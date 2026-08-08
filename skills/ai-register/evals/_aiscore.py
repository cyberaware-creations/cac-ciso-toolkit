"""The no-ai-score guard, both halves.

Every AI-governance product on the market emits a number: an AI risk score, a model risk
rating, a posture grade. This register emits none, for the same reason `vendor-register` emits
no vendor score — a generated number looks like an assessment, nobody can reproduce it, and it
disagrees with the register that actually owns scoring. Findings go one way to
`risk-register` and are scored once, there, under L×I with an appetite to judge them against.

The specific arithmetic this catches is the tempting one: exposure classes counted and
multiplied or averaged against a criticality rank. It is three lines, it produces a plausible
number, and it would be indistinguishable on a page from something somebody thought about.

  --json FILE    BEHAVIOURAL. No key anywhere in an emitted payload is named like a score.
                 Keys only — a deployment whose declared PURPOSE is "churn scoring" is a fact
                 about the business, and banning the word in values would be banning the truth.

  --static DIR   STATIC. No shipped .py multiplies, divides or averages anything touching a
                 criticality, a rank or an exposure count, and none emits a score-shaped key.
                 Catches the score computed internally and rendered under an innocent name,
                 which is a rename rather than a calculation and so is invisible to the first
                 half.

Usage: _aiscore.py --json <payload.json>
       _aiscore.py --static <skill-dir>
Prints `scanned N` / `inspected N` so a run that read nothing cannot pass in silence.
"""

from __future__ import annotations

import ast
import json
import pathlib
import re
import sys

SCORE_KEY = re.compile(r"score|rating|grade|posture", re.I)

# The operands that make arithmetic a score rather than a count. `len(x) + 1` is arithmetic
# and is fine; a criticality rank over an exposure count is the shape a posture score takes.
RISKY = ("criticality", "rank", "exposure", "class", "control", "count", "severity",
         "score", "weight", "autonomy")
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
    if len(seen) < 10:
        print("only %d key(s) in %s — an almost-empty payload has nothing to be wrong about"
              % (len(seen), path), file=sys.stderr)
        return 2
    problems = ["%s: key %r" % (where, key) for where, key in seen if SCORE_KEY.search(key)]
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
                    and SCORE_KEY.search(key.value):
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
