#!/usr/bin/env python3
"""pptx_writer.py — write a real .pptx from the standard library.

A .pptx is a Zip container of Open Packaging Convention parts: some XML describing the
presentation, one XML part per slide, and a web of relationship files pointing at each other.
`zipfile` and string formatting are enough to produce one, so this ships with no dependency —
which is the constraint the whole toolkit runs under.

**What this is not.** It is not a PowerPoint implementation. It writes exactly the shapes this
pack needs — a branded dark cover, dark section dividers, a two-column figure strip, and light
content slides of title-plus-paragraphs — using explicit EMU geometry rather than layout
placeholders, because a placeholder inherits from a master and a master is where fidelity
across PowerPoint, Keynote and Google Slides goes wrong. Everything here is positioned
absolutely and styled inline, which is uglier XML and far more predictable.

**The brand.** Colours are the tokens in `skills/risk-register/assets/brand.md`, and the deck
draws from the same list as the HTML pack. Two of those tokens are a trap worth naming here:
a band's fill and a band's text colour are different hexes for different jobs, and on the
light slides the fills measure 1.5–2.6:1. `verify()` enforces the split rather than trusting
whoever writes the next slide kind. The house mark itself is an SVG and is NOT embedded: the
deck carries the patina spark, drawn with native geometry, because SVG support is not even
across the applications a board pack gets opened in.

**The limit worth stating.** Structural validity is testable and is tested: the container
opens, every declared part exists, every relationship resolves, every part is well-formed XML,
and the content types cover every part. How it *renders* is not testable from here. Open the
example once in the application you care about before sending a pack to a board.

Units: EMU (English Metric Units), 914400 per inch. Slides are 13.333 x 7.5 inches — 16:9.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
import zipfile
from xml.sax.saxutils import escape

EMU_PER_INCH = 914400
EMU_PER_PT = 12700
SLIDE_W = int(13.333 * EMU_PER_INCH)
SLIDE_H = int(7.5 * EMU_PER_INCH)


def inch(n) -> int:
    return int(n * EMU_PER_INCH)


INK = "14171C"
MUTED = "4A4F58"
LINE = "D8D3C6"
SURFACE = "F6F4EE"
ACCENT = "666D7C"

# Brand tokens, spelled exactly as skills/risk-register/assets/brand.md spells them so a
# reader can grep one against the other. The deck and the HTML pack draw from the same list.
LIMESTONE = "EAE7DF"       # light text on ink
LIMESTONE_DIM = "9AA0A6"   # muted text on ink; the footer stamp
PATINA = "2FA98C"          # brand/action accent — chrome only, never a measurement
WORKBENCH = "F6F4EE"       # light working ground

# The RAG ramp, in its two jobs. A fill and a text colour are different jobs and the same hex
# cannot do both: on a light ground the fills measure 1.5–2.6:1, which is why `SEV_TEXT`
# exists and why nothing on a light slide is allowed to reach for `SEV_FILL`. `verify()`
# enforces that rather than trusting the caller — see the palette checks there.
SEV_FILL = {"good": "30915B", "medium": "e8c547", "high": "e08e0b", "critical": "c0392b"}
# The band-as-text variants, matching cac_graphics._RAG[*]["text"] exactly. critical
# is 8B2119 and NOT the c0392b fill: the fill does pass AA as text (5.44:1 on white),
# which is why the brand doc once reused it, but then one deliverable drew critical
# text in one hex and the SVG marks beside it drew the same band in another. One
# token, one answer.
SEV_TEXT = {"good": "25764A", "medium": "7A6410", "high": "8F5B06", "critical": "8B2119"}
# Green↔red is ΔE 6.2 under deuteranopia, so a band is never carried by colour alone. Every
# banded figure prints its band word beside the number, in the same colour.
SEV_WORD = {"good": "Good", "medium": "Medium", "high": "High", "critical": "Critical"}

PALETTE = frozenset(
    v.upper() for v in
    [INK, MUTED, LINE, SURFACE, ACCENT, LIMESTONE, LIMESTONE_DIM, PATINA, WORKBENCH,
     "FFFFFF"] + list(SEV_FILL.values()) + list(SEV_TEXT.values()))
# A fill hex that has no text twin. `critical` is deliberately absent: the same hex is both
# its fill and its text colour, because it already measures past 4.5:1 on a light ground.
FILL_ONLY = frozenset(v.upper() for v in SEV_FILL.values()) - frozenset(
    v.upper() for v in SEV_TEXT.values())


def sev_of(value):
    """The band a caller declared, or None. Never inferred, never defaulted.

    The pack model carries a band only where a producer declared one, so anything this does
    not recognise is None and renders in ink. A figure the pack left unbanded is a population,
    not a status, and colouring it would report something no producer said.
    """
    return value if value in SEV_TEXT else None

# Namespaces, spelled once. OOXML is unforgiving about these: a wrong namespace produces a
# file PowerPoint opens and silently shows as empty, which is the worst failure available.
NS_P = "http://schemas.openxmlformats.org/presentationml/2006/main"
NS_A = "http://schemas.openxmlformats.org/drawingml/2006/main"
NS_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
CT_SLIDE = ("application/vnd.openxmlformats-officedocument.presentationml.slide+xml")
CT_PRES = ("application/vnd.openxmlformats-officedocument."
           "presentationml.presentation.main+xml")
CT_MASTER = ("application/vnd.openxmlformats-officedocument."
             "presentationml.slideMaster+xml")
CT_LAYOUT = ("application/vnd.openxmlformats-officedocument."
             "presentationml.slideLayout+xml")
CT_THEME = "application/vnd.openxmlformats-officedocument.theme+xml"


def esc(text) -> str:
    return escape("" if text is None else str(text))


def _run(text: str, size: int, bold: bool = False, colour: str = INK) -> str:
    return (f'<a:r><a:rPr lang="en-GB" sz="{size}" b="{1 if bold else 0}" dirty="0">'
            f'<a:solidFill><a:srgbClr val="{colour}"/></a:solidFill>'
            f'<a:latin typeface="Helvetica Neue"/></a:rPr>'
            f'<a:t>{esc(text)}</a:t></a:r>')


def _para(text: str, size: int, bold: bool = False, colour: str = INK,
          space_after: int = 600, bullet: bool = False) -> str:
    """One paragraph. `bullet` uses a real buChar so it survives a copy-paste out of the deck."""
    return _para_runs(_run(text, size, bold, colour), space_after, bullet)


def _para_runs(runs: str, space_after: int = 600, bullet: bool = False) -> str:
    """One paragraph from runs already built — a number and its band word on one line."""
    marker = ('<a:buFont typeface="Arial"/><a:buChar char="•"/>' if bullet
              else "<a:buNone/>")
    indent = ' marL="228600" indent="-228600"' if bullet else ' marL="0" indent="0"'
    return (f'<a:p><a:pPr{indent}><a:spcAft><a:spcPts val="{space_after}"/></a:spcAft>'
            f'{marker}</a:pPr>{runs}</a:p>')


def _textbox(shape_id: int, name: str, x: int, y: int, cx: int, cy: int,
             paragraphs: str) -> str:
    return (f'<p:sp><p:nvSpPr><p:cNvPr id="{shape_id}" name="{esc(name)}"/>'
            f'<p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr>'
            f'<p:spPr><a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>'
            f'<a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:noFill/></p:spPr>'
            f'<p:txBody><a:bodyPr wrap="square" lIns="0" tIns="0" rIns="0" bIns="0">'
            f'<a:normAutofit/></a:bodyPr><a:lstStyle/>{paragraphs}</p:txBody></p:sp>')


def _rect(shape_id: int, x: int, y: int, cx: int, cy: int, fill: str,
          name: str = "", prst: str = "rect") -> str:
    """A filled shape with no outline and no text.

    `name` is what a reader sees in PowerPoint's selection pane, and it is also how
    `verify()` tells a backdrop from a rule from a figure tile — a shape whose name says
    which band it carries can be checked against the colour it actually uses.
    """
    return (f'<p:sp><p:nvSpPr>'
            f'<p:cNvPr id="{shape_id}" name="{esc(name or f"Rule {shape_id}")}"/>'
            f'<p:cNvSpPr/><p:nvPr/></p:nvSpPr>'
            f'<p:spPr><a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>'
            f'<a:prstGeom prst="{prst}"><a:avLst/></a:prstGeom>'
            f'<a:solidFill><a:srgbClr val="{fill}"/></a:solidFill>'
            f'<a:ln><a:noFill/></a:ln></p:spPr>'
            f'<p:txBody><a:bodyPr/><a:lstStyle/><a:p/></p:txBody></p:sp>')


def _spark(shape_id: int, x: int, y: int, size: int, name: str) -> str:
    """The patina spark — a diamond, drawn with native geometry.

    The house mark is an anvil and a spark. The anvil is an SVG, and PowerPoint's SVG support
    is not even across the applications a board pack gets opened in, so the deck carries the
    spark alone rather than a mark that may not draw. It is chrome: it never stands for a
    measurement.
    """
    return _rect(shape_id, x, y, size, size, PATINA, name=name, prst="diamond")


def slide_xml(shapes: str) -> str:
    return (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            f'<p:sld xmlns:a="{NS_A}" xmlns:r="{NS_R}" xmlns:p="{NS_P}">'
            f'<p:cSld><p:spTree>'
            f'<p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>'
            f'<p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/>'
            f'<a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>'
            f'{shapes}</p:spTree></p:cSld>'
            f'<p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sld>')


def _meta_pairs(meta) -> list:
    """Normalise cover meta into ordered (label, value) pairs.

    Accepts a dict, a list of pairs, or a list of plain strings, because the caller on the
    other side of this module is a renderer that may reasonably reach for any of the three.
    Empty values are dropped rather than printed as a label with nothing after it.
    """
    if isinstance(meta, dict):
        items = list(meta.items())
    else:
        items = list(meta or [])
    pairs = []
    for item in items:
        if isinstance(item, (list, tuple)) and len(item) == 2:
            pairs.append((str(item[0]), str(item[1])))
        else:
            pairs.append(("", str(item)))
    return [(k, v) for k, v in pairs if v.strip()]


def _figure_parts(figure) -> tuple:
    """(label, value, band) from a headline figure, however the caller spells it.

    A dict is the pack model's own shape: `{"label": ..., "value": ..., "sev": ...}` with
    `sev` ABSENT — not null — on any figure whose producer declared no band. A pair or triple
    works too. The band is passed through `sev_of`, so an unrecognised one becomes no band
    rather than a guess.
    """
    if isinstance(figure, dict):
        return (str(figure.get("label", "")), figure.get("value", ""),
                sev_of(figure.get("sev")))
    parts = list(figure)
    band = sev_of(parts[2]) if len(parts) > 2 else None
    return str(parts[0]), (parts[1] if len(parts) > 1 else ""), band


class Deck:
    """Accumulates slides, then writes the container.

    Slide geometry is a left margin, a title band, a rule, and a body. Every slide uses it,
    so a reader never has to re-find where things are.

    Four slide kinds, all of which `verify()` knows how to look at:

    * `cover()`   — the dark branded opener. Always lands first, whenever it is called.
    * `section()` — a dark divider between sections.
    * `figures()` — the headline figures, each in the band its producer declared.
    * `add()`     — a light content slide: eyebrow, patina kicker, title, rule, body.

    Every one of them carries the footer and a patina spark, because a deck gets split apart
    and pasted into other decks, and a slide that travels alone still has to say where it
    came from.
    """

    MARGIN = int(0.75 * EMU_PER_INCH)
    BODY_W = SLIDE_W - 2 * MARGIN
    TITLE_Y = int(0.6 * EMU_PER_INCH)
    RULE_Y = int(1.45 * EMU_PER_INCH)
    BODY_Y = int(1.75 * EMU_PER_INCH)
    FOOT_Y = int(6.85 * EMU_PER_INCH)

    KICKER_W = 4 * EMU_PER_PT
    RULE_H = 3 * EMU_PER_PT
    SPARK = inch(0.13)
    FIG_COLS = 2
    FIG_ROWS = 4

    def __init__(self, footer: str, title: str = "", meta=None, eyebrow: str = ""):
        self.slides = []
        self.footer = footer
        self.cover_title = title
        self.cover_meta = _meta_pairs(meta)
        self.cover_eyebrow = eyebrow
        self._cover = None
        self._sections = 0
        self._first_eyebrow = ""

    # --- the branded furniture every slide carries ----------------------------

    def _footer_shapes(self, sid: int, dark: bool = False) -> tuple:
        """The footer, with the spark in front of it. On every slide, both grounds."""
        colour = LIMESTONE_DIM if dark else MUTED
        shapes = [_spark(sid, self.MARGIN, self.FOOT_Y + inch(0.045), self.SPARK,
                         "Footer spark"),
                  _textbox(sid + 1, "Footer", self.MARGIN + inch(0.26), self.FOOT_Y,
                           self.BODY_W - inch(0.26), inch(0.3),
                           _para(self.footer, 900, False, colour, 0))]
        return shapes, sid + 2

    def _head_shapes(self, sid: int, title: str, eyebrow: str) -> tuple:
        """Eyebrow, patina kicker, title, rule — the top of every light slide.

        The kicker hangs in the left margin beside the title, and the rule under the title
        runs limestone with a patina lead. Both are chrome: they mark the brand, never a
        measurement, which is the one rule patina has.
        """
        shapes = []
        if eyebrow:
            if not self._first_eyebrow:
                self._first_eyebrow = eyebrow
            shapes.append(_textbox(sid, "Eyebrow", self.MARGIN, inch(0.32), self.BODY_W,
                                   inch(0.3), _para(eyebrow, 1100, False, MUTED, 0)))
            sid += 1
        shapes.append(_textbox(sid, "Title", self.MARGIN, self.TITLE_Y, self.BODY_W,
                               inch(0.8), _para(title, 2600, True, INK, 0)))
        sid += 1
        shapes.append(_rect(sid, self.MARGIN - inch(0.26), self.TITLE_Y + inch(0.04),
                            self.KICKER_W, inch(0.6), PATINA, name="Title kicker"))
        sid += 1
        shapes.append(_rect(sid, self.MARGIN, self.RULE_Y, self.BODY_W, EMU_PER_PT, LINE,
                            name="Rule"))
        sid += 1
        shapes.append(_rect(sid, self.MARGIN, self.RULE_Y, inch(1.1), self.RULE_H, PATINA,
                            name="Rule lead"))
        return shapes, sid + 1

    # --- slides ---------------------------------------------------------------

    def cover(self, title: str, meta=None, eyebrow: str = "") -> None:
        """The dark branded opener: spark and lockup, eyebrow, title, patina rule, meta.

        It is inserted at the front however late it is called, so a caller cannot produce a
        deck whose cover is slide four.
        """
        meta_pairs = _meta_pairs(meta) or self.cover_meta
        # The eyebrow is furniture, not prose: a cover that states what the document is.
        eyebrow = eyebrow or self.cover_eyebrow or "Board pack"
        sid = 2
        shapes = [_rect(sid, 0, 0, SLIDE_W, SLIDE_H, INK, name="Cover backdrop")]
        sid += 1
        shapes.append(_spark(sid, self.MARGIN, inch(0.62), inch(0.17), "Lockup spark"))
        sid += 1
        shapes.append(_textbox(sid, "Lockup", self.MARGIN + inch(0.32), inch(0.58),
                               inch(6), inch(0.32),
                               _para("Cyber Aware Creations", 1200, True, LIMESTONE, 0)))
        sid += 1
        if eyebrow:
            shapes.append(_textbox(sid, "Eyebrow", self.MARGIN, inch(2.55), self.BODY_W,
                                   inch(0.32),
                                   _para(eyebrow, 1200, False, LIMESTONE_DIM, 0)))
            sid += 1
        shapes.append(_textbox(sid, "Cover title", self.MARGIN, inch(2.95), self.BODY_W,
                               inch(1.5), _para(title, 3600, True, LIMESTONE, 0)))
        sid += 1
        shapes.append(_rect(sid, self.MARGIN, inch(4.62), inch(1.6), self.RULE_H, PATINA,
                            name="Cover rule"))
        sid += 1
        lines = "".join(
            _para_runs(
                (_run(f"{label}  ", 1200, False, LIMESTONE_DIM) if label else "")
                + _run(value, 1200, False, LIMESTONE), 260)
            for label, value in meta_pairs)
        shapes.append(_textbox(sid, "Cover meta", self.MARGIN, inch(4.98), self.BODY_W,
                               inch(1.7), lines))
        sid += 1
        foot, sid = self._footer_shapes(sid, dark=True)
        self._cover = slide_xml("".join(shapes + foot))

    def section(self, label: str, counter: str = "", note: str = "") -> None:
        """A dark divider. `counter` reads like "Section 2 of 5"; supplied or derived.

        It is always printed, and it is always different from the one before it. Two slides
        that read the same at a glance are a reader looking at the wrong one, and a divider
        with nothing but a section name on it is the easiest way to produce a pair.
        """
        self._sections += 1
        counter = counter or f"Section {self._sections}"
        sid = 2
        shapes = [_rect(sid, 0, 0, SLIDE_W, SLIDE_H, INK, name="Section backdrop")]
        sid += 1
        shapes.append(_textbox(sid, "Section label", self.MARGIN, inch(2.85), self.BODY_W,
                               inch(1.2), _para(label, 3200, True, LIMESTONE, 0)))
        sid += 1
        shapes.append(_rect(sid, self.MARGIN, inch(4.35), inch(1.2), self.RULE_H, PATINA,
                            name="Section rule"))
        sid += 1
        shapes.append(_textbox(sid, "Section counter", self.MARGIN, inch(4.65),
                               self.BODY_W, inch(0.3),
                               _para(counter, 1100, False, LIMESTONE_DIM, 0)))
        sid += 1
        if note:
            shapes.append(_textbox(sid, "Section note", self.MARGIN, inch(5.0),
                                   self.BODY_W, inch(0.9),
                                   _para(note, 1100, False, LIMESTONE_DIM, 0)))
            sid += 1
        foot, sid = self._footer_shapes(sid, dark=True)
        self.slides.append(slide_xml("".join(shapes + foot)))

    def figures(self, title: str, figures: list, eyebrow: str = "", note: str = "") -> None:
        """The headline figures, tiled, each in the band its producer declared.

        Two rules hold here and are checked by `verify()` rather than trusted:

        * A figure with no band is ink. Nothing is inferred from the number, its label or
          its neighbours, and a zero is never coloured.
        * A band on this light ground uses `SEV_TEXT`, never `SEV_FILL`. The fills measure
          1.5–2.6:1 on workbench; they are for dark grounds and for shapes that carry no
          text. The band word prints beside the number in the same colour, because green↔red
          is ΔE 6.2 under deuteranopia and colour never carries a band on its own.
        """
        parts = [_figure_parts(f) for f in figures]
        per_slide = self.FIG_COLS * self.FIG_ROWS
        pages = [parts[i:i + per_slide] for i in range(0, len(parts), per_slide)] or [[]]
        gap = inch(0.18)
        tile_w = (self.BODY_W - (self.FIG_COLS - 1) * gap) // self.FIG_COLS
        tile_h = inch(1.0)
        pitch = inch(1.15)
        top = inch(1.85)
        for page_no, page in enumerate(pages, start=1):
            suffix = "" if len(pages) == 1 else f" ({page_no})"
            shapes, sid = self._head_shapes(2, title + suffix, eyebrow)
            for n, (label, value, band) in enumerate(page):
                x = self.MARGIN + (n % self.FIG_COLS) * (tile_w + gap)
                y = top + (n // self.FIG_COLS) * pitch
                index = (page_no - 1) * per_slide + n + 1
                tag = f" [{band}]" if band else ""
                colour = SEV_TEXT[band] if band else INK
                shapes.append(_rect(sid, x, y, tile_w, tile_h, WORKBENCH,
                                    name=f"Figure {index} panel"))
                sid += 1
                if band:
                    shapes.append(_rect(sid, x, y, 3 * EMU_PER_PT, tile_h, colour,
                                        name=f"Figure {index} rule{tag}"))
                    sid += 1
                head = _run(str(value), 1800, True, colour)
                if band:
                    head += _run(f"   {SEV_WORD[band]}", 1000, True, colour)
                shapes.append(_textbox(sid, f"Figure {index}{tag}", x + inch(0.2),
                                       y + inch(0.16), tile_w - inch(0.4),
                                       tile_h - inch(0.28),
                                       _para_runs(head, 160)
                                       + _para(label, 1050, False, MUTED, 0)))
                sid += 1
            if note:
                shapes.append(_textbox(sid, "Figures note", self.MARGIN, inch(6.42),
                                       self.BODY_W, inch(0.32),
                                       _para(note, 1000, False, MUTED, 0)))
                sid += 1
            foot, sid = self._footer_shapes(sid)
            self.slides.append(slide_xml("".join(shapes + foot)))

    def add(self, title: str, paragraphs: list, eyebrow: str = "") -> None:
        """paragraphs: list of (text, size, bold, colour, bullet) tuples."""
        shapes, sid = self._head_shapes(2, title, eyebrow)
        body = "".join(_para(t, size, bold, colour, 700, bullet)
                       for t, size, bold, colour, bullet in paragraphs)
        shapes.append(_textbox(sid, "Body", self.MARGIN, self.BODY_Y, self.BODY_W,
                               self.FOOT_Y - self.BODY_Y - inch(0.2), body))
        sid += 1
        foot, sid = self._footer_shapes(sid)
        self.slides.append(slide_xml("".join(shapes + foot)))

    def _ensure_cover(self) -> None:
        """A deck always opens on the branded cover, even from a caller that asks for none.

        Where `cover()` was never called, the meta is read back out of what the deck already
        holds: the eyebrow the caller puts on every slide (client, period, audience) and the
        footer (the as-at date). Those are the same four facts a cover states, so nothing is
        invented here — a fact that is not in the deck simply does not appear. A caller that
        calls `cover()` itself never reaches this.
        """
        if self._cover is not None:
            return
        meta = list(self.cover_meta)
        if not meta:
            labels = ["Client", "Period", "Audience"]
            fields = [p.strip() for p in self._first_eyebrow.split("·") if p.strip()]
            if len(fields) == len(labels):
                meta = list(zip(labels, fields))
            elif fields:
                meta = [("", " · ".join(fields))]
            stamp = self.footer.split("as at ", 1)
            if len(stamp) == 2 and stamp[1].strip():
                meta.append(("As at", stamp[1].strip()))
        self.cover(self.cover_title or "Security board pack", meta,
                   self.cover_eyebrow or "Board pack")

    def _deck_slides(self) -> list:
        """Every slide in reading order, cover first. The one place slide order is decided."""
        self._ensure_cover()
        return [self._cover] + self.slides

    # --- the container --------------------------------------------------------

    def _content_types(self) -> str:
        overrides = "".join(
            f'<Override PartName="/ppt/slides/slide{i + 1}.xml" ContentType="{CT_SLIDE}"/>'
            for i in range(len(self._deck_slides())))
        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.'
            'relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            f'<Override PartName="/ppt/presentation.xml" ContentType="{CT_PRES}"/>'
            f'<Override PartName="/ppt/slideMasters/slideMaster1.xml" '
            f'ContentType="{CT_MASTER}"/>'
            f'<Override PartName="/ppt/slideLayouts/slideLayout1.xml" '
            f'ContentType="{CT_LAYOUT}"/>'
            f'<Override PartName="/ppt/theme/theme1.xml" ContentType="{CT_THEME}"/>'
            f'{overrides}</Types>')

    def _presentation(self) -> str:
        ids = "".join(f'<p:sldId id="{256 + i}" r:id="rId{i + 2}"/>'
                      for i in range(len(self._deck_slides())))
        return (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                f'<p:presentation xmlns:a="{NS_A}" xmlns:r="{NS_R}" xmlns:p="{NS_P}">'
                f'<p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="rId1"/>'
                f'</p:sldMasterIdLst>'
                f'<p:sldIdLst>{ids}</p:sldIdLst>'
                f'<p:sldSz cx="{SLIDE_W}" cy="{SLIDE_H}"/>'
                f'<p:notesSz cx="{SLIDE_H}" cy="{SLIDE_W}"/></p:presentation>')

    def _presentation_rels(self) -> str:
        count = len(self._deck_slides())
        rels = ['<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/'
                'officeDocument/2006/relationships/slideMaster" '
                'Target="slideMasters/slideMaster1.xml"/>']
        for i in range(count):
            rels.append(f'<Relationship Id="rId{i + 2}" '
                        f'Type="http://schemas.openxmlformats.org/officeDocument/2006/'
                        f'relationships/slide" Target="slides/slide{i + 1}.xml"/>')
        rels.append(f'<Relationship Id="rId{count + 2}" '
                    f'Type="http://schemas.openxmlformats.org/officeDocument/2006/'
                    f'relationships/theme" Target="theme/theme1.xml"/>')
        return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/'
                'relationships">' + "".join(rels) + "</Relationships>")

    @staticmethod
    def _theme() -> str:
        def scheme():
            slots = [("dk1", INK), ("lt1", "FFFFFF"), ("dk2", MUTED), ("lt2", SURFACE),
                     ("accent1", ACCENT), ("accent2", "2F5D3A"), ("accent3", "7A5218"),
                     ("accent4", "7C3A32"), ("accent5", "5E3660"), ("accent6", "2F4A63"),
                     ("hlink", ACCENT), ("folHlink", MUTED)]
            return "".join(f'<a:{n}><a:srgbClr val="{v}"/></a:{n}>' for n, v in slots)
        return (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                f'<a:theme xmlns:a="{NS_A}" name="Cyber Aware Creations">'
                f'<a:themeElements><a:clrScheme name="CAC">{scheme()}</a:clrScheme>'
                f'<a:fontScheme name="CAC">'
                f'<a:majorFont><a:latin typeface="Helvetica Neue"/><a:ea typeface=""/>'
                f'<a:cs typeface=""/></a:majorFont>'
                f'<a:minorFont><a:latin typeface="Helvetica Neue"/><a:ea typeface=""/>'
                f'<a:cs typeface=""/></a:minorFont></a:fontScheme>'
                f'<a:fmtScheme name="CAC">'
                f'<a:fillStyleLst><a:solidFill><a:schemeClr val="phClr"/></a:solidFill>'
                f'<a:solidFill><a:schemeClr val="phClr"/></a:solidFill>'
                f'<a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:fillStyleLst>'
                f'<a:lnStyleLst><a:ln><a:solidFill><a:schemeClr val="phClr"/></a:solidFill>'
                f'</a:ln><a:ln><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:ln>'
                f'<a:ln><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:ln>'
                f'</a:lnStyleLst>'
                f'<a:effectStyleLst><a:effectStyle><a:effectLst/></a:effectStyle>'
                f'<a:effectStyle><a:effectLst/></a:effectStyle>'
                f'<a:effectStyle><a:effectLst/></a:effectStyle></a:effectStyleLst>'
                f'<a:bgFillStyleLst><a:solidFill><a:schemeClr val="phClr"/></a:solidFill>'
                f'<a:solidFill><a:schemeClr val="phClr"/></a:solidFill>'
                f'<a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:bgFillStyleLst>'
                f'</a:fmtScheme></a:themeElements></a:theme>')

    @staticmethod
    def _empty_sp_tree() -> str:
        return ('<p:cSld><p:bg><p:bgPr><a:solidFill><a:srgbClr val="FFFFFF"/></a:solidFill>'
                '<a:effectLst/></p:bgPr></p:bg><p:spTree>'
                '<p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/>'
                '</p:nvGrpSpPr>'
                '<p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/>'
                '<a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>'
                '</p:spTree></p:cSld>')

    @staticmethod
    def _tx_styles() -> str:
        """A conventional master carries these. Nothing here inherits from them — every shape
        this writer emits is positioned and styled inline — but a master without them is
        unusual enough that an application may decide the file needs repairing."""
        def lvls(size):
            return "".join(
                f'<a:lvl{i}pPr marL="{(i - 1) * 342900}" algn="l" rtl="0">'
                f'<a:defRPr sz="{size}"><a:solidFill><a:srgbClr val="{INK}"/></a:solidFill>'
                f'<a:latin typeface="+mn-lt"/></a:defRPr></a:lvl{i}pPr>'
                for i in range(1, 10))
        return (f'<p:txStyles><p:titleStyle>{lvls(2600)}</p:titleStyle>'
                f'<p:bodyStyle>{lvls(1400)}</p:bodyStyle>'
                f'<p:otherStyle>{lvls(1200)}</p:otherStyle></p:txStyles>')

    def _master(self) -> str:
        return (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                f'<p:sldMaster xmlns:a="{NS_A}" xmlns:r="{NS_R}" xmlns:p="{NS_P}">'
                f'{self._empty_sp_tree()}'
                f'<p:clrMap bg1="lt1" tx1="dk1" bg2="lt2" tx2="dk2" accent1="accent1" '
                f'accent2="accent2" accent3="accent3" accent4="accent4" accent5="accent5" '
                f'accent6="accent6" hlink="hlink" folHlink="folHlink"/>'
                f'<p:sldLayoutIdLst><p:sldLayoutId id="2147483649" r:id="rId1"/>'
                f'</p:sldLayoutIdLst>{self._tx_styles()}</p:sldMaster>')

    def _layout(self) -> str:
        """A blank layout with no placeholders.

        Deliberate: every shape this writer emits is positioned absolutely, so nothing
        inherits from here. Placeholder inheritance is exactly where fidelity across
        PowerPoint, Keynote and Google Slides diverges, and a layout with no placeholders has
        nothing to diverge about.
        """
        return (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                f'<p:sldLayout xmlns:a="{NS_A}" xmlns:r="{NS_R}" xmlns:p="{NS_P}" '
                f'type="blank" preserve="1">'
                f'{self._empty_sp_tree()}'
                f'<p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sldLayout>')

    @staticmethod
    def _rels(pairs) -> str:
        body = "".join(
            f'<Relationship Id="{rid}" Type="http://schemas.openxmlformats.org/'
            f'officeDocument/2006/relationships/{kind}" Target="{target}"/>'
            for rid, kind, target in pairs)
        return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/'
                'relationships">' + body + "</Relationships>")

    def write(self, path: str) -> None:
        parts = {
            "[Content_Types].xml": self._content_types(),
            "_rels/.rels": self._rels([
                ("rId1", "officeDocument", "ppt/presentation.xml")]),
            "ppt/presentation.xml": self._presentation(),
            "ppt/_rels/presentation.xml.rels": self._presentation_rels(),
            "ppt/theme/theme1.xml": self._theme(),
            "ppt/slideMasters/slideMaster1.xml": self._master(),
            "ppt/slideMasters/_rels/slideMaster1.xml.rels": self._rels([
                ("rId1", "slideLayout", "../slideLayouts/slideLayout1.xml"),
                ("rId2", "theme", "../theme/theme1.xml")]),
            "ppt/slideLayouts/slideLayout1.xml": self._layout(),
            "ppt/slideLayouts/_rels/slideLayout1.xml.rels": self._rels([
                ("rId1", "slideMaster", "../slideMasters/slideMaster1.xml")]),
        }
        for i, slide in enumerate(self._deck_slides()):
            parts[f"ppt/slides/slide{i + 1}.xml"] = slide
            parts[f"ppt/slides/_rels/slide{i + 1}.xml.rels"] = self._rels([
                ("rId1", "slideLayout", "../slideLayouts/slideLayout1.xml")])
        # A fixed date_time so two runs over the same pack produce identical bytes. A deck
        # that differs only by its zip timestamps cannot be diffed between quarters.
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
            for name in sorted(parts):
                info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o644 << 16
                zf.writestr(info, parts[name])


FIGURE_NAME = re.compile(r"^Figure (\d+)( panel| rule)?(?: \[([a-z]+)\])?$")


def _slide_shapes(root) -> list:
    """(name, colours, text) for every shape on a slide, from the XML alone."""
    out = []
    for sp in root.iter(f"{{{NS_P}}}sp"):
        cnv = sp.find(f"{{{NS_P}}}nvSpPr/{{{NS_P}}}cNvPr")
        name = cnv.get("name", "") if cnv is not None else ""
        colours = {c.get("val", "").upper() for c in sp.iter(f"{{{NS_A}}}srgbClr")}
        text = "".join(t.text or "" for t in sp.iter(f"{{{NS_A}}}t"))
        out.append((name, colours, text))
    return out


def _check_slide(name: str, position: int, root) -> list:
    """What every slide owes the brand, and what each slide kind owes on top of it.

    A slide kind `verify` cannot see is a new way to ship a broken deck in silence, so each
    kind names its own parts in the shape names and this reads them back:

    * the footer and the spark, on every slide, because a deck gets split apart;
    * the palette, closed — anything outside the brand list is a hand-picked colour;
    * the RAG fills, barred from any slide with no dark backdrop, which is the one rule that
      cannot be checked by eye and the reason `SEV_FILL` and `SEV_TEXT` both exist;
    * a figure tile: banded ones carry the band's text colour AND its word, unbanded ones
      carry no band colour at all — a figure the pack left unbanded must not be coloured.
    """
    problems = []
    ids = [e.get("id") for e in root.iter(f"{{{NS_P}}}cNvPr")]
    if len(ids) != len(set(ids)):
        problems.append(f"{name}: two shapes share an id, which PowerPoint may rewrite")
    shapes = _slide_shapes(root)
    named = {nm: (cols, text) for nm, cols, text in shapes}

    if not named.get("Footer", ((), ""))[1].strip():
        problems.append(f"{name}: no footer text — every slide has to carry the footer")
    if not any(nm.endswith("spark") for nm, _, _ in shapes):
        problems.append(f"{name}: no brand spark")

    used = set()
    for _, cols, _ in shapes:
        used |= cols
    stray = sorted(c for c in used if c and c not in PALETTE)
    if stray:
        problems.append(f"{name}: colour outside the brand palette: {', '.join(stray)}")
    dark = any(nm.endswith("backdrop") and INK.upper() in cols for nm, cols, _ in shapes)
    if not dark:
        fills = sorted(used & FILL_ONLY)
        if fills:
            problems.append(f"{name}: a band FILL on a light slide: {', '.join(fills)} — "
                            f"a light ground takes the band's text colour")

    if "Cover backdrop" in named:
        if position != 1:
            problems.append(f"{name}: the cover is slide {position}, not slide 1")
        for part in ("Lockup", "Eyebrow", "Cover title", "Cover rule", "Cover meta"):
            if part not in named:
                problems.append(f"{name}: the cover has no {part}")
            elif part != "Cover rule" and not named[part][1].strip():
                problems.append(f"{name}: the cover's {part} is empty")
    if "Section backdrop" in named:
        for part in ("Section label", "Section counter"):
            if not named.get(part, ((), ""))[1].strip():
                problems.append(f"{name}: a section divider with no {part.lower()}")

    for shape_name, cols, text in shapes:
        match = FIGURE_NAME.match(shape_name)
        if not match:
            continue
        band = match.group(3)
        if band and band not in SEV_TEXT:
            problems.append(f"{name}: {shape_name} names a band nothing declares")
            continue
        if band:
            if SEV_TEXT[band].upper() not in cols:
                problems.append(f"{name}: {shape_name} is not in its band's text colour")
            if match.group(2) is None and SEV_WORD[band] not in text:
                problems.append(f"{name}: {shape_name} shows its band in colour alone")
        else:
            banded = sorted(cols & (frozenset(v.upper() for v in SEV_TEXT.values())
                                    | frozenset(v.upper() for v in SEV_FILL.values())))
            if banded:
                problems.append(f"{name}: {shape_name} carries no band but is coloured "
                                f"like one: {', '.join(banded)}")
    return problems


def verify(path: str) -> list:
    """Structural check of a written .pptx. Returns a list of problems; empty means sound.

    This is what can honestly be tested without an office application: the container opens,
    every part is well-formed XML, every declared part exists, every relationship target
    resolves, every part has a content type, and every slide is the kind of slide it claims
    to be — see `_check_slide` for what that means per kind. Rendering fidelity is not
    covered — open it once in the application you care about.
    """
    problems = []
    try:
        zf = zipfile.ZipFile(path)
    except zipfile.BadZipFile as exc:
        return [f"not a readable zip container: {exc}"]
    with zf:
        names = set(zf.namelist())
        bad = zf.testzip()
        if bad:
            problems.append(f"corrupt member: {bad}")
        for required in ("[Content_Types].xml", "_rels/.rels", "ppt/presentation.xml",
                         "ppt/_rels/presentation.xml.rels"):
            if required not in names:
                problems.append(f"missing required part: {required}")
        for name in sorted(names):
            if not name.endswith((".xml", ".rels")):
                continue
            try:
                ET.fromstring(zf.read(name))
            except ET.ParseError as exc:
                problems.append(f"{name} is not well-formed XML: {exc}")
        # Every relationship target must resolve to a real part.
        for name in sorted(n for n in names if n.endswith(".rels")):
            base = name.rsplit("_rels/", 1)[0]
            try:
                root = ET.fromstring(zf.read(name))
            except ET.ParseError:
                continue
            for rel in root:
                target = rel.get("Target", "")
                if target.startswith(("http:", "https:")) or rel.get("TargetMode") == "External":
                    continue
                import posixpath
                resolved = posixpath.normpath(posixpath.join(base, target))
                if resolved not in names:
                    problems.append(f"{name}: relationship target does not resolve: "
                                    f"{target} -> {resolved}")
        # Every part needs a content type, by Default extension or by Override.
        try:
            ct = ET.fromstring(zf.read("[Content_Types].xml"))
        except (KeyError, ET.ParseError) as exc:
            problems.append(f"[Content_Types].xml unreadable: {exc}")
        else:
            defaults = {e.get("Extension", "").lower() for e in ct
                        if e.tag.endswith("Default")}
            overrides = {e.get("PartName") for e in ct if e.tag.endswith("Override")}
            for name in sorted(names):
                if name == "[Content_Types].xml":
                    continue
                ext = name.rsplit(".", 1)[-1].lower()
                if ext not in defaults and "/" + name not in overrides:
                    problems.append(f"no content type declared for {name}")
            # A content type is not enough — it has to be the RIGHT one. Every part below
            # falls under `Default Extension="xml"`, so a missing Override leaves it typed
            # as plain application/xml and the check above passes over it. PowerPoint does
            # not: a slide typed as application/xml is a slide it will not open. This gap
            # was found by mutation testing, not by reading the code.
            required = [("ppt/presentation.xml", CT_PRES),
                        ("ppt/slideMasters/slideMaster1.xml", CT_MASTER),
                        ("ppt/slideLayouts/slideLayout1.xml", CT_LAYOUT),
                        ("ppt/theme/theme1.xml", CT_THEME)]
            required += [(n, CT_SLIDE) for n in sorted(names)
                         if n.startswith("ppt/slides/slide") and n.endswith(".xml")]
            typed = {e.get("PartName"): e.get("ContentType") for e in ct
                     if e.tag.endswith("Override")}
            for name, want in required:
                if name not in names:
                    continue
                got = typed.get("/" + name)
                if got != want:
                    problems.append(f"{name} is typed {got!r}, expected {want!r}")
        # --- the slides themselves, kind by kind ------------------------------
        # Sorted numerically: slide10 sorts before slide2 as a string, and "is the cover
        # slide 1" is a question about the deck's order, not its filenames.
        slide_names = sorted(
            (n for n in names
             if n.startswith("ppt/slides/slide") and n.endswith(".xml")),
            key=lambda n: int(n[len("ppt/slides/slide"):-len(".xml")]))
        if not slide_names:
            problems.append("the container holds no slides")
        covers = 0
        for position, slide in enumerate(slide_names, start=1):
            try:
                root = ET.fromstring(zf.read(slide))
            except ET.ParseError:
                continue  # already reported as not well-formed
            if any(nm == "Cover backdrop" for nm, _, _ in _slide_shapes(root)):
                covers += 1
            problems.extend(_check_slide(slide, position, root))
        if slide_names and covers != 1:
            problems.append(f"the deck carries {covers} cover slides, expected exactly 1")

        # The slide list must match the slide parts, or PowerPoint shows an empty deck.
        try:
            pres = ET.fromstring(zf.read("ppt/presentation.xml"))
        except (KeyError, ET.ParseError):
            return problems
        listed = len([e for e in pres.iter() if e.tag == f"{{{NS_P}}}sldId"])
        actual = len([n for n in names if n.startswith("ppt/slides/slide")
                      and n.endswith(".xml")])
        if listed != actual:
            problems.append(f"presentation lists {listed} slides but the container holds "
                            f"{actual}")
    return problems
