---
name: vendor-register
description: >-
  Two jobs, and the second is the one people reach for daily: RECORD third-party arrangements —
  who the organisation depends on, for what, and how critical that dependency is — and
  INTERROGATE the ones already recorded. Answers "what does this agreement actually commit them
  to": whether an MSA, master services agreement, DPA, security addendum or signed contract
  commits a provider to a breach or incident notification window and within what period, what
  audit or assurance rights we hold and when they were last exercised, what the exit and
  data-deletion terms are, and who the subprocessors are. **Use it even when the contract cannot
  be found or read** — that is precisely what it is for: it emits the dated question to send and
  names the clause to look for, instead of generalising about what such agreements usually say.
  A notification window nobody has read is an open question, never a fact. The spine is NIST CSF
  2.0 GV.SC, the Cybersecurity Supply Chain Risk Management Category; regimes such as DORA are
  overlays selected by the applicability profile, never the frame. Contract-centric, not
  vendor-centric: one provider commonly holds several arrangements at different criticalities,
  and a vendor-shaped register forces one criticality per company. Criticality is DERIVED by
  tracing what an arrangement supports back to a business workflow, then CONFIRMED by a named
  person — derivation proposes, a human assigns, and an unattributed final level is refused. A
  dependency the trace cannot reach is `untraced`, never `low`, and cannot be ordered against
  the scale at all. Evidence is tiered: only an audited artifact or a signed commitment may
  satisfy a requirement, and a questionnaire or a trust page generates questions and closes
  nothing. Emits no vendor risk score, deliberately and under an eval: findings belong in
  risk-register and are scored once, there. Use when asked what a contract, MSA or DPA commits a
  provider to, whether a supplier owes us a breach notification window or audit rights, to record
  a supplier or vendor arrangement, work out how critical a third party is, test or record an
  exit strategy, track subprocessors and fourth parties, find which arrangements are overdue for
  assessment, or build the third-party section of a board pack. NOT for scoring a vendor,
  accepting a finding (exceptions-register), or rating a control (nist-csf).
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

## When somebody asks what a contract commits a provider to

This is the most common live question — *"does our MSA with them actually commit them to a
breach notification window?"* — and it usually arrives **without the contract**. Answer it here,
in this order, and do not answer it any other way.

1. **Check the register first.** If the arrangement is recorded, `ask` already knows whether
   `contract-terms.incident-notice` is open, satisfied, or resting on evidence that has aged.
   *Satisfied* means a named person read the executed document and cited the clause — that is an
   answer. *Open* means nobody has, which is also an answer and a more useful one than a guess.

   ```bash
   python3 scripts/vendor_register.py ask register.vnd --arrangement VA-001
   ```

2. **If the document is not to hand, do not generalise.** Notification windows vary — 72 hours,
   "without undue delay", five business days, or nothing binding at all — and reciting that range
   answers nothing about *this* agreement while sounding like it did. The register's whole
   purpose is to tell those apart.

3. **Emit the question instead.** The battery already carries it, worded to be sendable and to
   degrade honestly when the answer is "none":

   > *What is the executed document, and which clause, that commits this provider to notifying us
   > of a security incident — and within what period?*

4. **When the document does arrive**, tier it, propose against it with a citation, and let a
   named person assess. An MSA or a DPA is **T2** — a contractual commitment, which may satisfy.
   A trust page saying the same thing is **T4** and satisfies nothing.

5. **If the arrangement is not in the register at all**, that is the finding. Record it with
   `add-arrangement`, then run `ask`.

The same shape answers the neighbouring questions: audit rights (`contract-terms.audit-right`),
the subprocessor list, and the exit terms. Never infer a contract term. A commitment nobody has
read is an open question, and this register exists to keep it looking like one.

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

## Commands

Every command the engine accepts, in the order a register is actually built. Six of these
appeared in no shipped document until v0.81.0 — including `init`, without which there is no
register at all — and `tools/check-commands.py` now fails the build if that recurs (BL-192).

```bash
# Set up, and record who you depend on
python3 scripts/vendor_register.py init acme.vnd --org "Acme Manufacturing" \
    --prepared-by CISO --scope-note "UK entities only"
python3 scripts/vendor_register.py add-vendor acme.vnd --name "Contoso Ltd" \
    --jurisdiction "US-DE" --group-parent "Contoso Global" --by CISO
python3 scripts/vendor_register.py add-arrangement acme.vnd --vendor V-001 \
    --name "Payments platform" --supports "Order capture" --by CISO
python3 scripts/vendor_register.py set-scale acme.vnd --levels low moderate high --by CISO

# Criticality: derivation proposes, a named person assigns
python3 scripts/vendor_register.py classify acme.vnd --arrangement VA-001 \
    --context ctx.json --confirm high --by "R. Calder" --basis "board minute 2026-06-11"

# The reading layer — tier the artifact, propose with a citation, a person assesses
python3 scripts/vendor_register.py ingest acme.vnd --arrangement VA-001 --kind soc2-type2 ...
python3 scripts/vendor_register.py propose acme.vnd --arrangement VA-001 ...
python3 scripts/vendor_register.py assess acme.vnd --arrangement VA-001 --by CISO --confirm PR-001
python3 scripts/vendor_register.py ask acme.vnd --arrangement VA-001 --context ctx.json
python3 scripts/vendor_register.py review-requirements acme.vnd --arrangement VA-001
python3 scripts/vendor_register.py record-subprocessor acme.vnd --arrangement VA-001 ...

# Exit, succession and retirement — the lifecycle acts
python3 scripts/vendor_register.py test-exit acme.vnd --arrangement VA-001 --by CISO ...
python3 scripts/vendor_register.py document-exit acme.vnd --arrangement VA-001 \
    --note "90-day transition, data returned in CSV" --on 2026-07-01 --by CISO
python3 scripts/vendor_register.py succeed acme.vnd --arrangement VA-002 --prior VA-001
python3 scripts/vendor_register.py retire acme.vnd --arrangement VA-001 ...
python3 scripts/vendor_register.py review acme.vnd --arrangement VA-001 ...

# Read the register, and hand what it found to the skills that own it
python3 scripts/vendor_register.py analyze acme.vnd --context ctx.json --today 2026-08-10 \
    --out analysis.json
python3 scripts/vendor_register.py export-findings acme.vnd --out findings.json
python3 scripts/vendor_register.py export-roi acme.vnd --out roi.json
python3 scripts/vendor_register.py self-test
```

**`document-exit` records what an exit would actually involve** — the note, the date and the
person — and is a different act from `test-exit`, which records that one was rehearsed. A
documented exit nobody has tested is a plan; a tested exit is evidence, and the register keeps
the two apart rather than letting either stand for the other.

**`succeed` links a replacement arrangement to the one it replaces**, so the history of a
dependency survives a change of provider. Without it a re-contracted supplier looks like a new
dependency with no past, which is exactly the arrangement an assessor asks about.

**`export-findings` is one-way and idempotent**, and carries no likelihood, impact or score —
`risk-register` scores once, there. `analyze` derives and reports; it never records.

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
