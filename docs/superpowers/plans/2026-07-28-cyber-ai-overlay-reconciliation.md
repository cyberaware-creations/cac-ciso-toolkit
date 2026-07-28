# Cyber AI Profile Overlay — reconciliation against the actual repo

**Date:** 2026-07-28
**Reviews:** `strategy_cyber-ai-profile-overlay-design-2026-07-27.md` (rev B) and
`plans_cyber-ai-profile-overlay-implementation-plan-2026-07-27.md`
**Status:** analysis only — no code written, no plan approved

## Verdict

**The design is good and should survive largely intact. The implementation plan cannot be
executed as written** — it targets a repository that does not exist. Every file it names as
"modified" is absent, one core mechanism is arithmetically impossible on the shipped rating
scale, and it proposes writing overlay state into a file format that is not the store.

Separately, the design predates two features that shipped this week (`queue` and the scope
guard) and which change what "reorder the gap queue" even means. That is the redesign the
planning note anticipated.

This is the same reconciliation the accretion design needed and got. It is not a criticism of
the thinking; both documents were written against an imagined tree.

---

## 1. What is right, and should not be relitigated

These are load-bearing and fit the repo's existing doctrine well:

- **Three modes with `reorder` as the default.** The reasoning — NIST priority is *sequencing*,
  not maturity, so mapping it onto a target is a category error — is exactly the discipline this
  skill already applies to Tiers ("Tiers are rigor, never a maturity score"). Getting this right
  in rev B, after reading the source, is the single best decision in the document.
- **Overlay, not a framework.** `frameworkId` stays `csf-2.0`; no new Subcategories; no second
  assessment surface. This is consistent with `references/framework-abstraction.md`.
- **Swappable dataset with a version stamp, labelled draft-derived on the artifact, not just in
  docs.** A number carries where it came from — the same principle the attribution work is built
  on. Stamping `datasetVersion` into the store and snapshots is right.
- **`standardPracticesApply` sentinel** to target authoring effort. Good instinct, and it mirrors
  how `guidance.json` ships 15 deep entries with template fallback rather than 106 thin ones.
- **Disabled by default, with parity as the acceptance bar.** Correct, and testable.
- **"Enabling adds no assessment work."** Worth stating loudly; the reasonable assumption is the
  opposite.

---

## 2. Blocking corrections — substantive, not cosmetic

### 2.1 The floor mapping is off-scale. `floor` mode cannot be built as specified.

The plan maps proposed priority **1→4, 2→3, 3→2**. The native rating scale is **0–3**:

```
$ python3 scripts/profile_analysis.py set t.csfp ID.AM-01 --target 4 --rationale "test"
error: --target 4 is outside the scale 0..3 (0=Not Achieved, 1=Partially Achieved,
       2=Largely Achieved, 3=Fully Achieved)
```

Worse than a clamp: **there are two scales, and `settings.scale` is per-Profile**
(`references/scale-and-scoring.md`). Native Profiles are 0–3. Profiles converted from the
web tool via `csfa_compat.py` keep the source **0–4** scale, deliberately unrescaled, because
"a '2' on a 0–4 scale is not a '2' on a 0–3 scale, and there is no honest mapping between them."

So a fixed priority→target table means *different things* on two Profiles that both load in this
tool, and the design never mentions the second scale. This is precisely the error the repo has
already written a reference document to prevent.

**Options, in order of preference:**

1. **Drop `floor` from v1.** `advisory` + `reorder` deliver the design's stated value, and
   `reorder` is already the default. `floor` is explicitly labelled a CAC interpretation rather
   than NIST doctrine — shipping it later costs nothing and removes the hardest correctness
   question from the first increment.
2. **Define the floor scale-relatively** — e.g. priority 1 → `scale.max`, 2 → `scale.max - 1`,
   3 → `scale.max - 2`, clamped at 0. This works on both scales but silently means something
   different on each, which is the thing `scale-and-scoring.md` exists to stop.
3. **Refuse `floor` on non-native scales.** Honest, and cheap to implement, but leaves converted
   Profiles with a mode they can see and cannot use.

Recommend option 1 for v1, with option 3 as the eventual shape.

### 2.2 `.csfa` is not the store. `.csfp` is.

The plan proposes `references/example-acme-overlay.csfa` and speaks of "existing `.csfa` stores
without an `overlays` block". `.csfa` is the **web-tool export format**, read by the frozen port
in `scripts/csfa_compat.py`, whose gaps CSV is under a byte-parity contract
(MD5 `c3e8557e398e30f8da7ca48e6642d362`). It is an input, not a store.

The store is `.csfp` — `examples/example-profile.csfp` (used by `self-test`) and
`examples/example-profile-v2.csfp`. Adding an `overlays` block to a `.csfa` would either be
discarded on conversion or perturb the parity contract.

### 2.3 `schemaVersion` is the string `"2.0"`, and the coordination task is moot

