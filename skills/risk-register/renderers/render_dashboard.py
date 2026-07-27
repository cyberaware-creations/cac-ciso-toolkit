#!/usr/bin/env python3
"""
render_dashboard.py — the operational working view (dashboards.md § Operational).

Headline tiles, an inherent/residual heat matrix, a sortable/filterable register
table, attention lists, owner load, and a per-risk drawer showing structured
acceptance and real change history. Everything is derived from the register file
passed in; nothing about a specific client is hardcoded.

Usage:
  python3 render_dashboard.py <register.rr> [out.html] [--today YYYY-MM-DD]
                              [--translations translations.json]
"""

import json
import sys

import _common as C

# Kept out of the f-string that uses it. An escaped quote inside an f-string expression
# only became legal in Python 3.12 (PEP 701); on the supported floor it is a SyntaxError
# that stops this module importing at all, so the whole working view disappears.
PROVTAG = ' <span class="provtag">unreworded</span>'


def build_data(ctx: C.Context) -> str:
    fields = ["id", "title", "description", "category", "owner", "status", "response",
              "inherent", "residual", "inherentExposure", "inherentBand", "residualExposure",
              "residualBand", "overAppetite", "outOfRange", "themeId", "themeName", "velocity",
              "priorExposure", "delta", "reviewDate", "reviewOverdue", "unowned", "acceptance",
              "acceptanceDue", "acceptanceExpired", "acceptanceIncomplete", "history",
              "translation",
              # Carried so the interactive table can mark what still needs review. The
              # working view shows provisional titles on purpose; it must not imply they
              # are board-ready.
              "provisionalTitle", "provisionalScore"]
    risks = [{**{k: r.get(k) for k in fields},
              "csfSubcategoryId": r.get("csfSubcategoryId", ""),
              "notes": r.get("notes", "")} for r in ctx.risks]
    blob = json.dumps({"meta": ctx.meta, "settings": ctx.settings, "risks": risks,
                       "today": ctx.today,
                       "baseline": ctx.baseline.get("label") if ctx.baseline else None})
    # Register text is user-authored: keep a stray "</script>" from ending the block early.
    return blob.replace("</", "<\\/")


def tiles(ctx: C.Context) -> str:
    s = ctx.summary
    prior = ctx.trend[-2]["overAppetite"] if len(ctx.trend) > 1 else None
    if prior is None:
        arrow, col, sub = "", C.SLATE, "no snapshot to compare against"
    else:
        d = s["overAppetite"] - prior
        arrow = C.VELOCITY_MARK["improving" if d < 0 else "worsening" if d > 0 else "steady"]
        col = C.VELOCITY_COLOR["improving" if d < 0 else "worsening" if d > 0 else "steady"]
        sub = f'was {prior} at {ctx.trend[-2]["label"]}'
    att = ctx.attention
    flagged = len({r["id"] for k in ("reviewOverdue", "acceptanceDue", "acceptanceExpired",
                                     "acceptanceIncomplete", "unowned") for r in att[k]})
    live = s["total"] - s["closed"]
    cards = [
        (s["total"], "Risks tracked", f'{live} live · {s["closed"]} closed', "", C.INK),
        (f'{s["overAppetite"]} <span style="color:{col}">{arrow}</span>',
         "Over appetite", sub, "warn" if s["overAppetite"] else "", C.INK),
        (len(att["acceptanceDue"]), "Acceptances due for re-validation",
         f'{len(att["acceptanceExpired"])} past expiry', "", C.INK),
        (flagged, "Risks needing attention",
         f'{len(att["reviewOverdue"])} review overdue · {len(att["unowned"])} unowned', "", C.INK),
    ]
    out = "".join(f'<div class="tile {cls}"><div class="n">{n}</div><div class="l">{lab}</div>'
                  f'<div class="s">{sub2}</div></div>' for n, lab, sub2, cls, _ in cards)
    pills = "".join(
        f'<div class="bandpill" style="background:{C.BAND[b]};'
        f'color:{"#fff" if b in ("high", "critical") else C.INK}">'
        f'<span class="bn">{s["byBand"][b]}</span>{C.BAND_LABEL[b]}</div>'
        for b in ["low", "medium", "high", "critical"])
    return f'<div class="tiles">{out}</div><div class="bandrow">{pills}</div>'


