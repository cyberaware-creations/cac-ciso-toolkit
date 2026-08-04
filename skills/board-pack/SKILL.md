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
