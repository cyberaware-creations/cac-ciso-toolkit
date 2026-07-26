#!/usr/bin/env python3
"""
score_register.py — deterministic NIST-aligned scoring for the risk-register skill.

Ported verbatim from the Limen Labs web engine (lib/risk/scoring.ts, summary.ts,
import.ts) so a skill run bands risks identically to the original tool instead of
eyeballing thresholds. Standard library only — no dependencies.

NIST anchors:
  - Exposure = Likelihood x Impact   (SP 800-30 Rev. 1, qualitative model)
  - Bands scale with matrix size     (documented per size below)
  - Appetite = worst band still acceptable  (CSF 2.0 GV.RM)

Subcommands:
  score        <register.rr> [--json]   Score a register; print summary (+ optional JSON).
  import-gaps  <gaps.csv> [--into r.rr]  Map a CSF gap CSV to candidate risks (dedupe if --into).
  self-test                              Assert the engine against the web repo's test cases.

Mutations (each appends an append-only history event and writes a schema-valid file):
  add          <register.rr> --title ... --il L --ii I --rl L --ri I [--theme ID] [--why ...]
  set-score    <register.rr> <id> [--inherent L I] [--residual L I] --why ...
  accept       <register.rr> <id> --approver ... --justification ... --revalidate DATE
  set-status   <register.rr> <id> <open|in-treatment|monitoring|closed> [--why ...]
  add-theme    <register.rr> --id ID --name 'Display Name' [--description ...]
  set-theme    <register.rr> <risk-id> <theme-id|none> [--why ...]
  snapshot     <register.rr> --label 'Q3 2026 Board Review' [--note ...]
  export-csv   <register.rr> [--out out.csv]

Usage:
  python3 score_register.py score client-register.rr
  python3 score_register.py score client-register.rr --json > scored.json
  python3 score_register.py import-gaps acme-gaps.csv --into client-register.rr
  python3 score_register.py self-test
"""

from __future__ import annotations

import csv
import io
import json
import os
import re
import sys
from datetime import datetime, timezone
from typing import Any

# Behave like a normal Unix filter: on a closed pipe (e.g. `... | head`), exit
# quietly instead of dumping a BrokenPipeError traceback.
try:
    import signal
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)
except (ImportError, AttributeError, ValueError):
    pass

# --- Constants (harvested from scoring.ts) -----------------------------------

SCHEMA_VERSION = 2          # current write version
SUPPORTED_SCHEMA = {1, 2}   # v1 files load and are normalized to v2 shape in memory
BAND_ORDER = ["low", "medium", "high", "critical"]

# Inclusive lower bound for each band, per matrix size. First band (scanning
# critical -> low) whose threshold <= exposure wins. Values match the 800-30
# banding used in the tool; 5x5 is the standard 1..25 spread.
BAND_THRESHOLDS = {
    5: {"low": 1, "medium": 5, "high": 10, "critical": 15},
    4: {"low": 1, "medium": 4, "high": 8, "critical": 12},
    3: {"low": 1, "medium": 3, "high": 5, "critical": 7},
}

RATING_LABELS = {
    5: {1: "Very Low", 2: "Low", 3: "Moderate", 4: "High", 5: "Very High"},
    4: {1: "Low", 2: "Moderate", 3: "High", 4: "Very High"},
    3: {1: "Low", 2: "Moderate", 3: "High"},
}

# Seed inherent likelihood == impact from a CSF gap's priority (import.ts).
PRIORITY_SEED = {"critical": 5, "high": 4, "medium": 3, "low": 2}

# --- Core scoring (scoring.ts) -----------------------------------------------


def exposure(likelihood: int, impact: int) -> int:
    return likelihood * impact


def band(exposure_value: int, size: int) -> str:
    thresholds = BAND_THRESHOLDS[size]
    for b in reversed(BAND_ORDER):  # critical -> low
        if exposure_value >= thresholds[b]:
            return b
    return "low"


def rating_label(level: int, size: int) -> str:
    return RATING_LABELS[size].get(level, str(level))


def over_appetite(residual_exposure: int, size: int, appetite: str) -> bool:
    return BAND_ORDER.index(band(residual_exposure, size)) > BAND_ORDER.index(appetite)


