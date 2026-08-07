# Trigger routing checklist — `business-context`

Confirms the skill fires on **the organisation's own facts, and what they make applicable** —
revenue base, crown jewels, the board's words, declared regulatory and technology scope — and
stays quiet when the question is about scoring a risk, judging an incident, phrasing a number
for a board, or any lifecycle another skill owns.

## The two routing traps

**Trap 1 — the applicability question looks like the consuming skill's question.**
`B6` ("which questions apply to us for an incident?") and `B7` ("does the AI battery apply to
this vendor?") are `business-context`, not `incident-materiality` or a vendor skill. The answer
comes from the profile, and `applies` is the command. `B10` is the genuine
`incident-materiality` case and must not be pulled here.

**Trap 2 — a business fact looks like the register that will consume it.**
`B3` (the CRM and the revenue that renews through it) and `B5` (the revenue base) are facts, not
scores. They belong here even though `risk-register` and `incident-materiality` are what
eventually read them. `B9` is the real `risk-register` case.

## Boundary cases in this set

| # | Prompt | Correct skill | Why it is easy to get wrong |
|---|---|---|---|
| B5 | revenue base for FY26 | `business-context` | Names materiality; the *fact* is still ours |
| B6 | which questions apply for an incident | `business-context` | Names incidents; the answer is the profile |
| B7 | vendor uses AI, we declared none | `business-context` | The §2.3 subject-override case, by design |
| B10 | is the breach material | `incident-materiality` | Also names materiality — this one is the judgment |
| B4 | the board's exact words on tolerance | `business-context` | Sounds like appetite, which `risk-register` owns |
| B9 | score and band our risks | `risk-register` | Appetite lives there; only the *quote* lives here |

## How to run

Route each prompt cold, with no prior context, and record the skill chosen. A prompt routed to
the skill that will eventually *consume* the fact is a failure, not a near miss: the fact never
gets recorded, and the consuming skill has nothing to cite.

**Status: not yet run.** Written with the skill rather than after it — `exceptions-register`
shipped without a checklist and had to have one retrofitted, which is the mistake this avoids.

---

*A Cyber Aware Creation · Not affiliated with NIST.*
