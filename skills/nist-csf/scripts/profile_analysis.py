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
  posture      <store.csfp> [--risk F.rr] [--policy F.pol] [--metrics F.mtr]
               [--context P] [--json] [--out F]
                                    The program posture report: every CSF outcome banded
                                    by WHAT IS RECORDED about it — well-evidenced,
                                    thinly evidenced, declared critical, no record, plus
                                    unknown for a store that could not be read. It answers
                                    "can you show your work?" and never "is your work any
                                    good?". No score, no percentage, no ranking.
               [--context PAYLOAD] [--ai-signal SIGNAL]   `--ai-signal` is optional evidence
               for the Cyber AI Profile scoping question, from `ai_register.py export-signal`.
               Counts only; the question is still asked, and still answered here.
  diff         <store.csfp> [--label L] [--json]   Compare current state to a snapshot.
  export-gaps  <store.csfp> [--out F]              Gap CSV for `risk-register import-gaps`.
  queue        <store.csfp> [--top N] [--json]      What to confirm next, ranked.
  elicit       <store.csfp> [--top N] [--json]      Cold-start questions still worth asking.
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
  overlay           list|enable|disable <store.csfp> [--focus A B] [--mode advisory|reorder]
                    (list is read-only; enable and disable rewrite the store)
  crosswalk         <store.csfp> --lens iso-27001-2022|cis-8.1|800-53-r5 [--json] [--out F]
                    Read-only projection of this Profile through a crosswalk lens. Derived,
                    never an audit or a certification.

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
import subprocess
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

# Integrity invariants for the bundled crosswalk data, same discipline as
# CORE_EXPECTED above. `labelSource` is the load-bearing one: it is the licensing
# contract, not a cosmetic tag. ISO and CIS ship IDs plus our own paraphrases and
# never the official control titles or normative text; 800-53 is a US Government
# work and ships verbatim. A refresh of the NIST reference export is expected to
# move these counts — that is the point. The rebuild diffs against them, so a
# changed catalog is a deliberate review step rather than silent drift.
CROSSWALK_EXPECTED = {
    # Moved 731/206 -> 737/210 at Release 5.2.0 (BL-160), and reviewed rather than accepted:
    # +7 edges, -1 edge (DE.AE-06 -> RA-3), +4 controls (RA-4, SA-15(13), SA-24, SI-2(07)),
    # ZERO controls lost. The one deletion is the kind of change this pin exists to surface.
    "800-53-r5":      {"edges": 737, "controls": 210, "groupings": 20,
                       "labelSource": "verbatim-public-domain", "verbatimAllowed": True},
    "iso-27001-2022": {"edges": 329, "controls": 119, "groupings": 5,
                       "labelSource": "cac-generated", "verbatimAllowed": False},
    "cis-8.1":        {"edges": 62,  "controls": 49,  "groupings": 16,
                       "labelSource": "cac-generated", "verbatimAllowed": False},
}

_SKILL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_CORE = os.path.join(_SKILL_ROOT, "references", "nist-csf-2.0-core.json")
DEFAULT_GUIDANCE = os.path.join(_SKILL_ROOT, "references", "guidance.json")
DEFAULT_COLD_START_RANK = os.path.join(_SKILL_ROOT, "references", "cold-start-rank.json")
DEFAULT_ELICITATION = os.path.join(_SKILL_ROOT, "references", "elicitation.json")
DEFAULT_CYBER_AI = os.path.join(_SKILL_ROOT, "references", "cyber-ai-profile.json")
DEFAULT_CROSSWALK_DIR = os.path.join(_SKILL_ROOT, "references", "crosswalks")
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


def check_crosswalks(index: dict, path: str | None = None) -> list[str]:
    """Integrity + licensing check on the bundled crosswalk data.

    Returns a list of problems; empty means clean. Deliberately overlaps the
    build-time checker in tools/crosswalks/validate_crosswalks.py, because that
    one does not ship: a user who only has the skill still needs the licensing
    invariant enforced. Two checks it makes that the build-time one structurally
    cannot, having no Core to compare against:

      - every edge's csfSubId resolves to a real CSF Subcategory, so a typo or a
        stale Subcategory id cannot silently drop a control's coverage to
        "unknown" while every count still looks right;
      - the pinned CROSSWALK_EXPECTED counts.

    `index` is index_subcategories(core) output.
    """
    problems: list[str] = []
    base = path or DEFAULT_CROSSWALK_DIR
    if not os.path.isdir(base):
        return [f"crosswalk data directory is missing: {base}"]

    for fid, want in sorted(CROSSWALK_EXPECTED.items()):
        cat_path = os.path.join(base, f"{fid}.catalog.json")
        map_path = os.path.join(base, f"csf-2.0__{fid}.map.json")
        for p in (cat_path, map_path):
            if not os.path.isfile(p):
                problems.append(f"[{fid}] missing {os.path.basename(p)}")
        if problems and any(fid in p for p in problems):
            continue
        try:
            with open(cat_path, encoding="utf-8") as f:
                cat = json.load(f)
            with open(map_path, encoding="utf-8") as f:
                mp = json.load(f)
        except (OSError, ValueError) as exc:
            problems.append(f"[{fid}] unreadable crosswalk data: {exc}")
            continue

        controls = cat.get("controls", [])
        groupings = cat.get("groupings", [])
        edges = mp.get("edges", [])
        if len(controls) != want["controls"]:
            problems.append(f"[{fid}] expected {want['controls']} controls, found {len(controls)}")
        if len(groupings) != want["groupings"]:
            problems.append(f"[{fid}] expected {want['groupings']} groupings, found {len(groupings)}")
        if len(edges) != want["edges"]:
            problems.append(f"[{fid}] expected {want['edges']} edges, found {len(edges)}")

        for field in ("frameworkId", "name", "version", "license", "provenance",
                      "sourceExport", "catalogueScope"):
            if not cat.get(field):
                problems.append(f"[{fid}] catalog is missing provenance field {field!r}")
        cov = (cat.get("catalogueScope") or {}).get("coverage")
        if cov not in ("full", "referenced-subset"):
            problems.append(f"[{fid}] catalogueScope.coverage is {cov!r}; must be "
                            f"'full' or 'referenced-subset' so an empty outside-CSF "
                            f"list can be read correctly")
        if cat.get("frameworkId") != fid:
            problems.append(f"[{fid}] catalog frameworkId is {cat.get('frameworkId')!r}")

        declared = {g.get("id") for g in groupings}
        seen: set[str] = set()
        for ctl in controls:
            cid = ctl.get("id")
            if not cid:
                problems.append(f"[{fid}] a control has no id")
                continue
            if cid in seen:
                problems.append(f"[{fid}] duplicate control id {cid}")
            seen.add(cid)
            if not (ctl.get("label") or "").strip():
                problems.append(f"[{fid}] {cid} has an empty label")
            if ctl.get("labelSource") != want["labelSource"]:
                problems.append(f"[{fid}] {cid} labelSource is {ctl.get('labelSource')!r}, "
                                f"must be {want['labelSource']!r}")
            # The licensing line. ISO and CIS text is copyrighted; shipping it
            # would be redistribution, so its absence is enforced, not trusted.
            if not want["verbatimAllowed"] and ctl.get("text") not in (None, ""):
                problems.append(f"[{fid}] {cid} carries normative text, which is "
                                f"forbidden for this framework")
            if ctl.get("groupingId") and ctl["groupingId"] not in declared:
                problems.append(f"[{fid}] {cid} groupingId {ctl['groupingId']!r} is not declared")
            # Optional, but not free-form: this field moves a control off the
            # "CSF does not reach this" list, so an unrecognised value must fail
            # loudly rather than be ignored into the default.
            if ctl.get("csfReference") not in (None, "category-only"):
                problems.append(f"[{fid}] {cid} csfReference is {ctl.get('csfReference')!r}; "
                                f"the only recognised value is 'category-only'")

        if not mp.get("mappingAuthority"):
            problems.append(f"[{fid}] map is missing mappingAuthority")
        for e in edges:
            sub, ctl_id = e.get("csfSubId"), e.get("controlId")
            if ctl_id not in seen:
                problems.append(f"[{fid}] edge {sub}->{ctl_id} does not resolve to a catalog control")
            if sub not in index:
                problems.append(f"[{fid}] edge {sub}->{ctl_id} cites {sub!r}, "
                                f"which is not a CSF Subcategory")
            if not e.get("authority"):
                problems.append(f"[{fid}] edge {sub}->{ctl_id} has no authority tag")

    return problems


# --- Store IO ----------------------------------------------------------------

_CORE_REF_CACHE = {}


def core_ref(core: dict = None) -> dict:
    """`{"version": ..., "sha256": ...}` for the shipped Core — its identity, not its content.

    The sha256 is the same string `tools/check-versions.py` compares the vendored CPRT export
    against, so a store's stamp, the shipped Core and the file on disk are all one identity
    (BL-75, BL-109). Cached because `save_store` calls it on every write and the Core is a
    2MB read.
    """
    if core is None:
        if "ref" not in _CORE_REF_CACHE:
            _CORE_REF_CACHE["ref"] = core_ref(load_core())
        return _CORE_REF_CACHE["ref"]
    return {"version": core.get("version"),
            "sha256": ((core.get("source") or {}).get("sha256"))}


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

    # Overlay state. Defaults are inert on purpose: a normalization bug should
    # produce a Profile that reports nothing, never one that silently
    # resequences a board's top five. Note this default is `advisory` while the
    # enable command defaults to `reorder` — the safe fallback and the useful
    # choice are different questions.
    overlays = store.setdefault("overlays", {})
    cyber = overlays.setdefault("cyberAi", {})
    cyber.setdefault("enabled", False)
    cyber.setdefault("focusAreas", [])
    cyber.setdefault("mode", "advisory")
    cyber.setdefault("datasetVersion", None)

    # Absent means NOT RECORDED, never "matches". Every store written before v0.80.0 has no
    # stamp, and the reader has to be able to tell that from agreement (BL-109 T2).
    store["profile"].setdefault("coreRef", None)

    for a in store["assessments"]:
        a.setdefault("confirmedAt", None)
        a.setdefault("confirmedBy", None)
        a.setdefault("source", None)
    return store


def save_store(store: dict, path: str, ts: str) -> None:
    """Write the store back, stamping schemaVersion and profile.updated.

    History is never rewritten here — callers append to store['history'] before saving.

    Written atomically: a crash mid-write leaves the previous file intact. Until BL-219 this
    was `open(path, "w")`, which TRUNCATES before the dump — an interrupted write left a
    half-written Profile and no copy of what had been there, on a store carrying all 106
    subcategories from `init` onwards. `dir=directory` is load-bearing: `os.replace` is atomic
    only within one filesystem, so a temp file in /tmp would make this a copy across a
    boundary rather than a move.

    One of ten copies of this pattern, registered as a twin under CAC-TW-1 and compared by
    executing them — `skills/ai-register/scripts/ai_register.py` holds the family list. The
    property compared is the interrupted write, because on the happy path an atomic writer and
    `open(path, "w")` produce identical bytes, which is how this copy stayed non-atomic
    through nine releases with every self-test green.
    """
    store["schemaVersion"] = SCHEMA_VERSION
    store["profile"]["updated"] = ts
    # WHICH CORE THIS STORE WAS LAST WRITTEN AGAINST (BL-109 T2).
    #
    # Nothing recorded it. `profile.frameworkRef` is the literal "nist-csf-2.0" — a framework
    # identity, not a version — and no report stated which export produced the Core it was
    # computed against. So a store assessed against one Core and analysed against a later one
    # was indistinguishable from one that had never moved.
    #
    # Stamped HERE rather than in each mutating command, for the same reason `profile.updated`
    # is: one place, and a command added later cannot forget it. The identity is the export's
    # sha256, following BL-75 — a date says when somebody downloaded a file, a hash says which
    # file. The version string rides along because it is what a human recognises.
    #
    # A legacy store gets it on its next write and reads as *not recorded* until then.
    # Refusing one would strand a CISO mid-assessment, which is the BL-169 D-2 violation this
    # whole item is careful not to commit.
    store["profile"]["coreRef"] = dict(core_ref())
    directory = os.path.dirname(os.path.abspath(path)) or "."
    fd, tmp = tempfile.mkstemp(dir=directory, suffix=".csfp.tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(store, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def provenance_notes(store: dict, dataset: dict = None) -> list[str]:
    """Sentences about WHICH DATA produced this Profile. Notes, never refusals (BL-109 D-1).

    Two comparisons nobody was making. `overlay list` printed the shipped dataset version and
    the in-force one **on adjacent lines** and said nothing about the difference; `analyze`
    reported the shipped version in its footer while the store still held an older stamp, with
    no warning, no note and exit 0. The numbers were on screen. The comparison was not.

    A mismatch is a fact about provenance, not an invalid store. Refusing would strand a CISO
    mid-assessment the day a dataset or a Core moves, which is exactly the BL-169 D-2 failure
    this repo refuses to commit — so these are notes, and everything still analyses.

    `coreRef` absent means NOT RECORDED — every store written before v0.80.0 — and that is
    reported as its own sentence rather than as agreement or as a mismatch.
    """
    notes = []
    stamped = (store.get("profile") or {}).get("coreRef") or {}
    shipped = core_ref()
    if not stamped:
        notes.append(
            "This Profile does not record which Core it was assessed against — it was written "
            "before that was stamped. The next write records it.")
    elif stamped.get("sha256") != shipped.get("sha256"):
        notes.append(
            "This Profile was last written against Core %s (%s); the shipped Core is %s (%s). "
            "Ratings still load and analyse; what may have moved is which Subcategories exist."
            % (stamped.get("version"), (stamped.get("sha256") or "?")[:12],
               shipped.get("version"), (shipped.get("sha256") or "?")[:12]))
    cfg = ((store.get("overlays") or {}).get("cyberAi") or {})
    if dataset and cfg.get("enabled"):
        in_force, avail = cfg.get("datasetVersion"), dataset.get("datasetVersion")
        if in_force and avail and in_force != avail:
            notes.append(
                "The overlay was enabled on dataset %s; the shipped dataset is %s. This "
                "analysis used the shipped one. Re-run `overlay enable` to re-stamp the "
                "Profile, or disable the overlay if the older priorities were the point."
                % (in_force, avail))
    return notes


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


def _completeness_of(subset: list[dict], expected: int = None) -> dict:
    """How much of the FRAMEWORK has been looked at — denominator from the Core, not the store.

    ⚠️ `expected` is the count of Subcategories the shipped Core carries in this scope, and it
    is the whole point of this function (BL-109 T4). Until v0.80.0 `total` was `len(subset)`,
    so a Subcategory the Core has and the store does not simply **left the denominator**: a
    Profile missing a row reported complete coverage of a framework it no longer fully covers,
    exit 0, no note. The opposite direction was always loud — an assessment for a Subcategory
    the Core removed fails `check_store` by name — so the register was strict about extra rows
    and silent about missing ones, which is the wrong way round for a number that reaches a
    board page.

    A Core Subcategory absent from the store is **unassessed, not out of scope.** Out of scope
    is a declaration somebody makes; absence is a declaration nobody made, and reading it as
    `notApplicable` would let a store shrink its own denominator by deleting rows. So missing
    rows count into `total` AND into `inScope`, and `notInStore` reports how many there are.

    `expected=None` keeps the old store-relative behaviour, for callers measuring a subset that
    is not a framework scope.
    """
    scoped = in_scope(subset)
    total = len(subset) if expected is None else max(expected, len(subset))
    missing = total - len(subset)
    return {
        "total": total,
        "inScope": len(scoped) + missing,
        "notApplicable": len(subset) - len(scoped),
        "assessed": sum(1 for a in scoped if a.get("current") is not None),
        "targeted": sum(1 for a in scoped if a.get("target") is not None),
        # Absent from the store entirely. Reported rather than folded into `inScope` alone,
        # so a reader can tell "not yet rated" from "not in this Profile at all".
        "notInStore": missing,
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
    """Completeness against the CORE. The denominators come from the framework (BL-109 T4).

    `byCategory` iterates the CORE's categories, not the store's, for the same reason
    `compute_coverage`'s `byFunction` iterates `function_ids(core)`: a Category with no
    assessments at all must appear as fully unassessed rather than silently vanish from the
    dashboard. Before this it appeared only if the store happened to hold a row in it.
    """
    by_fn = _group(assessments, index, "functionId")
    by_cat = _group(assessments, index, "categoryId")
    core_fn, core_cat = {}, {}
    for meta in index.values():
        core_fn[meta["functionId"]] = core_fn.get(meta["functionId"], 0) + 1
        core_cat[meta["categoryId"]] = core_cat.get(meta["categoryId"], 0) + 1
    return {
        "overall": _completeness_of(assessments, len(index)),
        "byFunction": {fid: _completeness_of(by_fn.get(fid, []), core_fn.get(fid, 0))
                       for fid in function_ids(core)},
        "byCategory": {cid: _completeness_of(by_cat.get(cid, []), core_cat[cid])
                       for cid in sorted(core_cat)},
    }


# --- Age bands ----------------------------------------------------------------
# One notion of "old", anchored to the Profile's own configurable threshold T
# (settings.reporting.ageThresholdDays, default 180) so the engine never holds two.
#
#   within       d <= T//2
#   approaching  d <= T
#   beyond       d <= 2T
#   wellBeyond   d >  2T
#
# T//2 is not a tuned figure. It is the halfway mark to the cadence the reader already
# chose, which is the one inner split that needs no second setting to justify it; a
# configurable inner boundary would be a second notion of "old" wearing a new name.
#
# AGE_BANDS is ordered ascending by age. Reporting renders in tuple order rather than
# re-deriving it, so reordering this tuple silently reorders every rendered band.
#
# `olderThanThreshold` is unchanged and must always equal beyond + wellBeyond. The
# self-test asserts that identity at three thresholds: 180 (the default), 365 (so that
# holding is a property of the model rather than an accident of the default), and 198,
# which puts a fixture rating exactly ON the line. The third is the one that earns its
# keep. The guarantee lives in two independent expressions — `days <= threshold_days`
# below and `d > age_days` in _age() — and they can only be caught disagreeing by a
# rating sitting exactly on the boundary. With 180 and 365 alone, flipping _age()'s
# `>` to `>=` breaks the identity and every test still passes.
#
# THREE copies of this function ship, not two:
#   skills/risk-register/scripts/score_register.py
#   skills/metrics-register/scripts/metrics_analysis.py
# and both now carry the matching note back to here. The third was missing from this list
# for its whole life. Its own note said "each carries a note pointing at the others" —
# neither of the other two mentioned it, so a maintainer moving a boundary here would grep
# one sibling and change two of three copies. That is not a hypothetical: it is the exact
# shape of the drift this comment warns about.
#
# The duplication is deliberate. The obvious cleanup — one shared module, say
# skills/_shared/age.py — is rejected: every shipped script must run standalone (this
# one also resolves its assets from _SKILL_ROOT off __file__), so a cross-skill import
# needs sys.path surgery and breaks outright the moment a single skill directory is used
# on its own. The obligation that replaces it: the copies are edited together — and
# tools/check-twins.py now executes all three over a shared corpus, because each skill's
# own self-test cannot see the other copies, by construction.
# Grep the sibling paths above before changing any boundary below.
#
# What must match is the SEMANTICS — the four boundaries and the band names. What must
# NOT converge is the rendered wording: each skill's AGE_BAND_LABEL sits in a different
# sentence shape, and those live in the renderers, not here.
AGE_BANDS = ("within", "approaching", "beyond", "wellBeyond")


def age_band(days: int, threshold_days: int) -> str:
    """Which band `days` of age falls in, relative to threshold `threshold_days`.

    Every boundary is inclusive of the lower band, so a rating at exactly T is
    `approaching` and not yet `beyond` — the threshold is a cadence the reader chose to
    aim at, and hitting it is meeting it.

    Nothing here is a statement about confidence. The engine reports age; the reader
    judges what age means for a given Subcategory, because a governance outcome and an
    asset inventory go stale at completely different rates.

    A negative `days` — a well-formed confirmedAt dated in the future, which nothing
    upstream currently rejects — reports as `within`. That is the one place in this file
    where a bad date becomes a positive claim of freshness, and it is left that way
    knowingly: this function is a pure distance measurement, and an `impossible` band
    would smuggle a validation verdict into the distribution. The honest fix belongs in
    check_store, where an impossible date pair can be surfaced as the store defect it
    is rather than hidden inside a band the reader would read as good news.
    """
    if days <= threshold_days // 2:
        return "within"
    if days <= threshold_days:
        return "approaching"
    if days <= threshold_days * 2:
        return "beyond"
    return "wellBeyond"


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


def declared_criticality(jewel: dict) -> str:
    """The level a crown jewel declares, or `""` when it declares none.

    THE THIRD COPY IN THE SUITE — `vendor_register.py` and `ai_register.py` hold the others.
    Shape reused, module never imported (CAC-AP-1 s 2.6), and `check-twins.py` compares all
    copies by EXECUTING them over both shapes rather than by diffing their text.

    TWO SHAPES ARE LEGAL AND BOTH ARE READ, permanently (BL-216 Q-2):

        "criticality": "high"                                # written before v0.74.0
        "criticality": {"value": "high", "declaredBy": ...}  # written after

    `business-context` did not bump `SCHEMA_VERSION` and does not convert, so both persist on
    disk indefinitely. **Do not "fix" this by forcing one shape** — dropping either branch
    refuses somebody's existing store, and a product arguing *your records persist and stay
    defensible* does not do that. A container that is not a declared record still refuses,
    because `str({...})` is truthy and would put a Python repr where a governance decision
    belongs.
    """
    raw = jewel.get("criticality")
    if isinstance(raw, dict) and "value" in raw:
        raw = raw.get("value")
    if isinstance(raw, (dict, list, tuple, set)):
        raise ValueError(
            "crown jewel %r declares a criticality that is a %s, not a level: %.120r"
            % (jewel.get("name") or jewel.get("system") or "(unnamed)", type(raw).__name__, raw))
    return "" if raw is None else str(raw).strip()


# --- Program posture (BL-222) -------------------------------------------------
#
# ⚠️ THIS REPORT ANSWERS "CAN YOU SHOW YOUR WORK?" AND NEVER "IS YOUR WORK ANY GOOD?"
#
# Those are different questions and only the first is answerable from records. A policy
# forbidding authentication is a terrible control and a perfectly valid record: a document
# exists, a named person approved it on a date, and it is mapped to a requirement. This report
# says the record exists. Judging whether the control is sound is the CISO's job, their
# auditor's and their board's — it is not the tool's. That is `record and refuse, never judge`
# reaching the reporting layer.
#
# THE BANDS ARE NAMED FOR THE RECORD, NOT THE POSTURE (OQ4, decided 2026-08-11). `strong` and
# `weak` were rejected: a board reading "GV.PO — strong" hears "policy is fine", which is
# exactly what the caveat exists to prevent. Under these names the misreading has to be worked
# at.
BAND_WELL = "well-evidenced"
BAND_THIN = "thinly evidenced"
BAND_CRITICAL = "declared critical"
BAND_NONE = "no record"
BAND_UNKNOWN = "unknown"
POSTURE_BANDS = (BAND_WELL, BAND_THIN, BAND_CRITICAL, BAND_NONE, BAND_UNKNOWN)

POSTURE_BAND_MEANS = {
    BAND_WELL: ("A record exists, is current, and carries who decided it and on what basis. "
                "It is not a finding that the control is adequate."),
    BAND_THIN: ("A record exists but is thin, stale, unowned or unattributed. It is not a "
                "finding that the control is weak."),
    BAND_CRITICAL: ("Somebody DECLARED this area load-bearing, and the declaration is named "
                    "below. It is not a computed risk level."),
    BAND_NONE: ("No record bearing on this outcome exists anywhere this report can read. It "
                "is not a finding that the area is failing, or that nobody is doing it."),
    BAND_UNKNOWN: ("A store that would hold records here could not be read, so nothing is "
                   "known either way. A different fact from a clean register, and reported "
                   "before anything that looks like a result."),
}

# D-7, adapted from the sentence `policy_register` already ships about a single policy. The
# word "addressed" appears in NO band name, so the caveat names the bands it actually governs
# rather than a state this report does not have.
POSTURE_CAVEAT = (
    "This report measures whether a defensible RECORD exists — not whether the thing recorded "
    "is any good. `well-evidenced` means a record exists, is current, and is attributed. It is "
    "not evidence that the control is adequate, sound, or effective, and this report has no "
    "way to determine whether it is. A policy nobody follows maps exactly as well as one "
    "everybody does.")


def load_outcome_owners(path: str = None) -> dict:
    here = os.path.dirname(os.path.abspath(__file__))
    path = path or os.path.join(here, "..", "references", "outcome-owners.json")
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def expand_outcome_owners(core: dict, owners: dict) -> dict:
    """Every Subcategory in the shipped Core, resolved to its owning skills.

    The map is authored at CATEGORY grain with per-Subcategory overrides — 106 hand-typed rows
    are 106 chances to mistype one, and nobody reviews a wall of repetition. The compression
    cannot hide a gap because this expansion runs against the CORE rather than against the map,
    so an outcome the map forgot resolves to nothing and the anti-vacuity check sees it.
    """
    out = {}
    cats, subs = owners.get("categories") or {}, owners.get("subcategories") or {}
    unowned = (owners.get("unowned") or {}).get("outcomes") or {}
    for fn in core.get("hierarchy") or []:
        for cat in fn.get("categories") or []:
            for sub in cat.get("subcategories") or []:
                sid = sub["id"]
                if sid in unowned:
                    out[sid] = {"owners": [], "means": unowned[sid].get("because", ""),
                                "grain": "unowned"}
                elif sid in subs:
                    out[sid] = dict(subs[sid], grain="subcategory")
                elif cat["id"] in cats:
                    out[sid] = dict(cats[cat["id"]], grain="category")
    return out


# The stores this report reads, and the CSF link each one actually carries. ⚠️ Only these three
# carry a Subcategory reference at all — the rest of the suite records real work with no CSF
# linkage, and inventing one here would be this report guessing. Where a skill owns an outcome
# but cannot link to it, that is said on the outcome rather than papered over.
POSTURE_SOURCES = {
    "risk-register": {"script": "score_register.py", "argv": ["score", "{store}", "--json"],
                      "link": "csfSubcategoryId"},
    "policy-register": {"script": "policy_register.py", "argv": ["analyze", "{store}", "--json"],
                        "link": "mappedTo"},
    "metrics-register": {"script": "metrics_analysis.py", "argv": ["analyze", "{store}", "--json"],
                         "link": "csfSubcategoryIds"},
}


def read_posture_source(skill: str, store_path: str, skills_root: str = "",
                        timeout: int = 120) -> dict:
    """Run one store's analyze and take its payload. Never fatal.

    Copied in shape AND in wording from `attention_surface.read_producer`, deliberately. A
    store that cannot be read is REPORTED, not skipped: an outcome whose only owner is an
    unreadable store is `unknown`, never `no record`, and the two must not look the same.
    """
    spec = POSTURE_SOURCES[skill]
    root = skills_root or os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))))
    script = os.path.join(root, skill, "scripts", spec["script"])
    result = {"skill": skill, "store": store_path, "ok": False, "reason": "", "payload": None}
    if not os.path.exists(script):
        result["reason"] = "no engine at %s — the skill is not installed here" % script
        return result
    if not os.path.exists(store_path):
        result["reason"] = ("no store at %s. The source is declared and the file is not there, "
                            "which is a different fact from a clean register." % store_path)
        return result
    argv = [sys.executable, script] + [a.replace("{store}", store_path) for a in spec["argv"]]
    try:
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError) as exc:
        result["reason"] = "could not run %s: %s" % (spec["script"], exc)
        return result
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "").strip().splitlines()
        result["reason"] = ("%s exited %d: %s" % (spec["script"], proc.returncode,
                                                  tail[-1] if tail else "no output"))
        return result
    try:
        result["payload"] = json.loads(proc.stdout)
    except json.JSONDecodeError:
        result["reason"] = "%s did not emit JSON" % spec["script"]
        return result
    result["ok"] = True
    return result


