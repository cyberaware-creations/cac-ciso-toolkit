#!/usr/bin/env python3
"""assemble_pack.py — stitch the section objects into one board pack.

The assembler **owns no data**. Every fact in a pack already lives in a producer's store and
has already been translated to board language by `ciso-board-translation`. What this script
adds is the part no producer can: one order, one through-line, one consolidated list of
decisions, and one honest account of what was missing.

Any temptation to *compute* a section's content belongs back in the producing skill. If you
find yourself adding a count, a band or a trend here, that is the bug.

Two responsibilities:

  **Validate.** Every `*.board.json` is checked against
  `references/section-contract.md` — the section name, the contract version, the exact item-key
  spelling, and the nesting. The flat per-item map is the dangerous one: it parses, so the
  render "succeeds", and every narrative silently falls back to a placeholder while the deck
  looks finished.

  **Assemble.** Deterministic ordering by audience, decisions deduplicated on text and never on
  meaning, cross-section counts, and a provenance record naming everything that was absent.

Standard library only. Subcommands:

  validate  <pack.manifest.json>
  assemble  <pack.manifest.json> [--out pack.json]
  self-test

See references/pack-structure.md for the order, the merge rule and the audience variants.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from datetime import date

# The graphics library owns the colour contract, including which brand tokens a client may
# override and the contrast floors an override has to clear. It is imported here — rather
# than the rules being restated — so a brand block is refused by `validate`, before a pack
# is assembled and rendered, instead of at render time when the operator has moved on.
# One copy of the floors, checked at the earliest moment they can be checked.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "renderers"))
import cac_graphics as _G  # noqa: E402

MANIFEST_VERSION = 1
CONTRACT_VERSION = 1

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

AUDIENCES = ("board", "audit-committee")

# The exact per-section item keys, from section-contract.md. Spelling is exact: this table is
# the enforcement the contract file promises.
SECTION_KEYS = {
    "risk": ("risks", "themes"),
    "posture": ("gaps",),
    "metrics": ("metrics",),
    "exceptions": ("acceptances", "exceptions"),
    "incident": ("incidents",),
}

# `nist-csf` accepts `subcategories` as an alias for `gaps`. The contract says a validator may
# warn on it and MUST NOT reject it — every sidecar written before the contract existed is a
# valid v1 document.
DEPRECATED_ALIASES = {"posture": {"subcategories": "gaps"}}

# Keys the envelope owns. Anything else that is a dict is a suspected mis-spelled item map.
ENVELOPE_KEYS = ("section", "executiveSummary", "decisions", "asOf", "contractVersion")

SECTION_ORDER = {
    # The frame first, then what we carry, how it moves, what we accepted, what happened.
    "board": ("posture", "risk", "metrics", "exceptions", "incident"),
    # An audit committee convened to examine controls, exceptions and incidents. That leads.
    "audit-committee": ("incident", "exceptions", "risk", "posture", "metrics"),
}

SECTION_TITLE = {
    "posture": "Framework posture",
    "risk": "Risk",
    "metrics": "Metrics",
    "exceptions": "Accepted risks and exceptions",
    "incident": "Incidents",
    "pack": "Executive through-line",
}

# The through-line is an ordinary section-contract document whose section name no producer
# emits, because the assembler is its producer.
PACK_SECTION = "pack"


class Refusal(Exception):
    """A pack the assembler declines to build, with the reason a user can act on."""


def check_date(value, field: str) -> str:
    if not isinstance(value, str) or not DATE_RE.match(value):
        raise Refusal(f"{field} must be a canonical zero-padded date, YYYY-MM-DD; "
                      f"got {value!r}")
    try:
        date.fromisoformat(value)
    except ValueError:
        raise Refusal(f"{field} is not a real calendar date: {value!r}")
    return value


def _read_json(path: str, what: str) -> dict:
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        raise Refusal(f"no such {what}: {path}")
    except json.JSONDecodeError as exc:
        raise Refusal(f"{path} is not valid JSON (line {exc.lineno}, column {exc.colno}): "
                      f"{exc.msg}")


# --- The client brand ---------------------------------------------------------

def resolve_brand(value, base: str) -> dict:
    """Resolve a manifest `brand` — inline object or path — into a checked brand block.

    A client may re-colour the chrome and the measure bucket. A client may not re-colour
    RAG: those hexes carry measured contrast and colour-vision separation, and a substituted
    palette would discard both while still producing a chart that looked fine. The graphics
    library holds that rule; this function only decides *where the block came from* and
    refuses early if it fails.

    Returns {} for "no override", which renders CAC. An empty dict and an absent key mean the
    same thing here, which is why an absent key is not an error.
    """
    if value is None:
        return {}
    if isinstance(value, str):
        path = os.path.normpath(os.path.join(base, value))
        value = _read_json(path, "brand")
        if not isinstance(value, dict):
            raise Refusal(f"{path} must contain a JSON object, got {type(value).__name__}")
    if not isinstance(value, dict):
        raise Refusal("manifest 'brand' must be an object or a path to one, "
                      f"got {type(value).__name__}")
    problems = _G.validate_brand(value)
    if problems:
        raise Refusal("the brand override was refused:\n  - " + "\n  - ".join(problems))
    return value


# --- The manifest -------------------------------------------------------------

def load_manifest(path: str) -> dict:
    """Read and check the manifest. Paths inside it resolve relative to its own directory.

    Relative-to-the-manifest rather than relative-to-the-cwd, so a manifest committed beside
    its sources keeps working from any working directory — which is how it will be run from a
    Makefile, a CI job and a shell, all three with different cwds.
    """
    raw = _read_json(path, "manifest")
    if not isinstance(raw, dict):
        raise Refusal(f"{path} must contain a JSON object, got {type(raw).__name__}")
    version = raw.get("manifestVersion", MANIFEST_VERSION)
    if version != MANIFEST_VERSION:
        raise Refusal(f"{path} declares manifestVersion {version!r}; this assembler "
                      f"implements {MANIFEST_VERSION}")
    audience = raw.get("audience") or "board"
    if audience not in AUDIENCES:
        raise Refusal(f"audience must be one of {', '.join(AUDIENCES)}; got {audience!r}")
    check_date(raw.get("asOf"), "asOf")
    sections = raw.get("sections")
    if not isinstance(sections, list) or not sections:
        raise Refusal(f"{path} must declare a non-empty 'sections' list")
    base = os.path.dirname(os.path.abspath(path))
    seen = []
    for i, entry in enumerate(sections):
        if not isinstance(entry, dict):
            raise Refusal(f"sections[{i}] must be an object, got {type(entry).__name__}")
        name = entry.get("section")
        if name not in SECTION_KEYS:
            raise Refusal(
                f"sections[{i}] declares section {name!r}, which is not one of "
                f"{', '.join(sorted(SECTION_KEYS))}. See "
                f"skills/board-pack/references/section-contract.md.")
        if name in seen:
            raise Refusal(f"section {name!r} is declared twice; one pack holds one of each")
        seen.append(name)
        for key in ("translations", "store"):
            if entry.get(key):
                entry[key + "Path"] = os.path.normpath(os.path.join(base, entry[key]))
    if raw.get("throughLine"):
        raw["throughLinePath"] = os.path.normpath(os.path.join(base, raw["throughLine"]))
    # CAC-AP-1. Optional, and absent is the normal case: a pack with no profile assembles
    # exactly as it did before, against every producer's full question set — which is the
    # safe direction and the one §2.2 requires.
    if raw.get("context"):
        raw["contextPath"] = os.path.normpath(os.path.join(base, raw["context"]))
    raw["brand"] = resolve_brand(raw.get("brand"), base)
    raw["audience"] = audience
    raw["manifestDir"] = base
    raw["manifestPath"] = os.path.abspath(path)
    return raw


# --- The section contract -----------------------------------------------------

def validate_section(name: str, raw: dict, path: str) -> dict:
    """Check one `*.board.json` against the contract. Returns {'warnings': [...], ...}.

    Errors are refusals — a section that half-renders is worse than one that does not render,
    because only one of those gets noticed. Warnings are surfaced on the provenance page and
    do not stop a pack.
    """
    warnings = []
    if not isinstance(raw, dict):
        raise Refusal(f"{path} must contain a JSON object, got {type(raw).__name__}")

    allowed = set(SECTION_KEYS[name]) if name in SECTION_KEYS else set()
    aliases = DEPRECATED_ALIASES.get(name, {})

    version = raw.get("contractVersion", CONTRACT_VERSION)
    if version != CONTRACT_VERSION:
        raise Refusal(
            f"{path} declares contractVersion {version!r}; this assembler implements "
            f"{CONTRACT_VERSION}. A section that half-renders is worse than one that does "
            f"not, so this is refused rather than best-efforted.")

    declared = raw.get("section")
    if declared is not None and declared != name:
        raise Refusal(f"{path} is a {declared!r} section but the manifest declares it as "
                      f"{name!r}. Pass the sidecar written for this section.")

    # The flat map. It parses, so without this the pack "succeeds" and every narrative falls
    # back to a placeholder while the deck looks finished.
    #
    # The test is narrow on purpose, and the limit is worth stating: the contract allows
    # passthrough string keys (`generatedBy`, and anything else it does not name), so a stray
    # top-level string cannot be rejected on sight. What can be rejected is a document with
    # stray strings and NO recognised content at all — which is what a flat map is. A sidecar
    # carrying a real summary AND a stray `"R-001": "..."` at top level is not caught here;
    # it renders correctly and the stray key is ignored, exactly as the contract says.
    #
    # `section` is a string too, so it and its fellow envelope keys are excluded — otherwise a
    # legitimately empty `{"section": "metrics"}` would be refused as a flat map, which is the
    # first thing this test did before that exclusion existed.
    item_maps = {k: v for k, v in raw.items() if isinstance(v, dict)}
    stray_strings = {k for k, v in raw.items()
                     if isinstance(v, str) and k not in ENVELOPE_KEYS}
    known_content = bool(item_maps) or raw.get("executiveSummary") or raw.get("decisions")
    if not known_content and stray_strings:
        raise Refusal(
            f'{path} looks like a flat {{"id": "sentence"}} map. Wrap it: '
            f'{{"{SECTION_KEYS[name][0]}": {{ ... }}}}. A flat map parses, so the pack would '
            f"assemble with every narrative silently replaced by a placeholder.")

    for key in item_maps:
        if key in allowed:
            continue
        if key in aliases:
            warnings.append(f"{path} uses the deprecated key {key!r}; "
                            f"{aliases[key]!r} is canonical")
            continue
        if key in ENVELOPE_KEYS:
            continue
        raise Refusal(
            f"{path} carries an item map named {key!r}, which is not a key of the {name!r} "
            f"section. Expected {' and '.join(repr(k) for k in SECTION_KEYS[name])}. "
            f"The spelling is exact — see section-contract.md.")

    if raw.get("asOf"):
        check_date(raw["asOf"], f"{path}:asOf")

    items = {}
    for key in SECTION_KEYS[name]:
        items[key] = dict(raw.get(key) or {})
    for alias, canonical in aliases.items():
        if raw.get(alias):
            items[canonical].update(raw[alias])

    total = sum(len(v) for v in items.values())
    if not total and not raw.get("executiveSummary"):
        warnings.append(f"the {name!r} section carries no items and no executive summary")
    if not raw.get("decisions"):
        warnings.append(f"the {name!r} section asks for no decision")

    return {
        "section": name,
        "path": path,
        "executiveSummary": raw.get("executiveSummary") or None,
        "items": items,
        "itemCount": total,
        "decisions": normalise_decisions(raw.get("decisions"), path),
        "asOf": raw.get("asOf") or None,
        "contractVersion": version,
        "warnings": warnings,
    }


ALTITUDES = ("board", "management")


def normalise_decisions(raw, path: str) -> list:
    """Every decision as `{"text", "altitude"}`, from either shipped shape.

    A decision may be written as a bare string, or as `{"text": ..., "altitude": ...}`.
    A string means **unclassified**, not "board" — the difference matters, because guessing
    the altitude of an ask is exactly the inference this toolkit does not make. An
    unclassified ask stays in front of the board, which is the safe direction to fail: a
    management action shown to a board wastes five minutes, and a board decision quietly
    filed as a management action is a decision nobody took.

    Altitude is **declared by the producer, never inferred here.** Only the skill that
    raised the ask knows whether it needs a board, and no amount of reading the sentence
    tells the assembler. This follows the vanity flag: a human sets it, the engine reports
    it, and nothing pattern-matches its way to a governance judgement.
    """
    out = []
    for entry in raw or []:
        if isinstance(entry, str):
            text, altitude = entry, None
        elif isinstance(entry, dict):
            text = entry.get("text")
            altitude = entry.get("altitude")
            if not isinstance(text, str) or not text.strip():
                raise Refusal(
                    f"{path} carries a decision object with no 'text'. A decision the board "
                    f"cannot read is not a decision — see section-contract.md.")
            if altitude is not None and altitude not in ALTITUDES:
                raise Refusal(
                    f"{path} carries a decision with altitude {altitude!r}. Expected one of "
                    f"{' or '.join(repr(a) for a in ALTITUDES)}, or the key omitted. An "
                    f"unrecognised altitude is refused rather than defaulted, because "
                    f"defaulting it would silently re-file somebody's board decision.")
        else:
            raise Refusal(
                f"{path} carries a decision that is neither a string nor an object "
                f"({type(entry).__name__}). See section-contract.md.")
        if str(text or "").strip():
            out.append({"text": str(text).strip(), "altitude": altitude})
    return out


def validate_pack(manifest: dict) -> dict:
    """Validate every declared section. Collects warnings; raises on the first error."""
    sections, warnings, missing = [], [], []
    for entry in manifest["sections"]:
        name = entry["section"]
        path = entry.get("translationsPath")
        if not path:
            missing.append(f"the {name!r} section declares no translations sidecar; "
                           f"it will render placeholders")
            sections.append({"section": name, "path": None, "executiveSummary": None,
                             "items": {k: {} for k in SECTION_KEYS[name]}, "itemCount": 0,
                             "decisions": [], "asOf": None,
                             "contractVersion": CONTRACT_VERSION, "warnings": []})
            continue
        raw = _read_json(path, f"{name} section sidecar")
        result = validate_section(name, raw, path)
        warnings.extend(result["warnings"])
        sections.append(result)
        store = entry.get("storePath")
        if store and not os.path.exists(store):
            missing.append(f"the {name!r} section declares store {entry['store']!r}, "
                           f"which does not exist")

    # asOf drift. A warning, not an error: mixing a July posture with a June metric snapshot
    # is sometimes deliberate and always worth seeing.
    dates = sorted({s["asOf"] for s in sections if s["asOf"]})
    if len(dates) > 1:
        detail = ", ".join(f'{s["section"]}={s["asOf"]}' for s in sections if s["asOf"])
        warnings.append(f"sections are dated differently ({detail}); a pack that mixes "
                        f"snapshots is sometimes deliberate and always worth seeing")

    return {"sections": sections, "warnings": warnings, "missing": missing,
            "sectionDates": dates}


# --- Assembly: order, decisions, rollups --------------------------------------

def order_sections(sections: list, audience: str) -> list:
    """Sections in this audience's fixed order, omitting the ones not present.

    Fixed matters. A pack whose section positions move quarter to quarter forces every
    reader to re-navigate and makes two quarters impossible to compare side by side.
    """
    by_name = {s["section"]: s for s in sections}
    return [by_name[name] for name in SECTION_ORDER[audience] if name in by_name]


def _normalise_decision(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip().rstrip(".;:!?").casefold()


def consolidate_decisions(ordered: list, through_line: dict = None) -> list:
    """Every section's asks, merged into one list, in audience order.

    Deduplicated on a **normalised form only** — case-folded, whitespace-collapsed, trailing
    punctuation dropped. Two differently-worded asks stay two entries, always. The assembler
    cannot tell a genuine duplicate from two asks that happen to rhyme, and collapsing them
    on meaning would silently delete a decision the board was supposed to make.

    First appearance wins its position; a later duplicate only adds its section.

    The through-line's own asks go **first**, labelled `pack`. They are the cross-cutting ones
    — the asks that only something seeing every section could make — and a board that reads
    the synthesis and then meets the same ask again five sections later has been asked twice
    for one decision.
    """
    out, index = [], {}
    sources = list(ordered)
    if through_line and through_line.get("decisions"):
        sources.insert(0, {"section": PACK_SECTION,
                           "decisions": normalise_decisions(
                               through_line["decisions"], "the through-line sidecar")})
    for section in sources:
        for raw in section["decisions"]:
            text, altitude = raw["text"], raw["altitude"]
            if not text.strip():
                continue
            key = _normalise_decision(text)
            if key in index:
                entry = out[index[key]]
                if section["section"] not in entry["sections"]:
                    entry["sections"].append(section["section"])
                # Two sections wording one ask identically but filing it at different
                # altitudes is a disagreement between producers, not a merge conflict to
                # resolve here. Keep the higher one — the board seeing an ask it did not
                # need is recoverable; the board never seeing it is not.
                if entry["altitude"] != altitude and "board" in (entry["altitude"], altitude):
                    entry["altitude"] = "board"
                elif entry["altitude"] is None:
                    entry["altitude"] = altitude
            else:
                index[key] = len(out)
                out.append({"text": text, "sections": [section["section"]],
                            "altitude": altitude})
    return out


# Record ids as the producers mint them: R-003, A-002, X-001, M-001, I-002, and the CSF
# Subcategory form PR.DS-01. Used only to notice that two sections named the same record.
RECORD_ID_RE = re.compile(r"\b(?:[A-Z]{1,2}-\d{3,}|[A-Z]{2}\.[A-Z]{2}-\d{2})\b")


def possible_duplicate_asks(decisions: list) -> list:
    """Flag asks from different sections that name the same record, without merging them.

    The merge rule is textual and never semantic, for a good reason: the assembler cannot
    tell a real duplicate from two asks that happen to rhyme, and collapsing them would
    delete a decision the board was supposed to make. But the failure that rule permits is
    real — the exceptions section asking to "re-validate A-002 or withdraw it" and the
    incident section asking to "re-confirm or withdraw A-002" are one decision arriving
    twice, and a board asked twice for one decision is the thing consolidation exists to
    prevent.

    So: notice, name, and leave both entries standing. Surfacing beats smoothing over, and
    the person who can tell whether they are the same ask is the one writing the pack.
    """
    by_id = {}
    for entry in decisions:
        for rid in set(RECORD_ID_RE.findall(entry["text"])):
            by_id.setdefault(rid, []).append(entry)
    notes = []
    for rid, entries in sorted(by_id.items()):
        sections = []
        for entry in entries:
            for name in entry["sections"]:
                if name not in sections:
                    sections.append(name)
        if len(entries) > 1 and len(sections) > 1:
            notes.append(
                f"{len(entries)} separate decisions name {rid} ({', '.join(sections)}). "
                f"They were not merged — the wording differs and this assembler never merges "
                f"on meaning — but they may be one ask arriving twice.")
    return notes


# Each producer computes its own figures. The assembler runs the producer's analysis and
# READS them. It does not recompute a count, a band or a trend — any temptation to do so
# belongs back in the producing skill, and a headline the assembler derived would be a second
# number that could disagree with the section it sits above.
# --- Carrying severity, not deciding it ---------------------------------------
#
# A headline figure may carry a `sev` so the pack can show at a glance which
# numbers are the bad ones. Every rule below is the same rule the rest of this
# file follows for figures: the assembler READS what a producer declared and
# never decides anything itself.
#
# Two consequences worth stating, because both are easy to get wrong later:
#
#   * A `sev` is the WORST band the producer already declared among the items a
#     headline counts. It is not derived from the count. "3 risks over appetite"
#     is critical because one of those three risks is declared critical, not
#     because three is a lot of risks.
#   * A count of zero carries no `sev` at all. Nothing over appetite is the good
#     outcome, and colouring that zero red because it sits in the breach row
#     would report an alarm the number itself contradicts.
#
# Each producer names its bands in its own vocabulary. The translations below are
# stated once, per producer, and are translations only — never judgements. Where
# a producer declares nothing for a figure, the figure carries no sev and renders
# neutral, which is the honest rendering of "this is a population, not a status".
SEV_ORDER = ("good", "medium", "high", "critical")

# risk-register calls its lowest band `low`; the shared vocabulary calls it
# `good`. The other three names already agree.
RISK_BAND_SEV = {"low": "good", "medium": "medium",
                 "high": "high", "critical": "critical"}

# metrics-register bands on warn and critical only; anything past warn is ok.
# `warn` maps to `high`, not `medium`, so the pack agrees with the metric's own
# bullet — see skills/metrics-register/renderers/_common.py STATUS_SEV.
METRIC_STATUS_SEV = {"ok": "good", "warn": "high", "critical": "critical"}


def _worst(sevs):
    """The most severe band among those declared. None when none were.

    None is a real answer and not a failure: it means the producer declared no
    band for anything counted here, so the pack has nothing to colour with.
    """
    present = [s for s in sevs if s in SEV_ORDER]
    return max(present, key=SEV_ORDER.index) if present else None


# --- Figures: the chartable series behind each section ------------------------
#
# A headline is one number. A figure is a series a mark can be drawn from, and it obeys
# exactly the same rule: every value is lifted from a field the producer computed. The
# assembler picks *which* series is worth a board's attention and what kind of mark suits
# it — that is a presentation judgement, not a fact — but it never sums, counts or bands
# anything. Where a producer had no rollup to lift, the rollup was added to that producer
# (see exceptions-register and incident-materiality `counts.byBand`) rather than computed
# here, because a count derived in two places is a count that can disagree with itself.
#
# Every figure carries `source`, naming the analysis field it came from. That turns "read,
# not computed" from a claim in a doc into something a reader can check, and it is what the
# provenance page prints.
#
# Three kinds, and the colour contract decides which colour each gets:
#   bar       a categorical measure. No thresholds, so MEASURE — never RAG.
#   band-mix  a population split by a band the producer declared. RAG is legitimate here
#             precisely because the bands are declared rather than inferred.
#   bullet    one thresholded metric against its target, with its zones.

FIGURE_KINDS = ("bar", "band-mix", "bullet")

# A board pack is a document, not a dashboard. Past this many bullets the metrics page
# stops being read and starts being flipped past. What is dropped is named on the
# provenance page — a silent cap reads as "this is all of them".
MAX_METRIC_BULLETS = 6


def _posture_figures(a):
    by_fn = (a.get("coverage") or {}).get("byFunction") or {}
    if not by_fn:
        return []
    # `percent` is null for a Function with nothing assessed, and it is carried through as
    # null rather than dropped or zeroed. Both alternatives lie: zero says "assessed, and
    # covers nothing", and omission says the Function does not exist. Unassessed is its own
    # state and the mark draws it as one.
    series = [{"label": fid, "value": v.get("percent")} for fid, v in by_fn.items()]
    return [{"kind": "bar", "title": "Subcategory coverage by CSF Function",
             "unit": "percent", "series": series, "source": "coverage.byFunction",
             # No sev, for the reason the headline gives: a low coverage figure may be a
             # deliberately low Target that is fully met. Coverage is a measure.
             "note": "Coverage against Target. A Function with nothing assessed is shown "
                     "as unassessed, not as zero."}]


def _risk_figures(a):
    by_band = (a.get("summary") or {}).get("byBand") or {}
    if not by_band:
        return []
    series = [{"label": b.capitalize(), "value": by_band.get(b, 0),
               "sev": RISK_BAND_SEV[b]}
              for b in ("low", "medium", "high", "critical") if b in by_band]
    return [{"kind": "band-mix", "title": "Open risks by residual band",
             "series": series, "source": "summary.byBand"}]


def _metrics_figures(a):
    out = []
    for m in a.get("metrics") or []:
        thr = m.get("threshold")
        # A metric with no threshold has no zones, so it has no bullet to draw. It is not
        # missing from the pack — it is in the metrics section as a sentence like every
        # other. It simply has nothing for this kind of mark to say.
        if not thr or m.get("value") is None:
            continue
        fig = {"kind": "bullet", "title": m.get("name"), "unit": m.get("unit"),
               "value": m.get("value"), "direction": m.get("direction"),
               "threshold": thr, "source": "metrics[%s]" % m.get("metricId")}
        sev = METRIC_STATUS_SEV.get(m.get("status"))
        if sev is not None:
            fig["sev"] = sev
        out.append(fig)
    return out


def _exceptions_figures(a):
    by_band = (a.get("counts") or {}).get("byBand") or {}
    if not by_band:
        return []
    # `expired` and `closed` are lifecycle termini rather than severities, and the register's
    # own renderers hold them apart from the RAG bands for that reason. `expired` carries no
    # sev here and takes the unassessed treatment in the mix.
    sev_by_band = {"current": "good", "revalidation-due": "high",
                   "revalidation-overdue": "critical"}
    label = {"current": "Current", "revalidation-due": "Re-validation due",
             "revalidation-overdue": "Re-validation overdue", "expired": "Expired"}
    series = []
    for band, count in by_band.items():
        item = {"label": label.get(band, band), "value": count}
        if band in sev_by_band:
            item["sev"] = sev_by_band[band]
        series.append(item)
    fig = {"kind": "band-mix", "title": "Active acceptances and exceptions by band",
           "series": series, "source": "counts.byBand"}
    # This mix partitions the *active* records, so it sums to `active` and not to the total
    # the section may quote elsewhere. Saying which population is being split is not
    # optional: a chart summing to 4 beside a figure reading 6 makes a reader do arithmetic
    # to discover it was never the same population, and some of them will conclude one of
    # the two is wrong. The closed count is read, not subtracted.
    # Named unconditionally, including when nothing was excluded. "Active records only"
    # is true whether or not a closed record happens to exist this quarter, and a note that
    # appeared only when the excluded count was non-zero would make its own absence
    # meaningful — a reader would have to know the rule to read the silence.
    closed = (a.get("counts") or {}).get("closed") or 0
    fig["note"] = ("Active records only. %s not shown."
                   % ("No closed records" if not closed else
                      "%d closed record%s" % (closed, "" if closed == 1 else "s")))
    return [fig]


def _incident_figures(a):
    by_band = (a.get("counts") or {}).get("byBand") or {}
    # Every band, including the empty ones, is what the producer returns — but a board pack
    # that drew nine segments of which six were zero would spend a whole mark saying
    # nothing. The empty ones are dropped from the *drawing* and the total is unchanged,
    # because the segments that remain still sum to `open`.
    present = {b: n for b, n in by_band.items() if n}
    if not present:
        return []
    sev_by_band = {"disclosure-overdue": "critical", "disclosure-due": "high",
                   "material": "high", "not-material": "good", "filed": "good"}
    label = {"no-determination": "No determination", "assessing": "Under assessment",
             "not-yet-determinable": "Not yet determinable", "not-material": "Not material",
             "material": "Material", "disclosure-due": "Reporting window open",
             "disclosure-overdue": "Past a reporting deadline", "filed": "Reported"}
    series = []
    for band, count in present.items():
        item = {"label": label.get(band, band), "value": count}
        if band in sev_by_band:
            item["sev"] = sev_by_band[band]
        series.append(item)
    # Same rule as the exceptions mix, and here it matters more: this partitions the *open*
    # incidents, so it sums to `open` while the headline beside it counts every incident in
    # the period. Both counts come from the producer; neither is a subtraction.
    closed = (a.get("counts") or {}).get("closed") or 0
    note = ("Open incidents only; bands with none are not drawn. %s not shown."
            % ("No closed incidents" if not closed else
               "%d closed incident%s" % (closed, "" if closed == 1 else "s")))
    return [{"kind": "band-mix", "title": "Open incidents by band",
             "series": series, "source": "counts.byBand", "note": note}]


# --- Escalations: read from the producers, aggregated, never derived --------------
#
# CAC-EL-1 §1.3. An escalation is a derived, stateless determination made by the skill that
# owns the clock — a crossed band, a lapsed acceptance, a metric past its threshold. This
# assembler collects them and orders them; it decides nothing about them, on exactly the same
# terms as every headline figure. A pack that computed an escalation would be a second opinion
# able to contradict the section printed beside it.
#
# Only `risk-register` emits them today. The others are absent rather than empty, which is why
# this is a per-producer adapter and not a field the collector assumes: a skill that escalates
# nothing and a skill that cannot escalate yet are different states, and the provenance page
# says which is which.

ESCALATION_KEYS = ("subjectRef", "subjectKind", "trigger", "severity", "since", "evidence")

# Optional, and read only by the duplicate check below. A producer sets it when it can name,
# from data it already holds, the record in ANOTHER skill that its subject is the same thing
# as. Nothing here infers one: an absent or null `relatedRef` means no link was declared, and
# the assembler never goes looking for one.
ESCALATION_LINK_KEY = "relatedRef"


def possible_duplicate_escalations(escalations: list) -> list:
    """Flag escalations from different producers about one underlying record, without merging.

    The failure is real. `exceptions-register` owns the acceptance lifecycle and escalates
    `expired` on the authoritative record; `risk-register` keeps its own lightweight
    `accepted` marker and escalates `acceptance-lapsed` on that. One expiry, two entries, and
    — because each skill severities its own concern on its own terms — often two different
    severities for the same day. A board reading "one critical and one high" counts two
    problems.

    This is the same answer the assembler gives to two sections asking for one decision:
    notice, name, leave both standing. With one difference in its favour. `possible_duplicate_asks`
    regexes ids out of free prose and can only say the two *may* be the same ask, because it
    cannot tell a real duplicate from two asks that rhyme. Here the join is declared — the
    producer stamped `relatedRef` from a field it owns — so the identity is a fact, and the
    only judgement left is whether one fact reported twice needs saying twice.

    Merging is still refused, for the reason it is always refused: the two records were
    derived by two skills that each own a clock, and an assembler that dropped one would be
    deciding which owner was right. Reporting both, and saying they are linked, leaves that
    where it belongs.
    """
    by_id, notes = {}, []
    for e in escalations:
        keys = {e["subjectRef"]}
        link = e.get(ESCALATION_LINK_KEY)
        if link:
            keys.add(link)
        for key in keys:
            by_id.setdefault(key, []).append(e)
    for key, group in sorted(by_id.items()):
        sections = []
        for e in group:
            if e.get("section") not in sections:
                sections.append(e.get("section"))
        # Two triggers from ONE producer on one subject is ordinary and already ordered —
        # an incident with a missing anchor and a superseded determination is two facts, not
        # one reported twice. Only a cross-producer collision is the failure described above.
        #
        # This is the whole condition. An earlier version also guarded `len(group) < 2`,
        # which cannot fire: two distinct sections need two escalations to carry them, so
        # the group is already at least that big. Mutation testing found it unreachable and
        # it came out rather than staying as a branch no test could ever justify.
        if len(sections) < 2:
            continue
        named = ", ".join(sorted(
            "{} {} ({})".format(e.get("section"), e["subjectRef"], e["trigger"])
            for e in group))
        severities = sorted({e["severity"] for e in group})
        note = ("{} escalations are linked to the same record {}: {}. They were not merged — "
                "each was derived by the skill that owns that clock — but they may be one "
                "fact reported twice.".format(len(group), key, named))
        if len(severities) > 1:
            # Worth its own sentence. A reader who spots the duplicate still has to decide
            # which severity the board sees, and the pack must not quietly pick.
            note += (" They also disagree on severity ({}), so the same day reads as two "
                     "different sizes of problem.".format(", ".join(severities)))
        notes.append(note)
    return notes


def _risk_escalations(a):
    """The escalations risk-register derived. Lifted whole, not re-read field by field.

    Carried verbatim so the record the board sees is the record the producer emitted. Picking
    it apart here and rebuilding it would be the assembler asserting a shape, and the shape
    belongs to the contract.
    """
    return list(a.get("escalations") or [])


def _metrics_escalations(a):
    """The escalations metrics-register derived. Same contract, different subjectKind.

    The second producer, and the one that tests whether §1.3 actually generalises: a
    breached metric and a crossed risk band arrive here in one shape, and the pack orders
    them together without knowing anything about either skill's clock.
    """
    return list(a.get("escalations") or [])


def _exceptions_escalations(a):
    """The escalations exceptions-register derived — it owns the acceptance clock.

    Third producer, third subjectKind vocabulary (`acceptance` / `exception`). The pack
    still knows nothing about any of them: it orders by severity and prints what it was
    handed, which is the whole claim §1.3 makes.
    """
    return list(a.get("escalations") or [])


def _incident_escalations(a):
    """The escalations incident-materiality derived — statutory clocks, and only those.

    Fourth producer, and the narrowest of the four by design. This one emits no verdict, so
    what arrives here is a passed deadline, an absent anchor or a record that moved after a
    determination — never a judgment about materiality. The pack ranks it beside a crossed
    risk band and a breached metric and, as with the other three, understands none of them.
    """
    return list(a.get("escalations") or [])


def _posture_headline(a):
    # No sev on either figure. A gap is a distance from a Target, and this skill
    # is explicit that a low coverage figure may be a deliberately low Target
    # that is fully met -- so a gap count is not a severity and must not be
    # coloured as one. See skills/nist-csf/assets/brand.md.
    completeness = (a.get("completeness") or {}).get("overall") or {}
    return [("outcomes short of target", len(a.get("gaps") or [])),
            ("outcomes assessed", completeness.get("assessed"))]


def _risk_headline(a):
    summary = a.get("summary") or {}
    # The band each over-appetite risk already carries. Read, not derived: the
    # engine writes residualBand and overAppetite onto every risk.
    over = [RISK_BAND_SEV.get(r.get("residualBand"))
            for r in (a.get("risks") or []) if r.get("overAppetite")]
    out = [("risks over appetite", summary.get("overAppetite"), _worst(over)),
           ("risks tracked", summary.get("total"))]
    # Money, at last. The register has always recorded `response.cost`; nothing ever showed
    # it, so a pack could carry eleven risks and not one figure a board could act on.
    #
    # The string and the counts both come from the producer — the assembler formats nothing
    # and sums nothing, which is the same rule every other headline follows. The label
    # carries `priced/of` because a total without its denominator is the false precision
    # this pack refuses everywhere else.
    tc = summary.get("treatmentCost") or {}
    if tc.get("priced"):
        label = f"recorded treatment cost, {tc['priced']} of {tc['of']} open risks priced"
        if not tc.get("currencyRecorded"):
            label += " (currency not recorded)"
        out.append((label, tc.get("display")))
    return out


def _metrics_headline(a):
    att = a.get("attention") or {}
    breached = set(att.get("breached") or [])
    worsening = set(att.get("worsening") or [])
    by_id = {m.get("metricId"): m for m in (a.get("metrics") or [])}

    def sev_of(ids):
        return _worst(METRIC_STATUS_SEV.get((by_id.get(i) or {}).get("status"))
                      for i in ids)

    return [("metrics past a threshold", len(breached), sev_of(breached)),
            # A trend is not a band, so this figure carries the worst status
            # among the metrics that are moving the wrong way, not a severity
            # invented from the direction of travel.
            ("metrics moving the wrong way", len(worsening), sev_of(worsening)),
            # The population, which this producer alone was not supplying.
            #
            # `_risk_headline` states the rule two hundred lines up — "a total without its
            # denominator is the false precision this pack refuses everywhere else" — and
            # posture, risk, exceptions and incident all follow it. Metrics did not, so a
            # pack carried "3 metrics past a threshold" with nothing anywhere saying
            # whether that was three of four or three of forty.
            #
            # It reads worst on an empty register, where the two figures above are both
            # zero and a board slide says the metrics programme is healthy when what it
            # means is that nobody has recorded a metric. That is the same failure
            # `nist-csf` suppresses its coverage figure to avoid, and it went unseen here
            # because every fixture in this suite is populated.
            #
            # A population takes no sev, per the note in `_exceptions_headline`.
            ("metrics tracked", (a.get("counts") or {}).get("metrics", len(by_id)))]


def _exceptions_headline(a):
    att = a.get("attention") or {}
    overdue = att.get("overdue") or []
    # Overdue is a lapsed clock the producer already declared -- a real
    # threshold, crossed -- so it is legitimately critical. The count of items
    # carried is a population and takes no sev.
    return [("acceptances and exceptions carried", (a.get("counts") or {}).get("active")),
            ("overdue for re-validation", len(overdue),
             "critical" if overdue else None)]


def _incident_headline(a):
    att = a.get("attention") or {}
    due = att.get("due") or []
    # An open reporting window is a declared statutory clock, not a judgement
    # about the incident. It is high rather than critical: the window being open
    # is the state to act on; missing it would be the breach.
    return [("incidents in the period", (a.get("counts") or {}).get("incidents")),
            ("reporting windows open", len(due), "high" if due else None)]


PRODUCERS = {
    "posture": {"skill": "nist-csf", "script": "scripts/profile_analysis.py",
                "argv": ["analyze", "{store}", "--today", "{asOf}"],
                "headline": _posture_headline, "figures": _posture_figures},
    # `--today` matters here and did not before. The escalation triggers that depend on a
    # date — a lapsed acceptance, a long dwell over appetite — are skipped rather than guessed
    # when the producer is given no reference date, so a pack assembled without it would
    # report fewer escalations than the same register reports on the same day. One number,
    # one answer: the pack dates the producer exactly as it dates every other section.
    "risk": {"skill": "risk-register", "script": "scripts/score_register.py",
             "argv": ["score", "{store}", "--json", "--today", "{asOf}"],
             "headline": _risk_headline, "figures": _risk_figures,
             "escalations": _risk_escalations},
    "metrics": {"skill": "metrics-register", "script": "scripts/metrics_analysis.py",
                "argv": ["analyze", "{store}", "--today", "{asOf}"],
                "headline": _metrics_headline, "figures": _metrics_figures,
                "escalations": _metrics_escalations},
    "exceptions": {"skill": "exceptions-register", "script": "scripts/exceptions_register.py",
                   "argv": ["analyze", "{store}", "--today", "{asOf}"],
                   "headline": _exceptions_headline, "figures": _exceptions_figures,
                   "escalations": _exceptions_escalations},
    # `context: True` says this producer accepts `--context`. Declared per adapter and
    # never assumed: passing the flag to a producer that does not take it makes its
    # analyze exit 2, and the whole section would drop off the pack with a note about an
    # unrecognised argument — strictly worse than not narrowing at all.
    "incident": {"skill": "incident-materiality", "script": "scripts/incident_analysis.py",
                 "argv": ["analyze", "{store}", "--today", "{asOf}",
                          "--now", "{asOf}T00:00:00+00:00"],
                 "context": True,
                 "headline": _incident_headline, "figures": _incident_figures,
                 "escalations": _incident_escalations},
}


def default_skills_root() -> str:
    """`skills/`, two levels up from this file. Overridable per manifest."""
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def export_context(biz_path: str, skills_root: str):
    """Turn a `.biz` into the CAC-AP-1 payload its consumers read. Returns (path, reason).

    Run as a subprocess, exactly like every other producer here. `business-context` owns the
    narrowing decision and this assembler must not re-derive it — §2.6 forbids the import
    and the contract reference is explicit that §2.2 lives in one place. So the pack asks
    that skill for its answer rather than reading the flags itself.

    Never fatal, on the same reasoning as `run_producer`: a profile that cannot be exported
    is reported on the provenance page and the pack assembles un-narrowed, which is the
    full question set and the safe direction.

    A file already holding a payload is passed through. A pack committed next to an
    exported payload should not need the producing skill installed to build.
    """
    import subprocess
    try:
        with open(biz_path, encoding="utf-8") as fh:
            head = json.load(fh)
    except (OSError, ValueError) as exc:
        return None, f"the applicability profile could not be read: {exc}"
    if head.get("contractVersion") == "CAC-AP-1":
        return biz_path, None

    script = os.path.join(skills_root, "business-context", "scripts", "business_context.py")
    if not os.path.exists(script):
        return None, ("business-context is not present, so the applicability profile was "
                      "not applied and every producer asked its full question set")
    try:
        proc = subprocess.run([sys.executable, script, "export", biz_path],
                              capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.SubprocessError) as exc:
        return None, f"the applicability profile could not be exported: {exc}"
    if proc.returncode != 0:
        first = (proc.stderr or proc.stdout or "").strip().splitlines()
        return None, ("the applicability profile was refused by business-context"
                      + (f": {first[0]}" if first else ""))
    fd, tmp = tempfile.mkstemp(suffix=".cac-ap-1.json")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(proc.stdout)
    return tmp, None


def run_producer(name: str, store: str, as_of: str, skills_root: str, context=None):
    """Run one producer's own analysis and return its JSON, or (None, reason).

    Never fatal. A store that cannot be read, a producer that errors, a version of a
    sibling skill that is not installed — each is reported on the provenance page and the
    pack assembles without that headline. A pack that refuses to build because one optional
    rollup failed would be trading a complete deliverable for a number.
    """
    import subprocess
    spec = PRODUCERS.get(name)
    if spec is None:
        return None, f"no producer adapter for section {name!r}"
    script = os.path.join(skills_root, spec["skill"], spec["script"])
    if not os.path.exists(script):
        return None, f"{spec['skill']} is not present at {script}"
    argv = [sys.executable, script] + [
        a.replace("{store}", store).replace("{asOf}", as_of) for a in spec["argv"]]
    # Only where the adapter declares it. See the note on the incident entry.
    if context and spec.get("context"):
        argv += ["--context", context]
    try:
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.SubprocessError) as exc:
        return None, f"{spec['skill']} analysis could not be run: {exc}"
    if proc.returncode != 0:
        first = (proc.stderr or proc.stdout or "").strip().splitlines()
        return None, (f"{spec['skill']} analysis exited {proc.returncode}"
                      + (f": {first[0]}" if first else ""))
    try:
        return json.loads(proc.stdout), None
    except json.JSONDecodeError as exc:
        return None, f"{spec['skill']} analysis did not return JSON: {exc.msg}"


def sections_names(sections) -> list:
    return [s.get("section") for s in sections]


def headline_counts(manifest: dict, sections: list, skills_root: str) -> dict:
    """Cross-section headline figures and chartable series, each read from its producer.

    One pass over the producers, not two. Each analysis is expensive enough — it is a
    subprocess running another skill's engine — that running it twice to collect two kinds
    of number from it would double the cost of a pack to no purpose, and would open the
    possibility of the two passes seeing different output.
    """
    figures, charts, escalations, unavailable = [], [], [], []
    stores = {e["section"]: e.get("storePath") for e in manifest["sections"]}

    # The applicability profile, exported once for the whole pass. Once, because the
    # payload is what every consumer reads and two exports of one file could not disagree
    # about anything worth the second subprocess — the same reasoning as the single pass
    # over the producers above.
    context, context_tmp = None, None
    profile_version = ""
    if manifest.get("contextPath"):
        context, reason = export_context(manifest["contextPath"], skills_root)
        if reason:
            unavailable.append(reason)
        elif context:
            context_tmp = context if context != manifest["contextPath"] else None
            try:
                with open(context, encoding="utf-8") as fh:
                    profile_version = str(json.load(fh).get("profileVersion") or "")
            except (OSError, ValueError):
                profile_version = ""
            # Which producers could actually use it. A profile that narrowed nothing
            # because no producer reads one yet is a fact about this pack, not a silent
            # no-op: a reader who supplied a profile is entitled to know it did nothing.
            takers = sorted(n for n in sections_names(sections)
                            if (PRODUCERS.get(n) or {}).get("context"))
            deaf = sorted(n for n in sections_names(sections)
                          if not (PRODUCERS.get(n) or {}).get("context"))
            if not takers:
                unavailable.append(
                    "an applicability profile was supplied and no section in this pack "
                    "reads one yet, so nothing was narrowed")
            elif deaf:
                unavailable.append(
                    "the applicability profile narrowed %s; %s do not read one yet and "
                    "asked their full question set" % (", ".join(takers), ", ".join(deaf)))

    for section in sections:
        name = section["section"]
        store = stores.get(name)
        if not store:
            unavailable.append(f"the {name!r} section declares no store, so its headline "
                               f"figures were not read")
            continue
        analysis, reason = run_producer(name, store, manifest["asOf"], skills_root,
                                        context)
        if analysis is None:
            unavailable.append(reason)
            continue

        for esc in PRODUCERS[name].get("escalations", lambda _a: [])(analysis):
            # A record missing a contract key cannot be rendered without the renderer
            # inventing the gap, so it is reported rather than drawn. This is not the lapse
            # rule in reverse: §1.2 forbids dropping a *lapsed* item, and a malformed record
            # is a producer defect, which the provenance page exists to name.
            missing = [k for k in ESCALATION_KEYS if k not in esc]
            if missing:
                unavailable.append(
                    f"an escalation from {name!r} is missing {', '.join(missing)} and was not "
                    f"carried; the producer emitted a record the CAC-EL-1 shape does not allow")
                continue
            row = dict(esc)
            row["section"] = name
            escalations.append(row)

        drawn = PRODUCERS[name].get("figures", lambda _a: [])(analysis)
        if name == "metrics" and len(drawn) > MAX_METRIC_BULLETS:
            unavailable.append(
                f"{len(drawn) - MAX_METRIC_BULLETS} of {len(drawn)} metrics are not drawn "
                f"on the metrics page; a board pack shows the first {MAX_METRIC_BULLETS}. "
                f"All of them remain in the metrics section.")
            drawn = drawn[:MAX_METRIC_BULLETS]
        for fig in drawn:
            fig["section"] = name
            charts.append(fig)

        for row in PRODUCERS[name]["headline"](analysis):
            # A headline row is (label, value) or (label, value, sev). The third
            # element is optional so a producer that declares no band for a
            # figure says so by omission rather than by passing a placeholder
            # that a renderer would then have to recognise.
            label, value = row[0], row[1]
            sev = row[2] if len(row) > 2 else None
            if value is None:
                continue
            figure = {"section": name, "label": label, "value": value}
            # Absent, not null: a figure with no declared band carries no `sev`
            # key at all, so `"sev" in figure` is the whole test a renderer needs
            # and there is no second way to spell "nothing declared".
            if sev is not None:
                figure["sev"] = sev
            figures.append(figure)
    # One order across every producer, so a board reads the worst thing on the page first
    # regardless of which skill raised it — which is the point of aggregating them at all.
    # Severity first, then the section order the audience already fixed, then the subject, so
    # two runs over one pack list them identically.
    # SEV_ORDER runs good -> critical, so a higher index is worse and the sort negates it.
    # An unrecognised severity gets -1, which negates to 1 and lands it after every known
    # band — visible at the bottom rather than silently first.
    worst_first = {s: i for i, s in enumerate(SEV_ORDER)}
    section_rank = {s["section"]: i for i, s in enumerate(sections)}
    escalations.sort(key=lambda e: (-worst_first.get(e["severity"], -1),
                                    section_rank.get(e["section"], 99), e["subjectRef"]))
    if context_tmp:
        try:
            os.unlink(context_tmp)
        except OSError:
            pass
    return {"figures": figures, "charts": charts, "escalations": escalations,
            "unavailable": unavailable, "profileVersion": profile_version}


def assemble(manifest: dict, skills_root: str = None, with_stores: bool = True) -> dict:
    """The content model. Everything in it was read; nothing in it was computed."""
    skills_root = skills_root or manifest.get("skillsRoot") or default_skills_root()
    validated = validate_pack(manifest)
    ordered = order_sections(validated["sections"], manifest["audience"])

    through_line = None
    if manifest.get("throughLinePath"):
        raw = _read_json(manifest["throughLinePath"], "through-line sidecar")
        through_line = validate_through_line(raw, manifest["throughLinePath"])

    decisions = consolidate_decisions(ordered, through_line)

    rollup = ({"figures": [], "charts": [], "escalations": [],
               "unavailable": ["store-backed rollups were not requested"],
               "profileVersion": ""}
              if not with_stores
              else headline_counts(manifest, ordered, skills_root))

    warnings = (list(validated["warnings"]) + possible_duplicate_asks(decisions)
                + possible_duplicate_escalations(rollup.get("escalations") or []))
    missing = list(validated["missing"]) + list(rollup["unavailable"])
    if through_line is None:
        missing.append("no through-line sidecar was supplied; the pack opens on a "
                       "placeholder rather than a synthesis")
    declared = [e["section"] for e in manifest["sections"]]
    for name in SECTION_ORDER[manifest["audience"]]:
        if name not in declared and name != "incident":
            missing.append(f"the {name!r} section is not in this pack")
    if "incident" not in declared:
        warnings.append("no incident section: none occurred in this period, or none was "
                        "declared. Absence is normal and is recorded rather than left silent.")

    doc = {
        "client": manifest.get("client") or "",
        "period": manifest.get("period") or "",
        "audience": manifest["audience"],
        "asOf": manifest["asOf"],
        # {} means CAC. Carried in the model rather than re-read by the renderers, so the
        # HTML and the deck cannot end up branded differently from one another.
        "brand": manifest.get("brand") or {},
        "throughLine": through_line,
        "sections": ordered,
        "decisions": decisions,
        "headlines": rollup["figures"],
        # The chartable series behind the sections. Separate from `headlines` because they
        # answer different questions: a headline is the one number a director remembers,
        # a chart is the shape behind it. A renderer that has no way to draw marks can
        # ignore this key entirely and lose nothing it was previously showing.
        "charts": rollup.get("charts") or [],
        # What the producers raised on their own, in one list across every section — the
        # aggregation no single skill can do, which is the reason this one exists. Separate
        # from `decisions` on purpose: a decision is board prose from
        # ciso-board-translation, and an escalation is a fact a producer derived. Merging
        # them would put a machine-written sentence in the one place this pack promises
        # every sentence came from a human translator.
        "escalations": rollup.get("escalations") or [],
        "provenance": {
            "manifest": manifest.get("manifestPath"),
            "sectionOrder": [s["section"] for s in ordered],
            "sectionDates": validated["sectionDates"],
            "sources": [{"section": e["section"], "translations": e.get("translations"),
                         "store": e.get("store")} for e in manifest["sections"]],
            "warnings": warnings,
            "missing": missing,
        },
    }
    # CAC-AP-1 §2.5, and additive exactly as `--context` is in every consumer: the key
    # appears only when a profile was actually applied. A pack built without one produces
    # the model it always did, which is how a renderer tells "not narrowed" from
    # "narrowed by something" without an empty string standing for both.
    if rollup.get("profileVersion"):
        doc["profileVersion"] = rollup["profileVersion"]
    return doc


def validate_through_line(raw: dict, path: str) -> dict:
    """The pack sidecar: an ordinary section-contract document with `section: "pack"`.

    It is the one section name no producer emits, because the assembler is its producer.
    """
    if not isinstance(raw, dict):
        raise Refusal(f"{path} must contain a JSON object, got {type(raw).__name__}")
    version = raw.get("contractVersion", CONTRACT_VERSION)
    if version != CONTRACT_VERSION:
        raise Refusal(f"{path} declares contractVersion {version!r}; this assembler "
                      f"implements {CONTRACT_VERSION}")
    declared = raw.get("section")
    if declared is not None and declared != PACK_SECTION:
        raise Refusal(f"{path} is a {declared!r} section; the through-line sidecar must be "
                      f"{PACK_SECTION!r}. A section sidecar is not a through-line — the "
                      f"through-line reconciles the sections and cannot be one of them.")
    if not raw.get("executiveSummary"):
        raise Refusal(f"{path} carries no executiveSummary, which is the only thing a "
                      f"through-line is. Compose it with ciso-board-translation.")
    return {"executiveSummary": raw["executiveSummary"],
            "decisions": list(raw.get("decisions") or []),
            "asOf": raw.get("asOf") or None,
            "path": path}


def compose_brief(pack: dict) -> dict:
    """The input `ciso-board-translation` needs to write the through-line.

    The assembler's half of the bargain is to supply the material and none of the words. It
    hands over each section's own summary, the figures each producer computed, and the asks
    already on the table — then consumes whatever comes back. Nothing here drafts a sentence,
    because one voice across every pack is the whole reason the composition exists.
    """
    audience_note = {
        "board": ("The board reads for direction and decisions. Lead with what changed and "
                  "where it is going, then the decision."),
        "audit-committee": ("The audit committee reads for controls, exceptions and "
                            "incidents. Lead with what was accepted, what deviated, and what "
                            "happened."),
    }[pack["audience"]]
    return {
        "task": "Compose the through-line for this board pack.",
        "audience": pack["audience"],
        "audienceNote": audience_note,
        "client": pack["client"],
        "period": pack["period"],
        "asOf": pack["asOf"],
        "sections": [
            {"section": s["section"],
             "title": SECTION_TITLE.get(s["section"], s["section"]),
             "executiveSummary": s["executiveSummary"],
             "itemCount": s["itemCount"],
             "asOf": s["asOf"],
             "decisions": s["decisions"]}
            for s in pack["sections"]],
        "headlines": pack["headlines"],
        "crossSectionNotes": pack["provenance"]["warnings"] + pack["provenance"]["missing"],
        "instructions": [
            "Write ONE paragraph that reconciles these sections into a single story with a "
            "direction. Not a summary of summaries — name the thread that runs through more "
            "than one section.",
            "Carry a direction, not just a state. 'Improving, with one exception' is a "
            "through-line; 'here is our posture' is a table of contents.",
            "Use only figures that appear in `headlines` or in a section's own summary. Do "
            "not compute a new number.",
            "Add cross-cutting asks to `decisions` only if they are not already asked by a "
            "section; per-section asks are consolidated separately.",
            "Mark each ask's altitude: {\"text\": \"...\", \"altitude\": \"board\"} for "
            "something a board must decide, \"management\" for something management should "
            "just do. Omit `altitude` if you genuinely cannot tell — an unmarked ask stays "
            "in front of the board, which is the safe way to be wrong. Do not guess it from "
            "the wording.",
            "Return a section-contract document: "
            '{"section": "pack", "contractVersion": 1, "executiveSummary": "...", '
            '"decisions": [...], "asOf": "%s"}' % pack["asOf"],
        ],
    }


# --- CLI ----------------------------------------------------------------------

def _cmd_compose_brief(args):
    manifest = load_manifest(args.manifest)
    pack = assemble(manifest, with_stores=not args.no_stores)
    brief = compose_brief(pack)
    text = json.dumps(brief, indent=2, ensure_ascii=False)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
        print(f"wrote {args.out}")
        print("  Hand this to the ciso-board-translation skill. Save what it returns as the "
              "manifest's throughLine sidecar.", file=sys.stderr)
    else:
        print(text)
    return 0


def _load_with_brand(args) -> dict:
    """The manifest, with `--brand FILE` overriding any block inside it.

    `--brand` resolves against the working directory, not the manifest: it is a flag someone
    typed just now, and a flag that silently resolved somewhere else would be the surprise.
    Manifest paths resolve against the manifest for the opposite reason.
    """
    manifest = load_manifest(args.manifest)
    if getattr(args, "brand", None):
        manifest["brand"] = resolve_brand(args.brand, os.getcwd())
    return manifest


def _cmd_assemble(args):
    manifest = _load_with_brand(args)
    pack = assemble(manifest, with_stores=not args.no_stores)
    text = json.dumps(pack, indent=2, ensure_ascii=False)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
        print(f"wrote {args.out}")
    else:
        print(text)
    order = " → ".join(pack["provenance"]["sectionOrder"])
    print(f"  {len(pack['sections'])} sections ({order})", file=sys.stderr)
    print(f"  {len(pack['decisions'])} decisions after consolidation", file=sys.stderr)
    print(f"  {len(pack['headlines'])} headline figures read from the producers",
          file=sys.stderr)
    for note in pack["provenance"]["missing"] + pack["provenance"]["warnings"]:
        print(f"  note: {note}", file=sys.stderr)
    return 0


def _cmd_validate(args):
    manifest = _load_with_brand(args)
    result = validate_pack(manifest)
    brand_note = ("CAC" if not manifest.get("brand")
                  else "client override (%s)" % ", ".join(sorted(manifest["brand"])))
    print(f"{os.path.basename(args.manifest)}: {len(result['sections'])} sections, "
          f"audience {manifest['audience']}, as at {manifest['asOf']}, brand {brand_note}")
    for s in result["sections"]:
        print(f"  {s['section']:<11} {s['itemCount']:>3} items · "
              f"{len(s['decisions'])} decisions · "
              f"{'summary' if s['executiveSummary'] else 'NO SUMMARY'}")
    for w in result["warnings"] + result["missing"]:
        print(f"  warning: {w}", file=sys.stderr)
    print(f"valid — {len(result['warnings']) + len(result['missing'])} warnings")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="assemble_pack.py",
                                description=__doc__.split("\n")[0],
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd")

    brand_help = ("a client brand block, overriding any in the manifest. Chrome and the "
                  "measure colour only — RAG is fixed, and a palette that misses the "
                  "contrast floors is refused rather than applied")

    sp = sub.add_parser("validate", help="check a manifest and its sections against the contract")
    sp.add_argument("manifest")
    sp.add_argument("--brand", default=None, help=brand_help)
    sp.set_defaults(fn=_cmd_validate)

    sp = sub.add_parser("compose-brief",
                        help="emit the input ciso-board-translation needs for the through-line")
    sp.add_argument("manifest")
    sp.add_argument("--out", default=None)
    sp.add_argument("--no-stores", action="store_true")
    sp.set_defaults(fn=_cmd_compose_brief)

    sp = sub.add_parser("assemble", help="build the pack content model")
    sp.add_argument("manifest")
    sp.add_argument("--out", default=None)
    sp.add_argument("--no-stores", action="store_true",
                    help="skip the store-backed headline figures; sections and decisions "
                         "still assemble")
    sp.add_argument("--brand", default=None, help=brand_help)
    sp.set_defaults(fn=_cmd_assemble)

    sp = sub.add_parser("self-test")
    sp.set_defaults(fn=lambda a: _cmd_self_test(a))
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    if not getattr(args, "fn", None):
        build_parser().print_help()
        return 2
    try:
        return args.fn(args)
    except Refusal as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 1


# --- Self-test ----------------------------------------------------------------

def _cmd_self_test(_args):
    import shutil
    import tempfile as _tf
    checks = [0]
    fails = []

    def ok(cond, label):
        checks[0] += 1
        if not cond: fails.append(label)

    def eq(actual, expected, label):
        checks[0] += 1
        if actual != expected: fails.append(f"{label}: expected {expected!r}, got {actual!r}")

    def refuses(fn, label, needle=""):
        checks[0] += 1
        try:
            fn()
        except Refusal as exc:
            if needle and needle not in str(exc):
                fails.append(f"{label}: refused, but not for the stated reason: {exc}")
            return
        fails.append(f"{label}: did not refuse")

    work = _tf.mkdtemp()
    try:
        def write(name, obj):
            path = os.path.join(work, name)
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(obj, fh)
            return path

        good_risk = {"section": "risk", "contractVersion": 1, "asOf": "2026-07-31",
                     "executiveSummary": "Risk is concentrated in third parties.",
                     "risks": {"R-001": "a sentence"}, "themes": {"third-party": "a theme"},
                     "decisions": ["Fund the vendor review."]}
        write("risk.board.json", good_risk)

        # --- the contract, section by section ---------------------------------
        r = validate_section("risk", good_risk, "risk.board.json")
        eq(r["itemCount"], 2, "both risk item maps are counted")
        eq([d["text"] for d in r["decisions"]], ["Fund the vendor review."],
           "decisions carry through")
        eq(r["decisions"][0]["altitude"], None,
           "a bare string is unclassified, NOT assumed to be a board decision")
        eq(r["warnings"], [], "a complete section warns about nothing")

        # --- decision altitude -------------------------------------------------
        # Declared by the producer, never inferred. A wrong guess here either wastes a
        # board's time or quietly buries a decision nobody then takes.
        d = normalise_decisions(
            [{"text": "Name a control owner.", "altitude": "management"},
             {"text": "Fund segmentation.", "altitude": "board"},
             "Decide the programme's shape."], "s.json")
        eq([x["altitude"] for x in d], ["management", "board", None],
           "both shapes read, and an unmarked ask stays unmarked")
        eq(d[0]["text"], "Name a control owner.", "the object form keeps its text")
        refuses(lambda: normalise_decisions([{"text": "x", "altitude": "committee"}], "s.json"),
                "an unrecognised altitude is refused, not defaulted — defaulting it would "
                "silently re-file somebody's board decision", "altitude")
        refuses(lambda: normalise_decisions([{"altitude": "board"}], "s.json"),
                "a decision object with no text is refused", "text")
        refuses(lambda: normalise_decisions([42], "s.json"),
                "a decision that is neither shape is refused", "neither a string nor an object")
        # Producers disagreeing on one identically-worded ask resolves upward.
        up = consolidate_decisions([
            {"section": "risk", "itemCount": 0,
             "decisions": normalise_decisions(
                 [{"text": "Fund it.", "altitude": "management"}], "a.json")},
            {"section": "metrics", "itemCount": 0,
             "decisions": normalise_decisions(
                 [{"text": "Fund it.", "altitude": "board"}], "b.json")}])
        eq(len(up), 1, "the identical ask still merges")
        eq(up[0]["altitude"], "board",
           "and resolves to the higher altitude — a board never seeing a decision is the "
           "failure that cannot be recovered from")

        # THE dangerous shape. It parses, so without this check the pack assembles and every
        # narrative is silently a placeholder while the deck looks finished.
        refuses(lambda: validate_section("risk", {"R-001": "a flat map"}, "flat.json"),
                "a flat per-item map is refused", "flat")
        # The boundary that moved when a legitimately empty section was first refused as a
        # flat map: envelope keys are excluded from the test, but a flat map that also
        # declares its section is still a flat map.
        refuses(lambda: validate_section("risk", {"section": "risk", "R-001": "flat"},
                                         "flat2.json"),
                "a flat map that also declares its section is still refused", "flat")
        eq(validate_section("metrics", {"section": "metrics"}, "e.json")["itemCount"], 0,
           "but a legitimately empty section is not a flat map")
        eq(validate_section("risk", dict(good_risk, generatedBy="ciso-board-translation"),
                            "pt.json")["itemCount"], 2,
           "and a passthrough string key is ignored, as the contract says")
        refuses(lambda: validate_section("risk", dict(good_risk, contractVersion=2), "v2.json"),
                "an unknown contractVersion is refused, not best-efforted", "contractVersion")
        refuses(lambda: validate_section("risk", dict(good_risk, section="metrics"), "x.json"),
                "a sidecar for the wrong section is refused", "metrics")
        refuses(lambda: validate_section("risk", dict(good_risk, gaps={"ID.RA-01": "x"}),
                                         "x.json"),
                "an item key from another section is refused", "not a key of the")
        refuses(lambda: validate_section("risk", dict(good_risk, asOf="2026-7-31"), "x.json"),
                "an unpadded asOf is refused", "canonical zero-padded")

        # contractVersion is absent-means-one: every sidecar written before the contract
        # existed is a valid v1 document.
        pre = {k: v for k, v in good_risk.items() if k not in ("contractVersion", "section")}
        eq(validate_section("risk", pre, "pre.json")["contractVersion"], 1,
           "an absent contractVersion reads as 1")
        eq(validate_section("risk", pre, "pre.json")["itemCount"], 2,
           "and a pre-contract sidecar validates unchanged")

        # The deprecated alias warns and still resolves.
        alias = {"section": "posture", "subcategories": {"ID.RA-01": "a gap"},
                 "executiveSummary": "s", "decisions": ["d"]}
        res = validate_section("posture", alias, "alias.json")
        eq(res["items"]["gaps"], {"ID.RA-01": "a gap"},
           "the deprecated alias resolves to the canonical key")
        eq(len(res["warnings"]), 1, "and warns exactly once")
        ok("deprecated" in res["warnings"][0], "naming it as deprecated")

        empty = validate_section("metrics", {"section": "metrics"}, "empty.json")
        eq(len(empty["warnings"]), 2,
           "an empty section warns about both its emptiness and its silence on decisions")

        # --- the manifest ------------------------------------------------------
        base = {"manifestVersion": 1, "client": "Test Co", "period": "Q3 2026",
                "asOf": "2026-07-31", "audience": "board",
                "sections": [{"section": "risk", "translations": "risk.board.json"}]}
        mpath = write("pack.manifest.json", base)
        m = load_manifest(mpath)
        eq(m["audience"], "board", "audience defaults are respected")
        eq(m["sections"][0]["translationsPath"],
           os.path.normpath(os.path.join(work, "risk.board.json")),
           "paths resolve relative to the manifest, not the working directory")

        refuses(lambda: load_manifest(write("m2.json", dict(base, manifestVersion=2))),
                "an unknown manifestVersion is refused", "manifestVersion")
        refuses(lambda: load_manifest(write("m3.json", dict(base, audience="shareholders"))),
                "an unknown audience is refused", "audience")
        refuses(lambda: load_manifest(write("m4.json", dict(base, asOf="2026-7-31"))),
                "an unpadded manifest asOf is refused", "canonical")
        refuses(lambda: load_manifest(write("m5.json", dict(base, sections=[]))),
                "an empty sections list is refused", "non-empty")
        refuses(lambda: load_manifest(write("m6.json", dict(
                    base, sections=[{"section": "budget", "translations": "x.json"}]))),
                "an unknown section name is refused", "budget")
        refuses(lambda: load_manifest(write("m7.json", dict(
                    base, sections=[{"section": "risk", "translations": "risk.board.json"},
                                    {"section": "risk", "translations": "risk.board.json"}]))),
                "the same section declared twice is refused", "twice")
        refuses(lambda: load_manifest(os.path.join(work, "nope.json")),
                "a manifest that does not exist is refused", "no such manifest")

        # --- the client brand --------------------------------------------------
        # Absent means CAC, and {} and "absent" have to be the same thing or a manifest
        # that never heard of branding would start refusing.
        eq(m["brand"], {}, "a manifest with no brand block renders CAC")

        inline = {"ink": "#101820", "measure": "#7A3E9D", "mark": "Northwind"}
        eq(load_manifest(write("mb1.json", dict(base, brand=inline)))["brand"], inline,
           "an inline brand block is carried through")

        write("client.brand.json", inline)
        eq(load_manifest(write("mb2.json", dict(base, brand="client.brand.json")))["brand"],
           inline,
           "a brand given as a path resolves relative to the manifest, like every other path")

        # Refused early — at validate time, not at render time. An operator who learns
        # their palette is illegal only once the deck is written has already moved on.
        refuses(lambda: load_manifest(write("mb3.json", dict(base, brand={"ink": "#AAAAAA"}))),
                "a brand below the contrast floor is refused when the manifest loads",
                "needs 4.5:1")
        refuses(lambda: load_manifest(write("mb4.json", dict(base, brand={"critical": "#F00"}))),
                "a brand that tries to re-colour RAG is refused", "not overridable")
        refuses(lambda: load_manifest(write("mb5.json", dict(base, brand={"accent": "#123456"}))),
                "a brand with an unknown key is refused", "unknown brand key")
        refuses(lambda: load_manifest(write("mb6.json", dict(base, brand="nope.brand.json"))),
                "a brand path that does not exist is refused", "brand")
        refuses(lambda: load_manifest(write("mb7.json", dict(base, brand=["#101820"]))),
                "a brand that is neither an object nor a path is refused", "must be an object")

        # --- the whole pack ----------------------------------------------------
        write("posture.board.json", {"section": "posture", "contractVersion": 1,
                                     "asOf": "2026-06-30", "executiveSummary": "p",
                                     "gaps": {"ID.RA-01": "g"},
                                     "decisions": ["Fund the vendor review."]})
        full = dict(base, sections=[
            {"section": "posture", "translations": "posture.board.json"},
            {"section": "risk", "translations": "risk.board.json"},
            {"section": "metrics"},
        ])
        m = load_manifest(write("full.manifest.json", full))
        out = validate_pack(m)
        eq(len(out["sections"]), 3, "every declared section is validated")
        ok(any("dated differently" in w for w in out["warnings"]),
           "an asOf mismatch across sections is surfaced")
        ok(any("no translations sidecar" in w for w in out["missing"]),
           "a section with no sidecar is named, not silently dropped")
        eq(out["sections"][2]["itemCount"], 0, "and renders as an empty section")
        eq(out["sectionDates"], ["2026-06-30", "2026-07-31"], "both section dates are kept")

        same = dict(base, sections=[
            {"section": "risk", "translations": "risk.board.json"}])
        out2 = validate_pack(load_manifest(write("same.manifest.json", same)))
        ok(not any("dated differently" in w for w in out2["warnings"]),
           "one section cannot drift from itself")

        store_missing = dict(base, sections=[
            {"section": "risk", "translations": "risk.board.json",
             "store": "nowhere/register.rr"}])
        out3 = validate_pack(load_manifest(write("sm.manifest.json", store_missing)))
        ok(any("does not exist" in w for w in out3["missing"]),
           "a declared store that cannot be read is named")

        refuses(lambda: validate_pack(load_manifest(write("bad.manifest.json", dict(
                    base, sections=[{"section": "risk", "translations": "absent.json"}])))),
                "a sidecar path that does not resolve is refused", "no such")

        # --- ordering ----------------------------------------------------------
        def secs(*names):
            return [{"section": n, "decisions": [], "itemCount": 0} for n in names]

        eq([s["section"] for s in order_sections(
                secs("incident", "metrics", "posture", "risk", "exceptions"), "board")],
           ["posture", "risk", "metrics", "exceptions", "incident"],
           "the board order is the frame first, then what we carry")
        eq([s["section"] for s in order_sections(
                secs("posture", "risk", "metrics", "exceptions", "incident"),
                "audit-committee")],
           ["incident", "exceptions", "risk", "posture", "metrics"],
           "an audit committee sees incidents and exceptions first — its own remit")
        eq([s["section"] for s in order_sections(secs("risk", "posture"), "board")],
           ["posture", "risk"], "an absent section is omitted, not left as a hole")
        eq(order_sections(secs(), "board"), [], "no sections is not an error here")
        # The order is fixed, not input-dependent: the same set in a different declared
        # order must produce the same pack, or two quarters cannot be compared.
        eq([s["section"] for s in order_sections(secs("risk", "posture"), "board")],
           [s["section"] for s in order_sections(secs("posture", "risk"), "board")],
           "declaration order does not change the pack")

        # --- decision consolidation --------------------------------------------
        def dsec(name, *decisions):
            return {"section": name, "itemCount": 0,
                    "decisions": normalise_decisions(list(decisions), f"{name}.json")}

        merged = consolidate_decisions([
            dsec("posture", "Fund the vendor review."),
            dsec("risk", "fund the vendor review", "Accept the residual on R-004."),
            dsec("metrics", "Fund  the   vendor review!"),
        ])
        eq(len(merged), 2, "textual duplicates merge across sections")
        eq(merged[0]["text"], "Fund the vendor review.",
           "the first appearance keeps its wording and its position")
        eq(merged[0]["sections"], ["posture", "risk", "metrics"],
           "and collects every section that asked for it")
        eq(merged[1]["sections"], ["risk"], "a unique ask keeps its single section")

        # The rule that protects the board: never merge on meaning.
        two = consolidate_decisions([
            dsec("risk", "Fund the vendor review."),
            dsec("metrics", "Fund the third-party assurance programme."),
        ])
        eq(len(two), 2,
           "two differently-worded asks stay two entries — merging on meaning would delete "
           "a decision the board was supposed to make")
        eq(len(consolidate_decisions([dsec("risk", "", "   ")])), 0,
           "an empty decision is dropped rather than rendered as a blank bullet")

        # --- the through-line sidecar ------------------------------------------
        tl = {"section": "pack", "contractVersion": 1,
              "executiveSummary": "One story, with a direction.",
              "decisions": ["Fund the vendor review."]}
        eq(validate_through_line(tl, "tl.json")["executiveSummary"],
           "One story, with a direction.", "a through-line sidecar validates")
        refuses(lambda: validate_through_line(dict(tl, section="risk"), "tl.json"),
                "a section sidecar cannot be used as the through-line", "cannot be one of them")
        refuses(lambda: validate_through_line(
                    {k: v for k, v in tl.items() if k != "executiveSummary"}, "tl.json"),
                "a through-line with no summary is refused", "only thing a through-line is")
        refuses(lambda: validate_through_line(dict(tl, contractVersion=2), "tl.json"),
                "an unknown contractVersion is refused here too", "contractVersion")

        # --- assemble end to end, without touching any store --------------------
        write("metrics.board.json", {"section": "metrics", "contractVersion": 1,
                                     "asOf": "2026-07-31", "executiveSummary": "m",
                                     "metrics": {"M-001": "a metric"},
                                     "decisions": ["Fund the vendor review."]})
        write("tl.board.json", tl)
        full2 = dict(base, throughLine="tl.board.json", sections=[
            {"section": "metrics", "translations": "metrics.board.json"},
            {"section": "risk", "translations": "risk.board.json"},
            {"section": "posture", "translations": "posture.board.json"},
        ])
        pack = assemble(load_manifest(write("a.manifest.json", full2)), with_stores=False)
        eq(pack["provenance"]["sectionOrder"], ["posture", "risk", "metrics"],
           "the assembled pack is in audience order, not declaration order")
        eq([d["text"] for d in pack["decisions"]], ["Fund the vendor review."],
           "one ask, made by three sections, appears once")
        eq(pack["decisions"][0]["sections"], ["pack", "posture", "risk", "metrics"],
           "the through-line asked for it too, and it leads")
        # A board that reads the synthesis and then meets the same ask five sections later
        # has been asked twice for one decision.
        tl2 = dict(tl, decisions=["Decide the third-party programme's owner."])
        write("tl2.board.json", tl2)
        pack_tl = assemble(load_manifest(write("c.manifest.json",
                                               dict(full2, throughLine="tl2.board.json"))),
                           with_stores=False)
        eq(pack_tl["decisions"][0]["text"], "Decide the third-party programme's owner.",
           "a cross-cutting ask from the through-line comes first")
        eq(pack_tl["decisions"][0]["sections"], ["pack"], "labelled as the pack's own")
        eq(len(pack_tl["decisions"]), 2, "and the sections' single shared ask follows it")

        # --- two sections, one record, two asks ---------------------------------
        # Exactly what the shipped example produces: the exceptions section asks to
        # "re-validate A-002 or withdraw it" and the incident section asks to "re-confirm or
        # withdraw A-002". One decision, arriving twice, in wording too different to merge.
        dupes = possible_duplicate_asks([
            {"text": "Re-validate the CRM vendor acceptance (A-002), or withdraw it.",
             "sections": ["exceptions"]},
            {"text": "Re-confirm or withdraw acceptance A-002 on the record.",
             "sections": ["incident"]},
        ])
        eq(len(dupes), 1, "two asks naming the same record are flagged")
        ok("A-002" in dupes[0] and "exceptions" in dupes[0] and "incident" in dupes[0],
           "and the flag names the record and both sections")
        ok("not merged" in dupes[0],
           "while stating plainly that both entries still stand")
        eq(possible_duplicate_asks([
               {"text": "Re-validate A-002.", "sections": ["exceptions"]},
               {"text": "Fund segmentation for R-006.", "sections": ["risk"]}]), [],
           "two asks about different records are not flagged")
        eq(possible_duplicate_asks([
               {"text": "Re-validate A-002 and close X-001.", "sections": ["exceptions"]}]), [],
           "one ask naming two records is not a duplicate of itself")
        # A merged entry already carries both sections, so it must not be flagged as well.
        eq(possible_duplicate_asks([
               {"text": "Re-validate A-002.", "sections": ["exceptions", "incident"]}]), [],
           "an ask that already merged is not then flagged as a possible duplicate")
        eq(possible_duplicate_asks([
               {"text": "Close PR.DS-01.", "sections": ["posture"]},
               {"text": "Fund the work behind PR.DS-01.", "sections": ["metrics"]}])[0][:1],
           "2", "CSF Subcategory ids are recognised too")

        # --- two producers, one record, two escalations -------------------------
        # `exceptions-register` owns the acceptance lifecycle and escalates `expired` on the
        # authoritative record; `risk-register` keeps its own `accepted` marker and escalates
        # `acceptance-lapsed` on that. One expiry, two entries, two severities.
        def _esc(section, ref, trigger, sev, related=None):
            row = {"section": section, "subjectRef": ref, "subjectKind": "x",
                   "trigger": trigger, "severity": sev, "since": "2026-07-15",
                   "evidence": {"from": "", "to": "", "baseline": "", "detail": ""}}
            if related is not None:
                row["relatedRef"] = related
            return row

        pair = [_esc("risk", "R-010", "acceptance-lapsed", "high"),
                _esc("exceptions", "A-002", "expired", "critical", related="R-010")]
        dups = possible_duplicate_escalations(pair)
        eq(len(dups), 1, "one declared link produces one flag, not one per id")
        ok("R-010" in dups[0] and "A-002" in dups[0],
           "and it names both records, so a reader can find each")
        ok("risk" in dups[0] and "exceptions" in dups[0], "and both producers")
        ok("not merged" in dups[0], "while stating plainly that both entries still stand")
        ok("disagree on severity" in dups[0] and "critical" in dups[0] and "high" in dups[0],
           "and names the severity disagreement, which is the sharpest symptom")

        # Only exceptions-register can declare the link — the bridge is one-way and
        # risk-register has no back-channel — so the join has to work from one side alone,
        # whichever order the producers ran in.
        eq(len(possible_duplicate_escalations(list(reversed(pair)))), 1,
           "and finds the pair from the one side that can declare it, in either order")

        # Same severity is still a duplicate, just without the extra sentence.
        agree = possible_duplicate_escalations(
            [_esc("risk", "R-010", "acceptance-lapsed", "high"),
             _esc("exceptions", "A-002", "expired", "high", related="R-010")])
        eq(len(agree), 1, "two producers agreeing on severity is still one fact twice")
        ok("disagree on severity" not in agree[0],
           "but there is no disagreement to report, and none is invented")

        # No declared link, no flag. The assembler never infers identity — two records that
        # merely concern related things are two facts.
        eq(possible_duplicate_escalations(
               [_esc("risk", "R-003", "appetite-dwell", "high"),
                _esc("exceptions", "A-002", "revalidation-overdue", "high")]), [],
           "without a declared link nothing is joined, however suggestive the pair looks")
        eq(possible_duplicate_escalations(
               [_esc("risk", "R-010", "acceptance-lapsed", "high"),
                _esc("exceptions", "A-002", "expired", "critical", related=None)]), [],
           "and a null relatedRef is no link, not a link to nothing")

        # Two triggers from ONE producer on one subject is ordinary, not a duplicate: an
        # incident with an absent anchor and a superseded determination is two facts.
        eq(possible_duplicate_escalations(
               [_esc("incident", "I-001", "anchor-missing", "high"),
                _esc("incident", "I-001", "determination-superseded", "high")]), [],
           "two triggers from one producer on one subject are not a duplicate")

        # Three collide when a risk escalates twice and its acceptance escalates once.
        triple = possible_duplicate_escalations(
            [_esc("risk", "R-010", "band-crossed", "critical"),
             _esc("risk", "R-010", "acceptance-lapsed", "high"),
             _esc("exceptions", "A-002", "expired", "critical", related="R-010")])
        eq(len(triple), 1, "one record, one flag, however many escalations name it")
        ok(triple[0].startswith("3 escalations"), "which counts all of them")

        # The shipped example declares no bridge link — its acceptances were hand-entered,
        # so `sourceRiskRef` is null on every one. Four distinct facts, no flag. Asserted
        # rather than assumed, because a flag appearing here would mean the join had started
        # matching on something it was built not to match on.
        eq(possible_duplicate_escalations(pack["escalations"]), [],
           "the shipped example's escalations are distinct facts, and none is joined")

        # --- the brief handed to ciso-board-translation -------------------------
        brief = compose_brief(pack)
        eq(brief["audience"], "board", "the brief carries the audience")
        eq([s["section"] for s in brief["sections"]], ["posture", "risk", "metrics"],
           "and the sections in reading order")
        ok(brief["headlines"] == pack["headlines"],
           "the figures handed over are the ones the producers computed")
        ok(any("Not a summary of summaries" in i for i in brief["instructions"]),
           "the brief asks for a synthesis, not a concatenation")
        ok(any("Do not compute a new number" in i for i in brief["instructions"]),
           "and forbids inventing a figure")
        ok(not any(isinstance(v, str) and len(v) > 400 for v in brief.values()),
           "the brief supplies material, never drafted prose")
        ac = compose_brief(assemble(load_manifest(write("d.manifest.json",
                                                        dict(full2, audience="audit-committee"))),
                                    with_stores=False))
        ok("controls, exceptions and incidents" in ac["audienceNote"],
           "the audit-committee brief says what that audience reads for")
        # This manifest declares no exceptions and no incident section, so the audit-committee
        # order is what remains of it: risk, posture, metrics. The two sections it would lead
        # with are simply absent — which is the point of omitting rather than holding a slot.
        eq([s["section"] for s in ac["sections"]], ["risk", "posture", "metrics"],
           "and orders the sections for it, omitting the two it does not have")
        eq(pack["throughLine"]["executiveSummary"], "One story, with a direction.",
           "the through-line is carried")
        ok(any("incident" in m for m in pack["provenance"]["warnings"]),
           "an absent incident section is recorded, not left silent")
        ok(any("exceptions" in m for m in pack["provenance"]["missing"]),
           "and a missing non-episodic section is named as missing")
        eq(pack["headlines"], [], "--no-stores means no headline figures")

        no_tl = dict(full2); no_tl.pop("throughLine")
        pack2 = assemble(load_manifest(write("b.manifest.json", no_tl)), with_stores=False)
        eq(pack2["throughLine"], None, "an absent through-line is None, never fabricated")
        ok(any("through-line" in m for m in pack2["provenance"]["missing"]),
           "and its absence is on the provenance record")

        # --- the producer adapters are wired to real siblings --------------------
        # Reading a headline from the producer that computed it is the whole design; a
        # table of adapters nobody exercises is a table of guesses.
        root = default_skills_root()
        eq(sorted(PRODUCERS), sorted(SECTION_KEYS),
           "every section has a producer adapter")
        csf_store = os.path.join(root, "nist-csf", "examples", "example-profile.csfp")
        if os.path.exists(csf_store):
            analysis, reason = run_producer("posture", csf_store, "2026-07-26", root)
            ok(analysis is not None, f"the posture adapter runs its producer ({reason})")
            if analysis is not None:
                labels = [lbl for lbl, val in _posture_headline(analysis) if val is not None]
                eq(labels, ["outcomes short of target", "outcomes assessed"],
                   "and reads both figures the producer computed")
        else:
            ok(False, "the nist-csf example profile is missing; the adapter went untested")

        # --- the figures each adapter draws --------------------------------------
        eq(sorted(k for k, v in PRODUCERS.items() if "figures" in v), sorted(SECTION_KEYS),
           "every section has a figures adapter too")

        if os.path.exists(csf_store):
            analysis, _ = run_producer("posture", csf_store, "2026-07-26", root)
            if analysis is not None:
                figs = _posture_figures(analysis)
                eq(len(figs), 1, "posture draws one figure")
                eq(figs[0]["kind"], "bar", "coverage by Function is a measure, not a band")
                ok(all("sev" not in s for s in figs[0]["series"]),
                   "and carries no severity — a low coverage may be a met low Target")
                # The null case is the one that matters. An unassessed Function must reach
                # the renderer as null, because zero would claim it was assessed and found
                # to cover nothing, and dropping it would claim it does not exist.
                ok(any(s["value"] is None for s in figs[0]["series"]),
                   "an unassessed Function reaches the model as null, not as zero")

        # A band-mix is a partition, and the segments must sum to the population the
        # producer says it split. This is the property that makes the chart trustworthy
        # beside the headline, and it is checked against the real sibling engines.
        for name, store_rel, total_key in (
                ("exceptions", ("exceptions-register", "examples", "example.exc"), "active"),
                ("incident", ("incident-materiality", "examples", "example-incident.inc"),
                 "open")):
            store = os.path.join(root, *store_rel)
            if not os.path.exists(store):
                ok(False, f"the {name} example store is missing; its mix went untested")
                continue
            analysis, reason = run_producer(name, store, "2026-07-31", root)
            if analysis is None:
                ok(False, f"the {name} figures adapter could not run its producer ({reason})")
                continue
            figs = PRODUCERS[name]["figures"](analysis)
            eq(len(figs), 1, f"{name} draws one mix")
            total = (analysis.get("counts") or {}).get(total_key)
            eq(sum(s["value"] for s in figs[0]["series"]), total,
               f"the {name} mix sums to the {total_key!r} count it partitions")
            ok("note" in figs[0] and "not shown" in figs[0]["note"],
               f"and the {name} mix names the population it leaves out")

        missing_store = os.path.join(work, "nope.csfp")
        analysis, reason = run_producer("posture", missing_store, "2026-07-26", root)
        eq(analysis, None, "a store that cannot be read yields no analysis")
        ok(reason and "exited" in reason,
           "and the reason is reported rather than raised — a pack does not fail to "
           "build because one optional rollup did")
    finally:
        shutil.rmtree(work, ignore_errors=True)

    if fails:
        print("FAILED:")
        for f in fails: print(f"  - {f}")
        print(f"self-test: {checks[0] - len(fails)}/{checks[0]} checks passed")
        return 1
    print(f"self-test: {checks[0]}/{checks[0]} checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
