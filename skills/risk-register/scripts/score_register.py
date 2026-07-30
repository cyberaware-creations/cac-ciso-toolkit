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
  import-gaps  <gaps.csv> [--into r.rr] [--write]   Map a CSF gap CSV to candidate risks.
                                         Previews by default; --write applies the merge.
  self-test                              Assert the engine against the web repo's test cases.

Mutations (each appends an append-only history event and writes a schema-valid file):
  init         <register.rr> --client 'Name' [--assessor ..] [--matrix 5] [--appetite medium]
                                         [--scope-note ..] [--appetite-statement ..]
  add          <register.rr> --title ... --il L --ii I --rl L --ri I [--theme ID] [--why ...]
  set-text     <register.rr> <id> [--title ...] [--description ...] --why ...
                                         Reword an imported gap as a NISTIR 8286 event
                                         statement; clears `provisionalTitle`.
  set-score    <register.rr> <id> [--inherent L I] [--residual L I] --why ...
  accept       <register.rr> <id> --approver ... --justification ... --revalidate DATE
  confirm      <register.rr> <id> --why ... [--review YYYY-MM-DD]
                                         Record that a risk was reviewed and nothing
                                         changed. Resets confirmation age; changes no
                                         score, status or band.
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

import contextlib
import csv
import io
import json
import os
import re
import sys
import tempfile
from datetime import date, datetime, timezone
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

# Default themes for CSF-imported risks. Themes are the stated board-rollup axis, and
# without a mapping every imported risk lands as "Unclassified", which makes the board's
# theme tile read "Unclassified · 74 risks · worst Critical". The CSF Function is the one
# grouping the gap CSV always carries, so it is the honest default — rename or re-theme
# afterwards with add-theme / set-theme if the organisation groups risk differently.
# This is the CSF import path specifically; nothing else in the engine knows these names.
CSF_FUNCTION_THEMES = {
    "GV": "Govern", "ID": "Identify", "PR": "Protect",
    "DE": "Detect", "RS": "Respond", "RC": "Recover",
}

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
        # Additive to the ported web-engine summary. Without these a register cannot tell
        # "assessed as medium" from "never refined", and a band mix of unreviewed
        # candidates renders as a confident bar.
        #
        # `provisional` is the union — anything unreviewed in either dimension — and is
        # what the disclosure banners count. The two components are reported separately
        # because they mean different things to a reader: a provisional *title* is a
        # board-safety issue, a provisional *score* is a data-quality one.
        "provisional": sum(1 for r in risks
                           if r.get("provisionalTitle") or r.get("provisionalScore")),
        "provisionalTitle": sum(1 for r in risks if r.get("provisionalTitle")),
        "provisionalScore": sum(1 for r in risks if r.get("provisionalScore")),
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


def trunc(text: str, limit: int = 140) -> str:
    """Truncate on a word boundary with an ellipsis, never mid-word.

    A title cut mid-word ("…other third parties are understood, recorded, prioritized,
    assesse") reads as a rendering bug to anyone senior enough to be shown it. The
    ellipsis is what tells a reader the sentence continues elsewhere.
    """
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    cut = text[:limit - 1]
    space = cut.rfind(" ")
    if space > limit * 0.6:                     # only if it doesn't gut the string
        cut = cut[:space]
    return cut.rstrip(" ,;:.-") + "…"


def gap_row_to_risk(row: dict, risk_id: str) -> dict:
    level = PRIORITY_SEED.get((row["priority"] or "").lower(), 3)
    risk = empty_risk(risk_id)
    risk["title"] = trunc(f"{row['subcategory_id']}: {row['subcategory_text']}")
    risk["description"] = f"CSF gap — {row['subcategory_text']}"
    risk["category"] = row["function_id"]
    fid = (row["function_id"] or "").strip().upper()
    risk["theme"] = fid.lower() if fid in CSF_FUNCTION_THEMES else None
    risk["csfSubcategoryId"] = row["subcategory_id"]
    risk["inherent"] = {"likelihood": level, "impact": level}
    risk["residual"] = {"likelihood": level, "impact": level}
    # An imported row is a *candidate*, not an assessed risk, and it is unreviewed in two
    # independent ways: the title is a control objective phrased as a good thing, and the
    # scores are a priority seed nobody has looked at.
    #
    # Tracked separately because they are cleared by different acts and only one of them
    # governs board safety. Treating them as one flag meant `set-score` — refining the
    # numbers — also authorised the untouched framework wording for the board, which is
    # precisely the exposure this mechanism exists to prevent.
    risk["provisionalTitle"] = True     # cleared by set-text; gates board-facing titles
    risk["provisionalScore"] = True     # cleared by set-score; gates "is this assessed?"
    # Deliberately NOT "Tier X → Y". These are achievement ratings on a 0-3 scale, and
    # both skills warn that the gap CSV's `current_tier`/`target_tier` column names must
    # never reach a reader. The importer used to produce that exact leak itself.
    note_parts = [f"CSF rating {row['current_tier']} → {row['target_tier']} (achievement, not a CSF Tier)",
                  f"priority: {row['priority']}"]
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
            # Only overwrite the wording while nobody has rewritten it. Once a risk has
            # been through set-text it carries a NISTIR 8286 event statement someone
            # authored; re-importing after a quarterly review must refresh the CSF-derived
            # facts without silently throwing that away.
            if match.get("provisionalTitle"):
                match["title"] = cand["title"]
                match["description"] = cand["description"]
            match["category"] = cand["category"]
            match["notes"] = cand.get("notes")
            # Fill an unset theme, but never overwrite a deliberate re-theme.
            if not match.get("theme") and cand.get("theme"):
                match["theme"] = cand["theme"]
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
        # Risks written before these flags existed were authored by hand, so they are
        # reviewed by definition. Only the importer sets them true.
        #
        # `provisional` was a single flag in an earlier build; a file carrying it is
        # normalized to both dimensions, since at that point neither had been reviewed
        # independently.
        legacy = r.pop("provisional", None)
        if legacy is not None:
            r.setdefault("provisionalTitle", bool(legacy))
            r.setdefault("provisionalScore", bool(legacy))
        r.setdefault("provisionalTitle", False)
        r.setdefault("provisionalScore", False)
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
    if s["provisional"]:
        print(f"\n⚠ {s['provisional']} of {s['total']} risks are PROVISIONAL:")
        if s["provisionalTitle"]:
            print(f"    {s['provisionalTitle']} still carry CSF framework wording as a title. "
                  f"Held out of every\n      board-facing view until reworded with `set-text`.")
        if s["provisionalScore"]:
            print(f"    {s['provisionalScore']} still sit on the import priority seed. "
                  f"Their scores are placeholders,\n      not assessments. Refine with `set-score`.")
    print("\nID     Residual  Band       Over  Title")
    for r in scored["risks"]:
        flag = "⚠" if r["overAppetite"] else " "
        mark = ("T" if r.get("provisionalTitle") else "") + ("S" if r.get("provisionalScore") else "")
        print(f"{r['id']:<6} {r['residualExposure']:>7}  {r['residualBand']:<9}  {flag:<4} "
              f"{mark:<2} {trunc(r['title'], 54)}")
    if s["provisional"]:
        print("\n  T = title still framework wording · S = score still the import seed")
    return 0


