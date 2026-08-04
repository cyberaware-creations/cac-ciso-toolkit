#!/usr/bin/env python3
"""
render_board.py — the executive/board dashboard (dashboards.md § Executive).

Fewer things, bigger, narrative: posture strip, theme rollup with direction,
top risks, over-appetite and band-mix trend across snapshots, the snapshot diff
("what changed since last review") with the rationales from the change log, and
the decisions the board is being asked to make.

Board *language* is never invented here. Pass --translations with the output of
the ciso-board-translation skill; without it the narrative slots render as
clearly-labelled placeholders.

Usage:
  python3 render_board.py <register.rr> [out.html] [--today YYYY-MM-DD]
                          [--translations translations.json]
"""

import sys

import _common as C

W, H, PAD = 340, 130, 30


def posture(ctx: C.Context) -> tuple[str, str, str, str]:
    """Headline over-appetite figure, arrow, colour and comparison — all derived."""
    s = ctx.live
    if len(ctx.trend) < 2:
        return str(s["overAppetite"]), "", C.LIME_DIM, "no snapshot to compare against"
    prev = ctx.trend[-2]
    d = s["overAppetite"] - prev["overAppetite"]
    key = "improving" if d < 0 else "worsening" if d > 0 else "steady"
    return (str(s["overAppetite"]), C.VELOCITY_MARK[key], C.VELOCITY_COLOR[key],
            f'was {prev["overAppetite"]} at {C.esc(prev["label"])}')


def trend_line(ctx: C.Context) -> str:
    pts, n = ctx.trend, len(ctx.trend)
    top = max([p["overAppetite"] for p in pts] + [1]) * 1.35
    step = (W - 2 * PAD) / max(n - 1, 1)
    xy = [(PAD + i * step, H - PAD - (p["overAppetite"] / top) * (H - 2 * PAD), p)
          for i, p in enumerate(pts)]
    poly = " ".join(f"{x:.0f},{y:.0f}" for x, y, _ in xy)
    ring = ' stroke="#fff" stroke-width="2"'
    dots = "".join(
        f'<circle cx="{x:.0f}" cy="{y:.0f}" r="4.5" fill="{C.PATINA}"'
        f'{ring if p["current"] else ""}/>'
        f'<text x="{x:.0f}" y="{y - 10:.0f}" font-size="11.5" fill="{C.INK}" '
        f'text-anchor="middle" font-weight="700">{p["overAppetite"]}</text>'
        f'<text x="{x:.0f}" y="{H - 9}" font-size="9.5" fill="{C.SLATE}" '
        f'text-anchor="middle">{C.esc(short(p["label"]))}</text>' for x, y, p in xy)
    return (f'<svg viewBox="0 0 {W} {H}" width="100%" height="{H}" role="img" '
            f'aria-label="Risks over appetite by review point">'
            f'<polyline points="{poly}" fill="none" stroke="{C.PATINA}" stroke-width="2.5"/>'
            f'{dots}</svg>')


def trend_bars(ctx: C.Context) -> str:
    pts = ctx.trend
    top = max([p["total"] for p in pts] + [1])
    bw = min(46, (W - 2 * PAD) / max(len(pts), 1) - 12)
    step = (W - 2 * PAD) / max(len(pts), 1)
    bars = ""
    for i, p in enumerate(pts):
        x = PAD + i * step + (step - bw) / 2
        y = H - PAD
        for b in ["critical", "high", "medium", "low"]:
            n = p["byBand"][b]
            if not n:
                continue
            h = (n / top) * (H - 2 * PAD)
            y -= h
            bars += (f'<rect x="{x:.0f}" y="{y:.0f}" width="{bw:.0f}" height="{h:.0f}" '
                     f'fill="{C.BAND[b]}"><title>{C.BAND_LABEL[b]}: {n}</title></rect>')
        bars += (f'<text x="{x + bw / 2:.0f}" y="{H - 9}" font-size="9.5" fill="{C.SLATE}" '
                 f'text-anchor="middle">{C.esc(short(p["label"]))}</text>')
    legend = "".join(f'<span class="lg"><i style="background:{C.BAND[b]}"></i>'
                     f'{C.BAND_LABEL[b]}</span>' for b in ["low", "medium", "high", "critical"])
    return (f'<svg viewBox="0 0 {W} {H}" width="100%" height="{H}" role="img" '
            f'aria-label="Residual band mix by review point">{bars}</svg>'
            f'<div class="legend">{legend}</div>')


