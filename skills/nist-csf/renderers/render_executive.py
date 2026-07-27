#!/usr/bin/env python3
"""
render_executive.py — the board view of a CSF Organizational Profile.

Reads the JSON emitted by `profile_analysis.py analyze` (stdin or --in) and writes one
self-contained, Limen-branded HTML file. Content spec: references/dashboards.md.

RENDER ONLY, and deterministic. The renderer never writes board *language*: business
outcome statements come from the `ciso-board-translation` skill via --translations. With
no sidecar, the slot shows a labelled placeholder — never raw framework text dressed up
as a board message, and never invented prose.

Two guardrails are enforced here because this is the artifact that leaves the building:
  - Tiers are rendered as a labelled characterization of rigor with NIST's own wording,
    never as a score, an average, or a trend line.
  - Coverage always carries its fraction, and "not yet targeted" never renders as 0/100%.

Usage:
  python3 ../scripts/profile_analysis.py analyze acme.csfp \\
    | python3 render_executive.py --translations board.json --out board.html
"""

from __future__ import annotations

import sys

import _common as c


def rollup(ctx: c.Context) -> str:
    """One tile per Function, with movement since the last snapshot."""
    dfn = (ctx.diff or {}).get("coverage", {}).get("byFunction", {})
    tiles = []
    for fn in ctx.function_meta():
        fid = fn["id"]
        cov = ctx.coverage["byFunction"].get(fid, {"percent": None, "n": 0, "d": 0})
        comp = ctx.completeness["byFunction"].get(fid, {})
        delta = (dfn.get(fid) or {}).get("delta")
        # Direction is carried by the arrow, not by colour, so the chip simply takes
        # the tile's own text colour — the one already measured against this fill.
        #
        # Two earlier attempts split it by coverage threshold instead: first a single
        # hardcoded dark green (unreadable on the dark low-coverage tiles), then an
        # ondark/onlight pair that fixed those two and left the light end of the ramp
        # at 1.57:1 on the full-coverage green. A threshold that approximates the fill
        # will always miss somewhere; asking the fill is exact.
        tone = "" if c.cov_is_untargeted(cov) else f' style="color:{c.cov_text_color(cov)}"'
        if delta is None:
            move = f'<span class="delta flat"{tone}>—</span>'
        elif delta > 0:
            move = f'<span class="delta up"{tone}>▲ {delta:+.0f} pts</span>'
        elif delta < 0:
            move = f'<span class="delta down"{tone}>▼ {delta:+.0f} pts</span>'
        else:
            move = f'<span class="delta flat"{tone}>no change</span>'

        untargeted = c.cov_is_untargeted(cov)
        style = ("" if untargeted else
                 f'style="background:{c.cov_color(cov)};color:{c.cov_text_color(cov)}"')
        big = "not yet targeted" if untargeted else f"{cov['percent']:.0f}%"
        sub = "" if untargeted else f'<div class="frac">{cov["n"]}/{cov["d"]} of Target</div>'
        tiles.append(
            f'<div class="tile {"untargeted" if untargeted else ""}" {style}>'
            f'<div class="tid">{c.esc(fid)}</div>'
            f'<div class="tname">{c.esc(fn.get("name", ""))}</div>'
            f'<div class="tbig">{c.esc(big)}</div>{sub}'
            f'<div class="tcomp">{c.esc(c.completeness_line(comp))}</div>'
            f'<div class="tmove">{move}</div></div>')
    return (f'<section><h2>Where the programme stands</h2>'
            f'<div class="hint">Coverage of the Target this organisation set for itself — '
            f'not a score against an external benchmark. Movement is versus the last review.</div>'
            f'<div class="tiles">{"".join(tiles)}</div></section>')


