"""Estimation, identification diagnostics and validation (build plan s 14, components B3, B4 and B6).

Method: simulated minimum distance. Chosen behavioural parameters are set so that the model-implied measured
quantities (measure.py) come as close as possible to the observed ones, each deviation weighted by the
inverse of its stated measurement variance:

    J(theta) = sum_i ((m_i(theta) - y_i) / sd_i)^2   over target observations.

Uncertainty is propagated from the stated measurement errors by the delta method,
Var(theta_hat) ~ (G' W G)^-1 with W = diag(1/sd^2) and G the Jacobian of the moments. It is not a sampling
error: the data used are aggregates without sampling theory (plan s 14.3, issue 6). Identification is
checked locally, before estimation and again at the estimate, from the same Jacobian.
"""
from __future__ import annotations
import math
import numpy as np
from .params import Params
from .world import World
from .design import Design, ParamSpec, apply_episode, BASELINE
from .mixed import MixedCompiled
from .equilibrium import solve
from .measure import Measured, observation_value, QUANTITIES

# name: where it lives, default bounds, plain label, technical label
# lo, hi: default bounds offered for estimation. dom: the values the model admits at all (validated on input).
EST_PARAMS = {
    "theta0": dict(where="params", lo=2.0, hi=8.0, dom=(0.01, 50.0), plain="How strongly holders react to tax rates", tech="θ₀ baseline semi-elasticity"),
    "beta": dict(where="params", lo=0.0, hi=60.0, dom=(0.0, 500.0), plain="How much escape routes add to that reaction", tech="β weight of escape capacity"),
    "sigma": dict(where="params", lo=0.0, hi=3.0, dom=(0.0, 10.0), plain="How attached holders are to where they operate", tech="σ dispersion of location tastes"),
    "exit_weight": dict(where="params", lo=0.05, hi=3.0, dom=(0.001, 100.0), plain="Appeal of leaving digital assets altogether", tech="Outside-option weight"),
    "home_bias": dict(where="params", lo=0.3, hi=0.95, dom=(0.0, 0.999), plain="Share of transactions that stay at home", tech="Home bias of flows"),
    "alpha": dict(where="params", lo=0.1, hi=0.95, dom=(0.0, 0.99), plain="How far indirect routes reach", tech="α Katz discount"),
    "mobility_custodial": dict(where="settings", lo=0.01, hi=2.0, dom=(0.0, 10.0), plain="Ease of using a foreign exchange", tech="Custodial mobility (scaled by exchange presence)"),
    "mobility_self_hosted": dict(where="settings", lo=0.01, hi=2.0, dom=(0.0, 10.0), plain="Ease of placing self-held keys abroad", tech="Self-hosted mobility"),
}


class IdentificationError(Exception):
    pass


def validate_spec(params) -> list:
    """Errors in a list of ParamSpec (shared by the workbook reader and the interface)."""
    errs, seen = [], set()
    for p in params:
        if p.name not in EST_PARAMS:
            errs.append(f"Unknown parameter '{p.name}'."); continue
        if p.name in seen:
            errs.append(f"{p.name} is listed more than once.")
        seen.add(p.name)
        dlo, dhi = EST_PARAMS[p.name]["dom"]
        inside = lambda v: v is None or dlo <= v <= dhi
        for label, v in (("value", p.value), ("lower bound", p.lower), ("upper bound", p.upper),
                         ("judgement range (low)", p.judgement_low), ("judgement range (high)", p.judgement_high)):
            if v is not None and not math.isfinite(v):
                errs.append(f"{p.name}: the {label} must be a finite number.")
            elif not inside(v):
                errs.append(f"{p.name}: the {label} ({v}) is outside the values the model admits ({dlo} to {dhi}).")
        lo = p.lower if p.lower is not None else EST_PARAMS[p.name]["lo"]
        hi = p.upper if p.upper is not None else EST_PARAMS[p.name]["hi"]
        if p.free:
            if not lo < hi:
                errs.append(f"{p.name}: the lower bound must be below the upper bound.")
            elif p.value is not None and not lo <= p.value <= hi:
                errs.append(f"{p.name}: the start value must lie within the bounds.")
        if (p.judgement_low is None) != (p.judgement_high is None):
            errs.append(f"{p.name}: give both ends of the judgement range, or neither.")
        elif p.judgement_low is not None and p.judgement_low > p.judgement_high:
            errs.append(f"{p.name}: the judgement range is reversed.")
    return errs


