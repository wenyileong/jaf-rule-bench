# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Wen Yi LEONG
"""Known-truth recovery tests (build plan s 14, component B5).

The model generates synthetic "observations" at parameter values set in advance; the estimator is then run
blind, from starting values away from the truth, and must find them again. A noiseless run tests that the
estimator inverts the model; noisy runs (normal noise with each observation's stated standard error) test that
the reported standard errors are honest. Passing shows the instrument works. It does not show the model is
true: that is what validation on real data is for (plan s 14.3, issue 3).
"""
from __future__ import annotations
import copy
import numpy as np
from .design import Design
from .estimate import Model, estimate, validate, identification


def recovery(world, design: Design, truth: dict | None = None, reps=3, seed=99, base=None, starts=1,
             tol_noiseless=0.02, z_max=3.5, progress=None, cancel=lambda: False):
    """truth: values of the free parameters (default: the design's start values shifted inside the bounds)."""
    d0 = copy.deepcopy(design)
    d0.starts = starts
    probe = Model(world, d0, base, cancel=cancel)
    free, lo, hi = probe.free, probe.lo, probe.hi
    if not free:
        return dict(status="fail", message="No parameter is marked free.")
    if truth is None:                                    # a point that is not the start value
        st = probe.start()
        truth = {n: float(lo[j] + 0.6 * (hi[j] - lo[j])) if abs(st[j] - (lo[j] + 0.6 * (hi[j] - lo[j]))) > 0.05 * (hi[j] - lo[j])
                 else float(lo[j] + 0.4 * (hi[j] - lo[j])) for j, n in enumerate(free)}
    truth = {n: float(truth[n]) for n in free}
    # starting values away from the truth: the design's start, or a quarter of the range away if they coincide
    for p in d0.params:
        if p.free:
            j = free.index(p.name); t = truth[p.name]; s = p.value if p.value is not None else probe.start()[j]
            if abs(s - t) < 0.1 * (hi[j] - lo[j]):
                s = t - 0.25 * (hi[j] - lo[j]) if t - lo[j] > hi[j] - t else t + 0.25 * (hi[j] - lo[j])
            p.value = float(min(hi[j], max(lo[j], s)))
    obs = d0.observations
    clean = probe.moments(probe.full(override=truth), obs)
    if not np.all(np.isfinite(clean)):
        return dict(status="fail", message="Some quantities could not be computed at the true values.")
    ident = identification(probe, np.array([truth[n] for n in free]))
    rng = np.random.default_rng(seed)
    runs = []
    total = reps + 1
    for r in range(total):
        if cancel():
            raise KeyboardInterrupt
        noise = np.zeros(len(obs)) if r == 0 else rng.normal(0.0, [o.sd for o in obs])
        dr = d0.with_values({o.id: float(v) for o, v in zip(obs, clean + noise)})
        m = Model(world, dr, base, cancel=cancel)
        cb = (lambda f, l, r=r: progress((r + f) / total, f"{'Noiseless run' if r == 0 else f'Noisy run {r} of {reps}'}: {l}")) if progress else None
        e = estimate(m, override=True, progress=cb)
        est = {p["name"]: p for p in e["params"]}
        row = dict(rep=r, noise=r > 0, J=e["J"], params={})
        for j, n in enumerate(free):
            x, se = est[n]["estimate"], est[n]["se"]
            row["params"][n] = dict(estimate=x, se=se, error=x - truth[n], rel_error=(x - truth[n]) / (hi[j] - lo[j]),
                                    z=(x - truth[n]) / se if se and np.isfinite(se) and se > 0 else None,
                                    covered=bool(abs(x - truth[n]) <= 1.96 * se) if se and np.isfinite(se) else None)
        if r == 0 and dr.holdouts():
            v = validate(m, e)
            row["validation"] = dict(passed=v["passed"], n=v["n"])
        runs.append(row)
    summary = []
    for j, n in enumerate(free):
        noiseless = runs[0]["params"][n]
        noisy = [x["params"][n] for x in runs[1:]]
        ests = np.array([x["estimate"] for x in noisy]) if noisy else np.array([])
        zs = [abs(x["z"]) for x in noisy if x["z"] is not None]
        ok_clean = abs(noiseless["rel_error"]) <= tol_noiseless
        ok_noisy = all(z <= z_max for z in zs) and len(zs) == len(noisy)
        summary.append(dict(name=n, truth=truth[n], lower=float(lo[j]), upper=float(hi[j]),
                            noiseless=noiseless["estimate"], noiseless_rel_error=noiseless["rel_error"],
                            mean=float(ests.mean()) if ests.size else None, bias=float(ests.mean() - truth[n]) if ests.size else None,
                            rmse=float(np.sqrt(((ests - truth[n]) ** 2).mean())) if ests.size else None,
                            mean_se=float(np.mean([x["se"] for x in noisy])) if noisy else None,
                            coverage=float(np.mean([bool(x["covered"]) for x in noisy])) if noisy else None,
                            max_abs_z=float(max(zs)) if zs else None, passed_noiseless=bool(ok_clean), passed_noisy=bool(ok_noisy)))
    passed = all(s["passed_noiseless"] for s in summary) and all(s["passed_noisy"] for s in summary)
    if progress:
        progress(1.0, "Done")
    return dict(status="ok", passed=bool(passed), truth=truth, reps=reps, seed=seed, identification=ident,
                summary=summary, runs=runs, criteria=dict(noiseless=f"error within {tol_noiseless:.0%} of the parameter's range",
                                                          noisy=f"every noisy estimate within {z_max} standard errors of the truth"))
