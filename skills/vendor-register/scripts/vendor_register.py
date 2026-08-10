#!/usr/bin/env python3
"""vendor_register.py — the third-party arrangement register.

A system of record for who the organisation depends on, for what, how critical that
dependency is, and whether any of it has been re-checked lately. The spine is NIST CSF 2.0
`GV.SC`, already bundled in this repo; the criticality method follows NISTIR 8179's shape;
the controls map to SP 800-53r5 `SR`. Regimes such as DORA are overlays, never the frame.

**The register is contract-centric, not vendor-centric.** One provider commonly holds several
arrangements at different criticalities — the same cloud provider behind a critical trading
dependency and a marketing sandbox. A vendor-shaped store forces one criticality per provider
and produces a register that is wrong in the way an assessor notices first.

Three ideas carry the file:

1. **`untraced` is a value, not a gap.** An arrangement whose dependency cannot be traced to
   a workflow with a declared criticality is `untraced` — never `low`. This is CAC-AP-1 §2.2
   applied to criticality: absence must not read as unimportant, and the arrangement nobody
   could trace is exactly the one worth looking at. `untraced` is not a member of the scale
   and ordering raises on it, so no comparison can quietly sort it to the bottom.

2. **Derivation proposes; a person confirms.** The walk produces a proposed level. Only a
   named human assigns the final one, and the engine refuses an unattributed confirmation.
   A method is not a substitute for a judgement.

3. **No vendor risk score.** Every commercial third-party tool emits one, and it is the same
   failure this suite refuses elsewhere: a generated number that looks like an assessment and
   disagrees with the register that owns scoring. Findings go to `risk-register` and are
   scored once, there. Enforced by an eval, not by this comment.

Refusals happen before the store file is opened, so a refused command leaves it
byte-identical. Standard library only. Subcommands:

  init             <store.vnd> --org 'Name' [--prepared-by ..]
  add-vendor       <store.vnd> --name '..' [--jurisdiction ..] [--group-parent ..]
  add-arrangement  <store.vnd> --vendor V-001 --services '..' --owner '..'
                               [--supports 'System'] [--entity 'Legal entity']
  set-scale        <store.vnd> --levels low,moderate,high
  classify         <store.vnd> --arrangement VA-001 [--context ctx.json]
                               [--confirm LEVEL --by NAME [--basis ..]] [--layer system]
  test-exit        <store.vnd> --arrangement VA-001 --tested '..' --why '..'
  review-requirements <store.vnd> --arrangement VA-001 --requirement '..' --evidence '..'
  record-subprocessor <store.vnd> --arrangement VA-001 --name '..' --effective YYYY-MM-DD
  retire           <store.vnd> --arrangement VA-001 --data-went '..' --deletion-confirmed DATE
  review           <store.vnd> --label '..' --why '..'
  analyze          <store.vnd> [--today YYYY-MM-DD] [--context ctx.json] [--out FILE]
  self-test

This tool is not legal advice.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from datetime import date, datetime, timezone

SCHEMA_VERSION = 1
FAMILY = "vendor-register"

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
VENDOR_ID_RE = re.compile(r"^V-\d{3,}$")
ARRANGEMENT_ID_RE = re.compile(r"^VA-\d{3,}$")

# `VA-` and not `A-`, deliberately, and this is a deviation from the plan's worked example.
#
# `board-pack` flags two sections asking the board about the same record by regexing ids out
# of decision prose (`[A-Z]{1,2}-\d{3,}`). `exceptions-register` already mints `A-001`. An
# arrangement called `A-002` in a vendor decision and an acceptance called `A-002` in an
# exceptions decision would be reported to the board as one ask arriving twice, which is a
# false duplicate in the one place the pack promises not to smooth things over. Two letters
# still match that regex, so real duplicates inside this skill are still caught.

UNTRACED = "untraced"
"""Traced, and the trace did not reach a workflow with a declared criticality.

Never a member of `criticalityScale`, and `criticality_rank` raises on it rather than
returning a number. The failure this guards against is a single `sorted(key=rank)` quietly
placing every untraceable arrangement at the bottom of a board table.
"""

UNCLASSIFIED = "unclassified"
"""Nobody ran the walk. Distinct from `untraced`, which means we ran it and could not finish.

Kept apart because the actions differ: one needs somebody to classify it, the other needs
somebody to declare what the dependency actually supports.
"""

DEFAULT_SCALE = ["low", "moderate", "high"]

# NISTIR 8276 recommends assessment frequency track supplier criticality. The intervals are
# a default, overridable per store; `low` deliberately has no cadence, so the triggers below
# are the only thing that catches the low arrangement that quietly stopped being low.
SETTINGS_DEFAULTS = {
    "criticalityScale": list(DEFAULT_SCALE),
    "scaleVersion": "v1",
    "cadenceDays": {"high": 365, "moderate": 730},
    "exitTestStaleDays": 730,
    "traceMaxHops": 2,
    # Twelve months from the END OF THE PERIOD an artifact covers, not from the day somebody
    # filed it. A SOC 2 for a period that closed fourteen months ago is a historical document
    # however recently it arrived.
    "evidenceGraceDays": 365,
    # A pile of unconfirmed proposals must not be able to masquerade as an assessment.
    "proposalStaleDays": 30,
}

TRACE_MAX_HOPS = 2

# --- Evidence tiers -----------------------------------------------------------
#
# The hierarchy is about ASSESSMENT RIGOUR, not about how much a vendor is trusted.
#
#   T1  an audited artifact — SOC 2 Type II, an ISO 27001 certificate with its Statement of
#       Applicability, a penetration test report, a regulatory examination finding. Somebody
#       independent looked, and recorded what they looked at and when.
#   T2  a contractual commitment — an executed DPA, a clause in the signed agreement, a
#       security addendum. Not a demonstration, but an obligation with a remedy behind it.
#   T3  a vendor assertion — a completed questionnaire, a trust centre, a security
#       whitepaper. The vendor describing itself.
#   T4  public copy — a privacy policy, a website, a status page, marketing material.
#
# Only T1 and T2 may satisfy a requirement, and that line is what the whole assessment layer
# stands on. A privacy page is a marketing artifact: scanning it is genuinely useful for
# knowing what to ASK, and is never a reason to stop asking.
TIERS = ("T1", "T2", "T3", "T4")

SATISFYING_TIERS = ("T1", "T2")
"""The only tiers that may close a requirement.

