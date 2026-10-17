# Build Plan: Jurisdictional Assignment Functions Research Tool

Version 0.1 (9 October 2026). Implements `jaf_model_specification.md` v0.2. Section 9 records the logical checks run on this plan and the revisions they forced.

---

## 1. Purpose and scope

The tool runs the six candidate situs rules of *Jurisdictional Assignment Functions* (SSRN 7351160), plus universal non-assignment, through one apparatus on the same synthetic population of holdings. It produces:

- the structural properties of each rule (exhaustiveness, exclusivity, observability);
- equilibrium sustainable rates under two equilibrium concepts, with rankings declared only where both agree;
- tests of Propositions 1 to 3 as restated in the specification;
- visualisations of all of the above;
- a register of dated, hashed predictions.

**Out of scope for the preview:** real data connectors, event studies, change monitoring, and a desktop application. These follow once the synthetic results are stable.

---

## 2. Architecture

```
jaf/
  params.py        parameters, defaults and sweep ranges (spec section 8)
  world.py         synthetic jurisdictions, configurations and option grid
  rules.py         the seven assignment rules as functions of an option
  network.py       flow matrix, P, resolvent M, escape E, round-trip Z
  equilibrium.py   option-level logit, revenue, two equilibrium concepts
  experiments.py   structural table, rate rankings, Propositions 1 to 3
  register.py      prediction freezing with date and SHA-256 hash
  export.py        results to JSON for the interface
tests/             acceptance tests (spec section 9) plus plan tests (section 9 below)
preview/           interactive page reading the exported JSON
```

Python 3.12 with NumPy and SciPy only. No network access at run time. Every run writes a manifest (parameters, code version, seed, hash of outputs), reusing the provenance approach of the A-share build.

---

## 3. Data model

### 3.1 Jurisdictions
N jurisdictions (default 6), each with:
- non-tax attractiveness aⱼ;
- exchange presence eⱼ (weights where custodians locate);
- validation share vⱼ (where computational work securing the ledger sits; concentrated in few states);
- register attractiveness gⱼ.

### 3.2 Options
An option is k = (economic location j, configuration c, predicate location p):
- **configurations**: custodial, self-hosted single key, self-hosted multi-signature;
- **predicate location** p: where the custodian, key or register sits. Holding the predicate away from j carries a configuration-specific friction δ_c (low for keys, moderate for custodians, election cost for registers).

Utility: ln aⱼ + ln w_c + ln δ(j, p, c) − θⱼ · bₖ(τ). A further **exit option** (holding other assets, untaxed by any digital-asset rule) gives every rule a common outside alternative and prevents corner solutions where a rule leaves holders no margin of escape.

### 3.3 Claim sets
Each rule maps an option to a weighted list of claim sets, so that mixtures (for example, the fraction of owners with dual residence) are represented exactly:

| Rule | Custodial | Self-hosted single | Self-hosted multi-signature |
|---|---|---|---|
| Owner-residence | [j], or [j, j₂] for dual residents | same | same |
| Intermediary | [p] | ∅ | ∅ |
| Control | [p] (custodian controls) | [p] | [p, j] (key shares split) |
| Enclosure | [p] | [p] | [p] (threshold infrastructure) |
| Registration | [p] (elected register) | [p] | [p] |
| Validation | [v] with weights vᵥ | same | same |
| Non-assignment | ∅ | ∅ | ∅ |

Each assumption in this table is stated in the interface and can be changed.

### 3.4 Burden and revenue
From specification sections 4 and 5:
- single claim: τᵢ;
- overlap with primary p and secondary s: τₚ + (1 − ρ)τₛ + ρ · max(0, τₛ − τₚ), revenue split as specified;
- gap: φ · τⱼ (residence backstop) collected by j;
- **observability**: each claim's burden and revenue are scaled by the observability o_c of the configuration (Part 9). Custodial holdings are observable through CARF-type reporting; self-hosted holdings much less so. An enforcement switch raises o_c.

---

## 4. Computation

