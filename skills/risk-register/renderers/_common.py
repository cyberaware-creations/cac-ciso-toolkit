#!/usr/bin/env python3
"""
_common.py — shared, data-driven derivation layer for the risk-register renderers.

Every number the three renderers show is derived here from a schema-v2 register:
themes from `themes` + each risk's `theme`, per-risk velocity and the register-wide
trend from `snapshots`, staleness from `acceptance` / `reviewDate` against --today.
Nothing about a specific register is hardcoded.

Board *language* is never derived — it is supplied by the `ciso-board-translation`
skill through an optional --translations sidecar, or clearly marked as absent.

Standard library only.
"""

from __future__ import annotations

import argparse
import html
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import score_register as sr  # noqa: E402

# --- Brand tokens (assets/brand.md) ------------------------------------------
# Patina is the brand/action accent and never signals "safe"; severity always
# uses the RAG ramp.
INK = "#14171C"; INK_RAISED = "#1C2026"; INK_LINE = "#2A2F36"
LIME = "#EAE7DF"; LIME_DIM = "#9AA0A6"
PATINA = "#2FA98C"; PATINA_H = "#279884"
# Patina reads well as text on the dark chrome (6.14:1 on ink) and badly on the
# light workbench (2.66:1). Same accent, two surfaces, two values.
PATINA_TEXT = "#1C6F5A"
# Slate was #6A7180: 4.45:1 on the workbench, just under the 4.5 AA floor, and it
# carries hints, footers, filter bars and table headers in every artifact. One
# step darker clears all of them at once.
SLATE = "#666D7C"; WB = "#F6F4EE"; WB_SURF = "#FFFFFF"; WB_LINE = "#D8D3C6"
# medium is amber, not a second green. Two adjacent greens are not separable at
# stacked-bar size — which also made a bar full of unrefined import seeds read as
# "we're fine" — and a ramp that runs green→green→orange→red is not the CVD-safe
# green→red brand.md claims. Lightness now carries the step as well as hue.
# low was #2e8b57, which tops out at 4.25:1 against its best text colour — the one
# band fill no text colour could rescue. A small lift clears AA with ink on top.
BAND = {"low": "#30915B", "medium": "#e8c547", "high": "#e08e0b", "critical": "#c0392b"}
BAND_LABEL = {"low": "Low", "medium": "Medium", "high": "High", "critical": "Critical"}

# A fill and a text colour are different jobs and the same hex cannot do both.
# BAND is for fills — text goes *on* it, and text_on() picks what. BAND_TEXT is
# for the cases where the band colour IS the text (a ⚠ mark, a velocity arrow, a
# tag) on a light surface, where the fill values run 1.5–2.6:1 and are unreadable.
BAND_TEXT = {"low": "#25764A", "medium": "#7A6410", "high": "#8F5B06",
             "critical": "#c0392b"}

# Two font modes. The brand faces come from Google Fonts, which means opening a report
# makes an outbound request — for a document full of a client's risk data, that is a real
# (if small) disclosure, and the dashboards were documented as making "no external calls".
#
# `--offline` is the honest escape hatch: no request, system stack, layout unchanged
# because the CSS already names fallbacks. Default stays branded.
FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com">'
         '<link href="https://fonts.googleapis.com/css2?family=Manrope:wght@400;600;700'
         '&family=Space+Grotesk:wght@500;600&display=swap" rel="stylesheet">')
FONTS_OFFLINE = ""


def fonts(offline: bool = False) -> str:
    """The <head> font links, or nothing at all when rendering offline."""
    return FONTS_OFFLINE if offline else FONTS


DISCLAIMER = "A Cyber Aware Creation · Not affiliated with NIST"

# Confirmation-age band width T, in days. One definition, one place. The twin
# (nist-csf's attention_lists) makes the equivalent parameter REQUIRED with no default
# precisely so the engine cannot hold the threshold in two spots and drift; the same
# reasoning applies here, so this constant is argparse's default and nothing else's.
# Matches nist-csf's ageThresholdDays.
DEFAULT_AGE_THRESHOLD = 180


def age_bounds(threshold_days: int) -> dict:
    """The four confirmation-age bands as inclusive day boundaries, derived from T.

    `{band: (low, high)}`, with `high is None` for the open-ended top band. Boundaries
    only — no wording. The views that print them are in different sentence shapes ("0–90d"
    on a counted row; "within the last 90 days" in a board sentence) and must not converge
    on one string, but they must not each re-derive `t // 2` either.

    THE ONLY `t // 2` IN THIS SKILL'S RENDERERS, which it was not when it was written: it
    landed with a single caller — freshness_line() below — while render_dashboard's `edges`
    dict still built its own copy, so it was the fifth statement of one formula rather than a
    consolidation, and two docstrings said otherwise. Both callers now read it, the
    render_dashboard copy is gone, and `age_band()` in ../scripts/score_register.py owns the
    semantics this function restates.

    age_band_ranges() and the age_band_bar() labels in skills/nist-csf/renderers/_common.py
    stay separate on purpose. That is a DECLARED cross-skill twin, like age_band and
    AGE_BAND_LABEL, where the semantics must match and the wording must not; it is not
    something left undone here.

    EXCLUSIVE ranges, mirroring sr.age_band(): each band is inclusive of its upper bound
    and `within` runs to T // 2. Cumulative ranges over mutually-exclusive counts are both
    false and flattering — "within 360 days" once captioned the count of determinations
    PAST the chosen cadence, on the board renderer.

    Agreement with sr.age_band() at every boundary is asserted in evals/confirmation-age.sh
    rather than assumed; this function restates that function's boundaries, and two
    statements of one rule that nothing compares will drift.
    """
    half = threshold_days // 2
    return {"within": (0, half), "approaching": (half + 1, threshold_days),
            "beyond": (threshold_days + 1, threshold_days * 2),
            "wellBeyond": (threshold_days * 2 + 1, None)}


def id_list(risks: list, cap: int) -> str:
    """`R-001, R-002, R-004 +2 more` — IDs only, capped, escaped.

    IDs and never titles, on every surface. An imported CSF gap carries raw framework
    wording as its title until somebody rewords it, and that wording has already reached a
    board page by three separate routes — the third being the change log, which the title
    guard's own docstring had not anticipated. A list of names beside a count would be a
    fourth. risk_title() exists for the places a title is genuinely wanted and can carry a
    placeholder; a count's supporting list is not one of them and has nowhere to put one.

    Naming them is the point, not a concession: _decisions() cites IDs for every board item
    it raises, and a director who cannot name the record cannot ask about it. The cap keeps
    a row or clause that points into the register from becoming a second copy of it.

    THE ONLY COPY. render_dashboard.py carried a module-private `_id_list()` that was this
    function character for character, with a default of 6; it is deleted and both of its call
    sites now read this one. That duplicate was undeclared, which in this repo is the
    exception — every intentional twin is declared at both ends (age_band, AGE_BAND_LABEL) —
    and the reason it is worth saying so here is that the two surfaces disagree about the cap
    and always will, so the shared thing is the formatting and nothing else.

    `cap` is REQUIRED and carries no default. The board sentence passes 5 on both of its
    clauses; the operational panel passes 6 on both of its rows, which is what the deleted
    twin's default silently supplied. A default would therefore be a fifth number for a
    reader to reconcile against four real ones, and it would let a new surface quote the
    register by accident. A cap is a per-surface editorial judgement about how much of the
    register one sentence or row may repeat, and there is no defensible default for it.
    """
    shown = ", ".join(esc(r["id"]) for r in risks[:cap])
    return shown + (f" +{len(risks) - cap} more" if len(risks) > cap else "")


