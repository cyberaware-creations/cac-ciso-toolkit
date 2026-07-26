# Board Question Bank — grouped by the director's intent

Boards ask a small number of recurring questions, and the words on the surface
matter less than the *intent* underneath. Read this when anticipating what the
board will ask back, or prepping a CISO for the room. Answer the intent, not
just the literal question.

Every model answer below neither over-reassures nor catastrophizes. Naming
exposure honestly is what builds credibility; false comfort destroys it the
moment it's proven wrong, and fear-mongering gets you tuned out. Numbers in the
answers are illustrative — the CISO fills them from real data.

## Contents

- [Reassurance-seeking questions](#reassurance-seeking-questions)
- [Comparison questions](#comparison-questions)
- [Economic questions (the director's actual job)](#economic-questions-the-directors-actual-job)
- [Accountability questions (their own oversight exposure)](#accountability-questions-their-own-oversight-exposure)
- [The gotcha — quarter-over-quarter reconciliation](#the-gotcha--quarter-over-quarter-reconciliation)

## Reassurance-seeking questions

The director wants to feel safe. The trap is that giving them the comfort they
ask for is exactly what will destroy your credibility later.

**"Are we secure?" / "Are we protected against [the latest headline breach]?"**

Refuse the binary — without sounding evasive. There is no yes/no answer, and
pretending there is sets a trap that springs the day something goes wrong.

> "No program is 'secure' in a yes-or-no sense — the honest frame is exposure
> and trend. On that specific vector, here's our exposure today and the
> direction it's moving: [exposure] and [trend]. That's a picture the board can
> govern, which 'yes, we're fine' isn't."

Why this works: naming exposure honestly *builds* the credibility that a
confident "yes" spends and then loses. A director who hears an honest exposure
picture trusts the next number you give them.

**"Are the unpatched / uncovered systems the ones that matter?"**

Show that you triage by consequence, not by ticket count.

> "We don't treat all gaps equally — we rank by consequence. Of the systems
> still uncovered, [N] are high-consequence [internet-facing / hold regulated
> data / run a revenue app], and those are the ones in this ask. The rest are
> low-consequence and scheduled."

## Comparison questions

The director wants a reference point. The trap is inventing one.

**"How do we compare to peers / companies our size?"**

If you have credible benchmark data, give it *and state its limits*. If you
don't, benchmark against your own trend or a framework target — never invent a
peer number.

> "I have credible benchmark data for [narrow scope], and there we're at
> [honest comparison] — with the caveat that these benchmarks self-report and
> definitions vary, so treat it as directional." *(With data.)*

> "I don't have a defensible peer number for this, and I won't invent one — a
> made-up benchmark is a landmine the moment a director knows the real figure.
> What I can show is our own trajectory: [trend], measured against the [framework
> target] we're aiming for." *(Without data.)*

Why this matters: a fabricated benchmark is a credibility landmine. The one time
a director on your board actually knows the real industry figure, you lose every
number you've ever given them.

**"Is this how companies like us actually get breached?"**

Ground it in the real threat pattern, honestly — neither inflate nor dismiss.

> "For our sector and size, yes — [the specific vector] is a documented, common
> entry point, which is why it's on this list. I'm not claiming it's the only
> way in, but it's a real and current one."

## Economic questions (the director's actual job)

Weighing spend against risk *is* the director's job. These questions are the
board doing its work — meet them with the trade-off, not a defense.

**"Why isn't it 100%?"**

Name the business constraints. 100% is usually the wrong target.

> "100% is the wrong target here, and chasing it would waste money. The last
> gap isn't neglect — it's [legacy systems that break a revenue app if patched
> / a vendor that hasn't shipped a fix / a change-freeze / capacity]. The right
> question isn't 'why not 100%' but 'is the residual exposure worth closing at
> what cost' — which is the decision I'm bringing."

**"What would it cost to close, and what happens if we don't?"**

This is the decision the whole translation exists to force. Give the cost of the
close *and* the specific exposure retained if they decline.

> "Closing it costs [cost + what I need]. If we don't, we retain [the specific,
> named exposure] — [N systems / this consequence]. Both are legitimate choices;
> I'm asking the board to make one deliberately."

**"You asked for budget last year — why is this still a problem?"**

This is where the quarter-over-quarter narrative earns its keep. Show the
trajectory the prior investment bought — do not get defensive.

> "The prior investment moved it from [old number] to [current number] — that
> spend worked and here's the evidence. It didn't close the last slice because
> [the different, harder constraint on the remainder]. So this isn't the same
> ask again; it's the next, more specific step, and the trend shows the money's
> been working."

## Accountability questions (their own oversight exposure)

The director is now thinking about *their own* liability. This is where the
"record the acceptance" mechanic pays off — meet it head-on.

**"If this is a known risk and we don't fund it, where does that leave the
board?"**

> "That's exactly why I'm bringing a documented decision, not an FYI. If the
> board chooses to accept this exposure, that is a legitimate governance
> decision — but a *recorded* one, so the record shows the board was informed
> and governed it. Whichever way you decide, the decision itself is the
> protection."

Why this works: it reframes the CISO from someone delivering bad news into
someone handing the board the exact instrument that discharges their oversight
duty. (For the sourced basis — the Caremark line and its honest limit — see
`references/regulatory-receipts.md`. Cite it only as written there; never invent
a legal hook.)

## The gotcha — quarter-over-quarter reconciliation

The single mistake a first-time CISO must not make: letting two quarterly
numbers contradict each other without a reconciling sentence. A director who
spots an unexplained contradiction stops trusting *every* number.

**"Last quarter you told us X — what changed?"**

Never let this ambush you. The narrative spine exists so this has a prepared
answer. Three cases:

- **The number genuinely moved.** Own the direction plainly: "It moved from X to
  Y because [real cause] — that's [progress / a setback], and here's what we're
  doing about it."
- **The metric definition changed.** Say so explicitly and give the
  apples-to-apples view: "The definition changed this quarter — we now count
  [new scope]. On the old definition it would be [comparable number], so the
  underlying trend is [direction]." Never let a definition change masquerade as
  a performance change.
- **You were wrong last quarter.** Correct it directly: "Last quarter's figure
  was overstated because [reason]; the corrected number is Z. I'm flagging it
  rather than letting it slide."

The rule: **two reported numbers must never contradict without a reconciling
sentence between them.** Before any board update, check every metric against
what the board was last told, and prepare the reconciliation. This is continuity
work a fresh prompt cannot do — it depends on the prior number, which the user
must supply.
