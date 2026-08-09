#!/usr/bin/env python3
"""Shared rendering pieces for the exceptions-register reports.

Each skill carries its own `_common.py` rather than importing a shared one: every shipped
script must run standalone, so a cross-skill import needs sys.path surgery and breaks the
moment a single skill directory is used on its own. Documented the same way in the siblings.

Two reports: an operational inventory for the team, and a board view whose language comes
from `ciso-board-translation` through a sidecar. Both carry the discoverability caveat —
see `references/exceptions.md` for why it is load-bearing rather than boilerplate.
"""
from __future__ import annotations

import argparse
import html
import json
import re
from datetime import date

# Vendored alongside this file, for the same reason this file is vendored: a shipped
# script must run from its own skill directory with no path surgery.
# tools/check-versions.py fails if this copy drifts from tools/cac_graphics.py.
import cac_graphics as G

INK = "#14171C"
LIME = "#EAE7DF"
PATINA = "#2FA98C"
SLATE = "#666D7C"
WB = "#F6F4EE"
WB_SURF = "#FFFFFF"
WB_LINE = "#D8D3C6"
MUTED = "#4A4F58"

# Lifecycle bands are a STATUS palette: named states, not points on a scale. Light fill,
# dark ink, so each chip clears AA against its own background by a wide margin. The band
# word is always inside the chip — colour never carries the meaning alone.
#
# The banded pairs come from the library so a chip and the mark beside it cannot draw one
# meaning in two colours. `expired` and `closed` keep their own: neither is a RAG band —
# expired is a lifecycle terminus rather than a severity, and holding it apart from
# `revalidation-overdue` is the point of showing both.
BAND_FILL = {
    "current":              G.chip("good"),
    "revalidation-due":     G.chip("high"),
    "revalidation-overdue": G.chip("critical"),
    "expired":              ("#EDE0EA", "#5E3660"),
    "closed":               ("#EFEDE7", MUTED),
}


def _rebuild_derived() -> None:
    """Recompute the maps that read a palette primitive.

    Called at import and again by apply_brand(). Built from MUTED, so binding it once
    at import froze a client's muted tone back to the CAC one — invisible to any test
    whose sample brand happens not to override `muted`, which is how it survived until
    check_import_time_palette went in.
    """
    global BAND_FILL
    BAND_FILL = {
        "current":              G.chip("good"),
        "revalidation-due":     G.chip("high"),
        "revalidation-overdue": G.chip("critical"),
        "expired":              ("#EDE0EA", "#5E3660"),
        "closed":               ("#EFEDE7", MUTED),
    }


_rebuild_derived()
BAND_LABEL = {
    "current": "current",
    "revalidation-due": "re-validation due",
    "revalidation-overdue": "re-validation overdue",
    "expired": "expired",
    "closed": "closed",
}
KIND_LABEL = {"acceptance": "accepted risk", "exception": "control exception"}

# --- Engine band -> the graphics library's RAG band ----------------------------
# One mapping, used by every mark and every chip on the page, so the chip, the graphic
# and the count cannot disagree about the same record.
#
# RAG is legitimate here because these bands are declared, not invented. A record carries
# a re-validation date and a due window the register itself recorded; `overdue` and
# `expired` mean a stated clock has lapsed, and `current` means it has not. That is the
# same shape as the metrics sibling's threshold statuses, and the mapping mirrors it:
# the engine bands on two levels, so `revalidation-due` maps to `high` rather than
# `medium` — a yellow chip beside an amber bar for one record would be two answers to
# one question.
#
# `expired` and `revalidation-overdue` both map to `critical`: both are a lapsed clock,
# and neither is worse than the other in a way this palette could carry. The band word
# is always rendered beside the colour, so the two stay distinguishable — see sev_for.
#
# `closed` maps to None. So does a record with no dated clock at all: with nothing
# declared there is no threshold, and painting it would invent the band the register
# declined to record.
BAND_SEV = {
    "current": "good",
    "revalidation-due": "high",
    "revalidation-overdue": "critical",
    "expired": "critical",
    "closed": None,
}


