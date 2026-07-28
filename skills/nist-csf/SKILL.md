---
name: nist-csf
description: >-
  Assess, track, and report a cybersecurity programme against the NIST
  Cybersecurity Framework 2.0 as an Organizational Profile that persists in a
  local file and shows how posture changes over time. Rates each of the 106
  Subcategories Current vs Target on a 0-3 achievement scale, computes
  deterministic gap analysis and risk-weighted prioritization, rolls coverage up
  by Function and Category, characterizes CSF Tiers, keeps an append-only history
  with rationale, takes named review snapshots with a what-changed diff, and
  tracks an owned action plan — reported as operational and executive dashboards.
  Bundles the full CSF 2.0 Core with all 363 Implementation Examples. Use
  whenever the user mentions NIST CSF, CSF 2.0, a Current or Target Profile, an
  Organizational Profile, framework coverage or gaps, a cybersecurity framework
  assessment, security programme maturity or posture, CSF Tiers, where the
  programme stands against a standard, or reporting framework progress to a
  board — even if they don't say "NIST". Not for scoring individual risks,
  likelihood and impact, or risk appetite (use risk-register), and not for
  writing policies.
---

# NIST CSF Organizational Profile

Turn the NIST Cybersecurity Framework 2.0 into a working system of record: where the programme
stands, where it should be, what the gap is worth, and what changed since last quarter. It lives in
a local file, remembers why every rating moved, and reports to both the team and the board.

`risk-register` answers *"what are our top risks and are they within appetite?"* This skill answers
*"how complete is our programme against a recognised standard, and what's the plan to close the
gap?"* They share the CSF Subcategory ID space, so a gap here becomes a scored risk there.

## What "good" looks like here

Each of these is where CSF work usually goes wrong:

1. **Scope before ratings.** An unscoped Profile produces numbers nobody can defend. Establish
   purpose, org units, threat types, and owner first — they change what a sensible Target is.
2. **Target is a decision, not a maximum.** A Profile with all 106 Targets at 3 is a wish list. NIST
   is explicit that Targets reflect risk-based prioritization. Ask what they would fund first.
3. **Tiers are rigor, never a maturity score.** See the guardrail below. This is the single most
   recognisable tell that a CSF report wasn't written by someone who reads NIST.
4. **Coverage must never flatter.** Nothing targeted means *no coverage figure*, not 0% and not
   100%. Every figure travels with its fraction. The engine enforces this; don't work around it.
5. **The reasons are the product.** Ratings without rationale are a spreadsheet. Rationale is what
   makes quarter-over-quarter a narrative a board can follow.

## The file is the source of truth

Everything persists in one local `.csfp` file (JSON, schema v2 — a v1 file loads and normalizes
automatically): the Profile definition, per-Subcategory assessments and their attribution, an
**append-only history**, an **append-only intake log** of recorded sources, **named snapshots**, and
the action plan. Dashboards are generated on demand and never stored — a rendered dashboard goes
stale the moment a rating moves. Full model: `references/schema.md`.

The framework itself is read-only bundled data in `references/nist-csf-2.0-core.json` — 6 Functions,
22 Categories, 106 Subcategories, 363 Implementation Examples, Informative References, and verbatim
Tier text from NIST CSWP 29. The store references it by id and never copies it.

## Always use the script

Never compute a gap, a coverage percentage, or a priority ranking by hand or by eye — two people
must get the same numbers from the same Profile.

```bash
python3 scripts/profile_analysis.py validate     # confirm the bundled Core is intact
python3 scripts/profile_analysis.py self-test     # 304 checks against a fixed fixture
```

Every mutating command appends a history event and rewrites a schema-valid file, so the audit trail
is enforced by tooling rather than by discipline.

## Core workflows

**A — Build or extend the Profile** (scope, seed Targets, assess Current).
**B — Run an assessment review** (the recurring ritual: update, surface, decide, snapshot, report).
**0 — Record a source**, mid-conversation, whenever one comes up (seconds, writes no ratings).
**C — Confirm from the queue**, its own session, working what 0 accreted.

All four are in `references/assessment-and-review.md`, with the exact command for every step. Most
sessions are A, B, or C. Start by asking which.

Quick shape of A:

