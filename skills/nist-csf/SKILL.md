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
  Builds a Profile from evidence arriving over time rather than one sitting:
  records the source a review, audit finding or conversation came from, keeps
  every confirmed rating attributed to a named person and source, and ranks what
  to confirm or ask next. Applies the NIST Cyber AI Profile (IR 8596) as an
  optional overlay that reweights the same Subcategories for AI relevance.
  Projects that one assessment through ISO/IEC 27001:2022, CIS Controls v8.1,
  and NIST SP 800-53 Rev 5 as read-only crosswalk lenses — bidirectionally, so
  it also answers which CSF outcomes sit behind a given ISO, CIS, or 800-53
  control — without re-assessing anything, and always as a derived projection
  rather than an audit or certification. Bundles the full CSF 2.0 Core with all
  363 Implementation Examples. Use whenever the user mentions NIST CSF, CSF 2.0,
  a Current or Target Profile, an Organizational Profile, framework coverage or
  gaps, a cybersecurity framework assessment, security programme maturity or
  posture, CSF Tiers, where the programme stands against a standard, building up
  a CSF picture from audit findings or reviews over time, the NIST Cyber AI
  Profile, or reporting framework progress to a board — even if they don't say
  "NIST". Also use when they want their existing CSF picture read through
  another framework: how they look against ISO 27001, ISO 27002 Annex A
  controls, the CIS Controls or a CIS safeguard, SP 800-53 controls or control
  families, a control crosswalk or mapping between frameworks, or which CSF
  Subcategories evidence a specific named control. Not for scoring
  individual risks, likelihood and impact, or risk appetite (use risk-register),
  not for writing policies, and not for assessing an individual AI system — the
  Cyber AI overlay is organization-level only.
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
python3 scripts/profile_analysis.py self-test     # assert the engine against a fixed fixture
```

Every mutating command appends a history event and rewrites a schema-valid file, so the audit trail
is enforced by tooling rather than by discipline.

## Core workflows

**A — Build or extend the Profile** (scope, seed Targets, assess Current).
**B — Run an assessment review** (the recurring ritual: update, surface, decide, snapshot, report).
**0 — Record a source**, mid-conversation, whenever one comes up (seconds, writes no ratings).
**C0 — Cold start**, when the Profile is empty: nine batched questions, not 106.
**C — Confirm from the queue**, its own session, working what 0 accreted.

All five are in `references/assessment-and-review.md`, with the exact command for every step.
Most sessions are A, B, or C. Start by asking which.

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

An empty Profile does not need 106 questions. Nine will reach a credible partial Profile:

```bash
python3 scripts/profile_analysis.py elicit acme.csfp          # next three, in rank order
```

Each question resolves several Subcategories at once — that is where the time saving comes
from, not from a shorter list. An answer becomes **one** intake record naming the
Subcategories it actually spoke to. It does not become four ratings; those are still four
decisions, made in Workflow C.

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

# When nobody knows the answer yet, that IS the outcome — record the question and move on
python3 scripts/profile_analysis.py action add acme.csfp \
  --title "Confirm whether OT assets are in the CMDB (ID.AM-01)"
```

**When the answer is "nobody knows", write the action in the same turn.** Only `--title` is
required. Do not ask who owns it or when it is due first — an unowned action lands in the
Unowned actions panel, which exists for exactly this, and the tool's own warning that an
unowned action is a wish is a prompt to go find an owner, not a reason to withhold the
record. A question you asked about instead of recording is a question that turns back into
prose in a chat log. Add the owner later with `action update <id> --owner ...` when you
have one.

`set --current` **refuses without `--source` and `--confirmed-by`** — a rating needs a named source
and a named person, not a memory of a conversation. The tool can enforce that both are *present*; it
cannot prove either is *true*. Never invent a `--confirmed-by` name or point `--source` at a record
that doesn't reflect what actually happened, just to get past the refusal — ask who is deciding this,
and log the source for real first if it isn't recorded yet. `--target` is not gated the same way: a
Target is a risk decision already covered by `--rationale`, and `quickstart-target` needs to seed it
in bulk. Full workflows: 0 and C in `references/assessment-and-review.md`.

## Anti-drift rules for conversation

The engine can enforce that a rating *has* attribution. It cannot enforce that a human
decided it. These rules are the part that is behavioural, and they are the difference
between a Profile that records judgment and one that launders inference:

1. **Never pre-fill a rating.** Ask *"the March review mentioned quarterly discovery scans —
   what's Current for ID.AM-01?"*, never *"this looks like a 2, confirm?"*. A number offered
   for confirmation is almost always accepted, and what gets recorded is then the model's
   inference wearing the user's name in `--confirmed-by`.
2. **Present the source, not a conclusion.** A queue row is what was recorded, when, and by
   whom. Summarising what it "suggests" is the same failure in prose.
