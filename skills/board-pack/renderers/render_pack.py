#!/usr/bin/env python3
"""render_pack.py — turn the assembled pack model into the two deliverables.

Print-ready HTML (which paginates to PDF through any browser's print dialog) and a real
`.pptx`. Both are built from the same content model, so they cannot drift: if a section is
missing from one it is missing from both, and a placeholder in one is a placeholder in the
other.

This renderer writes **no board prose**. Every sentence in the output came from a producer's
`*.board.json` or from the through-line sidecar, both composed by `ciso-board-translation`.
Where a slot is unfilled it renders a marked placeholder — visibly unfinished beats
plausibly wrong, because only one of those gets noticed.

Usage:
  python3 render_pack.py --in pack.json [--html board-pack.html] [--pptx board-pack.pptx]
"""
from __future__ import annotations

import argparse
import html
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
# The renderer's own directory first: `cac_graphics.py` is vendored beside this file so a
# skill directory runs on its own, and the caller's cwd is not ours to assume.
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(_HERE, "..", "scripts"))
import cac_graphics as G  # noqa: E402
import pptx_writer as PX  # noqa: E402

# Four of these follow the brand and are rebound by apply_brand(); the rest are page
# furniture the brand has no opinion about. They are declared here with their CAC values
# so this module reads the same whether or not a client override is in play.
INK = G._INK
MUTED = G._MUTED
WB = G._BG
# Patina is the brand accent. It appears on the cover, on rules and on the section
# kickers, and nowhere a reader could mistake it for a measurement.
PATINA = G._PATINA

LIME = "#EAE7DF"     # the warm off-white the cover sets on ink
SLATE = "#666D7C"    # placeholder and note borders
WB_SURF = "#FFFFFF"
WB_LINE = "#D8D3C6"

LOCKUP = G.brand()["mark"]

FOOTER = G.footer()
NOT_LEGAL = ("Not legal advice. The incident record structures and documents a materiality "
             "determination; it does not make one. Involve counsel on the determination and "
             "on any filing.")
PLACEHOLDER = ("Not supplied. Compose this with the ciso-board-translation skill and re-run "
               "the assembler — this pack does not write board prose.")

SECTION_TITLE = {
    "posture": "Framework posture",
    "risk": "Risk",
    "metrics": "Metrics",
    "exceptions": "Accepted risks and exceptions",
    "incident": "Incidents",
}
ITEM_LABEL = {
    "risks": "Risks", "themes": "Themes", "gaps": "Outcomes short of target",
    "metrics": "Metrics", "acceptances": "Accepted risks", "exceptions": "Exceptions",
    "incidents": "Incidents",
}


def esc(s) -> str:
    return html.escape("" if s is None else str(s))


def apply_brand(brand: dict) -> None:
    """Apply the pack's brand block to the library and to this renderer's chrome.

    The library floors what the library can see: text on white, a data mark against its
    surface, a bar against its own track. It cannot see the cover, because the cover sets
    a warm off-white on the *ink* — a pairing that exists only here. So this function
    checks that pairing itself rather than assuming a brand that passed the library's
    floors is safe everywhere it will be used.
    """
    global INK, MUTED, WB, PATINA, LOCKUP, FOOTER
    G.set_brand(brand or {})          # raises BrandError on a palette that misses the floors
    INK, MUTED, WB, PATINA = G._INK, G._MUTED, G._BG, G._PATINA
    LOCKUP, FOOTER = G.brand()["mark"], G.footer()

    problems = []
    if G.contrast(LIME, INK) < 4.5:
        problems.append("the cover sets %s on ink %s at %.2f:1, and the cover is body text"
                        % (LIME, INK, G.contrast(LIME, INK)))
    if G.contrast(PATINA, INK) < 3.0:
        problems.append("the cover eyebrow and kicker set patina %s on ink %s at %.2f:1"
                        % (PATINA, INK, G.contrast(PATINA, INK)))
    if problems:
        G.set_brand()                 # never leave a half-applied brand behind
        raise G.BrandError("the brand override was refused by the pack chrome:\n  - "
                           + "\n  - ".join(problems))

    PX.apply_brand(INK, MUTED, PATINA, WB, LOCKUP)


# --- HTML ---------------------------------------------------------------------

