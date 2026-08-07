#!/usr/bin/env python3
"""Build a manifest whose sections disagree about which organisation they describe.

The defect this exists for: a manifest could name one company on the cover and assemble its
sections from stores belonging to others. The shipped specimen did exactly that across three
fictional firms, and every page was individually correct — which is why nothing caught it.

Rather than shipping a permanently-wrong fixture, this MAKES one on demand: it copies a
section's store into the work directory, rewrites the organisation name in the copy, and
points an absolutised manifest at it. The committed stores stay honest and the suite still
gets a pack that genuinely disagrees with itself.

Paths are absolutised for the same reason `_ctxmanifest.py` absolutises them — a manifest
resolves its paths relative to its own directory, so a copy in a temp dir loses every store
and the suite reports an integrity defect that is really a fixture defect.

Its own file because a heredoc inside `$( ... )` is a parse error, which this repo has
already paid for more than once.

Usage:
  _orgfixture.py <src> <dest> <workdir> [--section NAME] [--org NAME]
                 [--declared-by NAME] [--basis TEXT]

  --section/--org   rewrite that section's store to name that organisation
  --declared-by     add a `consolidation` declaration; with --basis it is complete,
                    without one it is the unsigned case the guard must still refuse
"""
from __future__ import annotations

import json
import os
import sys

ORG_FIELDS = ("clientName", "orgName", "organisationName", "organizationName")


def _rewrite_org(src: str, dest: str, org: str) -> None:
    with open(src, encoding="utf-8") as fh:
        doc = json.load(fh)
    meta = doc.setdefault("meta", {})
    for field in ORG_FIELDS:
        if field in meta:
            meta[field] = org
            break
    else:
        meta["clientName"] = org
    with open(dest, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False)


def main(argv) -> int:
    src, dest, workdir = argv[0], argv[1], argv[2]
    rest = argv[3:]

    def opt(name, default=None):
        return rest[rest.index(name) + 1] if name in rest else default

    section = opt("--section", "metrics")
    org = opt("--org")
    declared_by = opt("--declared-by")
    basis = opt("--basis")

    base = os.path.dirname(os.path.abspath(src))
    with open(src, encoding="utf-8") as fh:
        doc = json.load(fh)

    def absolute(value):
        return value if os.path.isabs(value) else os.path.normpath(os.path.join(base, value))

    for entry in doc.get("sections") or []:
        for key in ("store", "translations"):
            if entry.get(key):
                entry[key] = absolute(entry[key])
        if org and entry.get("section") == section and entry.get("store"):
            copy = os.path.join(workdir, "org-" + os.path.basename(entry["store"]))
            _rewrite_org(entry["store"], copy, org)
            entry["store"] = copy
    if doc.get("throughLine"):
        doc["throughLine"] = absolute(doc["throughLine"])
    if doc.get("context"):
        doc["context"] = absolute(doc["context"])

    if declared_by is not None:
        doc["consolidation"] = {"declaredBy": declared_by}
        if basis is not None:
            doc["consolidation"]["basis"] = basis

    with open(dest, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=1, ensure_ascii=False)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
