---
name: ciso-board-translation
description: >-
  Translates raw security facts—a single metric, a specific risk, or a quarter
  of program work—into board-ready language a director will act on, backed by
  sourced regulatory receipts that carry their own honest limits. Use this
  whenever security content is going to a board, audit committee, or senior
  leadership: translate a metric or number for the board, "make this
  board-ready", build a board deck or report, an executive summary of security
  posture, "what do I tell the board", answering "are we secure?", a
  quarter-over-quarter security narrative, justifying a security budget to
  leadership, or framing a risk acceptance for the board. Other skills (for
  example risk-register) should invoke this for any board-facing security
  output. Every translation names the specific exposure, states the business
  consequence, shows the trend, and ends on a decision the board can make. NOT
  for general copywriting, security policy or procedure writing, or
  personal/career communications.
---

# CISO Board Translation

## What this skill does

This skill converts a raw security fact into language a corporate director can
govern with. Feed it one metric, one risk, or one quarter of program work plus
the context that surrounds it, and it returns board-ready output: a single
translated statement, an executive-summary narrative, and/or prepared answers
to the questions the board will ask back.

It is the reusable engine other skills call whenever their output faces a board.
If you are producing a board deck, an audit-committee memo, a risk acceptance,
or a budget ask, route the language through this skill rather than improvising.

**What this is NOT for:** general copywriting, marketing, security policy or
procedure documents, or an individual's personal or career communications. If
the audience is not a board or senior leadership weighing spend against risk,
this skill is the wrong tool.

## The delta — why a blank prompt cannot do this

State this plainly, because it is the skill's whole reason to exist. A generic
chatbot can polish a sentence. It cannot do the four things that make a
translation actually land:

- **It does not know your data.** That 13% unpatched is internet-facing, and
  two of those systems break billing if you touch them — that is the user's
  ground truth, not something a model can infer. The skill's job is to *demand
  and place* those facts, never to invent them.
- **It has no memory of the last quarter.** Continuity — reconciling this
  quarter's number against what the board was told two quarters ago — does not
  exist in a fresh prompt. The skill enforces the narrative spine.
- **It does not know your board.** Which questions your audit committee actually
  asks, and which follow-up ambushes a first-time CISO — that is curated
  judgment, carried in the question bank.
- **It cannot source a receipt honestly.** Grounding a "record the acceptance"
  ask in the DORA RTS or the Caremark line *without inventing a fake legal
  hook* takes sourced references with their limits attached.

The number is data. The translation is judgment. This skill supplies the
judgment scaffold; the user supplies the numbers.

## The core method: the Four Questions

Every board number must answer four questions, **in this order**. A finished
translation answers all four. Miss one and the item stalls in the room.

1. **So what's exposed?** — the specific thing at risk, named and counted. Not
   the percentage. "87% patched" is not an answer; "9 internet-facing systems
   unpatched for 40 days" is.
2. **So what does it mean for us?** — the business consequence, in the board's
   language: revenue, operations, regulatory, reputation. A board does not act
   on "unpatched systems"; it acts on "this is how ransomware operators get in."
3. **Are we winning or losing?** — the trend and direction. A board governs
   *direction*, not snapshots. One number is a dot; two numbers are a story.
4. **What do you need from me?** — end on a decision or ask, never a status
   update. A board item with no ask is a status update, and status updates do
   not move budget or discharge oversight.

Depth, the full rubric, the abstracted template, and more worked examples live
in `references/four-questions.md`. Pull it whenever you are constructing a
translation from scratch or teaching the method.

### Worked grades — show the reasoning, not just the answer

Grade the draft against the four questions so the user sees *why* a version
works. Using patch coverage as the flagship example:

- **Grade F** (raw number, dies in the room): *"Our patch coverage is 87%."*
  Accurate and useless. Answers none of the four questions.
- **Grade C** (number with color, still no decision): *"Patch coverage is 87%,
  up from 78% last quarter. Real progress."* Answers only the trend. A status
  update that feels like communication — where most competent technical CISOs
  top out.
- **Grade A** (board-ready): *"We patch 87% of systems within SLA — up from 78%
  last quarter, so the program is gaining ground. The remaining 13% isn't
  random: it includes 9 internet-facing systems, and unpatched internet-facing
  systems are one of the most common ways ransomware operators get in today.
  Our current exposure window on those 9 is 40 days. Two can't be patched
  without breaking the billing application — the real constraint. I can close
  the window to under 7 days with one additional engineer and a maintenance
  window on billing — or we can formally accept a 40-day window on those 9
  systems as a board. I'm asking for a decision today: fund the close, or
  record the acceptance."*

