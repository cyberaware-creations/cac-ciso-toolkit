# Cyber AI Profile Overlay (Increment 1 — mechanical) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Apply NIST IR 8596 Cyber AI Profile emphasis to an existing CSF 2.0 Profile as a disabled-by-default overlay — annotating in `advisory` mode and resequencing the gap table in `reorder` mode — without re-assessing anything and without moving a single computed number.

**Architecture:** An overlay, not a framework. `frameworkRef` stays `csf-2.0`; no Subcategories are added; the scoring path is untouched. A swappable bundled dataset carries per-Subcategory, per-Focus-Area priority with its own provenance; the store carries only enablement flags and the dataset version in force. The engine reads the dataset at analyze time. Two modes ship: `advisory` changes nothing computed, `reorder` changes only row order.

**Tech Stack:** Python 3.9 (stdlib only), in-script `_cmd_self_test` assertions, headless Chrome over CDP for the render gate.

**Supersedes:** `plans_cyber-ai-profile-overlay-implementation-plan-2026-07-27.md`, which targets a repository that does not exist. See `2026-07-28-cyber-ai-overlay-reconciliation.md` for the full delta. The **design** (`strategy_cyber-ai-profile-overlay-design-2026-07-27.md` rev B) survives intact apart from the two decisions below.

---

## Decisions taken, and why

### 1. `floor` mode is cut from v1

The design maps proposed priority **1→4**. The native scale is **0–3** and the engine refuses a 4:

```
error: --target 4 is outside the scale 0..3
```

Worse than a clamp: `settings.scale` is **per-Profile**. Native Profiles are 0–3; Profiles converted from the web tool keep 0–4, deliberately unrescaled, because `references/scale-and-scoring.md` states there is no honest mapping between them. A fixed priority→target table would mean different things on two Profiles that both load in this tool.

`advisory` + `reorder` deliver the design's stated value, and `reorder` is already the intended default. `floor` is explicitly a CAC interpretation rather than NIST doctrine, so deferring it costs nothing and removes the only mechanism that moves someone's numbers on preliminary-draft authority.

**Do not implement `floor`, `effectiveTarget`, or `targetRaisedBy` in this increment.** Accept `--mode floor` nowhere; the mode enum is `{advisory, reorder}`. If a later increment adds it, the eventual shape is to refuse `floor` on non-native scales rather than to rescale.

### 2. `reorder` reorders `gaps` only — never `queue` or `elicit`

The design predates both. As of v0.3.x there are two orderings:

- **`gaps`** — the prioritized gap table, `(-prioritizedGapScore, subcategoryId)`. This is what the overlay reorders.
- **`queue`** — *what to confirm next*: evidence-pending → revisit → cold-start, the last band ordered by `references/cold-start-rank.json`.

The queue answers "what do I have material for?", which is an evidence question. The overlay has nothing to say about it, and layering NIST IR 8596 priority over CAC's own editorial cold-start ranking would put two editorial orderings in silent competition. The same applies to `references/elicitation.json`.

**This is a decision, not an omission, and `references/cyber-ai-overlay.md` must say so.**

### 3. Build the mechanism against a test fixture, not the real dataset

The 318 hand-verified priority values are the most expensive and least stable part of this work, and the source status is unverified (T1). So the schema, validator, commands and modes are built and tested against a small checked-in **fixture** dataset. The real dataset lands in T9. If a newer IR 8596 draft appears, only T8–T9 are redone.

---

## Facts verified against the tree on 2026-07-28

Do not re-derive these. The superseded plan got every one of them wrong.

| Fact | Value |
|---|---|
| Engine | `skills/nist-csf/scripts/profile_analysis.py` (~2700 lines, stdlib only) |
| Tests | `_cmd_self_test` **inside** that file, run as `profile_analysis.py self-test`. There is no `self_test.py`. Nested helpers `ok`, `eq`, `close`; locals `core`, `index`. Currently 351 checks. |
| Renderers | **Two**: `renderers/render_operational.py`, `renderers/render_executive.py`, sharing `renderers/_common.py`. There is no `render_report.py`. |
| Store format | `.csfp`. `.csfa` is the **web-tool export**, read by the frozen `scripts/csfa_compat.py` under a gaps-CSV byte-parity contract. Never write overlay state to a `.csfa`. |
| Store shape | top-level `profile`, `assessments`, `history`, `snapshots`, `actionItems` (a **flat list**), `intake`, `schemaVersion` |
| `schemaVersion` | the **string** `"2.0"`. `SUPPORTED_SCHEMA = {"1.0", "2.0"}`. A comparison against int `2` fails silently. |
| Normalization | `load_store()` — one entry point, already extended once by the accretion work. Extend it; do not add a second. |
| Unknown top-level keys | `check_store` does not reject them, so `overlays` is additive-safe. Assert this rather than assume it. |
| Flag parser | `parse_flags(args) -> (pos, opt)`. Multi-value flags are **space-separated**: `--x a b` → `['a','b']`. Use `_list(opt.get("focus"))`. There is no comma splitting — `--focus secure,thwart` would parse as one string. |
| Store argument | **positional**, via `_require_store(pos, usage)`. There is no `--store` flag anywhere. |
| Gap builder | `compute_gaps(assessments, settings, index)`, sorting `(-prioritizedGapScore, subcategoryId)` at line ~448 |
| History | `append_history(store, etype, *, rationale=None, actor=None, ts=None, ...)` |
| Reference paths | module constants from `_SKILL_ROOT`: `DEFAULT_CORE`, `DEFAULT_GUIDANCE`, `DEFAULT_COLD_START_RANK`, `DEFAULT_ELICITATION`. There is no `_REF_DIR`. |
| Brand tokens | `assets/brand.md`. Dashboard spec is `references/dashboards.md`. There is no `brand.md` or `report-layout.md` under `references/`. |
| Render gate | `skills/risk-register/evals/responsive.sh` — headless Chrome over CDP, width **and** WCAG AA contrast on resolved layouts, 9 pages. There is no `visual_check.js`. |
| Footer seam | `_common.Context.footer(extra="")` joins bits with ` · `. This is where the provenance line attaches. |
| Python floor | 3.9. `from __future__ import annotations` is at line 55, so PEP 604 (`str \| None`) is safe. No PEP 701 f-strings. |
| `tools/` | at the **repo root**, not inside the skill |

---

## File Structure

**Create:**

| File | Responsibility |
|---|---|
| `skills/nist-csf/references/cyber-ai-profile.json` | The dataset: per-Subcategory, per-Focus-Area priority + sentinel flag, with provenance header |
| `skills/nist-csf/references/cyber-ai-overlay.md` | Overlay contract: mode semantics, effective-priority rule, the queue decision, and the draft disclaimer |
| `skills/nist-csf/examples/fixture-cyber-ai.json` | Small dataset fixture the engine is tested against |
| `tools/extract_cyber_ai.py` | One-time-per-draft extraction helper with a coverage report |

