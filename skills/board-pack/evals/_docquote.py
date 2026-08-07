"""Hold SKILL.md's quoted provenance sentence to the one the assembler actually emits.

SKILL.md is operational guidance a model reads instead of the implementation, so a stale
paragraph there is not a typo — it is an instruction to believe something untrue. This one
went stale exactly as designed-for: the doc said the profile narrowed `incident-materiality`
alone and quoted the note that named the other four as not reading one, which stopped being
true the moment they did. Four releases and an external retest later it still said so.

The fix is not a better memory. This check extracts the blockquote from SKILL.md and compares
it, whitespace-normalised, against the note a real assembly puts on the provenance page. It
pins no phrase of its own: when the sentence changes because a producer implemented the
contract, the check fails until the doc is brought along.

Usage: _docquote.py SKILL.md pack.json
Exit 0 on agreement; 1 with both strings on stderr otherwise.
"""

from __future__ import annotations

import json
import re
import sys

MARKER = "applicability profile narrowed"


def doc_quote(path):
    """The blockquote in SKILL.md that quotes the provenance note, normalised."""
    lines = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            if line.startswith(">"):
                lines.append(line.lstrip(">").strip())
            elif lines:
                if any(MARKER in ln for ln in lines):
                    break
                lines = []
    text = " ".join(lines).strip().strip("*")
    return re.sub(r"\s+", " ", text)


def emitted_note(path):
    """The note a real assembly wrote to the provenance page, normalised."""
    notes = json.load(open(path, encoding="utf-8"))["provenance"]["missing"]
    note = next((n for n in notes if MARKER in n), "")
    return re.sub(r"\s+", " ", note.strip())


def main(argv):
    quoted, actual = doc_quote(argv[1]), emitted_note(argv[2])
    if not actual:
        print("no provenance note was emitted at all", file=sys.stderr)
        return 1
    if not quoted:
        print("SKILL.md quotes no provenance note", file=sys.stderr)
        return 1
    if quoted != actual:
        print("SKILL.md says: %s" % quoted, file=sys.stderr)
        print("the pack says: %s" % actual, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
