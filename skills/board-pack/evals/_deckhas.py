#!/usr/bin/env python3
"""Does any slide of a .pptx contain this text? Exit 0 if yes, 1 if no.

Deck/document parity is a rule this skill has enforced for prose since it shipped: a figure
or a warning that reaches one deliverable and not the other means two people reading "the
same pack" saw different things. An applicability conflict is the case where that matters
most — the deck is what is open in the room while the document is what gets filed.

Reads the drawn text runs only, so a match cannot come from a shape name, a theme, or the
slide layout: the question is whether a reader would SEE it.

Also answers two shape questions the deck-mode suite needs, for the same reason: they are
about what a reader SEES, so they are asked of the drawn runs and nothing else.

Usage:
  _deckhas.py <deck.pptx> <text> [<text> ...]   exit 0 if all are present
  _deckhas.py <deck.pptx> --core               print slides before the Appendix divider
  _deckhas.py <deck.pptx> --lost <other.pptx>  print runs in <deck> absent from <other>
"""
from __future__ import annotations

import re
import sys
import zipfile

SLIDE_RE = re.compile(r"ppt/slides/slide\d+\.xml$")
TEXT_RE = re.compile(r"<a:t>(.*?)</a:t>", re.S)


def slide_runs(path: str) -> list:
    """Per slide, in deck order, the text runs a reader would see."""
    zf = zipfile.ZipFile(path)
    names = sorted((n for n in zf.namelist() if SLIDE_RE.search(n)),
                   key=lambda n: int(re.search(r"(\d+)", n.rsplit("/", 1)[-1]).group(1)))
    return [TEXT_RE.findall(zf.read(n).decode("utf-8")) for n in names]


def slide_text(path: str) -> str:
    return " ".join(r for slide in slide_runs(path) for r in slide)


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

    if argv[1] == "--core":
        # Slides before the Appendix divider. A section divider's FIRST run is its title —
        # reading runs[1] gets the subtitle, which is how this was miscounted the first time.
        runs = slide_runs(argv[0])
        cut = next((i for i, r in enumerate(runs) if r and r[0].strip() == "Appendix"),
                   len(runs))
        print(cut)
        return 0

    if argv[1] == "--lost":
        # Every run this deck draws that the other one does not. The board deck is a
        # REORDERING, so this must be empty except for the dividers it deliberately drops.
        mine = [r.strip() for slide in slide_runs(argv[0]) for r in slide if r.strip()]
        other_runs = set(r.strip() for slide in slide_runs(argv[2]) for r in slide)
        for run in sorted(set(mine) - other_runs):
            print(run)
        return 0

    missing = [needle for needle in argv[1:] if needle not in text]
    if missing:
        print("absent from every slide: " + ", ".join(repr(m) for m in missing))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
