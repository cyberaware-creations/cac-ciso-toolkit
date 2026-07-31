# Trigger routing checklist — `exceptions-register`

Confirms the skill fires on the **lifecycle of a decision already taken** — a risk knowingly
accepted, a control deviation approved — and stays quiet when the question is about a risk that
has not been accepted, an incident that actually happened, or how to phrase either for a board.

**Status: not yet run.** This set was written after Phase C, when a review found that
`exceptions-register` shipped in Phase B without one. That was the gap; this file closes it.

## How to run

```bash
claude plugin update cyber-aware-creations@cyber-aware-creations   # or the run scores a stale build

# routing mode — the comparable score
PROMPTS="$PWD/skills/exceptions-register/evals/prompts.tsv" \
  ./skills/nist-csf/evals/run-triggers.sh /tmp/xr-trigger

# reference mode — does references/exceptions.md earn its place?
ALLOWED_TOOLS="Read Glob Grep Skill" \
PROMPTS="$PWD/skills/exceptions-register/evals/prompts.tsv" \
  ./skills/nist-csf/evals/run-triggers.sh /tmp/xr-trigger-ref
```

**The two modes measure different things and their scores are not comparable.** Routing mode is
the default: every case runs in an empty directory and reads of this skill's own `references/`
are declined, so the model answers from `SKILL.md` alone. Reference mode grants those reads. See
`incident-materiality/evals/trigger-prompts.md` for what the distinction found there.

## The boundary this has to pin

**In scope — a decision already taken, and its lifecycle.** Log it, record who approved it and
why, re-validate it, close it, list what is overdue, produce the inventory.

**Out of scope — the decision itself.** Whether a risk is within appetite is `risk-register`'s
question and needs a scoring scale this skill deliberately does not own.

| case | goes to | not here, because |
|---|---|---|
| `Y1` score a risk against appetite | `risk-register` | the scale lives there; an acceptance register that scored would be a second, disagreeing scale |
| `Y2` risks past their review date | `risk-register` | **the sharpest case in the set** — this skill also has a review clock, so the noun decides: *risks* there, *acceptances* here |
| `Y3` is this incident material | `incident-materiality` | an incident is a thing that happened; an acceptance is a thing decided |
| `Y4` frame an acceptance for the board | `ciso-board-translation` | that skill's description already claims "framing a risk acceptance for the board", and a one-shot phrasing ask needs no store |
| `Y5` completeness against CSF Recover | `nist-csf` | framework coverage, not accepted risk |

`Y2` and `Y4` are the ones to watch. `Y2` because both skills genuinely have a re-validation
clock and only the noun separates them; `Y4` because the overlap is not accidental — it is
written into `ciso-board-translation`'s description on purpose, and this set exists partly to
confirm that phrasing asks still land there rather than being pulled into the register.

## The cases

| id | expects | prompt |
|---|---|---|
| X1 | `exceptions-register` | Log an exception for the finance team running without phishing-resistant MFA. |
| X2 | `exceptions-register` | Record that the CISO accepted the 40-day patch window on our internet-facing systems. |
| X3 | `exceptions-register` | Which of our risk acceptances are overdue for re-validation? |
| X4 | `exceptions-register` | We reviewed the MFA exception with the CFO and it still holds — record that. |
| X5 | `exceptions-register` | Produce the risk-acceptance inventory our DORA reviewer is asking for. |
| X6 | `exceptions-register` | What do we need on file for an accepted risk to be defensible? |
| X7 | `exceptions-register` | Our auditor wants a list of every control exception and what compensates for it. |
| X8 | `exceptions-register` | Close the vendor exception — we've migrated off that platform. |
| X9 | `exceptions-register` | Move the accepted risks out of our risk register and into the acceptance register. |
| X10 | `exceptions-register` | Is "users are reminded to choose strong passwords" a real compensating control? |
| Y1 | `risk-register` | Score our ransomware risk and tell me if it's within appetite. |
| Y2 | `risk-register` | Which of our risks are past their review date? |
| Y3 | `incident-materiality` | We had a breach at our payroll vendor last week. Is this material? |
| Y4 | `ciso-board-translation` | How should I frame this risk acceptance for the board? |
| Y5 | `nist-csf` | How complete are we against CSF Recover? |

## Beyond routing: what a reached run must not do

Read out of the transcripts by hand on the first run:

1. **`X1`, `X2` and `X4` must surface the refusal, not work around it.** The answer has to say
   that an approver, a justification and a re-validation date are required — and for `X1`, a
   compensating control. An answer that logs the exception with the fields it was given and
   fills the rest with a plausible default has defeated the whole skill.
2. **`X10` must not answer "yes".** "Users are reminded to choose strong passwords" restates the
   deviation; it reads as a control and functions as a sentence. The right answer names that,
   and offers the three honest options — fix the deviation, record it as an *acceptance* rather
   than dressing it as an exception, or escalate.
3. **`X5` and `X7` must carry the discoverability caveat**, and `X5` must not overstate DORA:
   RTS Art. 3(d) is real, satisfiable by free text, and exempts Art. 16 simplified-framework
   entities. An answer that implies a tool is required has sold something.
4. **`X9` must stay one-way.** `risk-register` feeds acceptances across; the lifecycle lives
   here, and nothing should suggest re-validating in the register.

## What the first run found

*To be filled in after the run.*

---

*A Cyber Aware Creation · Not affiliated with NIST. Not legal advice.*
