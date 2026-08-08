"""The no-closed-state guard, both halves.

An attack class has no closed state. Not `mitigated`, not `resolved`, not `closed`, not
`accepted`. The design records NIST's position that adversarial ML mitigations are empirical
rather than guaranteed, that published defences have repeatedly been broken by adaptive
attacks, and that the problem remains open — so a register letting somebody tick a class as
handled would assert exactly what the source declines to.

This is the rule most likely to be relaxed later, because its absence looks like a gap. It is
the obvious next feature request, it is a one-line change, and nothing about the codebase would
complain. So it is checked two ways:

  --store FILE   BEHAVIOURAL. Nothing inside a real store's `exposure` — no key, at any depth,
                 no string value — describes a class as handled. Catches the field somebody
                 adds and then writes through.

  --static DIR   STATIC. No shipped .py assigns such a key, and no function named for closing
                 one exists without raising. Catches the field computed and rendered but never
                 persisted, which the behavioural half cannot see.

Usage: _closedstate.py --store <store.air>
       _closedstate.py --static <skill-dir>
Prints `scanned N` on the static run so a glob that stopped matching cannot pass in silence.
Exit 1 with the offending lines on stderr; 2 if it found nothing to inspect at all.
"""

from __future__ import annotations

import ast
import json
import pathlib
import re
import sys

# Deliberately the same words `ai_register.CLOSED_STATE_RE` names, restated here rather than
# imported: a guard that reads its rule out of the file it is guarding proves nothing, because
# relaxing the rule relaxes the check with it.
CLOSED = re.compile(r"mitigat|resolv|closed|accepted|remediat|handled", re.I)

# A function whose NAME says it closes a class. `accept_exposure` is expected and must raise;
# anything else here is the feature this guard exists to prevent.
CLOSING_NAME = re.compile(r"mitigat|resolv|\bclose|accept|remediat|handle", re.I)


def walk_store(payload):
    """Every (path, key-or-value) pair inside every deployment's exposure block."""
    for dep in (payload.get("deployments") or []):
        exposure = dep.get("exposure") or {}
        for item in _walk("%s.exposure" % dep.get("id", "?"), exposure):
            yield item


def _walk(path, node):
    if isinstance(node, dict):
        for key, value in node.items():
            yield ("%s.%s" % (path, key), "key", str(key))
            for item in _walk("%s.%s" % (path, key), value):
                yield item
    elif isinstance(node, list):
        for i, value in enumerate(node):
            for item in _walk("%s[%d]" % (path, i), value):
                yield item
    elif isinstance(node, str):
        yield (path, "value", node)


def behavioural(path):
    payload = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    deployments = payload.get("deployments") or []
    classes = sum(len(d.get("exposure") or {}) for d in deployments)
    controls = sum(len(e.get("controls") or [])
                   for d in deployments for e in (d.get("exposure") or {}).values())
    if not classes or not controls:
        print("the store has %d exposure class(es) and %d recorded control(s) — there is "
              "nothing here for this guard to be wrong about"
              % (classes, controls), file=sys.stderr)
        return 2
    problems = []
    for where, kind, text in walk_store(payload):
        if CLOSED.search(text):
            problems.append("%s: %s %r" % (where, kind, text))
    print("inspected %d class(es) carrying %d control(s)" % (classes, controls), flush=True)
    if problems:
        print("\n".join(problems), file=sys.stderr)
        return 1
    return 0


def _slice_of(node):
    """The subscript key as an AST node, across the versions this suite runs on.

    Python 3.8 wrapped it in `ast.Index`; 3.9 unwrapped it. Reading `node.slice.value`
    without this returns the *string* on 3.9+ and the inner node on 3.8, and the isinstance
    check then quietly fails on the interpreter everybody actually uses — which is how the
    first draft of this scanner passed a planted `exposure[cls]["mitigated"] = True`.
    """
    sl = node.slice
    index_type = getattr(ast, "Index", None)
    if index_type is not None and isinstance(sl, index_type):
        sl = sl.value
    return sl


class Scan(ast.NodeVisitor):
    def __init__(self):
        self.hits = []

    def visit_Dict(self, node):
        for key in node.keys:
            if isinstance(key, ast.Constant) and isinstance(key.value, str) \
                    and CLOSED.search(key.value):
                self.hits.append("line %d: dict key %r" % (key.lineno, key.value))
        self.generic_visit(node)

    def visit_Assign(self, node):
        for target in node.targets:
            self._check_target(target)
        self.generic_visit(node)

    def visit_AnnAssign(self, node):
        self._check_target(node.target)
        self.generic_visit(node)

    def _check_target(self, target):
        if isinstance(target, ast.Subscript):
            key = _slice_of(target)
            if isinstance(key, ast.Constant) and isinstance(key.value, str) \
                    and CLOSED.search(key.value):
                self.hits.append("line %d: assigns [%r]" % (target.lineno, key.value))
        if isinstance(target, ast.Attribute) and CLOSED.search(target.attr):
            self.hits.append("line %d: assigns .%s" % (target.lineno, target.attr))

    def visit_Call(self, node):
        # `.setdefault("mitigated", ...)` and `.update({"resolved": ...})` write a field
        # without ever appearing as an assignment target.
        name = getattr(node.func, "attr", "")
        if name in ("setdefault", "get", "pop") and node.args:
            first = node.args[0]
            if isinstance(first, ast.Constant) and isinstance(first.value, str) \
                    and CLOSED.search(first.value):
                self.hits.append("line %d: .%s(%r)" % (node.lineno, name, first.value))
        self.generic_visit(node)

    def visit_FunctionDef(self, node):
        if CLOSING_NAME.search(node.name):
            raises = any(isinstance(sub, ast.Raise) for sub in ast.walk(node))
            if not raises:
                self.hits.append(
                    "line %d: def %s() is named for closing a class and does not refuse"
                    % (node.lineno, node.name))
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
    if len(argv) != 3 or argv[1] not in ("--store", "--static"):
        print(__doc__, file=sys.stderr)
        return 2
    return behavioural(argv[2]) if argv[1] == "--store" else static(argv[2])


if __name__ == "__main__":
    sys.exit(main(sys.argv))