# ---- chi-square tail (regularised upper incomplete gamma), to avoid a scipy dependency ---------------
def _gammq(a, x):
    if x < 0 or a <= 0:
        return float("nan")
    if x == 0:
        return 1.0
    gln = math.lgamma(a)
    if x < a + 1:                                   # series for P, then Q = 1 - P
        ap, s, d = a, 1.0 / a, 1.0 / a
        for _ in range(500):
            ap += 1; d *= x / ap; s += d
            if abs(d) < abs(s) * 1e-14:
                break
        return max(0.0, 1.0 - s * math.exp(-x + a * math.log(x) - gln))
    b = x + 1 - a; c = 1 / 1e-300; d = 1 / b; h = d   # continued fraction for Q
    for i in range(1, 500):
        an = -i * (i - a); b += 2
        d = an * d + b; d = 1e-300 if abs(d) < 1e-300 else d
        c = b + an / c; c = 1e-300 if abs(c) < 1e-300 else c
        d = 1 / d; de = d * c; h *= de
        if abs(de - 1) < 1e-14:
            break
    return min(1.0, math.exp(-x + a * math.log(x) - gln) * h)


def chi2_sf(x, dof):
    return _gammq(dof / 2.0, x / 2.0) if dof > 0 else float("nan")


# ---- the model as a function of parameters ------------------------------------------------------
class Model:
    """Maps parameter values to model-implied measured quantities across the design's episodes."""

    def __init__(self, world: World, design: Design, base: Params | None = None, cancel=lambda: False, tol=1e-6):
        self.world, self.design, self.base = world, design, base or Params()
        self.cancel, self.tol = cancel, tol
        self.ep_worlds = {e: apply_episode(world, design.episode(e)) for e in design.episode_names()}
        self.cache, self.warm = {}, {}
        self.evals = 0
        spec = {p.name: p for p in design.params}
        self.free = [p.name for p in design.params if p.free]
        self.lo = np.array([_bound(spec[n], "lower", n) for n in self.free])
        self.hi = np.array([_bound(spec[n], "upper", n) for n in self.free])
        self.fixed = {}
        for p in design.params:
            if not p.free and p.value is not None and p.name in EST_PARAMS:
                self.fixed[p.name] = float(p.value)

    # parameter vectors -----------------------------------------------------------------
    def full(self, theta=None, override=None):
        """All estimable parameter values: interface or world values, then fixed values, then free values."""
        v = {}
        for n, d in EST_PARAMS.items():
            v[n] = float(getattr(self.base, n)) if d["where"] == "params" else float(getattr(self.world.settings, n))
        v.update(self.fixed)
        if theta is not None:
            v.update(dict(zip(self.free, map(float, theta))))
        if override:
            v.update(override)
        return v

    def start(self):
        spec = {p.name: p for p in self.design.params}
        out = []
        for n, lo, hi in zip(self.free, self.lo, self.hi):
            s = spec[n].value
            x = float(s) if s is not None else self.full()[n]
            out.append(min(hi, max(lo, x)))
        return np.array(out)

    # solving ---------------------------------------------------------------------------
    def measured(self, values: dict, episodes):
        key = tuple(round(values[n], 12) for n in sorted(values))
        out = {}
        for e in episodes:
            k = (e, key)
            if k not in self.cache:
                if self.cancel():
                    raise KeyboardInterrupt
                w = self.ep_worlds[e]
                ws = World.from_dict(w.to_dict())
                ps = {}
                for n, val in values.items():
                    if EST_PARAMS[n]["where"] == "settings":
                        setattr(ws.settings, n, val)
                    else:
                        ps[n] = val
                P = self.base.replace(**ps)
                comp = MixedCompiled(ws, P)
                eq = solve(comp, self.design.concept, tau0=self.warm.get(e), tol=self.tol, eps_tol=1e-7)
                self.warm[e] = eq["tau"]
                self.evals += 1
                if len(self.cache) > 4000:
                    self.cache.clear()
                self.cache[k] = (Measured(comp, eq, self.design), bool(eq["converged"]), eq.get("epsilon"))
            out[e] = self.cache[k][0]
        return out

    def moments(self, values: dict, obs):
        eps = sorted({o.episode for o in obs} | {o.compared_with for o in obs if o.compared_with})
        meas = self.measured(values, eps)
        return np.array([observation_value(o, meas) for o in obs], float)

    def converged(self, values: dict):
        key = tuple(round(values[n], 12) for n in sorted(values))
        return all(v[1] for (e, k), v in self.cache.items() if k == key)

    def approximate(self, values: dict):
        """Largest forgone revenue gain among episodes whose rates were accepted as an epsilon-equilibrium (None if none)."""
        key = tuple(round(values[n], 12) for n in sorted(values))
        eps = [v[2] for (e, k), v in self.cache.items() if k == key and v[2] is not None]
        return max(eps) if eps else None

    def jacobian(self, theta, obs, rel_step=5e-3):
        """Central differences in natural units; one-sided at a bound."""
        G = np.zeros((len(obs), len(theta)))
        for j in range(len(theta)):
            h = rel_step * (self.hi[j] - self.lo[j])
            up, dn = theta.copy(), theta.copy()
            up[j] = min(self.hi[j], theta[j] + h); dn[j] = max(self.lo[j], theta[j] - h)
            G[:, j] = (self.moments(self.full(up), obs) - self.moments(self.full(dn), obs)) / (up[j] - dn[j])
        return G


