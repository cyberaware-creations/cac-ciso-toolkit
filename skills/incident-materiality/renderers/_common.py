#!/usr/bin/env python3
"""Shared rendering pieces for the incident-materiality reports.

Each skill carries its own `_common.py` rather than importing a shared one: every shipped
script must run standalone, so a cross-skill import needs sys.path surgery and breaks the
moment a single skill directory is used on its own. Documented the same way in the siblings.

Two reports: a determination worksheet for the CISO and counsel, and a board narrative whose
language comes from `ciso-board-translation` through a sidecar.

Three standing blocks appear on both, by construction rather than by remembering:

  - **not legal advice**, because a materiality determination is a legal judgment;
  - **no verdict**, because nothing here computes, suggests or scores a determination;
  - **the clock rule**, because the single most consequential fact about Item 1.05 is that
    it runs from the determination and not from the discovery.

They are rendered as blocks rather than footnoted. A reader who does not see them has not
been told the three things that most change how this record should be read.
"""
from __future__ import annotations

import argparse
import html
import json

# Vendored alongside this file, for the same reason this file is vendored: a shipped script
# must run from its own skill directory with no path surgery.
# tools/check-versions.py fails if this copy drifts from tools/cac_graphics.py.
import cac_graphics as G

INK = "#14171C"
LIME = "#EAE7DF"
# Brand/action accent. Chrome only: it marks the header spark and the today line on the
# chronology, and it never encodes a measurement or a state.
PATINA = "#2FA98C"
SLATE = "#666D7C"
WB = "#F6F4EE"
WB_SURF = "#FFFFFF"
WB_LINE = "#D8D3C6"
MUTED = "#4A4F58"

# Bands and clock states are a STATUS palette: named states, not points on a scale. Light
# fill, dark ink, so each chip clears AA against its own background by a wide margin. The
# state word is always inside the chip — colour never carries the meaning alone, which also
# means no reader has to infer alarm from a hue.
BAND_FILL = {
    "no-determination":   ("#EDEAE2", MUTED),
    "assessing":          ("#E4E9F0", "#2F4A63"),
    "not-yet-determinable": ("#E4E9F0", "#2F4A63"),
    "not-material":       G.chip("good"),
    "material":           G.chip("high"),
    "disclosure-due":     G.chip("high"),
    "disclosure-overdue": G.chip("critical"),
    "filed":              G.chip("good"),
    "closed":             ("#EFEDE7", MUTED),
}
BAND_LABEL = {
    "no-determination": "no determination recorded",
    "assessing": "under assessment",
    "not-yet-determinable": "not yet determinable",
    "not-material": "determined not material",
    "material": "determined material",
    "disclosure-due": "reporting window open",
    "disclosure-overdue": "past a reporting deadline",
    "filed": "reported",
    "closed": "closed",
}

CLOCK_FILL = {
    "not-applicable": ("#EFEDE7", MUTED),
    "not-started":    ("#EDEAE2", MUTED),
    "anchor-missing": ("#EDE0EA", "#5E3660"),
    # NOT the attention palette, and not the `not in scope` grey either. A withheld window is
    # not an exposure — nothing has gone wrong on this incident — so it may not borrow
    # `high`. But it is also not the settled "not in scope", and painting it the same grey
    # would make an unanswered question look like an answered one, which is the whole of
    # BL-175 arriving through the stylesheet. Its own tone, next to `anchor-missing` because
    # it is the same family: a computation that cannot honestly run yet.
    "scope-not-declared": ("#E5E7F2", "#3A3F6B"),
    "due":            G.chip("high"),
    "overdue":        G.chip("critical"),
    "filed":          G.chip("good"),
}
CLOCK_LABEL = {
    "not-applicable": "not in scope",
    "not-started": "not started",
    "anchor-missing": "anchor not recorded",
    "scope-not-declared": "scope not declared",
    "due": "window open",
    "overdue": "past the deadline",
    "filed": "reported",
}

ASSESSMENT_FILL = {
    "bearing":    G.chip("high"),
    "no-bearing": G.chip("good"),
    "unknown":    ("#EDEAE2", MUTED),
}


