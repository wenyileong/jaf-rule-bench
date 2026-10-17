"""Assemble a full run (default world, comparisons, sweep) into a JSON-ready payload."""
from __future__ import annotations
import datetime, hashlib, json
import numpy as np
from .params import Params, RULES, RULE_LABELS, SHORT, PREDICATE, VERSION, PARAM_SPEC
from . import experiments as X


def _f(x, n=5):
    if isinstance(x, np.ndarray):
        return np.round(x.astype(float), n).tolist()
    if isinstance(x, (float, np.floating)):
        return round(float(x), n)
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (np.bool_,)):
        return bool(x)
    return x


def summarise(eq):
    f = eq["failure"]
    return dict(tau=_f(eq["tau"]), mean_tau=_f(eq["tau"].mean()), theta=_f(eq["theta"]),
                effective=_f(eq["effective"]), revenue=_f(eq["revenue"].sum()), revenue_by=_f(eq["revenue"]),
                revenue_per_base=_f(eq["revenue_per_base"]), exit=_f(eq["exit"]),
                converged=bool(eq["converged"]), corner=bool(eq["corner"]), iterations=int(eq["iterations"]),
                network_share=_f(eq["network_share"]),
                assigned=_f(eq["Q"].sum(1)), gap=_f(f["gap"]), overlap=_f(f["overlap"]),
                unrelieved=_f(f["unrelieved"]), forgone=_f(f["forgone"]), unobserved=_f(f["unobserved"]), backstop=_f(f["backstop"]),
                P=_f(eq["P"]), F=_f(eq["F"], 6), Z=_f(np.diag(eq["M"]) - 1, 6))


class Progress:
    def __init__(self, cb, total):
        self.cb, self.total, self.done = cb, max(1, total), 0

    def step(self, label, w=1):
        self.done += w
        if self.cb:
            self.cb(min(1.0, self.done / self.total), label)


def run(P: Params, sweep_draws=12, grid=(6, 6), progress=None, cancel=lambda: False):
    nr = len(RULES)
    total = nr * 3 + nr + grid[0] * grid[1] + sweep_draws * nr + 2
    pr = Progress(progress, total)
    res, rules = {}, {}
    for r in RULES:
        comp, a, b = X.run_rule(r, P); res[r] = dict(comp=comp, a=a, b=b)
        L = X.leakage(comp, a) if X.usable(a) else dict(valid=False)
        rules[r] = dict(label=RULE_LABELS[r], short=SHORT[r], predicate=PREDICATE[r],
                        a=summarise(a), b=summarise(b), leakage={k: _f(v) for k, v in L.items() if k != "rows"})
        pr.step(f"Equilibrium: {SHORT[r]}", 3)
        if cancel(): raise KeyboardInterrupt
    # enforcement and network effect
    Pe = P.replace(enforcement=True); P0 = P.replace(beta=0.0)
    enforcement, network_effect = {}, {}
    for r in RULES:
        if cancel(): raise KeyboardInterrupt
        _, ea, _ = X.run_rule(r, Pe)
        enforcement[r] = dict(effective=_f(ea["effective"]), revenue=_f(ea["revenue"].sum()),
                              mean_tau=_f(ea["tau"].mean()), unobserved=_f(ea["failure"]["unobserved"]), corner=bool(ea["corner"]))
        _, za, zb = X.run_rule(r, P0)
        network_effect[r] = dict(a0=_f(za["effective"]), b0=_f(zb["effective"]),
                                 a=rules[r]["a"]["effective"], b=rules[r]["b"]["effective"],
                                 ya0=_f(za["revenue_per_base"]), yb0=_f(zb["revenue_per_base"]),
                                 ya=rules[r]["a"]["revenue_per_base"], yb=rules[r]["b"]["revenue_per_base"])
        pr.step(f"Comparisons: {SHORT[r]}")
    ranking = {f"{k[0]}|{k[1]}": v for k, v in X.ranking(res).items()}
    ranking_yield = {f"{k[0]}|{k[1]}": v for k, v in X.ranking(res, "revenue_per_base").items()}
    phis = list(np.round(np.linspace(0.0, 0.75, grid[0]), 3)); rhos = list(np.round(np.linspace(0.0, 1.0, grid[1]), 3))
    mp = X.matched_pair(P, phis, rhos, progress=lambda f: pr.step("Proposition 3 grid") if f else None)
    dists = X.distances(res)
    sweep = run_sweep(P, sweep_draws, pr, cancel)
    payload = dict(version=VERSION, generated=datetime.datetime.now().isoformat(timespec="seconds"),
                   params=P.to_dict(), param_spec=PARAM_SPEC, rules=rules, ranking=ranking, ranking_yield=ranking_yield,
                   enforcement=enforcement, network_effect=network_effect,
                   prop1=[{k: _f(v) for k, v in d.items()} for d in dists],
                   prop3=dict(phis=[float(x) for x in phis], rhos=[float(x) for x in rhos],
                              grid=[{k: _f(v) for k, v in c.items()} for c in mp]),
                   sweep=sweep, jurisdictions=dict(zip("aegv", [_f(x) for x in P.jurisdictions()])))
    payload["register"] = register(payload)
    pr.step("Done", 2)
    return payload


