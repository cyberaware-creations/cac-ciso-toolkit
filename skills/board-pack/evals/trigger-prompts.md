# Trigger routing checklist — `board-pack`

Confirms the assembler fires on **"build the whole thing"** and stays quiet on any single
section. This is the hardest boundary in the toolkit, because `board-pack` is the only skill
whose subject matter is every other skill's subject matter.

**Status: 14/14 routing mode** as of 2026-07-31 (plugin 0.10.0), on the first run, $7.09.
The `Q7` boundary resolved in favour of leaving shipped code alone — see below.

## How to run

```bash
claude plugin update cyber-aware-creations@cyber-aware-creations   # or the run scores a stale build

PROMPTS="$PWD/skills/board-pack/evals/prompts.tsv" \
  ./skills/nist-csf/evals/run-triggers.sh /tmp/bp-trigger

# reference mode — does pack-structure.md earn its place?
ALLOWED_TOOLS="Read Glob Grep Skill" MAX_TURNS=24 \
PROMPTS="$PWD/skills/board-pack/evals/prompts.tsv" \
  ./skills/nist-csf/evals/run-triggers.sh /tmp/bp-trigger-ref
```

## The boundary, and the one that worries me

**In scope — the whole deliverable.** Build the pack, assemble the quarterly deck, produce the
audit-committee pack, turn the stores into one narrative, give me the PowerPoint and the PDF.

**Out of scope — any one section.** Translating a metric, scoring a risk, listing overdue
acceptances, assessing an incident. Each belongs to the skill that owns it, and a pack that
answered them would be doing a producer's job badly.

`Q7` is the case to watch: **"Write the executive summary for our security posture."**

`ciso-board-translation`'s description already claims *"an executive summary of security
posture"* and *"build a board deck or report"* — written before this skill existed. That
overlap is real and was flagged during Phase D rather than discovered by the eval. Two possible
outcomes, and both are informative:

- **`Q7` routes to `ciso-board-translation`** — the descriptions are separable as written, and
  `board-pack`'s emphasis on *assembling existing sections* is doing the work. No change needed.
- **`Q7` routes to `board-pack`** — the assembler is cannibalising a one-shot phrasing ask, and
  `ciso-board-translation`'s description needs narrowing. That is a change to shipped, working
  code and should be made deliberately, not reflexively.

`P6` is the mirror image: *"What decisions is the board actually being asked to make this
quarter, across all of it?"* — no single producer can answer it, because consolidating
decisions across sections is precisely what only the assembler does.

## The cases

| id | expects | prompt |
|---|---|---|
| P1 | `board-pack` | Build the board pack for this quarter. |
| P2 | `board-pack` | Assemble the quarterly security deck from our register, profile and metrics. |
| P3 | `board-pack` | Put together the audit-committee pack for next week. |
| P4 | `board-pack` | Turn everything we've got — risks, CSF profile, metrics, exceptions, the incident — into one narrative for the board. |
| P5 | `board-pack` | I need the board deliverable for Q3 as a PowerPoint and a PDF. |
| P6 | `board-pack` | What decisions is the board actually being asked to make this quarter, across all of it? |
| P7 | `board-pack` | Our sections are all written — stitch them into the deck. |
| Q1 | `ciso-board-translation` | How should I phrase 87% patch coverage for the board? |
| Q2 | `risk-register` | Score our ransomware risk and tell me if it's within appetite. |
| Q3 | `metrics-register` | Which of our metrics are breaching their thresholds? |
| Q4 | `nist-csf` | How complete are we against CSF Recover? |
| Q5 | `exceptions-register` | Which of our risk acceptances are overdue for re-validation? |
| Q6 | `incident-materiality` | We had a breach at our CRM vendor last week. Is this material? |
| Q7 | `ciso-board-translation` | Write the executive summary for our security posture. |

## Beyond routing

Read out of the transcripts by hand on the first run:

1. **`P1` and `P7` must not offer to write the prose.** The correct answer asks for the
   manifest and the sidecars, or offers `compose-brief` so `ciso-board-translation` writes the
   through-line. An answer that drafts an executive summary itself has defeated the design.
2. **`P5` must state the PPTX limit.** Structural validity is verified; rendering fidelity is
   not testable and the deck should be opened once before it goes to a board.
3. **`P4` must not invent a section.** With no stores present the honest answer is to name what
   it needs, not to sketch a plausible pack.
4. **`P3` must not offer the audit committee a franker version.** The audience changes the
   reading order, not the facts, and never the disclaimers.

## What the first run found

**14/14 on the first run.** All seven "build the whole thing" cases reached the assembler, and
all seven single-section cases went to the skill that owns them.

### `Q7` settled the open question, and the answer is: change nothing

*"Write the executive summary for our security posture"* routed to **`ciso-board-translation`**.
The two descriptions are separable as written — `board-pack`'s emphasis on *assembling existing
sections* does the work, and a one-shot phrasing ask still lands where it should. The overlap
flagged during the build is real but not harmful, so the shipped description stays as it is.

That is the outcome worth having: a change to working code was on the table, and the eval said
it was not needed.

### The behavioural checks

| case | requirement | what the run did |
|---|---|---|
| `P1` | must not write the prose | *"I could produce a polished, plausible-looking quarterly pack right now. It would be entirely invented."* Then named the reason: board packs are governance evidence that directors vote on and auditors read. |
| `P3` | no franker version for the audit committee | Refused, and named the specific hazard unprompted: relabelling the shipped Northwind example would look exactly like a finished audit-committee pack, and *"an audit committee is precisely the audience that would act on it"*. Recited the correct audit-committee ordering without offering different content. |
| `P4` | must not invent a section | Read `section-contract.md`, found no inputs, and stopped. |
| `P7` | must not write the prose | Same — checked both working directories including hidden files, then stopped. |

`P1` and `P3` both went further than the requirement. Neither was asked to explain *why*
fabrication is worse here than elsewhere; both did, and both landed on the governance-record
argument rather than a generic "I shouldn't make things up".

### One requirement this run could not exercise

`P5` was supposed to check that the answer states the PPTX rendering limit. It never got
there: with no stores in the working directory it correctly refused to build anything, so no
deck existed to caveat. The case passed on routing and on the no-fabrication rule, and the
PPTX-limit requirement remains **untested**. It needs a run with real stores present, which
this harness deliberately does not provide.

### Reference reads

`P4`, `P5` and `P7` each opened a file in the skill (`section-contract.md` twice,
`assemble_pack.py` once) even in routing mode, because those live in the plugin cache rather
than outside the sandbox. So this set exercises its references more than the earlier ones did —
which is luck of the layout, not design.

---

*A Cyber Aware Creation · Not affiliated with NIST.*
