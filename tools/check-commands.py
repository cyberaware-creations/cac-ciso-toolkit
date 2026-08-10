#!/usr/bin/env python3
"""CAC-CD-1 — every command an engine accepts is a command the docs name.

The v0.44.0 release note said BL-115's fix came *"with a check that compares the list against
`COMMANDS`"*. **No such check existed.** Grepping every `.py`, `.sh` and `.md` found exactly one
consumer of any engine's `COMMANDS` outside its own file — `policy-register/evals/no-deletion.sh`
reading policy-register's to assert no subcommand deletes anything. `SKILL.md` was honest where
the changelog was not: it said the list *"can be checked against `COMMANDS` rather than trusted"*.

For a repo whose Gate 1 is *nothing shipped contradicts what the docs say it does*, a release
note claiming a guard that was never written is the defect in the document a reader trusts most
about what changed. This file is that guard, built (BL-192).

TWO DEFECTS, AND THEY ARE NOT THE SAME SHAPE.

  1. HELP DRIFT — the command exists and `--help` does not list it, so a user cannot discover
     it at the terminal. Only possible in the three engines whose `main()` does
     `print(__doc__)`: their help text is prose somebody maintains by hand. **Two of the three
     were affected** — `import-findings` in risk-register and `crosswalk` in nist-csf, both
     real commands with handlers, named in `SKILL.md`, absent from the text `--help` prints.
     The nine argparse engines generate help from `add_parser`, so theirs **cannot** drift, and
     this check says so rather than pretending to have tested it.

  2. DOC DRIFT — the command exists and no shipped document names it. Possible everywhere, and
     it was nearly everywhere: `vendor-register` had 8 of 20 undocumented.

WHICH DOCUMENTS COUNT (BL-192 Q1, decided 2026-08-10). `SKILL.md` **and** the skill's
`references/*.md`. The question this check answers is *can a reader of the shipped docs discover
this command*, and a `references/` page is shipped documentation the `SKILL.md` points at.
Counting `SKILL.md` alone would force a command documented in depth under `references/` to be
duplicated into the index page in order to satisfy a checker, which is the tool dictating where
prose lives. Three commands are documented exactly that way today.

ANTI-VACUITY IS THE POINT, NOT A DETAIL. An engine this file parses to zero commands **fails**.
A checker that reports success without having tested anything is precisely the defect being
fixed here, and it is the one that survives longest, because it looks identical to working.

Usage:  check-commands.py [repo-root]
        check-commands.py --self-test
"""
import ast
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.abspath(os.path.join(_HERE, ".."))

# The registry is EXPLICIT, like check-twins.py's. A glob over skills/*/scripts/*.py would go
# green the day a directory is renamed, and would silently drop an engine rather than fail.
# `helpFrom` records how each engine produces `--help`, because that decides whether defect 1
# is even reachable for it — and stating it per engine is how a future conversion to argparse
# gets noticed here instead of quietly disabling a check.
ENGINES = (
    ("risk-register", "score_register.py", "docstring"),
    ("nist-csf", "profile_analysis.py", "docstring"),
    ("nist-csf", "csfa_compat.py", "docstring"),
    ("vendor-register", "vendor_register.py", "argparse"),
    ("ai-register", "ai_register.py", "argparse"),
    ("board-pack", "assemble_pack.py", "argparse"),
    ("incident-materiality", "incident_analysis.py", "argparse"),
    ("business-context", "business_context.py", "argparse"),
    ("exceptions-register", "exceptions_register.py", "argparse"),
    ("metrics-register", "metrics_analysis.py", "argparse"),
    ("attention-surface", "attention_surface.py", "argparse"),
    ("policy-register", "policy_register.py", "argparse"),
)

# `self-test` and `validate` are engine plumbing rather than a CISO's vocabulary, and every
# skill's docs mention them where they matter. Exempted BY NAME with the reason here, never by
# a pattern: an exemption that matches a shape rather than a string grows silently.
_NOT_USER_FACING = {
    "self-test": "the engine's own test entry point, run by CI and named in tools/README.md",
}


def commands_of(source: str) -> set:
    """Every subcommand an engine accepts, from its own source.

    Two idioms, and both are read from the AST rather than by regex: a module-level `COMMANDS`
    dict whose keys are the command names, and `add_parser("name")` calls. An engine may use
    either; several use one and expose the other privately.
    """
    tree = ast.parse(source)
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if (isinstance(target, ast.Name) and target.id == "COMMANDS"
                        and isinstance(node.value, ast.Dict)):
                    for key in node.value.keys:
                        if isinstance(key, ast.Constant) and isinstance(key.value, str):
                            names.add(key.value)
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == "add_parser" and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)):
            names.add(node.args[0].value)
    return names


