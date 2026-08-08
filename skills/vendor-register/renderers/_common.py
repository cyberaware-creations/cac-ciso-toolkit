"""_common.py — shared chrome for the vendor-register renderers.

Vendored per skill on purpose: every shipped script must run standalone, because a skill
directory is usable on its own and a cross-skill import breaks the moment somebody takes one
skill. The palette, the brand plumbing and the CSS shell are the proven versions from the
sibling registers; what is skill-specific is the criticality layer below.

**The colour split (D-10) is the thing to read before changing anything here.**

Criticality is RAG-coloured on OPERATIONAL surfaces, where it is a genuine triage aid and the
reader knows what the scale means. On BOARD surfaces it renders as a classification carrying
its word, and RAG is reserved for what needs a decision — an overdue assessment, an untested
exit, an untraced dependency. The reason is management by exception: red marks what needs the
board, a well-managed high-criticality arrangement needs nothing from them, and a board
scanning twelve red rows reads twelve problems.

`untraced` takes the neutral measure colour on BOTH surfaces and always carries its word. It
is not a severity and must never borrow one: it says nobody knows what this arrangement holds
up, which is a reason to look rather than a position in a ranking.
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

# The criticality word is always inside its chip — colour never carries the meaning alone,
# which also means a reader who cannot distinguish the hues loses nothing.
PLACEHOLDER = ("Board narrative not supplied. Run the ciso-board-translation skill over "
               "this register and pass its output with --translations to replace this block.")

# Surfaced on the page, not tucked into a footer. The absence of a score is the design, and
# a reader who expects one from a third-party tool should be told why there isn't one.
CAVEAT = ("This register produces no vendor score, deliberately. A generated number would look "
          "like an assessment, would be irreproducible, and would disagree with the risk "
          "register that actually owns scoring — findings belong there, scored once. A "
          "criticality shown here is either what a named person assigned or what the walk "
          "derived and nobody has assigned yet, and the page says which.")


def _rebuild_derived() -> None:
    """Nothing to rebuild, and that is the stronger position rather than an omission.

    The sibling registers keep module-level colour tables that `apply_brand` has to
    recompute, and `check-versions.py` exists partly to police that. This skill has none:
    every colour is produced inside `criticality_fill` / `trigger_fill` at call time, so a
    brand rebound after import reaches them with no bookkeeping. Kept as an explicit no-op
    because `apply_brand` calls it, and a reader who finds it empty should be told why
    rather than left wondering what got deleted.
    """


UNTRACED = "untraced"
UNCLASSIFIED = "unclassified"


# --- Criticality, and the two ways it is coloured (D-10) ----------------------
#
# Built at CALL time, never bound at import: the brand is process-global and can be rebound
# after this module loads, so a value captured here would keep printing CAC colours on a
# client's re-branded page. `tools/check-versions.py` enforces that, and it is not advisory.

def neutral_fill():
    """The measure pair — a classification colour that is not a severity.

    `G.chip` deliberately only knows RAG bands, so this is built here rather than borrowed.
    Handing `untraced` a severity is the exact failure the state exists to prevent: it would
    turn "nobody knows what this holds up" into a position in a ranking.
    """
    return ("#EFEDE7", MUTED)


def criticality_fill(level: str, scale=(), board: bool = False):
    """(background, foreground) for a criticality chip.

    `board=True` gives the classification treatment: one measure colour for every real level,
    so a board page does not read as a wall of red. `board=False` gives RAG, which is what an
    operator triaging a register actually wants.
    """
    if level in (UNTRACED, UNCLASSIFIED):
        # Neutral on BOTH surfaces. Not a severity, and never allowed to borrow one.
        return neutral_fill()
    if board:
        # The classification treatment: one colour for every real level, so a board page
        # does not read as a wall of red. This IS the D-10 split.
        return neutral_fill()
    scale = list(scale or [])
    if level not in scale:
        return neutral_fill()
    # Derived from the scale's own length, not from the words: the scale is a setting, and an
    # organisation may not use "high" at all.
    place = scale.index(level)
    if place == len(scale) - 1:
        return G.chip("critical")
    if place == len(scale) - 2 and len(scale) > 2:
        return G.chip("high")
    return G.chip("good")


# Escalations are RAG on BOTH surfaces. This is the half that needs a decision, and it is
# what the board treatment reserves colour for.
TRIGGER_SEV = {
    "unclassified": "critical",
    "untraced": "critical",
    "assessment-overdue": "critical",
    "exit-untested": "high",
    "criticality-conflict": "high",
    "criticality-unreconciled": "high",
    "supplier-changed": "high",
}


def trigger_fill(trigger: str):
    return G.chip(TRIGGER_SEV.get(trigger, "medium"))


def crit_chip(level: str, scale=(), board: bool = False) -> str:
    """A criticality chip. The WORD is always inside it — colour never carries meaning alone."""
    bg, fg = criticality_fill(level, scale, board)
    # `chip crit` and not just `chip`: an escalation trigger is ALSO called "untraced", and a
    # checker (or a reader) with only the word to go on cannot tell a classification from a
    # severity. The two are coloured by opposite rules, so they must be tellable apart.
    return ('<span class="chip crit" style="background:%s;color:%s">%s</span>'
            % (bg, fg, esc(level)))


def trigger_chip(trigger: str, text: str = "") -> str:
    """An escalation mark. RAG on BOTH surfaces — this is the half that needs a decision."""
    bg, fg = trigger_fill(trigger)
    return ('<span class="chip trig" style="background:%s;color:%s">%s</span>'
            % (bg, fg, esc(text or trigger)))


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

    One item map, `arrangements`, keyed on the arrangement id rather than the vendor: the
    register is contract-centric, because one provider commonly holds several agreements at
    different criticalities and a vendor-keyed map would force one sentence per company for
    facts that differ per agreement.
    """

    SECTION = "vendor"
    CONTRACT_VERSION = 1

    def __init__(self, raw: dict | None):
        self.absent = raw is None
        raw = raw or {}
        self.executive_summary = raw.get("executiveSummary") or None
        self.arrangements = raw.get("arrangements") or {}
        self.decisions = raw.get("decisions") or []
        self.as_of = raw.get("asOf") or None
        self.contract_version = raw.get("contractVersion", self.CONTRACT_VERSION)
        self.section = raw.get("section") or None

    def line(self, rid: str):
        return self.arrangements.get(rid) or None

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
        if not (tr.arrangements or tr.executive_summary or tr.decisions):
            hint = ""
            if raw and all(isinstance(v, str) for v in raw.values()):
                hint = ('\n  It looks like a flat {"VA-001": "sentence"} map. '
                        'Wrap it: {"arrangements": { ... }}.')
            raise SystemExit(f"error: --translations file {path} contains no usable keys "
                             f'(expected "arrangements", "executiveSummary" '
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
        for key in ("arrangements", "counts", "escalations", "scale"):
            if key not in self.a:
                raise SystemExit(
                    f"error: {args.infile} is not a vendor-register analysis "
                    f"(no {key!r} key). Produce it with "
                    f"`vendor_register.py analyze <store.vnd> --out {args.infile}`.")
        self.rows = self.a["arrangements"]
        self.counts = self.a["counts"]
        self.escalations = self.a["escalations"]
        self.scale = self.a["scale"]
        self.notes = self.a.get("notes") or []
        self.organisation = self.a.get("organisation") or ""
        self.consolidation = self.a.get("consolidation")
        self.today = self.a.get("asOf") or ""
        self.tr = Translations.load(getattr(args, "translations", None))

    def live(self):
        return [r for r in self.rows if not r.get("retired")]

    def esc_for(self, rid: str):
        return [e for e in self.escalations if e.get("subjectRef") == rid]

    def footer(self) -> str:
        bits = [G.footer("Not legal advice"), f"generated {esc(self.today)}"]
        if self.organisation:
            bits.insert(0, esc(self.organisation))
        return "<footer>" + " · ".join(bits) + "</footer>"

    def caveat_block(self) -> str:
        return f'<div class="caveat"><strong>What this is not</strong><p>{esc(CAVEAT)}</p></div>'


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


def legend(board: bool = False) -> str:
    """What the colours mean, in this register's own words — and they differ by surface.

    This is the D-10 split made visible. An operational reader is told criticality is RAG;
    a board reader is told criticality is a classification and that colour marks what needs
    a decision. Printing one legend on both pages would make one of them a lie.
    """
    if board:
        items = [(neutral_fill()[0], "criticality — a classification, not a severity"),
                 (G._RAG["high"]["fill"], "needs attention"),
                 (G._RAG["critical"]["fill"], "needs a decision from this board")]
    else:
        items = [(G._RAG["critical"]["fill"], "top of the criticality scale"),
                 (G._RAG["high"]["fill"], "the level below it"),
                 (G._RAG["good"]["fill"], "lower on the scale"),
                 (neutral_fill()[0], "untraced or unclassified — a question, not a level")]
    out = [f'<span><i style="background:{c}"></i>{esc(t)}</span>' for c, t in items]
    return f'<div class="legend">{"".join(out)}</div>'


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