UNCLASSIFIED = "Unclassified"
VELOCITY_MARK = {"improving": "▼", "worsening": "▲", "steady": "→", "new": "＋"}
# These are arrows drawn *as text* on the light workbench, so they take the text
# ramp, not the fill ramp. Patina as text is 2.9:1 — the ink-on-patina button is
# fine, patina-on-workbench is not.
VELOCITY_COLOR = {"improving": BAND_TEXT["low"], "worsening": BAND_TEXT["critical"],
                  "steady": SLATE, "new": PATINA_TEXT}


def esc(s) -> str:
    return html.escape("" if s is None else str(s))


# --- Contrast ----------------------------------------------------------------
# The text colour for a fill is derived, never hand-picked. It was hand-picked in
# four places — `chip()`, the band pills, and twice more in the dashboard's inline
# JS — as `white if band in (high, critical) else ink`. That rule is wrong for
# amber: white on #e08e0b is 2.61:1, ink on it is 6.88:1. Four copies of one wrong
# judgement, and the two in JS were invisible to any check that reads Python.

def _luminance(hex_colour: str) -> float:
    h = hex_colour.lstrip("#")
    if len(h) == 3:
        h = "".join(ch * 2 for ch in h)
    chans = []
    for i in (0, 2, 4):
        v = int(h[i:i + 2], 16) / 255.0
        chans.append(v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4)
    return 0.2126 * chans[0] + 0.7152 * chans[1] + 0.0722 * chans[2]


def contrast_ratio(a: str, b: str) -> float:
    """WCAG 2.x contrast ratio between two opaque colours. 1.0 … 21.0."""
    la, lb = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def text_on(fill: str) -> str:
    """The brand text colour with the most contrast on `fill`.

    Ink for light fills, limestone/white for dark ones — decided by measurement so
    a change to a fill cannot silently leave unreadable text behind it.
    """
    return max((INK, LIME, "#FFFFFF"), key=lambda fg: contrast_ratio(fg, fill))


# Precomputed so the dashboard's inline JS can be handed the same answers rather
# than reimplementing the rule and drifting from it.
BAND_ON = {b: text_on(c) for b, c in BAND.items()}


def chip(band: str) -> str:
    return (f'<span class="chip" style="background:{BAND[band]};color:{BAND_ON[band]}">'
            f'{BAND_LABEL[band]}</span>')


def risk_title(r: dict, bold: bool = False) -> str:
    """The one place a risk title becomes board-facing HTML.

    A risk whose title is still CSF framework wording gets a placeholder instead. That
    wording is a control objective phrased as a good thing — "Information is correlated
    from multiple sources" — and printed next to a Critical chip it reads to a director
    as the opposite of what it says.

    Every renderer must go through here. This guard was originally written into the
    executive dashboard alone, which left the printable board report — the artifact most
    likely to be handed round a table on paper — exposing exactly what it exists to
    prevent.
    """
    if r.get("provisionalTitle"):
        return (f'<span class="placeholder">Risk statement not yet written for {esc(r["id"])} — '
                f'imported CSF gap, still framework wording. Reword it with '
                f'<code>set-text</code>.</span>')
    t = esc(r.get("title", ""))
    return f"<b>{t}</b>" if bold else t


def provisional_note(summary: dict) -> str:
    """One-line disclosure for any artifact whose totals include unreviewed candidates.

    Returns "" when there is nothing to disclose, so it is safe to drop into any layout.
    """
    n = summary.get("provisional", 0)
    if not n:
        return ""
    bits = []
    if summary.get("provisionalTitle"):
        bits.append(f'{summary["provisionalTitle"]} still carry CSF framework wording as a '
                    f'title and appear as placeholders')
    if summary.get("provisionalScore"):
        bits.append(f'{summary["provisionalScore"]} still sit on the import priority seed, so '
                    f'their scores are placeholders rather than assessments')
    return (f'<b>{n} of {summary["total"]} risks are provisional.</b> '
            + "; ".join(bits) + ". The figures here include them.")


# --- CLI ---------------------------------------------------------------------


def _today_utc() -> str:
    """Today's date in UTC — the reference date every derived age is measured against.

    This was `date.today()`, the LOCAL date, and that was a live defect rather than a
    style question. `score_register._now()` writes every history `ts` in UTC, so west of
    Greenwich an event written this evening is dated tomorrow: reproduced at 17:57 PDT
    with the engine writing 2026-07-30 against a default --today of 2026-07-29, and four
    operational cards reading "confirmed 2026-07-30, dated in the future".

    Not merely cosmetic. `age_band(-1, T)` returns `within` by documented design — it is a
    pure distance and an `impossible` band would smuggle a validation verdict into the
    distribution — so a future-dated confirmation is counted INSIDE the cadence. A
    register skewed one day forward therefore reports as fresher than it is, on the board
    page as well as the working one.

    THE RESIDUAL, in full, because half of it is a trade and not a win. One reference date
    serves two kinds of date and cannot be locally correct for both: history `ts` is a
    machine timestamp in UTC, while these six are human calendar commitments somebody made
    in a local zone —

        reviewDate           -> reviewOverdue, reviewOverdueDays, the _decisions() line
                                "N risks are past the scheduled review date", and an
                                attention list on the working view
        revalidationDate     -> acceptanceDue, the third KPI TILE on the board page, and
                                the _decisions() line "Re-validate N risk acceptances"
        expiryDate           -> acceptanceExpired, the "past expiry" figure beside that
                                tile, and the _decisions() line "N acceptances have passed
                                the expiry date and no longer carry approval"
        acceptance.accepted  -> stamped by `accept` from _now()[:10], so already UTC
        snapshot ts          -> trend x-axis labels, already UTC
        meta timestamps      -> display only

    So for the first three, a renderer WEST of UTC now flags a deadline up to a day early,
    and one EAST of UTC flags it up to a day late. Late is the flattering direction, and it
    is the same direction this fix removes from confirmation age. That is not a free trade
    and it should not be described as one: what makes it the right trade is asymmetry of
    magnitude, not of direction. A deadline misread by one day at the boundary is off by one
    day and self-corrects tomorrow; a negative age is not off by one day, it inverts — it
    lands in `within`, the freshest band, and reports a register as CURRENT.

    Neither error is eliminated by choosing the other zone; the ≤1-day boundary error simply
    moves onto the ages, where it inverts instead of shifting. The real fix is a
    per-register reporting timezone, which settings.reporting defers (see parse_args). Until
    then: `--today` is a UTC calendar date, every artifact stamps the zone beside it so a
    reader in California is not silently told tomorrow's date, and anyone who needs a
    deadline evaluated in a particular local zone passes --today explicitly.

    nist-csf's profile_analysis._today() is the same helper, written the same way; the two
    skills compare UTC timestamps against a UTC reference or the comparison is incoherent
    by construction. Keep them in step.
    """
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def parse_args(argv: list[str], description: str, default_out: str) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=description)
    p.add_argument("register", help="path to the .rr register (schema v2)")
    p.add_argument("out", nargs="?", default=default_out,
                   help=f"output HTML path (default: ./{default_out})")
    # UTC, not the local date — see _today_utc(). The register's timestamps are UTC.
    p.add_argument("--today", default=_today_utc(), metavar="YYYY-MM-DD",
                   help="date to evaluate review/re-validation staleness and confirmation "
                        "age against (default: today's date in UTC, matching the timezone "
                        "the register's own history timestamps are written in)")
    p.add_argument("--translations", metavar="FILE",
                   help="board-language sidecar from the ciso-board-translation skill; "
                        "omitted means board narrative is shown as a labelled placeholder")
    p.add_argument("--offline", action="store_true",
                   help="omit the Google Fonts links so the file makes no external request; "
                        "falls back to the system font stack")
    # DEFAULT_AGE_THRESHOLD is the *only* place this number lives. Context deliberately
    # has no fallback of its own — see Context.__init__.
    #
    # DEFERRED, decided rather than missed: T is per-invocation, so `render_dashboard
    # --age-threshold 180` and `render_board --age-threshold 90` over one register can
    # tell two freshness stories with no mechanism forcing them to agree. The design spec
    # defers `settings.reporting.ageThresholdDays` — a register-level T all three
    # renderers would read — and this comment is here so the next person knows the gap
    # was accepted for now rather than overlooked.
    p.add_argument("--age-threshold", type=int, default=DEFAULT_AGE_THRESHOLD, metavar="DAYS",
                   help="confirmation-age band width T: within <= T/2, approaching <= T, "
                        "beyond <= 2T, wellBeyond over 2T. Reporting only — no threshold "
                        "here expires, suppresses or rescores anything "
                        f"(default: {DEFAULT_AGE_THRESHOLD}, matching nist-csf's "
                        f"ageThresholdDays)")
    args = p.parse_args(argv)
    try:
        date.fromisoformat(args.today)
    except ValueError:
        p.error(f"--today {args.today!r} is not a YYYY-MM-DD date")
    # T <= 0 makes the bands meaningless rather than merely harsh: at T=0 every boundary
    # collapses onto `days <= 0`, so a determination made today reads `within` and one made
    # yesterday reads `wellBeyond`. A negative T inverts them outright. Neither is a strict
    # cadence, it is a misconfiguration, and it should say so here rather than print a
    # distribution somebody would act on.
    if args.age_threshold <= 0:
        p.error(f"--age-threshold must be a positive number of days "
                f"(got {args.age_threshold})")
    return args


