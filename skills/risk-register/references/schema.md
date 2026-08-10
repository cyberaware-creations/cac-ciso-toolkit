# Risk Register — Data Model & Scoring Reference

## Contents
- Register shape (schema v2)
- Risk shape
- Themes
- Structured acceptance
- Change log (history)
- Confirmation age
- Date fields are canonical `YYYY-MM-DD`
- Snapshots
- Escalation
- Categories / taxonomy
- Matrix sizes and rating labels
- Band thresholds
- Analysis method — the warrant behind the score
- Vocabulary — which word we use, and whose it is
- Risk appetite semantics
- Derived-not-stored rule
- v1 → v2 migration

## Register shape (schema v2)

```json
{
  "schemaVersion": 2,
  "meta": { "clientName": "", "assessor": "", "scopeNote": "", "appetiteStatement": "" },
  "settings": {
    "matrixSize": 5, "appetite": "medium", "currency": "",
    "escalation": { "sustainedWorseningSnapshots": 2, "appetiteDwellDays": 180,
                    "bandCross": true, "lapsedAcceptance": true }
  },
  "themes": [ { "id": "identity", "name": "Identity & Access", "description": "" } ],
  "risks": [ /* Risk[] */ ],
  "history": [ /* HistoryEvent[] — append-only */ ],
  "snapshots": [ /* Snapshot[] — named point-in-time freezes */ ],
  "createdAt": "ISO-8601",
  "updatedAt": "ISO-8601"
}
```

The file is the single local source of truth. It carries data **and** its own history and review
snapshots so the register can report change over time without any external store.

## Risk shape

```json
{
  "id": "R-001",
  "priority": 1,
  "title": "Short name",
  "description": "If <event>, then <consequence> — CAC house format, carrying 8286A r1's scenario elements.",
  "category": "PR",
  "theme": "identity",
  "owner": "Role or name",
  "inherent": { "likelihood": 4, "impact": 5 },
  "response": { "type": "mitigate", "description": "Controls in place / planned", "cost": 45000 },
  "residual": { "likelihood": 2, "impact": 4 },
  "status": "in-treatment",
  "reviewDate": "2026-09-30",
  "acceptance": null,
  "csfSubcategoryId": "PR.AT-01",
  "provisionalTitle": false,
  "provisionalScore": false,
  "notes": "Context, caveats, progress"
}
```

- `theme` — optional theme id (see Themes); the board-reporting rollup axis.
- `provisionalTitle` / `provisionalScore` — booleans, both set by `import-gaps`, and **independent**.
  `provisionalTitle` means the title is still raw framework wording and board-facing renderers must
  withhold it; only `set-text` clears it. `provisionalScore` means the numbers are a priority seed
  nobody has assessed; only `set-score` clears it. They were one `provisional` field in an earlier
  build — a register still carrying it is migrated to both on load. Full behaviour:
  `references/csf-import.md`.
- `acceptance` — populated when a risk is accepted (see Structured acceptance); otherwise `null`.
- `priority` — optional manual board-ranking (NISTIR 8286r1 Table 1, `Priority`). It is *not* used by scoring —
  banding is always derived from exposure — so it never affects the heat map or over-appetite flags;
  it is purely an author-assigned ordering hint.
- Everything else is as in v1: `id` `R-###`, `response.type` ∈ accept/transfer/mitigate/avoid,
  `status` ∈ open/in-treatment/monitoring/closed, likelihood/impact ∈ `1..matrixSize`.

## Themes

Boards think in themes, not line items. A theme groups risks for rollup reporting:

```json
{ "id": "third-party", "name": "Third-Party & Supply Chain", "description": "Vendor/SaaS exposure" }
```

Themes are project-defined. A risk references one via `theme`. Executive reporting aggregates by
theme (count, worst residual band, trend) so the board sees ~6 themes, not 40 rows.

## Structured acceptance

A risk with `response.type: "accept"` (and often `"transfer"`) must carry a structured acceptance,
not just a note — this is both good practice and the audit-defensible layer (DORA RTS Art. 3(d):
justified, re-validated acceptance; NYDFS §500: written approval):

```json
"acceptance": {
  "approver": "Name / role who accepted the risk",
  "justification": "Why this residual risk is acceptable",
  "acceptedDate": "2026-07-01",
  "expiryDate": "2027-07-01",
  "revalidationDate": "2027-01-01"
}
```

