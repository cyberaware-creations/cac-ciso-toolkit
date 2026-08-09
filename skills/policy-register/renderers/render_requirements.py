#!/usr/bin/env python3
"""render_requirements.py — the page an auditor is shown.

One row per requirement in the NIST policy spine, grouped by control family, each carrying
the documents aimed at it with their version, their state and who approved them on what date.
Then the register itself, every record including the superseded ones, because the question is
always *what was in force on the date of the incident*.

What this page will not do is tell you a requirement is met. See `_common.CAVEAT`, which is
printed on the page rather than filed in a footnote, and the module docstring of
`_common.py` for why two of the four state chips are deliberately neutral.

Usage: python3 render_requirements.py --in analysis.json [--out policy-requirements.html]
"""
from __future__ import annotations

import sys

import _common as C


def tiles(ctx: C.Context) -> str:
    """Counts. Never a proportion — see `no-coverage-percentage.sh` for the argument.

    Only the two states that describe a document problem take a colour. `approved-policy`
    and `not-declared` are neutral because neither is a verdict about the requirement.
    """
    counts = ctx.counts
    cells = [
        (len(ctx.policies), "policy records", None),
        (counts.get("approved-policy", 0), "with an approved policy recorded", None),
        (counts.get("draft-only", 0), "draft only", "high"),
        (counts.get("superseded-only", 0), "superseded, not replaced", "critical"),
        (counts.get("not-declared", 0), "not declared", None),
    ]
    out = ""
    for n, label, sev in cells:
        colour = C.G._sev_colour(sev, "text") if (sev and n) else C.INK
        out += ('<div class="tile"><span class="n" style="color:%s">%d</span>'
                '<span class="l">%s</span></div>' % (colour, n, C.esc(label)))
    return '<div class="tiles">%s</div>' % out


def _documents(row: dict) -> str:
    if not row["policies"]:
        return '<span class="muted">—</span>'
    bits = []
    for p in row["policies"]:
        who = ""
        if p.get("approvedBy") and p.get("approvedOn"):
            who = ('<br><span class="muted">approved by %s on %s</span>'
                   % (C.esc(p["approvedBy"]), C.esc(p["approvedOn"])))
        review = ""
        if p.get("reviewState") and p["reviewState"] != "review-current":
            review = " " + C.review_chip(p["reviewState"])
        bits.append('%s v%s %s%s%s' % (C.esc(p["id"]), C.esc(p.get("version")),
                                       C.policy_chip(p.get("state")), review, who))
    return "<br>".join(bits)


def requirement_table(ctx: C.Context) -> str:
    """Grouped by family, in catalogue order, with nothing collapsed away.

    Every requirement gets a row whatever its state. A view that showed only the rows with
    something in them would be a list of what the organisation has done, which is the
    opposite of the question being asked.
    """
    rows = []
    family = None
    for row in ctx.in_catalogue():
        if row.get("familyLabel") != family:
            family = row.get("familyLabel")
            rows.append('<tr class="famrow"><td colspan="4">%s</td></tr>' % C.esc(family))
        label = C.esc(row.get("label") or "")
        rows.append(
            '<tr><td class="id">%s</td><td>%s<br><span class="muted">%s</span></td>'
            '<td>%s</td><td>%s</td></tr>'
            % (C.esc(row["id"]), C.state_chip(row["state"]), label,
               _documents(row),
               '<span class="muted">%s</span>' % C.esc(row["means"])))
    return ('<div class="scroll"><table><thead><tr><th>Requirement</th>'
            '<th>What this register can say</th><th>Documents aimed at it</th>'
            '<th>Read this as</th></tr></thead><tbody>%s</tbody></table></div>'
            % "".join(rows))


def outside_block(ctx: C.Context) -> str:
    """Mapped ids this register's catalogue does not hold.

    Shown rather than dropped. An organisation that maps a policy to a PCI DSS or a
    contractual requirement has said something true, and silently discarding it because the
    spine is NIST-shaped would be an absence that looks exactly like a clean result.
    """
    rows = ctx.outside_catalogue()
    if not rows:
        return ""
    items = "".join(
        '<tr><td class="id">%s</td><td>%s</td></tr>'
        % (C.esc(r["id"]), _documents(r)) for r in rows)
    return ('<p class="muted">%s</p><div class="scroll"><table><thead><tr>'
            '<th>Requirement</th><th>Documents aimed at it</th></tr></thead>'
            '<tbody>%s</tbody></table></div>'
            % (C.esc("These ids are mapped in this register but are not part of the NIST "
                     "policy spine it ships. They are listed so nothing recorded is lost, "
                     "not because this register can say anything about them."), items))


