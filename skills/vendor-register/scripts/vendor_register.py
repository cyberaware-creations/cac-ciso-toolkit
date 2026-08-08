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
        if wf and str(wf.get("criticality") or "").strip():
            return str(wf["criticality"]).strip(), path, False
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
    if not str(requirement or "").strip():
        raise Refusal("--requirement names the contract provision being checked")
    if not str(evidence or "").strip():
        raise Refusal(
            "--evidence must reference what was actually read.\n"
            "  A requirement marked met with no evidence reference is an assertion about "
            "an agreement nobody opened, and it reads identically to one that was checked.")
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