def _bound(spec: ParamSpec, which, name):
    v = getattr(spec, which)
    return float(v) if v is not None else float(EST_PARAMS[name]["lo" if which == "lower" else "hi"])


# ---- transformation to an unbounded space -------------------------------------------------------
def to_u(v, lo, hi):
    z = np.clip((v - lo) / (hi - lo), 1e-6, 1 - 1e-6)
    return np.log(z / (1 - z))


def from_u(u, lo, hi):
    return lo + (hi - lo) / (1 + np.exp(-np.asarray(u, float)))


# ---- Nelder-Mead ---------------------------------------------------------------------------------
def nelder_mead(f, x0, step=0.6, maxfev=300, xatol=1e-3, fatol=1e-6, callback=None):
    n = len(x0)
    sim = [np.array(x0, float)] + [np.array(x0, float) + step * np.eye(n)[i] for i in range(n)]
    fs = [f(x) for x in sim]; fev = n + 1
    while fev < maxfev:
        order = np.argsort(fs); sim = [sim[i] for i in order]; fs = [fs[i] for i in order]
        if callback:
            callback(fev, fs[0])
        if max(np.abs(s - sim[0]).max() for s in sim[1:]) < xatol and abs(fs[-1] - fs[0]) <= fatol * max(1.0, abs(fs[0])):
            break
        c = np.mean(sim[:-1], axis=0)
        xr = c + (c - sim[-1]); fr = f(xr); fev += 1
        if fr < fs[0]:
            xe = c + 2 * (c - sim[-1]); fe = f(xe); fev += 1
            sim[-1], fs[-1] = (xe, fe) if fe < fr else (xr, fr)
        elif fr < fs[-2]:
            sim[-1], fs[-1] = xr, fr
        else:
            xc = c + 0.5 * (sim[-1] - c) if fr >= fs[-1] else c + 0.5 * (xr - c)
            fc = f(xc); fev += 1
            if fc < min(fr, fs[-1]):
                sim[-1], fs[-1] = xc, fc
            else:
                for i in range(1, n + 1):
                    sim[i] = sim[0] + 0.5 * (sim[i] - sim[0]); fs[i] = f(sim[i]); fev += 1
    k = int(np.argmin(fs))
    return sim[k], fs[k], fev


def levenberg_marquardt(resid, u0, jac, max_iter=40, ftol=1e-7, xtol=1e-5, callback=None):
    """Levenberg-Marquardt on residuals r(u) (unbounded u). jac(u, r) returns dr/du. Returns (u, cost, evaluations)."""
    u = np.array(u0, float); r = resid(u); cost = float(r @ r); fev = 1; lam = 1e-2
    if not np.isfinite(cost):
        return u, cost, fev
    for it in range(max_iter):
        if callback:
            callback(fev, cost)
        Jm = jac(u, r); fev += len(u)
        A = Jm.T @ Jm; g = Jm.T @ r
        improved = False
        for _ in range(12):
            D = np.diag(np.maximum(np.diag(A), 1e-12))
            try:
                step = -np.linalg.solve(A + lam * D, g)
            except np.linalg.LinAlgError:
                lam *= 10; continue
            step = np.clip(step, -3.0, 3.0)
            rn = resid(u + step); fev += 1
            cn = float(rn @ rn) if np.all(np.isfinite(rn)) else np.inf
            if cn < cost:
                rel = (cost - cn) / max(cost, 1e-300)
                u, r, cost = u + step, rn, cn
                lam = max(lam / 3, 1e-9); improved = True
                break
            lam *= 4
        if not improved or rel < ftol or np.abs(step).max() < xtol:
            break
    return u, cost, fev


