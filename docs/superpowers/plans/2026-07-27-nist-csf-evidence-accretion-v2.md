# NIST CSF Evidence Accretion (v2) — Increment 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a CSF Profile be built up from fragments arriving over time — record a source in seconds, confirm ratings later with attribution, and report a partial profile honestly.

**Architecture:** `.csfp` moves to schema `"2.0"`. The store gains an append-only `intake[]` of sources and three attribution fields per assessment. `set --current` refuses a write without `--source` and `--confirmed-by`. Everything else — evidence-pending, revisit, age, queue order, the four-way coverage split, the scope guard — is **derived in `analyze`, never stored**, exactly like every other derived number in this engine. Renderers stay projection-only.

**On the assertion counts below:** every `self-test: N/N checks passed` in this plan is arithmetic on the assertions written in that task, and it is a *prediction*. Read the real number off the output. If it differs, confirm the delta is explained by assertions you actually wrote before treating it as a problem — and carry the real number into `SKILL.md` in Task 13.

**Tech Stack:** Python 3.9-floor stdlib only (`skills/nist-csf/scripts/profile_analysis.py`, `renderers/*.py`); tests are in-script `self-test` assertions; visual gate is headless Chrome via `skills/risk-register/evals/responsive.sh`.

---

## Reconciling the design document with the repo

The design was written against an imagined schema. These are the actual bindings. **Use the right-hand column everywhere.**

