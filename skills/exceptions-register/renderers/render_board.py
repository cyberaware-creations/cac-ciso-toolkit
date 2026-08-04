#!/usr/bin/env python3
"""render_board.py — the board view of the acceptances and exceptions section.

Board language is never invented here. Pass --translations with the output of the
ciso-board-translation skill; without it every narrative slot renders a labelled
placeholder and the report says so rather than looking finished.

The sidecar conforms to skills/board-pack/references/section-contract.md: section
`exceptions`, with TWO per-item maps — `acceptances` and `exceptions` — because an accepted
risk and a control exception are different objects sharing one lifecycle.

Usage: python3 render_board.py --in analysis.json [--translations exceptions.board.json]
"""
from __future__ import annotations

import sys

import _common as C


def headline(ctx: C.Context) -> str:
    a = ctx.attention
    cells = [(ctx.counts["acceptances"], "residual risks formally accepted"),
             (ctx.counts["exceptions"], "control exceptions in force"),
             (len(a["overdue"]), "overdue for re-validation"),
             (len(a["expired"]), "past their expiry date")]
    return ('<div class="tiles">' + "".join(
        f'<div class="tile"><span class="n">{n}</span><span class="l">{C.esc(l)}</span></div>'
        for n, l in cells) + "</div>")


def summary(ctx: C.Context) -> str:
    if ctx.tr.executive_summary:
        return f'<div class="card"><p>{C.esc(ctx.tr.executive_summary)}</p></div>'
    return f'<div class="card"><div class="ph">{C.esc(C.PLACEHOLDER)}</div></div>'


def _priority(r: dict) -> tuple:
    """Expired first, then overdue, then due, then the rest — and by id within a rank.

    Deterministic, so the same register always produces the same deck.
    """
    rank = {"expired": 0, "revalidation-overdue": 1, "revalidation-due": 2}.get(r["band"], 3)
    return (rank, r["id"])


def blocks(ctx: C.Context) -> str:
    out = []
    for r in sorted(ctx.active(), key=_priority):
        line = ctx.tr.line(r["id"])
        narrative = (f'<p>{C.esc(line)}</p>' if line else
                     f'<div class="ph">No board sentence supplied for {C.esc(r["id"])}. '
                     f'The facts below are from the register; the language is not '
                     f'invented here.</div>')
        offset = (f' · offset by: {C.esc(r["compensatingControl"])}'
                  if r["compensatingControl"] else "")
        out.append(
            f'<div class="card"><h3>{C.esc(r["title"])}</h3>'
            f'<p class="muted">{C.esc(r["id"])} · '
            f'{C.esc(C.KIND_LABEL.get(r["kind"], r["kind"]))} · '
            f'approved by {C.esc(r["approver"])} · {C.band_chip(r["band"])} · '
            f'{C.esc(C.days_phrase(r["daysToRevalidation"], "re-validation"))}'
            f'{offset}</p>{narrative}</div>')
    return "".join(out) or '<div class="card"><p class="muted">Nothing active.</p></div>'


def _dtext(d): return d.get("text") if isinstance(d, dict) else d


def decisions(ctx: C.Context) -> str:
    board = [d for d in ctx.tr.decisions
             if not (isinstance(d, dict) and d.get("altitude") == "management")]
    mgmt = [d for d in ctx.tr.decisions
            if isinstance(d, dict) and d.get("altitude") == "management"]
    if board:
        items = "".join(f'<li>{C.esc(_dtext(d))}</li>' for d in board)
        out = f'<h2>Decisions</h2><div class="card"><ul class="list">{items}</ul></div>'
    else:
        out = ('<h2>Decisions</h2><div class="card"><div class="ph">'
               'No decisions supplied. Each item should end on something to re-validate, '
               'withdraw, extend, or fund; that language comes from the translation skill.'
               '</div></div>')
    if mgmt:
        mgmt_items = "".join(f'<li>{C.esc(_dtext(d))}</li>' for d in mgmt)
        out += (f'<h2>Management actions — not for board decision</h2>'
                f'<div class="card"><ul class="list">{mgmt_items}</ul></div>')
    return out


def main(argv=None) -> int:
    ctx = C.Context(C.build_parser(__doc__.split("\n")[0], "exceptions-board.html")
                    .parse_args(argv))
    client = ctx.meta.get("clientName") or "Acceptances and exceptions"
    as_of = ctx.tr.as_of or ctx.today
    drift = ""
    if ctx.tr.as_of and ctx.today and ctx.tr.as_of != ctx.today:
        drift = (f'<p class="sub">Note: the board narrative is dated {C.esc(ctx.tr.as_of)} '
                 f'and the register is as at {C.esc(ctx.today)}.</p>')
    body = (f'<h1>Accepted risk and control exceptions — {C.esc(client)}</h1>'
            f'<p class="sub">Board view · as at {C.esc(as_of)}</p>' + drift
            + headline(ctx)
            + '<h2>Where we stand</h2>' + summary(ctx)
            + ctx.caveat_block()
            + '<h2>What we are carrying</h2>' + blocks(ctx)
            + decisions(ctx)
            + ctx.footer())
    return C.write(ctx, C.page(f"Accepted risk and exceptions — {client}", body, ctx.offline),
                   f'{ctx.counts["active"]} active, '
                   f'{"narrative supplied" if not ctx.tr.absent else "placeholders"}')


if __name__ == "__main__":
    sys.exit(main())