def _css() -> str:
    return f"""
*{{box-sizing:border-box}}
body{{margin:0;padding:24px;background:{WB};color:{INK};
  font-family:Manrope,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
  font-size:15px;line-height:1.55}}
.wrap{{max-width:1100px;margin:0 auto}}
h1,h2,h3{{font-family:'Space Grotesk',Manrope,sans-serif;margin:0 0 8px;line-height:1.25}}
h1{{font-size:30px}} h2{{font-size:21px;margin-top:0}} h3{{font-size:16px;margin-top:18px}}
.sub{{color:{MUTED};margin:0 0 20px}}
.page{{background:{WB_SURF};border:1px solid {WB_LINE};border-radius:10px;
  padding:22px 24px;margin:18px 0;min-width:0}}
.lede{{font-size:17px;line-height:1.6}}
.tiles{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;
  margin:16px 0}}
.tile{{background:{WB};border:1px solid {WB_LINE};border-radius:10px;padding:14px;
  min-width:0}}
.tile .n{{font-family:'Space Grotesk',sans-serif;font-size:28px;font-weight:600;
  display:block;line-height:1.1}}
/* Block, not inline: the label wraps to two lines on a narrow tile and the chip
   below it has to start its own, or a figure reads "…open from: Incidents". */
.tile .l{{color:{MUTED};font-size:13px;display:block}}
.tile .src{{display:inline-block;margin-top:8px;padding:1px 9px;border-radius:999px;
  background:{LIME};color:{MUTED};font-size:11.5px;font-weight:600}}
ol.decisions{{margin:8px 0 0;padding-left:22px}}
ol.decisions li{{margin:0 0 12px}}
.from{{color:{MUTED};font-size:12.5px;display:block;margin-top:3px}}
dl{{margin:6px 0 0}} dt{{font-weight:600;margin-top:10px}}
dd{{margin:2px 0 0 0;color:{INK}}}
.muted{{color:{MUTED}}}
.ph{{background:{LIME};border:1px dashed {SLATE};border-radius:8px;padding:12px 14px;
  color:{MUTED}}}
.note{{background:{LIME};border:1px solid {WB_LINE};border-left:4px solid {SLATE};
  border-radius:8px;padding:12px 16px;margin:16px 0;color:{MUTED};font-size:14px}}
.note strong{{color:{INK};display:block;margin-bottom:4px}}
.note p{{margin:0}}
footer{{color:{MUTED};font-size:12.5px;margin-top:28px;padding-top:14px;
  border-top:1px solid {WB_LINE}}}

/* CAC chrome. A board pack is a document somebody opens once and reads front to
   back, so unlike the producers' working views this one earns a full cover page.
   Ink ground, patina spark, and the meta a reader checks before anything else.
   Colour is forced through the print path: a cover that prints as a white
   rectangle is not a cover. */
.cover{{background:{INK};color:{LIME};border-radius:10px;padding:44px 40px 38px;
  margin:0 0 18px;min-height:62vh;display:flex;flex-direction:column;
  break-after:page;
  -webkit-print-color-adjust:exact;print-color-adjust:exact}}
.cover .lockup{{display:flex;align-items:center;gap:10px;
  font-family:'Space Grotesk',Manrope,sans-serif;font-weight:600;font-size:13px;
  letter-spacing:.02em}}
.cover .eyebrow{{color:{PATINA};font-size:11px;font-weight:700;letter-spacing:.14em;
  text-transform:uppercase;margin:40px 0 8px}}
.cover h1{{color:{LIME};font-size:38px;margin:0}}
.cover .rule{{border:0;border-top:2px solid {PATINA};width:64px;margin:20px 0 0}}
.cover .meta{{margin-top:auto;padding-top:32px;display:grid;
  grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:16px 22px}}
.cover .meta .k{{display:block;color:{PATINA};font-size:11px;font-weight:700;
  letter-spacing:.12em;text-transform:uppercase}}
.cover .meta .v{{display:block;font-size:15px;margin-top:4px}}
.spark{{width:9px;height:9px;border-radius:2px;background:{PATINA};flex:0 0 auto}}

/* The section kicker: the same lockup, compressed to a strip, so every page of a
   pack that has been split apart and pasted into something else still says what
   it is and which section it came from. */
.band{{background:{INK};color:{LIME};border-radius:10px;padding:12px 16px;
  margin:0 0 18px;display:flex;align-items:center;gap:10px;flex-wrap:wrap;
  -webkit-print-color-adjust:exact;print-color-adjust:exact}}
.band .lockup{{font-family:'Space Grotesk',Manrope,sans-serif;font-weight:600;
  font-size:13px;letter-spacing:.02em}}
.band .kicker{{margin-left:auto;color:{PATINA};font-size:11px;font-weight:700;
  letter-spacing:.12em;text-transform:uppercase}}

/* The legend states what a coloured figure means, once. Without it a reader has to
   infer the contract from the figures. */
.legend{{display:flex;gap:14px;flex-wrap:wrap;color:{MUTED};font-size:12px;
  margin:12px 0 0}}
.legend span{{display:flex;align-items:center;gap:6px}}
.legend i{{width:14px;height:10px;border-radius:2px;display:block;flex:0 0 auto}}

@media (max-width:560px){{body{{padding:14px}} h1{{font-size:24px}}
  .cover{{padding:28px 22px 26px}} .cover h1{{font-size:28px}}
  .tile .n{{font-size:24px}}}}
@media print{{
  body{{background:#fff;padding:0;font-size:11pt}}
  .wrap{{max-width:none}}
  .page{{border:none;border-radius:0;padding:0;margin:0;break-after:page}}
  .page:last-of-type{{break-after:auto}}
  /* A cover that prints as a band across the top of an otherwise blank sheet is
     not a cover. 100vh is the page content box in paged media, so the ink fills
     what @page left it — and no more, or the overflow costs a blank page. */
  .cover{{border-radius:0;margin:0;min-height:100vh;padding:30mm 14mm 20mm;
    break-after:page;
    -webkit-print-color-adjust:exact;print-color-adjust:exact}}
  .band{{-webkit-print-color-adjust:exact;print-color-adjust:exact;
    break-inside:avoid;break-after:avoid}}
  .tile{{border:1px solid #ccc}}
  .note,.tile,ol.decisions li{{break-inside:avoid}}
}}
@page{{size:A4 portrait;margin:18mm 16mm 20mm 16mm}}
"""


