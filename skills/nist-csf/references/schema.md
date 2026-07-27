# CSF Organizational Profile — Data Model Reference (`.csfp` schema v1)

## Contents
- Store shape (schema v1)
- Profile shape
- Settings: scale, priority weights, function weights
- Assessment shape
- The three states a rating can be in
- Applicability (in scope / not applicable)
- Change log (history) and material changes
- `lastReviewed` semantics
- Snapshots
- Action items
- Derived-not-stored rule
- Coverage arithmetic
- Framework reference data (what is *not* in this file)

## Store shape (schema v1)

```json
{
  "schemaVersion": "1.0",
  "profile": { /* Profile */ },
  "assessments": [ /* Assessment[] — one per Subcategory */ ],
  "history":     [ /* HistoryEvent[] — append-only, never rewritten */ ],
  "snapshots":   [ /* Snapshot[] — named point-in-time freezes */ ],
  "actionItems": [ /* ActionItem[] */ ]
}
```

The `.csfp` file is the single local source of truth. It carries the Profile definition, the
assessment data, **and** its own history and snapshots, so the Profile can report change over time
with no external store. Dashboards are generated on demand and never stored — a rendered dashboard
goes stale the instant a rating moves; the data and the snapshots do not.

## Profile shape

```json
{
  "id": "acme-2026",
  "name": "Acme Corp — Enterprise Profile",
  "frameworkRef": "nist-csf-2.0",
  "scope": {
    "purpose": "Why this Profile exists and what decision it informs",
    "orgUnits": ["Corporate IT", "Manufacturing OT"],
    "threatTypes": ["ransomware", "supply chain"],
    "owner": "Role or name accountable for the Profile",
    "assumptions": "Anything a reader must know to interpret the ratings"
  },
  "tier": {
    "overall": 2,
    "byFunction": { "GV": 2, "ID": 2, "PR": 3, "DE": 1, "RS": 1, "RC": 1 }
  },
  "settings": { /* Settings */ },
  "created": "2026-07-26T00:00:00Z",
  "updated": "2026-07-26T00:00:00Z"
}
```

`frameworkRef` names the framework this Profile is assessed against. The engine resolves it to
bundled reference data; the store never copies the framework in. `tier.overall` and every
`tier.byFunction` value is `1..4` or `null` (not characterized).

> **Tiers are not a score.** They characterize the *rigor* of risk governance and management
> practices (NIST CSWP 29 §3.2, Appendix B). Never average them, trend them as a maturity number, or
> present "Tier 2.4". `byFunction` is optional and may be left entirely `null`.

## Settings

```json
{
  "scale": {
    "type": "ordinal",
    "min": 0,
    "max": 3,
    "labels": {
      "0": "Not Achieved",
      "1": "Partially Achieved",
      "2": "Largely Achieved",
      "3": "Fully Achieved"
    }
  },
  "priorityWeights": { "low": 1, "medium": 2, "high": 3, "critical": 4 },
  "functionWeights": { "GV": 1, "ID": 1, "PR": 1, "DE": 1, "RS": 1, "RC": 1 }
}
```

The scale definition lives in the store so the label set or size can change without invalidating
history: a historical event records the numbers that were set under the scale in force at the time.

`priorityWeights` and `functionWeights` feed the prioritized gap score. `functionWeights` default to
equal — raise one when a Function matters disproportionately for this organization (e.g. `DE` for a
detection-led strategy). Weights are keyed by the framework's own Function ids, so they are not
CSF-specific in principle.

## Assessment shape

One per Subcategory in the framework — 106 for CSF 2.0.

```json
{
  "subcategoryId": "PR.AA-01",
  "applicability": "in-scope",
  "current": 1,
  "target": 3,
  "priority": "high",
  "status": "in-progress",
  "notes": "SSO covers corporate apps; OT identities still local.",
  "evidenceRefs": ["IAM-policy-v4.pdf", "ticket:SEC-2211"],
  "lastReviewed": "2026-07-01"
}
```

| Field | Type | Notes |
|---|---|---|
| `subcategoryId` | string | Must exist in the referenced framework. The join key to outcome text and Implementation Examples. |
| `applicability` | `in-scope` \| `not-applicable` | Default `in-scope`. See below. |
| `current` | integer `0..scale.max`, or `null` | `null` = not yet assessed. |
| `target` | integer `0..scale.max`, or `null` | `null` = not yet targeted. |
| `priority` | `low` \| `medium` \| `high` \| `critical` | Default `medium`. Drives the prioritized gap score. |
| `status` | `not-started` \| `in-progress` \| `met` \| `accepted-gap` | Work state, independent of the ratings. |
| `notes` | string | Free text. |
| `evidenceRefs` | string[] | Pointers to evidence; the store holds references, never the evidence itself. |
| `lastReviewed` | ISO date, or `null` | See semantics below. |

### The three states a rating can be in

This distinction is load-bearing and is the reason ratings are never the string `"N/A"`:

1. **`null` — not yet rated.** Nobody has looked. Excluded from the coverage denominator.
2. **`0` — rated, Not Achieved.** Someone looked and found nothing in place. Counts in full.
3. **`applicability: "not-applicable"` — out of scope.** Excluded from every computation.

Collapsing these into one sentinel is how a Profile ends up claiming credit it has not earned. A
freshly initialized Profile is entirely state 1, and must report *no coverage figure at all* rather
than 0% or 100%.

### Applicability

