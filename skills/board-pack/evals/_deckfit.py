#!/usr/bin/env python3
"""Does every text box in a written `.pptx` hold what was put in it? Used by deck-fit.sh.

The deck is drawn with fixed EMU geometry, so nothing wraps or grows for free: a box holds
what it was given whether or not it fits. Every textBody carries `normAutofit` with no
computed fontScale, so a viewer that recomputes shrinks the text and one that does not
clips it — and a board decision with its last line cut off is the failure this exists to
stop.

**Deliberately not the writer's arithmetic.** `pptx_writer.para_height` decides where to
paginate; this decides whether the result fits, with its own constants and its own line
model. Two implementations sharing a constant agree by construction and prove nothing — the
band-label contrast defect survived four releases because the check and the code were
describing the same wrong decision. The advances here run NARROWER than the writer's, so
the writer paginates slightly early and a failure reported here is real overflow rather
than the two models disagreeing at the margin.

It is an estimate, and the honest limit is worth stating plainly: real line breaking needs
the font, and the font belongs to PowerPoint. What this catches is a box asked to hold
substantially more than it can — which is the failure that actually ships — not a single
word tipping onto a second line.

Usage:
  _deckfit.py <deck.pptx>            report boxes over budget, exit 1 if any
  _deckfit.py <deck.pptx> --count    print how many text boxes were measured
  _deckfit.py <deck.pptx> --slides   print the slide count
"""
from __future__ import annotations

import re
import sys
import zipfile

EMU_PER_PT = 12700
BULLET_INDENT_PT = 228600 / EMU_PER_PT
LINE = 1.22
# A box is over budget only past this much slack. Below it the two models are arguing
# about a rounding, not about a sentence falling off a slide.
TOLERANCE = 1.02

NARROW = frozenset("iljtfrI.,;:'\"!|()[]- ")
WIDE = frozenset("mMW@%")

SLIDE_RE = re.compile(r"ppt/slides/slide(\d+)\.xml$")
SHAPE_RE = re.compile(r"<p:sp>.*?</p:sp>", re.S)
NAME_RE = re.compile(r'name="([^"]*)"')
EXT_RE = re.compile(r'<a:ext cx="(\d+)" cy="(\d+)"/>')
PARA_RE = re.compile(r"<a:p>.*?</a:p>", re.S)
TEXT_RE = re.compile(r"<a:t>(.*?)</a:t>", re.S)
SZ_RE = re.compile(r'sz="(\d+)"')
SPC_RE = re.compile(r'<a:spcPts val="(\d+)"/>')


def advance_em(text: str) -> float:
    total = 0.0
    for ch in text:
        if ch in NARROW:
            total += 0.30
        elif ch in WIDE:
            total += 0.92
        elif ch.isupper():
            total += 0.70
        elif ch.isdigit():
            total += 0.56
        else:
            total += 0.53
    return total


def _slide_names(zf):
    return sorted((n for n in zf.namelist() if SLIDE_RE.search(n)),
                  key=lambda n: int(SLIDE_RE.search(n).group(1)))


def scan(path: str):
    zf = zipfile.ZipFile(path)
    problems, boxes = [], 0
    for name in _slide_names(zf):
        num = int(SLIDE_RE.search(name).group(1))
        xml = zf.read(name).decode("utf-8")
        for blob in SHAPE_RE.findall(xml):
            if "<p:txBody>" not in blob:
                continue
            ext = EXT_RE.search(blob)
            if not ext:
                continue
            boxes += 1
            shape = (NAME_RE.search(blob) or [None, ""])[1] if NAME_RE.search(blob) else ""
            box_w = int(ext.group(1)) / EMU_PER_PT
            box_h = int(ext.group(2)) / EMU_PER_PT
            used = 0.0
            for para in PARA_RE.findall(blob):
                usable = box_w - (BULLET_INDENT_PT if "buChar" in para else 0)
                text = "".join(TEXT_RE.findall(para))
                sizes = [int(s) for s in SZ_RE.findall(para)] or [1800]
                pt = max(sizes) / 100.0
                spc = SPC_RE.search(para)
                after = (int(spc.group(1)) / 100.0) if spc else 0.0
                if not text.strip():
                    used += pt * LINE + after
                    continue
                if usable <= 0:
                    used += pt * LINE + after
                    continue
                lines = max(1, int(-(-(advance_em(text) * pt) // usable)))
                used += lines * pt * LINE + after
            if used > box_h * TOLERANCE:
                problems.append(
                    "slide {} [{}] needs {:.0f}pt in a {:.0f}pt box (x{:.2f})".format(
                        num, shape or "unnamed", used, box_h, used / box_h))
    return problems, boxes


def main(argv) -> int:
    if not argv:
        print("usage: _deckfit.py <deck.pptx> [--count|--slides]", file=sys.stderr)
        return 2
    if "--slides" in argv:
        print(len(_slide_names(zipfile.ZipFile(argv[0]))))
        return 0
    problems, boxes = scan(argv[0])
    if "--count" in argv:
        print(boxes)
        return 0
    # A scan of zero boxes reports no problems, which reads exactly like a deck that fits.
    if not boxes:
        print("ERROR no text boxes were measured; the walk is broken, not the deck sound")
        return 1
    for p in problems:
        print("FAIL " + p)
    print("{} text boxes measured, {} over budget".format(boxes, len(problems)))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
