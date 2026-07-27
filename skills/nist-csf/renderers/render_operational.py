#!/usr/bin/env python3
"""
render_operational.py — the CISO/team view of a CSF Organizational Profile.

Reads the JSON emitted by `profile_analysis.py analyze` (stdin or --in) and writes one
self-contained, Limen-branded HTML file. Content spec: references/dashboards.md.

RENDER ONLY. Every number here comes straight from the analyze JSON; nothing is
recomputed. If a figure is missing, add it to `analyze`, not to this file.

Usage:
  python3 ../scripts/profile_analysis.py analyze acme.csfp | python3 render_operational.py --out coverage.html
"""

from __future__ import annotations

import sys

import _common as c


def heatmap(ctx: c.Context) -> str:
    """Function × Category coverage, with a Current/Target toggle.

    Every Function in the framework is rendered even when it has no assessments, so an
    untouched Function cannot silently vanish from the picture.
    """
    rows = []
    for fn in ctx.function_meta():
        fid = fn["id"]
        fcov = ctx.coverage["byFunction"].get(fid, {"percent": None, "n": 0, "d": 0})
        fcomp = ctx.completeness["byFunction"].get(fid, {})
        cells = []
        for cat in fn.get("categories", []):
            cid = cat["id"]
            cov = ctx.coverage["byCategory"].get(cid)
            comp = ctx.completeness["byCategory"].get(cid, {})
            if cov is None:
                # Category exists in the framework but nothing in this Profile tracks it.
                cells.append(
                    f'<div class="cell untargeted" title="{c.esc(cat.get("name",""))} — not tracked">'
                    f'<span class="cid">{c.esc(cid)}</span>'
                    f'<span class="cval">not tracked</span></div>')
                continue
            untargeted = c.cov_is_untargeted(cov)
            klass = "cell untargeted" if untargeted else "cell"
            style = "" if untargeted else (f'style="background:{c.cov_color(cov)};'
                                           f'color:{c.cov_text_color(cov)}"')
            cur_val = "not yet targeted" if untargeted else f"{cov['percent']:.0f}%"
            frac = "—" if untargeted else f"{cov['n']}/{cov['d']}"
            tgt_val = "—" if untargeted else f"target {cov['d']}"
            cells.append(
                f'<div class="{klass}" {style} title="{c.esc(cat.get("name",""))} — '
                f'{c.esc(c.completeness_line(comp))}">'
                f'<span class="cid">{c.esc(cid)}</span>'
                f'<span class="cval" data-current="{c.esc(cur_val)}" data-target="{c.esc(tgt_val)}">'
                f'{c.esc(cur_val)}</span>'
                f'<span class="cfrac">{c.esc(frac)}</span></div>')

        rows.append(
            f'<div class="fnrow"><div class="fnhead">'
            f'<span class="fid">{c.esc(fid)}</span>'
            f'<span class="fname">{c.esc(fn.get("name", ""))}</span>'
            f'<span class="fcov">{c.esc(c.cov_label(fcov))}</span>'
            f'<span class="fcomp muted">{c.esc(c.completeness_line(fcomp))}</span>'
            f'</div><div class="cells">{"".join(cells)}</div></div>')

    return (f'<section><h2>Coverage by Function and Category</h2>'
            f'<div class="hint">Achieved against Target. Hatched cells are '
            f'<strong>not yet targeted</strong> — that is not 0%, and it is not 100%.</div>'
            f'<div class="toggle"><button id="tg" type="button" data-mode="current">'
            f'Showing: coverage — switch to Target</button></div>'
            f'<div class="heat">{"".join(rows)}</div></section>')


