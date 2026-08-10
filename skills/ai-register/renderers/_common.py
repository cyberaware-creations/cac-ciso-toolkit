"""_common.py — shared chrome for the ai-register renderers.

Vendored per skill on purpose: every shipped script must run standalone, because a skill
directory is usable on its own and a cross-skill import breaks the moment somebody takes one
skill. The palette, the brand plumbing and the CSS shell are the proven versions from the
sibling registers; what is skill-specific is the two colour rules below.

**Rule one — the D-10 colour split, carried over from `vendor-register` unchanged.**

Criticality is RAG-coloured on OPERATIONAL surfaces, where it is a genuine triage aid and the
reader knows what the scale means. On BOARD surfaces it renders as a classification carrying
its word, and RAG is reserved for what needs a decision. The reason is management by
exception: red marks what needs the board, a well-run top-criticality deployment needs nothing
from them, and a board scanning twelve red rows reads twelve problems and acts on none.

`untraced` takes the neutral measure colour on BOTH surfaces and always carries its word. It
is not a severity and must never borrow one.

**Rule two — an exposure class NEVER renders in a resolved visual state.**

This is the file's own rule, and it is the visual half of the engine's no-closed-state
refusal. There are exactly two states, `no-controls-recorded` and `controls-recorded`, and
both carry words. `controls-recorded` is deliberately NOT green: green is the colour of done,
and a class with four controls against it is not done — NIST's position is that adversarial ML
mitigations are empirical rather than guaranteed and that published defences have repeatedly
been broken. A tick, a green fill or a progress bar would assert on the page exactly what the
engine refuses to assert in the store, and the page is what people actually read.

`evals/board-safety.sh` fails a green or complete affordance on an exposure class.
"""
#
# BRAND TOKENS ARE A DECLARED NINE-WAY TWIN (CAC-TW-1, BL-213). `FONTS`, `INK`, `LIME`,
# `PATINA`, `SLATE`, `WB`, `WB_SURF` and `WB_LINE` are duplicated across all nine
# `renderers/_common.py` copies and must agree character for character — one palette, one
# brand, whatever surface a reader is on. The family is listed in
# skills/risk-register/renderers/_common.py; `tools/check-twins.py` compares all nine on every
# run and fails if any token moves alone.
#
# Nothing else in these modules is claimed to agree. Each carries its own derivation layer and
# its own CLI surface, deliberately.
from __future__ import annotations

import argparse
import html
import json
import re
from datetime import date

# Vendored alongside this file, for the same reason this file is vendored: a shipped script
# must run from its own skill directory with no path surgery.
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

PLACEHOLDER = ("Board narrative not supplied. Run the ciso-board-translation skill over "
               "this register and pass its output with --translations to replace this block.")

# Surfaced on the page, not tucked into a footer. Both absences are the design, and a reader
# who expects a score or a "resolved" column from an AI tool should be told why there is
# neither.
CAVEAT = ("This register produces no AI risk score, deliberately: a generated number would "
          "look like an assessment, would be irreproducible, and would disagree with the risk "
          "register that actually owns scoring. It also has no way to mark an attack class "
          "handled. Controls are recorded with evidence and a date; a class with controls "
          "reads as controls applied, never as closed. Where the organisation wants to accept "
          "a residual exposure, that is an acceptance and belongs in the exceptions register.")


def _rebuild_derived() -> None:
    """Nothing to rebuild, and that is the stronger position rather than an omission.

    Every colour here is produced inside a `*_fill` function at call time, so a brand rebound
    after import reaches them with no bookkeeping. Kept as an explicit no-op because
    `apply_brand` calls it, and a reader who finds it empty should be told why rather than
    left wondering what got deleted.
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
    Handing `untraced` a severity is the exact failure the state exists to prevent.
    """
    return ("#EFEDE7", MUTED)


def criticality_fill(level: str, scale=(), board: bool = False):
    """(background, foreground) for a criticality chip. See rule one above."""
    if level in (UNTRACED, UNCLASSIFIED):
        # Neutral on BOTH surfaces. Not a severity, and never allowed to borrow one.
        return neutral_fill()
    if board:
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


# --- Exposure, and the state it can never be shown in --------------------------

EXPOSURE_LABEL = {
    "no-controls-recorded": "no controls recorded",
    "controls-recorded": "controls recorded",
}
"""Both states carry words, and neither word is a synonym for finished.

"controls recorded" says what happened — somebody recorded a control — and stops there. It
does not say mitigated, addressed, covered or handled, because the register cannot know any of
those and the page must not imply what the store refuses to store.
"""


def exposure_fill(state: str, board: bool = False):
    """(background, foreground) for an exposure-class chip.

    `no-controls-recorded` is RAG on the operational surface, because that is a genuine
    triage cue for whoever works the register. `controls-recorded` is NEUTRAL on both
    surfaces and is never green — see rule two at the top of this file. On a board surface
    both are neutral, and the escalation marks carry the colour.
    """
    if state == "no-controls-recorded" and not board:
        return G.chip("high")
    return neutral_fill()