# --- Summary (summary.ts) ----------------------------------------------------


def summarize(risks: list[dict], size: int, appetite: str) -> dict:
    by_band = {"low": 0, "medium": 0, "high": 0, "critical": 0}
    closed = 0
    over = 0
    for r in risks:
        res_exp = exposure(r["residual"]["likelihood"], r["residual"]["impact"])
        by_band[band(res_exp, size)] += 1
        if r.get("status") == "closed":
            closed += 1
        if over_appetite(res_exp, size, appetite):
            over += 1
    # Stable descending sort by residual exposure, capped at 5 (matches JS toSorted).
    top = sorted(
        risks,
        key=lambda r: exposure(r["residual"]["likelihood"], r["residual"]["impact"]),
        reverse=True,
    )[:5]
    return {
        "total": len(risks),
        "closed": closed,
        "overAppetite": over,
        "byBand": by_band,
        "topByResidual": [r["id"] for r in top],
    }


# --- CSF gap import (import.ts) ----------------------------------------------

REQUIRED_GAP_COLS = [
    "subcategory_id", "function_id", "category_id", "current_tier",
    "target_tier", "priority", "subcategory_text", "note",
]


def parse_gaps_csv(text: str) -> list[dict]:
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise ValueError("Empty CSV.")
    missing = [c for c in REQUIRED_GAP_COLS if c not in reader.fieldnames]
    if missing:
        raise ValueError(f"Missing required header column(s): {', '.join(missing)}")
    return [row for row in reader if any((v or "").strip() for v in row.values())]


def empty_risk(risk_id: str) -> dict:
    return {
        "id": risk_id, "title": "", "description": "", "category": "", "owner": "",
        "inherent": {"likelihood": 1, "impact": 1},
        "response": {"type": "mitigate", "description": ""},
        "residual": {"likelihood": 1, "impact": 1},
        "status": "open",
    }


def next_risk_id(risks: list[dict]) -> str:
    max_n = 0
    for r in risks:
        rid = r.get("id", "")
        if rid.startswith("R-") and rid[2:].isdigit():
            max_n = max(max_n, int(rid[2:]))
    return f"R-{max_n + 1:03d}"


def gap_row_to_risk(row: dict, risk_id: str) -> dict:
    level = PRIORITY_SEED.get((row["priority"] or "").lower(), 3)
    risk = empty_risk(risk_id)
    risk["title"] = f"{row['subcategory_id']}: {row['subcategory_text']}"[:140]
    risk["description"] = f"CSF gap — {row['subcategory_text']}"
    risk["category"] = row["function_id"]
    risk["csfSubcategoryId"] = row["subcategory_id"]
    risk["inherent"] = {"likelihood": level, "impact": level}
    risk["residual"] = {"likelihood": level, "impact": level}
    note_parts = [f"Tier {row['current_tier']} → {row['target_tier']}", f"priority: {row['priority']}"]
    if row["note"]:
        note_parts.append(row["note"])
    risk["notes"] = " · ".join(note_parts)
    return risk


def merge_import(existing: list[dict], candidates: list[dict]) -> dict:
    risks = [dict(r) for r in existing]
    added = updated = 0
    for cand in candidates:
        match = None
        if cand.get("csfSubcategoryId"):
            match = next((r for r in risks if r.get("csfSubcategoryId") == cand["csfSubcategoryId"]), None)
        if match:
            match["title"] = cand["title"]
            match["description"] = cand["description"]
            match["category"] = cand["category"]
            match["notes"] = cand.get("notes")
            updated += 1
        else:
            new = dict(cand)
            new["id"] = next_risk_id(risks)
            risks.append(new)
            added += 1
    return {"risks": risks, "added": added, "updated": updated}


# --- Register I/O (storage.ts) -----------------------------------------------


