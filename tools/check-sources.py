#!/usr/bin/env python3
"""CAC-RW-1 — every skill declares the sources it cites, and the citations do not drift.

The standard is written up in tools/sources-schema.md; this is its implementation.

Why this exists. Before v0.52.0 exactly two source families in the product carried a freshness
stamp. Every legal citation and every NIST publication was undated at the point of use, and the
v0.48.0-v0.51.0 verification pass found twelve defects across six families -- every one an
AMENDMENT failure, where the citation was right when written and the instrument moved underneath
it. None would have been caught by re-reading the repo. This manifest records what to open and
when it was last opened.

Four checks:

  C1  presence  -- every skill has a parsing sources.json (an empty `sources` array is valid)
  C2  shape     -- required fields present, ids unique per skill, checkedOn sane, gate coherent
  C3  rendered  -- a `renderedAs` string appears byte-for-byte in the files the row claims
  C4  usedFor   -- every path a row lists exists in the tree

C3 is the one this standard is named for. Renderers keep their literal string rather than
reading this file at runtime (RW-1.5), because every shipped script here runs standalone; the
byte-equality check is what keeps the two copies honest.

Exit 0 when clean, 1 otherwise.

Usage: tools/check-sources.py [--self-test] [--release-gate]
"""
import datetime
import json
import os
import re
import sys

REQUIRED = ("id", "label", "publisher", "instrument", "version",
            "checkedOn", "checkedBy", "gated", "usedFor")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
USAGE = "usage: tools/check-sources.py [--self-test] [--release-gate]"


def _today():
    return datetime.date.today()


def skill_dirs(root):
    """Every directory holding a SKILL.md. Discovered, never listed -- a skill added without a
    manifest must fail rather than be silently absent, which is the same reasoning
    prove-guards.sh applies to guards."""
    base = os.path.join(root, "skills")
    if not os.path.isdir(base):
        return []
    return sorted(d for d in os.listdir(base)
                  if os.path.isfile(os.path.join(base, d, "SKILL.md")))


def load(root, skill):
    """Returns (doc, error). A missing or unparsable manifest is an error, not an empty doc."""
    path = os.path.join(root, "skills", skill, "sources.json")
    if not os.path.isfile(path):
        return None, "no sources.json (an empty `sources` array is the honest answer for a " \
                     "skill that cites nothing -- a missing file is not)"
    try:
        with open(path, encoding="utf-8") as fh:
            doc = json.load(fh)
    except (OSError, ValueError) as exc:
        return None, "could not be read: %s" % exc
    if not isinstance(doc, dict) or not isinstance(doc.get("sources"), list):
        return None, "must be an object with a `sources` array"
    return doc, None


