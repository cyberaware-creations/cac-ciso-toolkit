# Cyber Aware Creations — Brand System & Rebrand

**Date:** 2026-08-04 · **Plugin:** `cyber-aware-creations` v0.12.0

> **⚠ Corrections — read before implementing (this doc was written before two later findings):**
> 1. **Do NOT create `skills/_shared/brandkit.py`.** §2 Phase 1 below proposes a shared module. The repo has an explicit, documented rule against cross-skill imports — every skill vendors its own `_common.py` because "every shipped script must run standalone." **Vendor `cac_graphics.py` per skill instead** and add a drift check to `tools/check-versions.py`. See the implementation plan, Conventions §1.
> 2. **The neutral/measure colour is now data blue `#2E6FA7`** (track `#D8E4F1`), not slate and not patina. Patina is **chrome-only** — never a data mark, because the CAC teal sits beside RAG green and a teal bar reads as "good". See `2026-08-04-metric-graphics-standard.md` §2, which is authoritative on colour.

---

## 0. What the audit found

- The **visual system already exists and is good** — accessible palette, Space Grotesk / Manrope type, CVD-safe RAG ramp with measured contrast ratios. It already mirrors the CAC site tokens.
- But it is **named "Limen Labs" internally** (12 references, only in `nist-csf` and `risk-register`) and the token set is called `limen`.
- **No single source of brand truth:** only 2 of 8 skills have `assets/brand.md`; the newer skills inline their own hex values per renderer, so near-duplicate colours drift skill to skill.
- The mark is described as `AnvilMark` but no SVG ships; renderers have no logo or cover.

So this is a **rebrand + consolidation + polish**, not a new colour exercise.

## 1. The brand system

### Palette (token set `cac`, was `limen`)

| Token | Hex | Use |
|---|---|---|
| `ink` | `#14171C` | Dark chrome: cover, header, footer rule |
| `inkRaised` | `#1C2026` | Raised dark surfaces / lines on dark |
| `limestone` | `#EAE7DF` | Light text on ink |
| `limestoneDim` | `#9AA0A6` | Muted text on ink (cover meta, footer stamp) |
| `patina` | `#2FA98C` | **Brand / chrome accent** — kickers, rules, lockup, today marker. **Never a data mark.** |
| `patinaText` | `#1C6F5A` | Patina *as text* on a light surface |
| `patinaTint` | `#E7F3EF` | Patina wash (chip backgrounds, placeholders) |
| `measure` | `#2E6FA7` | **Data blue** — any measure with no declared threshold |
| `measureTrack` | `#D8E4F1` | The track behind a measure fill (gantt planned duration) |
| `slate` | `#666D7C` | Secondary text |
| `muted` | `#4A4F58` | Body-muted text |
| `workbench` | `#F6F4EE` | Light working background |
| `workbenchSurface` | `#FFFFFF` | Cards, tables |
| `workbenchLine` | `#D8D3C6` | Lines on light |

**Load-bearing rule:** `patina` is the brand accent and is **never** used to signal "safe/low risk," and never used as a data mark at all. Risk severity uses the CVD-safe RAG ramp (`#30915B` / `#e8c547` / `#e08e0b` / `#c0392b`). Text-on-fill always goes through `_common.text_on()` — never hand-picked.

### Type
- Display: `'Space Grotesk', system-ui, sans-serif` (titles, numbers, kickers, `dt`)
- Body: `'Manrope', system-ui, sans-serif`
- Mono: `'IBM Plex Mono', ui-monospace, monospace`
- Load from Google Fonts with the system stack as fallback; never block rendering on a font fetch.

### Mark & lockup
- **Mark:** the **patina spark** — a 4-point concave star, inline SVG, no asset dependency:
  `M12 0 L14.6 9.4 L24 12 L14.6 14.6 L12 24 L9.4 14.6 L0 12 L9.4 9.4 Z`
- **Lockup:** `[spark] CYBER AWARE CREATIONS` in Space Grotesk, uppercase, letter-spaced. Light on the ink cover, ink on light footers.
- If a real **AnvilMark** SVG appears later, replace the spark in the vendored library — one change per copy, guarded by the drift check.

### Layout language
- **Cover** (board pack only): full-page `ink` panel — lockup, patina eyebrow, large title, patina rule, meta line, footer. Prints as its own A4 page (`print-color-adjust: exact`).
- **Working views** (operational/executive dashboards): a compact branded **header band** with the lockup, not a full cover.
- **Section chrome:** a short **patina kicker bar** above each card title; summaries as a **patina left-rule lede**.
- **Stat tiles:** white surface, `workbenchLine` border, left accent, big number in Space Grotesk.
- **Decisions:** patina list markers; `from: <section>` as a patina-tint pill.
- **Notes / placeholders:** patina left-border / patina-tint dashed — a placeholder is always visibly unfinished.
- **Footer:** the lockup + `A Cyber Aware Creation · Not affiliated with NIST` on every deliverable.

## 2. Rebrand steps

*(Execution order and verification are in the implementation plan, Phases 1 and 4–5.)*

- **Retire "Limen Labs"** — 12 references across `nist-csf` and `risk-register`: brand-doc headings, token-set name (`limen` → `cac`), doc mentions, example-fixture assessor names, and the provenance comments in `score_register.py`. Verify `grep -ri "limen"` returns nothing.
- **Vendor the graphics library** per skill (not a shared module), with a drift check.
- **Apply the cover + chrome** across renderers; give `pptx_writer.py` a branded title slide and section dividers.
- **Client-brand override:** optional `brand` block / `--brand brand.json` overriding `ink`, `measure`, wordmark and mark. **CAC is the default when absent.** Keep the attribution + NIST disclaimer footer unless the user explicitly white-labels.

## 3. Guardrails

- Accessibility is not cosmetic: keep the measured contrast ratios and `text_on()`; the patina-as-text vs patina-as-fill split (`#1C6F5A` vs `#2FA98C`) must survive consolidation.
- Patina never encodes risk safety and never carries data.
- Footer + "Not affiliated with NIST" on every deliverable; not-legal-advice on incident artifacts.
- Placeholders stay visibly unfinished — branding never dresses up a hole.

---

*A Cyber Aware Creation · Not affiliated with NIST.*