The A grade answers all four questions and ends on a genuine either/or the board
can vote on. That is the target every time.

### The reusable template

This structure is the durable asset. The numbers are illustrative — the CISO
fills them from their own data. Never invent the numbers; the structure is what
you are supplying.

> "[Metric] is [value] — [trend vs last period + one-word verdict: gaining
> ground / holding / slipping]. The gap is [the specific exposed thing, named
> and counted], which matters because [business consequence in the board's
> language]. The constraint is [the real reason it isn't closed — always a
> business fact: legacy system breaks a revenue app, vendor hasn't shipped a
> fix, change-freeze, headcount]. I can [the close: cost + what you need], or we
> [formally accept the exposure]. I'm asking for a decision: [fund / accept]."

## How to use this skill when another skill calls it

**Input you should expect or ask for:**
- The raw fact: a metric and its value, a named risk, or a quarter of program
  activity.
- Context only the user has: what the gap actually consists of, the real
  business constraint blocking closure, last period's number, and anything the
  board was previously told.

If that context is missing, ask for it — do not fabricate it. A translation
built on invented specifics is worse than no translation, because it sounds
authoritative and is wrong.

**Output you can produce, depending on the request:**
- A single board-ready statement (the template, filled).
- An executive-summary narrative stitching several metrics into one posture
  story with a through-line and a trend.
- Prepared answers to the questions the board will ask back (see the question
  bank).

**Recognize the metric.** If the fact matches one of the seven common
archetypes (patch coverage, phishing click rate, dwell time/MTTD, third-party
risk, MFA/identity coverage, framework maturity, backup/recovery), pull
`references/metric-archetypes.md` for that metric's specific trap, the sharp
board ask, and the receipt angle. Each archetype hides a different way the raw
number lies.

### Writing the sidecar file the dashboards consume

`nist-csf` and `risk-register` both render board dashboards with a
**labelled placeholder** wherever narrative should be, and neither will ever
write that prose itself. This skill fills those slots — and it does so through a
JSON file, not conversational output. Return prose when a human asked a
question; write the file when a dashboard is being generated.

`nist-csf` — `render_executive.py --translations board.json`, keyed by CSF
Subcategory ID:

```json
{
  "executiveSummary": "One paragraph of posture, with a through-line and a trend.",
  "gaps": {
    "PR.AA-01": "Leavers keep system access for weeks, so a departing employee can still reach patient records.",
    "GV.SC-07": "We cannot say which suppliers hold our data, so a breach at one of them would surprise us."
  },
  "decisions": ["Fund the joiner-mover-leaver automation, or record the acceptance and its owner."],
  "asOf": "2026-10-01"
}
```

`risk-register` — the same flag on all three of its renderers. Same
`executiveSummary` / `decisions` / `asOf`, but the per-item maps are `risks`
(keyed `R-001`) and `themes` (keyed by theme id), not `gaps`:

```json
{
  "executiveSummary": "…",
  "risks":  {"R-001": "One sentence on what this means for the business."},
  "themes": {"third-party": "One sentence on this theme as a whole."},
  "decisions": ["…"],
  "asOf": "2026-10-01"
}
```

See `risk-register/references/example-translations.json` for a filled example.

Three things that make the difference between a working file and a silent
failure:

- **`gaps` must be nested.** A flat `{"PR.AA-01": "..."}` map is the natural
  guess, and it is wrong. It parses, the render claims success, and every
  narrative reverts to the placeholder — a deck that looks finished and says
  nothing.
- **One sentence per key, in the board's language.** These land in a tile, not a
  page. The Subcategory text is already on the operational view; repeating it
  here wastes the only slot that was reserved for meaning.
- **The guardrails below still apply.** No invented numbers, no invented
  benchmarks, and a decision at the end. A placeholder left visible in the
  dashboard is a better outcome than a fabricated sentence.

### The fifth element — positive risk, and it is optional

CSF 2.0 asks for one thing this suite had no element for:

> **`GV.RM-07`** — Strategic opportunities (i.e., positive risks) are characterized and are
> included in organizational cybersecurity risk discussions

