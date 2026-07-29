#!/usr/bin/env python3
"""Version-manifest guard.

Four version strings describe this plugin, across three files. They must agree with
each other, and they must move when shipped content moves.

Both halves exist because both halves failed. Commit 18cfec5 bumped
.claude-plugin/plugin.json to 0.4.1 and left the other three at 0.4.0 -- and since
`claude plugin update` reads .claude-plugin/marketplace.json, those 0.4.1 fixes were
not reachable by any install. On the same branch, four of five fix commits bumped
nothing at all.

That is the same shape as the v0.1.4 incident that put evals.yml on every push, and it
gets the same answer, already written at the top of that workflow: a release checklist
a human has to remember is not a check.

  ./tools/check-versions.py                 # consistency only
  ./tools/check-versions.py --base <ref>    # consistency + bump-on-change
  ./tools/check-versions.py --self-test     # exercise both checks in a scratch repo

Exit 0 = all checks passed. Exit 1 = at least one failed, with the reason.
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

# Every version string that describes this plugin. .agents/plugins/marketplace.json is
# deliberately absent: it declares `source: local, path: ./` and carries no version of
# its own, so it inherits and cannot drift.
MANIFESTS = (
    (".claude-plugin/plugin.json", ("version",)),
    (".claude-plugin/marketplace.json", ("version",)),
    (".claude-plugin/marketplace.json", ("plugins", 0, "version")),
    (".codex-plugin/plugin.json", ("version",)),
)

# Path prefixes whose contents reach a user's install. Changing any of them obliges a
# version bump. docs/, tools/, .github/ and the top-level prose files are excluded on
# purpose -- a spec or a CI tweak is not a release.
SHIPPED = ("skills/", "assets/", ".claude-plugin/", ".codex-plugin/", ".agents/")


def _dig(doc, keypath):
    """Walk a JSON document by a tuple of keys/indices."""
    for k in keypath:
        doc = doc[k]
    return doc


def _label(path, keypath):
    return "{}:{}".format(path, ".".join(str(k) for k in keypath))


def read_versions(root="."):
    """[(label, version)] for all four manifest entries."""
    out = []
    for path, keypath in MANIFESTS:
        doc = json.loads((Path(root) / path).read_text(encoding="utf-8"))
        out.append((_label(path, keypath), _dig(doc, keypath)))
    return out


def check_consistency(root="."):
    rows = read_versions(root)
    for label, v in rows:
        print("  {:<52} {}".format(label, v))
    distinct = sorted({v for _, v in rows})
    if len(distinct) == 1:
        print("consistency: all {} version strings agree ({}).".format(
            len(rows), distinct[0]))
        return True
    print("ERROR: {} different versions across {} manifest entries: {}".format(
        len(distinct), len(rows), ", ".join(distinct)))
    print("       `claude plugin update` reads .claude-plugin/marketplace.json.")
    print("       A version that moved only in plugin.json never reaches an install.")
    return False


def main(argv):
    args = list(argv[1:])
    if "--self-test" in args:
        return 0 if self_test() else 1
    base = None
    if "--base" in args:
        i = args.index("--base")
        if i + 1 >= len(args):
            print("ERROR: --base needs a git ref")
            return 1
        base = args[i + 1]
    passed = check_consistency()
    if base is not None:
        passed = check_bump(base) and passed
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
