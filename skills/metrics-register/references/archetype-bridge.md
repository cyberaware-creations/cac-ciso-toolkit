# Archetype bridge — where the substance actually lives

This file is a **pointer, not a copy**. Every metric in a `.mtr` store may carry an
`archetype` key; everything that key *means* — the trap the number hides, the board ask it
should end on, the receipt angle, the Grade-A one-liner — lives in
`ciso-board-translation/references/metric-archetypes.md` and is maintained there.

## Why a pointer

Two copies of the same guidance drift, and the copy a reader happens to open is the one
they act on. There is no mechanism that keeps a duplicate of the archetype prose in step
with the original, so the duplicate would silently become the older opinion. The register
stores the key and nothing else, and the executive renderer resolves the key at render
time by composing `ciso-board-translation`.

This is the same reasoning that keeps ISO and CIS control text out of the crosswalk
catalogues: hold the identifier, resolve the content from the one place that owns it.

## The mapping

| `archetype` in the store | Section in `metric-archetypes.md` |
|---|---|
| `patch-coverage` | 1. Patch coverage |
| `phishing-click` | 2. Phishing click rate |
| `dwell-time` | 3. Dwell time / MTTD |
| `third-party` | 4. Third-party / vendor risk |
| `mfa-coverage` | 5. MFA / identity coverage |
| `framework-maturity` | 6. Framework maturity score |
| `backup-recovery` | 7. Backup / recovery |
| `custom` | — none; the author considered the seven and this is not one |
| `null` | — nothing decided yet; appears in the `untagged` attention list |

`custom` and `null` are different answers and the register keeps them apart. `custom` is a
decision that has been made. `null` is a decision that has not, which is why only `null`
reaches the untagged list — a review can then ask the question rather than assume it was
already settled.

## What the register adds that the archetype does not

The archetype describes a *kind* of number. The register holds *this organisation's*
instance of it over time: its direction, its thresholds, its owner, its readings, and what
it links to. `ciso-board-translation` is stateless by design and has no memory of the last
quarter. That memory is the whole reason this skill exists, and the archetype is the seam
between the two.

## Direction is not inferred from the archetype

It would be tempting to derive `direction` from the archetype — dwell time is obviously
lower-better, patch coverage obviously higher-better. The register does not do this, and
`add-metric` refuses without an explicit direction.

The reason is the metrics that are *not* obvious, and the ones an organisation defines
against the grain. "Days since last successful restore test" and "restore tests completed"
are both backup-recovery metrics with opposite polarity. A default that is right six times
out of seven produces a board sentence stating the opposite of the truth on the seventh,
and nothing downstream can detect it, because a confidently wrong trend reads exactly like
a right one.

---

*A Cyber Aware Creation · Not affiliated with NIST.*
