#!/usr/bin/env python3
"""Crosswalk coverage report — one CSF assessment, read through other frameworks.

Consumes `profile_analysis.py analyze <store> --crosswalk <id> ...` output and
renders a lens per crosswalk. Every view is a PROJECTION of an existing CSF
assessment: nothing here is an audit, a certification, or a rating of the other
framework's controls.

Three things this renderer will not do, each for a stated reason:

- It never prints a band word without the scale it was computed against. "moderate"
  is meaningless until you know whether the Profile rates 0-3 or 0-4, and the two
  are not comparable (references/scale-and-scoring.md).
- It never encodes a band by colour alone. Every heatmap cell and every table row
  carries the band word as text, so the report survives greyscale printing,
  colour-vision deficiency, and forced-colours mode.
- It never shows ISO or CIS control titles. Those are copyrighted; the labels here
  are our own paraphrases, and the label source is stated per lens.
"""
import json
import sys

import _common as c

CSS = f"""
.lensmeta{{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:12px}}
.lensmeta .chip{{background:{c.WB_SURF};border:1px solid {c.WB_LINE};color:{c.SLATE};
  font-weight:600}}
.derived{{background:{c.WB_SURF};border:1px solid {c.WB_LINE};border-left:3px solid {c.PATINA};
  border-radius:8px;padding:10px 14px;font-size:13px;margin-bottom:16px}}
.tiles{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px}}
.tile{{background:{c.WB_SURF};border:1px solid {c.WB_LINE};border-radius:10px;padding:12px 14px}}
.tile .n{{font-family:'Space Grotesk',system-ui,sans-serif;font-size:24px;font-weight:600;
  line-height:1.1}}
.tile .k{{color:{c.SLATE};font-size:12px;margin-top:4px}}
.heat{{display:grid;grid-template-columns:repeat(auto-fill,minmax(168px,1fr));gap:8px}}
.cell{{border-radius:9px;padding:10px 12px;border:1px solid {c.WB_LINE}}}
.cell .gid{{font-family:'IBM Plex Mono',ui-monospace,monospace;font-size:11.5px;
  font-weight:600;letter-spacing:.02em}}
.cell .band{{font-size:12px;font-weight:700;margin-top:5px}}
.cell .lab{{font-size:11.5px;margin-top:3px;line-height:1.35}}
.cell.unknown{{background:repeating-linear-gradient(45deg,{c.WB_LINE},{c.WB_LINE} 4px,
  {c.WB} 4px,{c.WB} 8px);color:{c.SLATE}}}
.bandchip{{display:inline-block;padding:2px 8px;border-radius:999px;font-size:11px;
  font-weight:700;white-space:nowrap}}
.subs{{font-family:'IBM Plex Mono',ui-monospace,monospace;font-size:11.5px;color:{c.SLATE}}}
.lookup{{display:flex;gap:8px;flex-wrap:wrap;align-items:center}}
.lookup input,.lookup select{{font:inherit;font-size:13px;padding:7px 10px;
  border:1px solid {c.WB_LINE};border-radius:8px;background:{c.WB_SURF};color:{c.INK}}}
.lookup input{{min-width:220px}}
#lkout{{margin-top:12px}}
#lkout table{{margin-top:8px}}
.tabs>input{{position:absolute;opacity:0;pointer-events:none}}
.tablabels{{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:16px;
  border-bottom:1px solid {c.WB_LINE};padding-bottom:0}}
.tablabels label{{cursor:pointer;padding:8px 14px;font-size:13px;font-weight:600;
  color:{c.SLATE};border:1px solid transparent;border-bottom:none;border-radius:8px 8px 0 0;
  margin-bottom:-1px}}
.panel{{display:none}}
{" ".join(f'.tabs>input#lens-{i}:checked~.tablabels label[for="lens-{i}"]'
          f'{{background:{c.WB_SURF};border-color:{c.WB_LINE};color:{c.INK}}}'
          for i in range(8))}
{" ".join(f'.tabs>input#lens-{i}:checked~.panels>.panel-{i}{{display:block}}'
          for i in range(8))}
@media print{{
  .panel{{display:block !important;break-before:page}}
  .tablabels,.lookup{{display:none}}
  .cell,.tile{{border:1px solid #999}}
}}
"""

