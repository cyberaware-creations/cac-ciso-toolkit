# Method — the derivations, and the claims they decline to make

Everything here is computed on demand from `metrics[]`, `readings[]` and `--today`.
None of it is stored. The rules are stated so a reader can reproduce any figure the
register prints by hand.

## Trend

Compare the latest reading to the one before it, and resolve the verdict through
`direction`:

| | value rose | value fell | value unchanged |
|---|---|---|---|
| `higher-better` | `gaining` | `slipping` | `holding` |
| `lower-better` | `slipping` | `gaining` | `holding` |

`delta` is the raw signed difference, always `latest - prior`. It is **not** flipped to
match the verdict: a lower-better metric that worsened from 8 to 14 reports
`trend: slipping` with `delta: +6`. Hiding the sign would make the arithmetic
irreproducible, and the two fields answer different questions.

A metric with one reading reports `no-prior`, never `holding`. One point is not a trend,
and "holding" asserts stability that nothing in the file evidences.

## Threshold status

`target`, `warn` and `critical` are values in the metric's own unit. Which side counts as
breached is decided by direction:

| direction | `warn` breached when | `critical` breached when |
|---|---|---|
| `higher-better` | `value < warn` | `value < critical` |
| `lower-better` | `value > warn` | `value > critical` |

**Exactly at a threshold is not breached.** A metric at precisely its `warn` value reports
`ok`. The threshold is a line somebody chose, and landing on it is meeting it — the same
rule the age bands use, for the same reason.

**Critical outranks warn.** A value past both reports `critical` only.

Two states are not breaches and are not failures: `no-threshold` (none set — legitimate,
some metrics are watched without a line) and `no-reading` (nothing recorded yet).

## Staleness

Age is `--today` minus the date of the latest reading, banded against
`settings.cadenceDays`:

```
within       age <= cadence // 2
approaching  age <= cadence
beyond       age <= cadence * 2
wellBeyond   age >  cadence * 2
```

**This is a distance, not a confidence.** The register reports how old a number is. It
does not claim how likely that number is to still be true, because the rate at which a
metric's truth decays is not derivable from the metric — it depends on what changed in the
world, which the file does not contain. Naming a band after that rate would commit the
engine to exactly the claim it declines to make, and the board-safety eval enforces the
vocabulary rather than trusting it.

The same function, with the same boundaries, lives in `risk-register` and `nist-csf`.
The three copies are edited together; each skill's self-test is what pins them to the
same semantics.

## Attention lists

Membership rules, stated rather than implied:

| list | rule |
|---|---|
| `breached` | status is `warn` or `critical` |
| `worsening` | trend is `slipping` |
| `stale` | age band is `beyond` or `wellBeyond` |
| `unmeasured` | no readings at all |
| `unowned` | `owner` is empty |
| `untagged` | `archetype` is `null` (not `custom`) |
| `vanity` | `vanityRisk` is set on the definition |

A metric can appear on several. `breached` and `worsening` overlap often and deliberately:
a number that is both past its line and still moving the wrong way is a different
conversation from one that is past its line and recovering.

## Rollups

By archetype and by CSF Function, and they **count** rather than average.

Averaging across metrics would mean averaging a percentage, a day count and a currency
figure into a number with no unit and no meaning. So a rollup reports how many metrics sit
in the group, how many are breached, and how many are worsening. A reader can act on those;
a mean of 2,140,000 and 6.8 is not a fact about anything.

## Vanity

`vanityRisk` is a flag on the *definition*, set by the author, never inferred from a value.
It marks a number whose shape is a big reassuring figure measuring effort rather than risk
— "2.1M malicious emails blocked" — so a review can down-rank or reframe it rather than
open the board pack with it.

The engine does not guess at this, because the same figure can be vanity or substance
depending on what decision it is attached to, and only the author knows which.

## What the engine never does

- **Invent a number.** A missing reading is a visible gap. There is no interpolation,
  no carry-forward of last quarter's value, and no projection.
- **Invent a benchmark.** There is no "industry average" here. Inherited hard rule from
  `ciso-board-translation`.
- **Write board language.** Every board-facing sentence comes from a `--translations`
  sidecar; an unfilled slot renders a marked placeholder.

---

*A Cyber Aware Creation · Not affiliated with NIST.*