```bash
python3 scripts/profile_analysis.py init --name "Acme Corp" --out acme.csfp --owner CISO
python3 scripts/profile_analysis.py quickstart-target acme.csfp        # baseline Target = 2
python3 scripts/profile_analysis.py set acme.csfp PR.AA-01 --target 3 --rationale "..."
python3 scripts/profile_analysis.py intake add acme.csfp --label "..." --subjects PR.AA-01
python3 scripts/profile_analysis.py set acme.csfp PR.AA-01 --current 1 \
  --source in-0001 --confirmed-by "CISO" --rationale "..."
```

`quickstart-target` **seeds blanks only** — it will not overwrite a Target someone set deliberately,
and reports how many it left alone. Pass `--force` to reset those too.

`--rationale` is **required** on material changes — rating moves, target moves, accepting a gap,
claiming an outcome met, and scoping something out. The tool refuses without it. That refusal is a
feature; don't route around it by editing the file directly.

## Building a Profile from fragments

Not every Profile gets built in one sitting. Evidence accretes — a review here, a debrief there —
and rating from memory when nothing was actually confirmed is how a Profile ends up making claims
nobody can defend.

```bash
# The moment a source comes up, log it — seconds, writes no ratings
python3 scripts/profile_analysis.py intake add acme.csfp \
  --label "architecture review with infra team" --subjects ID.AM-01 ID.AM-02 \
  --source-date 2026-03-14 --recorded-by "Darren"

# Later, in its own session: work the backlog, five at a time
python3 scripts/profile_analysis.py queue acme.csfp
python3 scripts/profile_analysis.py set acme.csfp ID.AM-01 --current 2 \
  --source in-0001 --confirmed-by "Darren" --rationale "..."
```

`set --current` **refuses without `--source` and `--confirmed-by`** — a rating needs a named source
and a named person, not a memory of a conversation. The tool can enforce that both are *present*; it
cannot prove either is *true*. Never invent a `--confirmed-by` name or point `--source` at a record
that doesn't reflect what actually happened, just to get past the refusal — ask who is deciding this,
and log the source for real first if it isn't recorded yet. `--target` is not gated the same way: a
Target is a risk decision already covered by `--rationale`, and `quickstart-target` needs to seed it
in bulk. Full workflows: 0 and C in `references/assessment-and-review.md`.

## Reporting

```bash
# 1. One command produces every derived number
python3 scripts/profile_analysis.py analyze acme.csfp --today 2026-10-01 > analysis.json

# 2. Operational view — CISO and team
python3 renderers/render_operational.py --in analysis.json --out coverage.html

# 3. Executive view — compose board language first
#    Run ciso-board-translation over the top gaps, save as {"gaps": {"PR.DS-01": "..."}}
python3 renderers/render_executive.py --in analysis.json --translations board.json --out board.html
```

`analyze` is the only place derived data is computed; the renderers are projection-only. If a
dashboard needs a number that isn't in the analyze JSON, add it to `analyze` — never to a renderer,
or two views of one Profile can disagree.

**Board language comes from `ciso-board-translation`, always.** This skill never hand-rolls
executive prose. Without `--translations` the executive dashboard shows a labelled placeholder
rather than putting raw framework wording in front of a board.

Deliver dashboards as files. Persist board-facing views as artifacts.

## Coming from the csf-assessment web tool

Existing `.csfa` assessments are first-class inputs, handled by `scripts/csfa_compat.py`:

```bash
# Migrate an assessment into a tracked Profile (history, snapshots, per-Subcategory targets)
python3 scripts/csfa_compat.py convert assessment.csfa --out profile.csfp

# Or just reproduce the tool's gaps CSV, byte-for-byte
python3 scripts/csfa_compat.py gaps assessment.csfa --out gaps.csv
```

Conversion **keeps the source 0–4 scale** rather than rescaling — a "2" on that scale is not a "2"
on the native 0–3 scale, and silently converting would change what every rating asserts. Read
`references/scale-and-scoring.md` before discussing a converted Profile: its 1–4 labels borrow NIST
Tier vocabulary, which is a practical convention and **not** NIST doctrine. Say so if it goes near an
assessor.

That module is a frozen port of the web tool's engine, kept separate from `profile_analysis.py` on
purpose. Byte-parity on the gaps CSV is a contract — don't "improve" the ported functions.

## Closing gaps: authored guidance

`analyze` attaches guidance to every gap row from `references/guidance.json`:

- **15 Subcategories** carry hand-authored deep guidance — what mature looks like, concrete next
  steps, and common pitfalls.
- The rest get a Function-level slant describing where gaps in that Function usually hide.
- Both sit alongside the NIST Implementation Examples, which all 106 Subcategories have.

