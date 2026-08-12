# Metrics Register — Data Model Reference

## Contents
- Store shape (`.mtr`, schema v1)
- Metric shape
- Reading shape
- Direction, and why it is required
- Thresholds
- Archetypes
- Change log (history)
- Date fields are canonical `YYYY-MM-DD`
- Derived-not-stored rule
- Cross-links

## Store shape (`.mtr`, schema v1)

```json
{
  "schemaVersion": 1,
  "family": "metrics-register",
  "meta": { "clientName": "", "owner": "", "scopeNote": "", "asOf": "YYYY-MM-DD" },
  "settings": { "cadenceDays": 90 },
  "metrics": [ /* Metric[] */ ],
  "readings": [ /* Reading[] — append-only */ ],
  "history": [ /* HistoryEvent[] — append-only */ ],
  "createdAt": "ISO-8601",
  "updatedAt": "ISO-8601"
}
```

The file is the single local source of truth. It carries the metric definitions, every reading
ever recorded, and its own change log, so the register can report movement over time with no
external store.

`family` distinguishes a `.mtr` from the other stores in the toolkit; a loader that is handed a
`.rr` or a `.csfp` refuses on this key rather than half-reading it.

`settings.cadenceDays` is the expected gap between readings. It is the *only* input to staleness —
see the derived rule below.

## Metric shape

```json
{
  "id": "M-001",
  "name": "Critical patches applied within SLA",
  "archetype": "patch-coverage",
  "unit": "percent",
  "direction": "higher-better",
  "threshold": { "target": 95, "warn": 90, "critical": 80 },
  "owner": "Head of Infrastructure",
  "csfSubcategoryIds": ["ID.RA-01"],
  "riskIds": ["R-006"],
  "vanityRisk": false,
  "viz": null,
  "notes": ""
}
```

- `id` — `M-###`, assigned on add, never reused.
- `archetype` — one of `patch-coverage`, `phishing-click`, `dwell-time`, `third-party`,
  `mfa-coverage`, `framework-maturity`, `backup-recovery`, `custom`, or `null`. The archetype is a
  *pointer* into `ciso-board-translation/references/metric-archetypes.md`; no archetype prose is
  copied here. See `archetype-bridge.md`.
- `unit` — `percent` | `count` | `days` | `currency` | `ratio`. Affects display only; no arithmetic
  depends on it.
- `direction` — **required**, see below.
- `threshold` — any subset of `target` / `warn` / `critical`; all optional, all in the metric's own
  unit. A metric with no thresholds has no status, which is a legitimate state, not an error.
- `vanityRisk` — the author's declaration that this number's shape is a big reassuring figure
  measuring effort rather than risk ("2M attacks blocked"). It is a flag on the *definition*,
  never inferred from a value.
- `viz` — optional. Which mark renders this metric: `bullet` | `progress` | `tank` | `gauge` |
  `sparkline` | `slope` | `line` | `column` | `bar` | `tile`. Omitted is the normal case; the
  resolved value is emitted by `analyze` either way, so a renderer never decides for itself.

### How `viz` resolves

In order — the first rule that applies wins:

| | Condition | Result |
|---|---|---|
| 1 | an explicit `viz` is set | that mark |
| 2 | no `warn` and no `critical` | `tile` |
| 3 | an archetype is set | its default, below |
| 4 | otherwise | `bullet` |

| Archetype | Default |
|---|---|
| `patch-coverage` | `bullet` |
| `phishing-click` | `bullet` |
| `dwell-time` | `line` |
| `third-party` | `bar` |
| `mfa-coverage` | `progress` |
| `framework-maturity` | `bar` |
| `backup-recovery` | `bullet` |
| `custom` | `bullet` |

Rule 2 outranks the archetype because a metric with no band is not a status. It renders as a bare
number in the measure colour — no gauge, no RAG — since colouring it would invent a limit nobody
agreed. Note that a lone `target` does not count: the engine bands on `warn` and `critical`, so a
`target` on its own is an aim, not a limit, and leaves the metric statusless.

Rule 1 outranks rule 2 because naming a mark is deliberate, and an override that is silently
ignored makes the field a suggestion. The colour contract is enforced separately by the renderer,
so an explicit `viz` changes how a metric is drawn and never what it claims.

**Resolved once, on purpose.** `analyze` emits `viz` on every metric so the operational view, the
executive view and the board pack all read the same answer. A renderer that picked its own mark is
how one number becomes a bullet on one page and a gauge on the next.