# The reverse-lookup box is the only scripted thing here. Everything else is
# server-rendered so the report is complete with scripting unavailable, in print,
# and in a PDF — the lookup degrades to absent, not to broken.
LOOKUP_JS = """
(function(){
  var DATA = window.__CROSSWALKS__ || {};
  var lens = document.getElementById('lklens');
  var ctl  = document.getElementById('lkctl');
  var out  = document.getElementById('lkout');
  var list = document.getElementById('lkopts');
  function esc(s){ return String(s==null?'':s).replace(/[&<>"]/g,function(m){
    return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[m]; }); }
  function fillOptions(){
    var d = DATA[lens.value]; if(!d) return;
    list.innerHTML = Object.keys(d.controls).map(function(k){
      return '<option value="'+esc(k)+'"></option>'; }).join('');
  }
  function render(){
    var d = DATA[lens.value];
    var q = (ctl.value||'').trim();
    if(!d || !q){ out.innerHTML = ''; return; }
    var hit = d.controls[q];
    if(!hit){
      var keys = Object.keys(d.controls).filter(function(k){
        return k.toLowerCase().indexOf(q.toLowerCase()) === 0; });
      if(keys.length === 1){ hit = d.controls[keys[0]]; q = keys[0]; }
    }
    if(!hit){
      out.innerHTML = '<div class="card muted">'+esc(q)+' is not a control in '+
        esc(d.name)+'. Check the identifier, or use the control table below.</div>';
      return;
    }
    var rows = (hit.subs||[]).map(function(sid){
      var s = d.subcategories[sid] || {};
      var rating = (s.current==null) ? 'not yet rated'
                 : (s.current + ' of ' + d.scaleMax);
      if(s.applicability && s.applicability !== 'in-scope'){ rating = 'not applicable'; }
      return '<tr><td class="mono">'+esc(sid)+'</td><td>'+esc(rating)+
             '</td><td>'+esc(s.text||'')+'</td></tr>';
    }).join('');
    var head = '<div class="card"><strong>'+esc(q)+'</strong> '+esc(hit.label||'')+
      '<div class="muted" style="font-size:12.5px;margin-top:6px">'+
      (!(hit.subs && hit.subs.length)
        ? 'No CSF Subcategory maps to this control &mdash; assess it directly against '+
          'the standard.'
        : hit.suppressed
        ? 'Too little of this control&rsquo;s basis is rated to band it: only '+
          esc(hit.rated)+' of '+esc(hit.basis)+' mapped CSF outcomes have a rating. '+
          'The figure is withheld rather than shown with a caveat.'
        : 'Derived <strong>'+esc(hit.band)+'</strong>'+
          (hit.score==null ? '' : ' (weakest link, '+esc(hit.score)+' of '+esc(d.scaleMax)+')')+
          ' from the CSF outcomes below. Not an audit or certification.')+
      '</div></div>';
    out.innerHTML = head + (rows
      ? '<div class="scroll"><table><thead><tr><th>CSF Subcategory</th><th>Rating</th>'+
        '<th>Outcome</th></tr></thead><tbody>'+rows+'</tbody></table></div>'
      : '');
  }
  lens.addEventListener('change', function(){ fillOptions(); render(); });
  ctl.addEventListener('input', render);
  // Follow the visible tab. Without this, a reader looking at the 800-53 panel
  // types AU-6 into a box still set to ISO and is told AU-6 is not an ISO
  // control — true, unhelpful, and easy to read as the report being wrong.
  var order = window.__CROSSWALK_ORDER__ || [];
  Array.prototype.forEach.call(
    document.querySelectorAll('.tabs > input[type=radio]'), function(r, i){
      r.addEventListener('change', function(){
        if(r.checked && order[i] && DATA[order[i]]){
          lens.value = order[i]; fillOptions(); render();
        }
      });
    });
  fillOptions();
})();
"""


