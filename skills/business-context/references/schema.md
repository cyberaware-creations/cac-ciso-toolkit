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
| Regulatory perimeter | `listedEntity` · `secItem105Scope` · `doraScope` · `nydfsScope` · `nydfsExemption` · `euEntity` · `ukEntity` |
| Technology posture | `aiInUse` · `otPresent` · `cloudPosture` · `regulatedDataHeld` |
| Third-party posture | `criticalVendorCount` · `concentrationConcern` |
| Shape and size | `primarySector` · `secondarySector` · `headcountBand` · `jurisdictions` |

The enumeration is **documentation, not a gate**. An unknown flag is accepted with a warning
rather than refused: the regulatory perimeter list will outgrow anything written here, and a
register that refuses tomorrow's regime is worse than one that records it unrecognised.

**One flag, one fact.** `listedEntity` says shares trade on an exchange. `secItem105Scope` says
the organisation must file current reports on Form 8-K under the Exchange Act. They are
separate flags because they are separate facts and neither implies the other — an unlisted US
issuer reporting under s.15(d) is inside the Item 1.05 perimeter, and plenty of listed
companies are outside it. A single flag documented as both gated a four-business-day filing
deadline off the wrong one for twelve releases (BL-175), so `one-fact-per-flag.sh` now fails
the build on a definition that joins two facts, and on a battery gated by a flag that does not
name its regime.

`secItem105Scope` is **declared by counsel and never inferred**, on the same reasoning that
stops `incident-materiality` emitting a materiality verdict: a generated answer would be
discoverable alongside the filing it disagreed with. Undeclared means *not declared* — the
battery is asked and no window is computed. See CAC-AP-1 §2.4.1.

`nydfsExemption` is the same pattern with one difference worth knowing before you reach for
it. It records **which limb** of 23 NYCRR §500.19 counsel says applies — `500.19(a)`,
`500.19(c)`, `500.19(g)`, or `none` — rather than a yes/no, because the limbs reach different
sections: (a) exempts from §500.15 and **not** §500.12, (c) and (d) exempt from both, and only
(b), (e) and (g) reach the whole Part including §500.17.

**It gates no battery, deliberately.** A section-level exemption cannot gate a whole one:
wiring it to `nydfs-notification` would drop the notification question for a limited-exemption
firm that still owes it. `nydfs-notification` stays gated on `nydfsScope` alone, and this flag
is read by the exceptions register and the board receipts, which speak at section level. The
engine self-test asserts that it gates nothing, because the obvious "improvement" is to wire
it up and it would be silent.

## The context record

| Fact | What it unlocks |
|---|---|
| `revenue` | The denominator `incident-materiality`'s financial factor had nowhere to get |
| `segments` | Impact expressed as *which part of the business*, not "high" |
| `crownJewels` | `{system, enables, atStake}` — the join between a technical asset and a business consequence. Optionally `criticality` (this organisation's own ranking of what stops when this stops), `sensitivity` (what the system HOLDS, in the organisation's own classification) and `dependsOn` (components the system relies on, so a consumer can trace a supplied component back to the workflow). `criticality` and `sensitivity` are each a `declared()` record, free text with a **required basis** — see the note below on criticality's two shapes. Neither is checked against a scale this skill does not own. Every one is **absent unless declared**: missing means *not declared*, never *not critical* and never *not sensitive* |
| `strategicGoals` | Lets a board pack open on the business's year, not security's |
| `boardTolerance` | The sentence an appetite band was derived from — verbatim, attributed, dated |
| `obligations` | The commitments an exception is actually deviating from |

**`atStake` is required.** A system with `enables` but nothing at stake is an asset inventory
row, and an asset inventory is not what this file is for.

### ⚠️ `criticality` has two shapes on disk, and that is a decision

```json
"criticality": "high"                                       // written before v0.74.0
"criticality": {"value": "high", "declaredBy": "CISO",      // written after
                "declaredOn": "2026-08-09", "basis": "FY26 business impact analysis"}
```

`SCHEMA_VERSION` was **not** bumped, there is **no converter**, and **no store is ever
refused**. Both shapes are legal, permanently. `sensitivity` has only one shape because it was
introduced as a record in v0.68.2 and has no legacy behind it — the difference between the two
fields is *when each arrived*, not an inconsistency to tidy up.

That was decided as BL-216 Q-2 on 2026-08-10, against the cleaner alternative of bumping and
refusing the old shape. BL-169 D-2 requires that stopping part-way leaves a loadable store, and
a product whose argument is *your records persist and stay defensible* cannot ship a read that
refuses a CISO's existing file. The polymorphism is affordable because there is exactly **one
read point per consuming skill** — `declared_criticality()` in `vendor-register` and
`ai-register`, which reads either shape and refuses everything else.

**Do not resolve this by forcing one shape.** Forcing the record is the breaking read the
decision declined; forcing the string discards the basis. Both directions are covered by
`evals/criticality-shapes.sh`, one half each, and by CAC-TW-1 across both engines.

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