| Design document says | Repo reality — use this |
|---|---|
| `ratings[subId]` map | `store["assessments"]` — a **list** of objects keyed by `subcategoryId` |
| `tier` (per-Subcategory rating) | `current` (and `target`). Per-Subcategory ratings are 0–3 **achievement ratings**; "Tier" means the Profile-level rigor characterization and must never be used for a rating |
| `na: false` | `applicability: "in-scope" \| "not-applicable"` |
| `note` | `notes` |
| `schemaVersion: 2` (integer) | `SCHEMA_VERSION = "2.0"` (**string** — nist-csf uses `"1.0"`; risk-register's integer 2 is a different file format) |
| `visual_check.js` | `skills/risk-register/evals/responsive.sh`, which drives `measure-width.mjs` + `contrast-check.mjs` and **already renders both CSF dashboards** |
| "the parity suite" | `profile_analysis.py self-test` (79 checks), `csfa_compat.py self-test` (28 checks), `profile_analysis.py validate`, `board-safety.sh`, `python-compat.sh` |
| "the Acme golden fixture" | `skills/nist-csf/examples/acme-manufacturing.csfa` → byte-parity against `acme-manufacturing-gaps.csv`, asserted by `csfa_compat.py self-test` |

Constraints the design does not mention but which bind this work:

- **Python floor is 3.9**, pinned in `.github/workflows/evals.yml`. No `match`, no runtime `X | Y`, no PEP 701 f-strings. Annotations are safe — every module has `from __future__ import annotations`.
- **`parse_flags` is a homegrown parser**, not argparse. `--x a b` → `["a","b"]`, `--x a` → `"a"`, `--x` → `True`. Always unwrap with `_s()` / `_list()`.
- **`analyze` is the only derivation point.** `references/dashboards.md` line 4 forbids computing anything in a renderer. Every new number goes in `analyze`.
- **Snapshots freeze `assessments`.** Snapshots taken before v2 hold v1-shaped assessments. Leave them alone — they are frozen history, and `compute_diff` only reads the five fields it already names.

## Decisions taken (design's open questions 1, 3, 4, plus two the design missed)

1. **Scope guard denominator = `assessed / inScope`, threshold 60%.** Not attribution. A v1 profile normalizes with attribution null on every rating, so an attribution-based guard would blank the headline on every profile shipped to date. Attribution is reported as its own count, beside the coverage split.
2. **Attribution is enforced on `--current` only.** Current is the evidence-derived claim the whole report rests on. Target is a risk-based decision already gated by `--rationale`, and gating it too would require reworking `quickstart-target`'s ~106-row bulk seed.
3. **Hard refusal, no escape hatch.** `set --current` fails without both flags. Callers get updated in Task 12.
4. **Age threshold default 180 days**, in `settings.reporting.ageThresholdDays`. A quarterly-reviewed programme should notice a rating that has survived two review cycles untouched.
5. **`confirmedAt` is NOT seeded from `lastReviewed` on normalization.** They are different claims — "a human looked" versus "a human decided this rating, from this source". Seeding would fabricate an attribution date. Consequence: age reporting is empty on every upgraded v1 profile until ratings are re-confirmed, and the renderers say so in words rather than showing an empty box.

## File structure

| File | Change | Responsibility |
|---|---|---|
| `skills/nist-csf/scripts/profile_analysis.py` | modify | Schema v2, normalization, `intake`, `queue`, attribution enforcement, derivation layer, `analyze` wiring, self-test |
| `skills/nist-csf/references/cold-start-rank.json` | **create** | CAC editorial cold-start ordering, 32 ranked ids + tail rule |
| `skills/nist-csf/scripts/csfa_compat.py` | modify | `convert` emits v2 and synthesises one intake record for the source assessment |
| `skills/nist-csf/renderers/_common.py` | modify | Evidence-state fills, `Context` accessors for the new analyze blocks |
| `skills/nist-csf/renderers/render_executive.py` | modify | Scope guard, four-way coverage, age readout, revisit count |
| `skills/nist-csf/renderers/render_operational.py` | modify | Same four, plus coverage-by-source |
| `skills/nist-csf/examples/example-profile-v2.csfp` | **create** | v2 fixture: intake, confirmations, revisit condition, ratings spanning >12 months |
| `skills/risk-register/evals/responsive.sh` | modify | Fix `set --current` calls; add a below-threshold CSF pair so the scope guard is measured |
| `skills/risk-register/evals/board-safety.sh` | modify | Fix `set --current` calls |
| `skills/nist-csf/references/schema.md` | modify | v2 store shape, intake, attribution, derived-not-stored additions |
| `skills/nist-csf/references/dashboards.md` | modify | The four new sections and the rules binding them |
| `skills/nist-csf/references/assessment-and-review.md` | modify | Intake and confirmation steps in workflows A and B |
| `skills/nist-csf/SKILL.md` | modify | Command surface, assertion count, evidence-accretion framing |
| `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json` (×2), `.codex-plugin/plugin.json` | modify | 0.1.8 → 0.2.0 |

**Increment 2 (conversational — `SKILL.md` intake proposal, batched elicitation, anti-drift rules, verified by eval) is planned separately once Increment 1 has landed.** It depends on the exact command surface this plan builds.

---

## Task 1: Schema v2 — constants, normalization, save stamp

**Files:**
- Modify: `skills/nist-csf/scripts/profile_analysis.py` (constants ~line 71; `load_store` 214–239; `save_store` 242–251)
- Test: `skills/nist-csf/scripts/profile_analysis.py::_cmd_self_test`

- [ ] **Step 1: Write the failing test**

> **Where every new assertion block goes.** All of them are appended to `_cmd_self_test` immediately before the `# --- Export contract ---` block near the end of the function, **in the order the tasks introduce them**: Task 1, Task 3, Task 4, Task 5, Task 6, Task 7, Task 11, then Task 2. Later blocks reuse names bound by earlier ones (`_p`, `fx_assess`, `ev`), so the order is load-bearing.
>
> Several of these blocks call `_cmd_init` and friends, which print. `self-test` output gets chattier as a result; the pass/fail summary is still the last line.

First add `import tempfile` to the module's import block (beside `import sys`), then add:

```python
    # --- Schema v2: normalization and attribution defaults ---
    v1 = {
        "schemaVersion": "1.0",
        "profile": {"id": "t", "name": "T", "frameworkRef": FRAMEWORK_REF,
                    "created": "2026-01-01T00:00:00Z", "updated": "2026-01-01T00:00:00Z"},
        "assessments": [{"subcategoryId": "ID.AM-01", "applicability": "in-scope",
                         "current": 2, "target": 3, "priority": "medium",
                         "status": "in-progress", "notes": "", "evidenceRefs": [],
                         "lastReviewed": "2026-01-01"}],
        "history": [], "snapshots": [], "actionItems": [],
    }
    with tempfile.TemporaryDirectory() as _d:
        _p = os.path.join(_d, "v1.csfp")
        with open(_p, "w", encoding="utf-8") as _fh:
            json.dump(v1, _fh)
        s = load_store(_p)
        eq(s["intake"], [], "v1 normalizes with an empty intake list")
        a0 = s["assessments"][0]
        eq(a0["confirmedAt"], None, "v1 rating normalizes with confirmedAt null")
        eq(a0["confirmedBy"], None, "v1 rating normalizes with confirmedBy null")
        eq(a0["source"], None, "v1 rating normalizes with source null")
        eq(a0["current"], 2, "v1 normalization does not touch the rating itself")
        eq(s["profile"]["settings"]["reporting"]["scopeThresholdPct"], 60,
           "reporting defaults are seeded on normalization")
        eq(s["profile"]["settings"]["reporting"]["ageThresholdDays"], 180,
           "age threshold default is 180 days")
        save_store(s, _p, "2026-07-27T00:00:00Z")
        with open(_p, encoding="utf-8") as _fh:
            back = json.load(_fh)
        eq(back["schemaVersion"], "2.0", "first write stamps schemaVersion 2.0")
        eq(load_store(_p)["assessments"][0]["current"], 2, "a v2 file round-trips")
    ok("2.0" in SUPPORTED_SCHEMA and "1.0" in SUPPORTED_SCHEMA,
       "both schema versions load")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 skills/nist-csf/scripts/profile_analysis.py self-test`
Expected: FAIL — `NameError: name 'SUPPORTED_SCHEMA' is not defined`

- [ ] **Step 3: Write the implementation**

Replace line 71 (`SCHEMA_VERSION = "1.0"`) with:

```python
SCHEMA_VERSION = "2.0"          # current write version
SUPPORTED_SCHEMA = {"1.0", "2.0"}   # v1 files load and normalize to v2 shape in memory
```

Add to `DEFAULT_SETTINGS` (find the dict and add this key alongside `scale`, `priorityWeights`, `functionWeights`):

```python
    # Reporting thresholds. Both are user-set with a shipped default; neither
    # changes a score, only whether a number is presented and what is flagged.
    "reporting": {
        # Below this share of in-scope Subcategories assessed, the headline
        # programme figure is SUPPRESSED, not caveated. A number with a warning
        # beside it is still a number, and people read the number.
        "scopeThresholdPct": 60,
        # A rating older than this is counted and reported. Ratings never expire:
        # age is reported and the human judges. See references/schema.md.
        "ageThresholdDays": 180,
    },
```

In `load_store`, replace the version check at lines 222–226 with:

```python
    if store.get("schemaVersion") not in SUPPORTED_SCHEMA:
        raise ValueError(
            f"Unsupported schemaVersion {store.get('schemaVersion')!r} "
            f"(supported: {', '.join(sorted(SUPPORTED_SCHEMA))})."
        )
```

Then, after the existing `prof["settings"] = {**copy.deepcopy(DEFAULT_SETTINGS), **prof.get("settings", {})}` line, add:

```python
    # Nested settings survive the shallow merge above: a v1 file has no
    # `reporting` key at all, and a v2 file may carry only one of the two.
    prof["settings"]["reporting"] = {
        **copy.deepcopy(DEFAULT_SETTINGS["reporting"]),
        **(prof["settings"].get("reporting") or {}),
    }

    # v1 -> v2 normalization, in memory. No data loss; the write path stamps 2.0.
    #
    # confirmedAt is deliberately NOT seeded from lastReviewed. "A human looked at
    # this outcome" and "a human decided this rating, from this source, on this
    # date" are different claims, and inventing the second from the first would
    # fabricate exactly the attribution this schema exists to make honest.
    store.setdefault("intake", [])
    for a in store["assessments"]:
        a.setdefault("confirmedAt", None)
        a.setdefault("confirmedBy", None)
        a.setdefault("source", None)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 skills/nist-csf/scripts/profile_analysis.py self-test`
Expected: `self-test: 89/89 checks passed`

- [ ] **Step 5: Verify the shipped fixture and the Acme parity path still load**

Run:
```bash
python3 skills/nist-csf/scripts/profile_analysis.py analyze skills/nist-csf/examples/example-profile.csfp --today 2026-07-27 | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d["coverage"]["overall"])'
python3 skills/nist-csf/scripts/csfa_compat.py self-test
```
Expected: `{'percent': 62.5, 'n': 15, 'd': 24}` (or whatever the pre-change value is — it must be **unchanged**), then `csfa-compat self-test: 28/28 checks passed`

- [ ] **Step 6: Commit**

```bash
git add skills/nist-csf/scripts/profile_analysis.py
git commit -m "feat(nist-csf): schema v2 — attribution fields and intake, normalized from v1 on load"
```

---

## Task 2: Attribution enforcement on `set --current`

**Files:**
- Modify: `skills/nist-csf/scripts/profile_analysis.py` (`_cmd_set` 773–867; module docstring ~line 32)
- Test: `skills/nist-csf/scripts/profile_analysis.py::_cmd_self_test`

- [ ] **Step 1: Write the failing test**

Add to `_cmd_self_test`, **after the Task 3 block** (it needs an intake record to point at):

```python
    # --- Attribution enforcement on a Current rating ---
    # This asserts FAILURE. A test that only exercises the happy path would pass
    # against an engine that enforces nothing.
    with tempfile.TemporaryDirectory() as _d:
        _p = os.path.join(_d, "a.csfp")
        _cmd_init(["--name", "Attr Co", "--out", _p, "--owner", "CISO",
                   "--ts", "2026-01-01T00:00:00Z"])
        _cmd_intake(["add", _p, "--label", "architecture review with infra team",
                     "--subjects", "ID.AM-01", "ID.AM-02",
                     "--source-date", "2026-03-14", "--recorded-by", "R. Calder",
                     "--ts", "2026-03-16T00:00:00Z"])
        for bad, why in (
            (["--current", "2", "--rationale", "x"], "no attribution at all"),
            (["--current", "2", "--rationale", "x", "--source", "in-0001"], "no --confirmed-by"),
            (["--current", "2", "--rationale", "x", "--confirmed-by", "R. Calder"], "no --source"),
        ):
            try:
                _cmd_set([_p, "ID.AM-01"] + bad + ["--ts", "2026-03-20T00:00:00Z"])
                failures.append(f"set --current with {why} should have been refused")
            except ValueError as exc:
                ok("--source" in str(exc) and "--confirmed-by" in str(exc),
                   f"refusal for {why} names both flags")
            checks += 1
        try:
            _cmd_set([_p, "ID.AM-01", "--current", "2", "--rationale", "x",
                      "--source", "in-9999", "--confirmed-by", "R. Calder",
                      "--ts", "2026-03-20T00:00:00Z"])
            failures.append("set --source with an unknown intake id should have been refused")
        except ValueError as exc:
            ok("in-9999" in str(exc), "unknown --source names the id")
        checks += 1

        # Target is NOT gated: it is a risk-based decision, already covered by --rationale.
        _cmd_set([_p, "ID.AM-01", "--target", "3", "--rationale", "risk-based target",
                  "--ts", "2026-03-20T00:00:00Z"])
        eq(load_store(_p)["assessments"][0]["target"], 3, "target writes without attribution")

        _cmd_set([_p, "ID.AM-01", "--current", "2", "--rationale", "confirmed at review",
                  "--source", "in-0001", "--confirmed-by", "R. Calder",
                  "--ts", "2026-03-20T00:00:00Z"])
        st = load_store(_p)
        a = [x for x in st["assessments"] if x["subcategoryId"] == "ID.AM-01"][0]
        eq(a["current"], 2, "attributed current rating is written")
        eq(a["source"], "in-0001", "source is recorded on the assessment")
        eq(a["confirmedBy"], "R. Calder", "confirmedBy is recorded on the assessment")
        eq(a["confirmedAt"], "2026-03-20", "confirmedAt is the date of the decision")
        eq(a["lastReviewed"], "2026-03-20", "a Current move still refreshes lastReviewed")
        ev = [e for e in st["history"] if e.get("type") == "rating-changed"][-1]
        eq(ev.get("source"), "in-0001", "the history event carries the source")
        eq(ev.get("confirmedBy"), "R. Calder", "the history event carries the confirmer")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 skills/nist-csf/scripts/profile_analysis.py self-test`
Expected: FAIL — `set --current with no attribution at all should have been refused`, three times over.

> **Execution note:** Tasks 2 and 3 are mutually referential — the enforcement test needs an intake record to point at, so `_cmd_intake` (Task 3) must already exist when this test runs. Implement Task 3 in full first, then return here. The commits stay separate.

- [ ] **Step 3: Write the implementation**

In `_cmd_set`, change the usage string (line 775–777) to:

```python
    usage = ("usage: set <store.csfp> <subcategoryId> [--current N|null] [--target N|null] "
             "[--priority P] [--status S] [--applicability A] [--notes ...] [--evidence A B] "
             "[--reviewed] [--rationale '...'] [--source in-0001] [--confirmed-by NAME]")
```

After the `rationale = ...` assignment (line 787), add:

```python
    source = _s(opt.get("source")) if isinstance(opt.get("source"), (str, list)) else None
    confirmed_by = (_s(opt.get("confirmed-by"))
                    if isinstance(opt.get("confirmed-by"), (str, list)) else None)
```

Immediately after the existing material-change refusal block (which ends at line 833), insert:

```python
    # Attribution: a Current rating is the claim the whole report rests on, so it
    # does not exist without a named source and a named person. The CLI cannot
    # prove a human typed the number — what it enforces is that no rating exists
    # that nobody will claim. The human-confirmation discipline itself is a
    # behavioural rule in SKILL.md, not a mechanical one.
    #
    # Target is deliberately NOT gated here: it is a risk-based decision, already
    # covered by --rationale, and gating it would break quickstart-target's seed.
    setting_current = any(f == "current" and n is not None for f, n in updates)
    if setting_current and a.get("current") != next(n for f, n in updates if f == "current"):
        if not source or not confirmed_by:
            raise ValueError(
                "--source and --confirmed-by are required for a Current rating. "
                "A rating nobody will claim is a rating nobody can defend. "
                "Record where it came from first: "
                "intake add <store> --label '...' --subjects " + sid
            )
        known = {r.get("id") for r in store.get("intake", [])}
        if source not in known:
            raise ValueError(
                f"--source {source!r} is not an intake record in this Profile. "
                f"Known: {', '.join(sorted(known)) or '(none)'}. "
                f"List them with: intake list <store.csfp>"
            )
```

In the apply loop (lines 836–849), extend the `current` branch:

```python
        if field == "current":
            a["lastReviewed"] = ts[:10]
            # Attribution travels with the rating, not beside it: the answer to
            # "how do you know?" must be readable from the assessment alone.
            a["confirmedAt"] = ts[:10]
            a["confirmedBy"] = confirmed_by
            a["source"] = source
```

Change the `append_history` call inside that loop (lines 843–844) to pass attribution through:

```python
        append_history(store, etype, subcategoryId=sid, field=field, frm=old, to=new,
                       rationale=rationale, actor=actor, ts=ts,
                       source=source if field == "current" else None,
                       confirmedBy=confirmed_by if field == "current" else None)
```

Extend `append_history` (line 308) to accept and record them:

```python
def append_history(store, etype, *, subcategoryId=None, field=None, frm=None, to=None,
                   rationale=None, actor=None, ts=None, actionId=None, intakeId=None,
                   source=None, confirmedBy=None):
    ev = {"ts": ts, "actor": actor or store["profile"]["scope"].get("owner") or "unknown", "type": etype}
    if subcategoryId is not None:
        ev["subcategoryId"] = subcategoryId
    if actionId is not None:
        ev["actionId"] = actionId
    if intakeId is not None:
        ev["intakeId"] = intakeId
    if field is not None:
        ev["field"] = field
        ev["from"] = frm
        ev["to"] = to
    if source:
        ev["source"] = source
    if confirmedBy:
        ev["confirmedBy"] = confirmedBy
    if rationale:
        ev["rationale"] = rationale
    store["history"].append(ev)
    return ev
```

Update the `set` line in the module docstring (line 32–34) to:

```
  set               <store.csfp> <subcategoryId> [--current N|null] [--target N|null]
                    [--priority P] [--status S] [--applicability A] [--notes ...]
                    [--evidence A B] [--reviewed] [--rationale ...] [--actor A] [--ts TS]
                    [--source in-0001] [--confirmed-by NAME]   (both REQUIRED with --current)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 skills/nist-csf/scripts/profile_analysis.py self-test`
Expected: `self-test: 105/105 checks passed`

- [ ] **Step 5: Verify the refusal by hand**

Run:
```bash
python3 skills/nist-csf/scripts/profile_analysis.py init --name Demo --out /tmp/d.csfp --owner CISO
python3 skills/nist-csf/scripts/profile_analysis.py set /tmp/d.csfp ID.AM-01 --current 1 --rationale x
```
Expected: exit 1, `error: --source and --confirmed-by are required for a Current rating. ...`

- [ ] **Step 6: Commit**

```bash
git add skills/nist-csf/scripts/profile_analysis.py
git commit -m "feat(nist-csf): a Current rating now requires a named source and a named confirmer"
```

---

## Task 3: `intake add` and `intake list`

**Files:**
- Modify: `skills/nist-csf/scripts/profile_analysis.py` (new commands near `_cmd_action`; `COMMANDS` dict ~1484; module docstring)
- Test: `skills/nist-csf/scripts/profile_analysis.py::_cmd_self_test`

- [ ] **Step 1: Write the failing test**

Add to `_cmd_self_test`, after the Task 1 block:

```python
    # --- Intake: the source is the unit of record ---
    with tempfile.TemporaryDirectory() as _d:
        _p = os.path.join(_d, "i.csfp")
        _cmd_init(["--name", "Intake Co", "--out", _p, "--owner", "CISO",
                   "--ts", "2026-01-01T00:00:00Z"])
        _cmd_intake(["add", _p, "--label", "architecture review with infra team",
                     "--subjects", "ID.AM-01", "ID.AM-02", "ID.AM-03",
                     "--source-date", "2026-03-14", "--recorded-by", "R. Calder",
                     "--ts", "2026-03-16T09:00:00Z"])
        st = load_store(_p)
        eq(len(st["intake"]), 1, "one intake record written")
        r = st["intake"][0]
        eq(r["id"], "in-0001", "intake ids are in-NNNN, zero padded")
        eq(r["label"], "architecture review with infra team", "label is stored verbatim")
        eq(r["subjects"], ["ID.AM-01", "ID.AM-02", "ID.AM-03"], "subjects are stored in order")
        eq(r["sourceDate"], "2026-03-14", "sourceDate is when the conversation happened")
        eq(r["recordedAt"], "2026-03-16", "recordedAt is when it entered the store")
        eq(r["recordedBy"], "R. Calder", "recordedBy is recorded")
        eq([a for a in st["assessments"] if a["subcategoryId"] == "ID.AM-01"][0]["current"], None,
           "intake writes no ratings")
        ev = [e for e in st["history"] if e.get("type") == "intake-recorded"]
        eq(len(ev), 1, "intake appends exactly one history event")
        eq(ev[0].get("intakeId"), "in-0001", "the history event names the intake id")

        # sourceDate defaults to the recording date, so the fast path stays fast.
        _cmd_intake(["add", _p, "--label", "hallway note on backups",
                     "--subjects", "PR.DS-11", "--ts", "2026-04-02T00:00:00Z"])
        r2 = load_store(_p)["intake"][1]
        eq(r2["id"], "in-0002", "intake ids increment")
        eq(r2["sourceDate"], "2026-04-02", "sourceDate defaults to the recording date")

        for bad, why in (
            (["add", _p, "--subjects", "ID.AM-01"], "no --label"),
            (["add", _p, "--label", "x"], "no --subjects"),
            (["add", _p, "--label", "x", "--subjects", "ZZ.ZZ-99"], "unknown Subcategory"),
            (["add", _p, "--label", "x", "--subjects", "ID.AM-01",
              "--source-date", "14/03/2026"], "non-ISO sourceDate"),
        ):
            try:
                _cmd_intake(bad)
                failures.append(f"intake add with {why} should have been refused")
            except ValueError:
                pass
            checks += 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 skills/nist-csf/scripts/profile_analysis.py self-test`
Expected: FAIL — `NameError: name '_cmd_intake' is not defined`

- [ ] **Step 3: Write the implementation**

Add above `_cmd_action` (line 1080):

```python
def _next_intake_id(store) -> str:
    used = [int(m.group(1)) for r in store.get("intake", [])
            if (m := re.match(r"in-(\d+)$", str(r.get("id", ""))))]
    return f"in-{max(used, default=0) + 1:04d}"


def _iso_date(raw, label: str) -> str:
    """Validate an ISO date. A silently-accepted '14/03/2026' would sort wrong and
    make every age and revisit computation quietly false."""
    text = str(_s(raw)).strip()
    try:
        datetime.strptime(text, "%Y-%m-%d")
    except ValueError:
        raise ValueError(f"{label} must be an ISO date (YYYY-MM-DD), got {text!r}") from None
    return text


def _cmd_intake(args):
    """Record that a source bears on some Subcategories. Writes no ratings, ever.

    The unit of record is the SOURCE, not the Subcategory. One conversation
    typically bears on many outcomes, and "what did the March architecture review
    cover?" is the question a CISO actually asks when rebuilding a picture — which
    a per-Subcategory pointer list cannot answer.

    This must cost under thirty seconds or it will not happen mid-conversation.
    No rating is discussed at this step and none can be written from here.
    """
    pos, opt = parse_flags(args)
    usage = ("usage: intake add <store.csfp> --label '...' --subjects ID.AM-01 ID.AM-02 "
             "[--source-date YYYY-MM-DD] [--recorded-by NAME] [--ts TS]\n"
             "       intake list <store.csfp> [--json]")
    if len(pos) < 2:
        raise ValueError(usage)
    sub, path = pos[0], pos[1]
    core = load_core(); index = index_subcategories(core)
    store = load_store(path)
    ts = _s(opt.get("ts")) if isinstance(opt.get("ts"), (str, list)) else _now()

    if sub == "add":
        label = _s(opt.get("label")) if isinstance(opt.get("label"), (str, list)) else ""
        if not str(label).strip():
            raise ValueError("--label is required. It is a note about the source — human-authored "
                             "or human-confirmed, never model-generated, and never a quoted "
                             "excerpt. That is what keeps internal material out of this file.\n\n"
                             + usage)
        subjects = _list(opt.get("subjects"))
        if not subjects:
            raise ValueError("--subjects is required: at least one Subcategory this source bears "
                             "on.\n\n" + usage)
        unknown = [s for s in subjects if s not in index]
        if unknown:
            raise ValueError(f"Unknown Subcategory {', '.join(unknown)} for framework {FRAMEWORK_REF}.")

        recorded_at = ts[:10]
        source_date = (_iso_date(opt["source-date"], "--source-date")
                       if isinstance(opt.get("source-date"), (str, list)) else recorded_at)
        recorded_by = (_s(opt.get("recorded-by"))
                       if isinstance(opt.get("recorded-by"), (str, list))
                       else (store["profile"]["scope"].get("owner") or ""))

        rec = {
            "id": _next_intake_id(store),
            "label": str(label).strip(),
            # These diverge routinely under accretion — a March conversation
            # recorded in July — and conflating them would misreport age.
            "sourceDate": source_date,
            "recordedAt": recorded_at,
            "subjects": list(subjects),
            "recordedBy": recorded_by,
        }
        store.setdefault("intake", []).append(rec)
        append_history(store, "intake-recorded", intakeId=rec["id"], ts=ts,
                       actor=_s(opt.get("actor")) if isinstance(opt.get("actor"), (str, list)) else None,
                       rationale=f"Source recorded: {rec['label']} ({rec['sourceDate']}), "
                                 f"bearing on {len(rec['subjects'])} Subcategories.")
        save_store(store, path, ts)
        print(f"Recorded {rec['id']}: {rec['label']}")
        print(f"  {rec['sourceDate']} · bears on {', '.join(rec['subjects'])}")
        print(f"  No ratings written. Confirm them when you have time to decide: "
              f"queue {path}")
        return 0

    if sub == "list":
        records = store.get("intake", [])
        if opt.get("json"):
            sys.stdout.write(json.dumps(records, indent=2, ensure_ascii=False) + "\n")
            return 0
        if not records:
            print("No intake recorded yet.")
            print("  intake add <store.csfp> --label '...' --subjects ID.AM-01 ID.AM-02")
            return 0
        rated = {a["subcategoryId"] for a in store["assessments"] if a.get("current") is not None}
        for r in records:
            done = sum(1 for s in r["subjects"] if s in rated)
            print(f"{r['id']}  {r['sourceDate']}  {r['label']}")
            print(f"          {len(r['subjects'])} Subcategories · {done} confirmed · "
                  f"{', '.join(r['subjects'])}")
        return 0

    raise ValueError(usage)
```

Register it in `COMMANDS` (line 1484):

```python
COMMANDS = {
    "validate": _cmd_validate, "self-test": _cmd_self_test,
    "init": _cmd_init, "set": _cmd_set, "set-tier": _cmd_set_tier,
    "quickstart-target": _cmd_quickstart_target,
    "snapshot": _cmd_snapshot, "diff": _cmd_diff, "action": _cmd_action,
    "intake": _cmd_intake, "queue": _cmd_queue,
    "analyze": _cmd_analyze, "export-gaps": _cmd_export_gaps,
}
```

> `_cmd_queue` lands in Task 6. Until then, leave `"queue": _cmd_queue` **out** of the dict and add it in Task 6 — a `NameError` at import time breaks every command.

Add to the module docstring's mutation list, after the `action close` line:

```
  intake add        <store.csfp> --label '...' --subjects ID.AM-01 ID.AM-02
                    [--source-date D] [--recorded-by NAME] [--ts TS]
  intake list       <store.csfp> [--json]
```

Also add `"intake": []` to the store literal in `_cmd_init` (line 761):

```python
        "assessments": assessments, "history": [], "snapshots": [], "actionItems": [],
        "intake": [],
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 skills/nist-csf/scripts/profile_analysis.py self-test`
Expected: `self-test: 105/105 checks passed`

- [ ] **Step 5: Verify the 30-second path by hand**

Run:
```bash
python3 skills/nist-csf/scripts/profile_analysis.py init --name Demo --out /tmp/d.csfp --owner CISO
python3 skills/nist-csf/scripts/profile_analysis.py intake add /tmp/d.csfp \
  --label "architecture review with infra team" --subjects ID.AM-01 ID.AM-02 ID.AM-03 \
  --source-date 2026-03-14 --recorded-by the maintainer
python3 skills/nist-csf/scripts/profile_analysis.py intake list /tmp/d.csfp
```
Expected: `Recorded in-0001: architecture review with infra team`, then a list line showing `3 Subcategories · 0 confirmed`

- [ ] **Step 6: Commit**

```bash
git add skills/nist-csf/scripts/profile_analysis.py
git commit -m "feat(nist-csf): intake add/list — record a source in seconds, rate nothing"
```

---

## Task 4: Cold-start rank reference file and resolver

**Files:**
- Create: `skills/nist-csf/references/cold-start-rank.json`
- Modify: `skills/nist-csf/scripts/profile_analysis.py` (loader + resolver, near `load_guidance` line 436)
- Test: `skills/nist-csf/scripts/profile_analysis.py::_cmd_self_test`

- [ ] **Step 1: Write the failing test**

Add to `_cmd_self_test`, after the intake block:

```python
    # --- Cold-start rank ---
    rank_data = load_cold_start_rank()
    ok(bool(rank_data.get("rank")), "cold-start rank file loads")
    ok(bool(rank_data.get("basis")) and bool(rank_data.get("disclaimer")),
       "cold-start rank states its basis and carries a disclaimer")
    unknown_ranked = [sid for sid in rank_data["rank"] if sid not in index]
    eq(unknown_ranked, [], "every ranked id exists in the framework")
    ranks = sorted(rank_data["rank"].values())
    eq(ranks, list(range(1, len(ranks) + 1)), "ranks are a dense 1..N sequence with no ties")
    order = resolve_rank(index, core, rank_data)
    eq(len(order), len(index), "every Subcategory gets a position")
    eq(order["ID.AM-01"], 1, "ID.AM-01 leads the cold start")
    ok(order["GV.RR-02"] > order["ID.AM-01"], "ranked ids sort by their rank")
    tail = [sid for sid in index if sid not in rank_data["rank"]]
    ok(min(order[s] for s in tail) > max(rank_data["rank"].values()),
       "unranked ids sort after every ranked id")
    ok(order["GV.OC-03"] < order["ID.RA-02"],
       "unranked ids fall back to framework order, GV before ID")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 skills/nist-csf/scripts/profile_analysis.py self-test`
Expected: FAIL — `NameError: name 'load_cold_start_rank' is not defined`

- [ ] **Step 3: Create the reference file**

Create `skills/nist-csf/references/cold-start-rank.json`:

```json
{
  "id": "cac-cold-start-rank-1",
  "basis": "Cyber Aware Creations editorial judgment. NIST publishes no Subcategory prioritization; any ordering is editorial and this one is ours, not NIST's.",
  "disclaimer": "This ordering is a Cyber Aware Creations opinion about where a programme with nothing recorded should start asking. It is not a NIST prioritization, not a maturity path, and not a compliance sequence. It carries the same caveat as the 0-4 tool scale: a practical convention, not doctrine.",
  "informedBy": [
    "CISA Cross-Sector Cybersecurity Performance Goals — a US federal, public-domain, explicitly prioritized subset published with a CSF mapping",
    "NIST CSF 2.0 Quick Start Guides, particularly the small-business guide (NIST SP 1300)"
  ],
  "informedByNote": "Read to inform judgment, not redistributed. No mapping table from any source is copied into this file.",
  "tailRule": "Subcategories absent from `rank` sort after every ranked id, in framework order: Function order as the Core defines it, then Category order, then Subcategory id.",
  "rank": {
    "ID.AM-01": 1,
    "ID.AM-02": 2,
    "ID.AM-03": 3,
    "PR.AA-01": 4,
    "PR.AA-03": 5,
    "PR.AA-05": 6,
    "PR.PS-02": 7,
    "PR.PS-01": 8,
    "PR.DS-11": 9,
    "RC.RP-01": 10,
    "RS.MA-01": 11,
    "DE.CM-01": 12,
    "DE.CM-09": 13,
    "DE.AE-02": 14,
    "GV.RR-02": 15,
    "GV.OC-02": 16,
    "GV.RM-01": 17,
    "ID.RA-01": 18,
    "ID.RA-05": 19,
    "PR.AT-01": 20,
    "GV.PO-01": 21,
    "GV.SC-04": 22,
    "GV.SC-07": 23,
    "PR.DS-01": 24,
    "PR.DS-02": 25,
    "RS.CO-02": 26,
    "RS.MI-01": 27,
    "DE.AE-06": 28,
    "ID.AM-05": 29,
    "PR.AA-06": 30,
    "GV.OV-01": 31,
    "ID.IM-01": 32
  },
  "rationale": {
    "1-3": "You cannot rate access, monitoring, or recovery for assets you cannot enumerate. Asset, software, and data-flow inventory resolve the most downstream uncertainty per question asked, and they batch into one conversation.",
    "4-9": "The controls that most often decide whether an incident is an event or a crisis: who can get in, is software patched, is the build known, and can you restore.",
    "10-14": "Can you detect it and can you respond. A programme that cannot see or recover has no floor under any other rating.",
    "15-23": "Governance and supplier context. Placed after the operational floor deliberately: a CISO with nothing recorded gets more from knowing what they run than from restating who is accountable, and governance questions are easier to answer once the operational picture exists.",
    "24-32": "Data protection specifics, response communication, and the improvement loop. Real, but they refine a picture rather than establish one."
  }
}
```

- [ ] **Step 4: Write the loader and resolver**

Add beside `DEFAULT_GUIDANCE` (near line 100, wherever `DEFAULT_GUIDANCE` is defined):

```python
DEFAULT_COLD_START_RANK = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                       "..", "references", "cold-start-rank.json")
```

Add after `load_guidance` (line 442):

```python
def load_cold_start_rank(path: str | None = None) -> dict:
    """Load the CAC cold-start ordering. Absent is fine — the queue falls back to
    framework order, which is still deterministic."""
    try:
        with open(path or DEFAULT_COLD_START_RANK, encoding="utf-8") as fh:
            return json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"rank": {}, "basis": "", "disclaimer": ""}


def resolve_rank(index: dict, core: dict, rank_data: dict) -> dict:
    """Map every Subcategory to a total-order position, ranked ids first.

    Used only when NO intake exists for a Subcategory. The queue mechanism is
    indifferent to what fills the table; this is where the editorial judgment
    lives, and it is labelled as CAC's in the reference file itself.
    """
    ranked = rank_data.get("rank") or {}
    out = {sid: ranked[sid] for sid in index if sid in ranked}
    n = len(out)
    # Framework order for the tail: Function order as the Core defines it, then
    # Category, then id. Never hardcode the six CSF Function names.
    pos = 0
    for f in core["hierarchy"]:
        for cat in f.get("categories", []):
            for s in cat.get("subcategories", []):
                if s["id"] in index and s["id"] not in ranked:
                    pos += 1
                    out[s["id"]] = n + pos
    return out
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python3 skills/nist-csf/scripts/profile_analysis.py self-test`
Expected: `self-test: 113/113 checks passed`

- [ ] **Step 6: Commit**

```bash
git add skills/nist-csf/references/cold-start-rank.json skills/nist-csf/scripts/profile_analysis.py
git commit -m "feat(nist-csf): cold-start rank — CAC editorial ordering, labelled as ours not NIST's"
```

---

## Task 5: Derivation layer — evidence states, four-way coverage, age, scope guard

**Files:**
- Modify: `skills/nist-csf/scripts/profile_analysis.py` (pure computation section, after `compute_completeness` line 431)
- Test: `skills/nist-csf/scripts/profile_analysis.py::_cmd_self_test`

- [ ] **Step 1: Write the failing test**

Add to `_cmd_self_test`, after the cold-start block:

```python
    # --- Derivation layer: derived, never stored ---
    fx_assess = [
        {"subcategoryId": "ID.AM-01", "applicability": "in-scope", "current": 2, "target": 3,
         "confirmedAt": "2026-03-20", "confirmedBy": "R. Calder", "source": "in-0001"},
        {"subcategoryId": "ID.AM-02", "applicability": "in-scope", "current": 1, "target": 3,
         "confirmedAt": "2025-06-01", "confirmedBy": "R. Calder", "source": "in-0001"},
        {"subcategoryId": "ID.AM-03", "applicability": "in-scope", "current": None, "target": 3,
         "confirmedAt": None, "confirmedBy": None, "source": None},
        {"subcategoryId": "PR.AA-01", "applicability": "in-scope", "current": None, "target": 3,
         "confirmedAt": None, "confirmedBy": None, "source": None},
        {"subcategoryId": "PR.AA-03", "applicability": "not-applicable", "current": None,
         "target": None, "confirmedAt": None, "confirmedBy": None, "source": None},
        {"subcategoryId": "PR.DS-11", "applicability": "in-scope", "current": 3, "target": 3,
         "confirmedAt": "2026-01-10", "confirmedBy": "R. Calder", "source": "in-0002"},
    ]
    fx_intake = [
        {"id": "in-0001", "label": "architecture review", "sourceDate": "2026-03-14",
         "recordedAt": "2026-03-16", "subjects": ["ID.AM-01", "ID.AM-02", "ID.AM-03"],
         "recordedBy": "R. Calder"},
        {"id": "in-0002", "label": "backup restore test", "sourceDate": "2026-01-08",
         "recordedAt": "2026-01-09", "subjects": ["PR.DS-11"], "recordedBy": "R. Calder"},
        {"id": "in-0003", "label": "vendor DR conversation", "sourceDate": "2026-06-02",
         "recordedAt": "2026-06-03", "subjects": ["PR.DS-11"], "recordedBy": "R. Calder"},
    ]
    ev = derive_evidence(fx_assess, fx_intake, index, core, today="2026-07-27",
                         threshold_pct=60, age_days=180)

    st = ev["states"]
    eq(st["ID.AM-01"], "confirmed", "rated with material is confirmed")
    eq(st["ID.AM-03"], "evidence-pending", "unrated with material is evidence-pending")
    eq(st["PR.AA-01"], "unrated", "unrated with no material is unrated")
    eq(st["PR.AA-03"], "not-applicable", "scoped out is its own state")

    cov = ev["coverage"]["overall"]
    eq(cov["confirmed"], 3, "four-way: confirmed count")
    eq(cov["evidencePending"], 1, "four-way: evidence-pending count")
    eq(cov["unrated"], 1, "four-way: unrated count")
    eq(cov["notApplicable"], 1, "four-way: not-applicable count")
    eq(cov["confirmed"] + cov["evidencePending"] + cov["unrated"] + cov["notApplicable"],
       len(fx_assess), "the four buckets partition every tracked Subcategory")
    eq(cov["attributed"], 3, "attributed = confirmed with source and confirmer")
    eq(cov["unattributed"], 0, "unattributed = confirmed without both")

    eq([r["subcategoryId"] for r in ev["revisit"]], ["PR.DS-11"],
       "revisit: material newer than the confirmation")
    eq(ev["revisit"][0]["newestSourceDate"], "2026-06-02", "revisit names the newer source date")
    ok("ID.AM-01" not in {r["subcategoryId"] for r in ev["revisit"]},
       "material older than the confirmation is not a revisit")

    age = ev["age"]["overall"]
    eq(age["dated"], 3, "age counts only dated confirmations")
    eq(age["oldestDays"], 421, "oldest: 2025-06-01 to 2026-07-27")
    eq(age["medianDays"], 198, "median of 129, 198, 421")
    eq(age["olderThanThreshold"], 2, "two ratings older than 180 days")
    eq(ev["age"]["thresholdDays"], 180, "the threshold is reported with the counts")

    g = ev["scopeGuard"]
    eq(g["assessed"], 3, "scope guard numerator is assessed in-scope")
    eq(g["inScope"], 5, "scope guard denominator excludes not-applicable")
    eq(g["thresholdPct"], 60, "scope guard reports its threshold")
    eq(g["assessedPct"], 60.0, "3 of 5 in-scope assessed is exactly 60%")
    # The boundary is inclusive: AT the threshold the figure is reported.
    ok(not g["suppressed"], "exactly at the threshold, the headline is NOT suppressed")
    ok("60%" in g["statement"] and "3 of 5" in g["statement"],
       "the scope statement carries both the fraction and the threshold")
    ev70 = derive_evidence(fx_assess, fx_intake, index, core, today="2026-07-27",
                           threshold_pct=70, age_days=180)
    ok(ev70["scopeGuard"]["suppressed"], "one point below the threshold suppresses the headline")
    ok("No headline coverage figure is reported" in ev70["scopeGuard"]["statement"],
       "the suppressed statement replaces the number rather than caveating it")

    ok(all("state" not in a and "age" not in a for a in fx_assess),
       "derivation mutates nothing on the assessments it reads")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 skills/nist-csf/scripts/profile_analysis.py self-test`
Expected: FAIL — `NameError: name 'derive_evidence' is not defined`

- [ ] **Step 3: Write the implementation**

Insert after `compute_completeness` (line 431):

```python
# --- Evidence accretion: derived, never stored ---------------------------------
#
# Every state below is computed from `assessments` + `intake` on demand. None of it
# is written back. `derived-not-stored` in references/schema.md is the contract;
# a stored `evidence-pending` flag would go stale the moment a rating moved.

def _median_int(nums: list[int]) -> int | None:
    if not nums:
        return None
    s = sorted(nums)
    mid = len(s) // 2
    return s[mid] if len(s) % 2 else (s[mid - 1] + s[mid]) // 2


def _days_between(start: str, end: str) -> int:
    a = datetime.strptime(start, "%Y-%m-%d")
    b = datetime.strptime(end, "%Y-%m-%d")
    return (b - a).days


def intake_by_subject(intake: list[dict]) -> dict:
    """Subcategory id -> the intake records bearing on it, oldest sourceDate first."""
    out: dict[str, list] = {}
    for r in intake or []:
        for sid in r.get("subjects", []):
            out.setdefault(sid, []).append(r)
    for sid in out:
        out[sid].sort(key=lambda r: (r.get("sourceDate") or "", r.get("id") or ""))
    return out


def derive_evidence(assessments: list[dict], intake: list[dict], index: dict, core: dict,
                    today: str, threshold_pct: int, age_days: int) -> dict:
    """The whole derivation layer, as one pure function. No IO, no clock.

    Four states partition every tracked Subcategory:
      not-applicable   scoped out
      confirmed        in-scope, has a Current rating
      evidence-pending in-scope, no Current rating, some intake bears on it
      unrated          in-scope, no Current rating, nothing bears on it

    `revisit` is a fifth, orthogonal flag: confirmed, and some intake bearing on it
    has a sourceDate later than its confirmedAt. It is a reporting flag and a queue
    input only — it does NOT affect scoring. Ratings never expire; new material is
    what questions a rating, not the passage of time.
    """
    by_subject = intake_by_subject(intake)
    states, revisit, pending = {}, [], []

    for a in assessments:
        sid = a["subcategoryId"]
        bearing = by_subject.get(sid, [])
        if a.get("applicability", "in-scope") != "in-scope":
            states[sid] = "not-applicable"
            continue
        if a.get("current") is not None:
            states[sid] = "confirmed"
            confirmed_at = a.get("confirmedAt")
            newer = [r for r in bearing
                     if confirmed_at and (r.get("sourceDate") or "") > confirmed_at]
            if newer:
                revisit.append({
                    "subcategoryId": sid,
                    "text": (index.get(sid) or {}).get("text", ""),
                    "confirmedAt": confirmed_at,
                    "newestSourceDate": max(r["sourceDate"] for r in newer),
                    "intakeIds": [r["id"] for r in newer],
                })
        elif bearing:
            states[sid] = "evidence-pending"
            pending.append({
                "subcategoryId": sid,
                "text": (index.get(sid) or {}).get("text", ""),
                "intakeIds": [r["id"] for r in bearing],
                "newestSourceDate": max(r.get("sourceDate") or "" for r in bearing),
            })
        else:
            states[sid] = "unrated"

    revisit.sort(key=lambda r: (r["newestSourceDate"], r["subcategoryId"]), reverse=True)
    pending.sort(key=lambda r: (r["newestSourceDate"], r["subcategoryId"]), reverse=True)

    def _split(subset: list[dict]) -> dict:
        out = {"confirmed": 0, "evidencePending": 0, "unrated": 0, "notApplicable": 0,
               "attributed": 0, "unattributed": 0, "total": len(subset)}
        key = {"confirmed": "confirmed", "evidence-pending": "evidencePending",
               "unrated": "unrated", "not-applicable": "notApplicable"}
        for a in subset:
            out[key[states[a["subcategoryId"]]]] += 1
            if states[a["subcategoryId"]] == "confirmed":
                full = a.get("confirmedAt") and a.get("confirmedBy") and a.get("source")
                out["attributed" if full else "unattributed"] += 1
        return out

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

    by_fn = _group(assessments, index, "functionId")
    fids = function_ids(core)

    scoped = in_scope(assessments)
    assessed = sum(1 for a in scoped if a.get("current") is not None)
    pct = (assessed / len(scoped) * 100) if scoped else 0.0
    suppressed = pct < threshold_pct
    statement = (
        f"No headline coverage figure is reported: {assessed} of {len(scoped)} in-scope "
        f"Subcategories have been assessed ({pct:.0f}%), below the {threshold_pct}% this "
        f"Profile requires. A programme mean drawn from a minority of Subcategories "
        f"describes the minority, not the programme."
        if suppressed else
        f"{assessed} of {len(scoped)} in-scope Subcategories assessed ({pct:.0f}%), "
        f"at or above the {threshold_pct}% this Profile requires for a headline figure."
    )

    return {
        "states": states,
        "coverage": {
            "overall": _split(assessments),
            "byFunction": {fid: _split(by_fn.get(fid, [])) for fid in fids},
        },
        "age": {
            "thresholdDays": age_days,
            "overall": _age(assessments),
            "byFunction": {fid: _age(by_fn.get(fid, [])) for fid in fids},
        },
        "revisit": revisit,
        "pending": pending,
        "scopeGuard": {
            "assessed": assessed, "inScope": len(scoped),
            "assessedPct": pct, "thresholdPct": threshold_pct,
            "suppressed": suppressed, "statement": statement,
        },
    }


def coverage_by_source(intake: list[dict], states: dict, index: dict) -> list[dict]:
    """Each intake record and what it bore on — the payoff of the source-keyed model.

    Answers "what did that review actually cover?", which a per-Subcategory pointer
    list structurally cannot.
    """
    rows = []
    for r in sorted(intake or [], key=lambda x: (x.get("sourceDate") or "", x.get("id") or ""),
                    reverse=True):
        subjects = [{"subcategoryId": sid,
                     "text": (index.get(sid) or {}).get("text", ""),
                     "state": states.get(sid, "unrated")}
                    for sid in r.get("subjects", [])]
        rows.append({
            "id": r.get("id"), "label": r.get("label"),
            "sourceDate": r.get("sourceDate"), "recordedAt": r.get("recordedAt"),
            "recordedBy": r.get("recordedBy"),
            "subjects": subjects,
            "confirmed": sum(1 for s in subjects if s["state"] == "confirmed"),
            "pending": sum(1 for s in subjects if s["state"] == "evidence-pending"),
        })
    return rows
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 skills/nist-csf/scripts/profile_analysis.py self-test`
Expected: `self-test: 139/139 checks passed`

- [ ] **Step 5: Commit**

```bash
git add skills/nist-csf/scripts/profile_analysis.py
git commit -m "feat(nist-csf): derive evidence states, four-way coverage, age and the scope guard"
```

---

## Task 6: The `queue` command

**Files:**
- Modify: `skills/nist-csf/scripts/profile_analysis.py` (new command after `_cmd_intake`; `COMMANDS`; module docstring)
- Test: `skills/nist-csf/scripts/profile_analysis.py::_cmd_self_test`

- [ ] **Step 1: Write the failing test**

Add to `_cmd_self_test`, after the derivation block (reusing `fx_assess`, `fx_intake`, `ev`):

```python
    # --- Queue order: evidence-pending -> revisit -> cold-start rank ---
    q = build_queue(fx_assess, fx_intake, ev, index, core,
                    resolve_rank(index, core, load_cold_start_rank()))
    eq([r["subcategoryId"] for r in q[:2]], ["ID.AM-03", "PR.DS-11"],
       "evidence-pending leads, then revisit")
    eq(q[0]["band"], "evidence-pending", "first band is evidence-pending")
    eq(q[1]["band"], "revisit", "second band is revisit")
    eq(q[2]["band"], "cold-start", "cold-start fills the tail")
    eq(q[2]["subcategoryId"], "PR.AA-01", "the only unrated in-scope id is next")
    ok("PR.AA-03" not in {r["subcategoryId"] for r in q},
       "not-applicable never enters the queue")
    ok("ID.AM-01" not in {r["subcategoryId"] for r in q},
       "a confirmed rating with no newer material is not queued")
    ok(all(r.get("tier") is None and "proposedTier" not in r for r in q),
       "the queue never carries a pre-filled rating")
    ok(q[0]["sources"] and q[0]["sources"][0]["label"] == "architecture review",
       "a queue item carries its source label and date, not a conclusion")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 skills/nist-csf/scripts/profile_analysis.py self-test`
Expected: FAIL — `NameError: name 'build_queue' is not defined`

- [ ] **Step 3: Write the implementation**

Add after `coverage_by_source` in the computation section:

```python
def build_queue(assessments: list[dict], intake: list[dict], evidence: dict,
                index: dict, core: dict, rank: dict, top: int | None = None) -> list[dict]:
    """What to confirm next, in three bands.

    Band order is fixed: evidence-pending, then revisit, then cold-start rank.
    Material you already have beats material you have to go find, and a rating a
    new conversation has called into question beats one nobody has looked at.

    A queue item carries the SOURCE and the DATE and nothing else. It must never
    carry a tier, a proposed tier, or a confidence — presenting a conclusion and
    asking for confirmation is how inference gets laundered as judgment, and a
    rubber-stamped rating is worse than an unrated one.
    """
    by_subject = intake_by_subject(intake)
    states = evidence["states"]
    by_id = {a["subcategoryId"]: a for a in assessments}

    def _sources(sid):
        return [{"id": r["id"], "label": r["label"], "sourceDate": r["sourceDate"],
                 "recordedBy": r.get("recordedBy", "")}
                for r in reversed(by_subject.get(sid, []))]

    def _row(sid, band, sort_key):
        return {
            "subcategoryId": sid,
            "text": (index.get(sid) or {}).get("text", ""),
            "functionId": (index.get(sid) or {}).get("functionId", ""),
            "band": band,
            "coldStartRank": rank.get(sid),
            "sources": _sources(sid),
            "confirmedAt": by_id[sid].get("confirmedAt"),
            "target": by_id[sid].get("target"),
            # Explicitly null. The confirmation session asks a question; it does
            # not present an answer for ratification.
            "tier": None,
            "_sort": sort_key,
        }

    pending = [_row(r["subcategoryId"], "evidence-pending",
                    (r["newestSourceDate"], -(rank.get(r["subcategoryId"]) or 0)))
               for r in evidence["pending"]]
    pending.sort(key=lambda r: (r["_sort"], r["subcategoryId"]), reverse=True)

    revisit = [_row(r["subcategoryId"], "revisit", (r["newestSourceDate"],))
               for r in evidence["revisit"]]
    revisit.sort(key=lambda r: (r["_sort"], r["subcategoryId"]), reverse=True)

    cold = [_row(sid, "cold-start", (rank.get(sid, 10 ** 6),))
            for sid, s in states.items() if s == "unrated"]
    cold.sort(key=lambda r: (r["_sort"], r["subcategoryId"]))

    rows = pending + revisit + cold
    for r in rows:
        r.pop("_sort")
    return rows if top is None else rows[:top]
```

Add the command after `_cmd_intake`:

```python
def _cmd_queue(args):
    pos, opt = parse_flags(args)
    path = _require_store(pos, "usage: queue <store.csfp> [--top N] [--today YYYY-MM-DD] [--json]")
    core = load_core(); index = index_subcategories(core)
    store = load_store(path)
    settings = store["profile"]["settings"]
    rep = settings["reporting"]
    today = _s(opt.get("today")) if isinstance(opt.get("today"), (str, list)) else _today()
    top = int(_s(opt.get("top"))) if isinstance(opt.get("top"), (str, list)) else 5

    ev = derive_evidence(store["assessments"], store.get("intake", []), index, core,
                         today, rep["scopeThresholdPct"], rep["ageThresholdDays"])
    rows = build_queue(store["assessments"], store.get("intake", []), ev, index, core,
                       resolve_rank(index, core, load_cold_start_rank()), top)

    if opt.get("json"):
        sys.stdout.write(json.dumps(rows, indent=2, ensure_ascii=False) + "\n")
        return 0

    if not rows:
        print("Queue is empty — every in-scope Subcategory is confirmed and nothing newer "
              "has arrived.")
        return 0

    # Batches of at most five by default. Long confirmation runs are where
    # rubber-stamping happens.
    print(f"Next {len(rows)} to confirm:\n")
    for r in rows:
        print(f"  {r['subcategoryId']}  [{r['band']}]")
        print(f"    {trunc_plain(r['text'], 110)}")
        for s in r["sources"]:
            print(f"    source {s['id']} · {s['sourceDate']} · {s['label']}")
        if r["band"] == "revisit":
            print(f"    confirmed {r['confirmedAt']}; newer material has arrived since")
        if not r["sources"]:
            print("    no material recorded — this is a cold start, go and ask")
        print()
    print("Confirm one with:")
    print(f"  set {path} <id> --current N --source in-NNNN --confirmed-by NAME "
          f"--rationale '...'")
    print("If the material is thin, the right outcome is a question to go ask — not a rating.")
    return 0
```

Add the plain-text truncator beside `_s`/`_list` (the renderers have their own; the engine needs one and must not import from `renderers/`):

```python
def trunc_plain(text: str, n: int) -> str:
    text = (text or "").strip()
    if len(text) <= n:
        return text
    cut = text[:n]
    space = cut.rfind(" ")
    return (cut[:space] if space > n * 0.6 else cut).rstrip() + "…"
```

Now add `"queue": _cmd_queue,` to `COMMANDS` (it was held back in Task 3). Add to the read-only section of the module docstring:

```
  queue        <store.csfp> [--top N] [--today D] [--json]   What to confirm next, ranked.
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 skills/nist-csf/scripts/profile_analysis.py self-test`
Expected: `self-test: 148/148 checks passed`

- [ ] **Step 5: Verify the cold-start path by hand**

Run:
```bash
python3 skills/nist-csf/scripts/profile_analysis.py init --name Cold --out /tmp/c.csfp --owner CISO
python3 skills/nist-csf/scripts/profile_analysis.py queue /tmp/c.csfp --top 3
```
Expected: three `[cold-start]` items, `ID.AM-01` first, each showing "no material recorded — this is a cold start, go and ask", and **no tier anywhere in the output**.

- [ ] **Step 6: Commit**

```bash
git add skills/nist-csf/scripts/profile_analysis.py
git commit -m "feat(nist-csf): queue — evidence-pending, then revisit, then cold-start rank"
```

---

## Task 7: Wire the derivations into `analyze`

**Files:**
- Modify: `skills/nist-csf/scripts/profile_analysis.py` (`_cmd_analyze` 1168–1238)
- Test: `skills/nist-csf/scripts/profile_analysis.py::_cmd_self_test`

- [ ] **Step 1: Write the failing test**

Add to `_cmd_self_test`, after the queue block:

```python
    # --- analyze carries every derived block, and the store carries none of them ---
    with tempfile.TemporaryDirectory() as _d:
        _p = os.path.join(_d, "an.csfp")
        _out = os.path.join(_d, "an.json")
        _cmd_init(["--name", "Analyze Co", "--out", _p, "--owner", "CISO",
                   "--ts", "2026-01-01T00:00:00Z"])
        _cmd_quickstart_target([_p, "--rationale", "baseline", "--ts", "2026-01-02T00:00:00Z"])
        _cmd_intake(["add", _p, "--label", "architecture review", "--subjects",
                     "ID.AM-01", "ID.AM-02", "--source-date", "2026-03-14",
                     "--ts", "2026-03-16T00:00:00Z"])
        _cmd_set([_p, "ID.AM-01", "--current", "2", "--rationale", "confirmed",
                  "--source", "in-0001", "--confirmed-by", "R. Calder",
                  "--ts", "2026-03-20T00:00:00Z"])
        _cmd_analyze([_p, "--today", "2026-07-27", "--out", _out])
        with open(_out, encoding="utf-8") as _fh:
            an = json.load(_fh)

        for key in ("evidence", "intake", "queue"):
            ok(key in an, f"analyze emits {key!r}")
        eq(an["evidence"]["coverage"]["overall"]["confirmed"], 1, "analyze counts confirmations")
        eq(an["evidence"]["coverage"]["overall"]["evidencePending"], 1,
           "analyze counts evidence-pending")
        ok(an["evidence"]["scopeGuard"]["suppressed"],
           "1 of 106 assessed suppresses the headline")
        eq(len(an["intake"]["records"]), 1, "analyze carries the intake records")
        eq(an["intake"]["bySource"][0]["confirmed"], 1, "coverage-by-source counts confirmations")
        eq(an["intake"]["bySource"][0]["pending"], 1, "coverage-by-source counts pending")
        eq(an["queue"][0]["subcategoryId"], "ID.AM-02", "the queue leads with the pending item")
        eq(an["generated"]["schemaVersion"], "2.0", "analyze stamps the schema version")

        raw = json.load(open(_p, encoding="utf-8"))
        ok("evidence" not in raw and "queue" not in raw,
           "no derived block is persisted to the store")
        ok(all("state" not in a for a in raw["assessments"]),
           "no derived state is persisted onto an assessment")

        # Coverage arithmetic is untouched by any of this.
        eq(an["coverage"]["overall"]["d"], 212, "quickstart target of 2 across 106 in-scope")
        eq(an["coverage"]["overall"]["n"], 2, "one Subcategory at Current 2")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 skills/nist-csf/scripts/profile_analysis.py self-test`
Expected: FAIL — `analyze emits 'evidence'`

- [ ] **Step 3: Write the implementation**

In `_cmd_analyze`, after `guidance = load_guidance()` (line 1186), add:

```python
    rep = settings["reporting"]
    evidence = derive_evidence(store["assessments"], store.get("intake", []), index, core,
                               today, rep["scopeThresholdPct"], rep["ageThresholdDays"])
    rank = resolve_rank(index, core, load_cold_start_rank())
```

Then add three keys to the `out` dict, immediately after `"completeness": ...` (line 1210):

```python
        # Derived on demand, never stored. The store holds intake and attribution;
        # everything below is computed from them at read time.
        "evidence": evidence,
        "intake": {
            "records": store.get("intake", []),
            "bySource": coverage_by_source(store.get("intake", []), evidence["states"], index),
        },
        "queue": build_queue(store["assessments"], store.get("intake", []), evidence,
                             index, core, rank, top),
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 skills/nist-csf/scripts/profile_analysis.py self-test`
Expected: `self-test: 162/162 checks passed`

- [ ] **Step 5: Verify the shipped fixture's existing numbers have not moved**

Run:
```bash
python3 skills/nist-csf/scripts/profile_analysis.py analyze \
  skills/nist-csf/examples/example-profile.csfp --today 2026-07-27 \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d["coverage"], d["completeness"]["overall"], len(d["gaps"]))'
```
Expected: identical to the values before Task 1. Any difference is a defect in this change, not a new baseline.

- [ ] **Step 6: Commit**

```bash
git add skills/nist-csf/scripts/profile_analysis.py
git commit -m "feat(nist-csf): analyze emits evidence, intake and queue blocks"
```

---

## Task 8: `csfa_compat convert` emits v2 with a synthesized source

**Files:**
- Modify: `skills/nist-csf/scripts/csfa_compat.py` (`convert_to_csfp` 192–265)
- Test: `skills/nist-csf/scripts/csfa_compat.py::_cmd_self_test`

- [ ] **Step 1: Write the failing test**

Add to `csfa_compat.py`'s `_cmd_self_test`, before its final print:

```python
    # --- Conversion lands as v2 with the source assessment as its own intake record ---
    conv = convert_to_csfp(a, core, ts="2026-07-27T00:00:00Z")
    eq(conv["schemaVersion"], "2.0", "convert writes schema 2.0")
    eq(len(conv["intake"]), 1, "convert synthesises one intake record for the source file")
    rec = conv["intake"][0]
    eq(rec["id"], "in-0001", "the synthesised record is in-0001")
    ok("csf-assessment" in rec["label"], "the label names where the ratings came from")
    rated = [x["subcategoryId"] for x in conv["assessments"] if x["current"] is not None]
    eq(sorted(rec["subjects"]), sorted(rated),
       "the record bears on exactly the Subcategories the source rated")
    for x in conv["assessments"]:
        if x["current"] is not None:
            eq(x["source"], "in-0001", f"{x['subcategoryId']}: rating attributed to the import")
            ok(bool(x["confirmedBy"]), f"{x['subcategoryId']}: rating names a confirmer")
            ok(bool(x["confirmedAt"]), f"{x['subcategoryId']}: rating carries a date")
            break
    unrated = [x for x in conv["assessments"] if x["current"] is None]
    ok(all(x["source"] is None for x in unrated), "unrated rows carry no attribution")
    ok("in-0001" not in {s for x in conv["assessments"] if x["current"] is None
                         for s in [x["source"]]},
       "the import does not attribute what it did not rate")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 skills/nist-csf/scripts/csfa_compat.py self-test`
Expected: FAIL — `convert writes schema 2.0: expected '2.0', got '1.0'` (or a `KeyError: 'intake'`)

- [ ] **Step 3: Write the implementation**

In `convert_to_csfp`, add the attribution fields to each assessment dict it builds, and append the intake record. The rated set is known once the assessments are built, so compute it after:

```python
    # A converted assessment IS a source: it happened on a date, a person ran it, and
    # it bears on exactly the Subcategories it rated. Recording it as intake means
    # every imported rating answers "how do you know?" from day one instead of
    # arriving as 106 unattributed numbers.
    imported_by = (assessment.get("assessor") or assessment.get("meta", {}).get("assessor")
                   or "csf-assessment import")
    source_date = (assessment.get("date") or assessment.get("meta", {}).get("date") or ts[:10])[:10]
    rated = [a["subcategoryId"] for a in assessments if a.get("current") is not None]
    for a in assessments:
        if a.get("current") is not None:
            a["source"] = "in-0001"
            a["confirmedBy"] = imported_by
            a["confirmedAt"] = source_date
        else:
            a["source"] = None
            a["confirmedBy"] = None
            a["confirmedAt"] = None

    intake = [{
        "id": "in-0001",
        "label": f"csf-assessment web tool export, imported {ts[:10]}",
        "sourceDate": source_date,
        "recordedAt": ts[:10],
        "subjects": rated,
        "recordedBy": imported_by,
    }] if rated else []
```

Add `"intake": intake,` to the returned store dict alongside `"assessments"`, `"history"`, `"snapshots"`, `"actionItems"`.

> `pa.SCHEMA_VERSION` is already referenced at line 235, so the version follows Task 1 automatically. Do not hardcode `"2.0"` here.

Append one history event so the import is on the audit trail, beside the existing conversion events:

```python
    if intake:
        history.append({
            "ts": ts, "actor": imported_by, "type": "intake-recorded",
            "intakeId": "in-0001",
            "rationale": f"Imported from a csf-assessment export; {len(rated)} ratings "
                         f"attributed to that assessment.",
        })
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 skills/nist-csf/scripts/csfa_compat.py self-test`
Expected: `csfa-compat self-test: 37/37 checks passed`

- [ ] **Step 5: Verify Acme gaps parity is byte-identical**

Run:
```bash
python3 skills/nist-csf/scripts/csfa_compat.py gaps \
  skills/nist-csf/examples/acme-manufacturing.csfa --out /tmp/acme-gaps.csv
diff /tmp/acme-gaps.csv skills/nist-csf/examples/acme-manufacturing-gaps.csv && echo "BYTE PARITY OK"
python3 skills/nist-csf/scripts/csfa_compat.py convert \
  skills/nist-csf/examples/acme-manufacturing.csfa --out /tmp/acme.csfp
python3 skills/nist-csf/scripts/profile_analysis.py analyze /tmp/acme.csfp --today 2026-07-27 \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); e=d["evidence"]; print(e["coverage"]["overall"]); print(e["scopeGuard"]["statement"])'
```
Expected: `BYTE PARITY OK`, then a four-way split where `attributed` equals `confirmed` (the import attributed all of them), and a scope-guard statement.

- [ ] **Step 6: Commit**

```bash
git add skills/nist-csf/scripts/csfa_compat.py
git commit -m "feat(nist-csf): convert lands as v2 and records the source assessment as intake"
```

---

## Task 9: Executive dashboard — scope guard, four-way coverage, age, revisit

**Files:**
- Modify: `skills/nist-csf/renderers/_common.py` (brand tokens ~line 40; `Context.__init__` ~line 245)
- Modify: `skills/nist-csf/renderers/render_executive.py` (`main` 269–296; `CSS`)

- [ ] **Step 1: Add the shared state fills and Context accessors**

In `_common.py`, after the `PRIORITY_COLOR` line, add:

```python
# Evidence states are STATES, not measurements, so they must not sit on the coverage
# ramp and must not use patina. Text on any of them comes from text_on(fill) — never
# hand-picked. See assets/brand.md, "Text on a coverage swatch — do not hand-pick it".
EVIDENCE_FILL = {
    "confirmed":        INK,        # 17.96:1 with white
    "evidence-pending": "#526A78",  #  5.69:1 with white
    "unrated":          WB_LINE,    # 12.02:1 with ink
    "not-applicable":   WB,         # 16.33:1 with ink, plus a WB_LINE border
}
EVIDENCE_LABEL = {
    "confirmed": "confirmed", "evidence-pending": "material, not yet confirmed",
    "unrated": "not looked at", "not-applicable": "not applicable",
}
EVIDENCE_ORDER = ["confirmed", "evidence-pending", "unrated", "not-applicable"]
EVIDENCE_KEY = {"confirmed": "confirmed", "evidence-pending": "evidencePending",
                "unrated": "unrated", "not-applicable": "notApplicable"}
```

In `Context.__init__`, after `self.diff = self.a.get("diff")`, add:

```python
        # Absent on analyze output from a v1 engine — every consumer must degrade,
        # not crash, so a dashboard built from an older JSON still renders.
        self.evidence = self.a.get("evidence") or {}
        self.intake = self.a.get("intake") or {"records": [], "bySource": []}
        self.queue = self.a.get("queue") or []
```

Add a shared bar builder to `_common.py` so both renderers draw an identical strip:

```python
def evidence_bar(split: dict) -> str:
    """The four-way coverage strip. 'Material on 41, confirmed on 24' is what makes a
    partial profile read as progress rather than abandonment."""
    total = split.get("total") or 0
    if not total:
        return ""
    segs, legend = [], []
    for state in EVIDENCE_ORDER:
        n = split.get(EVIDENCE_KEY[state], 0)
        if not n:
            continue
        fill = EVIDENCE_FILL[state]
        fg = text_on(fill)
        border = f";border:1px solid {WB_LINE}" if state == "not-applicable" else ""
        segs.append(f'<div class="eseg" style="flex:{n};background:{fill};color:{fg}{border}" '
                    f'title="{esc(EVIDENCE_LABEL[state])}: {n}">{n}</div>')
        legend.append(f'<span class="eleg"><i style="background:{fill}{border}"></i>'
                      f'{esc(EVIDENCE_LABEL[state])} {n}</span>')
    unatt = split.get("unattributed", 0)
    note = ("" if not unatt else
            f'<div class="muted" style="margin-top:6px">{unatt} of '
            f'{split.get("confirmed", 0)} confirmed ratings carry no source or confirmer — '
            f'they predate evidence tracking and report as unattributed.</div>')
    return (f'<div class="ebar">{"".join(segs)}</div>'
            f'<div class="elegend">{"".join(legend)}</div>{note}')


EVIDENCE_CSS = """
.ebar{display:flex;height:34px;border-radius:6px;overflow:hidden;margin-top:10px}
.eseg{display:flex;align-items:center;justify-content:center;font-weight:700;font-size:13px;
      min-width:0;overflow:hidden}
.elegend{display:flex;flex-wrap:wrap;gap:14px;margin-top:10px;font-size:13px;color:#666D7C}
.eleg{display:inline-flex;align-items:center;gap:6px}
.eleg i{width:12px;height:12px;border-radius:3px;display:inline-block;flex:none}
.guard{border-left:4px solid #526A78;padding:14px 16px}
.guard .gh{font-family:'Space Grotesk',sans-serif;font-size:20px;font-weight:600}
.agegrid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;
         margin-top:10px;min-width:0}
.agecell{border:1px solid #D8D3C6;border-radius:6px;padding:10px;min-width:0}
.agecell .an{font-size:20px;font-weight:700;font-family:'Space Grotesk',sans-serif}
"""
```

- [ ] **Step 2: Replace the executive headline with the scope guard**

In `render_executive.py`, add above `main`:

```python
def headline_or_guard(ctx: c.Context) -> str:
    """Below the scope threshold the programme mean is SUPPRESSED, not caveated.

    A number with a warning beside it is still a number, and people read the number.
    """
    cov, comp = ctx.coverage["overall"], ctx.completeness["overall"]
    guard = (ctx.evidence.get("scopeGuard") or {})
    if guard.get("suppressed"):
        return (f'<section><div class="card guard">'
                f'<div class="gh">Coverage is not reported at this level of assessment</div>'
                f'<p style="margin:10px 0 0">{c.esc(guard.get("statement", ""))}</p>'
                f'<div class="muted" style="margin-top:8px">'
                f'The Function-level figures below are shown with their fractions so a '
                f'reader can see what each one is drawn from.</div>'
                f'</div></section>')
    return (f'<section><div class="card">'
            f'<div style="font-size:30px;font-weight:700;'
            f'font-family:\'Space Grotesk\',sans-serif">{c.esc(c.cov_label(cov))}</div>'
            f'<div class="muted" style="margin-top:6px">overall coverage of Target · '
            f'{c.esc(c.completeness_line(comp))}</div></div></section>')


def evidence_block(ctx: c.Context) -> str:
    """Four-way coverage, age, and the revisit count — all four in the board view,
    not only the operational tables."""
    ev = ctx.evidence
    if not ev:
        return ""
    split = (ev.get("coverage") or {}).get("overall") or {}
    age = (ev.get("age") or {}).get("overall") or {}
    thr = (ev.get("age") or {}).get("thresholdDays", 180)
    revisit = ev.get("revisit") or []

    if age.get("dated"):
        cells = [
            ("median age", f'{age["medianDays"]} days'),
            ("oldest", f'{age["oldestDays"]} days'),
            (f"older than {thr} days", f'{age["olderThanThreshold"]}'),
            ("ratings questioned by newer material", f'{len(revisit)}'),
        ]
        age_html = ('<div class="agegrid">' + "".join(
            f'<div class="agecell"><div class="an">{c.esc(v)}</div>'
            f'<div class="muted">{c.esc(k)}</div></div>' for k, v in cells) + '</div>')
        if age.get("undated"):
            age_html += (f'<div class="muted" style="margin-top:8px">'
                         f'{age["undated"]} confirmed ratings carry no confirmation date and '
                         f'are excluded from these figures.</div>')
    else:
        age_html = ('<div class="muted" style="margin-top:10px">No rating in this Profile '
                    'carries a confirmation date yet, so there is no age to report. Age '
                    'reporting begins as ratings are confirmed with a source and a date.</div>')

    return (f'<section><h2>How much of this is known, and how old is it</h2>'
            f'<div class="hint">Ratings do not expire. Age is reported and the reader '
            f'judges — a governance outcome and an asset inventory go stale at completely '
            f'different rates.</div>'
            f'<div class="card">{c.evidence_bar(split)}{age_html}</div></section>')
```

Change the body composition in `main` (lines 286–293) to:

```python
    body = (head + "<main>" + summary + headline_or_guard(ctx) + evidence_block(ctx)
            + rollup(ctx) + tier_block(ctx)
            + top_gaps(ctx) + what_changed(ctx) + decisions(ctx) + "</main>"
            + f'<footer>{c.esc(ctx.footer())}</footer>')
```

Delete the now-unused `headline = (...)` assignment (lines 286–290).

Append the shared CSS to this module's `CSS` constant — find the closing `"""` of `CSS` and change the last line to:

```python
@media (max-width:720px){{.tierdetail{{grid-template-columns:1fr}}}}
""" + c.EVIDENCE_CSS
```

> `CSS` in this module is an f-string-style template consumed by `c.page`; `EVIDENCE_CSS` contains no braces, so concatenating it is safe. Verify by rendering in step 3 — a `KeyError` or stray `{` in the output means the concatenation happened on the wrong side of the formatting.

- [ ] **Step 3: Render and check**

Run:
```bash
python3 skills/nist-csf/scripts/profile_analysis.py init --name "Partial Co" --out /tmp/pc.csfp --owner CISO
python3 skills/nist-csf/scripts/profile_analysis.py quickstart-target /tmp/pc.csfp --rationale baseline
python3 skills/nist-csf/scripts/profile_analysis.py intake add /tmp/pc.csfp \
  --label "architecture review with infra team" --subjects ID.AM-01 ID.AM-02 ID.AM-03 \
  --source-date 2026-03-14 --recorded-by the maintainer
python3 skills/nist-csf/scripts/profile_analysis.py set /tmp/pc.csfp ID.AM-01 --current 2 \
  --source in-0001 --confirmed-by the maintainer --rationale "quarterly discovery scans confirmed"
python3 skills/nist-csf/scripts/profile_analysis.py analyze /tmp/pc.csfp --today 2026-07-27 > /tmp/pc.json
python3 skills/nist-csf/renderers/render_executive.py --in /tmp/pc.json --out /tmp/pc-exec.html --offline
grep -c "Coverage is not reported at this level of assessment" /tmp/pc-exec.html
grep -o 'class="ebar"' /tmp/pc-exec.html | head -1
```
Expected: `1`, then `class="ebar"`. Open `/tmp/pc-exec.html` and confirm **no headline percentage appears anywhere above the Function tiles**.

- [ ] **Step 4: Commit**

```bash
git add skills/nist-csf/renderers/_common.py skills/nist-csf/renderers/render_executive.py
git commit -m "feat(nist-csf): executive view suppresses a minority-coverage headline and reports evidence"
```

---

## Task 10: Operational dashboard — same four, plus coverage-by-source

**Files:**
- Modify: `skills/nist-csf/renderers/render_operational.py` (`main` 324–355; `CSS`)

- [ ] **Step 1: Write the sections**

Add above `main` in `render_operational.py`:

```python
def overall_block(ctx: c.Context) -> str:
    """The working view's overall card, under the same scope guard as the board view.

    The guard must bind BOTH renderers or the number simply reappears one document
    over, which is how a suppressed figure gets quoted back at a board anyway.
    """
    cov, comp = ctx.coverage["overall"], ctx.completeness["overall"]
    guard = (ctx.evidence.get("scopeGuard") or {})
    split = ((ctx.evidence.get("coverage") or {}).get("overall")) or {}
    tracked = (f'{ctx.a.get("tracked", 0)} of {ctx.framework.get("subcategories", 0)} '
               f'Subcategories tracked')

    if guard.get("suppressed"):
        head = (f'<div class="card guard">'
                f'<div class="gh">No overall coverage figure yet</div>'
                f'<p style="margin:10px 0 0">{c.esc(guard.get("statement", ""))}</p>'
                f'<div class="muted" style="margin-top:6px">{c.esc(tracked)}</div>'
                f'{c.evidence_bar(split)}</div>')
    else:
        head = (f'<div class="card"><div style="font-size:30px;font-weight:700;'
                f'font-family:\'Space Grotesk\',sans-serif">{c.esc(c.cov_label(cov))}</div>'
                f'<div class="muted" style="margin-top:6px">'
                f'{c.esc(c.completeness_line(comp))} · {c.esc(tracked)}</div>'
                + ('' if not c.cov_is_untargeted(cov) else
                   '<div class="muted" style="margin-top:8px">Nothing is targeted yet, so there '
                   'is no coverage figure to report. Run <span class="mono">quickstart-target'
                   '</span> and then tune Targets by risk.</div>')
                + c.evidence_bar(split) + '</div>')
    return f'<section><h2>Overall coverage</h2>{head}</section>'


def evidence_detail(ctx: c.Context) -> str:
    """Age by Function, and the ratings newer material has called into question."""
    ev = ctx.evidence
    if not ev:
        return ""
    thr = (ev.get("age") or {}).get("thresholdDays", 180)
    by_fn = (ev.get("age") or {}).get("byFunction") or {}
    rows = []
    for fn in ctx.function_meta():
        a = by_fn.get(fn["id"]) or {}
        if not a.get("dated"):
            rows.append(f'<tr><td class="mono">{c.esc(fn["id"])}</td><td>{c.esc(fn.get("name",""))}'
                        f'</td><td colspan="3" class="muted">no dated confirmations</td></tr>')
            continue
        rows.append(f'<tr><td class="mono">{c.esc(fn["id"])}</td>'
                    f'<td>{c.esc(fn.get("name",""))}</td>'
                    f'<td>{a["medianDays"]} days</td><td>{a["oldestDays"]} days</td>'
                    f'<td>{a["olderThanThreshold"]}</td></tr>')

    revisit = ev.get("revisit") or []
    if revisit:
        rv = "".join(
            f'<tr><td class="mono">{c.esc(r["subcategoryId"])}</td>'
            f'<td>{c.esc(c.trunc(r["text"], 90))}</td>'
            f'<td>{c.esc(r["confirmedAt"] or "—")}</td>'
            f'<td>{c.esc(r["newestSourceDate"])}</td>'
            f'<td class="mono">{c.esc(", ".join(r["intakeIds"]))}</td></tr>' for r in revisit)
        rv_block = (f'<h3>Questioned by newer material ({len(revisit)})</h3>'
                    f'<div class="scroll"><table><thead><tr><th>Subcategory</th><th>Outcome</th>'
                    f'<th>Confirmed</th><th>Newer material</th><th>Source</th></tr></thead>'
                    f'<tbody>{rv}</tbody></table></div>')
    else:
        rv_block = ('<h3>Questioned by newer material</h3><div class="card muted">Nothing. No '
                    'source recorded since a confirmation bears on a rating already made.</div>')

    return (f'<section><h2>Age and revisits</h2>'
            f'<div class="hint">Ratings never expire. A rating is questioned when new material '
            f'arrives about it, not when time passes — so this reports age and lets you judge. '
            f'"Older than" counts against the {thr}-day threshold set on this Profile.</div>'
            f'<div class="scroll"><table><thead><tr><th>Function</th><th></th><th>Median age</th>'
            f'<th>Oldest</th><th>Older than {thr}d</th></tr></thead><tbody>{"".join(rows)}'
            f'</tbody></table></div>{rv_block}</section>')


def by_source(ctx: c.Context) -> str:
    """What each source actually covered. The payoff of keying intake by source."""
    rows = ctx.intake.get("bySource") or []
    if not rows:
        return ('<section><h2>Coverage by source</h2><div class="card muted">No sources '
                'recorded yet. Record one as it arrives — it takes a label and a list of '
                'Subcategory ids, and it writes no ratings:<br>'
                '<span class="mono">intake add &lt;store.csfp&gt; --label \'...\' '
                '--subjects ID.AM-01 ID.AM-02</span></div></section>')
    cards = []
    for r in rows:
        chips = "".join(
            f'<span class="chip" style="background:{c.EVIDENCE_FILL[s["state"]]};'
            f'color:{c.text_on(c.EVIDENCE_FILL[s["state"]])}" '
            f'title="{c.esc(c.EVIDENCE_LABEL[s["state"]])}">{c.esc(s["subcategoryId"])}</span>'
            for s in r["subjects"])
        cards.append(
            f'<div class="card srccard"><div class="srchead">'
            f'<span class="mono">{c.esc(r["id"])}</span> · {c.esc(r["label"])}</div>'
            f'<div class="muted">source dated {c.esc(r["sourceDate"] or "—")} · recorded '
            f'{c.esc(r["recordedAt"] or "—")}'
            + (f' by {c.esc(r["recordedBy"])}' if r.get("recordedBy") else '')
            + f' · bears on {len(r["subjects"])} · {r["confirmed"]} confirmed · '
              f'{r["pending"]} still pending</div>'
            f'<div class="chips">{chips}</div></div>')
    return (f'<section><h2>Coverage by source <span class="muted">({len(rows)})</span></h2>'
            f'<div class="hint">What each conversation, note or review actually bore on. '
            f'Labels are what a human wrote about the source — never an excerpt from it.</div>'
            f'{"".join(cards)}</section>')
```

Replace the `overall = (...)` block in `main` (lines 337–347) — delete it — and change the body composition to:

```python
    body = (head + "<main>" + overall_block(ctx) + heatmap(ctx) + gap_table(ctx)
            + evidence_detail(ctx) + by_source(ctx) + attention(ctx)
            + playbook(ctx) + action_plan(ctx) + "</main>"
            + f'<footer>{c.esc(ctx.footer())}</footer>'
            + f"<script>{JS}</script>")
```

Append to this module's `CSS` constant, at its closing `"""`:

```python
""" + c.EVIDENCE_CSS + """
.srccard{margin-bottom:10px}
.srchead{font-weight:700;font-family:'Space Grotesk',sans-serif;font-size:15px}
.chips{display:flex;flex-wrap:wrap;gap:6px;margin-top:10px}
.chip{font-family:'IBM Plex Mono',ui-monospace,monospace;font-size:12px;padding:3px 7px;
      border-radius:4px;white-space:nowrap}
.scroll{overflow-x:auto;min-width:0}
"""
```

> Every wide element must scroll inside its own `overflow-x:auto` container **and** the grid item above it needs `min-width:0`, or one long table cell props the whole page open. That is trap 2 documented at the top of `responsive.sh`, and it is the defect this repo has shipped twice.

- [ ] **Step 2: Render and check**

Run:
```bash
python3 skills/nist-csf/renderers/render_operational.py --in /tmp/pc.json --out /tmp/pc-ops.html --offline
grep -c "Coverage by source" /tmp/pc-ops.html
grep -c "Age and revisits" /tmp/pc-ops.html
grep -c "No overall coverage figure yet" /tmp/pc-ops.html
```
Expected: `1`, `1`, `1`

- [ ] **Step 3: Commit**

```bash
git add skills/nist-csf/renderers/render_operational.py
git commit -m "feat(nist-csf): operational view gains age, revisits and coverage-by-source"
```

---

## Task 11: v2 fixture covering every new state

**Files:**
- Create: `skills/nist-csf/examples/example-profile-v2.csfp`
- Modify: `skills/nist-csf/scripts/profile_analysis.py::_cmd_self_test`

- [ ] **Step 1: Build the fixture from the CLI, so it can only contain what the engine can write**

Run:
```bash
P=skills/nist-csf/examples/example-profile-v2.csfp
rm -f "$P"
python3 skills/nist-csf/scripts/profile_analysis.py init \
  --name "Accretion Manufacturing Co — Enterprise Profile" --out "$P" --owner CISO \
  --purpose "Fixture Profile for evidence accretion: intake, partial confirmation, a revisit, and ratings spanning more than twelve months." \
  --org-units "Corporate IT" "Plant OT" --threat-types ransomware "supply chain compromise" \
  --ts 2025-06-01T00:00:00Z
python3 skills/nist-csf/scripts/profile_analysis.py quickstart-target "$P" \
  --rationale "Baseline Target of 2 across the Profile; tuned by risk in later reviews." \
  --ts 2025-06-01T00:00:00Z

python3 skills/nist-csf/scripts/profile_analysis.py intake add "$P" \
  --label "asset management workshop with infrastructure" --subjects ID.AM-01 ID.AM-02 ID.AM-03 ID.AM-05 \
  --source-date 2025-05-20 --recorded-by the maintainer --ts 2025-06-01T00:00:00Z
python3 skills/nist-csf/scripts/profile_analysis.py intake add "$P" \
  --label "annual backup restore test debrief" --subjects PR.DS-11 RC.RP-01 \
  --source-date 2026-01-08 --recorded-by the maintainer --ts 2026-01-09T00:00:00Z
python3 skills/nist-csf/scripts/profile_analysis.py intake add "$P" \
  --label "identity programme steering, notes only" --subjects PR.AA-01 PR.AA-03 PR.AA-05 \
  --source-date 2026-05-12 --recorded-by the maintainer --ts 2026-05-14T00:00:00Z
python3 skills/nist-csf/scripts/profile_analysis.py intake add "$P" \
  --label "DR walkthrough after the June outage" --subjects RC.RP-01 \
  --source-date 2026-06-30 --recorded-by the maintainer --ts 2026-07-02T00:00:00Z

# Confirmed >12 months ago — makes the age distribution real.
python3 skills/nist-csf/scripts/profile_analysis.py set "$P" ID.AM-01 --current 2 \
  --source in-0001 --confirmed-by the maintainer --ts 2025-06-02T00:00:00Z \
  --rationale "Workshop confirmed quarterly discovery scans across corporate IT; OT out of band."
python3 skills/nist-csf/scripts/profile_analysis.py set "$P" ID.AM-02 --current 1 \
  --source in-0001 --confirmed-by the maintainer --ts 2025-06-02T00:00:00Z \
  --rationale "Software inventory exists for managed endpoints only."
# Confirmed this year.
python3 skills/nist-csf/scripts/profile_analysis.py set "$P" PR.DS-11 --current 3 \
  --source in-0002 --confirmed-by the maintainer --ts 2026-01-10T00:00:00Z \
  --rationale "Restore test passed end to end within RTO."
# Confirmed, then newer material arrived -> revisit.
python3 skills/nist-csf/scripts/profile_analysis.py set "$P" RC.RP-01 --current 2 \
  --source in-0002 --confirmed-by the maintainer --ts 2026-01-10T00:00:00Z \
  --rationale "Recovery plan executed during the restore test."
# Scoped out, so the four-way split has an n/a bucket.
python3 skills/nist-csf/scripts/profile_analysis.py set "$P" PR.AA-06 \
  --applicability not-applicable \
  --rationale "Physical access is managed by the facilities contract and assessed there." \
  --ts 2026-01-10T00:00:00Z

python3 skills/nist-csf/scripts/profile_analysis.py snapshot "$P" --label "2026 mid-year" \
  --note "First accretion review" --ts 2026-07-01T00:00:00Z
```

- [ ] **Step 2: Write the test that pins the fixture**

Add to `_cmd_self_test`, after the analyze block:

```python
    # --- The shipped v2 fixture exercises every new state at once ---
    fx2 = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "examples",
                       "example-profile-v2.csfp")
    s2 = load_store(fx2)
    eq(s2["schemaVersion"], "2.0", "v2 fixture is schema 2.0")
    eq(len(s2["intake"]), 4, "v2 fixture carries four intake records")
    rep2 = s2["profile"]["settings"]["reporting"]
    ev2 = derive_evidence(s2["assessments"], s2["intake"], index, core, "2026-07-27",
                          rep2["scopeThresholdPct"], rep2["ageThresholdDays"])
    cov2 = ev2["coverage"]["overall"]
    eq(cov2["confirmed"], 4, "v2 fixture: four confirmed ratings")
    eq(cov2["attributed"], 4, "v2 fixture: every confirmation is attributed")
    eq(cov2["evidencePending"], 5, "v2 fixture: five Subcategories have material, no rating")
    eq(cov2["notApplicable"], 1, "v2 fixture: one Subcategory scoped out")
    eq(cov2["confirmed"] + cov2["evidencePending"] + cov2["unrated"] + cov2["notApplicable"],
       106, "v2 fixture: the four buckets still partition all 106")
    eq([r["subcategoryId"] for r in ev2["revisit"]], ["RC.RP-01"],
       "v2 fixture: the DR walkthrough questions the January recovery rating")
    ok(ev2["age"]["overall"]["oldestDays"] > 365,
       "v2 fixture: ratings span more than twelve months")
    eq(ev2["age"]["overall"]["olderThanThreshold"], 4,
       "v2 fixture: all four confirmations are older than the 180-day threshold")
    eq(ev2["age"]["overall"]["medianDays"], 309, "v2 fixture: median of 198, 198, 420, 420")
    eq(ev2["age"]["overall"]["oldestDays"], 420, "v2 fixture: oldest is 2025-06-02 to 2026-07-27")
    ok(ev2["scopeGuard"]["suppressed"], "v2 fixture sits below the scope threshold")
    q2 = build_queue(s2["assessments"], s2["intake"], ev2, index, core,
                     resolve_rank(index, core, load_cold_start_rank()), 5)
    eq(q2[0]["band"], "evidence-pending", "v2 fixture queue leads with pending material")
    ok(all(r["tier"] is None for r in q2), "v2 fixture queue carries no pre-filled ratings")
```

- [ ] **Step 3: Run test to verify it passes**

Run: `python3 skills/nist-csf/scripts/profile_analysis.py self-test`
Expected: `self-test: 178/178 checks passed`

> If a count assertion fails, read the actual number off the failure message and confirm it against the fixture-building commands above before changing it. A count that does not match the commands means the fixture build was wrong, not the assertion.

- [ ] **Step 4: Commit**

```bash
git add skills/nist-csf/examples/example-profile-v2.csfp skills/nist-csf/scripts/profile_analysis.py
git commit -m "test(nist-csf): v2 fixture covering intake, revisit, age spread and the scope guard"
```

---

## Task 12: Fix the eval fixtures and gate the new visual states

**Files:**
- Modify: `skills/risk-register/evals/board-safety.sh` (line 40)
- Modify: `skills/risk-register/evals/responsive.sh` (lines ~62, ~135)

- [ ] **Step 1: Confirm both suites currently break**

Run: `PY="$(command -v python3)" ./skills/risk-register/evals/board-safety.sh`
Expected: FAIL — the fixture loop hits `error: --source and --confirmed-by are required for a Current rating.`

- [ ] **Step 2: Fix `board-safety.sh`**

Replace the fixture loop (the `for s in ...` block around line 39–42) with:

```bash
"$PY" "$CSF/scripts/profile_analysis.py" intake add "$work/p.csfp" \
  --label "regression fixture seed" \
  --subjects PR.AA-01 GV.SC-07 DE.AE-03 ID.AM-01 RS.MA-01 RC.RP-01 >/dev/null
for s in PR.AA-01 GV.SC-07 DE.AE-03 ID.AM-01 RS.MA-01 RC.RP-01; do
  "$PY" "$CSF/scripts/profile_analysis.py" set "$work/p.csfp" "$s" \
    --current 0 --target 3 --source in-0001 --confirmed-by fixture --rationale fixture >/dev/null
done
```

- [ ] **Step 3: Fix `responsive.sh` and add the below-threshold pair**

Apply the identical fixture fix to the `for s in ...` loop around line 62.

Then, after the two existing CSF renders (around line 135), add a second, deliberately partial Profile so the scope guard and the four-way bar are actually laid out and measured:

```bash
# A second CSF pair, deliberately below the scope threshold. The first fixture seeds
# ratings across every Function, so it renders the headline path only — and the scope
# guard, the four-way bar and the by-source cards would never be drawn. A suite that
# cannot reach a state is not covering it, which is how three render defects already
# reached the user.
"$PY" "$CSF/scripts/profile_analysis.py" init --name "Partial Co" \
  --out "$work/partial.csfp" --owner CISO >/dev/null
"$PY" "$CSF/scripts/profile_analysis.py" quickstart-target "$work/partial.csfp" >/dev/null
"$PY" "$CSF/scripts/profile_analysis.py" intake add "$work/partial.csfp" \
  --label "architecture review with the infrastructure team, covering discovery and data flows" \
  --subjects ID.AM-01 ID.AM-02 ID.AM-03 ID.AM-05 PR.AA-01 --source-date 2025-03-14 \
  --recorded-by CISO >/dev/null
"$PY" "$CSF/scripts/profile_analysis.py" intake add "$work/partial.csfp" \
  --label "backup restore test debrief" --subjects PR.DS-11 RC.RP-01 \
  --source-date 2026-06-30 --recorded-by CISO >/dev/null
"$PY" "$CSF/scripts/profile_analysis.py" set "$work/partial.csfp" ID.AM-01 --current 2 \
  --source in-0001 --confirmed-by CISO --rationale fixture --ts 2025-03-20T00:00:00Z >/dev/null
"$PY" "$CSF/scripts/profile_analysis.py" set "$work/partial.csfp" RC.RP-01 --current 1 \
  --source in-0002 --confirmed-by CISO --rationale fixture --ts 2026-01-10T00:00:00Z >/dev/null
"$PY" "$CSF/scripts/profile_analysis.py" set "$work/partial.csfp" PR.AA-06 \
  --applicability not-applicable --rationale fixture >/dev/null
"$PY" "$CSF/scripts/profile_analysis.py" analyze "$work/partial.csfp" \
  --today 2026-07-27 > "$work/partial.json"
"$PY" "$CSF/renderers/render_executive.py" --in "$work/partial.json" \
  --out "$work/csf_exec_partial.html" --offline >/dev/null
"$PY" "$CSF/renderers/render_operational.py" --in "$work/partial.json" \
  --out "$work/csf_ops_partial.html" --offline >/dev/null
```

Extend the `pages=(...)` array to include both new files:

```bash
pages=("$work/render_board.html" "$work/render_dashboard.html" "$work/render_report.html"
       "$work/csf_exec.html" "$work/csf_ops.html"
       "$work/csf_exec_partial.html" "$work/csf_ops_partial.html")
```

- [ ] **Step 4: Run both suites**

Run:
```bash
PY="$(command -v python3)" ./skills/risk-register/evals/board-safety.sh
./skills/risk-register/evals/responsive.sh
```
Expected: board-safety passes; responsive prints `responsive: every artifact fits every tested width and meets AA contrast` across 320/375/768/1265px.

> If responsive prints `SKIP`, it found no Chrome or no Node 22 and **measured nothing**. A skip is not a pass. Set `CHROME=/path/to/chrome` and re-run before continuing — this task's entire purpose is the visual gate, and the four new states plus the source chips are the largest contrast surface this plugin has added in one change.

- [ ] **Step 5: Run the Python floor check**

Run: `./skills/risk-register/evals/python-compat.sh /usr/bin/python3`
Expected: every shipped `.py` compiles on 3.9. The walrus in `_next_intake_id` is 3.8+, so it is fine; a failure here means something newer slipped in.

- [ ] **Step 6: Commit**

```bash
git add skills/risk-register/evals/board-safety.sh skills/risk-register/evals/responsive.sh
git commit -m "test: seed eval fixtures through intake, and measure the below-threshold CSF pair"
```

---

## Task 13: Documentation

**Files:**
- Modify: `skills/nist-csf/references/schema.md`
- Modify: `skills/nist-csf/references/dashboards.md`
- Modify: `skills/nist-csf/references/assessment-and-review.md`
- Modify: `skills/nist-csf/SKILL.md`

- [ ] **Step 1: `references/schema.md`**

Change the title to `# CSF Organizational Profile — Data Model Reference (\`.csfp\` schema v2)` and the store-shape heading to `## Store shape (schema v2)`. Replace the store JSON block with:

```json
{
  "schemaVersion": "2.0",
  "profile": { /* Profile */ },
  "assessments": [ /* Assessment[] — one per Subcategory */ ],
  "intake":      [ /* IntakeRecord[] — append-only, never rewritten */ ],
  "history":     [ /* HistoryEvent[] — append-only, never rewritten */ ],
  "snapshots":   [ /* Snapshot[] — named point-in-time freezes */ ],
  "actionItems": [ /* ActionItem[] */ ]
}
```

Add these sections after "The three states a rating can be in":

````markdown
## Attribution on a rating

Every assessment carries three fields answering "how do you know?":

| Field | Type | Notes |
|---|---|---|
| `confirmedAt` | ISO date, or `null` | The date a human decided this Current rating. |
| `confirmedBy` | string, or `null` | The name of the confirming human. |
| `source` | intake `id`, or `null` | The source the decision was made from. |

`set --current` **refuses** without `--source` and `--confirmed-by`. `--target` is not gated:
a Target is a risk-based decision, already covered by `--rationale`.

**The honest limit.** The CLI cannot prove a human typed the number. What it enforces is that no
rating exists without attribution — a named person and a named source, or the write fails. The
human-confirmation discipline itself lives in `SKILL.md` and is a behavioural rule, not a
mechanical one. Mechanical where it can be; explicit about where it can't.

A v1 rating normalizes with all three `null`. It still scores; it simply reports as unattributed.
That is what lets every existing Profile load untouched.

`confirmedAt` is **not** seeded from `lastReviewed`. "A human looked at this outcome" and "a human
decided this rating, from this source, on this date" are different claims, and manufacturing the
second from the first would fabricate exactly the attribution this schema exists to make honest.

## Intake — the source is the unit of record

Append-only, mirroring `history[]`.

```json
{
  "id": "in-0001",
  "label": "architecture review with infra team",
  "sourceDate": "2026-03-14",
  "recordedAt": "2026-03-16",
  "subjects": ["ID.AM-01", "ID.AM-02", "ID.AM-03"],
  "recordedBy": "R. Calder"
}
```

- `label` is **human-authored or human-confirmed, never model-generated**, and is a note *about*
  the source — not a quoted excerpt *from* it. This is the line that keeps internal material out
  of the file.
- `sourceDate` is when the conversation happened. `recordedAt` is when it entered the store. These
  diverge routinely under accretion, and conflating them would misreport age.
- `subjects` is what the source bears on. One conversation typically bears on many Subcategories,
  and "what did the March architecture review cover?" is the question a per-Subcategory pointer
  list structurally cannot answer.

`intake add` writes **no ratings**, ever. That is the whole point: recording must cost under thirty
seconds or it will not happen mid-conversation.

**Not stored:** evidence artifacts of any kind. No documents, screenshots, exports or transcripts.
This skill helps produce a profile and a report; it does not become where the organization's
evidence lives.

**Personal data:** `confirmedBy` and `recordedBy` are names. They are the only personal data in the
store. The store remains a local file with no network path.

## Derived evidence states — never stored

| Derived state | Rule |
|---|---|
| `evidence-pending` | In scope, appears in some `intake.subjects`, `current` is `null` |
| `confirmed` | In scope, `current` is not `null` |
| `unrated` | In scope, `current` is `null`, no intake bears on it |
| `revisit` | Confirmed, and some intake bearing on it has `sourceDate` later than its `confirmedAt` |
| `age` | Today minus `confirmedAt` |
| `queue` | evidence-pending → revisit → cold-start rank |

**On staleness.** Ratings never expire. Age is reported, and the human judges. Auto-expiry was
rejected because it would change a score with no human act behind it — the same failure mode as a
model-inferred rating — and because a uniform interval is wrong on its face when GV.OC-01 and
ID.AM-02 decay at completely different rates.

`revisit` provides what expiry was reaching for without the arbitrary interval: **a rating is
questioned when new material arrives about it, not when time passes.** It is a reporting flag and a
queue input only. **It does not affect scoring.**

## Reporting settings

```json
"reporting": { "scopeThresholdPct": 60, "ageThresholdDays": 180 }
```

`scopeThresholdPct` is measured on `assessed / inScope` — **not** on attribution. An
attribution-based guard would blank the headline on every Profile written before v2, which
is a regression dressed up as rigour. Attribution is reported as its own count instead.
````

Extend the "Derived-not-stored rule" list with `evidence states, revisit, age, the queue, the
scope guard, and the four-way coverage split`.

- [ ] **Step 2: `references/dashboards.md`**

Add three rules to "Rules that bind both dashboards":

```markdown
6. **Below the scope threshold, the headline is suppressed, not caveated.** A number with a
   warning beside it is still a number, and people read the number. The guard binds **both**
   dashboards — suppressing it in one and printing it in the other just moves the number one
   document over, where it gets quoted back at a board anyway.
7. **Confirmed, evidence-pending, unrated and n/a always appear together.** "Material on 41,
   confirmed on 24" is what makes a partial profile read as progress rather than abandonment.
   Showing confirmed alone makes an accreting profile look abandoned.
8. **Age travels with every set of ratings.** Ratings never expire, so the age readout is what
   makes never-expiring honest. Where no rating carries a confirmation date, say that in words —
   never render an empty box.
```

Add to the operational section, after "Gap table":

```markdown
### Age and revisits
Median and oldest `confirmedAt` age per Function from `evidence.age.byFunction`, plus a count over
`evidence.age.thresholdDays`. Then `evidence.revisit`: ratings with material newer than their
confirmation, each showing the confirmation date, the newer source date, and the intake ids.

### Coverage by source
One card per `intake.bySource` record: id, human-authored label, source date, recorded date and
recorder, and a chip per Subcategory coloured by its derived state. This is the payoff of the
source-keyed model and the only thing that answers "what did that review actually cover?"
```

Add to the executive section, after "Function-level rollup":

```markdown
### Scope guard
Where `evidence.scopeGuard.suppressed` is true, the headline programme figure is **replaced** by
`evidence.scopeGuard.statement`. Never printed with a caveat beside it.

### How much of this is known, and how old is it
The four-way split from `evidence.coverage.overall`, the age readout from `evidence.age.overall`,
and the revisit count — all four in the board view, not only in the operational tables.
```

- [ ] **Step 3: `references/assessment-and-review.md`**

Add a new workflow section before Workflow A:

````markdown
## Workflow 0 — Record a source (seconds, mid-conversation)

A fragment surfaces — a meeting, a note, a passing remark. Record where it came from and what it
bears on. Rate nothing.

```bash
python3 scripts/profile_analysis.py intake add acme.csfp \
  --label "architecture review with infra team" \
  --subjects ID.AM-01 ID.AM-02 ID.AM-03 \
  --source-date 2026-03-14 --recorded-by the maintainer
```

The label is a note **about** the source, not a quote **from** it, and it is human-authored or
human-confirmed. Those Subcategories now derive as evidence-pending. No rating exists yet.

## Workflow C — Confirm from the queue (its own session)

Entered when there is time to decide, never mid-conversation.

```bash
python3 scripts/profile_analysis.py queue acme.csfp --top 5
python3 scripts/profile_analysis.py set acme.csfp ID.AM-01 --current 2 \
  --source in-0001 --confirmed-by the maintainer \
  --rationale "March review: quarterly discovery scans across corporate IT; OT out of band."
```

Batches of at most five. Long confirmation runs are where rubber-stamping happens, and a
rubber-stamped rating is worse than an unrated one because it launders inference as judgment.

Where the material is thin, the right outcome is **a question to go ask**, not a rating. Record it
as an action and move on — leaving the Subcategory evidence-pending is a legitimate result.
````

- [ ] **Step 4: `SKILL.md`**

Update line 49 — `one local `.csfp` file (JSON, schema v1)` → `schema v2` — and extend that
paragraph:

```markdown
Everything persists in one local `.csfp` file (JSON, schema v2): the Profile definition, per-
Subcategory assessments **with their attribution**, an **intake log of sources**, an **append-only
history**, **named snapshots**, and the action plan. v1 files load unchanged and are stamped v2 on
first write. Dashboards are generated on demand and never stored — a rendered dashboard goes stale
the moment a rating moves. Full model: `references/schema.md`.
```

Update line 65's assertion count to whatever `self-test` now prints (178 if every task landed as
planned — **read it off the actual output, do not copy this number**).

