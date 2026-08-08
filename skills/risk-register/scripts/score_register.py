#!/usr/bin/env python3
"""
score_register.py — deterministic NIST-aligned scoring for the risk-register skill.

Ported verbatim from the Cyber Aware Creations web engine (lib/risk/scoring.ts, summary.ts,
import.ts) so a skill run bands risks identically to the original tool instead of
eyeballing thresholds. Standard library only — no dependencies.

NIST anchors:
  - Exposure = Likelihood x Impact   (SP 800-30 Rev. 1, qualitative model)
  - Bands scale with matrix size     (documented per size below)
  - Appetite = worst band still acceptable  (CSF 2.0 GV.RM)

Subcommands:
  score        <register.rr> [--json] [--today YYYY-MM-DD]
                                         Score a register; print summary (+ optional JSON).
  escalations  <register.rr> [--today YYYY-MM-DD] [--json]
                                         What this register currently escalates, and why.
                                         Exits 0 either way — it flags, it does not gate.
  import-gaps  <gaps.csv> [--into r.rr] [--write]   Map a CSF gap CSV to candidate risks.
                                         Previews by default; --write applies the merge.
  self-test                              Assert the engine against the web repo's test cases.

Mutations (each appends an append-only history event and writes a schema-valid file):
  init         <register.rr> --client 'Name' [--assessor ..] [--matrix 5] [--appetite medium]
                                         [--scope-note ..] [--appetite-statement ..]
                                         [--currency GBP]
  add          <register.rr> --title ... --il L --ii I --rl L --ri I [--theme ID]
                                         [--response mitigate] [--response-desc ..]
                                         [--cost 45000] [--why ...]
                                         --cost is a whole number; 0 means priced at
                                         nothing, absent means not priced.
  set-text     <register.rr> <id> [--title ...] [--description ...] --why ...
                                         Reword an imported gap as an if-then event
                                         statement; clears `provisionalTitle`.
  set-score    <register.rr> <id> [--inherent L I] [--residual L I] --why ...
  accept       <register.rr> <id> --approver ... --justification ... --revalidate DATE
  confirm      <register.rr> <id> --why ... [--review YYYY-MM-DD]
                                         Record that a risk was reviewed and nothing
                                         changed. Resets confirmation age; changes no
                                         score, status or band.
  set-status   <register.rr> <id> <open|in-treatment|monitoring|closed> [--why ...]
  add-theme    <register.rr> --id ID --name 'Display Name' [--description ...]
  set-theme    <register.rr> <risk-id> <theme-id|none> [--why ...]
  set-response <register.rr> <id> [--type mitigate] [--response-desc ..] [--cost 45000]
                                         --why ...
                                         The correction path for a treatment recorded
                                         wrongly at `add`. Appends response-changed.
  set-currency <register.rr> --currency GBP --why ...
                                         Relabels treatment costs; never converts them.
  set-escalation <register.rr> [--sustained N] [--dwell-days D] [--band-cross on|off]
                                         [--lapsed-acceptance on|off] --why ...
                                         Tune when this register escalates. Logged: a
                                         threshold change rewrites what gets reported.
  snapshot     <register.rr> --label 'Q3 2026 Board Review' [--note ...]
  export-csv   <register.rr> [--out out.csv]
  export-acceptances <register.rr> [--out out.json]   Accepted risks, in the
                                         exceptions-register intake shape. One-way:
                                         that skill is the system of record.

Usage:
  python3 score_register.py score client-register.rr
  python3 score_register.py score client-register.rr --json > scored.json
  python3 score_register.py import-gaps acme-gaps.csv --into client-register.rr
  python3 score_register.py self-test
"""

from __future__ import annotations

import contextlib
import csv
import io
import json
import os
import re
import sys
import tempfile
from datetime import date, datetime, timezone
from typing import Any

# Behave like a normal Unix filter: on a closed pipe (e.g. `... | head`), exit
# quietly instead of dumping a BrokenPipeError traceback.
try:
    import signal
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)
except (ImportError, AttributeError, ValueError):
    pass

# --- Constants (harvested from scoring.ts) -----------------------------------

SCHEMA_VERSION = 2          # current write version
SUPPORTED_SCHEMA = {1, 2}   # v1 files load and are normalized to v2 shape in memory
BAND_ORDER = ["low", "medium", "high", "critical"]

# Inclusive lower bound for each band, per matrix size. First band (scanning
# critical -> low) whose threshold <= exposure wins. Values match the 800-30
# banding used in the tool; 5x5 is the standard 1..25 spread.
BAND_THRESHOLDS = {
    5: {"low": 1, "medium": 5, "high": 10, "critical": 15},
    4: {"low": 1, "medium": 4, "high": 8, "critical": 12},
    3: {"low": 1, "medium": 3, "high": 5, "critical": 7},
}

RATING_LABELS = {
    5: {1: "Very Low", 2: "Low", 3: "Moderate", 4: "High", 5: "Very High"},
    4: {1: "Low", 2: "Moderate", 3: "High", 4: "Very High"},
    3: {1: "Low", 2: "Moderate", 3: "High"},
}

# Seed inherent likelihood == impact from a CSF gap's priority (import.ts).
PRIORITY_SEED = {"critical": 5, "high": 4, "medium": 3, "low": 2}

# When a worsening exposure is worth surfacing on its own. Per-register rather than global,
# and stored in `settings` rather than anywhere else, because `snapshot` freezes settings
# wholesale — thresholds kept outside it would make a snapshot un-reproducible, since the
# escalations it recorded could not be recomputed from what it saved.
#
# The numbers are chosen to fire on real drift and stay quiet on noise. Two consecutive
# worsening snapshots is a trend rather than a wobble; 180 days over appetite is two
# quarterly reviews that both declined to act.
ESCALATION_DEFAULTS = {
    "sustainedWorseningSnapshots": 2,   # consecutive worsening snapshots, no band cross
    "appetiteDwellDays": 180,           # continuously over appetite this long
    "bandCross": True,                  # any residual band worsening escalates
    "lapsedAcceptance": True,           # acceptance past expiryDate escalates
}

# Default themes for CSF-imported risks. Themes are the stated board-rollup axis, and
# without a mapping every imported risk lands as "Unclassified", which makes the board's
# theme tile read "Unclassified · 74 risks · worst Critical". The CSF Function is the one
# grouping the gap CSV always carries, so it is the honest default — rename or re-theme
# afterwards with add-theme / set-theme if the organisation groups risk differently.
# This is the CSF import path specifically; nothing else in the engine knows these names.
CSF_FUNCTION_THEMES = {
    "GV": "Govern", "ID": "Identify", "PR": "Protect",
    "DE": "Detect", "RS": "Respond", "RC": "Recover",
}

# --- Core scoring (scoring.ts) -----------------------------------------------


def exposure(likelihood: int, impact: int) -> int:
    return likelihood * impact


def band(exposure_value: int, size: int) -> str:
    thresholds = BAND_THRESHOLDS[size]
    for b in reversed(BAND_ORDER):  # critical -> low
        if exposure_value >= thresholds[b]:
            return b
    return "low"


def rating_label(level: int, size: int) -> str:
    return RATING_LABELS[size].get(level, str(level))


def over_appetite(residual_exposure: int, size: int, appetite: str) -> bool:
    return BAND_ORDER.index(band(residual_exposure, size)) > BAND_ORDER.index(appetite)


# --- Summary (summary.ts) ----------------------------------------------------


def treatment_cost(risks: list[dict], currency: str = "") -> dict:
    """What the recorded treatments cost, and how much of the register carries no price.

    Every risk may record `response.cost`. Until this existed the figure was stored,
    validated, and then shown to nobody — a board pack could carry eleven risks and not one
    number about money.

    Two decisions worth stating, because both could reasonably have gone the other way:

    **Open risks only.** A closed risk's treatment cost is spent. Rolling it into a figure a
    board reads as "what this still needs" would overstate the ask.

    **`unpriced` travels with the total, always.** A sum that hides how many risks carry no
    cost at all is exactly the false precision this toolkit refuses elsewhere: eight of
    eleven priced reads very differently from eleven of eleven, and a board asked to fund
    something is entitled to the denominator next to the number. `display` is built here
    rather than downstream so the currency — which only this register knows — cannot be
    guessed by a consumer, and so a pack can print the string unchanged.
    """
    open_risks = [r for r in risks if r.get("status") != "closed"]
    priced, total = 0, 0
    for r in open_risks:
        cost = (r.get("response") or {}).get("cost")
        # bool is an int in Python, and `"cost": true` must not score as 1.
        if isinstance(cost, bool) or not isinstance(cost, (int, float)):
            continue
        priced += 1
        total += cost
    amount = f"{total:,.0f}"
    return {
        "total": total,
        "currency": currency or None,
        "priced": priced,
        "unpriced": len(open_risks) - priced,
        "of": len(open_risks),
        "display": f"{currency} {amount}".strip() if currency else amount,
        "currencyRecorded": bool(currency),
    }


def summarize(risks: list[dict], size: int, appetite: str, currency: str = "") -> dict:
    by_band = {"low": 0, "medium": 0, "high": 0, "critical": 0}
    closed = 0
    over = 0
    for r in risks:
        res_exp = exposure(r["residual"]["likelihood"], r["residual"]["impact"])
        by_band[band(res_exp, size)] += 1
        if r.get("status") == "closed":
            closed += 1
        if over_appetite(res_exp, size, appetite):
            over += 1
    # Stable descending sort by residual exposure, capped at 5 (matches JS toSorted).
    top = sorted(
        risks,
        key=lambda r: exposure(r["residual"]["likelihood"], r["residual"]["impact"]),
        reverse=True,
    )[:5]
    return {
        "total": len(risks),
        "closed": closed,
        "overAppetite": over,
        "byBand": by_band,
        "topByResidual": [r["id"] for r in top],
        # Additive to the ported web-engine summary. Without these a register cannot tell
        # "assessed as medium" from "never refined", and a band mix of unreviewed
        # candidates renders as a confident bar.
        #
        # `provisional` is the union — anything unreviewed in either dimension — and is
        # what the disclosure banners count. The two components are reported separately
        # because they mean different things to a reader: a provisional *title* is a
        # board-safety issue, a provisional *score* is a data-quality one.
        "provisional": sum(1 for r in risks
                           if r.get("provisionalTitle") or r.get("provisionalScore")),
        "provisionalTitle": sum(1 for r in risks if r.get("provisionalTitle")),
        "provisionalScore": sum(1 for r in risks if r.get("provisionalScore")),
        "treatmentCost": treatment_cost(risks, currency),
    }


# --- CSF gap import (import.ts) ----------------------------------------------

REQUIRED_GAP_COLS = [
    "subcategory_id", "function_id", "category_id", "current_tier",
    "target_tier", "priority", "subcategory_text", "note",
]


def parse_gaps_csv(text: str) -> list[dict]:
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise ValueError("Empty CSV.")
    missing = [c for c in REQUIRED_GAP_COLS if c not in reader.fieldnames]
    if missing:
        raise ValueError(f"Missing required header column(s): {', '.join(missing)}")
    return [row for row in reader if any((v or "").strip() for v in row.values())]


def empty_risk(risk_id: str) -> dict:
    return {
        "id": risk_id, "title": "", "description": "", "category": "", "owner": "",
        "inherent": {"likelihood": 1, "impact": 1},
        "response": {"type": "mitigate", "description": ""},
        "residual": {"likelihood": 1, "impact": 1},
        "status": "open",
    }


def next_risk_id(risks: list[dict]) -> str:
    max_n = 0
    for r in risks:
        rid = r.get("id", "")
        if rid.startswith("R-") and rid[2:].isdigit():
            max_n = max(max_n, int(rid[2:]))
    return f"R-{max_n + 1:03d}"


def trunc(text: str, limit: int = 140) -> str:
    """Truncate on a word boundary with an ellipsis, never mid-word.

    A title cut mid-word ("…other third parties are understood, recorded, prioritized,
    assesse") reads as a rendering bug to anyone senior enough to be shown it. The
    ellipsis is what tells a reader the sentence continues elsewhere.
    """
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    cut = text[:limit - 1]
    space = cut.rfind(" ")
    if space > limit * 0.6:                     # only if it doesn't gut the string
        cut = cut[:space]
    return cut.rstrip(" ,;:.-") + "…"


def gap_row_to_risk(row: dict, risk_id: str) -> dict:
    level = PRIORITY_SEED.get((row["priority"] or "").lower(), 3)
    risk = empty_risk(risk_id)
    risk["title"] = trunc(f"{row['subcategory_id']}: {row['subcategory_text']}")
    risk["description"] = f"CSF gap — {row['subcategory_text']}"
    risk["category"] = row["function_id"]
    fid = (row["function_id"] or "").strip().upper()
    risk["theme"] = fid.lower() if fid in CSF_FUNCTION_THEMES else None
    risk["csfSubcategoryId"] = row["subcategory_id"]
    risk["inherent"] = {"likelihood": level, "impact": level}
    risk["residual"] = {"likelihood": level, "impact": level}
    # An imported row is a *candidate*, not an assessed risk, and it is unreviewed in two
    # independent ways: the title is a control objective phrased as a good thing, and the
    # scores are a priority seed nobody has looked at.
    #
    # Tracked separately because they are cleared by different acts and only one of them
    # governs board safety. Treating them as one flag meant `set-score` — refining the
    # numbers — also authorised the untouched framework wording for the board, which is
    # precisely the exposure this mechanism exists to prevent.
    risk["provisionalTitle"] = True     # cleared by set-text; gates board-facing titles
    risk["provisionalScore"] = True     # cleared by set-score; gates "is this assessed?"
    # Deliberately NOT "Tier X → Y". These are achievement ratings on a 0-3 scale, and
    # both skills warn that the gap CSV's `current_tier`/`target_tier` column names must
    # never reach a reader. The importer used to produce that exact leak itself.
    note_parts = [f"CSF rating {row['current_tier']} → {row['target_tier']} (achievement, not a CSF Tier)",
                  f"priority: {row['priority']}"]
    if row["note"]:
        note_parts.append(row["note"])
    risk["notes"] = " · ".join(note_parts)
    return risk


def finding_to_risk(finding: dict, risk_id: str) -> dict:
    """A register's finding as a CANDIDATE risk. Unscored, and provisional in both ways.

    Handles `vendor-register` and `ai-register` findings through one path, because they are
    the same act: a named person checked something and recorded that it is not met. A second
    mapper would be a second place for the seed, the provisional flags and the no-score rule
    to drift apart, and the third producer would then get a third.

    Both source registers deliberately produce no likelihood, impact or band. So the seed here
    is the same neutral middle an unreviewed row gets, and `provisionalScore` says out loud
    that nobody has assessed it. The alternative — deriving a seed from the criticality — would
    be this register inventing the number the other skill refused to invent, one import
    removed.
    """
    risk = empty_risk(risk_id)
    risk["title"] = trunc(finding.get("title") or "Third-party finding")
    risk["description"] = finding.get("description") or ""
    # The Category comes from the finding's own Subcategory references where it has them, so
    # an AI finding against ID.RA-01 does not land under GV.SC. GV.SC is the fallback because
    # it is where a third-party finding belongs and where these used to land unconditionally.
    subcats = [s for s in (finding.get("gvsc") or []) if isinstance(s, str) and "." in s]
    risk["category"] = subcats[0].rsplit("-", 1)[0] if subcats else "GV.SC"
    fid = risk["category"].split(".")[0]
    # This read `"govern" if "govern" in CSF_FUNCTION_THEMES`, whose keys are "GV", "ID", ...
    # so it was always None: every imported finding landed outside every CSF theme, and a
    # theme-filtered view silently dropped them all.
    risk["theme"] = fid.lower() if fid in CSF_FUNCTION_THEMES else None
    risk["sourceRef"] = finding.get("sourceRef") or ""
    seed = 3
    risk["inherent"] = {"likelihood": seed, "impact": seed}
    risk["residual"] = {"likelihood": seed, "impact": seed}
    risk["provisionalTitle"] = True     # wording came from another register, not an author
    risk["provisionalScore"] = True     # nobody has scored this; the seed is a placeholder
    bits = []
    if finding.get("vendor"):
        bits.append("Provider: %s" % finding["vendor"])
    if finding.get("autonomy"):
        bits.append("Autonomy: %s" % finding["autonomy"])
    if finding.get("criticality"):
        bits.append("%s criticality: %s (scale %s, %s)"
                    % ("Deployment" if finding.get("sourceDeploymentRef") else "Arrangement",
                       finding["criticality"],
                       finding.get("criticalityScaleVersion") or "unstated",
                       "confirmed" if finding.get("criticalityConfirmed") else "DERIVED, "
                       "not confirmed by a person"))
    if finding.get("nistaml"):
        # Carried as context, never as a state. An attack class has no closed state in
        # `ai-register`; this risk does, and closing the risk closes the risk.
        bits.append("Exposed to %s (recorded in ai-register, where a class is never closed)"
                    % ", ".join(finding["nistaml"]))
    if finding.get("checkedBy"):
        bits.append("Checked by %s on %s" % (finding["checkedBy"],
                                             finding.get("checkedOn") or "an unstated date"))
    if subcats:
        bits.append("CSF: %s" % ", ".join(subcats))
    risk["notes"] = " · ".join(bits) or None
    return risk


# The name this shipped under in v0.39.0, kept so a caller written against it still works.
vendor_finding_to_risk = finding_to_risk


def merge_import(existing: list[dict], candidates: list[dict]) -> dict:
    risks = [dict(r) for r in existing]
    added = updated = 0
    for cand in candidates:
        match = None
        if cand.get("csfSubcategoryId"):
            match = next((r for r in risks if r.get("csfSubcategoryId") == cand["csfSubcategoryId"]), None)
        # `sourceRef` is the generic provenance key, added so vendor findings merge through
        # THIS function rather than through a second importer. Two merge paths would be two
        # sets of rules about when a human-authored title may be overwritten, and only one of
        # them would get the next fix.
        if match is None and cand.get("sourceRef"):
            match = next((r for r in risks if r.get("sourceRef") == cand["sourceRef"]), None)
        if match:
            # Only overwrite the wording while nobody has rewritten it. Once a risk has
            # been through set-text it carries an if-then event statement someone
            # authored; re-importing after a quarterly review must refresh the CSF-derived
            # facts without silently throwing that away.
            if match.get("provisionalTitle"):
                match["title"] = cand["title"]
                match["description"] = cand["description"]
            match["category"] = cand["category"]
            match["notes"] = cand.get("notes")
            # Fill an unset theme, but never overwrite a deliberate re-theme.
            if not match.get("theme") and cand.get("theme"):
                match["theme"] = cand["theme"]
            if cand.get("sourceRef"):
                match["sourceRef"] = cand["sourceRef"]
            updated += 1
        else:
            new = dict(cand)
            new["id"] = next_risk_id(risks)
            risks.append(new)
            added += 1
    return {"risks": risks, "added": added, "updated": updated}


# --- Register I/O (storage.ts) -----------------------------------------------


