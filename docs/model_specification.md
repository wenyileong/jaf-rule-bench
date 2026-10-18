# Model Specification: *Jurisdictional Assignment Functions* (SSRN 7351160)

Computational specification for JAF Rule Bench, version 1.0 (18 October 2026).

The document has two parts. **Part B** specifies the model as implemented in version 1.0: every quantity the tool computes, the measurement model that links them to data, and the estimation, identification, validation, recovery and pre-registration methods. **Part A** is the record from version 0.2 of how each open point in the paper's model was resolved, with the tests that failed along the way. Part A is kept because it bears on what the paper can claim. Where the two differ (for example the default value of β), Part B governs.

Notation: jurisdictions i, k, n ∈ {1, …, N}; holder residence j; configuration c ∈ {custodial, single, multisig}; base b (where a holding is housed, or where an exchange operates); seat s (where an exchange is incorporated or licensed). softplus(x; κ) = ln(1 + e^{κx})/κ, a smooth approximation to max(0, x).

---

# Part B. The model as implemented in version 1.0

## B1. Two kinds of world

1. **Synthetic world (single rule).** N = 6 jurisdictions with sizes, exchange presence, registration geography and validation geography drawn from a seeded generator. Every jurisdiction applies the same assignment rule. This is the paper's comparison of rules (tabs other than the coded-world and estimation tabs).
2. **Coded world (mixed regimes).** Named jurisdictions, each with its own liability rule, collection method and observation capacity, read from the coding template. The mixed engine reproduces the single-rule engine exactly when every jurisdiction applies the same rule (acceptance test 13).

The rest of Part B describes the coded world, which the estimation layer uses.

## B2. Holding options

An option is k = (j, c, b, s). For self-hosted configurations s = b. For custodial holdings, an exchange operating in b is seated in b, or in the offshore place h(b) coded for b with share η_b:

    weight of (b, s): 1 − η_b if s = b; η_b if s = h(b).

The non-tax weight of an option is

    A_k = a_j · w_c · π(j, c, b) · η(b, s),

where a_j is the relative holder base resident in j, w_c the weight of configuration c, and the placement weight π is 1 if b = j; m_cust · e_b for custodial holdings abroad (e_b the coded exchange presence); m_self for self-hosted holdings abroad; and effectively zero (10⁻¹²) for custodial holdings at an exchange based or seated in a state that prohibits domestic exchanges. m_cust and m_self are the world settings "ease of holding with a foreign exchange" and "ease of placing self-hosted keys abroad".

Under the **co-location assumption**, every location-based connecting factor of a holding follows its base b, except that registration, and intermediary location under a seat test, follow the seat s.

## B3. Claimants and relief order

For each option and each personal subtype of residents of j (plain residents; residents also resident in, or citizens of, another state, with the coded shares), the ordered claimant list is:

1. base claims: b, if b taxes by control, enclosure or validation; or by intermediary location (custodial only) with a base test, or with a seat test where s = b;
2. seat claims: s, if s taxes by registration; or by intermediary location (custodial only) with a seat test, or with a base test where s = b;
3. a co-signer: j, for a multi-signature holding placed abroad where j taxes by control;
4. residence: j, if j taxes by residence (with or without citizenship); then a second residence state, if it does;
5. citizenship: a state of citizenship that taxes citizens resident abroad.

Duplicates are dropped. The first entry is the primary claimant; up to three further claimants are kept (subtypes with more are truncated and the truncated share is reported). An empty list is a **gap**.

## B4. Burden

For an entry with primary p and secondaries q₁, …, q_m, the burden per unit of holding is

    B = τ_p v_p + Σ_q [ (1 − ρ_{q,p}) τ_q + ρ_{q,p} softplus(τ_q − τ_p; κ_r) ] v_q,

and for a gap, B = φ_j τ_j (the residence top-up). ρ_{q,p} is the share of double tax that q relieves for tax levied first by p (the directional relief matrix: coded pairs, otherwise the default). v is the visibility of the holding to the claimant:

- custodial holdings, exchange based in b and seated in s, seen by k: V[k, b, s] = 1 if k collects by domestic withholding and k ∈ {b, s}; the coded domestic visibility if k ∈ {b, s} otherwise; the visibility of exchanged information if k and (b or s) exchange information in the scenario year; otherwise k's visibility of self-hosted holdings;
- self-hosted holdings: k's visibility of self-hosted holdings.

Visibility multiplies the expected burden: tax that cannot be seen is not paid. The model assumes that tax falls on the holder whoever collects it; who bears a withholding tax in practice (incidence) is not modelled.

## B5. Holder choice

Holders choose among all options and an outside option (leaving the asset class). Utility of option k in simulation draw r:

    U_kr = ln A_k − Σ_entries ω · θ_{claimant} · B + ν_{r, j(k)},     U_exit = ln(exit_weight),

