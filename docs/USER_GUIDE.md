# JAF Rule Bench: User Guide

*Version 1.0. For readers with legal training and for economists. Every screen has a Plain English and a Technical reading mode (top right); this guide follows the Plain English labels and gives the technical term in brackets where it helps.*

## 1. What the tool is for

The tool accompanies the paper *Jurisdictional Assignment Functions* (SSRN 7351160). The paper asks how the rule that decides which state may tax a digital-asset holding (the assignment rule) affects how much tax can be collected, and how often holdings end up untaxed or taxed twice. The tool does three things:

1. **Compares assignment rules in an invented world.** Six invented states apply one rule at a time, compete on tax rates, and holders respond. This illustrates the paper's propositions.
2. **Runs a coded world.** Each jurisdiction applies its own rule, coded in an Excel template with sources. The mismatch map shows, from the coded law alone, which states may tax which holdings.
3. **Tests the model against data (new in 1.0).** It estimates the model's behavioural settings from observed facts, checks first whether those facts can pin the settings down, proves the method on data it generates itself, and tests the model by predicting facts it was not shown.

Version 1.0 contains **no results about real countries**. It is the instrument, proven on invented states and synthetic data. Real-world results belong to a later empirical piece that codes real law, gathers data, pre-registers its design and then uses the tool.

## 2. Starting the tool

- **Windows:** download `JAF_Rule_Bench.exe` from the Releases page and double-click it. A small window opens (the engine) and the interface opens in your browser. Everything runs on your computer; nothing is sent over the internet. Close the window, or press Quit, to stop. The program is unsigned, so Windows may warn that it is unrecognised: choose "More info", then "Run anyway".
- **Any system, from source:** install Python 3.10 or later, then run `pip install -r requirements.txt` and `python main.py`.

Saved results go to a "JAF Rule Bench" folder in your Documents. The tool remembers the last world and results between sessions.

## 3. A tour of the tabs

| Tab (Plain English) | What it shows |
|---|---|
| Overview | The main comparison of rules in the invented world, and where to start |
| Real-world sample | Loading a coded world; the coded rules; the mismatch map; results by jurisdiction; what-if changes |
| Test against data | Episodes, observed facts, identification check, estimation, predictions, recovery test, pre-registration |
| Tax each rule sustains, Cross-border picture, Where the base goes, Untaxed or double-taxed?, What authorities can see, Why rules differ, How robust? | The paper's analyses on the invented world |
| Chart builder | Your own charts from the results |
| Findings register | Model outputs that hold across robustness reruns, and draft hypotheses |
| Guide and glossary | Every term, in plain and technical form |

Every chart exports as PNG or SVG (for print) and its data as CSV. Each chart has a "What this chart tells you" box: what it shows, how to read it, why it matters.

## 4. Coding jurisdictions

Download the blank template from the Real-world sample tab (or use `templates/JAF_template_real_sample_BLANK.xlsx`). The completed example with invented states shows every sheet filled in.

**Jurisdictions sheet.** One row per jurisdiction: the liability rule (which connecting factor it taxes on), how it locates an exchange if it taxes by intermediary location (legal seat or operational base), who collects (holder or domestic exchanges), whether domestic exchanges are permitted, what its authority can see, when it starts automatic exchange of information, any top-up on residents' untaxed holdings, and the rate. Include low-tax hubs and a "rest of world" row.

**Personal links** (dual residence, citizenship), **Treaties** (relief by pair and direction) and **Settings** (scenario year, defaults).

For every row: cite the source in OSCOLA form, and set Verified to yes only once you have checked it against the source. The tool runs with unverified rows but labels every result that depends on them.

## 5. From statutory to effective rates

The model uses the **effective rate on the return from holdings**: the tax actually borne, as a share of the pre-tax return, over a typical holding. It is often not the headline rate. A method:

1. **Start from the statutory rate** t on gains (or income) from the asset class.
2. **Deferral.** If gains are taxed only on realisation and a holding is typically kept for H years with annual return r, the accrual-equivalent effective rate is

       t_eff = 1 − [((1 + r)^H (1 − t) + t)^(1/H) − 1] / r.

   Example: t = 30%, r = 10%, H = 3 gives about 28.1%; with H = 10, about 22.2%.
3. **Exemptions and allowances.** If gains are exempt after a holding period, or an annual allowance applies, weight the rate by the share of returns that remain taxable.
4. **No loss relief.** If losses cannot be set off against gains (an asymmetric tax), the effective rate on the expected return is higher than t: it is t × E[taxable gains] / E[net return]. Where returns are volatile, the ratio can be large; state your assumption about the spread of returns.
5. **Transaction taxes.** A tax on the value of each transfer that is not credited against the final liability is equivalent to a rate of (tax per transfer × transfers per year × value) / annual return. A withholding on transfers that is credited against the final liability (for example a tax deducted at source) mainly affects visibility and cash flow; code it through "Collection" rather than the rate.
6. **Record the conversion** and its assumptions in Notes, so that a reader can recompute it.