`analyze` also emits a **`playbook`** block: the top gaps with a recommended first move and blank
Owner/Due, rendered as the "Next 90 days" worksheet on the operational dashboard. Fill it in with the
team, then promote each line to a tracked action with `action add` — an item without an owner and a
date will still be there next quarter.

## Handing gaps to the risk register

```bash
python3 scripts/profile_analysis.py export-gaps acme.csfp --out gaps.csv
python3 ../risk-register/scripts/score_register.py import-gaps gaps.csv --into acme.rr
```

Dedupes on `csfSubcategoryId`, so re-exporting after a review updates the matching risks rather than
duplicating them. Note that the CSV contract names its rating columns `current_tier`/`target_tier`
for historical reasons — they carry **achievement ratings, not CSF Tiers**. Never let that column
name reach a reader.

## The Tier guardrail

Tiers characterize the **rigor** of cybersecurity risk governance (GOVERN) and risk management
(IDENTIFY, PROTECT, DETECT, RESPOND, RECOVER) practices. NIST presents them as a *notional
illustration* (CSWP 29 §3.2, Appendix B).

**Never:**
- compute or infer a Tier from the ratings
- average Tiers, or report a fractional Tier ("Tier 2.4")
- trend Tiers as a maturity progression, or call a higher Tier "better" unconditionally
- describe the Profile's coverage percentage as a maturity score

**Do:** set Tiers as a deliberate judgment with the user, reading the verbatim NIST characterization
in the Core's `tiers` block. Progression to a higher Tier is warranted only when risks or mandates
are greater, or when a cost-benefit analysis supports it — NIST's own framing.

```bash
python3 scripts/profile_analysis.py set-tier acme.csfp --overall 2 --function GV=3 PR=2 \
    --rationale "Board review: governance is repeatable; delivery is inconsistent across units."
```

`--rationale` is required and a fractional Tier is refused. The command never reads the ratings —
there is no code path from coverage to a Tier, by design.

Two strings live in the Core's `tiers` block and they are not interchangeable. `guardrail` is
**model-facing** and must never be rendered; `readerNote` is the sentence written for whoever is
holding the report. A board deck that tells its own reader what "must never be rendered" is the
report talking to its author.

## Routing between the three skills

| The user wants | Skill |
|---|---|
| Where does the programme stand against the framework; where are the gaps | **this skill** |
| A specific risk scored by likelihood × impact; is it within appetite | `risk-register` |
| A CSF gap turned into a tracked, scored risk | `export-gaps` here → `import-gaps` there |
| Board-ready language for any of it | `ciso-board-translation` |

If the ask is ambiguous — "we did a CSF assessment, what now?" — ask whether they want to *track the
framework position* (here) or *turn findings into scored risks* (register). Both is a normal answer,
and the export path serves it.

## Framework neutrality

The engine is framework-neutral: a framework is data, not code. Nothing in the computation path
hard-codes the CSF Function names — they come from the loaded framework. Don't write prose or code
that assumes six Functions called GOVERN/IDENTIFY/…; ISO 27001 and CIS attach later as data plus
crosswalks. See `references/framework-abstraction.md`.

## Reference files

| File | What it covers |
|---|---|
| `references/schema.md` | The `.csfp` contract, attribution and intake, evidence states, coverage arithmetic, material-change rules |
| `references/scale-and-scoring.md` | The two scales, the Tier-vocabulary caveat, both scoring models |
| `references/guidance.json` | Authored guidance: 15 deep entries, Function slants, tier transitions |
| `references/assessment-and-review.md` | Workflows 0, A, B, and C, command by command |
| `references/dashboards.md` | What each dashboard must contain, and the rules binding both |
| `references/framework-abstraction.md` | The multi-framework seam and the crosswalk plan |
| `references/nist-csf-2.0-core.json` | The bundled Core — read-only framework data |
| `references/cold-start-rank.json` | 37 Subcategories ranked for the queue's cold-start band — CAC editorial judgment, not NIST's; carries its own record of what informed it |
| `assets/brand.md` | Limen tokens, the coverage ramp, and the mandatory footer |
| `examples/example-profile.csfp` | A small worked Profile, used by `self-test` |
| `examples/example-profile-v2.csfp` | A Profile exercising every v2 state: intake, attribution, a revisit, an age spread, below-threshold scope |

Every generated deliverable carries the footer **"A Cyber Aware Creation · Not affiliated with
NIST"**. This skill renders NIST-derived content; that line is what keeps a coverage report from
reading as a NIST-endorsed assessment.