def sev_for(row: dict):
    """The RAG band for a record, or None when nothing was declared to band it against.

    Never computed from dates here. `band` is the engine's, carried straight through:
    a renderer that decided for itself whether a clock had lapsed could disagree with
    the inventory an auditor was handed, and the register is the system of record.
    """
    if not (row.get("revalidationDate") or row.get("expiryDate")):
        return None
    return BAND_SEV.get(row.get("band"))


_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def iso_or_none(value):
    """A date the graphics library will accept, or None. Never a guess at what was meant.

    `G.gantt` and `G.milestone_timeline` raise ValueError on a malformed date — deliberately,
    because the alternative was a silent zero-width bar. A register can still hold a date
    this renderer cannot draw (an import, a hand-edited store), and one bad field must not
    take the whole report down. So dates are screened here, the record keeps its row, and
    what could not be drawn is named on the page rather than dropped.
    """
    text = "" if value is None else str(value)
    if not _ISO.match(text):
        return None
    try:
        date.fromisoformat(text)
    except ValueError:
        return None
    return text


def window_elapsed(row: dict):
    """How much of the granted window has already gone, 0..1, or None.

    A duration, never a judgement: this is what the gantt's blue fill encodes, and it has
    no threshold, so it is never RAG. The arithmetic is over two dates the register
    recorded and the engine's own `daysToExpiry`; it decides nothing about the band.

    Clamped at 1.0, because a record past its expiry has used all of its window and a bar
    longer than its track would be a drawing error rather than a fact.
    """
    start = iso_or_none(row.get("acceptedDate"))
    end = iso_or_none(row.get("expiryDate"))
    remaining = row.get("daysToExpiry")
    if not (start and end) or remaining is None:
        return None
    total = (date.fromisoformat(end) - date.fromisoformat(start)).days
    if total <= 0:
        return None
    return max(0.0, min(1.0, (total - remaining) / total))


# The attribution line comes from the graphics library, at render time.
#
# It was a module constant here, one copy per skill, five copies in all — and every one of
# them spelled the maker's name out by hand. `G.footer()` drops that name when a client
# white-labels and keeps the disclaimer, so a hardcoded copy is a white-label leak waiting
# for the day this renderer gains a brand flag. Called rather than bound at import for the
# same reason: the brand is process-global and can be rebound after this module loads, and a
# constant captured at import would keep printing the old name on a re-branded page.
PLACEHOLDER = ("Board narrative not supplied. Run the ciso-board-translation skill over this "
               "register and pass its output with --translations to replace this block.")

# Surfaced on every view that shows these records, not tucked into a footer. The point is not
# to discourage keeping the record — the Caremark line rewards a documented process (In re
# Caremark Int'l Inc. Derivative Litig., 698 A.2d 959 (Del. Ch. 1996), restated in Stone v.
# Ritter, 911 A.2d 362 (Del. 2006); see references/exceptions.md) — but to make sure it is
# written as something that can be read by a regulator, a board, and opposing counsel without
# contradicting what the organisation said publicly.
CAVEAT = ("These records are discoverable. A permanent, dated inventory of accepted risk is a "
          "governance asset and a potential litigation exhibit, and which one it becomes depends "
          "on whether it agrees with what the organisation has said publicly. Keep entries "
          "governance-level and factual, align them with what is disclosed, and involve counsel "
          "on anything touching disclosure.")


