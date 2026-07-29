# Graded Age Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Report *how old* every rating and every risk determination is, in four named bands derived from the threshold the user already configured — and close the asymmetry where `nist-csf` reports an age distribution and `risk-register` reports nothing.

**Architecture:** One band function, `age_band(days, T)`, with identical semantics in both skills (they cannot share code — separate skills, no common import). `nist-csf` already computes ages; it gains a band counter. `risk-register` has no last-confirmed date at all, so it gains a `confirm` subcommand that writes a `risk-confirmed` history event, and a derivation that reads the newest age-affirming event out of `history[]`. Nothing is stored: every age, band and count is computed at read time, on both sides.

**Tech Stack:** Python 3.9 floor (`from __future__ import annotations` is present in all three files, so PEP 604 `X | None` annotations and f-strings are fine), standard library only, no dependencies. Bash for the eval suites.

**Source spec:** `docs/superpowers/specs/2026-07-29-staleness-graded-age-design.md`

---

## Three corrections to the spec, resolved here

Read these before starting. Each one is a place the spec is wrong or underspecified against the actual code, and each changes what you build.

**C1 — Two of the spec's age-affirming event types are never written, and two that are written are missing from the list.**

`score_register.py` emits exactly nine event types: `import-merged`, `register-created`, `risk-accepted`, `risk-added`, `risk-updated`, `score-changed`, `snapshot-created`, `status-changed`, `theme-changed`.

`references/schema.md:122-124` documents thirteen, five of which nothing emits: `response-changed`, `acceptance-revalidated`, `risk-closed`, `risk-reopened`, `risk-deleted`. And it omits two that *are* emitted: `import-merged`, `register-created`.

So the spec's affirming entry `acceptance-revalidated` is inert today, and its non-affirming entries `risk-closed` / `risk-reopened` / `risk-deleted` describe events that never arrive — the real one is `status-changed`. Resolution: keep `acceptance-revalidated` in the affirming set as forward-compatibility (harmless, and correct when something eventually writes it), classify every documented-or-emitted type explicitly, and add a totality test so a *new* event type cannot silently default to "does not affirm age". Task 8 also fixes `schema.md` to match reality.

**C2 — The `nist-csf` "Stalest" panel sorts on a different date than the one the bands measure.**

`attention_lists()` (`profile_analysis.py:1081`) builds `stalest` by sorting on `lastReviewed`. `_age()` computes ages from `confirmedAt`. These are deliberately different fields — `profile_analysis.py:611-617` states `confirmedAt` is never backfilled from `lastReviewed`, because that would fabricate attribution.

So "each row gains its band" (spec §4) would put a band derived from one date next to a sort order derived from another. Resolution: show **both** dates on the row and band on `confirmedAt` only, because that is the field the whole age model uses. A row with a `lastReviewed` but no `confirmedAt` renders **no band** rather than a guessed one — asserted by a test in Task 2. The existing sort order is unchanged (it is asserted at `profile_analysis.py:2625`).

**C3 — The eval suite path in spec §6 does not exist.**

The spec says `evals/board-safety.sh`. The real path is `skills/risk-register/evals/board-safety.sh`. There is no top-level `evals/` directory.

**C4 — `skills/nist-csf/examples/example-profile.csfp` has zero `confirmedAt`, so it cannot test banding at all.**

Found during Task 2, and it invalidated four of this plan's own assertions. That fixture is a **v1 Profile** — `grep -c confirmedAt` returns 0 — and the engine's self-test binds `store` to it. So any assertion of the form `all(... for r in rows if r["confirmedAt"])` iterates an empty set and is vacuously true. Reviewers reproduced this: the plan's Task 2 test block, applied verbatim, stayed green at 497/497 under a mutant that banded on `lastReviewed` instead of `confirmedAt` — the precise defect correction C2 exists to prevent.

`skills/nist-csf/examples/example-profile-v2.csfp` carries four dated confirmations (420d and 198d against `today=2026-07-27`), and all four change band between T=180 and T=365. **Any test of banding must use the v2 fixture.** Pin exact lists with a row count rather than writing `all(...)` over a filter — a filter that matches nothing passes.

**C5 — Renderer invocation: the nist-csf renderers take `--in <analyze JSON>` and `--out`, not a positional `.csfp`.** Positional paths raise an explicit `SystemExit`, and passing a store where analyze output is required fails a separate guard in `_common.py`. Pipe through `analyze` first. Also note that on the v1 fixture the executive band cells correctly do **not** render (all bands zero), so greping for them there and expecting a hit is unmeetable.

**C6 — There is no automated coverage of rendered `nist-csf` HTML.** `skills/nist-csf/evals/` holds conversation and trigger evals only; the CI workflow runs engine self-tests plus `responsive.sh` (which does cover 8 nist-csf pages for width and WCAG AA) and `contrast-check.mjs` (which is **not** a standalone entry point — it needs the headless Chrome that `responsive.sh` starts). Nothing greps rendered nist-csf content. A Critical label defect shipped through Task 2 review because of this: see the warning in Task 2 Step 6.

---

## File structure

| File | Responsibility for this work |
|---|---|
| `skills/nist-csf/scripts/profile_analysis.py` | `AGE_BANDS`, `age_band()`, `_age()` band counter, `attention_lists()` gains `age_days` and bands the stalest rows |
| `skills/nist-csf/renderers/render_executive.py` | Age cell grid gains the band distribution |
| `skills/nist-csf/renderers/render_operational.py` | Stalest panel rows show confirmation date + band |
| `skills/risk-register/scripts/score_register.py` | `AGE_BANDS`, `AGE_AFFIRMING`, `KNOWN_EVENT_TYPES`, `age_band()`, `confirm` subcommand, `risk-confirmed` event, self-test additions |
| `skills/risk-register/renderers/_common.py` | `--age-threshold` flag, `_days_since()`, per-risk confirmation fields, `reviewOverdueDays`, `confirmation` rollup |
| `skills/risk-register/renderers/render_dashboard.py` | "Confirmation age" panel + per-risk card line |
| `skills/risk-register/renderers/render_board.py` | One freshness sentence in `summary_block()` |
| `skills/risk-register/evals/board-safety.sh` | Checks 8 and 9: freshness line renders; no confidence vocabulary reaches a board view |
| Docs + manifests | Task 8 and Task 9 |

The band constants and `age_band()` live in `score_register.py` rather than `_common.py` on the risk-register side, because `_common.py` imports `score_register as sr` and not the reverse — putting them in the engine lets `score_register.py`'s own self-test assert them, and keeps the event writer and the event classifier in one file.

## Baselines to preserve

Measured on `main` at `c4f204b`, before any change:

```
risk-register  score_register.py self-test     34/34
nist-csf       profile_analysis.py self-test   472/472
nist-csf       csfa_compat.py self-test        47/47
version guard  tools/check-versions.py         19/19
board-safety                                   7 checks, all pass
```

Every task ends green on the suites it touches. Counts go **up**, never down.

## A standing rule: green is a claim, not evidence

This repo's recurring defect is not broken code — it is **assertions that cannot fail.** The
version guard shipped four distinct false-PASS classes. `board-safety.sh` passed over the
change log for a full release. `python-compat.sh` printed "all 0 shipped files compile" and
exited 0. Task 1 of this very plan was reviewed twice: the first review found a factually
impossible assertion, and the second found that two of the remaining ones survived mutation —
including the identity check whose comment claimed the two notions "cannot drift".

So for every new assertion in every task below: **revert the mechanism it guards and confirm
the assertion dies.** Where one property is held up by two independent expressions, mutate
each separately — passing one mutant proves only half. If a mutant survives, the test is
decoration; fix the test before writing more code. Each task's mutation steps are mandatory.

---

### Task 1: Age bands in `nist-csf`

**Files:**
- Modify: `skills/nist-csf/scripts/profile_analysis.py` (add constants + `age_band()` near `_median_int` at line 525; extend `_age()` at line 661; extend self-test after line 3660)

- [ ] **Step 1: Write the failing tests**

In `skills/nist-csf/scripts/profile_analysis.py`, find this block in `_cmd_self_test` (line 3655):

```python
    age = ev["age"]["overall"]
    eq(age["dated"], 3, "age counts only dated confirmations")
    eq(age["oldestDays"], 421, "oldest: 2025-06-01 to 2026-07-27")
    eq(age["medianDays"], 198, "median of 129, 198, 421")
    eq(age["olderThanThreshold"], 2, "two ratings older than 180 days")
    eq(ev["age"]["thresholdDays"], 180, "the threshold is reported with the counts")
```

Insert immediately after it:

```python
    # --- Age bands: graded distance from the cadence the reader chose ---
    #
    # Band names are deliberately not confidence words. `within` / `beyond` state how far
    # a determination sits from a chosen cadence; they never claim how sure anyone should
    # be that it is still true. See the design spec, section 7.
    #
    # Boundary tests go through age_band() directly rather than through the fixture,
    # because the interesting cases are the three exact edges and a fixture cannot sit on
    # all of them at once.
    eq(age_band(0, 180), "within", "a confirmation made today is within")
    eq(age_band(90, 180), "within", "exactly T//2 is still within — the edge is inclusive")
    eq(age_band(91, 180), "approaching", "one day past T//2 is approaching")
    eq(age_band(180, 180), "approaching", "exactly T is still approaching")
    eq(age_band(181, 180), "beyond", "one day past T is beyond")
    eq(age_band(360, 180), "beyond", "exactly 2T is still beyond")
    eq(age_band(361, 180), "wellBeyond", "one day past 2T is wellBeyond")
    eq(age_band(129, 365), "within", "bands rescale with T: 129 days is within at T=365")
    eq(age_band(421, 365), "beyond", "bands rescale with T: 421 days is beyond at T=365")

    # The fixture's three dated ages are 129, 198 and 421 days at today=2026-07-27.
    eq(age["bands"], {"within": 0, "approaching": 1, "beyond": 1, "wellBeyond": 1},
       "the band counter partitions the fixture's three dated ages")
    eq(sum(age["bands"].values()), age["dated"],
       "every dated confirmation lands in exactly one band")
    eq(age["bands"]["beyond"] + age["bands"]["wellBeyond"], age["olderThanThreshold"],
       "beyond + wellBeyond IS olderThanThreshold — the two notions cannot drift")
    eq(set(age["bands"]), set(AGE_BANDS), "the counter carries every band and no others")

    # The identity has to hold at a rescaled threshold too, or it is an accident of 180.
    ev365 = derive_evidence(fx_assess, fx_intake, index, core, today="2026-07-27",
                            threshold_pct=60, age_days=365)
    age365 = ev365["age"]["overall"]
    eq(age365["bands"], {"within": 1, "approaching": 1, "beyond": 1, "wellBeyond": 0},
       "at T=365 the same three ages redistribute")
    eq(age365["bands"]["beyond"] + age365["bands"]["wellBeyond"],
       age365["olderThanThreshold"], "the identity holds at T=365, not just at T=180")
    eq(ev365["age"]["thresholdDays"], 365, "the rescaled threshold is reported back")

    # A threshold that puts a fixture rating EXACTLY on the line. This is the only case
    # that can catch drift between the two independent expressions holding the identity
    # up — age_band's `days <= threshold_days` and _age's `d > age_days`. At T=180 and
    # T=365 no fixture age equals T (they are 129, 198, 421), so mutating _age's `>` to
    # `>=` passes both. PR.DS-11 is 198 days old, so T=198 sits a rating on the boundary.
    ev198 = derive_evidence(fx_assess, fx_intake, index, core, today="2026-07-27",
                            threshold_pct=60, age_days=198)
    age198 = ev198["age"]["overall"]
    eq(age198["bands"], {"within": 0, "approaching": 2, "beyond": 0, "wellBeyond": 1},
       "a rating at exactly T is approaching, not beyond")
    eq(age198["bands"]["beyond"] + age198["bands"]["wellBeyond"],
       age198["olderThanThreshold"],
       "the identity holds with a rating sitting exactly on the threshold")
    eq(ev198["age"]["thresholdDays"], 198, "the boundary threshold is reported back")

    # Per-Function bands, as full dicts. A single-key assertion here passes even when
    # byFunction wrongly hands every Function the whole Profile's ages — the full dict
    # is what pins the grouping. Fixture membership: ID holds the 129- and 421-day
    # ratings (ID.AM-01, ID.AM-02); PR holds the 198-day one (PR.DS-11).
    eq(ev["age"]["byFunction"]["PR"]["bands"],
       {"within": 0, "approaching": 0, "beyond": 1, "wellBeyond": 0},
       "PR carries the one beyond rating and nothing else")
    eq(ev["age"]["byFunction"]["ID"]["bands"],
       {"within": 0, "approaching": 1, "beyond": 0, "wellBeyond": 1},
       "ID carries the approaching and wellBeyond ratings, not PR's beyond")
```

