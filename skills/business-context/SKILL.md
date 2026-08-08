---
name: business-context
description: >-
  Two jobs, and the second is the one people ask out loud: RECORD the
  organisation's own facts — revenue base, crown jewels, board-voiced risk
  tolerance, segments, strategic goals, contractual security obligations — and
  READ BACK the ones already recorded, word for word. Answers "what did the
  board actually say about outage tolerance", "I want the exact words on file",
  "what is on record about our appetite", "who said that, and when": the board's
  sentence is stored VERBATIM with the person who said it and the date, and
  `show` prints it unparaphrased. **Use it even when no document can be found** —
  "on file" and "on record" mean THIS register, not a documents folder, and
  searching the working directory, Drive, Notion or a mailbox answers a different
  question. If the sentence was never recorded, that absence is itself the answer
  and the page says so plainly: nobody wrote down what the board said, which is a
  different fact from the board having said nothing. Also owns the applicability
  profile (CAC-AP-1): declared
  flags for regulatory perimeter, entity shape, technology posture and
  third-party posture that let every other skill ask only the questions that
  apply. A missing profile or flag means not declared and never means does not
  apply, so a skill with no profile asks its full question set; a subject-level
  declaration always outranks the org-level profile; and every skipped battery
  is recorded with its reason so an auditor can tell a question that was out of
  scope from one nobody asked. Declares, never infers — being an EU entity does
  not set DORA scope. Stores revenue exact for an honest materiality denominator
  and renders it as a band, and refuses to derive any percent-of-revenue
  threshold from it. Use when asked to record what the business does or what it
  cannot lose, capture the board's words on risk tolerance OR quote them back,
  find what the board actually said or the exact wording held on file about
  tolerance, appetite, an outage or a loss the business would not accept, declare
  which regulations or technologies are in scope, note a crown-jewel system and
  what depends on it, set the revenue base a materiality judgment weighs against,
  or work out which questions apply to this organisation or this vendor. Not a
  CRM, an asset inventory or a company database: if a fact does not change what a
  security question asks or what a security number means, it does not belong
  here. The appetite BAND derived from the board's words is risk-register and
  phrasing a number FOR the board is ciso-board-translation — only the words
  themselves live here.
---

# Business Context

The store for the organisation's own facts, and the **applicability profile** that lets every
other skill ask only the questions that apply.

## The gap this fills

Every skill in this suite asks the CISO to declare something, and then — correctly — refuses to
invent it. `risk-register` takes an appetite band. `metrics-register` takes target, warn and
critical. `exceptions-register` demands an approver and a justification. `incident-materiality`
walks six factors and emits no verdict.

The discipline is right. What was missing is **anywhere to record why the declared number is
that number.** An appetite of `medium` traced to nothing. A materiality assessment weighed
financial impact against a revenue base that lived in someone's head. A crown-jewel system was
"high impact" because everyone agreed it was.

## Handling — read this before you create one

**A `.biz` concentrates the revenue base, the crown jewels and the board's own words in a single
document.** That combination is more sensitive than any of the registers it feeds: it names what
the business cannot lose, and it says so alongside what the business is worth.

- Keep it where the risk register lives, not in a shared drive or a wiki.
- The default render **bands** the revenue. `--render-revenue exact` exists for an audience
  cleared for the figure, and writes that choice into the provenance line so the two documents
  cannot be mistaken for one another.
- The board tolerance quotes are verbatim and attributed. Treat them as board minutes.
- It is a governance asset and a potential litigation exhibit, which one depending on whether it
  agrees with what the organisation says publicly. Involve counsel before it circulates.

## Workflow A — build the profile

```bash
E=scripts/business_context.py
python3 $E init context.biz --org "Northwind Manufacturing" --prepared-by "D. Galleyne, CISO"

python3 $E declare context.biz --flag listedEntity --value false \
  --by "General Counsel" --basis "Privately held; no securities admitted to trading."
python3 $E declare context.biz --flag doraScope --value true \
  --by "General Counsel" --basis "Dublin subsidiary authorised as a payment institution."
```

**`--basis` is required, and so is `--by`.** A flag narrows what every other skill asks. One
that cannot say why is worse than an absent flag, because absence asks everything — so the only
thing an unjustified flag can do is ask *less*.

**Declared, never inferred.** Being an EU entity does not set DORA scope. A lawyer decides that,
and this tool records what they decided.

An unknown flag is **accepted with a warning**, not refused: the regulatory perimeter list will
outgrow any enumeration shipped here.

## Workflow B — record what the numbers mean

```bash
python3 $E set-fact context.biz --crown-jewel "CRM (Salesforce)" \
  --enables "every renewal conversation and the whole aftermarket pipeline" \
  --at-stake "the client contact and contract data that 60% of group revenue renews through" \
  --by "D. Galleyne" --basis "FY26 planning workshop"

python3 $E set-revenue context.biz --exact 412000000 --currency EUR --fiscal-year FY26 \
  --by "CFO" --basis "FY26 audited consolidated accounts"

python3 $E set-fact context.biz --board-tolerance \
  'We will not accept a "material" outage in the payments rail — not for a quarter'"'"'s savings.' \
  --by "Chair, FY26 Q2 board" --on 2026-05-19
```

The **crown jewel is the row that earns this skill.** It is the join between a technical asset
and a business consequence — the join `ciso-board-translation` otherwise has to be told by hand
every single time. `--at-stake` is required for that reason: a system with `--enables` and
nothing at stake is an asset inventory row.

A crown jewel may also carry `--criticality` and `--depends-on`, both optional:

