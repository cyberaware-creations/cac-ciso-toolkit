#!/usr/bin/env python3
"""Copy a manifest elsewhere with an added `context`, keeping every path valid.

Paths inside a manifest resolve relative to the manifest's own directory — deliberately,
so a manifest committed beside its sources works from any cwd. A copy written into a temp
directory therefore has to carry ABSOLUTE paths, or every store and sidecar in it silently
goes missing and the suite reports a context defect that is really a fixture defect.

Its own file because a heredoc inside `$( ... )` is a parse error, which this repo has
paid for more than once.

Usage: _ctxmanifest.py <src-manifest> <dest-manifest> <context>
"""
from __future__ import annotations

import json
import os
import sys


def main(argv) -> int:
    src, dest, context = argv[0], argv[1], argv[2]
    base = os.path.dirname(os.path.abspath(src))
    with open(src, encoding="utf-8") as fh:
        doc = json.load(fh)

    def absolute(value):
        return value if os.path.isabs(value) else os.path.normpath(os.path.join(base, value))

    for entry in doc.get("sections") or []:
        for key in ("store", "translations"):
            if entry.get(key):
                entry[key] = absolute(entry[key])
    if doc.get("throughLine"):
        doc["throughLine"] = absolute(doc["throughLine"])
    # The context is passed through as given: a caller naming a file that does not exist
    # is testing exactly that, and absolutising it would still not make it exist.
    doc["context"] = context
    with open(dest, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
