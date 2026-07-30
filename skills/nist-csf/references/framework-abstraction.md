# The framework seam

The load-bearing design decision in this skill: **the assessment, gap, and reporting machinery is
framework-neutral. A "framework" is data.** NIST CSF 2.0 is the first one plugged in, not the thing
the engine is built around.

This is documentation of a contract that is already honoured in v1, not a promise about v2. Alternate
framework *data* is what lands later; the seam itself is here now.

## The contract

A framework file is JSON of this shape:

```jsonc
{
  "id": "nist-csf-2.0",              // matches profile.frameworkRef in a .csfp store
  "name": "NIST Cybersecurity Framework",
  "version": "2.0",
  "source": { /* provenance: publication, catalog, sha256 of the source file */ },
  "tiers": { /* optional — see below */ },
  "hierarchy": [                      // three levels, names are framework-specific
    {
      "id": "GV",
      "name": "GOVERN",
      "description": "...",
      "informativeReferences": ["..."],
      "categories": [
        {
          "id": "GV.OC",
          "name": "Organizational Context",
          "description": "...",
          "informativeReferences": ["..."],
          "subcategories": [
            {
              "id": "GV.OC-01",
              "text": "The organizational mission is understood and informs ...",
              "examples": ["Share the organization's mission ..."],
              "informativeReferences": ["ISO/IEC 27001:2022: Mandatory Clause: 4.1", "..."]
            }
          ]
        }
      ]
    }
  ]
}
```

Required: `id`, `name`, `version`, and a three-level `hierarchy` whose leaves carry `id` and `text`.
Optional: `tiers`, `examples`, `informativeReferences`, `description`, `source`.

**The three levels are structural, not semantic.** CSF calls them Function / Category /
Subcategory. ISO 27001 would map them to Clause / Control Group / Control; CIS to Implementation
Group / Control / Safeguard. The engine only requires that the outermost level is what you want to
roll up and weight by, and the innermost is what you want to rate.

## How the engine stays neutral

Concretely, in `scripts/profile_analysis.py`:

- `load_core()` / `index_subcategories()` flatten any conforming hierarchy into
  `id -> {text, functionId, categoryId, examples, informativeReferences}`. Nothing downstream reads
  the framework file directly.
- `function_ids(core)` returns the outermost ids **in framework order**. Every place that iterates
  Functions calls it. There is no `["GV", "ID", "PR", ...]` literal in the computation path.
- `settings.functionWeights` is keyed by whatever ids the framework declares, and `init` populates
  it from `function_ids(core)`.
- `compute_gaps`, `compute_coverage`, `compute_completeness`, and `attention_lists` take
  `(assessments, settings, index)` and know nothing about CSF.
- The `.csfp` store holds `profile.frameworkRef` and Subcategory ids. It never copies framework
  content, so reference data can be corrected without touching user data.

The one deliberate exception is `CORE_EXPECTED` in `profile_analysis.py` — the 6/22/106/363
integrity invariants. Those are CSF-specific *validation* constants, not computation. A second
framework brings its own expected shape; the check is per-framework, not universal.

## Tiers are optional and framework-specific

`tiers` exists because CSF has them. The block carries its own `dimensions` and `levels`, so a
framework with a different rigor model — or none at all — simply omits or redefines it. Nothing in
the computation path depends on Tiers existing.

For CSF 2.0 the block is four levels × two dimensions, verbatim from NIST CSWP 29 Appendix B, with a
`guardrail` string stating that Tiers are a rigor characterization and never a maturity score. A
renderer should read that guardrail rather than reimplementing the caveat.

## What attaching a second framework requires

1. **A conforming data file** — the hierarchy, ideally with examples.
2. **Its own integrity constants** for `validate`.
3. **Nothing else in the computation path.** Gap, coverage, completeness, prioritization, snapshot,
   diff, and attention lists work unchanged.
4. **Renderer labels** — the operational dashboard says "Function" and "Category" in its chrome.
   Those become framework-supplied labels when a second framework lands. This is the one piece of
   real work outstanding, and it is presentational.

## Crosswalks, and why the data is already here

CSF 2.0 is a strong **hub** framework: the CPRT catalog ships Informative References mapping every
Subcategory to ISO/IEC 27001:2022, CRI Profile v2.0, CSF v1.1, SP 800-53, CIS, and others.

v1 **ingests all of them** into `informativeReferences` on every Subcategory, Category, and Function
— 106 of 106 Subcategories carry them. They travel through `analyze` on every gap row. v1 renders
none of it.

