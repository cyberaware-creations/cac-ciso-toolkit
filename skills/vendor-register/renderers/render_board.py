#!/usr/bin/env python3
"""render_board.py — the third-party section a board actually reads.

The colour split (D-10) is the whole difference between this file and the operational one,
and it is a deliberate design decision rather than a styling preference.

**Criticality is a classification here, not a severity.** It renders in the measure colour
carrying its word. RAG is reserved for what needs a decision — an overdue assessment, an
untested exit, a dependency nobody could trace. The reason is management by exception, which
the executive indicator system already commits to: red marks what needs the board. A
well-managed top-criticality arrangement needs nothing from them, and a board scanning twelve
red rows reads twelve problems and acts on none.

Same data, two audiences, neither view lying.

Every sentence on this page comes from a `ciso-board-translation` sidecar. A slot with no
translation renders a visible placeholder rather than an invented line — a page that fills a
hole with plausible prose is worse than one that shows the hole, because only one of them
gets noticed.

  render_board.py --in analysis.json --out board.html [--translations vendor.board.json]
"""
from __future__ import annotations

import _common as C


def _placeholder() -> str:
    return '<p class="ph">%s</p>' % C.esc(C.PLACEHOLDER)


def _summary(ctx) -> str:
    if ctx.tr.executive_summary:
        return "<p>%s</p>" % C.esc(ctx.tr.executive_summary)
    return _placeholder()


def _cards(ctx) -> str:
    """One card per live arrangement, worst-escalating first.

    Ordered by what is escalating, NOT by criticality — because criticality is not a
    severity here, and sorting on it would put a well-run critical dependency above an
    untraced one nobody can explain. It would also mean ranking `untraced`, which the engine
    refuses outright.
    """
    def rank(row):
        sev = [e["severity"] for e in ctx.esc_for(row["id"])]
        for i, name in enumerate(("critical", "high", "medium")):
            if name in sev:
                return (i, row["id"])
        return (9, row["id"])

    cards = []
    for row in sorted(ctx.live(), key=rank):
        esc_here = ctx.esc_for(row["id"])
        marks = "".join(C.trigger_chip(e["trigger"]) for e in esc_here)
        line = ctx.tr.line(row["id"])
        prose = ("<p>%s</p>" % C.esc(line)) if line else _placeholder()
        cards.append(
            '<div class="card"><div class="card-head"><code>%s</code> %s %s</div>'
            "%s<div class=\"sub\">%s · owner %s</div></div>"
            % (C.esc(row["id"]),
               # board=True: the classification treatment. This is the D-10 split.
               C.crit_chip(row["criticality"], ctx.scale, board=True),
               marks, prose, C.esc(row["vendor"]), C.esc(row["owner"])))
    return "".join(cards) or "<p>No live arrangements are recorded.</p>"


def _text_of(decision):
    """A decision is `{"text": ..., "altitude": ...}`, or a bare string from an older sidecar.

    Both forms are read. The object form is what `ciso-board-translation` emits today, and a
    renderer that stringified it printed a raw Python dict where a board decision should have
    been — a P1 that actually shipped across this suite. Bare strings still work, because every
    sidecar written before the object form existed is still a valid document.
    """
    if isinstance(decision, dict):
        return str(decision.get("text") or "")
    return str(decision or "")


def _decisions(ctx) -> str:
    """Board asks, then management actions — separated, because they are not the same request.

    A board votes on the first list. Mixing the second into it pads the agenda with things
    nobody in the room is being asked to decide.
    """
    if not ctx.tr.decisions:
        return _placeholder()
    board = [d for d in ctx.tr.decisions
             if not (isinstance(d, dict) and d.get("altitude") == "management")]
    mgmt = [d for d in ctx.tr.decisions
            if isinstance(d, dict) and d.get("altitude") == "management"]
    out = ""
    if board:
        out += "<ul>%s</ul>" % "".join(
            "<li>%s</li>" % C.esc(_text_of(d)) for d in board)
    else:
        out += _placeholder()
    if mgmt:
        out += ("<h2>Management actions — not for board decision</h2><ul>%s</ul>"
                % "".join("<li>%s</li>" % C.esc(_text_of(d)) for d in mgmt))
    return out


def build(ctx) -> str:
    body = [
        C.band("Third parties",
               "%s · %d arrangements · as at %s"
               % (ctx.organisation, ctx.counts.get("live", 0), ctx.today)),
        C.legend(board=True),
        C.section("Where we stand", _summary(ctx)),
    ]
    if ctx.consolidation:
        body.append(
            '<div class="note"><p><strong>Consolidated view.</strong> %s</p></div>'
            % C.esc("This covers %s, declared by %s: %s"
                    % (", ".join(ctx.consolidation["entities"]),
                       ctx.consolidation["declaredBy"], ctx.consolidation["basis"])))
    # A COUNT, not a mark. Open questions are work outstanding; rendering them as a severity
    # would put a judgement about the provider on this page by another name, on the one
    # surface that must not carry one. RAG stays reserved for what needs a board decision.
    #
    # The wording below avoids the scoring vocabulary `board-safety.sh` bans — including in
    # the act of DENYING one. The first draft read "that is work in hand, not a rating", and
    # the guard failed it, correctly: a list that has to reason about negation is a list that
    # gets it wrong eventually, and rewording costs nothing.
    outstanding = ctx.a.get("openQuestions", 0)
    reconfirm = ctx.a.get("reConfirmQuestions", 0)
    if outstanding or reconfirm:
        body.append(
            '<div class="note"><p><strong>Assessment outstanding.</strong> %s</p></div>'
            % C.esc("%d question%s across these arrangements have no evidence behind them "
                    "yet%s. That is what is left to check, not a judgement about any provider."
                    % (outstanding, "" if outstanding == 1 else "s",
                       ("; a further %d rest on evidence that is ageing" % reconfirm)
                       if reconfirm else "")))
    body.append(C.section("What we depend on", _cards(ctx)))
    body.append(C.section("Decisions for the board", _decisions(ctx)))
    body.append(ctx.caveat_block())
    body.append(ctx.footer())
    return C.page("Third parties — board section", "".join(body), ctx.offline)


def main() -> int:
    parser = C.build_parser(__doc__.split("\n")[0], "board.html")
    ctx = C.Context(parser.parse_args())
    return C.write(ctx, build(ctx), "board section")


if __name__ == "__main__":
    raise SystemExit(main())
