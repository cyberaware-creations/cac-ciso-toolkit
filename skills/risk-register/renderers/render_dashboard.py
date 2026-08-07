#!/usr/bin/env python3
"""
render_dashboard.py — the operational working view (dashboards.md § Operational).

Headline tiles, an inherent/residual heat matrix, a sortable/filterable register
table, attention lists, owner load, and a per-risk drawer showing structured
acceptance and real change history. Everything is derived from the register file
passed in; nothing about a specific client is hardcoded.

Usage:
  python3 render_dashboard.py <register.rr> [out.html] [--today YYYY-MM-DD]
                              [--translations translations.json]
"""

import json
import sys

import _common as C

# Kept out of the f-string that uses it. An escaped quote inside an f-string expression
# only became legal in Python 3.12 (PEP 701); on the supported floor it is a SyntaxError
# that stops this module importing at all, so the whole working view disappears.
PROVTAG = ' <span class="provtag">unreworded</span>'


def build_data(ctx: C.Context) -> str:
    fields = ["id", "title", "description", "category", "owner", "status", "response",
              "inherent", "residual", "inherentExposure", "inherentBand", "residualExposure",
              "residualBand", "overAppetite", "outOfRange", "themeId", "themeName", "velocity",
              "priorExposure", "delta", "reviewDate", "reviewOverdue", "unowned", "acceptance",
              "acceptanceDue", "acceptanceExpired", "acceptanceIncomplete", "history",
              "translation",
              # Carried so the interactive table can mark what still needs review. The
              # working view shows provisional titles on purpose; it must not imply they
              # are board-ready.
              "provisionalTitle", "provisionalScore"]
    risks = [{**{k: r.get(k) for k in fields},
              "csfSubcategoryId": r.get("csfSubcategoryId", ""),
              "notes": r.get("notes", "")} for r in ctx.risks]
    blob = json.dumps({"meta": ctx.meta, "settings": ctx.settings, "risks": risks,
                       "today": ctx.today,
                       "baseline": ctx.baseline.get("label") if ctx.baseline else None})
    # Register text is user-authored: keep a stray "</script>" from ending the block early.
    return blob.replace("</", "<\\/")


def tiles(ctx: C.Context) -> str:
    s = ctx.live
    prior = ctx.trend[-2]["overAppetite"] if len(ctx.trend) > 1 else None
    if prior is None:
        arrow, col, sub = "", C.SLATE, "no snapshot to compare against"
    else:
        d = s["overAppetite"] - prior
        arrow = C.VELOCITY_MARK["improving" if d < 0 else "worsening" if d > 0 else "steady"]
        col = C.VELOCITY_COLOR["improving" if d < 0 else "worsening" if d > 0 else "steady"]
        sub = f'was {prior} at {ctx.trend[-2]["label"]}'
    att = ctx.attention
    flagged = len({r["id"] for k in ("reviewOverdue", "acceptanceDue", "acceptanceExpired",
                                     "acceptanceIncomplete", "unowned", "escalated")
                   for r in att[k]})
    live = s["total"]
    cards = [
        (s["registerTotal"], "Risks tracked", f'{live} live · {s["closed"]} closed', "", C.INK),
        (f'{s["overAppetite"]} <span style="color:{col}">{arrow}</span>',
         "Over appetite", sub, "warn" if s["overAppetite"] else "", C.INK),
        (len(att["acceptanceDue"]), "Acceptances due for re-validation",
         f'{len(att["acceptanceExpired"])} past expiry', "", C.INK),
        (flagged, "Risks needing attention",
         f'{len(att["reviewOverdue"])} review overdue · {len(att["unowned"])} unowned', "", C.INK),
    ]
    out = "".join(f'<div class="tile {cls}"><div class="n">{n}</div><div class="l">{lab}</div>'
                  f'<div class="s">{sub2}</div></div>' for n, lab, sub2, cls, _ in cards)
    pills = "".join(
        f'<div class="bandpill" style="background:{C.BAND[b]};color:{C.BAND_ON[b]}">'
        f'<span class="bn">{s["byBand"][b]}</span>{C.BAND_LABEL[b]}</div>'
        for b in ["low", "medium", "high", "critical"])
    return f'<div class="tiles">{out}</div><div class="bandrow">{pills}</div>'


def _confirmed_note(r: dict) -> str:
    """`· confirmed 42d ago · R. Calder`, or an honest statement of what is missing.

    Sits beside the review date rather than replacing it: the review date is a deadline
    somebody committed to, and the confirmation age is how long since anyone acted on it.
    Two different facts, and collapsing them was the asymmetry this work exists to fix.

    Three outcomes, because `_common._confirmation()` produces three and conflating any
    two of them makes this line assert something false. `lastConfirmedAt` is the branch,
    NOT the day count: a risk whose affirming event has an unreadable `ts` has a
    confirmation and a named confirmer on record and only the distance is unknown, so
    "never confirmed" would be a lie about it. The bad date is printed rather than
    swallowed, because the reader of this screen is the person who can go and fix it.

    A fourth arm for the same reason, and it is not defensive padding — a negative age is
    routine, and THREE separate routes reach it (see _confirmation_rollup in _common.py):

      1. An explicit `--today` behind the register's newest confirmation. references/
         dashboards.md tells the reader to pass --today for a reproducible "as of" view, so
         `--today 2026-06-30` over a register confirmed in July puts every sound record
         here. This is the common route, and the record is not defective.
      2. A hand-edited or imported register carrying a genuinely wrong ts.
      3. Clock skew between whatever wrote the register and whoever renders it.

    This skill's own CLI was a fourth route until _today_utc() closed it: score_register
    writes every `ts` in UTC while `--today` defaulted to the LOCAL date, so an event
    written after 17:00 in California came back as -1 days. That route is gone; the other
    three are not, and the premise of an earlier version of this paragraph — that the
    branch exists to catch a local/UTC skew — is now false.

    age_band() deliberately reports a negative age as `within` — it is a pure distance and
    an `impossible` band would smuggle a validation verdict into the distribution — but
    "confirmed -1d ago" is not a sentence, and rounding it to "confirmed today" would hide
    from this reader the one fact that matters: no age can be measured from that record
    against the date this page was rendered for. So it is named, with its date, and which
    of the three routes produced it is left to the reader, who can go and look.
    """
    when = r.get("lastConfirmedAt")
    if not when:
        return " · never confirmed"
    who = r.get("lastConfirmedBy")
    tail = f" · {C.esc(who)}" if who else ""
    days = r.get("confirmationAgeDays")
    if days is None:
        return f" · confirmed, but the date cannot be read: {C.esc(when)}{tail}"
    if days < 0:
        return f" · confirmed {C.esc(when)}, dated in the future{tail}"
    return f" · confirmed {days}d ago{tail}"