1. **Shares.** Given τ and θ, option shares follow the logit.
2. **Network.** Each unit of base transacts with counterparties in its own economic location with probability h and elsewhere otherwise. Flows are aggregated between **assigned** jurisdictions (primary claimant); gap and exit holdings are not nodes. P is built as in specification section 2; M = (I − αP)⁻¹.
3. **Escape and elasticity.** Eᵢ = Σⱼ Mᵢⱼ softplus(τᵢ − τⱼ); θᵢ = θ₀ + βEᵢ.
4. **Equilibrium.** Each jurisdiction's best response is found numerically (the closed form holds only for partitions). Two concepts:
   - (a) elasticity-consistent: θ held fixed during each best response;
   - (b) full Nash: θ recomputed from E inside the best response, with the network held fixed.
5. **Outer loop.** Rates change shares, shares change the network, the network changes θ. The equilibrium is the joint fixed point, solved by damped iteration with a convergence check on rates and on P.

---

## 5. Experiments

| Experiment | Output | Specification reference |
|---|---|---|
| Structural table | Gap share, overlap share, observability-weighted coverage per rule | ss 3, 4 |
| Rate ranking | Mean sustainable rate per rule under (a) and (b); ranking declared where both agree, otherwise tie | s 1 |
| Proposition 1 | For each pair of rules: distance between induced networks, distance between base distributions, distance between outcomes | s 7 |
| Proposition 2 | Shock to one jurisdiction's rate; return ratio and change in Z per rule; prediction that movable-predicate rules show high return ratios | s 6 |
| Proposition 3 | Matched stylised pair and the intermediary-versus-control comparison over a (φ, ρ) grid; boundary where gap becomes the costlier failure | s 5 |
| Enforcement | Rates and coverage with the observability switch off and on | Part 9 |
| Sensitivity | Rankings across swept parameters; share of sweeps in which each ranking holds | s 8 |

---

## 6. Interface (preview)

One page, five panels, reading exported JSON:
1. **Rules at a glance**: structural table and failure map (gap against overlap).
2. **Sustainable rates**: per-rule rates under both concepts, with tie markers.
3. **Networks**: induced flow network per rule, nodes coloured by sustainable rate, edges by flow.
4. **Leakage signatures (Proposition 2)**: return ratio per rule after a shock.
5. **Gap versus overlap (Proposition 3)**: heatmap over (φ, ρ) with the boundary marked.

Every panel states its assumptions and that outputs are model-implied, not empirical findings.

---

## 7. Phases

| Phase | Deliverable | Gate |
|---|---|---|
| 0 | Specification v0.2 | Done |
| 1 | Core modules and acceptance tests | All spec section 9 tests pass |
| 2 | Experiments and JSON export | Plan tests (section 9) pass |
| 3 | Preview interface | Figures match computed values |
| 4 | Sensitivity sweeps and prediction register | Rankings reported with robustness shares |
| 5 | Real-data connectors for the intermediated segment; event study | Pre-registered predictions frozen first |

The preview covers phases 1 to 3 with a reduced sweep.

---

## 8. Risks

- **Assumption load.** Configuration weights, frictions and claim-set choices drive results. Mitigation: every assumption is a parameter, shown in the interface and swept.
- **Over-reading levels.** Mitigation: rankings and directions only, per Part 7.1.
- **Computation time.** Nested loops (outer network loop, best responses, sweeps). Mitigation: small N for the preview, vectorised shares, caching of M.

---

## 9. Logical checks on this plan

The plan was prototyped (the core modules in section 2) and probed before building the interface. Default world: 6 jurisdictions, 108 options, seed 11.

