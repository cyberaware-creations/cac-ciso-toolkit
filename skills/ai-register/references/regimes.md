# Regime overlays — the mechanism, and why it ships empty

## Status: the machinery is live and carries no regime content

**No regime ships.** Not the EU AI Act, not Colorado SB 24-205 or its amendments, not the NYC
automated-employment-decision rules, not any state or sectoral AI law. `references/regimes.json`
carries `"regimes": []`, and that is a decision rather than an unfinished job.

An obligation is the only thing this skill would say that is about what a **third party** — a
regulator — requires of the reader. Every other claim here is about their own register: what
they recorded, what they checked, what has no control against it, what is overdue. An
obligation says *the law requires this of you*, and a tool asserting one it cannot cite to
primary text is worse than one that stays quiet: the reader cannot distinguish a checked claim
from a plausible one, and will act on both.

This is the same decision `vendor-register` made about DORA, NYDFS and the SEC provisions, for
the same reason, and it is recorded there in `references/overlays.md`.

## Two things that make the AI case sharper than the third-party one

**1. Role decides almost everything, and it is easy to get backwards.**

Much of what these regimes say is addressed to **providers** of AI systems — the parties that
develop one or place it on the market. A firm that buys a product and puts it to work is
usually a **deployer**, with a shorter and different set of duties. Get this wrong and the
register fills with obligations that are entirely real and are somebody else's. The reader
cannot tell, because a provider obligation reads exactly like a deployer obligation.

`aiRole` is therefore a required field, and `register_regime` refuses a regime without one.

**2. Much of the rest is not security work, and saying so is part of the job.**

Notice to affected people, disclosure of automated decision-making, a right to human review, a
right to appeal, accessibility of the process: these are genuine legal duties and none of them
belongs to the security function. An overlay that lists them without naming an owner implies
the security team will discharge them — which is how a duty ends up owned by nobody, on the
strength of appearing in a security tool.

So `owningFunction` is required on every obligation, and `securityWork` is a separate field,
because "we own this" and "this applies to us" are different facts.

## What that costs, said plainly

An organisation in scope for an AI regime gets the inventory, the criticality trace, the
NISTAML exposure derivation, the evidence tiers, the generated questions, the escalations and
the bridges — and **no regime-specific requirements**. They will have to know their own
obligations. This skill will not pretend to tell them.

## The gate, so this cannot be quietly relaxed

`register_regime` refuses three things, and each refusal names what it wants:

- a regime with no `flag` — *"a regime that is always on is not an overlay, it is an assertion
  that every reader is in scope for it"*
- a regime with no `aiRole` in `deployer | provider`
- an obligation with no `source`, or with no `owningFunction`

`load_regimes` additionally refuses a dataset with no `asOf`: regulations are amended, and a
dataset with no date is a claim about an unknown version of every text in it.

Asserted in the self-test, and mutation-tested.

## No regulatory date in prose, anywhere

`evals/no-regime-dates.sh` fails any shipped `.py` that puts a year inside a sentence about a
regulation — an effective date, a compliance deadline, a "from 2027" in a refusal message.
Dates rot, prose does not get re-read, and a stale date inside a refusal is a wrong statement
of law delivered at the moment somebody is trying to do the right thing. Dates belong in
`regimes.json`, behind an `asOf`, where a reader can see how old they are.

## What a verification pass has to do

Whoever adds regime content — this is the work, not a formality:

1. **Read the primary text.** The regulation, the statute, the implementing rule. Not a
   summary of it, not a law-firm client alert, not a vendor's compliance page.
2. **Establish the role first.** Provider or deployer. Then read only what is addressed to it,
   and record which.
3. **Cite to the article or section**, in `source`, with the date it was checked.
4. **Distinguish an obligation from a practice.** "Shall", "is expected to" and "many firms do"
   are three different things, and only the first belongs in a requirement.
5. **Name the owning function honestly**, including when the answer is "not us".
6. **Record what was checked and what was not.** A regime entry covering four of a law's
   duties is useful; one that looks like it covers all of them is dangerous.
7. **Have someone qualified read it.** This tool is not legal advice, and a regime entry is
   the closest it would come to sounding like it.

---

*A Cyber Aware Creation · Not affiliated with NIST. Not legal advice, and emphatically not a
determination of regulatory scope.*