Referenced everywhere and never inlined, so the rule has exactly one definition to change and
one place to argue with. `evals/proposal-boundary.sh` proves no code path gets around it.
"""

TIER_LABEL = {
    "T1": "audited artifact",
    "T2": "contractual commitment",
    "T3": "vendor assertion",
    "T4": "public copy",
}

EVIDENCE_ID_RE = re.compile(r"^EV-\d{3,}$")
PROPOSAL_ID_RE = re.compile(r"^PR-\d{3,}$")


class Refusal(Exception):
    """A mutation the engine declines to perform.

    Raised before the store file is opened, so a refused mutation leaves the file
    byte-identical. Asserted in self-test rather than trusted.
    """


# --- Dates --------------------------------------------------------------------

def check_date(value: str, field: str) -> str:
    if not isinstance(value, str) or not DATE_RE.match(value):
        raise Refusal(
            f"{field} must be a canonical zero-padded date, YYYY-MM-DD; got {value!r}. "
            f"'2026-7-1' is refused because it sorts after '2026-10-01' as text, and every "
            f"cadence here compares dates.")
    try:
        date.fromisoformat(value)
    except ValueError:
        raise Refusal(f"{field} is not a real calendar date: {value!r}")
    return value


def days_between(earlier: str, later: str) -> int:
    return (date.fromisoformat(later) - date.fromisoformat(earlier)).days


def now_ts() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def utc_today() -> str:
    return now_ts()[:10]


# --- Store IO -----------------------------------------------------------------

def new_store(org: str, prepared_by: str = "", scope_note: str = "") -> dict:
    ts = now_ts()
    return {
        "schemaVersion": SCHEMA_VERSION,
        "family": FAMILY,
        "meta": {"orgName": org, "preparedBy": prepared_by, "scopeNote": scope_note,
                 "asOf": ts[:10]},
        "settings": json.loads(json.dumps(SETTINGS_DEFAULTS)),
        "vendors": [],
        "arrangements": [],
        "history": [],
        "snapshots": [],
        "createdAt": ts,
        "updatedAt": ts,
    }


def load(path: str) -> dict:
    """Open a `.vnd`. Validation guards WRITES; a store carrying a bad value still opens.

    A register that refuses to load because one field is wrong is a register nobody can fix.
    """
    try:
        with open(path, encoding="utf-8") as fh:
            store = json.load(fh)
    except FileNotFoundError:
        raise Refusal(f"no such store: {path}")
    except json.JSONDecodeError as exc:
        raise Refusal(f"{path} is not valid JSON (line {exc.lineno}, "
                      f"column {exc.colno}): {exc.msg}")
    if not isinstance(store, dict):
        raise Refusal(f"{path} must contain a JSON object, got {type(store).__name__}")
    fam = store.get("family")
    if fam != FAMILY:
        raise Refusal(
            f"{path} is not a vendor register: family is {fam!r}, expected {FAMILY!r}. "
            f"A risk register (.rr), exceptions register (.exc) or business context (.biz) "
            f"belongs to a different skill.")
    if store.get("schemaVersion") != SCHEMA_VERSION:
        raise Refusal(f"{path} is schemaVersion {store.get('schemaVersion')!r}; "
                      f"this engine reads {SCHEMA_VERSION}")
    # Defaults merged PER KEY, so a store written before a setting existed gains it rather
    # than losing every setting it did have.
    store["meta"] = {"orgName": "", "preparedBy": "", "scopeNote": "", "asOf": "",
                     **(store.get("meta") or {})}
    settings = json.loads(json.dumps(SETTINGS_DEFAULTS))
    settings.update(store.get("settings") or {})
    settings["cadenceDays"] = {**SETTINGS_DEFAULTS["cadenceDays"],
                               **((store.get("settings") or {}).get("cadenceDays") or {})}
    store["settings"] = settings
    for key in ("vendors", "arrangements", "history", "snapshots"):
        if not isinstance(store.get(key), list):
            store[key] = []
    return store


def save(path: str, store: dict) -> None:
    store["updatedAt"] = now_ts()
    directory = os.path.dirname(os.path.abspath(path)) or "."
    fd, tmp = tempfile.mkstemp(dir=directory, suffix=".vnd.tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(store, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def append_history(store: dict, event: str, target: str, actor: str = "",
                   why: str = "", detail: dict = None) -> None:
    entry = {"event": event, "target": target, "actor": actor or "", "ts": now_ts()}
    if why:
        entry["why"] = why
    if detail:
        entry["detail"] = detail
    store["history"].append(entry)


def next_id(store: dict, kind: str) -> str:
    prefix, key, pattern = (("V", "vendors", VENDOR_ID_RE) if kind == "vendor"
                            else ("VA", "arrangements", ARRANGEMENT_ID_RE))
    used = [int(r["id"].split("-")[1]) for r in store[key]
            if pattern.match(str(r.get("id", "")))]
    return "%s-%03d" % (prefix, (max(used) + 1) if used else 1)


# --- Provenance ---------------------------------------------------------------
#
# The same {value, declaredBy, declaredOn, basis} shape `business-context` uses. The shape is
# reused; the module is NOT imported. Every shipped script must run standalone — a skill
# directory is usable on its own — and CAC-AP-1 §2.6 says the transport between skills is
# data, never an import.

def declared(value, by: str = "", basis: str = "", on: str = "") -> dict:
    return {"value": value, "declaredBy": str(by or "").strip(),
            "declaredOn": on or utc_today(), "basis": str(basis or "").strip()}


def is_attributed(rec) -> bool:
    return isinstance(rec, dict) and bool(str(rec.get("declaredBy") or "").strip())


def value_of(rec):
    """Read a field that may be wrapped or bare.

    A bare value loads and is reported as unattributed rather than refused: a register that
    rejects a hand-edited file is a register people stop hand-editing, and then stop using.
    """
    return rec.get("value") if isinstance(rec, dict) and "value" in rec else rec


# --- Objects ------------------------------------------------------------------

def add_vendor(store: dict, name: str, jurisdiction: str = "", group_parent: str = "",
               identifiers: dict = None, by: str = "", basis: str = "") -> dict:
    if not str(name or "").strip():
        raise Refusal("a vendor needs a --name")
    rec = {
        "id": next_id(store, "vendor"),
        "name": name.strip(),
        "jurisdiction": str(jurisdiction or "").strip(),
        "groupParent": str(group_parent or "").strip(),
        "identifiers": dict(identifiers or {}),
        # Declared designations only. No bundled regulatory list drives engine behaviour:
        # a CTPP list is dated documentation, and a register whose behaviour changed when
        # someone refreshed a bundled file would be unauditable.
        "designations": [],
    }
    if by or basis:
        rec["provenance"] = declared(rec["name"], by, basis)
    store["vendors"].append(rec)
    append_history(store, "vendor-added", rec["id"], by, why=rec["name"])
    return rec


def add_arrangement(store: dict, vendor_ref: str, services: str, owner: str,
                    supports: str = "", entity_ref: str = "", starts_on: str = "",
                    ends_on: str = "", cost: str = "", gvsc=None, sr=None,
                    by: str = "") -> dict:
    """One agreement, for one set of services, with one owner.

    Refuses without an owner. `GV.SC-02` requires roles and responsibilities be established
    with suppliers, and an arrangement nobody owns is the one that goes stale — every
    escalation this register raises has to land on somebody.
    """
    if not str(vendor_ref or "").strip():
        raise Refusal("an arrangement needs --vendor, the id of the provider it is with")
    if not any(v.get("id") == vendor_ref for v in store["vendors"]):
        known = ", ".join(v.get("id", "?") for v in store["vendors"]) or "none yet"
        raise Refusal(
            f"no vendor {vendor_ref!r} in this register (known: {known}). An arrangement "
            f"hanging off a provider that does not exist is a row nobody can follow up.")
    if not str(services or "").strip():
        raise Refusal("an arrangement needs --services: what this provider actually does")
    if not str(owner or "").strip():
        raise Refusal(
            "an arrangement needs an --owner.\n"
            "  GV.SC-02 requires roles and responsibilities be established with suppliers, "
            "and every escalation this register raises has to land on somebody. An "
            "arrangement nobody owns is the one that goes stale.")
    rec = {
        "id": next_id(store, "arrangement"),
        "vendorRef": vendor_ref,
        # Present from the first commit, defaulting to the single org. A register spanning
        # legal entities is legitimate when a human declares it; it is a silent merge
        # otherwise, which is the failure `assemble_pack.py` already refuses for packs.
        "entityRef": str(entity_ref or "").strip() or (store["meta"].get("orgName") or ""),
        "services": services.strip(),
        "supports": str(supports or "").strip(),
        "owner": owner.strip(),
        "startsOn": check_date(starts_on, "--starts") if starts_on else "",
        "endsOn": check_date(ends_on, "--ends") if ends_on else "",
        "cost": str(cost or "").strip(),
        "gvsc": list(gvsc or []),
        "sr": list(sr or []),
        "subcontractors": [],
        # Documented and tested are SEPARATE fields with separate dates. A written but
        # never-exercised exit plan is the sector's most common paper control, and
        # collapsing the two into one "has an exit strategy" boolean is what lets it pass.
        "exit": {"documentedOn": "", "testedOn": "", "note": ""},
        "requirements": [],
        "evidence": [],
        "proposals": [],
        "assessments": [],
        "criticality": None,
        "retired": None,
        "priorArrangementRef": "",
    }
    store["arrangements"].append(rec)
    append_history(store, "arrangement-added", rec["id"], by, why=rec["services"],
                   detail={"vendorRef": vendor_ref, "owner": rec["owner"]})
    return rec


def find_arrangement(store: dict, aid: str) -> dict:
    for rec in store["arrangements"]:
        if rec.get("id") == aid:
            return rec
    known = ", ".join(r.get("id", "?") for r in store["arrangements"]) or "none yet"
    raise Refusal(f"no arrangement {aid!r} in this register (known: {known})")


def find_vendor(store: dict, vid: str) -> dict:
    for rec in store["vendors"]:
        if rec.get("id") == vid:
            return rec
    raise Refusal(f"no vendor {vid!r} in this register")


# --- The scale is a setting ---------------------------------------------------
#
# NISTIR 8179 declines to prescribe levels — the user "creates a way to measure or rank".
# Hard-coding three would impose what the source deliberately did not, so the scale is a
# setting, and every assigned value records the scale version it was assigned under. Same
# discipline that lets `risk-register` judge "it was over appetite THEN" by the appetite in
# force then.

def set_scale(store: dict, levels, version: str = "") -> list:
    levels = [str(x).strip() for x in levels if str(x or "").strip()]
    if len(levels) < 2:
        raise Refusal("a criticality scale needs at least two levels, lowest first")
    if UNTRACED in levels or UNCLASSIFIED in levels:
        raise Refusal(
            f"{UNTRACED!r} and {UNCLASSIFIED!r} are states, not levels, and must never be "
            f"members of the scale.\n"
            f"  If either were on the scale it would sort against real levels, and an "
            f"arrangement nobody could trace would take a position in a ranking it was "
            f"never assigned.")
    if len(set(levels)) != len(levels):
        raise Refusal("a criticality scale cannot repeat a level")
    # Values already assigned are NOT remapped. Remapping would silently restate somebody's
    # judgement in words they did not choose; naming the orphans makes it their call.
    orphans = []
    for rec in store["arrangements"]:
        conf = ((rec.get("criticality") or {}).get("confirmed") or {})
        val = conf.get("value")
        if val and val not in levels:
            orphans.append("%s (%s)" % (rec["id"], val))
    if orphans:
        raise Refusal(
            "changing the scale would orphan a confirmed level on: %s.\n"
            "  These values are not remapped, because remapping restates somebody's "
            "judgement in words they did not choose. Re-confirm them on the new scale "
            "first, or keep the old one."
            % ", ".join(orphans))
    store["settings"]["criticalityScale"] = levels
    store["settings"]["scaleVersion"] = str(version or "").strip() or ("v%d" % (
        len(store["snapshots"]) + 2))
    append_history(store, "scale-set", "settings", why=", ".join(levels),
                   detail={"scaleVersion": store["settings"]["scaleVersion"]})
    return levels


def criticality_rank(store: dict, value: str) -> int:
    """Position on the configured scale, lowest first.

    RAISES on `untraced` and `unclassified` rather than returning a number. This is the
    single most important line in the file: one `sorted(key=rank)` that placed `untraced`
    at the bottom would silently downgrade every arrangement nobody could trace, and the
    resulting board table would look complete.
    """
    scale = store["settings"]["criticalityScale"]
    if value in (UNTRACED, UNCLASSIFIED):
        raise Refusal(
            f"{value!r} has no position on the criticality scale and must not be ordered "
            f"against one.\n"
            f"  It is a state, not a level: it says the walk did not reach a declared "
            f"criticality, which is a reason to look rather than a reason to rank. Sorting "
            f"it anywhere — and the bottom is where it lands by default — turns 'we do not "
            f"know' into 'not important'.")
    if value not in scale:
        raise Refusal(f"{value!r} is not on this register's scale ({', '.join(scale)})")
    return scale.index(value)


# --- The criticality walk (NISTIR 8179 Process E, bounded) --------------------
#
# TWINNED with skills/ai-register/scripts/ai_register.py, which holds the same four functions
# — _norm, context_workflow_for, context_parent_of, derive_criticality — and says so in its
# own header: "Criticality: mirrored from vendor-register, deliberately". This end said
# nothing back for the whole life of that copy, so a maintainer editing the walk HERE, in the
# original, had nothing telling them a second copy existed.
#
# Deliberately duplicated on the usual terms: every shipped script must run standalone, so a
# cross-skill import needs sys.path surgery and breaks the moment one skill directory is used
# on its own. What replaces the import is tools/check-twins.py (CAC-TW-1), which executes both
# copies over a shared corpus of contexts on every push. Each skill's own self-test cannot see
# the other copy, by construction.
#
# The path above is what makes this greppable. The sibling's declaration named the SKILL and
# not the file, which is why CAC-TW-1 could not find the pair — the same ungreppable-prose
# failure that let evidence_text drift for four releases (BL-191, BL-217).

def _norm(name: str) -> str:
    return re.sub(r"\s+", " ", str(name or "")).strip().casefold()


def context_workflows(context: dict) -> list:
    return list((context or {}).get("crownJewels") or [])


def context_workflow_for(context: dict, node: str):
    """The declared workflow this node IS, if any."""
    for wf in context_workflows(context):
        if _norm(wf.get("system")) == _norm(node):
            return wf
    return None


def context_parent_of(context: dict, node: str) -> str:
    """The workflow that declares it depends on this node — the next hop up."""
    for wf in context_workflows(context):
        for dep in (wf.get("dependsOn") or []):
            if _norm(dep) == _norm(node):
                return wf.get("system") or ""
    return ""


def declared_criticality(wf: dict) -> str:
    """The level a crown jewel declares, or `""` when it declares none.

    REFUSES A CONTAINER, and that is the whole reason this exists as a function. The walk
    below used to read the field inline:

        if wf and str(wf.get("criticality") or "").strip():
            return str(wf["criticality"]).strip(), path, False

    `str({...})` is truthy and non-empty. A crown jewel whose `criticality` was a dict
    therefore sailed straight past that guard and the walk returned
    `"{'value': 'high', 'basis': 'board said so'}"` **as the criticality level** — a Python
    repr standing in for a governance decision, produced confidently, and only caught later
    (if at all) when `_rank` refused it as off-scale.

    That is BL-209's defect one layer below the renderers: `esc()` now refuses a container
    because a container never belongs in a text slot, and a derived criticality level is a
    text slot with more riding on it than a page.

    It is not hypothetical. BL-54's R-3 changes `crownJewels[].criticality` from a bare
    string to a record carrying its own basis. **This refusal is what makes that migration
    safe rather than hopeful** — until the reader lands, a container here is a store written
    against a contract this engine does not yet implement, and saying so is the only honest
    answer. When R-3 ships, this function is where the new shape is read; the refusal stays
    for everything that is still neither a level nor a record.

    An empty or whitespace-only value is NOT a refusal — it is a crown jewel that declares
    no criticality, which is ordinary and yields `untraced` further down. Scalars are passed
    through unchanged so the off-scale message still comes from `_rank`, which words it
    better than anything here could.
    """
    raw = wf.get("criticality")
    if isinstance(raw, (dict, list, tuple, set)):
        raise Refusal(
            "crown jewel %r declares a criticality that is a %s, not a level: %.120r\n"
            "  The walk cannot turn a container into a level, and rendering it would put a "
            "Python repr where a governance decision belongs. Either the store was written "
            "against a newer crown-jewel shape than this engine reads, or the field was "
            "hand-edited. Neither is something this walk may guess past."
            % (wf.get("system") or "(unnamed)", type(raw).__name__, raw))
    return "" if raw is None else str(raw).strip()


def derive_criticality(arrangement: dict, context: dict, max_hops: int = TRACE_MAX_HOPS):
    """Trace what this arrangement supports up to a workflow with a declared criticality.

    Returns `(level_or_UNTRACED, trace_path, truncated)`.

    Bounded at two hops — arrangement → system/component → workflow — because Process E is a
    reconciliation across levels, not a per-component re-derivation, and nobody runs
    twenty-one sub-processes against two hundred vendors. Beyond the bound the walk stops and
    says it was truncated.

    **A truncated trace is not a failed one and not a confident one.** It yields `untraced`
    AND records `truncated`, so a reader can tell "there was no more chain" from "there was
    more chain than we followed". Returning a level here would be the worst outcome
    available: a confident answer from an unfinished walk.

    With no context at all every arrangement derives `untraced`. That is correct and loud:
    the skill works standalone per CAC-AP-1 §2.1, and it does not pretend to know what it
    cannot see.
    """
    seen, path = set(), []
    node = str(arrangement.get("supports") or "").strip()
    for _hop in range(max(0, int(max_hops))):
        if not node or _norm(node) in seen:
            break
        seen.add(_norm(node))
        path.append(node)
        wf = context_workflow_for(context, node)
        if wf:
            level = declared_criticality(wf)
            if level:
                return level, path, False
        node = context_parent_of(context, node)
    # `node` still set means the chain continued past where we stopped — either the hop
    # budget ran out or we re-entered a cycle. Both are "more to walk", both truncate.
    return UNTRACED, path, bool(node)


def classify(store: dict, aid: str, context: dict = None, confirm: str = "",
             by: str = "", basis: str = "", layer: str = "") -> dict:
    """Derive a criticality, and optionally record the level a person assigned.

    Derivation PROPOSES. Only `--confirm` with `--by` assigns, and the engine refuses an
    unattributed confirmation: an unnamed final level is precisely what 8179 E.5 exists to
    prevent, and a register full of them cannot be defended to an assessor.

    A confirmed level that DIFFERS from the derived one is stored without complaint. It is a
    finding, not an error — Process E exists for consistency across layers, so a
    disagreement is information — and `escalations` surfaces it as `criticality-conflict`.
    """
    if layer and layer not in ("system", "component"):
        raise Refusal("--layer must be 'system' or 'component' if given")
    if confirm and not str(by or "").strip():
        raise Refusal(
            "--confirm needs --by: the name of the person assigning this level.\n"
            "  Derivation proposes and a person assigns (NISTIR 8179 E.5). An unattributed "
            "final level is the thing that step exists to prevent, and it cannot be "
            "defended to an assessor by pointing at the tool that produced it.")
    scale = store["settings"]["criticalityScale"]
    if confirm and confirm not in scale:
        raise Refusal(
            f"{confirm!r} is not on this register's scale ({', '.join(scale)}). "
            f"Use `set-scale` to change the scale deliberately, rather than assigning a "
            f"level that nothing else in the register can compare against.")
    rec = find_arrangement(store, aid)
    if rec.get("retired"):
        raise Refusal(f"{aid} is retired; a closed arrangement is not re-classified. "
                      f"A resumed relationship opens a new arrangement.")
    hops = int(store["settings"].get("traceMaxHops") or TRACE_MAX_HOPS)
    level, path, truncated = derive_criticality(rec, context or {}, hops)
    block = rec.get("criticality") or {}
    block["derived"] = level
    block["derivedOn"] = utc_today()
    block["trace"] = path
    block["truncated"] = truncated
    # What the workflow said when we last looked. `criticality-unreconciled` compares
    # against this, so a workflow that got more critical after somebody signed off
    # re-opens the question instead of sitting behind a stale confirmation.
    block["derivedFromLevel"] = level
    if layer:
        block["layer"] = layer
    if confirm:
        block["confirmed"] = {"value": confirm, "by": by.strip(),
                              "on": utc_today(), "basis": str(basis or "").strip(),
                              "scaleVersion": store["settings"].get("scaleVersion") or "",
                              "againstDerived": level}
    else:
        block.setdefault("confirmed", None)
    rec["criticality"] = block
    append_history(store, "classified", aid, by,
                   why=("confirmed %s" % confirm) if confirm else ("derived %s" % level),
                   detail={"derived": level, "trace": path, "truncated": truncated})
    return block


def criticality_of(rec: dict) -> str:
    """The level to act on: what a person confirmed, else what was derived, else unclassified.

    Never coerces. `untraced` stays `untraced` all the way to the surface.
    """
    block = rec.get("criticality") or {}
    conf = block.get("confirmed") or {}
    if conf.get("value"):
        return str(conf["value"])
    if block.get("derived"):
        return str(block["derived"])
    return UNCLASSIFIED


# --- Batteries: what gets asked, and what narrows it --------------------------
#
# A small CORE keyed to `GV.SC`, not a questionnaire product. The valuable output is not a
# 300-question bank; it is what the vendor's own documentation left open, which means the set
# has to be small enough that subtracting from it produces something a person will actually
# send.
#
# EVERY question asks for evidence with a date, never an attestation. "Do you encrypt data at
# rest?" is worthless — every vendor answers yes. "What is the most recent evidence you can
# provide that data at rest is encrypted, and when was it produced?" has a discoverable answer,
# a date, and degrades honestly when the answer is "none". `evals/questions.sh` fails on the
# attestation shapes, so this is enforced rather than remembered.

# Questions carry a stable ID, and the id is what `ask` subtracts against. Matching a
# satisfied requirement to an open question by comparing prose would be fuzzy in exactly the
# place that must not be: a near-miss would either drop a question nobody answered or keep one
# that was. `propose --requirement contract-terms.incident-notice` links a reading to the
# question it answers; free text is still accepted and simply subtracts nothing.
BATTERIES = (
    {
        "id": "contract-terms",
        "gvsc": ["GV.SC-05"],
        "sr": ["SR-3"],
        "appliesWhen": {},
        "questions": (
            {"id": "incident-notice",
             "ask": "What is the executed document, and which clause, that commits this "
                    "provider to notifying us of a security incident — and within what period?"},
            {"id": "audit-right",
             "ask": "Which signed document sets out our right to audit or to receive assurance "
                    "reports, and when was it last exercised?"},
        ),
    },
    {
        "id": "assurance",
        "gvsc": ["GV.SC-06", "GV.SC-07"],
        "sr": ["SR-6"],
        "appliesWhen": {},
        "questions": (
            {"id": "latest-report",
             "ask": "What is the most recent independent assurance report for the service we "
                    "consume, what period does it cover, and what did it exclude from scope?"},
            {"id": "open-findings",
             "ask": "What findings were open at the end of that period, and what evidence "
                    "shows their current state?"},
        ),
    },
    {
        "id": "exit",
        "gvsc": ["GV.SC-10"],
        "sr": ["SR-12"],
        # Top of the scale only. An exit plan for a marketing sandbox is paperwork.
        "appliesWhen": {"criticalityAtLeast": "TOP"},
        "questions": (
            {"id": "last-exercised",
             "ask": "What is the dated record of the last time exit from this provider was "
                    "actually exercised, rather than documented?"},
            {"id": "deletion-evidence",
             "ask": "What evidence would show our data had been returned and then deleted, and "
                    "how long would producing it take?"},
        ),
    },
    {
        "id": "subprocessors",
        "gvsc": ["GV.SC-07", "GV.SC-09"],
        "sr": ["SR-3"],
        "appliesWhen": {},
        "questions": (
            {"id": "current-list",
             "ask": "What is the current dated list of subprocessors for this service, and how "
                    "are we notified before it changes?"},
        ),
    },
    {
        "id": "ai-overlay",
        "gvsc": ["GV.SC-07"],
        "sr": ["SR-3"],
        # Gated on a flag declarable on the ARRANGEMENT or on the org profile.
        "appliesWhen": {"flag": "aiInUse"},
        "questions": (
            {"id": "models-in-scope",
             "ask": "What documentation states which models process our data, and when was it "
                    "last updated?"},
            {"id": "training-use",
             "ask": "What evidence shows whether our data is used to train or fine-tune a "
                    "model, and what dated commitment covers that?"},
        ),
    },
)


# --- Regime overlays ----------------------------------------------------------
#
# An overlay adds batteries on top of the `GV.SC` core when a profile flag says a regime
# applies. **None replaces the core**: a register with no overlay enabled is still a complete
# GV.SC register, and that is checked rather than asserted.
#
# **This ships EMPTY, and that is a decision rather than an unfinished job.**
#
# DORA, NYDFS Part 500, the US interagency guidance and the SEC rules were all drafted from
# secondary sources. An overlay tells a user that a regulation requires something of them, and
# a compliance tool asserting an obligation it cannot cite is worse than one that stays quiet —
# the user cannot tell the difference between a checked claim and a plausible one, and will act
# on both. So the machinery ships and the content does not, pending a primary-source pass.
#
# `register_overlay` REFUSES an uncited requirement, so this cannot be quietly relaxed later:
# whoever adds the content has to name the article or section, and the refusal message says
# what a source has to be. See `references/overlays.md`.

OVERLAYS = ()
"""Deliberately empty. See the note above, and `references/overlays.md`.

