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
- Rendering notes

## Operational dashboard (CISO / team)

The working view — dense, complete, for the people managing the risk:

- **Headline tiles:** total risks, by residual band, over-appetite count, by status.
- **Heat matrix** (see below), inherent/residual toggle.
- **Full register table** — RAG-colored, sortable/filterable by status, category, theme, response,
  band. Show inherent + residual exposure and velocity direction.
- **Attention lists:** over-appetite risks; risks past `reviewDate`; acceptances past
  `revalidationDate`; unowned risks.
- **Owner load:** count and worst-band of open risk per owner.

## Executive dashboard (board)

Fewer things, bigger, narrative — for a board that reads themes and direction, not line items:

- **Top strip:** total exposure posture in a sentence, over-appetite count **with trend arrow vs
  last snapshot**, count of stale acceptances due for re-validation.
- **Themes rollup:** each theme with its risk count, worst residual band, and direction. This is the
  board's mental model — ~6 themes, not 40 rows.
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
python3 renderers/render_dashboard.py <register.rr> [out.html] [--today YYYY-MM-DD] [--translations t.json]
python3 renderers/render_board.py     <register.rr> [out.html] [--today YYYY-MM-DD] [--translations t.json]
python3 renderers/render_report.py    <register.rr> [out.html] [--today YYYY-MM-DD] [--translations t.json]
```

- `--today` is the date staleness is measured against (`reviewDate`, `revalidationDate`,
  `expiryDate`). Defaults to the system date; pass it explicitly for a reproducible "as of" view.
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
  and per-risk velocity, trend series, snapshot diff with rationales, staleness flags, owner load,
  attention lists, brand tokens. Add a new renderer on top of it rather than re-deriving.

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
