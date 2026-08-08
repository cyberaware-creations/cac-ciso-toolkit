"""Static half of the no-vendor-score guard: nothing computes a score internally.

The behavioural half only sees what the engine emits. A score computed inside and rendered
under an innocent name — "priority", "attention", "index" — would pass it completely. So the
arithmetic itself is read.

Deliberately narrow. `len(x) + 1` is arithmetic and is fine. Multiplying or averaging a
criticality rank against a finding count or a severity is the specific shape a vendor score
takes, and it is the shape this catches.

Usage: _scorescan.py <skill-dir>
Prints `scanned N` to stdout so the caller can prove the glob matched something; exits 1 with
the offending lines on stderr, 2 if it scanned nothing at all.
"""

from __future__ import annotations

import ast
import pathlib
import sys

RISKY = ("criticality", "rank", "severity", "finding", "score", "weight")
AVERAGING = ("mean", "fmean", "median", "average")


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
            risky = sorted(n for n in self._names(node)
                           if any(r in n for r in RISKY))
            if risky:
                self.hits.append("line %d: %s over %s"
                                 % (node.lineno, type(node.op).__name__,
                                    ", ".join(risky)))
        self.generic_visit(node)

    def visit_Call(self, node):
        name = getattr(node.func, "attr", None) or getattr(node.func, "id", "")
        if name in AVERAGING:
            self.hits.append("line %d: %s()" % (node.lineno, name))
        self.generic_visit(node)


def main(argv):
    root = pathlib.Path(argv[1])
    files = [p for p in sorted(root.glob("scripts/*.py")) + sorted(root.glob("renderers/*.py"))
             # Vendored, byte-identical to tools/, and guarded there instead.
             if p.name not in ("cac_graphics.py", "_common.py")]
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


if __name__ == "__main__":
    sys.exit(main(sys.argv))