```bash
--crown-jewel "Plant historian (Dublin)" --enables "production scheduling across both lines" \
  --at-stake "a day of lost output is roughly a week of aftermarket margin" \
  --criticality high --depends-on "SCADA gateway"
```

These are the top of a criticality walk a consumer runs — `vendor-register` traces from a
third-party arrangement, through a component, to the workflow it ultimately supports. They live
here because that is what they are: statements about what the organisation cannot lose, not
about any vendor.

**Neither key exists unless declared**, so a `.biz` written before they did loads and exports
byte-identically. A missing level means *not declared* and never *not critical* — §2.2 applies
to this field exactly as to a profile flag, and a consumer reading absence as the bottom of its
scale would silently downgrade every system nobody has got to yet.

**The level is recorded as given and never checked**, because this skill owns no scale. The
consumer that has one compares and reports a disagreement rather than coercing the value;
validating here would mean deciding what a criticality level is allowed to be for everybody.

The **board tolerance is stored verbatim**, never paraphrased on write. `risk-register` owns the
appetite band; this owns the sentence the band was derived from.

## When somebody asks what the board actually said

*"What did the board actually say about outage tolerance? I want the exact words on file."*
This is the question the verbatim field exists for, and it is a **read**, not a write. Answer it
here, in this order, and do not answer it any other way.

1. **Read the register first.** `show` prints every recorded sentence word for word, with the
   person who said it and the date it was said.

   ```bash
   python3 $E show context.biz
   ```

2. **"On file" means this file.** The phrasing invites a document hunt — the working directory,
   then Drive, then Notion, then a mailbox — and that hunt answers a different question. Board
   minutes are where the sentence *came from*; this register is where it *is*, attributed and
   dated, which is what makes it citable.

3. **If nothing is recorded, say so — that is the answer.** `show` prints `NONE RECORDED` and
   names the distinction outright: nobody wrote down what the board said, which is not the same
   as the board having said nothing. The fix is one command and an afternoon, and it is a far
   better answer than a plausible reconstruction of what a board of that kind usually says.

4. **Never paraphrase on the way out.** A summary of the board's words, offered in answer to a
   request for the board's words, is the exact failure the verbatim rule was written against.
   Quote it, or report that there is nothing to quote.

The same order applies to any recorded fact somebody asks to see: the crown jewels, the
obligations, the revenue base and its basis all render from the store rather than from memory.

## The applicability contract (CAC-AP-1)

```bash
python3 $E applies context.biz --skill incident
python3 $E applies context.biz --skill vendor --subject-declares ai=true
```

Three rules, and two of them are the opposite of what a first draft does.

**Absence asks everything.** A missing profile, a missing flag, or a flag whose value is `null`
means *not declared* — never *does not apply*. Narrowing on absent data produces an assessment
that looks complete and is not.

**The subject outranks the profile.** An org that declared no AI still gets the full AI battery
on a vendor whose own record says it processes data with a model. The override runs in both
directions, and a subject that declares nothing does not override.

**Every skip is visible**, carried into the artifact rather than swallowed:

> *SEC Item 1.05 disclosure window — not assessed. Organisation profile: `listedEntity: false`,
> declared 2026-03-02 by General Counsel — Privately held; no securities admitted to trading.*

An auditor cannot otherwise tell a question that was correctly out of scope from one nobody
asked. The full contract, written for skill authors implementing `--context`, is in
`references/applicability-contract.md`.

## What this skill must not own

One skill owns any given lifecycle (`CAC-EL-1 §1.1`). This is a supplier of facts and takes
ownership of nothing that already has an owner.

| Not owned | Owner | What this supplies instead |
|---|---|---|
| Risk appetite band | `risk-register` | The board's voiced tolerance the statement cites |
| Metric thresholds | `metrics-register` | The business fact behind the number |
| Materiality verdicts | `incident-materiality` — which emits none | The revenue base, as a figure a human weighs |
| Acceptance lifecycle | `exceptions-register` | The obligation the deviation is from |

**No derived materiality.** Holding a revenue figure creates an obvious temptation to compute a
percent-of-revenue rule. It does not exist here. `incident-materiality` refuses to emit a verdict
precisely because a generated number is discoverable alongside the determination it disagreed
with; supplying the denominator must not smuggle that number back in. This is enforced by
`evals/no-derived-materiality.sh`, which is run against a deliberately poisoned copy so the
guard is known to work rather than assumed to.

## What this raises without being asked

| trigger | fires when | severity |
|---|---|---|
| `profile-stale` | the profile has not been reviewed within the configured cadence | `high` |

**One trigger, deliberately.** `profile-stale` is unlike every other escalation in the suite: it
is not an exposure. A crossed band or an expired acceptance says something got worse; this says
the lens every other skill looks through has not been checked, so what they report may be
measured against a perimeter that moved.

A store that has **never** been reviewed escalates nothing — it is new, not stale.
`fact-unattributed` is deferred until there is volume data from a real file: a freshly built
`.biz` is nearly all unattributed, and shipping it would teach the owner to skim the list.

## Reporting

```bash
(cd renderers && python3 render_context.py --in ../context.biz --out ../framing.html)
```

Framing, **not a sixth board section** — `board-pack`'s section contract keeps its five values.
This supplies the cover, the opening context paragraph, and a provenance stamp naming the
profile version the pack was assembled against.

## Reference

| File | What it covers |
|---|---|
| `references/schema.md` | the `.biz` store, the provenance wrapper, the band ladder, the derived list |
| `references/applicability-contract.md` | CAC-AP-1, normative, written for consumers |

Verify the engine with `python3 scripts/business_context.py self-test`.

---

*A Cyber Aware Creation · Not affiliated with NIST.*
