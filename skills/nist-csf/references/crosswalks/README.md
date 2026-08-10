# Crosswalk data — provenance, licensing, and refresh

Read-only bundled data. Six files: a control catalogue and a CSF-keyed edge map per lens. Nothing
here is ever rated, and nothing here is written to a `.csfp` or `.csfa` — a crosswalk is a
projection of an existing CSF assessment. The enforced contract is in
`../framework-abstraction.md`; this file covers where the data came from and how to refresh it.

## What is bundled

| Lens | Edges | Catalogue | Labels | Mapping authority |
|---|---|---|---|---|
| `800-53-r5` | 737 | 210 controls / 20 families | verbatim NIST titles | `nist-developed` |
| `iso-27001-2022` | 329 | 119 (93 Annex A + 26 ISMS clauses) / 5 groups | ours | `mixed-third-party` |
| `cis-8.1` | 62 | 49 mapped safeguards / 16 controls | ours | `cis-authored` |

The edges are facts from the NIST CPRT export's Informative References. The **labels are ours** for
ISO and CIS, and only 800-53 carries verbatim titles.

## Licensing — the reason the labels are ours

ISO/IEC 27001:2022 and the CIS Controls are copyrighted. Their control **titles and normative text
are not redistributable**, so this data carries identifiers plus our own short paraphrases and no
normative text at all. A reader who needs the official wording looks it up in their own licensed
copy; the identifier is there so they can.

Two things are worth separating, because they are easy to run together. **Where the identifiers came
from:** every mapped ISO and CIS identifier here was read out of NIST's CSF 2.0 informative-reference
export, where those organizations' references are published without licence terms attached — not out
of ISO's or CIS's own control materials, which were never used. **What was done with them:** an
identifier is a fact and a reference, and the only prose beside it is ours. Neither standard's
expression is reproduced, so a no-derivatives clause has nothing here to bite on. The provenance
string on each catalogue records the first; the `cac-generated` rule below enforces the second.

NIST SP 800-53 Rev 5 is a work of the US Government and not subject to copyright, so its family
names and all 210 control titles are verbatim.

**Which release, said explicitly.** The mapping is built at **Release 5.2.0**, stamped as
`release` on the catalogue and `overlayRelease` on the map. `version` stays `"Rev 5"` — that is
the revision, it has read the same since 2020, and it cannot express which patch release a
mapping was built from. It had to, because for one release two surfaces in this repo disagreed:
`sources.json` already recorded 5.2.0 while the bundle was still built from 5.1.1, and nothing
could see the difference (BL-160).

The titles are verbatim from NIST's own OSCAL catalogue — `usnistgov/oscal-content`,
`nist.gov/SP800-53/rev5/json/NIST_SP-800-53_rev5_catalog.json`, metadata version 5.2.0,
last-modified 2026-05-11. Naming the document matters because `labelSource:
"verbatim-public-domain"` is a claim, and a machine comparison against that catalogue found
**three shipped titles that were not verbatim** — two hyphens for em dashes, one capitalisation.
They are corrected, and the comparison is the reason they were found rather than assumed.

This boundary is enforced in two places rather than trusted:

- `check_crosswalks()` in `../../scripts/profile_analysis.py`, which runs inside
  `profile_analysis.py validate` and the engine self-test, and therefore ships with the skill;
- `tools/crosswalks/validate_crosswalks.py`, the build-time checker that owns the rules.

Both run in CI. A catalogue that carries ISO or CIS `text`, or marks an ISO or CIS label anything
other than `cac-generated`, fails the build.

Label wording conventions: `label-style.md`.

## Refreshing when NIST republishes the reference export

The builder is `tools/crosswalks/author_catalogs.py`. It lives under `tools/` because everything
under `skills/` ships to users, and a 144KB source export only a rebuild needs should not.
Stdlib only — no install step, and no `openpyxl`; the XLSX read reuses `read_sheet_rows()` from
`tools/ingest-csf-core.py`, which already parses this same export for the CSF Core.

```bash
# 1. Replace the vendored export.
#    Source: https://csrc.nist.gov/extensions/nudp/services/json/csf/download?olirids=all
#    (despite the /json path it returns an XLSX)
curl -L -o tools/crosswalks/_source_csf2.xlsx \
  "https://csrc.nist.gov/extensions/nudp/services/json/csf/download?olirids=all"

# 2. Update the retrieval stamp in the builder.
#    RETRIEVED="YYYY-MM-DD" near the top of author_catalogs.py — it is written into
#    every catalogue's provenance, so a stale stamp misdates the whole bundle.

# 3. Rebuild.
python3 tools/crosswalks/author_catalogs.py

# 4. Diff. This is the review step, not a formality.
git diff --stat skills/nist-csf/references/crosswalks/

# 5. Re-gate.
python3 tools/crosswalks/validate_crosswalks.py
python3 skills/nist-csf/scripts/profile_analysis.py validate
python3 skills/nist-csf/scripts/profile_analysis.py self-test
PY="$(command -v python3)" ./skills/nist-csf/evals/crosswalk-e2e.sh
```

