#!/usr/bin/env python3
"""Read KNOWN_FLAGS and QUESTION_SETS out of a module AS DATA, and check two properties.

Parsed with `ast` rather than imported. A poisoned copy is one of the inputs, and importing
it would run it; parsing also means this works on a file that would not import at all, which
is the state a half-finished edit leaves behind.

Usage:  _flagcheck.py <module.py> conflation|mapping|count|count-gated

`conflation`   no flag definition joins two facts.
`mapping`      a battery whose id names a regime is gated on a flag whose own definition
               names that regime.
`count`        how many flag definitions were read (GP-1.7: a scan asserts what it read).
`count-gated`  how many regime-bearing batteries the mapping half actually checked.

Prints `clean <n>` or one line per problem.
"""
import ast
import sys

# The join that produced BL-175. An em dash inside a definition is how somebody explains what
# a flag is "really for", and "really for" is a second fact. Semicolons and " and " were
# considered and left out deliberately: `regulatedDataHeld` legitimately enumerates classes of
# one fact, and a check that fired on it would be turned off within a week.
CONFLATING = ("—", " -- ")

# battery id -> tokens, ANY of which must appear in the gate flag's own definition.
#
# Data, not logic, and the table is short because it only needs the batteries that carry a
# statutory consequence. A battery whose gate names its regime cannot be repointed at an
# unrelated flag without this going red — which is the single edit that would have caught
# BL-175 on the day it was written.
REGIME_TOKENS = {
    "sec-item-105": ("8-k", "exchange act", "item 1.05"),
    "dora-windows": ("dora",),
    "dora-ict-provider": ("dora",),
    "dora-register": ("dora",),
    "nydfs-notification": ("nydfs", "part 500"),
    "ai-overlay": ("ai", "machine-learning", "machine learning"),
}


def _tables(path):
    tree = ast.parse(open(path, encoding="utf-8").read())
    flags, sets = {}, {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        names = [t.id for t in node.targets if isinstance(t, ast.Name)]
        if "KNOWN_FLAGS" in names and isinstance(node.value, ast.Dict):
            for k, v in zip(node.value.keys, node.value.values):
                if isinstance(k, ast.Constant) and isinstance(v, ast.Constant):
                    flags[k.value] = v.value
        if "QUESTION_SETS" in names and isinstance(node.value, ast.Dict):
            for _skill, inner in zip(node.value.keys, node.value.values):
                if not isinstance(inner, ast.Dict):
                    continue
                for bk, bv in zip(inner.keys, inner.values):
                    if isinstance(bk, ast.Constant) and isinstance(bv, ast.Constant):
                        sets[bk.value] = bv.value
    return flags, sets


def main(argv):
    if len(argv) != 3:
        print(__doc__.strip())
        return 2
    path, mode = argv[1], argv[2]
    flags, sets = _tables(path)

    gated = sorted(b for b in sets if b in REGIME_TOKENS)
    if mode == "count":
        print(len(flags))
        return 0
    if mode == "count-gated":
        print(len(gated))
        return 0

    problems = []
    if mode == "conflation":
        if not flags:
            problems.append("read NO flag definitions — the table moved and this check is "
                            "reporting clean on an empty scan")
        for name, definition in sorted(flags.items()):
            for join in CONFLATING:
                if join in definition:
                    problems.append(
                        "%s: definition joins two facts with %r — %r. One flag, one fact: a "
                        "second clause is a mapping in disguise, and it is what gated a Form "
                        "8-K deadline off a listing fact for twelve releases (BL-175)."
                        % (name, join, definition))
        counted = len(flags)
    elif mode == "mapping":
        if not gated:
            problems.append("checked NO gated batteries — either the question sets moved or "
                            "REGIME_TOKENS no longer names any battery that exists")
        for battery in gated:
            gate = sets[battery]
            definition = flags.get(gate)
            if definition is None:
                problems.append(
                    "%s is gated on %r, which is not in KNOWN_FLAGS — the enumeration accepts "
                    "an unknown flag from a USER with a warning, but a gate this file ships "
                    "must be documented." % (battery, gate))
                continue
            low = definition.lower()
            if not any(tok in low for tok in REGIME_TOKENS[battery]):
                problems.append(
                    "%s is gated on %r, whose definition %r names none of %s. A battery must "
                    "be gated on the flag that states its own regime; gating it on a "
                    "neighbouring fact is BL-175 exactly."
                    % (battery, gate, definition, list(REGIME_TOKENS[battery])))
        counted = len(gated)
    else:
        print("unknown mode %r" % mode)
        return 2

    if problems:
        print("\n".join(problems))
        return 1
    print("clean %d" % counted)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