def _linked_records(sources: dict) -> dict:
    """`{subcategoryId: [record summaries]}` from whichever stores were readable."""
    hits = {}

    def add(sid, skill, what, attributed, stale):
        if not sid:
            return
        hits.setdefault(str(sid).strip(), []).append(
            {"skill": skill, "what": what, "attributed": bool(attributed),
             "stale": bool(stale)})

    rr = sources.get("risk-register") or {}
    for r in ((rr.get("payload") or {}).get("risks") or []) if rr.get("ok") else []:
        add(r.get("csfSubcategoryId"), "risk-register",
            "risk %s" % r.get("id"),
            not r.get("provisionalScore") and bool(r.get("owner")),
            bool(r.get("reviewOverdue")))
    pr = sources.get("policy-register") or {}
    for pol in ((pr.get("payload") or {}).get("policies") or []) if pr.get("ok") else []:
        for req in pol.get("mappedTo") or []:
            add(req, "policy-register", "policy %s" % pol.get("id"),
                bool((pol.get("approval") or {}).get("by")),
                (pol.get("review") or {}).get("state") == "overdue")
    mr = sources.get("metrics-register") or {}
    for m in ((mr.get("payload") or {}).get("metrics") or []) if mr.get("ok") else []:
        for sid in m.get("csfSubcategoryIds") or []:
            add(sid, "metrics-register", "metric %s" % m.get("id"),
                bool(m.get("owner")), bool(m.get("stale")))
    return hits


def declared_critical_outcomes(context: dict) -> dict:
    """Outcomes a NAMED PERSON declared load-bearing — never anything this report inferred.

    ⚠️ `settings.appetite` is deliberately NOT an input. It is a bare enum set once at `init`
    with no declarer and no date, and D-5 says critical is declared, never inferred. An
    over-appetite risk is reported BESIDE a placement and never as its basis.
    """
    out = {}
    for jewel in (context or {}).get("crownJewels") or []:
        crit = declared_criticality(jewel)
        for sid in jewel.get("csfSubcategoryIds") or []:
            out.setdefault(sid, []).append({
                "basis": "crown jewel %r declared %s" % (jewel.get("name", "?"), crit or "?"),
                "declaredBy": (jewel.get("criticality") or {}).get("declaredBy", "")
                if isinstance(jewel.get("criticality"), dict) else "",
                "declaredOn": (jewel.get("criticality") or {}).get("declaredOn", "")
                if isinstance(jewel.get("criticality"), dict) else ""})
    return out


def posture(core: dict, evidence: dict, owners_map: dict, sources: dict,
            context: dict = None) -> dict:
    """Band every CSF outcome by what is RECORDED about it. No score, no percentage, no rank.

    The bands are exclusive and ordered by what the reader most needs to know first: an
    unreadable store beats everything, because nothing else said about that outcome is load
    bearing while a source is missing.
    """
    linked = _linked_records(sources)
    critical = declared_critical_outcomes(context or {})
    unread = {k: v for k, v in sources.items() if not v.get("ok")}
    states = (evidence or {}).get("states") or {}
    rows = []
    for sid, own in sorted(owners_map.items()):
        recs = linked.get(sid) or []
        owning_unread = sorted({s for s in own.get("owners") or [] if s in unread})
        if recs:
            band = (BAND_WELL if all(r["attributed"] and not r["stale"] for r in recs)
                    else BAND_THIN)
        elif owning_unread:
            band = BAND_UNKNOWN
        else:
            band = BAND_NONE
        # A Profile rating is itself a record about the outcome, so an outcome nobody linked a
        # register record to is not automatically `no record`.
        if band == BAND_NONE and states.get(sid) == "confirmed":
            band = BAND_THIN
        row = {"subcategoryId": sid, "band": band, "owners": own.get("owners") or [],
               "ownership": own.get("means", ""), "records": recs,
               "unreadOwners": owning_unread}
        if sid in critical:
            # `declared critical` does not REPLACE the evidence band — an area can be declared
            # load-bearing AND well-evidenced, and collapsing the two would lose the half the
            # CISO asked for. It is carried beside, with its declaration named.
            row["declaredCritical"] = critical[sid]
        rows.append(row)
    return {
        "bands": list(POSTURE_BANDS),
        "bandMeans": dict(POSTURE_BAND_MEANS),
        "caveat": POSTURE_CAVEAT,
        "notRead": [{"skill": k, "store": v.get("store"), "reason": v.get("reason")}
                    for k, v in sorted(unread.items())],
        "outcomes": rows,
        "counts": {b: sum(1 for r in rows if r["band"] == b) for b in POSTURE_BANDS},
        "declaredCritical": sum(1 for r in rows if r.get("declaredCritical")),
    }


def derive_evidence(assessments: list[dict], intake: list[dict], index: dict, core: dict,
                    today: str, threshold_pct: int, age_days: int) -> dict:
    """The whole derivation layer, as one pure function. No IO, no clock.

    Four states partition every tracked Subcategory:
      not-applicable   scoped out
      confirmed        in-scope, has a Current rating
      evidence-pending in-scope, no Current rating, some intake bears on it
      unrated          in-scope, no Current rating, nothing bears on it

    `revisit` is a fifth, orthogonal flag: confirmed, and material has arrived that the
    rating cannot be shown to predate. It is a reporting flag and a queue input only —
    it does NOT affect scoring. Ratings never expire; new material is what questions a
    rating, not the passage of time. There are two distinct reasons a confirmed rating
    lands in `revisit`, each carried as `reason`:
      newer-material        confirmedAt is set, and some bearing intake has a
                             sourceDate later than it
      undated-confirmation  confirmedAt is None (every rating carried over from a v1
                             Profile, by design — see references/schema.md), and some
                             intake bears on it at all

    The second reason exists because `confirmed_at and ...` — the original guard —
    silently swallowed every v1 rating: with confirmedAt None, the comparison never
    fired, so a v1 rating with fresh material against it scored `revisit == []` and
    dropped out of the queue and both dashboards as if nothing had arrived. There is
    no date to guess and confirmedAt is never backfilled (that would fabricate the
    attribution this schema exists to make honest) — so the honest answer for an
    undated confirmed rating with bearing material is "look again," not silence.
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
            if confirmed_at:
                newer = [r for r in bearing
                         if (r.get("sourceDate") or "") > confirmed_at]
                if newer:
                    revisit.append({
                        "subcategoryId": sid,
                        "text": (index.get(sid) or {}).get("text", ""),
                        "confirmedAt": confirmed_at,
                        "newestSourceDate": max(r["sourceDate"] for r in newer),
                        "intakeIds": [r["id"] for r in newer],
                        "reason": "newer-material",
                    })
            elif bearing:
                # No confirmedAt means no basis to claim this rating predates the
                # material sitting right next to it — that is a fact about the
                # rating, not a guess about a date, so every bearing record counts
                # (there is nothing to filter "newer" against). This is the v1
                # migration path: confirmedAt is deliberately never backfilled from
                # lastReviewed (schema.md, "Attribution"), so every carried-over
                # rating reaches this branch the first time intake bears on it.
                revisit.append({
                    "subcategoryId": sid,
                    "text": (index.get(sid) or {}).get("text", ""),
                    "confirmedAt": None,
                    "newestSourceDate": max(r.get("sourceDate") or "" for r in bearing),
                    "intakeIds": [r["id"] for r in bearing],
                    "reason": "undated-confirmation",
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

    def _row(sid, band, reason=None):
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
            # Only revisit rows carry a reason (newer-material or
            # undated-confirmation, from derive_evidence). None elsewhere.
            "reason": reason,
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
            + [_row(r["subcategoryId"], "revisit", r.get("reason")) for r in revisit]
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


def load_elicitation(path: str | None = None) -> dict:
    """The cold-start question bank.

    Unlike load_cold_start_rank, this does NOT degrade to an empty default when
    the file is missing. An absent rank means the queue falls back to framework
    order and is still correct. An absent bank would make `elicit` report that
    every question is settled, which is a lie about the Profile rather than a
    degraded ordering.
    """
    with open(path or DEFAULT_ELICITATION, encoding="utf-8") as fh:
        return json.load(fh)


# --- Crosswalk lenses --------------------------------------------------------
#
# A crosswalk projects an existing CSF assessment onto another framework. It is
# derived, read-only, and never stored: nothing here writes to a .csfp, and no
# control in another framework is ever rated. See references/framework-abstraction.md
# for the enforced contract, and note that "crosswalk" is not the Cyber AI Profile
# "overlay" defined below it — different mechanism, different data, no shared state.

# Bands are a share of the Profile's own scale.max, never fixed integers.
#
# Two rating scales exist (references/scale-and-scoring.md): the native 0-3
# achievement scale, and the 0-4 scale a .csfa import deliberately keeps rather
# than rescaling. A hardcoded ">= 3 is strong" would call a 0-4 Profile rated
# "Repeatable" strong while calling a native Profile rated "Fully Achieved" —
# its maximum — the same thing. scale-and-scoring.md is explicit that there is
# no honest mapping between the two scales, so the band is computed relative to
# whichever scale the Profile declares, and every rendered view names that scale
# rather than leaving the reader to assume.
CROSSWALK_BANDS = (("strong", 0.85), ("moderate", 0.60), ("weak", 0.30), ("minimal", 0.0))
CROSSWALK_BAND_UNKNOWN = "unknown"
# Distinct from "unknown": something IS rated here, but too little of the control's
# basis to band it honestly.
#
# The weakest-link minimum is taken over the RATED contributors only, so it is an
# upper bound on the true weakest link — every unrated outcome could be lower. A
# control showing "moderate" off 1 of 15 mapped Subcategories can therefore only
# overstate posture, never understate it, and that is the direction that gets a
# programme into trouble in front of a board.
#
# Suppressed rather than caveated, and gated on the Profile's existing
# reporting.scopeThresholdPct rather than a new knob, because this is the same
# judgement that setting already encodes for the headline coverage figure: below
# this share assessed, do not present a number. See references/dashboards.md —
# "a number with a warning beside it is still a number, and people read the number."
CROSSWALK_BAND_INSUFFICIENT = "insufficient"
CROSSWALK_AGGS = ("min", "mean")
CROSSWALK_DISCLAIMER = "Derived from your NIST CSF assessment — not an audit or certification."


def _crosswalk_sort_key(cid: str):
    """Natural sort, so A.5.10 follows A.5.9 and AC-2 precedes AC-10."""
    return [(0, int(p)) if p.isdigit() else (1, p)
            for p in re.split(r"(\d+)", cid or "") if p != ""]


def load_crosswalk(framework_id: str, path: str | None = None) -> dict:
    """Load one crosswalk's catalog + edge map into forward and reverse indexes.

    Returns {catalog, controls, fwd, rev, authority}. `fwd` maps a control id to
    the CSF Subcategories mapped to it; `rev` is the inverse. Only controls that
    have at least one edge appear in `fwd` — controls with no CSF mapping are
    reported by crosswalk_completeness() rather than being scored as zero.
    """
    if framework_id not in CROSSWALK_EXPECTED:
        raise ValueError(
            f"unknown crosswalk {framework_id!r}; available: "
            f"{', '.join(sorted(CROSSWALK_EXPECTED))}")
    base = path or DEFAULT_CROSSWALK_DIR
    with open(os.path.join(base, f"{framework_id}.catalog.json"), encoding="utf-8") as f:
        cat = json.load(f)
    with open(os.path.join(base, f"csf-2.0__{framework_id}.map.json"), encoding="utf-8") as f:
        mp = json.load(f)

    fwd: dict[str, list[str]] = {}
    rev: dict[str, list[str]] = {}
    for e in mp.get("edges", []):
        fwd.setdefault(e["controlId"], []).append(e["csfSubId"])
        rev.setdefault(e["csfSubId"], []).append(e["controlId"])
    for d in (fwd, rev):
        for k in d:
            d[k] = sorted(set(d[k]), key=_crosswalk_sort_key)
    return {
        "catalog": cat,
        "controls": {c["id"]: c for c in cat.get("controls", [])},
        "fwd": fwd,
        "rev": rev,
        "authority": mp.get("mappingAuthority"),
    }


def crosswalk_band(score, settings: dict | None) -> str:
    """Band a derived score as a share of the Profile's declared scale maximum."""
    if score is None:
        return CROSSWALK_BAND_UNKNOWN
    top = ((settings or {}).get("scale") or {}).get("max")
    if not top or top <= 0:
        return CROSSWALK_BAND_UNKNOWN
    share = score / top
    for name, floor in CROSSWALK_BANDS:
        if share >= floor:
            return name
    return CROSSWALK_BANDS[-1][0]


def _crosswalk_agg(vals: list, how: str):
    v = [x for x in vals if x is not None]
    if not v:
        return None
    if how == "min":
        return min(v)
    return round(sum(v) / len(v), 2)


