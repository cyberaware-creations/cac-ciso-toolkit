# Pack structure — order, the through-line, and audience variants

The assembler owns no data. Every fact in a pack already lives in a producer's store and has
already been translated to board language by `ciso-board-translation`. What the assembler adds
is the part no producer can: **one order, one through-line, one consolidated list of
decisions.** This file defines all three.

If the assembler is ever tempted to *compute* a section's content, that logic belongs back in
the producing skill. See `section-contract.md` for the input contract it validates.

## The pack, in order

| # | Part | Source |
|---|---|---|
| 1 | Cover — client, period, audience, as-at | manifest |
| 2 | **Executive through-line** | `ciso-board-translation`, via the pack sidecar |
| 3 | **Decisions** — consolidated and deduplicated | every section's `decisions[]` |
| 4–8 | The sections, in audience order | each producer's `*.board.json` |
| 9 | Provenance — what was read, as at when, and what was missing | assembler |

### Decisions come before the detail, and that is a decision

A board acts on decisions. Scattering the asks across five sections buries them, and a pack
whose asks arrive after twenty pages of detail gets a board that has already stopped reading.
So the consolidated list sits at position 3, before any section.

The corollary is that the list has to be trustworthy: it is deduplicated, and every entry
keeps the section it came from, so a director who wants the basis for an ask can find it in
one step.

### Provenance is a page, not a footnote

The last page states which stores were read, each section's `asOf`, and — the load-bearing
part — **what was missing**. A section with no sidecar, an unfilled slot, a source that was
declared and could not be read: all of it named. A pack that quietly omits a section it could
not build is the failure mode this page exists to prevent.

## Section order by audience

Two audiences, each with a **fixed** order. Fixed matters: a pack whose section positions move
quarter to quarter forces every reader to re-navigate, and makes two quarters impossible to
compare side by side.

| audience | order | why |
|---|---|---|
| `board` | posture · risk · metrics · exceptions · incident | the frame first (where we stand), then what we are carrying, then how it is moving, then what we have knowingly accepted, then what happened |
| `audit-committee` | incident · exceptions · risk · posture · metrics | an audit committee's remit is controls, exceptions and incidents; that is what it convened to examine, so it leads |

An **incident** section is present only when an incident occurred in the period. Its absence is
normal and is recorded on the provenance page rather than left silent.

Everything else about the two variants is identical — same content, same guardrails, same
disclaimers. The audience changes the reading order, not the facts, and never the
disclaimers. An audit committee does not get a franker version of the truth than the board.

## The through-line

**One paragraph that reconciles the sections into one story with a direction.** Not a summary
of summaries: a synthesis only something seeing every section can write — *"the Recover gap,
the top residual risk, and the untested-backup metric are the same story."*

Three rules:

1. **It is composed through `ciso-board-translation`, never hand-rolled by the assembler.**
   The assembler feeds it the section summaries and the cross-section counts and consumes what
   comes back. One voice across every pack is the point.
2. **Absent means a visible placeholder.** A pack with no through-line renders a marked,
   labelled block saying so. It never renders a concatenation of the section summaries dressed
   up as a synthesis — that reads finished and is not, which is the worst of the three
   available outcomes.
3. **It carries a direction, not just a state.** "Improving, with one exception" is a
   through-line; "here is our posture" is a table of contents.

The pack sidecar is an ordinary section-contract document with `section: "pack"` — the one
section name the producers do not emit, because the assembler is its producer.

## Consolidating decisions

Deterministic, and specified here because a merge rule nobody can predict is a merge rule
nobody trusts:

1. **Collect** every `decisions[]` entry from every included section, in audience order.
2. **Deduplicate** on a normalised form — case-folded, whitespace-collapsed, trailing
   punctuation dropped. Two sections asking for the same thing in the same words become one
   entry that names both sections.
3. **Never merge on meaning.** Two differently-worded asks stay two entries. The assembler
   cannot tell a genuine duplicate from two asks that happen to rhyme, and silently collapsing
   them would delete a decision the board was supposed to make.
4. **Preserve order.** First appearance wins its position; a later duplicate only adds its
   section to the existing entry.

## Cross-section honesty checks

Surfaced on the provenance page, never smoothed over:

- **`asOf` drift** — sections dated differently in one pack. A warning, not an error: mixing a
  July posture with a June metric snapshot is sometimes deliberate and always worth seeing.
- **An empty section** — declared in the manifest, valid, and carrying nothing.
- **A missing sidecar** — the section renders placeholders and the provenance page says so.
- **An unreadable source** — named, with the error.

None of these stop a pack from assembling. All of them appear in the pack.

### The two that are not warnings

- **Different organisations in one pack** — the manifest cover, the applicability profile and
  each section's store are compared, and a pack whose sources belong to different organisations
  is **refused**. Override with an attributed `consolidation` block in the manifest; the
  declaration is then printed on the provenance page. This is the one integrity failure that
  cannot be a warning: a mixed-entity pack is not a pack with a bad fact in it, it is a document
  that is not about one company, and no page would show a reader that.
- **An applicability conflict** — a section whose records are tracked against a regime the
  profile declares out of scope. **Carried, never resolved**, and given its own page before the
  through-line and its own slide before the through-line, because a reader must meet it before
  the sentence they will remember. The pack takes no side: choosing one would mean overruling
  either the organisation's declaration or its own records.

## What the assembler will not do

- Compute a count, a band, a trend or a status. Those come from the producers.
- Write a sentence of board prose. That comes from `ciso-board-translation`.
- Fill a gap. A missing translation renders a placeholder, always.
- Merge two decisions that are not textually the same.
- Reorder sections to put good news first.

---

*A Cyber Aware Creation · Not affiliated with NIST.*