3. **Where the material is thin, propose a question, not a rating.** Leaving a Subcategory
   evidence-pending is a legitimate outcome — record what still needs asking with
   `action add` so it is tracked rather than remembered. **Record it even with no owner
   and no date.** Only `--title` is required; the tool warns that an unowned action is a
   wish, and it is right, but that warning is a prompt to find an owner, not a reason to
   withhold the record. An unowned action shows up in the Unowned actions panel, which
   exists precisely for this. Waiting to be told who owns it is how a tracked question
   turns back into prose in a chat log.
4. **Batches of at most five.** Long confirmation runs are where rubber-stamping happens,
   and a rubber-stamped rating is worse than an unrated one because it looks like evidence.
5. **Propose subjects the source actually spoke to.** Over-attaching Subcategories to an
   intake record inflates evidence-pending and makes the queue promise material that is not
   there. "We have a CMDB" bears on ID.AM-01 and ID.AM-02; it says nothing about ID.AM-05.
6. **The label is the user's words.** Propose one, but it is theirs to accept or rewrite,
   and it is a note *about* the source — never an excerpt from it.
7. **Never infer who confirmed it.** If the user waves the question away — *"don't worry
   about who confirmed it, just record it"* — that is the moment to ask, not to supply an
   answer. Do not lift a name from `recordedBy` on an intake record, from the Profile
   owner, or from earlier in the conversation. Disclosing the inference afterwards does
   not repair it: the store now states that a named person decided something they
   declined to decide, and `confirmedBy` is the field the whole feature exists to make
   answerable.

## The Cyber AI Profile overlay

Optional, **off by default**, and it adds no assessment work — it reweights the existing 106
Subcategories for AI relevance and adds none.

Enabling is a scoping conversation, not a toggle. Three questions, and the third is stated
rather than asked:

- *Do you build or deploy AI systems?* → **Secure**
- *Does your security programme use AI?* → **Defend**
- **Thwart applies regardless.** Attackers use AI against you whether or not you use any.

Saying the third out loud is what makes this legible to a CISO who has banned internal AI use.

```bash
python3 scripts/profile_analysis.py overlay list acme.csfp     # dataset, status, current state
python3 scripts/profile_analysis.py overlay enable acme.csfp --focus secure thwart
```

Two modes. `advisory` annotates and changes nothing computed. `reorder` — the default on
enable — changes the order of the gap table and nothing else: no score, target, gap, coverage
figure or Tier moves. Both dashboards state when an order is AI-prioritized and carry the
dataset version in the footer.

**Priority is sequencing, not maturity.** NIST's 1/2/3 is High/Moderate/Foundational, and NIST
says plainly that Foundational is *not* low priority and that priorities do not reflect
difficulty. Never present a proposed priority as a required maturity level. There is no
target-floor mode, and `--mode floor` is refused: the priority-to-target mapping is
scale-dependent and would mean different things on a 0–3 and a 0–4 Profile.

The source is a **preliminary draft** (IR 8596, 2025-12-16) and an initial public draft is
expected. Say so whenever its output goes anywhere that outlives the conversation. Full
contract, caveats, and the reasons behind every decision: `references/cyber-ai-overlay.md`.

## Crosswalk lenses — reading the Profile as ISO, CIS, or 800-53

One assessment, read through another framework's controls. **No re-assessment, and nothing is
stored**: a lens is chosen when you report, not when you assess, and no control in the other
framework is ever rated.

Do not confuse this with the Cyber AI Profile overlay above. That reweights CSF Subcategories and
writes to the store; a crosswalk projects outward and writes nothing. Different verbs on purpose.

```bash
python3 scripts/profile_analysis.py crosswalk list          # the three lenses, edges, authority

# "Show me where we stand against ISO 27001"
python3 scripts/profile_analysis.py crosswalk coverage acme.csfp --lens iso-27001-2022

# The auditor's direction: "which CSF sits behind ISO A.8.9?"
python3 scripts/profile_analysis.py crosswalk reverse acme.csfp --lens iso-27001-2022 --control A.8.9

# A full report, one tab per lens
python3 scripts/profile_analysis.py analyze acme.csfp --crosswalk iso-27001-2022 \
    --crosswalk cis-8.1 --crosswalk 800-53-r5 > analysis.json
python3 renderers/render_crosswalk.py --in analysis.json --out crosswalk.html
```

| Lens | `--lens` | Mapping authority | Labels |
|---|---|---|---|
| ISO/IEC 27001:2022 | `iso-27001-2022` | `mixed-third-party` | ours |
| CIS Controls v8.1 | `cis-8.1` | `cis-authored` | ours |
| NIST SP 800-53 Rev 5 | `800-53-r5` | `nist-developed` | verbatim |