def load_register(path: str) -> dict:
    with open(path, encoding="utf-8") as fh:
        try:
            obj = json.load(fh)
        except json.JSONDecodeError as exc:
            raise ValueError("Not a valid risk register file (invalid JSON).") from exc
    if obj.get("schemaVersion") not in SUPPORTED_SCHEMA:
        raise ValueError(f"Unsupported schema version (supported: {sorted(SUPPORTED_SCHEMA)}).")
    if not isinstance(obj.get("risks"), list):
        raise ValueError("Invalid register: missing risks array.")
    # `currency` defaults to empty, and empty means *not recorded* — never a guessed symbol.
    # A cost total rendered with the wrong currency is worse than one rendered with none,
    # because only the second is obviously incomplete to the person reading it.
    obj["settings"] = {"matrixSize": 5, "appetite": "medium", "currency": "",
                       **obj.get("settings", {})}
    # Merged per key rather than defaulted wholesale, so a register that set one threshold
    # keeps the shipped values for the other three instead of losing them to a partial block.
    #
    # Deliberately not validated here. The house rule is that validation guards *writes*:
    # `set-escalation` refuses a bad value, and a file that already carries one still loads,
    # scores and renders. Refusing at load would make an existing user's register unopenable
    # over a reporting threshold, which is worse than the bad threshold — the same reasoning
    # references/schema.md gives for non-canonical dates.
    obj["settings"]["escalation"] = {**ESCALATION_DEFAULTS,
                                     **(obj["settings"].get("escalation") or {})}
    if obj["settings"]["matrixSize"] not in BAND_THRESHOLDS:
        raise ValueError(f"Invalid matrixSize {obj['settings']['matrixSize']!r} (must be 3, 4, or 5).")
    if obj["settings"]["appetite"] not in BAND_ORDER:
        raise ValueError(f"Invalid appetite {obj['settings']['appetite']!r} (must be one of {BAND_ORDER}).")
    obj["meta"] = {"clientName": "", "assessor": "", "scopeNote": "", "appetiteStatement": "",
                   **obj.get("meta", {})}
    # Normalize v1 → v2 shape in memory (no data loss; write path stamps schemaVersion 2).
    obj.setdefault("themes", [])
    obj.setdefault("history", [])
    obj.setdefault("snapshots", [])
    for r in obj["risks"]:
        r.setdefault("theme", None)
        r.setdefault("acceptance", None)
        # Risks written before these flags existed were authored by hand, so they are
        # reviewed by definition. Only the importer sets them true.
        #
        # `provisional` was a single flag in an earlier build; a file carrying it is
        # normalized to both dimensions, since at that point neither had been reviewed
        # independently.
        legacy = r.pop("provisional", None)
        if legacy is not None:
            r.setdefault("provisionalTitle", bool(legacy))
            r.setdefault("provisionalScore", bool(legacy))
        r.setdefault("provisionalTitle", False)
        r.setdefault("provisionalScore", False)
    return obj


# --- Escalation (contract CAC-EL-1) ------------------------------------------
#
# Derived, stateless, and never written to the file. An escalation is recomputed from the
# register on every run and clears when its condition clears, which is why there is no
# acknowledge or mute: a stored acknowledgement is how a live exposure goes quiet without
# anything about it having improved.
#
# Nothing here mutates a score. A lapsed acceptance and a drifting exposure are both
# reported and neither is auto-corrected — residual is an assessed number, and reverting one
# on a date would be inventing an assessment nobody made.


def _snap_exposure(r: dict):
    """Residual exposure for a risk as frozen in a snapshot, or None if unreadable.

    Recomputed with exposure() rather than read from a stored field, on the same terms as
    the derived-not-stored rule everywhere else: a snapshot that froze a stale computed
    number would let it contradict the likelihood and impact sitting beside it.
    """
    res = r.get("residual") or {}
    lik, imp = res.get("likelihood"), res.get("impact")
    if isinstance(lik, int) and isinstance(imp, int):
        return exposure(lik, imp)
    return None


def _snapshot_baseline(reg: dict) -> tuple[dict, str]:
    """({riskId: residualExposure}, snapshotLabel) from the newest snapshot.

    Empty dict and "" when the register has no snapshots — a register with no baseline
    escalates nothing, rather than escalating everything against zero. A first run against
    a fresh register is the moment escalation would be least trusted and hardest to undo.

    Newest is the last element, not the latest `ts`. Snapshots are append-only, so insertion
    order is the truth; sorting by timestamp would silently reorder the baseline if two
    machines with skewed clocks ever wrote to one register.
    """
    snaps = reg.get("snapshots") or []
    if not snaps:
        return {}, ""
    newest = snaps[-1]
    out = {}
    for r in (newest.get("data") or {}).get("risks") or []:
        rid = r.get("id")
        exp = _snap_exposure(r)
        if rid and exp is not None:
            out[rid] = exp
    return out, str(newest.get("label") or "")


def _exposure_series(reg: dict, rid: str) -> list:
    """[(YYYY-MM-DD, exposure)] for one risk across every snapshot it appears in, oldest first.

    Snapshots the risk is absent from are skipped rather than treated as zero: a risk added
    in Q3 has no Q2 value, and reading its absence as an exposure of nothing would manufacture
    the steepest possible worsening on the quarter it was created.
    """
    out = []
    for s in reg.get("snapshots") or []:
        for sr in (s.get("data") or {}).get("risks") or []:
            if sr.get("id") == rid:
                exp = _snap_exposure(sr)
                if exp is not None:
                    out.append((str(s.get("ts") or "")[:10], exp))
                break
    return out


def velocity(reg: dict) -> dict:
    """Per-risk movement against the newest snapshot.

    {riskId: {"delta": int, "direction": "worsening"|"improving"|"steady",
              "from": int, "to": int, "baseline": str}}

    Higher exposure is worse, so a positive delta is `worsening`. A risk the baseline does
    not contain is `steady` with a delta of 0 and no baseline — a new risk has not moved,
    and reporting it as worsening would put every addition on the escalation list.
    """
    base, label = _snapshot_baseline(reg)
    out = {}
    for r in reg["risks"]:
        to = exposure(r["residual"]["likelihood"], r["residual"]["impact"])
        if r["id"] in base:
            frm = base[r["id"]]
            delta = to - frm
            out[r["id"]] = {
                "delta": delta,
                "direction": ("worsening" if delta > 0
                              else "improving" if delta < 0 else "steady"),
                "from": frm, "to": to, "baseline": label,
            }
        else:
            out[r["id"]] = {"delta": 0, "direction": "steady",
                            "from": to, "to": to, "baseline": ""}
    return out


ESCALATION_SEVERITY_ORDER = ["critical", "high", "medium"]


def _dwell_days(since: str, today: str):
    """Whole days between two ISO dates, or None if either will not parse.

    Tolerant for the reason references/_common.py gives about ages: a register carrying a
    typo'd timestamp must not turn the escalation report into a traceback on the evening a
    board pack is being produced. A trigger that cannot be measured does not fire.
    """
    try:
        return (date.fromisoformat(today) - date.fromisoformat(since)).days
    except (ValueError, TypeError):
        return None


def suppressed_provisional(reg: dict) -> int:
    """Live risks whose score is an unassessed import seed, and so escalate nothing.

    Reported rather than hidden. Escalating off a `provisionalScore` would escalate off a
    number nobody assessed; suppressing it silently would be the same silence the lapse rule
    exists to prevent, so the count travels with the escalations in the summary.
    """
    return sum(1 for r in reg["risks"]
               if r.get("provisionalScore") and r.get("status") != "closed")


def escalations(reg: dict, today: str = "") -> list[dict]:
    """Every escalation this register currently warrants, in the CAC-EL-1 §1.3 shape.

    Stateless: recomputed from the file, never stored, never an event. `today` is passed in
    rather than read from the clock here — the same rule the renderers follow, so a run is
    reproducible and a test can pin the date. When it is empty the two date-derived triggers
    are skipped rather than guessed at.
    """
    policy = {**ESCALATION_DEFAULTS, **(reg.get("settings", {}).get("escalation") or {})}
    size = reg["settings"]["matrixSize"]
    appetite = reg["settings"]["appetite"]
    snaps = reg.get("snapshots") or []
    base, base_label = _snapshot_baseline(reg)
    base_since = str((snaps[-1].get("ts") if snaps else "") or "")[:10]
    out = []

    for r in reg["risks"]:
        rid = r["id"]
        cur = exposure(r["residual"]["likelihood"], r["residual"]["impact"])

        # acceptance-lapsed runs for closed risks too, and deliberately. A closed risk still
        # carrying a live acceptance is exactly the state worth seeing: the register says the
        # work is finished and the acceptance says somebody is still relying on it.
        #
        # `<=` matches renderers/_common.py::_overdue, which is what computes the
        # `acceptanceExpired` flag the dashboards already show. A stricter `<` here would
        # disagree with that flag for one day per acceptance — one concept, two answers.
        if policy.get("lapsedAcceptance") and today:
            acc = r.get("acceptance") or {}
            expiry = acc.get("expiryDate")
            if expiry and str(expiry)[:10] <= today:
                out.append({
                    "subjectRef": rid, "subjectKind": "risk",
                    "trigger": "acceptance-lapsed", "severity": "high",
                    "since": str(expiry)[:10],
                    "evidence": {
                        "from": str(expiry)[:10], "to": today, "baseline": "",
                        "detail": (f"acceptance expired {str(expiry)[:10]} and is still on "
                                   f"the register — not re-validated, not re-scored"),
                    },
                })

        if r.get("status") == "closed":
            continue
        if r.get("provisionalScore"):
            # Counted by suppressed_provisional(); no score-derived trigger may fire.
            continue

        crossed = False
        if policy.get("bandCross") and rid in base:
            frm = base[rid]
            frm_band, to_band = band(frm, size), band(cur, size)
            if BAND_ORDER.index(to_band) > BAND_ORDER.index(frm_band):
                crossed = True
                out.append({
                    "subjectRef": rid, "subjectKind": "risk",
                    "trigger": "band-crossed",
                    "severity": "critical" if to_band == "critical" else "high",
                    "since": base_since,
                    "evidence": {
                        "from": frm, "to": cur, "baseline": base_label,
                        "detail": (f"residual band {frm_band} -> {to_band} "
                                   f"since the last snapshot"),
                    },
                })

        # A crossed band is the escalation; drift toward it is the same story told twice.
        if not crossed:
            series = _exposure_series(reg, rid) + [(today, cur)]
            vals = [e for _, e in series]
            run = 0
            for i in range(len(vals) - 1, 0, -1):
                if vals[i] > vals[i - 1]:
                    run += 1
                else:
                    break
            need = policy.get("sustainedWorseningSnapshots", 2)
            if run >= need >= 1:
                first = series[len(vals) - 1 - run]
                out.append({
                    "subjectRef": rid, "subjectKind": "risk",
                    "trigger": "sustained-drift", "severity": "medium",
                    "since": first[0],
                    "evidence": {
                        "from": first[1], "to": cur, "baseline": base_label,
                        "detail": (f"residual exposure worsened across {run} consecutive "
                                   f"snapshots without crossing a band"),
                    },
                })

        if today and over_appetite(cur, size, appetite):
            # Walk back while it was over appetite at every snapshot, judging each by the
            # settings that snapshot froze — "it was over appetite then" means by the
            # appetite in force then, not by one adopted afterwards.
            earliest = ""
            for s in reversed(snaps):
                found = None
                for sr in (s.get("data") or {}).get("risks") or []:
                    if sr.get("id") == rid:
                        found = sr
                        break
                exp = _snap_exposure(found) if found else None
                if exp is None:
                    break
                s_set = (s.get("data") or {}).get("settings") or {}
                if not over_appetite(exp, s_set.get("matrixSize", size),
                                     s_set.get("appetite", appetite)):
                    break
                earliest = str(s.get("ts") or "")[:10]
            days = _dwell_days(earliest, today) if earliest else None
            if days is not None and days > policy.get("appetiteDwellDays", 180):
                out.append({
                    "subjectRef": rid, "subjectKind": "risk",
                    "trigger": "appetite-dwell", "severity": "high",
                    "since": earliest,
                    "evidence": {
                        "from": earliest, "to": today, "baseline": base_label,
                        "detail": (f"over appetite continuously for {days} days, "
                                   f"since {earliest}"),
                    },
                })

    out.sort(key=lambda e: (ESCALATION_SEVERITY_ORDER.index(e["severity"]), e["subjectRef"]))
    return out


def _utc_today() -> str:
    """Today in UTC, as YYYY-MM-DD.

    UTC and not local, for the reason the renderers give about `--today`: the register's own
    history timestamps are UTC, and comparing them against a local date gave confirmations a
    negative age that read as fresh.
    """
    return datetime.now(timezone.utc).date().isoformat()


# --- CAC-AP-1: the applicability profile, read as data --------------------------------
#
# The second consumer of the contract, after `incident-materiality` proved the shape.
#
# What narrowing means here is NOT what it means there, and the difference is worth being
# exact about, because getting it wrong would be the token narrowing the contract was written
# to avoid. `incident-materiality` suppresses COMPUTED ROWS — a disclosure window a not-listed
# entity should never have had calculated. This register computes nothing per-domain: a risk
# is scored the same whether it concerns OT or payroll.
#
# So what a profile narrows here is the QUESTION SET, which is exactly what CAC-AP-1 says a
# profile does and all it says. An organisation with no OT is not asked whether its register
# carries OT scenarios; one that has declared nothing IS asked, because §2.2 makes absence
# ask more.
#
# What this deliberately does NOT do is ANSWER the question. Nothing in a `.rr` records
# whether a risk concerns OT or AI — `category` is the CSF Function and `theme` derives from
# it — so a "coverage" figure would be inferred from data that is not there, and this suite
# refuses to invent the number it asks for. That is also why there is no conflict record here
# as there is in `incident-materiality`: a conflict needs both sides stated, and one side is
# genuinely missing. A domain dimension on a risk would make it computable; until one exists,
# the honest output is the question, attributed, and the skips.

CONTEXT_CONTRACT = "CAC-AP-1"
CONTEXT_SKILL = "risk"
CONTEXT_BATTERIES = {
    "ot-scenarios": {"flag": "otPresent", "label": "OT scenarios",
                     "question": "does this register carry scenarios for the operational "
                                 "technology in the estate?"},
    "ai-scenarios": {"flag": "aiInUse", "label": "AI scenarios",
                     "question": "does this register carry scenarios for the AI systems in "
                                 "production use?"},
}


def load_context(path: str) -> dict:
    """Read an applicability payload. As data — this skill imports no other skill (§2.6).

    Both refusals are deliberate. `--context` was passed on purpose, so a payload that cannot
    be honoured must say so rather than quietly leave the register un-narrowed: a full
    question set would read as a profile that decided nothing applied.
    """
    try:
        with open(path, encoding="utf-8") as fh:
            payload = json.load(fh)
    except FileNotFoundError:
        raise ValueError(f"no such context payload: {path}")
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path} is not valid JSON (line {exc.lineno}, "
                         f"column {exc.colno}): {exc.msg}")
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object, got {type(payload).__name__}")
    got = payload.get("contractVersion")
    if got != CONTEXT_CONTRACT:
        raise ValueError(
            f"{path} declares contractVersion {got!r}; this engine reads "
            f"{CONTEXT_CONTRACT!r}. Produce one with `business_context.py export <file.biz>`.")
    if not isinstance(payload.get("applicability"), dict):
        raise ValueError(
            f"{path} carries no decided `applicability`, so this skill cannot tell which "
            f"batteries the profile narrowed away. Re-export it with "
            f"`business_context.py export <file.biz>`; the narrowing decision belongs to "
            f"that skill and is not re-derived here.")
    return payload


def applicability_for(payload: dict) -> dict:
    """The profile's decision for this skill, in this skill's own vocabulary.

    The payload arrives DECIDED — §2.2 and §2.3 were applied by `business-context`, and
    re-deriving them here would be the second implementation the contract exists to prevent.

    There is no subject layer. A register has no per-record perimeter to declare one against:
    `incident-materiality` has an incident and a vendor record will have a vendor, but a risk
    does not sit in a different jurisdiction from the register around it.
    """
    base = (payload.get("applicability") or {}).get(CONTEXT_SKILL) or {}
    profile_ask = set(base.get("ask") or ())
    profile_skipped = {r.get("battery"): r for r in (base.get("skipped") or ())}

    asked, skipped = [], []
    for battery in sorted(CONTEXT_BATTERIES):
        spec = CONTEXT_BATTERIES[battery]
        if battery in profile_skipped:
            skipped.append(dict(profile_skipped[battery]))
        elif battery in profile_ask:
            asked.append({"battery": battery, "label": spec["label"],
                          "flag": spec["flag"], "question": spec["question"]})
    return {
        "profileVersion": str(payload.get("profileVersion") or ""),
        "asked": asked,
        "skipped": sorted(skipped, key=lambda r: r.get("battery") or ""),
        # Stated rather than left to be inferred from an absent key. This skill asks the
        # question and does not answer it, and a reader who assumed otherwise would take a
        # silence for a clean bill.
        "coverageAssessed": False,
    }


def score_register(reg: dict, today: str = "", context: dict = None) -> dict:
    """Score a register, and derive the escalations that follow from it.

    `today` is optional and defaults to empty rather than to the clock. An empty reference
    date skips the two date-derived triggers instead of guessing at them, so a caller that
    did not say what day it is gets fewer escalations rather than wrong ones. Every caller
    that cares — the CLI, the renderers, `snapshot` — passes one.
    """
    size = reg["settings"]["matrixSize"]
    appetite = reg["settings"]["appetite"]
    scored_risks = []
    for r in reg["risks"]:
        inh = exposure(r["inherent"]["likelihood"], r["inherent"]["impact"])
        res = exposure(r["residual"]["likelihood"], r["residual"]["impact"])
        # A score can sit above the matrix (e.g. a 5-level risk after a downshift to 3x3).
        # It is still banded and counted, but flagged so renderers can skip it on the heat
        # matrix (per dashboards.md / report-layout.md) rather than re-deriving that themselves.
        out_of_range = max(r["inherent"]["likelihood"], r["inherent"]["impact"],
                           r["residual"]["likelihood"], r["residual"]["impact"]) > size
        scored_risks.append({
            **r,
            "inherentExposure": inh,
            "inherentBand": band(inh, size),
            "residualExposure": res,
            "residualBand": band(res, size),
            "overAppetite": over_appetite(res, size, appetite),
            "outOfRange": out_of_range,
        })
    esc = escalations(reg, today)
    summary = summarize(reg["risks"], size, appetite,
                        reg["settings"].get("currency") or "")
    # Added to the summary rather than replacing anything in it. `snapshot` freezes this dict
    # verbatim, so renaming an existing key would silently invalidate every historical
    # snapshot's comparability — the figures would still be there and would no longer line up.
    counts = {s: sum(1 for e in esc if e["severity"] == s)
              for s in ESCALATION_SEVERITY_ORDER}
    summary["escalations"] = {**counts, "total": len(esc)}
    summary["escalationsSuppressedProvisional"] = suppressed_provisional(reg)
    out = {
        "meta": reg["meta"],
        "settings": reg["settings"],
        "themes": reg.get("themes", []),
        "summary": summary,
        # Top-level as well as counted in the summary: the renderers consume this list and
        # must never re-derive it, on the same terms that keep banding out of the renderers.
        "escalations": esc,
        "risks": scored_risks,
    }
    # Additive by construction, exactly as `--context` is in every consumer of CAC-AP-1: the
    # key exists only when a profile was supplied, so a run without one produces the bytes it
    # always did and no renderer has to tell an empty block from an absent one.
    if context is not None:
        out["context"] = applicability_for(context)
    return out


# --- CLI ---------------------------------------------------------------------