**Modify:** `scripts/profile_analysis.py` · `renderers/_common.py` · `renderers/render_operational.py` · `renderers/render_executive.py` · `SKILL.md` · `references/schema.md` · `references/dashboards.md` · `assets/brand.md` · `README.md` · the four version files

**Deliberately not touched:** the scoring path (`gap_of`, `prioritized_score`, `_coverage_of`), `queue`, `elicit`, `derive_evidence`, `csfa_compat.py`. If a task makes you want to change one, stop and report.

---

## Task 1: Source verification gate

**Files:** none — produces `docs/superpowers/notes/2026-XX-XX-ir8596-status.md`

**This gates T8 and T9 only.** T2–T7 and T10 may proceed regardless, because they are built against the fixture.

- [ ] **Step 1: Establish the current status of IR 8596**

The design was verified 2026-07-27 against an Initial Preliminary Draft published 2025-12-16, comment period closed 2026-01-30. On 2026-07-28 three NIST URLs returned **404**:

```
https://csrc.nist.gov/pubs/ir/8596
https://csrc.nist.gov/publications/detail/nistir/8596/draft
https://csrc.nist.gov/projects/cyber-ai-profile
```

Find the publication. Try the CSRC publication search, the NCCoE project pages, and `doi.org/10.6028/NIST.IR.8596.iprd`. Record what you actually reached, including failures.

- [ ] **Step 2: Write the note**

It must state: the newest version found, its date and stage; whether it differs from `8596-iprd-2025-12-16`; and the exact URLs tried with their outcomes.

**If a newer draft exists, STOP and report.** The priorities may have moved and T9 is 318 hand-verified values. Do not extract from a superseded draft.

**If nothing can be reached at all**, say so plainly and stop before T8. Do not populate a dataset from memory of a document — that is the failure mode the whole provenance design exists to prevent.

- [ ] **Step 3: Commit the note**

```bash
git add docs/superpowers/notes/
git commit -m "docs: record IR 8596 source status before building the overlay dataset"
```

---

## Task 2: Dataset schema, validator, and fixture

**Files:** Modify `scripts/profile_analysis.py`; create `skills/nist-csf/examples/fixture-cyber-ai.json`

- [ ] **Step 1: Write the failing test**

Add to `_cmd_self_test`, near the other reference-data assertions:

```python
    # --- cyber-ai overlay dataset -----------------------------------------
    # Validated before it is populated, so an extraction defect surfaces here
    # rather than as a wrong priority in a board pack.
    _ds = load_overlay_dataset(os.path.join(_SKILL_ROOT, "examples",
                                            "fixture-cyber-ai.json"))
    eq(_ds["datasetVersion"], "fixture-1", "the fixture dataset loads")
    eq(sorted(_ds["focusAreas"]), ["defend", "secure", "thwart"],
       "three focus areas, always")

    def _bad(mutate, label):
        import copy as _copy
        broken = _copy.deepcopy(_ds)
        mutate(broken)
        try:
            validate_overlay_dataset(broken, index)
        except ValueError:
            ok(True, label)
        else:
            ok(False, label)

    _bad(lambda d: d.pop("datasetVersion"), "a dataset with no version is refused")
    _bad(lambda d: d.pop("sourceStatus"), "a dataset with no source status is refused")
    _bad(lambda d: d["subcategories"]["ID.AM-01"]["secure"].__setitem__("priority", 0),
         "priority 0 is refused")
    _bad(lambda d: d["subcategories"]["ID.AM-01"]["secure"].__setitem__("priority", 4),
         "priority 4 is refused")
    _bad(lambda d: d["subcategories"].__setitem__("XX.YY-99", {}),
         "a Subcategory outside the Core is refused")
    _bad(lambda d: d["subcategories"]["ID.AM-01"].pop("defend"),
         "a Subcategory missing a focus area is refused")
    _bad(lambda d: d["subcategories"]["ID.AM-01"]["secure"]
         .__setitem__("standardPracticesApply", "yes"),
         "a non-boolean sentinel is refused")
```

- [ ] **Step 2: Run it to watch it fail**

```bash
cd ~/Documents/GitHub/cac-ciso-toolkit/skills/nist-csf
python3 scripts/profile_analysis.py self-test
```

Expected: `NameError: name 'load_overlay_dataset' is not defined`.

- [ ] **Step 3: Write the fixture**

`skills/nist-csf/examples/fixture-cyber-ai.json`. Six Subcategories is enough to exercise every rule, and they are chosen so `reorder` has something to prove: `ID.AM-01` is priority 1 in secure but 3 in thwart, so effective priority moves with Focus Area selection.

```json
{
  "datasetVersion": "fixture-1",
  "sourceStatus": "Fixture — not NIST content",
  "sourcePublished": "2026-07-28",
  "sourceUrl": "https://example.invalid/fixture",
  "note": "Test fixture for the overlay engine. Priorities here are invented and bear no relation to NIST IR 8596. The shipped dataset is references/cyber-ai-profile.json.",
  "focusAreas": ["secure", "defend", "thwart"],
  "subcategories": {
    "ID.AM-01": {
      "secure": {"priority": 1, "standardPracticesApply": false},
      "defend": {"priority": 2, "standardPracticesApply": false},
      "thwart": {"priority": 3, "standardPracticesApply": true}
    },
    "ID.AM-02": {
      "secure": {"priority": 2, "standardPracticesApply": false},
      "defend": {"priority": 3, "standardPracticesApply": true},
      "thwart": {"priority": 3, "standardPracticesApply": true}
    },
    "PR.AA-01": {
      "secure": {"priority": 3, "standardPracticesApply": true},
      "defend": {"priority": 1, "standardPracticesApply": false},
      "thwart": {"priority": 2, "standardPracticesApply": false}
    },
    "PR.DS-01": {
      "secure": {"priority": 1, "standardPracticesApply": false},
      "defend": {"priority": 3, "standardPracticesApply": true},
      "thwart": {"priority": 3, "standardPracticesApply": true}
    },
    "DE.CM-01": {
      "secure": {"priority": 3, "standardPracticesApply": true},
      "defend": {"priority": 1, "standardPracticesApply": false},
      "thwart": {"priority": 1, "standardPracticesApply": false}
    },
    "GV.OC-01": {
      "secure": {"priority": 3, "standardPracticesApply": true},
      "defend": {"priority": 3, "standardPracticesApply": true},
      "thwart": {"priority": 3, "standardPracticesApply": true}
    }
  }
}
```

- [ ] **Step 4: Implement loader and validator**

Add the path constant beside the others (~line 122):

```python
DEFAULT_CYBER_AI = os.path.join(_SKILL_ROOT, "references", "cyber-ai-profile.json")
```

Then, near the other reference loaders:

