#!/usr/bin/env python3
"""The scanner behind no-coverage-claim.sh. Two modes, because one of them is escapable.

  --analysis FILE   behavioural: no STATUS anywhere in a produced analysis claims that a
                    requirement is met, and the state vocabulary is exactly the four
                    declared values
  --page FILE       behavioural: no CHIP on a rendered page carries a coverage word. Chips
                    are what a reader takes as the verdict, so they are scanned by
                    themselves rather than drowned in the surrounding prose
  --static DIR      static: no shipped .py names, assigns or returns a coverage state.
                    Catches the field computed and rendered but never persisted, which
                    neither behavioural mode can see

WHY THE PROSE IS NOT BANNED WHOLESALE. This skill has to SAY "it is not evidence that the
requirement is met" on every surface, so a scan that failed on the word `met` anywhere would
fail on the sentence that makes the product honest. The distinction that matters is between
prose ABOUT the limit and a STATUS that asserts the opposite: coverage claims land in keys,
in short slug-like values, and in chips. Those three are scanned strictly; running prose is
not scanned at all.

Exit 0 clean, 1 with findings on stderr, 2 if the input could not be inspected — a scan that
read nothing must not report a clean bill.
"""
from __future__ import annotations

import argparse
import ast
import json
import pathlib
import re
import sys

# A status that says the requirement is in hand. `met` is here as a WHOLE WORD only: it is a
# substring of "metrics", "meta" and "metadata", and a stem match would flag the word
# `metadata` in a key and teach everyone to ignore this guard.
CLAIM_WORDS = ("covered", "coverage", "satisfied", "satisfies", "satisfy", "compliant",
               "compliance", "addressed", "handled", "fulfilled", "fulfils", "fulfilled",
               "implemented", "in-place", "inplace", "adequate", "sufficient", "attested",
               "assured", "demonstrated", "met")
_WORD = re.compile(r"[a-z]+", re.I)

# The four states the engine is allowed to put on a requirement row, written out here rather
# than imported. That is the point: if the engine's tuple changes, this list does not follow
# it, and the mismatch is the failure. A guard that read the value it is checking from the
# thing it is checking asserts nothing.
EXPECTED_STATES = ["approved-policy", "draft-only", "not-declared", "superseded-only"]

# Keys whose VALUES are read as a verdict rather than as prose.
STATUS_KEYS = ("state", "status", "verdict", "result", "outcome", "band", "level",
               "conclusion", "assessment", "rating", "posture")


def words(text: str):
    return set(w.lower() for w in _WORD.findall(str(text)))


def claims_in(text: str):
    return sorted(w for w in words(text) if w in CLAIM_WORDS)


def scan_analysis(path: str):
    problems = []
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError) as exc:
        return None, ["%s could not be read as JSON (%s)" % (path, exc)]

    rows = data.get("requirements")
    if not isinstance(rows, list) or not rows:
        return None, ["%s carries no requirement rows; this scan would pass on an empty "
                      "file and prove nothing" % path]
    states = sorted(set(r.get("state") for r in rows))
    if states != sorted(set(EXPECTED_STATES)) and not set(states) <= set(EXPECTED_STATES):
        problems.append("requirement rows carry states this guard does not know about: %s "
                        "(declared: %s)" % (states, EXPECTED_STATES))
    declared = data.get("stateMeans")
    if not isinstance(declared, dict) or sorted(declared) != EXPECTED_STATES:
        problems.append("the analysis declares its state vocabulary as %s; this guard was "
                        "written against %s. A state was added, renamed or removed."
                        % (sorted(declared or {}), EXPECTED_STATES))

    def walk(node, path_bits):
        where = ".".join(path_bits) or "(root)"
        if isinstance(node, dict):
            for key, value in node.items():
                hit = claims_in(key)
                if hit:
                    problems.append("%s.%s — a key named for a coverage claim (%s)"
                                    % (where, key, ", ".join(hit)))
                if isinstance(value, str) and key.lower() in STATUS_KEYS:
                    hit = claims_in(value)
                    if hit:
                        problems.append("%s.%s = %r — a status that says the requirement is "
                                        "met (%s)" % (where, key, value, ", ".join(hit)))
                walk(value, path_bits + [str(key)])
        elif isinstance(node, list):
            for i, value in enumerate(node):
                walk(value, path_bits + ["[%d]" % i])
        elif isinstance(node, str):
            # A short, slug-shaped string is a token, not prose. Prose is left alone, which
            # is what lets this skill say "not evidence that the requirement is met".
            if len(node) <= 40 and " " not in node.strip():
                hit = claims_in(node)
                if hit:
                    problems.append("%s = %r — a token that reads as a coverage verdict (%s)"
                                    % (where, node, ", ".join(hit)))

    walk(data, [])
    return len(rows), problems


