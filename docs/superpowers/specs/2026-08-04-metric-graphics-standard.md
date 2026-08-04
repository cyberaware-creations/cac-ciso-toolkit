# CAC Metric Graphics Standard — catalog, colour contract, selection & consistency

**Date:** 2026-08-04 · **rev h** · **Authoritative on colour.**
**Reference implementation:** `cac_graphics.py` (16 marks, `self-test` = 34 checks, `gallery` mode).

---

## 1. Principles

1. **Match the mark to the data's job**, decided before colour.
2. **Bullet graph is the default for "value against a target."** Space-efficient, shows target *and* qualitative ranges, handles >100%, stacks side-by-side. We read **lengths and positions faster and more accurately than angles** (Cleveland) — the reason a dial is a poor comparison tool.
3. **Colour means severity, never decoration** — and only where severity is defined (§2).
4. **Boards want a handful of things, kept short:** RAG status, QoQ trend, value-vs-target, a risk heat map, what is committed by when.
5. **Executive ≠ detailed.** Phases, status, a today marker — never tasks, dependencies, resourcing or day granularity.
6. **Consistency is a feature.** A metric's shape is stable, so its graphic should be too.

## 2. Colour discipline — the three-way split

| Role | Colour | Used for |
|---|---|---|
| **Status** | RAG — good `#30915B`, medium `#e8c547`, high `#e08e0b`, critical `#c0392b` | *only* where thresholds or a declared status exist |
| **Measure** | **data blue `#2E6FA7`** (track `#D8E4F1`) | any measure with **no** declared thresholds |
| **Chrome** | **patina `#2FA98C`** | kickers, lockup, cover, section rules, the *today* marker — **never a data mark** |

### The governing rule: colour the mark by what the mark itself encodes

This resolves what would otherwise look like an inconsistency between two graphics:

- **Bullet — the bar IS a status mark, so it is RAG.** The bar's position relative to the threshold zones *is* the status: where the tip lands determines the band. Value in amber → amber bar.
- **Gantt — the bar is a MEASURE, so it is blue.** Bar length encodes duration and % complete, neither of which has a threshold. The phase's health ("at risk") is an *independent human judgement*, not derivable from the bar — so it gets its own **RAG status chip** and the bar stays blue.

The test: **does the mark's own value determine the status?** If yes, colour the mark. If the status is a separate declared judgement about the thing, give it a separate indicator and leave the measure blue. Painting a gantt bar red double-encodes length and health, and two at-risk phases swamp the chart.

**Rule 1 — colour follows the zone.** Value in the amber band → every indicator for that metric is amber; green → green; red → red. Includes the measure mark wherever that mark is a status mark (above).

- **The engine supplies the zone; the graphic never asserts one.**
- **Direction is not colour.** Improving/slipping is carried by geometry, the ↑/↓ arrow and the word. A metric can be improving and still amber.
- **A sign is not a status.** A delta is never coloured by a leading `+`/`−` — on a lower-better metric a rise is bad.
- **Zones are ordered by the metric's direction.** Higher-better runs crit→high→good; lower-better runs good→high→crit.

**Rule 2 — no thresholds, no RAG.** A bare measure has no agreed limit, so colouring it red or green invents one.

| Carries RAG (thresholds or declared status) | Renders data blue (no thresholds) |
|---|---|
| bullet bar + zones, gauge, progress-with-SLA | gantt bars (duration, % complete) |
| KPI tile **only** where the metric has declared bands | progress toward a goal with no agreed band |
| sparkline / slope / line where bands exist | a volume/vanity figure ("2.14M blocked") |
| risk exposure bars, L×I heat cells, band-mix | a count per period (incidents, over-appetite) |
| acceptance/exception status, materiality state, **gantt phase-status chip** | a timeline event with no status of its own |

### Why data blue (decided by measurement, not taste)

Six candidates run through the dataviz palette validator against the full RAG ramp (all pairs, light surface). The gate is the **normal-vision floor**: below ΔE 15 a pair is hard to tell apart even with full colour vision.

| Candidate | Result |
|---|---|
| Slate `#666D7C` | **FAIL** — ΔE 14.3 vs RAG green; also fails the chroma floor: it "reads gray" |
| Teal-blue `#1C6E7E` | **FAIL** — ΔE 13.8, worst of the set (a patina cousin keeps the exact confusion being removed) |
| Navy `#1F3A5F` | **FAIL** — outside the lightness band (L 0.35); tinted black |
| **Data blue `#2E6FA7`** | **PASS — chosen.** ΔE 17.9; the universal analytical blue — reads as information, not judgement |
| Indigo `#4C5B9A` | PASS — widest margin (20.4) |
| Steel blue `#3E7CB1` | PASS — ΔE 16.4, narrowest |