def derive_crosswalk_coverage(assessments: list[dict], crosswalk: dict,
                              settings: dict, agg: str = "min",
                              index: dict | None = None) -> dict:
    """Project a CSF assessment onto one crosswalk's controls and themes.

    Control coverage is **weakest-link**: the minimum rating across the CSF
    Subcategories mapped to it, because a control is not satisfied by its best
    contributing outcome. Theme coverage is the **mean of its member control
    scores** regardless of `agg` — min-of-min would bottom every theme out at its
    single weakest control and report nothing useful.

    A contributor is counted, never silently dropped: not-applicable
    Subcategories are excluded from the score rather than dragging it down, and
    unrated ones leave the control unknown rather than defaulting to zero. A
    control with nothing rated behind it scores None and bands "unknown".

    A band drawn from too small a share of its basis is **suppressed** rather than
    caveated, and the score is withheld with it — see CROSSWALK_BAND_INSUFFICIENT.
    The share is measured against in-scope contributors and gated on
    `settings.reporting.scopeThresholdPct`, the same setting that suppresses the
    headline coverage figure. Suppressed controls are excluded from their theme.
    """
    if agg not in CROSSWALK_AGGS:
        raise ValueError(f"agg must be one of {CROSSWALK_AGGS}, got {agg!r}")
    by_id = {a["subcategoryId"]: a for a in assessments}
    scoped = {a["subcategoryId"] for a in in_scope(assessments)}
    threshold_pct = ((settings or {}).get("reporting") or {}).get(
        "scopeThresholdPct", DEFAULT_SETTINGS["reporting"]["scopeThresholdPct"])

    controls = []
    for cid in sorted(crosswalk["fwd"], key=_crosswalk_sort_key):
        subs = crosswalk["fwd"][cid]
        vals, unrated, not_applicable, absent = [], 0, 0, 0
        for s in subs:
            a = by_id.get(s)
            if a is None:
                absent += 1
            elif s not in scoped:
                not_applicable += 1
            elif a.get("current") is None:
                unrated += 1
            else:
                vals.append(a["current"])
        score = _crosswalk_agg(vals, agg)
        ctl = crosswalk["controls"].get(cid, {})
        # The basis is the in-scope contributors: not-applicable ones are excluded
        # from the denominator as well as the score, the same way _coverage_of()
        # measures against in-scope rows rather than every row.
        in_scope_contributors = len(vals) + unrated
        basis_pct = (100.0 * len(vals) / in_scope_contributors) if in_scope_contributors else None
        suppressed = (score is not None and basis_pct is not None
                      and basis_pct < threshold_pct)
        controls.append({
            "controlId": cid,
            "label": ctl.get("label"),
            "labelSource": ctl.get("labelSource"),
            "groupingId": ctl.get("groupingId"),
            "mappedSubcategories": subs,
            # The withheld score is NOT carried alongside the suppression flag. The
            # scope guard on the headline figure does not carry its withheld number
            # either, and for the same reason: anything present in the data gets
            # rendered by someone eventually.
            "score": None if suppressed else score,
            "band": CROSSWALK_BAND_INSUFFICIENT if suppressed
                    else crosswalk_band(score, settings),
            "bandSuppressed": suppressed,
            "basisPct": None if basis_pct is None else round(basis_pct, 1),
            "ratedContributors": len(vals),
            "unratedContributors": unrated,
            "notApplicableContributors": not_applicable,
            "absentContributors": absent,
        })

    # A suppressed control is excluded from its theme, not folded in at its withheld
    # value. Averaging in a figure we just declined to show would smuggle it back
    # into the report one level up.
    scored_by_group: dict[str, list] = {}
    members_by_group: dict[str, int] = {}
    withheld_by_group: dict[str, int] = {}
    for c in controls:
        members_by_group[c["groupingId"]] = members_by_group.get(c["groupingId"], 0) + 1
        if c["bandSuppressed"]:
            withheld_by_group[c["groupingId"]] = withheld_by_group.get(c["groupingId"], 0) + 1
        if c["score"] is not None:
            scored_by_group.setdefault(c["groupingId"], []).append(c["score"])
    groupings = []
    for g in crosswalk["catalog"].get("groupings", []):
        member_scores = scored_by_group.get(g["id"], [])
        members = members_by_group.get(g["id"], 0)
        gs = _crosswalk_agg(member_scores, "mean")
        # The same rule one level up, and for the same reason. Suppressing thin
        # controls removes scores from this mean, and the ones removed are not
        # randomly distributed: on the golden fixture it moved theme A.8 from
        # moderate 3.2 to strong 3.5, because the low figures were the ones with
        # the weakest basis. Without this the optimism simply relocates from the
        # control row to the theme cell.
        g_basis = (100.0 * len(member_scores) / members) if members else None
        # Two ways a theme is withheld rather than unknown. It has a mean but too
        # few members behind it; or every member that had anything behind it was
        # itself withheld, which is not the same as nothing being rated at all —
        # calling that "not yet rated" would understate what is actually known.
        g_suppressed = (
            (gs is not None and g_basis is not None and g_basis < threshold_pct)
            or (gs is None and withheld_by_group.get(g["id"], 0) > 0))
        groupings.append({
            "groupingId": g["id"],
            "label": g.get("label"),
            "score": None if g_suppressed else gs,
            "band": CROSSWALK_BAND_INSUFFICIENT if g_suppressed
                    else crosswalk_band(gs, settings),
            "bandSuppressed": g_suppressed,
            "basisPct": None if g_basis is None else round(g_basis, 1),
            "controlsScored": len(member_scores),
            "controlsMapped": members,
        })

    # Optional: enough detail about every Subcategory this lens references for a
    # consumer to answer "what sits behind this control?" without a second pass
    # over the store. The gaps list cannot serve that — it omits fully-met and
    # not-applicable rows, so a reverse lookup built on it would quietly lose
    # exactly the outcomes that are doing well.
    sub_detail = None
    if index is not None:
        sub_detail = {}
        for sid in sorted(crosswalk["rev"]):
            a = by_id.get(sid) or {}
            sub_detail[sid] = {
                "text": (index.get(sid) or {}).get("text"),
                "current": a.get("current"),
                "target": a.get("target"),
                "applicability": a.get("applicability", "in-scope"),
            }

    scale = (settings or {}).get("scale") or {}
    return {
        "frameworkId": crosswalk["catalog"].get("frameworkId"),
        "frameworkName": crosswalk["catalog"].get("name"),
        "frameworkVersion": crosswalk["catalog"].get("version"),
        "mappingAuthority": crosswalk["authority"],
        "license": crosswalk["catalog"].get("license"),
        "controls": controls,
        "groupings": groupings,
        # Echoed so a renderer states the scale a band was computed against
        # instead of leaving two different scales looking comparable.
        "scale": {"min": scale.get("min"), "max": scale.get("max"),
                  "labels": scale.get("labels")},
        "aggregation": {"control": agg, "grouping": "mean"},
        # Stated rather than left implicit, so a renderer can explain a withheld
        # band instead of hardcoding the threshold it was withheld against.
        "suppression": {
            "thresholdPct": threshold_pct,
            "setting": "reporting.scopeThresholdPct",
            "controlsSuppressed": sum(1 for c in controls if c["bandSuppressed"]),
            "groupingsSuppressed": sum(1 for g in groupings if g["bandSuppressed"]),
            "basis": "in-scope contributors per control; bandable controls per theme",
        },
        "disclaimer": CROSSWALK_DISCLAIMER,
        **({"subcategories": sub_detail} if sub_detail is not None else {}),
    }


def crosswalk_reverse_lookup(crosswalk: dict, control_id: str,
                             assessments: list[dict], settings: dict) -> dict:
    """The auditor's question: which CSF outcomes sit behind this control?"""
    by_id = {a["subcategoryId"]: a for a in assessments}
    known = control_id in crosswalk["controls"]
    subs = crosswalk["fwd"].get(control_id, [])
    ctl = crosswalk["controls"].get(control_id, {})

    behind = []
    for s in subs:
        a = by_id.get(s) or {}
        behind.append({
            "csfSubId": s,
            "current": a.get("current"),
            "target": a.get("target"),
            "applicability": a.get("applicability", "in-scope"),
            "status": a.get("status"),
        })
    if not known:
        note = (f"{control_id} is not a control in "
                f"{crosswalk['catalog'].get('name', 'this framework')}.")
    elif not subs:
        note = "No CSF Subcategory maps here — assess this control directly against the standard."
    else:
        note = ""
    in_scope_behind = [b for b in behind if b["applicability"] == "in-scope"]
    scores = [b["current"] for b in in_scope_behind if b["current"] is not None]
    score = _crosswalk_agg(scores, "min")
    # Same suppression as the forward view. If these two disagreed, a reader could
    # look up a control the table declined to band and be handed the band anyway.
    threshold_pct = ((settings or {}).get("reporting") or {}).get(
        "scopeThresholdPct", DEFAULT_SETTINGS["reporting"]["scopeThresholdPct"])
    basis_pct = (100.0 * len(scores) / len(in_scope_behind)) if in_scope_behind else None
    suppressed = (score is not None and basis_pct is not None and basis_pct < threshold_pct)
    return {
        "controlId": control_id,
        "known": known,
        "label": ctl.get("label"),
        "groupingId": ctl.get("groupingId"),
        "score": None if suppressed else score,
        "band": CROSSWALK_BAND_INSUFFICIENT if suppressed else crosswalk_band(score, settings),
        "bandSuppressed": suppressed,
        "basisPct": None if basis_pct is None else round(basis_pct, 1),
        "behind": behind,
        "note": note,
        "disclaimer": CROSSWALK_DISCLAIMER,
    }


def crosswalk_completeness(crosswalk: dict, assessments: list[dict]) -> dict:
    """Both honesty lists: what the lens cannot see, in each direction.

    `controlsOutsideCSF` are controls no CSF Subcategory maps to — they must be
    assessed directly against the standard, and a coverage view that omitted
    them would overstate what one CSF assessment can tell you. `csfNotInLens`
    are rated CSF outcomes no control in this lens references, i.e. work already
    done that this projection gives no credit for.

    `controlsCategoryOnly` is the third case, and it is neither of the other two.
    The source export also hangs references off Category rows, which carry no
    Subcategory to key an edge on. A control named only there cannot be scored —
    there is no rated outcome beneath it at the right grain — but telling a reader
    CSF does not reach it would be false. It gets its own list rather than being
    folded into either neighbour.
    """
    all_controls = set(crosswalk["controls"])
    mapped = set(crosswalk["fwd"])
    rated = {a["subcategoryId"] for a in in_scope(assessments)
             if a.get("current") is not None}
    unmapped = sorted(all_controls - mapped, key=_crosswalk_sort_key)
    coarse = [c for c in unmapped
              if (crosswalk["controls"].get(c) or {}).get("csfReference") == "category-only"]
    coarse_set = set(coarse)
    # The scope the catalogue declares about itself. Without it an empty
    # controlsOutsideCSF is ambiguous between "CSF reaches everything in this
    # framework" and "nothing else is catalogued here", and those are opposite
    # claims. Two of the three bundled catalogues are the second case.
    scope = (crosswalk["catalog"].get("catalogueScope") or {})
    return {
        "controlsTotal": len(all_controls),
        "controlsMapped": len(mapped & all_controls),
        "controlsOutsideCSF": [c for c in unmapped if c not in coarse_set],
        "controlsCategoryOnly": coarse,
        "csfNotInLens": sorted(rated - set(crosswalk["rev"])),
        "catalogueScope": scope.get("coverage"),
        "catalogueScopeNote": scope.get("note"),
    }


OVERLAY_FOCUS_AREAS = ("secure", "defend", "thwart")
OVERLAY_MODES = ("advisory", "reorder")   # `floor` is deliberately absent; see
                                          # references/cyber-ai-overlay.md


def validate_overlay_dataset(data: dict, index: dict) -> dict:
    """Assert a Cyber AI Profile dataset is well formed. Raises ValueError on any defect.

    Well formed is not the same as correct. This catches an extraction that
    dropped a cell or mangled a number; it cannot catch a priority transcribed
    as 2 when the source says 1. That is what the hand spot-check is for.
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
            # isinstance(pri, bool) must be rejected first — True == 1 in Python,
            # so a JSON `true` would pass `in (1, 2, 3)` and then read as High
            # priority everywhere downstream. Same trap as the cold-start ranks.
            if isinstance(pri, bool) or pri not in (1, 2, 3):
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


def resolve_overlay(sub_id: str, cfg: dict | None, dataset: dict) -> dict | None:
    """What the overlay says about one Subcategory, or None if it says nothing.

    Returns None — never a default — when the overlay is disabled, no areas are
    selected, or the Subcategory is absent from the dataset. A default would let
    an absent entry silently participate in ordering as though the dataset had
    spoken about it.

    effectivePriority is the MINIMUM across selected areas because NIST's 1/2/3
    is High/Moderate/Foundational: 1 is the most urgent. Minimum therefore means
    "the most urgent selected area wins", and deselecting an area can only relax
    the result, never tighten it.
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


def _settled_subjects(store: dict) -> set:
    """Subcategories that no longer need a cold-start question asked about them.

    Rated, scoped out, or already carrying recorded material. The last clause
    is deliberate: once a source names a Subcategory it is queue work, and
    asking the opening question again would collect the same material twice.
    """
    settled = set()
    for a in store.get("assessments", []):
        if a.get("current") is not None or a.get("applicability") == "not-applicable":
            settled.add(a["subcategoryId"])
    for rec in store.get("intake", []):
        settled.update(rec.get("subjects", []))
    return settled


def _elicit_rows(store: dict, top: int | None = 3, bank: dict | None = None) -> list:
    """Unsettled elicitation questions in bank order, with their open subjects.

    A row carries the question and what is still open under it — never a rating,
    proposed or otherwise. The same anti-drift rule the queue lives under: this
    command presents a question, and a human presents the answer.
    """
    bank = bank or load_elicitation()
    settled = _settled_subjects(store)
    rows = []
    for q in bank["questions"]:
        unsettled = [s for s in q["resolves"] if s not in settled]
        if not unsettled:
            continue
        rows.append({"id": q["id"], "ask": q["ask"],
                     "listenFor": q["listenFor"], "unsettled": unsettled,
                     "resolves": list(q["resolves"])})
    return rows[:top] if top is not None else rows


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


