# Presentation, Indicators & Graphics — Implementation Plan

**Date:** 2026-08-04
**Status:** Ready for execution
**Target repo:** `cyber-aware-creations` (shipped **v0.12.0**, 8 skills)
**Specs (ship alongside, into `docs/superpowers/specs/`):**
- `2026-08-04-cac-brand-system.md` — the CAC brand system + rebrand
- `2026-08-04-executive-indicator-system.md` — the status vocabulary
- `2026-08-04-metric-graphics-standard.md` — the 16-mark catalog, colour contract, selection & consistency rules
- `2026-08-04-metrics-executive-view-review.md` — the P1 bug + the metrics view redesign

**Reference implementation (ship into the repo):** `cac_graphics.py` — 16 marks, `self-test` (34 checks), `gallery` mode.

> **For Claude Code + Superpowers:** execute phase-by-phase with `superpowers:executing-plans`. Steps use `- [ ]`. **Phase 0 is independent and urgent — it can ship on its own.**

---

## Summary

Three strands, one pass: fix a shipped P1 defect in four board renderers; make every deliverable look like Cyber Aware Creations instead of "Limen Labs"; and give every number a *defined, consistent, evidence-based* graphic instead of ad-hoc styling.

## Repo conventions this plan MUST respect

1. **No cross-skill imports.** Every skill vendors its own `_common.py` because "every shipped script must run standalone." The graphics library is therefore **vendored per skill**, with `tools/check-versions.py` extended to assert the copies have not drifted. Do **not** create `skills/_shared/`.
2. **Python 3.9 floor.** CI (`.github/workflows/evals.yml`) pins 3.9 and compiles every shipped `.py`. `cac_graphics.py` is verified 3.9-clean and stdlib-only (`html`, `math`, `sys`) — keep it that way.
3. **Standard library only.** No new dependencies. SVG is emitted as text.
4. **Every engine has a `self-test`; every renderer has an eval.** New behaviour ships with a check, and checks must not be vacuous (assert counts, not just "no exception").
5. **Plans live in `docs/superpowers/plans/`, specs in `docs/superpowers/specs/`.**

## The colour contract (the through-line of the whole plan)

| Role | Colour | Used for |
|---|---|---|
| **Status** | RAG — good `#30915B`, medium `#e8c547`, high `#e08e0b`, critical `#c0392b` | *only* where thresholds or a declared status exist |
| **Measure** | **data blue `#2E6FA7`**, track `#D8E4F1` | any number with no declared limit |
| **Chrome** | **patina `#2FA98C`** | kickers, lockup, cover, today marker — **never a data mark** |

**Colour the mark by what the mark encodes.** A bullet bar *is* a status mark (its position against the zones is the status) → RAG. A gantt bar is a *measure* (duration, % complete) → blue, with the phase status in its own chip. **The library never computes status**: callers pass `sev`; absent `sev` falls back to the measure colour, so "no thresholds, no RAG" is enforced by the default.

---

## Pre-flight
- [ ] All four specs reviewed; `cac_graphics.py self-test` green (34/34)
- [ ] Baseline: every skill's `self-test` and `evals/*.sh` green on the 3.9 floor
- [ ] Branch created

---

## Phase 0 — P1: board renderers print raw Python dicts *(independent; ship first)*

Every producer's sidecar carries `decisions` as objects — `{"text": "...", "altitude": "board"|"management"}` — but four standalone board renderers stringify the whole object, so a board sees:

```
{'text': 'Fund the patching backlog…', 'altitude': 'board'}
```

The `board-pack` assembler normalises to `.text` and is unaffected, which is why this survived: it only shows in a **single skill's own board view** — a primary use case ("build the metrics section for the board"). `board-safety.sh` checks vocabulary, not that decision text is a string.

