#!/usr/bin/env python3
"""Does any slide of a .pptx contain this text? Exit 0 if yes, 1 if no.

Deck/document parity is a rule this skill has enforced for prose since it shipped: a figure
or a warning that reaches one deliverable and not the other means two people reading "the
same pack" saw different things. An applicability conflict is the case where that matters
most — the deck is what is open in the room while the document is what gets filed.

Reads the drawn text runs only, so a match cannot come from a shape name, a theme, or the
slide layout: the question is whether a reader would SEE it.

Usage: _deckhas.py <deck.pptx> <text> [<text> ...]   (all must be present)
"""
from __future__ import annotations

import re
import sys
import zipfile

SLIDE_RE = re.compile(r"ppt/slides/slide\d+\.xml$")
TEXT_RE = re.compile(r"<a:t>(.*?)</a:t>", re.S)


def slide_text(path: str) -> str:
    zf = zipfile.ZipFile(path)
    out = []
    for name in zf.namelist():
        if SLIDE_RE.search(name):
            out.extend(TEXT_RE.findall(zf.read(name).decode("utf-8")))
    return " ".join(out)


def main(argv) -> int:
    if len(argv) < 2:
        print("usage: _deckhas.py <deck.pptx> <text> [...]", file=sys.stderr)
        return 2
    try:
        text = slide_text(argv[0])
    except (OSError, zipfile.BadZipFile, ValueError) as exc:
        print(f"could not read {argv[0]}: {exc}", file=sys.stderr)
        return 2
    # A deck with no drawn text answers "no" to every question, which would read as a clean
    # negative result. Refused instead: that is a broken walk, not an absent phrase.
    if not text.strip():
        print("ERROR no text runs in the deck; the walk is broken", file=sys.stderr)
        return 2
    missing = [needle for needle in argv[1:] if needle not in text]
    if missing:
        print("absent from every slide: " + ", ".join(repr(m) for m in missing))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
