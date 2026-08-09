# The materiality factor framework

## What this framework is, and what it refuses to be

It is a **recorded checklist**. Six factors, each assessed by a human with a written rationale,
each stamped with who assessed it and when. Working through them forces completeness — the
common failure in a materiality call is not a wrong answer, it is a factor nobody looked at.

It is **not a scoring model**. There is no scale, no weight, no threshold and no total. The
engine never emits `material: yes`, never counts how many factors came back `bearing`, and never
recommends. Three reasons, and the third is the one that matters:

1. **Materiality is a legal standard, not an arithmetic.** The test is whether there is a
   substantial likelihood that a reasonable investor would consider the information important
   (*TSC Indus., Inc. v. Northway, Inc.*, 426 U.S. 438 (1976); applied to contingent events in
   *Basic Inc. v. Levinson*, 485 U.S. 224 (1988)). Nothing in that test decomposes into weighted
   factors.

   **Cite *Basic* for materiality only.** The same decision also established the
   fraud-on-the-market presumption of reliance, which later Supreme Court authority has
   narrowed. That is a separate question from the materiality standard, and an unqualified
   citation claims more of the case than this tool needs — or than the case still carries.
2. **A score invites the wrong defence.** "The tool scored it 3.2, below our threshold" is not a
   defensible position. "Our General Counsel determined it was not material on 14 July, on this
   recorded basis, having assessed these six factors" is.
3. **A score would be discoverable too.** A generated number that disagreed with the human
   determination — in either direction — becomes an exhibit arguing against your own conclusion.
   The safest artifact is the one that records the reasoning and claims nothing further.

The three assessment values are `bearing`, `no-bearing` and `unknown`. They are words rather
than numbers precisely so that they cannot be summed.

## The six factors

### 1. `financial` — financial impact, actual and reasonably likely

Direct costs (response, remediation, legal, notification), lost revenue, contractual penalties,
insurance recovery, and the effect on financial condition or results of operations.

**Assess the reasonably likely as well as the incurred.** Item 1.05 asks about material impact
*or reasonably likely material impact*; an assessment that only counts spend to date answers a
narrower question than the rule asks.

**Honest limit:** a quantitative threshold — 5% of pre-tax income, or any other rule of thumb —
is a screening heuristic, not the standard. Something below any threshold can still be material
on qualitative grounds, and this framework does not encode a threshold for that reason.

### 2. `operational` — disruption to operations

What stopped, for how long, for whom; whether critical or revenue-generating systems were
affected; the state of recovery; dependency on a third party for restoration.

Duration and breadth belong in the rationale as facts. Whether they matter is the judgment.

### 3. `data` — what was affected

Types, volume and sensitivity of data exposed, altered or made unavailable; whose data (customer,
employee, patient, counterparty); whether it was regulated data; and what is actually **known**
versus assumed at the time of assessment.

**Write down what is not yet known.** "Exfiltration not confirmed as of 9 July; forensics ongoing"
is a better record than silence, and it is what makes a later re-assessment legible rather than
looking like a reversal.

### 4. `regulatory` — regulatory and contractual triggers

Obligations this incident may trip independently of the securities question: sectoral regulators,
data-protection authorities, state breach-notice statutes, customer contract notice clauses, and
for in-scope financial entities the DORA classification and reporting duty.

**This factor exists to stop a common conflation.** "Not material for Item 1.05" does not mean
"no notification duty." The two questions have different tests, different timers and different
audiences. Recording them in one place is the point; merging them would be an error.

**Honest limit:** v1 tracks clocks for **SEC Item 1.05 and DORA only**. Any other obligation noted
here is a note — the engine computes no deadline for it, and does not pretend to.

### 5. `reputational` — reputational and relationship effects

Customer, counterparty, employee and market reaction; press and regulator attention; effects on a
pending transaction or financing.

**Honest limit:** this is the factor most prone to both catastrophizing and false comfort. Record
observable facts — customers who invoked a notice clause, coverage that ran, a counterparty that
paused — rather than a forecast of sentiment. If it cannot be observed, `unknown` is the honest
assessment and is not a failure.