where ω is the subtype weight, θ attaches to the primary claimant (to j for a gap), and ν_{r, j} ~ N(0, σ²) is a draw-specific taste for economic location j (antithetic draws; σ is the stickiness of economic location). Shares are logit within each draw and averaged across draws (mixed logit).

**Sensitivity and escape capacity.** θ_i = θ₀ + β E_i with

    E_i = Σ_{n ≠ i} M_{in} softplus(τ_i − τ_n; κ),

where M = (I − αP)⁻¹ is the Katz resolvent of the row-normalised flow matrix P. Flows come from the assignment of holdings to primary claimants, with a share (home bias) of each unit's transactions at its own economic location and the rest spread evenly; flows to unassigned holdings are not flows between jurisdictions.

## B6. Rates and equilibrium

A jurisdiction's rate is either **fixed** at its coded effective rate or **competitive**: set to maximise its revenue R_i given others' rates. Two concepts:

- (a) elasticity-consistent: in each best response θ is held at its current value;
- (b) partial anticipation: θ is recomputed for each candidate rate, with the network M held fixed.

Best responses use a nested grid search on [0, τ_max] (21 points, 5 rounds). Rates are updated with adaptive damping until the largest change is below 10⁻⁵ and M is stable.

**Epsilon-equilibrium (new in 1.0).** Where a best-response revenue curve is almost flat with two near-equal maxima, rates can cycle between them indefinitely although no state gains materially. From iteration 150, every tenth iteration, the average of the last 30 iterates is tested: if no competitive state could raise its revenue by more than 0.01% (relative) by deviating from it, it is accepted and the largest such gain is reported as `epsilon`. If rates still do not settle, the result is labelled not converged and the largest forgone gain is reported. In a 24-draw robustness sweep (168 solves of concept (a)), one solve remained unsettled, with a forgone gain of 0.03% of that state's revenue.

## B7. Outputs

- Revenue by jurisdiction; effective rate (rule revenue, excluding the residence top-up on gaps, divided by assigned base); yield (all revenue divided by base remaining in the class).
- Failure measures: gap, overlap, multiple claims (three or more), unrelieved double tax, forgone revenue on gaps, unobserved assigned base.
- Leakage decomposition after a rate rise into migration, round-tripping, conduit switching, foreign relocation, movement into the gap and exit (per-draw transitions).
- The mismatch matrix: claimant lists by residence and exchange type, which needs no economic assumptions.

## B8. Episodes

An episode is the coded world with stated changes: jurisdiction fields (liability rule, intermediary test, collection, prohibition of domestic exchanges, visibilities, first year of information exchange, residence top-up, rate mode and effective rate, exchange presence, holder base, offshore incorporation) or settings (scenario year, visibility of exchanged information, default treaty relief). "baseline" is the coded world unchanged. A single reform (for example India 2022) is one episode; staggered adoption of automatic exchange (for example the CARF waves) is one episode per wave, each setting the scenario year.

Each episode is solved separately at the same behavioural parameters. The comparison is between settled states: adjustment is assumed complete within the window over which the data are measured, which is a choice to be pre-registered (build plan s 14.3, issue 4).

## B9. Measurement model

Data record different quantities from the model. Each observation is defined as the model-implied value of what the data record.

**Reported exchange volume.** Volume at an exchange based in b is genuine holdings × genuine turnover t_b, inflated by wash trading with share w_b of reported volume:

    vol_k = s_k · t_b / (1 − w_b)   for custodial options k with base b.

t_b defaults to 1 (equal genuine turnover) and w_b to 0.

**Quantities** (j a residence; masses are option shares s_k or entry masses):

| Quantity | Definition | Recorded as |
|---|---|---|
| resident_domestic_exchange_share(j) | Σ vol over custodial options of residents of j based in j / Σ vol over residents' custodial options | volume |
| resident_offshore_unexchanged_share(j) | same denominator; numerator over options with b ≠ j, s ≠ j and no exchange of information between j and b or s | volume |
| custodial_share_by_base(i) | Σ vol with base i / Σ vol | volume |
| custodial_share_by_seat(i) | Σ vol with seat i / Σ vol | volume |
| resident_custodial_share(j) | residents' custodial holdings / residents' holdings | holdings |
| resident_share(j) | residents' holdings / all holdings in the class | holdings |
| resident_visible_share(j) | Σ entry mass × primary visibility over residents' assigned entries / residents' holdings | holdings |
| resident_gap_share(j) | residents' unassigned holdings / residents' holdings | holdings |
| exit_share | outside-option share | holdings; only as a change |
| rate(i) | τ_i | rate |
| revenue(i) | R_i in model units | only as a change |
| revenue_share(i) | R_i / Σ R | share |

