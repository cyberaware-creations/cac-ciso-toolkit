# Board Outcome Framing — Implementation Plan

**Date:** 2026-08-08
**Suite:** `cac-ciso-toolkit` v0.41.0 (executed against v0.42.3, shipped as v0.43.0)
**Design doc:** `strategy/board-outcome-design-2026-08-08.md` — **held outside this repository**, like
the `business-context` design doc before it. See the Execution record.
**Grounding:** `research/board-comms-methodology-2026-08-08.md` (corrected) ·
`research/ir8286-series-review-2026-08-08.md` — both also outside this repository
**Editions:** all NISTIR 8286 references are the **February 2025** revisions — `8286r1`, `A r1`,
`B upd1`, `C r1`, `D upd1`
**Status:** **Executed and shipped in v0.43.0, with one amendment to T3 — see the Execution
record at the end before changing anything here.**

For agentic workers: use `superpowers:executing-plans`. Checkbox (`- [ ]`) syntax.
**This touches every producer.** Phases 1–2 are additive and independent; Phase 3 is the
contract change and is sequenced last so a slip cannot block the enforcement work.

## Summary

Two changes. **C-1** turns the translation contract's existing requirements — a consequence in
every item sentence, a decision in every decisions entry — into a tested property. **C-2** adds
positive risk (`GV.RM-07`), permitted only when it cites a declared goal in `business-context`.

Both are additive. No producer's data changes, no existing sidecar stops validating, and the
refusal to compute a risk score is untouched.

---

## File map

**New**

- `skills/ciso-board-translation/references/consequence-vocabulary.json` — the connective and
  consequence-noun lists, plus decision verbs and opportunity vocabulary. **Data, not code**
- `skills/ciso-board-translation/references/positive-risk.md` — what `GV.RM-07` asks for, the
  grounding rule, and why blending is forbidden
- `skills/board-pack/evals/_outcomescan.py` — the shared checker
- `skills/board-pack/evals/outcome-framing.sh` — the floor check across all sections

**Modified**

- `skills/ciso-board-translation/SKILL.md` — the opportunity element and its grounding rule
- `skills/*/evals/board-safety.sh` (8 files) — call the shared checker
- `skills/board-pack/scripts/assemble_pack.py` + `references/section-contract.md` +
  `evals/section-contract.sh` — the `opportunities` key
- `skills/board-pack/renderers/` — the opportunity block
- Each producer's `examples/*translations*.json` — worked opportunity entries where a goal exists
- `.github/workflows/evals.yml` · both manifests → `0.42.0`

---

## Pre-flight

- [x] `main` clean at v0.41.0; all self-tests green
- [x] Design doc §2 read — in particular that C-1 is a **floor**, not a per-sentence gate
- [x] `business-context` strategic-goal and crown-jewel field names read, so C-2 cites real keys

---

## Phase 0 — Citation accuracy (independent, documentation only)

> Ships on its own. Nothing below depends on it, and it depends on nothing.

### T0: Correct the 8286 citations across the suite

**Files:** `skills/risk-register/SKILL.md`, `references/schema.md`, `scripts/score_register.py`
(comments only), plus any other `8286` reference found by grep

**Rationale:** the suite cites NISTIR 8286 in shipped guidance and attributes to it a prescription
it does not make. In a product whose pitch is citation accuracy, that is worth fixing even though
nothing behaves incorrectly.

**Implementation notes:**
- **Point every citation at the 2025 editions** (`8286r1`, `8286A r1`). The 2022 originals are
  superseded.
- **Fix the if-then attribution.** `SKILL.md` says *"8286 wants this if-then framing"*; 8286A r1
  §2.2 prescribes a **four-part scenario** — asset, threat, vulnerability, impact — and prescribes
  no template. 8286r1's own example is cause-and-effect prose.
- **Keep if-then.** The reasoning behind it holds: a topic cannot be scored or treated. Re-word as
  a **house format informed by** 8286A r1's scenario elements, rather than a NIST requirement. In
  `schema.md`, `description` becomes *"If \<event\>, then \<consequence\> — CAC house format,
  carrying 8286A r1's scenario elements."*
- **Change no behaviour.** Documentation and comments only; no schema change, no code path.

**Verification:** `grep -rn "8286" skills/` shows only 2025 editions; no remaining text claims NIST
prescribes if-then; every self-test and eval unchanged and green; `git diff --stat` touches no `.py`
outside comments.

- [x] T0 complete

**Phase 0 checkpoint:** citations are accurate and nothing behaves differently.

- [x] Phase 0 checkpoint passed

