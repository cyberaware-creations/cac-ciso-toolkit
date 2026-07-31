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
from datetime import date

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
        "decisions": list(raw.get("decisions") or []),
        "asOf": raw.get("asOf") or None,
        "contractVersion": version,
        "warnings": warnings,
    }


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
                           "decisions": through_line["decisions"]})
    for section in sources:
        for raw in section["decisions"]:
            if not str(raw or "").strip():
                continue
            key = _normalise_decision(raw)
            if key in index:
                entry = out[index[key]]
                if section["section"] not in entry["sections"]:
                    entry["sections"].append(section["section"])
            else:
                index[key] = len(out)
                out.append({"text": str(raw).strip(), "sections": [section["section"]]})
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
def _posture_headline(a):
    completeness = (a.get("completeness") or {}).get("overall") or {}
    return [("outcomes short of target", len(a.get("gaps") or [])),
            ("outcomes assessed", completeness.get("assessed"))]


def _risk_headline(a):
    summary = a.get("summary") or {}
    return [("risks over appetite", summary.get("overAppetite")),
            ("risks tracked", summary.get("total"))]


def _metrics_headline(a):
    att = a.get("attention") or {}
    return [("metrics past a threshold", len(att.get("breached") or [])),
            ("metrics moving the wrong way", len(att.get("worsening") or []))]


def _exceptions_headline(a):
    att = a.get("attention") or {}
    return [("acceptances and exceptions carried", (a.get("counts") or {}).get("active")),
            ("overdue for re-validation", len(att.get("overdue") or []))]


def _incident_headline(a):
    att = a.get("attention") or {}
    return [("incidents in the period", (a.get("counts") or {}).get("incidents")),
            ("reporting windows open", len(att.get("due") or []))]


PRODUCERS = {
    "posture": {"skill": "nist-csf", "script": "scripts/profile_analysis.py",
                "argv": ["analyze", "{store}", "--today", "{asOf}"],
                "headline": _posture_headline},
    "risk": {"skill": "risk-register", "script": "scripts/score_register.py",
             "argv": ["score", "{store}", "--json"],
             "headline": _risk_headline},
    "metrics": {"skill": "metrics-register", "script": "scripts/metrics_analysis.py",
                "argv": ["analyze", "{store}", "--today", "{asOf}"],
                "headline": _metrics_headline},
    "exceptions": {"skill": "exceptions-register", "script": "scripts/exceptions_register.py",
                   "argv": ["analyze", "{store}", "--today", "{asOf}"],
                   "headline": _exceptions_headline},
    "incident": {"skill": "incident-materiality", "script": "scripts/incident_analysis.py",
                 "argv": ["analyze", "{store}", "--today", "{asOf}",
                          "--now", "{asOf}T00:00:00+00:00"],
                 "headline": _incident_headline},
}


def default_skills_root() -> str:
    """`skills/`, two levels up from this file. Overridable per manifest."""
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def run_producer(name: str, store: str, as_of: str, skills_root: str):
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


def headline_counts(manifest: dict, sections: list, skills_root: str) -> dict:
    """Cross-section headline figures, each read from the producer that computed it."""
    figures, unavailable = [], []
    stores = {e["section"]: e.get("storePath") for e in manifest["sections"]}
    for section in sections:
        name = section["section"]
        store = stores.get(name)
        if not store:
            unavailable.append(f"the {name!r} section declares no store, so its headline "
                               f"figures were not read")
            continue
        analysis, reason = run_producer(name, store, manifest["asOf"], skills_root)
        if analysis is None:
            unavailable.append(reason)
            continue
        for label, value in PRODUCERS[name]["headline"](analysis):
            if value is not None:
                figures.append({"section": name, "label": label, "value": value})
    return {"figures": figures, "unavailable": unavailable}


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

    rollup = ({"figures": [], "unavailable": ["store-backed rollups were not requested"]}
              if not with_stores
              else headline_counts(manifest, ordered, skills_root))

    warnings = list(validated["warnings"]) + possible_duplicate_asks(decisions)
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

    return {
        "client": manifest.get("client") or "",
        "period": manifest.get("period") or "",
        "audience": manifest["audience"],
        "asOf": manifest["asOf"],
        "throughLine": through_line,
        "sections": ordered,
        "decisions": decisions,
        "headlines": rollup["figures"],
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


def _cmd_assemble(args):
    manifest = load_manifest(args.manifest)
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
    manifest = load_manifest(args.manifest)
    result = validate_pack(manifest)
    print(f"{os.path.basename(args.manifest)}: {len(result['sections'])} sections, "
          f"audience {manifest['audience']}, as at {manifest['asOf']}")
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

    sp = sub.add_parser("validate", help="check a manifest and its sections against the contract")
    sp.add_argument("manifest")
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
        eq(r["decisions"], ["Fund the vendor review."], "decisions carry through")
        eq(r["warnings"], [], "a complete section warns about nothing")

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
            return {"section": name, "decisions": list(decisions), "itemCount": 0}

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