def gap_table(ctx: c.Context) -> str:
    if not ctx.gaps:
        return ('<section><h2>Gaps</h2><div class="card muted">No gaps. Either the Profile '
                'meets every Target, or nothing has been targeted yet — check the completeness '
                'figures above before celebrating.</div></section>')

    rows = []
    for i, g in enumerate(ctx.gaps):
        ex = "".join(f"<li>{c.esc(e)}</li>" for e in g.get("examples", []))
        pc = c.PRIORITY_COLOR.get(g.get("priority", "medium"), c.SLATE)
        cur = c.rating(g.get("current"))
        gd = g.get("guidance") or {}
        gbits = []
        if gd.get("header"):
            gbits.append(f'<div class="ghead">{c.esc(gd["header"])}</div>')
        if gd.get("whatMatureLooksLike"):
            gbits.append(f'<p><strong>What mature looks like.</strong> '
                         f'{c.esc(gd["whatMatureLooksLike"])}</p>')
        if gd.get("nextSteps"):
            steps = "".join(f"<li>{c.esc(s)}</li>" for s in gd["nextSteps"])
            gbits.append(f'<p><strong>Next steps</strong></p><ol>{steps}</ol>')
        if gd.get("transition"):
            gbits.append(f'<p class="muted">{c.esc(gd["transition"])}</p>')
        if gd.get("functionSlant"):
            gbits.append(f'<p class="muted">{c.esc(gd["functionSlant"])}</p>')
        if gd.get("commonPitfalls"):
            gbits.append(f'<p class="pitfall"><strong>Watch for.</strong> '
                         f'{c.esc(gd["commonPitfalls"])}</p>')
        guidance_block = (f'<div class="guidance{" deep" if gd.get("source") == "deep" else ""}">'
                          f'{"".join(gbits)}</div>') if gbits else ""
        rows.append(
            f'<tr class="grow" data-i="{i}">'
            f'<td class="mono">{c.esc(g["subcategoryId"])}</td>'
            f'<td>{c.esc(g["text"])}</td>'
            f'<td class="mono nowrap">{c.esc(cur)} → {c.esc(g.get("target"))}</td>'
            f'<td class="mono">{g.get("gap")}</td>'
            f'<td><span class="chip" style="background:{pc};color:#fff">'
            f'{c.esc(g.get("priority", ""))}</span></td>'
            f'<td class="mono"><strong>{g.get("prioritizedGapScore", 0):g}</strong></td>'
            f'<td class="muted">{c.esc(g.get("status", ""))}</td>'
            f'<td class="muted mono">{c.esc(g.get("lastReviewed") or "never")}</td>'
            f'</tr>'
            f'<tr class="exrow" id="ex{i}"><td colspan="8">'
            f'<div class="exwrap">{guidance_block}'
            f'<strong>NIST Implementation Examples</strong>'
            f'<ul>{ex}</ul></div></td></tr>')

    return (f'<section><h2>Gaps <span class="muted">({len(ctx.gaps)})</span></h2>'
            f'<div class="hint">Ordered by prioritized score (gap × priority × Function weight) — '
            f'the only ordering that accounts for both size and importance. '
            f'Click a row for the NIST Implementation Examples that close it.</div>'
            f'<div class="scroll"><table id="gaps"><thead><tr>'
            f'<th data-sort="0">Subcategory</th><th data-sort="1">Outcome</th>'
            f'<th data-sort="2">Current → Target</th><th data-sort="3" class="num">Gap</th>'
            f'<th data-sort="4">Priority</th><th data-sort="5" class="num">Score</th>'
            f'<th data-sort="6">Status</th><th data-sort="7">Last reviewed</th>'
            f'</tr></thead><tbody>{"".join(rows)}</tbody></table></div></section>')


