# CAC — Executive Indicator System (colour, carefully)

**Date:** 2026-08-04 · Companion to `2026-08-04-cac-brand-system.md` and `2026-08-04-metric-graphics-standard.md`.
**Goal:** let an executive grasp *what needs their attention* in seconds, without turning a board pack into a rainbow.

> **⚠ Correction:** the `neutral` row in §2 originally used slate `#666D7C`. Slate **fails** the validator against RAG green (ΔE 14.3, below the 15 floor) and fails the chroma floor — it "reads gray". The no-threshold colour is now **data blue `#2E6FA7`**. `2026-08-04-metric-graphics-standard.md` §2 is authoritative on colour; this doc is authoritative on the *vocabulary* (chips, arrows, which producer field maps to which state).

---

## 1. The discipline (what makes it "careful")

1. **Colour only ever carries meaning** — severity, threshold status, or direction. Never decoration.
2. **Never colour alone.** Every colour is paired with a word or an arrow, so it survives colour-blindness, greyscale printing, and a projector that eats saturation (WCAG 1.4.1). This is not stylistic: RAG green↔red measures **ΔE 6.2 under deuteranopia**, which is inherent to any traffic-light ramp.
3. **Patina stays chrome, never "good."** Severity uses the CVD-safe RAG ramp only.
4. **Management by exception.** Red and amber mark what needs a decision or a watch; everything else stays neutral. If everything is coloured, nothing is.
5. **The producer declares status; the renderer maps it.** Severity is never inferred from prose — it comes from the engine that computed it. Same rule as the assembler: *declare, never infer.*

## 2. The vocabulary

| Sev | Meaning | Fill | Text | Tint |
|---|---|---|---|---|
| `crit` | Needs a decision | `#c0392b` | `#C0392B` | `#F6E0DC` |
| `high` | Watch / act soon | `#e08e0b` | `#8F5B06` | `#F7EBD9` |
| `medium` | Watch | `#e8c547` | `#7A6410` | `#FBF3D6` |
| `good` | Within tolerance | `#30915B` | `#25764A` | `#E3EDE4` |
| *(no status)* | Not a judgement | **`#2E6FA7`** (measure) | `#4A4F58` | — |

**Indicators:** a **chip** (tinted pill + UPPERCASE word) and a **direction arrow** (`↑` improving, `↓` slipping, `→` steady — coloured, but the glyph itself is the non-colour signal). One legend defines the code on the first content page.

**Mapping — from fields the engines already emit:**

| Producer | Field | → chip / arrow |
|---|---|---|
| `risk-register` | `residualBand` + `overAppetite` | `CRITICAL`/`HIGH`/`MEDIUM`/`LOW` (+ `· OVER APPETITE`); over-appetite never renders neutral |
| `metrics-register` | `status` + `trend` | `BREACH`(crit) / `WARN`(high) / `ON TRACK`(good); arrow from `trend`, which is already direction-aware — a lower-better metric rising is `↓` red |
| `exceptions-register` | `band` | `OVERDUE`/`EXPIRED`(crit) / `DUE`(high) / `CURRENT`(good) |
| `incident-materiality` | `determination.state` | `MATERIAL`(crit) / `ASSESSING`(high) / `NOT MATERIAL`(good) |
| `board-pack` (gantt) | phase status | `LATE`(crit) / `AT RISK`(high) / `WATCH`(medium) / `ON TRACK`(good) — dot **and** word |
| `nist-csf` | (gaps) | no chip — posture is narrative; deliberately left neutral |

**Headline tiles** colour only the exception counts — over-appetite → crit; past-threshold / moving-wrong-way / overdue / open-reporting-window → high; a count of `0` downgrades to neutral. Everything else stays neutral.

## 3. Integration (the real one)

The prototype read a `--status` side file. In production this must be **automatic**:

- **Extend the assembler:** while `assemble_pack.py` reads each producer's store for headline figures, also read the per-item status the engine already computes and attach it — `item.status = {sev, label, arrow}`, `headline.sev`. Additive; the data already exists. **The assembler carries status, it never computes it.**
- **Renderers map only.** No status logic beyond the table above.
- **Board-safety unaffected:** chips are *status* words, not *confidence* words, so the existing no-confidence-vocabulary guard still holds.
- **Roll the same vocabulary into every standalone renderer**, so a single dashboard reads like the board pack.

## 4. Guardrails

- Colour + word, always.
- Patina ≠ good, and patina never carries data.
- Neutral is the default; flag the exceptions, not everything.
- Declare, don't infer.
- Keep the measured contrast ratios; reuse `text_on()`. Amber (2.54:1) and yellow (1.64:1) fills always carry a visible label.

---

*A Cyber Aware Creation · Not affiliated with NIST.*