## Reading shape

```json
{ "metricId": "M-001", "period": "2026-Q3", "value": 91.4, "date": "2026-10-01",
  "source": "Tanium export", "actor": "R. Calder", "ts": "ISO-8601", "note": "" }
```

Append-only. A value is **never** silently overwritten: a correction is a new reading for the same
`period` carrying a `note`, and the later `ts` wins for derivation while the earlier one stays
visible. That is what makes "what did we report last quarter, and did we change it" answerable.

`period` is a free label (`2026-Q3`, `October`, `FY27-H1`). `date` is what the arithmetic uses;
`period` is what a human reads. Two readings may share a `period` (see corrections above); ordering
is always by `date`, then `ts`.

## Direction, and why it is required

`direction` is `higher-better` or `lower-better`, and there is no default.

Up is not good. A rising dwell time, phishing-click rate, or mean-time-to-detect is a metric
getting worse, and a register that guessed would state the opposite of the truth in board language.
Requiring the field means the wrong answer is unreachable rather than merely unlikely: `add-metric`
refuses without it, before the file is touched.

Every derivation that compares two numbers — trend, threshold status, breach — resolves through
`direction`. None of them infer it from the metric's name or archetype.

## Thresholds

`target`, `warn`, and `critical` are values in the metric's own unit, not bands. Which side of a
threshold counts as breached is decided by `direction`:

| direction | `warn` breached when | `critical` breached when |
|---|---|---|
| `higher-better` | `value < warn` | `value < critical` |
| `lower-better` | `value > warn` | `value > critical` |

So for `higher-better` a coherent set has `critical <= warn <= target`, and for `lower-better` the
order reverses. `set-threshold` refuses a set that is incoherent for the metric's direction — a
`warn` a value can never be on the wrong side of is not a threshold, it is a typo.

## Archetypes

The seven archetypes and everything they carry — the trap, the board ask, the receipt angle, the
Grade-A one-liner — live in `ciso-board-translation`. This store holds only the key. See
`archetype-bridge.md` for the mapping and for why it is a pointer rather than a copy.

`custom` and `null` differ: `custom` says the author considered the seven and this is not one of
them; `null` says nothing has been decided. Only `null` appears in the "untagged" attention list.

## Change log (history)

Append-only. Every mutation writes one event: `metric-added`, `reading-recorded`,
`threshold-set`, `metric-linked`, `metric-retired`. Each carries `ts`, `actor`, the target id, and
— for material changes — a `why`.

**Material changes require `--why`:** moving a threshold and re-tagging an archetype both change
what the same number *means*, and a register that lets either happen silently cannot answer "was
this always green, or did we move the line?". A refusal leaves the file byte-identical.

## Date fields are canonical `YYYY-MM-DD`

Every date is zero-padded `YYYY-MM-DD`. `2026-7-1` is refused on write, and the refusal happens
before the file is opened, so a rejected mutation cannot leave a partial store behind. Same rule
and same reason as `risk-register` — an unpadded date sorts wrongly as a string, and every
staleness and trend derivation here sorts by date.

## Derived-not-stored rule

Nothing in this list is ever written to the store. All of it is computed on demand from
`metrics[]`, `readings[]`, and `--today`:

- **trend** — direction-aware verdict against the prior reading (`gaining` / `holding` / `slipping`)
- **delta** — signed difference from the prior reading
- **threshold status** — `ok` / `warn` / `critical`, resolved through `direction`
- **staleness band** — distance from `settings.cadenceDays`, expressed as age
- **attention lists** — breached, worsening, stale, unowned, untagged, vanity
- **rollups** — by archetype and by CSF Function

Storing any of them would let the file disagree with itself the moment a reading lands.

**Staleness is age, never confidence.** A reading's age is derivable; the rate at which its
truth decays is not, and naming a band after that rate would commit this engine to exactly the
claim it declines to make. The vocabulary is enforced, not merely intended — see the board-safety
checks this skill inherits.

## Cross-links

`csfSubcategoryIds[]` and `riskIds[]` are plain id arrays. They are not validated against a
`.csfa` or `.rr` at write time, because the stores are independent files a user may not both
have — a link to an id that is not resolvable is reported by the renderer as unresolved, never
silently dropped.

---

*A Cyber Aware Creation · Not affiliated with NIST.*