### T0.1: Fix the four renderers
**Files:** `skills/metrics-register/renderers/render_executive.py` (~L77), `skills/exceptions-register/renderers/render_board.py` (~L69), `skills/incident-materiality/renderers/render_board.py` (~L83), `skills/risk-register/renderers/render_board.py` (~L260).
**Also verify:** `skills/nist-csf/renderers/render_executive.py` `decisions()` — it derives from attention lists *and* appends the sidecar; check the append path.
**Change:** mirror `board-pack/renderers/render_pack.py`:
```python
def dtext(d): return d.get("text") if isinstance(d, dict) else d
board = [d for d in ctx.tr.decisions if not (isinstance(d, dict) and d.get("altitude") == "management")]
mgmt  = [d for d in ctx.tr.decisions if isinstance(d, dict) and d.get("altitude") == "management"]
```
Render `dtext(d)`, and emit a **"Management actions — not for board decision"** block for `mgmt`, as the pack already does.
**Verification:** each skill's executive/board HTML built from its shipped `example-translations.json` contains **no** `{'text'` and no `altitude`; the management block appears where the sidecar has one.
- [ ] T0.1 complete

### T0.2: Add the eval that would have caught it
**Files:** each producer's `evals/board-safety.sh` (or a new `decisions-render.sh`).
**Check:** render with an object-form sidecar and assert the output contains neither `{'text'` nor `'altitude'`, **and** assert the expected decision count appears (a filter matching nothing is green over nothing).
**Verification:** eval fails on the pre-fix renderer, passes after.
- [ ] T0.2 complete

**Phase 0 checkpoint:** all five producers render object-form decisions as prose; new eval green; ship as a patch release.
- [ ] Phase 0 checkpoint passed

---

## Phase 1 — Brand: retire "Limen", vendor the graphics library

### T1.1: Rename Limen → Cyber Aware Creations (12 references)
**Files:** `nist-csf/assets/brand.md` + `risk-register/assets/brand.md` (heading `Limen Labs Brand Tokens` → `Cyber Aware Creations Brand Tokens`; token set `limen` → `cac`); `nist-csf/SKILL.md`; `risk-register/SKILL.md`; `risk-register/references/dashboards.md`; `risk-register/assets/report-layout.md`; fixtures `risk-register/references/example-register.rr` and `nist-csf/examples/acme-manufacturing.csfa` (assessor → `Cyber Aware Creations`); provenance comments in `risk-register/scripts/score_register.py` ("ported from the Limen Labs web engine" → "the Cyber Aware Creations web engine").
**Verification:** `grep -ri "limen" skills/ tools/` returns nothing; `score_register.py self-test` still prints its parity line.
- [ ] T1.1 complete

### T1.2: Add the measure + chrome tokens to the canonical brand doc
**Files:** `risk-register/assets/brand.md` and `nist-csf/assets/brand.md` (and add `assets/brand.md` to the six skills without one, or reference the canonical copy).
**Add:** `measure #2E6FA7` / `measureTrack #D8E4F1`; state that **patina is chrome-only, never a data mark**; record the three measured findings (deuteranopia ΔE 6.2 on green↔red; amber 2.54:1 and yellow 1.64:1 on white; medium↔high ΔE 13.3 and unfixable by darkening — label the band instead).
**Verification:** both brand docs carry identical token tables.
- [ ] T1.2 complete

### T1.3: Vendor `cac_graphics.py` into every skill + add a drift check
**Files:** copy to `skills/<skill>/renderers/cac_graphics.py` for all 8 skills; extend `tools/check-versions.py` with a hash comparison across the copies; canonical source at `tools/cac_graphics.py`.
**Notes:** vendoring is required by the standalone rule (T-conventions §1). The drift check is what makes duplication safe.
**Verification:** `python3 cac_graphics.py self-test` → **34/34** from each vendored copy; `check-versions.py` fails if one copy is edited alone; every copy compiles on 3.9.
- [ ] T1.3 complete

**Phase 1 checkpoint:** no "Limen" anywhere; graphics library vendored, self-testing and drift-checked. Bump minor.
- [ ] Phase 1 checkpoint passed

---

## Phase 2 — `metrics-register` adopts the graphics + brand (the pilot)

