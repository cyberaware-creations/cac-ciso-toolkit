#!/usr/bin/env python3
"""
csfa_compat.py — compatibility layer for the csf-assessment web tool's `.csfa` files.

Two jobs, both about not stranding anyone who used the web tool:

  1. PARITY. Reproduce the tool's gaps CSV byte-for-byte from a `.csfa`. That CSV is
     the documented interop contract consumed by risk-register's `import-gaps`, and
     byte-parity is the gate that lets the web app be retired without silently
     changing anyone's downstream data.

  2. MIGRATION. Convert a `.csfa` into a native `.csfp` so an existing assessment
     becomes a tracked Organizational Profile with history, snapshots, and
     per-Subcategory targets.

This is a PORT, not a redesign. The scoring, target resolution, priority rule, sort
order, and CSV quoting below are transcriptions of the TypeScript originals:

    src/lib/assessment/storage.ts   -> load_csfa (the parse gates)
    src/lib/assessment/targets.ts   -> resolve_target, TARGET_PRESETS
    src/lib/assessment/guidance.ts  -> priority_of, compute_gaps, export_gaps_csv

Deliberately kept OUT of profile_analysis.py. The native engine has a different and
more defensible model — per-Subcategory targets, coverage as sum(min(current,target))
/ sum(target) rather than a mean, and priority as gap x weight rather than gap-size
bands. Mixing the two in one module would invite one to drift into the other. This
file is frozen against the web tool; that one is free to evolve.

Note the scale difference: `.csfa` tiers are 1-4 (the tool never had a 0 level) and
its parse gate rejects 0. Conversion maps them onto the target Profile's own scale.

Subcommands:
  gaps      <file.csfa> [--out F]                 Byte-parity gaps CSV.
  convert   <file.csfa> --out <file.csfp> [--ts]  Migrate into a native Profile.
  self-test                                        Parity against the golden fixtures.

Usage:
  python3 csfa_compat.py gaps ../examples/acme-manufacturing.csfa --out gaps.csv
  python3 csfa_compat.py convert assessment.csfa --out profile.csfp
"""

from __future__ import annotations

import copy
import json
import os
import re
import sys
from datetime import datetime, timezone

try:
    import signal
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)
except (ImportError, AttributeError, ValueError):
    pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import profile_analysis as pa  # noqa: E402

SCHEMA_VERSION = 1
FRAMEWORK_ID = "csf-2.0"

# targets.ts — presets are starting points; any deviation flips preset to "custom".
TARGET_PRESETS = {
    "adaptive": {"preset": "adaptive", "default": 4},
    "repeatable": {"preset": "repeatable", "default": 3},
    "governance-first": {"preset": "governance-first", "default": 2,
                         "byFunction": {"GV": 3, "PR": 3}},
}
DEFAULT_TARGETS = TARGET_PRESETS["adaptive"]

# guidance.ts
PRIORITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3}
FUNCTION_ORDER = ["GV", "ID", "PR", "DE", "RS", "RC"]

# The tool's per-subcategory rating labels reuse NIST's Tier vocabulary for 1-4.
# Retained for fidelity when rendering ported guidance; see the disclaimer in
# references/scale-and-scoring.md. These are NOT CSF Implementation Tiers.
TIER_NAMES = {0: "Not Implemented", 1: "Partial", 2: "Risk Informed",
              3: "Repeatable", 4: "Adaptive"}


# --- storage.ts: parse ---------------------------------------------------------

def load_csfa(path: str) -> dict:
    """Load a `.csfa`, applying the web tool's exact validation gates."""
    try:
        with open(path, encoding="utf-8") as fh:
            obj = json.load(fh)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Not a valid assessment file (invalid JSON): {exc}") from exc

    if obj.get("schemaVersion") != SCHEMA_VERSION:
        raise ValueError(f"Unsupported schema version (expected {SCHEMA_VERSION}).")
    if obj.get("frameworkId") != FRAMEWORK_ID:
        raise ValueError(f"Unsupported framework {obj.get('frameworkId')!r}.")

    ratings = obj.get("ratings") or {}
    for sid, rt in ratings.items():
        # The tool has no 0 level; its gate rejects it. Honoured so a file this
        # accepts is exactly a file the tool accepts.
        if rt.get("tier") is not None and rt.get("tier") not in (1, 2, 3, 4):
            raise ValueError(f"Invalid tier for {sid}.")
        if not isinstance(rt.get("na"), bool):
            raise ValueError(f"Invalid N/A flag for {sid}.")

    obj["targets"] = obj.get("targets") or copy.deepcopy(DEFAULT_TARGETS)
    return obj


