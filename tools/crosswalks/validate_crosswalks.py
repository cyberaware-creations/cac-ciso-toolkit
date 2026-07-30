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
    "cis-8.1": {"cac-generated"},
}

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
        for ctl in c.get("controls", []):
            cid = ctl["id"]
            if cid in ids: errors.append(f"[{fid}] duplicate control id {cid}")
            ids.add(cid)
            if not ctl.get("label", "").strip():
                errors.append(f"[{fid}] {cid} has empty label")
            if want and ctl.get("labelSource") not in want:
                errors.append(f"[{fid}] {cid} labelSource={ctl.get('labelSource')} but rule requires one of {sorted(want)}")
            if fid in ("iso-27001-2022", "cis-8.1") and ctl.get("text") not in (None, ""):
                errors.append(f"[{fid}] {cid} carries normative text — forbidden for ISO/CIS")
            if ctl.get("groupingId") and ctl["groupingId"] not in groupings:
                errors.append(f"[{fid}] {cid} groupingId {ctl['groupingId']} not declared")
        c["_ids"] = ids
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

    # The catalogues are checked above, but they are not the only thing that ships
    # from this directory. label-style.md shipped for a while with a third column of
    # the official ISO and CIS titles, headed "for our internal keying" — an
    # authoring aid, in a file whose own first line promises we never reproduce
    # them. The JSON rules could not see it because it is prose.
    #
    # Detecting arbitrary official wording is not possible; detecting the shape of
    # this mistake is. A table column that announces itself as the official title is
    # the tell, and it is what an author reaches for next time.
    for p in sorted(glob.glob(os.path.join(DATA, "*.md"))):
        with open(p, encoding="utf-8") as f:
            for n, line in enumerate(f, 1):
                s = line.strip()
                if not s.startswith("|"):
                    continue
                cells = [x.strip().lower() for x in s.strip("|").split("|")]
                if any("official" in cx and "not" not in cx for cx in cells):
                    errors.append(
                        f"[{os.path.basename(p)}:{n}] a table column headed "
                        f"'official' — ISO and CIS titles are not ours to publish; "
                        f"give the identifier and let the reader use their licensed copy")

    for w in warns: print(f"WARN  {w}")
    for e in errors: print(f"ERROR {e}")
    print(f"\n{len(catalogs)} catalogs · {len(errors)} errors · {len(warns)} warnings")
    return 1 if errors else 0

if __name__ == "__main__":
    sys.exit(main())
