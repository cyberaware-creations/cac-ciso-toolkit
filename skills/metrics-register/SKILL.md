---
name: metrics-register
description: >-
  Maintain security metrics and KRIs as a living, trended record that persists in
  a local file, so the same numbers can be compared period over period. Define
  each metric with a required direction (higher-better or lower-better) and
  target/warn/critical thresholds, record dated readings with their source, and
  get deterministic direction-aware trend, threshold status, reading age, and the
  attention lists a metrics review works from — breached, worsening, stale,
  unowned, untagged, and vanity-flagged. Carries an archetype tag per metric that
  it resolves against ciso-board-translation at render time, cross-links to CSF
  Subcategories and register risks, and produces an operational review view plus
  a board section whose language comes from ciso-board-translation. Use when
  asked to track a metric or KRI, add this quarter's numbers, show how a metric
  is trending, judge whether a move between two readings is an improvement or a
  slip, find which metrics are breaching or going stale, or build the metrics
  section of a board pack. Do NOT use for a one-shot "translate this one number
  for the board" with nothing to store, or for questions about what a metric
  archetype means, what trap a kind of metric hides, or what the archetypes are —
  that content belongs to ciso-board-translation and is not duplicated here.
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

### What the register raises without being asked

The attention lists are the agenda a review works through. **Escalation is narrower**: what
should have interrupted somebody *before* the review. `analyze` carries them in the suite-wide
`CAC-EL-1 §1.3` shape with `subjectKind: "metric"`, so `board-pack` can put a breached metric
beside a crossed risk band without knowing anything about either skill's clock.

| trigger | fires when | severity |
|---|---|---|
| `threshold-breached` | past a limit its owner set — with how many consecutive readings it has been past it | `critical` past critical, `high` past warn |
| `sustained-slip` | moved the wrong way N readings running, **without** breaching | `medium` |

A breach **suppresses** the slip on the same metric: one movement reported twice reads as two
problems. Polarity holds throughout — a lower-better metric creeping *upward* inside its limits
is slipping, and that is exactly the movement worth seeing before a breach.

**Staleness is deliberately not a trigger.** An old reading is an age statement, not a claim the
number got worse — the same position this skill takes on `stale` and `risk-register` takes on
scores not expiring. A metric nobody re-measured has not moved for the worse; nobody knows
whether it moved at all, and escalating it would assert a decay the engine cannot observe. It
stays on the attention list, where a question about freshness belongs.

Tune per register, and the block travels with the store:

```json
"settings": { "escalation": { "sustainedSlipReadings": 2, "warnEscalates": true } }
```

Escalations are **derived on every run, never stored, never a history event.** They clear when
their cause clears. Nothing here blocks — a breached metric does not gate a command, and no
reading is changed on the strength of one.

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

### The axis a bullet is drawn on

A percent metric shares the 0-100 axis so a wall of them is comparable at a glance —
but only while that axis is readable. Two shapes break it, at opposite ends:

- **Banded near zero** — a click rate at 2/5/10. Its whole meaningful range is the
  first tenth of the bar. The shared ceiling is dropped and the mark scales to its
  own data.
- **Banded near the ceiling** — coverage at 85/90/95, MFA at 90/95/99, backup at
  95/98/99. On a 0-100 axis these spend **204 of 240 pixels** on the critical band,
  squeeze warn into **12**, and push every threshold past the right edge where the
  label placer drops them for collision. The bands are unreadable and their numbers
  unrecoverable at the same time.

For the second, the axis **floor** rises instead. Coverage at 85/90/95 goes from
204/12/24 pixels to **120/40/80**, and the 85 and 90 labels come back.

**A raised floor announces itself** — the axis prints its real value and the bar
carries a break glyph at the origin. Bar length reads as a proportion; a silently
truncated baseline makes it a proportion of nothing, which is the one way this mark
can lie outright.

**And the floor never rises above the data.** A reading below its own bands keeps
the full axis, so "well short" cannot be redrawn as "at the bottom of the range".

## The applicability profile (CAC-AP-1)

```bash
python3 $E analyze metrics.mtr --context context.json
```

Optional, and absent is the normal case — a run without one behaves exactly as it always did
and its output is byte-for-byte identical. The payload comes from
`business_context.py export <file.biz>`; this skill reads it as **data** and imports nothing
(§2.6).

What a profile narrows here is the **question set**, not the arithmetic. A reading is trended and banded identically whether it measures OT or payroll. So what
changes is which completeness questions this skill puts to you:

- **OT coverage** — gated on `otPresent`

A flag declared `false` removes its question and records the skip with the flag, the declarer
and the date, so an auditor can tell a question that was out of scope from one nobody asked
(§2.4). A flag that is **absent, or declared `null`, asks the question anyway** — §2.2, absence
asks more, because silently narrowing on undeclared data produces an assessment that looks
complete and is not.

**It asks; it does not answer.** Nothing in a `.mtr` records whether a metric measures OT: `archetype` is the metric's KIND, not its subject. A coverage figure would be inferred from data that is
not there, and this skill refuses to invent the number it asks for — the same rule that makes
it demand a direction and thresholds rather than guess. That is also why there is no *conflict* record here as
there is in `incident-materiality`: a conflict needs both sides stated, and one side is missing.

A payload from another contract version, or one carrying no decision, is **refused** rather than
ignored: `--context` was passed on purpose, and a silently un-narrowed run reads as a profile
that decided nothing applied.

## What the engine never does

- **Invent a number.** No interpolation, no carry-forward, no projection. A missing reading
  is a visible gap.
- **Invent a benchmark.** There is no industry average here.
- **Name a confidence.** Reading age is a distance from the cadence you chose. How likely a
  number is to still be true depends on what changed in the world, which the file does not
  contain — so the register reports the age and declines the inference.
- **Write board language.** That is `ciso-board-translation`'s job, always.

## Rendering under a client brand

Every renderer takes `--brand FILE`:

```bash
python3 renderers/render_board.py analysis.json report.html --brand northwind.json
```

```json
{"ink": "#101820", "muted": "#5A4436", "patina": "#C0701F", "bg": "#FAF7F2",
 "measure": "#8A4B12", "measureTrack": "#EFE0D2", "patinaText": "#8A4B12",
 "wordmark": "Northwind Group", "mark": "Northwind", "whiteLabel": true}
```

**It is refused rather than approximated.** A palette that leaves body text on the dark band
below 4.5:1, or the patina kicker on the dark band below 4.5:1, is rejected with every failing pairing named — not
the first, and not silently nudged into range. `whiteLabel` drops the maker's name and keeps
the "Not affiliated with NIST" line, because one says who built the document and the other is
a statement about the world.

**What does not follow the brand, deliberately:** the RAG status ramp. Red/amber/green is a
contract with the reader about severity, not styling the client is buying. Only the shell —
ink, muted, background, patina, and the steps derived from them — moves.

## Reference

| File | What it covers |
|---|---|
| `references/schema.md` | the `.mtr` store, every field, the derived-never-stored list |
| `references/metrics-method.md` | trend, threshold, staleness and rollup rules, worked |
| `references/archetype-bridge.md` | the archetype key → where its substance lives |

Verify the engine at any time with `python3 scripts/metrics_analysis.py self-test`.

---

*A Cyber Aware Creation · Not affiliated with NIST.*