# --- Translations sidecar ----------------------------------------------------

PLACEHOLDER = ("Board narrative not supplied. Run the ciso-board-translation skill over this "
               "register and pass its output with --translations to replace this block.")


class Translations:
    """The ciso-board-translation sidecar. Never fabricates: absent means absent."""

    def __init__(self, raw: dict | None):
        self.absent = raw is None
        raw = raw or {}
        self.executive_summary = raw.get("executiveSummary") or None
        self.risks = raw.get("risks") or {}
        self.themes = raw.get("themes") or {}
        self.decisions = raw.get("decisions") or []
        self.as_of = raw.get("asOf") or None

    def risk(self, rid: str) -> str | None:
        return self.risks.get(rid) or None

    def theme(self, tid: str) -> str | None:
        return self.themes.get(tid) or None

    @staticmethod
    def load(path: str | None) -> "Translations":
        # Same handling as nist-csf's loader, deliberately. A sidecar that parses but maps
        # nothing is the dangerous case: the render "succeeds", every narrative falls back
        # to a placeholder, and the deck looks finished.
        if not path:
            return Translations(None)
        try:
            with open(path, encoding="utf-8") as fh:
                raw = json.load(fh)
        except FileNotFoundError:
            raise SystemExit(f"error: --translations file not found: {path}")
        except json.JSONDecodeError as exc:
            raise SystemExit(f"error: --translations file {path} is not valid JSON "
                             f"(line {exc.lineno}, column {exc.colno}): {exc.msg}")
        if not isinstance(raw, dict):
            raise SystemExit(f"error: --translations file {path} must contain a JSON object, "
                             f"got {type(raw).__name__}.")
        tr = Translations(raw)
        if not (tr.risks or tr.themes or tr.executive_summary or tr.decisions):
            hint = ""
            if raw and all(isinstance(v, str) for v in raw.values()):
                hint = ('\n  It looks like a flat {"R-001": "sentence"} map. '
                        'Wrap it: {"risks": { ... }}.')
            raise SystemExit(f"error: --translations file {path} contains no usable keys "
                             f'(expected "risks", "themes", "executiveSummary" or '
                             f'"decisions").{hint}')
        return tr


# --- Derivation --------------------------------------------------------------


def _overdue(value: str | None, today: str) -> bool:
    """True when an ISO date has been reached or passed. Blank/missing is never overdue."""
    return bool(value) and str(value)[:10] <= today


def _days_since(value: str | None, today: str) -> int | None:
    """Whole days from an ISO date (or timestamp) to `today`; None if absent or malformed.

    Tolerant on purpose. `_overdue()` above compares strings and can never raise, so a
    register carrying a typo'd date still renders — and worse, a typo like "2026-02-30"
    sorts as *past*, so `_overdue()` flags it and hands it straight to this function.
    Age must not be the one field that turns a bad date into a traceback on the evening
    a board pack is being produced: it reports "unknown", which is what it actually knows.
    """
    if not value:
        return None
    try:
        return (date.fromisoformat(today) - date.fromisoformat(str(value)[:10])).days
    except ValueError:
        return None


def live_risks(risks: list) -> list:
    """The risks a board is being asked about: everything not closed.

    One definition, called from every place that needs it. It was written out inline in
    live_summary(), _attention(), top_risks() and then again in the confirmation rollup —
    four verbatim copies of one rule, which is the same shape as the four hand-copied
    contrast judgements this module's own text_on() note describes.

    Named live_risks rather than live because Context.live is already a summary dict, and
    two different things called `live` one scope apart is a trap.
    """
    return [r for r in risks if r.get("status") != "closed"]


def live_summary(risks: list, size: int, appetite: str) -> dict:
    """`summarize()` over the risks a board is actually being asked about.

    `sr.summarize()` is a faithful port of the web engine's summary.ts and counts every
    risk regardless of status. That parity is asserted and shipped, and it must not move
    — but it means a closed risk keeps its band, keeps counting as over appetite, and
    keeps its place in the top five. A CISO who treats out three criticals reports the
    same headline as one who treated out none, and `snapshot` freezes that figure into
    the audit trail.

    So every renderer draws its over-appetite count, band mix and top five from here
    instead. `_attention()` and `_owner_load()` already filtered this way; the headline
    numbers printed inches above them did not, which left one page reporting the same
    quantity twice with two different answers.

    `total` is the live count, so an "N of M" sentence has the same population on both
    sides of the "of". `registerTotal` and `closed` keep the whole-register view for the
    one line that reports register size.
    """
    open_risks = live_risks(risks)
    out = sr.summarize(open_risks, size, appetite)
    out["registerTotal"] = len(risks)
    out["closed"] = len(risks) - len(open_risks)
    return out