| # | Check | Result | Revision |
|---|---|---|---|
| 1 | Every rule converges under both concepts | **Failed** for owner-residence (both concepts) and control (concept a): best responses cycled with amplitude about 0.05 and did not settle even with strong damping. Diagnosis: the credit-relief term ρ · max(0, τₛ − τₚ) gives the secondary claimant an incentive to sit just above the primary's rate, and the kinked best responses chase each other. Cycling stopped with ρ = 0 or with a smoother kink. | Credit relief smoothed with its own parameter κ_relief (default 20), justified by heterogeneity in how credit operates in practice (base definitions, timing). Escape capacity keeps κ = 200. All rules now converge. Any future non-convergence is reported as "no pure equilibrium found" and excluded from rankings. κ_relief is swept. |
| 2 | Interior solutions | Place of validation and universal non-assignment reach the rate bound. Under validation, every holder bears the same validation-weighted burden whatever its own choices, so a validating state's rate barely moves its base; only exit restrains it. Under non-assignment the rate taxes nothing but the residence backstop. | Corners are reported as a separate category ("rate unconstrained by the base"), not ranked. For validation this is itself a finding: the rule exports tax to holders with no nexus, consistent with Part 6.6. |
| 3 | Ranking agreement between concepts | Owner-residence and enclosure swap order between (a) and (b) with a gap of about 3% under (a), larger than the near-ties seen in specification testing. | The agreement rule (declare only where both agree) already handles this; the specification's description of flips as near-ties is narrowed accordingly. |
| 4 | Partition formula and uniqueness | Owner-residence with no dual residence and full observability reproduces τᵢ* = 1/[θᵢ(1 − Sᵢ)] within 10⁻⁶. Six random starts converge to the same rates (spread 6 × 10⁻⁶). | None. |
| 5 | Proposition 2 signature | **Failed.** The observable statistic (bilateral traffic per unit of base lost) could not tell restructuring from migration: its sensitivity was 0.003 to 0.02 for every rule that permits restructuring, against 1.08 under owner-residence. Diagnosis: in equilibrium, base assigned to a jurisdiction under a movable or elective predicate is mostly **economically located elsewhere** (alignment 0.15 to 0.26). Most of what a jurisdiction loses after a rate rise is foreign activity moving its predicate to another host, which is neither migration nor round-tripping. | A third response, **conduit switching**, is added. The tool reports the model-truth decomposition of lost base into migration, round-tripping and conduit switching (it sums to one), plus an identifiability score for the observable statistic. In the default world conduit switching is 74% to 84% of leakage under every rule except owner-residence, which shows pure migration. |
| 6 | Proposition 1 | Control and enclosure induce almost identical networks (distance 0.018) and base distributions (0.017) yet differ in mean rate by 0.10, because control's multi-signature overlap changes the burden through credit relief without changing the network or the distribution. | Proposition 1 is restated with a third channel: consequences are determined by the induced network, the base distribution and the **incidence of overlap and gap**. |
| 7 | Proposition 3 grid | Computes in about 0.2 s per cell. | None. |
| 8 | Run time | All seven rules under both concepts in about 4 s; the full preview export (with a 12-draw sweep) in about 1 minute. | Sensitivity sweeps are feasible in the preview at modest size. |
| 9 | Enforcement (Part 9) | Improving observation of self-hosted holdings **lowers nominal rates** (for example control 0.77 to 0.58) but **raises revenue** for every rule that relies on self-hosted claims (control 0.33 to 0.39), and leaves intermediary location unchanged. Nominal rates fall because the same nominal rate now bites on more of the base. | The interface reports revenue and unobserved base for the enforcement comparison, not nominal rates. The paper's statement that rate and enforcement are complements holds here for revenue and effective rates, not nominal rates; worth a sentence in Part 9. |
| 10 | Robustness of convergence | In the 12-draw sweep, owner-residence failed to converge in 4 draws (those with the sharpest credit-relief kink); every other rule converged in all draws. | Non-converged draws are counted and shown; rankings involving them are "unranked". |
| 11 | Stability of predictions before freezing | A first draft of prediction P2-1 ("conduit switching is the majority of leakage") was falsified within the sweep at low predicate mobility (as low as 0.23). | P2-1 restated: conduit switching rises with mobility and is the majority at or above default mobility (true in every sweep run at that level). Predictions are now checked against the sweep before they are frozen. |

