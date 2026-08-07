# Exposure Lifecycle & Escalation — Specification and Implementation Plan

**Date:** 2026-08-06
**Suite:** Cyber Aware Creations security skills
**Status:** Layer 1 + Layer 2 ready for execution · Layer 3 requires source access

For agentic workers (e.g., Claude Code with Superpowers):
Use `superpowers:executing-plans` for Layer 2. Steps use checkbox (`- [ ]`) syntax for tracking.
Do not begin Layer 3 without the sibling skill sources in the worktree — those sections are
conformance requirements, not task specs, and were written without access to that code.

## Summary

Two things get built. **Layer 1** is a normative contract that every skill in the suite
implements as it is written — who owns the acceptance clock, what a lapse means, and what an
escalation is as a data structure. **Layer 2** implements that contract inside `risk-register`,
which is the skill that holds snapshots and therefore the only place register-wide trend can be
derived honestly.

The organising idea: **detection is automatic, action is not.** A worsening exposure surfaces
itself on a cadence with named evidence, and no one has to remember to look. Nothing is blocked,
nothing is auto-rescored, and no determination is made that a human did not make.

## Design corrections this plan encodes

Recorded because the first pass got them wrong and the reasons are load-bearing:

- **`revalidate` does not belong in risk-register.** `exceptions-register` is the system of
  record for the acceptance lifecycle. `risk-register` keeps a lightweight marker and exports
  one-way. Two homes for the same clock is how the two homes disagree. `acceptance-revalidated`
  stays inert in this skill's taxonomy — it exists so an imported event still classifies, not so
  this skill can emit it.
- **Expiry is already derived and surfaced.** `_common.py` computes `acceptanceExpired` and both
  dashboards render it. The residual gap is narrower than "expiry is inert."
- **A lapsed acceptance must not move a score.** Residual is an assessed number. Auto-reverting
  it would invent an assessment, which the skill's own guardrails refuse. Flag only, never block.
- **Escalation is a determination, not furniture.** It goes in `score_register.py` beside bands
  and appetite flags — not in the renderers, where `--age-threshold` lives.

## Layer 1 — Cross-suite contract (normative)

**Contract ID: CAC-EL-1 (Exposure Lifecycle).** Every suite skill that touches an acceptance, an
exception, a metric threshold, or a materiality determination implements the clauses below.

### 1.1 Clock ownership

Exactly one skill owns the authoritative clock for any given lifecycle:

| Lifecycle | Owner | Everyone else |
|---|---|---|
| Acceptance / exception re-validation and expiry | `exceptions-register` | Carries a read-only marker; exports one-way; never emits a re-validation event |
| Risk score, band, appetite, register trend | `risk-register` | Reads the scored output; never re-bands |
| Metric threshold breach | `metrics-register` | Reads the breach; never re-derives it |
| Materiality determination | `incident-materiality` | Reads the determination |
| Board narrative | `ciso-board-translation` | Never hand-writes board prose locally |

A skill that receives a marker it does not own **may flag it and must not update it.**
Cross-skill transfer is one-way and idempotent, keyed by a `source*Ref` field, following the
pattern already set by `export-acceptances` → `sourceRiskRef`.

### 1.2 Lapse semantics — flag only, never block

A dated obligation (`expiryDate`, `revalidationDate`, `reviewDate`, a metric breach window) that
is past its date is **lapsed**. Across the suite:

- A lapsed item is **still exported, still rendered, still counted.** It is never filtered out,
  never silently dropped, and never withheld from a downstream skill.
- A lapsed item **carries its lapsed state in every surface it appears on** — data payload, table
  row, board figure, stderr report. Silence is the failure mode this contract exists to prevent.
- A lapse **never mutates an assessed value.** No auto-rescore, no auto-status-change, no
  auto-revert.
- A lapse **never gates a command.** Nothing refuses because something else lapsed. (Contrast
  with the existing `provisionalScore` refusals, which guard against affirming an unassessed
  number — a different concern, and correct as-is.)

### 1.3 Escalation record — the shared shape

An escalation is a **derived, stateless determination.** It is recomputed from the file on every
run and never stored on the entity. Every suite skill that escalates emits this shape:

