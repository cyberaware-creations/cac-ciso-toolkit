#!/usr/bin/env python3
"""Validate crosswalk catalog + map pairs against the Phase 0 contract.

Enforces the legal + structural rules so bad data can't ship:
- every mapped controlId resolves to a catalog entry that has a non-empty label
- ISO/CIS labels must be labelSource == 'cac-generated' (no verbatim title leakage)
- ISO/CIS controls must carry no normative text — the licensing gate
- 800-53 labels must be labelSource == 'verbatim-public-domain'
- every control.groupingId resolves to a declared grouping
- every mapped edge resolves and carries an authority tag
- version + retrievedAt provenance stamped (warns while TODO)

The list above once also promised "if a catalog declares expectedCounts and is marked complete,
counts must match". No catalogue declares expectedCounts and no code here reads it, so the line
described a rule that has never run. Removed rather than implemented: inventing an enforcement
contract for data that does not exist is how a docstring becomes the only place a rule lives.

Usage: python3 validate_crosswalks.py [data_dir]
       python3 validate_crosswalks.py --self-test
Defaults to the bundled overlay data in the skill. Exit 0 = clean, 1 = errors.
"""
import contextlib, io, json, sys, glob, os, re, shutil, tempfile

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

# ---------------------------------------------------------------------------
# Self-test fixtures.
#
# The suite below used to be four checks, all of them about the two ways this file reads
# nothing and calls it clean. Every rule in the per-control loop — where nearly all the logic
# lives — went untested: BL-204's mutation sweep suppressed each guard in turn so it could never
# report, and ten of the twelve left `--self-test` green. Line 64, the ISO/CIS normative-text
# rule, was among them. That is the licensing gate, it runs in CI on every push, and nothing
# tested that it fires.
#
# It could not, either, against the shipped data: the real catalogues are clean, so this file
# prints `3 catalogs · 0 errors · 0 warnings` whether its guards work or not. A guard needs
# something to catch, and clean data is exactly the condition under which a broken one is
# invisible. Hence synthetic catalogues, built valid and then broken one rule at a time.
#
# Two things each case asserts, neither sufficient alone:
#   - the SPECIFIC message, not just a non-zero exit. A fixture with a duplicate control id
#     also trips the required-catalogue rule if it is built carelessly, and then the duplicate
#     guard is proved by a different guard's finding — one property standing in for another.
#   - the error and warning COUNTS, so a fixture cannot pass by failing for two reasons.
#
# And most rules get an acceptance case as well as a firing one, because a guard that fires on
# everything is as useless as one that fires on nothing, and only the acceptance case can tell
# them apart (GP-1.10).

_LABEL_OK = {"800-53-r5": "verbatim-public-domain",
             "iso-27001-2022": "cac-generated",
             "cis-8.1": "cac-generated"}
_SUMMARY = re.compile(r"^(\d+) catalogs · (\d+) errors · (\d+) warnings$", re.M)


def _ctl(fid, cid, **over):
    c = {"id": cid, "label": f"{cid} — a label in our own words", "groupingId": "G1",
         "labelSource": _LABEL_OK.get(fid, "cac-generated"), "text": None}
    c.update(over)
    return c


def _cat(fid, controls=None):
    return {"frameworkId": fid, "name": f"fixture {fid}", "version": "fixture-1",
            "sourceExport": {"tool": "fixture", "retrievedAt": "2026-08-09"},
            "groupings": [{"id": "G1", "label": "Grouping one"}],
            # Two controls, not one: `if cid in ids` cannot be shown to discriminate against a
            # catalogue that only ever holds a single control.
            "controls": controls if controls is not None
            else [_ctl(fid, f"{fid}-1"), _ctl(fid, f"{fid}-2")]}


def _map(fid, edges=None):
    return {"csfFrameworkId": "csf-2.0", "overlayFrameworkId": fid,
            "direction": "csf-to-overlay", "mappingAuthority": "fixture",
            "sourceExport": {"tool": "fixture", "retrievedAt": "2026-08-09"},
            "edges": edges if edges is not None
            else [{"csfSubId": "GV.OC-01", "controlId": f"{fid}-1",
                   "authority": "fixture-authored"}]}