def check_shape(skill, doc, today):
    """C2. Every problem is collected rather than raised, so one run reports all of them."""
    problems, seen = [], set()
    for i, row in enumerate(doc["sources"]):
        where = "%s sources[%d]" % (skill, i)
        if not isinstance(row, dict):
            problems.append("%s is not an object" % where)
            continue
        rid = row.get("id")
        if isinstance(rid, str) and rid.strip():
            where = "%s/%s" % (skill, rid)
            if rid in seen:
                problems.append("%s: duplicate id within the skill" % where)
            seen.add(rid)
        for field in REQUIRED:
            if field not in row:
                problems.append("%s: missing `%s`" % (where, field))
            elif field == "gated":
                if not isinstance(row[field], bool):
                    problems.append("%s: `gated` must be true or false" % where)
            elif field == "usedFor":
                if not isinstance(row[field], list) or not row[field]:
                    problems.append("%s: `usedFor` must be a non-empty list" % where)
            elif not isinstance(row[field], str) or not row[field].strip():
                problems.append("%s: `%s` is empty" % (where, field))
        on = row.get("checkedOn")
        if isinstance(on, str) and DATE_RE.match(on):
            try:
                d = datetime.date(*(int(p) for p in on.split("-")))
                if d > today:
                    problems.append("%s: `checkedOn` %s is in the future" % (where, on))
            except ValueError:
                problems.append("%s: `checkedOn` %s is not a real date" % (where, on))
        elif "checkedOn" in row:
            problems.append("%s: `checkedOn` must be YYYY-MM-DD" % where)
        # RW-1.8 -- `unverified` is an allowed and load-bearing value for checkedBy. Most rows
        # in the first manifest record a citation nobody has yet read against its primary
        # source, and saying so is the entire point of the exercise: a manifest that stamped
        # every row as checked on the day it was authored would be a worse lie than the
        # undated citations it replaced. What an unverified row may NOT be is `gated` -- the
        # release gate would then be measuring the age of a check that never happened.
        if row.get("checkedBy") == "unverified":
            if row.get("gated") is True:
                problems.append("%s: `checkedBy` is unverified, so `gated` cannot be true -- the "
                                "gate would be timing a check that never happened" % where)
            # An unverified row must say WHY. Without this the value degrades into a shrug, and
            # the next maintainer cannot tell "nobody got to it" from "the source is paywalled
            # and no amount of trying will change that". Both remaining rows in this repo are
            # the second kind, and knowing that saves someone an afternoon.
            why = row.get("whyUnverified")
            if not isinstance(why, str) or not why.strip():
                problems.append("%s: `checkedBy` is unverified, so `whyUnverified` is required "
                                "-- say what blocked it, or it reads as nobody having tried"
                                % where)
        # RW-1.6 -- a gated row the release gate cannot evaluate is worse than an ungated one,
        # because it looks supervised and is not.
        if row.get("gated") is True:
            iv = row.get("reviewIntervalDays")
            if not isinstance(iv, int) or isinstance(iv, bool) or iv <= 0:
                problems.append("%s: `gated` is true so `reviewIntervalDays` must be a "
                                "positive integer" % where)
    return problems


def check_used_for(root, skill, doc):
    """C4. A manifest that has drifted from the tree describes a repo that no longer exists."""
    problems = []
    for row in doc["sources"]:
        if not isinstance(row, dict) or not isinstance(row.get("usedFor"), list):
            continue
        for rel in row["usedFor"]:
            if not isinstance(rel, str):
                continue
            if not os.path.exists(os.path.join(root, "skills", skill, rel)):
                problems.append("%s/%s: usedFor names %s, which is not in the tree"
                                % (skill, row.get("id", "?"), rel))
    return problems


def check_rendered(root, skill, doc):
    """C3. `renderedAs` must appear byte-for-byte in at least one file the row claims.

    Byte-for-byte and not normalised: the whole point is to catch the character that drifted.
    Searching only the row's own `usedFor` files rather than the whole skill is deliberate --
    it makes the row say where its citation lives, so a reader can find it without grepping.
    """
    problems = []
    for row in doc["sources"]:
        if not isinstance(row, dict):
            continue
        rendered = row.get("renderedAs")
        if rendered is None:
            continue  # RW-1.4 -- absence is meaningful, not incomplete
        if not isinstance(rendered, str) or not rendered.strip():
            problems.append("%s/%s: `renderedAs` is present but empty -- omit it instead"
                            % (skill, row.get("id", "?")))
            continue
        found = False
        for rel in row.get("usedFor") or []:
            path = os.path.join(root, "skills", skill, rel)
            try:
                with open(path, encoding="utf-8") as fh:
                    if rendered in fh.read():
                        found = True
                        break
            except (OSError, UnicodeDecodeError):
                continue
        if not found:
            problems.append("%s/%s: renderedAs %r appears in none of its usedFor files -- "
                            "either the renderer drifted or the manifest did"
                            % (skill, row.get("id", "?"), rendered[:70]))
    return problems


_DNC_EXEMPT = ("CHANGELOG.md", "docs/", "research/", "tools/do-not-cite.json",
               "tools/check-sources.py", "tools/sources-schema.md")
_DNC_NAMES = ("NOTICE", "README")
# How far either side of a hit a withdrawal marker may sit and still count as "discussing"
# rather than "citing". A paragraph, roughly. Same-line-only was too tight -- the honest form
# is often "X is withdrawn.\nUse Y instead." -- and whole-file was far too loose, since one
# mention of the word "superseded" anywhere would excuse every bare citation in the document.
_DNC_WINDOW = 320