def _ensure_csf_themes(reg: dict) -> list[str]:
    """Define a theme for every CSF Function actually used by a risk in this register.

    Assigning `theme` on import is not enough on its own — an id with no matching theme
    definition rolls up as Unclassified, which is the state this is fixing. Only Functions
    present in the data get a theme, so a register importing three Functions does not grow
    six themes it will never use.
    """
    have = {t.get("id") for t in reg.get("themes", [])}
    used = {r.get("theme") for r in reg["risks"] if r.get("theme")}
    added = []
    for fid, name in CSF_FUNCTION_THEMES.items():
        tid = fid.lower()
        if tid in used and tid not in have:
            reg.setdefault("themes", []).append(
                {"id": tid, "name": name,
                 "description": f"CSF 2.0 {name} ({fid}) Function — assigned automatically on gap import."})
            added.append(tid)
    if added:
        _append_event(reg, "theme-changed", field="themes", to=",".join(added),
                      rationale="CSF Function themes defined automatically during gap import.")
    return added


def _cmd_import_gaps(args: list[str]) -> int:
    into = None
    if "--into" in args:
        into = args[args.index("--into") + 1]
    paths = [a for a in args if not a.startswith("--") and a != into]
    if not paths:
        print("usage: score_register.py import-gaps <gaps.csv> [--into <register.rr>] [--write]\n"
              "  Previews the mapped candidates by default and writes nothing.\n"
              "  --write applies the merge to the --into register.", file=sys.stderr)
        return 2
    do_write = "--write" in args
    if do_write and not into:
        print("import-gaps: --write needs --into <register.rr> to write to.", file=sys.stderr)
        return 2
    with open(paths[0], encoding="utf-8") as fh:
        rows = parse_gaps_csv(fh.read())
    existing = load_register(into)["risks"] if into else []
    candidates = [gap_row_to_risk(row, f"R-{i + 1:03d}") for i, row in enumerate(rows)]
    result = merge_import(existing, candidates)
    if do_write and into:
        reg = load_register(into)
        reg["risks"] = result["risks"]
        added_themes = _ensure_csf_themes(reg)
        _append_event(reg, "import-merged",
                      rationale=f"{result['added']} added, {result['updated']} updated from {os.path.basename(paths[0])}")
        save_register(reg, into)
        print(f"Wrote {into}: {result['added']} added, {result['updated']} updated", file=sys.stderr)
        if added_themes:
            print(f"  Defined {len(added_themes)} CSF Function themes so the board rollup is not "
                  f"all Unclassified: {', '.join(added_themes)}.\n"
                  f"  Re-theme with set-theme if you group risk differently.", file=sys.stderr)
        prov = sum(1 for r in reg["risks"]
                   if r.get("provisionalTitle") or r.get("provisionalScore"))
        if prov:
            print(f"  {prov} risks are provisional: CSF framework wording for a title and seeded "
                  f"scores.\n  Titles are held out of every board-facing view until reworded with "
                  f"`set-text`;\n  scores stay placeholders until refined with `set-score`.",
                  file=sys.stderr)
    else:
        print(json.dumps(result, indent=2))
        tail = " (preview only — nothing written; add --write to apply)" if into else \
               " (preview only — pass --into <register.rr> --write to apply)"
        print(f"\n# {result['added']} added, {result['updated']} updated{tail}", file=sys.stderr)
    return 0


