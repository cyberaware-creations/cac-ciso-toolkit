#!/usr/bin/env python3
"""render_inventory.py — the operational acceptance and exception inventory.

The working view: every active record with its approver, its basis, what compensates it
where that applies, and where it sits in the lifecycle. Deviation and compensating control
are deliberately placed on the same line, so the comparison the review has to make is
unavoidable rather than optional.

Usage: python3 render_inventory.py --in analysis.json [--out inventory.html]
"""
from __future__ import annotations

import sys

import _common as C


def tiles(ctx: C.Context) -> str:
    """The same four attention counts the board view leads on, plus the due list.

    Coloured on the same rule and from the same mapping as every other mark on the page:
    only a non-empty count takes a band, and the two population counts never take one.
    """
    a = ctx.attention
    cells = [(ctx.counts["acceptances"], "accepted risks", None),
             (ctx.counts["exceptions"], "control exceptions", None),
             (len(a["overdue"]), "overdue for re-validation", "critical"),
             (len(a["due"]), "due for re-validation", "high"),
             (len(a["expired"]), "past their expiry date", "critical")]
    out = ""
    for n, label, sev in cells:
        colour = C.G._sev_colour(sev, "text") if (sev and n) else C.INK
        out += (f'<div class="tile"><span class="n" style="color:{colour}">{n}</span>'
                f'<span class="l">{C.esc(label)}</span></div>')
    return f'<div class="tiles">{out}</div>'


def table(ctx: C.Context) -> str:
    rows = []
    for r in sorted(ctx.active(), key=lambda x: (x["daysToRevalidation"] is None,
                                                 x["daysToRevalidation"] or 0)):
        offset = (f'<br><span class="muted">offsets: '
                  f'{C.esc(r["compensatingControl"])}</span>'
                  if r["compensatingControl"] else "")
        deviation = (f'<br><span class="muted">deviates from '
                     f'{C.esc(r["deviationFrom"])}</span>' if r["deviationFrom"] else "")
        links = ", ".join(r["riskIds"] + r["csfSubcategoryIds"] + r["incidentIds"]) or "—"
        src = (f'<br><span class="muted">from {C.esc(r["sourceRiskRef"])}</span>'
               if r.get("sourceRiskRef") else "")
        rows.append(
            f'<tr><td><strong>{C.esc(r["id"])}</strong><br>{C.esc(r["title"])}'
            f'{deviation}{offset}{src}</td>'
            f'<td>{C.esc(C.KIND_LABEL.get(r["kind"], r["kind"]))}</td>'
            f'<td>{C.esc(r["approver"])}<br>'
            f'<span class="muted">{C.esc(r["justification"])}</span></td>'
            f'<td>{C.band_chip(r["band"])}<br>'
            f'<span class="muted">{C.esc(C.days_phrase(r["daysToRevalidation"], "re-validation"))}</span></td>'
            f'<td>{C.esc(r["acceptedDate"] or "—")}<br>'
            f'<span class="muted">expires {C.esc(r["expiryDate"] or "no expiry set")}</span></td>'
            f'<td>{C.esc(links)}</td></tr>')
    if not rows:
        return '<div class="card"><p class="muted">No active records.</p></div>'
    return ('<div class="scroll"><table><thead><tr><th>Record</th><th>Type</th>'
            '<th>Approved by / basis</th><th>Lifecycle</th><th>Dates</th><th>Links</th>'
            f'</tr></thead><tbody>{"".join(rows)}</tbody></table></div>')


def attention(ctx: C.Context) -> str:
    spec = [
        ("overdue", "Overdue for re-validation",
         "the re-validation date has passed. The record stays in the inventory — the "
         "organisation is still carrying this — and a lapsed clock surfaces an item, it "
         "never expires the reasoning."),
        ("due", "Due for re-validation",
         f"the re-validation date falls within the next {ctx.window} days."),
        ("expired", "Past the expiry date",
         "the expiry date has passed. Renew deliberately or close."),
        ("noCompensatingControl", "Exception with nothing offsetting it",
         "an exception must name a compensating control; the engine refuses one without, "
         "so anything here predates that rule or arrived from an import."),
        ("unlinked", "Not linked to a risk or a CSF outcome",
         "the record stands alone, so nothing else in the toolkit will surface it."),
    ]
    out = []
    for key, title, rule in spec:
        ids = ctx.attention.get(key) or []
        body = (f'<p class="muted">{C.esc(rule)}</p>' +
                (f'<ul class="list">' + "".join(
                    f'<li>{C.esc(i)} — {C.esc(_title(ctx, i))}</li>' for i in ids) + "</ul>"
                 if ids else '<p class="muted">None.</p>'))
        out.append(f'<div class="card"><h3>{C.esc(title)} ({len(ids)})</h3>{body}</div>')
    return "".join(out)


def _title(ctx: C.Context, rid: str) -> str:
    for r in ctx.records:
        if r["id"] == rid:
            return r["title"]
    return ""


def main(argv=None) -> int:
    ctx = C.Context(C.build_parser(__doc__.split("\n")[0], "exceptions-inventory.html")
                    .parse_args(argv))
    client = ctx.meta.get("clientName") or "Exceptions register"
    body = (C.band("Cyber Aware Creations", "Operational view")
            + f'<h1>Acceptances and exceptions — {C.esc(client)}</h1>'
            f'<p class="sub">{ctx.counts["active"]} active · {ctx.counts["closed"]} closed '
            f'· re-validation shows as due {ctx.window} days ahead · '
            f'as at {C.esc(ctx.today)}</p>'
            + tiles(ctx)
            + ctx.caveat_block()
            + C.section("What we are carrying, and until when", C.lifecycle_block(ctx))
            + '<h2>The inventory</h2>' + table(ctx)
            + '<h2>Attention</h2>' + attention(ctx)
            + ctx.footer())
    return C.write(ctx, C.page(f"Acceptances and exceptions — {client}", body, ctx.offline),
                   f'{ctx.counts["active"]} active, '
                   f'{len(ctx.attention["overdue"])} overdue')


if __name__ == "__main__":
    sys.exit(main())
