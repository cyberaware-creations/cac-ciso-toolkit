# Cyber Aware Creations Brand Tokens

Canonical brand for generated HTML/PDF deliverables. Mirrors `cac-site` `cac` tokens. Use these
exact values so every artifact reads as one product family.

## Palette (`cac`)

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
| measure | `#2E6FA7` | **Measurement** with no threshold — the default data colour |
| measureTrack | `#D8E4F1` | Track/background behind a `measure` fill |

**Rule:** patina is the brand/action colour and is **chrome only** — it marks interactive and brand
elements and **never encodes a measurement or a risk**. A "today" line or a section rule may be
patina; a bar, a dot, a cell or a segment may not.

## Measurement colours

Data that carries no agreed threshold is **not** a status, and must not borrow the RAG ramp. It uses
`measure` on a `measureTrack` ground. Where several *categories* must be told apart — incident
source, asset class, control family — they separate by lightness along a sequential ramp, never by
RAG hue:

| Step | Hex |
|---|---|
| 1 (darkest) | `#1B4E7A` |
| 2 | `#2E6FA7` |
| 3 | `#5B9BD0` |
| 4 | `#94BEE2` |
| 5 | `#C4DAEE` |
| 6 (lightest) | `#E4EEF7` |

Colouring a category red asserts a danger the data never claimed, and a reader who has learnt the
RAG contract will believe it.

## Three measured findings that constrain every ramp

These are measurements, not preferences. They are why the rules above are shaped as they are, and
re-deriving them by eye will reproduce the defects they were introduced to fix.

1. **Green↔red is ΔE 6.2 under deuteranopia.** Inherent to any traffic-light ramp; darkening does
   not help. This is why a RAG mark is *always* paired with a word, and why colour is never the only
   signal.
2. **Amber `#e08e0b` is 2.54:1 on white; medium `#e8c547` is 1.64:1.** Both are under the 3:1 relief
   line, so **white text on either is prohibited** and those fills always carry a visible label. Use
   the band's dark text colour on a tint or mid ground, or ink on a saturated fill.
3. **Medium↔high is ΔE 13.3 and cannot be fixed by darkening.** Tested: `#DDB02A` → 8.1,
   `#D4A017` → 4.6, `#CFA524` → 5.9 — all worse, because darkening moves yellow toward orange. So
   wherever all four bands can appear adjacently — heat matrix, stacked bar, bullet zones — **every
   cell or segment carries its label or value**, and the band boundary is tickable. Do not
   "improve" the brand hexes to try to separate them.

**Never use `opacity` to de-emphasise.** An opacity-composited colour is not the colour any
contrast check validated, so the contract cannot be enforced on it. Pick a token that measures.

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