---

## Phase 1 — C-1, enforcement

### T1: The vocabulary file

**Files:** create `skills/ciso-board-translation/references/consequence-vocabulary.json`

**Implementation notes:**
- Four lists: `connectives`, `consequenceNouns`, `decisionVerbs`, `opportunityVocabulary`.
- Seed from the shipped examples — they are the reference implementation of good output, so the
  vocabulary should already pass them.
- `datasetVersion` and a note that extending it is the intended response to a false negative.

**Verification:** every shipped example sidecar passes when checked against this vocabulary. If
one fails, the vocabulary is wrong, not the example.

- [x] T1 complete

### T2: The shared checker

**Files:** create `skills/board-pack/evals/_outcomescan.py`

**Implementation notes:**
- `check(sidecar, vocab) -> {itemsTotal, itemsWithConsequence, decisionsTotal, decisionsWithDecision, failures[]}`
- A consequence requires a **connective and** a consequence noun. Either alone is not enough —
  "so" appears everywhere.
- A decision entry passes on a leading decision verb **or** an explicit `or` fork.
- **Every failure names the sentence**, truncated, with its item id.

**Tests to write first:**
1. `"Patch compliance fell to 88%."` → no consequence.
2. The shipped M-001 sentence → consequence found.
3. `"We should look at this."` → not a decision.
4. The shipped fork decision → passes.
5. An empty section → reports zero totals and does not divide by zero.

**Verification:** all five green.

**Depends on:** T1

- [x] T2 complete

### T3: The floor, wired into board-safety

**Files:** create `evals/outcome-framing.sh`; modify eight `board-safety.sh` files

**Implementation notes:**
- **Hard rule:** every `decisions[]` entry must pass. Unambiguous, no floor.
- **Floor:** ≥ **80%** of item sentences carry a consequence. Configurable in one place.
  **→ AMENDED. See the Execution record: the shipped rule is 80% AND at least one miss always
  tolerated. Do not "correct" this back to a flat 80%.**
- Per-item misses print as **warnings**; only the floor fails the run.
- Existing board-safety checks unchanged — append, do not restructure.

**Verification:** all eight board-safety suites green on shipped examples; a fixture with three
consequence-free sentences out of four fails and names all three.

**Depends on:** T2

- [x] T3 complete, as amended

### T4: Mutation-prove it

**Files:** `evals/guard-proofs/outcome-framing.json` (per CAC-GP-1, if built; otherwise record in
the eval header **and** as a fixture)

**Implementation notes:** strip the consequence clause from a shipped example sentence; the floor
must fail. Restore; must pass. **Prove both directions.**

**Verification:** seen to fail, then pass.

**Depends on:** T3

- [x] T4 complete

**Phase 1 checkpoint:** the contract's existing requirements are now tested, and the test has been
seen to fail.

- [x] Phase 1 checkpoint passed

---

## Phase 2 — C-2, positive risk

### T5: The translation guidance

**Files:** modify `skills/ciso-board-translation/SKILL.md`; create `references/positive-risk.md`

**Implementation notes:**
- State `GV.RM-07` verbatim, and IR 8286C's *"alongside"* framing.
- **The grounding rule, stated as a refusal:** an opportunity without a citation to a declared
  goal or crown-jewel dependency is not written. Ungrounded upside costs more credibility than
  silence — the skill already says this about regulatory overclaim; say it here too.
- **The blending prohibition**, with the reason: an optimistic tail on a risk sentence reads as
  softening, and teaches a board to discount the section.
- Two worked examples, one grounded and accepted, one ungrounded and refused.

**Verification:** trigger-prompt eval green; `positive-risk.md` names the Subcategory and the source.

**Depends on:** T4

- [x] T5 complete

### T6: No blending — the eval

**Files:** modify `evals/outcome-framing.sh`, `_outcomescan.py`

**Implementation notes:** no sentence in a risk-carrying item map may contain opportunity
vocabulary. Catches the optimistic tail before it reaches a page.

**Verification:** a fixture with *"…and this also unlocks faster onboarding"* appended to a risk
sentence fails, naming it.

**Depends on:** T5

- [x] T6 complete

### T7: Worked examples

**Files:** modify each producer's `examples/*translations*.json`

**Implementation notes:**
- Add opportunities **only where the worked business context actually declares a goal** to cite.
  Some sections will legitimately have none, and leaving them empty is the correct demonstration.
- The vendor example is the natural one: a tested exit making a renewal negotiable.

**Verification:** every added entry carries a `cites`; at least one example section has none and
renders cleanly without it.