def tier_block(ctx: c.Context) -> str:
    """Tier as a characterization of rigor. Never a score, never averaged, never trended."""
    tiers = ctx.tiers or {}
    levels = {int(l["tier"]): l for l in tiers.get("levels", [])}
    prof_tier = (tiers.get("profile") or {}).get("overall")
    # readerNote, never guardrail: guardrail is the instruction to the model that builds
    # this page. Printing it puts "must never be rendered, averaged, or trended as one"
    # in front of the board, in caps, which is the report talking to its author.
    reader_note = tiers.get("readerNote", "")

    if not levels:
        return ""

    steps = []
    for n in sorted(levels):
        lv = levels[n]
        on = (n == prof_tier)
        steps.append(f'<div class="step {"on" if on else ""}">'
                     f'<div class="sn">{n}</div>'
                     f'<div class="sl">{c.esc(lv.get("name", ""))}</div></div>')

    if prof_tier and prof_tier in levels:
        lv = levels[prof_tier]
        gov = "".join(f"<p>{c.esc(p)}</p>" for p in lv.get("governance", []))
        mgt = "".join(f"<p>{c.esc(p)}</p>" for p in lv.get("riskManagement", []))
        dims = tiers.get("dimensions", [])
        gov_label = next((d["label"] for d in dims if d["key"] == "governance"), "Governance")
        mgt_label = next((d["label"] for d in dims if d["key"] == "riskManagement"), "Risk Management")
        detail = (f'<div class="tierdetail">'
                  f'<div><h3>{c.esc(gov_label)}</h3>{gov}</div>'
                  f'<div><h3>{c.esc(mgt_label)}</h3>{mgt}</div></div>'
                  f'<div class="cite muted">Verbatim from '
                  f'{c.esc(tiers.get("source", {}).get("publication", "NIST CSWP 29"))}, '
                  f'{c.esc(tiers.get("source", {}).get("location", ""))}.</div>')
        headline = f'{c.esc(lv.get("label", ""))}'
    else:
        detail = ('<div class="card muted">No Tier has been characterized for this Profile. '
                  'A Tier is a deliberate judgment about the rigor of risk governance and '
                  'management practices — it is not calculated from the ratings above.</div>')
        headline = "Not characterized"

    return (f'<section><h2>Rigor of risk governance and management</h2>'
            f'<div class="hint">{c.esc(reader_note)}</div>'
            f'<div class="card"><div class="tierhead">{headline}</div>'
            f'<div class="steps">{"".join(steps)}</div>{detail}</div></section>')


def top_gaps(ctx: c.Context) -> str:
    """The top gaps, spoken as business outcomes — or an honest placeholder."""
    gaps = (ctx.attention.get("largestGaps") or ctx.gaps)[:5]
    if not gaps:
        return ('<section><h2>Where the biggest shortfalls are</h2>'
                '<div class="card muted">No gaps against the current Target.</div></section>')

    rows = []
    for g in gaps:
        tr = ctx.tr.gap(g["subcategoryId"])
        if tr:
            body = f'<div class="translated">{c.esc(tr)}</div>'
        else:
            body = (f'<div class="placeholder"><strong>Board language not supplied.</strong> '
                    f'{c.esc(c.PLACEHOLDER)}</div>'
                    f'<div class="rawtext muted">Framework wording, for reference only: '
                    f'{c.esc(g["text"])}</div>')
        cur = c.rating(g.get("current"))
        rows.append(
            f'<div class="gap"><div class="gaphead">'
            f'<span class="mono gid">{c.esc(g["subcategoryId"])}</span>'
            f'<span class="muted">{c.esc(g.get("functionName") or g.get("functionId", ""))}</span>'
            f'<span class="gscore">{c.esc(cur)} → {c.esc(g.get("target"))}</span>'
            f'</div>{body}</div>')
    return (f'<section><h2>Where the biggest shortfalls are</h2>'
            f'<div class="hint">Ranked by shortfall weighted by priority — not by count.</div>'
            f'{"".join(rows)}</section>')


