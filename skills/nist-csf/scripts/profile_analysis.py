#!/usr/bin/env python3
"""
profile_analysis.py — deterministic CSF Organizational Profile engine for the nist-csf skill.

Owns a local `.csfp` store: per-Subcategory Current/Target ratings, gap analysis, coverage
rollups, risk-weighted prioritization, Tier characterization, append-only history, named
snapshots, and an action plan. Standard library only — no dependencies.

Framework-neutral by construction: a "framework" is data, not code. The bundled
`references/nist-csf-2.0-core.json` is the first framework loaded; nothing here hard-codes
the six CSF Function names. See `references/framework-abstraction.md`.

Design anchors:
  - Achievement rating != Tier.  Ratings are per-Subcategory (0-3); Tiers characterize the
    rigor of the whole Profile (CSWP 29 Sec. 3.2) and are NEVER a maturity score.
  - Coverage never flatters.  A Profile with nothing targeted reports no coverage at all,
    not 100%.  Every coverage figure carries its numerator and denominator.
  - Derived data is never stored, only computed (except frozen inside a snapshot).
  - Reproducible.  Timestamps and "today" are passed in wherever a test observes them.

Read-only:
  validate     [--core PATH]                       Assert the bundled Core is intact (6/22/106).
  analyze      <store.csfp> [--today D] [--top N] [--out F]   Emit the complete derived JSON.
  diff         <store.csfp> [--label L] [--json]   Compare current state to a snapshot.
  export-gaps  <store.csfp> [--out F]              Gap CSV for `risk-register import-gaps`.
  self-test                                        Assert engine math against the fixture.

Mutations (each appends an append-only history event and rewrites the store):
  init              --name N --out F [--purpose ...] [--owner ...] [--org-units A B]
                    [--threat-types X Y] [--assumptions ...] [--id ID] [--ts TS]
  set               <store.csfp> <subcategoryId> [--current N|null] [--target N|null]
                    [--priority P] [--status S] [--applicability A] [--notes ...]
                    [--evidence A B] [--reviewed] [--rationale ...] [--actor A] [--ts TS]
  set-tier          <store.csfp> [--overall N] [--function GV=N ...] --rationale ... [--actor A]
  quickstart-target <store.csfp> [--level N] [--force] [--rationale ...] [--actor A] [--ts TS]
  snapshot          <store.csfp> --label 'Q2 2026 Assessment' [--note ...] [--ts TS]
  action add        <store.csfp> --title T [--linked A B] [--owner O] [--milestone M]
                    [--target-date D] [--notes ...]
  action update     <store.csfp> <id> [--title ...] [--owner ...] [--target-date ...] ...
  action close      <store.csfp> <id> --rationale ...

Usage:
  python3 profile_analysis.py init --name "Acme Corp" --out acme.csfp --owner CISO
  python3 profile_analysis.py quickstart-target acme.csfp
  python3 profile_analysis.py set acme.csfp PR.AA-01 --current 1 --rationale "SSO live for corp apps"
  python3 profile_analysis.py analyze acme.csfp --today 2026-07-26 > analysis.json
  python3 profile_analysis.py self-test
"""

from __future__ import annotations

import copy
import csv
import io
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timezone

# Behave like a normal Unix filter: on a closed pipe (e.g. `... | head`), exit
# quietly instead of dumping a BrokenPipeError traceback.
try:
    import signal
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)
except (ImportError, AttributeError, ValueError):
    pass

# --- Constants ---------------------------------------------------------------

SCHEMA_VERSION = "2.0"          # current write version
SUPPORTED_SCHEMA = {"1.0", "2.0"}   # v1 files load and normalize to v2 shape in memory
FRAMEWORK_REF = "nist-csf-2.0"

APPLICABILITY = ("in-scope", "not-applicable")
PRIORITIES = ("low", "medium", "high", "critical")
STATUSES = ("not-started", "in-progress", "met", "accepted-gap")
ACTION_STATUSES = ("open", "in-progress", "closed")

DEFAULT_SETTINGS = {
    "scale": {
        "type": "ordinal", "min": 0, "max": 3,
        "labels": {"0": "Not Achieved", "1": "Partially Achieved",
                   "2": "Largely Achieved", "3": "Fully Achieved"},
    },
    "priorityWeights": {"low": 1, "medium": 2, "high": 3, "critical": 4},
    "functionWeights": {},   # filled per framework at init; equal by default
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
}

QUICKSTART_DEFAULT_LEVEL = 2   # "Largely Achieved" — a defensible baseline, not a maximum.

# Integrity invariants for the bundled CSF 2.0 Core. Verified against the NIST CPRT
# catalog at ingest time; asserted again on every load so a corrupted or truncated
# reference file fails loudly instead of silently under-reporting coverage.
CORE_EXPECTED = {
    "functions": 6, "categories": 22, "subcategories": 106, "examples": 363,
    "perFunction": {"GV": 31, "ID": 21, "PR": 22, "DE": 11, "RS": 13, "RC": 8},
}

_SKILL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_CORE = os.path.join(_SKILL_ROOT, "references", "nist-csf-2.0-core.json")
DEFAULT_GUIDANCE = os.path.join(_SKILL_ROOT, "references", "guidance.json")
FIXTURE = os.path.join(_SKILL_ROOT, "examples", "example-profile.csfp")


# --- Core (framework reference data) -----------------------------------------

def load_core(path: str | None = None) -> dict:
    """Load the bundled framework definition.

    Resolved relative to the skill root, not the caller's cwd, so the engine works from
    any working directory.
    """
    path = path or DEFAULT_CORE
    try:
        with open(path, encoding="utf-8") as fh:
            core = json.load(fh)
    except FileNotFoundError:
        raise FileNotFoundError(
            f"Framework Core not found at {path}. This file is generated from the NIST CPRT "
            f"catalog and ships with the skill; a missing file means a broken install."
        ) from None
    except json.JSONDecodeError as exc:
        raise ValueError(f"Framework Core at {path} is not valid JSON: {exc}") from exc

    if not isinstance(core.get("hierarchy"), list) or not core["hierarchy"]:
        raise ValueError(f"Framework Core at {path} has no hierarchy.")
    return core


def index_subcategories(core: dict) -> dict:
    """Flatten the hierarchy to `subcategoryId -> {...}` for O(1) joins.

    Carries the Function/Category context, the outcome text, Implementation Examples, and
    Informative References. The references travel with the index but are not rendered in
    v1 — they are the substrate for the v2 crosswalk views.
    """
    index: dict[str, dict] = {}
    for fn in core["hierarchy"]:
        for cat in fn.get("categories", []):
            for sub in cat.get("subcategories", []):
                sid = sub["id"]
                if sid in index:
                    raise ValueError(f"Duplicate Subcategory id in Core: {sid}")
                index[sid] = {
                    "id": sid,
                    "text": sub.get("text", ""),
                    "functionId": fn["id"],
                    "functionName": fn.get("name", fn["id"]),
                    "categoryId": cat["id"],
                    "categoryName": cat.get("name", cat["id"]),
                    "examples": sub.get("examples", []),
                    "informativeReferences": sub.get("informativeReferences", []),
                }
    return index


def function_ids(core: dict) -> list[str]:
    """Ordered Function ids. Never hard-code these — they are framework data."""
    return [fn["id"] for fn in core["hierarchy"]]


