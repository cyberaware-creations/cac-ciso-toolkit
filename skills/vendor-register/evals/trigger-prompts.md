# Trigger routing checklist — `vendor-register`

Confirms the skill fires on **the arrangement and what is known about it** — who we depend on,
how critical that dependency is, what the agreement commits them to, whether we could leave —
and stays quiet when the question is about scoring, accepting, disclosing or phrasing.

**Status: scored 2026-08-08 against v0.41.0 — 13/15.** Routing mode (no `ALLOWED_TOOLS`),
fifteen fresh `claude -p` sessions, $8.27, ~50s a case.

All ten `V` cases were written to reach this skill and nine did. All five `Y` cases were written
to reach a *different* skill, and four did — `exceptions-register`, `incident-materiality`,
`ciso-board-translation` and `nist-csf` each took the case written for it. That second half is
the load-bearing one: a checklist that only proves a skill fires proves the easy direction.

Scored with `score-triggers.py` **after** fixing a defect in it that would have invalidated this
run entirely — its list of "our" skills was hardcoded and predated this skill, so every correct
routing here would have scored as `none` with `vendor-register` reported as somebody else's
plugin. See `skills/ai-register/evals/trigger-prompts.md` for the detail.

## The two that failed

**V6 — "Does our MSA with Fabrikam actually commit them to a breach notification window?"**
Expected `vendor-register`, got no skill at all. **This is a real miss and the most useful
result in the run.** It is almost word-for-word the `contract-terms.incident-notice` question
this skill generates, and the skill is exactly what turns "I can't read the contract" into "here
is the question to send, and here is the clause to look for". Instead the session searched Drive
and Dropbox for the file, was blocked, and declined to guess — sound behaviour, wrong route. The
answer even reasoned about typical notification windows unaided, which is the freelancing the
skill exists to replace. Worth a `description` change: the current one leads on *recording* an
arrangement, and this prompt is about *interrogating* one already recorded.

**Y1 — "Give me a risk score for our hosting provider and tell me if it is within appetite."**
Expected `risk-register`, got `vendor-register`. Scored as a fail and recorded as one, but the
expectation is arguably the thing that is wrong: the answer refused the number and explained
that this register emits none by design, which is precisely what should happen. "Within
appetite" is `risk-register` vocabulary and the provider is `vendor-register`'s subject, so the
honest pre-registration is `vendor-register|risk-register`. Left as a recorded fail rather than
quietly widened — the next run is where that changes.

## What the run establishes

Adding an arrangement, tracing criticality, finding what is overdue, recording an exercised
exit, logging a subprocessor, and the questions-still-open path all reached this skill. Nothing
in the `V` set leaked into `ai-register`, and nothing in the `A` set leaked here — the two
registers share vocabulary and this was the confusion both checklists were written to catch.

## How to run

```bash
claude plugin update cyber-aware-creations@cyber-aware-creations   # or the run scores a stale build
```

```bash
PROMPTS="$PWD/skills/vendor-register/evals/prompts.tsv" ./skills/nist-csf/evals/run-triggers.sh /tmp/vr-trigger
```

```bash
ALLOWED_TOOLS="Read Glob Grep Skill" PROMPTS="$PWD/skills/vendor-register/evals/prompts.tsv" ./skills/nist-csf/evals/run-triggers.sh /tmp/vr-trigger-ref
```

**The two modes measure different things and their scores are not comparable.** Routing mode is
the default: every case runs in an empty directory and reads of this skill's own `references/`
are declined, so the model answers from `SKILL.md` alone. Reference mode grants those reads.

## The cases, and what each is for

### Positives — `V1`–`V10`

| | Tests |
|---|---|
| `V1` | The plain case: record an arrangement |
| `V2` | Criticality asked about an **arrangement**, not a company |
| `V3` | Cadence — which suppliers are overdue |
| `V4` | Exit strategy **exercised**, not written. The distinction the register exists to keep |
| `V5` | Subprocessor / fourth-party change |
| `V6` | What the executed agreement actually commits them to (`GV.SC-05`) |
| `V7` | **`untraced`** asked in a user's own words, without the word itself |
| `V8` | The board section |
| `V9` | Retirement — data return and confirmed deletion (`GV.SC-10`) |
| `V10` | **Contract-centric vs vendor-centric.** One provider, several arrangements, different levels — the shape a vendor-keyed register gets wrong |

### Negatives — `Y1`–`Y5`

These matter more than the positives, because they are the four places this skill is most
likely to over-claim.

**`Y1` is the load-bearing case.** *"Give me a risk score for our hosting provider and tell me
if it is within appetite."* Every commercial third-party tool answers this with a vendor score.
This suite's answer is `risk-register`: findings are scored once, there, under L×I with an
appetite to judge them against. If `vendor-register` takes `Y1`, the guardrail that
`no-vendor-score.sh` enforces in code has failed at the routing layer instead — the eval proves
nothing *computes* a score, and `Y1` proves nothing *offers* to.

| | Belongs to | Because |
|---|---|---|
| `Y1` | `risk-register` | Scoring and appetite are owned there. See above |
| `Y2` | `exceptions-register` | Accepting an exposure is a lifecycle this skill refers to and never records |
| `Y3` | `incident-materiality` | A vendor breach is still a materiality judgement, made with counsel |
| `Y4` | `ciso-board-translation` | Phrasing for a board is owned there; this skill never hand-writes board language |
| `Y5` | `nist-csf` | `GV.SC` **coverage** is a Profile rating. This skill cross-links to Subcategories and never rates them |

`Y5` is the subtle one. `vendor-register` is built on `GV.SC` and names those Subcategories
throughout, so a question about the supply-chain *category* reads like its territory. It is not:
"how well do we score against `GV.SC`" is a Profile question, and answering it here would be the
skill rating controls it does not own.

## What a failure means

A positive routed elsewhere is usually a `SKILL.md` description gap. A **negative** captured by
this skill is more serious — it means the description is claiming ownership of something another
skill is the system of record for, and the fix belongs in the `description`, not in a prompt.

---

*A Cyber Aware Creation · Not affiliated with NIST.*
