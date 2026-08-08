"""No regulatory date lives in prose, and no regime obligation is unattributable.

Two halves, and they guard the same failure from opposite ends.

  --static DIR   No shipped .py puts a year inside a sentence about a regulation. Dates rot,
                 prose does not get re-read, and a stale date inside a refusal message is a
                 wrong statement of law delivered at the exact moment somebody is trying to
                 do the right thing.

  --data FILE    Every obligation in the dataset carries a source and an owning function, and
                 the dataset carries an `asOf`. A dataset with no date is a claim about an
                 unknown version of every text in it.

The static half is DELIBERATELY NARROW, and the narrowing is the interesting part. Every
shipped script here is full of four-digit years — self-test fixtures, example dates, period
ends — and banning those would mean banning test data. What is banned is a year in a string
that is ALSO talking about a regulation: an effective date, a compliance deadline, an
"applies from". That is the claim that rots.

Usage: _regimescan.py --static <skill-dir>
       _regimescan.py --data <regimes.json>
Prints `scanned N` / `checked N` so a run that read nothing cannot pass in silence.
"""

from __future__ import annotations

import ast
import json
import pathlib
import re
import sys

YEAR = re.compile(r"\b(19|20)\d{2}\b")

# Vocabulary that makes a sentence a statement about law rather than about a store. Named
# regimes are included because "the AI Act" plus a year is the exact shape being banned, and
# generic words like `article` catch the ones nobody has heard of yet.
#
# **The first version chased verbs, and verbs leak.** It matched `applies from` and missed
# `apply from` — one letter of subject-verb agreement — and missed `take effect on` and `begin`
# entirely. An audit found all three with phrasings a well-meaning author would actually write.
# Chasing verb forms is unwinnable: there is always another way to say "starts".
#
# So the list leads with NOUNS. What makes a sentence a claim about law is that it is about an
# obligation, a duty, a requirement, a deadline — and those words do not conjugate. The verb
# patterns are kept, with agreement variants, because they catch sentences whose noun is only
# implied ("this comes into force in 2027").
REGULATORY = re.compile(
    # named regimes and citation shapes
    r"regulation|directive|statute|article\s+\d|section\s+\d|§|"
    r"\bAI Act\b|\bDORA\b|\bNYDFS\b|\bGDPR\b|\bSEC\b|\bSB[- ]?\d|\bHB[- ]?\d|"
    # the nouns — a sentence carrying one of these and a year is making a claim about law
    r"\bobligation|\bdut(?:y|ies)\b|\brequirement|\bdeadline\b|\bgrace period\b|"
    r"\benforcement\b|\bin scope\b|\bnon-compliance\b|\bpenalt(?:y|ies)\b|"
    # the verbs, with agreement variants, for sentences whose noun is only implied
    r"appl(?:y|ies|ied|icable)\s+from|"
    r"take[s]?\s+effect|took\s+effect|"
    r"come[s]?\s+into\s+(?:force|effect)|came\s+into\s+(?:force|effect)|"
    r"enter[s]?\s+into\s+(?:force|effect)|entered\s+into\s+(?:force|effect)|"
    r"begin[s]?\s+(?:on\s+)?\d|began\s+(?:on\s+)?\d|"
    r"effective from|compliance deadline|transition period",
    re.I)


