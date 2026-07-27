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
| patinaText | `#1C6F5A` | Patina *as text on a light surface* — the fill is 2.66:1 there |
| patinaHover | `#279884` | Hover state for patina |
| slate | `#666D7C` | Secondary text (was `#6A7180`: 4.45:1 on workbench, just under AA) |
| workbench | `#F6F4EE` | Light working background |
| workbenchSurface | `#FFFFFF` | Cards, tables |
| workbenchLine | `#D8D3C6` | Lines on light |

**Rule:** patina is the brand/action color and is **never** used to signal "safe" or "low risk."
Risk severity uses the RAG ramp below, which is visually distinct from patina.

## Risk-band colors (RAG ramp)

CVD-safe green→red, used **only** to encode risk severity in tiles, tables, and the heat matrix:

| Band | Hex | Label |
|---|---|---|
| low | `#30915B` | Low (was `#2e8b57`, which no text colour could take past 4.25:1) |
| medium | `#e8c547` | Medium |
| high | `#e08e0b` | High |
| critical | `#c0392b` | Critical |

### Text on a band fill — do not hand-pick it

Use `_common.text_on(fill)` (or the precomputed `BAND_ON[band]`). It measures.

The old rule here was *"on high/critical cells, use white text; on low/medium, use ink."* It is
wrong for high: white on `#e08e0b` is **2.61:1**, ink on it is **6.88:1**. That sentence was copied
into five places across three renderers and two blocks of inline JS, and the two JS copies were
invisible to anything that reads Python.

### Band colours used *as text*

A fill and a text colour are different jobs; the same hex cannot do both. On the light workbench the
fills run 1.5–2.6:1. Use `BAND_TEXT` for a ⚠ mark, a velocity arrow, or a tag:

| Band | Fill (`BAND`) | As text (`BAND_TEXT`) |
|---|---|---|
| low | `#30915B` | `#25764A` |
| medium | `#e8c547` | `#7A6410` |
| high | `#e08e0b` | `#8F5B06` |
| critical | `#c0392b` | `#c0392b` (already ≥4.5:1) |

### Never use `opacity` to de-emphasise text

It is invisible to a colour-pair check and fades text toward its backdrop exactly as alpha would.
`.frac`, `.tcomp`, `.tid` and `.delta.flat` all used it to push already-marginal tile text under AA.
Pick a colour that measures instead.

**Why medium is amber and not a second green.** It used to be `#7fb069`, a light green. Two adjacent
greens are not separable at stacked-bar size, which is exactly where the band mix is read — and a
mostly-green bar tells the reader "we're fine" when it may be nothing of the sort. It also broke the
CVD-safe claim above: a ramp that runs green→green→orange→red carries its first step in hue alone.
Amber puts a large lightness step between low and medium, so the ramp survives both a small render
and a colour-vision deficiency.

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
