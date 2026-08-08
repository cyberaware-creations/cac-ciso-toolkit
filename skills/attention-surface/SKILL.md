---
name: attention-surface
description: >-
  Two jobs, and the second is the one people ask for in exactly those words: WHAT NEEDS THE CISO
  THIS WEEK, and WHAT CHANGED SINCE THE LAST REVIEW — including the last *security* review, the
  last Monday review, or last week. Both are derived from what every other skill already
  computes. "What changed" here means a diff over the ESCALATIONS the registers hold — new since
  the last recorded review, still open, and no longer firing — and NOT a diff of files, code, git
  history, a working directory or a session transcript, which is the wrong reading of the same
  words and answers a question nobody asked. **Use it even when no earlier review is recorded**:
  the first one is a baseline, and the page says so outright rather than reporting that nothing
  changed. What stopped firing is reported as *no longer firing*, never as *resolved* — the
  underlying record may simply have been edited, and this surface cannot tell those apart. Reads
  the escalations the seven producing skills emit — risk-register, metrics-register,
  exceptions-register, incident-materiality, vendor-register, ai-register and business-context —
  groups them by DECISION rather than by producer (clocks running out, something moved under us,
  nobody owns it, we disagree with ourselves, uncontrolled exposure, over tolerance), orders them
  deterministically, and shows what changed since the last review. Weekly and operational, where
  board-pack is quarterly and board-facing: same escalation contract, different period and
  audience. It OWNS NO DATA and computes no status — every fact comes from a producer's store and
  the producer is named on every item, which is what stops the list becoming a thirty-first
  opinion. There is no priority score: ordering is severity as the producer declared it, then age,
  then subject reference, and nothing is weighted or blended. There is no mute and no snooze — if
  volume is unusable the fix is threshold tuning at the producer, logged and visible. A producer
  whose store is missing is reported as NOT READ, never as clean, because a quiet list and an
  unread one must not look the same. An unmapped trigger surfaces in an explicit unclustered
  group rather than disappearing. Use when asked what needs attention this week, what is on fire,
  what changed since the last review or the last security review, what is new since last week,
  what moved under us, what came off the list, what is overdue across the whole programme, to run
  a weekly or Monday security review, to prepare a stand-up or one-to-one digest, or to see every
  escalation in one place. NOT for the quarterly board pack (board-pack), for creating or
  changing any escalation (the producer that computes it), for assigning or tracking tasks, or
  for scoring anything.
---

# attention-surface

**What needs the CISO this week.** A projection, not a register.

The suite emits thirty escalation triggers across seven producers. Every one is computed, dated,
evidenced and carries a subject reference — and until this skill there was nowhere to look at
them together on a working cadence.

`board-pack` consumes the same escalations for a **quarterly** artifact aimed at a **board**.
This consumes them **weekly**, for the **person who has to act**. Same input contract, different
period and audience, which is exactly why it is a second consumer rather than a feature of the
first.

## It owns no data

Every fact comes from a producer's store. This skill orders, groups, and shows what changed. It
computes no status, assigns no severity, and merges nothing — the same discipline `board-pack`
holds, and what stops an attention list becoming a thirty-first opinion.

| Not owned | Owner |
|---|---|
| An escalation's existence, severity or evidence | the producer that computes it |
| Any status, band, criticality or threshold | the producer |
| Merging two escalations about one record | nobody — `board-pack` flags without merging, and so does this |
| A priority score | **nobody. It does not exist.** |
| The quarterly board narrative | `board-pack` |
| Task assignment and tracking | out of scope, permanently — see `references/scope.md` |

## Three things make thirty items useful

### 1. Grouping by decision, not by producer

Nobody thinks *"show me vendor escalations."* They think *"what is overdue,"* *"what changed
under me,"* *"what is unowned."* Triggers cluster naturally across producers:

| Cluster | Means |
|---|---|
| **Clocks running out** | a period the organisation or a regulator set has passed |
| **Something moved under us** | a fact an earlier judgement rested on has changed — the ones nobody reports, because nothing failed |
| **Nobody owns it** | no name attached, or no answer to what this holds up |
| **We disagree with ourselves** | two records about the same thing say different things |
| **Uncontrolled exposure** | something is exposed and nothing is recorded against it |
| **Over tolerance** | past a line the organisation itself drew, and still there |

The mapping lives in `references/clusters.json` as **data**. A new trigger lands in a cluster by
declaration, and an unmapped one surfaces in an explicit `unclustered` group rather than
disappearing — a new producer must not be able to emit into silence. `evals/clusters.sh` asserts
every trigger the shipped producers can emit has a home, reading that list out of the producers'
own source rather than a hand-kept copy.

### 2. Ordering without a score

Three declared facts, compared as a tuple:

1. **severity**, exactly as the producer stated it — never re-derived here
2. **age since `since`**, oldest first
3. **subject reference**, so two alike items never swap places between runs

