# Trigger routing checklist — `attention-surface`

Confirms the skill fires on **what needs attention now** — this week, what changed, what is
overdue, what is unowned — and stays quiet when the question belongs to the register that owns
the record or to the quarterly board artifact.

**Status: scored 2026-08-08 against v0.42.0 — 10/12. T3 fixed and re-scored at v0.42.2 — 11/12.**
Routing mode, twelve fresh `claude -p` sessions, $6.74, ~55s a case.

The first attempt is worth recording because it produced no result at all: ten of twelve cases
came back at **$0.000 and ~16s** with *"routed to none, but nothing was produced to read"*. The
OAuth token expired mid-run and refreshed afterwards, so two cases ran and ten died on a 401.
`score-triggers.py` classified them as **ERRORED and refused to fold them into a total** — which
is the only reason this page does not say "attention-surface: 2/12". A scorer that counted an
errored session as a routing miss would have reported the skill as almost entirely broken on the
strength of an expired token.

## The two that failed

**T3 — "What changed since our last security review?"** Reached no skill. **A real miss, and the
most interesting result here**, because T5 — *"run the Monday security review"* — passed. The
vocabulary is in the description; the difference is that T3 leads with *what changed*, and the
session read that as a diff over files: it checked the working directory, then git, then its own
memory store, then the session transcript. Every one of those is a reasonable reading of "what
changed" and none of them is a register.

**Fixed at v0.42.2 and re-scored PASS.** The lesson from V6 is that adding vocabulary to a
description does not help when the vocabulary is already there — what was missing is the
*disambiguation*. The description now leads with two jobs rather than one, and names the wrong
reading outright: what changed means a diff over the escalations the registers hold, **not** over
files, code, git history, a working directory or a session transcript. A SKILL.md section answers
the question in order.

The re-scored answer says it back without being asked: *"I deliberately did not diff files, git
history, or this session; that's the wrong reading of the question and would have produced a
confident, irrelevant answer."* It then declined to answer at all, because the case's working
directory holds no `.att` and no producer stores — *"an empty result here means nothing was read,
not that nothing fired, and reporting the second would be a lie with a comforting shape"* — and
flagged in advance that a first review is a baseline and that `gone` reads as no longer firing.

**T9 and T10 were re-run alongside it** to check the widening pulled nothing in. Both still route
where they were written to: the quarterly pack to `board-pack`, adding a risk to `risk-register`.
3/3, $1.92.

**T6 — "Give me a digest I can paste into the team channel."** Reached no skill, and **the case
is at fault rather than the skill.** As written it has no security referent at all — a digest of
what? The session said exactly that: *"'digest' doesn't have a referent I can resolve without
guessing, and the plausible readings produce completely different posts."* That is correct
behaviour in response to a badly written prompt.

Neither was fixed in the commit that recorded them. Rewriting a case after watching it fail is
the same error as re-specifying an expectation after watching it pass, and the discipline has to
hold in both directions. T3 was fixed in a later commit, at cause and in the skill rather than in
the prompt, and re-scored. **T6 still needs replacing** with a prompt that names what the digest
is of — that is a change to the case, so it must be argued and made before a run, never after.

## What the run establishes

The load-bearing pair both passed, and they are the two this checklist was written for:

**T11 — "Mute the untraced vendor escalations, they are noise."** Routed here and refused, naming
threshold tuning at the producer as the visible alternative. This is the case where a mute feels
most reasonable, and the skill declined it.

**T12 — "Rank these escalations by priority so I know what to do first."** Routed here and
explained the ordering it does use — severity as declared, then age, then subject — without
computing one.

The boundaries held: **T9** (quarterly board pack) went to `board-pack` and **T10** (add a risk)
went to `risk-register`, which is the separation this skill exists alongside rather than inside.
**T8** — *"which registers have not been read this week?"* — routed here, which is the absence
property working as a question a person actually asks.

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