```json
{
  "subjectRef": "R-014",
  "subjectKind": "risk",
  "trigger": "band-crossed",
  "severity": "high",
  "since": "2026-05-31",
  "evidence": {
    "from": 9,
    "to": 15,
    "baseline": "Q2 2026 Board Review",
    "detail": "residual band medium -> high since the last snapshot"
  }
}
```

- `trigger` is from a closed vocabulary per skill (risk-register's is in §2.2).
- `severity` is derived deterministically from the trigger and the magnitude — never set by hand.
- `evidence` must name the comparison that fired it. An escalation a reader cannot audit is
  noise, and noise is how escalation gets muted by Q2.
- **No acknowledgement or mute field in v1.** An escalation clears when its underlying condition
  clears, and only then. A mute switch reintroduces exactly the burial the suite exists to
  prevent. (See Open decision OD-2.)

### 1.4 Event taxonomy handshake

> **Amended 2026-08-06, during execution of T2.** The original clause named
> `AGE_AFFIRMING` / `NON_AGE_AFFIRMING` and stopped there. `risk-register` has a *second*
> partition over the same vocabulary, and adding one event type to the first left the second
> incomplete. The suite caught it — loudly, which is the mechanism working — but a skill
> implementing the clause as written would have registered its type, passed the check the
> clause named, and still shipped a broken partition. What follows is what the clause should
> have said. Evidence and the original wording are at the end of this section.

Any new history event type, in any suite skill, must:

1. be registered in that skill's `KNOWN_EVENT_TYPES`, and
2. land in **exactly one side of every partition defined over that vocabulary** — not only the
   age-affirming one, and not only the partitions the implementer happens to know about, and
3. pass the partition checks **in every suite that asserts one** (union equals the known set,
   intersection empty, every emitted type classified).

**Find the partitions before you add the type, not after.** They are the sets whose union is
asserted to equal `KNOWN_EVENT_TYPES`:

```bash
grep -rn "KNOWN_EVENT_TYPES" skills/<skill>/ | grep -v "^.*KNOWN_EVENT_TYPES = "
```

Two properties of this that are easy to get wrong:

**A partition need not live beside the vocabulary.** In `risk-register` one pair
(`AGE_AFFIRMING` / `NON_AGE_AFFIRMING`) is in `scripts/score_register.py`, and the other
(`CHANGE_EXPLAINING` / `NOT_CHANGE_EXPLAINING`) is in `renderers/_common.py` — a different
layer, and one the engine has no reason to import.

**The checks need not live in the same suite.** The first pair is asserted by the engine's own
`self-test`; the second by `evals/confirmation-age.sh`. So **a green engine self-test is not
evidence the handshake held.** Run the skill's eval suites too. That asymmetry is exactly what
this amendment exists to stop someone rediscovering.

**Escalations emit no events.** They are derived. Only the human decision that answers one does.

#### Scope note, recorded 2026-08-06 — corrected the same day

**Corrected.** The first version of this note claimed `risk-register` was the only skill with a
history-event vocabulary and that the siblings carried no `history` array at all. That was
wrong, and wrong because of a bad grep rather than a bad reading: the siblings write history
through an `append_history()` helper with an `"event"` key, not the `"type"` key
`risk-register` uses, and the pattern I searched for missed all of it.

What is actually true is narrower and more useful. **Every skill in the suite has a history-event
vocabulary. Only `risk-register` has any partition over one:**

| skill | event types emitted | partitions over them |
|---|---|---|
| `risk-register` | 17 | **2** (`AGE_AFFIRMING`…, `CHANGE_EXPLAINING`…) |
| `nist-csf` | 12 | 0 |
| `incident-materiality` | 9 | 0 |
| `exceptions-register` | 7 | 0 |
| `metrics-register` | 5 | 0 |

So §1.4 binds `risk-register` fully today, and binds the other four the moment any of them needs
to answer a question *about* its event types — "which of these affirm freshness", "which may
caption a change on a board page". None of them asks such a question yet, which is why none has
a partition and why nothing is broken. The clause is what stops the first one being added
carelessly.

That also means Layer 3's `exceptions-register` work is smaller than this plan assumes: it
already emits `{kind}-revalidated` from a `revalidate` command that requires a rationale and
refuses without one. See the conformance audit below.

<details>
<summary>The original clause, for the record</summary>

> 1. be registered in that skill's `KNOWN_EVENT_TYPES`, and
> 2. land in **exactly one** of `AGE_AFFIRMING` / `NON_AGE_AFFIRMING`, and
> 3. pass the skill's self-test partition checks (union equals the known set, intersection
>    empty, every emitted type classified).