def _cmd_self_test(_: list[str]) -> int:
    checks: list[tuple[str, Any, Any]] = []

    def eq(name, got, want):
        checks.append((name, got, want))

    def _quiet(fn, argv):
        """Run a mutating command with its console output swallowed.

        The fixture's chatter is not the suite's output: an unscoped-register warning and a
        temp path printed mid-run read like failures to anyone running self-test. Errors
        still propagate — redirect_stdout restores on the way out — so the refusal tests
        below are unaffected.
        """
        with contextlib.redirect_stdout(io.StringIO()):
            return fn(argv)

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

    # --- Age bands and the age-affirming event taxonomy ---
    eq("age_band(0,180)", age_band(0, 180), "within")
    eq("age_band(90,180) edge", age_band(90, 180), "within")
    eq("age_band(91,180)", age_band(91, 180), "approaching")
    eq("age_band(180,180) edge", age_band(180, 180), "approaching")
    eq("age_band(181,180)", age_band(181, 180), "beyond")
    eq("age_band(360,180) edge", age_band(360, 180), "beyond")
    eq("age_band(361,180)", age_band(361, 180), "wellBeyond")
    # Rescaling, shown with one fixed age against two cadences rather than one lucky
    # number: 200 days is past the line at a 180-day cadence and comfortably short of it
    # at 365. (365//2 == 182, so 200 is `approaching` there, not `within` — the floor
    # division is the thing worth pinning.)
    eq("age_band rescales at T=365", age_band(200, 365), "approaching")
    eq("age_band(200,180) for contrast", age_band(200, 180), "beyond")
    eq("age_band(182,365) floor-division edge", age_band(182, 365), "within")
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
    # Totality: a new event type must be *classified*, not merely registered. The emitted
    # set is scraped from this file's own source rather than hand-listed, so adding an
    # emitting call is what breaks the suite; and the partition below means the repair has
    # to be a decision about age rather than one more name in a list.
    _emitted = _emitted_event_types()
    eq("every affirming type is a known type", AGE_AFFIRMING - KNOWN_EVENT_TYPES, set())
    eq("every type score_register can write is classified", _emitted - KNOWN_EVENT_TYPES, set())
    # ...and the scrape itself is not vacuous. Without this, a regex that matches nothing
    # makes the check above pass over an empty set — green proving nothing.
    eq("the emitted-type scrape found real calls",
       {"risk-added", "score-changed", "risk-confirmed", "status-changed"} - _emitted, set())
    # Both arms of the unreadable-source sentinel, by rebinding __file__ rather than by
    # trusting the comment. Nothing else in the suite notices if the UnicodeDecodeError arm
    # is removed, and then a .pyc-only install fails with a codec error nobody would ever
    # connect to event types instead of the loud sentinel this is here to produce.
    with tempfile.TemporaryDirectory() as _sd:
        _binary = os.path.join(_sd, "notsource.bin")
        with open(_binary, "wb") as _fh:
            _fh.write(b"\xf6\x00\xa4\xff not valid utf-8 \x80\x81")
        _real_file = globals()["__file__"]

        def _probe(path):
            """Scrape with __file__ pointed elsewhere, reporting a raise as a value.

            Returned rather than propagated so a missing except-arm fails this check by
            name. Left to propagate, it aborts the suite with a bare codec error and the
            tally never prints — which is how the arm this pins came to be missing.
            """
            globals()["__file__"] = path
            try:
                return _emitted_event_types()
            except Exception as exc:
                return {"<raised:" + type(exc).__name__ + ">"}

        try:
            _undecodable = _probe(_binary)                      # a .pyc-only install
            _missing = _probe(os.path.join(_sd, "absent.py"))    # a missing source
        finally:
            globals()["__file__"] = _real_file
        eq("an undecodable source yields the sentinel", _undecodable, {"<source-unreadable>"})
        eq("a missing source yields the sentinel", _missing, {"<source-unreadable>"})
        # The sentinel has to actually fail the totality check, or it is decoration.
        eq("the sentinel fails the totality check",
           bool(_undecodable - KNOWN_EVENT_TYPES), True)
        eq("the scrape recovers once the source is back",
           _emitted_event_types(), _emitted)
    # The partition. Subset-of-known alone forced registration and stopped there, which
    # left a new type non-affirming by omission — the exact default the mechanism claims to
    # prevent. Requiring the union makes registration insufficient: a type must land on one
    # side or the other, and choosing a side is the decision.
    eq("no type both affirms and does not", AGE_AFFIRMING & NON_AGE_AFFIRMING, frozenset())
    eq("every known type is classified either way",
       AGE_AFFIRMING | NON_AGE_AFFIRMING, KNOWN_EVENT_TYPES)
    eq("the two halves are non-empty",
       bool(AGE_AFFIRMING) and bool(NON_AGE_AFFIRMING), True)

    # --- confirm: "I looked at this and nothing changed" has a home ---
    eq("confirm is reachable from the CLI", "confirm" in COMMANDS, True)

    def _load(path):
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)

    def _raw(path):
        with open(path, "rb") as fh:
            return fh.read()

    def _refuses(argv):
        """True when a command refuses AND leaves the file byte-identical.

        Both halves in one helper because they are one property: a refusal that has
        already written is not a refusal. Asserting them separately is how the second
        half ends up covering only the first refusal anyone thought to test.
        """
        raw = _raw(argv[0])
        try:
            _quiet(_cmd_confirm, argv)
            return (False, raw == _raw(argv[0]))
        except ValueError:
            return (True, raw == _raw(argv[0]))

    with tempfile.TemporaryDirectory() as _d:
        _rr = os.path.join(_d, "c.rr")
        _quiet(_cmd_init, [_rr, "--client", "Fixture Co", "--assessor", "D. Alleyne"])
        _quiet(_cmd_add, [_rr, "--title", "Supplier concentration", "--il", "4", "--ii", "4",
                          "--rl", "3", "--ri", "4", "--why", "fixture"])
        _before = _load(_rr)
        _n_before = len(_before["history"])
        # The before-state as `confirm` itself will see it. Comparing a raw json.load
        # against a post-save file would fail on load_register's v1->v2 normalization (it
        # defaults provisionalTitle/provisionalScore, which `add` never wrote) and blame
        # `confirm` for it. Normalize both sides so the comparison can only fail on a real
        # mutation.
        _norm_before = load_register(_rr)
        _quiet(_cmd_confirm, [_rr, "R-001", "--why",
                              "reviewed at the monthly risk forum; unchanged"])
        _after = _load(_rr)
        _ev = _after["history"][-1]
        eq("confirm appends exactly one event", len(_after["history"]) - _n_before, 1)
        eq("confirm writes risk-confirmed", _ev["type"], "risk-confirmed")
        eq("confirm names the risk", _ev.get("riskId"), "R-001")
        # .get() throughout: a mutant that writes a different event shape should fail a
        # named check, not abort the whole suite with a KeyError five minutes from
        # anyone working out which assertion it was.
        eq("confirm records the rationale", _ev.get("rationale"),
           "reviewed at the monthly risk forum; unchanged")
        eq("confirm records the actor", _ev.get("actor"), "D. Alleyne")
        eq("confirm carries a timestamp", bool(_ev.get("ts")), True)
        # Confirming asserts nothing new about magnitude, treatment or status.
        _r_before = [r for r in _norm_before["risks"] if r["id"] == "R-001"][0]
        _r_after = [r for r in load_register(_rr)["risks"] if r["id"] == "R-001"][0]
        eq("confirm changes no score", _r_after["residual"], _r_before["residual"])
        eq("confirm changes no status", _r_after["status"], _r_before["status"])
        eq("confirm changes no response", _r_after["response"], _r_before["response"])
        # The three above name three fields. This one holds the line: without --review,
        # `confirm` may change *nothing* on the risk, so a future version that quietly
        # edits owner, priority or a field invented next year is caught here.
        eq("confirm changes nothing whatsoever on the risk", _r_after, _r_before)
        # ...and the same again one level up. The risk object is not the only thing a
        # register holds: appetite and matrixSize drive every over-appetite flag and the
        # board headline, and a confirm that edited settings would sail past a
        # risk-only comparison. history and updatedAt are the two things confirm is
        # supposed to move.
        def _reg_key(g):
            return {k: v for k, v in g.items() if k not in ("history", "updatedAt")}

        eq("confirm changes nothing else in the register",
           _reg_key(load_register(_rr)), _reg_key(_norm_before))

        # Each refusal must both refuse and leave the file byte-identical, asserted as one
        # pair at every site: a refusal that has already written is not a refusal.
        eq("confirm without --why is refused, leaving the register untouched",
           _refuses([_rr, "R-001"]), (True, True))
        # A bare --review is a typo, not a request for a default: silently dropping it
        # sends a reviewer out of the meeting believing the next review is booked.
        eq("a bare --review is refused, writing nothing",
           _refuses([_rr, "R-001", "--why", "still stands", "--review"]), (True, True))
        eq("a non-ISO --review is refused, writing nothing",
           _refuses([_rr, "R-001", "--why", "still stands", "--review", "31/01/2027"]),
           (True, True))
        # An unpadded date is the dangerous one: strptime accepted `2027-2-01`, stored it,
        # and _overdue's lexical compare then read an overdue review as on time.
        eq("an unpadded --review is refused, writing nothing",
           _refuses([_rr, "R-001", "--why", "still stands", "--review", "2027-2-01"]),
           (True, True))
        # Every site below asserts the pair, never just the refusal half. _refuses() makes
        # the two halves impossible to drift apart in construction, but a caller can still
        # drop one — and a refusal copied from a half-asserted site inherits the gap.
        # The basic form is rejected too, so the flag means one thing on 3.9 and on 3.11+.
        eq("a basic-form --review is refused, writing nothing",
           _refuses([_rr, "R-001", "--why", "x", "--review", "20270201"]), (True, True))
        # A flag given twice used to keep the last value silently.
        eq("a repeated --review is refused, writing nothing",
           _refuses([_rr, "R-001", "--why", "a", "--review", "2027-01-31",
                     "--review", "2027-02-28"]), (True, True))
        eq("a repeated --why is refused, writing nothing",
           _refuses([_rr, "R-001", "--why", "a", "--why", "b"]), (True, True))
        # An unknown risk id is an error, not a silently-created risk.
        eq("confirm on an unknown id is refused, writing nothing",
           _refuses([_rr, "R-999", "--why", "t"]), (True, True))

        # --review sets the next review date in the same breath as the confirmation,
        # because that is the actual review-meeting workflow.
        _quiet(_cmd_confirm, [_rr, "R-001", "--why", "forum re-affirmed",
                              "--review", "2027-01-31"])
        _r3 = [r for r in _load(_rr)["risks"] if r["id"] == "R-001"][0]
        eq("--review sets the next review date", _r3.get("reviewDate"), "2027-01-31")
        # reviewDate is the one field --review is licensed to write. Nothing else may move.
        eq("--review changes nothing but reviewDate",
           {k: v for k, v in _r3.items() if k != "reviewDate"},
           {k: v for k, v in _r_after.items() if k != "reviewDate"})

        # Confirming a *closed* risk is allowed on purpose — see the note in _cmd_confirm.
        # "We re-checked this closed risk and it stays closed" is a claim reviewers make
        # and ask about, and refusing it would push people to reopen a risk to record it.
        _quiet(_cmd_set_status, [_rr, "R-001", "closed", "--why", "treatment complete"])
        _quiet(_cmd_confirm, [_rr, "R-001", "--why", "re-checked; stays closed"])
        _closed = _load(_rr)
        eq("confirm works on a closed risk", _closed["history"][-1]["type"], "risk-confirmed")
        eq("confirming a closed risk does not reopen it",
           [r for r in _closed["risks"] if r["id"] == "R-001"][0]["status"], "closed")

    # A provisional score is the importer's seed off a CSF gap priority — nobody has
    # assessed it. risk-confirmed affirms age, so confirming here would reset confirmation
    # age on a number no human ever reviewed and feed a board freshness figure with it.
    with tempfile.TemporaryDirectory() as _d2:
        _pr = os.path.join(_d2, "p.rr")
        _quiet(_cmd_init, [_pr, "--client", "Fixture Co", "--assessor", "D. Alleyne"])
        _quiet(_cmd_add, [_pr, "--title", "PR.AA-05 partially implemented", "--il", "4",
                          "--ii", "4", "--rl", "4", "--ri", "4", "--why", "imported"])
        _p = load_register(_pr)
        _p["risks"][0]["provisionalTitle"] = True
        _p["risks"][0]["provisionalScore"] = True
        save_register(_p, _pr)
        _praw = _raw(_pr)
        try:
            _quiet(_cmd_confirm, [_pr, "R-001", "--why", "looks fine"])
            _prov = False
        except ValueError:
            _prov = True
        eq("confirm refuses a provisional score", _prov, True)
        eq("a refused provisional confirm writes nothing", _raw(_pr), _praw)
        # Clearing the score flag the honest way — set-score, which records a rationale —
        # makes it confirmable. A provisional *title* only warns: wording is a
        # board-eligibility question, not a magnitude one.
        _quiet(_cmd_set_score, [_pr, "R-001", "--residual", "4", "4",
                                "--why", "assessed; seed value was right"])
        # Caught rather than called bare: an over-strict confirm that also refused a
        # provisional *title* would otherwise abort the whole suite with an unnamed error
        # instead of failing this one check by name.
        try:
            _quiet(_cmd_confirm, [_pr, "R-001", "--why", "re-affirmed at the forum"])
            _title_warns = True
        except ValueError:
            _title_warns = False
        eq("a provisional title only warns, it does not refuse", _title_warns, True)
        eq("...and the confirmation was recorded",
           _load(_pr)["history"][-1]["type"], "risk-confirmed")
        eq("confirming leaves the provisional title flag alone",
           [r for r in _load(_pr)["risks"] if r["id"] == "R-001"][0].get("provisionalTitle"),
           True)

    # --- The invariant: no affirming event may attach to a provisional-score risk ---
    #
    # Asserted over the writer set derived from this file's own source, not over the two
    # instances we happened to think of. `confirm` was fixed first and `accept` was found
    # open afterwards through the adjacent door; the point of deriving the set is that a
    # fifth affirming writer has to face the question instead of inheriting the gap.
    _writers = _affirming_writers()
    # _cmd_add is exempt by construction: it *creates* the risk and never sets the
    # provisional flags, so there is no pre-existing provisional risk for it to affirm.
    # Every other affirming writer takes an existing id and is probed below.
    _probes = {
        "_cmd_confirm": (_cmd_confirm, ["R-001", "--why", "still stands"], "refuses"),
        "_cmd_accept": (_cmd_accept, ["R-001", "--approver", "Audit Committee",
                                      "--justification", "board tolerates it",
                                      "--revalidate", "2027-01-31"], "refuses"),
        # set-score is the sanctioned way through rather than an exception to the rule: it
        # affirms *and* clears provisionalScore, so the score it affirms has been assessed.
        "_cmd_set_score": (_cmd_set_score, ["R-001", "--residual", "4", "4",
                                            "--why", "assessed at the forum"], "clears"),
    }
    eq("every affirming writer is either probed or exempt with a reason",
       set(_probes) | {"_cmd_add"}, _writers)
    for _name in sorted(_probes):
        _fn, _tail, _expected = _probes[_name]
        with tempfile.TemporaryDirectory() as _id:
            _ir = os.path.join(_id, "i.rr")
            _quiet(_cmd_init, [_ir, "--client", "Fixture Co", "--assessor", "D. Alleyne"])
            _quiet(_cmd_add, [_ir, "--title", "PR.AA-05 partially implemented", "--il", "4",
                              "--ii", "4", "--rl", "4", "--ri", "4", "--why", "imported"])
            _ip = load_register(_ir)
            _ip["risks"][0]["provisionalScore"] = True
            save_register(_ip, _ir)
            _iraw = _raw(_ir)
            try:
                _quiet(_fn, [_ir] + _tail)
                _refused = False
            except ValueError:
                _refused = True
            _after_risk = [r for r in load_register(_ir)["risks"] if r["id"] == "R-001"][0]
            _still = bool(_after_risk.get("provisionalScore"))
            # The invariant, stated once and applied to every writer: either the command
            # refused and wrote nothing, or the score it affirmed is no longer a seed.
            eq(f"invariant — {_name} cannot affirm a provisional score",
               (_refused and _raw(_ir) == _iraw) or not _still, True)
            # ...and which branch held is pinned too, so "refuses" cannot silently become
            # "clears" (or vice versa) while the invariant above stays green.
            eq(f"{_name} takes the {_expected} branch",
               "refuses" if _refused else ("clears" if not _still else "neither"),
               _expected)

    # The same date validation on every flag that writes a lexically-compared date.
    with tempfile.TemporaryDirectory() as _d3:
        _dr = os.path.join(_d3, "d.rr")
        _quiet(_cmd_init, [_dr, "--client", "Fixture Co", "--assessor", "D. Alleyne"])

        def _rejects(fn, argv):
            raw = _raw(argv[0])
            try:
                _quiet(fn, argv)
                return (False, raw == _raw(argv[0]))
            except ValueError:
                return (True, raw == _raw(argv[0]))

        _add = [_dr, "--title", "T", "--il", "2", "--ii", "2", "--rl", "2", "--ri", "2",
                "--why", "w"]
        eq("add --review rejects an unpadded date",
           _rejects(_cmd_add, _add + ["--review", "2027-2-01"]), (True, True))
        _quiet(_cmd_add, _add + ["--review", "2027-02-01"])
        eq("add --review keeps a canonical date",
           [r for r in _load(_dr)["risks"] if r["id"] == "R-001"][0]["reviewDate"],
           "2027-02-01")
        _acc = [_dr, "R-001", "--approver", "CFO", "--justification", "j"]
        eq("accept --revalidate rejects an unpadded date",
           _rejects(_cmd_accept, _acc + ["--revalidate", "2027-2-01"]), (True, True))
        eq("accept --expiry rejects an unpadded date",
           _rejects(_cmd_accept, _acc + ["--revalidate", "2027-02-01",
                                         "--expiry", "2027-6-30"]), (True, True))
        _quiet(_cmd_accept, _acc + ["--revalidate", "2027-02-01", "--expiry", "2027-06-30"])
        _acceptance = [r for r in _load(_dr)["risks"] if r["id"] == "R-001"][0]["acceptance"]
        eq("accept stores canonical dates",
           (_acceptance["revalidationDate"], _acceptance["expiryDate"]),
           ("2027-02-01", "2027-06-30"))
        # The defect in one line: the date the old code stored reads as NOT overdue
        # against a later today, because the comparison downstream is lexical.
        eq("an unpadded date would have inverted the overdue compare",
           ("2027-2-01"[:10] <= "2027-11-01", "2027-02-01"[:10] <= "2027-11-01"),
           (False, True))

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