def attention_lists(ctx: C.Context) -> str:
    a = ctx.attention
    groups = [
        ("Over appetite", a["overAppetite"], C.BAND["critical"],
         lambda r: f'residual {r["residualExposure"]} {C.BAND_LABEL[r["residualBand"]]}'),
        ("Review overdue", a["reviewOverdue"], C.BAND["high"],
         lambda r: f'review due {r["reviewDate"]}'),
        ("Acceptances due for re-validation", a["acceptanceDue"], C.BAND["high"],
         lambda r: f're-validate by {r["acceptance"].get("revalidationDate")} '
                   f'· {C.esc(r["acceptance"].get("approver") or "no approver")}'),
        ("Acceptance past expiry", a["acceptanceExpired"], C.BAND["critical"],
         lambda r: f'expired {r["acceptance"].get("expiryDate")}'),
        ("Acceptance incomplete", a["acceptanceIncomplete"], C.BAND["critical"],
         lambda r: "missing approver or justification"),
        ("Unowned", a["unowned"], C.SLATE, lambda r: "no owner assigned"),
        ("Scored above the matrix", a["outOfRange"], C.SLATE,
         lambda r: "excluded from the heat matrix"),
    ]
    cards = ""
    for title, rs, colour, detail in groups:
        if not rs:
            continue
        # Working view: show the real title even when provisional. This is the screen the
        # CISO rewords *from* — withholding it here would hide the very text that needs
        # fixing. The tag says it is not board-eligible yet; the board renderers withhold.
        #
        # The tag is a module constant rather than an inline literal on purpose: a
        # backslash-escaped quote inside an f-string expression is a hard SyntaxError
        # before Python 3.12, and this file would not import at all on the floor we
        # support. See PROVTAG.
        items = "".join(f'<li><b>{r["id"]}</b> {C.esc(r["title"])}'
                        f'{PROVTAG if r.get("provisionalTitle") else ""}'
                        f'<span class="d">{detail(r)}</span></li>' for r in rs)
        cards += (f'<div class="att" style="border-left-color:{colour}">'
                  f'<h3>{title} <span class="cnt">{len(rs)}</span></h3>'
                  f'<ul class="plain">{items}</ul></div>')
    if not cards:
        cards = ('<div class="att" style="border-left-color:' + C.BAND["low"] + '">'
                 '<h3>Nothing flagged</h3><p class="d">No risk is over appetite, past review, '
                 'unowned, or carrying a stale acceptance.</p></div>')
    return cards


def owner_table(ctx: C.Context) -> str:
    rows = "".join(
        f'<tr><td>{C.esc(o["owner"])}</td><td>{o["count"]}</td>'
        f'<td>{C.chip(o["worst"])}</td>'
        f'<td>{o["over"] or ""}{" ⚠" if o["over"] else ""}</td>'
        f'<td>{o["exposure"]}</td></tr>' for o in ctx.owner_load)
    return (f'<table class="reg"><thead><tr><th>Owner</th><th>Open risks</th><th>Worst residual</th>'
            f'<th>Over appetite</th><th>Total residual exposure</th></tr></thead>'
            f'<tbody>{rows}</tbody></table>')