def load_register(path: str) -> dict:
    with open(path, encoding="utf-8") as fh:
        try:
            obj = json.load(fh)
        except json.JSONDecodeError as exc:
            raise ValueError("Not a valid risk register file (invalid JSON).") from exc
    if obj.get("schemaVersion") not in SUPPORTED_SCHEMA:
        raise ValueError(f"Unsupported schema version (supported: {sorted(SUPPORTED_SCHEMA)}).")
    if not isinstance(obj.get("risks"), list):
        raise ValueError("Invalid register: missing risks array.")
    obj["settings"] = {"matrixSize": 5, "appetite": "medium", **obj.get("settings", {})}
    if obj["settings"]["matrixSize"] not in BAND_THRESHOLDS:
        raise ValueError(f"Invalid matrixSize {obj['settings']['matrixSize']!r} (must be 3, 4, or 5).")
    if obj["settings"]["appetite"] not in BAND_ORDER:
        raise ValueError(f"Invalid appetite {obj['settings']['appetite']!r} (must be one of {BAND_ORDER}).")
    obj["meta"] = {"clientName": "", "assessor": "", "scopeNote": "", "appetiteStatement": "",
                   **obj.get("meta", {})}
    # Normalize v1 → v2 shape in memory (no data loss; write path stamps schemaVersion 2).
    obj.setdefault("themes", [])
    obj.setdefault("history", [])
    obj.setdefault("snapshots", [])
    for r in obj["risks"]:
        r.setdefault("theme", None)
        r.setdefault("acceptance", None)
    return obj


def score_register(reg: dict) -> dict:
    size = reg["settings"]["matrixSize"]
    appetite = reg["settings"]["appetite"]
    scored_risks = []
    for r in reg["risks"]:
        inh = exposure(r["inherent"]["likelihood"], r["inherent"]["impact"])
        res = exposure(r["residual"]["likelihood"], r["residual"]["impact"])
        # A score can sit above the matrix (e.g. a 5-level risk after a downshift to 3x3).
        # It is still banded and counted, but flagged so renderers can skip it on the heat
        # matrix (per dashboards.md / report-layout.md) rather than re-deriving that themselves.
        out_of_range = max(r["inherent"]["likelihood"], r["inherent"]["impact"],
                           r["residual"]["likelihood"], r["residual"]["impact"]) > size
        scored_risks.append({
            **r,
            "inherentExposure": inh,
            "inherentBand": band(inh, size),
            "residualExposure": res,
            "residualBand": band(res, size),
            "overAppetite": over_appetite(res, size, appetite),
            "outOfRange": out_of_range,
        })
    return {
        "meta": reg["meta"],
        "settings": reg["settings"],
        "themes": reg.get("themes", []),
        "summary": summarize(reg["risks"], size, appetite),
        "risks": scored_risks,
    }


# --- CLI ---------------------------------------------------------------------


def _cmd_score(args: list[str]) -> int:
    as_json = "--json" in args
    paths = [a for a in args if not a.startswith("--")]
    if not paths:
        print("usage: score_register.py score <register.rr> [--json]", file=sys.stderr)
        return 2
    scored = score_register(load_register(paths[0]))
    if as_json:
        print(json.dumps(scored, indent=2))
        return 0
    s = scored["summary"]
    m, st = scored["meta"], scored["settings"]
    print(f"Register: {m['clientName'] or '(unnamed)'}   Assessor: {m['assessor'] or '—'}")
    print(f"Matrix: {st['matrixSize']}x{st['matrixSize']}   Appetite: {st['appetite']}")
    print(f"Total: {s['total']}   Closed: {s['closed']}   Over appetite: {s['overAppetite']}")
    print(f"Residual band mix — Low {s['byBand']['low']} · Medium {s['byBand']['medium']} · "
          f"High {s['byBand']['high']} · Critical {s['byBand']['critical']}")
    print("\nID     Residual  Band       Over  Title")
    for r in scored["risks"]:
        flag = "⚠" if r["overAppetite"] else " "
        print(f"{r['id']:<6} {r['residualExposure']:>7}  {r['residualBand']:<9}  {flag:<4}  {r['title'][:54]}")
    return 0


