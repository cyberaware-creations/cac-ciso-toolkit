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

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "scripts"))
import pptx_writer as PX  # noqa: E402

INK = "#14171C"
LIME = "#EAE7DF"
SLATE = "#666D7C"
WB = "#F6F4EE"
WB_SURF = "#FFFFFF"
WB_LINE = "#D8D3C6"
MUTED = "#4A4F58"

FOOTER = "A Cyber Aware Creation · Not affiliated with NIST"
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
.tile .l{{color:{MUTED};font-size:13px}}
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
@media (max-width:560px){{body{{padding:14px}} h1{{font-size:24px}}
  .tile .n{{font-size:24px}}}}
@media print{{
  body{{background:#fff;padding:0;font-size:11pt}}
  .wrap{{max-width:none}}
  .page{{border:none;border-radius:0;padding:0;margin:0;break-after:page}}
  .page:last-of-type{{break-after:auto}}
  .tile{{border:1px solid #ccc}}
  .note,.tile,ol.decisions li{{break-inside:avoid}}
}}
@page{{size:A4 portrait;margin:18mm 16mm 20mm 16mm}}
"""


def _tiles(headlines: list) -> str:
    if not headlines:
        return ""
    cells = "".join(f'<div class="tile"><span class="n">{esc(h["value"])}</span>'
                    f'<span class="l">{esc(h["label"])}</span></div>' for h in headlines)
    return (f'<div class="tiles">{cells}</div>'
            f'<p class="muted">Every figure above was computed by the skill that owns it and '
            f'read here unchanged. The pack calculates nothing.</p>')


def _decisions(decisions: list) -> str:
    if not decisions:
        return f'<div class="ph">{esc(PLACEHOLDER)}</div>'
    items = "".join(
        f'<li>{esc(d["text"])}'
        f'<span class="from">from: {esc(", ".join(d["sections"]))}</span></li>'
        for d in decisions)
    return f'<ol class="decisions">{items}</ol>'


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
    return (f'<div class="page"><h2>{esc(title)}</h2>'
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
    return (f'<div class="page"><h2>Provenance</h2>'
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
        f'<div class="page"><h1>{esc(pack["client"] or "Security board pack")}</h1>'
        f'<p class="sub">{esc(pack["period"])} · {esc(audience)} · '
        f'as at {esc(pack["asOf"])}</p>'
        f'<h2>Executive through-line</h2>{through}{_tiles(pack["headlines"])}</div>'
        f'<div class="page"><h2>Decisions</h2>'
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

    tl = pack["throughLine"]
    deck.add("Executive through-line",
             [(tl["executiveSummary"] if tl else PLACEHOLDER, 1400, False,
               PX.INK if tl else PX.MUTED, False)],
             eyebrow=eyebrow)

    if pack["headlines"]:
        deck.add("This quarter, in figures",
                 [(f'{h["value"]}  —  {h["label"]}', 1500, False, PX.INK, True)
                  for h in pack["headlines"]]
                 + [("Every figure was computed by the skill that owns it and read here "
                     "unchanged. The pack calculates nothing.", 1000, False, PX.MUTED,
                     False)],
                 eyebrow=eyebrow)

    if pack["decisions"]:
        # A board deck that runs a decision onto a second slide loses the second half of it.
        for i in range(0, len(pack["decisions"]), 5):
            chunk = pack["decisions"][i:i + 5]
            more = "" if len(pack["decisions"]) <= 5 else f" ({i // 5 + 1})"
            deck.add(f"Decisions{more}",
                     [(d["text"], 1300, False, PX.INK, True) for d in chunk],
                     eyebrow=eyebrow)
    else:
        deck.add("Decisions", [(PLACEHOLDER, 1300, False, PX.MUTED, False)],
                 eyebrow=eyebrow)

    for section in pack["sections"]:
        title = SECTION_TITLE.get(section["section"], section["section"])
        paras = [(section["executiveSummary"] or PLACEHOLDER, 1300, False,
                  PX.INK if section["executiveSummary"] else PX.MUTED, False)]
        if section["section"] == "incident":
            paras.append((NOT_LEGAL, 1000, False, PX.MUTED, False))
        deck.add(title, paras, eyebrow=eyebrow)
        for key, items in section["items"].items():
            if not items:
                continue
            entries = list(items.items())
            for i in range(0, len(entries), 4):
                chunk = entries[i:i + 4]
                deck.add(f'{title} — {ITEM_LABEL.get(key, key)}',
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