def _strings(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            yield node.lineno, node.value


def static(root):
    root = pathlib.Path(root)
    files = [p for p in sorted(root.glob("scripts/*.py")) + sorted(root.glob("renderers/*.py"))
             if p.name not in ("cac_graphics.py", "_common.py")]
    if not files:
        print("scanned 0", flush=True)
        print("no shipped .py was scanned — the glob stopped matching, so this guard "
              "proved nothing", file=sys.stderr)
        return 2
    problems = []
    for path in files:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for lineno, text in _strings(tree):
            if REGULATORY.search(text) and YEAR.search(text):
                problems.append("%s line %d: a regulatory sentence carrying a year — %r"
                                % (path.name, lineno, text.strip()[:120]))
    print("scanned %d" % len(files), flush=True)
    if problems:
        print("\n".join(problems), file=sys.stderr)
        print("\nRegulatory dates belong in references/regimes.json, behind an `asOf`, "
              "where a reader can see how old they are.", file=sys.stderr)
        return 1
    return 0


def data(path):
    payload = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    problems = []
    if not str(payload.get("asOf") or "").strip():
        problems.append("the dataset has no `asOf`")
    checked = 0
    for regime in (payload.get("regimes") or []):
        rid = regime.get("id") or "?"
        if regime.get("aiRole") not in ("deployer", "provider"):
            problems.append("%s: aiRole is %r, not deployer or provider"
                            % (rid, regime.get("aiRole")))
        if not str(regime.get("flag") or "").strip():
            problems.append("%s: no flag selects it" % rid)
        for ob in (regime.get("obligations") or []):
            checked += 1
            oid = ob.get("id") or "?"
            if not str(ob.get("source") or "").strip():
                problems.append("%s/%s: no source" % (rid, oid))
            if not str(ob.get("owningFunction") or "").strip():
                problems.append("%s/%s: no owningFunction" % (rid, oid))
    print("checked %d obligation(s) across %d regime(s)"
          % (checked, len(payload.get("regimes") or [])), flush=True)
    if problems:
        print("\n".join(problems), file=sys.stderr)
        return 1
    return 0


# The guard's own mutation set: sentences a well-meaning author would actually write.
#
# The first three were caught by the original vocabulary. The last three were NOT — an audit
# found them, and each is one small step from a phrase that was caught: subject-verb agreement,
# a different verb for "starts", and a verb with no preposition at all. They are registered here
# so the leak cannot reopen: widening the list is easy, and narrowing it again by accident while
# tidying a regex is easier.
#
# The negative cases matter as much. This guard is deliberately narrow — every script in this
# suite is full of dates in fixtures — so a phrasing that is about a STORE rather than about law
# must keep passing, or the guard gets switched off for noise.
VOCAB_PROBE = [
    ("This regulation applies from 2 December 2027.", True),
    ("The AI Act high-risk deadline moved to December 2027.", True),
    ("Regulation (EU) 2026/1744 postponed this to 2027.", True),
    # The three the original vocabulary missed.
    ("These obligations apply from 2 December 2027.", True),
    ("These duties take effect on 1 January 2027.", True),
    ("Deployer obligations begin 2 December 2027.", True),
    # Must NOT fire: dates that are about this register, not about law.
    ("period_end 2026-12-31", False),
    ("the assessment on 2026-04-10 was made against GPT-cx-2", False),
    ("the report covers 2026-01-01 to 2026-06-30 and excludes tool calling", False),
    ("cadence for high is 365 days; last assessed 2025-06-30", False),
]


def vocab_probe():
    """Assert the vocabulary against phrasings it must and must not catch."""
    problems = []
    for text, should_fire in VOCAB_PROBE:
        fired = bool(REGULATORY.search(text) and YEAR.search(text))
        if fired != should_fire:
            problems.append("%s: %r" % ("missed" if should_fire else "false positive on", text))
    print("probed %d phrasing(s): %d must fire, %d must not"
          % (len(VOCAB_PROBE), sum(1 for _, f in VOCAB_PROBE if f),
             sum(1 for _, f in VOCAB_PROBE if not f)), flush=True)
    if problems:
        print("\n".join(problems), file=sys.stderr)
        return 1
    return 0


def main(argv):
    if len(argv) == 2 and argv[1] == "--vocab-probe":
        return vocab_probe()
    if len(argv) != 3 or argv[1] not in ("--static", "--data"):
        print(__doc__, file=sys.stderr)
        return 2
    return static(argv[2]) if argv[1] == "--static" else data(argv[2])


if __name__ == "__main__":
    sys.exit(main(sys.argv))
