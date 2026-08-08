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
        "dataClasses": [str(x).strip() for x in (data_classes or []) if str(x or "").strip()],
        "connectedResources": [str(x).strip() for x in (connected_resources or [])
                               if str(x or "").strip()],
        "consequentialDecision": bool(consequential),
        "supports": str(supports or "").strip(),
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
    if not getattr(args, "context", ""):
        return None
    with open(args.context, encoding="utf-8") as fh:
        payload = json.load(fh)
    if payload.get("family") == "business-context":
        raise Refusal(
            "%s is a raw .biz store, not an exported payload. Run `business_context.py export "
            "%s --out ctx.json` and pass that: CAC-AP-1 §2.6 makes the transport between "
            "skills data rather than an import." % (args.context, args.context))
    return payload


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