def attention(ctx: c.Context) -> str:
    a = ctx.attention
    panels = [
        ("Largest gaps", "Is anything being done about the top few?",
         [f'<span class="mono">{c.esc(g["subcategoryId"])}</span> {c.esc(c.trunc(g["text"], 70))}'
          f'<span class="muted"> · score {g["prioritizedGapScore"]:g}</span>'
          for g in a.get("largestGaps", [])]),
        ("Never reviewed", "Why has nobody looked at these at all?",
         [f'<span class="mono">{c.esc(r["subcategoryId"])}</span> {c.esc(c.trunc(r["text"], 70))}'
          for r in a.get("neverReviewed", [])]),
        ("Stalest", "Is this rating still true, or just old?",
         [f'<span class="mono">{c.esc(r["subcategoryId"])}</span> '
          f'<span class="muted">{c.esc(r["lastReviewed"])}</span> {c.esc(c.trunc(r["text"], 60))}'
          for r in a.get("stalest", [])]),
        ("Unowned actions", "An action without an owner is a wish.",
         [f'<span class="mono">{c.esc(i["id"])}</span> {c.esc(i["title"])}'
          for i in a.get("unownedActions", [])]),
        ("Past due", "Slipped, or abandoned? Re-date it or close it honestly.",
         [f'<span class="mono">{c.esc(i["id"])}</span> {c.esc(i["title"])}'
          f'<span class="muted"> · due {c.esc(i.get("targetDate"))}</span>'
          for i in a.get("pastDueActions", [])]),
        ("Accepted gaps", "Is the acceptance still valid, and who re-affirms it?",
         [f'<span class="mono">{c.esc(r["subcategoryId"])}</span> {c.esc(c.trunc(r["text"], 70))}'
          for r in a.get("acceptedGaps", [])]),
    ]
    cards = []
    for title, question, items in panels:
        body = ("".join(f"<li>{i}</li>" for i in items) if items
                else '<li class="muted">Nothing here.</li>')
        cards.append(f'<div class="card panel"><h3>{c.esc(title)} '
                     f'<span class="count">{len(items)}</span></h3>'
                     f'<div class="q muted">{c.esc(question)}</div><ul>{body}</ul></div>')
    return (f'<section><h2>Needs attention</h2>'
            f'<div class="hint">Never-reviewed and stalest are separate lists on purpose — '
            f'"nobody ever looked" is a different problem from "nobody looked lately".</div>'
            f'<div class="grid">{"".join(cards)}</div></section>')


def playbook(ctx: c.Context) -> str:
    """The Next-90-Days worksheet, from the web tool's report section 8.

    Owner and Due are intentionally blank. This is a page to sit in front of a team
    and fill in together; once a line has an owner and a date it belongs in the
    action plan below, tracked by `action add`.
    """
    rows = ctx.a.get("playbook") or []
    if not rows:
        return ""
    out = []
    for r in rows:
        move = r.get("recommendedFirstMove") or "—"
        out.append(
            f'<tr><td class="mono">{c.esc(r["subcategoryId"])}</td>'
            f'<td>{c.esc(c.trunc(r["text"], 90))}</td>'
            f'<td class="mono nowrap">{c.esc(c.rating(r.get("current")))} → {c.esc(r.get("target"))}</td>'
            f'<td>{c.esc(move)}</td>'
            f'<td class="fill"></td><td class="fill"></td></tr>')
    return (f'<section><h2>Next 90 days</h2>'
            f'<div class="hint">The highest-priority shortfalls with a recommended first move. '
            f'Owner and due date are blank on purpose — fill them in with the team, then track '
            f'them as action items so they show up on the attention lists.</div>'
            f'<div class="scroll"><table class="playbook"><thead><tr>'
            f'<th>Subcategory</th><th>Outcome</th><th>Current → Target</th>'
            f'<th>Recommended first move</th><th>Owner</th><th>Due</th>'
            f'</tr></thead><tbody>{"".join(out)}</tbody></table></div></section>')


