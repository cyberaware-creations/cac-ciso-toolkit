# Disclosure clocks — SEC Item 1.05 and DORA

The clocks are the one part of this skill that is **deterministic**, and therefore the one part
that has to be exactly right. The judgment is the human's; the arithmetic is the engine's, and an
engine that miscounts a weekend has done the only thing it was for, wrongly.

**Scope in v1: SEC Item 1.05 and DORA only.** State breach-notice statutes, NIS2 and sectoral
regimes are out of scope — noted on the `regulatory` factor as text, with no computed deadline.
The engine does not compute a deadline it cannot compute correctly.

---

## SEC Item 1.05 — four business days from the **determination**

### The rule the engine implements

> The 8-K is due **four business days after the registrant determines that the incident is
> material.** The determination itself must be made *without unreasonable delay* after discovery.

### The distinction that matters most

**The clock starts at the determination date, not the discovery date.**

This is the single most consequential fact in this file, and getting it backwards fails in both
directions. Anchoring on discovery invents a deadline that does not exist, and a tool that shows a
false overdue flag will eventually push somebody into filing something they had not yet decided
was true. Anchoring correctly means an incident under honest assessment shows **`not-started`** —
no deadline, no days remaining, nothing red.

That is not a loophole, and the engine does not let it read as one. Where an incident has been
open for a while with no determination recorded, `analyze` reports the elapsed days since
discovery as an open item. What it does not do is call any number of days unreasonable — the rule
sets no number, and a tool that invented one would be manufacturing a standard and then timing
you against it. See `materiality-factors.md`.

### The counting rule, stated so it can be checked

- A **business day** is any day that is not a Saturday, not a Sunday, and not in
  `settings.holidays`.
- The determination day itself is **day zero** and is not counted, whether or not it is a
  business day.
- Count forward, four business days. That day is the deadline.

Worked, so the arithmetic is auditable:

| determined | count | deadline |
|---|---|---|
| Mon 2026-07-06 | Tue 1, Wed 2, Thu 3, Fri 4 | **Fri 2026-07-10** |
| Fri 2026-07-10 | Mon 1, Tue 2, Wed 3, Thu 4 | **Thu 2026-07-16** |
| Sat 2026-07-11 | Mon 1, Tue 2, Wed 3, Thu 4 | **Thu 2026-07-16** |
| Tue 2026-07-14, with Fri 2026-07-17 a holiday | Wed 1, Thu 2, Mon 3, Tue 4 | **Tue 2026-07-21** |

Note rows two and three: a Friday and a Saturday determination land on the same deadline, because
the weekend contributes nothing either way.

### The holiday calendar, and its direction of error

`settings.holidays` ships **empty**. The engine does not bundle a federal-holiday calendar,
because a stale bundled calendar is a wrong answer that looks authoritative, and holidays are a
per-year fact somebody has to supply anyway.

With no holidays supplied, a federal holiday is counted as a business day and the computed
deadline lands **one day early per holiday in the window**. Early is the safe direction. It is
still wrong. Supply the calendar:

```bash
python3 scripts/incident_analysis.py init incidents.inc --client "Acme" \
    --holiday 2026-07-03 --holiday 2026-09-07 --holiday 2026-11-26
```

### Limits on the SEC clock

- **The engine computes a date, not a time.** Under Rule 13(a)(2) of Regulation S-T
  (**17 CFR 232.13(a)(2)**) a filing transmitted after 5:30 p.m. Eastern is deemed filed the next
  business day. Treat the computed deadline as the last day, not the last moment, and file with
  room.
- **Item 1.05 applies to SEC registrants** and nobody else.
- **The technical-detail carve-out is narrower than it is usually described, and it does not
  cover the incident.** Instruction 4 to Item 1.05 says a registrant *"need not disclose specific
  or technical information about its planned response to the incident or its cybersecurity
  systems, related networks and devices, or potential system vulnerabilities in such detail as
  would impede the registrant's response or remediation of the incident."* Three things: the
  **response**, the **systems**, the **vulnerabilities**. The incident itself is not among them —
  Item 1.05(a) requires the material aspects of its *nature, scope, and timing*. A tool that
  produced a technical narrative of your defences for an 8-K would be answering a question the
  rule did not ask; a tool that read this carve-out as licence to withhold what happened would be
  worse, and this file said something close enough to that to matter until v0.48.0.
