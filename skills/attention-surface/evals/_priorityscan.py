"""No priority score — the fourth opinion this surface refuses to have.

Thirty triggers arrive here, each already carrying a severity its producer computed and can
defend. The tempting next step is one number that orders them all: a weighted blend of severity,
age and maybe criticality. It would be three lines, it would sort beautifully, and it would be
**this skill's own opinion about what matters** — a thirty-first voice in a room that already has
thirty, and the one voice with no register behind it.

The suite refuses a computed score in four other places for the same reason. This is the fifth.

  --json FILE    BEHAVIOURAL. No key in an emitted review is named like a priority. Keys only:
                 a producer's own `severity` value is a fact it owns and must travel through.

  --static DIR   STATIC. No shipped .py multiplies, divides or averages anything touching a
                 severity, an age or a count, and none emits a priority-shaped key. This is the
                 half that catches the score computed inside and rendered under an innocent
                 name, which is a rename rather than a calculation.

The ordering that IS allowed is a tuple of three declared facts — severity as the producer
stated it, age since `since`, and the subject reference — compared lexicographically. A tuple
comparison is not arithmetic: no weight is assigned, nothing is combined, and the reason any
item sits where it does can be read off in words.

Usage: _priorityscan.py --json <review.json>
       _priorityscan.py --static <skill-dir>
"""

from __future__ import annotations

import ast
import json
import pathlib
import re
import sys

# Deliberately does not ban `severity`: that is the producer's own declared value, and this
# surface must carry it through untouched. What is banned is a number of this skill's own.
PRIORITY_KEY = re.compile(r"score|priority|urgency|weight|ranking|\brank\b|index$|"
                          r"attention[A-Z_]|composite", re.I)

RISKY = ("severity", "age", "days", "count", "rank", "score", "weight", "priority",
         "criticality")
AVERAGING = ("mean", "fmean", "median", "average")


def _keys(node, path="$"):
    if isinstance(node, dict):
        for key, value in node.items():
            yield ("%s.%s" % (path, key), str(key))
            for item in _keys(value, "%s.%s" % (path, key)):
                yield item
    elif isinstance(node, list):
        for i, value in enumerate(node):
            for item in _keys(value, "%s[%d]" % (path, i)):
                yield item


def behavioural(path):
    payload = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    seen = list(_keys(payload))
    if len(seen) < 20:
        print("only %d key(s) in %s — an almost-empty review has nothing to be wrong about"
              % (len(seen), path), file=sys.stderr)
        return 2
    problems = ["%s: key %r" % (where, key) for where, key in seen if PRIORITY_KEY.search(key)]
    print("inspected %d key(s)" % len(seen), flush=True)
    if problems:
        print("\n".join(problems), file=sys.stderr)
        return 1
    return 0


class Scan(ast.NodeVisitor):
    def __init__(self):
        self.hits = []

    @staticmethod
    def _names(node):
        names = set()
        for sub in ast.walk(node):
            if isinstance(sub, ast.Name):
                names.add(sub.id.lower())
            elif isinstance(sub, ast.Attribute):
                names.add(sub.attr.lower())
            elif isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                names.add(sub.value.lower())
        return names

    def visit_BinOp(self, node):
        if isinstance(node.op, (ast.Mult, ast.Div, ast.FloorDiv, ast.Pow)):
            risky = sorted(n for n in self._names(node) if any(r in n for r in RISKY))
            if risky:
                self.hits.append("line %d: %s over %s"
                                 % (node.lineno, type(node.op).__name__, ", ".join(risky)))
        self.generic_visit(node)

    def visit_Call(self, node):
        name = getattr(node.func, "attr", None) or getattr(node.func, "id", "")
        if name in AVERAGING:
            self.hits.append("line %d: %s()" % (node.lineno, name))
        self.generic_visit(node)

    def visit_Dict(self, node):
        for key in node.keys:
            if isinstance(key, ast.Constant) and isinstance(key.value, str) \
                    and PRIORITY_KEY.search(key.value):
                self.hits.append("line %d: emits key %r" % (key.lineno, key.value))
        self.generic_visit(node)


def static(root):
    root = pathlib.Path(root)
    # `cac_graphics.py` is vendored byte-identical from tools/ and guarded there — the one
    # documented exclusion. `_common.py` sat beside it under that same comment, which only ever
    # justified the brand file, while `_common.py` is where board-visible prose lives. The count
    # printed below is asserted by the guard, so narrowing this list again fails (GP-1.7).
    files = [p for p in sorted(root.glob("scripts/*.py")) + sorted(root.glob("renderers/*.py"))
             if p.name != "cac_graphics.py"]
    if not files:
        print("scanned 0", flush=True)
        print("no shipped .py was scanned — the glob stopped matching, so this guard "
              "proved nothing", file=sys.stderr)
        return 2
    problems = []
    for path in files:
        scan = Scan()
        scan.visit(ast.parse(path.read_text(encoding="utf-8")))
        problems.extend("%s %s" % (path.name, hit) for hit in scan.hits)
    print("scanned %d" % len(files), flush=True)
    if problems:
        print("\n".join(problems), file=sys.stderr)
        return 1
    return 0


def main(argv):
    if len(argv) != 3 or argv[1] not in ("--json", "--static"):
        print(__doc__, file=sys.stderr)
        return 2
    return behavioural(argv[2]) if argv[1] == "--json" else static(argv[2])


if __name__ == "__main__":
    sys.exit(main(sys.argv))