def _cmd_import_gaps(args: list[str]) -> int:
    into = None
    if "--into" in args:
        into = args[args.index("--into") + 1]
    paths = [a for a in args if not a.startswith("--") and a != into]
    if not paths:
        print("usage: score_register.py import-gaps <gaps.csv> [--into <register.rr>]", file=sys.stderr)
        return 2
    do_write = "--write" in args
    with open(paths[0], encoding="utf-8") as fh:
        rows = parse_gaps_csv(fh.read())
    existing = load_register(into)["risks"] if into else []
    candidates = [gap_row_to_risk(row, f"R-{i + 1:03d}") for i, row in enumerate(rows)]
    result = merge_import(existing, candidates)
    if do_write and into:
        reg = load_register(into)
        reg["risks"] = result["risks"]
        _append_event(reg, "import-merged",
                      rationale=f"{result['added']} added, {result['updated']} updated from {os.path.basename(paths[0])}")
        save_register(reg, into)
        print(f"Wrote {into}: {result['added']} added, {result['updated']} updated", file=sys.stderr)
    else:
        print(json.dumps(result, indent=2))
        tail = " (preview; add --write to apply)" if into else ""
        print(f"\n# {result['added']} added, {result['updated']} updated{tail}", file=sys.stderr)
    return 0


def _cmd_self_test(_: list[str]) -> int:
    checks: list[tuple[str, Any, Any]] = []

    def eq(name, got, want):
        checks.append((name, got, want))

    # exposure / band (scoring.test.ts)
    eq("exposure(4,5)", exposure(4, 5), 20)
    eq("band(4,5)", band(4, 5), "low")
    eq("band(9,5)", band(9, 5), "medium")
    eq("band(12,5)", band(12, 5), "high")
    eq("band(25,5)", band(25, 5), "critical")
    eq("band(5,5)", band(5, 5), "medium")
    eq("band(10,5)", band(10, 5), "high")
    eq("band(15,5)", band(15, 5), "critical")
    eq("band(3,4)", band(3, 4), "low")
    eq("band(4,4)", band(4, 4), "medium")
    eq("band(8,4)", band(8, 4), "high")
    eq("band(12,4)", band(12, 4), "critical")
    eq("band(2,3)", band(2, 3), "low")
    eq("band(4,3)", band(4, 3), "medium")
    eq("band(6,3)", band(6, 3), "high")
    eq("band(9,3)", band(9, 3), "critical")
    # rating labels
    eq("ratingLabel(1,5)", rating_label(1, 5), "Very Low")
    eq("ratingLabel(5,5)", rating_label(5, 5), "Very High")
    eq("ratingLabel(1,3)", rating_label(1, 3), "Low")
    eq("ratingLabel(3,3)", rating_label(3, 3), "High")
    eq("ratingLabel(1,4)", rating_label(1, 4), "Low")
    eq("ratingLabel(4,4)", rating_label(4, 4), "Very High")
    # overAppetite
    eq("overAppetite(20,5,medium)", over_appetite(20, 5, "medium"), True)
    eq("overAppetite(4,5,medium)", over_appetite(4, 5, "medium"), False)
    eq("overAppetite(9,5,medium)", over_appetite(9, 5, "medium"), False)
    eq("BAND_ORDER", BAND_ORDER, ["low", "medium", "high", "critical"])

    # summarize (summary.test.ts)
    a = {**empty_risk("R-001"), "residual": {"likelihood": 5, "impact": 5}, "status": "open"}
    b = {**empty_risk("R-002"), "residual": {"likelihood": 1, "impact": 1}, "status": "closed"}
    s = summarize([a, b], 5, "medium")
    eq("summary.total", s["total"], 2)
    eq("summary.closed", s["closed"], 1)
    eq("summary.overAppetite", s["overAppetite"], 1)
    eq("summary.byBand.critical", s["byBand"]["critical"], 1)
    eq("summary.byBand.low", s["byBand"]["low"], 1)

    specs = [("R-001", 1, 4), ("R-002", 5, 5), ("R-003", 3, 3),
             ("R-004", 4, 5), ("R-005", 4, 4), ("R-006", 3, 4)]
    risks = [{**empty_risk(i), "residual": {"likelihood": l, "impact": im}} for i, l, im in specs]
    top = summarize(risks, 5, "medium")["topByResidual"]
    eq("topByResidual", top, ["R-002", "R-004", "R-005", "R-006", "R-003"])

    # import priority seeding + dedupe (import.test.ts semantics)
    eq("PRIORITY_SEED[critical]", PRIORITY_SEED["critical"], 5)
    eq("PRIORITY_SEED[low]", PRIORITY_SEED["low"], 2)

    failures = [(n, g, w) for (n, g, w) in checks if g != w]
    for n, g, w in checks:
        status = "ok " if (g == w) else "FAIL"
        if g != w:
            print(f"[{status}] {n}: got {g!r} want {w!r}")
    print(f"\n{len(checks) - len(failures)}/{len(checks)} checks passed.")
    if failures:
        print(f"{len(failures)} FAILED — engine does NOT match the web tool.", file=sys.stderr)
        return 1
    print("Parity confirmed: scoring matches the Limen Labs web engine.")
    return 0


