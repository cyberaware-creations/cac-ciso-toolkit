# Dashboards — content specification

Two audiences, two artifacts, one data source. Both are rendered from the `analyze` JSON and
**nothing is computed in a renderer**. If a number a dashboard needs is not in `analyze`, add it to
`analyze` (T10), not to the renderer — otherwise two views of the same Profile can disagree.

Both outputs are single self-contained HTML files: inline CSS and JS, no external assets beyond a
Google Fonts link with a system fallback. That link is one outbound request when the file is opened
— pass `--offline` to drop it and render on the system font stack instead, for anything going to a
client or an air-gapped machine. Both carry the footer from `assets/brand.md`.

---

## Rules that bind both dashboards

These exist because each one is a way a coverage report can mislead:

1. **Never render a bare percentage.** Every coverage figure shows `x/y` alongside it. "62%" hides
   whether it is drawn from 4 Subcategories or 106.
2. **Untargeted is not zero, and not full.** Where `percent` is `null`, render "not yet targeted"
   with the hatch treatment — never 0%, never 100%, never an empty cell that reads as fine.
3. **Show completeness beside coverage.** `assessed` and `targeted` out of `inScope`. A 90% coverage
   figure over 8 assessed Subcategories is not a 90% programme.
4. **Tiers are never a score.** No averaging, no "Tier 2.4", no trend line implying maturity
   progression. Render the Tier label and the verbatim characterization, nothing more.
5. **Not applicable is visible, not hidden.** A reader must be able to see what was scoped out, and
   ideally why. Silently dropping N/A rows is how scope creep hides.

---

## Operational dashboard (CISO and team)

`renderers/render_operational.py` · working view, dense, built for the people closing the gaps.

### Header
Profile name, scope summary (org units, threat types), owner, `generated.today`, framework name and
version, and the tracked count (`tracked` of `framework.subcategories`).

### Coverage heatmap — Function × Category
The centrepiece. A grid of Categories grouped under their Function.

- Each cell: Category id, coverage `x/y`, percentage, colored by the sequential ramp in
  `assets/brand.md`.
- **Current/Target toggle** — switch the cell value between achieved-against-target (coverage) and
  the raw Target profile, so a user can see *what we aimed at* separately from *how far we got*.
- Untargeted Categories: hatched, labeled "not yet targeted".
- Function row totals from `coverage.byFunction`; every Function appears even with no assessments.
- Cells link to the gap table filtered to that Category.

### Gap table
Sortable, default order = `gaps` as emitted (prioritized score descending, id ascending).

Columns: Subcategory id · outcome text · Current → Target · gap · priority · prioritized score ·
status · last reviewed.

- **Row expand** reveals the Implementation Examples for that Subcategory — the concrete "how to
  close this" prompts. All 106 Subcategories have at least one, so the expander is never empty.
- Rows with `current: null` show "unassessed", not "0" — the distinction is the point.
- Sortable by every column; the prioritized score is the honest default because it is the only
  ordering that accounts for both size of gap and importance.

### Gap drill-down
Expanding a gap row reveals, in order: **authored guidance** (what mature looks like, next steps,
pitfalls — or the Function slant where no deep entry exists), then the **NIST Implementation
Examples**. Deep entries are marked with a patina left border so it is obvious which Subcategories
carry hand-written guidance and which fall back to the template.

Guidance is scale-aware: tier-transition prose appears only on the 0–4 tool scale. See
`scale-and-scoring.md`.

### Next 90 days
A worksheet, not a plan. Top gaps by prioritized score, each with a recommended first move drawn
from the authored guidance, and **blank Owner and Due columns** for filling in with a team. Ported
from section 8 of the web tool's report. Once a line has an owner and a date it belongs in the
action plan, tracked by `action add` — the blank columns are a prompt, not a record.

### Attention lists
Six panels, from `attention`, each labeled with the question it answers:

| Panel | Source | Question |
|---|---|---|
| Largest gaps | `largestGaps` | Is anything being done about the top five? |
| Never reviewed | `neverReviewed` | Why has nobody looked at these at all? |
| Stalest | `stalest` | Is this rating still true, or just old? |
| Unowned actions | `unownedActions` | Who owns this? |
| Past due | `pastDueActions` | Slipped, or abandoned? |
| Accepted gaps | `acceptedGaps` | Is the acceptance still valid? |

Never-reviewed and stalest are **separate panels**, never merged — they are different failures.

### Action plan
Table of `actionItems.items`: id, title, linked Subcategories, owner, milestone, target date,
status. Unowned rows and past-due rows are marked inline as well as appearing in their panels.

### Footer
The brand footer, plus the framework citation and the `generated.today` stamp.

---

## Executive dashboard (board)

`renderers/render_executive.py` · the board view. Fewer numbers, more meaning. Composes
`ciso-board-translation` for the language.

### Header
Profile name, the period under review, and the snapshot being compared against.

### Function-level rollup
Six tiles (one per Function), each: Function name, coverage `x/y` and percentage, delta versus the
last snapshot from `diff.coverage.byFunction`. Untargeted Functions read "not yet targeted".

No Category detail here — a board does not work at Category level.

### Tier trajectory
Current Tier, and the previous Tier if a snapshot records one, with the **verbatim NIST
characterization** for the current Tier shown alongside.

Rendered as a labeled position on a four-point scale, explicitly annotated as a *characterization of
rigor, not a maturity score*, citing NIST's own "notional illustration" framing. If the Profile has
no Tier set, say "not characterized" — do not infer one.

### Top gaps, translated
The top five from `attention.largestGaps`, each with a **business-outcome statement** rather than
the Subcategory text.

- Translations come from the optional `--translations` JSON, produced by `ciso-board-translation`.
- Absent a translation, render the `_common.PLACEHOLDER` prompt — a visible instruction to run the
  translation skill, never a silent fallback to raw framework language. Framework text in front of a
  board is the failure this slot exists to prevent.

#### The `--translations` sidecar contract

```json
{
  "executiveSummary": "One paragraph in the board's language. Optional.",
  "gaps": {
    "PR.AA-01": "Leavers keep system access for weeks, so a departing employee can still reach patient records.",
    "GV.SC-07": "We cannot say which suppliers hold our data, so a breach at one of them would surprise us."
  },
  "decisions": ["Optional extra board asks, appended to the derived ones."],
  "asOf": "2026-10-01"
}
```

**`gaps` must be nested.** A flat `{"PR.AA-01": "..."}` map at the top level is the natural guess and
it is wrong — it parses, the render reports success, and every narrative silently reverts to the
placeholder, which is how a board deck ends up looking finished and saying nothing. The renderer now
rejects a sidecar with no usable keys and names this specific mistake, but the shape above is the
contract. `subcategories` is accepted as an alias for `gaps`.

All four keys are optional individually; at least one must be present.

### What changed
From `diff`: coverage movement overall and by Function, Subcategory changes worth board attention,
and actions opened and closed since the last snapshot. This is the continuity that makes a quarterly
report a narrative instead of a fresh set of numbers.

### Decisions needed
Derived from the attention lists — unowned actions, past-due actions, and accepted gaps due for
revalidation, framed as asks: what needs funding, ownership, or an explicit acceptance from this
board.

### Footer
Brand footer, framework citation, and the build stamp.
