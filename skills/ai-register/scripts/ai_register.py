#!/usr/bin/env python3
"""ai_register.py — the AI deployment register, from a security point of view.

An inventory of the AI the organisation runs, what each deployment touches, what it is exposed
to under the NIST adversarial ML taxonomy, and what is evidenced about its security.

Three ideas carry the file, and each is a refusal as much as a feature:

1. **Risk lives in the DEPLOYMENT, not the model.** The same LLM drafting marketing copy and
   screening job applicants is one system and two entirely different exposures. A register keyed
   on the model would force one answer, and it would be the wrong one for whichever deployment
   mattered more.

2. **An attack class has no closed state.** There is no `mitigated`, `resolved`, `closed` or
   `accepted` field on an exposure class anywhere in this file, and no command that sets one.
   Controls are recorded with evidence and a date; a class with controls reads as *controls
   applied*, never as handled. Where an organisation wants to accept the residual, that belongs
   in `exceptions-register`, and the refusal here says so.

3. **This is the CISO's slice, not AI governance.** It inventories and assesses security. It
   does not evaluate models, assess bias, or perform conformity assessment — see
   `references/scope.md`, which names those boundaries with their sources.

**Sourcing, stated plainly.** The exposure taxonomy follows the shape of NIST's adversarial
machine learning work (AI 100-2), which is NOT bundled in this repository the way the CSF Core
and the 800-53 crosswalk are. This file implements the structure and attributes it; it does not
quote the publication, and nothing here should be relied on as a citation without checking the
source. `references/nistaml-exposure.md` says the same thing at more length.

Refusals happen before the store file is opened, so a refused command leaves it byte-identical.
Standard library only. Subcommands:

  init              <store.air> --org 'Name'
  add-system        <store.air> --name '..' --provider '..' --version '..'
  intake-discovered <store.air> --name '..' --source '..' --found-on YYYY-MM-DD
  sanction          <store.air> --system S-001 --state sanctioned --by NAME --why '..'
  deploy            <store.air> --system S-001 --purpose '..' --owner '..' --autonomy informs
  classify          <store.air> --deployment D-001 [--context ctx.json]
                                [--confirm LEVEL --by NAME]
  map-exposure      <store.air> --deployment D-001
  record-control    <store.air> --deployment D-001 --class NISTAML.02 --control '..'
                                --evidence '..' --on YYYY-MM-DD
  declare           <store.air> --deployment D-001 --flag regulatedDataHeld --value true
                                --by NAME
  ingest            <store.air> --deployment D-001 --kind model-card --tier T3 --source '..'
  propose           <store.air> --deployment D-001 --requirement KEY --evidence EV-001
                                --citation '..'
  assess            <store.air> --deployment D-001 --by NAME [--confirm PR-001]
  record-requirement <store.air> --deployment D-001 --requirement KEY --evidence '..'
                                [--not-met] --by NAME
  ask               <store.air> --deployment D-001 [--context ctx.json] [--json]
  analyze           <store.air> [--today YYYY-MM-DD] [--context ctx.json] [--out FILE]
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
FAMILY = "ai-register"

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
SYSTEM_ID_RE = re.compile(r"^S-\d{3,}$")
DEPLOYMENT_ID_RE = re.compile(r"^D-\d{3,}$")

# `S-` and `D-`, chosen against the ids already minted across the suite: R- risks, A-
# acceptances, X- exceptions, M- metrics, I- incidents, V-/VA- vendors and arrangements.
# `board-pack` flags two sections asking the board about the same record by regexing ids out of
# decision prose, so a collision would be reported as one ask arriving twice.

UNTRACED = "untraced"
"""Traced, and the trace did not reach a workflow with a declared criticality.

Deliberately the SAME word `vendor-register` uses. A CISO who learned this vocabulary once must
not meet a second one for the same idea — and the property is identical: never a member of the
scale, and `criticality_rank` raises on it rather than returning a number.
"""

UNCLASSIFIED = "unclassified"
"""Nobody ran the walk. Distinct from `untraced`, which means we ran it and could not finish."""

DEFAULT_SCALE = ["low", "moderate", "high"]

# --- Autonomy -----------------------------------------------------------------
#
# Ordered, lowest first. Declared and never inferred: what a deployment is permitted to do is a
# statement about how it was wired up and who signed that off, and no attribute of a model
# implies it.
#
#   informs     it produces output a person reads
#   recommends  it proposes an action a person takes
#   decides     its output IS the decision — what most regimes call a consequential decision
#   acts        it takes actions against connected resources without a person in the loop
AUTONOMY = ("informs", "recommends", "decides", "acts")

HOSTING = ("self-hosted", "saas", "hybrid")
PROVENANCE = ("declared", "discovered")
SANCTION = ("sanctioned", "unsanctioned", "under-review")

SETTINGS_DEFAULTS = {
    "criticalityScale": list(DEFAULT_SCALE),
    "scaleVersion": "v1",
    "cadenceDays": {"high": 365, "moderate": 730},
    "traceMaxHops": 2,
    "evidenceGraceDays": 365,
    "proposalStaleDays": 30,
}

TRACE_MAX_HOPS = 2


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
        "systems": [],
        "deployments": [],
        "history": [],
        "snapshots": [],
        "createdAt": ts,
        "updatedAt": ts,
    }


def load(path: str) -> dict:
    """Open a `.air`. Validation guards WRITES; a store carrying a bad value still opens."""
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
            f"{path} is not an AI register: family is {fam!r}, expected {FAMILY!r}. A vendor "
            f"register (.vnd), risk register (.rr) or business context (.biz) belongs to a "
            f"different skill.")
    if store.get("schemaVersion") != SCHEMA_VERSION:
        raise Refusal(f"{path} is schemaVersion {store.get('schemaVersion')!r}; "
                      f"this engine reads {SCHEMA_VERSION}")
    store["meta"] = {"orgName": "", "preparedBy": "", "scopeNote": "", "asOf": "",
                     **(store.get("meta") or {})}
    settings = json.loads(json.dumps(SETTINGS_DEFAULTS))
    settings.update(store.get("settings") or {})
    settings["cadenceDays"] = {**SETTINGS_DEFAULTS["cadenceDays"],
                               **((store.get("settings") or {}).get("cadenceDays") or {})}
    store["settings"] = settings
    for key in ("systems", "deployments", "history", "snapshots"):
        if not isinstance(store.get(key), list):
            store[key] = []
    return store


def save(path: str, store: dict) -> None:
    store["updatedAt"] = now_ts()
    directory = os.path.dirname(os.path.abspath(path)) or "."
    fd, tmp = tempfile.mkstemp(dir=directory, suffix=".air.tmp")
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
    prefix, key, pattern = (("S", "systems", SYSTEM_ID_RE) if kind == "system"
                            else ("D", "deployments", DEPLOYMENT_ID_RE))
    used = [int(r["id"].split("-")[1]) for r in store[key]
            if pattern.match(str(r.get("id", "")))]
    return "%s-%03d" % (prefix, (max(used) + 1) if used else 1)


# --- Systems ------------------------------------------------------------------

def add_system(store: dict, name: str, provider: str, version: str, family: str = "",
               base_model: str = "", hosting: str = "saas", gen_ai: bool = True,
               fine_tuned: bool = False, retrieval_augmented: bool = False,
               vendor_ref: str = "", arrangement_ref: str = "", chain_note: str = "",
               by: str = "") -> dict:
    """A model or AI product the organisation has. Not, on its own, a risk.

    Refuses without a provider and a version. A register of AI that cannot say WHOSE model and
    WHICH version cannot answer the only question that matters after a model changes underneath
    a deployment — and it changes without anybody being told.
    """
    if not str(name or "").strip():
        raise Refusal("a system needs a --name")
    if not str(provider or "").strip():
        raise Refusal(
            "a system needs a --provider.\n"
            "  'Whose model is this' is the question every supply-chain exposure starts from, "
            "and an inventory that cannot answer it is a list of names.")
    if not str(version or "").strip():
        raise Refusal(
            "a system needs a --version.\n"
            "  Without one, nothing can tell that the model under a deployment changed — which "
            "is the event that silently invalidates every assessment made against it.")
    if hosting not in HOSTING:
        raise Refusal("--hosting must be one of %s" % ", ".join(HOSTING))
    rec = {
        "id": next_id(store, "system"),
        "name": name.strip(),
        "provider": provider.strip(),
        "version": version.strip(),
        "family": str(family or "").strip(),
        # Optional, and recorded only WHERE DISCLOSED. Many products do not say what they are
        # built on, and inventing a plausible answer would be worse than an empty field: the
        # `base-model-changed` trigger would then fire against a guess.
        "baseModel": str(base_model or "").strip(),
        "hosting": hosting,
        "genAI": bool(gen_ai),
        "fineTuned": bool(fine_tuned),
        "retrievalAugmented": bool(retrieval_augmented),
        "vendorRef": str(vendor_ref or "").strip(),
        "arrangementRef": str(arrangement_ref or "").strip(),
        # Free text, deliberately. The chain behind a model is often several parties deep and
        # partially undisclosed; a structured field would imply a completeness nobody has.
        "chainNote": str(chain_note or "").strip(),
        "provenance": "declared",
        "sanction": "sanctioned",
        "sanctionBy": "",
        "sanctionOn": "",
        "sanctionWhy": "",
    }
    store["systems"].append(rec)
    append_history(store, "system-added", rec["id"], by,
                   why="%s %s (%s)" % (rec["provider"], rec["name"], rec["version"]))
    return rec


def intake_discovered(store: dict, name: str, source: str, found_on: str,
                      provider: str = "", by: str = "") -> dict:
    """Shadow AI, recorded as a real row the moment it is found.

    No staging area, and that is the design. The failure mode of shadow AI is a finding that
    lives in a spreadsheet, an email thread or a CASB console — somewhere the register cannot
    see — until somebody remembers to promote it. A discovered system is unsanctioned and
    incomplete, and it is IN the register, where it can escalate.

    Refuses without a source and a date because 'we found some AI' is not a finding anybody can
    act on: the next person has to know where to look and how stale the sighting is.
    """
    if not str(name or "").strip():
        raise Refusal("a discovered system needs a --name, even a rough one")
    if not str(source or "").strip():
        raise Refusal(
            "--source is required: where this was found (a CASB egress review, an expense "
            "line, a support ticket).\n"
            "  Somebody has to be able to go back to it. 'We found some AI' is not a finding.")
    if not str(found_on or "").strip():
        raise Refusal("--found-on is required: a sighting with no date has unknown staleness")
    rec = add_system(store, name, provider or "undisclosed", "unknown",
                     hosting="saas", by=by)
    rec["provenance"] = "discovered"
    rec["sanction"] = "unsanctioned"
    rec["discoveredVia"] = source.strip()
    rec["discoveredOn"] = check_date(found_on, "--found-on")
    append_history(store, "system-discovered", rec["id"], by, why=source.strip(),
                   detail={"foundOn": rec["discoveredOn"]})
    return rec


def sanction(store: dict, sid: str, state: str, by: str, why: str) -> dict:
    if state not in SANCTION:
        raise Refusal("--state must be one of %s" % ", ".join(SANCTION))
    if not str(by or "").strip():
        raise Refusal("--by is required: sanctioning is a decision, and decisions have names")
    if not str(why or "").strip():
        raise Refusal("--why is required: the basis for the decision, not just the outcome")
    rec = find_system(store, sid)
    rec["sanction"] = state
    rec["sanctionBy"] = by.strip()
    rec["sanctionOn"] = utc_today()
    rec["sanctionWhy"] = why.strip()
    append_history(store, "sanction-set", sid, by, why=why.strip(),
                   detail={"state": state})
    return rec


def find_system(store: dict, sid: str) -> dict:
    for rec in store["systems"]:
        if rec.get("id") == sid:
            return rec
    known = ", ".join(r.get("id", "?") for r in store["systems"]) or "none yet"
    raise Refusal(f"no system {sid!r} in this register (known: {known})")


def find_deployment(store: dict, did: str) -> dict:
    for rec in store["deployments"]:
        if rec.get("id") == did:
            return rec
    known = ", ".join(r.get("id", "?") for r in store["deployments"]) or "none yet"
    raise Refusal(f"no deployment {did!r} in this register (known: {known})")


# --- Deployments --------------------------------------------------------------

def deploy(store: dict, system_ref: str, purpose: str, owner: str, autonomy: str,
           data_classes=None, connected_resources=None, supports: str = "",
           entity_ref: str = "", consequential: bool = False, by: str = "") -> dict:
    """One use of one system. THIS is where risk lives.

    Refuses without an owner and a declared autonomy. Autonomy gates both the security battery
    and every regulatory question this register can ask, so a deployment carrying an undeclared
    one cannot be assessed correctly — and would be assessed anyway, quietly, at whatever the
    default was.
    """
    if not str(system_ref or "").strip():
        raise Refusal("a deployment needs --system: which model or product it uses")
    if not any(s.get("id") == system_ref for s in store["systems"]):
        known = ", ".join(s.get("id", "?") for s in store["systems"]) or "none yet"
        raise Refusal(
            f"no system {system_ref!r} in this register (known: {known}). A deployment of "
            f"something that is not in the inventory is a row nobody can follow up.")
    if not str(purpose or "").strip():
        raise Refusal("a deployment needs a --purpose: what it is actually used for")
    if not str(owner or "").strip():
        raise Refusal(
            "a deployment needs an --owner.\n"
            "  Every escalation this register raises has to land on somebody, and a deployment "
            "nobody owns is the one that goes stale.")
    if autonomy not in AUTONOMY:
        raise Refusal(
            "--autonomy is required and must be one of %s.\n"
            "  It is declared, never inferred: what a deployment is permitted to do is a "
            "statement about how it was wired up and who signed that off, and no attribute of "
            "a model implies it. It gates the security battery and every regulatory question "
            "here, so an undeclared one would be assessed anyway, quietly, at the default."
            % ", ".join(AUTONOMY))
    rec = {
        "id": next_id(store, "deployment"),
        "systemRef": system_ref,
        "entityRef": str(entity_ref or "").strip() or (store["meta"].get("orgName") or ""),
        "purpose": purpose.strip(),
        "owner": owner.strip(),
        "autonomy": autonomy,
        # Who said so, and when. A battery skipped because the autonomy is below a threshold
        # is a narrowing, and CAC-AP-1 §2.4 wants every narrowing to name its declarer and its
        # date — otherwise a reader cannot tell "we judged this out of scope" from "nobody
        # asked". These carry that through to the skip record.
        "autonomyDeclaredBy": str(by or "").strip(),
        "autonomyDeclaredOn": utc_today(),
        # CAC-AP-1 §2.3. A declaration here outranks the org profile in both directions, and
        # absence is not a declaration — an empty dict means nothing has been narrowed.
        "declares": {},
        "dataClasses": [str(x).strip() for x in (data_classes or []) if str(x or "").strip()],
        "connectedResources": [str(x).strip() for x in (connected_resources or [])
                               if str(x or "").strip()],
        "consequentialDecision": bool(consequential),
        "supports": str(supports or "").strip(),
        # The cadence clock has to start somewhere. A deployment never assessed is measured
        # from the day it was recorded, not from nothing — otherwise the deployment nobody has
        # ever looked at is the one `assessment-overdue` stays silent about.
        "addedOn": utc_today(),
        "criticality": None,
        "exposure": {},
        "evidence": [],
        "proposals": [],
        "requirements": [],
        "assessments": [],
        "retired": None,
    }
    store["deployments"].append(rec)
    append_history(store, "deployment-added", rec["id"], by, why=rec["purpose"],
                   detail={"systemRef": system_ref, "autonomy": autonomy,
                           "owner": rec["owner"]})
    return rec


def autonomy_rank(value: str) -> int:
    if value not in AUTONOMY:
        raise Refusal("%r is not a declared autonomy level (%s)"
                      % (value, ", ".join(AUTONOMY)))
    return AUTONOMY.index(value)


def autonomy_warnings(rec: dict) -> list:
    """Things a declared autonomy implies that the record does not bear out.

    A warning rather than a refusal: the register records what somebody declared, and telling
    them their declaration looks inconsistent is useful, while refusing to store it would just
    mean the deployment goes unrecorded.
    """
    out = []
    if rec.get("autonomy") == "acts" and not (rec.get("connectedResources") or []):
        out.append(
            "%s is declared as acting without a person in the loop, but names no connected "
            "resources. Either it acts on something nobody has written down, or the autonomy "
            "is overstated — and the two need different fixes." % rec["id"])
    if rec.get("consequentialDecision") and autonomy_rank(rec.get("autonomy") or "informs") < \
            autonomy_rank("decides"):
        out.append(
            "%s is marked as making a consequential decision while declared only to %s. If a "
            "person genuinely decides, the flag is wrong; if they rubber-stamp, the autonomy "
            "is." % (rec["id"], rec.get("autonomy")))
    return out


# --- Criticality: mirrored from vendor-register, deliberately -----------------
#
# Same vocabulary, same properties, same refusals. A CISO who learned `untraced` in the
# third-party register must not meet a second word for it here, and an auditor comparing the
# two must not have to learn which one is which.
#
# MIRRORED, NOT IMPORTED. Every shipped script runs standalone — a skill directory is usable on
# its own — and CAC-AP-1 §2.6 makes the transport between skills data rather than an import.

def set_scale(store: dict, levels, version: str = "") -> list:
    levels = [str(x).strip() for x in levels if str(x or "").strip()]
    if len(levels) < 2:
        raise Refusal("a criticality scale needs at least two levels, lowest first")
    if UNTRACED in levels or UNCLASSIFIED in levels:
        raise Refusal(
            f"{UNTRACED!r} and {UNCLASSIFIED!r} are states, not levels, and must never be "
            f"members of the scale. If either were on it, a deployment nobody could trace "
            f"would take a position in a ranking it was never assigned.")
    if len(set(levels)) != len(levels):
        raise Refusal("a criticality scale cannot repeat a level")
    orphans = []
    for rec in store["deployments"]:
        conf = ((rec.get("criticality") or {}).get("confirmed") or {})
        val = conf.get("value")
        if val and val not in levels:
            orphans.append("%s (%s)" % (rec["id"], val))
    if orphans:
        raise Refusal(
            "changing the scale would orphan a confirmed level on: %s. These are not remapped, "
            "because remapping restates somebody's judgement in words they did not choose."
            % ", ".join(orphans))
    store["settings"]["criticalityScale"] = levels
    store["settings"]["scaleVersion"] = str(version or "").strip() or ("v%d" % (
        len(store["snapshots"]) + 2))
    append_history(store, "scale-set", "settings", why=", ".join(levels))
    return levels


def criticality_rank(store: dict, value: str) -> int:
    """Position on the configured scale, lowest first. RAISES on the two states.

    The single most important line in the file, and it is the same one as in
    `vendor-register`: one `sorted(key=rank)` placing `untraced` at the bottom would silently
    downgrade every deployment nobody could trace, and the resulting board table would look
    complete.
    """
    scale = store["settings"]["criticalityScale"]
    if value in (UNTRACED, UNCLASSIFIED):
        raise Refusal(
            f"{value!r} has no position on the criticality scale and must not be ordered "
            f"against one. It is a state, not a level: it says the walk did not reach a "
            f"declared criticality, which is a reason to look rather than a reason to rank.")
    if value not in scale:
        raise Refusal(f"{value!r} is not on this register's scale ({', '.join(scale)})")
    return scale.index(value)


def _norm(name: str) -> str:
    return re.sub(r"\s+", " ", str(name or "")).strip().casefold()


def context_workflow_for(context: dict, node: str):
    for wf in ((context or {}).get("crownJewels") or []):
        if _norm(wf.get("system")) == _norm(node):
            return wf
    return None


def context_parent_of(context: dict, node: str) -> str:
    for wf in ((context or {}).get("crownJewels") or []):
        for dep in (wf.get("dependsOn") or []):
            if _norm(dep) == _norm(node):
                return wf.get("system") or ""
    return ""


def derive_criticality(rec: dict, context: dict, max_hops: int = TRACE_MAX_HOPS):
    """Trace what this deployment supports up to a workflow with a declared criticality.

    Returns `(level_or_UNTRACED, trace_path, truncated)`. Bounded at two hops; a truncated walk
    yields `untraced` AND records `truncated`, never a confident level from an unfinished walk.
    With no context at all, everything derives `untraced` — correct and loud.
    """
    seen, path = set(), []
    node = str(rec.get("supports") or "").strip()
    for _hop in range(max(0, int(max_hops))):
        if not node or _norm(node) in seen:
            break
        seen.add(_norm(node))
        path.append(node)
        wf = context_workflow_for(context, node)
        if wf and str(wf.get("criticality") or "").strip():
            return str(wf["criticality"]).strip(), path, False
        node = context_parent_of(context, node)
    return UNTRACED, path, bool(node)


def classify(store: dict, did: str, context: dict = None, confirm: str = "",
             by: str = "", basis: str = "") -> dict:
    """Derive a criticality, and optionally record the level a person assigned.

    Derivation proposes; only `--confirm` with `--by` assigns. A confirmed level that differs
    from the derived one is stored without complaint and escalates as a conflict.
    """
    if confirm and not str(by or "").strip():
        raise Refusal(
            "--confirm needs --by: the name of the person assigning this level.\n"
            "  Derivation proposes and a person assigns. An unattributed final level cannot be "
            "defended by pointing at the tool that produced it.")
    scale = store["settings"]["criticalityScale"]
    if confirm and confirm not in scale:
        raise Refusal(f"{confirm!r} is not on this register's scale ({', '.join(scale)})")
    rec = find_deployment(store, did)
    hops = int(store["settings"].get("traceMaxHops") or TRACE_MAX_HOPS)
    level, path, truncated = derive_criticality(rec, context or {}, hops)
    block = rec.get("criticality") or {}
    block.update({"derived": level, "derivedOn": utc_today(), "trace": path,
                  "truncated": truncated, "derivedFromLevel": level})
    if confirm:
        block["confirmed"] = {"value": confirm, "by": by.strip(), "on": utc_today(),
                              "basis": str(basis or "").strip(),
                              "scaleVersion": store["settings"].get("scaleVersion") or "",
                              "againstDerived": level}
    else:
        block.setdefault("confirmed", None)
    rec["criticality"] = block
    append_history(store, "classified", did, by,
                   why=("confirmed %s" % confirm) if confirm else ("derived %s" % level),
                   detail={"derived": level, "trace": path, "truncated": truncated})
    return block


def criticality_of(rec: dict) -> str:
    block = rec.get("criticality") or {}
    conf = block.get("confirmed") or {}
    if conf.get("value"):
        return str(conf["value"])
    if block.get("derived"):
        return str(block["derived"])
    return UNCLASSIFIED


# --- NISTAML exposure ---------------------------------------------------------
#
# THE HEART OF THE FILE, and the two rules below are what make this an AI *security* register
# rather than a spreadsheet of tools.
#
# **Exposure is DERIVED from attributes, never selected.** There is no command to mark a class
# applicable or inapplicable, and that absence is deliberate: a hand-selectable list becomes a
# list somebody trims when it is inconvenient, and the class most likely to be trimmed is the
# one that took the longest to explain. Change the attributes and the exposure recomputes.
#
# **There is no closed state.** No `mitigated`, `resolved`, `closed` or `accepted` field on a
# class, and no command that sets one. The design records NIST's position that adversarial ML
# mitigations are empirical rather than guaranteed, that published defences have repeatedly
# been broken by adaptive attacks, and that the problem remains open. A register that let
# somebody tick a class as handled would be asserting exactly what the source declines to.
#
# Controls are recorded WITH EVIDENCE AND A DATE. A class with controls reads as *controls
# applied*, never as resolved. Where the organisation wants to accept the residual, that is an
# acceptance and belongs in `exceptions-register` — and the refusal here says so, because a
# refusal with nowhere to go just gets worked around.
#
# Sourcing: this follows the SHAPE of NIST's adversarial ML taxonomy (AI 100-2), which is not
# bundled in this repository. See `references/nistaml-exposure.md`.

NISTAML = {
    "01": "availability",
    "02": "integrity",
    "03": "privacy",
    "04": "misuse",
    "05": "supply-chain",
}

NISTAML_WHY = {
    "01": "an attacker degrading the service the deployment provides",
    "02": "an attacker causing the deployment to produce the output they choose",
    "03": "an attacker recovering data the deployment was trained on or has access to",
    "04": "an attacker using the deployment's own generative capability for their ends",
    "05": "compromise reaching the deployment through the model or its supply chain",
}

# The states a class may be in. Two, and there is no third — see the note above.
EXPOSURE_STATES = ("no-controls-recorded", "controls-recorded")

CLOSED_STATE_RE = re.compile(r"mitigat|resolv|closed|accepted|remediat|handled", re.I)
"""What a class must never be described as, in a key or a value.