def run_sweep(base: Params, n, pr: Progress, cancel):
    rng = np.random.default_rng(base.seed * 31 + 5)
    levels = [0.25, 0.5, 1.0, 1.5]
    draws = []
    for d in range(n):
        if cancel(): raise KeyboardInterrupt
        P = base.replace(seed=int(rng.integers(1, 10_000)), mobility_scale=levels[d % len(levels)] * base.mobility_scale,
                         beta=float(rng.uniform(0.0, 50.0)), theta0=float(rng.uniform(2.6, 4.0)),
                         rho=float(rng.uniform(0.3, 1.0)), phi=float(rng.uniform(0.0, 0.4)),
                         sigma=float(rng.uniform(0.5, 2.0)), kappa_relief=float(rng.choice([10.0, 20.0, 40.0])))
        res, row = {}, dict(params=dict(seed=P.seed, mobility_scale=P.mobility_scale, beta=round(P.beta, 2),
                                        theta0=round(P.theta0, 2), rho=round(P.rho, 2), phi=round(P.phi, 2), sigma=round(P.sigma, 2)),
                            rules={})
        for r in RULES:
            comp, a, b = X.run_rule(r, P); res[r] = dict(comp=comp, a=a, b=b)
            L = X.leakage(comp, a, shocks=[int(np.argmax(a["Q"].sum(1)))], sizes=(0.05,)) if X.usable(a) else dict(valid=False)
            row["rules"][r] = dict(eff_a=_f(a["effective"]), eff_b=_f(b["effective"]),
                                   yield_a=_f(a["revenue_per_base"]), yield_b=_f(b["revenue_per_base"]), converged=bool(a["converged"] and b["converged"]),
                                   corner=bool(a["corner"]), gap=_f(a["failure"]["gap"]),
                                   leak={k: _f(L[k]) for k in X.LEAK_KEYS} if L.get("valid") else None)
            pr.step(f"Sweep draw {d + 1} of {n}: {r}")
        row["ranking"] = {f"{k[0]}|{k[1]}": v for k, v in X.ranking(res).items()}
        row["ranking_yield"] = {f"{k[0]}|{k[1]}": v for k, v in X.ranking(res, "revenue_per_base").items()}
        draws.append(row)
    return dict(n=n, draws=draws)


def register(payload):
    """Model outputs (fingerprinted) and draft observable hypotheses (not frozen)."""
    sw = payload["sweep"]["draws"]; out = []
    if sw:
        for rk, noun in (("ranking", "effective rate on the base it assigns"), ("ranking_yield", "yield per unit of base in the asset class")):
            for key, v in payload[rk].items():
                if v not in (">", "<"):
                    continue
                hold = [d[rk].get(key) for d in sw]
                ranked = [h for h in hold if h in (">", "<", "tie")]
                share = (sum(h == v for h in ranked) / len(ranked)) if ranked else 0.0
                if share >= 0.9 and len(ranked) >= max(3, len(sw) // 2):
                    r1, r2 = key.split("|")
                    out.append(dict(kind="ranking" if rk == "ranking" else "yield ranking",
                                    statement=f"{SHORT[r1]} sustains a {'higher' if v == '>' else 'lower'} {noun} than {SHORT[r2]} under both equilibrium concepts.",
                                    support=f"Same verdict in {share:.0%} of {len(ranked)} ranked sweep draws."))
    g = payload["prop3"]["grid"]
    phis = sorted({c["phi"] for c in g})
    ok = [p for p in phis if all(c["gap_worse"] for c in g if c["phi"] == p)]
    if ok:
        out.append(dict(kind="Proposition 3", statement=f"On the matched pair, the gap is the costlier failure at every tested level of treaty relief while φ ≤ {max(ok)}.",
                        support="Default world; matched rules X and Y."))
    lk = [(r, payload["rules"][r]["leakage"]) for r in payload["rules"] if payload["rules"][r]["leakage"].get("valid")]
    if lk:
        r, L = max(lk, key=lambda t: t[1]["to_gap"])
        out.append(dict(kind="Proposition 2", statement=f"After a rate rise, the largest single destination of base leaving a jurisdiction under {SHORT[r].lower()} is the gap ({L['to_gap']:.0%} on average across shocks).",
                        support="Default world; all jurisdictions shocked by 2 and 5 points."))
    fp = hashlib.sha256(json.dumps(out, sort_keys=True).encode()).hexdigest()
    hyp = [
        dict(id="H1", statement="Where intermediary location governs, a rise in the effective tax on intermediated holdings is followed by growth in self-custody relative to custodial balances.",
             data="Exchange-reported balances under CARF-type reporting; on-chain self-custody estimates.", status="Draft. Needs a data mapping and pre-registration before any data are examined."),
        dict(id="H2", statement="Where custodial predicates govern, a rate rise is followed by a shift of residents' custodial balances to foreign-domiciled exchanges (conduit and round-trip channels).",
             data="CARF exchange-of-information returns, by reporting provider jurisdiction and holder residence.", status="Draft. As H1."),
        dict(id="H3", statement="Improved observation of self-hosted holdings raises revenue under owner-residence and control rules but not under intermediary location.",
             data="Revenue statistics before and after reporting reforms, by rule family.", status="Draft. As H1."),
    ]
    return dict(model_outputs=out, fingerprint=fp, date=datetime.date.today().isoformat(), hypotheses=hyp)
