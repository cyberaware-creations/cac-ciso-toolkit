---
name: incident-materiality
description: >-
  Structure and record a cybersecurity incident materiality determination, and
  run the disclosure clocks that follow from it. Walks the six factors the
  judgment turns on — financial impact, operational disruption, data affected,
  regulatory and contractual triggers, reputational effects, and whether related
  incidents must be assessed as one series — recording each with its reasoning,
  the person and the date, and refusing an assessment that has no rationale.
  Never emits a verdict: no scale, no score, no threshold, because materiality is
  a legal judgment made with counsel and a generated number would be discoverable
  alongside the determination it disagreed with. Computes the SEC Item 1.05
  window as four business days from the determination — not from discovery, so an
  incident still under assessment has no window open — and the DORA initial,
  intermediate and final report windows in clock hours. Keeps every determination
  as an appended record, so the "what did we know and when did we decide"
  sequence survives. Use when asked whether an incident is material, whether it
  has to be disclosed, when the 8-K clock starts or how much of it is left, to
  record a determination or a disclosure decision, to track DORA reporting
  windows, or to draft an audit-committee incident update. Not for
  incident-response runbooks, triage, containment or forensics: this structures
  the governance decision around an incident, not the response to it.
---

# Incident Materiality

A workspace for the one decision the disclosure regime genuinely creates: **is this incident
material, on what basis, who decided, and by when must we act** — with a record that a board,
a regulator and, if it comes to it, a court can read.

It is not a SIEM, a ticketing system or an IR runbook. It does not detect, triage or
remediate. It structures the governance decision around an incident and records it
defensibly.

**This is not legal advice.** A materiality determination is a legal judgment. This skill
structures and documents it; it does not make it. Involve counsel on the determination and on
any filing.

## The two halves, and they are deliberately unequal

**The judgment half records what a human decided.** Six factors, each with a written
rationale, a named assessor and a date. A determination with its own rationale and its
decider. A disclosure decision with its basis. Nothing here is computed.

**The clock half is deterministic, and is the only thing the engine claims to know.** Business
days for Item 1.05, clock hours for DORA, exact in both.

## The engine never emits a verdict

No scale, no weight, no threshold, no total. `analyze` reports *which* factors have been
assessed and which have not — completeness — and never how many came back `bearing`.

Three reasons, and the third is the one that matters:

1. **Materiality is a legal standard, not an arithmetic.** *TSC Industries v. Northway* does
   not decompose into weighted factors.
2. **A score invites the wrong defence.** *"The tool scored it 3.2, below our threshold"* is
   not a defensible position. *"Our General Counsel determined it not material on 14 July, on
   this recorded basis, having assessed these six factors"* is.
3. **A generated score is discoverable too.** A number that disagreed with the human
   determination — in either direction — becomes an exhibit arguing against your own
   conclusion.

## The clock starts at the determination, not the discovery

```
discovered 6 July  ──  determined material 14 July  ──  8-K due 20 July
                       ▲
                       the clock starts HERE
```

Item 1.05 gives four business days **after the registrant determines the incident is
material**. So an incident still under honest assessment shows `not-started` — no deadline,
nothing red.

That is not a loophole, and the tool does not let it read as one: the determination itself
must be made *without unreasonable delay*, and `analyze` reports the elapsed days since
discovery as an open item. What it will **not** do is call any number of days unreasonable.
The rule sets no number, and a tool that invented one would be manufacturing a standard and
then timing you against it.

## Workflow A — open an incident and work the factors

```bash
E=scripts/incident_analysis.py
python3 $E init incidents.inc --client "Acme" --owner CISO \
    --holiday 2026-07-03 --holiday 2026-09-07 --actor "you"

python3 $E open incidents.inc --title "Vendor payroll portal breach" \
    --discovered 2026-07-06 --regime sec-1.05 --actor "you"

python3 $E assess-factor incidents.inc --id I-001 --factor data --assessment unknown \
    --rationale "Exfiltration not confirmed as of 9 July; vendor forensics engaged." --actor "you"
python3 $E assess-factor incidents.inc --id I-001 --factor data --assessment bearing \
    --rationale "Forensics confirmed export of SSN and bank details for 1,940 employees." --actor "you"
```

`--rationale` is required. An assessment with no rationale is a ticked box, and a ticked box
is not a record of a judgment. **Re-assessing appends; the earlier entry stays** — that
sequence is the answer to *"when did you know?"*.

Work all six: `financial`, `operational`, `data`, `regulatory`, `reputational`,
`aggregation`. The last is the one most often missed and an explicit SEC concern — a series
of related occurrences may have to be assessed as one incident rather than five.

Supply `--holiday` dates. Without them a federal holiday counts as a business day and the
deadline lands one day early per holiday — the safe direction, and still wrong.