# --- Client brand override ----------------------------------------------------
#
# The chart marks followed a client brand long before the page around them did: the graphics
# library floors what it can see, and this shell — a dark band, light text on it, a lifted
# sub-header — lived here as literals. A brand that reached the charts and left the page in
# CAC colours is a worse result than no override at all, because only one half of it looks
# deliberate.
#
# `G.chrome()` now owns the shell and floors the pairings the library cannot see. This binds
# what that returns onto the names the CSS below already interpolates.
_BRAND_BINDINGS = {
    "INK": "ink", "INK_RAISED": "inkRaised", "INK_LINE": "inkLine",
    "LIME": "lime", "LIME_DIM": "limeDim",
    "PATINA": "patina", "PATINA_H": "patinaHover", "PATINA_TEXT": "patinaText",
    "SLATE": "slate", "WB": "bg", "WB_SURF": "surface", "WB_LINE": "line",
    "MUTED": "muted",
}
# Snapshotted at import, and restored verbatim when no brand is supplied. Not recomputed from
# `G.chrome()`, deliberately: a couple of these values were tuned in this file and differ
# slightly from the library's, and rebuilding the default from the library would change what
# an unbranded page renders. Restoring the literal shipped values makes "no --brand renders
# exactly what it always did" true by construction rather than by inspection.
_BRAND_DEFAULTS = {n: globals()[n] for n in _BRAND_BINDINGS if n in globals()}


def apply_brand(path: str = "") -> None:
    """Rebind this module's shell from a client brand file, or restore the CAC one.

    Raises `SystemExit` with the reason on a bad file or a refused palette. A renderer that
    fell back to CAC colours after a failed override would hand a client a document that
    looks finished and is not the one they asked for.
    """
    if not path:
        globals().update(_BRAND_DEFAULTS)
        G.set_brand()
        _rebuild_derived()
        return
    try:
        with open(path, encoding="utf-8") as fh:
            raw = json.load(fh)
    except OSError as exc:
        raise SystemExit("--brand %s: %s" % (path, exc))
    except ValueError as exc:
        raise SystemExit("--brand %s is not valid JSON: %s" % (path, exc))
    if not isinstance(raw, dict):
        raise SystemExit("--brand %s must contain a JSON object, got %s"
                         % (path, type(raw).__name__))
    try:
        shell = G.apply_chrome(raw)
    except G.BrandError as exc:
        raise SystemExit("--brand %s was refused:\n%s" % (path, exc))
    g = globals()
    for name, key in _BRAND_BINDINGS.items():
        if name in g:
            g[name] = shell[key]
    _rebuild_derived()

def esc(s) -> str:
    """HTML-escape a scalar for a text slot, and REFUSE a container.

    `str()` on a dict produces a Python repr; `html.escape` then turns its quotes into
    `&#x27;`, and a board reads `{'text': ...}` off the page. That is a shipped P1, and the
    escaping is also why it survived: the guard greps for the RAW repr, which escaping has
    already destroyed, so five suites reported clean over a live defect (BL-209 / BL-199).

    Scalars are unaffected and deliberately so. A runtime census over every eval suite in the
    repo found 21,213 strings, 595 ints and four dicts — the ints are legitimate (`esc(42)` is
    "42") and all four dicts were the defect. So the rule is not "strings only", which would
    break 595 real call sites; it is that a container never belongs in a text slot.

    It raises rather than rendering, at the call site holding the object rather than three
    layers later in a page nobody diffed."""
    if isinstance(s, (dict, list, tuple, set)):
        raise TypeError(
            "esc() was passed a %s. It would render on the page as a Python repr: %.140r\n"
            "  Pass the field a reader should see. For a decision object that is d['text'].\n"
            "  Escaping does not save you here, it hides the problem: html.escape rewrites\n"
            "  the repr's quotes as &#x27;, so the output slips a grep for {'text'."
            % (type(s).__name__, s))
    return html.escape("" if s is None else str(s))


def band_chip(band: str) -> str:
    bg, fg = BAND_FILL.get(band, BAND_FILL["closed"])
    return (f'<span class="chip" style="background:{bg};color:{fg}">'
            f'{esc(BAND_LABEL.get(band, band))}</span>')


def band_chip_mark(row: dict) -> str:
    """The lifecycle state as the shared library's status chip: dot, tint, and the word.

    Falls back to the HTML chip when the record has no declared clock — `G.rag_chip`
    returns an empty string for a band-less state, and a record that rendered no state at
    all would be a record the reader could not see. A lapsed clock surfaces an item; so
    does a missing one.
    """
    sev = sev_for(row)
    band = row.get("band", "")
    svg = G.rag_chip(sev, BAND_LABEL.get(band, band)) if sev else ""
    if not svg:
        return band_chip(band)
    return f'<span class="chipmark">{svg}</span>'


