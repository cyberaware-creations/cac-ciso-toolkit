# Crosswalk Overlays — Phase 3 Implementation Plan (skill integration)

> **Shipped 2026-07-30 in v0.6.0 (PR #18). Filed as a record — do not execute.**
> Four things were decided differently during execution, so the file map below no longer
> describes the repo:
> - **"overlay" → "crosswalk"** throughout, with a `--lens` flag on the CLI.
> - **Build tooling lives in `tools/crosswalks/`**, not `skills/nist-csf/build/` — everything
>   under `skills/` ships to users, and a 144KB source export only a rebuild needs should not.
> - **No separate engine or renderer module:** the coverage engine folded into
>   `scripts/profile_analysis.py` and the report into `renderers/render_crosswalk.py`, matching
>   the two dashboards already there.
> - **Tests live in `evals/`** (`crosswalk-e2e.sh` + `evals/fixtures/`), not `tests/`, and the
>   parity assertions went into the existing engine `self-test` rather than a new file.
>
> Three things the plan did not anticipate were also built: scale-relative bands, suppression of
> bands drawn from too thin a basis, and a declared `catalogueScope` per lens. See the shipped
> `skills/nist-csf/references/crosswalks/README.md` for what is actually there.

**Date:** 2026-07-29 · **Status:** Ready for execution
**Design:** `plans/crosswalk-overlay-design-and-plan-2026-07-28.md` · **Legal spine:** `strategy/framework-licensing-iso-vs-cis-2026-07-28.md` · **Built artifacts:** `crosswalk-overlay-kit.zip` (data + `overlay_coverage.py` engine + `render_overlay_report.py` + validator)

> **For Claude Code (Superpowers):** execute task-by-task with `superpowers:executing-plans`. Checkbox syntax tracks progress. Target repo: `cac-ciso-toolkit`, skill at `skills/nist-csf/`.

## Summary
Fold the built crosswalk overlays into the `nist-csf` skill so a single `.csfa` assessment can be projected — read-only, bidirectionally — through ISO 27001:2022, CIS v8.1, and 800-53 r5. Phases 0–2 (data, engine, renderer) are already built and verified in the kit; this plan lands them in the skill, brands the report, wires SKILL.md, and adds evals. Nothing changes the `.csfa` schema or existing CSF math — overlays are additive.

## File map

**New files:**
- `skills/nist-csf/references/crosswalks/{800-53-r5,iso-27001-2022,cis-8.1}.catalog.json` — control catalogs (from kit)
- `skills/nist-csf/references/crosswalks/csf-2.0__{…}.map.json` — 3 crosswalk edge files (from kit)
- `skills/nist-csf/references/crosswalks/README.md` — provenance, legal, refresh runbook
- `skills/nist-csf/references/crosswalks/label-style.md` — CAC label style (from kit)
- `skills/nist-csf/build/author_catalogs.py`, `build/validate_crosswalks.py`, `build/_source_csf2.xlsx` — build-time only (not on the runtime path)
- `skills/nist-csf/tests/test_overlay_coverage.py` — engine parity + self-test
- `skills/nist-csf/tests/fixtures/overlay_golden.csfa` + `overlay_golden_expected.json` — parity fixture
- `skills/nist-csf/evals/overlay_triggers.jsonl`, `evals/overlay_e2e.md` — eval sets

**Modified files:**
- `skills/nist-csf/scripts/profile_analysis.py` — add overlay functions + self-test asserts
- `skills/nist-csf/scripts/<report renderer>.py` — add overlay render functions + branded overlay sections
- `skills/nist-csf/SKILL.md` — overlay workflow verbs, triggers, derived-not-audit framing
- `skills/nist-csf/references/framework-abstraction.md` — promote overlay contract from doc-only to enforced
- `skills/nist-csf/references/report-layout.md` — document overlay sections
- `skills/nist-csf/assets/` (+ `brand.md`) — brand tokens for the coverage ramp

## Pre-flight checks
- [ ] Design + handoff reviewed; ISO/CIS CAC labels reviewed by Darren
- [ ] `crosswalk-overlay-kit.zip` unzipped into a scratch dir in the repo
- [ ] Baseline `nist-csf` self-test + evals passing on a clean tree
- [ ] Git worktree created

---

## Phase 1 — Foundation: land data + build gate

### T1: Land the crosswalk data
**Files:** create `references/crosswalks/{3 catalogs, 3 maps, label-style.md}` (copy from kit `data/` + `scripts/label-style.md`).
**Rationale:** the read-only bundled data the engine reads.
**Verification:** `python -c "import json,glob;[json.load(open(f)) for f in glob.glob('skills/nist-csf/references/crosswalks/*.json')]"` exits 0; 6 JSON files present.
- [ ] T1 complete

### T2: Add build tooling (off the runtime path)
**Files:** create `build/author_catalogs.py`, `build/validate_crosswalks.py`, `build/_source_csf2.xlsx` (from kit). Point the validator's default dir at `../references/crosswalks`.
**Rationale:** reproducible rebuild + the legal/structural gate; kept out of `references/`/`scripts/` so it never ships on the skill's runtime path.
**Verification:** `python build/validate_crosswalks.py references/crosswalks` → `3 catalogs · 0 errors · 0 warnings`.
- [ ] T2 complete

### T3: Wire the validator into the skill's test target
**Files:** modify the skill's test entrypoint (or add `tests/test_crosswalk_data.py`) to shell `validate_crosswalks.py` and fail non-zero on any error.
**Rationale:** bad crosswalk data (verbatim ISO/CIS leakage, unresolved edges, missing provenance) must never ship.
**Verification:** temporarily corrupt one ISO label's `labelSource` to `verbatim-public-domain` → test FAILS; revert → passes.
- [ ] T3 complete

### T4: Formalize the overlay contract
**Files:** modify `references/framework-abstraction.md` — promote from doc-only to the enforced overlay contract: an overlay = `{frameworkId, name, version, license, provenance, groupings[], controls[{id,label,groupingId,labelSource,text}]}` + a map `{edges[{csfSubId,controlId,authority}], mappingAuthority}`. State the invariants the validator enforces (ISO/CIS `labelSource=cac-generated`, no `text`; every edge resolves) and that the assessed framework (CSF) is the only rated thing — overlays are read-only projection targets.
**Verification:** contract in the doc matches the rules in `validate_crosswalks.py` (1:1 on each invariant).
- [ ] T4 complete

**Phase 1 checkpoint:** data validates, gate is in the test suite, contract documented.
- [ ] Phase 1 checkpoint passed

---

## Phase 2 — Engine port

### T5: Port overlay loaders into the engine
**Files:** modify `scripts/profile_analysis.py` — add `load_overlay(frameworkId)`, `_band`, `_agg` (from kit `overlay_coverage.py`), resolving `references/crosswalks/` relative to the skill dir.
**Rationale:** the engine already owns deterministic `.csfa` math; overlays live beside it.
**Implementation notes:** profile shape already matches (`ratings{subId:{tier:0–4|null, na}}`). Keep functions pure/deterministic; no new deps.
**Verification:** `python -c "from scripts import profile_analysis as p; [p.load_overlay(f) for f in ('iso-27001-2022','cis-8.1','800-53-r5')]"` exits 0.
- [ ] T5 complete

### T6: Port coverage + reverse + completeness
**Files:** modify `scripts/profile_analysis.py` — add `derive_overlay_coverage(profile, overlay, agg="min")` (**control = weakest-link min; theme rollup = mean of member controls**), `reverse_lookup`, `completeness`.
**Rationale:** the three views (forward coverage, auditor reverse, honesty lists).
**Verification:** run on `tests/fixtures/overlay_golden.csfa`; spot-check a control (min of its mapped subs) and a theme (mean of member controls) by hand.
- [ ] T6 complete

### T7: Overlay self-test + parity fixture
**Files:** create `tests/test_overlay_coverage.py` (port the kit's data-independent `self_test`) and `tests/fixtures/overlay_golden.csfa` + `overlay_golden_expected.json` (a small hand-verified profile → expected control/theme/completeness numbers). Add to the engine's `self_test`.
**Rationale:** parity discipline mirroring `score_register.py` — lock the math.
**Verification:** `python scripts/profile_analysis.py self_test` green; `pytest tests/test_overlay_coverage.py` green; expected JSON matches computed byte-for-byte.
- [ ] T7 complete

**Phase 2 checkpoint:** overlays compute deterministically; self-test + parity green.
- [ ] Phase 2 checkpoint passed

---

## Phase 3 — Reporting (branded)

### T8: Port overlay render functions
**Files:** modify the report renderer — add overlay render helpers (tabs, stat tiles, grouping heatmap, reverse-lookup JS, control table, honesty lists) from kit `render_overlay_report.py`.
**Verification:** renderer emits an overlay HTML from the golden fixture; opens without JS errors (console clean).
- [ ] T8 complete

### T9: Apply Limen brand tokens
**Files:** modify renderer + `assets/`/`brand.md` — replace the neutral palette CSS custom properties with Limen brand tokens; keep coverage as a **sequential ordinal ramp** and every cell carries the band word (never color-alone).
**Verification:** rendered HTML references brand token vars, not raw neutral hex; band words present on all cells.
- [ ] T9 complete

### T10: Validate the branded coverage ramp
**Files:** none (validation step). Run the dataviz validator on the Limen coverage ramp.
**Implementation notes:** `node validate_palette.js "<4 brand blues>" --mode light --ordinal` and `--mode dark` against the brand surfaces; if any FAIL, re-step to the nearest passing brand ramp step.
**Verification:** validator prints ALL CHECKS PASS for light and dark.
- [ ] T10 complete

### T11: Integrate overlay sections + disclaimers
**Files:** modify renderer + `references/report-layout.md` — expose overlays as (a) a standalone overlay report and (b) an optional appendix in the 9-section report. Every overlay view carries "derived from your CSF assessment — not an audit/certification" + the non-affiliation footer; authority tag per overlay.
**Verification:** screenshot all three overlay tabs (headless chromium); confirm disclaimers, authority tags, honesty lists, natural-sorted controls, verbatim 800-53 titles / CAC ISO-CIS labels.
- [ ] T11 complete

**Phase 3 checkpoint:** branded overlay report renders; ramp validated; disclaimers present.
- [ ] Phase 3 checkpoint passed

---

## Phase 4 — Skill surface

### T12: SKILL.md overlay verbs + triggers
**Files:** modify `SKILL.md` — add workflows: "view/report my Profile through ISO 27001 / CIS / 800-53" (forward coverage) and "what CSF sits behind <control id>" / "which CSF is under ISO A.8.9" (reverse/auditor). State overlays are chosen at report time — **no re-assessment** — and are derived, not an audit/cert.
**Verification:** SKILL.md documents both verbs; contains no audit/certification claim; references the derived-not-audit disclaimer.
- [ ] T12 complete

### T13: Document authority, honesty, selection
**Files:** modify `SKILL.md` + `references/report-layout.md` — document authority tags (nist-developed / cis-authored / mixed-third-party), the honesty lists (outside-CSF, not-in-lens), and that ISO/CIS show CAC labels while 800-53 shows verbatim titles.
**Verification:** docs match renderer output field-for-field.
- [ ] T13 complete

**Phase 4 checkpoint:** skill documents overlays end-to-end.
- [ ] Phase 4 checkpoint passed

---

## Phase 5 — Evals, polish, runbook

### T14: Trigger-accuracy eval set
**Files:** create `evals/overlay_triggers.jsonl` — positives (overlay coverage asks, reverse-lookup asks) and negatives (plain CSF assessment asks that must NOT invoke overlay mode).
**Verification:** trigger-accuracy runner meets the skill's existing threshold; no negative misfires.
- [ ] T14 complete

### T15: End-to-end eval
**Files:** create `evals/overlay_e2e.md` — golden `.csfa` → render all three overlays → assert headline numbers + run `validate_crosswalks.py` (guards against legal leakage in CI).
**Verification:** e2e passes; validator green inside the eval.
- [ ] T15 complete

### T16: Data-refresh runbook
**Files:** modify `references/crosswalks/README.md` (or `build/README.md`) — document: re-download the CSF 2.0 reference xlsx → `python build/author_catalogs.py` → `validate_crosswalks.py` → diff → commit, with `retrievedAt`/version staleness stamps.
**Verification:** following the runbook against the bundled `_source_csf2.xlsx` reproduces the current `references/crosswalks/` data byte-for-byte.
- [ ] T16 complete

### T17 (optional): Completeness upgrades
**Files:** extend `cis-8.1.catalog.json` to the full 153 safeguards (CAC labels) so CIS gets its own "outside-CSF" honesty list; (optional) per-overlay targets.
**Verification:** validator green; CIS `completeness.controlsOutsideCSF` non-empty.
- [ ] T17 complete

---

## Final verification
- [ ] Full `nist-csf` self-test + all evals passing
- [ ] Overlay report renders all three lenses with disclaimers, authority tags, honesty lists
- [ ] `validate_crosswalks.py` green in CI; no verbatim ISO/CIS leakage
- [ ] `.csfa` schema + existing CSF math unchanged (diff shows additive only)
- [ ] Design success criteria met: one assessment, three lenses, bidirectional, ID-only ISO/CIS

## Known risks & mitigations
- **Brand ramp fails dataviz validation** → T10 re-steps to nearest passing brand step (pure color change).
- **Engine port drifts from `.csfa` model** → T7 parity fixture catches it before merge.
- **CIS partial catalog (49/153)** → honesty note in report; T17 completes it if the CIS outside-CSF list is wanted.
- **NIST refreshes the crosswalk** → T16 runbook + staleness stamps make re-ingest a one-command diff.

## Rollback plan
Fully additive: `references/crosswalks/` + `build/` + overlay functions in `profile_analysis.py` + overlay render functions + SKILL.md overlay section + `framework-abstraction.md` edits. Roll back = remove the crosswalks dir + build dir, revert the additive engine/renderer/SKILL.md blocks. Core CSF assessment, `.csfa` schema, and `score_register.py` are untouched.

*A Cyber Aware Creation · Not affiliated with NIST, ISO, or CIS.*