Populate through `register_overlay`, which refuses anything uncited."""


def register_overlay(overlay: dict, into=None) -> dict:
    """Add an overlay, refusing any requirement that cannot say where it comes from.

    The gate is the point. An overlay is the only part of this skill that tells a user a THIRD
    PARTY — a regulator — requires something of them, and that claim has to be traceable to the
    text it came from. A citation to a summary, a vendor blog or a consultancy explainer is not
    a citation to the regulation.
    """
    if not str(overlay.get("id") or "").strip():
        raise Refusal("an overlay needs an id")
    if not str(overlay.get("flag") or "").strip():
        raise Refusal(
            "overlay %r needs a --flag: the profile key that selects it.\n"
            "  An overlay that is always on is not an overlay, it is the core."
            % overlay.get("id"))
    for battery in (overlay.get("batteries") or []):
        for q in (battery.get("questions") or []):
            src = str(q.get("source") or "").strip()
            if not src:
                raise Refusal(
                    "overlay %r, question %r has no `source`.\n"
                    "  Every overlay question must cite the article or section it comes from, "
                    "checked against the regulation or the supervisory text — not a summary, a "
                    "vendor explainer or a consultancy note. An overlay asserting an obligation "
                    "it cannot cite does not ship: a reader cannot tell a checked claim from a "
                    "plausible one, and will act on both."
                    % (overlay["id"], q.get("id")))
    target = OVERLAYS if into is None else into
    if isinstance(target, tuple):
        raise Refusal("pass a mutable list as `into` to register an overlay at runtime")
    target.append(overlay)
    return overlay


def overlays_for(context: dict = None, overlays=None) -> list:
    """The overlays a profile turns on. Absence never enables one — a regime applies because
    somebody declared it, not because nothing said otherwise."""
    profile = ((context or {}).get("profile") or {})
    active = []
    for ov in (OVERLAYS if overlays is None else overlays):
        entry = profile.get(ov["flag"])
        value = entry.get("value") if isinstance(entry, dict) else entry
        if value is True:
            active.append(ov)
    return active


def question_key(battery: dict, question: dict) -> str:
    return "%s.%s" % (battery["id"], question["id"])


def all_questions(batteries=None) -> list:
    out = []
    for battery in (batteries if batteries is not None else BATTERIES):
        for q in battery["questions"]:
            out.append((battery, q))
    return out


def _battery_applies(battery: dict, rec: dict, store: dict, context: dict):
    """(applies, skip_record_or_None). CAC-AP-1 narrowing, reused rather than re-derived.

    §2.2 — a missing criticality or a missing flag means NOT DECLARED, so the battery
    APPLIES. Absence asks more. An arrangement nobody classified is exactly the one that must
    not be quietly treated as low-risk.

    §2.3 — a declaration on the arrangement outranks the org profile IN BOTH DIRECTIONS. An
    organisation that declared no AI still gets the AI battery on a provider whose own record
    says a model touches our data, and vice versa.

    §2.4 — every skip carries the flag, the declarer and the date, so an assessor can tell
    "we judged this out of scope, here is who said so" from "nobody asked".
    """
    cond = battery.get("appliesWhen") or {}

    if "criticalityAtLeast" in cond:
        level = criticality_of(rec)
        # `untraced` and `unclassified` get the FULL battery. Neither is a level, so neither
        # can narrow anything — and the arrangement nobody could place is the one worth asking
        # every question of.
        #
        # This is the FIRST of two layers, and it is here for intent rather than because the
        # second is weak: `level in scale` below also excludes both states, so removing this
        # line changes no behaviour today. It is kept because the obvious future edit — using
        # `criticality_rank` to compare levels — would raise on these states rather than
        # returning a number, and a reader needs to know that is deliberate before working out
        # why their comparison blew up.
        if level in (UNTRACED, UNCLASSIFIED):
            return True, None
        scale = store["settings"]["criticalityScale"]
        if cond["criticalityAtLeast"] == "TOP" and level in scale:
            if scale.index(level) < len(scale) - 1:
                return False, {
                    "battery": battery["id"],
                    "reason": "criticality %r is below the top of the scale (%s)"
                              % (level, scale[-1]),
                    "flag": "criticality",
                    "declaredBy": ((rec.get("criticality") or {}).get("confirmed") or {})
                                  .get("by", ""),
                    "declaredOn": ((rec.get("criticality") or {}).get("confirmed") or {})
                                  .get("on", ""),
                }
        return True, None

    if "flag" in cond:
        flag = cond["flag"]
        # Subject layer first (§2.3), and `None` is not `False`: only an explicit declaration
        # on the arrangement outranks anything.
        subject = (rec.get("declares") or {}).get(flag)
        if isinstance(subject, dict):
            sub_val, sub_by, sub_on = (subject.get("value"), subject.get("declaredBy", ""),
                                       subject.get("declaredOn", ""))
        else:
            sub_val, sub_by, sub_on = subject, "", ""
        if sub_val is True:
            return True, None
        if sub_val is False:
            return False, {"battery": battery["id"],
                           "reason": "the arrangement declares %s false" % flag,
                           "flag": flag, "declaredBy": sub_by, "declaredOn": sub_on}
        entry = ((context or {}).get("profile") or {}).get(flag)
        if isinstance(entry, dict) and entry.get("value") is False:
            return False, {"battery": battery["id"],
                           "reason": "the organisation profile declares %s false" % flag,
                           "flag": flag,
                           "declaredBy": entry.get("declaredBy", ""),
                           "declaredOn": entry.get("declaredOn", "")}
        # Not declared anywhere, or declared true. Either way: ask.
        return True, None

    return True, None


def batteries_for(rec: dict, store: dict, context: dict = None, overlays=None) -> dict:
    """Which batteries apply to this arrangement, and which were skipped and why.

    Core first, then any overlay a declared profile flag turned on. The core is never replaced
    or narrowed by an overlay: a register with no overlay enabled asks exactly what it asked
    before overlays existed, which is asserted in the self-test rather than assumed.
    """
    pool = list(BATTERIES)
    for ov in overlays_for(context, overlays):
        pool.extend(ov.get("batteries") or [])
    applied, skipped = [], []
    for battery in pool:
        yes, skip = _battery_applies(battery, rec, store, context or {})
        if yes:
            applied.append(battery)
        elif skip:
            skipped.append(skip)
    return {"applied": applied, "skipped": skipped}


# --- Evidence -----------------------------------------------------------------

def _next_sub_id(rec: dict, key: str, prefix: str, pattern) -> str:
    used = [int(x["id"].split("-")[1]) for x in (rec.get(key) or [])
            if pattern.match(str(x.get("id", "")))]
    return "%s-%03d" % (prefix, (max(used) + 1) if used else 1)


def ingest(store: dict, aid: str, kind: str, tier: str, source: str, scope: str = "",
           period_start: str = "", period_end: str = "", url: str = "",
           retrieved: str = "", by: str = "") -> dict:
    """Record an artifact a vendor supplied, with the tier that says what it can close.

    **Scope and period are required for T1**, and this is the refusal that makes the tier mean
    anything. A SOC 2 that excludes the subservice organisation actually running the workload
    has not covered that workload, and a report with no period cannot expire — it would sit in
    the register looking like current assurance forever. The two failures are the same failure:
    an artifact whose limits are not written down gets read as though it had none.

    Anything fetched from a URL needs `--retrieved`. Public copy changes without notice, and
    an undated capture is a claim about a page that may no longer say it.
    """
    if tier not in TIERS:
        raise Refusal("--tier must be one of %s; got %r" % (", ".join(TIERS), tier))
    if not str(kind or "").strip():
        raise Refusal("--kind names what the artifact is (soc2-type2, iso27001-cert, dpa, ...)")
    if not str(source or "").strip():
        raise Refusal("--source says where this came from. An artifact with no provenance "
                      "cannot be re-found by the person who has to check it.")
    if tier == "T1":
        missing = []
        if not str(scope or "").strip():
            missing.append("--scope")
        if not (str(period_start or "").strip() and str(period_end or "").strip()):
            missing.append("--period-start and --period-end")
        if missing:
            raise Refusal(
                "a T1 artifact needs %s.\n"
                "  T1 is the tier that can close a requirement, and it can only do so WITHIN "
                "its scope and period. A SOC 2 excluding the subservice organisation running "
                "the workload has not covered it; a report with no period cannot expire, so it "
                "would sit here looking like current assurance forever."
                % " and ".join(missing))
    if str(url or "").strip() and not str(retrieved or "").strip():
        raise Refusal(
            "evidence with a --url needs --retrieved.\n"
            "  Public copy changes without notice. An undated capture is a claim about a page "
            "that may no longer say it, and nobody can check which.")
    rec = find_arrangement(store, aid)
    entry = {
        "id": _next_sub_id(rec, "evidence", "EV", EVIDENCE_ID_RE),
        "kind": kind.strip(),
        "tier": tier,
        "source": source.strip(),
        "scope": str(scope or "").strip(),
        "periodStart": check_date(period_start, "--period-start") if period_start else "",
        "periodEnd": check_date(period_end, "--period-end") if period_end else "",
        "url": str(url or "").strip(),
        "retrievedOn": check_date(retrieved, "--retrieved") if retrieved else "",
        "ingestedOn": utc_today(),
        "ingestedBy": str(by or "").strip(),
    }
    rec.setdefault("evidence", []).append(entry)
    append_history(store, "evidence-ingested", aid, by,
                   why="%s (%s)" % (entry["kind"], TIER_LABEL[tier]),
                   detail={"evidenceId": entry["id"], "tier": tier})
    return entry


def find_evidence(rec: dict, eid: str) -> dict:
    for ev in (rec.get("evidence") or []):
        if ev.get("id") == eid:
            return ev
    known = ", ".join(e.get("id", "?") for e in (rec.get("evidence") or [])) or "none"
    raise Refusal("no evidence %r on %s (known: %s)" % (eid, rec["id"], known))


def evidence_status(ev: dict, today: str = "", grace: int = 365) -> str:
    """`current`, `in-grace` or `expired`, measured from the END OF THE PERIOD.

    A tier that cannot expire is not evidence, it is a keepsake. T3 and T4 have no period and
    are reported `current` because they close nothing anyway — their job is to generate
    questions, and a question does not go stale the way an assurance claim does.
    """
    today = today or utc_today()
    end = str(ev.get("periodEnd") or "")
    if not end:
        return "current"
    age = days_between(end, today)
    if age <= 0:
        return "current"          # the period has not closed yet
    return "in-grace" if age <= int(grace) else "expired"


# --- Generated questions ------------------------------------------------------
#
# The whole speed argument, and the reason this is not a questionnaire product.
#
# Take the batteries the criticality gate and the overlays left applicable, subtract what T1
# and T2 evidence genuinely covers, and emit WHAT REMAINS OPEN. Read a SOC 2 properly and the
# set might be four questions instead of forty, which is the difference between a decision this
# week and a decision next quarter. A full questionnaire is simply the degenerate case where
# the vendor supplied nothing — same code path, no special casing.
#
# T3 and T4 subtract NOTHING. That is the product claim, and `evals/questions.sh` asserts it in
# the only form that matters: the same three requirements covered by a T1 shrink the set, and
# covered by a T3 do not.

NOTHING_OPEN = ("Nothing is open for this arrangement at its current criticality. Every "
                "applicable question is covered by evidence that can satisfy it.")
"""Printed when the subtraction leaves nothing.