def short(label: str) -> str:
    """Trend axes are labelled by snapshot, not raw date — keep them tick-sized."""
    parts = label.split()
    return " ".join(parts[:2]) if len(parts) > 2 else label


def themes_block(ctx: C.Context) -> str:
    if not ctx.theme_rollup:
        return '<p class="note">No risks to roll up.</p>'
    out = ""
    for t in ctx.theme_rollup:
        col = C.VELOCITY_COLOR[t["direction"]]
        narr = f'<div class="tnarr">{C.esc(t["narrative"])}</div>' if t["narrative"] else ""
        over = f' · <b>{t["over"]} over</b>' if t["over"] else ""
        plural = "s" if t["count"] != 1 else ""
        out += (f'<div class="theme" style="border-left-color:{C.BAND[t["worst"]]}">'
                f'<div class="tn">{C.esc(t["name"])}</div>'
                f'<div class="tm"><span class="cnt">{t["count"]} risk'
                f'{plural} · worst {C.chip(t["worst"])}{over}</span>'
                f'<span style="color:{col};font-weight:700;font-size:16px" '
                f'title="{t["direction"]} — residual exposure {t["priorExposure"]} → '
                f'{t["exposure"]}">{C.VELOCITY_MARK[t["direction"]]}</span></div>{narr}</div>')
    return out


def top_risks_block(ctx: C.Context) -> str:
    rows = ""
    for r in ctx.top_risks(5):
        provisional = r.get("provisionalTitle")
        title = (C.risk_title(r) if provisional
                 else f'<span class="t">{C.esc(r["title"])}</span>')
        line = (C.esc(r["translation"]) if r["translation"]
                else f'<span class="placeholder">Business-impact line not supplied — '
                     f'run ciso-board-translation for {r["id"]}.</span>')
        vel = (f'<span style="color:{C.VELOCITY_COLOR[r["velocity"]]}">'
               f'{C.VELOCITY_MARK[r["velocity"]]}</span>'
               f' {r["priorExposure"]} → {r["residualExposure"]}'
               if r["priorExposure"] is not None else "new since last review")
        rows += (f'<div class="toprisk"><div>{C.chip(r["residualBand"])}</div>'
                 f'<div class="body">{title} '
                 f'<span class="note">({r["id"]} · {C.esc(r["themeName"])} · residual '
                 f'{r["residualExposure"]}{" — provisional seed" if provisional else ""} · {vel}'
                 f'{" · over appetite" if r["overAppetite"] else ""})</span><br>{line}</div></div>')
    return rows


def changed_block(ctx: C.Context) -> str:
    d = ctx.diff
    if not d["baseline"]:
        return ('<p class="note">No snapshot exists yet, so there is no previous review to '
                'compare against. Create one with <code>score_register.py snapshot</code>.</p>')
    if not d["changes"]:
        return (f'<p class="note">Nothing has changed since '
                f'{C.esc(d["baseline"].get("label", "the last snapshot"))}.</p>')
    colour = {"worsened": C.BAND["critical"], "improved": C.PATINA, "closed": C.BAND["low"],
              "added": C.INK, "changed": C.SLATE, "removed": C.SLATE}
    out = ""
    for c in d["changes"]:
        why = (f'<div class="why">{C.esc(c["rationale"])}</div>' if c["rationale"]
               else '<div class="why placeholder">No rationale recorded for this change.</div>')
        out += (f'<div class="chg"><span class="tag" style="background:'
                f'{colour.get(c["kind"], C.SLATE)}">{c["kind"]}</span>'
                f'<span><b>{c["id"]}</b> {C.risk_title(c)} — {C.esc(c["detail"])}{why}</span>'
                f'</div>')
    return out


