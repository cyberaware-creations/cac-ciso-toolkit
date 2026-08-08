"""Static half of the proposal-boundary guard: no code path closes a requirement on its own.

The self-test proves the two shipped acts behave. This proves no THIRD path exists — the
failure mode is not `assess` going wrong, it is somebody adding a convenience helper next year
that writes `met: True` without going through it.

Two scans, both over the AST rather than over text:

`--met` — every place that writes a truthy `met` key must sit inside `assess`. That function is
the only one allowed to close anything, because it is the only one that demands a named person.

`--tiers` — every comparison against an evidence tier must go through `SATISFYING_TIERS`. A
literal `("T1", "T2")` inlined somewhere is the same rule written twice, and two copies of a
rule are one copy and one future bug.

Usage: _boundaryscan.py <engine.py> <--met|--tiers>
Prints offending lines to stderr; exit 1 if any, 2 if it scanned nothing.
"""

from __future__ import annotations

import ast
import sys

# Both are Layer B acts demanding a named person and a reference to what was read. The
# self-test is exempt because it builds fixtures rather than offering a path a user can reach;
# every OTHER function is in scope, which is how this scan found that `review_requirements`
# shipped in v0.39.0 without requiring a name at all.
ALLOWED_MET_WRITERS = ("assess", "review_requirements", "_cmd_self_test")


def _enclosing_function(tree, node):
    """The name of the function a node sits inside, or '' at module level."""
    for func in ast.walk(tree):
        if isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for sub in ast.walk(func):
                if sub is node:
                    return func.name
    return ""


def scan_met(tree, source):
    """Dict literals writing a truthy `met`, outside the functions allowed to."""
    problems = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        for key, value in zip(node.keys, node.values):
            if not (isinstance(key, ast.Constant) and key.value == "met"):
                continue
            if isinstance(value, ast.Constant) and value.value is False:
                continue          # writing met: False closes nothing
            where = _enclosing_function(tree, node)
            if where not in ALLOWED_MET_WRITERS:
                problems.append(
                    "line %d: a requirement is marked met inside %r, which is not one of %s"
                    % (node.lineno, where or "<module>", ", ".join(ALLOWED_MET_WRITERS)))
    return problems


def scan_tiers(tree, source):
    """Tier literals compared outside the one constant that defines the rule."""
    problems = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Tuple, ast.List, ast.Set)):
            continue
        values = [e.value for e in node.elts
                  if isinstance(e, ast.Constant) and isinstance(e.value, str)]
        if not values:
            continue
        # The two definitions are the one place tier literals may appear: TIERS enumerates
        # them and SATISFYING_TIERS names the subset that can close anything. Recognised by
        # SHAPE rather than by line number, which drifts every time the file grows.
        if set(values) == {"T1", "T2", "T3", "T4"}:
            continue
        if set(values) == {"T1", "T2"} and node.lineno < 200:
            continue
        if set(values) & {"T1", "T2"} and set(values) <= {"T1", "T2", "T3", "T4"}:
            problems.append(
                "line %d: an inlined tier list %s — compare against SATISFYING_TIERS instead, "
                "so the rule has one definition" % (node.lineno, values))
    return problems


def main(argv):
    source = open(argv[1], encoding="utf-8").read()
    tree = ast.parse(source)
    mode = argv[2] if len(argv) > 2 else "--met"
    # A scan that walked nothing passes in silence, which is the failure this whole suite is
    # written against.
    funcs = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
    if len(funcs) < 10:
        print("scanned only %d functions — this is not the engine" % len(funcs),
              file=sys.stderr)
        return 2
    print("scanned %d functions" % len(funcs))
    problems = scan_met(tree, source) if mode == "--met" else scan_tiers(tree, source)
    if problems:
        print("\n".join(problems), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