def days_phrase(days, noun: str) -> str:
    """A signed day distance, in words. Never a judgement about whether it is still true."""
    if days is None:
        return "—"
    if days < 0:
        return f"{abs(days)} days past {noun}"
    if days == 0:
        return f"{noun} today"
    return f"{days} days to {noun}"


class Translations:
    """The ciso-board-translation sidecar, per board-pack/references/section-contract.md.

    This section is the one with two item maps: `acceptances` and `exceptions`, because an
    accepted risk and a control exception are different objects sharing one lifecycle.
    """

    SECTION = "exceptions"
    CONTRACT_VERSION = 1

    def __init__(self, raw: dict | None):
        self.absent = raw is None
        raw = raw or {}
        self.executive_summary = raw.get("executiveSummary") or None
        self.acceptances = raw.get("acceptances") or {}
        self.exceptions = raw.get("exceptions") or {}
        self.decisions = raw.get("decisions") or []
        self.as_of = raw.get("asOf") or None
        self.contract_version = raw.get("contractVersion", self.CONTRACT_VERSION)
        self.section = raw.get("section") or None

    def line(self, rid: str):
        return self.acceptances.get(rid) or self.exceptions.get(rid) or None

    @staticmethod
    def load(path: str | None) -> "Translations":
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
        if not (tr.acceptances or tr.exceptions or tr.executive_summary or tr.decisions):
            hint = ""
            if raw and all(isinstance(v, str) for v in raw.values()):
                hint = ('\n  It looks like a flat {"A-001": "sentence"} map. '
                        'Wrap it: {"acceptances": { ... }, "exceptions": { ... }}.')
            raise SystemExit(f"error: --translations file {path} contains no usable keys "
                             f'(expected "acceptances", "exceptions", "executiveSummary" '
                             f'or "decisions").{hint}')
        if tr.contract_version != Translations.CONTRACT_VERSION:
            raise SystemExit(
                f"error: --translations file {path} declares contractVersion "
                f"{tr.contract_version!r}; this renderer implements version "
                f"{Translations.CONTRACT_VERSION}. See "
                f"skills/board-pack/references/section-contract.md.")
        if tr.section is not None and tr.section != Translations.SECTION:
            raise SystemExit(
                f"error: --translations file {path} is a {tr.section!r} section; "
                f"this renderer produces the {Translations.SECTION!r} section. "
                f"Pass the sidecar written for this skill.")
        return tr


class Context:
    """The analyze JSON plus an optional sidecar. A pass-through, not a derivation layer."""

    def __init__(self, args: argparse.Namespace):
        self.args = args
        # Applied before anything renders. Every CSS block below is an f-string evaluated at
        # call time, so rebinding the module palette here reaches all of them — but only if
        # it happens before the first one is built.
        apply_brand(getattr(args, "brand", "") or "")
        self.offline = bool(getattr(args, "offline", False))
        self.out_path = args.out
        try:
            with open(args.infile, encoding="utf-8") as fh:
                self.a = json.load(fh)
        except FileNotFoundError:
            raise SystemExit(f"error: --in file not found: {args.infile}")
        except json.JSONDecodeError as exc:
            raise SystemExit(f"error: --in file {args.infile} is not valid JSON: {exc.msg}")
        for key in ("records", "attention", "counts"):
            if key not in self.a:
                raise SystemExit(
                    f"error: {args.infile} is not an exceptions-register analysis "
                    f"(no {key!r} key). Produce it with "
                    f"`exceptions_register.py analyze <store.exc> --out {args.infile}`.")
        self.records = self.a["records"]
        self.attention = self.a["attention"]
        self.counts = self.a["counts"]
        self.meta = self.a.get("meta") or {}
        self.today = self.a.get("today") or ""
        self.window = self.a.get("dueWindowDays")
        self.tr = Translations.load(getattr(args, "translations", None))

    def active(self):
        return [r for r in self.records if r["band"] != "closed"]

    def footer(self) -> str:
        bits = [G.footer("Not legal advice"), f"generated {esc(self.today)}"]
        if self.meta.get("clientName"):
            bits.insert(0, esc(self.meta["clientName"]))
        return "<footer>" + " · ".join(bits) + "</footer>"

    def caveat_block(self) -> str:
        return f'<div class="caveat"><strong>Discoverability</strong><p>{esc(CAVEAT)}</p></div>'


FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com">'
         '<link href="https://fonts.googleapis.com/css2?family=Manrope:wght@400;600;700'
         '&family=Space+Grotesk:wght@500;600&display=swap" rel="stylesheet">')


def base_css() -> str:
    return f"""
*{{box-sizing:border-box}}
body{{margin:0;padding:24px;background:{WB};color:{INK};
  font-family:Manrope,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
  font-size:15px;line-height:1.55}}
.wrap{{max-width:1100px;margin:0 auto}}
h1,h2,h3{{font-family:'Space Grotesk',Manrope,sans-serif;margin:0 0 8px;line-height:1.25}}
h1{{font-size:26px}} h2{{font-size:19px;margin-top:28px}} h3{{font-size:16px}}
.sub{{color:{MUTED};margin:0 0 20px}}
.card{{background:{WB_SURF};border:1px solid {WB_LINE};border-radius:10px;
  padding:16px 18px;margin:14px 0}}
.tiles{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px}}
.tile{{background:{WB_SURF};border:1px solid {WB_LINE};border-radius:10px;padding:14px}}
.tile .n{{font-family:'Space Grotesk',sans-serif;font-size:28px;font-weight:600;
  display:block;line-height:1.1}}
.tile .l{{color:{MUTED};font-size:13px}}
.scroll{{overflow-x:auto;-webkit-overflow-scrolling:touch}}
table{{border-collapse:collapse;width:100%;min-width:700px}}
th,td{{text-align:left;padding:9px 10px;border-bottom:1px solid {WB_LINE};vertical-align:top}}
th{{color:{MUTED};font-size:13px;font-weight:600;white-space:nowrap}}
.chip{{display:inline-block;padding:2px 9px;border-radius:999px;font-size:12.5px;
  font-weight:600;white-space:nowrap}}
.muted{{color:{MUTED}}}
.list{{margin:6px 0 0;padding-left:20px}}
.list li{{margin:3px 0}}
.ph{{background:{LIME};border:1px dashed {SLATE};border-radius:8px;padding:12px 14px;
  color:{MUTED}}}
.caveat{{background:{LIME};border:1px solid {WB_LINE};border-left:4px solid {SLATE};
  border-radius:8px;padding:12px 16px;margin:18px 0;color:{MUTED};font-size:14px}}
.caveat strong{{color:{INK};display:block;margin-bottom:4px}}
.caveat p{{margin:0}}
footer{{color:{MUTED};font-size:12.5px;margin-top:28px;padding-top:14px;
  border-top:1px solid {WB_LINE}}}
/* CAC chrome. A compact band, not a cover: these are working views, and a
   full-page cover on a section a reader opens twenty times is furniture. */
.band{{background:{INK};color:{LIME};border-radius:10px;padding:14px 18px;
  margin:0 0 18px;display:flex;align-items:center;gap:10px;flex-wrap:wrap}}
.band .lockup{{font-family:'Space Grotesk',Manrope,sans-serif;font-weight:600;
  font-size:13px;letter-spacing:.02em}}
.band .spark{{width:9px;height:9px;border-radius:2px;background:{PATINA};
  flex:0 0 auto}}
.band .kicker{{margin-left:auto;color:{PATINA};font-size:11px;font-weight:700;
  letter-spacing:.12em;text-transform:uppercase}}

/* Marks size to their column and never push the page sideways. */
.mark{{margin:10px 0 2px}}
.mark svg{{display:block;max-width:100%;height:auto}}
/* A status chip sits on a line of prose, so it is the one mark that stays inline. */
.chipmark svg{{display:inline-block;vertical-align:-7px}}

/* The legend states what the colours mean, once per page. Without it a reader
   has to infer the contract from the marks. */
.legend{{display:flex;gap:14px;flex-wrap:wrap;color:{MUTED};font-size:12px;
  margin:6px 0 0}}
.legend span{{display:flex;align-items:center;gap:6px}}
.legend i{{width:14px;height:10px;border-radius:2px;display:block;flex:0 0 auto}}
.legend i.today{{background:none;border-top:2px dashed {PATINA};height:0;border-radius:0}}
.note{{color:{MUTED};font-size:12.5px;margin:8px 0 0}}
@media (max-width:560px){{body{{padding:14px}} h1{{font-size:22px}}
  .tile .n{{font-size:24px}}}}
@media print{{body{{background:#fff;padding:0}} .card,.tile,.caveat{{break-inside:avoid}}
  .band{{-webkit-print-color-adjust:exact;print-color-adjust:exact}}}}
"""