# --- targets.ts ----------------------------------------------------------------

def resolve_target(function_id: str, targets: dict) -> int:
    """byFunction[fid] takes precedence over default."""
    return (targets.get("byFunction") or {}).get(function_id, targets["default"])


# --- guidance.ts ---------------------------------------------------------------

def priority_of(current: int, target: int, function_id: str) -> str:
    gap = target - current
    if gap >= 3:
        return "critical"
    if gap == 2:
        return "high"
    return "medium" if function_id in ("GV", "PR") else "low"


def _function_order_index(function_id: str) -> int:
    return FUNCTION_ORDER.index(function_id) if function_id in FUNCTION_ORDER else 999


def compute_gaps(assessment: dict, core: dict) -> list[dict]:
    """Gaps in the tool's semantics: skip N/A, unassessed, and current >= target."""
    targets = assessment.get("targets") or DEFAULT_TARGETS
    ratings = assessment.get("ratings") or {}
    gaps = []
    for fn in core["hierarchy"]:
        for cat in fn.get("categories", []):
            for sub in cat.get("subcategories", []):
                rt = ratings.get(sub["id"])
                if not rt or rt.get("na") or rt.get("tier") is None:
                    continue
                current = rt["tier"]
                target = resolve_target(fn["id"], targets)
                if current >= target:
                    continue
                gaps.append({
                    "subcategoryId": sub["id"],
                    "subcategoryText": sub.get("text", ""),
                    "functionId": fn["id"],
                    "functionName": fn.get("name", fn["id"]),
                    "categoryId": cat["id"],
                    "categoryName": cat.get("name", cat["id"]),
                    "currentTier": current,
                    "targetTier": target,
                    "priority": priority_of(current, target, fn["id"]),
                    "note": rt.get("note"),
                })
    gaps.sort(key=lambda g: (PRIORITY_RANK[g["priority"]],
                             _function_order_index(g["functionId"]),
                             g["subcategoryId"]))
    return gaps


CSV_HEADER = ("subcategory_id,function_id,category_id,current_tier,target_tier,"
              "priority,subcategory_text,note")


def _q(v) -> str:
    """The tool's quoting rule, transcribed: quote only if it contains " , CR or LF."""
    s = "" if v is None else str(v)
    return '"' + s.replace('"', '""') + '"' if re.search(r'[",\n\r]', s) else s


def export_gaps_csv(gaps: list[dict]) -> str:
    """Byte-for-byte reproduction of the web tool's exportGapsCsv.

    Uses manual quoting rather than the csv module: Python's writer quotes and
    line-terminates on its own rules, which differ from the TypeScript original.
    Parity is the whole point of this function, so the original's rules win.
    """
    rows = [",".join(_q(v) for v in (
        g["subcategoryId"], g["functionId"], g["categoryId"], g["currentTier"],
        g["targetTier"], g["priority"], g["subcategoryText"], g.get("note") or "",
    )) for g in gaps]
    return "\n".join([CSV_HEADER] + rows) + ("\n" if rows else "")


# --- Migration: .csfa -> .csfp -------------------------------------------------

