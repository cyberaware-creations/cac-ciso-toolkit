# Build-time tools

**Not part of the plugin.** Nothing here ships to users or is loaded by a skill. These scripts
either regenerate bundled reference data from its published sources, or guard a repo-wide
invariant that no single skill owns.

The generators exist so that `skills/nist-csf/references/nist-csf-2.0-core.json` is reproducible.
Without them the file is a 389K blob nobody can regenerate, verify, or update when NIST publishes
a revision.

The guards live here rather than in a skill's `evals/` directory for the same reason everything
else here does: `skills/**` ships to users, and a check about the repo's own manifests is not
something a user should be shipped.

| Guard | What it enforces |
|---|---|
| `check-versions.py` | The four plugin version strings agree, and they move whenever shipped content moves. Run by the `manifests` job in `.github/workflows/evals.yml`. |

**No dependencies, no install step.** Python stdlib and node built-ins only. That is a deliberate
constraint, not a happy accident — see "Why there is no `package.json`" at the end.

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

### Pass 1 — hierarchy, examples, informative references

```bash
python3 tools/ingest-csf-core.py skills/nist-csf/references/nist-csf-2.0-core.json
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

Runs on `node:fs`, `node:path`, and `node:vm` — built-ins only, no install.

Sources: `guidance-deep.ts`, `guidance.data.ts`, `csf-2.0-context.ts`.

**Provenance note.** Function `definition` strings are NIST CSWP 29 text (public domain).
Everything else — the deep guidance, the Function slants, the tier-transition paragraphs, and
`whyItMatters` — is original Cyber Aware Creations content, and the JSON records that distinction in
its `source.note`. The `0 → 1` transition and the `0 Not Implemented` label are authored *for this
skill* (the web tool had no 0 level) and are flagged separately under `added`.

## Extracting the Cyber AI Profile dataset

`skills/nist-csf/references/cyber-ai-profile.json` holds the per-Subcategory, per-Focus-Area
proposed priorities from **NIST IR 8596 (Cyber AI Profile)**. It exists so the `nist-csf`
overlay can reweight the 106 Subcategories for AI relevance without anyone retyping 318
numbers.

```bash
curl -A "Mozilla/5.0" -o /tmp/ir8596.pdf \
  https://nvlpubs.nist.gov/nistpubs/ir/2025/NIST.IR.8596.iprd.pdf
pdftotext -layout /tmp/ir8596.pdf /tmp/ir8596.txt      # NOTE: -layout IS required here

python3 tools/extract_cyber_ai.py /tmp/ir8596.txt \
  --out skills/nist-csf/references/cyber-ai-profile.json \
  --coverage /tmp/coverage.txt \
  --core skills/nist-csf/references/nist-csf-2.0-core.json
```

Note the opposite `-layout` advice from Pass 2 above: the Tier extraction must **not** use it,
this one **must**. The priorities live in three side-by-side columns, and the parser slices
them by character offset — without `-layout` there are no columns to slice.

Three gotchas, all of which cost time once:

- **`nvlpubs.nist.gov` returns 404 to a default curl user-agent** and 200 to a browser one.
  The file is not missing; the request is being refused.
- **Column order is Secure | Defend | Thwart.** Swapping two would invert priorities in a way
  no validator can catch, because every value would still be a legal 1/2/3. The script warns
  if it cannot find the column header, and `--check` on the output is not a substitute for
  looking at a rendered page.
- **The "standard cybersecurity practices apply" sentinel wraps across lines.** Grepping the
  whole document for it returns exactly one hit — the sentence in §2.2 that *defines* the
  phrase. It is used 142 times. A line-based parser sets `standardPracticesApply` false for
  all 318 cells and looks entirely successful.

The script emits a coverage report naming every cell it could not parse and **exits non-zero**
if any Subcategory is missing, so a partial extraction cannot be mistaken for a finished one.
It defaults nothing.

Verification method and results for the shipped dataset are in
`docs/superpowers/notes/2026-07-28-ir8596-dataset-verification.md`. IR 8596 is a preliminary
draft; an initial public draft is expected, and this script exists so following it costs a
re-run rather than a re-transcription.

## Why there is no `package.json`

Pass 1 used to be `ingest-csf-core.js`, running on SheetJS (`xlsx`) to turn the worksheet into rows
of strings. That single call cost two unfixable high-severity advisories:

| Advisory | CVSS | Fixed in |
|---|---|---|
| [GHSA-4r6h-8v6p-xvw6](https://github.com/advisories/GHSA-4r6h-8v6p-xvw6) — prototype pollution | 7.8 | 0.19.3 |
| [GHSA-5pgg-2g8v-p4x9](https://github.com/advisories/GHSA-5pgg-2g8v-p4x9) — ReDoS | 7.5 | 0.20.2 |

**Unfixable via npm**: SheetJS stopped publishing to the registry at 0.18.5 and ships later releases
only from its own CDN, so `npm audit` reports `fixAvailable: false` in perpetuity. The choices were a
CDN tarball URL that Dependabot cannot track, or no dependency at all.

An XLSX is a zip of XML; `zipfile` and `xml.etree` are stdlib. Pass 1 was ported to
`ingest-csf-core.py` and the JS deleted, along with `package.json`, `package-lock.json`, and
`node_modules`. The repo now has zero third-party dependencies of any kind.

The port is **verified, not asserted** — both implementations were run against the vendored XLSX and
their output diffed:

```
775e835b1c4436cc3fe2d98f44b3025b4beca4fe114be3126252df0af7151505   core-js.json
775e835b1c4436cc3fe2d98f44b3025b4beca4fe114be3126252df0af7151505   core-py.json
```

Byte-identical, so the shipped Core is unchanged by the migration. Re-check any time with the
regeneration diff below. Worth remembering if a future tool is tempted to take a dependency to save
sixty lines: this one was build-time only and never shipped, and it still generated recurring alerts
on the default branch.

## A note on Informative References

Column E is ingested and stored as **raw catalog lines**, exactly as published. It is not split into
`{source, reference}` pairs: source names such as `ISO/IEC 27001:2022` contain colons, so any split
rule is guesswork against an open-ended set of catalogs, and a wrong parse baked into shipped data
would be harder to correct later than no parse at all.

v1 carries this data but renders none of it. The v2 crosswalk work owns the structured split, with
the raw strings still available to it.

## `prove-guards.sh` — CAC-GP-1

Every guard in the suite must FAIL when the defect it forbids is present. This proves that on
each run, against a fresh copy, in both directions — clean must pass first, then mutated must
fail — from mutations registered as data in `skills/*/evals/guard-proofs/*.json`.

It lives here rather than in a skill because it is about the repo's own invariants and covers
seven guards across three skills. See `guard-proof-standard.md` for the rules and the registry.

```bash
./tools/prove-guards.sh              # all eight guards, sixteen halves
./tools/prove-guards.sh no-ai-score  # one guard
```
