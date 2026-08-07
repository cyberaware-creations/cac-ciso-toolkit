# The `.biz` store

Append-only with named review snapshots, matching every other register in the suite.

## Contents

- [Store shape](#store-shape)
- [The provenance wrapper](#the-provenance-wrapper)
- [Profile flags](#profile-flags)
- [The context record](#the-context-record)
- [Revenue, and the band ladder](#revenue-and-the-band-ladder)
- [Snapshots](#snapshots)
- [Derived-not-stored rule](#derived-not-stored-rule)
- [Single entity, and the reservation that makes groups cheap](#single-entity-and-the-reservation-that-makes-groups-cheap)

## Store shape

```json
{
  "schemaVersion": 1,
  "family": "business-context",
  "meta":      {"orgName", "preparedBy", "scopeNote", "fiscalYearEnd", "asOf"},
  "settings":  {"reviewCadenceDays": 365},
  "profile":   {"<flag>": {"value", "declaredBy", "declaredOn", "basis"}},
  "context":   {"segments", "crownJewels", "strategicGoals", "boardTolerance",
                "obligations", "revenue"},
  "history":   [{"event", "target", "ts", "why", "detail"}],
  "snapshots": [{"label", "ts", "why", "profile", "context"}]
}
```

Defaults merge **per key**, never wholesale: a file that set only `meta.orgName` keeps the
shipped values for everything else. Validation guards **writes** and never loads — a store
carrying a value the engine would refuse to write still opens, because locking an owner out of
their own document to punish a bad field helps nobody.

## The provenance wrapper

Every declared value carries who said it, when, and on what basis — the pattern `nist-csf` uses
for a confirmed rating.

```json
"aiInUse": {"value": true, "declaredBy": "R. Calder", "declaredOn": "2026-07-14",
            "basis": "Legal ops deployed a contract-review assistant in May"}
```

A **bare scalar is legal on read** and reported as unattributed. `declare` refuses to *write*
one: a flag that narrows another skill's question set and cannot say why is worse than an absent
flag, because absence asks everything.

**`value: null` is not `value: false`.** Null is *nobody has said*; false is *we looked, and it
does not apply*. See `applicability-contract.md` §2.2 — this distinction is the contract.

## Profile flags

Declared, never inferred. This skill does not decide that you are in scope for DORA; being an
EU entity does not set DORA scope, and a lawyer decides that.

| Group | Flags |
|---|---|
| Regulatory perimeter | `listedEntity` · `doraScope` · `nydfsScope` · `euEntity` · `ukEntity` |
| Technology posture | `aiInUse` · `otPresent` · `cloudPosture` · `regulatedDataHeld` |
| Third-party posture | `criticalVendorCount` · `concentrationConcern` |
| Shape and size | `primarySector` · `secondarySector` · `headcountBand` · `jurisdictions` |

The enumeration is **documentation, not a gate**. An unknown flag is accepted with a warning
rather than refused: the regulatory perimeter list will outgrow anything written here, and a
register that refuses tomorrow's regime is worse than one that records it unrecognised.

## The context record

| Fact | What it unlocks |
|---|---|
| `revenue` | The denominator `incident-materiality`'s financial factor had nowhere to get |
| `segments` | Impact expressed as *which part of the business*, not "high" |
| `crownJewels` | `{system, enables, atStake}` — the join between a technical asset and a business consequence |
| `strategicGoals` | Lets a board pack open on the business's year, not security's |
| `boardTolerance` | The sentence an appetite band was derived from — verbatim, attributed, dated |
| `obligations` | The commitments an exception is actually deviating from |

**`atStake` is required.** A system with `enables` but nothing at stake is an asset inventory
row, and an asset inventory is not what this file is for.

**`boardTolerance` is stored verbatim.** Never paraphrased, never summarised on write. This is
the sentence a risk appetite band was derived from — `risk-register` owns the band, this owns
the words behind it — and a paraphrase is a second-hand quote in the one place a reader most
needs a first-hand one.

## Revenue, and the band ladder

```json
"revenue": {"exact": 412000000.0, "currency": "EUR", "fiscalYear": "FY26",
            "declaredBy": "CFO", "declaredOn": "2026-08-07", "basis": "FY26 audited accounts"}
```

**Stored exact, rendered as a band.** The exact figure exists because a materiality denominator
must be honest and a banded one is not. The band exists because the rendered artifact is what
circulates, and a document naming revenue to the euro travels further than anyone intends.

Ladder: `<10m · 10-50m · 50-100m · 100-250m · 250-500m · 500m-1bn · 1-5bn · >5bn`

**Every boundary belongs to the band above it.** `10,000,000` is `10-50m`, not `<10m`: a ladder
whose edges fall the other way reports a company sitting exactly on a round number as smaller
than it is, and round numbers are where real revenue figures land.

`--render-revenue exact` overrides at render time, **and the override is written into the
provenance line**, so a reader can tell which document they are holding.

## Snapshots

`review --label --why` freezes **both** the profile and the context. A determination made in Q1
was made against Q1's profile — and a materiality assessment weighed against last year's
revenue base is as misread as one narrowed by last year's perimeter.

The newest snapshot is the **last appended**, not the latest timestamp. Snapshots are
append-only, so insertion order is the truth; sorting by `ts` would let two machines with
skewed clocks silently reorder which profile counts as current.

## Derived-not-stored rule

Computed on demand, never written:

- the revenue **band** — derived from `exact` at render, so it cannot drift from the figure
- `profileVersion` — the newest snapshot's label, or `unreviewed`
- escalations — `profile-stale` only (see `SKILL.md`)
- the applicable question set and its skips — `applies`

## Single entity, and the reservation that makes groups cheap

v1 assumes **one organisation with one regulatory perimeter**. That is right for the CISO this
suite serves best — a single firm, however many offices — and wrong for a group with several
regulated subsidiaries, where perimeter is genuinely per-entity.

**`profile` therefore sits at the top level of the document, never nested under an entity.**
This is a deliberate reservation, not an accident of layout. A future `entities[]` *inherits*
from the top-level profile, each entity carrying only the flags that differ — which makes the
change additive, leaves every existing `.biz` valid, and needs no migration.

Nest the profile under an entity now and that reversal costs a migration instead.

---

*A Cyber Aware Creation · Not affiliated with NIST.*