def action_plan(ctx: c.Context) -> str:
    items = ctx.actions.get("items", [])
    if not items:
        return ('<section><h2>Action plan</h2><div class="card muted">No action items. '
                'Gaps that never become owned, dated work will be on this list again next '
                'quarter.</div></section>')
    rows = []
    for i in items:
        flags = []
        if not (i.get("owner") or "").strip() and i.get("status") != "closed":
            flags.append('<span class="flag">unowned</span>')
        if (i.get("targetDate") and i.get("status") != "closed"
                and i["targetDate"] < ctx.today):
            flags.append('<span class="flag">past due</span>')
        rows.append(
            f'<tr><td class="mono">{c.esc(i.get("id"))}</td>'
            f'<td>{c.esc(i.get("title"))} {"".join(flags)}</td>'
            f'<td class="mono">{c.esc(", ".join(i.get("linkedSubcategoryIds", [])))}</td>'
            f'<td>{c.esc(i.get("owner") or "—")}</td>'
            f'<td>{c.esc(i.get("milestone") or "—")}</td>'
            f'<td class="mono">{c.esc(i.get("targetDate") or "—")}</td>'
            f'<td>{c.esc(i.get("status"))}</td></tr>')
    s = ctx.actions.get("summary", {})
    return (f'<section><h2>Action plan '
            f'<span class="muted">({s.get("open",0)} open · {s.get("inProgress",0)} in progress '
            f'· {s.get("closed",0)} closed)</span></h2>'
            f'<div class="scroll"><table><thead><tr><th>ID</th><th>Title</th>'
            f'<th>Linked</th><th>Owner</th><th>Milestone</th><th>Target</th><th>Status</th>'
            f'</tr></thead><tbody>{"".join(rows)}</tbody></table></div></section>')


CSS = f"""
.toggle{{margin-bottom:10px}}
.toggle button{{background:{c.PATINA};color:#fff;border:0;border-radius:8px;
  padding:7px 13px;font:inherit;font-size:13px;font-weight:600;cursor:pointer}}
.toggle button:hover{{background:{c.PATINA_H}}}
.heat{{display:flex;flex-direction:column;gap:8px}}
.fnrow{{background:{c.WB_SURF};border:1px solid {c.WB_LINE};border-radius:10px;padding:12px}}
.fnhead{{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap;margin-bottom:9px}}
.fid{{font-family:'IBM Plex Mono',monospace;font-weight:700;background:{c.INK};
  color:{c.LIME};padding:2px 7px;border-radius:5px;font-size:12px}}
.fname{{font-family:'Space Grotesk',sans-serif;font-weight:600}}
.fcov{{font-weight:600}}
.fcomp{{font-size:12px}}
.cells{{display:grid;grid-template-columns:repeat(auto-fill,minmax(112px,1fr));gap:6px}}
.cell{{border-radius:7px;padding:8px;min-height:62px;display:flex;flex-direction:column;
  gap:2px;border:1px solid rgba(0,0,0,.06)}}
.cid{{font-family:'IBM Plex Mono',monospace;font-size:11px;opacity:.85}}
.cval{{font-weight:700;font-size:14px}}
.cfrac{{font-size:11px;opacity:.8}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(290px,1fr));gap:12px}}
.panel h3{{font-size:14px;display:flex;justify-content:space-between;align-items:center}}
.panel .count{{background:{c.INK};color:{c.LIME};border-radius:999px;
  padding:1px 8px;font-size:11px;font-family:'IBM Plex Mono',monospace}}
.panel .q{{font-size:12px;margin:4px 0 8px}}
.panel ul{{margin:0;padding-left:16px}}
.panel li{{font-size:12.5px;margin-bottom:5px}}
.nowrap{{white-space:nowrap}}
th.num,td.num{{text-align:right}}
th[data-sort]{{cursor:pointer;user-select:none}}
th[data-sort]:hover{{color:{c.INK}}}
.grow{{cursor:pointer}}
.grow:hover td{{background:{c.WB}}}
.exrow{{display:none}}
.exrow.open{{display:table-row}}
.exwrap{{background:{c.WB};padding:10px 12px;border-radius:8px}}
.exwrap ul{{margin:6px 0 0;padding-left:18px}}
.exwrap li{{font-size:12.5px;margin-bottom:4px}}
.guidance{{background:#FFFDF7;border:1px solid {c.WB_LINE};border-left:3px solid {c.SLATE};
  border-radius:8px;padding:10px 12px;margin-bottom:10px}}
.guidance.deep{{border-left-color:{c.PATINA}}}
.guidance .ghead{{font-weight:700;font-size:12.5px;margin-bottom:6px}}
.guidance p{{font-size:12.5px;margin:0 0 6px}}
.guidance ol{{margin:4px 0 6px;padding-left:18px}}
.guidance li{{font-size:12.5px;margin-bottom:3px}}
.guidance .pitfall{{color:#7C3A32}}
.playbook td.fill{{background:{c.WB};min-width:110px}}
.flag{{display:inline-block;background:#7C3A32;color:#fff;border-radius:4px;
  padding:1px 6px;font-size:10.5px;font-weight:700;margin-left:6px}}
"""

