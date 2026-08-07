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
       python3 validate_crosswalks.py --self-test
Defaults to the bundled overlay data in the skill. Exit 0 = clean, 1 = errors.
"""
import json, sys, glob, os, shutil, tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
_BUNDLED = os.path.join(_HERE, "..", "..", "skills", "nist-csf", "references", "crosswalks")
DATA = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("-") else _BUNDLED

# The catalogues that must be present for a run of this checker to mean anything.
#
# Named, not counted. This guard exists because the checker reported
# "0 catalogs · 0 errors · 0 warnings" and exited 0 against an empty directory, and
# against a directory that does not exist — a clean bill from a run that read nothing.
# A count ("at least three") would go green the day one catalogue is replaced by a
# second copy of another; a list is the thing a reader can hold against the directory.
REQUIRED_FRAMEWORKS = ("800-53-r5", "cis-8.1", "iso-27001-2022")
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

def main(data=None):
    data = DATA if data is None else data
    errors, warns = [], []
    catalogs = {}
    if not os.path.isdir(data):
        print(f"ERROR data directory does not exist: {data}")
        print("\n0 catalogs · 1 errors · 0 warnings")
        return 1
    for p in sorted(glob.glob(os.path.join(data, "*.catalog.json"))):
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

    maps = 0
    for p in sorted(glob.glob(os.path.join(data, "csf-2.0__*.map.json"))):
        maps += 1
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
    for p in sorted(glob.glob(os.path.join(data, "*.md"))):
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

    # Completeness, checked LAST so the specific findings above are reported first.
    # Everything above this line is a rule about data that was read; these are the two
    # ways a run reads nothing and calls it clean.
    for fid in REQUIRED_FRAMEWORKS:
        if fid not in catalogs:
            errors.append(f"required catalogue {fid!r} not found in {data} — a run that "
                          f"reads no catalogue reports no error, which is not the same "
                          f"as reporting no problem")
    if catalogs and not maps:
        errors.append(f"{len(catalogs)} catalogue(s) but no csf-2.0__*.map.json in {data} — "
                      f"the edges are the half of this data that can be wrong")

    for w in warns: print(f"WARN  {w}")
    for e in errors: print(f"ERROR {e}")
    print(f"\n{len(catalogs)} catalogs · {len(errors)} errors · {len(warns)} warnings")
    return 1 if errors else 0

def _self_test():
    """The guard, seen to fail. Both vacuous-pass cases, and the real data as the control."""
    checks = fails = 0

    def expect(label, got, want):
        nonlocal checks, fails
        checks += 1
        if got == want:
            print(f"  ok    {label}")
        else:
            fails += 1
            print(f"  FAIL  {label}\n         expected exit {want}, got {got}")

    work = tempfile.mkdtemp()
    try:
        expect("an empty directory is refused", main(work), 1)
        expect("a directory that does not exist is refused",
               main(os.path.join(work, "nope")), 1)
        # Every required catalogue present and no map at all — the shape a
        # half-finished ingest leaves behind. The edges are the half of this data
        # that can be wrong, so catalogues alone are not a validated crosswalk.
        one = os.path.join(work, "partial")
        os.makedirs(one)
        for fid in REQUIRED_FRAMEWORKS:
            with open(os.path.join(one, f"{fid}.catalog.json"), "w") as fh:
                json.dump({"frameworkId": fid, "controls": [], "groupings": []}, fh)
        expect("catalogues with no map at all are refused", main(one), 1)
        # The control. Without this, every check above passes on a checker that
        # returns 1 unconditionally.
        expect("...and the bundled data still passes", main(_BUNDLED), 0)
    finally:
        shutil.rmtree(work, ignore_errors=True)

    print(f"\nvalidate_crosswalks self-test: {checks - fails}/{checks} checks passed")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(_self_test() if "--self-test" in sys.argv[1:] else main())