### T2.1: Add `viz` to the metric schema
**Files:** `skills/metrics-register/references/schema.md`, `scripts/metrics_analysis.py`.
**Change:** optional `viz` per metric (a catalog id: `bullet|progress|tank|gauge|sparkline|slope|line|column|bar|tile`). When absent, resolve from `archetype` using the defaults table in the graphics spec §6 (patch→bullet, phishing→bullet lower-better, dwell→line, MFA→progress, backup→bullet+age, vanity/volume→**tile, no gauge, no RAG**). Emit the resolved `viz` in `analyze` output so renderers do not re-decide.
**Verification:** `self-test` asserts each archetype resolves to its documented default and an explicit `viz` overrides it.
- [ ] T2.1 complete

### T2.2: Rebuild `render_executive.py` on the library
**Files:** `skills/metrics-register/renderers/render_executive.py`, `_common.py`.
**Change:** CAC chrome (dark header band + lockup, patina kickers, footer lockup); severity-coloured attention tiles (a `0` count stays neutral); per-metric mark selected by `viz`, passed the engine's own `value/threshold/direction/status/trend`; **bullet is the default for anything with a target**; sparkline suppressed under 4 readings; humanised age bands (no raw `wellBeyond`); the §2 legend; decisions fixed per Phase 0.
**Verification:** renders on `examples/example-metrics.mtr`; M-006 breach renders red, M-001/M-003 amber, M-002/M-004 green, M-005 (no threshold) renders **no gauge and no RAG**; missing translation still renders a visible placeholder.
- [ ] T2.2 complete

### T2.3: Same for `render_operational.py`
**Verification:** operational view uses the same marks for the same metrics (consistency rule §6.1) and passes `board-safety.sh`.
- [ ] T2.3 complete

### T2.4: Evals
**Files:** `skills/metrics-register/evals/graphics-contract.sh` (new).
**Checks (anti-vacuity — assert counts, not just absence):** a metric with no threshold emits the measure colour and **zero** RAG fills; a metric in the amber band emits amber in tile, mark and delta; `viz` resolution matches the archetype table for all seven archetypes; sparkline absent at 3 readings and present at 4.
**Verification:** exits 0 with an exact check count; `board-safety.sh` still green.
- [ ] T2.4 complete

**Phase 2 checkpoint:** metrics executive + operational views branded, graphed and contract-checked. Bump minor.
- [ ] Phase 2 checkpoint passed

---

## Phase 3 — Roll the marks across the other producers

Each task: adopt the CAC chrome (compact header band + lockup + footer — **not** a full cover; these are working views) and the marks below. All keep the colour contract.

### T3.1: `risk-register`
Heat matrix (L×I) for the matrix view; stacked bar for band-mix over time; bullet for residual-vs-appetite; bar chart for top risks by exposure (RAG legitimate — risk bands are declared). **Label the band wherever all four appear adjacently** (spec §2, finding 3).
**Verification:** existing register evals green; heat cells and band-mix segments carry a label or value.
- [ ] T3.1 complete

### T3.2: `nist-csf`
Bar by Function for coverage; heat grid for Function × Category; bullet for current-vs-target where a target exists.
- [ ] T3.2 complete

### T3.3: `exceptions-register`
**Milestone timeline or gantt** for expiry + re-validation across the year; overdue renders crit (a real threshold); current/due/overdue chips.
- [ ] T3.3 complete

### T3.4: `incident-materiality`
**Milestone timeline** — discovery → determination → filing → DORA final report, with the **disclosure clock as the today marker**. Only the determination and the filing carry status; other events are data blue. Keep the not-legal-advice line.
- [ ] T3.4 complete

**Phase 3 checkpoint:** every producer view is branded and uses the shared marks; all evals green. Bump minor.
- [ ] Phase 3 checkpoint passed

---

## Phase 4 — `board-pack`: carry status, brand the deliverables, add the marks

### T4.1: Carry per-item status into the pack model
**Files:** `skills/board-pack/scripts/assemble_pack.py`.
**Change:** while reading each producer's store for headline figures, also read the per-item status the engine already computes and attach it — `item.status = {sev, label, arrow}` and `headline.sev`. **The assembler must not compute severity**; it carries what the producer declared, exactly as it does for figures.
**Verification:** `assembly.sh` asserts status is carried for every item that has one and is absent for items that do not; `self-test` count updated.
- [ ] T4.1 complete

