# Dashboards & Reporting

Two audiences, one dataset. Generate dashboards on demand from the current register (or a snapshot)
— never store rendered HTML in the `.rr` file; it goes stale the moment a risk changes. Store data
and snapshots; regenerate the view.

## Contents
- Operational dashboard (CISO / team)
- Executive dashboard (board)
- The heat matrix
- Theme rollup
- Trend charts
- Confirmation age
- Rendering notes

## Operational dashboard (CISO / team)

The working view — dense, complete, for the people managing the risk:

- **Headline tiles:** total risks, by residual band, over-appetite count, by status.
- **Heat matrix** (see below), inherent/residual toggle.
- **Full register table** — RAG-colored, sortable/filterable by status, category, theme, response,
  band. Show inherent + residual exposure and velocity direction.
- **Attention lists:** over-appetite risks; risks past `reviewDate`; acceptances past
  `revalidationDate`; unowned risks.
- **"How old these determinations are"** — the confirmation-age distribution, in its own section and
  explicitly *not* an attention list (see below).
- **Owner load:** count and worst-band of open risk per owner.

## Executive dashboard (board)

Fewer things, bigger, narrative — for a board that reads themes and direction, not line items:

- **Top strip:** total exposure posture in a sentence, over-appetite count **with trend arrow vs
  last snapshot**, count of stale acceptances due for re-validation.
- **Themes rollup:** each theme with its risk count, worst residual band, and direction. This is the
  board's mental model — ~6 themes, not 40 rows.
- **Freshness sentence** in the executive summary: how old the determinations on the page are, in one
  line, citing IDs only (see Confirmation age below).
- **Top risks (5):** by residual exposure, each with a one-line **business-outcome translation**
  (from `ciso-board-translation`) — not the technical description.
- **Trend chart:** over-appetite count and band mix across snapshots.
- **What changed since last review:** the snapshot diff (added, band moves, newly over/within
  appetite, closed) — the continuity spine.
- **Decisions needed:** acceptances to re-validate, risks needing board awareness or funding.

The executive dashboard is where `ciso-board-translation` composes in: pass it the scored summary,
the theme rollup, the top risks, and the snapshot diff; it returns the board-facing language,
including the regulatory receipts where relevant.

## The heat matrix

A `matrixSize × matrixSize` grid: impact increasing upward, likelihood increasing rightward. Each
cell is colored by its band (RAG ramp from `assets/brand.md`) and shows the count of risks whose
(likelihood, impact) land there. Provide an inherent ↔ residual toggle. Skip any risk scored above
the current matrix size (e.g. a level-5 risk after switching to 3×3) rather than indexing out of
range — the scored JSON flags these as `outOfRange: true`, so filter on that instead of re-deriving
it — and note the count, since they remain counted in the register and band totals. The board PDF
uses the residual view.

## Theme rollup

Aggregate risks by `theme`: count, worst residual band, over-appetite count, and trend direction per
theme. A risk with no theme falls into an "Unclassified" bucket — surface that so themes stay
complete.

## Trend charts

Built from snapshots (not live edits): over-appetite count over time, and residual band mix over
time (stacked). Two or three snapshots already tell a story; label the x-axis with snapshot labels
("Q1", "Q2"), not raw dates.

## Running the renderers

All three take the register as an argument and derive everything from it — themes, trend, staleness,
owner load. Nothing about a client is baked into a renderer:

```bash
python3 renderers/render_dashboard.py <register.rr> [out.html] [--today YYYY-MM-DD] [--translations t.json] [--age-threshold 180]
python3 renderers/render_board.py     <register.rr> [out.html] [--today YYYY-MM-DD] [--translations t.json] [--age-threshold 180]
python3 renderers/render_report.py    <register.rr> [out.html] [--today YYYY-MM-DD] [--translations t.json] [--age-threshold 180]
```

