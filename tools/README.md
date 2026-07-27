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
| `tools/csf-2.0.xlsx` | **Vendored here.** The NIST CPRT CSF 2.0 catalog export, originally from `https://csrc.nist.gov/extensions/nudp/services/json/csf/download?olirids=all` — despite the `/json` path it returns an XLSX. NIST publications are US Government works and are not subject to copyright. |
| `NIST.CSWP.29.pdf` | `https://nvlpubs.nist.gov/nistpubs/CSWP/NIST.CSWP.29.pdf` — the CSF 2.0 publication. Tier text lives in Appendix B, Table 2. Not vendored: it is a stable NIST URL and only its extracted text is needed. |

The vendored XLSX is provably the file the shipped Core was built from — its sha256 matches the
`source.sha256` recorded inside `nist-csf-2.0-core.json`. Check it any time:

```bash
shasum -a 256 tools/csf-2.0.xlsx
python3 -c "import json;print(json.load(open('skills/nist-csf/references/nist-csf-2.0-core.json'))['source']['sha256'])"
```

### Setup

```bash
npm install --prefix tools     # installs xlsx (SheetJS); tools/node_modules is gitignored
```

### Pass 1 — hierarchy, examples, informative references

```bash
node tools/ingest-csf-core.js skills/nist-csf/references/nist-csf-2.0-core.json
```

Defaults to the vendored `tools/csf-2.0.xlsx`. Pass a different path as a second argument to build
against a newer catalog export.

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

## Harvesting the authored guidance

`skills/nist-csf/references/guidance.json` holds the hand-authored guidance IP lifted from the
`csf-assessment` web tool — the actual differentiator, as distinct from the NIST public-domain
taxonomy.

```bash
node tools/harvest-guidance.js ../csf-assessment skills/nist-csf/references/guidance.json
```

Extracts by stripping TypeScript annotations and evaluating the exported object literals, rather
than transcribing by hand: 15 multi-paragraph entries copied manually is a near-certain source of
silent drift, and re-running this proves the shipped JSON still matches source. Asserts 15 deep
entries, 6 Function slants, 6 `whyItMatters` entries and 3 tier transitions before writing.

Sources: `guidance-deep.ts`, `guidance.data.ts`, `csf-2.0-context.ts`.

**Provenance matters here.** Function `definition` strings are NIST CSWP 29 text (public domain).
Everything else — the deep guidance, the Function slants, the tier-transition paragraphs, and
`whyItMatters` — is original Cyber Aware Creations content, and the JSON records that distinction in
its `source.note`. The `0 → 1` transition and the `0 Not Implemented` label are authored *for this
skill* (the web tool had no 0 level) and are flagged separately under `added`.

No npm dependency; runs on plain node.

## A note on Informative References

Column E is ingested and stored as **raw catalog lines**, exactly as published. It is not split into
`{source, reference}` pairs: source names such as `ISO/IEC 27001:2022` contain colons, so any split
rule is guesswork against an open-ended set of catalogs, and a wrong parse baked into shipped data
would be harder to correct later than no parse at all.

v1 carries this data but renders none of it. The v2 crosswalk work owns the structured split, with
the raw strings still available to it.
