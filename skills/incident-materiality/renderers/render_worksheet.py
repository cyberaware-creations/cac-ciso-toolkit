#!/usr/bin/env python3
"""render_worksheet.py — the determination worksheet.

For the CISO, the disclosure committee and counsel. Every incident with its factor
assessments and the reasoning behind each, the full determination trail in the order it was
recorded, the live regulatory windows, and the disclosure decision with its basis.

It shows the *record*, not a conclusion. Every determination on this page was made by a named
person on a stated date and is reproduced as recorded; nothing here is generated, scored or
recommended.

Usage: python3 render_worksheet.py --in analysis.json [--incident I-001] [--out worksheet.html]
"""
from __future__ import annotations

import sys

import _common as C


def tiles(ctx: C.Context) -> str:
    att = ctx.attention
    cells = [
        (ctx.counts["open"], "incidents open"),
        (len(att["awaitingDetermination"]) + len(att["noDetermination"]),
         "awaiting a determination"),
        (len(att["due"]), "reporting windows open"),
        (len(att["overdue"]), "past a reporting deadline"),
    ]
    out = "".join(f'<div class="tile"><span class="n">{n}</span>'
                  f'<span class="l">{C.esc(label)}</span></div>' for n, label in cells)
    return f'<div class="tiles">{out}</div>'


def determination_trail(row: dict) -> str:
    dets = row["determinations"]
    if not dets:
        return ('<p class="muted">No determination recorded. The Item 1.05 window has not '
                f'opened; {row["daysSinceDiscovery"]} days have passed since discovery.</p>')
    items = []
    for d in dets:
        items.append(
            f'<li><p class="rec"><strong>'
            f'{C.esc(C.DET_LABEL.get(d["state"], d["state"]))}</strong> on '
            f'{C.esc(d["determinedAt"])}</p>'
            f'<p class="rec">{C.esc(d["rationale"])}</p>'
            f'<p class="who">recorded by {C.esc(d["decider"])} · logged {C.esc(d["ts"])}</p>'
            f'</li>')
    note = ("" if len(dets) == 1 else
            '<p class="muted">Every determination is kept. A revised call does not replace '
            'the one before it — the sequence is the record of what was known and when.</p>')
    return f'<ul class="trail">{"".join(items)}</ul>{note}'


def factor_table(row: dict) -> str:
    latest = row["factorsLatest"]
    history = row["factorHistory"]
    rows = []
    for key in C.FACTOR_ORDER:
        cur = latest.get(key)
        if cur is None:
            rows.append(
                f'<tr><td><strong>{C.esc(C.FACTOR_LABEL[key])}</strong></td>'
                f'<td class="muted">not assessed</td>'
                f'<td class="muted">Nobody has looked at this factor yet.</td>'
                f'<td class="muted">—</td></tr>')
            continue
        earlier = [f for f in history if f["key"] == key][:-1]
        prior = ""
        if earlier:
            bits = "".join(
                f'<li>{C.esc(e["assessment"])} — {C.esc(e["rationale"])} '
                f'<span class="who">({C.esc(e["actor"] or "unattributed")}, '
                f'{C.esc(e["ts"][:10])})</span></li>' for e in earlier)
            prior = (f'<details><summary class="muted">{len(earlier)} earlier '
                     f'assessment{"s" if len(earlier) != 1 else ""}</summary>'
                     f'<ul class="list">{bits}</ul></details>')
        related = ""
        if cur.get("relatedIncidentIds"):
            related = ('<br><span class="muted">considered together with '
                       + C.esc(", ".join(cur["relatedIncidentIds"])) + "</span>")
        rows.append(
            f'<tr><td><strong>{C.esc(C.FACTOR_LABEL[key])}</strong></td>'
            f'<td>{C.assessment_chip(cur["assessment"])}</td>'
            f'<td>{C.esc(cur["rationale"])}{related}{prior}</td>'
            f'<td class="who">{C.esc(cur["actor"] or "unattributed")}<br>'
            f'{C.esc(cur["ts"][:10])}</td></tr>')
    missing = row["factorsUnassessed"]
    tail = ('<p class="muted">Every factor has been assessed.</p>' if not missing else
            '<p class="muted">Outstanding: ' + C.esc(", ".join(
                C.FACTOR_LABEL[k] for k in missing))
            + '. A factor nobody looked at is the usual way a determination goes wrong.</p>')
    return ('<div class="scroll"><table><thead><tr><th>Factor</th><th>Assessment</th>'
            '<th>Recorded reasoning</th><th>By / on</th></tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></div>{tail}')


def clock_table(row: dict) -> str:
    rows = []
    for c in row["clocks"]:
        if c["state"] == "not-applicable":
            continue
        if "hoursRemaining" in c:
            remaining = C.hours_phrase(c["hoursRemaining"])
        elif "daysRemaining" in c:
            remaining = (f'{C.days_phrase(c["daysRemaining"])} · '
                         f'{c["businessDaysRemaining"]} business days')
        else:
            remaining = "—"
        rows.append(
            f'<tr><td><strong>{C.esc(C.window_name(c))}</strong></td>'
            f'<td>{C.clock_chip(c["state"])}</td>'
            f'<td>{C.esc(c["deadline"] or "—")}<br>'
            f'<span class="muted">{C.esc(remaining if c["deadline"] else "")}</span></td>'
            f'<td>{C.esc(c["anchor"] or "—")}<br>'
            f'<span class="muted">{C.esc(c["anchorKind"] or "")}</span></td>'
            f'<td class="muted">{C.esc(c["note"])}</td></tr>')
    if not rows:
        return ('<p class="muted">This incident is not tracked against SEC Item 1.05 or '
                'DORA. No window is computed — see the regulatory factor for anything else '
                'that may be triggered.</p>')
    return ('<div class="scroll"><table><thead><tr><th>Window</th><th>State</th>'
            '<th>Deadline</th><th>Anchored on</th><th>Rule</th></tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></div>')