def band_chip(band: str) -> str:
    """A band as a chip. The word is always present; colour is the second channel."""
    fill = c.crosswalk_fill(band)
    label = c.CROSSWALK_BAND_LABEL.get(band, band)
    if band in c.CROSSWALK_OFF_RAMP:
        return f'<span class="bandchip untargeted">{c.esc(label)}</span>'
    return (f'<span class="bandchip" style="background:{fill};color:{c.text_on(fill)}">'
            f'{c.esc(label)}</span>')


def scale_sentence(block: dict) -> str:
    scale = block.get("scale") or {}
    lo, hi = scale.get("min"), scale.get("max")
    agg = (block.get("aggregation") or {}).get("control", "min")
    rule = ("the weakest of the CSF outcomes mapped to it"
            if agg == "min" else "the mean of the CSF outcomes mapped to it")
    return (f"Bands are a share of this Profile&rsquo;s {lo}&ndash;{hi} rating scale. "
            f"A control scores {rule}; a theme is the mean of its member controls. "
            f"Scores from a {lo}&ndash;{hi} Profile and a differently-scaled one are not "
            f"comparable.")


def lens_meta(block: dict) -> str:
    cat_bits = [
        f'authority: {block.get("mappingAuthority") or "unstated"}',
        f'labels: {"our own paraphrases" if block.get("license") != "public-domain" else "verbatim (public domain)"}',
        f'licence: {block.get("license") or "unstated"}',
    ]
    chips = "".join(f'<span class="chip">{c.esc(b)}</span>' for b in cat_bits)
    return f'<div class="lensmeta">{chips}</div>'


def tiles(block: dict) -> str:
    controls = block["controls"]
    comp = block.get("completeness") or {}
    rated = [x for x in controls if x["score"] is not None]
    cells = [
        (f"{len(rated)} of {len(controls)}", "mapped controls with a rating behind them"),
        (str(comp.get("controlsTotal", len(controls))), "controls in this framework"),
        (str(len(comp.get("controlsOutsideCSF") or [])), "controls no CSF outcome reaches"),
        (str(len(comp.get("csfNotInLens") or [])), "rated CSF outcomes this lens cannot see"),
    ]
    return ('<div class="tiles">'
            + "".join(f'<div class="tile"><div class="n">{c.esc(n)}</div>'
                      f'<div class="k">{c.esc(k)}</div></div>' for n, k in cells)
            + "</div>")


def heatmap(block: dict) -> str:
    out = []
    for g in block["groupings"]:
        if not g["controlsScored"]:
            continue
        band = g["band"]
        fill = c.crosswalk_fill(band)
        off = band in c.CROSSWALK_OFF_RAMP
        klass = "cell unknown" if off else "cell"
        style = "" if off else f'style="background:{fill};color:{c.text_on(fill)}"'
        n = g["controlsScored"]
        # Kept out of the f-string: a nested same-quote f-string only parses on
        # 3.12+, and this file has to compile on the declared 3.9 floor.
        score_bit = "" if g["score"] is None else f" &middot; {g['score']}"
        plural = "" if n == 1 else "s"
        out.append(
            f'<div class="{klass}" {style}>'
            f'<div class="gid">{c.esc(g["groupingId"])}</div>'
            f'<div class="band">{c.esc(c.CROSSWALK_BAND_LABEL.get(band, band))}'
            f'{score_bit}</div>'
            f'<div class="lab">{c.esc(g.get("label") or "")} '
            f'<span style="opacity:.85">({n} control{plural})</span></div>'
            f'</div>')
    if not out:
        return ('<div class="card muted">No theme in this lens has a rated control behind '
                'it yet, so no theme coverage can be shown.</div>')
    # A grid of nothing but hatching reads as a broken report rather than as an
    # honest refusal, so when nothing is publishable the reason is stated instead.
    publishable = [g for g in block["groupings"] if g.get("score") is not None]
    if not publishable:
        thin = [g for g in block["groupings"] if g.get("bandSuppressed")]
        worst = max((g.get("basisPct") or 0) for g in thin) if thin else 0
        return ('<div class="card"><p style="margin:0 0 8px"><strong>No theme in this lens '
                'can be banded from this Profile yet.</strong> Every theme has too few '
                'controls with a rated basis behind them &mdash; the best is '
                f'{worst:.0f}% covered, under the '
                f'{int((block.get("suppression") or {}).get("thresholdPct", 60))}% threshold '
                'this Profile is set to.</p>'
                '<p style="margin:0" class="muted">This is the same judgement that '
                'withholds the headline CSF coverage figure on a sparsely-rated Profile: '
                'the projection is not wrong, there is simply not enough assessed behind it '
                'to characterise. Rate more Subcategories, or lower '
                '<span class="mono">reporting.scopeThresholdPct</span> deliberately.</p>'
                '</div>')
    return f'<div class="heat">{"".join(out)}</div>'