def _snapshot_summary(snap: dict) -> dict:
    """A snapshot's summary on the same definition the live figures use.

    Recomputed from the snapshot's stored risks rather than read from its frozen
    `summary`, because the frozen one counts closed risks and the live figures do not.
    Plotting the two on one line would make the trend step whenever a risk was closed
    rather than when exposure moved. The frozen summary is the fallback only for a
    snapshot written before risks were stored beside it.
    """
    data = snap.get("data", {})
    st = {"matrixSize": 5, "appetite": "medium", **data.get("settings", {})}
    if data.get("risks"):
        return live_summary(data["risks"], st["matrixSize"], st["appetite"])
    return data.get("summary") or sr.summarize([], st["matrixSize"], st["appetite"])


class Context:
    """Everything the renderers draw, derived from one register + optional sidecar."""

    def __init__(self, args: argparse.Namespace):
        self.args = args
        self.offline = bool(getattr(args, "offline", False))
        self.today = args.today
        # Band width for confirmation age. Reporting furniture only: nothing in this
        # skill expires, suppresses or rescores on age; the boundaries themselves are
        # defined and asserted in scripts/score_register.py::age_band.
        #
        # REQUIRED, with no fallback, following nist-csf's attention_lists(): a default
        # here would be a second place this module holds the threshold, and `or 180`
        # would silently rewrite the age_threshold=0 that parse_args refuses a few lines
        # above into 180 for any caller building the Namespace by hand. A caller that
        # forgets it gets an immediate AttributeError instead of a quiet wrong answer.
        self.age_threshold = int(args.age_threshold)
        self.register_path = args.register
        self.out_path = args.out
        self.reg = sr.load_register(args.register)
        self.scored = sr.score_register(self.reg)
        self.meta = self.reg["meta"]
        self.settings = self.reg["settings"]
        self.size = self.settings["matrixSize"]
        self.appetite = self.settings["appetite"]
        self.summary = self.scored["summary"]
        # The board-facing figures. `summary` stays the parity port; see live_summary().
        self.live = live_summary(self.reg["risks"], self.size, self.appetite)
        self.tr = Translations.load(args.translations)

        # Themes: file order is the display order; Unclassified always trails.
        self.themes = list(self.reg.get("themes", []))
        self._theme_name = {t["id"]: t.get("name") or t["id"] for t in self.themes}

        # Baseline = most recent snapshot. History is append-only, so append order
        # is chronological even when several snapshots share a timestamp.
        snaps = self.reg.get("snapshots", [])
        self.baseline = snaps[-1] if snaps else None
        self._prior = {}
        if self.baseline:
            b_settings = {"matrixSize": self.size, "appetite": self.appetite,
                          **self.baseline.get("data", {}).get("settings", {})}
            b_size = b_settings["matrixSize"]
            for r in self.baseline.get("data", {}).get("risks", []):
                exp = sr.exposure(r["residual"]["likelihood"], r["residual"]["impact"])
                self._prior[r["id"]] = {
                    "exposure": exp, "band": sr.band(exp, b_size),
                    "status": r.get("status"), "response": r.get("response", {}).get("type"),
                    "overAppetite": sr.over_appetite(exp, b_size, b_settings["appetite"]),
                    "title": r.get("title", ""), "acceptance": r.get("acceptance"),
                    # Carried so a risk that left the register is still title-guarded
                    # in the change log; see risk_title().
                    "provisionalTitle": bool(r.get("provisionalTitle")),
                }

        self.risks = [self._enrich(r) for r in self.scored["risks"]]
        self.by_id = {r["id"]: r for r in self.risks}
        self.trend = self._trend()
        self.diff = self._diff()
        self.attention = self._attention()
        self.owner_load = self._owner_load()
        self.theme_rollup = self._theme_rollup()
        self.decisions = self._decisions()
        self.confirmation = self._confirmation_rollup()

    # -- per risk --

    def _history_for(self, rid: str) -> list[dict]:
        return [e for e in self.reg.get("history", []) if e.get("riskId") == rid]

    def _confirmation(self, hist: list[dict]) -> dict:
        """When this risk was last affirmed, by whom, and how old that is.

        Derived from history[] and nothing else — there is no stored age field and there
        must never be one, on the same grounds as every other derived value here.

        Only `sr.AGE_AFFIRMING` events count: someone asserting something about the
        risk's magnitude or its treatment decision. A note, a rewording, a theme move, a
        status flip and a snapshot deliberately do not, because an age that any edit
        resets makes a "stalest" list worthless — the same rule nist-csf states in
        references/schema.md.

        THREE outcomes, deliberately distinguishable by the caller, because conflating
        any two of them makes a renderer assert something false:

        1. No affirming event at all — a v1 register, a fresh import-gaps. All four
           fields are None. `lastConfirmedAt is None` is the test for this, and the
           rollup counts it as `undated`. Never inferred, never backfilled.
        2. An affirming event whose `ts` cannot be read as a date. `lastConfirmedAt` and
           `lastConfirmedBy` are populated — the confirmation and the confirmer are on
           record and it would be a lie to report otherwise — but the age and the band
           are None because no distance can be computed. The rollup counts this
           separately as `unreadableDate`. Folding it into `undated` would let a panel
           captioned "never confirmed" name a risk that has a confirmation and a named
           confirmer, which is the one thing that bucket's own docstring forbids.
        3. A readable date: all four fields populated.

        Ties on `ts` resolve to the later-appended event, since history is append-only.
        This is defensive robustness for a hand-edited or future multi-actor history, not
        a live defect being fixed: `_append_event` takes `actor` from
        `reg["meta"]["assessor"]`, nothing mutates that after `init`, and one `set-score`
        writes both of its `score-changed` events in the same second — so today every
        tied pair shares an actor and a date, and the four fields above come out
        identical whichever member wins. Cheap to be right in advance.

        `ts` is coerced with str() before comparison. A register whose history mixes a
        numeric `ts` with a string one would otherwise raise TypeError out of the sort
        and take the whole render down — the exact class of failure _days_since() exists
        to prevent, one line away from it. Both consumers below already coerce.
        """
        affirming = [e for e in hist
                     if e.get("type") in sr.AGE_AFFIRMING and e.get("ts")]
        if not affirming:
            return {"lastConfirmedAt": None, "lastConfirmedBy": None,
                    "confirmationAgeDays": None, "confirmationBand": None}
        # A READABLE ts always beats an unreadable one, whatever they sort like as strings.
        # Without that first key the comparison is plain lexicographic, and "not-a-date"
        # sorts above every ISO date because 'n' > '2' — so a risk holding a good, later
        # confirmation alongside one corrupt event reported `unreadableDate` and lost both
        # its age and its band. That is the same conflation the three-outcome model exists
        # to prevent (see _confirmation_rollup), arriving through the sort instead of
        # through the buckets. `unreadableDate` is now reached only when NO affirming
        # event is readable, which is what the docstring above claims it means.
        last = max(enumerate(affirming),
                   key=lambda t: (_days_since(t[1]["ts"], self.today) is not None,
                                  str(t[1]["ts"]), t[0]))[1]
        days = _days_since(last["ts"], self.today)
        return {
            "lastConfirmedAt": str(last["ts"])[:10],
            "lastConfirmedBy": (last.get("actor") or "").strip() or None,
            "confirmationAgeDays": days,
            "confirmationBand": (sr.age_band(days, self.age_threshold)
                                 if days is not None else None),
        }

    def _enrich(self, r: dict) -> dict:
        tid = r.get("theme")
        acc = r.get("acceptance") or None
        hist = self._history_for(r["id"])
        prior = self._prior.get(r["id"])
        # Computed once. Re-typing this expression for the day count made two copies of
        # one rule that have to agree forever, which is what text_on() exists to stop.
        review_overdue = (r.get("status") != "closed"
                          and _overdue(r.get("reviewDate"), self.today))
        if prior is None:
            velocity = "new" if self.baseline else "steady"
            delta = None
        else:
            delta = r["residualExposure"] - prior["exposure"]
            velocity = "improving" if delta < 0 else "worsening" if delta > 0 else "steady"
        return {
            **r,
            "themeId": tid,
            "themeName": self._theme_name.get(tid, UNCLASSIFIED) if tid else UNCLASSIFIED,
            "priorExposure": prior["exposure"] if prior else None,
            "priorBand": prior["band"] if prior else None,
            "delta": delta,
            "velocity": velocity,
            "reviewDate": r.get("reviewDate") or "",
            "reviewOverdue": review_overdue,
            # A reviewDate is a deadline a human committed to, so passing it is a fact,
            # not decay — the flag stays boolean. The day count exists only so renderers
            # can rank by how badly it slipped, without changing the semantics.
            "reviewOverdueDays": (_days_since(r.get("reviewDate"), self.today)
                                  if review_overdue else None),
            "unowned": not (r.get("owner") or "").strip(),
            "acceptance": acc,
            "acceptanceDue": bool(acc) and _overdue(acc.get("revalidationDate"), self.today),
            "acceptanceExpired": bool(acc) and _overdue(acc.get("expiryDate"), self.today),
            "acceptanceIncomplete": bool(acc) and not (acc.get("approver")
                                                       and acc.get("justification")),
            **self._confirmation(hist),
            "history": hist,
            "translation": self.tr.risk(r["id"]),
        }

    # -- register wide --

    def _trend(self) -> list[dict]:
        """Over-appetite count and band mix across snapshots, plus the live position."""
        series = []
        for snap in self.reg.get("snapshots", []):
            s = _snapshot_summary(snap)
            series.append({"label": snap.get("label") or snap.get("id", "—"),
                           "ts": (snap.get("ts") or "")[:10], "overAppetite": s["overAppetite"],
                           "byBand": s["byBand"], "total": s["total"], "current": False})
        series.append({"label": "Current", "ts": self.today,
                       "overAppetite": self.live["overAppetite"],
                       "byBand": self.live["byBand"], "total": self.live["total"],
                       "current": True})
        return series

    # Event types whose rationale may caption a change-log entry on a board page.
    CHANGE_EXPLAINING = frozenset({
        "risk-added", "risk-updated", "score-changed", "status-changed", "theme-changed",
        "risk-accepted", "acceptance-revalidated", "response-changed",
        # Documented in references/schema.md but not emitted yet. Classified now so they
        # behave correctly when they arrive, on the same grounds score_register classifies
        # acceptance-revalidated before anything writes it. Each names a material change
        # to one risk, so each explains one.
        "risk-closed", "risk-reopened", "risk-deleted",
    })

    # The other half of the partition. Spelled out rather than left as "everything not
    # listed above", for the reason score_register.py's KNOWN_EVENT_TYPES note gives at
    # length: a subset assertion alone forces a new type to be *registered* and nothing
    # more, leaving it change-explaining or not by omission — and omission is precisely
    # the default the mechanism exists to prevent. Requiring the union to equal
    # sr.KNOWN_EVENT_TYPES makes registration insufficient: a new type has to land on one
    # side, and choosing a side is the decision. That check is in confirmation-age.sh,
    # against score_register's taxonomy rather than a second copy of this list, so a
    # typo'd name here fails the suite instead of silently never matching.
    NOT_CHANGE_EXPLAINING = frozenset({
        # It asserts that nothing changed, so letting it supply the "why" for a score
        # move rendered "residual Low → Critical — 'reviewed at the forum; unchanged'" on
        # a board page. Its rationale is not worthless — it is the audit trail for the
        # confirmation itself, and the confirmation-age view is where it belongs.
        "risk-confirmed",
        # These three carry no riskId, so `_rationales_since_baseline` cannot key on them
        # and including them would be inert. `import-merged` was listed as explaining for
        # exactly one commit, contradicting the note beside it that gave this same reason
        # for excluding snapshot-created.
        "snapshot-created", "register-created", "import-merged",
        # Register-wide, not about any one risk.
        "settings-changed",
    })

    def _rationales_since_baseline(self) -> dict[str, str]:
        """Rationales logged after the last snapshot — the 'why' behind this period's moves.

        Newest-wins per risk, but only among events that actually changed something. See
        CHANGE_EXPLAINING: an event asserting that nothing changed must never caption a
        change.
        """
        hist = self.reg.get("history", [])
        cut = 0
        for i, e in enumerate(hist):
            if e.get("type") == "snapshot-created":
                cut = i + 1
        out = {}
        for e in hist[cut:]:
            if (e.get("riskId") and e.get("rationale")
                    and e.get("type") in self.CHANGE_EXPLAINING):
                out[e["riskId"]] = e["rationale"]
        return out

    def _diff(self) -> dict:
        """What changed since the last snapshot — the continuity spine of the board story.

        Each change carries `provisionalTitle` alongside the raw title so the renderers
        can put it through risk_title(). Without it the change log was a third route for
        framework wording onto a board page, and the one the title guard's own docstring
        did not yet know about: a snapshot taken before an import leaves every imported
        gap in this list, in CSF voice, next to a band chip.
        """
        if not self.baseline:
            return {"baseline": None, "changes": [], "added": [], "removed": []}
        why = self._rationales_since_baseline()
        changes, added = [], []
        for r in self.risks:
            prior = self._prior.get(r["id"])
            if prior is None:
                added.append(r)
                changes.append({"kind": "added", "id": r["id"], "title": r["title"],
                                "provisionalTitle": bool(r.get("provisionalTitle")),
                                "detail": f'new risk · residual {r["residualExposure"]} '
                                          f'{BAND_LABEL[r["residualBand"]]}',
                                "rationale": why.get(r["id"], "")})
                continue
            bits = []
            if r["residualBand"] != prior["band"]:
                bits.append(f'residual {BAND_LABEL[prior["band"]]} → '
                            f'{BAND_LABEL[r["residualBand"]]}')
            elif r["delta"]:
                bits.append(f'residual {prior["exposure"]} → {r["residualExposure"]}')
            if prior["overAppetite"] and not r["overAppetite"]:
                bits.append("now within appetite")
            elif not prior["overAppetite"] and r["overAppetite"]:
                bits.append("now over appetite")
            if r.get("status") != prior["status"]:
                bits.append(f'{prior["status"]} → {r["status"]}')
            if r["response"]["type"] != prior["response"]:
                bits.append(f'response {prior["response"]} → {r["response"]["type"]}')
            if r["acceptance"] and not prior["acceptance"]:
                bits.append(f'accepted by {r["acceptance"].get("approver") or "—"}')
            if not bits:
                continue
            newly_closed = r.get("status") == "closed" and prior["status"] != "closed"
            kind = ("closed" if newly_closed
                    else "improved" if (r["delta"] or 0) < 0
                    else "worsened" if (r["delta"] or 0) > 0
                    else "changed")
            changes.append({"kind": kind, "id": r["id"], "title": r["title"],
                            "provisionalTitle": bool(r.get("provisionalTitle")),
                            "detail": " · ".join(bits), "rationale": why.get(r["id"], "")})
        removed = [p for rid, p in self._prior.items() if rid not in self.by_id]
        for rid, p in self._prior.items():
            if rid not in self.by_id:
                changes.append({"kind": "removed", "id": rid, "title": p["title"],
                                "provisionalTitle": p.get("provisionalTitle", False),
                                "detail": "no longer in the register", "rationale": ""})
        order = {"worsened": 0, "added": 1, "improved": 2, "closed": 3, "changed": 4, "removed": 5}
        changes.sort(key=lambda c: (order.get(c["kind"], 9), c["id"]))
        return {"baseline": self.baseline, "changes": changes, "added": added, "removed": removed}

    @staticmethod
    def _accepted_and_current(r: dict) -> bool:
        """A risk the board has already decided about, and whose decision still stands.

        Deliberately strict: an acceptance that is past re-validation, past expiry, or
        missing its approver or justification is NOT a current decision, and each of those
        already raises its own board item above.
        """
        return bool(r.get("acceptance")) and not (
            r["acceptanceDue"] or r["acceptanceExpired"] or r["acceptanceIncomplete"])

    def _attention(self) -> dict:
        open_risks = live_risks(self.risks)
        over = [r for r in open_risks if r["overAppetite"]]
        return {
            "overAppetite": over,
            # Split so the board is asked about what it has not yet decided, and merely
            # reminded of what it has. Asking again about a risk the audit committee
            # formally accepted last quarter is the credibility failure that structured
            # acceptance exists to prevent.
            "overAppetiteOpen": [r for r in over if not self._accepted_and_current(r)],
            "overAppetiteAccepted": [r for r in over if self._accepted_and_current(r)],
            "reviewOverdue": [r for r in self.risks if r["reviewOverdue"]],
            "acceptanceDue": [r for r in self.risks if r["acceptanceDue"]],
            "acceptanceExpired": [r for r in self.risks if r["acceptanceExpired"]],
            "acceptanceIncomplete": [r for r in self.risks if r["acceptanceIncomplete"]],
            "unowned": [r for r in open_risks if r["unowned"]],
            "outOfRange": [r for r in self.risks if r.get("outOfRange")],
        }

    def _owner_load(self) -> list[dict]:
        by: dict[str, list] = {}
        for r in self.risks:
            if r.get("status") == "closed":
                continue
            by.setdefault((r.get("owner") or "").strip() or "— unowned —", []).append(r)
        out = []
        for owner, rs in by.items():
            worst = max(rs, key=lambda r: sr.BAND_ORDER.index(r["residualBand"]))["residualBand"]
            out.append({"owner": owner, "count": len(rs), "worst": worst,
                        "over": sum(1 for r in rs if r["overAppetite"]),
                        "exposure": sum(r["residualExposure"] for r in rs)})
        out.sort(key=lambda o: (-sr.BAND_ORDER.index(o["worst"]), -o["exposure"]))
        return out

    def _theme_rollup(self) -> list[dict]:
        by: dict[str, list] = {}
        for r in self.risks:
            by.setdefault(r["themeName"], []).append(r)
        ordered = [t.get("name") or t["id"] for t in self.themes]
        if UNCLASSIFIED in by:
            ordered.append(UNCLASSIFIED)
        out = []
        for name in ordered:
            rs = by.get(name)
            if not rs:
                continue
            worst = max(rs, key=lambda r: sr.BAND_ORDER.index(r["residualBand"]))["residualBand"]
            cur = sum(r["residualExposure"] for r in rs)
            # Theme direction: sum of residual exposure vs the same risks at the baseline.
            # Risks with no baseline contribute equally to both sides, so adding a risk
            # doesn't by itself read as a worsening theme.
            prior = sum((r["priorExposure"] if r["priorExposure"] is not None
                         else r["residualExposure"]) for r in rs)
            direction = ("improving" if cur < prior else "worsening" if cur > prior else "steady")
            tid = next((t["id"] for t in self.themes if (t.get("name") or t["id"]) == name), None)
            out.append({"id": tid, "name": name, "count": len(rs), "worst": worst,
                        "over": sum(1 for r in rs if r["overAppetite"]),
                        "exposure": cur, "priorExposure": prior, "direction": direction,
                        "risks": sorted(rs, key=lambda r: -r["residualExposure"]),
                        "narrative": self.tr.theme(tid) if tid else None})
        return out

    def _decisions(self) -> list[str]:
        """Structural decisions derived from the data, then anything the sidecar adds."""
        out = []
        due = self.attention["acceptanceDue"]
        if due:
            out.append(f'Re-validate {len(due)} risk acceptance{"s" if len(due) > 1 else ""} '
                       f'past the re-validation date ({", ".join(r["id"] for r in due)}).')
        exp = self.attention["acceptanceExpired"]
        if exp:
            out.append(f'{len(exp)} acceptance{"s have" if len(exp) > 1 else " has"} passed the '
                       f'expiry date and no longer carries approval '
                       f'({", ".join(r["id"] for r in exp)}).')
        over = self.attention["overAppetiteOpen"]
        if over:
            out.append(f'Board awareness: {len(over)} risk{"s remain" if len(over) > 1 else " remains"} '
                       f'above the {BAND_LABEL[self.appetite].lower()} appetite with no recorded '
                       f'acceptance ({", ".join(r["id"] for r in over)}).')
        acc = self.attention["overAppetiteAccepted"]
        if acc:
            # Not a decision — a reminder that one was already made. Phrased so nobody
            # reads it as a fresh ask.
            out.append(f'No action: {len(acc)} risk{"s sit" if len(acc) > 1 else " sits"} above '
                       f'appetite under a current, approved acceptance '
                       f'({", ".join(r["id"] for r in acc)}).')
        inc = self.attention["acceptanceIncomplete"]
        if inc:
            out.append(f'{len(inc)} acceptance{"s are" if len(inc) > 1 else " is"} missing an '
                       f'approver or justification ({", ".join(r["id"] for r in inc)}).')
        stale = self.attention["reviewOverdue"]
        if stale:
            out.append(f'{len(stale)} risk{"s are" if len(stale) > 1 else " is"} past the '
                       f'scheduled review date ({", ".join(r["id"] for r in stale)}).')
        out.extend(self.tr.decisions)
        return out

    def _confirmation_rollup(self) -> dict:
        """Confirmation-age distribution over the live register.

        Live only, for the same reason live_summary() exists: a closed risk keeps its
        last confirmation date forever, and letting it sit in the distribution means the
        freshness picture never improves as risks are treated out. `confirm` deliberately
        allows confirming a closed risk — "we re-checked this and it stays closed" is a
        real claim — so excluding closed risks here is the corollary obligation, not an
        optimisation.

        Neither `undated` nor `unreadableDate` is a band. A band is a distance from a
        cadence; these two are the absence of a distance, for two different reasons, and
        all three counts are kept apart:

          undated         no affirming event exists. "Nobody has ever re-affirmed this."
          unreadableDate  an affirming event exists and names a confirmer, but its ts
                          cannot be read as a date. "Confirmed, but the record is broken."

        Folding either into `within` would report a guess as a measurement; folding either
        into `wellBeyond` would invent an age nobody recorded; and folding the two into
        each other would let a panel captioned "never confirmed" name a risk with a
        confirmation and a named confirmer on record. See _confirmation() for the three
        states this reads.

        bands + undated + unreadableDate == live, exactly, and that is asserted.

        `futureDated` is the one count here that is NOT part of that partition, and it says
        so in its own name rather than by omission. A confirmation dated after `today` has
        a negative age, and `age_band()` reports a negative age as `within` on purpose — so
        those risks are already counted inside `bands`, and adding them again would make
        the partition read one too many. They are surfaced as a subset so a renderer can
        say "this many of the fresh ones are a broken record, not a recent review" instead
        of quietly presenting a file defect as the best band on the page.

        NOT a defect count, and nothing here may caption it as one. Three separate routes
        reach this state and only one of them is a broken file:

          1. An explicit `--today` behind the register's newest confirmation. This is a
             DOCUMENTED workflow — references/dashboards.md tells the reader to pass
             --today for a reproducible "as of" view — so `--today 2026-06-30` over a
             register confirmed in July puts every sound record in this bucket. It is the
             common case, not the exotic one.
          2. A hand-edited or imported register carrying a genuinely wrong ts. This is the
             one that is a file defect, and it is the population `unreadableDate` already
             serves: a record that is wrong rather than missing.
          3. Clock skew between whatever wrote the register and whoever renders it.

        _today_utc() closed the fourth route, which was this skill's own CLI defaulting
        --today to the local date against UTC timestamps. It did not close route 1, and an
        earlier version of this comment claimed it had.

        What the three share, and all a renderer may say, is that no age can be measured
        from a confirmation dated after the reference date. Which of the three caused it is
        not something this rollup can know.

        DERIVED ONCE, HERE. render_dashboard.confirmation_panel() used to re-derive this same
        list inline with its own comprehension over live_risks(), so one rule lived in two
        places and the count on its row could disagree with the list beside it; it now reads
        `futureDated` and `futureDatedRisks`. Both renderers therefore get the same
        most-impossible-first ordering, and both are subject to the "no diagnosis" rule above
        — the operational note may be blunter than the board's, because its reader is the one
        who can go and look at the file, but it may not name a cause either.
        """
        open_risks = live_risks(self.risks)
        bands = {b: 0 for b in sr.AGE_BANDS}
        undated = 0
        unreadable = 0
        for r in open_risks:
            if r["confirmationBand"] is not None:
                bands[r["confirmationBand"]] += 1
            elif r["lastConfirmedAt"] is None:
                undated += 1
            else:
                unreadable += 1
        # Most-impossible first, so a renderer naming a few names the worst few. Same
        # ordering contract as `wellBeyond` below.
        future = sorted((r for r in open_risks
                         if (r["confirmationAgeDays"] or 0) < 0),
                        key=lambda r: r["confirmationAgeDays"])
        return {
            "bands": bands,
            "undated": undated,
            "unreadableDate": unreadable,
            # A subset of `bands`, never a summand of it — see the docstring.
            "futureDated": len(future),
            "futureDatedRisks": future,
            "live": len(open_risks),
            "thresholdDays": self.age_threshold,
            # Oldest first, so a renderer can name the worst few without re-sorting.
            "wellBeyond": sorted(
                (r for r in open_risks if r["confirmationBand"] == "wellBeyond"),
                key=lambda r: -(r["confirmationAgeDays"] or 0)),
        }

    # -- helpers renderers share --

    def top_risks(self, n: int = 5) -> list[dict]:
        """The worst live risks. Closed ones are excluded on the same grounds as
        live_summary(): a risk the board watched get treated out does not belong in
        'what these mean for the business', least of all flagged over appetite on the
        same page whose change log reports it closed."""
        return sorted(live_risks(self.risks), key=lambda r: -r["residualExposure"])[:n]

    def heat_counts(self, view: str = "residual") -> tuple[list[list[int]], int]:
        """Counts per (impact, likelihood) cell. Risks flagged outOfRange are skipped
        (per dashboards.md) and returned as a count so the view can say so."""
        counts = [[0] * self.size for _ in range(self.size)]
        skipped = 0
        for r in self.risks:
            if r.get("outOfRange"):
                skipped += 1
                continue
            counts[r[view]["impact"] - 1][r[view]["likelihood"] - 1] += 1
        return counts, skipped

    # The zone, stamped, and not negotiable now that --today is a UTC calendar date. On the
    # evening of 2026-07-29 PDT this line read "As of 2026-07-30" — tomorrow's date, on a
    # board artifact, to a reader in California who had asked for no such thing. The date is
    # right and the reader's reading of it was wrong, which is a labelling problem and is
    # fixed by labelling. Stamped unconditionally, including when --today was passed
    # explicitly, because the zone says how the date is INTERPRETED — every comparison behind
    # this page reads it as a UTC calendar date whoever supplied it.
    #
    # Read directly by render_report.py's cover(), which builds its own "As of {ctx.today}"
    # rather than calling as_of_line() — that helper's trailing snapshot clause is already
    # printed on that cover as its own badge, so the report takes the zone string and not the
    # whole line. That is the reason ZONE is a class attribute and not a local: three surfaces
    # print the reference date and there is one spelling of the zone between them.
    ZONE = "UTC"

    def as_of_line(self) -> str:
        if self.baseline:
            return (f'As of {self.today} {self.ZONE} · compared against '
                    f'{self.baseline.get("label", "the last snapshot")}')
        return f"As of {self.today} {self.ZONE} · no snapshot yet, so no trend is available"

    def footer(self, extra: str = "") -> str:
        # Zone-stamped for the same reason as as_of_line(): this is the second place a bare
        # UTC date reached a board artifact and read as tomorrow to a reader west of
        # Greenwich. "generated" is also slightly wrong — it is the reference date, which
        # --today can move — but that wording predates this change and is left alone.
        bits = [DISCLAIMER,
                f"generated {self.today} {self.ZONE} from {Path(self.register_path).name}"]
        if extra:
            bits.append(extra)
        if self.tr.absent:
            bits.append("board narrative not supplied")
        return " · ".join(bits)


