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
    # Decoded as UTF-8 rather than by locale: with --name-only -z below, a non-ASCII
    # path arrives as raw bytes, and a C-locale runner would otherwise fail to decode
    # it. surrogateescape keeps even undecodable bytes intact instead of raising.
    return subprocess.run(["git", "-C", str(root)] + args, check=True,
                          capture_output=True, encoding="utf-8",
                          errors="surrogateescape").stdout


def _utf8_stdout():
    """Print UTF-8 whatever the runner's locale says.

    Decoding git's output and encoding our own are independent settings, and fixing
    only the first just moves the crash: under LC_ALL=C a non-ASCII path decodes
    cleanly in _git and then blows up on the way to stdout while the guard is trying
    to report the very violation it caught. backslashreplace also absorbs the
    surrogates _git's surrogateescape can produce, which fail to encode even in a
    UTF-8 locale.
    """
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    except (AttributeError, ValueError):
        pass  # stdout replaced by something without reconfigure; nothing to do


def _version_tuple(v):
    """(int, ...) for a dot-separated numeric version, else None."""
    try:
        return tuple(int(p) for p in str(v).split("."))
    except ValueError:
        return None


def _moved_forward(before, now):
    """True if `now` is strictly ahead of `before`.

    A downgrade is as much a silent no-op as standing still, so it does not count.
    Falls back to plain inequality when either side is not dot-separated ints, so an
    unusual scheme loses the direction check rather than crashing the guard.
    """
    b, n = _version_tuple(before), _version_tuple(now)
    if b is None or n is None:
        return now != before
    return n > b


def check_bump(base, root="."):
    """If anything under SHIPPED changed against `base`, every version string must
    have moved forward.

    Diffs with `base...HEAD` (three dots) so the comparison is against the merge base,
    not the tip of the base branch -- otherwise unrelated commits landing on main
    while a PR is open would be counted as this PR's changes.

    All four entries are witnessed, not one. Witnessing a single manifest would assume
    the base commit is internally consistent, and 18cfec5 -- the commit that motivated
    this file -- was not: it moved plugin.json to 0.4.1 and left marketplace.json at
    0.4.0. Against such a base, a head that converges every string onto 0.4.0 shows
    plugin.json "moving" 0.4.1 -> 0.4.0 while marketplace.json, the file
    `claude plugin update` actually reads, never moves at all. One witness plus a
    consistency check on the head passes that commit; four witnesses do not.
    """
    try:
        changed = _git(["diff", "--name-only", "-z", "{}...HEAD".format(base)],
                       root).split("\0")
    except subprocess.CalledProcessError:
        print("ERROR: cannot diff against base ref {!r}.".format(base))
        print("       Does this checkout have full history? CI needs fetch-depth: 0.")
        return False

    # -z both NUL-delimits and disables core.quotePath. Without it git renders a
    # non-ASCII path quoted ("skills/caf\303\251.md"), the leading quote defeats the
    # prefix test, and the change vanishes from this list.
    shipped = sorted(f for f in changed if f.startswith(SHIPPED))
    if not shipped:
        print("bump: no shipped file changed against {}; no bump required.".format(base))
        return True

    stale = []
    absent = []
    for path, keypath in MANIFESTS:
        try:
            raw = _git(["show", "{}:{}".format(base, path)], root)
        except subprocess.CalledProcessError:
            # New at base, so there is no prior version to compare against. Only a
            # clean sweep means a first release: one manifest arriving late must not
            # excuse the others from moving.
            absent.append(path)
            continue
        try:
            before = _dig(json.loads(raw), keypath)
        except (ValueError, KeyError):
            print("ERROR: {} is unreadable at {}: malformed JSON, or no such key.".format(
                _label(path, keypath), base))
            print("       Only a wholly absent manifest set means a first release. "
                  "This one is present and cannot be trusted, so the bump cannot be "
                  "verified.")
            return False
        now = _dig(json.loads((Path(root) / path).read_text(encoding="utf-8")), keypath)
        if not _moved_forward(before, now):
            stale.append((_label(path, keypath), before, now))

    if len(absent) == len(MANIFESTS):
        print("bump: no manifest exists at {}; treating as a first release.".format(
            base))
        return True

    if not stale:
        print("bump: {} shipped file(s) changed and all {} version strings moved "
              "forward.".format(len(shipped), len(MANIFESTS) - len(absent)))
        return True

    print("ERROR: {} shipped file(s) changed against {}, but {} of {} version strings "
          "did not move forward:".format(
              len(shipped), base, len(stale), len(MANIFESTS) - len(absent)))
    for label, before, now in stale:
        print("         {:<52} {} -> {}".format(label, before, now))
    for path in absent:
        print("         {:<52} (new at base)".format(path))
    print("       shipped:")
    for f in shipped[:10]:
        print("         {}".format(f))
    if len(shipped) > 10:
        print("         ... and {} more".format(len(shipped) - 10))
    print("       A version that does not move forward makes `claude plugin update` a "
          "silent no-op.")
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
    """Commit everything in a scratch repo, with identity, signing and hooks all
    supplied inline so the check never depends on the runner's global git config.
    A developer with commit.gpgsign or core.hooksPath set would otherwise see this
    self-test fail on their machine for reasons that have nothing to do with it."""
    subprocess.run(["git", "-C", str(root), "add", "-A"], check=True,
                   capture_output=True)
    subprocess.run(
        ["git", "-C", str(root),
         "-c", "user.email=selftest@example.invalid", "-c", "user.name=selftest",
         "-c", "commit.gpgsign=false", "-c", "core.hooksPath=/dev/null",
         "commit", "-q", "-m", message],
        check=True, capture_output=True)
    return subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"],
                          check=True, capture_output=True, text=True).stdout.strip()


