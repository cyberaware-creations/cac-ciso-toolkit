# CSF Organizational Profile — Data Model Reference (`.csfp` schema v2)

## Contents
- Store shape (schema v2)
- Profile shape
- Settings: scale, priority weights, function weights, reporting thresholds
- Assessment shape
- The three states a rating can be in
- Applicability (in scope / not applicable)
- Attribution: `confirmedAt`, `confirmedBy`, `source`
- Intake records
- Change log (history) and material changes
- `lastReviewed` semantics
- Snapshots
- Action items
- Derived evidence states
- Ratings never expire
- Derived-not-stored rule
- Coverage arithmetic
- Privacy
- Framework reference data (what is *not* in this file)

## Store shape (schema v2)

```json
{
  "schemaVersion": "2.0",
  "profile": { /* Profile */ },
  "assessments": [ /* Assessment[] — one per Subcategory */ ],
  "intake":      [ /* IntakeRecord[] — append-only, never rewritten */ ],
  "history":     [ /* HistoryEvent[] — append-only, never rewritten */ ],
  "snapshots":   [ /* Snapshot[] — named point-in-time freezes */ ],
  "actionItems": [ /* ActionItem[] */ ]
}
```

The `.csfp` file is the single local source of truth. It carries the Profile definition, the
assessment data, **and** its own history and snapshots, so the Profile can report change over time
with no external store. Dashboards are generated on demand and never stored — a rendered dashboard
goes stale the instant a rating moves; the data and the snapshots do not.