**Depends on:** T6

- [x] T7 complete

**Phase 2 checkpoint:** opportunities are groundable, ungrounded ones are refused, and absence
renders nothing.

- [x] Phase 2 checkpoint passed

---

## Phase 3 — The contract and the render

### T8: `opportunities` in the section contract

**Files:** modify `skills/board-pack/scripts/assemble_pack.py`,
`references/section-contract.md`, `evals/section-contract.sh`

**Implementation notes:**
- **Additive within `contractVersion: 1`** — third use of the precedent documented above
  `ENVELOPE_KEYS`. Do not bump.
- `opportunities` is an array of `{text, cites, gvsc}`. **The assembler validates `cites` is
  present and refuses the section without it** — the grounding rule enforced at the contract, not
  only in guidance.
- It is **not** an item map; add it to the envelope keys so the mis-spelled-item-map detector does
  not flag it.

**Verification:** a sidecar with no `opportunities` assembles **byte-identically** to before T8; one
with an uncited opportunity is refused, naming the rule.

**Depends on:** T7

- [x] T8 complete

### T9: The opportunity block

**Files:** modify `skills/board-pack/renderers/`

**Implementation notes:**
- Rendered **after items, before decisions** — exposure, cost, what good unlocks, decision.
- **Patina, not RAG green.** The brand system is explicit that patina never signals "safe", and an
  opportunity is not a low-severity risk. Carries its word, as the graphics standard requires.
- Absent → renders nothing. No placeholder.

**Verification:** eval asserts no RAG hex on an opportunity block; a section without opportunities
produces output identical to before.

**Depends on:** T8

- [x] T9 complete

### T10: Registration

**Files:** `.github/workflows/evals.yml`, `README.md`, both manifests

**Implementation notes:** add `outcome-framing.sh` individually; re-run all eight `board-safety.sh`
and `section-contract.sh`; both manifests → `0.42.0`.

**Verification:** `check-versions.py` green; full floor job passes on 3.9.

- [x] T10 complete — shipped as `0.43.0` rather than `0.42.0`, see the Execution record

---

## Final verification

- [x] All eight `board-safety.sh` green on shipped examples — **nine**, see the Execution record
- [x] `outcome-framing.sh` **seen to fail**, then pass
- [x] A pack with no `opportunities` assembles byte-identically to v0.41.0
- [x] An uncited opportunity is refused at the assembler, not just discouraged in guidance
- [x] No opportunity vocabulary appears in any risk-carrying item sentence
- [x] A section with no declared goals renders with no opportunity block and no placeholder

## Known risks & mitigations

| Risk | Mitigation |
|---|---|
| **The consequence check becomes a style checker** | It tests presence of a required element, never quality. Floor not gate; per-item misses warn |
| False negatives frustrate authors | Failures name the sentence; vocabulary is data and extending it is the intended response |
| **Opportunity becomes marketing copy on a board page** | `cites` required and enforced at the assembler; no citation, no entry |
| An optimistic tail softens a risk sentence | T6 forbids blending outright |
| Sections manufacture opportunities to look complete | Absence renders nothing; there is no placeholder to fill |
| Third contract change in three releases | Additive on a documented precedent; byte-identical no-`opportunities` pack asserted |

## Rollback

Additive throughout. Every existing sidecar omits `opportunities` and still validates; the
enforcement work adds checks without changing producer data. Reverting restores prior behaviour
with no migration.

## Follow-on

- **OD-1a — Risk Response Cost** (design §6). **8286r1 Table 1 lists it among the core CSRR
  elements** and the suite doesn't carry it. Not an invention — an adoption from the register model
  already cited, and it answers the question every generated decision currently begs: *what would
  fixing this cost?* Small, well-grounded, worth doing next.
- **OD-1b — modelled loss exposure.** A different figure from response cost, and riskier. If it
  ships it carries a **named method** (8286C r1: PML, MFL, VAR) rendered beside the number. Decide
  separately.
- **The four-element scenario as fields** in `risk-register` — asset, threat, vulnerability, impact,
  per 8286A r1 §2.2, with if-then rendered from them. A schema change to a shipped store.
- **Profile versus register.** 8286C r1 keeps the distinction verbatim: executives get *"a
  prioritized inventory of the most significant risks… versus a complete inventory."* Worth checking
  whether the board pack carries the significant few or everything.
- **Register-level positive risk.** The 8286 series puts opportunity in identification and in every
  aggregation activity, not only in board output. Deliberately out of scope while NIST still calls
  it emerging practice — recorded so the decision is visible rather than forgotten.