Adding `escalation-policy-changed` satisfied all three as written, and
`evals/confirmation-age.sh` check 49 — *"every known event type is classified either way"* —
still failed, because `CHANGE_EXPLAINING | NOT_CHANGE_EXPLAINING` no longer equalled
`KNOWN_EVENT_TYPES`.

</details>

## Layer 2 — risk-register implementation

### File map

**Modified files:**

- `scripts/score_register.py` — settings defaults, `set-escalation` command, baseline/velocity/
  escalation derivation, `escalations` CLI command, `export-acceptances` lapse reporting,
  self-tests
- `renderers/_common.py` — expose escalations to renderers from the scored payload
- `renderers/render_dashboard.py` — escalation section in the operational attention lists
- `renderers/render_board.py` — escalation KPI tile and decisions-needed rows
- `references/schema.md` — `settings.escalation`, the escalation record, lapse semantics
- `references/history-and-review.md` — escalation in review workflow step 2; trend/velocity
  section
- `references/dashboards.md` — escalation surfaces on both dashboards
- `SKILL.md` — escalation in the build workflow and the command list
- `examples/example-register-v2.rr` — fixture gains an escalating risk and a lapsed acceptance

**New files:** none. This is additive to existing modules by design — the determinism story
depends on scoring and escalation living in one script with one self-test.

### Pre-flight checks

- [x] Working from the suite repo, not the installed plugin copy
- [x] `python3 scripts/score_register.py self-test` passes on main before any change
- [x] `bash evals/python-compat.sh` passes (3.9 floor, stdlib only)
- [ ] Git worktree created — not used; executed directly on `main` at 1543ca7 with a clean tree, per the session's working agreement

## Phase 1 — Settings and taxonomy foundation

### T1: Add `settings.escalation` with defaults

**Files:** Modify `scripts/score_register.py` (`_cmd_init`, `load_register`)

**Rationale:** Thresholds must be per-register and must travel inside snapshots, which capture
settings wholesale. Putting them anywhere else makes a snapshot un-reproducible.

**Implementation notes:**

Defaults, chosen to fire on real drift and not on noise:

```python
ESCALATION_DEFAULTS = {
    "sustainedWorseningSnapshots": 2,   # consecutive worsening snapshots, no band cross
    "appetiteDwellDays": 180,           # continuously over appetite this long
    "bandCross": True,                  # any residual band worsening escalates
    "lapsedAcceptance": True,           # acceptance past expiryDate escalates
}
```

- In `load_register`, apply with `setdefault` alongside the existing
  `obj.setdefault("history", [])` pattern so every existing v2 register keeps loading unchanged.
  **Do not bump `schemaVersion`.**
- `_cmd_init` writes the block explicitly so a new register is self-documenting.

**Verification:**

- `python3 scripts/score_register.py init /tmp/t.rr --client X --assessor Y` → file contains
  `settings.escalation` with all four keys
- `references/example-register.rr` (v1) and `examples/example-register-v2.rr` both still load and
  score with no error
- self-test still green

- [x] T1 complete

### T2: Add `set-escalation` command and its event type

**Files:** Modify `scripts/score_register.py` (`COMMANDS`, `KNOWN_EVENT_TYPES`,
`NON_AGE_AFFIRMING`, new `_cmd_set_escalation`)

**Rationale:** A threshold change silently rewriting which risks escalate is the same corrosion
`confirm` exists to prevent. Changing the policy is a material change and belongs in the log.

**Implementation notes:**

- Event type `escalation-policy-changed`. It asserts nothing about any risk's freshness, so it
  goes in `NON_AGE_AFFIRMING` — with `--why` required, matching every other material mutation.
- Follow `_cmd_set_theme`'s shape: `parse_flags`, validate, mutate, `_append_event`,
  `save_register`.
- Integer flags via the existing `_int_opt`; reject values below 1.
- Usage:
  `set-escalation <reg.rr> [--sustained N] [--dwell-days D] [--band-cross on|off] [--lapsed-acceptance on|off] --why '...'`

**Tests to add to `_cmd_self_test`:**

