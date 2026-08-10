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

# A second copy of the assembler's SECTION_TITLE, because a skill directory has to run on
# its own. `vendor` and `ai` were added to the assembler's map and not to this one, so every
# heading naming them on both deliverables read as the bare key — "vendor", "ai" — on a board
# page whose whole claim is that it was written for a board. Nothing failed; it just looked
# unfinished, and no eval assembled a section that would have shown it.
# section-contract.sh asserts the two maps agree, so the next section cannot drift the same way.
SECTION_TITLE = {
    "posture": "Framework posture",
    "risk": "Risk",
    "vendor": "Third parties",
    "ai": "Artificial intelligence",
    "metrics": "Metrics",
    "exceptions": "Accepted risks and exceptions",
    "incident": "Incidents",
}
ITEM_LABEL = {
    "risks": "Risks", "themes": "Themes", "gaps": "Outcomes short of target",
    "metrics": "Metrics", "acceptances": "Accepted risks", "exceptions": "Exceptions",
    "incidents": "Incidents",
    "arrangements": "Arrangements", "deployments": "Deployments",
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
/* Positive risk (GV.RM-07). Patina on the rule, never a RAG fill: the brand system is
   explicit that patina does not signal "safe", and an opportunity is not a low-severity risk.
   The heading carries the word, as every coloured thing in this suite must.

   The heading is INK, not patina. Patina is #2FA98C and measures 2.93:1 on white — the
   responsive suite caught it at 16px/700 the first time this block rendered, which is the
   contrast floor doing exactly its job. The block's identity is carried by the patina rule
   down its left edge, which is a mark rather than text and has no ratio to meet, and by the
   heading's own word. Colour never carries meaning alone here anyway. */
h3.opp-h{{color:{INK}}}
ol.opps{{margin:8px 0 0;padding-left:22px;border-left:2px solid {PATINA};
  padding-top:2px;padding-bottom:2px}}
ol.opps li{{margin:0 0 12px}}
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
/* An applicability conflict. Only the left rule changes: the background/text pair is the
   one `.note` already uses and is already checked for AA, and a border carries no text
   contrast obligation — so this buys visual weight without opening a contrast question. */
.note.alarm{{border-left-color:{G._sev_colour("critical", "text")}}}
.note.alarm strong{{color:{G._sev_colour("critical", "text")}}}
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

/* Escalations. A table rather than cards: five short columns that a reader scans down one
   at a time, and severity is the column they scan. `overflow-x:auto` on the wrapper, so the
   trigger column can keep its full name at 320px instead of wrapping to three lines. */
.esc{{width:100%;border-collapse:collapse;font-size:13.5px;margin:6px 0 0;display:block;
  overflow-x:auto;white-space:nowrap}}
.esc th{{text-align:left;font-size:11px;letter-spacing:.06em;text-transform:uppercase;
  color:{MUTED};border-bottom:1px solid {WB_LINE};padding:0 14px 6px 0;font-weight:600}}
.esc td{{padding:9px 14px 9px 0;border-bottom:1px solid {LIME};vertical-align:top}}
.esc td:last-child{{white-space:normal;min-width:16em}}
.esc .mono{{font-family:ui-monospace,monospace;font-size:12.5px}}
.esc .from{{display:block;color:{MUTED};font-size:11.5px;margin-top:2px}}
.sevdot{{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:7px;
  vertical-align:baseline}}

/* Figures. `flex-wrap` rather than a fixed column count: the marks are fixed-width SVGs,
   so a grid would either clip them on a narrow page or strand them on a wide one. */
.figs{{display:flex;flex-wrap:wrap;gap:18px;margin:18px 0 22px}}
.fig{{margin:0;background:{WB};border:1px solid {WB_LINE};border-radius:10px;
  padding:12px 14px 10px}}
.fig svg{{display:block;max-width:100%}}
.figtitle{{display:block;font-size:12.5px;font-weight:600;color:{INK};
  margin:0 0 8px;display:flex;gap:10px;align-items:baseline;flex-wrap:wrap}}
.figsrc{{font-size:10.5px;font-weight:400;color:{MUTED};font-family:ui-monospace,monospace}}
.fignote{{font-size:11px;color:{MUTED};margin:8px 0 0;max-width:34em}}

@media (max-width:560px){{body{{padding:14px}} h1{{font-size:24px}}
  .cover{{padding:28px 22px 26px}} .cover h1{{font-size:28px}}
  .tile .n{{font-size:24px}} .figs{{gap:12px}}}}
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


def evidence_text(evidence) -> str:
    """`evidence` as a sentence, whichever shape the producer emits.

    CAC-EL-1 §1.3 fixes the six KEYS an escalation carries. **It does not fix the type of
    `evidence`**, and the producers legitimately differ: `risk-register`, `metrics-register`
    and `exceptions-register` emit a structured delta — `{from, to, baseline, detail}` —
    because a band crossing is a movement and both ends of it are the fact, while
    `vendor-register` and `ai-register` emit a finished sentence.

    Both call sites here assumed the dict. A pack carrying a `vendor` or `ai` section
    assembled cleanly and then died in the renderer with `'str' object has no attribute
    'get'` — before writing either deliverable, so a PowerPoint-only request was blocked by
    the HTML path it never asked for. Two sections shipped at v0.41.0 and v0.42.0 could not
    reach a page.

    `attention-surface` hit the same shape on its first live run against all seven producers
    and fixed it the same way: one function, not a check at each call site. That the defect
    recurred in a second consumer is the argument for the function existing at all — and for
    the eval below it, which renders a vendor-only, an AI-only and a seven-section pack to
    BOTH deliverables rather than trusting that the five-section fixture covers them.

    TWINNED with skills/attention-surface/scripts/attention_surface.py::evidence_text, which
    carries the matching note back to here. The same escalation read by the weekly operational
    surface and by this quarterly pack has to produce the same sentence.

    That end declared the twin and this end declared nothing, so a reader editing this function
    had no way to know a second copy existed — and the two drifted (BL-191). On
    `{"from": "", "to": 5}` this function reported no usable evidence while the surface printed
    `" -> 5"`. This reading is the correct one: an empty-string bound means NOT RECORDED,
    decided 2026-08-09, and `not in (None, "")` below is load-bearing, not defensive clutter.
    `0` is a recorded value and both copies keep it.

    tools/check-twins.py now executes both over a shared corpus on every push. Edit the two
    together; a self-test inside one skill cannot see the other copy, by construction.
    """
    if isinstance(evidence, dict):
        detail = str(evidence.get("detail") or "").strip()
        moved = ""
        if evidence.get("from") not in (None, "") and evidence.get("to") not in (None, ""):
            moved = "%s -> %s" % (evidence["from"], evidence["to"])
        baseline = str(evidence.get("baseline") or "").strip()
        bits = [b for b in (detail, moved,
                            ("against %s" % baseline) if baseline else "") if b]
        if not bits:
            # An EMPTY dict is empty evidence, and renders as nothing — there is no shape
            # question to report. A dict with keys this function does not recognise is
            # different: say so, and name them, rather than printing the object. A reader
            # who sees `{'from': 12}` on a board page cannot tell a shape change from a
            # data problem, and neither can the person they ask.
            if not evidence:
                return ""
            return "(structured evidence with no `detail`: %s)" % ", ".join(sorted(evidence))
        return "%s%s" % (bits[0], (" (%s)" % "; ".join(bits[1:])) if bits[1:] else "")
    return str(evidence or "")


def _escalations(escalations: list) -> str:
    """What the producers raised on their own, across every section.

    Rendered as data and not as prose. Every string on this block — the trigger, the evidence
    detail, the date — was written by the skill that owns the clock, the same way a headline
    figure is. That is why it sits in its own block rather than inside `Decisions`: the pack
    promises every *sentence* on the decisions page came from ciso-board-translation, and
    dropping a machine-derived line in among them would quietly break that promise.

    A pack with none says so, because an empty escalation list and a pack that could not read
    one are different states, and only one of them is good news.
    """
    if not escalations:
        return ('<p class="note">Nothing escalated. No section reported a band crossing, a '
                'sustained drift, a long dwell over appetite, or a lapsed acceptance.</p>')
    rows = ""
    for e in escalations:
        ev = evidence_text(e.get("evidence"))
        colour = G._sev_colour(e["severity"], "text")
        rows += (
            f'<tr><td><span class="sevdot" style="background:{colour}"></span>'
            f'{esc(e["severity"])}</td>'
            f'<td class="mono">{esc(e["subjectRef"])}</td>'
            f'<td>{esc(SECTION_TITLE.get(e.get("section"), e.get("section", "")))}</td>'
            f'<td class="mono">{esc(e["trigger"])}</td>'
            f'<td>{esc(ev)}'
            f'<span class="from">since {esc(e.get("since") or "—")}</span></td></tr>')
    return (f'<table class="esc"><thead><tr><th>Severity</th><th>Ref</th><th>Section</th>'
            f'<th>Trigger</th><th>What fired it</th></tr></thead><tbody>{rows}</tbody></table>'
            f'<p class="note">Each line was derived by the skill that owns the clock and read '
            f'here unchanged — the pack raises none of these itself. They are not decisions: '
            f'nothing above has been translated for a board or asks it to act. They are what '
            f'changed for the worse without anyone being asked.</p>')


def _conflicts(conflicts: list) -> str:
    """Where the applicability profile and this pack's own records disagree.

    Its own page, before the through-line, because of what it is: not a finding inside a
    section but a statement that two parts of this document describe different perimeters.
    A reader who stops after the executive summary must still have passed it.

    Renders nothing at all when there are none — and that silence is correct here, unlike
    the escalations block which announces an empty list. "No section escalated" is a real
    result about the period. "The profile and the records agree" is not a result; it is the
    ordinary state, and a panel asserting it on every clean pack would train a reader to
    skip the place the alarm appears.
    """
    if not conflicts:
        return ""
    rows = ""
    for c in conflicts:
        rows += (f'<tr><td class="mono">{esc(c.get("id") or "—")}</td>'
                 f'<td class="mono">{esc(c.get("regime") or "—")}</td>'
                 f'<td class="mono">{esc(c["flag"])}</td>'
                 f'<td>{esc(c["sentence"])}</td></tr>')
    n = len(conflicts)
    return (
        f'<div class="page">{_band("Applicability conflict")}'
        f'<h2>The profile and the records disagree</h2>'
        f'<p class="sub">Read this before the rest of the pack.</p>'
        f'<div class="note alarm"><strong>'
        f'{n} record{"" if n == 1 else "s"} {"is" if n == 1 else "are"} tracked against a '
        f'regime the applicability profile declares does not apply.</strong>'
        f'<p>The disclosure clocks below were computed anyway. A profile narrows the default '
        f'question set; it does not overrule an assessor who opened a clock in front of the '
        f'evidence. Both readings are therefore still in this document, and one of them is '
        f'wrong — resolve it in the profile or in the records before relying on this pack.</p>'
        f'</div>'
        f'<table class="esc"><thead><tr><th>Record</th><th>Regime</th><th>Flag</th>'
        f'<th>The disagreement</th></tr></thead><tbody>{rows}</tbody></table>'
        f'<p class="note">Reported by the section that owns the clock and read here '
        f'unchanged. This pack raised none of it and resolved none of it: choosing a side '
        f'would be the pack overruling either the organisation\'s declaration or its own '
        f'incident record, and it is entitled to do neither.</p></div>')


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


def _figure(fig: dict) -> str:
    """One chart, drawn from the series the assembler read out of its producer.

    The mark is chosen by `kind` and nothing else. A renderer that inspected the numbers to
    decide what to draw would be making a judgement about the data — which shape suits it,
    whether a band is worth colouring — and that judgement belongs to the section that owns
    the facts, not to the thing painting them.
    """
    kind = fig.get("kind")
    if kind == "bar":
        items = [(s["label"], s["value"]) for s in fig.get("series") or []]
        svg = G.bar_chart(items)
    elif kind == "band-mix":
        # One period, so a stacked bar reads as a composition rather than a trend. Segments
        # carrying `sev` make it a RAG stack; a segment without one — `expired`, which is a
        # lifecycle terminus and not a severity — is drawn unassessed by the library rather
        # than given a band colour it was never assigned.
        segments = [{"value": s["value"], "label": s["label"],
                     **({"sev": s["sev"]} if "sev" in s else {})}
                    for s in fig.get("series") or [] if s["value"]]
        svg = G.stacked_bar([{"label": "", "segments": segments}])
    elif kind == "bullet":
        thr = fig.get("threshold") or {}
        direction = fig.get("direction") or "higher-better"
        svg = G.bullet(fig["value"], thr.get("target"),
                       G.zones_from_threshold(thr, direction),
                       direction=direction, unit=fig.get("unit") or "")
    else:
        return ""
    if not svg:
        return ""
    note = (f'<figcaption class="fignote">{esc(fig["note"])}</figcaption>'
            if fig.get("note") else "")
    # `source` names the producer field every number came from. It is printed, not hidden in
    # a comment, because "the pack computes nothing" is a claim a reader should be able to
    # check rather than take on trust.
    return (f'<figure class="fig"><figcaption class="figtitle">{esc(fig["title"])}'
            f'<span class="figsrc">{esc(fig["source"])}</span></figcaption>'
            f'{svg}{note}</figure>')


def _figures_for(section_name: str, charts: list) -> str:
    drawn = [_figure(f) for f in charts if f.get("section") == section_name]
    drawn = [d for d in drawn if d]
    if not drawn:
        return ""
    return f'<div class="figs">{"".join(drawn)}</div>'


def _section_page(section: dict, charts: list = ()) -> str:
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
    # Figures sit after the summary and before the items: the summary says what happened,
    # the figures show the shape of it, and the items are the detail a reader drops into
    # only if the first two raised a question.
    figs = _figures_for(section["section"], charts)
    return (f'<div class="page">{_band(title)}<h2>{esc(title)}</h2>'
            f'<p class="sub">{esc(section["itemCount"])} items{as_of}</p>'
            f'{summary}{legal}{figs}{body}{_opportunities(section)}</div>')


def _cites_display(cites: str) -> str:
    """`goal:Close the Dublin year` -> `goal: Close the Dublin year`.

    The section contract stores a citation as `goal:<declared goal>` or
    `crown-jewel:<system>` — a tagged value, written the way a machine reads it. That string
    was being printed onto a board slide verbatim, so a reader saw `goal:Close the Dublin
    authorisation year`, which looks like a typo rather than a field name.

    Only the separator is touched. The tag and the declared goal are the business's own
    words and are printed back unaltered — a citation is a receipt, and a renderer that
    tidied its wording would be editing the thing being cited. A citation with no tag is
    passed through untouched rather than guessed at.
    """
    tag, sep, value = (cites or "").partition(":")
    if not sep or not value.strip() or " " in tag:
        return cites
    return "%s: %s" % (tag, value.strip())


def _opportunities(section: dict) -> str:
    """Positive risk, in its own block, after the items and before the decisions.

    That sequence is the argument: *here is the exposure, here is what it costs us, here is
    what good would unlock, here is the decision.* CSF 2.0 `GV.RM-07` asks that strategic
    opportunities be characterised and **included in** cybersecurity risk discussions, and its
    own implementation example is to prioritise positive risks **alongside** negative ones —
    alongside, not inside. IR 8286C r1 asks that positive risk be recorded and acted upon.
    Both describe a distinct item, and both
    are the reason this is a block rather than a clause: an optimistic tail welded onto a loss
    statement reads as softening the loss, which teaches a board to discount the section.
    `outcome-framing.sh` fails a sidecar that tries it.

    **Patina, never RAG green.** The brand system is explicit that patina never signals
    "safe", and an opportunity is not a low-severity risk — it is a different kind of
    statement, so it takes the chrome colour and carries its word, as the graphics standard
    requires of every coloured thing in this suite.

    **Absent renders nothing.** No heading, no "none identified" placeholder. A placeholder
    would manufacture pressure to fill it, and a section with nothing to cite is the correct
    output rather than an incomplete one.
    """
    entries = section.get("opportunities") or []
    if not entries:
        return ""
    rows = "".join(
        f'<li>{esc(e["text"])}'
        f'<span class="from">cites {esc(_cites_display(e["cites"]))} · '
        f'{esc(e.get("gvsc") or "GV.RM-07")}</span></li>' for e in entries)
    return (f'<h3 class="opp-h">Positive risk</h3>'
            f'<p class="sub">What good would unlock, each against a goal or dependency the '
            f'business itself declared. An entry with nothing to cite is not written.</p>'
            f'<ol class="opps">{rows}</ol>')


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
    # CAC-AP-1 §2.5. Present only when a profile was applied — an absent line is the
    # honest rendering of a pack that narrowed nothing, and a reader a year from now needs
    # to know which perimeter the questions inside were asked against.
    profile = pack.get("profileVersion")
    profile_block = (
        f'<h3>Applicability profile</h3><p class="muted">Assembled against profile '
        f'<strong>{esc(profile)}</strong>. Sections that read a profile asked only the '
        f'questions it declares apply, and every question they skipped is recorded in '
        f'that section with who declared it and when.</p>' if profile else "")
    return (f'<div class="page">{_band("Provenance")}<h2>Provenance</h2>'
            f'<p class="sub">What this pack was built from, and what was not there.</p>'
            f'<h3>Sources</h3><dl>{sources}</dl>{profile_block}'
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
    charts = pack.get("charts") or []
    pages = "".join(_section_page(s, charts) for s in pack["sections"])
    body = (
        _cover(pack, audience)
        # Before the through-line, not after it. The through-line is the sentence a director
        # remembers; if the document is describing two different perimeters, that has to be
        # known before the memorable sentence rather than in a footnote after it.
        + _conflicts(pack.get("contextConflicts") or [])
        + f'<div class="page">{_band("Executive through-line")}'
        f'<h2>Executive through-line</h2>'
        f'<p class="sub">{esc(pack["period"])} · {esc(audience)} · '
        f'as at {esc(pack["asOf"])}</p>'
        f'{through}{_tiles(pack["headlines"])}</div>'
        # Before Decisions, deliberately. A board should see what moved on its own before it
        # sees what it is being asked to do about anything — the escalations are the context
        # the asks sit in, and several of the asks will be about them.
        f'<div class="page">{_band("Escalations")}<h2>What escalated</h2>'
        f'<p class="sub">Raised by the sections themselves, worst first. '
        f'Derived on every run and never stored — an escalation clears when its cause does.'
        f'</p>{_escalations(pack.get("escalations") or [])}</div>'
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

def build_pptx(pack: dict, path: str, mode: str = "full") -> None:
    """Write the deck. `mode` is "full" (everything, in reading order) or "board".

    BOARD MODE MOVES; IT NEVER DROPS. Every slide the full deck contains is still in the
    file — the per-section item lists and the management actions are relocated behind an
    appendix divider, and the section dividers, which are pure navigation for a deck that no
    longer runs long, are the only things that stop being drawn.

    That distinction is the whole design. A board deck that silently omitted a section's
    detail would be this skill inventing an editorial judgment about what a board needs to
    see, which is exactly what it refuses to do everywhere else — and unlike a placeholder,
    an omission leaves nothing behind to notice. An appendix is a reading order, not a
    filter, and the deck says on its divider what was moved and why.
    """
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

    # Straight after the cover, ahead of the through-line, on the same reasoning as the HTML:
    # if the pack is describing two different regulatory perimeters, a director must meet that
    # before the sentence they will remember. Parity is not optional here — a conflict that
    # reached the document and not the deck would mean the room and the reading pack disagreed
    # about whether there was a problem, which is a worse failure than the one being reported.
    conflicts = pack.get("contextConflicts") or []
    if conflicts:
        n = len(conflicts)
        # Not every conflict is about a regulatory regime — a posture conflict is
        # about an assessment lens. Fall back to the battery, which every conflict
        # has, rather than printing an empty list of regimes.
        regimes = ", ".join(sorted({c.get("regime") or c["battery"]
                                    for c in conflicts}))
        paras = [(f"{n} record{'' if n == 1 else 's'} {'is' if n == 1 else 'are'} tracked "
                  f"against {regimes}, which the applicability profile declares does not "
                  f"apply. The clocks were computed anyway.", 1250, True, PX.SEV_TEXT.get(
                      "critical", PX.INK), False),
                 ("A profile narrows the default question set; it does not overrule an "
                  "assessor who opened a clock in front of the evidence. Both readings are "
                  "still in this pack and one of them is wrong.", 1100, False, PX.MUTED,
                  False)]
        for c in conflicts[:4]:
            paras.append((f"{c.get('id') or '—'}  ·  {c['regime']}  ·  {c['flag']}",
                          1050, False, PX.INK, True))
        if n > 4:
            paras.append((f"and {n - 4} more, listed in full in the document",
                          1000, False, PX.MUTED, False))
        deck.add("The profile and the records disagree", paras, eyebrow=eyebrow)

    tl = pack["throughLine"]
    deck.add("Executive through-line",
             [(tl["executiveSummary"] if tl else PLACEHOLDER, 1400, False,
               PX.INK if tl else PX.MUTED, False)],
             eyebrow=eyebrow)

    # Declared here rather than beside the management actions, because board mode now moves
    # two kinds of slide and both have to reach the same list. See the escalation block below.
    appendix = []

    if pack["headlines"]:
        # Tiles rather than bullets, so a figure can carry the band its producer
        # declared. A figure with no band renders in ink and takes no rule and no
        # band word -- the deck decides severity exactly as little as the HTML does.
        #
        # In board mode only the first tile page stays in the core; the rest move to the
        # appendix, on the same rule as the escalation continuations. Seventeen headlines
        # across seven producers is three tile slides, and a board core is not the place for
        # the second and third — the through-line and the section summaries already carry the
        # story those tiles support. Moved, never dropped: the full deck is unchanged and the
        # appendix divider says so.
        note = ("Every figure was computed by the skill that owns it and read here "
                "unchanged. The pack calculates nothing.")
        if mode != "board":
            deck.figures("This quarter, in figures", pack["headlines"],
                         eyebrow=eyebrow, note=note)
        else:
            # Page one stays in the core, the rest move to the appendix — the rule already
            # applied to the escalation list, applied to the other block that grows with the
            # number of producers. Seventeen headlines across seven is three tile slides, and
            # a board core is not the place for the second and third: the through-line and
            # the section summaries already carry the story those tiles support.
            #
            # Paged HERE rather than by passing a slice, and titled with the SAME suffix the
            # full deck uses, because `_deckhas.py --lost` compares text runs: a core page
            # titled "This quarter, in figures" where the full deck says "…(1)" drops three
            # title runs and reads, correctly, as content lost. Moves-never-drops has to hold
            # for the titles too.
            per_page = PX.Deck.FIG_COLS * PX.Deck.FIG_ROWS
            pages = [pack["headlines"][i:i + per_page]
                     for i in range(0, len(pack["headlines"]), per_page)]
            for n, page in enumerate(pages, start=1):
                title = ("This quarter, in figures" if len(pages) == 1
                         else "This quarter, in figures (%d)" % n)
                if n == 1:
                    deck.figures(title, page, eyebrow=eyebrow, note=note)
                else:
                    # As TILES, not text rows: a tile writes its value as its own run, so
                    # "19" re-rendered as "AI deployments tracked: 19" would lose the bare
                    # run. Same content, same rendering, different place.
                    appendix.append(("figures", title, page))

    # The band compositions, as native shapes. Only the mixes: a bullet needs a zone axis and
    # a bar needs a scale, and both are marks the SVG library draws properly and this writer
    # would only approximate. Half a chart in a deck is worse than a clear pointer to the
    # document that has it, so the deck says where the rest are rather than faking them.
    mixes = [c for c in (pack.get("charts") or []) if c.get("kind") == "band-mix"]
    if mixes:
        deck.mixes("How the totals break down", mixes, eyebrow=eyebrow)

    # BL-124 T1. The comment above says the deck "says where the rest are rather than faking
    # them". Until now it did not. Eleven charts reach the pack, the HTML draws eleven, this
    # writer draws the three mixes, and the other eight left NO trace on the deck — no title,
    # no pointer, nothing. A reader working from the deck could not learn that a chart existed
    # to go and look for, which is the same silent divergence between deliverables that the
    # placeholder pair has prevented for prose since this skill shipped. The decision to draw
    # only the mixes stands; going undeclared about it does not.
    #
    # Derived from what the writer ACTUALLY drew, never from a hand-kept list, so it cannot
    # drift. That also catches a second gap for free: `Deck.mixes` renders
    # `charts[:MIX_PER_SLIDE]` with no pagination, so a fourth band-mix would vanish as
    # silently as the bars do today. Counting it as undrawn is correct rather than convenient
    # — it IS undrawn — and it means the deck reports the drop instead of swallowing it.
    # Paginating `mixes()` properly is a separate change and is filed, not smuggled in here.
    drawn = mixes[:PX.Deck.MIX_PER_SLIDE]
    undrawn = [c for c in (pack.get("charts") or []) if c not in drawn]
    if undrawn:
        # Sizes at or above NARRATIVE_TYPE_FLOOR (1100), deliberately. `deck-fit.sh` check 13
        # pins the set of sub-floor sizes the deck emits to exactly {900,950,1000,1050}; a new
        # size under the floor would fail it, and this slide has no reason to want one.
        kinds = {"bar": "bar chart", "bullet": "bullet chart", "band-mix": "band mix"}
        paras = [("The deck draws the band compositions as native shapes. The charts below "
                  "are in the pack and are drawn in full in the HTML document — they are "
                  "named here so that nothing is missing without saying so.",
                  1250, False, PX.INK, False)]
        for c in undrawn:
            paras.append(("%s  ·  %s" % (c.get("title") or "(untitled)",
                                         kinds.get(c.get("kind"), c.get("kind") or "chart")),
                          1150, False, PX.MUTED, True))
        paras.append(("A bullet needs a zone axis and a bar needs a scale. Both are marks the "
                      "SVG library draws properly and this writer would only approximate, and "
                      "half a chart in a board deck is worse than a clear pointer to the "
                      "document that has the whole one.",
                      1100, False, PX.MUTED, False))
        deck.add("Charts in the document, not on these slides", paras, eyebrow=eyebrow)

    # Escalations reach the deck as well as the document, and before the decisions for the
    # same reason they lead in the HTML. A figure that reaches one deliverable and not the
    # other means two readers of "the same pack" saw different things — the rule the
    # placeholder pair has enforced for prose since this skill shipped.
    escalated = pack.get("escalations") or []
    if escalated:
        for i in range(0, len(escalated), 5):
            chunk = escalated[i:i + 5]
            more = "" if len(escalated) <= 5 else f" ({i // 5 + 1})"
            paras = []
            for e in chunk:
                # Same shape rule as the HTML path, through the same function — see
                # evidence_text(). The deck was the second call site that assumed a dict,
                # and it is only reachable after the HTML path, which is why one crash hid
                # two.
                ev = evidence_text(e.get("evidence"))
                # Severity in the band's TEXT colour, never its fill: this is a light slide,
                # and the fills measure 1.5-2.6:1 there. verify() enforces it.
                paras.append((f"{e['severity'].upper()}  {e['subjectRef']}  ·  "
                              f"{e['trigger']}", 1250, True,
                              PX.SEV_TEXT.get(e["severity"], PX.INK), False))
                paras.append((ev, 1050, False, PX.MUTED, False))
            title = f"What escalated{more}"
            # In board mode the FIRST page stays in the core and the continuations move to the
            # appendix. Escalations arrive sorted worst-first by the assembler, so page one is
            # the worst five and moving pages two onward is not a judgement about which matter
            # — it is the same MOVES-NEVER-DROPS rule already applied to item detail, applied
            # to the other list that grows without limit.
            #
            # It became necessary when the specimen went from five sections to seven: 28
            # escalations is six slides, and a board core of 23 is not a board core. Nothing
            # about a board sitting's attention got longer because the product gained two
            # producers, so the deck is what has to give, not the length rule.
            if mode == "board" and i >= 5:
                appendix.append(("text", title, paras))
            else:
                deck.add(title, paras, eyebrow=eyebrow)
    else:
        deck.add("What escalated",
                 [("Nothing escalated. No section reported a band crossing, a sustained "
                   "drift, a long dwell over appetite, or a lapsed acceptance.",
                   1300, False, PX.MUTED, False)], eyebrow=eyebrow)

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
    #
    # In board mode they move to the appendix on the same reasoning taken one step further:
    # they are not for board decision at all, so they are not core to a board meeting. They
    # are still in the file, in full. (`appendix` is declared above the figures, because the
    # escalation continuations reach it first.)
    for i in range(0, len(management_asks), 5):
        chunk = management_asks[i:i + 5]
        more = "" if len(management_asks) <= 5 else f" ({i // 5 + 1})"
        rows = ([(d["text"], 1300, False, PX.INK, True) for d in chunk]
                + [("Marked by the section that raised each one. An ask nobody marked "
                    "stays on the decision slides.", 1000, False, PX.MUTED, False)])
        title = f"Management actions — not for board decision{more}"
        if mode == "board":
            appendix.append(("text", title, rows))
        else:
            deck.add(title, rows, eyebrow=eyebrow)

    total_sections = len(pack["sections"])
    for idx, section in enumerate(pack["sections"], start=1):
        title = SECTION_TITLE.get(section["section"], section["section"])
        # The counter, not the title, is the divider's second run: a divider
        # repeating its section's name would collide with that section's own
        # summary slide and trip the no-duplicate-titles check.
        if mode != "board":
            deck.section(title, f"Section {idx} of {total_sections}")
        paras = [(section["executiveSummary"] or PLACEHOLDER, 1300, False,
                  PX.INK if section["executiveSummary"] else PX.MUTED, False)]
        if section["section"] == "incident":
            paras.append((NOT_LEGAL, 1000, False, PX.MUTED, False))
        deck.add(title, paras, eyebrow=eyebrow)
        # Positive risk reaches the deck too, on its own slide and NEVER inside the item
        # detail — the same separation the HTML keeps, for the same reason. A figure or a
        # sentence that reaches one deliverable and not the other means two readers of "the
        # same pack" saw different things, and this pack's oldest rule is that they must not.
        #
        # It stays in the core in board mode. It is short, it is board-altitude by
        # construction (it cites a goal the business declared), and moving it to the appendix
        # would quietly make the loss-framed half of the pack the only half a board reads.
        opportunities = section.get("opportunities") or []
        if opportunities:
            # The citation gets its own muted line rather than a mid-dot clause welded to the
            # end of the sentence, which is what `.from { display:block }` already does in the
            # HTML. Inline, it collided with the bullet glyph: a slide read as a dot, a
            # sentence, another dot and a tag, so the citation looked like an unfinished
            # fragment rather than the receipt it is. Two deliverables, one treatment — the
            # rule stated four lines up applies to how a thing is set, not only to whether
            # it appears.
            body = [("What good would unlock, each against a declared goal.",
                     1000, False, PX.MUTED, False)]
            for e in opportunities:
                body.append((e["text"], 1150, False, PX.INK, True))
                body.append((f"cites {_cites_display(e['cites'])}",
                             950, False, PX.MUTED, False))
            deck.add(f"{title} — positive risk", body, eyebrow=eyebrow)
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
                rows = [(f"{k}: {v}", 1150, False, PX.INK, True) for k, v in chunk]
                if mode == "board":
                    appendix.append(("text", heading + part, rows))
                else:
                    deck.add(heading + part, rows, eyebrow=eyebrow)

    prov = pack["provenance"]
    notes = prov["missing"] + prov["warnings"]
    profile = pack.get("profileVersion")
    profile_line = ([("Assembled against applicability profile %s." % profile, 1100,
                      True, PX.INK, False)] if profile else [])
    deck.add("Provenance",
             [("What this pack was built from, and what was not there.", 1200, False,
               PX.MUTED, False)]
             + profile_line
             + [(n, 1100, False, PX.INK, True) for n in (notes or ["Nothing was missing."])],
             eyebrow=eyebrow)

    # The appendix, in board mode only. The divider states what was moved, so a reader who
    # notices the main deck is shorter than the document can see where the rest went instead
    # of wondering whether it was cut.
    if appendix:
        deck.section("Appendix",
                     "Item detail, management actions, and escalations beyond the first "
                     "five — which arrive worst-first, so the five in the main sequence are "
                     "the five that matter most. "
                     "Nothing has been removed — this is the same content the full deck "
                     "carries inline.")
        for kind, title, payload in appendix:
            # A moved figures page is re-rendered AS TILES. `_deckhas.py --lost` compares the
            # text runs in the two decks, and a tile writes its value as its own run — so
            # re-rendering "19" as "AI deployments tracked: 19" drops the bare run and reads,
            # correctly, as content lost. Same content, same rendering, different place: that
            # is what MOVES-NEVER-DROPS means.
            if kind == "figures":
                deck.figures(title, payload, eyebrow=eyebrow)
            else:
                deck.add(title, payload, eyebrow=eyebrow)
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
    p.add_argument("--deck-mode", choices=("full", "board"), default="full",
                   help="'full' (default) is every slide in reading order. 'board' moves "
                        "item detail and management actions behind an appendix divider and "
                        "drops the section dividers; nothing is removed from the file.")
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
        build_pptx(pack, args.pptx, args.deck_mode)
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