### T4.2: Renderer — brand + indicators + marks
**Files:** `skills/board-pack/renderers/render_pack.py`.
**Change:** the CAC cover (dark ink page, spark lockup, eyebrow, patina rule, meta); patina section kickers; the indicator legend; severity-coloured headline tiles; `from:` chips; and the marks — metrics section as **bullets/small multiples**, risk as **heat matrix + band-mix**, a **commitments gantt**, and an **incident timeline** when one occurred.
**Verification:** end-to-end assemble+render on the shipped example stores; `assembly.sh`, `section-contract.sh`, `board-safety.sh` green; placeholder-on-missing still holds.
- [ ] T4.2 complete

### T4.3: PPTX parity
**Files:** `skills/board-pack/scripts/pptx_writer.py`.
**Change:** branded dark **title slide** (lockup, eyebrow, title, patina rule), patina title kickers, spark in the footer; severity colour on the figures slide; **section divider slides**; keep the deck's structural verifier.
**Verification:** `PX.verify` clean; deck opens; title/eyebrow/footer present on every slide.
- [ ] T4.3 complete

### T4.4: Snapshot-alignment + duplicate-decision notes
**Files:** `skills/board-pack/SKILL.md`.
**Change:** two workflow lines surfaced by the dogfood run — snapshot all producer stores to one `asOf` before assembling (the specimen mixes 07-26 and 07-31 and the assembler correctly warns), and a human reconciles any decision the assembler flags as naming the same item twice.
- [ ] T4.4 complete

**Phase 4 checkpoint:** a full branded pack with indicators and marks, HTML + PPTX + PDF, from the example stores. Bump minor.
- [ ] Phase 4 checkpoint passed

---

## Phase 5 — Client brand override + final sweep

### T5.1: `--brand` override
**Files:** `skills/board-pack/scripts/assemble_pack.py` (+ `pack.manifest.json` schema), renderers.
**Change:** optional `brand` block / `--brand brand.json` overriding `ink`, `measure`, wordmark and mark. **CAC is the default when absent.** Keep the `A Cyber Aware Creation · Not affiliated with NIST` footer even under override, unless the user explicitly white-labels.
**Verification:** a manifest with a `brand` block re-colours cover and marks; without one, CAC renders.
- [ ] T5.1 complete

### T5.2: Full sweep
- [ ] All engine `self-test`s green (6 engines + graphics library)
- [ ] All `evals/*.sh` exit 0 with exact counts, on the 3.9 floor
- [ ] `grep -ri "limen"` returns nothing
- [ ] No hardcoded hexes in renderers outside the vendored library / brand tokens
- [ ] Every deliverable carries the footer; incident artifacts carry not-legal-advice
- [ ] Trigger-accuracy sets unchanged and clean
- [ ] `check-versions.py` reports no library drift
- [ ] `plugin.json` version bumped; keywords updated

---

## Known risks & mitigations
- **Library drift across 8 vendored copies** → `check-versions.py` hash check is a release gate, not a convention.
- **3.9 floor** → the library is verified 3.9-clean; CI compiles every shipped `.py` on 3.9. Do not introduce `X | Y` annotations or `match`.
- **Colour regressions** → `cac_graphics.py self-test` (34 checks) encodes the contract; each check exists because a real defect broke it. Extend it rather than reasoning about colour by eye.
- **Yellow↔orange (ΔE 13.3)** → unfixable by hex; enforced by labelling wherever all four bands are adjacent.
- **Scope creep in the assembler** → it carries status, it never computes it; any computation belongs in a producer.

## Rollback
Phase 0 is a self-contained bug fix. Phases 1–5 are additive: the vendored library is a new file per skill, brand changes are text/tokens, and renderer changes are revertible per skill. No store schema changes except the optional `viz` field, which is backward-compatible (absent → resolved from archetype).
