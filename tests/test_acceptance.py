"""Acceptance tests for v0.2 (specification s 9; build plan ss 9 and 10).
Run: PYTHONPATH=. python3 tests/test_acceptance.py
"""
import numpy as np
from jaf.params import Params, RULES
from jaf.rules import Compiled
from jaf.equilibrium import solve
from jaf.network import resolvent, round_trip
from jaf import experiments as X

results = []
def check(name, cond, detail=""):
    results.append(bool(cond)); print(("PASS " if cond else "FAIL ") + name + (f"  [{detail}]" if detail else ""))

rng = np.random.default_rng(0)
F = rng.random((5, 5)); np.fill_diagonal(F, 0); D = rng.random(5) * 3
Pm, M = resolvent(F, D, 0.6); S = np.eye(5); T = np.eye(5)
for _ in range(400): T = T @ (0.6 * Pm); S = S + T
check("1 resolvent = power series", np.abs(S - M).max() < 1e-12)

full = dict(obs_custodial=1.0, obs_self=1.0, sigma=0.0)
c = Compiled("owner_residence", Params(dual_residence=0.0, **full)); e = solve(c, "a", tol=1e-8)
Sj = np.bincount(c.j, weights=e["s"], minlength=6)
err = np.abs(e["tau"] - 1 / (e["theta"] * (1 - Sj))).max()
check("2 partition reproduces tau = 1/[theta(1 - s)] (plain logit)", err < 1e-4, f"{err:.1e}")

c = Compiled("enclosure", Params()); sols = [solve(c, "a", tau0=rng.uniform(0.1, 0.9, 6))["tau"] for _ in range(4)]
spread = np.ptp(np.array(sols), axis=0).max()
check("3 equilibrium unique across starts", spread < 1e-3, f"{spread:.1e}")

P = Params()
res = {r: dict(zip(("comp", "a", "b"), X.run_rule(r, P))) for r in RULES}
check("4 all rules converge under both concepts", all(res[r]["a"]["converged"] and res[r]["b"]["converged"] for r in RULES))
check("5 only non-assignment is a corner", [r for r in RULES if res[r]["a"]["corner"]] == ["non_assignment"])
rk = X.ranking(res); ok = True
for (r1, r2), v in rk.items():
    if v in (">", "<"):
        ok &= np.sign(res[r1]["a"]["effective"] - res[r2]["a"]["effective"]) == np.sign(res[r1]["b"]["effective"] - res[r2]["b"]["effective"])
check("6 ranking uses effective rates and requires agreement", ok)

L = {r: X.leakage(res[r]["comp"], res[r]["a"]) for r in RULES if X.usable(res[r]["a"])}
check("7 leakage decomposition sums to one", all(abs(sum(l[k] for k in X.LEAK_KEYS) - 1) < 1e-6 for l in L.values()))
o = L["owner_residence"]
check("8 owner-residence: no round-tripping, conduit switching only via dual residents (<1%), exit separated", o["round_trip"] < 1e-6 and o["conduit_switching"] < 0.01 and o["exit"] > 0.1,
      f"exit {o['exit']:.2f}")
check("9 intermediary location leaks into the gap", L["intermediary"]["to_gap"] > 0.2, f"{L['intermediary']['to_gap']:.2f}")

ex = solve(Compiled("X_gap", P), "a"); ey = solve(Compiled("Y_overlap", P), "a")
check("10 matched pair: X has gap, no overlap; Y the reverse", ex["failure"]["overlap"] == 0 and ey["failure"]["gap"] == 0
      and ex["failure"]["gap"] > 0 and ey["failure"]["overlap"] > 0)
z0 = round_trip(resolvent(np.ones((4, 4)) - np.eye(4), np.full(4, 10.0), 0.6)[1])[0]
F2 = np.ones((4, 4)) - np.eye(4); F2[0, 1] += 3; F2[1, 0] += 3
check("11 round trip raises Z", round_trip(resolvent(F2, np.full(4, 10.0), 0.6)[1])[0] > z0)
ei = res["intermediary"]["a"]; fi = ei["failure"]
ident = abs(ei["effective"] * ei["Q"].sum() + fi["backstop"] - ei["revenue"].sum())
check("12 effective rate excludes gap backstop; yield counts the gap", ident < 1e-9 and ei["revenue_per_base"] < ei["effective"]
      and abs(res["control"]["a"]["revenue_per_base"] - res["control"]["a"]["effective"]) < 1e-9, f"identity {ident:.1e}")

# ---- 0.3: mixed regimes (build plan s 12.2) -------------------------------------------
from jaf.mixed import MixedCompiled
from jaf.synthetic import uniform_world
from jaf.world import World, Jurisdiction, Link, Settings, illustrative_world, mismatch_matrix, claimants
from jaf.template import write_template, read_template
import io
from openpyxl import load_workbook

