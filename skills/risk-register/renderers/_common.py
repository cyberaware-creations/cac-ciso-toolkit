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
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import score_register as sr  # noqa: E402

# --- Brand tokens (assets/brand.md) ------------------------------------------
# Patina is the brand/action accent and never signals "safe"; severity always
# uses the RAG ramp.
INK = "#14171C"; INK_RAISED = "#1C2026"; INK_LINE = "#2A2F36"
LIME = "#EAE7DF"; LIME_DIM = "#9AA0A6"
PATINA = "#2FA98C"; PATINA_H = "#279884"
SLATE = "#6A7180"; WB = "#F6F4EE"; WB_SURF = "#FFFFFF"; WB_LINE = "#D8D3C6"
# medium is amber, not a second green. Two adjacent greens are not separable at
# stacked-bar size — which also made a bar full of unrefined import seeds read as
# "we're fine" — and a ramp that runs green→green→orange→red is not the CVD-safe
# green→red brand.md claims. Lightness now carries the step as well as hue.
BAND = {"low": "#2e8b57", "medium": "#e8c547", "high": "#e08e0b", "critical": "#c0392b"}
BAND_LABEL = {"low": "Low", "medium": "Medium", "high": "High", "critical": "Critical"}

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

UNCLASSIFIED = "Unclassified"
VELOCITY_MARK = {"improving": "▼", "worsening": "▲", "steady": "→", "new": "＋"}
VELOCITY_COLOR = {"improving": BAND["low"], "worsening": BAND["critical"],
                  "steady": SLATE, "new": PATINA}


def esc(s) -> str:
    return html.escape("" if s is None else str(s))


def chip(band: str) -> str:
    fg = "#fff" if band in ("high", "critical") else INK
    return (f'<span class="chip" style="background:{BAND[band]};color:{fg}">'
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


def parse_args(argv: list[str], description: str, default_out: str) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=description)
    p.add_argument("register", help="path to the .rr register (schema v2)")
    p.add_argument("out", nargs="?", default=default_out,
                   help=f"output HTML path (default: ./{default_out})")
    p.add_argument("--today", default=date.today().isoformat(), metavar="YYYY-MM-DD",
                   help="date to evaluate review/re-validation staleness against "
                        "(default: the system date)")
    p.add_argument("--translations", metavar="FILE",
                   help="board-language sidecar from the ciso-board-translation skill; "
                        "omitted means board narrative is shown as a labelled placeholder")
    p.add_argument("--offline", action="store_true",
                   help="omit the Google Fonts links so the file makes no external request; "
                        "falls back to the system font stack")
    args = p.parse_args(argv)
    try:
        date.fromisoformat(args.today)
    except ValueError:
        p.error(f"--today {args.today!r} is not a YYYY-MM-DD date")
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


def _snapshot_summary(snap: dict) -> dict:
    """A snapshot's frozen summary, recomputed only if the file predates summary freezing."""
    data = snap.get("data", {})
    if data.get("summary"):
        return data["summary"]
    st = {"matrixSize": 5, "appetite": "medium", **data.get("settings", {})}
    return sr.summarize(data.get("risks", []), st["matrixSize"], st["appetite"])


