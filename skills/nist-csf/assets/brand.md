# Limen Labs Brand Tokens

Canonical brand for generated HTML/PDF deliverables. Mirrors `cac-site` `limen` tokens and the
`risk-register` skill's `assets/brand.md`. Use these exact values so every artifact reads as one
product family.

> Kept deliberately in sync with `skills/risk-register/assets/brand.md`. Skills are self-contained,
> so this is a copy, not an import — change one, change the other.

## Palette (`limen`)

| Token | Hex | Use |
|---|---|---|
| ink | `#14171C` | Dark chrome: header, tabs, footer, report cover |
| inkRaised | `#1C2026` | Raised dark surfaces |
| inkLine | `#2A2F36` | Lines on dark |
| limestone | `#EAE7DF` | Light text on ink |
| limestoneDim | `#9AA0A6` | Muted text on ink; footer stamp |
| patina | `#2FA98C` | **Brand/action** accent (active tab, primary button) |
| patinaHover | `#279884` | Hover state for patina |
| slate | `#666D7C` | Secondary text (was `#6A7180`: 4.45:1 on workbench, just under AA) |
| workbench | `#F6F4EE` | Light working background |
| workbenchSurface | `#FFFFFF` | Cards, tables |
| workbenchLine | `#D8D3C6` | Lines on light |

**Rule:** patina is the brand/action color and is **never** used to encode a measurement. It marks
interactive and brand elements only.

## Encoding coverage (this skill)

`risk-register` uses a green→red RAG ramp to encode **risk severity**. Coverage is not severity, and
reusing that ramp would imply that a low-coverage Category is "critical" when it may be a
deliberately low Target that is fully met. Coverage therefore uses a **single-hue sequential ramp**,
visually distinct from both patina and the RAG ramp:

| Coverage | Hex | Meaning |
|---|---|---|
| 0–24% | `#7C3A32` | Far below Target |
| 25–49% | `#A6603A` | Well below Target |
| 50–74% | `#C08A3E` | Approaching Target |
| 75–99% | `#8A9A4B` | Near Target |
| 100% | `#4A7C59` | At Target |

Two states are **not** on this ramp and must be visually distinct from every value on it:

| State | Treatment |
|---|---|
| **Untargeted** (`percent: null`, `d == 0`) | `workbenchLine` fill, diagonal hatch, label "not yet targeted" |
| **Not applicable** | `workbench` fill, no border, label "n/a" |

This is the visual half of the rule the engine enforces: *nothing targeted* must never look like
*fully covered*. A blank cell and a green cell must never be confusable.

## Encoding crosswalk bands (this skill)

A **third** ramp, and the reason is the same one that separated the two above. `COVERAGE_RAMP`
encodes coverage against a Target. The register's RAG ramp encodes risk severity. A crosswalk band
encodes something else again — a derived share of the Profile's own rating scale, projected onto
another framework's control. Sharing a ramp between any two of those would assert an equivalence
they do not have.

Single-hue slate blue, so it also cannot be mistaken for `patina`, which never encodes a
measurement:

| Band | Hex | Meaning |
|---|---|---|
| minimal | `#98AEBE` | below 30% of the Profile's scale maximum |
| weak | `#7595A8` | 30–59% |
| moderate | `#4E768B` | 60–84% |
| strong | `#2D4C5E` | 85%+ |

**Validated, not chosen by eye.** Run the `dataviz` skill's validator on any change:

```bash
node scripts/validate_palette.js "#98AEBE,#7595A8,#4E768B,#2D4C5E" --ordinal --mode light --surface "#F6F4EE"
```

ALL CHECKS PASS — monotone lightness, adjacent ΔL ≥ 0.06, light end 2.09:1 on workbench, hue spread
8°. A validated dark-mode ramp exists for a future dark variant and is **not currently rendered**
(these deliverables are light-surface and print-first): `#3A4E59,#587783,#86A6B6,#BAD2DE`, ALL
CHECKS PASS against `ink`.

One state is **not** on this ramp:

| State | Treatment |
|---|---|
| **unknown** (no rated Subcategory behind the control) | `workbenchLine` fill, diagonal hatch, label "not yet rated" |

Same rule as *untargeted* above, for the same reason: *nothing rated* must never be confusable with
*rated and weak*. `minimal` is a measurement; `unknown` is the absence of one.

**The band word is on every cell and every row.** A crosswalk band is never encoded by colour alone
— not for a greyscale print, not for a colour-vision-deficient reader, not in forced-colours mode.

### Text on a coverage swatch — do not hand-pick it

Use `_common.text_on(fill)`, or `cov_text_color(cov)` which wraps it. It measures.

The rule here used to be *"on the two darkest coverage swatches use limestone; on the rest use
ink"* — a threshold that approximates the fill instead of asking it. It put limestone on `#A6603A`
at **3.90:1** and ink on `#4A7C59` at **3.69:1**, both under AA, and the delta chip that inherited
the same threshold logic sat at **1.57:1** on the full-coverage tile. A threshold will always miss
somewhere on a five-value ramp; measuring cannot.

Anything drawn *on* a tile — the Function code, the fraction, the completeness line, the movement
chip — takes that same measured colour. And never reach for `opacity` to de-emphasise one of them:
it is invisible to a colour-pair check but fades the text toward the fill exactly as alpha would.

## Type

- Display: `'Space Grotesk', system-ui, sans-serif`
- Body: `'Manrope', system-ui, sans-serif`
- Mono: `'IBM Plex Mono', ui-monospace, monospace`

For self-contained HTML, either load these from Google Fonts or fall back to the system stack; never
block rendering on a font fetch.

## Layout language

Ink dark chrome (header, tabs, footer) over workbench-light working surfaces (cards, tables). The
mark is `AnvilMark` (anvil + patina spark).

**Footer on every deliverable**, exactly as the shared constant defines it — no trailing period:

```
A Cyber Aware Creation · Not affiliated with NIST
```

This skill renders NIST-derived content, so the disclaimer is not optional decoration. It is the
line that keeps a generated coverage report from reading as a NIST-endorsed assessment.