An acceptance past its `revalidationDate` is **stale** and must be surfaced for re-validation. An
acceptance with no approver or justification is incomplete and should be flagged.

## Change log (history)

Append-only. Every material change adds an event; events are never edited or removed (that is what
makes the log defensible and the trend real):

```json
{
  "ts": "2026-07-26T18:04:00Z",
  "actor": "D. Alleyne",
  "riskId": "R-005",
  "type": "score-changed",
  "field": "residual",
  "from": { "likelihood": 3, "impact": 5 },
  "to": { "likelihood": 3, "impact": 4 },
  "rationale": "Insurance rider bound; impact of financial loss reduced."
}
```

Event `type` values. The **age-affirming** column is what resets a risk's confirmation age (see
Confirmation age below); everything else leaves it exactly where it was.

| type | written by | age-affirming |
|---|---|---|
| `register-created` | `init` | no |
| `risk-added` | `add` | **yes** |
| `risk-confirmed` | `confirm` | **yes** |
| `score-changed` | `set-score` | **yes** |
| `risk-accepted` | `accept` | **yes** |
| `acceptance-revalidated` | *nothing writes it yet* | **yes** |
| `risk-updated` | `set-text`; also `set-score`, once, when it clears `provisionalScore` | no |
| `status-changed` | `set-status` | no |
| `theme-changed` | `add-theme`, `set-theme` | no |
| `snapshot-created` | `snapshot` | no |
| `import-merged` | `import-gaps --write` | no |
| `escalation-policy-changed` | `set-escalation` | no |
| `response-changed` | `set-response` | no |
| `settings-changed` | `set-currency` | no |
| `method-recorded` | `set-method` | no |
| `risk-closed`, `risk-reopened`, `risk-deleted` | *nothing writes them yet* | no |

Only an assertion about a risk's **magnitude** or its **treatment decision** affirms age. A
rewording, a theme move, a status flip and a snapshot deliberately do not: an age that any edit
resets makes the confirmation-age report worthless — the same rule `nist-csf` states about notes and
staleness in its own `references/schema.md`.

The unwritten types are classified now so they behave correctly when something starts emitting them.
`scripts/score_register.py` holds the classification as `AGE_AFFIRMING`, `NON_AGE_AFFIRMING` and
`KNOWN_EVENT_TYPES`, and its `self-test` asserts the first two are disjoint and that their union is
exactly the third, against an emitted set scraped from the script's own source. A newly-emitted type
therefore fails the suite until somebody places it on one side, rather than defaulting to "does not
affirm age" by omission.

### Adding an event type: there are TWO partitions, in two files, checked by two suites

This paragraph used to stop at the sentence above, and that omission cost real time when
`escalation-policy-changed` was added. **The event vocabulary carries two partitions, not one**,
and satisfying only the documented one leaves the other incomplete:

| partition | lives in | asserted by |
|---|---|---|
| `AGE_AFFIRMING` / `NON_AGE_AFFIRMING` | `scripts/score_register.py` | the engine's own `self-test` |
| `CHANGE_EXPLAINING` / `NOT_CHANGE_EXPLAINING` | `renderers/_common.py` | `evals/confirmation-age.sh` |

Both assert that their union is exactly `KNOWN_EVENT_TYPES`. So:

- **A green `self-test` is not evidence the handshake held.** It only checks the first pair. The
  second fails in a different suite entirely, and the engine will happily report parity while the
  renderer layer has an unclassified type. Run `evals/confirmation-age.sh` too.
- **The second partition answers a different question**, which is why it is not a copy of the
  first. Age-affirming asks *did a human assert something about this risk's magnitude or its
  treatment?* Change-explaining asks *may this event's rationale caption a change on a board
  page?* A type can be one and not the other.
- The register-wide types — `settings-changed`, `snapshot-created`, `register-created`,
  `import-merged`, `escalation-policy-changed` — carry no `riskId`, so they sit on the
  **not**-change-explaining side by construction: there is no risk for their rationale to caption.

Find every partition before adding a type, rather than after:

```bash
grep -rn "KNOWN_EVENT_TYPES" skills/risk-register/ | grep -v "KNOWN_EVENT_TYPES = "
```

**Material changes require a `rationale`** (score moves, acceptances, closures, reopenings,
confirmations). Capture the *why* in-session — it is what powers the board narrative and the audit
trail. Non-material edits (typo fixes, notes) may omit it.