Add a section after "Two core workflows":

````markdown
## Building a Profile from fragments

A Profile does not have to start with a sit-down assessment of 106 Subcategories. Record sources as
they arrive; confirm ratings later, when there is time to decide.

```bash
# Seconds, mid-conversation. Writes no ratings.
python3 scripts/profile_analysis.py intake add acme.csfp \
  --label "architecture review with infra team" --subjects ID.AM-01 ID.AM-02 ID.AM-03

# Its own session, when there is time to decide.
python3 scripts/profile_analysis.py queue acme.csfp --top 5
python3 scripts/profile_analysis.py set acme.csfp ID.AM-01 --current 2 \
  --source in-0001 --confirmed-by the maintainer --rationale "..."
```

**`set --current` refuses without `--source` and `--confirmed-by`.** Every confirmed rating answers
who confirmed it, when, and from what. The engine enforces that a rating carries attribution; it
cannot enforce that a human typed the number — that discipline is yours, and it is why the queue
never presents a tier to ratify.

`queue` returns evidence-pending first, then ratings that newer material has called into question,
then a cold-start ordering from `references/cold-start-rank.json` — **Cyber Aware Creations'
editorial judgment, not NIST's.** NIST publishes no Subcategory prioritization; say so if it goes
near an assessor.

**Ratings never expire.** Age is reported and you judge. A rating is questioned when new material
arrives about it, not when time passes.
````

