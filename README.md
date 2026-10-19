# JAF Rule Bench

A research tool accompanying the paper *Jurisdictional Assignment Functions* (SSRN 7351160). It models how the rule for deciding which state may tax a digital-asset holding (the assignment rule) affects how much tax can be collected, and how often holdings end up untaxed or taxed twice.

> **Status: version 1.0.** A validation-ready instrument: it can estimate the model's behavioural settings from observed facts and test its predictions, with every method proven on synthetic data first. It contains **no results about real countries**; those belong to a later empirical piece. Cite a specific release, not this repository's main branch. Results from the invented example describe no real country.

## What it does

- **Rule comparison (synthetic world).** Seven candidate assignment rules applied in turn to an invented world of six competing states, under two equilibrium concepts, with robustness reruns.
- **Real-world sample (coded world).** Each jurisdiction applies its own rule, coded in an Excel template in three layers: liability (what it taxes on), collection (who collects) and observation (what its authority can see, including CARF or DAC8 exchange of information). Exchanges may operate in one state and be incorporated in another; treaty relief is coded by pair and direction.
- **Mismatch map.** For every pair of states, which may tax a holding. It needs no economic assumptions: it is the coded law run through the paper's assignment logic.
- **What-if analysis.** Change one state's rule and see the effect on every state.
- **Test against data (new in 1.0).** Describe versions of the law to compare (a single reform such as India 2022, or successive waves of automatic exchange of information such as CARF), the facts observed under each and their margins of error. The tool checks whether the facts can pin the model's settings down, proves its estimator on data it generates itself, estimates the settings, predicts facts held back, and freezes the design for pre-registration.
- **Two reading modes.** Plain English for readers without quantitative training; Technical for economists. Every chart exports as PNG, SVG or CSV.

## Getting started

### Windows (no installation)
Download `JAF_Rule_Bench.exe` from the [Releases](../../releases) page and double-click it. The interface opens in your web browser and runs entirely on your computer. The program is unsigned, so Windows may warn that it is unrecognised: choose "More info", then "Run anyway".

### From source (any system)
Requires Python 3.10 or later.

```
pip install -r requirements.txt
python main.py
```

### Coding real jurisdictions
Start from `templates/JAF_template_real_sample_BLANK.xlsx`. Fill one row per jurisdiction, cite a source for each row (OSCOLA), mark rows verified once checked, and upload the file on the *Real-world sample* tab. To test the model against data, fill the Episodes, Data, Measurement, Estimation and Hypotheses sheets too (see `docs/USER_GUIDE.md`, section 6). `templates/JAF_template_illustrative_INVENTED_STATES.xlsx` is a completed example using invented states and synthetic data; its rows are not anyone's law and its values are not observations.

## Tests

```
PYTHONPATH=. python tests/test_acceptance.py
```

The suite (35 tests) checks, among other things, that the mixed-regime engine reproduces the single-rule engine exactly when every state applies the same rule, that the estimator recovers known settings from synthetic data, and that identification failures and departures from a pre-registered design are detected. It takes a few minutes.

## Documentation

- `docs/USER_GUIDE.md`: how to use the tool, for lawyers and economists, including how to convert statutory rates into effective rates and the workflow for testing the model against data.
- `docs/model_specification.md`: the model specification (Part B: the model as implemented in 1.0; Part A: the design decisions of 0.2).
- `docs/build_plan.md`: build history, the logical checks run before each build, the flaws found and how each was resolved, and the modelling assumptions with their limits.
- `docs/real_data_roadmap.md`: the plan for real-world data and the comparison of large economies.
- `docs/BUILDING.md`: how the Windows executable is built.

## Key modelling assumptions

- Holders choose among holding options under a mixed logit model; states set rates that maximise their revenue given the others' rates.
- A holding is kept in one place, except that an exchange may operate in one state and be incorporated in another. Registration follows the place of incorporation; infrastructure, key control and validation follow the place of operation.
- Where several states claim the same holding, the state where the exchange operates taxes first, then the state of incorporation, then residence, then citizenship; later claimants give relief at the coded rate.

- Estimation weights each observed fact by its stated margin of error; reported uncertainty reflects those margins, not doubt about the model, which is what the predictions test checks.

See `docs/build_plan.md`, sections 12 to 14, and `docs/model_specification.md`, section B16, for the full list and the limitations each brings.

## How to cite

Cite the archived version used, with its DOI (each version is deposited on Zenodo):

> Wen Yi LEONG, *JAF Rule Bench* (version 1.0.0, 2026) <https://doi.org/[DOI]>

GitHub's "Cite this repository" button (from `CITATION.cff`) gives other formats.

## Development and AI assistance

The code and documentation were developed with the assistance of Claude, an AI system made by Anthropic, under the author's direction. The author specified the model, reviewed the logic and results, and is responsible for the content.

## Licence

Not yet decided. Until a licence is added, all rights are reserved by the author: the code may be read and run for review, but not redistributed or adapted. See `LICENCE_TO_CHOOSE.md`.

Bundled components keep their own licences. The Windows executable includes third-party components (CPython, NumPy, openpyxl, et_xmlfile, the PyInstaller bootloader and the Microsoft Visual C++ runtime), each of which remains under its own licence; their notices and licence texts are reproduced in full in `THIRD_PARTY_NOTICES.txt`, which is shipped with every release. The licence of JAF Rule Bench, once chosen, covers only its own code and documents. The source code in this repository does not include those components: NumPy and openpyxl are installed separately (`requirements.txt`) under their own licences (BSD-3-Clause and MIT).

Copyright © 2026 Wen Yi LEONG.