```python
OVERLAY_FOCUS_AREAS = ("secure", "defend", "thwart")
OVERLAY_MODES = ("advisory", "reorder")   # `floor` is deliberately absent; see
                                          # references/cyber-ai-overlay.md


def validate_overlay_dataset(data: dict, index: dict) -> dict:
    """Assert a Cyber AI Profile dataset is well formed. Raises ValueError on any defect.

    Well formed is not the same as correct. This catches an extraction that
    dropped a cell or mangled a number; it cannot catch a priority transcribed
    as 2 when the source says 1. That is what the spot-check in T9 is for.
    """
    for field in ("datasetVersion", "sourceStatus", "sourcePublished", "sourceUrl"):
        if not str(data.get(field) or "").strip():
            raise ValueError(
                f"overlay dataset is missing {field!r}. Every artifact carrying "
                f"overlay output has to state where the data came from and what "
                f"status it has; a dataset that cannot say is not usable.")
    if list(data.get("focusAreas") or []) != list(OVERLAY_FOCUS_AREAS):
        raise ValueError(
            f"overlay dataset focusAreas must be exactly "
            f"{list(OVERLAY_FOCUS_AREAS)}, got {data.get('focusAreas')!r}.")
    subs = data.get("subcategories")
    if not isinstance(subs, dict) or not subs:
        raise ValueError("overlay dataset has no subcategories.")
    for sid, areas in sorted(subs.items()):
        if sid not in index:
            raise ValueError(
                f"overlay dataset references {sid!r}, which is not a Subcategory "
                f"of {FRAMEWORK_REF}.")
        for area in OVERLAY_FOCUS_AREAS:
            cell = areas.get(area)
            if not isinstance(cell, dict):
                raise ValueError(f"{sid} has no {area!r} entry.")
            pri = cell.get("priority")
            if pri not in (1, 2, 3):
                raise ValueError(
                    f"{sid}.{area}.priority is {pri!r}; NIST proposes 1 (High), "
                    f"2 (Moderate) or 3 (Foundational) and nothing else.")
            if not isinstance(cell.get("standardPracticesApply"), bool):
                raise ValueError(
                    f"{sid}.{area}.standardPracticesApply must be true or false, "
                    f"got {cell.get('standardPracticesApply')!r}.")
    return data


def load_overlay_dataset(path: str | None = None, index: dict | None = None) -> dict:
    """Load and validate the Cyber AI Profile dataset.

    Does NOT degrade when the file is missing, unlike load_cold_start_rank. An
    absent rank means the queue falls back to framework order and is still
    correct; an absent overlay dataset means the overlay silently annotates
    nothing while reporting itself enabled, which is a lie about the Profile.
    """
    with open(path or DEFAULT_CYBER_AI, encoding="utf-8") as fh:
        data = json.load(fh)
    return validate_overlay_dataset(data, index if index is not None
                                    else index_subcategories(load_core()))
```

- [ ] **Step 5: Run the tests**

```bash
python3 scripts/profile_analysis.py self-test
```

Expected: PASS, count above 351. Report the new total.

- [ ] **Step 6: Prove a validator assertion can fail**

```bash
cd ~/Documents/GitHub/cac-ciso-toolkit/skills/nist-csf
python3 - <<'EOF'
import json, sys
sys.path.insert(0, "scripts")
import profile_analysis as p
d = json.load(open("examples/fixture-cyber-ai.json"))
idx = p.index_subcategories(p.load_core())
d["subcategories"]["ID.AM-01"]["secure"]["priority"] = 4
try:
    p.validate_overlay_dataset(d, idx)
    print("DEFECT: priority 4 was accepted")
except ValueError as e:
    print("refused as expected:", e)
EOF
```

Expected: refused. If accepted, the validator is wrong.

- [ ] **Step 7: Commit**

```bash
cd ~/Documents/GitHub/cac-ciso-toolkit
./skills/risk-register/evals/python-compat.sh
git add skills/nist-csf/scripts/profile_analysis.py skills/nist-csf/examples/fixture-cyber-ai.json
git commit -m "feat(nist-csf): cyber-ai overlay dataset schema and validator"
```

---

## Task 3: The store block

**Files:** Modify `scripts/profile_analysis.py`; modify `references/schema.md`

- [ ] **Step 1: Write the failing test**

```python
    # --- overlay store block ----------------------------------------------
    _ov_store = os.path.join(_tmp, "overlay.csfp")
    _cmd_init(["--name", "Overlay Fixture", "--out", _ov_store,
               "--ts", "2026-01-01T00:00:00Z"])
    _ovs = load_store(_ov_store)
    eq(_ovs["overlays"]["cyberAi"]["enabled"], False,
       "a fresh Profile normalizes with the overlay disabled")
    eq(_ovs["overlays"]["cyberAi"]["focusAreas"], [],
       "and with no focus areas selected")
    eq(_ovs["overlays"]["cyberAi"]["mode"], "advisory",
       "and the inert mode, so a normalization bug cannot silently reorder")

    # A v1 store — no overlays, no intake — must still load.
    _v1 = json.load(open(FIXTURE))
    _v1_path = os.path.join(_tmp, "v1.csfp")
    _v1.pop("overlays", None)
    with open(_v1_path, "w") as _fh:
        json.dump(_v1, _fh)
    ok(load_store(_v1_path)["overlays"]["cyberAi"]["enabled"] is False,
       "a store predating the overlay normalizes to disabled, never to enabled")

    eq(check_store(load_store(_ov_store), index), [],
       "an overlays block is not a structural problem")
```

`_tmp` may not be in scope at your insertion point — check the surrounding code and wrap in `with tempfile.TemporaryDirectory() as _tmp:` if needed, as the elicit block does.

- [ ] **Step 2: Run it to verify it fails**

Expected: `KeyError: 'overlays'`.

- [ ] **Step 3: Extend `load_store` normalization**

Find where `load_store` does `store.setdefault("intake", [])` and add beside it:

```python
    # Overlay state. Defaults are inert on purpose: a normalization bug should
    # produce a Profile that reports nothing, never one that silently
    # resequences a board's top five.
    overlays = store.setdefault("overlays", {})
    cyber = overlays.setdefault("cyberAi", {})
    cyber.setdefault("enabled", False)
    cyber.setdefault("focusAreas", [])
    cyber.setdefault("mode", "advisory")
    cyber.setdefault("datasetVersion", None)
```

- [ ] **Step 4: Run the tests**

```bash
python3 scripts/profile_analysis.py self-test
```

Expected: PASS.

- [ ] **Step 5: Document it in `references/schema.md`**

Add a section after the intake section:

````markdown
## `overlays` — reweighting, not re-assessing

```json
"overlays": {
  "cyberAi": {
    "enabled": false,
    "focusAreas": [],
    "mode": "advisory",
    "datasetVersion": null
  }
}
```

An overlay applies emphasis from another published profile to the **same** 106 Subcategories.
It adds none, changes no framework, and creates no second assessment surface. `frameworkRef`
stays `csf-2.0`.

