# Positive risk — `GV.RM-07`, and the rule that keeps it honest

## The Subcategory

CSF 2.0, Govern function, Risk Management Strategy category, verbatim from the bundled Core
(`nist-csf/references/nist-csf-2.0-core.json`):

> **`GV.RM-07`** — Strategic opportunities (i.e., positive risks) are characterized and are
> included in organizational cybersecurity risk discussions

NIST's term is **positive risk**, and that is the term this suite uses. It is better than
"upside" or "enablement" because it keeps the concept inside risk language instead of importing
sales language, which is the failure mode the whole element has to be designed against.

NIST IR 8286C r1 (December 2025) tracks opportunity **alongside** threats: *"The IR 8286 series
stresses the importance of recording and acting upon positive risk."* Its examples are concrete
rather than aspirational — machine-learning technology that significantly increases the
throughput of the enterprise research team, high-availability services that lift availability
from 93.4 % to 99.1 % and market share by 3 %.

**Do not quote 8286C r1 as calling for "a balanced approach" to all uncertainty.** That phrase
sits in the document's closing observation that managing positive risk *"is a field of interest
that is new to many readers and merits further exploration"* — and that the topic itself is an
opportunity **for the risk community** to create *"a more balanced approach to considering,
measuring, and managing the uncertainty of all types of risk in pursuit of the enterprise
mission."* That is an aspiration for the field, not a description of what the standard does.

An earlier version of this file quoted that sentence as the latter, dated the document February
2025, and dropped two words from the quotation. All three were caught by reading the source
instead of the note about the source. This file exists to stop the suite claiming more of a
reference than the reference says; it does not get an exemption.

## The grounding rule — the whole point

**An opportunity entry must cite a declared strategic goal or crown-jewel dependency from
`business-context`. No citation, no entry. Refused, not warned.**

Refused at the assembler (`validate_opportunities`), not only discouraged here, because a rule
that lives only in guidance is the rule this repo keeps having to convert into a check.

This is what separates positive risk from marketing copy on a board page:

| Refused | Accepted |
|---|---|
| *"Better security helps the business move faster."* | *"A tested exit on the plant historian is what makes the renewal negotiable."* — `cites: goal:...` |

The first is unfalsifiable. Nobody can check it, nobody can act on it, and a director who has
read three of them stops reading the section. This skill already says that overclaiming a
regulatory obligation destroys credibility faster than saying nothing; the same is true here,
and for the same reason.

The second is a claim with a source, and the source is a fact somebody in the business declared
and attached their name to.

**Why this was correct to omit until now.** Until `business-context` shipped there was nothing
in the toolkit for an upside claim to cite, so silence was the right answer. `business-context`
now holds declared strategic goals, crown jewels and what each one enables. The constraint that
made silence correct has been removed — which is the only reason this element exists.

## Separate, never blended

An opportunity is its own array, rendered as its own block, and is **never a clause appended to
a risk sentence.**

`GV.RM-07` says positive risks are *"included in"* cybersecurity risk discussions; 8286C r1
tracks opportunity *"alongside"* threats. Both describe a distinct item.

A risk sentence with an optimistic tail — *"…and this also unlocks faster onboarding"* — reads
as **softening the risk**. That is worse than either element on its own, and it is how a board
learns to discount the whole section. `outcome-framing.sh` fails a sidecar that does it, naming
the sentence and the word.

## Absent is not a finding

With no `--context`, or no declared goals, a section carries no opportunities and **that is
correct output, not an incomplete section.** `GV.RM-07` asks that opportunities be characterised
where they exist, not that every section invent one.

There is deliberately **no "opportunities: none identified" placeholder.** A placeholder is a
box, and a box on a board page manufactures pressure to fill it — which is precisely how this
element would turn into the marketing copy the grounding rule exists to prevent.

## Two worked examples

**Accepted.** The vendor section, against a goal the worked business context declares:

```json
"opportunities": [
  {"text": "A tested exit on the plant historian is what makes the Dublin renewal negotiable — the arrangement is the group's single production dependency and the supplier knows it.",
   "cites": "goal:Close the Dublin authorisation year without a supervisory finding",
   "gvsc": "GV.RM-07"}
]
```

It names a thing the organisation wrote down, it says what changes if the security work happens,
and a reader can go and check the goal.

**Refused.** Same idea, no source:

```json
"opportunities": [
  {"text": "Stronger third-party assurance would be a real differentiator for us in enterprise deals."}
]
```

The assembler refuses this and says why. There may well be a true version of it — but until
somebody declares the goal it would cite, the honest output is no entry at all.

## Deliberately scoped to board output

The 8286 series puts positive risk **earlier than board reporting**: 8286r1's lifecycle step 2
is *"catalog positive and negative uncertainties"*, 8286A r1 says opportunities warrant the same
systematic identification as threats, and 8286C r1 §4.2.3 says every aggregation activity should
surface beneficial uncertainty. On a full reading, positive risk belongs in the register too.

It is **not** scoped there, and that is a recorded decision rather than a gap. 8286C r1 is candid
that positive risk management *"is a field of interest that is new to many readers and merits
further exploration."* The board element is where the evidence is strongest, the cost lowest and
the failure mode most contained. Register-level positive risk waits until somebody asks for it.

---

## Sources

- NIST CSF 2.0 Core, `GV.RM-07` — bundled at `skills/nist-csf/references/nist-csf-2.0-core.json`
- [NIST IR 8286r1 — Integrating Cybersecurity and Enterprise Risk Management](https://nvlpubs.nist.gov/nistpubs/ir/2025/NIST.IR.8286r1.pdf) (final, 18 December 2025)
- [NIST IR 8286A r1 — Identifying and Estimating Cybersecurity Risk](https://nvlpubs.nist.gov/nistpubs/ir/2025/NIST.IR.8286Ar1.pdf) (final, 18 December 2025)
- [NIST IR 8286C r1 — Staging Cybersecurity Risks for Enterprise Risk Management](https://nvlpubs.nist.gov/nistpubs/ir/2025/NIST.IR.8286Cr1.pdf) (final, 18 December 2025 — supersedes the 2022 edition)

**February 2025 was the initial public draft of all three, not the revision.** The finals landed
on 18 December 2025 and are what these links now serve. 8286B and 8286D are different: those
*were* finalised on 26 February 2025 and carry no `r1`. Anything in this repo still dated
"February 2025 revisions" is describing a draft.

*A Cyber Aware Creation · Not affiliated with NIST. Not legal advice.*