Phase 0 T2 exists to coordinate `schemaVersion: 2` with the accretion branch. **Accretion has
landed** (PR #7, and #8 on top). There is one normalization entry point already — `load_store`
in `scripts/profile_analysis.py` — and it is the function to extend.

The value is `"2.0"` as a **string**, not integer `2`, and `SUPPORTED_SCHEMA = {"1.0", "2.0"}`.
Any comparison written against `2` will silently fail.

Good news: `check_store` does not reject unknown top-level keys, so an additive `overlays` block
is safe. That should be asserted, not assumed.

---

## 3. The file map is wrong in every row

| Plan names | Actually |
|---|---|
| `scripts/render_report.py` | `renderers/render_operational.py` **and** `renderers/render_executive.py`, sharing `renderers/_common.py` — **two** renderers, not one |
| `scripts/self_test.py` | no such file; tests are `_cmd_self_test` **inside** `profile_analysis.py`, run as `profile_analysis.py self-test` (351 checks) |
| `references/example-acme.csfa` | `examples/acme-manufacturing.csfa` |
| `references/deep-guidance.md` | `references/guidance.json` |
| `references/brand.md` | `assets/brand.md` |
| `references/report-layout.md` | `references/dashboards.md` |
| `references/roadmap-cyber-ai.md` | **does not exist** — nothing in the repo mentions cyber-ai, IR 8596, or overlays. T21 has nothing to supersede. |
| `tools/extract_cyber_ai.py` under `skills/nist-csf/` | `tools/` is at the **repo root**, not inside the skill |
| `visual_check.js` | `skills/risk-register/evals/responsive.sh` — headless Chrome over CDP, measuring width **and** WCAG AA contrast on resolved layouts, across 9 pages |

Also: `overlay list --store <path>` contradicts the CLI convention. Every command in
`profile_analysis.py` takes the store as a **positional** argument (`parse_flags` returns
`(pos, opt)`; `_require_store(pos, usage)`).

---

## 4. What the design predates — the actual redesign question

Two things shipped after these documents were written, and they change the core proposition.

### 4.1 There are now two orderings, and the design only addresses one

`reorder` mode says it reorders "the gap queue". As of v0.3.x there are two distinct orderings in
`analyze` output:

- **`gaps`** — the prioritized gap table, sorted `(-prioritizedGapScore, subcategoryId)`. This is
  what the design means, and reordering it is straightforward.
- **`queue`** — *what to confirm next*, in three bands: evidence-pending → revisit → cold-start.
  The cold-start band is ordered by `references/cold-start-rank.json`.

**Nobody has decided whether the overlay touches `queue`.** It is a real question, not a detail:

- The cold-start band is **CAC editorial judgment**, informed by NIST SP 1300, with its own
  disclaimer and provenance record. Layering NIST IR 8596 priority over CAC's own ordering means
  two editorial rankings competing, and the file that records "what informed this" would need to
  say so.
- `references/elicitation.json` (nine cold-start questions covering the ranked 37) has the same
  problem one level up. Should an AI-focused organization be asked different opening questions?
  Defensible either way — but it must be answered, because the alternative is that `elicit` and
  `queue` silently disagree with the gap table about what matters.

**Recommendation:** v1 reorders `gaps` only, and says so explicitly in
`references/cyber-ai-overlay.md`. The queue answers "what do I ask next?", which is an evidence
question, not a priority question — the overlay has nothing to say about which Subcategory you
have material for. Leaving `queue` alone is defensible on its own terms rather than by omission.

### 4.2 The scope guard interacts with `reorder`

Below `scopeThresholdPct` (60%) of in-scope Subcategories assessed, the headline coverage figure
is **suppressed** on both dashboards. An overlay that reorders a gap table on a Profile too
sparse to have a headline is not wrong, but it needs a stated position: AI-prioritized ordering
over four assessed Subcategories is ordering noise. Consider suppressing the Focus Area rollup
under the same guard, for the same reason.

---

## 5. The parity bar needs restating

Success criterion 1 — "`analyze` output byte-identical to the pre-change baseline against the
Acme golden file" — names the wrong artifact twice. Acme is a `.csfa`, and its parity contract is
the **gaps CSV MD5**, not `analyze` output.

The correct form: with the overlay disabled, `analyze` over `examples/example-profile.csfp` and
`examples/example-profile-v2.csfp` is byte-identical to the branch baseline, **and**
`csfa_compat.py self-test` (47 checks) still passes with the CSV MD5 unchanged.

T14's instinct — capture the baseline explicitly at branch start rather than assuming — is right
and becomes more important, not less: the baseline has moved twice this week.

---

## 6. Recommended restructure

1. **Reconcile the plan against the tree**, as the accretion plan did with its reconciliation
   table. Nothing in the design changes; the file map, the command surface, and the test idiom
   all do.
2. **Cut `floor` from v1.** Ship `advisory` + `reorder`. It removes the only arithmetically
   broken mechanism and the only mode that moves someone's numbers on preliminary-draft
   authority.
3. **Decide the `queue` / `elicit` question explicitly** and write the decision down, whichever
   way it goes.
4. **Split into two increments**, matching how accretion was delivered:
   - **1 — mechanical:** dataset + validator + `overlay` commands + `advisory`/`reorder` in
     `analyze` + parity assertions. Independently useful and fully unit-testable.
   - **2 — presentation:** badges, Focus Area rollup, provenance line, executive AI-posture
     paragraph, and the `responsive.sh` contrast gate. This increment is where the repo's
     documented blind spot lives — three render defects have reached users through it.
5. **Keep the extraction helper (T4) and the spot-check (T6).** Both are good, and T6's
   "any mismatch means re-verify everything" rule is the right severity.

## 7. Open gates before any of this starts

- **IR 8596 status is unverified.** `csrc.nist.gov/pubs/ir/8596` and two other NIST URLs
  returned **404** on 2026-07-28. I could not confirm whether the 2025-12-16 initial preliminary
  draft is still current. The comment period closed 2026-01-30, six months ago, so a second draft
  or final is plausible. **T1 remains a hard gate** — if the priorities moved, the entire dataset
  task changes, and that is 318 hand-verified values.
- **CAC guidance coverage for v1** — still an open number in the design. The `guidance.json`
  precedent is 15 deep entries plus fallback.
- **Whether `floor` ships at all**, per §2.1.
