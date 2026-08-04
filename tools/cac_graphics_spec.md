# CAC Graphics Library — Implementation Specification

This document records the exact design decisions made when implementing `tools/cac_graphics.py`.
Use it to compare any alternative implementation and identify gaps or divergence.

---

## Overview

- **File**: `tools/cac_graphics.py`
- **Language**: Python 3.9+ (no walrus operator ``:=``, no ``X | Y`` union types, no ``match`` statement)
- **Dependencies**: stdlib only — ``html``, ``math``, ``sys``
- **Marks**: 16 SVG-returning functions + `zones_from_threshold()` adapter
- **Surface**: every mark opens with an opaque white rect; the palette is validated light-only
- **CLI modes**:
  - ``python3 cac_graphics.py self-test`` — runs 53 assertions, exits 0 on pass
  - ``python3 cac_graphics.py gallery <output.html>`` — writes a full-page HTML gallery

---

## Brand Tokens

```python
# Four variants per RAG band:
#   fill  — saturated; for bars, dots, strokes where the mark IS the status
#   text  — dark, accessible (WCAG AA); chip labels and value labels on tint
#   tint  — pale; chip/badge backgrounds; never on data marks
#   mid   — desaturated zone band; replaces opacity compositing in bullet zones
_RAG = {
    "good":     {"fill": "#30915B", "text": "#25764A", "tint": "#E3EDE4", "mid": "#86BE9C"},
    "medium":   {"fill": "#e8c547", "text": "#7A6410", "tint": "#FBF3D6", "mid": "#F0DC92"},
    "high":     {"fill": "#e08e0b", "text": "#8F5B06", "tint": "#F7EBD9", "mid": "#EEC17E"},
    "critical": {"fill": "#c0392b", "text": "#8B2119", "tint": "#F6E0DC", "mid": "#DFA096"},
}
_MEASURE       = "#2E6FA7"   # data without thresholds
_MEASURE_TRACK = "#D8E4F1"   # track/background for MEASURE fills
_PATINA        = "#2FA98C"   # chrome only — today lines, brand accent
_INK           = "#14171C"   # primary text, milestone diamonds
_MUTED         = "#4A4F58"   # secondary text, axis labels
_BG            = "#F6F4EE"   # brand workbench background

_FONT_DISPLAY  = "'Space Grotesk',system-ui,sans-serif"   # numbers, kickers
_FONT_BODY     = "'Manrope',system-ui,sans-serif"          # labels, prose
```

### Why the four variants exist (the three measured findings)

1. **RAG green↔red is ΔE 6.2 under deuteranopia** — colour alone cannot distinguish bands. Every band always pairs colour with a word.
2. **Amber (`#e08e0b`) is 2.54:1 on white; medium yellow is 1.64:1** — both below the 3:1 relief floor. White text on these fills is prohibited. The `text` variant (dark, accessible) resolves this.
3. **Medium↔high is ΔE 13.3 and cannot be fixed by darkening** — wherever all four bands appear together (heat matrix, stacked bar), every cell/segment must carry a visible label. The `mid` zone tones are fixed; do not "improve" the brand hexes.

### Chip rendering rule

Chips use **`tint` background + `fill` dot + `text` label**. Never a saturated fill with white text.
Rationale: amber and yellow fills fail WCAG AA at any text size. The tint+dot pattern passes for all four bands without exception.

### The governing colour rule

> **Colour the mark by what the mark itself encodes.** A bullet bar *is* a status mark — its position against the zone bands *is* the status — so it takes RAG fill. A gantt bar is a *measure* — length encodes duration and % complete, neither of which has a threshold — so it stays MEASURE blue, and the phase's health (a separate human judgement) gets its own chip.
>
> Test: *does the mark's own value determine the status?* Yes → colour the mark. No → give the status a separate indicator and leave the measure blue.

### `fill` vs `mid` — single values vs regions

A second question decides which *variant* a RAG mark takes:

- **`fill` (saturated)** — the mark is a **single value**: a KPI accent stripe, a chip dot, a bullet bar, a bar-chart bar, a line/sparkline stroke, a milestone dot, a gauge needle.
- **`mid` (desaturated)** — the mark is a **region**: a bullet zone band, a heat-matrix cell, a stacked-bar segment, a gauge zone arc.