- `--today` is the reference date every derived age and deadline is measured against (`reviewDate`,
  `revalidationDate`, `expiryDate`, and confirmation age). **It defaults to today's date in UTC, not
  the local date** — every history `ts` is written in UTC, so comparing against a local date was
  incoherent: west of Greenwich a confirmation written this evening is dated tomorrow, which gives it
  a negative age, and `age_band` reports a negative age as `within`. A register skewed one day
  forward read as *fresher than it is*, on the board page as well as the working one.
  Pass it explicitly for a reproducible "as of" view.

  The residual is a trade, not a win, and worth stating: one reference date serves two kinds of date
  and cannot be locally correct for both. `reviewDate`, `revalidationDate` and `expiryDate` are human
  calendar commitments made in a local zone; a history `ts` is a machine timestamp in UTC. So a
  renderer west of UTC now flags a deadline up to a day early and one east of UTC up to a day late.
  That error is ≤1 day at a boundary and self-corrects tomorrow, whereas a negative age does not
  shift — it inverts, landing in the freshest band and reporting a stale register as current. Every
  artifact stamps the zone beside the date (`As of 2026-07-30 UTC`) so a reader in California is not
  silently shown tomorrow's date, and anyone who needs a deadline judged in a particular local zone
  passes `--today` explicitly. A per-register reporting timezone is deferred.

  Note the consequence of the "as of" workflow: `--today 2026-06-30` over a register confirmed in
  July legitimately puts every sound record after the reference date. The renderers state that as a
  **fact** — "dated after the reference date, so no age can be measured for them" — and never as a
  file defect. Three routes reach that state (an explicit as-of date, a genuinely wrong `ts`, clock
  skew) and no renderer can tell which; an earlier wording called it a record defect and libelled
  nine sound records on a board page. Keep any new wording on the same side of that line.
- `--age-threshold DAYS` sets the confirmation-age band width `T` on all three renderers, default
  180. It is reporting furniture and nothing else: it flags nothing, gates nothing, suppresses
  nothing, and rescores nothing. `T` is per-invocation, so `render_dashboard --age-threshold 180` and
  `render_board --age-threshold 90` over one register can tell two freshness stories with nothing
  forcing them to agree. Settings-level parity with `nist-csf`'s
  `settings.reporting.ageThresholdDays` — a register-level `T` all three renderers would read — is
  **deferred by design**, not overlooked.
- `--translations` takes the board-language sidecar from `ciso-board-translation`. **Omit it and the
  narrative slots render as visibly-marked placeholders** — the renderers never invent board prose.
  Derived figures are always complete either way. Shape (every key optional):

```json
{ "generatedBy": "ciso-board-translation", "asOf": "2026-07-26",
  "executiveSummary": "one paragraph answering the four questions",
  "risks":    { "R-003": "one-line business-outcome translation" },
  "themes":   { "third-party": "optional one-line theme narrative" },
  "decisions": ["an ask the board can vote on"] }
```

  `risks` keys are risk ids; `themes` keys are theme ids. Worked example:
  `references/example-translations.json`. Decisions derived from the data (acceptances due,
  over-appetite risks, overdue reviews) are always listed; sidecar `decisions` are appended.
- Shared derivation lives in `renderers/_common.py` (stdlib only): theme rollup, snapshot baseline
  and per-risk velocity, trend series, snapshot diff with rationales, staleness flags, confirmation
  age and its rollup, the band boundaries, the board freshness sentence, owner load, attention lists,
  brand tokens. Add a new renderer on top of it rather than re-deriving — a board-facing surface that
  copies the freshness sentence instead of calling it is how the title guard came to be enforced on
  one board artifact and not the other for a full release.

## Confirmation age

The governing principle: **operational views get the distribution, board views get one sentence.** A
board does not need an age histogram — it needs to know whether the picture in front of it is fresh.
The model itself (the four bands, the three outcomes, what affirms age) is in `references/schema.md`.

**`render_dashboard.py`** — a section headed *"How old these determinations are"*, carrying a
six-row distribution over the live register: the four bands, then `undated`, then `unreadableDate`.

