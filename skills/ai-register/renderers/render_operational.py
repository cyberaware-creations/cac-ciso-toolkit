#!/usr/bin/env python3
"""render_operational.py — the working view of the AI register.

For the person who runs the programme, not the board. Criticality is RAG here, because this is
the surface where it is a genuine triage aid and the reader knows what the scale means: they
are deciding what to look at this week.

Reads an `ai_register.py analyze` JSON and renders it. It derives nothing: every level, class,
control count and escalation on this page was computed by the engine, because a renderer that
decided for itself whether a class was covered could disagree with the register an assessor
was handed.

The one rule this file must not break: **no exposure class renders in a resolved state.**
Controls are shown as a count with the word "recorded" and nothing else — no tick, no green,
no progress bar, no "3 of 5 covered". See `_common.py`.

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


def _model_cell(row) -> str:
    bits = ["%s <span class=\"muted\">%s</span>"
            % (C.esc(row.get("system") or row.get("systemRef") or ""),
               C.esc(row.get("version") or ""))]
    if row.get("provider"):
        bits.append('<div class="sub">%s · %s%s</div>'
                    % (C.esc(row["provider"]), C.esc(row.get("hosting") or ""),
                       (" · built on %s" % C.esc(row["baseModel"]))
                       if row.get("baseModel") else
                       ' · <span class="muted">base model not disclosed</span>'))
    if row.get("sanction") and row["sanction"] != "sanctioned":
        bits.append('<div class="sub">%s</div>' % C.esc(row["sanction"].upper()))
    return "".join(bits)


def _exposure_cell(row) -> str:
    """Every derived class, each with its own state. Never a ratio, never a total.

    "3 of 5 classes covered" is the shape this deliberately does not produce: it implies the
    other two are a shortfall against a target, and there is no target — a class is not
    something you finish.
    """
    classes = row.get("exposure") or []
    if not classes:
        return '<span class="muted">no classes derived</span>'
    out = []
    for entry in classes:
        label = C.esc(entry["class"])
        if entry.get("noLongerDerived"):
            label += ' <span class="muted">(no longer derived; controls kept)</span>'
        out.append("<div>%s %s</div>"
                   % (label, C.exposure_chip(entry["state"], entry.get("controls", 0))))
    return "".join(out)


def _open_cell(row) -> str:
    if row.get("retired"):
        return '<span class="muted">retired</span>'
    bits = ["%d open" % row.get("openQuestions", 0)]
    if row.get("reConfirmQuestions"):
        bits.append("%d to re-confirm" % row["reConfirmQuestions"])
    if row.get("openProposals"):
        bits.append("%d proposal(s) awaiting a person" % row["openProposals"])
    ev = row.get("evidence") or {}
    if ev.get("total"):
        by = ev.get("byStatus") or {}
        # Each state carries its word. `in-grace` and `expired` are different facts: the first
        # is an answer ageing, the second is no answer at all.
        states = ", ".join("%d %s" % (by[s], s) for s in ("current", "in-grace", "expired")
                           if by.get(s))
        bits.append("evidence: %s" % states)
    return C.esc(" · ".join(bits))


def _rows(ctx) -> str:
    out = []
    for row in ctx.rows:
        chips = "".join(C.trigger_chip(e["trigger"]) for e in ctx.esc_for(row["id"]))
        assigned = ("assigned by %s" % C.esc(row["confirmedBy"])) if row.get("confirmedBy") \
            else '<span class="muted">derived only — nobody has assigned it</span>'
        out.append(
            "<tr><td><code>%s</code></td><td>%s</td><td>%s</td><td>%s</td>"
            '<td>%s<div class="sub">%s</div></td><td>%s</td><td>%s</td><td>%s</td>'
            "<td>%s</td></tr>"
            % (C.esc(row["id"]), _model_cell(row), C.esc(row.get("purpose") or ""),
               C.autonomy_chip(row.get("autonomy") or ""),
               C.crit_chip(row["criticality"], ctx.scale, board=False), assigned,
               _trace_cell(row), _exposure_cell(row),
               C.esc(row.get("owner") or ""),
               chips or '<span class="muted">none</span>'))
        if row.get("autonomyWarnings"):
            out.append('<tr><td></td><td colspan="8" class="muted">%s</td></tr>'
                       % " ".join(C.esc(w) for w in row["autonomyWarnings"]))
    return "".join(out)


def _escalations(ctx) -> str:
    if not ctx.escalations:
        return ("<p>Nothing is escalating. Every deployment is classified, owned, within its "
                "cadence, and unchanged since it was last assessed.</p>")
    rows = []
    for e in ctx.escalations:
        rows.append(
            "<tr><td>%s</td><td><code>%s</code></td><td>%s</td><td>%s</td></tr>"
            % (C.trigger_chip(e["trigger"], e["severity"]), C.esc(e["subjectRef"]),
               C.esc(e["trigger"]), C.esc(e["evidence"])))
    return ('<div class="scroll"><table><thead><tr><th>severity</th>'
            "<th>deployment</th><th>trigger</th><th>why</th></tr></thead>"
            "<tbody>%s</tbody></table></div>" % "".join(rows))


def _counts(ctx) -> str:
    by = ctx.counts.get("byCriticality") or {}
    crit = "".join('<div class="stat">%s<span>%s</span></div>'
                   % (C.crit_chip(level, ctx.scale, board=False), n)
                   for level, n in sorted(by.items()))
    auto = "".join('<div class="stat">%s<span>%s</span></div>' % (C.autonomy_chip(level), n)
                   for level, n in (ctx.counts.get("byAutonomy") or {}).items())
    tiles = "".join(
        '<div class="tile"><span class="n">%d</span><span class="l">%s</span></div>' % (n, lbl)
        for n, lbl in (
            (ctx.counts.get("live", 0), "live deployments"),
            (ctx.counts.get("systems", 0), "systems in the inventory"),
            (ctx.counts.get("generative", 0), "generative"),
            (ctx.counts.get("unsanctioned", 0), "on unsanctioned systems"),
            (ctx.counts.get("discovered", 0), "discovered, not declared"),
            (ctx.a.get("uncontrolledClasses", 0), "classes with no control recorded"),
        ))
    return ('<div class="tiles">%s</div><div class="stats">%s</div>'
            '<div class="stats">%s</div>'
            '<p class="muted">Counts, never an aggregate. A register with three '
            "top-criticality deployments has three of them; a single number standing for that "
            "is an opinion this tool is not entitled to.</p>" % (tiles, crit, auto))


def build(ctx) -> str:
    body = [
        C.band("AI deployments",
               "%s · %d live, %d retired · as at %s"
               % (ctx.organisation, ctx.counts.get("live", 0),
                  ctx.counts.get("retired", 0), ctx.today)),
        C.legend(board=False),
    ]
    for note in ctx.notes:
        body.append('<div class="note"><p>%s</p></div>' % C.esc(note))
    body.append(C.section("How the estate sits", _counts(ctx)))
    # `.scroll`: nine columns, one of them a trace rendered as `A -> B -> ...` that refuses to
    # wrap. Wide content scrolls inside its own container so the page body never does — a table
    # that widens the document is unreadable on a phone in a way nobody notices on a desktop.
    body.append(C.section(
        "Every deployment",
        '<div class="scroll"><table><thead><tr><th>id</th><th>model</th><th>purpose</th>'
        "<th>autonomy</th><th>criticality</th><th>traced through</th>"
        "<th>exposed to</th><th>owner</th><th>escalating</th></tr></thead>"
        "<tbody>%s</tbody></table></div>" % _rows(ctx)))
    body.append(C.section("What is escalating", _escalations(ctx)))
    body.append(ctx.caveat_block())
    body.append(ctx.footer())
    return C.page("AI register — operational", "".join(body), ctx.offline)


def main() -> int:
    parser = C.build_parser(__doc__.split("\n")[0], "operational.html")
    ctx = C.Context(parser.parse_args())
    return C.write(ctx, build(ctx), "operational view")


if __name__ == "__main__":
    raise SystemExit(main())
