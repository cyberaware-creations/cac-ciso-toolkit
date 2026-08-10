---
name: board-pack
description: >-
  Assemble the quarterly security board pack or audit-committee pack from the
  section objects the other skills produce, and output it as a print-ready
  document and an editable PowerPoint deck. Reads each producer's *.board.json
  against the versioned section contract, orders the sections for the audience,
  consolidates every section's decisions into one list the board actually votes
  on, reads each producer's own headline figures, and records on a provenance
  page what was missing. Owns no data and computes nothing: every fact comes
  from a producer's store and every sentence from ciso-board-translation, so a
  slot with no translation renders a visible placeholder rather than an invented
  line. Use when asked to build or assemble the board pack, put together the
  quarterly security deck or the audit-committee pack, produce the board
  deliverable for the quarter, or turn the registers and the profile into one
  narrative. NOT for a single section — translating one metric, running a risk
  review, or writing one board sentence belongs to the skill that owns it.
---

# Board Pack

The capstone. It turns five separate reports into **one story, one set of decisions, and one
deliverable** — and it is deliberately the thinnest skill in the toolkit.

## It owns no data, and computes nothing

Every fact in a pack already lives in a producer's store and has already been translated to
board language by `ciso-board-translation`. The assembler's job is the part no producer can do:
stitch, order, consolidate, and account for what was missing.

**If you are tempted to make it compute a count, a band or a trend, that logic belongs back in
the producing skill.** A figure the assembler derived would be a second number that could
disagree with the section printed above it, and the reader would have no way to tell which was
right. So the headline figures are *read*: each adapter runs the producer's own analysis and
lifts the number that producer calculated.

## Figures follow the same rule as facts

Each section carries chartable series as well as sentences, in a `charts` block. A figure is
read exactly the way a headline is: **every value comes from a field the producing skill
computed.** The assembler chooses which series is worth a board's attention and what kind of
mark suits it — a presentation judgement — and sums, counts and bands nothing.

Where a producer had no rollup to lift, the rollup was **added to that producer** rather than
computed here. That is why `exceptions-register` and `incident-materiality` now return
`counts.byBand`: a count derived in two places is a count that can disagree with itself.

Every figure names the analysis field it came from, and the pack prints it:

```
Open risks by residual band          summary.byBand
Subcategory coverage by CSF Function coverage.byFunction
Backup restores tested               metrics[M-006]
```

That turns "the pack computes nothing" from a claim in this file into something a reader can
check against the producer's own output.

Three kinds, and the colour contract decides the palette:

| kind | what it is | colour |
|---|---|---|
| `bar` | a categorical measure | MEASURE — never RAG, because no threshold was declared |
| `band-mix` | a population split by a band the producer declared | RAG, legitimately: the bands are declared, not inferred |
| `bullet` | one thresholded metric against its target | RAG, from the metric's own zones |

Two rules that stop a figure lying:

**A band-mix is a partition, and it says which population it split.** The exceptions mix sums
to the *active* records and the incident mix to the *open* incidents, so both name what they
left out — a chart summing to 3 beside a headline reading 4 makes a reader do arithmetic to
discover they were never the same population, and some of them will conclude one is wrong.

**Unassessed is not zero.** A CSF Function with nothing assessed reaches the page hatched and
labelled `not assessed`, never as a zero-length bar. Zero says it was measured and covers
nothing; a zero bar sitting in a row of long ones reads as the worst score on the chart rather
than as an absent one.

The document draws all three kinds. **The deck draws the band-mixes** as native shapes — a
rectangle is a rectangle in PowerPoint, Keynote and Google Slides, where an embedded SVG is
not — and leaves bullets and bars to the document, because both need an axis this writer would
only approximate, and half a chart in a deck is worse than a pointer to the page that has it.

## What escalated, and why that is not a decision

Sections raise things on their own. A risk crosses a band between snapshots, an acceptance
expires and stays on the register, a metric dwells over appetite for two quarters — nobody put
those on the agenda, and by the time somebody notices, the quarter is over.

The pack collects them into one list across every section, worst first:

```
CRITICAL  R-007  band-crossed        residual band high -> critical since the last snapshot
HIGH      R-003  appetite-dwell      over appetite continuously for 212 days, since 2025-12-31
HIGH      R-010  acceptance-lapsed   acceptance expired 2026-07-15 and is still on the register
MEDIUM    R-008  sustained-drift     residual exposure worsened across 2 consecutive snapshots
```