# The four graded age bands, ascending by age. The engine owns the KEY SET and emits the
# counts — see AGE_BANDS and age_band() in ../scripts/score_register.py; this module only
# names and draws them, in the engine's own order rather than a second copy of it.
#
# The LABELS are this view's own and must NOT be merged with the near-identical
# AGE_BAND_LABEL in skills/nist-csf/renderers/_common.py, which carries the matching note
# back to here. What must match across the two skills is the SEMANTICS — the four
# boundaries and the four band names. What must NOT converge is the wording, because the
# two sit in different sentence shapes: over there a label is a trailing clause after a
# date ("confirmed 2026-01-10, beyond cadence"); here it is the predicate of a counted row
# ("1 past the cadence"). So "keep the two in step" applies to the keys and the boundaries
# and to nothing else. Do not unify these values.
#
# Each label carries the same valence as its band name, which is not free: an earlier
# board renderer labelled `beyond` — determinations PAST the chosen cadence — as "within
# 360 days", and three of its four labels were arithmetically wrong in the flattering
# direction. `beyond` reads "past the cadence" here for that reason.
#
# What holds this honest is the rendered-HTML block in evals/confirmation-age.sh: it pins
# this key set against sr.AGE_BANDS, and it pins the rendered ranges at TWO thresholds. A
# missing key here only raises KeyError at render time and an extra one is silent, and the
# ranges read at 180 alone cannot tell "derived from t" from "the argparse default" — so
# that block is the only thing standing between a relabelling and a quietly flattering
# working view. It is not optional.
#
# These are distances from a cadence the reader chose, never confidence words. Nothing in
# this panel suppresses, expires or rescores anything, and no label may imply otherwise.
AGE_BAND_LABEL = {"within": "inside the cadence", "approaching": "nearing the cadence",
                  "beyond": "past the cadence", "wellBeyond": "far past the cadence"}