### Consequences for the paper (to be carried into the specification)
- **Proposition 2** should distinguish three responses, not two. The new one, conduit switching, is plausibly the dominant form of leakage under movable or elective predicates, and it has a sharp implication: rules that assign on movable predicates erode the alignment between assignment and economic activity, and with it the observability of their own round-tripping. That strengthens the paper's Part 9 argument for institutional predicates.
- **Proposition 1** needs the third channel.
- The validation rule's corner supports Part 6.6's conclusion on a new ground: the rule removes the holder's margin of response, so the assigned state's rate is restrained only by exit from the asset class.

All results here depend on the synthetic world, in particular the predicate-mobility weights, which set baseline alignment. These are swept in phase 4 before any of the above is stated as a property of the rules rather than of this world.

## 10. Second audit and version 0.2 (Windows preview)

The 0.1 preview was audited for flaws beyond the checks in section 9. Nine were found; a tenth surfaced while testing the 0.2 build. Each is recorded with the fix and the result after the fix. Figures are for the default synthetic world (12 sensitivity draws) and remain model outputs, not findings about any real jurisdiction.

| # | Flaw | Why it mattered | Fix in 0.2 | Result after fix |
|---|---|---|---|---|
| 1 | Rules were ranked on **nominal** rates | A claimant that cannot observe much of its base can post a high nominal rate that collects little. The 0.1 headline (intermediary location sustains the lowest rate) was an artefact of this and was wrong. | Ranking moved to the **effective rate** (rule revenue ÷ assigned base). Nominal rates are still shown, labelled as not comparable across rules. | Intermediary location moves from last to first or joint first (see flaw 10 for the refinement). |
| 2 | The network channel was nearly inert | With β = 2 the escape term barely moved θ, so Proposition 1's network channel was untested. | β default raised to 25 and swept over 0 to 50; every run reports the effective rate with β = 0 against the current β. | The network channel matters mainly under concept (b) (about −17 points on average) and little under (a) (about −2), because rates converge in equilibrium and escape capacity is small near equilibrium. |
| 3 | "Migration" counted exit from the asset class | Base leaving digital assets altogether was booked as migration between jurisdictions. | Six-way decomposition from per-draw transitions: migration, round-tripping, conduit switching, foreign relocation, movement into the gap, exit. Sums to one (test 7). | Owner-residence: about 68% migration, 30% exit. |
| 4 | Plain logit implied independence of irrelevant alternatives | Substitution between predicates and locations was proportional by construction, so the leakage shares were assumed rather than modelled. | Mixed logit with location stickiness σ (16 antithetic normal draws); σ swept. | Conduit switching ranges from about 9% to 35% of leakage and rises with σ. |
| 5 | The validation rule's corner was built in | Validation bore on every holder identically, so the rate was unrestrained by design. | Validation modelled as a chain choice open to holders. | Validation is now interior; only universal non-assignment is a corner (test 5). |
| 6 | Proposition 3 compared rules that differ in more than the failure mode, in different units | The gap and overlap panels used different rules and compared revenue with tax burden directly. | Matched pair: rule X (gap) and rule Y (overlap) treat custodial holdings identically and differ only for self-hosted keys held abroad. The two costs are reported separately, with the equal-weight comparison stated as a choice. | Gap costlier at every tested ρ while φ ≤ 0.6; overlap costlier only at φ = 0.75 with low ρ. |
| 7 | Predictions were not falsifiable against data, and P2-2 was tautological | Model statements were presented as if they were testable predictions. | The register now separates fingerprinted **model outputs** (checked against the sweep at a 90% threshold) from **draft observable hypotheses** (H1 to H3), which are not frozen until data sources are specified. | 19 ranking outputs pass the threshold, plus one each for Propositions 2 and 3; H1 to H3 remain drafts. |
| 8 | Concept (b) was described as full anticipation | It holds the network fixed and anticipates only own escape capacity. | Relabelled "partial anticipation" throughout. | Wording only. |
| 9 | Thin sweep and a single shock | Robustness rested on few draws and one shocked jurisdiction. | Stratified sweep over β, θ₀, ρ, φ, σ, κ_relief, predicate mobility and the world seed; leakage averages every jurisdiction shocked by 2 and 5 points, with ranges. | Owner-residence still fails to converge in 4 of 12 draws (sharp relief kink); those pairs are "unranked". |
| 10 | **Effective rate counted the residence backstop on gap base** (found while testing 0.2) | Revenue included φ · τ collected by residence states on base the rule leaves unassigned, while the denominator counted assigned base only. This inflated the intermediary rule (42.8% under (a)). | Two measures. **Effective rate**: revenue the rule itself raises ÷ base it assigns (backstop excluded). **Yield**: all revenue ÷ base remaining in the asset class (gap included). Rankings are reported on both. Test 12 pins the accounting identity. | See below. |

