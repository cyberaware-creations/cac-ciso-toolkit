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

INK = "#14171C"
LIME = "#EAE7DF"
SLATE = "#666D7C"
WB = "#F6F4EE"
WB_SURF = "#FFFFFF"
WB_LINE = "#D8D3C6"
MUTED = "#4A4F58"

# Lifecycle bands are a STATUS palette: named states, not points on a scale. Light fill,
# dark ink, so each chip clears AA against its own background by a wide margin. The band
# word is always inside the chip — colour never carries the meaning alone.
BAND_FILL = {
    "current":              ("#E3EDE4", "#2F5D3A"),
    "revalidation-due":     ("#F7EBD9", "#7A5218"),
    "revalidation-overdue": ("#F6E0DC", "#7C3A32"),
    "expired":              ("#EDE0EA", "#5E3660"),
    "closed":               ("#EFEDE7", MUTED),
}
BAND_LABEL = {
    "current": "current",
    "revalidation-due": "re-validation due",
    "revalidation-overdue": "re-validation overdue",
    "expired": "expired",
    "closed": "closed",
}
KIND_LABEL = {"acceptance": "accepted risk", "exception": "control exception"}

DISCLAIMER = "A Cyber Aware Creation · Not affiliated with NIST · Not legal advice"
PLACEHOLDER = ("Board narrative not supplied. Run the ciso-board-translation skill over this "
               "register and pass its output with --translations to replace this block.")

# Surfaced on every view that shows these records, not tucked into a footer. The point is
# not to discourage keeping the record — Caremark rewards a documented process — but to
# make sure it is written as something that can be read by a regulator, a board, and
# opposing counsel without contradicting what the organisation said publicly.
CAVEAT = ("These records are discoverable. A permanent, dated inventory of accepted risk is a "
          "governance asset and a potential litigation exhibit, and which one it becomes depends "
          "on whether it agrees with what the organisation has said publicly. Keep entries "
          "governance-level and factual, align them with what is disclosed, and involve counsel "
          "on anything touching disclosure.")


def esc(s) -> str:
    return html.escape("" if s is None else str(s))


def band_chip(band: str) -> str:
    bg, fg = BAND_FILL.get(band, BAND_FILL["closed"])
    return (f'<span class="chip" style="background:{bg};color:{fg}">'
            f'{esc(BAND_LABEL.get(band, band))}</span>')


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
        bits = [DISCLAIMER, f"generated {esc(self.today)}"]
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
@media (max-width:560px){{body{{padding:14px}} h1{{font-size:22px}}
  .tile .n{{font-size:24px}}}}
@media print{{body{{background:#fff;padding:0}} .card,.tile,.caveat{{break-inside:avoid}}}}
"""


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
    p.add_argument("--offline", action="store_true")
    return p


def write(ctx: Context, doc: str, note: str) -> int:
    with open(ctx.out_path, "w", encoding="utf-8") as fh:
        fh.write(doc)
    print(f"wrote {ctx.out_path} ({len(doc):,} bytes) — {note}")
    return 0
