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

### Documented disclosure-clock deviations, stated rather than modelled

Three places where this engine knowingly does less than the instrument. Each is stated because
a deviation a reader cannot see is indistinguishable from a bug, and each **errs early**, which
is the safe direction for a filing deadline.

- **Regulation No 1182/71 is not applied to the one-month window.** DORA's final-report window
  is *"one month"*, and EU time-limit computation has its own day-exclusion and end-of-day
  rules. `add_months` does plain calendar arithmetic instead. The effect is **at most about one
  day early**, and a DORA-scoped entity should confirm the exact date with counsel.
  ⚠️ **Do not "fix" `add_months` to model 1182/71.** Early is the safe direction, and a
  half-modelled EU computation rule would be less predictable than an honestly stated one.
- **The Item 1.05 amendment window is not computed.** Form 8-K General Instruction 2 sets a
  **second** four-business-day clock, running from when information unavailable at the original
  filing becomes available. `WINDOWS["sec-1.05"]` is unchanged and models the original filing
  only. Modelling the amendment is filed as its own item.
- **An updated intermediate report does not move the final window.** Art. 5(1)(c) anchors the
  final report on *"the latest updated intermediate report"*, and `dora_clocks` has no
  representation of an update — it anchors on the intermediate report as filed. Where an update
  exists the computed date is **early**, which is again the safe direction.

### Limits on the SEC clock

- ⭐ **The day-zero convention is the Form's, not this engine's.** Form 8-K General Instruction
  B.1 provides that where the triggering event falls on a Saturday, Sunday or holiday, *"the
  four business day period shall begin to run on, and include, the first business day
  thereafter."* That is why `business_days_after` treats the anchor as day zero and counts
  forward — the worked table above is **citable, not merely asserted**.
- **The four-business-day period comes from Form 8-K, General Instruction B.1** — the Form is
  prescribed at **17 CFR 249.308**. Not §229.105 (Risk Factors), not §229.106 (the annual item),
  and not the body of Item 1.05. Earlier drafts of this file named the wrong locus.
- **The engine computes a date, not a time.** Under Rule 13(a)(2) of Regulation S-T
  (**17 CFR 232.13(a)(2)**) a filing transmitted after 5:30 p.m. Eastern is deemed filed the next
  business day. Treat the computed deadline as the last day, not the last moment, and file with
  room.
- **Item 1.05 applies to SEC registrants** and nobody else — and the engine no longer guesses
  who those are. Whether an organisation must file current reports on Form 8-K under the
  Exchange Act is a securities-law determination, so it is declared on the applicability
  profile as `secItem105Scope`, by counsel, and inferred from nothing.

  Until v0.64.x it was inferred, from `listedEntity` — a flag meaning only that shares trade on
  an exchange. That is not the same fact in either direction, and it failed in both: a
  London-listed company with no Exchange Act obligation was given an 8-K clock it does not owe,
  and an unlisted US issuer reporting under Exchange Act s.15(d) was denied one it does. Where
  scope is **not declared**, the battery is still asked and **no window is computed** — see
  CAC-AP-1 §2.4.1 and the `scope-not-declared` state below.
- **This engine models the Form 8-K path only, and a registrant that does not use it is not
  covered.** Not every organisation with a US reporting obligation discloses on Form 8-K; a
  foreign private issuer follows a different route on a different form, and this engine has no
  representation of it — no state, no anchor, no window.

  That is a deliberate non-goal rather than an omission, and the reason is this file's own
  standard: a clock ships here only once its rule has been read against the primary source and
  written down with worked examples, the way Item 1.05 and DORA Art. 5 are. Nobody has done
  that read for the alternative path, so the honest position is that it does not exist here.
  The practical consequence is narrow but must be said plainly: declaring `secItem105Scope`
  false is a statement about **Form 8-K**, not a finding that no disclosure obligation exists,
  and this tool computes no deadline for anything it has not modelled.
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
- **A rescission petition is pending and enforcement activity has visibly slowed. Neither has
  changed the rule.** *Dated, because an undated posture claim is the fastest-decaying sentence
  a compliance tool can carry — as at August 2026.*
  Both sentences below are the **verbatim** replacement text from Reference Watch dossier
  RW-001, findings F1 and F3 (2026-08-08). They are quoted rather than paraphrased because a
  paraphrase of a posture claim is how the undated original got here in the first place.

  - **The petition — RW-001 F1, verbatim:**

    > In May 2025 five financial-industry trade associations petitioned the SEC to rescind
    > Form 8-K Item 1.05 (File No. 4-856). As of 2026-08-08 the Commission has not acted on
    > the petition: no proposal has been issued, the item does not appear on the SEC's
    > regulatory agenda, and Items 1.05 and 106 remain in force unchanged.

    A petition is not a proposal and not a rule.

  - **The enforcement half — RW-001 F3, verbatim:**

    > As of 2026-08-08 the SEC has announced no public-company cybersecurity-disclosure
    > enforcement action since 2024-10-22, and dismissed the SolarWinds action with prejudice
    > on 2025-11-20. The Commission has not stated a change of policy: the Cyber and Emerging
    > Technologies Unit's stated scope still includes public-issuer cyber disclosure, and
    > Items 1.05 and 106 remain in force. This is a change in observed enforcement activity,
    > not in stated obligation.

    The dismissal is **Litigation Release No. 26423**, which records in the same document that
    it *"does not necessarily reflect the Commission's position on any other case"*. The Cyber
    and Emerging Technologies Unit was announced **20 February 2025**.

  This is a preparedness and defensibility tool. Do not sell it as an imminent-enforcement tool;
  the board-safety eval fails the render if it reads that way. **Re-check both dates before
  relying on either** — that is what they are here for.