- All six rows are always drawn, even at zero, because they partition the live population exactly and
  the reader is meant to add them up against the denominator in the heading. A row suppressed at zero
  also makes "0 undated" indistinguishable from "this panel does not report undated at all".
- Each band row carries an **exclusive** day range (`0–90d`, `91–180d`, `181–360d`, `over 360d`).
  Cumulative ranges over mutually-exclusive counts are false in the flattering direction: "within 360
  days" once captioned the count of determinations *past* the chosen cadence.
- The `wellBeyond` row names the IDs it counts, oldest first. Without them the row is a number the
  reader cannot act on — a risk that is stale but not over appetite, overdue, unowned or accepted
  appears on no attention card at all.
- The `within` row discloses any future-dated records inside it rather than rebanding them.
- Attention cards carry `· confirmed 42d ago · <actor>` **beside** the review date, not instead of it.
- It is **not an attention list**. Filed among them it would assert that risks inside the cadence are
  things needing attention, which is exactly the judgement the data refuses to make, and it would give
  the panel count two meanings on one screen ("flagged risks" everywhere else, "live population"
  here).
- It is deliberately **not** painted with the RAG band ramp that residual bands and ⚠ marks use.
  Colouring `wellBeyond` red would tell the reader an old determination is a critical one. Row order
  plus the explicit day range carries the ordering instead.

**`render_board.py`** and **`render_report.py`** — one freshness sentence in the executive summary,
on both the narrative branch and the placeholder branch of each. Both artifacts call the one shared
helper; neither copies it. A page whose narrative slot is a placeholder is the page most likely to be
read off the numbers alone, and a page rendered *with* board language is the one that reaches a board,
so leaving the sentence off either branch fails a check.

> Of 9 live risks: 9 confirmed within the last 90 days. Age is reported so the board can weigh it,
> and nothing on this page is rescored or re-ranked because of it.

- The clauses partition the live register, so the numbers add up to the "Of N live risks" the sentence
  opens with and a director can check them. Four band clauses, each with its future-dated records
  moved out of the band their negative age landed them in, then one clause each for future-dated,
  `undated` and `unreadableDate`. An earlier draft reported only the best and worst bands, leaving a
  board figure with a silent remainder. Zero-count clauses are dropped rather than printed as "0",
  and a dropped clause contributes nothing, so the sum still holds.
- Clauses run freshest to oldest, matching the operational panel's row order. A director and the CISO
  read the two artifacts over one register, and two orderings of one distribution is a difference the
  reader has to reconcile before trusting either.
- It cites risk **IDs only, never titles**. An imported gap carries raw CSF framework wording until
  somebody rewords it, and this line would otherwise be a fourth route for that wording onto a board
  page — the third one, the change log, shipped for a full release before anyone noticed.
- It sits in the executive summary rather than under "Decisions for the board": it is a caveat on the
  whole document, not an ask. The missed-review line under decisions is the right home for "somebody
  missed a commitment" and is unchanged.

`evals/board-safety.sh` check 9 fails if confidence vocabulary ever reaches a board-facing view. The
bands say how old a determination is; they never say how sure anyone should be that it is still true.

## Rendering notes

- Output **self-contained HTML** — inline CSS and JS, no build step, no assets on disk — so it opens
  anywhere and respects the local-only design. Use the Limen tokens in `assets/brand.md`.
- **One external request, by default:** the brand faces load from Google Fonts, so opening a report
  reaches out to `fonts.googleapis.com`. The register data never leaves the file, but the *fact that
  it was opened* does. Pass `--offline` to drop the links entirely and fall back to the system font
  stack — the layout is unchanged, since the CSS already names fallbacks. Use it for anything going
  to a client, an air-gapped machine, or a reader whose browsing you should not be sampling.
- Deliver the file to the user. If it's a dashboard they'll revisit or show the board, persist it as
  an artifact so it survives beyond the conversation.
- Every deliverable carries the footer: **"A Cyber Aware Creation · Not affiliated with NIST"** and,
  for point-in-time board views, the snapshot label and date so the reader knows exactly what
  they're looking at.