**This is the aggregation no single skill can do**, and it is the reason the contract
(`CAC-EL-1 §1.3`) fixes one record shape across the suite. Each line was derived by the skill
that owns that clock and is read here unchanged — the assembler raises none of them, exactly as
it computes no headline figure. `evals/assembly.sh` proves it the strong way: every record must
appear **verbatim** in the producer's own output, so an assembler that adjusted a severity on
the way through fails the suite.

**They are deliberately not in the decisions list.** A decision is board prose from
`ciso-board-translation`; an escalation is a fact a producer derived. Merging them would put a
machine-written sentence in the one place this pack promises every sentence came from a human
translator. So escalations get their own page, before the decisions — a board should see what
moved on its own before it sees what it is being asked to do about it.

Two consequences worth knowing:

- **Nothing is blocked.** A pack assembles and renders with escalations outstanding; none of
  them gates anything, and nothing is auto-rescored. Flag, never block.
- **An empty list is stated, not implied.** "Nothing escalated" is printed, because a pack with
  no escalations and a pack that could not read any are different states and only one is good
  news.

Four producers emit them, each owning a different clock and none knowing about the others:

| producer | `subjectKind` | what it is entitled to say has run out |
|---|---|---|
| `risk-register` | `risk` | a band crossed, appetite dwelt in, an acceptance marker lapsed |
| `metrics-register` | `metric` | a threshold breached, a reading sliding the wrong way |
| `exceptions-register` | `acceptance`, `exception` | the acceptance lifecycle it is the system of record for |
| `incident-materiality` | `incident` | a statutory disclosure clock — and nothing about materiality |

`nist-csf` emits none: a gap against a Target is a distance, not a clock, and nothing in a
Profile expires. That is *absent* rather than empty, and the distinction is why this is a
per-producer adapter — a skill that escalates nothing and a skill that cannot escalate yet are
different facts, and the provenance page says which.

### When two producers escalate the same record

`exceptions-register` owns the acceptance lifecycle and escalates `expired` on the
authoritative record. `risk-register` keeps its own lightweight `accepted` marker and escalates
`acceptance-lapsed` on that. One expiry can therefore reach a pack twice — and, because each
skill severities its own concern on its own terms, often at two severities:

```
2 escalations are linked to the same record R-010: exceptions A-001 (expired), risk R-010
(acceptance-lapsed). They were not merged — each was derived by the skill that owns that
clock — but they may be one fact reported twice. They also disagree on severity (critical,
high), so the same day reads as two different sizes of problem.
```

**Noticed, named, and both left standing** — the same answer this pack gives to two sections
asking for one decision. Merging would mean deciding which clock-owner was right, and that is
not the assembler's call to make.

With one difference in its favour. The duplicate-*decision* flag regexes ids out of free prose
and can only say the two *may* be one ask. Here the join is **declared**: `exceptions-register`
stamps `relatedRef` from `sourceRiskRef`, which `export-acceptances` sets and intake uses as its
idempotency key — so the identity is a fact, not a guess.

It is `sourceRiskRef` and deliberately **not** `riskIds`. One means *this record is the
acceptance of that risk*; the other means *this relates to that risk*. An acceptance linked to
R-003 and a dwell escalation on R-003 are two different facts about one risk, and joining them
would manufacture exactly the false positive the flag exists to avoid.

The severities are not comparable across producers by arithmetic, and the pack does not pretend
they are. It orders by the severity each producer **declared**, then by section, then by
subject. A `critical` from the incident workspace means a filing deadline passed; a `critical`
from the register means a band crossed. One list, four vocabularies, no translation layer
inventing a common scale.

## What it adds

| | |
|---|---|
| **One order** | fixed per audience, so two quarters can be compared side by side |
| **One through-line** | a synthesis only something seeing every section could write |
| **One decision list** | consolidated across sections, because boards act on decisions and scattering them buries them |
| **One honest account** | a provenance page naming every source, and everything that was absent |

## The workflow

```bash
A=scripts/assemble_pack.py

# 1. Check the manifest and every section against the contract.
python3 $A validate examples/pack.manifest.json

# 2. Get the material ciso-board-translation needs for the through-line.
python3 $A compose-brief examples/pack.manifest.json --out brief.json
#    Hand brief.json to the ciso-board-translation skill.
#    Save what it returns as the manifest's throughLine sidecar.

# 3. Assemble, then render both deliverables.
python3 $A assemble examples/pack.manifest.json --out pack.json
(cd renderers && python3 render_pack.py --in ../pack.json \
     --html ../board-pack.html --pptx ../board-pack.pptx)
```

