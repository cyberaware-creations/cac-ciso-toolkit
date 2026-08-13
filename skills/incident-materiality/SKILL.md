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
  sequence survives. Optionally reads an applicability profile from
  business-context, so Item 1.05 is asked only of a listed entity and the DORA
  windows only of a DORA-scoped one — with every narrowed question recorded on
  the page naming who declared it and when, and a declaration on the incident
  itself always outranking the organisation profile. Use when asked whether an incident is material, whether it
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

## What this skill is grounded in

The spine is **NIST CSF 2.0** (NIST CSWP 29), and every part of the record answers a named
Subcategory outcome rather than a house convention:

| Subcategory | the outcome, verbatim | what it grounds here |
| --- | --- | --- |
| `RS.AN-08` | *"An incident's magnitude is estimated and validated"* | the six-factor walk |
| `RS.AN-06` | *"Actions performed during an investigation are recorded, and the records' integrity and provenance are preserved"* | the append-only history |
| `RS.MA-02` | *"Incident reports are triaged and validated"* | the determination states |
| `RS.MA-03` | *"Incidents are categorized and prioritized"* | the incident band |
| `RS.CO-02` | *"Internal and external stakeholders are notified of incidents"* | the record that a notification happened |
| `RS.CO-03` | *"Information is shared with designated internal and external stakeholders"* | the disclosure decision |