def control_table(block: dict) -> str:
    rows = []
    for x in block["controls"]:
        score = "&mdash;" if x["score"] is None else str(x["score"])
        notes = []
        # The unrated count qualifies a score; with no score the band already says
        # "not yet rated" and repeating it is noise on every unrated row.
        basis = x["ratedContributors"] + x["unratedContributors"]
        if x.get("bandSuppressed"):
            # The band is withheld, so the reason has to be legible here instead.
            notes.append(f'only {x["ratedContributors"]} of {basis} rated')
        elif x["unratedContributors"] and x["score"] is not None:
            notes.append(f'{x["unratedContributors"]} of {basis} not yet rated')
        # These two are never redundant: "not yet rated" and "deliberately scoped
        # out" are different facts, and an absent Subcategory is a third thing again.
        # Collapsing them into the band would hide a scope decision.
        if x["notApplicableContributors"]:
            notes.append(f'{x["notApplicableContributors"]} not applicable')
        if x["absentContributors"]:
            notes.append(f'{x["absentContributors"]} absent from the Profile')
        rows.append(
            f'<tr><td class="mono">{c.esc(x["controlId"])}</td>'
            f'<td>{c.esc(x.get("label") or "")}</td>'
            f'<td>{band_chip(x["band"])}</td>'
            f'<td class="mono">{score}</td>'
            f'<td class="subs">{c.esc(", ".join(x["mappedSubcategories"]))}</td>'
            f'<td class="muted" style="font-size:12px">{c.esc("; ".join(notes))}</td></tr>')
    return ('<div class="scroll"><table><thead><tr><th>Control</th><th>What it covers</th>'
            '<th>Derived</th><th>Score</th><th>From CSF</th><th>Caveats</th></tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></div>')


def honesty(block: dict) -> str:
    comp = block.get("completeness") or {}
    outside = comp.get("controlsOutsideCSF") or []
    not_in = comp.get("csfNotInLens") or []
    parts = []
    if outside:
        parts.append(
            f'<p><strong>{len(outside)} control'
            f'{"" if len(outside) == 1 else "s"} no CSF Subcategory maps to.</strong> '
            f'A CSF assessment says nothing about {"it" if len(outside) == 1 else "these"}; '
            f'assess {"it" if len(outside) == 1 else "them"} directly against the standard.</p>'
            f'<p class="subs">{c.esc(", ".join(outside))}</p>')
    elif (comp.get("catalogueScope") or "") == "full":
        parts.append('<p><strong>Every control in this framework is reachable from CSF.</strong> '
                     'This catalogue holds the full control set, so the list is empty because '
                     'nothing falls outside CSF.</p>')
    else:
        # The dangerous case: a blank here would read as full coverage when in fact
        # the rest of the framework simply is not catalogued.
        parts.append('<p><strong>This list cannot be produced for this framework.</strong> '
                     'The catalogue holds the controls the NIST CSF export references, not the '
                     'framework&rsquo;s full control set &mdash; so an empty list here means '
                     '<em>not enumerated</em>, not <em>none exist</em>.</p>'
                     + (f'<p class="muted" style="font-size:12.5px">{c.esc(comp.get("catalogueScopeNote") or "")}</p>'
                        if comp.get("catalogueScopeNote") else ''))
    coarse = comp.get("controlsCategoryOnly") or []
    if coarse:
        # Deliberately its own paragraph rather than a footnote on the list above:
        # these are the controls a reader would otherwise be told to go assess from
        # scratch, when CSF does reach them — just not at a grain this can score.
        parts.append(
            f'<p><strong>{len(coarse)} control'
            f'{"" if len(coarse) == 1 else "s"} CSF reaches only at Category level.</strong> '
            f'The source names {"it" if len(coarse) == 1 else "them"} against a Category '
            f'rather than a Subcategory, so there is no rating at the right grain to project '
            f'&mdash; but {"it is" if len(coarse) == 1 else "they are"} not outside CSF, and '
            f'{"it does" if len(coarse) == 1 else "they do"} not belong on the list above.</p>'
            f'<p class="subs">{c.esc(", ".join(coarse))}</p>')
    if not_in:
        parts.append(
            f'<p><strong>{len(not_in)} rated CSF outcome'
            f'{"" if len(not_in) == 1 else "s"} this lens cannot see.</strong> '
            f'Work already assessed that this projection gives no credit for.</p>'
            f'<p class="subs">{c.esc(", ".join(not_in))}</p>')
    else:
        parts.append('<p><strong>Every rated CSF outcome is visible somewhere in this '
                     'lens.</strong></p>')
    return f'<div class="card">{"".join(parts)}</div>'


