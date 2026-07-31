# Exceptions Register — Data Model Reference

## Contents
- Store shape (`.exc`, schema v1)
- Acceptance shape
- Exception shape
- The five required fields, and why a record without them does not exist
- Status bands
- Change log (history)
- Date fields are canonical `YYYY-MM-DD`
- Derived-not-stored rule
- Cross-links and `sourceRiskRef`

## Store shape (`.exc`, schema v1)

```json
{
  "schemaVersion": 1,
  "family": "exceptions-register",
  "meta": { "clientName": "", "owner": "", "scopeNote": "", "asOf": "YYYY-MM-DD" },
  "settings": { "dueWindowDays": 30 },
  "acceptances": [ /* Acceptance[] */ ],
  "exceptions":  [ /* Exception[] */ ],
  "history":     [ /* HistoryEvent[] — append-only */ ],
  "createdAt": "ISO-8601",
  "updatedAt": "ISO-8601"
}
```

`family` is checked before anything else, so a `.rr`, `.csfp` or `.mtr` handed to this engine
is refused by name rather than half-read into a shape that happens to parse.

`settings.dueWindowDays` is how far ahead of a re-validation date an item starts showing as
due. It is the only tunable in the status bands below.

## Two object types, one lifecycle

An **acceptance** records a residual risk the organisation has knowingly accepted. An
**exception** records a deviation from a control, policy or standard, with the compensating
control that offsets it. They are different objects — one is about a risk you are living
with, the other about a rule you are not following — but they share one lifecycle:
approved, re-validated periodically, and eventually closed or expired.

## Acceptance shape

```json
{
  "id": "A-001",
  "title": "40-day patch window on nine internet-facing systems",
  "description": "",
  "approver": "CISO",
  "justification": "Vendor patch cadence is quarterly; compensating monitoring in place.",
  "acceptedDate": "2026-07-01",
  "revalidationDate": "2027-01-01",
  "expiryDate": "2027-07-01",
  "status": "active",
  "riskIds": ["R-006"],
  "csfSubcategoryIds": ["ID.RA-01"],
  "incidentIds": [],
  "sourceRiskRef": "R-006",
  "notes": ""
}
```

## Exception shape

```json
{
  "id": "X-001",
  "title": "Finance runs without phishing-resistant MFA",
  "deviationFrom": "NYDFS-500.12",
  "compensatingControl": "Callback verification on all payment changes over $10k.",
  "approver": "CFO",
  "justification": "Hardware token rollout blocked until the ERP upgrade completes.",
  "acceptedDate": "2026-05-01",
  "revalidationDate": "2026-11-01",
  "expiryDate": "2026-09-30",
  "status": "active",
  "riskIds": ["R-007"],
  "csfSubcategoryIds": ["PR.AA-01"],
  "incidentIds": [],
  "notes": ""
}
```

`deviationFrom` is **free text or a control/standard reference** — `NYDFS-500.12`,
`CIS-4.1`, `ISO A.8.5`, or an internal policy id. It is not validated against a catalogue,
because the standard being deviated from is frequently the organisation's own.

Exceptions are **unscored in v1**. An exception's severity is the severity of the risk it
creates, and that belongs in `risk-register`; link the two by id rather than inventing a
second scoring scale here.

## The five required fields, and why a record without them does not exist

Both object types require, on creation:

| field | why it is required |
|---|---|
| `title` | an inventory of untitled items cannot be reviewed |
| `approver` | an acceptance nobody approved is a description of a problem, not a decision |
| `justification` | the basis is the artifact — "we accepted it" is not a record of *why* |
| `acceptedDate` | when the clock started |
| `revalidationDate` | when somebody must look again |

An exception additionally requires `compensatingControl`. A deviation with nothing
offsetting it is not an exception; it is an unmanaged gap, and calling it an exception
launders it.

**A record missing any of these is refused before the file is opened**, so the store is
never left half-written. That refusal is not a validation nicety — it *is* the product. A
register that accepts "R-014, accepted, see email" reproduces the free text it was built to
replace, and passes an audit exactly as badly.

## Status bands

Derived from dates and `--today`, never stored:

| band | rule |
|---|---|
| `current` | `revalidationDate` is more than `dueWindowDays` away |
| `revalidation-due` | `revalidationDate` is within `dueWindowDays` |
| `revalidation-overdue` | `revalidationDate` has passed |
| `expired` | `expiryDate` has passed |
| `closed` | the record was explicitly closed |

`expired` outranks the re-validation bands: an item past its expiry date is past its expiry
date whether or not it was also due for review.

**A lapsed clock surfaces an item. It never expires the reasoning.** An overdue acceptance is
still an acceptance — the organisation is still carrying that risk — and silently dropping it
from the inventory because a date passed would delete the very record the inventory exists to
hold. Overdue items stay, and stay visible.

These are distances from a date somebody chose, in the same sense as the age bands in the
sibling skills. They say nothing about whether the reasoning is still sound; only a human
re-validating can say that.

## Change log (history)

Append-only, one event per mutation:

`acceptance-added` · `acceptance-revalidated` · `acceptance-closed` ·
`exception-added` · `exception-revalidated` · `exception-closed`

Each carries `ts`, `actor`, the target id, and a `why` where one is required.

**`revalidate` requires a rationale.** Re-validation is an *act* — a human re-checked the
reasoning and it still holds — not a timer reset. Allowing it without a rationale would make
the event indistinguishable from an automated bump, which is precisely what DORA RTS
Art. 3(d)(iv) asks the organisation to demonstrate it is not doing.

## Date fields are canonical `YYYY-MM-DD`

Zero-padded, and a real calendar date. `2026-7-1` is refused, before the file is opened.
Every status band sorts and compares by date, and an unpadded date sorts wrongly as text.
Same rule and same reason as the sibling skills.

## Derived-not-stored rule

Computed on demand, never written:

- status band, for both object types
- days until or since `revalidationDate` and `expiryDate`
- the attention lists: overdue, due, expired, no-compensating-control, unlinked
- inventory rollups and counts

`status` on the record itself holds only `active` or `closed` — a fact about what a human
did, not a derivation about where a date sits.

## Cross-links and `sourceRiskRef`

`riskIds[]`, `csfSubcategoryIds[]` and `incidentIds[]` are plain id arrays, not resolved
against those stores at write time — they are independent files a user may not both have.
A link that does not resolve is reported as unresolved, never silently dropped.

`sourceRiskRef` is set only by the `export-acceptances` bridge in `risk-register`, and marks
a record that originated as an accepted risk there. It exists so the bridge is idempotent:
re-running the export updates the record it created rather than adding a second one.

---

*A Cyber Aware Creation · Not affiliated with NIST. Not legal advice.*
