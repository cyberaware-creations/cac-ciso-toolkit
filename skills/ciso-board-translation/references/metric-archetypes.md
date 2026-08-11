# The Seven Metric Archetypes

Most security metrics that reach a board are one of seven recognizable shapes,
and each hides a *different* way the raw number lies to a director. Read the
relevant section when the fact you're translating matches one of these — it
gives you the specific trap to expose, the sharp board ask to land on, the
receipt angle to ground it, and a one-line Grade-A example.

For every archetype the same discipline applies: never invent the numbers, name
the real exposure, and end on a decision (fund the close, or record the
acceptance). Numbers in the examples are illustrative placeholders.

## Contents

1. [Patch coverage — the coverage % that says nothing](#1-patch-coverage)
2. [Phishing click rate — the reassuring 4%](#2-phishing-click-rate)
3. [Dwell time / MTTD — the 8-hour illusion](#3-dwell-time--mttd)
4. [Third-party / vendor risk — the 90% that isn't yours](#4-third-party--vendor-risk)
5. [MFA / identity coverage — the last 5%](#5-mfa--identity-coverage)
6. [Framework maturity score — the maturity mirage](#6-framework-maturity-score)
7. [Backup / recovery — the backup you haven't tested](#7-backup--recovery)

## 1. Patch coverage

**The trap.** A coverage percentage that looks reassuring and says nothing. "87%
patched" hides *which* systems make up the missing slice — and that slice is
never random. The remainder typically concentrates the real risk (internet-
facing, revenue-critical), which the average erases.

**The board ask.** Fund the close (cost + what you need), or formally record the
acceptance of the exposure window on the specific systems that remain.

**Receipt angle.** A recorded acceptance produces the documented board decision
the Caremark line rewards. (See `references/regulatory-receipts.md`.)

**Grade-A one-liner.** "We patch 87% within SLA, up from 78% — gaining ground —
but the last 13% is 9 internet-facing systems open for 40 days, two blocked by
the billing app; fund one engineer plus a maintenance window to close it under 7
days, or accept the 40-day window on the record."

## 2. Phishing click rate

**The trap.** A *low* number that feels like safety and ends the conversation.
4% of 5,000 people is still ~200 who clicked, and an attacker needs exactly one.
The metric measures *your simulation*, not a real spear-phish, and it is silent
on *who* clicked and whether they reported it.

**The board ask.** Fund phishing-resistant MFA on high-value groups (finance,
admins), or accept that a single click can land on a payment system.

**Receipt angle.** **Business email compromise** is among the costliest cybercrime
categories the FBI records: **$3,046,598,558 in reported losses across 24,768
complaints in 2025**, second only to investment fraud (FBI IC3, *2025 Internet
Crime Report*, against 2025 totals of 1,008,597 complaints and $20.877bn). Human
error here is predictable, therefore foreseeable, therefore governable — which is
what makes it a board decision rather than an IT footnote.

> ⚠️ **Two limits, and both belong in the room with the number.**
>
> **IC3 counts REPORTED losses from complaints filed with IC3.** It is not total
> economic loss and it is not an estimate of one — it is the sum of what people
> who chose to report told the FBI. Under-reporting is unmeasured, so the figure
> is a floor of a subset, not a measurement of the problem.
>
> **"Wire fraud" is NOT an IC3 category. BEC is.** An earlier version of this
> sentence said *"BEC and wire fraud"*, and the citation supports only the first
> — wire fraud is a federal criminal offence (18 U.S.C. § 1343), not a line in
> this report. **Pin the sentence to BEC and give the year**, or half of it is
> uncited. A board member who checks will find the BEC row and not the other.

**Grade-A one-liner.** "Click rate is 4%, down from 6% — improving — but that's
~200 people, and finance approves payments without phishing-resistant MFA; fund
hardware-key MFA for that group, or accept that one click can reach the payment
system."

## 3. Dwell time / MTTD

**The trap.** A time metric with no reference point, distorted three ways:
there's no baseline to say whether 8 hours is good or bad; **survivorship bias**
means the average only counts incidents you actually *found*; and it hides *when*
you're watching — an 8-hour average during business hours says nothing about the
nights and weekends when attackers prefer to move.

**The board ask.** Fund 24/7 detection coverage, or accept the off-hours
detection gap on the record.

**Receipt angle.** Detection speed drives disclosure timeliness (SEC Item 1.05
runs a four-business-day clock from the materiality determination; DORA incident
reporting), and a documented monitoring capability is the kind of board-level
reporting whose *absence* is what Caremark claims survive on. Do not put it the
other way round — see regulatory-receipts.md on *Bingle*, where the reporting
system was called "subpar" and the claim was dismissed anyway.

**Grade-A one-liner.** "Mean time to detect is 8 hours — but that's a business-
hours average that only counts what we caught, and we don't watch nights or
weekends; fund 24/7 detection, or accept an unmonitored off-hours window on the
record."

## 4. Third-party / vendor risk

**The trap.** A metric that reports *your effort*, not the risk you actually
control. "90% of vendors assessed" often means a stale, self-attested
questionnaire — and the percentage ignores **concentration**: the single vendor
whose breach takes you down matters more than the other 89%. Their breach still
becomes your notification obligation and your liability.

**The board ask.** Fund real oversight of the critical few vendors, or accept
the concentration risk on the named vendor(s).

**Receipt angle.** **NYDFS 23 NYCRR § 500.11**, *"Third-party service provider
security policy"*, and **DORA (Reg. (EU) 2022/2554) Chapter V, Arts. 28–31** —
28 general principles, 29 the strategy, 30 contractual arrangements, 31 key
contractual provisions — both target this; breach-notification liability runs to
the data owner, not the vendor.

> ⚠️ **Cite Arts. 34+ only if the point is critical-provider designation.** That
> is the oversight framework for providers the ESAs have designated critical, and
> it is a **different claim** about a different population. Reaching for it here
> would overstate what a third-party assessment-coverage metric measures, which is
> the organisation's own diligence over its own arrangements.

**Grade-A one-liner.** "We've assessed 90% of vendors — but that's self-attested
paperwork, and one vendor holds the data whose breach would force *our*
notification; fund continuous oversight of that critical vendor, or accept the
concentration risk on the record."

## 5. MFA / identity coverage

**The trap.** The uncovered gap is *inversely* correlated with risk — the 5%
left out is usually admins, service accounts, and legacy systems, the highest-
value targets. On top of that: push and SMS MFA are bypassed at scale (MFA
fatigue, SIM swap, adversary-in-the-middle); enrollment is not enforcement; and
non-human identities are often unprotected entirely.

**The board ask.** Move crown-jewel accounts to phishing-resistant MFA (FIDO2 /
hardware keys), or accept the privileged-access gap on the record.

**Receipt angle.** **NYDFS §500.12** sets an MFA baseline for covered entities,
and the escape route is narrow *and* conditional: written CISO approval of
*"reasonably equivalent or more secure compensating controls"*, reviewed at least
annually — and only *"if the covered entity has a CISO"*, so an entity without one
has no such route at all. (See `regulatory-receipts.md` for the full reading,
including the opposite structure at §500.17(b)(2).)

> ⛔ **The insurance half of this angle is DELIBERATELY UNSOURCED — BL-244.**
> Two assertions used to sit on this line and neither is a receipt:
>
> - *"MFA is a common cyber-insurance precondition"* — **market practice.**
>   Widely reported, carrier- and year-specific, no instrument behind it.
> - *"a privileged-access gap can void a claim"* — **a claim about insurance
>   contract law**, not a fact about MFA. Whether a gap voids cover turns on the
>   policy wording, on what was warranted or represented at placement, on the
>   jurisdiction, and on whether the term is a condition precedent or a warranty.
>
> **Do not put either to a board as a legal position.** The board ask above does
> not need them: *"accept the privileged-access gap on the record"* stands on
> §500.12 and on the trap alone.

**Grade-A one-liner.** "MFA covers 95% — but the missing 5% is admins and
service accounts, and our push MFA is phishable anyway; move privileged accounts
to hardware keys, or accept the crown-jewel gap on the record."

## 6. Framework maturity score

**The trap.** A composite average that hides the one weak function. A 3.2/5
overall can conceal a strong Protect at 4 masking a Recover at 1.5. It measures
*process*, not *outcome*, and it's usually self-assessed. The average is
precisely the thing that buries the material gap.

**The board ask.** Fund the *specific weak function* up one level — not a
uniform push to 5 everywhere, which wastes money.

**Receipt angle.** **NIST publishes no CSF maturity score, so a "3.2 out of 5" is
the organisation's own scale — not the framework's.** CSF 2.0's **Tiers** run 1–4
and characterise the *rigour* of an organisation's cybersecurity risk governance
and risk management; they are not a scale to be averaged or trended, and this
suite's own `nist-csf` skill refuses to render them as one. Per **NIST CSWP 29
§3.2**, Tiers *complement* a risk-management methodology rather than replace it,
and progression to a higher Tier is encouraged **only** when risks or mandates are
greater, or when a cost-benefit analysis indicates a feasible and cost-effective
reduction of negative risk.

So "get everything to 5" is not what the framework asks for. A board funding a
uniform push is funding something NIST does not recommend, while the *material*
gap stays buried in the average — and after an incident, the question is whether
the board governed **that** gap.

**Grade-A one-liner.** "Our CSF maturity is 3.2, up from 2.9 — but that average
hides Recover at 1.5 behind a strong Protect; fund Recover up one level, or
accept the recovery gap on the record — chasing a uniform 5 is the wrong
target."

## 7. Backup / recovery

**The trap.** Backup success is not restore success. Most organizations have
never run a full restore drill, so real RTO is unknown (and, for those who test,
often days). Ransomware hunts backups first, so immutability matters — and
RTO/RPO figures are usually *assumed*, not measured.

**The board ask.** Fund isolated/immutable recovery plus quarterly restore
drills, or accept an unknown recovery time on the record.

**Receipt angle.** Operational-resilience regimes require recovery to be
*tested*, not merely planned. Under DORA's ICT risk-management RTS — **Commission
Delegated Regulation (EU) 2024/1774** — **Art. 8(2)(b)(i)** puts *"backup and
restore requirements of ICT systems"* into the ICT operations policy, and
**Art. 25** (*Testing of the ICT business continuity plans*) requires testing that
contains *"the testing of switchover from primary ICT infrastructure to the
redundant capacity, backups and redundant facilities"* and that verifies critical
or important functions can be operated for a sufficient period and normal
functioning restored (**Art. 25(2)(c)**).

> ⚠️ **Read Art. 25 for what it is: a business-continuity testing duty that must
> COVER backups — not a standalone "test your restores" mandate.** No provision
> isolates periodic backup-restore testing; the obligation sits inside the BCP
> testing cycle. Telling a board *"DORA requires quarterly restore drills"* states
> a cadence the instrument does not set — the quarterly drill in the board ask
> above is **this toolkit's recommendation**, not a regulatory minimum.
>
> ⛔ *"Insurers now probe immutability and restore testing directly"* also sat on
> this line and is **market practice, not a receipt** — no instrument, and
> carrier- and year-specific. Filed as **BL-244**.

**Grade-A one-liner.** "Backups succeed on 99% of systems — but we've never run a
full restore, so real recovery time is unknown and our backups aren't immutable;
fund immutable recovery plus quarterly restore drills, or accept an unmeasured
recovery time on the record."