An observation is a level in one episode, or a **ratio** (episode / comparison episode) or **difference** (episode minus comparison episode). Quantities whose level has no observed counterpart (exit share, revenue in model units) may only be used as changes. Each observation carries a standard error sd_o, in its own units, and a role: **target** (used to estimate) or **holdout** (used only to validate).

## B10. Estimation

Free parameters θ (a subset of θ₀, β, σ, exit weight, home bias, α, m_cust, m_self) are chosen within stated bounds to minimise

    J(θ) = Σ_{targets} ((m_o(θ) − y_o) / sd_o)²,

a simulated minimum-distance criterion with the inverse measurement variances as weights. Other parameters are fixed at stated values (or the interface values). Optimisation is by Levenberg–Marquardt on the residuals, in unbounded coordinates u = logit((θ − lo)/(hi − lo)), from the stated start and further seeded starts; the best fit is kept and the agreement of starts is reported. Equilibria are solved to a tolerance of 10⁻⁶, warm-started from the previous solution of the same episode; within estimation, an epsilon-equilibrium (B6) is accepted only if no state could gain more than 10⁻⁷ of its revenue, and any such acceptance at the estimate is reported. Parameter values, bounds and judgement ranges are checked against the values the model admits (for example 0 ≤ α < 1) before any run.

**Uncertainty.** With G the Jacobian of the target moments (central differences, step 0.5% of each range) and W = diag(1/sd²),

    Var(θ̂) ≈ (G′WG)⁻¹.

This propagates the stated measurement errors; it is not a sampling error, because the data are aggregates without sampling theory. If G′WG is singular (possible only when identification has been overridden), no covariance is reported: standard errors are shown as undetermined and predictions cannot be scored. 95% intervals are θ̂ ± 1.96 se, clipped to the bounds. The fit is summarised by J against χ² with n − k degrees of freedom (when n > k). Warnings are issued for estimates at a bound, for distinct starts reaching different parameters with a similar fit, and for unsettled equilibria at the estimate.

## B11. Identification diagnostics

Before estimation (at the start values) and again at the estimate, the tool computes the scaled Jacobian

    G̃_{o,p} = ∂(m_o / sd_o) / ∂(θ_p / range_p),

the change in each standardised target when a parameter moves across its whole range. From it: the rank and condition number of G̃; the implied standard error of each parameter as a share of its range, sqrt(diag((G̃′G̃)⁻¹)); and near-flat directions (singular vectors with singular value below 1% of the largest). A parameter is **identified** if its relative standard error is below 0.10, **weak** below 0.33, and **not identified** above that, if it lies in a rank-deficient direction, or if it has no effect on the targets. The order condition (at least as many targets as free parameters) is checked. Estimation is refused if any free parameter is not identified, unless the user overrides; the diagnosis is local (at the point where it is computed).

**Finding from the build.** On the illustrative design, θ₀ and β are not separately identified: both raise holders' sensitivity in nearly the same pattern across the targets, probably because escape capacity varies little across the states in this design. The illustrative design therefore estimates θ₀ and m_cust and fixes β by judgement. A real design that wants β will need facts from states whose escape routes differ sharply (build plan s 14.4, item 4).

## B12. Validation

With θ̂ and its covariance Σ, each holdout is predicted as m_h(θ̂). Its band combines (i) parameter uncertainty, H Σ H′ with H the holdout Jacobian, and (ii) a judgement band for parameters fixed by judgement with a stated plausible range: the prediction is recomputed at each end of each range (one parameter at a time), the larger deviation is treated as 1.96 standard deviations, and the contributions are combined in quadrature. A holdout is **consistent** if

    |z| = |y_h − m_h(θ̂)| / sqrt(sd_h² + var_param + var_judgement) ≤ 1.96.

Σ z² is reported against χ² with as many degrees of freedom as holdouts. A holdout whose band cannot be computed (an undetermined parameter direction) is reported as unscorable, never as consistent.

## B13. Known-truth recovery

At stated true values θ*, the tool computes every observation of the design, then estimates blind from starting values at least a tenth of the range away: once without noise, and in R further runs with normal noise of each observation's sd. It passes if the noiseless estimate is within 2% of each parameter's range and every noisy estimate lies within 3.5 standard errors of the truth. It reports bias, root mean squared error, mean standard error and coverage of the 95% intervals. Passing shows that the estimator inverts the model and that its standard errors are honest under correct specification; it is not evidence that the model is correctly specified (build plan s 14.3, issue 3).

## B14. Pre-registration

