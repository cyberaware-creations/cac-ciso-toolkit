---
name: vendor-register
description: >-
  Maintain a defensible register of third-party arrangements — who the organisation depends on,
  for what, how critical that dependency is, whether the agreement commits them to anything,
  whether we could leave, and whether any of it has been re-checked lately. The spine is NIST
  CSF 2.0 GV.SC, the Cybersecurity Supply Chain Risk Management Category; regimes such as DORA
  are overlays selected by the applicability profile, never the frame. Contract-centric, not
  vendor-centric: one provider commonly holds several arrangements at different criticalities,
  and a vendor-shaped register forces one criticality per company. Criticality is DERIVED by
  tracing what an arrangement supports back to a business workflow, then CONFIRMED by a named
  person — derivation proposes, a human assigns, and an unattributed final level is refused. A
  dependency the trace cannot reach is `untraced`, never `low`, and cannot be ordered against
  the scale at all. Emits no vendor risk score, deliberately and under an eval: findings belong
  in risk-register and are scored once, there. Use when asked to record a supplier or vendor
  arrangement, work out how critical a third party is, check what a contract commits a provider
  to, test or record an exit strategy, track subprocessors and fourth parties, find which
  arrangements are overdue for assessment, or build the third-party section of a board pack.
  NOT for scoring a vendor, accepting a finding (exceptions-register), or rating a control
  (nist-csf).
---

# vendor-register

A system of record for **third-party arrangements** — not for vendors, and not for scores.

## Two object types, because one is not enough

| Object | Is | Carries |
|---|---|---|
| `vendor` | The legal provider | Name, jurisdiction, group parent, identifiers, **declared** designations |
| `arrangement` | One agreement, one set of services | `vendorRef`, `entityRef`, services, what it supports, criticality, owner, dates, requirement coverage, exit strategy, subprocessors |

**The register is contract-centric.** One provider commonly holds several arrangements at
different criticalities — the same cloud provider behind a critical production dependency and
a marketing sandbox. A vendor-shaped store forces one criticality per company and produces a
register that is wrong in the way an assessor notices first.

**An arrangement is refused without an owner.** `GV.SC-02` requires roles be established with
suppliers, and every escalation this register raises has to land on somebody. An arrangement
nobody owns is the one that goes stale.

## Criticality: derived, then confirmed

```bash
python3 scripts/vendor_register.py classify store.vnd --arrangement VA-001 \
  --context ctx.json --confirm high --by "Head of Engineering" \
  --basis "FY26 criticality review; the historian stops both lines"
```

The walk traces what an arrangement supports back to a workflow whose criticality the business
has declared — `arrangement → system/component → workflow`, two hops, following NISTIR 8179's
Process E in shape. The workflows come from `business-context` crown jewels, through
`--context`. That is where they belong: how critical a workflow is, is a business judgement.

```
VA-001  derived high
  trace: SCADA gateway -> Plant historian (Dublin)
  assigned high by Head of Engineering on 2026-08-07 (scale v1)
```

**Derivation proposes; a person assigns.** `--confirm` without `--by` is refused. An
unattributed final level is what 8179 E.5 exists to prevent, and it cannot be defended to an
assessor by pointing at the tool that produced it.

**A confirmed level may differ from the derived one, and that is a finding rather than an
error.** Process E exists for consistency across layers, so a disagreement is information. It
escalates as `criticality-conflict` and is never silently resolved either way.

### `untraced` is a value, not a gap

**This is the most important rule in the skill.** A dependency the walk cannot trace to a
declared workflow is `untraced` — never `low`:

- `untraced` is **not a member of the scale**, and `criticality_rank` **raises** on it rather
  than returning a number. One `sorted(key=rank)` placing it at the bottom would silently
  downgrade every untraceable arrangement, and the resulting board table would look complete.
- A **truncated** walk returns `untraced` *and* records `truncated`. A confident level from an
  unfinished walk is the worst outcome available.
- With **no `--context` at all**, every arrangement derives `untraced`. Correct and loud: the
  skill works standalone, and it does not pretend to know what it cannot see.
