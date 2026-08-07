#!/usr/bin/env python3
"""Detect a derived materiality figure, in an output or in the source. Used by
no-derived-materiality.sh.

Two modes, because either alone is weak:

  --stdin   scan a JSON payload for a key that names a derived materiality figure.
  --source  scan a skill's shipped .py for arithmetic that divides by, or takes a
            percentage of, the revenue field.

The static mode walks the AST rather than grepping. A regex over source text cannot tell
`impact / revenue` from the word "revenue" inside a docstring explaining why that division
must not exist — and this skill's source is full of exactly such prose, so a regex here
would either miss the real thing or fire on every honest comment about it.
"""
from __future__ import annotations

import ast
import json
import pathlib
import sys

# Names an output must never carry. A threshold that arrives through the payload is the same
# defect as one computed in the source, and it is the one a reader would actually act on.
FORBIDDEN_KEYS = ("materialityThreshold", "pctOfRevenue", "materialPercent",
                  "revenueShare", "materialityPct", "percentOfRevenue")

# Identifiers that denote the revenue base. Dividing ANY of these, or dividing BY them, is
# the arithmetic being refused.
REVENUE_NAMES = {"revenue", "revenueBase", "revenue_base", "exact_revenue", "revenueExact"}


def scan_payload(text: str):
    problems = []
    try:
        doc = json.loads(text)
    except ValueError:
        return ["output was not JSON, so this check saw nothing"]

    def walk(node, path=""):
        if isinstance(node, dict):
            for key, val in node.items():
                for bad in FORBIDDEN_KEYS:
                    if bad.lower() == str(key).lower():
                        problems.append("%s/%s names a derived materiality figure"
                                        % (path, key))
                walk(val, "%s/%s" % (path, key))
        elif isinstance(node, list):
            for i, val in enumerate(node):
                walk(val, "%s[%d]" % (path, i))

    walk(doc)
    return problems


def _mentions_revenue(node, bound=()) -> bool:
    """True if this expression reads the revenue base, directly or through a local name.

    `bound` is the set of local names a preceding assignment pulled the revenue base into.
    Without it this check has a hole wide enough to walk the whole defect through: the
    idiomatic way to use the figure in this codebase is

        exact = revenue.get("exact")
        ... 1_000_000 / exact * 100

    and the division names nothing on the revenue list. That mutation was introduced
    deliberately and this function returned clean, which is how the gap was found rather
    than assumed. Tracking the binding is what closes it.
    """
    for sub in ast.walk(node):
        if isinstance(sub, ast.Name) and (sub.id in REVENUE_NAMES or sub.id in bound):
            return True
        if isinstance(sub, ast.Attribute) and sub.attr in REVENUE_NAMES:
            return True
        if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
            if sub.value in ("exact",) or sub.value in REVENUE_NAMES:
                # `store["context"]["revenue"]["exact"]` — the subscript chain.
                return True
    return False


def _revenue_bound_names(tree) -> set:
    """Local names that a plain assignment pulled the revenue base into.

    Deliberately module-wide rather than per-scope, and deliberately not a real dataflow
    analysis. This is a guardrail, and a guardrail that over-reaches is corrected by whoever
    trips it; one that under-reaches is discovered by whoever reads the percentage it let
    through. Fixed-point so that `a = revenue["exact"]` followed by `b = a` binds both.
    """
    bound, changed = set(), True
    while changed:
        changed = False
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Assign, ast.AnnAssign)):
                continue
            value = node.value
            if value is None or not _mentions_revenue(value, bound):
                continue
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                for name in ast.walk(target):
                    if isinstance(name, ast.Name) and name.id not in bound:
                        bound.add(name.id)
                        changed = True
    return bound


def scan_source(root: str):
    problems, scanned = [], 0
    base = pathlib.Path(root)
    for path in sorted(base.rglob("*.py")):
        if path.name == "cac_graphics.py":     # vendored library, not this skill's code
            continue
        scanned += 1
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError):
            continue
        bound = _revenue_bound_names(tree)
        for node in ast.walk(tree):
            if not isinstance(node, ast.BinOp):
                continue
            # Div and FloorDiv only. `ast.Mod` was here for "percentage" and had to go:
            # `%` on a string is formatting, not modulo, and this codebase formats with it
            # constantly — the first run of this check flagged three `print("... %s ..." %
            # (rec["exact"], ...))` lines as derived materiality. A real percentage of
            # revenue is `impact / revenue * 100`, which is a Div and is still caught.
            if not isinstance(node.op, (ast.Div, ast.FloorDiv)):
                continue
            # A division whose divisor is the revenue base, or whose dividend is.
            if _mentions_revenue(node.right, bound) or _mentions_revenue(node.left, bound):
                problems.append("%s:%d divides using the revenue base"
                                % (path.relative_to(base).as_posix(), node.lineno))
    if not scanned:
        problems.append("no .py files were scanned; the walk is broken, not the source clean")
    return problems


def main(argv) -> int:
    if "--stdin" in argv:
        problems = scan_payload(sys.stdin.read())
    elif "--source" in argv:
        problems = scan_source(argv[argv.index("--source") + 1])
    else:
        print("usage: _derivedcheck.py --stdin | --source <skill-dir>", file=sys.stderr)
        return 2
    print("clean" if not problems else "; ".join(problems[:4]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