dev = 0.0
for r in ("owner_residence", "intermediary", "control", "enclosure", "registration"):
    w_, pw, a_ = uniform_world(r, P)
    m_ = MixedCompiled(w_, P, placement_weight=pw, holder_base=a_)
    for k in "ab":
        dev = max(dev, np.abs(solve(Compiled(r, P), k)["tau"] - solve(m_, k)["tau"]).max())
check("13 mixed engine with one common rule reproduces 0.2 equilibria", dev < 1e-6, f"max dev {dev:.1e}")

J3 = [Jurisdiction("X", "X", liability_rule="intermediary", rate_mode="fixed", effective_rate=0.3, info_exchange_from=2020, visibility_domestic_custodial=1.0, visibility_self_hosted=1.0),
      Jurisdiction("Y", "Y", liability_rule="residence", rate_mode="fixed", effective_rate=0.2, info_exchange_from=2020, visibility_domestic_custodial=1.0, visibility_self_hosted=1.0),
      Jurisdiction("Z", "Z", liability_rule="residence_citizenship", rate_mode="fixed", effective_rate=0.25, info_exchange_from=2020, visibility_domestic_custodial=1.0, visibility_self_hosted=1.0)]
w3 = World(J3, [Link("Y", "Z", "citizenship", 0.5)], Settings(scenario_year=2027, visibility_exchanged=1.0, treaty_relief=0.5))
cl = claimants(w3, 1, "custodial", 0, [(2, "citizenship")])
m3 = MixedCompiled(w3); e3 = solve(m3, "a")
s3 = e3["s"]; total = m3.revenue(e3["tau"], s3).sum()
b, pr, se, gp = m3.entry_terms(e3["tau"]); mw = s3[m3.ek] * m3.ew
check("14 three claimants: order placement, residence, citizenship; revenue adds up",
      [k for k, _ in cl] == [0, 1, 2] and abs(total - (mw * (pr + se + gp)).sum()) < 1e-12 and 1 + m3.smask.sum(1).max() == 3)

wi = illustrative_world(); mi = MixedCompiled(wi); ei = solve(mi, "b")
fx = mi.fixed
check("15 fixed-rate states keep their coded rate; competitive states converge",
      np.allclose(ei["tau"][fx], mi.fixed_tau[fx]) and ei["converged"] and not np.allclose(ei["tau"][~fx], 0.3))

mmd = mismatch_matrix(wi, "custodial"); colix = {(c["base"], c["seat"]): n for n, c in enumerate(mmd["cols"])}
mm = [[row[colix[(code, code)]] for code in wi.codes] for row in mmd["cells"]]   # co-located exchange types
iC, iA, iE, iH1 = (wi.index(c) for c in ("C", "A", "E", "H1"))
check("16 mismatch matrix matches hand-worked cells",
      mm[iC][iA]["n"] == 0 and mm[iA][iC]["claimants"] == ["C", "A"] and mm[iH1][iE]["claimants"] == ["E"] and mm[iA][iA]["claimants"] == ["A"])

b1 = write_template(kind="illustrative"); w1, iss1 = read_template(b1)
check("17 template round trip reproduces the illustrative world", w1 is not None and w1.to_dict() == wi.to_dict() and not iss1)

wb = load_workbook(io.BytesIO(b1)); sh = wb["Jurisdictions"]
H18 = [str(c.value).rstrip(" *") for c in sh[1]]; C18 = lambda name: H18.index(name) + 1   # columns by header, not position
sh.cell(4, C18("Code")).value = "A"                                   # duplicate code
sh.cell(5, C18("Liability rule")).value = "nonsense_rule"             # bad liability rule
sh.cell(6, C18("Effective rate on returns (0 to 1)")).value = None    # fixed rate missing (row 6 is D, fixed); cell(r, c, None) would not clear
sh.cell(7, C18("Verified")).value = "no"; sh.cell(7, C18("Source (OSCOLA)")).value = None   # unverified, no source
bio = io.BytesIO(); wb.save(bio); w2, iss2 = read_template(bio.getvalue())
msgs = " | ".join(i["message"] for i in iss2)
check("18 validation catches duplicates, bad values and missing rates; flags unverified and unsourced rows",
      w2 is None and "more than once" in msgs and "Liability rule" in msgs and "Effective rate" in msgs and "Not yet verified" in msgs and "No source" in msgs)

