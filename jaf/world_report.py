"""Run a coded world and its counterfactuals; produce the payload for the interface (build plan s 12)."""
from __future__ import annotations
import datetime
import numpy as np
from .params import Params, VERSION, CONFIGS
from .world import World, mismatch_matrix, personal_mismatches, LIABILITY
from .mixed import MixedCompiled
from .equilibrium import solve
from . import experiments as X
from .report import _f


def _solve_world(world: World, P: Params, concepts=("a", "b"), leak=True, cancel=lambda: False, step=lambda l: None):
    comp = MixedCompiled(world, P)
    out = {}
    for k in concepts:
        if cancel():
            raise KeyboardInterrupt
        e = solve(comp, k)
        bj = comp.by_jurisdiction(e["tau"], e["s"])
        d = dict(tau=_f(e["tau"]), theta=_f(e["theta"]), revenue=_f(e["revenue"]), revenue_total=_f(e["revenue"].sum()),
                 converged=bool(e["converged"]), iterations=int(e["iterations"]), exit=_f(e["exit"]),
                 failure={x: _f(v) for x, v in e["failure"].items()},
                 F=_f(e["F"], 6), assigned=_f(e["Q"].sum(1)), Z=_f(np.diag(e["M"]) - 1, 6),
                 yield_=_f(e["revenue_per_base"]),
                 **{x: _f(v) for x, v in bj.items()})
        if leak and k == "a" and e["converged"]:
            L = X.leakage(comp, e, shocks=range(world.N), sizes=(0.02, 0.05))
            if L.get("valid"):
                per = {}
                for r in L["rows"]:
                    per.setdefault(r["shocked"], []).append(r)
                d["leakage"] = {world.codes[i]: {key: _f(float(np.mean([x[key] for x in rows]))) for key in X.LEAK_KEYS}
                                for i, rows in per.items()}
        out[k] = d
        step(f"Equilibrium, concept ({k})")
    return out, comp


def run_world(world: World, P: Params | None = None, issues=None, progress=None, cancel=lambda: False):
    P = P or Params()
    total = 3; done = [0]
    def step(label):
        done[0] += 1
        if progress:
            progress(min(1.0, done[0] / total), label)
    res, comp = _solve_world(world, P, cancel=cancel, step=step)
    mm = {c: mismatch_matrix(world, c) for c in CONFIGS}
    step("Mismatch matrix")
    return dict(version=VERSION, kind="world", generated=datetime.datetime.now().isoformat(timespec="seconds"),
                world=world.to_dict(), issues=issues or [], unverified=world.unverified(),
                illustrative=bool(world.settings.illustrative), params=P.to_dict(),
                codes=world.codes, names=[j.name for j in world.jurisdictions], kinds=[j.kind for j in world.jurisdictions],
                rules=[j.liability_rule for j in world.jurisdictions], rule_labels=LIABILITY,
                fixed=[j.rate_mode == "fixed" for j in world.jurisdictions],
                truncated=_f(comp.truncated), concepts=res, mismatch=mm, personal=personal_mismatches(world))


def run_counterfactual(world: World, code: str, rule: str, P: Params | None = None, progress=None, cancel=lambda: False):
    P = P or Params()
    cw = world.with_rule(code, rule)
    n = [0]
    def step(label):
        n[0] += 1
        if progress:
            progress(min(1.0, n[0] / 2), label)
    res, comp = _solve_world(cw, P, leak=False, cancel=cancel, step=step)
    j0 = world.jurisdictions[world.index(code)]
    from_rule = f"intermediary:{j0.intermediary_test}" if j0.liability_rule == "intermediary" else j0.liability_rule
    return dict(kind="counterfactual", code=code, rule=rule, from_rule=from_rule,
                generated=datetime.datetime.now().isoformat(timespec="seconds"), concepts=res,
                mismatch={c: mismatch_matrix(cw, c) for c in CONFIGS})
