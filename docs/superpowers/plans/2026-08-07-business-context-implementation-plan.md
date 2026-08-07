# business-context — Specification and Implementation Plan

**Date:** 2026-08-07
**Suite:** Cyber Aware Creations CISO toolkit (`cac-ciso-toolkit`, shipped v0.29.0)
**Design doc:** `strategy/business-context-skill-design-2026-08-07.md` (rev b — decisions locked)
**Status:** **Executed and audited.** See the Execution record at the end — including the fact that the design doc cited on the line above never existed in this repository.

For agentic workers (e.g. Claude Code with Superpowers):
Use `superpowers:executing-plans`. Steps use checkbox (`- [ ]`) syntax for tracking.

Phases 1–4 build the skill. **Phase 5 is the point of the whole plan** — it proves CAC-AP-1
survives a real consumer before four more are built against it. Do not skip it to save time.

## Summary

Builds skill #8, `business-context`: a `.biz` store holding the organisation's own facts, and the
**applicability profile** that lets every other skill ask only the questions that apply. Then
proves the contract against exactly one existing consumer, `incident-materiality`.

The organising idea: **the profile narrows the question set and never answers a question.** A
skill with no profile asks everything; a subject that contradicts the profile wins; and every
skipped battery is recorded with its reason so an auditor can tell out-of-scope from unasked.

## Decisions this plan encodes

From the design doc's locked banner. Recorded here because a plan that restates them is a plan
that cannot quietly drift from them.

- **Framing, not a sixth board section.** The `section` enum stays at five values. `business-context`
  supplies cover, opening context, and a provenance stamp naming the profile version.
- **Revenue stored exact, rendered as a band.** The band is derived at render time from a fixed
  ladder and never stored, so it cannot drift from the figure it describes.
- **One escalation trigger in v1** — `profile-stale`. `fact-unattributed` is deferred until there
  is volume data from a real file.
- **Single entity in v1**, with the two forward-compatibility measures in T2 and the note in
  §"Follow-on". Neither is optional.
- **Manual declaration in v1.** No ingestion of published reports.

## Why only one consumer in Phase 5

`incident-materiality` is the right proof because its question set is *genuinely* conditional —
SEC Item 1.05 applies to a listed entity, the DORA report windows apply to a DORA-scoped one, and
its financial factor is the place the revenue base was always missing. A skill whose narrowing is
token would prove nothing.

This mirrors the sequencing that worked for CAC-EL-1: `board-pack` was built against
`risk-register` alone first, which proved the §1.3 shape survived a consumer before three more
producers were built against it.

---

## File map

**New — the skill**
- `skills/business-context/SKILL.md` — trigger surface, handling note for a sensitive store
- `skills/business-context/scripts/business_context.py` — engine + `self-test`; the only place
  narrowing logic lives
- `skills/business-context/renderers/_common.py` — vendored per house rule; no cross-skill imports
- `skills/business-context/renderers/render_context.py` — the `framing` output
- `skills/business-context/references/schema.md` — `.biz` shape
- `skills/business-context/references/applicability-contract.md` — CAC-AP-1, normative, written
  for *consumers* to implement against
- `skills/business-context/examples/example-org.biz` — worked file
- `skills/business-context/evals/applicability.sh` — the contract's behavioural suite
- `skills/business-context/evals/no-derived-materiality.sh` — the §5 guardrail as a test
- `skills/business-context/evals/board-safety.sh` — inherited vocabulary rules
- `skills/business-context/evals/prompts.tsv`, `evals/trigger-prompts.md`

**Modified**
- `skills/incident-materiality/scripts/incident_analysis.py` — accept `--context`
- `skills/incident-materiality/SKILL.md`, `.../references/`, `.../evals/` — document and test it
- `.github/workflows/evals.yml` — new evals, listed individually (never globbed)
- `tools/check-versions.py` — the `VENDORED` glob and the skill inventory
- `README.md` — skill list and structure section
- `.claude-plugin/plugin.json`, `.codex-plugin/plugin.json` — version → `0.30.0`

---

## Pre-flight

- [x] Working from the suite repo, not the installed plugin copy
- [x] `main` is clean and every existing self-test passes before any change
- [x] `bash skills/risk-register/evals/python-compat.sh "$(command -v python3)"` passes
- [ ] Design doc rev b read in full, including the locked-decisions banner
      — **not satisfiable; the cited file does not exist in this repo.** See Execution record.

