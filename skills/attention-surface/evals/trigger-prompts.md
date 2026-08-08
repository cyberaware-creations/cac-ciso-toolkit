# Trigger routing checklist — `attention-surface`

Confirms the skill fires on **what needs attention now** — this week, what changed, what is
overdue, what is unowned — and stays quiet when the question belongs to the register that owns
the record or to the quarterly board artifact.

**Status: not yet run.** These twelve cases are written and shipped; no routing pass has been
scored against them. Recorded rather than left blank, because a checklist with an invented score
is worse than one admitting it has not been exercised.

Score it alongside `board-pack`'s cases when that happens. The interesting confusion for this
skill is T9 — a quarterly board pack and a weekly attention review read the same escalations,
and the only thing separating them is period and audience.

## How to run

```bash
claude plugin update cyber-aware-creations@cyber-aware-creations   # or the run scores a stale build
```

```bash
PROMPTS="$PWD/skills/attention-surface/evals/prompts.tsv" ./skills/nist-csf/evals/run-triggers.sh /tmp/att-trigger
```

## What each case is for

| id | expects | and specifically tests |
|---|---|---|
| T1 | `attention-surface` | the plainest opener; nothing else owns "this week" |
| T2 | `attention-surface` | urgency vocabulary, with no register named |
| T3 | `attention-surface` | the diff — the one thing needing state |
| T4 | `attention-surface` | cross-producer, which is the whole point. Must NOT go to a single register |
| T5 | `attention-surface` | the cadence, in the words a person uses for it |
| T6 | `attention-surface` | `brief`. Must not become task tracking |
| T7 | `attention-surface` | a cluster named in the user's own words |
| T8 | `attention-surface` | absence — a correct answer names the unread sources |
| T9 | **`board-pack`** | the boundary that matters most: same escalations, quarterly, board-facing |
| T10 | **`risk-register`** | creating a record belongs to the producer, never here |
| T11 | `attention-surface` | **the mute trap.** A correct answer refuses and names threshold tuning at the producer as the visible alternative |
| T12 | `attention-surface` | **the score trap.** A correct answer explains the ordering it does use and refuses to compute a priority |

T11 and T12 are the load-bearing pair. Both are reasonable requests, both are one line from
being implemented, and a correct answer to either declines and says what to do instead.