def _rebuild_derived() -> None:
    """Recompute the maps that read a palette primitive.

    Called at import and again by apply_brand(). Built from MUTED, so binding them
    once at import froze a client's muted tone back to the CAC one — a leak invisible
    to any test whose sample brand happens not to override `muted`, which is how it
    survived until check_import_time_palette went in.
    """
    global BAND_FILL, CLOCK_FILL, ASSESSMENT_FILL
    BAND_FILL = {
        "no-determination":   ("#EDEAE2", MUTED),
        "assessing":          ("#E4E9F0", "#2F4A63"),
        "not-yet-determinable": ("#E4E9F0", "#2F4A63"),
        "not-material":       G.chip("good"),
        "material":           G.chip("high"),
        "disclosure-due":     G.chip("high"),
        "disclosure-overdue": G.chip("critical"),
        "filed":              G.chip("good"),
        "closed":             ("#EFEDE7", MUTED),
    }
    CLOCK_FILL = {
        "not-applicable": ("#EFEDE7", MUTED),
        "not-started":    ("#EDEAE2", MUTED),
        "anchor-missing": ("#EDE0EA", "#5E3660"),
        "scope-not-declared": ("#E5E7F2", "#3A3F6B"),
        "due":            G.chip("high"),
        "overdue":        G.chip("critical"),
        "filed":          G.chip("good"),
    }
    ASSESSMENT_FILL = {
        "bearing":    G.chip("high"),
        "no-bearing": G.chip("good"),
        "unknown":    ("#EDEAE2", MUTED),
    }


_rebuild_derived()
ASSESSMENT_LABEL = {
    "bearing": "bears on the judgment",
    "no-bearing": "assessed, does not bear",
    "unknown": "not yet knowable",
}

FACTOR_LABEL = {
    "financial": "Financial impact",
    "operational": "Operational disruption",
    "data": "Data affected",
    "regulatory": "Regulatory and contractual",
    "reputational": "Reputational and relationships",
    "aggregation": "Related incidents (aggregation)",
}
FACTOR_ORDER = ("financial", "operational", "data", "regulatory", "reputational",
                "aggregation")

DET_LABEL = {
    "assessing": "under assessment",
    "material": "material",
    "not-material": "not material",
    "not-yet-determinable": "not yet determinable",
}


def determination_phrase(det: dict) -> str:
    """How a determination reads in a sentence.

    `assessing` is not a determination and does not get the verb: an incident is *under
    assessment*, it has not been *determined under assessment*. The distinction is small in
    prose and load-bearing in substance, because the Item 1.05 window turns on it.
    """
    label = DET_LABEL.get(det["state"], det["state"])
    if det["state"] == "assessing":
        return f'under assessment since {det["determinedAt"]}, recorded by {det["decider"]}'
    return f'determined {label} on {det["determinedAt"]} by {det["decider"]}'

REGIME_LABEL = {"sec-1.05": "SEC Item 1.05", "dora": "DORA"}
WINDOW_LABEL = {"8-K": "8-K", "initial": "initial notification",
                "intermediate": "intermediate report", "final": "final report"}

# The attribution line comes from the graphics library, at render time.
#
# It was a module constant here, one copy per skill, five copies in all — and every one of
# them spelled the maker's name out by hand. `G.footer()` drops that name when a client
# white-labels and keeps the disclaimer, so a hardcoded copy is a white-label leak waiting
# for the day this renderer gains a brand flag. Called rather than bound at import for the
# same reason: the brand is process-global and can be rebound after this module loads, and a
# constant captured at import would keep printing the old name on a re-branded page.
PLACEHOLDER = ("Board narrative not supplied. Run the ciso-board-translation skill over this "
               "incident record and pass its output with --translations to replace this block.")

NOT_LEGAL_ADVICE = (
    "A materiality determination is a legal judgment. This record structures and documents "
    "it; it does not make it, and it is not a substitute for counsel. Involve counsel on the "
    "determination and on any filing.")

NO_VERDICT = (
    "Nothing on this page is a verdict. Each factor below carries the assessment and the "
    "reasoning a named person recorded on a stated date. There is no scale, no weight and no "
    "total: the engine does not compute, suggest or score a determination, and it does not "
    "count how many factors were assessed as bearing on it.")

