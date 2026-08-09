#!/usr/bin/env python3
"""CAC-LE-1 — an eval script may not call a harness helper it does not define.

The standard is written up in tools/eval-lint-standard.md; this is its implementation.

Why this exists, and it is not a style rule.

`skills/risk-register/evals/board-safety.sh` gained an outcome-framing check written with
`ok`/`bad`. That suite declares `chk` and neither of the other two. Under `set -u` without
`set -e` — which is the house convention here, deliberately, so one failing check does not
abort the forty after it — an unrecognised command is a silent no-op: the shell wrote
`ok: command not found` to stderr, the failure counter stayed at zero, and the suite printed
`all checks passed` and exited 0. The check was never registered, so it could not fail, and
its greenness was indistinguishable from a real pass.

That is the same failure mode `prove-guards.sh` exists for at the guard layer — a check that
has stopped checking goes on printing `ok` forever — applied one level down, to the harness
itself. So it gets the same treatment: made data, and re-run every time.

The rule: for each `evals/*.sh`, every name in HARNESS that the script *calls* must also be
*defined* in that script or in a file it sources. Nothing else is inspected. This does not
try to be a shell linter; it answers one question, which is the question that was missed.

Exit 0 when clean, 1 otherwise. Usage: tools/lint-evals.py [--self-test] [paths...]
"""
import os
import re
import sys

# The helper vocabulary the suites in this repo use to REGISTER a check. A name here is one
# whose silent absence turns a check into a no-op. Deliberately a closed list: a generic
# "undefined function" linter would drown in the real commands these scripts run, and a check
# nobody reads is the thing being fixed, not a thing to add more of.
HARNESS = ("ok", "bad", "chk", "eq", "ne", "yn", "skip", "probe", "pass_line", "fail_line")

DEF_RE = re.compile(r"^\s*(?:function\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*\(\s*\)", re.M)
SOURCE_RE = re.compile(r"^\s*(?:\.|source)\s+(\S+)", re.M)
INLINE_C_RE = re.compile(r"(-c\s+)'[^']*'", re.S)


def _strip_inline_c(text):
    """Blank the payload of `python3 -c '...'`.

    Same reasoning as the heredoc stripper, different syntax. `nist-csf/evals/
    run-conversations.sh` embeds a Python program this way, and that program has a local
    variable called `bad` — which is also the name of a harness helper in eight of these
    suites. Without this the linter reported a Python assignment as an unregistered shell
    check, and a linter with a false positive on a real file is one that gets switched off.

    Only single-quoted payloads. A double-quoted one is shell-expanded, so a helper named in
    it could genuinely be one, and it is left visible.
    """
    def blank(m):
        return m.group(1) + "'" + "\n" * m.group(0).count("\n") + "'"
    return INLINE_C_RE.sub(blank, text)


def _strip_heredocs(text):
    """Drop quoted heredoc bodies — they are Python, not shell.

    Only quoted delimiters (`<<'PY'`, `<<"PY"`) are stripped. An unquoted heredoc is still
    shell-expanded, so a helper named in one is a real reference and stays visible.

    A body is BLANKED, never deleted, so every line number reported below is the line number
    in the file the reader is about to open. A linter that points three lines above the defect
    gets argued with rather than fixed.

    A heredoc opener inside a COMMENT is not an opener. Documenting the idiom in prose —
    `probe "$f" <<'PY' ... PY` — used to start a heredoc the stripper could never terminate,
    because the closing line was commented too and so never matched bare `PY`. Everything from
    that comment to the end of file was blanked, which meant the functions below it did not
    exist as far as this linter was concerned. `tools/eval-probe.sh` documents its own call
    shapes that way, so `probe` vanished and every suite sourcing it was reported as calling a
    helper nobody defines (BL-121).

    Worth naming plainly: **a comment could switch this linter off for the rest of a file**,
    and the only symptom was a confident, wrong failure. A silent pass would have been worse.
    """
    out, lines, i = [], text.split("\n"), 0
    while i < len(lines):
        line = lines[i]
        out.append(line)
        m = None if line.lstrip().startswith("#") else re.search(
            r"<<-?\s*(['\"])([A-Za-z_][A-Za-z0-9_]*)\1", line)
        i += 1
        if not m:
            continue
        end = m.group(2)
        while i < len(lines) and lines[i].strip() != end:
            out.append("")
            i += 1
        if i < len(lines):
            out.append(lines[i])
            i += 1
    return "\n".join(out)


def _uncommented(text):
    return "\n".join(re.sub(r"(?<!\S)#.*$", "", ln) for ln in text.split("\n"))