def confirmation_panel(ctx: C.Context) -> str:
    """How old the determinations on this register are, as a distribution.

    This is the working view, so it gets the shape rather than a sentence — the reader is
    deciding what to look at next, and "three risks have not been re-affirmed in over a
    year" is a work queue. The board page gets one sentence instead; operational views get
    the distribution.

    Its own section, NOT one of the attention lists. Filed inside `attgrid` under "Needs
    attention" it said that three risks inside the cadence are three things needing
    attention — the exact judgement the rest of this docstring refuses to make — and it
    gave `.cnt` two meanings on one screen, "flagged risks" on every sibling card and "live
    population" on this one. references/dashboards.md also enumerates the attention lists,
    and this is not one of them.

    The `wellBeyond` row names the risks it counts. The rollup builds that list oldest-first
    for exactly this, and without it the row is a number the reader cannot act on: a risk
    that is stale but not over appetite, overdue, unowned or accepted appears on no
    attention card, carries no confirmation column in the register table, and is therefore
    unfindable from a screen that just told you it exists.

    Six rows, always drawn, even at zero. They partition the live population exactly
    (`_confirmation_rollup` asserts that), so a reader can add them up against the
    denominator in the heading — which is the whole reason the denominator is there. A row
    suppressed at zero would also make every check over this panel vacuous on a fixture
    that happens not to reach that state, and would leave "0 undated" indistinguishable
    from "this panel does not report undated at all".

    `undated` and `unreadableDate` are NOT bands and are never folded together or into
    one. A band is a distance from a cadence; those two are the absence of a distance for
    two different reasons, and a panel captioned "never confirmed" must never name a risk
    that has a confirmation and a named confirmer on record.

    Deliberately NOT coloured with the band ramp. `C.BAND`/`C.BAND_TEXT` is the RAG
    severity ramp this register spends on residual bands and on ⚠ marks, so painting
    `wellBeyond` red would tell the reader that an old determination is a critical one —
    a verdict the data explicitly refuses to make, and the same conclusion nist-csf's
    age_band_bar() reached when it chose a non-RAG lightness ramp over red. A proportional
    strip like that one was considered and rejected here: this card is half a column wide
    and one column on a phone, the counts are small enough that four segments would be
    slivers, and the two non-band rows have no honest place inside a bar whose width means
    "distance". Row order plus an explicit exclusive range carries the ordering instead,
    in the same markup shape as every sibling card in this grid.

    Nothing here suppresses, expires or rescores anything. The bands report distance from
    a cadence the reader chose; whether that distance matters for a given risk is the
    reader's judgement, because a supplier concentration and a patching backlog go stale
    at completely different rates.
    """
    c = ctx.confirmation
    if not c["live"]:
        return ""
    t = c["thresholdDays"]
    # EXCLUSIVE ranges, and no boundary arithmetic here at all. C.age_bounds() owns the
    # `t // 2` derivation for this skill; this dict is only the WORDING, which is this view's
    # own and must not converge with the board sentence's ("0–90d" on a counted row against
    # "within the last 90 days" in prose). Cumulative ranges over mutually-exclusive counts
    # are both false and flattering: "0–360d" against the count of determinations that are
    # PAST the cadence reads as reassurance, and that shipped on the board renderer.
    #
    # The open-ended band takes `beyond`'s upper bound rather than recomputing `t * 2`, so
    # the two adjacent rows cannot disagree about where one ends and the next begins — the
    # same expression the board sentence uses for its own last clause.
    bounds = C.age_bounds(t)
    edges = {b: (f'over {bounds["beyond"][1]}d' if hi is None else f"{lo}–{hi}d")
             for b, (lo, hi) in bounds.items()}
    notes = dict(edges)

    # A future-dated confirmation is a negative age, which age_band() reports as `within` on
    # purpose — it is a pure distance, and an `impossible` band would smuggle a validation
    # verdict into the distribution. But then the `within` row silently captions those
    # records with the freshest range, which is false in the flattering direction while every
    # attention card on the same page names them. Disclosed here rather than rebanded.
    #
    # Routine rather than exotic, and the common route is an explicitly-passed `--today`:
    # references/dashboards.md documents doing that for a reproducible "as of" view, which
    # makes every confirmation later than the chosen date land here. The other two routes are
    # a genuinely wrong ts in a hand-edited or imported register, and clock skew. So the note
    # states the FACT — dated after the reference date, so no age can be measured — and never
    # the cause. An earlier version of it called a negative age "a file defect", which is a
    # diagnosis this code cannot make and is simply wrong on the documented route; the board
    # sentence had the same overclaim removed. The bar is lower here than on a board page
    # because this reader is the one who can go and look, but a false diagnosis is still
    # false, and the IDs are what make looking possible.
    #
    # The list comes from the rollup, which derives it once and sorts it most-impossible
    # first. It was re-derived inline here with a second comprehension over C.live_risks(),
    # so one rule lived in two places and the count could disagree with the list.
    future = c["futureDatedRisks"]
    if future:
        notes["within"] = (f'{edges["within"]} · includes {c["futureDated"]} dated after the '
                           f'{C.esc(ctx.today)} reference date ({C.id_list(future, cap=6)}), '
                           f'so no age can be measured for them')
    # Named, oldest first, from the list the rollup built for this. Capped: the row is a
    # pointer into the register, not a second register.
    if c["wellBeyond"]:
        notes["wellBeyond"] = (f'{edges["wellBeyond"]} · '
                               f'{C.id_list(c["wellBeyond"], cap=6)}')

    def row(n, label: str, note: str) -> str:
        return f'<li><b>{n}</b> {label}<span class="d">{note}</span></li>'

    rows = "".join(row(c["bands"][b], AGE_BAND_LABEL[b], notes[b]) for b in C.sr.AGE_BANDS)
    rows += row(c["undated"], "with no confirmation on record",
                "no affirming event exists at all — not an age of zero")
    # The one coloured word in the panel, and it is not an age verdict: an affirming event
    # whose ts will not parse is a broken record, and `.warnmark` is already this page's ink
    # for a broken record — an overdue review, a missing owner. Taking the CLASS rather than
    # re-inlining its colour: BAND is a fill ramp and reads 1.68:1 (medium) to 5.44:1
    # (critical) as text, with `high` at 2.61:1, and a hand-copied colour judgement is the
    # thing text_on() and this file's four-copies note exist to stop.
    #
    # The note claims only what the count can support. "The confirmer is on record" was an
    # inference: an affirming event with a blank actor AND an unreadable ts lands in this row
    # with lastConfirmedBy None, so the panel would have asserted a confirmer while the card
    # correctly showed none.
    rows += row(c["unreadableDate"],
                '<span class="warnmark">confirmed, but the date will not parse</span>',
                "an affirming event exists — only the distance is unknown")
    return (f'<div class="att">'
            f'<h3>Confirmation age <span class="cnt">{c["live"]}</span></h3>'
            f'<div class="d" style="margin-bottom:8px">How long since anyone affirmed each '
            f'live risk’s score or treatment decision, against the {t}-day cadence this '
            f'register was rendered with. These six rows account for all {c["live"]} live '
            f'risks. Scores do not expire — the age is reported and you judge.</div>'
            f'<ul class="plain">{rows}</ul></div>')


def shape_block(ctx: C.Context) -> str:
    """Two shared marks the working view had no equivalent of.

    The heat matrix is deliberately NOT repeated here. This page already draws one
    — the interactive grid above, which toggles inherent/residual and drills into a
    cell — and a second, static copy of the same matrix on the same page is not a
    second fact, it is a thing that can disagree with the first one.

    Band mix over review points, because the band pills at the top of this page say
    where the register is and nothing on it said where it came from. Top residual
    exposures as bars, because the register table ranks by whatever column was last
    clicked and a triage reader wants the magnitudes side by side. Both carry the
    engine's own band per segment and per bar.
    """
    return (f'<div class="card"><div class="gfxrow">'
            f'<div class="gfxcol">{C.gfx(C.band_mix_mark(ctx))}'
            f'<div class="hint">Residual band mix by review point. Every band '
            f'states its count — in the segment where it fits, in the key below '
            f'where it does not — because colour alone does not separate medium '
            f'from high.</div></div>'
            f'<div class="gfxcol">{C.gfx(C.top_risks_mark(ctx))}'
            f'<div class="hint">The five worst live risks by residual exposure, '
            f'coloured by the band the engine scored each one.</div></div>'
            f'</div>{C.gfx_legend(ctx.live["byBand"])}</div>')