def _cover(pack: dict, audience: str) -> str:
    """The cover page. Chrome and the four facts a reader checks before anything else.

    Nothing here is composed: every field is a manifest value carried through the
    assembler, so a cover cannot say something the pack does not.
    """
    meta = [("Client", pack["client"]), ("Period", pack["period"]),
            ("Audience", audience), ("As at", pack["asOf"])]
    cells = "".join(f'<div><span class="k">{esc(k)}</span>'
                    f'<span class="v">{esc(v) if v else "—"}</span></div>'
                    for k, v in meta)
    return (f'<div class="cover">'
            f'<div class="lockup"><span class="spark"></span>{esc(LOCKUP)}</div>'
            f'<p class="eyebrow">Security board pack</p>'
            f'<h1>{esc(pack["client"] or "Security board pack")}</h1>'
            f'<hr class="rule">'
            f'<div class="meta">{cells}</div></div>')


def _band(kicker: str) -> str:
    """The section kicker: ink strip, patina spark, lockup, the page's own name."""
    return (f'<div class="band"><span class="spark"></span>'
            f'<span class="lockup">{esc(LOCKUP)}</span>'
            f'<span class="kicker">{esc(kicker)}</span></div>')


def _legend() -> str:
    """What a coloured figure means.

    The neutral swatch is the body colour and not the library's MEASURE blue, because
    the body colour is what an unbanded figure actually renders in here — a legend that
    showed a colour the page never uses would be a key to a different document.
    """
    items = [(INK, "no band declared"),
             (G._RAG["good"]["fill"], "good"),
             (G._RAG["medium"]["fill"], "medium"),
             (G._RAG["high"]["fill"], "high"),
             (G._RAG["critical"]["fill"], "critical")]
    inner = "".join(f'<span><i style="background:{c}"></i>{esc(t)}</span>'
                    for c, t in items)
    return f'<div class="legend">{inner}</div>'