def defined_in(path, _seen=None):
    """Helpers this script defines, following `source`/`.` one level and then some."""
    _seen = _seen if _seen is not None else set()
    real = os.path.realpath(path)
    if real in _seen or not os.path.isfile(real):
        return set()
    _seen.add(real)
    with open(real, encoding="utf-8", errors="replace") as fh:
        raw = fh.read()
    body = _uncommented(_strip_inline_c(_strip_heredocs(raw)))
    names = set(DEF_RE.findall(body))
    for target in SOURCE_RE.findall(body):
        target = target.strip().strip('"').strip("'")
        # `$here` is this repo's universal convention for the sourcing script's own directory
        # — every eval sets `here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"` — so a
        # `$here/`-rooted source IS resolvable, and refusing to resolve it made every suite
        # sourcing `tools/eval-probe.sh` fail this lint with "calls `probe`, never defines it"
        # (BL-121). Any OTHER computed path is still skipped rather than guessed at.
        if target.startswith("$here/"):
            target = target[len("$here/"):]
        elif "$" in target:
            continue
        cand = target if os.path.isabs(target) else os.path.join(os.path.dirname(real), target)
        names |= defined_in(cand, _seen)
    return names


def called_in(path):
    """Harness helpers this script invokes, as a name -> first line number map.

    A call is the name in command position: start of line, or after `;`, `|`, `&&`, `||`,
    `(`, or one of the block keywords. `foo=$(...)` and `--ok` are not calls, and neither is
    the definition itself.
    """
    with open(path, encoding="utf-8", errors="replace") as fh:
        raw = fh.read()
    body = _uncommented(_strip_inline_c(_strip_heredocs(raw)))
    lead = r"(?:^|[;|&(]|\b(?:then|else|elif|do|fi|done)\s)\s*"
    found = {}
    for name in HARNESS:
        # `(?!\s*=)` keeps a Python assignment inside an inline script from reading as a
        # shell call. `ok "y"` is a call; `bad = [...]` never is, in any of these files.
        pattern = re.compile(lead + re.escape(name) + r"(?!\s*=)(?=\s+[^\s)])")
        for i, line in enumerate(body.split("\n"), 1):
            if re.search(r"^\s*(?:function\s+)?" + re.escape(name) + r"\s*\(", line):
                continue
            if pattern.search(line):
                found.setdefault(name, i)
                break
    return found


# LE-1.2 (BL-121). A suite that has adopted `probe` must not keep a raw inline capture.
#
# `hit=$($PY - "$f" <<'PY' ... PY)` discards the exit status, so a traceback leaves stdout
# empty — byte-for-byte what a clean run produces. The caller reads "nothing to report" and
# prints `ok`. Nine board-safety suites ran that idiom for fourteen versions after the fix was
# written in `assembly.sh` and copied nowhere.
#
# Scoped to files that source `tools/eval-probe.sh`, deliberately. Plenty of other captures in
# this repo take a VALUE and compare it — `n=$($PY -c '...print(count)')` then `[ "$n" -eq 5 ]`
# — where a crash yields an empty string and the comparison fails loudly. Those are a
# different shape and flagging them would be noise. What this stops is a migrated suite
# drifting back one line at a time.
_RAW_CAPTURE = re.compile(r"""\$\(\s*"?\$PY"?\s+-(?:c\b|\s)""")
_PROBE_SOURCE = "eval-probe.sh"


def lint(paths):
    problems = []
    for path in paths:
        try:
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
        except (OSError, UnicodeDecodeError):
            text = ""
        if _PROBE_SOURCE in text:
            for n, line in enumerate(text.split("\n"), 1):
                if line.lstrip().startswith("#") or _PROBE_SOURCE in line:
                    continue
                if _RAW_CAPTURE.search(line):
                    problems.append(
                        "%s:%d: captures an inline Python script directly. This suite sources "
                        "%s — route it through `probe`. Command substitution discards the exit "
                        "status, so a traceback and a clean run both leave stdout empty, and "
                        "the check reports `ok` without having examined anything."
                        % (os.path.relpath(path), n, _PROBE_SOURCE))
        defined = defined_in(path)
        for name, line in sorted(called_in(path).items()):
            if name not in defined:
                problems.append(
                    "%s:%d: calls `%s`, which this suite never defines. Under `set -u` "
                    "without `set -e` that line is a silent no-op: the check is never "
                    "registered, nothing increments the failure count, and the suite "
                    "reports green. Use a helper this suite declares (%s)."
                    % (os.path.relpath(path), line, name,
                       ", ".join(sorted(defined & set(HARNESS))) or "it declares none"))
    return problems


def discover(repo):
    out = []
    for base in ("skills", "tools"):
        for root, _dirs, files in os.walk(os.path.join(repo, base)):
            for fn in files:
                if fn.endswith(".sh"):
                    out.append(os.path.join(root, fn))
    return sorted(out)