def register_table(ctx: C.Context) -> str:
    """Every record, superseded ones included. That is the point of the register."""
    rows = []
    for p in sorted(ctx.policies, key=lambda x: x.get("id") or ""):
        approval = p.get("approval") or {}
        review = p.get("review") or {}
        appr = ('%s<br><span class="muted">%s</span>'
                % (C.esc(approval.get("by")), C.esc(approval.get("on")))
                if approval.get("by") else '<span class="muted">not approved</span>')
        nxt = review.get("nextOn")
        review_cell = (C.review_chip(p.get("reviewState")) +
                       ('<br><span class="muted">%s%s</span>'
                        % (C.esc(nxt), (" · " + C.days_phrase(p.get("daysUntilReview"),
                                                              "day"))
                           if p.get("daysUntilReview") is not None else "")
                        if nxt else "")) if p.get("reviewState") else \
            '<span class="muted">—</span>'
        sup = ""
        if p.get("supersededOn"):
            sup = ('<br><span class="muted">superseded %s%s</span>'
                   % (C.esc(p["supersededOn"]),
                      (" by " + C.esc(p["supersededBy"])) if p.get("supersededBy")
                      else ", no replacement recorded"))
        aimed = ", ".join(C.esc(m) for m in (p.get("mappedTo") or [])) or "—"
        rows.append(
            '<tr><td class="id">%s</td><td>%s<br><span class="muted">v%s · %s</span>%s</td>'
            '<td>%s</td><td>%s</td><td>%s</td><td class="muted">%s</td></tr>'
            % (C.esc(p.get("id")), C.esc(p.get("title")), C.esc(p.get("version")),
               C.esc(p.get("owner")), sup, C.policy_chip(p.get("state")), appr,
               review_cell, aimed))
    if not rows:
        return ('<p class="muted">%s</p>'
                % C.esc("No policy records yet. That is a normal starting state, not a "
                        "fault — record the documents that already exist, in any order, "
                        "and map them as you go."))
    return ('<div class="scroll"><table><thead><tr><th>Id</th><th>Document</th>'
            '<th>State</th><th>Approved</th><th>Review</th><th>Aimed at</th></tr></thead>'
            '<tbody>%s</tbody></table></div>' % "".join(rows))


def attention(ctx: C.Context) -> str:
    """Derived every time, stored nowhere, and never a reason to withhold a row above."""
    if not ctx.escalations:
        return ('<p class="muted">%s</p>'
                % C.esc("Nothing is flagged. That means no review is overdue and no "
                        "requirement is left with only a draft or only a superseded "
                        "document — not that the policy programme is complete."))
    out = []
    for e in ctx.escalations:
        out.append('<div class="esc"><div class="what">%s %s</div>'
                   '<p class="muted">%s</p></div>'
                   % (C.severity_chip(e["severity"], e["kind"]),
                      C.esc(e["what"]), C.esc(e["soWhat"])))
    return "".join(out)


def main(argv=None) -> int:
    ctx = C.Context(C.build_parser(__doc__.split("\n")[0], "policy-requirements.html")
                    .parse_args(argv))
    org = ctx.meta.get("orgName") or "Policy register"
    body = (C.band("Cyber Aware Creations", "Policy register")
            + '<h1>Policies and what each one is aimed at — %s</h1>' % C.esc(org)
            + '<p class="sub">%d policy record(s) · %d requirement(s) in this register\'s '
              'catalogue · as at %s</p>'
              % (len(ctx.policies), len(ctx.in_catalogue()), C.esc(ctx.today))
            + ctx.caveat_block()
            + tiles(ctx)
            + C.legend()
            + C.section("The requirement view", requirement_table(ctx))
            + '<p class="muted">%s</p>' % C.esc(C.SPINE_NOTE)
            + C.section("Mapped outside the catalogue", outside_block(ctx))
            + C.section("The register", register_table(ctx))
            + C.section("Attention", attention(ctx))
            + ctx.footer())
    return C.write(ctx, C.page("Policy register — %s" % org, body, ctx.offline),
                   "%d record(s), %d flagged" % (len(ctx.policies), len(ctx.escalations)))


if __name__ == "__main__":
    sys.exit(main())