def check_core(core: dict) -> list[str]:
    """Return a list of integrity problems; empty means the Core is intact."""
    problems: list[str] = []
    fns = core["hierarchy"]
    cats = [c for f in fns for c in f.get("categories", [])]
    subs = [s for c in cats for s in c.get("subcategories", [])]

    if core.get("id") != FRAMEWORK_REF:
        problems.append(f"framework id is {core.get('id')!r}, expected {FRAMEWORK_REF!r}")
    if len(fns) != CORE_EXPECTED["functions"]:
        problems.append(f"expected {CORE_EXPECTED['functions']} Functions, found {len(fns)}")
    if len(cats) != CORE_EXPECTED["categories"]:
        problems.append(f"expected {CORE_EXPECTED['categories']} Categories, found {len(cats)}")
    if len(subs) != CORE_EXPECTED["subcategories"]:
        problems.append(f"expected {CORE_EXPECTED['subcategories']} Subcategories, found {len(subs)}")

    for fn in fns:
        want = CORE_EXPECTED["perFunction"].get(fn["id"])
        got = sum(len(c.get("subcategories", [])) for c in fn.get("categories", []))
        if want is None:
            problems.append(f"unexpected Function id {fn['id']!r}")
        elif got != want:
            problems.append(f"{fn['id']}: expected {want} Subcategories, found {got}")

    ids = [s["id"] for s in subs]
    if len(set(ids)) != len(ids):
        dupes = sorted({i for i in ids if ids.count(i) > 1})
        problems.append(f"duplicate Subcategory ids: {', '.join(dupes)}")

    n_examples = sum(len(s.get("examples", [])) for s in subs)
    if n_examples != CORE_EXPECTED["examples"]:
        problems.append(f"expected {CORE_EXPECTED['examples']} Implementation Examples, found {n_examples}")

    missing = [s["id"] for s in subs if not s.get("examples")]
    if missing:
        problems.append(f"Subcategories with no Implementation Example: {', '.join(missing[:8])}")

    blank = [s["id"] for s in subs if not s.get("text")]
    if blank:
        problems.append(f"Subcategories with empty text: {', '.join(blank[:8])}")

    tiers = core.get("tiers")
    if not tiers or not tiers.get("levels"):
        problems.append("Tier characterizations are missing")
    elif len(tiers["levels"]) != 4:
        problems.append(f"expected 4 Tiers, found {len(tiers['levels'])}")

    return problems


# --- Store IO ----------------------------------------------------------------

def load_store(path: str) -> dict:
    """Load and structurally validate a `.csfp` store."""
    try:
        with open(path, encoding="utf-8") as fh:
            store = json.load(fh)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path} is not a valid Profile file (invalid JSON): {exc}") from exc

    if store.get("schemaVersion") not in SUPPORTED_SCHEMA:
        raise ValueError(
            f"Unsupported schemaVersion {store.get('schemaVersion')!r} "
            f"(supported: {', '.join(sorted(SUPPORTED_SCHEMA))})."
        )
    if not isinstance(store.get("profile"), dict):
        raise ValueError("Invalid Profile file: missing 'profile' object.")
    if not isinstance(store.get("assessments"), list):
        raise ValueError("Invalid Profile file: missing 'assessments' array.")

    store.setdefault("history", [])
    store.setdefault("snapshots", [])
    store.setdefault("actionItems", [])
    prof = store["profile"]
    prof.setdefault("scope", {})
    prof.setdefault("tier", {"overall": None, "byFunction": {}})
    prof["settings"] = {**copy.deepcopy(DEFAULT_SETTINGS), **prof.get("settings", {})}

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
    return store


