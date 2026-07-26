# Risk Register — Data Model & Scoring Reference

## Contents
- Register shape (schema v2)
- Risk shape
- Themes
- Structured acceptance
- Change log (history)
- Snapshots
- Categories / taxonomy
- Matrix sizes and rating labels
- Band thresholds
- Risk appetite semantics
- Derived-not-stored rule
- v1 → v2 migration

## Register shape (schema v2)

```json
{
  "schemaVersion": 2,
  "meta": { "clientName": "", "assessor": "", "scopeNote": "", "appetiteStatement": "" },
  "settings": { "matrixSize": 5, "appetite": "medium" },
  "themes": [ { "id": "identity", "name": "Identity & Access", "description": "" } ],
  "risks": [ /* Risk[] */ ],
  "history": [ /* HistoryEvent[] — append-only */ ],
  "snapshots": [ /* Snapshot[] — named point-in-time freezes */ ],
  "createdAt": "ISO-8601",
  "updatedAt": "ISO-8601"
}
```

The file is the single local source of truth. It carries data **and** its own history and review
snapshots so the register can report change over time without any external store.

## Risk shape

```json
{
  "id": "R-001",
  "priority": 1,
  "title": "Short name",
  "description": "If <event>, then <consequence> (NISTIR 8286 event statement).",
  "category": "PR",
  "theme": "identity",
  "owner": "Role or name",
  "inherent": { "likelihood": 4, "impact": 5 },
  "response": { "type": "mitigate", "description": "Controls in place / planned", "cost": 45000 },
  "residual": { "likelihood": 2, "impact": 4 },
  "status": "in-treatment",
  "reviewDate": "2026-09-30",
  "acceptance": null,
  "csfSubcategoryId": "PR.AT-01",
  "notes": "Context, caveats, progress"
}
```

- `theme` — optional theme id (see Themes); the board-reporting rollup axis.
- `acceptance` — populated when a risk is accepted (see Structured acceptance); otherwise `null`.
- `priority` — optional manual board-ranking (NISTIR 8286 Priority). It is *not* used by scoring —
  banding is always derived from exposure — so it never affects the heat map or over-appetite flags;
  it is purely an author-assigned ordering hint.
- Everything else is as in v1: `id` `R-###`, `response.type` ∈ accept/transfer/mitigate/avoid,
  `status` ∈ open/in-treatment/monitoring/closed, likelihood/impact ∈ `1..matrixSize`.

## Themes

Boards think in themes, not line items. A theme groups risks for rollup reporting:

```json
{ "id": "third-party", "name": "Third-Party & Supply Chain", "description": "Vendor/SaaS exposure" }
```

Themes are project-defined. A risk references one via `theme`. Executive reporting aggregates by
theme (count, worst residual band, trend) so the board sees ~6 themes, not 40 rows.

## Structured acceptance

A risk with `response.type: "accept"` (and often `"transfer"`) must carry a structured acceptance,
not just a note — this is both good practice and the audit-defensible layer (DORA RTS Art. 3(d):
justified, re-validated acceptance; NYDFS §500: written approval):

```json
"acceptance": {
  "approver": "Name / role who accepted the risk",
  "justification": "Why this residual risk is acceptable",
  "acceptedDate": "2026-07-01",
  "expiryDate": "2027-07-01",
  "revalidationDate": "2027-01-01"
}
```

An acceptance past its `revalidationDate` is **stale** and must be surfaced for re-validation. An
acceptance with no approver or justification is incomplete and should be flagged.

## Change log (history)

Append-only. Every material change adds an event; events are never edited or removed (that is what
makes the log defensible and the trend real):

```json
{
  "ts": "2026-07-26T18:04:00Z",
  "actor": "D. Galleyne",
  "riskId": "R-005",
  "type": "score-changed",
  "field": "residual",
  "from": { "likelihood": 3, "impact": 5 },
  "to": { "likelihood": 3, "impact": 4 },
  "rationale": "Insurance rider bound; impact of financial loss reduced."
}
```

Event `type` values: `risk-added`, `risk-updated`, `score-changed`, `response-changed`,
`status-changed`, `risk-accepted`, `acceptance-revalidated`, `risk-closed`, `risk-reopened`,
`risk-deleted`, `theme-changed`, `settings-changed`, `snapshot-created`.

**Material changes require a `rationale`** (score moves, acceptances, closures, reopenings). Capture
the *why* in-session — it is what powers the board narrative and the audit trail. Non-material edits
(typo fixes, notes) may omit it.

## Snapshots

A named, frozen copy of the register at a point in time — the anchor for quarter-over-quarter
comparison and "as of" board views:

```json
{
  "id": "2026-Q2",
  "label": "Q2 2026 Board Review",
  "ts": "2026-06-30T00:00:00Z",
  "note": "Presented to audit committee",
  "data": { "settings": { }, "risks": [ /* frozen */ ], "summary": { /* frozen scored summary */ } }
}
```

Diffing the current register against a snapshot yields the "what changed since Q2" delta. Snapshots
are created at review checkpoints, not on every edit.

## Categories / taxonomy

CSF functions: `GV` Govern · `ID` Identify · `PR` Protect · `DE` Detect · `RS` Respond · `RC` Recover.
General categories: Operational · Financial · Third-Party / Supply-Chain · Compliance · Reputational.
(`category` is the risk-taxonomy axis; `theme` is the board-rollup axis — they can differ.)

## Matrix sizes and rating labels

`matrixSize` ∈ {3, 4, 5} (5×5 default). Likelihood and impact run `1..matrixSize`. Labels (SP 800-30):

| Level | 5×5 | 4×4 | 3×3 |
|---|---|---|---|
| 1 | Very Low | Low | Low |
| 2 | Low | Moderate | Moderate |
| 3 | Moderate | High | High |
| 4 | High | Very High | — |
| 5 | Very High | — | — |

## Band thresholds

Exposure = likelihood × impact. Band = highest band whose inclusive lower bound ≤ exposure:

| Matrix | low ≥ | medium ≥ | high ≥ | critical ≥ |
|---|---|---|---|---|
| 5×5 | 1 | 5 | 10 | 15 |
| 4×4 | 1 | 4 | 8 | 12 |
| 3×3 | 1 | 3 | 5 | 7 |

Band order (ascending): `low < medium < high < critical`. Lives in `scripts/score_register.py`.

## Risk appetite semantics

`settings.appetite` is the **worst band still acceptable**. A risk is **over appetite** when its
residual band is strictly worse than the appetite band. `meta.appetiteStatement` holds the written
appetite (CSF 2.0 GV.RM) that boards ask to see.

## Derived-not-stored rule

Exposure and band are never persisted on a risk — the script computes them from likelihood × impact
every time, so a stale number can't contradict the inputs. (Snapshots are the one exception: they
freeze a *computed* summary on purpose, as a historical record.)

## v1 → v2 migration

A `schemaVersion: 1` file loads fine: treat missing `themes`, `history`, and `snapshots` as empty
arrays and missing `acceptance` as `null`. On first write, stamp `schemaVersion: 2`. No data is lost.