def _mentions(text: str, cmd: str) -> bool:
    """Is `cmd` named in this prose as a command, not merely as a substring?

    Bounded on both sides by something that is not a word character or a hyphen, so `add` does
    not match inside `add-theme` and `export` does not match inside `export-findings`. That
    distinction is the whole reason this is not a plain `in` test: the undocumented commands
    found here are overwhelmingly the hyphenated ones, and every one of them contains a
    documented shorter command as a prefix.
    """
    return re.search(r"(?<![\w-])%s(?![\w-])" % re.escape(cmd), text) is not None


def docs_text(repo: str, skill: str) -> str:
    """SKILL.md plus every references/*.md — the shipped documentation surface (Q1)."""
    parts = []
    base = os.path.join(repo, "skills", skill)
    for rel in ["SKILL.md"]:
        path = os.path.join(base, rel)
        if os.path.isfile(path):
            parts.append(open(path, encoding="utf-8").read())
    refs = os.path.join(base, "references")
    if os.path.isdir(refs):
        for name in sorted(os.listdir(refs)):
            if name.endswith(".md"):
                parts.append(open(os.path.join(refs, name), encoding="utf-8").read())
    return "\n".join(parts)


def run(repo: str, engines=ENGINES):
    """Returns (problems, counts). Every engine is reported, green or not."""
    problems, rows = [], []
    total_cmds = 0
    for skill, script, help_from in engines:
        path = os.path.join(repo, "skills", skill, "scripts", script)
        if not os.path.isfile(path):
            problems.append("%s/%s: not on disk. The registry names an engine that has moved "
                            "or been renamed; a check that skips it is a check that stopped "
                            "looking." % (skill, script))
            continue
        source = open(path, encoding="utf-8").read()
        cmds = {c for c in commands_of(source) if c not in _NOT_USER_FACING}
        if not cmds:
            problems.append("%s/%s: parsed to ZERO commands. Either the engine changed idiom "
                            "or this parser stopped working — and a checker that tests nothing "
                            "reports success, which is the defect this file exists for."
                            % (skill, script))
            continue
        total_cmds += len(cmds)

        # (a) HELP. Only meaningful where the help text is hand-maintained prose.
        missing_help = set()
        if help_from == "docstring":
            doc = ast.get_docstring(ast.parse(source)) or ""
            if not doc.strip():
                problems.append("%s/%s: declared `docstring` help and has no module docstring, "
                                "so `--help` prints nothing." % (skill, script))
            missing_help = {c for c in cmds if not _mentions(doc, c)}
            if missing_help:
                problems.append(
                    "%s/%s: `--help` prints the module docstring and does not name %s. The "
                    "command exists and a user at the terminal cannot discover it."
                    % (skill, script, ", ".join(sorted(missing_help))))

        # (b) DOCS. Everywhere, because every engine has a SKILL.md.
        text = docs_text(repo, skill)
        if not text.strip():
            problems.append("%s: no SKILL.md or references/*.md read. The documentation half "
                            "of this check tested nothing." % skill)
            continue
        missing_docs = {c for c in cmds if not _mentions(text, c)}
        if missing_docs:
            problems.append(
                "%s: %s accepted by the engine and named in no shipped document — not "
                "SKILL.md, not references/*.md."
                % (skill, ", ".join(sorted(missing_docs))))
        rows.append((skill, script, len(cmds), help_from,
                     len(missing_help), len(missing_docs)))

    if not rows and not problems:
        problems.append("no engines were read at all; the registry or the tree has moved.")
    return problems, {"engines": len(rows), "commands": total_cmds}


