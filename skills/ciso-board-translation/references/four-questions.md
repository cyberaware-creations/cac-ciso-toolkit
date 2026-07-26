# The Four Questions — the method in depth

This is the core method the skill is built on. Read it when you are
constructing a translation from scratch, grading a draft, or teaching a CISO
how the method works. Everything here serves one goal: turn a number that dies
in the boardroom into a decision the board can actually make.

## Contents

- [Why four questions, and why in order](#why-four-questions-and-why-in-order)
- [Question 1 — So what's exposed?](#question-1--so-whats-exposed)
- [Question 2 — So what does it mean for us?](#question-2--so-what-does-it-mean-for-us)
- [Question 3 — Are we winning or losing?](#question-3--are-we-winning-or-losing)
- [Question 4 — What do you need from me?](#question-4--what-do-you-need-from-me)
- [The grading rubric (F / C / A)](#the-grading-rubric-f--c--a)
- [The reusable template](#the-reusable-template)
- [Worked examples across metrics](#worked-examples-across-metrics)
- [Common failure modes](#common-failure-modes)

## Why four questions, and why in order

A board is not a technical audience and does not want to become one. Directors
govern: they weigh spend against risk, and they discharge an oversight duty they
are personally on the hook for. A raw metric gives them nothing to govern with.

The four questions map exactly to how a director processes a risk item:
*What is actually at stake? What does it cost us? Which way is it heading? What
are you asking me to do about it?* Answer them out of order and you lose the
room — lead with the ask before naming the exposure and it sounds like begging;
give the trend before the consequence and it sounds like a status update. The
order is the argument.

A finished translation answers all four. That is the definition of "done."

## Question 1 — So what's exposed?

**The specific thing at risk, named and counted — not the percentage.**

Why it matters: a percentage is an abstraction, and abstractions do not create
urgency or enable judgment. "87% patched" tells a director nothing they can act
on. "9 internet-facing systems unpatched for 40 days" is a thing they can
picture, size, and decide about. The percentage hides the exposure; naming it
reveals it.

- **Done badly:** "Our coverage has some gaps." (Vague — nothing to govern.)
- **Done badly:** "We're at 87%." (A number, not an exposure.)
- **Done well:** "The gap is 9 internet-facing systems, unpatched for 40 days."

The move: convert the percentage into the concrete, counted noun behind it, and
name *which* items — because the remaining gap is almost never random (see the
metric archetypes; the leftover is usually the riskiest slice).

## Question 2 — So what does it mean for us?

**The business consequence, in the board's language — revenue, operational,
regulatory, reputational.**

Why it matters: a board does not act on technical facts; it acts on business
consequences. "Unpatched internet-facing systems" is a technical fact. "This is
one of the most common ways ransomware operators get into companies like ours
today" is a consequence a director can weigh. You are translating from the
language of the SOC to the language of the P&L.

- **Done badly:** "This increases our attack surface." (Still technical.)
- **Done well:** "Unpatched internet-facing systems are a leading ransomware
  entry point — a hit here is an operational-outage and breach-notification
  event, not just an IT ticket."

Pick the consequence axis the board cares about most for this asset: revenue
interruption, operational downtime, regulatory exposure, or reputational harm.
Ground it in the real threat pattern honestly — do not inflate it.

## Question 3 — Are we winning or losing?

**The trend and direction — because a board governs direction, not snapshots.**

Why it matters: a single number is a dot on a chart; a director cannot tell if
it is good or bad, or whether their prior investment is working. Two numbers are
a story. The board's real question underneath is "is the program getting better
or worse, and did what we funded last time move it?" Give them the vector, with
a one-word verdict: **gaining ground / holding / slipping.**

- **Done badly:** "We're at 87%." (A snapshot — no direction.)
- **Done well:** "87%, up from 78% last quarter — the program is gaining
  ground."

This is also where continuity lives. The number must be consistent with what
the board was told before, or explicitly reconciled if the definition changed.
A prompt has no memory of last quarter; the user must supply the prior number,
and you must place it.

## Question 4 — What do you need from me?

**End on a decision or ask — not a status update.**

Why it matters: this is the whole point. A board item with no ask is a status
update, and status updates do not move budget or discharge oversight. The
translation exists to *force a decision*: fund the close, or formally accept the
exposure on the record. Either outcome is legitimate governance — but only if
the board actually decides.

- **Done badly:** "We'll keep working on it and update you next quarter."
  (No decision — the item evaporates.)
- **Done well:** "I can close the window to under 7 days with one engineer and a
  billing maintenance window, or we accept a 40-day window on those 9 systems as
  a board. I'm asking for a decision today: fund the close, or record the
  acceptance."

The ask must be a real either/or with named costs on both sides — the cost to
close *and* the specific exposure retained if they decline. That symmetry is
what lets a director actually choose rather than defer.

## The grading rubric (F / C / A)

Grade any draft by counting which of the four questions it answers. Show the
grade and the reasoning — the user learns the method by seeing why a version
falls short.

| Grade | What it looks like | Questions answered | Why it fails / works |
|-------|--------------------|--------------------|----------------------|
| **F** | "Our patch coverage is 87%." | None | Accurate and useless. A raw number dies in the room. |
| **C** | "Patch coverage is 87%, up from 78% last quarter. Real progress." | Only Q3 (trend) | A status update that *feels* like communication. Where most competent technical CISOs top out. No exposure, no consequence, no decision. |
| **A** | The full flagship statement (all four, ending on fund-or-accept). | All four | Board-ready. Names the exposure, states the consequence, shows the trend, forces a decision. |

The gap between C and A is the gap this skill closes. C is where good technical
leaders plateau; A is governance.

## The reusable template

The structure is the durable asset. Numbers are illustrative and come from the
user's own data — never invent them.

> "[Metric] is [value] — [trend vs last period + one-word verdict: gaining
> ground / holding / slipping]. The gap is [the specific exposed thing, named
> and counted], which matters because [business consequence in the board's
> language]. The constraint is [the real reason it isn't closed — always a
> business fact: legacy system breaks a revenue app, vendor hasn't shipped a
> fix, change-freeze, headcount]. I can [the close: cost + what you need], or we
> [formally accept the exposure]. I'm asking for a decision: [fund / accept]."

Note the "constraint" slot: it must always be a *business* fact, not a technical
excuse. "We haven't gotten to it" is not a constraint; "patching it breaks the
billing app that runs $2M/day" is. The constraint is what makes 100% the wrong
target and reframes the item from failure to trade-off.

## Worked examples across metrics

Each shows input (the raw fact + context the user supplies) → Grade-A output.
Numbers are illustrative placeholders.

### Example 1 — Phishing click rate (the reassuring low number)

**Input:** Click rate 4% on the last simulation of 5,000 staff, down from 6%.
Context: no phishing-resistant MFA on the finance group; a click there could
land on the payment-approval system.

**Grade A:** "Our phishing click rate is 4%, down from 6% — awareness is
improving. But 4% of 5,000 people is roughly 200 who clicked, and an attacker
needs exactly one — this metric measures our *simulation*, not a targeted
spear-phish, and it's silent on whether the clickers sit near money. The
exposure that matters: our finance group approves payments and isn't on
phishing-resistant MFA, so a successful lure there is a wire-fraud event. I can
move that group to hardware-key MFA for about [cost], or we accept that a
single click in finance can reach the payment system. I'm asking for a decision:
fund the MFA upgrade, or record the acceptance."

### Example 2 — Backup coverage (the untested backup)

**Input:** "99% of systems backed up successfully." Context: no full restore
drill has ever run; real RTO unknown; backups are not immutable.

**Grade A:** "Backups succeed on 99% of systems — but backup success is not
restore success, and that's the number that matters after ransomware. We have
never run a full restore drill, so our real recovery time is unknown and, for
peers who finally test, it's usually measured in days, not hours. Our backups
also aren't immutable, and modern ransomware hunts and encrypts backups first.
The exposure: an incident today could mean an unknown, possibly multi-day outage
with no guaranteed clean recovery point. I can fund isolated immutable backups
plus quarterly restore drills for [cost], or we accept an unmeasured recovery
time on the record. I'm asking for a decision: fund tested recovery, or record
the acceptance."

### Example 3 — Framework maturity score (the averaged-away weak spot)

**Input:** NIST CSF self-assessment averages 3.2/5, up from 2.9. Context: the
average hides Recover at 1.5; Protect is strong at 4.

**Grade A:** "Our NIST CSF maturity is 3.2 out of 5, up from 2.9 — trending up.
But that's a composite average, and averaging is exactly what hides the risk: our
Protect function is a strong 4, which is masking a Recover function sitting at
1.5. After an incident, the board's question won't be our average — it'll be
whether we governed the specific weak function, and Recover is where we'd
struggle to bring the business back. The right move isn't a uniform push to 5
everywhere; it's funding Recover up one level for [cost], or accepting the
recovery gap explicitly. I'm asking for a decision: fund the Recover uplift, or
record the acceptance of the gap."

## Common failure modes

- **Leading with the ask.** Naming the budget request before the exposure and
  consequence reads as begging. Follow the order.
- **Stopping at C.** Trend-plus-color feels finished but forces no decision.
  Always push to Q4.
- **A soft or absent constraint.** If the "constraint" slot is a technical
  excuse rather than a business fact, the item sounds like negligence instead of
  a trade-off. Find the real business reason.
- **A one-sided ask.** "Fund this" without stating the exposure retained on
  decline gives the board nothing to weigh. Name both sides.
- **Inventing the specifics.** If you don't have the count, the prior number, or
  the constraint, ask for them. A confident fabrication is the worst outcome.