A sidecar may carry an `opportunities` array. It is optional, additive, and **absent is the
correct output for most sections most of the time.**

```json
"opportunities": [
  {"text": "A tested exit on the plant historian is what makes the Dublin renewal negotiable.",
   "cites": "goal:Close the Dublin authorisation year without a supervisory finding",
   "gvsc": "GV.RM-07"}
]
```

**Three rules, and the first is the whole point:**

1. **It must cite a declared goal or crown-jewel dependency from `business-context`.** No
   citation, no entry — **refused by the assembler**, not warned. *"Better security helps the
   business move faster"* is unfalsifiable, and this skill already says overclaiming costs more
   credibility than silence. That applies here exactly as it applies to a regulatory claim.
2. **Never blended into a risk sentence.** Its own array, its own block. An optimistic tail on a
   loss statement reads as softening the loss and teaches a board to discount the section.
   `outcome-framing.sh` fails a sidecar that tries, naming the sentence and the word.
3. **Write nothing rather than something.** There is no "none identified" placeholder, because a
   box on a board page manufactures pressure to fill it — which is how this becomes marketing
   copy. A section with nothing to cite writes no array and renders no block.

The full argument, both worked examples, and why this was correct to omit until
`business-context` shipped: `references/positive-risk.md`.

### Two things now checked rather than trusted

`board-pack/evals/outcome-framing.sh` enforces what this file has always asked for and nothing
tested:

- **every item sentence carries a consequence** — a connective *and* a consequence noun,
  clearing an 80% floor per section, with one miss always tolerated;
- **every `decisions[]` entry ends on a decision** — a leading decision verb or an explicit
  `or` fork. No floor on this one; it is unambiguous.

The vocabulary is data, in `references/consequence-vocabulary.json`. An occasional false
negative is expected and is not a defect: the check names the sentence it rejected, and **adding
a word to the vocabulary is the intended response**. It tests that a required element is
present. It has no opinion about whether the prose is good, and it must never grow one.

## When to pull each reference

Keep this file lean and reach for depth only when the task needs it. One level
deep only — each reference is self-contained and does not send you to another.

- `references/four-questions.md` — building a translation from scratch, grading
  a draft, or teaching the method. Holds the full rubric, the template, and
  worked examples across several metric types.
- `references/board-question-bank.md` — anticipating what the board will ask
  back, or prepping a CISO for the room. Questions grouped by the director's
  underlying intent, each with a model answer, plus the quarter-over-quarter
  reconciliation rule.
- `references/regulatory-receipts.md` — grounding a "record the acceptance" or
  "the board should govern this" ask in why regulators and courts reward the
  framing. Every receipt carries an explicit, load-bearing honest limit. Read
  this before citing any law.
- `references/metric-archetypes.md` — the specific fact matches a known metric
  shape and you want its tailored trap, ask, and receipt angle.

## Guardrails — bake these into every output

These are not style preferences; violating them destroys the credibility the
whole method is built to earn.

- **Never invent numbers.** Values, counts, exposure windows, and costs come
  from the user's data. If you don't have them, leave a clearly marked
  placeholder and ask.
- **Never invent a peer benchmark.** A fabricated "companies our size are at
  X%" is a credibility landmine that detonates the moment a director knows the
  real figure. If you lack credible benchmark data, benchmark against the org's
  own trend or a framework target instead.
- **Never invent or overclaim a legal hook.** Cite receipts only as they appear
  in `references/regulatory-receipts.md`, and always carry the honest limit.
  Overclaiming the law is a faster route to losing the room than saying nothing.
- **Preserve every honest limit.** The limits are load-bearing. A receipt
  stripped of its limit is a liability, not a strength.
- **Refuse the false binary honestly.** When asked "are we secure?", do not
  answer yes/no. Reframe to exposure and trend. Naming exposure honestly builds
  the credibility that a confident "we're fine" destroys the moment it's proven
  wrong.
- **Neither over-reassure nor catastrophize.** The board needs a true picture,
  not comfort and not fear. Fear-based framing ("the SEC will get you") is as
  disqualifying as false comfort.
- **Neutral, professional voice.** This is a generic, publishable product
  component. Write competently and plainly. Do not imitate any individual's
  personal voice, catchphrases, or style.
- **Always end on a decision.** Every translation closes on something the board
  can actually act on — fund the close, or record the acceptance. If you cannot
  name the decision, you have not finished the translation.
