#!/usr/bin/env python3
"""render_operational.py — the metrics review working view.

For the CISO and the team, not the board: every metric with its direction, latest reading,
movement, threshold status and reading age, followed by the attention lists a review works
through. No board language appears here at all — that belongs in render_executive.py.

Usage: python3 render_operational.py --in analysis.json [--out metrics-operational.html]
"""
from __future__ import annotations

import sys

import _common as C


def tiles(ctx: C.Context) -> str:
    att = ctx.attention
    cells = [
        (ctx.counts["metrics"], "metrics tracked"),
        (len(att["breached"]), "past a threshold"),
        (len(att["worsening"]), "moving the wrong way"),
        (len(att["stale"]), "past the review cadence"),
    ]
    out = "".join(f'<div class="tile"><span class="n">{n}</span>'
                  f'<span class="l">{C.esc(label)}</span></div>' for n, label in cells)
    return f'<div class="tiles">{out}</div>'


def table(ctx: C.Context) -> str:
    rows = []
    for r in ctx.metrics:
        thr = r["threshold"] or {}
        thr_text = " · ".join(
            f'{k} {C.fmt_value(thr[k], r["unit"])}'
            for k in ("target", "warn", "critical") if k in thr) or "—"
        age = "—" if r["ageDays"] is None else (
            f'{r["ageDays"]} d <span class="muted">· '
            f'{C.esc(C.AGE_LABEL.get(r["ageBand"], r["ageBand"] or ""))}</span>')
        links = ", ".join(r["csfSubcategoryIds"] + r["riskIds"]) or "—"
        flags = []
        if r["vanityRisk"]:
            flags.append("vanity risk")
        if not r["owner"]:
            flags.append("unowned")
        if r["archetype"] is None:
            flags.append("untagged")
        rows.append(
            f'<tr><td><strong>{C.esc(r["metricId"])}</strong><br>{C.esc(r["name"])}'
            f'<br><span class="muted">{C.esc(r["direction"])}'
            + (f' · {C.esc(r["archetype"])}' if r["archetype"] else "")
            + (f'<br>{C.esc(", ".join(flags))}' if flags else "") + "</span></td>"
            f'<td class="num">{C.fmt_value(r["value"], r["unit"])}'
            f'<br><span class="muted">{C.esc(r["period"] or "—")}</span></td>'
            f'<td class="num">{C.fmt_delta(r["delta"], r["unit"])}</td>'
            f'<td>{C.trend_cell(r["trend"])}</td>'
            f'<td>{C.status_chip(r["status"])}<br>'
            f'<span class="muted">{C.esc(thr_text)}</span></td>'
            f'<td>{age}</td>'
            f'<td>{C.esc(r["owner"] or "—")}<br>'
            f'<span class="muted">{C.esc(links)}</span></td></tr>')
    return ('<div class="scroll"><table><thead><tr>'
            '<th>Metric</th><th>Latest</th><th>Delta</th><th>Movement</th>'
            '<th>Against threshold</th><th>Reading age</th><th>Owner / links</th>'
            f'</tr></thead><tbody>{"".join(rows)}</tbody></table></div>')


def attention_lists(ctx: C.Context) -> str:
    # Each list states its own membership rule. A reader who disagrees with an item's
    # presence can then check the rule rather than guess at it.
    spec = [
        ("breached", "Past a threshold", "status is past warn or past critical"),
        ("worsening", "Moving the wrong way", "the latest reading is worse than the prior one, resolved through the metric's direction"),
        ("stale", "Past the review cadence", "the newest reading is more than the chosen cadence old — an age, not a judgement about whether the number is still true"),
        ("unmeasured", "No reading yet", "defined but never recorded"),
        ("unowned", "No owner", "no one is named against the metric"),
        ("untagged", "No archetype", "archetype is unset — 'custom' counts as a decision and does not appear here"),
        ("vanity", "Flagged as vanity risk", "the author marked this as a big number measuring effort rather than risk"),
    ]
    blocks = []
    for key, title, rule in spec:
        ids = ctx.attention.get(key) or []
        body = (f'<p class="muted">{C.esc(rule)}</p>'
                + (f'<ul class="list">'
                   + "".join(f'<li>{C.esc(i)} — {C.esc(_name(ctx, i))}</li>' for i in ids)
                   + "</ul>" if ids else '<p class="muted">None.</p>'))
        blocks.append(f'<div class="card"><h3>{C.esc(title)} ({len(ids)})</h3>{body}</div>')
    return "".join(blocks)


def _name(ctx: C.Context, mid: str) -> str:
    for r in ctx.metrics:
        if r["metricId"] == mid:
            return r["name"]
    return ""


def rollup_block(ctx: C.Context) -> str:
    by_arch = (ctx.rollups or {}).get("byArchetype") or {}
    if not by_arch:
        return ""
    rows = "".join(
        f'<tr><td>{C.esc(k)}</td><td class="num">{v["metrics"]}</td>'
        f'<td class="num">{v["breached"]}</td><td class="num">{v["worsening"]}</td></tr>'
        for k, v in sorted(by_arch.items()))
    return ('<h2>By archetype</h2>'
            '<p class="muted">Counts, never averages: a mean of a percentage, a day count '
            'and a currency figure is a number with no unit and no meaning.</p>'
            '<div class="scroll"><table><thead><tr><th>Archetype</th><th>Metrics</th>'
            '<th>Past a threshold</th><th>Worsening</th></tr></thead>'
            f'<tbody>{rows}</tbody></table></div>')


def main(argv=None) -> int:
    p = C.build_parser(__doc__.split("\n")[0], "metrics-operational.html")
    ctx = C.Context(p.parse_args(argv))
    client = ctx.meta.get("clientName") or "Metrics register"
    cad = f"{ctx.cadence}-day review cadence" if ctx.cadence else "no cadence set"
    body = (
        f'<h1>Metrics review — {C.esc(client)}</h1>'
        f'<p class="sub">{C.esc(ctx.counts["metrics"])} metrics · '
        f'{C.esc(ctx.counts["readings"])} readings · {C.esc(cad)} · '
        f'as at {C.esc(ctx.today)}</p>'
        + tiles(ctx)
        + '<h2>Every metric</h2>' + table(ctx)
        + rollup_block(ctx)
        + '<h2>Attention</h2>' + attention_lists(ctx)
        + ctx.footer())
    return C.write(ctx, C.page(f"Metrics review — {client}", body, ctx.offline),
                   f'{ctx.counts["metrics"]} metrics, '
                   f'{len(ctx.attention["breached"])} past a threshold')


if __name__ == "__main__":
    sys.exit(main())