**`RS.AN-08` is why there is no verdict.** *Estimated and validated* is a judgment somebody
reached and somebody else checked. NIST supplies no scale to reach it with and no threshold to
read it against, so neither does this engine — see [The engine never emits a
verdict](#the-engine-never-emits-a-verdict).

**`RS.CO-02` draws the line this skill is being moved to.** That stakeholders *were notified* is
a CSF outcome and belongs in the record. *When* a notification falls due is a different question
with a different source, and it is not what the Subcategory says. The principle is: record what
a human did, never compute what they must do.

⚠️ **This release does not yet keep that line, and says so rather than implying otherwise.** The
clock half below still computes Item 1.05 and DORA windows from statutory instruments. Those
computations are being removed — this section is the grounding that replaces them, landed first
and deliberately, so that the skill changes what it stands on rather than being left standing on
nothing. Until they are gone, treat every statutory window here as the deviation, not the model.

## The two halves, and they are deliberately unequal

**The judgment half records what a human decided.** Six factors, each with a written
rationale, a named assessor and a date. A determination with its own rationale and its
decider. A disclosure decision with its basis. Nothing here is computed.

**The clock half is deterministic, and is the only thing the engine claims to know.** Business
days for Item 1.05, clock hours for DORA, exact in both.

## The engine never emits a verdict

No scale, no weight, no threshold, no total. `analyze` reports *which* factors have been
assessed and which have not — completeness — and never how many came back `bearing`.

**The first reason is `RS.AN-08` itself.** It says an incident's magnitude is *estimated and
validated*; it does not say scored, and NIST attaches no scale and no threshold to it. There is
no number here to compute because the framework never supplies one.

Three more reasons, and the third is the one that matters:

1. **Materiality is a legal standard, not an arithmetic.** *TSC Indus., Inc. v. Northway, Inc.*,
   426 U.S. 438 (1976), does not decompose into weighted factors. Full citations, and the limit
   on citing *Basic*, are in `references/materiality-factors.md`.
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

## Workflow C — narrow the questions to the organisation (CAC-AP-1)

Two of this skill's question sets apply only to some organisations: **SEC Item 1.05** to a
registrant, and the **DORA report windows** to a DORA-scoped entity. `business-context` owns
that declaration; this skill reads it.

```bash
python3 ../business-context/scripts/business_context.py export context.biz > profile.json
python3 $E analyze incidents.inc --context profile.json --out analysis.json
```

**`--context` is optional and absent is the normal case.** Without it this engine behaves
exactly as it always has, byte for byte — the narrowing is additive and nothing about it
appears in an un-narrowed run.

**The subject outranks the profile.** An incident at a listed subsidiary of a private group
still gets the Item 1.05 battery, declared on the incident itself:

```bash
python3 $E declare-context incidents.inc --id I-003 --flag secItem105Scope --value true \
    --by "General Counsel" --on 2026-07-22 \
    --basis "The affected entity is the US subsidiary, itself an Exchange Act registrant."
```

`--by` and `--basis` are required, for the same reason `business-context` requires them: a
declaration that narrows what a disclosure record asks and cannot say why is worse than no
declaration, because absence asks everything. **`--value null` is not `false`** — it records
that the question was put to this incident and nobody could answer it, and it does not
override the organisation profile.

**Every narrowed battery is on the page**, with who declared it and when:

> *SEC Item 1.05 disclosure window — not assessed. Organisation profile:
> `secItem105Scope: false`, declared 2026-03-02 by General Counsel — no class registered under
> the Exchange Act and no s.15(d) obligation.*

A disclosure record that silently omits a question is worse than one that asks it: an auditor
cannot otherwise tell a battery that was correctly out of scope from one nobody got to.

**No perimeter declared means no deadline computed — and it says so.** Where nobody has
declared whether a regime reaches this organisation, the battery is asked in full and the
window renders as `scope not declared`, naming the flag that would settle it:

> *no window is computed: `secItem105Scope` is not declared, so whether this regime reaches
> this organisation has not been established. Declare it on the organisation profile, or on
> this incident with `declare-context`, and the window computes from the same anchor it always
> would. This is not a finding that the regime does not apply.*

This is decision AP-2, and both halves of it are deliberate. Computing would manufacture a
four-business-day Form 8-K deadline for an organisation that may owe no such filing, and a
manufactured legal date gets acted on. Dropping the row would leave a firm that has simply not
filled in its profile looking identical to one that is genuinely out of scope. So the window is
withheld, visibly — and where the incident is tracked against that regime anyway, it escalates
as `scope-undeclared`, so the attention survives the withholding.

**And that escalation carries a conditional date.** *If `sec-1.05` applies, the four-business-day
Item 1.05 window closes on — .* The clock field stays empty and nothing goes `overdue`; the
registrant still gets a date to work to. A conditional asserts nothing about whether the regime
applies, which is exactly why computing the clock is refused and stating the conditional is not.

**A disagreement is reported, never resolved.** An incident tracked against `sec-1.05` while
the profile says the organisation is not listed keeps its window and raises a conflict. The
profile keeps the default question set proportionate; it does not overrule an assessor who
opened a clock.

**The revenue base flows into the financial factor as a stated figure**, and nothing divides
by it. Item 1.05 sets no percentage, so a computed one would be this tool manufacturing the
standard the rule declines to set. It appears on the worksheet, where the judgment is made,
and never on the committee page, which circulates. Enforced by
`../business-context/evals/no-derived-materiality.sh`.

`determine --context profile.json` freezes the profile version and the batteries it did not
ask into the determination record (§2.5), so a reader a year later can tell which perimeter
the judgment was made against. The full contract is
`../business-context/references/applicability-contract.md`.

`initial` is the **earlier** of classification + 4h and awareness + 24h — **except** where
classification came more than 24h after awareness, when Art. 5(2) of RTS 2025/301 gives four
hours from classification and the lapsed awareness cap does not bind. `intermediate` runs
72h from the initial notification actually filed, and `final` one month from the intermediate
— each anchored on the previous filing, so a missed initial produces no phantom deadline.

## A running clock outranks the determination

An incident can be determined **not material** for Item 1.05 and still owe a DORA report on a
live clock. *"Not material"* and *"no notification duty"* are different questions with
different tests. The band reports the clock, because that is the one of the two with a date
attached. The shipped example demonstrates it.

## What this workspace raises without being asked

`analyze` carries escalations in the suite-wide `CAC-EL-1 §1.3` shape with
`subjectKind: "incident"`, so `board-pack` can put a missed 8-K window beside a crossed risk
band and a breached metric without knowing anything about any of the three clocks.

**This is the narrowest escalation set in the toolkit, and the narrowness is the design.** The
engine emits no verdict, so an escalation here may only ever report one of three facts about
the store: a deadline that passed, an anchor that is absent, or a record that moved.

| trigger | fires when | severity |
|---|---|---|
| `window-overdue` | a disclosure deadline passed with no filing recorded against it | `critical` |
| `anchor-missing` | tracked against DORA with no anchor timestamp, so no deadline can be computed at all | `high` |
| `determination-superseded` | a factor was recorded **after** a settled determination and changed its answer | `high` |

**`determination-superseded` never says the determination was wrong.** It says the record moved
after the determination was written, and the determination has not been revisited — a fact about
two dated entries, not a review of a legal judgment. Its severity deliberately **does not vary
with which way the factor moved**: ranking *"a factor turned `bearing` after a `not-material`
determination"* above the reverse would be this engine grading a judgment it exists not to make,
and a graded judgment is discoverable as an exhibit arguing against your own conclusion.

It compares the **recording** timestamps, never `determinedAt`. That date is back-datable by
design — it is the Item 1.05 anchor and often records a decision made before anyone typed it in
— so a determination written *after* a factor is not superseded by it, however it is dated.

### What deliberately does not escalate

- **Elapsed days with no determination.** Item 1.05 requires the determination *without
  unreasonable delay* and names no number of days. `analyze` reports the elapsed distance and
  declines to judge it. An escalation would *be* that judgment — manufacturing the standard the
  rule declines to set, then writing down the date you supposedly crossed it. That record would
  be discoverable too.
- **A window that is `due`.** Inside the window is on schedule. Due is the attention list;
  overdue is the escalation.
- **Unassessed factors.** Already reported as completeness. A gap in the worksheet is not a
  clock that ran out.
- **Anything counting `bearing` factors.** That is a score wearing different clothes.

Tune per store, and the block travels with it:

```json
"settings": { "escalation": { "windowOverdue": true, "anchorMissing": true,
                              "supersededDetermination": true } }
```

**Note what is missing: a number.** Every other register in the suite tunes an escalation with a
count or a window. The only quantities this one could tune are the ones the SEC and DORA already
set, and they are not this engine's to move.

Escalations are **derived on every run, never stored, never a history event** — and nothing here
blocks. An overdue window still renders, still exports, still counts.

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

`references/disclosure-clocks.md` carries every limit with its receipt, **in both directions**.

*Outward — who the rule does not reach.* Item 1.05 binds SEC registrants and nobody else, and
carves out technical detail of the *response, systems and vulnerabilities* but **not of the
incident**. DORA binds in-scope EU financial entities, its *major* classification is a judgment
this tool does not make, and the engine does not apply the next-working-day allowance.

*And the SEC's posture, dated and quoted verbatim from Reference Watch dossier RW-001 (F1, F3),
because an undated posture claim is the fastest-decaying sentence a compliance tool can carry:*

> In May 2025 five financial-industry trade associations petitioned the SEC to rescind Form 8-K
> Item 1.05 (File No. 4-856). As of 2026-08-08 the Commission has not acted on the petition: no
> proposal has been issued, the item does not appear on the SEC's regulatory agenda, and Items
> 1.05 and 106 remain in force unchanged.

> As of 2026-08-08 the SEC has announced no public-company cybersecurity-disclosure enforcement
> action since 2024-10-22, and dismissed the SolarWinds action with prejudice on 2025-11-20. The
> Commission has not stated a change of policy: the Cyber and Emerging Technologies Unit's stated
> scope still includes public-issuer cyber disclosure, and Items 1.05 and 106 remain in force.
> This is a change in observed enforcement activity, not in stated obligation.

*Inward — who inside the perimeter is excluded, delayed or unmodelled.* A limit that only scopes
outward tells an exempt organisation that a lawful gap is a failure, which is the defect BL-188
found in three NYDFS receipts. For Item 1.05: registrant status is declared as `secItem105Scope`
and never inferred, Item 1.05(c) and 1.05(d) are delay mechanisms the engine does not model, and
the Form 8-K path is the only one it models at all. For DORA: **Art. 2(3)** excludes six
categories from inside the financial-entity list — including IORPs with no more than 15 members
and SME insurance intermediaries — and **Art. 2(4)** lets a Member State exclude more. DORA's
**Art. 16** simplified framework disapplies *Articles 5 to 15* only and does **not** reach the
Chapter III reporting obligation, so it is not a limit on anything this skill computes.

**This is a preparedness and defensibility tool, not a scare tactic.** The board-safety eval
fails the render if any board-facing view reads as fear framing.

**`board-pack` passes the profile through.** Name a `.biz` as `context` in the pack manifest
and the assembler exports the payload and hands it to every producer that reads one — this
skill today — so the worksheet and the pack narrow identically rather than disagreeing about
which clocks exist for the same incident. The pack's provenance page names the profile version
it was assembled against (§2.5), and says which sections read it and which asked their full
question set.

## Rendering under a client brand

Every renderer takes `--brand FILE`:

```bash
python3 renderers/render_board.py analysis.json report.html --brand northwind.json
```

```json
{"ink": "#101820", "muted": "#5A4436", "patina": "#C0701F", "bg": "#FAF7F2",
 "measure": "#8A4B12", "measureTrack": "#EFE0D2", "patinaText": "#8A4B12",
 "wordmark": "Northwind Group", "mark": "Northwind", "whiteLabel": true}
```

**It is refused rather than approximated.** A palette that leaves body text on the dark band
below 4.5:1, or the patina kicker on the dark band below 4.5:1, is rejected with every failing pairing named — not
the first, and not silently nudged into range. `whiteLabel` drops the maker's name and keeps
the "Not affiliated with NIST" line, because one says who built the document and the other is
a statement about the world.

**What does not follow the brand, deliberately:** the RAG status ramp. Red/amber/green is a
contract with the reader about severity, not styling the client is buying. Only the shell —
ink, muted, background, patina, and the steps derived from them — moves.

## Reference

| File | What it covers |
|---|---|
| `references/schema.md` | the `.inc` store, append-only histories, bands, derived list |
| `references/materiality-factors.md` | the six factors, the aggregation rule, why there is no score, receipts and their limits |
| `references/disclosure-clocks.md` | Item 1.05 business-day math, DORA hour windows, clock states, every limit |
| `../business-context/references/applicability-contract.md` | CAC-AP-1, normative — what `--context` implements |

Verify the engine with `python3 scripts/incident_analysis.py self-test`, the clocks with
`evals/disclosure-clock.sh`, the guardrails with `evals/board-safety.sh`, and the
applicability contract with `evals/applicability.sh`.

---

*A Cyber Aware Creation · Not affiliated with NIST. Not legal advice.*