def _tiles(headlines: list) -> str:
    if not headlines:
        return ""
    cells = []
    for h in headlines:
        # A figure is coloured only where the section that computed it declared a band.
        # `"sev" in h` is the whole test, and it is the only test: the assembler writes
        # no key at all where nothing was declared, and never bands a count of nothing.
        # Neither of those judgements is remade here — a renderer that decided a
        # severity would be a second opinion able to disagree with the section it sits
        # above. `text` rather than `fill`, so the figure clears AA on a light card.
        colour = G._sev_colour(h["sev"], "text") if "sev" in h else INK
        cells.append(
            f'<div class="tile">'
            f'<span class="n" style="color:{colour}">{esc(h["value"])}</span>'
            f'<span class="l">{esc(h["label"])}</span>'
            f'<span class="src">from: '
            f'{esc(SECTION_TITLE.get(h["section"], h["section"]))}</span></div>')
    return (f'<div class="tiles">{"".join(cells)}</div>{_legend()}'
            f'<p class="muted">Every figure above was computed by the skill that owns it and '
            f'read here unchanged. The pack calculates nothing. Colour follows the same '
            f'rule: a figure is banded only where its own section declared a band, so a '
            f'population — and a count of nothing — stays in the body colour.</p>')


def split_by_altitude(decisions: list) -> tuple:
    """(what the board decides, what management should just do).

    An ask marked `management` is one the producer said does not need a board. Everything
    else — `board`, or unmarked — stays in front of the board. Unmarked lands there on
    purpose: the assembler never infers an altitude, and of the two ways to be wrong, a
    board reading an ask it did not need costs a minute, while a board decision filed away
    as a management action is a decision nobody takes.
    """
    board = [d for d in decisions if d.get("altitude") != "management"]
    management = [d for d in decisions if d.get("altitude") == "management"]
    return board, management


def _decision_items(decisions: list) -> str:
    return "".join(
        f'<li>{esc(d["text"])}'
        f'<span class="from">from: {esc(", ".join(d["sections"]))}</span></li>'
        for d in decisions)


def _decisions(decisions: list) -> str:
    board, management = split_by_altitude(decisions)
    if not decisions:
        return f'<div class="ph">{esc(PLACEHOLDER)}</div>'
    out = (f'<ol class="decisions">{_decision_items(board)}</ol>' if board
           else f'<div class="ph">{esc(PLACEHOLDER)}</div>')
    if management:
        out += (f'<h2>Management actions — not for board decision</h2>'
                f'<p class="sub">Recorded here so the board can see they are owned, and '
                f'ask about them if it wants to. Each was marked by the section that raised '
                f'it as something management should do rather than something the board must '
                f'decide. An ask nobody marked stays in the list above.</p>'
                f'<ol class="decisions">{_decision_items(management)}</ol>')
    return out


def _section_page(section: dict) -> str:
    title = SECTION_TITLE.get(section["section"], section["section"])
    summary = (f'<p class="lede">{esc(section["executiveSummary"])}</p>'
               if section["executiveSummary"]
               else f'<div class="ph">{esc(PLACEHOLDER)}</div>')
    blocks = []
    for key, items in section["items"].items():
        if not items:
            continue
        rows = "".join(f'<dt>{esc(k)}</dt><dd>{esc(v)}</dd>' for k, v in items.items())
        blocks.append(f'<h3>{esc(ITEM_LABEL.get(key, key))}</h3><dl>{rows}</dl>')
    body = "".join(blocks) or '<p class="muted">No items in this section.</p>'
    legal = (f'<div class="note"><strong>Not legal advice</strong><p>{esc(NOT_LEGAL)}</p>'
             f'</div>' if section["section"] == "incident" else "")
    as_of = (f' · as at {esc(section["asOf"])}' if section["asOf"] else "")
    return (f'<div class="page">{_band(title)}<h2>{esc(title)}</h2>'
            f'<p class="sub">{esc(section["itemCount"])} items{as_of}</p>'
            f'{summary}{legal}{body}</div>')


def _provenance(pack: dict) -> str:
    prov = pack["provenance"]
    sources = "".join(
        f'<dt>{esc(SECTION_TITLE.get(s["section"], s["section"]))}</dt>'
        f'<dd class="muted">{esc(s["translations"] or "no sidecar")}'
        + (f' · {esc(s["store"])}' if s.get("store") else "") + "</dd>"
        for s in prov["sources"])
    notes = prov["missing"] + prov["warnings"]
    note_list = ("".join(f"<li>{esc(n)}</li>" for n in notes)
                 or "<li>Nothing was missing.</li>")
    return (f'<div class="page">{_band("Provenance")}<h2>Provenance</h2>'
            f'<p class="sub">What this pack was built from, and what was not there.</p>'
            f'<h3>Sources</h3><dl>{sources}</dl>'
            f'<h3>Noted</h3><ul class="list">{note_list}</ul>'
            f'<div class="note"><strong>How to read a gap here</strong>'
            f'<p>A section with no sidecar renders a marked placeholder rather than an '
            f'invented sentence, and appears in the list above. Nothing in this pack was '
            f'written to fill a hole.</p></div></div>')