def self_test() -> int:
    """Both directions, on synthetic engines — a guard never seen to fail is not known to work."""
    import shutil
    import tempfile

    results = []

    def case(label, cond):
        results.append((bool(cond), label))

    def tree(cmds, doc_cmds, skill_cmds, help_from="docstring", refs_cmds=()):
        root = tempfile.mkdtemp()
        d = os.path.join(root, "skills", "probe", "scripts")
        os.makedirs(d)
        body = ['"""probe engine.\n\nSubcommands:\n']
        body += ["  %s   does a thing\n" % c for c in doc_cmds]
        body += ['"""\n']
        if help_from == "docstring":
            body.append("COMMANDS = {%s}\n"
                        % ", ".join('"%s": None' % c for c in cmds))
        else:
            body.append("def build():\n")
            for c in cmds:
                body.append('    sub.add_parser("%s")\n' % c)
        open(os.path.join(d, "e.py"), "w", encoding="utf-8").write("".join(body))
        sk = os.path.join(root, "skills", "probe")
        open(os.path.join(sk, "SKILL.md"), "w", encoding="utf-8").write(
            "# probe\n" + "\n".join("`%s` does a thing" % c for c in skill_cmds) + "\n")
        if refs_cmds:
            os.makedirs(os.path.join(sk, "references"))
            open(os.path.join(sk, "references", "r.md"), "w", encoding="utf-8").write(
                "\n".join("`%s` in depth" % c for c in refs_cmds) + "\n")
        return root

    def probes(root, help_from="docstring"):
        return run(root, engines=(("probe", "e.py", help_from),))[0]

    r = tree(["add", "remove"], ["add", "remove"], ["add", "remove"])
    case("an engine whose commands appear in help and in SKILL.md passes", not probes(r))
    shutil.rmtree(r, ignore_errors=True)

    r = tree(["add", "remove"], ["add"], ["add", "remove"])
    p = probes(r)
    case("a command missing from the docstring fails, naming it",
         len(p) == 1 and "remove" in p[0] and "--help" in p[0])
    shutil.rmtree(r, ignore_errors=True)

    r = tree(["add", "remove"], ["add", "remove"], ["add"])
    p = probes(r)
    case("a command named in no document fails, naming it",
         len(p) == 1 and "remove" in p[0] and "no shipped document" in p[0])
    shutil.rmtree(r, ignore_errors=True)

    # Q1's decision, executed: references/ counts as documentation.
    r = tree(["add", "remove"], ["add", "remove"], ["add"], refs_cmds=["remove"])
    case("...and a command documented under references/ counts as documented",
         not probes(r))
    shutil.rmtree(r, ignore_errors=True)

    # The hyphen boundary. `add` must not launder `add-theme`, which is the shape every real
    # undocumented command in this repo had.
    r = tree(["add", "add-theme"], ["add"], ["add"])
    p = probes(r)
    case("`add` in the docs does not launder `add-theme`",
         len(p) == 2 and all("add-theme" in x for x in p))
    shutil.rmtree(r, ignore_errors=True)

    # argparse engines: help is generated, so (a) is not asserted — and saying so is the point.
    r = tree(["add", "remove"], ["add"], ["add", "remove"], help_from="argparse")
    case("an argparse engine is not judged on its docstring — its help cannot drift",
         not probes(r, help_from="argparse"))
    shutil.rmtree(r, ignore_errors=True)

    # ANTI-VACUITY, both ways.
    r = tree([], ["add"], ["add"])
    p = probes(r)
    case("an engine parsed to ZERO commands fails rather than passing vacuously",
         len(p) == 1 and "ZERO commands" in p[0])
    shutil.rmtree(r, ignore_errors=True)

    r = tree(["add"], ["add"], ["add"])
    os.remove(os.path.join(r, "skills", "probe", "scripts", "e.py"))
    p = probes(r)
    case("a registry entry naming an engine that is not on disk fails",
         len(p) == 1 and "not on disk" in p[0])
    shutil.rmtree(r, ignore_errors=True)

    r = tree(["add"], ["add"], ["add"])
    os.remove(os.path.join(r, "skills", "probe", "SKILL.md"))
    p = probes(r)
    case("an engine with no documentation at all fails rather than passing",
         len(p) == 1 and "tested nothing" in p[0])
    shutil.rmtree(r, ignore_errors=True)

    case("an empty registry fails — no engines read is not a clean run",
         run(_REPO, engines=())[0])

    for ok, label in results:
        print("  %-4s %s" % ("ok" if ok else "FAIL", label))
    bad = [r for r in results if not r[0]]
    print("\ncheck-commands self-test: %d/%d checks passed"
          % (len(results) - len(bad), len(results)))
    return 1 if bad else 0


def main(argv) -> int:
    if "--self-test" in argv:
        return self_test()
    repo = argv[1] if len(argv) > 1 else _REPO
    problems, counts = run(repo)
    if problems:
        print("ERROR: commands the docs do not name (CAC-CD-1):")
        for p in problems:
            print("  " + p)
        print("       Every command an engine accepts is a command a reader must be able to "
              "find. Document it, or remove it.")
        return 1
    print("check-commands (CAC-CD-1): %d engine(s), %d command(s), each named in the help "
          "surface and in a shipped document." % (counts["engines"], counts["commands"]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
