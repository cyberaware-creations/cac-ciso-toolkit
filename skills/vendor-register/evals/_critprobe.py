"""Read criticality and escalation marks out of rendered HTML, and tell them apart.

The two are coloured by opposite rules (D-10) and one of them is spelled the same as an
escalation trigger — `untraced` is both a criticality state and a trigger name. A checker with
only the word to go on cannot tell a classification from a severity, which is why the renderers
mark them `chip crit` and `chip trig`.

Usage: _critprobe.py <html> <crit|trig|ragset>
Prints one `word<TAB>background` per line, lowercased. `ragset` prints the RAG grounds the
graphics library actually uses, so the caller compares against the library rather than against
a hex literal copied into a test — a checker sharing constants with the thing it checks proves
only that somebody typed the same string twice.
"""

from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "renderers"))
import cac_graphics as G  # noqa: E402

CHIP = r'<span class="chip %s" style="background:(#[0-9A-Fa-f]{6});[^"]*">([^<]+)</span>'


def main(argv):
    mode = argv[2] if len(argv) > 2 else "crit"
    if mode == "ragset":
        for band in ("critical", "high", "good", "medium"):
            print(G.chip(band)[0].lower())
        return 0
    html = open(argv[1], encoding="utf-8").read()
    for match in re.finditer(CHIP % mode, html):
        print("%s\t%s" % (match.group(2).strip().lower(), match.group(1).lower()))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