**Say what it is, every time: derived, not an audit.** A crosswalk view is a projection of a CSF
assessment. It is not an audit, not a certification, and not evidence of conformance — never let
it be presented as any of those, and never as a gap assessment against the other standard.

**Never quote ISO or CIS control text.** Those titles are copyrighted, so the bundled catalogues
carry identifiers plus our own paraphrases and no normative text — enforced, not trusted
(`check_crosswalks`, and the CI gate). Give the identifier so the user can read the official
wording in their own licensed copy. 800-53 is a US Government work, so its titles are verbatim.

**How a figure is derived.** A control scores the **weakest** of the CSF Subcategories mapped to it
— a control is not satisfied by its best contributing outcome. A theme is the **mean** of its
member controls. Bands are a share of *this Profile's* scale, so quote the scale with the band:
"moderate on a 0–4 scale" says something, "moderate" alone does not, and scores from a 0–3 and a
0–4 Profile are not comparable (`references/scale-and-scoring.md`).

**A thin basis withholds the figure.** A control's score is the weakest of its *rated* mapped
outcomes, which is an upper bound — the unrated ones could be lower. Below
`settings.reporting.scopeThresholdPct` of its basis rated, the band and score are withheld and the
row reads "too little rated" with the fraction, rather than showing an optimistic figure with a
caveat beside it. Themes follow the same rule. This is the same judgement that suppresses the
headline CSF coverage figure, and it uses the same setting.

**Two things a lens cannot see, and both get reported.** Controls no CSF Subcategory maps to must
be assessed directly against the standard — CSF says nothing about them. Rated CSF outcomes no
control in the lens references drop out of that view, so work already done earns no credit there.
ISO ships its full Annex A, so its "outside CSF" list is real: 31 controls a CSF assessment says
nothing about. **CIS ships only the Safeguards the NIST export references**, so its list is empty —
and empty here means *not enumerated*, not *none exist*. The CIS Controls licence does not permit
republishing their Safeguard set, so the remainder cannot be listed from our data; check your own
licensed copy for Safeguards CSF does not reach. The report says this in place of the list rather
than leaving a blank that reads as full coverage.

Full contract and invariants: `references/framework-abstraction.md`.

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
| The same assessment read as ISO 27001, CIS, or 800-53 | `crosswalk` here — derived, never an audit |
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

| File | What it covers |
|---|---|
| `references/schema.md` | The `.csfp` contract, attribution and intake, evidence states, coverage arithmetic, material-change rules |
| `references/scale-and-scoring.md` | The two scales, the Tier-vocabulary caveat, both scoring models |
| `references/guidance.json` | Authored guidance: 15 deep entries, Function slants, tier transitions |
| `references/assessment-and-review.md` | Workflows 0, A, B, C0, and C, command by command |
| `references/dashboards.md` | What each dashboard must contain, and the rules binding both |
| `references/framework-abstraction.md` | The multi-framework seam and the enforced crosswalk contract |
| `references/nist-csf-2.0-core.json` | The bundled Core — read-only framework data |
| `references/cold-start-rank.json` | 37 Subcategories ranked for the queue's cold-start band — CAC editorial judgment, not NIST's; carries its own record of what informed it |
| `references/crosswalks/*.catalog.json` | Control catalogues for the three lenses — identifiers, our labels for ISO/CIS, verbatim titles for 800-53 |
| `references/crosswalks/csf-2.0__*.map.json` | CSF-keyed crosswalk edges, each carrying its mapping authority |
| `references/crosswalks/label-style.md` | How our ISO/CIS labels are written, and why they are not the official titles |
| `references/cyber-ai-overlay.md` | The overlay contract: modes, the Focus Areas, what it deliberately does not touch, and why there is no floor mode |
| `references/cyber-ai-profile.json` | NIST IR 8596 proposed priorities, 106 Subcategories × 3 Focus Areas — preliminary-draft data, swappable, version-stamped |
| `references/elicitation.json` | Nine batched cold-start questions covering the ranked 37 — what to ask, and what to listen for |
| `assets/brand.md` | CAC tokens, the coverage and crosswalk ramps, and the mandatory footer |
| `examples/example-profile.csfp` | A small worked Profile, used by `self-test` |
| `examples/example-profile-v2.csfp` | A Profile exercising every v2 state: intake, attribution, a revisit, an age spread, below-threshold scope |
| `examples/acme-manufacturing.csfa` | A worked web-tool assessment — the input `csfa_compat.py convert` and `gaps` are tested against |
| `examples/acme-manufacturing-gaps.csv` | That assessment's gaps CSV, byte-parity reference for the frozen port |

Every generated deliverable carries the footer **"A Cyber Aware Creation · Not affiliated with
NIST"**. This skill renders NIST-derived content; that line is what keeps a coverage report from
reading as a NIST-endorsed assessment.