JS = """
document.querySelectorAll('tr.grow').forEach(function(r){
  r.addEventListener('click', function(){
    var ex = document.getElementById('ex' + r.dataset.i);
    if (ex) ex.classList.toggle('open');
  });
});
var tg = document.getElementById('tg');
if (tg) tg.addEventListener('click', function(){
  var toTarget = tg.dataset.mode === 'current';
  document.querySelectorAll('.cval').forEach(function(el){
    var v = toTarget ? el.dataset.target : el.dataset.current;
    if (v) el.textContent = v;
  });
  tg.dataset.mode = toTarget ? 'target' : 'current';
  tg.textContent = toTarget ? 'Showing: Target — switch to coverage'
                            : 'Showing: coverage — switch to Target';
});
document.querySelectorAll('#gaps th[data-sort]').forEach(function(th){
  th.addEventListener('click', function(){
    var tb = document.querySelector('#gaps tbody');
    var i = +th.dataset.sort;
    var asc = th.dataset.dir !== 'asc';
    th.dataset.dir = asc ? 'asc' : 'desc';
    var pairs = [];
    var rows = Array.prototype.slice.call(tb.querySelectorAll('tr.grow'));
    rows.forEach(function(r){
      pairs.push([r, document.getElementById('ex' + r.dataset.i)]);
    });
    pairs.sort(function(a, b){
      var x = a[0].cells[i].textContent.trim(), y = b[0].cells[i].textContent.trim();
      var nx = parseFloat(x), ny = parseFloat(y);
      var r = (!isNaN(nx) && !isNaN(ny)) ? nx - ny : x.localeCompare(y);
      return asc ? r : -r;
    });
    pairs.forEach(function(p){ tb.appendChild(p[0]); if (p[1]) tb.appendChild(p[1]); });
  });
});
"""


def main(argv):
    ctx = c.build(argv, "Operational CSF Profile dashboard", "csf-operational.html")
    p, cov, comp = ctx.profile, ctx.coverage["overall"], ctx.completeness["overall"]
    scope = p.get("scope", {})
    scope_bits = [b for b in [
        ", ".join(scope.get("orgUnits", [])) or None,
        ("threats: " + ", ".join(scope.get("threatTypes", []))) if scope.get("threatTypes") else None,
        ("owner: " + scope["owner"]) if scope.get("owner") else None,
    ] if b]

    head = (f'<header><h1>{c.esc(p.get("name", "CSF Organizational Profile"))}</h1>'
            f'<div class="sub">{c.esc(ctx.as_of_line())}</div>'
            f'<div class="sub">{c.esc(" · ".join(scope_bits))}</div></header>')

    overall = (f'<section><h2>Overall coverage</h2>'
               f'<div class="card"><div style="font-size:30px;font-weight:700;'
               f'font-family:\'Space Grotesk\',sans-serif">{c.esc(c.cov_label(cov))}</div>'
               f'<div class="muted" style="margin-top:6px">{c.esc(c.completeness_line(comp))} · '
               f'{ctx.a.get("tracked", 0)} of {ctx.framework.get("subcategories", 0)} '
               f'Subcategories tracked</div>'
               + ('' if not c.cov_is_untargeted(cov) else
                  '<div class="muted" style="margin-top:8px">Nothing is targeted yet, so there is '
                  'no coverage figure to report. Run <span class="mono">quickstart-target</span> '
                  'and then tune Targets by risk.</div>')
               + f'</div></section>')

    body = (head + "<main>" + overall + heatmap(ctx) + gap_table(ctx) + attention(ctx)
            + playbook(ctx) + action_plan(ctx) + "</main>"
            + f'<footer>{c.esc(ctx.footer())}</footer>'
            + f"<script>{JS}</script>")
    c.write(ctx, c.page(f'{p.get("name", "CSF Profile")} — Coverage', CSS, body))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