- `untraced` and `unclassified` are **different**: nobody classified it, versus we tried and
  could not finish. The actions differ, so the triggers do.

### The scale is a setting

NISTIR 8179 declines to prescribe levels, so this does not either. `low, moderate, high` ships
as the default; `set-scale` replaces it. Existing values are **not remapped** — that would
restate somebody's judgement in words they did not choose — and a change that would orphan a
confirmed level is refused, naming the arrangements. Every assigned value records the
`scaleVersion` it was assigned under.

## The acts, and what each refuses

| Act | Refuses without |
|---|---|
| `classify --confirm` | A named person for the final level |
| `test-exit` | What was actually exercised, and why |
| `review-requirements` | An evidence reference per requirement |
| `record-subprocessor` | An effective date |
| `retire` | Where the data went, and when deletion was **confirmed** — **terminal** |

**Documented and tested are separate fields with separate dates.** A written but never-exercised
exit strategy is the sector's most common paper control, and collapsing the two into one
"has an exit strategy" boolean is exactly what lets it pass.

**`retire` is terminal.** A resumed relationship opens a *new* arrangement carrying
`--prior VA-004`. The closed exit and deletion record is the evidence that `GV.SC-10` was
satisfied at the time; reopening it would rewrite an answer somebody already gave about data
that has already gone. A successor pointing at a *live* arrangement is refused — two running at
once are two arrangements, and the register should show both.

## Escalations, and why they fire at every level

Cadence scales with criticality: **high annually, moderate every two years, low on trigger
only.** But the triggers fire at **every** level regardless — and `low` having no cadence is
precisely why. A subprocessor introduced into a low-criticality chain is the event that makes
it stop being low, and nothing else would catch it.

`untraced` satisfies **no** cadence rule. Treating it as "no cadence applies" would make it
quieter than `low`, which is backwards.

## Reading evidence — this section IS the reading layer

Everything above is bookkeeping. This is the part that saves time: read what the vendor
supplied, work out what it genuinely covers, and produce the questions still worth asking.

**You may propose. You may never satisfy.** A model reading a trust page and ticking
requirements produces a register full of green derived from marketing copy — worse than an
empty register, because it looks finished and nobody re-checks a page of ticks. The engine
enforces this; the instructions below are how to work inside it.

### 1. Tier the artifact before reading its content

Identify what it *is* before what it *says*, because the tier decides whether anything it says
can close a question:

| It is | Tier |
|---|---|
| SOC 2 Type II, ISO 27001 certificate **with its Statement of Applicability**, penetration test report, regulatory examination finding | **T1** |
| Executed DPA, a clause in the signed agreement, a security addendum | **T2** |
| Completed questionnaire, trust centre, security whitepaper | **T3** |
| Privacy policy, website, status page, marketing material | **T4** |

```bash
python3 scripts/vendor_register.py ingest store.vnd --arrangement VA-001 \
  --kind soc2-type2 --tier T1 --source "auditor PDF, received 2026-02-10" \
  --scope "the hosting platform, excluding the payments subservice" \
  --period-start 2025-01-01 --period-end 2025-12-31
```

**T1 refuses without a scope and a period, and you should not fight it.** Read the scope
section and the period from the report and record what it actually says — including the
exclusions. A SOC 2 that excludes the subservice organisation running our workload has not
covered our workload, and that exclusion is usually the most valuable sentence in the document.

**A bridge letter is T3.** It is a management assertion, not an audited artifact, and it does
not extend the currency of the T1 it accompanies.

### 2. Propose, with a citation

```bash
python3 scripts/vendor_register.py propose store.vnd --arrangement VA-001 \
  --requirement contract-terms.incident-notice --evidence EV-001 \
  --citation "SOC 2 section IV, control CC7.3, tested with no exceptions" \
  --by "reading layer"
```

`--requirement` takes a **question key** (`battery.question`, as printed by `ask --format json`)
so the proposal subtracts from the right question. Free text is accepted and simply subtracts
from nothing.

