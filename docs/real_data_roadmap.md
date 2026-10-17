# JAF Rule Bench: Roadmap to Real-World Data and Multi-Jurisdiction Comparison

*Advice note, 10 October 2026. Relates to the paper* Jurisdictional Assignment Functions *(SSRN 7351160) and JAF Rule Bench version 0.2 (preview). Companion to* jaf_tool_github_release_advice.md.

## Part A. Using real-world data

### A1. Where the tool stands

Nothing in version 0.2 is measured. The six states, their sizes, where holders sit and every behavioural parameter are invented or set by hand. Real data cannot simply be connected to it: a bridge is needed between the model's ingredients and things that can be observed. That bridge has three levels, and each is worth doing on its own.

### A2. Three levels of "real data"

| Level | What it means | What it yields | Difficulty |
|---|---|---|---|
| 1. Calibration | Replace the invented world with real jurisdictions, real tax rules and observed base shares; behavioural parameters still set by judgement | A "what if" model of the actual world (for example, what happens if country X moves from intermediary location to owner-residence) | Moderate; mostly legal coding plus a few datasets |
| 2. Estimation | Choose the behavioural parameters (how strongly holders react, how far escape routes reach) so that the model reproduces an episode that actually happened | Parameters grounded in evidence rather than assumption | Hard; needs econometrics |
| 3. Validation | Use the estimated model to predict an episode it was not fitted to, then compare | A tested model, the strongest claim available to the paper | Hard; depends on a second natural experiment |

### A3. Mapping model ingredients to sources

| Model ingredient | Possible source | Status |
|---|---|---|
| Tax rates and the assignment rule each country applies | National legislation and guidance, coded by hand | The author's comparative advantage. A coded dataset of assignment rules in force may be publishable in its own right. |
| Cross-border crypto flows (the network) | P Cardozo, A Fernández, J Jiang and FD Rojas, 'On Cross-Border Crypto Flows: Measurement, Drivers and Policy Implications' (IMF Working Paper No 2024/261); IMF Working Paper No 2025/141 on stablecoin flows | IMF staff working papers, **not peer reviewed** |
| Where trading sits (exchange domicile; custodial versus self-custody) | Commercial blockchain-analytics and market-data providers; public blockchain datasets, which lack exchange labels | Commercial, proprietary methods, **not peer reviewed**; usually paid or licensed |
| Holders' responsiveness to tax (θ) | Natural experiments. India's 2022 regime (30% tax plus 1% tax deducted at source): Esya Centre reported foreign exchanges' share of Indian trading rising from 50% (November 2021) to 67.6% (October 2022) | Think-tank report reported in the press, **not peer reviewed**, method not described in coverage; re-estimate from primary data before use |
| Observability | OECD Crypto-Asset Reporting Framework (CARF) and EU DAC8 apply from 1 January 2026; first reports on 2026 activity due in 2027 (about 46 jurisdictions), others in 2028 to 2029 | Timeline from an industry source (**not peer reviewed**); confirm against the OECD commitments list. Reported data are confidential; only published aggregates will be usable. |

### A4. Changes to the tool