**A refresh is expected to fail step 5 the first time it changes a count.** The counts are pinned in
`CROSSWALK_EXPECTED` (`profile_analysis.py`) and asserted again in the e2e suite. That is the
intended behaviour: a moved mapping is a change to what this skill claims about coverage, so it
should require a human to look at the diff and update the constants deliberately rather than
sliding through. Update `CROSSWALK_EXPECTED`, the table above, and the e2e suite's headline
assertions together, and say in the commit what moved.

If a rebuild changes the **golden fixture's** expected numbers, re-derive
`../../evals/fixtures/crosswalk-golden-expected.json` and hand-check the affected controls against
their contributing Subcategories before freezing it again. The whole value of that fixture is that
its numbers were verified by hand, not generated by the code they test.

Reproducibility is checked, not assumed: rebuilding from the vendored export reproduces all six
files byte-for-byte, which is what makes step 4's diff trustworthy.

## New labels

Adding a lens, or extending a catalogue to controls it does not yet hold, means authoring new
labels. Those are **reviewed by a human before shipping** — the 168 ISO and CIS labels bundled here
were reviewed and approved on 2026-07-29. A generated label that has not been read is a claim about
a standard nobody checked, so treat the review as part of the data, not a formality.

## Why the CIS catalogue is only the mapped subset

The CIS catalogue holds the **49 Safeguards the NIST CSF export references** and no others, so its
"controls outside CSF" honesty list is empty. That is a sourcing boundary, not an unfinished task,
and more work of the same kind will not close it.

Those 49 are the complete set of `CIS Controls v8.1:` references the export carries — checked, not
assumed — so there is nothing further to take from that source. Extending the catalogue to the rest
of v8.1 would mean working from CIS's own control materials instead, and that is the line we do not
cross: the CIS Controls are published under CC BY-NC-ND, whose ND term forbids distributing material
that remixes, transforms, or builds upon the original, with commercial use requiring prior approval.
Nothing about the 49 depends on that judgement — they arrived via NIST, unencumbered — but the
remaining hundred-odd would.

The consequence is stated in-product rather than hidden: an empty CIS "outside CSF" list means
*not enumerated here*, not *none exist*, and the report tells the reader to check their own licensed
copy of the CIS Controls for Safeguards CSF does not reach. ISO is different only because we hold a
full Annex A control list; its 28-control list is real.

The 49 Safeguards we do carry are named by identifier from the NIST export — a US Government work —
with CAC-authored labels, never CIS wording.

## Why the ISO catalogue is the full set

It is the one lens whose "outside CSF" list is real, and that is worth being precise about, because
it is not purely an export read. NIST's export references **91 of the 119 identifiers** — 88 against
a Subcategory, and 3 only against a Category. The other 28 are the standard's own numbering, added
deliberately: a catalogue holding only what CSF already reaches cannot answer "what does CSF *not*
reach", which is the question the honesty list exists for. Numbering is a reference, not expression,
and every label against those 28 is CAC-authored like the rest. `catalogueScope.note` on the
catalogue says the same thing, so the distinction travels with the data rather than living only here.

## The third case: referenced only at Category level

The export hangs references off Function and Category rows too, and those rows carry no Subcategory
to key an edge on. Dropping them is right for the edge map — a crosswalk projects Subcategory
ratings, and there is nothing at the right grain to project — but treating the controls as *unmapped*
was wrong: **A.5.33, A.5.36 and A.8.27** sat on the "CSF does not reach this" list while NIST does in
fact reach them, one grain up. A reader following that list would have gone and assessed all three
from scratch.

They now carry `csfReference: "category-only"` in the catalogue, stamped at build time because the
shipped engine cannot see the source, and `crosswalk_completeness()` returns them as
`controlsCategoryOnly` — a third list, neither scored nor disowned. The ISO outside-CSF list is 28,
not 31. 800-53 has one such control (IR-9) which the catalogue does not hold at all, since it holds
what the export references at Subcategory grain; CIS has none.

*A Cyber Aware Creation · Not affiliated with NIST, ISO, or CIS*