# --- Persistence (write-back, append-only history, snapshots) ----------------

STATUSES = {"open", "in-treatment", "monitoring", "closed"}
RESPONSES = {"accept", "transfer", "mitigate", "avoid"}


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _s(v):
    """Coerce a possibly-multi-token flag value back to a string."""
    return " ".join(v) if isinstance(v, list) else v


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


def save_register(reg: dict, path: str) -> None:
    """Write the register back, stamping schemaVersion 2 and updatedAt. History is never
    rewritten here — callers append to reg['history'] before saving."""
    reg["schemaVersion"] = SCHEMA_VERSION
    reg.setdefault("createdAt", _now())
    reg["updatedAt"] = _now()
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(reg, fh, indent=2, ensure_ascii=False)


def _append_event(reg, etype, riskId=None, field=None, frm=None, to=None, rationale=None):
    ev = {"ts": _now(), "actor": reg["meta"].get("assessor") or "unknown", "type": etype}
    if riskId is not None:
        ev["riskId"] = riskId
    if field is not None:
        ev["field"] = field
    if frm is not None:
        ev["from"] = frm
    if to is not None:
        ev["to"] = to
    if rationale:
        ev["rationale"] = _s(rationale)
    reg.setdefault("history", []).append(ev)


def _find(reg, rid):
    for r in reg["risks"]:
        if r["id"] == rid:
            return r
    raise ValueError(f"No risk with id {rid!r}.")


def _lvl(v, size, label):
    try:
        n = int(_s(v))
    except (TypeError, ValueError):
        raise ValueError(f"{label} must be an integer 1..{size}.")
    if not 1 <= n <= size:
        raise ValueError(f"{label} {n} out of range 1..{size}.")
    return n


def _cmd_add(args):
    pos, opt = parse_flags(args)
    if not pos:
        raise ValueError("usage: add <register.rr> --title '...' --il L --ii I --rl L --ri I "
                         "[--category ..] [--owner ..] [--theme ..] [--response mitigate] "
                         "[--response-desc ..] [--review DATE] [--csf ID] [--notes ..] [--why ..]")
    path = pos[0]
    reg = load_register(path)
    size = reg["settings"]["matrixSize"]
    for req in ("title", "il", "ii", "rl", "ri"):
        if req not in opt:
            raise ValueError(f"add: missing --{req}")
    rtype = _s(opt.get("response", "mitigate"))
    if rtype not in RESPONSES:
        raise ValueError(f"--response must be one of {sorted(RESPONSES)}")
    risk = {
        "id": next_risk_id(reg["risks"]), "title": _s(opt["title"]),
        "description": _s(opt.get("description", opt.get("desc", ""))),
        "category": _s(opt.get("category", "")), "theme": _s(opt["theme"]) if "theme" in opt else None,
        "owner": _s(opt.get("owner", "")),
        "inherent": {"likelihood": _lvl(opt["il"], size, "--il"), "impact": _lvl(opt["ii"], size, "--ii")},
        "response": {"type": rtype, "description": _s(opt.get("response-desc", ""))},
        "residual": {"likelihood": _lvl(opt["rl"], size, "--rl"), "impact": _lvl(opt["ri"], size, "--ri")},
        "status": "open", "acceptance": None,
    }
    if "cost" in opt:
        risk["response"]["cost"] = int(_s(opt["cost"]))
    if "review" in opt:
        risk["reviewDate"] = _s(opt["review"])
    if "csf" in opt:
        risk["csfSubcategoryId"] = _s(opt["csf"])
    if "notes" in opt:
        risk["notes"] = _s(opt["notes"])
    if risk["theme"] and not any(t.get("id") == risk["theme"] for t in reg["themes"]):
        print(f"warning: theme {risk['theme']!r} is not defined in this register; "
              f"it will roll up as Unclassified. Define it with: add-theme", file=sys.stderr)
    reg["risks"].append(risk)
    _append_event(reg, "risk-added", riskId=risk["id"], rationale=opt.get("why"))
    save_register(reg, path)
    res = exposure(risk["residual"]["likelihood"], risk["residual"]["impact"])
    over = " (over appetite)" if over_appetite(res, size, reg["settings"]["appetite"]) else ""
    print(f"Added {risk['id']}: residual {res} {band(res, size)}{over}")
    return 0


