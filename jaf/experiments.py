# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Wen Yi LEONG
"""Experiments (build plan s 5, revised s 10)."""
from __future__ import annotations
import numpy as np
from .params import Params, RULES, PREDICATE
from .rules import Compiled
from .equilibrium import solve
from .network import flows, resolvent, round_trip

LEAK_KEYS = ("migration", "round_trip", "conduit_switching", "foreign_relocation", "to_gap", "exit")


def run_rule(rule, P: Params):
    comp = Compiled(rule, P)
    a = solve(comp, "a")
    b = solve(comp, "b", tau0=a["tau"])
    return comp, a, b


def usable(x):
    return x["converged"] and not x["corner"]


def ranking(res, metric="effective"):
    """Pairwise verdicts on the effective rate, declared only where both concepts agree."""
    out = {}
    names = list(res)
    for n, r1 in enumerate(names):
        for r2 in names[n + 1:]:
            A, B = res[r1], res[r2]
            if not all(usable(x) for x in (A["a"], A["b"], B["a"], B["b"])):
                out[(r1, r2)] = "unranked"; continue
            da = A["a"][metric] - B["a"][metric]; db = A["b"][metric] - B["b"][metric]
            out[(r1, r2)] = (">" if da > 0 else "<") if np.sign(da) == np.sign(db) else "tie"
    return out


def leakage(comp: Compiled, eq, shocks=None, sizes=(0.02, 0.05)):
    """Six-way decomposition of the base lost after a rate rise, from per-draw transitions.

    Within each simulation draw the logit kernel substitutes in proportion to shares, so the base
    leaving the options a jurisdiction taxes is distributed over all other options and exit in
    proportion to their gains. Origin (economic location) and destination are then classified:
    own activity -> same location, assigned abroad = round-tripping; -> other location = migration;
    foreign activity hosted by i -> same location, other host = conduit switching;
    -> other location = foreign relocation; any -> gap; any -> exit.
    """
    P = comp.P
    tau0, theta = eq["tau"], eq["theta"]
    shocks = range(P.N) if shocks is None else shocks
    rows = []
    S0, X0 = comp.draw_shares(tau0, theta)
    onehot = np.eye(P.N)[comp.j]                                   # K x N
    assigned = (comp.kprim >= 0).astype(float)
    for i in shocks:
        for d in sizes:
            tau1 = tau0.copy(); tau1[i] = min(P.tau_max, tau1[i] + d)
            S1, X1 = comp.draw_shares(tau1, theta)
            dec = np.maximum(0.0, S0 - S1); inc = np.maximum(0.0, S1 - S0); incX = np.maximum(0.0, X1 - X0)
            T = inc.sum(1) + incX
            lost = dec.sum()
            if lost <= 1e-9:
                continue
            D = dec @ onehot                                           # R x N origin by economic location
            A = (inc * assigned) @ onehot                              # R x N assigned gains by location
            G = (inc * (1 - assigned)).sum(1)
            tot = {k: 0.0 for k in LEAK_KEYS}
            for e in range(P.N):
                frac = np.divide(D[:, e], T, out=np.zeros_like(T), where=T > 0)
                same = (frac * A[:, e]).sum(); diff = (frac * (T - A[:, e] - G - incX)).sum()
                if e == i:
                    tot["round_trip"] += same; tot["migration"] += diff
                else:
                    tot["conduit_switching"] += same; tot["foreign_relocation"] += diff
                tot["to_gap"] += (frac * G).sum(); tot["exit"] += (frac * incX).sum()
            rows.append(dict(shocked=int(i), size=d, **{k: v / lost for k, v in tot.items()}))
    if not rows:
        return dict(valid=False)
    Q0 = eq["Q"]
    out = dict(valid=True, n=len(rows), predicate=PREDICATE.get(comp.rule, "mixed"))
    for k in LEAK_KEYS:
        v = np.array([r[k] for r in rows]); out[k] = float(v.mean()); out[k + "_min"] = float(v.min()); out[k + "_max"] = float(v.max())
    out["alignment"] = float(np.trace(Q0) / Q0.sum()) if Q0.sum() > 0 else 0.0
    out["rows"] = rows
    return out


def distances(res):
    rows = []
    names = [r for r in res if usable(res[r]["a"])]
    for n, r1 in enumerate(names):
        for r2 in names[n + 1:]:
            A, B = res[r1]["a"], res[r2]["a"]
            dnet = float(np.abs(A["P"] - B["P"]).sum() / A["P"].shape[0])
            def dist(x):
                return np.r_[x["Q"].sum(1), x["gapj"].sum(), x["exit"]]
            dbase = float(0.5 * np.abs(dist(A) - dist(B)).sum())
            dinc = float(abs(A["failure"]["gap"] - B["failure"]["gap"]) + abs(A["failure"]["overlap"] - B["failure"]["overlap"])
                         + abs(A["failure"]["unobserved"] - B["failure"]["unobserved"]))
            dout = float(abs(A["effective"] - B["effective"]))
            rows.append(dict(pair=[r1, r2], network=dnet, base=dbase, incidence=dinc, outcome=dout,
                             third_channel=bool(dnet < 0.05 and dbase < 0.05 and dout > 0.02)))
    return rows


def matched_pair(P: Params, phis, rhos, weight=1.0, progress=None):
    """Proposition 3 on the matched pair: same holdings fail, by gap under X and by overlap under Y."""
    grid = []; n = len(phis) * len(rhos); k = 0
    for phi in phis:
        for rho in rhos:
            Q = P.replace(phi=phi, rho=rho)
            ex = solve(Compiled("X_gap", Q), "a"); ey = solve(Compiled("Y_overlap", Q), "a")
            gap_cost = ex["failure"]["forgone"]; over_cost = ey["failure"]["unrelieved"] * weight
            grid.append(dict(phi=phi, rho=rho, gap_cost=gap_cost, overlap_cost=over_cost,
                             gap_volume=ex["failure"]["gap"], overlap_volume=ey["failure"]["overlap"],
                             gap_worse=bool(gap_cost > over_cost), converged=bool(ex["converged"] and ey["converged"])))
            k += 1
            if progress: progress(k / n)
    return grid