# ---- identification diagnostics (B4) -------------------------------------------------------------
def identification(model: Model, theta=None, obs=None, G=None):
    """Local identification of the free parameters by the target observations at theta."""
    d = model.design
    obs = obs if obs is not None else d.targets()
    k, n = len(model.free), len(obs)
    theta = model.start() if theta is None else np.asarray(theta, float)
    out = dict(free=model.free, n_targets=n, n_free=k, at=dict(zip(model.free, map(float, theta))))
    if k == 0:
        return dict(out, status="fail", reasons=["No parameter is marked free."], params=[])
    if n == 0:
        return dict(out, status="fail", reasons=["The design has no target observations."], params=[])
    sd = np.array([o.sd for o in obs], float)
    if G is None:
        G = model.jacobian(theta, obs)
    rng = model.hi - model.lo
    Gs = G / sd[:, None] * rng[None, :]                 # change in standardised moment per full range of the parameter
    reasons = []
    if not np.all(np.isfinite(Gs)):
        return dict(out, status="fail", reasons=["Some quantities could not be computed at the starting values (for example a share with an empty denominator)."], params=[])
    U, S, Vt = np.linalg.svd(Gs, full_matrices=True)        # Vt is k x k, so Vt[rank:] spans the whole null space
    smax = S.max() if S.size else 0.0
    cond = float(smax / S.min()) if S.size and S.min() > 0 else float("inf")
    info = Gs.T @ Gs
    cov_s = np.linalg.pinv(info)                        # in units of parameter range
    rank = int((S > 1e-8 * max(smax, 1e-300)).sum())
    se_rel = np.sqrt(np.maximum(np.diag(cov_s), 0))
    col = np.linalg.norm(Gs, axis=0)
    params = []
    for j, name in enumerate(model.free):
        if col[j] < 1e-6:
            status = "no effect"
        elif rank < k and np.abs(Vt[rank:, j]).max() > 0.1:
            status = "not identified"
        elif se_rel[j] < 0.10:
            status = "identified"
        elif se_rel[j] < 0.33:
            status = "weak"
        else:
            status = "not identified"
        params.append(dict(name=name, sensitivity=float(col[j]), rel_se=float(se_rel[j]) if rank == k else float("inf"),
                           se=float(se_rel[j] * rng[j]) if rank == k else float("inf"), status=status))
    if n < k:
        reasons.append(f"Fewer target observations ({n}) than free parameters ({k}): the order condition fails.")
    if rank < k:
        reasons.append(f"The targets move together in fewer directions ({rank}) than there are free parameters ({k}).")
    bad = [p["name"] for p in params if p["status"] in ("no effect", "not identified")]
    weak = [p["name"] for p in params if p["status"] == "weak"]
    if bad:
        reasons.append("Not identified by these targets: " + ", ".join(bad) + ". Fix them by judgement, or add targets that respond to them.")
    if weak:
        reasons.append("Weakly identified: " + ", ".join(weak) + ". Estimates will be imprecise.")
    flat = []
    for idx in range(k):                                  # rows beyond len(S) (fewer targets than parameters) are exactly flat
        sv = S[idx] if idx < len(S) else 0.0
        if sv < 1e-2 * smax:
            v = Vt[idx]; v = v / np.abs(v).max()
            flat.append(dict(singular=float(sv / smax) if smax > 0 else 0.0, direction={model.free[j]: float(v[j]) for j in range(k) if abs(v[j]) > 0.05}))
    corr = None
    if rank == k:
        dsd = np.sqrt(np.diag(cov_s))
        corr = (cov_s / np.outer(dsd, dsd)).tolist()
    status = "fail" if (n < k or rank < k or bad) else ("weak" if weak or cond > 1e3 else "ok")
    if cond > 1e3 and not weak and status == "weak":
        reasons.append(f"The problem is ill-conditioned (condition number {cond:.0f}): parameters trade off against each other.")
    return dict(out, status=status, reasons=reasons, params=params, rank=rank, condition=cond,
                singular_values=(S / smax).tolist() if smax > 0 else S.tolist(), flat_directions=flat, correlation=corr,
                sensitivity=Gs.tolist(), targets=[o.id for o in obs])


# ---- estimation (B3) -------------------------------------------------------------------------------
def objective_factory(model: Model, obs):
    y = np.array([o.value for o in obs], float); sd = np.array([o.sd for o in obs], float)
    def J(theta):
        m = model.moments(model.full(theta), obs)
        r = (m - y) / sd
        if not np.all(np.isfinite(r)):
            return 1e12
        return float(r @ r)
    return J


