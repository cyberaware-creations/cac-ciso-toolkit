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

## The manifest

```json
{
  "manifestVersion": 1,
  "client": "Northwind Financial",
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

`store` is optional and is used only to read that producer's headline figures. A store that
cannot be read costs you the figures and is named on the provenance page; it never stops a pack
from building.

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