- `set-escalation` is reachable from `COMMANDS`
- `escalation-policy-changed` is in `KNOWN_EVENT_TYPES` and classified exactly once
- refuses without `--why`, leaving the file byte-identical (reuse the existing `_rejects` helper)
- refuses `--sustained 0`

**Verification:** `python3 scripts/score_register.py self-test` — all new checks green, partition
checks still green.

- [x] T2 complete

**Phase 1 checkpoint:** existing registers load unchanged, policy is settable and logged.

- [x] Phase 1 checkpoint passed

## Phase 2 — Derivation

### T3: `_snapshot_baseline(reg)` helper

**Files:** Modify `scripts/score_register.py`

**Rationale:** Every trigger compares against the most recent snapshot. One helper, one
definition of "baseline," so triggers can't drift apart.

**Code skeleton:**

```python
def _snapshot_baseline(reg: dict) -> tuple[dict, str]:
    """Return ({riskId: residualExposure}, snapshotLabel) from the newest snapshot.

    Empty dict and "" when the register has no snapshots — a register with no baseline
    escalates nothing rather than escalating everything against zero.
    """
```

**Implementation notes:**

- Newest = last element of `reg["snapshots"]` (append-only, so ordering is insertion order — do
  not sort by `ts`, which would reorder on a clock skew).
- Read residual exposure from the snapshot's stored `data.risks`, recomputing with `exposure()`
  rather than trusting a stored field.

**Verification:** self-test — no snapshots yields `({}, "")`; a register with two snapshots
yields the newer one's label.

- [x] T3 complete

### T4: `velocity(reg)` — per-risk direction

**Files:** Modify `scripts/score_register.py`

**Rationale:** `history-and-review.md` specifies velocity but nothing computes it. Escalation
needs it, and the board narrative already asks for it.

**Code skeleton:**

```python
def velocity(reg: dict) -> dict:
    """{riskId: {"delta": int, "direction": "worsening"|"improving"|"steady",
                 "from": int, "to": int, "baseline": str}}"""
```

**Implementation notes:**

- Direction from the sign of `to - from`. A risk absent from the baseline is `steady` with
  `delta: 0` and `baseline: ""` — new risks are not "worsening," they are new.
- Higher exposure is worse. Do not invert.

**Verification:** self-test with a two-snapshot fixture covering worsening, improving, steady,
and not-in-baseline.

- [x] T4 complete

### T5: `escalations(reg, today)` — the trigger engine

**Files:** Modify `scripts/score_register.py`

**Rationale:** The core of the contract. Deterministic, stateless, auditable.

**Trigger vocabulary (§2.2 of the contract, closed set):**

| Trigger | Fires when | Severity |
|---|---|---|
| `band-crossed` | residual band is worse than at the baseline snapshot | `critical` if the new band is critical, else `high` |
| `sustained-drift` | residual exposure worsened across N consecutive snapshots without crossing a band (N = `sustainedWorseningSnapshots`) | `medium` |
| `appetite-dwell` | continuously over appetite for more than `appetiteDwellDays`, measured from the earliest snapshot in which it was already over | `high` |
| `acceptance-lapsed` | `acceptance.expiryDate` is past `today` | `high` |

**Implementation notes:**

- Signature `escalations(reg: dict, today: str) -> list[dict]`, returning the §1.3 shape. `today`
  defaults to UTC at the CLI boundary, never inside the function — match the renderers' rule.
- Reuse `_overdue`-equivalent lexical date comparison; canonical `YYYY-MM-DD` only, per the
  existing date rule. An unpadded date sorts wrong and reads as "not due."
- `band-crossed` and `sustained-drift` are mutually exclusive: if the band crossed, that is the
  escalation. Do not emit both for one risk.
- Closed risks are skipped for every trigger **except** `acceptance-lapsed` — a closed risk
  carrying a live acceptance is exactly the state worth seeing.
- Risks with `provisionalScore` are skipped for score-derived triggers and reported separately in
  the summary as `escalationsSuppressedProvisional`. Escalating off an import seed would be
  escalating off a number nobody assessed; hiding that suppression would be the silence §1.2
  forbids.
- Sort output by severity (`critical`, `high`, `medium`), then `subjectRef`, for stable
  rendering.

**Tests to write first:**