RAG owns red/amber/green and patina owns teal, so **blue is the only hue that cannot collide with a status**.

### Three measured findings that constrain every graphic

1. **RAG green↔red is ΔE 6.2 under deuteranopia** — inherent to *any* traffic-light ramp, not fixable by choosing better hexes. Hard evidence for the rule that **colour is always paired with a word**.
2. **RAG amber is 2.54:1 on white**, medium/yellow **1.64:1** — both below the 3:1 relief line. Amber and yellow always carry a visible label or value.
3. **Medium↔high (yellow↔orange) is ΔE 13.3 and cannot be fixed by darkening.** Tested: `#DDB02A` → 8.1, `#D4A017` → 4.6, `#CFA524` → 5.9 — all worse, because darkening moves yellow toward orange. The shipped `#e8c547` is the best of its family. **Do not change the brand hex;** instead label the band wherever all four appear adjacently (heat matrix, band-mix stacked bar).

## 3. The catalog

| # | Graphic | Job | Use when | Avoid when | Data needed |
|---|---|---|---|---|---|
| 1 | **KPI stat tile** | read one headline number | any single current value (+ delta) | comparisons/trends | 1 value |
| 2 | **RAG / YAG status** | grasp a state | over/under appetite, breach, pass/fail | conveying magnitude | a state + a word |
| 3 | **Bullet graph** *(default)* | value vs target with context | patch %, MFA %, click rate vs SLA | trend or ranking | value + target + warn/crit |
| 4 | **Progress / "fuel" bar** | completion toward a goal | remediation %, rollout, coverage | a metric with a target band → bullet | value bounded 0..goal |
| 5 | **Fuel-tank gauge** | "how full" for a lay audience | a single progress metric | comparison / precise read | 1 bounded value |
| 6 | **Radial gauge** | single hero KPI, dial metaphor | **at most one**, non-analytical audience | comparison, >1 gauge, precision, >100% | value + thresholds *(discouraged)* |
| 7 | **Sparkline** | trajectory inline | ≥4 periods, beside a number | <4 points; standalone hero | ≥4 readings |
| 8 | **Slope** | this period vs last | exactly 2 readings | >3 periods → line | 2 readings |
| 9 | **Line chart** | trend detail | ≥4 periods, inflections matter | 2–3 points | ≥4 readings, 1–3 series |
| 10 | **Column trend** | per-period counts | discrete periods | many periods; **RAG on a bare count** | a few periods |
| 11 | **Bar chart** | rank/compare items | top risks, load by owner | time series | comparable items |
| 12 | **Heat matrix (L×I)** | two-variable risk | likelihood×impact | a single metric | paired scores |
| 13 | **Stacked bar** | composition over time | risk band-mix QoQ | precise per-segment compare | a mix that sums |
| 14 | **Small multiples** | many metrics at once | a metric wall, same mark | when one metric is the story | many metrics, one type |
| 15 | **Milestone timeline** | *when did things happen* | incident chronology, deadline run | durations → gantt; >6 events | dated point events |
| 16 | **Executive gantt** | *what are we committed to, by when* | phases, % complete, milestones, what is late | task plans, dependencies, day granularity; >8 rows | phases + start/end + status |

## 4. Selection guide

- **One number** → KPI tile. **One state** → RAG chip.
- **A number against a target** → **bullet** (zones flip for lower-better).
- **Progress to a goal** → progress bar (fuel-tank for a lay audience).
- **A single dial** → radial gauge, *once*, reluctantly.
- **Change over time:** 2 points → **slope**; ≥4 inline → **sparkline**; ≥4 detailed → **line**; discrete counts → **column**.
- **Compare items** → bar. **Two-variable risk** → heat matrix. **Mix over time** → stacked bar. **Many metrics** → small multiples.
- **Time:** point events → **timeline**; start-and-end → **gantt**. The test is *duration*.

## 5. When NOT to use (hard rules)

- **No speedometer** for comparison, >1 together, precision, tight space, >100%, or a trend.
- **No RAG on a measure with no declared thresholds.** No colouring a delta by its sign.
- **No colour that contradicts the zone.**
- **No RAG on a gantt bar** — the bar is duration and progress. RAG lives only in the phase-status chip, always a dot **and** a word.
- **No patina on a data mark.**
- **A coloured measure bar must sit in its own surface lane**, never directly on the zone fills.
- **No unlabelled yellow or amber fill**; no four-band display without labels.
- **No pie/donut** for >3 slices. **No dual-axis chart, ever.**
- **No sparkline or line below 4 readings** — use a slope.
- **No PM-style gantt in a board pack**; **no timeline with >6 events**, never a timeline for durations.
- **No colour without a word**, no value-ramp on nominal categories, no clipped or colliding labels.