def convert_to_csfp(assessment: dict, core: dict, ts: str, scale_max: int = 3) -> dict:
    """Turn a web-tool assessment into a native Profile.

    The tool rates 1-4 with no 0; the native default scale is 0-3. Rather than
    silently rescale — which would change what every rating asserts — the converted
    Profile adopts a 0-4 scale so each rating keeps its original value and meaning.
    The labels travel with it, carrying the non-doctrine caveat in their name.

    Function-level targets are expanded to per-Subcategory targets, which is what
    the native model tracks. That is a genuine gain in resolution, not a
    reinterpretation: every Subcategory in a Function simply starts at that
    Function's target and can then be tuned individually.
    """
    index = pa.index_subcategories(core)
    targets = assessment.get("targets") or DEFAULT_TARGETS
    ratings = assessment.get("ratings") or {}
    meta = assessment.get("meta") or {}

    settings = copy.deepcopy(pa.DEFAULT_SETTINGS)
    settings["scale"] = {
        "type": "ordinal", "min": 0, "max": 4,
        "labels": {str(k): v for k, v in TIER_NAMES.items()},
    }
    settings["functionWeights"] = {fid: 1 for fid in pa.function_ids(core)}

    assessments = []
    for sid, meta_sub in index.items():
        rt = ratings.get(sid) or {}
        na = bool(rt.get("na"))
        assessments.append({
            "subcategoryId": sid,
            "applicability": "not-applicable" if na else "in-scope",
            "current": None if na else rt.get("tier"),
            "target": None if na else resolve_target(meta_sub["functionId"], targets),
            "priority": "medium",
            "status": "not-started",
            "notes": rt.get("note") or "",
            "evidenceRefs": [],
            "lastReviewed": (meta.get("assessedAt") or ts[:10]) if rt.get("tier") is not None else None,
        })

    # A converted assessment IS a source: it happened on a date, a named assessor ran
    # it, and it bears on exactly the Subcategories it rated. Recording it as intake
    # means every imported rating answers "how do you know?" from day one, instead of
    # arriving as anonymous numbers the CLI would have refused to write.
    imported_by = meta.get("assessor") or "csf-assessment import"
    raw_assessed_at = meta.get("assessedAt")
    assessed_at = str(raw_assessed_at).strip() if raw_assessed_at else None
    if assessed_at and pa._is_iso_date(assessed_at):
        source_date = assessed_at
    else:
        created_at = assessment.get("createdAt")
        candidate = str(created_at)[:10] if created_at else None
        source_date = candidate if candidate and pa._is_iso_date(candidate) else ts[:10]

    rated = [x["subcategoryId"] for x in assessments if x["current"] is not None]
    intake = []
    if rated:
        intake_id = "in-0001"
        intake.append({
            "id": intake_id,
            "label": f"csf-assessment import ({meta.get('clientName') or 'Imported Profile'})",
            "sourceDate": source_date,
            "recordedAt": ts[:10],
            "subjects": list(rated),
            "recordedBy": imported_by,
        })
        rated_set = set(rated)
        for x in assessments:
            if x["subcategoryId"] in rated_set:
                x["confirmedAt"], x["confirmedBy"], x["source"] = source_date, imported_by, intake_id
            else:
                x["confirmedAt"] = x["confirmedBy"] = x["source"] = None
    else:
        for x in assessments:
            x["confirmedAt"] = x["confirmedBy"] = x["source"] = None

    name = meta.get("clientName") or "Imported Profile"
    store = {
        "schemaVersion": pa.SCHEMA_VERSION,
        "profile": {
            "id": re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-"),
            "name": name,
            "frameworkRef": pa.FRAMEWORK_REF,
            "scope": {
                "purpose": meta.get("scopeNote", ""),
                "orgUnits": [], "threatTypes": [],
                "owner": meta.get("assessor", ""),
                "assumptions": "Imported from a csf-assessment .csfa file. Ratings use the "
                               "tool's 0-4 scale, whose 1-4 labels borrow NIST Tier vocabulary "
                               "and are NOT CSF Implementation Tiers.",
            },
            "tier": {"overall": None, "byFunction": {fid: None for fid in pa.function_ids(core)}},
            "settings": settings,
            "created": assessment.get("createdAt") or ts,
            "updated": ts,
        },
        "assessments": assessments,
        "history": [], "snapshots": [], "actionItems": [],
        "intake": intake,
    }
    pa.append_history(store, "profile-imported",
                      rationale=f"Imported from csf-assessment .csfa "
                                f"(assessed {meta.get('assessedAt') or 'date unknown'}, "
                                f"targets preset '{targets.get('preset')}').",
                      actor=meta.get("assessor"), ts=ts)
    if intake:
        pa.append_history(store, "intake-recorded", intakeId="in-0001", ts=ts,
                          actor=imported_by,
                          rationale=f"Imported from a csf-assessment export; "
                                    f"{len(rated)} ratings attributed to that assessment.")
    return store


# --- CLI -----------------------------------------------------------------------

def _cmd_gaps(args):
    pos, opt = pa.parse_flags(args)
    if not pos:
        raise ValueError("usage: gaps <file.csfa> [--out gaps.csv]")
    core = pa.load_core()
    csv_text = export_gaps_csv(compute_gaps(load_csfa(pos[0]), core))
    dest = pa._s(opt.get("out")) if isinstance(opt.get("out"), (str, list)) else None
    if dest:
        with open(dest, "w", newline="", encoding="utf-8") as fh:
            fh.write(csv_text)
        print(f"Wrote {dest} — {csv_text.count(chr(10)) - 1} gap rows.")
    else:
        sys.stdout.write(csv_text)
    return 0