---

## DORA — clock hours, from awareness and from classification

For in-scope EU financial entities, a **major** ICT-related incident carries three reports. The
windows the engine implements:

| window | deadline |
|---|---|
| `initial` | **4 hours** from classification as major, and no later than **24 hours** from becoming aware — the earlier of the two, **except** where classification came more than 24 hours after awareness, when it is 4 hours from classification alone |
| `intermediate` | **72 hours** from submission of the initial notification |
| `final` | **one month** from the intermediate report, or the latest updated intermediate report |

All three are **Article 5 of Commission Delegated Regulation (EU) 2025/301** — the RTS on the
content and time limits for the initial notification and the intermediate and final reports,
made under DORA. Cite that instrument for the windows, not RTS 2024/1774, which is the ICT
risk-management RTS and sets no reporting deadline.

⚠️ **Two DORA articles are in play and they do different jobs.** **Article 19(4)** is the
reporting obligation; **Article 20** is the RTS mandate, and it is Article 20 that empowers the
Commission to set the *time limits*. The RTS's own citation line reads *"Article 20, third
subparagraph thereof"*. An earlier version of this file named 19(4) alone as the empowerment,
which is the wrong one for a deadline.

> **The 19(4) label here rests on the RTS's own in-text cross-reference, not on a direct read of
> DORA Arts. 19/20** — EUR-Lex truncates those articles in the HTML rendering this project can
> open. Marked rather than presented as verified.

### Why these anchors are timestamps

DORA counts **clock hours**. SEC counts **business days**. The store therefore holds
`anchors.awareAt` and `anchors.classifiedAt` as `YYYY-MM-DDTHH:MM` timestamps while everything
else is a date, and that asymmetry is deliberate — see `schema.md`.

**If an anchor is absent, the DORA clock reports `anchor-missing`, not a deadline.** The engine
will not read a bare date as midnight to manufacture hour precision. A deadline that looks exact
and is not is worse than a visible gap.

### The `initial` deadline, and the carve-out that is easy to miss

Normally the deadline is the **earlier** of the two bounds: an entity that classifies promptly
cannot use the four-hour bound to run past the 24-hour awareness cap. Where only `awareAt` is
set, the 24-hour bound is used alone and the output says so.

**Article 5(2) is the exception, and it runs the other way.** Where the entity has *not*
classified the incident as major within 24 hours of awareness and classifies it later, the
notification is due *"within four hours from the classification"* — full stop. The awareness cap
has already lapsed and does not bind.

Until v0.49.0 this engine applied the earlier-of rule unconditionally, which on a
late-classified incident produced a deadline **already in the past** and reported it
**overdue** while four hours still remained. That is a false overdue, and this file argues
elsewhere that a false overdue is the worst way for a clock to fail: it pushes somebody into
filing before they are ready. The engine now applies 5(2), the note names the provision that
governed, and the self-test pins both the deadline and the `due` state.

`intermediate` and `final` anchor on the **previous filing**, not on the incident — so they are
`not-started` until `dora:initial` and `dora:intermediate` respectively are recorded in
`disclosure.filings`. That is the rule as written, and it means a missed initial notification does
not silently produce a phantom intermediate deadline.

### Limits on the DORA clocks

- **Classification as *major* is a criteria-based judgment** made against the classification RTS
  thresholds. This engine does not make it, and does not check it. It runs the clock from the
  moment you record that you made it.
- **The engine does not apply the next-working-day allowance, and the allowance is narrower than
  it sounds.** Article 5(4) of RTS 2025/301 gives relief only where a deadline falls **on a
  weekend day or a bank holiday** in the entity's Member State — not merely outside working
  hours — and then only until **noon of the next working day**. Article 5(5) withdraws it
  entirely for the initial notification and the intermediate report by **credit institutions,
  central counterparties, operators of trading venues, and entities identified as essential or
  important under Article 3 of NIS2 (Directive (EU) 2022/2555)**. ⚠️ **Article 5 has SIX
  paragraphs and this file described five.** **Article 5(6)** lets a competent authority
  disapply the 5(4) relief for an entity that is *"significant or ha[s] a systemic character"* —
  which changes no number this engine computes, because it never applies 5(4) in the first
  place, but a Limits section that stopped at 5(5) was incomplete about the instrument it
  summarises. The engine computes the raw
  hour deadline for everyone. That is **earlier** than any relieved deadline — the safe
  direction — but it is not the letter of the rule and should not be quoted as such.
