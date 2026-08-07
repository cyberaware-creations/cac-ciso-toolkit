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
# version bump. docs/, tools/ and .github/ are excluded on purpose -- a spec or a CI
# tweak is not a release.
#
# LICENSE and NOTICE are bare filenames rather than prefixes, and they are here for a
# harder reason than the directories are: marketplace.json declares `"source": "./"`,
# so the repository root IS the plugin and both files land on a user's disk. Apache-2.0
# section 4(d) requires the NOTICE to travel with the distribution, so an updated
# attribution that never reaches an install is a licence problem, not just a stale file.
# README.md and SECURITY.md ship too but are deliberately absent: prose that describes
# the plugin is not the plugin, and gating a typo fix on a release would train people to
# bump for nothing -- which is how a guard stops being believed.
SHIPPED = ("skills/", "assets/", ".claude-plugin/", ".codex-plugin/", ".agents/",
           "LICENSE", "NOTICE")

# Libraries that live once in tools/ and are copied into each skill that uses them.
#
# The copies are not an accident to be cleaned up later. Every shipped script must run
# standalone -- a skill directory is usable on its own -- so a cross-skill import needs
# sys.path surgery and breaks the moment someone takes one skill. The same argument is
# written at the top of every _common.py.
#
# What duplication costs is drift: six copies of a file are six chances to fix a bug in
# one place and ship it in one. This check is the thing that makes the duplication safe,
# so it is not optional and it is not advisory.
#
# (canonical, directory glob, filename)
VENDORED = (
    ("tools/cac_graphics.py", "skills/*/renderers", "cac_graphics.py"),
)


def _dig(doc, keypath):
    """Walk a JSON document by a tuple of keys/indices."""
    for k in keypath:
        doc = doc[k]
    return doc


def _label(path, keypath):
    return "{}:{}".format(path, ".".join(str(k) for k in keypath))


def read_versions(root="."):
    """[(label, version)] for all four manifest entries.

    Each file is parsed once even though marketplace.json carries two of the four
    entries -- the cache is per-call, so a caller always sees one coherent snapshot
    rather than two reads that could straddle an edit.

    Raises OSError / ValueError / KeyError if a manifest is missing, malformed, or has
    lost its version key. check_consistency turns those into a stated reason; nothing
    here guesses at a value.
    """
    docs, out = {}, []
    for path, keypath in MANIFESTS:
        if path not in docs:
            docs[path] = json.loads((Path(root) / path).read_text(encoding="utf-8"))
        out.append((_label(path, keypath), _dig(docs[path], keypath)))
    return out


def check_consistency(root="."):
    try:
        rows = read_versions(root)
    except (OSError, ValueError, KeyError) as exc:
        # The module docstring promises "exit 1 with the reason". A traceback is an
        # exit 1 without one, and the file this fails on is sitting in the reader's own
        # working tree -- so name it rather than making them read a stack.
        print("ERROR: a version manifest could not be read: {}: {}".format(
            type(exc).__name__, exc))
        print("       Expected all of: {}".format(
            ", ".join(sorted({p for p, _ in MANIFESTS}))))
        return False
    for label, v in rows:
        print("  {:<52} {}".format(label, v))
    unparsed = sorted({v for _, v in rows if _version_tuple(v) is None})
    if unparsed:
        # Not a failure: an unusual scheme is allowed. But _moved_forward silently
        # degrades to plain inequality for it, so a downgrade would stop being caught.
        # Silent degradation in a guard is the thing this file exists to argue against.
        print("NOTE:  not dot-separated integers: {}. The bump check still requires a "
              "change,".format(", ".join(unparsed)))
        print("       but cannot tell forwards from backwards for these.")
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


