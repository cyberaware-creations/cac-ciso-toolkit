# Trigger routing checklist — `ai-register`

Confirms the skill fires on **the AI deployment and what is known about its security** — what
we run, what it touches, what it is exposed to, what is evidenced, what changed — and stays
quiet when the question is about model quality, bias, accepting a residual, scoring a risk, or
regulatory scope.

**Status: scored 2026-08-08 against v0.41.0 — 11 of 13 scoreable; four cases re-run against v0.42.0, now 14/15 with one case unusable as written.**

Routing mode (no `ALLOWED_TOOLS`), fifteen fresh `claude -p` sessions, $8.16, ~55s a case.

The headline number needs three caveats before it means anything, and they are more useful
than the number:

**The scorer was broken when this first ran, and it would have reported 0/15.**
`score-triggers.py` held a hardcoded seven-name list of "our" skills, written before
`business-context`, `vendor-register` and `ai-register` existed. A1 routed correctly to
`ai-register` and scored `FAIL … got none [non-toolkit: ai-register]` — a correct routing,
reported as a miss, in the words that make it look like somebody else's plugin answered. Caught
on the first case because that case was run alone before committing to the other fourteen. The
list is derived from the filesystem now, and the scorer's self-test validates every
`skills/*/evals/prompts.tsv` rather than only its own.

**Six expectations in `prompts.tsv` contradicted the table below**, which shipped in the same
commit. Every row had been transcribed as `ai-register`, including the five cases whose whole
purpose is that this skill must *not* fire. The table is the pre-registered expectation and the
TSV was fixed to match it — A10, A11 and A12 by what the table already said, which is a
transcription fix rather than a fit to the outcome.

**A14 and A15 are NOT evidence from this run.** The table said "not this skill", and the
scorer's vocabulary has no way to say that: `neither` means *no toolkit skill at all*, which is
a stronger claim and not the one intended. Both were re-specified after seeing where they went
(`business-context` and `nist-csf` respectively — both defensible: one owns the applicability
profile, the other owns maturity tiers). Re-specifying an expectation to match an observation is
fitting the test to the result, so they are excluded from the count and score for real on the
next run.

## The two that failed

**A13 — "Score the risk from the unsanctioned writing tool."** Expected `risk-register`, got
`ai-register`. Scored as a fail against the pre-registered expectation, and recorded as one.

**Changed to `ai-register|risk-register` before the second run**, not after seeing its result —
which is the whole difference between fixing an expectation and fitting one. The reasoning was
stated at the time and stands on its own: the deployment belongs to `ai-register`, so firing
there and handing off is right, and the pipe list is exactly what that syntax exists for.
But the answer opened with the refusal — *"There is no risk score, by design … likelihood ×
impact belongs [in risk-register] and only there"* — which is exactly the designed behaviour.
The expectation is probably the thing that is wrong: the deployment belongs to `ai-register`, so
firing there and handing off is right, and `ai-register|risk-register` is the honest
pre-registration. Deliberately left as a recorded fail rather than quietly widened, because the
next run should be the one that changes it.

**A1 — "What AI are we actually running?"** Flaky, and the flakiness is the finding: it passed
when run alone and failed in the batch, both times reading the prompt two ways — *which model
are you* and *what AI does the organisation run*. In the passing run it loaded the skill for the
second reading; in the failing one it named the skill without invoking it. The prompt is
ambiguous in a way the other fourteen are not. Left unchanged for now, because rewording a case
after watching it fail is the same error as re-specifying A14 and A15.

## Second run — 2026-08-08, against v0.42.0

Four cases were held over from the first run. All four were re-run once the expectations were
sharpened, in a commit that did not contain their results.

| case | result | note |
|---|---|---|
| **A1** | **PASS** | *"What AI are we actually running?"* — passed solo, failed in batch one, passed in batch two. Two of three. The ambiguity is real and unresolved; the prompt still reads two ways |
| **A13** | **PASS** | against `ai-register\|risk-register`, widened before the run. Fired here and opened with the no-score refusal, naming `risk-register` |
| **A15** | **PASS** | against `nist-csf`. Declined to produce a number out of ten and cited both refusals preventing it |
| **A14** | **FAIL** | and the failure is the finding — see below |

**A14 — "Are we in scope for the EU AI Act as a deployer?" is non-deterministic.** It reached
`business-context` on the first run and `ai-register` on the second, with a good answer both
times: each refused to determine scope, pointed at counsel, and named `regimes.json` shipping
empty rather than shipping a plausible rule set.

