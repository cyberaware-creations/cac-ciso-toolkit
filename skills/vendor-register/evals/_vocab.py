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
    """Remove every docstring, so a file may explain the claim it refuses to make."""
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
    lines = source.split("\n")
    for start, end in spans:
        for i in range(start - 1, min(end, len(lines))):
            lines[i] = ""
    # Comments too: the same argument applies to a paragraph above a function.
    return "\n".join("" if ln.lstrip().startswith("#") else ln for ln in lines)


def main(argv):
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