def check_vendored(root="."):
    """Every vendored copy must be byte-identical to its canonical source in tools/.

    Three ways this can fail, and all three are failures rather than notes:

      * a copy differs      -- a fix landed in one place and ships from another
      * a copy is missing   -- the skill that needs it renders without it
      * no copy is found    -- the glob stopped matching

    The third is the one worth spelling out. A check that silently finds nothing to
    check reports success, and it reports it forever: rename `renderers/` and this
    turns into a guard that passes because it is no longer looking at anything. That
    is the same silent no-op the bump check exists to eliminate, so an empty match is
    an error here, not a quiet pass.
    """
    import hashlib

    root = Path(root)
    ok = True
    for canonical, dirglob, name in VENDORED:
        src = root / canonical
        try:
            want = hashlib.sha256(src.read_bytes()).hexdigest()
        except OSError as exc:
            print("ERROR: canonical {} could not be read: {}".format(canonical, exc))
            ok = False
            continue

        # Directories first, then the file inside them: a skill with renderers/ but no
        # copy is a missing vendor, which globbing for the file itself cannot see.
        dirs = sorted(p for p in root.glob(dirglob) if p.is_dir())
        if not dirs:
            print("ERROR: {!r} matched no directory. This check is not checking "
                  "anything.".format(dirglob))
            print("       If the layout moved, move VENDORED with it; a guard that "
                  "matches nothing passes forever.")
            ok = False
            continue

        drifted, missing = [], []
        for d in dirs:
            copy = d / name
            try:
                got = hashlib.sha256(copy.read_bytes()).hexdigest()
            except OSError:
                missing.append(copy.relative_to(root).as_posix())
                continue
            if got != want:
                drifted.append(copy.relative_to(root).as_posix())

        if not drifted and not missing:
            print("vendored: {} copies of {} match {}.".format(
                len(dirs), name, canonical))
            continue

        ok = False
        print("ERROR: {} of {} vendored copies of {} do not match {}:".format(
            len(drifted) + len(missing), len(dirs), name, canonical))
        for f in drifted:
            print("         {:<52} differs".format(f))
        for f in missing:
            print("         {:<52} missing".format(f))
        print("       Edit {} and copy it out; never edit a copy in place.".format(
            canonical))
    return ok


# The maker's name, and the one place it is allowed to be written down. `G.footer()` drops
# it when a client white-labels and keeps the NIST disclaimer; a renderer that spells it out
# by hand ships the maker's name onto a re-branded page and cannot be told to stop.
MAKER = "A Cyber Aware Creation"
MAKER_HOME = "cac_graphics.py"


def check_maker_name(root="."):
    """No shipped renderer may spell the maker's name out for itself.

    This existed as five hand-written copies, one per skill, each of them correct only
    because nothing could rebrand those renderers yet. The day one gains a brand flag, every
    copy becomes a white-label leak — and the copies are in five files nobody would think to
    open while adding that flag. So the rule is checked rather than remembered.

    An empty match is an error, on the same reasoning as check_vendored: a guard that stops
    finding files to guard reports success forever.
    """
    import pathlib
    base = pathlib.Path(root)
    scanned, offenders = 0, []
    for path in sorted(base.glob("skills/*/renderers/*.py")):
        if path.name == MAKER_HOME:
            continue                      # the one file entitled to hold the string
        scanned += 1
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        for n, line in enumerate(text.splitlines(), 1):
            if MAKER in line and not line.lstrip().startswith("#"):
                offenders.append((path.relative_to(base).as_posix(), n))
    if not scanned:
        print("ERROR: no shipped renderers were scanned for the maker name; the glob "
              "stopped matching and this check is no longer checking anything.")
        return False
    if offenders:
        print("ERROR: {} shipped renderer line(s) hardcode the maker name:".format(
            len(offenders)))
        for f, n in offenders:
            print("         {}:{}".format(f, n))
        print("       Call G.footer() instead — it drops the maker on a white-labelled "
              "page and keeps the NIST disclaimer. Call it at render time, not at import: "
              "the brand can be rebound after the module loads.")
        return False
    print("attribution: {} shipped renderers, none hardcodes the maker name.".format(
        scanned))
    return True


def check_skill_coverage(root="."):
    """Every shipped skill must be named in the user-facing description of every manifest.

    The manifests advertised three skills for five releases while the repository shipped
    seven, and it took an external tester to notice. Nothing was invalid — the JSON parsed,
    the versions agreed, CI was green — so no guard here had anything to say about it. That
    is the shape of the failure: a description is prose, prose drifts from the product
    silently, and the only reader who finds out is the one deciding whether to install.

    Matching on the skill's DIRECTORY NAME rather than on any prose summary of it. A
    description that names `incident-materiality` has said the thing a marketplace search
    can find; one that says "we also handle disclosure" has not, and a check that accepted
    the second would pass on text that mentions no skill at all.

    An empty scan is an error, on the same reasoning as every guard above it.
    """
    import pathlib
    base = pathlib.Path(root)
    skills = sorted(p.parent.name for p in base.glob("skills/*/SKILL.md"))
    if not skills:
        print("ERROR: no skills were found to check against the manifests; the glob "
              "stopped matching and this check is no longer checking anything.")
        return False

    # field path -> the blob a reader actually sees. Listed individually: a walk of every
    # string in the file would pass on a keyword array and prove nothing.
    targets = [
        (".claude-plugin/plugin.json", ("description",)),
        (".codex-plugin/plugin.json", ("description",)),
        (".codex-plugin/plugin.json", ("interface", "longDescription")),
        (".claude-plugin/marketplace.json", ("plugins", 0, "description")),
    ]
    problems = []
    for rel, path in targets:
        try:
            node = json.loads((base / rel).read_text(encoding="utf-8"))
            for key in path:
                node = node[key]
        except (OSError, ValueError, KeyError, IndexError, TypeError) as exc:
            problems.append("{}:{} could not be read ({})".format(
                rel, ".".join(str(k) for k in path), exc))
            continue
        absent = [s for s in skills if s not in node]
        if absent:
            problems.append("{}:{} never names {}".format(
                rel, ".".join(str(k) for k in path), ", ".join(absent)))
    if problems:
        print("ERROR: shipped skills missing from a user-facing description:")
        for p in problems:
            print("         {}".format(p))
        print("       A skill nobody can find in the marketplace listing ships to nobody. "
              "Name it, or remove the skill.")
        return False
    print("coverage: {} shipped skills, each named in all {} manifest descriptions.".format(
        len(skills), len(targets)))
    return True