No weighting, no blending, no priority number. A weighted score would be this skill's own
opinion about what matters, and it is the one voice in the room with no register behind it.
`evals/no-priority-score.sh` holds the line behaviourally and statically, and CAC-GP-1 proves
both halves fail when the defect is present.

### 3. What changed since you last looked

The most useful thing, and the only one needing state.

The diff keys on **producer + trigger + subject**, deliberately not on the evidence string:
evidence carries counts and dates that move between runs, and keying on it would report
everything as new every week — the same as reporting nothing as new.

`gone` is reported as **no longer firing**, never as *resolved*. The trigger stopped; the
underlying record may have been fixed or may have changed. This surface cannot tell those apart,
and saying so is cheaper than being wrong.

## When somebody asks what changed since the last review

*"What changed since our last security review?"* is this skill's second job, and the phrasing
has a trap in it. **"What changed" has an obvious wrong reading** — a diff of the working
directory, the git history, or the session so far. Every one of those is a reasonable thing to
compute and none of them is a security review. What changed here is *which escalations the
registers are raising now that they were not raising then*, which is a fact about the
organisation rather than about a repository.

Answer it in this order:

1. **Run the review against the recorded baseline.** The diff keys on producer + trigger +
   subject, so an item is *new* because that combination was absent last time — not because its
   evidence string moved.

   ```bash
   python3 scripts/attention_surface.py review week.att --today 2026-08-07
   ```

2. **If no earlier review is recorded, say so and set the baseline.** The page prints it: *no
   earlier review is recorded, so nothing can be marked new.* An empty diff at that point means
   there is nothing to compare against, and reporting it as "nothing changed" would be a lie
   with a comforting shape. Record it with `--record --by "Name"` so the next one is a
   comparison.

3. **Read `gone` out loud as "no longer firing".** Never as fixed, closed or resolved. The three
   are different and only the producer knows which happened.

4. **Do not go looking for files.** If a source cannot be read the page already says NOT READ
   and names it. Searching the filesystem for a "last review" document answers a different
   question, and this skill holds the review events itself — `reviews` lists them.

## What it stores, and the one thing it must not

A `.att` file holding **review events**: when a review happened, who ran it, and the escalation
keys as they stood. Nothing else.

**No mute.** The exposure-lifecycle contract already decided this for escalation volume — if the
volume is unusable, the fix is threshold tuning at the producer, logged and visible, not a mute
field that is silent. That decision carries here, and it is the single most important guardrail
in this skill, because an attention surface is exactly where a mute feels most reasonable.

**No acknowledgement in v1** either, and that is a decision rather than an omission. *"I have
seen this and it is in hand"* is genuinely useful and one small step from silencing. The shape it
would have to take is recorded in the engine so whoever adds it inherits the constraints: an
acknowledgement **changes ordering and never visibility**, carries a named person, a date and a
note, and **expires**. An acknowledgement that never expires is a mute with better manners.

## Absence is visible

A producer whose store is missing, or whose analyze fails, is reported as **NOT READ** — never
as clean, and always above the first cluster. A short list must never leave a reader unsure
whether it is short because nothing fired or because nothing was read.

An escalation missing one of CAC-EL-1's six keys is carried as **malformed** and shown, not
dropped: a producer changing its contract is precisely the change worth knowing about.

`nist-csf` is **not** a source, and its absence is a statement. A gap against a Target is a
distance, not a clock — it emits no escalations, correctly, and listing it would produce a
source that is always silent, indistinguishable on this page from one that failed to load.

## Commands

```bash
python3 scripts/attention_surface.py init week.att --org "Acme Manufacturing"
python3 scripts/attention_surface.py add-source week.att --skill vendor-register \
    --store ../vendors.vnd
python3 scripts/attention_surface.py review week.att --context ctx.json
python3 scripts/attention_surface.py review week.att --record --by "D. Galleyne" --label "week 32"
python3 scripts/attention_surface.py review week.att --since "week 31"
python3 scripts/attention_surface.py brief week.att
python3 scripts/attention_surface.py reviews week.att
python3 scripts/attention_surface.py self-test
```

`brief` is a short digest shaped to paste into a channel or a one-to-one. That is deliberately
where the hand-off stops: turning an escalation into an owned, tracked task is a different
product, and it is where this becomes a ticketing system with a worse interface.

## What this will not do

- **No priority score.** Under an eval with two halves, registered under CAC-GP-1.
- **No mute, no snooze**, and no acknowledgement in v1.
- **No merging** of two escalations about one record — flagged, never combined.
- **No task tracking.** Permanently out of scope.
- **No board surface.** `board-pack` is the board surface, and a second would be the
  duplication this skill exists to avoid.

---

*A Cyber Aware Creation · Not affiliated with NIST. Not legal advice.*
