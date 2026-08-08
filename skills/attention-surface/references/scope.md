# What this skill does not own

A projection that grows opinions stops being a projection. This page names the boundaries and
says where each one comes from, so the line is defensible rather than asserted.

The short version: **it orders, groups and diffs what other skills computed.** Every fact on
every surface traces to a producer's store, and the producer is named on the item.

## Not any escalation's existence, severity or evidence

The producer computes it, dates it and evidences it. This surface reads the six keys CAC-EL-1
§1.3 fixes and changes none of them. Where an item is missing a key it is carried as
**malformed** and shown — a producer changing its contract is the change most worth knowing
about, and a projection that patched its input would be inventing facts.

**Whose it is:** the register that owns the record.

## Not a priority score

There is no number ordering the list, and there never will be. Ordering is severity as the
producer declared it, then age, then subject reference — three declared facts compared as a
tuple, which is not arithmetic.

Why not: a weighted blend would be **this skill's own opinion about what matters**, and it is
the only voice in the room with no register behind it. It would also be irreproducible and would
disagree with the four skills that already refuse to compute one. `evals/no-priority-score.sh`
holds both halves, registered under CAC-GP-1.

## Not a mute, and not (yet) an acknowledgement

The exposure-lifecycle contract already decided this: if escalation volume proves unusable, the
fix is threshold tuning at the producer — logged and visible — not a mute field, which is
silent. An attention surface is exactly where a mute feels most reasonable, which is exactly why
the rule has to be written down here.

Acknowledgement is the hard case, because *"I have seen this and it is in hand"* is genuinely
useful and one small step from silencing. If it is ever built it must: **change ordering and
never visibility**, carry a named person, a date and a note, and **expire**. An acknowledgement
that never expires is a mute with better manners.

Deferred to v2 on the same reasoning that kept `fact-unattributed` out of `business-context` v1:
the near-miss to a forbidden feature is best not built until real volume proves it is needed,
because the version built speculatively gets the constraints wrong.

## Not task assignment or tracking

No owner field, no due date, no state machine. `brief` emits a digest shaped to paste into
whatever the organisation already uses, and the hand-off stops there.

Why not: this is where an attention list becomes a ticketing system with a worse interface, and
the organisation already has one. **Permanently out of scope**, not deferred.

## Not merging

Two escalations about the same record from different producers stay two items. `board-pack`
already flags duplicate asks without merging them, and this does the same: which of two records
is the right one to act on is a human's call, and combining them would hide that a decision is
needed.

## Not the board narrative

`board-pack` is the board surface. Adding a second would be the duplication this skill exists to
avoid — it reads the same escalations for a different purpose, on a different cadence, for a
different reader.

## Not a source of its own escalations

It does not escalate its own staleness. A `review-overdue` on the reviewer is either elegant or
insufferable, and shipping it before anybody has used the weekly cadence in anger would be
guessing which. **No self-escalation in v1.**

## What was considered and rejected

- **A priority score.** See above.
- **A mute or snooze.** See above.
- **`nist-csf` as a source.** It emits no escalations, correctly — a gap against a Target is a
  distance, not a clock. Listing it would produce a source that is always silent, and on this
  page that is indistinguishable from one that failed to load. `add-source` refuses it by name,
  with that reason.
- **Reading producer stores directly instead of their `analyze --json`.** Rejected: it would
  make this skill know seven store formats, and the escalation shape is already standardised by
  CAC-EL-1. The contract existed; it just was not named as a transport.
- **An `export-escalations` command on each producer.** Cleaner in the abstract and touches
  seven skills to gain nothing that `analyze --json` does not already give.
- **Keying the diff on evidence text.** Rejected: evidence carries counts and dates that move
  between runs, so everything would read as new every week — the same as nothing reading as new.

---

*A Cyber Aware Creation · Not affiliated with NIST. Not legal advice.*