## Confirmation age

**Scores do not expire.** No threshold in this skill expires a score, suppresses a figure, or moves
a band on the strength of a date. Age is reported and the reader judges — a supplier concentration
and a patching backlog go stale at completely different rates, and the tool does not claim to know
either rate.

Four values are derived per risk from `history[]` alone. None is stored, on the same terms as
exposure and band:

| field | meaning |
|---|---|
| `lastConfirmedAt` | newest `ts` among that risk's age-affirming events, as `YYYY-MM-DD` |
| `lastConfirmedBy` | that event's `actor`, or `null` if it carries none |
| `confirmationAgeDays` | whole days from `lastConfirmedAt` to the reference date (`--today`) |
| `confirmationBand` | the band below, or `null` |

Bands are anchored to the renderers' `--age-threshold` (`T`, default 180). Every boundary is
inclusive of the lower band, so a risk at exactly `T` is `approaching` and not yet `beyond`:

| band | boundary | at T=180 |
|---|---|---|
| `within` | `d ≤ T//2` | 0–90d |
| `approaching` | `d ≤ T` | 91–180d |
| `beyond` | `d ≤ 2T` | 181–360d |
| `wellBeyond` | `d > 2T` | over 360d |

The band names describe **distance from a cadence you chose**. They are not confidence words and
never become them: age is derivable from stored data, confidence is not. `evals/board-safety.sh`
checks 9 and 10 fail if confidence vocabulary reaches a board-facing view — check 9 over the
rendered page, check 10 over the source that writes it, by word stem.

### Three outcomes, not two

A missing band is not one state but two, and conflating them makes a renderer assert something
false:

| outcome | `lastConfirmedAt` / `lastConfirmedBy` | `confirmationAgeDays` / `confirmationBand` |
|---|---|---|
| banded | populated | populated |
| **`undated`** — no age-affirming event exists | `null` | `null` |
| **`unreadableDate`** — an age-affirming event exists and names a confirmer, but its `ts` will not parse | populated | `null` |

`undated` is the v1 register and the fresh `import-gaps`: nobody has ever re-affirmed the risk.
Never inferred, never backfilled. `unreadableDate` populates the attribution deliberately — a risk
with a confirmation and a named confirmer on record *has* both, and reporting otherwise would be a
lie. What is absent is the *age*, not the confirmation.

So a renderer must not caption `undated` as "never confirmed" without also handling
`unreadableDate`. That mislabelling is the defect the third state exists to prevent. Over the live
register (closed risks excluded, as everywhere else), `bands + undated + unreadableDate == live`
exactly, and that is asserted.

`futureDated` / `futureDatedRisks` are a **named subset of `bands`, never a summand**. A
confirmation dated after the reference date has a negative age, and `age_band` reports a negative
age as `within` on purpose — it is a pure distance, and an `impossible` band would smuggle a
validation verdict into a distribution. Those risks are therefore already counted inside `bands`;
they are surfaced separately so a view can say "this many of the fresh ones cannot be measured"
rather than presenting them as the best news on the page.

`reviewDate` is a different thing and stays boolean. It is a deadline a human committed to, so
passing it is a fact rather than decay: `reviewOverdue` remains a flag, and `reviewOverdueDays`
exists only so a renderer can rank by how far it slipped.

### Recording a re-affirmation

```bash
python3 scripts/score_register.py confirm register.rr R-004 \
  --why "reviewed at the November risk forum; controls unchanged and still effective" \
  --review 2027-05-31
```

`--why` is required. Asserting that a risk is still right is a material claim and belongs in the
audit trail on the same terms as a score change. Before `confirm` existed the only way to record one
was `set-score` at an identical value, which writes a `score-changed` event where no score changed.

`confirm` changes no score, status or band, and its rationale is deliberately **not** eligible to
caption a change on a board page — a claim that nothing changed cannot explain a change. The
rationale stays in history and belongs to the confirmation-age view.

### No affirming event may attach to a provisional-score risk

`confirm` and `accept` both refuse while `provisionalScore` is true, and the reason is that
invariant rather than fussiness. A provisional score is the importer's seed off a CSF gap's
priority; affirming it would reset confirmation age on a number nobody has assessed and feed it to a
board-facing freshness figure as though it had been.