An empty result must never be an empty string. A blank page and "we have asked everything and
it is all evidenced" look identical on a screen and mean opposite things, and the blank one is
the one somebody forwards as though it were the second.
"""


def ask(store: dict, aid: str, context: dict = None, today: str = "") -> dict:
    """What is still worth asking about this arrangement, and why each question is being asked.

    A question survives when nothing that CAN satisfy it does. A question whose requirement is
    covered by evidence that has slipped into grace is still emitted, marked `re-confirm`
    rather than `open`: the answer was good and is ageing, which is a different request from
    one nobody has ever answered, and collapsing the two would either nag or go quiet.
    """
    today = today or utc_today()
    rec = find_arrangement(store, aid)
    grace = int(store["settings"].get("evidenceGraceDays") or 365)
    narrowed = batteries_for(rec, store, context or {})

    # What a satisfying tier actually covers, keyed by the question it answers. Only
    # requirements closed by T1/T2 count — the tier rule is not re-implemented here, it is
    # read off SATISFYING_TIERS, so there is one definition of what may close anything.
    covered = {}
    for req in (rec.get("requirements") or []):
        if not req.get("met"):
            continue
        key = str(req.get("requirement") or "")
        ev_id = str(req.get("evidenceRef") or "")
        try:
            ev = find_evidence(rec, ev_id) if ev_id else None
        except Refusal:
            ev = None
        if not ev or ev["tier"] not in SATISFYING_TIERS:
            continue
        status = evidence_status(ev, today, grace)
        if status == "expired":
            continue          # covered by something that has run out is not covered
        # A question answered twice keeps the WORSE standing, so ageing evidence cannot be
        # masked by a fresher artifact answering a different part of the same question.
        prior = covered.get(key)
        if prior is None or (prior["status"] == "current" and status == "in-grace"):
            covered[key] = {"status": status, "evidence": ev}

    questions, reconfirm = [], []
    for battery, q in all_questions(narrowed["applied"]):
        key = question_key(battery, q)
        hit = covered.get(key)
        entry = {
            "key": key,
            "ask": q["ask"],
            "battery": battery["id"],
            "gvsc": list(battery.get("gvsc") or []),
            "sr": list(battery.get("sr") or []),
        }
        if hit is None:
            entry["status"] = "open"
            # The GV.SC reference is printed alongside by every caller, so naming it here
            # too produced "against GV.SC-05 (GV.SC-05)" on the page.
            entry["why"] = "no evidence that can satisfy this has been recorded"
            questions.append(entry)
        elif hit["status"] == "in-grace":
            entry["status"] = "re-confirm"
            entry["why"] = ("covered by %s (%s), whose period ended %s and is now in grace"
                            % (hit["evidence"]["id"], hit["evidence"]["kind"],
                               hit["evidence"]["periodEnd"]))
            reconfirm.append(entry)
    out = {
        "arrangement": aid,
        "asOf": today,
        "criticality": criticality_of(rec),
        "questions": questions + reconfirm,
        "open": len(questions),
        "reConfirm": len(reconfirm),
        "skipped": narrowed["skipped"],
        "batteriesApplied": [b["id"] for b in narrowed["applied"]],
    }
    if not out["questions"]:
        out["note"] = NOTHING_OPEN
    return out


# --- The Layer A / Layer B boundary -------------------------------------------
#
# THE safety property of this whole feature, and worth stating before the code.
#
# Layer A is the reading layer: agentic, living in SKILL.md. It ingests artifacts, works out
# what they appear to cover, and PROPOSES — every proposal citing a passage or a document
# reference. Layer B is this file: deterministic, and the only thing that can mark a
# requirement satisfied, which it does only when a named person says so.
#
# The failure this prevents is specific. A model reading a trust page and ticking requirements
# produces a register full of green derived from marketing copy — worse than an empty register,
# because it LOOKS FINISHED. Nobody re-checks a page of ticks.
#
# Two refusals hold the line, and neither is a convention:
#   1. `propose` refuses without a citation. A proposal with no citation is an opinion.
#   2. `propose` refuses to cite T3 or T4 evidence AT ALL. Those tiers generate questions and
#      never propose satisfaction, and this is the single most important refusal in the file.
#
# `evals/proposal-boundary.sh` proves no code path gets around either.

def propose(store: dict, aid: str, requirement: str, evidence_ref: str, citation: str,
            note: str = "", by: str = "") -> dict:
    """Layer A's output: a reading, with its receipt. Satisfies nothing.

    A proposal is stored `proposed` and never touches a requirement's satisfied state. That
    separation is the whole point — see `assess`, which is the only thing that closes anything.
    """
    if not str(requirement or "").strip():
        raise Refusal("--requirement names what this proposal claims to cover")
    if not str(citation or "").strip():
        raise Refusal(
            "--citation is required: the passage or document reference this reading rests on.\n"
            "  A proposal with no citation is an opinion. The person who confirms it has to be "
            "able to go and read the same thing.")
    rec = find_arrangement(store, aid)
    ev = find_evidence(rec, evidence_ref)
    if ev["tier"] not in SATISFYING_TIERS:
        raise Refusal(
            "%s is %s (%s), which can never satisfy a requirement.\n"
            "  Only %s can — an audited artifact or a contractual commitment. A vendor "
            "assertion or a public page is genuinely useful for working out what to ASK, and "
            "is never a reason to stop asking. Ingest it, let it generate questions, and "
            "propose against something that was independently looked at or actually signed."
            % (evidence_ref, ev["tier"], TIER_LABEL[ev["tier"]], " or ".join(SATISFYING_TIERS)))
    entry = {
        "id": _next_sub_id(rec, "proposals", "PR", PROPOSAL_ID_RE),
        "requirement": requirement.strip(),
        "evidenceRef": evidence_ref,
        "citation": citation.strip(),
        "note": str(note or "").strip(),
        "status": "proposed",
        "proposedOn": utc_today(),
        "proposedBy": str(by or "").strip(),
    }
    rec.setdefault("proposals", []).append(entry)
    append_history(store, "proposed", aid, by, why=entry["requirement"],
                   detail={"proposalId": entry["id"], "evidenceRef": evidence_ref})
    return entry


def find_proposal(rec: dict, pid: str) -> dict:
    for pr in (rec.get("proposals") or []):
        if pr.get("id") == pid:
            return pr
    known = ", ".join(x.get("id", "?") for x in (rec.get("proposals") or [])) or "none"
    raise Refusal("no proposal %r on %s (known: %s)" % (pid, rec["id"], known))


def assess(store: dict, aid: str, by: str, on: str = "", confirm=None, reject=None,
           why: str = "", note: str = "") -> dict:
    """Layer B: a named person rules on proposals, and the assessment clock resets.

    This is the act that writes the `assessments` list `_last_assessed` has been reading since
    v0.39.1 — the clock existed with nothing able to reset it, and this closes that seam.

    Refuses without `--by`. An unattributed assessment is exactly what this boundary exists to
    prevent, and it is what an assessor will ask for first.

    Rejected proposals are RETAINED, excluded from the working view and present on export.
    Keeping one records that a claim was examined and not accepted, which is worth having under
    examination; deleting it would leave no trace that anybody looked.
    """
    if not str(by or "").strip():
        raise Refusal(
            "--by is required: the name of the person making this assessment.\n"
            "  Derivation and reading both propose; only a person confirms. An assessment with "
            "nobody's name on it cannot be defended by pointing at the tool that produced it.")
    reject = list(reject or [])
    if reject and not str(why or "").strip():
        raise Refusal(
            "--reject needs --why.\n"
            "  A rejected reading is retained on the record, and a rejection with no reason "
            "tells a later reader nothing about whether to try again.")
    rec = find_arrangement(store, aid)
    on = check_date(on, "--on") if on else utc_today()
    confirmed_ids, rejected_ids = [], []
    for pid in list(confirm or []):
        pr = find_proposal(rec, pid)
        ev = find_evidence(rec, pr["evidenceRef"])
        # Belt and braces. `propose` already refuses these tiers, so a T3 reaching here means
        # a proposal was written some other way — and this is the last gate before a tick.
        if ev["tier"] not in SATISFYING_TIERS:
            raise Refusal(
                "%s cites %s, which is %s and can never satisfy a requirement."
                % (pid, pr["evidenceRef"], TIER_LABEL[ev["tier"]]))
        pr["status"] = "confirmed"
        pr["confirmedBy"] = by.strip()
        pr["confirmedOn"] = on
        # The audit trail IS the point: what was satisfied, by which artifact, on whose word,
        # citing what. A bare `met: true` is the thing this register exists not to produce.
        rec.setdefault("requirements", []).append({
            "requirement": pr["requirement"],
            "met": True,
            "evidenceRef": pr["evidenceRef"],
            "citation": pr["citation"],
            "checkedOn": on,
            "checkedBy": by.strip(),
            "viaProposal": pid,
        })
        confirmed_ids.append(pid)
    for pid in reject:
        pr = find_proposal(rec, pid)
        pr["status"] = "rejected"
        pr["rejectedBy"] = by.strip()
        pr["rejectedOn"] = on
        pr["rejectedWhy"] = why.strip()
        rejected_ids.append(pid)
    entry = {"on": on, "by": by.strip(), "confirmed": confirmed_ids,
             "rejected": rejected_ids, "note": str(note or "").strip()}
    rec.setdefault("assessments", []).append(entry)
    append_history(store, "assessed", aid, by,
                   why=note or ("%d confirmed, %d rejected"
                                % (len(confirmed_ids), len(rejected_ids))),
                   detail={"confirmed": confirmed_ids, "rejected": rejected_ids})
    return entry


def open_proposals(rec: dict) -> list:
    """The working view: what is still awaiting a person. Rejections are kept, not shown."""
    return [pr for pr in (rec.get("proposals") or []) if pr.get("status") == "proposed"]


# --- Lifecycle acts -----------------------------------------------------------

def test_exit(store: dict, aid: str, tested: str, why: str, on: str = "",
              by: str = "") -> dict:
    if not str(tested or "").strip():
        raise Refusal("--tested must say what was actually exercised, not that a test "
                      "happened. 'Ran the exit plan' records nothing a reviewer can check.")
    if not str(why or "").strip():
        raise Refusal("--why must give the rationale for the test that was run")
    rec = find_arrangement(store, aid)
    on = check_date(on, "--on") if on else utc_today()
    rec["exit"]["testedOn"] = on
    rec["exit"]["note"] = tested.strip()
    append_history(store, "exit-tested", aid, by, why=why, detail={"tested": tested.strip()})
    return rec["exit"]


def document_exit(store: dict, aid: str, note: str, on: str = "", by: str = "") -> dict:
    if not str(note or "").strip():
        raise Refusal("--note must describe the documented exit strategy")
    rec = find_arrangement(store, aid)
    rec["exit"]["documentedOn"] = check_date(on, "--on") if on else utc_today()
    if not rec["exit"].get("note"):
        rec["exit"]["note"] = note.strip()
    append_history(store, "exit-documented", aid, by, why=note.strip())
    return rec["exit"]


def review_requirements(store: dict, aid: str, requirement: str, evidence: str,
                        met: bool = True, by: str = "") -> dict:
    """Record a contract provision checked directly against the executed agreement.

    A Layer B act, like `assess`: a person reads the signed document and says what it commits
    the provider to. It is NOT a way around the proposal boundary — it demands the same things
    `assess` does, a named person and a reference to what was actually read.

    `--by` became required in v0.40.0. It was optional when this act shipped in v0.39.0, which
    meant a requirement could be marked met with nobody's name against it — a hole in the
    "only a named person closes anything" claim that the assessment layer is built on. Found by
    `proposal-boundary.sh`'s static scan on its first run, which is the entire reason that scan
    reads the AST rather than trusting the two acts it was written for.
    """
    if not str(requirement or "").strip():
        raise Refusal("--requirement names the contract provision being checked")
    if not str(evidence or "").strip():
        raise Refusal(
            "--evidence must reference what was actually read.\n"
            "  A requirement marked met with no evidence reference is an assertion about "
            "an agreement nobody opened, and it reads identically to one that was checked.")
    if not str(by or "").strip():
        raise Refusal(
            "--by is required: the person who read the agreement.\n"
            "  Marking a requirement met is closing it, and only a named person closes "
            "anything here. An unattributed tick cannot be defended by pointing at the tool "
            "that recorded it.")
    rec = find_arrangement(store, aid)
    entry = {"requirement": requirement.strip(), "evidence": evidence.strip(),
             "met": bool(met), "checkedOn": utc_today(), "checkedBy": str(by or "").strip()}
    rec["requirements"].append(entry)
    append_history(store, "requirement-reviewed", aid, by, why=requirement.strip())
    return entry


def record_subprocessor(store: dict, aid: str, name: str, effective: str,
                        note: str = "", by: str = "") -> dict:
    if not str(name or "").strip():
        raise Refusal("--name identifies the subprocessor")
    if not str(effective or "").strip():
        raise Refusal(
            "--effective must give the date the change takes effect.\n"
            "  Without it the chain cannot be read as at a date, and 'has subprocessors' "
            "says nothing about what was true when the last assessment was done.")
    rec = find_arrangement(store, aid)
    entry = {"name": name.strip(), "effective": check_date(effective, "--effective"),
             "note": str(note or "").strip(), "recordedOn": utc_today()}
    rec["subcontractors"].append(entry)
    append_history(store, "subprocessor-recorded", aid, by, why=name.strip(),
                   detail={"effective": entry["effective"]})
    return entry


def retire(store: dict, aid: str, data_went: str, deletion_confirmed: str,
           why: str = "", by: str = "") -> dict:
    """End an arrangement. TERMINAL.

    There is no un-retire. A resumed relationship opens a NEW arrangement carrying
    `priorArrangementRef`, because the closed exit and deletion record is the evidence that
    `GV.SC-10` was satisfied at the time — reopening it would rewrite an answer somebody
    already gave about data that has already gone.
    """
    if not str(data_went or "").strip():
        raise Refusal("--data-went must say where the data went on exit (GV.SC-10, SR-12)")
    if not str(deletion_confirmed or "").strip():
        raise Refusal(
            "--deletion-confirmed must give the date deletion was confirmed.\n"
            "  Not the date it was requested. The gap between the two is the exposure, and "
            "an arrangement closed on a request is closed on a promise.")
    rec = find_arrangement(store, aid)
    if rec.get("retired"):
        raise Refusal(
            f"{aid} is already retired (on {rec['retired'].get('on')}). Retirement is "
            f"terminal: a resumed relationship opens a new arrangement carrying "
            f"--prior {aid}, so the closed deletion record stays closed.")
    rec["retired"] = {"on": utc_today(),
                      "dataWent": data_went.strip(),
                      "deletionConfirmedOn": check_date(deletion_confirmed,
                                                        "--deletion-confirmed"),
                      "why": str(why or "").strip(), "by": str(by or "").strip()}
    append_history(store, "retired", aid, by, why=why or data_went.strip())
    return rec["retired"]


def set_prior(store: dict, aid: str, prior_ref: str) -> str:
    """Point a new arrangement at the retired one it succeeds.

    Refuses a reference to a LIVE arrangement: a successor to something still running is not
    a successor, it is a second arrangement, and the register should show two.
    """
    rec = find_arrangement(store, aid)
    prior = find_arrangement(store, prior_ref)
    if not prior.get("retired"):
        raise Refusal(
            f"{prior_ref} is still live, so {aid} cannot succeed it. Two arrangements "
            f"running at once are two arrangements — the register should show both.")
    if prior_ref == aid:
        raise Refusal("an arrangement cannot succeed itself")
    rec["priorArrangementRef"] = prior_ref
    append_history(store, "successor-linked", aid, why=prior_ref)
    return prior_ref


# --- Snapshots ----------------------------------------------------------------

def review(store: dict, label: str, why: str) -> dict:
    """Freeze the settings and every criticality block, so 'what did we think then' survives.

    The scale is frozen with them. A level read a year later means nothing without the scale
    it was assigned under.
    """
    if not str(label or "").strip():
        raise Refusal("--label names this review, so a later reader can find it")
    if not str(why or "").strip():
        raise Refusal("--why records what this review was for")
    snap = {
        "label": label.strip(),
        "why": why.strip(),
        "ts": now_ts(),
        "settings": json.loads(json.dumps(store["settings"])),
        "arrangements": [
            {"id": r["id"], "criticality": json.loads(json.dumps(r.get("criticality")))}
            for r in store["arrangements"]
        ],
    }
    store["snapshots"].append(snap)
    append_history(store, "reviewed", "register", why=why.strip(),
                   detail={"label": label.strip()})
    return snap


# --- Escalations (CAC-EL-1 §1.3) ----------------------------------------------
#
# `subjectKind` is `arrangement`. Derived on every run, never stored, and nothing here
# blocks: a register full of escalations still loads, still classifies, still renders.

ESCALATION_SEVERITY_ORDER = ["critical", "high", "medium"]


def _cadence_days(store: dict, level: str):
    """None means no cadence for this level — which is a decision, not an oversight.

    `low` has no interval by design. The triggers below fire at every level regardless, and
    they are what catch the low-criticality arrangement that quietly stopped being low.
    """
    return (store["settings"].get("cadenceDays") or {}).get(level)


def _last_assessed(rec: dict) -> str:
    dates = [str(a.get("on") or "") for a in (rec.get("assessments") or []) if a.get("on")]
    return max(dates) if dates else ""


def escalations(store: dict, today: str = "") -> list:
    today = today or utc_today()
    out = []

    def add(trigger, rec, severity, since, evidence):
        out.append({"trigger": trigger, "subjectKind": "arrangement",
                    "subjectRef": rec["id"], "severity": severity,
                    "since": since or today, "evidence": evidence})

    for rec in store["arrangements"]:
        if rec.get("retired"):
            continue
        block = rec.get("criticality") or {}
        level = criticality_of(rec)
        conf = block.get("confirmed") or {}

        if level == UNCLASSIFIED:
            add("unclassified", rec, "high", "",
                "no criticality has been derived or assigned, so this arrangement is "
                "asked the full question set and nobody has been told")
            continue

        if level == UNTRACED:
            add("untraced", rec, "high", block.get("derivedOn") or "",
                "the trace could not reach a workflow with a declared criticality%s. "
                "This is not low criticality; it is an unanswered question about what "
                "this arrangement holds up"
                % (" and stopped with more chain to follow"
                   if block.get("truncated") else ""))

        if block.get("derived") and not conf.get("value"):
            add("criticality-unreconciled", rec, "medium", block.get("derivedOn") or "",
                "a level was derived (%s) and nobody has assigned the final one"
                % block["derived"])
        elif conf.get("value") and block.get("derived") not in (None, "") \
                and conf.get("againstDerived") not in (None, "") \
                and block.get("derived") != conf.get("againstDerived"):
            add("criticality-unreconciled", rec, "medium", block.get("derivedOn") or "",
                "the supported workflow now derives %s, and the confirmed level was "
                "assigned against %s" % (block.get("derived"), conf.get("againstDerived")))

        if conf.get("value") and block.get("derived") not in (None, "", UNTRACED) \
                and conf["value"] != block["derived"]:
            add("criticality-conflict", rec, "medium", conf.get("on") or "",
                "derived %s, assigned %s by %s. Process E exists for consistency across "
                "layers, so a disagreement is a finding rather than an error"
                % (block["derived"], conf["value"], conf.get("by") or "someone"))

        # Cadence. `untraced` satisfies NO cadence rule — there is no level to look one up
        # for, and treating it as "no cadence applies" would make it quieter than `low`.
        if level == UNTRACED:
            pass
        else:
            cadence = _cadence_days(store, level)
            last = _last_assessed(rec)
            if cadence:
                since = last or str(rec.get("startsOn") or "")
                if since and days_between(since, today) > int(cadence):
                    add("assessment-overdue", rec, "high", since,
                        "last assessed %s; cadence for %s is %d days"
                        % (last or "never (dated from the start of the arrangement)",
                           level, int(cadence)))

        # Exit strategy: documented and tested are different facts.
        if level not in (UNTRACED,) and level in store["settings"]["criticalityScale"]:
            top = store["settings"]["criticalityScale"][-1]
            if level == top:
                tested = rec.get("exit", {}).get("testedOn") or ""
                stale = int(store["settings"].get("exitTestStaleDays") or 730)
                if not tested:
                    add("exit-untested", rec, "high",
                        rec.get("exit", {}).get("documentedOn") or "",
                        "a %s arrangement whose exit strategy has never been exercised. "
                        "Documented and tested are separate facts, and only one of them "
                        "is evidence" % level)
                elif days_between(tested, today) > stale:
                    add("exit-untested", rec, "medium", tested,
                        "exit last exercised %s, beyond the %d-day staleness window"
                        % (tested, stale))

        # Evidence that has expired and that a CONFIRMED requirement leans on. Not every
        # expired artifact: an old report nobody cited is clutter, while an old report
        # holding up a "satisfied" tick is a requirement that is no longer evidenced.
        grace = int(store["settings"].get("evidenceGraceDays") or 365)
        relied_on = {str(r.get("evidenceRef") or "")
                     for r in (rec.get("requirements") or []) if r.get("met")}
        for ev in (rec.get("evidence") or []):
            if ev.get("id") not in relied_on:
                continue
            if evidence_status(ev, today, grace) != "expired":
                continue
            top = store["settings"]["criticalityScale"][-1]
            add("evidence-expired", rec, "high" if level == top else "medium",
                ev.get("periodEnd") or "",
                "%s (%s) covers a requirement recorded as met, and its period ended %s — "
                "beyond the %d-day window. The tick is still there; the evidence behind it "
                "is not" % (ev.get("id"), ev.get("kind"), ev.get("periodEnd"), grace))

        # Proposals nobody has ruled on. A stack of these must never read as an assessment:
        # Layer A can produce them all day, and only Layer B closes anything.
        stale_days = int(store["settings"].get("proposalStaleDays") or 30)
        pending = [pr for pr in (rec.get("proposals") or [])
                   if pr.get("status") == "proposed"
                   and pr.get("proposedOn")
                   and days_between(pr["proposedOn"], today) > stale_days]
        if pending:
            add("unconfirmed-proposals", rec, "medium",
                min(pr["proposedOn"] for pr in pending),
                "%d proposal(s) have sat un-assessed for more than %d days. A proposal is a "
                "reading, not a finding — nothing here is satisfied until a named person "
                "confirms it" % (len(pending), stale_days))

        # Triggers fire at EVERY level, including the lowest. A subprocessor change on a
        # low-criticality arrangement is exactly the event that makes it stop being low,
        # and `low` has no cadence to catch it.
        last = _last_assessed(rec)
        for sub in (rec.get("subcontractors") or []):
            eff = str(sub.get("effective") or "")
            if eff and (not last or eff > last):
                add("supplier-changed", rec, "medium", eff,
                    "subprocessor %r effective %s, after the last assessment (%s)"
                    % (sub.get("name"), eff, last or "none recorded"))
                break

    order = {s: i for i, s in enumerate(ESCALATION_SEVERITY_ORDER)}
    out.sort(key=lambda e: (order.get(e["severity"], 99), e["subjectRef"], e["trigger"]))
    return out


# --- Context ------------------------------------------------------------------

def load_context(path: str) -> dict:
    """Read a CAC-AP-1 payload exported by `business-context`.

    Data, never an import (§2.6). A raw `.biz` is refused with the command that turns one
    into a payload, because reading the store directly would put the narrowing decision in
    the wrong skill.
    """
    try:
        with open(path, encoding="utf-8") as fh:
            payload = json.load(fh)
    except FileNotFoundError:
        raise Refusal(f"no such context payload: {path}")
    except json.JSONDecodeError as exc:
        raise Refusal(f"{path} is not valid JSON: {exc.msg}")
    if payload.get("family") == "business-context":
        raise Refusal(
            f"{path} is a raw .biz store, not an exported payload. Run "
            f"`business_context.py export {path} --out ctx.json` and pass that: the "
            f"narrowing decision belongs to that skill, and CAC-AP-1 §2.6 makes the "
            f"transport data rather than an import.")
    if payload.get("contractVersion") not in (None, "", "CAC-AP-1"):
        raise Refusal(f"{path} declares contract {payload.get('contractVersion')!r}, "
                      f"which this engine does not read")
    return payload


# --- Register of Information --------------------------------------------------

ROI_REQUIRED = (
    ("vendorName", "the legal name of the provider"),
    ("entityRef", "the legal entity holding the arrangement"),
    ("services", "what the provider actually does"),
    ("criticality", "a criticality that a person has confirmed"),
    ("supports", "the function or system this arrangement supports"),
    ("owner", "the person accountable for the arrangement"),
)


def export_roi(store: dict, context: dict = None, today: str = "") -> dict:
    """A CAC-shaped register export, field names chosen so mapping to a filing template is
    mechanical.

    **It refuses to look complete when it is not.** An arrangement missing an identifier, a
    confirmed criticality or a supported function is reported as a NAMED GAP rather than
    emitted as a blank cell. A register that files cleanly and is wrong is worse than one that
    refuses: the blank cell is indistinguishable from a legitimately empty one, and the filing
    carries the organisation's name on it.

    Gated on a DECLARED profile flag. This exports a register in a documented shape; it does
    not tell anybody what a regulation requires, and the overlay that would is not shipped —
    see `references/overlays.md`.
    """
    today = today or utc_today()
    profile = ((context or {}).get("profile") or {})
    entry = profile.get("doraScope")
    scoped = entry.get("value") if isinstance(entry, dict) else entry
    if scoped is not True:
        raise Refusal(
            "this export is gated on a declared `doraScope` in the applicability profile, and "
            "the profile %s.\n"
            "  Absence is not a 'no' — it means nobody has declared it. Declare the flag in "
            "`business-context` and pass the exported payload with --context.\n"
            "  The export produces a register in a documented shape. It does not assert what "
            "any regulation requires of you: the regime overlay that would carry those "
            "obligations is not shipped, pending a primary-source pass."
            % ("declares it false" if scoped is False else "does not declare one"))
    rows, gaps = [], []
    for rec in store["arrangements"]:
        if rec.get("retired"):
            continue
        vendor = next((v for v in store["vendors"]
                       if v.get("id") == rec.get("vendorRef")), {})
        conf = ((rec.get("criticality") or {}).get("confirmed") or {})
        row = {
            "arrangementRef": rec["id"],
            "vendorName": vendor.get("name") or "",
            "vendorJurisdiction": vendor.get("jurisdiction") or "",
            "vendorGroupParent": vendor.get("groupParent") or "",
            "entityRef": rec.get("entityRef") or "",
            "services": rec.get("services") or "",
            "supports": rec.get("supports") or "",
            "owner": rec.get("owner") or "",
            # The CONFIRMED level only. A derived one is a proposal, and filing a proposal as
            # though a person had assigned it is the whole failure this skill refuses.
            "criticality": conf.get("value") or "",
            "criticalityScaleVersion": conf.get("scaleVersion") or "",
            "criticalityConfirmedBy": conf.get("by") or "",
            "startsOn": rec.get("startsOn") or "",
            "endsOn": rec.get("endsOn") or "",
            "subprocessorCount": len(rec.get("subcontractors") or []),
            "exitDocumentedOn": (rec.get("exit") or {}).get("documentedOn") or "",
            "exitTestedOn": (rec.get("exit") or {}).get("testedOn") or "",
        }
        missing = [(field, why) for field, why in ROI_REQUIRED if not str(row.get(field) or "")]
        if missing:
            gaps.append({
                "arrangementRef": rec["id"],
                "missing": [f for f, _ in missing],
                "detail": "; ".join("%s — %s" % (f, why) for f, why in missing),
            })
        rows.append(row)
    return {
        "family": FAMILY,
        "export": "register-of-information",
        "shape": "CAC",
        "asOf": today,
        "organisation": store["meta"].get("orgName") or "",
        "rows": rows,
        "gaps": gaps,
        "complete": not gaps,
        "note": ("This is a CAC-shaped export. Field names are chosen so mapping to a filing "
                 "template is mechanical; it is not a filing, and it asserts no regulatory "
                 "obligation."),
    }


# --- The findings bridge (GV.SC-03, SR-2) -------------------------------------
#
# C-SCRM integrated into enterprise risk, implemented as a ONE-WAY export. This skill never
# scores: findings go to `risk-register` and are scored once, there, under L×I with an appetite
# to judge them against.
#
# **A finding is a requirement a named person recorded as NOT met.** That is a deliberate
# narrowing, and it is the decision worth arguing with:
#
#   - It is a CHECKED fact. Somebody read the agreement or the report, said the provision is
#     absent, and their name and the date are on it. That is what becomes a defensible
#     candidate risk.
#   - Escalations are NOT exported, even though several of them describe real exposure. They
#     are derived and stateless — recomputed on every run — so exporting them would mint a new
#     candidate risk every time the clock moved, and `board-pack` already aggregates them as
#     escalations. One exposure in two systems of record is how the two disagree.
#
# What the payload deliberately does NOT carry: likelihood, impact, or any score. SP 800-161r1's
# assessment template ends in a likelihood and a risk-exposure determination, and this stops
# exactly there. `no-vendor-score.sh` and `evals/proposal-boundary.sh` both hold that line;
# so does the self-test, by asserting the payload has no scoring key at all.

FINDING_SCORING_KEYS = ("likelihood", "impact", "score", "severity", "rating", "band",
                        "exposure", "priority")
"""Keys the payload must never contain. Asserted rather than remembered.