def estimate(model: Model, override=False, maxfev=None, progress=None, check_first=True, method="lm"):
    d = model.design
    obs = d.targets()
    missing = [o.id for o in obs if o.value is None]
    if missing:
        raise ValueError("Target observations without values: " + ", ".join(missing[:8]) + (" …" if len(missing) > 8 else ""))
    k = len(model.free)
    ident0 = identification(model) if check_first else None
    if ident0 is not None and ident0["status"] == "fail" and not override:
        return dict(status="refused", identification_start=ident0,
                    message="Estimation was not run because the free parameters are not identified by the targets at the starting values. "
                            "Fix some parameters, add targets, or override (results would not be reliable).")
    J = objective_factory(model, obs)
    lo, hi = model.lo, model.hi
    f = lambda u: J(from_u(u, lo, hi))
    y = np.array([o.value for o in obs], float); sdv = np.array([o.sd for o in obs], float)
    def resid(u):
        return (model.moments(model.full(from_u(u, lo, hi)), obs) - y) / sdv
    def jac(u, r0):
        Jm = np.zeros((len(r0), len(u)))
        for j in range(len(u)):
            h = 1e-3 * (1 + abs(u[j]))
            e = u.copy(); e[j] += h
            Jm[:, j] = (resid(e) - r0) / h
        return Jm
    rng = np.random.default_rng(d.seed)
    starts = [model.start()] + [lo + (hi - lo) * rng.uniform(0.15, 0.85, k) for _ in range(max(0, d.starts - 1))]
    maxfev = maxfev or (120 + 60 * k) if method == "nm" else (maxfev or 12 * (k + 2))
    runs = []
    for si, st in enumerate(starts):
        def cb(fev, fbest, si=si):
            if progress:
                progress(min(0.95, (si + fev / maxfev) / len(starts)), f"Search {si + 1} of {len(starts)}: J = {fbest:.4g}")
        if method == "nm":
            u, fu, fev = nelder_mead(f, to_u(st, lo, hi), maxfev=maxfev, callback=cb)
        else:
            u, fu, fev = levenberg_marquardt(resid, to_u(st, lo, hi), jac, callback=lambda fev, c: cb(min(fev, maxfev), c))
        runs.append(dict(start=dict(zip(model.free, map(float, st))), estimate=from_u(u, lo, hi), J=fu, evaluations=fev))
    best = min(runs, key=lambda r: r["J"])
    theta = best["estimate"]
    if progress:
        progress(0.96, "Standard errors and identification at the estimate")
    G = model.jacobian(theta, obs)
    sd = np.array([o.sd for o in obs], float)
    W = np.diag(1 / sd ** 2)
    info = G.T @ W @ G
    singular = np.linalg.matrix_rank(info) < k
    if singular:                    # some direction is undetermined: no finite covariance exists
        cov = np.full((k, k), np.nan)
    else:
        try:
            cov = np.linalg.inv(info)
        except np.linalg.LinAlgError:
            cov, singular = np.full((k, k), np.nan), True
    se = np.sqrt(np.maximum(np.diag(cov), 0)) if not singular else np.full(k, np.inf)
    ident = identification(model, theta, obs, G=G)
    m = model.moments(model.full(theta), obs)
    y = np.array([o.value for o in obs], float)
    z = (m - y) / sd
    Jv = float(z @ z); dof = len(obs) - k
    spread = [float(np.max(np.abs((r["estimate"] - theta) / (hi - lo)))) for r in runs]
    multi = any(s_ > 0.05 and r["J"] <= best["J"] + max(0.5, 0.05 * best["J"]) for r, s_ in zip(runs, spread))
    params = []
    for j, name in enumerate(model.free):
        rngj = hi[j] - lo[j]
        params.append(dict(name=name, estimate=float(theta[j]), se=float(se[j]), lower=float(lo[j]), upper=float(hi[j]),
                           ci_low=float(max(lo[j], theta[j] - 1.96 * se[j])) if np.isfinite(se[j]) else float(lo[j]),
                           ci_high=float(min(hi[j], theta[j] + 1.96 * se[j])) if np.isfinite(se[j]) else float(hi[j]),
                           at_bound=bool(min(theta[j] - lo[j], hi[j] - theta[j]) < 0.005 * rngj),
                           start=float(starts[0][j])))
    fit = [dict(id=o.id, quantity=o.quantity, code=o.code, episode=o.episode, compared_with=o.compared_with, comparison=o.comparison,
                observed=float(o.value), model=float(mi), sd=float(o.sd), z=float(zi)) for o, mi, zi in zip(obs, m, z)]
    warnings = []
    if any(p["at_bound"] for p in params):
        warnings.append("An estimate lies at a bound of its range: the bound, not the data, determines it.")
    if multi:
        warnings.append("Different starting points reach different parameter values with a similar fit: the objective has more than one near-minimum.")
    if not model.converged(model.full(theta)):
        warnings.append("At the estimate, rates in at least one episode did not fully settle.")
    ap = model.approximate(model.full(theta))
    if ap is not None:
        warnings.append(f"At the estimate, rates in at least one episode settled only approximately (no state could gain more than {ap:.1e} of its revenue by deviating).")
    if singular:
        warnings.append("The estimates are not determined in at least one direction: no standard errors can be given, and predictions cannot be scored.")
    if ident["status"] != "ok":
        warnings.extend(ident["reasons"])
    if progress:
        progress(1.0, "Done")
    return dict(status="ok", params=params, cov=cov.tolist(), J=Jv, dof=dof,
                p_value=float(chi2_sf(Jv, dof)) if dof > 0 else None, fit=fit,
                theta=[float(x) for x in theta], values=model.full(theta),
                runs=[dict(start=r["start"], estimate=dict(zip(model.free, map(float, r["estimate"]))), J=float(r["J"]), evaluations=r["evaluations"]) for r in runs],
                identification_start=ident0, identification=ident, warnings=warnings, evaluations=model.evals)


