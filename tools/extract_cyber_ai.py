#!/usr/bin/env python3
"""Extract the Cyber AI Profile dataset from NIST IR 8596.

    pdftotext -layout NIST.IR.8596.iprd.pdf ir8596.txt
    ./extract_cyber_ai.py ir8596.txt --out cyber-ai-profile.json --coverage cov.txt

This exists to be run AGAIN. IR 8596 is a preliminary draft; an initial public
draft is expected, and when it lands the cost of following it should be a re-run
plus verification rather than a re-transcription of 318 numbers.

Standard library only, so it runs anywhere the rest of the toolkit does. The PDF
to text step is `pdftotext -layout` (poppler) — the `-layout` flag is not
optional, because this parser depends on horizontal character positions to tell
the three Focus Area columns apart.

## How the source is laid out

Tables 1-6 (one per CSF Function) give each of the 106 Subcategories one row.
Each row spans ~20 lines of extracted text, in five columns:

    CSF 2.0 Core | General Considerations | Secure | Defend | Thwart
                                           `------ Focus Area columns ------'

Two properties of the extracted text make this tractable:

1. **All three priorities land on the row's first line**, in column order:
   `GV.OC-01: The   General Considerations: No   Proposed Priority: 3   Proposed Priority: 3   Proposed Priority: 3`
   So the priorities parse from one line, and the character offset of each
   `Proposed Priority` marker gives that column's left edge.

2. **Everything else in the cell wraps across the remaining lines** at those
   same offsets. That is why the sentinel needs column slicing rather than a
   line grep: "Standard cybersecurity practices apply." is split as
   "Standard cybersecurity practices" / "apply." on separate lines, so a
   line-based search finds almost none of them.

## What it does not do

It does not read the considerations prose, and deliberately so — this repo does
not redistribute NIST's text. It records only the priority number and whether
the cell said "standard cybersecurity practices apply", which is a fact about
the cell, not a copy of it.
"""
from __future__ import annotations

import argparse
import json
import re
import sys

FOCUS_AREAS = ("secure", "defend", "thwart")

# Column order is asserted by the table header, which reads
# "Focus Area Proposed Priorities & Considerations / Secure | Defend | Thwart".
# Getting this backwards would invert every priority in a way no validator can
# catch, so --check-header verifies it rather than trusting this comment.
HEADER = re.compile(r"Secure\s+Defend\s+Thwart")

SUBCATEGORY = re.compile(r"\b((?:GV|ID|PR|DE|RS|RC)\.[A-Z]{2}-\d{2}):")
PRIORITY = re.compile(r"Proposed Priority:\s*([123])")
# Wrapped freely across lines in the extracted text, hence the \s+.
SENTINEL = re.compile(r"standard\s+cybersecurity\s+practices\s+apply", re.I)


def find_rows(lines: list[str]) -> tuple[list[tuple[int, str, list[int]]], list[str]]:
    """Row-start lines carrying a Subcategory id and all three priorities.

    Also returns anomalies: lines that name a Subcategory and carry SOME but not
    three priorities. Those are the page-break and merged-cell casualties the
    coverage report exists to surface. They are never silently defaulted.
    """
    rows, anomalies = [], []
    for i, line in enumerate(lines):
        m = SUBCATEGORY.search(line)
        if not m:
            continue
        found = PRIORITY.findall(line)
        if len(found) == 3:
            rows.append((i, m.group(1), [int(x) for x in found]))
        elif found:
            anomalies.append(
                f"line {i + 1}: {m.group(1)} carries {len(found)} priorities, not 3 "
                f"— likely split across a page break; read this row by hand")
    return rows, anomalies


def column_bounds(line: str) -> list[int]:
    """Left edge of each Focus Area column, from the priority markers."""
    return [m.start() for m in PRIORITY.finditer(line)]


def cell_text(block: list[str], lo: int, hi: int) -> str:
    """One column's text across a row's lines, whitespace-normalised.

    Slicing by character offset is what makes the sentinel findable: the phrase
    wraps mid-cell, so it only reassembles once the column is read vertically.
    """
    joined = " ".join(line[lo:hi] for line in block if len(line) > lo)
    return " ".join(joined.split())


def extract(lines: list[str]) -> tuple[dict, list[str]]:
    rows, notes = find_rows(lines)
    subcategories: dict = {}
    duplicates = []

    for n, (start, sid, priorities) in enumerate(rows):
        end = rows[n + 1][0] if n + 1 < len(rows) else len(lines)
        block = lines[start:end]
        bounds = column_bounds(lines[start])
        if sid in subcategories:
            duplicates.append(sid)
        entry = {}
        for a, area in enumerate(FOCUS_AREAS):
            lo = bounds[a]
            hi = bounds[a + 1] if a + 1 < len(bounds) else len(max(block, key=len)) + 1
            text = cell_text(block, lo, hi)
            entry[area] = {
                "priority": priorities[a],
                "standardPracticesApply": bool(SENTINEL.search(text)),
            }
        subcategories[sid] = entry

    if duplicates:
        notes.append(f"duplicate Subcategory rows: {', '.join(sorted(set(duplicates)))} "
                     f"— the later row won; check which is real")
    return subcategories, notes