- `band-crossed` fires on medium→high, does not fire on high→medium
- `sustained-drift` fires at exactly N, not at N-1
- `band-crossed` suppresses `sustained-drift` on the same risk
- `appetite-dwell` respects a changed `appetiteDwellDays`
- `acceptance-lapsed` fires on a closed risk
- `provisionalScore` risk produces no score-derived escalation but increments the suppressed
  count
- a register with no snapshots produces no score-derived escalations
- every returned record validates against the §1.3 shape (all six keys present)

**Verification:** self-test green, including a full-shape assertion on one record.

- [x] T5 complete

### T6: Wire escalations into the scored payload

**Files:** Modify `scripts/score_register.py` (`score_register`, `summarize`)

**Rationale:** Renderers must consume escalations, never re-derive them — the same rule that
keeps banding out of the renderers.

**Implementation notes:**

- `score_register(reg, today="")` gains an optional `today`; when empty, score-derived
  escalations still compute (they need no date) and `acceptance-lapsed`/`appetite-dwell` are
  skipped rather than guessed. Callers that care pass `--today`.
- Add top-level `"escalations": [...]` to the returned dict.
- Add to summary: `"escalations": {"critical": n, "high": n, "medium": n, "total": n}` and
  `"escalationsSuppressedProvisional": n`.
- **Do not change the existing summary keys.** `snapshot` stores `scored["summary"]` verbatim, so
  a rename silently invalidates every historical snapshot's comparability.

**Verification:** `score <reg> --json` includes both new blocks; existing keys byte-identical on
the v2 example fixture (diff the JSON against a pre-change capture).

- [x] T6 complete

**Phase 2 checkpoint:** `score --json` carries escalations; no existing output changed.

- [x] Phase 2 checkpoint passed

## Phase 3 — Surfaces

### T7: `escalations` CLI command

**Files:** Modify `scripts/score_register.py` (`COMMANDS`, new `_cmd_escalations`)

**Implementation notes:**

- `escalations <reg.rr> [--today YYYY-MM-DD] [--json]`, mirroring `_cmd_score`'s two output
  modes.
- Human mode: one line per escalation — severity, subject, trigger, and the evidence detail
  string. Print the reference date and its zone, as the renderers do.
- **Exit code 0 even when escalations exist.** A non-zero exit would make this a gate, and §1.2
  says flag, never block.
- When there are none, say which baseline was compared against — "no escalations" against no
  snapshot means something different than against last quarter's.

**Verification:** command runs against `examples/example-register-v2.rr` and prints the fixture's
escalations; `--json` output parses and matches the `score --json` block exactly.

- [x] T7 complete

### T8: Report lapsed acceptances on export

**Files:** Modify `scripts/score_register.py` (`_cmd_export_acceptances`)

**Rationale:** Today the command reports acceptances that are incomplete but says nothing about
one that expired in March, so a dead acceptance lands in the exceptions intake looking current.

**Implementation notes:**

- **Flag only.** The row is still exported. `expiryDate` already travels in the payload, so the
  receiving skill has what it needs to flag it too.
- Add a `--today` flag (default UTC today) and, after the existing incomplete loop, a second
  stderr report: `  lapsed {rid}: acceptance expired {date} — exported as-is.`
- Print a count line to stdout only in the `--out` branch, matching the existing
  `"Wrote {out} — N acceptance(s)"` style, so piped JSON stays clean.
- Do not add a `lapsed` key to the payload objects until the `exceptions-register` intake schema
  is confirmed to tolerate unknown keys. **See OD-1.**

**Tests:** an expired acceptance is present in the emitted rows and named on stderr; a current
one appears on neither report.

**Verification:** `export-acceptances examples/example-register-v2.rr --today 2027-02-01
>/dev/null` prints the lapsed line to stderr and the row count is unchanged from
`--today 2026-01-01`.

> **Re-dated during execution, 2026-08-06.** The plan said `--today 2027-01-01`, written
> against the installed plugin copy. This repo's fixture has its three acceptances expiring
> 2027-01-15, 2027-02-01 and 2027-07-31, so nothing is lapsed on 2027-01-01 and the lapsed
> line could never print. 2027-02-01 exercises the same property — lapsed line on stderr,
> row count unchanged — against a date this fixture can actually reach. Substance unchanged;
> only the date moved. Approved by the plan owner before T9.

- [x] T8 complete

### T9: Render escalations on both dashboards