Regions are large areas that carry a text label on top, so they must be light enough for the band's `text` colour to sit on them. That is also why no mark composites `opacity`: an opacity-blended colour is not the colour any contrast check validated.

### `zones` is direction-dependent

> Under `higher`, `(t, s)` means *values **below** `t` are `s`*.
> Under `lower`, `(t, s)` means *values **at or above** `t` are `s`*.

Any code that paints bands must ask `_zone_sev()` what a mid-band value scores rather than reading the list positionally. Painting from the `higher` reading silently inverts every lower-better mark — green lands at the bad end and the bar contradicts its own bands. `bullet()` and `radial_gauge()` both derive bands this way; check 44 asserts it across 40 samples in both directions.

---

## Colour Contract (Three-Way Split)

| Bucket | Colour | Rule |
|--------|--------|------|
| **RAG** | good / medium / high / critical | Status only. Used **exclusively** where a threshold or declared severity exists. Never inferred from sign, direction, or magnitude alone. |
| **MEASURE** | `#2E6FA7` + track `#D8E4F1` | Default data colour. Used whenever no threshold or sev is present. |
| **PATINA** | `#2FA98C` | Chrome only — today lines, milestone markers, decorative accents. **Never encodes data or risk.** |

### Enforcement rules tested in self-test

1. **Delta never coloured by sign** — a positive delta on a KPI tile must not emit green; a negative delta must not emit red.
2. **`fuel_tank()` can never emit RAG** — it has no `sev` parameter by design.
3. **`column_trend()` can never emit RAG** — it has no `sev` parameter by design.
4. **`stacked_bar()` segments never use `_PATINA`** — patina is chrome only.
5. **`sparkline()` returns a note SVG (not `""`) when fewer than 4 readings** — placeholder-beats-silence: visible, not an empty string.
6. **`gantt()` bars are always MEASURE** — bar fill is never RAG regardless of chip status.
7. **`radial_gauge()` large-arc-flag is always 0** — a 180° half-gauge arc never exceeds a semicircle.
8. **`rag_chip()` medium and high bands never use white text** — `text` variant (dark) required; tested at checks 35–38.
9. **No `opacity` compositing** — bullet zones use `mid` hex fills directly; opacity on colours is not validated by colour-pair checks.
10. **Regions use `mid` + the band's `text` colour** — heat-matrix cells and stacked-bar segments are regions, not single values. White on `good` `#30915B` is 3.9:1, under the floor; `text` on `mid` passes for all four bands. Tested at checks 49–50.
11. **No mark emits `opacity=`** — asserted across every mark, not one example (check 41).
12. **No mark leaks a Python repr into an attribute** — asserted across every mark (check 40). The token model went `str` → `dict`; two call sites kept indexing it directly and emitted `fill="{'fill': '#e08e0b', ...}"`, an invalid paint that the browser silently drops. Every RAG lookup goes through `_sev_colour(sev, variant)`.
13. **No white text on any light RAG ground** — asserted across every mark (check 42).
14. **Every mark opens with a surface rect** — asserted across every mark (check 43).
15. **Colour assertions are quote-delimited** — `'fill="#e08e0b"'`, never a bare `"#e08e0b"`. A bare hex substring matched *inside the leaked dict*, so the suite reported 44/44 green on a mark that rendered with no colour at all.

---

## Gantt Chip Vocabulary

Maps severity to the executive indicator vocabulary from the EIS spec:

```python
_GANTT_CHIP = {
    "good":     "ON TRACK",
    "medium":   "WATCH",
    "high":     "AT RISK",
    "critical": "LATE",
}
```

---

## Helper Functions

### `_normalize_direction(direction)`

Accepts `"higher"` / `"higher-better"` → `"higher"`, and `"lower"` / `"lower-better"` → `"lower"`.
Raises `ValueError` on any other string. Called by `_zone_sev()` and `bullet()`.
The metrics engine emits `"higher-better"` / `"lower-better"`; both spellings are accepted.

### `_validate_iso(d, context="")`

Raises `ValueError` if `d` is not a recognisable ISO date string (`YYYY-MM` or `YYYY-MM-DD`).
Called at gantt date collection time — malformed dates raise rather than silently producing 0-width bars.

### `zones_from_threshold(threshold, direction)`

Converts the engine's threshold dict to the `[(value, sev), ...]` list expected by `bullet()` and `_zone_sev()`.