def attention_lists(ctx: C.Context) -> str:
    a = ctx.attention
    # The engine sorts severity-first, so element 0 is the worst thing on the register and
    # its band colours the card. No new colour is introduced: escalation severity uses the
    # same critical/high/medium vocabulary as everything else on this page, which keeps the
    # CVD-safe palette in assets/brand.md the only palette here.
    esc_worst = ctx.escalations[0]["severity"] if ctx.escalations else "high"
    groups = [
        # First, deliberately. This is the list that answers "what changed for the worse
        # without anyone touching it", which is the question the rest of the page cannot.
        # Each line names its trigger and the comparison behind it — a count alone would be
        # the muted-by-Q2 failure the contract is written against.
        ("Escalating", a["escalated"], C.BAND.get(esc_worst, C.BAND["high"]),
         lambda r: " · ".join(f'{e["trigger"]}: {e["evidence"]["detail"]}'
                              for e in ctx.escalations_by_risk.get(r["id"], []))),
        ("Over appetite", a["overAppetite"], C.BAND["critical"],
         lambda r: f'residual {r["residualExposure"]} {C.BAND_LABEL[r["residualBand"]]}'),
        ("Review overdue", a["reviewOverdue"], C.BAND["high"],
         lambda r: f'review due {r["reviewDate"]}'),
        ("Acceptances due for re-validation", a["acceptanceDue"], C.BAND["high"],
         lambda r: f're-validate by {r["acceptance"].get("revalidationDate")} '
                   f'· {C.esc(r["acceptance"].get("approver") or "no approver")}'),
        ("Acceptance past expiry", a["acceptanceExpired"], C.BAND["critical"],
         lambda r: f'expired {r["acceptance"].get("expiryDate")}'),
        ("Acceptance incomplete", a["acceptanceIncomplete"], C.BAND["critical"],
         lambda r: "missing approver or justification"),
        ("Unowned", a["unowned"], C.SLATE, lambda r: "no owner assigned"),
        ("Scored above the matrix", a["outOfRange"], C.SLATE,
         lambda r: "excluded from the heat matrix"),
    ]
    cards = ""
    for title, rs, colour, detail in groups:
        if not rs:
            continue
        # Working view: show the real title even when provisional. This is the screen the
        # CISO rewords *from* — withholding it here would hide the very text that needs
        # fixing. The tag says it is not board-eligible yet; the board renderers withhold.
        #
        # The tag is a module constant rather than an inline literal on purpose: a
        # backslash-escaped quote inside an f-string expression is a hard SyntaxError
        # before Python 3.12, and this file would not import at all on the floor we
        # support. See PROVTAG.
        items = "".join(f'<li><b>{r["id"]}</b> {C.esc(r["title"])}'
                        f'{PROVTAG if r.get("provisionalTitle") else ""}'
                        f'<span class="d">{detail(r)}{_confirmed_note(r)}</span></li>'
                        for r in rs)
        cards += (f'<div class="att" style="border-left-color:{colour}">'
                  f'<h3>{title} <span class="cnt">{len(rs)}</span></h3>'
                  f'<ul class="plain">{items}</ul></div>')
    if not cards:
        cards = ('<div class="att" style="border-left-color:' + C.BAND["low"] + '">'
                 '<h3>Nothing flagged</h3><p class="d">No risk is escalating, over appetite, '
                 'past review, unowned, or carrying a stale acceptance.</p></div>')
    return cards


def owner_table(ctx: C.Context) -> str:
    rows = "".join(
        f'<tr><td>{C.esc(o["owner"])}</td><td>{o["count"]}</td>'
        f'<td>{C.chip(o["worst"])}</td>'
        f'<td>{o["over"] or ""}{" ⚠" if o["over"] else ""}</td>'
        f'<td>{o["exposure"]}</td></tr>' for o in ctx.owner_load)
    return (f'<table class="reg"><thead><tr><th>Owner</th><th>Open risks</th><th>Worst residual</th>'
            f'<th>Over appetite</th><th>Total residual exposure</th></tr></thead>'
            f'<tbody>{rows}</tbody></table>')