**Why these five extra assertions, and not the single per-Function check this plan first
carried:** the original was `eq(ev["age"]["byFunction"]["ID"]["bands"]["beyond"], 1, ...)`,
which is factually impossible — the fixture's only `beyond` rating at T=180 is `PR.DS-11`
(198 days), in Function **PR**, so ID's `beyond` count is legitimately 0. Two independent
reviews caught it. Worse, both the single-key form *and* the T=180/T=365 identity checks
survive mutation: a single-key per-Function assertion passes when `byFunction` hands every
Function the whole Profile, and the identity assertions pass when `_age`'s `>` becomes `>=`,
because drift is only observable with a rating exactly on the line. Assertions that cannot
fail are the defect this repo has shipped most often; these five can.

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 skills/nist-csf/scripts/profile_analysis.py self-test 2>&1 | tail -5`

Expected: FAIL — a `NameError: name 'age_band' is not defined` traceback, because `age_band` does not exist yet.

- [ ] **Step 3: Add the constants and the band function**

In `skills/nist-csf/scripts/profile_analysis.py`, immediately **before** `def _median_int(` (line 525), insert:

```python
# --- Age bands ----------------------------------------------------------------
# One notion of "old", anchored to the Profile's own configurable threshold T
# (settings.reporting.ageThresholdDays, default 180) so the engine never holds two.
#
#   within       d <= T//2
#   approaching  d <= T
#   beyond       d <= 2T
#   wellBeyond   d >  2T
#
# `olderThanThreshold` is unchanged and must always equal beyond + wellBeyond. The
# self-test asserts that identity at two different thresholds, because holding at 180
# alone would be an accident of the default rather than a property of the model.
AGE_BANDS = ("within", "approaching", "beyond", "wellBeyond")


def age_band(days: int, threshold_days: int) -> str:
    """Which band `days` of age falls in, relative to threshold `threshold_days`.

    Every boundary is inclusive of the lower band, so a rating at exactly T is
    `approaching` and not yet `beyond` — the threshold is a cadence the reader chose to
    aim at, and hitting it is meeting it.

    Nothing here is a statement about confidence. The engine reports age; the reader
    judges what age means for a given Subcategory, because a governance outcome and an
    asset inventory go stale at completely different rates.
    """
    if days <= threshold_days // 2:
        return "within"
    if days <= threshold_days:
        return "approaching"
    if days <= threshold_days * 2:
        return "beyond"
    return "wellBeyond"
```

- [ ] **Step 4: Add the band counter to `_age()`**

In `skills/nist-csf/scripts/profile_analysis.py`, replace the body of `_age()` (line 661, inside `derive_evidence`) — currently:

```python
    def _age(subset: list[dict]) -> dict:
        ages = [_days_between(a["confirmedAt"], today) for a in subset
                if states[a["subcategoryId"]] == "confirmed" and a.get("confirmedAt")]
        undated = sum(1 for a in subset
                      if states[a["subcategoryId"]] == "confirmed" and not a.get("confirmedAt"))
        return {
            "dated": len(ages),
            # A rating carried over from a v1 Profile has no confirmation date. It is
            # counted here rather than guessed at: age reporting begins when ratings
            # are confirmed under v2, and saying so is the honest version.
            "undated": undated,
            "medianDays": _median_int(ages),
            "oldestDays": max(ages) if ages else None,
            "olderThanThreshold": sum(1 for d in ages if d > age_days),
        }
```

with:

```python
    def _age(subset: list[dict]) -> dict:
        ages = [_days_between(a["confirmedAt"], today) for a in subset
                if states[a["subcategoryId"]] == "confirmed" and a.get("confirmedAt")]
        undated = sum(1 for a in subset
                      if states[a["subcategoryId"]] == "confirmed" and not a.get("confirmedAt"))
        bands = {b: 0 for b in AGE_BANDS}
        for d in ages:
            bands[age_band(d, age_days)] += 1
        return {
            "dated": len(ages),
            # A rating carried over from a v1 Profile has no confirmation date. It is
            # counted here rather than guessed at: age reporting begins when ratings
            # are confirmed under v2, and saying so is the honest version.
            "undated": undated,
            "medianDays": _median_int(ages),
            "oldestDays": max(ages) if ages else None,
            "olderThanThreshold": sum(1 for d in ages if d > age_days),
            # A graded distribution rather than one count past one line. `undated` is
            # NOT a band: it is the absence of a date, not a distance from one, and
            # folding it in would report a guess as a measurement.
            "bands": bands,
        }
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `python3 skills/nist-csf/scripts/profile_analysis.py self-test 2>&1 | tail -3`

Expected: `self-test: 493/493 checks passed` — 472 baseline plus the 21 assertions above. Do
not treat that number as the goal: the goal is 472 plus however many assertions you actually
wrote. If it is *below* 472, you deleted a test, and that is the only outcome here that is a
failure.

- [ ] **Step 6: Prove the tests bind — three mutants, not one**

A test that cannot fail is not a test, and this repo has shipped that defect more than any
other. Each mutant below targets one of the three independent things these assertions claim.
Run all three. Every one MUST fail, and the restore MUST return to green.

**Mutant A — the band boundary.** Widens `beyond` so nothing is ever `wellBeyond`:

```bash
cd /Users/darren/Documents/GitHub/cac-ciso-toolkit
cp skills/nist-csf/scripts/profile_analysis.py /tmp/pa.bak
# Mutant: make `beyond` swallow everything, so beyond+wellBeyond no longer equals
# olderThanThreshold at T=365 (where wellBeyond should be 0 and beyond should be 1).
python3 - <<'PY'
import pathlib
p = pathlib.Path("skills/nist-csf/scripts/profile_analysis.py")
s = p.read_text()
s = s.replace("    if days <= threshold_days * 2:\n        return \"beyond\"",
              "    if days <= threshold_days * 99:\n        return \"beyond\"", 1)
p.write_text(s)
PY
python3 skills/nist-csf/scripts/profile_analysis.py self-test 2>&1 | tail -5
cp /tmp/pa.bak skills/nist-csf/scripts/profile_analysis.py
```

Expected: FAILS, naming `one day past 2T is wellBeyond`.

**Mutant B — the identity's other half.** The identity is held up by two *independent*
expressions: `age_band`'s `days <= threshold_days` and `_age`'s `d > age_days`. Mutant A only
tests the first. This tests the second, and it is the reason the `age_days=198` case exists —
at T=180 and T=365 no fixture age equals T, so this mutant passes without it:

```bash
cp skills/nist-csf/scripts/profile_analysis.py /tmp/pa.bak
python3 - <<'PY'
import pathlib
p = pathlib.Path("skills/nist-csf/scripts/profile_analysis.py")
s = p.read_text()
old = '"olderThanThreshold": sum(1 for d in ages if d > age_days),'
assert old in s, "mutant target not found"
p.write_text(s.replace(old, '"olderThanThreshold": sum(1 for d in ages if d >= age_days),', 1))
PY
python3 skills/nist-csf/scripts/profile_analysis.py self-test 2>&1 | tail -5
cp /tmp/pa.bak skills/nist-csf/scripts/profile_analysis.py
```

Expected: FAILS, naming `the identity holds with a rating sitting exactly on the threshold`.
If it passes, the boundary case is not doing its job — fix it before continuing.

**Mutant C — the per-Function grouping.** Hands every Function the whole Profile's ages. A
single-key per-Function assertion survives this; a full-dict one does not:

```bash
cp skills/nist-csf/scripts/profile_analysis.py /tmp/pa.bak
python3 - <<'PY'
import pathlib
p = pathlib.Path("skills/nist-csf/scripts/profile_analysis.py")
s = p.read_text()
old = '"byFunction": {fid: _age(by_fn.get(fid, [])) for fid in fids},'
assert old in s, "mutant target not found"
p.write_text(s.replace(old, '"byFunction": {fid: _age(assessments) for fid in fids},', 1))
PY
python3 skills/nist-csf/scripts/profile_analysis.py self-test 2>&1 | tail -5
cp /tmp/pa.bak skills/nist-csf/scripts/profile_analysis.py
python3 skills/nist-csf/scripts/profile_analysis.py self-test 2>&1 | tail -2
```

Expected: FAILS, naming one or both of the per-Function band assertions. The final restore
returns to green.

- [ ] **Step 7: Confirm the Python floor**

Run: `PY=/usr/bin/python3 ./skills/risk-register/evals/python-compat.sh /usr/bin/python3 2>&1 | tail -2`

Expected: `python-compat: all N shipped files compile on 3.9.6`

- [ ] **Step 8: Commit**

```bash
git add skills/nist-csf/scripts/profile_analysis.py
git commit -m "feat(nist-csf): report confirmation age as four graded bands

Bands are anchored to the Profile's own ageThresholdDays (T//2, T, 2T) so the
engine holds exactly one notion of 'old'. olderThanThreshold is unchanged and
asserted equal to beyond + wellBeyond at two different thresholds, so the two
cannot drift apart.

The band names state distance from a chosen cadence, never confidence."
```

---

### Task 2: Surface the bands in the `nist-csf` renderers

**Files:**
- Modify: `skills/nist-csf/scripts/profile_analysis.py` (`attention_lists()` at line 1081, its call site at line 2355, self-test after line 2628)
- Modify: `skills/nist-csf/renderers/render_executive.py` (age cell grid, around line 88-96)
- Modify: `skills/nist-csf/renderers/render_operational.py` (stalest panel, line 325-327)

- [ ] **Step 1: Write the failing tests**

In `skills/nist-csf/scripts/profile_analysis.py`, find this in `_cmd_self_test` (line 2625):

```python
    eq([r["subcategoryId"] for r in att["stalest"]][:3], ["PR.DS-01", "PR.AA-01", "GV.RM-01"],
       "stalest ordering (oldest first)")
    ok(all(r["subcategoryId"] not in ("GV.SC-01", "ID.RA-01") for r in att["stalest"]),
       "never-reviewed excluded from stalest")
```

Insert immediately after it:

```python
    # A stalest row is SORTED on lastReviewed but BANDED on confirmedAt. Those are
    # different fields on purpose (confirmedAt is never backfilled from lastReviewed —
    # that would fabricate attribution), so the row carries both and bands only the one
    # the age model actually measures.
    ok(all("confirmedAt" in r and "confirmationBand" in r for r in att["stalest"]),
       "every stalest row carries both the confirmation date and its band")
    ok(all(r["confirmationBand"] is None for r in att["stalest"] if not r["confirmedAt"]),
       "a row reviewed but never confirmed shows NO band rather than a guessed one")
    ok(all(r["confirmationBand"] in AGE_BANDS
           for r in att["stalest"] if r["confirmedAt"]),
       "a row with a confirmation date is banded")
    # The threshold reaches attention_lists, so a rescaled Profile bands consistently
    # rather than silently falling back to 180.
    _att365 = attention_lists(store, index, "2026-07-26", top=10, age_days=365)
    ok(all(r["confirmationBand"] in AGE_BANDS
           for r in _att365["stalest"] if r["confirmedAt"]),
       "stalest bands honour a rescaled age threshold")
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 skills/nist-csf/scripts/profile_analysis.py self-test 2>&1 | tail -6`

Expected: FAIL — `TypeError: attention_lists() got an unexpected keyword argument 'age_days'`.

- [ ] **Step 3: Extend `attention_lists()`**

In `skills/nist-csf/scripts/profile_analysis.py`, replace the signature and `_brief` (lines 1081-1091) — currently:

```python
def attention_lists(store: dict, index: dict, today: str, top: int = 10) -> dict:
    """What a reviewer must look at. `today` is passed in — never read from the clock."""
    settings = store["profile"]["settings"]
    scoped = in_scope(store["assessments"])
    gaps = compute_gaps(store["assessments"], settings, index)

    def _brief(a):
        return {"subcategoryId": a["subcategoryId"], "text": index[a["subcategoryId"]]["text"],
                "lastReviewed": a.get("lastReviewed"), "status": a.get("status")}
```

with:

```python
def attention_lists(store: dict, index: dict, today: str, top: int = 10,
                    age_days: int = 180) -> dict:
    """What a reviewer must look at. `today` is passed in — never read from the clock.

    `age_days` is the Profile's own ageThresholdDays, used only to band each row's
    confirmation age. It has a default so the two date-handling self-tests below can call
    this with three arguments, but the real call site passes the configured value.
    """
    settings = store["profile"]["settings"]
    scoped = in_scope(store["assessments"])
    gaps = compute_gaps(store["assessments"], settings, index)

    def _brief(a):
        # Two dates, deliberately. `lastReviewed` is when somebody looked; `confirmedAt`
        # is when the rating was decided, with a source and a confirmer behind it. The
        # stalest list is ordered by the first and banded by the second, because the
        # band belongs to the same field every other age figure in this engine measures.
        # A rating with no confirmedAt gets no band — never a guessed one.
        confirmed_at = a.get("confirmedAt")
        return {"subcategoryId": a["subcategoryId"], "text": index[a["subcategoryId"]]["text"],
                "lastReviewed": a.get("lastReviewed"), "status": a.get("status"),
                "confirmedAt": confirmed_at,
                "confirmationAgeDays": (_days_between(confirmed_at, today)
                                        if confirmed_at else None),
                "confirmationBand": (age_band(_days_between(confirmed_at, today), age_days)
                                     if confirmed_at else None)}
```

- [ ] **Step 4: Pass the configured threshold at the call site**

In `skills/nist-csf/scripts/profile_analysis.py` line 2355, inside `_cmd_analyze`, replace:

```python
        "attention": attention_lists(store, index, today, top),
```

with:

```python
        "attention": attention_lists(store, index, today, top,
                                     age_days=rep["ageThresholdDays"]),
```

(`rep = settings["reporting"]` is already bound at line 2255 in the same function.)

- [ ] **Step 5: Run the test to verify it passes**

Run: `python3 skills/nist-csf/scripts/profile_analysis.py self-test 2>&1 | tail -3`

Expected: `self-test: 494/494 checks passed` (490 + 4 new).

- [ ] **Step 6: Show the distribution on the executive age grid**

In `skills/nist-csf/renderers/render_executive.py`, find this block (around line 86-96):

```python
        if thr is not None and age.get("olderThanThreshold") is not None:
            cells.append((f"older than {thr} days", f'{age["olderThanThreshold"]}'))
```

Insert immediately after it:

> ### ⚠️ This step originally carried a Critical defect. Do not restore it.
>
> The first version of this plan wrote the labels as cumulative phrases:
> `("approaching", f"within {thr} days")`, `("beyond", f"within {thr * 2} days")`.
>
> The band counts are **exclusive** populations, so those labels are arithmetically false —
> with a distribution spread across all four bands, `"within 180 days": 1` is wrong when two
> ratings are within 180 days. Worse, `beyond` means *past the cadence the Profile chose*,
> and "within 360 days" reads as **meeting** a deadline, while `render_operational.py` calls
> that same band "beyond cadence". One dataset, two renderers, opposite valence, and the
> flattering reading on the board surface. That breaks "numbers never flatter" through labels
> alone, and it survived a full review round.
>
> Both shipped fixtures **hide it**: `example-profile.csfp` has no dated confirmations at
> all, and `example-profile-v2.csfp` has `within` and `approaching` both 0, so the cumulative
> misreading yields the same number. See correction **C4**.

Labels must be **exclusive ranges** carrying the **same valence** as the operational
renderer, every boundary derived from `thr`, and the distribution must show its denominator:

```python
    # The band distribution, grading the same population the "older than T" cell counts —
    # beyond + wellBeyond IS that figure, and the engine asserts the identity. Each count
    # carries `dated` so four new numbers do not appear without a denominator.
    #
    # Labels are EXCLUSIVE ranges and share render_operational's valence. Cumulative
    # phrasing over exclusive counts is both false and flattering: `beyond` means past the
    # cadence this Profile chose, so no label for it may read as meeting a deadline.
    bands = age.get("bands") or {}
    if thr is not None and any(bands.values()):
        ranges = {"within": f"0–{thr // 2}d", "approaching": f"{thr // 2 + 1}–{thr}d",
                  "beyond": f"{thr + 1}–{thr * 2}d", "wellBeyond": f"over {thr * 2}d"}
        for key in c.AGE_BAND_ORDER:
            cells.append((f'{c.AGE_BAND_LABEL[key]} ({ranges[key]})',
                          f'{bands.get(key, 0)} of {age["dated"]}'))
```

`AGE_BAND_LABEL` and `AGE_BAND_ORDER` belong in `skills/nist-csf/renderers/_common.py`, not
in either renderer: that file already holds `EVIDENCE_LABEL` / `EVIDENCE_ORDER` /
`EVIDENCE_KEY` in exactly this shape for both renderers, and a shared home collapses what
would otherwise be a third copy of the band order. Consider `c.evidence_bar` in place of four
cells if it fits — it is this codebase's existing idiom for mutually-exclusive counts that
sum to a total with the denominator in view.

**Then build a store spread across all four bands and read the rendered text.** Neither
shipped fixture exercises all four, which is exactly how the defect above survived. This is
the only check that would have caught it.

- [ ] **Step 7: Show the band on each stalest row**

In `skills/nist-csf/renderers/render_operational.py`, replace the "Stalest" panel entry (lines 325-328) — currently:

```python
        ("Stalest", "Is this rating still true, or just old?",
         [f'<span class="mono">{c.esc(r["subcategoryId"])}</span> '
          f'<span class="muted">{c.esc(r["lastReviewed"])}</span> {c.esc(c.trunc(r["text"], 60))}'
          for r in a.get("stalest", [])]),
```

with:

```python
        # Ordered by lastReviewed, banded on confirmedAt. Both dates are shown because
        # they answer different questions — "when did anyone look" and "when was this
        # decided, with a source behind it" — and a row with no confirmation date says
        # so rather than being handed a band it has not earned.
        ("Stalest", "Is this rating still true, or just old?",
         [f'<span class="mono">{c.esc(r["subcategoryId"])}</span> '
          f'<span class="muted">{c.esc(r["lastReviewed"])}</span> '
          f'{c.esc(c.trunc(r["text"], 60))}'
          f'{_age_note(r)}'
          for r in a.get("stalest", [])]),
```

Then add this helper immediately **before** `def attention(` in the same file:

```python
AGE_BAND_LABEL = {"within": "within cadence", "approaching": "approaching cadence",
                  "beyond": "beyond cadence", "wellBeyond": "well beyond cadence"}


def _age_note(row: dict) -> str:
    """The confirmation age of one stalest row, or an honest blank.

    Never a band without a date behind it: a rating carried over from a v1 Profile has
    no confirmedAt, and the whole point of not backfilling it is to avoid inventing the
    attribution. So the row says the date is missing instead of guessing a band.
    """
    band = row.get("confirmationBand")
    if not band:
        return ('<span class="muted"> · no confirmation date</span>')
    return (f'<span class="muted"> · confirmed {c.esc(row["confirmedAt"])}, '
            f'{AGE_BAND_LABEL[band]} ({row["confirmationAgeDays"]}d)</span>')
```

- [ ] **Step 8: Verify both renderers still render**

```bash
cd /Users/darren/Documents/GitHub/cac-ciso-toolkit
work=$(mktemp -d)
python3 skills/nist-csf/scripts/profile_analysis.py self-test >/dev/null 2>&1
python3 skills/nist-csf/renderers/render_executive.py \
  skills/nist-csf/examples/example-profile.csfp "$work/exec.html" && \
python3 skills/nist-csf/renderers/render_operational.py \
  skills/nist-csf/examples/example-profile.csfp "$work/ops.html" && \
grep -c 'confirmed within' "$work/exec.html" && \
grep -c 'cadence\|no confirmation date' "$work/ops.html"
```

Expected: both renderers exit 0, and both greps print a count of at least 1. If `skills/nist-csf/examples/example-profile.csfp` is not the fixture path, find it with `ls skills/nist-csf/examples/` and substitute.

- [ ] **Step 9: Run the full nist-csf suite**

```bash
python3 skills/nist-csf/scripts/profile_analysis.py self-test 2>&1 | tail -2
python3 skills/nist-csf/scripts/csfa_compat.py self-test 2>&1 | tail -1
```

Expected: `self-test: 494/494 checks passed` and `csfa-compat self-test: 47/47 checks passed`.

- [ ] **Step 10: Commit**

```bash
git add skills/nist-csf/scripts/profile_analysis.py \
        skills/nist-csf/renderers/render_executive.py \
        skills/nist-csf/renderers/render_operational.py
git commit -m "feat(nist-csf): show the age distribution, and band each stalest row

The stalest list is ordered on lastReviewed and banded on confirmedAt. Those
are different fields by design — confirmedAt is never backfilled — so a row
carries both dates and a row with no confirmation date shows no band at all
rather than one it has not earned."
```

---

### Task 3: `confirm` subcommand and the `risk-confirmed` event

**Files:**
- Modify: `skills/risk-register/scripts/score_register.py` (module docstring line 27; constants near line 526; new `_cmd_confirm` before `_cmd_set_status` at line 853; `COMMANDS` at line 924; self-test before line 513)

- [ ] **Step 1: Write the failing tests**

In `skills/risk-register/scripts/score_register.py`, find the end of `_cmd_self_test` (line 510-513):

```python
    # import priority seeding + dedupe (import.test.ts semantics)
    eq("PRIORITY_SEED[critical]", PRIORITY_SEED["critical"], 5)
    eq("PRIORITY_SEED[low]", PRIORITY_SEED["low"], 2)
```

Insert immediately after it:

```python
    # --- Age bands and the age-affirming event taxonomy ---
    eq("age_band(0,180)", age_band(0, 180), "within")
    eq("age_band(90,180) edge", age_band(90, 180), "within")
    eq("age_band(91,180)", age_band(91, 180), "approaching")
    eq("age_band(180,180) edge", age_band(180, 180), "approaching")
    eq("age_band(181,180)", age_band(181, 180), "beyond")
    eq("age_band(360,180) edge", age_band(360, 180), "beyond")
    eq("age_band(361,180)", age_band(361, 180), "wellBeyond")
    # 365//2 == 182, so 200 days is `approaching` at T=365 and `beyond` at T=180 — the same
    # age, two cadences, two answers. (An earlier draft of this plan asserted "within" here,
    # which is wrong: floor division puts the within/approaching line at 182, not 200.)
    eq("age_band(200,180)", age_band(200, 180), "beyond")
    eq("age_band(200,365) rescales", age_band(200, 365), "approaching")
    eq("age_band(182,365) floor-division edge", age_band(182, 365), "within")
    eq("age_band(183,365) floor-division edge", age_band(183, 365), "approaching")
    eq("AGE_BANDS", AGE_BANDS, ("within", "approaching", "beyond", "wellBeyond"))

    # Affirming means a human asserted something about the risk's magnitude or its
    # treatment decision. A note, a theme move, a status flip and a snapshot do not.
    eq("score-changed affirms", "score-changed" in AGE_AFFIRMING, True)
    eq("risk-confirmed affirms", "risk-confirmed" in AGE_AFFIRMING, True)
    eq("risk-added affirms", "risk-added" in AGE_AFFIRMING, True)
    eq("risk-accepted affirms", "risk-accepted" in AGE_AFFIRMING, True)
    eq("risk-updated does NOT affirm", "risk-updated" in AGE_AFFIRMING, False)
    eq("theme-changed does NOT affirm", "theme-changed" in AGE_AFFIRMING, False)
    eq("status-changed does NOT affirm", "status-changed" in AGE_AFFIRMING, False)
    eq("snapshot-created does NOT affirm", "snapshot-created" in AGE_AFFIRMING, False)
    eq("import-merged does NOT affirm", "import-merged" in AGE_AFFIRMING, False)
    # Totality: a new event type must be classified deliberately, not default to
    # "does not affirm age" by omission. references/schema.md documents several types
    # nothing writes yet; they are classified here so they behave correctly on arrival.
    eq("every affirming type is a known type", AGE_AFFIRMING - KNOWN_EVENT_TYPES, set())
    eq("every type score_register can write is classified",
       _EMITTED_EVENT_TYPES - KNOWN_EVENT_TYPES, set())

    # --- confirm: "I looked at this and nothing changed" has a home ---
    import tempfile as _tf
    _d = _tf.mkdtemp()
    _rr = os.path.join(_d, "c.rr")
    _cmd_init([_rr, "--client", "Fixture Co", "--assessor", "D. Alleyne"])
    _cmd_add([_rr, "--title", "Supplier concentration", "--il", "4", "--ii", "4",
              "--rl", "3", "--ri", "4", "--why", "fixture"])
    _before = json.load(open(_rr))
    _n_before = len(_before["history"])
    _cmd_confirm([_rr, "R-001", "--why", "reviewed at the monthly risk forum; unchanged"])
    _after = json.load(open(_rr))
    _ev = _after["history"][-1]
    eq("confirm appends exactly one event", len(_after["history"]) - _n_before, 1)
    eq("confirm writes risk-confirmed", _ev["type"], "risk-confirmed")
    eq("confirm names the risk", _ev["riskId"], "R-001")
    eq("confirm records the rationale", _ev["rationale"],
       "reviewed at the monthly risk forum; unchanged")
    eq("confirm records the actor", _ev["actor"], "D. Alleyne")
    eq("confirm carries a timestamp", bool(_ev.get("ts")), True)
    # Confirming asserts nothing new about magnitude, treatment or status.
    _r_before = [r for r in _before["risks"] if r["id"] == "R-001"][0]
    _r_after = [r for r in _after["risks"] if r["id"] == "R-001"][0]
    eq("confirm changes no score", _r_after["residual"], _r_before["residual"])
    eq("confirm changes no status", _r_after["status"], _r_before["status"])
    eq("confirm changes no response", _r_after["response"], _r_before["response"])

    # --why is a hard refusal, and a refused mutation leaves the file byte-identical.
    _raw_before = open(_rr, "rb").read()
    try:
        _cmd_confirm([_rr, "R-001"])
        _refused = False
    except ValueError:
        _refused = True
    eq("confirm without --why is refused", _refused, True)
    eq("a refused confirm leaves the register untouched", open(_rr, "rb").read(), _raw_before)

    # --review sets the next review date in the same breath as the confirmation,
    # because that is the actual review-meeting workflow.
    _cmd_confirm([_rr, "R-001", "--why", "forum re-affirmed", "--review", "2027-01-31"])
    _r3 = [r for r in json.load(open(_rr))["risks"] if r["id"] == "R-001"][0]
    eq("--review sets the next review date", _r3["reviewDate"], "2027-01-31")

    # An unknown risk id is an error, not a silently-created risk.
    try:
        _cmd_confirm([_rr, "R-999", "--why", "typo"])
        _bad_id = False
    except ValueError:
        _bad_id = True
    eq("confirm on an unknown id is refused", _bad_id, True)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 skills/risk-register/scripts/score_register.py self-test 2>&1 | tail -5`

Expected: FAIL — `NameError: name 'age_band' is not defined`.

- [ ] **Step 3: Add the constants and the band function**

In `skills/risk-register/scripts/score_register.py`, immediately **after** these lines (line 526-527):

```python
STATUSES = {"open", "in-treatment", "monitoring", "closed"}
RESPONSES = {"accept", "transfer", "mitigate", "avoid"}
```

insert:

```python
# --- Age bands and the age-affirming event taxonomy ---------------------------
# Identical semantics to nist-csf's profile_analysis.age_band(), deliberately duplicated:
# the two skills ship independently and neither may import the other. The self-tests on
# both sides assert the same boundaries, so a change to one that is not made to the other
# shows up as a failure rather than as two skills quietly disagreeing about "old".
#
#   within       d <= T//2
#   approaching  d <= T
#   beyond       d <= 2T
#   wellBeyond   d >  2T
AGE_BANDS = ("within", "approaching", "beyond", "wellBeyond")


def age_band(days: int, threshold_days: int) -> str:
    """Which band `days` of age falls in, relative to threshold `threshold_days`.

    Boundaries are inclusive of the lower band: at exactly T a determination is
    `approaching`, not yet `beyond`. The threshold is a cadence somebody chose to aim
    at, and hitting it is meeting it.

    These are not confidence words. The engine reports how old a determination is; it
    never claims how sure anyone should be that it is still true.
    """
    if days <= threshold_days // 2:
        return "within"
    if days <= threshold_days:
        return "approaching"
    if days <= threshold_days * 2:
        return "beyond"
    return "wellBeyond"


# Events where a human asserted something about a risk's magnitude or its treatment
# decision. Only these reset confirmation age.
AGE_AFFIRMING = frozenset({
    "risk-added", "score-changed", "risk-confirmed", "risk-accepted",
    # Nothing writes this yet; references/schema.md documents it, and it is an
    # affirmation when it arrives. Classified now so it behaves correctly then.
    "acceptance-revalidated",
})

# Every type this file can write, plus every type references/schema.md documents. The
# self-test asserts _EMITTED_EVENT_TYPES is a subset, so a newly-emitted type fails the
# suite until somebody decides whether it affirms age. Without that, a new event would
# default to "does not affirm" by omission — and silently resetting, or silently failing
# to reset, staleness is exactly what makes a "stalest" list worthless.
KNOWN_EVENT_TYPES = frozenset({
    "register-created", "risk-added", "risk-updated", "score-changed", "response-changed",
    "status-changed", "risk-accepted", "acceptance-revalidated", "risk-confirmed",
    "risk-closed", "risk-reopened", "risk-deleted", "theme-changed", "settings-changed",
    "snapshot-created", "import-merged",
})

# Kept in step with the _append_event() calls in this file by the self-test.
_EMITTED_EVENT_TYPES = frozenset({
    "register-created", "risk-added", "risk-updated", "score-changed", "risk-accepted",
    "status-changed", "theme-changed", "snapshot-created", "import-merged",
    "risk-confirmed",
})
```

- [ ] **Step 4: Add the `confirm` command**

In `skills/risk-register/scripts/score_register.py`, immediately **before** `def _cmd_set_status(args):` (line 853), insert:

```python
def _cmd_confirm(args):
    """Record that a risk was looked at and nothing changed.

    Before this existed, the only way to re-affirm a risk was `set-score` at an identical
    value — which writes a `score-changed` event where no score changed, corroding the
    audit trail the skill exists to keep honest. "I reviewed this and it still stands" is
    a material claim and deserves its own event type and its own rationale.

    Changes no score, no status, no response, no band. The only optional write is
    `--review`, because setting the next review date in the same breath is the actual
    review-meeting workflow.
    """
    pos, opt = parse_flags(args)
    if len(pos) < 2:
        raise ValueError("usage: confirm <register.rr> <id> --why '...' [--review YYYY-MM-DD]")
    reg = load_register(pos[0])
    r = _find(reg, pos[1])
    if not (isinstance(opt.get("why"), (str, list)) and _s(opt["why"]).strip()):
        raise ValueError("confirm: --why is required. Asserting that a risk is still right "
                         "is a material claim and belongs in the audit trail on the same "
                         "terms as a score change.")
    review = None
    if "review" in opt and opt["review"] is not True:
        review = _s(opt["review"])
        try:
            datetime.strptime(review, "%Y-%m-%d")
        except ValueError:
            raise ValueError(f"confirm: --review {review!r} is not a YYYY-MM-DD date.")
        r["reviewDate"] = review
    _append_event(reg, "risk-confirmed", riskId=pos[1], rationale=opt["why"])
    save_register(reg, pos[0])
    print(f"{pos[1]} confirmed by {reg['meta'].get('assessor') or 'unknown'}.")
    if review:
        print(f"  Next review: {review}")
    return 0


```

- [ ] **Step 5: Register the command and document it**

In `skills/risk-register/scripts/score_register.py`, replace the `COMMANDS` dict (line 924):

```python
COMMANDS = {
    "score": _cmd_score, "import-gaps": _cmd_import_gaps, "self-test": _cmd_self_test,
    "init": _cmd_init, "set-text": _cmd_set_text,
    "add": _cmd_add, "set-score": _cmd_set_score, "accept": _cmd_accept,
    "set-status": _cmd_set_status, "snapshot": _cmd_snapshot, "export-csv": _cmd_export_csv,
    "add-theme": _cmd_add_theme, "set-theme": _cmd_set_theme,
}
```

with:

```python
COMMANDS = {
    "score": _cmd_score, "import-gaps": _cmd_import_gaps, "self-test": _cmd_self_test,
    "init": _cmd_init, "set-text": _cmd_set_text,
    "add": _cmd_add, "set-score": _cmd_set_score, "accept": _cmd_accept,
    "confirm": _cmd_confirm,
    "set-status": _cmd_set_status, "snapshot": _cmd_snapshot, "export-csv": _cmd_export_csv,
    "add-theme": _cmd_add_theme, "set-theme": _cmd_set_theme,
}
```

Then in the module docstring, after the `accept` line (line 30):

```
  accept       <register.rr> <id> --approver ... --justification ... --revalidate DATE
```

insert:

```
  confirm      <register.rr> <id> --why ... [--review YYYY-MM-DD]
                                         Record that a risk was reviewed and nothing
                                         changed. Resets confirmation age; changes no
                                         score, status or band.
```

- [ ] **Step 6: Run the test to verify it passes**

Run: `python3 skills/risk-register/scripts/score_register.py self-test 2>&1 | tail -3`

Expected: `62/62 checks passed.` (34 baseline + 28 new), followed by `Parity confirmed: scoring matches the Limen Labs web engine.`

- [ ] **Step 7: Prove the `--why` refusal actually leaves the file untouched**

The byte-identity assertion is the one most likely to pass for the wrong reason — if `_cmd_confirm` raised *before* ever opening the file, it would pass trivially. Confirm the ordering binds.

> **The mutant must move the guard past `save_register`, not merely past `_append_event`.**
> An earlier draft of this step moved it between the two, which is behaviourally a **no-op**:
> `_append_event` only appends to the in-memory dict, and `save_register` is the sole writer,
> so nothing reaches disk either way and the mutant survives at full green. Reading that as
> "the ordering is not asserted" would have been a false alarm — the assertion is sound, the
> mutant was not. A mutant that cannot change observable behaviour proves nothing about the
> test that fails to catch it.

```bash
cd /Users/darren/Documents/GitHub/cac-ciso-toolkit
cp skills/risk-register/scripts/score_register.py /tmp/sr.bak
# Mutant: move the --why guard AFTER the write, so a refused confirm still mutates.
python3 - <<'PY'
import pathlib
p = pathlib.Path("skills/risk-register/scripts/score_register.py")
s = p.read_text()
guard = """    if not (isinstance(opt.get("why"), (str, list)) and _s(opt["why"]).strip()):
        raise ValueError("confirm: --why is required. Asserting that a risk is still right "
                         "is a material claim and belongs in the audit trail on the same "
                         "terms as a score change.")
"""
assert guard in s, "guard block not found — adjust the mutant to match the file"
s = s.replace(guard, "", 1)
# Past save_register, not merely past _append_event: save_register is the only writer.
s = s.replace('    save_register(reg, pos[0])',
              '    save_register(reg, pos[0])\n' + guard.rstrip("\n"), 1)
p.write_text(s)
PY
python3 skills/risk-register/scripts/score_register.py self-test 2>&1 | tail -4
cp /tmp/sr.bak skills/risk-register/scripts/score_register.py
python3 skills/risk-register/scripts/score_register.py self-test 2>&1 | tail -2
```

Expected: the mutant run FAILS naming `a refused confirm leaves the register untouched`, and the restore returns to 62/62. If the mutant passes, the ordering is not asserted and the test must be strengthened.

- [ ] **Step 8: Check the Python floor and commit**

```bash
PY=/usr/bin/python3 ./skills/risk-register/evals/python-compat.sh /usr/bin/python3 2>&1 | tail -1
git add skills/risk-register/scripts/score_register.py
git commit -m "feat(risk-register): add confirm, so re-affirmation has its own event

'I looked at this and nothing changed' had no home. The only way to record it
was set-score at an identical value, which writes a score-changed event where
no score changed — corroding the audit trail the skill exists to keep honest.

--why is a hard refusal and is checked before the file is touched, so a refused
confirm leaves the register byte-identical. The event taxonomy is asserted total:
a newly-emitted type fails the suite until somebody decides whether it affirms
age, rather than defaulting to 'no' by omission."
```

---

### Task 4: Derive confirmation age in `risk-register`

**Files:**
- Modify: `skills/risk-register/renderers/_common.py` (`parse_args` at line 175; `_days_since` near `_overdue` at line 254; `Context.__init__` at line 304; `_enrich` at line 360; new `_confirmation_rollup`)

- [ ] **Step 1: Write the failing test**

Create `skills/risk-register/evals/confirmation-age.sh`:

```bash
#!/bin/bash
# Confirmation-age derivation, asserted against a register built by the real CLI.
#
#   ./confirmation-age.sh [workdir]
#
# The four derived fields (lastConfirmedAt, lastConfirmedBy, confirmationAgeDays,
# confirmationBand) come from history[] and nothing else — there is no stored age field
# and there must never be one. So they are asserted through the same Context the
# renderers use, over a register whose history was written by actual commands rather
# than hand-assembled JSON. A hand-built fixture would not catch the failure that
# matters most: a command that writes the wrong event type.
#
# Exit 0 = all pass. Exit 1 = at least one failure, listed.

set -u
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "$here/../../.." && pwd)"
work="${1:-$(mktemp -d)}"
PY="${PY:-python3}"
RR="$repo/skills/risk-register"
mkdir -p "$work"

fails=0
chk() {
  printf '%-5s %-58s %s\n' "$1" "$2" "$3"
  [ "$3" = PASS ] || fails=$((fails + 1))
}

rm -f "$work/a.rr"
"$PY" "$RR/scripts/score_register.py" init "$work/a.rr" --client "Age Co" \
  --assessor "D. Alleyne" >/dev/null || { echo "FIXTURE FAILED — init"; exit 1; }
"$PY" "$RR/scripts/score_register.py" add "$work/a.rr" --title "Supplier concentration" \
  --il 4 --ii 4 --rl 3 --ri 4 --why "fixture" >/dev/null || {
    echo "FIXTURE FAILED — add R-001"; exit 1; }
"$PY" "$RR/scripts/score_register.py" add "$work/a.rr" --title "Legacy VPN appliance" \
  --il 5 --ii 4 --rl 4 --ri 4 --why "fixture" >/dev/null || {
    echo "FIXTURE FAILED — add R-002"; exit 1; }
# R-002 gets a non-affirming event LAST. Its age must still date from `risk-added`.
"$PY" "$RR/scripts/score_register.py" set-text "$work/a.rr" R-002 \
  --title "Remote access via an unsupported VPN appliance" --why "reworded" >/dev/null || {
    echo "FIXTURE FAILED — set-text R-002"; exit 1; }
"$PY" "$RR/scripts/score_register.py" set-status "$work/a.rr" R-002 monitoring \
  --why "watching" >/dev/null || { echo "FIXTURE FAILED — set-status R-002"; exit 1; }
"$PY" "$RR/scripts/score_register.py" snapshot "$work/a.rr" --label "Baseline" >/dev/null || {
    echo "FIXTURE FAILED — snapshot"; exit 1; }

"$PY" - "$work" "$RR" <<'PY' > "$work/out.txt"
import json, sys, pathlib, argparse, datetime
work, rr = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
sys.path.insert(0, str(rr / "renderers"))
sys.path.insert(0, str(rr / "scripts"))
import _common as C

reg = json.loads((work / "a.rr").read_text())
# Every event this fixture wrote is dated today, so ages are 0 and every risk is
# `within`. The band boundaries themselves are asserted in score_register's self-test;
# what is asserted here is that the derivation reads the right event.
today = max(e["ts"] for e in reg["history"])[:10]

def ctx(**over):
    args = argparse.Namespace(register=str(work / "a.rr"), out=str(work / "x.html"),
                              today=today, translations=None, offline=True,
                              age_threshold=180)
    for k, v in over.items():
        setattr(args, k, v)
    return C.Context(args)

c = ctx()
by = c.by_id
out = []
out.append(("R-001 dates from risk-added", by["R-001"]["lastConfirmedAt"] == today))
out.append(("R-001 names the actor", by["R-001"]["lastConfirmedBy"] == "D. Alleyne"))
out.append(("R-001 age is 0 days", by["R-001"]["confirmationAgeDays"] == 0))
out.append(("R-001 bands as within", by["R-001"]["confirmationBand"] == "within"))
# The load-bearing one: set-text, set-status and snapshot all landed after risk-added
# on R-002, and none of them may reset its age.
r2_hist = [e["type"] for e in by["R-002"]["history"]]
out.append(("R-002 history really does end non-affirming",
            r2_hist[-1] in ("risk-updated", "status-changed")))
out.append(("R-002 still dates from risk-added",
            by["R-002"]["lastConfirmedAt"] == today))

# A confirm resets the age; nothing else about the risk moves.
import subprocess
subprocess.run([sys.executable, str(rr / "scripts" / "score_register.py"), "confirm",
                str(work / "a.rr"), "R-001", "--why", "reviewed, unchanged"],
               check=True, capture_output=True)
c2 = ctx()
ev = c2.by_id["R-001"]["history"][-1]
out.append(("confirm becomes the affirming event", ev["type"] == "risk-confirmed"))
out.append(("confirm keeps the age at 0",
            c2.by_id["R-001"]["confirmationAgeDays"] == 0))

# A register with a v1-style history — no affirming event at all — must yield None,
# not a guess and not a crash.
raw = json.loads((work / "a.rr").read_text())
raw["history"] = [e for e in raw["history"] if e["type"] not in
                  ("risk-added", "score-changed", "risk-confirmed", "risk-accepted",
                   "acceptance-revalidated")]
(work / "b.rr").write_text(json.dumps(raw))
argsb = argparse.Namespace(register=str(work / "b.rr"), out=str(work / "y.html"),
                           today=today, translations=None, offline=True, age_threshold=180)
cb = C.Context(argsb)
out.append(("no affirming event yields None, not a guess",
            cb.by_id["R-001"]["lastConfirmedAt"] is None
            and cb.by_id["R-001"]["confirmationBand"] is None))
out.append(("undated risks are counted, not hidden",
            cb.confirmation["undated"] == len([r for r in cb.risks
                                               if r.get("status") != "closed"])))

# The rollup partitions the live population and nothing else.
live = [r for r in c2.risks if r.get("status") != "closed"]
out.append(("rollup counts every live risk exactly once",
            sum(c2.confirmation["bands"].values()) + c2.confirmation["undated"]
            == len(live) == c2.confirmation["live"]))
out.append(("rollup reports its own threshold",
            c2.confirmation["thresholdDays"] == 180))

# --age-threshold reaches the derivation rather than falling back to 180.
c3 = ctx(age_threshold=2)
out.append(("--age-threshold reaches the derivation",
            c3.confirmation["thresholdDays"] == 2))

# reviewOverdueDays: a missed deadline is a fact with a magnitude, still boolean-gated.
out.append(("not-overdue carries no day count",
            all(r["reviewOverdueDays"] is None for r in c2.risks
                if not r["reviewOverdue"])))

# A malformed date must not turn a board night into a traceback.
raw2 = json.loads((work / "a.rr").read_text())
raw2["risks"][0]["reviewDate"] = "not-a-date"
(work / "c.rr").write_text(json.dumps(raw2))
argsc = argparse.Namespace(register=str(work / "c.rr"), out=str(work / "z.html"),
                           today=today, translations=None, offline=True, age_threshold=180)
try:
    cc = C.Context(argsc)
    out.append(("a malformed reviewDate degrades rather than crashing",
                cc.by_id["R-001"]["reviewOverdueDays"] is None))
except Exception as exc:
    out.append((f"a malformed reviewDate degrades rather than crashing ({exc!r})", False))

for name, good in out:
    print(("PASS" if good else "FAIL") + "\t" + name)
PY

n=1
while IFS=$'\t' read -r verdict name; do
  chk "$n" "$name" "$verdict"
  n=$((n + 1))
done < "$work/out.txt"

echo
if [ "$fails" -eq 0 ]; then
  echo "confirmation-age: all checks passed"
else
  echo "confirmation-age: $fails check(s) FAILED"
fi
exit $([ "$fails" -eq 0 ] && echo 0 || echo 1)
```

Then: `chmod +x skills/risk-register/evals/confirmation-age.sh`

- [ ] **Step 2: Run it to verify it fails**

Run: `./skills/risk-register/evals/confirmation-age.sh 2>&1 | tail -20`

Expected: FAIL — an `AttributeError: 'Namespace' object has no attribute ...` or `KeyError: 'lastConfirmedAt'` traceback, because none of the fields exist yet.

- [ ] **Step 3: Add the `--age-threshold` flag**

In `skills/risk-register/renderers/_common.py`, in `parse_args` (line 175), after the `--offline` argument:

```python
    p.add_argument("--offline", action="store_true",
                   help="omit the Google Fonts links so the file makes no external request; "
                        "falls back to the system font stack")
```

insert:

```python
    p.add_argument("--age-threshold", type=int, default=180, metavar="DAYS",
                   help="confirmation-age band width T: within <= T/2, approaching <= T, "
                        "beyond <= 2T, wellBeyond over 2T. Reporting only — no threshold "
                        "here expires, suppresses or rescores anything "
                        "(default: 180, matching nist-csf's ageThresholdDays)")
```

and after the existing `--today` validation:

```python
    try:
        date.fromisoformat(args.today)
    except ValueError:
        p.error(f"--today {args.today!r} is not a YYYY-MM-DD date")
    return args
```

change it to:

```python
    try:
        date.fromisoformat(args.today)
    except ValueError:
        p.error(f"--today {args.today!r} is not a YYYY-MM-DD date")
    # A zero or negative T collapses every band into wellBeyond, which reports as
    # "everything is ancient" rather than as the misconfiguration it is.
    if args.age_threshold <= 0:
        p.error(f"--age-threshold must be a positive number of days "
                f"(got {args.age_threshold})")
    return args
```

- [ ] **Step 4: Add the date helper**

In `skills/risk-register/renderers/_common.py`, immediately **after** `_overdue` (line 254-257):

```python
def _overdue(value: str | None, today: str) -> bool:
    """True when an ISO date has been reached or passed. Blank/missing is never overdue."""
    return bool(value) and str(value)[:10] <= today
```

insert:

```python
def _days_since(value: str | None, today: str) -> int | None:
    """Whole days from an ISO date (or timestamp) to `today`; None if absent or malformed.

    Tolerant on purpose. `_overdue()` above compares strings and can never raise, so a
    register carrying a typo'd date still renders. Age must not be the one field that
    turns a bad date into a traceback on the evening a board pack is being produced —
    it reports "unknown", which is what it actually knows.
    """
    if not value:
        return None
    try:
        return (date.fromisoformat(today) - date.fromisoformat(str(value)[:10])).days
    except ValueError:
        return None
```

- [ ] **Step 5: Read the threshold in `Context.__init__`**

In `skills/risk-register/renderers/_common.py`, in `Context.__init__` (line 304), after:

```python
        self.today = args.today
```

insert:

```python
        # Band width for confirmation age. Reporting furniture only: nothing in this
        # skill expires, suppresses or rescores on age. See references/dashboards.md.
        self.age_threshold = int(getattr(args, "age_threshold", 180) or 180)
```

Then, at the end of `__init__`, after:

```python
        self.decisions = self._decisions()
```

insert:

```python
        self.confirmation = self._confirmation_rollup()
```

Note the ordering: `_confirmation_rollup()` reads `self.risks`, which is built at line 346, so it must come after that. `self.decisions` is already the last line, so appending here is correct.

- [ ] **Step 6: Derive the per-risk fields**

In `skills/risk-register/renderers/_common.py`, add this method to `Context`, immediately **after** `_history_for` (line 357-358):

```python
    def _history_for(self, rid: str) -> list[dict]:
        return [e for e in self.reg.get("history", []) if e.get("riskId") == rid]
```

insert:

```python
    def _confirmation(self, hist: list[dict]) -> dict:
        """When this risk was last affirmed, by whom, and how old that is.

        Derived from history[] and nothing else — there is no stored age field and there
        must never be one, on the same grounds as every other derived value here.

        Only `sr.AGE_AFFIRMING` events count: someone asserting something about the
        risk's magnitude or its treatment decision. A note, a rewording, a theme move, a
        status flip and a snapshot deliberately do not, because an age that any edit
        resets makes a "stalest" list worthless — the same rule nist-csf states in
        references/schema.md.

        A risk with no affirming event — a v1 register, a fresh import-gaps — yields
        None rather than a guess, and is counted in its own undated bucket.
        """
        affirming = [e for e in hist
                     if e.get("type") in sr.AGE_AFFIRMING and e.get("ts")]
        if not affirming:
            return {"lastConfirmedAt": None, "lastConfirmedBy": None,
                    "confirmationAgeDays": None, "confirmationBand": None}
        last = max(affirming, key=lambda e: e["ts"])
        days = _days_since(last["ts"], self.today)
        return {
            "lastConfirmedAt": str(last["ts"])[:10],
            "lastConfirmedBy": (last.get("actor") or "").strip() or None,
            "confirmationAgeDays": days,
            "confirmationBand": (sr.age_band(days, self.age_threshold)
                                 if days is not None else None),
        }
```

Then in `_enrich` (line 360), replace:

```python
            "reviewDate": r.get("reviewDate") or "",
            "reviewOverdue": (r.get("status") != "closed"
                              and _overdue(r.get("reviewDate"), self.today)),
```

with:

```python
            "reviewDate": r.get("reviewDate") or "",
            "reviewOverdue": (r.get("status") != "closed"
                              and _overdue(r.get("reviewDate"), self.today)),
            # A reviewDate is a deadline a human committed to, so passing it is a fact,
            # not decay — the flag stays boolean. The day count exists only so renderers
            # can rank by how badly it slipped, without changing the semantics.
            "reviewOverdueDays": (_days_since(r.get("reviewDate"), self.today)
                                  if (r.get("status") != "closed"
                                      and _overdue(r.get("reviewDate"), self.today))
                                  else None),
```

and add the confirmation fields to the same returned dict, immediately before `"history": self._history_for(r["id"]),`:

```python
            **self._confirmation(self._history_for(r["id"])),
            "history": self._history_for(r["id"]),
```

- [ ] **Step 7: Stop a "nothing changed" rationale from explaining a change**

**A board-facing defect that Task 3 created and handed here.** Reproduced on real rendered
output: score a risk from residual 2×2 to 5×5 with a rationale, then `confirm` it, and the
board change log reads

> **worsened** — R-001 Third-party access — residual **Low → Critical** · now over appetite —
> *"reviewed at the forum; unchanged"*

Self-contradictory, on the artifact directors actually read. The cause is
`_rationales_since_baseline`: it walks history forward and does `out[e["riskId"]] = e["rationale"]`,
so the **last** rationale wins — and a `risk-confirmed` rationale now overwrites the
`score-changed` one that actually explains the move.

`_cmd_confirm`'s docstring in `score_register.py` carries a `KNOWN INTERACTION` handover note
with the reproduction. **Remove that note as part of this step**, once the defect is closed.

Replace `_rationales_since_baseline` (around line 407) with:

```python
    # Event types whose rationale can explain a change-log entry. `risk-confirmed` is
    # deliberately absent: it asserts that nothing changed, so letting it supply the "why"
    # for a score move renders "residual Low → Critical — 'reviewed at the forum;
    # unchanged'" on a board page. Its rationale is not worthless — it is the audit trail
    # for the confirmation itself, and the confirmation-age panel is where it belongs.
    # `snapshot-created` is absent because it carries no riskId to key on.
    CHANGE_EXPLAINING = frozenset({
        "risk-added", "risk-updated", "score-changed", "status-changed", "theme-changed",
        "risk-accepted", "acceptance-revalidated", "response-changed", "import-merged",
    })

    def _rationales_since_baseline(self) -> dict[str, str]:
        """Rationales logged after the last snapshot — the 'why' behind this period's moves.

        Newest-wins per risk, but only among events that actually changed something. See
        CHANGE_EXPLAINING: an event asserting that nothing changed must never caption a
        change.
        """
        hist = self.reg.get("history", [])
        cut = 0
        for i, e in enumerate(hist):
            if e.get("type") == "snapshot-created":
                cut = i + 1
        out = {}
        for e in hist[cut:]:
            if (e.get("riskId") and e.get("rationale")
                    and e.get("type") in self.CHANGE_EXPLAINING):
                out[e["riskId"]] = e["rationale"]
        return out
```

Add a check to `confirmation-age.sh` reproducing the exact scenario — score a risk with one
rationale, confirm it with another, render the board, and assert the change-log entry for that
risk carries the **score** rationale and not the confirmation one. Then **prove it binds**: add
`"risk-confirmed"` to `CHANGE_EXPLAINING` and confirm the check fails.

`CHANGE_EXPLAINING` must be a subset of `sr.KNOWN_EVENT_TYPES` — assert that too, so a typo'd
event name here fails the suite rather than silently never matching.

- [ ] **Step 8: Add the rollup**

In `skills/risk-register/renderers/_common.py`, add this method to `Context`, immediately **after** `_decisions` (which ends at line 585 with `return out`):

```python
    def _confirmation_rollup(self) -> dict:
        """Confirmation-age distribution over the live register.

        Live only, for the same reason live_summary() exists: a closed risk keeps its
        last confirmation date forever, and letting it sit in the distribution means the
        freshness picture never improves as risks are treated out.

        `undated` is not a band. It is the absence of a date rather than a distance from
        one, and folding it into `within` would report a guess as a measurement while
        folding it into `wellBeyond` would invent an age nobody recorded.
        """
        live = [r for r in self.risks if r.get("status") != "closed"]
        bands = {b: 0 for b in sr.AGE_BANDS}
        undated = 0
        for r in live:
            band = r["confirmationBand"]
            if band is None:
                undated += 1
            else:
                bands[band] += 1
        return {
            "bands": bands,
            "undated": undated,
            "live": len(live),
            "thresholdDays": self.age_threshold,
            # Oldest first, so a renderer can name the worst few without re-sorting.
            "wellBeyond": sorted(
                (r for r in live if r["confirmationBand"] == "wellBeyond"),
                key=lambda r: -(r["confirmationAgeDays"] or 0)),
        }
```

- [ ] **Step 9: Run the test to verify it passes**

Run: `./skills/risk-register/evals/confirmation-age.sh 2>&1 | tail -20`

Expected: 14 checks, all `PASS`, ending `confirmation-age: all checks passed`.

- [ ] **Step 10: Prove the non-affirming test binds**

The check that matters most is "R-002 still dates from risk-added". Confirm it dies when the mechanism does:

```bash
cd /Users/darren/Documents/GitHub/cac-ciso-toolkit
cp skills/risk-register/scripts/score_register.py /tmp/sr2.bak
python3 - <<'PY'
import pathlib
p = pathlib.Path("skills/risk-register/scripts/score_register.py")
s = p.read_text()
old = '''AGE_AFFIRMING = frozenset({
    "risk-added", "score-changed", "risk-confirmed", "risk-accepted",'''
new = '''AGE_AFFIRMING = frozenset({
    "risk-added", "score-changed", "risk-confirmed", "risk-accepted",
    "risk-updated", "status-changed",'''
assert old in s
p.write_text(s.replace(old, new, 1))
PY
./skills/risk-register/evals/confirmation-age.sh 2>&1 | tail -8
cp /tmp/sr2.bak skills/risk-register/scripts/score_register.py
./skills/risk-register/evals/confirmation-age.sh 2>&1 | tail -2
```

Expected: the mutant run FAILS on `R-002 still dates from risk-added` (and the score_register self-test would independently fail its `does NOT affirm` assertions). The restore returns all checks to PASS.

- [ ] **Step 11: Confirm the existing suites are untouched and commit**

```bash
python3 skills/risk-register/scripts/score_register.py self-test 2>&1 | tail -2
./skills/risk-register/evals/board-safety.sh 2>&1 | tail -2
./skills/risk-register/evals/responsive.sh 2>&1 | tail -2
PY=/usr/bin/python3 ./skills/risk-register/evals/python-compat.sh /usr/bin/python3 2>&1 | tail -1
git add skills/risk-register/renderers/_common.py skills/risk-register/evals/confirmation-age.sh
git commit -m "feat(risk-register): derive confirmation age from history, never stored

Four derived fields off the newest age-affirming event, plus reviewOverdueDays.
A risk with no affirming event yields null and lands in its own undated bucket —
never inferred, never backfilled, on the same grounds nist-csf refuses to
backfill confirmedAt from lastReviewed.

reviewOverdue stays boolean: a missed deadline a human committed to is a fact,
not decay. The day count only lets renderers rank it.

A malformed date reports 'unknown' rather than raising. Age must not be the one
field that turns a typo into a traceback on a board night."
```

---

### Task 5: The operational "Confirmation age" panel

**Files:**
- Modify: `skills/risk-register/renderers/render_dashboard.py` (`attention_lists` at line 79)

- [ ] **Step 1: Write the failing test**

Append to `skills/risk-register/evals/confirmation-age.sh`, immediately **before** the final `echo` / summary block (i.e. after the `while IFS=... done < "$work/out.txt"` loop):

```bash
# The working view gets the distribution — a CISO ranking work needs the shape, not a
# sentence. Rendered rather than unit-tested because the panel is the deliverable.
"$PY" "$RR/renderers/render_dashboard.py" "$work/a.rr" "$work/dash.html" --offline >/dev/null || {
  echo "FIXTURE FAILED — render_dashboard errored"; exit 1; }
grep -q 'Confirmation age' "$work/dash.html"
chk "$n" "operational dashboard renders a Confirmation age panel" \
    "$([ $? -eq 0 ] && echo PASS || echo FAIL)"
n=$((n + 1))
grep -q 'confirmed .* ago' "$work/dash.html"
chk "$n" "per-risk card shows when it was last confirmed" \
    "$([ $? -eq 0 ] && echo PASS || echo FAIL)"
n=$((n + 1))
```

- [ ] **Step 2: Run it to verify it fails**

Run: `./skills/risk-register/evals/confirmation-age.sh 2>&1 | tail -6`

Expected: the two new checks report `FAIL`.

- [ ] **Step 3: Add the panel**

In `skills/risk-register/renderers/render_dashboard.py`, in `attention_lists`, replace:

```python
    if not cards:
        cards = ('<div class="att" style="border-left-color:' + C.BAND["low"] + '">'
                 '<h3>Nothing flagged</h3><p class="d">No risk is over appetite, past review, '
                 'unowned, or carrying a stale acceptance.</p></div>')
    return cards
```

with:

```python
    if not cards:
        cards = ('<div class="att" style="border-left-color:' + C.BAND["low"] + '">'
                 '<h3>Nothing flagged</h3><p class="d">No risk is over appetite, past review, '
                 'unowned, or carrying a stale acceptance.</p></div>')
    return cards + confirmation_panel(ctx)


AGE_BAND_LABEL = {"within": "within", "approaching": "approaching",
                  "beyond": "beyond", "wellBeyond": "well beyond"}


def confirmation_panel(ctx: C.Context) -> str:
    """How old the determinations on this register are, as a distribution.

    This is the working view, so it gets the shape rather than a sentence — the reader
    is deciding what to look at next, and "three risks have not been re-affirmed in over
    a year" is a work queue.

    Nothing here suppresses, expires or rescores anything. The bands report distance from
    a cadence the reader chose; whether that distance matters for a given risk is the
    reader's judgement, because a supplier concentration and a patching backlog go stale
    at completely different rates.
    """
    c = ctx.confirmation
    if not c["live"]:
        return ""
    t = c["thresholdDays"]
    edges = {"within": f"0–{t // 2}d", "approaching": f"{t // 2 + 1}–{t}d",
             "beyond": f"{t + 1}–{t * 2}d", "wellBeyond": f"over {t * 2}d"}
    colour = {"within": C.BAND["low"], "approaching": C.BAND["medium"],
              "beyond": C.BAND["high"], "wellBeyond": C.BAND["critical"]}
    rows = "".join(
        f'<li><b>{c["bands"][b]}</b> '
        f'<span style="color:{C.BAND_TEXT[k]};font-weight:700">{AGE_BAND_LABEL[b]}</span>'
        f'<span class="d">{edges[b]}</span></li>'
        for b, k in (("within", "low"), ("approaching", "medium"),
                     ("beyond", "high"), ("wellBeyond", "critical")))
    if c["undated"]:
        rows += (f'<li><b>{c["undated"]}</b> no confirmation record'
                 f'<span class="d">never affirmed since the register was created</span></li>')
    return (f'<div class="att" style="border-left-color:{C.SLATE}">'
            f'<h3>Confirmation age <span class="cnt">{c["live"]}</span></h3>'
            f'<div class="d">How long since anyone affirmed each live risk’s score or '
            f'treatment decision. Scores do not expire — age is reported and you judge.</div>'
            f'<ul class="plain">{rows}</ul></div>')
```

Note `colour` is defined for symmetry with the band ramp but the row markup uses `C.BAND_TEXT` directly, because these are coloured words on the light workbench rather than fills — `C.BAND` values run 1.5–2.6:1 as text and are unreadable. Delete the unused `colour` dict if your linter objects.

- [ ] **Step 4: Add the per-risk confirmation line**

In `skills/risk-register/renderers/render_dashboard.py`, in `attention_lists`, replace the `items` assignment:

```python
        items = "".join(f'<li><b>{r["id"]}</b> {C.esc(r["title"])}'
                        f'{PROVTAG if r.get("provisionalTitle") else ""}'
                        f'<span class="d">{detail(r)}</span></li>' for r in rs)
```

with:

```python
        items = "".join(f'<li><b>{r["id"]}</b> {C.esc(r["title"])}'
                        f'{PROVTAG if r.get("provisionalTitle") else ""}'
                        f'<span class="d">{detail(r)}{_confirmed_note(r)}</span></li>'
                        for r in rs)
```

and add this helper immediately **before** `def attention_lists(`:

```python
def _confirmed_note(r: dict) -> str:
    """`· confirmed 42d ago · D. Alleyne`, or an honest statement that nobody has.

    Sits beside the review date rather than replacing it: the review date is a deadline
    somebody committed to, and the confirmation age is how long since anyone acted on it.
    Two different facts, and collapsing them was the asymmetry this work exists to fix.
    """
    days = r.get("confirmationAgeDays")
    if days is None:
        return ' · never confirmed'
    who = r.get("lastConfirmedBy")
    return f' · confirmed {days}d ago' + (f' · {C.esc(who)}' if who else "")
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `./skills/risk-register/evals/confirmation-age.sh 2>&1 | tail -6`

Expected: 16 checks, all `PASS`, ending `confirmation-age: all checks passed`.

- [ ] **Step 6: Check layout and contrast did not regress**

```bash
./skills/risk-register/evals/responsive.sh 2>&1 | tail -3
node skills/risk-register/evals/contrast-check.mjs 2>&1 | tail -3
```

Expected: both pass. The new panel adds coloured band words on the light workbench, which is exactly the class of change `contrast-check.mjs` exists to catch — `BAND` fill values run 1.5–2.6:1 as text, which is why `_confirmed_note` and `confirmation_panel` use `BAND_TEXT`.

- [ ] **Step 7: Commit**

```bash
git add skills/risk-register/renderers/render_dashboard.py \
        skills/risk-register/evals/confirmation-age.sh
git commit -m "feat(risk-register): confirmation-age panel on the working view

Operational views get the distribution: the reader is deciding what to look at
next, and 'three risks have not been re-affirmed in over a year' is a work queue.
Per-risk cards carry 'confirmed 42d ago · <actor>' beside the review date rather
than instead of it — a committed deadline and the age of the last affirmation are
two different facts.

Band words take BAND_TEXT, not BAND: the fill ramp runs 1.5-2.6:1 as text on the
light workbench and is unreadable."
```

---

### Task 6: The board freshness sentence

**Files:**
- Modify: `skills/risk-register/renderers/render_board.py` (`summary_block` at line 152)

- [ ] **Step 1: Write the failing test**

Append to `skills/risk-register/evals/confirmation-age.sh`, immediately before the final summary block:

```bash
# The board gets ONE sentence. A board does not need a histogram; it needs to know
# whether the picture in front of it is fresh.
"$PY" "$RR/renderers/render_board.py" "$work/a.rr" "$work/board.html" --offline >/dev/null || {
  echo "FIXTURE FAILED — render_board errored"; exit 1; }
grep -q 'live risks' "$work/board.html"
chk "$n" "board renders one freshness sentence" \
    "$([ $? -eq 0 ] && echo PASS || echo FAIL)"
n=$((n + 1))
# IDs only, never titles: an imported gap still carries CSF wording, and this line
# must not become a fourth route for framework text onto a board page.
"$PY" - "$work" <<'PY' > "$work/titles.txt"
import json, pathlib, sys, re
work = pathlib.Path(sys.argv[1])
reg = json.loads((work / "a.rr").read_text())
html = (work / "board.html").read_text()
seg = re.search(r'Of \d+ live risks.*?</div>', html, re.S)
leaks = [r["title"][:40] for r in reg["risks"]
         if seg and len(r["title"]) > 12 and r["title"][:25] in seg.group(0)]
print("PASS" if not leaks else "FAIL " + "; ".join(leaks[:2]))
PY
chk "$n" "freshness sentence cites IDs, never titles" "$(cat "$work/titles.txt")"
n=$((n + 1))
# The numbers in the sentence must sum to the denominator the sentence opens with. An
# earlier draft reported only the best and worst bands, leaving a silent remainder — a
# board figure that does not add up. Parse the rendered text, do not re-derive from the
# register, because the defect is in the prose and not in the data.
"$PY" - "$work" <<'PY' > "$work/sums.txt"
import pathlib, re, sys
html = (pathlib.Path(sys.argv[1]) / "board.html").read_text()
m = re.search(r"Of (\d+) live risks: (.*?)\. Scores do not expire", html, re.S)
if not m:
    print("FAIL freshness sentence not found in the expected shape")
else:
    total = int(m.group(1))
    # Leading integer of each semicolon-separated clause; ignore digits inside day ranges
    # and inside parenthesised risk IDs.
    parts = [c.strip() for c in m.group(2).split(";")]
    counts = [int(re.match(r"(\d+)", p).group(1)) for p in parts if re.match(r"(\d+)", p)]
    if len(counts) != len(parts):
        print(f"FAIL a clause does not begin with a count: {parts!r}")
    elif sum(counts) != total:
        print(f"FAIL clauses sum to {sum(counts)}, sentence says {total} live risks")
    else:
        print("PASS")
PY
chk "$n" "freshness sentence numbers sum to its own denominator" "$(cat "$work/sums.txt")"
n=$((n + 1))
```

**Prove this one binds** — it is guarding prose, so it is easy to write vacuously. Drop the
`approaching` clause from `freshness_line` and confirm the check FAILS with a sum mismatch,
using a fixture that actually has a risk in that band. If your fixture has every live risk in
`within`, the check passes trivially and proves nothing: build one with a spread first, the
same lesson as correction **C4**.

- [ ] **Step 2: Run it to verify it fails**

Run: `./skills/risk-register/evals/confirmation-age.sh 2>&1 | tail -6`

Expected: `board renders one freshness sentence` reports `FAIL`.

- [ ] **Step 3: Add the sentence**

In `skills/risk-register/renderers/render_board.py`, replace `summary_block` (line 152):

```python
def summary_block(ctx: C.Context) -> str:
    if ctx.tr.executive_summary:
        return (f'<p class="lead">{C.esc(ctx.tr.executive_summary)}</p>'
                f'<div class="note">Executive narrative from the ciso-board-translation skill.</div>')
    return (f'<p class="lead placeholder">{C.PLACEHOLDER}</p>'
            f'<div class="note">The figures on this page are derived from the register and are '
            f'complete; only the narrative is missing.</div>')
```

with:

```python
def freshness_line(ctx: C.Context) -> str:
    """One sentence on how current this picture is. IDs only, never titles.

    Belongs in the executive summary rather than in "Decisions for the board": it is a
    caveat on the whole document, not an ask. The missed-review line in _decisions() is
    the right home for "somebody missed a commitment" and is unchanged.

    Titles are withheld on purpose. An imported gap still carries raw CSF wording until
    somebody rewords it, and this line would otherwise be a fourth route for framework
    text onto a board page — the third one shipped for a full release before anybody
    noticed. IDs carry no such payload.

    Says nothing about confidence. It reports how long ago each risk was affirmed and
    leaves the reader to decide what that means.
    """
    c = ctx.confirmation
    if not c["live"]:
        return ""
    t, b = c["thresholdDays"], c["bands"]
    # Every clause is an EXCLUSIVE band, and together with `undated` they partition the live
    # register — so the numbers in this sentence sum to the "Of N live risks" it opens with.
    # Reporting only the best and worst bands leaves a silent remainder, which on a board
    # page is a figure that does not add up. Zero-count bands are dropped rather than
    # printed as "0", so the sentence stays short when the picture is simple.
    clauses = [
        (b["within"], f'{b["within"]} confirmed within the last {t // 2} days'),
        (b["approaching"], f'{b["approaching"]} between {t // 2 + 1} and {t} days ago'),
        (b["beyond"], f'{b["beyond"]} between {t + 1} and {t * 2} days ago'),
    ]
    bits = [text for count, text in clauses if count]
    old = c["wellBeyond"]
    if old:
        shown = old[:5]
        ids = ", ".join(r["id"] for r in shown)
        more = f", and {len(old) - len(shown)} more" if len(old) > len(shown) else ""
        bits.append(f'{len(old)} not confirmed in over {t * 2} days ({ids}{more})')
    if c["undated"]:
        bits.append(f'{c["undated"]} carrying no confirmation record')
    return (f'<div class="note">Of {c["live"]} live risks: ' + "; ".join(bits) + '. '
            f'Scores do not expire — age is reported so the board can judge it.</div>')


def summary_block(ctx: C.Context) -> str:
    if ctx.tr.executive_summary:
        return (f'<p class="lead">{C.esc(ctx.tr.executive_summary)}</p>'
                f'<div class="note">Executive narrative from the ciso-board-translation skill.</div>'
                + freshness_line(ctx))
    return (f'<p class="lead placeholder">{C.PLACEHOLDER}</p>'
            f'<div class="note">The figures on this page are derived from the register and are '
            f'complete; only the narrative is missing.</div>'
            + freshness_line(ctx))
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `./skills/risk-register/evals/confirmation-age.sh 2>&1 | tail -6`

Expected: 18 checks, all `PASS`.

- [ ] **Step 5: Run the board-safety and layout suites**

```bash
./skills/risk-register/evals/board-safety.sh 2>&1 | tail -3
./skills/risk-register/evals/responsive.sh 2>&1 | tail -2
```

Expected: `board-safety: all checks passed` (still 7 checks — Task 7 adds to it) and responsive passes.

- [ ] **Step 6: Commit**

```bash
git add skills/risk-register/renderers/render_board.py \
        skills/risk-register/evals/confirmation-age.sh
git commit -m "feat(risk-register): one freshness sentence for the board

Operational views get the distribution; board views get a sentence. It goes in
the executive summary, not in 'Decisions for the board' — it is a caveat on the
whole document rather than an ask.

Cites risk IDs and never titles. An imported gap carries raw CSF wording until
somebody rewords it, and this line would otherwise be a fourth route for
framework text onto a board page."
```

---

### Task 7: Assert the claim we decline to make

**Files:**
- Modify: `skills/risk-register/evals/board-safety.sh` (add checks 8 and 9 before the final summary block)

- [ ] **Step 1: Write the failing test**

In `skills/risk-register/evals/board-safety.sh`, immediately **before** the final block:

```bash
echo
if [ "$fails" -eq 0 ]; then
  echo "board-safety: all checks passed"
```

insert:

```bash
# 8. The board freshness line renders, and reports the live population.
chk 8 "board freshness line present and counts live risks" "$("$PY" - "$work" <<'PY'
import json, pathlib, re, sys
work = pathlib.Path(sys.argv[1])
reg = json.loads((work / "r.rr").read_text())
live = len([r for r in reg["risks"] if r.get("status") != "closed"])
html = (work / "render_board.html").read_text()
m = re.search(r"Of (\d+) live risks", html)
if not m:
    print("FAIL freshness line absent from the board")
elif int(m.group(1)) != live:
    print(f"FAIL freshness line says {m.group(1)} live, register has {live}")
else:
    print("PASS")
PY
)"

# 9. No confidence vocabulary reaches a board-facing view.
#
# An inverted test: it fails if anyone later reintroduces the claim this toolkit
# deliberately declines to make. The engine reports AGE — a number it can derive from
# stored data. "Confidence" is a decay rate it cannot derive, on a risk whose real decay
# rate the tool already argues is unknowable in general. Naming an age band after
# confidence would commit the engine to exactly that.
#
# If a future fixture legitimately needs one of these words, change the fixture — not
# this list. The list is the decision.
chk 9 "no confidence vocabulary in any board-facing view" "$("$PY" - "$work" <<'PY'
import pathlib, re, sys
work = pathlib.Path(sys.argv[1])
banned = ("confidence", "degrading", "degraded", "decaying", "decay",
          "current (assumed)", "assumed current", "unreliable")
hits = []
for name in ("render_board", "render_report"):          # board-facing only
    text = (work / f"{name}.html").read_text().lower()
    for word in banned:
        if word in text:
            i = text.index(word)
            hits.append(f"{name}:{word}:…{text[max(0, i - 25):i + 25]}…")
print("PASS" if not hits else "FAIL " + " | ".join(hits[:2]))
PY
)"
```

- [ ] **Step 2: Run it to verify both checks are meaningful**

Run: `./skills/risk-register/evals/board-safety.sh 2>&1 | tail -6`

Expected: 9 checks, all `PASS`, ending `board-safety: all checks passed`. Check 8 exercises the code added in Task 6; check 9 should already pass, which is correct — it is a regression guard, not a bug report.

- [ ] **Step 3: Prove check 9 can actually fail**

An inverted test that cannot fail is decoration. Confirm it bites:

```bash
cd /Users/darren/Documents/GitHub/cac-ciso-toolkit
cp skills/risk-register/renderers/render_board.py /tmp/rb.bak
python3 - <<'PY'
import pathlib
p = pathlib.Path("skills/risk-register/renderers/render_board.py")
s = p.read_text()
old = 'Scores do not expire — age is reported so the board can judge it.'
assert old in s
p.write_text(s.replace(old, 'Confidence in these scores is degrading with age.', 1))
PY
./skills/risk-register/evals/board-safety.sh 2>&1 | tail -4
cp /tmp/rb.bak skills/risk-register/renderers/render_board.py
./skills/risk-register/evals/board-safety.sh 2>&1 | tail -2
```

Expected: the mutant run FAILS check 9, naming `confidence` and `degrading`. The restore returns all 9 to PASS. If the mutant passes, the word list is not reaching the rendered HTML and the check must be fixed before continuing.

- [ ] **Step 4: Commit**

```bash
git add skills/risk-register/evals/board-safety.sh
git commit -m "test(board-safety): assert the confidence claim stays unmade

Check 9 is inverted: it fails if anyone reintroduces confidence vocabulary on a
board-facing view. The engine reports age, which it can derive; confidence is a
decay rate it cannot, on a risk whose real decay rate the tool already argues is
unknowable in general.

Check 8 asserts the freshness line renders and counts the live population, so the
sentence cannot silently disappear or drift off the board's own denominator."
```

---

### Task 8: Documentation

**Files:**
- Modify: `skills/risk-register/references/schema.md` (event list at line 122-124; new Confirmation age section)
- Modify: `skills/risk-register/references/dashboards.md`
- Modify: `skills/risk-register/SKILL.md`
- Modify: `skills/nist-csf/references/schema.md`
- Modify: `skills/nist-csf/references/dashboards.md`
- Modify: `README.md` (the non-expiry bullet, around lines 75-85)

- [ ] **Step 1: Fix and extend the risk-register event list**

In `skills/risk-register/references/schema.md`, replace lines 122-124:

```markdown
Event `type` values: `risk-added`, `risk-updated`, `score-changed`, `response-changed`,
`status-changed`, `risk-accepted`, `acceptance-revalidated`, `risk-closed`, `risk-reopened`,
`risk-deleted`, `theme-changed`, `settings-changed`, `snapshot-created`.
```

with:

```markdown
Event `type` values. The **age-affirming** column is what resets a risk's confirmation age
(see "Confirmation age" below); everything else leaves it exactly where it was.

| type | written by | age-affirming |
|---|---|---|
| `register-created` | `init` | no |
| `risk-added` | `add` | **yes** |
| `risk-confirmed` | `confirm` | **yes** |
| `score-changed` | `set-score` | **yes** |
| `risk-accepted` | `accept` | **yes** |
| `acceptance-revalidated` | *not yet written* | **yes** |
| `risk-updated` | `set-text` | no |
| `status-changed` | `set-status` | no |
| `theme-changed` | `add-theme`, `set-theme` | no |
| `snapshot-created` | `snapshot` | no |
| `import-merged` | `import-gaps --write` | no |
| `response-changed`, `risk-closed`, `risk-reopened`, `risk-deleted`, `settings-changed` | *not yet written* | no |

Only an assertion about a risk's **magnitude** or its **treatment decision** affirms age. A
rewording, a theme move, a status flip and a snapshot deliberately do not: an age that any
edit resets makes the confirmation-age report worthless, which is the same rule
`nist-csf/references/schema.md` states about notes and staleness.

`score_register.py` asserts this table is total. A newly-emitted event type fails the
self-test until somebody classifies it, rather than defaulting to "does not affirm age" by
omission.
```

- [ ] **Step 2: Document the confirmation-age model**

In `skills/risk-register/references/schema.md`, immediately after the block you just replaced, add:

```markdown
## Confirmation age

**Scores do not expire.** No threshold in this skill expires a score, suppresses a figure,
or changes a band on the strength of a date. Age is reported and the reader judges — a
supplier concentration and a patching backlog go stale at completely different rates, and
the tool does not claim to know either rate.

Four values are derived per risk, from `history[]` only. Nothing is stored:

| field | meaning |
|---|---|
| `lastConfirmedAt` | newest `ts` among that risk's age-affirming events |
| `lastConfirmedBy` | that event's `actor` |
| `confirmationAgeDays` | whole days from `lastConfirmedAt` to `--today` |
| `confirmationBand` | the band below, or `null` |

Bands are anchored to `--age-threshold` (`T`, default 180 days, matching `nist-csf`'s
`settings.reporting.ageThresholdDays`). Every boundary is inclusive of the lower band, so a
risk at exactly `T` is `approaching` and not yet `beyond`:

| band | boundary | at T=180 |
|---|---|---|
| `within` | `d ≤ T//2` | ≤ 90d |
| `approaching` | `d ≤ T` | ≤ 180d |
| `beyond` | `d ≤ 2T` | ≤ 360d |
| `wellBeyond` | `d > 2T` | > 360d |

The band names describe distance from a cadence you chose. They are **not** confidence
words and never become them: age is derivable from stored data, confidence is not.

A risk with no age-affirming event — a v1 register, a fresh `import-gaps` — yields `null`
and is reported in its own **undated** count. Never inferred, never backfilled.

`reviewDate` is a different thing and stays boolean. It is a deadline a human committed to,
so passing it is a fact rather than decay; `reviewOverdue` remains a flag and
`reviewOverdueDays` exists only so renderers can rank by how far it slipped.

Recording a re-affirmation:

```bash
python3 scripts/score_register.py confirm register.rr R-004 \
  --why "reviewed at the November risk forum; controls unchanged and still effective" \
  --review 2027-05-31
```

`--why` is required. Asserting that a risk is still right is a material claim and belongs in
the audit trail on the same terms as a score change. Before `confirm` existed the only way
to record one was `set-score` at an identical value, which writes a `score-changed` event
where no score changed.
```

- [ ] **Step 3: Document the surfacing**

In `skills/risk-register/references/dashboards.md`, append:

```markdown
## Confirmation age

Operational views get the distribution; board views get one sentence. A board does not need
an age histogram — it needs to know whether the picture in front of it is fresh.

- **`render_dashboard.py`** — a "Confirmation age" panel counting live risks by band, plus
  the undated count, and `confirmed 42d ago · D. Alleyne` on each attention card beside the
  review date rather than instead of it.
- **`render_board.py`** — one sentence in the executive summary: *"Of 24 live risks, 18 were
  confirmed within the last 90 days; 3 have not been confirmed in over 360 days (R-004,
  R-011, R-019); 2 carry no confirmation record."* It cites risk **IDs only, never titles**,
  because an imported gap carries raw CSF wording until somebody rewords it and this line
  must not become another route for framework text onto a board page.
- **`render_report.py`** — unchanged. The printable report already carries the missed-review
  line via "Decisions for the board".

The sentence sits in the executive summary rather than under "Decisions for the board": it
is a caveat on the whole document, not an ask.

`--age-threshold DAYS` (default 180) sets the band width on all three renderers. It is
reporting furniture and nothing else — it flags nothing, gates nothing, suppresses nothing,
and changes no score. Settings-level parity with `nist-csf`'s
`settings.reporting.ageThresholdDays` is deferred.

`board-safety.sh` check 9 fails if confidence vocabulary ever reaches a board-facing view.
```

- [ ] **Step 4: Document the command in SKILL.md**

In `skills/risk-register/SKILL.md`, find the command list that names `accept` and add a
`confirm` entry alongside it, matching the file's existing formatting:

```markdown
- `confirm <register.rr> <id> --why '...' [--review YYYY-MM-DD]` — record that a risk was
  reviewed and nothing changed. Resets confirmation age; changes no score, status or band.
  Use this instead of re-entering an identical score, which would log a `score-changed`
  event where nothing changed.
```

Read the surrounding lines first and match their exact bullet style — do not assume the
format above matches.

- [ ] **Step 5: Document the bands in nist-csf**

In `skills/nist-csf/references/schema.md`, find the existing passage on age and staleness
(search for `ageThresholdDays`) and add after it:

```markdown
### Age bands

`age.overall.bands` and `age.byFunction.<id>.bands` grade every dated confirmation by
distance from `settings.reporting.ageThresholdDays` (`T`, default 180). Boundaries are
inclusive of the lower band, so a rating at exactly `T` is `approaching`:

| band | boundary | at T=180 |
|---|---|---|
| `within` | `d ≤ T//2` | ≤ 90d |
| `approaching` | `d ≤ T` | ≤ 180d |
| `beyond` | `d ≤ 2T` | ≤ 360d |
| `wellBeyond` | `d > 2T` | > 360d |

`olderThanThreshold` is unchanged and **always equals `beyond + wellBeyond`**. The self-test
asserts that identity at two different thresholds, so the two notions cannot drift apart.

`undated` is not a band. A rating carried over from a v1 Profile has no `confirmedAt`, and
counting it as `within` would report a guess as a measurement while counting it as
`wellBeyond` would invent an age nobody recorded. It stays its own number.

Band names state distance from a cadence, never confidence. Ratings do not expire; new
material is what questions a rating, not the passage of time.
```

In `skills/nist-csf/references/dashboards.md`, find the passage describing the executive age
grid and the operational "Stalest" panel, and add:

```markdown
The executive age grid carries the band distribution alongside median, oldest and the
past-threshold count. Because `beyond + wellBeyond` is exactly the past-threshold figure,
the grid grades one population rather than reporting two.

Each "Stalest" row is **ordered** on `lastReviewed` and **banded** on `confirmedAt`. Those
are different fields on purpose — `confirmedAt` is never backfilled from `lastReviewed`,
because that would fabricate the attribution the schema exists to make honest — so the row
shows both, and a rating with no confirmation date says so instead of being given a band it
has not earned.
```

- [ ] **Step 6: Complete the README bullet**

In `README.md`, find the non-expiry bullet (around line 80, beginning `- **Ratings do not
expire.**`). Read it, then extend the `ageThresholdDays` sentence so it names the bands.
Append to that bullet:

```markdown
  Age is now reported in four bands derived from that same threshold `T` — `within` (≤ T/2),
  `approaching` (≤ T), `beyond` (≤ 2T), `wellBeyond` (> 2T) — in both skills. They are
  distance-from-cadence labels, not confidence labels: the engine reports how old a
  determination is and the reader judges what that means, because age is derivable from
  stored data and confidence is not.
```

Do not restructure the surrounding bullets. The coverage-vs-currency disambiguation landed
in #15 and is correct as it stands.

- [ ] **Step 7: Verify no doc drifted from the code**

```bash
cd /Users/darren/Documents/GitHub/cac-ciso-toolkit
# Every event type the docs claim is emitted must actually be emitted, and vice versa.
python3 - <<'PY'
import re, pathlib, sys
sys.path.insert(0, "skills/risk-register/scripts")
import score_register as sr
src = pathlib.Path("skills/risk-register/scripts/score_register.py").read_text()
emitted = set(re.findall(r'_append_event\(reg, "([a-z-]+)"', src))
print("emitted by code   :", sorted(emitted))
print("declared _EMITTED :", sorted(sr._EMITTED_EVENT_TYPES))
print("MATCH" if emitted == sr._EMITTED_EVENT_TYPES else "*** MISMATCH ***")
print("affirming ⊆ known :", sr.AGE_AFFIRMING <= sr.KNOWN_EVENT_TYPES)
PY
```

Expected: `MATCH` and `affirming ⊆ known : True`. A mismatch means `_EMITTED_EVENT_TYPES`
is stale — fix it, since the self-test's totality assertion depends on it being honest.

- [ ] **Step 8: Commit**

```bash
git add skills/risk-register/references/schema.md \
        skills/risk-register/references/dashboards.md \
        skills/risk-register/SKILL.md \
        skills/nist-csf/references/schema.md \
        skills/nist-csf/references/dashboards.md \
        README.md
git commit -m "docs: the age bands, and an event-type table that matches the code

schema.md documented five event types nothing writes and omitted two that are
written. It now lists what each command actually emits and whether it affirms
age, which is the fact a reader needs and the one the code asserts is total.

Both skills state the same stance in their own docs: scores and ratings do not
expire, age is reported, the reader judges. That sentence existed only on the
nist-csf side, which is exactly why the two skills read as disagreeing."
```

---

### Task 9: Version bump and full verification

**Files:**
- Modify: `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json` (two places), `.codex-plugin/plugin.json`

- [ ] **Step 1: Move all four version strings forward together**

Current version is `0.4.2`. This adds a subcommand and new derived output, so the target is
`0.5.0`.

```bash
cd /Users/darren/Documents/GitHub/cac-ciso-toolkit
python3 - <<'PY'
import json, pathlib
targets = [(".claude-plugin/plugin.json", ("version",)),
           (".claude-plugin/marketplace.json", ("version",)),
           (".claude-plugin/marketplace.json", ("plugins", 0, "version")),
           (".codex-plugin/plugin.json", ("version",))]
for path, keypath in targets:
    p = pathlib.Path(path)
    doc = json.loads(p.read_text())
    node = doc
    for k in keypath[:-1]:
        node = node[k]
    node[keypath[-1]] = "0.5.0"
    p.write_text(json.dumps(doc, indent=2) + "\n")
    print("set", path, ".".join(str(k) for k in keypath), "-> 0.5.0")
PY
./tools/check-versions.py
```

Expected: `consistency: all 4 version strings agree (0.5.0).`

Do not hand-edit these files one at a time. The guard exists because four strings drifted
apart once already, and the whole point is that they move together.

- [ ] **Step 2: Run every suite in the repo**

```bash
cd /Users/darren/Documents/GitHub/cac-ciso-toolkit
echo "=== version guard ===";      ./tools/check-versions.py --self-test 2>&1 | tail -1
echo "=== manifests ===";          ./tools/check-versions.py 2>&1 | tail -1
echo "=== risk-register ===";      python3 skills/risk-register/scripts/score_register.py self-test 2>&1 | tail -2
echo "=== nist-csf ===";           python3 skills/nist-csf/scripts/profile_analysis.py self-test 2>&1 | tail -1
echo "=== csfa compat ===";        python3 skills/nist-csf/scripts/csfa_compat.py self-test 2>&1 | tail -1
echo "=== board-safety ===";       ./skills/risk-register/evals/board-safety.sh 2>&1 | tail -1
echo "=== confirmation-age ===";   ./skills/risk-register/evals/confirmation-age.sh 2>&1 | tail -1
echo "=== responsive ===";         ./skills/risk-register/evals/responsive.sh 2>&1 | tail -1
echo "=== python floor ===";       PY=/usr/bin/python3 ./skills/risk-register/evals/python-compat.sh /usr/bin/python3 2>&1 | tail -1
```

Expected, with every count at or above baseline:

```
version guard      self-test: 19/19 checks passed
manifests          consistency: all 4 version strings agree (0.5.0).
risk-register      62/62 checks passed.
nist-csf           self-test: 494/494 checks passed
csfa compat        csfa-compat self-test: 47/47 checks passed
board-safety       board-safety: all checks passed          (9 checks)
confirmation-age   confirmation-age: all checks passed      (18 checks)
responsive         (passes)
python floor       python-compat: all N shipped files compile on 3.9.6
```

If any count is *below* its baseline (34 / 472 / 47 / 19), a test was deleted rather than
added. Find it before going further.

- [ ] **Step 3: Confirm the derived-not-stored rule still holds**

The single most important invariant in both skills. Assert no age field leaked into a
written file:

```bash
cd /Users/darren/Documents/GitHub/cac-ciso-toolkit
work=$(mktemp -d)
python3 skills/risk-register/scripts/score_register.py init "$work/v.rr" \
  --client "Verify Co" --assessor "D. Alleyne" >/dev/null
python3 skills/risk-register/scripts/score_register.py add "$work/v.rr" \
  --title "Test risk" --il 3 --ii 3 --rl 2 --ri 3 --why "verify" >/dev/null
python3 skills/risk-register/scripts/score_register.py confirm "$work/v.rr" R-001 \
  --why "verify" >/dev/null
python3 - "$work/v.rr" <<'PY'
import json, sys
raw = open(sys.argv[1]).read()
banned = ["lastConfirmedAt", "confirmationAgeDays", "confirmationBand",
          "lastConfirmedBy", "reviewOverdueDays"]
found = [b for b in banned if b in raw]
print("PASS: no derived age field is stored" if not found
      else "FAIL: stored derived fields " + ", ".join(found))
PY
```

Expected: `PASS: no derived age field is stored`.

- [ ] **Step 4: Commit and push as one PR**

```bash
cd /Users/darren/Documents/GitHub/cac-ciso-toolkit
git add .claude-plugin/plugin.json .claude-plugin/marketplace.json .codex-plugin/plugin.json
git commit -m "chore: 0.5.0 — graded age in both skills"
git push -u origin HEAD
gh pr create --title "feat: staleness as graded age, not confidence and not expiry" --body "$(cat <<'BODY'
Implements `docs/superpowers/specs/2026-07-29-staleness-graded-age-design.md`.

Four age bands — `within` / `approaching` / `beyond` / `wellBeyond` — derived from the
`ageThresholdDays` the user already configured (T/2, T, 2T), with identical semantics in
both skills.

**`nist-csf`** already implemented non-expiry; it gains a band counter and surfaces the
distribution. `olderThanThreshold` is unchanged and asserted equal to
`beyond + wellBeyond` at two different thresholds, so the two cannot drift apart.

**`risk-register`** had no last-confirmed date at all — a review three days overdue was
indistinguishable from one three years overdue. It gains a `confirm` subcommand, a
`risk-confirmed` event, and four fields derived from `history[]`. Nothing is stored.

**What this does not do**, stated so it does not creep back in: no "confidence" label
anywhere; no suppression or invalidation on age, ever; no change to acceptance expiry
(that timer is a human's stated time-box and enforcing it honours their judgment); no
stored age fields.

`board-safety.sh` check 9 is inverted — it fails if anyone reintroduces confidence
vocabulary on a board-facing view.

### Three corrections to the spec, found against the code

1. `schema.md` documented five event types nothing emits and omitted two that are
   emitted. The affirming set is now asserted total, so a new event type fails the suite
   until it is classified rather than defaulting to "does not affirm age".
2. The `nist-csf` "Stalest" panel sorts on `lastReviewed` but the bands measure
   `confirmedAt`. Rows now show both and band only the field the age model uses; a row
   with no confirmation date shows no band.
3. Spec §6 named `evals/board-safety.sh`; the real path is
   `skills/risk-register/evals/board-safety.sh`.

### Suites

| suite | before | after |
|---|---|---|
| risk-register self-test | 34 | 62 |
| nist-csf self-test | 472 | 494 |
| csfa_compat | 47 | 47 |
| board-safety | 7 | 9 |
| confirmation-age | — | 18 |
| version guard | 19 | 19 |

Each new regression test was mutation-tested: the mechanism was reverted and the test
confirmed to die.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
BODY
)"
```

Note: `main` requires all seven checks and has **no bypass** (`bypass_actors: []`,
`enforce_admins: true`), so the PR merges only on a fully green board.

---

## Self-review

**Spec coverage.** §3.1 bands → Task 1 + Task 3. §3.2 `_age()` counter → Task 1. §3.3
`confirm` + event → Task 3; derived fields → Task 4; `reviewOverdueDays` → Task 4;
`--age-threshold` → Task 4. §3.4 stance stated in `risk-register` → Task 8. §4 surfacing:
nist-csf operational + executive → Task 2; risk-register operational → Task 5; board →
Task 6. §5 docs → Task 8 (items 1–3; item 4 is Task 9). §6 testing → distributed, with
`board-safety.sh` inverted check in Task 7. §7 non-goals: no confidence label (asserted by
Task 7 check 9), no suppression on age (nothing added gates anything), acceptance expiry
untouched (`_accepted_and_current` is not modified by any task), no stored fields (asserted
by Task 9 step 3).

**Deliberately not done.** Settings-level `settings.reporting.ageThresholdDays` parity for
`risk-register` is deferred by spec §3.3, so `--age-threshold` is renderer-only.
`render_report.py` gets no freshness line — the spec's surfacing table does not list it, and
it already carries the missed-review line through `_decisions()`.

**Type consistency.** `age_band(days, threshold_days) -> str` and
`AGE_BANDS = ("within", "approaching", "beyond", "wellBeyond")` are the same in both skills.
`_days_since(value, today) -> int | None` is risk-register only; `nist-csf` keeps its
existing `_days_between(start, end) -> int`. Derived field names — `lastConfirmedAt`,
`lastConfirmedBy`, `confirmationAgeDays`, `confirmationBand` — are identical between Task 4
(where they are produced), Task 5 and Task 6 (where they are read), and the docs in Task 8.
`ctx.confirmation` keys `bands` / `undated` / `live` / `thresholdDays` / `wellBeyond` are
consistent across Tasks 4, 5 and 6.

**One risk worth naming.** `AGE_BAND_LABEL` is defined in both
`skills/nist-csf/renderers/render_operational.py` (Task 2) and
`skills/risk-register/renderers/render_dashboard.py` (Task 5), with **different values** —
the nist-csf one says "within cadence", the risk-register one says "within". That is
deliberate, because the two sit in different sentence shapes, but the shared name across two
skills invites a future editor to "unify" them. They cannot be unified: the skills ship
independently and cannot import each other.