**Corrected headline (0.2).**
- Effective rate, (a) and (b): intermediary 39.1% and 21.2%; owner-residence 37.7% and 26.7% (a tie, since the concepts disagree); then control, validation, registration, enclosure.
- Yield: owner-residence is highest under both concepts in every converged sweep draw. Intermediary location falls to the bottom tier (22.5% and 14.5%), level with enclosure, because 33% to 43% of its base sits in the gap.
- Read together: intermediary location sustains a high rate on what it reaches, but it reaches less. The difference between the two rankings is the gap, which is the paper's Part 7 point expressed in revenue.
- Proposition 2 by predicate type is not cleanly supported: registration, not a movable predicate, shows the most round-tripping.
- The gap cost in the matched pair is not monotone in φ: a weak backstop (about 0.15) lets source states raise rates, which pushes more base into the gap, so forgone revenue rises before it falls.

**Packaging.** Tk is unavailable in the embeddable Windows Python, so the preview is a single console executable that starts a local server on 127.0.0.1 (from port 8765) and opens an offline interface in the default browser. Nothing is sent over the network. Built with PyInstaller 6.11.1 on CPython 3.12.9 and NumPy 2.1.3 under Wine; tested under Wine only, not on a Windows machine.

**Visualisation tools in the interface.** Every chart exports as PNG, SVG and CSV. Tabs: Overview; Rates (measure selector, pairwise ranking switchable between effective rate and yield, network-effect bars); Networks (rule, concept and flow-threshold controls); Leakage (six-way stacked bars with ranges); Gap and overlap (matched-pair heatmap); Observation; Proposition 1 (scatter and table); Sensitivity (ranking stability, switchable measure); Chart builder (any measure by rule and concept; sweep scatter of any parameter against any outcome for up to three rules); Register.

## 11. Interface for two audiences (0.2 interface update)

The interface must serve both an economist and a legal researcher without quantitative training. One build serves both through a reading-mode switch in the header ("Plain English" or "Technical"). The choice is remembered on the user's machine. Plain English is the default on first opening.

| Element | Plain English mode | Technical mode |
|---|---|---|
| Tab names | Descriptive ("Tax each rule sustains", "Untaxed or double-taxed?", "Why rules differ") | Analytical ("Rates", "Gap and overlap", "Proposition 1") |
| Chart guidance | A yellow box, open by default, on every chart: what it shows, how to read it, why it matters for the paper. The technical description is folded away. | The technical description is shown; the plain-English box is folded away but available. |
| Settings | Plain names grouped by question ("How states compete", "Gaps and double taxation"), with the symbol kept beside each name for cross-reference | Symbols and model terms (θ₀, β, ρ, φ) |
| Equilibrium concepts | "View A" and "View B", explained in the Guide | "Concept (a)" and "Concept (b)" |
| Overview | "Start here" panel and plain-language findings | Findings in model terms |
| Glossary | The Guide tab: every rule and measure defined in plain English, each with its technical definition beneath | The same tab, titled "Glossary" |

Every setting carries a "?" with a hover explanation in both registers. Legal analogies are used only where they are accurate (a full foreign tax credit for ρ = 1; a subject-to-tax or switch-over rule for φ, described as "similar in spirit").