PALETTE_NAMES = frozenset({
    "INK", "INK_RAISED", "INK_LINE", "LIME", "LIME_DIM", "PATINA", "PATINA_H",
    "PATINA_TEXT", "SLATE", "WB", "WB_SURF", "WB_LINE", "MUTED", "text_on",
})
# Names allowed to hold a palette value at module level: the primitives themselves, the
# brand plumbing, and the placeholder a rebuild function fills in later.
PALETTE_PLUMBING = frozenset({"_BRAND_BINDINGS", "_BRAND_DEFAULTS"})
# Bindings that come from the library's RAG ramp, which does not move under a client brand:
# status colour is a contract with the reader, not a thing the client restyles.
PALETTE_FIXED = frozenset({"BAND", "BAND_TEXT"})


def check_import_time_palette(root="."):
    """No shipped renderer may bake a palette value into a module-level constant.

    This is the bug that made `--brand` a half-feature four separate times: a stylesheet, a
    chrome block, a fill map and a chip-text map, each an f-string or dict evaluated at
    import — which is before any brand is applied — so an override reached the charts and
    left the page around them in CAC colours. Every one of them was invisible until a page
    was rendered twice and diffed.

    The rule is therefore structural: if a module-level assignment reads a palette name, it
    froze that value at import. Build it in a function instead, and call the function.

    The names in PALETTE_ALLOWED are the exceptions, and they are exceptions for one reason:
    each is either a primitive definition or is reassigned by a `_rebuild_derived()` that
    `apply_brand` calls. Adding a name here without that reassignment reopens the hole.
    """
    import ast
    import pathlib
    base = pathlib.Path(root)
    scanned, offenders = 0, []
    for path in sorted(base.glob("skills/*/renderers/*.py")):
        if path.name == "cac_graphics.py":
            continue
        scanned += 1
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError):
            continue
        rebuilt = set()
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name == "_rebuild_derived":
                for inner in ast.walk(node):
                    if isinstance(inner, ast.Global):
                        rebuilt.update(inner.names)
        for node in tree.body:                      # module level only, by construction
            if not isinstance(node, ast.Assign):
                continue
            targets = {t.id for t in node.targets if isinstance(t, ast.Name)}
            if targets & (PALETTE_NAMES | PALETTE_PLUMBING | PALETTE_FIXED):
                continue
            # A name reassigned by this module's _rebuild_derived() is fine: the binding
            # below is only there so the name exists during the rest of the import, and
            # apply_brand() recomputes it. Verified against the actual `global` statement
            # rather than taken on trust from a hand-maintained list — an allow-list nobody
            # checks is how the exemption outlives the thing that justified it.
            if targets & rebuilt:
                continue
            used = {n.id for n in ast.walk(node.value)
                    if isinstance(n, ast.Name) and n.id in PALETTE_NAMES}
            used |= {n.attr for n in ast.walk(node.value)
                     if isinstance(n, ast.Attribute) and n.attr in PALETTE_NAMES}
            if used:
                offenders.append((path.relative_to(base).as_posix(), node.lineno,
                                  ", ".join(sorted(targets)) or "<assignment>",
                                  ", ".join(sorted(used))))
    if not scanned:
        print("ERROR: no shipped renderers were scanned for import-time palette use; the "
              "glob stopped matching and this check is no longer checking anything.")
        return False
    if offenders:
        print("ERROR: {} module-level assignment(s) freeze a palette value at import:".format(
            len(offenders)))
        for f, n, tgt, used in offenders:
            print("         {}:{}  {} reads {}".format(f, n, tgt, used))
        print("       Build it inside a function and call the function at render time. A "
              "value bound at import is bound before --brand is applied, so it ships CAC "
              "colours on a client's page.")
        return False
    print("chrome: {} shipped renderers, none freezes a palette value at import.".format(
        scanned))
    return True


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


