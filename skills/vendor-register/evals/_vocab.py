"""Board-safety vocabulary checks for the vendor-register views.

Three lists, each banning something different, and each deliberately narrow — a list that
bans the subject matter is a list somebody turns off.

`confidence` — words that make a claim about our own certainty. This register records what was
checked and when; it does not know how confident anyone should be, and printing "degrading" or
"unreliable" beside a dependency invents a judgement nobody made.

`catastrophizing` — "existential", "crippling". Deliberately NOT "critical", "severe" or
"high": those are the classification vocabulary the frameworks themselves use, and this skill's
own top criticality level is usually spelled with one of them.

`scoring` — the one this skill needs that its siblings do not. A page that says a provider is
"graded" or prints a "scorecard" has delivered the number the whole design refuses, whether or
not any code computed one.

Two things this list learned the hard way, on its first run:

- **Word boundaries are not optional.** `rated` matches inside *gene*`rated`, so a bare
  substring list flagged the footer of every page it was meant to protect.
- **"vendor score" has to be allowed when it is being DENIED.** The pages are required
  elsewhere in this suite to say they produce none, so banning the phrase outright put two
  checks in direct contradiction. It is flagged only when it is not negated.

`tiers` is allowed throughout: evidence tiers rank evidence rigour, not vendors.

Usage: _vocab.py <html-or-py> <confidence|catastrophizing|scoring> [--source]
Prints the offending terms, comma-separated, or nothing. `--source` strips docstrings first:
the refusal has to be explainable, and every file here carries a paragraph naming the claim it
declines to make.
"""

from __future__ import annotations

import ast
import re
import sys

LISTS = {
    "confidence": (r"\bconfidence\b", r"\bdegrading\b", r"\bdegraded\b", r"\bdecaying\b",
                   r"\bno longer reliable\b", r"\bless reliable\b", r"\bunreliable\b",
                   r"\btrustworthy\b"),
    "catastrophizing": (r"catastroph", r"devastat", r"existential", r"crippl", r"disastrous",
                        r"nightmare", r"ruinous", r"calamit", r"apocalyp", r"bet-the-company",
                        r"reputational ruin", r"could destroy", r"wiped out"),
    # Regexes, not substrings, and every one anchored on a word boundary.
    "scoring": (r"\bscorecard\b", r"\brisk score\b", r"\boverall score\b",
                r"\bcomposite score\b", r"\bgraded\b", r"\brating\b",
                r"\bwe rate\b", r"\bvendor grade\b"),
}