# ---- validation (B6) -------------------------------------------------------------------------------
def validate(model: Model, est: dict, obs=None, progress=None):
    """Predict observations not used in fitting; compare with what was observed."""
    d = model.design
    obs = obs if obs is not None else d.holdouts()
    if not obs:
        return dict(status="none", message="The design has no holdout observations.", rows=[])
    theta = np.array(est["theta"], float)
    cov = np.array(est["cov"], float)
    base_vals = model.full(theta)
    pred = model.moments(base_vals, obs)
    if progress:
        progress(0.4, "Propagating parameter uncertainty")
    H = model.jacobian(theta, obs) if len(theta) else np.zeros((len(obs), 0))
    var_p = np.einsum("ij,jk,ik->i", H, cov, H) if len(theta) else np.zeros(len(obs))
    # judgement band from parameters fixed by judgement with a stated range (one at a time, combined in quadrature)
    band2 = np.zeros(len(obs)); used = []
    for p in d.params:
        if p.free or p.name not in EST_PARAMS or p.judgement_low is None or p.judgement_high is None:
            continue
        devs = []
        for v in (p.judgement_low, p.judgement_high):
            devs.append(model.moments(model.full(theta, override={p.name: float(v)}), obs) - pred)
        dev = np.max(np.abs(np.vstack(devs)), axis=0)
        band2 += (dev / 1.96) ** 2
        used.append(p.name)
    if progress:
        progress(0.9, "Comparing predictions with observations")
    rows = []
    for o, pr, vp, b2 in zip(obs, pred, var_p, band2):
        row = dict(id=o.id, quantity=o.quantity, code=o.code, episode=o.episode, compared_with=o.compared_with, comparison=o.comparison,
                   prediction=float(pr), observed=o.value, sd=o.sd)
        if not (math.isfinite(vp) and math.isfinite(b2) and math.isfinite(pr)):
            row.update(model_sd=None, param_sd=None, judgement_sd=None, lo=None, hi=None, unscorable=True)
            rows.append(row); continue
        model_sd = math.sqrt(max(0.0, vp) + b2)
        row.update(model_sd=model_sd, param_sd=math.sqrt(max(0.0, vp)), judgement_sd=math.sqrt(b2),
                   lo=float(pr - 1.96 * model_sd), hi=float(pr + 1.96 * model_sd))
        if o.value is not None:
            z = (o.value - pr) / math.sqrt(o.sd ** 2 + model_sd ** 2)
            row.update(z=float(z), passed=bool(abs(z) <= 1.96))
        rows.append(row)
    scored = [r for r in rows if "z" in r]
    chi = float(sum(r["z"] ** 2 for r in scored))
    return dict(status="ok", rows=rows, judgement_params=used, n=len(scored), unscorable=sum(1 for r in rows if r.get("unscorable")),
                passed=sum(r["passed"] for r in scored), chi2=chi, p_value=float(chi2_sf(chi, len(scored))) if scored else None)
