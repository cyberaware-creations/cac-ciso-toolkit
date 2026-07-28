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
  analyze      <store.csfp> [--today D] [--top N] [--queue-top N] [--out F]   Emit the complete derived JSON.
  diff         <store.csfp> [--label L] [--json]   Compare current state to a snapshot.
  export-gaps  <store.csfp> [--out F]              Gap CSV for `risk-register import-gaps`.
  queue        <store.csfp> [--top N] [--json]      What to confirm next, ranked.
  self-test                                        Assert engine math against the fixture.

Mutations (each appends an append-only history event and rewrites the store):
  init              --name N --out F [--purpose ...] [--owner ...] [--org-units A B]
                    [--threat-types X Y] [--assumptions ...] [--id ID] [--ts TS]
  set               <store.csfp> <subcategoryId> [--current N|null] [--target N|null]
                    [--priority P] [--status S] [--applicability A] [--notes ...]
                    [--evidence A B] [--reviewed] [--rationale ...] [--actor A] [--ts TS]
                    [--source in-NNNN] [--confirmed-by NAME]   (both REQUIRED with --current)
  set-tier          <store.csfp> [--overall N] [--function GV=N ...] --rationale ... [--actor A]
  quickstart-target <store.csfp> [--level N] [--force] [--rationale ...] [--actor A] [--ts TS]
  snapshot          <store.csfp> --label 'Q2 2026 Assessment' [--note ...] [--ts TS]
  action add        <store.csfp> --title T [--linked A B] [--owner O] [--milestone M]
                    [--target-date D] [--notes ...]
  action update     <store.csfp> <id> [--title ...] [--owner ...] [--target-date ...] ...
  action close      <store.csfp> <id> --rationale ...
  intake add        <store.csfp> --label '...' --subjects ID.AM-01 ID.AM-02
                    [--source-date D] [--recorded-by NAME] [--ts TS]
  intake list       <store.csfp> [--json]

Usage:
  python3 profile_analysis.py init --name "Acme Corp" --out acme.csfp --owner CISO
  python3 profile_analysis.py quickstart-target acme.csfp
  python3 profile_analysis.py set acme.csfp PR.AA-01 --current 1 --rationale "SSO live for corp apps"
  python3 profile_analysis.py analyze acme.csfp --today 2026-07-26 > analysis.json
  python3 profile_analysis.py self-test