```python
# threshold = {"target": x, "warn": y, "critical": z}
# direction = "higher-better" | "lower-better" (or without -better suffix)
zones = zones_from_threshold({"target": 90, "warn": 75, "critical": 60}, "higher-better")
# → [(60, "critical"), (75, "high"), (90, "medium")]
```

This adapter exists so the mapping is defined once and tested once, not rebuilt inconsistently in each renderer.

---

## Zone / Bullet Logic

```python
def _zone_sev(value, zones, direction="higher"):
```

- `zones` = `[(threshold_value, sev), ...]`.
- Direction normalised via `_normalize_direction()` — accepts `"higher-better"` etc.
- `direction="higher"`: iterates thresholds ascending; returns the sev of the first threshold the value does **not** exceed. Default = `"good"` if value exceeds all thresholds.
- `direction="lower"`: iterates thresholds descending; returns sev of the first threshold the value **meets or exceeds**. Default = `"good"` if value is below all thresholds.

---

## The 16 Mark Functions

### 1. `kpi_tile(value, label, delta="", unit="", sev="", delta_sev=None)`

- **Canvas**: 200 × 110 px.
- **Left accent stripe**: 4 px wide, full height. Colour = `_RAG[sev]["fill"]` if sev, else `_MEASURE`.
- **Value text**: 32 px, `_FONT_DISPLAY`, weight 700, `_INK`.
- **Delta text**: `_RAG[delta_sev]["text"]` if `delta_sev` provided, else `_MUTED`. **Never coloured by sign.**
- **Label text**: 12 px, `_FONT_BODY`, `_MUTED`.

### 2. `rag_chip(sev, label)`

- **Canvas**: auto-width × 24 px.
- **Background pill**: `rx=12`, fill = `_RAG[sev]["tint"]`.
- **Dot**: `r=4`, fill = `_RAG[sev]["fill"]`. Positioned left of the label.
- **Label**: 12 px, `_FONT_BODY`, weight 600, fill = `_RAG[sev]["text"]`.
- Returns `""` if `sev` not in `_RAG`.

### 3. `bullet(value, target, zones, direction="higher", unit="", labels=True, axis_max=None)`

- **Canvas**: 280 × 70 px.
- **Zone bands**: drawn with `_RAG[s]["mid"]` fill — no opacity compositing.
- **White measure lane**: full-width rect punched through the zones so the bar edge stays crisp.
- **Value bar**: inside the lane, height 10 px, `rx=2`, fill = `_RAG[bar_sev]["fill"]`.
- **Value label**: above the bar tip, 10 px, fill = `_RAG[bar_sev]["text"]`.
- **Target tick**: white halo (`stroke-width=5`) under ink stroke (`stroke-width=2.4`), so the tick reads through a passed bar.
- **Axis max label**: suppressed when `target / scale_max ≥ 0.88` to avoid collision.
- **`axis_max`**: explicit scale ceiling. Pass `100` for percent metrics to make metric-wall comparisons valid. Defaults to `max(thresholds, value, target) × 1.1` which **breaks comparability** across multiple bullet marks.

### 4. `progress_bar(value, goal, label="", sev="")`

- **Canvas**: 280 × 50 px.
- **Track**: full width, height 16, `rx=8`, fill `_MEASURE_TRACK`.
- **Fill**: fill = `_RAG[sev]["fill"]` if sev else `_MEASURE`.

### 5. `fuel_tank(value, goal, label="")`

- **Canvas**: 80 × 140 px.
- **Fill**: always `_MEASURE`. **No `sev` parameter** — cannot emit RAG by design.

### 6. `radial_gauge(value, min_v, max_v, zones=None, sev="", direction="higher", target=None, unit="")`

- **Canvas**: 200 × 132 px. Centre (100, 96), r = 72. **large-arc-flag always 0.**
- **Zone arcs**: `mid` tones, derived from `_zone_sev()` per band — same construction as the bullet. `stroke-linecap="butt"` (round overhangs the track end at 100% and leaves a stub near 0).
- **Needle**: tapered polygon from the hub shoulders to the tip, in the band's `fill`. Hub disc + surface-coloured centre.
- **Target tick**: white halo under an ink stroke, crossing the band.
- **Value + status word**: *below* the hub. Inside the arc they collide with it.
- Use once per report. Not for comparison across metrics — use a bullet wall.