def _strip_docstrings(source: str) -> str:
    """Blank everything that explains or asserts the refusal, leaving code that can reach a page.

    Three populations come out, and each is here for a stated reason.

    **Docstrings.** The refusal has to be explainable, and every file in this suite carries a
    paragraph naming the claim it declines to make. A scan that banned the words there would
    ban the explanation.

    **Comments.** The same argument, applied to the paragraph above a function.

    **Any function whose name contains `self_test`.** An assertion that a word is ABSENT has
    to name the word. `no key or value describes a class as mitigated, resolved, closed or
    accepted` is a self-test's own failure message, and flagging it means the check that
    forbids the vocabulary and the check that proves the forbidding works are in direct
    contradiction — which is how a guard gets switched off rather than fixed. Exempted by line
    span rather than by pattern, and `nist-csf/evals/board-safety.sh` has done it this way
    since BL-211; this is that pattern reaching the two suites BL-211 scoped out (BL-221).
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return source
    spans = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            doc = ast.get_docstring(node, clean=False)
            if doc and node.body and isinstance(node.body[0], ast.Expr):
                spans.append((node.body[0].lineno, node.body[0].end_lineno))
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and "self_test" in node.name:
            spans.append((node.lineno, node.end_lineno))
    lines = source.split("\n")
    for start, end in spans:
        for i in range(start - 1, min(end, len(lines))):
            lines[i] = ""
    # Comments too: the same argument applies to a paragraph above a function.
    return "\n".join("" if ln.lstrip().startswith("#") else ln for ln in lines)



# vendor-register's `scoring` list has no phrase this suite is REQUIRED to print in denial, so
# there is nothing to negate here. Declared empty rather than omitted: the tree scan reads it,
# and a missing name would read as an oversight rather than as a stated absence.
NEGATABLE = {}
_NEGATION = re.compile(r"\b(no|not|never|without|refuses|declines|cannot|neither|"
                       r"rather than|instead of)\b[^.]*$")


# --- GP-1.7: the file list is RECOMPUTED, and it reaches `scripts/` -------------------------
#
# Until BL-221 this suite scanned `renderers/render_*.py` and `renderers/_common.py` through a
# shell glob — every renderer and NO engine script. `scripts/vendor_register.py` (2800+ lines) is the file that writes most
# of the strings the renderers print, and this suite had never read one line of it. A glob is
# better than the hardcoded tuple BL-211 found elsewhere (it catches a new renderer) and it is
# still not GP-1.7: a renderer not named `render_*.py` joins neither population, and the whole
# `scripts/` half was unreachable.
#
# The list is derived from the tree on every run. An exclusion must state its reason, and one
# that outlives its file FAILS — an exclusion nobody can find is a scan that quietly narrowed.

EXCLUDE = {
    "renderers/cac_graphics.py":
        "vendored byte-identical from tools/cac_graphics.py and scanned there. "
        "tools/check-versions.py fails if this copy drifts, so reading it here would "
        "duplicate a guard rather than add one.",
}

# --- Hits that ship, are not defects, and whose DISPOSITION IS NOT YET DECIDED --------------
#
# BL-221 D-3. Widening the scan to `scripts/` surfaces three string literals that are real,
# that reach no page as a claim about us, and that fall into two populations:
#
#   describing-an-attack  — "an attacker degrading the service" is a statement about what an
#                           adversary does, not about our certainty. The `confidence` list
#                           exists to stop the SECOND sense and cannot tell them apart.
#   forbidding-a-key      — `FINDING_SCORING_KEYS` contains "rating" because the engine
#                           REFUSES a finding carrying it. The word is present in order to be
#                           banned, which is this file's own stated principle one level up.
#
# The item names three candidate dispositions — narrow the stems, move the attack-class text
# into a data file the scan does not read, or accept them under a named exclusion — and says
# to RAISE it rather than improvise one. So these are not excluded and not suppressed: they
# are ALLOWED-AND-ANNOUNCED. Every run prints them, and the entry must still match a real hit
# or the run fails, so this cannot decay into a silent exemption. Filed in Open Decisions.
UNDECIDED = {
    ("scripts/vendor_register.py", "scoring", r"\brating\b"):
        "FINDING_SCORING_KEYS — the tuple of keys export-findings REFUSES to carry. The word "
        "is present in order to be banned, which is the forbidding-a-key population.",
}


def _shipped_strings(path):
    """(lineno, text) for every string literal that is neither prose nor a self-test."""
    src = open(path, encoding="utf-8").read()
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return []
    docs, exempt = set(), []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            doc = ast.get_docstring(node, clean=False)
            if doc is not None:
                docs.add(doc)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and "self_test" in node.name:
            exempt.append((node.lineno, node.end_lineno))
    out = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
            continue
        if node.value in docs:
            continue
        if any(lo <= node.lineno <= hi for lo, hi in exempt):
            continue
        out.append((node.lineno, node.value))
    return out


def tree_scan(root):
    """Scan every shipped .py under scripts/ and renderers/. Returns lines to print."""
    import os
    disk = []
    for d in ("scripts", "renderers"):
        full = os.path.join(root, d)
        if not os.path.isdir(full):
            continue
        for name in sorted(os.listdir(full)):
            if name.endswith(".py"):
                disk.append("%s/%s" % (d, name))
    disk.sort()
    out = []
    for rel in sorted(EXCLUDE):
        if rel not in disk:
            out.append("LIST: EXCLUDE names %s, which is not on disk — an exclusion that "
                       "outlived its file silently narrows the scan" % rel)
    files = [rel for rel in disk if rel not in EXCLUDE]
    if not files:
        out.append("LIST: nothing to scan — the walk is broken, not the source clean")
    seen = set()
    scanned = 0
    for rel in files:
        scanned += 1
        for lineno, value in _shipped_strings(os.path.join(root, rel)):
            low = value.lower()
            for which, pats in LISTS.items():
                negatable = set(NEGATABLE.get(which, ()))
                for pat in pats:
                    for match in re.finditer(pat, low):
                        if pat in negatable and _NEGATION.search(low[:match.start()]):
                            continue
                        key = (rel, which, pat)
                        if key in UNDECIDED:
                            seen.add(key)
                            out.append("UNDECIDED: %s:%d [%s] %s — %s"
                                       % (rel, lineno, which, pat.replace(r"\b", ""),
                                          UNDECIDED[key]))
                        else:
                            out.append("SCAN: %s:%d [%s] %r in %r"
                                       % (rel, lineno, which, pat.replace(r"\b", ""),
                                          value[:70]))
                        break
    if scanned != len(files):
        out.append("LIST: scanned %d of %d files" % (scanned, len(files)))
    for key in sorted(UNDECIDED):
        if key not in seen:
            out.append("UNDECIDED-ORPHAN: %s no longer occurs. The disposition was settled "
                       "in code and this entry was not removed with it." % (key,))
    out.append("SCANNED: %d" % scanned)
    # Printed so the SUITE can assert the population rather than trust the count.
    # `scanned == len(files)` is true of any list, including one with no engine in
    # it — which is exactly the state BL-221 was raised about.
    out.append("POPULATION: %s" % ",".join(files))
    return out


def main(argv):
    if "--tree" in argv:
        # argv[1] is the SKILL ROOT, not a file. Prints one line per finding plus a
        # SCANNED count; the suite reads the prefixes.
        for line in tree_scan(argv[1]):
            print(line)
        return 0
    text = open(argv[1], encoding="utf-8").read()
    if "--source" in argv:
        text = _strip_docstrings(text)
    else:
        text = re.sub(r"<[^>]+>", " ", text)
    text = text.lower()
    hits = [pat for pat in LISTS[argv[2]] if re.search(pat, text)]
    if argv[2] == "scoring":
        # "vendor score" is a violation when CLAIMED and required when DENIED. Every
        # occurrence must be negated; one that is not is the real thing.
        for match in re.finditer(r"\bvendor score\b", text):
            before = text[max(0, match.start() - 24):match.start()]
            if not re.search(r"\b(no|not|never|without|refuses|produces no)\b[^.]*$", before):
                hits.append("vendor score (claimed, not denied)")
                break
    print(",".join(hits))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