def attention_lists(store: dict, index: dict, today: str, age_days: int,
                    *, top: int = 10) -> dict:
    """What a reviewer must look at. `today` is passed in — never read from the clock.

    `age_days` is the Profile's own ageThresholdDays, used only to band each row's
    confirmation age. It is REQUIRED and deliberately has no default: a default would be
    a second place this engine holds the age threshold, which is the one thing the note
    above AGE_BANDS forbids ("so the engine never holds two"). It also turns a caller that
    forgets to pass it from a silent fallback to 180 — caught only for as long as some
    assertion happens to exist — into an immediate TypeError.

    `top` is keyword-only for that guarantee's sake. Left positional, a call site that
    dropped `age_days` would simply slide `top` into it and band every row against a
    10-day cadence, which is not a TypeError and not 180 either — a new silent wrong
    answer in place of the one being designed out.
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


def coverage_stdout(guard: dict, cov: dict | None) -> str:
    """The coverage figure as it may be spoken on stdout — or the reason it may not be.

    The scope guard's stated reason for suppressing the headline is that the number must
    not reappear one document over. Three commands were printing it to the terminal
    anyway while the dashboards withheld it, and an agent reads stdout and repeats it to
    the user — so the guard was being routed around by the tool's own output.

    One function so the three sites cannot drift: `analyze`/renderers, `snapshot`, `diff`.
    """
    if guard.get("suppressed"):
        return (f"withheld ({guard.get('assessed', 0)} of {guard.get('inScope', 0)} "
                f"assessed, below the {guard.get('thresholdPct', 60)}% threshold)")
    if not cov or cov.get("percent") is None:
        return "not yet targeted"
    return f"{cov['percent']:.1f}% ({cov['n']}/{cov['d']})"


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
    """Tiny --flag parser. `--x a b` -> {'x': ['a','b']}; `--x a` -> {'x': 'a'}; `--x` -> {'x': True}.

    A repeated flag accumulates rather than overwriting. It used to overwrite, silently:
    `--function ID=3 --function PR=1 --function RS=2` applied RS and dropped the other
    two, exit 0, no warning. The space-separated form is what SKILL.md teaches and it
    always worked, but the usage strings render as `[--function GV=N ...]`, and that `...`
    reads as "repeatable" to anyone typing at a shell. Losing two thirds of a tier
    judgment without saying so is the worst available outcome, so both forms now mean the
    same thing. Applies to every multi-value flag: --subjects, --evidence, --linked,
    --org-units, --threat-types.
    """
    pos, opt, i = [], {}, 0
    while i < len(args):
        a = args[i]
        if a.startswith("--"):
            key, vals, j = a[2:], [], i + 1
            while j < len(args) and not args[j].startswith("--"):
                vals.append(args[j]); j += 1
            new = (vals if len(vals) > 1 else vals[0]) if vals else True
            if key in opt:
                # `--x a --x b` is `--x a b`. A bare repeat (`--x --x`) stays True.
                merged = _list(opt[key]) + _list(new)
                opt[key] = merged if merged else True
            else:
                opt[key] = new
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

    cw_problems = check_crosswalks(index_subcategories(core))
    if cw_problems:
        print("\nCrosswalk integrity check FAILED:", file=sys.stderr)
        for p in cw_problems:
            print(f"  - {p}", file=sys.stderr)
        return 1
    print("  Crosswalks     " + "; ".join(
        f"{fid} {w['edges']}e/{w['controls']}c ({w['labelSource']})"
        for fid, w in sorted(CROSSWALK_EXPECTED.items())))
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

    _ov = (store.get("overlays") or {}).get("cyberAi") or {}
    snap = {
        "id": re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-"),
        "label": label, "ts": ts,
        "note": _s(opt.get("note", "")) if opt.get("note") is not True else "",
        "assessments": copy.deepcopy(store["assessments"]),
        # Action items are frozen too: without them the diff cannot report work opened
        # and closed, which is half of "what changed since last review".
        "actionItems": copy.deepcopy(store["actionItems"]),
        "rollups": rollups(store, index, core),
        # WHICH DATA PRODUCED THIS SNAPSHOT (BL-109 T5).
        #
        # `references/schema.md` and `references/cyber-ai-overlay.md` both said the dataset
        # version was "stamped into snapshots". It was not: a snapshot's keys were exactly the
        # seven above, and the serialised record contained no `dataset` or `overlay` substring
        # anywhere. Of the two ways to end a false claim — make it true or delete it — this one
        # is worth making true. A snapshot is a stored report a board reads months later, and a
        # stored report that cannot say what produced it is this item's whole subject, frozen.
        #
        # `datasetVersion` is null when the overlay is off, which is a fact rather than an
        # absence: the snapshot was taken with no overlay in force.
        "coreRef": dict(core_ref(core)),
        "datasetVersion": (_ov.get("datasetVersion") if _ov.get("enabled") else None),
    }
    store["snapshots"].append(snap)
    append_history(store, "snapshot-created", rationale=snap["note"] or label,
                   actor=_s(opt.get("actor")) if isinstance(opt.get("actor"), (str, list)) else None, ts=ts)
    save_store(store, path, ts)

    cov = snap["rollups"]["coverage"]["overall"]
    rep = store["profile"]["settings"]["reporting"]
    guard = derive_evidence(store["assessments"], store.get("intake", []), index, core,
                            _today(), rep["scopeThresholdPct"],
                            rep["ageThresholdDays"])["scopeGuard"]
    pct = coverage_stdout(guard, cov)
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
    rep = store["profile"]["settings"]["reporting"]
    guard = derive_evidence(store["assessments"], store.get("intake", []), index, core,
                            _today(), rep["scopeThresholdPct"],
                            rep["ageThresholdDays"])["scopeGuard"]
    if guard["suppressed"]:
        # Below the threshold the movement is as unreportable as the level: a delta
        # between two figures that both describe a minority describes the minority too.
        print(f"  Coverage: {coverage_stdout(guard, None)}. Subcategory changes below.")
    elif ov["delta"] is None:
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

    Twinned with skills/risk-register/scripts/score_register.py::_iso_date, which carries
    the matching note: same name, same rule, same reason, deliberately duplicated on the
    same terms as age_band() above. Edit the two together.
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


def _cmd_crosswalk(args):
    """Read a Profile through another framework's controls. Never writes.

    Distinct from `overlay`, which enables the Cyber AI Profile and does rewrite
    the store. A crosswalk is a projection: it needs no re-assessment, changes
    nothing, and is chosen when you report rather than when you assess.
    """
    pos, opt = parse_flags(args)
    usage = ("usage: crosswalk list\n"
             "       crosswalk coverage <store.csfp> --lens iso-27001-2022 [--agg min|mean] [--json]\n"
             "       crosswalk reverse  <store.csfp> --control 'A.8.9' [--lens iso-27001-2022]")
    if not pos:
        raise ValueError(usage)
    sub = pos[0]

    if sub == "list":
        for fid, want in sorted(CROSSWALK_EXPECTED.items()):
            cw = load_crosswalk(fid)
            cat = cw["catalog"]
            print(f"{fid:18} {cat.get('name')} ({cat.get('version')})")
            print(f"{'':18} {want['edges']} edges · {want['controls']} controls · "
                  f"{len(cw['fwd'])} mapped · authority {cw['authority']}")
            print(f"{'':18} labels: {want['labelSource']} · licence {cat.get('license')}")
        print("\nProjections are derived from your CSF assessment — not an audit or "
              "certification.")
        return 0

    path = _require_store(pos[1:], usage)
    core = load_core(); index = index_subcategories(core)
    store = load_store(path)
    settings = store["profile"]["settings"]
    asmts = store["assessments"]
    lens = _s(opt.get("lens")) if isinstance(opt.get("lens"), (str, list)) else None
    if not lens:
        raise ValueError("--lens is required. " + usage)
    cw = load_crosswalk(lens)
    scale_max = settings.get("scale", {}).get("max")

    if sub == "coverage":
        agg = _s(opt.get("agg")) if isinstance(opt.get("agg"), (str, list)) else "min"
        cov = derive_crosswalk_coverage(asmts, cw, settings, agg=agg)
        comp = crosswalk_completeness(cw, asmts)
        if opt.get("json"):
            cov["completeness"] = comp
            sys.stdout.write(json.dumps(cov, indent=2, ensure_ascii=False) + "\n")
            return 0
        print(f"{cov['frameworkName']} ({cov['frameworkVersion']}) — projected from "
              f"{store['profile'].get('name', 'this Profile')}")
        print(f"  bands are a share of this Profile's 0-{scale_max} scale · "
              f"control = {agg} of mapped Subcategories · theme = mean of member controls")
        print(f"  mapping authority: {cov['mappingAuthority']}\n")
        sup = cov["suppression"]
        for g in cov["groupings"]:
            if not (g["controlsScored"] or g["bandSuppressed"]):
                continue
            score = "  —  " if g["score"] is None else f"{g['score']:<5}"
            print(f"  {g['groupingId']:8} {g['band']:13} {score} "
                  f"({g['controlsScored']} of {g['controlsMapped']} controls)  {g['label']}")
        rated = [c for c in cov["controls"] if c["score"] is not None]
        print(f"\n  {len(rated)} of {len(cov['controls'])} mapped controls carry a published band")
        if sup["controlsSuppressed"] or sup["groupingsSuppressed"]:
            print(f"  withheld as too thinly rated to band: "
                  f"{sup['controlsSuppressed']} control(s), "
                  f"{sup['groupingsSuppressed']} theme(s) — under "
                  f"{sup['thresholdPct']}% of their basis rated "
                  f"({sup['setting']})")
        outside = len(comp["controlsOutsideCSF"])
        if outside:
            print(f"  {outside} control{'' if outside == 1 else 's'} no CSF Subcategory reaches — "
                  f"assess {'it' if outside == 1 else 'those'} directly against the standard")
        coarse = comp.get("controlsCategoryOnly") or []
        if coarse:
            print(f"  {len(coarse)} referenced only at CSF Category level, so not scored "
                  f"here though CSF does reach {'it' if len(coarse) == 1 else 'them'}: "
                  f"{', '.join(coarse)}")
        if comp["csfNotInLens"]:
            print(f"  {len(comp['csfNotInLens'])} rated CSF outcomes this lens cannot see: "
                  f"{', '.join(comp['csfNotInLens'][:6])}"
                  f"{' ...' if len(comp['csfNotInLens']) > 6 else ''}")
        print(f"\n  {CROSSWALK_DISCLAIMER}")
        return 0

    if sub == "reverse":
        control = _s(opt.get("control")) if isinstance(opt.get("control"), (str, list)) else None
        if not control:
            raise ValueError("--control is required. " + usage)
        rl = crosswalk_reverse_lookup(cw, control, asmts, settings)
        print(f"{rl['controlId']}  {rl['label'] or ''}")
        if rl["note"]:
            print(f"  {rl['note']}")
        if rl["behind"]:
            rated = sum(1 for b in rl["behind"]
                        if b["current"] is not None and b["applicability"] == "in-scope")
            basis = sum(1 for b in rl["behind"] if b["applicability"] == "in-scope")
            if rl["bandSuppressed"]:
                thr = ((settings or {}).get("reporting") or {}).get(
                    "scopeThresholdPct", DEFAULT_SETTINGS["reporting"]["scopeThresholdPct"])
                print(f"  band withheld — only {rated} of {basis} mapped outcomes are rated, "
                      f"under the {thr}% this Profile requires. What sits behind it:")
            elif rl["score"] is None:
                print("  not yet rated — nothing mapped here carries a rating. Behind it:")
            else:
                print(f"  derived {rl['band']} (score {rl['score']} of {scale_max}) "
                      f"— weakest link of:")
            for b in rl["behind"]:
                cur = "unrated" if b["current"] is None else f"{b['current']}/{scale_max}"
                na = "  [not applicable]" if b["applicability"] != "in-scope" else ""
                txt = index.get(b["csfSubId"], {}).get("text", "")
                print(f"    {b['csfSubId']:11} {cur:>9}{na}  {trunc_text(txt, 62)}")
        print(f"\n  {CROSSWALK_DISCLAIMER}")
        return 0

    raise ValueError(usage)


def trunc_text(s: str, n: int) -> str:
    s = (s or "").strip()
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


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


def _cmd_overlay(argv):
    """Turn the NIST Cyber AI Profile overlay on or off for this Profile.

    The overlay reweights the same 106 Subcategories and adds none, so enabling
    it adds no assessment work — it changes the order in which existing work is
    presented, and it says so on every surface that reports it.

    Every validation happens before `cfg` is touched, so a refused enable leaves
    the stored selection exactly as it was rather than half-written.
    """
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
    index = index_subcategories(load_core())
    # --dataset is undocumented in the usage banner on purpose: it exists so the
    # tests can run against examples/fixture-cyber-ai.json, not as a way to point
    # a Profile at an unvetted priority table.
    dataset = load_overlay_dataset(
        _s(opt["dataset"]) if isinstance(opt.get("dataset"), (str, list)) else None,
        index)
    cfg = store["overlays"]["cyberAi"]

    if sub == "list":
        print("cyber-ai — NIST Cyber AI Profile overlay")
        print(f"  dataset      {dataset['datasetVersion']}")
        print(f"  source       {dataset['sourceStatus']}, published "
              f"{dataset['sourcePublished']}")
        print(f"  {dataset['sourceUrl']}")
        print(f"  focus areas  {', '.join(dataset['focusAreas'])}")
        print("")
        if cfg["enabled"]:
            print(f"  ENABLED  areas: {', '.join(cfg['focusAreas']) or 'none'}  "
                  f"mode: {cfg['mode']}  dataset in force: {cfg['datasetVersion']}")
        else:
            print("  disabled. This Profile is not affected by the overlay.")
        # The two versions were printed on adjacent lines and never compared — the cheapest
        # possible place to notice, and the place it was not noticed (BL-109 T1).
        for note in provenance_notes(store, dataset):
            print("")
            print(f"  note: {note}")
        print("")
        print("Priority indicates sequencing, not required maturity. Enabling adds "
              "no assessment work — the overlay reweights the existing 106 "
              "Subcategories and adds none.")
        return 0

    ts = _s(opt["ts"]) if isinstance(opt.get("ts"), (str, list)) else _now()
    actor = _s(opt["actor"]) if isinstance(opt.get("actor"), (str, list)) else None

    if sub == "disable":
        was = cfg["enabled"]
        cfg["enabled"] = False
        if was:
            append_history(store, "overlay-disabled", ts=ts, actor=actor,
                           rationale="cyber-ai overlay disabled")
        save_store(store, path, ts)
        print("cyber-ai overlay disabled. Focus areas and mode kept, so re-enabling "
              "is one command.")
        return 0

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
        # parse_flags splits on spaces and never on commas, so `--focus a,b`
        # arrives as one unrecognised token. Name that specifically: a bare
        # "unknown focus area" reads as a typo and sends people looking for one.
        hint = ""
        if any("," in b for b in bad):
            hint = ("\nFocus areas are separated by spaces, not commas: "
                    "--focus secure thwart")
        raise ValueError(
            f"Unknown focus area(s) {', '.join(repr(b) for b in bad)}. "
            f"Valid: {', '.join(OVERLAY_FOCUS_AREAS)}.{hint}")

    mode = _s(opt["mode"]) if isinstance(opt.get("mode"), (str, list)) else "reorder"
    if mode == "floor":
        # Refused with its reason, not as an unknown value. `floor` was in the
        # original design and was cut; anyone working from that design will type
        # it, and "unknown mode" would send them hunting for a typo.
        raise ValueError(
            "--mode floor is not available. It would map NIST proposed priority "
            "onto a raised target, and that mapping is scale-dependent: the rating "
            "scale is a per-Profile setting, native Profiles run 0-3 while Profiles "
            "converted from the web tool run 0-4, and there is no honest mapping "
            "between them (references/scale-and-scoring.md). A fixed "
            "priority-to-target table would mean different things on two Profiles "
            "that both load here.\n\n"
            "Use --mode reorder, which sequences the work without asserting a "
            "maturity level NIST does not claim.")
    if mode not in OVERLAY_MODES:
        raise ValueError(f"--mode must be one of {', '.join(OVERLAY_MODES)}, "
                         f"got {mode!r}.")

    cfg["enabled"] = True
    cfg["focusAreas"] = [a for a in OVERLAY_FOCUS_AREAS if a in focus]
    cfg["mode"] = mode
    cfg["datasetVersion"] = dataset["datasetVersion"]
    append_history(store, "overlay-enabled", ts=ts, actor=actor,
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
    return 0


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
            if r.get("reason") == "undated-confirmation":
                print("    this rating carries no confirmation date, so it cannot be "
                      "shown to predate this material")
            else:
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


def _cmd_elicit(args):
    pos, opt = parse_flags(args)
    path = _require_store(pos, "usage: elicit <store.csfp> [--top N] [--json]")
    # Three questions by default. This is a conversation opener, not a
    # questionnaire; handing over nine at once turns it back into one.
    top = int(_s(opt.get("top"))) if isinstance(opt.get("top"), (str, list)) else 3
    if top < 0:
        raise ValueError("--top must be zero or greater.")
    store = load_store(path)
    bank = load_elicitation()
    # Slice only for display. Every "nothing left" claim below is made against
    # all_rows, never rows — the same defect --top 0 once produced in the queue.
    all_rows = _elicit_rows(store, top=None, bank=bank)
    rows = all_rows[:top]

    if opt.get("json"):
        sys.stdout.write(json.dumps(
            {"disclaimer": bank["disclaimer"], "rule": bank["theRule"],
             "remaining": len(all_rows), "questions": rows},
            indent=2, ensure_ascii=False) + "\n")
        return 0

    if not all_rows:
        print("Every Subcategory in the cold-start bank is settled — rated, scoped "
              "out, or already carrying recorded material.")
        print("That is not the same as finished. `queue` is where the remaining "
              "work is.")
        return 0

    if not rows:
        print(f"{len(all_rows)} questions still open, but --top {top} is showing "
              "none of them.")
        return 0

    print(f"Cold-start elicitation — {len(all_rows)} of {len(bank['questions'])} "
          f"questions still open (showing {len(rows)})\n")
    for r in rows:
        print(f"{r['id']}  {r['ask']}")
        print(f"    Still open: {', '.join(r['unsettled'])}")
        print(f"    Listen for: {r['listenFor']}")
        print()
    print(bank["theRule"])
    print()
    print("Record an answer as one source:")
    print(f"  python3 scripts/profile_analysis.py intake add {path} \\")
    print("    --label '<what the conversation was, in their words>' \\")
    print("    --subjects <only the ids the answer actually spoke to> \\")
    print("    --source-date <when it happened> --recorded-by <name>")
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


# --- CAC-AP-1: the applicability profile, read as data --------------------------------
#
# The consumer with both sides of its question, and the only one so far besides
# `incident-materiality` that can report a DISAGREEMENT rather than only a narrowing.
#
# The battery is the NIST Cyber AI Profile (IR 8596), and the gate is NOT the overlay as a
# whole. This skill's own `overlay enable` help is why:
#
#   secure  — you build or deploy AI systems
#   defend  — your security programme uses AI
#   thwart  — attackers use AI against you. THIS APPLIES WHETHER OR NOT YOU USE AI AT ALL.
#
# So `aiInUse` gates `secure` and `defend` only. Gating the whole overlay on it would tell
# an organisation with no AI to switch off the lens that covers attackers using AI against
# THEM — narrowing away a question that is not conditional on anything the profile declares,
# which is the exact harm §2.2 is written to prevent, arriving through the front door.
#
# Unlike the registers, a `.csfp` RECORDS the answer: the enabled flag and the focus areas
# are facts in the store. So this consumer holds the profile's declaration and the Profile's
# own state together, and where they disagree it says so in both directions:
#
#   * AI declared in use, no AI-use focus area applied -> the assessment is missing a lens
#     it is owed
#   * AI declared NOT in use, `secure` or `defend` applied -> the assessment is weighted for
#     something the organisation says it does not do. `thwart` alone is never a conflict.
#
# Reported, never resolved — the same rule `incident-materiality` applies to a clock. A
# profile narrows the default question set; it does not reach into a Profile and switch an
# overlay on or off, because which of the two statements is wrong is a human's call.

# The focus areas that turn on whether the organisation itself uses AI. `thwart` is
# deliberately absent: it is conditional on the threat landscape, not on this flag.
AI_USE_FOCUS = ("secure", "defend")

CONTEXT_CONTRACT = "CAC-AP-1"
CONTEXT_SKILL = "posture"
CONTEXT_BATTERIES = {
    "ai-overlay": {"flag": "aiInUse", "label": "NIST Cyber AI Profile overlay (IR 8596)",
                   "question": "are the AI-use focus areas of the Cyber AI Profile overlay "
                               "(secure, defend) applied to this Profile?"},
}


def load_context(path: str) -> dict:
    """Read an applicability payload. As data — this skill imports no other skill (§2.6).

    Both refusals are deliberate. `--context` was passed on purpose, so a payload that
    cannot be honoured must say so rather than quietly leave the Profile un-narrowed: a full
    question set would read as a profile that decided nothing applied.

    Twinned with `skills/vendor-register/scripts/vendor_register.py`, which holds
    the family list. Compared under CAC-TW-1 by running all seven `--context`
    consumers against a corpus of malformed payloads (BL-218). What must agree is
    WHICH payloads are refused and what is returned, never the wording: two of the
    seven refuse with `ValueError` and five with a local `Refusal`, and each is that
    engine's own refusal channel.
    """
    try:
        with open(path, encoding="utf-8") as fh:
            payload = json.load(fh)
    except FileNotFoundError:
        raise ValueError(f"no such context payload: {path}")
    except OSError as exc:
        # A DIRECTORY, an unreadable file, a symlink to nowhere. `except FileNotFoundError`
        # does NOT catch `IsADirectoryError`, so `--context .` or `--context ~/ctx/` came out
        # of all seven copies as a raw traceback until BL-226 — the same BL-169 D-1 failure
        # BL-218 was raised for, one exception class along. Caught after FileNotFoundError,
        # which is an OSError subclass and keeps its own sentence.
        raise ValueError(f"cannot read the context payload {path}: "
                         f"{exc.strerror or exc}")
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path} is not valid JSON (line {exc.lineno}, "
                         f"column {exc.colno}): {exc.msg}")
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object, got {type(payload).__name__}")
    # A RAW .biz STORE. Refused with the command that produces the right file, because a
    # refusal that names no fix turns a five-second correction into a support question.
    # Checked BEFORE the contract clause and not after: a raw store carries no
    # contractVersion, so answering it with the generic contract message would throw away the
    # one sentence that tells the reader what to run (BL-226 T3).
    if payload.get("family") == "business-context":
        raise ValueError(
            f"{path} is a raw .biz store, not an exported payload. Run "
            f"`business_context.py export {path} --out ctx.json` and pass that: the "
            f"narrowing decision belongs to that skill, and CAC-AP-1 §2.6 makes the "
            f"transport data rather than an import.")
    got = payload.get("contractVersion")
    if got != CONTEXT_CONTRACT:
        raise ValueError(
            f"{path} declares contractVersion {got!r}; this engine reads "
            f"{CONTEXT_CONTRACT!r}. Produce one with `business_context.py export <file.biz>`.")
    if not isinstance(payload.get("applicability"), dict):
        raise ValueError(
            f"{path} carries no decided `applicability`, so this skill cannot tell which "
            f"batteries the profile narrowed away. Re-export it with "
            f"`business_context.py export <file.biz>`; the narrowing decision belongs to "
            f"that skill and is not re-derived here.")
    return payload


def load_ai_signal(path: str) -> dict:
    """Read an `ai-register export-signal` payload. Optional, and evidence only.

    `ai-register` counts what an organisation actually runs. This skill asks whether the
    AI-use focus areas are applied to the Profile, and until now asked that of a human with
    nothing to hand. The signal gives the question EVIDENCE and never an answer: it carries
    counts, no ratings and no recommendation, and the sentences below still say "resolve it"
    rather than resolving it.

    Absent, everything behaves exactly as it did — the key is omitted rather than set to
    None, on the same rule as the overlay block.
    """
    try:
        with open(path, encoding="utf-8") as fh:
            payload = json.load(fh)
    except FileNotFoundError:
        raise ValueError(f"no such AI signal: {path}")
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path} is not valid JSON (line {exc.lineno}, "
                         f"column {exc.colno}): {exc.msg}")
    if not isinstance(payload, dict) or payload.get("export") != "signal":
        raise ValueError(
            f"{path} is not an AI inventory signal (export="
            f"{payload.get('export') if isinstance(payload, dict) else None!r}). Produce one "
            f"with `ai_register.py export-signal`.")
    counts = payload.get("counts")
    if not isinstance(counts, dict):
        raise ValueError(f"{path} carries no `counts`, so there is no evidence in it.")
    # Counts only, asserted rather than trusted. A rating or a priority arriving here would be
    # the other skill answering this skill's question, which is the one thing it must not do.
    bad = sorted(k for k in counts if not isinstance(counts[k], int)
                 or isinstance(counts[k], bool))
    if bad:
        raise ValueError(
            f"{path} carries non-count value(s) for {', '.join(bad)}. The signal is counts "
            f"only: which focus areas a Profile applies is a judgement, and it is made here.")
    return {"asOf": str(payload.get("asOf") or ""),
            "organisation": str(payload.get("organisation") or ""),
            "counts": {k: int(v) for k, v in sorted(counts.items())}}


def ai_signal_sentence(signal: dict) -> str:
    """What the inventory says, as a sentence. Facts, and no instruction."""
    c = (signal or {}).get("counts") or {}
    bits = [f"{c.get('deployments', 0)} AI deployment(s) recorded"]
    for key, label in (("generative", "generative"),
                       ("acts", "acting without a person in the loop"),
                       ("consequentialDecisions", "in consequential decisions"),
                       ("unsanctioned", "on unsanctioned systems")):
        if c.get(key):
            bits.append(f"{c[key]} {label}")
    return (f"The AI register as at {signal.get('asOf') or 'an unstated date'}: "
            f"{'; '.join(bits)}.")


def applicability_for(payload: dict, overlay_cfg: dict, ai_signal: dict = None) -> dict:
    """The profile's decision, and where it disagrees with what this Profile actually does.

    The payload arrives DECIDED — §2.2 and §2.3 were applied by `business-context`, and
    re-deriving them here would be the second implementation the contract prevents. What is
    added here is the half only this skill holds: which focus areas this Profile applies.
    """
    base = (payload.get("applicability") or {}).get(CONTEXT_SKILL) or {}
    profile_ask = set(base.get("ask") or ())
    profile_skipped = {r.get("battery"): r for r in (base.get("skipped") or ())}
    enabled = bool((overlay_cfg or {}).get("enabled"))
    focus = [f for f in ((overlay_cfg or {}).get("focusAreas") or []) if isinstance(f, str)]
    ai_use_focus = sorted(f for f in focus if f in AI_USE_FOCUS)
    applied = enabled and bool(ai_use_focus)

    asked, skipped, conflicts = [], [], []
    for battery in sorted(CONTEXT_BATTERIES):
        spec = CONTEXT_BATTERIES[battery]
        if battery in profile_skipped:
            rec = dict(profile_skipped[battery])
            skipped.append(rec)
            # `thwart` alone is NOT a conflict: it applies whether or not the organisation
            # uses AI, so a Profile carrying only that focus area agrees with a declaration
            # of no AI in use rather than contradicting it.
            if battery == "ai-overlay" and applied:
                conflicts.append({
                    "battery": battery, "flag": spec["flag"],
                    "sentence": (
                        f"{spec['label']} — this Profile applies the "
                        f"{', '.join(ai_use_focus)} focus area"
                        f"{'' if len(ai_use_focus) == 1 else 's'} while the applicable "
                        f"declaration says AI is not in use, so its priorities are weighted "
                        f"for something the organisation says it does not do. Resolve it in "
                        f"the profile or in the Profile. Declaration: "
                        f"{rec.get('sentence', '')}")})
        elif battery in profile_ask:
            asked.append({"battery": battery, "label": spec["label"],
                          "flag": spec["flag"], "question": spec["question"],
                          # The answer, which no other consumer can give.
                          "answered": True, "applied": applied,
                          "focusAreas": sorted(focus)})
            # Evidence for the question, when somebody supplied it. Never the answer: the
            # entry above still records what this Profile applies, and the sentence below
            # still says to resolve it rather than resolving it.
            if ai_signal:
                asked[-1]["inventorySignal"] = {
                    "asOf": ai_signal.get("asOf") or "",
                    "counts": dict(ai_signal.get("counts") or {}),
                    "sentence": ai_signal_sentence(ai_signal)}
            if battery == "ai-overlay" and not applied:
                conflicts.append({
                    "battery": battery, "flag": spec["flag"],
                    "sentence": (
                        f"{spec['label']} — AI is declared in production use and this "
                        f"Profile applies no AI-use focus area"
                        + (f" (it carries {', '.join(sorted(focus))}, which covers a "
                           f"different question)" if focus else "")
                        + f", so the assessment is not weighted for the AI-relevant "
                          f"Subcategories IR 8596 identifies. Enable `secure` and/or "
                          f"`defend` with `overlay enable --focus`, or record why they do "
                          f"not apply."
                        + (f" {ai_signal_sentence(ai_signal)}" if ai_signal else ""))})
    return {
        "profileVersion": str(payload.get("profileVersion") or ""),
        "asked": asked,
        "skipped": sorted(skipped, key=lambda r: r.get("battery") or ""),
        "conflicts": conflicts,
        # True here, unlike the registers: this skill holds the answer as well as the
        # question, so a reader is entitled to expect one.
        "coverageAssessed": True,
    }


def _cmd_posture(args):
    """The program posture report — can you show your work?

    Reads the Profile plus whichever sibling stores were pointed at, and bands every CSF
    outcome by WHAT IS RECORDED about it. No score, no percentage, no ranking, no composite:
    those would all be this report answering a question it cannot answer.
    """
    pos, opt = parse_flags(args)
    path = _require_store(pos, "usage: posture <store.csfp> [--risk F.rr] [--policy F.pol] "
                               "[--metrics F.mtr] [--context PAYLOAD] [--json] [--out F]")
    core = load_core()
    index = index_subcategories(core)
    store = load_store(path)
    owners_map = expand_outcome_owners(core, load_outcome_owners())
    settings = store.get("profile", {}).get("settings", {})
    ev = derive_evidence(store.get("assessments") or [], store.get("intake") or [], index, core,
                         _s(opt["today"]) if "today" in opt else _today(),
                         settings.get("reporting", {}).get("scopeThresholdPct", 0),
                         settings.get("reporting", {}).get("evidenceAgeDays", 365))
    sources = {}
    for skill, flag in (("risk-register", "risk"), ("policy-register", "policy"),
                        ("metrics-register", "metrics")):
        if flag in opt:
            sources[skill] = read_posture_source(skill, _s(opt[flag]))
    context = {}
    if "context" in opt:
        with open(_s(opt["context"]), encoding="utf-8") as fh:
            context = json.load(fh)
    report = posture(core, ev, owners_map, sources, context)
    if "json" in opt:
        text = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    else:
        text = render_posture_text(report)
    out = _s(opt.get("out")) if opt.get("out") not in (None, True) else None
    if out:
        with open(out, "w", encoding="utf-8") as fh:
            fh.write(text)
        print("Wrote %s" % out, file=sys.stderr)
    else:
        sys.stdout.write(text)
    return 0


def render_posture_text(report: dict) -> str:
    """The report as text. THE CAVEAT IS A BLOCK ABOVE THE RESULTS, never a footnote.

    `policy-register`'s renderer states the placement rule this follows: "a caveat block on the
    page, not a footnote … a reader who does not see it has not been told the thing that most
    affects how they should read everything below."

    And the NOT READ block comes before ANYTHING that looks like a result, for the same reason
    `attention-surface` puts it there: a reader who sees bands first has already formed a view
    by the time they learn a store was missing.
    """
    L = ["PROGRAM POSTURE — what is on the record", "=" * 46, ""]
    # D-7. Worded to name the bands this report ACTUALLY has: "addressed" appears in no band
    # name, so a caveat about "addressed" would describe a state that does not exist here.
    L += ["WHAT THIS REPORT DOES NOT SAY", "-" * 30]
    L += ["  " + line for line in _wrap_plain(report["caveat"], 88)]
    L += [""]
    if report["notRead"]:
        L += ["NOT READ — %d store(s)" % len(report["notRead"]), "-" * 30]
        for nr in report["notRead"]:
            L += ["  %s: %s" % (nr["skill"], nr["reason"])]
        L += ["  Outcomes owned only by these read `unknown`, never `no record`. Nothing below "
              "is a finding about them.", ""]
    L += ["BANDS", "-" * 30]
    for band in report["bands"]:
        L += ["  %-18s %3d   %s" % (band, report["counts"][band],
                                    _wrap_plain(report["bandMeans"][band], 60)[0])]
        for cont in _wrap_plain(report["bandMeans"][band], 60)[1:]:
            L += ["  %-18s %3s   %s" % ("", "", cont)]
    L += [""]
    if report["declaredCritical"]:
        L += ["DECLARED CRITICAL — %d outcome(s), each naming its declaration"
              % report["declaredCritical"], "-" * 30]
        for row in report["outcomes"]:
            for d in row.get("declaredCritical") or []:
                who = d.get("declaredBy") or "nobody named"
                L += ["  %-11s %s (declared by %s)" % (row["subcategoryId"], d["basis"], who)]
        L += [""]
    L += ["BY OUTCOME", "-" * 30]
    for row in report["outcomes"]:
        owners = ", ".join(row["owners"]) or "no owner in this suite"
        L += ["  %-11s %-18s %s" % (row["subcategoryId"], row["band"], owners)]
        for rec in row["records"]:
            L += ["  %-11s   from %s: %s%s%s" % ("", rec["skill"], rec["what"],
                                                 "" if rec["attributed"] else " [unattributed]",
                                                 " [stale]" if rec["stale"] else "")]
    L += ["", "A partial program is the ordinary state. This is a map of what is written down, "
              "not a scolding.", ""]
    return "\n".join(L)


def _wrap_plain(text: str, width: int) -> list:
    words, lines, cur = str(text).split(), [], ""
    for w in words:
        if cur and len(cur) + 1 + len(w) > width:
            lines.append(cur); cur = w
        else:
            cur = (cur + " " + w).strip()
    if cur:
        lines.append(cur)
    return lines or [""]


def _cmd_analyze(args):
    pos, opt = parse_flags(args)
    path = _require_store(pos, "usage: analyze <store.csfp> [--today YYYY-MM-DD] [--top N] "
                                "[--queue-top N] [--out F] [--context PAYLOAD] "
                                "[--ai-signal SIGNAL]")
    core = load_core(); index = index_subcategories(core)
    store = load_store(path)

    problems = check_store(store, index)
    if problems:
        raise ValueError("Profile failed validation: " + "; ".join(problems))

    # Validated, not merely read. Every age figure here is a subtraction against this
    # value, and banding the attention rows widened the blast radius: `_age` measures only
    # ratings in the `confirmed` state, while `_brief` measures any row carrying a
    # confirmedAt, so a junk --today over a hand-edited store now reaches strptime on
    # paths it previously could not. cf. --source-date, validated the same way.
    today = (_iso_date(opt["today"], "--today")
             if isinstance(opt.get("today"), (str, list)) else _today())
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

    # --- Cyber AI Profile overlay -----------------------------------------
    # Advisory mode annotates and nothing else: no gap value moves, no row
    # moves, and a Profile that has not opted in emits no `overlay` key at all
    # — not `"overlay": null`, which would be a diff in every existing report.
    cfg = store["overlays"]["cyberAi"]
    overlay_block = None
    if cfg.get("enabled"):
        # --dataset is undocumented in the usage banner for the same reason it is
        # on `overlay`: it exists so the tests can run against the fixture, not as
        # a way to point a report at an unvetted priority table.
        ov_data = load_overlay_dataset(
            _s(opt["dataset"]) if isinstance(opt.get("dataset"), (str, list)) else None,
            index)
        for row in gaps:
            res = resolve_overlay(row["subcategoryId"], cfg, ov_data)
            if res:
                row["overlay"] = res
        counts = {a: {"1": 0, "2": 0, "3": 0} for a in cfg["focusAreas"]}
        for _sid, entry in (ov_data.get("subcategories") or {}).items():
            for a in cfg["focusAreas"]:
                if a in entry:
                    counts[a][str(entry[a]["priority"])] += 1
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
            # instead of composing its own and drifting.
            "provenance": (f"Cyber AI Profile overlay · dataset "
                           f"{ov_data['datasetVersion']} · "
                           f"{ov_data['sourceStatus']}, "
                           f"{ov_data['sourcePublished']}"),
            "orderingNote": ("Gap order is AI-prioritized, not gap-severity order."
                             if cfg["mode"] == "reorder" else
                             "Gap order is unchanged; the overlay annotates only."),
        }
        if cfg["mode"] == "reorder":
            # Two-pass stable sort. Python's sort is stable, so sorting by the
            # existing key first and the overlay key second preserves the old
            # ordering WITHIN each priority band. A single sort over a tuple
            # would work too, but this keeps the existing key in one place and
            # makes the band structure obvious.
            #
            # The first pass is currently redundant — compute_gaps already
            # returns rows in exactly this order — so deleting it changes no
            # output today. It is kept because it makes the band ordering a
            # property of THIS block rather than an inherited assumption about
            # compute_gaps: if that function's tie-break ever changes, reorder
            # keeps refining a severity order rather than silently refining
            # whatever it was handed.
            gaps.sort(key=lambda r: (-r["prioritizedGapScore"], r["subcategoryId"]))
            gaps.sort(key=lambda r: (r.get("overlay") or {})
                      .get("effectivePriority", 99))

    out = {
        "generated": {"today": today, "engine": "profile_analysis.py", "schemaVersion": SCHEMA_VERSION},
        "profile": {
            "id": prof.get("id"), "name": prof.get("name"), "frameworkRef": prof.get("frameworkRef"),
            "scope": prof.get("scope", {}), "settings": settings,
            "created": prof.get("created"), "updated": prof.get("updated"),
            # A fact about the STORE, so it sits with the store's other facts rather than in
            # the `framework` block — that block describes the framework and must not vary
            # with which Profile is being analysed. `None` means not recorded, never agreement.
            "assessedAgainstCore": prof.get("coreRef"),
        },
        "framework": {
            "id": core.get("id"), "name": core.get("name"), "version": core.get("version"),
            # Which EXPORT produced this Core, not just which framework version. No report
            # stated it before v0.80.0, so two analyses of the same Profile against different
            # Cores were indistinguishable after the fact (BL-109).
            "sha256": core_ref(core).get("sha256"),
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
        "attention": attention_lists(store, index, today, rep["ageThresholdDays"], top=top),
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
    # Only when present. `out["overlay"] = None` is a diff for every Profile that
    # never opted in, which is exactly what the parity assertion forbids.
    if overlay_block:
        out["overlay"] = overlay_block

    # CAC-AP-1. Additive on the same rule as the overlay block directly above: the key
    # exists only when a profile was supplied, so a run without one is byte-for-byte what
    # it always was.
    if isinstance(opt.get("context"), (str, list)):
        # D-3. The AI inventory signal is optional evidence for the scoping question, and
        # rides on the context block because that is where the question lives. With no
        # signal the block is byte-for-byte what it was.
        signal = (load_ai_signal(_s(opt["ai-signal"]))
                  if isinstance(opt.get("ai-signal"), (str, list)) else None)
        out["context"] = applicability_for(load_context(_s(opt["context"])), cfg, signal)

    # Crosswalk lenses are a report-time choice, so they appear only when asked
    # for and are never written back to the store. Same omit-when-absent rule as
    # the overlay block above.
    want_lenses = opt.get("crosswalk")
    if want_lenses:
        lenses = [want_lenses] if isinstance(want_lenses, str) else list(want_lenses)
        unknown = [x for x in lenses if x not in CROSSWALK_EXPECTED]
        if unknown:
            raise ValueError(
                f"unknown crosswalk lens {', '.join(repr(u) for u in unknown)}; "
                f"available: {', '.join(sorted(CROSSWALK_EXPECTED))}")
        cw_problems = check_crosswalks(index)
        if cw_problems:
            raise ValueError("Refusing to project onto corrupt crosswalk data: "
                             + "; ".join(cw_problems))
        crosswalks = {}
        for fid in lenses:
            cw = load_crosswalk(fid)
            block = derive_crosswalk_coverage(store["assessments"], cw, settings,
                                              index=index)
            block["completeness"] = crosswalk_completeness(cw, store["assessments"])
            crosswalks[fid] = block
        out["crosswalks"] = crosswalks

    # WHICH DATA PRODUCED THIS (BL-109 T1/T3). In the report so a rendered page or a board
    # pack can carry it, and on stderr so a person running the command sees it — stderr
    # because stdout is the JSON when --out is not given, and a note that corrupts the
    # payload is worse than no note. Never a non-zero exit: a provenance mismatch is a fact,
    # not an invalid store.
    notes = provenance_notes(store, ov_data if cfg["enabled"] else None)
    out["provenanceNotes"] = notes

    text = json.dumps(out, indent=2, ensure_ascii=False)
    dest = _s(opt.get("out")) if isinstance(opt.get("out"), (str, list)) else None
    if dest:
        with open(dest, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
        print(f"Wrote {dest}")
    else:
        sys.stdout.write(text + "\n")
    for note in notes:
        print("note: " + note, file=sys.stderr)
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

    # --- Flag parsing ---
    # A repeated flag used to overwrite: `--function ID=3 --function PR=1 --function RS=2`
    # applied RS and silently dropped ID and PR, exit 0. Both forms must now agree.
    eq(parse_flags(["--function", "ID=3", "PR=1", "RS=2"])[1],
       parse_flags(["--function", "ID=3", "--function", "PR=1", "--function", "RS=2"])[1],
       "repeated flag == space-separated flag")
    eq(parse_flags(["--function", "ID=3", "--function", "PR=1"])[1]["function"],
       ["ID=3", "PR=1"], "a repeated flag accumulates in order")
    eq(parse_flags(["--subjects", "PR.AA-01", "--subjects", "ID.AM-01", "ID.AM-02"])[1],
       {"subjects": ["PR.AA-01", "ID.AM-01", "ID.AM-02"]},
       "mixed repeated and space-separated values all survive")
    eq(parse_flags(["--x", "a"])[1], {"x": "a"}, "a single value is still a scalar")
    eq(parse_flags(["--x"])[1], {"x": True}, "a valueless flag is still True")
    eq(parse_flags(["--x", "--x"])[1], {"x": True}, "a repeated valueless flag stays True")
    eq(_s(parse_flags(["--rationale", "first", "--rationale", "second"])[1]["rationale"]),
       "first second",
       "a repeated scalar joins the same way an unquoted multi-token value always has")
    eq(parse_flags(["p.csfp", "--a", "1", "--b"])[0], ["p.csfp"],
       "positionals are unaffected")

    # --- The scope guard binds stdout too ---
    # Suppressing the figure inside the HTML and printing it to the terminal defeats the
    # guard's stated reason: the number must not reappear one document over. An agent
    # reads stdout and repeats it, which is the outcome the guard exists to prevent.
    _sup = {"suppressed": True, "assessed": 31, "inScope": 106, "thresholdPct": 60}
    _open = {"suppressed": False, "assessed": 80, "inScope": 106, "thresholdPct": 60}
    _cov = {"percent": 22.2, "n": 47, "d": 212}
    ok("22" not in coverage_stdout(_sup, _cov),
       "a suppressed profile never prints the coverage percentage")
    ok("31 of 106" in coverage_stdout(_sup, _cov),
       "it prints the assessed fraction instead, so the reader knows why")
    eq(coverage_stdout(_open, _cov), "22.2% (47/212)",
       "at or above the threshold the figure is printed unchanged")
    eq(coverage_stdout(_open, None), "not yet targeted",
       "nothing targeted is still reported as such, not as 0%")
    eq(coverage_stdout(_sup, None), coverage_stdout(_sup, _cov),
       "suppression does not depend on having a figure to suppress")

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

    # --- Completeness, measured against the CORE (BL-109 T4) ---
    #
    # This fixture holds 10 assessments. Until v0.80.0 it reported `total: 10` — the store
    # measuring itself, and presenting a complete-looking picture of 10% of the framework.
    comp = compute_completeness(store["assessments"], index, core)
    eq(comp["overall"], {"total": 106, "inScope": 105, "notApplicable": 1, "assessed": 8,
                         "targeted": 8, "notInStore": 96},
       "overall completeness counts against the Core, not the store")
    # The load-bearing property, asserted rather than left implicit in the numbers above: a
    # Subcategory the Core has and the store does not is UNASSESSED, never out of scope.
    # Reading absence as `notApplicable` would let any store shrink its own denominator by
    # deleting rows.
    eq(comp["overall"]["total"], len(index),
       "...and the denominator IS the Core's Subcategory count")
    eq(comp["overall"]["notApplicable"], 1,
       "a missing row does not become an n/a — only a declaration does that")
    # Every Category in the Core appears, even one the store never touched. Before this,
    # byCategory iterated the store, so an untouched Category vanished from the dashboard.
    _core_cats = {meta["categoryId"] for meta in index.values()}
    eq(set(comp["byCategory"]), _core_cats,
       "every Core Category appears, including ones the store has no row in")
    # And the direction that reaches a board page: ADD a Subcategory to the Core and the
    # denominator follows it. That is the silent failure this item was raised for — the
    # opposite direction has always been loud, because check_store names an unknown
    # Subcategory by ID and refuses.
    _wider = dict(index)
    _wider["GV.XX-99"] = dict(next(iter(index.values())))
    _wide = compute_completeness(store["assessments"], _wider, core)
    eq((_wide["overall"]["total"], _wide["overall"]["notInStore"]), (107, 97),
       "a Subcategory added to the Core raises the denominator rather than vanishing")
    eq(_wide["overall"]["assessed"], comp["overall"]["assessed"],
       "...and does not change what was assessed, only what remains")

    # --- Provenance notes: the comparison nobody was making (BL-109 T1/T3) ---
    #
    # These are NOTES, never refusals. A dataset or Core mismatch is a fact about provenance,
    # and refusing would strand a CISO mid-assessment the day either moves — the BL-169 D-2
    # failure this repo declines everywhere else.
    _unstamped = copy.deepcopy(store)
    _unstamped["profile"]["coreRef"] = None
    _n = provenance_notes(_unstamped)
    ok(len(_n) == 1 and "does not record which Core" in _n[0],
       "a store with no Core stamp says so — absent is not agreement")
    _stamped = copy.deepcopy(store)
    _stamped["profile"]["coreRef"] = dict(core_ref(core))
    eq(provenance_notes(_stamped), [],
       "...and a store stamped with the shipped Core is SILENT — no noise on the common path")
    _moved = copy.deepcopy(store)
    _moved["profile"]["coreRef"] = {"version": "2.0", "sha256": "0" * 64}
    _n = provenance_notes(_moved)
    ok(len(_n) == 1 and "000000000000" in _n[0] and core_ref()["sha256"][:12] in _n[0],
       "a store written against a different Core names BOTH, so a reader can tell which moved")
    # The dataset half, which `overlay list` printed on adjacent lines and never compared.
    _ds = copy.deepcopy(_stamped)
    _ds["overlays"]["cyberAi"].update({"enabled": True, "datasetVersion": "fixture-1"})
    _n = provenance_notes(_ds, {"datasetVersion": "8596-iprd-2025-12-16"})
    ok(len(_n) == 1 and "fixture-1" in _n[0] and "8596-iprd-2025-12-16" in _n[0],
       "an overlay enabled on one dataset and analysed against another names both versions")
    eq(provenance_notes(_ds, {"datasetVersion": "fixture-1"}), [],
       "...and matching dataset versions are silent too")
    # A disabled overlay carrying a stale stamp is not a mismatch: nothing used it.
    _off = copy.deepcopy(_ds)
    _off["overlays"]["cyberAi"]["enabled"] = False
    eq(provenance_notes(_off, {"datasetVersion": "8596-iprd-2025-12-16"}), [],
       "a DISABLED overlay's stale stamp says nothing — no dataset was in force")

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
    att = attention_lists(store, index, "2026-07-26", 180, top=10)
    eq([g["subcategoryId"] for g in att["largestGaps"]],
       ["PR.DS-01", "GV.RM-01", "PR.AA-01", "ID.RA-01", "GV.SC-01", "GV.OC-01"], "largestGaps order")
    eq([r["subcategoryId"] for r in att["neverReviewed"]], ["GV.SC-01", "ID.RA-01"], "neverReviewed")
    eq([r["subcategoryId"] for r in att["stalest"]][:3], ["PR.DS-01", "PR.AA-01", "GV.RM-01"],
       "stalest ordering (oldest first)")
    ok(all(r["subcategoryId"] not in ("GV.SC-01", "ID.RA-01") for r in att["stalest"]),
       "never-reviewed excluded from stalest")
    # A stalest row is SORTED on lastReviewed but BANDED on confirmedAt. Those are
    # different fields on purpose (confirmedAt is never backfilled from lastReviewed —
    # that would fabricate attribution), so the row carries both and bands only the one
    # the age model actually measures.
    ok(all("confirmedAt" in r and "confirmationBand" in r for r in att["stalest"]),
       "every stalest row carries both the confirmation date and its band")
    # This v1 fixture carries no confirmedAt anywhere at all, by design, so every one of
    # its stalest rows IS the reviewed-but-never-confirmed case. Asserted as an exact
    # list rather than an all(...) over `if r["confirmedAt"]`, which would read the same
    # and pass just as happily over no rows whatsoever.
    eq(len(att["stalest"]), 7, "the v1 fixture has seven reviewed in-scope Subcategories")
    eq([r["confirmationBand"] for r in att["stalest"]], [None] * 7,
       "a row reviewed but never confirmed shows NO band rather than a guessed one")
    eq([r["confirmationAgeDays"] for r in att["stalest"]], [None] * 7,
       "and no confirmation age either — there is no date to measure from")

    # The banded branch needs a Profile that actually holds confirmations, and the v1
    # fixture above holds none. The shipped v2 fixture does. Its four dated ratings sit
    # at 420 and 198 days, which straddles a boundary at BOTH thresholds, so every row
    # moves band when the threshold is rescaled — a rescale that silently fell back to
    # 180 could not produce the second list. Ordering is pinned here too: banding must
    # not disturb the lastReviewed sort asserted above.
    _v2 = load_store(os.path.join(_SKILL_ROOT, "examples", "example-profile-v2.csfp"))
    _s180 = attention_lists(_v2, index, "2026-07-27", 180, top=10)["stalest"]
    _s365 = attention_lists(_v2, index, "2026-07-27", 365, top=10)["stalest"]
    eq([(r["subcategoryId"], r["confirmationBand"]) for r in _s180],
       [("ID.AM-01", "wellBeyond"), ("ID.AM-02", "wellBeyond"),
        ("PR.DS-11", "beyond"), ("RC.RP-01", "beyond")],
       "a row with a confirmation date is banded, at the Profile's default threshold")
    eq([(r["subcategoryId"], r["confirmationAgeDays"]) for r in _s180],
       [("ID.AM-01", 420), ("ID.AM-02", 420), ("PR.DS-11", 198), ("RC.RP-01", 198)],
       "and carries the confirmation age its band was computed from")
    eq([(r["subcategoryId"], r["confirmationBand"]) for r in _s365],
       [("ID.AM-01", "beyond"), ("ID.AM-02", "beyond"),
        ("PR.DS-11", "approaching"), ("RC.RP-01", "approaching")],
       "stalest bands honour a rescaled age threshold")
    # Two checks that stood here have been removed rather than kept for reassurance. One
    # re-derived what the two `eq`s above already fix — the band change between T=180 and
    # T=365 is visible in those literals, and its truth value was settled at edit time.
    # The other, `all(band in AGE_BANDS ...)`, is the exact tautology the note at the
    # AGE_BANDS identity check documents as rejected: the counter is built from
    # AGE_BANDS, so changing the vocabulary raises KeyError during fixture setup long
    # before any assertion here could report it.
    eq([i["id"] for i in att["unownedActions"]], ["A-002"], "unowned actions")
    eq([i["id"] for i in att["pastDueActions"]], ["A-003"], "past-due actions (A-004 closed, excluded)")
    eq([r["subcategoryId"] for r in att["acceptedGaps"]], ["PR.DS-01"], "accepted gaps")

    # today is honoured, not the wall clock
    eq([i["id"] for i in attention_lists(store, index, "2026-01-01", 180)["pastDueActions"]], [],
       "no past-due when today precedes every target date")
    eq([i["id"] for i in attention_lists(store, index, "2027-01-01", 180)["pastDueActions"]],
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
    # Both ids here MUST be absent from the rank table, or this stops testing the tail
    # rule and starts testing the table. GV.OC-03 used to sit here and was later ranked,
    # at which point the assertion still passed while covering nothing.
    ok("GV.OC-05" not in rank_data["rank"] and "ID.RA-02" not in rank_data["rank"],
       "the tail-rule assertion uses genuinely unranked ids")
    ok(order["GV.OC-05"] < order["ID.RA-02"],
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

    # The shipped file is already dense, so compaction must be an identity on
    # it — verified directly, since that is exactly the case the bug hid in.
    shipped = load_cold_start_rank()
    ok(all(order[sid] == v for sid, v in shipped["rank"].items()),
       "compaction is an identity on the shipped table — every ranked id keeps its authored position")

    # --- elicitation bank -------------------------------------------------
    # The bank and the rank must agree about what a cold-start Profile asks
    # first. They are two files; nothing but this assertion keeps them in step.
    _rank_map = load_cold_start_rank()["rank"]
    with open(DEFAULT_ELICITATION, encoding="utf-8") as _fh:
        _elic = json.load(_fh)
    _qs = _elic["questions"]

    eq([q["id"] for q in _qs], [f"q{i + 1}" for i in range(len(_qs))],
       "elicitation question ids are dense q1..qN in order")

    _seen = []
    for _q in _qs:
        ok(_q["ask"].strip() and _q["listenFor"].strip(),
           f"elicitation {_q['id']} carries both an ask and a listenFor")
        ok(len(_q["resolves"]) >= 2,
           f"elicitation {_q['id']} resolves more than one Subcategory (a bank of "
           "one-to-one questions is just the rank with extra words)")
        _seen.extend(_q["resolves"])

    eq(len(_seen), len(set(_seen)),
       "no Subcategory appears in two elicitation questions")
    ok(all(s in index for s in _seen),
       "every elicitation subject is a real Core Subcategory")
    eq(set(_seen), set(_rank_map),
       "the elicitation bank covers exactly the cold-start rank, no more and "
       "no less")

    _mins = [min(_rank_map[s] for s in _q["resolves"]) for _q in _qs]
    eq(_mins, sorted(_mins),
       "elicitation questions are ordered by their highest-ranked subject — "
       "a bank that asks rank-27 material before rank-1 contradicts the rank "
       "it is built from")

    # --- cyber-ai overlay dataset -----------------------------------------
    # Validated before it is populated, so an extraction defect surfaces here
    # rather than as a wrong priority in a board pack.
    _ds = load_overlay_dataset(os.path.join(_SKILL_ROOT, "examples",
                                            "fixture-cyber-ai.json"), index)
    eq(_ds["datasetVersion"], "fixture-1", "the fixture dataset loads")
    eq(sorted(_ds["focusAreas"]), ["defend", "secure", "thwart"],
       "three focus areas, always")

    def _bad(mutate, label):
        broken = copy.deepcopy(_ds)
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
    # True == 1 in Python, so a JSON `true` would satisfy a naive `in (1, 2, 3)`
    # check and then behave as High priority everywhere downstream.
    _bad(lambda d: d["subcategories"]["ID.AM-01"]["secure"].__setitem__("priority", True),
         "a boolean priority is refused, not silently read as 1")

    # --- overlay store block ----------------------------------------------
    # Defaults are inert on purpose: a normalization bug should produce a
    # Profile that reports nothing, never one that silently resequences a
    # board's top five.
    with tempfile.TemporaryDirectory() as _tmp:
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
        ok(_ovs["overlays"]["cyberAi"]["datasetVersion"] is None,
           "and no dataset stamped until something enables it")

        # A store predating the overlay must still load.
        with open(FIXTURE, encoding="utf-8") as _fh:
            _v1 = json.load(_fh)
        _v1.pop("overlays", None)
        _v1_path = os.path.join(_tmp, "no-overlays.csfp")
        with open(_v1_path, "w", encoding="utf-8") as _fh:
            json.dump(_v1, _fh)
        ok(load_store(_v1_path)["overlays"]["cyberAi"]["enabled"] is False,
           "a store predating the overlay normalizes to disabled, never to enabled")

        eq(check_store(load_store(_ov_store), index), [],
           "an overlays block is not a structural problem")

        # An explicitly-configured block must survive a load/save round trip
        # untouched — setdefault must not clobber a real choice.
        _rt = load_store(_ov_store)
        _rt["overlays"]["cyberAi"] = {"enabled": True, "focusAreas": ["secure"],
                                      "mode": "reorder", "datasetVersion": "fixture-1"}
        save_store(_rt, _ov_store, "2026-01-02T00:00:00Z")
        _back = load_store(_ov_store)["overlays"]["cyberAi"]
        eq(_back, {"enabled": True, "focusAreas": ["secure"], "mode": "reorder",
                   "datasetVersion": "fixture-1"},
           "an explicitly set overlay block round-trips unchanged")

        # --- overlay commands ----------------------------------------------
        _fx_path = os.path.join(_SKILL_ROOT, "examples", "fixture-cyber-ai.json")
        _ov2 = os.path.join(_tmp, "cmds.csfp")
        _cmd_init(["--name", "Overlay Cmds", "--out", _ov2,
                   "--ts", "2026-01-01T00:00:00Z"])

        _cmd_overlay(["enable", _ov2, "--focus", "secure", "thwart",
                      "--dataset", _fx_path, "--ts", "2026-01-02T00:00:00Z"])
        _en = load_store(_ov2)["overlays"]["cyberAi"]
        eq(_en["enabled"], True, "enable turns the overlay on")
        eq(_en["focusAreas"], ["secure", "thwart"], "and records the selected areas")
        eq(_en["mode"], "reorder",
           "defaulting to reorder — the honest use of a sequencing signal")
        eq(_en["datasetVersion"], "fixture-1",
           "and stamps the dataset version in force")
        eq(load_store(_ov2)["history"][-1]["type"], "overlay-enabled",
           "enabling writes a history event; it changes what every report says")

        # Focus areas are stored in canonical order, not the order they were typed.
        _cmd_overlay(["enable", _ov2, "--focus", "thwart", "secure",
                      "--dataset", _fx_path, "--ts", "2026-01-02T01:00:00Z"])
        eq(load_store(_ov2)["overlays"]["cyberAi"]["focusAreas"], ["secure", "thwart"],
           "focus areas are canonicalised, so two equivalent commands agree")

        try:
            _cmd_overlay(["enable", _ov2, "--focus", "secure", "--mode", "floor",
                          "--dataset", _fx_path, "--ts", "2026-01-03T00:00:00Z"])
            ok(False, "floor mode is refused")
        except ValueError as _e:
            ok("floor" in str(_e) and "scale" in str(_e),
               "floor is refused NAMING THE SCALE — anyone who read the original "
               "design will type it, and 'unknown mode' sends them hunting a typo")

        try:
            _cmd_overlay(["enable", _ov2, "--focus", "secure,thwart",
                          "--dataset", _fx_path, "--ts", "2026-01-03T00:00:00Z"])
            ok(False, "a comma-joined focus list is refused")
        except ValueError as _e:
            ok("secure,thwart" in str(_e) and "space" in str(_e).lower(),
               "a comma-joined focus list is refused by name and says to use spaces")

        try:
            _cmd_overlay(["enable", _ov2, "--dataset", _fx_path,
                          "--ts", "2026-01-03T00:00:00Z"])
            ok(False, "enable with no --focus is refused")
        except ValueError as _e:
            ok("thwart" in str(_e),
               "and the refusal explains the three areas, including that thwart "
               "applies whether or not you use AI")

        try:
            _cmd_overlay(["enable", _ov2, "--focus", "sekure",
                          "--dataset", _fx_path, "--ts", "2026-01-03T00:00:00Z"])
            ok(False, "an unknown focus area is refused")
        except ValueError as _e:
            ok("sekure" in str(_e), "and names the value it did not recognise")

        # A refused enable must not have half-written the store.
        eq(load_store(_ov2)["overlays"]["cyberAi"]["focusAreas"], ["secure", "thwart"],
           "a refused enable leaves the previous state intact")

        _cmd_overlay(["disable", _ov2, "--dataset", _fx_path,
                      "--ts", "2026-01-04T00:00:00Z"])
        _dis = load_store(_ov2)["overlays"]["cyberAi"]
        eq(_dis["enabled"], False, "disable turns it off")
        eq(_dis["focusAreas"], ["secure", "thwart"],
           "and preserves the selection, so re-enabling is one command")
        eq(load_store(_ov2)["history"][-1]["type"], "overlay-disabled",
           "and writes its own history event")

    # --- overlay resolution ------------------------------------------------
    # Effective priority is the MINIMUM across selected areas because NIST's
    # 1/2/3 is High/Moderate/Foundational — 1 is the most urgent. That gives
    # the property that matters: deselecting an area can only relax.
    _fx = load_overlay_dataset(os.path.join(_SKILL_ROOT, "examples",
                                            "fixture-cyber-ai.json"), index)
    _on = {"enabled": True, "focusAreas": ["secure", "thwart"], "mode": "reorder"}

    eq(resolve_overlay("ID.AM-01", _on, _fx)["effectivePriority"], 1,
       "effective priority is the minimum across selected areas")
    eq(resolve_overlay("DE.CM-01", _on, _fx)["effectivePriority"], 1,
       "and finds the urgent one whichever area carries it")
    eq(resolve_overlay("GV.OC-01", _on, _fx)["effectivePriority"], 3,
       "a Subcategory foundational everywhere resolves to 3")

    _one = {"enabled": True, "focusAreas": ["thwart"], "mode": "reorder"}
    eq(resolve_overlay("ID.AM-01", _one, _fx)["effectivePriority"], 3,
       "deselecting an area relaxes — ID.AM-01 is 1 in secure, 3 in thwart")

    # The invariant, over every Subcategory in the dataset rather than one.
    for _sid in _fx["subcategories"]:
        _all3 = resolve_overlay(_sid, {"enabled": True, "mode": "reorder",
                                       "focusAreas": list(OVERLAY_FOCUS_AREAS)}, _fx)
        for _area in OVERLAY_FOCUS_AREAS:
            _fewer = resolve_overlay(_sid, {"enabled": True, "mode": "reorder",
                                            "focusAreas": [a for a in OVERLAY_FOCUS_AREAS
                                                           if a != _area]}, _fx)
            ok(_fewer["effectivePriority"] >= _all3["effectivePriority"],
               f"deselecting {_area} never tightens {_sid}")

    ok(resolve_overlay("ID.AM-01", {"enabled": False, "focusAreas": ["secure"],
                                    "mode": "reorder"}, _fx) is None,
       "disabled resolves to None, never to a default priority")
    ok(resolve_overlay("ID.AM-01", {"enabled": True, "focusAreas": [],
                                    "mode": "reorder"}, _fx) is None,
       "no areas selected resolves to None")
    ok(resolve_overlay("RC.RP-01", _on, _fx) is None,
       "a Subcategory absent from the dataset resolves to None")
    ok(resolve_overlay("ID.AM-01", None, _fx) is None,
       "a missing config resolves to None rather than raising")

    eq(resolve_overlay("GV.OC-01", _on, _fx)["sentinelAreas"], ["secure", "thwart"],
       "the 'standard practices apply' sentinel is reported per selected area")
    eq(resolve_overlay("ID.AM-01", _on, _fx)["sentinelAreas"], ["thwart"],
       "and only for the areas where the source said it")
    eq(resolve_overlay("ID.AM-01", _on, _fx)["perArea"], {"secure": 1, "thwart": 3},
       "per-area priorities carry through for display, selected areas only")

    _res = resolve_overlay("ID.AM-01", _on, _fx)
    ok("target" not in _res and "effectiveTarget" not in _res
       and "targetRaisedBy" not in _res,
       "resolution never touches targets — floor mode is not in this increment")

    with tempfile.TemporaryDirectory() as _tmp:
        # --- advisory mode changes nothing computed ---------------------------
        # The acceptance bar. If enabling the overlay in advisory mode can move a
        # number, the overlay is a defect regardless of how useful it is.
        def _copy_fixture(src, dst):
            with open(src, encoding="utf-8") as _s, open(dst, "w", encoding="utf-8") as _d:
                _d.write(_s.read())

        _fx_path = os.path.join(_SKILL_ROOT, "examples", "fixture-cyber-ai.json")
        _par = os.path.join(_tmp, "parity.csfp")
        _copy_fixture(FIXTURE, _par)

        _base_out = os.path.join(_tmp, "base.json")
        _cmd_analyze([_par, "--today", "2026-07-28", "--dataset", _fx_path,
                      "--out", _base_out])
        with open(_base_out, encoding="utf-8") as _fh:
            _base = json.load(_fh)
        ok("overlay" not in _base,
           "a Profile that has not opted in carries no overlay key at all — not "
           "null, which would be a diff")

        _cmd_overlay(["enable", _par, "--focus", "secure", "defend", "thwart",
                      "--mode", "advisory", "--dataset", _fx_path,
                      "--ts", "2026-02-01T00:00:00Z"])
        _adv_out = os.path.join(_tmp, "adv.json")
        _cmd_analyze([_par, "--today", "2026-07-28", "--dataset", _fx_path,
                      "--out", _adv_out])
        with open(_adv_out, encoding="utf-8") as _fh:
            _adv = json.load(_fh)

        for _k in ("coverage", "completeness", "tiers", "attention", "queue",
                   "evidence", "playbook", "tracked", "actionItems", "framework"):
            eq(_adv[_k], _base[_k],
               f"advisory mode leaves analyze.{_k} identical")

        _vals = lambda rows: [(r["subcategoryId"], r["current"], r["target"], r["gap"],
                               r["prioritizedGapScore"]) for r in rows]
        eq(_vals(_adv["gaps"]), _vals(_base["gaps"]),
           "advisory mode leaves every gap value AND the row order untouched")

        ok("overlay" in _adv, "advisory mode adds an overlay block")
        eq(_adv["overlay"]["mode"], "advisory", "which states the mode")
        eq(_adv["overlay"]["datasetVersion"], "fixture-1", "and the dataset version")
        ok(_adv["overlay"]["sourceStatus"], "and the source status, for the artifact")
        eq(_adv["overlay"]["focusAreas"], ["secure", "defend", "thwart"],
           "and which areas are selected")
        ok("provenance" in _adv["overlay"] and "orderingNote" in _adv["overlay"],
           "and the two sentences renderers project rather than compose themselves")

        _annotated = [r for r in _adv["gaps"] if r.get("overlay")]
        ok(_annotated, "gap rows for Subcategories in the dataset are annotated")
        ok(all("effectivePriority" in r["overlay"] for r in _annotated),
           "each annotation carries an effective priority")
        ok(any(not r.get("overlay") for r in _adv["gaps"])
           or len(_adv["gaps"]) == len(_annotated),
           "rows the dataset says nothing about are simply not annotated")

        # Disabling must restore byte-identical output, not merely similar output.
        _cmd_overlay(["disable", _par, "--dataset", _fx_path,
                      "--ts", "2026-02-02T00:00:00Z"])
        _off_out = os.path.join(_tmp, "off.json")
        _cmd_analyze([_par, "--today", "2026-07-28", "--dataset", _fx_path,
                      "--out", _off_out])

        # Compared as TEXT, not as parsed objects, so key ORDER and a stray
        # `"overlay": null` both show up. Exactly two fields are set aside, and
        # they are the audit trail rather than the report: toggling the overlay
        # deliberately writes overlay-enabled/overlay-disabled history and
        # re-stamps profile.updated (already asserted above, and the point of
        # having those events at all). Everything else — every gap row, every
        # rollup, the absence of the overlay key — is compared byte for byte.
        def _sans_audit(_path):
            with open(_path, encoding="utf-8") as _fh:
                _d = json.load(_fh)
            _d["history"] = "<audit trail, asserted separately below>"
            _d["profile"]["updated"] = "<stamped by save_store on every write>"
            # Set aside for the same reason `updated` is, and no more. `save_store` stamps
            # which Core the store was written against on EVERY write (BL-109 T2), so the
            # baseline report — taken before this store had ever been written here — carries
            # `null` while the post-round-trip one carries the stamp. That difference belongs
            # to the write, not to the overlay, and this assertion is a claim about the
            # overlay. `assessedAgainstCore` has its own checks below.
            _d["profile"]["assessedAgainstCore"] = "<stamped by save_store on every write>"
            # Same reason, one step downstream: the baseline store has no Core stamp, so it
            # earns the "does not record which Core" note and the written one does not.
            _d["provenanceNotes"] = "<derived from the stamp set aside above>"
            return json.dumps(_d, indent=2, ensure_ascii=False)

        eq(_sans_audit(_off_out), _sans_audit(_base_out),
           "disabling restores byte-identical analyze output — the overlay is "
           "fully reversible, leaving no residue in a report")

        with open(_off_out, encoding="utf-8") as _fh:
            _off = json.load(_fh)
        ok("overlay" not in _off and all(not _r.get("overlay") for _r in _off["gaps"]),
           "no overlay key survives disabling, at the top level or on any gap row")
        eq([_h["type"] for _h in _off["history"][-2:]],
           ["overlay-enabled", "overlay-disabled"],
           "and the only trace left anywhere is the audit trail the toggle is "
           "supposed to write")

    with tempfile.TemporaryDirectory() as _tmp:
        # --- reorder changes order and NOTHING else ---------------------------
        # This is the default mode on enable. NIST priority is sequencing, not
        # maturity, so the honest use of it moves the queue and leaves every
        # number exactly where it was.
        def _copy_fixture(src, dst):
            with open(src, encoding="utf-8") as _s, open(dst, "w", encoding="utf-8") as _d:
                _d.write(_s.read())

        _fx_path = os.path.join(_SKILL_ROOT, "examples", "fixture-cyber-ai.json")
        _ro = os.path.join(_tmp, "reorder.csfp")
        _copy_fixture(FIXTURE, _ro)

        _ro_base_out = os.path.join(_tmp, "ro-base.json")
        _cmd_analyze([_ro, "--today", "2026-07-28", "--out", _ro_base_out])
        with open(_ro_base_out, encoding="utf-8") as _fh:
            _rbase = json.load(_fh)

        # `defend` and not `secure`: under `secure` the fixture's only priority-1
        # gap row is also its LARGEST gap, so "a small gap at priority 1 beats a
        # large gap at priority 3" would be vacuous. Under `defend` the priority-1
        # row (PR.AA-01, gap 2) is smaller than a priority-3 row (PR.DS-01, gap 3),
        # which is the case the mode exists for.
        _cmd_overlay(["enable", _ro, "--focus", "defend", "--mode", "reorder",
                      "--dataset", _fx_path, "--ts", "2026-02-01T00:00:00Z"])
        _ro_out = os.path.join(_tmp, "ro.json")
        _cmd_analyze([_ro, "--today", "2026-07-28", "--out", _ro_out,
                      "--dataset", _fx_path])
        with open(_ro_out, encoding="utf-8") as _fh:
            _ran = json.load(_fh)

        # Values: identical, keyed by id so ordering cannot mask a change.
        _by_id = lambda rows: {r["subcategoryId"]: (r["current"], r["target"], r["gap"],
                                                    r["prioritizedGapScore"],
                                                    r["priority"], r["status"])
                               for r in rows}
        eq(_by_id(_ran["gaps"]), _by_id(_rbase["gaps"]),
           "reorder changes no gap VALUE")
        eq(sorted(r["subcategoryId"] for r in _ran["gaps"]),
           sorted(r["subcategoryId"] for r in _rbase["gaps"]),
           "and drops or adds no row")
        for _k in ("coverage", "completeness", "tiers", "queue", "evidence",
                   "tracked", "actionItems"):
            eq(_ran[_k], _rbase[_k],
               f"reorder leaves analyze.{_k} untouched — it is not a scoring change")

        _order_base = [r["subcategoryId"] for r in _rbase["gaps"]]
        _order_ro = [r["subcategoryId"] for r in _ran["gaps"]]
        ok(_order_ro != _order_base,
           "and the order actually differs, or the mode does nothing at all")

        # The point of the mode: urgency beats size.
        _pos = {sid: i for i, sid in enumerate(_order_ro)}
        _p1 = [r["subcategoryId"] for r in _ran["gaps"]
               if (r.get("overlay") or {}).get("effectivePriority") == 1]
        _p3 = [r["subcategoryId"] for r in _ran["gaps"]
               if (r.get("overlay") or {}).get("effectivePriority") == 3]
        _none = [r["subcategoryId"] for r in _ran["gaps"] if not r.get("overlay")]
        ok(_p1 and _p3 and _none,
           "the fixture exercises all three cases: priority 1, priority 3, and "
           "Subcategories the dataset says nothing about")
        ok(max(_pos[s] for s in _p1) < min(_pos[s] for s in _p3),
           "every priority-1 row outranks every priority-3 row, whatever the gap size")
        ok(min(_pos[s] for s in _none) > max(_pos[s] for s in _p3),
           "and Subcategories the dataset says nothing about sort after those it does")

        # Specifically: a small gap at priority 1 beats a large gap at priority 3.
        _gapof = {r["subcategoryId"]: r["gap"] for r in _ran["gaps"]}
        _beats = [(a, b) for a in _p1 for b in _p3 if _gapof[a] < _gapof[b]]
        ok(_beats and all(_pos[a] < _pos[b] for a, b in _beats),
           "a SMALLER gap at priority 1 still outranks a larger gap at priority 3 — "
           "which is the whole point of a sequencing signal")

        # Stable within a band: ties keep the old relative order.
        _band3 = [s for s in _order_ro if s in _p3]
        eq(_band3, [s for s in _order_base if s in _p3],
           "within a priority band the previous ordering is preserved — the sort is "
           "stable, so reorder refines the old order rather than replacing it")

        # Determinism.
        _ro_out2 = os.path.join(_tmp, "ro2.json")
        _cmd_analyze([_ro, "--today", "2026-07-28", "--out", _ro_out2,
                      "--dataset", _fx_path])
        with open(_ro_out2, encoding="utf-8") as _fh:
            eq([r["subcategoryId"] for r in json.load(_fh)["gaps"]], _order_ro,
               "ordering is deterministic across runs")

        ok(_ran["overlay"]["orderingNote"].startswith("Gap order is AI-prioritized"),
           "and the output states the order is AI-prioritized, so a reader is not "
           "left assuming it reflects gap severity")

        # Two downstream consumers, and they behave differently ON PURPOSE.
        #
        # `playbook` is built from the reordered `gaps` list, so it inherits the
        # new sequence. That is intended, not incidental: the playbook is the
        # Next-90-Days worksheet, and if the overlay has resequenced the work
        # queue then the worksheet is exactly the thing that should follow it.
        # Its VALUES still move nowhere — same rows, same numbers, new order.
        _pb_ro = [r["subcategoryId"] for r in _ran["playbook"]]
        _pb_base = [r["subcategoryId"] for r in _rbase["playbook"]]
        eq(_pb_ro, _order_ro[:len(_pb_ro)],
           "the playbook is cut from the reordered gap list, so the Next-90-Days "
           "worksheet follows the resequenced queue — intended, and the reason "
           "reorder is worth having")
        ok(_pb_ro != _pb_base, "which means it visibly differs from the base order")
        eq(sorted(_pb_base), sorted(_pb_ro),
           "and it is the same set of rows, resequenced — reorder adds and drops "
           "nothing here either")
        eq({r["subcategoryId"]: (r["current"], r["target"], r["prioritizedGapScore"])
            for r in _ran["playbook"]},
           {r["subcategoryId"]: (r["current"], r["target"], r["prioritizedGapScore"])
            for r in _rbase["playbook"]},
           "with every playbook value identical — the sequence moved, the numbers "
           "did not")

        # `attention` does NOT move: attention_lists recomputes gaps from the
        # store rather than reading the reordered list, so largestGaps stays in
        # severity order. That is the correct reading of its name — it answers
        # "what is biggest", not "what is next".
        eq(_ran["attention"], _rbase["attention"],
           "attention is untouched: it recomputes its own gap list, so largestGaps "
           "still means largest and not AI-first")
        eq([r["subcategoryId"] for r in _ran["attention"]["largestGaps"]], _order_base,
           "specifically largestGaps keeps severity order, so the two lists are "
           "readable as the different questions they answer")

    # --- elicit ------------------------------------------------------------
    # Settled = rated, scoped out, or already carrying intake. The third
    # clause is the one that makes this a cold-start tool rather than a
    # second queue.
    with tempfile.TemporaryDirectory() as _tmp:
        _el_store = os.path.join(_tmp, "elicit.csfp")
        _cmd_init(["--name", "Elicit Fixture", "--out", _el_store,
                   "--ts", "2026-01-01T00:00:00Z"])

        _e0 = _elicit_rows(load_store(_el_store), top=99)
        eq(len(_e0), 9, "a Profile with nothing in it is unsettled on all nine questions")
        eq(_e0[0]["id"], "q1", "elicit leads with q1 on an empty Profile")
        eq(len(_e0[0]["unsettled"]), 4, "q1 starts with all four subjects unsettled")

        _cmd_intake(["add", _el_store, "--label", "fixture source",
                     "--subjects", "ID.AM-01", "--source-date", "2026-01-02",
                     "--recorded-by", "Fixture", "--ts", "2026-01-02T00:00:00Z"])
        _cmd_set([_el_store, "ID.AM-01", "--current", "2", "--source", "in-0001",
                  "--confirmed-by", "Fixture", "--rationale", "fixture",
                  "--ts", "2026-01-03T00:00:00Z"])
        _e1 = _elicit_rows(load_store(_el_store), top=99)
        eq(_e1[0]["id"], "q1", "q1 survives while any subject is unsettled")
        ok("ID.AM-01" not in _e1[0]["unsettled"], "a rated subject leaves the question")

        _cmd_intake(["add", _el_store, "--label", "second source",
                     "--subjects", "ID.AM-02", "ID.AM-03", "ID.AM-05",
                     "--source-date", "2026-01-04", "--recorded-by", "Fixture",
                     "--ts", "2026-01-04T00:00:00Z"])
        _e2 = _elicit_rows(load_store(_el_store), top=99)
        eq(len(_e2), 8, "a question whose every subject carries intake drops out entirely")
        eq(_e2[0]["id"], "q2", "the next unsettled question leads")

        _cmd_set([_el_store, "PR.AA-06", "--applicability", "not-applicable",
                  "--rationale", "fixture: no premises", "--ts", "2026-01-05T00:00:00Z"])
        _e3 = _elicit_rows(load_store(_el_store), top=99)
        _q3row = [r for r in _e3 if r["id"] == "q3"][0]
        ok("PR.AA-06" not in _q3row["unsettled"],
           "a not-applicable subject is settled, not pending forever")

        eq(len(_elicit_rows(load_store(_el_store), top=3)), 3, "--top bounds the batch")
        ok(all("proposed" not in r and "current" not in r for r in _e3),
           "an elicit row never carries a proposed rating — the same rule the "
           "queue lives under")

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
    eq(ev["revisit"][0]["reason"], "newer-material",
       "a dated confirmation with newer intake against it is reason newer-material")
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

    # --- revisit reason: newer-material vs undated-confirmation ---
    #
    # This is the exact defect a final whole-branch review caught: derive_evidence
    # used to guard the whole revisit check on `confirmed_at and ...`, so a rating
    # with confirmedAt None — every rating carried over from a v1 Profile, by
    # design — could never raise a revisit no matter what material arrived against
    # it. These three fixtures pin the two honest reasons and the one non-reason.
    reason_assess = [
        # Confirmed, no confirmedAt (the v1-migrated shape), material bears on it:
        # there is no date to compare against, so every bearing record counts.
        {"subcategoryId": "GV.OC-01", "applicability": "in-scope", "current": 1, "target": 2,
         "confirmedAt": None, "confirmedBy": None, "source": None},
        # Confirmed, dated, and intake postdates the confirmation.
        {"subcategoryId": "GV.OC-02", "applicability": "in-scope", "current": 1, "target": 2,
         "confirmedAt": "2026-01-01", "confirmedBy": "Darren", "source": "in-r02"},
        # Confirmed, dated, and every bearing record predates the confirmation.
        {"subcategoryId": "GV.OC-03", "applicability": "in-scope", "current": 1, "target": 2,
         "confirmedAt": "2026-06-01", "confirmedBy": "Darren", "source": "in-r03"},
    ]
    reason_intake = [
        {"id": "in-r01", "label": "control walkthrough", "sourceDate": "2026-05-01",
         "recordedAt": "2026-05-02", "subjects": ["GV.OC-01"], "recordedBy": "Darren"},
        {"id": "in-r02", "label": "policy review", "sourceDate": "2026-03-01",
         "recordedAt": "2026-03-02", "subjects": ["GV.OC-02"], "recordedBy": "Darren"},
        {"id": "in-r03", "label": "prior review", "sourceDate": "2026-01-01",
         "recordedAt": "2026-01-02", "subjects": ["GV.OC-03"], "recordedBy": "Darren"},
    ]
    ev_reason = derive_evidence(reason_assess, reason_intake, index, core, today="2026-07-27",
                                threshold_pct=0, age_days=180)
    by_reason_sid = {r["subcategoryId"]: r for r in ev_reason["revisit"]}
    eq(set(by_reason_sid), {"GV.OC-01", "GV.OC-02"},
       "undated-confirmation and newer-material both raise a revisit; fully-predated "
       "material raises neither")
    eq(by_reason_sid["GV.OC-01"]["reason"], "undated-confirmation",
       "confirmed, no confirmedAt, bearing material: reason is undated-confirmation")
    eq(by_reason_sid["GV.OC-01"]["confirmedAt"], None,
       "undated-confirmation carries confirmedAt None — never a guessed date")
    eq(by_reason_sid["GV.OC-01"]["newestSourceDate"], "2026-05-01",
       "undated-confirmation still names the newest bearing source")
    eq(by_reason_sid["GV.OC-02"]["reason"], "newer-material",
       "confirmed, dated, intake postdates it: reason is newer-material")

    q_reason = build_queue(reason_assess, reason_intake, ev_reason, index,
                           resolve_rank(index, core, load_cold_start_rank()))
    q_reason_revisit = {r["subcategoryId"]: r for r in q_reason if r["band"] == "revisit"}
    eq(q_reason_revisit["GV.OC-01"]["reason"], "undated-confirmation",
       "build_queue threads the reason through to the row for undated-confirmation")
    eq(q_reason_revisit["GV.OC-02"]["reason"], "newer-material",
       "build_queue threads the reason through to the row for newer-material")

    # --- Reproduction: the shipped v1 fixture must not swallow new material ---
    #
    # GV.OC-01 in the v1 fixture is confirmed (current=2) and, being schema v1,
    # carries no confirmedAt at all (load_store normalizes it to None in memory —
    # never backfilled from lastReviewed). Before the fix this intake vanished:
    # `analyze` reported revisit == [] and `queue` offered an unrelated cold-start
    # item instead, exactly the silent drop the review reproduced.
    v1_store = load_store(FIXTURE)
    eq(v1_store["assessments"][
           [a["subcategoryId"] for a in v1_store["assessments"]].index("GV.OC-01")
       ]["confirmedAt"], None, "the v1 fixture's GV.OC-01 carries no confirmedAt")
    v1_intake = [{"id": "in-0001", "label": "audit found the asset inventory is stale",
                  "sourceDate": "2026-07-20", "recordedAt": "2026-07-27",
                  "subjects": ["GV.OC-01"], "recordedBy": "Darren"}]
    ev_v1 = derive_evidence(v1_store["assessments"], v1_intake, index, core, today="2026-07-27",
                            threshold_pct=60, age_days=180)
    v1_revisit = {r["subcategoryId"]: r for r in ev_v1["revisit"]}
    ok("GV.OC-01" in v1_revisit,
       "reproduction: a v1 rating with fresh intake against it must raise a revisit, "
       "not be silently dropped (the exact defect the final review caught)")
    eq(v1_revisit.get("GV.OC-01", {}).get("reason"), "undated-confirmation",
       "reproduction: the reason names why — no confirmation date to compare against")
    q_v1 = build_queue(v1_store["assessments"], v1_intake, ev_v1, index,
                       resolve_rank(index, core, load_cold_start_rank()))
    ok(any(r["subcategoryId"] == "GV.OC-01" and r["band"] == "revisit" for r in q_v1),
       "reproduction: GV.OC-01 surfaces in the queue as a revisit rather than vanishing "
       "behind an unrelated cold-start item")

    age = ev["age"]["overall"]
    eq(age["dated"], 3, "age counts only dated confirmations")
    eq(age["oldestDays"], 421, "oldest: 2025-06-01 to 2026-07-27")
    eq(age["medianDays"], 198, "median of 129, 198, 421")
    eq(age["olderThanThreshold"], 2, "two ratings older than 180 days")
    eq(ev["age"]["thresholdDays"], 180, "the threshold is reported with the counts")

    # --- Age bands: graded distance from the cadence the reader chose ---
    #
    # Band names are deliberately not confidence words. `within` / `beyond` state how far
    # a determination sits from a chosen cadence; they never claim how sure anyone should
    # be that it is still true.
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
    # Pinned against a literal, not against itself: comparing the counter's keys to
    # AGE_BANDS is a tautology, since the counter is built from AGE_BANDS. The exact-dict
    # assertions above already fix the key set. What is worth pinning is the tuple's
    # ORDER, which reporting renders in and cannot re-derive.
    eq(AGE_BANDS, ("within", "approaching", "beyond", "wellBeyond"),
       "AGE_BANDS is ascending by age — reporting renders in this order")

    # --- The rendered band vocabulary, pinned from the side that owns the bands ---
    #
    # Both dashboards take their labels from renderers/_common.py, and until this block
    # existed nothing asserted them anywhere. That is how the executive age grid came to
    # label `beyond` — ratings PAST the cadence — as "within 360 days", the opposite
    # valence to the operational view's "beyond cadence", on the board's own page. The
    # engine owns this vocabulary, so the engine is where it gets pinned.
    #
    # An intra-skill import, the same shape as csfa_compat.py's: this file and the
    # renderers ship and version together. Not a cross-skill import, which is the thing
    # the note above AGE_BANDS rules out.
    #
    # Bytecode writing is off for this import, for two reasons. A shipped skill directory
    # is not ours to leave build artefacts in, and it may not even be writable. More
    # usefully: a mutation test that edits _common.py to the same byte length within the
    # same second leaves a .pyc that Python still considers valid, so the mutant appears
    # to survive and the restored original appears to fail. That cost real time to spot
    # once; nobody should have to spot it twice.
    _wrote_bytecode = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    sys.path.insert(0, os.path.join(_SKILL_ROOT, "renderers"))
    try:
        import _common as _rc
    finally:
        sys.dont_write_bytecode = _wrote_bytecode
    eq(tuple(_rc.AGE_BAND_ORDER), AGE_BANDS,
       "the renderers draw the bands in the engine's own order")
    eq(sorted(_rc.AGE_BAND_LABEL), sorted(AGE_BANDS),
       "every band the engine can emit has a rendered label")
    eq(sorted(_rc.AGE_BAND_FILL), sorted(AGE_BANDS),
       "every band the engine can emit has a fill")
    # The values, not just the keys. A relabelling is the defect this catches, and its
    # failure mode is prose that reads perfectly well while describing a different
    # population — so the words are fixed here and a reword has to be deliberate.
    eq(_rc.AGE_BAND_LABEL,
       {"within": "within cadence", "approaching": "approaching cadence",
        "beyond": "beyond cadence", "wellBeyond": "well beyond cadence"},
       "a rating past its cadence is labelled as past it, on every surface")
    # Ranges are EXCLUSIVE and adjacent: each band begins the day after the one below
    # ends, so the four together partition the dated population exactly once. A cumulative
    # phrase over any one of them describes a population it does not count.
    eq(_rc.age_band_ranges(180),
       {"within": "0–90d", "approaching": "91–180d", "beyond": "181–360d",
        "wellBeyond": "over 360d"},
       "band ranges are exclusive and adjacent, never cumulative")
    eq(_rc.age_band_ranges(365),
       {"within": "0–182d", "approaching": "183–365d", "beyond": "366–730d",
        "wellBeyond": "over 730d"},
       "and every range boundary is derived from T, never hardcoded")
    # Both properties the fill ramp claims for itself. Lightness is what orders an ordinal
    # scale, so it must descend strictly; and each fill must clear AA against the text
    # colour text_on() picks for it. The suite's contrast eval measures a rendered page —
    # this measures the tokens, so a retune fails before anything is rendered at all.
    _lums = [_rc._luminance(_rc.AGE_BAND_FILL[b]) for b in AGE_BANDS]
    ok(all(x > y for x, y in zip(_lums, _lums[1:])),
       "the age ramp darkens monotonically — lightness is what orders the bands")
    ok(all(_rc.contrast_ratio(_rc.text_on(_rc.AGE_BAND_FILL[b]), _rc.AGE_BAND_FILL[b]) >= 4.5
           for b in AGE_BANDS),
       "every age band fill clears WCAG AA against its own text colour")
    ok(all(_rc.AGE_BAND_FILL[b] not in set(_rc.EVIDENCE_FILL.values()) for b in AGE_BANDS),
       "no age band reuses an evidence-state fill — the two strips sit one above the other")

    # The ranges must agree with age_band() itself, or a label and the count beneath it
    # describe different populations. Checked at the boundaries, which is where the two can
    # disagree: the last day each range claims is read back out of the label string and fed
    # to age_band, and the day after it must land in a different band. That catches an
    # off-by-one in either direction. Three thresholds, including T=198, which puts a
    # fixture rating exactly on a line — the same reason the identity checks below use it.
    for _T in (180, 365, 198):
        _r = _rc.age_band_ranges(_T)
        _upper = {"within": _T // 2, "approaching": _T, "beyond": _T * 2}
        for _b, _hi in _upper.items():
            ok(_r[_b].endswith(f"{_hi}d") and age_band(_hi, _T) == _b,
               f"T={_T}: the {_b} range ends where age_band puts its last day")
            ok(age_band(_hi + 1, _T) != _b,
               f"T={_T}: one day past the {_b} range is a different band")

    # The identity has to hold at a rescaled threshold too, or it is an accident of 180.
    ev365 = derive_evidence(fx_assess, fx_intake, index, core, today="2026-07-27",
                            threshold_pct=60, age_days=365)
    age365 = ev365["age"]["overall"]
    eq(age365["bands"], {"within": 1, "approaching": 1, "beyond": 1, "wellBeyond": 0},
       "at T=365 the same three ages redistribute")
    eq(age365["bands"]["beyond"] + age365["bands"]["wellBeyond"],
       age365["olderThanThreshold"], "the identity holds at T=365, not just at T=180")
    eq(ev365["age"]["thresholdDays"], 365, "the rescaled threshold is reported back")

    # T=198 puts PR.DS-11 exactly ON the line, and that is the whole point of this third
    # call. beyond + wellBeyond == olderThanThreshold is a claim about two independent
    # expressions agreeing — age_band's `days <= threshold_days` and _age's `d > age_days`
    # — and no fixture age equals 180 or 365, so at those thresholds the identity holds
    # no matter which way either comparison is written. Flip _age's `>` to `>=` and only
    # a rating sitting on the boundary notices.
    ev198 = derive_evidence(fx_assess, fx_intake, index, core, today="2026-07-27",
                            threshold_pct=60, age_days=198)
    age198 = ev198["age"]["overall"]
    eq(age198["bands"], {"within": 0, "approaching": 2, "beyond": 0, "wellBeyond": 1},
       "at T=198 the 198-day rating sits on the line and counts as approaching")
    eq(age198["bands"]["beyond"] + age198["bands"]["wellBeyond"],
       age198["olderThanThreshold"],
       "the identity survives a rating exactly ON the threshold — the only case that "
       "can catch the two comparisons disagreeing")
    eq(ev198["age"]["thresholdDays"], 198, "the on-the-line threshold is reported back")

    # Per-Function bands are asserted as whole dicts, not single keys. A single-key check
    # stays true even if every Function wrongly reports the entire Profile, which is
    # precisely the claim these labels make. The 198-day rating is PR.DS-11, so `beyond`
    # sits under PR alone; ID carries the 129-day and 421-day ratings and nothing else.
    eq(ev["age"]["byFunction"]["PR"]["bands"],
       {"within": 0, "approaching": 0, "beyond": 1, "wellBeyond": 0},
       "bands are reported per Function as well as overall")
    eq(ev["age"]["byFunction"]["ID"]["bands"],
       {"within": 0, "approaching": 1, "beyond": 0, "wellBeyond": 1},
       "the per-Function partition puts ID's 421-day rating in wellBeyond, not PR's")

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

        # ...and hands that same threshold to the attention lists. Nothing above binds
        # this: every banding check so far calls attention_lists directly, so dropping
        # the age_days argument at the call site would leave it defaulting to 180 with
        # every one of them still green. ID.AM-01 was confirmed 2026-03-20 and today is
        # 2026-07-27 — 129 days, which is `approaching` a 180-day cadence and `within` a
        # 365-day one. The same store rescaled must therefore move.
        _an_row = [r for r in an["attention"]["stalest"] if r["subcategoryId"] == "ID.AM-01"]
        eq([(r["confirmationAgeDays"], r["confirmationBand"]) for r in _an_row],
           [(129, "approaching")], "analyze bands a stalest row against `today`, not the clock")
        _v365 = json.load(open(_p, encoding="utf-8"))
        _v365["profile"]["settings"]["reporting"]["ageThresholdDays"] = 365
        _p365 = os.path.join(_d, "an365.csfp")
        _out365 = os.path.join(_d, "an365.json")
        with open(_p365, "w", encoding="utf-8") as _fh:
            json.dump(_v365, _fh)
        _cmd_analyze([_p365, "--today", "2026-07-27", "--out", _out365])
        with open(_out365, encoding="utf-8") as _fh:
            an365 = json.load(_fh)
        eq(an365["evidence"]["age"]["thresholdDays"], 365, "the rescaled threshold is in force")
        eq([(r["subcategoryId"], r["confirmationBand"]) for r in an365["attention"]["stalest"]],
           [("ID.AM-01", "within")],
           "analyze passes the Profile's configured threshold to attention_lists, not 180")
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

    # --- The shipped v2 fixture exercises every new state at once ---
    fx2 = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "examples",
                       "example-profile-v2.csfp")
    s2 = load_store(fx2)
    eq(s2["schemaVersion"], "2.0", "v2 fixture is schema 2.0")
    eq(len(s2["intake"]), 4, "v2 fixture carries four intake records")
    eq(check_store(s2, index), [], "v2 fixture passes structural validation")
    rep2 = s2["profile"]["settings"]["reporting"]
    ev2 = derive_evidence(s2["assessments"], s2["intake"], index, core, "2026-07-27",
                          rep2["scopeThresholdPct"], rep2["ageThresholdDays"])
    cov2 = ev2["coverage"]["overall"]
    eq(cov2["confirmed"], 4, "v2 fixture: four confirmed ratings")
    eq(cov2["attributed"], 4, "v2 fixture: every confirmation is attributed")
    eq(cov2["unattributed"], 0, "v2 fixture: nothing confirmed without a source")
    eq(cov2["evidencePending"], 5, "v2 fixture: five Subcategories have material, no rating")
    eq(cov2["unrated"], 96, "v2 fixture: the rest have nothing recorded")
    eq(cov2["notApplicable"], 1, "v2 fixture: one Subcategory scoped out")
    eq(cov2["confirmed"] + cov2["evidencePending"] + cov2["unrated"] + cov2["notApplicable"],
       106, "v2 fixture: the four buckets partition all 106")

    eq([r["subcategoryId"] for r in ev2["revisit"]], ["RC.RP-01"],
       "v2 fixture: the DR walkthrough questions the January recovery rating")
    eq(ev2["revisit"][0]["confirmedAt"], "2026-01-10", "revisit names the confirmation it questions")
    eq(ev2["revisit"][0]["newestSourceDate"], "2026-06-30", "and the material that questions it")
    eq(ev2["revisit"][0]["reason"], "newer-material",
       "v2 fixture: RC.RP-01 is dated, so its revisit reason is newer-material")

    age2 = ev2["age"]["overall"]
    eq(age2["dated"], 4, "v2 fixture: four dated confirmations")
    eq(age2["oldestDays"], 420, "v2 fixture: oldest is 2025-06-02 to 2026-07-27")
    eq(age2["medianDays"], 309, "v2 fixture: median of 198, 198, 420, 420")
    eq(age2["olderThanThreshold"], 4, "v2 fixture: all four are older than the 180-day default")
    ok(age2["oldestDays"] > 365, "v2 fixture: ratings span more than twelve months")

    eq(ev2["scopeGuard"]["assessed"], 4, "v2 fixture: four of 105 in-scope assessed")
    eq(ev2["scopeGuard"]["inScope"], 105, "v2 fixture: the n/a Subcategory is out of the denominator")
    ok(ev2["scopeGuard"]["suppressed"], "v2 fixture sits below the scope threshold")

    _rank2 = resolve_rank(index, core, load_cold_start_rank())
    q2_all = build_queue(s2["assessments"], s2["intake"], ev2, index, _rank2)
    bands2 = [r["band"] for r in q2_all]
    eq(bands2[:5], ["evidence-pending"] * 5, "the five pending items lead the queue")
    eq(bands2[5], "revisit", "the revisit follows them, before any cold start")
    eq(q2_all[5]["subcategoryId"], "RC.RP-01", "and it is the recovery rating")
    ok(all(b == "cold-start" for b in bands2[6:]), "cold-start fills the tail")

    # A full batch of pending material pushes the revisit to the next session. That is
    # the anti-rubber-stamping cap working, not a defect — five is a deliberate limit.
    q2 = build_queue(s2["assessments"], s2["intake"], ev2, index, _rank2, 5)
    eq(len(q2), 5, "the default batch is five")
    ok(all(r["band"] == "evidence-pending" for r in q2),
       "five pending items fill the first batch, so the revisit waits for the next")
    ok(all(r["tier"] is None for r in q2), "v2 fixture queue carries no pre-filled ratings")

    bysrc2 = coverage_by_source(s2["intake"], ev2["states"], index)
    eq([r["id"] for r in bysrc2], ["in-0004", "in-0003", "in-0002", "in-0001"],
       "v2 fixture sources are newest-first by sourceDate")
    eq([r["confirmed"] for r in bysrc2 if r["id"] == "in-0001"][0], 2,
       "the asset workshop confirmed two of its four subjects")
    eq(len(s2["snapshots"]), 1, "v2 fixture carries a snapshot, so diff has something to compare")

    # --- Export contract ---
    eq(EXPORT_COLUMNS,
       ["subcategory_id", "function_id", "category_id", "current_tier", "target_tier",
        "priority", "subcategory_text", "note"],
       "export columns match the risk-register import contract exactly")

    # --- Crosswalk lenses ---
    #
    # Data-independent: a synthetic crosswalk built inline, so the math is
    # asserted in isolation from whatever the bundled catalogs happen to contain.
    # Every expectation below was computed by hand before the code was written.
    synth = {
        "catalog": {"frameworkId": "synth", "name": "Synthetic", "version": "1",
                    "license": "test",
                    "groupings": [{"id": "G1", "label": "Group one"},
                                  {"id": "G2", "label": "Group two"}]},
        "controls": {
            "X-1": {"id": "X-1", "label": "min of 1 and 3", "groupingId": "G1",
                    "labelSource": "cac-generated"},
            "X-2": {"id": "X-2", "label": "only unrated behind it", "groupingId": "G1",
                    "labelSource": "cac-generated"},
            "X-10": {"id": "X-10", "label": "sorts after X-2", "groupingId": "G2",
                     "labelSource": "cac-generated"},
            "X-99": {"id": "X-99", "label": "no CSF maps here", "groupingId": "G2",
                     "labelSource": "cac-generated"},
            # Unmapped like X-99, but for a different reason: the source names it
            # against a Category, so CSF does reach it and the two must not share
            # a list. Without this the honesty list overstates itself.
            "X-98": {"id": "X-98", "label": "reached at Category grain only",
                     "groupingId": "G2", "labelSource": "cac-generated",
                     "csfReference": "category-only"},
        },
        "fwd": {"X-1": ["S.A", "S.B"], "X-2": ["S.C"], "X-10": ["S.D", "S.E"]},
        "rev": {"S.A": ["X-1"], "S.B": ["X-1"], "S.C": ["X-2"],
                "S.D": ["X-10"], "S.E": ["X-10"]},
        "authority": "test",
    }
    cw_asmts = [
        {"subcategoryId": "S.A", "current": 1, "target": 3, "applicability": "in-scope"},
        {"subcategoryId": "S.B", "current": 3, "target": 3, "applicability": "in-scope"},
        {"subcategoryId": "S.C", "current": None, "target": 3, "applicability": "in-scope"},
        {"subcategoryId": "S.D", "current": 2, "target": 3, "applicability": "in-scope"},
        {"subcategoryId": "S.E", "current": 0, "target": 3, "applicability": "not-applicable"},
        {"subcategoryId": "S.Z", "current": 3, "target": 3, "applicability": "in-scope"},
    ]
    s3 = {"scale": {"min": 0, "max": 3, "labels": {}}}
    cov = derive_crosswalk_coverage(cw_asmts, synth, s3, agg="min")
    byc = {c["controlId"]: c for c in cov["controls"]}

    # Weakest link, not the average: min(1, 3) is 1, and the mean would be 2.
    eq(byc["X-1"]["score"], 1, "crosswalk X-1 is the weakest link")
    eq(byc["X-1"]["ratedContributors"], 2, "crosswalk X-1 counts both contributors")
    # A control with nothing rated behind it is unknown, never zero.
    eq(byc["X-2"]["score"], None, "crosswalk X-2 unrated scores None")
    eq(byc["X-2"]["band"], "unknown", "crosswalk X-2 bands unknown")
    eq(byc["X-2"]["unratedContributors"], 1, "crosswalk X-2 counts the unrated contributor")
    # not-applicable is excluded from the score rather than dragging it to 0,
    # and is reported so the exclusion is visible.
    eq(byc["X-10"]["score"], 2, "crosswalk not-applicable excluded from min")
    eq(byc["X-10"]["notApplicableContributors"], 1, "crosswalk counts the n/a contributor")
    # Natural sort: X-10 comes after X-2, not between X-1 and X-2.
    eq([c["controlId"] for c in cov["controls"]], ["X-1", "X-2", "X-10"],
       "crosswalk controls sort naturally")
    # Theme is the mean of member control scores, not min-of-min — asserted with
    # suppression disabled, since G1 has only 1 of its 2 controls scored (50%) and
    # is withheld at the default threshold.
    bygrp = {g["groupingId"]: g for g in cov["groupings"]}
    eq(bygrp["G1"]["band"], "insufficient", "a theme with a thin basis is suppressed too")
    eq(bygrp["G1"]["score"], None, "a suppressed theme withholds its score")
    eq(bygrp["G1"]["controlsScored"], 1, "crosswalk theme G1 counts scored controls only")
    eq(bygrp["G1"]["controlsMapped"], 2, "crosswalk theme G1 reports its full membership")
    eq(bygrp["G2"]["score"], 2.0, "crosswalk theme G2 = mean([2])")
    _open = derive_crosswalk_coverage(
        cw_asmts, synth, {"scale": s3["scale"], "reporting": {"scopeThresholdPct": 0}})
    eq({g["groupingId"]: g["score"] for g in _open["groupings"]}["G1"], 1.0,
       "crosswalk theme G1 = mean([1]) once suppression is off")
    # mean aggregation is available and differs from min on X-1.
    cov_mean = derive_crosswalk_coverage(cw_asmts, synth, s3, agg="mean")
    eq({c["controlId"]: c["score"] for c in cov_mean["controls"]}["X-1"], 2.0,
       "crosswalk mean agg averages contributors")
    ok(_crosswalk_agg([], "min") is None, "crosswalk agg of nothing is None")

    # A band drawn from too little of its basis is suppressed, not caveated, and
    # the score goes with it. X-thin has one rated contributor of three in scope
    # (33%, under the 60% default), so the weakest-link minimum it would report is
    # an upper bound the report declines to publish.
    synth_thin = json.loads(json.dumps(synth))
    synth_thin["controls"]["X-thin"] = {"id": "X-thin", "label": "one of three rated",
                                        "groupingId": "G2", "labelSource": "cac-generated"}
    synth_thin["fwd"]["X-thin"] = ["S.A", "S.C", "S.F"]
    thin_asmts = cw_asmts + [
        {"subcategoryId": "S.F", "current": None, "target": 3, "applicability": "in-scope"}]
    cov_thin = derive_crosswalk_coverage(thin_asmts, synth_thin, s3)
    bythin = {c["controlId"]: c for c in cov_thin["controls"]}
    eq(bythin["X-thin"]["band"], "insufficient", "a thin basis suppresses the band")
    eq(bythin["X-thin"]["score"], None, "a suppressed band withholds its score too")
    ok(bythin["X-thin"]["bandSuppressed"], "a suppressed band says so")
    eq(bythin["X-thin"]["basisPct"], 33.3, "a suppressed band reports its basis share")
    # X-1 is fully rated, so it is unaffected — suppression must not be indiscriminate.
    eq(bythin["X-1"]["band"], "weak", "a fully-rated control is not suppressed")
    # And the withheld control must not reach its theme at its withheld value.
    thin_g2 = next(g for g in cov_thin["groupings"] if g["groupingId"] == "G2")
    eq(thin_g2["controlsScored"], 1, "a suppressed control is excluded from its theme")
    # Raising the threshold to 100 suppresses anything less than fully rated;
    # dropping it to 0 restores every band. One knob, both directions.
    s3_strict = {"scale": s3["scale"], "reporting": {"scopeThresholdPct": 100}}
    strict = {c["controlId"]: c for c in
              derive_crosswalk_coverage(thin_asmts, synth_thin, s3_strict)["controls"]}
    eq(strict["X-1"]["band"], "weak", "a fully-rated control survives a 100% threshold")
    s3_off = {"scale": s3["scale"], "reporting": {"scopeThresholdPct": 0}}
    lax = {c["controlId"]: c for c in
           derive_crosswalk_coverage(thin_asmts, synth_thin, s3_off)["controls"]}
    eq(lax["X-thin"]["band"], "weak", "a zero threshold suppresses nothing")
    # The reverse view must agree with the forward one, or a reader could look up
    # a control the table declined to band and be handed the band anyway.
    rl_thin = crosswalk_reverse_lookup(synth_thin, "X-thin", thin_asmts, s3)
    eq(rl_thin["band"], "insufficient", "reverse lookup suppresses the same band")
    eq(rl_thin["score"], None, "reverse lookup withholds the same score")

    # Bands are a share of the declared scale, so the same rating bands
    # differently on the two scales the skill supports. This is the whole reason
    # crosswalk_band takes settings: a hardcoded ">= 3 is strong" would call a
    # 0-4 Profile rated 3 ("Repeatable") the same as a native 0-3 Profile rated
    # 3 ("Fully Achieved"), which is its maximum.
    s4 = {"scale": {"min": 0, "max": 4, "labels": {}}}
    eq(crosswalk_band(3, s3), "strong", "3 of 3 is strong")
    eq(crosswalk_band(3, s4), "moderate", "3 of 4 is not strong")
    eq(crosswalk_band(4, s4), "strong", "4 of 4 is strong")
    eq(crosswalk_band(2, s3), "moderate", "2 of 3 is moderate")
    eq(crosswalk_band(1, s3), "weak", "1 of 3 is weak")
    eq(crosswalk_band(0, s3), "minimal", "0 of 3 is minimal")
    eq(crosswalk_band(None, s3), "unknown", "no score bands unknown")
    eq(crosswalk_band(2, {"scale": {"max": 0}}), "unknown", "a zero scale cannot band")
    eq(crosswalk_band(2, {}), "unknown", "a missing scale cannot band")
    eq(cov["scale"]["max"], 3, "crosswalk coverage echoes the scale it banded against")
    eq(cov["aggregation"], {"control": "min", "grouping": "mean"},
       "crosswalk coverage states its aggregation")
    ok(cov["disclaimer"].startswith("Derived from your NIST CSF assessment"),
       "crosswalk coverage carries the derived-not-audit disclaimer")

    # Reverse lookup: the auditor's direction.
    rl = crosswalk_reverse_lookup(synth, "X-1", cw_asmts, s3)
    eq([b["csfSubId"] for b in rl["behind"]], ["S.A", "S.B"], "reverse lookup lists what is behind")
    eq(rl["behind"][0]["current"], 1, "reverse lookup carries the rating")
    eq(rl["score"], 1, "reverse lookup agrees with forward coverage")
    # A control that exists but nothing maps to differs from one that does not exist.
    rl_unmapped = crosswalk_reverse_lookup(synth, "X-99", cw_asmts, s3)
    ok(rl_unmapped["known"] and "assess this control directly" in rl_unmapped["note"],
       "reverse lookup tells an unmapped control to be assessed directly")
    rl_absent = crosswalk_reverse_lookup(synth, "NOPE-1", cw_asmts, s3)
    ok(not rl_absent["known"] and "not a control" in rl_absent["note"],
       "reverse lookup rejects a control the framework does not have")

    # Honesty lists, both directions.
    comp = crosswalk_completeness(synth, cw_asmts)
    eq(comp["controlsOutsideCSF"], ["X-99"], "completeness lists controls outside CSF")
    eq(comp["csfNotInLens"], ["S.Z"], "completeness lists rated outcomes the lens cannot see")
    ok("S.E" not in comp["csfNotInLens"], "a not-applicable outcome is not owed lens credit")
    # Both are unmapped; only one of them is outside CSF. Folding them together
    # would tell a reader to go assess X-98 from scratch when CSF already reaches it.
    eq(comp["controlsCategoryOnly"], ["X-98"], "a Category-only control gets its own list")
    ok("X-98" not in comp["controlsOutsideCSF"],
       "and is kept off the outside-CSF list, which would otherwise overstate by one")
    eq(comp["controlsTotal"], 5, "the Category-only control still counts in the total")
    eq(comp["controlsMapped"], 3, "and is not counted as mapped, because nothing scores it")

    # Bundled data: every edge resolves and the counts are the pinned ones.
    eq(check_crosswalks(index), [], "bundled crosswalk data is clean")
    for _fid, _want in sorted(CROSSWALK_EXPECTED.items()):
        _cw = load_crosswalk(_fid)
        eq(len(_cw["controls"]), _want["controls"], f"{_fid} control count")
        eq(sum(len(v) for v in _cw["fwd"].values()), _want["edges"], f"{_fid} edge count")
        ok(all(s in index for subs in _cw["fwd"].values() for s in subs),
           f"{_fid} every edge cites a real Subcategory")
        ok(all(c.get("text") in (None, "") for c in _cw["controls"].values())
           if not _want["verbatimAllowed"] else True,
           f"{_fid} ships no normative text")
    try:
        load_crosswalk("not-a-framework")
        failures.append("load_crosswalk accepted an unknown framework")
        checks += 1
    except ValueError:
        ok(True, "load_crosswalk rejects an unknown framework")

    # A lens is opt-in. The trigger eval routes prompts to skills and cannot see
    # sub-modes, so the "plain CSF ask must not produce a crosswalk" requirement is
    # asserted here instead, where it is deterministic: no --crosswalk, no key at
    # all. `"crosswalks": null` would be a diff on every existing Profile.
    _no_lens = derive_crosswalk_coverage(cw_asmts, synth, s3)
    ok("subcategories" not in _no_lens,
       "crosswalk coverage omits Subcategory detail unless an index is supplied")
    ok(load_crosswalk("cis-8.1", DEFAULT_CROSSWALK_DIR)["authority"] == "cis-authored",
       "load_crosswalk honours an explicit data directory")

    # Real-data parity against a hand-verified golden fixture. The synthetic
    # checks above lock the math; this locks the math against the actual bundled
    # catalogs, so a data refresh that moves a mapping cannot pass unnoticed.
    # The fixture is a .csfa, so it converts onto the 0-4 scale and its bands are
    # shares of 4 — which is what makes it the regression test for banding
    # against the wrong scale.
    _golden = os.path.join(_SKILL_ROOT, "evals", "fixtures", "crosswalk-golden.csfa")
    _golden_expected = os.path.join(_SKILL_ROOT, "evals", "fixtures",
                                    "crosswalk-golden-expected.json")
    if os.path.isfile(_golden) and os.path.isfile(_golden_expected):
        import importlib.util as _ilu
        _cc_path = os.path.join(_SKILL_ROOT, "scripts", "csfa_compat.py")
        _spec = _ilu.spec_from_file_location("_csfa_compat_selftest", _cc_path)
        _cc = _ilu.module_from_spec(_spec)
        _spec.loader.exec_module(_cc)
        with open(_golden, encoding="utf-8") as f:
            _csfa = json.load(f)
        with open(_golden_expected, encoding="utf-8") as f:
            _exp = json.load(f)
        _store = _cc.convert_to_csfp(_csfa, core, "2026-07-29T00:00:00Z")
        _asmts = _store["assessments"]
        _settings = _store["profile"]["settings"]
        eq(_settings["scale"]["max"], _exp["scaleMax"], "golden fixture converts to the expected scale")
        eq(_settings["reporting"]["scopeThresholdPct"], _exp["thresholdPct"],
           "golden fixture asserts against the expected suppression threshold")
        for _fid, _want_lens in sorted(_exp["lenses"].items()):
            _cw = load_crosswalk(_fid)
            _cov = derive_crosswalk_coverage(_asmts, _cw, _settings, agg="min", index=index)
            _comp = crosswalk_completeness(_cw, _asmts)
            _byc = {c["controlId"]: c for c in _cov["controls"]}
            eq(_cov["mappingAuthority"], _want_lens["mappingAuthority"],
               f"golden {_fid} mapping authority")
            eq(len(_cov["controls"]), _want_lens["controlsScored"],
               f"golden {_fid} scored control count")
            _hist: dict[str, int] = {}
            for c in _cov["controls"]:
                _hist[c["band"]] = _hist.get(c["band"], 0) + 1
            eq(dict(sorted(_hist.items())), _want_lens["bandHistogram"],
               f"golden {_fid} band histogram")
            eq({k: v for k, v in _cov["suppression"].items() if k != "basis"},
               _want_lens["suppression"], f"golden {_fid} suppression summary")
            for _gid, _wg in sorted(_want_lens["groupings"].items()):
                _got = next((g for g in _cov["groupings"] if g["groupingId"] == _gid), None)
                eq({k: (_got or {}).get(k) for k in _wg}, _wg, f"golden {_fid} theme {_gid}")
            for _cid, _wc in sorted(_want_lens["handVerifiedControls"].items()):
                _gc = _byc.get(_cid)
                eq({k: (_gc or {}).get(k) for k in _wc}, _wc,
                   f"golden {_fid} control {_cid}")
            _got_comp = dict(_comp,
                             controlsOutsideCSF=len(_comp["controlsOutsideCSF"]),
                             controlsCategoryOnly=len(_comp["controlsCategoryOnly"]))
            eq({k: _got_comp.get(k) for k in _want_lens["completeness"]},
               _want_lens["completeness"], f"golden {_fid} completeness")
    else:
        failures.append("golden crosswalk fixture is missing")
        checks += 1

    # --- D-3: the AI inventory signal, as evidence and never as an answer -----
    #
    # The property that matters is what the signal is NOT allowed to be. A rating or a
    # priority arriving here would be `ai-register` answering this skill's question, and the
    # question — which focus areas does this Profile apply — is a judgement made here.
    _payload = {
        "contractVersion": CONTEXT_CONTRACT,
        "profileVersion": "1",
        "applicability": {CONTEXT_SKILL: {"ask": ["ai-overlay"], "skipped": []}},
    }
    _no_signal = applicability_for(_payload, {"enabled": False, "focusAreas": []})
    eq(json.dumps(_no_signal, sort_keys=True),
       json.dumps(applicability_for(_payload, {"enabled": False, "focusAreas": []}, None),
                  sort_keys=True),
       "with no signal, the context block is byte-for-byte what it always was")
    ok("inventorySignal" not in (_no_signal["asked"][0] if _no_signal["asked"] else {}),
       "...and carries no signal key at all, rather than one set to null")
    _sig = {"asOf": "2026-08-01",
            "counts": {"deployments": 12, "generative": 9, "acts": 2,
                       "consequentialDecisions": 3, "unsanctioned": 1}}
    _with = applicability_for(_payload, {"enabled": False, "focusAreas": []}, _sig)
    ok("inventorySignal" in _with["asked"][0], "a supplied signal appears as evidence")
    ok("12 AI deployment(s) recorded" in _with["asked"][0]["inventorySignal"]["sentence"],
       "...as counts of what is recorded")
    ok(_with["conflicts"] and "Enable `secure`" in _with["conflicts"][0]["sentence"],
       "and the conflict still says to resolve it — the signal informs, it does not answer")
    eq(_with["asked"][0]["applied"], _no_signal["asked"][0]["applied"],
       "...specifically: the signal changes no decision this skill makes")
    with tempfile.TemporaryDirectory() as _sd:
        _p = os.path.join(_sd, "sig.json")
        with open(_p, "w", encoding="utf-8") as _fh:
            json.dump({"export": "signal", "asOf": "2026-08-01",
                       "counts": {"deployments": 3}}, _fh)
        eq(load_ai_signal(_p)["counts"], {"deployments": 3}, "a counts-only signal loads")
        with open(_p, "w", encoding="utf-8") as _fh:
            json.dump({"export": "signal", "asOf": "2026-08-01",
                       "counts": {"deployments": 3, "postureRating": "high"}}, _fh)
        try:
            load_ai_signal(_p)
            failures.append("a signal carrying a rating was accepted")
            checks += 1
        except ValueError as _exc:
            ok("counts only" in str(_exc),
               "and one carrying a rating is refused, saying the judgement is made here")
        with open(_p, "w", encoding="utf-8") as _fh:
            json.dump({"export": "findings", "findings": []}, _fh)
        try:
            load_ai_signal(_p)
            failures.append("a findings export was accepted as a signal")
            checks += 1
        except ValueError:
            ok("...and a findings export is not a signal", True)

    # --- BL-219: an interrupted write leaves the Profile exactly as it was ---------------
    #
    # No happy-path test can see this. `open(path, "w")` and mkstemp+os.replace write
    # identical bytes when nothing goes wrong, which is how a store carrying all 106
    # subcategories stayed non-atomic through nine releases with every check above green. The
    # comparison is BYTE FOR BYTE against what was on disk before: a rollback leaving a
    # valid-but-different Profile is a different bug in this one's clothes.
    with tempfile.TemporaryDirectory() as _atd:
        _apath = os.path.join(_atd, "atomic.csfp")
        _before = '{"the Profile that was already here": "must survive"}\n'
        with open(_apath, "w", encoding="utf-8") as _fh:
            _fh.write(_before)

        def _cut_short(*_a, **_k):
            raise KeyboardInterrupt("interrupted part-way through the dump")

        _real_dump = json.dump
        json.dump = _cut_short
        try:
            save_store({"profile": {}, "subcategories": []}, _apath, "2026-01-01T00:00:00Z")
            _propagated = "nothing"
        except BaseException as _exc:       # KeyboardInterrupt is not an Exception
            _propagated = type(_exc).__name__
        finally:
            json.dump = _real_dump
        eq(_propagated, "KeyboardInterrupt",
           "an interrupted write propagates rather than being swallowed")
        with open(_apath, encoding="utf-8") as _fh:
            eq(_fh.read(), _before,
               "and the Profile on disk is byte-identical to before the write")
        eq(sorted(f for f in os.listdir(_atd) if f != "atomic.csfp"), [],
           "with no temp file left behind")

    print(f"self-test: {checks - len(failures)}/{checks} checks passed")
    if failures:
        print("\nFAILED:", file=sys.stderr)
        for f in failures:
            print(f"  - {f}", file=sys.stderr)
        return 1
    return 0


COMMANDS = {
    "validate": _cmd_validate, "self-test": _cmd_self_test, "posture": _cmd_posture,
    "init": _cmd_init, "set": _cmd_set, "set-tier": _cmd_set_tier,
    "quickstart-target": _cmd_quickstart_target,
    "snapshot": _cmd_snapshot, "diff": _cmd_diff, "action": _cmd_action,
    "intake": _cmd_intake, "overlay": _cmd_overlay, "crosswalk": _cmd_crosswalk,
    "queue": _cmd_queue, "elicit": _cmd_elicit,
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