That is deliberate. It costs nothing at ingest time and it means the crosswalk views need no
re-ingest, no second data pull, and no schema migration — only rendering. Because CSF is the hub, a
single assessment can then be reported through an ISO or CIS lens without re-assessing anything.

**Stored as raw catalog lines**, exactly as published. Splitting them into `{source, reference}` was
deferred with intent: source names like `ISO/IEC 27001:2022` contain colons, so any split rule is
guesswork against an open-ended set of catalogs. A wrong parse baked into v1 data would be harder to
correct later than no parse at all.

That parse now exists, and it lives in build tooling rather than in shipped data: the raw strings
stay as published on every Subcategory, and `tools/crosswalks/author_catalogs.py` derives typed
edges from them into `references/crosswalks/`. Correcting the parse re-runs the builder; it never
touches user data or the Core.

## The crosswalk contract

This is enforced, not aspirational. `check_crosswalks()` in `scripts/profile_analysis.py` asserts it
from inside the shipped skill, and `tools/crosswalks/validate_crosswalks.py` owns the same rules at
build time. Both run in CI.

A **crosswalk** is two files per framework, in `references/crosswalks/`:

```jsonc
// <frameworkId>.catalog.json — what the other framework contains
{
  "frameworkId": "iso-27001-2022",   // must equal the filename stem
  "name": "ISO/IEC 27001:2022",
  "version": "2022",
  "license": "iso-copyright",        // provenance, all four required
  "provenance": { /* ... */ },
  "sourceExport": { /* which export, retrieved when */ },
  "groupings": [ {"id": "A.5", "label": "Organizational controls"} ],
  "controls": [
    {
      "id": "A.5.1",
      "label": "Approved security policy set, communicated",  // ours, not ISO's
      "groupingId": "A.5",                                    // must be declared above
      "labelSource": "cac-generated",
      "text": null                                            // see the licensing line
    }
  ]
}

// csf-2.0__<frameworkId>.map.json — how CSF reaches it
{
  "csfFrameworkId": "nist-csf-2.0",
  "overlayFrameworkId": "iso-27001-2022",
  "direction": "bidirectional",
  "mappingAuthority": "mixed-third-party",   // required
  "edges": [
    {"csfSubId": "DE.AE-02", "controlId": "A.5.24", "authority": "mixed-third-party"}
  ]
}
```

### Invariants

| Invariant | Why |
|---|---|
| `labelSource` is `cac-generated` for ISO and CIS, `verbatim-public-domain` for 800-53 | The licensing contract. ISO and CIS control titles are copyrighted; NIST publications are US Government works. |
| ISO and CIS controls carry **no** `text` | Shipping normative text would be redistribution. Enforced rather than trusted. |
| Every `label` is non-empty, every control `id` unique | A blank label renders as a bare ID no reader can act on. |
| Every `groupingId` resolves to a declared grouping | Otherwise a control silently vanishes from the theme rollup. |
| Every edge's `controlId` resolves to a catalog control | An unresolved edge is a coverage claim about nothing. |
| Every edge's `csfSubId` is a real CSF Subcategory | A stale id would drop that control's coverage to "unknown" while every count still looked correct. Needs the Core, so only the shipped check can make it. |
| Every edge carries an `authority` tag | Readers are entitled to know who asserted the mapping. |
| Counts match `CROSSWALK_EXPECTED` | A refresh of the NIST export is expected to move them; pinning makes that a deliberate review step instead of silent drift. |

### What a crosswalk is not

**The assessed framework is the only rated thing.** Crosswalks are read-only projection targets:
never rated, never stored in a `.csfp` or `.csfa`, never assessed directly. Coverage for an ISO
control is *derived* from the CSF Subcategories mapped to it and carries the weakest-link rule
(control = min of its mapped Subcategories; theme = mean of its member controls). That is a
projection of an existing assessment, not an audit or a certification, and every rendered view says
so.

Two consequences worth stating plainly. A crosswalk lens can only see what CSF maps — controls with
no CSF mapping must be assessed directly against the standard, and assessed CSF outcomes that no
control in the lens references drop out of that view. Both lists are reported rather than hidden.

**"Crosswalk" is not the Cyber AI Profile overlay.** That mechanism (`overlay enable`, IR 8596)
reweights the same Subcategories for AI relevance and *does* write to the store. Crosswalks project
outward to another framework and write nothing. Different verbs, different data, no shared state.

## What this seam is not

It is not a plugin API, and there is no framework registry. It is the discipline of keeping
framework knowledge in data and out of code, so that adding ISO 27001 later is a data task and a
labelling task — not a rewrite. That is the same bet `risk-register` makes with its deferred FAIR
seam: build the abstraction while it is cheap, populate it when there is a reason to.
