"""Every shipped question asks for evidence with a date, never an attestation.

The shape of the question is the product. "Do you test for prompt injection?" is worthless:
everybody answers yes, and the answer is unfalsifiable. "What is the most recent dated
adversarial test of THIS deployment, and what did it find?" has a discoverable answer, a date,
and degrades honestly when the answer is "none".

Two conditions, both required of every question:

  BANNED   an attestation opener — "do you", "are you", "is there", "have you", "can you
           confirm", "does the provider". These invite yes, and yes is not evidence.
  REQUIRED an evidentiary noun — evidence, record, document, report, commitment, configuration
           — AND a temporal anchor: "dated", "most recent", "when", "last", "how long".

The temporal half matters as much as the noun. "What evidence shows X" without a date produces
an artifact of unknown age, and an artifact of unknown age is indistinguishable from a current
one on the page that reports it.

`--mutant` runs the same check against a deliberately bad battery, so the scanner is proved to
fail before it is trusted to pass.

Usage: _questionscan.py <ai_register.py> [--mutant]
"""

from __future__ import annotations

import importlib.util
import re
import sys

BANNED = (
    r"^\s*do you\b", r"^\s*are you\b", r"^\s*is there\b", r"^\s*have you\b",
    r"^\s*does the\b", r"^\s*can you confirm\b", r"^\s*will you\b", r"^\s*would you\b",
    r"\bconfirm that\b", r"\bdo you have a policy\b", r"\bis .{0,30}in place\?",
)
EVIDENTIARY = re.compile(
    r"\bevidence\b|\brecord\b|\bdocument(?:ation)?\b|\breport\b|\bcommitment\b|"
    r"\bconfiguration\b|\bexport\b|\bagreement\b|\bcard\b|\btest\b|\bassurance\b", re.I)
TEMPORAL = re.compile(
    r"\bdated\b|\bmost recent\b|\bwhen\b|\blast\b|\bhow long\b|\bperiod\b|\bbefore\b|"
    r"\bsince\b|\bcurrent\b", re.I)

MUTANT = {
    "id": "planted",
    "gvsc": ["ID.RA-01"],
    "nistaml": ["02"],
    "appliesWhen": {},
    "questions": ({"id": "attestation", "ask": "Do you test for prompt injection?"},),
}


def check(batteries):
    problems = []
    total = 0
    for battery in batteries:
        for q in battery["questions"]:
            total += 1
            key = "%s.%s" % (battery["id"], q["id"])
            ask = q["ask"]
            for pat in BANNED:
                if re.search(pat, ask, re.I):
                    problems.append("%s is an attestation (%s): %r"
                                    % (key, pat.strip("^\\s*"), ask))
                    break
            if not ask.rstrip().endswith("?"):
                problems.append("%s does not end in a question mark: %r" % (key, ask))
            if not EVIDENTIARY.search(ask):
                problems.append("%s asks for no evidentiary artifact: %r" % (key, ask))
            if not TEMPORAL.search(ask):
                problems.append("%s asks for no date or recency: %r" % (key, ask))
    return total, problems


def main(argv):
    if len(argv) < 2:
        print(__doc__, file=sys.stderr)
        return 2
    spec = importlib.util.spec_from_file_location("ar", argv[1])
    ar = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ar)
    batteries = list(ar.BATTERIES) + ([MUTANT] if "--mutant" in argv else [])
    total, problems = check(batteries)
    if not total:
        print("no questions were inspected — BATTERIES is empty, so this proved nothing",
              file=sys.stderr)
        return 2
    print("inspected %d question(s) across %d batteries" % (total, len(batteries)), flush=True)
    if problems:
        print("\n".join(problems), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
