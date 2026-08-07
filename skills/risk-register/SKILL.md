---
name: risk-register
description: >-
  Build, score, maintain, and report a NIST-aligned cybersecurity risk register
  that persists in a local file and tracks how risk changes over time. Turns
  messy inputs (a CSF gap export, an assessment, rough notes, or a conversation)
  into properly-worded risks (NISTIR 8286 event statements), deterministic
  Likelihood×Impact scoring and banding (SP 800-30), risk-appetite flagging
  (CSF 2.0 GV.RM), an append-only change log with rationale, named review
  snapshots, and reporting — heat matrix, themes, trend, and operational and
  executive/board dashboards. Use whenever the user mentions a risk register,
  risk log, risk matrix, heat map, risk assessment, residual vs inherent risk,
  risk treatment or acceptance, over-appetite risks, tracking risk over time,
  running a risk review, or reporting risk to the board — even if they don't say
  "NIST." Not for writing security policies, running a maturity assessment
  itself, or generic project risk logs.
---

# Risk Register

Turn identified security risks into a tracked, scored, board-ready register aligned to NIST
guidance — one that lives in a local file, remembers how it changed, and reports to both the team
and the board. This skill does the parts a spreadsheet can't: wording risks so they're defensible,
scoring them identically every time, tracking change with reasons, and translating the result into
language a board acts on.

## What "good" looks like here

A register earns its keep only if these are true, and each is where people usually fail:

1. **Risks are written as events, not topics.** "Phishing" is a topic. "If employees are targeted by
   credential-harvesting phishing, then stolen passwords enable account takeover" is a risk. NISTIR
   8286 wants this if-then framing because you can't score or treat a topic. Always draft it for them.
