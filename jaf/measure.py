# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Wen Yi LEONG
"""Measurement model (build plan s 14, component B2).

Data never record the model's quantities directly. Exchange statistics are recorded by where an exchange
operates or is incorporated, as trading volume rather than holdings, and include wash trading. This module
defines each measurable quantity as the model-implied value of what the data actually record:

  * volume-based quantities weight exchange-held holdings at an exchange based in b by
    turnover_b / (1 - wash_b), so that reported volume = genuine holdings x genuine turnover, inflated by
    wash trading (genuine turnover equal across places unless coded otherwise);
  * holdings-based quantities use the model's holdings directly;
  * quantities whose level has no counterpart in the data (revenue in model units) may only be used as a
    ratio or difference between two episodes.

Each observation carries a standard error; the model value is compared with the observed value only
through that error (estimate.py).
"""
from __future__ import annotations
import numpy as np

# name: plain label, technical label, needs a jurisdiction, basis, level usable, unit, designs it serves
QUANTITIES = {
    "resident_domestic_exchange_share": dict(
        plain="Share of residents' exchange trading that takes place on exchanges operating at home",
        tech="Residents' custodial volume at domestically based exchanges / residents' custodial volume",
        code=True, basis="volume", level=True, unit="share (0 to 1)",
        use="India 2022: the shift of Indian users' trading from domestic to offshore exchanges after the tax change."),
    "resident_offshore_unexchanged_share": dict(
        plain="Share of residents' exchange trading on foreign exchanges outside automatic exchange of information with home",
        tech="Residents' custodial volume at exchanges whose base and seat are foreign and not exchanging with the residence state / residents' custodial volume",
        code=True, basis="volume", level=True, unit="share (0 to 1)",
        use="CARF waves: the share of residents' activity that remains outside the reporting net as states join."),
    "custodial_share_by_base": dict(
        plain="Share of all exchange trading at exchanges operating in this place",
        tech="Custodial volume at exchanges based in the jurisdiction / total custodial volume",
        code=True, basis="volume", level=True, unit="share (0 to 1)",
        use="Both: market shares of exchanges by place of operation (where volume data are reported)."),
    "custodial_share_by_seat": dict(
        plain="Share of all exchange trading at exchanges incorporated in this place",
        tech="Custodial volume at exchanges seated in the jurisdiction / total custodial volume",
        code=True, basis="volume", level=True, unit="share (0 to 1)",
        use="Both: market shares by place of incorporation (company registries, licensing data)."),
    "resident_custodial_share": dict(
        plain="Share of residents' holdings kept with exchanges rather than self-held",
        tech="Residents' custodial holdings / residents' holdings in the class",
        code=True, basis="holdings", level=True, unit="share (0 to 1)",
        use="Both: the move to self-custody after a tax or reporting change (survey or on-chain estimates)."),
    "resident_share": dict(
        plain="Share of all digital-asset holdings belonging to residents of this place",
        tech="Holdings of residents / holdings in the class",
        code=True, basis="holdings", level=True, unit="share (0 to 1)",
        use="Both: the distribution of holders across states (adoption surveys, on-chain geography)."),
    "resident_visible_share": dict(
        plain="Share of residents' holdings that the state taxing them first can see",
        tech="Residents' assigned holdings weighted by the primary claimant's visibility / residents' holdings",
        code=True, basis="holdings", level=True, unit="share (0 to 1)",
        use="CARF waves: reported holdings relative to estimated holdings, before and after a wave."),
    "resident_gap_share": dict(
        plain="Share of residents' holdings that no state may tax",
        tech="Residents' holdings with no claimant / residents' holdings",
        code=True, basis="holdings", level=True, unit="share (0 to 1)",
        use="Rarely observed directly; mainly for validation against expert estimates."),
    "exit_share": dict(
        plain="Share of potential holdings that leave digital assets altogether",
        tech="Outside-option share x",
        code=False, basis="holdings", level=False, unit="change between episodes",
        use="Both: falls in total activity after a change. The level has no observed counterpart, so use it only as a ratio or difference between episodes."),
    "rate": dict(
        plain="Effective tax rate the state applies",
        tech="Equilibrium (or coded) rate tau_i",
        code=True, basis="holdings", level=True, unit="rate (0 to 1)",
        use="Competitive states: an observed effective rate disciplines the model's rate competition."),
    "revenue": dict(
        plain="Tax collected by the state from digital-asset holdings",
        tech="Revenue R_i in model units",
        code=True, basis="holdings", level=False, unit="change between episodes",
        use="Both: the change in collections after a reform. Model units have no observed counterpart, so use only as a ratio or difference."),
    "revenue_share": dict(
        plain="This state's share of all tax collected from digital-asset holdings",
        tech="R_i / sum of R",
        code=True, basis="holdings", level=True, unit="share (0 to 1)",
        use="Rarely available; mainly for validation."),
}