def _cmd_score(args: list[str]) -> int:
    as_json = "--json" in args
    _, opt = parse_flags(args)
    paths = [a for a in args if not a.startswith("--")]
    if not paths:
        print("usage: score_register.py score <register.rr> [--json] [--today YYYY-MM-DD] "
              "[--context <payload.json>]", file=sys.stderr)
        return 2
    # Defaulted at the CLI boundary rather than inside score_register(), so the library
    # function stays reproducible and only the command reads the clock.
    today = _iso_date(opt["today"], "--today") if "today" in opt else _utc_today()
    context = load_context(opt["context"]) if "context" in opt else None
    scored = score_register(load_register(paths[0]), today, context)
    if as_json:
        print(json.dumps(scored, indent=2))
        return 0
    s = scored["summary"]
    m, st = scored["meta"], scored["settings"]
    print(f"Register: {m['clientName'] or '(unnamed)'}   Assessor: {m['assessor'] or '—'}")
    print(f"Matrix: {st['matrixSize']}x{st['matrixSize']}   Appetite: {st['appetite']}")
    print(f"Total: {s['total']}   Closed: {s['closed']}   Over appetite: {s['overAppetite']}")
    tc = s["treatmentCost"]
    if tc["priced"]:
        note = "" if tc["currencyRecorded"] else "   (no currency recorded in this register)"
        print(f"Recorded treatment cost (open risks): {tc['display']}   "
              f"priced: {tc['priced']}/{tc['of']}{note}")
        if tc["unpriced"]:
            print(f"  {tc['unpriced']} open risk(s) carry no recorded cost — the total above "
                  f"is a floor, not the bill.")
    print(f"Residual band mix — Low {s['byBand']['low']} · Medium {s['byBand']['medium']} · "
          f"High {s['byBand']['high']} · Critical {s['byBand']['critical']}")
    if s["provisional"]:
        print(f"\n⚠ {s['provisional']} of {s['total']} risks are PROVISIONAL:")
        if s["provisionalTitle"]:
            print(f"    {s['provisionalTitle']} still carry CSF framework wording as a title. "
                  f"Held out of every\n      board-facing view until reworded with `set-text`.")
        if s["provisionalScore"]:
            print(f"    {s['provisionalScore']} still sit on the import priority seed. "
                  f"Their scores are placeholders,\n      not assessments. Refine with `set-score`.")
    print("\nID     Residual  Band       Over  Title")
    for r in scored["risks"]:
        flag = "⚠" if r["overAppetite"] else " "
        mark = ("T" if r.get("provisionalTitle") else "") + ("S" if r.get("provisionalScore") else "")
        print(f"{r['id']:<6} {r['residualExposure']:>7}  {r['residualBand']:<9}  {flag:<4} "
              f"{mark:<2} {trunc(r['title'], 54)}")
    if s["provisional"]:
        print("\n  T = title still framework wording · S = score still the import seed")
    return 0


def _ensure_csf_themes(reg: dict) -> list[str]:
    """Define a theme for every CSF Function actually used by a risk in this register.

    Assigning `theme` on import is not enough on its own — an id with no matching theme
    definition rolls up as Unclassified, which is the state this is fixing. Only Functions
    present in the data get a theme, so a register importing three Functions does not grow
    six themes it will never use.
    """
    have = {t.get("id") for t in reg.get("themes", [])}
    used = {r.get("theme") for r in reg["risks"] if r.get("theme")}
    added = []
    for fid, name in CSF_FUNCTION_THEMES.items():
        tid = fid.lower()
        if tid in used and tid not in have:
            reg.setdefault("themes", []).append(
                {"id": tid, "name": name,
                 "description": f"CSF 2.0 {name} ({fid}) Function — assigned automatically on gap import."})
            added.append(tid)
    if added:
        _append_event(reg, "theme-changed", field="themes", to=",".join(added),
                      rationale="CSF Function themes defined automatically during gap import.")
    return added


def _cmd_import_findings(args: list[str]) -> int:
    """Take vendor-register findings as candidate risks, through the SAME merge path as gaps.

    One-way and idempotent on `sourceRef`. `vendor-register` is the system of record for the
    arrangement and what was checked about it; this register is the system of record for what
    that exposure is worth. Neither grows the other's lifecycle.
    """
    into = None
    if "--into" in args:
        into = args[args.index("--into") + 1]
    paths = [a for a in args if not a.startswith("--") and a != into]
    if not paths:
        print("usage: score_register.py import-findings <findings.json> "
              "[--into <register.rr>] [--write]\n"
              "  Previews the mapped candidates by default and writes nothing.\n"
              "  Produce the input with `vendor_register.py export-findings` or\n"
              "  `ai_register.py export-findings`.", file=sys.stderr)
        return 2
    do_write = "--write" in args
    if do_write and not into:
        print("import-findings: --write needs --into <register.rr> to write to.",
              file=sys.stderr)
        return 2
    with open(paths[0], encoding="utf-8") as fh:
        payload = json.load(fh)
    if payload.get("export") != "findings":
        print("import-findings: %s is not a findings export (export=%r). Produce it with "
              "`vendor_register.py export-findings` or `ai_register.py export-findings`."
              % (paths[0], payload.get("export")), file=sys.stderr)
        return 2
    # A scoring key reaching here means the other register started scoring, which is the one
    # thing this bridge exists to prevent. Refuse rather than quietly import a second opinion.
    banned = sorted({k for f in (payload.get("findings") or []) for k in f
                     if k.lower() in ("likelihood", "impact", "score", "band", "severity")})
    if banned:
        print("import-findings: the payload carries scoring key(s) %s. This register scores "
              "imported findings; the source register must not." % ", ".join(banned),
              file=sys.stderr)
        return 2
    existing = load_register(into)["risks"] if into else []
    candidates = [finding_to_risk(f, "R-%03d" % (i + 1))
                  for i, f in enumerate(payload.get("findings") or [])]
    result = merge_import(existing, candidates)
    if do_write and into:
        reg = load_register(into)
        reg["risks"] = result["risks"]
        _ensure_csf_themes(reg)
        _append_event(reg, "import-merged",
                      rationale="%d added, %d updated from %s findings"
                                % (result["added"], result["updated"],
                                   payload.get("family") or "an external register"))
        save_register(reg, into)
        print("Wrote %s: %d added, %d updated" % (into, result["added"], result["updated"]),
              file=sys.stderr)
        print("  Imported findings are provisional in both dimensions: the wording came from "
              "another register and nobody has scored them.\n"
              "  Titles stay out of board-facing views until reworded with `set-text`; the "
              "seeded scores are placeholders until refined with `set-score`.", file=sys.stderr)
    else:
        print(json.dumps(result, indent=2))
        tail = (" (preview only — nothing written; add --write to apply)" if into
                else " (preview only — pass --into <register.rr> --write to apply)")
        print("\n# %d added, %d updated%s" % (result["added"], result["updated"], tail),
              file=sys.stderr)
    return 0


def _cmd_import_gaps(args: list[str]) -> int:
    into = None
    if "--into" in args:
        into = args[args.index("--into") + 1]
    paths = [a for a in args if not a.startswith("--") and a != into]
    if not paths:
        print("usage: score_register.py import-gaps <gaps.csv> [--into <register.rr>] [--write]\n"
              "  Previews the mapped candidates by default and writes nothing.\n"
              "  --write applies the merge to the --into register.", file=sys.stderr)
        return 2
    do_write = "--write" in args
    if do_write and not into:
        print("import-gaps: --write needs --into <register.rr> to write to.", file=sys.stderr)
        return 2
    with open(paths[0], encoding="utf-8") as fh:
        rows = parse_gaps_csv(fh.read())
    existing = load_register(into)["risks"] if into else []
    candidates = [gap_row_to_risk(row, f"R-{i + 1:03d}") for i, row in enumerate(rows)]
    result = merge_import(existing, candidates)
    if do_write and into:
        reg = load_register(into)
        reg["risks"] = result["risks"]
        added_themes = _ensure_csf_themes(reg)
        _append_event(reg, "import-merged",
                      rationale=f"{result['added']} added, {result['updated']} updated from {os.path.basename(paths[0])}")
        save_register(reg, into)
        print(f"Wrote {into}: {result['added']} added, {result['updated']} updated", file=sys.stderr)
        if added_themes:
            print(f"  Defined {len(added_themes)} CSF Function themes so the board rollup is not "
                  f"all Unclassified: {', '.join(added_themes)}.\n"
                  f"  Re-theme with set-theme if you group risk differently.", file=sys.stderr)
        prov = sum(1 for r in reg["risks"]
                   if r.get("provisionalTitle") or r.get("provisionalScore"))
        if prov:
            print(f"  {prov} risks are provisional: CSF framework wording for a title and seeded "
                  f"scores.\n  Titles are held out of every board-facing view until reworded with "
                  f"`set-text`;\n  scores stay placeholders until refined with `set-score`.",
                  file=sys.stderr)
    else:
        print(json.dumps(result, indent=2))
        tail = " (preview only — nothing written; add --write to apply)" if into else \
               " (preview only — pass --into <register.rr> --write to apply)"
        print(f"\n# {result['added']} added, {result['updated']} updated{tail}", file=sys.stderr)
    return 0