**Colour.** The palette was changed to more saturated, clearly separated hues (blue, orange, teal, amber, magenta, violet). Violet replaced the earlier dark green, which was hard to tell from teal. Text on coloured bars uses a dark or light ink chosen for each hue. In the cross-border network each jurisdiction has its own colour (circle outline, outgoing arrows and table swatch), so states can be followed across the chart. An on-chart colour key gives the rate scale, because the shading direction differs between light and dark display themes.

**Checks.** Every tab rendered in both modes and both display themes with no script errors, on the local build and on the packaged executable under Wine. Layout was also checked at phone width. Acceptance tests: 12 of 12 pass. The model is unchanged by this update.

## 12. Next build (0.3): mixed regimes, coding template and mismatch matrix

The roadmap (jaf_tool_real_data_roadmap.md, Part C) sets step 1 as: build the mixed-regime extension, the three-layer coding template and the data layer with provenance. Before building, the step was checked against the 0.2 engine.

### 12.1 Logical evaluation

| # | Issue | Severity | Resolution |
|---|---|---|---|
| 1 | **Each holding option carries a single placement location *p*, which the one active rule interprets** (as the intermediary's seat, the key location, the registration place, and so on), and placement mobility is defined per rule. Once states apply different rules, one option must answer all of them at once, so "let each jurisdiction carry its own rule" is undefined on the 0.2 option space. Carrying a separate location for every connecting factor would multiply the options beyond computation. | **Fatal as written** | **Co-location assumption.** A holding is housed in one place *p*, and every location-based connecting factor follows it: for custodial holdings the intermediary's seat, registration, infrastructure and key control are at *p*; for self-hosted holdings the key and infrastructure are at *p*; a multi-signature arrangement adds a co-signer at the holder's residence. Placement mobility becomes a property of the holding configuration and the destination (exchange presence), not of the rule. Personal factors (residence, citizenship) come from holder attributes. **Limitation:** the split between an exchange's legal seat and its operational base cannot be represented; a second placement dimension for custodial holdings is deferred to a later build. |
| 2 | Mixed rules can give three or more claimants (for example, citizenship, residence and intermediary seat) where 0.2 allows two | Serious | Overlaps generalised to several secondary claimants. Relief order: location-based claimant primary, then residence, then citizenship, mirroring the usual treaty and foreign-tax-credit ordering. Stated as an assumption. |
| 3 | Observability in 0.2 depends only on the holding configuration, not on who is looking. CARF and DAC8 make it depend on the pair (claimant, placement). | Serious | Observability per claim: domestic custodial holdings at the domestic level; foreign custodial holdings at the exchange-of-information level only if both states exchange by the scenario year; self-hosted holdings at the self-hosted level. |
| 4 | The collection layer (withholding by intermediaries) has no counterpart in 0.2 | Moderate | Modelled through observation: withholding by domestic intermediaries raises the observability of domestic custodial holdings to full collection. Statutory incidence is not modelled (stated). A prohibition on domestic exchanges sets custodial placement in that state to zero. |
| 5 | Real states have statutory rates; the 0.2 model only produces competitive rates. The model's rate is an effective rate on the return from holdings, not a statutory capital gains rate. | Moderate | Per-jurisdiction rate mode: fixed at the coded rate, or set by competition. The template's rate field is labelled "effective rate on returns from holdings" with guidance on conversion. |
| 6 | A demonstration world with real country names would attribute invented law to real states | Serious (integrity) | The illustrative template uses hypothetical states (Country A and so on). The real-sample template lists the candidate countries with every legal field blank and "verified" set to no. |
| 7 | Mixed-world outputs are per jurisdiction, not per rule, so the 0.2 report and tabs do not fit | Moderate | New "Coded world" report and tab: per-jurisdiction table, mismatch matrix, network, and a "change one country's rule" counterfactual. The synthetic rule comparison is kept unchanged. |
| 8 | Run time with about 14 jurisdictions | Checked | Measured: 11 s (concept a) and 34 s (concept b) for 14 jurisdictions, against under 3 s for 6. Acceptable. |

**Verdict.** One flaw was fatal to the step as written (issue 1). It is resolved by the co-location assumption, at the stated cost. No fatal flaw remains, so the build proceeds.

### 12.2 Acceptance tests added for 0.3

- 13: With every state applying the same rule, and placement weights set to the 0.2 values, the mixed engine reproduces the 0.2 equilibrium for each of the five assigning rules.
- 14: Three claimants: the burden and revenue split follow the stated relief order, and revenue sums to the total.
- 15: Fixed-rate states keep their coded rate; competitive states converge.
- 16: The mismatch matrix matches a hand-worked example.
- 17: Template round trip: the illustrative workbook written and read back is identical.
- 18: Template validation catches missing fields, bad values and duplicate codes, and flags unverified rows and rows without a source.
- 19: Exchange of information switched on raises the observability of foreign custodial holdings; switched off, it falls to the self-hosted level.

### 12.3 Build results (0.3)

- All 19 acceptance tests pass. Test 13 reproduces the 0.2 equilibria to machine precision (deviation 0). Test 18 at first failed because the test, not the validator, was wrong: openpyxl ignores `cell(row, column, None)`, so the cells meant to be emptied never were. The test was corrected; the validator was already right.
- The illustrative world (eight hypothetical states with mixed rules, fixed and competitive rates) converges under both concepts in under half a second; a counterfactual takes about 1.5 seconds.
- The mismatch matrix shows the mechanism the roadmap anticipated. A state taxing only holdings at its own exchanges, surrounded by residence-based states, leaves its residents untaxed wherever they hold abroad, while residents of residence-based states holding at its exchanges are taxed twice. Switching that state to residence taxation cut the untaxed share from 21.6% to 17.4% but halved its own revenue and raised double taxation (17.2% to 20.4%). These are properties of an invented world, recorded only to show that the tool works.
- Packaging: the Windows executable (PyInstaller under Wine) now bundles openpyxl and the illustrative results. It was smoke-tested under Wine for template download, upload, run, counterfactual and save. It has not yet been tested on a Windows machine.

### 12.4 Next steps

1. **Author:** code the real-world sample in the blank template: liability, collection and observation, with dates, OSCOLA sources and verification.
2. **Build 0.4:** a second placement dimension for custodial holdings (legal seat against operational base), lifting the main limitation of the co-location assumption; and per-pair treaty relief, replacing the single global rate.
3. **Then:** the India 2022 case study (calibration and fitting), per the roadmap.

## 13. Build 0.4: legal seat against operational base; treaty relief by pair

Section 12.4 sets two items for 0.4: lift the co-location assumption for exchange-held holdings by separating an exchange's legal seat from its operational base, and replace the single global treaty-relief rate with relief agreed between pairs of states.

### 13.1 Logical evaluation

| # | Issue | Severity | Resolution |
|---|---|---|---|
| 1 | **"Seat of the intermediary" is not one place.** States locate a company by different tests: incorporation or licence (a legal seat) or management and operations (a base). An intermediary rule applied at a uniform "seat" would code every state's test identically, which is wrong for states using a management test. | **Fatal if built as planned** | Each intermediary-based state codes its own test: **seat** or **base**. This yields the mismatch the paper predicts. If the seat state tests by base and the base state tests by seat, neither claims (a gap); if the reverse, both claim (an overlap). |
| 2 | Letting every exchange choose any (seat, base) pair multiplies exchange-held options by the number of states (about 2,700 for 14 states) and requires data no one has | Serious | Each operating state codes one typical offshore place of incorporation and the share of its exchanges incorporated there. Exchange-held options become two per (residence, base) pair, so the option count roughly doubles rather than multiplying. Stated as a limitation. |
| 3 | Other location-based factors must be assigned to seat or base | Moderate | Registration follows the seat. Infrastructure, key control and validation follow the base (where the systems and keys are run). Self-held holdings keep seat equal to base. |
| 4 | Where both a seat state and a base state claim, the relief order between them is unspecified | Moderate | The base state taxes first, then the seat state, then residence, then citizenship. Stated as an assumption. |
| 5 | Observability: which location triggers domestic reporting? | Moderate | An authority sees exchange holdings at the domestic level if the exchange's seat or base is in its territory. Otherwise it sees them through automatic exchange if it, and either the seat or the base state, exchange by the scenario year; failing that, only at the self-reported level. |
| 6 | A prohibition on domestic exchanges must cover both locations | Minor | Prohibited if either the seat or the base lies in a prohibiting state. |
| 7 | Treaty relief is granted by the state that gives relief (usually residence), for tax levied by the state with the prior claim. A symmetric pair rate would misstate one-sided relief such as unilateral credits. | Serious | Relief is coded by direction (relieving state, taxing state, rate), with an option to apply both ways. Pairs not coded use the global default. Each secondary claimant relieves against the primary only, as in 0.3. |
| 8 | Saved 0.3 results lack the new structures | Minor | On start-up, results from an earlier version are discarded while the coded world is kept, and the user is asked to re-run. |
| 9 | The mismatch map must show seat and base | Moderate | For exchange-held holdings, the map's columns become the exchange types that exist (base, plus seat if incorporated elsewhere), so only real combinations appear. |

**Verdict.** Issue 1 would have made the seat and base split misleading as originally planned. It is resolved by coding each state's own corporate location test. No fatal flaw remains, so the build proceeds.

### 13.2 Acceptance tests added for 0.4

- 20: Seat and base mismatch, hand-worked: a seat-testing seat state plus a base-testing base state gives an overlap; the reverse gives a gap.
- 21: Pair relief: with full relief for a pair, unrelieved double tax for that pair is zero; with none, it equals the full second tax.
- 22: Validation catches an unknown offshore incorporation code, a missing share, and treaty relief out of range.
- Tests 1 to 19 must still pass. In particular, test 13 (equivalence with 0.2) confirms the extension changes nothing when no offshore incorporation or pair relief is coded.

### 13.3 Build results (0.4)

- All 23 acceptance tests pass (22 planned plus test 23, added during the build). Test 13 still reproduces 0.2 exactly, confirming that the extension changes nothing where no offshore incorporation or pair relief is coded. Test 18 broke because it addressed template columns by position; it now finds them by header, which also guards against future column changes.
- Two defects were found and fixed while building: (i) the template wrote "Intermediary located by" and a zero offshore share for every state, confusing readers and triggering spurious warnings on reading; both are now left blank where they do not apply. (ii) In the coded-rules table the source column was squeezed off-screen, making rows very tall; it now has a minimum width. (iii) A check of the read-me's claim that 0.3 templates still load found it false: every column was treated as mandatory. Optional columns that are absent now produce warnings and defaults; where the intermediary-test column is absent, intermediary-based states are assumed to locate by seat, with a warning on each such row. Test 23 locks this in, bringing the suite to 23 tests.
- The illustrative world now has exchanges incorporated in a hub, one intermediary-based state testing by operations, and three directional treaty reliefs. Its mismatch map shows triple claims on exchanges operating in that state but incorporated in the registration-taxing hub, and taxation by the hub alone of exchanges operating in the untaxing hub but incorporated in it. The what-if switching that state's location test from operations to incorporation lowered the untaxed share slightly (19.5% to 19.1%), raised double taxation (22.3% to 22.5%) and lowered its own revenue (1.10 to 0.97 per 100 units). Invented world; recorded only to show that the tool works.
- Run time is unchanged in practice: the illustrative world (216 options) solves in 0.1 s (a) and 0.3 s (b).
- Windows executable rebuilt and smoke-tested under Wine (template download, upload, run, counterfactual with an intermediary location test, save, interface). Not yet tested on a Windows machine.

### 13.4 Next steps

1. **Author:** code the real-world sample. Three new fields per state: the intermediary location test (if relevant), the typical offshore place of incorporation of exchanges operating there, and its share. Plus the Treaties sheet.
2. **Then:** the India 2022 case study (calibration and fitting), per the roadmap. Its own logic check should consider whether one natural experiment can identify θ₀, β and σ jointly, or whether some must be fixed by judgement.