CSS = f"""
*{{box-sizing:border-box}}body{{margin:0;font-family:'Manrope',system-ui,sans-serif;
  background:{C.WB};color:{C.INK}}}
h1,h2,h3{{font-family:'Space Grotesk','Manrope',sans-serif;margin:0}}
.wrap{{max-width:1180px;margin:0 auto;padding:0 24px 48px}}
header{{background:{C.INK};color:{C.LIME};padding:18px 0}}
header .wrap{{display:flex;align-items:center;justify-content:space-between;gap:16px;
  flex-wrap:wrap;padding-bottom:0}}
.brand{{display:flex;align-items:center;gap:12px}}
.mark{{width:30px;height:30px;border-radius:7px;
  background:linear-gradient(135deg,{C.PATINA},{C.PATINA_H});position:relative;flex:0 0 auto}}
.mark::after{{content:"";position:absolute;inset:9px 8px;background:{C.INK};
  clip-path:polygon(0 40%,100% 0,100% 60%,0 100%)}}
.eyebrow{{color:{C.PATINA};font-size:11px;letter-spacing:.14em;text-transform:uppercase;
  font-weight:700}}
.brand h1{{font-size:19px}}
.meta{{text-align:right;font-size:12.5px;color:{C.LIME_DIM};line-height:1.5}}
.meta b{{color:{C.LIME}}}
.appetite{{background:{C.PATINA};color:{C.INK};font-weight:700;border-radius:999px;
  padding:2px 10px;font-size:12px}}
.sub{{background:{C.INK_RAISED};color:{C.LIME_DIM};font-size:12.5px}}
.sub.provisional{{background:{C.BAND["high"]}26;color:{C.LIME};
  border-bottom:1px solid {C.BAND["high"]}66}}
.placeholder{{color:{C.SLATE};font-style:italic}}
.provtag{{display:inline-block;background:{C.BAND["high"]}2e;color:{C.BAND["high"]};
  border-radius:999px;padding:1px 7px;font-size:10.5px;font-weight:700;white-space:nowrap}}
.placeholder code{{font-style:normal;font-family:'IBM Plex Mono',ui-monospace,monospace;
  font-size:11px}}
.sub .wrap{{padding:8px 24px;display:flex;justify-content:space-between;gap:16px;flex-wrap:wrap}}
.section{{margin-top:26px}}
.section h2{{font-size:15px;margin-bottom:12px}}
.tiles{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}}
.tile{{background:{C.WB_SURF};border:1px solid {C.WB_LINE};border-radius:12px;padding:14px 16px}}
.tile .n{{font-family:'Space Grotesk',sans-serif;font-size:30px;font-weight:600;line-height:1}}
.tile .l{{color:{C.INK};font-size:12.5px;margin-top:6px;font-weight:600}}
.tile .s{{color:{C.SLATE};font-size:11.5px;margin-top:2px}}
.tile.warn{{border-color:{C.BAND['high']}}}
.bandrow{{display:flex;gap:8px;margin-top:12px}}
.bandpill{{flex:1;border-radius:8px;padding:8px;text-align:center;font-size:12px}}
.bandpill .bn{{font-family:'Space Grotesk';font-size:19px;font-weight:600;display:block}}
.top{{display:grid;grid-template-columns:auto 1fr;gap:24px;align-items:start}}
.card{{background:{C.WB_SURF};border:1px solid {C.WB_LINE};border-radius:12px;padding:16px}}
.toggle{{display:inline-flex;border:1px solid {C.WB_LINE};border-radius:8px;overflow:hidden;
  margin-bottom:12px}}
.toggle button{{border:none;background:{C.WB_SURF};padding:6px 14px;font:inherit;font-size:12.5px;
  cursor:pointer;color:{C.SLATE}}}
.toggle button.on{{background:{C.INK};color:{C.LIME};font-weight:700}}
.matrix{{border-collapse:collapse}}
.matrix td.cell{{width:46px;height:46px;text-align:center;font-weight:700;font-size:14px;
  border:2px solid {C.WB};cursor:pointer;transition:transform .08s}}
.matrix td.cell:hover{{transform:scale(1.08);outline:2px solid {C.INK}}}
.matrix td.cell.sel{{outline:3px solid {C.INK};outline-offset:-3px}}
.matrix td.cell.dim{{opacity:.28}}
.matrix td.ax{{color:{C.SLATE};font-size:11px;padding:2px 6px}}
.axtitle{{color:{C.SLATE};font-size:11px;letter-spacing:.08em;text-transform:uppercase}}
.controls{{display:flex;align-items:center;gap:14px;margin-bottom:10px;flex-wrap:wrap}}
.fbtn{{border:1px solid {C.WB_LINE};background:{C.WB_SURF};color:{C.SLATE};border-radius:8px;
  padding:6px 12px;font:inherit;font-size:12.5px;cursor:pointer}}
.fbtn.on{{background:{C.BAND['high']};border-color:{C.BAND['high']};color:#fff;font-weight:700}}
.filterbar{{font-size:12.5px;color:{C.SLATE}}}
.filterbar .clear{{color:{C.PATINA};cursor:pointer;font-weight:700;text-decoration:underline;
  margin-left:8px}}
table.reg{{width:100%;border-collapse:collapse;font-size:12.5px;background:{C.WB_SURF};
  border:1px solid {C.WB_LINE};border-radius:12px;overflow:hidden}}
table.reg th{{background:{C.INK};color:{C.LIME};text-align:left;padding:9px 10px;font-size:11.5px;
  cursor:pointer;user-select:none;white-space:nowrap}}
table.reg th:hover{{color:#fff}}
table.reg th .ar{{color:{C.PATINA};margin-left:4px}}
table.reg tr.row{{cursor:pointer}}
table.reg tr.row:hover td{{background:#eef4f2}}
table.reg td{{padding:8px 10px;border-top:1px solid {C.WB_LINE}}}
.chip{{border-radius:999px;padding:2px 8px;font-size:11px;font-weight:700;white-space:nowrap}}
.flag{{color:{C.BAND['critical']};font-weight:700}}
.warnmark{{color:{C.BAND['high']};font-weight:700}}
.hint{{color:{C.SLATE};font-size:12px;font-style:italic;margin-top:6px}}
.attgrid{{display:grid;grid-template-columns:repeat(2,1fr);gap:12px;align-items:start}}
.att{{background:{C.WB_SURF};border:1px solid {C.WB_LINE};border-left:5px solid {C.SLATE};
  border-radius:10px;padding:12px 14px}}
.att h3{{font-size:12.5px;text-transform:uppercase;letter-spacing:.05em;color:{C.SLATE};
  margin-bottom:8px}}
.att h3 .cnt{{background:{C.INK};color:{C.LIME};border-radius:999px;padding:1px 8px;
  font-size:11px;margin-left:4px}}
.att li{{font-size:12.5px;line-height:1.45;margin-bottom:7px}}
.att .d{{color:{C.SLATE};display:block;font-size:11.5px}}
ul.plain{{list-style:none;padding:0;margin:0}}
.backdrop{{position:fixed;inset:0;background:rgba(20,23,28,.45);opacity:0;pointer-events:none;
  transition:opacity .2s;z-index:5}}
.backdrop.open{{opacity:1;pointer-events:auto}}
.drawer{{position:fixed;top:0;right:0;height:100%;width:460px;max-width:92vw;background:{C.WB};
  box-shadow:-8px 0 40px rgba(0,0,0,.25);transform:translateX(100%);transition:transform .22s;
  z-index:6;overflow-y:auto}}
.drawer.open{{transform:none}}
.dhead{{background:{C.INK};color:{C.LIME};padding:18px 20px;position:relative}}
.dhead .id{{color:{C.PATINA};font-weight:700;font-size:12px;letter-spacing:.1em}}
.dhead h2{{font-size:18px;margin-top:4px;line-height:1.25;padding-right:28px}}
.dclose{{position:absolute;top:14px;right:16px;background:none;border:none;color:{C.LIME};
  font-size:24px;cursor:pointer;line-height:1}}
.dbody{{padding:18px 20px}}
.kv{{display:grid;grid-template-columns:110px 1fr;gap:6px 12px;font-size:13px;margin-bottom:16px}}
.kv .k{{color:{C.SLATE}}}
.scores{{display:flex;gap:10px;margin-bottom:16px}}
.score{{flex:1;background:{C.WB_SURF};border:1px solid {C.WB_LINE};border-radius:10px;
  padding:10px 12px}}
.score .lab{{color:{C.SLATE};font-size:11px;text-transform:uppercase;letter-spacing:.05em}}
.score .val{{font-family:'Space Grotesk';font-size:20px;font-weight:600;margin-top:3px}}
.blk{{margin-bottom:16px}}
.blk h3{{font-size:12px;text-transform:uppercase;letter-spacing:.06em;color:{C.SLATE};
  margin-bottom:6px}}
.blk p{{margin:0;font-size:13px;line-height:1.5}}
.muted{{color:{C.SLATE};font-style:italic}}
.accept{{background:#fff;border:1px solid {C.WB_LINE};border-left:4px solid {C.BAND['low']};
  border-radius:8px;padding:10px 12px;font-size:12.5px;line-height:1.5}}
.accept.stale{{border-left-color:{C.BAND['critical']}}}
.hist{{border-left:2px solid {C.WB_LINE};padding-left:12px}}
.hist .ev{{margin-bottom:12px;font-size:12.5px}}
.hist .ev .t{{color:{C.SLATE};font-size:11px}}
.hist .ev .c{{font-weight:700}}
.hist .ev .r{{font-style:italic}}
footer{{margin-top:32px;color:{C.SLATE};font-size:11px;border-top:1px solid {C.WB_LINE};
  padding-top:14px}}
"""