def _fs_holds(name):
    """True if this filesystem's encoding can represent `name` as a filename."""
    try:
        name.encode(sys.getfilesystemencoding())
        return True
    except (UnicodeEncodeError, LookupError):
        return False


def self_test():
    _utf8_stdout()  # reachable without going through main()
    checks, skipped = [], []

    def ok(cond, label):
        checks.append(bool(cond))
        print("{:<4} {}".format("PASS" if cond else "FAIL", label))

    # Decoding git's output and encoding our own are separate settings, and the café
    # case below only reaches the second one on a filesystem that can hold the name --
    # which Linux under LC_ALL=C cannot. This asserts the stdout half on its own, so
    # the locale run still proves something where the filesystem forces a skip.
    try:
        print("     (stdout carries non-ASCII: café)")
        ok(True, "stdout carries non-ASCII whatever the locale says")
    except UnicodeEncodeError:
        ok(False, "stdout carries non-ASCII whatever the locale says")

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

        # A manifest that is malformed, absent, or has lost its version key must fail
        # with a stated reason rather than a traceback -- an exit 1 either way, but the
        # module docstring promises the reason, and a stack is not one.
        broken = Path(tmp) / "broken"
        broken.mkdir()
        _write_manifests(broken, "1.2.3")
        (broken / ".codex-plugin" / "plugin.json").write_text("{not json",
                                                              encoding="utf-8")
        ok(check_consistency(str(broken)) is False,
           "a malformed manifest fails with a reason, not a traceback")

        gone = Path(tmp) / "gone"
        gone.mkdir()
        _write_manifests(gone, "1.2.3")
        (gone / ".codex-plugin" / "plugin.json").unlink()
        ok(check_consistency(str(gone)) is False,
           "an absent manifest fails with a reason, not a traceback")

        keyless = Path(tmp) / "keyless"
        keyless.mkdir()
        _write_manifests(keyless, "1.2.3")
        (keyless / ".codex-plugin" / "plugin.json").write_text(
            json.dumps({"name": "x"}), encoding="utf-8")
        ok(check_consistency(str(keyless)) is False,
           "a manifest missing its version key fails with a reason")

        # An unusual scheme is allowed through consistency -- it just loses the
        # direction check, which check_consistency now says out loud.
        odd = Path(tmp) / "odd"
        odd.mkdir()
        _write_manifests(odd, "1.2.3-rc1")
        ok(check_consistency(str(odd)) is True,
           "a non-numeric scheme still passes consistency, with a note")

        # -- vendored-copy drift, no git needed --
        #
        # Each case isolates one mechanism. Matching-copies-pass on its own would be
        # satisfied by a function that returns True unconditionally, so the three
        # failures below are what actually bind it.
        def _vendor_tree(name, bodies, canonical=b"CANON\n"):
            """bodies = {skill: content|None}; None means the copy is absent."""
            r = Path(tmp) / name
            (r / "tools").mkdir(parents=True, exist_ok=True)
            (r / "tools" / "cac_graphics.py").write_bytes(canonical)
            for skill, body in bodies.items():
                d = r / "skills" / skill / "renderers"
                d.mkdir(parents=True, exist_ok=True)
                if body is not None:
                    (d / "cac_graphics.py").write_bytes(body)
            return r

        ok(check_vendored(str(_vendor_tree(
            "vend-match", {"a": b"CANON\n", "b": b"CANON\n"}))) is True,
           "vendored copies identical to the canonical pass")

        ok(check_vendored(str(_vendor_tree(
            "vend-drift", {"a": b"CANON\n", "b": b"CANON edited in place\n"}))) is False,
           "one edited vendored copy fails")

        ok(check_vendored(str(_vendor_tree(
            "vend-missing", {"a": b"CANON\n", "b": None}))) is False,
           "a skill with renderers/ but no copy fails")

        # The reviewed hole in this shape: a guard that matches nothing reports success
        # and keeps reporting it. No skills/ at all must fail, not pass vacuously.
        empty = Path(tmp) / "vend-empty"
        (empty / "tools").mkdir(parents=True, exist_ok=True)
        (empty / "tools" / "cac_graphics.py").write_bytes(b"CANON\n")
        ok(check_vendored(str(empty)) is False,
           "a glob that matches no directory fails instead of passing vacuously")

        # A canonical that cannot be read is a failure with a reason, not a traceback.
        nocanon = Path(tmp) / "vend-nocanon"
        (nocanon / "skills" / "a" / "renderers").mkdir(parents=True, exist_ok=True)
        ok(check_vendored(str(nocanon)) is False,
           "an unreadable canonical fails with a reason")

        # -- every shipped skill is named in every manifest description --
        def _cov_tree(name, skills, described):
            r = Path(tmp) / name
            for s in skills:
                (r / "skills" / s).mkdir(parents=True, exist_ok=True)
                (r / "skills" / s / "SKILL.md").write_text("# %s\n" % s, encoding="utf-8")
            blob = "Skills: " + ", ".join(described) + "."
            (r / ".claude-plugin").mkdir(parents=True, exist_ok=True)
            (r / ".codex-plugin").mkdir(parents=True, exist_ok=True)
            (r / ".claude-plugin" / "plugin.json").write_text(
                json.dumps({"description": blob}), encoding="utf-8")
            (r / ".codex-plugin" / "plugin.json").write_text(
                json.dumps({"description": blob,
                            "interface": {"longDescription": blob}}), encoding="utf-8")
            (r / ".claude-plugin" / "marketplace.json").write_text(
                json.dumps({"plugins": [{"description": blob}]}), encoding="utf-8")
            return r

        ok(check_skill_coverage(str(_cov_tree(
            "cov-all", ["risk-register", "board-pack"],
            ["risk-register", "board-pack"]))) is True,
           "a description naming every shipped skill passes")

        # The reported defect, reproduced: the manifests describe a subset of what ships.
        ok(check_skill_coverage(str(_cov_tree(
            "cov-short", ["risk-register", "board-pack", "business-context"],
            ["risk-register", "board-pack"]))) is False,
           "a description that omits a shipped skill fails")

        # And the vacuity hole this shares with every guard above it.
        ok(check_skill_coverage(str(_cov_tree("cov-none", [], ["risk-register"]))) is False,
           "no skills found fails instead of passing vacuously")

        # A manifest that cannot be read is a reported problem, not a traceback.
        broken = _cov_tree("cov-broken", ["risk-register"], ["risk-register"])
        (broken / ".claude-plugin" / "plugin.json").write_text("{ not json",
                                                               encoding="utf-8")
        ok(check_skill_coverage(str(broken)) is False,
           "an unreadable manifest fails with a reason")

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
        base3 = _git_commit(repo, "docs only")
        ok(check_bump(base2, str(repo)) is True,
           "docs-only change needs no version bump")

        # NOTICE is a bare filename in SHIPPED, not a prefix. It ships because the repo
        # root is the plugin, and Apache-2.0 4(d) obliges it to travel -- so an updated
        # attribution with no bump must fail exactly like a skills/ change does.
        (repo / "NOTICE").write_text("attribution v2\n", encoding="utf-8")
        _git_commit(repo, "NOTICE change, no bump")
        ok(check_bump(base3, str(repo)) is False,
           "a NOTICE change without a version bump fails")

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
        #
        # This case needs a filesystem that can hold the name. Under LC_ALL=C on Linux
        # sys.getfilesystemencoding() is 'ascii' and creating it raises before the check
        # is ever reached -- macOS always encodes filenames as UTF-8, so a laptop cannot
        # show you this. It is reported as a skip rather than a pass: a case that did not
        # run has not proved anything, and counting it would be the vacuous green this
        # file exists to argue against.
        if _fs_holds("café.md"):
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
        else:
            skipped.append("non-ASCII shipped path")
            print("SKIP a non-ASCII shipped path: filesystem encoding is {}, which "
                  "cannot".format(sys.getfilesystemencoding()))
            print("     represent the filename. The -z handling is covered by the same "
                  "case under a UTF-8 filesystem.")

    print("\nself-test: {}/{} checks passed{}".format(
        sum(checks), len(checks),
        ", {} skipped ({})".format(len(skipped), "; ".join(skipped)) if skipped else ""))
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
    passed = check_vendored(root) and passed
    passed = check_maker_name(root) and passed
    passed = check_import_time_palette(root) and passed
    passed = check_skill_coverage(root) and passed
    if base is not None:
        passed = check_bump(base, root) and passed
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