def css() -> str:
    """The page stylesheet, built when it is asked for.

    This was a module-level constant, an f-string evaluated at import — which is before
    `_common.apply_brand()` has run, so every colour in it was frozen at the CAC palette and
    a `--brand` override reached the charts while leaving the page around them unbranded.
    Half a client's palette looks like a mistake in a way that none of it does not.
    """
    return f"""
*{{box-sizing:border-box}}body{{margin:0;font-family:'Manrope',system-ui,sans-serif;
  background:{C.WB};color:{C.INK}}}
h1,h2,h3{{font-family:'Space Grotesk','Manrope',sans-serif;margin:0}}
.wrap{{max-width:1180px;margin:0 auto;padding:0 24px 48px}}
header{{background:{C.INK};color:{C.LIME};padding:18px 0}}
header .wrap{{display:flex;align-items:center;justify-content:space-between;gap:16px;
  flex-wrap:wrap;padding-bottom:0}}
.brand{{display:flex;align-items:center;gap:12px}}
.mark{{width:30px;height:30px;border-radius:7px;
  background:linear-gradient(135deg,{C.PATINA},{C.PATINA_H});position:relative;flex:0 0 auto}}
.mark::after{{content:"";position:absolute;inset:9px 8px;background:{C.INK};
  clip-path:polygon(0 40%,100% 0,100% 60%,0 100%)}}
.eyebrow{{color:{C.PATINA};font-size:11px;letter-spacing:.14em;text-transform:uppercase;
  font-weight:700}}
.brand h1{{font-size:19px}}
.meta{{text-align:right;font-size:12.5px;color:{C.LIME_DIM};line-height:1.5}}
.meta b{{color:{C.LIME}}}
.appetite{{background:{C.PATINA};color:{C.INK};font-weight:700;border-radius:999px;
  padding:2px 10px;font-size:12px}}
.sub{{background:{C.INK_RAISED};color:{C.LIME_DIM};font-size:12.5px}}
/* This banner sits BELOW the dark chrome, on the light workbench — but `.sub` is
   a chrome class and brings limestone text with it. Amber at 15% over the
   workbench is #F3E5CC; limestone on that is 1.01:1, i.e. the single most
   important caveat on this screen was invisible. Ink on it is 14.45:1. */
.sub.provisional{{background:{C.BAND["high"]}26;color:{C.INK};
  border-bottom:1px solid {C.BAND["high"]}66}}
.sub.provisional b{{color:{C.INK}}}
.placeholder{{color:{C.SLATE};font-style:italic}}
.provtag{{display:inline-block;background:{C.BAND["high"]}2e;color:{C.BAND_TEXT["high"]};
  border-radius:999px;padding:1px 7px;font-size:10.5px;font-weight:700;white-space:nowrap}}
.placeholder code{{font-style:normal;font-family:'IBM Plex Mono',ui-monospace,monospace;
  font-size:11px}}
.sub .wrap{{padding:8px 24px;display:flex;justify-content:space-between;gap:16px;flex-wrap:wrap}}
.section{{margin-top:26px}}
.section h2{{font-size:15px;margin-bottom:12px}}
.tiles{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}}
.tile{{background:{C.WB_SURF};border:1px solid {C.WB_LINE};border-radius:12px;padding:14px 16px}}
.tile .n{{font-family:'Space Grotesk',sans-serif;font-size:30px;font-weight:600;line-height:1}}
.tile .l{{color:{C.INK};font-size:12.5px;margin-top:6px;font-weight:600}}
.tile .s{{color:{C.SLATE};font-size:11.5px;margin-top:2px}}
.tile.warn{{border-color:{C.BAND['high']}}}
.bandrow{{display:flex;gap:8px;margin-top:12px}}
.bandpill{{flex:1;border-radius:8px;padding:8px;text-align:center;font-size:12px}}
.bandpill .bn{{font-family:'Space Grotesk';font-size:19px;font-weight:600;display:block}}
.top{{display:grid;grid-template-columns:auto 1fr;gap:24px;align-items:start}}
/* A grid item defaults to min-width:auto — its min-content size — so one long
   table cell props the whole column, and the page, open. Overriding it is what
   lets the scroll container below actually take effect. */
.top>*,.attgrid>*,.tiles>*{{min-width:0}}
.card{{background:{C.WB_SURF};border:1px solid {C.WB_LINE};border-radius:12px;padding:16px}}
.toggle{{display:inline-flex;border:1px solid {C.WB_LINE};border-radius:8px;overflow:hidden;
  margin-bottom:12px}}
.toggle button{{border:none;background:{C.WB_SURF};padding:6px 14px;font:inherit;font-size:12.5px;
  cursor:pointer;color:{C.SLATE}}}
.toggle button.on{{background:{C.INK};color:{C.LIME};font-weight:700}}
.matrix{{border-collapse:collapse}}
.matrix td.cell{{width:46px;height:46px;text-align:center;font-weight:700;font-size:14px;
  border:2px solid {C.WB};cursor:pointer;transition:transform .08s}}
.matrix td.cell:hover{{transform:scale(1.08);outline:2px solid {C.INK}}}
.matrix td.cell.sel{{outline:3px solid {C.INK};outline-offset:-3px}}
.matrix td.cell.dim{{opacity:.28}}
.matrix td.ax{{color:{C.SLATE};font-size:11px;padding:2px 6px}}
.axtitle{{color:{C.SLATE};font-size:11px;letter-spacing:.08em;text-transform:uppercase}}
.controls{{display:flex;align-items:center;gap:14px;margin-bottom:10px;flex-wrap:wrap}}
.fbtn{{border:1px solid {C.WB_LINE};background:{C.WB_SURF};color:{C.SLATE};border-radius:8px;
  padding:6px 12px;font:inherit;font-size:12.5px;cursor:pointer}}
.fbtn.on{{background:{C.BAND['high']};border-color:{C.BAND['high']};color:{C.BAND_ON['high']};font-weight:700}}
.filterbar{{font-size:12.5px;color:{C.SLATE}}}
.filterbar .clear{{color:{C.PATINA_TEXT};cursor:pointer;font-weight:700;text-decoration:underline;
  margin-left:8px}}
table.reg{{width:100%;border-collapse:collapse;font-size:12.5px;background:{C.WB_SURF};
  border:1px solid {C.WB_LINE};border-radius:12px;overflow:hidden}}
/* A wide table scrolls inside its own box. Without this the table sets the page
   width and the whole document scrolls sideways on a phone, so sections start
   off-screen. min-width keeps the columns legible rather than crushing them. */
.tscroll{{overflow-x:auto}}
.tscroll>table.reg{{min-width:620px}}
.tscroll.slim>table.reg{{min-width:330px}}
table.reg th{{background:{C.INK};color:{C.LIME};text-align:left;padding:9px 10px;font-size:11.5px;
  cursor:pointer;user-select:none;white-space:nowrap}}
table.reg th:hover{{color:#fff}}
table.reg th .ar{{color:{C.PATINA};margin-left:4px}}
table.reg tr.row{{cursor:pointer}}
table.reg tr.row:hover td{{background:#eef4f2}}
table.reg td{{padding:8px 10px;border-top:1px solid {C.WB_LINE}}}
.chip{{border-radius:999px;padding:2px 8px;font-size:11px;font-weight:700;white-space:nowrap}}
.flag{{color:{C.BAND_TEXT['critical']};font-weight:700}}
.warnmark{{color:{C.BAND_TEXT['high']};font-weight:700}}
.hint{{color:{C.SLATE};font-size:12px;font-style:italic;margin-top:6px}}
.attgrid{{display:grid;grid-template-columns:repeat(2,1fr);gap:12px;align-items:start}}
.att{{background:{C.WB_SURF};border:1px solid {C.WB_LINE};border-left:5px solid {C.SLATE};
  border-radius:10px;padding:12px 14px}}
.att h3{{font-size:12.5px;text-transform:uppercase;letter-spacing:.05em;color:{C.SLATE};
  margin-bottom:8px}}
.att h3 .cnt{{background:{C.INK};color:{C.LIME};border-radius:999px;padding:1px 8px;
  font-size:11px;margin-left:4px}}
.att li{{font-size:12.5px;line-height:1.45;margin-bottom:7px}}
.att .d{{color:{C.SLATE};display:block;font-size:11.5px}}
ul.plain{{list-style:none;padding:0;margin:0}}
.backdrop{{position:fixed;inset:0;background:rgba(20,23,28,.45);opacity:0;pointer-events:none;
  transition:opacity .2s;z-index:5}}
.backdrop.open{{opacity:1;pointer-events:auto}}
.drawer{{position:fixed;top:0;right:0;height:100%;width:460px;max-width:92vw;background:{C.WB};
  box-shadow:-8px 0 40px rgba(0,0,0,.25);transform:translateX(100%);transition:transform .22s;
  z-index:6;overflow-y:auto}}
.drawer.open{{transform:none}}
.dhead{{background:{C.INK};color:{C.LIME};padding:18px 20px;position:relative}}
.dhead .id{{color:{C.PATINA};font-weight:700;font-size:12px;letter-spacing:.1em}}
.dhead h2{{font-size:18px;margin-top:4px;line-height:1.25;padding-right:28px}}
.dclose{{position:absolute;top:14px;right:16px;background:none;border:none;color:{C.LIME};
  font-size:24px;cursor:pointer;line-height:1}}
.dbody{{padding:18px 20px}}
.kv{{display:grid;grid-template-columns:110px 1fr;gap:6px 12px;font-size:13px;margin-bottom:16px}}
.kv .k{{color:{C.SLATE}}}
.scores{{display:flex;gap:10px;margin-bottom:16px}}
.score{{flex:1;background:{C.WB_SURF};border:1px solid {C.WB_LINE};border-radius:10px;
  padding:10px 12px}}
.score .lab{{color:{C.SLATE};font-size:11px;text-transform:uppercase;letter-spacing:.05em}}
.score .val{{font-family:'Space Grotesk';font-size:20px;font-weight:600;margin-top:3px}}
.blk{{margin-bottom:16px}}
.blk h3{{font-size:12px;text-transform:uppercase;letter-spacing:.06em;color:{C.SLATE};
  margin-bottom:6px}}
.blk p{{margin:0;font-size:13px;line-height:1.5}}
.muted{{color:{C.SLATE};font-style:italic}}
.accept{{background:#fff;border:1px solid {C.WB_LINE};border-left:4px solid {C.BAND['low']};
  border-radius:8px;padding:10px 12px;font-size:12.5px;line-height:1.5}}
.accept.stale{{border-left-color:{C.BAND['critical']}}}
.hist{{border-left:2px solid {C.WB_LINE};padding-left:12px}}
.hist .ev{{margin-bottom:12px;font-size:12.5px}}
.hist .ev .t{{color:{C.SLATE};font-size:11px}}
.hist .ev .c{{font-weight:700}}
.hist .ev .r{{font-style:italic}}
footer{{margin-top:32px;color:{C.SLATE};font-size:11px;border-top:1px solid {C.WB_LINE};
  padding-top:14px}}
/* Column counts are declared here, never inline on the element — an inline
   grid-template-columns outranks a media rule and silently defeats it. */
@media (max-width:900px){{.top{{grid-template-columns:1fr}}}}
@media (max-width:720px){{
  .wrap,.sub .wrap{{padding-left:14px;padding-right:14px}}
  .tiles{{grid-template-columns:repeat(2,1fr)}}
  .attgrid{{grid-template-columns:1fr}}
  .meta{{text-align:left}}
}}
@media (max-width:460px){{.tiles{{grid-template-columns:1fr}}.bandrow{{flex-wrap:wrap}}}}
{C.mark_css()}"""

