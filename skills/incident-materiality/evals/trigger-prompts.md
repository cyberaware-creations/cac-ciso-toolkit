# Trigger routing checklist — `incident-materiality`

Confirms the skill fires on the **governance decision around an incident** and stays quiet on
the **response to one**. That is the whole boundary, and it is sharper here than in the other
skills because both sides of it contain the word "incident".

**Status: not yet run at 0.9.0.** Filled in below after the first run.

## How to run

```bash
claude plugin update cyber-aware-creations@cyber-aware-creations   # or the run scores a stale build
PROMPTS="$PWD/skills/incident-materiality/evals/prompts.tsv" \
  ./skills/nist-csf/evals/run-triggers.sh /tmp/im-trigger          # all 15
PROMPTS=... ./skills/nist-csf/evals/run-triggers.sh /tmp/im-trigger N7 B1   # or named cases
```

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

*To be filled in after the run.*

---

*A Cyber Aware Creation · Not affiliated with NIST. Not legal advice.*