### 6. `aggregation` — related incidents considered together

**The factor most often missed, and an explicit SEC concern.** A "cybersecurity incident" is
defined to include *a series of related unauthorized occurrences*, so a set of individually
unremarkable events arising from the same root cause, the same actor or the same unremediated
weakness may have to be assessed as one incident rather than five.

Name the other incidents in `relatedIncidentIds` and say in the rationale **why** they are or are
not related. A recorded "considered and not related, because —" is worth as much as a link; what
is worth nothing is never having asked.

**Shared infrastructure is evidence, not the test.** Three sprays from the same hosting provider
against different properties months apart are not a series; three waves of one campaign replaying
one credential list against one login path are. What pushes toward *one series*:

- the same actor or campaign, and the same corpus or tooling being reused
- the same target surface and the same **unremediated weakness** — the strongest signal, because
  it is the thing that made all of them possible
- continuity in time: the later event is a resumption, not a coincidence
- one remediation would close all of them

The failure mode this factor exists to catch: each occurrence lands just under whatever the
disclosure committee treats as consequential, while the combined impact would not have.

**Aggregating moves the discovery date back, and that is the consequence people miss.** If
three waves are one incident, the incident was discovered at the first wave — not the third.
The four-business-day Item 1.05 window still starts at the determination and is unaffected.
What *is* affected is *without unreasonable delay*, which runs from discovery: a determination
that looks prompt against wave three may look very different against wave one.

That is a reason to assess the aggregation question early, not a reason to answer it "no". The
engine does not compute this — it records the ids you name and the reasoning you write — but
the elapsed-days figure it reports is measured from the `discoveredAt` of the incident you are
looking at, so if you conclude the waves are one series, say so in the rationale and be
deliberate about which record carries the earlier date.

**Honest limit:** the engine will not infer relatedness. It records the ids you name and reports
them; it does not cluster incidents by time, actor or asset, because a false cluster and a missed
one are both judgments about facts the tool does not have.

## The aggregation rule, stated once

> Assess whether this incident is one of a series of related occurrences that should be
> considered together, and record the reasoning either way. Where related incidents are
> identified, the materiality judgment is made on the aggregate, not on each piece.

That is the whole rule. It is recorded on the `aggregation` factor and it is the only place in
this framework where one factor's assessment changes what the others are about.

## Completeness, which is not a score

`analyze` reports which of the six keys have been assessed and which have not. That is a
completeness check — *did anybody look at this?* — and it is the only counting the engine does.

It does not report how many came back `bearing`. A count of `bearing` factors is a score wearing
different clothes, and the moment it exists somebody will treat 4-of-6 as a threshold.

## What "without unreasonable delay" is, and what the engine says about it

Item 1.05 requires the materiality determination to be made **without unreasonable delay** after
discovery. It does not define a number of days, and neither does this tool.

What the engine does: report the elapsed days since `discoveredAt` where no determination has
been recorded, and flag it as an open item. What the engine does not do: call any number of days
unreasonable. That is a judgment about the facts and the circumstances, made with counsel — and a
tool that named a threshold would be manufacturing a standard the rule declines to set, then
handing the regulator a record of the day you crossed it.

## Receipts, with their limits attached

**SEC Item 1.05 of Form 8-K** — a registrant must disclose a cybersecurity incident it determines
to be material, describing the material aspects of its nature, scope and timing, and the material
impact or reasonably likely material impact.

**Limits, outward:** it applies to SEC registrants and nobody else; its technical-detail
carve-out covers the *planned response*, the *systems* and the *vulnerabilities* — **not the
incident**, whose nature, scope and timing Item 1.05(a) requires (see `disclosure-clocks.md`);
the determination is a company-specific judgment; and the rules have faced rescission pressure
and a materially reduced enforcement posture. Cite it as a preparedness obligation, never as an
imminent enforcement threat.