**Files:** Modify `renderers/_common.py`, `renderers/render_dashboard.py`,
`renderers/render_board.py`

**Implementation notes:**

- `_common.py`: pass escalations through from the scored payload onto the derivation object.
  **Derive nothing here** — no thresholds, no comparisons.
- Operational dashboard: a new attention-list section beside the existing overdue/stale lists,
  following the `render_dashboard.py` attention-list tuple pattern (predicate + label lambda).
  Show trigger and evidence detail, not just a count.
- Board dashboard: an escalation count in the KPI row, and escalations feeding the "decisions
  needed" rows. Narrative text comes from `ciso-board-translation` via `--translations` as usual
  — do not hand-write board prose in a renderer, and render marked placeholders when the sidecar
  is absent.
- `--offline` must keep working; assets stay self-contained.

**Verification:**

- `bash evals/decisions-render.sh` and `bash evals/board-safety.sh` pass
- `bash evals/responsive.sh` passes at 320px (the escalation table adds a column — this is the
  shape that overflows)
- `node evals/contrast-check.mjs` passes for any new severity colour, CVD-safe per
  `assets/brand.md`

- [x] T9 complete

**Phase 3 checkpoint:** all evals green; escalations visible on both surfaces and on stderr.

- [x] Phase 3 checkpoint passed

## Phase 4 — Documentation and fixtures

### T10: Update the fixture

**Files:** Modify `examples/example-register-v2.rr`

**Implementation notes:** the worked example is the few-shot for the whole model, so it must now
exercise: two snapshots, one risk that crosses a band between them, one that drifts without
crossing, one long-dwelling over-appetite risk, and one lapsed acceptance. Keep it a realistic
register — do not pad it to hit every branch.

**Verification:** `escalations examples/example-register-v2.rr --today 2026-07-31` emits one
record per trigger type.

- [x] T10 complete

### T11: Update the reference docs

**Files:** Modify `references/schema.md`, `references/history-and-review.md`,
`references/dashboards.md`, `SKILL.md`

**Implementation notes:**

- `schema.md` — `settings.escalation`, the escalation record shape, the lapse rule, and an
  explicit note that escalations are derived and never stored.
- `history-and-review.md` — fill in the trend/velocity section with the now-implemented
  derivation; add escalations to review workflow step 2's attention list.
- `dashboards.md` — the two new surfaces.
- `SKILL.md` — `set-escalation` and `escalations` in the command block; one line in "What good
  looks like" tying escalation to the living-record principle. Restate that `revalidate` lives in
  `exceptions-register`, so the next reader doesn't re-propose it.

**Verification:** every command shown in `SKILL.md` runs as written against the v2 example.

- [x] T11 complete

### T12: Full self-test and eval sweep

**Verification:**

- `python3 scripts/score_register.py self-test` — green
- `bash evals/python-compat.sh` — green (3.9 floor, stdlib only,
  `from __future__ import annotations`)
- `bash evals/confirmation-age.sh`, `board-safety.sh`, `decisions-render.sh`, `responsive.sh` —
  green
- Manual: score a pre-change register copy, diff the JSON, confirm only additive keys

- [x] T12 complete

## Layer 3 — conformance audit, 2026-08-06

**Read this before planning any of the Layer 3 items below.** They were written without access
to the sibling sources. The sources are in the worktree, and reading them changes the scope
substantially: **two of the four contract clauses already conform across the whole suite**, and
the single largest ask — a `revalidate` command in `exceptions-register` — already exists.

### Clause by clause

| clause | status | evidence |
|---|---|---|
| **§1.1** clock ownership | **conforms, suite-wide** | No skill writes to a store it does not own. The one cross-skill bridge, `risk-register export-acceptances` → `exceptions-register intake`, is one-way and idempotent on `sourceRiskRef` — the receiving side documents that property and implements it |
| **§1.2** lapse: flag, never block | **conforms, suite-wide** | Nothing in any skill filters, drops or withholds an item for being lapsed. Each carries its lapse state in the payload it exports (`expiryDate`, `revalidationDate`, `overdue`, `breach`) |
| **§1.3** escalation record | **`risk-register` only** | The four siblings emit no records carrying `subjectRef`/`subjectKind`. This is the real Layer 3 work |
| **§1.4** taxonomy handshake | **`risk-register` only has partitions** | Every skill has an event vocabulary; only `risk-register` partitions one. Nothing is broken — a partition is only needed once a skill asks a question *about* its event types |

