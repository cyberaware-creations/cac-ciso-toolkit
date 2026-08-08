"""Board-safety vocabulary checks for the ai-register views.

Four lists, each banning something different, and each deliberately narrow — a list that bans
the subject matter is a list somebody turns off.

`confidence` — words that make a claim about our own certainty. This register records what was
checked and when; it does not know how confident anyone should be, and printing "degrading" or
"unreliable" beside a deployment invents a judgement nobody made.

`catastrophizing` — "existential", "crippling". Deliberately NOT "critical", "severe" or
"high": those are the classification vocabulary the frameworks themselves use, and this skill's
own top criticality level is usually spelled with one of them.

`scoring` — a page that says a deployment is "graded" or prints a "posture score" has
delivered the number the whole design refuses, whether or not any code computed one.

`closure` — THE list this skill needs that no sibling does. An attack class has no closed
state, and the page is what people actually read: "mitigated", "remediated", "resolved",
"fully covered", "addressed" are all claims the store refuses to hold and the page must
therefore refuse to make. `no-closed-state.sh` proves nothing STORES one; this proves nothing
SAYS one.

Three things these lists learned from the sibling that shipped first:

- **Word boundaries are not optional.** `rated` matches inside *gene*`rated`, so a bare
  substring list flagged the footer of every page it was meant to protect.
- **A banned phrase has to be allowed when it is being DENIED.** These pages are required
  elsewhere in this suite to say they produce no score and close no class, so banning the
  words outright would put two checks in direct contradiction. Both are flagged only when not
  negated.
- **The stripper is tested on a purpose-built probe**, not on a shipped file whose docstring
  happens to contain a banned word.

`tiers` is allowed throughout: evidence tiers rank evidence rigour, not deployments.

Usage: _vocab.py <html-or-py> <confidence|catastrophizing|scoring|closure> [--source]
Prints the offending terms, comma-separated, or nothing. `--source` strips docstrings and
comments first: the refusal has to be explainable, and every file here carries a paragraph
naming the claim it declines to make.
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
    "scoring": (r"\bscorecard\b", r"\brisk score\b", r"\boverall score\b",
                r"\bcomposite score\b", r"\bmaturity score\b", r"\bgraded\b", r"\brating\b",
                r"\bwe rate\b", r"\bai grade\b", r"\breadiness score\b"),
    # Every one of these describes an attack class as finished. None of them is a word this
    # register is entitled to about a class, and several are words a well-meaning renderer
    # would reach for first.
    "closure": (r"\bfully mitigated\b", r"\bmitigated\b", r"\bremediated\b", r"\bresolved\b",
                r"\bfully covered\b", r"\bfully addressed\b", r"\bclass closed\b",
                r"\brisk eliminated\b", r"\bno longer exposed\b", r"\bthreat removed\b",
                r"\bprotected against\b", r"\bsecured against\b"),
}

# The two lists whose words are REQUIRED elsewhere on the page when denied. A caveat block
# that says "never as resolved" or "produces no AI risk score" is the page doing its job.
NEGATABLE = {
    "closure": (r"\bmitigated\b", r"\bremediated\b", r"\bresolved\b"),
    # `risk score` joins these because the caveat block on every page is REQUIRED to say the
    # register produces none. Banning it outright would put two checks in this suite in direct
    # contradiction, which is how a guard gets switched off rather than fixed.
    "scoring": (r"\brating\b", r"\brisk score\b"),
}
_NEGATION = re.compile(r"\b(no|not|never|without|refuses|declines|cannot|neither|"
                       r"rather than|instead of)\b[^.]*$")


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
    which = argv[2]
    negatable = set(NEGATABLE.get(which, ()))
    hits = []
    for pat in LISTS[which]:
        for match in re.finditer(pat, text):
            if pat in negatable:
                before = text[max(0, match.start() - 40):match.start()]
                if _NEGATION.search(before):
                    continue
            hits.append(pat.replace(r"\b", ""))
            break
    print(",".join(hits))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