- `focusAreas` ⊆ `{secure, defend, thwart}` — NIST IR 8596's three Focus Areas, independently
  selectable. Effective priority for a Subcategory is the **minimum** (most urgent) proposed
  priority across the selected areas, so deselecting an area can only relax, never tighten.
- `mode` ∈ `{advisory, reorder}`. `advisory` changes nothing computed. `reorder` changes only
  the order of the `gaps` table and anything derived from its head. **No mode changes a score,
  a target, a gap, a coverage figure, or a Tier.**
- `datasetVersion` records which dataset produced the last analysis, and is stamped into
  snapshots. A dataset swap is a file replacement plus a version bump; stores stamped with an
  older version keep reporting that version until re-analyzed.

Defaults are inert: absent `overlays` normalizes to disabled, no areas, `advisory`. A Profile
that has not opted in is never perturbed.

Enable and disable append a `history` event. The change alters what every report says.
````

- [ ] **Step 6: Commit**

```bash
git add skills/nist-csf/scripts/profile_analysis.py skills/nist-csf/references/schema.md
git commit -m "feat(nist-csf): additive overlays block, inert by default"
```

---

## Task 4: `overlay` commands

**Files:** Modify `scripts/profile_analysis.py`

Three subcommands, matching the `intake` / `action` shape: `overlay list <store>`, `overlay enable <store> --focus secure thwart [--mode advisory|reorder]`, `overlay disable <store>`.

**Flags are space-separated** — `--focus secure thwart`, not `secure,thwart`. `parse_flags` does not split on commas, so a comma form would silently become one unrecognised area.

- [ ] **Step 1: Write the failing test**

```python
    # --- overlay commands --------------------------------------------------
    _cmd_overlay(["enable", _ov_store, "--focus", "secure", "thwart",
                  "--ts", "2026-01-02T00:00:00Z"])
    _en = load_store(_ov_store)["overlays"]["cyberAi"]
    eq(_en["enabled"], True, "enable turns the overlay on")
    eq(_en["focusAreas"], ["secure", "thwart"], "and records the selected areas")
    eq(_en["mode"], "reorder",
       "defaulting to reorder — the honest use of a sequencing signal")
    ok(_en["datasetVersion"], "and stamps the dataset version in force")
    eq([e["type"] for e in load_store(_ov_store)["history"]][-1], "overlay-enabled",
       "enabling writes a history event; it changes what every report says")

    try:
        _cmd_overlay(["enable", _ov_store, "--focus", "secure", "--mode", "floor",
                      "--ts", "2026-01-03T00:00:00Z"])
        ok(False, "floor mode is refused")
    except ValueError as _e:
        ok("floor" in str(_e) and "scale" in str(_e),
           "floor mode is refused, naming the scale as the reason")

    try:
        _cmd_overlay(["enable", _ov_store, "--focus", "secure,thwart",
                      "--ts", "2026-01-03T00:00:00Z"])
        ok(False, "a comma-joined focus list is refused")
    except ValueError as _e:
        ok("secure,thwart" in str(_e),
           "a comma-joined focus list is refused by name, not silently dropped")

    try:
        _cmd_overlay(["enable", _ov_store, "--ts", "2026-01-03T00:00:00Z"])
        ok(False, "enable with no --focus is refused")
    except ValueError:
        ok(True, "enable with no --focus is refused")

    _cmd_overlay(["disable", _ov_store, "--ts", "2026-01-04T00:00:00Z"])
    _dis = load_store(_ov_store)["overlays"]["cyberAi"]
    eq(_dis["enabled"], False, "disable turns it off")
    eq(_dis["focusAreas"], ["secure", "thwart"],
       "and preserves the selection, so re-enabling is one word")
```

- [ ] **Step 2: Run it to verify it fails**

Expected: `NameError: name '_cmd_overlay' is not defined`.

- [ ] **Step 3: Implement**

```python
def _cmd_overlay(argv):
    usage = ("usage: overlay list <store.csfp>\n"
             "       overlay enable <store.csfp> --focus secure defend thwart "
             "[--mode advisory|reorder]\n"
             "       overlay disable <store.csfp>")
    if not argv:
        raise ValueError(usage)
    sub, rest = argv[0], argv[1:]
    if sub not in ("list", "enable", "disable"):
        raise ValueError(usage)
    pos, opt = parse_flags(rest)
    path = _require_store(pos, usage)
    store = load_store(path)
    core = load_core()
    index = index_subcategories(core)
    dataset = load_overlay_dataset(index=index)
    cfg = store["overlays"]["cyberAi"]

    if sub == "list":
        print(f"cyber-ai — NIST Cyber AI Profile overlay")
        print(f"  dataset      {dataset['datasetVersion']}")
        print(f"  source       {dataset['sourceStatus']}, published "
              f"{dataset['sourcePublished']}")
        print(f"  {dataset['sourceUrl']}")
        print(f"  focus areas  {', '.join(dataset['focusAreas'])}")
        print("")
        if cfg["enabled"]:
            print(f"  ENABLED  areas: {', '.join(cfg['focusAreas']) or 'none'}"
                  f"  mode: {cfg['mode']}  dataset in force: "
                  f"{cfg['datasetVersion']}")
        else:
            print("  disabled. This Profile is not affected by the overlay.")
        print("")
        print("Priority indicates sequencing, not required maturity. Enabling adds no "
              "assessment work — the overlay reweights the existing 106 Subcategories "
              "and adds none.")
        return

    ts = _s(opt.get("ts")) if opt.get("ts") else _now()

    if sub == "disable":
        was = cfg["enabled"]
        cfg["enabled"] = False
        if was:
            append_history(store, "overlay-disabled", ts=ts,
                           actor=_s(opt.get("actor")) if opt.get("actor") else None,
                           rationale="cyber-ai overlay disabled")
        save_store(path, store)
        print("cyber-ai overlay disabled. Focus areas and mode kept, so re-enabling "
              "is one command.")
        return

    focus = _list(opt.get("focus"))
    if not focus:
        raise ValueError(
            "--focus is required. Which Focus Areas apply?\n"
            "  secure  — you build or deploy AI systems\n"
            "  defend  — your security programme uses AI\n"
            "  thwart  — attackers use AI against you. This applies whether or not "
            "you use AI at all.\n\n" + usage)
    bad = [f for f in focus if f not in OVERLAY_FOCUS_AREAS]
    if bad:
        hint = ""
        if any("," in b for b in bad):
            hint = ("\nFocus areas are separated by spaces, not commas: "
                    "--focus secure thwart")
        raise ValueError(
            f"Unknown focus area(s) {', '.join(repr(b) for b in bad)}. "
            f"Valid: {', '.join(OVERLAY_FOCUS_AREAS)}.{hint}")

    mode = _s(opt.get("mode")) if opt.get("mode") else "reorder"
    if mode == "floor":
        raise ValueError(
            "--mode floor is not available. It would map NIST proposed priority onto "
            "a target, and the priority-to-target mapping is scale-dependent: this "
            "Profile's scale is per-Profile settings, native Profiles run 0-3 and "
            "converted web-tool Profiles run 0-4, and there is no honest mapping "
            "between them (references/scale-and-scoring.md). Use reorder, which "
            "sequences the work without asserting a maturity level NIST does not "
            "claim.")
    if mode not in OVERLAY_MODES:
        raise ValueError(f"--mode must be one of {', '.join(OVERLAY_MODES)}, "
                         f"got {mode!r}.")

    cfg["enabled"] = True
    cfg["focusAreas"] = [a for a in OVERLAY_FOCUS_AREAS if a in focus]
    cfg["mode"] = mode
    cfg["datasetVersion"] = dataset["datasetVersion"]
    append_history(store, "overlay-enabled", ts=ts,
                   actor=_s(opt.get("actor")) if opt.get("actor") else None,
                   rationale=f"cyber-ai overlay enabled: "
                             f"{', '.join(cfg['focusAreas'])}, mode {mode}")
    save_store(store, path, ts)
    print(f"cyber-ai overlay enabled — {', '.join(cfg['focusAreas'])}, mode {mode}, "
          f"dataset {cfg['datasetVersion']}.")
    print("No assessment work is added. The overlay reweights the existing 106 "
          "Subcategories.")
    if mode == "reorder":
        print("The gap table will be ordered by AI priority. Scores, targets, gaps "
              "and coverage are unchanged.")
```