Checked by `evals/no-closed-state.sh` behaviourally AND statically. Named here so the pattern
has one definition, and so a reader can see exactly which words this register refuses to apply
to an attack class.
"""


def applicable_classes(store: dict, rec: dict) -> dict:
    """Which NISTAML classes this deployment is exposed to, derived from its attributes.

    Every class is justified from something declared on the record, so a reader can always ask
    "why is this here" and get an answer that is not "somebody ticked it".
    """
    system = next((s for s in store["systems"] if s.get("id") == rec.get("systemRef")), {})
    gen = bool(system.get("genAI"))
    out = {}

    def add(code, why):
        out[code] = {"class": "NISTAML.%s" % code, "name": NISTAML[code],
                     "concern": NISTAML_WHY[code], "because": why}

    # Availability and integrity apply to any deployment. A model that can be degraded or
    # steered is every model; the question is only what that costs here.
    add("01", "any deployment can be degraded by an attacker who can reach it")
    add("02", "any model's output can be steered by an attacker who can shape its input")

    # Privacy: training data, retrieval, or reach into resources the model can read.
    privacy_why = []
    if rec.get("dataClasses"):
        privacy_why.append("it handles %s" % ", ".join(rec["dataClasses"]))
    if system.get("fineTuned"):
        privacy_why.append("the model was fine-tuned, so organisation data is in its weights")
    if system.get("retrievalAugmented"):
        privacy_why.append("retrieval puts organisation data in its context at run time")
    if rec.get("connectedResources"):
        privacy_why.append("it reaches %s" % ", ".join(rec["connectedResources"]))
    if privacy_why:
        add("03", "; ".join(privacy_why))

    # Misuse is a GENERATIVE concern. A predictive classifier has no generative capability for
    # an attacker to borrow, and asking about it would be noise in a register whose value is
    # that its questions are all live ones.
    if gen:
        add("04", "the deployment is generative, so its capability can be turned to an "
                  "attacker's purpose")

    # Supply chain applies wherever the model comes from outside — which is the join to
    # `vendor-register`, and the reason `arrangementRef` exists on the system.
    if str(system.get("provider") or "").strip().lower() not in ("", "in-house", "internal"):
        add("05", "the model comes from %s, so its provenance is somebody else's to assure"
                  % system.get("provider"))
    return out


def map_exposure(store: dict, did: str, by: str = "") -> dict:
    """Recompute a deployment's exposure from its current attributes.

    Idempotent, and called automatically wherever an attribute that feeds it changes. Existing
    controls are PRESERVED across a recompute: a control recorded against integrity is still a
    control that was applied, even if the class stopped being derivable — and losing that
    record would erase evidence somebody produced.
    """
    rec = find_deployment(store, did)
    derived = applicable_classes(store, rec)
    prior = rec.get("exposure") or {}
    fresh = {}
    for code, entry in derived.items():
        keep = (prior.get(entry["class"]) or {})
        fresh[entry["class"]] = {
            "class": entry["class"],
            "name": entry["name"],
            "concern": entry["concern"],
            "because": entry["because"],
            # Preserved, never reset by a recompute.
            "controls": list(keep.get("controls") or []),
        }
    # A class that stopped being derivable but carries controls is kept, marked as no longer
    # derived. Deleting it would throw away evidence; pretending it is still applicable would
    # be a different lie.
    for cls, keep in prior.items():
        if cls not in fresh and (keep.get("controls") or []):
            entry = dict(keep)
            entry["noLongerDerived"] = True
            fresh[cls] = entry
    rec["exposure"] = fresh
    append_history(store, "exposure-mapped", did, by,
                   why=", ".join(sorted(fresh)) or "no classes derived")
    return fresh


def exposure_state(entry: dict) -> str:
    """One of exactly two states. There is no third, by design."""
    return "controls-recorded" if (entry.get("controls") or []) else "no-controls-recorded"


def record_control(store: dict, did: str, cls: str, control: str, evidence: str,
                   on: str = "", by: str = "") -> dict:
    """Record a control applied against an attack class, with what shows it was applied.

    Refuses without evidence and a date. A control asserted with neither is indistinguishable
    from an intention, and this register's whole claim is that it can tell those apart.

    Note what this does NOT do: it does not close the class, reduce it, or mark it handled.
    """
    if not str(control or "").strip():
        raise Refusal("--control describes what was actually put in place")
    if not str(evidence or "").strip():
        raise Refusal(
            "--evidence is required: what shows this control is in place and working.\n"
            "  A control with no evidence is an intention. Recording one here would let a "
            "class read as attended to on the strength of somebody's memory.")
    rec = find_deployment(store, did)
    if cls not in (rec.get("exposure") or {}):
        known = ", ".join(sorted(rec.get("exposure") or {})) or "none derived yet"
        raise Refusal(
            "%s is not a class this deployment is exposed to (derived: %s).\n"
            "  Exposure is derived from attributes and cannot be selected by hand. If this "
            "class should apply, the attribute that would make it apply is what needs "
            "declaring." % (cls, known))
    entry = {"control": control.strip(), "evidence": evidence.strip(),
             "on": check_date(on, "--on") if on else utc_today(),
             "by": str(by or "").strip()}
    rec["exposure"][cls].setdefault("controls", []).append(entry)
    append_history(store, "control-recorded", did, by, why=control.strip(),
                   detail={"class": cls})
    return entry


def accept_exposure(*_args, **_kwargs):
    """Deliberately not implemented, and deliberately present so the refusal has a home.

    Somebody will look for this. The answer is that accepting a residual exposure is an
    acceptance — it needs an approver, a justification, an expiry and a re-validation act — and
    a register that grew a second, weaker version of that lifecycle would be the one people
    used, because it asks for less.
    """
    raise Refusal(
        "this register has no way to accept an exposure, and that is deliberate.\n"
        "  An attack class is not a finding that gets closed: the mitigations are empirical, "
        "published defences have been broken by adaptive attacks, and the problem is open. "
        "Recording controls is the most this register will say.\n"
        "  If the organisation wants to accept the residual, that is an ACCEPTANCE and belongs "
        "in `exceptions-register`, which will demand an approver, a justification, an expiry "
        "and a re-validation act. Reference the deployment id from the acceptance.")


# --- Batteries: what gets asked, and what narrows it --------------------------
#
# Mirrored from `vendor-register`'s shape — `{id, gvsc, nistaml, appliesWhen, questions[]}` —
# because the two registers are read by the same person and an auditor comparing them should
# not have to learn which one narrows how. The CAC-AP-1 rules are unchanged: absence applies
# the battery, a subject-level declaration outranks the profile in both directions, and every
# skip carries the flag, the declarer and the date.
#
# EVERY question asks for evidence with a date, never an attestation. "Do you test for prompt
# injection?" is worthless — everybody answers yes. "What is the most recent dated adversarial
# test of THIS deployment, and what did it find?" has a discoverable answer, a date, and
# degrades honestly when the answer is "none". `evals/questions.sh` fails the attestation
# shapes, so this is enforced rather than remembered.
#
# The set is deliberately small. The valuable output is not a question bank; it is what the
# provider's own documentation left open, which means the set has to be short enough that
# subtracting from it produces something a person will actually send.
#
# Each battery names the NISTAML classes its questions bear on, so a reader can see the line
# from an attack class to the thing being asked about it. `nistamlDerived` gates a battery on
# a class the engine DERIVED — the questions follow the exposure rather than re-deriving it,
# which means there is still exactly one place that decides what a deployment is exposed to.

BATTERIES = (
    {
        "id": "inventory",
        "gvsc": ["ID.AM-02", "GV.SC-04"],
        "nistaml": ["05"],
        "appliesWhen": {},
        "questions": (
            {"id": "provenance",
             "ask": "What dated record states which model this deployment calls, at which "
                    "version, and when was it last checked against what is actually "
                    "configured?"},
            {"id": "change-notice",
             "ask": "What dated commitment or configuration tells us BEFORE the model behind "
                    "this deployment changes, and when did it last do so?"},
        ),
    },
    {
        "id": "access-and-data",
        "gvsc": ["PR.AA-05", "PR.DS-01"],
        "nistaml": ["03"],
        "appliesWhen": {},
        "questions": (
            {"id": "entitlements",
             "ask": "What dated evidence shows which identities and resources this deployment "
                    "can reach, and when was that list last reviewed?"},
            {"id": "training-use",
             "ask": "What dated commitment or configuration evidence shows whether our inputs "
                    "are used to train, fine-tune or otherwise improve the provider's model?"},
        ),
    },
    {
        "id": "adversarial-testing",
        "gvsc": ["ID.RA-01", "ID.IM-02"],
        "nistaml": ["02", "04"],
        # Gated on a RECORDED ATTRIBUTE of the system, not on a declaration. See
        # `_battery_applies`: a profile cannot narrow this away, and that is deliberate.
        "appliesWhen": {"genAI": True},
        "questions": (
            {"id": "red-team",
             "ask": "What is the most recent dated adversarial test of THIS deployment — "
                    "prompt injection, jailbreak, exfiltration through its own output — and "
                    "what did it find?"},
            {"id": "untrusted-input",
             "ask": "What dated evidence shows what happens when content the organisation "
                    "does not control reaches this deployment's context, and who produced it?"},
        ),
    },
    {
        "id": "monitoring",
        "gvsc": ["DE.CM-09"],
        "nistaml": ["01", "02"],
        "appliesWhen": {},
        "questions": (
            {"id": "output-retention",
             "ask": "What dated record shows this deployment's inputs and outputs are "
                    "retained, for how long, and who can read them?"},
            {"id": "degradation",
             "ask": "What dated evidence shows how we would know this deployment had started "
                    "behaving differently, and when that last happened?"},
        ),
    },
    {
        "id": "supply-chain",
        "gvsc": ["GV.SC-07", "ID.RA-09"],
        "nistaml": ["05"],
        # Follows the derived exposure. If NISTAML.05 applies, these questions are live.
        "appliesWhen": {"nistamlDerived": "NISTAML.05"},
        "questions": (
            {"id": "provider-assurance",
             "ask": "What is the most recent independent assurance report covering the service "
                    "that runs this model, what period does it cover, and what did it exclude?"},
            {"id": "arrangement-link",
             "ask": "Which arrangement in the third-party register covers this provider, and "
                    "what dated document commits them to telling us about a security incident?"},
        ),
    },
    {
        "id": "autonomy-controls",
        "gvsc": ["PR.AA-05"],
        "nistaml": ["02"],
        # `decides` and above. A deployment that only informs has a person between its output
        # and any consequence, and asking these of it produces paperwork rather than answers.
        "appliesWhen": {"autonomyAtLeast": "decides"},
        "questions": (
            {"id": "human-review",
             "ask": "What dated evidence shows what a person can see, and can override, before "
                    "this deployment's output takes effect?"},
            {"id": "blast-radius",
             "ask": "What dated record bounds what this deployment can do to the resources it "
                    "reaches, and when was that boundary last tested rather than documented?"},
        ),
    },
    {
        "id": "regulated-data",
        "gvsc": ["PR.DS-01", "GV.SC-05"],
        "nistaml": ["03"],
        # A CAC-AP-1 flag, declarable on the deployment or on the org profile. `regulatedDataHeld`
        # is a `business-context` known flag, not a word invented here.
        "appliesWhen": {"flag": "regulatedDataHeld"},
        "questions": (
            {"id": "class-boundary",
             "ask": "What dated evidence shows which regulated data classes can reach this "
                    "deployment, and what stops the ones that should not?"},
            {"id": "retention",
             "ask": "What dated record states how long the provider keeps this deployment's "
                    "prompts, outputs and any retrieved content, and where is that written?"},
        ),
    },
    {
        "id": "withdrawal",
        "gvsc": ["GV.SC-10", "ID.AM-08"],
        "nistaml": ["01"],
        # Top of the scale only. A withdrawal plan for a marketing drafting assistant is
        # paperwork; for the model inside a consequential decision it is the whole question.
        "appliesWhen": {"criticalityAtLeast": "TOP"},
        "questions": (
            {"id": "version-withdrawn",
             "ask": "What is the dated record of what happens to this deployment and the "
                    "process behind it if the provider withdraws the version we use?"},
            {"id": "data-return",
             "ask": "What evidence would show our inputs and any fine-tuning data had been "
                    "returned and then deleted, and how long would producing it take?"},
        ),
    },
)


def question_key(battery: dict, question: dict) -> str:
    return "%s.%s" % (battery["id"], question["id"])


def all_questions(batteries=None) -> list:
    out = []
    for battery in (batteries if batteries is not None else BATTERIES):
        for q in battery["questions"]:
            out.append((battery, q))
    return out


def _declared(rec: dict, flag: str):
    """(value, declaredBy, declaredOn) for a deployment-level declaration. `None` is not False."""
    subject = (rec.get("declares") or {}).get(flag)
    if isinstance(subject, dict):
        return (subject.get("value"), subject.get("declaredBy", ""),
                subject.get("declaredOn", ""))
    return subject, "", ""


def _battery_applies(battery: dict, rec: dict, store: dict, context: dict):
    """(applies, skip_record_or_None). CAC-AP-1 narrowing, mirrored rather than re-derived.

    §2.2 — a missing criticality, a missing flag or an undeclared anything means NOT DECLARED,
    so the battery APPLIES. Absence asks more. The deployment nobody classified is exactly the
    one that must not be quietly treated as low-risk.

    §2.3 — a declaration on the deployment outranks the org profile IN BOTH DIRECTIONS.

    §2.4 — every skip carries the flag, the declarer and the date, so a reader can tell "we
    judged this out of scope, here is who said so" from "nobody asked".
    """
    cond = battery.get("appliesWhen") or {}

    if "criticalityAtLeast" in cond:
        level = criticality_of(rec)
        # Neither state is a level, so neither can narrow anything — and the deployment nobody
        # could place is the one worth asking every question of. Kept explicitly, even though
        # the `level in scale` test below also excludes both, because the obvious future edit
        # is to compare with `criticality_rank`, which RAISES on these rather than returning a
        # number, and a reader needs to know that is deliberate before working out why.
        if level in (UNTRACED, UNCLASSIFIED):
            return True, None
        scale = store["settings"]["criticalityScale"]
        conf = ((rec.get("criticality") or {}).get("confirmed") or {})
        if cond["criticalityAtLeast"] == "TOP" and level in scale:
            if scale.index(level) < len(scale) - 1:
                return False, {
                    "battery": battery["id"],
                    "reason": "criticality %r is below the top of the scale (%s)"
                              % (level, scale[-1]),
                    "flag": "criticality",
                    "declaredBy": conf.get("by", ""),
                    "declaredOn": conf.get("on", ""),
                }
        return True, None

    if "autonomyAtLeast" in cond:
        declared = rec.get("autonomy") or ""
        if declared not in AUTONOMY:
            # Undeclared autonomy cannot narrow anything. `deploy` refuses one, so this is the
            # store that was hand-edited — and the safe direction is to ask.
            return True, None
        if autonomy_rank(declared) < autonomy_rank(cond["autonomyAtLeast"]):
            return False, {
                "battery": battery["id"],
                "reason": "autonomy %r is below %r" % (declared, cond["autonomyAtLeast"]),
                "flag": "autonomy",
                "declaredBy": rec.get("autonomyDeclaredBy", ""),
                "declaredOn": rec.get("autonomyDeclaredOn", ""),
            }
        return True, None

    if "genAI" in cond:
        # An ATTRIBUTE gate, not a declaration gate, and the difference matters. Whether a
        # system is generative is a recorded fact about what is in the inventory; the profile
        # flag `aiInUse` answers a different question — whether this organisation uses AI at
        # all — and a deployment sitting in this register has already answered that. So a
        # profile saying false does NOT narrow this away, and the self-test asserts it.
        system = next((s for s in store["systems"] if s.get("id") == rec.get("systemRef")), {})
        value, by, on = _declared(rec, "genAI")
        if value is None:
            value = bool(system.get("genAI"))
        if bool(value) == bool(cond["genAI"]):
            return True, None
        return False, {
            "battery": battery["id"],
            "reason": "the system is recorded as %s"
                      % ("generative" if value else "predictive, not generative"),
            "flag": "genAI",
            "declaredBy": by or ("the system record %s" % (system.get("id") or "?")),
            "declaredOn": on or "",
        }

    if "hosting" in cond:
        system = next((s for s in store["systems"] if s.get("id") == rec.get("systemRef")), {})
        allowed = list(cond["hosting"])
        where = str(system.get("hosting") or "")
        if not where or where in allowed:
            return True, None
        return False, {"battery": battery["id"],
                       "reason": "hosting is %r, and this asks only of %s"
                                 % (where, ", ".join(allowed)),
                       "flag": "hosting",
                       "declaredBy": "the system record %s" % (system.get("id") or "?"),
                       "declaredOn": ""}

    if "nistamlDerived" in cond:
        # Follows the derived exposure rather than re-deriving it. One place decides what a
        # deployment is exposed to, and this reads that decision.
        exposure = rec.get("exposure") or {}
        if cond["nistamlDerived"] in exposure:
            return True, None
        return False, {"battery": battery["id"],
                       "reason": "%s is not among the classes derived for this deployment"
                                 % cond["nistamlDerived"],
                       "flag": "exposure",
                       "declaredBy": "derived from the recorded attributes",
                       "declaredOn": ""}

    if "flag" in cond:
        flag = cond["flag"]
        sub_val, sub_by, sub_on = _declared(rec, flag)
        if sub_val is True:
            return True, None
        if sub_val is False:
            return False, {"battery": battery["id"],
                           "reason": "the deployment declares %s false" % flag,
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


def batteries_for(rec: dict, store: dict, context: dict = None) -> dict:
    """Which batteries apply to this deployment, and which were skipped and why."""
    applied, skipped = [], []
    for battery in BATTERIES:
        yes, skip = _battery_applies(battery, rec, store, context or {})
        if yes:
            applied.append(battery)
        elif skip:
            skipped.append(skip)
    return {"applied": applied, "skipped": skipped}


def declare_on_deployment(store: dict, did: str, flag: str, value, by: str,
                          basis: str = "") -> dict:
    """Record a CAC-AP-1 declaration on a deployment. §2.3: it outranks the org profile.

    Refuses without `--by`. A narrowing nobody signed is the shape of a scope decision that
    turns out, later, to have been nobody's.
    """
    if not str(flag or "").strip():
        raise Refusal("--flag names what is being declared")
    if not str(by or "").strip():
        raise Refusal(
            "--by is required: declaring a flag narrows what this register asks, and a "
            "narrowing with nobody's name on it cannot be defended later.")
    rec = find_deployment(store, did)
    entry = {"value": value, "declaredBy": by.strip(), "declaredOn": utc_today(),
             "basis": str(basis or "").strip()}
    rec.setdefault("declares", {})[flag.strip()] = entry
    append_history(store, "declared", did, by, why="%s = %r" % (flag.strip(), value))
    return entry


# --- Evidence tiers -----------------------------------------------------------
#
# Mirrored from `vendor-register`, down to the constant names, because the hierarchy is about
# ASSESSMENT RIGOUR and not about how much a provider is trusted — and that is the same
# judgement in both registers.
#
#   T1  an audited artifact — an independent model evaluation, an AI red-team report by a
#       party that does not report to the team that built it, a penetration test of the
#       deployment, a regulatory examination finding. Somebody independent looked, and
#       recorded what they looked at and when.
#   T2  a contractual commitment — an executed DPA, a clause in the signed agreement, a
#       written no-training-on-our-data commitment. Not a demonstration, but an obligation
#       with a remedy behind it.
#   T3  an assertion — a model card, a system card, a completed questionnaire, the provider's
#       own evaluation results, our own DPIA. The party describing itself.
#   T4  public copy — a trust page, a product blog, marketing material.
#
# **A model card is T3, and this is the tier judgement most likely to be got wrong.** It is
# the most substantive-looking artifact in the whole AI supply chain: structured, technical,
# full of numbers, often the only thing a provider publishes. Nobody independent produced it,
# nothing in it is an obligation with a remedy behind it, and the evaluations it reports were
# chosen by the party being evaluated. It is genuinely useful for working out what to ASK, and
# it is never a reason to stop asking.

TIERS = ("T1", "T2", "T3", "T4")

SATISFYING_TIERS = ("T1", "T2")
"""The only tiers that may close a requirement.