- **Two delay mechanisms exist, and the engine models neither.**
  - **Item 1.05(c)** — the Attorney General may determine that disclosure poses a substantial
    risk to national security or public safety: up to 30 days, a further 30 on a renewed
    determination, then a final 60 in extraordinary circumstances, and beyond that only by
    Commission exemptive order.
  - **Item 1.05(d)** — a registrant subject to the FCC's breach-notification rule
    (**47 CFR 64.2011**) may delay for the period applicable under that rule, and in no event
    more than **seven business days** after the notification it requires, provided it notifies
    the Commission by EDGAR correspondence.

  If either is in play, the deadline computed here is not your deadline.
- **The rules have faced rescission pressure and a materially reduced enforcement posture.** This
  is a preparedness and defensibility tool. Do not sell it as an imminent-enforcement tool; the
  board-safety eval fails the render if it reads that way.

---

## DORA — clock hours, from awareness and from classification

For in-scope EU financial entities, a **major** ICT-related incident carries three reports. The
windows the engine implements:

| window | deadline |
|---|---|
| `initial` | **4 hours** from classification as major, and no later than **24 hours** from becoming aware of the incident — whichever comes first |
| `intermediate` | **72 hours** from the initial notification |
| `final` | **one month** from the latest intermediate report |

### Why these anchors are timestamps

DORA counts **clock hours**. SEC counts **business days**. The store therefore holds
`anchors.awareAt` and `anchors.classifiedAt` as `YYYY-MM-DDTHH:MM` timestamps while everything
else is a date, and that asymmetry is deliberate — see `schema.md`.

**If an anchor is absent, the DORA clock reports `anchor-missing`, not a deadline.** The engine
will not read a bare date as midnight to manufacture hour precision. A deadline that looks exact
and is not is worse than a visible gap.

The `initial` deadline is the **earlier** of the two computed bounds, so an entity that classifies
late does not thereby extend the 24-hour awareness cap. Where only `awareAt` is set, the 24-hour
bound is used alone and the output says so.

`intermediate` and `final` anchor on the **previous filing**, not on the incident — so they are
`not-started` until `dora:initial` and `dora:intermediate` respectively are recorded in
`disclosure.filings`. That is the rule as written, and it means a missed initial notification does
not silently produce a phantom intermediate deadline.

### Limits on the DORA clocks

- **Classification as *major* is a criteria-based judgment** made against the classification RTS
  thresholds. This engine does not make it, and does not check it. It runs the clock from the
  moment you record that you made it.
- **The engine does not apply the next-working-day allowance.** The reporting rules provide relief
  where a deadline falls outside working hours or on a weekend or public holiday; the engine
  computes the raw hour deadline instead. That is **earlier** than the relieved deadline — the
  safe direction — but it is not the letter of the rule, and it should not be quoted as such.
- **Windows and content requirements are set by the RTS/ITS and are amendable.** Verify against
  the current text before relying on a date this tool prints.
- **DORA binds in-scope EU financial entities only.** `regimes` is set per incident for exactly
  this reason: scope is a fact about the entity, not a global default.

---

## Clock states

| state | meaning |
|---|---|
| `not-applicable` | the incident is not tracked against this regime |
| `not-started` | the anchoring event has not happened — for Item 1.05, no `material` determination |
| `anchor-missing` | the regime applies and the event has happened, but the anchor timestamp was never recorded |
| `due` | running; a deadline exists and has not passed |
| `overdue` | the deadline has passed with no filing recorded |
| `filed` | a filing is recorded for this window |

`not-started` and `anchor-missing` are different states on purpose. The first is a correct,
comfortable position — nothing is owed yet. The second is a gap in the record, and it is the one
that should make somebody act.

### There is no state for "the profile narrowed this away"

`analyze --context` against an applicability profile that declares a regime out of scope does
**not** produce a row in some seventh state. The windows are **absent** — a question nobody asked
has no answer, and inventing a state for it would put a clock on the page whose only content is
that there is no clock. Where they went is recorded beside them, naming who declared it and when
(CAC-AP-1 §2.4).

An incident explicitly tracked against the regime **keeps its clock regardless.** The profile
narrows the default question set; it does not close a window an assessor opened. The
disagreement is reported as a conflict rather than resolved — which is why narrowing can never
suppress an `overdue`.

## Not legal advice

These clocks are decision support. The determination, the classification and any filing are legal
judgments made with counsel. The engine computes dates; it does not tell you whether you owe a
filing.

---

*A Cyber Aware Creation · Not affiliated with NIST. Not legal advice.*