### 7. `sparkline(readings, unit="", sev="")`

- Returns a **note SVG** ("≥4 readings needed") if `len(readings) < 4`. Never returns `""`.

### 8. `slope(readings, labels=None, unit="", sev="")`

- Exactly 2 readings. Returns `""` if not exactly 2.

### 9. `line_chart(readings, labels=None, unit="", sev="")`

- ≥4 readings. Returns `""` if fewer.

### 10. `column_trend(readings, labels=None, unit="")`

- **No `sev` parameter** — always `_MEASURE`. Cannot emit RAG by design.

### 11. `bar_chart(items)`

- `items` = `[(label, value)]` or `[(label, value, sev)]`.
- Fill = `_RAG[sev]["fill"]` if sev, else `_MEASURE`.

### 12. `heat_matrix(cells, row_labels=None, col_labels=None)`

- `cells[i][j]` = `{"sev": ..., "label": ...}` or `None`.
- Fill = `_RAG[sev]["fill"]` at 0.85 opacity if sev, else `_MEASURE`.
- **Text colour**: white for `good` / `critical` fills (dark enough); `_RAG[sev]["text"]` for `medium` / `high` (too light for white).
- **Mandatory labelling**: ΔE 13.3 between medium and high means all four-band displays must carry cell labels.

### 13. `stacked_bar(periods)`

- `periods` = `[{label, segments: [{sev, value}]}]`.
- Fill = `_RAG[sev]["fill"]` if sev, else `_MEASURE`. **`_PATINA` is never a segment fill.**
- **Mandatory value labels**: printed inside segments when segment height ≥ 14 px. Text colour: white for good/critical, `_RAG[sev]["text"]` for medium/high.

### 14. `small_multiples(metrics, mark_fn, axis_max=None)`

- Grid of the same mark, 3 columns max. `mark_fn(metric)` → SVG string.
- `axis_max` is merged into every metric dict before `mark_fn` sees it. Without a shared ceiling each bullet auto-scales to its own data and the wall stops being comparable — which is the only reason to build a wall.

### 15. `milestone_timeline(events, today="")`

- `events` = `[{label, date, sev=""}]`. Dates validated by `_validate_iso()`.
- **Canvas**: 520 × 152 px, `max-width:100%`.
- **Orientation**: horizontal, **x proportional to date** via `_date_ord()`.
- **Labels**: alternate above/below the axis so near dates do not collide.
- **Dots**: `r=6`, band `fill` if sev else `_INK`, with a surface-coloured stroke so they read against the axis.
- **Today**: *vertical* `_PATINA` dashed line + "TODAY" caption.

The proportional spacing is the mark's whole value: on an incident timeline, determination → filing at 3 days and the DORA final report a month out must *look* that way. Evenly spaced rows make them identical, which turns a chronology into a changelog — and stops it matching the gantt's time axis when both sit on one page.

### 16. `gantt(phases, today="", milestones=None)`

- `phases` = `[{label, start, end, pct=1.0, sev=None}]`
- `milestones` = `[{label, date}]` — rendered as `_INK` diamonds.
- `today` = ISO date string — validated via `_validate_iso()`, then rendered as `_PATINA` dashed vertical line.

**Canvas layout** (w=568):
- `label_col_w = 110`, `bar_col_w = 326`, `pct_col_w = 32`, `chip_col_w = 92`

**Bar rendering**: track = `_MEASURE_TRACK`, fill = `_MEASURE` × pct. **Never RAG.**

**Status chip**: `tint` background + `fill` dot + `text` label (9 px, weight 600). Pattern: `dot + word`, not `saturated pill + white text`.

**Date validation**: `_validate_iso()` raises `ValueError` on malformed dates. No silent 0-width bars.

---

## Self-Test (53 checks)

Run with `python3 cac_graphics.py self-test`.

