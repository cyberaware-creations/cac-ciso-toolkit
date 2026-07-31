# CISO Toolkit — Board-Pack Skill Suite Implementation Plan (2→3→4→1)

**Date:** 2026-07-30 (rev b — all open decisions resolved)
**Status:** Ready for execution
**Target repo:** the `cyber-aware-creations` plugin (shipped v0.5.1)
**Design docs (approved):**
- `strategy/metrics-register-skill-design-2026-07-30.md` (#2)
- `strategy/exceptions-acceptances-skill-design-2026-07-30.md` (#3 — standalone `exceptions-register`)
- `strategy/incident-materiality-skill-design-2026-07-30.md` (#4)
- `strategy/board-pack-assembler-skill-design-2026-07-30.md` (#1)

> **For Claude Code + Superpowers:** execute phase-by-phase with `superpowers:executing-plans`. Each skill is independently shippable; each phase ends with a checkpoint. Steps use `- [ ]` for tracking. Bump the plugin `version` at each phase checkpoint (0.6.0 → 0.7.0 → 0.8.0 → 0.9.0).

---

## Summary

Adds the four "board-pack suite" capabilities on top of the three shipped skills, in dependency order: a metrics/KRI system-of-record (#2), a standalone exceptions/acceptances register (#3), an incident-materiality skill (#4), and finally the board-pack assembler (#1) that stitches all section producers into one quarterly PPTX/PDF. The spine is the **`board.json` section contract** — already shipped in `ciso-board-translation` and consumed by `risk-register` + `nist-csf` — which Phase 0 promotes to a versioned, enforced contract so every producer and the assembler evolve together.

## Why this order

`ciso-board-translation` (the board-voice engine) and the section contract already ship. Building the producers (#2, #3, #4) before the assembler (#1) means #1 consumes stable, structured inputs. #2 first (lowest-risk, proves the metric-keyed section); #3 next (self-contained, carries the DORA wedge); #4 next (episodic, standalone); #1 last (pure assembly).

---

## Locked decisions (resolved 2026-07-30)

| Decision | Locked value |
|---|---|
| #2 skill name / store / home | `metrics-register` / `.mtr` / **standalone** |
| #2 details | dated readings w/ period label · seed the 7 archetypes as starter templates · metric-keyed sidecar |
| **#3 home / name / store** | **standalone skill `exceptions-register` / `.exc`** (not a register extension) |
| **#3 relationship to `risk-register`** | `exceptions-register` is the **system of record**; `risk-register` keeps an `accepted` marker + a one-way `export-acceptances` bridge; **no `revalidate` added to the register** |
| #3 details | acceptances[] + exceptions[]; `deviationFrom` = free text + optional control ref; exceptions unscored in v1 |
| **#3 GTM gate (G1)** | **build the engine now; defer exceptions marketing/positioning** until DORA-scoped interviews validate demand |
| #4 skill name / store | `incident-materiality` / `.inc` (standalone) |
| **#4 jurisdiction scope v1** | **SEC Item 1.05 + DORA only** (state/NIS2/sectoral → v2 reference pack) |
| #4 details | factor framework = recorded checklist, never scoring-to-verdict; per-incident append-only determination history |
| #1 skill name / config / output | `board-pack` / `pack.manifest.json` / **PPTX + PDF both** |
| #1 details | consumes the validated section contract as its interface (can also orchestrate producers); board + audit-committee audience variants |
| Section contract | `contractVersion: 1`, promoted to `board-pack/references/section-contract.md` |

## Gates

- **G1 — DORA-interview gate (blocks the go-to-market surface of Phase B, not its engine).** Build the Phase B engine (the standalone `exceptions-register`) regardless; gate the exceptions marketing/positioning and any "sell the inventory" copy on 10–15 DORA-scoped interviews (per the kill report). *Resolved policy: build now, defer GTM.*
- **G2 — Contract sign-off (blocks Phase 0).** Confirm the `board.json` envelope in Phase 0 / T0.1 before retrofitting the two shipped consumers.

## Global conventions (apply to every task)

- **Deterministic engines, standard library only**, each with a `self-test`/`self_test` asserting reference math against an authored golden fixture (parity discipline from `score_register.py` / `profile_analysis.py`).
- **Derived-never-stored:** trend, bands, status, coverage, deadlines — computed on demand (snapshots are the only frozen record).
- **Append-only history**, canonical `YYYY-MM-DD` dates only (unpadded dates refused on write), material changes require `--why`.
- **Board-safety guards** on every board-facing view: no confidence vocabulary (age = distance-from-cadence), inherited from `risk-register/evals/board-safety.sh` checks 9/10; Phase C extends it to reject catastrophizing.
- **All board prose composes `ciso-board-translation`** via a `board.json` sidecar; unfilled slots render a marked placeholder — never hand-write or fabricate board prose.
- **Footer on every deliverable:** *"A Cyber Aware Creation · Not affiliated with NIST."*
- Each new skill is authored/iterated through the **skill-creator eval loop** (with-skill vs baseline, trigger-accuracy set, description optimizer).

---

## Pre-flight checks
- [ ] All four design docs reviewed and approved
- [ ] G2 (contract sign-off) resolved
- [ ] Repo cloned, `python3` available, existing `self-test`s green on `risk-register` and `nist-csf`
- [ ] Git worktree/branch created for the suite
- [ ] Baseline: `render_board.py`/`render_executive.py` produce valid output on the example stores

---

## Phase 0 — Promote & version the section contract (the seam)

*Do this first; everything downstream depends on it. Small, load-bearing, touches shipped code.*

**File map — New:** `skills/board-pack/references/section-contract.md`. **Modified:** `skills/ciso-board-translation/SKILL.md` (document `section` + `contractVersion` keys), `skills/risk-register/renderers/_common.py` + `render_board.py`/`render_report.py`, `skills/nist-csf/renderers/render_executive.py` + `_common.py`.

### T0.1: Write the canonical section contract
**Files:** Create `skills/board-pack/references/section-contract.md`.
**Notes:** Envelope = `{section, executiveSummary, <itemsKey>{id:sentence}, decisions[], asOf, contractVersion:1}`. Enumerate the five sections and their exact keys: `risk`→`risks`(+`themes`), `posture`→`gaps`, `metrics`→`metrics`, `exceptions`→`acceptances`+`exceptions`, `incident`→`incidents`. Carry the shipped rules (nested per-item map, one sentence/key, placeholder-beats-fabrication).
**Verification:** Doc lists all five sections with their exact item-key spellings.
- [ ] T0.1 complete

### T0.2: Retrofit the two shipped consumers to stamp `contractVersion`
**Files:** Modify `risk-register` and `nist-csf` executive renderers + their `example-translations.json`.
**Notes:** Additive only — a sidecar without `contractVersion` still renders (treat as v1). Do **not** change the per-item map keys.
**Verification:** Both skills' existing renderer tests pass; sidecars with and without `contractVersion` both render.
- [ ] T0.2 complete

**Phase 0 checkpoint:** existing `risk-register` + `nist-csf` board renders unchanged; contract doc exists.
- [ ] Phase 0 checkpoint passed

---

## Phase A — `metrics-register` (#2)

**File map — New:** `skills/metrics-register/SKILL.md`; `scripts/metrics_analysis.py`; `references/{schema.md,metrics-method.md,archetype-bridge.md,brand.md,report-layout.md}`; `renderers/{render_operational.py,render_executive.py,_common.py}`; `evals/{trigger-prompts.md,metric-trend.sh,board-safety.sh}`; `examples/{example-metrics.mtr,example-translations.json}`. Design: `metrics-register-skill-design-2026-07-30.md`.

### TA.1: Define the `.mtr` schema
**Files:** Create `references/schema.md`.
**Notes:** `metrics[]` (id, name, archetype, unit, direction, threshold{target,warn,critical}, owner, csfSubcategoryIds[], riskIds[], vanityRisk, notes), `readings[]` (metricId, period, value, source, actor, ts, note), `meta`, timestamps. Derived-never-stored list explicit.
**Verification:** Schema documents every field + the derived list; matches design §4.
- [ ] TA.1 complete

### TA.2: Engine — store I/O + mutations (TDD)
**Files:** Create `scripts/metrics_analysis.py`, `examples/example-metrics.mtr`.
**Notes:** `init`, `add-metric`, `record`, `set-threshold`, `link`, all append-only-history + schema-safe + canonical-date-refusing. Standard library only.
**Tests first:** add-metric persists; record appends a reading; unpadded date refused leaves file byte-identical.
**Verification:** `self-test` green; the three tests pass.
- [ ] TA.2 complete

### TA.3: Engine — deterministic derivations (TDD)
**Files:** Modify `scripts/metrics_analysis.py`; add derivation cases to `self-test`.
**Notes:** direction-aware trend (gaining/holding/slipping), delta vs prior, threshold status respecting direction, staleness band (distance-from-cadence, **not** confidence), vanity flag.
**Tests first:** a lower-better metric rising reports "slipping"; a value past `critical` on the correct side reports critical; a stale reading bands by age not confidence.
**Verification:** `self-test` green incl. the direction-polarity cases.
- [ ] TA.3 complete

### TA.4: Engine — attention lists + rollups
**Files:** Modify `scripts/metrics_analysis.py`.
**Notes:** breached / worsening / stale / unowned / vanity lists; rollups by archetype and CSF Function.
**Verification:** `self-test` asserts each list's membership and pinned counts.
- [ ] TA.4 complete

### TA.5: `archetype-bridge.md` + `metrics-method.md`
**Files:** Create both references.
**Notes:** bridge maps each `archetype` to `ciso-board-translation/references/metric-archetypes.md` (pointer, not a copy); method = trend/threshold/direction rules.
**Verification:** bridge references all seven archetype keys; no archetype prose duplicated.
- [ ] TA.5 complete

### TA.6: Renderers — operational + executive (with `--translations`)
**Files:** Create `renderers/*`.
**Notes:** operational = metric table + sparkline + attention lists; executive = top metrics via `ciso-board-translation`, emits/consumes `metrics.board.json` (metric-keyed, `contractVersion:1`); placeholder-on-missing; Limen brand + footer.
**Verification:** renders on `example-metrics.mtr`; missing translation → visible placeholder.
- [ ] TA.6 complete

### TA.7: Evals + SKILL.md + trigger boundary
**Files:** Create `evals/*`, `SKILL.md`.
**Notes:** `metric-trend.sh` mirrors `confirmation-age.sh`; `board-safety.sh` reuses checks 9/10. **Description must draw the boundary vs `ciso-board-translation`:** one-shot "translate this number" → translation skill; "track/add this quarter/show trends" → here.
**Verification:** `metric-trend.sh` exits 0 with exact check count; trigger set separates register asks from translation asks.
- [ ] TA.7 complete

**Phase A checkpoint:** self-test + evals green; end-to-end (init → record two periods → render board) yields valid `metrics.board.json` + HTML. Bump to 0.6.0.
- [ ] Phase A checkpoint passed

---

## Phase B — `exceptions-register` (#3, standalone)  *(engine ungated; marketing surface behind G1)*

**File map — New:** `skills/exceptions-register/SKILL.md`; `scripts/exceptions_register.py`; `references/{schema.md,exceptions.md,receipts.md,brand.md,report-layout.md}`; `renderers/{render_inventory.py,render_board.py,_common.py}`; `evals/{trigger-prompts.md,revalidation-lifecycle.sh,board-safety.sh}`; `examples/{example.exc,example-translations.json}`. **Modified (additive):** `skills/risk-register/scripts/score_register.py` (+ `SKILL.md`) — `export-acceptances` bridge + `accepted` marker only. Design: `exceptions-acceptances-skill-design-2026-07-30.md`.

### TB.1: Define the `.exc` schema
**Files:** Create `references/schema.md`, `references/exceptions.md`.
**Notes:** `acceptances[]` + `exceptions[]` (design §4), shared structured-approval + re-validation + expiry fields, append-only `history[]`, cross-link id arrays. `exceptions.md` = the exception + compensating-control model.
**Verification:** schema documents both object types + the event taxonomy; matches design §4.
- [ ] TB.1 complete

### TB.2: Engine — store + record mutations (TDD)
**Files:** Create `scripts/exceptions_register.py`, `examples/example.exc`.
**Notes:** `init`, `accept-add`, `except-add`, `close`, append-only + canonical-date + refusal discipline (no approver/justification/revalidate → refused before the file is touched).
**Tests first:** accept-add / except-add refuse without approver+justification+revalidate (file byte-identical); close appends event.
**Verification:** `self-test` green; the refusals leave the file unchanged.
- [ ] TB.2 complete

### TB.3: Engine — `revalidate` + derived status (TDD)
**Files:** Modify `scripts/exceptions_register.py`.
**Notes:** `revalidate` writes `acceptance-revalidated` / `exception-revalidated`, resets `revalidationDate` (rationale required); status band (current/due/overdue/expired) from dates + `--today`, distance-from-cadence not confidence.
**Tests first:** revalidate resets the clock + appends the event; refuses without `--why`; banding correct at boundary dates.
**Verification:** `self-test` + `revalidation-lifecycle.sh` pin the lifecycle.
- [ ] TB.3 complete

### TB.4: Inventory export + re-validation review ritual
**Files:** Modify `scripts/exceptions_register.py`; add the ritual to `SKILL.md` (or a reference).
**Notes:** `export-inventory` (CSV+JSON) = the DORA evidence artifact; the recurring review surfaces due/overdue, captures "still valid → revalidate / no longer → close/escalate," snapshots, reports.
**Verification:** export contains exactly the active items; ritual documented with exact commands.
- [ ] TB.4 complete

### TB.5: Renderers + board section
**Files:** Create `renderers/*`.
**Notes:** operational inventory view; executive board view via `ciso-board-translation`, emits `exceptions.board.json` (`acceptances{}` + `exceptions{}`, `contractVersion:1`); placeholder-on-missing; discoverability caveat visible; footer.
**Verification:** renders on `example.exc`; inventory counts match the store.
- [ ] TB.5 complete

### TB.6: `risk-register` bridge + evals + SKILL.md
**Files:** Modify `risk-register/score_register.py` (+SKILL.md); create `exceptions-register` `evals/*`.
**Notes:** register gains `export-acceptances` (writes accepted risks in the `.exc` intake shape, reusing the interop pattern) + keeps `accept` as an `accepted` marker — **no `revalidate` in the register**. `exceptions-register` description triggers on "exception, waiver, compensating control, risk-acceptance inventory, re-validate."
**Tests first:** `export-acceptances` round-trips into a valid `.exc` intake; existing register fixtures unchanged.
**Verification:** bridge round-trips; register regression-clean; `revalidation-lifecycle.sh` exits 0 with exact count; trigger set routes exception/acceptance asks to the new skill, register asks to the register.
- [ ] TB.6 complete

**Phase B checkpoint:** `exceptions-register` self-test + evals green; full acceptance+exception lifecycle demonstrable standalone; register bridge round-trips; register regression-clean. Bump to 0.7.0. **Hold the exceptions marketing surface until G1.**
- [ ] Phase B checkpoint passed

---

## Phase C — `incident-materiality` (#4)

**File map — New:** `skills/incident-materiality/SKILL.md`; `scripts/incident_analysis.py`; `references/{materiality-factors.md,disclosure-clocks.md,schema.md,brand.md,report-layout.md}`; `renderers/{render_worksheet.py,render_board.py,_common.py}`; `evals/{trigger-prompts.md,disclosure-clock.sh,board-safety.sh}`; `examples/{example-incident.inc,example-translations.json}`. Design: `incident-materiality-skill-design-2026-07-30.md`. **Scope locked: SEC Item 1.05 + DORA only.**

### TC.1: `.inc` schema + factor framework
**Files:** Create `references/schema.md`, `references/materiality-factors.md`.
**Notes:** incident record (design §4); factor framework is a **recorded checklist, not a scoring model**; the tool never emits a verdict.
**Verification:** schema documents append-only determination history; factors doc lists the factor set incl. the aggregation rule.
- [ ] TC.1 complete

### TC.2: Engine — record + determination mutations (TDD)
**Files:** Create `scripts/incident_analysis.py`, `examples/example-incident.inc`.
**Notes:** `open`, `assess-factor`, `determine` (state+rationale+decider), `set-disclosure`, append-only + canonical-date. No auto-verdict.
**Tests first:** determine appends with rationale + decider; a determination change is appended not overwritten; unpadded date refused.
**Verification:** `self_test` green.
- [ ] TC.2 complete

### TC.3: Engine — disclosure clocks (TDD, parity-critical)
**Files:** Modify `scripts/incident_analysis.py`; `references/disclosure-clocks.md`.
**Notes:** business-day math for Item 1.05 (four days **from determination date, not discovery**); DORA windows; status bands. SEC + DORA only.
**Tests first:** four-business-day deadline skips weekends; clock anchors on determinedAt; DORA windows computed; a determination-less "clock" flagged.
**Verification:** `disclosure-clock.sh` + `self_test` pin every date case.
- [ ] TC.3 complete

### TC.4: Renderers — worksheet + board narrative
**Files:** Create `renderers/*`.
**Notes:** worksheet (factors+rationale, determination history, live clock); board narrative via `ciso-board-translation`, aligned to public statements; emits `incident.board.json`; **not-legal-advice line on every artifact**; placeholder-on-missing.
**Verification:** renders on `example-incident.inc`; disclaimer present; no auto-verdict text.
- [ ] TC.4 complete

### TC.5: Evals (extended board-safety) + SKILL.md + cross-links
**Files:** Create `evals/*`; `SKILL.md`; wire `linkedRiskIds[]`/`linkedExceptionIds[]` (to `exceptions-register` records).
**Notes:** board-safety extended to **reject catastrophizing/fear framing**; description triggers on "is this material / do we have to disclose / start the 8-K clock / audit-committee incident update," not IR-runbook asks.
**Verification:** board-safety fails on injected fear phrasing; trigger set clean; risk/exception links resolve.
- [ ] TC.5 complete

**Phase C checkpoint:** self_test + evals green; end-to-end (open → assess → determine → disclosure → board render); every artifact carries not-legal-advice. Bump to 0.8.0.
- [ ] Phase C checkpoint passed

---

## Phase D — `board-pack` assembler (#1)

**File map — New:** `skills/board-pack/SKILL.md`; `scripts/assemble_pack.py`; `references/{pack-structure.md,brand.md,report-layout.md}` (section-contract.md exists from Phase 0); `assets/{board-template.pptx,report-layout.md}`; `evals/{assembly.sh,board-safety.sh,trigger-prompts.md}`; `examples/{pack.manifest.json,section fixtures,assembled example}`. Uses platform `pptx` + `pdf` skills. Design: `board-pack-assembler-skill-design-2026-07-30.md`. Producers: `risk-register`, `nist-csf`, `metrics-register`, `exceptions-register`, `incident-materiality`.

### TD.1: Manifest + contract validation (TDD)
**Files:** Create `scripts/assemble_pack.py`, `examples/pack.manifest.json`.
**Notes:** read manifest (sources, period, audience, translations paths, template); validate each `*.board.json` against `section-contract.md` (`section`, `contractVersion`, nesting, `asOf`); mismatched `asOf` → surfaced warning.
**Tests first:** a flat per-item map is rejected; an `asOf` mismatch is reported; an unknown `section` is rejected.
**Verification:** validation tests pass over golden section fixtures.
- [ ] TD.1 complete

### TD.2: Assembly — order, consolidate decisions, roll up counts (TDD)
**Files:** Modify `scripts/assemble_pack.py`.
**Notes:** deterministic — section ordering, **dedupe/merge `decisions[]`** across sections, cross-section headline counts, QoQ deltas from each store's latest snapshot. No prose here.
**Tests first:** duplicate decisions merge; counts sum correctly; incident section omitted when absent.
**Verification:** `assembly.sh` asserts ordering, dedup, counts, and **placeholder-on-missing**.
- [ ] TD.2 complete

### TD.3: Through-line via `ciso-board-translation`
**Files:** Modify `scripts/assemble_pack.py`; `references/pack-structure.md`.
**Notes:** feed section summaries + counts to `ciso-board-translation` for the single reconciling executive summary; never hand-roll. Audience variants (board vs audit-committee).
**Verification:** through-line slot renders from the composed sidecar; placeholder when absent.
- [ ] TD.3 complete

### TD.4: Output — PPTX + PDF via platform skills
**Files:** `assets/*`; wire `pptx` + `pdf` skills.
**Notes:** Limen brand; footer on every page; not-legal-advice on the incident section; both formats share the assembled content model.
**Verification:** end-to-end run over the example stores for all five producers yields one PPTX + one PDF.
- [ ] TD.4 complete

### TD.5: Evals + SKILL.md
**Files:** Create `evals/*`, `SKILL.md`.
**Notes:** board-safety over the finished pack; description triggers on "build the board pack / assemble the quarterly deck / audit-committee pack," not single-section asks.
**Verification:** board-safety green on assembled pack; trigger set clean.
- [ ] TD.5 complete

**Phase D checkpoint (toolkit integration test):** assemble a full pack from example `.rr`/`.csfa`/`.mtr`/`.exc`/`.inc` → PPTX+PDF, one through-line, consolidated decisions, all disclaimers. Bump to 0.9.0.
- [ ] Phase D checkpoint passed

---

## Final verification
- [ ] All five skills' `self-test`/`self_test` green; all evals exit 0 with exact check counts
- [ ] Full board pack assembles end-to-end across all producers
- [ ] Board-safety passes on every board-facing view (no confidence vocabulary, no catastrophizing)
- [ ] Every deliverable carries the footer; incident artifacts carry not-legal-advice
- [ ] No fabricated content — missing translation always renders a placeholder
- [ ] Trigger-accuracy sets show no cannibalization (metrics-register ↔ ciso-board-translation; exceptions-register ↔ risk-register; board-pack ↔ single-section asks)
- [ ] `risk-register` `export-acceptances` bridge round-trips into `exceptions-register`; register regression-clean
- [ ] `plugin.json` version bumped; keywords updated (add metrics/kri, exceptions, acceptance, incident, materiality, board-pack)

## Known risks & mitigations
- **Trigger cannibalization** → sharp descriptions + trigger-accuracy evals are acceptance criteria, not polish. Watch metrics↔translation and exceptions↔register especially.
- **Two homes for acceptance** (register `accepted` marker vs `exceptions-register` SoR) → resolved by making `exceptions-register` the SoR and the register a one-way feeder; do **not** build a second revalidation lifecycle in the register.
- **Assembler scope creep** → contract validation + "consumes, never derives"; any computation is a bug that belongs in a producer.
- **Legal exposure on #4** → never emits a verdict; not-legal-advice on every artifact; extended board-safety guard; SEC+DORA scope only.
- **Discoverability** on #3/#4 records → governance-level, aligned-to-disclosure; caveat surfaced on risk/exception/incident links.
- **DORA-wedge demand unproven (G1)** → engine is low-regret; gate the marketing surface, not the build.
- **Contract drift** → `contractVersion` + one canonical `section-contract.md`; retrofit shipped consumers in Phase 0.

## Rollback plan
Each phase is additive and independently revertible. #2 (`metrics-register`), #3 (`exceptions-register`), and #4 (`incident-materiality`) are new skill dirs — delete to roll back. #3's only touch to shipped code is the additive `export-acceptances` + `accepted` marker in `risk-register` (revert the commit; existing `.rr` files unaffected — no acceptance behavior was removed). #1 (`board-pack`) is a new skill dir. Phase 0's contract retrofit is backward-compatible (a sidecar without `contractVersion` still renders), so reverting it does not break existing packs.