The HTML carries `@page` rules — print it to PDF from any browser and it paginates A4 with a
break between sections. The `.pptx` opens as an editable deck.

### Two things the assembler will tell you, and neither is its to fix

**Snapshot the producer stores to one date before you assemble.** Each section is analysed
`--today` the manifest's `asOf`, but the *readings* inside each store are whatever was last
recorded there. Run every producer's own update to the same date first, or the pack reports a
risk register current to one week and a metrics register current to another. The assembler
notices and says so:

```
note: sections are dated differently (posture=2026-07-26, risk=2026-07-26,
metrics=2026-07-31, …); a pack that mixes snapshots is sometimes deliberate and
always worth seeing
```

It is a note and not a refusal because mixing snapshots is sometimes right — a quarterly
posture assessment beside monthly metrics is a real pack, not a mistake. What it must never
be is *accidental*, which is why it is printed rather than assumed.

**A decision flagged as naming the same record twice needs a human, not a merge.** Two
sections can each ask the board about `A-002` in different words. The assembler consolidates
decisions on *text* and never on meaning, so it surfaces the pair instead of picking one:

```
note: 2 separate decisions name A-002 (exceptions, incident). They were not merged —
the wording differs and this assembler never merges on meaning — but they may be one
ask arriving twice.
```

Read both, decide whether they are one ask or two, and edit the sidecars. A board asked the
same question twice in one pack will answer neither.

**An agenda can be wrong as a whole while every ask on it is right.** Above five decisions
pitched at the board — a convention this skill declares rather than a standard it cites, and
one you should overrule when your board's calendar says otherwise — the pack says so:

```
note: 10 decisions in this pack are pitched at the board (exceptions 2, incident 3,
metrics 1, pack 1, posture 1, risk 2), against the 5 a sitting can genuinely take.
Nothing was dropped and nothing was re-pitched: which asks are due this quarter is the
writer's call, and an ask held back is itself a decision worth minuting.
```

It counts, and it does not choose. Which asks are genuinely due needs the board's calendar,
what was deferred last quarter, and what the chair will table — none of which is in this pack
and all of which you have.

**It suggests no remedy, deliberately, because the obvious one is harmful.** Re-pitching an ask
from `board` to `management` makes the warning disappear and changes nothing about the
exposure. Do not do it to quiet the note. Holding an ask back is a decision in its own right,
and it belongs in the minutes rather than in an `altitude` field.

## The manifest

```json
{
  "manifestVersion": 1,
  "client": "Your Organisation",
  "period": "Q3 2026",
  "asOf": "2026-07-31",
  "audience": "board",
  "throughLine": "pack.board.json",
  "sections": [
    {"section": "posture", "store": "../../nist-csf/examples/example-profile.csfp",
     "translations": "../../nist-csf/references/example-translations.json"}
  ]
}
```

Paths resolve **relative to the manifest**, not the working directory, so a manifest committed
beside its sources keeps working from a Makefile, a CI job and a shell alike.

`asOf` is **not a label.** It is passed to every producer as `--today`, so it decides every age
band, clock state and overdue list in the pack. Changing it re-dates the analysis rather than the
cover, and a pack built with the wrong `asOf` is wrong in its figures, not just its heading.
`client` and `period` are the display-only pair — they reach the cover and the slide eyebrow and
nothing else. That is why the shipped example marks itself a specimen in those two fields and
leaves `asOf` alone.

`store` is optional and is used only to read that producer's headline figures. A store that
cannot be read costs you the figures and is named on the provenance page; it never stops a pack
from building.

### `context` — the applicability profile (CAC-AP-1)

```json
"context": "../../business-context/examples/example-org.biz"
```

Optional, and absent is the normal case: a pack without one assembles exactly as it did before,
against every producer's full question set — the safe direction, and what §2.2 requires.

Given one, the assembler exports the payload by running `business-context` itself — it never
reads the flags directly, because the narrowing decision belongs to that skill and §2.6 forbids
the import — and hands it to **every producer that declares it reads one.** A producer that does
not is never given the flag: it would exit on an unrecognised argument and the whole section
would drop off the pack, which is strictly worse than not narrowing.

