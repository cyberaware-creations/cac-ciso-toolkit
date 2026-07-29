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


def _git(args, root="."):
    return subprocess.run(["git", "-C", str(root)] + args, check=True,
                          capture_output=True, text=True).stdout


def check_bump(base, root="."):
    """If anything under SHIPPED changed against `base`, the version must have moved.

    Diffs with `base...HEAD` (three dots) so the comparison is against the merge base,
    not the tip of the base branch -- otherwise unrelated commits landing on main
    while a PR is open would be counted as this PR's changes.
    """
    try:
        changed = _git(["diff", "--name-only", "{}...HEAD".format(base)], root).split()
    except subprocess.CalledProcessError:
        print("ERROR: cannot diff against base ref {!r}.".format(base))
        print("       Does this checkout have full history? CI needs fetch-depth: 0.")
        return False

    shipped = sorted(f for f in changed if f.startswith(SHIPPED))
    if not shipped:
        print("bump: no shipped file changed against {}; no bump required.".format(base))
        return True

    path, keypath = MANIFESTS[0]
    try:
        before = _dig(json.loads(_git(["show", "{}:{}".format(base, path)], root)),
                      keypath)
    except (subprocess.CalledProcessError, KeyError, ValueError):
        print("bump: {} unreadable at {}; treating as a first release.".format(
            path, base))
        return True

    now = _dig(json.loads((Path(root) / path).read_text(encoding="utf-8")), keypath)
    if now != before:
        print("bump: {} shipped file(s) changed and the version moved {} -> {}.".format(
            len(shipped), before, now))
        return True

    print("ERROR: {} shipped file(s) changed against {}, but the version is still "
          "{}.".format(len(shipped), base, now))
    for f in shipped[:10]:
        print("         {}".format(f))
    if len(shipped) > 10:
        print("         ... and {} more".format(len(shipped) - 10))
    print("       An unchanged version makes `claude plugin update` a silent no-op.")
    return False


# -- self-test ------------------------------------------------------------------


def _write_manifests(root, version):
    """Lay down the four version strings in a scratch tree."""
    (root / ".claude-plugin").mkdir(parents=True, exist_ok=True)
    (root / ".codex-plugin").mkdir(parents=True, exist_ok=True)
    (root / ".claude-plugin" / "plugin.json").write_text(
        json.dumps({"version": version}), encoding="utf-8")
    (root / ".claude-plugin" / "marketplace.json").write_text(
        json.dumps({"version": version, "plugins": [{"version": version}]}),
        encoding="utf-8")
    (root / ".codex-plugin" / "plugin.json").write_text(
        json.dumps({"version": version}), encoding="utf-8")


def _git_commit(root, message):
    """Commit everything in a scratch repo, with identity supplied inline so the
    check never depends on the runner's global git config."""
    subprocess.run(["git", "-C", str(root), "add", "-A"], check=True,
                   capture_output=True)
    subprocess.run(
        ["git", "-C", str(root),
         "-c", "user.email=selftest@example.invalid", "-c", "user.name=selftest",
         "commit", "-q", "-m", message],
        check=True, capture_output=True)
    return subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"],
                          check=True, capture_output=True, text=True).stdout.strip()


def self_test():
    checks = []

    def ok(cond, label):
        checks.append(bool(cond))
        print("{:<4} {}".format("PASS" if cond else "FAIL", label))

    with tempfile.TemporaryDirectory() as tmp:
        # -- consistency, no git needed --
        agree = Path(tmp) / "agree"
        agree.mkdir()
        _write_manifests(agree, "1.2.3")
        ok(check_consistency(str(agree)) is True,
           "four matching version strings pass consistency")

        drift = Path(tmp) / "drift"
        drift.mkdir()
        _write_manifests(drift, "1.2.3")
        (drift / ".codex-plugin" / "plugin.json").write_text(
            json.dumps({"version": "1.2.4"}), encoding="utf-8")
        ok(check_consistency(str(drift)) is False,
           "one divergent version string fails consistency")

        # -- bump-on-change, needs a real repo --
        repo = Path(tmp) / "repo"
        repo.mkdir()
        subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True,
                       capture_output=True)
        _write_manifests(repo, "1.0.0")
        (repo / "skills").mkdir()
        (repo / "skills" / "SKILL.md").write_text("v1\n", encoding="utf-8")
        (repo / "docs").mkdir()
        (repo / "docs" / "note.md").write_text("note\n", encoding="utf-8")
        base = _git_commit(repo, "base")

        # shipped file changed, version did not -> must fail
        (repo / "skills" / "SKILL.md").write_text("v2\n", encoding="utf-8")
        _git_commit(repo, "shipped change, no bump")
        ok(check_bump(base, str(repo)) is False,
           "shipped change without a version bump fails")

        # same change, now with a bump -> must pass
        _write_manifests(repo, "1.0.1")
        _git_commit(repo, "bump")
        ok(check_bump(base, str(repo)) is True,
           "shipped change with a version bump passes")

        # docs-only change against the new base -> no bump required
        base2 = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"],
                               check=True, capture_output=True,
                               text=True).stdout.strip()
        (repo / "docs" / "note.md").write_text("note v2\n", encoding="utf-8")
        _git_commit(repo, "docs only")
        ok(check_bump(base2, str(repo)) is True,
           "docs-only change needs no version bump")

    print("\nself-test: {}/{} checks passed".format(sum(checks), len(checks)))
    return all(checks)


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