def check_do_not_cite(root="."):
    """C5. A withdrawn publication may be discussed, never cited as current.

    sources.json watches what a skill DOES cite and structurally cannot see a publication the
    skill has not cited yet -- and that is the more dangerous class, because the defect arrives
    fresh rather than sitting in text somebody could review. SP 800-61 Rev. 2 is the worked
    example: withdrawn, and its four-phase incident lifecycle is still repeated by nearly every
    secondary source, so the first author to write incident-response content reaches for it by
    reflex.

    The rule is not a ban on the string. Naming a withdrawn document in order to say it is
    withdrawn is exactly what this repo should do, and this file does it constantly. What fails
    is the string with no withdrawal marker near it -- a citation, rather than a caution.
    """
    path = os.path.join(root, "tools", "do-not-cite.json")
    if not os.path.isfile(path):
        print("ERROR: tools/do-not-cite.json is missing; C5 checked nothing.")
        return False
    try:
        with open(path, encoding="utf-8") as fh:
            doc = json.load(fh)
        entries = doc["entries"]
        markers = [m.lower() for m in doc["markers"]]
        pats = [(e, re.compile(e["pattern"], re.I)) for e in entries]
    except (OSError, ValueError, KeyError, re.error) as exc:
        print("ERROR: tools/do-not-cite.json could not be used: %s" % exc)
        return False
    if not pats:
        print("ERROR: do-not-cite.json lists no entries; C5 would pass vacuously.")
        return False

    problems, scanned = [], 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in (".git", "__pycache__", "node_modules")]
        for fn in filenames:
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, root).replace(os.sep, "/")
            if any(rel == e or rel.startswith(e) for e in _DNC_EXEMPT):
                continue
            if (os.path.splitext(fn)[1].lower() not in (".md", ".py", ".json", ".sh")
                    and fn not in _DNC_NAMES):
                continue
            try:
                with open(full, encoding="utf-8") as fh:
                    text = fh.read()
            except (OSError, UnicodeDecodeError):
                continue
            scanned += 1
            low = text.lower()
            for entry, pat in pats:
                for m in pat.finditer(text):
                    lo = max(0, m.start() - _DNC_WINDOW)
                    if any(k in low[lo:m.end() + _DNC_WINDOW] for k in markers):
                        continue  # discussed, not cited
                    line = text.count("\n", 0, m.start()) + 1
                    problems.append("%s:%d: %s (%s) cited with no withdrawal marker nearby "
                                    "— use %s"
                                    % (rel, line, m.group(0).strip(), entry["status"],
                                       entry["supersededBy"].split(" — ")[0]))
    if not scanned:
        print("ERROR: the do-not-cite scan read no files; its glob stopped matching.")
        return False
    if problems:
        print("ERROR: withdrawn or superseded publications cited as current (CAC-RW-1.9):")
        for p in problems:
            print("         %s" % p)
        print("       Naming one to say it is withdrawn is fine — put the word near it. "
              "Citing one as guidance is not. See tools/do-not-cite.json.")
        return False
    print("do-not-cite: %d file(s), %d withdrawn publication(s) watched, none cited as current."
          % (scanned, len(entries)))
    return True


def check_sources(root="."):
    skills = skill_dirs(root)
    if not skills:
        print("ERROR: no skills found; the layout moved and this checked nothing.")
        return False
    problems, rows, unverified = [], 0, 0
    for skill in skills:
        doc, err = load(root, skill)
        if err:
            problems.append("%s: %s" % (skill, err))
            continue
        rows += len(doc["sources"])
        unverified += sum(1 for r in doc["sources"]
                          if isinstance(r, dict) and r.get("checkedBy") == "unverified")
        problems.extend(check_shape(skill, doc, _today()))
        problems.extend(check_used_for(root, skill, doc))
        problems.extend(check_rendered(root, skill, doc))
    if problems:
        print("ERROR: source manifest problems (CAC-RW-1):")
        for p in problems:
            print("         %s" % p)
        print("       See tools/sources-schema.md.")
        return False
    # Printed on every run, not buried: the count of citations nobody has read against the
    # primary source is the number this whole standard exists to drive down, and a manifest
    # that reported only its own green tick would hide it.
    print("sources: %d skill(s), %d declared source(s), citations match their renderers."
          % (len(skills), rows))
    if unverified:
        print("         %d of %d not yet verified against a primary source "
              "(checkedBy: unverified) — none of them gated." % (unverified, rows))
    return True


