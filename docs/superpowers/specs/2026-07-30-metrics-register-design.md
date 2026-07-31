# metrics-register Skill — Design Spec

**Date:** 2026-07-30
**Status:** Design draft. Fourth skill for the `cyber-aware-creations` plugin (currently shipped at **v0.5.1**). First of the "board-pack section producers" (#2 in the next-skills sequence 2→3→4→1).
**Product family:** Cyber Aware Creations (CAC) / Limen Labs
**Part of:** `cyber-aware-creations` (alongside `risk-register`, `nist-csf`, `ciso-board-translation`)
**Companion to:** `content/translation-series-backbone.md` (the metric substance), `strategy/cac-plugin-design-2026-07-26.md`, `strategy/nist-csf-skill-design-2026-07-26.md`, `research/feasibility-kill-report-2026-07-18.md` (the guardrails).

---

## 0. Scope reconciliation — READ FIRST

The original "next skills" sketch called #2 a *metrics translator / KRI library* that would "productize the 40-numbers content series into a skill." Inspection of the shipped v0.5.1 plugin changes that framing, and this spec supersedes the sketch:

**Already shipped inside `ciso-board-translation` (do not rebuild):**
- The **seven metric archetypes** — trap, board ask, receipt angle, Grade-A one-liner — in `references/metric-archetypes.md`.
- The **Four Questions** method, the reusable translation template, and worked A/C/F grades in `references/four-questions.md`.
- The **board question bank** and **regulatory receipts** (with honest limits).
- The **board-section output contract** — the `board.json` sidecar (`executiveSummary` / per-item map / `decisions` / `asOf`) consumed today by `nist-csf` and `risk-register` via `render_executive.py --translations board.json`.

**Genuinely missing anywhere in the plugin (this skill's reason to exist):**
- A **system of record for metrics over time.** The plugin has a `.rr` store (risks) and a `.csfa` store (framework posture) — but nothing persists the CISO's board metrics across periods, computes trend/direction deterministically, evaluates threshold breaches, or tags each number to the archetype trap it hides. `ciso-board-translation` is deliberately **stateless** — it translates one number on demand and has "no memory of the last quarter" (its own words). That memory is the gap.

So `metrics-register` is the **third system-of-record**, completing the trio a CISO tracks over time: **risks** (`risk-register`), **framework posture** (`nist-csf`), and now **metrics/KRIs**. It *composes* `ciso-board-translation` for every board-facing sentence and conforms to the existing sidecar contract — it does not re-implement translation.

---

## 1. What this is

A skill that lets a security leader **maintain their board metrics as a living, trended record** — the "40 numbers" as data, not slideware. It persists in a local store, holds each metric's value period over period, computes direction/trend and threshold status deterministically, flags the ones moving the wrong way or going stale, tags each to its archetype trap, cross-links to CSF Subcategories and register risks, and reports to two audiences — routing all board language through `ciso-board-translation`.

Where `risk-register` answers *"what are our top risks and are they within appetite?"* and `nist-csf` answers *"how complete is our program against the framework?"*, `metrics-register` answers *"which of our numbers are moving the wrong way, which ones are lying to us, and what decision does each force?"*

It is the **metrics/KPI section producer** for the eventual board-pack assembler (#1). Building it first proves the section contract on the cheapest, lowest-risk skill.

---

## 2. Architecture

Fourth skill in the monorepo (`skills/metrics-register/`). Structure parallels the existing two stateful skills:

- **SKILL.md** — two core workflows (build/update the register; run a metrics review) + reporting. Neutral-professional voice.
- **`scripts/metrics_analysis.py`** — deterministic engine: trend/direction, threshold evaluation, attention lists, rollups, `self_test`. Same parity discipline as `score_register.py` / `profile_analysis.py`. **Note:** unlike register and csf (which were harvest-parity *ports* of web tools), this is a **greenfield build** — the golden fixture is authored here, not inherited.
- **`references/`** — `schema.md` (the store), `metrics-method.md` (trend/threshold/direction rules), `archetype-bridge.md` (maps each stored metric to the archetype content that already lives in `ciso-board-translation` — a pointer, not a copy), `framework-abstraction.md` alignment notes, `brand.md`, `report-layout.md`.
- **`renderers/`** — `render_operational.py`, `render_executive.py` (the `--translations board.json` flag, metric-keyed), shared `_common.py`. Limen-branded self-contained HTML.
- **`evals/`** — trigger-accuracy set, board-safety guard (inherits the no-confidence-vocabulary rule), a `metric-trend.sh` derivation eval mirroring `confirmation-age.sh`.
- **`examples/`** — a golden `.mtr` fixture + a filled `board.json`.

---

## 3. Scope

**Two core workflows:** (A) build/scope the metric set and record readings; (B) run a **metrics review** — the recurring ritual that ingests the period's numbers, surfaces breaches / worsening / stale / unowned, captures the decision each forces, and reports.

**v1:**
- Stateful store, one register per org, with scope metadata.
- Metric definitions: name, **archetype tag** (one of the seven, or custom/none), unit, **direction** (higher-better / lower-better), thresholds (target / warn / critical), owner, links to CSF Subcategory IDs and register risk IDs.
- **Readings** (append-only, period-stamped values with source + actor).
- Deterministic **trend** (this period vs prior, direction-aware: gaining / holding / slipping), **delta**, and **threshold status** (ok / warn / critical).
- **Attention lists:** breached, worsening, stale (no recent reading), unowned, and **vanity-flagged** (the "big number" trap — e.g. "we blocked 2M attacks").
- **Rollups:** by archetype, by CSF Function (via linked Subcategories), by linked risk/theme.
- **Operational + executive HTML report**; the executive layer composes `ciso-board-translation`.
- **`board.json` section contract** (metric-keyed) so the future assembler ingests it.
- `self_test` golden fixture.

**v2:**
- **Snapshots + diff** ("what changed since last board review") — mirrors register/csf.
- Append-only **definition history** with rationale on material changes (threshold moves, archetype re-tags).
- **Bidirectional KRI↔risk link** with `risk-register` (satisfies register's parked "KRI/metric linkage" v2 line) and **metric↔CSF evidence view** with `nist-csf` ("are our CSF outcomes actually measured?").
- **Import** (CSV / connector-fed readings). Richer target/appetite banding. **True PDF.**

**Parked (clean deferred seams):**
- Automated collection from SIEM / connectors / dashboards.
- Peer benchmarking (kill-report + `ciso-board-translation` guardrail: never invent a benchmark).
- Forecasting / projection of trend.

---

## 4. Data model (the store)

Single local source of truth; dashboards generated on demand, never stored. Proposed extension `.mtr` (open decision — see §9).

Top-level: `schemaVersion`, `family` ("metrics-register"), `meta{clientName, owner, scopeNote, asOf}`, `metrics[]`, `readings[]`, `createdAt`, `updatedAt`. (v2 adds `snapshots[]`, definition `history[]`.)

- **Metric:** `id`, `name`, `archetype` (`patch-coverage` | `phishing-click` | `dwell-time` | `third-party` | `mfa-coverage` | `framework-maturity` | `backup-recovery` | `custom` | `null`), `unit` (`percent` | `count` | `days` | `currency` | `ratio`), **`direction`** (`higher-better` | `lower-better`), `threshold{target?, warn?, critical?}`, `owner`, `csfSubcategoryIds[]`, `riskIds[]`, `vanityRisk` (bool — flags big-number traps), `notes`.
- **Reading (append-only):** `metricId`, `period` (label, e.g. `2026-Q3`), `value`, `source`, `actor`, `ts`, `note`.
- **Derived, never stored:** trend/direction verdict, delta vs prior, threshold status, streak, staleness band, archetype trap text (pulled from `ciso-board-translation`). Consistent with exposure/band (register), gap/coverage (csf), age bands.

Reading/period history is the record; a value is never silently overwritten (a correction is a new reading with a note).

---

## 5. Method — the honesty rules that make it non-generic

The whole point is that a raw metric lies in a specific way. The engine encodes that, deterministically:

- **Direction-aware trend.** "Up" is not "good." A lower-better metric (dwell time, click rate) rising is *slipping*. The verdict is computed against `direction`, never assumed.
- **Threshold status respects direction.** `warn`/`critical` bands evaluate correctly for both polarities.
- **Staleness = distance from a chosen cadence, never confidence.** Reuse the shipped board-safety philosophy verbatim: age is derivable, a decay *rate* is not. No confidence vocabulary reaches a board view; the eval enforces it (inherit `board-safety.sh` checks 9/10).
- **Vanity-trap flag.** Metrics whose shape is a big reassuring number that measures effort, not risk ("2M attacks blocked", "10k alerts triaged") are flagged so a review can down-rank or reframe them.
- **Never invent numbers or benchmarks.** Inherited hard rule from `ciso-board-translation`: the engine computes *only* from stored readings; a missing reading is a visible gap, not an interpolation.

---

## 6. Reporting

- **Operational report** (CISO/team): metric table — value, direction-aware trend arrow, threshold status, archetype, owner, last-reading age; sparkline per metric; attention lists (breached / worsening / stale / unowned / vanity). Archetype and CSF-Function rollups.
- **Executive report** (board): top metrics each run through the **Four Questions** via `ciso-board-translation` (the archetype tag auto-selects the right trap/ask/receipt), trend vs last snapshot (v2), decisions needed. Never hand-rolls board language.
- Self-contained Limen-branded HTML; deliver as files; persist board views as artifacts. Footer: **"A Cyber Aware Creation · Not affiliated with NIST."**

---

## 7. Composition & the section contract (the load-bearing seam)

`metrics-register` is the first skill built *after* the section contract exists, so it **conforms to and extends** the shipped sidecar rather than inventing one.

- **`ciso-board-translation`** — all board prose. Because each metric carries its `archetype` tag, the executive renderer can hand the translation engine both the number *and* the archetype, so it pulls the exact trap/ask/receipt without guessing.
- **Board-section object** — `render_executive.py --translations board.json`, same envelope as register/csf, with a **metric-keyed** per-item map:

```json
{
  "executiveSummary": "One paragraph of posture across the tracked metrics, with a through-line and a trend.",
  "metrics": {
    "M-004": "One board sentence: the exposure behind this number, in the board's language.",
    "M-011": "One sentence — direction-aware, ends implying a decision."
  },
  "decisions": ["Fund phishing-resistant MFA for finance, or record acceptance that one click can reach the payment system."],
  "asOf": "2026-10-01"
}
```

  Same rules as the existing sidecar: one sentence per key, nested map (a flat map silently reverts to placeholders), guardrails still apply. This makes `metrics-register` a drop-in section for the **board-pack assembler (#1)** — the assembler ingests `metrics.board.json` next to `risks.board.json` and `gaps.board.json` with zero re-plumbing.

- **`risk-register`** — a metric can be the leading indicator for a risk (`riskIds[]`); the bidirectional link ships v2 and closes register's parked "KRI/metric linkage."
- **`nist-csf`** — metrics tagged to Subcategories enable a "which CSF outcomes are actually measured?" evidence view (v2).

---

## 8. Testing

- **Deterministic core:** `self_test` asserts trend/direction, threshold status, staleness banding, and rollup math against an authored golden `.mtr` fixture (byte-parity discipline from the other two engines). A `metric-trend.sh` eval derives trend/breach through the same Context the renderers use, over a register built by real commands (mirrors `confirmation-age.sh`, with the same anti-vacuity rules).
- **Board-safety:** inherit checks 9/10 (no confidence vocabulary; honest-risk-statement vs confidence-claim distinction) over the executive view.
- **Skill behavior:** full skill-creator eval loop (with-skill vs baseline via subagents), trigger-accuracy set + description optimizer.
- **Trigger boundary (critical — §9 #6).** `metrics-register` and `ciso-board-translation` both fire on "metric for the board." The disambiguation the eval must pin: *one-shot "translate this 87%"* → `ciso-board-translation` (stateless); *"track / add this quarter's numbers / show metric trends / build the metrics section"* → `metrics-register` (stateful). Descriptions must make this boundary sharp so they don't cannibalize each other.

---

## 9. Open decisions (RESOLVED 2026-07-30)

1. **Skill name** → **`metrics-register`** (confirmed).
2. **Store extension** → **`.mtr`** (confirmed).
3. **Standalone skill vs. module of `risk-register`** → **standalone** (confirmed): metrics are cross-cutting (they map to *both* CSF Subcategories and risks); the register *links* to them.
4. **Period model** → **arbitrary dated readings with a `period` label** (confirmed).
5. **Seed archetypes as starter templates?** → **yes** (confirmed): offer the seven as one-command starter metric definitions.
6. **Metric-keyed sidecar shape** → confirm against `ciso-board-translation`'s renderer flag convention during Phase 0 / build (trivial extension).

---

## 10. Guardrails (bake in)

- Compose `ciso-board-translation` for every board sentence; never hand-roll board language.
- Never invent numbers or benchmarks; a missing reading is a visible gap.
- Direction-aware always; "up" is never blindly "good."
- Staleness is age/cadence-distance, never confidence; no confidence vocabulary in board views (enforced).
- End every executive item on a decision (fund / accept) — inherited from the Four Questions.
- Footer + disclaimer on all outputs. Neutral, publishable voice; no individual's personal style.

---

## 11. Sequence note

This is #2 of 2→3→4→1. It is the ideal first build because the section contract already exists (proven by two consumers), its content dependency (`ciso-board-translation` + the seven archetypes) already ships, and it is the lowest-risk place to validate the metric-keyed sidecar the board-pack assembler (#1) will later ingest. #3 (`exceptions-register`) and #4 (`incident-materiality`) follow the same section-producer pattern; #1 assembles all three plus register + csf.

---

*A Cyber Aware Creation · Not affiliated with NIST.*
