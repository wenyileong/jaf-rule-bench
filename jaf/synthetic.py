"""Bridge between the 0.2 synthetic world and the mixed engine (used by acceptance test 13)."""
from __future__ import annotations
from .params import Params
from .rules import location_weight
from .world import World, Jurisdiction, Link, Settings

RULE_MAP = {"owner_residence": "residence", "intermediary": "intermediary", "control": "control",
            "enclosure": "enclosure", "registration": "registration", "validation": "validation",
            "non_assignment": "none"}


def uniform_world(rule: str, P: Params):
    """All N synthetic jurisdictions apply the same 0.2 rule; returns (world, placement_weight, holder_base)."""
    a, e, g, v = P.jurisdictions()
    J = [Jurisdiction(code=f"J{i + 1}", name=f"J{i + 1}", holder_base=float(a[i]), exchange_presence=float(e[i]),
                      liability_rule=RULE_MAP[rule], visibility_domestic_custodial=P.obs_custodial,
                      visibility_self_hosted=P.obs["single"], info_exchange_from=2000, residence_topup=P.phi,
                      rate_mode="competitive", verified=True, source="synthetic")
         for i in range(P.N)]
    links = []
    if rule == "owner_residence" and P.dual_residence > 0:
        links = [Link(f"J{i + 1}", f"J{(i + 1) % P.N + 1}", "dual_residence", P.dual_residence, "synthetic", True)
                 for i in range(P.N)]
    w = World(J, links, Settings(scenario_year=2027, visibility_exchanged=P.obs_custodial, treaty_relief=P.rho))
    pw = lambda j, c, p: location_weight(rule, j, c, p, P, e, g, v)
    return w, pw, a