Verified signatures: `save_store(store, path, ts)` — **store first, and it takes the timestamp**; `_now()`; `_s(v)`; `_list(v)`; `FIXTURE` is `examples/example-profile.csfp`. Register `overlay` in the dispatch table beside `intake`, and add to the usage banner:

```
  overlay      list|enable|disable <store.csfp> [--focus A B] [--mode advisory|reorder]
```

- [ ] **Step 4: Run the tests, then exercise it by hand**

```bash
python3 scripts/profile_analysis.py self-test
T=$(mktemp -d) && cp examples/example-profile-v2.csfp $T/t.csfp
python3 scripts/profile_analysis.py overlay list $T/t.csfp
python3 scripts/profile_analysis.py overlay enable $T/t.csfp --focus secure thwart
python3 scripts/profile_analysis.py overlay list $T/t.csfp
python3 scripts/profile_analysis.py overlay enable $T/t.csfp --focus secure,thwart
python3 scripts/profile_analysis.py overlay enable $T/t.csfp --focus secure --mode floor
rm -rf $T
```

Read the output. The comma form and `floor` must each fail with a message that explains rather than just refusing.

**Note:** until T9 lands, `load_overlay_dataset()` reads `references/cyber-ai-profile.json`, which does not exist yet. For this task, temporarily point `DEFAULT_CYBER_AI` at the fixture **or** copy the fixture to the real path as a placeholder — and record which you did, because T9 must overwrite it.

- [ ] **Step 5: Commit**

```bash
git add skills/nist-csf/scripts/profile_analysis.py
git commit -m "feat(nist-csf): overlay list/enable/disable, floor refused with its reason"
```

---

## Task 5: Overlay resolution

**Files:** Modify `scripts/profile_analysis.py`

- [ ] **Step 1: Write the failing test**

```python
    # --- overlay resolution ------------------------------------------------
    _fx = load_overlay_dataset(os.path.join(_SKILL_ROOT, "examples",
                                            "fixture-cyber-ai.json"), index)
    _on = {"enabled": True, "focusAreas": ["secure", "thwart"], "mode": "reorder"}

    eq(resolve_overlay("ID.AM-01", _on, _fx)["effectivePriority"], 1,
       "effective priority is the MINIMUM across selected areas — most urgent wins")
    eq(resolve_overlay("DE.CM-01", _on, _fx)["effectivePriority"], 1,
       "and it finds the urgent one whichever area carries it")
    eq(resolve_overlay("GV.OC-01", _on, _fx)["effectivePriority"], 3,
       "a Subcategory foundational everywhere resolves to 3")

    _one = {"enabled": True, "focusAreas": ["thwart"], "mode": "reorder"}
    eq(resolve_overlay("ID.AM-01", _one, _fx)["effectivePriority"], 3,
       "deselecting an area can only relax — ID.AM-01 is 1 in secure, 3 in thwart")
    ok(resolve_overlay("ID.AM-01", _one, _fx)["effectivePriority"]
       >= resolve_overlay("ID.AM-01", _on, _fx)["effectivePriority"],
       "deselecting never tightens, for any Subcategory")

    ok(resolve_overlay("ID.AM-01", {"enabled": False, "focusAreas": ["secure"],
                                    "mode": "reorder"}, _fx) is None,
       "disabled resolves to None, never to a default priority")
    ok(resolve_overlay("RC.RP-01", _on, _fx) is None,
       "a Subcategory absent from the dataset resolves to None")

    eq(resolve_overlay("GV.OC-01", _on, _fx)["sentinelAreas"], ["secure", "thwart"],
       "the 'standard practices apply' sentinel is reported per selected area")
    eq(resolve_overlay("ID.AM-01", _on, _fx)["sentinelAreas"], ["thwart"],
       "and only for the areas where the source said it")
    ok("perArea" in resolve_overlay("ID.AM-01", _on, _fx),
       "per-area priorities are carried through for display")
    ok(all("target" not in r and "effectiveTarget" not in r
           for r in [resolve_overlay("ID.AM-01", _on, _fx)]),
       "resolution never touches targets — floor mode is not in this increment")
```

- [ ] **Step 2: Run it to verify it fails**

Expected: `NameError: name 'resolve_overlay' is not defined`.

- [ ] **Step 3: Implement**

```python
def resolve_overlay(sub_id: str, cfg: dict, dataset: dict) -> dict | None:
    """What the overlay says about one Subcategory, or None if it says nothing.

    Returns None — never a default — when the overlay is disabled, no areas are
    selected, or the Subcategory is absent from the dataset. A default would let
    an absent entry silently participate in ordering.

    effectivePriority is the MINIMUM across selected areas because NIST's 1/2/3
    is High/Moderate/Foundational: 1 is the most urgent. Minimum therefore means
    "most urgent area wins", and deselecting an area can only relax the result.
    """
    if not cfg or not cfg.get("enabled"):
        return None
    areas = [a for a in cfg.get("focusAreas") or [] if a in OVERLAY_FOCUS_AREAS]
    if not areas:
        return None
    entry = (dataset.get("subcategories") or {}).get(sub_id)
    if not entry:
        return None
    per_area = {a: entry[a]["priority"] for a in areas if a in entry}
    if not per_area:
        return None
    return {
        "effectivePriority": min(per_area.values()),
        "perArea": per_area,
        "sentinelAreas": [a for a in areas
                          if entry.get(a, {}).get("standardPracticesApply")],
    }
```