def summary_block(ctx: C.Context) -> str:
    # C.freshness_line() goes on BOTH branches. It is a caveat on the figures, and the
    # figures are present either way — a page whose narrative slot is a placeholder is
    # exactly the page most likely to be read off the numbers alone.
    #
    # It lives in _common.py rather than here because render_report.py::exec_summary() has
    # this identical two-branch shape and now calls it too. That renderer is the printable
    # board report — the artifact most likely to be handed round a table on paper, and the
    # one board-safety.sh's own header records as having kept exposing raw framework wording
    # for a full release after the executive dashboard was fixed. Two board-facing surfaces,
    # one sentence, one place: a reworded caveat cannot land on one page and not the other.
    if ctx.tr.executive_summary:
        return (f'<p class="lead">{C.esc(ctx.tr.executive_summary)}</p>'
                f'<div class="note">Executive narrative from the ciso-board-translation skill.</div>'
                + C.freshness_line(ctx))
    return (f'<p class="lead placeholder">{C.PLACEHOLDER}</p>'
            f'<div class="note">The figures on this page are derived from the register and are '
            f'complete; only the narrative is missing.</div>'
            + C.freshness_line(ctx))


CSS = f"""
*{{box-sizing:border-box}}body{{margin:0;font-family:'Manrope',system-ui,sans-serif;
  background:{C.WB};color:{C.INK}}}
h1,h2,h3{{font-family:'Space Grotesk','Manrope',system-ui,sans-serif;margin:0}}
.wrap{{max-width:1120px;margin:0 auto;padding:0 24px 48px}}
header{{background:{C.INK};color:{C.LIME};padding:20px 0}}
header .wrap{{padding-bottom:0;display:flex;align-items:center;justify-content:space-between;
  gap:16px;flex-wrap:wrap}}
.brand{{display:flex;align-items:center;gap:12px}}
.mark{{width:30px;height:30px;border-radius:7px;
  background:linear-gradient(135deg,{C.PATINA},{C.PATINA_H});position:relative;flex:0 0 auto}}
.mark::after{{content:"";position:absolute;inset:9px 8px;background:{C.INK};
  clip-path:polygon(0 40%,100% 0,100% 60%,0 100%)}}
.eyebrow{{color:{C.PATINA};font-size:11px;letter-spacing:.14em;text-transform:uppercase;
  font-weight:700}}
.brand h1{{font-size:19px;line-height:1.1}}
.meta{{text-align:right;font-size:12.5px;color:{C.LIME_DIM};line-height:1.5}}
.meta b{{color:{C.LIME}}}
.appetite{{display:inline-block;background:{C.PATINA};color:{C.INK};font-weight:700;
  border-radius:999px;padding:2px 10px;font-size:12px}}
.sub{{background:{C.INK_RAISED};color:{C.LIME_DIM};font-size:12.5px}}
/* `.sub` is a dark-chrome class and carries dimmed limestone text. The provisional
   banner reuses its shape but sits on the light workbench, where that inherited
   colour was 2.21:1 — unreadable, on the one line that says the numbers below are
   not assessments. `.onlight` opts back into ink. */
.sub.onlight,.sub.onlight b{{color:{C.INK}}}
.sub .wrap{{padding-top:8px;padding-bottom:8px}}
.section{{margin-top:28px}}
.section h2{{font-size:15px;letter-spacing:.02em;margin-bottom:12px}}
.exec-top{{display:grid;grid-template-columns:1.6fr 1fr 1fr;gap:12px}}
.big{{background:{C.INK};color:{C.LIME};border-radius:12px;padding:16px 18px}}
.big .n{{font-family:'Space Grotesk';font-size:32px;font-weight:600;line-height:1.1}}
.big .l{{color:{C.LIME_DIM};font-size:12px;margin-top:6px;line-height:1.45}}
.card{{background:{C.WB_SURF};border:1px solid {C.WB_LINE};border-radius:12px;padding:16px}}
.lead{{font-size:13.5px;line-height:1.65;margin:0}}
.themegrid{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}}
.theme{{background:{C.WB_SURF};border:1px solid {C.WB_LINE};border-left:5px solid {C.SLATE};
  border-radius:10px;padding:12px 14px}}
.theme .tn{{font-weight:700;font-size:13.5px}}
.theme .tm{{display:flex;justify-content:space-between;align-items:center;margin-top:8px;gap:8px}}
.theme .cnt{{color:{C.SLATE};font-size:12px}}
.theme .tnarr{{font-size:12px;line-height:1.45;margin-top:8px;color:{C.INK}}}
.chip{{border-radius:999px;padding:2px 8px;font-size:11px;font-weight:700;white-space:nowrap}}
.grid2{{display:grid;gap:24px;align-items:start;grid-template-columns:1.45fr 1fr}}
/* Grid items default to min-width:auto (min-content), so one long unbroken
   string props the column — and the page — wider than the device. */
.exec-top>*,.themegrid>*,.grid2>*{{min-width:0}}
.toprisk{{display:flex;gap:12px;padding:12px 0;border-top:1px solid {C.WB_LINE}}}
.toprisk:first-child{{border-top:none}}
.toprisk .body{{font-size:13px;line-height:1.5}}
.toprisk .t{{font-weight:700}}
.chg{{display:flex;gap:10px;padding:9px 0;font-size:12.5px;align-items:baseline;
  border-top:1px solid {C.WB_LINE};line-height:1.45}}
.chg:first-child{{border-top:none}}
.tag{{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.05em;
  border-radius:5px;padding:2px 7px;color:#fff;white-space:nowrap}}
.why{{color:{C.SLATE};font-style:italic;margin-top:3px;font-size:12px}}
.decision{{background:{C.WB_SURF};border:1px solid {C.WB_LINE};border-left:5px solid {C.PATINA};
  border-radius:10px;padding:11px 14px;margin-bottom:10px;font-size:13px;line-height:1.5}}
.note{{color:{C.SLATE};font-size:11.5px;font-style:italic;margin-top:8px}}
/* The freshness sentence is a caveat on the whole page, not a continuation of the
   sidecar attribution note above it, so it takes a rule and a separator. Italic is
   dropped because this note is mostly numbers and day ranges, which italics at
   11.5px make measurably harder to read. Colour is left inherited from .note
   deliberately: SLATE on the surface is the one contrast judgement responsive.sh
   already measures, and a second value here would be a second judgement to keep. */
.note.freshness{{font-style:normal;border-top:1px solid {C.WB_LINE};padding-top:9px;
  margin-top:11px;line-height:1.55}}
.placeholder{{color:{C.SLATE};background:repeating-linear-gradient(135deg,#EFEBE0,#EFEBE0 6px,
  #F6F4EE 6px,#F6F4EE 12px);border-radius:6px;padding:2px 6px;display:inline-block}}
.legend{{display:flex;gap:12px;justify-content:center;margin-top:2px}}
.legend .lg{{font-size:10.5px;color:{C.SLATE};display:flex;align-items:center;gap:4px}}
.legend i{{width:9px;height:9px;border-radius:2px;display:inline-block}}
svg text{{font-family:'Manrope',sans-serif}}
footer{{margin-top:36px;color:{C.SLATE};font-size:11px;border-top:1px solid {C.WB_LINE};
  padding-top:14px}}
/* The column counts live in CSS, never inline on the element: an inline
   grid-template-columns outranks this rule and silently defeats it. */
@media (max-width:900px){{.exec-top,.themegrid,.grid2{{grid-template-columns:1fr}}}}
"""