---

## Phase 1 — Store and provenance

### T1: Engine skeleton, load/save, `init`

**Files:** create `skills/business-context/scripts/business_context.py`

**Rationale:** Everything else writes into this shape. Get the envelope and the 3.9 floor right first.

**Implementation notes:**
- `from __future__ import annotations` on line 1 of the imports — the repo's 3.9 floor rejects
  bare `X | Y` at runtime even though it compiles. Every sibling engine does this.
- Stdlib only (`json`, `argparse`, `datetime`, `sys`, `pathlib`).
- Defaults merged **per key**, not wholesale, following `score_register.py`: a file that set one
  field keeps shipped values for the rest.
- Validation guards **writes**, never loads. A `.biz` carrying a bad value still opens.

**Verification:** `python3 scripts/business_context.py init /tmp/t.biz --org 'Acme'` writes a file
that `load` round-trips unchanged; re-running `init` on an existing path refuses rather than
overwriting.

- [x] T1 complete

### T2: The provenance wrapper, and the single-entity forward-compat measure

**Files:** modify `skills/business-context/scripts/business_context.py`

**Rationale:** Every declared value carries who said it and on what basis — the pattern `nist-csf`
uses for confirmed ratings. This task also lands the first of the two D-5 measures.

**Implementation notes:**
- Wrapper shape: `{"value", "declaredBy", "declaredOn", "basis"}`.
- A bare scalar is **legal on read** and reported as unattributed. Do not coerce on load.
- **D-5 measure 1:** `profile` sits at the **top level** of the document, not nested under an
  entity. A future `entities[]` inherits from it, each entity carrying only the flags that differ.
  Write this as a comment in the schema and in `references/schema.md`, naming it as a deliberate
  reservation — otherwise the first person to add groups nests the profile and forces a migration.

**Verification:** self-test asserts `value_of` returns the same result for `True` and for
`declared(True, "D. G.", "2026-07-14", "...")`, and that `is_attributed` distinguishes them.

**Depends on:** T1

- [x] T2 complete

### T3: `declare` — write a profile flag

**Files:** modify `scripts/business_context.py`

**Implementation notes:**
- `declare --flag aiInUse --value true --by 'Name' --basis '...'`.
- **Refuse a flag with no `--basis`.** This is the skill's version of the refusal discipline
  `exceptions-register` applies to a justification: a flag that narrows another skill's questions
  and cannot say why is worse than an absent flag, because absence asks everything (§2.2).
- Known flag names are a documented enumeration; an unknown flag is **accepted with a warning**,
  not refused — the perimeter list will outgrow the enumeration.
- Every write appends to `history` with a rationale.

**Verification:** self-test — a `declare` without `--basis` exits non-zero and leaves the file
**byte-identical**; a valid one appends exactly one history entry.

**Depends on:** T2

- [x] T3 complete

**Phase 1 checkpoint:** a `.biz` can be created and flags declared with provenance; refusals leave
the file untouched.

- [x] Phase 1 checkpoint passed

---

## Phase 2 — Facts, revenue, snapshots

### T4: `set-fact` — crown jewels and the narrative record

**Files:** modify `scripts/business_context.py`

**Implementation notes:**
- Crown jewel: `{system, enables, atStake}` — all three required. `atStake` is free text; it is
  the join to a business consequence and a crown jewel without one is just an asset.
- Also: segments, strategic goals, board tolerance (verbatim + attributed + dated), obligations.
- Board tolerance is stored **verbatim**. Never paraphrase, never summarise on write.

**Verification:** self-test — a crown jewel missing `atStake` is refused; the store round-trips a
tolerance quote containing quotes and non-ASCII unchanged.

**Depends on:** T3

- [x] T4 complete

### T5: `set-revenue`, and the band ladder

**Files:** modify `scripts/business_context.py`

**Rationale:** D-2. Exact for the materiality denominator, band for what circulates.

**Implementation notes:**
- Store `{"exact", "currency", "fiscalYear", ...provenance}`.
- The band is **derived, never stored** — computed at render from a module-level ladder so it can
  never drift from the figure.