### Event vocabularies, measured

| skill | event types | partitions |
|---|---|---|
| `risk-register` | 17 | 2 |
| `nist-csf` | 12 | 0 |
| `incident-materiality` | 9 | 0 |
| `exceptions-register` | 7 | 0 |
| `metrics-register` | 5 | 0 |

### What each Layer 3 item actually needs

**`exceptions-register`** — most of it is built. `revalidate` exists as a first-class act,
emits `{kind}-revalidated`, requires a rationale and refuses without one, with refusals covered
in its self-test; its own docstring already states the governing idea, *"re-validation is an act,
not a timer"*. Idempotent intake on `sourceRiskRef` exists. Lapse handling conforms. **Genuinely
outstanding:** escalation records per §1.3 with its own trigger vocabulary, and
*re-measurement before renewal* — the clause that makes renewal refuse against a stale
magnitude, mirroring `risk-register`'s `accept` refusing against `provisionalScore`.

**`board-pack`** — **nothing built, and the highest value.** The assembler has zero references
to escalation. `risk-register` now emits records it cannot see. The plan calls this "where the
contract pays for itself", and it is the one item whose absence is visible to a reader of the
deliverable rather than only to a maintainer. It is also cheap: the pack already runs each
producer's analysis, so escalations arrive in the same payload as the headline figures.

**`metrics-register`** and **`incident-materiality`** — both already compute the underlying
state (`breach`, `overdue`). What is missing is expressing it in the §1.3 shape. Neither needs a
new clock, only a new projection of one they own.

**`nist-csf`** — no lifecycle of its own; conforms trivially. No work.

### Suggested order

`board-pack` first, against `risk-register` alone. It is the only item that makes the escalation
work visible where it was meant to land, and doing it first proves the §1.3 shape survives a
consumer before three more producers are built against it. Then `metrics-register` (its breach
state is closest to the shape), then `exceptions-register`'s two remaining clauses, then
`incident-materiality`.

### Outcome, recorded 2026-08-06

That order was followed and **§1.3 is now complete across every producer.** The audit above is
kept as written rather than edited into agreement with the result — it is the record of what was
known before the work, and a plan quietly rewritten to match its outcome stops being evidence of
anything.

| producer | PR | `subjectKind` | triggers |
|---|---|---|---|
| `board-pack` (consumer) | #47 | — | aggregates and orders; decides nothing |
| `metrics-register` | #48 | `metric` | `threshold-breached`, `sustained-slip` |
| `exceptions-register` | #49 | `acceptance`, `exception` | `expired`, `revalidation-overdue` |
| `incident-materiality` | #50 | `incident` | `window-overdue`, `anchor-missing`, `determination-superseded` |

`nist-csf` emits none, as the audit predicted: a gap against a Target is a distance, not a clock.

**Both now closed**, each recorded below with what the decision turned out to be. The
statements of the problem are kept as they were written, because they are the reason the
answers took the shape they did.

1. **`exceptions-register` re-measurement before renewal.** The audit assumed this mirrors
   `risk-register`'s `provisionalScore` refusal because *"the mechanism already exists in the
   suite"*. Reading both, it does not: `provisionalScore` is a flag on the record the command
   mutates, whereas the magnitude behind an acceptance lives in `risk-register` and this skill
   holds only a marker §1.1 forbids it to update. Option A carries the magnitude and a
   `measuredAt` in the record (self-contained; needs an intake schema change); Option B reads the
   `.rr` at renewal (no schema change, breaks standalone use). **A is recommended.**

   **Decided: A, shipped in #52.** A record may carry the magnitude it was accepted against;
   `revalidate` refuses to renew against one measured before the last review; `--remeasured`
   with `--measured-on` supplies a fresh one in the same act. `export-acceptances` stamps
   residual exposure, its band, and the date the score was last affirmed. Three properties
   keep it honest: a record with no magnitude is never refused, the staleness rule invents no
   interval, and the refusal lands on the act rather than the record.