def _dtext(d): return d.get("text") if isinstance(d, dict) else d


def render(ctx: C.Context) -> str:
    m, s, sm = ctx.meta, ctx.settings, ctx.live
    n, arrow, col, cmp_txt = posture(ctx)
    due = len(ctx.attention["acceptanceDue"])
    live = sm["total"]
    board_d = [d for d in ctx.decisions
               if not (isinstance(d, dict) and d.get("altitude") == "management")]
    mgmt_d = [d for d in ctx.decisions
              if isinstance(d, dict) and d.get("altitude") == "management"]
    decisions = ("".join(f'<div class="decision">{C.esc(_dtext(d))}</div>' for d in board_d)
                 or '<p class="note">No decisions are outstanding from the data.</p>')
    mgmt_block = ""
    if mgmt_d:
        mgmt_items = "".join(f'<div class="decision">{C.esc(_dtext(d))}</div>' for d in mgmt_d)
        mgmt_block = (f'\n  <div class="section"><h2>Management actions — not for board decision</h2>'
                      f'{mgmt_items}</div>')
    client = C.esc(m.get("clientName") or "")
    title_tail = " · " + client if client else ""
    expired = ctx.attention["acceptanceExpired"]
    expired_txt = "· %d past expiry" % len(expired) if expired else ""
    since = (C.esc(ctx.diff["baseline"].get("label", "the last review"))
             if ctx.diff["baseline"] else "the last review")
    # A register that is mostly unrefined import seeds still renders a confident band
    # mix and a headline count. Say so at the top, once, rather than letting the numbers
    # imply an assessment that has not happened.
    # "1 of 73 risks sit above" — the subject is the count, not the noun beside it.
    # Small, but this is the first sentence a director reads.
    sit_verb = "sits" if sm["overAppetite"] == 1 else "sit"
    # Only say "live" where it distinguishes something. On a register with no closures
    # the word is noise; on one with closures it is the difference between a headline
    # that improves as risks are treated out and one that never moves.
    live_word = " live" if sm["closed"] else ""
    prov = sm.get("provisional", 0)
    prov_banner = (
        f'<div class="sub onlight" style="background:{C.BAND["high"]}1a;border-bottom:1px solid '
        f'{C.BAND["high"]}55"><div class="wrap"><b>{prov} of {sm["total"]} risks are '
        f'provisional</b> — imported CSF gaps still carrying the priority seed and framework '
        f'wording. Their scores are placeholders, not assessments, and the figures below '
        f'include them.</div></div>' if prov else "")
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Risk Register — Executive{title_tail}</title>
{C.fonts(ctx.offline)}<style>{CSS}</style></head><body>
<header><div class="wrap"><div class="brand"><div class="mark"></div><div>
  <div class="eyebrow">Cyber Aware Creations · Risk Register</div>
  <h1>Executive dashboard</h1></div></div>
  <div class="meta"><b>{C.esc(m.get('clientName') or '(unnamed register)')}</b><br>
  {C.esc(m.get('assessor') or '—')}<br>
  <span class="appetite">Appetite: {C.esc(s['appetite'])}</span>
  &nbsp;{s['matrixSize']}×{s['matrixSize']} matrix</div></div></header>