Freezing records: the SHA-256 fingerprint of the coded world (law, provenance and settings); the episodes and their changes; each observation's definition (quantity, jurisdiction, episodes, comparison, standard error, role, source) **without its value**; the measurement attributes; the parameter settings (free or fixed, values, bounds, judgement ranges); the estimation settings; and the hypotheses. It also records every other model setting estimation will use (the interface values the coded-world engine reads, such as α, home bias, draws and seed, and the world's mobility settings), so that a change to any of them after freezing is a recorded departure. The whole record (title, author, date, the list of observations that already had values, and the content) is fingerprinted with SHA-256 over its canonical JSON and exported as a Markdown document (with the JSON appended) and a JSON record. The record notes any observations that already had values when it was frozen. When a record is loaded, the current design and settings are checked against it and every departure is listed (added, removed or changed items; changed estimation or model settings; changed tool version; a record edited after freezing); a catch-all compares the fingerprints of the whole design. Duplicate identifiers are rejected on reading. The fingerprint cannot prove timing; deposit with an independent registry before data access does.

## B15. Parameters and defaults

| Parameter | Meaning | Default | Range offered for estimation |
|---|---|---|---|
| θ₀ | baseline semi-elasticity | 3.0 | 2 to 8 |
| β | weight of escape capacity | 25 | 0 to 60 |
| α | per-step discount in the resolvent | 0.6 | 0.1 to 0.95 |
| σ | dispersion of location tastes | 1.0 | 0 to 3 |
| exit weight | attractiveness of the outside option | 0.6 | 0.05 to 3 |
| home bias | share of transactions at home | 0.7 | 0.3 to 0.95 |
| m_cust | ease of holding with a foreign exchange | 0.40 (world setting) | 0.01 to 2 |
| m_self | ease of placing self-hosted keys abroad | 0.90 (world setting) | 0.01 to 2 |
| κ, κ_r | softplus steepness (escape, relief) | 200, 20 | not estimated |
| draws | simulation draws | 16 | not estimated |

## B16. Assumptions and their limits

1. **Co-location** (B2): a holding's location-based factors follow its base, except seat-based ones. Exchanges with operations in several states are represented by a share split, not by multi-state operations.
2. **Statutory incidence** (B4): tax falls on the holder; collection affects visibility only.
3. **Effective rates**: the model uses the effective rate on returns from holdings. Converting statutory rules into effective rates is the coder's task; the user guide sets out a method.
4. **Static comparison** (B8): episodes are compared as settled states.
5. **Equal genuine turnover** (B9) unless coded otherwise; reported volume is otherwise proportional to holdings.
6. **Local identification** (B11): diagnostics hold near the point where they are computed.
7. **Measurement-error uncertainty only** (B10): no sampling error, no model-specification error. Validation on holdouts is the check on the latter.

---

# Part A. Design decisions and tests (version 0.2)

*Recorded 9 October 2026; citations in section 2 verified. Superseded where Part B differs: in particular, the default β is now 25 (build plan s 10) and the parameter table in section 8 below is the 0.2 table.*

This part records how each open point in the paper's model is resolved for implementation. Every resolution was tested numerically on synthetic data before being adopted. Where a test exposed a flaw in the first proposal, the proposal was revised and the revision retested; the record of what failed is kept, because it bears on what the paper can claim.

---

## 0. Summary of decisions

| # | Issue | Resolution | Status after testing |
|---|---|---|---|
| 1 | First-order condition ignores the endogenous elasticity | Solve both the elasticity-consistent equilibrium and full Nash; declare a ranking of rules only where both agree | Revised: rankings flip between concepts in near-ties |
| 2 | Inconsistent matrices; reciprocal trade read as round-tripping | One substochastic matrix P for all measures; round-tripping measured by change from baseline, not by a null model | Revised: null-model correction and Helmholtz–Hodge both failed as primary measures |
| 3 | Two definitions of the base | Claim set Cᵢ and exclusive base Bᵢ | Adopted unchanged |
| 4 | Shares assume a partition | Option-level logit over (economic location, configuration); gap and overlap arise from the rule | Revised: first proposal was circular |
| 5 | Proposition 3 is argued, not modelled | Restate as a condition on residence enforcement over unassigned holdings (φ) and treaty relief (ρ) | Revised: first proposal conditioned on ρ alone and was wrong |
| 6 | Proposition 2 needs holder behaviour and an observable signature | Holder choice among stay, migrate, restructure; primary signature is the **return ratio** | Revised: paper's stated signature is not observable as written |
| 7 | Proposition 1 omits the share channel (found during testing) | Restate: consequences are determined by the induced network **and** base distribution | New |

---

## 1. Equilibrium concept

### Problem
Footnote 20 gives τᵢ* = 1/[θᵢ(1 − sᵢ)], which assumes θᵢ is fixed. But θᵢ = θ₀ + βEᵢ (footnote 22), and Eᵢ = Σⱼ≠ᵢ Mᵢⱼ max(0, τᵢ − τⱼ) depends on τᵢ. Raising τᵢ also lowers other jurisdictions' escape capacity. The max function is non-smooth.

