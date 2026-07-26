# Limen Labs Brand Tokens

Canonical brand for generated HTML/PDF deliverables. Mirrors `cac-site` `limen` tokens. Use these
exact values so every artifact reads as one product family.

## Palette (`limen`)

| Token | Hex | Use |
|---|---|---|
| ink | `#14171C` | Dark chrome: header, tabs, footer, report cover |
| inkRaised | `#1C2026` | Raised dark surfaces |
| inkLine | `#2A2F36` | Lines on dark |
| limestone | `#EAE7DF` | Light text on ink |
| limestoneDim | `#9AA0A6` | Muted text on ink; footer stamp |
| patina | `#2FA98C` | **Brand/action** accent (active tab, primary button, appetite chip) |
| patinaHover | `#279884` | Hover state for patina |
| slate | `#6A7180` | Secondary text |
| workbench | `#F6F4EE` | Light working background |
| workbenchSurface | `#FFFFFF` | Cards, tables |
| workbenchLine | `#D8D3C6` | Lines on light |

**Rule:** patina is the brand/action color and is **never** used to signal "safe" or "low risk."
Risk severity uses the RAG ramp below, which is visually distinct from patina.

## Risk-band colors (RAG ramp)

CVD-safe green→red, used **only** to encode risk severity in tiles, tables, and the heat matrix:

| Band | Hex | Label |
|---|---|---|
| low | `#2e8b57` | Low |
| medium | `#7fb069` | Medium |
| high | `#e08e0b` | High |
| critical | `#c0392b` | Critical |

On high/critical cells, use white text; on low/medium, use ink.

## Type

- Display: `'Space Grotesk', system-ui, sans-serif`
- Body: `'Manrope', system-ui, sans-serif`
- Mono: `'IBM Plex Mono', ui-monospace, monospace`

For self-contained HTML, either load these from Google Fonts or fall back to the system stack; never
block rendering on a font fetch.

## Layout language

Ink dark chrome (header, tabs, footer) over workbench-light working surfaces (cards, tables). The
mark is `AnvilMark` (anvil + patina spark). Footer on every deliverable: **"A Cyber Aware Creation"**
plus the disclaimer **"Not affiliated with NIST."**
