# Incident Materiality — Data Model Reference

## Contents
- Store shape (`.inc`, schema v1)
- Incident shape
- Factor assessments
- Determinations are a list, not a field
- Disclosure: regimes, decision, filings
- Anchors, and why two kinds of time appear here
- Status bands and clock states
- Change log (history)
- Date and timestamp rules
- Derived-not-stored rule
- Cross-links and the discoverability caveat

## Store shape (`.inc`, schema v1)

```json
{
  "schemaVersion": 1,
  "family": "incident-materiality",
  "meta": { "clientName": "", "owner": "", "scopeNote": "", "asOf": "YYYY-MM-DD" },
  "settings": { "holidays": ["YYYY-MM-DD"] },
  "incidents": [ /* Incident[] */ ],
  "history":   [ /* HistoryEvent[] — append-only */ ],
  "createdAt": "ISO-8601",
  "updatedAt": "ISO-8601"
}
```

`family` is checked before anything else, so a `.rr`, `.csfp`, `.mtr` or `.exc` handed to this
engine is refused by name rather than half-read into a shape that happens to parse.

**One store holds many incidents.** The design spec's phrase *"one record per incident"* describes
the grain of a **record**, not of a file. A file per incident would make the board section — which
is keyed by incident id and may carry several — an assembly of loose files, and would give the
aggregation factor (§ *Factor assessments*) nothing to point at. The sibling skills all hold a
list, and this one does too.

`settings.holidays` is the non-business-day calendar the SEC clock uses on top of weekends. It
ships **empty**, and that has a direction of error worth stating: with no holidays supplied, a
federal holiday is counted as a business day, so the computed deadline lands **earlier** than the
true one. That is the safe direction, and it is still wrong. Supply the calendar.

## Incident shape

```json
{
  "id": "I-001",
  "title": "Vendor payroll portal breach",
  "discoveredAt": "2026-07-06",
  "scopeNote": "Third-party HR SaaS; our tenant only.",
  "status": "open",
  "factors": [ /* FactorAssessment[] — append-only */ ],
  "determinations": [ /* Determination[] — append-only */ ],
  "disclosure": {
    "regimes": ["sec-1.05"],
    "decision": "pending",
    "basis": "",
    "filings": { "sec-1.05:8-K": "2026-07-20" }
  },
  "anchors": { "awareAt": null, "classifiedAt": null },
  "linkedRiskIds": ["R-006"],
  "linkedExceptionIds": ["A-001"],
  "notes": ""
}
```

`status` is `open` or `closed` — a fact about what a human did. Every band below is derived.

## Factor assessments

```json
{ "key": "data", "assessment": "bearing",
  "rationale": "Names and work email for ~1,900 employees; no financial or health data.",
  "relatedIncidentIds": [], "actor": "CISO", "ts": "ISO-8601" }
```

Six keys, fixed: `financial`, `operational`, `data`, `regulatory`, `reputational`,
`aggregation`. They are documented one by one in `materiality-factors.md`.

`assessment` is one of **`bearing`**, **`no-bearing`**, **`unknown`** — deliberately three words
that do not add up. There is no scale, no weight and no score, because a materiality
determination is not the output of an arithmetic and a tool that implied otherwise would be
inviting its user to defend a number they did not choose.

`rationale` is **required**. An assessment without one is a ticked box, and a ticked box is not a
record of a judgment. Refused before the file is opened.

Assessments are **appended**, never overwritten. Re-assessing `data` after the forensics report
lands adds a second entry; the earlier one stays. The current assessment for a key is its most
recent entry — and the sequence is the answer to *"when did you know?"*.

`relatedIncidentIds` is meaningful only on the `aggregation` factor, where it names the other
incidents considered together.

## Determinations are a list, not a field

```json
{ "state": "material", "rationale": "...", "decider": "General Counsel",
  "determinedAt": "2026-07-14", "ts": "ISO-8601" }
```

`state` is one of `assessing`, `material`, `not-material`, `not-yet-determinable`.

The **current** determination is the last entry. Everything before it stays. A determination that
changed from `not-material` to `material` is the single most consequential fact in this store, and
a design that let it be edited in place would destroy the record precisely where it matters most.

`rationale` and `decider` are both **required** on every determination, including the first
`assessing` one. `determinedAt` is required and is a canonical date; it is the anchor the SEC
clock runs from, so it is not allowed to default to today.

**The engine never writes a determination by itself.** Nothing in this tool computes, suggests or
defaults a `state`. The factors are recorded so a human can reason from them; the reasoning and
the conclusion are the human's, made with counsel.

## Disclosure: regimes, decision, filings

`regimes` — which regimes this incident is being tracked against: `sec-1.05`, `dora`, or neither.
Set per incident, because scope is a fact about the entity and the incident, not a global setting.