def exposure_chip(state: str, controls: int = 0, board: bool = False) -> str:
    """An exposure-class state. Always a word, never a tick and never a completion bar."""
    bg, fg = exposure_fill(state, board)
    label = EXPOSURE_LABEL.get(state, state)
    if state == "controls-recorded" and controls:
        label = "%d control%s recorded" % (controls, "" if controls == 1 else "s")
    return ('<span class="chip expo" style="background:%s;color:%s">%s</span>'
            % (bg, fg, esc(label)))


# Escalations are RAG on BOTH surfaces. This is the half that needs a decision, and it is what
# the board treatment reserves colour for. The three that fire at every criticality level —
# a model swapped, a base model swapped, something unsanctioned in use — sit at the top,
# because a low-criticality deployment has no cadence and these are all that would catch it.
TRIGGER_SEV = {
    "unsanctioned-in-use": "critical",
    "unclassified": "critical",
    "untraced": "critical",
    "assessment-overdue": "critical",
    "model-changed": "high",
    "base-model-changed": "high",
    "autonomy-increased": "high",
    "unowned": "high",
    "attack-class-uncontrolled": "high",
    "provider-arrangement-missing": "medium",
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


def autonomy_chip(level: str) -> str:
    """Autonomy is a classification, never a severity — on either surface.

    `acts` is not worse than `informs`; it is a different thing, and whether it is a problem
    depends entirely on what the deployment reaches. Colouring it red would make the board
    read the ladder as a risk scale, which is the misreading this register works hardest to
    avoid.
    """
    bg, fg = neutral_fill()
    return ('<span class="chip auto" style="background:%s;color:%s">%s</span>'
            % (bg, fg, esc(level or "undeclared")))


_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def iso_or_none(value):
    """A date the graphics library will accept, or None. Never a guess at what was meant."""
    text = "" if value is None else str(value)
    if not _ISO.match(text):
        return None
    try:
        date.fromisoformat(text)
    except ValueError:
        return None
    return text


# --- Client brand override ----------------------------------------------------

_BRAND_BINDINGS = {
    "INK": "ink", "INK_RAISED": "inkRaised", "INK_LINE": "inkLine",
    "LIME": "lime", "LIME_DIM": "limeDim",
    "PATINA": "patina", "PATINA_H": "patinaHover", "PATINA_TEXT": "patinaText",
    "SLATE": "slate", "WB": "bg", "WB_SURF": "surface", "WB_LINE": "line",
    "MUTED": "muted",
}
# Snapshotted at import and restored verbatim when no brand is supplied, so "no --brand
# renders exactly what it always did" is true by construction rather than by inspection.
_BRAND_DEFAULTS = {n: globals()[n] for n in _BRAND_BINDINGS if n in globals()}


def apply_brand(path: str = "") -> None:
    """Rebind this module's shell from a client brand file, or restore the CAC one.

    Raises `SystemExit` with the reason on a bad file or a refused palette. A renderer that
    fell back to CAC colours after a failed override would hand a client a document that looks
    finished and is not the one they asked for.
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


class Translations:
    """The ciso-board-translation sidecar, per board-pack/references/section-contract.md.

    One item map, `deployments`, keyed on the deployment id rather than the system: risk lives
    in the deployment, so one model used twice needs two sentences, and a system-keyed map
    would force one sentence to cover facts that differ per use.
    """

    SECTION = "ai"
    CONTRACT_VERSION = 1

    def __init__(self, raw):
        self.absent = raw is None
        raw = raw or {}
        self.executive_summary = raw.get("executiveSummary") or None
        self.deployments = raw.get("deployments") or {}
        self.decisions = raw.get("decisions") or []
        self.as_of = raw.get("asOf") or None
        self.contract_version = raw.get("contractVersion", self.CONTRACT_VERSION)
        self.section = raw.get("section") or None

    def line(self, did: str):
        return self.deployments.get(did) or None

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
        if not (tr.deployments or tr.executive_summary or tr.decisions):
            hint = ""
            if raw and all(isinstance(v, str) for v in raw.values()):
                hint = ('\n  It looks like a flat {"D-001": "sentence"} map. '
                        'Wrap it: {"deployments": { ... }}.')
            raise SystemExit(f"error: --translations file {path} contains no usable keys "
                             f'(expected "deployments", "executiveSummary" '
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
        # call time, so rebinding the module palette here reaches all of them — but only if it
        # happens before the first one is built.
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
        for key in ("deployments", "counts", "escalations", "scale"):
            if key not in self.a:
                raise SystemExit(
                    f"error: {args.infile} is not an ai-register analysis "
                    f"(no {key!r} key). Produce it with "
                    f"`ai_register.py analyze <store.air> --out {args.infile}`.")
        self.rows = self.a["deployments"]
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

    def esc_for(self, did: str):
        return [e for e in self.escalations if e.get("subjectRef") == did]

    def footer(self) -> str:
        bits = [G.footer("Not legal advice"), f"generated {esc(self.today)}"]
        if self.organisation:
            bits.insert(0, esc(self.organisation))
        return "<footer>" + " · ".join(bits) + "</footer>"

    def caveat_block(self) -> str:
        return f'<div class="caveat"><strong>What this is not</strong><p>{esc(CAVEAT)}</p></div>'


# The gstatic preconnect is where the font FILES come from; the googleapis one only
# reaches the stylesheet. Eight of the nine copies had only the second until v0.85.0,
# so the nine `FONTS` values were not identical and the CAC-TW-1 brand-token twin below
# could not be registered without either converging them or exempting a real difference.
# Converged on the fuller form rather than the majority one: matching eight files by
# deleting a correct resource hint from the ninth would be the checker dictating the
# product (BL-213).
FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com">'
         '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
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
.card-head{{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:6px}}
.tiles{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px}}
.tile{{background:{WB_SURF};border:1px solid {WB_LINE};border-radius:10px;padding:14px}}
.tile .n{{font-family:'Space Grotesk',sans-serif;font-size:28px;font-weight:600;
  display:block;line-height:1.1}}
.tile .l{{color:{MUTED};font-size:13px}}
.scroll{{overflow-x:auto;-webkit-overflow-scrolling:touch}}
table{{border-collapse:collapse;width:100%;min-width:820px}}
th,td{{text-align:left;padding:9px 10px;border-bottom:1px solid {WB_LINE};vertical-align:top}}
th{{color:{MUTED};font-size:13px;font-weight:600;white-space:nowrap}}
.chip{{display:inline-block;padding:2px 9px;border-radius:999px;font-size:12.5px;
  font-weight:600;white-space:nowrap}}
.muted{{color:{MUTED}}}
.list{{margin:6px 0 0;padding-left:20px}}
.list li{{margin:3px 0}}
.stats{{display:flex;gap:16px;flex-wrap:wrap;margin:12px 0}}
.stat{{display:flex;align-items:center;gap:7px;background:{WB_SURF};
  border:1px solid {WB_LINE};border-radius:999px;padding:5px 12px 5px 6px}}
.stat span{{font-family:'Space Grotesk',sans-serif;font-weight:600}}
.ph{{background:{LIME};border:1px dashed {SLATE};border-radius:8px;padding:12px 14px;
  color:{MUTED}}}
.caveat{{background:{LIME};border:1px solid {WB_LINE};border-left:4px solid {SLATE};
  border-radius:8px;padding:12px 16px;margin:18px 0;color:{MUTED};font-size:14px}}
.caveat strong{{color:{INK};display:block;margin-bottom:4px}}
.caveat p{{margin:0}}
.note{{background:{WB_SURF};border:1px solid {WB_LINE};border-left:4px solid {PATINA};
  border-radius:8px;padding:10px 14px;margin:14px 0;font-size:14px;color:{MUTED}}}
.note p{{margin:0}}
footer{{color:{MUTED};font-size:12.5px;margin-top:28px;padding-top:14px;
  border-top:1px solid {WB_LINE}}}
/* CAC chrome. A compact band, not a cover: these are working views. */
.band{{background:{INK};color:{LIME};border-radius:10px;padding:14px 18px;
  margin:0 0 18px;display:flex;align-items:center;gap:10px;flex-wrap:wrap}}
.band .lockup{{font-family:'Space Grotesk',Manrope,sans-serif;font-weight:600;
  font-size:13px;letter-spacing:.02em}}
.band .spark{{width:9px;height:9px;border-radius:2px;background:{PATINA};flex:0 0 auto}}
.band .kicker{{margin-left:auto;color:{PATINA};font-size:11px;font-weight:700;
  letter-spacing:.12em;text-transform:uppercase}}
.legend{{display:flex;gap:14px;flex-wrap:wrap;color:{MUTED};font-size:12px;margin:6px 0 0}}
.legend span{{display:flex;align-items:center;gap:6px}}
.legend i{{width:14px;height:10px;border-radius:2px;display:block;flex:0 0 auto}}
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

    Both legends say the same thing about exposure, because that rule does not vary: neither
    state is a finished state, and there is no colour on either page that means done.
    """
    if board:
        items = [(neutral_fill()[0], "criticality and autonomy — classifications, "
                                     "not severities"),
                 (G._RAG["high"]["fill"], "needs attention"),
                 (G._RAG["critical"]["fill"], "needs a decision from this board")]
    else:
        items = [(G._RAG["critical"]["fill"], "top of the criticality scale"),
                 (G._RAG["high"]["fill"], "the level below it, or a class with no control "
                                          "recorded"),
                 (G._RAG["good"]["fill"], "lower on the scale"),
                 (neutral_fill()[0], "untraced, autonomy, or controls recorded — none of "
                                     "which is a severity")]
    out = [f'<span><i style="background:{c}"></i>{esc(t)}</span>' for c, t in items]
    tail = ('<div class="legend"><span>No colour on this page means an attack class is '
            'handled. There is no such state.</span></div>')
    return f'<div class="legend">{"".join(out)}</div>{tail}'


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
                   help="ai_register.py analyze --out JSON")
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