def _cmd_self_test(_: list[str]) -> int:
    checks: list[tuple[str, Any, Any]] = []

    def eq(name, got, want):
        checks.append((name, got, want))

    def _quiet(fn, argv):
        """Run a mutating command with its console output swallowed.

        The fixture's chatter is not the suite's output: an unscoped-register warning and a
        temp path printed mid-run read like failures to anyone running self-test. Errors
        still propagate — redirect_stdout restores on the way out — so the refusal tests
        below are unaffected.
        """
        with contextlib.redirect_stdout(io.StringIO()):
            return fn(argv)

    # --- vendor findings: the one-way bridge from vendor-register ------------
    #
    # Extended through the EXISTING merge path rather than a second importer. Two merge
    # functions would be two sets of rules about when a human-authored title may be
    # overwritten, and only one of them would get the next fix.
    _finding = {
        "sourceRef": "vendor-register:VA-001:breach notice",
        "title": "Contoso Cloud: breach notice not evidenced",
        "description": "checked and recorded as not met",
        "vendor": "Contoso Cloud", "criticality": "high",
        "criticalityScaleVersion": "v1", "criticalityConfirmed": True,
        "checkedBy": "General Counsel", "checkedOn": "2026-08-08",
        "gvsc": ["GV.SC-05"],
    }
    _vr = vendor_finding_to_risk(_finding, "R-900")
    eq("a vendor finding imports provisional in BOTH dimensions",
       (_vr["provisionalTitle"], _vr["provisionalScore"]), (True, True))
    eq("...and carries no assessed magnitude, only the neutral seed",
       (_vr["inherent"], _vr["residual"]),
       ({"likelihood": 3, "impact": 3}, {"likelihood": 3, "impact": 3}))
    eq("the scale a criticality was assigned under travels with it",
       "scale v1" in (_vr["notes"] or ""), True)
    eq("and whether a person confirmed that level, or only derived it",
       "confirmed" in (_vr["notes"] or ""), True)
    # Idempotent on sourceRef, through merge_import — re-running updates rather than doubling.
    _first = merge_import([], [vendor_finding_to_risk(_finding, "R-900")])
    _again = merge_import(_first["risks"], [vendor_finding_to_risk(_finding, "R-901")])
    eq("re-importing a finding updates rather than duplicating",
       (_again["added"], _again["updated"], len(_again["risks"])), (0, 1, 1))
    eq("and the provenance key survives the update",
       _again["risks"][0].get("sourceRef"), _finding["sourceRef"])
    # A human-authored title is never overwritten by a re-import.
    _authored = [dict(_first["risks"][0], title="Loss of the CRM through a provider gap",
                      provisionalTitle=False)]
    _kept = merge_import(_authored, [vendor_finding_to_risk(_finding, "R-902")])
    eq("a reworded title survives a re-import",
       _kept["risks"][0]["title"], "Loss of the CRM through a provider gap")
    # This was `"govern" if "govern" in CSF_FUNCTION_THEMES`, whose keys are "GV", "ID", ... —
    # so every imported finding landed with no theme at all, and a theme-filtered view
    # dropped the lot in silence.
    eq("a GV.SC finding lands in the Govern theme rather than nowhere",
       (_vr["category"], _vr["theme"]), ("GV.SC", "gv"))

    # --- ai-register findings: the SAME path, not a second one ---------------
    #
    # An AI finding is the same act as a third-party one — a named person checked something
    # and recorded that it is not met — so it maps through the same function. A second mapper
    # would be a second place for the seed, the provisional flags and the no-score rule to
    # drift, and the third producer would then get a third.
    _ai = {
        "family": "ai-register",
        "sourceRef": "ai-register:D-002:monitoring.output-retention",
        "sourceDeploymentRef": "D-002",
        "title": "Contoso Assist (screening job applicants): retention not evidenced",
        "description": "checked and recorded as not met",
        "vendor": "Contoso", "autonomy": "decides", "criticality": "high",
        "criticalityScaleVersion": "v1", "criticalityConfirmed": True,
        "nistaml": ["NISTAML.02", "NISTAML.03"],
        "checkedBy": "DPO", "checkedOn": "2026-08-08",
        "gvsc": ["DE.CM-09"],
    }
    _ar = finding_to_risk(_ai, "R-910")
    eq("an AI finding imports provisional in both dimensions too",
       (_ar["provisionalTitle"], _ar["provisionalScore"]), (True, True))
    eq("...with the same neutral seed and no assessed magnitude",
       (_ar["inherent"], _ar["residual"]),
       ({"likelihood": 3, "impact": 3}, {"likelihood": 3, "impact": 3}))
    eq("a DE.CM finding lands under Detect, not under GV.SC",
       (_ar["category"], _ar["theme"]), ("DE.CM", "de"))
    eq("the deployment's autonomy travels with it",
       "Autonomy: decides" in (_ar["notes"] or ""), True)
    # The exposure classes are context on the risk, never a state. A class has no closed state
    # in `ai-register`; a risk has one, and closing the risk closes the risk.
    eq("and its exposure classes, said to be recorded where a class is never closed",
       "never closed" in (_ar["notes"] or ""), True)
    _mixed = merge_import(_first["risks"], [finding_to_risk(_ai, "R-910")])
    eq("an AI finding merges alongside a vendor one rather than colliding with it",
       (_mixed["added"], len(_mixed["risks"])), (1, 2))
    eq("and re-importing it updates rather than doubling",
       merge_import(_mixed["risks"], [finding_to_risk(_ai, "R-911")])["added"], 0)

    # exposure / band (scoring.test.ts)
    eq("exposure(4,5)", exposure(4, 5), 20)
    eq("band(4,5)", band(4, 5), "low")
    eq("band(9,5)", band(9, 5), "medium")
    eq("band(12,5)", band(12, 5), "high")
    eq("band(25,5)", band(25, 5), "critical")
    eq("band(5,5)", band(5, 5), "medium")
    eq("band(10,5)", band(10, 5), "high")
    eq("band(15,5)", band(15, 5), "critical")
    eq("band(3,4)", band(3, 4), "low")
    eq("band(4,4)", band(4, 4), "medium")
    eq("band(8,4)", band(8, 4), "high")
    eq("band(12,4)", band(12, 4), "critical")
    eq("band(2,3)", band(2, 3), "low")
    eq("band(4,3)", band(4, 3), "medium")
    eq("band(6,3)", band(6, 3), "high")
    eq("band(9,3)", band(9, 3), "critical")
    # rating labels
    eq("ratingLabel(1,5)", rating_label(1, 5), "Very Low")
    eq("ratingLabel(5,5)", rating_label(5, 5), "Very High")
    eq("ratingLabel(1,3)", rating_label(1, 3), "Low")
    eq("ratingLabel(3,3)", rating_label(3, 3), "High")
    eq("ratingLabel(1,4)", rating_label(1, 4), "Low")
    eq("ratingLabel(4,4)", rating_label(4, 4), "Very High")
    # overAppetite
    eq("overAppetite(20,5,medium)", over_appetite(20, 5, "medium"), True)
    eq("overAppetite(4,5,medium)", over_appetite(4, 5, "medium"), False)
    eq("overAppetite(9,5,medium)", over_appetite(9, 5, "medium"), False)
    eq("BAND_ORDER", BAND_ORDER, ["low", "medium", "high", "critical"])

    # summarize (summary.test.ts)
    a = {**empty_risk("R-001"), "residual": {"likelihood": 5, "impact": 5}, "status": "open"}
    b = {**empty_risk("R-002"), "residual": {"likelihood": 1, "impact": 1}, "status": "closed"}
    s = summarize([a, b], 5, "medium")
    eq("summary.total", s["total"], 2)
    eq("summary.closed", s["closed"], 1)
    eq("summary.overAppetite", s["overAppetite"], 1)
    eq("summary.byBand.critical", s["byBand"]["critical"], 1)
    eq("summary.byBand.low", s["byBand"]["low"], 1)

    # treatmentCost — the figure the register always stored and never showed.
    def _priced(rid, cost, status="open"):
        r = {**empty_risk(rid), "residual": {"likelihood": 1, "impact": 1}, "status": status}
        r["response"] = {**(r.get("response") or {}), "cost": cost}
        return r

    tc = treatment_cost([_priced("R-001", 90000), _priced("R-002", 25000)], "GBP")
    eq("treatmentCost.total", tc["total"], 115000)
    eq("treatmentCost.display", tc["display"], "GBP 115,000")
    eq("treatmentCost.priced", tc["priced"], 2)
    eq("treatmentCost.unpriced", tc["unpriced"], 0)
    # A closed risk's treatment is already paid for; counting it would overstate the ask.
    tc = treatment_cost([_priced("R-001", 90000), _priced("R-002", 25000, "closed")], "GBP")
    eq("treatmentCost excludes closed", tc["total"], 90000)
    eq("treatmentCost.of counts open only", tc["of"], 1)
    # An unpriced open risk must not vanish into the denominator.
    tc = treatment_cost([_priced("R-001", 90000), _priced("R-002", None)], "GBP")
    eq("treatmentCost.unpriced counted", tc["unpriced"], 1)
    eq("treatmentCost.priced counted", tc["priced"], 1)
    # No currency means no guessed symbol, and the caller is told which case it is.
    tc = treatment_cost([_priced("R-001", 1500)], "")
    eq("treatmentCost.display bare", tc["display"], "1,500")
    eq("treatmentCost.currencyRecorded", tc["currencyRecorded"], False)
    eq("treatmentCost.currency", tc["currency"], None)
    # `"cost": true` is an int in Python and must not score as 1.
    tc = treatment_cost([_priced("R-001", True)], "GBP")
    eq("treatmentCost ignores bool", (tc["total"], tc["priced"]), (0, 0))

    specs = [("R-001", 1, 4), ("R-002", 5, 5), ("R-003", 3, 3),
             ("R-004", 4, 5), ("R-005", 4, 4), ("R-006", 3, 4)]
    risks = [{**empty_risk(i), "residual": {"likelihood": l, "impact": im}} for i, l, im in specs]
    top = summarize(risks, 5, "medium")["topByResidual"]
    eq("topByResidual", top, ["R-002", "R-004", "R-005", "R-006", "R-003"])

    # import priority seeding + dedupe (import.test.ts semantics)
    eq("PRIORITY_SEED[critical]", PRIORITY_SEED["critical"], 5)
    eq("PRIORITY_SEED[low]", PRIORITY_SEED["low"], 2)

    # --- Age bands and the age-affirming event taxonomy ---
    eq("age_band(0,180)", age_band(0, 180), "within")
    eq("age_band(90,180) edge", age_band(90, 180), "within")
    eq("age_band(91,180)", age_band(91, 180), "approaching")
    eq("age_band(180,180) edge", age_band(180, 180), "approaching")
    eq("age_band(181,180)", age_band(181, 180), "beyond")
    eq("age_band(360,180) edge", age_band(360, 180), "beyond")
    eq("age_band(361,180)", age_band(361, 180), "wellBeyond")
    # Rescaling, shown with one fixed age against two cadences rather than one lucky
    # number: 200 days is past the line at a 180-day cadence and comfortably short of it
    # at 365. (365//2 == 182, so 200 is `approaching` there, not `within` — the floor
    # division is the thing worth pinning.)
    eq("age_band rescales at T=365", age_band(200, 365), "approaching")
    eq("age_band(200,180) for contrast", age_band(200, 180), "beyond")
    eq("age_band(182,365) floor-division edge", age_band(182, 365), "within")
    eq("AGE_BANDS", AGE_BANDS, ("within", "approaching", "beyond", "wellBeyond"))

    # Affirming means a human asserted something about the risk's magnitude or its
    # treatment decision. A note, a theme move, a status flip and a snapshot do not.
    eq("score-changed affirms", "score-changed" in AGE_AFFIRMING, True)
    eq("risk-confirmed affirms", "risk-confirmed" in AGE_AFFIRMING, True)
    eq("risk-added affirms", "risk-added" in AGE_AFFIRMING, True)
    eq("risk-accepted affirms", "risk-accepted" in AGE_AFFIRMING, True)
    eq("risk-updated does NOT affirm", "risk-updated" in AGE_AFFIRMING, False)
    eq("theme-changed does NOT affirm", "theme-changed" in AGE_AFFIRMING, False)
    eq("status-changed does NOT affirm", "status-changed" in AGE_AFFIRMING, False)
    eq("snapshot-created does NOT affirm", "snapshot-created" in AGE_AFFIRMING, False)
    eq("import-merged does NOT affirm", "import-merged" in AGE_AFFIRMING, False)
    # Totality: a new event type must be *classified*, not merely registered. The emitted
    # set is scraped from this file's own source rather than hand-listed, so adding an
    # emitting call is what breaks the suite; and the partition below means the repair has
    # to be a decision about age rather than one more name in a list.
    _emitted = _emitted_event_types()
    eq("every affirming type is a known type", AGE_AFFIRMING - KNOWN_EVENT_TYPES, set())
    eq("every type score_register can write is classified", _emitted - KNOWN_EVENT_TYPES, set())
    # ...and the scrape itself is not vacuous. Without this, a regex that matches nothing
    # makes the check above pass over an empty set — green proving nothing.
    eq("the emitted-type scrape found real calls",
       {"risk-added", "score-changed", "risk-confirmed", "status-changed"} - _emitted, set())

    # Every command either declares the flags it accepts, or is named in the shrink-only list
    # of ones not yet converted. Neither is allowed: a new command that does neither would
    # silently swallow typos, which is the defect this whole mechanism exists for.
    #
    # The undeclared list may ONLY shrink, and its size is printed below so the number is
    # visible in test output rather than buried in a constant. There is no check that it got
    # smaller — that would fail every run that changed nothing — so the pressure is the
    # printed count, which is the same pressure `ai-register`'s battery count applies.
    _declares = _flag_declaring_commands()
    eq("the flag-declaration scrape found real declarations",
       {"init", "add", "set-text", "set-escalation"} - _declares, set())
    eq("every command either declares its flags or is listed as not yet converted",
       set(COMMANDS) - _declares - _FLAGS_UNDECLARED, set())
    # ...and nothing is in both, which would let a converted command keep its exemption and
    # quietly stop rejecting.
    eq("no command is both declared and exempt", _declares & _FLAGS_UNDECLARED, set())
    # The list names only real commands — a stale entry for a deleted command would make the
    # remaining count look worse than it is and hide the next real one.
    eq("the exempt list names only real commands", _FLAGS_UNDECLARED - set(COMMANDS), set())
    # A CEILING, not an equality. Converting a command passes without touching this line;
    # adding an undeclared one fails. That is the asymmetry "may only shrink" means, and it
    # is why this is not `== len(...)` — an equality would fail the run that improved things
    # and train whoever hit it to edit the number rather than read the rule.
    eq(f"{len(_FLAGS_UNDECLARED)} of {len(COMMANDS)} commands do not yet declare their flags "
       f"(may only shrink; ceiling {_UNDECLARED_CEILING})",
       len(_FLAGS_UNDECLARED) <= _UNDECLARED_CEILING, True)
    # Both arms of the unreadable-source sentinel, by rebinding __file__ rather than by
    # trusting the comment. Nothing else in the suite notices if the UnicodeDecodeError arm
    # is removed, and then a .pyc-only install fails with a codec error nobody would ever
    # connect to event types instead of the loud sentinel this is here to produce.
    with tempfile.TemporaryDirectory() as _sd:
        _binary = os.path.join(_sd, "notsource.bin")
        with open(_binary, "wb") as _fh:
            _fh.write(b"\xf6\x00\xa4\xff not valid utf-8 \x80\x81")
        _real_file = globals()["__file__"]

        def _probe(path):
            """Scrape with __file__ pointed elsewhere, reporting a raise as a value.

            Returned rather than propagated so a missing except-arm fails this check by
            name. Left to propagate, it aborts the suite with a bare codec error and the
            tally never prints — which is how the arm this pins came to be missing.
            """
            globals()["__file__"] = path
            try:
                return _emitted_event_types()
            except Exception as exc:
                return {"<raised:" + type(exc).__name__ + ">"}

        try:
            _undecodable = _probe(_binary)                      # a .pyc-only install
            _missing = _probe(os.path.join(_sd, "absent.py"))    # a missing source
        finally:
            globals()["__file__"] = _real_file
        eq("an undecodable source yields the sentinel", _undecodable, {"<source-unreadable>"})
        eq("a missing source yields the sentinel", _missing, {"<source-unreadable>"})
        # The sentinel has to actually fail the totality check, or it is decoration.
        eq("the sentinel fails the totality check",
           bool(_undecodable - KNOWN_EVENT_TYPES), True)
        eq("the scrape recovers once the source is back",
           _emitted_event_types(), _emitted)
    # The partition. Subset-of-known alone forced registration and stopped there, which
    # left a new type non-affirming by omission — the exact default the mechanism claims to
    # prevent. Requiring the union makes registration insufficient: a type must land on one
    # side or the other, and choosing a side is the decision.
    eq("no type both affirms and does not", AGE_AFFIRMING & NON_AGE_AFFIRMING, frozenset())
    eq("every known type is classified either way",
       AGE_AFFIRMING | NON_AGE_AFFIRMING, KNOWN_EVENT_TYPES)
    eq("the two halves are non-empty",
       bool(AGE_AFFIRMING) and bool(NON_AGE_AFFIRMING), True)

    # --- confirm: "I looked at this and nothing changed" has a home ---
    eq("confirm is reachable from the CLI", "confirm" in COMMANDS, True)

    def _load(path):
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)

    def _raw(path):
        with open(path, "rb") as fh:
            return fh.read()

    def _refuses(argv):
        """True when a command refuses AND leaves the file byte-identical.

        Both halves in one helper because they are one property: a refusal that has
        already written is not a refusal. Asserting them separately is how the second
        half ends up covering only the first refusal anyone thought to test.
        """
        raw = _raw(argv[0])
        try:
            _quiet(_cmd_confirm, argv)
            return (False, raw == _raw(argv[0]))
        except ValueError:
            return (True, raw == _raw(argv[0]))

    with tempfile.TemporaryDirectory() as _d:
        _rr = os.path.join(_d, "c.rr")
        _quiet(_cmd_init, [_rr, "--client", "Fixture Co", "--assessor", "R. Calder"])
        _quiet(_cmd_add, [_rr, "--title", "Supplier concentration", "--il", "4", "--ii", "4",
                          "--rl", "3", "--ri", "4", "--why", "fixture"])
        _before = _load(_rr)
        _n_before = len(_before["history"])
        # The before-state as `confirm` itself will see it. Comparing a raw json.load
        # against a post-save file would fail on load_register's v1->v2 normalization (it
        # defaults provisionalTitle/provisionalScore, which `add` never wrote) and blame
        # `confirm` for it. Normalize both sides so the comparison can only fail on a real
        # mutation.
        _norm_before = load_register(_rr)
        _quiet(_cmd_confirm, [_rr, "R-001", "--why",
                              "reviewed at the monthly risk forum; unchanged"])
        _after = _load(_rr)
        _ev = _after["history"][-1]
        eq("confirm appends exactly one event", len(_after["history"]) - _n_before, 1)
        eq("confirm writes risk-confirmed", _ev["type"], "risk-confirmed")
        eq("confirm names the risk", _ev.get("riskId"), "R-001")
        # .get() throughout: a mutant that writes a different event shape should fail a
        # named check, not abort the whole suite with a KeyError five minutes from
        # anyone working out which assertion it was.
        eq("confirm records the rationale", _ev.get("rationale"),
           "reviewed at the monthly risk forum; unchanged")
        eq("confirm records the actor", _ev.get("actor"), "R. Calder")
        eq("confirm carries a timestamp", bool(_ev.get("ts")), True)
        # Confirming asserts nothing new about magnitude, treatment or status.
        _r_before = [r for r in _norm_before["risks"] if r["id"] == "R-001"][0]
        _r_after = [r for r in load_register(_rr)["risks"] if r["id"] == "R-001"][0]
        eq("confirm changes no score", _r_after["residual"], _r_before["residual"])
        eq("confirm changes no status", _r_after["status"], _r_before["status"])
        eq("confirm changes no response", _r_after["response"], _r_before["response"])
        # The three above name three fields. This one holds the line: without --review,
        # `confirm` may change *nothing* on the risk, so a future version that quietly
        # edits owner, priority or a field invented next year is caught here.
        eq("confirm changes nothing whatsoever on the risk", _r_after, _r_before)
        # ...and the same again one level up. The risk object is not the only thing a
        # register holds: appetite and matrixSize drive every over-appetite flag and the
        # board headline, and a confirm that edited settings would sail past a
        # risk-only comparison. history and updatedAt are the two things confirm is
        # supposed to move.
        def _reg_key(g):
            return {k: v for k, v in g.items() if k not in ("history", "updatedAt")}

        eq("confirm changes nothing else in the register",
           _reg_key(load_register(_rr)), _reg_key(_norm_before))

        # Each refusal must both refuse and leave the file byte-identical, asserted as one
        # pair at every site: a refusal that has already written is not a refusal.
        eq("confirm without --why is refused, leaving the register untouched",
           _refuses([_rr, "R-001"]), (True, True))
        # A bare --review is a typo, not a request for a default: silently dropping it
        # sends a reviewer out of the meeting believing the next review is booked.
        eq("a bare --review is refused, writing nothing",
           _refuses([_rr, "R-001", "--why", "still stands", "--review"]), (True, True))
        eq("a non-ISO --review is refused, writing nothing",
           _refuses([_rr, "R-001", "--why", "still stands", "--review", "31/01/2027"]),
           (True, True))
        # An unpadded date is the dangerous one: strptime accepted `2027-2-01`, stored it,
        # and _overdue's lexical compare then read an overdue review as on time.
        eq("an unpadded --review is refused, writing nothing",
           _refuses([_rr, "R-001", "--why", "still stands", "--review", "2027-2-01"]),
           (True, True))
        # Every site below asserts the pair, never just the refusal half. _refuses() makes
        # the two halves impossible to drift apart in construction, but a caller can still
        # drop one — and a refusal copied from a half-asserted site inherits the gap.
        # The basic form is rejected too, so the flag means one thing on 3.9 and on 3.11+.
        eq("a basic-form --review is refused, writing nothing",
           _refuses([_rr, "R-001", "--why", "x", "--review", "20270201"]), (True, True))
        # A flag given twice used to keep the last value silently.
        eq("a repeated --review is refused, writing nothing",
           _refuses([_rr, "R-001", "--why", "a", "--review", "2027-01-31",
                     "--review", "2027-02-28"]), (True, True))
        eq("a repeated --why is refused, writing nothing",
           _refuses([_rr, "R-001", "--why", "a", "--why", "b"]), (True, True))
        # An unknown risk id is an error, not a silently-created risk.
        eq("confirm on an unknown id is refused, writing nothing",
           _refuses([_rr, "R-999", "--why", "t"]), (True, True))

        # --review sets the next review date in the same breath as the confirmation,
        # because that is the actual review-meeting workflow.
        _quiet(_cmd_confirm, [_rr, "R-001", "--why", "forum re-affirmed",
                              "--review", "2027-01-31"])
        _r3 = [r for r in _load(_rr)["risks"] if r["id"] == "R-001"][0]
        eq("--review sets the next review date", _r3.get("reviewDate"), "2027-01-31")
        # reviewDate is the one field --review is licensed to write. Nothing else may move.
        eq("--review changes nothing but reviewDate",
           {k: v for k, v in _r3.items() if k != "reviewDate"},
           {k: v for k, v in _r_after.items() if k != "reviewDate"})

        # Confirming a *closed* risk is allowed on purpose — see the note in _cmd_confirm.
        # "We re-checked this closed risk and it stays closed" is a claim reviewers make
        # and ask about, and refusing it would push people to reopen a risk to record it.
        _quiet(_cmd_set_status, [_rr, "R-001", "closed", "--why", "treatment complete"])
        _quiet(_cmd_confirm, [_rr, "R-001", "--why", "re-checked; stays closed"])
        _closed = _load(_rr)
        eq("confirm works on a closed risk", _closed["history"][-1]["type"], "risk-confirmed")
        eq("confirming a closed risk does not reopen it",
           [r for r in _closed["risks"] if r["id"] == "R-001"][0]["status"], "closed")

    # A provisional score is the importer's seed off a CSF gap priority — nobody has
    # assessed it. risk-confirmed affirms age, so confirming here would reset confirmation
    # age on a number no human ever reviewed and feed a board freshness figure with it.
    with tempfile.TemporaryDirectory() as _d2:
        _pr = os.path.join(_d2, "p.rr")
        _quiet(_cmd_init, [_pr, "--client", "Fixture Co", "--assessor", "R. Calder"])
        _quiet(_cmd_add, [_pr, "--title", "PR.AA-05 partially implemented", "--il", "4",
                          "--ii", "4", "--rl", "4", "--ri", "4", "--why", "imported"])
        _p = load_register(_pr)
        _p["risks"][0]["provisionalTitle"] = True
        _p["risks"][0]["provisionalScore"] = True
        save_register(_p, _pr)
        _praw = _raw(_pr)
        try:
            _quiet(_cmd_confirm, [_pr, "R-001", "--why", "looks fine"])
            _prov = False
        except ValueError:
            _prov = True
        eq("confirm refuses a provisional score", _prov, True)
        eq("a refused provisional confirm writes nothing", _raw(_pr), _praw)
        # Clearing the score flag the honest way — set-score, which records a rationale —
        # makes it confirmable. A provisional *title* only warns: wording is a
        # board-eligibility question, not a magnitude one.
        _quiet(_cmd_set_score, [_pr, "R-001", "--residual", "4", "4",
                                "--why", "assessed; seed value was right"])
        # Caught rather than called bare: an over-strict confirm that also refused a
        # provisional *title* would otherwise abort the whole suite with an unnamed error
        # instead of failing this one check by name.
        try:
            _quiet(_cmd_confirm, [_pr, "R-001", "--why", "re-affirmed at the forum"])
            _title_warns = True
        except ValueError:
            _title_warns = False
        eq("a provisional title only warns, it does not refuse", _title_warns, True)
        eq("...and the confirmation was recorded",
           _load(_pr)["history"][-1]["type"], "risk-confirmed")
        eq("confirming leaves the provisional title flag alone",
           [r for r in _load(_pr)["risks"] if r["id"] == "R-001"][0].get("provisionalTitle"),
           True)

    # --- The invariant: no affirming event may attach to a provisional-score risk ---
    #
    # Asserted over the writer set derived from this file's own source, not over the two
    # instances we happened to think of. `confirm` was fixed first and `accept` was found
    # open afterwards through the adjacent door; the point of deriving the set is that a
    # fifth affirming writer has to face the question instead of inheriting the gap.
    _writers = _affirming_writers()
    # _cmd_add is exempt by construction: it *creates* the risk and never sets the
    # provisional flags, so there is no pre-existing provisional risk for it to affirm.
    # Every other affirming writer takes an existing id and is probed below.
    _probes = {
        "_cmd_confirm": (_cmd_confirm, ["R-001", "--why", "still stands"], "refuses"),
        "_cmd_accept": (_cmd_accept, ["R-001", "--approver", "Audit Committee",
                                      "--justification", "board tolerates it",
                                      "--revalidate", "2027-01-31"], "refuses"),
        # set-score is the sanctioned way through rather than an exception to the rule: it
        # affirms *and* clears provisionalScore, so the score it affirms has been assessed.
        "_cmd_set_score": (_cmd_set_score, ["R-001", "--residual", "4", "4",
                                            "--why", "assessed at the forum"], "clears"),
    }
    eq("every affirming writer is either probed or exempt with a reason",
       set(_probes) | {"_cmd_add"}, _writers)
    for _name in sorted(_probes):
        _fn, _tail, _expected = _probes[_name]
        with tempfile.TemporaryDirectory() as _id:
            _ir = os.path.join(_id, "i.rr")
            _quiet(_cmd_init, [_ir, "--client", "Fixture Co", "--assessor", "R. Calder"])
            _quiet(_cmd_add, [_ir, "--title", "PR.AA-05 partially implemented", "--il", "4",
                              "--ii", "4", "--rl", "4", "--ri", "4", "--why", "imported"])
            _ip = load_register(_ir)
            _ip["risks"][0]["provisionalScore"] = True
            save_register(_ip, _ir)
            _iraw = _raw(_ir)
            try:
                _quiet(_fn, [_ir] + _tail)
                _refused = False
            except ValueError:
                _refused = True
            _after_risk = [r for r in load_register(_ir)["risks"] if r["id"] == "R-001"][0]
            _still = bool(_after_risk.get("provisionalScore"))
            # The invariant, stated once and applied to every writer: either the command
            # refused and wrote nothing, or the score it affirmed is no longer a seed.
            eq(f"invariant — {_name} cannot affirm a provisional score",
               (_refused and _raw(_ir) == _iraw) or not _still, True)
            # ...and which branch held is pinned too, so "refuses" cannot silently become
            # "clears" (or vice versa) while the invariant above stays green.
            eq(f"{_name} takes the {_expected} branch",
               "refuses" if _refused else ("clears" if not _still else "neither"),
               _expected)

    # The same date validation on every flag that writes a lexically-compared date.
    with tempfile.TemporaryDirectory() as _d3:
        _dr = os.path.join(_d3, "d.rr")
        _quiet(_cmd_init, [_dr, "--client", "Fixture Co", "--assessor", "R. Calder"])

        def _rejects(fn, argv):
            raw = _raw(argv[0])
            try:
                _quiet(fn, argv)
                return (False, raw == _raw(argv[0]))
            except ValueError:
                return (True, raw == _raw(argv[0]))

        _add = [_dr, "--title", "T", "--il", "2", "--ii", "2", "--rl", "2", "--ri", "2",
                "--why", "w"]
        eq("add --review rejects an unpadded date",
           _rejects(_cmd_add, _add + ["--review", "2027-2-01"]), (True, True))
        _quiet(_cmd_add, _add + ["--review", "2027-02-01"])
        eq("add --review keeps a canonical date",
           [r for r in _load(_dr)["risks"] if r["id"] == "R-001"][0]["reviewDate"],
           "2027-02-01")
        _acc = [_dr, "R-001", "--approver", "CFO", "--justification", "j"]
        eq("accept --revalidate rejects an unpadded date",
           _rejects(_cmd_accept, _acc + ["--revalidate", "2027-2-01"]), (True, True))
        eq("accept --expiry rejects an unpadded date",
           _rejects(_cmd_accept, _acc + ["--revalidate", "2027-02-01",
                                         "--expiry", "2027-6-30"]), (True, True))
        _quiet(_cmd_accept, _acc + ["--revalidate", "2027-02-01", "--expiry", "2027-06-30"])
        _acceptance = [r for r in _load(_dr)["risks"] if r["id"] == "R-001"][0]["acceptance"]
        eq("accept stores canonical dates",
           (_acceptance["revalidationDate"], _acceptance["expiryDate"]),
           ("2027-02-01", "2027-06-30"))
        # The defect in one line: the date the old code stored reads as NOT overdue
        # against a later today, because the comparison downstream is lexical.
        eq("an unpadded date would have inverted the overdue compare",
           ("2027-2-01"[:10] <= "2027-11-01", "2027-02-01"[:10] <= "2027-11-01"),
           (False, True))

        # --- set-escalation (T2) ------------------------------------------------
        eq("set-escalation is reachable from COMMANDS",
           COMMANDS.get("set-escalation") is _cmd_set_escalation, True)
        eq("escalation-policy-changed is a known type",
           "escalation-policy-changed" in KNOWN_EVENT_TYPES, True)
        eq("escalation-policy-changed is classified exactly once",
           (("escalation-policy-changed" in AGE_AFFIRMING),
            ("escalation-policy-changed" in NON_AGE_AFFIRMING)),
           (False, True))
        # Refuses without --why, and leaves the file byte-identical when it does.
        eq("set-escalation refuses without --why",
           _rejects(_cmd_set_escalation, [_dr, "--sustained", "3"]), (True, True))
        eq("set-escalation refuses --sustained 0",
           _rejects(_cmd_set_escalation, [_dr, "--sustained", "0", "--why", "w"]),
           (True, True))
        eq("set-escalation refuses a no-op",
           _rejects(_cmd_set_escalation, [_dr, "--sustained", "2", "--why", "w"]),
           (True, True))
        eq("set-escalation refuses a non on/off boolean",
           _rejects(_cmd_set_escalation, [_dr, "--band-cross", "false", "--why", "w"]),
           (True, True))
        # And the accepted path: one threshold moves, the other three hold.
        _quiet(_cmd_set_escalation, [_dr, "--dwell-days", "90", "--why", "tighter cadence"])
        eq("set-escalation moves only what was passed",
           _load(_dr)["settings"]["escalation"],
           {"sustainedWorseningSnapshots": 2, "appetiteDwellDays": 90,
            "bandCross": True, "lapsedAcceptance": True})
        eq("and logs the policy change with its rationale",
           [(e["type"], e.get("rationale")) for e in _load(_dr)["history"]][-1],
           ("escalation-policy-changed", "tighter cadence"))

        # --- unknown flags fail loudly (BL-104) ---------------------------------
        # The parser used to collect an unrecognised flag into `opt` and let every command
        # ignore it, so `init --currency GBP` exited 0 and wrote nothing. Both directions:
        # the typo is refused AND the file is untouched, because a refusal that had already
        # half-written the register would be worse than the silence it replaced.
        eq("a typo'd flag is refused and nothing is written",
           _rejects(_cmd_add, [_dr, "--title", "T", "--il", "2", "--ii", "2", "--rl", "2",
                               "--ri", "2", "--ownr", "X"]), (True, True))
        eq("...and the correctly spelled flag still works",
           _rejects(_cmd_add, [_dr, "--title", "T", "--il", "2", "--ii", "2", "--rl", "2",
                               "--ri", "2", "--owner", "X"]), (False, False))
        def _why_refused(fn, argv):
            try:
                _quiet(fn, argv)
            except ValueError as exc:
                return str(exc)
            return ""
        # A refusal a reader cannot act on is a refusal they work around. It has to name the
        # flag they typed AND one they could have meant.
        eq("the refusal names the flag and lists what is accepted",
           all(s in _why_refused(_cmd_add,
                                 [_dr, "--title", "T", "--il", "2", "--ii", "2", "--rl", "2",
                                  "--ri", "2", "--ownr", "X"])
               for s in ("--ownr", "--owner", "Nothing was written")), True)

        # --- cost validation (BL-105) -------------------------------------------
        eq("--cost refuses a negative", _rejects(_cmd_add, _add + ["--cost", "-5000"]),
           (True, True))
        eq("--cost refuses a non-integer", _rejects(_cmd_add, _add + ["--cost", "45,000"]),
           (True, True))
        eq("--cost refuses a bare flag", _rejects(_cmd_add, _add + ["--cost"]), (True, True))
        # Zero is a real answer — priced, and the answer is nothing — and it must survive
        # both the write and the round trip, because the renderer distinguishes it from absent.
        _quiet(_cmd_add, _add + ["--cost", "0", "--title", "Zero-cost"])
        eq("...and ACCEPTS zero, which round-trips as 0 rather than vanishing",
           _load(_dr)["risks"][-1]["response"].get("cost"), 0)

        # --- set-response, the correction path (BL-105) --------------------------
        eq("set-response is reachable from COMMANDS",
           COMMANDS.get("set-response") is _cmd_set_response, True)
        eq("response-changed is classified exactly once",
           (("response-changed" in AGE_AFFIRMING), ("response-changed" in NON_AGE_AFFIRMING)),
           (False, True))
        _rid = _load(_dr)["risks"][-1]["id"]
        eq("set-response refuses without --why",
           _rejects(_cmd_set_response, [_dr, _rid, "--cost", "10"]), (True, True))
        eq("set-response refuses a no-op",
           _rejects(_cmd_set_response, [_dr, _rid, "--cost", "0", "--why", "w"]), (True, True))
        eq("set-response refuses an unknown response type",
           _rejects(_cmd_set_response, [_dr, _rid, "--type", "ignore", "--why", "w"]),
           (True, True))
        eq("set-response refuses a negative, through the same helper as add",
           _rejects(_cmd_set_response, [_dr, _rid, "--cost", "-1", "--why", "w"]), (True, True))
        _quiet(_cmd_set_response, [_dr, _rid, "--cost", "45000", "--why", "typo at entry"])
        eq("a cost entered wrongly is correctable",
           _load(_dr)["risks"][-1]["response"]["cost"], 45000)
        eq("...and the correction lands in history with both ends and its rationale",
           [(e["type"], e["from"].get("cost"), e["to"].get("cost"), e.get("rationale"))
            for e in _load(_dr)["history"] if e["type"] == "response-changed"][-1],
           ("response-changed", 0, 45000, "typo at entry"))

        # --- set-currency (BL-103) -----------------------------------------------
        eq("set-currency is reachable from COMMANDS",
           COMMANDS.get("set-currency") is _cmd_set_currency, True)
        eq("settings-changed is classified exactly once",
           (("settings-changed" in AGE_AFFIRMING), ("settings-changed" in NON_AGE_AFFIRMING)),
           (False, True))
        eq("set-currency refuses without --why",
           _rejects(_cmd_set_currency, [_dr, "--currency", "GBP"]), (True, True))
        eq("set-currency refuses a bare --currency",
           _rejects(_cmd_set_currency, [_dr, "--currency", "--why", "w"]), (True, True))
        _quiet(_cmd_set_currency, [_dr, "--currency", "GBP", "--why", "group reports in GBP"])
        eq("set-currency records the code", _load(_dr)["settings"]["currency"], "GBP")
        eq("...and refuses the same value a second time",
           _rejects(_cmd_set_currency, [_dr, "--currency", "GBP", "--why", "w"]), (True, True))
        # Relabels, never converts: the amount recorded above is untouched by the change.
        eq("changing the currency does NOT convert recorded amounts",
           _load(_dr)["risks"][-1]["response"]["cost"], 45000)
        eq("and the total now renders with the currency",
           summarize(_load(_dr)["risks"], 5, "medium",
                     _load(_dr)["settings"]["currency"])["treatmentCost"]["currencyRecorded"],
           True)

    # --- escalation derivation (T3/T4/T5) -------------------------------------
    # Built by hand rather than by driving the CLI, so each trigger can be isolated. A
    # fixture that fires three triggers at once cannot show which one a check is proving.

    def _risk(rid, rl, ri, **kw):
        r = {"id": rid, "title": rid, "description": "", "category": "PR", "theme": None,
             "owner": "o", "inherent": {"likelihood": 5, "impact": 5},
             "response": {"type": "mitigate", "description": ""},
             "residual": {"likelihood": rl, "impact": ri}, "status": "open",
             "reviewDate": "", "acceptance": None, "provisionalTitle": False,
             "provisionalScore": False}
        r.update(kw)
        return r

    def _reg(risks, snaps=(), **settings):
        return {"schemaVersion": 2, "meta": {},
                "settings": {"matrixSize": 5, "appetite": "medium",
                             "escalation": {**ESCALATION_DEFAULTS, **settings}},
                "themes": [], "risks": risks, "history": [], "snapshots": list(snaps)}

    def _snap(ts, label, risks, size=5, appetite="medium"):
        return {"id": label.lower(), "label": label, "ts": ts, "note": "",
                "data": {"settings": {"matrixSize": size, "appetite": appetite},
                         "risks": risks, "summary": {}}}

    # T3 — the baseline helper.
    eq("no snapshots yields an empty baseline",
       _snapshot_baseline(_reg([_risk("R-001", 2, 2)])), ({}, ""))
    _two = _reg([_risk("R-001", 3, 3)],
                [_snap("2026-01-31T00:00:00Z", "Q1", [_risk("R-001", 1, 2)]),
                 _snap("2026-06-30T00:00:00Z", "Q2", [_risk("R-001", 2, 2)])])
    eq("the baseline is the newest snapshot, by insertion order",
       _snapshot_baseline(_two), ({"R-001": 4}, "Q2"))
    # Append order is the truth, not the timestamp. Two machines with skewed clocks writing
    # to one register must not silently reorder what the whole engine compares against, so
    # the last-appended snapshot wins even when its `ts` is the earlier of the two.
    eq("a skewed clock does not reorder the baseline",
       _snapshot_baseline(_reg(
           [_risk("R-001", 3, 3)],
           [_snap("2026-06-30T00:00:00Z", "later ts, appended first",
                  [_risk("R-001", 1, 1)]),
            _snap("2026-01-31T00:00:00Z", "earlier ts, appended last",
                  [_risk("R-001", 2, 2)])])),
       ({"R-001": 4}, "earlier ts, appended last"))

    # T4 — velocity, all four cases.
    _vel = velocity(_reg(
        [_risk("R-001", 3, 3), _risk("R-002", 1, 1), _risk("R-003", 2, 2),
         _risk("R-004", 4, 4)],
        [_snap("2026-06-30T00:00:00Z", "Q2",
               [_risk("R-001", 2, 2), _risk("R-002", 3, 3), _risk("R-003", 2, 2)])]))
    eq("velocity: worsening", (_vel["R-001"]["direction"], _vel["R-001"]["delta"]),
       ("worsening", 5))
    eq("velocity: improving", (_vel["R-002"]["direction"], _vel["R-002"]["delta"]),
       ("improving", -8))
    eq("velocity: steady", (_vel["R-003"]["direction"], _vel["R-003"]["delta"]),
       ("steady", 0))
    eq("velocity: a risk the baseline never had is steady, not worsening",
       (_vel["R-004"]["direction"], _vel["R-004"]["delta"], _vel["R-004"]["baseline"]),
       ("steady", 0, ""))

    # T5 — band-crossed.
    _bc = escalations(_reg(
        [_risk("R-001", 3, 4)],                                    # 12 -> high
        [_snap("2026-06-30T00:00:00Z", "Q2", [_risk("R-001", 3, 3)])]),  # 9 -> medium
        today="2026-07-31")
    eq("band-crossed fires on medium -> high",
       [(e["trigger"], e["severity"]) for e in _bc], [("band-crossed", "high")])
    eq("band-crossed to critical is critical",
       [e["severity"] for e in escalations(_reg(
           [_risk("R-001", 5, 5)],
           [_snap("2026-06-30T00:00:00Z", "Q2", [_risk("R-001", 3, 3)])]),
           today="2026-07-31") if e["trigger"] == "band-crossed"], ["critical"])
    eq("band-crossed does NOT fire on high -> medium",
       [e["trigger"] for e in escalations(_reg(
           [_risk("R-001", 3, 3)],
           [_snap("2026-06-30T00:00:00Z", "Q2", [_risk("R-001", 3, 4)])]),
           today="2026-07-31")], [])
    eq("bandCross off suppresses it",
       escalations(_reg([_risk("R-001", 3, 4)],
                        [_snap("2026-06-30T00:00:00Z", "Q2", [_risk("R-001", 3, 3)])],
                        bandCross=False), today="2026-07-31"), [])

    # T5 — sustained-drift fires at exactly N, not N-1. Two snapshots plus the current
    # value is two transitions; one snapshot plus current is one.
    _drift_snaps = [_snap("2026-01-31T00:00:00Z", "Q1", [_risk("R-001", 1, 5)]),   # 5
                    _snap("2026-06-30T00:00:00Z", "Q2", [_risk("R-001", 1, 6)])]   # 6
    eq("sustained-drift fires at exactly N=2",
       [(e["trigger"], e["severity"]) for e in
        escalations(_reg([_risk("R-001", 1, 7)], _drift_snaps), today="2026-07-31")],
       [("sustained-drift", "medium")])
    eq("sustained-drift does not fire at N-1",
       [e["trigger"] for e in escalations(
           _reg([_risk("R-001", 1, 7)], _drift_snaps[1:]), today="2026-07-31")], [])
    eq("a raised N stops it firing",
       [e["trigger"] for e in escalations(
           _reg([_risk("R-001", 1, 7)], _drift_snaps, sustainedWorseningSnapshots=3),
           today="2026-07-31")], [])

    # T5 — a crossed band suppresses drift on the same risk: one story, told once.
    _both = escalations(_reg(
        [_risk("R-001", 2, 5)],                                     # 10 -> high
        [_snap("2026-01-31T00:00:00Z", "Q1", [_risk("R-001", 1, 6)]),   # 6  medium
         _snap("2026-06-30T00:00:00Z", "Q2", [_risk("R-001", 1, 8)])]), # 8  medium
        today="2026-07-31")
    eq("band-crossed suppresses sustained-drift on the same risk",
       [e["trigger"] for e in _both], ["band-crossed"])

    # T5 — appetite-dwell, and that the threshold is respected.
    _dwell_snaps = [_snap("2026-01-01T00:00:00Z", "Q1", [_risk("R-001", 3, 4)]),
                    _snap("2026-06-30T00:00:00Z", "Q2", [_risk("R-001", 3, 4)])]
    eq("appetite-dwell fires past the threshold",
       [(e["trigger"], e["severity"]) for e in escalations(
           _reg([_risk("R-001", 3, 4)], _dwell_snaps), today="2026-07-31")
        if e["trigger"] == "appetite-dwell"], [("appetite-dwell", "high")])
    eq("appetite-dwell respects a raised appetiteDwellDays",
       [e["trigger"] for e in escalations(
           _reg([_risk("R-001", 3, 4)], _dwell_snaps, appetiteDwellDays=3650),
           today="2026-07-31") if e["trigger"] == "appetite-dwell"], [])

    # T5 — acceptance-lapsed fires on a closed risk, which is the point of it.
    _acc = {"approver": "CFO", "justification": "j", "acceptedDate": "2025-01-01",
            "revalidationDate": "2025-06-01", "expiryDate": "2026-01-01"}
    eq("acceptance-lapsed fires on a closed risk",
       [(e["subjectRef"], e["trigger"]) for e in escalations(
           _reg([_risk("R-001", 1, 1, status="closed", acceptance=_acc)]),
           today="2026-07-31")], [("R-001", "acceptance-lapsed")])
    # The boundary, pinned deliberately. renderers/_common.py::_overdue is `<=`, so an
    # acceptance expiring *today* already shows as expired on both dashboards. A stricter
    # `<` here would make the escalation disagree with that flag for exactly one day per
    # acceptance — one concept answered two ways, which is the divergence this engine
    # exists to close rather than create.
    eq("an acceptance expiring today is already lapsed, as the dashboards read it",
       [e["trigger"] for e in escalations(
           _reg([_risk("R-001", 1, 1, acceptance={**_acc, "expiryDate": "2026-07-31"})]),
           today="2026-07-31")], ["acceptance-lapsed"])
    eq("an unexpired acceptance does not fire",
       escalations(_reg([_risk("R-001", 1, 1, acceptance={**_acc,
                                                          "expiryDate": "2027-01-01"})]),
                   today="2026-07-31"), [])
    eq("lapsedAcceptance off suppresses it",
       escalations(_reg([_risk("R-001", 1, 1, acceptance=_acc)], lapsedAcceptance=False),
                   today="2026-07-31"), [])

    # T5 — a provisional score escalates nothing, and says so rather than going quiet.
    _prov = _reg([_risk("R-001", 3, 4, provisionalScore=True)],
                 [_snap("2026-06-30T00:00:00Z", "Q2", [_risk("R-001", 3, 3)])])
    eq("a provisionalScore risk produces no score-derived escalation",
       escalations(_prov, today="2026-07-31"), [])
    eq("and is counted as suppressed instead of vanishing",
       suppressed_provisional(_prov), 1)

    # T5 — no snapshots, no score-derived escalation. A first run escalates nothing.
    eq("a register with no snapshots escalates nothing from scores",
       escalations(_reg([_risk("R-001", 5, 5)]), today="2026-07-31"), [])

    # T5 — the §1.3 shape, on a real record.
    _shape = escalations(_reg([_risk("R-001", 3, 4)],
                              [_snap("2026-06-30T00:00:00Z", "Q2", [_risk("R-001", 3, 3)])]),
                         today="2026-07-31")[0]
    eq("every escalation carries the six contract keys",
       sorted(_shape), ["evidence", "severity", "since", "subjectKind", "subjectRef",
                        "trigger"])
    eq("and its evidence names the comparison that fired it",
       sorted(_shape["evidence"]), ["baseline", "detail", "from", "to"])
    eq("subjectKind is risk", _shape["subjectKind"], "risk")

    # T5 — severity ordering is stable, so a rendered list does not reshuffle between runs.
    _mixed = escalations(_reg(
        [_risk("R-003", 3, 4), _risk("R-001", 1, 1, acceptance=_acc),
         _risk("R-002", 5, 5)],
        [_snap("2026-06-30T00:00:00Z", "Q2",
               [_risk("R-003", 3, 3), _risk("R-002", 3, 3)])]), today="2026-07-31")
    eq("escalations sort by severity, then by subject",
       [(e["severity"], e["subjectRef"]) for e in _mixed],
       [("critical", "R-002"), ("high", "R-001"), ("high", "R-003")])

    # T6 — the scored payload carries escalations, and the summary counts agree with the
    # list they count. Two numbers for one thing is how they come to disagree; asserting
    # they match is what stops a renderer picking the wrong one.
    _wired = score_register(_reg(
        [_risk("R-001", 3, 4), _risk("R-002", 5, 5), _risk("R-003", 1, 1,
                                                           provisionalScore=True)],
        [_snap("2026-06-30T00:00:00Z", "Q2",
               [_risk("R-001", 3, 3), _risk("R-002", 3, 3), _risk("R-003", 1, 1)])]),
        today="2026-07-31")
    eq("score_register carries the escalation list", len(_wired["escalations"]), 2)
    eq("and the summary counts match it exactly",
       _wired["summary"]["escalations"],
       {"critical": 1, "high": 1, "medium": 0, "total": 2})
    eq("and the suppressed count travels with them",
       _wired["summary"]["escalationsSuppressedProvisional"], 1)
    eq("every pre-existing summary key survives",
       all(k in _wired["summary"] for k in
           ("total", "closed", "overAppetite", "byBand", "topByResidual", "provisional",
            "provisionalTitle", "provisionalScore", "treatmentCost")), True)
    eq("scoring without a reference date still returns a list, just a shorter one",
       isinstance(score_register(_reg([_risk("R-001", 1, 1)]))["escalations"], list), True)

    # T5 — an empty `today` skips the two date-derived triggers rather than guessing.
    eq("no reference date skips the date-derived triggers",
       [e["trigger"] for e in escalations(
           _reg([_risk("R-001", 3, 4, acceptance=_acc)],
                [_snap("2026-06-30T00:00:00Z", "Q2", [_risk("R-001", 3, 3)])]))],
       ["band-crossed"])

    # T13 — the magnitude the acceptance bridge exports.
    #
    # `exceptions-register` refuses to re-validate against a magnitude measured before its
    # last review, which makes `measuredAt` load-bearing on the far side of a skill
    # boundary: get it wrong here and a stale number renews cleanly over there.
    def _hist(rid, etype, ts):
        return {"riskId": rid, "type": etype, "ts": ts, "actor": "t"}

    _h = _reg([_risk("R-001", 2, 2)])
    eq("no history means no measurement date, rather than a guessed one",
       _last_affirmed(_h, "R-001"), None)
    _h["history"] = [_hist("R-001", "risk-added", "2026-01-05T00:00:00Z"),
                     _hist("R-001", "score-changed", "2026-04-02T00:00:00Z"),
                     _hist("R-001", "risk-updated", "2026-06-01T00:00:00Z")]
    eq("the latest AFFIRMING event dates the measurement",
       _last_affirmed(_h, "R-001"), "2026-04-02")
    eq("a non-affirming event does not date it — risk-updated is the later one here",
       "risk-updated" in AGE_AFFIRMING, False)
    _h["history"].append(_hist("R-002", "score-changed", "2026-09-09T00:00:00Z"))
    eq("another risk's affirmation does not date this one",
       _last_affirmed(_h, "R-001"), "2026-04-02")
    _h["history"].append(_hist("R-001", "score-changed", "not-a-timestamp"))
    eq("an unreadable ts is skipped, never coerced into a measurement date",
       _last_affirmed(_h, "R-001"), "2026-04-02")
    _only_bad = _reg([_risk("R-001", 2, 2)])
    _only_bad["history"] = [_hist("R-001", "score-changed", "not-a-timestamp")]
    eq("and when every affirmation is unreadable the date is None, not a fabrication",
       _last_affirmed(_only_bad, "R-001"), None)

    # The row itself, end to end through the command. Both defects this section was written
    # after — a NameError on a regex this module does not define, and reading a scored field
    # off a RAW register risk — were invisible to every check above and surfaced only by
    # running the command. So it is run.
    _acc_full = {"approver": "CISO", "justification": "within appetite",
                 "acceptedDate": "2026-02-01", "revalidationDate": "2027-02-01",
                 "expiryDate": "2027-06-01"}
    _breg = _reg([_risk("R-001", 2, 3, response={"type": "accept", "description": ""},
                        acceptance=_acc_full)])
    _breg["history"] = [_hist("R-001", "score-changed", "2026-03-04T00:00:00Z")]
    with tempfile.TemporaryDirectory() as _bd:
        _bridge, _out = os.path.join(_bd, "bridge.rr"), os.path.join(_bd, "bridge.json")
        with open(_bridge, "w", encoding="utf-8") as fh:
            json.dump(_breg, fh)
        # Redirected: this command reports what it wrote, and a self-test that prints a
        # temp path in the middle of its own results reads like a failure.
        _buf = io.StringIO()
        with contextlib.redirect_stdout(_buf):
            _cmd_export_acceptances([_bridge, "--out", _out])
        with open(_out, encoding="utf-8") as fh:
            _rows = json.load(fh)
    eq("the bridge exports the accepted risk", len(_rows), 1)
    eq("with the magnitude it was accepted against, computed not read",
       _rows[0]["magnitude"],
       {"value": 6, "unit": "residual exposure", "band": "medium",
        "measuredAt": "2026-03-04", "source": "risk-register"})
    eq("and the exported value is exposure() over the residual pair, not a stored field",
       _rows[0]["magnitude"]["value"], exposure(2, 3))

    failures = [(n, g, w) for (n, g, w) in checks if g != w]
    for n, g, w in checks:
        status = "ok " if (g == w) else "FAIL"
        if g != w:
            print(f"[{status}] {n}: got {g!r} want {w!r}")
    print(f"\n{len(checks) - len(failures)}/{len(checks)} checks passed.")
    if failures:
        print(f"{len(failures)} FAILED — engine does NOT match the web tool.", file=sys.stderr)
        return 1
    print("Parity confirmed: scoring matches the Cyber Aware Creations web engine.")
    return 0


