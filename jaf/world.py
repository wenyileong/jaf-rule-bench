# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Wen Yi LEONG
"""A coded world of named jurisdictions with their own assignment rules (build plan s 12).

Each jurisdiction carries three layers: liability (which connecting factor it taxes on),
collection (self-assessment or withholding by domestic intermediaries) and observation
(what its authority can see, including exchange of information under CARF or DAC8).
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
import numpy as np

LIABILITY = {
    "residence": "Residence of the holder",
    "residence_citizenship": "Residence, plus citizens resident abroad",
    "intermediary": "Location of the intermediary (exchange-held holdings only; located by the state's own test)",
    "control": "Location of key control",
    "enclosure": "Location of the technical infrastructure",
    "registration": "Place of registration",
    "validation": "Place of validation",
    "none": "No assignment (this asset class is not taxed)",
}
PLACEMENT_RULES = ("intermediary", "control", "enclosure", "registration", "validation")
PERSONAL_RULES = ("residence", "residence_citizenship")
COLLECTION = {"self_assessment": "Holder self-assesses", "domestic_withholding": "Domestic intermediaries withhold or collect"}
KINDS = ("economy", "hub", "rest_of_world")
RATE_MODES = ("fixed", "competitive")
LINK_TYPES = ("dual_residence", "citizenship")
INTERMEDIARY_TESTS = {"seat": "Legal seat (incorporation or licence)", "base": "Operational base (management and operations)"}


@dataclass
class Jurisdiction:
    code: str
    name: str
    kind: str = "economy"
    holder_base: float = 1.0                 # relative size of the holder base resident here
    exchange_presence: float = 1.0           # relative attractiveness as a place to hold with an exchange
    liability_rule: str = "residence"
    collection: str = "self_assessment"
    domestic_exchanges_permitted: bool = True
    visibility_domestic_custodial: float = 0.95
    visibility_self_hosted: float = 0.35
    info_exchange_from: int | None = None    # first year of automatic exchange (CARF or DAC8); None = never
    residence_topup: float = 0.0             # share of own rate applied to residents' unassigned holdings
    rate_mode: str = "competitive"
    effective_rate: float | None = None      # effective rate on returns from holdings, used when rate_mode is fixed
    in_force_from: str = ""
    in_force_until: str = ""
    source: str = ""
    verified: bool = False
    notes: str = ""
    # 0.4 (build plan s 13): appended so positional construction stays valid
    intermediary_test: str = "seat"          # how this state locates an intermediary, if it taxes by intermediary location
    offshore_incorporation_in: str = ""      # code of the typical offshore place of incorporation of exchanges operating here
    offshore_incorporation_share: float = 0.0


@dataclass
class Treaty:
    """Relief granted by `relieving` for tax levied by `taxing` on the same holding (build plan s 13.1, issue 7)."""
    relieving: str
    taxing: str
    relief: float = 0.75
    both_directions: bool = True
    source: str = ""
    verified: bool = False


@dataclass
class Link:
    from_code: str                           # holders resident here ...
    to_code: str                             # ... also connected to this jurisdiction
    link_type: str = "dual_residence"
    share: float = 0.0
    source: str = ""
    verified: bool = False


@dataclass
class Settings:
    scenario_year: int = 2027
    visibility_exchanged: float = 0.9        # quality of information received through automatic exchange
    mobility_custodial: float = 0.40         # ease of holding with a foreign exchange (scaled by exchange presence)
    mobility_self_hosted: float = 0.90       # ease of placing self-hosted keys or infrastructure abroad
    treaty_relief: float = 0.75              # rho
    label: str = "Coded world"
    illustrative: bool = False


@dataclass
class World:
    jurisdictions: list[Jurisdiction]
    links: list[Link] = field(default_factory=list)
    settings: Settings = field(default_factory=Settings)
    treaties: list[Treaty] = field(default_factory=list)

    # ---- convenience ---------------------------------------------------------------
    @property
    def N(self):
        return len(self.jurisdictions)

    @property
    def codes(self):
        return [j.code for j in self.jurisdictions]

    def index(self, code):
        return self.codes.index(code)

    def vec(self, attr, cast=float):
        return np.array([cast(getattr(j, attr)) for j in self.jurisdictions])

    def exchanging(self):
        """Boolean vector: automatic exchange of information active in the scenario year."""
        y = self.settings.scenario_year
        return np.array([j.info_exchange_from is not None and j.info_exchange_from <= y for j in self.jurisdictions])

    def custodial_visibility(self):
        """V[k, p]: share of custodial holdings at an exchange in p that authority k can see."""
        N, ex = self.N, self.exchanging()
        V = np.zeros((N, N))
        for k, jk in enumerate(self.jurisdictions):
            dom = 1.0 if jk.collection == "domestic_withholding" else jk.visibility_domestic_custodial
            for p in range(N):
                if p == k:
                    V[k, p] = dom
                elif ex[k] and ex[p]:
                    V[k, p] = self.settings.visibility_exchanged
                else:
                    V[k, p] = jk.visibility_self_hosted          # only what the holder self-reports
        return V

    def relief_matrix(self):
        """R[q, p]: share of the double tax that relieving state q relieves for tax levied first by p."""
        N = self.N
        R = np.full((N, N), float(self.settings.treaty_relief))
        for t in self.treaties:
            q, p = self.index(t.relieving), self.index(t.taxing)
            R[q, p] = t.relief
            if t.both_directions:
                R[p, q] = t.relief
        return R

    def exchange_types(self):
        """Exchange types by operational base b: list of (b, seat s, share of b's exchanges with that seat)."""
        out = []
        for b, jb in enumerate(self.jurisdictions):
            h, sh = jb.offshore_incorporation_in, float(jb.offshore_incorporation_share or 0.0)
            if h and h != jb.code and sh > 0:
                out.append((b, b, 1.0 - sh))
                out.append((b, self.index(h), sh))
            else:
                out.append((b, b, 1.0))
        return [t for t in out if t[2] > 0]

    def custodial_visibility3(self):
        """V[k, b, s]: share of holdings at an exchange based in b and seated in s that authority k can see."""
        N, ex = self.N, self.exchanging()
        V = np.zeros((N, N, N))
        for k, jk in enumerate(self.jurisdictions):
            dom = 1.0 if jk.collection == "domestic_withholding" else jk.visibility_domestic_custodial
            for b in range(N):
                for s_ in range(N):
                    if k in (b, s_):
                        V[k, b, s_] = dom
                    elif ex[k] and (ex[b] or ex[s_]):
                        V[k, b, s_] = self.settings.visibility_exchanged
                    else:
                        V[k, b, s_] = jk.visibility_self_hosted
        return V

    def personal_subtypes(self, j):
        """Holder subtypes resident in j: list of (weight, [(k, link_type), ...])."""
        own = [l for l in self.links if l.from_code == self.codes[j] and l.share > 0]
        rest = max(0.0, 1.0 - sum(l.share for l in own))
        out = [(rest, [])]
        for l in own:
            out.append((l.share, [(self.index(l.to_code), l.link_type)]))
        return out

    def unverified(self):
        rows = [j.code for j in self.jurisdictions if not j.verified]
        rows += [f"{l.from_code}->{l.to_code}" for l in self.links if not l.verified]
        rows += [f"relief {t.relieving}/{t.taxing}" for t in self.treaties if not t.verified]
        return rows

    # ---- serialisation -----------------------------------------------------------------
    def to_dict(self):
        return dict(jurisdictions=[asdict(j) for j in self.jurisdictions], links=[asdict(l) for l in self.links],
                    settings=asdict(self.settings), treaties=[asdict(t) for t in self.treaties])

    @staticmethod
    def from_dict(d):
        return World([Jurisdiction(**j) for j in d["jurisdictions"]], [Link(**l) for l in d.get("links", [])],
                     Settings(**d.get("settings", {})), [Treaty(**t) for t in d.get("treaties", [])])

    def with_rule(self, code, rule):
        """Copy of the world with one jurisdiction's liability rule changed (counterfactual)."""
        w = World.from_dict(self.to_dict())
        j = w.jurisdictions[w.index(code)]
        if rule.startswith("intermediary:"):          # intermediary with a stated location test (seat or base)
            j.liability_rule, j.intermediary_test = "intermediary", rule.split(":", 1)[1]
        else:
            j.liability_rule = rule
        return w


# ---- claimant logic (co-location assumption, build plan s 12.1, issue 1) ---------------
def claimants(world: World, j: int, c: str, p: int, personal: list, seat: int | None = None):
    """Ordered claimants for a holding of a holder resident in j, configuration c, based (housed) in p,
    with legal seat `seat` (defaults to p; differs only for exchange-held holdings, build plan s 13).

    Relief order (s 12.1 issue 2; s 13.1 issue 4): base-located claims, then seat-located claims, then a
    multi-signature co-signer at the holder's residence, then residence (own, then dual), then citizenship.
    Each entry is (k, basis) with basis in {"base", "seat", "cosigner", "residence", "citizenship"}.
    """
    s_ = p if seat is None else seat
    J = world.jurisdictions
    rules = [x.liability_rule for x in J]
    out = []
    def add(k, basis):
        if all(k != q for q, _ in out):
            out.append((k, basis))
    # base-located factors: infrastructure, key control, validation; intermediary if the base state tests by base
    rb = rules[p]
    if rb in ("control", "enclosure", "validation"):
        add(p, "base")
    elif rb == "intermediary" and c == "custodial" and (J[p].intermediary_test == "base" or s_ == p):
        add(p, "base")
    # seat-located factors: registration; intermediary if the seat state tests by seat
    rs = rules[s_]
    if rs == "registration":
        add(s_, "seat")
    elif rs == "intermediary" and c == "custodial" and (J[s_].intermediary_test == "seat" or s_ == p):
        add(s_, "seat")
    if c == "multisig" and p != j and rules[j] == "control":
        add(j, "cosigner")
    if rules[j] in PERSONAL_RULES:
        add(j, "residence")
    for k_, t in personal:
        if t == "dual_residence" and rules[k_] in PERSONAL_RULES:
            add(k_, "residence")
    for k_, t in personal:
        if t == "citizenship" and rules[k_] == "residence_citizenship":
            add(k_, "citizenship")
    return out


def mismatch_matrix(world: World, config: str):
    """Claimants of a plain resident (no personal links) for each (residence, column).

    Columns: for exchange-held holdings, the exchange types that exist (base, seat); otherwise each state
    as the place the holding is kept. Returns dict(cols=[{base, seat, label}], cells=[[...]]).
    """
    N, codes = world.N, world.codes
    if config == "custodial":
        cols = [(b, s_) for b, s_, _ in world.exchange_types()]
    else:
        cols = [(p, p) for p in range(N)]
    banned = [not x.domestic_exchanges_permitted for x in world.jurisdictions]
    out_cols = [dict(base=codes[b], seat=codes[s_], label=codes[b] if b == s_ else f"{codes[b]}/{codes[s_]}",
                     prohibited=bool(config == "custodial" and (banned[b] or banned[s_]))) for b, s_ in cols]
    cells = []
    for j in range(N):
        row = []
        for b, s_ in cols:
            cl = claimants(world, j, config, b, [], seat=s_)
            row.append(dict(n=len(cl), claimants=[codes[k] for k, _ in cl], basis=[x for _, x in cl]))
        cells.append(row)
    return dict(cols=out_cols, cells=cells)


def personal_mismatches(world: World, config: str = "custodial"):
    """Claims arising from personal links (dual residence, citizenship) for holdings kept at home."""
    out = []
    for l in world.links:
        j, k = world.index(l.from_code), world.index(l.to_code)
        cl = claimants(world, j, config, j, [(k, l.link_type)])
        out.append(dict(from_code=l.from_code, to_code=l.to_code, link_type=l.link_type, share=l.share,
                        claimants=[world.codes[q] for q, _ in cl], basis=[b for _, b in cl]))
    return out


# ---- example worlds ------------------------------------------------------------------
def illustrative_world():
    """Hypothetical states for demonstration. None of these rows describes any real country's law."""
    src = "Illustrative only: hypothetical state, not real law"
    J = [
        Jurisdiction("A", "Country A", "economy", 1.6, 1.0, "residence", "self_assessment", True, 0.9, 0.3, 2027, 0.0, "fixed", 0.24, source=src, verified=True,
                     notes="Residence-based; joins automatic exchange in the first wave; many of its exchanges are incorporated in Hub Two",
                     offshore_incorporation_in="H2", offshore_incorporation_share=0.4),
        Jurisdiction("B", "Country B", "economy", 1.8, 1.2, "residence_citizenship", "self_assessment", True, 0.9, 0.35, 2029, 0.0, "fixed", 0.30, source=src, verified=True,
                     notes="Taxes its citizens living abroad; joins exchange late"),
        Jurisdiction("C", "Country C", "economy", 1.2, 0.8, "intermediary", "domestic_withholding", True, 1.0, 0.2, 2027, 0.5, "competitive", None, source=src, verified=True,
                     notes="Taxes holdings at exchanges it treats as its own, by operational base; collected by withholding; top-up on residents' untaxed holdings",
                     intermediary_test="base", offshore_incorporation_in="H2", offshore_incorporation_share=0.3),
        Jurisdiction("D", "Country D", "economy", 1.4, 0.0, "residence", "self_assessment", False, 0.5, 0.2, None, 0.0, "fixed", 0.20, source=src, verified=True,
                     notes="Domestic exchanges prohibited"),
        Jurisdiction("E", "Country E", "economy", 0.9, 0.9, "registration", "self_assessment", True, 0.9, 0.35, 2027, 0.0, "competitive", None, source=src, verified=True,
                     notes="Taxes holdings registered with its service providers"),
        Jurisdiction("H1", "Hub One", "hub", 0.2, 2.5, "none", "self_assessment", True, 0.9, 0.3, 2028, 0.0, "fixed", 0.0, source=src, verified=True,
                     notes="No tax on the asset class; large exchange presence; some exchanges incorporated in Hub Two",
                     offshore_incorporation_in="H2", offshore_incorporation_share=0.5),
        Jurisdiction("H2", "Hub Two", "hub", 0.15, 2.0, "registration", "self_assessment", True, 0.9, 0.3, None, 0.0, "fixed", 0.02, source=src, verified=True,
                     notes="Low registration-based tax on exchanges incorporated here; outside automatic exchange"),
        Jurisdiction("R", "Rest of world", "rest_of_world", 1.0, 0.6, "residence", "self_assessment", True, 0.7, 0.2, None, 0.0, "fixed", 0.15, source=src, verified=True,
                     notes="Aggregate of all other jurisdictions"),
    ]
    L = [Link("A", "B", "citizenship", 0.04, src, True), Link("C", "A", "dual_residence", 0.05, src, True),
         Link("R", "B", "citizenship", 0.02, src, True)]
    T = [Treaty("A", "C", 1.0, True, src, True), Treaty("B", "H2", 0.0, False, src, True),
         Treaty("D", "E", 0.5, True, src, True)]
    return World(J, L, Settings(scenario_year=2028, label="Illustrative world (hypothetical states)", illustrative=True), T)


CANDIDATE_SAMPLE = [  # names only: every legal field is left for the author to code and verify
    ("US", "United States", "economy"), ("UK", "United Kingdom", "economy"), ("DE", "Germany", "economy"),
    ("JP", "Japan", "economy"), ("KR", "South Korea", "economy"), ("IN", "India", "economy"),
    ("ID", "Indonesia", "economy"), ("CN", "China (mainland)", "economy"), ("BR", "Brazil", "economy"),
    ("SG", "Singapore", "hub"), ("AE", "United Arab Emirates", "hub"), ("HK", "Hong Kong", "hub"),
    ("ROW", "Rest of world", "rest_of_world"),
]