# --- Age bands and the age-affirming event taxonomy ---------------------------
# The twin of skills/nist-csf/scripts/profile_analysis.py's age_band(), and that file
# carries the matching note pointing here. Deliberately duplicated: the obvious cleanup —
# one shared module, say skills/_shared/age.py — is rejected because every shipped script
# must run standalone, so a cross-skill import needs sys.path surgery and breaks outright
# the moment a single skill directory is used on its own. The obligation that replaces it:
# the two copies are edited together, and each skill's own self-test is the only thing
# pinning them to the same semantics. Grep the sibling path above before moving a boundary.
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

    A negative `days` — an affirming event dated in the future — reports as `within`,
    matching the twin. This is a pure distance measurement and an `impossible` band would
    smuggle a validation verdict into the distribution; a future-dated event is a file
    defect and belongs wherever the file is validated, not hidden inside a band a reader
    would take as good news.
    """
    if days <= threshold_days // 2:
        return "within"
    if days <= threshold_days:
        return "approaching"
    if days <= threshold_days * 2:
        return "beyond"
    return "wellBeyond"


# Events where a human asserted something about a risk's magnitude or its treatment
# decision. Only these reset confirmation age. A note, a rewording, a theme move, a
# status flip and a snapshot deliberately do not: an age that any edit resets makes the
# confirmation-age report worthless.
AGE_AFFIRMING = frozenset({
    "risk-added", "score-changed", "risk-confirmed", "risk-accepted",
    # Nothing writes this yet; references/schema.md documents it, and it is an
    # affirmation when it arrives. Classified now so it behaves correctly then.
    "acceptance-revalidated",
})

# The other half of the partition: events that are real history but assert nothing about
# a risk's magnitude or its treatment decision, and so must NOT reset confirmation age.
# Spelled out rather than left as "everything not listed above", because the difference
# between the two is the whole mechanism — see the note on KNOWN_EVENT_TYPES.
NON_AGE_AFFIRMING = frozenset({
    "register-created", "risk-updated", "response-changed", "status-changed",
    "theme-changed", "settings-changed", "snapshot-created", "import-merged",
    "risk-closed", "risk-reopened", "risk-deleted",
})

# Every type this file can write, plus every type references/schema.md documents.
#
# The self-test holds three things together: the emitted set (scraped from this file's own
# source) is a subset of this one, AGE_AFFIRMING and NON_AGE_AFFIRMING are disjoint, and
# their union is exactly this set. That third assertion is the one that matters. An
# earlier version asserted only the subset property, which forced a new event type to be
# *registered* here and nothing more — the single edit a failing subset check steers you
# toward — leaving it non-affirming by omission, which is precisely the default the
# mechanism exists to prevent. Requiring the union makes registration insufficient: a new
# type has to be placed in AGE_AFFIRMING or NON_AGE_AFFIRMING, and that placement is the
# decision. Silently resetting, or silently failing to reset, staleness is what makes a
# staleness report worthless.
#
# Written out independently rather than as `AGE_AFFIRMING | NON_AGE_AFFIRMING`, which would
# make the union assertion a tautology and hand back the hole it was added to close.
KNOWN_EVENT_TYPES = frozenset({
    "register-created", "risk-added", "risk-updated", "score-changed", "response-changed",
    "status-changed", "risk-accepted", "acceptance-revalidated", "risk-confirmed",
    "risk-closed", "risk-reopened", "risk-deleted", "theme-changed", "settings-changed",
    "snapshot-created", "import-merged",
})


def _emitted_event_types() -> set:
    """Every event type this file actually writes, scraped from its own source text.

    Derived rather than hand-listed on purpose. The self-test asserts this is a subset of
    KNOWN_EVENT_TYPES; if both sides were hand-maintained constants the check could not
    fail, because whoever added an emitting call would be the same person updating the
    list — green over an unclassified event type. Reading the source means the new call
    itself is what breaks the suite.

    The pattern below does not match its own text (the literal here is `_append_event\\(`,
    with a backslash), so this function never counts itself.

    If the source cannot be read, this returns a sentinel that is deliberately not a valid
    event type, so the totality check fails loudly rather than passing over an empty set.
    UnicodeDecodeError is caught alongside OSError because a .pyc-only install makes
    __file__ the bytecode: decoding it raises UnicodeDecodeError, which subclasses
    ValueError and would be swallowed by __main__'s handler into a codec error no
    maintainer would ever connect to event types. python-compat.sh's own note that the
    installed plugin "is NOT a git checkout" is why non-checkout execution is worth
    handling rather than assuming away.
    """
    try:
        with open(os.path.abspath(__file__), encoding="utf-8") as fh:
            src = fh.read()
    except (OSError, UnicodeDecodeError):
        return {"<source-unreadable>"}
    return set(re.findall(r'_append_event\(\s*reg\s*,\s*"([a-z-]+)"', src))


def _affirming_writers() -> set:
    """Every command function in this file that can write an AGE_AFFIRMING event.

    Derived from source for the same reason _emitted_event_types() is: the invariant it
    guards — no affirming event may attach to a provisional-score risk — has to hold for
    writers nobody has thought of yet, and a hand-kept list of writers is exactly the
    omission-by-default the taxonomy partition was added to close.
    """
    try:
        with open(os.path.abspath(__file__), encoding="utf-8") as fh:
            src = fh.read()
    except (OSError, UnicodeDecodeError):
        return {"<source-unreadable>"}
    out = set()
    for chunk in re.split(r"\ndef ", src):
        name = chunk.split("(", 1)[0].strip()
        if not name.startswith("_cmd_"):
            continue
        emitted = re.findall(r'_append_event\(\s*reg\s*,\s*"([a-z-]+)"', chunk)
        if any(e in AGE_AFFIRMING for e in emitted):
            out.add(name)
    return out


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


def _iso_date(value, flag: str) -> str:
    """Validate a date flag as a canonical YYYY-MM-DD string, or refuse.

    Every date this file stores is compared *lexically* downstream —
    renderers/_common.py::_overdue is `str(value)[:10] <= today` — so a non-canonical
    date does not merely look untidy, it silently inverts the comparison.
    `datetime.strptime(v, "%Y-%m-%d")` accepts unpadded fields, so `2027-2-01` used to be
    stored verbatim and then read as *not overdue* against a today of `2027-11-01`,
    dropping an eight-month-overdue review off the attention list entirely.

    Twinned with skills/nist-csf/scripts/profile_analysis.py::_iso_date, which carries the
    matching note and enforced this rule first — references/schema.md:245 there states it
    exactly: "`2026-3-14` sorts after `2026-12-01` and would make every revisit flag and age
    figure downstream quietly wrong." Same name, same rule, same reason, duplicated on the
    same terms as age_band() above; edit the two together. That file reaches the verdict via
    a strptime round-trip and this one via date.fromisoformat plus a round-trip; the verdicts
    agree on every input either accepts, including `20270201`, and each skill's own self-test
    is what pins them.

    `date.fromisoformat` rejects the unpadded form. The round-trip equality check then
    rejects the basic form `20270201`, which 3.11+ accepts and the 3.9 floor does not —
    without it this flag would mean two different things on two supported interpreters,
    and `20270201` breaks `_overdue` exactly the same way. Same wording as _common.py's
    `--today` guard, which has always validated this way; this is that idiom reaching the
    flags that write the file rather than only the one that reads it.
    """
    s = _s(value)
    if s is True or s is None or not str(s).strip():
        raise ValueError(f"{flag} needs a date (YYYY-MM-DD).")
    s = str(s).strip()
    try:
        parsed = date.fromisoformat(s)
    except (ValueError, TypeError):
        raise ValueError(f"{flag} {s!r} is not a YYYY-MM-DD date.")
    if parsed.isoformat() != s:
        raise ValueError(f"{flag} {s!r} is not a YYYY-MM-DD date "
                         f"(write it as {parsed.isoformat()}).")
    return s


def _int_opt(opt, key, default):
    """Read an integer flag. A bare `--matrix` with no value is a typo, not a default."""
    if key not in opt or opt[key] is True:
        return default
    try:
        return int(_s(opt[key]))
    except (TypeError, ValueError):
        raise ValueError(f"--{key} must be an integer (got {_s(opt[key])!r}).")


def _cmd_init(args):
    """Create an empty register.

    Without this, the only way to start one is to hand-author the JSON — which
    SKILL.md forbids everywhere else ("the audit trail is enforced by tooling rather
    than by discipline") and which means the register's own creation, its matrix size
    and its appetite never enter history. Those three are exactly the settings a
    board later asks to see justified.
    """
    pos, opt = parse_flags(args)
    if not pos or "client" not in opt:
        raise ValueError("usage: init <register.rr> --client 'Acme Corp' [--assessor 'CISO'] "
                         "[--matrix 5] [--appetite medium] [--scope-note '...'] "
                         "[--appetite-statement '...']")
    path = pos[0]
    # Never clobber a register. It is the system of record, and a re-run of a setup
    # command is a plausible mistake with an unrecoverable outcome.
    if os.path.exists(path):
        raise ValueError(f"{path} already exists — refusing to overwrite an existing register.")

    size = _int_opt(opt, "matrix", 5)
    if size not in BAND_THRESHOLDS:
        raise ValueError(f"--matrix must be one of {sorted(BAND_THRESHOLDS)} (got {size}).")
    appetite = _s(opt.get("appetite", "medium"))
    if appetite not in BAND_ORDER:
        raise ValueError(f"--appetite must be one of {BAND_ORDER} (got {appetite!r}).")

    reg = {
        "schemaVersion": SCHEMA_VERSION,
        "meta": {
            "clientName": _s(opt["client"]),
            "assessor": _s(opt.get("assessor", "")) if opt.get("assessor") is not True else "",
            "scopeNote": _s(opt.get("scope-note", "")) if opt.get("scope-note") is not True else "",
            "appetiteStatement": (_s(opt.get("appetite-statement", ""))
                                  if opt.get("appetite-statement") is not True else ""),
        },
        "settings": {"matrixSize": size, "appetite": appetite},
        "themes": [],
        "risks": [],
        "history": [],
        "snapshots": [],
    }
    _append_event(reg, "register-created", field="settings",
                  to=f"{size}x{size} matrix, {appetite} appetite",
                  rationale=_s(opt.get("why")) if isinstance(opt.get("why"), (str, list)) else None)
    save_register(reg, path)

    print(f"Created {path}")
    print(f"  Client:   {reg['meta']['clientName']}")
    print(f"  Assessor: {reg['meta']['assessor'] or '—'}")
    print(f"  Matrix:   {size}x{size}   Appetite: {appetite} "
          f"(worst band still acceptable)")
    if not reg["meta"]["scopeNote"]:
        print("  Note: no --scope-note set. An unscoped register is hard to defend; "
              "record what is in and out.")
    print("  Next: add risks with `add`, or import CSF gaps with "
          "`import-gaps <gaps.csv> --into " + path + " --write`.")
    return 0


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
        risk["reviewDate"] = _iso_date(opt["review"], "--review")
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


def _cmd_set_text(args):
    """Rewrite a risk's title and/or description, clearing `provisionalTitle`.

    The build workflow says to reword each imported gap as a NISTIR 8286 event
    statement — "PR.AA-05 partially implemented" is a control objective, not a risk —
    but until this command existed there was no way to do it except hand-editing the
    JSON, which bypasses history entirely. This is the command that makes an imported
    candidate into an assessed risk.
    """
    pos, opt = parse_flags(args)
    if len(pos) < 2 or not ({"title", "description"} & set(opt)):
        raise ValueError("usage: set-text <register.rr> <risk-id> [--title '...'] "
                         "[--description '...'] --why '...'")
    path, rid = pos[0], pos[1]
    if "why" not in opt:
        raise ValueError("set-text: --why is required — rewording a risk is a material change.")
    reg = load_register(path)
    risk = _find(reg, rid)

    for field in ("title", "description"):
        if field in opt:
            old, new = risk.get(field, ""), _s(opt[field])
            if old == new:
                continue
            risk[field] = new
            _append_event(reg, "risk-updated", riskId=rid, field=field,
                          frm=trunc(old, 80), to=trunc(new, 80), rationale=opt["why"])

    was_provisional = bool(risk.get("provisionalTitle"))
    if was_provisional:
        risk["provisionalTitle"] = False
        _append_event(reg, "risk-updated", riskId=rid, field="provisionalTitle",
                      frm=True, to=False, rationale=opt["why"])
    save_register(reg, path)

    print(f"Updated {rid}: {trunc(risk['title'], 90)}")
    if was_provisional:
        print("  Wording reviewed — this title will now render in board-facing views.")
    if risk.get("provisionalScore"):
        print("  Scores are still the import seed. Refine them with `set-score`.")
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
    # Scoring clears the *score* dimension only. It deliberately does not authorise the
    # title: refining likelihood and impact says nothing about whether the wording is
    # still a control objective phrased as a good thing. Conflating the two let the
    # score-only review path put raw framework text in front of a board.
    if r.get("provisionalScore"):
        r["provisionalScore"] = False
        _append_event(reg, "risk-updated", riskId=pos[1], field="provisionalScore",
                      frm=True, to=False, rationale=opt["why"])
    save_register(reg, pos[0])
    res = exposure(r["residual"]["likelihood"], r["residual"]["impact"])
    print(f"{pos[1]} updated: residual {res} {band(res, size)}")
    if r.get("provisionalTitle"):
        print("  Title is still CSF framework wording, so it stays out of board views.")
        print("  Reword it with `set-text` when you are ready to show it.")
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
    # Refused for the same reason `confirm` is, and this is the door that closes the set.
    # `risk-accepted` is in AGE_AFFIRMING, so accepting here reset confirmation age to zero
    # on the importer's seed number and fed a board-facing freshness figure with it — and
    # `accept` is the worse of the two paths, because it also flips response.type and books
    # a *named approver* against a magnitude nobody has assessed, which is precisely what an
    # auditor tests.
    #
    # The invariant this establishes: NO AFFIRMING EVENT CAN ATTACH TO A PROVISIONAL-SCORE
    # RISK. It holds because the affirming writers are exactly four. `risk-added` comes only
    # from _cmd_add, which creates the risk and never sets the provisional flags (only the
    # importer does, and it writes `import-merged`, which is non-affirming). `score-changed`
    # comes from _cmd_set_score, which *clears* provisionalScore in the same breath — it is
    # the sanctioned way through, not an exception to the rule. That leaves confirm and
    # accept, both of which now refuse. `acceptance-revalidated` is inert: nothing emits it.
    # The self-test asserts the invariant over the writer set derived from this file's own
    # source, so a fifth affirming writer has to face the question rather than inherit a
    # gap. That invariant is what makes the confirmation-age report trustworthy.
    if r.get("provisionalScore"):
        raise ValueError(f"accept: {pos[1]}'s score is still the import seed, so there is no "
                         f"assessed magnitude to accept. Assess it with `set-score` first — "
                         f"booking a named approver against a number nobody has reviewed is "
                         f"the acceptance an auditor pulls.")
    # All three dates are validated before anything is written. revalidationDate and
    # expiryDate both reach _overdue's lexical compare in the renderers, so an unpadded
    # date here reads as "not due" and an acceptance nobody re-validated stops appearing
    # on the attention list. acceptedDate is validated for the same reason its siblings
    # are: one flag name meaning one thing.
    revalidate = _iso_date(opt["revalidate"], "--revalidate")
    expiry = _iso_date(opt["expiry"], "--expiry") if "expiry" in opt else ""
    accepted = _iso_date(opt["accepted"], "--accepted") if "accepted" in opt else _now()[:10]
    # Every date is parsed before the first write, so a bad one refuses without leaving a
    # half-applied acceptance behind — response.type used to flip to "accept" first.
    r["response"]["type"] = "accept"
    r["acceptance"] = {
        "approver": _s(opt["approver"]), "justification": _s(opt["justification"]),
        "acceptedDate": accepted, "expiryDate": expiry, "revalidationDate": revalidate,
    }
    _append_event(reg, "risk-accepted", riskId=pos[1], rationale=opt.get("why", opt["justification"]))
    save_register(reg, pos[0])
    print(f"{pos[1]} accepted by {r['acceptance']['approver']}; re-validate by {r['acceptance']['revalidationDate']}")
    return 0


def _cmd_confirm(args):
    """Record that a risk was looked at and nothing changed.

    Before this existed, the only way to re-affirm a risk was `set-score` at an identical
    value — which writes a `score-changed` event where no score changed, corroding the
    audit trail the skill exists to keep honest. "I reviewed this and it still stands" is
    a material claim and deserves its own event type and its own rationale.

    Changes no score, no status, no response, no band. The only optional write is
    `--review`, because setting the next review date in the same breath is the actual
    review-meeting workflow.

    Refuses while `provisionalScore` is true — there is nothing to re-affirm about a number
    nobody has assessed — and only warns on a provisional title, which is the same line
    `set-score` draws between magnitude and board-eligible wording.

    Confirming a *closed* risk is allowed, deliberately. "We re-checked this and it stays
    closed" is a claim reviewers make and auditors ask about, and refusing it would push
    people to reopen a risk purely to have somewhere to record the re-check — a worse
    audit trail than the one we are protecting. The corollary belongs downstream: a
    confirmation-age report must exclude closed risks rather than let a re-checked closed
    risk pad a freshness figure the board reads as live coverage.

    Ordering: every refusal below happens before the single in-memory write, and the only
    statement after that write is _append_event + save_register, neither of which
    validates. So a refused confirm never reaches save_register and the file on disk stays
    byte-identical — asserted in the self-test, not merely intended.

    This event's rationale is deliberately not eligible to caption a change on the board.
    `renderers/_common.py::Context.CHANGE_EXPLAINING` excludes `risk-confirmed`, because a
    claim that nothing changed cannot explain a change — left in, it printed "residual Low
    → Critical — 'reviewed at the forum; unchanged'" on the board page. The rationale is
    still kept in history and belongs to the confirmation-age view.
    """
    pos, opt = parse_flags(args)
    if len(pos) < 2:
        raise ValueError("usage: confirm <register.rr> <id> --why '...' [--review YYYY-MM-DD]")
    # A flag given twice used to keep the last value and drop the rest without a word.
    # Losing half of a stated intent in silence is the worst available outcome.
    for dup in ("why", "review"):
        if args.count("--" + dup) > 1:
            raise ValueError(f"confirm: --{dup} given more than once. Pass it once — "
                             f"keeping the last value silently discards what you meant.")
    reg = load_register(pos[0])
    r = _find(reg, pos[1])
    if not (isinstance(opt.get("why"), (str, list)) and _s(opt["why"]).strip()):
        raise ValueError("confirm: --why is required. Asserting that a risk is still right "
                         "is a material claim and belongs in the audit trail on the same "
                         "terms as a score change.")
    # A provisional score has never been reviewed by anyone — it is the importer's seed,
    # derived from a CSF gap's priority. `risk-confirmed` is in AGE_AFFIRMING, so
    # confirming here would reset confirmation age on a number nobody has ever assessed
    # and feed it into a board-facing freshness figure as though it had been. Refuse: the
    # honest path is `set-score` (at the seed value, if that is the assessment), which
    # clears the flag and records the rationale.
    #
    # This is not a date gate. It refuses to affirm something never assessed; it neither
    # expires nor rescores anything, and an assessed risk is confirmable forever.
    if r.get("provisionalScore"):
        raise ValueError(f"confirm: {pos[1]}'s score is still the import seed, so there is "
                         f"nothing yet to re-affirm. Assess it with `set-score` first — "
                         f"confirming would reset its confirmation age on a number nobody "
                         f"has reviewed.")
    review = None
    if "review" in opt:
        # A bare `--review` with no date is a typo, not a request for a default. There is
        # no sane default next-review date, and silently dropping the flag would send a
        # reviewer out of the meeting believing the next review is booked.
        if opt["review"] is True:
            raise ValueError("confirm: --review needs a date (YYYY-MM-DD). Bare --review "
                             "sets nothing, and a next review you think is booked but "
                             "isn't is worse than no date at all.")
        review = _iso_date(opt["review"], "--review")
        r["reviewDate"] = review
    _append_event(reg, "risk-confirmed", riskId=pos[1], rationale=opt["why"])
    save_register(reg, pos[0])
    print(f"{pos[1]} confirmed by {reg['meta'].get('assessor') or 'unknown'}.")
    if review:
        print(f"  Next review: {review}")
    # A provisional *title* only warns. Wording is a board-eligibility question, not a
    # magnitude one, and that is the same line `set-score` draws.
    if r.get("provisionalTitle"):
        print("  Title is still CSF framework wording, so it stays out of board views.")
        print("  Reword it with `set-text` when you are ready to show it.")
    return 0


def _cmd_set_status(args):
    pos, opt = parse_flags(args)
    if len(pos) < 3:
        raise ValueError(f"usage: set-status <register.rr> <id> <{'|'.join(sorted(STATUSES))}> [--why '...']")
    if pos[2] not in STATUSES:
        raise ValueError(f"status must be one of {sorted(STATUSES)}")
    reg = load_register(pos[0]); r = _find(reg, pos[1]); frm = r["status"]
    # Closing a risk, or reopening one that was closed, is a material change: it is a
    # completion claim an auditor will test. Refuse before touching the file so a rejected
    # mutation leaves the register byte-identical.
    material = pos[2] == "closed" or frm == "closed"
    if material and not (isinstance(opt.get("why"), (str, list)) and _s(opt["why"]).strip()):
        verb = "Closing" if pos[2] == "closed" else "Reopening"
        raise ValueError(f"set-status: --why is required to move {pos[1]} {frm} → {pos[2]}. "
                         f"{verb} a risk is a material change and the rationale is the audit "
                         f"trail — an unsupported completion claim is exactly what a reviewer "
                         f"looks for.")
    r["status"] = pos[2]
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
            "residualBand", "overAppetite", "status", "reviewDate", "csfSubcategoryId", "provisionalTitle", "provisionalScore"]
    # Python's True/False are not CSV booleans — Excel and every downstream parser expect
    # true/false. Writing the repr leaks the implementation language into an export.
    b = lambda v: "true" if v else "false"          # noqa: E731
    buf = io.StringIO(); w = csv.writer(buf); w.writerow(cols)
    for r in scored["risks"]:
        w.writerow([r["id"], r["title"], r["category"], r.get("theme") or "", r["owner"],
                    r["inherent"]["likelihood"], r["inherent"]["impact"], r["inherentExposure"], r["inherentBand"],
                    r["response"]["type"], r["response"].get("cost", ""),
                    r["residual"]["likelihood"], r["residual"]["impact"], r["residualExposure"], r["residualBand"],
                    b(r["overAppetite"]), r["status"], r.get("reviewDate", ""),
                    r.get("csfSubcategoryId", ""), b(r.get("provisionalTitle")),
                    b(r.get("provisionalScore"))])
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
    "init": _cmd_init, "set-text": _cmd_set_text,
    "add": _cmd_add, "set-score": _cmd_set_score, "accept": _cmd_accept,
    "confirm": _cmd_confirm,
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