def section(heading: str, body: str) -> str:
    """A heading only where there is something under it. An empty section reads as a bug."""
    return f'<h2>{esc(heading)}</h2>{body}' if body else ""


def band(title: str, kicker: str = "") -> str:
    """The CAC header band: ink ground, patina spark, lockup, optional kicker."""
    k = f'<span class="kicker">{esc(kicker)}</span>' if kicker else ""
    return (f'<div class="band"><span class="spark"></span>'
            f'<span class="lockup">{esc(title)}</span>{k}</div>')


def legend() -> str:
    """What the colours mean, in this register's own words.

    Measure first: the granted window is a duration and carries no band, which is the
    default here rather than the exception. Patina is last and is labelled as chrome —
    it marks today and never says anything about a record.
    """
    items = [(G._MEASURE, "granted window elapsed"),
             (G._RAG["good"]["fill"], "current"),
             (G._RAG["high"]["fill"], "re-validation due"),
             (G._RAG["critical"]["fill"], "re-validation overdue or past expiry")]
    out = [f'<span><i style="background:{c}"></i>{esc(t)}</span>' for c, t in items]
    out.append('<span><i class="today"></i>today — chrome, never a status</span>')
    return f'<div class="legend">{"".join(out)}</div>'


# The graphics standard puts the gantt's ceiling at eight rows: past that the bars are
# thinner than their labels and the mark stops answering anything. A register can hold
# far more than eight live records, so the rows shown are the most urgent ones and the
# page says how many it is not drawing. Nothing is dropped — every record is in the table
# or the cards below, which is where a lapsed clock has to keep surfacing.
GANTT_ROW_LIMIT = 8

# Expired first, then overdue, then due, then the rest, and by id inside a rank. Same
# order the board view ranks its cards by, so the mark and the page agree, and
# deterministic so one register always draws the same chart.
_BAND_ORDER = {"expired": 0, "revalidation-overdue": 1, "revalidation-due": 2}


def lifecycle_rows(ctx: "Context") -> list:
    return sorted(ctx.active(), key=lambda r: (_BAND_ORDER.get(r["band"], 3), r["id"]))


