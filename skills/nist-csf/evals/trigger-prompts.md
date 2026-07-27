# Trigger routing checklist — `nist-csf`

Confirms the skill fires when it should, stays quiet when `risk-register` should handle the request,
and resolves the genuinely ambiguous middle predictably.

**Why a checklist and not a harness.** `cac-ciso-toolkit` has no eval runner and `skill-creator` is
not available in it. Building a harness is worthwhile, but it is its own project and this skill
should not wait on it. This checklist is executable today by a human in a fresh session.

## How to run

Each prompt needs a **fresh session** — a warm one biases routing, because the model has already
seen the skill in context.

**Manually:** open a new session, paste the prompt verbatim, record which skill loads.

**Headless (faster):** every `claude -p` invocation is a fresh session.

```bash
cd /path/to/cac-ciso-toolkit          # run from the repo so the skill's scripts are reachable
claude -p "assess our NIST CSF posture" --output-format json > out.json
```

Measured cost: **~$0.42 and ~40s per prompt**, so the full 20 is roughly **$8.40 and 15 minutes**.

**Detection caveat, learned the hard way.** Grepping the `result` text for the skill name is
unreliable — in two runs of the same prompt, one named `nist-csf` explicitly and the other never did
despite plainly having used it (it reported `self-test 79/79` and talked in Profiles). Judge by
*behaviour*, not by name: `.csfp` / `profile_analysis.py` / Organizational Profile language means
`nist-csf`; `.rr` / `score_register.py` / likelihood × impact means `risk-register`. For reliable
machine detection use `--output-format stream-json` and look for `Skill` tool-use events rather than
parsing prose.

Any miss means tuning **both** skill descriptions together, never one alone: they partition one
space, and widening this one silently narrows the other.

Record the date and the plugin version each time this is run.

---

## Positive — must load `nist-csf`

| # | Prompt | Expected | Actual | Pass |
|---|---|---|---|---|
| P1 | "Assess our NIST CSF posture." | nist-csf | **nist-csf** (2 headless runs, 2026-07-26) | **✓** |
| P2 | "Where are our framework gaps?" | nist-csf | | |
| P3 | "Build a CSF target profile for us." | nist-csf | | |
| P4 | "I need a board view of our cybersecurity maturity against the framework." | nist-csf | | |
| P5 | "What CSF tier are we at?" | nist-csf | | |
| P6 | "How complete is our security programme against a recognised standard?" | nist-csf | | |
| P7 | "Track how our CSF coverage has moved since last quarter." | nist-csf | | |
| P8 | "We need a current profile and a target profile." | nist-csf | | |

P6 and P8 deliberately avoid the word "NIST" — the description must catch the concept, not the
brand.

## Negative — must load `risk-register`, not this skill

| # | Prompt | Expected | Actual | Pass |
|---|---|---|---|---|
| N1 | "Add a risk to the register." | risk-register | | |
| N2 | "What's our top risk over appetite?" | risk-register | | |
| N3 | "Score this risk: likelihood 4, impact 5." | risk-register | | |
| N4 | "Show me the heat map." | risk-register | | |
| N5 | "We accepted this risk — record who approved it." | risk-register | | |

N4 and N5 are the trap cases: both involve security posture reporting, and neither belongs here.

## Negative — must load neither

| # | Prompt | Expected | Actual | Pass |
|---|---|---|---|---|
| X1 | "Write us an acceptable use policy." | neither | | |
| X2 | "Track delivery risks for the ERP project." | neither | | |

## Ambiguous — the real test

These are legitimately unclear. The requirement is not that one specific skill wins, but that the
routing is **predictable and defensible**, and that whichever skill loads acknowledges the other
rather than silently doing half the job.

| # | Prompt | Defensible resolution | Actual | Pass |
|---|---|---|---|---|
| A1 | "We have a CSF assessment — what should we do with it?" | Either, if it asks which: track the framework position (nist-csf) or turn findings into scored risks (risk-register). SKILL.md's routing table covers this. | | |
| A2 | "Turn our gap assessment into risks." | `risk-register` (the verb is *become risks*). If nist-csf loads, it must point at `export-gaps` → `import-gaps`. | | |
| A3 | "How mature is our security programme?" | `nist-csf` — but it must **not** answer with a maturity score. Correct behaviour is coverage against Target plus a Tier characterization, with the guardrail stated. | | |
| A4 | "What should I show the board about our security posture?" | Either, plus `ciso-board-translation`. Both skills compose it; neither should hand-roll board prose. | | |
| A5 | "Are we compliant with NIST?" | `nist-csf`, and it must push back on the premise: CSF is not a compliance standard and there is no "compliant with CSF". Coverage against a self-set Target is the honest answer. | | |

A3 and A5 test whether the skill's guardrails survive contact with the way people actually ask.

---

## Result log

| Date | Plugin version | Positives | Negatives | Ambiguous | Notes |
|---|---|---|---|---|---|
| 2026-07-26 | 0.1.0 | 1/8 | 0/7 | 0/5 | Partial. P1 verified twice via headless probe; both runs routed to `nist-csf` and neither mentioned `risk-register`. Remaining 19 not yet run. |

## If something misroutes

- **A negative fires this skill** → the description is too broad. Tighten the closing exclusion, and
  check that `risk-register`'s "Not for … running a maturity assessment itself" still reads as the
  matching half.
- **A positive doesn't fire** → add the missing vocabulary. Users say "posture", "where we stand",
  "against the framework", and "maturity" far more than "Organizational Profile".
- **An ambiguous case answers without acknowledging the other skill** → that is a SKILL.md body
  problem, not a description problem. Fix the routing table.
