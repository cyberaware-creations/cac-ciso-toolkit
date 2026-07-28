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
6. **The scope guard suppresses, it does not caveate.** Below `scopeThresholdPct` of in-scope
   Subcategories assessed, the headline coverage figure does not render with a warning beside it — a
   number with a warning beside it is still a number, and people read the number. It is replaced by
   the guard statement instead. This must bind **both** dashboards, or the suppressed figure simply
   reappears one document over, which is how a board ends up being quoted a number the operational
   view refused to show.
7. **The four-way evidence split always appears together.** `confirmed`, `evidence-pending`,
   `unrated`, `not-applicable` render as one set, never a subset — showing only "confirmed" and
   "unrated" collapses evidence-pending into unrated, which erases the exact distinction this schema
   exists to draw.
8. **Age travels with every set of ratings.** Wherever confirmed ratings are shown, their age is
   shown alongside — and where no rating in the Profile carries a confirmation date, that is said in
   words ("no rating here carries a confirmation date yet"), never rendered as a blank or a zero.
9. **Reordered is never silently reordered.** When an overlay changes row order, the dashboard
   says so *adjacent to the affected table* — not in the footer, and not only in documentation.
   A reader who is not told assumes a prioritized gap table is ordered by gap severity, because
   that is what it means everywhere else here. Where a caption asserts an ordering that the
   overlay has replaced, the caption is **replaced**, not supplemented: leaving "ordered by
   prioritized score" above AI-sequenced rows is a wrong statement, not a missing one.
   The converse also binds: a table the overlay did *not* reorder, on a Profile where an
   overlay is active, must say that too. Two views of one Profile may order by different rules;
   they may not do so without saying which.
10. **Overlay output carries its provenance on the artifact.** Dataset version and source
   status appear in the footer of every rendered page that carries overlay output, alongside
   the standing disclaimer. Draft-derived priorities presented without their status read as
   settled doctrine, and a report outlives the conversation that produced it.

---

## Operational dashboard (CISO and team)

`renderers/render_operational.py` · working view, dense, built for the people closing the gaps.

### Header
Profile name, scope summary (org units, threat types), owner, `generated.today`, framework name and
version, and the tracked count (`tracked` of `framework.subcategories`).

### Overall coverage
A card above the heatmap, under the **same** scope guard as the executive headline (Rule 6). Below
`scopeThresholdPct` assessed, no coverage percentage renders — the guard statement takes its place,
with the tracked count and the four-way evidence split beside it. At or above threshold, the
achieved-against-target percentage renders with completeness and the same evidence split alongside.

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

### Age and revisits
Two blocks under one heading.

**Age of confirmed ratings, by Function** — dated count, median age, oldest, and (only when
`ageThresholdDays` is actually configured) how many exceed it. A Function with no dated confirmations
says so in its row rather than showing zeros. The threshold in force is stated once, as a hint above
the table, not repeated per cell.

**Revisit** — every confirmed rating that cannot be shown to predate material recorded against it:
Subcategory, outcome, confirmed date (or "undated"), the source date, the source id(s), and **why**
the row is there. Two reasons, and they are not interchangeable: `newer-material` means the
comparison was made and the material won; `undated-confirmation` means there was no basis for a
comparison, because the rating carries no `confirmedAt` — the state every rating migrated from a v1
Profile is in. Both earn a second look; only the first is a claim about chronology.

The empty state names what "nothing to revisit" actually means — no confirmed rating has material
recorded against it that it cannot be shown to predate — which is a different claim from "nothing
has been assessed."

Ratings never expire on their own (`references/schema.md`); this section prompts a second look when
something changed, not staleness for its own sake.

### Coverage by source
One card per intake record: id, label, source date, recorded date, recorder, and how many of its
subjects are confirmed versus still pending, plus a chip per subject colored by evidence state.
Answers "what did that review actually cover?" — a question a per-Subcategory pointer list cannot
answer. Chips carry only a Subcategory id and its state, never the outcome text: this block grows
without bound as intake accretes over the life of the Profile, and the text is already duplicated in
the gap table and the queue.

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

### The headline figure, or the scope guard
Below `scopeThresholdPct` of in-scope Subcategories assessed, no overall percentage renders — a
labelled guard card takes its place, stating the assessed/in-scope count and why the figure is
withheld, sourced from `evidence.scopeGuard.statement`. At or above threshold, the
achieved-against-target percentage renders as the headline, with completeness beside it. This must
read the same as the operational dashboard's own guard on the same numbers (Rule 6) — a board seeing
a figure the working team's own dashboard refuses to show is how a suppressed number gets quoted
back anyway.

### How much of this is known, and how old is it
The four-way evidence split (confirmed / evidence-pending / unrated / not applicable), plus age:
median, oldest, the count older than the configured `ageThresholdDays`, and a count of ratings
currently flagged `revisit`. Captioned explicitly that ratings do not expire — age is reported, the
reader judges. Where no confirmed rating in the Profile carries a `confirmedAt` yet, the section says
so in words rather than rendering empty cells.

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
