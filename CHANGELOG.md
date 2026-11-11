# Changelog

Full reasoning for each change, including the logical checks and flaws found, is in `docs/build_plan.md`.

## 1.1.0 (2026-11-11)
- File manager ("Your files" tab), modelled on the A-share Company Intelligence data folder: one library for every export and import; previews; manifests with SHA-256 for every saved bundle; folders, rename, move and copy with a dry run; Trash with restore; undo of the last change; an activity log; packages (.jafpack) checked by hash for moving results between computers; moving or adopting the whole library (copy and verify, old folder untouched).
- A copy of every workbook and pre-registration record loaded is kept in Imports.
- The local engine accepts requests only at its own address, and changes only from its own interface.
- New program icon (also the interface's browser-tab icon) and Windows file properties.
- Built, tested (all acceptance tests) and smoke-tested on GitHub's Windows runners; tagged versions produce a draft release.
- Acceptance tests 41 to 50. The model is unchanged; results equal those of 1.0.

## 1.0.0 (2026-10-18, not published separately)
Version 1.0 is a validation-ready instrument: it can test the model against data, with every method proven on synthetic data first. It contains no results about real countries.
- New "Test against data" tab, supporting single-reform designs (such as India 2022) and staggered adoption of information exchange (such as the CARF waves).
- Data layer: Episodes, Data, Measurement, Estimation and Hypotheses sheets in the template, with provenance, quality grades and validation.
- Measurement model for exchange volume (by place of operation or incorporation, adjusted for wash trading and turnover) and holdings.
- Estimation by simulated minimum distance with standard errors from stated measurement error; identification diagnostics run first, and estimation is refused when a parameter cannot be pinned down.
- Known-truth recovery tests; out-of-sample validation with prediction bands; fingerprinted pre-registration with a check for departures.
- Rates that cycle between near-equal revenue maxima are accepted as an epsilon-equilibrium and the forgone gain reported.
- Specification rewritten for the current model (Part B); new user guide; template guidance corrected.
- Workbooks from 0.4 load unchanged.
- Licensed: code under the PolyForm Noncommercial License 1.0.0; documents, templates and data under CC BY-NC 4.0. Third-party notices for the components bundled in the Windows executable.

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