### Options
- **(a) Elasticity-consistent equilibrium.** Each jurisdiction optimises treating θᵢ as given; θ is recomputed from the resulting rates; the equilibrium is the fixed point. The paper's formula holds exactly at the fixed point.
- **(b) Full Nash.** Each jurisdiction anticipates how its own rate changes θ (its own and others'). Solved numerically by best-response iteration.

### Tests and results (5 jurisdictions, θ₀ = 2, β = 3, α = 0.6)
- (a) converges in about 30 damped iterations; the same solution is reached from 10 random starts (spread below 10⁻⁹); each rate is a best response given θ (deviation 10⁻⁶).
- (b) converges, but rates are about 20% lower than under (a). This is expected: anticipating that a higher rate enlarges one's own escape capacity makes jurisdictions more cautious. **Levels under (a) overstate sustainable rates.**
- Across 40 random worlds, each with three rules inducing different networks, the ranking of rules by mean sustainable rate was identical under (a) and (b) in 31 of 40 worlds. Of 120 pairwise comparisons, 9 flipped, and every flip occurred where the two rules' rates differed by less than 0.44%.
- Smoothing: replacing max(0, x) with softplus at steepness κ converges by κ = 200 (change below 0.001 thereafter).
- With θ₀ = 0.5 all rates hit the upper bound of 1. The formula implies τ* ≥ 1/θ, so interior solutions require θ₀ comfortably above 1/τ_max.

### Resolution
1. Compute both (a) and (b) for every run.
2. Report a ranking between two rules **only where (a) and (b) agree**; otherwise report the pair as tied. In testing this removes every flip.
3. Present levels from (b) if levels are reported at all; the paper already directs readers to rankings rather than levels (Part 7.1).
4. Softplus smoothing with κ = 200 by default, with κ sensitivity reported.
5. Admissible domain: θ₀ > 2/τ_max by default; any run with a rate at a bound is flagged as a corner solution and excluded from rankings.

### Paper change
Footnote 20: name both equilibrium concepts, state that the displayed formula holds for (a), and state that rankings are reported only where the two concepts agree.

---

## 2. Network measures

### Problem
Escape capacity uses the row-normalised matrix P (footnote 22) while round-trip capacity uses the adjacency matrix A (footnote 25). With A, convergence requires α < 1/λₘₐₓ(A), and the two measures are not comparable, contrary to Part 7.5. Footnote 25 cites Estrada and Rodríguez-Velázquez for the resolvent form, but their subgraph centrality uses the matrix exponential (confirmed; see section 11). Ordinary reciprocal trade forms directed 2-cycles.

### First proposal and why it failed
The first proposal measured round-tripping as **excess** Zᵢ over a null model preserving each jurisdiction's in- and out-flows, with Helmholtz–Hodge decomposition as a cross-check. Tested on a 4-jurisdiction network with symmetric reciprocal trade:

| Scenario | Change in Z₀ from baseline | Excess Z₀ over null | Helmholtz–Hodge circular share |
|---|---|---|---|
| Round trip through one conduit (0→1→0) | +0.0210 | +0.0033 | 0.000 |
| Round trip through two conduits (0→1→2→0) | +0.0105 | **−0.0048** | 1.000 |
| Genuine migration of the same volume | +0.0015 | 0.0000 | 0.000 |

- The null-model excess is **negative** for a three-step round trip, because a null that preserves flow totals reproduces much of the cycle. It cannot serve as a detector.
- Helmholtz–Hodge decomposition operates on net flows, so it is **blind to round trips through a single conduit**, which are the most common form in the FDI literature. It detects longer cycles well.
- The change in Zᵢ from a pre-shock baseline detects both forms and separates them from migration.

### Resolution
1. One matrix for all measures: Pᵢⱼ = Fᵢⱼ / (Dᵢ + Σₖ Fᵢₖ), with Fᵢⱼ cross-border flow, Dᵢ domestic volume, and a zero diagonal. Rows are substochastic, so any α in (0, 1) converges (verified: resolvent equals its power series to 10⁻¹⁶).
2. M = (I − αP)⁻¹. Escape capacity from off-diagonals (footnote 22 unchanged in substance); round-trip capacity Zᵢ = Mᵢᵢ − 1.
3. Round-tripping is measured **as a change from a baseline period**, never as a level. Levels of Zᵢ are reported only as descriptive structure.
4. The primary round-trip statistic is the return ratio (section 6). Zᵢ is secondary, because it is small in magnitude when the responding base is small relative to the total.
5. Helmholtz–Hodge decomposition is retained as a supplementary diagnostic for multi-conduit cycles only, with its blindness to two-step round trips stated.
6. Citations (verified 9 October 2026; see section 11):
   - Katz (1953) for the resolvent and discounted walks of every length.
   - Ernesto Estrada and Desmond J Higham, 'Network Properties Revealed through Matrix Functions' (2010) 52(4) SIAM Review 696, for a centrality built from the diagonal of the resolvent, which the authors call "resolvent centrality" (s 3, eqns (11) and (12)). Their version is defined on an undirected adjacency matrix with the parameter fixed at 1/(N − 1). The measure here applies the same construction to the directed, substochastic matrix P with a free α, so it is an adaptation and should be cited with "cf." or "adapting".
   - Ernesto Estrada and Juan A Rodríguez-Velázquez, 'Subgraph Centrality in Complex Networks' (2005) 71 Physical Review E 056103 is correctly cited bibliographically, but its subgraph centrality weights closed walks of length k by 1/k! (eqn (2)), which is the diagonal of the matrix exponential, not the resolvent. It may be retained only for the general idea of scoring a node by its closed walks, introduced with "cf.", and not as the source of the formula.

### Paper change
Footnote 25 rewritten on P. Suggested citation wording: "Discounted round-trip capacity is Zᵢ = [(I − αP)⁻¹]ᵢᵢ − 1, the diagonal analogue of the Katz resolvent in n 22; cf. the resolvent centrality of Ernesto Estrada and Desmond J Higham, 'Network Properties Revealed through Matrix Functions' (2010) 52 SIAM Review 696, 702–03, adapted here to a directed flow matrix, and the exponential-weighted subgraph centrality of Ernesto Estrada and Juan A Rodríguez-Velázquez, 'Subgraph Centrality in Complex Networks' (2005) 71 Physical Review E 056103." The pinpoint 702–03 is a placeholder: confirm the page on which section 3 falls in the published version. Part 7.5 states that round-trip capacity is read as a change from a baseline, and that two-step round trips are indistinguishable from reciprocal trade in levels.

---

## 3. Definitions of the base

### Resolution
- Claim set: Cᵢ = {h : i ∈ r(h)}, everything jurisdiction i may tax.
- Exclusive base: Bᵢ = {h : r(h) = {i}}.
- Overlap: O = {h : |r(h)| > 1}. Gap: G = {h : r(h) = ∅}.
- Under a partition, Cᵢ = Bᵢ (footnote 12's case).

### Paper change
Footnote 12 uses Bᵢ only under the partition assumption; footnote 13 uses Cᵢ.

---

## 4. Shares when the rule is not a partition

### First proposal and why it failed
The first proposal set the attractiveness of an untaxed outside option to γ · gᵣ, where gᵣ was the observed fraction of unassigned holdings, and weighted overlap by each jurisdiction's observed share of overlapping claims. Both inputs are equilibrium outcomes, so the specification was **circular**.

### Resolution: option-level logit
- A holder chooses an **option** k = (economic location j, configuration c). Configurations include at least custodial and self-hosted; the synthetic world may add multi-signature and others.
- The rule maps each option to an ordered claim set r(j, c): empty (gap), one claimant, or several (overlap). Gap and overlap shares are therefore **outputs** of the model.
- Utility of option k: ln(aⱼ · w_c) − θⱼ · bₖ, where bₖ is the tax burden on the option and θ attaches to the economic location j.
- **Burden and revenue under overlap**, with primary claimant p and secondary s (primary = the claimant assigning on the more observable predicate):
  - burden: τₚ + (1 − ρ)τₛ + ρ · max(0, τₛ − τₚ);
  - revenue: p collects τₚ; s collects (1 − ρ)τₛ + ρ · max(0, τₛ − τₚ).
  - ρ = 1 is full credit relief (burden equals the higher rate); ρ = 0 is unrelieved double taxation.
- **Burden under gap**: φ · τ_res(j), the residence jurisdiction's rate scaled by φ, the effectiveness of residence taxation over unassigned holdings (see section 5). φ = 0 is the paper's implicit assumption.
- Equilibrium rates by numerical best response on each jurisdiction's total revenue.
- Indeterminacy stays outside the share model and is recorded as a separate dispute-cost measure (Part 5.4).

### Tests and results
- With a partition, the numerical equilibrium reproduces the paper's formula τᵢ* = 1/[θᵢ(1 − sᵢ)] exactly (error 0).
- With a gap and φ = 0, the formula holds exactly using the taxed option's share. The gap acts as a zero-rate competitor in the same functional form.
- The gap's effect is large: in the test world, the unassigned option absorbs 67% of the base in equilibrium and mean sustainable rates fall from about 0.47 to 0.36.

### Paper change
Part 7.6: a paragraph introducing the option-level choice, the relief parameter ρ and the residence-backstop parameter φ, and noting that the displayed formula is the partition special case.

---

## 5. Proposition 3

### First proposal and why it failed
The first proposal restated Proposition 3 as holding whenever treaty relief efficiency ρ exceeds a threshold. Testing showed two problems.

1. **Revenue rewards double taxation.** An exhaustive but non-exclusive rule collected more revenue than a partition even with full credit relief, because credit relief makes the burden the higher of two rates and so softens competition. Ranking rules by revenue would favour overlap for reasons unrelated to the paper's argument.
2. **The remedy for gap was missing.** In practice an asset outside every source rule may still be taxed by the holder's residence jurisdiction. The paper's model implicitly sets that backstop to zero.

### Revised test
Matched pair in a 4-jurisdiction world: rule X (exclusive, not exhaustive: self-hosted holdings unassigned) and rule Y (exhaustive, not exclusive: self-hosted holdings claimed by two jurisdictions). Costs measured separately rather than through revenue:
- **gap cost** = revenue lost relative to a partition;
- **overlap cost** = unrelieved double-tax burden borne by taxpayers.

| φ (residence backstop) | Gap cost | Gap worse than overlap at ρ = 0 / 0.5 / 0.9? |
|---|---|---|
| 0.00 | 0.327 | yes / yes / yes |
| 0.25 | 0.185 | yes / yes / yes |
| 0.50 | 0.063 | no / yes / yes |
| 0.75 | 0.012 | no / no / no |
| 0.90 | 0.002 | no / no / no |

### Resolution
Proposition 3 is restated as a **condition in (φ, ρ) space**: the gap is the costlier failure where residence enforcement over unassigned holdings is weak relative to treaty relief over overlapping ones. The tool computes the boundary for each world and reports where the paper's claim holds.

This restatement suits the paper's argument well. The holdings left unassigned by intermediary location are self-hosted holdings, which are precisely those a residence jurisdiction cannot observe (Parts 5.2 and 9), so φ is low for exactly the segment in question. The proposition then rests on an empirical claim about φ that the paper already defends, rather than on an assertion.

Revenue is reported, but never used alone to rank rules, and the competition-softening effect of credit relief is reported as a separate finding.

### Paper change
Proposition 3 restated conditionally on φ and ρ; Part 5.5 acknowledges the residence backstop and explains why it is weak for self-hosted holdings.

---

## 6. Proposition 2: holder behaviour and the observable signature

### Problem found in the paper
Part 7.5 says round-tripping "leav[es] the distribution of shares broadly unchanged". That is true of **economic** location but not of **assigned** location. When a holder moves a key, the assignment moves with it, so the assigned base leaves the jurisdiction under both responses. Only assigned shares are observable, so the signature as stated cannot be measured.

### Resolution: holder choice
After a rate change, each holding chooses (random-utility logit) among:
- **stay**;
- **migrate**: move economic activity and the predicate, cost c_M;
- **restructure**: move only the predicate, cost c_R, set by predicate type.

| Rule | Predicate | c_R |
|---|---|---|
| Control, enclosure | Movable (key relocation) | Low |
| Intermediary, registration | Institutional | Close to c_M |
| Owner-residence | Personal | High; lowered by nominee and entity structures |
| Validation | Outside the holder's control | Not available |

### Resolution: the return ratio
Both responses move assigned base out of jurisdiction i. They differ in whether that base keeps transacting with counterparties in i. The primary signature is:

> **return ratio** = (increase in flows from destination jurisdictions back to i) ÷ (assigned base lost by i)

### Tests and results (4,000 holdings; 30% of jurisdiction 0's holdings leave)

| True restructured share of leavers | Return ratio (migrants cut all ties) | Return ratio (30% of migrants keep ties) | Change in Z₀ |
|---|---|---|---|
| 0.00 | 0.000 | 0.245 | +0.0000 |
| 0.25 | 0.281 | 0.462 | +0.0003 |
| 0.50 | 0.467 | 0.630 | +0.0006 |
| 0.75 | 0.734 | 0.812 | +0.0017 |
| 1.00 | 1.000 | 1.000 | +0.0036 |

- The return ratio recovers the true restructured share almost exactly when migrants cut ties.
- When some migrants keep ties to their origin (legacy rate ℓ), the ratio is biased upwards by ℓ(1 − share). The correction is: estimated share = (ratio − ℓ) / (1 − ℓ).
- ℓ is estimated from a placebo: the return ratio among leavers under an institutional-predicate rule (where restructuring is not available) or in periods with no tax change.
- The change in Zᵢ moves in the right direction but is two orders of magnitude smaller and convex in the share, so it is unreliable with real noise. It is reported as secondary.

This also addresses the paper's concession that its measurement strategy "has not been validated": the synthetic test shows the return ratio is identified, given an estimate of ℓ.

### Paper change
Part 7.5: replace the claim that round-tripping leaves shares unchanged with the return-ratio signature; Part 10.2: report the synthetic validation and the placebo strategy for ℓ.

---

## 7. Proposition 1 (found during testing)

### Problem
Proposition 1 says consequences are determined by the induced network and not by doctrinal pedigree. But Part 7.6 says a rule enters the model at two points: the network **and** the distribution of the base. The equilibrium depends on both (τᵢ* depends on sᵢ). Two rules inducing the same network but different base distributions yield different equilibria, which would falsify Proposition 1 as worded although the paper's own model predicts it.

### Resolution
Restate: the consequences of an assignment rule are determined by the network **and** base distribution it induces. The tool tests Proposition 1 by comparing pairs of rules on both induced objects and on outcomes.

---

## 8. Parameters

| Symbol | Meaning | Default | Swept range |
|---|---|---|---|
| θ₀ | Baseline semi-elasticity | 3 | 2.5 to 6 (interior domain) |
| β | Weight of escape capacity | 3 | 0 to 6 |
| α | Per-step discount in the resolvent | 0.6 | 0.3 to 0.9 |
| κ | Softplus steepness | 200 | 50 to 1,000 |
| ρ | Treaty relief efficiency on overlap | 0.75 | 0 to 1 |
| φ | Residence enforcement on unassigned holdings | 0.1 | 0 to 1 |
| w_c | Non-tax attractiveness of configuration c | from world | ± 50% |
| c_M, c_R | Migration and restructuring costs | by predicate type | ± 50% |
| ℓ | Legacy-tie rate of migrants | estimated | 0 to 0.5 |

All results are reported as rankings across the swept ranges, consistent with Part 7.1.

---

## 9. Acceptance tests for the build

Each test below passed during this specification exercise and becomes a unit or integration test in the build.

1. Resolvent equals its power series (tolerance 10⁻¹²).
2. Partition rule reproduces τᵢ* = 1/[θᵢ(1 − sᵢ)] (tolerance 10⁻⁶).
3. Gap rule with φ = 0 reproduces the formula with the taxed option's share.
4. Elasticity-consistent equilibrium is unique across 10 random starts.
5. Rule rankings are declared only where (a) and (b) agree.
6. Round trips through one and two conduits raise Zᵢ from baseline; migration raises it by less than a fifth as much.
7. Return ratio recovers the restructured share within 0.05 when ℓ = 0, and within 0.05 after correction when ℓ is known.
8. Corner solutions are flagged and excluded from rankings.

---

## 10. Remaining open points (not fatal)

- **Synthetic world calibration.** The configuration weights and costs are assumptions. Results are conditional on them and are reported as such.
- **Primary-claimant rule under overlap.** Observability is a proxy for the tie-breaker; alternatives should be tested as robustness.
- **φ in practice.** The restated Proposition 3 rests on φ being low for self-hosted holdings. The paper argues this; the companion piece should support it with sources on residence-based enforcement over self-custodied assets.
- **Pinpoint for Estrada and Higham (2010).** The section and equation numbers are confirmed; the page number for section 3 in the published version still needs confirming (section 11).

---

## 11. Citation verification log

### Entry: 9 October 2026, section 2 (network measures)

| Citation | Status | Detail | Source checked |
|---|---|---|---|
| Ernesto Estrada and Desmond J Higham, 'Network Properties Revealed through Matrix Functions' (2010) 52(4) SIAM Review 696–714, DOI 10.1137/090761070 | Verified | Authors, title, journal, volume, issue, pages, year and DOI confirmed from the copy on Higham's university page and the DOI record. Section 3 defines "resolvent centrality" from the diagonal of the resolvent, for undirected graphs with parameter 1/(N − 1). | Author's copy (University of Edinburgh); SIAM DOI record; University of Strathclyde repository |
| Ernesto Estrada and Juan A Rodríguez-Velázquez, 'Subgraph Centrality in Complex Networks' (2005) 71 Physical Review E 056103, DOI 10.1103/PhysRevE.71.056103 | Verified (bibliography); **misattributed in the paper** | Citation details correct. Eqn (2) defines subgraph centrality with 1/k! weights (matrix exponential), not the resolvent used in footnote 25. | arXiv preprint cond-mat/0504730; APS DOI record |
| Pinpoint page for section 3 of Estrada and Higham | Unconfirmed detail | The publisher page could not be fetched (access refused); the page on which section 3 begins should be read from the published PDF. | Not resolved |

Running tally: 2 citations checked; 0 fabricated; 1 misattribution in the paper (corrected above); 1 detail unconfirmed.