"""

from __future__ import annotations

import contextlib
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
DEFAULT_COLD_START_RANK = os.path.join(_SKILL_ROOT, "references", "cold-start-rank.json")
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
        # The write path always produces ts[:10], but this file defends against a
        # hand-edited or externally-converted store elsewhere, and an unvalidated
        # confirmedAt would crash _days_between's strptime with a bare ValueError
        # instead of a labelled problem here.
        for field in ("confirmedAt",):
            v = a.get(field)
            if v is None:
                continue
            if not _is_iso_date(v):
                problems.append(f"{sid}: {field} {v!r} is not a zero-padded ISO date (YYYY-MM-DD)")

    for item in store["actionItems"]:
        if item.get("status") not in ACTION_STATUSES:
            problems.append(f"action {item.get('id')}: status {item.get('status')!r} not in {ACTION_STATUSES}")
        for sid in item.get("linkedSubcategoryIds", []):
            if sid not in index:
                problems.append(f"action {item.get('id')}: unknown Subcategory {sid!r}")

    # sourceDate and recordedAt are guarded by _iso_date on the write path, but this
    # loop is what protects a store that arrived some other way — and the revisit
    # comparison in derive_evidence depends on sourceDate being lexically sortable.
    for r in store.get("intake", []):
        for field in ("sourceDate", "recordedAt"):
            v = r.get(field)
            if v is None:
                continue
            if not _is_iso_date(v):
                problems.append(f"intake {r.get('id')}: {field} {v!r} is not a zero-padded ISO date (YYYY-MM-DD)")
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
    if rationale:
        ev["rationale"] = rationale
    if source:
        ev["source"] = source
    if confirmedBy:
        ev["confirmedBy"] = confirmedBy
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
            # No exception for the record cited as this rating's own source: in a
            # coherent store its sourceDate is never after confirmedAt (you cannot
            # decide a rating from a conversation that hasn't happened yet), so the
            # comparison is a no-op there. If it DOES fire on the cited source, that
            # means the store holds an impossible date pair, and surfacing it as a
            # revisit — go look at this again — is correct; suppressing it would
            # hide the only signal a user gets that something is wrong.
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

    # Newest material first, then id ascending. Two passes because the primary key
    # is a date string and cannot be negated — and a single reverse=True over the
    # tuple would reverse the tie-break too, handing a user ID.AM-03 before ID.AM-01.
    for rows in (revisit, pending):
        rows.sort(key=lambda r: r["subcategoryId"])
        rows.sort(key=lambda r: r["newestSourceDate"], reverse=True)

    def _split(subset: list[dict]) -> dict:
        out = {"confirmed": 0, "evidencePending": 0, "unrated": 0, "notApplicable": 0,
               "attributed": 0, "unattributed": 0, "total": len(subset)}
        key = {"confirmed": "confirmed", "evidence-pending": "evidencePending",
               "unrated": "unrated", "not-applicable": "notApplicable"}
        for a in subset:
            state = states[a["subcategoryId"]]
            out[key[state]] += 1
            if state == "confirmed":
                # Confirmed means a rating exists. Attributed means we also know who
                # decided it, when, and from what. A v1 rating is the first without
                # the second, and reporting them as one number is the failure this
                # whole schema exists to prevent.
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

    Subjects carry an id and a state, deliberately not the outcome text. This is the
    one block that grows without bound — intake accretes for the life of the Profile
    and is never pruned — and the text is duplicated from `gaps`/`queue` anyway. A
    renderer that later needs it should get a lookup map, not a copy per subject.
    """
    rows = []
    for r in sorted(intake or [], key=lambda x: (x.get("sourceDate") or "", x.get("id") or ""),
                    reverse=True):
        subjects = [{"subcategoryId": sid, "state": states.get(sid, "unrated")}
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


def build_queue(assessments: list[dict], intake: list[dict], evidence: dict,
                index: dict, rank: dict, top: int | None = None) -> list[dict]:
    """What to confirm next, in three bands.

    Band order is fixed: evidence-pending, then revisit, then cold-start rank.
    Material you already have beats material you have to go find, and a rating a
    new conversation has called into question beats one nobody has looked at.

    A queue item carries the SOURCE and the DATE and nothing else. It must never
    carry a tier, a proposed tier, or a confidence — presenting a conclusion and
    asking for confirmation is how inference gets laundered as judgment, and a
    rubber-stamped rating is worse than an unrated one because it looks like
    evidence. The absence of a rating here is the feature.
    """
    by_subject = intake_by_subject(intake)
    states = evidence["states"]
    by_id = {a["subcategoryId"]: a for a in assessments}

    def _sources(sid):
        # Newest first: the most recent conversation is the one a human can still recall.
        return [{"id": r["id"], "label": r["label"], "sourceDate": r["sourceDate"],
                 "recordedBy": r.get("recordedBy", "")}
                for r in reversed(by_subject.get(sid, []))]

    def _row(sid, band):
        return {
            "subcategoryId": sid,
            "text": (index.get(sid) or {}).get("text", ""),
            "functionId": (index.get(sid) or {}).get("functionId", ""),
            "band": band,
            "coldStartRank": rank.get(sid),
            "sources": _sources(sid),
            "confirmedAt": by_id.get(sid, {}).get("confirmedAt"),
            "target": by_id.get(sid, {}).get("target"),
            # Explicitly null, and asserted by the tests. The confirmation session
            # asks a question; it does not present an answer for ratification.
            "tier": None,
        }

    # Two-pass stable sorts throughout. A single reverse=True over a (date, id)
    # tuple would reverse the tie-break too — see the same fix in derive_evidence.
    #
    # rank[sid], not rank.get(sid, ...): resolve_rank positions every id in index,
    # and every sid reaching this point came from an assessment check_store already
    # validated against index. A missing rank is an internal invariant broken, not
    # a case to paper over with a fallback — the same call this file already made
    # for _split's key[state] lookup. A silent default would sort the row to the
    # bottom with no signal, far from wherever the real bug is.
    pending = list(evidence["pending"])
    pending.sort(key=lambda r: (rank[r["subcategoryId"]], r["subcategoryId"]))
    pending.sort(key=lambda r: r["newestSourceDate"], reverse=True)

    revisit = list(evidence["revisit"])
    revisit.sort(key=lambda r: (rank[r["subcategoryId"]], r["subcategoryId"]))
    revisit.sort(key=lambda r: r["newestSourceDate"], reverse=True)

    cold = sorted((sid for sid, s in states.items() if s == "unrated"),
                  key=lambda sid: (rank[sid], sid))

    rows = ([_row(r["subcategoryId"], "evidence-pending") for r in pending]
            + [_row(r["subcategoryId"], "revisit") for r in revisit]
            + [_row(sid, "cold-start") for sid in cold])
    return rows if top is None else rows[:top]


# --- Authored guidance -------------------------------------------------------

def load_guidance(path: str | None = None) -> dict:
    """Load the harvested authored guidance. Absent is fine — guidance is additive."""
    try:
        with open(path or DEFAULT_GUIDANCE, encoding="utf-8") as fh:
            return json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


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
    # Rank values must be numbers. A hand-edited file that quotes them sorts
    # lexicographically instead — "10" before "2" — which loads, passes every
    # structural check, and silently produces a wrong queue order. Fail loudly.
    bad = sorted(sid for sid, v in ranked.items() if not isinstance(v, int) or isinstance(v, bool))
    if bad:
        raise ValueError(f"cold-start rank values must be integers; {', '.join(bad)} "
                         f"are not. Quoted numbers sort as text and would silently "
                         f"reorder the queue.")
    # Compact to 1..n rather than trusting the file's numbers. A gap, a tie, or an
    # id the framework no longer has would otherwise collide with the tail offset
    # below and silently break the total order the queue sorts on. Relative order
    # is what the editorial judgment actually encodes; the absolute values are not
    # load-bearing, so normalising them costs nothing and removes a whole failure mode.
    present = sorted((v, sid) for sid, v in ranked.items() if sid in index)
    out = {sid: i for i, (_, sid) in enumerate(present, start=1)}
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


def trunc_plain(text: str, n: int) -> str:
    text = (text or "").strip()
    if len(text) <= n:
        return text
    cut = text[:n]
    space = cut.rfind(" ")
    return (cut[:space] if space > n * 0.6 else cut).rstrip() + "…"


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
        # Null because nobody has confirmed anything yet — set --source populates
        # these on the first confirmed rating (see Task 2's attribution enforcement).
        "confirmedAt": None,
        "confirmedBy": None,
        "source": None,
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
        "intake": [],
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
             "[--reviewed] [--rationale '...'] [--source in-NNNN] [--confirmed-by NAME]")
    if len(pos) < 2:
        raise ValueError(usage)
    path, sid = pos[0], pos[1]

    core = load_core(); index = index_subcategories(core)
    store = load_store(path)
    settings = store["profile"]["settings"]
    ts = _s(opt.get("ts")) if isinstance(opt.get("ts"), (str, list)) else _now()
    actor = _s(opt.get("actor")) if isinstance(opt.get("actor"), (str, list)) else None
    rationale = _s(opt.get("rationale")) if isinstance(opt.get("rationale"), (str, list)) else None
    source = _s(opt.get("source")) if isinstance(opt.get("source"), (str, list)) else None
    confirmed_by = (_s(opt.get("confirmed-by"))
                    if isinstance(opt.get("confirmed-by"), (str, list)) else None)

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

    # A Current rating is the claim the whole report rests on, so it does not exist
    # without a named source and a named person. The CLI cannot prove a human typed
    # the number; what it enforces is that no rating exists that nobody will claim.
    # The confirmation discipline itself is a behavioural rule in SKILL.md.
    #
    # Target is deliberately NOT gated: it is a risk-based decision, already covered
    # by --rationale, and quickstart-target seeds it in bulk across ~106 Subcategories.
    #
    # Computed once, here, and reused below for the apply/skip decision on the same
    # field — so the gate's "is Current actually moving?" and the apply loop's cannot
    # independently drift out of agreement.
    current_update = next(((f, n) for f, n in updates if f == "current"), None)
    new_current = current_update[1] if current_update else None
    current_changing = current_update is not None and a.get("current") != new_current
    if current_changing and new_current is not None:
        if not source or not confirmed_by:
            raise ValueError(
                "--source and --confirmed-by are required for a Current rating. "
                "A rating nobody will claim is a rating nobody can defend. "
                "Record where it came from first:\n"
                f"  intake add <store.csfp> --label '...' --subjects {sid}\n"
                f"  then: set <store.csfp> {sid} --current N --source <the id it prints> "
                f"--confirmed-by <you> --rationale '...'"
            )
        known = {r.get("id") for r in store.get("intake", [])}
        if source not in known:
            raise ValueError(
                f"--source {source!r} is not an intake record in this Profile. "
                f"Known: {', '.join(sorted(known)) or '(none)'}. "
                f"List them with: intake list <store.csfp>"
            )

    applied = 0
    for field, new in updates:
        old = a.get(field)
        if field == "current":
            if not current_changing:
                continue
        elif old == new:
            continue
        a[field] = new
        etype = {"current": "rating-changed", "target": "target-changed",
                 "status": "status-changed", "applicability": "applicability-changed"}.get(field, "field-changed")
        # A cleared rating (new is None) carries no attribution even if stray --source /
        # --confirmed-by flags were passed alongside it — the clear itself is ungated
        # (see above), so those flags are meaningless here and must not be recorded as
        # if they justified a rating that, after this call, does not exist.
        attributed = field == "current" and new is not None
        append_history(store, etype, subcategoryId=sid, field=field, frm=old, to=new,
                       rationale=rationale, actor=actor, ts=ts,
                       source=source if attributed else None,
                       confirmedBy=confirmed_by if attributed else None)
        applied += 1
        # lastReviewed tracks "when did a human last look at this outcome" — only a
        # Current move (or an explicit --reviewed) affirms that. Notes edits must not.
        if field == "current":
            a["lastReviewed"] = ts[:10]
            # Attribution travels with the rating, not beside it — and it leaves with
            # it too. All three clear together on a withdrawal, or the assessment ends
            # up naming a source for a rating that no longer exists.
            if new is not None:
                a["confirmedAt"], a["confirmedBy"], a["source"] = ts[:10], confirmed_by, source
            else:
                a["confirmedAt"] = a["confirmedBy"] = a["source"] = None

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


