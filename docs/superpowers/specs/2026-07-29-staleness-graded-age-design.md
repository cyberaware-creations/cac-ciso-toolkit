# Staleness as Graded Age (not confidence, not expiry)

**Date:** 2026-07-29
**Status:** Approved design. Ready for implementation planning.
**Skills affected:** `nist-csf`, `risk-register`
**Supersedes:** the design note "Staleness as Confidence Decay", whose premise was based on a
misreading of the current implementation (see §1).

---

## 1. The premise correction

The originating design note — itself derived from external expert feedback — asserted that the
toolkit "treats freshness as effectively binary with an age-based guardrail (the 60% line)."
Both halves of that are false against the code.

**`nist-csf` already implements the non-expiry model.** `scripts/profile_analysis.py:562`, in the
docstring of the derivation layer:

> Ratings never expire; new material is what questions a rating, not the passage of time.

It is surfaced to the reader in `renderers/render_executive.py:111`:

> Ratings do not expire. Age is reported and the reader judges — a governance outcome and an
> asset inventory go stale at completely different rates.

A rating is questioned only when newer material is recorded against it (`revisit`, reason
`newer-material`) or when it carries no `confirmedAt` to compare against
(`undated-confirmation`). No timer alters any score.

**The 60% is not a currency threshold.** It is `scopeThresholdPct` — `assessed / inScope`
(`profile_analysis.py:683`) — a *coverage* guard that suppresses the headline coverage figure.
It has no relationship to age. The age parameter is separate and independent:
`ageThresholdDays`, default 180.

**Attribution already exists as a hard refusal.** `--source` and `--confirmed-by` are required to
set a Current rating (`profile_analysis.py:1468`). The who / what-evidence / when triple is
`confirmedAt` / `confirmedBy` / `source`. The "build decay and attribution on one substrate"
economy the note proposed is already half-spent.

The misreading is traceable to README bullets 75–81, where the scope-guard bullet sits directly
above the non-expiry bullet. A domain expert fused them on reading. That is a documentation
defect and §5 fixes it.

## 2. What genuinely holds up

Two real defects survive the correction.

**2a. The binary-flag critique lands on `risk-register`, not `nist-csf`.** `nist-csf` reports an
age *distribution* — `medianDays`, `oldestDays`, `olderThanThreshold`, plus a "stalest" list
ordered oldest-first. `risk-register` has none of it. `reviewOverdue` and `acceptanceDue` are
bare booleans (`renderers/_common.py:379-384`), there is no age reporting anywhere in the skill,
and a review three days overdue is indistinguishable from one three years overdue. The two
sibling skills disagree with each other about how to treat time. That asymmetry is the actual
defect the external feedback exposed.

**2b. `risk-register` has no last-confirmed date at all.** `reviewDate` is forward-looking — the
*next* review due. Per-risk age is not derivable today from any stored field.

## 3. The model

### 3.1 Age bands

One derivation, identical semantics in both skills, anchored to the existing configurable
threshold `T` (`ageThresholdDays`, default 180) so the engine holds exactly one notion of "old":

| band | boundary | at T=180 | at T=365 |
|---|---|---|---|
| `within` | `d ≤ T//2` | ≤ 90d | ≤ 182d |
| `approaching` | `d ≤ T` | ≤ 180d | ≤ 365d |
| `beyond` | `d ≤ 2T` | ≤ 360d | ≤ 730d |
| `wellBeyond` | `d > 2T` | > 360d | > 730d |

`olderThanThreshold` is unchanged and must equal `beyond + wellBeyond`. That identity is
asserted in the test suite so the two notions cannot drift apart.

**The band names are deliberately not confidence words.** `within` / `beyond` describe distance
from a cadence the reader chose. They state how old a determination is, never how sure anyone
should be that it is still true. See §7.

### 3.2 `nist-csf` changes

`_age()` (`profile_analysis.py:661`) gains a `bands` counter alongside its existing keys. Nothing
else in the derivation changes. `undated` (ratings carried from a v1 Profile with no
`confirmedAt`) continues to be counted separately and never guessed at.

### 3.3 `risk-register` changes

**New `confirm` subcommand and `risk-confirmed` event type.**