def what_changed(ctx: c.Context) -> str:
    d = ctx.diff
    if not d:
        return ('<section><h2>What changed</h2><div class="card muted">No previous snapshot, '
                'so there is no comparison to draw. Take a snapshot at the end of this review '
                'and the next one will open with movement instead of a standing start.'
                '</div></section>')
    ov = d["coverage"]["overall"]
    if ov["delta"] is None:
        head = "Coverage is not comparable to the last review (one side had nothing targeted)."
    else:
        head = (f'Overall coverage moved from {ov["from"]:.0f}% to {ov["to"]:.0f}% '
                f'({ov["delta"]:+.1f} points).')

    items = []
    for ch in d["assessments"]["changed"][:12]:
        if ch["field"] in ("current", "target", "status"):
            frm = "unassessed" if ch["from"] is None else ch["from"]
            to = "unassessed" if ch["to"] is None else ch["to"]
            items.append(f'<li><span class="mono">{c.esc(ch["subcategoryId"])}</span> '
                         f'{c.esc(ch["field"])}: {c.esc(frm)} → {c.esc(to)}</li>')
    for i in d["actionItems"]["closed"]:
        items.append(f'<li>Completed: {c.esc(i["title"])}</li>')
    for i in d["actionItems"]["added"]:
        items.append(f'<li>New commitment: {c.esc(i["title"])}</li>')

    body = "".join(items) or '<li class="muted">No material movement since the last review.</li>'
    return (f'<section><h2>What changed since {c.esc(d["against"].get("label", "last review"))}</h2>'
            f'<div class="card"><p class="lede">{c.esc(head)}</p><ul>{body}</ul></div></section>')


def decisions(ctx: c.Context) -> str:
    """Asks, derived from the attention lists, plus anything the sidecar adds.

    The bar for this section is that a board could *vote* on the item. Assigning an owner
    to an action is the CISO's job, not a board decision, and putting it here trains the
    reader to skim the one section that must not be skimmed. Owner gaps surface on the
    operational dashboard instead.
    """
    a = ctx.attention
    out = []
    past = a.get("pastDueActions", [])
    if past:
        out.append(f'{len(past)} commitment{"s have" if len(past) != 1 else " has"} passed the '
                   f'target date and need{"" if len(past) != 1 else "s"} re-dating or honest '
                   f'closure ({", ".join(i["id"] for i in past)}).')
    acc = a.get("acceptedGaps", [])
    if acc:
        out.append(f'Re-affirm or withdraw {len(acc)} accepted gap'
                   f'{"s" if len(acc) != 1 else ""} '
                   f'({", ".join(r["subcategoryId"] for r in acc)}). An acceptance nobody '
                   f'revisits is how organisations get surprised.')
    never = a.get("neverReviewed", [])
    if never:
        out.append(f'{len(never)} outcome{"s have" if len(never) != 1 else " has"} never been '
                   f'assessed. Coverage figures above exclude them, so the picture is '
                   f'incomplete by that much.')
    out.extend(ctx.tr.decisions)

    if not out:
        return ""
    lis = "".join(f"<li>{c.esc(x)}</li>" for x in out)
    return (f'<section><h2>Decisions needed</h2>'
            f'<div class="card"><ul class="decisions">{lis}</ul></div></section>')