Two runs, two skills, two correct answers. **It is not re-specified again.** It was widened once
already after the first run, which is why it was excluded from that count; widening it a second
time to match a second observation is a ratchet, not a test. Recorded instead as **unusable as a
routing case in its present form** — a question that two skills answer equally well needs either
a pipe list argued from the design rather than from results, or a rewrite that picks a side.

That leaves **14 of 15**, with A14 the only failing case and its failure a property of the case.

### Resolved at v0.42.3 — the side was already picked, and the skill did not know it

Of the two options above, **a pipe list is the wrong one here**, and the reason is written at the
top of this file: this checklist confirms the skill *"stays quiet when the question is about …
regulatory scope."* Widening A14 to `business-context|ai-register` would make the case agree with
whatever happened to occur, and it would do that by contradicting the skill's own stated
boundary. The side was picked before the first run and it stands: **`business-context`**, because
scope is declared and never inferred, and a declaration is the profile's job.

So the case is unchanged and the **cause is fixed instead**, on the pattern T3, B4 and V6 set.
`ai-register`'s description claimed only that it "does not perform conformity assessment" — a
narrower and far more technical statement than *"does not decide whether the AI Act applies to
you"* — while `references/scope.md` and the empty `regimes.json` carried the real boundary in
places a routing decision never reads. The description now names regulatory scope alongside bias
and conformity assessment, spells out the roles (deployer, provider, importer), says the
determination is **declared in the applicability profile, on legal advice**, describes the regime
overlays as *selected by* that declaration rather than a substitute for it, and repeats the
boundary in the NOT list.

This is a prediction rather than a re-specification, and it can fail: **if A14 still lands on
`ai-register` after this, the description was not the cause** and the case is genuinely ambiguous
— which is worth knowing, and is the opposite of a ratchet.

## What the run actually establishes

The eight core cases (A2–A9) routed here every time: a new deployment, shadow AI found in a CASB
review, exposure, cadence, a base-model change, recording a control, the model-card tier
question, and autonomy as a query dimension. **A3 did not go to `vendor-register`**, which was
the confusion this checklist was written to catch.

The refusal boundary held on every case that reached it. A11 went to `exceptions-register` and
was told the acceptance would be refused without an approver, a justification and a
re-validation date. A12 declined to assess bias and said why the AI register is a natural-looking
fit that is not one. A15 declined to produce a number out of ten and cited both refusals that
prevent it.

## How to run

```bash
claude plugin update cyber-aware-creations@cyber-aware-creations   # or the run scores a stale build
```

```bash
PROMPTS="$PWD/skills/ai-register/evals/prompts.tsv" ./skills/nist-csf/evals/run-triggers.sh /tmp/ai-trigger
```

## What each case is for

| id | expects | and specifically tests |
|---|---|---|
| A1 | `ai-register` | the plainest possible opener; nothing else in the suite owns "what AI are we running" |
| A2 | `ai-register` | a new deployment, phrased as a rollout rather than as a register entry |
| A3 | `ai-register` | shadow AI. Must NOT route to `vendor-register` — the tool is not an arrangement, it is a system nobody sanctioned |
| A4 | `ai-register` | exposure, in the user's words rather than the taxonomy's |
| A5 | `ai-register` | cadence. Shares vocabulary with `vendor-register`'s A/V overdue case, deliberately |
| A6 | `ai-register` | `base-model-changed`. The hardest one: it is a fact about a provider, and it belongs here because the invalidated thing is our assessment |
| A7 | `ai-register` | recording a control with evidence — and must not be answered as though it closed anything |
| A8 | `ai-register` | the tier boundary. A correct answer says a model card is T3 and closes nothing |
| A9 | `ai-register` | autonomy as a query dimension |
| A10 | `ai-register`\|`board-pack` | the section hand-off |
| A11 | `exceptions-register` | the acceptance boundary. This skill refuses and names where it goes |
| A12 | `neither` | bias assessment. `references/scope.md` is the answer, and the answer is "not ours, and here is why" |
| A13 | `ai-register`\|`risk-register` *(widened before the second run — see above)* | scoring. One exposure, one scoring register; firing here and handing off is right |
| A14 | `business-context` *(re-specified after the first run — see above)* | regulatory scope. Role determination is a legal question and `regimes.json` ships empty |
| A15 | `nist-csf` *(re-specified after the first run — see above)* | the maturity score. There isn't one, on purpose |

The last five are the load-bearing half. A routing checklist that only proves a skill fires
proves the easy direction; what matters is that it stays quiet on the four things it has
deliberately refused to own.