V_on = wi.custodial_visibility(); w_off = World.from_dict(wi.to_dict()); w_off.settings.scenario_year = 2000
V_off = w_off.custodial_visibility()
ia, ie = wi.index("A"), wi.index("E")
check("19 exchange of information raises visibility of foreign exchange holdings",
      V_on[ia, ie] == wi.settings.visibility_exchanged and V_off[ia, ie] == wi.jurisdictions[ia].visibility_self_hosted and V_on[ia, ia] == V_off[ia, ia])


# ---- 0.4: legal seat against operational base; treaty relief by pair (build plan s 13.2) ----
from jaf.world import Treaty
def two(test_x, test_y):
    J = [Jurisdiction("X", "X", liability_rule="intermediary", intermediary_test=test_x),
         Jurisdiction("Y", "Y", liability_rule="intermediary", intermediary_test=test_y, offshore_incorporation_in="X", offshore_incorporation_share=0.5),
         Jurisdiction("Z", "Z", liability_rule="none")]
    return World(J)
wo, wg = two("seat", "base"), two("base", "seat")
z = 2   # holder resident in Z (claims nothing itself); exchange based in Y (index 1), incorporated in X (index 0)
co = [wo.codes[k] for k, _ in claimants(wo, z, "custodial", 1, [], seat=0)]
cg = [wg.codes[k] for k, _ in claimants(wg, z, "custodial", 1, [], seat=0)]
same = [wo.codes[k] for k, _ in claimants(wo, z, "custodial", 1, [], seat=1)]
check("20 seat and base: seat-testing seat state plus base-testing base state overlap; the reverse is a gap",
      co == ["Y", "X"] and cg == [] and same == ["Y"], f"overlap {co}, gap {cg}, co-located {same}")

def relief_world(r):
    J = [Jurisdiction("A", "A", liability_rule="intermediary", intermediary_test="base", rate_mode="fixed", effective_rate=0.3,
                      info_exchange_from=2020, visibility_domestic_custodial=1.0, visibility_self_hosted=1.0),
         Jurisdiction("B", "B", liability_rule="residence", rate_mode="fixed", effective_rate=0.2,
                      info_exchange_from=2020, visibility_domestic_custodial=1.0, visibility_self_hosted=1.0)]
    return World(J, [], Settings(scenario_year=2027, visibility_exchanged=1.0, treaty_relief=0.5), [Treaty("B", "A", r, False)])
res21 = {}
for r in (1.0, 0.0):
    mw_ = MixedCompiled(relief_world(r)); ew_ = solve(mw_, "a")
    res21[r] = ew_["failure"]["unrelieved"] / max(1e-12, ew_["failure"]["overlap"])
kap = Params().kappa_relief
check("21 pair relief: full relief leaves only the smoothing residue; none leaves the full second tax",
      res21[1.0] < np.log1p(np.exp(-0.1 * kap)) / kap + 1e-9 and abs(res21[0.0] - 0.2) < 1e-9, f"full {res21[1.0]:.4f}, none {res21[0.0]:.4f}")

wb = load_workbook(io.BytesIO(write_template(kind="illustrative"))); sh = wb["Jurisdictions"]
hdr = [str(c.value).rstrip(" *") for c in sh[1]]
col = lambda name: hdr.index(name) + 1
sh.cell(3, col("Exchanges here incorporated offshore in (code)")).value = "QQ"          # unknown code
sh.cell(5, col("Share incorporated offshore (0 to 1)")).value = None                   # C: code given, share missing
tw = wb["Treaties"]; tw.cell(3, 3).value = 1.7                                          # relief out of range
bio = io.BytesIO(); wb.save(bio); w22, iss22 = read_template(bio.getvalue())
m22 = " | ".join(i["message"] for i in iss22)
check("22 validation catches unknown offshore code, missing share and relief out of range",
      w22 is None and "'QQ' is not a code" in m22 and "is needed when an offshore place" in m22 and "Relief must be between 0 and 1" in m22)


wb23 = load_workbook(io.BytesIO(write_template(kind="illustrative"))); sh23 = wb23["Jurisdictions"]
for name in ("Share incorporated offshore (0 to 1)", "Exchanges here incorporated offshore in (code)", "Intermediary located by"):
    hdr23 = [str(c.value).rstrip(" *") for c in sh23[1]]; sh23.delete_cols(hdr23.index(name) + 1)
del wb23["Treaties"]
bio = io.BytesIO(); wb23.save(bio); w23, iss23 = read_template(bio.getvalue())
check("23 a template from 0.3 (no new columns, no Treaties sheet) loads, with warnings and defaults",
      w23 is not None and not w23.treaties and all(i["level"] == "warning" for i in iss23)
      and any("Assumed to locate intermediaries by legal seat" in i["message"] for i in iss23))

print(f"\n{sum(results)}/{len(results)} passed")
raise SystemExit(len(results) - sum(results))
