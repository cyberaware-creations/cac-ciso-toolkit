#!/usr/bin/env python3
"""Which producers state the population their headline counts are drawn from?

`assemble_pack._risk_headline` writes the rule down: *a total without its denominator is
the false precision this pack refuses everywhere else.* Posture, risk, exceptions and
incident all followed it. Metrics did not, so a pack printed "3 metrics past a threshold"
with nothing anywhere saying whether that was three of four or three of forty — and on a
register holding nothing it printed two reassuring zeros and no population at all, which
reads from the back of a boardroom as a healthy metrics programme rather than an empty one.

Checked per SECTION rather than by naming the labels this pack happens to use today, so a
producer wired in later cannot ship a bare count either.

A population figure is one whose label names the WHOLE set rather than a subset of it. The
vocabulary is small and deliberate — a producer inventing a sixth word for "all of them"
should have to add it here, where somebody will read the list and think about it, rather
than have a regex quietly accept it.

Lives in its own file because the shell it is called from cannot hold it: a heredoc inside
`$( ... )` is a parse error, and this repo has already paid for that lesson twice.

Usage:
  _popcheck.py <pack.json>              print the sections with no population figure
  _popcheck.py <pack.json> --sections   print how many sections supplied any figure
"""
from __future__ import annotations

import json
import re
import sys

# "tracked", "carried", "assessed", "in the period" — each names the whole set.
POPULATION = re.compile(r"\b(tracked|carried|assessed|in the period)\b", re.I)


def by_section(doc: dict) -> dict:
    out = {}
    for h in doc.get("headlines") or []:
        out.setdefault(h.get("section"), []).append(str(h.get("label") or ""))
    return out


def main(argv) -> int:
    if not argv:
        print("usage: _popcheck.py <pack.json> [--sections]", file=sys.stderr)
        return 2
    with open(argv[0], encoding="utf-8") as fh:
        sections = by_section(json.load(fh))
    if "--sections" in argv:
        print(len(sections))
        return 0
    missing = [s for s, labels in sorted(sections.items())
               if not any(POPULATION.search(l) for l in labels)]
    print(",".join(str(s) for s in missing))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