def build_html(pack: dict) -> str:
    tl = pack["throughLine"]
    through = (f'<p class="lede">{esc(tl["executiveSummary"])}</p>' if tl
               else f'<div class="ph">{esc(PLACEHOLDER)}</div>')
    audience = ("Board" if pack["audience"] == "board" else "Audit committee")
    pages = "".join(_section_page(s) for s in pack["sections"])
    body = (
        _cover(pack, audience)
        + f'<div class="page">{_band("Executive through-line")}'
        f'<h2>Executive through-line</h2>'
        f'<p class="sub">{esc(pack["period"])} · {esc(audience)} · '
        f'as at {esc(pack["asOf"])}</p>'
        f'{through}{_tiles(pack["headlines"])}</div>'
        f'<div class="page">{_band("Decisions")}<h2>Decisions</h2>'
        f'<p class="sub">Consolidated across every section, in reading order. '
        f'Duplicates merged only where the wording matched.</p>'
        f'{_decisions(pack["decisions"])}</div>'
        f'{pages}{_provenance(pack)}'
        f'<footer>{esc(pack["client"])} · {esc(FOOTER)} · '
        f'generated {esc(pack["asOf"])}</footer>')
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{esc(pack["client"])} — security board pack</title>'
            f'<style>{_css()}</style></head><body><div class="wrap">{body}</div>'
            f'</body></html>')


# --- PPTX ---------------------------------------------------------------------