Today that is **all seven** — `ai`, `exceptions`, `incident`, `metrics`, `posture`, `risk`,
`vendor` — and the provenance page says so in as many words:

> *the applicability profile narrowed every section in this pack (ai, exceptions, incident,
> metrics, posture, risk, vendor); none asked a question the profile had ruled out*

`board-pack` is not itself on that list, and never will be. It exports the profile and
distributes it; it owns no question set of its own to narrow, because it owns no data. Until a
producer implements the contract it is named in a second sentence — *"… `x` does not read one
yet and asked its full question set"* — so the list shrinks visibly as the suite catches up
rather than the note quietly disappearing when it empties.

A profile that quietly narrowed nothing would be indistinguishable from one that narrowed
everything, so the pack states which sections read it. It also records the **profile version**
it was assembled against (§2.5): a pack read a year later should say which perimeter the
questions inside it were asked against.

A profile that cannot be read or exported is a note on the provenance page, never a refusal.
The pack assembles un-narrowed, which is the full question set.

This is what stops the worksheet and the pack disagreeing. Before it, a `.biz` on disk narrowed
`incident-materiality`'s own worksheet and did nothing to the pack built from the same store,
so the two showed different clock rows for the same incident.

#### When the profile and the records disagree

A profile can declare a regime out of scope while a section's own records are tracked against
it anyway — a profile saying the entity is not listed, over incidents with an SEC clock open.
`incident-materiality` reports that rather than resolving it, and **keeps the clock**: §2.3 says
a profile narrows the default question set and does not overrule an assessor standing in front
of the evidence.

The pack carries every one of those reports onto **its own page before the through-line, a slide
before the through-line, and the provenance page.** It does not refuse and it does not choose a
side. Choosing would mean the pack overruling either the organisation's declaration or its own
incident record, and it is entitled to do neither — but a reader must not be able to reach the
executive summary without meeting the disagreement.

This was a real defect. The pack computed those conflicts, dropped them, printed *"the
applicability profile narrowed incident"*, showed Form 8-K three times, and never mentioned that
the profile declared the entity not listed. Every page was true; the document was not.

### `consolidation` — more than one organisation in one pack

```json
"consolidation": {
  "declaredBy": "D. Galleyne, CISO",
  "basis": "Contoso Freight is a wholly owned subsidiary, consolidated for group reporting"
}
```

**A pack assembled from stores belonging to different organisations is refused.** Every store in
this suite records the organisation it describes, and until v0.34.0 nothing compared them — so a
manifest could name one company on the cover and pull its sections from others. The shipped
specimen did exactly that across three fictional firms, and each page was correct about its own
source.

That is refused rather than warned about, which is the opposite of how this pack treats almost
everything else. The distinction is between a fact that is bad and a document that is not about
one thing: §1.2 flag-never-block protects *exposures*, and here there is no exposure to hide —
the pack simply cannot be trusted to be about the entity on its cover.

Names are compared leniently enough that `Acme Manufacturing Co.`, `ACME Manufacturing` and
`Acme Manufacturing (fictional)` are one company. `Group` and `Holdings` are **not** stripped:
they distinguish real entities, and this guard errs toward a refusal you can override rather
than a silent merge nobody sees.

A group pack is legitimate. A group pack assembled by accident is not, and the difference is a
human saying so by name — the same shape `exceptions-register` demands for an acceptance and
`business-context` demands for a flag. A consolidation without a `basis` is refused too: that is
the silent merge with an extra key. When it is accepted, the declaration is printed on the
provenance page, so a consolidated pack never looks like a single-entity one.

### `boundTo` — was this prose written against these numbers?

```json
"boundTo": {
  "storeUpdatedAt": "2026-07-26T20:00:33Z",
  "profileVersion": "FY26 close"
}
```

Optional, in any section sidecar. A pack pairs **live figures**, read from the store now,
with **prose** `ciso-board-translation` wrote at some earlier moment — and nothing tied the
two together. A register edited after its sidecar was written produced a pack whose sentences
described one state of the world and whose numbers described another, with the sidecar's
`asOf` (a reporting date, not a store version) still agreeing with the pack.

That is a quiet failure and a bad one to argue with later: the board was told a risk improved,
in a sentence a human wrote and signed, beside a figure showing it did not.

