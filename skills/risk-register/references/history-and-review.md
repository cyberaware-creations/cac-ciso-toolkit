# History, Change Tracking & the Review Cycle

The register is a *living record*, not a one-time document. Its value compounds through change
tracking and a regular review ritual. This file covers how to maintain state, log change, and run a
risk review.

## Contents
- The maintain loop (load → change → log → write)
- What counts as a material change
- Capturing the "why"
- Trend and velocity
- The risk-review workflow
- Snapshots and quarter-over-quarter diffs

## The maintain loop

Every time you touch a register, follow the same discipline so the file stays the source of truth
and its history stays intact:

1. **Load** the `.rr` file.
2. **Apply** the change to the data.
3. **Append** a history event (never edit or delete existing events — the log is append-only).
4. **Write** the file back, refresh `updatedAt`, and stamp `schemaVersion: 2`.

If you skip step 3, the register silently loses its ability to report change — which is most of why
it exists. Treat "log the change" as part of making the change, not an optional extra.

## What counts as a material change

Append a history event for any of: a risk added, a likelihood/impact score moved, a response type
or plan changed, a status changed, a risk accepted / re-validated / closed / reopened / deleted, a
theme reassignment, an appetite or matrix-size change, and snapshot creation. Pure cosmetic edits
(fixing a typo, adding a note) don't need one.

## Capturing the "why"

For **material changes** — score moves, acceptances, closures, reopenings — capture a `rationale`.
Ask for it in-session ("what changed that lowered this residual?") and store it on the event. This
is what turns the log from a diff into an audit trail and a board narrative:

- The board asks "why did third-party risk drop?" → the rationale is the answer, already recorded.
- An auditor asks "on what basis was this risk accepted, and is it still valid?" → the acceptance
  rationale plus its re-validation date answer it (DORA RTS Art. 3(d), NYDFS §500).

Don't invent rationales. And don't record the change without one either — for material changes the
tooling will not let you. These refuse outright, before the file is touched, so a rejected mutation
leaves the register byte-identical:

| Command | Refuses without |
|---|---|
| `set-score` | `--why` |
| `set-text` | `--why` |
| `set-status` | `--why`, when closing a risk or reopening a closed one |
| `accept` | `--approver`, `--justification`, `--revalidate` |

So there is no "record it and mark the rationale missing" path for those. If the user can't say why
yet, the change doesn't land yet — ask, and apply it once they can. That is the point: a score move
or a closure with no stated basis is precisely the entry an auditor pulls on.

Everything else (`add`, `set-theme`) takes an optional `--why` and is logged either way.

## Trend and velocity

Both are derived from the log — never stored on the risk:

- **Velocity (per risk):** compare a risk's current residual exposure to its value at the last
  snapshot (or its previous score-changed event). Report direction: worsening ↑, improving ↓,
  steady →. Direction moves a board more than the absolute number.
- **Trend (register-wide):** from snapshots, plot over-appetite count and band mix over time. "Nine
  over-appetite risks last quarter, six now" is the headline a board remembers.

## The risk-review workflow

The connective ritual. When the user says "run my quarterly review," "let's review the register,"
or similar, work this checklist:

```
- [ ] 1. Load the register; report headline stats and trend since the last snapshot
- [ ] 2. Surface what needs attention:
        - risks past their reviewDate (stale)
        - risks over appetite (residual band worse than appetite)
        - acceptances past their revalidationDate (stale acceptances)
        - unowned risks; acceptances missing approver/justification
- [ ] 3. Walk each flagged item with the user; apply decisions, logging each with a rationale
- [ ] 4. Re-score (scripts/score_register.py) and re-check the flags
- [ ] 5. Create a named snapshot (e.g. "Q3 2026 Board Review")
- [ ] 6. Generate the deliverables: operational dashboard + executive board dashboard + board summary
        (invoke ciso-board-translation for the executive narrative)
- [ ] 7. Write the file back
```

Step 2 is the antidote to the single most common register failure — risks documented once and never
revisited. Leading with "here's what's stale, over-appetite, or due for re-validation" is what makes
the review worth having.

## Snapshots and quarter-over-quarter diffs

A snapshot freezes the register (settings + risks + computed summary) under a label at a review
checkpoint. To produce a "what changed since last review" delta, diff the current register against
the most recent snapshot:

- **Added / removed** risks since the snapshot.
- **Band moves** — risks whose residual band changed (with direction).
- **Newly over / newly within** appetite.
- **Status changes** — what moved into treatment, monitoring, or closed.

That delta, plus the rationales from the log, *is* the quarter-over-quarter board story — the
continuity a one-shot prompt structurally cannot produce.
