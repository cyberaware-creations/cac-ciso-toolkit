#!/usr/bin/env python3
"""WCAG AA contrast for every text run in a written `.pptx`. Used by deck-contrast.sh.

The HTML artifacts are measured in a real headless Chrome, because a resolved layout is the
only place a colour pairing exists: which surface an element lands on, what an 8-digit alpha
composites to over it, and what `opacity` does are all layout facts rather than CSS text. The
deck had no equivalent and so had no check at all — the one output format in this suite that
goes to a board with nothing measuring it.

It does not need a rendering engine, and that is a property of how the deck is written rather
than a shortcut taken here. `pptx_writer.py` emits explicit EMU geometry and an explicit
`srgbClr` on every run and every fill. There is no cascade, no inheritance and no theme
indirection to resolve, so the pairing a viewer will see is already written down. What this
walks is the emitted XML, not the source's intention.

Two things it is honest about NOT being:

  * It is not a renderer. Font metrics, autofit and line breaking belong to PowerPoint, so
    this says nothing about whether text overflows its box.
  * It resolves a run's background by z-order and containment, which is what the writer
    actually does — every backdrop is a full-bleed or containing rect drawn before the text
    over it. A deck that started overlapping partially-covering shapes would need more than
    this, and would deserve to be told so rather than quietly mis-measured.

Usage:
  _deckcontrast.py <deck.pptx>            report failures, exit 1 if any
  _deckcontrast.py <deck.pptx> --count    print how many runs were measured
"""
from __future__ import annotations

import re
import sys
import zipfile

# WCAG 2.1: large text is >= 18pt, or >= 14pt when bold. Everything else owes 4.5:1.
LARGE_PT = 18.0
LARGE_PT_BOLD = 14.0
FLOOR_NORMAL = 4.5
FLOOR_LARGE = 3.0

SHAPE_RE = re.compile(r"<p:sp>.*?</p:sp>", re.S)
NAME_RE = re.compile(r'<p:cNvPr[^>]*name="([^"]*)"')
OFF_RE = re.compile(r'<a:off x="(-?\d+)" y="(-?\d+)"/>')
EXT_RE = re.compile(r'<a:ext cx="(\d+)" cy="(\d+)"/>')
SPPR_RE = re.compile(r"<p:spPr>.*?</p:spPr>", re.S)
FILL_RE = re.compile(r'<a:solidFill><a:srgbClr val="([0-9A-Fa-f]{6})"/></a:solidFill>')
RUN_RE = re.compile(r"<a:r>(.*?)</a:r>", re.S)
RPR_RE = re.compile(r"<a:rPr[^>]*>")
SZ_RE = re.compile(r'sz="(\d+)"')
B_RE = re.compile(r'b="1"')
COLOUR_RE = re.compile(r'<a:srgbClr val="([0-9A-Fa-f]{6})"/>')
TEXT_RE = re.compile(r"<a:t>(.*?)</a:t>", re.S)
BG_RE = re.compile(r"<p:bg>.*?<a:srgbClr val=\"([0-9A-Fa-f]{6})\"/>.*?</p:bg>", re.S)