- [ ] **Step 4: Run the tests**

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add skills/nist-csf/scripts/profile_analysis.py
git commit -m "feat(nist-csf): overlay resolution — minimum across selected focus areas"
```

---

## Task 6: `advisory` mode, and the parity assertion

**Files:** Modify `scripts/profile_analysis.py`

This is the task that protects every existing user. **Advisory must change nothing computed.**

- [ ] **Step 1: Write the failing test**

```python
    # --- advisory mode changes nothing computed ---------------------------
    # The acceptance bar. If enabling the overlay in advisory mode can move a
    # number, the overlay is a defect regardless of how useful it is.
    _par = os.path.join(_tmp, "parity.csfp")
    _copy_fixture(FIXTURE, _par)
    _base_out = os.path.join(_tmp, "base.json")
    _cmd_analyze([_par, "--today", "2026-07-28", "--out", _base_out])
    with open(_base_out) as _fh:
        _base = json.load(_fh)

    _cmd_overlay(["enable", _par, "--focus", "secure", "defend", "thwart",
                  "--mode", "advisory", "--ts", "2026-02-01T00:00:00Z"])
    _adv_out = os.path.join(_tmp, "adv.json")
    _cmd_analyze([_par, "--today", "2026-07-28", "--out", _adv_out])
    with open(_adv_out) as _fh:
        _adv = json.load(_fh)

    for _k in ("coverage", "completeness", "tiers", "attention", "queue",
               "evidence", "playbook", "tracked"):
        eq(_adv[_k], _base[_k],
           f"advisory mode leaves analyze.{_k} byte-identical")
    eq([ (r["subcategoryId"], r["current"], r["target"], r["gap"],
           r["prioritizedGapScore"]) for r in _adv["gaps"] ],
       [ (r["subcategoryId"], r["current"], r["target"], r["gap"],
           r["prioritizedGapScore"]) for r in _base["gaps"] ],
       "advisory mode leaves every gap value AND the row order untouched")
    ok("overlay" in _adv, "advisory mode adds an overlay block")
    eq(_adv["overlay"]["mode"], "advisory", "which states the mode")
    ok(_adv["overlay"]["datasetVersion"], "and the dataset version")
    ok("overlay" not in _base, "a disabled Profile carries no overlay block at all")
```

`shutil` is **not** imported in this module (only `copy`). Define a tiny local helper beside the
test block rather than adding an import:

```python
    def _copy_fixture(src, dst):
        with open(src) as _s, open(dst, "w") as _d:
            _d.write(_s.read())
```

- [ ] **Step 2: Run it to verify it fails**

Expected: `KeyError: 'overlay'`.

- [ ] **Step 3: Implement**

In `_cmd_analyze`, after the gaps are computed and before the output dict is assembled:

```python
    cfg = store["overlays"]["cyberAi"]
    overlay_block = None
    if cfg.get("enabled"):
        ov_data = load_overlay_dataset(index=index)
        for row in gaps:
            res = resolve_overlay(row["subcategoryId"], cfg, ov_data)
            if res:
                row["overlay"] = res
        counts = {a: {1: 0, 2: 0, 3: 0} for a in cfg["focusAreas"]}
        for sid, entry in (ov_data.get("subcategories") or {}).items():
            for a in cfg["focusAreas"]:
                if a in entry:
                    counts[a][entry[a]["priority"]] += 1
        overlay_block = {
            "id": "cyber-ai",
            "mode": cfg["mode"],
            "focusAreas": list(cfg["focusAreas"]),
            "datasetVersion": ov_data["datasetVersion"],
            "sourceStatus": ov_data["sourceStatus"],
            "sourcePublished": ov_data["sourcePublished"],
            "sourceUrl": ov_data["sourceUrl"],
            "byFocusArea": counts,
            # Said once, here, so every renderer projects the same sentence
            # instead of composing its own.
            "provenance": (f"Cyber AI Profile overlay · dataset "
                           f"{ov_data['datasetVersion']} · "
                           f"{ov_data['sourceStatus']}, "
                           f"{ov_data['sourcePublished']}"),
            "orderingNote": ("Gap order is AI-prioritized, not gap-severity order."
                             if cfg["mode"] == "reorder" else
                             "Gap order is unchanged; the overlay annotates only."),
        }
```

Add to the output dict, **only when present**, so a disabled Profile's JSON is byte-identical to before:

```python
    if overlay_block:
        out["overlay"] = overlay_block
```

Never write `out["overlay"] = None`. A null key is a diff.

- [ ] **Step 4: Run the tests, and prove the parity assertion can fail**

```bash
python3 scripts/profile_analysis.py self-test
```

Then break it deliberately — make the advisory path also sort by priority — and confirm the parity assertion fails naming `gaps`. Restore afterwards and report exactly what the failing output said. An assertion that cannot fail is decoration.

- [ ] **Step 5: Commit**

```bash
git add skills/nist-csf/scripts/profile_analysis.py
git commit -m "feat(nist-csf): advisory mode, with the parity bar that protects non-adopters"
```

---

## Task 7: `reorder` mode

**Files:** Modify `scripts/profile_analysis.py`

This is the default mode. **Give its tests the most attention in the plan.**

- [ ] **Step 1: Write the failing test**

```python
    # --- reorder changes order and NOTHING else ---------------------------
    _re = os.path.join(_tmp, "reorder.csfp")
    _copy_fixture(FIXTURE, _re)
    _cmd_overlay(["enable", _re, "--focus", "secure", "--mode", "reorder",
                  "--ts", "2026-02-01T00:00:00Z"])
    _re_out = os.path.join(_tmp, "re.json")
    _cmd_analyze([_re, "--today", "2026-07-28", "--out", _re_out])
    with open(_re_out) as _fh:
        _re_an = json.load(_fh)

    _base_vals = {r["subcategoryId"]: (r["current"], r["target"], r["gap"],
                                       r["prioritizedGapScore"])
                  for r in _base["gaps"]}
    _re_vals = {r["subcategoryId"]: (r["current"], r["target"], r["gap"],
                                     r["prioritizedGapScore"])
                for r in _re_an["gaps"]}
    eq(_re_vals, _base_vals, "reorder changes no gap VALUE")
    eq(sorted(r["subcategoryId"] for r in _re_an["gaps"]),
       sorted(r["subcategoryId"] for r in _base["gaps"]),
       "and drops or adds no row")
    for _k in ("coverage", "completeness", "tiers", "queue", "evidence"):
        eq(_re_an[_k], _base[_k],
           f"reorder leaves analyze.{_k} untouched — it is not a scoring change")

    _order_base = [r["subcategoryId"] for r in _base["gaps"]]
    _order_re = [r["subcategoryId"] for r in _re_an["gaps"]]
    ok(_order_re != _order_base,
       "and the order actually differs, or the mode does nothing")

    # The point of the mode: urgency beats size.
    _pos = {sid: i for i, sid in enumerate(_order_re)}
    _p1 = [r for r in _re_an["gaps"]
           if (r.get("overlay") or {}).get("effectivePriority") == 1]
    _p3 = [r for r in _re_an["gaps"]
           if (r.get("overlay") or {}).get("effectivePriority") == 3]
    if _p1 and _p3:
        ok(max(_pos[r["subcategoryId"]] for r in _p1)
           < min(_pos[r["subcategoryId"]] for r in _p3),
           "every priority-1 row outranks every priority-3 row, whatever the gap size")

    _un = [r for r in _re_an["gaps"] if not r.get("overlay")]
    if _un and _p3:
        ok(min(_pos[r["subcategoryId"]] for r in _un)
           > max(_pos[r["subcategoryId"]] for r in _p3),
           "Subcategories the dataset says nothing about sort after those it does")

    # Determinism: same input, same order, twice.
    _re_out2 = os.path.join(_tmp, "re2.json")
    _cmd_analyze([_re, "--today", "2026-07-28", "--out", _re_out2])
    with open(_re_out2) as _fh:
        eq([r["subcategoryId"] for r in json.load(_fh)["gaps"]], _order_re,
           "ordering is deterministic across runs")

    eq(_re_an["overlay"]["orderingNote"][:9], "Gap order",
       "and the output states that the order is AI-prioritized")
