# CSF Gap Import Reference

How a CSF 2.0 gap assessment becomes candidate risks. Handled by
`scripts/score_register.py import-gaps`.

## Gap CSV contract

The `nist-csf` skill's `export-gaps` command (and the legacy `csf-assessment` web tool) writes one
row per gap with exactly these columns:

```
subcategory_id, function_id, category_id, current_tier, target_tier, priority, subcategory_text, note
```

The parser requires all eight header columns and fails with a clear message if any is missing. It
tolerates quoted fields containing commas and doubled-quote (`""`) escapes. Rows that are entirely
blank are skipped.

## Field mapping

| CSV field | → Risk field |
|---|---|
| `subcategory_id` + `subcategory_text` | `title` (`"<id>: <text>"`, truncated at 140 chars on a word boundary with `…`) |
| `subcategory_text` | `description` (`"CSF gap — <text>"`) |
| `function_id` | `category` (the CSF function, e.g. `PR`) |
| `function_id` | `theme` (lowercased, e.g. `pr`) — see **Themes** below |
| `subcategory_id` | `csfSubcategoryId` (dedupe key) |
| `priority` | seeds inherent **and** residual likelihood×impact (see table) |
| `current_tier`, `target_tier`, `priority`, `note` | concatenated into `notes` (`"CSF rating X → Y (achievement, not a CSF Tier) · priority: Z · <note>"`) |
| — | `provisional: true` — see **Provisional risks** below |

Note the `notes` wording. The CSV's columns are named `current_tier`/`target_tier` for historical
reasons but carry **achievement ratings on a 0–3 scale, not CSF Tiers**. The importer used to write
"Tier 0 → 3" into every imported risk, producing the exact leak both skills warn about.

## Provisional risks

Every imported risk is written with `provisional: true`. An imported row is a *candidate*, not an
assessed risk: its title is a control objective phrased as a good thing, and its scores are a
priority seed nobody has looked at.

While a risk is provisional:

- **Board-facing renderers refuse to print its title**, showing a labelled placeholder instead — the
  same treatment an untranslated narrative gets. "Identities and credentials for authorized users …
  are managed by the organization", tagged Critical, reads to a director as the opposite of what it
  says.
- The board dashboard carries a banner stating how many of the totals are provisional.
- `score` marks it `~` and prints a summary count.
- A **re-import will not overwrite its title or description**. Once you reword one, that wording is
  yours and survives every subsequent import.

Clear the flag by doing the review: `set-text` (reword it as a NISTIR 8286 event statement) or
`set-score` (refine the seeded scores). Either counts.

## Themes

Themes are the board rollup axis, so an unthemed import makes the board's theme tile read
"Unclassified · 74 risks". Each risk is themed by its CSF Function (`gv`, `id`, `pr`, `de`, `rs`,
`rc`), and `--write` defines any of those six themes actually used by the imported data.

This is a default, not a decision. If the organisation groups risk differently, re-theme with
`set-theme` — a re-import fills an *unset* theme but never overwrites one you set.

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

### `--into` previews; `--write` applies

```bash
# 1. Preview. Prints the mapped candidates as JSON and writes NOTHING.
python3 scripts/score_register.py import-gaps gaps.csv --into client.rr

# 2. Apply, once you have looked at what it would do.
python3 scripts/score_register.py import-gaps gaps.csv --into client.rr --write
```

`--into` alone is a **dry run**. It reports `N added, M updated` describing what *would* happen —
following the docs without `--write` and believing the merge had happened was previously an easy and
silent mistake. Without `--into` at all, it emits every row as a fresh candidate to stdout.

On update, a matched risk always refreshes its CSF-derived fields (`category`, `notes`, and an unset
`theme`). Its `title` and `description` are refreshed **only while it is still provisional**.

## .csfa prefill (optional)

A `.csfa` assessment file (`frameworkId: "csf-2.0"`) can additionally prefill `meta.clientName` and
`meta.assessor`. Validate the framework id defensively and fail with a clear message on mismatch.

## Flow

Always **preview → confirm → merge**: show the mapped candidates (and which would update vs add)
before writing anything, let the user adjust seeded scores, then merge.