# --- Persistence (write-back, append-only history, snapshots) ----------------

STATUSES = {"open", "in-treatment", "monitoring", "closed"}
RESPONSES = {"accept", "transfer", "mitigate", "avoid"}

# --- Age bands and the age-affirming event taxonomy ---------------------------
# The twin of skills/nist-csf/scripts/profile_analysis.py's age_band(), and that file
# carries the matching note pointing here. Deliberately duplicated: the obvious cleanup —
# one shared module, say skills/_shared/age.py — is rejected because every shipped script
# must run standalone, so a cross-skill import needs sys.path surgery and breaks outright
# the moment a single skill directory is used on its own. The obligation that replaces it:
# the two copies are edited together, and each skill's own self-test is the only thing
# pinning them to the same semantics. Grep the sibling path above before moving a boundary.
#
#   within       d <= T//2
#   approaching  d <= T
#   beyond       d <= 2T
#   wellBeyond   d >  2T
AGE_BANDS = ("within", "approaching", "beyond", "wellBeyond")


def age_band(days: int, threshold_days: int) -> str:
    """Which band `days` of age falls in, relative to threshold `threshold_days`.

    Boundaries are inclusive of the lower band: at exactly T a determination is
    `approaching`, not yet `beyond`. The threshold is a cadence somebody chose to aim
    at, and hitting it is meeting it.

    These are not confidence words. The engine reports how old a determination is; it
    never claims how sure anyone should be that it is still true.

    A negative `days` — an affirming event dated in the future — reports as `within`,
    matching the twin. This is a pure distance measurement and an `impossible` band would
    smuggle a validation verdict into the distribution; a future-dated event is a file
    defect and belongs wherever the file is validated, not hidden inside a band a reader
    would take as good news.
    """
    if days <= threshold_days // 2:
        return "within"
    if days <= threshold_days:
        return "approaching"
    if days <= threshold_days * 2:
        return "beyond"
    return "wellBeyond"


