#!/usr/bin/env python3
"""render_operational.py — the working view of the third-party register.

For the person who runs the programme, not the board. Criticality is RAG here, because that
is the surface where it is a genuine triage aid and the reader knows what the scale means:
they are deciding what to look at this week.

Reads a `vendor_register.py analyze` JSON and renders it. It derives nothing: every level,
trace and escalation on this page was computed by the engine, because a renderer that decided
for itself whether a clock had lapsed could disagree with the register an assessor was handed.

  render_operational.py --in analysis.json --out operational.html [--brand brand.json]
"""
from __future__ import annotations

import _common as C


def _trace_cell(row) -> str:
    trace = row.get("trace") or []
    if not trace:
        return '<span class="muted">nothing declared to trace from</span>'
    arrow = " &rarr; ".join(C.esc(node) for node in trace)
    if row.get("truncated"):
        # A truncated walk is neither a success nor a failure, and the page has to say so.
        # "high, truncated" would be a confident answer from an unfinished walk.
        arrow += ' <span class="muted">&rarr; … (stopped; more chain to follow)</span>'
    return arrow


def _rows(ctx) -> str:
    out = []
    for row in ctx.rows:
        esc_here = ctx.esc_for(row["id"])
        chips = "".join(C.trigger_chip(e["trigger"]) for e in esc_here)
        assigned = ("assigned by %s" % C.esc(row["confirmedBy"])) if row.get("confirmedBy") \
            else '<span class="muted">derived only — nobody has assigned it</span>'
        out.append(
            "<tr%s><td><code>%s</code></td><td>%s</td><td>%s</td>"
            "<td>%s<div class=\"sub\">%s</div></td><td>%s</td><td>%s</td><td>%s</td></tr>"
            % (' class="retired"' if row.get("retired") else "",
               C.esc(row["id"]), C.esc(row["vendor"]), C.esc(row["services"]),
               C.crit_chip(row["criticality"], ctx.scale, board=False), assigned,
               _trace_cell(row), C.esc(row["owner"]),
               chips or '<span class="muted">none</span>'))
    return "".join(out)


def _escalations(ctx) -> str:
    if not ctx.escalations:
        return "<p>Nothing is escalating. Every arrangement is classified, within its "\
               "cadence, and unchanged since it was last assessed.</p>"
    rows = []
    for e in ctx.escalations:
        rows.append(
            "<tr><td>%s</td><td><code>%s</code></td><td>%s</td><td>%s</td></tr>"
            % (C.trigger_chip(e["trigger"], e["severity"]), C.esc(e["subjectRef"]),
               C.esc(e["trigger"]), C.esc(e["evidence"])))
    return ('<table><thead><tr><th>severity</th><th>arrangement</th><th>trigger</th>'
            "<th>why</th></tr></thead><tbody>%s</tbody></table>" % "".join(rows))


def _counts(ctx) -> str:
    by = ctx.counts.get("byCriticality") or {}
    cells = "".join(
        '<div class="stat">%s<span>%s</span></div>'
        % (C.crit_chip(level, ctx.scale, board=False), n)
        for level, n in sorted(by.items()))
    return ('<div class="stats">%s</div>'
            "<p class=\"muted\">Counts, never an aggregate. A register with three "
            "top-criticality arrangements has three of them; a single number standing for "
            "that is an opinion this tool is not entitled to.</p>" % cells)


def build(ctx) -> str:
    body = [
        C.band("Third-party arrangements",
               "%s · %d live, %d retired · as at %s"
               % (ctx.organisation, ctx.counts.get("live", 0),
                  ctx.counts.get("retired", 0), ctx.today)),
        C.legend(board=False),
    ]
    for note in ctx.notes:
        body.append('<div class="note"><p>%s</p></div>' % C.esc(note))
    body.append(C.section("How the estate sits", _counts(ctx)))
    body.append(C.section(
        "Every arrangement",
        '<table><thead><tr><th>id</th><th>vendor</th><th>services</th>'
        "<th>criticality</th><th>traced through</th><th>owner</th><th>escalating</th>"
        "</tr></thead><tbody>%s</tbody></table>" % _rows(ctx)))
    body.append(C.section("What is escalating", _escalations(ctx)))
    body.append(ctx.caveat_block())
    body.append(ctx.footer())
    return C.page("Third-party register — operational", "".join(body), ctx.offline)


def main() -> int:
    parser = C.build_parser(__doc__.split("\n")[0], "operational.html")
    ctx = C.Context(parser.parse_args())
    return C.write(ctx, build(ctx), "operational view")


if __name__ == "__main__":
    raise SystemExit(main())