## Workflow B — determine, then run the clock

```bash
python3 $E determine incidents.inc --id I-001 --state material \
    --rationale "Export of SSN and bank details for 1,940 employees confirmed 13 July; expected costs exceed the policy retention." \
    --decider "General Counsel" --on 2026-07-14 --actor "you"

python3 $E set-disclosure incidents.inc --id I-001 --decision file \
    --basis "Determined material 2026-07-14; 8-K within the window." --actor "you"
python3 $E record-filing incidents.inc --id I-001 --window sec-1.05:8-K --at 2026-07-17 --actor "you"
```

`--rationale`, `--decider` and `--on` are all required. **Determinations are appended, never
overwritten** — a change from `not-material` to `material` is the most consequential fact in
the store, and an implementation that edited in place would destroy the record exactly where
it matters most.

### DORA, in clock hours

```bash
python3 $E set-anchor incidents.inc --id I-002 \
    --aware 2026-07-20T14:10:00+00:00 --classified 2026-07-20T17:40:00+00:00 --actor "you"
python3 $E record-filing incidents.inc --id I-002 --window dora:initial \
    --at 2026-07-20T20:05:00+00:00 --actor "you"
```

Anchors are **timestamps**, not dates: DORA counts hours where the SEC counts business days.
A bare date is refused rather than read as midnight — a deadline that looks exact and is
invented is worse than a visible gap, so a missing anchor reports `anchor-missing`.

`initial` is the **earlier** of classification + 4h and awareness + 24h. `intermediate` runs
72h from the initial notification actually filed, and `final` one month from the intermediate
— each anchored on the previous filing, so a missed initial produces no phantom deadline.

## A running clock outranks the determination

An incident can be determined **not material** for Item 1.05 and still owe a DORA report on a
live clock. *"Not material"* and *"no notification duty"* are different questions with
different tests. The band reports the clock, because that is the one of the two with a date
attached. The shipped example demonstrates it.

## Reporting

```bash
python3 $E analyze incidents.inc --today 2026-07-31 --now 2026-07-31T09:00:00+00:00 --out an.json
(cd renderers && python3 render_worksheet.py --in ../an.json --out ../worksheet.html)
(cd renderers && python3 render_board.py --in ../an.json \
    --translations ../incident.board.json --out ../board.html)
```

The **worksheet** is for the CISO, the disclosure committee and counsel: every factor with its
recorded reasoning, the full determination trail, the live windows, the disclosure decision.

The **board narrative** is for the audit committee, composed through `ciso-board-translation`.
Without `--translations`, every narrative slot renders a labelled placeholder — this page
never writes a sentence about an incident that nobody has written. The sidecar conforms to the
section contract: section `incident`, item key `incidents`.

Both carry, as blocks rather than footnotes: **not legal advice**, **no verdict is produced
here**, **when the window opens**, and — wherever an incident is linked to an accepted risk —
the **discoverability** caveat.

## Linking to an accepted risk

```bash
python3 $E link incidents.inc --id I-001 --risk R-006 --exception A-001 --actor "you"
```

*"The third-party risk we accepted in April is the one that materialised in July"* is exactly
the sentence a board needs and exactly the sentence opposing counsel would like to find. It is
kept, because a governance record that omits it is not a governance record — and the
discoverability caveat renders wherever it appears.

## Scope and honest limits

**SEC Item 1.05 and DORA only.** State breach-notice statutes, NIS2 and sectoral regimes are
recorded as notes on the `regulatory` factor with **no computed deadline**. The engine does
not compute a deadline it cannot compute correctly.

`references/disclosure-clocks.md` carries every limit with its receipt: Item 1.05 binds SEC
registrants and nobody else, expressly does not require technical detail, and sits under
rescission pressure with a materially reduced enforcement posture; DORA binds in-scope EU
financial entities, its *major* classification is a judgment this tool does not make, and the
engine does not apply the next-working-day allowance.

**This is a preparedness and defensibility tool, not a scare tactic.** The board-safety eval
fails the render if any board-facing view reads as fear framing.

## Reference

| File | What it covers |
|---|---|
| `references/schema.md` | the `.inc` store, append-only histories, bands, derived list |
| `references/materiality-factors.md` | the six factors, the aggregation rule, why there is no score, receipts and their limits |
| `references/disclosure-clocks.md` | Item 1.05 business-day math, DORA hour windows, clock states, every limit |

Verify the engine with `python3 scripts/incident_analysis.py self-test`, the clocks with
`evals/disclosure-clock.sh`, and the guardrails with `evals/board-safety.sh`.

---

*A Cyber Aware Creation · Not affiliated with NIST. Not legal advice.*