The invariant holds because the affirming writers are exactly four. `risk-added` comes only from
`add`, which creates the risk and never sets the provisional flags — only `import-gaps` does, and it
writes the non-affirming `import-merged`. `score-changed` comes from `set-score`, which affirms
*and* clears the flag in the same breath, so it is the sanctioned way through rather than an
exception. That left `confirm` and `accept` as the last two doors, and both now refuse before
anything is written, leaving the file byte-identical.

A provisional **title** only warns. Wording is a board-eligibility question, not a magnitude one,
which is the same line `set-score` draws.

## Date fields are canonical `YYYY-MM-DD`

`reviewDate`, `acceptance.revalidationDate`, `acceptance.expiryDate` and `acceptance.acceptedDate`
are compared and sorted **as plain strings** by the renderers, so a non-canonical date does not
merely look untidy — it inverts the comparison. `2027-2-01` sorts *after* `2027-11-01`, which made an
eight-month-overdue review render as on time and dropped it off the attention list entirely.

Every date flag that writes one of those fields therefore validates it and refuses otherwise:

| command | flags validated |
|---|---|
| `add` | `--review` |
| `confirm` | `--review` |
| `accept` | `--revalidate`, `--expiry`, `--accepted` |

Both the unpadded form `2027-2-01` and the basic form `20270201` are rejected, the second because
Python 3.11+ accepts it and the 3.9 floor does not — one flag meaning two things on two supported
interpreters is worse than a refusal.

The write-path rule is house-wide: `nist-csf` enforces the identical one on the dates its own
commands take, and its `references/schema.md` gives the same reason — *"`2026-3-14` sorts after
`2026-12-01` and would make every revisit flag and age figure downstream quietly wrong."*

**Here, validation guards writes only, deliberately.** A pre-existing register hand-carrying
`"reviewDate": "2027-3-01"` still loads, scores and renders; only a *new write* of that date is
refused. Do not "fix" this into a load-time validator — that would make an existing user's file
unopenable, which is worse than the bug it came from. (The two skills part company here on purpose:
`nist-csf`'s `analyze` runs `check_store` and *does* refuse a store carrying a non-canonical
`confirmedAt`, because there a bad date reaches a `strptime` and would surface as a bare traceback
instead of a labelled problem. This skill's renderers tolerate a malformed date by reporting the age
as unknown, so there is nothing to protect the reader from and no reason to lock them out of their
own file.)

## Snapshots

A named, frozen copy of the register at a point in time — the anchor for quarter-over-quarter
comparison and "as of" board views:

```json
{
  "id": "2026-Q2",
  "label": "Q2 2026 Board Review",
  "ts": "2026-06-30T00:00:00Z",
  "note": "Presented to audit committee",
  "data": { "settings": { }, "risks": [ /* frozen */ ], "summary": { /* frozen scored summary */ } }
}
```

Diffing the current register against a snapshot yields the "what changed since Q2" delta. Snapshots
are created at review checkpoints, not on every edit.

## Escalation

Detection is automatic; action is not. A register surfaces what worsened without anyone
remembering to look, and then stops — nothing is blocked, nothing is auto-rescored, and no
determination is made that a human did not make.

### Escalations are derived, and never stored

An escalation is recomputed from the file on every run. It is **never written to a risk,
never written to the register, and never a history event.** It clears when its underlying
condition clears, and only then. There is deliberately no acknowledge or mute field: a stored
acknowledgement is how a live exposure goes quiet without anything about it having improved.

Only the *policy* is stored, in `settings.escalation`, because `snapshot` freezes settings
wholesale — thresholds kept anywhere else would make a snapshot un-reproducible, since the
escalations it recorded could not be recomputed from what it saved. Changing the policy is a
material change and writes an `escalation-policy-changed` event, for the reason `confirm`
exists: a threshold that quietly rewrites which risks escalate would report a calmer quarter
without a single risk having improved.

```json
"escalation": {
  "sustainedWorseningSnapshots": 2,
  "appetiteDwellDays": 180,
  "bandCross": true,
  "lapsedAcceptance": true
}
```

Absent from an existing register, the four defaults are applied on load and merged per key,
so a register that set one threshold keeps the shipped values for the other three. **Values
are not validated on load** — `set-escalation` refuses a bad one, and a file already carrying
one still loads, scores and renders. That is the same write-path-only rule the canonical date
section gives: refusing at load would make a user's register unopenable over a reporting
threshold, which is worse than the threshold.

