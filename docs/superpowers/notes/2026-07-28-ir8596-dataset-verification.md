# Cyber AI Profile dataset — extraction and verification

**Date:** 2026-07-28
**Source:** NIST IR 8596 iprd, published 2025-12-16 (status confirmed in
`2026-07-28-ir8596-status.md`)
**Dataset:** `skills/nist-csf/references/cyber-ai-profile.json`, `datasetVersion`
`8596-iprd-2025-12-16`
**Result:** 106 Subcategories, 318 priority values, **zero mismatches** against an
independent re-extraction; six Subcategories additionally verified against rendered pages.

## What the source actually looks like

Tables 1–6 give each of the 106 Subcategories one row across five columns:

```
CSF 2.0 Core | General Considerations | Secure | Defend | Thwart
                                       `----- Focus Area columns -----'
```

**Column order is Secure | Defend | Thwart**, confirmed visually from the table header on
page 25. This is the single most consequential fact in the extraction: swapping two columns
would invert priorities in a way no validator could catch, because every value would still be
a legal 1/2/3.

Two properties made extraction tractable, and one nearly caused a silent defect:

1. **All three priorities land on the row's first line** in `pdftotext -layout` output. All
   106 rows parsed with exactly three priorities each; **no partial rows, no page-break
   casualties.** The plan expected to hand-complete some cells and none were needed.
2. **The sentinel is wrapped across lines.** `grep -c "standard cybersecurity practices apply"`
   over the whole document returns **1** — the sentence in §2.2 *defining* the phrase. It
   reads as though the phrase is never used in a table. It is used 142 times; `-layout`
   output splits it as `Standard cybersecurity practices` / `apply.` inside its column, so a
   line-based search finds none of them. The extractor slices each column by character offset
   and reads it vertically, which reassembles the phrase.

   **A line-based parser would have produced `standardPracticesApply: false` for all 318
   cells and looked entirely successful.**

## Coverage

```
Subcategories found:   106
Priority values:       318
'standard practices'   142 of 318 cells {'secure': 57, 'defend': 17, 'thwart': 68}
AI-specific cells:     176   (the CAC guidance authoring targets)
Missing from extraction: none
Not in the CSF Core:     none

Priority distribution (1=High, 2=Moderate, 3=Foundational):
  secure  1: 23  2: 33  3: 50
  defend  1: 28  2: 43  3: 35
  thwart  1: 24  2: 44  3: 38
```

Defend carries the fewest sentinels (17), which fits: Defend is about opportunities to *use*
AI, so more of its cells have substantive content.

## Verification — two independent methods

**1. Full cross-parse with a different library — 318 of 318 values, 0 mismatches.**
The dataset comes from `pdftotext -layout` (poppler). The cross-check re-extracted every page
with **pypdf**, a separate implementation with a different text-layout algorithm, and compared
all three priorities for all 106 Subcategories in reading order. Zero disagreements.

This is stronger than the 20-Subcategory hand sample the plan asked for — it covers every
value rather than 19% of them — but it shares one assumption with the original: both read the
PDF's text layer. A defect in the text layer itself would fool both.

**2. Visual verification against rendered pages — 6 Subcategories, 36 values.**
Rendered page images, independent of any text extraction:

| Subcategory | Page | Priorities (S/D/T) | Sentinel (S/D/T) | Match |
|---|---|---|---|---|
| GV.OC-01 | 25 | 3 / 3 / 3 | T / T / T | ✅ |
| GV.OC-02 | 25 | 3 / 2 / 2 | — | ✅ |
| ID.AM-01 | 45 | 3 / 2 / 3 | T / F / T | ✅ |
| ID.AM-02 | 45 | 2 / 2 / 3 | — | ✅ |
| RC.RP-03 | 93 | 2 / 2 / 3 | F / F / T | ✅ |
| RC.RP-04 | 93 | 3 / 2 / 2 | T / F / T | ✅ |

The mixed sentinel patterns (`T/F/T`, `F/F/T`) are the ones worth having: they prove the
column slicing distinguishes cells rather than flagging whole rows.

## Limits of this verification, stated plainly

- **The sentinel is verified on 6 Subcategories (18 cells), not on all 142.** pypdf's layout
  does not preserve the column geometry the sentinel detection depends on, so the cross-parse
  covers priorities only. The sentinel drives guidance-authoring targeting and nothing
  computed, so a miss degrades authoring effort rather than a reported number — but it is less
  verified than the priorities and should not be described as equally checked.
- **Both automated methods read the same text layer.** Only the six visual checks are
  independent of it.
- Visual verification covered GOVERN, IDENTIFY and RECOVER. PROTECT, DETECT and RESPOND rest
  on the cross-parse alone.

## Reproducing this

```bash
curl -A "Mozilla/5.0" -o ir8596.pdf \
  https://nvlpubs.nist.gov/nistpubs/ir/2025/NIST.IR.8596.iprd.pdf
pdftotext -layout ir8596.pdf ir8596.txt
python3 tools/extract_cyber_ai.py ir8596.txt \
  --out skills/nist-csf/references/cyber-ai-profile.json \
  --coverage coverage.txt \
  --core skills/nist-csf/references/nist-csf-2.0-core.json
```

`nvlpubs.nist.gov` **returns 404 to a default curl user-agent** and 200 to a browser one. The
file is not missing; the request is being refused. This cost time once.

When the initial public draft lands, re-run the above, diff the dataset, and re-do the visual
spot-check — the extractor exists so that following a redraft costs a re-run rather than a
re-transcription of 318 numbers.