def _build(root, mutate=None):
    """A valid three-framework directory, then one deliberate defect."""
    os.makedirs(root)
    cats = {fid: _cat(fid) for fid in REQUIRED_FRAMEWORKS}
    maps = {fid: _map(fid) for fid in REQUIRED_FRAMEWORKS}
    docs = {}
    if mutate:
        mutate(cats, maps, docs)
    for fid, c in cats.items():
        with open(os.path.join(root, f"{fid}.catalog.json"), "w") as fh:
            json.dump(c, fh)
    for fid, m in maps.items():
        with open(os.path.join(root, f"csf-2.0__{fid}.map.json"), "w") as fh:
            json.dump(m, fh)
    for name, body in docs.items():
        with open(os.path.join(root, name), "w", encoding="utf-8") as fh:
            fh.write(body)
    return root


def _self_test():
    """The guard, seen to fail — every rule in turn, against data built to break it."""
    checks = fails = 0
    work = tempfile.mkdtemp()
    seq = [0]

    def report(label, why=None):
        nonlocal checks, fails
        checks += 1
        if why is None:
            print(f"  ok    {label}")
        else:
            fails += 1
            print(f"  FAIL  {label}\n         {why}")

    def run(data):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = main(data)
        out = buf.getvalue()
        m = _SUMMARY.search(out)
        return rc, out, (int(m.group(2)), int(m.group(3))) if m else (None, None)

    def case(label, mutate, needle=None, errors=1, warnings=0):
        """Build the fixture, run, and assert the message AND the counts."""
        seq[0] += 1
        rc, out, (nerr, nwarn) = run(_build(os.path.join(work, f"c{seq[0]}"), mutate))
        want_rc = 1 if errors else 0
        if rc != want_rc:
            return report(label, f"expected exit {want_rc}, got {rc}\n{out.rstrip()}")
        if (nerr, nwarn) != (errors, warnings):
            return report(label, f"expected {errors} error(s) and {warnings} warning(s), "
                                 f"got {nerr} and {nwarn}\n{out.rstrip()}")
        if needle is not None and needle not in out:
            return report(label, f"expected {needle!r} in the output\n{out.rstrip()}")
        report(label)

    def raw(label, data, want):
        rc, out, _ = run(data)
        report(label, None if rc == want else f"expected exit {want}, got {rc}\n{out.rstrip()}")

    try:
        # -- the control. Everything below is a departure from this one directory. -----------
        case("a well-formed three-framework directory passes", None, errors=0)

        # -- the licensing gate, first, because it is the rule with a lawyer behind it -------
        for fid in ("iso-27001-2022", "cis-8.1"):
            def carries_text(cats, maps, docs, fid=fid):
                cats[fid]["controls"][0]["text"] = "The organization shall establish a policy."
            case(f"{fid}: a control carrying normative text is refused", carries_text,
                 "carries normative text")

        def text_on_80053(cats, maps, docs):
            cats["800-53-r5"]["controls"][0]["text"] = "a. Develop, document, and disseminate…"
        case("800-53 may carry its text — it is public domain", text_on_80053, errors=0)

        def empty_text(cats, maps, docs):
            cats["iso-27001-2022"]["controls"][0]["text"] = ""
        case("an empty text field is an absent one, not a breach", empty_text, errors=0)

        # -- the per-control rules ------------------------------------------------------------
        def dup(cats, maps, docs):
            cats["cis-8.1"]["controls"][1]["id"] = cats["cis-8.1"]["controls"][0]["id"]
        case("a duplicate control id is refused", dup, "duplicate control id")

        def blank_label(cats, maps, docs):
            cats["800-53-r5"]["controls"][0]["label"] = ""
        case("an empty label is refused", blank_label, "has empty label")

        def spaces_label(cats, maps, docs):
            cats["800-53-r5"]["controls"][0]["label"] = "   "
        case("a whitespace-only label is refused", spaces_label, "has empty label")

        def no_label(cats, maps, docs):
            del cats["800-53-r5"]["controls"][0]["label"]
        case("a control with no label field at all is refused", no_label, "has empty label")

        def verbatim_iso(cats, maps, docs):
            cats["iso-27001-2022"]["controls"][0]["labelSource"] = "verbatim-public-domain"
        case("an ISO label claiming to be verbatim is refused", verbatim_iso,
             "labelSource=verbatim-public-domain")

        def generated_80053(cats, maps, docs):
            cats["800-53-r5"]["controls"][0]["labelSource"] = "cac-generated"
        case("an 800-53 label that is not the verbatim title is refused", generated_80053,
             "labelSource=cac-generated")

        def unknown_framework(cats, maps, docs):
            # No LABEL_RULE entry, so `want` is None and the provenance rule must stand down
            # rather than reject everything it has no rule for.
            cats["soc2-2017"] = _cat("soc2-2017", [_ctl("soc2-2017", "CC1.1",
                                                        labelSource="third-party-supplied")])
        case("a framework with no label rule is left alone", unknown_framework, errors=0)

        def bad_grouping(cats, maps, docs):
            cats["cis-8.1"]["controls"][0]["groupingId"] = "G-nope"
        case("a groupingId that is not declared is refused", bad_grouping, "not declared")

        def no_grouping(cats, maps, docs):
            del cats["cis-8.1"]["controls"][0]["groupingId"]
        case("a control in no grouping is allowed", no_grouping, errors=0)

        # -- provenance warns, and warning is not failing --------------------------------------
        def todo_export(cats, maps, docs):
            cats["cis-8.1"]["sourceExport"]["retrievedAt"] = "TODO"
        case("a TODO in sourceExport warns and does not fail", todo_export,
             "provenance/status still TODO", errors=0, warnings=1)

        def todo_status(cats, maps, docs):
            cats["cis-8.1"]["_status"] = "TODO — starter slice"
        case("a TODO in _status warns too", todo_status,
             "provenance/status still TODO", errors=0, warnings=1)

        # -- the edges, which are the half of this data the catalogues cannot check ------------
        def orphan_map(cats, maps, docs):
            maps["ghost-framework"] = _map("ghost-framework", [
                {"csfSubId": "GV.OC-01", "controlId": "X-1", "authority": "fixture-authored"}])
        case("a map with no catalogue behind it is refused", orphan_map, "has no catalog")

        def unresolved_edge(cats, maps, docs):
            maps["iso-27001-2022"]["edges"][0]["controlId"] = "A.99.99"
        case("an edge pointing at no control is refused", unresolved_edge,
             "unresolved in catalog")

        def no_authority(cats, maps, docs):
            del maps["800-53-r5"]["edges"][0]["authority"]
        case("an edge with no authority tag is refused", no_authority, "missing authority tag")

        def blank_authority(cats, maps, docs):
            maps["800-53-r5"]["edges"][0]["authority"] = ""
        case("an edge whose authority is blank is refused", blank_authority,
             "missing authority tag")

        # -- the prose rule, which the JSON rules cannot see -----------------------------------
        def official_column(cats, maps, docs):
            docs["label-style.md"] = ("# Labels\n\n"
                                      "| Identifier | Our label | Official title |\n"
                                      "|---|---|---|\n"
                                      "| A.5.1 | Approved policy set | … |\n")
        case("a table column headed 'official title' is refused", official_column,
             "a table column headed")

        def disclaimed_column(cats, maps, docs):
            docs["label-style.md"] = ("# Labels\n\n"
                                      "| Identifier | Our label | Not the official title |\n"
                                      "|---|---|---|\n"
                                      "| A.5.1 | Approved policy set | our wording |\n")
        case("a column that disclaims the official title is allowed", disclaimed_column,
             errors=0)

        def official_in_prose(cats, maps, docs):
            docs["README.md"] = ("# Crosswalks\n\nWe never reproduce the official ISO or CIS "
                                 "titles; the reader uses their own licensed copy.\n")
        case("the word 'official' outside a table is prose, not a column", official_in_prose,
             errors=0)

        # -- and the two ways a run reads nothing and calls it clean ---------------------------
        def missing_framework(cats, maps, docs):
            del cats["cis-8.1"]
            del maps["cis-8.1"]
        case("a required catalogue that is absent is refused", missing_framework,
             "required catalogue 'cis-8.1' not found")

        def no_maps(cats, maps, docs):
            maps.clear()
        case("catalogues with no map at all are refused", no_maps,
             "the edges are the half of this data that can be wrong")

        empty = os.path.join(work, "empty")
        os.makedirs(empty)
        raw("an empty directory is refused", empty, 1)
        raw("a directory that does not exist is refused", os.path.join(work, "nope"), 1)

        # The control on the whole suite. Without it, every check above passes on a checker
        # that returns 1 unconditionally.
        raw("...and the bundled data still passes", _BUNDLED, 0)
    finally:
        shutil.rmtree(work, ignore_errors=True)

    print(f"\nvalidate_crosswalks self-test: {checks - fails}/{checks} checks passed")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(_self_test() if "--self-test" in sys.argv[1:] else main())