def release_gate(root="."):
    """RW-1.6. A gated source older than its interval blocks the release."""
    overrides = {}
    opath = os.path.join(root, "tools", "release-overrides.json")
    if os.path.isfile(opath):
        try:
            with open(opath, encoding="utf-8") as fh:
                raw = json.load(fh)
            for o in (raw.get("overrides") or []):
                # An override with no reason is not an override. Owner and date are required
                # for the same reason the exceptions-register refuses an unapproved acceptance:
                # somebody has to be answerable for the decision to ship anyway.
                if all(isinstance(o.get(k), str) and o[k].strip()
                       for k in ("source", "reason", "owner", "date")):
                    overrides[o["source"]] = o
        except (OSError, ValueError) as exc:
            print("ERROR: tools/release-overrides.json could not be read: %s" % exc)
            return False
    today, stale, used = _today(), [], []
    for skill in skill_dirs(root):
        doc, err = load(root, skill)
        if err:
            print("ERROR: %s: %s" % (skill, err))
            return False
        for row in doc["sources"]:
            if not isinstance(row, dict) or row.get("gated") is not True:
                continue
            on, iv = row.get("checkedOn"), row.get("reviewIntervalDays")
            if not (isinstance(on, str) and DATE_RE.match(on) and isinstance(iv, int)):
                continue  # C2 already reports this; the gate does not double-report
            age = (today - datetime.date(*(int(p) for p in on.split("-")))).days
            if age <= iv:
                continue
            key = "%s/%s" % (skill, row["id"])
            ov = overrides.get(key)
            if ov:
                used.append("%s -- %s (%s, %s)" % (key, ov["reason"], ov["owner"], ov["date"]))
            else:
                stale.append("%s: checked %s, %d days ago, interval %d"
                             % (key, on, age, iv))
    for u in used:
        print("  override  %s" % u)
    if stale:
        print("ERROR: gated sources are past their review interval (CAC-RW-1.6):")
        for s in stale:
            print("         %s" % s)
        print("       Re-verify against the primary source and update `checkedOn`, or record "
              "an override in tools/release-overrides.json with a reason, owner and date.")
        return False
    print("release-gate: every gated source is within its review interval.")
    return True