1. **Data layer:** importers reading versioned data snapshots; every number carries its source and date.
2. **"World from data" mode:** real jurisdictions, base shares from volume data, and the transfer network from flow estimates replace the random world generator.
3. **Calibration and estimation module:** θ₀, β and σ chosen so the model reproduces observed facts (for example, the size of India's offshore shift), using the simulated method of moments.
4. **Validation tab:** predicted against observed for held-out episodes, with uncertainty bands.

### A5. Scraping

Mostly unnecessary. The research needs a small number of well-documented episodes and dated snapshots, not a live stream. Scraping is useful only for public legal sources (rate tables, published guidance). Exchanges' and data vendors' terms usually forbid scraping; APIs or licensed downloads are safer and easier to defend in peer review.

### A6. Suggested first project: India 2022 case study

India plus the main jurisdictions where offshore exchanges are domiciled; code the rules in force; fit the behavioural parameters to the observed offshore shift; check whether the model's leakage decomposition (migration, round-tripping, conduit switching) matches volume and flow data. If it works, a held-out episode (a rule change elsewhere, or the first CARF/DAC8 aggregates) becomes the validation test.

## Part B. Comparing multiple jurisdictions (large economies)

### B1. Required model change: mixed regimes

Version 0.2 applies **one rule to the whole world**. Real economies apply different rules at once, and most gaps and overlaps arise from **mismatches between rules** rather than from any single rule (for example, US citizenship-based taxation against UK residence-based taxation produces two claims on the same holder). The first development step is to let each jurisdiction carry its own rule, with gaps and overlaps computed from the interaction of rules. Without it, a real-world sample cannot be modelled faithfully.

### B2. Three layers of assignment

| Layer | Question | Example of variation |
|---|---|---|
| Liability | Who must pay tax on the holding? | Residence (most); citizenship (United States) |
| Collection | Who collects or withholds it? | Holder self-assesses; exchange deducts at source (India) |
| Observation | What can the authority see? | Self-assessment only; domestic exchange reporting; CARF/DAC8 exchange of information |

Among large economies the liability rule varies less than expected; most variation lies in collection and observation. Collection at the intermediary behaves much like the model's intermediary-location rule in practice, even where liability is residence-based.

### B3. Sample design principles

1. Cover the **variation in rules**, not merely the largest GDPs.
2. Include the **destinations**: low-tax hubs with large exchange presence, without which the escape routes are cut.
3. Align with the **CARF waves** (2027: EU-27, UK, Japan, Canada and others; 2028: hubs including Singapore, Hong Kong and the UAE; United States targeting 2029). Staggered adoption supports identification.
4. Prefer jurisdictions with data and official guidance in **English or Chinese**.

### B4. Candidate sample (illustrative)

Every row's current legal status must be verified before coding; crypto tax regimes change quickly.

| Jurisdiction | Reason for inclusion | Feature to code |
|---|---|---|
| United States | Largest market; distinctive liability rule | Citizenship plus residence liability; CARF targeted for 2029 |
| United Kingdom | Residence benchmark; first CARF wave | Residence-based capital gains treatment |
| Germany (or EU block) | DAC8 from 2026; distinctive holding-period treatment | Exemption for private disposals after a holding period (verify) |
| Japan | Large market; first CARF wave | Treatment of gains as miscellaneous income; reform proposals (verify) |
| South Korea | Large retail market | Crypto income tax repeatedly deferred (verify) |
| India | Natural experiment | 30% rate plus exchange-collected 1% tax deducted at source (2022) |
| Indonesia | Transaction-level tax collected by exchanges (verify details) | Collection at the intermediary |
| China (mainland) | Prohibition as a form of non-assignment | Trading ban (2021); offshore routing |
| Brazil | Large emerging market; covered by IMF flows work | Residence liability plus exchange reporting (verify) |
| Singapore, UAE, Hong Kong | Destinations and hubs; second CARF wave | Low or no tax on individuals' gains; large exchange presence |

About ten economies and three hubs, plus a "rest of world" node to absorb residual flows.

### B5. What the comparison can deliver

1. **Calibrated counterfactuals:** change one jurisdiction's rule, hold the rest at their real settings, and trace where base moves.
2. **Staggered-reform event studies:** India (2022), DAC8 (2026), CARF waves (2027, 2028, 2029), analysed by difference-in-differences.
3. **Mismatch matrix:** for every pair of jurisdictions, where their rules produce overlaps or gaps. This needs no behavioural estimation, only legal coding run through the model's assignment logic, and could stand as a figure in the paper.

### B6. Changes to the tool

- Named jurisdictions with a variable count.
- Per-jurisdiction settings across the three layers, read from a coding template (a spreadsheet completed by the author).
- A mismatch-matrix view and a "change one country's rule" counterfactual control.
- Each coded rule carries "in force from / until" dates; every input carries its source.

### B7. Cautions

- Hubs publish the least data yet receive the base; their figures will rest most on commercial estimates (**not peer reviewed**).
- Holders' residence is rarely observed; exchange volume by domicile is a crude proxy. Wash trading distorts volumes, and an exchange's operational base often differs from its legal seat.
- A sample of large economies is not random; results describe the group chosen, and the paper should justify the choice.
- One natural experiment identifies little; some parameters will remain judgement calls, to be stated openly.
- Level 2 (estimation) benefits from an economist co-author or reviewer for credibility in economics or tax-policy journals.

## Part C. Recommended order of work

| Step | Who | Action |
|---|---|---|
| 1 | Claude | Build the mixed-regime extension, the three-layer coding template and the data layer with provenance |
| 2 | Author | Code the sample's rules (liability, collection, observation; with dates and sources) |
| 3 | Claude | Produce the mismatch matrix (no estimation needed) |
| 4 | Both | India 2022 case study: calibrate, then fit θ₀, β and σ to the observed offshore shift |
| 5 | Both | Counterfactuals and staggered-reform event studies; validation on a held-out episode |

## Sources

- P Cardozo, A Fernández, J Jiang and FD Rojas, 'On Cross-Border Crypto Flows: Measurement, Drivers and Policy Implications' (IMF Working Paper No 2024/261, 2024) <https://www.imf.org/en/publications/wp/issues/2024/12/20/on-cross-border-crypto-flows-measurement-drivers-and-policy-implications-559166> (working paper; not peer reviewed)
- 'Decrypting Crypto: How to Estimate International Stablecoin Flows' (IMF Working Paper No 2025/141, 2025) <https://www.imf.org/en/publications/wp/issues/2025/07/11/decrypting-crypto-how-to-estimate-international-stablecoin-flows-568260> (working paper; not peer reviewed)
- TechCrunch report on the Esya Centre study of India's crypto tax (3 January 2023) <https://techcrunch.com/2023/01/03/india-crypto-tax-pushing-traders-to-foreign-exchanges> (news report of a think-tank study; not peer reviewed; author and exact title to be confirmed, and the Esya Centre report itself should be cited once obtained)
- 'The CARF deadline crypto firms cannot afford to miss' (FinTech Global, 14 August 2026) <https://fintech.global/2026/08/14/the-carf-deadline-crypto-firms-cannot-afford-to-miss/> (industry article; not peer reviewed)
- OECD Global Forum, 'Jurisdictions committed to implement the Crypto-Asset Reporting Framework' <https://www.oecd.org/content/dam/oecd/en/networks/global-forum-tax-transparency/commitments-carf.pdf> (authoritative list; not opened during preparation of this note, to be checked)
