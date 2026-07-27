#!/usr/bin/env python3
"""ONE-TIME ingest: NIST CSF 2.0 CPRT catalog (XLSX) -> framework-neutral core JSON.

This script does NOT ship inside the skill. Only its output does.

    python3 tools/ingest-csf-core.py <out-path> [path/to/csf-2.0.xlsx]

Source:  tools/csf-2.0.xlsx (vendored NIST CPRT export; sha256 recorded in the output)
Model:   csf-assessment/scripts/ingest-csf.ts documents the row shape and the
         [Withdrawn:] exclusion rule; this script additionally captures columns
         D (Implementation Examples) and E (Informative References), which that
         ingest deliberately skipped.

Ported from ingest-csf-core.js (SheetJS) in 2026-07. The only thing the npm
dependency did was turn a worksheet into rows of strings, and it cost two
unfixable high-severity advisories to do it: npm's latest `xlsx` is 0.18.5, while
the prototype-pollution and ReDoS fixes landed in 0.19.3 and 0.20.2 — versions
SheetJS publishes only from its own CDN. An XLSX is a zip of XML, `zipfile` and
`ElementTree` are stdlib, and the read we need is about sixty lines. The port is
verified by regenerating the committed Core and diffing it byte-for-byte, so
"equivalent to the JS" is a checked claim rather than an assertion.

No dependencies. No install step. Same output.
"""
import hashlib
import json
import os
import re
import sys
import zipfile
from xml.etree import ElementTree as ET

SHEET = "CSF 2.0"
FUNCTION_ORDER = ["GV", "ID", "PR", "DE", "RS", "RC"]
EXPECTED_PER_FUNCTION = {"GV": 31, "ID": 21, "PR": 22, "DE": 11, "RS": 13, "RC": 8}

# Row patterns. The descriptor is optional so that bare "GOVERN (GV)" section
# terminators are recognised and skipped rather than silently parsed as a second
# Function. `.` excludes newlines and `[\s\S]` includes them, in both JS and
# Python — the descriptor spans lines, the name never does.
RE_FUNCTION = re.compile(r"^(.+?) \(([A-Z]{2})\)(?::\s*([\s\S]+))?\Z")
RE_CATEGORY = re.compile(r"^(.+?) \(([A-Z]{2}\.[A-Z]{2})\)(?::\s*([\s\S]+))?\Z")
RE_SUBCATEGORY = re.compile(r"^([A-Z]{2}\.[A-Z]{2}-\d{2}):\s*([\s\S]+)\Z")

NS_MAIN = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
NS_REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
NS_PKGREL = "{http://schemas.openxmlformats.org/package/2006/relationships}"


# --- XLSX reading (the part SheetJS used to do) -------------------------------


def _si_text(si):
    """Concatenate every <t> under one shared-string item, runs included.

    A cell whose text carries mixed formatting is stored as a sequence of <r>
    runs, each with its own <t>. Reading only the first would silently truncate
    at the first bold word.
    """
    return "".join(t.text or "" for t in si.iter(NS_MAIN + "t"))


def _col_index(ref):
    """'AB12' -> 27 (zero-based column). Letters are base-26, bijective."""
    n = 0
    for ch in ref:
        if not ch.isalpha():
            break
        n = n * 26 + (ord(ch.upper()) - 64)
    return n - 1


def _row_number(ref):
    return int(re.sub(r"[^0-9]", "", ref))


def read_sheet_rows(path, sheet_name):
    """Return the worksheet as a dense list of rows, each a list of cell strings.

    Mirrors SheetJS `sheet_to_json(ws, {header: 1, defval: "", blankrows: true})`:
    row N of the file is index N-1 here, blank rows included, so a row number in
    an error message points at the row you would see in Excel.
    """
    with zipfile.ZipFile(path) as z:
        # workbook.xml names the sheets; the rels file says which XML part each one is.
        wb = ET.fromstring(z.read("xl/workbook.xml"))
        rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        target_by_id = {r.get("Id"): r.get("Target") for r in rels.iter(NS_PKGREL + "Relationship")}

        target = None
        for sh in wb.iter(NS_MAIN + "sheet"):
            if sh.get("name") == sheet_name:
                target = target_by_id.get(sh.get(NS_REL + "id"))
                break
        if target is None:
            names = [s.get("name") for s in wb.iter(NS_MAIN + "sheet")]
            raise SystemExit(f"sheet {sheet_name!r} not found; workbook has: {names}")

        part = target[1:] if target.startswith("/") else "xl/" + target.lstrip("./")

        shared = []
        if "xl/sharedStrings.xml" in z.namelist():
            sst = ET.fromstring(z.read("xl/sharedStrings.xml"))
            shared = [_si_text(si) for si in sst.iter(NS_MAIN + "si")]

        ws = ET.fromstring(z.read(part))

    cells, max_row, max_col = {}, 0, 0
    for c in ws.iter(NS_MAIN + "c"):
        ref, ctype = c.get("r"), c.get("t")
        if not ref:
            continue
        r, col = _row_number(ref), _col_index(ref)
        if ctype == "s":                                    # shared string
            v = c.find(NS_MAIN + "v")
            text = shared[int(v.text)] if v is not None and v.text else ""
        elif ctype == "inlineStr":                          # inline string
            is_el = c.find(NS_MAIN + "is")
            text = _si_text(is_el) if is_el is not None else ""
        else:                                               # number, bool, formula result
            v = c.find(NS_MAIN + "v")
            text = v.text or "" if v is not None else ""
        if text == "":
            continue
        cells[(r, col)] = text
        max_row, max_col = max(max_row, r), max(max_col, col)

    return [[cells.get((r, col), "") for col in range(max_col + 1)]
            for r in range(1, max_row + 1)]


