#!/usr/bin/env python3
"""Inspect one consumer's output for the CAC-AP-1 properties. Reads JSON on stdin.

Every consumer puts its decided block in the same place — a top-level `context` — but they
carry different payloads around it, and `incident-materiality` also repeats the block per
incident. This finds the top-level one and answers a single question about it, so the shell
suite stays a list of assertions rather than a pile of inline Python.

Its own file because a heredoc inside `$( ... )` is a parse error, which this repo has
already paid for more than once.

Usage (one mode per call, JSON on stdin):
  --has-block          exit 0 if a decided context block is present
  --no-block           exit 0 if NO context key is present (the additive guarantee)
  --asked              print how many batteries were asked
  --skips-attributed   exit 0 if every skip names its flag, declarer and date (§2.4)
"""
from __future__ import annotations

import json
import sys


def block(doc):
    ctx = doc.get("context")
    return ctx if isinstance(ctx, dict) else None


def main(argv) -> int:
    if not argv:
        print(__doc__, file=sys.stderr)
        return 2
    try:
        doc = json.load(sys.stdin)
    except ValueError as exc:
        print(f"stdin is not JSON: {exc}", file=sys.stderr)
        return 2
    if not isinstance(doc, dict):
        print("stdin is not a JSON object", file=sys.stderr)
        return 2
    mode = argv[0]
    ctx = block(doc)

    if mode == "--has-block":
        return 0 if ctx is not None and "asked" in ctx else 1
    if mode == "--no-block":
        return 0 if "context" not in doc else 1
    if mode == "--asked":
        # A missing block prints 0 rather than raising: the caller compares two counts, and
        # a crash there would read as an inconclusive run instead of a failed assertion.
        print(len((ctx or {}).get("asked") or []))
        return 0
    if mode == "--skips-attributed":
        skips = (ctx or {}).get("skipped") or []
        # No skips is NOT a pass. This mode is called on a profile that declares every flag
        # false, so an empty list means the narrowing did not happen and the assertion would
        # otherwise pass over nothing at all.
        if not skips:
            print("no skips to check; the narrowing did not happen", file=sys.stderr)
            return 1
        for rec in skips:
            missing = [k for k in ("flag", "declaredBy", "declaredOn") if not rec.get(k)]
            if missing:
                print(f"{rec.get('battery')!r} is missing {', '.join(missing)}",
                      file=sys.stderr)
                return 1
        return 0
    print(f"unknown mode {mode!r}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