def save_store(store: dict, path: str, ts: str) -> None:
    """Write the store back, stamping schemaVersion and profile.updated.

    History is never rewritten here — callers append to store['history'] before saving.
    """
    store["schemaVersion"] = SCHEMA_VERSION
    store["profile"]["updated"] = ts
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(store, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


def check_store(store: dict, index: dict) -> list[str]:
    """Structural problems with a store, checked against the framework index."""
    problems = []
    prof = store["profile"]
    if prof.get("frameworkRef") != FRAMEWORK_REF:
        problems.append(f"profile.frameworkRef is {prof.get('frameworkRef')!r}, expected {FRAMEWORK_REF!r}")

    seen = set()
    for a in store["assessments"]:
        sid = a.get("subcategoryId")
        if sid not in index:
            problems.append(f"assessment references unknown Subcategory {sid!r}")
            continue
        if sid in seen:
            problems.append(f"duplicate assessment for {sid}")
        seen.add(sid)
        if a.get("applicability") not in APPLICABILITY:
            problems.append(f"{sid}: applicability {a.get('applicability')!r} not in {APPLICABILITY}")
        if a.get("priority") not in PRIORITIES:
            problems.append(f"{sid}: priority {a.get('priority')!r} not in {PRIORITIES}")
        if a.get("status") not in STATUSES:
            problems.append(f"{sid}: status {a.get('status')!r} not in {STATUSES}")
        for field in ("current", "target"):
            v = a.get(field)
            if v is None:
                continue
            lo, hi = prof["settings"]["scale"]["min"], prof["settings"]["scale"]["max"]
            if not isinstance(v, int) or not (lo <= v <= hi):
                problems.append(f"{sid}: {field} {v!r} outside scale {lo}..{hi}")

    for item in store["actionItems"]:
        if item.get("status") not in ACTION_STATUSES:
            problems.append(f"action {item.get('id')}: status {item.get('status')!r} not in {ACTION_STATUSES}")
        for sid in item.get("linkedSubcategoryIds", []):
            if sid not in index:
                problems.append(f"action {item.get('id')}: unknown Subcategory {sid!r}")
    return problems


# --- History -----------------------------------------------------------------

# Rationale is REQUIRED on these. Each is a claim someone will later be asked to defend.
def is_material(field: str, old, new) -> bool:
    if old == new:
        return False
    if field in ("current", "target"):
        return True
    if field == "status" and new in ("accepted-gap", "met"):
        return True
    if field == "applicability" and new == "not-applicable":
        return True
    return False


def append_history(store, etype, *, subcategoryId=None, field=None, frm=None, to=None,
                   rationale=None, actor=None, ts=None, actionId=None):
    ev = {"ts": ts, "actor": actor or store["profile"]["scope"].get("owner") or "unknown", "type": etype}
    if subcategoryId is not None:
        ev["subcategoryId"] = subcategoryId
    if actionId is not None:
        ev["actionId"] = actionId
    if field is not None:
        ev["field"] = field
        ev["from"] = frm
        ev["to"] = to
    if rationale:
        ev["rationale"] = rationale
    store["history"].append(ev)
    return ev


# --- Computation (pure: no IO, no clock) --------------------------------------

def in_scope(assessments: list[dict]) -> list[dict]:
    return [a for a in assessments if a.get("applicability", "in-scope") == "in-scope"]


def gap_of(a: dict):
    """max(0, target - current), with current null treated as 0.

    Returns None where no target is set — untargeted is undecided, not zero-gap.
    """
    if a.get("target") is None:
        return None
    return max(0, a["target"] - (a.get("current") or 0))


def prioritized_score(a: dict, settings: dict, index: dict) -> float:
    g = gap_of(a)
    if not g:
        return 0.0
    pw = settings["priorityWeights"].get(a.get("priority", "medium"), 1)
    fid = index[a["subcategoryId"]]["functionId"]
    fw = settings["functionWeights"].get(fid, 1)
    return g * pw * fw


def compute_gaps(assessments: list[dict], settings: dict, index: dict) -> list[dict]:
    """Gap rows for every in-scope assessment with a gap > 0, richest-first.

    Tie-break is subcategoryId ascending so ordering is total and reproducible.
    """
    rows = []
    for a in in_scope(assessments):
        g = gap_of(a)
        if not g:
            continue
        meta = index[a["subcategoryId"]]
        rows.append({
            "subcategoryId": a["subcategoryId"],
            "functionId": meta["functionId"],
            "functionName": meta["functionName"],
            "categoryId": meta["categoryId"],
            "categoryName": meta["categoryName"],
            "text": meta["text"],
            "current": a.get("current"),
            "target": a.get("target"),
            "gap": g,
            "priority": a.get("priority", "medium"),
            "prioritizedGapScore": prioritized_score(a, settings, index),
            "status": a.get("status"),
            "lastReviewed": a.get("lastReviewed"),
            "examples": meta["examples"],
            "informativeReferences": meta["informativeReferences"],
        })
    rows.sort(key=lambda r: (-r["prioritizedGapScore"], r["subcategoryId"]))
    return rows


def _coverage_of(subset: list[dict]) -> dict:
    """Coverage for a set of assessments. See references/schema.md for the contract."""
    targeted = [a for a in in_scope(subset) if a.get("target") is not None]
    d = sum(a["target"] for a in targeted)
    n = sum(min(a.get("current") or 0, a["target"]) for a in targeted)
    # D == 0 yields null, never 100%. A Profile with nothing targeted has no coverage.
    return {"percent": (n / d * 100) if d else None, "n": n, "d": d}


def _completeness_of(subset: list[dict]) -> dict:
    scoped = in_scope(subset)
    return {
        "total": len(subset),
        "inScope": len(scoped),
        "notApplicable": len(subset) - len(scoped),
        "assessed": sum(1 for a in scoped if a.get("current") is not None),
        "targeted": sum(1 for a in scoped if a.get("target") is not None),
    }


def _group(assessments: list[dict], index: dict, key: str) -> dict:
    out: dict[str, list] = {}
    for a in assessments:
        meta = index.get(a["subcategoryId"])
        if meta:
            out.setdefault(meta[key], []).append(a)
    return out


def compute_coverage(assessments: list[dict], index: dict, core: dict) -> dict:
    by_fn = _group(assessments, index, "functionId")
    by_cat = _group(assessments, index, "categoryId")
    return {
        "overall": _coverage_of(assessments),
        # Every Function in the framework appears, even with no assessments, so a
        # dashboard cannot silently omit an untouched Function.
        "byFunction": {fid: _coverage_of(by_fn.get(fid, [])) for fid in function_ids(core)},
        "byCategory": {cid: _coverage_of(subset) for cid, subset in sorted(by_cat.items())},
    }


def compute_completeness(assessments: list[dict], index: dict, core: dict) -> dict:
    by_fn = _group(assessments, index, "functionId")
    by_cat = _group(assessments, index, "categoryId")
    return {
        "overall": _completeness_of(assessments),
        "byFunction": {fid: _completeness_of(by_fn.get(fid, [])) for fid in function_ids(core)},
        "byCategory": {cid: _completeness_of(subset) for cid, subset in sorted(by_cat.items())},
    }


# --- Authored guidance -------------------------------------------------------

def load_guidance(path: str | None = None) -> dict:
    """Load the harvested authored guidance. Absent is fine — guidance is additive."""
    try:
        with open(path or DEFAULT_GUIDANCE, encoding="utf-8") as fh:
            return json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def render_guidance(row: dict, settings: dict, guidance: dict) -> dict | None:
    """Assemble 'how to close this' for one gap row.

    Ported from the web tool's renderGuidance, with one deliberate restriction.
    The tool's tier-transition paragraphs name specific levels ("Partial to Risk
    Informed") and only make sense on its own 0-4 scale. A Profile using the
    default 0-3 achievement scale means something different by "1", so the
    transition text is included only when the scale actually matches. The deep
    entries and function slants describe practice rather than levels, so they
    apply on any scale.
    """
    if not guidance:
        return None
    deep = (guidance.get("deepGuidance") or {}).get(row["subcategoryId"])
    out = {"subcategoryId": row["subcategoryId"], "source": "deep" if deep else "template"}

    if deep:
        out["whatMatureLooksLike"] = deep.get("whatMatureLooksLike")
        out["nextSteps"] = list(deep.get("nextSteps") or [])
        if deep.get("commonPitfalls"):
            out["commonPitfalls"] = deep["commonPitfalls"]
    else:
        slant = (guidance.get("functionSlants") or {}).get(row["functionId"])
        if slant:
            out["functionSlant"] = slant

    scale = settings.get("scale", {})
    tool_scale = scale.get("max") == 4 and scale.get("labels", {}).get("2") == "Risk Informed"
    if tool_scale:
        cur = row.get("current")
        transition = (guidance.get("tierTransitions") or {}).get(str(cur if cur is not None else 0))
        if transition:
            out["transition"] = transition
        names = guidance.get("tierNames") or {}
        if names:
            out["header"] = (f"{names.get(str(cur if cur is not None else 0), cur)} → "
                             f"{names.get(str(row.get('target')), row.get('target'))}.")
    else:
        labels = scale.get("labels", {})
        cur = row.get("current")
        out["header"] = (f"{labels.get(str(cur), 'unassessed') if cur is not None else 'unassessed'} → "
                         f"{labels.get(str(row.get('target')), row.get('target'))}.")
    return out if len(out) > 2 else None


def build_playbook(gaps: list[dict], settings: dict, guidance: dict, top: int = 10) -> list[dict]:
    """The Next-90-Days worksheet: top gaps, each with a recommended first move.

    Owner and due date are deliberately blank — this is a worksheet to be filled in
    with a team, not a plan to be handed down. Once an item has an owner and a date
    it belongs in the action plan, tracked by `action add`.
    """
    rows = []
    for g in gaps[:top]:
        gd = render_guidance(g, settings, guidance) or {}
        first = (gd.get("nextSteps") or [None])[0] or gd.get("functionSlant")
        rows.append({
            "subcategoryId": g["subcategoryId"],
            "functionId": g["functionId"],
            "text": g["text"],
            "current": g.get("current"),
            "target": g.get("target"),
            "priority": g.get("priority"),
            "prioritizedGapScore": g.get("prioritizedGapScore"),
            "recommendedFirstMove": first,
            "owner": "", "due": "",
        })
    return rows


def attention_lists(store: dict, index: dict, today: str, top: int = 10) -> dict:
    """What a reviewer must look at. `today` is passed in — never read from the clock."""
    settings = store["profile"]["settings"]
    scoped = in_scope(store["assessments"])
    gaps = compute_gaps(store["assessments"], settings, index)

    def _brief(a):
        return {"subcategoryId": a["subcategoryId"], "text": index[a["subcategoryId"]]["text"],
                "lastReviewed": a.get("lastReviewed"), "status": a.get("status")}

    never = [_brief(a) for a in scoped if not a.get("lastReviewed")]
    never.sort(key=lambda r: r["subcategoryId"])

    reviewed = [a for a in scoped if a.get("lastReviewed")]
    reviewed.sort(key=lambda a: (a["lastReviewed"], a["subcategoryId"]))

    open_actions = [i for i in store["actionItems"] if i.get("status") != "closed"]
    return {
        "largestGaps": gaps[:top],
        # Never-reviewed is deliberately a separate bucket from stalest: "nobody has ever
        # looked" is a different problem from "nobody has looked lately".
        "neverReviewed": never,
        "stalest": [_brief(a) for a in reviewed[:top]],
        "unownedActions": [i for i in open_actions if not (i.get("owner") or "").strip()],
        "pastDueActions": [i for i in open_actions
                           if i.get("targetDate") and i["targetDate"] < today],
        "acceptedGaps": [_brief(a) for a in scoped if a.get("status") == "accepted-gap"],
    }


def rollups(store: dict, index: dict, core: dict) -> dict:
    return {
        "coverage": compute_coverage(store["assessments"], index, core),
        "completeness": compute_completeness(store["assessments"], index, core),
    }


# --- Diff --------------------------------------------------------------------

def compute_diff(store: dict, index: dict, core: dict, label: str | None = None) -> dict | None:
    """Compare current state to a snapshot (latest, or the one matching `label`)."""
    snaps = store.get("snapshots") or []
    if not snaps:
        return None
    if label:
        match = [s for s in snaps if s.get("label") == label or s.get("id") == label]
        if not match:
            raise ValueError(f"No snapshot labelled {label!r}. Available: "
                             f"{', '.join(s.get('label', '?') for s in snaps) or '(none)'}")
        snap = match[-1]
    else:
        snap = snaps[-1]

    then = {a["subcategoryId"]: a for a in snap.get("assessments", [])}
    now = {a["subcategoryId"]: a for a in store["assessments"]}

    changed = []
    for sid in sorted(set(then) & set(now)):
        for field in ("current", "target", "status", "applicability", "priority"):
            frm, to = then[sid].get(field), now[sid].get(field)
            if frm != to:
                changed.append({"subcategoryId": sid, "text": index[sid]["text"],
                                "field": field, "from": frm, "to": to})

    cov_then = compute_coverage(snap.get("assessments", []), index, core)
    cov_now = compute_coverage(store["assessments"], index, core)

    def _delta(a, b):
        if a is None or b is None:
            return None
        return b - a

    then_actions = {i["id"]: i for i in snap.get("actionItems", [])}
    now_actions = {i["id"]: i for i in store["actionItems"]}
    closed = [now_actions[i] for i in sorted(now_actions)
              if now_actions[i].get("status") == "closed"
              and then_actions.get(i, {}).get("status") != "closed"]

    return {
        "against": {"id": snap.get("id"), "label": snap.get("label"), "ts": snap.get("ts")},
        "assessments": {
            "changed": changed,
            "added": sorted(set(now) - set(then)),
            "removed": sorted(set(then) - set(now)),
        },
        "coverage": {
            "overall": {"from": cov_then["overall"]["percent"], "to": cov_now["overall"]["percent"],
                        "delta": _delta(cov_then["overall"]["percent"], cov_now["overall"]["percent"])},
            "byFunction": {
                fid: {"from": cov_then["byFunction"][fid]["percent"],
                      "to": cov_now["byFunction"][fid]["percent"],
                      "delta": _delta(cov_then["byFunction"][fid]["percent"],
                                      cov_now["byFunction"][fid]["percent"])}
                for fid in function_ids(core)
            },
        },
        "actionItems": {
            "added": [now_actions[i] for i in sorted(set(now_actions) - set(then_actions))],
            "closed": closed,
        },
    }


# --- CLI helpers -------------------------------------------------------------

def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _s(v):
    """Coerce a possibly-multi-token flag value back to a string."""
    return " ".join(v) if isinstance(v, list) else v


def _list(v):
    if v is None or v is True:
        return []
    return v if isinstance(v, list) else [v]


def parse_flags(args: list[str]):
    """Tiny --flag parser. `--x a b` -> {'x': ['a','b']}; `--x a` -> {'x': 'a'}; `--x` -> {'x': True}."""
    pos, opt, i = [], {}, 0
    while i < len(args):
        a = args[i]
        if a.startswith("--"):
            key, vals, j = a[2:], [], i + 1
            while j < len(args) and not args[j].startswith("--"):
                vals.append(args[j]); j += 1
            opt[key] = (vals if len(vals) > 1 else vals[0]) if vals else True
            i = j
        else:
            pos.append(a); i += 1
    return pos, opt


def _parse_rating(raw, settings, field):
    """Parse a rating flag into int | None, with a pointed error for the old 'N/A' habit."""
    text = str(_s(raw)).strip()
    if text.lower() in ("null", "none", "unset", ""):
        return None
    if text.lower() in ("n/a", "na", "not-applicable"):
        raise ValueError(
            f"'{text}' is not a rating. Out-of-scope is recorded separately: "
            f"use --applicability not-applicable --rationale '...'. "
            f"A rating of 0 means 'assessed, Not Achieved' — a different claim entirely."
        )
    try:
        v = int(text)
    except ValueError:
        raise ValueError(f"--{field} must be an integer or 'null', got {text!r}") from None
    lo, hi = settings["scale"]["min"], settings["scale"]["max"]
    if not (lo <= v <= hi):
        labels = settings["scale"]["labels"]
        opts = ", ".join(f"{k}={v2}" for k, v2 in sorted(labels.items()))
        raise ValueError(f"--{field} {v} is outside the scale {lo}..{hi} ({opts})")
    return v


def _require_store(pos, usage):
    if not pos:
        raise ValueError(usage)
    return pos[0]


# --- Commands ----------------------------------------------------------------

def _cmd_validate(args):
    _, opt = parse_flags(args)
    core = load_core(_s(opt.get("core")) if isinstance(opt.get("core"), (str, list)) else None)
    problems = check_core(core)
    if problems:
        print("Core integrity check FAILED:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 1

    fns = core["hierarchy"]
    cats = [c for f in fns for c in f.get("categories", [])]
    subs = [s for c in cats for s in c.get("subcategories", [])]
    per_fn = " ".join(
        f"{f['id']}:{sum(len(c.get('subcategories', [])) for c in f.get('categories', []))}" for f in fns
    )
    print(f"OK — {core['name']} {core['version']}")
    print(f"  Functions      {len(fns)}")
    print(f"  Categories     {len(cats)}")
    print(f"  Subcategories  {len(subs)}  ({per_fn})")
    print(f"  Examples       {sum(len(s.get('examples', [])) for s in subs)}")
    print(f"  Tiers          {len(core['tiers']['levels'])} × "
          f"{len(core['tiers']['dimensions'])} dimensions (verbatim, {core['tiers']['source']['publication']})")
    return 0


def _cmd_init(args):
    _, opt = parse_flags(args)
    if "name" not in opt or "out" not in opt:
        raise ValueError("usage: init --name 'Acme Corp' --out acme.csfp [--owner CISO] "
                         "[--purpose ...] [--org-units A B] [--threat-types X Y] [--assumptions ...]")
    core = load_core()
    problems = check_core(core)
    if problems:
        raise ValueError("Refusing to initialise against a corrupt Core: " + "; ".join(problems))

    ts = _s(opt.get("ts")) if isinstance(opt.get("ts"), (str, list)) else _now()
    name = _s(opt["name"])
    out = _s(opt["out"])
    pid = _s(opt.get("id")) if isinstance(opt.get("id"), (str, list)) else \
        re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")

    settings = copy.deepcopy(DEFAULT_SETTINGS)
    settings["functionWeights"] = {fid: 1 for fid in function_ids(core)}

    index = index_subcategories(core)
    assessments = [{
        "subcategoryId": sid,
        "applicability": "in-scope",
        # Seeded null, not 0. "Not yet assessed" and "assessed as Not Achieved" are
        # different claims, and only the second one belongs in a coverage denominator.
        "current": None,
        "target": None,
        "priority": "medium",
        "status": "not-started",
        "notes": "",
        "evidenceRefs": [],
        "lastReviewed": None,
    } for sid in index]

    store = {
        "schemaVersion": SCHEMA_VERSION,
        "profile": {
            "id": pid, "name": name, "frameworkRef": FRAMEWORK_REF,
            "scope": {
                "purpose": _s(opt.get("purpose", "")) if opt.get("purpose") is not True else "",
                "orgUnits": _list(opt.get("org-units")),
                "threatTypes": _list(opt.get("threat-types")),
                "owner": _s(opt.get("owner", "")) if opt.get("owner") is not True else "",
                "assumptions": _s(opt.get("assumptions", "")) if opt.get("assumptions") is not True else "",
            },
            "tier": {"overall": None, "byFunction": {fid: None for fid in function_ids(core)}},
            "settings": settings,
            "created": ts, "updated": ts,
        },
        "assessments": assessments, "history": [], "snapshots": [], "actionItems": [],
    }
    append_history(store, "profile-created", rationale=f"Profile '{name}' initialised.",
                   actor=_s(opt.get("actor")) if isinstance(opt.get("actor"), (str, list)) else None, ts=ts)
    save_store(store, out, ts)

    print(f"Created {out}")
    print(f"  {len(assessments)} Subcategories seeded, all unrated and untargeted.")
    print(f"  Next: quickstart-target to set a baseline Target, then assess Current.")
    return 0


def _cmd_set(args):
    pos, opt = parse_flags(args)
    usage = ("usage: set <store.csfp> <subcategoryId> [--current N|null] [--target N|null] "
             "[--priority P] [--status S] [--applicability A] [--notes ...] [--evidence A B] "
             "[--reviewed] [--rationale '...']")
    if len(pos) < 2:
        raise ValueError(usage)
    path, sid = pos[0], pos[1]

    core = load_core(); index = index_subcategories(core)
    store = load_store(path)
    settings = store["profile"]["settings"]
    ts = _s(opt.get("ts")) if isinstance(opt.get("ts"), (str, list)) else _now()
    actor = _s(opt.get("actor")) if isinstance(opt.get("actor"), (str, list)) else None
    rationale = _s(opt.get("rationale")) if isinstance(opt.get("rationale"), (str, list)) else None

    if sid not in index:
        raise ValueError(f"Unknown Subcategory {sid!r} for framework {FRAMEWORK_REF}.")
    match = [a for a in store["assessments"] if a["subcategoryId"] == sid]
    if not match:
        raise ValueError(f"{sid} is not tracked in this Profile.")
    a = match[0]

    updates = []   # (field, new_value)
    if "current" in opt:
        updates.append(("current", _parse_rating(opt["current"], settings, "current")))
    if "target" in opt:
        updates.append(("target", _parse_rating(opt["target"], settings, "target")))
    if "priority" in opt:
        v = _s(opt["priority"])
        if v not in PRIORITIES:
            raise ValueError(f"--priority must be one of {', '.join(PRIORITIES)}, got {v!r}")
        updates.append(("priority", v))
    if "status" in opt:
        v = _s(opt["status"])
        if v not in STATUSES:
            raise ValueError(f"--status must be one of {', '.join(STATUSES)}, got {v!r}")
        updates.append(("status", v))
    if "applicability" in opt:
        v = _s(opt["applicability"])
        if v not in APPLICABILITY:
            raise ValueError(f"--applicability must be one of {', '.join(APPLICABILITY)}, got {v!r}")
        updates.append(("applicability", v))
    if "notes" in opt:
        updates.append(("notes", _s(opt["notes"]) if opt["notes"] is not True else ""))
    if "evidence" in opt:
        updates.append(("evidenceRefs", _list(opt["evidence"])))

    if not updates and not opt.get("reviewed"):
        raise ValueError(usage)

    # Refuse the whole change if any part of it is material and unexplained, before
    # mutating anything — a partially-applied edit would leave an incoherent audit trail.
    material = [(f, a.get(f), n) for f, n in updates if is_material(f, a.get(f), n)]
    if material and not rationale:
        detail = "; ".join(f"{f}: {o!r} -> {n!r}" for f, o, n in material)
        raise ValueError(
            f"--rationale is required for this change ({detail}). "
            f"Material changes are the ones you will be asked to defend later: rating moves, "
            f"gap acceptances, closure claims, and scoping a Subcategory out."
        )

    applied = 0
    for field, new in updates:
        old = a.get(field)
        if old == new:
            continue
        a[field] = new
        etype = {"current": "rating-changed", "target": "target-changed",
                 "status": "status-changed", "applicability": "applicability-changed"}.get(field, "field-changed")
        append_history(store, etype, subcategoryId=sid, field=field, frm=old, to=new,
                       rationale=rationale, actor=actor, ts=ts)
        applied += 1
        # lastReviewed tracks "when did a human last look at this outcome" — only a
        # Current move (or an explicit --reviewed) affirms that. Notes edits must not.
        if field == "current":
            a["lastReviewed"] = ts[:10]

    if opt.get("reviewed"):
        a["lastReviewed"] = ts[:10]
        if not any(f == "current" for f, _ in updates):
            append_history(store, "reviewed", subcategoryId=sid, rationale=rationale or "Reviewed; no change.",
                           actor=actor, ts=ts)
            applied += 1

    if not applied:
        print(f"{sid}: no change.")
        return 0

    save_store(store, path, ts)
    for field, new in updates:
        print(f"{sid}: {field} → {new!r}")
    if opt.get("reviewed"):
        print(f"{sid}: lastReviewed → {a['lastReviewed']}")
    return 0


def _cmd_set_tier(args):
    """Record a Tier characterization as a deliberate judgment, with its reasoning.

    Tiers are a headline capability of this skill and the executive dashboard has a whole
    section for them, but until this command existed `profile.tier` could only be reached
    by hand-editing the .csfp — which SKILL.md forbids and which bypasses history entirely.

    This command deliberately does NOT derive anything. It refuses a fractional Tier and
    it never looks at the ratings: a Tier calculated from coverage is the single most
    recognisable tell that a CSF report was not written by someone who reads NIST.
    """
    pos, opt = parse_flags(args)
    usage = ("usage: set-tier <store.csfp> [--overall N] [--function GV=N ...] "
             "--rationale '...' [--actor A]")
    path = _require_store(pos, usage)
    store = load_store(path)
    core = load_core()
    valid_fns = function_ids(core)
    levels = sorted(int(lv["tier"]) for lv in (core.get("tiers") or {}).get("levels", []))
    if not levels:
        raise ValueError("The bundled Core carries no Tier definitions; cannot set a Tier.")

    ts = _s(opt.get("ts")) if isinstance(opt.get("ts"), (str, list)) else _now()
    actor = _s(opt.get("actor")) if isinstance(opt.get("actor"), (str, list)) else None
    rationale = _s(opt.get("rationale")) if isinstance(opt.get("rationale"), (str, list)) else None
    if not rationale:
        raise ValueError("--rationale is required. A Tier is a judgment about the rigor of risk "
                         "governance; without the reasoning it is just a number someone picked.")

    def parse_tier(raw, label):
        v = _s(raw)
        if str(v).lower() in ("none", "null", "-"):
            return None
        try:
            n = int(str(v))
        except (TypeError, ValueError):
            raise ValueError(f"{label} must be a whole Tier {levels[0]}-{levels[-1]} "
                             f"(got {v!r}). Fractional Tiers do not exist.")
        if n not in levels:
            raise ValueError(f"{label} must be one of {levels}, got {n}.")
        return n

    tier = store["profile"].setdefault("tier", {"overall": None, "byFunction": {}})
    changes = []
    if "overall" in opt and opt["overall"] is not True:
        new = parse_tier(opt["overall"], "--overall")
        if tier.get("overall") != new:
            changes.append(("overall", tier.get("overall"), new))
            tier["overall"] = new
    for pair in _list(opt.get("function")):
        if "=" not in pair:
            raise ValueError(f"--function expects FID=N (e.g. GV=3), got {pair!r}.")
        fid, raw = pair.split("=", 1)
        fid = fid.strip().upper()
        if fid not in valid_fns:
            raise ValueError(f"Unknown Function {fid!r}; expected one of {valid_fns}.")
        new = parse_tier(raw, f"--function {fid}")
        if tier.setdefault("byFunction", {}).get(fid) != new:
            changes.append((f"byFunction.{fid}", tier["byFunction"].get(fid), new))
            tier["byFunction"][fid] = new

    if not changes:
        print("No change — the Tier characterization already reads that way.")
        return 0

    for field, old, new in changes:
        append_history(store, "tier-changed", field=field, frm=old, to=new,
                       rationale=rationale, actor=actor, ts=ts)
    save_store(store, path, ts)

    names = {int(lv["tier"]): lv.get("name", "") for lv in core["tiers"]["levels"]}
    for field, old, new in changes:
        def show(v):
            return f"Tier {v} ({names.get(v, '')})" if v is not None else "not characterized"
        print(f"{field}: {show(old)} → {show(new)}")
    print("  Recorded as a judgment, not a calculation. Tiers are never derived from ratings.")
    return 0


def _cmd_quickstart_target(args):
    pos, opt = parse_flags(args)
    path = _require_store(pos, "usage: quickstart-target <store.csfp> [--level N] [--force] [--rationale ...]")
    core = load_core(); index = index_subcategories(core)
    store = load_store(path)
    settings = store["profile"]["settings"]
    ts = _s(opt.get("ts")) if isinstance(opt.get("ts"), (str, list)) else _now()
    actor = _s(opt.get("actor")) if isinstance(opt.get("actor"), (str, list)) else None

    level = QUICKSTART_DEFAULT_LEVEL if "level" not in opt else _parse_rating(opt["level"], settings, "level")
    if level is None:
        raise ValueError("--level must be a rating, not null.")
    rationale = (_s(opt.get("rationale")) if isinstance(opt.get("rationale"), (str, list))
                 else f"Quick-start default Target applied at level {level} "
                      f"({settings['scale']['labels'].get(str(level), level)}).")

    # A Target someone already set deliberately is a decision with reasoning behind it.
    # Quick-start is a *seeding* command: it fills in the blanks, it does not overrule
    # judgment. Overwriting PR.AA-01's considered Target of 0 back to 2 — and logging a
    # generic quick-start rationale over the user's own — silently destroys the thing the
    # rationale requirement exists to protect. --force is the deliberate way to reset.
    force = bool(opt.get("force"))
    changed, untouched, skipped, preserved = 0, 0, 0, []
    for a in store["assessments"]:
        if a.get("applicability") != "in-scope":
            skipped += 1
            continue
        if a.get("target") == level:
            untouched += 1
            continue
        old = a.get("target")
        if old is not None and not force:
            preserved.append(a["subcategoryId"])
            continue
        a["target"] = level
        append_history(store, "target-changed", subcategoryId=a["subcategoryId"], field="target",
                       frm=old, to=level, rationale=rationale, actor=actor, ts=ts)
        changed += 1

    if not changed:
        # Idempotent: a true no-op writes nothing, so re-running cannot pad the history.
        print(f"No change — all {untouched} in-scope Targets are already at level {level}.")
        if preserved:
            print(f"  {len(preserved)} Target{'s' if len(preserved) != 1 else ''} already set "
                  f"deliberately and left alone. Re-run with --force to reset "
                  f"{'them' if len(preserved) != 1 else 'it'} to {level}.")
        return 0

    save_store(store, path, ts)
    label = settings["scale"]["labels"].get(str(level), str(level))
    print(f"Set {changed} Target{'s' if changed != 1 else ''} to level {level} ({label}).")
    if untouched:
        print(f"  {untouched} already at that level.")
    if preserved:
        shown = ", ".join(preserved[:6]) + (f", +{len(preserved) - 6} more" if len(preserved) > 6 else "")
        print(f"  {len(preserved)} left alone — already set deliberately ({shown}).")
        print(f"  Re-run with --force to overwrite {'those' if len(preserved) != 1 else 'that'} too.")
    if skipped:
        print(f"  {skipped} skipped (not applicable).")
    print("  Now tune Targets by risk — not every outcome warrants the same Target.")
    return 0


def _cmd_snapshot(args):
    pos, opt = parse_flags(args)
    path = _require_store(pos, "usage: snapshot <store.csfp> --label 'Q2 2026 Assessment' [--note ...]")
    if "label" not in opt:
        raise ValueError("usage: snapshot <store.csfp> --label 'Q2 2026 Assessment' [--note ...]")
    core = load_core(); index = index_subcategories(core)
    store = load_store(path)
    ts = _s(opt.get("ts")) if isinstance(opt.get("ts"), (str, list)) else _now()
    label = _s(opt["label"])

    snap = {
        "id": re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-"),
        "label": label, "ts": ts,
        "note": _s(opt.get("note", "")) if opt.get("note") is not True else "",
        "assessments": copy.deepcopy(store["assessments"]),
        # Action items are frozen too: without them the diff cannot report work opened
        # and closed, which is half of "what changed since last review".
        "actionItems": copy.deepcopy(store["actionItems"]),
        "rollups": rollups(store, index, core),
    }
    store["snapshots"].append(snap)
    append_history(store, "snapshot-created", rationale=snap["note"] or label,
                   actor=_s(opt.get("actor")) if isinstance(opt.get("actor"), (str, list)) else None, ts=ts)
    save_store(store, path, ts)

    cov = snap["rollups"]["coverage"]["overall"]
    pct = "not yet targeted" if cov["percent"] is None else f"{cov['percent']:.1f}% ({cov['n']}/{cov['d']})"
    print(f"Snapshot '{label}' saved — coverage {pct}, {len(store['actionItems'])} action items.")
    return 0


def _cmd_diff(args):
    pos, opt = parse_flags(args)
    path = _require_store(pos, "usage: diff <store.csfp> [--label L] [--json]")
    core = load_core(); index = index_subcategories(core)
    store = load_store(path)
    label = _s(opt.get("label")) if isinstance(opt.get("label"), (str, list)) else None
    d = compute_diff(store, index, core, label)
    if d is None:
        print("No snapshots yet — nothing to compare against.")
        return 0
    if opt.get("json"):
        json.dump(d, sys.stdout, indent=2, ensure_ascii=False); sys.stdout.write("\n")
        return 0

    print(f"Since '{d['against']['label']}' ({d['against']['ts']}):")
    ov = d["coverage"]["overall"]
    if ov["delta"] is None:
        print("  Coverage: not comparable (one side has nothing targeted).")
    else:
        print(f"  Coverage: {ov['from']:.1f}% → {ov['to']:.1f}% ({ov['delta']:+.1f} pts)")
    if not d["assessments"]["changed"]:
        print("  No Subcategory changes.")
    for c in d["assessments"]["changed"]:
        print(f"  {c['subcategoryId']}: {c['field']} {c['from']!r} → {c['to']!r}")
    for i in d["actionItems"]["added"]:
        print(f"  + action {i['id']}: {i['title']}")
    for i in d["actionItems"]["closed"]:
        print(f"  ✓ action {i['id']} closed: {i['title']}")
    return 0


def _next_action_id(store) -> str:
    used = [int(m.group(1)) for i in store["actionItems"]
            if (m := re.match(r"A-(\d+)$", str(i.get("id", ""))))]
    return f"A-{max(used, default=0) + 1:03d}"


def _cmd_action(args):
    pos, opt = parse_flags(args)
    usage = ("usage: action add <store.csfp> --title T [--linked A B] [--owner O] [--milestone M] "
             "[--target-date D] [--notes ...]\n"
             "       action update <store.csfp> <id> [--title ...] [--owner ...] [--status S] ...\n"
             "       action close <store.csfp> <id> --rationale '...'")
    if len(pos) < 2:
        raise ValueError(usage)
    sub, path = pos[0], pos[1]
    core = load_core(); index = index_subcategories(core)
    store = load_store(path)
    ts = _s(opt.get("ts")) if isinstance(opt.get("ts"), (str, list)) else _now()
    actor = _s(opt.get("actor")) if isinstance(opt.get("actor"), (str, list)) else None
    rationale = _s(opt.get("rationale")) if isinstance(opt.get("rationale"), (str, list)) else None

    def _fields(item):
        for flag, key in (("title", "title"), ("owner", "owner"), ("milestone", "milestone"),
                          ("target-date", "targetDate"), ("notes", "notes")):
            if flag in opt:
                item[key] = _s(opt[flag]) if opt[flag] is not True else ""
        if "linked" in opt:
            linked = _list(opt["linked"])
            for sid in linked:
                if sid not in index:
                    raise ValueError(f"Unknown Subcategory {sid!r} in --linked.")
            item["linkedSubcategoryIds"] = linked
        if "status" in opt:
            v = _s(opt["status"])
            if v not in ACTION_STATUSES:
                raise ValueError(f"--status must be one of {', '.join(ACTION_STATUSES)}, got {v!r}")
            item["status"] = v
        return item

    if sub == "add":
        if "title" not in opt:
            raise ValueError(usage)
        item = _fields({"id": _next_action_id(store), "title": "", "linkedSubcategoryIds": [],
                        "owner": "", "milestone": "", "targetDate": "", "status": "open", "notes": ""})
        store["actionItems"].append(item)
        append_history(store, "action-added", actionId=item["id"],
                       rationale=rationale or f"Action '{item['title']}' opened.", actor=actor, ts=ts)
        save_store(store, path, ts)
        print(f"Added {item['id']}: {item['title']}")
        if not item["owner"]:
            print("  Warning: unowned. An action without an owner is a wish.")
        return 0

    if len(pos) < 3:
        raise ValueError(usage)
    aid = pos[2]
    match = [i for i in store["actionItems"] if i.get("id") == aid]
    if not match:
        raise ValueError(f"No action item {aid!r}.")
    item = match[0]

    if sub == "close":
        if item.get("status") == "closed":
            print(f"{aid} is already closed.")
            return 0
        if not rationale:
            raise ValueError(f"--rationale is required to close {aid} — closure is a completion claim.")
        frm = item.get("status")
        item["status"] = "closed"
        append_history(store, "action-closed", actionId=aid, field="status", frm=frm, to="closed",
                       rationale=rationale, actor=actor, ts=ts)
        save_store(store, path, ts)
        print(f"Closed {aid}: {item['title']}")
        return 0

    if sub == "update":
        before = copy.deepcopy(item)
        _fields(item)
        if item == before:
            print(f"{aid}: no change.")
            return 0
        if item.get("status") == "closed" and before.get("status") != "closed" and not rationale:
            raise ValueError(f"--rationale is required to close {aid} — closure is a completion claim.")
        for k, v in item.items():
            if before.get(k) != v:
                append_history(store, "action-updated", actionId=aid, field=k, frm=before.get(k),
                               to=v, rationale=rationale, actor=actor, ts=ts)
        save_store(store, path, ts)
        print(f"Updated {aid}: {item['title']}")
        return 0

    raise ValueError(usage)


def _cmd_analyze(args):
    pos, opt = parse_flags(args)
    path = _require_store(pos, "usage: analyze <store.csfp> [--today YYYY-MM-DD] [--top N] [--out F]")
    core = load_core(); index = index_subcategories(core)
    store = load_store(path)

    problems = check_store(store, index)
    if problems:
        raise ValueError("Profile failed validation: " + "; ".join(problems))

    today = _s(opt.get("today")) if isinstance(opt.get("today"), (str, list)) else _today()
    top = int(_s(opt.get("top"))) if isinstance(opt.get("top"), (str, list)) else 10
    settings = store["profile"]["settings"]
    prof = store["profile"]

    tiers = copy.deepcopy(core.get("tiers") or {})
    tiers["profile"] = prof.get("tier", {})

    guidance = load_guidance()
    gaps = compute_gaps(store["assessments"], settings, index)
    for row in gaps:
        g = render_guidance(row, settings, guidance)
        if g:
            row["guidance"] = g

    out = {
        "generated": {"today": today, "engine": "profile_analysis.py", "schemaVersion": SCHEMA_VERSION},
        "profile": {
            "id": prof.get("id"), "name": prof.get("name"), "frameworkRef": prof.get("frameworkRef"),
            "scope": prof.get("scope", {}), "settings": settings,
            "created": prof.get("created"), "updated": prof.get("updated"),
        },
        "framework": {
            "id": core.get("id"), "name": core.get("name"), "version": core.get("version"),
            "subcategories": len(index),
            "functions": [{"id": f["id"], "name": f.get("name"),
                           "categories": [{"id": c["id"], "name": c.get("name")}
                                          for c in f.get("categories", [])]}
                          for f in core["hierarchy"]],
        },
        "tracked": len(store["assessments"]),
        "coverage": compute_coverage(store["assessments"], index, core),
        "completeness": compute_completeness(store["assessments"], index, core),
        "gaps": gaps,
        "playbook": build_playbook(gaps, settings, guidance, top),
        "attention": attention_lists(store, index, today, top),
        "actionItems": {
            "items": store["actionItems"],
            "summary": {
                "total": len(store["actionItems"]),
                "open": sum(1 for i in store["actionItems"] if i.get("status") == "open"),
                "inProgress": sum(1 for i in store["actionItems"] if i.get("status") == "in-progress"),
                "closed": sum(1 for i in store["actionItems"] if i.get("status") == "closed"),
            },
        },
        "tiers": tiers,
        "snapshots": [{"id": s.get("id"), "label": s.get("label"), "ts": s.get("ts")}
                      for s in store.get("snapshots", [])],
        "diff": compute_diff(store, index, core),
        "history": store["history"][-50:],
    }

    text = json.dumps(out, indent=2, ensure_ascii=False)
    dest = _s(opt.get("out")) if isinstance(opt.get("out"), (str, list)) else None
    if dest:
        with open(dest, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
        print(f"Wrote {dest}")
    else:
        sys.stdout.write(text + "\n")
    return 0


# The exact contract consumed by risk-register's `score_register.py import-gaps`
# (skills/risk-register/references/csf-import.md). Column order is load-bearing.
#
# NOTE the misnomer: that contract names the rating columns current_tier/target_tier.
# These carry per-Subcategory ACHIEVEMENT RATINGS (0-3), not CSF Tiers. Tiers are a
# Profile-level rigor characterization and are never per-Subcategory. The columns are
# emitted as-named so the existing importer keeps working; renaming them is a v2 change
# made across both skills at once.
EXPORT_COLUMNS = ["subcategory_id", "function_id", "category_id", "current_tier",
                  "target_tier", "priority", "subcategory_text", "note"]


def _cmd_export_gaps(args):
    pos, opt = parse_flags(args)
    path = _require_store(pos, "usage: export-gaps <store.csfp> [--out gaps.csv]")
    core = load_core(); index = index_subcategories(core)
    store = load_store(path)
    rows = compute_gaps(store["assessments"], store["profile"]["settings"], index)

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(EXPORT_COLUMNS)
    for r in rows:
        note = " · ".join(x for x in [
            f"CSF gap: {r['current'] if r['current'] is not None else 'unassessed'}"
            f" → {r['target']} on a 0-{store['profile']['settings']['scale']['max']} achievement scale",
            f"status: {r['status']}",
            (next(iter(r["examples"]), "") or "")[:160],
        ] if x)
        w.writerow([r["subcategoryId"], r["functionId"], r["categoryId"],
                    r["current"] if r["current"] is not None else 0, r["target"],
                    r["priority"], r["text"], note])

    dest = _s(opt.get("out")) if isinstance(opt.get("out"), (str, list)) else None
    if dest:
        with open(dest, "w", newline="", encoding="utf-8") as fh:
            fh.write(buf.getvalue())
        print(f"Wrote {dest} — {len(rows)} gap rows.")
        # Both commands, in order. `--into` alone is a preview that writes nothing, so a
        # message showing only that step invites the reader to believe the register was
        # updated when it was not.
        print("  Feed to risk-register — preview first, then apply:")
        print(f"    python3 ../risk-register/scripts/score_register.py import-gaps {dest} "
              f"--into <register.rr>")
        print(f"    python3 ../risk-register/scripts/score_register.py import-gaps {dest} "
              f"--into <register.rr> --write")
        print("  Imported risks land provisional: framework wording and seeded scores, held out")
        print("  of board views until reworded with `set-text`.")
    else:
        sys.stdout.write(buf.getvalue())
    return 0


# --- Self-test ---------------------------------------------------------------

def _cmd_self_test(_args):
    """Assert engine math against the shipped fixture, with hand-computed expectations.

    Expectations here were derived by hand from examples/example-profile.csfp BEFORE the
    code was written. If a change makes one fail, the burden is on the change.
    """
    core = load_core(); index = index_subcategories(core)
    failures: list[str] = []
    checks = 0

    def ok(cond, label):
        nonlocal checks
        checks += 1
        if not cond:
            failures.append(label)

    def eq(got, want, label):
        nonlocal checks
        checks += 1
        if got != want:
            failures.append(f"{label}: expected {want!r}, got {got!r}")

    def close(got, want, label, tol=1e-9):
        nonlocal checks
        checks += 1
        if got is None or abs(got - want) > tol:
            failures.append(f"{label}: expected {want!r}, got {got!r}")

    # --- Core integrity ---
    eq(check_core(core), [], "core integrity")
    eq(len(index), 106, "core index size")
    ok(all(index[s]["examples"] for s in index), "every Subcategory has an Implementation Example")

    # --- Fixture loads and validates ---
    store = load_store(FIXTURE)
    eq(check_store(store, index), [], "fixture validates")
    settings = store["profile"]["settings"]
    A = {a["subcategoryId"]: a for a in store["assessments"]}
    eq(len(A), 10, "fixture assessment count")

    # --- Gaps: hand-computed ---
    # gap = max(0, target - (current or 0)); no gap where target is null.
    eq(gap_of(A["GV.OC-01"]), 1, "gap GV.OC-01 (2->3)")
    eq(gap_of(A["GV.RM-01"]), 2, "gap GV.RM-01 (1->3)")
    eq(gap_of(A["GV.SC-01"]), 2, "gap GV.SC-01 (0->2)")
    eq(gap_of(A["ID.AM-01"]), 0, "gap ID.AM-01 (3->3)")
    eq(gap_of(A["ID.RA-01"]), 2, "gap ID.RA-01 (null current treated as 0, ->2)")
    eq(gap_of(A["PR.DS-01"]), 3, "gap PR.DS-01 (0->3)")
    eq(gap_of(A["DE.CM-01"]), None, "gap DE.CM-01 is None (untargeted, not zero-gap)")

    # --- Prioritized scores: gap x priorityWeight x functionWeight (all fn weights 1) ---
    eq(prioritized_score(A["GV.OC-01"], settings, index), 3, "score GV.OC-01 = 1 x high(3)")
    eq(prioritized_score(A["GV.RM-01"], settings, index), 8, "score GV.RM-01 = 2 x critical(4)")
    eq(prioritized_score(A["GV.SC-01"], settings, index), 4, "score GV.SC-01 = 2 x medium(2)")
    eq(prioritized_score(A["ID.RA-01"], settings, index), 6, "score ID.RA-01 = 2 x high(3)")
    eq(prioritized_score(A["PR.AA-01"], settings, index), 8, "score PR.AA-01 = 2 x critical(4)")
    eq(prioritized_score(A["PR.DS-01"], settings, index), 9, "score PR.DS-01 = 3 x high(3)")

    gaps = compute_gaps(store["assessments"], settings, index)
    eq([g["subcategoryId"] for g in gaps],
       ["PR.DS-01", "GV.RM-01", "PR.AA-01", "ID.RA-01", "GV.SC-01", "GV.OC-01"],
       "gap ordering (score desc, then id asc as tie-break at 8)")
    eq(len(gaps), 6, "gap row count == in-scope assessments with gap > 0")
    ok(all(g["text"] and g["examples"] for g in gaps), "every gap row carries text and >=1 example")
    ok(all(a["subcategoryId"] != "DE.AE-02" for a in gaps), "not-applicable excluded from gaps")

    # --- Coverage: N = sum(min(current or 0, target)), D = sum(target) over targeted in-scope ---
    cov = compute_coverage(store["assessments"], index, core)
    eq(cov["overall"]["d"], 21, "overall denominator (3+3+2 +3+2 +3+2+3)")
    eq(cov["overall"]["n"], 9, "overall numerator (2+1+0 +3+0 +1+2+0)")
    close(cov["overall"]["percent"], 9 / 21 * 100, "overall coverage %")
    close(cov["byFunction"]["GV"]["percent"], 3 / 8 * 100, "GV coverage % (3/8)")
    close(cov["byFunction"]["ID"]["percent"], 3 / 5 * 100, "ID coverage % (3/5)")
    close(cov["byFunction"]["PR"]["percent"], 3 / 8 * 100, "PR coverage % (3/8)")
    # DE has one untargeted and one not-applicable assessment => nothing targeted.
    eq(cov["byFunction"]["DE"]["percent"], None, "DE coverage is null (nothing targeted), NOT 100%")
    eq(cov["byFunction"]["DE"]["d"], 0, "DE denominator 0")
    eq(cov["byFunction"]["RS"]["percent"], None, "RS coverage is null (no assessments)")
    eq(cov["byFunction"]["RC"]["percent"], None, "RC coverage is null (no assessments)")
    eq(sorted(cov["byFunction"]), sorted(function_ids(core)), "every Function present in coverage")
    close(cov["byCategory"]["PR.AA"]["percent"], 3 / 5 * 100, "PR.AA category coverage (3/5)")
    eq(cov["byCategory"]["ID.AM"]["percent"], 100.0, "ID.AM fully covered (3/3)")
    eq(cov["byCategory"]["GV.SC"]["percent"], 0.0, "GV.SC 0% — assessed at 0, NOT null")

    # The distinction the whole schema exists to protect: rated-zero is 0%, untargeted is null.
    ok(cov["byCategory"]["GV.SC"]["percent"] == 0.0 and cov["byFunction"]["DE"]["percent"] is None,
       "rated-0 (0%) and untargeted (null) are distinguishable")

    # --- Completeness ---
    comp = compute_completeness(store["assessments"], index, core)
    eq(comp["overall"], {"total": 10, "inScope": 9, "notApplicable": 1, "assessed": 8, "targeted": 8},
       "overall completeness")

    # --- A freshly initialised Profile must not flatter ---
    fresh = {"assessments": [{"subcategoryId": sid, "applicability": "in-scope", "current": None,
                              "target": None, "priority": "medium", "status": "not-started"}
                             for sid in index]}
    fresh_cov = compute_coverage(fresh["assessments"], index, core)
    eq(fresh_cov["overall"]["percent"], None, "fresh Profile coverage is null, NOT 100%")
    ok(all(v["percent"] is None for v in fresh_cov["byFunction"].values()),
       "fresh Profile: every Function null")
    eq(compute_gaps(fresh["assessments"], settings, index), [], "fresh Profile has no gaps")

    # --- Attention lists (today passed in, never the clock) ---
    att = attention_lists(store, index, "2026-07-26", top=10)
    eq([g["subcategoryId"] for g in att["largestGaps"]],
       ["PR.DS-01", "GV.RM-01", "PR.AA-01", "ID.RA-01", "GV.SC-01", "GV.OC-01"], "largestGaps order")
    eq([r["subcategoryId"] for r in att["neverReviewed"]], ["GV.SC-01", "ID.RA-01"], "neverReviewed")
    eq([r["subcategoryId"] for r in att["stalest"]][:3], ["PR.DS-01", "PR.AA-01", "GV.RM-01"],
       "stalest ordering (oldest first)")
    ok(all(r["subcategoryId"] not in ("GV.SC-01", "ID.RA-01") for r in att["stalest"]),
       "never-reviewed excluded from stalest")
    eq([i["id"] for i in att["unownedActions"]], ["A-002"], "unowned actions")
    eq([i["id"] for i in att["pastDueActions"]], ["A-003"], "past-due actions (A-004 closed, excluded)")
    eq([r["subcategoryId"] for r in att["acceptedGaps"]], ["PR.DS-01"], "accepted gaps")

    # today is honoured, not the wall clock
    eq([i["id"] for i in attention_lists(store, index, "2026-01-01")["pastDueActions"]], [],
       "no past-due when today precedes every target date")
    eq([i["id"] for i in attention_lists(store, index, "2027-01-01")["pastDueActions"]],
       ["A-001", "A-002", "A-003"], "all open items past due when today is later")

    # --- Diff against the fixture's Q1 snapshot ---
    d = compute_diff(store, index, core)
    eq(d["against"]["label"], "Q1 2026 Baseline", "diff compares to latest snapshot")
    changed = {(c["subcategoryId"], c["field"]): (c["from"], c["to"]) for c in d["assessments"]["changed"]}
    eq(changed.get(("GV.OC-01", "current")), (1, 2), "diff sees GV.OC-01 current 1->2")
    eq(changed.get(("ID.AM-01", "current")), (2, 3), "diff sees ID.AM-01 current 2->3")
    eq(changed.get(("ID.AM-01", "status")), ("in-progress", "met"), "diff sees ID.AM-01 status change")
    close(d["coverage"]["overall"]["from"], 7 / 21 * 100, "diff coverage from (7/21)")
    close(d["coverage"]["overall"]["to"], 9 / 21 * 100, "diff coverage to (9/21)")
    close(d["coverage"]["overall"]["delta"], (9 - 7) / 21 * 100, "diff coverage delta")
    eq([i["id"] for i in d["actionItems"]["added"]], ["A-002"], "diff sees A-002 added since snapshot")
    eq([i["id"] for i in d["actionItems"]["closed"]], ["A-004"], "diff sees A-004 closed since snapshot")

    # Diff against identical state reports nothing.
    same = copy.deepcopy(store)
    same["snapshots"] = [{"id": "now", "label": "Now", "ts": "2026-07-26T00:00:00Z",
                          "assessments": copy.deepcopy(store["assessments"]),
                          "actionItems": copy.deepcopy(store["actionItems"]), "rollups": {}}]
    d2 = compute_diff(same, index, core)
    eq(d2["assessments"]["changed"], [], "diff against identical state: no assessment changes")
    eq(d2["coverage"]["overall"]["delta"], 0.0, "diff against identical state: zero coverage delta")
    eq(d2["actionItems"]["added"], [], "diff against identical state: no new actions")
    eq(d2["actionItems"]["closed"], [], "diff against identical state: no newly closed actions")

    # --- Material-change classification ---
    ok(is_material("current", 1, 2), "current move is material")
    ok(is_material("target", 2, 3), "target move is material")
    ok(is_material("status", "in-progress", "accepted-gap"), "accepting a gap is material")
    ok(is_material("status", "in-progress", "met"), "claiming met is material")
    ok(is_material("applicability", "in-scope", "not-applicable"), "scoping out is material")
    ok(not is_material("notes", "a", "b"), "notes edit is not material")
    ok(not is_material("priority", "low", "high"), "priority change is not material")
    ok(not is_material("current", 2, 2), "no-op is not material")

    # --- Rating parsing ---
    eq(_parse_rating("2", settings, "current"), 2, "parse rating '2'")
    eq(_parse_rating("null", settings, "current"), None, "parse rating 'null'")
    for bad, why in (("4", "above scale"), ("-1", "below scale"), ("abc", "non-numeric")):
        try:
            _parse_rating(bad, settings, "current")
            failures.append(f"rating {bad!r} ({why}) should have been rejected")
        except ValueError:
            pass
        checks += 1
    try:
        _parse_rating("N/A", settings, "current")
        failures.append("'N/A' should be rejected with a pointer to --applicability")
    except ValueError as exc:
        ok("applicability" in str(exc), "'N/A' error points at --applicability")
    checks += 1

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

    # --- Export contract ---
    eq(EXPORT_COLUMNS,
       ["subcategory_id", "function_id", "category_id", "current_tier", "target_tier",
        "priority", "subcategory_text", "note"],
       "export columns match the risk-register import contract exactly")

    print(f"self-test: {checks - len(failures)}/{checks} checks passed")
    if failures:
        print("\nFAILED:", file=sys.stderr)
        for f in failures:
            print(f"  - {f}", file=sys.stderr)
        return 1
    return 0


COMMANDS = {
    "validate": _cmd_validate, "self-test": _cmd_self_test,
    "init": _cmd_init, "set": _cmd_set, "set-tier": _cmd_set_tier,
    "quickstart-target": _cmd_quickstart_target,
    "snapshot": _cmd_snapshot, "diff": _cmd_diff, "action": _cmd_action,
    "analyze": _cmd_analyze, "export-gaps": _cmd_export_gaps,
}


def main(argv: list[str]) -> int:
    if len(argv) < 2 or argv[1] not in COMMANDS:
        print(__doc__)
        return 0 if (len(argv) >= 2 and argv[1] in ("-h", "--help")) else 2
    return COMMANDS[argv[1]](argv[2:])


if __name__ == "__main__":
    try:
        rc = main(sys.argv)
    except (ValueError, FileNotFoundError, KeyError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        rc = 1
    raise SystemExit(rc)
