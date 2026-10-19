# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Wen Yi LEONG
"""Pre-registration export and check (build plan s 14, component B7).

Freezing records, before data are examined: the coded law (by fingerprint), the episodes, which quantities will
be observed and how (but not their values), the measurement attributes, which parameters are estimated and
which are fixed by judgement, the estimation settings, and the hypotheses. The record is fingerprinted with
SHA-256. A fingerprint on the author's own computer proves nothing about timing; credibility comes from
depositing the document with an independent registry (for example OSF) before data access (plan s 14.3, issue 5).
"""
from __future__ import annotations
import datetime
from dataclasses import asdict
from .params import VERSION
from .design import Design, fingerprint, world_fingerprint
from .measure import QUANTITIES
from .estimate import EST_PARAMS
from .params import Params

_OBS_KEYS = ("id", "quantity", "code", "episode", "compared_with", "comparison", "sd", "role", "unit", "source")


# Params fields the coded-world engine reads (others, such as rho or phi, come from the coded world itself)
MIXED_USED = ("theta0", "beta", "alpha", "kappa", "kappa_relief", "tau_max", "home_bias", "exit_weight", "sigma",
              "draws", "seed", "w_custodial", "w_single", "w_multisig")


def resolved_settings(world, design: Design, base: Params | None = None):
    """Every model setting estimation will use, other than the free parameters: the interface values, the
    world's settings and the design's fixed values, resolved (review finding 4)."""
    base = base or Params()
    full = base.to_dict()
    d = {k: full[k] for k in MIXED_USED}
    for n, meta in EST_PARAMS.items():
        if meta["where"] == "settings":
            d[n] = float(getattr(world.settings, n))
    for p in design.params:
        if not p.free and p.value is not None and p.name in EST_PARAMS:
            d[p.name] = float(p.value)
    for p in design.params:
        if p.free:
            d.pop(p.name, None)
    return {k: d[k] for k in sorted(d)}


def frozen_content(world, design: Design, base: Params | None = None):
    obs = [{k: getattr(o, k) for k in _OBS_KEYS} for o in design.observations]
    return dict(
        tool_version=VERSION,
        world_fingerprint=world_fingerprint(world),
        world_label=world.settings.label,
        jurisdictions=world.codes,
        episodes=[dict(name=e.name, description=e.description,
                       changes=[dict(target=c.target, field=c.field, value=c.value) for c in e.changes]) for e in design.episodes],
        observations=sorted(obs, key=lambda o: o["id"]),
        measurement=sorted([dict(code=m.code, wash_share=m.wash_share, turnover=m.turnover) for m in design.measurement], key=lambda m: m["code"]),
        parameters=sorted([dict(name=p.name, free=p.free, value=p.value, lower=p.lower, upper=p.upper,
                                judgement_low=p.judgement_low, judgement_high=p.judgement_high) for p in design.params], key=lambda p: p["name"]),
        settings=dict(concept=design.concept, starts=design.starts, seed=design.seed),
        resolved_settings=resolved_settings(world, design, base),
        hypotheses=sorted([asdict(h) for h in design.hypotheses], key=lambda h: h["id"]),
    )


def _record_fingerprint(record):
    """Fingerprint of the whole record except the fingerprint itself (review finding 2)."""
    return fingerprint({k: v for k, v in record.items() if k != "fingerprint"})


def freeze(world, design: Design, author="", title="", base: Params | None = None):
    content = frozen_content(world, design, base)
    with_values = [o.id for o in design.observations if o.value is not None]
    record = dict(kind="JAF Rule Bench pre-registration", title=title or design.label or "Pre-registration",
                  author=author, created=datetime.datetime.now().isoformat(timespec="seconds"),
                  values_present_at_freeze=with_values, content=content)
    record["fingerprint"] = _record_fingerprint(record)
    return record


def check(record: dict, world, design: Design, base: Params | None = None):
    """Compare the current world, design and settings with a frozen record. Returns dict(consistent, deviations, ...)."""
    now = frozen_content(world, design, base)
    then = record.get("content", {})
    dev = []
    if now["world_fingerprint"] != then.get("world_fingerprint"):
        dev.append("The coded law or settings differ from those frozen (world fingerprint changed).")
    def keyed(rows, key):
        return {r[key]: r for r in rows}
    for sect, key, noun in (("observations", "id", "Observation"), ("episodes", "name", "Episode"),
                            ("parameters", "name", "Parameter"), ("hypotheses", "id", "Hypothesis"), ("measurement", "code", "Measurement row")):
        a, b = keyed(then.get(sect, []), key), keyed(now[sect], key)
        for k in sorted(set(a) - set(b)):
            dev.append(f"{noun} {k} was pre-registered but is no longer in the design.")
        for k in sorted(set(b) - set(a)):
            dev.append(f"{noun} {k} was added after freezing.")
        for k in sorted(set(a) & set(b)):
            if a[k] != b[k]:
                changed = [f for f in a[k] if a[k].get(f) != b[k].get(f)]
                dev.append(f"{noun} {k} changed after freezing ({', '.join(changed)}).")
    if then.get("settings") != now["settings"]:
        dev.append("Estimation settings (concept, number of starts or seed) changed after freezing.")
    rs_then, rs_now = then.get("resolved_settings") or {}, now["resolved_settings"]
    changed = sorted(k for k in set(rs_then) | set(rs_now) if rs_then.get(k) != rs_now.get(k))
    if changed:
        dev.append("Model settings used in estimation differ from those frozen: " + ", ".join(
            f"{k} ({rs_then.get(k)} then, {rs_now.get(k)} now)" for k in changed[:8]) + ("…" if len(changed) > 8 else "") + ".")
    if then.get("tool_version") != now["tool_version"]:
        dev.append(f"Tool version changed from {then.get('tool_version')} to {now['tool_version']}.")
    fp_ok = _record_fingerprint(record) == record.get("fingerprint")
    if not fp_ok:
        dev.append("The record's own fingerprint does not match its content: it has been edited since it was frozen.")
    if not dev and fingerprint(now) != fingerprint(then):      # catch-all (review finding 3)
        dev.append("The design differs from the frozen record in a way not itemised above (for example duplicated identifiers).")
    return dict(consistent=not dev, deviations=dev, fingerprint=record.get("fingerprint"), record_intact=fp_ok,
                frozen=record.get("created"), values_present_at_freeze=record.get("values_present_at_freeze", []))


