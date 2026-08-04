#!/usr/bin/env python3
"""
render_executive.py — the board view of a CSF Organizational Profile.

Reads the JSON emitted by `profile_analysis.py analyze` (stdin or --in) and writes one
self-contained, CAC-branded HTML file. Content spec: references/dashboards.md.

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


def headline_or_guard(ctx: c.Context) -> str:
    """Below the scope threshold the programme mean is SUPPRESSED, not caveated.

    A number with a warning beside it is still a number, and people read the number.

    Suppression is checked before anything else is unpacked: `ctx.coverage["overall"]`
    and `ctx.completeness["overall"]` are only needed on the non-suppressed path, and
    indexing them unconditionally would raise on a malformed-but-structurally-valid
    payload that this branch never reaches.
    """
    guard = (ctx.evidence.get("scopeGuard") or {})
    if guard.get("suppressed"):
        return (f'<section><div class="card guard">'
                f'<div class="gh">Coverage is not reported at this level of assessment</div>'
                f'<p style="margin:10px 0 0">{c.esc(guard.get("statement", ""))}</p>'
                f'<div class="muted" style="margin-top:8px">'
                f'Function-level figures below carry the counts they are drawn from, and '
                f'a Function with nothing targeted says so rather than showing a zero.'
                f'</div></div></section>')
    cov, comp = ctx.coverage["overall"], ctx.completeness["overall"]
    return (f'<section><div class="card">'
            f'<div style="font-size:30px;font-weight:700;'
            f'font-family:\'Space Grotesk\',sans-serif">{c.esc(c.cov_label(cov))}</div>'
            f'<div class="muted" style="margin-top:6px">overall coverage of Target · '
            f'{c.esc(c.completeness_line(comp))}</div></div></section>')


def evidence_block(ctx: c.Context) -> str:
    """Four-way coverage, age, and the revisit count — all four in the board view,
    not only the operational tables."""
    ev = ctx.evidence
    if not ev:
        return ""
    split = (ev.get("coverage") or {}).get("overall") or {}
    age = (ev.get("age") or {}).get("overall") or {}
    thr = (ev.get("age") or {}).get("thresholdDays")
    revisit = ev.get("revisit") or []

    # The revisit count must never be gated on age.dated. A rating with no
    # confirmedAt at all — every rating carried over from a v1 Profile, by design —
    # can still be flagged revisit (reason undated-confirmation): confirmedAt unset
    # is not the same fact as "nothing to revisit". Nesting the revisit cell inside
    # the dated-only branch was a second instance of the falsehood a final review
    # caught: a Profile with zero dated confirmations — a fresh v1 import, exactly
    # the audience this feature exists to onboard — could carry a real, non-zero
    # revisit count and the board would see no cell for it at all.
    #
    # Every value here is optional on a partially-populated payload — .get()
    # throughout, and a cell whose value is missing is dropped rather than
    # rendered blank or defaulted. The "older than N days" cell in particular only
    # appears when BOTH the threshold and the count are present: printing one
    # without the other would put a count on screen next to a threshold it was
    # never counted against.
    cells = []
    if age.get("dated"):
        if age.get("medianDays") is not None:
            cells.append(("median age", f'{age["medianDays"]} days'))
        if age.get("oldestDays") is not None:
            cells.append(("oldest", f'{age["oldestDays"]} days'))
        if thr is not None and age.get("olderThanThreshold") is not None:
            cells.append((f"older than {thr} days", f'{age["olderThanThreshold"]}'))
    # Counts both revisit reasons (derive_evidence): confirmedAt set with newer
    # material against it, and confirmedAt unset (a v1-migrated rating) with any
    # material against it at all — "newer" would overclaim the second, so the
    # label says "new" rather than "newer".
    cells.append(("ratings questioned by new material", f'{len(revisit)}'))
    age_html = ('<div class="agegrid">' + "".join(
        f'<div class="agecell"><div class="an">{c.esc(v)}</div>'
        f'<div class="muted">{c.esc(k)}</div></div>' for k, v in cells) + '</div>')
    # The band distribution grades the same population the `older than T days` cell above
    # counts — `beyond` + `wellBeyond` IS that figure, an identity the engine asserts. So
    # it goes below the grid as one strip rather than in it as four more tiles, which
    # would have set five numbers side by side with no denominator among them.
    if thr is not None:
        age_html += c.age_band_bar(age, thr)
    if age.get("dated"):
        if age.get("undated"):
            age_html += (f'<div class="muted" style="margin-top:8px">'
                         f'{age["undated"]} confirmed ratings carry no confirmation date and '
                         f'are excluded from these figures.</div>')
    else:
        age_html += (f'<div class="muted" style="margin-top:10px">No rating in this Profile '
                     'carries a confirmation date yet, so there is no age to report beyond the '
                     'revisit count above. Age reporting begins as ratings are confirmed with a '
                     'source and a date.</div>')

    return (f'<section><h2>How much of this is known, and how old is it</h2>'
            f'<div class="hint">Ratings do not expire. Age is reported and the reader '
            f'judges — a governance outcome and an asset inventory go stale at completely '
            f'different rates.</div>'
            f'<div class="card">{c.evidence_bar(split)}{age_html}</div></section>')


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
    # The mark is handed no `sev`, which is what keeps a coverage bar out of the RAG
    # ramp — see the block comment above c.coverage_bar. It sits above the tiles as
    # the comparison across Functions; the tiles remain the record, because they are
    # what carry the completeness line and the "not yet targeted" wording.
    return (f'<section><h2>Where the programme stands</h2>'
            f'<div class="hint">Coverage of the Target this organisation set for itself — '
            f'not a score against an external benchmark. Movement is versus the last review.</div>'
            f'{c.legend()}'
            f'{c.coverage_bar(ctx)}'
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
    # This list is attention.largestGaps, which analyze computes fresh — it is
    # NOT the reordered gap table. The note says so rather than leaving a reader
    # to assume the overlay reached here too.
    ov_note = c.overlay_note(ctx, reordered=False)
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
            f'{ov_note}'
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
    board_tr = [d for d in ctx.tr.decisions
                if not (isinstance(d, dict) and d.get("altitude") == "management")]
    mgmt_tr = [d for d in ctx.tr.decisions
               if isinstance(d, dict) and d.get("altitude") == "management"]
    out.extend(board_tr)

    if not out and not mgmt_tr:
        return ""
    dtext = lambda d: d.get("text") if isinstance(d, dict) else d  # noqa: E731
    lis = "".join(f"<li>{c.esc(dtext(x))}</li>" for x in out)
    result = (f'<section><h2>Decisions needed</h2>'
              f'<div class="card"><ul class="decisions">{lis}</ul></div></section>')
    if mgmt_tr:
        mgmt_lis = "".join(f"<li>{c.esc(dtext(d))}</li>" for d in mgmt_tr)
        result += (f'<section><h2>Management actions — not for board decision</h2>'
                   f'<div class="card"><ul class="decisions">{mgmt_lis}</ul></div></section>')
    return result


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
/* min-width:0 because a flex item defaults to min-width:auto — min-content — so the
   longest tier label ("Risk Informed") props the row open and the page with it. Same
   defect family as the grid fix in 0.1.6 and the report fix in 0.1.7; this row was the
   one place it had not been applied. It only shows up where the label renders wider
   than it does on the author's machine, which is any box without the brand fonts. */
.step{{flex:1;min-width:0;border:1px solid {c.WB_LINE};border-radius:8px;padding:8px;
  text-align:center;background:{c.WB}}}
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
""" + c.EVIDENCE_CSS


def main(argv):
    ctx = c.build(argv, "Executive CSF Profile dashboard", "csf-executive.html")
    p = ctx.profile

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

    # The CAC band opens the body proper. It sits inside <main> rather than above the
    # ink header: this skill's header() already carries the lockup and the AnvilMark,
    # and stacking a second ink block on top of it would read as a rendering fault
    # rather than as chrome. Here it works as the artifact kicker the sibling skills
    # get from the band alone.
    body = (head + "<main>" + c.band("Cyber Aware Creations", "Board view")
            + summary + headline_or_guard(ctx) + evidence_block(ctx)
            + rollup(ctx) + tier_block(ctx)
            + top_gaps(ctx) + what_changed(ctx) + decisions(ctx) + "</main>"
            + f'<footer>{c.esc(ctx.footer(ctx.overlay.get("provenance", "")))}</footer>')
    c.write(ctx, c.page(f'{p.get("name", "CSF Profile")} — Board View', CSS, body, ctx.offline))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
