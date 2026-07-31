#!/usr/bin/env python3
"""render_board.py — the audit-committee incident narrative.

What happened, what was determined and on what basis, what was disclosed and when, and the
decision the committee is being asked for. The prose comes from `ciso-board-translation`
through a sidecar; the facts beside it come from the record. A slot with no translation
renders as a visible placeholder — this page never writes a sentence about an incident that
somebody has not written.

The board view carries one extra obligation the worksheet does not: **every sentence on it
should be consistent with what the organisation has said publicly.** A granular internal
record that contradicts a public statement is the sword, not the shield. That note is on the
page, not in this docstring.

Usage:
  python3 render_board.py --in analysis.json [--translations incident.board.json] \\
      [--incident I-001] [--out incident-board.html]
"""
from __future__ import annotations

import sys

import _common as C

ALIGNMENT = (
    "Every sentence in this section should say the same thing the organisation says publicly "
    "about the same incident. Where it does not, one of the two needs to change before this "
    "goes to the committee — and finding that here is the point of keeping the record. "
    "Counsel reviews anything touching disclosure.")


def summary_block(ctx: C.Context) -> str:
    text = ctx.tr.executive_summary
    if not text:
        return f'<div class="ph">{C.esc(C.PLACEHOLDER)}</div>'
    return f'<div class="card"><p class="rec">{C.esc(text)}</p></div>'


def facts_line(row: dict) -> str:
    det = row["determination"]
    bits = []
    if det is None:
        bits.append(f'no determination recorded · {row["daysSinceDiscovery"]} days since '
                    f'discovery on {row["discoveredAt"]}')
    else:
        bits.append(C.determination_phrase(det))
    live = [c for c in row["clocks"] if c["state"] in ("due", "overdue")]
    filed = [c for c in row["clocks"] if c["state"] == "filed"]
    if filed:
        bits.append("reported: " + ", ".join(
            f'{C.window_name(c)} on {c["filedAt"]}' for c in filed))
    if live:
        bits.append("open: " + ", ".join(
            f'{C.window_name(c)} by {c["deadline"]}' for c in live))
    if not live and not filed and row["regimes"]:
        bits.append("no reporting window is open")
    return " · ".join(bits)


def incident_block(ctx: C.Context, row: dict) -> str:
    line = ctx.tr.line(row["id"])
    narrative = (f'<p class="rec">{C.esc(line)}</p>' if line
                 else f'<div class="ph">No board sentence supplied for {C.esc(row["id"])}. '
                      f'Compose it with ciso-board-translation rather than writing one '
                      f'here.</div>')
    links = []
    if row["linkedRiskIds"]:
        links.append("tracked risk " + C.esc(", ".join(row["linkedRiskIds"])))
    if row["linkedExceptionIds"]:
        links.append("accepted risk / exception "
                     + C.esc(", ".join(row["linkedExceptionIds"])))
    link_line = (f'<p class="who">Linked to {" and ".join(links)}.</p>' if links else "")
    return (f'<div class="card"><h3>{C.esc(row["id"])} — {C.esc(row["title"])} '
            f'{C.band_chip(row["band"])}</h3>'
            f'{narrative}'
            f'<p class="who">{C.esc(facts_line(row))}</p>{link_line}</div>')


def decisions_block(ctx: C.Context) -> str:
    if not ctx.tr.decisions:
        return ('<div class="ph">No decisions supplied. A board section that asks for nothing '
                'is a status update; compose the asks with ciso-board-translation.</div>')
    items = "".join(f"<li>{C.esc(d)}</li>" for d in ctx.tr.decisions)
    return f'<ul class="list">{items}</ul>'


def main(argv=None) -> int:
    p = C.build_parser(__doc__.split("\n")[0], "incident-board.html")
    ctx = C.Context(p.parse_args(argv))
    client = ctx.meta.get("clientName") or "Incident update"
    shown = [r for r in ctx.incidents if r["band"] != "closed"] or ctx.incidents
    as_of = ctx.tr.as_of or ctx.today
    body = (
        f'<h1>Cybersecurity incident update — {C.esc(client)}</h1>'
        f'<p class="sub">{len(shown)} incident{"s" if len(shown) != 1 else ""} '
        f'in this period · as at {C.esc(as_of)}</p>'
        + summary_block(ctx)
        + ctx.legal_block()
        + f'<div class="note"><strong>Aligned to what is said publicly</strong>'
          f'<p>{C.esc(ALIGNMENT)}</p></div>'
        + ctx.clock_rule_block()
        + (ctx.caveat_block() if ctx.any_linked() else "")
        + "<h2>Incidents</h2>"
        + ("".join(incident_block(ctx, r) for r in shown)
           or '<p class="muted">No incidents in this period.</p>')
        + "<h2>Decisions for the committee</h2>" + decisions_block(ctx)
        + ctx.footer())
    return C.write(ctx, C.page(f"Incident update — {client}", body, ctx.offline),
                   f'{len(shown)} incidents, '
                   f'{"sidecar supplied" if not ctx.tr.absent else "no sidecar — placeholders"}')


if __name__ == "__main__":
    sys.exit(main())