def freshness_line(ctx: Context) -> str:
    """One sentence on how current a board-facing picture is. IDs only, never titles.

    Operational views get the distribution; board views get one sentence. A board does not
    need a histogram — render_dashboard's confirmation_panel() is the work queue, and its
    reader is deciding what to look at next. The reader here is deciding whether to act on
    the page in front of them, so what they need is whether the page is current.

    Filed in the executive summary rather than under "Decisions for the board": it is a
    caveat on the whole document, not an ask. The missed-review line in _decisions() is the
    right home for "somebody missed a commitment" and is unchanged by this.

    HERE, not in render_board.py, because there are TWO board-facing renderers and BOTH call
    it: render_board.summary_block() and render_report.exec_summary(), on both branches of
    each, which is four call sites over two artifacts. board-safety.sh's header exists because
    the title guard was written into the executive dashboard first and the printable report
    kept exposing raw framework wording for a full release afterwards; a module-private helper
    is what makes that mistake easy to repeat. Any third board-facing surface calls this and
    does not copy it.

    Every clause is an EXCLUSIVE band, and together with the three non-band states they
    partition the live register — so the numbers here sum to the "Of N live risks" the
    sentence opens with, and a director can add them up. An earlier draft of this reported
    only the best and worst bands, which leaves a silent remainder: a board figure that does
    not add up. Zero-count clauses are dropped rather than printed as "0", so the sentence
    stays short when the picture is simple, and the sum still holds because a dropped clause
    contributes nothing.

    Boundaries come from age_bounds() and are never re-derived here. Cumulative ranges over
    mutually-exclusive counts are false in the flattering direction, and the board renderer
    is where that shipped: "within 360 days" once captioned the count of determinations PAST
    the chosen cadence.

    Clauses run freshest to oldest, deliberately matching confirmation_panel()'s row order
    rather than leading with the worst. A director and the CISO read these two artifacts over
    one register, often side by side, and two orderings of one distribution is a difference
    a reader has to reconcile before they can trust either. The wellBeyond clause names its
    IDs, which is what makes it findable without being first.

    THREE things that are not bands, kept apart, because conflating any two of them makes
    this sentence assert something false about a specific register:

      undated         no affirming event exists at all — "nobody has ever re-affirmed this".
      unreadableDate  a confirmation IS on record and the date will not parse. It must
                      never be captioned as an absent confirmation; only the distance is
                      unknown.
      futureDated     a confirmation dated after the reference date. age_band() reports a
                      negative age as `within`, so these arrive inside the freshest band;
                      leaving them there would count a record nobody can measure as the best
                      news on the page, so they are subtracted out and named.

    That last clause states the FACT and not a diagnosis, and the distinction is not
    pedantry. `--today` is a user-supplied reference date that references/dashboards.md tells
    people to pass explicitly for a reproducible "as of" view, so `--today 2026-06-30` over a
    register confirmed in July puts every sound record in this clause. Calling those a
    "record defect" would libel nine good records on a board page over a documented
    workflow. "Dated after the reference date" is true whichever cause applies, and which
    cause it is — a skewed file, or an as-of date behind the register — is not something this
    function can know.

    Titles are withheld on purpose. An imported gap still carries raw CSF framework wording
    until somebody rewords it, and this line would otherwise be a fourth route for that
    wording onto a board page — the third one shipped for a full release before anybody
    noticed it. id_list() gives IDs, capped; IDs carry no such payload. Naming them is the
    point: _decisions() names IDs for every board item it raises, and a director who cannot
    name the record cannot ask about it.

    Says nothing about confidence. It reports how long ago each risk was affirmed and
    leaves the reader to decide what that means, because a supplier concentration and a
    patching backlog go stale at completely different rates. Nothing here expires,
    suppresses or rescores anything, and no wording in it may imply otherwise.
    """
    c = ctx.confirmation
    if not c["live"]:
        return ""
    bounds = age_bounds(c["thresholdDays"])
    # Future-dated records are already counted inside the band their negative age fell in
    # (`within`, per age_band), so they are moved OUT of the band counts before any clause
    # is written — otherwise they are reported twice and the sum overshoots its own
    # denominator. Decremented from the band each one actually landed in rather than from
    # `within` by name, so the partition holds by construction.
    future = c["futureDatedRisks"]
    bands = dict(c["bands"])
    for r in future:
        if r["confirmationBand"] in bands:
            bands[r["confirmationBand"]] -= 1
    # DEFENSIVE, and unreachable through age_band() as written: a negative age always lands
    # in `within` for any threshold parse_args accepts, so `old` cannot differ from the
    # decremented wellBeyond count above. It is here so the ID LIST and the count can never
    # disagree if that ever stops being true — the count comes from the loop above and this
    # list does not, and a clause that says "2" beside three names is worse than either.
    # Labelled rather than left looking load-bearing.
    future_ids = {r["id"] for r in future}
    old = [r for r in c["wellBeyond"] if r["id"] not in future_ids]

    clauses = [
        (bands["within"],
         f'{bands["within"]} confirmed within the last {bounds["within"][1]} days'),
        (bands["approaching"],
         f'{bands["approaching"]} last confirmed between {bounds["approaching"][0]} and '
         f'{bounds["approaching"][1]} days ago'),
        (bands["beyond"],
         f'{bands["beyond"]} last confirmed between {bounds["beyond"][0]} and '
         f'{bounds["beyond"][1]} days ago'),
        # Named, oldest first, from the list the rollup built for exactly this. A count a
        # board cannot ask a question about is not worth the words.
        (len(old),
         f'{len(old)} not confirmed in over {bounds["beyond"][1]} days '
         f'({id_list(old, cap=5)})'),
        # The fact, not the cause. See the docstring: an explicit --today behind the
        # register puts sound records here, and this clause must be true of those too.
        #
        # `today` is escaped even though parse_args() rejects anything date.fromisoformat()
        # will not accept, because parse_args is not the only door: Context takes a Namespace
        # and the evals build one directly, so a caller that skips the CLI puts an unchecked
        # string into board-facing HTML. render_dashboard's equivalent row note escapes it for
        # the same reason, and one of the two doing it would be the more confusing state.
        (len(future),
         f'{len(future)} dated after the {esc(ctx.today)} reference date, so no age can be '
         f'measured for them ({id_list(future, cap=5)})'),
        (c["undated"], f'{c["undated"]} carrying no confirmation record'),
        # "Confirmed", explicitly. The confirmation and its confirmer are on record and it
        # would be a lie to file this under an absent one.
        (c["unreadableDate"],
         f'{c["unreadableDate"]} confirmed on a date the register cannot read'),
    ]
    bits = [text for count, text in clauses if count]
    plural = "s" if c["live"] != 1 else ""
    # The closing clause says what the sentence is NOT, because a distribution of ages
    # printed on a board page invites the reading that old determinations have been marked
    # down. Nothing in this skill expires, suppresses or rescores on age.
    #
    # It says so without the word "expire", which is a preference and not a constraint: the
    # confidence-vocabulary guard on board views does not list that word, and "past expiry"
    # already reaches this page from _decisions(). The phrasing below states the
    # non-suppression half directly, which is the part a director would otherwise infer
    # wrongly, so there was no reason to spend the word.
    return (f'<div class="note freshness">Of {c["live"]} live risk{plural}: '
            + "; ".join(bits) + '. Age is reported so the board can weigh it, and nothing '
            'on this page is rescored or re-ranked because of it.</div>')


def build(argv: list[str], description: str, default_out: str) -> Context:
    return Context(parse_args(argv, description, default_out))


def write(ctx: Context, doc: str) -> None:
    out = Path(ctx.out_path)
    if out.parent != Path(""):
        out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(doc, encoding="utf-8")
    print(f"wrote {out} ({len(doc):,} bytes) — {ctx.live['registerTotal']} risks, "
          f"{ctx.live['overAppetite']} over appetite")