Add to the reference table at the bottom:

```markdown
| `references/cold-start-rank.json` | Cold-start ordering — CAC editorial judgment, explicitly not NIST's |
| `examples/example-profile-v2.csfp` | v2 worked Profile: intake, partial confirmation, a revisit |
```

- [ ] **Step 5: Verify every documented command actually runs**

Run:
```bash
python3 skills/nist-csf/scripts/profile_analysis.py 2>&1 | head -40
python3 skills/nist-csf/scripts/profile_analysis.py self-test
```
Expected: the docstring lists `intake add`, `intake list` and `queue`, and the assertion count
matches what you wrote into `SKILL.md`.

- [ ] **Step 6: Commit**

```bash
git add skills/nist-csf/SKILL.md skills/nist-csf/references/
git commit -m "docs(nist-csf): schema v2, intake and confirmation workflows, evidence reporting"
```

---

## Task 14: Version bump and the full suite

**Files:**
- Modify: `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `.codex-plugin/plugin.json`

- [ ] **Step 1: Bump every version string**

Run: `grep -rn "0\.1\.8" . --exclude-dir=.git`
Expected: exactly four hits — `.claude-plugin/plugin.json:4`, `.claude-plugin/marketplace.json:8`, `.claude-plugin/marketplace.json:14`, `.codex-plugin/plugin.json:3`

Change all four to `0.2.0`. This is a feature increment with a schema change, so it is a minor bump, not a patch.

> An unchanged version makes `claude plugin update` a silent no-op and a stale cache has already cost one bad test run. Never ship a change without moving this number.

- [ ] **Step 2: Verify no version string was missed**

Run: `grep -rn "0\.1\.8" . --exclude-dir=.git; grep -rn "0\.2\.0" . --exclude-dir=.git`
Expected: no output from the first, four hits from the second

- [ ] **Step 3: Run the complete suite, exactly as CI does**

Run:
```bash
./skills/risk-register/evals/python-compat.sh /usr/bin/python3
python3 skills/risk-register/scripts/score_register.py self-test
python3 skills/nist-csf/scripts/profile_analysis.py validate
python3 skills/nist-csf/scripts/profile_analysis.py self-test
python3 skills/nist-csf/scripts/csfa_compat.py self-test
PY="$(command -v python3)" ./skills/risk-register/evals/board-safety.sh
./skills/risk-register/evals/responsive.sh
```
Expected: every command exits 0. `responsive.sh` must print its measured-pass line — a `SKIP` means it measured nothing and does not count.

- [ ] **Step 4: Confirm the success criteria, one at a time**

Run:
```bash
# 2 & 3: every confirmed rating answers who/when/from what; a bare set is refused.
python3 skills/nist-csf/scripts/profile_analysis.py analyze \
  skills/nist-csf/examples/example-profile-v2.csfp --today 2026-07-27 \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); c=d["evidence"]["coverage"]["overall"]; print("unattributed:", c["unattributed"], "of", c["confirmed"])'