# Events where a human asserted something about a risk's magnitude or its treatment
# decision. Only these reset confirmation age. A note, a rewording, a theme move, a
# status flip and a snapshot deliberately do not: an age that any edit resets makes the
# confirmation-age report worthless.
AGE_AFFIRMING = frozenset({
    "risk-added", "score-changed", "risk-confirmed", "risk-accepted",
    # Nothing writes this yet; references/schema.md documents it, and it is an
    # affirmation when it arrives. Classified now so it behaves correctly then.
    "acceptance-revalidated",
})

# The other half of the partition: events that are real history but assert nothing about
# a risk's magnitude or its treatment decision, and so must NOT reset confirmation age.
# Spelled out rather than left as "everything not listed above", because the difference
# between the two is the whole mechanism — see the note on KNOWN_EVENT_TYPES.
NON_AGE_AFFIRMING = frozenset({
    "register-created", "risk-updated", "response-changed", "status-changed",
    "theme-changed", "settings-changed", "snapshot-created", "import-merged",
    "risk-closed", "risk-reopened", "risk-deleted",
    # Changing when the register escalates asserts nothing about any individual risk's
    # magnitude or treatment, so it must not reset anything's confirmation age. It is real
    # history — it changes what the register reports — but it is a statement about the
    # policy, not about a risk.
    "escalation-policy-changed",
})

# Every type this file can write, plus every type references/schema.md documents.
#
# The self-test holds three things together: the emitted set (scraped from this file's own
# source) is a subset of this one, AGE_AFFIRMING and NON_AGE_AFFIRMING are disjoint, and
# their union is exactly this set. That third assertion is the one that matters. An
# earlier version asserted only the subset property, which forced a new event type to be
# *registered* here and nothing more — the single edit a failing subset check steers you
# toward — leaving it non-affirming by omission, which is precisely the default the
# mechanism exists to prevent. Requiring the union makes registration insufficient: a new
# type has to be placed in AGE_AFFIRMING or NON_AGE_AFFIRMING, and that placement is the
# decision. Silently resetting, or silently failing to reset, staleness is what makes a
# staleness report worthless.
#
# Written out independently rather than as `AGE_AFFIRMING | NON_AGE_AFFIRMING`, which would
# make the union assertion a tautology and hand back the hole it was added to close.
KNOWN_EVENT_TYPES = frozenset({
    "register-created", "risk-added", "risk-updated", "score-changed", "response-changed",
    "status-changed", "risk-accepted", "acceptance-revalidated", "risk-confirmed",
    "risk-closed", "risk-reopened", "risk-deleted", "theme-changed", "settings-changed",
    "snapshot-created", "import-merged", "escalation-policy-changed",
})


def _emitted_event_types() -> set:
    """Every event type this file actually writes, scraped from its own source text.

    Derived rather than hand-listed on purpose. The self-test asserts this is a subset of
    KNOWN_EVENT_TYPES; if both sides were hand-maintained constants the check could not
    fail, because whoever added an emitting call would be the same person updating the
    list — green over an unclassified event type. Reading the source means the new call
    itself is what breaks the suite.

    The pattern below does not match its own text (the literal here is `_append_event\\(`,
    with a backslash), so this function never counts itself.

    If the source cannot be read, this returns a sentinel that is deliberately not a valid
    event type, so the totality check fails loudly rather than passing over an empty set.
    UnicodeDecodeError is caught alongside OSError because a .pyc-only install makes
    __file__ the bytecode: decoding it raises UnicodeDecodeError, which subclasses
    ValueError and would be swallowed by __main__'s handler into a codec error no
    maintainer would ever connect to event types. python-compat.sh's own note that the
    installed plugin "is NOT a git checkout" is why non-checkout execution is worth
    handling rather than assuming away.
    """
    try:
        with open(os.path.abspath(__file__), encoding="utf-8") as fh:
            src = fh.read()
    except (OSError, UnicodeDecodeError):
        return {"<source-unreadable>"}
    return set(re.findall(r'_append_event\(\s*reg\s*,\s*"([a-z-]+)"', src))


def _flag_declaring_commands() -> set:
    """Every command function that passes a `known=` set to `parse_flags`, read from source.

    Scraped rather than hand-listed for the reason `_emitted_event_types` gives: if both sides
    of the check were maintained by hand, whoever added a command would be the same person
    updating the list, and the check could not fail. Reading the source means the new command
    itself is what breaks the suite.

    Returns command NAMES as `COMMANDS` spells them — `set-text`, not `_cmd_set_text` — so the
    self-test compares against `COMMANDS` and `_FLAGS_UNDECLARED` directly.
    """
    try:
        with open(os.path.abspath(__file__), encoding="utf-8") as fh:
            src = fh.read()
    except (OSError, UnicodeDecodeError):
        return {"<source-unreadable>"}
    out = set()
    for chunk in re.split(r"\ndef ", src):
        name = chunk.split("(", 1)[0].strip()
        if not name.startswith("_cmd_"):
            continue
        # The needle is assembled rather than written whole, so this function does not match
        # its own body and report itself as a declaring command.
        if re.search(r"parse_flags\(\s*args\s*,\s*" + "known" + r"=", chunk):
            out.add(name[len("_cmd_"):].replace("_", "-"))
    return out


def _affirming_writers() -> set:
    """Every command function in this file that can write an AGE_AFFIRMING event.

    Derived from source for the same reason _emitted_event_types() is: the invariant it
    guards — no affirming event may attach to a provisional-score risk — has to hold for
    writers nobody has thought of yet, and a hand-kept list of writers is exactly the
    omission-by-default the taxonomy partition was added to close.
    """
    try:
        with open(os.path.abspath(__file__), encoding="utf-8") as fh:
            src = fh.read()
    except (OSError, UnicodeDecodeError):
        return {"<source-unreadable>"}
    out = set()
    for chunk in re.split(r"\ndef ", src):
        name = chunk.split("(", 1)[0].strip()
        if not name.startswith("_cmd_"):
            continue
        emitted = re.findall(r'_append_event\(\s*reg\s*,\s*"([a-z-]+)"', chunk)
        if any(e in AGE_AFFIRMING for e in emitted):
            out.add(name)
    return out


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _s(v):
    """Coerce a possibly-multi-token flag value back to a string."""
    return " ".join(v) if isinstance(v, list) else v


# Commands whose flags are not yet declared to `parse_flags`. **This list may only shrink.**
#
# `risk-register` is the one engine in the suite that does not use `argparse`, and it is also
# the one with the most mutation commands — so an unknown flag was accepted and dropped in
# silence. `init --currency GBP` exited 0 with a success message and wrote no currency, and
# `--appetitie medium` produced a register that did not contain what its author believed.
#
# The obvious fix is a full argparse conversion. It is deliberately NOT done: that rewrites all
# twenty commands in one change, in the skill where a mistake costs most, for a benefit strict
# rejection delivers on its own. Instead each command declares what it accepts, and this names
# the ones not yet converted.
#
# The list is the point rather than the compromise. It turns "twenty commands to fix someday"
# into a number the self-test prints and asserts, and that number can only go down — the same
# pattern as `ai-register/evals/exposure.sh`: an absence has to be checked or it grows back.
# A new command cannot join it without editing this line, and the self-test refuses a command
# that is neither declared nor listed.
_FLAGS_UNDECLARED = frozenset({
    "score", "import-gaps", "import-findings", "self-test", "set-score", "accept",
    "confirm", "set-status", "snapshot", "export-csv", "export-acceptances",
    "add-theme", "set-theme", "escalations",
})

# The self-test asserts the list is no LONGER than this. Lower it when a command is converted;
# it may never go up. A ceiling rather than an equality on purpose — see the check itself.
_UNDECLARED_CEILING = 14


def parse_flags(args: list[str], known=None):
    """Tiny --flag parser. `--x a b` -> {'x': ['a','b']}; `--x a` -> {'x': 'a'}; `--x` -> {'x': True}.

    When `known` is supplied, an unrecognised `--flag` RAISES, naming the flag and listing what
    the command does accept. `known=None` keeps the old permissive behaviour, which is what the
    commands still in `_FLAGS_UNDECLARED` rely on.

    Rejecting is the whole point. Discarding a flag silently turns a typo into a register that
    is missing what its author believes is in it, and no later command can detect that.
    """
    pos, opt, i = [], {}, 0
    while i < len(args):
        a = args[i]
        if a.startswith("--"):
            key, vals, j = a[2:], [], i + 1
            while j < len(args) and not args[j].startswith("--"):
                vals.append(args[j]); j += 1
            opt[key] = (vals if len(vals) > 1 else vals[0]) if vals else True
            i = j
        else:
            pos.append(a); i += 1
    if known is not None:
        unknown = sorted(k for k in opt if k not in known)
        if unknown:
            raise ValueError(
                "unknown flag%s: %s\n  this command accepts: %s\n  Nothing was written. A flag "
                "this parser did not recognise used to be discarded in silence, which is how a "
                "typo became a register missing the thing its author thought they had set."
                % ("" if len(unknown) == 1 else "s",
                   ", ".join("--" + k for k in unknown),
                   ", ".join("--" + k for k in sorted(known))))
    return pos, opt


def save_register(reg: dict, path: str) -> None:
    """Write the register back, stamping schemaVersion 2 and updatedAt. History is never
    rewritten here — callers append to reg['history'] before saving."""
    reg["schemaVersion"] = SCHEMA_VERSION
    reg.setdefault("createdAt", _now())
    reg["updatedAt"] = _now()
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(reg, fh, indent=2, ensure_ascii=False)


def _append_event(reg, etype, riskId=None, field=None, frm=None, to=None, rationale=None):
    ev = {"ts": _now(), "actor": reg["meta"].get("assessor") or "unknown", "type": etype}
    if riskId is not None:
        ev["riskId"] = riskId
    if field is not None:
        ev["field"] = field
    if frm is not None:
        ev["from"] = frm
    if to is not None:
        ev["to"] = to
    if rationale:
        ev["rationale"] = _s(rationale)
    reg.setdefault("history", []).append(ev)


def _find(reg, rid):
    for r in reg["risks"]:
        if r["id"] == rid:
            return r
    raise ValueError(f"No risk with id {rid!r}.")


def _lvl(v, size, label):
    try:
        n = int(_s(v))
    except (TypeError, ValueError):
        raise ValueError(f"{label} must be an integer 1..{size}.")
    if not 1 <= n <= size:
        raise ValueError(f"{label} {n} out of range 1..{size}.")
    return n


def _iso_date(value, flag: str) -> str:
    """Validate a date flag as a canonical YYYY-MM-DD string, or refuse.

    Every date this file stores is compared *lexically* downstream —
    renderers/_common.py::_overdue is `str(value)[:10] <= today` — so a non-canonical
    date does not merely look untidy, it silently inverts the comparison.
    `datetime.strptime(v, "%Y-%m-%d")` accepts unpadded fields, so `2027-2-01` used to be
    stored verbatim and then read as *not overdue* against a today of `2027-11-01`,
    dropping an eight-month-overdue review off the attention list entirely.

    Twinned with skills/nist-csf/scripts/profile_analysis.py::_iso_date, which carries the
    matching note and enforced this rule first — references/schema.md:245 there states it
    exactly: "`2026-3-14` sorts after `2026-12-01` and would make every revisit flag and age
    figure downstream quietly wrong." Same name, same rule, same reason, duplicated on the
    same terms as age_band() above; edit the two together. That file reaches the verdict via
    a strptime round-trip and this one via date.fromisoformat plus a round-trip; the verdicts
    agree on every input either accepts, including `20270201`, and each skill's own self-test
    is what pins them.

    `date.fromisoformat` rejects the unpadded form. The round-trip equality check then
    rejects the basic form `20270201`, which 3.11+ accepts and the 3.9 floor does not —
    without it this flag would mean two different things on two supported interpreters,
    and `20270201` breaks `_overdue` exactly the same way. Same wording as _common.py's
    `--today` guard, which has always validated this way; this is that idiom reaching the
    flags that write the file rather than only the one that reads it.
    """
    s = _s(value)
    if s is True or s is None or not str(s).strip():
        raise ValueError(f"{flag} needs a date (YYYY-MM-DD).")
    s = str(s).strip()
    try:
        parsed = date.fromisoformat(s)
    except (ValueError, TypeError):
        raise ValueError(f"{flag} {s!r} is not a YYYY-MM-DD date.")
    if parsed.isoformat() != s:
        raise ValueError(f"{flag} {s!r} is not a YYYY-MM-DD date "
                         f"(write it as {parsed.isoformat()}).")
    return s


def _int_opt(opt, key, default):
    """Read an integer flag. A bare `--matrix` with no value is a typo, not a default."""
    if key not in opt or opt[key] is True:
        return default
    try:
        return int(_s(opt[key]))
    except (TypeError, ValueError):
        raise ValueError(f"--{key} must be an integer (got {_s(opt[key])!r}).")


def _cost_opt(opt, key="cost"):
    """Read a treatment-cost flag, or None when absent. Rejects negative; ACCEPTS zero.

    Three refusals and one deliberate acceptance:

    * **Negative is refused.** `response.cost` feeds `treatment_cost`, whose total prints on a
      board page. A negative slipped in at `add` reduced that total and there was no path to
      correct it — a board figure quietly too low, which is the direction nobody audits.
    * **A bare `--cost` is refused**, on `_int_opt`'s stated rule: a flag with no value is a
      typo, not a default. Defaulting it to zero would record "we priced this at nothing".
    * **A non-integer is refused**, naming the value, so a stray currency symbol or comma
      fails loudly instead of raising a bare ValueError from `int()`.
    * **Zero is ACCEPTED**, and that is the point of the rule rather than an edge case. Zero
      means *priced, and the answer is nothing* — a control already funded, a change absorbed
      in run costs. It is a different statement from absent, which means nobody has priced it,
      and the renderer keeps them apart too.

    Integer, not decimal: the display format is `,.0f`, so a decimal would be silently rounded
    on the way to the page. A stated decision rather than an artifact of `int()`.
    """
    if key not in opt:
        return None
    if opt[key] is True:
        raise ValueError(f"--{key} needs a value, e.g. --{key} 45000. A bare flag is a typo, "
                         f"not a default — recording zero would claim it was priced at nothing.")
    raw = _s(opt[key]).strip()
    try:
        value = int(raw)
    except (TypeError, ValueError):
        raise ValueError(f"--{key} must be a whole number of currency units (got {raw!r}). "
                         f"No symbols, no separators, no decimals — the total renders with "
                         f"no decimal places, so one here would be silently rounded.")
    if value < 0:
        raise ValueError(f"--{key} cannot be negative (got {value}). A treatment cost is what "
                         f"the response is expected to cost; a negative reduces the board's "
                         f"total and there is no reading of it that is true. Record 0 for "
                         f"'priced at nothing', or leave it off for 'not priced'.")
    return value


def _currency_opt(opt):
    """Read `--currency`, or "" for not recorded. A bare `--currency` is refused.

    `SKILL.md` is explicit that currency is *optional and never guessed*, and this closes the
    gap rather than relaxing it: the flag existed in the documentation and no command read it,
    so `init --currency GBP` exited 0 and wrote nothing. Never inferred from a locale, a
    jurisdiction or an amount — a total shown in the wrong currency is worse than one shown in
    none, because only the second is obviously incomplete to whoever reads it.

    A bare `--currency` with no value RAISES rather than defaulting. That is the rule
    `_int_opt`'s docstring states, and this is the first place it is actually enforced.
    """
    if "currency" not in opt:
        return ""
    if opt["currency"] is True:
        raise ValueError("--currency needs a value, e.g. --currency GBP. A bare flag is a "
                         "typo, not a default; currency is never guessed.")
    code = _s(opt["currency"]).strip()
    if not code:
        raise ValueError("--currency needs a value, e.g. --currency GBP.")
    # Deliberately NOT validated against a code list. The register does not own a currency
    # taxonomy any more than it owns a criticality scale, and a shipped ISO-4217 list would
    # be one more dataset to keep current for no gain — the string is printed back, not
    # computed with.
    return code