# --- Cell parsing -------------------------------------------------------------


def collapse(s):
    return re.sub(r"\s+", " ", s).strip()


def parse_examples(cell):
    """Column D: "Ex1: ...\\nEx2: ..." -> ["...", "..."]."""
    text = (cell or "").strip()
    if not text:
        return []
    parts = re.split(r"\s*(?:\r?\n)?\s*Ex\d+:\s*", text)
    return [p for p in (collapse(s) for s in parts) if p]


def parse_references(cell):
    """Column E: newline-separated reference lines. Stored RAW.

    Deliberate: a line like "ISO/IEC 27001:2022: Mandatory Clause: 4.1" carries
    colons inside the source name, so splitting source from reference is guesswork
    against an open-ended set of catalogs. v1 ships this data dormant (rendered in
    v2), and a fragile parse baked in now would be harder to correct later than no
    parse at all. v2's crosswalk work owns the structured split.
    """
    return [s for s in ((line or "").strip() for line in re.split(r"\r?\n", cell or "")) if s]


def build_hierarchy(rows):
    functions, cur_fn, cur_cat = [], None, None
    skipped = {"functionTerminators": 0, "withdrawnCategories": 0, "withdrawnSubcategories": 0}

    for i in range(2, len(rows)):                           # two header rows
        row = rows[i] if i < len(rows) else []
        cell = lambda n: (row[n] if n < len(row) else "") or ""   # noqa: E731
        a, b, c = cell(0).strip(), cell(1).strip(), cell(2).strip()
        examples, references = parse_examples(cell(3)), parse_references(cell(4))

        if a:
            m = RE_FUNCTION.match(a)
            if not m:
                raise SystemExit(f"row {i + 1}: unparseable Function cell: {a}")
            name, fid, description = m.group(1), m.group(2), m.group(3)
            if not description:
                skipped["functionTerminators"] += 1          # bare section terminator
                continue
            if fid not in FUNCTION_ORDER:
                raise SystemExit(f"row {i + 1}: unknown Function id {fid}")
            cur_fn = {"id": fid, "name": collapse(name), "description": collapse(description),
                      "informativeReferences": references, "categories": []}
            cur_cat = None
            functions.append(cur_fn)
            continue

        if b:
            if "[Withdrawn" in b:
                skipped["withdrawnCategories"] += 1
                cur_cat = None
                continue
            m = RE_CATEGORY.match(b)
            if not m:
                raise SystemExit(f"row {i + 1}: unparseable Category cell: {b}")
            name, cid, description = m.group(1), m.group(2), m.group(3)
            if not cur_fn:
                raise SystemExit(f"row {i + 1}: category {cid} before any function")
            if not cid.startswith(cur_fn["id"] + "."):
                raise SystemExit(f"row {i + 1}: category {cid} outside function {cur_fn['id']}")
            cur_cat = {"id": cid, "name": collapse(name), "description": collapse(description or ""),
                       "informativeReferences": references, "subcategories": []}
            cur_fn["categories"].append(cur_cat)
            continue

        if c:
            if "[Withdrawn" in c:
                skipped["withdrawnSubcategories"] += 1
                continue
            m = RE_SUBCATEGORY.match(c)
            if not m:
                raise SystemExit(f"row {i + 1}: unparseable Subcategory cell: {c}")
            sid, text = m.group(1), m.group(2)
            if not cur_cat:
                raise SystemExit(f"row {i + 1}: subcategory {sid} before any category")
            if not sid.startswith(cur_cat["id"] + "-"):
                raise SystemExit(f"row {i + 1}: subcategory {sid} outside category {cur_cat['id']}")
            cur_cat["subcategories"].append({"id": sid, "text": collapse(text), "examples": examples,
                                             "informativeReferences": references})

    return functions, skipped