SCRIPT = r"""
const DB=__DATA__;const BAND=__BAND__;const BL=__BANDLABEL__;
const size=DB.settings.matrixSize;const appetite=DB.settings.appetite;
const BAND_ORDER=["low","medium","high","critical"];
const THRESH={5:{low:1,medium:5,high:10,critical:15},4:{low:1,medium:4,high:8,critical:12},
  3:{low:1,medium:3,high:5,critical:7}}[size];
let view="residual",sel=null,overOnly=false,sortK="residualExposure",sortDir=-1;
const VELRANK={improving:0,steady:1,new:2,worsening:3};
const VELMARK={improving:"▼",worsening:"▲",steady:"→",new:"＋"};
const COLS=[{k:"id",l:"ID",t:"s"},{k:"title",l:"Risk",t:"s"},{k:"themeName",l:"Theme",t:"s"},
 {k:"response",l:"Response",t:"s"},{k:"exposure",l:"Exposure",t:"n"},{k:"velocity",l:"Trend",t:"n"},
 {k:"owner",l:"Owner",t:"s"},{k:"status",l:"Status",t:"s"},{k:"flags",l:"Flags",t:"s"}];
function bandOf(e){for(const b of ["critical","high","medium","low"])if(e>=THRESH[b])return b;return "low";}
function expOf(r){return r[view].likelihood*r[view].impact;}
function bandOfView(r){return bandOf(expOf(r));}
function isOver(r){return BAND_ORDER.indexOf(bandOfView(r))>BAND_ORDER.indexOf(appetite);}
function chip(b){const fg=(b==="high"||b==="critical")?"#fff":"#14171C";
  return `<span class="chip" style="background:${BAND[b]};color:${fg}">${BL[b]}</span>`;}
function inCell(r,l,i){return r[view].likelihood===l&&r[view].impact===i;}
function flagsOf(r){const f=[];
  if(r.reviewOverdue)f.push('<span class="warnmark" title="review overdue">⏱</span>');
  if(r.acceptanceDue||r.acceptanceExpired)f.push('<span class="flag" title="acceptance due for re-validation">↻</span>');
  if(r.acceptanceIncomplete)f.push('<span class="flag" title="acceptance incomplete">!</span>');
  if(r.unowned)f.push('<span class="warnmark" title="no owner">◌</span>');
  if(r.outOfRange)f.push('<span class="warnmark" title="scored above the matrix">↗</span>');
  return f.join(" ");}
function val(r,k){if(k==="exposure")return expOf(r);if(k==="velocity")return VELRANK[r.velocity];
  if(k==="response")return r.response.type;if(k==="flags")return flagsOf(r).length;return r[k];}
function filtered(){return DB.risks.filter(r=>(!sel||inCell(r,sel[0],sel[1]))&&(!overOnly||isOver(r)));}
function sorted(list){const c=COLS.find(x=>x.k===sortK)||{t:"n"};
  return list.slice().sort((a,b)=>{const x=val(a,sortK==="residualExposure"?"exposure":sortK),
    y=val(b,sortK==="residualExposure"?"exposure":sortK);
    return ((c.t==="n")?(x-y):String(x).localeCompare(String(y)))*sortDir;});}
function renderHead(){document.getElementById("head").innerHTML=COLS.map(c=>{
  const lab=c.k==="exposure"?(view==="residual"?"Residual":"Inherent"):c.l;
  const key=c.k==="exposure"?"exposure":c.k;
  const ar=key===sortK?`<span class="ar">${sortDir>0?"▲":"▼"}</span>`:"";
  return `<th onclick="setSort('${key}')">${lab}${ar}</th>`;}).join("");}
function renderGrid(){let h='<table class="matrix">';
 const inRange=DB.risks.filter(r=>!r.outOfRange);
 for(let impact=size;impact>=1;impact--){h+=`<tr><td class="ax">${impact}</td>`;
  for(let lik=1;lik<=size;lik++){const b=bandOf(lik*impact);
   const n=inRange.filter(r=>inCell(r,lik,impact)).length;
   const s=sel&&sel[0]===lik&&sel[1]===impact?" sel":(sel?" dim":"");
   const fg=(b==="high"||b==="critical")?"#fff":"#14171C";
   h+=`<td class="cell${s}" style="background:${BAND[b]};color:${fg}" onclick="pick(${lik},${impact})">${n||""}</td>`;}
  h+="</tr>";}
 h+='<tr><td class="ax"></td>';for(let l=1;l<=size;l++)h+=`<td class="ax">${l}</td>`;
 h+="</tr></table>";document.getElementById("grid").innerHTML=h;
 const skipped=DB.risks.length-inRange.length;
 document.getElementById("skip").innerHTML=skipped?
   `${skipped} risk${skipped>1?"s":""} scored above the ${size}×${size} matrix and ${skipped>1?"are":"is"} not plotted (still counted in every total).`:"";}
function renderRows(){const list=sorted(filtered());
 document.getElementById("rows").innerHTML=list.map(r=>`<tr class="row" onclick="openDrawer('${r.id}')">
  <td>${r.id}</td><td>${r.title}${r.provisionalTitle?' <span class="provtag">unreworded</span>':''}</td><td>${r.themeName}</td><td>${r.response.type}</td>
  <td>${chip(bandOfView(r))} ${expOf(r)} ${isOver(r)?'<span class="flag">⚠</span>':''}</td>
  <td style="color:${{improving:BAND.low,worsening:BAND.critical,steady:"#6A7180",new:"#2FA98C"}[r.velocity]}"
    title="${r.priorExposure===null?"no baseline":"was "+r.priorExposure+" at "+DB.baseline}">${VELMARK[r.velocity]}</td>
  <td>${r.owner||'<span class="muted">unowned</span>'}</td><td>${r.status}</td>
  <td>${flagsOf(r)}</td></tr>`).join("");
 const parts=[`${list.length} of ${DB.risks.length} risks · ${view} view`];
 if(sel)parts.push(`cell L${sel[0]}×I${sel[1]}`);if(overOnly)parts.push("over appetite only");
 document.getElementById("filter").innerHTML=parts.join(" · ")+
   ((sel||overOnly)?`<span class="clear" onclick="clearFilters()">clear filters</span>`:"");}
function draw(){renderHead();renderGrid();renderRows();}
function pick(l,i){sel=(sel&&sel[0]===l&&sel[1]===i)?null:[l,i];draw();}
function toggleOver(){overOnly=!overOnly;
 document.getElementById("overBtn").classList.toggle("on",overOnly);draw();}
function clearFilters(){sel=null;overOnly=false;
 document.getElementById("overBtn").classList.remove("on");draw();}
function setSort(k){const c=COLS.find(x=>x.k===k||(k==="exposure"&&x.k==="exposure"))||{t:"n"};
 if(sortK===k)sortDir=-sortDir;else{sortK=k;sortDir=(c.t==="n")?-1:1;}draw();}
function setView(v){view=v;sel=null;
 document.getElementById("bRes").classList.toggle("on",v==="residual");
 document.getElementById("bInh").classList.toggle("on",v==="inherent");draw();}
function openDrawer(id){const r=DB.risks.find(x=>x.id===id);const d=document.getElementById("drawer");
 const acc=r.acceptance;const stale=r.acceptanceDue||r.acceptanceExpired||r.acceptanceIncomplete;
 const accNote=r.acceptanceExpired?"past expiry":r.acceptanceDue?"due for re-validation":
   r.acceptanceIncomplete?"incomplete":"";
 d.innerHTML=`<div class="dhead"><button class="dclose" onclick="closeDrawer()">×</button>
   <div class="id">${r.id} · ${r.themeName}${r.provisionalTitle?' · <span class="provtag">title not reworded — withheld from board views</span>':''}${r.provisionalScore?' · <span class="provtag">score is an import seed</span>':''}</div><h2>${r.title}</h2></div><div class="dbody">
   <div class="scores">
     <div class="score"><div class="lab">Inherent</div><div class="val">${r.inherent.likelihood}×${r.inherent.impact}=${r.inherentExposure}</div>${chip(r.inherentBand)}</div>
     <div class="score"><div class="lab">Residual</div><div class="val">${r.residual.likelihood}×${r.residual.impact}=${r.residualExposure}</div>${chip(r.residualBand)} ${r.overAppetite?'<span class="flag">⚠ over</span>':''}</div></div>
   <div class="kv"><span class="k">Category</span><span>${r.category||"—"}</span>
     <span class="k">Owner</span><span>${r.owner||'<span class="muted">unowned</span>'}</span>
     <span class="k">Status</span><span>${r.status}</span>
     <span class="k">Review</span><span>${r.reviewDate||"—"}${r.reviewOverdue?' <span class="warnmark">overdue</span>':''}</span>
     <span class="k">Since ${DB.baseline||"baseline"}</span><span>${r.priorExposure===null?'<span class="muted">no baseline</span>':`${r.priorExposure} → ${r.residualExposure} ${VELMARK[r.velocity]}`}</span>
     <span class="k">CSF</span><span>${r.csfSubcategoryId||"—"}</span></div>
   <div class="blk"><h3>Risk (event statement)</h3><p>${r.description||'<span class="muted">No event statement recorded.</span>'}</p></div>
   <div class="blk"><h3>Response — ${r.response.type}${r.response.cost?` · $${r.response.cost.toLocaleString()}`:''}</h3><p>${r.response.description||'<span class="muted">—</span>'}</p></div>
   ${acc?`<div class="blk"><h3>Acceptance ${accNote?`· <span style="color:${BAND.critical}">${accNote}</span>`:''}</h3>
     <div class="accept${stale?' stale':''}"><b>${acc.approver||'<span class="flag">no approver recorded</span>'}</b> · accepted ${acc.acceptedDate||"—"} · re-validate by ${acc.revalidationDate||"—"}${acc.expiryDate?` · expires ${acc.expiryDate}`:''}<br>${acc.justification||'<span class="flag">no justification recorded</span>'}</div></div>`:''}
   ${r.translation?`<div class="blk"><h3>Board translation</h3><p>${r.translation}</p></div>`:''}
   ${r.notes?`<div class="blk"><h3>Notes</h3><p>${r.notes}</p></div>`:''}
   <div class="blk"><h3>Change history</h3>${r.history.length?`<div class="hist">${r.history.slice().reverse().map(h=>{
     const move=(h.from!==undefined&&h.to!==undefined)?
       `${h.field||""} ${fmt(h.from)} → ${fmt(h.to)}`:(h.field||h.type);
     return `<div class="ev"><div class="t">${(h.ts||"").slice(0,10)} · ${h.actor||"—"} · ${h.type}</div>
       <div class="c">${move}</div>${h.rationale?`<div class="r">${h.rationale}</div>`:''}</div>`;}).join("")}</div>`
     :'<p class="muted">No logged changes yet.</p>'}</div>
   </div>`;
 d.classList.add("open");document.getElementById("backdrop").classList.add("open");}
function fmt(v){return (v&&typeof v==="object")?`${v.likelihood}×${v.impact}=${v.likelihood*v.impact}`:v;}
function closeDrawer(){document.getElementById("drawer").classList.remove("open");
 document.getElementById("backdrop").classList.remove("open");}
document.addEventListener("keydown",e=>{if(e.key==="Escape")closeDrawer();});
draw();
"""


