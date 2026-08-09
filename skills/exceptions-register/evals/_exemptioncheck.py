#!/usr/bin/env python3
"""Do the shipped NYDFS locations state the §500.19 exemptions, and refuse to compute them?

Usage:  _exemptioncheck.py <repo-root> stated|not-computed|count

`stated`        each location names §500.19 AND distinguishes the limbs that matter.
`not-computed`  wherever a qualification threshold appears, so does the sentence saying
                qualifying is a legal determination.
`count`         how many of the listed locations were opened and read (GP-1.7).

Prints `clean <n>` or one line per problem.

The file list is EXPLICIT rather than globbed. A glob would quietly shrink to whatever still
matched after a rename, and a checker that finds nothing to check reports success forever.
"""
import os
import sys

# The three locations BL-188 identified, each of which states a NYDFS obligation to a reader.
LOCATIONS = (
    "skills/exceptions-register/references/exceptions.md",
    "skills/exceptions-register/SKILL.md",
    "skills/ciso-board-translation/references/regulatory-receipts.md",
)

# The limbs a receipt has to distinguish, because they reach different sections. Naming
# "§500.19" alone is not enough: (a) exempts from 500.15 and NOT from 500.12, while (c) and
# (d) exempt from both. A reader given the bare section number cannot tell which applies to
# them, and the difference is whether MFA binds.
LIMBS = ("500.19(a)", "500.19(c)")

# The asymmetry itself, in whatever words the location uses. Both section numbers must appear
# near the exemption, or the receipt states that an exemption exists without saying what it
# reaches — which is the same missing fact one level up.
SECTIONS = ("500.12", "500.15")

# Figures that look like arithmetic and are not. Any location printing one must also carry
# the sentence that stops a reader self-assessing off it.
THRESHOLDS = ("$7,500,000", "$15,000,000", "20 employees")

# The caveat, in any of the forms the three locations write it.
CAVEATS = ("legal determination", "determination this suite does not make",
           "legal determinations")


def _read(root, rel):
    """The file with its whitespace runs collapsed to single spaces.

    Every needle below is a PHRASE, and these are hard-wrapped Markdown: `legal\ndeterminations`
    is the same sentence as `legal determinations` and a raw substring search sees neither. The
    first version of this checker missed the caveat in the board receipt for exactly that
    reason and reported the file as uncaveated — a red on a property that held, which is the
    same class of wrongness as a green on one that did not.
    """
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

    texts, problems = {}, []
    for rel in LOCATIONS:
        body = _read(root, rel)
        if body is None:
            problems.append("%s: missing — the check read nothing, so a clean result here "
                            "would mean the file was renamed rather than the property held"
                            % rel)
            continue
        texts[rel] = body

    if mode == "count":
        print(len(texts))
        return 0

    if mode == "stated":
        for rel, body in sorted(texts.items()):
            if "500.19" not in body:
                problems.append(
                    "%s: states a NYDFS obligation and never names §500.19. Every limit in "
                    "this file scopes OUTWARD — who the rule does not reach — and says "
                    "nothing about which covered entities inside the perimeter are exempt, "
                    "so an exempt firm reads a lawful gap as non-compliance (BL-188)." % rel)
                continue
            missing = [x for x in LIMBS if x not in body]
            if missing:
                problems.append(
                    "%s: names §500.19 but not %s. The limbs are not interchangeable — (a) "
                    "exempts from §500.15 and NOT from §500.12, (c) and (d) exempt from "
                    "both — and a reader given the bare section number cannot tell which "
                    "applies to them." % (rel, ", ".join(missing)))
            if not all(x in body for x in SECTIONS):
                problems.append(
                    "%s: names §500.19 without naming both §500.12 and §500.15, so it says "
                    "an exemption exists without saying what it reaches." % rel)
        counted = len(texts)
    elif mode == "not-computed":
        for rel, body in sorted(texts.items()):
            hits = [t for t in THRESHOLDS if t in body]
            if not hits:
                continue
            if not any(c in body for c in CAVEATS):
                problems.append(
                    "%s: prints the qualification threshold(s) %s with no sentence saying "
                    "qualifying is a legal determination. The tests read like arithmetic and "
                    "are not — affiliate aggregation, operating under a license, and whether "
                    "an entity otherwise qualifies as a covered entity are counsel's calls. "
                    "A file that prints the numbers and drops the caveat invites the reader "
                    "to self-assess." % (rel, ", ".join(hits)))
        counted = len(texts)
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