`decision` — `pending`, `file`, or `no-file`. A recorded decision, with `basis`, and never derived
from the factors.

`filings` — a map keyed `"<regime>:<window>"` to the date or timestamp the filing was made:
`"sec-1.05:8-K"`, `"dora:initial"`, `"dora:intermediate"`, `"dora:final"`. A window with no entry
is unfiled; the clock for it stays live.

## Anchors, and why two kinds of time appear here

`anchors.awareAt` and `anchors.classifiedAt` are ISO-8601 **timestamps** (`YYYY-MM-DDTHH:MM`),
not dates. Everything else here is a date.

That asymmetry is not sloppiness — it is the regimes. **SEC Item 1.05 counts business days from a
determination date. DORA counts clock hours from awareness and from classification.** A single
time representation would have to fake one of them, and faking hour precision from a date is the
worse of the two failures: it would produce a DORA deadline that looks exact and is not.

So: **if a DORA anchor is absent, the DORA clocks report `anchor-missing` rather than a deadline.**
The engine will not invent midnight.

## Status bands and clock states

**Incident band** — one word for where the incident stands. Evaluated in this order:

| # | band | rule |
|---|---|---|
| 1 | `closed` | the incident was explicitly closed |
| 2 | `disclosure-overdue` | at least one deadline has passed with no filing recorded |
| 3 | `disclosure-due` | at least one clock is running |
| 4 | `no-determination` | nothing determined yet, including no `assessing` entry |
| 5 | `assessing` | latest determination state is `assessing` |
| 6 | `not-yet-determinable` | latest state is `not-yet-determinable` |
| 7 | `not-material` | latest state is `not-material` |
| 8 | `filed` | latest state is `material` and every applicable window has a filing |
| 9 | `material` | latest state is `material` with nothing currently owed |

**A running clock outranks the determination, and the ordering is the point.** An incident can be
determined **not material** for Item 1.05 and still owe a DORA report on a live clock — *"not
material"* and *"no notification duty"* are different questions with different tests and different
audiences. A band that read the determination first would report `not-material` and hide the one
of the two facts that has a date attached. Pinned in `self-test`.

`anchor-missing` deliberately does **not** drive the band. It is a gap in the record rather than a
deadline, and it has its own attention list.

**Clock state**, per regime window:

`not-applicable` · `not-started` · `anchor-missing` · `due` · `overdue` · `filed`

`not-started` is the honest state for an incident under assessment: the Item 1.05 clock has not
begun, because it begins at the determination. See `disclosure-clocks.md`.

## Change log (history)

Append-only, one event per mutation, at store level:

`incident-opened` · `factor-assessed` · `determination-recorded` · `disclosure-set` ·
`filing-recorded` · `anchor-set` · `incident-linked` · `incident-closed`

Each carries `ts`, `actor`, the incident id, and a `why` where one is required.

## Date and timestamp rules

Dates are canonical `YYYY-MM-DD`: zero-padded, and a real calendar date. `2026-7-1` is refused,
before the file is opened. Every band sorts and compares by date, and an unpadded date sorts
wrongly as text. Same rule and same reason as the sibling skills.

Timestamps (the two DORA anchors and the filing entries for DORA windows) are
`YYYY-MM-DDTHH:MM`, optionally with seconds and an offset. A bare date supplied where a timestamp
is required is refused with the reason above — not silently read as midnight.

## Derived-not-stored rule

Computed on demand, never written:

- every deadline — the Item 1.05 business-day date, and each DORA window
- days and hours remaining, and whether a window is overdue
- the incident band and every clock state
- the elapsed time since discovery with no determination recorded
- factor completeness — which of the six keys are assessed, and which are not

Stored: what a human did. Derived: where a date sits. The line is the same one the whole toolkit
draws, and it is why re-running `analyze` with a different `--today` never rewrites anything.

**Factor completeness is not a score.** The engine reports *which* factors are assessed and which
are not. It never counts how many were assessed `bearing`, because that count reads as an
arithmetic leading to a verdict, and there is no such arithmetic.

## Cross-links and the discoverability caveat

`linkedRiskIds[]` and `linkedExceptionIds[]` are plain id arrays, not resolved against those
stores at write time — they are independent files a user may not both have. A link that does not
resolve is reported as unresolved, never silently dropped.

The link from an incident to an **accepted risk or a granted exception** is the most useful and
the most dangerous connection in this toolkit: *"the third-party risk we accepted in April is the
one that materialised in July"* is exactly the sentence a board needs and exactly the sentence
opposing counsel would like to find. It is kept, because a governance record that omits it is not
a governance record — and the discoverability caveat is rendered wherever it appears, not
footnoted. See `exceptions-register/references/exceptions.md`.

---

*A Cyber Aware Creation · Not affiliated with NIST. Not legal advice.*