def build_pptx(pack: dict, path: str) -> None:
    audience = "Board" if pack["audience"] == "board" else "Audit committee"
    eyebrow = f'{pack["client"]} · {pack["period"]} · {audience}'
    deck = PX.Deck(f'{FOOTER} · as at {pack["asOf"]}')

    # The cover, before anything else. The deck inserts it at slide 1 however late
    # it is called, but calling it first keeps the reading order of this function
    # the same as the reading order of the deck.
    deck.cover("Security board pack",
               [("Client", pack["client"]), ("Period", pack["period"]),
                ("Audience", audience), ("As at", pack["asOf"])],
               eyebrow="Quarterly security board pack")

    tl = pack["throughLine"]
    deck.add("Executive through-line",
             [(tl["executiveSummary"] if tl else PLACEHOLDER, 1400, False,
               PX.INK if tl else PX.MUTED, False)],
             eyebrow=eyebrow)

    if pack["headlines"]:
        # Tiles rather than bullets, so a figure can carry the band its producer
        # declared. A figure with no band renders in ink and takes no rule and no
        # band word -- the deck decides severity exactly as little as the HTML does.
        deck.figures("This quarter, in figures", pack["headlines"],
                     eyebrow=eyebrow,
                     note="Every figure was computed by the skill that owns it and "
                          "read here unchanged. The pack calculates nothing.")

    board_asks, management_asks = split_by_altitude(pack["decisions"])
    if board_asks:
        # A board deck that runs a decision onto a second slide loses the second half of it.
        for i in range(0, len(board_asks), 5):
            chunk = board_asks[i:i + 5]
            more = "" if len(board_asks) <= 5 else f" ({i // 5 + 1})"
            deck.add(f"Decisions{more}",
                     [(d["text"], 1300, False, PX.INK, True) for d in chunk],
                     eyebrow=eyebrow)
    else:
        deck.add("Decisions", [(PLACEHOLDER, 1300, False, PX.MUTED, False)],
                 eyebrow=eyebrow)

    # Management actions travel with the deck but after the decisions, and never mixed into
    # them. A board asked to decide something management already owns learns to skim the
    # decision slide, which is the one slide it must not skim.
    for i in range(0, len(management_asks), 5):
        chunk = management_asks[i:i + 5]
        more = "" if len(management_asks) <= 5 else f" ({i // 5 + 1})"
        deck.add(f"Management actions — not for board decision{more}",
                 [(d["text"], 1300, False, PX.INK, True) for d in chunk]
                 + [("Marked by the section that raised each one. An ask nobody marked "
                     "stays on the decision slides.", 1000, False, PX.MUTED, False)],
                 eyebrow=eyebrow)

    total_sections = len(pack["sections"])
    for idx, section in enumerate(pack["sections"], start=1):
        title = SECTION_TITLE.get(section["section"], section["section"])
        # The counter, not the title, is the divider's second run: a divider
        # repeating its section's name would collide with that section's own
        # summary slide and trip the no-duplicate-titles check.
        deck.section(title, f"Section {idx} of {total_sections}")
        paras = [(section["executiveSummary"] or PLACEHOLDER, 1300, False,
                  PX.INK if section["executiveSummary"] else PX.MUTED, False)]
        if section["section"] == "incident":
            paras.append((NOT_LEGAL, 1000, False, PX.MUTED, False))
        deck.add(title, paras, eyebrow=eyebrow)
        for key, items in section["items"].items():
            if not items:
                continue
            entries = list(items.items())
            label = ITEM_LABEL.get(key, key)
            # Two failures pulling in opposite directions, both found by opening the deck.
            # "Incidents — Incidents" repeats itself, because that section's only item map is
            # named after the section. But collapsing to plain "Incidents" then collides with
            # the section's own summary slide, and two slides sharing a title is worse than
            # one clumsy title — a deck is navigated by its titles.
            heading = (f"{title} — detail" if label.lower() == title.lower()
                       else f"{title} — {label}")
            for i in range(0, len(entries), 4):
                chunk = entries[i:i + 4]
                part = "" if len(entries) <= 4 else f" ({i // 4 + 1})"
                deck.add(heading + part,
                         [(f"{k}: {v}", 1150, False, PX.INK, True) for k, v in chunk],
                         eyebrow=eyebrow)

    prov = pack["provenance"]
    notes = prov["missing"] + prov["warnings"]
    deck.add("Provenance",
             [("What this pack was built from, and what was not there.", 1200, False,
               PX.MUTED, False)]
             + [(n, 1100, False, PX.INK, True) for n in (notes or ["Nothing was missing."])],
             eyebrow=eyebrow)
    deck.write(path)


# --- CLI ----------------------------------------------------------------------

def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0],
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--in", dest="infile", required=True,
                   help="assemble_pack.py assemble --out JSON")
    p.add_argument("--html", default="board-pack.html")
    p.add_argument("--pptx", default="board-pack.pptx")
    p.add_argument("--no-pptx", action="store_true")
    args = p.parse_args(argv)

    try:
        with open(args.infile, encoding="utf-8") as fh:
            pack = json.load(fh)
    except FileNotFoundError:
        raise SystemExit(f"error: --in file not found: {args.infile}")
    except json.JSONDecodeError as exc:
        raise SystemExit(f"error: --in file {args.infile} is not valid JSON: {exc.msg}")
    for key in ("sections", "decisions", "headlines", "provenance"):
        if key not in pack:
            raise SystemExit(
                f"error: {args.infile} is not an assembled pack (no {key!r} key). "
                f"Produce it with `assemble_pack.py assemble <manifest> --out {args.infile}`.")

    # Before anything is drawn, so the HTML and the deck are branded identically or neither is.
    try:
        apply_brand(pack.get("brand") or {})
    except G.BrandError as exc:
        raise SystemExit(f"error: {exc}")

    doc = build_html(pack)
    with open(args.html, "w", encoding="utf-8") as fh:
        fh.write(doc)
    print(f"wrote {args.html} ({len(doc):,} bytes)")
    print("  Print to PDF from a browser; @page sets A4 portrait and the section breaks.",
          file=sys.stderr)

    if not args.no_pptx:
        build_pptx(pack, args.pptx)
        problems = PX.verify(args.pptx)
        size = os.path.getsize(args.pptx)
        print(f"wrote {args.pptx} ({size:,} bytes)")
        if problems:
            for prob in problems:
                print(f"  PPTX PROBLEM: {prob}", file=sys.stderr)
            return 1
        print("  Structurally verified. Rendering fidelity is not testable from here — open "
              "it once in the application you care about.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