def disclosure_block(row: dict) -> str:
    d = row["disclosure"]
    filings = ("<br>".join(f'{C.esc(k)} — {C.esc(v)}' for k, v in sorted(d["filings"].items()))
               or '<span class="muted">nothing recorded as filed</span>')
    basis = C.esc(d["basis"]) if d["basis"] else '<span class="muted">no basis recorded</span>'
    links = []
    if row["linkedRiskIds"]:
        links.append("risks " + C.esc(", ".join(row["linkedRiskIds"])))
    if row["linkedExceptionIds"]:
        links.append("accepted risks / exceptions "
                     + C.esc(", ".join(row["linkedExceptionIds"])))
    link_line = (f'<p class="rec"><strong>Linked:</strong> {" · ".join(links)}</p>'
                 if links else "")
    return (f'<h4>Disclosure decision</h4>'
            f'<p class="rec"><strong>{C.esc(d["decision"])}</strong></p>'
            f'<p class="rec">{basis}</p>'
            f'<h4>Filings recorded</h4><p class="rec">{filings}</p>{link_line}')


def incident_card(row: dict) -> str:
    scope = (f'<p class="rec">{C.esc(row["scopeNote"])}</p>' if row["scopeNote"] else "")
    return (
        f'<div class="card"><h3>{C.esc(row["id"])} — {C.esc(row["title"])} '
        f'{C.band_chip(row["band"])}</h3>'
        f'<p class="who">discovered {C.esc(row["discoveredAt"])} · '
        f'{row["daysSinceDiscovery"]} days ago · '
        f'{C.esc(", ".join(C.REGIME_LABEL.get(r, r) for r in row["regimes"]) or "no regime tracked")}'
        f'</p>{scope}'
        f'<h4>Determination trail</h4>{determination_trail(row)}'
        f'<h4>Factors assessed</h4>{factor_table(row)}'
        f'<h4>Regulatory windows</h4>{clock_table(row)}'
        f'{disclosure_block(row)}</div>')


def attention_lists(ctx: C.Context) -> str:
    spec = [
        ("overdue", "Past a reporting deadline", "a computed deadline has passed with no filing recorded"),
        ("due", "Reporting window open", "a deadline exists, has not passed, and nothing is recorded as filed"),
        ("noDetermination", "No determination recorded",
         "nothing has been determined, not even an 'assessing' entry — the elapsed days since discovery are on the card"),
        ("awaitingDetermination", "Still open on the determination",
         "the current state is 'assessing' or 'not yet determinable'"),
        ("anchorMissing", "DORA anchor not recorded",
         "the regime applies and the event happened, but no awareness or classification timestamp was recorded, so no deadline can be computed"),
        ("incompleteFactors", "Factors outstanding",
         "at least one of the six factors has never been assessed"),
        ("realizedAcceptedRisk", "Linked to an accepted risk or exception",
         "this incident is recorded against a risk the organisation knowingly accepted — read the discoverability note above before writing about it"),
    ]
    by_id = {r["id"]: r["title"] for r in ctx.incidents}
    blocks = []
    for key, title, rule in spec:
        ids = [i for i in (ctx.attention.get(key) or []) if i in by_id]
        body = (f'<p class="muted">{C.esc(rule)}</p>'
                + (f'<ul class="list">'
                   + "".join(f'<li>{C.esc(i)} — {C.esc(by_id[i])}</li>' for i in ids)
                   + "</ul>" if ids else '<p class="muted">None.</p>'))
        blocks.append(f'<div class="card"><h3>{C.esc(title)} ({len(ids)})</h3>{body}</div>')
    return "".join(blocks)


def main(argv=None) -> int:
    p = C.build_parser(__doc__.split("\n")[0], "incident-worksheet.html")
    ctx = C.Context(p.parse_args(argv))
    client = ctx.meta.get("clientName") or "Incident record"
    hol = (f'{len(ctx.holidays)} holidays supplied' if ctx.holidays
           else 'no holiday calendar supplied — a deadline falling on a federal holiday will '
                'be computed one day early')
    body = (
        f'<h1>Materiality determination worksheet — {C.esc(client)}</h1>'
        f'<p class="sub">{len(ctx.incidents)} incident'
        f'{"s" if len(ctx.incidents) != 1 else ""} · as at {C.esc(ctx.today)} · '
        f'{C.esc(hol)}</p>'
        + tiles(ctx)
        + ctx.legal_block()
        + ctx.verdict_block()
        + ctx.clock_rule_block()
        + (ctx.caveat_block() if ctx.any_linked() else "")
        + "<h2>Incidents</h2>"
        + ("".join(incident_card(r) for r in ctx.incidents)
           or '<p class="muted">No incidents in this store.</p>')
        + "<h2>Attention</h2>" + attention_lists(ctx)
        + ctx.footer())
    return C.write(ctx, C.page(f"Determination worksheet — {client}", body, ctx.offline),
                   f'{len(ctx.incidents)} incidents, '
                   f'{len(ctx.attention["due"])} windows open')


if __name__ == "__main__":
    sys.exit(main())