- Ladder (module constant, documented in `schema.md`):
  `<10m · 10–50m · 50–100m · 100–250m · 250–500m · 500m–1bn · 1–5bn · >5bn`.

**Verification:** self-test asserts every ladder boundary lands in the band above it
(`revenue_band(10e6) == "10–50m"`, not `"<10m"`), and that no code path writes a band into the store.

**Depends on:** T4

- [x] T5 complete

### T6: `review` — snapshots that freeze profile and context

**Files:** modify `scripts/business_context.py`

**Rationale:** CAC-AP-1 §2.5. A determination made in Q1 was made against Q1's profile.

**Implementation notes:**
- `review --label '...' --why '...'`; both required.
- A snapshot freezes **both** bodies, following how `risk-register` freezes `settings` per snapshot.
- Snapshots are append-only and never edited.

**Verification:** self-test — declare a flag, snapshot, change the flag, and assert the snapshot
still reports the old value.

**Depends on:** T5

- [x] T6 complete

**Phase 2 checkpoint:** facts and revenue are recorded with provenance; a snapshot preserves the
profile as it stood.

- [x] Phase 2 checkpoint passed

---

## Phase 3 — `applies`, the contract engine

> This is the heart of the plan. Both clauses below have burned projects that got them backwards.

### T7: The narrowing function

**Files:** modify `scripts/business_context.py`

**Rationale:** CAC-AP-1 §2.2 and §2.3, in the one place they exist.

**Implementation notes:**
- Signature takes the profile, a consuming skill's question-set id, and **optional subject
  declarations**.
- Returns `{"ask": [...], "skipped": [{"battery", "reason", "flag", "declaredBy", "declaredOn"}]}`.
- **§2.2 — absence asks everything.** A flag that is missing, or whose `value` is `None`, must
  fall through to *ask*. Do not treat falsy as false: `False` means declared-not-applicable,
  `None`/absent means not-declared. Getting this wrong silently narrows every assessment.
- **§2.3 — the subject wins.** A subject declaration is applied **after** the profile and
  overrides it in both directions. It may re-add a battery the profile removed *and* remove one
  the profile kept.

