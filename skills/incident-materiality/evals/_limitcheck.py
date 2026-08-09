#!/usr/bin/env python3
"""Does every regulatory limit in the shipped prose run in BOTH directions?

Usage:  _limitcheck.py <repo-root> inward-stated|no-borrowed-limit|count

`inward-stated`     each (file, regime) pair carries the inward limit that was READ against a
                    primary source. Outward-only is the BL-188 defect.
`no-borrowed-limit` a file naming DORA Art. 16 next to incident reporting must state what
                    Art. 16 actually disapplies, so nobody re-derives the wrong exemption.
`count`             how many (file, regime) pairs were checked (GP-1.7).

Prints `clean <n>` or one line per problem.

WHY A TABLE AND NOT A PATTERN. "Does this regulation exempt anyone inside the perimeter it
names?" cannot be answered by a regex — it is answered by reading the regulation. So this file
is a REGISTRY OF ANSWERS, each entry standing for a primary-source read that happened, and the
check is only that the shipped prose still carries it. Adding a regime here without doing the
read would make the guard a green light over a guess, which is the failure it exists to stop.
"""
import os
import sys

# (path, regime, tokens that must all be present, what the read established)
#
# Every entry below was read against the primary text on 2026-08-09 — DORA from the EUR-Lex
# text of Regulation (EU) 2022/2554, Item 106 from 17 CFR 229.106 on eCFR, Item 1.05 from the
# SEC release already declared in this skill's sources.json.
INWARD = (
    ("skills/incident-materiality/references/materiality-factors.md", "DORA reporting",
     ("Art. 2(3)",),
     "Art. 2(3) excludes six categories from inside the financial-entity list, and Art. 2(4) "
     "lets a Member State exclude more."),
    ("skills/incident-materiality/references/materiality-factors.md", "SEC Item 106",
     ("Instruction 1 to Item 106(c)",),
     "17 CFR 229.106 carries no exemption; the only inward variation is the two-tier-board "
     "accommodation for a foreign private issuer, which relieves nobody of the disclosure."),
    ("skills/incident-materiality/references/materiality-factors.md", "SEC Item 1.05",
     ("Item 1.05(c)", "secItem105Scope"),
     "Registrant status is declared, never inferred; 1.05(c) and 1.05(d) are delay mechanisms "
     "the engine does not model."),
    ("skills/incident-materiality/SKILL.md", "SEC Item 1.05 and DORA",
     ("secItem105Scope", "Art. 2(3)"),
     "The skill's own scope section points at both inward limits rather than only outward."),
    ("skills/incident-materiality/references/disclosure-clocks.md", "SEC Item 1.05",
     ("Item 1.05(c)", "Item 1.05(d)"),
     "Both delay mechanisms are named, with the engine's statement that it models neither."),
    ("skills/ciso-board-translation/references/regulatory-receipts.md", "SEC Item 106",
     ("Instruction 1 to Item 106(c)",),
     "Same read as above, on the board-facing receipt."),
)

# The near-miss this guard exists to freeze. DORA's Art. 16 simplified framework disapplies
# "Articles 5 to 15" and NOTHING ELSE; incident reporting is Chapter III, Arts. 17-23, with
# major-incident reporting at Art. 19. The Art. 16 limit is correctly attached to the
# residual-risk inventory receipts, which cite RTS 2024/1774 — and carrying it across to the
# reporting receipts because the wording matches would invent an exemption in a disclosure
# record. It was one line from happening; this is what stops it happening later.
ART16_FILES = (
    "skills/incident-materiality/references/materiality-factors.md",
    "skills/incident-materiality/SKILL.md",
)
ART16_MENTION = ("Art. 16", "Article 16")
ART16_CORRECTION = "Articles 5 to 15"


def _read(root, rel):
    """Whitespace collapsed — every needle is a phrase and this is hard-wrapped Markdown."""
    path = os.path.join(root, rel)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as fh:
        return " ".join(fh.read().split())


def main(argv):
    if len(argv) != 3:
        print(__doc__.strip())
        return 2
    root, mode = argv[1], argv[2]
    problems = []

    if mode == "count":
        seen = sum(1 for rel, _r, _t, _w in INWARD if _read(root, rel) is not None)
        print(seen)
        return 0

    if mode == "inward-stated":
        for rel, regime, tokens, established in INWARD:
            body = _read(root, rel)
            if body is None:
                problems.append("%s: missing — the check read nothing, so a clean result would "
                                "mean the file was renamed rather than the limit held" % rel)
                continue
            missing = [t for t in tokens if t not in body]
            if missing:
                problems.append(
                    "%s (%s): states the perimeter and not who is excluded from inside it. "
                    "Missing %s. What the primary-source read established: %s"
                    % (rel, regime, ", ".join(repr(m) for m in missing), established))
        counted = len(INWARD)
    elif mode == "no-borrowed-limit":
        checked = 0
        for rel in ART16_FILES:
            body = _read(root, rel)
            if body is None:
                problems.append("%s: missing — cannot check the Art. 16 correction" % rel)
                continue
            if not any(m in body for m in ART16_MENTION):
                continue
            checked += 1
            if ART16_CORRECTION not in body:
                problems.append(
                    "%s: names DORA Art. 16 beside incident reporting without saying what it "
                    "actually disapplies. Art. 16 reaches %r and nothing else; reporting is "
                    "Chapter III (Arts. 17-23), with major-incident reporting at Art. 19. The "
                    "Art. 16 limit belongs to the residual-risk receipts under RTS 2024/1774, "
                    "and reading it across because the wording matches would invent an "
                    "exemption in a disclosure record." % (rel, ART16_CORRECTION))
        if not checked and not problems:
            problems.append(
                "no file names DORA Art. 16 at all, so this half asserted nothing. The "
                "correction was written precisely because the wrong reading is one line away; "
                "if the mention is gone, so is the warning.")
        counted = checked
    else:
        print("unknown mode %r" % mode)
        return 2

    if problems:
        print("\n".join(problems))
        return 1
    print("clean %d" % counted)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