def _next_intake_id(store) -> str:
    used = [int(m.group(1)) for r in store.get("intake", [])
            if (m := re.match(r"in-(\d+)$", str(r.get("id", ""))))]
    return f"in-{max(used, default=0) + 1:04d}"


def _is_iso_date(value) -> bool:
    """True only for a zero-padded YYYY-MM-DD.

    strptime alone is lenient about padding, so '2026-3-1' parses — and then sorts
    after '2026-12-01', because every date in this store is compared as a string.
    One predicate, used by both the write path (_iso_date) and the read path
    (check_store), so the two cannot drift apart.
    """
    text = str(value).strip()
    try:
        return datetime.strptime(text, "%Y-%m-%d").strftime("%Y-%m-%d") == text
    except ValueError:
        return False


def _iso_date(raw, label: str) -> str:
    """Validate an ISO date, zero-padding included.

    Dates in this store are compared and sorted as plain strings — `revisit` asks
    whether a source is newer than a confirmation by comparing them directly. So
    '2026-3-14' is not merely untidy: it sorts after '2026-12-01' and would make
    every revisit flag and age figure downstream quietly false.
    """
    text = str(_s(raw)).strip()
    if _is_iso_date(text):
        return text
    try:
        parsed = datetime.strptime(text, "%Y-%m-%d")
    except ValueError:
        raise ValueError(f"{label} must be an ISO date (YYYY-MM-DD), got {text!r}") from None
    raise ValueError(f"{label} must be zero-padded (YYYY-MM-DD), got {text!r} — "
                     f"try {parsed.strftime('%Y-%m-%d')!r}. Dates here are sorted as "
                     f"strings, so an unpadded month or day compares wrong.") from None


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
            noun = "Subcategory" if len(unknown) == 1 else "Subcategories"
            raise ValueError(f"Unknown {noun} {', '.join(repr(s) for s in unknown)} "
                             f"for framework {FRAMEWORK_REF}.")
        # A fumbled --subjects list can repeat an id. Task 5's per-source
        # confirmed/pending split sums len(subjects) directly, so a duplicate would
        # silently inflate coverage-by-source. dict.fromkeys dedupes and keeps
        # first-seen order without pulling in a set (which would not).
        subjects = list(dict.fromkeys(subjects))

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
        if not rec["recordedBy"]:
            print("  Warning: no recorder. Set --recorded-by, or an --owner on the Profile — "
                  "a source nobody recorded is a source nobody can be asked about.")
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
        # "confirmed" here means a rating exists, matching the four-way coverage
        # bucket the dashboards report. Whether that rating is *attributed* — has a
        # source, a confirmer and a date — is a separate axis, reported by `analyze`.
        # Conflating the two is the mistake this whole schema exists to prevent.
        rated = {a["subcategoryId"] for a in store["assessments"] if a.get("current") is not None}
        for r in records:
            done = sum(1 for s in r["subjects"] if s in rated)
            print(f"{r['id']}  {r['sourceDate']}  {r['label']}")
            print(f"          {len(r['subjects'])} Subcategories · {done} confirmed · "
                  f"{len(r['subjects']) - done} pending · {', '.join(r['subjects'])}")
        return 0

    raise ValueError(usage)