SCRIPT = r"""
const DB=__DATA__;const BAND=__BAND__;const BL=__BANDLABEL__;const BAND_ON=__BANDON__;
// Injected, not inlined: this block is a plain string, so a colour written here would
// survive --brand and print CAC green on a client's page.
const VELCOLOR=__VELCOLOR__;
// The matrix draws ZONES, so it takes the zone tones — the same ones G.heat_matrix
// uses for this grid on the board page. Chips elsewhere stay on BAND, which is the
// saturated fill, because a chip IS a status mark rather than a region of the score
// space. Two different jobs, two different tones, one grid either way.
const BAND_MID=__BANDMID__;const BAND_MID_ON=__BANDMIDON__;
const size=DB.settings.matrixSize;const appetite=DB.settings.appetite;
const BAND_ORDER=["low","medium","high","critical"];
const THRESH={5:{low:1,medium:5,high:10,critical:15},4:{low:1,medium:4,high:8,critical:12},
  3:{low:1,medium:3,high:5,critical:7}}[size];
let view="residual",sel=null,overOnly=false,sortK="residualExposure",sortDir=-1;
const VELRANK={improving:0,steady:1,new:2,worsening:3};
const VELMARK={improving:"▼",worsening:"▲",steady:"→",new:"＋"};
const COLS=[{k:"id",l:"ID",t:"s"},{k:"title",l:"Risk",t:"s"},{k:"themeName",l:"Theme",t:"s"},
 {k:"response",l:"Response",t:"s"},{k:"exposure",l:"Exposure",t:"n"},{k:"velocity",l:"Trend",t:"n"},
 {k:"owner",l:"Owner",t:"s"},{k:"status",l:"Status",t:"s"},{k:"flags",l:"Flags",t:"s"}];
function bandOf(e){for(const b of ["critical","high","medium","low"])if(e>=THRESH[b])return b;return "low";}
function expOf(r){return r[view].likelihood*r[view].impact;}
function bandOfView(r){return bandOf(expOf(r));}
function isOver(r){return BAND_ORDER.indexOf(bandOfView(r))>BAND_ORDER.indexOf(appetite);}
function chip(b){const fg=BAND_ON[b];
  return `<span class="chip" style="background:${BAND[b]};color:${fg}">${BL[b]}</span>`;}
function inCell(r,l,i){return r[view].likelihood===l&&r[view].impact===i;}
function flagsOf(r){const f=[];
  if(r.reviewOverdue)f.push('<span class="warnmark" title="review overdue">⏱</span>');
  if(r.acceptanceDue||r.acceptanceExpired)f.push('<span class="flag" title="acceptance due for re-validation">↻</span>');
  if(r.acceptanceIncomplete)f.push('<span class="flag" title="acceptance incomplete">!</span>');
  if(r.unowned)f.push('<span class="warnmark" title="no owner">◌</span>');
  if(r.outOfRange)f.push('<span class="warnmark" title="scored above the matrix">↗</span>');
  return f.join(" ");}
function val(r,k){if(k==="exposure")return expOf(r);if(k==="velocity")return VELRANK[r.velocity];
  if(k==="response")return r.response.type;if(k==="flags")return flagsOf(r).length;return r[k];}
function filtered(){return DB.risks.filter(r=>(!sel||inCell(r,sel[0],sel[1]))&&(!overOnly||isOver(r)));}
function sorted(list){const c=COLS.find(x=>x.k===sortK)||{t:"n"};
  return list.slice().sort((a,b)=>{const x=val(a,sortK==="residualExposure"?"exposure":sortK),
    y=val(b,sortK==="residualExposure"?"exposure":sortK);
    return ((c.t==="n")?(x-y):String(x).localeCompare(String(y)))*sortDir;});}
function renderHead(){document.getElementById("head").innerHTML=COLS.map(c=>{
  const lab=c.k==="exposure"?(view==="residual"?"Residual":"Inherent"):c.l;
  const key=c.k==="exposure"?"exposure":c.k;
  const ar=key===sortK?`<span class="ar">${sortDir>0?"▲":"▼"}</span>`:"";
  return `<th onclick="setSort('${key}')">${lab}${ar}</th>`;}).join("");}
function renderGrid(){let h='<table class="matrix">';
 const inRange=DB.risks.filter(r=>!r.outOfRange);
 for(let impact=size;impact>=1;impact--){h+=`<tr><td class="ax">${impact}</td>`;
  for(let lik=1;lik<=size;lik++){const b=bandOf(lik*impact);
   const n=inRange.filter(r=>inCell(r,lik,impact)).length;
   const s=sel&&sel[0]===lik&&sel[1]===impact?" sel":(sel?" dim":"");
   const fg=BAND_MID_ON[b];
   h+=`<td class="cell${s}" style="background:${BAND_MID[b]};color:${fg}" onclick="pick(${lik},${impact})">${n||""}</td>`;}
  h+="</tr>";}
 h+='<tr><td class="ax"></td>';for(let l=1;l<=size;l++)h+=`<td class="ax">${l}</td>`;
 h+="</tr></table>";document.getElementById("grid").innerHTML=h;
 const skipped=DB.risks.length-inRange.length;
 document.getElementById("skip").innerHTML=skipped?
   `${skipped} risk${skipped>1?"s":""} scored above the ${size}×${size} matrix and ${skipped>1?"are":"is"} not plotted (still counted in every total).`:"";}
function renderRows(){const list=sorted(filtered());
 document.getElementById("rows").innerHTML=list.map(r=>`<tr class="row" onclick="openDrawer('${r.id}')">
  <td>${r.id}</td><td>${r.title}${r.provisionalTitle?' <span class="provtag">unreworded</span>':''}</td><td>${r.themeName}</td><td>${r.response.type}</td>
  <td>${chip(bandOfView(r))} ${expOf(r)} ${isOver(r)?'<span class="flag">⚠</span>':''}</td>
  <td style="color:${{improving:BAND.low,worsening:BAND.critical,steady:VELCOLOR.steady,new:VELCOLOR.new}[r.velocity]}"
    title="${r.priorExposure===null?"no baseline":"was "+r.priorExposure+" at "+DB.baseline}">${VELMARK[r.velocity]}</td>
  <td>${r.owner||'<span class="muted">unowned</span>'}</td><td>${r.status}</td>
  <td>${flagsOf(r)}</td></tr>`).join("");
 const parts=[`${list.length} of ${DB.risks.length} risks · ${view} view`];
 if(sel)parts.push(`cell L${sel[0]}×I${sel[1]}`);if(overOnly)parts.push("over appetite only");
 document.getElementById("filter").innerHTML=parts.join(" · ")+
   ((sel||overOnly)?`<span class="clear" onclick="clearFilters()">clear filters</span>`:"");}
function draw(){renderHead();renderGrid();renderRows();}
function pick(l,i){sel=(sel&&sel[0]===l&&sel[1]===i)?null:[l,i];draw();}
function toggleOver(){overOnly=!overOnly;
 document.getElementById("overBtn").classList.toggle("on",overOnly);draw();}
function clearFilters(){sel=null;overOnly=false;
 document.getElementById("overBtn").classList.remove("on");draw();}
function setSort(k){const c=COLS.find(x=>x.k===k||(k==="exposure"&&x.k==="exposure"))||{t:"n"};
 if(sortK===k)sortDir=-sortDir;else{sortK=k;sortDir=(c.t==="n")?-1:1;}draw();}
function setView(v){view=v;sel=null;
 document.getElementById("bRes").classList.toggle("on",v==="residual");
 document.getElementById("bInh").classList.toggle("on",v==="inherent");draw();}
function openDrawer(id){const r=DB.risks.find(x=>x.id===id);const d=document.getElementById("drawer");
 const acc=r.acceptance;const stale=r.acceptanceDue||r.acceptanceExpired||r.acceptanceIncomplete;
 const accNote=r.acceptanceExpired?"past expiry":r.acceptanceDue?"due for re-validation":
   r.acceptanceIncomplete?"incomplete":"";
 d.innerHTML=`<div class="dhead"><button class="dclose" onclick="closeDrawer()">×</button>
   <div class="id">${r.id} · ${r.themeName}${r.provisionalTitle?' · <span class="provtag">title not reworded — withheld from board views</span>':''}${r.provisionalScore?' · <span class="provtag">score is an import seed</span>':''}</div><h2>${r.title}</h2></div><div class="dbody">
   <div class="scores">
     <div class="score"><div class="lab">Inherent</div><div class="val">${r.inherent.likelihood}×${r.inherent.impact}=${r.inherentExposure}</div>${chip(r.inherentBand)}</div>
     <div class="score"><div class="lab">Residual</div><div class="val">${r.residual.likelihood}×${r.residual.impact}=${r.residualExposure}</div>${chip(r.residualBand)} ${r.overAppetite?'<span class="flag">⚠ over</span>':''}</div></div>
   <div class="kv"><span class="k">Category</span><span>${r.category||"—"}</span>
     <span class="k">Owner</span><span>${r.owner||'<span class="muted">unowned</span>'}</span>
     <span class="k">Status</span><span>${r.status}</span>
     <span class="k">Review</span><span>${r.reviewDate||"—"}${r.reviewOverdue?' <span class="warnmark">overdue</span>':''}</span>
     <span class="k">Since ${DB.baseline||"baseline"}</span><span>${r.priorExposure===null?'<span class="muted">no baseline</span>':`${r.priorExposure} → ${r.residualExposure} ${VELMARK[r.velocity]}`}</span>
     <span class="k">CSF</span><span>${r.csfSubcategoryId||"—"}</span></div>
   <div class="blk"><h3>Risk (event statement)</h3><p>${r.description||'<span class="muted">No event statement recorded.</span>'}</p></div>
   <div class="blk"><h3>Response — ${r.response.type}${r.response.cost?` · $${r.response.cost.toLocaleString()}`:''}</h3><p>${r.response.description||'<span class="muted">—</span>'}</p></div>
   ${acc?`<div class="blk"><h3>Acceptance ${accNote?`· <span style="color:${BAND.critical}">${accNote}</span>`:''}</h3>
     <div class="accept${stale?' stale':''}"><b>${acc.approver||'<span class="flag">no approver recorded</span>'}</b> · accepted ${acc.acceptedDate||"—"} · re-validate by ${acc.revalidationDate||"—"}${acc.expiryDate?` · expires ${acc.expiryDate}`:''}<br>${acc.justification||'<span class="flag">no justification recorded</span>'}</div></div>`:''}
   ${r.translation?`<div class="blk"><h3>Board translation</h3><p>${r.translation}</p></div>`:''}
   ${r.notes?`<div class="blk"><h3>Notes</h3><p>${r.notes}</p></div>`:''}
   <div class="blk"><h3>Change history</h3>${r.history.length?`<div class="hist">${r.history.slice().reverse().map(h=>{
     const move=(h.from!==undefined&&h.to!==undefined)?
       `${h.field||""} ${fmt(h.from)} → ${fmt(h.to)}`:(h.field||h.type);
     return `<div class="ev"><div class="t">${(h.ts||"").slice(0,10)} · ${h.actor||"—"} · ${h.type}</div>
       <div class="c">${move}</div>${h.rationale?`<div class="r">${h.rationale}</div>`:''}</div>`;}).join("")}</div>`
     :'<p class="muted">No logged changes yet.</p>'}</div>
   </div>`;
 d.classList.add("open");document.getElementById("backdrop").classList.add("open");}
function fmt(v){return (v&&typeof v==="object")?`${v.likelihood}×${v.impact}=${v.likelihood*v.impact}`:v;}
function closeDrawer(){document.getElementById("drawer").classList.remove("open");
 document.getElementById("backdrop").classList.remove("open");}
document.addEventListener("keydown",e=>{if(e.key==="Escape")closeDrawer();});
draw();
"""


