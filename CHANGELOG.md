# Changelog

Full reasoning for each change, including the logical checks and flaws found, is in `docs/build_plan.md`.

## 1.0.0 (2026-10-18)
Version 1.0 is a validation-ready instrument: it can test the model against data, with every method proven on synthetic data first. It contains no results about real countries.
- New "Test against data" tab, supporting single-reform designs (such as India 2022) and staggered adoption of information exchange (such as the CARF waves).
- Data layer: Episodes, Data, Measurement, Estimation and Hypotheses sheets in the template, with provenance, quality grades and validation.
- Measurement model for exchange volume (by place of operation or incorporation, adjusted for wash trading and turnover) and holdings.
- Estimation by simulated minimum distance with standard errors from stated measurement error; identification diagnostics run first, and estimation is refused when a parameter cannot be pinned down.
- Known-truth recovery tests; out-of-sample validation with prediction bands; fingerprinted pre-registration with a check for departures.
- Rates that cycle between near-equal revenue maxima are accepted as an epsilon-equilibrium and the forgone gain reported.
- Specification rewritten for the current model (Part B); new user guide; template guidance corrected.
- Workbooks from 0.4 load unchanged.

## 0.4.0 (2026-10-16)
- Exchanges may operate in one state and be incorporated in another; each intermediary-based state codes its own location test (incorporation or operations).
- Treaty relief coded by pair and direction (new Treaties sheet).
- Mismatch map shows each kind of exchange as a column; what-if can switch a state's location test.
- Templates from 0.3 still load, with warnings and defaults.

## 0.3.0 (2026-10-10)
- Mixed regimes: each jurisdiction applies its own rule (liability, collection, observation).
- Excel coding template with validation and provenance; mismatch map; results by jurisdiction; what-if analysis.

## 0.2.0 (2026-10-09)
- Effective rate and yield replace nominal rates for ranking; mixed logit holders; six-way leakage decomposition; matched-pair test of Proposition 3; Windows executable; Plain English and Technical reading modes.
- Corrects the 0.1 headline, which ranked rules on nominal rates.

## 0.1.0
- First preview (web page only).
