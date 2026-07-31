---
name: metrics-register
description: >-
  Maintain security metrics and KRIs as a living, trended record that persists in
  a local file, so the same numbers can be compared period over period. Define
  each metric with a required direction (higher-better or lower-better) and
  target/warn/critical thresholds, record dated readings with their source, and
  get deterministic direction-aware trend, threshold status, reading age, and the
  attention lists a metrics review works from — breached, worsening, stale,
  unowned, untagged, and vanity-flagged. Tags each metric to one of the seven
  board metric archetypes, cross-links to CSF Subcategories and register risks,
  and produces an operational review view plus a board section whose language
  comes from ciso-board-translation. Use when asked to track a metric or KRI, add
  this quarter's numbers, show how a metric is trending, find which metrics are
  breaching or going stale, or build the metrics section of a board pack. For a
  one-shot "translate this one number for the board" with nothing to store, use
  ciso-board-translation instead.
---

# Metrics Register

A system of record for the numbers a security leader reports. `risk-register` answers
*"what are our top risks and are they within appetite?"*; `nist-csf` answers *"how complete
is our programme against the framework?"*; this answers **"which of our numbers are moving
the wrong way, which ones are lying to us, and what decision does each force?"**

`ciso-board-translation` is stateless — it translates one number on demand and has no
memory of the last quarter. That memory is what this skill adds. It **composes** the
translation skill for every board-facing sentence; it never writes board language itself.

## When this skill applies, and when it does not

| The ask | Skill |
|---|---|
| "Track our patch coverage each quarter" | **metrics-register** |
| "Add this quarter's numbers" / "record October's reading" | **metrics-register** |
| "Which metrics are breaching or going stale?" | **metrics-register** |
| "Build the metrics section of the board pack" | **metrics-register** |
| "How do I say 87% patch coverage to the board?" — one number, nothing stored | `ciso-board-translation` |
| "What's the trap in a phishing click-rate metric?" | `ciso-board-translation` |
| "Score and band our risks" | `risk-register` |
| "How complete are we against CSF?" | `nist-csf` |

The boundary is **state**. If the answer needs last quarter's value, it is this skill. If
the answer is about one number in isolation, it is the translation skill.

## Workflow A — build and maintain the register

```bash
E=scripts/metrics_analysis.py

python3 $E init metrics.mtr --client "Acme" --owner "CISO" --cadence-days 90 --actor "you"

# direction is required and has no default — see below
python3 $E add-metric metrics.mtr --name "Critical patches within SLA" \
    --direction higher-better --archetype patch-coverage --unit percent \
    --owner "Head of Infrastructure" --actor "you"

python3 $E set-threshold metrics.mtr --metric M-001 --target 95 --warn 90 --critical 80 --actor "you"

python3 $E record metrics.mtr --metric M-001 --period 2026-Q3 --value 88 \
    --date 2026-07-01 --source "Tanium export" --actor "you"

python3 $E link metrics.mtr --metric M-001 --csf ID.RA-01 --risk R-006 --actor "you"
```

**`--direction` is required and there is no default.** Up is not good: a rising dwell time
or click rate is a metric getting worse. Nothing here infers direction from a name or an
archetype, because a default that is right six times out of seven produces a board sentence
stating the opposite of the truth on the seventh — and a confidently wrong trend reads
exactly like a right one.

**Corrections are new readings, not edits.** Record the corrected value for the same period
with a `--note`. The original stays in the file; the later write drives the derivation. That
is what keeps *"what did we report last quarter, and did we change it"* answerable.

**Moving a threshold needs `--why`.** It changes what the same number means, and a register
that allows it silently cannot say whether a metric was always green or the line moved.

## Workflow B — run a metrics review

```bash
python3 $E analyze metrics.mtr --today 2026-07-31 --out analysis.json
(cd renderers && python3 render_operational.py --in ../analysis.json --out ../review.html)
```

The review works down the attention lists: **breached**, **worsening**, **stale**,
**unmeasured**, **unowned**, **untagged**, **vanity**. Each list states its own membership
rule in the report, so a disagreement is about the rule rather than about the tool.

For each item the review captures the decision it forces — fund, accept, or re-scope — and
those become the `decisions[]` in the board sidecar.

## Reporting

```bash
# operational: the working view, no board language anywhere
(cd renderers && python3 render_operational.py --in ../analysis.json --out ../review.html)

# executive: composes ciso-board-translation via the sidecar
(cd renderers && python3 render_executive.py --in ../analysis.json \
    --translations ../metrics.board.json --out ../board.html)
```

Without `--translations` every narrative slot renders a labelled placeholder. **Placeholder
beats fabrication** — a board view that looks finished but was never written is the failure
this guards against. The sidecar conforms to the section contract
(`skills/board-pack/references/section-contract.md`): section `metrics`, per-item map keyed
by metric id, so the board-pack assembler ingests it with no re-plumbing.

## What the engine never does

- **Invent a number.** No interpolation, no carry-forward, no projection. A missing reading
  is a visible gap.
- **Invent a benchmark.** There is no industry average here.
- **Name a confidence.** Reading age is a distance from the cadence you chose. How likely a
  number is to still be true depends on what changed in the world, which the file does not
  contain — so the register reports the age and declines the inference.
- **Write board language.** That is `ciso-board-translation`'s job, always.

## Reference

| File | What it covers |
|---|---|
| `references/schema.md` | the `.mtr` store, every field, the derived-never-stored list |
| `references/metrics-method.md` | trend, threshold, staleness and rollup rules, worked |
| `references/archetype-bridge.md` | the archetype key → where its substance lives |

Verify the engine at any time with `python3 scripts/metrics_analysis.py self-test`.

---

*A Cyber Aware Creation · Not affiliated with NIST.*