<div class="sub"><div class="wrap">{C.esc(ctx.as_of_line())} · {sm['registerTotal']} risks tracked
  ({live} live, {sm['closed']} closed)</div></div>
{prov_banner}
<div class="wrap">
  <div class="section exec-top">
    <div class="big"><div class="n">{sm['overAppetite']} of {sm['total']}{live_word} risks</div>
      <div class="l">{sit_verb} above the {C.esc(C.BAND_LABEL[ctx.appetite].lower())} risk appetite.
      {C.esc(m.get('appetiteStatement') or '')}</div></div>
    <div class="big"><div class="n">{n} <span style="color:{col}">{arrow}</span></div>
      <div class="l">Over appetite<br>{cmp_txt}</div></div>
    <div class="big"><div class="n">{due}</div>
      <div class="l">Acceptance{"s" if due != 1 else ""} due for re-validation
      {expired_txt}</div></div>
  </div>

  <div class="section"><h2>Executive summary</h2><div class="card">{summary_block(ctx)}</div></div>

  <div class="section"><h2>Risk themes</h2><div class="themegrid">{themes_block(ctx)}</div></div>

  <div class="section grid2">
    <div><h2>Top risks — what they mean for the business</h2>
      <div class="card">{top_risks_block(ctx)}</div></div>
    <div><h2>Trend across reviews</h2><div class="card">{trend_line(ctx)}
      <div class="note" style="text-align:center;margin-top:0">Risks over appetite</div>
      <div style="margin-top:14px">{trend_bars(ctx)}</div>
      <div class="note" style="text-align:center;margin-top:0">Residual band mix</div></div></div>
  </div>

  <div class="section grid2">
    <div><h2>What changed since {since}</h2>
      <div class="card">{changed_block(ctx)}</div></div>
    <div><h2>Decisions for the board</h2>{decisions}</div>
  </div>{mgmt_block}

  <footer>{C.esc(ctx.footer("executive dashboard"))}</footer>
</div></body></html>"""


if __name__ == "__main__":
    ctx = C.build(sys.argv[1:], __doc__, "risk-register-executive.html")
    C.write(ctx, render(ctx))
