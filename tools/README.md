# Build-time tools

**Not part of the plugin.** Nothing here ships to users or is loaded by a skill. These scripts
regenerate bundled reference data from its published sources, and they are exempt from the repo's
stdlib-only Python rule because their *output* is what ships, not their code.

They exist so that `skills/nist-csf/references/nist-csf-2.0-core.json` is reproducible. Without
them the file is a 389K blob nobody can regenerate, verify, or update when NIST publishes a
revision.

## Regenerating the CSF 2.0 Core

The bundled Core is built in two passes.

### Inputs

| Input | Where it comes from |
|---|---|
| `csf-2.0.xlsx` | The NIST CPRT CSF 2.0 catalog export. A copy is checked into the sibling `csf-assessment` repo at `scripts/csf-2.0.xlsx`. Originally from `https://csrc.nist.gov/extensions/nudp/services/json/csf/download?olirids=all` — despite the `/json` path it returns an XLSX. |
| `NIST.CSWP.29.pdf` | `https://nvlpubs.nist.gov/nistpubs/CSWP/NIST.CSWP.29.pdf` — the CSF 2.0 publication. Tier text lives in Appendix B, Table 2. |

Neither input is vendored here. The XLSX lives in `csf-assessment` (which checked it in for exactly
this reason) and the PDF is a stable NIST URL. If you want this repo to be self-contained, copy the
XLSX in and point the script at it.

### Pass 1 — hierarchy, examples, informative references

```bash
# xlsx (SheetJS) is not a dependency of this repo; borrow the sibling project's install
NODE_PATH=../csf-assessment/node_modules \
  node tools/ingest-csf-core.js \
    skills/nist-csf/references/nist-csf-2.0-core.json \
    ../csf-assessment/scripts/csf-2.0.xlsx
```

Parses columns A–E, excludes every `[Withdrawn:]` row (12 categories and 79 subcategories retired
from CSF 1.1 still sit in the sheet), and asserts the known-good shape **before writing**: 6
Functions / 22 Categories / 106 Subcategories, per-function counts GV:31 ID:21 PR:22 DE:11 RS:13
RC:8, 363 Implementation Examples, every Subcategory carrying at least one, all ids unique. Any
mismatch fails loudly and writes nothing.

Provenance is recorded as a sha256 of the source file rather than a timestamp, so re-running against
the same input produces a byte-identical file.

### Pass 2 — verbatim Tier text

```bash
curl -sSL -o /tmp/cswp29.pdf https://nvlpubs.nist.gov/nistpubs/CSWP/NIST.CSWP.29.pdf
pdftotext /tmp/cswp29.pdf /tmp/cswp29-raw.txt      # NOTE: no -layout, see below

python3 tools/add-tiers.py \
  skills/nist-csf/references/nist-csf-2.0-core.json \
  /tmp/cswp29-raw.txt
```

Injects the Tier block and **verifies every transcribed paragraph as a substring of the published
PDF** before writing — 24 checks, normalising whitespace, hyphens, and typographic quotes. A typo or
a dropped clause fails the run rather than shipping as "verbatim".

Two extraction gotchas, both load-bearing:

- **Do not pass `-layout`.** It preserves the table's column geometry, which interleaves the two
  Tier columns line by line and makes cell text non-contiguous. Plain mode keeps each cell together.
- **`pdftotext` silently de-hyphenates across line breaks** — `organization-wide` extracts as
  `organizationwide`. The verifier strips hyphens before comparing, which is why the transcription
  can carry the correct hyphenation while still matching the source.

### Verifying a regeneration

```bash
python3 skills/nist-csf/scripts/profile_analysis.py validate
python3 skills/nist-csf/scripts/profile_analysis.py self-test
```

Both must pass. `validate` re-asserts the integrity invariants on load; `self-test` checks the
engine math against the fixture, which depends on the Core's text and examples.

If the regenerated file should be identical to what is committed, diff it — the build is
deterministic, so any difference is a real change in the source data or the tools:

```bash
diff <(git show HEAD:skills/nist-csf/references/nist-csf-2.0-core.json) \
     skills/nist-csf/references/nist-csf-2.0-core.json
```

## A note on Informative References

Column E is ingested and stored as **raw catalog lines**, exactly as published. It is not split into
`{source, reference}` pairs: source names such as `ISO/IEC 27001:2022` contain colons, so any split
rule is guesswork against an open-ended set of catalogs, and a wrong parse baked into shipped data
would be harder to correct later than no parse at all.

v1 carries this data but renders none of it. The v2 crosswalk work owns the structured split, with
the raw strings still available to it.