**Limits, inward:** which organisations are registrants is declared as `secItem105Scope` and
never inferred from a listing — an unlisted issuer reporting under Exchange Act s.15(d) is
inside the perimeter and a listed company may be outside it (CAC-AP-1 §2.4.1 covers what happens
when nobody has declared it). Inside the perimeter, **Item 1.05(c)** and **Item 1.05(d)** are
delay mechanisms, and the engine models neither. `disclosure-clocks.md` carries both, with the
Form 8-K boundary beside them.

**SEC Item 106 of Regulation S-K** — annual disclosure of cybersecurity risk management, strategy
and governance, including board oversight. **Limit:** it is an annual narrative obligation, not an
incident clock; it is listed here because it is the other half of what a board is asked about.
**Inward:** 17 CFR 229.106 carries **no exemption** — read in full, it is definitions, risk
management and strategy, governance, and a structured-data requirement, with no scaled or
omitted disclosure for any registrant inside its perimeter. Its one inward variation is
**Instruction 1 to Item 106(c)**, which reads "board of directors" as the supervisory or
non-management board for a foreign private issuer with a two-tier board, and as the board of
auditors for one other foreign-private-issuer board structure the Instruction cross-refers to.
That is an accommodation, not a carve-out: nobody inside the perimeter is relieved of the
disclosure.

**DORA (Regulation (EU) 2022/2554, applicable from 17 Jan. 2025) and its reporting RTS,
Commission Delegated Regulation (EU) 2025/301** — in-scope financial entities must
classify ICT-related incidents and report major ones on the Art. 5 windows. **Limits, outward:**
it binds in-scope EU financial entities only; classification as *major* is itself a
criteria-based judgment this tool does not make; and the windows are counted in clock hours, not
business days. See `disclosure-clocks.md`.

**Limits, inward — who is excluded from inside that perimeter.** **Art. 2(3)** takes six
categories out of DORA altogether even though they sit in the financial-entity list: AIFMs
under Art. 3(2) of Directive 2011/61/EU; insurance and reinsurance undertakings under Art. 4 of
Directive 2009/138/EC; IORPs whose schemes together have **no more than 15 members**; persons
exempted under Arts. 2 and 3 of Directive 2014/65/EU; insurance, reinsurance and ancillary
insurance intermediaries that are **micro, small or medium-sized enterprises**; and post office
giro institutions under Art. 2(5)(3) of Directive 2013/36/EU. **Art. 2(4)** lets a Member State
exclude certain Directive 2013/36/EU entities on its own territory, so the answer can differ by
country.

**The exemption that does NOT apply here, and it is the tempting one.** DORA's **Art. 16
simplified ICT risk management framework** disapplies **"Articles 5 to 15"** and nothing else.
Incident reporting lives in **Chapter III (Arts. 17–23)**, with major-incident reporting at
Art. 19 — untouched by Art. 16. So an Art. 16 entity carries the full reporting obligation, and
the only mention of microenterprises anywhere in Chapter III is a mandate to the ESAs to bear
their capacity in mind when setting the Art. 18 classification criteria, which is not an
exemption. The Art. 16 limit **is** correctly attached to the residual-risk inventory receipts
in `exceptions-register` and `ciso-board-translation`, which cite RTS 2024/1774; carrying it
across to this one because the wording matches would be an invented exemption in a disclosure
record.

**Delaware oversight (the *Caremark* line)** — *In re Caremark Int'l Inc. Derivative Litig.*,
698 A.2d 959 (Del. Ch. 1996), as restated in *Stone v. Ritter*, 911 A.2d 362 (Del. 2006). A board
that can show it received information about a material incident and acted on it is far better
placed than one that cannot. **Limit:** this is a reason to keep a good record, not an obligation
with a deadline — and the liability threshold *Stone* fixed is bad faith, not imperfection.

Never imply a filing duty that is not there. The most common way to do that by accident is to
describe the four-business-day window without saying that it starts at the **determination**, and
that an incident under honest assessment has **no running Item 1.05 clock at all**.

## Not legal advice

A materiality determination is a legal judgment. This framework structures and records it; it does
not make it, and it is not a substitute for counsel. Involve counsel on the determination and on
any filing.

---

*A Cyber Aware Creation · Not affiliated with NIST. Not legal advice.*