CLOCK_RULE = (
    "The Item 1.05 window runs four business days from the determination that an incident is "
    "material — not from the date it was discovered. An incident still under assessment "
    "therefore has no window open. That is the rule as written, not an omission: the "
    "determination itself must be made without unreasonable delay, and the elapsed time since "
    "discovery is shown alongside so it can be seen.")

# Surfaced wherever an incident is linked to an accepted risk or a granted exception. That
# link is the most useful sentence a board will hear and the one opposing counsel would most
# like to find, and a reader who does not see this has not been told the thing that most
# affects how the entry should be written.
CAVEAT = (
    "These records are discoverable. An incident linked to a risk the organisation knowingly "
    "accepted is a governance asset and a potential litigation exhibit, and which one it "
    "becomes depends on whether it agrees with what the organisation has said publicly. Keep "
    "entries governance-level and factual, align them with what is disclosed, and involve "
    "counsel on anything touching disclosure.")




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
    return html.escape("" if s is None else str(s))


def _chip(table: dict, labels: dict, key: str, fallback: str) -> str:
    bg, fg = table.get(key, table[fallback])
    return (f'<span class="chip" style="background:{bg};color:{fg}">'
            f'{esc(labels.get(key, key))}</span>')


def band_chip(band: str) -> str:
    return _chip(BAND_FILL, BAND_LABEL, band, "closed")


def clock_chip(state: str) -> str:
    return _chip(CLOCK_FILL, CLOCK_LABEL, state, "not-applicable")


def assessment_chip(value: str) -> str:
    return _chip(ASSESSMENT_FILL, ASSESSMENT_LABEL, value, "unknown")


def window_name(clock: dict) -> str:
    return (f'{REGIME_LABEL.get(clock["regime"], clock["regime"])} · '
            f'{WINDOW_LABEL.get(clock["window"], clock["window"])}')


def days_phrase(days, noun: str = "the deadline") -> str:
    """A signed day distance, in words. A distance, never a judgement."""
    if days is None:
        return "—"
    if days < 0:
        return f"{abs(days)} days past {noun}"
    if days == 0:
        return f"{noun} today"
    return f"{days} days to {noun}"


def hours_phrase(hours) -> str:
    if hours is None:
        return "—"
    if hours < 0:
        return f"{abs(hours):.0f}h past the deadline"
    if hours < 48:
        return f"{hours:.0f}h remaining"
    return f"{hours / 24:.0f} days remaining"


# --- The disclosure chronology ------------------------------------------------
#
# One mark, on both views: discovery, the determination, the Item 1.05 filing and the DORA
# final report, laid out on a proportional time axis with today drawn through it.
#
# Every date on it is carried out of the analysis exactly as the engine produced it. Nothing
# here computes a deadline, counts a business day, or decides a determination — the renderer
# positions dates it was handed. The SEC window runs from the determination and an off-by-one
# is a missed filing, so the only safe amount of date arithmetic in a renderer is none.
#
# The spacing is the point. Three days from a determination to an 8-K and a month to the DORA
# final report are the same two rows in a table and visibly different distances here, which is
# the question a reader actually has: where does today sit against the next deadline.

# Only two milestones on this mark carry a band, because only two of them are judgements
# somebody made. Discovery is a fact. A DORA report is a fact. Painting either of them amber
# would put a verdict on the page that nobody recorded.
DET_MILESTONE_LABEL = {
    "material": "determined material",
    "not-material": "determined not material",
    "assessing": "under assessment",
    "not-yet-determinable": "not yet determinable",
}

# `assessing` and `not-yet-determinable` map to no band on purpose. Neither is a
# determination of materiality — the same distinction determination_phrase makes in prose —
# and a coloured dot on either would read as a call that has not been made.
DET_SEV = {"material": "high", "not-material": "good"}

# The filing's band is the engine's own clock state, not a comparison this renderer makes.
# It mirrors CLOCK_FILL so the dot and the chip for one window cannot disagree.
CLOCK_SEV = {"filed": "good", "due": "high", "overdue": "critical"}

# A window's milestone is named for the state the engine put it in. A dot on a deadline that
# has passed must not be captioned "due", and the label carries that on its own so the
# colour is never the only thing saying it.
CLOCK_MILESTONE_LABEL = {
    "sec-1.05:8-K": {"filed": "8-K filed", "due": "8-K due", "overdue": "8-K overdue"},
    "dora:final": {"filed": "DORA final report", "due": "DORA final report due",
                   "overdue": "DORA final report overdue"},
}