def coverage_report(subcategories: dict, notes: list[str], core_ids: set | None) -> str:
    out = ["Cyber AI Profile extraction — coverage report", ""]
    out.append(f"Subcategories found:   {len(subcategories)}")
    values = sum(len(v) for v in subcategories.values())
    out.append(f"Priority values:       {values} (expect 3 per Subcategory)")

    sentinel_by_area = {a: sum(1 for v in subcategories.values()
                               if v[a]["standardPracticesApply"]) for a in FOCUS_AREAS}
    total_sentinel = sum(sentinel_by_area.values())
    out.append(f"'standard practices'   {total_sentinel} of {values} cells "
               f"{dict(sentinel_by_area)}")
    out.append(f"AI-specific cells:     {values - total_sentinel} "
               f"(these are the CAC guidance authoring targets)")
    out.append("")

    if core_ids is not None:
        missing = sorted(core_ids - set(subcategories))
        extra = sorted(set(subcategories) - core_ids)
        out.append(f"Missing from extraction: {', '.join(missing) if missing else 'none'}")
        out.append(f"Not in the CSF Core:     {', '.join(extra) if extra else 'none'}")
        out.append("")

    dist = {}
    for v in subcategories.values():
        for a in FOCUS_AREAS:
            dist.setdefault(a, {1: 0, 2: 0, 3: 0})[v[a]["priority"]] += 1
    out.append("Priority distribution (1=High, 2=Moderate, 3=Foundational):")
    for a in FOCUS_AREAS:
        d = dist.get(a, {})
        out.append(f"  {a:7s} 1:{d.get(1, 0):3d}  2:{d.get(2, 0):3d}  3:{d.get(3, 0):3d}")
    out.append("")

    if notes:
        out.append("CELLS NEEDING A HAND — nothing here was defaulted:")
        out.extend(f"  - {n}" for n in notes)
    else:
        out.append("No unparsed cells. Every row yielded three priorities.")
    out.append("")
    out.append("Well formed is not correct. Spot-check a sample against the PDF before")
    out.append("shipping this: a transcription error is invisible to every automated check.")
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("text", help="output of `pdftotext -layout` over the IR 8596 PDF")
    ap.add_argument("--out", required=True, help="dataset JSON to write")
    ap.add_argument("--coverage", help="coverage report to write (also printed to stderr)")
    ap.add_argument("--core", help="nist-csf-2.0-core.json, to check the id set")
    ap.add_argument("--dataset-version", default="8596-iprd-2025-12-16")
    ap.add_argument("--source-status", default="Initial Preliminary Draft")
    ap.add_argument("--source-published", default="2025-12-16")
    ap.add_argument("--source-url",
                    default="https://csrc.nist.gov/pubs/ir/8596/iprd")
    args = ap.parse_args()

    with open(args.text, encoding="utf-8", errors="replace") as fh:
        lines = fh.read().splitlines()

    if not any(HEADER.search(l) for l in lines):
        print("WARNING: could not find the 'Secure Defend Thwart' column header. "
              "Column order is assumed and may be wrong — verify before shipping.",
              file=sys.stderr)

    subcategories, notes = extract(lines)

    core_ids = None
    if args.core:
        with open(args.core, encoding="utf-8") as fh:
            core = json.load(fh)
        core_ids = set()

        def walk(node):
            if isinstance(node, dict):
                sid = node.get("id")
                if isinstance(sid, str) and SUBCATEGORY.match(sid + ":"):
                    core_ids.add(sid)
                for v in node.values():
                    walk(v)
            elif isinstance(node, list):
                for v in node:
                    walk(v)

        walk(core)

    dataset = {
        "datasetVersion": args.dataset_version,
        "sourceStatus": args.source_status,
        "sourcePublished": args.source_published,
        "sourceUrl": args.source_url,
        "note": ("Proposed priorities transcribed from NIST IR 8596 tables 1-6. "
                 "NIST states that determining priority is a subjective exercise "
                 "based on field observation and subject-matter expertise, and that "
                 "the level may be higher or lower for an individual organization. "
                 "Priority indicates sequencing, not required maturity. No NIST "
                 "consideration text is reproduced here — standardPracticesApply "
                 "records only whether a cell said 'standard cybersecurity practices "
                 "apply', which is a fact about the cell rather than a copy of it."),
        "extractedBy": "tools/extract_cyber_ai.py",
        "focusAreas": list(FOCUS_AREAS),
        "subcategories": dict(sorted(subcategories.items())),
    }

    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(dataset, fh, indent=1, ensure_ascii=False)
        fh.write("\n")

    report = coverage_report(subcategories, notes, core_ids)
    print(report, file=sys.stderr)
    if args.coverage:
        with open(args.coverage, "w", encoding="utf-8") as fh:
            fh.write(report + "\n")

    # A missing row is a failure, not a warning. Exit non-zero so a pipeline
    # cannot treat a partial extraction as a finished one.
    if core_ids is not None and (core_ids - set(subcategories)):
        return 1
    return 1 if notes else 0


if __name__ == "__main__":
    sys.exit(main())