- **A deadline you cannot meet still has to be told to the regulator.** Article 5(3) requires an
  entity that cannot file in time to inform the competent authority **before the deadline
  passes** and explain why. The engine tracks the deadline, not that obligation.
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
| `scope-not-declared` | nobody has declared whether this regime reaches this organisation, so no deadline is computed |
| `due` | running; a deadline exists and has not passed |
| `overdue` | the deadline has passed with no filing recorded |
| `filed` | a filing is recorded for this window |

`not-started` and `anchor-missing` are different states on purpose. The first is a correct,
comfortable position — nothing is owed yet. The second is a gap in the record, and it is the one
that should make somebody act.

`scope-not-declared` is a third kind of thing again, and it exists because the other five could
not say it. `not-applicable` means nobody tracked the regime; `not-started` means the anchor
event has not happened. Neither means *we do not know whether this regime reaches you* — and
with no word for that, an undeclared perimeter borrowed silence: the clock simply computed. That
is how a four-business-day Form 8-K deadline came to be produced for organisations that owe no
such filing.

The row names the flag that would settle it, and where the incident is tracked against the
regime anyway it escalates as `scope-undeclared`. Both halves are the rule: withholding without
escalating trades a false date for a blank one, and a firm that has simply not filled in its
profile would then look identical to one that is genuinely out of scope.

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

That exception belongs to a **declared** no, and deliberately not to a silence. A declared no is
an answer, so an assessor who tracked the regime anyway is contradicting one, and the engine
reports the contradiction rather than picking a side. A silence is not an answer: there is
nothing to contradict, and nothing to compute a date from. The tracking still earns attention —
that is what `scope-undeclared` is for — but it does not manufacture a deadline.

### The escalation carries a CONDITIONAL date, and the clock still does not

Withholding the clock is right and withholding it *in silence* is not. A real registrant who has
simply not filled in the profile is left with no date at all against an obligation that runs four
business days from the materiality determination — and that is a worse outcome than the
manufactured date this rule exists to prevent, arriving by a different route.

So `scope-undeclared` states it: **if `sec-1.05` applies, the four-business-day Item 1.05 window
closes on that date.** The clock field stays empty, the state stays `scope-not-declared`, and
nothing goes `overdue`.

**A conditional is not a judgement.** *"If X applies, the date is Y"* asserts nothing whatever
about whether X applies, and the sentence says so in the same breath rather than trusting the
reader to infer it. Computing the clock instead would assert that Item 1.05 *does* apply,
inferred from an assessor's tag — a legal conclusion, and *record and refuse, never judge*
forbids it.

The conditional clause is **load-bearing and lives in the emitted text**, not only here.
*"Window closes 20 July"* is wrong. *"If `sec-1.05` applies, the window closes 20 July"* is right.
`evals/scope-withheld.sh` asserts the date is the one the declared path would compute **to the
day**, and separately that no escalation ever states the window closes without its clause.

**DORA carries it too, and NOT as a copy** (BL-237, decided). `sec-1.05` works because its
anchor — the materiality determination — exists by the time the question arises. DORA stacks
**two** unknowns: scope may be undeclared *and* the anchor absent, because its windows run in
clock hours from `awareAt` or `classifiedAt` and neither may ever have been recorded. So there
are two paths:

- **Anchor present.** Identical in shape to `sec-1.05`: *"If `dora` applies, the initial report
  window closes at DATETIME — a conditional, not a finding that it applies."*
- **Anchor absent.** **No date. No placeholder. No empty string dressed as a value.** The
  message names the missing anchor instead: *"neither `awareAt` nor `classifiedAt` is recorded,
  and DORA counts clock hours from one of them. No date is asserted and none is invented."*

The second message is the **more useful of the two.** It names something the reader can go and
supply, and it is true whether or not DORA applies — so it needs no scope hypothesis at all.
*"If DORA applies, the window closes ???"* would be worse than silence: it looks like a
computation and is none.

⚠️ **That second path is the one a careless implementation gets wrong, and it fails in the
direction that looks like success.** An empty-or-`None` date still renders — the sentence is
there, the field is there, it simply has nothing in it — so a check written as *"a date is
present"* goes green on a lie. `evals/dora-conditional.sh` therefore asserts the **absence** of
the conditional clause and the absence of anything datetime-shaped, and its registered mutation
emits an empty-but-present date to prove those checks bite.

**A declared-false profile gets no conditional** on either regime: it already has a real clock
and a reported conflict, and a conditional beside them would put two dates on one incident.

**NYDFS is not a regime in this engine** and does not become one by implication.

## Not legal advice

These clocks are decision support. The determination, the classification and any filing are legal
judgments made with counsel. The engine computes dates; it does not tell you whether you owe a
filing.

---

*A Cyber Aware Creation · Not affiliated with NIST. Not legal advice.*