def render(ctx: C.Context) -> str:
    m, s = ctx.meta, ctx.settings
    script = (SCRIPT.replace("__DATA__", build_data(ctx))
              .replace("__BANDLABEL__", json.dumps(C.BAND_LABEL))
              .replace("__BANDON__", json.dumps(C.BAND_ON))
              .replace("__BAND__", json.dumps(C.BAND))
              .replace("__VELCOLOR__", json.dumps(C.VELOCITY_COLOR))
              .replace("__BANDMIDON__", json.dumps(C.BAND_MID_ON))
              .replace("__BANDMID__", json.dumps(C.BAND_MID)))
    client = C.esc(m.get("clientName") or "")
    title_tail = " · " + client if client else ""
    note = C.provisional_note(ctx.live)
    prov_banner = (f'<div class="sub provisional"><div class="wrap">{note}</div></div>'
                   if note else "")
    # Its own section, deliberately not an attention list — see confirmation_panel(). Built
    # here rather than interpolated inline so a register with no live risk renders no heading
    # over an empty card.
    conf = confirmation_panel(ctx)
    conf_section = (f'<div class="section"><h2>How old these determinations are</h2>{conf}'
                    f'</div>' if conf else "")
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Risk Register — Working View{title_tail}</title>
{C.fonts(ctx.offline)}<style>{css()}</style></head><body>
<header><div class="wrap"><div class="brand"><div class="mark"></div><div>
  <div class="eyebrow">Cyber Aware Creations · Risk Register</div>
  <h1>Heat map &amp; register — working view</h1></div></div>
  <div class="meta"><b>{C.esc(m.get('clientName') or '(unnamed register)')}</b><br>
  {C.esc(m.get('assessor') or '—')}<br>
  <span class="appetite">Appetite: {C.esc(s['appetite'])}</span>
  &nbsp;{s['matrixSize']}×{s['matrixSize']} matrix</div></div></header>