_CHIP = re.compile(r'<span class="chip"[^>]*>(.*?)</span>', re.S | re.I)


def scan_page(path: str):
    try:
        html = open(path, encoding="utf-8").read()
    except OSError as exc:
        return None, ["%s could not be read (%s)" % (path, exc)]
    chips = [re.sub(r"<[^>]+>", " ", c).strip() for c in _CHIP.findall(html)]
    if not chips:
        return None, ["%s carries no chips; the page a reader takes their verdict from was "
                      "not inspected" % path]
    problems = []
    for chip in sorted(set(chips)):
        hit = claims_in(chip)
        if hit:
            problems.append("a chip reads %r — that is a coverage verdict (%s)"
                            % (chip, ", ".join(hit)))
    return len(set(chips)), problems


def _key_names(node):
    """Every literal key or attribute name being ASSIGNED to, at any depth of the target."""
    out = []
    if isinstance(node, ast.Subscript):
        sl = node.slice
        if isinstance(sl, ast.Constant) and isinstance(sl.value, str):
            out.append(sl.value)
    elif isinstance(node, ast.Attribute):
        out.append(node.attr)
    elif isinstance(node, (ast.Tuple, ast.List)):
        for el in node.elts:
            out.extend(_key_names(el))
    return out


def scan_static(root: str):
    base = pathlib.Path(root)
    files = sorted(p for p in list(base.glob("scripts/*.py")) + list(base.glob("renderers/*.py"))
                   if p.name != "cac_graphics.py")
    if not files:
        return 0, ["%s holds no shipped .py to scan; a scan that read nothing must not "
                   "report a clean bill" % root]
    problems = []
    for path in files:
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError) as exc:
            problems.append("%s could not be parsed (%s)" % (path.name, exc))
            continue
        docstrings = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                                 ast.AsyncFunctionDef)):
                doc = ast.get_docstring(node, clean=False)
                if doc is not None:
                    docstrings.add(doc)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                hit = claims_in(node.name.replace("_", " "))
                if hit:
                    problems.append("%s:%d def %s — a function named for a coverage claim (%s)"
                                    % (path.name, node.lineno, node.name, ", ".join(hit)))
            elif isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                for t in targets:
                    for name in _key_names(t):
                        hit = claims_in(name.replace("_", " ").replace("-", " "))
                        if hit:
                            problems.append(
                                "%s:%d assigns %r — a coverage field written into a record "
                                "(%s)" % (path.name, node.lineno, name, ", ".join(hit)))
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                value = node.value
                if value in docstrings or len(value) > 40 or " " in value.strip():
                    continue
                hit = claims_in(value)
                if hit:
                    problems.append("%s:%d holds the token %r — a coverage verdict in "
                                    "shipped source (%s)"
                                    % (path.name, node.lineno, value, ", ".join(hit)))
    return len(files), problems


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--analysis")
    p.add_argument("--page")
    p.add_argument("--static")
    args = p.parse_args(argv)
    if not any((args.analysis, args.page, args.static)):
        print("nothing to scan", file=sys.stderr)
        return 2

    counted, problems = None, []
    if args.analysis:
        counted, problems = scan_analysis(args.analysis)
        noun = "requirement row(s)"
    elif args.page:
        counted, problems = scan_page(args.page)
        noun = "distinct chip(s)"
    else:
        counted, problems = scan_static(args.static)
        noun = "shipped file(s)"
    if counted is None:
        for msg in problems:
            print(msg, file=sys.stderr)
        return 2
    # The count goes to stdout WHATEVER the verdict. It used to be printed only on a clean
    # run, which meant a finding also blanked it — so the caller's "did this scan read
    # everything?" check went red as a side effect of the scan going red, and one mutation
    # appeared to defeat two independent checks. Coverage of the scan and correctness of the
    # thing scanned are different questions and must fail separately.
    print("scanned %d" % counted)
    for msg in problems:
        print(msg, file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
