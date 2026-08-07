#!/usr/bin/env python3
"""Build a manifest whose sidecar declares which store state its prose was written against.

`boundTo` is optional and no shipped sidecar carries one, so rather than committing a bound
fixture — which would make the shipped example demonstrate the exception instead of the
ordinary case — this writes one on demand into the work directory and points an absolutised
manifest at it.

Two states, and the suite needs both. `--match` binds to the store's real `updatedAt`, which
must be silent. `--stale` binds to a moment before it, which must warn: that is the register
edited after its prose was written, and it is the whole reason the field exists.

Paths are absolutised for the same reason `_ctxmanifest.py` absolutises them — a manifest
resolves its paths relative to its own directory, so a copy in a temp dir loses every store
and the suite reports a binding defect that is really a fixture defect.

Its own file because a heredoc inside `$( ... )` is a parse error, which this repo has
already paid for more than once.

Usage:
  _bindfixture.py <src> <dest> <workdir> --section NAME (--match | --stale)
"""
from __future__ import annotations

import json
import os
import sys

STALE = "2026-05-01T09:00:00Z"


def main(argv) -> int:
    src, dest, workdir = argv[0], argv[1], argv[2]
    rest = argv[3:]
    section = rest[rest.index("--section") + 1] if "--section" in rest else "risk"
    stale = "--stale" in rest

    base = os.path.dirname(os.path.abspath(src))
    with open(src, encoding="utf-8") as fh:
        doc = json.load(fh)

    def absolute(value):
        return value if os.path.isabs(value) else os.path.normpath(os.path.join(base, value))

    for entry in doc.get("sections") or []:
        for key in ("store", "translations"):
            if entry.get(key):
                entry[key] = absolute(entry[key])
        if entry.get("section") != section or not entry.get("translations"):
            continue
        with open(entry["store"], encoding="utf-8") as fh:
            updated = str(json.load(fh).get("updatedAt") or "")
        with open(entry["translations"], encoding="utf-8") as fh:
            sidecar = json.load(fh)
        sidecar["boundTo"] = {"storeUpdatedAt": STALE if stale else updated}
        copy = os.path.join(workdir, f"bound-{section}.json")
        with open(copy, "w", encoding="utf-8") as fh:
            json.dump(sidecar, fh, ensure_ascii=False)
        entry["translations"] = copy
    if doc.get("throughLine"):
        doc["throughLine"] = absolute(doc["throughLine"])
    if doc.get("context"):
        doc["context"] = absolute(doc["context"])

    with open(dest, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=1, ensure_ascii=False)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