<div class="sub"><div class="wrap"><span>{C.esc(ctx.as_of_line())}</span>
  <span>Toggle inherent / residual · click a cell to drill in · sort any column · click a risk for detail</span>
</div></div>
{prov_banner}
<div class="wrap">
  {C.gfx_band("Cyber Aware Creations", "Working view")}
  <div class="section">{tiles(ctx)}</div>
  <div class="section top">
    <div class="card">
      <div class="toggle"><button id="bRes" class="on" onclick="setView('residual')">Residual</button>
        <button id="bInh" onclick="setView('inherent')">Inherent</button></div>
      <div class="axtitle">↑ Impact</div><div id="grid"></div>
      <div class="axtitle" style="text-align:right">Likelihood →</div>
      <div class="hint" id="skip"></div>
    </div>
    <div>
      <div class="controls">
        <button id="overBtn" class="fbtn" onclick="toggleOver()">⚠ Over appetite only</button>
        <span class="filterbar" id="filter"></span>
      </div>
      <div class="tscroll">
        <table class="reg"><thead><tr id="head"></tr></thead><tbody id="rows"></tbody></table></div>
      <div class="hint">Flags: ⏱ review overdue · ↻ acceptance due for re-validation ·
        ! acceptance incomplete · ◌ unowned · ↗ scored above the matrix.</div>
    </div>
  </div>
  <div class="section"><h2>Band mix and the biggest exposures</h2>
    {shape_block(ctx)}</div>
  <div class="section"><h2>Needs attention</h2>
    <div class="attgrid">{attention_lists(ctx)}</div></div>
  {conf_section}
  <div class="section"><h2>Owner load — open risk per owner</h2>
    <div class="tscroll slim">{owner_table(ctx)}</div></div>
  <footer>{C.esc(ctx.footer("operational working view"))}</footer>
</div>
<div class="backdrop" id="backdrop" onclick="closeDrawer()"></div>
<div class="drawer" id="drawer"></div>
<script>{script}</script></body></html>"""


if __name__ == "__main__":
    ctx = C.build(sys.argv[1:], __doc__, "risk-register-working-view.html")
    C.write(ctx, render(ctx))
