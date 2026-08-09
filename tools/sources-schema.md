# CAC-RW-1 — the source manifest

**Applies to:** every skill in `cac-ciso-toolkit`
**Implemented by:** `tools/check-sources.py`, run in CI on the 3.9 floor
**In force since:** v0.52.0
**Sibling standards:** [CAC-GP-1](guard-proof-standard.md) · [CAC-LE-1](eval-lint-standard.md)

---

## The problem, stated exactly

Before this file, **exactly two source families in the product carried a freshness stamp**: the
crosswalk bundle (`sourceExport.retrievedAt`) and the Cyber AI Profile dataset. Every legal
citation, every NIST methodology publication and every statistic was undated at the point of use.

That is not a hypothetical. The v0.48.0–v0.51.0 verification pass read six reference families
against their primary sources and found **twelve defects**, every one of them an *amendment*
failure — the citation was right when written and the instrument moved underneath it:

- IR 8286 r1, 8286A r1 and 8286C r1 went from initial public draft to final; the repo described
  the drafts as "the revisions".
- The SEC's technical-detail carve-out was stated to cover the incident, which Item 1.05(a)
  compels.
- DORA's reporting windows had no instrument behind them at all, and a misread carve-out reached
  the engine as a **false overdue** on a regulatory clock.
- NYDFS deleted a compensating-controls route the toolkit still offered.
- SP 800-30 Rev. 1 turned out never to have defined the scoring model attributed to it.

**Not one of those was careless authorship, and not one would have been caught by re-reading the
repo.** Only opening the instrument catches them. This manifest exists so the next pass knows
what to open, and so the gap between passes is visible rather than silent.

The pattern being copied is already in the tree: the crosswalk bundle is the one place with a
stamp discipline, and it is the one place a validator enforces one. That is not a coincidence.

---

## The standard

### RW-1.1 Every skill ships a `sources.json`

`skills/<skill>/sources.json`, schema version 1. A skill that cites nothing ships an **empty
`sources` array** — that is the honest answer, not a missing file, and the check accepts it.
`board-pack` is the live example: it owns no data and computes nothing, so every fact arrives
from a producer that stamped it.

### RW-1.2 A row carries only what serves disclosure and the check

```json
{
  "id": "dora-rts-2024-1774",
  "label": "DORA ICT risk-management RTS",
  "publisher": "European Commission",
  "instrument": "Commission Delegated Regulation (EU) 2024/1774, Art. 3, point (d)(iii)-(iv)",
  "version": "OJ L, 25.6.2024; in force 15 July 2024",
  "checkedOn": "2026-08-08",
  "checkedBy": "claude-code",
  "gated": true,
  "reviewIntervalDays": 365,
  "usedFor": ["references/exceptions.md"],
  "renderedAs": "DORA RTS (EU) 2024/1774 Art. 3(d)"
}
```

Binding strength, volatility class, watch URL, watch method and monitoring state are **private
maintainer data and never ship**. The two gate fields — `gated` and `reviewIntervalDays` — are
policy rather than monitoring state, which is what lets the release gate run with no private
store behind it.

> **D-9, confirmed by the maintainer on 2026-08-08.** Shipping these two fields narrows the
> original rule that no cadence appears in the shipped file. The judgment is that a boolean and
> an integer are *policy*, not monitoring state, and that a self-contained release gate is worth
> the narrowing — it is what lets this ship complete rather than waiting on the private store.
> Recorded here rather than left in a chat log, because the alternative reading is defensible and
> a future maintainer is entitled to know it was decided rather than overlooked.

**`checkedBy: "claude-code"` means machine-verified against the primary source and *not*
human-reviewed.** It is deliberately not a person's name. A human sign-off replaces it with one.

### RW-1.3 `checkedOn` never renders

It is a claim about maintenance diligence, not a fact about the law. What renders is the
instrument identifier and, where it matters, the in-force date.

### RW-1.4 `renderedAs` is present only where a source actually renders

Its presence is what triggers the byte-equality check. Most non-legal sources have no
`renderedAs` at all, and **that absence is meaningful rather than incomplete**.

### RW-1.5 The renderer keeps its literal string; CI asserts byte-equality

Renderers do **not** read `sources.json` at runtime. Every shipped script in this repo runs
standalone with no cross-skill imports and a vendored `_common.py`; a runtime manifest dependency
would break that and invent a new failure mode where a missing file stops a board pack rendering.

Instead the manifest holds the canonical string and CI compares it byte-for-byte against the
renderer. One canonical value, no runtime coupling, drift caught at build time — the same
technique `CROSSWALK_EXPECTED` already uses to pin counts.

### RW-1.6 A stale gated source blocks a release, overridably with a recorded reason

`check-sources.py --release-gate` fails when a `gated` source is older than its
`reviewIntervalDays`. An override in `tools/release-overrides.json` must carry a reason, an owner
and a date; **an empty reason still fails.**

This is load-bearing for RW-1.3's converse: shipping precise, dated legal citations is only safe
while something keeps them current. If the gate is ever relaxed, rendered citations must fall
back to identifier-only, because a confident citation nobody maintains is worse than the vague
one it replaced.

### RW-1.7 An empty scan is a failure

Finding no manifests, or a manifest whose `usedFor` points at a file that no longer exists, fails
the run. The same anti-vacuity rule CAC-GP-1 applies to guards and CAC-LE-1 to suites.

---

## The four checks

| | Check | Fails when |
|---|---|---|
| **C1** | Presence | a skill has no `sources.json`, or it does not parse |
| **C2** | Shape | a required field is missing or empty, an id repeats within a skill, `checkedOn` is malformed or in the future, `gated` is true with no positive `reviewIntervalDays` |
| **C3** | Rendered citation | a `renderedAs` string is not found byte-for-byte in the files its row lists under `usedFor` |
| **C4** | `usedFor` exists | a listed path is not in the tree |

C3 is the one that catches the failure this standard is named for: a renderer whose citation
drifts from the manifest, or a manifest that was updated without touching the renderer.

---

## What this cannot do

**A manifest watches what a skill cites. It cannot see a withdrawn publication the skill does
not cite** — and that is the more dangerous class, because the defect arrives fresh rather than
sitting in existing text.

The worked example: **SP 800-61 Rev. 2 was withdrawn on 2025-04-03.** Its four-phase incident
lifecycle is the most-quoted structure in incident response and essentially every secondary
source still repeats it. This toolkit cites it nowhere, so there is nothing to fix — but the
first person to write incident-response content will reach for that lifecycle by reflex, and no
sources manifest would catch it, because r2 will never appear in one.

A **do-not-cite list** is the complement to this file and is tracked separately.

---

*A Cyber Aware Creation · Not affiliated with NIST.*