Naming them here rather than checking for a vague 'number' means the assertion can be exact,
and means a reader can see precisely which words this bridge refuses to put in a risk's mouth.
"""


def export_findings(store: dict, today: str = "") -> dict:
    """Requirements recorded as not met, in the `risk-register` import shape.

    Idempotent on `sourceRef`: re-running updates the candidate it created rather than adding
    a second one. The key is the arrangement plus the requirement, because one arrangement can
    fail several provisions and each is its own candidate.
    """
    today = today or utc_today()
    rows = []
    for rec in store["arrangements"]:
        if rec.get("retired"):
            continue
        vendor = next((v for v in store["vendors"]
                       if v.get("id") == rec.get("vendorRef")), {})
        conf = ((rec.get("criticality") or {}).get("confirmed") or {})
        for req in (rec.get("requirements") or []):
            if req.get("met"):
                continue
            if not str(req.get("checkedBy") or "").strip():
                # Not a finding: nobody is recorded as having looked. Exporting it would put
                # an unattributed claim into a register whose whole discipline is refusing one.
                continue
            rows.append({
                "sourceRef": "%s:%s:%s" % (FAMILY, rec["id"],
                                           str(req.get("requirement") or "")),
                "sourceArrangementRef": rec["id"],
                "title": "%s: %s not evidenced" % (vendor.get("name") or rec["id"],
                                                   req.get("requirement")),
                "description": ("Third-party arrangement %s with %s — %r was checked and "
                                "recorded as not met."
                                % (rec["id"], vendor.get("name") or "the provider",
                                   req.get("requirement"))),
                "vendor": vendor.get("name") or "",
                "services": rec.get("services") or "",
                "owner": rec.get("owner") or "",
                # The criticality AND the scale it was assigned under. A level read a year
                # later means nothing without it, and the importing register has its own
                # scale for other things.
                "criticality": conf.get("value") or criticality_of(rec),
                "criticalityScaleVersion": conf.get("scaleVersion") or "",
                "criticalityConfirmed": bool(conf.get("value")),
                "evidenceRef": req.get("evidenceRef") or "",
                "checkedBy": req.get("checkedBy") or "",
                "checkedOn": req.get("checkedOn") or "",
                "gvsc": list(rec.get("gvsc") or []),
                "sr": list(rec.get("sr") or []),
            })
    return {
        "family": FAMILY,
        "export": "findings",
        "asOf": today,
        "organisation": store["meta"].get("orgName") or "",
        "findings": rows,
        "note": ("Candidate risks. This register does not score: no likelihood, no impact, no "
                 "band. risk-register scores them once, under SP 800-30, against an appetite."),
    }


# --- Multi-entity ------------------------------------------------------------

def organisations(store: dict) -> list:
    seen = []
    for rec in store["arrangements"]:
        name = str(rec.get("entityRef") or "").strip()
        if name and name not in seen:
            seen.append(name)
    return sorted(seen)


def check_one_organisation(store: dict) -> dict:
    """Refuse to render a register spanning legal entities as a single-org view.

    Same shape and same reasoning as `assemble_pack.py`'s consolidation check: a view built
    from more than one entity can be true about every row and wrong as a document, because
    the reader takes the whole thing to be about one company. An attributed `consolidation`
    declaration lets it through and is printed on the surface, so a consolidated view never
    looks single-entity.
    """
    names = organisations(store)
    consolidation = (store.get("settings") or {}).get("consolidation") or {}
    if len(names) <= 1:
        return {"organisation": names[0] if names else "", "consolidated": None}
    by = str(consolidation.get("declaredBy") or "").strip()
    basis = str(consolidation.get("basis") or "").strip()
    if not by or not basis:
        raise Refusal(
            "this register holds arrangements for %d legal entities (%s) and no "
            "consolidation is declared.\n"
            "  A single-organisation view built from several entities is true about every "
            "row and wrong as a document — the reader takes it to be about one company. "
            "Declare it: settings.consolidation = {\"declaredBy\": \"...\", \"basis\": "
            "\"...\"}. A consolidation with no basis is refused too, because the basis is "
            "the part a reviewer actually needs."
            % (len(names), ", ".join(names)))
    return {"organisation": ", ".join(names),
            "consolidated": {"declaredBy": by, "basis": basis, "entities": names}}


# --- Analysis -----------------------------------------------------------------

def analyze(store: dict, today: str = "", context: dict = None) -> dict:
    """Everything a surface needs, computed once. No score is produced here or anywhere.

    Counts are counts of things that exist. There is deliberately no aggregate: a register
    with three critical arrangements and one untraced one has three critical arrangements
    and one untraced one, and any single number standing for that is an opinion the tool is
    not entitled to.
    """
    today = today or utc_today()
    entity = check_one_organisation(store)
    scale = store["settings"]["criticalityScale"]
    grace = int(store["settings"].get("evidenceGraceDays") or 365)

    live = [r for r in store["arrangements"] if not r.get("retired")]
    by_level = {}
    for rec in live:
        by_level.setdefault(criticality_of(rec), []).append(rec["id"])

    rows = []
    for rec in sorted(store["arrangements"], key=lambda r: r["id"]):
        block = rec.get("criticality") or {}
        conf = block.get("confirmed") or {}
        vendor = next((v for v in store["vendors"]
                       if v.get("id") == rec.get("vendorRef")), {})
        rows.append({
            "id": rec["id"],
            "vendor": vendor.get("name") or rec.get("vendorRef") or "",
            "entityRef": rec.get("entityRef") or "",
            "services": rec.get("services") or "",
            "supports": rec.get("supports") or "",
            "owner": rec.get("owner") or "",
            "criticality": criticality_of(rec),
            "derived": block.get("derived") or "",
            "confirmedBy": conf.get("by") or "",
            "scaleVersion": conf.get("scaleVersion") or "",
            "trace": block.get("trace") or [],
            "truncated": bool(block.get("truncated")),
            "exitDocumentedOn": (rec.get("exit") or {}).get("documentedOn") or "",
            "exitTestedOn": (rec.get("exit") or {}).get("testedOn") or "",
            "lastAssessed": _last_assessed(rec),
            "subcontractors": len(rec.get("subcontractors") or []),
            "retired": bool(rec.get("retired")),
            "priorArrangementRef": rec.get("priorArrangementRef") or "",
        })
        # The assessment layer, per arrangement. Counts, never a rating: how many questions
        # are open is a fact about the work left, and turning it into a severity would be the
        # vendor score arriving through a side door.
        if not rec.get("retired"):
            asked = ask(store, rec["id"], context, today=today)
            rows[-1]["openQuestions"] = asked["open"]
            rows[-1]["reConfirmQuestions"] = asked["reConfirm"]
            rows[-1]["skippedBatteries"] = len(asked["skipped"])
            rows[-1]["openProposals"] = len(open_proposals(rec))
            by_status = {}
            for ev in (rec.get("evidence") or []):
                st = evidence_status(ev, today, grace)
                by_status[st] = by_status.get(st, 0) + 1
            rows[-1]["evidence"] = {"total": len(rec.get("evidence") or []),
                                    "byStatus": by_status}

    esc = escalations(store, today)
    out = {
        "family": FAMILY,
        "asOf": today,
        "organisation": entity["organisation"],
        "scale": list(scale),
        "scaleVersion": store["settings"].get("scaleVersion") or "",
        "counts": {
            "vendors": len(store["vendors"]),
            "arrangements": len(store["arrangements"]),
            "live": len(live),
            "retired": len(store["arrangements"]) - len(live),
            "byCriticality": {k: len(v) for k, v in sorted(by_level.items())},
        },
        "arrangements": rows,
        "openQuestions": sum(r.get("openQuestions", 0) for r in rows),
        "reConfirmQuestions": sum(r.get("reConfirmQuestions", 0) for r in rows),
        "openProposals": sum(r.get("openProposals", 0) for r in rows),
        "escalations": esc,
        "notes": [],
    }
    if entity["consolidated"]:
        out["consolidation"] = entity["consolidated"]
        out["notes"].append(
            "this view consolidates %d legal entities (%s), declared by %s: %s"
            % (len(entity["consolidated"]["entities"]),
               ", ".join(entity["consolidated"]["entities"]),
               entity["consolidated"]["declaredBy"], entity["consolidated"]["basis"]))
    if context is None:
        out["notes"].append(
            "no applicability profile was supplied, so every criticality that has not been "
            "assigned by hand is 'untraced' — the walk had no workflows to reach. This is "
            "the safe direction and never a refusal.")
    return out


# --- Self-test ----------------------------------------------------------------

def _cmd_self_test(_args):
    import shutil
    import tempfile as _tf
    checks = [0]
    fails = []

    def ok(cond, label):
        checks[0] += 1
        if not cond:
            fails.append(label)

    def eq(actual, expected, label):
        checks[0] += 1
        if actual != expected:
            fails.append("%s: expected %r, got %r" % (label, expected, actual))

    def at(seq, index, key, default="<missing>"):
        """Read seq[index][key] without ever raising.

        Written after the third mutation test in this file was caught by an IndexError or a
        KeyError rather than by a named check. A crash inside the self-test aborts the run and
        throws away the summary, so a broken guard reads as a silent pass in exactly the
        situation the guard exists for.
        """
        try:
            return seq[index][key]
        except (IndexError, KeyError, TypeError):
            return default

    def refuses(fn, label, needle=""):
        checks[0] += 1
        try:
            fn()
        except Refusal as exc:
            if needle and needle not in str(exc):
                fails.append("%s: refused, but not for the stated reason: %s" % (label, exc))
            return
        fails.append("%s: did not refuse" % label)

    work = _tf.mkdtemp()
    try:
        path = os.path.join(work, "t.vnd")

        # --- T1: round trip -------------------------------------------------
        store = new_store("Acme Manufacturing", "R. Calder")
        save(path, store)
        loaded = load(path)
        eq(loaded["meta"]["orgName"], "Acme Manufacturing", "a store round-trips")
        eq(loaded["settings"]["criticalityScale"], DEFAULT_SCALE,
           "and ships the default scale")
        eq(loaded["arrangements"], [], "with nothing in it yet")
        # Defaults merge PER KEY: a store written before a setting existed gains it rather
        # than losing every setting it did have.
        thin = json.loads(open(path, encoding="utf-8").read())
        thin["settings"] = {"exitTestStaleDays": 90}
        open(path, "w", encoding="utf-8").write(json.dumps(thin))
        merged = load(path)
        eq(merged["settings"]["exitTestStaleDays"], 90, "a stored setting survives the merge")
        eq(merged["settings"]["criticalityScale"], DEFAULT_SCALE,
           "and the settings it never had are filled in, not dropped")
        save(path, store)

        wrong = os.path.join(work, "w.rr")
        open(wrong, "w", encoding="utf-8").write('{"family": "risk-register"}')
        refuses(lambda: load(wrong), "another skill's store is refused", "not a vendor register")

        # --- T2: the two object types --------------------------------------
        before = open(path, "rb").read()
        refuses(lambda: add_arrangement(store, "V-999", "hosting", "CTO"),
                "an arrangement on an unknown vendor is refused", "no vendor")
        v = add_vendor(store, "Contoso Cloud", jurisdiction="IE")
        eq(v["id"], "V-001", "vendors are numbered from one")
        refuses(lambda: add_arrangement(store, "V-001", "hosting", ""),
                "an arrangement with no owner is refused", "GV.SC-02")
        refuses(lambda: add_arrangement(store, "V-001", "", "CTO"),
                "and one with no services is refused")
        eq(open(path, "rb").read(), before, "and no refusal touched the file")

        a1 = add_arrangement(store, "V-001", "production hosting", "CTO",
                             supports="Plant historian (Dublin)")
        eq(a1["id"], "VA-001", "arrangements are numbered from one")
        eq(a1["entityRef"], "Acme Manufacturing",
           "entityRef defaults to the org, present from the first commit")
        eq(a1["exit"], {"documentedOn": "", "testedOn": "", "note": ""},
           "documented and tested are separate fields, both empty to start")

        # --- T3: provenance -------------------------------------------------
        wrapped = declared("high", "R. Calder", "FY26 review")
        eq(value_of(wrapped), "high", "a wrapped value reads through")
        ok(is_attributed(wrapped), "and is attributed")
        eq(value_of("high"), "high", "a bare value loads rather than being refused")
        ok(not is_attributed("high"),
           "and is reported as unattributed — a register that rejects a hand-edited file "
           "is one people stop using")
        ok(any(h["event"] == "arrangement-added" for h in store["history"]),
           "every mutation appends to history")

        # --- T4: the scale is a setting -------------------------------------
        refuses(lambda: set_scale(store, ["only-one"]), "a one-level scale is refused")
        refuses(lambda: set_scale(store, ["low", "untraced"]),
                "untraced can never be a scale member", "states, not levels")
        refuses(lambda: set_scale(store, ["low", "low", "high"]),
                "a scale cannot repeat a level")
        ctx = {"crownJewels": [
            {"system": "Plant historian (Dublin)", "criticality": "high",
             "dependsOn": ["SCADA gateway"]},
            {"system": "CRM", "criticality": "moderate"},
        ]}
        classify(store, "VA-001", ctx, confirm="high", by="R. Calder")
        eq(store["arrangements"][0]["criticality"]["confirmed"]["scaleVersion"], "v1",
           "a confirmed level records the scale version it was assigned under")
        refuses(lambda: set_scale(store, ["minor", "major"]),
                "a scale change that would orphan a confirmed level is refused",
                "orphan")
        eq(store["settings"]["criticalityScale"], DEFAULT_SCALE,
           "and the scale is unchanged after that refusal")
        # Changing the scale does NOT remap what was already assigned, and the stored value
        # still reports the version it was assigned under.
        set_scale(store, ["low", "moderate", "high", "critical"], version="v2")
        eq(store["arrangements"][0]["criticality"]["confirmed"]["scaleVersion"], "v1",
           "an existing value still reports its ORIGINAL scale version after a change")
        set_scale(store, DEFAULT_SCALE, version="v1")

        # --- T5: untraced is a value, not a gap -----------------------------
        lonely = add_arrangement(store, "V-001", "marketing sandbox", "CMO")
        lvl, trace, trunc = derive_criticality(lonely, ctx)
        eq(lvl, UNTRACED, "an arrangement supporting nothing derives untraced, NOT low")
        ok(lvl != "low", "and specifically is not the bottom of the scale")
        eq(trace, [], "with an empty trace")
        eq(trunc, False, "and nothing truncated, because there was no chain at all")
        refuses(lambda: criticality_rank(store, UNTRACED),
                "ordering a list containing untraced RAISES rather than placing it",
                "state, not a level")
        eq(criticality_rank(store, "low"), 0, "while a real level ranks normally")
        eq(criticality_rank(store, "high"), 2, "at its position on the scale")
        refuses(lambda: criticality_rank(store, UNCLASSIFIED),
                "and unclassified is refused an ordering too")

        # --- T6: the trace ---------------------------------------------------
        direct = {"supports": "Plant historian (Dublin)"}
        eq(derive_criticality(direct, ctx), ("high", ["Plant historian (Dublin)"], False),
           "direct support of a crown jewel: its criticality, one hop, not truncated")
        via = {"supports": "SCADA gateway"}
        eq(derive_criticality(via, ctx),
           ("high", ["SCADA gateway", "Plant historian (Dublin)"], False),
           "support via one intermediate: same criticality, two hops, not truncated")
        # Three hops. The load-bearing case: it must return untraced AND truncated, never a
        # confident level from an unfinished walk.
        deep = {"crownJewels": [
            {"system": "Top", "criticality": "high", "dependsOn": ["Middle"]},
            {"system": "Middle", "dependsOn": ["Bottom"]},
        ]}
        lvl3, path3, trunc3 = derive_criticality({"supports": "Bottom"}, deep)
        eq(lvl3, UNTRACED, "a three-hop chain does not return a confident level")
        eq(trunc3, True, "and says it was truncated, so the two are never confused")
        eq(path3, ["Bottom", "Middle"], "recording how far it did get")
        eq(derive_criticality({"supports": "Plant historian (Dublin)"}, {}),
           (UNTRACED, ["Plant historian (Dublin)"], False),
           "no context at all: untraced for everything, and never a refusal")
        cyclic = {"crownJewels": [
            {"system": "A", "dependsOn": ["B"]},
            {"system": "B", "dependsOn": ["A"]},
        ]}
        lvlc, _, _ = derive_criticality({"supports": "A"}, cyclic, max_hops=99)
        eq(lvlc, UNTRACED, "a cycle terminates rather than spinning")

        # A container where a level belongs. `str({...})` is truthy and non-empty, so the
        # inline read this replaced returned the repr AS the level. `check-twins` proves this
        # walk and ai-register's agree; agreement is not correctness, and two copies can agree
        # on a repr. These pin what the right answer IS on this side.
        for shape in ({"value": "high", "basis": "board said so"}, ["high"], ("high",)):
            refuses(lambda s=shape: derive_criticality(
                {"supports": "Plant historian (Dublin)"},
                {"crownJewels": [{"system": "Plant historian (Dublin)",
                                  "criticality": s}]}),
                    "a %s criticality is refused, not stringified into a level"
                    % type(shape).__name__, "not a level")
        eq(derive_criticality({"supports": "Plant historian (Dublin)"},
                              {"crownJewels": [{"system": "Plant historian (Dublin)",
                                                "criticality": "   "}]}),
           (UNTRACED, ["Plant historian (Dublin)"], False),
           "...but a blank criticality declares nothing and is not a refusal")

        # --- T7: derive proposes, a person confirms -------------------------
        before = open(path, "rb").read()
        save(path, store)
        before = open(path, "rb").read()
        refuses(lambda: classify(store, "VA-002", ctx, confirm="low"),
                "--confirm with no --by is refused", "8179 E.5")
        refuses(lambda: classify(store, "VA-002", ctx, confirm="enormous", by="D"),
                "a level not on the scale is refused")
        refuses(lambda: classify(store, "VA-002", ctx, layer="galaxy"),
                "an unknown --layer is refused")
        eq(open(path, "rb").read(), before, "and none of those touched the file")
        block = classify(store, "VA-002", ctx)
        eq(block["derived"], UNTRACED, "classify without --confirm derives only")
        eq(block["confirmed"], None, "and assigns nothing")
        # A confirmed level MAY differ from the derived one. That is a finding, not an error.
        conflict = classify(store, "VA-002", ctx, confirm="moderate", by="R. Calder",
                            basis="it fronts the customer portal")
        eq(conflict["confirmed"]["value"], "moderate",
           "a confirmed level differing from the derived one is stored without complaint")
        eq(criticality_of(store["arrangements"][1]), "moderate",
           "and is what the register acts on")

        # --- T8: the acts and their refusals --------------------------------
        save(path, store)
        before = open(path, "rb").read()
        refuses(lambda: test_exit(store, "VA-001", "", "why"),
                "test-exit with nothing tested is refused", "what was actually exercised")
        refuses(lambda: test_exit(store, "VA-001", "failed over to the DR region", ""),
                "and with no rationale")
        refuses(lambda: review_requirements(store, "VA-001", "breach notice", ""),
                "review-requirements with no evidence reference is refused", "nobody opened")
        refuses(lambda: record_subprocessor(store, "VA-001", "Fabrikam", ""),
                "record-subprocessor with no effective date is refused", "as at a date")
        # Closing a requirement needs a name here exactly as it does in `assess`. This act
        # shipped in v0.39.0 without one, so a tick could carry nobody's judgement.
        refuses(lambda: review_requirements(store, "VA-001", "breach notice",
                                            "MSA schedule 3"),
                "review-requirements with no named person is refused", "only a named person")
        refuses(lambda: retire(store, "VA-001", "", "2026-06-01"),
                "retire with no data destination is refused", "GV.SC-10")
        refuses(lambda: retire(store, "VA-001", "returned to us on encrypted media", ""),
                "retire with no confirmed deletion date is refused", "closed on a promise")
        eq(open(path, "rb").read(), before, "and no act's refusal touched the file")

        test_exit(store, "VA-001", "failed over to the DR region for 4h", "annual DR test",
                  on="2026-05-01")
        eq(store["arrangements"][0]["exit"]["testedOn"], "2026-05-01",
           "a tested exit records its own date, separate from the documented one")
        eq(store["arrangements"][0]["exit"]["documentedOn"], "",
           "and testing does not backfill a documented date it never had")

        retire(store, "VA-002", "returned on encrypted media, then purged",
               "2026-06-01", why="service consolidated")
        refuses(lambda: retire(store, "VA-002", "again", "2026-06-02"),
                "retiring twice is refused — retirement is terminal", "terminal")
        refuses(lambda: classify(store, "VA-002", ctx),
                "and a retired arrangement is not re-classified")
        successor = add_arrangement(store, "V-001", "replacement portal", "CTO")
        eq(set_prior(store, successor["id"], "VA-002"), "VA-002",
           "a new arrangement may succeed a retired one")
        refuses(lambda: set_prior(store, successor["id"], "VA-001"),
                "but not a live one — two running at once are two arrangements", "still live")

        # --- T9: snapshots freeze scale and criticality ----------------------
        refuses(lambda: review(store, "", "why"), "a review needs a label")
        refuses(lambda: review(store, "Q3", ""), "and a reason")
        snap = review(store, "Q3 FY26", "quarterly third-party review")
        eq(snap["settings"]["criticalityScale"], DEFAULT_SCALE, "a snapshot freezes the scale")
        classify(store, "VA-001", ctx, confirm="low", by="R. Calder")
        frozen = next(a for a in store["snapshots"][-1]["arrangements"] if a["id"] == "VA-001")
        eq(frozen["criticality"]["confirmed"]["value"], "high",
           "and still reports the level in force then, after a re-classification")
        eq(frozen["criticality"]["confirmed"]["scaleVersion"], "v1",
           "with the scale version that level was assigned under")
        eq(criticality_of(store["arrangements"][0]), "low", "while the live record has moved")

        # --- T10: escalations -------------------------------------------------
        quiet = new_store("Quiet Ltd")
        add_vendor(quiet, "Steady Supply")
        q = add_arrangement(quiet, "V-001", "payroll", "CFO", supports="CRM",
                            starts_on=utc_today())
        classify(quiet, q["id"], ctx, confirm="moderate", by="CFO")
        quiet["arrangements"][0]["assessments"].append({"on": utc_today(), "by": "CFO"})
        eq(escalations(quiet, utc_today()), [],
           "an arrangement classified and assessed today escalates nothing")

        def _fixture(**kw):
            s = new_store("Fix Ltd")
            add_vendor(s, "Some Vendor")
            rec = add_arrangement(s, "V-001", "a service", "An Owner",
                                  supports=kw.pop("supports", ""),
                                  starts_on=kw.pop("starts_on", ""))
            return s, rec

        def _triggers(s, today=""):
            return sorted({e["trigger"] for e in escalations(s, today or utc_today())})

        s, _ = _fixture()
        ok("unclassified" in _triggers(s),
           "an arrangement nobody classified escalates `unclassified`")
        s, rec = _fixture(supports="Nowhere")
        classify(s, rec["id"], ctx)
        ok("untraced" in _triggers(s),
           "one the walk could not finish escalates `untraced`, separately")
        ok("unclassified" not in _triggers(s),
           "and the two are never the same trigger — nobody asked vs we could not answer")
        s, rec = _fixture(supports="CRM")
        classify(s, rec["id"], ctx)
        ok("criticality-unreconciled" in _triggers(s),
           "derived with nobody having assigned the final level escalates unreconciled")
        s, rec = _fixture(supports="CRM")
        classify(s, rec["id"], ctx, confirm="high", by="R. Calder")
        ok("criticality-conflict" in _triggers(s),
           "derived and confirmed disagreeing is a finding, not an error")
        s, rec = _fixture(supports="Plant historian (Dublin)", starts_on="2020-01-01")
        classify(s, rec["id"], ctx, confirm="high", by="R. Calder")
        trig = _triggers(s)
        ok("assessment-overdue" in trig, "beyond its cadence escalates overdue")
        ok("exit-untested" in trig,
           "and a top-criticality arrangement with an unexercised exit escalates that too")
        # THE trigger-at-every-level case. `low` has no cadence by design (D-14), so if
        # triggers did not fire at `low` the arrangement that quietly stopped being low
        # would be the one thing this register never mentions.
        s, rec = _fixture(supports="CRM", starts_on="2026-01-01")
        classify(s, rec["id"], ctx, confirm="low", by="R. Calder")
        s["arrangements"][0]["assessments"].append({"on": "2026-02-01", "by": "D"})
        record_subprocessor(s, rec["id"], "New Fourth Party", "2026-07-01")
        trig = _triggers(s, "2026-08-07")
        ok("supplier-changed" in trig,
           "a subprocessor change on a LOW arrangement still escalates, though low has "
           "no cadence at all")
        ok("assessment-overdue" not in trig,
           "and low genuinely has no cadence, so it is the trigger doing the work")
        # untraced must not be quieter than low: it satisfies no cadence rule.
        s, rec = _fixture(supports="Nowhere", starts_on="2020-01-01")
        classify(s, rec["id"], ctx)
        ok("untraced" in _triggers(s), "an untraced arrangement is never silent")

        # --- P2 T1: evidence and its tiers ------------------------------------
        ev_store = new_store("Evidence Ltd")
        add_vendor(ev_store, "Contoso Cloud")
        add_arrangement(ev_store, "V-001", "hosting", "CTO", supports="CRM")
        epath = os.path.join(work, "e.vnd")
        save(epath, ev_store)
        before = open(epath, "rb").read()
        refuses(lambda: ingest(ev_store, "VA-001", "soc2-type2", "T1", "auditor PDF"),
                "a T1 with no scope and no period is refused", "its scope and period")
        refuses(lambda: ingest(ev_store, "VA-001", "soc2-type2", "T1", "auditor PDF",
                               scope="the hosting platform"),
                "a T1 with a scope but no period is refused", "cannot expire")
        refuses(lambda: ingest(ev_store, "VA-001", "trust-page", "T4", "their website",
                               url="https://example.test/trust"),
                "a URL source with no retrieval date is refused", "may no longer say it")
        refuses(lambda: ingest(ev_store, "VA-001", "soc2-type2", "T5", "x"),
                "an unknown tier is refused")
        refuses(lambda: ingest(ev_store, "VA-001", "", "T3", "questionnaire"),
                "evidence with no --kind is refused")
        eq(open(epath, "rb").read(), before, "and no refusal touched the file")

        # T3 needs neither scope nor period, because it closes nothing anyway.
        t3 = ingest(ev_store, "VA-001", "questionnaire", "T3", "their completed CAIQ")
        eq(t3["id"], "EV-001", "evidence is numbered per arrangement")
        eq(t3["scope"], "", "a T3 needs no scope, because it can satisfy nothing")
        t1 = ingest(ev_store, "VA-001", "soc2-type2", "T1", "auditor PDF, filed 2026-02",
                    scope="the hosting platform, excluding the payments subservice",
                    period_start="2025-01-01", period_end="2025-12-31")
        eq(t1["id"], "EV-002", "and numbering continues")
        ok(t1["scope"] and t1["periodEnd"], "a T1 records both its scope and its period")

        # --- P2 T2: currency, and what does NOT extend it ---------------------
        eq(evidence_status(t1, "2025-06-01", 365), "current",
           "an artifact whose period has not closed is current")
        eq(evidence_status(t1, "2026-11-30", 365), "in-grace",
           "eleven months past the period end is in grace")
        eq(evidence_status(t1, "2027-02-01", 365), "expired",
           "thirteen months past it is expired")
        eq(evidence_status(t3, "2030-01-01", 365), "current",
           "a tier with no period never expires, because it closes nothing to begin with")
        # THE rule most likely to be "helpfully" relaxed later. A bridge letter is a
        # management assertion, and a management assertion is not an audited artifact.
        bridge = ingest(ev_store, "VA-001", "bridge-letter", "T3",
                        "management letter covering Jan-Jun 2026")
        eq(bridge["tier"], "T3", "a bridge letter is ingested as T3, not as an extension")
        eq(evidence_status(t1, "2027-02-01", 365), "expired",
           "and ingesting it leaves the expired T1 expired — a management assertion does "
           "not extend an audited artifact's currency")
        ok(bridge["tier"] not in SATISFYING_TIERS,
           "...because it is not a tier that can satisfy anything")

        # An expired artifact escalates only when something LEANS on it.
        ev_rec = ev_store["arrangements"][0]
        classify(ev_store, "VA-001", ctx, confirm="high", by="R. Calder")
        ev_rec["assessments"].append({"on": "2027-01-15", "by": "D"})
        eq(any(e["trigger"] == "evidence-expired"
               for e in escalations(ev_store, "2027-02-01")), False,
           "an expired artifact nobody cited is clutter, not an escalation")
        ev_rec["requirements"].append(
            {"requirement": "encryption at rest", "met": True, "evidenceRef": t1["id"]})
        expired = [e for e in escalations(ev_store, "2027-02-01")
                   if e["trigger"] == "evidence-expired"]
        eq(len(expired), 1, "but one holding up a satisfied requirement escalates")
        # Indexed defensively: a broken `evidence_status` empties this list, and an
        # IndexError here would kill the run's summary and hide how much else broke.
        ok("period ended" in str(at(expired, 0, "evidence")),
           "and the record says what expired and when")

        # --- P2 T3/T4: batteries and their narrowing --------------------------
        # Every shipped question names a GV.SC reference and asks for EVIDENCE, never an
        # attestation. "Do you encrypt at rest?" is worthless; every vendor answers yes.
        ATTESTATION = re.compile(r"^(do|are|is|does|have|has|can|will) ", re.I)
        seen_keys = set()
        for battery in BATTERIES:
            ok(battery.get("gvsc"), "battery %r names a GV.SC reference" % battery["id"])
            for q in battery["questions"]:
                ok(not ATTESTATION.match(q["ask"]),
                   "battery %r asks for evidence, not an attestation: %r"
                   % (battery["id"], q["ask"][:44]))
                key = question_key(battery, q)
                ok(key not in seen_keys, "question key %r is unique across the core" % key)
                seen_keys.add(key)

        bt_store = new_store("Battery Ltd")
        add_vendor(bt_store, "Some Provider")
        bt = add_arrangement(bt_store, "V-001", "a service", "An Owner")
        total = len(BATTERIES)

        # §2.2 — nothing declared anywhere. Absence asks MORE.
        res = batteries_for(bt, bt_store, None)
        eq(len(res["applied"]), total, "with no context and no criticality, every battery applies")
        eq(res["skipped"], [], "and nothing is skipped")

        # untraced is not a level and narrows nothing.
        classify(bt_store, "VA-001", {}, confirm=None)
        eq(criticality_of(bt), UNTRACED, "the fixture is untraced")
        eq(len(batteries_for(bt, bt_store, None)["applied"]), total,
           "an untraced arrangement gets the FULL battery — it is not a level to narrow by")

        # §2.3 — the arrangement outranks the profile, in BOTH directions.
        profile_no_ai = {"profile": {"aiInUse": {"value": False, "declaredBy": "GC",
                                                 "declaredOn": "2026-01-01"}}}
        res = batteries_for(bt, bt_store, profile_no_ai)
        ok(not any(b["id"] == "ai-overlay" for b in res["applied"]),
           "a profile declaring aiInUse false skips the AI battery")
        skip = next((x for x in res["skipped"] if x["battery"] == "ai-overlay"), {})
        eq(skip.get("declaredBy"), "GC", "and the skip names who declared it")
        eq(skip.get("declaredOn"), "2026-01-01", "and when")
        ok("profile" in skip.get("reason", ""), "and which layer decided it")

        bt["declares"] = {"aiInUse": {"value": True, "declaredBy": "Vendor Manager",
                                      "declaredOn": "2026-05-05"}}
        res = batteries_for(bt, bt_store, profile_no_ai)
        ok(any(b["id"] == "ai-overlay" for b in res["applied"]),
           "an ARRANGEMENT declaring aiInUse true beats a profile declaring it false")
        bt["declares"] = {"aiInUse": {"value": False, "declaredBy": "Vendor Manager",
                                      "declaredOn": "2026-05-05"}}
        profile_ai = {"profile": {"aiInUse": {"value": True, "declaredBy": "CISO",
                                              "declaredOn": "2026-01-01"}}}
        res = batteries_for(bt, bt_store, profile_ai)
        skip = next((x for x in res["skipped"] if x["battery"] == "ai-overlay"), {})
        ok(skip, "...and declaring it false beats a profile declaring it true")
        ok("arrangement" in skip.get("reason", ""),
           "with the reason naming the arrangement as the deciding layer")
        eq(skip.get("declaredBy"), "Vendor Manager", "and its declarer, not the profile's")
        bt.pop("declares", None)

        # A criticality-gated battery narrows only for a real level below the top.
        classify(bt_store, "VA-001", ctx, confirm="low", by="R. Calder")
        res = batteries_for(bt, bt_store, None)
        ok(not any(b["id"] == "exit" for b in res["applied"]),
           "a low-criticality arrangement is not asked for a tested exit")
        classify(bt_store, "VA-001", ctx, confirm="high", by="R. Calder")
        ok(any(b["id"] == "exit" for b in batteries_for(bt, bt_store, None)["applied"]),
           "and a top-criticality one is")
        ok(all(x.get("declaredBy") is not None and "declaredOn" in x
               for x in batteries_for(bt, bt_store, profile_no_ai)["skipped"]),
           "every skip record carries a declarer and a date (§2.4)")

        # --- P2 T5/T6/T7: the Layer A / Layer B boundary ----------------------
        pb = new_store("Boundary Ltd")
        add_vendor(pb, "Contoso Cloud")
        pbr = add_arrangement(pb, "V-001", "hosting", "CTO", supports="CRM",
                              starts_on="2026-01-01")
        classify(pb, "VA-001", ctx, confirm="moderate", by="R. Calder")
        soc2 = ingest(pb, "VA-001", "soc2-type2", "T1", "auditor PDF",
                      scope="the hosting platform", period_start="2025-01-01",
                      period_end="2025-12-31")
        trust = ingest(pb, "VA-001", "trust-page", "T3", "their trust centre")
        pbpath = os.path.join(work, "pb.vnd")
        save(pbpath, pb)
        before = open(pbpath, "rb").read()

        refuses(lambda: propose(pb, "VA-001", "encryption at rest", soc2["id"], ""),
                "propose with no citation is refused", "is an opinion")
        # THE refusal. A trust page can never propose satisfaction.
        refuses(lambda: propose(pb, "VA-001", "encryption at rest", trust["id"],
                                "their trust centre says AES-256"),
                "propose citing a T3 is REFUSED outright", "never satisfy a requirement")
        refuses(lambda: propose(pb, "VA-001", "", soc2["id"], "s 4.2"),
                "propose with no requirement is refused")
        eq(open(pbpath, "rb").read(), before, "and no refusal touched the file")

        pr = propose(pb, "VA-001", "encryption at rest", soc2["id"],
                     "SOC 2 section IV, control CC6.7, tested no exceptions",
                     by="reading layer")
        eq(pr["status"], "proposed", "a valid proposal is stored as proposed")
        # THE test that matters. Layer A has written, and nothing is satisfied.
        eq([r for r in (pbr.get("requirements") or []) if r.get("met")], [],
           "and NOTHING is satisfied by it — the reading layer cannot close anything")
        eq(len(open_proposals(pbr)), 1, "it sits in the working view awaiting a person")

        refuses(lambda: assess(pb, "VA-001", "", confirm=[pr["id"]]),
                "assess with no --by is refused", "nobody's name on it")
        refuses(lambda: assess(pb, "VA-001", "R. Calder", reject=[pr["id"]]),
                "--reject with no --why is refused", "tells a later reader nothing")
        eq([r for r in (pbr.get("requirements") or []) if r.get("met")], [],
           "and a refused assessment satisfies nothing either")

        act = assess(pb, "VA-001", "R. Calder", on="2026-06-30", confirm=[pr["id"]],
                     note="FY26 H1 review")
        met = [r for r in pbr["requirements"] if r.get("met")]
        eq(len(met), 1, "a confirmed proposal satisfies its requirement")
        eq(at(met, 0, "evidenceRef"), soc2["id"], "...naming the evidence that satisfied it")
        ok(str(at(met, 0, "citation")).startswith("SOC 2 section IV"), "...and the citation")
        eq(at(met, 0, "checkedBy"), "R. Calder", "...and the person who confirmed it")
        eq(open_proposals(pbr), [], "and it leaves the working view")

        # THE SEAM PLAN 1 LEFT OPEN. `_last_assessed` has been reading this list since
        # v0.39.1 with nothing able to write to it; `assess` is the act that resets the clock.
        eq(_last_assessed(pbr), "2026-06-30", "assess writes the assessments list")
        pb["arrangements"][0]["exit"]["testedOn"] = "2026-06-30"
        trig = {e["trigger"] for e in escalations(pb, "2026-07-01")}
        ok("assessment-overdue" not in trig,
           "...and clears assessment-overdue, closing the seam Plan 1 built the clock for")

        # A rejected proposal is retained, hidden from the working view, present on export.
        pr2 = propose(pb, "VA-001", "penetration testing cadence", soc2["id"],
                      "SOC 2 section III mentions annual testing", by="reading layer")
        assess(pb, "VA-001", "R. Calder", on="2026-07-01", reject=[pr2["id"]],
               why="the report describes the vendor's own testing, not an independent test")
        eq(open_proposals(pbr), [], "a rejected proposal leaves the working view")
        kept = [x for x in pbr["proposals"] if x["status"] == "rejected"]
        eq(len(kept), 1, "but is RETAINED — that a claim was examined and refused is a record")
        ok(at(kept, 0, "rejectedWhy", ""), "with the reason it was refused")

        # unconfirmed-proposals: a stack of readings must never read as an assessment.
        pr3 = propose(pb, "VA-001", "backup restoration testing", soc2["id"],
                      "SOC 2 section IV CC7.4", by="reading layer")
        pr3["proposedOn"] = "2026-07-02"
        eq(any(e["trigger"] == "unconfirmed-proposals"
               for e in escalations(pb, "2026-07-20")), False,
           "proposals inside the window escalate nothing")
        stale = [e for e in escalations(pb, "2026-09-01")
                 if e["trigger"] == "unconfirmed-proposals"]
        eq(len(stale), 1, "beyond it, exactly one record — not one per proposal")
        ok("1 proposal" in str(at(stale, 0, "evidence")), "naming how many are waiting")

        # --- P2 T9: the subtraction -------------------------------------------
        def _askstore(level="high"):
            st = new_store("Ask Ltd")
            add_vendor(st, "Contoso Cloud")
            add_arrangement(st, "V-001", "hosting", "CTO", supports="CRM")
            classify(st, "VA-001", ctx, confirm=level, by="R. Calder")
            return st, st["arrangements"][0]

        def _cover(st, keys, tier="T1", period_end="2026-12-31"):
            """Close `keys` with an artifact of `tier`, through the real acts."""
            ev = ingest(st, "VA-001", "soc2-type2" if tier == "T1" else "questionnaire",
                        tier, "supplied by the vendor",
                        scope="the hosting platform" if tier == "T1" else "",
                        period_start="2025-01-01" if tier == "T1" else "",
                        period_end=period_end if tier == "T1" else "")
            for key in keys:
                if tier in SATISFYING_TIERS:
                    pr = propose(st, "VA-001", key, ev["id"], "cited passage for %s" % key)
                    assess(st, "VA-001", "R. Calder", on="2026-01-05", confirm=[pr["id"]])
                else:
                    # A T3 cannot be proposed against at all, which IS the point. Record the
                    # closure the only other way a store could carry one, so the check below
                    # measures the tier rule rather than the refusal that precedes it.
                    st["arrangements"][0].setdefault("requirements", []).append(
                        {"requirement": key, "met": True, "evidenceRef": ev["id"],
                         "citation": "their trust page", "checkedBy": "someone",
                         "checkedOn": "2026-01-05"})
            return ev

        # 1. No evidence at all: every applicable question, and the count is the battery total.
        st, rec_a = _askstore("high")
        applied = batteries_for(rec_a, st, None)["applied"]
        expected = sum(len(b["questions"]) for b in applied)
        res = ask(st, "VA-001", None, today="2026-02-01")
        eq(res["open"], expected, "with no evidence, every applicable question is open")
        eq(res["reConfirm"], 0, "and nothing is a re-confirmation")
        ok(all(q["gvsc"] for q in res["questions"]),
           "every question names the GV.SC outcome it serves")
        ok(all(q["why"] for q in res["questions"]),
           "and says why it is being asked")

        # 2. A T1 covering three questions removes exactly those three.
        st, rec_b = _askstore("high")
        three = ["contract-terms.incident-notice", "assurance.latest-report",
                 "subprocessors.current-list"]
        _cover(st, three, tier="T1")
        res = ask(st, "VA-001", None, today="2026-02-01")
        keys = {q["key"] for q in res["questions"]}
        eq(res["open"], expected - 3, "a T1 covering three questions removes exactly three")
        ok(not (keys & set(three)), "...and it is those three that are gone")
        eq(res["reConfirm"], 0, "and none of them came back as a re-confirmation")

        # 3. THE PRODUCT CLAIM. The same three, covered by a T3, remove nothing.
        st, rec_c = _askstore("high")
        _cover(st, three, tier="T3")
        res_t3 = ask(st, "VA-001", None, today="2026-02-01")
        eq(res_t3["open"], expected,
           "the same three covered by a T3 remove NOTHING — a trust page closes no question")
        ok(set(three) <= {q["key"] for q in res_t3["questions"]},
           "...and all three are still being asked")
        ok(res_t3["open"] > (expected - 3),
           "so reading a real report shrinks the set and reading marketing copy does not")

        # 4. Evidence that has slipped into grace is re-confirmed, not silently dropped.
        st, rec_d = _askstore("high")
        _cover(st, three, tier="T1", period_end="2025-12-31")
        res = ask(st, "VA-001", None, today="2026-06-01")
        eq(res["reConfirm"], 3, "evidence in grace produces re-confirmation questions")
        eq(res["open"], expected - 3, "which are not counted as never-answered")
        grace_q = [q for q in res["questions"] if q["status"] == "re-confirm"]
        ok(all("in grace" in q["why"] for q in grace_q),
           "and each says the answer is ageing rather than missing")
        # Past grace it is not coverage at all, and the question is open again.
        res = ask(st, "VA-001", None, today="2027-06-01")
        eq(res["open"], expected, "past grace the question is open again, not re-confirm")
        eq(res["reConfirm"], 0, "because expired evidence covers nothing")

        # 5. Everything covered: an explicit sentence, never an empty string.
        st, rec_e = _askstore("high")
        every = [question_key(b, q)
                 for b in batteries_for(rec_e, st, None)["applied"] for q in b["questions"]]
        _cover(st, every, tier="T1")
        res = ask(st, "VA-001", None, today="2026-02-01")
        eq(res["questions"], [], "with everything covered there are no questions")
        eq(res.get("note"), NOTHING_OPEN,
           "...and the result SAYS so — a blank page and 'all evidenced' look identical "
           "on screen and mean opposite things")

        # --- P2 T11: the overlay mechanism, shipping empty --------------------
        eq(list(OVERLAYS), [],
           "no regime overlay ships — no obligation is asserted that cannot cite its source")
        # THE regression this has to prevent: with no overlay active, the battery set must be
        # exactly what it was before overlays existed.
        ov_store, ov_rec = _askstore("high")
        base = [b["id"] for b in batteries_for(ov_rec, ov_store, None)["applied"]]
        eq([b["id"] for b in batteries_for(ov_rec, ov_store, None, overlays=[])["applied"]],
           base, "a register with no overlay asks exactly what the core asks")

        # The gate that stops uncited content shipping later.
        bucket = []
        refuses(lambda: register_overlay({"id": "dora", "flag": "doraScope", "batteries": [
                    {"id": "roi", "questions": [{"id": "q1", "ask": "What is X?"}]}]},
                    into=bucket),
                "an overlay question with no source is refused", "cannot cite")
        refuses(lambda: register_overlay({"id": "x", "batteries": []}, into=bucket),
                "an overlay with no selecting flag is refused", "not an overlay")
        eq(bucket, [], "and nothing uncited was registered")
        cited = register_overlay(
            {"id": "demo", "flag": "demoScope", "source": "a primary text",
             "batteries": [{"id": "demo-battery", "gvsc": ["GV.SC-05"],
                            "appliesWhen": {},
                            "questions": [{"id": "q1", "ask": "What dated evidence covers X?",
                                           "source": "Article 1(1), verified 2026-08-08"}]}]},
            into=bucket)
        eq(len(bucket), 1, "a cited overlay registers")
        eq(overlays_for({"profile": {"demoScope": {"value": True}}}, bucket), [cited],
           "and a declared flag turns it on")
        eq(overlays_for({"profile": {"demoScope": {"value": False}}}, bucket), [],
           "a flag declared false leaves it off")
        eq(overlays_for({}, bucket), [],
           "and absence never turns one on — a regime applies because somebody declared it")
        with_ov = [b["id"] for b in
                   batteries_for(ov_rec, ov_store, {"profile": {"demoScope": {"value": True}}},
                                 overlays=bucket)["applied"]]
        ok("demo-battery" in with_ov, "an active overlay ADDS a battery")
        ok(set(base) <= set(with_ov), "...and replaces none of the core")

        # --- P2 T12: the Register of Information ------------------------------
        dora_on = {"profile": {"doraScope": {"value": True, "declaredBy": "GC",
                                             "declaredOn": "2026-01-20"}}}
        refuses(lambda: export_roi(ov_store, None), "export-roi with no declared scope is refused",
                "Absence is not a 'no'")
        refuses(lambda: export_roi(ov_store, {"profile": {"doraScope": {"value": False}}}),
                "...and with the flag declared false")
        roi_store = new_store("Filing Ltd")
        add_vendor(roi_store, "Contoso Cloud", jurisdiction="IE")
        add_arrangement(roi_store, "V-001", "hosting", "CTO", supports="CRM",
                        starts_on="2026-01-01")
        add_arrangement(roi_store, "V-001", "sandbox", "CMO")     # no supports, unclassified
        classify(roi_store, "VA-001", ctx, confirm="high", by="R. Calder")
        out = export_roi(roi_store, dora_on, today="2026-08-08")
        eq(out["complete"], False, "an incomplete register does NOT export as complete")
        eq([g["arrangementRef"] for g in out["gaps"]], ["VA-002"],
           "and names which arrangement is short")
        ok("criticality" in out["gaps"][0]["missing"] and "supports" in out["gaps"][0]["missing"],
           "naming each missing field rather than emitting a blank cell")
        eq(len(out["rows"]), 2, "every live arrangement is still present, gaps and all")
        row = next(r for r in out["rows"] if r["arrangementRef"] == "VA-001")
        eq(row["criticalityScaleVersion"], "v1",
           "a filed criticality carries the scale it was assigned under")
        eq(row["criticalityConfirmedBy"], "R. Calder", "and who assigned it")
        # A DERIVED level is a proposal. Filing one as though a person assigned it is the
        # failure this whole skill refuses.
        classify(roi_store, "VA-002", ctx)
        out2 = export_roi(roi_store, dora_on, today="2026-08-08")
        row2 = next(r for r in out2["rows"] if r["arrangementRef"] == "VA-002")
        eq(row2["criticality"], "",
           "a derived-but-unconfirmed level is NOT filed as though somebody assigned it")
        ok(any(g["arrangementRef"] == "VA-002" for g in out2["gaps"]),
           "...it stays a named gap")

        # --- P2 T14: the findings bridge --------------------------------------
        fb = new_store("Bridge Ltd")
        add_vendor(fb, "Contoso Cloud", jurisdiction="IE")
        add_arrangement(fb, "V-001", "hosting", "CTO", supports="CRM", gvsc=["GV.SC-05"])
        classify(fb, "VA-001", ctx, confirm="high", by="R. Calder")
        eq(export_findings(fb)["findings"], [],
           "a register with nothing recorded as unmet exports no findings")
        review_requirements(fb, "VA-001", "breach notification within 24h",
                            "MSA schedule 3 — no such clause", met=False, by="General Counsel")
        out = export_findings(fb, today="2026-08-08")
        eq(len(out["findings"]), 1, "a requirement recorded as NOT met is a finding")
        f = out["findings"][0]
        ok("not evidenced" in f["title"] and "Contoso Cloud" in f["title"],
           "titled so a risk register reader knows the provider and the gap")
        eq(f["criticalityScaleVersion"], "v1",
           "carrying the scale the criticality was assigned under")
        eq(f["checkedBy"], "General Counsel", "and who checked it")
        # THE line this bridge does not cross.
        flat = json.dumps(out).lower()
        for key in FINDING_SCORING_KEYS:
            ok('"%s"' % key not in flat,
               "the payload carries no %r — risk-register scores these once, there" % key)
        # An escalation is derived and stateless. Exporting one would mint a fresh candidate
        # risk every time a clock moved.
        ok(any(e["trigger"] == "exit-untested" for e in escalations(fb, "2026-08-08")),
           "the fixture is escalating something")
        eq(len(export_findings(fb)["findings"]), 1,
           "...and escalations are NOT exported — one exposure, one system of record")
        # Unattributed non-compliance is not a finding: nobody is recorded as having looked.
        fb["arrangements"][0]["requirements"].append(
            {"requirement": "something", "met": False, "checkedBy": ""})
        eq(len(export_findings(fb)["findings"]), 1,
           "a requirement nobody is recorded as checking is not exported")

        # --- T14: the consolidation guard -------------------------------------
        multi = new_store("Group Plc")
        add_vendor(multi, "Shared Provider")
        add_arrangement(multi, "V-001", "hosting", "CTO", entity_ref="Northwind Ltd")
        add_arrangement(multi, "V-001", "hosting", "CTO", entity_ref="Contoso Freight Ltd")
        refuses(lambda: analyze(multi), "a register spanning entities refuses a single view",
                "Contoso Freight Ltd")
        multi["settings"]["consolidation"] = {"declaredBy": "General Counsel"}
        refuses(lambda: analyze(multi), "a consolidation with no basis is refused too",
                "the basis is the part a reviewer actually needs")
        multi["settings"]["consolidation"] = {
            "declaredBy": "General Counsel",
            "basis": "Contoso Freight is a wholly owned subsidiary, consolidated for group "
                     "reporting"}
        out = analyze(multi)
        eq(out["consolidation"]["entities"], ["Contoso Freight Ltd", "Northwind Ltd"],
           "an attributed consolidation renders, naming every entity")
        ok(any("General Counsel" in n for n in out["notes"]),
           "and the declaration is printed, so a consolidated view never looks single-entity")

        # --- analyze: no score, anywhere --------------------------------------
        out = analyze(store, context=ctx)
        flat = json.dumps(out).lower()
        for banned in ("score", "rating", "grade", "posturescore"):
            ok(banned not in flat,
               "the analysis emits no %r — findings are scored once, in risk-register"
               % banned)
        ok(isinstance(out["counts"]["byCriticality"], dict),
           "criticality is counted, never aggregated into a single number")

    finally:
        shutil.rmtree(work, ignore_errors=True)

    if fails:
        print("FAILED:")
        for f in fails:
            print("  - %s" % f)
        print("self-test: %d/%d checks passed" % (checks[0] - len(fails), checks[0]))
        return 1
    print("self-test: %d/%d checks passed" % (checks[0], checks[0]))
    return 0


# --- CLI ----------------------------------------------------------------------

def _ctx(args):
    return load_context(args.context) if getattr(args, "context", "") else None


def _cmd_init(args) -> int:
    if os.path.exists(args.store):
        raise Refusal(f"{args.store} already exists. `init` never overwrites a register: "
                      f"the history in it is the point.")
    save(args.store, new_store(args.org, args.prepared_by, args.scope_note))
    print("Created %s for %r" % (args.store, args.org))
    return 0


def _cmd_add_vendor(args) -> int:
    store = load(args.store)
    rec = add_vendor(store, args.name, args.jurisdiction, args.group_parent, by=args.by)
    save(args.store, store)
    print("%s  %s" % (rec["id"], rec["name"]))
    return 0


def _cmd_add_arrangement(args) -> int:
    store = load(args.store)
    rec = add_arrangement(store, args.vendor, args.services, args.owner,
                          supports=args.supports, entity_ref=args.entity,
                          starts_on=args.starts, ends_on=args.ends, cost=args.cost,
                          gvsc=args.gvsc, sr=args.sr, by=args.by)
    save(args.store, store)
    print("%s  %s — %s (owner: %s)"
          % (rec["id"], rec["vendorRef"], rec["services"], rec["owner"]))
    return 0


def _cmd_set_scale(args) -> int:
    store = load(args.store)
    levels = set_scale(store, [x for x in args.levels.split(",")], version=args.version)
    save(args.store, store)
    print("scale: %s (version %s)" % (", ".join(levels), store["settings"]["scaleVersion"]))
    return 0


def _cmd_classify(args) -> int:
    store = load(args.store)
    block = classify(store, args.arrangement, _ctx(args), confirm=args.confirm,
                     by=args.by, basis=args.basis, layer=args.layer)
    save(args.store, store)
    print("%s  derived %s%s" % (args.arrangement, block["derived"],
                                "  (truncated)" if block.get("truncated") else ""))
    if block.get("trace"):
        print("  trace: %s" % " -> ".join(block["trace"]))
    if block.get("confirmed"):
        print("  assigned %s by %s on %s (scale %s)"
              % (block["confirmed"]["value"], block["confirmed"]["by"],
                 block["confirmed"]["on"], block["confirmed"]["scaleVersion"]))
    else:
        print("  no final level assigned yet — derivation proposes, a person assigns")
    return 0


def _cmd_test_exit(args) -> int:
    store = load(args.store)
    ex = test_exit(store, args.arrangement, args.tested, args.why, on=args.on, by=args.by)
    save(args.store, store)
    print("%s  exit exercised %s" % (args.arrangement, ex["testedOn"]))
    return 0


def _cmd_document_exit(args) -> int:
    store = load(args.store)
    ex = document_exit(store, args.arrangement, args.note, on=args.on, by=args.by)
    save(args.store, store)
    print("%s  exit documented %s (not tested: %s)"
          % (args.arrangement, ex["documentedOn"], ex["testedOn"] or "never"))
    return 0


def _cmd_ingest(args) -> int:
    store = load(args.store)
    ev = ingest(store, args.arrangement, args.kind, args.tier, args.source,
                scope=args.scope, period_start=args.period_start,
                period_end=args.period_end, url=args.url, retrieved=args.retrieved,
                by=args.by)
    save(args.store, store)
    print("%s  %s  %s (%s)" % (args.arrangement, ev["id"], ev["kind"],
                               TIER_LABEL[ev["tier"]]))
    if ev["tier"] not in SATISFYING_TIERS:
        print("  %s closes nothing. It records context and generates questions."
              % ev["tier"])
    return 0


def _cmd_propose(args) -> int:
    store = load(args.store)
    pr = propose(store, args.arrangement, args.requirement, args.evidence, args.citation,
                 note=args.note, by=args.by)
    save(args.store, store)
    print("%s  %s  proposed: %s" % (args.arrangement, pr["id"], pr["requirement"]))
    print("  cites %s — %s" % (pr["evidenceRef"], pr["citation"]))
    print("  NOTHING is satisfied by this. A named person confirms it with `assess`.")
    return 0


def _cmd_assess(args) -> int:
    store = load(args.store)
    act = assess(store, args.arrangement, args.by, on=args.on, confirm=args.confirm,
                 reject=args.reject, why=args.why, note=args.note)
    save(args.store, store)
    print("%s  assessed %s by %s — %d confirmed, %d rejected"
          % (args.arrangement, act["on"], act["by"],
             len(act["confirmed"]), len(act["rejected"])))
    return 0


def _cmd_ask(args) -> int:
    store = load(args.store)
    out = ask(store, args.arrangement, _ctx(args), today=args.today)
    if args.format == "json":
        json.dump(out, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
        return 0
    md = args.format == "md"
    head = "%s — %s criticality, as at %s" % (out["arrangement"], out["criticality"],
                                              out["asOf"])
    print(("## " + head) if md else head)
    print()
    if not out["questions"]:
        # Never an empty page. A blank result and "all evidenced" look identical on screen.
        print(out["note"])
    else:
        print("%d open, %d for re-confirmation:" % (out["open"], out["reConfirm"]))
        print()
        for q in out["questions"]:
            bullet = "- " if md else "  "
            flag = "" if q["status"] == "open" else "  [re-confirm]"
            print("%s%s%s" % (bullet, q["ask"], flag))
            print("%s  why: %s (%s)" % ("  " if md else "    ", q["why"],
                                        ", ".join(q["gvsc"])))
            print()
    for skip in out["skipped"]:
        # §2.4 verbatim: an assessor must be able to tell a question ruled out from one
        # nobody asked.
        print("not asked — %s: %s%s"
              % (skip["battery"], skip["reason"],
                 (" (declared by %s on %s)" % (skip["declaredBy"], skip["declaredOn"]))
                 if skip.get("declaredBy") else " (nobody is recorded as declaring this)"))
    return 0


def _cmd_export_roi(args) -> int:
    store = load(args.store)
    out = export_roi(store, _ctx(args), today=args.today)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(out, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
        print("Wrote %s — %d row(s)" % (args.out, len(out["rows"])), file=sys.stderr)
    else:
        json.dump(out, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
    if out["gaps"]:
        # Non-zero, deliberately. A register that files cleanly and is wrong is worse than one
        # that refuses, and a zero exit is what a script reads as "fine to send".
        print("\n%d arrangement(s) are not complete enough to file:" % len(out["gaps"]),
              file=sys.stderr)
        for gap in out["gaps"]:
            print("  %s — %s" % (gap["arrangementRef"], gap["detail"]), file=sys.stderr)
        return 1
    return 0


def _cmd_export_findings(args) -> int:
    store = load(args.store)
    out = export_findings(store, today=args.today)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(out, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
        print("Wrote %s — %d finding(s)" % (args.out, len(out["findings"])), file=sys.stderr)
    else:
        json.dump(out, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
    print("\nOne-way. Import with `score_register.py import-findings <file> --into r.rr "
          "--write`.\nNo likelihood, impact or band travels: risk-register scores these once, "
          "there.", file=sys.stderr)
    return 0


def _cmd_review_requirements(args) -> int:
    store = load(args.store)
    entry = review_requirements(store, args.arrangement, args.requirement, args.evidence,
                                met=not args.absent, by=args.by)
    save(args.store, store)
    print("%s  %s: %s" % (args.arrangement, entry["requirement"],
                          "met" if entry["met"] else "ABSENT"))
    return 0


def _cmd_record_subprocessor(args) -> int:
    store = load(args.store)
    entry = record_subprocessor(store, args.arrangement, args.name, args.effective,
                               note=args.note, by=args.by)
    save(args.store, store)
    print("%s  subprocessor %s effective %s"
          % (args.arrangement, entry["name"], entry["effective"]))
    return 0


def _cmd_retire(args) -> int:
    store = load(args.store)
    rec = retire(store, args.arrangement, args.data_went, args.deletion_confirmed,
                 why=args.why, by=args.by)
    save(args.store, store)
    print("%s  retired %s; deletion confirmed %s"
          % (args.arrangement, rec["on"], rec["deletionConfirmedOn"]))
    return 0


def _cmd_succeed(args) -> int:
    store = load(args.store)
    set_prior(store, args.arrangement, args.prior)
    save(args.store, store)
    print("%s succeeds %s" % (args.arrangement, args.prior))
    return 0


def _cmd_review(args) -> int:
    store = load(args.store)
    snap = review(store, args.label, args.why)
    save(args.store, store)
    print("snapshot %r — %d arrangements frozen at scale %s"
          % (snap["label"], len(snap["arrangements"]),
             snap["settings"].get("scaleVersion")))
    return 0


def _cmd_analyze(args) -> int:
    store = load(args.store)
    out = analyze(store, today=args.today, context=_ctx(args))
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(out, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
        print("Wrote %s" % args.out)
        return 0
    if args.json:
        json.dump(out, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
        return 0
    print("%s — %d arrangements across %d vendors, as at %s"
          % (out["organisation"], out["counts"]["arrangements"],
             out["counts"]["vendors"], out["asOf"]))
    for level, n in out["counts"]["byCriticality"].items():
        print("  %-14s %d" % (level, n))
    for note in out["notes"]:
        print("  note: %s" % note)
    if out["escalations"]:
        print("  %d escalation(s):" % len(out["escalations"]))
        for e in out["escalations"]:
            print("    %-8s %-26s %s" % (e["severity"], e["trigger"], e["subjectRef"]))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="vendor_register.py", description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)

    def store_arg(sp):
        sp.add_argument("store")
        return sp

    sp = store_arg(sub.add_parser("init"))
    sp.add_argument("--org", required=True)
    sp.add_argument("--prepared-by", default="")
    sp.add_argument("--scope-note", default="")
    sp.set_defaults(fn=_cmd_init)

    sp = store_arg(sub.add_parser("add-vendor"))
    sp.add_argument("--name", required=True)
    sp.add_argument("--jurisdiction", default="")
    sp.add_argument("--group-parent", default="")
    sp.add_argument("--by", default="")
    sp.set_defaults(fn=_cmd_add_vendor)

    sp = store_arg(sub.add_parser("add-arrangement"))
    sp.add_argument("--vendor", required=True)
    sp.add_argument("--services", default="")
    sp.add_argument("--owner", default="")
    sp.add_argument("--supports", default="",
                    help="the system or component this arrangement holds up. The start of "
                         "the criticality walk; without it the trace has nowhere to begin.")
    sp.add_argument("--entity", default="")
    sp.add_argument("--starts", default="")
    sp.add_argument("--ends", default="")
    sp.add_argument("--cost", default="")
    sp.add_argument("--gvsc", action="append", default=[])
    sp.add_argument("--sr", action="append", default=[])
    sp.add_argument("--by", default="")
    sp.set_defaults(fn=_cmd_add_arrangement)

    sp = store_arg(sub.add_parser("set-scale"))
    sp.add_argument("--levels", required=True, help="comma-separated, LOWEST first")
    sp.add_argument("--version", default="")
    sp.set_defaults(fn=_cmd_set_scale)

    sp = store_arg(sub.add_parser("classify"))
    sp.add_argument("--arrangement", required=True)
    sp.add_argument("--context", default="")
    sp.add_argument("--confirm", default="")
    sp.add_argument("--by", default="")
    sp.add_argument("--basis", default="")
    sp.add_argument("--layer", default="", choices=["", "system", "component"])
    sp.set_defaults(fn=_cmd_classify)

    sp = store_arg(sub.add_parser("test-exit"))
    sp.add_argument("--arrangement", required=True)
    sp.add_argument("--tested", default="")
    sp.add_argument("--why", default="")
    sp.add_argument("--on", default="")
    sp.add_argument("--by", default="")
    sp.set_defaults(fn=_cmd_test_exit)

    sp = store_arg(sub.add_parser("document-exit"))
    sp.add_argument("--arrangement", required=True)
    sp.add_argument("--note", default="")
    sp.add_argument("--on", default="")
    sp.add_argument("--by", default="")
    sp.set_defaults(fn=_cmd_document_exit)

    sp = store_arg(sub.add_parser("ingest"))
    sp.add_argument("--arrangement", required=True)
    sp.add_argument("--kind", default="", help="soc2-type2, iso27001-cert, dpa, trust-page, ...")
    sp.add_argument("--tier", default="", choices=list(TIERS) + [""],
                    help="T1 audited · T2 contractual · T3 vendor assertion · T4 public copy. "
                         "Only T1 and T2 can satisfy a requirement.")
    sp.add_argument("--source", default="")
    sp.add_argument("--scope", default="", help="required for T1: what the artifact covers")
    sp.add_argument("--period-start", default="")
    sp.add_argument("--period-end", default="", help="required for T1: when its period closed")
    sp.add_argument("--url", default="")
    sp.add_argument("--retrieved", default="", help="required with --url")
    sp.add_argument("--by", default="")
    sp.set_defaults(fn=_cmd_ingest)

    sp = store_arg(sub.add_parser("propose"))
    sp.add_argument("--arrangement", required=True)
    sp.add_argument("--requirement", default="")
    sp.add_argument("--evidence", default="", help="the EV- id this reading rests on")
    sp.add_argument("--citation", default="",
                    help="the passage or document reference. Required: a proposal with no "
                         "citation is an opinion.")
    sp.add_argument("--note", default="")
    sp.add_argument("--by", default="")
    sp.set_defaults(fn=_cmd_propose)

    sp = store_arg(sub.add_parser("assess"))
    sp.add_argument("--arrangement", required=True)
    sp.add_argument("--by", default="", help="required: only a named person confirms")
    sp.add_argument("--on", default="")
    sp.add_argument("--confirm", action="append", default=[], help="a PR- id. Repeatable.")
    sp.add_argument("--reject", action="append", default=[], help="a PR- id. Repeatable.")
    sp.add_argument("--why", default="", help="required with --reject")
    sp.add_argument("--note", default="")
    sp.set_defaults(fn=_cmd_assess)

    sp = store_arg(sub.add_parser("ask"))
    sp.add_argument("--arrangement", required=True)
    sp.add_argument("--context", default="")
    sp.add_argument("--today", default="")
    sp.add_argument("--format", default="text", choices=["text", "json", "md"])
    sp.set_defaults(fn=_cmd_ask)

    sp = store_arg(sub.add_parser("export-roi"))
    sp.add_argument("--context", default="")
    sp.add_argument("--today", default="")
    sp.add_argument("--out", default="")
    sp.set_defaults(fn=_cmd_export_roi)

    sp = store_arg(sub.add_parser("export-findings"))
    sp.add_argument("--today", default="")
    sp.add_argument("--out", default="")
    sp.set_defaults(fn=_cmd_export_findings)

    sp = store_arg(sub.add_parser("review-requirements"))
    sp.add_argument("--arrangement", required=True)
    sp.add_argument("--requirement", default="")
    sp.add_argument("--evidence", default="")
    sp.add_argument("--absent", action="store_true")
    sp.add_argument("--by", default="")
    sp.set_defaults(fn=_cmd_review_requirements)

    sp = store_arg(sub.add_parser("record-subprocessor"))
    sp.add_argument("--arrangement", required=True)
    sp.add_argument("--name", default="")
    sp.add_argument("--effective", default="")
    sp.add_argument("--note", default="")
    sp.add_argument("--by", default="")
    sp.set_defaults(fn=_cmd_record_subprocessor)

    sp = store_arg(sub.add_parser("retire"))
    sp.add_argument("--arrangement", required=True)
    sp.add_argument("--data-went", default="")
    sp.add_argument("--deletion-confirmed", default="")
    sp.add_argument("--why", default="")
    sp.add_argument("--by", default="")
    sp.set_defaults(fn=_cmd_retire)

    sp = store_arg(sub.add_parser("succeed"))
    sp.add_argument("--arrangement", required=True)
    sp.add_argument("--prior", required=True)
    sp.set_defaults(fn=_cmd_succeed)

    sp = store_arg(sub.add_parser("review"))
    sp.add_argument("--label", default="")
    sp.add_argument("--why", default="")
    sp.set_defaults(fn=_cmd_review)

    sp = store_arg(sub.add_parser("analyze"))
    sp.add_argument("--today", default="")
    sp.add_argument("--context", default="")
    sp.add_argument("--json", action="store_true")
    sp.add_argument("--out", default="")
    sp.set_defaults(fn=_cmd_analyze)

    sub.add_parser("self-test").set_defaults(fn=_cmd_self_test)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.fn(args)
    except Refusal as exc:
        print("Refused: %s" % exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
