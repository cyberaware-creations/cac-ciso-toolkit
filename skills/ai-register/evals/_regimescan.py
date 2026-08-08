"""No regulatory date lives in prose, and no regime obligation is unattributable.

Two halves, and they guard the same failure from opposite ends.

  --static DIR   No shipped .py puts a year inside a sentence about a regulation. Dates rot,
                 prose does not get re-read, and a stale date inside a refusal message is a
                 wrong statement of law delivered at the exact moment somebody is trying to
                 do the right thing.

  --data FILE    Every obligation in the dataset carries a source and an owning function, and
                 the dataset carries an `asOf`. A dataset with no date is a claim about an
                 unknown version of every text in it.

The static half is DELIBERATELY NARROW, and the narrowing is the interesting part. Every
shipped script here is full of four-digit years — self-test fixtures, example dates, period
ends — and banning those would mean banning test data. What is banned is a year in a string
that is ALSO talking about a regulation: an effective date, a compliance deadline, an
"applies from". That is the claim that rots.

Usage: _regimescan.py --static <skill-dir>
       _regimescan.py --data <regimes.json>
Prints `scanned N` / `checked N` so a run that read nothing cannot pass in silence.
"""

from __future__ import annotations

import ast
import json
import pathlib
import re
import sys

YEAR = re.compile(r"\b(19|20)\d{2}\b")

# Vocabulary that makes a sentence a statement about law rather than about a store. Named
# regimes are included because "the AI Act" plus a year is the exact shape being banned, and
# generic words like `article` and `applies from` catch the ones nobody has heard of yet.
REGULATORY = re.compile(
    r"regulation|directive|statute|article\s+\d|section\s+\d|§|"
    r"\bAI Act\b|\bDORA\b|\bNYDFS\b|\bGDPR\b|\bSEC\b|\bSB[- ]?\d|\bHB[- ]?\d|"
    r"comes into force|enters into force|applies from|effective from|"
    r"compliance deadline|transition period|in scope from",
    re.I)


def _strings(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            yield node.lineno, node.value


def static(root):
    root = pathlib.Path(root)
    files = [p for p in sorted(root.glob("scripts/*.py")) + sorted(root.glob("renderers/*.py"))
             if p.name not in ("cac_graphics.py", "_common.py")]
    if not files:
        print("scanned 0", flush=True)
        print("no shipped .py was scanned — the glob stopped matching, so this guard "
              "proved nothing", file=sys.stderr)
        return 2
    problems = []
    for path in files:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for lineno, text in _strings(tree):
            if REGULATORY.search(text) and YEAR.search(text):
                problems.append("%s line %d: a regulatory sentence carrying a year — %r"
                                % (path.name, lineno, text.strip()[:120]))
    print("scanned %d" % len(files), flush=True)
    if problems:
        print("\n".join(problems), file=sys.stderr)
        print("\nRegulatory dates belong in references/regimes.json, behind an `asOf`, "
              "where a reader can see how old they are.", file=sys.stderr)
        return 1
    return 0


def data(path):
    payload = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    problems = []
    if not str(payload.get("asOf") or "").strip():
        problems.append("the dataset has no `asOf`")
    checked = 0
    for regime in (payload.get("regimes") or []):
        rid = regime.get("id") or "?"
        if regime.get("aiRole") not in ("deployer", "provider"):
            problems.append("%s: aiRole is %r, not deployer or provider"
                            % (rid, regime.get("aiRole")))
        if not str(regime.get("flag") or "").strip():
            problems.append("%s: no flag selects it" % rid)
        for ob in (regime.get("obligations") or []):
            checked += 1
            oid = ob.get("id") or "?"
            if not str(ob.get("source") or "").strip():
                problems.append("%s/%s: no source" % (rid, oid))
            if not str(ob.get("owningFunction") or "").strip():
                problems.append("%s/%s: no owningFunction" % (rid, oid))
    print("checked %d obligation(s) across %d regime(s)"
          % (checked, len(payload.get("regimes") or [])), flush=True)
    if problems:
        print("\n".join(problems), file=sys.stderr)
        return 1
    return 0


def main(argv):
    if len(argv) != 3 or argv[1] not in ("--static", "--data"):
        print(__doc__, file=sys.stderr)
        return 2
    return static(argv[2]) if argv[1] == "--static" else data(argv[2])


if __name__ == "__main__":
    sys.exit(main(sys.argv))
