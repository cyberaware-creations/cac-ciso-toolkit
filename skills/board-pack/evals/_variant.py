#!/usr/bin/env python3
"""_variant.py — write a variant of the shipped manifest into a temp directory.

Used only by `assembly.sh`. Every path in the shipped manifest is relative to the manifest's
own directory, so a copy written into a temp dir resolves none of them. This absolutises them
first, then applies the caller's mutation.

That is not a convenience. Without it a variant fails because nothing could be found, and a
refusal check passes for entirely the wrong reason — which is what the first run of that
suite did on three of its four refusal cases.

Usage: _variant.py <source-manifest> <out-manifest> <python-snippet mutating `m`>
"""
import json
import os
import sys


def main() -> int:
    src, out, snippet = sys.argv[1], sys.argv[2], sys.argv[3]
    base = os.path.dirname(os.path.abspath(src))
    with open(src, encoding="utf-8") as fh:
        m = json.load(fh)
    for entry in m.get("sections") or []:
        for key in ("translations", "store"):
            if entry.get(key):
                entry[key] = os.path.normpath(os.path.join(base, entry[key]))
    if m.get("throughLine"):
        m["throughLine"] = os.path.normpath(os.path.join(base, m["throughLine"]))
    exec(snippet, {"m": m})  # noqa: S102 — the snippet is this repo's own eval code
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(m, fh, indent=2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