def _self_test():
    import shutil
    import tempfile
    checks = []

    def ok(cond, label):
        checks.append(bool(cond))
        print("{:<4} {}".format("PASS" if cond else "FAIL", label))

    def tree(tmp, name, sources, extra=None):
        """A minimal repo: one skill, its SKILL.md, and whatever files the rows claim."""
        root = os.path.join(tmp, name)
        sk = os.path.join(root, "skills", "demo")
        os.makedirs(sk)
        with open(os.path.join(sk, "SKILL.md"), "w", encoding="utf-8") as fh:
            fh.write("# demo\n")
        for rel, body in (extra or {}).items():
            p = os.path.join(sk, rel)
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "w", encoding="utf-8") as fh:
                fh.write(body)
        with open(os.path.join(sk, "sources.json"), "w", encoding="utf-8") as fh:
            json.dump({"schemaVersion": 1, "skill": "demo", "sources": sources}, fh)
        return root

    def row(**kw):
        base = {"id": "s1", "label": "L", "publisher": "P", "instrument": "I",
                "version": "V", "checkedOn": "2026-01-01", "checkedBy": "claude-code",
                "gated": False, "usedFor": ["SKILL.md"]}
        base.update(kw)
        return base

    with tempfile.TemporaryDirectory() as tmp:
        ok(check_sources(tree(tmp, "clean", [row()])) is True,
           "a complete row passes")
        # RW-1.1 -- a skill that cites nothing is valid; a skill with no file is not.
        ok(check_sources(tree(tmp, "empty", [])) is True,
           "an empty sources array is valid (board-pack cites nothing)")
        missing = tree(tmp, "missing", [])
        os.remove(os.path.join(missing, "skills", "demo", "sources.json"))
        ok(check_sources(missing) is False,
           "a missing sources.json fails -- absence is not an empty array")

        for field in REQUIRED:
            bad = row()
            del bad[field]
            ok(check_sources(tree(tmp, "no_" + field, [bad])) is False,
               "a row missing `%s` fails" % field)

        ok(check_sources(tree(tmp, "dupe", [row(), row()])) is False,
           "a duplicate id within a skill fails")
        ok(check_sources(tree(tmp, "future",
                              [row(checkedOn="2099-01-01")])) is False,
           "a future checkedOn fails")
        ok(check_sources(tree(tmp, "baddate", [row(checkedOn="08-08-2026")])) is False,
           "a malformed checkedOn fails")
        ok(check_sources(tree(tmp, "gatenoiv", [row(gated=True)])) is False,
           "gated with no reviewIntervalDays fails -- it would look supervised and not be")
        ok(check_sources(tree(tmp, "gateok",
                              [row(gated=True, reviewIntervalDays=365)])) is True,
           "gated with a positive interval passes")
        ok(check_sources(tree(tmp, "ghost", [row(usedFor=["renderers/gone.py"])])) is False,
           "C4: a usedFor path not in the tree fails")

        # RW-1.8 -- unverified rows are allowed and counted, must say why, never gated.
        ok(check_sources(tree(tmp, "unver", [row(checkedBy="unverified",
                                                 whyUnverified="paywalled")])) is True,
           "an unverified row with a reason is valid -- saying so beats a check never made")
        ok(check_sources(tree(tmp, "unvernowhy", [row(checkedBy="unverified")])) is False,
           "an unverified row with no `whyUnverified` fails -- otherwise it reads as a shrug")
        ok(check_sources(tree(tmp, "unvergate",
                              [row(checkedBy="unverified", whyUnverified="paywalled",
                                   gated=True, reviewIntervalDays=365)])) is False,
           "an unverified row that is gated fails -- the gate would time a check never made")

        # C3, both directions -- the check this standard is named for.
        cite = "DORA RTS (EU) 2024/1774 Art. 3(d)"
        ok(check_sources(tree(tmp, "c3ok", [row(usedFor=["renderers/r.py"],
                                                renderedAs=cite)],
                              {"renderers/r.py": "x = '%s'\n" % cite})) is True,
           "C3: a renderedAs found byte-for-byte passes")
        ok(check_sources(tree(tmp, "c3drift", [row(usedFor=["renderers/r.py"],
                                                   renderedAs=cite)],
                              {"renderers/r.py": "x = 'DORA RTS Art. 3(d)'\n"})) is False,
           "C3: a renderer that dropped the instrument fails")
        ok(check_sources(tree(tmp, "c3char", [row(usedFor=["renderers/r.py"],
                                                  renderedAs=cite)],
                              {"renderers/r.py": "x = '%s'\n" % cite.replace("3(d)", "3(e)")}
                              )) is False,
           "C3: one altered character fails -- byte equality, not resemblance")
        ok(check_sources(tree(tmp, "c3none", [row()])) is True,
           "C3: no renderedAs is valid, and means this source does not render (RW-1.4)")
        ok(check_sources(tree(tmp, "c3empty", [row(renderedAs="  ")])) is False,
           "C3: an empty renderedAs fails -- omit it instead of shipping a blank claim")

        # The release gate.
        old = (_today() - datetime.timedelta(days=400)).isoformat()
        stale_root = tree(tmp, "stale", [row(gated=True, reviewIntervalDays=365,
                                             checkedOn=old)])
        ok(release_gate(stale_root) is False,
           "release-gate fails on a gated source past its interval")
        ok(release_gate(tree(tmp, "fresh", [row(gated=True, reviewIntervalDays=365,
                                                checkedOn=_today().isoformat())])) is True,
           "release-gate passes on a freshly checked source")

        def with_override(name, entry):
            r = tree(tmp, name, [row(gated=True, reviewIntervalDays=365, checkedOn=old)])
            os.makedirs(os.path.join(r, "tools"))
            with open(os.path.join(r, "tools", "release-overrides.json"), "w",
                      encoding="utf-8") as fh:
                json.dump({"overrides": [entry]}, fh)
            return r

        ok(release_gate(with_override("ovok", {
            "source": "demo/s1", "reason": "EUR-Lex unreachable; re-check booked",
            "owner": "R. Calder", "date": "2026-08-08"})) is True,
           "a reasoned override lets the release through")
        ok(release_gate(with_override("ovempty", {
            "source": "demo/s1", "reason": "   ",
            "owner": "R. Calder", "date": "2026-08-08"})) is False,
           "an override with an empty reason still fails")
        ok(release_gate(with_override("ovnoowner", {
            "source": "demo/s1", "reason": "busy", "date": "2026-08-08"})) is False,
           "an override with no owner still fails -- somebody is answerable")

        # Anti-vacuity, the same rule CAC-GP-1 and CAC-LE-1 apply.
        bare = os.path.join(tmp, "bare")
        os.makedirs(bare)
        ok(check_sources(bare) is False,
           "a tree with no skills fails instead of passing vacuously")
        ok(check_do_not_cite(bare) is False,
           "C5 with no do-not-cite.json fails rather than checking nothing")
        shutil.rmtree(bare, ignore_errors=True)

        # -- C5, both directions --
        #
        # The rule is not "never write the string". Naming a withdrawn publication in order to
        # say it is withdrawn is what this repo should do. Both cases are registered, because a
        # ban that also forbids the warning would get switched off within a week.
        def dnc(name, body, entries=None, markers=None):
            root = os.path.join(tmp, name)
            os.makedirs(os.path.join(root, "tools"))
            os.makedirs(os.path.join(root, "skills", "demo"))
            with open(os.path.join(root, "skills", "demo", "SKILL.md"), "w",
                      encoding="utf-8") as fh:
                fh.write(body)
            with open(os.path.join(root, "tools", "do-not-cite.json"), "w",
                      encoding="utf-8") as fh:
                json.dump({"schemaVersion": 1,
                           "markers": markers if markers is not None else ["withdrawn"],
                           "entries": entries if entries is not None else [
                               {"id": "e", "label": "L",
                                "pattern": r"SP\s*800-61(?!\s*(?:r|Rev\.?\s*)3)",
                                "status": "withdrawn",
                                "supersededBy": "SP 800-61 Rev. 3 — Final, 3 April 2025",
                                "why": "w"}]}, fh)
            return root

        ok(check_do_not_cite(dnc("d1", "Follow SP 800-61 Rev. 2 for incident handling.\n"))
           is False, "C5: a withdrawn publication cited as guidance fails")
        ok(check_do_not_cite(dnc("d2", "SP 800-61 Rev. 2 is withdrawn; use Rev. 3.\n"))
           is True, "C5: the same string WITH a withdrawal marker passes -- warning, not citing")
        ok(check_do_not_cite(dnc("d3", "We follow SP 800-61 Rev. 3.\n")) is True,
           "C5: the current revision is not matched at all")
        ok(check_do_not_cite(dnc("d4", "See SP 800-61 for the lifecycle.\n")) is False,
           "C5: the bare original, with no revision, fails too")
        # The window matters in both directions: a marker three paragraphs away is not a
        # caveat on this sentence, and one on the next line is.
        far = "SP 800-61 Rev. 2 is the standard.\n" + ("filler. " * 90) + "\nwithdrawn\n"
        ok(check_do_not_cite(dnc("d5", far)) is False,
           "C5: a marker far away does not excuse a bare citation")
        ok(check_do_not_cite(dnc("d6", "SP 800-61 Rev. 2.\nThat edition is withdrawn.\n"))
           is True, "C5: a marker on the next line does excuse it")
        ok(check_do_not_cite(dnc("d7", "x\n", entries=[])) is False,
           "C5: an empty entry list fails rather than passing vacuously")

    print("\ncheck-sources self-test: %d checks, %d failed"
          % (len(checks), sum(1 for c in checks if not c)))
    return all(checks)


def main(argv):
    if "--self-test" in argv:
        return 0 if _self_test() else 1
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for arg in argv:
        if arg not in ("--release-gate",):
            print("ERROR: unknown argument %r.\n       %s" % (arg, USAGE))
            return 1
    passed = check_sources(root)
    passed = check_do_not_cite(root) and passed
    if "--release-gate" in argv:
        passed = release_gate(root) and passed
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