`--citation` is required and must point at something a person can go and read: a section, a
control reference, a clause number. "The report covers this" is not a citation.

**Proposing against a T3 or T4 is refused outright.** Do not look for a way round it. Those
tiers exist to tell you what to *ask*.

### 3. Say what a document does not cover, in these words

When an artifact does not reach a question, record it as a note rather than a proposal, and
phrase it the same way every time so it reads consistently across a register:

> *The SOC 2 covers the hosting platform for 2025 and does not address subprocessor
> notification; the report's scope section excludes it.*

Name the document, name what it does cover, and name what it does not. "Not covered" alone
tells the next reader nothing about whether somebody looked.

### 4. A person assesses

```bash
python3 scripts/vendor_register.py assess store.vnd --arrangement VA-001 \
  --by "R. Calder" --confirm PR-001 --confirm PR-002 \
  --reject PR-003 --why "the report describes the vendor's own testing, not an independent test"
```

This is the only act that closes anything, and it refuses without a name. Rejections are
retained — that a claim was examined and refused is a record worth having.

### 5. Ask for what remains

```bash
python3 scripts/vendor_register.py ask store.vnd --arrangement VA-001 --context ctx.json
```

Every question names why it is being asked and the `GV.SC` outcome it serves. Every skipped
battery prints its §2.4 sentence with the declarer and the date, so an assessor can tell a
question ruled out of scope from one nobody asked.

**An empty result prints a sentence, never a blank page.**

### Fetching public material

Trust centre, security page, sub-processor list, status history — all **T3 or T4**, always with
`--retrieved`. **Nothing behind a login or a click-through NDA**, which is where most real audit
reports live. Document upload is the primary path and fetching is the supplement.

### The walkthrough, end to end

```
ask   → 7 open                      nothing supplied yet
ingest  a SOC 2 as T1
propose three questions, cited
ask   → 7 open                      ← the reading layer changed NOTHING
assess  --by "R. Calder" --confirm PR-001 PR-002 PR-003
ask   → 4 open                      ← a named person closed three
```

That third line is the whole boundary. If proposing ever moves the count, something is wrong.

## What this skill will not do

**It emits no vendor risk score.** Every commercial third-party tool does, and it is the same
failure this suite refuses everywhere: a generated number that looks like an assessment, that
nobody can reproduce, and that disagrees with the register which actually owns scoring.
Findings go to `risk-register` and are scored once, there, under L×I with an appetite to judge
them against.

This is enforced by `evals/no-vendor-score.sh`, in two halves — nothing *emitted* is named like
a score, and no shipped file multiplies or averages a criticality against a count or a severity
— because a score renamed to `attentionIndex` escapes the first check and not the second.

It also does not accept a finding (`exceptions-register`), rate a control (`nist-csf`), write
board prose (`ciso-board-translation`), or decide materiality (`incident-materiality`).

## Surfaces, and the colour split

```bash
cd renderers
python3 render_operational.py --in analysis.json --out operational.html
python3 render_board.py --in analysis.json --out board.html --translations vendor.board.json
```

**Criticality is RAG on the operational view** — a genuine triage aid for a reader who knows
the scale and is deciding what to look at this week.

**On the board view it is a classification**, in the measure colour, carrying its word. RAG is
reserved there for what needs a decision: an overdue assessment, an untested exit, an untraced
dependency. Management by exception — a well-managed critical arrangement needs nothing from
the board, and a board scanning twelve red rows reads twelve problems and acts on none.

`untraced` is neutral on **both**, always with its word. It is not a severity and must never
borrow one.

## Multi-entity

Every arrangement carries `entityRef`, defaulting to the org. A register spanning legal entities
**refuses** to render a single-organisation view without an attributed `consolidation` block —
same shape and same reasoning as `board-pack`. A consolidated view is legitimate when a human
declares it by name and says why; it is a silent merge otherwise, and the declaration is
printed so a consolidated view never looks single-entity.

## Not legal advice

This tool structures a record. It does not determine regulatory scope, and the regime overlays
name obligations without interpreting them for your circumstances.
