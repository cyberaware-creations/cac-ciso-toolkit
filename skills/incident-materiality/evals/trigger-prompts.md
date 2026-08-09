# Trigger routing checklist — `incident-materiality`

Confirms the skill fires on the **governance decision around an incident** and stays quiet on
the **response to one**. That is the whole boundary, and it is sharper here than in the other
skills because both sides of it contain the word "incident".

**Status: 15/15 routing mode** as of 2026-07-31 (plugin 0.9.0), on the first run, with no
description fix needed. $7.18, ~4 min wall clock.
**15/15 reference mode** as of 2026-07-31 (plugin 0.10.3), $8.12 — see
[what reference mode found](#what-reference-mode-found), which is the run that put the
disclosure clocks in front of a reader instead of merely shipping them.

## How to run

```bash
claude plugin update cyber-aware-creations@cyber-aware-creations   # or the run scores a stale build
PROMPTS="$PWD/skills/incident-materiality/evals/prompts.tsv" \
  ./skills/nist-csf/evals/run-triggers.sh /tmp/im-trigger          # all 15
PROMPTS=... ./skills/nist-csf/evals/run-triggers.sh /tmp/im-trigger N7 B1   # or named cases

# reference mode — do the clock references survive contact with a reader?
ALLOWED_TOOLS="Read Glob Grep Skill" MAX_TURNS=24 \
PROMPTS="$PWD/skills/incident-materiality/evals/prompts.tsv" \
  ./skills/nist-csf/evals/run-triggers.sh /tmp/im-trigger-ref
```

Routing-mode and reference-mode scores are **not comparable** and should not be averaged. They
answer different questions: routing mode asks whether the description wins the case, reference
mode asks whether the files behind it are usable. A skill can pass one and fail the other.

The harness lives under `nist-csf/evals/` and takes the case list as a `PROMPTS` parameter —
shared rather than copied, because a second skill's routing checklist is the same harness over
a different file and two copies of a hundred lines drift.

Every `claude -p` is a fresh session, and each case runs in its own empty working directory:
routing is decided before any file is read, and a warm session has already seen the skill.

## The boundary this has to pin

**In scope — the governance decision.** Is it material? Do we have to disclose? When does the
clock start and how much is left? Record the determination, the basis, the decider. Track the
DORA windows. Draft the audit-committee update.

**Out of scope — the response.** Runbooks, triage, containment, forensics, SOC playbooks. This
skill does not detect, triage or remediate, and a request that wants any of those should not
reach it. `B1` and `B2` exist to hold that line, and they expect `neither`: nothing this repo
ships is an IR runbook, and a skill that answered anyway would be claiming a competence it
does not have.

Three softer boundaries, one against each sibling that shares vocabulary:

| case | goes to | not here, because |
|---|---|---|
| `B3` log an MFA exception | `exceptions-register` | an approved deviation is a lifecycle record, not an incident |
| `B4` phrase "we had an incident" for a board | `ciso-board-translation` | a one-shot phrasing ask needs no state and no clock |
| `B5` score third-party breach risk | `risk-register` | a risk is a thing that might happen; an incident is one that did |

`B5` is the one worth watching. An incident often **realizes** a tracked risk, and the two
skills cross-link — but scoring a risk against appetite is `risk-register`'s job, and a
determination workspace that answered it would be doing arithmetic on a scale it does not
own.

## The cases

| id | expects | prompt |
|---|---|---|
| N1 | `incident-materiality` | We had a breach at our payroll vendor last week. Is this material? |
| N2 | `incident-materiality` | Do we have to file an 8-K for the vendor breach? |
| N3 | `incident-materiality` | When does the four-business-day clock start on this, and how much of it is left? |
| N4 | `incident-materiality` | Record that the GC determined the payroll breach material on 14 July, and the basis. |
| N5 | `incident-materiality` | Draft the audit-committee update on the payroll incident. |
| N6 | `incident-materiality` | Our EU subsidiary classified an outage as major under DORA — track the reporting windows. |
| N7 | `incident-materiality` | We've had three waves of credential stuffing from the same infrastructure. Do we have to assess them together? |
| N8 | `incident-materiality` | Which of our incidents are still waiting on a materiality determination? |
| N9 | `incident-materiality` | We decided not to disclose the outage. Record the decision and the basis for it. |
| N10 | `incident-materiality` | Walk me through the factors we should be assessing on this incident. |
| B1 | `neither` | Write me an incident response runbook for a ransomware outbreak. |
| B2 | `neither` | Our SIEM is alerting on lateral movement — what should the SOC do first? |
| B3 | `exceptions-register` | Log an exception for the finance team running without phishing-resistant MFA. |
| B4 | `ciso-board-translation` | How should I phrase "we had a security incident" for a board audience? |
| B5 | `risk-register` | Score our third-party breach risk and tell me if it's within appetite. |

## Beyond routing: what a reached run must not do

Routing is necessary and not sufficient. Two behaviours matter more than which skill fired,
and both are read out of the transcript by hand on the first run:

1. **No verdict.** On `N1` and `N7` the answer must structure the question — the factors, what
   would need to be established, who decides — and must not conclude that the incident is or
   is not material. An answer that says "this is likely material" has failed the case even if
   it routed perfectly.
2. **No invented deadline.** On `N2` and `N3` the answer must state that the window runs from
   the determination, not from discovery. An answer that counts four business days from the
   breach date has produced exactly the mistake this skill exists to prevent.

`N7` also has a content requirement: it must reach the **aggregation** factor and say that a
series of related occurrences may have to be assessed as one incident. That is the factor most
often missed, and a run that treats the third wave in isolation has missed it too.

## What the first run found

**15/15 on the first run**, which is not the norm — `metrics-register` needed a description fix
after scoring 13/15. Two reasons this one had an easier job, worth recording because they are
the reusable part:

- **The out-of-scope half is stated in the description, not implied.** "Not for
  incident-response runbooks, triage, containment or forensics" is the last sentence of the
  description, and `B1` and `B2` both correctly reached nothing.
- **The in-scope half enumerates the asks rather than the concepts.** "whether an incident is
  material, whether it has to be disclosed, when the 8-K clock starts or how much of it is
  left" are the sentences a user types. `metrics-register` lost `M8` at 0.7.0 by describing
  what the skill *is* rather than what gets asked of it.

### The behavioural checks, read out of the transcripts

All four passed, and two exceeded what the case required:

| case | requirement | what the run did |
|---|---|---|
| `N1` | no verdict | opened with *"I can't answer that, and — deliberately — neither will the tooling"*, named the *TSC Industries* standard, and gave the discoverable-exhibit reason |
| `N2` | no invented deadline | stated the clock starts at the determination, **and** added "that is not a way to stall" unprompted |
| `N3` | no invented deadline | reproduced the clock diagram from `SKILL.md`, then covered business days, the holiday direction-of-error, and both scope limits |
| `N7` | reaches aggregation | named it as "the factor most often skipped", then drew a distinction the reference does not make explicitly: **shared infrastructure is evidence, not the test** |

`N7`'s addition is the interesting one. It is correct, it is not in
`references/materiality-factors.md`, and it is worth folding back into that file — a reference
that says "name the related incidents and say why" is weaker than one that says what makes them
related.

### The harness gap this run exposed, and what closing it found

`N7`'s first transcript noted it could not open `references/materiality-factors.md` — reads
outside the empty working directory are declined under the harness's default permissions. That
is true of **every case in every skill's trigger set**: the shipped scores measure routing, and
the model answers from `SKILL.md` alone. For a routing test that is the right default.

It is the wrong default for asking whether the references earn their place, so `N7` was re-run
with `ALLOWED_TOOLS="Read Glob Grep Skill"` ($0.40). The result settles it:

- It read exactly one file — `references/materiality-factors.md` — and nothing else.
- It reproduced the aggregation signals close to verbatim, which is the reference doing its job.
- **It then derived a consequence the reference did not state:** aggregating the waves moves the
  *discovery* date back to wave one, which does not touch the four-business-day window (that
  still runs from the determination) but does change how *without unreasonable delay* reads.

That last point was a genuine omission and is now in `materiality-factors.md`. The reference
demonstrably improves the answer, so `run-triggers.sh` gained an optional `ALLOWED_TOOLS`
parameter — unset by default, so every previously recorded score stays comparable.

**Scores from the two modes are not comparable.** Record which mode a number came from.

## What reference mode found

**15/15, $8.12** (plugin 0.10.3, 2026-07-31) — the full set this time, not just `N7`.

All three references were opened across the set: `materiality-factors.md` by six cases,
`incident_analysis.py` by five, `disclosure-clocks.md` by two, `schema.md` by two. `N8` answered
from the description alone and read nothing, which is the right call for "which incidents are
waiting on a determination" — that is a store query, not a doctrine question.

### The clock answers were audited against the engine, not eyeballed

This is the skill where being wrong means a missed filing deadline, so the arithmetic was checked
rather than read.

`N3` built a ten-row table of determination dates against their 8-K deadlines **by hand**, because
the sandbox withheld Bash and it could not run the engine. All eleven rows it produced — including
the worked example from the reference — match `business_days_after()` exactly. It also identified
the two holidays bounding the window correctly (Independence Day observed Fri 3 July, Labor Day
Mon 7 September 2026).

More to the point, it *said* the arithmetic was unverified: "I calculated this table by hand — the
engine's `self-test` and its date math need a Bash approval I didn't get... I'd rather run it than
assert it." Right answer, correctly labelled as not-yet-checked.

`N6` reproduced the DORA windows exactly — initial at the earlier of classification + 4h or
awareness + 24h, intermediate at 72h from the initial *as filed*, final one month from the
intermediate *as filed* — and drew the consequence the reference implies without stating: **a late
classification buys no time**, because the 24h awareness cap binds regardless. It also separated
"major under DORA" from "material under Item 1.05" unprompted, which is the confusion the two
regimes invite.

> **Correction, v0.49.0 — that consequence is wrong in law, and the model got it from us.**
> Article 5(2) of RTS 2025/301 says a late classification *does* open a fresh window: where the
> entity has not classified within 24 hours of awareness, the notification is due four hours from
> classification and the lapsed cap no longer binds.
>
> The observation is left exactly as written, because it is an accurate record of what `N6` said —
> and it is now the most useful entry in this file. It shows the defect completing the circuit:
> the reference asserted a rule, the model reasoned *correctly from the reference*, and emitted a
> confident statement of law that was wrong. Nothing in a routing eval can catch that; the scoring
> would mark it right, because it matches the reference. Only reading the instrument catches it.
> Engine and reference both fixed in v0.49.0.

### The fix from the earlier `N7` re-run is load-bearing

`N7` reproduced *both* paragraphs that this checklist's previous entry added to
`materiality-factors.md`: "shared infrastructure is evidence, not the test", and the consequence
that aggregating moves the discovery date back to wave one while leaving the four-day window
alone. Neither was in the model's answer before those paragraphs existed; both are now.

That closes the loop a reference eval is for. The 2026-07-31 routing run could not have shown it,
because it never opened the file.

---

*A Cyber Aware Creation · Not affiliated with NIST. Not legal advice.*