```
confirm <register.rr> <id> --why '...' [--review <date>]
```

- `--why` is required. Asserting "this is still right" is a material claim and belongs in the
  audit trail on the same terms as a score change.
- Appends `{ts, actor, riskId, type: "risk-confirmed", rationale}` to `history[]`.
- Changes no score, no status, no band.
- `--review` optionally sets the next `reviewDate` in the same breath, because that is the actual
  review-meeting workflow.

This exists so that "I looked at this and nothing changed" has a home. Today the only way to
record a re-affirmation is `set-score` at an identical value, which writes a `score-changed`
event where no score changed (`scripts/score_register.py:811` fires unconditionally) — corroding
the very audit trail the skill exists to keep honest.

**Derivation in `renderers/_common.py`**, from `history[]` only, alongside the existing per-risk
derived fields:

| field | meaning |
|---|---|
| `lastConfirmedAt` | newest `ts` among that risk's age-affirming events |
| `lastConfirmedBy` | that event's `actor` |
| `confirmationAgeDays` | days between `lastConfirmedAt` and `--today` |
| `confirmationBand` | the §3.1 band, or `null` |

**Age-affirming event types:** `risk-added`, `score-changed`, `risk-confirmed`, `risk-accepted`,
`acceptance-revalidated`. Each represents a human asserting something about the risk's magnitude
or its treatment decision.

**Not age-affirming:** `risk-updated` (notes, title), `theme-changed`, `status-changed`,
`settings-changed`, `snapshot-created`, `import-merged`, `register-created`, `risk-closed`,
`risk-reopened`, `risk-deleted`. This mirrors the rule already stated in
`nist-csf/references/schema.md:332` — that notes must not silently reset staleness, or the
"stalest" list is worthless.

A risk with no age-affirming event — a v1 register, a fresh `import-gaps` — yields
`lastConfirmedAt: null` and lands in an **undated** bucket reported as its own count. Never
inferred, never backfilled, on the same grounds that `nist-csf` refuses to backfill `confirmedAt`
from `lastReviewed`.

**`reviewOverdue` stays boolean and gains `reviewOverdueDays`.** A `reviewDate` is a deadline a
human committed to, so passing it is a *fact*, not decay. Confirmation age is the graded thing; a
missed commitment is binary. The day count exists so renderers can rank without changing the
semantics.

**New `--age-threshold` flag** on all three renderers, default 180, matching `nist-csf`.
Settings-level parity (`settings.reporting.ageThresholdDays`) is deferred.

### 3.4 State the stance in `risk-register`

`nist-csf` says "Ratings do not expire" in its README bullet, its schema, and on the executive
dashboard itself. `risk-register` says it nowhere — which is exactly why the two skills read as
disagreeing. The equivalent sentence goes into `references/schema.md`,
`references/dashboards.md`, and the dashboard hint text.

## 4. Surfacing

Governing principle: **operational views get the distribution, board views get one sentence.** A
board does not need an age histogram; it needs to know whether the picture in front of it is
fresh.

| View | Change |
|---|---|
| `nist-csf` operational | The "Stalest" panel (`render_operational.py:327`) keeps its list; each row gains its band. Its question line — *"Is this rating still true, or just old?"* — already says the right thing and is unchanged. |
| `nist-csf` executive | The age cell grid (`render_executive.py:96`) gains the band distribution. The existing hint text stays verbatim; it is now doing more work than it was. |
| `risk-register` operational | New "Confirmation age" panel in `attention_lists()` (`render_dashboard.py:79`) — band distribution plus the undated count. Per-risk cards gain `confirmed 42d ago · R. Calder` beside the existing review date. |
| `risk-register` board | One line in the executive summary block (`render_board.py:152`). Example: *"Of 24 live risks, 18 were confirmed within 90 days; 3 have not been confirmed in over a year (R-004, R-011, R-019); 2 carry no confirmation record."* |

The board line cites risk **IDs only, never titles**, which keeps it clear of the
provisional-title guard that `evals/board-safety.sh` enforces.