# 4: a partial profile never shows a headline mean.
python3 skills/nist-csf/scripts/profile_analysis.py analyze \
  skills/nist-csf/examples/example-profile-v2.csfp --today 2026-07-27 \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["evidence"]["scopeGuard"]["suppressed"])'
# 5: Acme loads unchanged, byte-parity holds.
python3 skills/nist-csf/scripts/csfa_compat.py gaps \
  skills/nist-csf/examples/acme-manufacturing.csfa --out /tmp/acme2.csv
diff /tmp/acme2.csv skills/nist-csf/examples/acme-manufacturing-gaps.csv && echo "BYTE PARITY OK"
# 6: a profile spanning months reports its own age distribution.
python3 skills/nist-csf/scripts/profile_analysis.py analyze \
  skills/nist-csf/examples/example-profile-v2.csfp --today 2026-07-27 \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["evidence"]["age"]["overall"])'
```
Expected: `unattributed: 0 of 4`, `True`, `BYTE PARITY OK`, and an age dict with `oldestDays` over 365.

- [ ] **Step 5: Commit**

```bash
git add .claude-plugin/plugin.json .claude-plugin/marketplace.json .codex-plugin/plugin.json
git commit -m "chore: version the plugin 0.1.8 -> 0.2.0 for CSF evidence accretion"
```

---

## What this plan does not cover

Deliberately, per the design's non-goals — do not add any of it:

- Evidence artifact storage of any kind. No documents, screenshots, exports or transcripts.
- OSCAL, or any export format beyond `export-gaps`.
- Evidence sufficiency scoring in the audit sense.
- Time-based auto-expiry of ratings.
- Multi-user, access control, retention policy, litigation hold, integrity guarantees.
- Integrations, discovery, continuous monitoring.
- Any change to how scores are computed or how Tiers work.
- `risk-register` adopting the intake pattern — the seam is designed, the implementation is deferred.
- Engagement mode (consultant, bounded sprint) — deferred. The seam is `sourceDate` versus
  `recordedAt` plus the queue ordering; nothing here forecloses it.

These are the anti-GRC-platform boundary. They are load-bearing, not aspirational — most of them are
the exact obligations that would drag a local-file plugin into being a platform.

**Increment 2 (conversational)** — `SKILL.md` behaviour for proposing labels and subjects from
fragments, batched cold-start elicitation, confirmation ergonomics, anti-drift rules, and the
question-instead-of-rating affordance — is judgment-shaped and verified by eval rather than unit
test. It gets its own plan once this increment has landed and the command surface is fixed.