A file written under schema 1.0 loads without complaint: `load_store` normalizes it to the v2 shape
in memory — every assessment gains `confirmedAt`, `confirmedBy` and `source`, all `null`, and an
empty `intake` array is seeded if absent. Nothing is inferred and nothing is lost. The version
stamped on disk does not change on a read-only command (`analyze`, `diff`, `queue`); `save_store`
stamps `schemaVersion: "2.0"` the first time anything actually writes the file.

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
  "functionWeights": { "GV": 1, "ID": 1, "PR": 1, "DE": 1, "RS": 1, "RC": 1 },
  "reporting": { "scopeThresholdPct": 60, "ageThresholdDays": 180 }
}
```

The scale definition lives in the store so the label set or size can change without invalidating
history: a historical event records the numbers that were set under the scale in force at the time.

`priorityWeights` and `functionWeights` feed the prioritized gap score. `functionWeights` default to
equal — raise one when a Function matters disproportionately for this organization (e.g. `DE` for a
detection-led strategy). Weights are keyed by the framework's own Function ids, so they are not
CSF-specific in principle.

`reporting` governs presentation, not scoring — neither threshold changes a rating or a coverage
number, only whether a headline figure is shown and what age is called out for a second look.

- **`scopeThresholdPct`** (default 60) — below this share of in-scope Subcategories *assessed*, the
  headline programme coverage figure is suppressed on both dashboards; see `references/dashboards.md`.
  The denominator is `assessed / inScope`, deliberately not attribution — gating on `attributed /
  inScope` would blank the headline on every Profile written before v2 existed.
- **`ageThresholdDays`** (default 180) — a confirmed rating older than this is counted in
  `evidence.age.overall.olderThanThreshold` and by Function. It is a reporting threshold only:
  ratings do not expire (see "Ratings never expire" below).

A v1 file has no `reporting` key at all, and a v2 file may set only one of the two. `load_store`
fills in the shipped default for whichever is missing, rather than merging `settings` as one flat
object — a shallow merge alone would let a v1 file's absent `reporting` silently null out both.

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
  "lastReviewed": "2026-07-01",
  "confirmedAt": "2026-07-01",
  "confirmedBy": "Darren",
  "source": "in-0004"
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
| `confirmedAt` | ISO date, or `null` | The date a human decided this rating. Schema v2. See "Attribution" below. |
| `confirmedBy` | string, or `null` | Who decided it. |
| `source` | intake `id`, or `null` | Which recorded source it was decided from. |

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

## Attribution: `confirmedAt`, `confirmedBy`, `source`

Three fields travel with every Current rating, added in schema v2: `confirmedAt` (the ISO date a
human decided the rating), `confirmedBy` (who), and `source` (the `intake` record it was decided
from). All three are set together — by `set --current N --source in-NNNN --confirmed-by NAME` — and
all three clear together when the rating is cleared. `--current null` needs no attribution; there is
nothing left to attribute.

`--current` **refuses** without both `--source` and `--confirmed-by` present. `--target` is
deliberately **not** gated the same way: it is a risk-based decision already covered by
`--rationale`, and `quickstart-target` seeds it in bulk across the whole Profile — gating it would
make the bulk seed impossible.

`confirmedAt` is **not** seeded from `lastReviewed` on a v1→v2 load. "A human looked at this
outcome" (`lastReviewed`) and "a human decided this rating, from this source, on this date"
(`confirmedAt`) are different claims, and inventing the second from the first would fabricate
exactly the attribution this schema exists to make honest. A v1 rating normalizes with all three
fields `null` — it still scores, exactly as it always did; it simply reports as unattributed.

**The honest limit.** The CLI cannot prove a human typed the number — nothing stops a caller from
passing `--confirmed-by "Darren"` when Darren said no such thing. What it enforces is only that no
rating exists without a named source and a named person attached to it. The actual discipline —
asking who is deciding this, and pointing `--source` at a real recorded conversation rather than an
invented id — is a behavioural rule for whoever operates this skill, not a mechanical one the tool
can check. See `SKILL.md`.

`confirmed` (a rating exists) and `attributed` (has all three fields) are separate axes, both
reported by `analyze`: `attributed + unattributed == confirmed`. Reporting them as one number is the
exact failure this schema exists to prevent — it would let a bare v1 rating read identically to one
someone can actually defend.

## Intake records

```json
{
  "id": "in-0001",
  "label": "architecture review with infra team",
  "sourceDate": "2026-03-14",
  "recordedAt": "2026-03-16",
  "subjects": ["ID.AM-01", "ID.AM-02"],
  "recordedBy": "Darren"
}
```

`intake` is append-only, mirroring `history` — never rewritten, never reordered, never pruned.
Written only by `intake add`, which **writes no ratings, ever**. The unit of record is the *source*,
not the Subcategory: one conversation typically bears on several outcomes, and "what did the March
architecture review actually cover?" is a question a per-Subcategory pointer list cannot answer.

| Field | Type | Notes |
|---|---|---|
| `id` | string | `in-0001`, `in-0002`, … — assigned, never chosen. |
| `label` | string | A note *about* the source. Human-authored or human-confirmed, **never model-generated**, and never an excerpt *from* the source — that is what keeps internal material out of this file. |
| `sourceDate` | ISO date | When the conversation, document, or review actually happened. |
| `recordedAt` | ISO date | When it entered the store. Defaults to today. |
| `subjects` | string[] | Subcategory ids this source bears on. Deduplicated on write. |
| `recordedBy` | string, or `""` | Who logged it. Falls back to `profile.scope.owner`; `intake add` warns if both are empty — a source nobody can be asked about. |

`sourceDate` and `recordedAt` **diverge routinely under accretion** — a March conversation recorded
in July is normal, not an error — and conflating them misreports how old the evidence actually is.
Both, along with `confirmedAt`, are compared and sorted **as plain strings**, so `check_store`
refuses anything that is not zero-padded ISO (`YYYY-MM-DD`): `2026-3-14` sorts after `2026-12-01`
and would make every `revisit` flag and age figure downstream quietly wrong.

Referenced by a rating's `source` field and by `queue`; never edited or removed once written —
correcting a bad record means adding a new one, the same discipline `history` already enforces.

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

## Derived evidence states

Computed by `analyze` and `queue` from `assessments` + `intake` on every read (`derive_evidence` in
`profile_analysis.py`); never written to the store. Every tracked Subcategory falls into exactly one
of four states:

| State | Rule |
|---|---|
| `not-applicable` | `applicability != "in-scope"`. |
| `confirmed` | in scope, `current is not None`. |
| `evidence-pending` | in scope, `current is None`, and at least one intake record's `subjects` names it. |
| `unrated` | in scope, `current is None`, and nothing in `intake` bears on it. |

`revisit` is a fifth, *orthogonal* flag, not a fifth state: a Subcategory that is `confirmed`, where
the rating cannot be shown to predate material that bears on it. It answers "has anything arrived
that this rating cannot be shown to predate?" It is a reporting flag and a `queue` input only — **it
does not affect scoring**. A `confirmed` rating flagged `revisit` still counts in coverage exactly as
before the material arrived; only a human choosing to re-confirm it changes the number.

There are two distinct reasons a `confirmed` rating lands in `revisit`, carried as `reason`:

| `reason` | Condition |
|---|---|
| `newer-material` | `confirmedAt` is set, and some bearing intake record has a `sourceDate` later than it. |
| `undated-confirmation` | `confirmedAt` is `null`, and some intake record bears on the Subcategory at all. |

The two are not interchangeable. `newer-material` is a comparison: the rating names the date it was
decided, and something newer has since arrived. `undated-confirmation` is not a comparison at all —
with no `confirmedAt` there is no date to compare against, so there is no basis to claim the rating
predates the material sitting next to it. Guessing a `confirmedAt` to make the comparison possible,
or treating the absence of a date as "nothing to flag," would both fabricate a claim this schema
exists to avoid. For `undated-confirmation`, `confirmedAt` stays `null` in the `revisit` row and
`newestSourceDate` is the newest bearing record's `sourceDate`.

## Ratings never expire

There is no auto-expiry, deliberately. It was rejected on two grounds: it would change a score with
no human act behind it, and a uniform interval is wrong on its face — a governance outcome and an
asset inventory decay at completely different rates, and no single `ageThresholdDays` describes both
honestly.

`age` is reported instead — median, oldest, and the count older than `settings.reporting.
ageThresholdDays`, overall and by Function — and the human judges. `revisit` gives what expiry was
reaching for, without the arbitrary interval: **a rating is questioned when new material arrives
about it, not when time passes.**

A rating carried over from a v1 Profile has no `confirmedAt` and is reported as `undated` rather
than guessed at — age reporting begins when ratings are confirmed under v2. That same absence of a
`confirmedAt` is exactly why `revisit` must not require one: a rating with no confirmation date has
no basis to claim it predates anything, so a v1 rating with intake bearing on it is flagged
`revisit` with `reason: "undated-confirmation"` the moment that intake is recorded — not left
silent until someone confirms it and gives it a date to compare against. An implementation that
guards the `revisit` check on `confirmedAt` being set silently drops every v1 rating from the queue
and from both dashboards' revisit counts, which is precisely the false "nothing to revisit" this
flag exists to prevent.

## Derived-not-stored rule

Never written to the store outside a snapshot:

- gap and prioritized gap score
- coverage percentages, numerators, denominators
- completeness counts (assessed / targeted / not-applicable)
- attention lists
- Tier *suggestions*
- evidence state per Subcategory, the four-way coverage split, and the `attributed`/`unattributed`
  split
- age statistics, the `revisit` list, and the scope guard's `suppressed` flag and statement
- the confirmation `queue` and its bands

All are computed on demand by `analyze` (or, for evidence states and the queue alone, by `queue`).
`profile.tier` is different — a Tier a human has **decided** is data, and is stored.

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

## Privacy

**No evidence artifacts are stored.** `evidenceRefs` and `intake[].label` hold pointers and notes —
never a document, a screenshot, an export, or a transcript. This skill helps produce a Profile and a
report; it is not where an organization's evidence lives, and nothing here is built to hold it.

`confirmedBy` and `recordedBy` are new in v2, and — like the pre-existing `profile.scope.owner`,
`history[].actor`, and `actionItems[].owner` — they hold whatever name or role the user supplies.
None of these fields are validated against a directory or resolved to an identity; they are the only
personal data this store carries, and all of it is free text the user chose to put there.

The store remains what it has always been: a local file with no network path. `profile_analysis.py`
and `csfa_compat.py` are standard-library-only; nothing here calls out.

## Framework reference data (what is *not* in this file)

The 106 Subcategories, their outcome text, the 363 Implementation Examples, the Informative
References, and the Tier characterizations are **read-only bundled data** in
`references/nist-csf-2.0-core.json`. The store references them by id and never copies them.

That keeps `.csfp` files small and diffable, lets the framework data be corrected without touching
user data, and is what makes the engine framework-neutral: point `frameworkRef` at different
reference data and the same machinery applies. See `references/framework-abstraction.md`.
