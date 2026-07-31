# Trigger routing checklist — `metrics-register`

Confirms the skill fires when a request needs **state** — a number compared against last
period — and stays quiet when `ciso-board-translation` should handle a one-shot ask.

**Status: 15/15 routing mode** as of 2026-07-31 (plugin 0.7.1), after one description fix, and
**15/15 reference mode** at plugin 0.9.3 — see "Reference mode" below.
The first run at 0.7.0 scored **13/15** and lost exactly the two cases flagged below as
the soft boundaries — see "What the first run found".

## How to run

```bash
claude plugin update cyber-aware-creations@cyber-aware-creations   # or the run scores a stale build
PROMPTS="$PWD/skills/metrics-register/evals/prompts.tsv" \
  ./skills/nist-csf/evals/run-triggers.sh /tmp/mx-trigger          # all 15, ~$7, ~4 min
PROMPTS=... ./skills/nist-csf/evals/run-triggers.sh /tmp/mx-trigger M8 T4   # or named cases
```

The harness lives under `nist-csf/evals/` and takes the case list as a `PROMPTS`
parameter. It is shared rather than copied: a second skill's routing checklist is the same
harness over a different file, and two copies of a hundred lines drift.

Every `claude -p` is a fresh session — a warm session has already seen the skill and biases
the result — and each case runs in its own empty working directory, because routing is
decided before any file is read.

## Reference mode — do `metrics-method.md` and `archetype-bridge.md` earn their place?

Run at plugin 0.9.3 with `ALLOWED_TOOLS="Read Glob Grep Skill"`, which grants the reads the
routing-mode default declines. **15/15**, $9.56 including the re-run described below.

Every reference file was opened by at least one case, which is the minimum bar and not a
foregone conclusion:

| file | cases that opened it |
|---|---|
| `references/schema.md` | M1, M2, M6, M7 |
| `references/archetype-bridge.md` | M1, M2, M8 |
| `references/metrics-method.md` | M1 |
| **`ciso-board-translation/references/metric-archetypes.md`** | **M8**, T1, T2, T4 |

The last row is the result worth having. `archetype-bridge.md` is deliberately a **pointer, not
a copy** — it maps each archetype to the canonical prose in `ciso-board-translation` rather than
duplicating it. `M8` followed that pointer across the skill boundary and read the canonical file.
The composition design is not just documented; it is exercised.

`M8` is also the case that failed at 0.7.0 by inventing a Mandiant benchmark. In reference mode
it invented nothing, resolved the direction correctly (dwell time is lower-better, 11 → 8 is a
27% reduction), and volunteered **survivorship bias** — a falling average that counts only the
incidents you found looks identical to getting worse at finding slow-burn intrusions. Then it
ended on a decision. Nothing in the references says "survivorship bias"; the reasoning came from
the direction and vanity-risk framing they do carry.

### The turn cap, which is a harness defect and not a skill defect

`M1` and `M2` first came back `error_max_turns` — routed correctly, **nothing produced to read**,
and scored as errors rather than passes. Reference mode spends turns: both had opened two
reference files before they began composing. The routing-mode default of 12 turns is not enough
for it.

`run-triggers.sh` now takes `MAX_TURNS` (default 12, unchanged). Re-run at 24, both pass:

```bash
ALLOWED_TOOLS="Read Glob Grep Skill" MAX_TURNS=24 PROMPTS=... ./run-triggers.sh /tmp/out M1 M2
```

Worth noting the harness caught this itself — it printed `re-run before quoting a total` rather
than folding two answerless runs into a green score. That guard exists because a run that made
its Skill call and then died was once reported as a pass.

## The boundary this has to pin

`metrics-register` and `ciso-board-translation` both fire on "a metric for the board", and
they are the pair most likely to cannibalise each other. The distinction is **state**:

- needs last quarter's value, or writes one down → **metrics-register**
- one number, in isolation, nothing stored → **ciso-board-translation**

A secondary boundary runs against `risk-register`: a KRI *linked to* a risk is still a
metric, and the register is not where its readings live.

## Cases

| id | expected | prompt |
|---|---|---|
| M1 | metrics-register | Start tracking our patch coverage so I can show the trend at each board meeting. |
| M2 | metrics-register | Add this quarter's numbers: phishing click rate 6.8%, dwell time 8 days. |
| M3 | metrics-register | Which of our metrics are breaching their thresholds? |
| M4 | metrics-register | Which numbers have we not refreshed since the last review? |
| M5 | metrics-register | Show me how MFA coverage has moved over the last three quarters. |
| M6 | metrics-register | Build the metrics section for the Q3 board pack. |
| M7 | metrics-register | Set a warning threshold of 90% on our patch SLA metric. |
| M8 | metrics-register | Our dwell time went from 11 days to 8 — is that good or bad? |
| T1 | ciso-board-translation | How should I phrase 87% patch coverage for the board? |
| T2 | ciso-board-translation | What's the trap in reporting a phishing click rate? |
| T3 | ciso-board-translation | Give me a board sentence for "we blocked 2 million attacks". |
| T4 | ciso-board-translation | What are the seven metric archetypes? |
| R1 | risk-register | Score our ransomware risk and tell me if it's within appetite. |
| R2 | risk-register | Which risks are past their review date? |
| C1 | nist-csf | How complete are we against CSF Recover? |

### Why the tricky ones are here

**M8** ("11 days to 8 — is that good or bad?") looks like a one-shot translation ask and is
not. It names two values in sequence, which is a comparison, and the answer depends on the
metric's direction — exactly what the register stores and the translation skill does not.
If this routes to `ciso-board-translation` the description boundary is too soft.

**T3** ("we blocked 2 million attacks") is the mirror image. It is a single number with no
prior and nothing to store, so it belongs to the translation skill even though this skill
has a vanity flag for precisely that shape of number. Owning a *concept* is not owning a
*request*.

**R2** ("risks past their review date") uses "past their date" language that this skill also
uses for stale readings. Different object, different store.

## Adding a case

One row here and one line in a `prompts.tsv` (`id · expected · prompt`). Keep the ratio of
negative cases high: a description that fires on everything scores well on positives alone
and is worse than useless in a plugin with four skills.

---

*A Cyber Aware Creation · Not affiliated with NIST.*

## What the first run found

Both failures were description defects, and both were on the boundaries this file predicted.

**T4 — "What are the seven board metric archetypes?" reached `metrics-register`.**
The description said *"Tags each metric to one of the seven board metric archetypes"*, and
that phrase was enough to match a pure-knowledge question about content this skill does not
own. Worse, the model answered by listing all seven **out of the description itself**,
without opening the file that actually defines them. Advertising a list you do not own is
how a skill cannibalises its neighbour. Reworded to *"carries an archetype tag it resolves
against ciso-board-translation at render time"*, with an explicit negative clause.

**M8 — "dwell time went from 11 days to 8, is that good or bad?" reached nothing at all.**
No skill fired; the model answered directly. It got the polarity right — and then **invented
a benchmark**, citing a Mandiant global median from memory to say 8 days was "at or slightly
ahead of typical". That is precisely the move every guardrail in this toolkit exists to
prevent, and it is the strongest argument for the case: left unrouted, the default behaviour
is the failure mode. The description now claims *"judge whether a move between two readings
is an improvement or a slip"* explicitly.

The fix was re-run on the two cases, then on **all fifteen**, because a two-case retry cannot
show that a sharpened description has not suppressed the thirteen that were already passing —
and the added negative clauses were exactly the kind of edit that could.
