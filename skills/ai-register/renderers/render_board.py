#!/usr/bin/env python3
"""render_board.py — the AI section a board actually reads.

Two colour rules govern this page, and both are decisions rather than styling preferences.

**Criticality and autonomy are classifications here, not severities.** They render in the
measure colour carrying their word. RAG is reserved for what needs a decision — something
unsanctioned in production, a model swapped since anybody looked at it, a deployment nobody
owns. The reason is management by exception: red marks what needs the board, a well-run
top-criticality deployment needs nothing from them, and a board scanning twelve red rows reads
twelve problems and acts on none.

Autonomy in particular must not be coloured. `acts` is not worse than `informs`; it is a
different thing, and whether it is a problem depends entirely on what the deployment reaches.
A red `acts` chip would turn the ladder into a risk scale on the one surface where that
misreading is hardest to undo.

**An exposure class never renders as resolved.** Not with a tick, not in green, not as "3 of 5
covered". A class with controls recorded is a class with controls recorded. This page says so
in words, and the caveat block says why.

Every sentence of narrative comes from a `ciso-board-translation` sidecar. A slot with no
translation renders a visible placeholder rather than an invented line — a page that fills a
hole with plausible prose is worse than one that shows the hole, because only one of them gets
noticed.

  render_board.py --in analysis.json --out board.html [--translations ai.board.json]
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
    """One card per live deployment, worst-escalating first.

    Ordered by what is ESCALATING, not by criticality — because criticality is not a severity
    here, and sorting on it would put a well-run top-criticality deployment above an untraced
    one nobody can explain. It would also mean ranking `untraced`, which the engine refuses.
    """
    def rank(row):
        sev = [e["severity"] for e in ctx.esc_for(row["id"])]
        for i, name in enumerate(("critical", "high", "medium")):
            if name in sev:
                return (i, row["id"])
        return (9, row["id"])

    cards = []
    for row in sorted(ctx.live(), key=rank):
        marks = "".join(C.trigger_chip(e["trigger"]) for e in ctx.esc_for(row["id"]))
        line = ctx.tr.line(row["id"])
        prose = ("<p>%s</p>" % C.esc(line)) if line else _placeholder()
        # Classes are NAMED, with their state in words, and no completion figure anywhere.
        classes = row.get("exposure") or []
        uncovered = [e["class"] for e in classes
                     if e["state"] == "no-controls-recorded" and not e.get("noLongerDerived")]
        if classes:
            exposure = ("Exposed to %s. %s"
                        % (", ".join(e["class"] for e in classes),
                           ("Nothing is recorded against %s."
                            % ", ".join(uncovered)) if uncovered
                           else "Controls are recorded against each; a class is never closed."))
        else:
            exposure = "No attack classes have been derived for this deployment yet."
        cards.append(
            '<div class="card"><div class="card-head"><code>%s</code> %s %s %s</div>'
            '%s<div class="sub">%s · %s · owner %s</div>'
            '<div class="sub">%s</div></div>'
            % (C.esc(row["id"]),
               # board=True: the classification treatment. This is the D-10 split.
               C.crit_chip(row["criticality"], ctx.scale, board=True),
               C.autonomy_chip(row.get("autonomy") or ""),
               marks, prose,
               C.esc(row.get("system") or row.get("systemRef") or ""),
               C.esc(row.get("purpose") or ""), C.esc(row.get("owner") or ""),
               C.esc(exposure)))
    return "".join(cards) or "<p>No live AI deployments are recorded.</p>"


def _text_of(decision):
    """A decision is `{"text": ..., "altitude": ...}`, or a bare string from an older sidecar.

    Both forms are read. The object form is what `ciso-board-translation` emits today, and a
    renderer that stringified it printed a raw Python dict where a board decision should have
    been — a defect that actually shipped in a sibling skill. Bare strings still work, because
    every sidecar written before the object form existed is still a valid document.
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
        out += "<ul>%s</ul>" % "".join("<li>%s</li>" % C.esc(_text_of(d)) for d in board)
    else:
        out += _placeholder()
    if mgmt:
        out += ("<h2>Management actions — not for board decision</h2><ul>%s</ul>"
                % "".join("<li>%s</li>" % C.esc(_text_of(d)) for d in mgmt))
    return out


def build(ctx) -> str:
    body = [
        C.band("Artificial intelligence",
               "%s · %d deployments · as at %s"
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
    # A COUNT, not a mark. Unsanctioned systems are a fact about what is running; rendering
    # them as a severity would put a judgement about a provider on this page by another name.
    unsanctioned = ctx.counts.get("unsanctioned", 0)
    discovered = ctx.counts.get("discovered", 0)
    if unsanctioned or discovered:
        body.append(
            '<div class="note"><p><strong>Found rather than declared.</strong> %s</p></div>'
            % C.esc("%d deployment%s runs on a system nobody has sanctioned%s. Each is in "
                    "this register the moment it was found, which is the point: the failure "
                    "mode of unsanctioned AI is a sighting that lives somewhere the register "
                    "cannot see."
                    % (unsanctioned, "" if unsanctioned == 1 else "s",
                       ("; %d system%s reached the inventory through discovery rather than a "
                        "request" % (discovered, "" if discovered == 1 else "s"))
                       if discovered else "")))
    outstanding = ctx.a.get("openQuestions", 0)
    reconfirm = ctx.a.get("reConfirmQuestions", 0)
    if outstanding or reconfirm:
        body.append(
            '<div class="note"><p><strong>Assessment outstanding.</strong> %s</p></div>'
            % C.esc("%d question%s across these deployments have no evidence behind them "
                    "yet%s. That is what is left to check, not a judgement about any provider."
                    % (outstanding, "" if outstanding == 1 else "s",
                       ("; a further %d rest on evidence that is ageing" % reconfirm)
                       if reconfirm else "")))
    body.append(C.section("What we run, and what it is exposed to", _cards(ctx)))
    body.append(C.section("Decisions for the board", _decisions(ctx)))
    body.append(ctx.caveat_block())
    body.append(ctx.footer())
    return C.page("Artificial intelligence — board section", "".join(body), ctx.offline)


def main() -> int:
    parser = C.build_parser(__doc__.split("\n")[0], "board.html")
    ctx = C.Context(parser.parse_args())
    return C.write(ctx, build(ctx), "board section")


if __name__ == "__main__":
    raise SystemExit(main())
