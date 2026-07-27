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

Imported risks land **provisional**: seeded scores, framework wording, and held out of board-facing
views until you reword them with `set-text` or rescore them with `set-score`. See
`references/csf-import.md`.

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
python3 scripts/score_register.py set-status <reg.rr> <id> closed --why '...'
python3 scripts/score_register.py add-theme <reg.rr> --id third-party --name 'Third-Party & Supply Chain'
python3 scripts/score_register.py set-theme <reg.rr> <id> third-party --why '...'
python3 scripts/score_register.py snapshot <reg.rr> --label 'Q3 2026 Board Review' --note '...'
python3 scripts/score_register.py export-csv <reg.rr> --out register.csv
```

**Material changes** (score moves, acceptances, closures) require `--why` — the rationale is what
makes the log an audit trail and a board narrative rather than a bare diff, so always capture it from
the user. Full rules, trend/velocity derivation, and the review workflow:
`references/history-and-review.md`.

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

`--today` sets the date staleness is judged against; `--translations` supplies the board language
from `ciso-board-translation`. **Without `--translations` the narrative slots render as marked
placeholders — never hand-write board prose into a renderer.** Sidecar shape and a worked example:
`references/dashboards.md` and `references/example-translations.json`.

Dashboards are self-contained, Limen-branded HTML (tokens in `assets/brand.md`; layouts in
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

## Reference files

- `references/schema.md` — full data model (risks, themes, acceptance, history, snapshots), taxonomy,
  matrix sizes, band thresholds, v1→v2 migration.
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
- `assets/brand.md` — Limen Labs palette, fonts, CVD-safe risk-band colors.
- `assets/report-layout.md` — the board PDF report structure.
- `scripts/score_register.py` — scoring, summary, CSF import, **and persistence** (add / set-score /
  accept / set-status / add-theme / set-theme / snapshot / export-csv, all append-only-history and
  schema-safe). Standard library only; `self-test` verifies parity with the reference engine.
- `renderers/` — `render_dashboard.py` (operational working view), `render_board.py` (executive board
  dashboard), `render_report.py` (printable board report), over a shared `_common.py` derivation
  layer. All three take the register path as an argument; nothing about a client is hardcoded.