class Measured:
    """Model-implied measured quantities for one solved episode."""

    def __init__(self, comp, eq, design=None):
        self.comp, self.eq = comp, eq
        w = comp.world
        N = w.N
        wash = np.zeros(N); turn = np.ones(N)
        if design is not None:
            for m in design.measurement:
                if m.code in w.codes:
                    k = w.index(m.code)
                    wash[k] = min(0.99, max(0.0, float(m.wash_share or 0.0)))
                    turn[k] = max(1e-9, float(m.turnover if m.turnover is not None else 1.0))
        self.vfac = turn / (1.0 - wash)                       # reported volume per unit of genuine holdings, by base
        s = np.asarray(eq["s"], float)
        self.s = s
        self.cust = comp.c == 0
        self.vol = np.where(self.cust, s * self.vfac[comp.p], 0.0)
        self.ex = w.exchanging()
        self.m = s[comp.ek] * comp.ew                          # entry masses
        self.codes = w.codes

    def _i(self, code):
        return self.codes.index(code)

    def value(self, quantity, code=""):
        c, eq = self.comp, self.eq
        s, vol, cust = self.s, self.vol, self.cust
        if quantity == "exit_share":
            return float(eq["exit"])
        i = self._i(code)
        J, Pb, Qs = c.j, c.p, c.q
        div = lambda a, b: float(a / b) if b > 1e-15 else float("nan")
        if quantity == "resident_domestic_exchange_share":
            return div(vol[(J == i) & (Pb == i)].sum(), vol[J == i].sum())
        if quantity == "resident_offshore_unexchanged_share":
            ex = self.ex
            outside = (Pb != i) & (Qs != i) & ~(ex[i] & (ex[Pb] | ex[Qs]))
            return div(vol[(J == i) & outside].sum(), vol[J == i].sum())
        if quantity == "custodial_share_by_base":
            return div(vol[Pb == i].sum(), vol.sum())
        if quantity == "custodial_share_by_seat":
            return div(vol[cust & (Qs == i)].sum(), vol.sum())
        if quantity == "resident_custodial_share":
            return div(s[cust & (J == i)].sum(), s[J == i].sum())
        if quantity == "resident_share":
            return div(s[J == i].sum(), s.sum())
        ej, m = c.ej, self.m
        if quantity == "resident_visible_share":
            return div((m * c.op * (~c.egap))[ej == i].sum(), m[ej == i].sum())
        if quantity == "resident_gap_share":
            return div((m * c.egap)[ej == i].sum(), m[ej == i].sum())
        if quantity == "rate":
            return float(eq["tau"][i])
        if quantity == "revenue":
            return float(eq["revenue"][i])
        if quantity == "revenue_share":
            R = np.asarray(eq["revenue"], float)
            return div(R[i], R.sum())
        raise KeyError(quantity)


def observation_value(obs, measured: dict):
    """Model-implied value of an observation, given Measured objects by episode name."""
    a = measured[obs.episode].value(obs.quantity, obs.code)
    if not obs.compared_with:
        return a
    b = measured[obs.compared_with].value(obs.quantity, obs.code)
    if obs.comparison == "difference":
        return a - b
    return a / b if abs(b) > 1e-15 else float("nan")
