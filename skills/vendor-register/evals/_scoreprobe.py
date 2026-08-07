"""Behavioural half of the no-vendor-score guard: nothing EMITTED is named like a score.

Catches the key somebody adds to `analyze` output next year, which the static scan cannot
see because it is a rename rather than a calculation.

`tiers` is deliberately allowed. Evidence tiers are a real concept in the design — an audited
artifact versus a marketing page — and they rank evidence rigour, not vendors. The pattern
excludes a trailing `s` for exactly that reason.

Usage: _scoreprobe.py <analysis.json> [--keys | --counts]
"""

from __future__ import annotations

import json
import re
import sys

BANNED = re.compile(r"score|rating|grade|tier(?!s)", re.I)


def score_like_keys(node, path=""):
    hits = []
    if isinstance(node, dict):
        for key, value in node.items():
            if BANNED.search(str(key)):
                hits.append("%s.%s" % (path, key))
            hits.extend(score_like_keys(value, "%s.%s" % (path, key)))
    elif isinstance(node, list):
        for i, value in enumerate(node):
            hits.extend(score_like_keys(value, "%s[%d]" % (path, i)))
    return hits


def main(argv):
    analysis = json.load(open(argv[1], encoding="utf-8"))
    mode = argv[2] if len(argv) > 2 else "--keys"
    if mode == "--keys":
        hits = score_like_keys(analysis)
        if hits:
            print("score-like keys: %s" % ", ".join(hits), file=sys.stderr)
            return 1
        return 0
    # --counts: criticality is reported as a count per NAMED level and never as one number.
    # A register with three critical arrangements has three critical arrangements; a single
    # figure standing for that is an opinion the tool is not entitled to.
    by = analysis["counts"]["byCriticality"]
    if not isinstance(by, dict) or not all(isinstance(v, int) for v in by.values()):
        print("byCriticality is not a mapping of level -> count", file=sys.stderr)
        return 1
    if sum(by.values()) != analysis["counts"]["live"]:
        print("the per-level counts do not add up to the live arrangements, so one of "
              "them is not a count", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