def _luminance(hex6: str) -> float:
    def chan(v):
        v = v / 255.0
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (int(hex6[i:i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * chan(r) + 0.7152 * chan(g) + 0.0722 * chan(b)


def contrast(fg: str, bg: str) -> float:
    a, b = _luminance(fg), _luminance(bg)
    hi, lo = max(a, b), min(a, b)
    return (hi + 0.05) / (lo + 0.05)


def _shapes(slide_xml: str):
    """Every shape, in document order — which is z-order, back to front."""
    out = []
    for m in SHAPE_RE.finditer(slide_xml):
        blob = m.group(0)
        name = (NAME_RE.search(blob) or [None, ""])[1] if NAME_RE.search(blob) else ""
        off, ext = OFF_RE.search(blob), EXT_RE.search(blob)
        if not off or not ext:
            continue
        x, y = int(off.group(1)), int(off.group(2))
        cx, cy = int(ext.group(1)), int(ext.group(2))
        # The fill belongs to spPr. A run's own <a:solidFill> lives inside txBody and would
        # otherwise be read as the shape's background — which is the text colour, and would
        # make every run pass against itself at 1:1... or rather at exactly 1.0, silently.
        sppr = SPPR_RE.search(blob)
        fill = None
        if sppr:
            f = FILL_RE.search(sppr.group(0))
            fill = f.group(1).upper() if f else None
        out.append({"name": name, "box": (x, y, cx, cy), "fill": fill, "xml": blob})
    return out


def _background_for(shape, earlier, slide_bg: str) -> str:
    """The colour a viewer sees behind this shape's text.

    Last filled shape, in z-order, whose box contains this one. `pptx_writer` draws a
    backdrop before the text that sits on it, so the nearest containing fill is what a
    viewer sees. Falls back to the deck's own slide background.
    """
    x, y, cx, cy = shape["box"]
    found = slide_bg
    for other in earlier:
        if other["fill"] is None:
            continue
        ox, oy, ocx, ocy = other["box"]
        if ox <= x and oy <= y and ox + ocx >= x + cx and oy + ocy >= y + cy:
            found = other["fill"]
    return found


def _runs(shape):
    """Each run's colour, point size, boldness and text."""
    body = shape["xml"].split("<p:txBody>", 1)
    if len(body) < 2:
        return
    for m in RUN_RE.finditer(body[1]):
        blob = m.group(0)
        rpr = RPR_RE.search(blob)
        rpr_text = rpr.group(0) if rpr else ""
        sz = SZ_RE.search(rpr_text)
        pt = (int(sz.group(1)) / 100.0) if sz else 18.0
        bold = bool(B_RE.search(rpr_text))
        col = COLOUR_RE.search(blob)
        text = "".join(TEXT_RE.findall(blob))
        if not col or not text.strip():
            continue
        yield col.group(1).upper(), pt, bold, text


def scan(path: str):
    zf = zipfile.ZipFile(path)
    names = sorted((n for n in zf.namelist()
                    if re.match(r"ppt/slides/slide\d+\.xml$", n)),
                   key=lambda n: int(re.search(r"(\d+)", n.rsplit("/", 1)[1]).group(1)))
    master = ""
    for cand in ("ppt/slideMasters/slideMaster1.xml", "ppt/slideLayouts/slideLayout1.xml"):
        try:
            master = zf.read(cand).decode("utf-8")
            break
        except KeyError:
            continue
    bg = BG_RE.search(master)
    slide_bg = bg.group(1).upper() if bg else "FFFFFF"

    problems, measured = [], 0
    for n in names:
        num = int(re.search(r"(\d+)", n.rsplit("/", 1)[1]).group(1))
        shapes = _shapes(zf.read(n).decode("utf-8"))
        for i, shape in enumerate(shapes):
            behind = _background_for(shape, shapes[:i], slide_bg)
            for colour, pt, bold, text in _runs(shape):
                measured += 1
                large = pt >= LARGE_PT or (bold and pt >= LARGE_PT_BOLD)
                floor = FLOOR_LARGE if large else FLOOR_NORMAL
                ratio = contrast(colour, behind)
                if ratio + 0.005 < floor:
                    problems.append(
                        "slide {} [{}] {:.2f}:1 (need {}) #{} on #{} {:g}pt{} — {!r}".format(
                            num, shape["name"] or "unnamed", ratio, floor, colour, behind,
                            pt, "/bold" if bold else "", text[:52]))
    return problems, measured


def main(argv) -> int:
    if not argv:
        print("usage: _deckcontrast.py <deck.pptx> [--count]", file=sys.stderr)
        return 2
    problems, measured = scan(argv[0])
    if "--count" in argv:
        print(measured)
        return 0
    # A scan that measured nothing is a broken walk, not a clean deck — the same hole
    # every guard in this repo has had to be told about explicitly.
    if not measured:
        print("ERROR no text runs were measured; the walk is broken, not the deck clean")
        return 1
    for p in problems:
        print("FAIL " + p)
    print("{} runs measured, {} under AA".format(measured, len(problems)))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
