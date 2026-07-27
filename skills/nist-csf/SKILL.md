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

Everything persists in one local `.csfp` file (JSON, schema v1): the Profile definition, per-
Subcategory assessments, an **append-only history**, **named snapshots**, and the action plan.
Dashboards are generated on demand and never stored — a rendered dashboard goes stale the moment a
rating moves. Full model: `references/schema.md`.

The framework itself is read-only bundled data in `references/nist-csf-2.0-core.json` — 6 Functions,
22 Categories, 106 Subcategories, 363 Implementation Examples, Informative References, and verbatim
Tier text from NIST CSWP 29. The store references it by id and never copies it.

## Always use the script

Never compute a gap, a coverage percentage, or a priority ranking by hand or by eye — two people
must get the same numbers from the same Profile.

```bash
python3 scripts/profile_analysis.py validate     # confirm the bundled Core is intact
python3 scripts/profile_analysis.py self-test     # 79 assertions against a fixed fixture
```

Every mutating command appends a history event and rewrites a schema-valid file, so the audit trail
is enforced by tooling rather than by discipline.

## Two core workflows

**A — Build or extend the Profile** (scope, seed Targets, assess Current).
**B — Run an assessment review** (the recurring ritual: update, surface, decide, snapshot, report).

Both are in `references/assessment-and-review.md`, with the exact command for every step. Most
sessions are one or the other. Start by asking which.

Quick shape of A:

```bash
python3 scripts/profile_analysis.py init --name "Acme Corp" --out acme.csfp --owner CISO
python3 scripts/profile_analysis.py quickstart-target acme.csfp        # baseline Target = 2
python3 scripts/profile_analysis.py set acme.csfp PR.AA-01 --target 3 --rationale "..."
python3 scripts/profile_analysis.py set acme.csfp PR.AA-01 --current 1 --rationale "..."
```

`--rationale` is **required** on material changes — rating moves, target moves, accepting a gap,
claiming an outcome met, and scoping something out. The tool refuses without it. That refusal is a
feature; don't route around it by editing the file directly.

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
| `references/schema.md` | The `.csfp` contract, coverage arithmetic, material-change rules |
| `references/assessment-and-review.md` | Workflows A and B, command by command |
| `references/dashboards.md` | What each dashboard must contain, and the rules binding both |
| `references/framework-abstraction.md` | The multi-framework seam and the crosswalk plan |
| `references/nist-csf-2.0-core.json` | The bundled Core — read-only framework data |
| `assets/brand.md` | Limen tokens, the coverage ramp, and the mandatory footer |
| `examples/example-profile.csfp` | A small worked Profile, used by `self-test` |

Every generated deliverable carries the footer **"A Cyber Aware Creation · Not affiliated with
NIST"**. This skill renders NIST-derived content; that line is what keeps a coverage report from
reading as a NIST-endorsed assessment.
