"""Parameters (model specification v0.2 s 8, revised by build plan s 10)."""
from __future__ import annotations
from dataclasses import dataclass, field, asdict, fields
import numpy as np

VERSION = "0.4"
CONFIGS = ("custodial", "single", "multisig")
RULES = ("owner_residence", "intermediary", "control", "enclosure",
         "registration", "validation", "non_assignment")
RULE_LABELS = {
    "owner_residence": "Owner-residence", "intermediary": "Intermediary location",
    "control": "Control", "enclosure": "Infrastructural enclosure",
    "registration": "Registration", "validation": "Place of validation",
    "non_assignment": "Universal non-assignment",
    "X_gap": "Matched rule X (exclusive, not exhaustive)",
    "Y_overlap": "Matched rule Y (exhaustive, not exclusive)",
}
SHORT = {"owner_residence": "Owner-residence", "intermediary": "Intermediary", "control": "Control",
         "enclosure": "Enclosure", "registration": "Registration", "validation": "Validation",
         "non_assignment": "Non-assignment", "X_gap": "Rule X", "Y_overlap": "Rule Y"}
PREDICATE = {"owner_residence": "personal", "intermediary": "institutional", "control": "movable",
             "enclosure": "movable", "registration": "institutional", "validation": "elective (chain choice)",
             "non_assignment": "none", "X_gap": "matched", "Y_overlap": "matched"}


def default_mobility():
    return {
        ("intermediary", "custodial"): 0.40,
        ("control", "custodial"): 0.40, ("control", "single"): 0.90, ("control", "multisig"): 0.90,
        ("enclosure", "custodial"): 0.40, ("enclosure", "single"): 0.90, ("enclosure", "multisig"): 0.90,
        ("registration", "custodial"): 0.45, ("registration", "single"): 0.45, ("registration", "multisig"): 0.45,
        ("validation", "custodial"): 0.30, ("validation", "single"): 0.30, ("validation", "multisig"): 0.30,
        # matched pair for Proposition 3: custodians as intermediary; keys placed abroad as under control
        ("X_gap", "custodial"): 0.40, ("X_gap", "single"): 0.90, ("X_gap", "multisig"): 0.90,
        ("Y_overlap", "custodial"): 0.40, ("Y_overlap", "single"): 0.90, ("Y_overlap", "multisig"): 0.90,
    }


@dataclass
class Params:
    N: int = 6
    seed: int = 11
    theta0: float = 3.0
    beta: float = 25.0             # calibrated so the network is a material share of sensitivity (plan s 10, A2)
    alpha: float = 0.6
    kappa: float = 200.0
    kappa_relief: float = 20.0
    tau_max: float = 1.0
    home_bias: float = 0.7
    rho: float = 0.75
    phi: float = 0.1
    dual_residence: float = 0.15
    exit_weight: float = 0.6
    sigma: float = 1.0             # stickiness of economic location (random location preference, mixed logit)
    draws: int = 16                # simulation draws for the mixed logit
    mobility_scale: float = 1.0
    obs_custodial: float = 0.95
    obs_self: float = 0.35
    enforcement_self: float = 0.6  # observability of self-hosted holdings when observation is raised
    enforcement: bool = False
    w_custodial: float = 0.55
    w_single: float = 0.30
    w_multisig: float = 0.15
    immobile: float = 0.02

    # ---- derived ---------------------------------------------------------------
    @property
    def w(self):
        return {"custodial": self.w_custodial, "single": self.w_single, "multisig": self.w_multisig}

    @property
    def obs(self):
        o_self = self.enforcement_self if self.enforcement else self.obs_self
        return {"custodial": self.obs_custodial, "single": o_self, "multisig": o_self}

    @property
    def mobility(self):
        return {k: v * self.mobility_scale for k, v in default_mobility().items()}

    def jurisdictions(self):
        rng = np.random.default_rng(self.seed)
        a = rng.uniform(0.6, 1.6, self.N)
        e = rng.uniform(0.3, 1.7, self.N); e /= e.mean()
        g = rng.uniform(0.3, 1.7, self.N); g /= g.mean()
        v = rng.dirichlet(np.full(self.N, 0.4)) * self.N      # validation geography of chains (mean 1)
        return a, e, g, v

    def location_draws(self):
        rng = np.random.default_rng(self.seed + 7919)
        if self.sigma <= 0 or self.draws <= 1:
            return np.zeros((1, self.N))
        z = rng.standard_normal((self.draws // 2, self.N))
        return np.vstack([z, -z]) * self.sigma                  # antithetic draws

    def replace(self, **kw):
        d = self.to_dict(); d.update(kw)
        return Params.from_dict(d)

    def to_dict(self):
        return asdict(self)

    @staticmethod
    def from_dict(d):
        names = {f.name: f.type for f in fields(Params)}
        out = {}
        for k, v in d.items():
            if k in names:
                cur = getattr(Params, k, None)
                if isinstance(cur, bool):
                    out[k] = bool(v)
                elif isinstance(cur, int) and not isinstance(cur, bool):
                    out[k] = int(v)
                elif isinstance(cur, float):
                    out[k] = float(v)
                else:
                    out[k] = v
        return Params(**out)


PARAM_SPEC = [  # name, label, min, max, step, group
    ("theta0", "θ₀ baseline semi-elasticity", 2.5, 6.0, 0.1, "Competition"),
    ("beta", "β weight of escape capacity", 0.0, 60.0, 1.0, "Competition"),
    ("alpha", "α per-step discount", 0.1, 0.95, 0.05, "Competition"),
    ("sigma", "σ stickiness of economic location", 0.0, 3.0, 0.1, "Holders"),
    ("mobility_scale", "Predicate mobility (× default)", 0.0, 2.0, 0.05, "Holders"),
    ("exit_weight", "Attractiveness of leaving the asset class", 0.1, 2.0, 0.05, "Holders"),
    ("home_bias", "Home bias of transactions", 0.3, 0.95, 0.05, "Holders"),
    ("rho", "ρ treaty relief on overlap", 0.0, 1.0, 0.05, "Failure modes"),
    ("phi", "φ residence backstop on gap", 0.0, 1.0, 0.05, "Failure modes"),
    ("dual_residence", "Dual residence share", 0.0, 0.5, 0.01, "Failure modes"),
    ("obs_custodial", "Observability: custodial", 0.3, 1.0, 0.01, "Observation"),
    ("obs_self", "Observability: self-hosted", 0.0, 1.0, 0.01, "Observation"),
    ("enforcement_self", "Self-hosted, observation raised", 0.0, 1.0, 0.01, "Observation"),
    ("w_custodial", "Weight: custodial", 0.05, 1.0, 0.05, "Configurations"),
    ("w_single", "Weight: self-hosted single key", 0.05, 1.0, 0.05, "Configurations"),
    ("w_multisig", "Weight: multi-signature", 0.0, 1.0, 0.05, "Configurations"),
    ("kappa_relief", "Smoothing of credit relief", 5.0, 80.0, 1.0, "Numerics"),
    ("draws", "Simulation draws", 2, 200, 2, "Numerics"),
    ("seed", "World seed", 1, 9999, 1, "Numerics"),
]