def lifecycle_block(ctx: "Context") -> str:
    """The granted windows, as a gantt, with the re-validation dates on the same axis.

    A gantt rather than a milestone timeline, deliberately. Every record here has a start
    (the date it was accepted) and, where one was set, an end (the date it expires) — a
    duration, and the standard's test between the two marks is exactly that. The count
    settles it the same way: a record contributes both an expiry and a re-validation, so
    four records are eight events and the standard forbids a timeline past six.

    Bars are MEASURE blue because length is duration and fill is elapsed window, neither
    of which has a threshold. The lifecycle band is a separate declared judgement, so it
    gets the chip. That is the library's contract, not a choice made here.
    """
    rows = lifecycle_rows(ctx)
    if not rows:
        return ""
    shown = rows[:GANTT_ROW_LIMIT]
    phases, reval_dates, no_window, unusable = [], set(), [], []
    for r in shown:
        start = iso_or_none(r.get("acceptedDate"))
        end = iso_or_none(r.get("expiryDate"))
        phase = {"label": r["id"], "sev": sev_for(r) or ""}
        if start and end and start <= end:
            phase["start"], phase["end"] = start, end
            phase["pct"] = window_elapsed(r) or 0.0
        elif not r.get("expiryDate"):
            # The row stays, with its label and its state, and the reason it has no bar is
            # printed under the chart. An expiry date that was never set is a fact about
            # the record; inferring an end from the re-validation date would be an
            # invention, and one that would read as an approved end date.
            no_window.append(r["id"])
        else:
            unusable.append(r["id"])
        phases.append(phase)
        reval = iso_or_none(r.get("revalidationDate"))
        if reval:
            reval_dates.add(reval)
    # One diamond per distinct date, and no label on it. Registers review on a cycle, so
    # several records share a date; labelling each one printed four ids on top of each
    # other and the mark said less than nothing. Which record is due when is in the table
    # and in the cards, where it can be read. What the diamonds answer here is the
    # aggregate question the row labels cannot: how many reviews are stacked up, and how
    # many of them sit behind today.
    milestones = [{"label": "", "date": d} for d in sorted(reval_dates)]
    try:
        svg = G.gantt(phases, today=iso_or_none(ctx.today) or "", milestones=milestones)
    except ValueError as exc:
        # Belt and braces: the dates were screened above, so this is a library rule this
        # renderer has not anticipated. Say so on the page — a missing chart with no
        # explanation reads as a chart with nothing in it.
        return (f'<div class="card"><div class="ph">The lifecycle chart could not be '
                f'drawn: {esc(exc)}. Every record is still listed below.</div></div>')
    if not svg:
        return ""
    notes = ['Each bar runs from the date the record was accepted to the date it expires. '
             'The blue fill is how much of that granted window has already gone — a '
             'duration, not a verdict. Each diamond on the top rule is a date somebody '
             'must look again, one per date; the dashed line is today, so a diamond to '
             'its left is a review that has already come round.',
             'Bars are ordered by date rather than scaled to it, so read a fill as a share '
             'of its own window and the dashed line as where today falls.']
    if no_window:
        notes.append("No expiry date is recorded, so there is no window to draw: "
                     + ", ".join(no_window) + ". The record still stands.")
    if unusable:
        notes.append("The accepted and expiry dates could not be drawn as a window — one "
                     "of them is missing, is not in YYYY-MM-DD form, or the end falls "
                     "before the start: " + ", ".join(unusable) + ". Fix them in the store.")
    if len(rows) > len(shown):
        notes.append(f"Showing the {len(shown)} most pressing of {len(rows)} active "
                     f"records, expiry and overdue first. The rest are below, in full.")
    body = "".join(f'<p class="note">{esc(n)}</p>' for n in notes)
    return (f'<div class="card"><div class="mark">{svg}</div>{legend()}{body}</div>')


def page(title: str, body: str, offline: bool = False) -> str:
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{esc(title)}</title>{"" if offline else FONTS}'
            f'<style>{base_css()}</style></head><body><div class="wrap">'
            f'{body}</div></body></html>')


def build_parser(description: str, default_out: str) -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=description,
                                epilog="This report is not legal advice.",
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--in", dest="infile", required=True,
                   help="exceptions_register.py analyze --out JSON")
    p.add_argument("--out", default=default_out)
    p.add_argument("--translations", metavar="FILE",
                   help="ciso-board-translation sidecar; omitted means the board "
                        "narrative renders as a labelled placeholder")
    p.add_argument("--brand", metavar="FILE",
                   help="client brand JSON — ink, patina, bg, measure, wordmark, "
                        "whiteLabel. Refused rather than approximated if any pairing "
                        "falls below its contrast floor")
    p.add_argument("--offline", action="store_true")
    return p


def write(ctx: Context, doc: str, note: str) -> int:
    with open(ctx.out_path, "w", encoding="utf-8") as fh:
        fh.write(doc)
    print(f"wrote {ctx.out_path} ({len(doc):,} bytes) — {note}")
    return 0