def render(ctx: C.Context) -> str:
    m, s = ctx.meta, ctx.settings
    script = (SCRIPT.replace("__DATA__", build_data(ctx))
              .replace("__BANDLABEL__", json.dumps(C.BAND_LABEL))
              .replace("__BAND__", json.dumps(C.BAND)))
    client = C.esc(m.get("clientName") or "")
    title_tail = " · " + client if client else ""
    note = C.provisional_note(ctx.summary)
    prov_banner = (f'<div class="sub provisional"><div class="wrap">{note}</div></div>'
                   if note else "")
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Risk Register — Working View{title_tail}</title>
{C.fonts(ctx.offline)}<style>{CSS}</style></head><body>
<header><div class="wrap"><div class="brand"><div class="mark"></div><div>
  <div class="eyebrow">Cyber Aware Creations · Risk Register</div>
  <h1>Heat map &amp; register — working view</h1></div></div>
  <div class="meta"><b>{C.esc(m.get('clientName') or '(unnamed register)')}</b><br>
  {C.esc(m.get('assessor') or '—')}<br>
  <span class="appetite">Appetite: {C.esc(s['appetite'])}</span>
  &nbsp;{s['matrixSize']}×{s['matrixSize']} matrix</div></div></header>
<div class="sub"><div class="wrap"><span>{C.esc(ctx.as_of_line())}</span>
  <span>Toggle inherent / residual · click a cell to drill in · sort any column · click a risk for detail</span>