### Triggers

Closed set. Each names the comparison that fired it, because an escalation a reader cannot
audit is noise, and noise is how escalation gets ignored by the second quarter.

| trigger | fires when | severity |
|---|---|---|
| `band-crossed` | residual band is worse than at the baseline snapshot | `critical` if the new band is critical, else `high` |
| `sustained-drift` | residual exposure worsened across N consecutive snapshots without crossing a band | `medium` |
| `appetite-dwell` | continuously over appetite for more than `appetiteDwellDays`, from the earliest snapshot in which it was already over | `high` |
| `acceptance-lapsed` | `acceptance.expiryDate` has been reached or passed | `high` |
| `method-prerequisite-unmet` | a declared analysis method whose prerequisites the register can see are unmet | `medium` |

- **`band-crossed` suppresses `sustained-drift`** on the same risk. If the band crossed, that
  is the escalation; drift toward it is the same story told twice.
- **Closed risks are skipped for every trigger except `acceptance-lapsed`.** A closed risk
  still carrying a live acceptance is exactly the state worth seeing: the register says the
  work is finished and the acceptance says somebody is still relying on it.
- **A `provisionalScore` risk escalates nothing** and is counted in
  `summary.escalationsSuppressedProvisional` instead. Escalating off an import seed would be
  escalating off a number nobody assessed; hiding the suppression would be the silence the
  lapse rule forbids.
- **A register with no snapshots escalates nothing from scores.** No baseline means no
  comparison — a first run escalates almost nothing by construction.
- `acceptance-lapsed` uses **reached or passed**, matching `renderers/_common.py::_overdue`,
  so this and the dashboards' `acceptanceExpired` flag can never disagree by a day.
- **`method-prerequisite-unmet` is `medium`, and deliberately not `high`.** `acceptance-lapsed`
  and `appetite-dwell` are `high` because somebody is currently relying on something that
  expired. An undocumented deviation is wrong on the page, not wrong in the world.
- **It checks exactly two things**, both arithmetic over facts the file already holds:
  `type: quantitative` while `settings.currency` is empty, and `conformance: partial` with an
  empty `deviations`. It should stay two until a third is as mechanical as these.
- ⚠️ **A method the catalogue marks `external` emits nothing, under any input.** Monte Carlo's
  real prerequisites are the analyst's input distributions, Bayesian's are their priors, event
  tree's are their branch probabilities, and Open FAIR's are computed in their own model. This
  toolkit can see none of them, and flagging their absence would assert a fact about work done
  outside it — the same restraint as `untraced` being a value rather than a gap.
  `references/analysis-methods.json` carries the `checkable`/`external` mark per method, and
  `evals/analysis-method.sh` proves the boundary holds in both directions.
- **The escalation needs no storage.** `escalations()` is derived, stateless and never written,
  so a prerequisite gap is computed on read and clears the moment it is fixed. Nothing records
  that it fired.

### The record

```json
{
  "subjectRef": "R-014", "subjectKind": "risk",
  "trigger": "band-crossed", "severity": "high", "since": "2026-05-31",
  "evidence": { "from": 9, "to": 15, "baseline": "Q2 2026 Board Review",
                "detail": "residual band medium -> high since the last snapshot" }
}
```

Sorted by severity, then by `subjectRef`, so a rendered list does not reshuffle between runs.
`score --json` carries the list at the top level and the counts in `summary.escalations`;
renderers **consume it and never re-derive it**, the same rule that keeps banding out of the
renderers.

### Lapse semantics — flag only, never block

A dated obligation past its date is *lapsed*. Across this skill, and across the suite:

- A lapsed item is **still exported, still rendered, still counted.** `export-acceptances`
  emits an expired acceptance and names it on stderr rather than dropping it — a dead
  acceptance silently missing from the intake is worse than one that arrives flagged.
- A lapse **never mutates an assessed value.** Residual is an assessment; auto-reverting one
  on a date would invent an assessment nobody made.
- A lapse **never gates a command.** Nothing refuses because something else lapsed, and
  `escalations` exits 0 whether or not anything fired. (Contrast the `provisionalScore`
  refusals, which guard against affirming an unassessed number — a different concern.)

## Categories / taxonomy

