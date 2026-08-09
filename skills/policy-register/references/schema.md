# The `.pol` file

JSON, `schemaVersion` 1, `family` `"policy-register"`. Written atomically through a temp file
and `os.replace`, so an interrupted write cannot leave a half-file.

```json
{
  "schemaVersion": 1,
  "family": "policy-register",
  "meta":     { "orgName": "…", "owner": "…", "scopeNote": "…", "asOf": "YYYY-MM-DD" },
  "settings": { "reviewIntervalDays": 365, "dueWindowDays": 30 },
  "policies": [ … ],
  "history":  [ … ],
  "createdAt": "…", "updatedAt": "…"
}
```

`family` is checked on load, so a risk register (`.rr`), CSF profile (`.csfp`), exceptions
register (`.exc`) or metrics register (`.mtr`) is refused by name rather than misread.

## A policy record

```json
{
  "id": "P-001",
  "kind": "policy",
  "title": "Information Security Policy",
  "owner": "Head of Information Security",
  "version": "3.1",
  "state": "approved",
  "mappedTo": ["PM-1", "PL-1", "GV.PO-01"],
  "approval": { "by": "The Board", "on": "2025-11-04", "version": "3.1" },
  "review":   { "intervalDays": 365, "lastOn": "2026-05-12", "nextOn": "2027-05-12" },
  "acknowledgement": { "required": true, "cadence": ["on-hire", "annual", "on-update"] },
  "supersededOn": null, "supersededBy": null, "supersedes": null,
  "note": "", "createdAt": "…"
}
```

| Field | Notes |
|---|---|
| `id` | `P-001`, allocated from the highest existing number. Never reused. |
| `kind` | `policy`, `plan` or `playbook`. Only `policy` behaves in this release; the other two are **refused at write time** with that reason. The field ships anyway so a store written today needs no migration later. |
| `state` | `draft` → `approved` → `superseded`. `revise` returns an approved record to `draft` and clears `approval`. |
| `mappedTo` | Requirement ids this document is aimed at. Free-form on purpose: ids outside the shipped spine are kept and shown in their own section. |
| `approval` | `null` until approved. `approve` refuses without **both** `by` and `on`. |
| `review` | `nextOn` is derived from `intervalDays` at approval unless `--next-review` is given. |
| `acknowledgement.cadence` | Any of `on-hire`, `annual`, `on-update` — the three GV.PO-01 names. |
| `supersededBy` | `null` when a document was withdrawn with no replacement, which is a real state and the one that escalates. |

## What is NOT in the file

**Nothing derived.** No review status, no escalation, no requirement state, no count. All of
it is computed on every read from the dates and the record states, so an overdue flag clears
the moment the review is recorded and cannot be left stale by an edit somebody made by hand.

`evals/lifecycle.sh` asserts this directly: after a review is recorded, the escalation is
gone, and no record in the store carries a `reviewState` key.

## `history`

Append-only. One entry per act — `add`, `approve`, `revise`, `review`, `supersede`, `map`,
`unmap` — each with `event`, `target`, `actor`, `ts`, and `why` where the act requires a
reason. Nothing reads history to compute a current state; it is the record of what happened,
which is a different thing and stays a different thing.

## Loading is more tolerant than writing

`approve` refuses without a named approver and a date. A file that **already** carries
`"state": "approved"` with `"approval": null` still loads, and `analyze` reports it as
`no-review-date` rather than hiding it.

That asymmetry is deliberate. The person holding a register in that state is the person who
has to fix it, and a loader that refused would leave them unable to look at their own file.
The refusal belongs where the bad state is created, not where it is read.

## Settings

| Key | Default | Meaning |
|---|---|---|
| `reviewIntervalDays` | 365 | Default gap between reviews. Overridable per record at `add`. |
| `dueWindowDays` | 30 | How far ahead a review shows as due rather than current. |

Neither affects whether anything appears — only how it is labelled. **Nothing in this engine
removes a record or a row from a view on the strength of a date.**
