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
| slate | `#6A7180` | Secondary text |
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

On the two darkest coverage swatches use `limestone` text; on the rest use `ink`.

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