| # | What is checked |
|---|----------------|
| 1 | `kpi_tile` no-sev emits no RAG fill |
| 2 | `kpi_tile` sev=critical emits `#c0392b` |
| 3 | `kpi_tile` positive delta does NOT emit green |
| 4 | `kpi_tile` negative delta does NOT emit red |
| 5 | `progress_bar` no-sev emits no RAG |
| 6 | `progress_bar` sev=critical emits `#c0392b` |
| 7 | `fuel_tank` emits no RAG |
| 8 | `column_trend` emits no RAG |
| 9 | `column_trend` emits `_MEASURE` |
| 10 | `sparkline` <4 readings returns note SVG (not `""`, not a polyline) |
| 11 | `sparkline` ≥4 readings returns non-empty SVG |
| 12 | `sparkline` sev=medium emits `#e8c547` |
| 13 | `slope` sev=medium emits `#e8c547` on a declining series |
| 14 | `bullet` value in high zone → high fill |
| 15 | `bullet` value in crit zone → crit fill |
| 16 | `bullet` lower-better high value → crit fill |
| 17 | `heat_matrix` sev=critical → `#c0392b` |
| 18 | `heat_matrix` no-sev → `_MEASURE` |
| 19 | `stacked_bar` critical segment → `#c0392b` |
| 20 | `stacked_bar` no `_PATINA` in segment fills |
| 21 | `milestone_timeline` no-sev event → no RAG |
| 22 | `milestone_timeline` sev=high → `#e08e0b` |
| 23 | `milestone_timeline` today → `_PATINA` |
| 24 | `gantt` → `_MEASURE` present |
| 25 | `gantt` no phase status → no RAG |
| 26 | `gantt` sev=good → RAG dot + "ON TRACK" label |
| 27 | `gantt` today → `_PATINA` |
| 28 | `rag_chip` good → `#30915B` (dot fill) |
| 29 | `rag_chip` critical → `#c0392b` (dot fill) |
| 30 | `column_trend` → no `_PATINA` |
| 31 | `bar_chart` no-sev → `_MEASURE` |
| 32 | `bar_chart` sev=critical → `#c0392b` |
| 33 | `radial_gauge` large-arc-flag is 0 |
| 34 | `line_chart` sev=high → `#e08e0b` |
| 35 | `rag_chip` medium → no `#FFFFFF` text |
| 36 | `rag_chip` high → no `#FFFFFF` text |
| 37 | `rag_chip` medium → dark text `#7A6410` |
| 38 | `rag_chip` high → dark text `#8F5B06` |
| 39 | `gantt` chip medium → no `#FFFFFF` |
| 40 | **No mark leaks a dict repr into an attribute** (all marks) |
| 41 | **No mark emits `opacity=`** (all marks) |
| 42 | **No white text on any light RAG ground** (all marks) |
| 43 | **Every mark opens with a surface rect** (all marks) |
| 44 | **Bullet bands agree with `_zone_sev`** — 40 samples, both directions |
| 45 | `radial_gauge` `zones=` branch paints a needle in the band colour |
| 46 | `milestone_timeline` `sev=` paints a real dot fill |
| 47 | `progress_bar` % label clears the track |
| 48 | Four-band bullet ticks its zone boundaries |
| 49 | `heat_matrix` medium cell → `mid` ground + band `text` |
| 50 | `stacked_bar` high segment → `mid` ground + band `text` |
| 51 | `bullet` zones → no `opacity` attribute |
| 52 | `bullet` accepts `direction="higher-better"` |
| 53 | `_zone_sev` accepts `direction="lower-better"` |

---

## Decisions Recorded (previously open)

- **Milestone timeline** — horizontal and date-proportional. Settled; see Mark 15.
- **Radial gauge** — needle dial with zone arcs, target tick and status word. A plain fill arc is a bent progress bar and duplicates `progress_bar()`. Settled; see Mark 6.

---

## Known Gaps

- **Light-only palette.** Every mark carries an opaque `#FFFFFF` surface and any page embedding them must declare `<meta name="color-scheme" content="light">`. The `text` variants are dark-on-light by construction. A dark theme needs `validate_palette.js --mode dark` re-run and a separate `text-dark` variant per band before it exists — do not ship one by inverting.
- **Tooltip / interactivity** — all marks are static SVG; no hover states or data-attributes.
- **Accessibility** — no `<title>` or `<desc>` elements. Colour is supplemented by text labels, not `aria-*`.
- **Responsive scaling** — wide marks (gantt, milestone timeline) carry `max-width:100%;height:auto`. Others need the caller to scale via CSS.
- **`small_multiples` height** — top-aligned, not centred, when marks differ in height.
- **`_date_ord` is approximate** — 30.44-day months. Fine for positioning at the scale these marks are read; not a calendar.