Referenced everywhere and never inlined, so the rule has exactly one definition to change and
one place to argue with. `evals/proposal-boundary.sh` proves no code path gets around it.
"""

TIER_LABEL = {
    "T1": "audited artifact",
    "T2": "contractual commitment",
    "T3": "an assertion by the party being described",
    "T4": "public copy",
}

TIER_CEILING = {
    # kind -> the best tier it can honestly be recorded at, and why.
    "model-card": ("T3", "a model card is the provider describing its own model: nobody "
                         "independent produced it, and nothing in it is an obligation with a "
                         "remedy behind it"),
    "system-card": ("T3", "a system card is the provider describing its own system"),
    "provider-evaluation": ("T3", "an evaluation run by the party being evaluated, which "
                                  "chose what to evaluate"),
    "questionnaire": ("T3", "the provider answering our questions about itself"),
    "dpia": ("T3", "our own documented assessment — a considered one, and still ours"),
    "trust-page": ("T4", "public copy, which changes without notice"),
    "product-blog": ("T4", "marketing material"),
}
"""Kinds that cannot be recorded above a stated tier, with the reason in the refusal.

This is a ceiling and not a mapping: a third-party model evaluation may be T1, and the same
words describe an internal one that is T3, so most kinds are left to the person recording
them. These seven are the ones where the tier is not a judgement call and where getting it
wrong would let an assertion close a requirement.
"""

EVIDENCE_ID_RE = re.compile(r"^EV-\d{3,}$")
PROPOSAL_ID_RE = re.compile(r"^PR-\d{3,}$")


def _next_sub_id(rec: dict, key: str, prefix: str, pattern) -> str:
    used = [int(x["id"].split("-")[1]) for x in (rec.get(key) or [])
            if pattern.match(str(x.get("id", "")))]
    return "%s-%03d" % (prefix, (max(used) + 1) if used else 1)


def ingest(store: dict, did: str, kind: str, tier: str, source: str, scope: str = "",
           period_start: str = "", period_end: str = "", url: str = "",
           retrieved: str = "", by: str = "") -> dict:
    """Record an artifact about this deployment, with the tier that says what it can close.

    **Scope and period are required for T1.** An artifact whose limits are not written down
    gets read as though it had none: a penetration test that covered the API and not the
    retrieval path has not covered the retrieval path, and a report with no period cannot
    expire — it would sit here looking like current assurance forever.

    Anything fetched from a URL needs `--retrieved`. A provider's published claims change
    without notice, and an undated capture is a claim about a page that may no longer say it.
    """
    if tier not in TIERS:
        raise Refusal("--tier must be one of %s; got %r" % (", ".join(TIERS), tier))
    if not str(kind or "").strip():
        raise Refusal("--kind names what the artifact is (model-card, red-team-report, "
                      "penetration-test, dpa, ...)")
    if not str(source or "").strip():
        raise Refusal("--source says where this came from. An artifact with no provenance "
                      "cannot be re-found by the person who has to check it.")
    ceiling = TIER_CEILING.get(str(kind or "").strip().lower())
    if ceiling and TIERS.index(tier) < TIERS.index(ceiling[0]):
        raise Refusal(
            "a %r cannot be recorded as %s; %s is the most it can be.\n"
            "  %s. That makes it genuinely useful for working out what to ASK, and never a "
            "reason to stop asking — only %s can close anything here."
            % (kind, tier, ceiling[0], ceiling[1][0].upper() + ceiling[1][1:],
               " or ".join(SATISFYING_TIERS)))
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
                "its scope and period. A red-team report that exercised the chat surface and "
                "not the tool-calling path has not covered the tool-calling path; a report "
                "with no period cannot expire, so it would sit here looking like current "
                "assurance forever." % " and ".join(missing))
    if str(url or "").strip() and not str(retrieved or "").strip():
        raise Refusal(
            "evidence with a --url needs --retrieved.\n"
            "  A provider's published claims change without notice. An undated capture is a "
            "claim about a page that may no longer say it, and nobody can check which.")
    rec = find_deployment(store, did)
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
    append_history(store, "evidence-ingested", did, by,
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


# --- The Layer A / Layer B boundary -------------------------------------------
#
# The same safety property as `vendor-register`, and it matters more here, because the
# artifacts a model provider publishes are unusually persuasive. A model card is structured,
# technical and full of measured numbers, and a model reading one and ticking requirements
# would produce a register full of green derived from a document the provider wrote about
# itself — worse than an empty register, because it LOOKS FINISHED. Nobody re-checks a page
# of ticks.
#
# Two refusals hold the line:
#   1. `propose` refuses without a citation. A proposal with no citation is an opinion.
#   2. `propose` refuses to cite T3 or T4 AT ALL.

def propose(store: dict, did: str, requirement: str, evidence_ref: str, citation: str,
            note: str = "", by: str = "") -> dict:
    """Layer A's output: a reading, with its receipt. Satisfies nothing."""
    if not str(requirement or "").strip():
        raise Refusal("--requirement names what this proposal claims to cover")
    if not str(citation or "").strip():
        raise Refusal(
            "--citation is required: the passage or document reference this reading rests on.\n"
            "  A proposal with no citation is an opinion. The person who confirms it has to be "
            "able to go and read the same thing.")
    rec = find_deployment(store, did)
    ev = find_evidence(rec, evidence_ref)
    if ev["tier"] not in SATISFYING_TIERS:
        raise Refusal(
            "%s is %s (%s), which can never satisfy a requirement.\n"
            "  Only %s can — something independently looked at, or something actually signed. "
            "A model card is the most persuasive artifact in this whole supply chain and it is "
            "still the provider describing itself: useful for working out what to ASK, never a "
            "reason to stop asking."
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
    append_history(store, "proposed", did, by, why=entry["requirement"],
                   detail={"proposalId": entry["id"], "evidenceRef": evidence_ref})
    return entry


def find_proposal(rec: dict, pid: str) -> dict:
    for pr in (rec.get("proposals") or []):
        if pr.get("id") == pid:
            return pr
    known = ", ".join(x.get("id", "?") for x in (rec.get("proposals") or [])) or "none"
    raise Refusal("no proposal %r on %s (known: %s)" % (pid, rec["id"], known))


def assess(store: dict, did: str, by: str, on: str = "", confirm=None, reject=None,
           why: str = "", note: str = "") -> dict:
    """Layer B: a named person rules on proposals, and the assessment clock resets.

    This is the act that writes the `assessments` list the cadence reads. Refuses without
    `--by` — an unattributed assessment is exactly what this boundary exists to prevent, and
    it is what an assessor will ask for first.

    Rejected proposals are RETAINED. Keeping one records that a claim was examined and not
    accepted; deleting it would leave no trace that anybody looked.
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
    rec = find_deployment(store, did)
    on = check_date(on, "--on") if on else utc_today()
    system = next((s for s in store["systems"] if s.get("id") == rec.get("systemRef")), {})
    confirmed_ids, rejected_ids = [], []
    for pid in list(confirm or []):
        pr = find_proposal(rec, pid)
        ev = find_evidence(rec, pr["evidenceRef"])
        # Belt and braces: `propose` already refuses these tiers, so a T3 reaching here means
        # a proposal was written some other way, and this is the last gate before a tick.
        if ev["tier"] not in SATISFYING_TIERS:
            raise Refusal(
                "%s cites %s, which is %s and can never satisfy a requirement."
                % (pid, pr["evidenceRef"], TIER_LABEL[ev["tier"]]))
        pr["status"] = "confirmed"
        pr["confirmedBy"] = by.strip()
        pr["confirmedOn"] = on
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
    entry = {
        "on": on, "by": by.strip(), "confirmed": confirmed_ids, "rejected": rejected_ids,
        "note": str(note or "").strip(),
        # WHAT WAS ASSESSED, not just when. A silent model swap is the event that invalidates
        # an assessment, and comparing today's system against the one that was actually in
        # front of the assessor is the only way to notice. `model-changed` reads these.
        "againstSystem": {
            "systemRef": rec.get("systemRef") or "",
            "version": system.get("version") or "",
            "baseModel": system.get("baseModel") or "",
            "hosting": system.get("hosting") or "",
        },
        "againstAutonomy": rec.get("autonomy") or "",
        "againstConnectedResources": sorted(rec.get("connectedResources") or []),
    }
    rec.setdefault("assessments", []).append(entry)
    append_history(store, "assessed", did, by,
                   why=note or ("%d confirmed, %d rejected"
                                % (len(confirmed_ids), len(rejected_ids))),
                   detail={"confirmed": confirmed_ids, "rejected": rejected_ids})
    return entry


def open_proposals(rec: dict) -> list:
    """The working view: what is still awaiting a person. Rejections are kept, not shown."""
    return [pr for pr in (rec.get("proposals") or []) if pr.get("status") == "proposed"]


def record_requirement(store: dict, did: str, requirement: str, evidence: str,
                       met: bool = True, by: str = "") -> dict:
    """Record a requirement checked directly, met or not met.

    A Layer B act, like `assess`, and held to the same standard: a named person, and a
    reference to what they actually read. `--by` is required from the first version here
    rather than added later, because `vendor-register` shipped the equivalent act without it
    and a requirement could be marked met with nobody's name against it — a hole in the "only
    a named person closes anything" claim, found by a static scan rather than by review.

    A requirement recorded NOT met is what `export-findings` carries to `risk-register`.
    """
    if not str(requirement or "").strip():
        raise Refusal("--requirement names what is being checked")
    if not str(evidence or "").strip():
        raise Refusal(
            "--evidence must reference what was actually read.\n"
            "  A requirement marked met with no evidence reference is an assertion about "
            "something nobody opened, and it reads identically to one that was checked.")
    if not str(by or "").strip():
        raise Refusal(
            "--by is required: the person who checked.\n"
            "  Recording a requirement met is closing it, and only a named person closes "
            "anything here. Recording one NOT met opens a candidate risk in another register, "
            "and that needs a name on it just as much.")
    rec = find_deployment(store, did)
    entry = {"requirement": requirement.strip(), "evidence": evidence.strip(),
             "met": bool(met), "checkedOn": utc_today(), "checkedBy": by.strip()}
    rec.setdefault("requirements", []).append(entry)
    append_history(store, "requirement-recorded", did, by,
                   why="%s: %s" % (requirement.strip(), "met" if met else "NOT met"))
    return entry


# --- Generated questions ------------------------------------------------------
#
# Take the batteries the gates left applicable, subtract what T1 and T2 evidence genuinely
# covers, and emit WHAT REMAINS OPEN. A full battery is simply the degenerate case where
# nothing was supplied — same code path, no special casing.
#
# T3 and T4 subtract NOTHING, and here that is the entire product claim: the artifact a model
# provider is most likely to hand over is a model card, and a register that let one close
# questions would go quiet exactly where it should be loudest.

NOTHING_OPEN = ("Nothing is open for this deployment at its current criticality and autonomy. "
                "Every applicable question is covered by evidence that can satisfy it.")
"""Printed when the subtraction leaves nothing.

An empty result must never be an empty string. A blank page and "we have asked everything and
it is all evidenced" look identical on a screen and mean opposite things, and the blank one is
the one somebody forwards as though it were the second.
"""


def ask(store: dict, did: str, context: dict = None, today: str = "") -> dict:
    """What is still worth asking about this deployment, and why each question is being asked.

    A question survives when nothing that CAN satisfy it does. A question whose requirement is
    covered by evidence that has slipped into grace is still emitted, marked `re-confirm`
    rather than `open`: the answer was good and is ageing, which is a different request from
    one nobody has ever answered.
    """
    today = today or utc_today()
    rec = find_deployment(store, did)
    grace = int(store["settings"].get("evidenceGraceDays") or 365)
    narrowed = batteries_for(rec, store, context or {})

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
        # The tier rule is READ OFF `SATISFYING_TIERS` rather than re-implemented, so there is
        # one definition of what may close anything.
        if not ev or ev["tier"] not in SATISFYING_TIERS:
            continue
        status = evidence_status(ev, today, grace)
        if status == "expired":
            continue          # covered by something that has run out is not covered
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
            "nistaml": ["NISTAML.%s" % c for c in (battery.get("nistaml") or [])],
        }
        if hit is None:
            entry["status"] = "open"
            entry["why"] = "no evidence that can satisfy this has been recorded"
            questions.append(entry)
        elif hit["status"] == "in-grace":
            entry["status"] = "re-confirm"
            entry["why"] = ("covered by %s (%s), whose period ended %s and is now in grace"
                            % (hit["evidence"]["id"], hit["evidence"]["kind"],
                               hit["evidence"]["periodEnd"]))
            reconfirm.append(entry)
    out = {
        "deployment": did,
        "asOf": today,
        "criticality": criticality_of(rec),
        "autonomy": rec.get("autonomy") or "",
        "questions": questions + reconfirm,
        "open": len(questions),
        "reConfirm": len(reconfirm),
        "skipped": narrowed["skipped"],
        "batteriesApplied": [b["id"] for b in narrowed["applied"]],
    }
    if not out["questions"]:
        out["note"] = NOTHING_OPEN
    return out


# --- Escalations (CAC-EL-1 §1.3) ----------------------------------------------
#
# `subjectKind` is `deployment`, because that is where risk lives here. Derived on every run,
# never stored, and nothing blocks: a register full of escalations still loads, still
# classifies, still renders.
#
# Three of these fire at EVERY criticality level, including the lowest, and that is the design
# decision worth arguing with rather than a missing filter:
#
#   model-changed          the model under a deployment was swapped
#   base-model-changed     what it is BUILT ON was swapped, product version unchanged
#   unsanctioned-in-use    something nobody approved is in production
#
# A silent model swap is precisely the event that makes a low-criticality deployment stop
# being low. `low` has no cadence by design, so if these were gated on criticality nothing
# would ever look at the deployments most likely to change without anybody noticing.

ESCALATION_SEVERITY_ORDER = ["critical", "high", "medium"]


def _cadence_days(store: dict, level: str):
    """None means no cadence for this level — a decision, not an oversight.

    `low` has no interval. The always-fire triggers above are what catch a low-criticality
    deployment that quietly stopped being low.
    """
    return (store["settings"].get("cadenceDays") or {}).get(level)


def _last_assessment(rec: dict) -> dict:
    dated = [a for a in (rec.get("assessments") or []) if a.get("on")]
    return max(dated, key=lambda a: a["on"]) if dated else {}


def _last_assessed(rec: dict) -> str:
    return _last_assessment(rec).get("on") or ""


def escalations(store: dict, today: str = "") -> list:
    today = today or utc_today()
    out = []

    def add(trigger, rec, severity, since, evidence):
        out.append({"trigger": trigger, "subjectKind": "deployment",
                    "subjectRef": rec["id"], "severity": severity,
                    "since": since or today, "evidence": evidence})

    for rec in store["deployments"]:
        if rec.get("retired"):
            continue
        system = next((s for s in store["systems"] if s.get("id") == rec.get("systemRef")), {})
        block = rec.get("criticality") or {}
        level = criticality_of(rec)
        last = _last_assessment(rec)
        consequential = (rec.get("consequentialDecision")
                         or (rec.get("autonomy") in AUTONOMY
                             and autonomy_rank(rec["autonomy"]) >= autonomy_rank("decides")))

        # --- the same two words as vendor-register, with the same meanings ----
        if level == UNCLASSIFIED:
            add("unclassified", rec, "high", "",
                "no criticality has been derived or assigned, so this deployment is asked "
                "the full question set and nobody has been told")
        elif level == UNTRACED:
            add("untraced", rec, "high", block.get("derivedOn") or "",
                "the trace could not reach a workflow with a declared criticality%s. This is "
                "not low criticality; it is an unanswered question about what this deployment "
                "holds up"
                % (" and stopped with more chain to follow" if block.get("truncated") else ""))

        # --- exposure with nothing recorded against it ------------------------
        #
        # ONE escalation per deployment naming every uncontrolled class, rather than one per
        # class. A newly recorded deployment derives five classes and has controls against
        # none of them; five rows would say the same thing five times and bury the deployment
        # that has four of five covered.
        uncontrolled = sorted(cls for cls, entry in (rec.get("exposure") or {}).items()
                              if not (entry.get("controls") or [])
                              and not entry.get("noLongerDerived"))
        if uncontrolled:
            add("attack-class-uncontrolled", rec,
                "high" if consequential else "medium", "",
                "%s %s no control recorded against %s. Recording one does not close the "
                "class — there is no closed state here — but nothing at all recorded is a "
                "different fact"
                % (", ".join(uncontrolled), "has" if len(uncontrolled) == 1 else "have",
                   "it" if len(uncontrolled) == 1 else "them"))

        # --- what changed under an assessment ---------------------------------
        prior = last.get("againstSystem") or {}
        if last:
            if prior.get("systemRef") and prior["systemRef"] != rec.get("systemRef"):
                add("model-changed", rec, "high", last.get("on") or "",
                    "the deployment now uses %s; it was assessed against %s on %s"
                    % (rec.get("systemRef"), prior["systemRef"], last.get("on")))
            elif prior.get("version") and prior["version"] != (system.get("version") or ""):
                add("model-changed", rec, "high", last.get("on") or "",
                    "%s is now version %s; the assessment on %s was made against %s. Every "
                    "answer in it was about a different model"
                    % (system.get("id") or rec.get("systemRef"), system.get("version"),
                       last.get("on"), prior["version"]))
            elif prior.get("hosting") and prior["hosting"] != (system.get("hosting") or ""):
                add("model-changed", rec, "high", last.get("on") or "",
                    "hosting moved from %s to %s since the assessment on %s"
                    % (prior["hosting"], system.get("hosting"), last.get("on")))

            # Separate from the above, and deliberately: a provider re-basing a product on a
            # different foundation model without changing its version number is the change
            # that nothing else in this file would notice.
            now_base = str(system.get("baseModel") or "")
            was_base = str(prior.get("baseModel") or "")
            if now_base and now_base != was_base:
                add("base-model-changed", rec, "high", last.get("on") or "",
                    ("the disclosed base model is now %s; the assessment on %s was made "
                     "against %s, with the product version unchanged at %s"
                     % (now_base, last.get("on"), was_base, system.get("version") or "?"))
                    if was_base else
                    ("the disclosed base model is %s; the assessment on %s was made when the "
                     "provider had disclosed none, so nobody looked at what this is built on"
                     % (now_base, last.get("on"))))

            was_autonomy = str(last.get("againstAutonomy") or "")
            now_autonomy = str(rec.get("autonomy") or "")
            if was_autonomy in AUTONOMY and now_autonomy in AUTONOMY \
                    and autonomy_rank(now_autonomy) > autonomy_rank(was_autonomy):
                add("autonomy-increased", rec, "high", last.get("on") or "",
                    "autonomy rose from %s to %s since the assessment on %s"
                    % (was_autonomy, now_autonomy, last.get("on")))
            else:
                was_res = set(last.get("againstConnectedResources") or [])
                now_res = set(rec.get("connectedResources") or [])
                grew = sorted(now_res - was_res)
                if grew:
                    add("autonomy-increased", rec, "medium", last.get("on") or "",
                        "it now reaches %s, which it did not when it was assessed on %s"
                        % (", ".join(grew), last.get("on")))

        # --- cadence ----------------------------------------------------------
        #
        # `untraced` satisfies NO cadence rule — there is no level to look one up for, and
        # treating it as "no cadence applies" would make it quieter than `low`.
        if level not in (UNTRACED, UNCLASSIFIED):
            cadence = _cadence_days(store, level)
            since = _last_assessed(rec) or str(rec.get("addedOn") or "")
            if cadence and since and days_between(since, today) > int(cadence):
                add("assessment-overdue", rec, "high", since,
                    "last assessed %s; cadence for %s is %d days"
                    % (_last_assessed(rec) or "never (dated from when it was recorded)",
                       level, int(cadence)))

        # --- facts about the record itself ------------------------------------
        if not str(rec.get("owner") or "").strip():
            add("unowned", rec, "high", "",
                "no owner is recorded. `deploy` refuses one without an owner, so this row "
                "was written some other way — and every escalation above has nobody to land on")

        provider = str(system.get("provider") or "").strip().lower()
        external = provider not in ("", "in-house", "internal")
        if external and system.get("hosting") in ("saas", "hybrid") \
                and not str(system.get("arrangementRef") or "").strip():
            add("provider-arrangement-missing", rec, "medium", "",
                "%s runs on %s's infrastructure and names no arrangement in the third-party "
                "register. The contractual questions this raises — incident notice, "
                "subprocessors, exit — are asked there, of the provider, not here"
                % (system.get("id") or "the system", system.get("provider")))

        # Fires at every level, including the lowest.
        if system.get("sanction") == "unsanctioned":
            add("unsanctioned-in-use", rec, "critical" if consequential else "high", "",
                "%s is recorded as unsanctioned and has a live deployment%s. Somebody is "
                "using it either way; the only question is whether the organisation knows "
                "what it agreed to"
                % (system.get("id") or "the system",
                   " making a consequential decision" if consequential else ""))

    order = {s: i for i, s in enumerate(ESCALATION_SEVERITY_ORDER)}
    out.sort(key=lambda e: (order.get(e["severity"], 99), e["subjectRef"], e["trigger"]))
    return out


# --- Regimes as dated data ----------------------------------------------------
#
# **This ships with no regime content, and that is a decision rather than an unfinished job.**
# The mechanism is here, the gate that keeps it honest is here, and `references/regimes.json`
# carries an empty list.
#
# The reason is the one `vendor-register`'s `references/overlays.md` gives at length. A regime
# obligation is the only thing this skill would say that is about what a THIRD PARTY — a
# regulator — requires of the reader. Every other claim here is about their own register: what
# they recorded, what they checked, what is overdue. Asserting an obligation the tool cannot
# cite to primary text is worse than staying quiet, because a reader cannot tell a checked
# claim from a plausible one and will act on both.
#
# Two things make the AI case sharper than the third-party one:
#
#   1. `aiRole` is the decisive gate. Much of what these regimes say is addressed to PROVIDERS
#      of AI systems, and a firm that buys and deploys one is usually a deployer. Conflating
#      the two fills a register with obligations that are real and are somebody else's — and
#      the reader cannot tell, because they read exactly like the ones that apply.
#   2. Much of the rest is not security work. Notice, disclosure, appeal rights, human review,
#      accessibility: real duties owned by legal, HR or the product function. An overlay that
#      lists them without saying whose they are implies the security team will discharge them,
#      which is how a duty ends up owned by nobody.
#
# So every obligation must name its `owningFunction` and its `source`, and `register_regime`
# refuses one that does not. **No regulatory date is compiled into prose anywhere in this
# skill** — dates live in `regimes.json` behind an `asOf`, because a citation with no version
# is a claim about an unknown text. `evals/no-regime-dates.sh` holds that line.

AI_ROLES = ("deployer", "provider")

REGIMES = []
"""Populated from `references/regimes.json`, which ships empty. See the note above."""


def regimes_path() -> str:
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "references", "regimes.json")


def load_regimes(path: str = "") -> dict:
    """Read the regime dataset. Every obligation in it is validated on the way in."""
    path = path or regimes_path()
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except FileNotFoundError:
        raise Refusal("no regime dataset at %s" % path)
    except json.JSONDecodeError as exc:
        raise Refusal("%s is not valid JSON (line %d, column %d): %s"
                      % (path, exc.lineno, exc.colno, exc.msg))
    if not str(data.get("asOf") or "").strip():
        raise Refusal(
            "%s has no `asOf`.\n"
            "  Regulations are amended. A dataset with no date is a claim about an unknown "
            "version of every text in it." % path)
    out = {"datasetVersion": data.get("datasetVersion") or "",
           "sourceStatus": data.get("sourceStatus") or "",
           "asOf": data["asOf"], "note": data.get("note") or "", "regimes": []}
    for regime in (data.get("regimes") or []):
        register_regime(regime, into=out["regimes"])
    return out


def register_regime(regime: dict, into=None) -> dict:
    """Add a regime, refusing anything it cannot attribute or hand to somebody.

    The gate is the point, and it is annoying in exactly the right places: whoever adds regime
    content has to have read the text, named the article, and decided who at the firm owns the
    duty. Each of those is real work, and each is the piece that gets skipped.
    """
    rid = str(regime.get("id") or "").strip()
    if not rid:
        raise Refusal("a regime needs an id")
    if not str(regime.get("flag") or "").strip():
        raise Refusal(
            "regime %r needs a `flag`: the profile key that selects it.\n"
            "  A regime that is always on is not an overlay, it is an assertion that every "
            "reader is in scope for it." % rid)
    role = str(regime.get("aiRole") or "").strip()
    if role not in AI_ROLES:
        raise Refusal(
            "regime %r needs an `aiRole` of %s.\n"
            "  It is the decisive gate. Much of what these regimes say is addressed to "
            "PROVIDERS of AI systems, and a firm that buys and deploys one is usually a "
            "deployer. Without the distinction a register fills with obligations that are "
            "real and are somebody else's." % (rid, " or ".join(AI_ROLES)))
    for ob in (regime.get("obligations") or []):
        oid = str(ob.get("id") or "").strip() or "?"
        if not str(ob.get("source") or "").strip():
            raise Refusal(
                "regime %r, obligation %r has no `source`.\n"
                "  Every obligation must cite the article or section it comes from, checked "
                "against the regulation or the supervisory text — not a summary, a vendor "
                "explainer or a consultancy note — with the date it was checked. A tool "
                "asserting an obligation it cannot cite does not ship: a reader cannot tell a "
                "checked claim from a plausible one, and will act on both." % (rid, oid))
        if not str(ob.get("owningFunction") or "").strip():
            raise Refusal(
                "regime %r, obligation %r has no `owningFunction`.\n"
                "  Notice, disclosure, appeal rights, human review and accessibility are real "
                "duties and they are not security work. An overlay that lists them without "
                "saying whose they are implies the security team will discharge them, which "
                "is how a duty ends up owned by nobody." % (rid, oid))
    if into is None:
        target = REGIMES
    elif isinstance(into, tuple):
        raise Refusal("pass a mutable list to register a regime at runtime")
    else:
        target = into
    target.append(regime)
    return regime


def regimes_for(context: dict = None, role: str = "", regimes=None) -> list:
    """The regimes a profile turns on, for the role the organisation declared.

    Absence never enables one. A regime applies because somebody declared the flag, not
    because nothing said otherwise — the one place CAC-AP-1 §2.2's "absence asks more"
    inverts, and deliberately: asking a reader a provider's questions because nobody said they
    were not one would be inventing a regulator's interest in them.
    """
    profile = ((context or {}).get("profile") or {})
    active = []
    for regime in (REGIMES if regimes is None else regimes):
        entry = profile.get(regime["flag"])
        value = entry.get("value") if isinstance(entry, dict) else entry
        if value is not True:
            continue
        if role and regime.get("aiRole") != role:
            continue
        active.append(regime)
    return active


# --- The nist-csf signal (D-3) ------------------------------------------------
#
# `nist-csf` already asks one scoping question: are the AI-use focus areas of the Cyber AI
# Profile overlay applied to this Profile? Today it asks that of a human with nothing to hand.
# This gives the question EVIDENCE, and nothing else.
#
# Counts only. No ratings, no priorities, and no recommendation about which focus areas to
# enable. The signal informs; `nist-csf` still asks, and with no signal it behaves exactly as
# it did. The failure being avoided is one skill quietly deciding another's scope: a "you
# should enable secure and defend" that reads as an answer makes the question ceremonial.

def export_signal(store: dict, today: str = "") -> dict:
    """What this register knows, as counts, for `nist-csf`'s scoping question."""
    today = today or utc_today()
    live = [r for r in store["deployments"] if not r.get("retired")]
    by_system = {s.get("id"): s for s in store["systems"]}

    def sysof(rec):
        return by_system.get(rec.get("systemRef")) or {}

    return {
        "family": FAMILY,
        "export": "signal",
        "asOf": today,
        "organisation": store["meta"].get("orgName") or "",
        "counts": {
            "deployments": len(live),
            "generative": sum(1 for r in live if sysof(r).get("genAI")),
            "acts": sum(1 for r in live if r.get("autonomy") == "acts"),
            "consequentialDecisions": sum(
                1 for r in live
                if r.get("consequentialDecision")
                or (r.get("autonomy") in AUTONOMY
                    and autonomy_rank(r["autonomy"]) >= autonomy_rank("decides"))),
            "unsanctioned": sum(1 for r in live
                                if sysof(r).get("sanction") == "unsanctioned"),
        },
        "note": ("Counts of what is recorded, as at the date above. Evidence for a scoping "
                 "question, not an answer to it: which focus areas a Profile applies is a "
                 "judgement, and it stays where it is made."),
    }


# --- The findings bridge ------------------------------------------------------
#
# One-way, to `risk-register`, through the import path the third-party bridge already uses —
# not a third one. This skill never scores: findings are scored once, there, under L×I with an
# appetite to judge them against.
#
# **A finding is a requirement a named person recorded as NOT met.** Deliberately narrow, and
# the same narrowing `vendor-register` makes:
#
#   - It is a CHECKED fact with a name and a date on it, which is what makes it a defensible
#     candidate risk rather than a generated one.
#   - Escalations are NOT exported, though several describe real exposure. They are derived
#     and stateless, recomputed every run, so exporting them would mint a new candidate every
#     time the clock moved — and `board-pack` already aggregates escalations.
#   - **An uncontrolled attack class is not a finding.** It is a fact about something with no
#     closed state, and a risk HAS a closed state. Exporting one would defeat the rule this
#     whole skill is built on, one hop removed and out of sight.

FINDING_SCORING_KEYS = ("likelihood", "impact", "score", "severity", "rating", "band",
                        "exposure", "priority")
"""Keys the payload must never contain. Asserted rather than remembered."""


def export_findings(store: dict, today: str = "") -> dict:
    """Requirements recorded as not met, in the `risk-register` import shape.

    Idempotent on `sourceRef`, which is the deployment PLUS the requirement rather than the
    deployment alone: one deployment can fail three requirements and each is its own
    candidate, so keying on the deployment would collapse them into one and lose two.
    """
    today = today or utc_today()
    rows = []
    for rec in store["deployments"]:
        if rec.get("retired"):
            continue
        system = next((s for s in store["systems"] if s.get("id") == rec.get("systemRef")), {})
        conf = ((rec.get("criticality") or {}).get("confirmed") or {})
        classes = sorted(cls for cls, entry in (rec.get("exposure") or {}).items()
                         if not entry.get("noLongerDerived"))
        # "Contoso Contoso Assist" is what naive concatenation produces, and a board reader
        # notices it before they notice the finding.
        provider = str(system.get("provider") or "").strip()
        sysname = str(system.get("name") or "").strip()
        name = sysname if sysname.lower().startswith(provider.lower() or "\0") \
            else ("%s %s" % (provider, sysname)).strip()
        for req in (rec.get("requirements") or []):
            if req.get("met"):
                continue
            if not str(req.get("checkedBy") or "").strip():
                # Not a finding: nobody is recorded as having looked. Exporting it would put
                # an unattributed claim into a register whose whole discipline is refusing one.
                continue
            rows.append({
                "family": FAMILY,
                "sourceRef": "%s:%s:%s" % (FAMILY, rec["id"],
                                           str(req.get("requirement") or "")),
                "sourceDeploymentRef": rec["id"],
                "title": "%s (%s): %s not evidenced"
                         % (name or rec["id"], rec.get("purpose") or "unstated purpose",
                            req.get("requirement")),
                "description": ("AI deployment %s — %s, using %s, autonomy %s — %r was "
                                "checked and recorded as not met."
                                % (rec["id"], rec.get("purpose") or "an unstated purpose",
                                   name or "an unnamed system",
                                   rec.get("autonomy") or "undeclared",
                                   req.get("requirement"))),
                "vendor": system.get("provider") or "",
                "services": rec.get("purpose") or "",
                "owner": rec.get("owner") or "",
                "autonomy": rec.get("autonomy") or "",
                # The criticality AND the scale it was assigned under. A level read a year
                # later means nothing without it.
                "criticality": conf.get("value") or criticality_of(rec),
                "criticalityScaleVersion": conf.get("scaleVersion") or "",
                "criticalityConfirmed": bool(conf.get("value")),
                "nistaml": classes,
                "evidenceRef": req.get("evidenceRef") or req.get("evidence") or "",
                "checkedBy": req.get("checkedBy") or "",
                "checkedOn": req.get("checkedOn") or "",
                "gvsc": sorted({g for b in BATTERIES
                                if str(req.get("requirement") or "").startswith(b["id"] + ".")
                                for g in b.get("gvsc") or []}),
                "arrangementRef": system.get("arrangementRef") or "",
            })
    return {
        "family": FAMILY,
        "export": "findings",
        "asOf": today,
        "organisation": store["meta"].get("orgName") or "",
        "findings": rows,
        "note": ("Candidate risks. This register does not score: no likelihood, no impact, no "
                 "band. risk-register scores them once, there, against an appetite. Attack "
                 "classes are NOT exported — a class has no closed state, and a risk does."),
    }


# --- Context ------------------------------------------------------------------

def load_context(path: str) -> dict:
    """Read a CAC-AP-1 payload exported by `business-context`.

    Data, never an import (§2.6). A raw `.biz` is refused with the command that turns one into
    a payload, because reading the store directly would put the narrowing decision in the
    wrong skill.
    """
    with open(path, encoding="utf-8") as fh:
        payload = json.load(fh)
    if payload.get("family") == "business-context":
        raise Refusal(
            "%s is a raw .biz store, not an exported payload. Run `business_context.py export "
            "%s --out ctx.json` and pass that: CAC-AP-1 §2.6 makes the transport between "
            "skills data rather than an import." % (path, path))
    return payload


# --- Multi-entity -------------------------------------------------------------

def organisations(store: dict) -> list:
    seen = []
    for rec in store["deployments"]:
        name = str(rec.get("entityRef") or "").strip()
        if name and name not in seen:
            seen.append(name)
    return sorted(seen)


def check_one_organisation(store: dict) -> dict:
    """Refuse to render a register spanning legal entities as a single-org view.

    Same shape and same reasoning as everywhere else in this suite: a view built from more
    than one entity can be true about every row and wrong as a document, because the reader
    takes the whole thing to be about one company.
    """
    names = organisations(store)
    consolidation = (store.get("settings") or {}).get("consolidation") or {}
    if len(names) <= 1:
        return {"organisation": names[0] if names else "", "consolidated": None}
    by = str(consolidation.get("declaredBy") or "").strip()
    basis = str(consolidation.get("basis") or "").strip()
    if not by or not basis:
        raise Refusal(
            "this register holds deployments for %d legal entities (%s) and no consolidation "
            "is declared.\n"
            "  A single-organisation view built from several entities is true about every row "
            "and wrong as a document. Declare it: settings.consolidation = {\"declaredBy\": "
            "\"...\", \"basis\": \"...\"}. A consolidation with no basis is refused too, "
            "because the basis is the part a reviewer actually needs."
            % (len(names), ", ".join(names)))
    return {"organisation": ", ".join(names),
            "consolidated": {"declaredBy": by, "basis": basis, "entities": names}}


# --- Analysis -----------------------------------------------------------------

def analyze(store: dict, today: str = "", context: dict = None) -> dict:
    """Everything a surface needs, computed once. No score is produced here or anywhere.

    Counts are counts of things that exist. There is deliberately no aggregate: a register
    with three top-criticality deployments and one untraced one has three top-criticality
    deployments and one untraced one, and any single number standing for that is an opinion
    the tool is not entitled to.
    """
    today = today or utc_today()
    entity = check_one_organisation(store)
    scale = store["settings"]["criticalityScale"]
    grace = int(store["settings"].get("evidenceGraceDays") or 365)

    live = [r for r in store["deployments"] if not r.get("retired")]
    by_level = {}
    for rec in live:
        by_level.setdefault(criticality_of(rec), []).append(rec["id"])

    rows = []
    for rec in sorted(store["deployments"], key=lambda r: r["id"]):
        block = rec.get("criticality") or {}
        conf = block.get("confirmed") or {}
        system = next((s for s in store["systems"] if s.get("id") == rec.get("systemRef")), {})
        exposure = rec.get("exposure") or {}
        row = {
            "id": rec["id"],
            "systemRef": rec.get("systemRef") or "",
            "system": system.get("name") or rec.get("systemRef") or "",
            "provider": system.get("provider") or "",
            "version": system.get("version") or "",
            "baseModel": system.get("baseModel") or "",
            "hosting": system.get("hosting") or "",
            "genAI": bool(system.get("genAI")),
            "sanction": system.get("sanction") or "",
            "provenance": system.get("provenance") or "",
            "arrangementRef": system.get("arrangementRef") or "",
            "entityRef": rec.get("entityRef") or "",
            "purpose": rec.get("purpose") or "",
            "owner": rec.get("owner") or "",
            "autonomy": rec.get("autonomy") or "",
            "consequentialDecision": bool(rec.get("consequentialDecision")),
            "connectedResources": list(rec.get("connectedResources") or []),
            "dataClasses": list(rec.get("dataClasses") or []),
            "supports": rec.get("supports") or "",
            "criticality": criticality_of(rec),
            "derived": block.get("derived") or "",
            "confirmedBy": conf.get("by") or "",
            "scaleVersion": conf.get("scaleVersion") or "",
            "trace": block.get("trace") or [],
            "truncated": bool(block.get("truncated")),
            "lastAssessed": _last_assessed(rec),
            "retired": bool(rec.get("retired")),
            # Per class, with its control count and its state. Never rolled into a number:
            # "three of five classes have a control" is a fact, and any average of it is an
            # opinion about which classes matter.
            "exposure": [
                {"class": cls,
                 "name": entry.get("name") or "",
                 "concern": entry.get("concern") or "",
                 "because": entry.get("because") or "",
                 "controls": len(entry.get("controls") or []),
                 "state": exposure_state(entry),
                 "noLongerDerived": bool(entry.get("noLongerDerived"))}
                for cls, entry in sorted(exposure.items())],
            "autonomyWarnings": autonomy_warnings(rec) if rec.get("autonomy") in AUTONOMY
                                else [],
        }
        if not rec.get("retired"):
            asked = ask(store, rec["id"], context, today=today)
            row["openQuestions"] = asked["open"]
            row["reConfirmQuestions"] = asked["reConfirm"]
            row["skippedBatteries"] = len(asked["skipped"])
            row["openProposals"] = len(open_proposals(rec))
            by_status = {}
            for ev in (rec.get("evidence") or []):
                st = evidence_status(ev, today, grace)
                by_status[st] = by_status.get(st, 0) + 1
            row["evidence"] = {"total": len(rec.get("evidence") or []), "byStatus": by_status}
        rows.append(row)

    out = {
        "family": FAMILY,
        "asOf": today,
        "organisation": entity["organisation"],
        "scale": list(scale),
        "scaleVersion": store["settings"].get("scaleVersion") or "",
        "counts": {
            "systems": len(store["systems"]),
            "deployments": len(store["deployments"]),
            "live": len(live),
            "retired": len(store["deployments"]) - len(live),
            "generative": sum(1 for r in rows if r["genAI"] and not r["retired"]),
            "unsanctioned": sum(1 for r in rows
                                if r["sanction"] == "unsanctioned" and not r["retired"]),
            "discovered": sum(1 for s in store["systems"]
                              if s.get("provenance") == "discovered"),
            "byCriticality": {k: len(v) for k, v in sorted(by_level.items())},
            "byAutonomy": {a: sum(1 for r in rows if r["autonomy"] == a and not r["retired"])
                           for a in AUTONOMY},
        },
        "deployments": rows,
        "openQuestions": sum(r.get("openQuestions", 0) for r in rows),
        "reConfirmQuestions": sum(r.get("reConfirmQuestions", 0) for r in rows),
        "openProposals": sum(r.get("openProposals", 0) for r in rows),
        "uncontrolledClasses": sum(1 for r in rows for e in r["exposure"]
                                   if e["state"] == "no-controls-recorded"
                                   and not e["noLongerDerived"] and not r["retired"]),
        "escalations": escalations(store, today),
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
            "assigned by hand is 'untraced' — the walk had no workflows to reach. This is the "
            "safe direction and never a refusal.")
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

        Mirrored from `vendor_register.py`, where three mutation tests were caught by a crash
        rather than a named check — and a crash aborts the run and discards the summary, so a
        broken guard reads as a silent pass in exactly the situation it exists for.
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
        path = os.path.join(work, "t.air")

        # --- T1: round trip ---------------------------------------------------
        store = new_store("Acme Manufacturing", "D. Galleyne")
        save(path, store)
        loaded = load(path)
        eq(loaded["meta"]["orgName"], "Acme Manufacturing", "a store round-trips")
        eq(loaded["settings"]["criticalityScale"], DEFAULT_SCALE, "with the default scale")
        wrong = os.path.join(work, "w.vnd")
        open(wrong, "w", encoding="utf-8").write('{"family": "vendor-register"}')
        refuses(lambda: load(wrong), "another skill's store is refused", "not an AI register")

        # --- T2: the two object types -----------------------------------------
        before = open(path, "rb").read()
        refuses(lambda: add_system(store, "Copilot", "", "1.0"),
                "a system with no provider is refused", "Whose model is this")
        refuses(lambda: add_system(store, "Copilot", "Contoso", ""),
                "a system with no version is refused", "silently invalidates")
        eq(open(path, "rb").read(), before, "and no refusal touched the file")

        sysrec = add_system(store, "Contoso Assist", "Contoso", "2026.4",
                            base_model="GPT-cx-2", hosting="saas", gen_ai=True,
                            retrieval_augmented=True, arrangement_ref="VA-001")
        eq(sysrec["id"], "S-001", "systems are numbered from one")
        eq(sysrec["sanction"], "sanctioned", "a declared system is sanctioned by default")
        eq(sysrec["provenance"], "declared", "and declared, not discovered")

        refuses(lambda: deploy(store, "S-999", "screening", "HR Director", "decides"),
                "a deployment of an unknown system is refused", "not in the inventory")
        refuses(lambda: deploy(store, "S-001", "screening", "", "decides"),
                "a deployment with no owner is refused", "goes stale")
        # THE autonomy refusal. It gates every battery here.
        refuses(lambda: deploy(store, "S-001", "screening", "HR Director", ""),
                "a deployment with no declared autonomy is refused", "assessed anyway, quietly")
        refuses(lambda: deploy(store, "S-001", "screening", "HR Director", "supervises"),
                "and an autonomy outside the declared set is refused")
        eq(open(path, "rb").read(), before, "and none of those touched the file either")

        dep = deploy(store, "S-001", "drafting marketing copy", "CMO", "informs")
        eq(dep["id"], "D-001", "deployments are numbered from one")
        eq(dep["entityRef"], "Acme Manufacturing", "entityRef defaults to the org")
        # The same system, deployed twice, is two exposures. This is the design in one line.
        dep2 = deploy(store, "S-001", "screening job applicants", "HR Director", "decides",
                      data_classes=["applicant personal data"], consequential=True,
                      supports="CRM")
        eq(dep2["systemRef"], dep["systemRef"],
           "one system can carry two deployments — risk lives in the deployment")

        # --- T3: shadow AI ----------------------------------------------------
        refuses(lambda: intake_discovered(store, "Some chatbot", "", "2026-05-01"),
                "a discovered system with no source is refused", "not a finding")
        refuses(lambda: intake_discovered(store, "Some chatbot", "CASB egress review", ""),
                "one with no sighting date is refused", "unknown staleness")
        found = intake_discovered(store, "Fabrikam Writer", "CASB egress review, 2026-05",
                                  "2026-05-01")
        eq(found["provenance"], "discovered", "a discovered system is marked as such")
        eq(found["sanction"], "unsanctioned", "and is unsanctioned until somebody says otherwise")
        ok(any(s["id"] == found["id"] for s in store["systems"]),
           "and it is a real row immediately — no staging area for shadow AI")
        refuses(lambda: sanction(store, found["id"], "sanctioned", "", "it is fine"),
                "sanctioning with no name is refused")
        refuses(lambda: sanction(store, found["id"], "sanctioned", "CISO", ""),
                "and with no basis")
        sanction(store, found["id"], "under-review", "CISO", "assessing before a decision")
        eq(find_system(store, found["id"])["sanction"], "under-review", "a sanction records")

        # --- T4: criticality, mirrored ----------------------------------------
        ctx = {"crownJewels": [
            {"system": "Plant historian", "criticality": "high", "dependsOn": ["SCADA gateway"]},
            {"system": "CRM", "criticality": "moderate"},
        ]}
        lvl, trace, trunc = derive_criticality({"supports": ""}, ctx)
        eq(lvl, UNTRACED, "a deployment supporting nothing derives untraced, NOT low")
        ok(lvl != "low", "and specifically not the bottom of the scale")
        eq(derive_criticality({"supports": "SCADA gateway"}, ctx),
           ("high", ["SCADA gateway", "Plant historian"], False),
           "a two-hop dependency resolves, exactly as in vendor-register")
        eq(derive_criticality({"supports": "CRM"}, {}),
           (UNTRACED, ["CRM"], False), "no context at all: untraced, and never a refusal")
        refuses(lambda: criticality_rank(store, UNTRACED),
                "ordering a list containing untraced RAISES", "state, not a level")
        eq(criticality_rank(store, "high"), 2, "while a real level ranks normally")
        refuses(lambda: classify(store, "D-002", ctx, confirm="high"),
                "--confirm with no --by is refused", "cannot be defended")
        classify(store, "D-002", ctx, confirm="high", by="D. Galleyne")
        eq(criticality_of(dep2), "high", "and a confirmed level is what the register acts on")

        # --- T5: autonomy as a gate -------------------------------------------
        eq(list(AUTONOMY), ["informs", "recommends", "decides", "acts"],
           "autonomy is ordered, lowest first")
        ok(autonomy_rank("acts") > autonomy_rank("decides") > autonomy_rank("informs"),
           "and the order is usable for comparison")
        acting = deploy(store, "S-001", "auto-remediating tickets", "Head of IT", "acts")
        warn = autonomy_warnings(acting)
        eq(len(warn), 1, "an 'acts' deployment with no connected resources warns")
        ok("overstated" in warn[0],
           "...naming both readings, because they need different fixes")
        ok(not autonomy_warnings(dep), "while a plain 'informs' deployment warns about nothing")

        # --- T6: exposure DERIVED, never selected -----------------------------
        map_exposure(store, "D-002")
        exp = find_deployment(store, "D-002")["exposure"]
        # THE test. A generative deployment handling personal data is exposed to privacy
        # attacks, and there is no path that says otherwise.
        ok("NISTAML.03" in exp, "a generative deployment handling personal data is exposed "
                                "to NISTAML.03")
        ok(exp["NISTAML.03"]["because"], "and the record says WHY, from a declared attribute")
        ok(not any(callable(getattr(sys.modules[__name__], n, None))
                   and "inapplicable" in n.lower() for n in dir(sys.modules[__name__])),
           "and no function exists to mark a class inapplicable")
        ok("NISTAML.04" in exp, "a generative deployment is exposed to misuse")
        ok("NISTAML.05" in exp,
           "and to supply chain, because the model comes from outside")
        # Predictive: misuse does not apply, and asking about it would be noise.
        pred_sys = add_system(store, "Churn model", "In-house", "3.1", gen_ai=False,
                              hosting="self-hosted")
        pred = deploy(store, pred_sys["id"], "churn scoring", "Head of Sales", "recommends")
        map_exposure(store, pred["id"])
        pexp = find_deployment(store, pred["id"])["exposure"]
        ok("NISTAML.04" not in pexp, "a PREDICTIVE deployment is not exposed to misuse")
        ok("NISTAML.05" not in pexp,
           "and an in-house model raises no supply-chain class")
        ok("NISTAML.01" in pexp and "NISTAML.02" in pexp,
           "while availability and integrity apply to any deployment")
        # Recompute on attribute change.
        pred_sys["genAI"] = True
        map_exposure(store, pred["id"])
        ok("NISTAML.04" in find_deployment(store, pred["id"])["exposure"],
           "flipping genAI recomputes exposure")
        ok(any(h["event"] == "exposure-mapped" for h in store["history"]),
           "and the recompute appends to history")

        # --- T7: no closed state ----------------------------------------------
        save(path, store)
        before = open(path, "rb").read()
        refuses(lambda: record_control(store, "D-002", "NISTAML.02", "input filtering", ""),
                "record-control with no evidence is refused", "is an intention")
        refuses(lambda: record_control(store, "D-002", "NISTAML.99", "x", "y"),
                "a control against a class not derived is refused", "cannot be selected by hand")
        refuses(lambda: accept_exposure(),
                "there is no way to accept an exposure", "exceptions-register")
        eq(open(path, "rb").read(), before, "and no refusal touched the file")

        for n in range(3):
            record_control(store, "D-002", "NISTAML.02", "control %d" % n,
                           "evidence %d" % n, by="Head of Security")
        entry = find_deployment(store, "D-002")["exposure"]["NISTAML.02"]
        eq(len(entry["controls"]), 3, "three controls record against a class")
        eq(exposure_state(entry), "controls-recorded",
           "...and the class reads as controls-recorded")
        ok(exposure_state(entry) in EXPOSURE_STATES, "which is one of exactly two states")
        eq(len(EXPOSURE_STATES), 2, "and there is no third")
        # THE rule. Nothing anywhere says a class is done.
        blob = json.dumps(find_deployment(store, "D-002")["exposure"])
        ok(not CLOSED_STATE_RE.search(blob),
           "no key or value describes a class as mitigated, resolved, closed or accepted")
        ok(not any(CLOSED_STATE_RE.search(s) for s in EXPOSURE_STATES),
           "and neither state is a closed one")
        # Controls survive a recompute; evidence somebody produced is not thrown away.
        map_exposure(store, "D-002")
        eq(len(find_deployment(store, "D-002")["exposure"]["NISTAML.02"]["controls"]), 3,
           "controls survive a recompute")

        # --- T9: batteries, and what narrows them -----------------------------
        #
        # D-001 is `informs`, unclassified, generative, external provider.
        # D-002 is `decides`, confirmed high (the top of the default scale), generative.
        map_exposure(store, "D-001")
        plain = batteries_for(find_deployment(store, "D-001"), store, None)
        applied = [b["id"] for b in plain["applied"]]
        # §2.2 in one assertion: no context, no criticality — everything applies EXCEPT the
        # two gated on a declared attribute that says otherwise.
        ok("inventory" in applied and "access-and-data" in applied
           and "monitoring" in applied,
           "with no context and no criticality, the ungated batteries all apply")
        ok("regulated-data" in applied,
           "and a flag nobody declared APPLIES — absence asks more (CAC-AP-1 §2.2)")
        ok("adversarial-testing" in applied,
           "a generative deployment gets the adversarial battery")
        ok("autonomy-controls" not in applied,
           "while an 'informs' deployment is not asked what a person can override")
        # `untraced` and `unclassified` narrow NOTHING. D-001 has never been classified.
        eq(criticality_of(find_deployment(store, "D-001")), UNCLASSIFIED,
           "D-001 has never been classified")
        ok("withdrawal" in applied,
           "an unclassified deployment gets the FULL set — neither state can narrow anything")

        top = batteries_for(find_deployment(store, "D-002"), store, None)
        top_ids = [b["id"] for b in top["applied"]]
        ok("autonomy-controls" in top_ids,
           "a 'decides' deployment IS asked what a person can override")
        ok("withdrawal" in top_ids, "and a top-of-scale one is asked about withdrawal")

        # §2.3, the seam this skill plugs into: an org profile saying the organisation uses no
        # AI does NOT narrow away the generative battery on a system recorded as generative.
        no_ai = {"profile": {"aiInUse": {"value": False, "declaredBy": "COO",
                                         "declaredOn": "2026-01-01"}}}
        with_profile = [b["id"] for b in
                        batteries_for(find_deployment(store, "D-002"), store,
                                      no_ai)["applied"]]
        ok("adversarial-testing" in with_profile,
           "a profile declaring no AI in use does NOT narrow away the generative battery — "
           "genAI is a recorded attribute of a system in the inventory, not a declaration")

        # §2.3 in the other direction, on a flag that IS a declaration.
        prof_false = {"profile": {"regulatedDataHeld": {"value": False, "declaredBy": "DPO",
                                                        "declaredOn": "2026-02-01"}}}
        narrowed = batteries_for(find_deployment(store, "D-002"), store, prof_false)
        ok("regulated-data" not in [b["id"] for b in narrowed["applied"]],
           "a profile declaring regulatedDataHeld false narrows that battery away")
        skip = next((s for s in narrowed["skipped"]
                     if s["battery"] == "regulated-data"), {})
        eq(skip.get("declaredBy"), "DPO", "and the skip names who declared it (§2.4)")
        eq(skip.get("declaredOn"), "2026-02-01", "...and when")
        refuses(lambda: declare_on_deployment(store, "D-002", "regulatedDataHeld", True, ""),
                "declaring a flag with no name is refused", "cannot be defended")
        declare_on_deployment(store, "D-002", "regulatedDataHeld", True, "HR Director",
                              basis="applicant data is regulated personal data")
        ok("regulated-data" in [b["id"] for b in
                                batteries_for(find_deployment(store, "D-002"), store,
                                              prof_false)["applied"]],
           "and a deployment declaring it TRUE outranks the profile saying false (§2.3)")

        # Every skip carries a declarer and a date. A skip that cannot say who narrowed it is
        # indistinguishable from a question nobody thought to ask.
        low = deploy(store, "S-001", "internal search", "Head of IT", "informs", by="CIO")
        classify(store, low["id"], ctx, confirm="low", by="D. Galleyne")
        skips = batteries_for(find_deployment(store, low["id"]), store, None)["skipped"]
        ok(skips, "a low-criticality 'informs' deployment does have skips to inspect")
        ok(all(s.get("declaredBy") and "declaredOn" in s for s in skips),
           "and every skip record carries a declarer and a date (§2.4)")

        # --- T10: evidence, tiers and assessment ------------------------------
        save(path, store)
        before = open(path, "rb").read()
        # THE tier judgement most likely to be got wrong.
        refuses(lambda: ingest(store, "D-002", "model-card", "T1", "the provider's site",
                               scope="the model", period_start="2026-01-01",
                               period_end="2026-12-31"),
                "a model card cannot be recorded as T1", "describing its own model")
        refuses(lambda: ingest(store, "D-002", "model-card", "T2", "the provider's site"),
                "nor as a contractual commitment", "never a reason to stop asking")
        refuses(lambda: ingest(store, "D-002", "red-team-report", "T1", "an external firm"),
                "a T1 with no scope and no period is refused", "cannot expire")
        refuses(lambda: ingest(store, "D-002", "trust-page", "T4", "their site",
                               url="https://example.test/trust"),
                "a URL with no retrieval date is refused", "may no longer say it")
        eq(open(path, "rb").read(), before, "and none of those refusals touched the file")

        card = ingest(store, "D-002", "model-card", "T3", "the provider's published card",
                      by="Security Analyst")
        eq(card["tier"], "T3", "a model card ingests as T3")
        refuses(lambda: propose(store, "D-002", "inventory.provenance", card["id"],
                                "the Model details section"),
                "and cannot be proposed against", "still the provider describing itself")
        refuses(lambda: propose(store, "D-002", "inventory.provenance", card["id"], ""),
                "a proposal with no citation is refused", "is an opinion")

        rt = ingest(store, "D-002", "red-team-report", "T1", "Fabrikam Security, engagement 41",
                    scope="the chat surface and the retrieval path, excluding tool calling",
                    period_start="2026-01-01", period_end="2026-06-30", by="CISO")
        pr = propose(store, "D-002", "adversarial-testing.red-team", rt["id"],
                     "section 4.2, findings 1-3", by="Security Analyst")
        eq(pr["status"], "proposed", "a proposal against a T1 is stored, and satisfies nothing")
        ok(not any(r.get("requirement") == "adversarial-testing.red-team"
                   for r in find_deployment(store, "D-002").get("requirements") or []),
           "...specifically: no requirement moved")
        refuses(lambda: assess(store, "D-002", "", confirm=[pr["id"]]),
                "assessing with no --by is refused", "nobody's name on it")
        refuses(lambda: assess(store, "D-002", "CISO", reject=[pr["id"]]),
                "and rejecting with no --why is refused", "whether to try again")

        asked_before = ask(store, "D-002", None, today="2026-06-15")
        assess(store, "D-002", "CISO", on="2026-06-10", confirm=[pr["id"]],
               note="read the report against the deployment as configured")
        asked_after = ask(store, "D-002", None, today="2026-06-15")
        ok(asked_after["open"] < asked_before["open"],
           "a confirmed T1 proposal subtracts a question")
        eq(asked_before["open"] - asked_after["open"], 1, "...exactly the one it answered")
        ok(any(q["key"] == "adversarial-testing.red-team" for q in asked_before["questions"])
           and not any(q["key"] == "adversarial-testing.red-team"
                       for q in asked_after["questions"]),
           "...and it is that question, by id rather than by prose")
        # THE product claim, in the only form that matters.
        card2 = ingest(store, "D-002", "questionnaire", "T3", "their completed answers")
        find_deployment(store, "D-002")["requirements"].append(
            {"requirement": "monitoring.degradation", "met": True,
             "evidenceRef": card2["id"], "checkedOn": "2026-06-10", "checkedBy": "CISO"})
        eq(ask(store, "D-002", None, today="2026-06-15")["open"], asked_after["open"],
           "while the same requirement covered by a T3 subtracts NOTHING")
        # Ageing, not gone.
        in_grace = ask(store, "D-002", None, today="2027-01-01")
        ok(any(q["status"] == "re-confirm" and q["key"] == "adversarial-testing.red-team"
               for q in in_grace["questions"]),
           "evidence in grace re-asks the question, marked re-confirm rather than open")
        expired = ask(store, "D-002", None, today="2028-01-01")
        ok(any(q["status"] == "open" and q["key"] == "adversarial-testing.red-team"
               for q in expired["questions"]),
           "and expired evidence puts it back to open")
        eq(assess(store, "D-002", "CISO", on="2026-06-11")["againstSystem"]["version"],
           "2026.4",
           "an assessment records the system version it was made against")
        refuses(lambda: record_requirement(store, "D-002", "monitoring.output-retention",
                                           "the DPA, clause 8", met=False),
                "recording a requirement with no name is refused", "needs a name on it")

        # --- T11: escalations -------------------------------------------------
        #
        # Each trigger gets a fixture built for it, on its own store, so a fixture that
        # accidentally fires two triggers cannot make a broken one look alive.
        def fresh():
            s = new_store("Escalation Ltd")
            sysrec = add_system(s, "Contoso Assist", "Contoso", "2026.4",
                                base_model="GPT-cx-2", hosting="saas",
                                arrangement_ref="VA-001")
            d = deploy(s, sysrec["id"], "drafting", "CMO", "informs", by="CIO")
            map_exposure(s, d["id"])
            classify(s, d["id"], {"crownJewels": [{"system": "CRM", "criticality": "low"}]},
                     confirm="low", by="D. Galleyne")
            assess(s, d["id"], "CISO", on="2026-06-01")
            return s, sysrec, d

        def triggers(s, when="2026-07-01"):
            return {e["trigger"] for e in escalations(s, when)}

        base, _, _ = fresh()
        # Baseline. Everything below is measured against this, so anything that shows up
        # here is noise the register would emit about a well-kept deployment.
        base_fired = triggers(base)
        ok("model-changed" not in base_fired and "base-model-changed" not in base_fired
           and "autonomy-increased" not in base_fired and "unowned" not in base_fired
           and "unsanctioned-in-use" not in base_fired
           and "provider-arrangement-missing" not in base_fired,
           "a classified, assessed, owned, sanctioned deployment escalates none of the "
           "change triggers")
        ok("attack-class-uncontrolled" in base_fired,
           "...while a deployment with no control recorded against any class does escalate")
        ok("assessment-overdue" not in base_fired,
           "and a low-criticality deployment has no cadence to be overdue against")

        s, sysrec, dep_e = fresh()
        sysrec["version"] = "2026.5"
        ok("model-changed" in triggers(s),
           "a version change since the last assessment fires model-changed")
        ok(criticality_of(find_deployment(s, dep_e["id"])) == "low",
           "...at the LOWEST criticality level, where there is no cadence to catch it")

        s, sysrec, _ = fresh()
        sysrec["baseModel"] = "GPT-cx-3"                 # product version untouched
        fired = triggers(s)
        ok("base-model-changed" in fired,
           "a disclosed base-model change fires with the product version unchanged")
        ok("model-changed" not in fired,
           "...and it is a DIFFERENT trigger, because nothing else would have noticed")

        s, _, dep_e = fresh()
        find_deployment(s, dep_e["id"])["autonomy"] = "acts"
        ok("autonomy-increased" in triggers(s), "autonomy rising since the assessment fires")
        s, _, dep_e = fresh()
        find_deployment(s, dep_e["id"])["connectedResources"] = ["the ticketing system"]
        ok("autonomy-increased" in triggers(s), "and so does reaching something new")

        s, _, dep_e = fresh()
        find_deployment(s, dep_e["id"])["owner"] = ""
        ok("unowned" in triggers(s), "a deployment with no owner fires unowned")

        s, sysrec, _ = fresh()
        sysrec["arrangementRef"] = ""
        ok("provider-arrangement-missing" in triggers(s),
           "SaaS with no third-party arrangement recorded fires")

        s, sysrec, _ = fresh()
        sysrec["sanction"] = "unsanctioned"
        fired = [e for e in escalations(s, "2026-07-01")
                 if e["trigger"] == "unsanctioned-in-use"]
        eq(len(fired), 1, "an unsanctioned system with a live deployment fires")
        eq(at(fired, 0, "severity"), "high", "...as high on an 'informs' deployment")
        find_deployment(s, "D-001")["autonomy"] = "decides"
        eq(at([e for e in escalations(s, "2026-07-01")
               if e["trigger"] == "unsanctioned-in-use"], 0, "severity"), "critical",
           "...and critical where it makes the decision")

        s, _, dep_e = fresh()
        classify(s, dep_e["id"], {"crownJewels": [{"system": "CRM", "criticality": "high"}]},
                 confirm="high", by="D. Galleyne")
        ok("assessment-overdue" in triggers(s, "2027-08-01"),
           "a high-criticality deployment past its cadence fires assessment-overdue")
        ok("assessment-overdue" not in triggers(s, "2026-07-01"),
           "...and not before it")

        s, _, dep_e = fresh()
        record_control(s, dep_e["id"], "NISTAML.01", "rate limiting", "config export",
                       on="2026-05-01", by="Head of Security")
        left = [e for e in escalations(s, "2026-07-01")
                if e["trigger"] == "attack-class-uncontrolled"]
        eq(len(left), 1, "uncontrolled classes are ONE escalation, not one per class")
        ok("NISTAML.01" not in at(left, 0, "evidence", ""),
           "...naming only the classes with nothing recorded against them")
        ok(all(set(e) == {"trigger", "subjectKind", "subjectRef", "severity", "since",
                          "evidence"} for e in escalations(s, "2026-07-01")),
           "and every escalation carries exactly the CAC-EL-1 six-key shape")
        ok(all(e["subjectKind"] == "deployment" for e in escalations(s, "2026-07-01")),
           "with subjectKind 'deployment' — where risk lives here")

        # --- analyze ----------------------------------------------------------
        out = analyze(store, today="2026-08-01")
        eq(out["family"], FAMILY, "analyze declares its family")
        ok(out["counts"]["deployments"] >= 4, "and counts what is there")
        ok("byCriticality" in out["counts"] and "byAutonomy" in out["counts"],
           "criticality and autonomy are counted per named level, never aggregated")
        ok(not any(k in out for k in ("score", "rating", "grade", "postureScore")),
           "and there is no aggregate anywhere in the output")
        ok(any("no applicability profile was supplied" in n for n in out["notes"]),
           "an analysis with no profile says so on its face")

        # --- T12: regimes as dated data ---------------------------------------
        data = load_regimes()
        eq(data["regimes"], [],
           "the shipped regime dataset is EMPTY — the mechanism ships, the content does not")
        ok(data["asOf"], "and it still carries an asOf, because a dataset with no date is a "
                         "claim about an unknown version of every text in it")
        pool = []
        refuses(lambda: register_regime({"id": "x"}, into=pool),
                "a regime with no flag is refused", "not an overlay")
        refuses(lambda: register_regime({"id": "x", "flag": "f"}, into=pool),
                "a regime with no aiRole is refused", "usually a deployer")
        refuses(lambda: register_regime(
            {"id": "x", "flag": "f", "aiRole": "auditor"}, into=pool),
            "and an aiRole outside deployer/provider is refused")
        refuses(lambda: register_regime(
            {"id": "x", "flag": "f", "aiRole": "deployer",
             "obligations": [{"id": "o1", "requirement": "do the thing",
                              "owningFunction": "Legal"}]}, into=pool),
            "an obligation with no source is refused", "cannot tell a checked claim")
        refuses(lambda: register_regime(
            {"id": "x", "flag": "f", "aiRole": "deployer",
             "obligations": [{"id": "o1", "requirement": "do the thing",
                              "source": "Article 1, as checked against the text"}]}, into=pool),
            "and one with no owningFunction is refused", "owned by nobody")
        eq(pool, [], "and none of those refusals registered anything")
        good = register_regime(
            {"id": "example", "flag": "exampleScope", "aiRole": "deployer",
             "obligations": [{"id": "o1", "requirement": "do the thing",
                              "owningFunction": "Legal",
                              "source": "Article 1, checked against the text"}]}, into=pool)
        eq(len(pool), 1, "a complete regime registers — the gate is not refusing everything")
        # Absence never enables a regime. This is where §2.2 deliberately inverts.
        eq(regimes_for({}, regimes=pool), [],
           "a profile that says nothing enables NO regime — absence never invents a "
           "regulator's interest in somebody")
        on = {"profile": {"exampleScope": {"value": True, "declaredBy": "GC",
                                           "declaredOn": "2026-03-01"}}}
        eq(len(regimes_for(on, regimes=pool)), 1, "a declared flag turns it on")
        eq(regimes_for(on, role="provider", regimes=pool), [],
           "and the role gate excludes a deployer regime from a provider's questions")
        eq(len(regimes_for(on, role="deployer", regimes=pool)), 1, "...and includes it there")
        eq(good["aiRole"], "deployer", "the registered regime keeps its role")

        # --- T13: the nist-csf signal -----------------------------------------
        sig = export_signal(store, today="2026-08-01")
        eq(sig["export"], "signal", "export-signal declares what it is")
        eq(sorted(sig["counts"]),
           ["acts", "consequentialDecisions", "deployments", "generative", "unsanctioned"],
           "and carries exactly five counts")
        ok(all(isinstance(v, int) for v in sig["counts"].values()),
           "every one of them an integer count of things that exist")
        ok(not any(k in json.dumps(sig).lower()
                   for k in ("priority", "recommend", "\"rating\"")),
           "with no rating, no priority and no recommendation — it informs, it does not answer")

        # --- T14: the findings bridge -----------------------------------------
        record_requirement(store, "D-002", "monitoring.output-retention",
                           "the DPA, clause 8 — silent on retention", met=False, by="DPO")
        payload = export_findings(store, today="2026-08-01")
        eq(payload["export"], "findings", "export-findings declares what it is")
        eq(len(payload["findings"]), 1, "one requirement recorded not met is one finding")
        row = at(payload["findings"], 0, "sourceRef", "")
        eq(row, "ai-register:D-002:monitoring.output-retention",
           "keyed on the deployment AND the requirement, so three failures are three rows")
        ok(at(payload["findings"], 0, "nistaml"),
           "the finding carries the exposure classes derived for its deployment")
        eq(at(payload["findings"], 0, "criticalityScaleVersion"), "v1",
           "and the scale version the criticality was assigned under")
        # THE property. No number crosses this bridge.
        keys = {k for f in payload["findings"] for k in f}
        eq(sorted(keys & set(FINDING_SCORING_KEYS)), [],
           "and the payload carries no likelihood, impact, score, band or severity")
        # An escalation is not a finding, and neither is an uncontrolled class.
        ok(any(e["trigger"] == "attack-class-uncontrolled"
               for e in escalations(store, "2026-08-01")),
           "the register does have uncontrolled attack classes")
        eq(len(payload["findings"]), 1,
           "...and not one of them crossed the bridge — a class has no closed state, "
           "and a risk does")
        # Nobody looked = not a finding.
        find_deployment(store, "D-002")["requirements"].append(
            {"requirement": "monitoring.degradation", "met": False, "checkedBy": ""})
        eq(len(export_findings(store, today="2026-08-01")["findings"]), 1,
           "a requirement marked not met by nobody is not exported")

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
        raise Refusal("%s already exists. `init` never overwrites a register." % args.store)
    save(args.store, new_store(args.org, args.prepared_by, args.scope_note))
    print("Created %s for %r" % (args.store, args.org))
    return 0


def _cmd_add_system(args) -> int:
    store = load(args.store)
    rec = add_system(store, args.name, args.provider, args.version, family=args.family,
                     base_model=args.base_model, hosting=args.hosting,
                     gen_ai=not args.predictive, fine_tuned=args.fine_tuned,
                     retrieval_augmented=args.retrieval_augmented,
                     vendor_ref=args.vendor, arrangement_ref=args.arrangement,
                     chain_note=args.chain_note, by=args.by)
    save(args.store, store)
    print("%s  %s %s (%s)" % (rec["id"], rec["provider"], rec["name"], rec["version"]))
    return 0


def _cmd_intake_discovered(args) -> int:
    store = load(args.store)
    rec = intake_discovered(store, args.name, args.source, args.found_on,
                            provider=args.provider, by=args.by)
    save(args.store, store)
    print("%s  %s — discovered via %s on %s, UNSANCTIONED"
          % (rec["id"], rec["name"], rec["discoveredVia"], rec["discoveredOn"]))
    return 0


def _cmd_sanction(args) -> int:
    store = load(args.store)
    rec = sanction(store, args.system, args.state, args.by, args.why)
    save(args.store, store)
    print("%s  %s by %s on %s" % (rec["id"], rec["sanction"], rec["sanctionBy"],
                                  rec["sanctionOn"]))
    return 0


def _cmd_deploy(args) -> int:
    store = load(args.store)
    rec = deploy(store, args.system, args.purpose, args.owner, args.autonomy,
                 data_classes=args.data_class, connected_resources=args.connects,
                 supports=args.supports, entity_ref=args.entity,
                 consequential=args.consequential, by=args.by)
    map_exposure(store, rec["id"], by=args.by)
    save(args.store, store)
    print("%s  %s — %s, autonomy %s" % (rec["id"], rec["systemRef"], rec["purpose"],
                                        rec["autonomy"]))
    for warning in autonomy_warnings(rec):
        print("  warning: %s" % warning)
    exp = sorted(rec["exposure"])
    print("  exposed to: %s" % (", ".join(exp) if exp else "nothing derived"))
    return 0


def _cmd_classify(args) -> int:
    store = load(args.store)
    block = classify(store, args.deployment, _ctx(args), confirm=args.confirm, by=args.by,
                     basis=args.basis)
    save(args.store, store)
    print("%s  derived %s%s" % (args.deployment, block["derived"],
                                "  (truncated)" if block.get("truncated") else ""))
    if block.get("trace"):
        print("  trace: %s" % " -> ".join(block["trace"]))
    if not block.get("confirmed"):
        print("  no final level assigned yet — derivation proposes, a person assigns")
    return 0


def _cmd_map_exposure(args) -> int:
    store = load(args.store)
    exp = map_exposure(store, args.deployment, by=args.by)
    save(args.store, store)
    for cls in sorted(exp):
        entry = exp[cls]
        print("%s  %s (%s) — %s" % (cls, entry["name"], exposure_state(entry),
                                    entry["concern"]))
        print("    because: %s" % entry["because"])
    return 0


def _cmd_record_control(args) -> int:
    store = load(args.store)
    record_control(store, args.deployment, args.klass, args.control, args.evidence,
                   on=args.on, by=args.by)
    save(args.store, store)
    entry = find_deployment(store, args.deployment)["exposure"][args.klass]
    print("%s  %s — %d control(s) recorded" % (args.deployment, args.klass,
                                               len(entry["controls"])))
    print("  The class is still exposed. Controls are recorded, never resolved.")
    return 0


def _cmd_declare(args) -> int:
    store = load(args.store)
    raw = str(args.value).strip().lower()
    value = True if raw in ("true", "yes", "1") else (
        False if raw in ("false", "no", "0") else args.value)
    entry = declare_on_deployment(store, args.deployment, args.flag, value, args.by,
                                  basis=args.basis)
    save(args.store, store)
    print("%s  %s = %r, declared by %s on %s"
          % (args.deployment, args.flag, entry["value"], entry["declaredBy"],
             entry["declaredOn"]))
    return 0


def _cmd_ingest(args) -> int:
    store = load(args.store)
    entry = ingest(store, args.deployment, args.kind, args.tier, args.source,
                   scope=args.scope, period_start=args.period_start,
                   period_end=args.period_end, url=args.url, retrieved=args.retrieved,
                   by=args.by)
    save(args.store, store)
    print("%s  %s  %s (%s)" % (entry["id"], args.deployment, entry["kind"],
                               TIER_LABEL[entry["tier"]]))
    if entry["tier"] not in SATISFYING_TIERS:
        print("  %s cannot satisfy a requirement. It generates questions, which is a "
              "different and useful job." % entry["tier"])
    return 0


def _cmd_propose(args) -> int:
    store = load(args.store)
    entry = propose(store, args.deployment, args.requirement, args.evidence, args.citation,
                    note=args.note, by=args.by)
    save(args.store, store)
    print("%s  proposes %s from %s" % (entry["id"], entry["requirement"],
                                       entry["evidenceRef"]))
    print("  Nothing is satisfied yet. `assess --confirm %s --by NAME` is the act that "
          "closes it." % entry["id"])
    return 0


def _cmd_assess(args) -> int:
    store = load(args.store)
    entry = assess(store, args.deployment, args.by, on=args.on, confirm=args.confirm,
                   reject=args.reject, why=args.why, note=args.note)
    save(args.store, store)
    print("%s  assessed by %s on %s — %d confirmed, %d rejected"
          % (args.deployment, entry["by"], entry["on"], len(entry["confirmed"]),
             len(entry["rejected"])))
    return 0


def _cmd_record_requirement(args) -> int:
    store = load(args.store)
    entry = record_requirement(store, args.deployment, args.requirement, args.evidence,
                               met=not args.not_met, by=args.by)
    save(args.store, store)
    print("%s  %s: %s (checked by %s on %s)"
          % (args.deployment, entry["requirement"], "met" if entry["met"] else "NOT met",
             entry["checkedBy"], entry["checkedOn"]))
    if not entry["met"]:
        print("  This is a finding. `export-findings` carries it to risk-register, which "
              "scores it once, there.")
    return 0


def _cmd_ask(args) -> int:
    store = load(args.store)
    out = ask(store, args.deployment, _ctx(args), today=args.today)
    if args.json:
        print(json.dumps(out, indent=2, ensure_ascii=False))
        return 0
    print("%s — %s, autonomy %s, as at %s"
          % (out["deployment"], out["criticality"], out["autonomy"] or "undeclared",
             out["asOf"]))
    if out.get("note"):
        print("\n%s" % out["note"])
    for q in out["questions"]:
        print("\n[%s] %s" % (q["status"], q["key"]))
        print("  %s" % q["ask"])
        print("  against %s%s" % (", ".join(q["gvsc"]),
                                  ("; bears on %s" % ", ".join(q["nistaml"]))
                                  if q["nistaml"] else ""))
        print("  why: %s" % q["why"])
    for skip in out["skipped"]:
        print("\nskipped: %s — %s (declared by %s%s)"
              % (skip["battery"], skip["reason"], skip.get("declaredBy") or "nobody named",
                 (" on %s" % skip["declaredOn"]) if skip.get("declaredOn") else ""))
    return 0


def _cmd_analyze(args) -> int:
    store = load(args.store)
    out = analyze(store, today=args.today, context=_ctx(args))
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(out, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
    if args.json:
        print(json.dumps(out, indent=2, ensure_ascii=False))
        return 0
    print("%s — %d deployment(s) of %d system(s), as at %s"
          % (out["organisation"] or "(no entity recorded)", out["counts"]["deployments"],
             out["counts"]["systems"], out["asOf"]))
    print("  generative %d · unsanctioned %d · discovered %d"
          % (out["counts"]["generative"], out["counts"]["unsanctioned"],
             out["counts"]["discovered"]))
    print("  by criticality: %s"
          % (", ".join("%s %d" % (k, v)
                       for k, v in out["counts"]["byCriticality"].items()) or "none"))
    print("  by autonomy: %s"
          % ", ".join("%s %d" % (k, v) for k, v in out["counts"]["byAutonomy"].items()))
    print("  %d question(s) open, %d to re-confirm, %d proposal(s) awaiting a person"
          % (out["openQuestions"], out["reConfirmQuestions"], out["openProposals"]))
    print("  %d attack class(es) with no control recorded" % out["uncontrolledClasses"])
    for note in out["notes"]:
        print("  note: %s" % note)
    if out["escalations"]:
        print("\nEscalations")
        for e in out["escalations"]:
            print("  [%s] %s  %s" % (e["severity"], e["subjectRef"], e["trigger"]))
            print("        %s" % e["evidence"])
    if args.out:
        print("\nWrote %s" % args.out)
    return 0


def _write_json(payload: dict, out: str) -> None:
    if not out:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    print("Wrote %s" % out, file=sys.stderr)


def _cmd_export_signal(args) -> int:
    store = load(args.store)
    _write_json(export_signal(store, today=args.today), args.out)
    print("  Counts only. nist-csf still asks which focus areas apply; this is evidence for "
          "that question, not an answer to it.", file=sys.stderr)
    return 0


def _cmd_export_findings(args) -> int:
    store = load(args.store)
    payload = export_findings(store, today=args.today)
    _write_json(payload, args.out)
    print("  %d finding(s). Import with `score_register.py import-findings`, which scores "
          "them once, there." % len(payload["findings"]), file=sys.stderr)
    return 0


def _cmd_regimes(args) -> int:
    data = load_regimes(args.file)
    print("regime dataset %s, as at %s" % (data["datasetVersion"] or "(unversioned)",
                                           data["asOf"]))
    if not data["regimes"]:
        print("  No regimes ship. %s" % data["note"])
        return 0
    for regime in data["regimes"]:
        print("  %s  flag %s  role %s  %d obligation(s)"
              % (regime["id"], regime["flag"], regime["aiRole"],
                 len(regime.get("obligations") or [])))
        for ob in (regime.get("obligations") or []):
            print("    %s — owned by %s\n      source: %s"
                  % (ob.get("requirement") or ob.get("id"), ob["owningFunction"],
                     ob["source"]))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="ai_register.py",
                                description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)

    def store_arg(sp):
        sp.add_argument("store")
        return sp

    sp = store_arg(sub.add_parser("init"))
    sp.add_argument("--org", required=True)
    sp.add_argument("--prepared-by", default="")
    sp.add_argument("--scope-note", default="")
    sp.set_defaults(fn=_cmd_init)

    sp = store_arg(sub.add_parser("add-system"))
    sp.add_argument("--name", default="")
    sp.add_argument("--provider", default="")
    sp.add_argument("--version", default="")
    sp.add_argument("--family", default="")
    sp.add_argument("--base-model", default="",
                    help="where disclosed. Left empty rather than guessed.")
    sp.add_argument("--hosting", default="saas", choices=list(HOSTING))
    sp.add_argument("--predictive", action="store_true", help="not generative")
    sp.add_argument("--fine-tuned", action="store_true")
    sp.add_argument("--retrieval-augmented", action="store_true")
    sp.add_argument("--vendor", default="")
    sp.add_argument("--arrangement", default="", help="the vendor-register VA- id")
    sp.add_argument("--chain-note", default="")
    sp.add_argument("--by", default="")
    sp.set_defaults(fn=_cmd_add_system)

    sp = store_arg(sub.add_parser("intake-discovered"))
    sp.add_argument("--name", default="")
    sp.add_argument("--source", default="")
    sp.add_argument("--found-on", default="")
    sp.add_argument("--provider", default="")
    sp.add_argument("--by", default="")
    sp.set_defaults(fn=_cmd_intake_discovered)

    sp = store_arg(sub.add_parser("sanction"))
    sp.add_argument("--system", required=True)
    sp.add_argument("--state", required=True, choices=list(SANCTION))
    sp.add_argument("--by", default="")
    sp.add_argument("--why", default="")
    sp.set_defaults(fn=_cmd_sanction)

    sp = store_arg(sub.add_parser("deploy"))
    sp.add_argument("--system", required=True)
    sp.add_argument("--purpose", default="")
    sp.add_argument("--owner", default="")
    sp.add_argument("--autonomy", default="",
                    help="informs | recommends | decides | acts. Declared, never inferred.")
    sp.add_argument("--data-class", action="append", default=[])
    sp.add_argument("--connects", action="append", default=[])
    sp.add_argument("--supports", default="")
    sp.add_argument("--entity", default="")
    sp.add_argument("--consequential", action="store_true")
    sp.add_argument("--by", default="")
    sp.set_defaults(fn=_cmd_deploy)

    sp = store_arg(sub.add_parser("classify"))
    sp.add_argument("--deployment", required=True)
    sp.add_argument("--context", default="")
    sp.add_argument("--confirm", default="")
    sp.add_argument("--by", default="")
    sp.add_argument("--basis", default="")
    sp.set_defaults(fn=_cmd_classify)

    sp = store_arg(sub.add_parser("map-exposure"))
    sp.add_argument("--deployment", required=True)
    sp.add_argument("--by", default="")
    sp.set_defaults(fn=_cmd_map_exposure)

    sp = store_arg(sub.add_parser("record-control"))
    sp.add_argument("--deployment", required=True)
    sp.add_argument("--class", dest="klass", required=True)
    sp.add_argument("--control", default="")
    sp.add_argument("--evidence", default="",
                    help="required: what shows the control is in place and working")
    sp.add_argument("--on", default="")
    sp.add_argument("--by", default="")
    sp.set_defaults(fn=_cmd_record_control)

    sp = store_arg(sub.add_parser("declare"))
    sp.add_argument("--deployment", required=True)
    sp.add_argument("--flag", required=True,
                    help="a CAC-AP-1 flag. Outranks the org profile, in both directions.")
    sp.add_argument("--value", required=True)
    sp.add_argument("--by", default="")
    sp.add_argument("--basis", default="")
    sp.set_defaults(fn=_cmd_declare)

    sp = store_arg(sub.add_parser("ingest"))
    sp.add_argument("--deployment", required=True)
    sp.add_argument("--kind", default="",
                    help="model-card, system-card, red-team-report, penetration-test, "
                         "third-party-evaluation, dpa, dpia, questionnaire, trust-page")
    sp.add_argument("--tier", default="", choices=list(TIERS))
    sp.add_argument("--source", default="")
    sp.add_argument("--scope", default="", help="required for T1: what it covered")
    sp.add_argument("--period-start", default="")
    sp.add_argument("--period-end", default="")
    sp.add_argument("--url", default="")
    sp.add_argument("--retrieved", default="", help="required with --url")
    sp.add_argument("--by", default="")
    sp.set_defaults(fn=_cmd_ingest)

    sp = store_arg(sub.add_parser("propose"))
    sp.add_argument("--deployment", required=True)
    sp.add_argument("--requirement", default="", help="the question id this claims to cover")
    sp.add_argument("--evidence", required=True, help="the EV- id being read")
    sp.add_argument("--citation", default="",
                    help="required: the passage this reading rests on")
    sp.add_argument("--note", default="")
    sp.add_argument("--by", default="")
    sp.set_defaults(fn=_cmd_propose)

    sp = store_arg(sub.add_parser("assess"))
    sp.add_argument("--deployment", required=True)
    sp.add_argument("--by", default="", help="required: only a named person confirms")
    sp.add_argument("--on", default="")
    sp.add_argument("--confirm", action="append", default=[])
    sp.add_argument("--reject", action="append", default=[])
    sp.add_argument("--why", default="", help="required with --reject")
    sp.add_argument("--note", default="")
    sp.set_defaults(fn=_cmd_assess)

    sp = store_arg(sub.add_parser("record-requirement"))
    sp.add_argument("--deployment", required=True)
    sp.add_argument("--requirement", default="")
    sp.add_argument("--evidence", default="")
    sp.add_argument("--not-met", action="store_true")
    sp.add_argument("--by", default="")
    sp.set_defaults(fn=_cmd_record_requirement)

    sp = store_arg(sub.add_parser("ask"))
    sp.add_argument("--deployment", required=True)
    sp.add_argument("--context", default="")
    sp.add_argument("--today", default="")
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(fn=_cmd_ask)

    sp = store_arg(sub.add_parser("analyze"))
    sp.add_argument("--today", default="")
    sp.add_argument("--context", default="")
    sp.add_argument("--out", default="")
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(fn=_cmd_analyze)

    sp = store_arg(sub.add_parser("export-signal"))
    sp.add_argument("--today", default="")
    sp.add_argument("--out", default="")
    sp.set_defaults(fn=_cmd_export_signal)

    sp = store_arg(sub.add_parser("export-findings"))
    sp.add_argument("--today", default="")
    sp.add_argument("--out", default="")
    sp.set_defaults(fn=_cmd_export_findings)

    sp = sub.add_parser("regimes")
    sp.add_argument("--file", default="")
    sp.set_defaults(fn=_cmd_regimes)

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