CSF functions: `GV` Govern · `ID` Identify · `PR` Protect · `DE` Detect · `RS` Respond · `RC` Recover.
General categories: Operational · Financial · Third-Party / Supply-Chain · Compliance · Reputational.
(`category` is the risk-taxonomy axis; `theme` is the board-rollup axis — they can differ.)

## Matrix sizes and rating labels

`matrixSize` ∈ {3, 4, 5} (5×5 default). Likelihood and impact run `1..matrixSize`.

**The 5-level labels are SP 800-30 Rev. 1's qualitative scale; the 4- and 3-level sets are this
tool's own.** 800-30 defines one five-level scale — Very Low / Low / Moderate / High / Very High —
and no shorter variants, so a smaller matrix is a CAC convenience, not a NIST one. Labels:

| Level | 5×5 | 4×4 | 3×3 |
|---|---|---|---|
| 1 | Very Low | Low | Low |
| 2 | Low | Moderate | Moderate |
| 3 | Moderate | High | High |
| 4 | High | Very High | — |
| 5 | Very High | — | — |

## Band thresholds

Exposure = likelihood × impact. Band = highest band whose inclusive lower bound ≤ exposure:

| Matrix | low ≥ | medium ≥ | high ≥ | critical ≥ |
|---|---|---|---|---|
| 5×5 | 1 | 5 | 10 | 15 |
| 4×4 | 1 | 4 | 8 | 12 |
| 3×3 | 1 | 3 | 5 | 7 |

Band order (ascending): `low < medium < high < critical`. Lives in `scripts/score_register.py`.

## Analysis method — the warrant behind the score

Each risk may carry `analysisMethod`, and `settings.analysisMethodDefault` holds a register-wide
fallback of the same shape:

```json
"analysisMethod": {
  "name": "OPEN FAIR",              // free text — the method as its owners call it
  "type": "quantitative",           // one of: qualitative, semi-quantitative, quantitative
  "conformance": "partial",         // full | partial
  "deviations": "no monetised loss magnitude; frequency estimated from three incidents",
  "setBy": "D. Galleyne",
  "asOf": "2026-08-10"
}
```

**Absent means NOT DECLARED, never *no method was used*** (CAC-AP-1 §2.2). Every risk scored
before v0.87.0 is in that state, and a reader has to be able to tell it from a risk somebody
deliberately recorded as qualitative. The engine stores `null`, not `{}`.

**Why per risk and not per register.** A register commonly holds both: three risks somebody
modelled with loss distributions and thirty scored by judgement in a workshop. A register-level
field has to describe the least rigorous of them or overstate the rest.
`settings.analysisMethodDefault` covers the ordinary case where one method genuinely applies to
everything, and **a risk's own record outranks it in both directions** — a register defaulting
to `quantitative` must be able to say *this one is qualitative because we have nothing to
count*. A default that could only raise the floor would quietly assert monetised analysis on a
risk nobody costed.

**`type` is constrained; `name` is not.** The three types are NIST's. The name is free text and
an unfamiliar one is not refused: this tool does not hold a catalogue of every method a CISO
might legitimately use, and refusing an unknown name would make it the arbiter of that.

**⚠️ The tool never renames somebody else's method.** A FAIR analysis run without monetised loss
is `open-fair` at `conformance: partial` **with the deviation stated** — never a coined
"FAIR-lite". Renaming a licensed third-party standard to describe a reduced variant is a false
claim about work that is not ours, and it is exactly the kind of claim that gets repeated by
people who never read the original. Same reasoning as `incident-materiality`'s documented
disclosure-clock deviations.

**Validation guards writes, never loads.** `set-method` refuses `partial` with no `deviations`;
a register that already carries that combination **loads, scores and renders unchanged** and
refuses on the next write that touches the method. Refusing at load would make an existing
register unopenable over a field whose whole purpose is honest disclosure.

**Mixed methods are not comparable and the engine does not pretend otherwise.** There is no
conversion, no normalisation and no cross-method re-ranking anywhere. Disclosure of a mixed
register on the rendered page is Phase B (BL-93), not shipped.

## Vocabulary — which word we use, and whose it is

This register borrows vocabulary from two NIST documents that **do not use the same words for the
same things**, and it cites both. Where they differ, this section says which word this tool uses
and what the other one means, so a reader holding either document is not quietly misled.

