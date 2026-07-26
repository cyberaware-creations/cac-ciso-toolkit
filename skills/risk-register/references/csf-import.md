# CSF Gap Import Reference

How a CSF 2.0 gap assessment becomes candidate risks. Handled by
`scripts/score_register.py import-gaps`.

## Gap CSV contract

The `csf-assessment` tool exports one row per gap with exactly these columns:

```
subcategory_id, function_id, category_id, current_tier, target_tier, priority, subcategory_text, note
```

The parser requires all eight header columns and fails with a clear message if any is missing. It
tolerates quoted fields containing commas and doubled-quote (`""`) escapes. Rows that are entirely
blank are skipped.

## Field mapping

| CSV field | → Risk field |
|---|---|
| `subcategory_id` + `subcategory_text` | `title` (`"<id>: <text>"`, capped 140 chars) |
| `subcategory_text` | `description` (`"CSF gap — <text>"`) |
| `function_id` | `category` (the CSF function, e.g. `PR`) |
| `subcategory_id` | `csfSubcategoryId` (dedupe key) |
| `priority` | seeds inherent **and** residual likelihood×impact (see table) |
| `current_tier`, `target_tier`, `priority`, `note` | concatenated into `notes` (`"Tier X → Y · priority: Z · <note>"`) |

## Priority → score seeding

Each gap's `priority` seeds both likelihood and impact (so a fresh candidate sits on the matrix
diagonal). Unknown/blank priority defaults to 3.

| priority | seeded likelihood & impact |
|---|---|
| critical | 5 |
| high | 4 |
| medium | 3 |
| low | 2 |

These are **starting points**, deliberately conservative and symmetric. Always refine likelihood
and impact with the user — a gap's priority is not the same as its scored risk. In particular,
residual is seeded equal to inherent (no control credit yet); lower residual once a real response is
described.

## Dedupe and merge

Import is non-destructive:
- A candidate whose `csfSubcategoryId` matches an existing risk **updates** that risk's title,
  description, category, and notes — it does not create a duplicate.
- A candidate with no match is **added** with the next free `R-###` id.

`import-gaps <gaps.csv> --into <existing.rr>` merges against an existing register and reports
`N added, M updated`. Without `--into`, it emits all rows as fresh candidates.

## .csfa prefill (optional)

A `.csfa` assessment file (`frameworkId: "csf-2.0"`) can additionally prefill `meta.clientName` and
`meta.assessor`. Validate the framework id defensively and fail with a clear message on mismatch.

## Flow

Always **preview → confirm → merge**: show the mapped candidates (and which would update vs add)
before writing anything, let the user adjust seeded scores, then merge.