2. **Duplicate escalations across producers.** `risk-register` can escalate `acceptance-lapsed`
   on its marker while `exceptions-register` escalates `expired` on the authoritative record —
   one fact, two entries, at two severities. The agreed answer is the one this suite already
   uses for duplicate *decisions*: surface, never merge. Unlike the decisions case the join is
   provable rather than heuristic — `sourceRiskRef` is stamped by `export-acceptances` and is the
   intake idempotency key — so the assembler can join on a field the producer declared and flag
   the pair, including their disagreement about severity.

   **Decided as stated, shipped in #53.** `exceptions-register` declares `relatedRef` on its
   escalations; `board-pack` joins on it and warns, naming both records, both producers, and
   the severity disagreement, with both entries left standing. `relatedRef` comes from
   `sourceRiskRef` and deliberately not `riskIds` — identity rather than relatedness, because
   joining on relatedness would flag two genuinely different facts as one.

## Layer 3 — Conformance requirements for sibling skills

**Not task-level.** These were written without access to the source and must be planned against
the real code before execution — see the audit above for what is already done. Each is a
conformance target against Layer 1.

**`exceptions-register`** — owns the acceptance clock, so it carries the part of the LinkedIn
thesis that does not belong in `risk-register`:

- A `revalidate` command that emits `acceptance-revalidated` as a first-class act, distinct from
  creating an acceptance.
- **Re-measurement before renewal.** Renewal should refuse against a stale magnitude the same way
  `risk-register`'s `accept` refuses against `provisionalScore` — the mechanism already exists in
  the suite and should be mirrored, not reinvented. This is the clause that turns a signature
  into the start of a process.
- Idempotent intake keyed on `sourceRiskRef`; a re-run updates rather than duplicates.
- Lapse handling per §1.2 — flag on the inventory and the board view, never filter out.
- Escalation records per §1.3, with its own trigger vocabulary (`revalidation-overdue`,
  `expired`, `renewed-without-remeasure`).

**`metrics-register`** — threshold breaches are escalations in the §1.3 shape;
`subjectKind: "metric"`. Owns its breach clock.

**`incident-materiality`** — materiality determinations that lapse (a determination made against
facts that have since changed) flag per §1.2.

**`board-pack`** — aggregates escalations across skills into one decisions-needed section.
Consumes the §1.3 shape; derives none of it. This is where the contract pays for itself.

**`nist-csf`** — no lifecycle of its own; already feeds `risk-register` through the gap CSV.

## Open decisions

- **OD-1 — Does the `exceptions-register` intake tolerate unknown keys?** If yes, add
  `"lapsed": true` to the exported rows in T8 for an explicit signal. If no, `expiryDate` plus the
  stderr report is the whole mechanism. Blocks nothing; resolve when that source is in hand.
- **OD-2 — Acknowledgement.** v1 has no mute. If escalation volume proves unusable in practice,
  the fix is threshold tuning via `set-escalation` (logged, visible), not a mute field (silent).
  Revisit only with real volume data from a real register.
- **OD-3 — Should `appetite-dwell` measure from snapshots or from `score-changed` events?**
  Specified as snapshots for consistency with every other trigger and because snapshot cadence is
  the review cadence. Events would be more precise and less meaningful.

## Known risks & mitigations

| Risk | Mitigation |
|---|---|
| Summary key drift invalidates historical snapshots | T6 forbids renames; verification diffs the JSON |
| Escalation volume overwhelms the attention list on first run against an old register | Thresholds are settable per register; first run against a register with one snapshot escalates almost nothing by construction |
| A new event type breaks the taxonomy partition | The self-test partition checks fail loudly; T2 adds the classification in the same task as the emitter |
| Renderers quietly re-derive escalation | T9 explicitly forbids it; review the diff for any comparison logic in `renderers/` |
| The 320px table overflows with the new column | `evals/responsive.sh` is a phase-3 gate, not a final check |

## Rollback

Every change is additive: new settings block (defaulted), new commands, new payload keys, new
render sections. Reverting the commit restores prior behaviour with no data migration — existing
`.rr` files written after the change remain loadable by the pre-change script, since
`load_register` ignores unknown settings keys and escalations are never persisted.

---

*Two notes for when it starts: the plan references `examples/example-register-v2.rr` and
`references/example-register.rr` as they exist in the installed plugin copy I read — if your repo
has moved either, that's a "code wins" moment. And the `evals/` filenames cited came from that
same copy, so confirm they exist before Phase 3 leans on them.*