</div></div>
{prov_banner}
<div class="wrap">
  <div class="section">{tiles(ctx)}</div>
  <div class="section top">
    <div class="card">
      <div class="toggle"><button id="bRes" class="on" onclick="setView('residual')">Residual</button>
        <button id="bInh" onclick="setView('inherent')">Inherent</button></div>
      <div class="axtitle">↑ Impact</div><div id="grid"></div>
      <div class="axtitle" style="text-align:right">Likelihood →</div>
      <div class="hint" id="skip"></div>
    </div>
    <div>
      <div class="controls">
        <button id="overBtn" class="fbtn" onclick="toggleOver()">⚠ Over appetite only</button>
        <span class="filterbar" id="filter"></span>
      </div>
      <table class="reg"><thead><tr id="head"></tr></thead><tbody id="rows"></tbody></table>
      <div class="hint">Flags: ⏱ review overdue · ↻ acceptance due for re-validation ·
        ! acceptance incomplete · ◌ unowned · ↗ scored above the matrix.</div>
    </div>
  </div>
  <div class="section"><h2>Needs attention</h2>
    <div class="attgrid">{attention_lists(ctx)}</div></div>
  <div class="section"><h2>Owner load — open risk per owner</h2>{owner_table(ctx)}</div>
  <footer>{C.esc(ctx.footer("operational working view"))}</footer>
</div>
<div class="backdrop" id="backdrop" onclick="closeDrawer()"></div>
<div class="drawer" id="drawer"></div>
<script>{script}</script></body></html>"""


if __name__ == "__main__":
    ctx = C.build(sys.argv[1:], __doc__, "risk-register-working-view.html")
    C.write(ctx, render(ctx))