# --- Integrity ----------------------------------------------------------------


def check_integrity(functions):
    """Assert the known-good shape. Fails before writing, never after."""
    problems = []

    def check(cond, msg):
        if not cond:
            problems.append(msg)

    cats = [c for f in functions for c in f["categories"]]
    subs = [s for c in cats for s in c["subcategories"]]

    check(len(functions) == 6, f"expected 6 functions, got {len(functions)}")
    check(len(cats) == 22, f"expected 22 categories, got {len(cats)}")
    check(len(subs) == 106, f"expected 106 subcategories, got {len(subs)}")

    order = ",".join(f["id"] for f in functions)
    check(order == ",".join(FUNCTION_ORDER), f"unexpected function order: {order}")

    for f in functions:
        n = sum(len(c["subcategories"]) for c in f["categories"])
        check(n == EXPECTED_PER_FUNCTION[f["id"]],
              f'{f["id"]}: expected {EXPECTED_PER_FUNCTION[f["id"]]} subcategories, got {n}')

    ids = [s["id"] for s in subs]
    check(len(set(ids)) == len(ids), "duplicate subcategory ids")
    cat_ids = [c["id"] for c in cats]
    check(len(set(cat_ids)) == len(cat_ids), "duplicate category ids")

    example_count = sum(len(s["examples"]) for s in subs)
    check(example_count == 363, f"expected 363 implementation examples, got {example_count}")

    no_examples = [s["id"] for s in subs if not s["examples"]]
    check(not no_examples, f'subcategories with no implementation example: {", ".join(no_examples)}')

    empty = [s["id"] for s in subs if not s["text"]]
    check(not empty, f'subcategories with empty text: {", ".join(empty)}')

    if problems:
        print("INGEST FAILED — integrity assertions did not hold:", file=sys.stderr)
        for p in problems:
            print("  - " + p, file=sys.stderr)
        raise SystemExit(1)

    return cats, subs, example_count


def main(argv):
    if len(argv) < 2:
        print("usage: ingest-csf-core.py <out-path> [xlsx-path]", file=sys.stderr)
        return 2
    out = argv[1]
    source = argv[2] if len(argv) > 2 else os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                        "csf-2.0.xlsx")

    functions, skipped = build_hierarchy(read_sheet_rows(source, SHEET))
    cats, subs, example_count = check_integrity(functions)

    with open(source, "rb") as fh:
        digest = hashlib.sha256(fh.read()).hexdigest()

    core = {
        "id": "nist-csf-2.0",
        "name": "NIST Cybersecurity Framework",
        "version": "2.0",
        # Provenance is recorded by content hash rather than a timestamp so that
        # regenerating from the same source produces a byte-identical file.
        "source": {
            "publication": "NIST CSWP 29 — The NIST Cybersecurity Framework (CSF) 2.0",
            "catalog": "NIST Cybersecurity and Privacy Reference Tool (CPRT) CSF 2.0 export",
            "file": "csf-2.0.xlsx",
            "sha256": digest,
            "note": "NIST publications are US Government works and are not subject to copyright.",
        },
        "notes": {
            "informativeReferences":
                "Stored as raw catalog lines exactly as published. Structured splitting into "
                "{source, reference} is deferred to the v2 crosswalk work: source names such as "
                "'ISO/IEC 27001:2022' contain colons, so any split rule would be guesswork against "
                "an open-ended set of catalogs. v1 carries this data but does not render it.",
            "tiers": "Populated by T0b from NIST CSWP 29. Tiers characterise rigor, never a maturity score.",
        },
        "tiers": None,
        "hierarchy": functions,
    }

    # ensure_ascii=False to match JSON.stringify, which emits raw UTF-8 rather than
    # \uXXXX escapes. The em dash in `source.publication` is the visible case.
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(core, indent=2, ensure_ascii=False) + "\n")

    per_fn = " ".join(f'{f["id"]}:{sum(len(c["subcategories"]) for c in f["categories"])}'
                      for f in functions)
    print("OK")
    print(f"  functions      {len(functions)}")
    print(f"  categories     {len(cats)}")
    print(f"  subcategories  {len(subs)}  ({per_fn})")
    print(f"  examples       {example_count}  "
          f'(min per subcategory: {min(len(s["examples"]) for s in subs)})')
    print(f'  subs w/ refs   {sum(1 for s in subs if s["informativeReferences"])}')
    print(f'  skipped        {skipped["functionTerminators"]} function terminators, '
          f'{skipped["withdrawnCategories"]} withdrawn categories, '
          f'{skipped["withdrawnSubcategories"]} withdrawn subcategories')
    print(f"  -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
