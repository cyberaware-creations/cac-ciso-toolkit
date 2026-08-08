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

**Status: scored 2026-08-08 against v0.42.0 — 12/15. B4 fixed and re-scored at v0.42.2 — 13/15.**
Routing mode, fifteen fresh `claude -p` sessions, $8.40, ~52s a case.

All six cases written to reach a *different* skill reached it — `risk-register`,
`incident-materiality`, `ciso-board-translation`, `exceptions-register`, `metrics-register` and
`nist-csf` each took the one written for it. That half is the load-bearing one: a checklist that
only proves a skill fires proves the easy direction.

## One real miss

**B4 — "What did the board actually say about outage tolerance? I want the exact words on file."**
Reached no skill. This skill owns board-voiced tolerance *verbatim* — recording the sentence the
board said rather than the number somebody derived from it is one of the two reasons it exists —
and the session instead searched the working directory, then Notion, Drive, Gmail and Dropbox,
and reported that it could not check them.

The behaviour after the miss was sound: it refused to reconstruct something plausible. But the
routing is wrong, and the shape is familiar — it is the same failure as `vendor-register`'s V6.
The prompt is phrased as *"what is on file"*, so the session went looking for a **file** rather
than for the register that holds the fact. Worth the same fix V6 got: lead the description with
retrieval as well as recording.

**Fixed at v0.42.2 and re-scored PASS — and the routing miss was hiding an engine gap.** Chasing
the fix found that `set-fact --board-tolerance` stored the board's sentence verbatim from the
first release, refused an unattributed one, and then **`show` never printed it.** The quote was
reachable only through `--json`. Widening the description on its own would have routed B4 here
and answered it with a page that does not mention the board — a worse outcome than the miss,
because it would have looked like it worked. `show` now prints each recorded sentence word for
word with who said it and when, and prints `NONE RECORDED` otherwise.

The re-scored answer leads with the absence and names the distinction the engine now prints:
*"Nobody wrote down what the board said about outage tolerance. That is a different fact from the
board having said nothing."* It declines to reconstruct a plausible version — *"a paraphrase
offered in answer to a request for exact words is precisely the failure the verbatim rule exists
to prevent"* — and states the scope rule in the user's own words: *"'On file' here means this
register. I didn't search Drive, Notion, or a mailbox — a document hunt answers a different
question."*

**B9–B14 were re-run alongside it** to check the widening pulled nothing in. All six still route
to the skill each was written for — `risk-register`, `incident-materiality`,
`ciso-board-translation`, `exceptions-register`, `metrics-register`, `nist-csf`. 7/7, $4.03.

## Two where the expectation is the weaker half

Both are recorded as fails and left red, because widening an expectation in the same breath as
seeing it fail is how a checklist stops measuring anything.

**B6 — "Which questions actually apply to us for an incident? We're not listed."** Expected
`business-context`, got `incident-materiality` — which produced a genuinely good answer: *"'not
listed' narrows exactly one thing — SEC Item 1.05. Nothing else,"* then listed what still
applies in full. The question is about which questions apply *to an incident*, and that consumer
owns the narrowed set. `business-context|incident-materiality` is probably the honest
pre-registration.

**B7 — "I'm assessing a vendor that uses an AI model, but we've declared no AI internally. Does
the AI battery still apply?"** Expected `business-context`, got `vendor-register` — **and
`business-context` also fired**, which the scorer records but does not count, since it takes the
first. The answer cited CAC-AP-1 §2.3 correctly: the subject outranks the profile, in both
directions. Two skills, one correct answer, and an expectation that names only one of them.

Both should become pipe lists **before** the next run, on the precedent set for A13 and Y1 —
argued on their own terms, and changed in a commit that does not also contain their result.

## Refresh the plugin first

```bash
claude plugin update cyber-aware-creations@cyber-aware-creations   # or the run scores a stale build
```

```bash
PROMPTS="$PWD/skills/business-context/evals/prompts.tsv" ./skills/nist-csf/evals/run-triggers.sh /tmp/biz-trigger
```

`claude plugin update` is a no-op when the version has not moved, so an edited skill is **not**
under test until the manifest version does.

---

*A Cyber Aware Creation · Not affiliated with NIST.*