def to_markdown(record: dict) -> str:
    c = record["content"]
    L = [f"# {record['title']}", "",
         f"*Pre-registration generated by JAF Rule Bench {c['tool_version']} on {record['created']}.*", "",
         f"**SHA-256 fingerprint:** `{record['fingerprint']}`", "",
         "The fingerprint covers the whole record (title, author, date, the list of values present when frozen, and the JSON "
         "content at the end of this document). Depositing this document with an independent "
         "registry before any data are examined is what establishes its timing; the fingerprint only shows whether it was "
         "later altered.", ""]
    if record.get("author"):
        L += [f"**Author:** {record['author']}", ""]
    if record["values_present_at_freeze"]:
        L += [f"**Note:** {len(record['values_present_at_freeze'])} observation(s) already had values when this was frozen "
              f"({', '.join(record['values_present_at_freeze'][:12])}). Values are not part of the registration; disclose how they were obtained.", ""]
    else:
        L += ["**No observation values were present when this was frozen.**", ""]
    L += ["## 1. Coded law", "", f"World: {c['world_label']} ({len(c['jurisdictions'])} jurisdictions: {', '.join(c['jurisdictions'])}).",
          f"World fingerprint: `{c['world_fingerprint']}`", "", "## 2. Episodes", ""]
    L += ["| Episode | Description | Changes to the coded world |", "|---|---|---|", "| baseline | The coded world as loaded | none |"]
    for e in c["episodes"]:
        ch = "; ".join(f"{x['target']}.{x['field']} = {x['value']}" for x in e["changes"]) or "none"
        L.append(f"| {e['name']} | {e['description']} | {ch} |")
    L += ["", "## 3. Observations to be collected", "", "| ID | Role | Quantity | Jurisdiction | Episode | Compared with | Standard error | Source |", "|---|---|---|---|---|---|---|---|"]
    for o in c["observations"]:
        comp = f"{o['compared_with']} ({o['comparison']})" if o["compared_with"] else ""
        L.append(f"| {o['id']} | {o['role']} | {QUANTITIES.get(o['quantity'], {}).get('plain', o['quantity'])} | {o['code']} | {o['episode']} | {comp} | {o['sd']} | {o['source']} |")
    L += ["", "## 4. Measurement", ""]
    if c["measurement"]:
        L += ["| Exchanges based in | Wash-trading share | Relative genuine turnover |", "|---|---|---|"]
        L += [f"| {m['code']} | {m['wash_share']} | {m['turnover']} |" for m in c["measurement"]]
    else:
        L += ["No wash-trading or turnover adjustments."]
    L += ["", "## 5. Parameters", "", "| Parameter | Estimated or fixed | Start or fixed value | Bounds | Judgement range |", "|---|---|---|---|---|"]
    for p in c["parameters"]:
        lab = EST_PARAMS.get(p["name"], {}).get("tech", p["name"])
        jr = "" if p["judgement_low"] is None else "%s to %s" % (p["judgement_low"], p["judgement_high"])
        bounds = "" if p["lower"] is None and p["upper"] is None else "%s to %s" % (p["lower"], p["upper"])
        L.append(f"| {lab} | {'estimated' if p['free'] else 'fixed'} | {p['value']} | {bounds} | {jr} |")
    rs = c.get("resolved_settings") or {}
    if rs:
        L += ["", "Other model settings used in estimation (fixed): " + "; ".join(f"{k} = {v}" for k, v in rs.items()) + "."]
    s = c["settings"]
    L += ["", f"Estimation: simulated minimum distance weighted by the inverse measurement variances; equilibrium concept ({s['concept']}); "
              f"{s['starts']} starting point(s); seed {s['seed']}. Targets are fitted; holdout observations are used only for validation.", "",
          "## 6. Hypotheses", ""]
    for h in c["hypotheses"]:
        L += [f"**{h['id']}.** {h['statement']}", "", f"*Test:* {h['test']}", ""]
    if not c["hypotheses"]:
        L += ["None stated.", ""]
    import json
    L += ["## 7. Frozen content (JSON)", "", "```json", json.dumps(c, indent=1, ensure_ascii=False, sort_keys=True), "```", ""]
    return "\n".join(L)