def self_test():
    _utf8_stdout()  # reachable without going through main()
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
        base2 = _git_commit(repo, "bump")
        ok(check_bump(base, str(repo)) is True,
           "shipped change with a version bump passes")

        # docs-only change against the new base -> no bump required
        (repo / "docs" / "note.md").write_text("note v2\n", encoding="utf-8")
        _git_commit(repo, "docs only")
        ok(check_bump(base2, str(repo)) is True,
           "docs-only change needs no version bump")

        ok(check_bump("nosuchref", str(repo)) is False,
           "an unresolvable base ref fails")

        # -- a base whose manifest is present but malformed is not a first release --
        bad = Path(tmp) / "bad"
        bad.mkdir()
        subprocess.run(["git", "-C", str(bad), "init", "-q"], check=True,
                       capture_output=True)
        _write_manifests(bad, "1.0.0")
        (bad / ".claude-plugin" / "plugin.json").write_text(
            "{not json", encoding="utf-8")
        (bad / "skills").mkdir()
        (bad / "skills" / "SKILL.md").write_text("v1\n", encoding="utf-8")
        bad_base = _git_commit(bad, "base carrying a malformed manifest")
        _write_manifests(bad, "1.0.0")  # repaired, but the version never moved
        (bad / "skills" / "SKILL.md").write_text("v2\n", encoding="utf-8")
        _git_commit(bad, "shipped change")
        ok(check_bump(bad_base, str(bad)) is False,
           "a malformed manifest at base fails instead of passing as a first release")

        # -- the reviewed hole: one witness plus a consistent head passed 18cfec5 --
        skew = Path(tmp) / "skew"
        skew.mkdir()
        subprocess.run(["git", "-C", str(skew), "init", "-q"], check=True,
                       capture_output=True)
        _write_manifests(skew, "0.4.0")
        (skew / ".claude-plugin" / "plugin.json").write_text(
            json.dumps({"version": "0.4.1"}), encoding="utf-8")
        (skew / "skills").mkdir()
        (skew / "skills" / "SKILL.md").write_text("v1\n", encoding="utf-8")
        skew_base = _git_commit(skew, "base: plugin.json ahead of the other three")
        _write_manifests(skew, "0.4.0")  # head converges downward onto 0.4.0
        (skew / "skills" / "SKILL.md").write_text("v2\n", encoding="utf-8")
        _git_commit(skew, "converge downward, with a shipped change")
        ok(check_bump(skew_base, str(skew)) is False,
           "a downward convergence from an inconsistent base fails")
        ok(check_consistency(str(skew)) is True,
           "...and consistency alone would not have caught it")

        # -- Case A binds the four-witness loop on its own. The skew case above needs
        #    BOTH the loop and the forward-only rule to fail, so reverting either one
        #    alone left it green -- it tested the conjunction, not the mechanisms. Here
        #    plugin.json moves forward legitimately and the other three simply do not,
        #    so only the count of witnesses can catch it. --
        one = Path(tmp) / "one-witness"
        one.mkdir()
        subprocess.run(["git", "-C", str(one), "init", "-q"], check=True,
                       capture_output=True)
        _write_manifests(one, "1.0.0")
        (one / "skills").mkdir()
        (one / "skills" / "SKILL.md").write_text("v1\n", encoding="utf-8")
        one_base = _git_commit(one, "base: all four at 1.0.0")
        (one / ".claude-plugin" / "plugin.json").write_text(
            json.dumps({"version": "1.0.1"}), encoding="utf-8")
        (one / "skills" / "SKILL.md").write_text("v2\n", encoding="utf-8")
        _git_commit(one, "bump plugin.json alone, with a shipped change")
        ok(check_bump(one_base, str(one)) is False,
           "a bump in plugin.json alone fails: marketplace.json never moved")

        # -- Case B binds the forward-only rule on its own: all four move, so the
        #    witness count is satisfied and only direction can catch it. --
        down = Path(tmp) / "downgrade"
        down.mkdir()
        subprocess.run(["git", "-C", str(down), "init", "-q"], check=True,
                       capture_output=True)
        _write_manifests(down, "1.0.1")
        (down / "skills").mkdir()
        (down / "skills" / "SKILL.md").write_text("v1\n", encoding="utf-8")
        down_base = _git_commit(down, "base: all four at 1.0.1")
        _write_manifests(down, "1.0.0")
        (down / "skills" / "SKILL.md").write_text("v2\n", encoding="utf-8")
        _git_commit(down, "downgrade all four, with a shipped change")
        ok(check_bump(down_base, str(down)) is False,
           "a straight downgrade of all four fails: backwards ships nothing either")

        # -- a manifest merely new at base must not excuse the three that exist --
        partial = Path(tmp) / "partial"
        partial.mkdir()
        subprocess.run(["git", "-C", str(partial), "init", "-q"], check=True,
                       capture_output=True)
        _write_manifests(partial, "1.0.0")
        (partial / ".codex-plugin" / "plugin.json").unlink()
        (partial / "skills").mkdir()
        (partial / "skills" / "SKILL.md").write_text("v1\n", encoding="utf-8")
        partial_base = _git_commit(partial, "base lacking .codex-plugin/plugin.json")
        _write_manifests(partial, "1.0.0")  # adds it back; nothing else moves
        (partial / "skills" / "SKILL.md").write_text("v2\n", encoding="utf-8")
        _git_commit(partial, "add the missing manifest, with a shipped change")
        ok(check_bump(partial_base, str(partial)) is False,
           "one manifest new at base does not excuse the three that did not move")

        # -- git quotes non-ASCII paths by default; -z is what keeps them visible --
        uni = Path(tmp) / "unicode"
        uni.mkdir()
        subprocess.run(["git", "-C", str(uni), "init", "-q"], check=True,
                       capture_output=True)
        _write_manifests(uni, "1.0.0")
        (uni / "skills").mkdir()
        (uni / "skills" / "café.md").write_text("v1\n", encoding="utf-8")
        uni_base = _git_commit(uni, "base")
        (uni / "skills" / "café.md").write_text("v2\n", encoding="utf-8")
        _git_commit(uni, "shipped change to a non-ASCII path, no bump")
        ok(check_bump(uni_base, str(uni)) is False,
           "a non-ASCII shipped path is not lost to git's path quoting")

    print("\nself-test: {}/{} checks passed".format(sum(checks), len(checks)))
    return all(checks)


USAGE = "usage: check-versions.py [--base <ref>] [--self-test]"


def main(argv):
    _utf8_stdout()
    args = list(argv[1:])
    base = None
    want_self_test = False
    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "--self-test":
            want_self_test = True
        elif arg == "--base":
            if i + 1 >= len(args):
                print("ERROR: --base needs a git ref")
                return 1
            base = args[i + 1]
            i += 1
        else:
            # Silently ignoring a typo like --base-sha would leave the bump check
            # unrun and the script exiting 0 -- the same silent no-op this file exists
            # to eliminate.
            print("ERROR: unknown argument {!r}.".format(arg))
            print("       " + USAGE)
            return 1
        i += 1

    if want_self_test:
        return 0 if self_test() else 1

    # git reports paths from the repo root, so the manifests must be read from there
    # too. Resolving once keeps the two halves of check_bump talking about the same
    # files no matter which directory the script was invoked from.
    root = "."
    try:
        root = _git(["rev-parse", "--show-toplevel"]).strip()
    except (subprocess.CalledProcessError, OSError):
        print("note: not a git repository; checking the current directory instead.")

    passed = check_consistency(root)
    if base is not None:
        passed = check_bump(base, root) and passed
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