2. **Scoring is deterministic.** Two people scoring the same risk must get the same band — so banding
   is done by the script, never by eye. See [Scoring](#scoring-always-use-the-script).
3. **It's a living record, not a snapshot.** The value compounds through change tracking: what moved,
   when, and *why*. Every material change is logged. See [Maintaining the register](#maintaining-the-register-the-core-loop).
   The same record is what lets the register **raise its own hand**: `escalations` surfaces what
   worsened since the last review without anyone remembering to look — detection is automatic,
   action is not.
4. **The output speaks to its reader.** A technical register bores a board; a board summary
   frustrates an engineer. Generate both. Use `ciso-board-translation` for the executive layer.

## The file is the source of truth

Everything persists in one local `.rr` file (JSON, schema v2): the risk data, an **append-only
change log**, **named review snapshots**, theme definitions, and settings. A skill run is stateless;
the file is the memory. Dashboards are **generated on demand** from the file, never stored in it (a
rendered dashboard goes stale the instant a risk changes; the data and snapshots don't). Full model:
`references/schema.md`.

## Two core workflows

**A — Build or update the register** (add/score/treat risks). **B — Run a risk review** (the
recurring ritual that surfaces what's stale or over appetite, captures decisions, snapshots, and
reports to the board). Most sessions are one or the other. Workflow B is in
`references/history-and-review.md`; the build workflow is below.

## Build workflow

```
- [ ] 1. Set up: `init` — client, assessor, matrix size (default 5×5), appetite (default medium)
- [ ] 2. Intake risks — from a CSF gap CSV (run the import) or elicited in conversation
- [ ] 3. Draft each risk as a NISTIR 8286 event statement (`set-text` for imported ones);
         set owner, category, theme, response
- [ ] 4. Assign inherent + residual likelihood × impact (1..matrixSize)
- [ ] 5. Score with scripts/score_register.py — never band by hand
- [ ] 6. Log every material change with a rationale; write the file back
- [ ] 7. Report — heat matrix, dashboards, board summary — as needed
```

### Step 2 — Intake

**From a CSF gap assessment (common path).** The `nist-csf` skill's `export-gaps` writes a gap CSV
(`subcategory_id, function_id, category_id, current_tier, target_tier, priority, subcategory_text,
note`). Map it to candidate risks:

```bash
# Preview first — --into alone writes nothing.
python3 scripts/score_register.py import-gaps <gaps.csv> --into <existing.rr>
# Then apply.
python3 scripts/score_register.py import-gaps <gaps.csv> --into <existing.rr> --write
```

Imported risks land unreviewed in **two independent ways**, each with its own flag, because each is
cleared by a different act:

- `provisionalTitle` — the title is still framework wording ("Identities … **are managed**", a
  control objective phrased as a good thing). Cleared **only** by `set-text`. While set, board-facing
  renderers print a placeholder instead of the title.
- `provisionalScore` — the scores are a seed off the gap's priority that nobody has assessed. Cleared
  **only** by `set-score`.

Rescoring does **not** authorize the wording for a board, and rewording does not make the seeded
numbers an assessment. Details: `references/csf-import.md`.

Seeds inherent scores from each gap's `priority` (critical→5, high→4, medium→3, low→2), carries the
CSF subcategory as the dedupe key, and — with `--into` — updates matching risks instead of
duplicating. Seeded scores are a starting point; refine with the user. Details:
`references/csf-import.md`.

**From conversation.** No export? Elicit directly: for each concern, ask the asset, the threat/event,
the consequence, what's in place today, and who owns it — then draft the event statement yourself.

### Step 3–4 — Draft and rate (judgment)

Wording and rating are where you add value over a template:

- **Inherent** = before/without today's controls. **Residual** = with them working as described.
  Residual should be below inherent wherever a real control exists; if they're equal, either the
  control is missing or the risk is being **accepted** — make that explicit (`response.type: accept`).
- Choose the response honestly: `transfer` (e.g. insurance) moves *financial* loss but rarely reduces
  likelihood or impact, so a transferred risk often stays over appetite. Don't let a response type
  flatter the residual.
- Set a `theme` (the board-rollup axis) and a `reviewDate`. Keep likelihood/impact within 1..matrixSize.
- **Accepting a risk requires structured acceptance** — approver, justification, expiry,
  re-validation date — not just a note. This is the audit-defensible layer (DORA RTS Art. 3(d),
  NYDFS §500). See `references/schema.md` → Structured acceptance.

### Step 5 — Scoring (always use the script)

Never compute bands or over-appetite flags yourself — thresholds scale with matrix size and
hand-banding drifts:

```bash
python3 scripts/score_register.py score <register.rr>          # readable table
python3 scripts/score_register.py score <register.rr> --json   # scored JSON for rendering
python3 scripts/score_register.py self-test                    # verify engine parity anytime
```

`--json` adds `inherentExposure/Band`, `residualExposure/Band`, `overAppetite`, and a `summary`
block. Feed it to the renderers in step 7.

#### What the treatments cost

`summary.treatmentCost` totals `response.cost` and is what the board pack prints. Three
things about it are deliberate:

- **Open risks only.** A closed risk's treatment is already paid for; counting it would
  overstate what is still being asked for.
- **`unpriced` always travels with the total.** Six of nine risks priced reads very
  differently from nine of nine, and the figure is a **floor, not the bill**. Both the
  script's own output and the board pack's label carry the denominator — a total without it
  is the false precision this toolkit refuses everywhere else.
- **`settings.currency` is optional and never guessed.** Set it (`"GBP"`, `"USD"`, `"EUR"`)
  and the total renders with it; leave it and the number renders bare, labelled *currency not
  recorded*. A total shown in the wrong currency is worse than one shown in none, because
  only the second is obviously incomplete to whoever reads it.

### Step 6 — Maintaining the register (the core loop)

Every change follows the same discipline so the file stays canonical and its history stays intact:
**load → apply the change → append a history event → write back.** Do this through the script's
mutation commands rather than editing the JSON by hand — each one appends the history event and
writes a schema-valid file for you, so append-only history and determinism are enforced by tooling,
not by memory:

```bash
python3 scripts/score_register.py init <reg.rr> --client 'Acme Corp' --assessor 'CISO' \
    --matrix 5 --appetite medium --scope-note '...'
python3 scripts/score_register.py add <reg.rr> --title '...' --il 4 --ii 5 --rl 2 --ri 4 \
    --category PR --owner '...' --theme identity --response mitigate --why '...'
python3 scripts/score_register.py set-text <reg.rr> <id> --title '...' --description '...' --why '...'
python3 scripts/score_register.py set-score <reg.rr> <id> --residual L I --why '...'
python3 scripts/score_register.py accept <reg.rr> <id> --approver '...' --justification '...' \
    --revalidate 2027-01-31 --expiry 2027-07-31 --why '...'
python3 scripts/score_register.py confirm <reg.rr> <id> --why '...' --review 2027-05-31
python3 scripts/score_register.py set-status <reg.rr> <id> closed --why '...'
python3 scripts/score_register.py add-theme <reg.rr> --id third-party --name 'Third-Party & Supply Chain'
python3 scripts/score_register.py set-theme <reg.rr> <id> third-party --why '...'
python3 scripts/score_register.py snapshot <reg.rr> --label 'Q3 2026 Board Review' --note '...'
python3 scripts/score_register.py set-escalation <reg.rr> --dwell-days 90 --why '...'
python3 scripts/score_register.py export-csv <reg.rr> --out register.csv
```

### What the register raises on its own

Everything above needs somebody to type it. `escalations` is the one thing that does not:

```bash
python3 scripts/score_register.py escalations <reg.rr> --today 2026-07-31
```

Four triggers — a **crossed band**, **sustained drift** without a crossing, a **long dwell over
appetite**, and a **lapsed acceptance** — each printed with the comparison that fired it. It
**exits 0 either way**: this flags, it does not gate, and nothing downstream refuses to run
because something escalated. Nothing is auto-rescored either; a lapsed acceptance does not move
a residual, because residual is an assessment and reverting one on a date would invent one.

Thresholds are per register and travel inside snapshots. Tune them with `set-escalation`, which
takes a `--why` and logs the change — a threshold that quietly rewrote which risks escalate
would report a calmer quarter without a single risk having improved.

**`revalidate` is deliberately not here.** `exceptions-register` owns the acceptance lifecycle:
re-validation as a recorded act, the DORA inventory, the whole clock. This skill keeps the
lightweight marker and feeds it one-way through `export-acceptances`, which now names an expired
acceptance on stderr and **still exports it** — a dead acceptance silently missing from the
intake is worse than one that arrives flagged. Two homes for one clock is how the two homes come
to disagree.

**Material changes** (score moves, acceptances, closures, confirmations) require `--why` — the
rationale is what makes the log an audit trail and a board narrative rather than a bare diff, so
always capture it from the user. Full rules, trend/velocity derivation, and the review workflow:
`references/history-and-review.md`.

`confirm` records that a risk was reviewed and **nothing changed** — it resets the risk's confirmation
age and moves no score, status or band. Use it instead of re-entering an identical score, which would
log a `score-changed` event where no score changed. `--review` optionally books the next review date
in the same breath, because that is the actual review-meeting workflow.

Two refusals worth knowing before you type them:

- **Date flags take canonical `YYYY-MM-DD` only.** `--review` (on `add` and `confirm`) and
  `--revalidate` / `--expiry` / `--accepted` (on `accept`) reject both `2027-2-01` and `20270201`.
  Those fields are compared as plain strings downstream, so an unpadded date made an
  eight-month-overdue review render as on time. A register that already carries a non-canonical date
  still loads and renders — only new writes are refused.
- **`confirm` and `accept` refuse while `provisionalScore` is set**, because no affirming event may
  attach to a score nobody has assessed. `set-score` is the way through: it affirms the number *and*
  clears the flag. A provisional *title* only warns. Both: `references/schema.md`.

### Step 7 — Reporting

Generate on demand from the scored data:

- **`.rr` file** — the register as pretty JSON (schema v2). Portable source of truth.
- **CSV** — the register table for spreadsheets.
- **Heat matrix + operational dashboard** — dense working view (tiles, matrix, filterable table,
  attention lists, owner load).
- **Executive/board dashboard** — themes, top risks with business-outcome translations, trend since
  last snapshot, "what changed," decisions needed.
- **PDF board report** — cover, executive summary, residual heat map, register table, over-appetite
  focus, footer stamp.

Generate the HTML with the renderers. Each one takes the register as an argument and derives
everything — themes, trend, staleness, owner load — from it:

```bash
python3 renderers/render_dashboard.py <reg.rr> working-view.html --today 2026-07-26
python3 renderers/render_board.py     <reg.rr> executive.html    --today 2026-07-26 --translations t.json
python3 renderers/render_report.py    <reg.rr> board-report.html --today 2026-07-26 --translations t.json
```

`--today` sets the reference date every age and deadline is judged against, and defaults to today's
date **in UTC** — the register's own history timestamps are UTC, and comparing them against a local
date gave confirmations a negative age that read as fresh. Every artifact stamps the zone beside the
date. `--age-threshold DAYS` (default 180) sets the confirmation-age band width; it is reporting
furniture and rescores nothing. `--translations` supplies the board language from
`ciso-board-translation`. **Without `--translations` the narrative slots render as marked
placeholders — never hand-write board prose into a renderer.** Sidecar shape, the confirmation-age
surfacing, and a worked example: `references/dashboards.md` and
`references/example-translations.json`.

Dashboards are self-contained, CAC-branded HTML (tokens in `assets/brand.md`; layouts in
`references/dashboards.md` and `assets/report-layout.md`). Deliver as files; persist board-facing
ones as artifacts so they survive the conversation. Every deliverable carries the footer *"A Cyber
Aware Creation · Not affiliated with NIST."*

## Board layer

For the executive summary, the theme narrative, the over-appetite story, the trend, and any "what do
we tell the board" ask, **invoke the `ciso-board-translation` skill** rather than writing board
language here. Pass it the scored summary, theme rollup, top risks, and the snapshot diff; drop its
output into the executive dashboard and the PDF. Keeping that logic in one skill means every CAC tool
tells the board story the same way — and it's the part a blank prompt can't reproduce.

## Guardrails

- **Not affiliated with NIST.** Aligns to NISTIR 8286, SP 800-30 Rev. 1, CSF 2.0 — not endorsed by
  NIST. Say so; never imply certification.
- **Structure, not data exfiltration.** Everything runs locally on the risks the user provides. Never
  suggest uploading a client's register anywhere.
- **Append-only history.** Never rewrite or delete past history events — that's what keeps the log
  defensible.
- **Don't invent risks, scores, or rationales to fill space.** A tight register of real, well-worded,
  honestly-scored risks beats a padded one.

## Rendering under a client brand

Every renderer takes `--brand FILE`:

```bash
python3 renderers/render_board.py analysis.json report.html --brand northwind.json
```

```json
{"ink": "#101820", "muted": "#5A4436", "patina": "#C0701F", "bg": "#FAF7F2",
 "measure": "#8A4B12", "measureTrack": "#EFE0D2", "patinaText": "#8A4B12",
 "wordmark": "Northwind Group", "mark": "Northwind", "whiteLabel": true}
```

**It is refused rather than approximated.** A palette that leaves body text on the dark band
below 4.5:1, or the patina kicker on the dark band below 4.5:1, is rejected with every failing pairing named — not
the first, and not silently nudged into range. `whiteLabel` drops the maker's name and keeps
the "Not affiliated with NIST" line, because one says who built the document and the other is
a statement about the world.

**What does not follow the brand, deliberately:** the RAG status ramp. Red/amber/green is a
contract with the reader about severity, not styling the client is buying. Only the shell —
ink, muted, background, patina, and the steps derived from them — moves.

## Reference files

- `references/schema.md` — full data model (risks, themes, acceptance, history, snapshots), taxonomy,
  matrix sizes, band thresholds, confirmation age and the age-affirming event taxonomy, the canonical
  date rule, v1→v2 migration.
- `references/history-and-review.md` — the maintain loop, change-log rules, trend/velocity, and the
  risk-review workflow (workflow B).
- `references/dashboards.md` — operational and executive dashboard specs, heat matrix, theme rollup,
  trend charts.
- `references/csf-import.md` — CSF gap-CSV contract, priority seeding, dedupe behavior.
- `references/example-register.rr` — worked 20-risk register (v1; import/migration + scoring fixture).
- `examples/example-register-v2.rr` — worked v2 register with themes, structured acceptance, change
  history, and a snapshot. The few-shot for the full model.
- `references/example-gaps.csv` — sample CSF gap export for testing import.
- `references/example-translations.json` — worked `ciso-board-translation` sidecar; the `--translations`
  contract for the renderers.
- `assets/brand.md` — Cyber Aware Creations palette, fonts, CVD-safe risk-band colors.
- `assets/report-layout.md` — the board PDF report structure.
- `scripts/score_register.py` — scoring, summary, CSF import, **and persistence** (add / set-text /
  set-score / accept / confirm / set-status / add-theme / set-theme / snapshot / export-csv, all
  append-only-history and schema-safe). Standard library only; `self-test` verifies parity with the
  reference engine.
- `renderers/` — `render_dashboard.py` (operational working view), `render_board.py` (executive board
  dashboard), `render_report.py` (printable board report), over a shared `_common.py` derivation
  layer. All three take the register path as an argument; nothing about a client is hardcoded.
