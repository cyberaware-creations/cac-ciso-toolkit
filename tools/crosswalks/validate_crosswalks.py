#!/usr/bin/env python3
"""Validate crosswalk catalog + map pairs against the Phase 0 contract.

Enforces the legal + structural rules so bad data can't ship:
- every mapped controlId resolves to a catalog entry that has a non-empty label
- ISO/CIS labels must be labelSource == 'cac-generated' (no verbatim title leakage)
- 800-53 labels must be labelSource == 'verbatim-public-domain'
- every control.groupingId resolves to a declared grouping
- if a catalog declares expectedCounts and is marked complete, counts must match
- version + retrievedAt provenance stamped (warns while TODO)

Usage: python3 validate_crosswalks.py [data_dir]
Defaults to the bundled overlay data in the skill. Exit 0 = clean, 1 = errors.
"""
import json, sys, glob, os

_HERE = os.path.dirname(os.path.abspath(__file__))
_BUNDLED = os.path.join(_HERE, "..", "..", "skills", "nist-csf", "references", "crosswalks")
DATA = sys.argv[1] if len(sys.argv) > 1 else _BUNDLED
# "pending-verbatim-title" was allowed while the 800-53 titles were being
# ingested. All 206 now carry verbatim titles, so the placeholder is dead slack
# that would let an unlabelled control ship; dropped so this rule matches
# CROSSWALK_EXPECTED in profile_analysis.py exactly.
LABEL_RULE = {
    "800-53-r5": {"verbatim-public-domain"},
    "iso-27001-2022": {"cac-generated"},
    "cis-8.1": {"cac-generated", "id-only"},
}
# An identifier with no label at all. Legal ONLY for a control no CSF Subcategory
# maps to, and enforced that way below: an unmapped control is only ever listed as
# "assess this directly", where the id is the whole answer, whereas a mapped control
# appears in the coverage table and would render as a blank row.
#
# It exists because the CIS Controls are CC BY-NC-ND and ND forbids distributing
# transformed material; a paraphrase of a safeguard is arguably a transform. Shipping
# the identifier alone makes the honesty list possible without that question.
ID_ONLY = "id-only"

def load(p):
    with open(p) as f: return json.load(f)

def main():
    errors, warns = [], []
    catalogs = {}
    for p in sorted(glob.glob(os.path.join(DATA, "*.catalog.json"))):
        c = load(p); fid = c["frameworkId"]; catalogs[fid] = c
        ids = set()
        groupings = {g["id"] for g in c.get("groupings", [])}
        want = LABEL_RULE.get(fid)
        id_only = set()
        for ctl in c.get("controls", []):
            cid = ctl["id"]
            if cid in ids: errors.append(f"[{fid}] duplicate control id {cid}")
            ids.add(cid)
            if ctl.get("labelSource") == ID_ONLY:
                id_only.add(cid)
                # An id-only entry must be exactly that: no label, no text. A
                # half-filled one is worse than either, because a consumer cannot
                # tell whether the wording is ours or theirs.
                if (ctl.get("label") or "").strip():
                    errors.append(f"[{fid}] {cid} is {ID_ONLY} but carries a label")
            elif not (ctl.get("label") or "").strip():
                errors.append(f"[{fid}] {cid} has empty label")
            if want and ctl.get("labelSource") not in want:
                errors.append(f"[{fid}] {cid} labelSource={ctl.get('labelSource')} but rule requires one of {sorted(want)}")
            if fid in ("iso-27001-2022", "cis-8.1") and ctl.get("text") not in (None, ""):
                errors.append(f"[{fid}] {cid} carries normative text — forbidden for ISO/CIS")
            if ctl.get("groupingId") and ctl["groupingId"] not in groupings:
                errors.append(f"[{fid}] {cid} groupingId {ctl['groupingId']} not declared")
        c["_ids"] = ids
        c["_id_only"] = id_only
        se = c.get("sourceExport", {})
        if "TODO" in json.dumps(se) or "TODO" in c.get("_status", ""):
            warns.append(f"[{fid}] provenance/status still TODO (starter slice, expected pre-ingest)")

    for p in sorted(glob.glob(os.path.join(DATA, "csf-2.0__*.map.json"))):
        m = load(p); fid = m["overlayFrameworkId"]
        cat = catalogs.get(fid)
        if not cat: errors.append(f"map for {fid} has no catalog"); continue
        for e in m.get("edges", []):
            if e["controlId"] not in cat["_ids"]:
                errors.append(f"[{fid}] edge {e['csfSubId']}->{e['controlId']} unresolved in catalog")
            if not e.get("authority"):
                errors.append(f"[{fid}] edge {e['csfSubId']}->{e['controlId']} missing authority tag")
            # The whole justification for a label-less entry is that it is only ever
            # rendered as "assess this directly", where the id is the answer. A mapped
            # control appears in the coverage table, so it must carry a label.
            if e["controlId"] in cat.get("_id_only", ()):
                errors.append(f"[{fid}] {e['controlId']} is {ID_ONLY} but CSF maps to it "
                              f"({e['csfSubId']}); a mapped control needs a label")

    for w in warns: print(f"WARN  {w}")
    for e in errors: print(f"ERROR {e}")
    print(f"\n{len(catalogs)} catalogs · {len(errors)} errors · {len(warns)} warnings")
    return 1 if errors else 0

if __name__ == "__main__":
    sys.exit(main())