| Sidecar | Result |
|---|---|
| bound, and matching | silence — the ordinary case earns no words |
| bound, and the store has moved since | a **warning** naming both timestamps |
| bound to a different `profileVersion` | a warning: the perimeter moved, so the questions behind that prose are not the questions behind these figures |
| not bound | **one** note for the whole pack listing the unbound sections |

It is a warning and not a refusal because every sidecar ever written omits it, and because a
sidecar legitimately predating a trivial store edit is not a governance failure. And it is one
note rather than one per section for the same reason `fact-unattributed` was deferred in
`business-context`: five notes on every pack is how a provenance page teaches people to skim
it.

`boundTo` lives in the sidecar **envelope**, beside `asOf` and `contractVersion`. It carries no
sentence a board reads, and it is purely additive — the contract version did not move, because
bumping it would have refused every existing sidecar to gain nothing.

## Two type floors, because the deck is read at two distances

The seven section-narrative slides — band-mix included — are a **pre-read**: circulated before
the meeting and read at a desk. The decisions slides are **projected**, taken in from ten feet
while the CISO explains them aloud. One number cannot serve both, so there are two:

| slide class | read at | floor |
|---|---|---|
| section narrative, including band-mix | a desk, before the meeting | `NARRATIVE_TYPE_FLOOR` — ~11pt |
| decisions | ten feet, explained aloud | `DECISIONS_TYPE_FLOOR` — ~18pt |

**This is not a third `--deck-mode`.** Both classes ship in the same deck at two floors;
`--deck-mode full | board` is untouched. Two constants are cheaper than a mode, and the
evidence does not ask for more.

**The deck's own chrome is exempt from both** — the footer stamp, the page number, the lockup
and the rules. They identify the artifact rather than carrying an argument, and holding
furniture to a floor written for content would inflate the chrome to the size of the case.
They are named individually in `CHROME_EXEMPT` rather than pattern-matched, because *"it looks
like chrome"* is exactly the judgement that lets a real measurement slip out of the floor.

⚠️ **Declared, not yet enforced.** Raising the emitted sizes to meet these floors forces real
editorial cuts, and deciding what gets dropped per slide is a person's call. `deck-fit.sh` pins
the floors, their class mapping, the exemptions, and an inventory of every size the shipped
deck currently emits below the narrative floor — so nothing new slips under while the work to
raise them is outstanding.

## The board deck mode

```bash
python3 render_pack.py --in pack.json --pptx deck.pptx --deck-mode board
```

`full` is the default and is every slide in reading order. `board` targets a deck a board
actually sits through: the shipped specimen goes from **31 slides to 15 before the appendix**.

**It moves; it never drops.** The per-section item lists and the management actions are
relocated behind an appendix divider, and the five section dividers — pure navigation for a
deck that no longer runs long — stop being drawn. Every other slide is still in the file, and
`assembly.sh` proves it by diffing every text run of the two decks: the only thing the board
deck does not say is `Section N of 5`.

That distinction is the whole design. A board deck that silently omitted a section's detail
would be this skill inventing an editorial judgment about what a board needs to see, which is
what it refuses to do everywhere else — and unlike a placeholder, an omission leaves nothing
behind for anyone to notice. The appendix divider says what was moved and that nothing was cut.

The **HTML document is unchanged in both modes.** It is the record; the deck is the meeting.

## Client branding, and the part of the palette it cannot reach

A pack can carry a client's identity. Add a `brand` block to the manifest — inline, or a path
resolved beside it like every other manifest path — or pass `--brand client.brand.json`, which
overrides whatever the manifest says.

```json
{"ink": "#101820", "measure": "#7A3E9D", "measureTrack": "#E6DCEE",
 "patina": "#C0873A", "patinaText": "#8A5E1E", "bg": "#F7F4F0",
 "mark": "Northwind Group", "wordmark": "Northwind Group"}
```

Absent means CAC. Any key you leave out keeps its CAC value, so a block naming only `ink` is a
complete block.

**RAG is not overridable, and that is the feature.** Those four hexes carry measured contrast
and colour-vision separation — green↔red is ΔE 6.2 under deuteranopia, and each `text` variant
was darkened until it cleared 4.5:1. A client palette dropped into those slots would discard
every one of those measurements and still produce a chart that looked completely fine, which
is the worst way for this to fail. Status renders in toolkit colours; the client's identity
lives in the chrome around it. A block that names a RAG band is refused and says why.

