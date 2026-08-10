#!/usr/bin/env python3
"""render_context.py — the framing a board pack opens on.

D-1: this is **framing, not another section**. `board-pack`'s section enum belongs to the
producers that own data, and this adds nothing to it. What it supplies is the cover, the
opening context paragraph, and a provenance stamp naming the profile version the pack was
assembled against — so a reader a year later can tell which perimeter the assessment inside
was narrowed by.

The count of sections is deliberately not repeated here. It used to read "five-value enum",
which was true when this was written and had gone stale by two once `vendor` and `ai`
shipped — a number in a docstring is a number nothing checks.

Revenue renders as a **band** by default (D-2). `--render-revenue exact` shows the figure
**and writes that choice into the provenance line**, because the two documents are not
interchangeable and a reader holding one needs to know which they have.

Usage:
  render_context.py --in context.biz --out framing.html [--render-revenue band|exact]
                    [--offline] [--brand FILE]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _common as C  # noqa: E402


def _revenue_line(rev, mode: str) -> str:
    """The revenue sentence, banded or exact.

    The band is computed here from the exact figure every time, never read from the store —
    a stored band could go stale against the number it describes, and it would be the stale
    one a reader saw.
    """
    if not rev:
        return ""
    ladder = ((10e6, "&lt;10m"), (50e6, "10-50m"), (100e6, "50-100m"),
              (250e6, "100-250m"), (500e6, "250-500m"), (1e9, "500m-1bn"),
              (5e9, "1-5bn"), (float("inf"), "&gt;5bn"))
    exact = float(rev.get("exact") or 0)
    band = next(label for ceiling, label in ladder if exact < ceiling)
    cur = C.esc(rev.get("currency", ""))
    fy = C.esc(rev.get("fiscalYear", ""))
    if mode == "exact":
        return "%s %s (%s)" % (cur, format(int(exact), ","), fy)
    return "%s %s (%s)" % (band, cur, fy)


def build(payload: dict, store: dict, mode: str, offline: bool) -> str:
    meta = store.get("meta") or {}
    ctx = store.get("context") or {}
    org = C.esc(meta.get("orgName") or "(organisation not named)")
    version = C.esc(payload.get("profileVersion") or "unreviewed")
    reviewed = C.esc(payload.get("profileReviewedOn") or "")
    rev = ctx.get("revenue")

    # Criticality and sensitivity are shown, and shown as two lines rather than one.
    # Neither appeared on this page at all until v0.68.2, which made `sensitivity`'s required
    # basis a rule enforced on write and invisible on read — a required field nobody can see
    # decays into ceremony. They stay separate because they answer different questions: what
    # stops when this stops, against what it holds.
    #
    # `sensitivity` is a declared() record and `criticality` is still a bare string, so the
    # two are read differently here. That asymmetry is deliberate and temporary — see
    # add_crown_jewel — and reading them the same way would mean guessing at one of them.
    jewels = ""
    for cj in (ctx.get("crownJewels") or []):
        marks = ""
        crit = cj.get("criticality")
        if isinstance(crit, str) and crit.strip():
            marks += '<div class="mark">Criticality: %s</div>' % C.esc(crit.strip())
        sens = cj.get("sensitivity")
        if isinstance(sens, dict) and str(sens.get("value") or "").strip():
            marks += ('<div class="mark">Sensitivity: %s'
                      '<span class="basis"> — %s</span></div>'
                      % (C.esc(sens.get("value")),
                         C.esc(sens.get("basis") or "no basis recorded")))
        jewels += ('<div class="jewel"><span class="sys">%s</span> — %s'
                   '<div class="stake">At stake: %s</div>%s</div>'
                   % (C.esc(cj.get("system")), C.esc(cj.get("enables")),
                      C.esc(cj.get("atStake")), marks))
    if not jewels:
        jewels = ('<p class="stake">No crown jewels recorded. The join between a system and '
                  'the business consequence of losing it is what lets a risk be stated as '
                  'something other than "high".</p>')

    quotes = ""
    for tol in (ctx.get("boardTolerance") or []):
        quotes += ("<blockquote>%s<span class=\"who\">%s, %s</span></blockquote>"
                   % (C.esc(tol.get("quote")), C.esc(tol.get("declaredBy")),
                      C.esc(tol.get("declaredOn"))))

    goals = "".join("<li>%s</li>" % C.esc(g) for g in (ctx.get("strategicGoals") or []))
    goals_block = ("<h2>The year the business is having</h2><ul>%s</ul>" % goals
                   if goals else "")

    revenue_block = ""
    if rev:
        revenue_block = ('<div class="card"><div class="k">Revenue base</div>'
                         '<div>%s</div></div>' % _revenue_line(rev, mode))

    # The provenance stamp. It names the profile version, and — when the exact figure was
    # requested — says so, so the two renders can never be mistaken for one another.
    override = ""
    if mode == "exact" and rev:
        override = (" Revenue is shown as the <strong>exact figure</strong> by "
                    "<code>--render-revenue exact</code>; the default render bands it.")
    # The discoverability caveat, on the page rather than in a footer.
    #
    # This document names the revenue base, what the business cannot lose, and the board's
    # own words about what it will tolerate — in one place, on a page built to circulate.
    # `exceptions-register` carries the same caveat for the same reason and it is more
    # load-bearing here: an inventory of accepted risk is a governance asset or a litigation
    # exhibit depending on whether it agrees with what the organisation says publicly, and
    # this page is where the two would be compared.
    caveat = ('<div class="card"><div class="k">Discoverability</div>'
              '<p>This page records what the organisation itself declared: its revenue base, '
              'the systems it cannot lose, and the board\'s own words on tolerance. A dated, '
              'attributed record of those is a governance asset and a potential litigation '
              'exhibit, and which one it becomes depends on whether it agrees with what the '
              'organisation has said publicly. Everything here is <strong>discoverable</strong>. '
              'Keep entries governance-level and factual, align them with what is disclosed, '
              'and involve counsel on anything touching disclosure.</p>'
              '<p><strong>Not legal advice.</strong> This tool structures and records what a '
              'human declared; it makes no legal determination and derives no threshold from '
              'any figure on this page.</p></div>')

    prov = ('<div class="prov">Framing assembled against applicability profile '
            '<strong>%s</strong>%s. Facts are declared by the organisation and are not '
            'derived by this tool.%s</div>'
            % (version, (" reviewed %s" % reviewed) if reviewed else "", override))

    return (
        "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        "<title>%s — business context</title>%s<style>%s</style></head><body>"
        "<header><div class=\"wrap\"><div class=\"eyebrow\">Business context</div>"
        "<h1>%s</h1><div class=\"sub\">%s</div></div></header><div class=\"wrap\">"
        "<p class=\"lead\">%s</p>%s%s<h2>What the business cannot lose</h2>%s%s%s%s"
        "<footer>%s</footer></div></body></html>"
        % (org, C.fonts(offline), C.base_css(), org,
           C.esc(meta.get("scopeNote") or "Prepared for the security programme."),
           _opening(store, payload), revenue_block, goals_block, jewels,
           ("<h2>What the board has said</h2>%s" % quotes) if quotes else "",
           caveat, prov, C.esc(C.G.footer())))


def _opening(store: dict, payload: dict) -> str:
    """The opening context paragraph — the business's year, not security's.

    Assembled from declared facts only. Where a fact is absent the sentence is left out
    rather than filled with a plausible one: this page is the frame a board reads the rest
    of the pack through, and an invented frame is worse here than anywhere else in the suite.
    """
    ctx = store.get("context") or {}
    bits = []
    segs = ctx.get("segments") or []
    if segs:
        bits.append("Operating across %s." % C.esc(", ".join(segs)))
    n_flags = len(payload.get("profile") or {})
    if n_flags:
        bits.append("%d applicability flag%s declared, which is what lets every other skill "
                    "ask only the questions that apply."
                    % (n_flags, "" if n_flags == 1 else "s"))
    else:
        bits.append("No applicability flags are declared yet — so every skill reading this "
                    "profile asks its full question set, which is the safe default.")
    return " ".join(bits)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--in", dest="infile", required=True, help="a .biz store")
    p.add_argument("--out", default="business-context.html")
    p.add_argument("--render-revenue", choices=("band", "exact"), default="band")
    p.add_argument("--offline", action="store_true")
    p.add_argument("--brand", metavar="FILE",
                   help="client brand JSON; refused rather than approximated if any pairing "
                        "falls below its contrast floor")
    args = p.parse_args(argv)

    C.apply_brand(args.brand or "")

    store = json.loads(Path(args.infile).read_text(encoding="utf-8"))
    # The payload is rebuilt here rather than imported from the engine: no skill imports
    # another, and this renderer is one directory away from the same rule.
    snaps = store.get("snapshots") or []
    snap = snaps[-1] if snaps else None
    payload = {"profileVersion": snap["label"] if snap else "unreviewed",
               "profileReviewedOn": (snap["ts"][:10] if snap else ""),
               "profile": store.get("profile") or {}}

    doc = build(payload, store, args.render_revenue, args.offline)
    Path(args.out).write_text(doc, encoding="utf-8")
    print("wrote %s (%s bytes) — profile version %r, revenue rendered %s"
          % (args.out, format(len(doc), ","), payload["profileVersion"],
             args.render_revenue))
    return 0


if __name__ == "__main__":
    sys.exit(main())