def _day(value) -> str:
    """The date part of a recorded date or timestamp. Truncation, never arithmetic.

    DORA anchors and filings are recorded to the hour; the chronology is a day axis. Slicing
    the day off a recorded timestamp changes how a date is displayed and never which date it
    is — unlike a conversion, which is the kind of step that loses a day.
    """
    return str(value)[:10] if value else ""


def _clock_of(row: dict, regime: str, window: str):
    for c in row.get("clocks") or []:
        if c["regime"] == regime and c["window"] == window:
            return c
    return None


def timeline_events(row: dict) -> list:
    """The disclosure sequence for one incident, as the record carries it.

    Four milestones at most, and only where the store holds a date for one. An incident with
    no determination recorded has no determination milestone: that is a legitimate state of
    the record, not a hole to fill, and the mark shows discovery and today with nothing
    between them — which is exactly what is true.
    """
    events = []
    if row.get("discoveredAt"):
        events.append({"label": "discovered", "date": _day(row["discoveredAt"])})

    det = row.get("determination")
    if det and det.get("determinedAt"):
        state = det.get("state", "")
        ev = {"label": DET_MILESTONE_LABEL.get(state, DET_LABEL.get(state, state)),
              "date": _day(det["determinedAt"])}
        if state in DET_SEV:
            ev["sev"] = DET_SEV[state]
        events.append(ev)

    # The 8-K: the date it was filed on if it was, otherwise the deadline the engine
    # computed, so the today line has something to sit against. A window that never opened
    # has neither and plots nothing — an incident under assessment owes no 8-K, and drawing
    # a deadline for one would be the exact error this skill exists to prevent.
    events.append(_window_event(row, "sec-1.05", "8-K", banded=True))
    # The DORA final report, plotted without a band. Its state is in the clock table with
    # the rule beside it; on this mark it is a date in the sequence.
    events.append(_window_event(row, "dora", "final", banded=False))
    return [e for e in events if e]


def _window_event(row: dict, regime: str, window: str, banded: bool):
    """A regulatory window as one milestone: the filing if it happened, else the deadline.

    `banded` says whether this window's ordinary states carry a colour. The 8-K's do; the
    DORA final report's do not, because on a normal incident it is a date in the sequence
    rather than a call anyone has made.

    A LAPSED window is coloured either way. `overdue` is not this renderer's opinion — it is
    a state the engine put the clock in, and it is already shown as a chip in the clock table
    on the same page. A dot that stayed neutral while the table beside it said "overdue"
    would be the mark disagreeing with the number next to it, which is the failure every
    other rule here exists to prevent.
    """
    clock = _clock_of(row, regime, window)
    if not clock:
        return None
    state = clock["state"]
    labels = CLOCK_MILESTONE_LABEL.get(f"{regime}:{window}") or {}
    if state == "filed" and clock.get("filedAt"):
        date = clock["filedAt"]
    elif state in ("due", "overdue") and clock.get("deadline"):
        date = clock["deadline"]
    else:
        return None
    ev = {"label": labels.get(state, window), "date": _day(date)}
    if banded or state == "overdue":
        ev["sev"] = CLOCK_SEV[state]
    return ev


def timeline_block(row: dict, today: str) -> str:
    """One incident's chronology, or a labelled note where a stored date is malformed.

    milestone_timeline raises on a date it cannot place, deliberately: an empty mark where a
    chronology should be is the failure nobody notices. A store is normally written through
    the engine, which refuses a malformed date at the door, so this path means a
    hand-edited file — and the honest response is to name the bad value and keep rendering
    the record, not to drop the page.
    """
    events = timeline_events(row)
    if not events:
        return ""
    try:
        svg = G.milestone_timeline(events, today=_day(today))
    except ValueError as exc:
        return (f'<p class="muted">No chronology is drawn for this incident: {esc(exc)}. '
                f'The dates in the record below are unaffected — the mark is a picture of '
                f'them, never the source.</p>')
    return f'<div class="mark">{svg}</div>' if svg else ""