## 6. Consistency — chosen once, used everywhere

1. **Bind the graphic to the metric** via a `viz` field; the same metric renders identically in operational, executive and board-pack views.
2. **Archetype defaults** (override only deliberately):

   | Archetype | Default `viz` | Trend companion |
   |---|---|---|
   | patch coverage | bullet (higher-better, vs SLA) | slope / sparkline |
   | phishing click rate | bullet (lower-better) | slope |
   | dwell time / MTTD | line (or slope at 2 pts) + bullet vs target | — |
   | MFA / identity coverage | progress bar (or bullet) | slope |
   | framework maturity | bar by function / heat coverage | — |
   | backup / recovery tested | bullet + freshness chip | — |
   | third-party / vendor | bar (top vendors) / heat | — |
   | vanity / volume | **bare KPI number, data blue, no gauge, no RAG** | — |

3. **Same job → same mark on a page.** Two KPIs with targets are both bullets — never one bullet and one gauge.
4. **Fixed semantics:** RAG = severity only where declared; arrows ↑ improving / ↓ slipping; zones ordered by direction; bars start at zero; **the today marker is always a patina dashed line**.
5. **Sparklines are progressive:** suppressed below 4 readings, lighting up once history exists — the same metric's card gets richer over time without changing identity.

## 7. Where each time graphic earns its place

- **`incident-materiality` → milestone timeline.** Discovery → determination → 8-K filed → DORA final report; today marker = the disclosure clock. Only the determination and the filing carry status; other events are data blue.
- **`exceptions-register` → timeline or gantt.** Expiry and re-validation dates; overdue renders crit.
- **`nist-csf` / programme roadmap → executive gantt.** Gap-closure phases by quarter with % complete.
- **`board-pack` → both.**

## 8. Implementation notes

- `cac_graphics.py` — one function per catalog entry, self-contained inline SVG (print-safe, stdlib-only, 3.9-clean; same marks in HTML, PDF and slides). The gantt scales to its container.
- **The library never computes status.** Every function takes `sev` (or explicit thresholds) and falls back to data blue — rule 2 is enforced by the *default*, not by discipline. The measure hue is a single token (`MEASURE`).
- **Gantt.** Bar = `MEASURE_TINT` track (planned duration) + `MEASURE` fill (% complete). Right-hand columns: % complete in muted, then the **RAG phase-status chip** (dot + word: ON TRACK / WATCH / AT RISK / LATE). Milestones are ink diamonds; today is a patina dashed line.
- **Bullet.** The measure bar carries its **zone** colour, sitting in a **full-width white lane** — a halo hugging the bar reads as a glow and its rounded cap collides with the target tick, whereas a lane keeps the edge crisp where an amber bar crosses the amber band and makes the bar's end obvious. Zones use **mid tones** (near-white tints were invisible, which is why the measure appeared to align to nothing); the bar is thin within a taller band so zones stay readable above and below. `labels=False` serves small multiples; axis end-labels drop when the target label would collide.
- **Radial gauge.** A half-gauge sweeps 180°, so every zone arc is a *minor* arc and the SVG large-arc-flag must be **0** (it was 1, which drew every zone the long way round); the value sits **below the hub**, never under the needle.
- **Four-band alignment.** The library carries the full shipped risk ramp including medium `#e8c547`, so a medium-band risk renders yellow rather than borrowing a neutral slot.
- **Defects fixed and locked by `self-test`:** delta coloured by sign; sparkline/slope hard-coded red on an amber metric; column trend given invented thresholds; progress bar, fuel tank and KPI tile coloured with no thresholds; timeline events asserting status they did not have; patina used as a data colour; gantt bars RAG-coloured when they encode duration.

---

## Sources

- [Bullet graphs beat gauge charts — Tableau](https://www.tableau.com/about/blog/2015/2/bullet-graphs-beat-gauge-charts)
- [Not Gauges Again! — Peltier Tech](https://peltiertech.com/not-gauges-again/)
- [Bullet graph — Wikipedia (Few's specification)](https://en.wikipedia.org/wiki/Bullet_graph)
- [Cybersecurity board reporting: executive dashboard guide — Blue Radius](https://blueradius.io/cybersecurity-board-reporting-executive-guide)
- [7 cybersecurity dashboard KPIs for your board — Bitsight](https://www.bitsight.com/blog/7-cyber-security-dashboard-kpis-your-board-directors)
- [Executive report gantt chart template — Lucen](https://www.lucensoftware.com/templates/executive-report-gantt-chart)
- Internal: dataviz skill `choosing-a-form.md`, `anti-patterns.md`, `scripts/validate_palette.js`.

---

*A Cyber Aware Creation · Not affiliated with NIST.*