class Context:
    """Everything the renderers draw, derived from one register + optional sidecar."""

    def __init__(self, args: argparse.Namespace):
        self.args = args
        self.offline = bool(getattr(args, "offline", False))
        self.today = args.today
        self.register_path = args.register
        self.out_path = args.out
        self.reg = sr.load_register(args.register)
        self.scored = sr.score_register(self.reg)
        self.meta = self.reg["meta"]
        self.settings = self.reg["settings"]
        self.size = self.settings["matrixSize"]
        self.appetite = self.settings["appetite"]
        self.summary = self.scored["summary"]
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
                }

        self.risks = [self._enrich(r) for r in self.scored["risks"]]
        self.by_id = {r["id"]: r for r in self.risks}
        self.trend = self._trend()
        self.diff = self._diff()
        self.attention = self._attention()
        self.owner_load = self._owner_load()
        self.theme_rollup = self._theme_rollup()
        self.decisions = self._decisions()

    # -- per risk --

    def _history_for(self, rid: str) -> list[dict]:
        return [e for e in self.reg.get("history", []) if e.get("riskId") == rid]

    def _enrich(self, r: dict) -> dict:
        tid = r.get("theme")
        acc = r.get("acceptance") or None
        prior = self._prior.get(r["id"])
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
            "reviewOverdue": (r.get("status") != "closed"
                              and _overdue(r.get("reviewDate"), self.today)),
            "unowned": not (r.get("owner") or "").strip(),
            "acceptance": acc,
            "acceptanceDue": bool(acc) and _overdue(acc.get("revalidationDate"), self.today),
            "acceptanceExpired": bool(acc) and _overdue(acc.get("expiryDate"), self.today),
            "acceptanceIncomplete": bool(acc) and not (acc.get("approver")
                                                       and acc.get("justification")),
            "history": self._history_for(r["id"]),
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
                       "overAppetite": self.summary["overAppetite"],
                       "byBand": self.summary["byBand"], "total": self.summary["total"],
                       "current": True})
        return series

    def _rationales_since_baseline(self) -> dict[str, str]:
        """Rationales logged after the last snapshot — the 'why' behind this period's moves."""
        hist = self.reg.get("history", [])
        cut = 0
        for i, e in enumerate(hist):
            if e.get("type") == "snapshot-created":
                cut = i + 1
        out = {}
        for e in hist[cut:]:
            if e.get("riskId") and e.get("rationale"):
                out[e["riskId"]] = e["rationale"]
        return out

    def _diff(self) -> dict:
        """What changed since the last snapshot — the continuity spine of the board story."""
        if not self.baseline:
            return {"baseline": None, "changes": [], "added": [], "removed": []}
        why = self._rationales_since_baseline()
        changes, added = [], []
        for r in self.risks:
            prior = self._prior.get(r["id"])
            if prior is None:
                added.append(r)
                changes.append({"kind": "added", "id": r["id"], "title": r["title"],
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
                            "detail": " · ".join(bits), "rationale": why.get(r["id"], "")})
        removed = [p for rid, p in self._prior.items() if rid not in self.by_id]
        for rid, p in self._prior.items():
            if rid not in self.by_id:
                changes.append({"kind": "removed", "id": rid, "title": p["title"],
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
        live = [r for r in self.risks if r.get("status") != "closed"]
        over = [r for r in live if r["overAppetite"]]
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
            "unowned": [r for r in live if r["unowned"]],
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

    # -- helpers renderers share --

    def top_risks(self, n: int = 5) -> list[dict]:
        return sorted(self.risks, key=lambda r: -r["residualExposure"])[:n]

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

    def as_of_line(self) -> str:
        if self.baseline:
            return (f'As of {self.today} · compared against '
                    f'{self.baseline.get("label", "the last snapshot")}')
        return f"As of {self.today} · no snapshot yet, so no trend is available"

    def footer(self, extra: str = "") -> str:
        bits = [DISCLAIMER, f"generated {self.today} from {Path(self.register_path).name}"]
        if extra:
            bits.append(extra)
        if self.tr.absent:
            bits.append("board narrative not supplied")
        return " · ".join(bits)


def build(argv: list[str], description: str, default_out: str) -> Context:
    return Context(parse_args(argv, description, default_out))


def write(ctx: Context, doc: str) -> None:
    out = Path(ctx.out_path)
    if out.parent != Path(""):
        out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(doc, encoding="utf-8")
    print(f"wrote {out} ({len(doc):,} bytes) — {ctx.summary['total']} risks, "
          f"{ctx.summary['overAppetite']} over appetite")
