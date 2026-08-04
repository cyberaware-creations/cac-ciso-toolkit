#!/usr/bin/env python3
"""render_executive.py — the board view of the metrics section.

Board language is never invented here. Pass --translations with the output of the
ciso-board-translation skill; without it every narrative slot renders as a clearly
labelled placeholder, and the report says so rather than looking finished.

The sidecar conforms to skills/board-pack/references/section-contract.md: section
`metrics`, per-item map keyed by metric id. That makes this a drop-in section for the
board-pack assembler.

Usage: python3 render_executive.py --in analysis.json [--translations metrics.board.json]
"""
from __future__ import annotations

import sys

import _common as C


def summary_block(ctx: C.Context) -> str:
    if ctx.tr.executive_summary:
        return f'<div class="card"><p>{C.esc(ctx.tr.executive_summary)}</p></div>'
    return f'<div class="card"><div class="ph">{C.esc(C.PLACEHOLDER)}</div></div>'


def headline(ctx: C.Context) -> str:
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


def _priority(row: dict) -> tuple:
    """Board order: past critical first, then past warn, then worsening, then the rest.

    Ordering is deterministic and stated so the same register always produces the same
    deck. Within a rank, metric id — never the value, which would let a unit change
    reorder the page.
    """
    rank = {"critical": 0, "warn": 1}.get(row["status"], 3)
    if rank == 3 and row["trend"] == "slipping":
        rank = 2
    return (rank, row["metricId"])


def metric_blocks(ctx: C.Context) -> str:
    rows = sorted(ctx.metrics, key=_priority)
    out = []
    for r in rows:
        sentence = ctx.tr.metric(r["metricId"])
        narrative = (f'<p>{C.esc(sentence)}</p>' if sentence
                     else f'<div class="ph">No board sentence supplied for '
                          f'{C.esc(r["metricId"])}. The figures below are from the '
                          f'register; the language is not invented here.</div>')
        age = ("" if r["ageDays"] is None else
               f' · reading {r["ageDays"]} days old '
               f'({C.esc(C.AGE_LABEL.get(r["ageBand"], ""))})')
        out.append(
            f'<div class="card"><h3>{C.esc(r["name"])}</h3>'
            f'<p class="muted">{C.esc(r["metricId"])} · '
            f'{C.fmt_value(r["value"], r["unit"])} this period · '
            f'{C.fmt_delta(r["delta"], r["unit"])} on last · '
            f'{C.trend_cell(r["trend"])} · {C.status_chip(r["status"])}{age}</p>'
            f'{narrative}</div>')
    return "".join(out)


def _dtext(d): return d.get("text") if isinstance(d, dict) else d


def decisions_block(ctx: C.Context) -> str:
    board = [d for d in ctx.tr.decisions
             if not (isinstance(d, dict) and d.get("altitude") == "management")]
    mgmt = [d for d in ctx.tr.decisions
            if isinstance(d, dict) and d.get("altitude") == "management"]
    if board:
        items = "".join(f'<li>{C.esc(_dtext(d))}</li>' for d in board)
        out = f'<h2>Decisions</h2><div class="card"><ul class="list">{items}</ul></div>'
    else:
        out = ('<h2>Decisions</h2><div class="card"><div class="ph">'
               'No decisions supplied. Each board item should end on something to fund, '
               'accept, or decide; that language comes from the translation skill.'
               '</div></div>')
    if mgmt:
        mgmt_items = "".join(f'<li>{C.esc(_dtext(d))}</li>' for d in mgmt)
        out += (f'<h2>Management actions — not for board decision</h2>'
                f'<div class="card"><ul class="list">{mgmt_items}</ul></div>')
    return out


def main(argv=None) -> int:
    p = C.build_parser(__doc__.split("\n")[0], "metrics-executive.html")
    ctx = C.Context(p.parse_args(argv))
    client = ctx.meta.get("clientName") or "Metrics"
    as_of = ctx.tr.as_of or ctx.today
    # A sidecar dated differently from the analysis is surfaced, not smoothed over: two
    # dates in one board section is a real mistake a reader wants to see.
    drift = ""
    if ctx.tr.as_of and ctx.today and ctx.tr.as_of != ctx.today:
        drift = (f'<p class="sub">Note: the board narrative is dated '
                 f'{C.esc(ctx.tr.as_of)} and the figures are as at {C.esc(ctx.today)}.</p>')
    body = (
        f'<h1>Security metrics — {C.esc(client)}</h1>'
        f'<p class="sub">Board view · as at {C.esc(as_of)}</p>'
        + drift
        + headline(ctx)
        + '<h2>Where we stand</h2>' + summary_block(ctx)
        + '<h2>The numbers</h2>' + metric_blocks(ctx)
        + decisions_block(ctx)
        + ctx.footer())
    return C.write(ctx, C.page(f"Security metrics — {client}", body, ctx.offline),
                   f'{ctx.counts["metrics"]} metrics, '
                   f'{"narrative supplied" if not ctx.tr.absent else "placeholders"}')


if __name__ == "__main__":
    sys.exit(main())