What *is* overridable is checked rather than trusted, against the same floors the defaults were
built to, and refused as a list so you fix every problem in one pass instead of four:

```
refused: the brand override was refused:
  - ink: #AAAAAA on #FFFFFF is 2.32:1, needs 4.5:1 (body text on a mark surface)
  - ink: #AAAAAA on #F6F4EE is 2.11:1, needs 4.5:1 (body text on the workbench ground)
  - measure: #CCE0F5 on #FFFFFF is 1.35:1, needs 3.0:1 (a data mark against its surface)
  - measure: #CCE0F5 on #E6DCEE is 1.02:1, needs 3.0:1 (the filled part of a bar against its own track)
```

It is refused when the **manifest loads**, so `validate` catches it before anything is
assembled or rendered. A refused block leaves the previous brand exactly as it was — you never
get a half-applied hybrid.

`"whiteLabel": true` drops the maker's name from the footer and **keeps** `Not affiliated with
NIST`. Those two clauses sit side by side and are not the same kind of thing: one says who
built the pack, which a client is entitled to replace, and the other says the pack is not a
NIST product, which stays true no matter whose logo is on the cover.

## Audience decides the order, and nothing else

| audience | order |
|---|---|
| `board` | posture · risk · metrics · exceptions · incident |
| `audit-committee` | incident · exceptions · risk · posture · metrics |

Same content, same guardrails, same disclaimers. **An audit committee does not get a franker
version of the truth than the board.**

## Placeholder beats fabrication

A section with no sidecar, an unfilled through-line, an empty decision list — each renders a
marked, labelled placeholder in **both** the HTML and the PPTX, and appears on the provenance
page. Nothing is written to fill a hole.

`evals/board-safety.sh` proves it the strong way: every paragraph the pack presents as board
prose must appear **verbatim** in one of the sidecars it was built from. Not paraphrased, not
trimmed, not joined. A renderer that helpfully tidied a sentence would be writing board prose
with extra steps.

## Decisions merge on text, never on meaning

Two sections asking for the same thing in the same words become one entry naming both. Two
differently-worded asks stay two entries — the assembler cannot tell a real duplicate from two
asks that happen to rhyme, and collapsing them would delete a decision the board was supposed
to make.

What it does instead: **flags** two asks that name the same record, and leaves both standing.
The shipped example produces one, because the exceptions and incident sections both ask about
the same overdue acceptance.

## Not every ask is a board decision

A section can mark an ask `"altitude": "management"` — something management should simply do,
not something a board must decide. Those render in their own block, after the decisions, in
both the HTML and the deck. The shipped example carries thirteen asks: **ten decisions and
three management actions** (naming a control owner, approving assessment work, scheduling a
restore test).

Two rules make this safe:

- **The producer declares it; the assembler never infers it.** Only the skill that raised the
  ask knows whether it needs a board. Same rule as the vanity flag.
- **Unmarked stays in front of the board.** Absent is *unclassified*, not `management`. A
  board reading an ask it did not need costs a minute; a board decision filed away as a
  management action is a decision nobody takes.

See `references/section-contract.md`. It is not a `contractVersion` bump — the string form
still means what it always meant.

## The PPTX, and its honest limit

`scripts/pptx_writer.py` writes a real OOXML package from `zipfile` alone — no dependency,
which is the constraint the whole toolkit runs under. Every shape is positioned absolutely and
styled inline rather than inheriting from layout placeholders, because placeholder inheritance
is where fidelity across PowerPoint, Keynote and Google Slides diverges.

**What is verified:** the container opens, every part is well-formed XML, every relationship
resolves, every part carries the *correct* content type, and the slide list matches the slide
parts. **What is not:** how it renders. Open the example once in the application you care about
before a pack goes to a board.

Zip entries carry a fixed timestamp, so two runs over one pack are byte-identical — a deck that
differed only by its zip mtimes could not be diffed between quarters.

## Reference

| File | What it covers |
|---|---|
| `references/section-contract.md` | the canonical `*.board.json` envelope, per-section item keys, `contractVersion` |
| `references/pack-structure.md` | the order, the through-line rules, the merge rule, the audience variants |

Verify with `python3 scripts/assemble_pack.py self-test`, `evals/assembly.sh` and
`evals/board-safety.sh`.

---

*A Cyber Aware Creation · Not affiliated with NIST.*