---

# Execution record

**Executed 2026-08-08 against v0.42.3. Shipped as v0.43.0.** Alongside the release-readiness
findings for v0.42.0, which are recorded in the CHANGELOG rather than here.

## The one amendment — T3's floor

**The plan specified a flat 80%. The shipped rule is 80% AND at least one miss always tolerated,
and the divergence was raised at the time and ratified.** Do not change it back to a flat 80%
without re-opening the argument below.

The reason: **on a section with four items, an 80% floor is a 100% gate wearing a percentage.**
Three of four is 75% and would fail. Four of the eight shipped sidecars carry four or five items,
so a flat 80% is a perfect gate on half the suite — and the design's own words, in §2 of the
design doc and repeated in this plan's Known Risks table, are *"a floor, not a per-sentence
gate"*. A linguistic check over prose, with acknowledged false negatives, must not be perfect on
a small section.

The rule as shipped:

```python
allowed = max(1, int(round(items_total * (1 - floor))))
```

Two misses is a pattern worth failing on; one is a phrasing. On a ten-item section the tolerance
is exactly the 80% the plan asked for, so nothing is loosened where the share can express itself.

Lives in `skills/board-pack/evals/_outcomescan.py`, with the reasoning in the comment above that
line and in the v0.43.0 CHANGELOG entry.

## Everything else, as planned or better

| Task | Note |
|---|---|
| T0 | Done. No behaviour changed; `score_register.py` 185/185 and board-safety unchanged |
| T1 | The vocabulary needed **widening twice** before every shipped sidecar passed, exactly as T1's verification says it should: *if one fails, the vocabulary is wrong, not the example.* Ended at 42 connectives, 105 consequence nouns, 50 decision verbs |
| T2 | All five named tests written first, plus two more the design implies |
| T3 | Amended (above). Wired into **nine** `board-safety.sh`, not eight — the plan predates `attention-surface`. `business-context` ships no sidecar because it is framing rather than a section, and that is asserted rather than skipped: the day it gains one, the check fails |
| T4 | CAC-GP-1 **was** built, so `outcome-framing.sh` is a registered guard rather than a prose note. Two mutations, one per half: the floor stops biting, and the hard decision rule stops biting. Suite went 8 guards / 16 halves → **9 / 18** |
| T5–T7 | As planned. One worked opportunity ships, on the vendor section, citing the Dublin authorisation goal the worked business context actually declares — and six sections legitimately carry none, which is the demonstration T7 asked for |
| T8–T9 | As planned. Three checks added to `section-contract.sh`: the refusal, the additive byte-identity, and the colour rule |
| T10 | Shipped as **0.43.0**, not 0.42.0 — three releases intervened between the plan being written and executed. `mixed-evidence.sh` registered alongside `outcome-framing.sh` |

## What the guards caught during execution

Three defects, none of which review would have found, all in the C-2 rendering work:

1. **The opportunity heading in patina measured 2.93:1 on white** and failed WCAG AA at 16px/700 —
   caught by `responsive.sh` on the first render. Patina is the brand accent and is *not* a
   text-safe colour at that size. The rule down the block's left edge carries the identity; the
   heading is ink. T9's own instruction — *carries its word* — is what made this safe to fix.
2. **The board deck's core reached 19 slides**, past the 8–18 the assembly suite pins. Page one of
   the figures now stays in the core and the rest move to the appendix, the same rule already
   applied to item detail.
3. **Splitting a paginated block changed its TITLES**, and the moves-never-drops check caught three
   title runs going missing. The moved pages carry the suffixes the full deck uses and render as
   tiles, not text rows — a tile writes its value as its own run, so `"19"` re-rendered as
   `"AI deployments tracked: 19"` is a dropped run.

## The three grounding documents

`strategy/board-outcome-design-2026-08-08.md`,
`research/board-comms-methodology-2026-08-08.md` and
`research/ir8286-series-review-2026-08-08.md` were supplied as attachments and **are not in this
repository**, so the citations at the top of this file do not resolve here. That is the same
condition the `business-context` plan records about its own design doc, and it is written down
for the same reason: a dangling citation somebody discovers later should be a known fact, not a
mystery.

Their load-bearing content survives in the shipped artifacts —
`skills/ciso-board-translation/references/positive-risk.md` carries the `GV.RM-07` argument, the
grounding rule and both worked examples with their sources, and the corrected 8286 editions are
cited throughout `risk-register`.

---

*A Cyber Aware Creation · Not affiliated with NIST. Not legal advice.*