It belongs in the summary, not in "Decisions for the board" — it is a caveat on the whole
document rather than an ask. `_decisions()` (`_common.py:552`) already carries the missed-review
line, which is the correct home for "someone missed a commitment", and is unchanged.

## 5. Documentation

1. **README lines 75–81** — ~~restructure the two bullets that fused~~ **partly done**. The
   coverage-vs-currency disambiguation landed separately in #15: the scope-guard bullet now states
   explicitly that it is a *coverage* floor and not a currency one, and the non-expiry bullet names
   `ageThresholdDays` as reporting furniture. What remains for this work is the band detail — the
   non-expiry bullet absorbing `within` / `approaching` / `beyond` / `wellBeyond` once they exist.
   Do not add that wording before the bands ship; describing unbuilt behaviour is the same defect
   one document over.
2. **`risk-register`** — `SKILL.md`, `references/schema.md`, `references/dashboards.md`: document
   `confirm`, the age-affirming event list, the derivation, and the "scores do not expire" stance.
3. **`nist-csf`** — `references/schema.md`, `references/dashboards.md`: document the bands and the
   `beyond + wellBeyond == olderThanThreshold` identity.
4. **Version** — ~~reconcile the existing drift~~ **done**. #15 converged all four version strings
   on `0.4.2` and added `tools/check-versions.py`, run by the `manifests` job on every push and PR.
   This work still needs its own bump, but it is no longer something to remember: the guard fails
   any change under `skills/`, `assets/`, `LICENSE`, `NOTICE` or the manifest directories that does
   not move all four strings forward.

## 6. Testing

Baseline to beat, measured 2026-07-29: `risk-register` self-test 34/34,
`nist-csf` self-test 472/472.

- **`score_register.py` self-test** — `confirm` writes the correct event shape; `--why` is
  enforced; band edges tested off-by-one at exactly `T//2`, `T` and `2T`; non-affirming events
  provably do not reset age; an undated risk yields `null` rather than a guess.
- **`profile_analysis.py` self-test** — bands sum to `dated`; `beyond + wellBeyond ==
  olderThanThreshold`; `T=365` rescales the boundaries correctly.
- **`evals/board-safety.sh`** — assert the board freshness line renders, **and assert the
  rendered board HTML contains no confidence vocabulary.** An inverted test that fails if anyone
  later reintroduces the claim §7 declines to make.
- Existing suites stay green: `responsive.sh`, `contrast-check.mjs`, `python-compat.sh`.

## 7. Non-goals

Stated explicitly so they do not creep back in.

- **No "confidence" label anywhere.** The engine reports age; the reader judges decay. Age is
  derivable from stored data; confidence is not.
- **No suppression or invalidation on age, ever.** The scope guard suppresses on *coverage*.
  Nothing suppresses on time.
- **No per-control-class cadence.** (Open question 5 of the originating note, deferred there
  too.) Powerful, but it adds config surface to every Subcategory.
- **No change to acceptance expiry behaviour.** (Open question 6.) `_accepted_and_current`
  (`_common.py:480`) currently demotes a risk from `overAppetiteAccepted` to `overAppetiteOpen`
  once its acceptance passes `revalidationDate`. This is the one place a timer genuinely flips a
  determination, and it is **kept deliberately**: an acceptance is time-boxed by the human who
  granted it, so enforcing its stated expiry honours that judgment rather than overriding it.
  Recording this as a decision rather than leaving it implicit is the point.
- **No stored age fields.** The derived-not-stored rule holds in both skills; `history[]` remains
  the single source of truth for when anything was last affirmed.

## 8. Relationship to the external feedback

This design is **more conservative than the feedback that prompted it**. The reviewer proposed
labelled confidence decay — `Current — confidence degrading`, `Current (assumed)`. We ship graded
age with the confidence claim explicitly refused.

That is not a dilution. The reviewer's substantive point — that a binary flag overstates what age
tells you — is correct, and §3 fixes it where it was actually true (`risk-register`). But naming
an age band "confidence" commits the engine to a decay rate it cannot derive, on a Subcategory
whose real decay rate the tool already argues is unknowable in general
(`render_executive.py:112`). The honest answer to "you should be less binary" turned out to be
"yes — and we still will not claim to know what we cannot compute."