CSS = f"""
.tiles{{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:10px}}
.tile{{border-radius:10px;padding:14px;border:1px solid rgba(0,0,0,.07);min-height:150px;
  display:flex;flex-direction:column;gap:3px}}
.tid{{font-family:'IBM Plex Mono',monospace;font-size:11px}}
.tname{{font-family:'Space Grotesk',sans-serif;font-weight:600;font-size:13px}}
.tbig{{font-size:26px;font-weight:700;font-family:'Space Grotesk',sans-serif;
  line-height:1.1;margin-top:4px}}
.tile.untargeted .tbig{{font-size:15px;font-weight:600}}
/* No opacity on tile text. Opacity is invisible to a colour-pair check but not to
   a reader: it fades the text toward the fill, so .85 and .8 were quietly pulling
   already-marginal pairings further under AA. The tile's text colour is now
   measured against its own fill, so it can simply be used at full strength. */
.frac{{font-size:12px}}
.tcomp{{font-size:11px;margin-top:auto}}
.tmove{{font-size:12px;font-weight:600;margin-top:4px}}
/* .delta takes its colour inline from the tile's own text colour. */
.tile.untargeted .delta{{color:{c.SLATE}}}
.tierhead{{font-family:'Space Grotesk',sans-serif;font-size:20px;font-weight:600;
  margin-bottom:10px}}
.steps{{display:flex;gap:6px;margin-bottom:14px}}
.step{{flex:1;border:1px solid {c.WB_LINE};border-radius:8px;padding:8px;text-align:center;
  background:{c.WB}}}
.step.on{{background:{c.INK};color:{c.LIME};border-color:{c.INK}}}
.sn{{font-family:'IBM Plex Mono',monospace;font-size:16px;font-weight:700}}
.sl{{font-size:11px}}
.tierdetail{{display:grid;grid-template-columns:1fr 1fr;gap:18px}}
.tierdetail h3{{font-size:13px;margin-bottom:6px;color:{c.SLATE};text-transform:uppercase;
  letter-spacing:.04em}}
.tierdetail p{{font-size:13px;margin:0 0 8px}}
.cite{{font-size:11.5px;margin-top:10px;border-top:1px solid {c.WB_LINE};padding-top:8px}}
.gap{{background:{c.WB_SURF};border:1px solid {c.WB_LINE};border-radius:10px;
  padding:14px;margin-bottom:10px}}
.gaphead{{display:flex;gap:10px;align-items:baseline;margin-bottom:8px;flex-wrap:wrap}}
.gid{{background:{c.INK};color:{c.LIME};padding:2px 7px;border-radius:5px;font-size:12px}}
.gscore{{margin-left:auto;font-family:'IBM Plex Mono',monospace;font-size:12px;
  color:{c.SLATE}}}
.translated{{font-size:15px;line-height:1.55}}
.placeholder{{background:#FFF6E5;border:1px dashed #C08A3E;border-radius:8px;
  padding:10px;font-size:13px}}
.rawtext{{font-size:12.5px;margin-top:6px;font-style:italic}}
.lede{{font-size:15px;margin:0 0 10px}}
.decisions li{{margin-bottom:8px;font-size:14px}}
@media (max-width:720px){{.tierdetail{{grid-template-columns:1fr}}}}
"""


def main(argv):
    ctx = c.build(argv, "Executive CSF Profile dashboard", "csf-executive.html")
    p, cov, comp = ctx.profile, ctx.coverage["overall"], ctx.completeness["overall"]

    head = c.header("Executive dashboard", ctx,
                    [f'Cybersecurity programme posture · {c.esc(ctx.as_of_line())}'])

    summary_text = ctx.tr.executive_summary
    summary = ""
    if summary_text:
        summary = (f'<section><div class="card"><p class="lede">{c.esc(summary_text)}</p>'
                   f'</div></section>')
    elif ctx.tr.absent:
        summary = (f'<section><div class="card placeholder">'
                   f'<strong>Executive summary not supplied.</strong> {c.esc(c.PLACEHOLDER)}'
                   f'</div></section>')

    headline = (f'<section><div class="card">'
                f'<div style="font-size:30px;font-weight:700;'
                f'font-family:\'Space Grotesk\',sans-serif">{c.esc(c.cov_label(cov))}</div>'
                f'<div class="muted" style="margin-top:6px">overall coverage of Target · '
                f'{c.esc(c.completeness_line(comp))}</div></div></section>')

    body = (head + "<main>" + summary + headline + rollup(ctx) + tier_block(ctx)
            + top_gaps(ctx) + what_changed(ctx) + decisions(ctx) + "</main>"
            + f'<footer>{c.esc(ctx.footer())}</footer>')
    c.write(ctx, c.page(f'{p.get("name", "CSF Profile")} — Board View', CSS, body, ctx.offline))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