def lens_title(block: dict, fid: str) -> str:
    """Name plus version, without repeating a version the name already carries.

    "ISO/IEC 27001:2022" already states its year, so appending frameworkVersion
    produced "ISO/IEC 27001:2022 2022".
    """
    name = (block.get("frameworkName") or fid).strip()
    ver = str(block.get("frameworkVersion") or "").strip()
    if not ver or ver in name:
        return name
    return f"{name} {ver}"


def lens_panel(fid: str, block: dict, idx: int) -> str:
    name = lens_title(block, fid)
    return (
        f'<div class="panel panel-{idx}">'
        f'<section><h2>{c.esc(name)}</h2>'
        f'<div class="hint">Projected from this CSF Profile &mdash; not an audit or '
        f'certification.</div>'
        f'{lens_meta(block)}'
        f'<div class="derived">{scale_sentence(block)}</div>'
        f'{tiles(block)}</section>'
        f'<section><h2>Theme coverage</h2>'
        f'<div class="hint">Each theme is the mean of its member controls. The band word is '
        f'on every cell, so the colour is never the only signal.</div>'
        f'{heatmap(block)}</section>'
        f'<section><h2>Controls</h2>'
        f'<div class="hint">Derived coverage per mapped control, weakest-link. '
        f'&ldquo;From CSF&rdquo; names the outcomes the figure came from.</div>'
        f'{control_table(block)}</section>'
        f'<section><h2>What this lens cannot tell you</h2>'
        f'<div class="hint">Both directions, reported rather than hidden.</div>'
        f'{honesty(block)}</section>'
        f'</div>')


def lookup_section(crosswalks: dict) -> str:
    payload = {}
    for fid, block in crosswalks.items():
        payload[fid] = {
            "name": f'{block.get("frameworkName") or fid}',
            "scaleMax": (block.get("scale") or {}).get("max"),
            "subcategories": block.get("subcategories") or {},
            "controls": {x["controlId"]: {"label": x.get("label"),
                                          "band": c.CROSSWALK_BAND_LABEL.get(x["band"], x["band"]),
                                          "score": x["score"],
                                          "suppressed": bool(x.get("bandSuppressed")),
                                          "rated": x["ratedContributors"],
                                          "basis": x["ratedContributors"] + x["unratedContributors"],
                                          "subs": x["mappedSubcategories"]}
                         for x in block["controls"]},
        }
    # Unmapped controls belong in the lookup too — "nothing maps here" is the
    # answer an auditor needs, and omitting them would look like a missing record.
    # Category-only controls need a record for the same reason, and a different
    # answer: "nothing maps here" would be wrong for them.
    for fid, block in crosswalks.items():
        comp = block.get("completeness") or {}
        for cid in comp.get("controlsOutsideCSF") or []:
            payload[fid]["controls"].setdefault(cid, {"label": "", "band": "not yet rated",
                                                      "score": None, "subs": []})
        for cid in comp.get("controlsCategoryOnly") or []:
            payload[fid]["controls"].setdefault(
                cid, {"label": "", "band": "reached only at CSF Category level",
                      "score": None, "subs": []})
    opts = "".join(f'<option value="{c.esc(f)}">{c.esc(b.get("frameworkName") or f)}</option>'
                   for f, b in crosswalks.items())
    blob = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    order = json.dumps(list(crosswalks)).replace("</", "<\\/")
    return (
        '<section><h2>Which CSF sits behind a control?</h2>'
        '<div class="hint">The auditor&rsquo;s direction. Type a control identifier &mdash; '
        'for example A.8.9, CIS 1.1, or AU-6.</div>'
        '<div class="card"><div class="lookup">'
        f'<select id="lklens" aria-label="Framework">{opts}</select>'
        '<input id="lkctl" list="lkopts" placeholder="Control identifier" '
        'aria-label="Control identifier">'
        '<datalist id="lkopts"></datalist>'
        '</div><div id="lkout"></div></div></section>'
        f'<script>window.__CROSSWALKS__={blob};window.__CROSSWALK_ORDER__={order};</script>'
        f'<script>{LOOKUP_JS}</script>')


