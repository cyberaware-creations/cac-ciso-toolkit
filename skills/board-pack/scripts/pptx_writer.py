#!/usr/bin/env python3
"""pptx_writer.py — write a real .pptx from the standard library.

A .pptx is a Zip container of Open Packaging Convention parts: some XML describing the
presentation, one XML part per slide, and a web of relationship files pointing at each other.
`zipfile` and string formatting are enough to produce one, so this ships with no dependency —
which is the constraint the whole toolkit runs under.

**What this is not.** It is not a PowerPoint implementation. It writes exactly the shapes this
pack needs — a title, a body of paragraphs, and a two-column figure strip — using explicit
EMU geometry rather than layout placeholders, because a placeholder inherits from a master and
a master is where fidelity across PowerPoint, Keynote and Google Slides goes wrong. Everything
here is positioned absolutely and styled inline, which is uglier XML and far more predictable.

**The limit worth stating.** Structural validity is testable and is tested: the container
opens, every declared part exists, every relationship resolves, every part is well-formed XML,
and the content types cover every part. How it *renders* is not testable from here. Open the
example once in the application you care about before sending a pack to a board.

Units: EMU (English Metric Units), 914400 per inch. Slides are 13.333 x 7.5 inches — 16:9.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
import zipfile
from xml.sax.saxutils import escape

EMU_PER_INCH = 914400
SLIDE_W = int(13.333 * EMU_PER_INCH)
SLIDE_H = int(7.5 * EMU_PER_INCH)

INK = "14171C"
MUTED = "4A4F58"
LINE = "D8D3C6"
SURFACE = "F6F4EE"
ACCENT = "666D7C"

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
    marker = ('<a:buFont typeface="Arial"/><a:buChar char="•"/>' if bullet
              else "<a:buNone/>")
    indent = ' marL="228600" indent="-228600"' if bullet else ' marL="0" indent="0"'
    return (f'<a:p><a:pPr{indent}><a:spcAft><a:spcPts val="{space_after}"/></a:spcAft>'
            f'{marker}</a:pPr>{_run(text, size, bold, colour)}</a:p>')


def _textbox(shape_id: int, name: str, x: int, y: int, cx: int, cy: int,
             paragraphs: str) -> str:
    return (f'<p:sp><p:nvSpPr><p:cNvPr id="{shape_id}" name="{esc(name)}"/>'
            f'<p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr>'
            f'<p:spPr><a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>'
            f'<a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:noFill/></p:spPr>'
            f'<p:txBody><a:bodyPr wrap="square" lIns="0" tIns="0" rIns="0" bIns="0">'
            f'<a:normAutofit/></a:bodyPr><a:lstStyle/>{paragraphs}</p:txBody></p:sp>')


def _rect(shape_id: int, x: int, y: int, cx: int, cy: int, fill: str) -> str:
    return (f'<p:sp><p:nvSpPr><p:cNvPr id="{shape_id}" name="Rule {shape_id}"/>'
            f'<p:cNvSpPr/><p:nvPr/></p:nvSpPr>'
            f'<p:spPr><a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>'
            f'<a:prstGeom prst="rect"><a:avLst/></a:prstGeom>'
            f'<a:solidFill><a:srgbClr val="{fill}"/></a:solidFill>'
            f'<a:ln><a:noFill/></a:ln></p:spPr>'
            f'<p:txBody><a:bodyPr/><a:lstStyle/><a:p/></p:txBody></p:sp>')


def slide_xml(shapes: str) -> str:
    return (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            f'<p:sld xmlns:a="{NS_A}" xmlns:r="{NS_R}" xmlns:p="{NS_P}">'
            f'<p:cSld><p:spTree>'
            f'<p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>'
            f'<p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/>'
            f'<a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>'
            f'{shapes}</p:spTree></p:cSld>'
            f'<p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sld>')


class Deck:
    """Accumulates slides, then writes the container.

    Slide geometry is a left margin, a title band, a rule, and a body. Every slide uses it,
    so a reader never has to re-find where things are.
    """

    MARGIN = int(0.75 * EMU_PER_INCH)
    BODY_W = SLIDE_W - 2 * MARGIN
    TITLE_Y = int(0.6 * EMU_PER_INCH)
    RULE_Y = int(1.45 * EMU_PER_INCH)
    BODY_Y = int(1.75 * EMU_PER_INCH)
    FOOT_Y = int(6.85 * EMU_PER_INCH)

    def __init__(self, footer: str):
        self.slides = []
        self.footer = footer

    def add(self, title: str, paragraphs: list, eyebrow: str = "") -> None:
        """paragraphs: list of (text, size, bold, colour, bullet) tuples."""
        shapes = []
        sid = 2
        if eyebrow:
            shapes.append(_textbox(sid, "Eyebrow", self.MARGIN,
                                   int(0.32 * EMU_PER_INCH), self.BODY_W,
                                   int(0.3 * EMU_PER_INCH),
                                   _para(eyebrow, 1100, False, MUTED, 0)))
            sid += 1
        shapes.append(_textbox(sid, "Title", self.MARGIN, self.TITLE_Y, self.BODY_W,
                               int(0.8 * EMU_PER_INCH),
                               _para(title, 2600, True, INK, 0)))
        sid += 1
        shapes.append(_rect(sid, self.MARGIN, self.RULE_Y, self.BODY_W, 12700, LINE))
        sid += 1
        body = "".join(_para(t, size, bold, colour, 700, bullet)
                       for t, size, bold, colour, bullet in paragraphs)
        shapes.append(_textbox(sid, "Body", self.MARGIN, self.BODY_Y, self.BODY_W,
                               self.FOOT_Y - self.BODY_Y - int(0.2 * EMU_PER_INCH), body))
        sid += 1
        shapes.append(_textbox(sid, "Footer", self.MARGIN, self.FOOT_Y, self.BODY_W,
                               int(0.3 * EMU_PER_INCH),
                               _para(self.footer, 900, False, MUTED, 0)))
        self.slides.append(slide_xml("".join(shapes)))

    # --- the container --------------------------------------------------------

    def _content_types(self) -> str:
        overrides = "".join(
            f'<Override PartName="/ppt/slides/slide{i + 1}.xml" ContentType="{CT_SLIDE}"/>'
            for i in range(len(self.slides)))
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
                      for i in range(len(self.slides)))
        return (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                f'<p:presentation xmlns:a="{NS_A}" xmlns:r="{NS_R}" xmlns:p="{NS_P}">'
                f'<p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="rId1"/>'
                f'</p:sldMasterIdLst>'
                f'<p:sldIdLst>{ids}</p:sldIdLst>'
                f'<p:sldSz cx="{SLIDE_W}" cy="{SLIDE_H}"/>'
                f'<p:notesSz cx="{SLIDE_H}" cy="{SLIDE_W}"/></p:presentation>')

    def _presentation_rels(self) -> str:
        rels = ['<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/'
                'officeDocument/2006/relationships/slideMaster" '
                'Target="slideMasters/slideMaster1.xml"/>']
        for i in range(len(self.slides)):
            rels.append(f'<Relationship Id="rId{i + 2}" '
                        f'Type="http://schemas.openxmlformats.org/officeDocument/2006/'
                        f'relationships/slide" Target="slides/slide{i + 1}.xml"/>')
        rels.append(f'<Relationship Id="rId{len(self.slides) + 2}" '
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
        for i, slide in enumerate(self.slides):
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


def verify(path: str) -> list:
    """Structural check of a written .pptx. Returns a list of problems; empty means sound.

    This is what can honestly be tested without an office application: the container opens,
    every part is well-formed XML, every declared part exists, every relationship target
    resolves, and every part has a content type. Rendering fidelity is not covered — open it
    once in the application you care about.
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