def _cmd_init(args):
    """Create an empty register.

    Without this, the only way to start one is to hand-author the JSON — which
    SKILL.md forbids everywhere else ("the audit trail is enforced by tooling rather
    than by discipline") and which means the register's own creation, its matrix size
    and its appetite never enter history. Those three are exactly the settings a
    board later asks to see justified.
    """
    pos, opt = parse_flags(args, known={
        "client", "assessor", "matrix", "appetite", "scope-note", "appetite-statement",
        "currency", "why"})
    if not pos or "client" not in opt:
        raise ValueError("usage: init <register.rr> --client 'Acme Corp' [--assessor 'CISO'] "
                         "[--matrix 5] [--appetite medium] [--scope-note '...'] "
                         "[--appetite-statement '...'] [--currency GBP]")
    path = pos[0]
    # Never clobber a register. It is the system of record, and a re-run of a setup
    # command is a plausible mistake with an unrecoverable outcome.
    if os.path.exists(path):
        raise ValueError(f"{path} already exists — refusing to overwrite an existing register.")

    size = _int_opt(opt, "matrix", 5)
    if size not in BAND_THRESHOLDS:
        raise ValueError(f"--matrix must be one of {sorted(BAND_THRESHOLDS)} (got {size}).")
    appetite = _s(opt.get("appetite", "medium"))
    if appetite not in BAND_ORDER:
        raise ValueError(f"--appetite must be one of {BAND_ORDER} (got {appetite!r}).")
    currency = _currency_opt(opt)

    reg = {
        "schemaVersion": SCHEMA_VERSION,
        "meta": {
            "clientName": _s(opt["client"]),
            "assessor": _s(opt.get("assessor", "")) if opt.get("assessor") is not True else "",
            "scopeNote": _s(opt.get("scope-note", "")) if opt.get("scope-note") is not True else "",
            "appetiteStatement": (_s(opt.get("appetite-statement", ""))
                                  if opt.get("appetite-statement") is not True else ""),
        },
        # Written out rather than left to load_register's default, so a new register is
        # self-documenting: someone opening the file sees the four thresholds and can change
        # them, instead of having to know an invisible default existed.
        # `currency` is written whether or not it was given, and empty means NOT RECORDED —
        # never a guessed symbol. Writing the key out rather than leaving it to
        # load_register's default keeps a new register self-documenting, the same reasoning
        # as the four escalation thresholds beside it.
        "settings": {"matrixSize": size, "appetite": appetite, "currency": currency,
                     "escalation": dict(ESCALATION_DEFAULTS)},
        "themes": [],
        "risks": [],
        "history": [],
        "snapshots": [],
    }
    _append_event(reg, "register-created", field="settings",
                  to=f"{size}x{size} matrix, {appetite} appetite",
                  rationale=_s(opt.get("why")) if isinstance(opt.get("why"), (str, list)) else None)
    save_register(reg, path)

    print(f"Created {path}")
    print(f"  Client:   {reg['meta']['clientName']}")
    print(f"  Assessor: {reg['meta']['assessor'] or '—'}")
    print(f"  Matrix:   {size}x{size}   Appetite: {appetite} "
          f"(worst band still acceptable)")
    print(f"  Currency: {currency or '— not recorded (treatment costs render bare)'}")
    if not reg["meta"]["scopeNote"]:
        print("  Note: no --scope-note set. An unscoped register is hard to defend; "
              "record what is in and out.")
    print("  Next: add risks with `add`, or import CSF gaps with "
          "`import-gaps <gaps.csv> --into " + path + " --write`.")
    return 0


def _cmd_add(args):
    pos, opt = parse_flags(args, known={
        "title", "description", "desc", "il", "ii", "rl", "ri", "category", "owner", "theme",
        "response", "response-desc", "cost", "review", "csf", "notes", "why"})
    if not pos:
        raise ValueError("usage: add <register.rr> --title '...' --il L --ii I --rl L --ri I "
                         "[--category ..] [--owner ..] [--theme ..] [--response mitigate] "
                         "[--response-desc ..] [--cost 45000] [--review DATE] [--csf ID] "
                         "[--notes ..] [--why ..]")
    path = pos[0]
    reg = load_register(path)
    size = reg["settings"]["matrixSize"]
    for req in ("title", "il", "ii", "rl", "ri"):
        if req not in opt:
            raise ValueError(f"add: missing --{req}")
    rtype = _s(opt.get("response", "mitigate"))
    if rtype not in RESPONSES:
        raise ValueError(f"--response must be one of {sorted(RESPONSES)}")
    risk = {
        "id": next_risk_id(reg["risks"]), "title": _s(opt["title"]),
        "description": _s(opt.get("description", opt.get("desc", ""))),
        "category": _s(opt.get("category", "")), "theme": _s(opt["theme"]) if "theme" in opt else None,
        "owner": _s(opt.get("owner", "")),
        "inherent": {"likelihood": _lvl(opt["il"], size, "--il"), "impact": _lvl(opt["ii"], size, "--ii")},
        "response": {"type": rtype, "description": _s(opt.get("response-desc", ""))},
        "residual": {"likelihood": _lvl(opt["rl"], size, "--rl"), "impact": _lvl(opt["ri"], size, "--ri")},
        "status": "open", "acceptance": None,
    }
    _cost = _cost_opt(opt)
    if _cost is not None:
        risk["response"]["cost"] = _cost
    if "review" in opt:
        risk["reviewDate"] = _iso_date(opt["review"], "--review")
    if "csf" in opt:
        risk["csfSubcategoryId"] = _s(opt["csf"])
    if "notes" in opt:
        risk["notes"] = _s(opt["notes"])
    if risk["theme"] and not any(t.get("id") == risk["theme"] for t in reg["themes"]):
        print(f"warning: theme {risk['theme']!r} is not defined in this register; "
              f"it will roll up as Unclassified. Define it with: add-theme", file=sys.stderr)
    reg["risks"].append(risk)
    _append_event(reg, "risk-added", riskId=risk["id"], rationale=opt.get("why"))
    save_register(reg, path)
    res = exposure(risk["residual"]["likelihood"], risk["residual"]["impact"])
    over = " (over appetite)" if over_appetite(res, size, reg["settings"]["appetite"]) else ""
    print(f"Added {risk['id']}: residual {res} {band(res, size)}{over}")
    return 0


def _cmd_set_text(args):
    """Rewrite a risk's title and/or description, clearing `provisionalTitle`.

    The build workflow says to reword each imported gap as an if-then event
    statement — "PR.AA-05 partially implemented" is a control objective, not a risk —
    but until this command existed there was no way to do it except hand-editing the
    JSON, which bypasses history entirely. This is the command that makes an imported
    candidate into an assessed risk.
    """
    pos, opt = parse_flags(args, known={"title", "description", "why"})
    if len(pos) < 2 or not ({"title", "description"} & set(opt)):
        raise ValueError("usage: set-text <register.rr> <risk-id> [--title '...'] "
                         "[--description '...'] --why '...'")
    path, rid = pos[0], pos[1]
    if "why" not in opt:
        raise ValueError("set-text: --why is required — rewording a risk is a material change.")
    reg = load_register(path)
    risk = _find(reg, rid)

    for field in ("title", "description"):
        if field in opt:
            old, new = risk.get(field, ""), _s(opt[field])
            if old == new:
                continue
            risk[field] = new
            _append_event(reg, "risk-updated", riskId=rid, field=field,
                          frm=trunc(old, 80), to=trunc(new, 80), rationale=opt["why"])

    was_provisional = bool(risk.get("provisionalTitle"))
    if was_provisional:
        risk["provisionalTitle"] = False
        _append_event(reg, "risk-updated", riskId=rid, field="provisionalTitle",
                      frm=True, to=False, rationale=opt["why"])
    save_register(reg, path)

    print(f"Updated {rid}: {trunc(risk['title'], 90)}")
    if was_provisional:
        print("  Wording reviewed — this title will now render in board-facing views.")
    if risk.get("provisionalScore"):
        print("  Scores are still the import seed. Refine them with `set-score`.")
    return 0


def _cmd_add_theme(args):
    pos, opt = parse_flags(args)
    if not pos or "id" not in opt or "name" not in opt:
        raise ValueError("usage: add-theme <register.rr> --id <theme-id> --name 'Display Name' "
                         "[--description '...'] [--why '...']")
    path = pos[0]
    reg = load_register(path)
    tid = _s(opt["id"])
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", tid):
        raise ValueError(f"--id {tid!r} must be lowercase alphanumeric with hyphens (e.g. 'third-party').")
    if any(t.get("id") == tid for t in reg["themes"]):
        raise ValueError(f"Theme {tid!r} already exists.")
    theme = {"id": tid, "name": _s(opt["name"]), "description": _s(opt.get("description", ""))}
    reg["themes"].append(theme)
    _append_event(reg, "theme-changed", field="themes", to=tid,
                  rationale=opt.get("why") or f"Theme '{theme['name']}' added")
    save_register(reg, path)
    print(f"Added theme {tid}: {theme['name']} ({len(reg['themes'])} themes)")
    return 0


def _cmd_set_theme(args):
    pos, opt = parse_flags(args)
    if len(pos) < 3:
        raise ValueError("usage: set-theme <register.rr> <risk-id> <theme-id|none> [--why '...']")
    path, rid, tid = pos[0], pos[1], pos[2]
    reg = load_register(path)
    r = _find(reg, rid)
    new = None if tid in ("none", "-", "null") else tid
    if new is not None and not any(t.get("id") == new for t in reg["themes"]):
        raise ValueError(f"No theme {new!r} in this register (add it with add-theme first).")
    frm = r.get("theme")
    r["theme"] = new
    _append_event(reg, "theme-changed", riskId=rid, field="theme", frm=frm, to=new,
                  rationale=opt.get("why"))
    save_register(reg, path)
    print(f"{rid}: theme {frm or '—'} → {new or '—'}")
    return 0


def _on_off(opt, key, current):
    """Read an `on|off` flag, keeping `current` when the flag is absent.

    Strict about the two words rather than accepting anything truthy. `--band-cross false`
    silently meaning "on" — because a non-empty string is truthy — is the kind of quiet
    inversion that turns a threshold nobody re-read into a report nobody can trust.
    """
    if key not in opt or opt[key] is True:
        return current
    raw = str(_s(opt[key])).strip().lower()
    if raw == "on":
        return True
    if raw == "off":
        return False
    raise ValueError(f"--{key} must be 'on' or 'off' (got {_s(opt[key])!r}).")


def _cmd_set_escalation(args):
    """Change when this register escalates, and log that the policy moved.

    A threshold quietly rewriting which risks escalate is the same corrosion `confirm`
    exists to prevent: the register would report a calmer quarter without a single risk
    having improved. So the policy is a material change with a required rationale, and it
    lands in history beside the score moves it governs.

    Absent flags keep their current value rather than resetting to the shipped defaults —
    tuning one threshold must not silently revert the other three.
    """
    pos, opt = parse_flags(args, known={
        "sustained", "dwell-days", "band-cross", "lapsed-acceptance", "why"})
    if not pos:
        raise ValueError("usage: set-escalation <register.rr> [--sustained N] [--dwell-days D] "
                         "[--band-cross on|off] [--lapsed-acceptance on|off] --why '...'")
    path = pos[0]
    reg = load_register(path)
    if "why" not in opt:
        raise ValueError("set-escalation: --why is required "
                         "(material change; the rationale is the audit trail).")
    cur = dict(reg["settings"]["escalation"])
    new = dict(cur)
    new["sustainedWorseningSnapshots"] = _int_opt(opt, "sustained",
                                                  cur["sustainedWorseningSnapshots"])
    new["appetiteDwellDays"] = _int_opt(opt, "dwell-days", cur["appetiteDwellDays"])
    new["bandCross"] = _on_off(opt, "band-cross", cur["bandCross"])
    new["lapsedAcceptance"] = _on_off(opt, "lapsed-acceptance", cur["lapsedAcceptance"])

    for key, flag in (("sustainedWorseningSnapshots", "--sustained"),
                      ("appetiteDwellDays", "--dwell-days")):
        if new[key] < 1:
            raise ValueError(f"{flag} must be 1 or more (got {new[key]}). "
                             f"A threshold of zero escalates everything, every run, which is "
                             f"how escalation gets ignored.")
    # A no-op write would put "policy changed" in the log where no policy changed — the same
    # defect `confirm` exists to keep out of `score-changed`.
    if new == cur:
        raise ValueError("set-escalation: nothing would change. Pass at least one of "
                         "--sustained, --dwell-days, --band-cross, --lapsed-acceptance.")

    moved = ", ".join(f"{k} {cur[k]} → {new[k]}" for k in new if new[k] != cur[k])
    reg["settings"]["escalation"] = new
    _append_event(reg, "escalation-policy-changed", field="settings.escalation",
                  frm=cur, to=new, rationale=_s(opt["why"]))
    save_register(reg, path)
    print(f"Escalation policy updated — {moved}")
    return 0


def _cmd_set_currency(args):
    """Record or change the currency treatment costs are denominated in.

    Modelled on `_cmd_set_escalation`, which is this register's shape for a settings mutator:
    requires `--why`, refuses a no-op, appends one event. `settings-changed` was already in
    `KNOWN_EVENT_TYPES` and already classified as non-age-affirming — `confirmation-age.sh`
    asserts it — so nothing about the taxonomy moves for this.

    Changing the currency of a register that already carries costs does NOT convert them. The
    amounts are the numbers somebody entered, and re-denominating them would be this tool
    deciding what a figure means; the event records the change so a reader can see when the
    label moved and ask what the numbers were.
    """
    pos, opt = parse_flags(args, known={"currency", "why"})
    if not pos:
        raise ValueError("usage: set-currency <register.rr> --currency GBP --why '...'")
    path = pos[0]
    reg = load_register(path)
    if "why" not in opt:
        raise ValueError("set-currency: --why is required "
                         "(material change; the rationale is the audit trail).")
    if "currency" not in opt:
        raise ValueError("set-currency: --currency is required, e.g. --currency GBP.")
    new = _currency_opt(opt)
    cur = _s(reg["settings"].get("currency", ""))
    # A no-op write would put "settings changed" in the log where nothing changed — the same
    # defect `confirm` exists to keep out of `score-changed`.
    if new == cur:
        raise ValueError(f"set-currency: the register already records {cur!r}. "
                         f"Nothing would change.")

    n_costed = sum(1 for r in reg["risks"] if isinstance(r.get("response"), dict)
                   and r["response"].get("cost") is not None)
    reg["settings"]["currency"] = new
    _append_event(reg, "settings-changed", field="settings.currency",
                  frm=cur or None, to=new, rationale=_s(opt["why"]))
    save_register(reg, path)
    print(f"Currency {'set to' if not cur else f'changed {cur} →'} {new}")
    if n_costed:
        print(f"  {n_costed} risk(s) already carry a treatment cost. The amounts are "
              f"unchanged — this relabels them, it does not convert them.")
    return 0


def _cmd_set_response(args):
    """Correct a risk's treatment response — its type, description or cost.

    Until this existed, `response` was write-once at `add`. A cost typed wrongly was
    permanent: `SKILL.md` forbids hand-editing the store, and no command touched the field,
    so the only routes were to leave a wrong number on a board page or to break the rule that
    makes the audit trail worth anything.

    `set-response` rather than `set-cost`, for two reasons. `response-changed` is the event
    already in `KNOWN_EVENT_TYPES` and already classified, so no vocabulary moves. And the
    response object carries three fields that are one decision — changing the type from
    `mitigate` to `accept` without being able to say what that now costs would be half a
    correction. `set-text` handles title and description together on the same reasoning.

    `--why` is required, matching `set-text`, `set-score` and `set-escalation`. A cost typo
    looks immaterial, but the register cannot tell a typo from a re-estimate, and the two have
    very different meanings to whoever reads the history a year later. The rationale is what
    distinguishes them.

    Note what this does NOT do: it does not re-score the risk. Response and score are separate
    judgements and `set-score` owns the second one.
    """
    pos, opt = parse_flags(args, known={"type", "response-desc", "cost", "why"})
    if len(pos) < 2:
        raise ValueError("usage: set-response <register.rr> <risk-id> [--type mitigate] "
                         "[--response-desc '...'] [--cost 45000] --why '...'")
    path, rid = pos[0], pos[1]
    reg = load_register(path)
    risk = _find(reg, rid)
    if "why" not in opt:
        raise ValueError("set-response: --why is required — the register cannot tell a typo "
                         "from a re-estimate, and the rationale is what does.")
    if not ({"type", "response-desc", "cost"} & set(opt)):
        raise ValueError("set-response: pass at least one of --type, --response-desc, --cost.")

    cur = dict(risk.get("response") or {})
    new = dict(cur)
    if "type" in opt:
        rtype = _s(opt["type"])
        if rtype not in RESPONSES:
            raise ValueError(f"--type must be one of {sorted(RESPONSES)} (got {rtype!r}).")
        new["type"] = rtype
    if "response-desc" in opt:
        new["description"] = _s(opt["response-desc"])
    if "cost" in opt:
        new["cost"] = _cost_opt(opt)

    # A no-op write would put "response changed" in the log where nothing changed — the same
    # defect `confirm` exists to keep out of `score-changed`.
    if new == cur:
        raise ValueError("set-response: nothing would change. The values given are the ones "
                         "already recorded.")

    moved = ", ".join(f"{k} {cur.get(k, '—')!r} → {new[k]!r}"
                      for k in sorted(new) if new.get(k) != cur.get(k))
    risk["response"] = new
    _append_event(reg, "response-changed", riskId=risk["id"], field="response",
                  frm=cur or None, to=new, rationale=_s(opt["why"]))
    save_register(reg, path)
    print(f"{risk['id']} response updated — {moved}")
    return 0


def _cmd_set_score(args):
    pos, opt = parse_flags(args)
    if len(pos) < 2:
        raise ValueError("usage: set-score <register.rr> <id> [--inherent L I] [--residual L I] --why '...'")
    reg = load_register(pos[0]); size = reg["settings"]["matrixSize"]; r = _find(reg, pos[1])
    if "why" not in opt:
        raise ValueError("set-score: --why is required (material change; the rationale is the audit trail).")
    changed = False
    for field in ("inherent", "residual"):
        if field in opt:
            vals = opt[field]
            if not isinstance(vals, list) or len(vals) != 2:
                raise ValueError(f"--{field} needs two values: L I")
            frm = dict(r[field])
            r[field] = {"likelihood": _lvl(vals[0], size, f"--{field} L"), "impact": _lvl(vals[1], size, f"--{field} I")}
            _append_event(reg, "score-changed", riskId=pos[1], field=field, frm=frm, to=r[field], rationale=opt["why"])
            changed = True
    if not changed:
        raise ValueError("set-score: provide --inherent and/or --residual.")
    # Scoring clears the *score* dimension only. It deliberately does not authorise the
    # title: refining likelihood and impact says nothing about whether the wording is
    # still a control objective phrased as a good thing. Conflating the two let the
    # score-only review path put raw framework text in front of a board.
    if r.get("provisionalScore"):
        r["provisionalScore"] = False
        _append_event(reg, "risk-updated", riskId=pos[1], field="provisionalScore",
                      frm=True, to=False, rationale=opt["why"])
    save_register(reg, pos[0])
    res = exposure(r["residual"]["likelihood"], r["residual"]["impact"])
    print(f"{pos[1]} updated: residual {res} {band(res, size)}")
    if r.get("provisionalTitle"):
        print("  Title is still CSF framework wording, so it stays out of board views.")
        print("  Reword it with `set-text` when you are ready to show it.")
    return 0


