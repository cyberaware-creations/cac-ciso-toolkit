# Trigger routing checklist — `ai-register`

Confirms the skill fires on **the AI deployment and what is known about its security** — what
we run, what it touches, what it is exposed to, what is evidenced, what changed — and stays
quiet when the question is about model quality, bias, accepting a residual, scoring a risk, or
regulatory scope.

**Status: not yet run.** These fifteen cases are written and shipped; no routing pass has been
scored against them. That is recorded rather than left blank, because a checklist with an
invented score is worse than one that admits it has not been exercised. Score it before relying
on it.

`vendor-register`'s checklist is in the same state, and the two should be scored together: the
most interesting confusions in this suite are between them (A6 and A8 both touch a provider),
and scoring one alone would miss them.

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
| A10 | `ai-register` → `board-pack` | the section hand-off |
| A11 | **`exceptions-register`** | the acceptance boundary. This skill refuses and names where it goes |
| A12 | **not this skill** | bias assessment. `references/scope.md` is the answer, and the answer is "not ours, and here is why" |
| A13 | **`risk-register`** | scoring. One exposure, one scoring register |
| A14 | **not this skill** | regulatory scope. Role determination is a legal question and `regimes.json` ships empty |
| A15 | **not this skill** | the maturity score. There isn't one, on purpose |

The last five are the load-bearing half. A routing checklist that only proves a skill fires
proves the easy direction; what matters is that it stays quiet on the four things it has
deliberately refused to own.