class Translations:
    """The ciso-board-translation sidecar, per board-pack/references/section-contract.md."""

    SECTION = "incident"
    CONTRACT_VERSION = 1

    def __init__(self, raw):
        self.absent = raw is None
        raw = raw or {}
        self.executive_summary = raw.get("executiveSummary") or None
        self.incidents = raw.get("incidents") or {}
        self.decisions = raw.get("decisions") or []
        self.as_of = raw.get("asOf") or None
        self.contract_version = raw.get("contractVersion", self.CONTRACT_VERSION)
        self.section = raw.get("section") or None

    def line(self, iid: str):
        return self.incidents.get(iid) or None

    @staticmethod
    def load(path) -> "Translations":
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
        if not (tr.incidents or tr.executive_summary or tr.decisions):
            hint = ""
            if raw and all(isinstance(v, str) for v in raw.values()):
                hint = ('\n  It looks like a flat {"I-001": "sentence"} map. '
                        'Wrap it: {"incidents": { ... }}.')
            raise SystemExit(f"error: --translations file {path} contains no usable keys "
                             f'(expected "incidents", "executiveSummary" or '
                             f'"decisions").{hint}')
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
        for key in ("incidents", "attention", "counts"):
            if key not in self.a:
                raise SystemExit(
                    f"error: {args.infile} is not an incident-materiality analysis "
                    f"(no {key!r} key). Produce it with "
                    f"`incident_analysis.py analyze <store.inc> --out {args.infile}`.")
        self.incidents = self.a["incidents"]
        self.attention = self.a["attention"]
        self.counts = self.a["counts"]
        self.meta = self.a.get("meta") or {}
        self.today = self.a.get("today") or ""
        self.now = self.a.get("now") or ""
        self.holidays = self.a.get("holidays") or []
        self.tr = Translations.load(getattr(args, "translations", None))
        only = getattr(args, "incident", None)
        if only:
            known = [r["id"] for r in self.incidents]
            if only not in known:
                raise SystemExit(f"error: no incident {only!r} in {args.infile} "
                                 f"(have: {', '.join(known) or 'none'})")
            self.incidents = [r for r in self.incidents if r["id"] == only]

    def open_incidents(self):
        return [r for r in self.incidents if r["band"] != "closed"]

    def any_linked(self) -> bool:
        return any(r["linkedExceptionIds"] or r["linkedRiskIds"] for r in self.incidents)

    def footer(self) -> str:
        bits = [G.footer("Not legal advice"), f"generated {esc(self.today)}"]
        if self.meta.get("clientName"):
            bits.insert(0, esc(self.meta["clientName"]))
        return "<footer>" + " · ".join(bits) + "</footer>"

    def legal_block(self) -> str:
        return (f'<div class="note note-law"><strong>Not legal advice</strong>'
                f'<p>{esc(NOT_LEGAL_ADVICE)}</p></div>')

    def verdict_block(self) -> str:
        return (f'<div class="note"><strong>No verdict is produced here</strong>'
                f'<p>{esc(NO_VERDICT)}</p></div>')

    def clock_rule_block(self) -> str:
        return (f'<div class="note"><strong>When the window opens</strong>'
                f'<p>{esc(CLOCK_RULE)}</p></div>')

    def caveat_block(self) -> str:
        return (f'<div class="caveat"><strong>Discoverability</strong>'
                f'<p>{esc(CAVEAT)}</p></div>')


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
h4{{font-family:'Space Grotesk',Manrope,sans-serif;font-size:14px;margin:0 0 4px}}
.sub{{color:{MUTED};margin:0 0 20px}}
.card{{background:{WB_SURF};border:1px solid {WB_LINE};border-radius:10px;
  padding:16px 18px;margin:14px 0;min-width:0}}
.tiles{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px}}
.tile{{background:{WB_SURF};border:1px solid {WB_LINE};border-radius:10px;padding:14px;
  min-width:0}}
.tile .n{{font-family:'Space Grotesk',sans-serif;font-size:28px;font-weight:600;
  display:block;line-height:1.1}}
.tile .l{{color:{MUTED};font-size:13px}}
.scroll{{overflow-x:auto;-webkit-overflow-scrolling:touch}}
table{{border-collapse:collapse;width:100%;min-width:680px}}
th,td{{text-align:left;padding:9px 10px;border-bottom:1px solid {WB_LINE};vertical-align:top}}
th{{color:{MUTED};font-size:13px;font-weight:600;white-space:nowrap}}
.chip{{display:inline-block;padding:2px 9px;border-radius:999px;font-size:12.5px;
  font-weight:600;white-space:nowrap}}