def _cmd_accept(args):
    pos, opt = parse_flags(args)
    if len(pos) < 2:
        raise ValueError("usage: accept <register.rr> <id> --approver '...' --justification '...' "
                         "--revalidate DATE [--expiry DATE] [--accepted DATE] [--why '...']")
    reg = load_register(pos[0]); r = _find(reg, pos[1])
    for req in ("approver", "justification", "revalidate"):
        if req not in opt:
            raise ValueError(f"accept: missing --{req}")
    # Refused for the same reason `confirm` is, and this is the door that closes the set.
    # `risk-accepted` is in AGE_AFFIRMING, so accepting here reset confirmation age to zero
    # on the importer's seed number and fed a board-facing freshness figure with it — and
    # `accept` is the worse of the two paths, because it also flips response.type and books
    # a *named approver* against a magnitude nobody has assessed, which is precisely what an
    # auditor tests.
    #
    # The invariant this establishes: NO AFFIRMING EVENT CAN ATTACH TO A PROVISIONAL-SCORE
    # RISK. It holds because the affirming writers are exactly four. `risk-added` comes only
    # from _cmd_add, which creates the risk and never sets the provisional flags (only the
    # importer does, and it writes `import-merged`, which is non-affirming). `score-changed`
    # comes from _cmd_set_score, which *clears* provisionalScore in the same breath — it is
    # the sanctioned way through, not an exception to the rule. That leaves confirm and
    # accept, both of which now refuse. `acceptance-revalidated` is inert: nothing emits it.
    # The self-test asserts the invariant over the writer set derived from this file's own
    # source, so a fifth affirming writer has to face the question rather than inherit a
    # gap. That invariant is what makes the confirmation-age report trustworthy.
    if r.get("provisionalScore"):
        raise ValueError(f"accept: {pos[1]}'s score is still the import seed, so there is no "
                         f"assessed magnitude to accept. Assess it with `set-score` first — "
                         f"booking a named approver against a number nobody has reviewed is "
                         f"the acceptance an auditor pulls.")
    # All three dates are validated before anything is written. revalidationDate and
    # expiryDate both reach _overdue's lexical compare in the renderers, so an unpadded
    # date here reads as "not due" and an acceptance nobody re-validated stops appearing
    # on the attention list. acceptedDate is validated for the same reason its siblings
    # are: one flag name meaning one thing.
    revalidate = _iso_date(opt["revalidate"], "--revalidate")
    expiry = _iso_date(opt["expiry"], "--expiry") if "expiry" in opt else ""
    accepted = _iso_date(opt["accepted"], "--accepted") if "accepted" in opt else _now()[:10]
    # Every date is parsed before the first write, so a bad one refuses without leaving a
    # half-applied acceptance behind — response.type used to flip to "accept" first.
    r["response"]["type"] = "accept"
    r["acceptance"] = {
        "approver": _s(opt["approver"]), "justification": _s(opt["justification"]),
        "acceptedDate": accepted, "expiryDate": expiry, "revalidationDate": revalidate,
    }
    _append_event(reg, "risk-accepted", riskId=pos[1], rationale=opt.get("why", opt["justification"]))
    save_register(reg, pos[0])
    print(f"{pos[1]} accepted by {r['acceptance']['approver']}; re-validate by {r['acceptance']['revalidationDate']}")
    return 0


def _cmd_confirm(args):
    """Record that a risk was looked at and nothing changed.

    Before this existed, the only way to re-affirm a risk was `set-score` at an identical
    value — which writes a `score-changed` event where no score changed, corroding the
    audit trail the skill exists to keep honest. "I reviewed this and it still stands" is
    a material claim and deserves its own event type and its own rationale.

    Changes no score, no status, no response, no band. The only optional write is
    `--review`, because setting the next review date in the same breath is the actual
    review-meeting workflow.

    Refuses while `provisionalScore` is true — there is nothing to re-affirm about a number
    nobody has assessed — and only warns on a provisional title, which is the same line
    `set-score` draws between magnitude and board-eligible wording.

    Confirming a *closed* risk is allowed, deliberately. "We re-checked this and it stays
    closed" is a claim reviewers make and auditors ask about, and refusing it would push
    people to reopen a risk purely to have somewhere to record the re-check — a worse
    audit trail than the one we are protecting. The corollary belongs downstream: a
    confirmation-age report must exclude closed risks rather than let a re-checked closed
    risk pad a freshness figure the board reads as live coverage.

    Ordering: every refusal below happens before the single in-memory write, and the only
    statement after that write is _append_event + save_register, neither of which
    validates. So a refused confirm never reaches save_register and the file on disk stays
    byte-identical — asserted in the self-test, not merely intended.

    This event's rationale is deliberately not eligible to caption a change on the board.
    `renderers/_common.py::Context.CHANGE_EXPLAINING` excludes `risk-confirmed`, because a
    claim that nothing changed cannot explain a change — left in, it printed "residual Low
    → Critical — 'reviewed at the forum; unchanged'" on the board page. The rationale is
    still kept in history and belongs to the confirmation-age view.
    """
    pos, opt = parse_flags(args)
    if len(pos) < 2:
        raise ValueError("usage: confirm <register.rr> <id> --why '...' [--review YYYY-MM-DD]")
    # A flag given twice used to keep the last value and drop the rest without a word.
    # Losing half of a stated intent in silence is the worst available outcome.
    for dup in ("why", "review"):
        if args.count("--" + dup) > 1:
            raise ValueError(f"confirm: --{dup} given more than once. Pass it once — "
                             f"keeping the last value silently discards what you meant.")
    reg = load_register(pos[0])
    r = _find(reg, pos[1])
    if not (isinstance(opt.get("why"), (str, list)) and _s(opt["why"]).strip()):
        raise ValueError("confirm: --why is required. Asserting that a risk is still right "
                         "is a material claim and belongs in the audit trail on the same "
                         "terms as a score change.")
    # A provisional score has never been reviewed by anyone — it is the importer's seed,
    # derived from a CSF gap's priority. `risk-confirmed` is in AGE_AFFIRMING, so
    # confirming here would reset confirmation age on a number nobody has ever assessed
    # and feed it into a board-facing freshness figure as though it had been. Refuse: the
    # honest path is `set-score` (at the seed value, if that is the assessment), which
    # clears the flag and records the rationale.
    #
    # This is not a date gate. It refuses to affirm something never assessed; it neither
    # expires nor rescores anything, and an assessed risk is confirmable forever.
    if r.get("provisionalScore"):
        raise ValueError(f"confirm: {pos[1]}'s score is still the import seed, so there is "
                         f"nothing yet to re-affirm. Assess it with `set-score` first — "
                         f"confirming would reset its confirmation age on a number nobody "
                         f"has reviewed.")
    review = None
    if "review" in opt:
        # A bare `--review` with no date is a typo, not a request for a default. There is
        # no sane default next-review date, and silently dropping the flag would send a
        # reviewer out of the meeting believing the next review is booked.
        if opt["review"] is True:
            raise ValueError("confirm: --review needs a date (YYYY-MM-DD). Bare --review "
                             "sets nothing, and a next review you think is booked but "
                             "isn't is worse than no date at all.")
        review = _iso_date(opt["review"], "--review")
        r["reviewDate"] = review
    _append_event(reg, "risk-confirmed", riskId=pos[1], rationale=opt["why"])
    save_register(reg, pos[0])
    print(f"{pos[1]} confirmed by {reg['meta'].get('assessor') or 'unknown'}.")
    if review:
        print(f"  Next review: {review}")
    # A provisional *title* only warns. Wording is a board-eligibility question, not a
    # magnitude one, and that is the same line `set-score` draws.
    if r.get("provisionalTitle"):
        print("  Title is still CSF framework wording, so it stays out of board views.")
        print("  Reword it with `set-text` when you are ready to show it.")
    return 0


def _cmd_set_status(args):
    pos, opt = parse_flags(args)
    if len(pos) < 3:
        raise ValueError(f"usage: set-status <register.rr> <id> <{'|'.join(sorted(STATUSES))}> [--why '...']")
    if pos[2] not in STATUSES:
        raise ValueError(f"status must be one of {sorted(STATUSES)}")
    reg = load_register(pos[0]); r = _find(reg, pos[1]); frm = r["status"]
    # Closing a risk, or reopening one that was closed, is a material change: it is a
    # completion claim an auditor will test. Refuse before touching the file so a rejected
    # mutation leaves the register byte-identical.
    material = pos[2] == "closed" or frm == "closed"
    if material and not (isinstance(opt.get("why"), (str, list)) and _s(opt["why"]).strip()):
        verb = "Closing" if pos[2] == "closed" else "Reopening"
        raise ValueError(f"set-status: --why is required to move {pos[1]} {frm} → {pos[2]}. "
                         f"{verb} a risk is a material change and the rationale is the audit "
                         f"trail — an unsupported completion claim is exactly what a reviewer "
                         f"looks for.")
    r["status"] = pos[2]
    _append_event(reg, "status-changed", riskId=pos[1], field="status", frm=frm, to=pos[2], rationale=opt.get("why"))
    save_register(reg, pos[0])
    print(f"{pos[1]}: {frm} → {pos[2]}")
    return 0


def _cmd_snapshot(args):
    pos, opt = parse_flags(args)
    if not pos or "label" not in opt:
        raise ValueError("usage: snapshot <register.rr> --label 'Q3 2026 Board Review' [--note '...']")
    reg = load_register(pos[0])
    # Snapshotted with a reference date, deliberately. This summary is frozen forever, and
    # scoring it without one would omit the two date-derived triggers — leaving a stored
    # escalation count permanently lower than what a live run reports for the same moment.
    # A snapshot's `ts` is now, so UTC today is exactly the date it was taken on.
    scored = score_register(reg, _utc_today())
    label = _s(opt["label"])
    snap = {
        "id": re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-"), "label": label,
        "ts": _now(), "note": _s(opt.get("note", "")),
        "data": {"settings": reg["settings"], "risks": [dict(r) for r in reg["risks"]], "summary": scored["summary"]},
    }
    reg.setdefault("snapshots", []).append(snap)
    _append_event(reg, "snapshot-created", rationale=opt.get("note") or label)
    save_register(reg, pos[0])
    print(f"Snapshot '{label}' saved ({scored['summary']['overAppetite']} over appetite, {scored['summary']['total']} risks).")
    return 0


def _cmd_escalations(args):
    """List what this register currently escalates.

    Exits 0 whether or not anything escalated. A non-zero exit would turn this into a gate,
    and the contract is flag-never-block: a lapsed acceptance or a drifting exposure is
    reported, and nothing downstream refuses to run because of one. Anyone who wants a gate
    can build it on the JSON; the tool will not impose one.
    """
    pos, opt = parse_flags(args)
    if not pos:
        raise ValueError("usage: escalations <register.rr> [--today YYYY-MM-DD] [--json]")
    today = _iso_date(opt["today"], "--today") if "today" in opt else _utc_today()
    reg = load_register(pos[0])
    esc = escalations(reg, today)
    _, base_label = _snapshot_baseline(reg)

    if "json" in opt:
        print(json.dumps(esc, indent=2, ensure_ascii=False))
        return 0

    # Naming the baseline is not decoration. "No escalations" against last quarter's review
    # means the register held steady; "no escalations" against no snapshot at all means
    # nothing has ever been compared, and the two must not read the same.
    against = (f"compared against {base_label}" if base_label
               else "no snapshot to compare against — nothing has a baseline yet")
    print(f"Escalations as at {today} UTC · {against}")
    if not esc:
        print("  none.")
    for e in esc:
        print(f"  [{e['severity']:<8}] {e['subjectRef']:<7} {e['trigger']:<17} "
              f"{e['evidence']['detail']}")
    suppressed = suppressed_provisional(reg)
    if suppressed:
        print(f"\n  {suppressed} risk(s) carry a provisional score and were not assessed "
              f"for escalation — clear it with set-score.")
    return 0


def _last_affirmed(reg: dict, rid: str):
    """The date this risk's score was last stood behind, or None.

    Only `AGE_AFFIRMING` events count — the same partition `renderers/_common.py` uses for
    confirmation age, read here rather than re-decided, so the export and the dashboards
    cannot disagree about when a number was last affirmed.

    An unreadable `ts` is skipped rather than coerced. A malformed timestamp becoming a
    measurement date would hand `exceptions-register` a magnitude that looks dated and is
    not, which is precisely the state its re-measurement refusal exists to catch.
    """
    dates = []
    for e in reg.get("history") or []:
        if e.get("riskId") != rid or e.get("type") not in AGE_AFFIRMING:
            continue
        stamp = str(e.get("ts") or "")[:10]
        try:
            date.fromisoformat(stamp)
        except ValueError:
            continue
        dates.append(stamp)
    return max(dates) if dates else None


def _cmd_export_acceptances(args):
    """Emit accepted risks in the exceptions-register intake shape.

    One-way, by design. `exceptions-register` is the system of record for acceptances:
    the full lifecycle — justification, approver, re-validation as an act, expiry, the
    DORA inventory — lives there. This register keeps the lightweight `accepted` marker it
    always had and feeds it across; it does NOT grow a second re-validation lifecycle, and
    `revalidate` is deliberately absent here. Two homes for the same clock is how the two
    disagree.

    `sourceRiskRef` carries the originating risk id so the import is idempotent: re-running
    the export updates the record it created rather than adding a second one.

    Only risks with a complete acceptance are exported. A risk marked accepted without an
    approver or justification cannot be exported into a register whose whole discipline is
    refusing exactly that, and it is reported rather than silently dropped.
    """
    pos, opt = parse_flags(args)
    if not pos:
        raise ValueError("usage: export-acceptances <register.rr> [--out out.json] "
                         "[--today YYYY-MM-DD]")
    today = _iso_date(opt["today"], "--today") if "today" in opt else _utc_today()
    reg = load_register(pos[0])
    size = reg["settings"]["matrixSize"]
    rows, incomplete, lapsed = [], [], []
    for r in reg["risks"]:
        acc = r.get("acceptance")
        if (r.get("response") or {}).get("type") != "accept" or not acc:
            continue
        missing = [f for f in ("approver", "justification", "revalidationDate")
                   if not str(acc.get(f) or "").strip()]
        if missing:
            incomplete.append((r["id"], missing))
            continue
        # Flagged, never filtered. An expired acceptance is exactly the record the receiving
        # register most needs to see, and dropping it here would hand exceptions-register a
        # clean-looking inventory with the dead entry quietly missing. `expiryDate` already
        # travels in the row below, so the receiver can reach the same verdict independently.
        expiry = acc.get("expiryDate")
        if expiry and str(expiry)[:10] <= today:
            lapsed.append((r["id"], str(expiry)[:10]))
        # Computed with the same two functions `score` uses, on the same settings, rather
        # than read off a scored row — this command walks the raw register. Calling
        # exposure()/band() here means the exported magnitude and the scored one cannot
        # drift apart; re-implementing the arithmetic is how they would.
        res = exposure(r["residual"]["likelihood"], r["residual"]["impact"])
        rows.append({
            "title": r["title"],
            "approver": acc["approver"],
            "justification": acc["justification"],
            "acceptedDate": acc.get("acceptedDate") or "",
            "revalidationDate": acc["revalidationDate"],
            "expiryDate": acc.get("expiryDate") or "",
            "riskIds": [r["id"]],
            "csfSubcategoryIds": ([r["csfSubcategoryId"]]
                                  if r.get("csfSubcategoryId") else []),
            "sourceRiskRef": r["id"],
            # What the acceptance was accepted AGAINST. The receiving register refuses to
            # re-validate against a magnitude measured before its last review, so this is
            # the field that makes "re-measure before you renew" enforceable there rather
            # than aspirational. `measuredAt` is null when nothing ever affirmed the score:
            # a number with no date is reported as exactly that, and the receiver treats it
            # as needing measurement rather than as fresh.
            "magnitude": {
                "value": res,
                "unit": "residual exposure",
                "band": band(res, size),
                "measuredAt": _last_affirmed(reg, r["id"]),
                "source": "risk-register",
            },
        })
    text = json.dumps(rows, indent=2, ensure_ascii=False) + "\n"
    out = _s(opt.get("out")) if isinstance(opt.get("out"), (str, list)) else None
    if out:
        with open(out, "w", encoding="utf-8") as fh:
            fh.write(text)
        print(f"Wrote {out} — {len(rows)} acceptance(s) in exceptions-register intake shape")
        # Only in this branch: stdout is the JSON itself when --out is absent, and a count
        # line there would corrupt anything piping it.
        if lapsed:
            print(f"  {len(lapsed)} of them lapsed — exported as-is, flagged below")
    else:
        sys.stdout.write(text)
    for rid, missing in incomplete:
        print(f"  skipped {rid}: acceptance is missing {', '.join(missing)}", file=sys.stderr)
    for rid, expiry in lapsed:
        print(f"  lapsed {rid}: acceptance expired {expiry} — exported as-is.",
              file=sys.stderr)
    return 0


def _cmd_export_csv(args):
    pos, opt = parse_flags(args)
    if not pos:
        raise ValueError("usage: export-csv <register.rr> [--out out.csv]")
    scored = score_register(load_register(pos[0]))
    cols = ["id", "title", "category", "theme", "owner", "inherentL", "inherentI", "inherentExposure",
            "inherentBand", "response", "cost", "residualL", "residualI", "residualExposure",
            "residualBand", "overAppetite", "status", "reviewDate", "csfSubcategoryId", "provisionalTitle", "provisionalScore"]
    # Python's True/False are not CSV booleans — Excel and every downstream parser expect
    # true/false. Writing the repr leaks the implementation language into an export.
    b = lambda v: "true" if v else "false"          # noqa: E731
    buf = io.StringIO(); w = csv.writer(buf); w.writerow(cols)
    for r in scored["risks"]:
        w.writerow([r["id"], r["title"], r["category"], r.get("theme") or "", r["owner"],
                    r["inherent"]["likelihood"], r["inherent"]["impact"], r["inherentExposure"], r["inherentBand"],
                    r["response"]["type"], r["response"].get("cost", ""),
                    r["residual"]["likelihood"], r["residual"]["impact"], r["residualExposure"], r["residualBand"],
                    b(r["overAppetite"]), r["status"], r.get("reviewDate", ""),
                    r.get("csfSubcategoryId", ""), b(r.get("provisionalTitle")),
                    b(r.get("provisionalScore"))])
    out = _s(opt.get("out")) if isinstance(opt.get("out"), (str, list)) else None
    if out:
        with open(out, "w", newline="", encoding="utf-8") as fh:
            fh.write(buf.getvalue())
        print(f"Wrote {out}")
    else:
        sys.stdout.write(buf.getvalue())
    return 0


COMMANDS = {
    "score": _cmd_score, "import-gaps": _cmd_import_gaps,
    "import-findings": _cmd_import_findings, "self-test": _cmd_self_test,
    "init": _cmd_init, "set-text": _cmd_set_text,
    "add": _cmd_add, "set-score": _cmd_set_score, "accept": _cmd_accept,
    "confirm": _cmd_confirm,
    "set-status": _cmd_set_status, "snapshot": _cmd_snapshot, "export-csv": _cmd_export_csv,
    "export-acceptances": _cmd_export_acceptances,
    "add-theme": _cmd_add_theme, "set-theme": _cmd_set_theme,
    "set-escalation": _cmd_set_escalation, "escalations": _cmd_escalations,
    "set-currency": _cmd_set_currency, "set-response": _cmd_set_response,
}


def main(argv: list[str]) -> int:
    if len(argv) < 2 or argv[1] not in COMMANDS:
        print(__doc__)
        return 0 if (len(argv) >= 2 and argv[1] in ("-h", "--help")) else 2
    return COMMANDS[argv[1]](argv[2:])


if __name__ == "__main__":
    try:
        rc = main(sys.argv)
    except (ValueError, FileNotFoundError, KeyError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        rc = 1
    raise SystemExit(rc)