```

- [ ] **Step 2: Run it to verify it fails**

Expected: the "order actually differs" assertion fails — reorder is not implemented.

- [ ] **Step 3: Implement**

In `_cmd_analyze`, after overlay data is attached to gap rows and only when `cfg["mode"] == "reorder"`:

```python
        if cfg["mode"] == "reorder":
            # Two-pass stable sort. Python's sort is stable, so sorting by the
            # existing key first and the overlay key second preserves the old
            # ordering WITHIN each priority band. A single reverse=True over a
            # tuple would reverse the tie-break too.
            gaps.sort(key=lambda r: (-r["prioritizedGapScore"], r["subcategoryId"]))
            gaps.sort(key=lambda r: (r.get("overlay") or {})
                      .get("effectivePriority", 99))
```

`99` is the sentinel for "the dataset says nothing", which sorts after every real priority. Do **not** use `None` — Python 3 refuses to compare `None` with `int`.

Nothing else changes. Do not touch `playbook`, `attention`, `queue`, or any coverage figure; if the playbook or top-five is derived from `gaps` downstream, it inherits the new order for free — confirm which by reading, and assert it either way.

- [ ] **Step 4: Run the tests**

```bash
python3 scripts/profile_analysis.py self-test
```

- [ ] **Step 5: Prove the ordering assertion can fail**

Change the sentinel from `99` to `0` so unranked rows sort first, re-run, and confirm the "sort after those it does" assertion fails. Restore. Report the failing text.

- [ ] **Step 6: Commit**

```bash
git add skills/nist-csf/scripts/profile_analysis.py
git commit -m "feat(nist-csf): reorder mode — sequencing only, every value untouched"
```

---

## Task 8: Extraction helper

**Files:** Create `tools/extract_cyber_ai.py`

**Gated on Task 1.** Do not start if T1 found a newer draft or could not reach the source.

- [ ] **Step 1: Write it**

`tools/extract_cyber_ai.py`, stdlib only, Python 3.9. Input: IR 8596 PDF text. Output: a dataset conforming to T2's schema, plus a **coverage report**.

Requirements, in priority order:

1. **Never silently default.** A cell whose priority cannot be parsed is reported as unparsed, not filled with 3.
2. **Emit the coverage report to stderr and a file**: Subcategories found, Subcategories missing from the Core's 106, and every `(subcategory, focusArea)` cell where a priority could not be read.
3. Parse `Proposed Priority: <n>` within each Focus Area sub-column.
4. Set `standardPracticesApply` true when the cell's considerations contain "standard cybersecurity practices apply" (case-insensitive, whitespace-normalised).
5. Expect merged cells and page breaks to split rows. The coverage report is how those are found; the parser does not have to be perfect.

- [ ] **Step 2: Run it and read the coverage report**

```bash
python3 tools/extract_cyber_ai.py <source> --out /tmp/cyber-ai-raw.json \
  --coverage /tmp/coverage.txt
cat /tmp/coverage.txt
```

Report the count found and the count needing manual completion. Do not proceed to T9 until you have read the whole report.

- [ ] **Step 3: Commit**

```bash
git add tools/extract_cyber_ai.py
git commit -m "tools: IR 8596 extraction helper with a coverage report"
```

---

## Task 9: Populate and verify the real dataset

**Files:** Create `skills/nist-csf/references/cyber-ai-profile.json`

**Gated on Tasks 1 and 8.**

- [ ] **Step 1: Complete every cell the coverage report flagged**

Read the source directly for each. Expected total: **106 × 3 = 318** priority values. Point `DEFAULT_CYBER_AI` back at the real path if T4 pointed it elsewhere.

- [ ] **Step 2: Validate**

```bash
cd ~/Documents/GitHub/cac-ciso-toolkit/skills/nist-csf
python3 - <<'EOF'
import json, sys
sys.path.insert(0, "scripts")
import profile_analysis as p
idx = p.index_subcategories(p.load_core())
d = p.load_overlay_dataset(index=idx)
subs = d["subcategories"]
print("subcategories:", len(subs), "(expect 106)")
print("values:", sum(len([a for a in ("secure","defend","thwart") if a in v])
                     for v in subs.values()), "(expect 318)")
missing = sorted(set(idx) - set(subs))
print("missing from dataset:", missing or "none")
EOF
```

Expected: 106, 318, none missing. **If any Subcategory is missing, the dataset is incomplete — do not ship it as complete.**

- [ ] **Step 3: Independent spot-check — 20 Subcategories, 60 values**

Select 20 spread across all six Functions, including **at least five** that required manual completion. Read each directly from the source and compare all three priorities.

**Any mismatch means re-verify the entire dataset, not just the failing row.** One transcription error means the process is unreliable, and a wrong priority misdirects remediation invisibly — the validator proves well-formedness, never correctness.

Record the sampled IDs and the result in `docs/superpowers/notes/`.

- [ ] **Step 4: Run everything and commit**

```bash
cd ~/Documents/GitHub/cac-ciso-toolkit
python3 skills/nist-csf/scripts/profile_analysis.py self-test
git add skills/nist-csf/references/cyber-ai-profile.json docs/superpowers/notes/
git commit -m "feat(nist-csf): the IR 8596 dataset, 318 values, spot-checked"
```

---

## Task 10: Minimum honest disclosure in both renderers

**Files:** Modify `renderers/_common.py`, `renderers/render_operational.py`, `renderers/render_executive.py`, `references/dashboards.md`

**Why this is in Increment 1 and not deferred.** `reorder` changes the gap table's order, and the renderers project `gaps` directly. Shipping the engine without this would produce a dashboard whose rows are AI-sequenced while it still reads as gap-severity order — a report that misleads by omission. Badges, the Focus Area rollup, CAC guidance and the executive AI-posture paragraph are **Increment 2**; this task ships only what stops the output lying.

- [ ] **Step 1: Add overlay to the Context**

In `_common.py`, beside `Context.evidence` / `.intake` / `.queue`:

```python
    @property
    def overlay(self) -> dict:
        """Overlay block, or {} when the Profile has not opted in."""
        return self.data.get("overlay") or {}