def _cmd_convert(args):
    pos, opt = pa.parse_flags(args)
    if not pos or "out" not in opt:
        raise ValueError("usage: convert <file.csfa> --out <file.csfp>")
    ts = pa._s(opt.get("ts")) if isinstance(opt.get("ts"), (str, list)) else pa._now()
    core = pa.load_core()
    store = convert_to_csfp(load_csfa(pos[0]), core, ts)
    out = pa._s(opt["out"])
    pa.save_store(store, out, ts)

    scoped = [a for a in store["assessments"] if a["applicability"] == "in-scope"]
    rated = [a for a in scoped if a["current"] is not None]
    print(f"Converted {pos[0]} -> {out}")
    print(f"  {len(store['assessments'])} Subcategories · {len(rated)} rated · "
          f"{len(store['assessments']) - len(scoped)} not applicable")
    print(f"  Scale 0-4 preserved from the source; Function targets expanded to per-Subcategory.")
    print(f"  Next: profile_analysis.py analyze {out}")
    return 0


def _cmd_self_test(_args):
    """Parity against the golden fixtures shipped in examples/."""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    csfa = os.path.join(root, "examples", "acme-manufacturing.csfa")
    golden = os.path.join(root, "examples", "acme-manufacturing-gaps.csv")
    failures, checks = [], 0

    def eq(got, want, label):
        nonlocal checks
        checks += 1
        if got != want:
            failures.append(f"{label}: expected {want!r}, got {got!r}")

    def ok(cond, label):
        nonlocal checks
        checks += 1
        if not cond:
            failures.append(label)

    core = pa.load_core()
    a = load_csfa(csfa)
    eq(a["schemaVersion"], 1, "schemaVersion")
    eq(a["frameworkId"], "csf-2.0", "frameworkId")
    eq(len(a["ratings"]), 106, "ratings count")
    eq(sum(1 for r in a["ratings"].values() if r.get("na")), 2, "N/A count")
    eq(sum(1 for r in a["ratings"].values() if r.get("note")), 15, "notes count")

    # targets.ts
    eq(resolve_target("GV", a["targets"]), 4, "GV target from byFunction")
    eq(resolve_target("DE", a["targets"]), 3, "DE target falls through to default")
    eq(TARGET_PRESETS["adaptive"]["default"], 4, "adaptive preset")
    eq(TARGET_PRESETS["repeatable"]["default"], 3, "repeatable preset")
    eq(TARGET_PRESETS["governance-first"]["byFunction"], {"GV": 3, "PR": 3}, "governance-first preset")

    # priorityOf
    eq(priority_of(1, 4, "GV"), "critical", "gap 3 -> critical")
    eq(priority_of(2, 4, "DE"), "high", "gap 2 -> high")
    eq(priority_of(3, 4, "GV"), "medium", "gap 1 in GV -> medium")
    eq(priority_of(3, 4, "PR"), "medium", "gap 1 in PR -> medium")
    eq(priority_of(3, 4, "RC"), "low", "gap 1 elsewhere -> low")
    eq(priority_of(0, 4, "GV"), "critical", "gap 4 (0 level) -> critical")

    gaps = compute_gaps(a, core)
    ok(all(g["currentTier"] < g["targetTier"] for g in gaps), "every row is a real gap")
    ok(not any((a["ratings"][g["subcategoryId"]].get("na")) for g in gaps), "N/A excluded")
    ranks = [(PRIORITY_RANK[g["priority"]], _function_order_index(g["functionId"]),
              g["subcategoryId"]) for g in gaps]
    eq(ranks, sorted(ranks), "sort order: priority -> function -> id")

    # THE GATE: byte-identical CSV.
    produced = export_gaps_csv(gaps)
    expected = open(golden, encoding="utf-8", newline="").read()
    eq(len(produced), len(expected), "CSV byte length")
    if produced != expected:
        for i, (p, e) in enumerate(zip(produced.splitlines(), expected.splitlines()), 1):
            if p != e:
                failures.append(f"CSV line {i} differs:\n      got:  {p[:120]}\n      want: {e[:120]}")
                break
    ok(produced == expected, "gaps CSV is byte-identical to the golden file")
    checks += 1

    # Migration sanity
    store = convert_to_csfp(a, core, "2026-06-18T00:00:00Z")
    eq(len(store["assessments"]), 106, "converted Profile tracks 106 Subcategories")
    eq(sum(1 for x in store["assessments"] if x["applicability"] == "not-applicable"), 2,
       "N/A carried across as applicability")
    eq(store["profile"]["settings"]["scale"]["max"], 4, "converted Profile keeps the 0-4 scale")
    eq(pa.check_store(store, pa.index_subcategories(core)), [], "converted Profile validates")
    byfn = {}
    for x in store["assessments"]:
        if x["target"] is not None:
            byfn.setdefault(pa.index_subcategories(core)[x["subcategoryId"]]["functionId"], set()).add(x["target"])
    eq(byfn.get("GV"), {4}, "GV Subcategory targets expanded from the Function target")
    eq(byfn.get("DE"), {3}, "DE Subcategory targets expanded from the default")

    # --- Conversion lands as v2 with the source assessment as its own intake record ---
    conv = convert_to_csfp(a, core, ts="2026-07-27T00:00:00Z")
    eq(conv["schemaVersion"], "2.0", "convert writes schema 2.0")
    eq(len(conv["intake"]), 1, "convert synthesises one intake record for the source file")
    rec = conv["intake"][0]
    eq(rec["id"], "in-0001", "the synthesised record is in-0001")
    ok("csf-assessment" in rec["label"], "the label names where the ratings came from")
    ok(pa._is_iso_date(rec["sourceDate"]), "sourceDate is a zero-padded ISO date")
    ok(pa._is_iso_date(rec["recordedAt"]), "recordedAt is a zero-padded ISO date")
    rated = sorted(x["subcategoryId"] for x in conv["assessments"] if x["current"] is not None)
    eq(sorted(rec["subjects"]), rated,
       "the record bears on exactly the Subcategories the source rated")
    ok(len(rated) > 0, "the fixture actually rates something, so this test means something")

    # The source's conversion loop is a single membership test plus an unconditional
    # triple-assignment applied uniformly across all 106 rows — there is no per-row
    # branching for row 12 to pass while row 87 fails. So assert the aggregate: four
    # list-valued checks mirroring the source's two branches, not 106 near-identical
    # ones. eq(bad, [], ...) still prints the offending ids if the property ever breaks.
    rated_rows = [x for x in conv["assessments"] if x["current"] is not None]
    unrated_rows = [x for x in conv["assessments"] if x["current"] is None]
    eq([x["subcategoryId"] for x in rated_rows if x["source"] != "in-0001"], [],
       "every rated row is attributed to the import")
    eq([x["subcategoryId"] for x in rated_rows if not x["confirmedBy"]], [],
       "every rated row names a confirmer")
    eq([x["subcategoryId"] for x in rated_rows if not pa._is_iso_date(x["confirmedAt"])], [],
       "every rated row carries a zero-padded ISO confirmation date")
    eq([x["subcategoryId"] for x in unrated_rows
        if x["source"] or x["confirmedBy"] or x["confirmedAt"]], [],
       "no unrated or not-applicable row carries attribution")

    ev = [e for e in conv["history"] if e.get("type") == "intake-recorded"]
    eq(len(ev), 1, "the import appends exactly one intake-recorded event")
    eq(ev[0].get("intakeId"), "in-0001", "the event names the intake id")

    # The converted Profile must survive the engine's own validation, which now
    # checks date shape on both attribution and intake.
    eq(pa.check_store(conv, pa.index_subcategories(core)), [],
       "a converted Profile passes check_store with no problems")

    # A .csfa with no ratings at all must not fabricate an empty source.
    empty = convert_to_csfp({"meta": {"clientName": "Empty Co"}, "ratings": {}},
                            core, ts="2026-07-27T00:00:00Z")
    eq(empty["intake"], [], "an assessment that rated nothing records no source")
    ok(all(x["source"] is None for x in empty["assessments"]),
       "and attributes nothing")

    # The fixture always supplies meta.assessor, so the fallback literal is never
    # exercised there. Cover it directly: a rated Subcategory with no assessor named.
    no_assessor = convert_to_csfp(
        {"meta": {"clientName": "No Assessor Co"},
         "ratings": {"GV.OC-01": {"tier": 2, "na": False}}},
        core, ts="2026-07-27T00:00:00Z")
    eq(no_assessor["intake"][0]["recordedBy"], "csf-assessment import",
       "with no assessor named, the intake record falls back to the literal")
    rated_row = next(x for x in no_assessor["assessments"] if x["subcategoryId"] == "GV.OC-01")
    eq(rated_row["confirmedBy"], "csf-assessment import",
       "and the rated row's confirmedBy falls back to the same literal")

    print(f"csfa-compat self-test: {checks - len(failures)}/{checks} checks passed")
    if failures:
        print("\nFAILED:", file=sys.stderr)
        for f in failures:
            print(f"  - {f}", file=sys.stderr)
        return 1
    return 0


COMMANDS = {"gaps": _cmd_gaps, "convert": _cmd_convert, "self-test": _cmd_self_test}


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