> ⚠️ **Provenance of the quotes below.** They are transcribed from the register-alignment design
> (`strategy/register-alignment-design-2026-08-08.md` rev b, pasted onto BL-54). The wording is
> verbatim as recorded there. **The section numbers are the design's and have not been re-read
> against the published text in this pass** — where a section is given below it carries that
> caveat. `sources.json` records the same distinction. Pull the primary text before quoting any
> of these in a room.

### Exposure, and *level of risk*

**This tool says `exposure`, and it means likelihood × impact.** That is NIST IR 8286r1's word
— *"the combination of impact and likelihood is referred to as exposure."*

**SP 800-30 Rev. 1, which this tool cites for its rating labels, calls the same quantity
*level of risk*.** The two are aliases here. They are not aliases in general: 800-30 Rev. 1
combines likelihood and impact through **Table I-2, a 5×5 lookup**, and this tool multiplies —
see *Band thresholds* above, and the engine docstring, which states the arithmetic is CAC's own.
So *level of risk* names the same **axis**; it does not name the same **calculation**.

### Inherent — a stage, not a permanent partner to residual

**`inherent` is the assessment before today's controls, and it is a stage in a cycle rather than
half of a fixed pair.** NIST IR 8286r1: *"On the first iteration… this may also be considered the
initial assessment, whereas subsequent cycles refer to this as inherent."*

The practical consequence, and the reason this correction exists: a register on its **first**
pass is recording an *initial* assessment, and calling it inherent asserts a
before-controls/after-controls relationship the first pass has not established. Later cycles earn
the word. Nothing in the engine changes — both fields are recorded and scored identically — but
a board asked to read "inherent vs residual" on a first assessment is being shown a comparison
that is really initial-vs-current.

### Residual — this tool records the ACTUAL residual only

**`residual` here always means *actual* residual: the exposure with today's controls working as
described.**

NIST IR 8286r1 also uses **target residual risk** — the level a treatment is aiming at — and
observes that *"actual residual risk should be equal to or less than the target residual risk."*
**This register does not record a target residual today.** The word is defined here so that a
reader who meets it in the source knows which of the two this tool's field is, and does not read
`residual` as an aspiration. (Recording a target is BL-54 R-4, not shipped.)

### Band order is not a work queue

**The band ordering `low < medium < high < critical` ranks severity. It does not schedule work.**
NIST IR 8286r1: *"priority is not necessarily a reflection of the chronological order in which
risk should be mitigated."*

A critical risk whose treatment depends on a system that is being replaced next quarter may
legitimately be sequenced after a high one that can be closed this week. The register ranks; the
plan sequences; and the two are allowed to differ as long as somebody can say why.

### Vulnerability is wider than a scanner finding

**A vulnerability here is *a condition that enables a threat event to occur*** — the definition
NIST IR 8286A r1 uses for the scenario element of that name.

It explicitly includes **planning gaps, training deficiencies, physical access and supply-chain
conditions**, not only a software defect with a CVE. This matters at the point a risk is written:
the house event statement carries asset, threat, vulnerability and impact, and a register that
reads `vulnerability` as *unpatched software* will silently exclude every risk whose enabling
condition is a process nobody owns.

## Risk appetite semantics

`settings.appetite` is the **worst band still acceptable**. A risk is **over appetite** when its
residual band is strictly worse than the appetite band. `meta.appetiteStatement` holds the written
appetite (CSF 2.0 GV.RM) that boards ask to see.

## Derived-not-stored rule

Exposure and band are never persisted on a risk — the script computes them from likelihood × impact
every time, so a stale number can't contradict the inputs. The same holds for the four
confirmation-age fields and for `reviewOverdue` / `reviewOverdueDays`: `history[]` is the single
source of truth for when anything was last affirmed, and a stored age field would be a second one.
(Snapshots are the one exception: they freeze a *computed* summary on purpose, as a historical
record.)

Escalations obey the same rule and go further — they are not persisted even on a risk they
concern. See Escalation above. A snapshot's frozen summary does carry the escalation *counts*,
and `snapshot` therefore scores with a reference date so those counts are complete rather than
missing the two date-derived triggers.

## v1 → v2 migration

A `schemaVersion: 1` file loads fine: treat missing `themes`, `history`, and `snapshots` as empty
arrays and missing `acceptance` as `null`. On first write, stamp `schemaVersion: 2`. No data is lost.