`applicability` is its own field, not a rating value, so exclusion is defined once and every
subcommand applies the same rule. An assessment is excluded from **gap, coverage, completeness,
prioritization, quickstart-target, and export** if and only if `applicability == "not-applicable"`.

Marking a Subcategory `not-applicable` is a **material change** and requires a rationale — it is a
scoping decision an auditor will ask about, and "we decided it doesn't apply" is not an answer
unless the reason is recorded.

## Change log (history)

Append-only. Never rewritten, never reordered, never pruned.

```json
{
  "ts": "2026-07-26T14:03:00Z",
  "actor": "j.doe",
  "subcategoryId": "PR.AA-01",
  "type": "rating-changed",
  "field": "current",
  "from": 0,
  "to": 1,
  "rationale": "SSO rollout completed for corporate apps; OT still pending."
}
```

Every mutation appends exactly one event carrying `from` and `to`. Events about the Profile or an
action item rather than a Subcategory omit `subcategoryId` and carry the relevant id instead.

### Material changes — rationale REQUIRED

The tool refuses the change without `--rationale`:

| Change | Why it is material |
|---|---|
| `current` moves | It is the claim the whole report rests on. |
| `target` moves | It redefines what "done" means. |
| `status` → `accepted-gap` | A decision to live with a gap. |
| `status` → `met` | A closure claim. |
| `applicability` → `not-applicable` | A scoping decision. |
| action item → `closed` | A completion claim. |

Everything else — `notes`, `evidenceRefs`, `priority`, action item edits short of closure — is
recorded in history but does not require a rationale.

This is the un-promptable part: quarter over quarter, the *reasons* are what make a Profile a
narrative a board can follow rather than a spreadsheet that mysteriously changed.

## `lastReviewed` semantics

`lastReviewed` answers "when did a human last look at this outcome?" — so it is refreshed **only**
by a review-affirming action:

- a change to `current`, or
- an explicit `set --reviewed` (affirming "I looked; nothing changed" — which is itself a finding).

It is **not** touched by a notes edit, an evidence link, or a priority tweak. Otherwise tidying
notes would silently reset staleness across the Profile and the "stalest" list would be worthless.

`null` means never reviewed. It is reported as its own bucket, not merged into "stalest" — 40 never-
reviewed Subcategories is a different problem from 40 that were reviewed a year ago.

## Snapshots

```json
{
  "id": "q2-2026-assessment",
  "label": "Q2 2026 Assessment",
  "ts": "2026-06-30T00:00:00Z",
  "note": "Post-remediation review",
  "assessments": [ /* frozen copy */ ],
  "actionItems": [ /* frozen copy */ ],
  "rollups":     { /* frozen computed coverage + completeness */ }
}
```

Snapshots freeze assessments, **action items**, and the computed rollups. Action items are frozen
because the diff must report work opened and closed since the last review — a snapshot that omitted
them could not answer "what changed."

The rollups are the one place derived data is persisted, and deliberately so: a snapshot must keep
reporting the same numbers even if the scale or weights are later reconfigured.

## Action items

```json
{
  "id": "A-004",
  "title": "Extend SSO to OT identity stores",
  "linkedSubcategoryIds": ["PR.AA-01", "PR.AA-03"],
  "owner": "Head of Infrastructure",
  "milestone": "Q4 2026",
  "targetDate": "2026-12-15",
  "status": "open",
  "notes": ""
}
```

`status` is `open` | `in-progress` | `closed`. An item with an empty `owner` appears on the unowned
attention list; `targetDate` earlier than today with a non-closed status appears on the past-due
list. Gaps that never become owned, dated work are the failure mode this exists to catch.

## Derived-not-stored rule

Never written to the store outside a snapshot:

- gap and prioritized gap score
- coverage percentages, numerators, denominators
- completeness counts (assessed / targeted / not-applicable)
- attention lists
- Tier *suggestions*

All are computed on demand by `analyze`. `profile.tier` is different — a Tier a human has
**decided** is data, and is stored.

## Coverage arithmetic

Defined here because every consumer must compute it identically.

For a set S of assessments (a Category, a Function, or the whole Profile), considering only
`applicability == "in-scope"` members that have a `target` set:

```
D = sum(target)
N = sum(min(current or 0, target))
coverage = null            if D == 0
           N / D * 100     otherwise
```

Rules that follow, and must not be "simplified" away:

- **`current: null` counts as 0 in the numerator.** You cannot claim coverage you have not assessed.
- **`target: null` puts the assessment in neither N nor D.** Untargeted is not zero-gap; it is
  undecided, and it is reported through the completeness counts instead.
- **`D == 0` yields `null`, never 100%.** A Profile with nothing targeted has no coverage figure.
- **`N` and `D` always travel with the percentage** so any renderer can show `x/y`. A bare percentage
  hides whether it is drawn from 4 Subcategories or 106.

Completeness is reported alongside coverage at every level: `{total, inScope, notApplicable,
assessed, targeted}`.

Gap is `max(0, target - current or 0)`, and is undefined (not zero) where `target` is `null`.
Prioritized gap score is `gap × priorityWeights[priority] × functionWeights[function]`.

## Framework reference data (what is *not* in this file)

The 106 Subcategories, their outcome text, the 363 Implementation Examples, the Informative
References, and the Tier characterizations are **read-only bundled data** in
`references/nist-csf-2.0-core.json`. The store references them by id and never copies them.

That keeps `.csfp` files small and diffable, lets the framework data be corrected without touching
user data, and is what makes the engine framework-neutral: point `frameworkRef` at different
reference data and the same machinery applies. See `references/framework-abstraction.md`.