def _cmd_add_theme(args):
    pos, opt = parse_flags(args)
    if not pos or "id" not in opt or "name" not in opt:
        raise ValueError("usage: add-theme <register.rr> --id <theme-id> --name 'Display Name' "
                         "[--description '...'] [--why '...']")
    path = pos[0]
    reg = load_register(path)
    tid = _s(opt["id"])
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", tid):
        raise ValueError(f"--id {tid!r} must be lowercase alphanumeric with hyphens (e.g. 'third-party').")
    if any(t.get("id") == tid for t in reg["themes"]):
        raise ValueError(f"Theme {tid!r} already exists.")
    theme = {"id": tid, "name": _s(opt["name"]), "description": _s(opt.get("description", ""))}
    reg["themes"].append(theme)
    _append_event(reg, "theme-changed", field="themes", to=tid,
                  rationale=opt.get("why") or f"Theme '{theme['name']}' added")
    save_register(reg, path)
    print(f"Added theme {tid}: {theme['name']} ({len(reg['themes'])} themes)")
    return 0


def _cmd_set_theme(args):
    pos, opt = parse_flags(args)
    if len(pos) < 3:
        raise ValueError("usage: set-theme <register.rr> <risk-id> <theme-id|none> [--why '...']")
    path, rid, tid = pos[0], pos[1], pos[2]
    reg = load_register(path)
    r = _find(reg, rid)
    new = None if tid in ("none", "-", "null") else tid
    if new is not None and not any(t.get("id") == new for t in reg["themes"]):
        raise ValueError(f"No theme {new!r} in this register (add it with add-theme first).")
    frm = r.get("theme")
    r["theme"] = new
    _append_event(reg, "theme-changed", riskId=rid, field="theme", frm=frm, to=new,
                  rationale=opt.get("why"))
    save_register(reg, path)
    print(f"{rid}: theme {frm or '—'} → {new or '—'}")
    return 0


def _cmd_set_score(args):
    pos, opt = parse_flags(args)
    if len(pos) < 2:
        raise ValueError("usage: set-score <register.rr> <id> [--inherent L I] [--residual L I] --why '...'")
    reg = load_register(pos[0]); size = reg["settings"]["matrixSize"]; r = _find(reg, pos[1])
    if "why" not in opt:
        raise ValueError("set-score: --why is required (material change; the rationale is the audit trail).")
    changed = False
    for field in ("inherent", "residual"):
        if field in opt:
            vals = opt[field]
            if not isinstance(vals, list) or len(vals) != 2:
                raise ValueError(f"--{field} needs two values: L I")
            frm = dict(r[field])
            r[field] = {"likelihood": _lvl(vals[0], size, f"--{field} L"), "impact": _lvl(vals[1], size, f"--{field} I")}
            _append_event(reg, "score-changed", riskId=pos[1], field=field, frm=frm, to=r[field], rationale=opt["why"])
            changed = True
    if not changed:
        raise ValueError("set-score: provide --inherent and/or --residual.")
    save_register(reg, pos[0])
    res = exposure(r["residual"]["likelihood"], r["residual"]["impact"])
    print(f"{pos[1]} updated: residual {res} {band(res, size)}")
    return 0