def _cmd_queue(args):
    pos, opt = parse_flags(args)
    path = _require_store(pos, "usage: queue <store.csfp> [--top N] [--json]")
    core = load_core(); index = index_subcategories(core)
    store = load_store(path)
    rep = store["profile"]["settings"]["reporting"]
    # today is needed by derive_evidence for the age block, which the queue does not
    # read. It is deliberately NOT a flag here: nothing observable in the queue
    # depends on it, and a flag that accepts a value and changes nothing is worse
    # than no flag.
    today = _today()
    # Batches of at most five by default. Long confirmation runs are where
    # rubber-stamping happens, and a rubber-stamped rating is worse than none.
    top = int(_s(opt.get("top"))) if isinstance(opt.get("top"), (str, list)) else 5
    if top < 0:
        raise ValueError("--top must be zero or greater.")

    ev = derive_evidence(store["assessments"], store.get("intake", []), index, core,
                         today, rep["scopeThresholdPct"], rep["ageThresholdDays"])
    all_rows = build_queue(store["assessments"], store.get("intake", []), ev, index,
                           resolve_rank(index, core, load_cold_start_rank()))
    rows = all_rows[:top]

    if opt.get("json"):
        sys.stdout.write(json.dumps(rows, indent=2, ensure_ascii=False) + "\n")
        return 0

    if not all_rows:
        # "Confirmed" is only true if something was in scope to confirm. Scoping
        # everything out and reading "confirmed" back is how a CISO concludes their
        # programme is current when it was never assessed at all — the exact
        # conclusion-laundering this command exists to refuse.
        scoped = in_scope(store["assessments"])
        if not scoped:
            print("Queue is empty because nothing is in scope — all "
                  f"{len(store['assessments'])} Subcategories are marked not-applicable. "
                  "That is a scoping position, not an assessment result.")
        else:
            print(f"Queue is empty — all {len(scoped)} in-scope Subcategories are "
                  "confirmed and nothing newer has arrived.")
        return 0

    if not rows:
        print(f"{len(all_rows)} to confirm, but --top {top} is showing none of them.")
        return 0

    print(f"Next {len(rows)} to confirm ({len(all_rows)} in the queue):\n")
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
    print("If the material is thin, the right outcome is a question to go ask — "
          "not a rating.")
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
    path = _require_store(pos, "usage: analyze <store.csfp> [--today YYYY-MM-DD] [--top N] "
                                "[--queue-top N] [--out F]")
    core = load_core(); index = index_subcategories(core)
    store = load_store(path)

    problems = check_store(store, index)
    if problems:
        raise ValueError("Profile failed validation: " + "; ".join(problems))

    today = _s(opt.get("today")) if isinstance(opt.get("today"), (str, list)) else _today()
    top = int(_s(opt.get("top"))) if isinstance(opt.get("top"), (str, list)) else 10
    # The playbook and the queue answer different questions and have different safe
    # batch sizes. --top governs the playbook, as it always has; the queue keeps the
    # cap the `queue` command chose for it, because a long confirmation run is where
    # rubber-stamping happens no matter which surface presents it.
    queue_top = int(_s(opt.get("queue-top"))) if isinstance(opt.get("queue-top"), (str, list)) else 5
    settings = store["profile"]["settings"]
    prof = store["profile"]

    tiers = copy.deepcopy(core.get("tiers") or {})
    tiers["profile"] = prof.get("tier", {})

    guidance = load_guidance()
    rep = settings["reporting"]
    evidence = derive_evidence(store["assessments"], store.get("intake", []), index, core,
                               today, rep["scopeThresholdPct"], rep["ageThresholdDays"])
    rank = resolve_rank(index, core, load_cold_start_rank())
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
        # Derived on demand, never stored. The store holds intake records and the
        # attribution on each assessment; everything below is computed from them at
        # read time. A renderer must never recompute any of it — two views of one
        # Profile disagreeing is the failure this rule exists to prevent.
        "evidence": evidence,
        "intake": {
            "records": store.get("intake", []),
            "bySource": coverage_by_source(store.get("intake", []), evidence["states"], index),
        },
        "queue": build_queue(store["assessments"], store.get("intake", []), evidence,
                             index, rank, queue_top),
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

    # A hand-edited or externally-converted store can carry a malformed date where
    # the write path never would. check_store is the gate analyze already calls
    # before computing anything, so this is where it must be caught.
    bad_confirmed = copy.deepcopy(store)
    bad_confirmed["assessments"][0]["confirmedAt"] = "14 March 2026"
    ok(any("confirmedAt" in p for p in check_store(bad_confirmed, index)),
       "check_store reports a malformed confirmedAt")

    # Unpadded — '2026-3-1' parses fine under plain strptime, but sorts AFTER
    # '2026-12-01' as a string, which is exactly the failure _iso_date's round-trip
    # exists to catch on the write path. check_store is the read-path equivalent
    # and must share the same predicate, or a hand-edited store slips through here.
    unpadded_confirmed = copy.deepcopy(store)
    unpadded_confirmed["assessments"][0]["confirmedAt"] = "2026-3-1"
    ok(any("confirmedAt" in p for p in check_store(unpadded_confirmed, index)),
       "check_store reports an unpadded confirmedAt")

    bad_intake = copy.deepcopy(store)
    bad_intake["intake"] = [{"id": "in-0001", "label": "x", "sourceDate": "14 March 2026",
                              "recordedAt": "2026-03-16", "subjects": [], "recordedBy": "Darren"}]
    ok(any("sourceDate" in p for p in check_store(bad_intake, index)),
       "check_store reports a malformed intake sourceDate")

    unpadded_source = copy.deepcopy(store)
    unpadded_source["intake"] = [{"id": "in-0001", "label": "x", "sourceDate": "2026-3-1",
                                   "recordedAt": "2026-03-16", "subjects": [], "recordedBy": "Darren"}]
    ok(any("sourceDate" in p for p in check_store(unpadded_source, index)),
       "check_store reports an unpadded intake sourceDate")

    unpadded_recorded = copy.deepcopy(store)
    unpadded_recorded["intake"] = [{"id": "in-0001", "label": "x", "sourceDate": "2026-03-01",
                                     "recordedAt": "2026-3-2", "subjects": [], "recordedBy": "Darren"}]
    ok(any("recordedAt" in p for p in check_store(unpadded_recorded, index)),
       "check_store reports an unpadded intake recordedAt")

    eq(check_store(store, index), [], "the well-formed store still reports neither")
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

        # A file carrying `"reporting": null` or only one of the two keys must not
        # defeat the defaults — the `or {}` guard in load_store is what stops it,
        # and a future "simplification" of that line needs to fail loudly here.
        for partial, expect_scope, expect_age, why in (
            (None, 60, 180, "reporting: null falls back to both defaults"),
            ({"scopeThresholdPct": 75}, 75, 180, "a partial reporting block keeps the other default"),
        ):
            _pp = os.path.join(_d, f"r{expect_scope}.csfp")
            _v = json.loads(json.dumps(v1))
            _v["profile"]["settings"] = {"reporting": partial}
            with open(_pp, "w", encoding="utf-8") as _fh:
                json.dump(_v, _fh)
            _rep = load_store(_pp)["profile"]["settings"]["reporting"]
            eq(_rep["scopeThresholdPct"], expect_scope, why)
            eq(_rep["ageThresholdDays"], expect_age, why + " (age)")

    with tempfile.TemporaryDirectory() as _d:
        _p = os.path.join(_d, "v3.csfp")
        with open(_p, "w", encoding="utf-8") as _fh:
            json.dump({**v1, "schemaVersion": "3.0"}, _fh)
        try:
            load_store(_p)
            failures.append("schemaVersion 3.0 should have been refused")
        except ValueError as exc:
            ok("3.0" in str(exc), "an unsupported schemaVersion names the version found")
        checks += 1

    # --- Intake: the source is the unit of record ---
    with tempfile.TemporaryDirectory() as _d:
        _p = os.path.join(_d, "i.csfp")
        _cmd_init(["--name", "Intake Co", "--out", _p, "--owner", "CISO",
                   "--ts", "2026-01-01T00:00:00Z"])
        _cmd_intake(["add", _p, "--label", "architecture review with infra team",
                     "--subjects", "ID.AM-01", "ID.AM-02", "ID.AM-03",
                     "--source-date", "2026-03-14", "--recorded-by", "Darren",
                     "--ts", "2026-03-16T09:00:00Z"])
        st = load_store(_p)
        eq(len(st["intake"]), 1, "one intake record written")
        r = st["intake"][0]
        eq(r["id"], "in-0001", "intake ids are in-NNNN, zero padded")
        eq(r["label"], "architecture review with infra team", "label is stored verbatim")
        eq(r["subjects"], ["ID.AM-01", "ID.AM-02", "ID.AM-03"], "subjects are stored in order")
        eq(r["sourceDate"], "2026-03-14", "sourceDate is when the conversation happened")
        eq(r["recordedAt"], "2026-03-16", "recordedAt is when it entered the store")
        eq(r["recordedBy"], "Darren", "recordedBy is recorded")
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

        # A repeated id in --subjects (a fumbled paste) must not inflate the count
        # Task 5 sums for per-source coverage.
        _cmd_intake(["add", _p, "--label", "duplicate subjects test",
                     "--subjects", "PR.DS-11", "PR.DS-11", "ID.AM-01",
                     "--ts", "2026-04-03T00:00:00Z"])
        r3 = load_store(_p)["intake"][2]
        eq(r3["subjects"], ["PR.DS-11", "ID.AM-01"],
           "duplicate --subjects entries are deduped, first-seen order preserved")

        # A source nobody recorded is a source nobody can be asked about. The warning
        # fires only when BOTH --recorded-by and a profile --owner are absent.
        _p_nowarn = os.path.join(_d, "no-owner.csfp")
        _cmd_init(["--name", "No Owner Co", "--out", _p_nowarn, "--ts", "2026-01-01T00:00:00Z"])
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            _cmd_intake(["add", _p_nowarn, "--label", "unattributed note",
                         "--subjects", "ID.AM-01", "--ts", "2026-01-02T00:00:00Z"])
        ok("Warning: no recorder" in buf.getvalue(),
           "no --recorded-by and no profile owner triggers the recorder warning")

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            _cmd_intake(["add", _p_nowarn, "--label", "attributed note",
                         "--subjects", "ID.AM-02", "--recorded-by", "Darren",
                         "--ts", "2026-01-03T00:00:00Z"])
        ok("Warning: no recorder" not in buf.getvalue(),
           "--recorded-by suppresses the recorder warning")

        for bad, why, expect in (
            (["add", _p, "--subjects", "ID.AM-01"], "no --label", "--label is required"),
            (["add", _p, "--label", "x"], "no --subjects", "--subjects is required"),
            (["add", _p, "--label", "x", "--subjects", "ZZ.ZZ-99"], "unknown Subcategory", "ZZ.ZZ-99"),
            (["add", _p, "--label", "x", "--subjects", "ID.AM-01",
              "--source-date", "14/03/2026"], "non-ISO sourceDate", "ISO date"),
            (["add", _p, "--label", "x", "--subjects", "ID.AM-01",
              "--source-date", "2026-3-14"], "unpadded sourceDate", "zero-padded"),
        ):
            try:
                _cmd_intake(bad)
                failures.append(f"intake add with {why} should have been refused")
            except ValueError as exc:
                ok(expect in str(exc), f"refusal for {why} names the actual problem")
            checks += 1

    # --- Intake list: the vocabulary and arithmetic a human actually reads ---
    with tempfile.TemporaryDirectory() as _d2:
        _p2 = os.path.join(_d2, "list.csfp")
        _cmd_init(["--name", "List Co", "--out", _p2, "--owner", "CISO",
                   "--ts", "2026-01-01T00:00:00Z"])

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = _cmd_intake(["list", _p2])
        eq(rc, 0, "intake list on an empty store returns 0")
        ok("No intake recorded yet." in buf.getvalue(),
           "empty store prints a clear message, not a crash")

        _cmd_intake(["add", _p2, "--label", "two-subject source",
                     "--subjects", "ID.AM-01", "ID.AM-02", "--ts", "2026-02-01T00:00:00Z"])

        # Confirm one of the two subjects directly on the store. `set`'s attribution
        # requirement (Task 2) does not exist yet, so this writes exactly what a
        # confirmed rating will later look like.
        s2 = load_store(_p2)
        for a in s2["assessments"]:
            if a["subcategoryId"] == "ID.AM-01":
                a["current"] = 2
        save_store(s2, _p2, "2026-02-02T00:00:00Z")

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = _cmd_intake(["list", _p2])
        eq(rc, 0, "intake list on a populated store returns 0")
        out = buf.getvalue()
        ok("1 confirmed" in out, "confirmed count reflects the one rated subject")
        ok("1 pending" in out, "pending count reflects the one unrated subject")

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = _cmd_intake(["list", _p2, "--json"])
        eq(rc, 0, "intake list --json returns 0")
        eq(json.loads(buf.getvalue()), load_store(_p2)["intake"],
           "--json emits the stored intake records verbatim")

    # --- Attribution enforcement on a Current rating ---
    # This asserts FAILURE. A test that only exercised the happy path would pass
    # against an engine that enforces nothing.
    with tempfile.TemporaryDirectory() as _d:
        _p = os.path.join(_d, "a.csfp")
        _cmd_init(["--name", "Attr Co", "--out", _p, "--owner", "CISO",
                   "--ts", "2026-01-01T00:00:00Z"])
        _cmd_intake(["add", _p, "--label", "architecture review with infra team",
                     "--subjects", "ID.AM-01", "ID.AM-02",
                     "--source-date", "2026-03-14", "--recorded-by", "Darren",
                     "--ts", "2026-03-16T00:00:00Z"])
        for bad, why in (
            (["--current", "2", "--rationale", "x"], "no attribution at all"),
            (["--current", "2", "--rationale", "x", "--source", "in-0001"], "no --confirmed-by"),
            (["--current", "2", "--rationale", "x", "--confirmed-by", "Darren"], "no --source"),
        ):
            try:
                _cmd_set([_p, "ID.AM-01"] + bad + ["--ts", "2026-03-20T00:00:00Z"])
                failures.append(f"set --current with {why} should have been refused")
            except ValueError as exc:
                # Assert on text unique to the attribution gate, NOT on "--source" /
                # "--confirmed-by" alone — the usage banner also names both flags, so
                # a regression that routed this call into the generic usage error
                # (raise ValueError(usage)) would pass that weaker assertion silently.
                ok("required for a Current rating" in str(exc)
                   and "nobody can defend" in str(exc),
                   f"refusal for {why} names the attribution gate, not generic usage")
            checks += 1
        try:
            _cmd_set([_p, "ID.AM-01", "--current", "2", "--rationale", "x",
                      "--source", "in-9999", "--confirmed-by", "Darren",
                      "--ts", "2026-03-20T00:00:00Z"])
            failures.append("set --source with an unknown intake id should have been refused")
        except ValueError as exc:
            ok("in-9999" in str(exc) and "not an intake record" in str(exc),
               "unknown --source names the id and the actual problem, not generic usage")
        checks += 1

        # Target is NOT gated: it is a risk-based decision, already covered by --rationale.
        _cmd_set([_p, "ID.AM-01", "--target", "3", "--rationale", "risk-based target",
                  "--ts", "2026-03-20T00:00:00Z"])
        eq([a for a in load_store(_p)["assessments"]
            if a["subcategoryId"] == "ID.AM-01"][0]["target"], 3,
           "target writes without attribution")

        _cmd_set([_p, "ID.AM-01", "--current", "2", "--rationale", "confirmed at review",
                  "--source", "in-0001", "--confirmed-by", "Darren",
                  "--ts", "2026-03-20T00:00:00Z"])
        st = load_store(_p)
        a = [x for x in st["assessments"] if x["subcategoryId"] == "ID.AM-01"][0]
        eq(a["current"], 2, "attributed current rating is written")
        eq(a["source"], "in-0001", "source is recorded on the assessment")
        eq(a["confirmedBy"], "Darren", "confirmedBy is recorded on the assessment")
        eq(a["confirmedAt"], "2026-03-20", "confirmedAt is the date of the decision")
        eq(a["lastReviewed"], "2026-03-20", "a Current move still refreshes lastReviewed")
        ev = [e for e in st["history"] if e.get("type") == "rating-changed"][-1]
        eq(ev.get("source"), "in-0001", "the history event carries the source")
        eq(ev.get("confirmedBy"), "Darren", "the history event carries the confirmer")

        # Clearing a rating is not a claim, so it needs no attribution.
        _cmd_set([_p, "ID.AM-01", "--current", "null", "--rationale", "withdrawn: source disputed",
                  "--ts", "2026-03-21T00:00:00Z"])
        a2 = [x for x in load_store(_p)["assessments"]
              if x["subcategoryId"] == "ID.AM-01"][0]
        eq(a2["current"], None, "a rating can be cleared without attribution")
        eq(a2["confirmedAt"], None, "confirmedAt clears along with the rating")

        # CRITICAL (caught in review): a clear passed WITH stray --source/--confirmed-by
        # flags must still end up fully unattributed. The clear itself is ungated — the
        # flags are simply irrelevant to it — but they must not be recorded anyway, or
        # the assessment ends up naming a source and a confirmer for a rating that, after
        # this call, does not exist.
        _cmd_set([_p, "ID.AM-01", "--current", "2", "--rationale", "re-confirmed",
                  "--source", "in-0001", "--confirmed-by", "Darren",
                  "--ts", "2026-03-22T00:00:00Z"])
        _cmd_set([_p, "ID.AM-01", "--current", "null", "--rationale", "withdrawn again",
                  "--source", "in-0001", "--confirmed-by", "Darren",
                  "--ts", "2026-03-23T00:00:00Z"])
        a3 = [x for x in load_store(_p)["assessments"]
              if x["subcategoryId"] == "ID.AM-01"][0]
        eq(a3["current"], None, "current clears even with stray attribution flags present")
        eq(a3["confirmedAt"], None, "confirmedAt clears despite stray --source/--confirmed-by")
        eq(a3["confirmedBy"], None, "confirmedBy clears despite stray --source/--confirmed-by")
        eq(a3["source"], None, "source clears despite stray --source/--confirmed-by")

        # An unchanged value is a no-op, not a new claim — it must not demand attribution.
        _cmd_set([_p, "ID.AM-02", "--priority", "high", "--ts", "2026-03-22T00:00:00Z"])
        eq([x for x in load_store(_p)["assessments"]
            if x["subcategoryId"] == "ID.AM-02"][0]["priority"], "high",
           "a non-rating field still writes without attribution")

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
    eq(len(set(order.values())), len(order), "positions are unique — the order is total")
    ok(load_cold_start_rank("/nonexistent/cold-start-rank.json").get("rank") == {},
       "a missing rank file degrades to an empty table, not a crash")
    eq(len(resolve_rank(index, core, {"rank": {}})), len(index),
       "with no ranked ids, every Subcategory still gets a position from framework order")

    # Adversarial rank tables: an id the framework lacks, a gap, and a tie. Each of
    # these collided a ranked id's compacted position with the tail offset before
    # resolve_rank compacted to 1..n instead of trusting the file's raw numbers —
    # reproduced by spec review against the code as originally handed over.
    for bad, why in (
        ({"rank": {"ZZ.ZZ-99": 1, "ID.AM-01": 2}}, "a rank table naming an id the framework lacks"),
        ({"rank": {"ID.AM-01": 1, "ID.AM-02": 2, "ID.AM-03": 5}}, "a gapped rank table"),
        ({"rank": {"ID.AM-01": 1, "ID.AM-02": 1}}, "a rank table with a tie"),
    ):
        o = resolve_rank(index, core, bad)
        eq(len(o), len(index), f"{why} still positions every Subcategory")
        eq(len(set(o.values())), len(index), f"{why} still yields a total order")

    # Quoted rank values are the hand-editing mistake that sorts lexicographically
    # and passes every structural check while silently reordering the queue.
    # isinstance(v, bool) must also be rejected — True is an int in Python and
    # would otherwise slip through as rank 1.
    for bad_ranks, why in (
        ({"ID.AM-01": "1", "ID.AM-02": "2", "ID.AM-03": "10"}, "string-valued ranks"),
        ({"ID.AM-01": True, "ID.AM-02": 2}, "a bool-valued rank"),
    ):
        try:
            resolve_rank(index, core, {"rank": bad_ranks})
            failures.append(f"resolve_rank with {why} should have been refused")
        except ValueError as exc:
            ok("must be integers" in str(exc), f"{why} refusal names the actual problem")
        checks += 1

    # The shipped file is already dense 1..32, so compaction must be an identity on
    # it — verified directly, since that is exactly the case the bug hid in.
    shipped = load_cold_start_rank()
    ok(all(order[sid] == v for sid, v in shipped["rank"].items()),
       "compaction is an identity on the shipped table — every ranked id keeps its authored position")

    # --- Derivation layer: derived, never stored ---
    fx_assess = [
        {"subcategoryId": "ID.AM-01", "applicability": "in-scope", "current": 2, "target": 3,
         "confirmedAt": "2026-03-20", "confirmedBy": "Darren", "source": "in-0001"},
        {"subcategoryId": "ID.AM-02", "applicability": "in-scope", "current": 1, "target": 3,
         "confirmedAt": "2025-06-01", "confirmedBy": "Darren", "source": "in-0001"},
        {"subcategoryId": "ID.AM-03", "applicability": "in-scope", "current": None, "target": 3,
         "confirmedAt": None, "confirmedBy": None, "source": None},
        {"subcategoryId": "PR.AA-01", "applicability": "in-scope", "current": None, "target": 3,
         "confirmedAt": None, "confirmedBy": None, "source": None},
        {"subcategoryId": "PR.AA-03", "applicability": "not-applicable", "current": None,
         "target": None, "confirmedAt": None, "confirmedBy": None, "source": None},
        {"subcategoryId": "PR.DS-11", "applicability": "in-scope", "current": 3, "target": 3,
         "confirmedAt": "2026-01-10", "confirmedBy": "Darren", "source": "in-0002"},
    ]
    fx_intake = [
        {"id": "in-0001", "label": "architecture review", "sourceDate": "2025-05-20",
         "recordedAt": "2026-03-16", "subjects": ["ID.AM-01", "ID.AM-02", "ID.AM-03"],
         "recordedBy": "Darren"},
        {"id": "in-0002", "label": "backup restore test", "sourceDate": "2026-01-08",
         "recordedAt": "2026-01-09", "subjects": ["PR.DS-11"], "recordedBy": "Darren"},
        {"id": "in-0003", "label": "vendor DR conversation", "sourceDate": "2026-06-02",
         "recordedAt": "2026-06-03", "subjects": ["PR.DS-11"], "recordedBy": "Darren"},
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
    eq(cov["unattributed"], 0, "unattributed = confirmed without all three")

    eq([r["subcategoryId"] for r in ev["revisit"]], ["PR.DS-11"],
       "revisit: material newer than the confirmation")
    eq(ev["revisit"][0]["newestSourceDate"], "2026-06-02", "revisit names the newer source date")
    ok("ID.AM-01" not in {r["subcategoryId"] for r in ev["revisit"]},
       "material older than the confirmation is not a revisit")

    # A cited source dated after its own confirmation is incoherent data, and the
    # right response is to surface it for a human, not to special-case it away.
    incoherent = [dict(a) for a in fx_assess]
    for a in incoherent:
        if a["subcategoryId"] == "ID.AM-01":
            a["confirmedAt"] = "2025-01-01"      # before in-0001's sourceDate
    ev_inc = derive_evidence(incoherent, fx_intake, index, core, today="2026-07-27",
                             threshold_pct=60, age_days=180)
    ok("ID.AM-01" in {r["subcategoryId"] for r in ev_inc["revisit"]},
       "a source dated after the confirmation it grounds still raises a revisit")

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

    # Per-Function derivation uses framework ids, never hardcoded names.
    eq(set(ev["coverage"]["byFunction"]), set(function_ids(core)),
       "four-way coverage covers every Function in the framework")
    eq(set(ev["age"]["byFunction"]), set(function_ids(core)),
       "age is reported per Function")
    eq(ev["coverage"]["byFunction"]["ID"]["confirmed"], 2, "ID has two confirmed")
    eq(ev["coverage"]["byFunction"]["RC"]["total"], 0, "an untouched Function reports zeros")

    # Coverage by source: what did that review actually cover?
    bysrc = coverage_by_source(fx_intake, ev["states"], index)
    eq([r["id"] for r in bysrc], ["in-0003", "in-0002", "in-0001"],
       "sources are newest-first by sourceDate")
    first = [r for r in bysrc if r["id"] == "in-0001"][0]
    eq(first["confirmed"], 2, "in-0001 confirmed two of its three subjects")
    eq(first["pending"], 1, "in-0001 has one subject still pending")
    eq(len(first["subjects"]), 3, "every subject is listed, with its state")
    ok(all(set(s) == {"subcategoryId", "state"} for s in first["subjects"]),
       "each subject carries only an id and a state — no per-subject text to accrete")

    # Tie-break: three pending Subcategories sharing one sourceDate. A single
    # reverse=True over the (date, id) tuple would hand these out id-descending —
    # this is the case that shipped silently because the earlier fixture had no tie.
    tie_assess = [
        {"subcategoryId": "ID.AM-03", "applicability": "in-scope", "current": None, "target": 3,
         "confirmedAt": None, "confirmedBy": None, "source": None},
        {"subcategoryId": "ID.AM-02", "applicability": "in-scope", "current": None, "target": 3,
         "confirmedAt": None, "confirmedBy": None, "source": None},
        {"subcategoryId": "ID.AM-01", "applicability": "in-scope", "current": None, "target": 3,
         "confirmedAt": None, "confirmedBy": None, "source": None},
    ]
    tie_intake = [{"id": "in-tie", "label": "one review, three subjects",
                   "sourceDate": "2026-05-01", "recordedAt": "2026-05-02",
                   "subjects": ["ID.AM-03", "ID.AM-02", "ID.AM-01"], "recordedBy": "Darren"}]
    ev_tie = derive_evidence(tie_assess, tie_intake, index, core, today="2026-07-27",
                             threshold_pct=60, age_days=180)
    eq([r["subcategoryId"] for r in ev_tie["pending"]], ["ID.AM-01", "ID.AM-02", "ID.AM-03"],
       "tied newestSourceDate breaks by ascending Subcategory id, not descending")

    # --- Queue order: evidence-pending -> revisit -> cold-start rank ---
    _rank = resolve_rank(index, core, load_cold_start_rank())
    q = build_queue(fx_assess, fx_intake, ev, index, _rank)
    eq([r["subcategoryId"] for r in q], ["ID.AM-03", "PR.DS-11", "PR.AA-01"],
       "bands run pending, then revisit, then cold-start")
    eq([r["band"] for r in q], ["evidence-pending", "revisit", "cold-start"],
       "each row names its band")
    ok("PR.AA-03" not in {r["subcategoryId"] for r in q},
       "not-applicable never enters the queue")
    ok("ID.AM-01" not in {r["subcategoryId"] for r in q},
       "a confirmed rating with no newer material is not queued")

    # The anti-drift rule: a queue item presents a question, never an answer.
    for r in q:
        ok(r.get("tier") is None, f"{r['subcategoryId']}: queue row carries no tier")
        ok(not any(k in r for k in ("proposedTier", "suggested", "confidence", "current")),
           f"{r['subcategoryId']}: queue row carries no proposed rating of any kind")

    eq(q[0]["sources"][0]["label"], "architecture review",
       "a pending row carries its source label")
    eq(q[0]["sources"][0]["sourceDate"], "2025-05-20", "and the date the source is from")
    eq(q[1]["confirmedAt"], "2026-01-10", "a revisit row carries the confirmation it questions")
    eq(q[2]["sources"], [], "a cold-start row has no material — that is what makes it cold")
    ok(all(r.get("coldStartRank") for r in q), "every row carries its cold-start rank")
    eq(build_queue(fx_assess, fx_intake, ev, index, _rank, top=2), q[:2],
       "top=N truncates after ordering, not before")

    # Ties must break on id ASCENDING. reverse=True over a (date, id) tuple would
    # reverse the tie-break too and hand a user ID.AM-03 before ID.AM-01.
    tie_assess = [{"subcategoryId": s, "applicability": "in-scope", "current": None,
                   "target": 3, "confirmedAt": None, "confirmedBy": None, "source": None}
                  for s in ("ID.AM-03", "ID.AM-01", "ID.AM-02")]
    tie_intake = [{"id": "in-0009", "label": "one workshop", "sourceDate": "2026-05-01",
                   "recordedAt": "2026-05-02",
                   "subjects": ["ID.AM-03", "ID.AM-01", "ID.AM-02"], "recordedBy": "D"}]
    tie_ev = derive_evidence(tie_assess, tie_intake, index, core, today="2026-07-27",
                             threshold_pct=60, age_days=180)
    tie_q = build_queue(tie_assess, tie_intake, tie_ev, index, _rank)
    eq([r["subcategoryId"] for r in tie_q], ["ID.AM-01", "ID.AM-02", "ID.AM-03"],
       "within one source date, pending rows order by cold-start rank then id")

    # An empty queue is a real state, not an error.
    eq(build_queue([], [], derive_evidence([], [], index, core, "2026-07-27", 60, 180),
                   index, _rank), [],
       "a Profile with nothing to confirm yields an empty queue")

    # --- queue CLI: --top must truncate the display, never lie about what exists ---
    with tempfile.TemporaryDirectory() as _dq:
        _pq = os.path.join(_dq, "q.csfp")
        _cmd_init(["--name", "Queue Co", "--out", _pq, "--owner", "CISO",
                   "--ts", "2026-01-01T00:00:00Z"])
        # Fresh store: 106 unrated Subcategories, all cold-start, so the full queue
        # is non-empty. --top 0 must not claim otherwise.
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = _cmd_queue([_pq, "--top", "0"])
        out = buf.getvalue()
        eq(rc, 0, "queue --top 0 returns 0")
        ok("Queue is empty" not in out,
           "--top 0 truncates the view; it must not claim the queue itself is empty")
        ok("to confirm, but --top 0 is showing none of them" in out,
           "--top 0 says what it is doing instead")

        # A normal, non-zero --top folds the total into the header, ahead of the
        # listing — not as an afterthought below the call to action.
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = _cmd_queue([_pq, "--top", "3"])
        out = buf.getvalue()
        eq(rc, 0, "queue --top 3 returns 0")
        eq(out.count("[cold-start]"), 3, "--top 3 lists exactly three rows")
        ok("Next 3 to confirm (106 in the queue):" in out,
           "a truncated queue tells the reader how much more there is, in the header")

        # --json must be pinned to the exact same rows the plain-text path would
        # list, truncated the same way — a future edit that swaps all_rows/rows in
        # one branch but not the other must fail here.
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = _cmd_queue([_pq, "--top", "3", "--json"])
        eq(rc, 0, "queue --top 3 --json returns 0")
        core_q = load_core(); index_q = index_subcategories(core_q)
        store_q = load_store(_pq)
        ev_q = derive_evidence(store_q["assessments"], store_q.get("intake", []), index_q,
                               core_q, _today(), 60, 180)
        expected_q = build_queue(store_q["assessments"], store_q.get("intake", []), ev_q,
                                 index_q, resolve_rank(index_q, core_q, load_cold_start_rank()),
                                 top=3)
        eq(json.loads(buf.getvalue()), expected_q,
           "--json emits exactly build_queue's own output, truncated the same way")

        # A negative --top would slice from the end and silently show the wrong
        # rows — refuse it outright rather than let Python's slicing paper over it.
        try:
            _cmd_queue([_pq, "--top", "-1"])
            failures.append("queue --top -1 should have been refused")
        except ValueError as exc:
            ok("--top must be zero or greater" in str(exc),
               "a negative --top names the actual problem")
        checks += 1

        # A genuinely empty queue has two distinct causes, and conflating them is
        # exactly the overclaim this command exists to refuse: scoping everything
        # out is a scoping position, not an assessment result, and must never read
        # back as "confirmed".
        s_empty = load_store(_pq)
        for a in s_empty["assessments"]:
            a["applicability"] = "not-applicable"
            a["current"] = None
            a["target"] = None
        save_store(s_empty, _pq, "2026-01-02T00:00:00Z")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = _cmd_queue([_pq, "--top", "5"])
        out = buf.getvalue()
        eq(rc, 0, "queue on a fully scoped-out store returns 0")
        ok("Queue is empty because nothing is in scope" in out,
           "a fully scoped-out store gets the SCOPING message, not the confirmed one")
        ok("confirmed" not in out,
           "the scoping message never uses the word that would claim an assessment happened")

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
                  "--source", "in-0001", "--confirmed-by", "Darren",
                  "--ts", "2026-03-20T00:00:00Z"])
        _cmd_analyze([_p, "--today", "2026-07-27", "--out", _out])
        with open(_out, encoding="utf-8") as _fh:
            an = json.load(_fh)

        for key in ("evidence", "intake", "queue"):
            ok(key in an, f"analyze emits {key!r}")
        eq(an["evidence"]["coverage"]["overall"]["confirmed"], 1, "analyze counts confirmations")
        eq(an["evidence"]["coverage"]["overall"]["evidencePending"], 1,
           "analyze counts evidence-pending")
        eq(an["evidence"]["coverage"]["overall"]["attributed"], 1,
           "analyze reports attribution as its own axis")
        ok(an["evidence"]["scopeGuard"]["suppressed"],
           "1 of 106 assessed suppresses the headline")
        eq(an["evidence"]["age"]["thresholdDays"], 180,
           "analyze reports the age threshold in force")
        eq(len(an["intake"]["records"]), 1, "analyze carries the intake records")
        eq(an["intake"]["bySource"][0]["confirmed"], 1, "coverage-by-source counts confirmations")
        eq(an["intake"]["bySource"][0]["pending"], 1, "coverage-by-source counts pending")
        eq(an["queue"][0]["subcategoryId"], "ID.AM-02", "the queue leads with the pending item")
        eq(an["queue"][0]["band"], "evidence-pending", "and names its band")
        ok(all(r.get("tier") is None for r in an["queue"]),
           "no queue row in analyze output carries a rating")
        eq(an["generated"]["schemaVersion"], "2.0", "analyze stamps the schema version")

        raw = json.load(open(_p, encoding="utf-8"))
        ok("evidence" not in raw and "queue" not in raw,
           "no derived block is persisted to the store")
        ok(all("state" not in a for a in raw["assessments"]),
           "no derived state is persisted onto an assessment")

        # The existing scoring path is untouched by any of this.
        eq(an["coverage"]["overall"]["d"], 212, "quickstart target of 2 across 106 in-scope")
        eq(an["coverage"]["overall"]["n"], 2, "one Subcategory at Current 2")
        eq(an["completeness"]["overall"]["assessed"], 1, "completeness still counts assessed")

        # analyze must not mutate the store it reads.
        _before = open(_p, encoding="utf-8").read()
        _cmd_analyze([_p, "--today", "2026-07-27", "--out", _out])
        eq(open(_p, encoding="utf-8").read(), _before, "analyze does not rewrite the store")

        # --top governs the playbook, as it always has; the queue is a different
        # question with its own safe batch size and does not move with it.
        _cmd_analyze([_p, "--today", "2026-07-27", "--top", "3", "--out", _out])
        _an_top3 = json.load(open(_out, encoding="utf-8"))
        eq(len(_an_top3["playbook"]), 3, "--top bounds the playbook emitted by analyze")
        eq(len(_an_top3["queue"]), 5,
           "the queue keeps its own default of 5, unmoved by --top")

        # --queue-top governs the queue independently, leaving --top's default alone.
        _cmd_analyze([_p, "--today", "2026-07-27", "--queue-top", "3", "--out", _out])
        _an_qtop3 = json.load(open(_out, encoding="utf-8"))
        eq(len(_an_qtop3["queue"]), 3, "--queue-top bounds the queue emitted by analyze")
        eq(len(_an_qtop3["playbook"]), 10, "--top keeps its own default of 10, unmoved by --queue-top")

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
    "intake": _cmd_intake, "queue": _cmd_queue,
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