def main(argv):
    ctx = c.build(argv, "Crosswalk coverage report (CSF projected onto other frameworks)",
                  "csf-crosswalk.html")
    if not ctx.crosswalks:
        raise SystemExit(
            "error: this analysis JSON carries no crosswalk lenses. Regenerate it with\n"
            "  profile_analysis.py analyze <store.csfp> --crosswalk iso-27001-2022 "
            "[--crosswalk cis-8.1] ...\n"
            "Crosswalks are chosen when you report, so they are absent unless requested.")

    lenses = list(ctx.crosswalks.items())
    head = c.header("Crosswalk coverage", ctx,
                    [f'One assessment, {len(lenses)} '
                     f'lens{"" if len(lenses) == 1 else "es"} &middot; '
                     f'{c.esc(ctx.as_of_line())}'])

    inputs = "".join(f'<input type="radio" name="lens" id="lens-{i}"'
                     f'{" checked" if i == 0 else ""}>' for i in range(len(lenses)))
    labels = "".join(
        f'<label for="lens-{i}">'
        f'{c.esc(b.get("frameworkName") or f)}</label>'
        for i, (f, b) in enumerate(lenses))
    panels = "".join(lens_panel(f, b, i) for i, (f, b) in enumerate(lenses))

    intro = (
        '<section><div class="card">'
        '<p style="margin:0 0 8px">This report re-reads one NIST CSF assessment through '
        'other frameworks&rsquo; controls. Nothing here was assessed against those '
        'frameworks, and no control in them has been rated: each figure is derived from '
        'the CSF outcomes mapped to it.</p>'
        '<p style="margin:0" class="muted">It is therefore not an audit, not a '
        'certification, and not evidence of conformance. ISO and CIS control wording is '
        'ours, not theirs &mdash; identifiers are given so you can look up the official '
        'text in your own licensed copy.</p>'
        '</div></section>')

    # The CAC band only — no graphics marks. A crosswalk band is a third measure
    # again, and cac_graphics has no way to be handed CROSSWALK_BAND_FILL: every
    # palette it offers is either RAG or the MEASURE ramp, and borrowing either
    # would assert an equivalence with coverage or with risk severity that a
    # crosswalk band does not have. Inside <main>, for the reason stated in
    # render_executive.main.
    body = (head + "<main>" + c.band("Cyber Aware Creations", "Crosswalk lens")
            + intro
            + f'<div class="tabs">{inputs}<div class="tablabels">{labels}</div>'
              f'<div class="panels">{panels}</div></div>'
            + lookup_section(ctx.crosswalks)
            + "</main>"
            + f'<footer>{c.esc(ctx.footer())}</footer>')
    # page() already prepends BASE_CSS; pass only this renderer's additions.
    c.write(ctx, c.page(
        f'{ctx.profile.get("name", "CSF Profile")} — Crosswalk coverage',
        CSS, body, ctx.offline))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