def _cmd_accept(args):
    pos, opt = parse_flags(args)
    if len(pos) < 2:
        raise ValueError("usage: accept <register.rr> <id> --approver '...' --justification '...' "
                         "--revalidate DATE [--expiry DATE] [--accepted DATE] [--why '...']")
    reg = load_register(pos[0]); r = _find(reg, pos[1])
    for req in ("approver", "justification", "revalidate"):
        if req not in opt:
            raise ValueError(f"accept: missing --{req}")
    r["response"]["type"] = "accept"
    r["acceptance"] = {
        "approver": _s(opt["approver"]), "justification": _s(opt["justification"]),
        "acceptedDate": _s(opt.get("accepted", _now()[:10])),
        "expiryDate": _s(opt.get("expiry", "")), "revalidationDate": _s(opt["revalidate"]),
    }
    _append_event(reg, "risk-accepted", riskId=pos[1], rationale=opt.get("why", opt["justification"]))
    save_register(reg, pos[0])
    print(f"{pos[1]} accepted by {r['acceptance']['approver']}; re-validate by {r['acceptance']['revalidationDate']}")
    return 0


def _cmd_set_status(args):
    pos, opt = parse_flags(args)
    if len(pos) < 3:
        raise ValueError(f"usage: set-status <register.rr> <id> <{'|'.join(sorted(STATUSES))}> [--why '...']")
    if pos[2] not in STATUSES:
        raise ValueError(f"status must be one of {sorted(STATUSES)}")
    reg = load_register(pos[0]); r = _find(reg, pos[1]); frm = r["status"]; r["status"] = pos[2]
    _append_event(reg, "status-changed", riskId=pos[1], field="status", frm=frm, to=pos[2], rationale=opt.get("why"))
    save_register(reg, pos[0])
    print(f"{pos[1]}: {frm} → {pos[2]}")
    return 0


def _cmd_snapshot(args):
    pos, opt = parse_flags(args)
    if not pos or "label" not in opt:
        raise ValueError("usage: snapshot <register.rr> --label 'Q3 2026 Board Review' [--note '...']")
    reg = load_register(pos[0]); scored = score_register(reg); label = _s(opt["label"])
    snap = {
        "id": re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-"), "label": label,
        "ts": _now(), "note": _s(opt.get("note", "")),
        "data": {"settings": reg["settings"], "risks": [dict(r) for r in reg["risks"]], "summary": scored["summary"]},
    }
    reg.setdefault("snapshots", []).append(snap)
    _append_event(reg, "snapshot-created", rationale=opt.get("note") or label)
    save_register(reg, pos[0])
    print(f"Snapshot '{label}' saved ({scored['summary']['overAppetite']} over appetite, {scored['summary']['total']} risks).")
    return 0


def _cmd_export_csv(args):
    pos, opt = parse_flags(args)
    if not pos:
        raise ValueError("usage: export-csv <register.rr> [--out out.csv]")
    scored = score_register(load_register(pos[0]))
    cols = ["id", "title", "category", "theme", "owner", "inherentL", "inherentI", "inherentExposure",
            "inherentBand", "response", "cost", "residualL", "residualI", "residualExposure",
            "residualBand", "overAppetite", "status", "reviewDate", "csfSubcategoryId"]
    buf = io.StringIO(); w = csv.writer(buf); w.writerow(cols)
    for r in scored["risks"]:
        w.writerow([r["id"], r["title"], r["category"], r.get("theme") or "", r["owner"],
                    r["inherent"]["likelihood"], r["inherent"]["impact"], r["inherentExposure"], r["inherentBand"],
                    r["response"]["type"], r["response"].get("cost", ""),
                    r["residual"]["likelihood"], r["residual"]["impact"], r["residualExposure"], r["residualBand"],
                    r["overAppetite"], r["status"], r.get("reviewDate", ""), r.get("csfSubcategoryId", "")])
    out = _s(opt.get("out")) if isinstance(opt.get("out"), (str, list)) else None
    if out:
        with open(out, "w", newline="", encoding="utf-8") as fh:
            fh.write(buf.getvalue())
        print(f"Wrote {out}")
    else:
        sys.stdout.write(buf.getvalue())
    return 0


COMMANDS = {
    "score": _cmd_score, "import-gaps": _cmd_import_gaps, "self-test": _cmd_self_test,
    "add": _cmd_add, "set-score": _cmd_set_score, "accept": _cmd_accept,
    "set-status": _cmd_set_status, "snapshot": _cmd_snapshot, "export-csv": _cmd_export_csv,
    "add-theme": _cmd_add_theme, "set-theme": _cmd_set_theme,
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
