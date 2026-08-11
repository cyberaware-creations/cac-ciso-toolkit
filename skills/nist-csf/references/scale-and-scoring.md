# Scales, scoring, and the Tier caveat

Two rating scales exist in this skill's world. They are not interchangeable, and the difference
matters enough to have its own document.

## The native scale — 0–3 achievement (default)

```
0 Not Achieved · 1 Partially Achieved · 2 Largely Achieved · 3 Fully Achieved
```

What a new Profile gets from `init`. It describes **to what extent an outcome is being achieved** and
deliberately borrows no vocabulary from anywhere else, so a rating cannot be mistaken for a Tier or a
maturity level. Full contract in `schema.md`.

## The web-tool scale — 0–4, borrowing Tier names

```
0 Not Implemented · 1 Partial · 2 Risk Informed · 3 Repeatable · 4 Adaptive
```

Used by the `csf-assessment` web tool and by any Profile converted from a `.csfa` file. Levels 1–4
reuse the names of NIST's four **Implementation Tiers**.

> **This is an adaptation, not NIST doctrine.** NIST defines the four Tiers as an
> **organization-wide** characterization of the rigor of risk governance and risk management
> practices (CSWP 29 §3.2, Appendix B, presented there as a *notional illustration*). NIST does
> **not** define per-Subcategory Tiers. Rating an individual outcome "Repeatable" is a widely used
> practical convention that borrows the vocabulary because it is familiar — it is not a claim NIST
> makes.
>
> If a Profile on this scale goes in front of an assessor, say so explicitly. The credibility cost of
> being caught conflating the two is far higher than the cost of a sentence of explanation.

Where Tiers appear *properly* — `profile.tier`, and the Tier block on the executive dashboard — they
are Profile-level and per-Function only, carry verbatim NIST text, and are never computed from
ratings. That separation is the whole point.

## Why both exist

Migration. A `.csfa` from the web tool converts into a native `.csfp` via
`csfa_compat.py convert`, and the conversion **keeps the source scale** rather than rescaling.
Rescaling would silently change what every rating asserts: a "2" on a 0–4 scale is not a "2" on a
0–3 scale, and there is no honest mapping between them. Better to carry the original numbers with
their original meaning and label them clearly.

`settings.scale` is per-Profile, so both coexist across files without conflict.

## Scale-dependent behaviour

Guidance adapts. `render_guidance()` in `profile_analysis.py`:

| Content | Applies on | Why |
|---|---|---|
| Deep guidance (`whatMatureLooksLike`, `nextSteps`, `commonPitfalls`) | **any scale** | Describes practice, not levels. |
| Function slants | **any scale** | Describes where to look, not levels. |
| Tier-transition paragraphs ("Moving from Partial to Risk Informed…") | **only the 0–4 tool scale** | Names specific levels. On a 0–3 Profile, "1" means something else, so the text would be wrong. |

The check is deliberately narrow: `scale.max == 4` **and** `labels["2"] == "Risk Informed"`. A
Profile that merely happens to have a max of 4 does not get level-named prose written for a
different scale.

## Scoring: two models, both intentional

The native engine and the web tool compute different things. Neither is a bug; they answer different
questions.

| | Native (`profile_analysis.py`) | Web tool (`csfa_compat.py`) |
|---|---|---|
| Rollup | `Σ min(current, target) / Σ target` | mean of assessed, non-N/A ratings |
| Targets | per-Subcategory | per-Function (presets + overrides) |
| Priority | `gap × priorityWeight × functionWeight` | `gap ≥ 3` critical · `== 2` high · else `GV\|PR` medium · else low |
| Unassessed | excluded from the denominator; reported as a completeness count | excluded from the mean; counted against coverage |

> **The Targets row is two models, not a contradiction — and migration reconciles them.**
> `csfa_compat.py convert` **expands** the tool's Function-level target across every Subcategory
> in that Function, so a converted Profile carries a per-Subcategory target like any other. On
> `examples/acme-manufacturing.csfa`, whose targets are `{default: 3, byFunction: {GV: 4, PR: 4}}`,
> that produces **104 rated Subcategories each holding their own `target`** — 4 across GV and PR,
> 3 elsewhere — which is why `csfa_compat.py`'s own docstring says migration yields
> *"per-Subcategory targets"* while this row says the tool's targets are per-Function. **Both are
> true and they describe different sides of the conversion.**
>
> It is a gain in resolution rather than a reinterpretation: every Subcategory simply *starts* at
> its Function's target and can then be tuned individually. Spelled out here because the row was
> read as a doc-versus-code divergence (BL-94 C2) when it is not one — reading it without its
> column headers makes it look like one claim about one thing.

Two consequences of the native model worth knowing:

- **Over-achievement earns no credit.** `min(current, target)` caps a Subcategory's contribution at
  its Target, so a 3-against-a-target-of-2 cannot offset a 0 elsewhere.
- **Coverage is not a mean.** A mean lets one strong Category mask a zero and invites being read as a
  maturity score. Coverage always travels with its numerator and denominator so the reader can see
  what it is drawn from.

The web tool's model is preserved verbatim in `csfa_compat.py` for byte-parity on the gaps CSV, which
`risk-register import-gaps` consumes. That parity is a contract; do not "improve" the ported
functions.