def _self_test():
    """GP-1.4 in miniature: clean must pass, and the known defect must fail.

    A linter that only ever ran on a clean tree would be the same false green one level up.
    """
    import tempfile
    checks = 0

    def case(label, body, expect_problem, siblings=None):
        """`siblings` writes extra files beside the fixture, for the `source` cases."""
        nonlocal checks
        with tempfile.NamedTemporaryFile("w", suffix=".sh", delete=False) as fh:
            fh.write(body)
            name = fh.name
        extra = []
        for rel, text in (siblings or {}).items():
            p = os.path.join(os.path.dirname(name), rel)
            with open(p, "w", encoding="utf-8") as fh:
                fh.write(text)
            extra.append(p)
        try:
            got = bool(lint([name]))
            checks += 1
            status = "ok   " if got == expect_problem else "FAIL "
            print("  %s %s" % (status, label))
            return got == expect_problem
        finally:
            os.unlink(name)
            for p in extra:
                os.unlink(p)

    results = [
        # The exact v0.43.0 defect.
        case("a suite defining chk but calling ok is caught",
             'chk() { :; }\nchk 1 "x" PASS\nok "y"\n', True),
        case("a suite defining ok/bad and calling them is clean",
             'ok() { :; }\nbad() { :; }\nok "y"\nbad "z" "w"\n', False),
        case("`function ok {` style counts as a definition",
             'function ok() { :; }\nok "y"\n', False),
        # The false positives that would make this linter unusable, and so unread.
        case("a helper named only inside a quoted heredoc is not a call",
             'chk() { :; }\npython3 - <<\'PY\'\nok = 1\nprint("ok done")\nPY\n', False),
        case("a variable assignment is not a call",
             'chk() { :; }\nok=1\necho "$ok"\n', False),
        case("a bare word with no argument is not a call",
             'chk() { :; }\necho ok\n', False),
        case("a commented-out call is not a call",
             'chk() { :; }\n# ok "y"\n', False),
        case("a call in an else arm is caught",
             'chk() { :; }\nif true; then chk 1 a PASS; else bad "y" "z"; fi\n', True),
        # Both regressions found by running this linter over the real repo for the first time.
        case("a python variable inside `-c '...'` is not a call",
             'chk() { :; }\npython3 -c \'\nbad = [1]\nprint(bad)\n\'\n', False),
        case("a spaced assignment is not a call",
             'chk() { :; }\nok = 1\n', False),

        # --- BL-121. Three behaviours, each of which was wrong before v0.59.0. ---
        #
        # A heredoc opener inside a comment used to start a heredoc nothing could terminate,
        # blanking every definition below it. `tools/eval-probe.sh` documents its own call
        # shapes in prose, so `probe` disappeared and every suite sourcing it was reported as
        # calling a helper nobody defines.
        case("a heredoc opener inside a COMMENT does not blank the rest of the file",
             "# usage:  probe \"$f\" <<'PY' ... PY\nok() { :; }\nok \"y\"\n", False),
        case("...and a real quoted heredoc still is stripped",
             'ok() { :; }\npython3 - <<\'PY\'\nbad = 1\nPY\nok "y"\n', False),
        # `$here` is the repo's universal name for the sourcing script's own directory, so a
        # `$here/`-rooted source is resolvable. Skipping it as "computed" made the sourced
        # helper invisible, which is the same can't-see-it defect one level up.
        case("a `$here/`-rooted source is followed, so its helpers count as defined",
             'here="x"\n. "$here/le1-fixture.sh"\nprobe -c "print(1)"\n', False,
             {"le1-fixture.sh": "probe() { :; }\n"}),
        case("...and an unresolvable `$here/` source still reports the undefined helper",
             'here="x"\n. "$here/le1-absent.sh"\nprobe -c "print(1)"\n', True),
        # LE-1.2 itself, both directions.
        case("LE-1.2: a suite sourcing eval-probe.sh with a raw inline capture is caught",
             'here="x"\n. "$here/eval-probe.sh"\nhit=$($PY - "$f")\n', True,
             {"eval-probe.sh": "probe() { :; }\n"}),
        case("LE-1.2: the same suite routing through `probe` is clean",
             'here="x"\n. "$here/eval-probe.sh"\nhit=$(probe "$f")\n', False,
             {"eval-probe.sh": "probe() { :; }\n"}),
        case("LE-1.2: a suite that does NOT source it keeps its raw captures",
             'ok() { :; }\nn=$($PY -c \'print(1)\')\nok "y"\n', False),
    ]
    print("\nlint-evals self-test: %d checks, %d failed"
          % (checks, sum(1 for r in results if not r)))
    return 0 if all(results) else 1


def main(argv):
    if "--self-test" in argv:
        return _self_test()
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    paths = [a for a in argv if not a.startswith("-")] or discover(repo)
    if not paths:
        print("lint-evals: found no shell suites to lint, which is itself a failure")
        return 1
    problems = lint(paths)
    print("lint-evals (CAC-LE-1): %d suite(s) checked" % len(paths))
    for p in problems:
        print("  FAIL  %s" % p)
    if problems:
        print("\nlint-evals: %d unregistered check(s)" % len(problems))
        return 1
    print("  ok    every harness helper called is declared by the suite calling it")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