**Tests to write first:**
1. Empty profile → **every** battery in `ask`, `skipped` empty.
2. Flag present but `value: None` → battery in `ask` (not skipped).
3. Flag `false` → battery in `skipped`, with `reason`, `declaredBy` and `declaredOn` populated.
4. Flag `false` **and** subject declares true → battery in `ask` (the design's vendor-with-AI case).
5. Flag `true` and subject declares false → battery in `skipped`, reason names the subject.

**Verification:** all five green in `self-test`. These are the checks the contract lives or dies on.

**Depends on:** T6

- [x] T7 complete

### T8: `applies` CLI and the skip record's rendered form

**Files:** modify `scripts/business_context.py`

**Implementation notes:**
- `applies --skill vendor [--subject-declares ai=true]`, human output and `--json`.
- §2.4 — the human form is the sentence a consumer embeds verbatim:
  > *AI battery — not assessed. No AI processing declared for this vendor (org profile:
  > `aiInUse: false`, declared 2026-07-14 by D. Galleyne).*
- An unknown `--skill` is **refused**, naming the known set. A typo that silently returns "ask
  nothing" is the worst possible failure here.

**Verification:** `applies --skill incident --json` on the worked example returns a skip record
whose rendered sentence contains the flag, the date and the declarer.

**Depends on:** T7

- [x] T8 complete

### T9: `export --context` — the consumer payload

**Files:** modify `scripts/business_context.py`

**Implementation notes:**
- One flat, versioned payload consumers read via `--context`. Carries `profileVersion` (the last
  snapshot label, or `unreviewed`), the flags, the revenue **exact**, and crown jewels.
- No skill imports another (house rule); this is the transport.

**Verification:** payload validates against `references/schema.md`; `profileVersion` is present
even on a never-reviewed file.

**Depends on:** T8

- [x] T9 complete

**Phase 3 checkpoint:** `applies` honours absence-asks-everything and subject-wins; the export
payload is stable.

- [x] Phase 3 checkpoint passed

---

## Phase 4 — Escalation, framing, guardrail

### T10: `profile-stale` escalation

**Files:** modify `scripts/business_context.py`

**Implementation notes:**
- CAC-EL-1 §1.3 shape, `subjectKind: "context"`, trigger `profile-stale`, one trigger only (D-3).
- Cadence is a setting with a shipped default; a file with one snapshot and a recent date
  escalates nothing.
- **Do not add `fact-unattributed`.** It is deferred by decision, and a freshly built file would
  escalate on nearly every field.

**Verification:** self-test — a file reviewed today escalates nothing; one reviewed beyond the
cadence emits exactly one record carrying `subjectRef` and `subjectKind`.

**Depends on:** T9

- [x] T10 complete

### T11: `framing` renderer

**Files:** create `renderers/_common.py`, `renderers/render_context.py`

**Implementation notes:**
- D-1 — cover, opening context paragraph, provenance stamp naming the profile version.
- Revenue renders as a **band** by default; `--render-revenue exact` overrides **and writes the
  override into the provenance line**, so a reader can tell which they hold.
- Vendored `_common.py`; no cross-skill imports.
- **`tools/check-versions.py` treats `skills/*/renderers` as the vendored-copy glob for
  `cac_graphics.py`.** This skill draws no charts. Either vendor the file anyway or narrow the
  glob — decide in T15 and do not leave the guard reporting a false "missing".

**Verification:** eval asserts the default render contains a band and no exact figure; the
`--render-revenue exact` render contains the figure **and** the override note.

**Depends on:** T10

- [x] T11 complete

### T12: `no-derived-materiality` eval

**Files:** create `evals/no-derived-materiality.sh`

**Rationale:** Design §5. The guardrail that stops the revenue base becoming a computed threshold.

**Implementation notes:** two checks, because either alone is weak.
1. **Behavioural** — no key in any output matches
   `materialityThreshold|pctOfRevenue|materialPercent|revenueShare`.
2. **Static** — no shipped `.py` in this skill contains a division or percentage expression whose
   operand is the revenue field.

**Verification:** the suite fails when a deliberately added `impact / revenue` line is introduced,
and passes when it is removed. **Prove both directions** — a guard never seen to fail is not
known to work.

**Depends on:** T11

- [x] T12 complete

### T13: `SKILL.md`, schema, contract reference, worked example

**Files:** create `SKILL.md`, `references/schema.md`, `references/applicability-contract.md`,
`examples/example-org.biz`, `evals/board-safety.sh`, `evals/prompts.tsv`, `evals/trigger-prompts.md`

**Implementation notes:**
- `applicability-contract.md` is written **for consumers** — a skill author implementing `--context`
  should need only this file. Reproduce §2.1–§2.6 verbatim from the design doc.
- `SKILL.md` carries the sensitivity note: a `.biz` concentrates revenue, crown jewels and
  board-room quotes in one document.
- The worked example must include at least one `false` flag and one crown jewel, so Phase 5 has
  something real to narrow against.
- `board-safety.sh` inherits the no-confidence-vocabulary checks (risk-register checks 9 and 10).

**Verification:** `board-safety.sh` green; the example loads and `applies --skill incident` against
it returns a non-empty `skipped`.

**Depends on:** T12

- [x] T13 complete

**Phase 4 checkpoint:** the skill is complete and self-contained — engine, renderer, docs, evals,
worked example — with `python3 scripts/business_context.py self-test` green.

- [x] Phase 4 checkpoint passed

---

## Phase 5 — Prove CAC-AP-1 against one consumer

### T14: `incident-materiality` accepts `--context`

**Files:** modify `skills/incident-materiality/scripts/incident_analysis.py`, its `SKILL.md`,
`references/`, and add `evals/applicability.sh`

**Rationale:** The reason the plan exists. Until a real consumer narrows against a real profile,
CAC-AP-1 is prose.

**Implementation notes:**
- `--context <file.biz>` **optional**. Absent → today's behaviour exactly, unchanged.
- Two conditional batteries, both genuinely conditional: **SEC Item 1.05** gated on a listed
  entity, **DORA report windows** gated on declared DORA scope.
- The **revenue base flows into the financial factor as a stated figure the human weighs** — and
  **no threshold is derived from it**. This skill emits no verdict and that does not change.
- Every skipped battery is recorded in the determination record and rendered per §2.4. A
  disclosure record that silently omits a question is worse than one that asks it.
- Read the payload as **data**. No import of `business_context.py`.

**Tests to write first:**
1. No `--context` → output byte-identical to the pre-change run on the same fixture.
2. Profile declaring not-listed → SEC battery skipped, skip reason present in the record.
3. Profile declaring not-listed, incident record declaring a listed subsidiary → SEC battery
   **asked** (§2.3).
4. Profile with revenue → the financial factor shows the base; **no** percentage appears anywhere.

**Verification:** `evals/applicability.sh` green; `incident_analysis.py self-test` still green;
test 1 diffed byte-for-byte, not eyeballed.

**Depends on:** T13

- [x] T14 complete

**Phase 5 checkpoint:** one real consumer narrows correctly, the subject overrides the profile, and
the unconfigured path is provably unchanged.

- [x] Phase 5 checkpoint passed

---

## Phase 6 — Registration

### T15: CI, drift guard, README, version

**Files:** modify `.github/workflows/evals.yml`, `tools/check-versions.py`, `README.md`,
`.claude-plugin/plugin.json`, `.codex-plugin/plugin.json`

**Implementation notes:**
- Add to the 3.9 floor job, **listed individually** — the repo's own comment explains that a loop
  over `evals/*.sh` goes green the day someone renames a directory:
  - `python3 skills/business-context/scripts/business_context.py self-test`
  - `evals/applicability.sh`, `evals/no-derived-materiality.sh`, `evals/board-safety.sh`
  - `skills/incident-materiality/evals/applicability.sh`
- Resolve the `VENDORED` glob question from T11.
- Both plugin manifests move to `0.30.0` together — `check-versions.py` fails on a mismatch.

**Verification:** `python3 tools/check-versions.py` green; the full floor job passes locally on a
3.9 interpreter.

**Depends on:** T14

- [x] T15 complete — with one deviation, recorded below

---

## Final verification

- [x] `business_context.py self-test` green, and the five T7 checks are among them
- [x] Every eval listed in T15 runs and passes on the 3.9 floor *(four of five; see deviation 1)*
- [x] `python-compat.sh` passes — including the new untracked files
- [x] `check-versions.py` green, both manifests at `0.30.0`
- [x] `incident_analysis.py` with no `--context` is byte-identical to pre-change output
- [x] The `no-derived-materiality` guard has been **seen to fail** and then pass
- [x] No skill imports another; `.biz` travels only as data

## Known risks & mitigations

| Risk | Mitigation |
|---|---|
| **Falsy-vs-absent collapse in `applies`** — the failure that silently narrows every assessment | T7 tests 1 and 2 exist only for this; `None` and `False` are distinguished explicitly, never by truthiness |
| A skipped battery is dropped instead of recorded, so an artifact looks complete | §2.4 render is asserted in T8 and again in the consumer at T14 |
| The revenue base becomes a computed materiality threshold | T12, both directions proven |
| `check-versions.py` reports a false "missing vendored copy" for a renderers dir with no charts | Explicitly owned by T11 and resolved in T15, rather than discovered in CI |
| Single-entity assumption spreads into the vendor skill | D-5 measure 1 in T2; measure 2 is a required task in the *vendor* plan, recorded in Follow-on below |
| Escalation noise on first run | Only `profile-stale` ships; a file reviewed today escalates nothing |

## Rollback

Every change is additive: a new skill directory, a new optional flag on one existing script, new CI
entries. `incident-materiality` with no `--context` is byte-identical to today, so reverting the
commit restores prior behaviour with no data migration. No existing store format changes.

## Follow-on — not in this plan

- **`--context` for the other four producers** (`risk-register`, `metrics-register`,
  `exceptions-register`, `nist-csf`). Deliberately deferred until Phase 5 proves the shape.
- **D-5 measure 2** — the vendor skill carries an optional `entityRef` on every vendor record from
  its first commit, defaulting to the single org. **This belongs in the vendor plan as a task, not
  a note.** Without it, every vendor record written before groups are supported must be revisited.
- `fact-unattributed` escalation, revisited with volume data from a real `.biz`.
- Ingestion from published reports (D-4, v2).

---

# Execution record — 2026-08-07

Shipped as **v0.30.0** in [#62]. Follow-on work has since carried the suite to **v0.33.0**, the
last step of which ([#68]) taught `board-pack` to read the profile.

This section was written during an audit that re-ran the plan's own verification steps as
executable checks rather than reading the code and agreeing with it. Boxes above are ticked
because that audit ticked them, not because the implementer reported them done.

## Deviations

**1 — `skills/business-context/evals/applicability.sh` was never created.**
It is named in the File map and in T15's CI list. Its substance lives inside the engine's
154-check `self-test`, which CI runs on the 3.9 floor — and T7's own verification line specifies
`self-test` as the home for the five contract checks, so the two halves of the plan disagreed with
each other. Nothing is unproven: all five cases are present (`business_context.py:994–1067`), plus
subject-`None` and empty-wrapper variants the plan did not ask for. Recorded as a deviation rather
than back-filled with a duplicate suite, because the coverage is real and a second file asserting
the same things would be ceremony. **The consumer-side `skills/incident-materiality/evals/applicability.sh`
does exist** (58 checks) and is registered in CI.

**2 — the cited design doc never existed in this repository.**
`strategy/business-context-skill-design-2026-08-07.md` (rev b — decisions locked) is the stated
source of D-1 through D-5 and a pre-flight requirement. There is no `strategy/` directory and the
file is nowhere in the repo. `business-context` was therefore the only skill owning a normative
cross-skill contract with no committed design record, while CAC-EL-1 has a full plan alongside
this one. A retrospective spec now exists at
`docs/superpowers/specs/2026-08-07-business-context-applicability-design.md`, and it says plainly
that it was written after the code.

**3 — the version target moved.** The plan targets `0.30.0`, which is what shipped. The manifests
now read `0.33.0` because subsequent work landed on top; both move together and `check-versions.py`
enforces it.

**4 — minor, T1.** The skeleton suggested `pathlib`; the implementation uses `tempfile` for atomic
writes instead. Stdlib-only holds. `from __future__ import annotations` is present at line 42, the
first line of the imports.

**5 — the `VENDORED` glob question (T11) was resolved by vendoring, not narrowing.**
`cac_graphics.py` is vendored into this skill's `renderers/` although it draws no charts, with a
comment in `_common.py` explaining that the copy exists so the drift guard stays honest.
`check-versions.py` reports 7 matching copies.

## What the audit executed

| Claim | Method | Result |
|---|---|---|
| T14-1 byte-identical with no `--context` | real diff against pre-change commit `ebd27cc` | `--out` JSON **and** store byte-for-byte identical, across 415 added lines |
| T5 ladder | every boundary evaluated | all 7 land in the band above; no band string in the store |
| T6 snapshot freeze | declare → snapshot → change | live `False`, snapshot still `True`; freezes profile *and* context |
| T3 / T4 / T6 refusals | `cmp` before and after | every refusal leaves the file byte-identical |
| T3 unknown flag | executed | accepted, warned, stored — and the warning names the §2.2 consequence |
| T8 unknown skill | executed | refused, naming the known set and why a silent empty set is worse |
| T9 `profileVersion` | fresh store | `unreviewed`, present |
| T10 escalation | today vs beyond cadence | 0 and exactly 1, with `subjectRef` + `subjectKind`; `profile-stale` is the only trigger |
| T11 renderer | both modes | band by default with no exact figure; `--render-revenue exact` shows the figure *and* the override note |
| T12 guardrail | poisoned copy | fails on both poisons, including through a local binding |
| T14-3 §2.3 | 4 incidents, 1 declaring | I-001 asks SEC, I-002/3/4 skip it — per-subject, not global |
| T14-4 | full output scan | revenue base stated; no derived-threshold key, no percentage string |
| §2.6 | import scan + source read | no cross-skill imports; `board-pack` reaches this skill by subprocess |
| Floor | `/usr/bin/python3` 3.9.6 | 55 shipped files compile; 154 + 172 self-test; 58 consumer; 7 guardrail; 10 board-safety |

[#62]: https://github.com/cyberaware-creations/cac-ciso-toolkit/pull/62
[#68]: https://github.com/cyberaware-creations/cac-ciso-toolkit/pull/68

---

*A Cyber Aware Creation · Not affiliated with NIST.*