**Example of what to look for (to be verified by the coder).** India's regime from 2022 taxes income from transfers of virtual digital assets at 30% with no deduction other than cost of acquisition and no set-off of losses (Income-tax Act 1961, s 115BBH), and requires 1% tax to be deducted at source on transfers (s 194S), both inserted by the Finance Act 2022. Step 4 (no loss relief) raises the effective rate above 30% on volatile returns; the deduction at source is credited against the final liability, so it is coded as collection by domestic exchanges rather than as an addition to the rate.

## 6. Testing the model against data

### 6.1 The two designs the tool supports

- **A single reform.** One episode changes one state's law (for example India's 2022 regime: a higher effective rate and collection by domestic exchanges). Facts are measured before and after: for example, the share of residents' exchange trading on domestic exchanges, as a ratio after / before.
- **Staggered adoption of information exchange.** One episode per wave of states starting automatic exchange of crypto-asset information under the OECD Crypto-Asset Reporting Framework (CARF), or under DAC8 in the European Union (Council Directive (EU) 2023/2226). Each episode sets the scenario year (and, if needed, a state's first year of exchange). Facts are measured as each wave takes effect: for example, the share of residents' trading on foreign exchanges outside the reporting net.

Both designs can be combined in one workbook. Use some facts to fit the model (targets) and keep others back to test it (holdouts). A good holdout is a fact from a different episode or state than the targets, for example a later wave.

### 6.2 Filling the data sheets

The template's sheets **Episodes**, **Data**, **Measurement**, **Estimation** and **Hypotheses** hold the design. The **Quantities** sheet lists what can be observed, what each measures, and whether data record it as trading volume or as holdings.

- **Episodes:** one row per change: episode name, jurisdiction code (or "settings"), field and new value.
- **Data:** one row per fact: ID, quantity, jurisdiction, episode, the episode it is compared with (for a change) and whether as a ratio or a difference, the value, its **standard error** (how far it could be off, in the same units), its role (target or holdout), source, quality (A official or audited; B reputable estimate; C indicative) and verification.
- **Measurement:** for exchange data, the share of reported volume that is wash trading at exchanges based in each place, and genuine turnover relative to elsewhere (1 if unknown).
- **Estimation:** which settings to estimate (with a start value and bounds) and which to fix by judgement (with a value and, optionally, a plausible range).
- **Hypotheses:** the claims to be tested, and which facts would support or refute each.

**Standard errors.** If a source gives a confidence interval, the standard error is about a quarter of its width. If not, judge it and say so in Notes: the fit weights each fact by it, so an over-precise figure dominates the estimate.

### 6.3 The workflow, in order

1. **Code the law and the design, leaving values blank.**
2. **Check the facts can pin the settings down** (identification). If a setting is not pinned down, fix it by judgement or add facts that respond to it. A grid shows how strongly each fact responds to each setting; two settings that move the facts in the same pattern cannot be told apart.
3. **Prove the method on known settings** (recovery test). The tool invents values from settings it knows and checks it can find them again. Do not proceed if it fails.
4. **Freeze the design** (pre-registration) and download the document and record. **Deposit the document with an independent registry (for example OSF) before collecting values.** The deposit, not the tool, establishes the date.
5. **Collect the values**, enter them, and reload the workbook. Load the frozen record so the tool can check the design against it.
6. **Estimate and test predictions.** Read the estimates with their ranges, the fit, and above all the predictions for the facts kept back.
7. **Report** every departure from the frozen design, with reasons. The tool lists them.

### 6.4 Reading the results

- **Estimated settings** come with a likely error (standard error) and a range consistent with the data. These reflect the stated margins of error of the facts only, not doubt about whether the model is right.
- **Fit**: each fact's distance from the model in margins of error. A setting "at its limit" is set by the bound, not the data.
- **Predictions**: a prediction is consistent with the data if the observed value lies within the combined margin. Several inconsistent predictions count against the model, or against how the law was coded; check the coding first.
- **What the tool cannot tell you**: whether the coded law is right (that is the coder's responsibility), whether adjustment was complete within the measurement window, or who in practice bears a tax collected by withholding.

### 6.5 Trying it on the invented example

On the Test against data tab, choose "Use the invented example with synthetic data". Its facts were generated from known settings (how strongly holders react to tax rates, 3.4; ease of using a foreign exchange, 0.55) with random error added. Run the three steps: the identification check passes; the recovery test passes; estimation should land close to the known settings, and the three predictions should be consistent. Note that in this example how much escape routes add to holders' reaction (β) cannot be separated from how strongly they react (θ₀), so it is fixed by judgement: the identification check shows why.

## 7. Troubleshooting

| Problem | What to do |
|---|---|
| The browser does not open | Open the address shown in the engine window (for example http://127.0.0.1:8765/) |
| "The template could not be loaded" | Fix the listed problems; each names the sheet, row and field |
| Estimation refused | A setting cannot be pinned down by the facts: fix it, or add facts. Override only to explore |
| "Rates did not settle" | The tool reports how much revenue any state forgoes at the final rates; below about 0.1%, results are usable |
| Estimation is slow | Each step re-solves every episode many times. Reduce the number of search starts, estimated settings or episodes |
| Results from an earlier version | Results saved by an earlier version are discarded on start; re-run |

## 8. Citing the tool

Cite the archived release you used, with its DOI (see the README). Results from the invented example must be described as such and must not be presented as describing real countries.