```

Match the surrounding idiom — read how `evidence` is defined and follow it.

- [ ] **Step 2: Extend the footer with provenance**

`footer(extra="")` already joins bits with ` · `. Pass the overlay provenance through from both renderers:

```python
ctx.footer(ctx.overlay.get("provenance", ""))
```

The existing `DISCLAIMER` stays first. Every artifact carrying overlay output now states the dataset version and its draft status on the artifact itself, not only in documentation.

- [ ] **Step 3: State the ordering, where the ordering is**

In `render_operational.py`, immediately above the gap table, and in `render_executive.py` above the top-gaps section, render `ctx.overlay["orderingNote"]` when the overlay block is present. It must be adjacent to the rows it describes — a note in the footer does not stop a reader misreading the table.

Use an existing hint/caption class rather than inventing one. **Check `_common.py` for the class names already in use, and do not reuse `.chip` or `.schip`** — both are taken, and a collision restyles unrelated elements without failing any gate.

- [ ] **Step 4: Update `references/dashboards.md`**

Add to the rules binding both dashboards:

```markdown
9. **Reordered is never silently reordered.** When an overlay changes row order, both
   dashboards state so adjacent to the affected table, and both carry the dataset version and
   its source status in the footer. A reader who is not told assumes the prioritized gap table
   is ordered by gap severity, because that is what it means everywhere else. An overlay that
   is invisible in the artifact is indistinguishable from the tool having changed its mind.
```

- [ ] **Step 5: Run the render gate — do not skip and do not trust a grep**

```bash
cd ~/Documents/GitHub/cac-ciso-toolkit
./skills/risk-register/evals/responsive.sh
```

Both measured properties — width and WCAG AA contrast — are properties of a **resolved layout**, not of the CSS text. Reading the stylesheet cannot answer either, which is where four shipped defects hid. If the suite does not render an overlay-enabled page, add one: a fixture with the overlay on, in `reorder` mode.

- [ ] **Step 6: Commit**

```bash
git add skills/nist-csf/renderers skills/nist-csf/references/dashboards.md
git commit -m "feat(nist-csf): say when the order is AI-prioritized, and where the data came from"
```

---

## Task 11: Documentation, version, and the full gate

**Files:** Create `references/cyber-ai-overlay.md`; modify `SKILL.md`, `README.md`, the four version files

- [ ] **Step 1: Write `references/cyber-ai-overlay.md`**

The canonical contract. It must cover:

- **Mode semantics.** `advisory` annotates; `reorder` resequences `gaps` only. Neither changes a score, target, gap, coverage figure or Tier.
- **The effective-priority rule.** Minimum across selected Focus Areas; deselecting can only relax.
- **The queue decision, stated as a decision:** the overlay does **not** reorder `queue` or `elicit`. Those answer "what do I have material for?", an evidence question; and layering IR 8596 priority over `cold-start-rank.json` would put two editorial orderings in silent competition.
- **Why `floor` is absent**, with the scale reasoning and a pointer to `scale-and-scoring.md`.
- **The disclaimer**, covering all four points: the source is a preliminary draft; NIST describes priority determination as a subjective exercise that may differ by organization; priority indicates **sequencing, not required maturity**; and any target-floor interpretation would be CAC's, not NIST's.

- [ ] **Step 2: `SKILL.md`**

Add a section covering:

- **The three scoping questions, asked plainly.** *Do you build or deploy AI systems?* → secure. *Does your security programme use AI?* → defend. *Thwart applies regardless* — stated as confirmation, not asked. Saying the third out loud is what makes the overlay legible to a CISO who has banned internal AI use.
- **Enabling adds no assessment work.** State it explicitly; the reasonable assumption is the opposite.
- **What each mode does to the numbers**, in one line each.
- A row in the reference table for `references/cyber-ai-overlay.md` and one for `references/cyber-ai-profile.json`.

Do not add a check count or any other number that goes stale — two have already been removed from this file for that reason.

- [ ] **Step 3: Version and README**

Bump all four version occurrences (`.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json` ×2, `.codex-plugin/plugin.json`). Add a bullet to README's nist-csf section describing the overlay, disabled by default.

- [ ] **Step 4: Run the full gate**

```bash
cd ~/Documents/GitHub/cac-ciso-toolkit
python3 skills/nist-csf/scripts/profile_analysis.py self-test
python3 skills/nist-csf/scripts/csfa_compat.py self-test
python3 skills/risk-register/scripts/score_register.py self-test
python3 skills/nist-csf/evals/score-conversations.py self-test
./skills/risk-register/evals/python-compat.sh
PY=/usr/bin/python3 ./skills/risk-register/evals/board-safety.sh
./skills/risk-register/evals/responsive.sh
```

All must pass. `csfa_compat` **must** still report 47/47 with the gaps CSV MD5 unchanged — the overlay must not reach the frozen port. If it moved, something touched a path this plan said not to.

- [ ] **Step 5: Commit and open the PR**

---

## What this plan does not cover

- **`floor` mode**, per the decision above. No `effectiveTarget`, no `targetRaisedBy`.
- **Reordering `queue` or `elicit`** — a decision, documented as one.
- **Focus Area badges, the Focus Area rollup, CAC-authored guidance, and the executive AI-posture paragraph.** These are Increment 2, planned separately once the mechanism has landed. They are the largest contrast surface the skill has taken at once and deserve their own render-gate pass.
- **`references/cyber-ai-guidance.md`** — a parallel human authoring track, filtered by `standardPracticesApply`. Blocks nothing here.
- NIST AI RMF, per-AI-system assessment, EU AI Act classification, auto-detection of AI usage, reproducing NIST's consideration text, per-Focus-Area mode selection, SP 800-53 COSAiS.

## Risks

| Risk | Mitigation |
|---|---|
| Source is superseded or unreachable | T1 gates T8/T9 and is a hard stop. The dataset is swappable, so the cost is a re-run. |
| A wrong priority silently misdirects remediation | T9 spot-check, 60 values, with a re-verify-everything failure rule. The validator proves form, never correctness — stated in its own docstring. |
| Overlay perturbs a Profile that has not opted in | T6 parity assertions across every computed block, plus inert normalization defaults. |
| Reordered rows read as severity order | T10, adjacent to the table, plus dashboards.md rule 9. |
| Priority read as a maturity claim | `floor` cut; disclaimer in T11; `overlay list` says it in its own output. |
| Overlay reaches the frozen `.csfa` port | T11 asserts csfa-compat 47/47 and the CSV MD5. |
| Render defects in new elements | T10 runs `responsive.sh` on an overlay-enabled fixture; Increment 2 carries the larger surface. |