.muted{{color:{MUTED}}}
.list{{margin:6px 0 0;padding-left:20px}}
.list li{{margin:3px 0}}
.ph{{background:{LIME};border:1px dashed {SLATE};border-radius:8px;padding:12px 14px;
  color:{MUTED}}}
.note{{background:{LIME};border:1px solid {WB_LINE};border-left:4px solid {SLATE};
  border-radius:8px;padding:12px 16px;margin:16px 0;color:{MUTED};font-size:14px}}
.note strong{{color:{INK};display:block;margin-bottom:4px}}
.note p{{margin:0}}
.note-law{{border-left-color:{INK}}}
.caveat{{background:{LIME};border:1px solid {WB_LINE};border-left:4px solid {SLATE};
  border-radius:8px;padding:12px 16px;margin:18px 0;color:{MUTED};font-size:14px}}
.caveat strong{{color:{INK};display:block;margin-bottom:4px}}
.caveat p{{margin:0}}
.rec{{margin:0 0 6px}}
.rec .who{{color:{MUTED};font-size:13px}}
.trail{{border-left:2px solid {WB_LINE};margin:8px 0 0;padding:0 0 0 14px}}
.trail li{{list-style:none;margin:0 0 10px}}
footer{{color:{MUTED};font-size:12.5px;margin-top:28px;padding-top:14px;
  border-top:1px solid {WB_LINE}}}
/* CAC chrome. A compact band, not a cover: these are working views, and a
   full-page cover on a section a reader opens twenty times is furniture. It also
   stays out of the way of the standing blocks — nothing on this page may push the
   not-legal-advice statement off the first screen. */
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
.mrow{{display:flex;gap:18px;align-items:flex-start;flex-wrap:wrap}}
.mrow .mcol{{flex:1 1 280px;min-width:0}}

/* The legend states what the colours mean, once per page. Without it a reader
   has to infer the contract from the marks. */
.legend{{display:flex;gap:14px;flex-wrap:wrap;color:{MUTED};font-size:12px;
  margin:6px 0 0}}
.legend span{{display:flex;align-items:center;gap:6px}}
.legend i{{width:14px;height:10px;border-radius:2px;display:block;flex:0 0 auto}}

@media (max-width:560px){{body{{padding:14px}} h1{{font-size:22px}}
  .tile .n{{font-size:24px}}}}
@media print{{body{{background:#fff;padding:0}}
  .card,.tile,.note,.caveat{{break-inside:avoid}}
  .band{{-webkit-print-color-adjust:exact;print-color-adjust:exact}}}}
"""


def band(title: str, kicker: str = "") -> str:
    """The CAC header band: ink ground, patina spark, lockup, optional kicker."""
    k = f'<span class="kicker">{esc(kicker)}</span>' if kicker else ""
    return (f'<div class="band"><span class="spark"></span>'
            f'<span class="lockup">{esc(title)}</span>{k}</div>')


def legend() -> str:
    """What the chronology's colours mean. Ink first: it is the default, not the exception.

    A dot is ink unless a named person made a call or a window has a state, which is the
    whole contract of this page restated in four swatches. Patina is last and is not in the
    same list as the others: it is the today line, and it never marks data.
    """
    items = [(G._INK, "a recorded event — no judgement attached"),
             (G._RAG["good"]["fill"], "determined not material, or reported"),
             (G._RAG["high"]["fill"], "determined material, or a window open"),
             (G._RAG["critical"]["fill"], "past a reporting deadline")]
    inner = "".join(f'<span><i style="background:{c}"></i>{esc(t)}</span>'
                    for c, t in items)
    inner += (f'<span><i style="background:{PATINA};width:3px;height:14px"></i>'
              f'today</span>')
    return f'<div class="legend">{inner}</div>'


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
                   help="incident_analysis.py analyze --out JSON")
    p.add_argument("--out", default=default_out)
    p.add_argument("--incident", metavar="ID",
                   help="render one incident only; default is every incident in the store")
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
