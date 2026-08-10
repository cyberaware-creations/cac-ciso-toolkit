#!/usr/bin/env python3
"""policy_register.py — which policies exist, who approved them, and what each one is aimed at.

The question this answers is the one every auditor asks every CISO every year: *show me your
policies and which requirement each one is meant to satisfy*. The toolkit had no answer, and
GV.PO was the only CSF 2.0 GOVERN category with no coverage at all.

WHAT THIS REGISTER WILL NOT SAY
-------------------------------
A mapped policy is never evidence that a requirement is met. "We have a policy for that",
accepted as "that risk is controlled", is the most common quiet untruth in this industry, and
a register that permitted the slide would make a CISO LESS defensible for having used it.

So a policy record supports exactly one claim, and the whole engine is shaped to make the
larger claim unavailable rather than merely discouraged:

    a document exists, a named person approved it on a date, and it is aimed at these
    requirements.

`REQUIREMENT_STATES` is the complete vocabulary a requirement row may carry, and every state
in it describes the DOCUMENTS, never the requirement. There is no state meaning covered, met,
satisfied or compliant, and `evals/no-coverage-claim.sh` fails if one is added.

The other five refusals:

  * counts, never percentages — a percentage of a requirement list is a completeness score
    for a catalogue nobody claimed was complete (`evals/no-coverage-percentage.sh`)
  * `approve` refuses without a named approver AND a date. Write-time only: a file that
    already carries the bad state still LOADS, because refusing to read it would strand the
    person who most needs to fix it
  * supersession, never deletion. There is no delete command anywhere, because the audit
    question is always *what was in force on the date of the incident*
    (`evals/no-deletion.sh`)
  * a requirement with no policy reads NOT DECLARED, never "no policy exists". Many
    organisations hold one omnibus policy across several control families
  * an overdue review flags. It never blocks, and it never removes anything from a view

ENTRY ANYWHERE, AND A PARTIAL PROGRAMME IS NORMAL (BL-169 D-1/D-2/D-4)
---------------------------------------------------------------------
This skill reads no other skill's store and requires none to have been run. The requirement
spine is vendored in `references/requirements.json`. An empty register is a legitimate state
that analyses cleanly and says what is not yet declared; every mutation leaves a schema-valid
file, so stopping half way through leaves a legible partial state rather than wreckage.

Standard library only. Subcommands:

  init          <store.pol> --org 'Name' [--owner ..] [--scope-note ..]
                            [--review-interval-days 365] [--due-window-days 30]
  add           <store.pol> --title '..' --owner '..' [--kind policy] [--version '1.0']
                            [--map AC-1]... [--review-interval-days N]
                            [--acknowledge on-hire,annual,on-update]
  approve       <store.pol> --id P-001 --by 'Name' --on YYYY-MM-DD [--next-review YYYY-MM-DD]
  revise        <store.pol> --id P-001 --version '2.0' --why '..'
  review        <store.pol> --id P-001 --on YYYY-MM-DD --next YYYY-MM-DD --why '..'
  supersede     <store.pol> --id P-001 --on YYYY-MM-DD --why '..' [--by-policy P-004]
  map           <store.pol> --id P-001 --requirement AC-1 [--requirement ..]
  unmap         <store.pol> --id P-001 --requirement AC-1 --why '..'
  requirements  <store.pol> [--today YYYY-MM-DD] [--format text|json] [--out FILE]
  analyze       <store.pol> [--today YYYY-MM-DD] [--out FILE]
  export        <store.pol> [--today ..] [--format csv|json] [--out FILE]
  self-test

This tool is not legal advice.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import os
import re
import sys
import tempfile
from datetime import date, datetime, timezone

SCHEMA_VERSION = 1
FAMILY = "policy-register"
DEFAULT_REVIEW_INTERVAL_DAYS = 365
DEFAULT_DUE_WINDOW_DAYS = 30

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
POLICY_ID_RE = re.compile(r"^P-\d{3,}$")

# --- The record kinds ---------------------------------------------------------
#
# `kind` ships in the schema from day one and defaults to `policy`. Only `policy` BEHAVES in
# this release. The field is here rather than added later because migrating a store already
# in the wild costs far more than an unused field, and a queued capability rides on the
# decision: CSF 2.0 ID.IM-04 — *"Incident response plans and other cybersecurity plans that
# affect operations are established, communicated, maintained, and improved"* — is this
# lifecycle exactly, with a different record kind. Carrying the discriminator removes an
# object from the suite rather than adding one.
#
# `plan` and `playbook` are separate reserved values rather than one because they are
# separate documents: a plan is strategic, a playbook is an actionable, system-specific set
# of steps. A store that rendered both identically would quietly encourage one document where
# two are wanted. No behaviour for either ships here, so neither makes any claim yet.
KIND_POLICY = "policy"
KINDS_WITH_BEHAVIOUR = (KIND_POLICY,)
KINDS_RESERVED = ("plan", "playbook")
KINDS = KINDS_WITH_BEHAVIOUR + KINDS_RESERVED

STATE_DRAFT = "draft"
STATE_APPROVED = "approved"
STATE_SUPERSEDED = "superseded"
POLICY_STATES = (STATE_DRAFT, STATE_APPROVED, STATE_SUPERSEDED)

# --- The requirement vocabulary — the load-bearing list -----------------------
#
# THE COMPLETE SET OF THINGS A REQUIREMENT ROW MAY SAY. Every member describes the DOCUMENTS
# mapped to the requirement. None of them describes the REQUIREMENT, because this register
# has no way to know whether a requirement is met and will not imply that it does.
#
# `no-coverage-claim.sh` asserts this tuple by value and by length, so adding "covered" here
# is a red run rather than a quiet expansion of what the product claims. That is deliberate:
# it is a one-line change nothing else in the codebase would object to, and it is the single
# most likely way this register turns into the thing it was built not to be.
REQ_NOT_DECLARED = "not-declared"
REQ_DRAFT_ONLY = "draft-only"
REQ_SUPERSEDED_ONLY = "superseded-only"
REQ_APPROVED_POLICY = "approved-policy"
REQUIREMENT_STATES = (REQ_NOT_DECLARED, REQ_DRAFT_ONLY, REQ_SUPERSEDED_ONLY,
                      REQ_APPROVED_POLICY)

REQUIREMENT_STATE_MEANS = {
    REQ_NOT_DECLARED:
        "No policy in this register names this requirement. That is not a finding that no "
        "policy exists — many organisations hold one omnibus policy across several control "
        "families and have simply not mapped it here yet.",
    REQ_DRAFT_ONLY:
        "Every policy mapped here is still a draft. Nobody has approved a document aimed at "
        "this requirement.",
    REQ_SUPERSEDED_ONLY:
        "Every policy mapped here has been superseded and nothing approved replaced it. This "
        "is the state that most often goes unnoticed.",
    REQ_APPROVED_POLICY:
        "At least one approved policy is aimed at this requirement. This says a document "
        "exists and a named person approved it on a date. It does not say the requirement "
        "is met, and this register cannot tell you whether it is.",
}

ACK_CADENCES = ("on-hire", "annual", "on-update")

# The fields without which a record does not exist, named here rather than checked inline so
# the list is one thing a reader can audit.
REQUIRED_ADD = ("title", "owner")
REQUIRED_APPROVE = ("by", "on")

WHY_FIELD_HELP = {
    "title": "an inventory of untitled documents cannot be reviewed",
    "owner": "a policy nobody owns is a file, not a governance instrument",
    "by": ("CSF GV.PO-01 asks the organisation to require approval from senior management on "
           "policy; 'approved' with nobody named records the opposite of that"),
    "on": "the date the approval happened is what an auditor asks for first",
    "version": "a revision that does not change the version is indistinguishable from the original",
    "why": "the act is the record — a state change with no stated reason is evidence of nothing",
    "requirement": "a mapping needs a requirement to map to",
    "next": "a review that sets no next date stops the cycle it was supposed to continue",
}

ESCALATION_SEVERITY_ORDER = ["high", "medium", "low"]


class Refusal(Exception):
    """A mutation the engine declines to perform.

    Raised before the store file is opened for writing, so a refused mutation leaves the file
    byte-identical. Asserted in self-test rather than trusted.
    """


# --- Dates --------------------------------------------------------------------

def check_date(value: str, field: str) -> str:
    """Canonical `YYYY-MM-DD`, and a real calendar date, or a refusal."""
    if not isinstance(value, str) or not DATE_RE.match(value):
        raise Refusal(
            "%s must be a canonical zero-padded date, YYYY-MM-DD; got %r. '2026-7-1' is "
            "refused because it sorts after '2026-10-01' as text, and every review state "
            "here compares dates." % (field, value))
    try:
        date.fromisoformat(value)
    except ValueError:
        raise Refusal("%s is not a real calendar date: %r" % (field, value))
    return value


def days_between(earlier: str, later: str) -> int:
    return (date.fromisoformat(later) - date.fromisoformat(earlier)).days


def add_days(start: str, days: int) -> str:
    return date.fromordinal(date.fromisoformat(start).toordinal() + int(days)).isoformat()


def now_ts() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


# --- The vendored requirement spine -------------------------------------------

def requirements_path() -> str:
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "references", "requirements.json")


def load_requirements(path: str = None) -> list:
    """The twenty SP 800-53 Rev. 5 '-1' controls plus CSF GV.PO-01/-02, as shipped.

    Read from this skill's own directory. No other skill is consulted, and none needs to be
    installed — that is BL-169 D-1, and it is why the list is vendored at all.
    """
    path = path or requirements_path()
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError) as exc:
        raise Refusal(
            "the vendored requirement spine at %s could not be read (%s). This skill ships "
            "it; a missing or malformed copy means the install is incomplete rather than "
            "that the organisation has no requirements." % (path, exc))
    reqs = data.get("requirements")
    if not isinstance(reqs, list) or not reqs:
        raise Refusal("%s carries no requirements; the requirement view would be empty and "
                      "would look like a clean bill" % path)
    return reqs


# --- Store IO -----------------------------------------------------------------

def new_store(org: str, owner: str = "", scope_note: str = "",
              review_interval_days: int = DEFAULT_REVIEW_INTERVAL_DAYS,
              due_window_days: int = DEFAULT_DUE_WINDOW_DAYS) -> dict:
    ts = now_ts()
    return {
        "schemaVersion": SCHEMA_VERSION,
        "family": FAMILY,
        "meta": {"orgName": org, "owner": owner, "scopeNote": scope_note, "asOf": ts[:10]},
        "settings": {"reviewIntervalDays": int(review_interval_days),
                     "dueWindowDays": int(due_window_days)},
        "policies": [],
        "history": [],
        "createdAt": ts,
        "updatedAt": ts,
    }


def load_store(path: str) -> dict:
    """Read a register.

    Deliberately tolerant of records that the WRITE path would refuse. `approved` with no
    approver cannot be written by this engine, but a file carrying it still loads — the
    person holding that file is the one who needs to see it and fix it, and a loader that
    refused would leave them with no way to look at their own register. The refusal belongs
    at write time; `analyze` reports the state instead.
    """
    try:
        with open(path, encoding="utf-8") as fh:
            store = json.load(fh)
    except FileNotFoundError:
        raise Refusal("no such register: %s" % path)
    except json.JSONDecodeError as exc:
        raise Refusal("%s is not valid JSON (line %d, column %d): %s"
                      % (path, exc.lineno, exc.colno, exc.msg))
    if not isinstance(store, dict):
        raise Refusal("%s must contain a JSON object, got %s" % (path, type(store).__name__))
    fam = store.get("family")
    if fam != FAMILY:
        raise Refusal(
            "%s is not a policy register: family is %r, expected %r. A risk register (.rr), "
            "CSF profile (.csfp), exceptions register (.exc) or metrics register (.mtr) "
            "belongs to a different skill." % (path, fam, FAMILY))
    if store.get("schemaVersion") != SCHEMA_VERSION:
        raise Refusal("%s is schemaVersion %r; this engine reads %d"
                      % (path, store.get("schemaVersion"), SCHEMA_VERSION))
    for key, kind in (("policies", list), ("history", list), ("meta", dict),
                      ("settings", dict)):
        if not isinstance(store.get(key), kind):
            raise Refusal("%s is missing or malformed %r" % (path, key))
    return store


def save_store(path: str, store: dict) -> None:
    store["updatedAt"] = now_ts()
    directory = os.path.dirname(os.path.abspath(path)) or "."
    fd, tmp = tempfile.mkstemp(dir=directory, suffix=".pol.tmp")
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


def next_id(store: dict) -> str:
    used = [int(r["id"].split("-")[1]) for r in store["policies"]
            if POLICY_ID_RE.match(r.get("id", ""))]
    return "P-%03d" % ((max(used) + 1) if used else 1)


def find_policy(store: dict, pid: str) -> dict:
    for rec in store["policies"]:
        if rec.get("id") == pid:
            return rec
    known = ", ".join(r.get("id", "?") for r in store["policies"]) or "none yet"
    raise Refusal("no policy %r in this register. Recorded: %s" % (pid, known))


def _require(fields: dict, names) -> None:
    """Refuse naming EVERY missing field at once, before the file is touched.

    One refusal listing three gaps beats three runs each finding one.
    """
    missing = [n for n in names if not str(fields.get(n) or "").strip()]
    if missing:
        lines = ["refused: %s" % ", ".join("--%s" % m.replace("_", "-") for m in missing)]
        for m in missing:
            lines.append("  --%-12s %s" % (m.replace("_", "-"), WHY_FIELD_HELP.get(m, "required")))
        raise Refusal("\n".join(lines))


# --- Mutations ----------------------------------------------------------------

def add_policy(store: dict, title: str, owner: str, kind: str = KIND_POLICY,
               version: str = "", mapped=(), review_interval_days=None,
               acknowledge=(), note: str = "", actor: str = "") -> dict:
    _require({"title": title, "owner": owner}, REQUIRED_ADD)
    kind = (kind or KIND_POLICY).strip().lower()
    if kind not in KINDS:
        raise Refusal("kind must be one of %s; got %r" % (", ".join(KINDS), kind))
    if kind not in KINDS_WITH_BEHAVIOUR:
        raise Refusal(
            "kind %r is reserved in the schema but ships no behaviour in this release. The "
            "field exists so a store written today does not need migrating when it does; "
            "recording a %s now would produce a record this engine cannot review, exercise "
            "or render honestly. Use kind %r." % (kind, kind, KIND_POLICY))
    for cad in acknowledge:
        if cad not in ACK_CADENCES:
            raise Refusal("acknowledgement cadence must be one of %s; got %r"
                          % (", ".join(ACK_CADENCES), cad))
    interval = int(review_interval_days if review_interval_days is not None
                   else store["settings"].get("reviewIntervalDays",
                                              DEFAULT_REVIEW_INTERVAL_DAYS))
    if interval <= 0:
        raise Refusal("review interval must be a positive number of days; got %r" % interval)

    rec = {
        "id": next_id(store),
        "kind": kind,
        "title": title.strip(),
        "owner": owner.strip(),
        "version": (version or "1.0").strip(),
        "state": STATE_DRAFT,
        "mappedTo": [],
        "approval": None,
        "review": {"intervalDays": interval, "lastOn": None, "nextOn": None},
        "acknowledgement": {"required": bool(acknowledge), "cadence": list(acknowledge)},
        "supersededOn": None,
        "supersededBy": None,
        "supersedes": None,
        "note": (note or "").strip(),
        "createdAt": now_ts(),
    }
    store["policies"].append(rec)
    append_history(store, "add", rec["id"], actor,
                   detail={"title": rec["title"], "kind": kind})
    if mapped:
        map_requirements(store, rec["id"], mapped, actor=actor)
    return rec


def approve(store: dict, pid: str, by: str, on: str, next_review: str = "",
            actor: str = "") -> dict:
    """R-3. No named approver and no date means the record does not become approved.

    Refused before the store is written, so nothing is half-applied.
    """
    _require({"by": by, "on": on}, REQUIRED_APPROVE)
    on = check_date(on, "--on")
    rec = find_policy(store, pid)
    if rec.get("state") == STATE_SUPERSEDED:
        raise Refusal(
            "%s was superseded on %s. Approving it again would put two documents in force "
            "for the same requirements with nothing recording which one governs. Add the "
            "replacement as its own record." % (pid, rec.get("supersededOn")))
    interval = int((rec.get("review") or {}).get("intervalDays")
                   or store["settings"].get("reviewIntervalDays",
                                            DEFAULT_REVIEW_INTERVAL_DAYS))
    nxt = check_date(next_review, "--next-review") if next_review else add_days(on, interval)
    rec["state"] = STATE_APPROVED
    rec["approval"] = {"by": by.strip(), "on": on, "version": rec.get("version")}
    rec["review"] = {"intervalDays": interval, "lastOn": on, "nextOn": nxt}
    append_history(store, "approve", pid, actor,
                   detail={"by": by.strip(), "on": on, "nextReview": nxt})
    return rec


def revise(store: dict, pid: str, version: str, why: str, actor: str = "") -> dict:
    """A new version is a draft again. The prior approval stays in history, not in force."""
    _require({"version": version, "why": why}, ("version", "why"))
    rec = find_policy(store, pid)
    if rec.get("state") == STATE_SUPERSEDED:
        raise Refusal("%s was superseded on %s; revise the document that replaced it"
                      % (pid, rec.get("supersededOn")))
    if str(version).strip() == str(rec.get("version") or "").strip():
        raise Refusal("%s is already version %r. %s"
                      % (pid, rec.get("version"), WHY_FIELD_HELP["version"]))
    previous = {"version": rec.get("version"), "approval": rec.get("approval")}
    rec["version"] = str(version).strip()
    rec["state"] = STATE_DRAFT
    rec["approval"] = None
    append_history(store, "revise", pid, actor, why=why, detail=previous)
    return rec


def review(store: dict, pid: str, on: str, nxt: str, why: str, actor: str = "") -> dict:
    """GV.PO-01: *periodically review policy*. Recorded as an act with a reason.

    A clock that resets itself is evidence of nothing, so `--why` is required — the same
    reasoning as the exceptions register's re-validation, and the same wording an auditor
    asks for.
    """
    _require({"on": on, "next": nxt, "why": why}, ("on", "next", "why"))
    on = check_date(on, "--on")
    nxt = check_date(nxt, "--next")
    if days_between(on, nxt) <= 0:
        raise Refusal("--next (%s) must fall after --on (%s); a review whose next date has "
                      "already passed schedules nothing" % (nxt, on))
    rec = find_policy(store, pid)
    if rec.get("state") == STATE_SUPERSEDED:
        raise Refusal("%s was superseded on %s; a superseded document is kept as the record "
                      "of what was in force, not reviewed onward" % (pid, rec.get("supersededOn")))
    block = dict(rec.get("review") or {})
    block["lastOn"] = on
    block["nextOn"] = nxt
    block.setdefault("intervalDays", store["settings"].get("reviewIntervalDays",
                                                           DEFAULT_REVIEW_INTERVAL_DAYS))
    rec["review"] = block
    append_history(store, "review", pid, actor, why=why, detail={"on": on, "next": nxt})
    return rec


def supersede(store: dict, pid: str, on: str, why: str, by_policy: str = "",
              actor: str = "") -> dict:
    """R-4. The only way a policy leaves force, and it stays in the file.

    There is no delete command in this engine and there is not going to be one. The audit
    question is always *what was in force on the date of the incident*, and a register that
    can answer it only for today answers the wrong question.

    `--by-policy` is optional because withdrawing a policy without a replacement is a real
    act. It is also the state that quietly goes wrong, so the requirement view surfaces it as
    `superseded-only` rather than letting the row fall silent.
    """
    _require({"on": on, "why": why}, ("on", "why"))
    on = check_date(on, "--on")
    rec = find_policy(store, pid)
    if rec.get("state") == STATE_SUPERSEDED:
        raise Refusal("%s was already superseded on %s" % (pid, rec.get("supersededOn")))
    successor = None
    if by_policy:
        if by_policy == pid:
            raise Refusal("%s cannot supersede itself" % pid)
        successor = find_policy(store, by_policy)
        if successor.get("state") == STATE_SUPERSEDED:
            raise Refusal("%s is itself superseded and cannot be named as the replacement "
                          "for %s" % (by_policy, pid))
    rec["state"] = STATE_SUPERSEDED
    rec["supersededOn"] = on
    rec["supersededBy"] = by_policy or None
    if successor is not None:
        successor["supersedes"] = pid
    append_history(store, "supersede", pid, actor, why=why,
                   detail={"on": on, "by": by_policy or None})
    return rec


def map_requirements(store: dict, pid: str, requirements, actor: str = "") -> dict:
    """Record that a document is AIMED AT these requirements. Nothing more than that."""
    reqs = [str(r).strip() for r in requirements if str(r).strip()]
    if not reqs:
        _require({"requirement": ""}, ("requirement",))
    rec = find_policy(store, pid)
    added = []
    for r in reqs:
        if r not in rec["mappedTo"]:
            rec["mappedTo"].append(r)
            added.append(r)
    if added:
        append_history(store, "map", pid, actor, detail={"requirements": added})
    return rec


def unmap_requirement(store: dict, pid: str, requirement: str, why: str,
                      actor: str = "") -> dict:
    """Remove a MAPPING, which is not a record.

    A mistyped mapping needs a way back or people stop mapping. This narrows one record's
    aim; it removes no document, and `no-deletion.sh` proves the distinction rather than
    trusting it — the policy count is asserted to be non-decreasing across every command in
    this module.
    """
    _require({"requirement": requirement, "why": why}, ("requirement", "why"))
    rec = find_policy(store, pid)
    requirement = str(requirement).strip()
    if requirement not in rec["mappedTo"]:
        raise Refusal("%s is not mapped to %r. Mapped: %s"
                      % (pid, requirement, ", ".join(rec["mappedTo"]) or "nothing"))
    rec["mappedTo"] = [r for r in rec["mappedTo"] if r != requirement]
    append_history(store, "unmap", pid, actor, why=why, detail={"requirement": requirement})
    return rec


# --- Derivation ---------------------------------------------------------------

def review_state(rec: dict, today: str, due_window_days: int):
    """(label, daysUntilDue) for an approved policy's review clock, or (None, None).

    Derived on every read and stored nowhere. R-6: this flags, it never blocks — no caller
    filters a record out on the strength of it.
    """
    if rec.get("state") != STATE_APPROVED:
        return None, None
    nxt = (rec.get("review") or {}).get("nextOn")
    if not nxt:
        return "no-review-date", None
    remaining = days_between(today, nxt)
    if remaining < 0:
        return "review-overdue", remaining
    if remaining <= int(due_window_days):
        return "review-due", remaining
    return "review-current", remaining


def requirement_rows(store: dict, today: str, requirements=None) -> list:
    """One row per shipped requirement, plus every mapped id this catalogue does not hold.

    The second half matters more than it looks. An organisation that maps a policy to
    'PCI DSS 12.1.1' has said something true, and dropping it because this register's spine
    is NIST-shaped would be an absence that looks exactly like a clean result. Those ids get
    their own rows, marked as outside the catalogue.
    """
    reqs = requirements if requirements is not None else load_requirements()
    window = int(store["settings"].get("dueWindowDays", DEFAULT_DUE_WINDOW_DAYS))
    by_req = {}
    for rec in store["policies"]:
        for r in rec.get("mappedTo") or []:
            by_req.setdefault(r, []).append(rec)

    def row_for(rid, base):
        mapped = by_req.get(rid, [])
        states = set(r.get("state") for r in mapped)
        if not mapped:
            state = REQ_NOT_DECLARED
        elif STATE_APPROVED in states:
            state = REQ_APPROVED_POLICY
        elif STATE_DRAFT in states:
            state = REQ_DRAFT_ONLY
        else:
            state = REQ_SUPERSEDED_ONLY
        out = dict(base)
        out["state"] = state
        out["means"] = REQUIREMENT_STATE_MEANS[state]
        out["policies"] = [{
            "id": r["id"], "title": r.get("title"), "version": r.get("version"),
            "state": r.get("state"),
            "approvedBy": (r.get("approval") or {}).get("by"),
            "approvedOn": (r.get("approval") or {}).get("on"),
            "reviewState": review_state(r, today, window)[0],
            "reviewNextOn": (r.get("review") or {}).get("nextOn"),
        } for r in mapped]
        out["policyCount"] = len(mapped)
        return out

    rows = []
    seen = set()
    for req in reqs:
        rid = req.get("id")
        seen.add(rid)
        rows.append(row_for(rid, {
            "id": rid, "label": req.get("label"), "familyId": req.get("familyId"),
            "familyLabel": req.get("familyLabel"), "catalogue": req.get("catalogue"),
            "inCatalogue": True,
        }))
    for rid in sorted(r for r in by_req if r not in seen):
        rows.append(row_for(rid, {
            "id": rid, "label": None, "familyId": None,
            "familyLabel": "Outside this register's catalogue",
            "catalogue": None, "inCatalogue": False,
        }))
    return rows


def state_counts(rows: list) -> dict:
    """Counts. Never a percentage — see `no-coverage-percentage.sh` and the module docstring.

    A percentage here would be a completeness figure for a catalogue nobody claimed was
    complete: twenty-two requirements is the NIST policy spine, not the organisation's
    obligations, and '68% covered' reads as a programme measurement to every board that has
    ever seen one.
    """
    counts = dict((s, 0) for s in REQUIREMENT_STATES)
    for row in rows:
        if row.get("inCatalogue"):
            counts[row["state"]] = counts.get(row["state"], 0) + 1
    return counts


# CAC-EL-1 §1.3. The six keys every escalation this register emits must carry, so that
# `attention-surface` and `board-pack` can read it without either of them patching the input.
# Declared here rather than assumed, because a consumer that fills a blank is inventing a fact.
ESCALATION_KEYS = ("evidence", "severity", "since", "subjectKind", "subjectRef", "trigger")


def _superseded_on(store: dict, row: dict) -> str:
    """The date a requirement lost its last document in force.

    Every policy mapped here is superseded — that is what `superseded-only` means — so the
    LATEST `supersededOn` among them is the day the cover ended. A recorded date, taken from
    the act that ended it, and never `today`: stamping now on a historic fact is BL-111, and
    this skill is young enough not to repeat it.
    """
    by_id = dict((r["id"], r) for r in store["policies"])
    dates = [str((by_id.get(p["id"]) or {}).get("supersededOn") or "")
             for p in (row.get("policies") or [])]
    dates = [d for d in dates if d]
    return max(dates) if dates else ""


def escalations(store: dict, today: str, rows: list = None) -> list:
    """Derived on every read, stored nowhere, and never a reason to withhold anything.

    **Two triggers, and the other three are an attention list.** `review-due`,
    `no-review-date` and `draft-only` were escalations until v0.70.0, which contradicted a
    rule four sibling skills state in nearly the same words — `exceptions-register`: *"Due is
    the attention list; overdue is an escalation… escalating a deadline nobody has missed
    teaches a reader to ignore the list by the second quarter."* A policy inside its review
    window is on schedule. Nothing has gone wrong yet, and saying it has, weekly, is how a
    surface trains its reader to skim. They live in `analyze()["attention"]` instead — see
    `attention_lists`, which is a review agenda rather than a claim that something failed.

    `draft-only` is the interesting one to demote and the reasoning is recorded because it
    will read as a mistake later. It shares its END STATE with `superseded-only`: neither
    requirement has an approved document in force. The distinction is not severity, it is
    whether the gap is VISIBLE. A draft is somebody's work in progress and the register shows
    it as a draft; a requirement covered only by superseded documents looks populated and is
    not, which is the state that goes unnoticed. Deceptive escalates. Visible does not.
    """
    rows = rows if rows is not None else requirement_rows(store, today)
    window = int(store["settings"].get("dueWindowDays", DEFAULT_DUE_WINDOW_DAYS))
    out = []

    def add(trigger, kind, ref, severity, since, evidence):
        out.append({"trigger": trigger, "subjectKind": kind, "subjectRef": ref,
                    "severity": severity, "since": since, "evidence": evidence})

    # Two subject kinds, deliberately. Three of this register's concerns are about a POLICY
    # and two about a REQUIREMENT, so `subjectKind` cannot be a constant the way it is in
    # vendor-register. A consumer grouping by subject must be able to tell a document that
    # went stale from an obligation nothing covers.
    for rec in store["policies"]:
        label, remaining = review_state(rec, today, window)
        if label != "review-overdue":
            continue
        nxt = (rec.get("review") or {}).get("nextOn")
        add("review-overdue", "policy", rec["id"], "high", nxt or "",
            "%s (%s) was due for review on %s, %d day(s) ago. "
            "GV.PO-02 asks that policy be updated to reflect changes in requirements, "
            "threats and technology. An unreviewed policy is still in force; nothing here "
            "removes it." % (rec.get("title"), rec["id"], nxt, -remaining))

    for row in rows:
        if not row.get("inCatalogue") or row["state"] != REQ_SUPERSEDED_ONLY:
            continue
        add("superseded-only", "requirement", row["id"], "high",
            _superseded_on(store, row),
            "%s — every policy mapped here has been superseded and nothing approved "
            "replaced it. This is the state that goes unnoticed: the register looks "
            "populated and the requirement has no document in force." % row["id"])

    order = dict((s, i) for i, s in enumerate(ESCALATION_SEVERITY_ORDER))
    out.sort(key=lambda e: (order.get(e["severity"], 99), e["subjectRef"]))
    return out


def attention_lists(policies: list, rows: list) -> dict:
    """The review agenda: things to look at, none of which has gone wrong yet.

    Beside `escalations`, never inside it, and the boundary is the whole point. An escalation
    says a line has been crossed. These three say a line is coming, or that a gap is visible
    to anyone reading the register. `exceptions-register` draws the same line in the same
    place and this is modelled on it.

    Ids only. A consumer that wants the record has the record — `policies` and `requirements`
    are in the same payload, and repeating their fields here would give two places to read
    one fact and one of them would go stale.
    """
    return {
        "reviewDue": [p["id"] for p in policies if p.get("reviewState") == "review-due"],
        "noReviewDate": [p["id"] for p in policies
                         if p.get("reviewState") == "no-review-date"],
        "draftOnly": [r["id"] for r in rows
                      if r.get("inCatalogue") and r["state"] == REQ_DRAFT_ONLY],
    }


def analyze(store: dict, today: str, requirements=None) -> dict:
    """The whole read model. Valid, legible and honest on an empty register (BL-169 D-2/D-4).

    An organisation that has recorded nothing gets twenty-two `not-declared` rows and a
    sentence saying so. That is the NORMAL starting state, not a fault, and nothing here
    nags about it.
    """
    check_date(today, "--today")
    rows = requirement_rows(store, today, requirements)
    window = int(store["settings"].get("dueWindowDays", DEFAULT_DUE_WINDOW_DAYS))
    policies = []
    for rec in store["policies"]:
        label, remaining = review_state(rec, today, window)
        item = dict(rec)
        item["reviewState"] = label
        item["daysUntilReview"] = remaining
        policies.append(item)
    counts = state_counts(rows)
    return {
        "family": FAMILY,
        "schemaVersion": SCHEMA_VERSION,
        "generatedAt": now_ts(),
        "today": today,
        "meta": dict(store.get("meta") or {}),
        "settings": dict(store.get("settings") or {}),
        "policies": policies,
        "policyCount": len(policies),
        "requirements": rows,
        "requirementCount": sum(1 for r in rows if r.get("inCatalogue")),
        "outsideCatalogueCount": sum(1 for r in rows if not r.get("inCatalogue")),
        "stateCounts": counts,
        "stateMeans": dict(REQUIREMENT_STATE_MEANS),
        "escalations": escalations(store, today, rows),
        # Beside `escalations`, not inside it. A line crossed against a line coming — the
        # same boundary `exceptions-register` draws, and the reason `review-due` stopped
        # escalating in v0.70.0.
        "attention": attention_lists(policies, rows),
        "limits": [
            "A mapped policy records that a document exists, that a named person approved "
            "it on a date, and what it is aimed at. It is not evidence that the requirement "
            "is met, and this register has no way to determine whether it is.",
            "The twenty-two requirements here are the NIST policy spine — the '-1' Policy "
            "and Procedures control in each SP 800-53 Rev. 5 family, plus CSF 2.0 GV.PO-01 "
            "and GV.PO-02. They are not the organisation's obligations, so counts are "
            "reported and proportions are not.",
            "Not legal advice.",
        ],
    }


EXPORT_COLUMNS = ("id", "kind", "title", "owner", "version", "state", "approvedBy",
                  "approvedOn", "reviewLastOn", "reviewNextOn", "reviewState",
                  "supersededOn", "supersededBy", "mappedTo")


def export_rows(store: dict, today: str) -> list:
    window = int(store["settings"].get("dueWindowDays", DEFAULT_DUE_WINDOW_DAYS))
    rows = []
    for rec in store["policies"]:
        approval = rec.get("approval") or {}
        rev = rec.get("review") or {}
        rows.append({
            "id": rec.get("id"), "kind": rec.get("kind"), "title": rec.get("title"),
            "owner": rec.get("owner"), "version": rec.get("version"),
            "state": rec.get("state"),
            "approvedBy": approval.get("by") or "", "approvedOn": approval.get("on") or "",
            "reviewLastOn": rev.get("lastOn") or "", "reviewNextOn": rev.get("nextOn") or "",
            "reviewState": review_state(rec, today, window)[0] or "",
            "supersededOn": rec.get("supersededOn") or "",
            "supersededBy": rec.get("supersededBy") or "",
            "mappedTo": " ".join(rec.get("mappedTo") or []),
        })
    return rows


def export_csv(rows: list) -> str:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(EXPORT_COLUMNS), lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return buf.getvalue()


def render_requirements_text(result: dict) -> str:
    """The plain-text requirement view. What an auditor is shown first."""
    lines = []
    meta = result.get("meta") or {}
    lines.append("Policy register — requirement view")
    lines.append("%s · as at %s" % (meta.get("orgName") or "(no organisation recorded)",
                                    result["today"]))
    lines.append("")
    counts = result["stateCounts"]
    lines.append("Of %d requirements in this register's catalogue: %s."
                 % (result["requirementCount"],
                    ", ".join("%d %s" % (counts[s], s) for s in REQUIREMENT_STATES)))
    lines.append("")
    family = None
    for row in result["requirements"]:
        if row.get("familyLabel") != family:
            family = row.get("familyLabel")
            lines.append("  %s" % family)
        docs = ", ".join("%s %s (%s)" % (p["id"], p["version"], p["state"])
                         for p in row["policies"]) or "—"
        lines.append("    %-10s %-18s %s" % (row["id"], row["state"], docs))
    lines.append("")
    for note in result["limits"]:
        lines.append("* %s" % note)
    return "\n".join(lines) + "\n"


# --- Self-test ----------------------------------------------------------------

def _cmd_self_test(_args):
    """Deterministic assertions over the engine. Every check counted, none vacuous."""
    checks = [0]
    fails = []

    def ok(label):
        checks[0] += 1

    def check(label, condition, detail=""):
        checks[0] += 1
        if not condition:
            fails.append("%s%s" % (label, (" — %s" % detail) if detail else ""))

    def refuses(label, fn, must_mention=()):
        checks[0] += 1
        try:
            fn()
        except Refusal as exc:
            missing = [m for m in must_mention if m not in str(exc)]
            if missing:
                fails.append("%s — refused, but the message never mentions %s"
                             % (label, ", ".join(repr(m) for m in missing)))
            return
        except Exception as exc:  # noqa: BLE001 — a crash is not a refusal
            fails.append("%s — raised %s instead of Refusal: %s"
                         % (label, type(exc).__name__, exc))
            return
        fails.append("%s — was permitted" % label)

    reqs = load_requirements()
    check("the vendored spine holds 22 requirements", len(reqs) == 22, "got %d" % len(reqs))
    dash_one = [r for r in reqs if re.match(r"^[A-Z]{2}-1$", r["id"])]
    check("twenty of them are SP 800-53 Rev. 5 '-1' controls", len(dash_one) == 20,
          "got %d" % len(dash_one))
    check("and two are CSF GV.PO subcategories",
          sorted(r["id"] for r in reqs if r["id"].startswith("GV.PO")) ==
          ["GV.PO-01", "GV.PO-02"])
    check("every requirement carries a family label",
          all(str(r.get("familyLabel") or "").strip() for r in reqs))

    # --- the vocabulary that carries the product's honesty --------------------
    check("there are exactly four requirement states", len(REQUIREMENT_STATES) == 4,
          "got %d: %s" % (len(REQUIREMENT_STATES), REQUIREMENT_STATES))
    # Written out rather than derived, so a renamed or added state fails here. The check that
    # no state uses coverage VOCABULARY lives in evals/no-coverage-claim.sh, which owns that
    # rule for the whole skill — a denylist of coverage words kept in this file would itself
    # be a set of coverage tokens in shipped source, and that guard would rightly flag it.
    check("the four states are exactly the ones the guards were written against",
          REQUIREMENT_STATES == ("not-declared", "draft-only", "superseded-only",
                                 "approved-policy"), REQUIREMENT_STATES)
    check("every state has a plain-English meaning recorded",
          set(REQUIREMENT_STATE_MEANS) == set(REQUIREMENT_STATES))
    check("the approved-policy meaning says explicitly that it is not a coverage claim",
          "does not say the requirement is met"
          in REQUIREMENT_STATE_MEANS[REQ_APPROVED_POLICY])

    # --- the store ------------------------------------------------------------
    store = new_store("Probe Ltd", owner="Head of Security")
    check("a new register is empty", store["policies"] == [])
    empty = analyze(store, "2026-08-09")
    check("an empty register still analyses", empty["requirementCount"] == 22)
    check("and every requirement reads not-declared",
          empty["stateCounts"][REQ_NOT_DECLARED] == 22, empty["stateCounts"])
    check("an empty register raises no escalation", empty["escalations"] == [],
          empty["escalations"])
    check("and says in its own output that a mapped policy is not evidence",
          any("not evidence that the requirement is met" in n for n in empty["limits"]))

    # --- add / R-3 approve refusal -------------------------------------------
    refuses("add without a title", lambda: add_policy(store, "", "Owner"), ("--title",))
    refuses("add without an owner", lambda: add_policy(store, "Access Control Policy", ""),
            ("--owner",))
    check("neither refusal wrote a record", len(store["policies"]) == 0,
          "%d record(s) present" % len(store["policies"]))

    rec = add_policy(store, "Access Control Policy", "Head of Security",
                     mapped=["AC-1", "IA-1"], acknowledge=("on-hire", "annual"))
    check("a new policy starts as a draft", rec["state"] == STATE_DRAFT)
    check("a new policy defaults to kind 'policy'", rec["kind"] == KIND_POLICY)
    check("and carries its mappings", rec["mappedTo"] == ["AC-1", "IA-1"])
    refuses("a reserved kind that ships no behaviour",
            lambda: add_policy(store, "IR Plan", "Head of Security", kind="plan"),
            ("plan", "reserved"))
    refuses("an unknown kind", lambda: add_policy(store, "X", "Y", kind="charter"))
    check("kind carries all three values in the schema", len(KINDS) == 3, KINDS)

    refuses("approve with no approver named",
            lambda: approve(store, rec["id"], "", "2026-01-15"), ("--by",))
    refuses("approve with no date",
            lambda: approve(store, rec["id"], "Board", ""), ("--on",))
    refuses("approve naming neither",
            lambda: approve(store, rec["id"], "", ""), ("--by", "--on"))
    refuses("approve with a non-canonical date",
            lambda: approve(store, rec["id"], "Board", "2026-1-15"), ("YYYY-MM-DD",))
    check("none of the refused approvals changed the state",
          store["policies"][0]["state"] == STATE_DRAFT)
    check("and none of them wrote an approval block",
          store["policies"][0]["approval"] is None)

    approve(store, rec["id"], "The Board", "2026-01-15")
    check("an approved policy records who and when",
          rec["approval"] == {"by": "The Board", "on": "2026-01-15", "version": "1.0"})
    check("and gets a next review date derived from its interval",
          rec["review"]["nextOn"] == "2027-01-15", rec["review"])

    # --- R-3 is write-time only ----------------------------------------------
    bad = new_store("Legacy Ltd")
    bad["policies"].append({"id": "P-001", "kind": "policy", "title": "Imported",
                            "owner": "?", "version": "1.0", "state": STATE_APPROVED,
                            "mappedTo": ["AC-1"], "approval": None,
                            "review": {"intervalDays": 365, "lastOn": None, "nextOn": None},
                            "acknowledgement": {"required": False, "cadence": []},
                            "supersededOn": None, "supersededBy": None, "supersedes": None,
                            "note": "", "createdAt": now_ts()})
    import tempfile as _tf
    fd, tmp = _tf.mkstemp(suffix=".pol")
    os.close(fd)
    try:
        save_store(tmp, bad)
        reloaded = load_store(tmp)
        check("a file already carrying approved-with-no-approver still LOADS",
              reloaded["policies"][0]["state"] == STATE_APPROVED)
        got = analyze(reloaded, "2026-08-09")
        check("and analyze reports it rather than hiding it",
              "P-001" in got["attention"]["noReviewDate"], got["attention"])
        check("as an agenda item and not as an escalation, because no date was missed",
              not [e for e in got["escalations"]
                   if e["trigger"] == "no-review-date"],
              [e["trigger"] for e in got["escalations"]])
    finally:
        os.unlink(tmp)

    # --- the requirement view -------------------------------------------------
    result = analyze(store, "2026-06-01")
    rows = dict((r["id"], r) for r in result["requirements"])
    check("a mapped, approved requirement reads approved-policy",
          rows["AC-1"]["state"] == REQ_APPROVED_POLICY, rows["AC-1"]["state"])
    check("an unmapped requirement reads not-declared",
          rows["PE-1"]["state"] == REQ_NOT_DECLARED)
    check("and says so without claiming no policy exists",
          "not a finding that no policy exists" in rows["PE-1"]["means"])
    check("the counts add up to the catalogue size",
          sum(result["stateCounts"].values()) == 22, result["stateCounts"])

    draft = add_policy(store, "Physical Security Policy", "Facilities", mapped=["PE-1"])
    rows = dict((r["id"], r) for r in analyze(store, "2026-06-01")["requirements"])
    check("a requirement mapped only by a draft reads draft-only",
          rows["PE-1"]["state"] == REQ_DRAFT_ONLY, rows["PE-1"]["state"])

    # --- an id outside the catalogue is shown, never dropped ------------------
    map_requirements(store, draft["id"], ["PCI DSS 12.1.1"])
    result = analyze(store, "2026-06-01")
    outside = [r for r in result["requirements"] if not r["inCatalogue"]]
    check("a mapped id outside the catalogue gets its own row", len(outside) == 1, outside)
    check("and is not counted against the catalogue",
          result["requirementCount"] == 22 and result["outsideCatalogueCount"] == 1)

    # --- R-4 supersession, never deletion -------------------------------------
    before = len(store["policies"])
    refuses("supersede with no reason", lambda: supersede(store, draft["id"], "2026-07-01", ""),
            ("--why",))
    replacement = add_policy(store, "Physical Security Policy", "Facilities",
                             version="2.0", mapped=["PE-1"])
    approve(store, replacement["id"], "The Board", "2026-07-01")
    supersede(store, draft["id"], "2026-07-01", "Replaced by the 2.0 issue.",
              by_policy=replacement["id"])
    check("superseding adds a record and removes none",
          len(store["policies"]) == before + 1, len(store["policies"]))
    check("the superseded policy is still in the file",
          any(p["id"] == draft["id"] for p in store["policies"]))
    check("and still appears in the requirement view",
          any(p["id"] == draft["id"]
              for p in dict((r["id"], r) for r in
                            analyze(store, "2026-07-02")["requirements"])["PE-1"]["policies"]))
    check("the successor records what it replaced",
          replacement["supersedes"] == draft["id"])
    refuses("superseding the same record twice",
            lambda: supersede(store, draft["id"], "2026-08-01", "again"))
    refuses("approving a superseded policy",
            lambda: approve(store, draft["id"], "The Board", "2026-08-01"),
            ("superseded",))
    check("this engine exposes no command that deletes a record",
          not [n for n in COMMANDS if re.search(r"delete|remove|destroy|purge|drop", n)],
          [n for n in COMMANDS if re.search(r"delete|remove|destroy|purge|drop", n)])

    # a requirement whose only policy is superseded
    orphan = add_policy(store, "Media Protection Policy", "IT", mapped=["MP-1"])
    approve(store, orphan["id"], "The Board", "2026-02-01")
    supersede(store, orphan["id"], "2026-06-15", "Withdrawn pending a rewrite.")
    result = analyze(store, "2026-07-02")
    rows = dict((r["id"], r) for r in result["requirements"])
    check("a requirement left with only a superseded policy reads superseded-only",
          rows["MP-1"]["state"] == REQ_SUPERSEDED_ONLY, rows["MP-1"]["state"])
    sup = [e for e in result["escalations"]
           if e["trigger"] == "superseded-only" and e["subjectRef"] == "MP-1"]
    check("and escalates as high", sup and sup[0]["severity"] == "high", result["escalations"])
    check("against a requirement, not a policy", sup and sup[0]["subjectKind"] == "requirement")
    check("dated from the supersession that ended the cover, never from today",
          sup and sup[0]["since"] == "2026-06-15", sup and sup[0]["since"])

    # --- R-6 an overdue review flags and never blocks -------------------------
    late = analyze(store, "2028-01-01")
    overdue = [e for e in late["escalations"] if e["trigger"] == "review-overdue"]
    check("an overdue review raises an escalation", overdue, late["escalations"])
    check("and the policy is still in the register", len(late["policies"]) == len(store["policies"]))
    check("and still appears in its requirement rows",
          dict((r["id"], r) for r in late["requirements"])["AC-1"]["policyCount"] == 1)
    check("nothing about being overdue is written into the store",
          all("reviewState" not in p and "escalation" not in p
              for p in store["policies"]),
          "a derived field was persisted")

    # --- CAC-EL-1 §1.3, the shape the consumers read --------------------------
    #
    # Iterated from ESCALATION_KEYS rather than listed by hand. A hand-written list is a
    # second copy of the contract that can drift from the first, and the drift would be
    # invisible: both would be wrong in the same direction and agree with each other.
    missing = [(e.get("trigger"), k) for e in late["escalations"]
               for k in ESCALATION_KEYS if k not in e]
    check("every escalation carries all six CAC-EL-1 keys", not missing, missing)
    check("and the key set is the contract, not a longer one",
          all(set(e) == set(ESCALATION_KEYS) for e in late["escalations"]),
          [sorted(set(e) - set(ESCALATION_KEYS)) for e in late["escalations"]])
    check("the overdue escalation is dated from the review date that passed",
          overdue and overdue[0]["since"] == "2027-01-15", overdue and overdue[0]["since"])
    check("and names a policy as its subject",
          overdue and overdue[0]["subjectKind"] == "policy")
    check("the CSF grounding survives into evidence",
          overdue and "GV.PO-02" in overdue[0]["evidence"])
    check("no escalation carries a `since` of today — a derived date is not a recorded one",
          all(e["since"] != "2028-01-01" for e in late["escalations"]),
          [e["since"] for e in late["escalations"]])

    # --- the demotion, asserted from both sides -------------------------------
    #
    # Both halves, because only asserting the absence would pass just as well if the states
    # had been deleted rather than moved. Due must be ON the agenda AND off the escalations.
    triggers = set(e["trigger"] for e in late["escalations"])
    check("review-due, no-review-date and draft-only no longer escalate",
          not (triggers & {"review-due", "no-review-date", "draft-only"}), sorted(triggers))
    check("and the only two triggers this register emits are the two that are clocks or gaps",
          triggers <= {"review-overdue", "superseded-only"}, sorted(triggers))
    # Inside the 30-day window ahead of the 2027-01-15 next review, so the same record that
    # escalates above is merely due here. One record, two dates, two different lists.
    soon = analyze(store, "2026-12-20")
    check("a policy due inside the window is on the agenda",
          soon["attention"]["reviewDue"], soon["attention"])
    check("and is not escalating, because nobody has missed anything",
          "review-due" not in [e["trigger"] for e in soon["escalations"]])

    # --- review is an act, not a timer ----------------------------------------
    refuses("a review with no reason",
            lambda: review(store, rec["id"], "2027-01-10", "2028-01-10", ""), ("--why",))
    refuses("a review whose next date precedes it",
            lambda: review(store, rec["id"], "2027-01-10", "2026-01-10", "x"),
            ("must fall after",))
    review(store, rec["id"], "2027-01-10", "2028-01-10", "Reviewed with the risk committee.")
    check("a recorded review moves the next date", rec["review"]["nextOn"] == "2028-01-10")
    check("and lands in history with its reason",
          any(h["event"] == "review" and h.get("why") for h in store["history"]))

    # --- revise ---------------------------------------------------------------
    refuses("a revision to the same version",
            lambda: revise(store, rec["id"], rec["version"], "no change"), ("already version",))
    revise(store, rec["id"], "2.0", "Rewritten for the new joiner process.")
    check("a revision returns the policy to draft", rec["state"] == STATE_DRAFT)
    check("and clears the approval, because the new text is not the approved text",
          rec["approval"] is None)
    revised = analyze(store, "2027-02-01")
    rows = dict((r["id"], r) for r in revised["requirements"])
    check("so its requirement drops back to draft-only",
          rows["IA-1"]["state"] == REQ_DRAFT_ONLY, rows["IA-1"]["state"])
    check("and lands on the review agenda, not in the escalations",
          "IA-1" in revised["attention"]["draftOnly"]
          and "draft-only" not in [e["trigger"] for e in revised["escalations"]],
          revised["attention"])

    # --- mapping --------------------------------------------------------------
    refuses("mapping to nothing", lambda: map_requirements(store, rec["id"], []),
            ("--requirement",))
    refuses("unmapping something that was never mapped",
            lambda: unmap_requirement(store, rec["id"], "SR-1", "typo"), ("not mapped",))
    refuses("unmapping with no reason",
            lambda: unmap_requirement(store, rec["id"], "AC-1", ""), ("--why",))
    before = len(store["policies"])
    unmap_requirement(store, rec["id"], "IA-1", "Mapped in error; IA is a separate document.")
    check("unmapping narrows the aim", "IA-1" not in rec["mappedTo"])
    check("and removes no record", len(store["policies"]) == before)

    # --- percentages ----------------------------------------------------------
    blob = json.dumps(analyze(store, "2026-07-02"))
    check("no analyze output contains a percent sign", "%" not in blob,
          blob[max(0, blob.find("%") - 60):blob.find("%") + 20])
    text = render_requirements_text(analyze(store, "2026-07-02"))
    check("nor does the rendered requirement view", "%" not in text)
    check("and it reports the catalogue size as a count", "Of 22 requirements" in text)

    # --- export ---------------------------------------------------------------
    rows = export_rows(store, "2026-07-02")
    check("export carries every record", len(rows) == len(store["policies"]))
    csv_text = export_csv(rows)
    check("the CSV header matches the declared columns",
          csv_text.splitlines()[0] == ",".join(EXPORT_COLUMNS))
    check("and a superseded record is in the export too",
          any(r["id"] == draft["id"] for r in rows))

    # --- load refusals --------------------------------------------------------
    fd, tmp = _tf.mkstemp(suffix=".pol")
    os.close(fd)
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump({"family": "risk-register", "schemaVersion": 1}, fh)
        refuses("loading another skill's store", lambda: load_store(tmp), ("family",))
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write("{not json")
        refuses("loading malformed JSON", lambda: load_store(tmp), ("not valid JSON",))
    finally:
        os.unlink(tmp)
    refuses("loading a file that is not there", lambda: load_store(tmp + ".missing"))

    print("policy-register self-test: %d checks" % checks[0])
    if fails:
        print("FAILED:")
        for f in fails:
            print("  - %s" % f)
        return 1
    if checks[0] < 60:
        print("FAILED: only %d checks ran; this self-test is supposed to be substantial "
              "and a shrinking count is how it stops testing anything" % checks[0])
        return 1
    print("all %d checks passed" % checks[0])
    return 0


# --- CLI ----------------------------------------------------------------------

def _today(args) -> str:
    return check_date(args.today, "--today") if args.today else date.today().isoformat()


def _cmd_init(args):
    if os.path.exists(args.store):
        raise Refusal("%s already exists; init would overwrite a register. Delete it "
                      "yourself if that is what you mean." % args.store)
    store = new_store(args.org, owner=args.owner or "", scope_note=args.scope_note or "",
                      review_interval_days=args.review_interval_days,
                      due_window_days=args.due_window_days)
    save_store(args.store, store)
    print("initialised %s for %s — 0 policies, %d requirements not declared"
          % (args.store, args.org, len(load_requirements())))
    return 0


def _cmd_add(args):
    store = load_store(args.store)
    ack = tuple(c.strip() for c in (args.acknowledge or "").split(",") if c.strip())
    rec = add_policy(store, args.title, args.owner, kind=args.kind, version=args.version,
                     mapped=args.map or (), review_interval_days=args.review_interval_days,
                     acknowledge=ack, note=args.note or "", actor=args.by or "")
    save_store(args.store, store)
    print("%s added as a draft — %s v%s, owned by %s%s"
          % (rec["id"], rec["title"], rec["version"], rec["owner"],
             (", aimed at " + ", ".join(rec["mappedTo"])) if rec["mappedTo"] else ""))
    return 0


def _cmd_approve(args):
    store = load_store(args.store)
    rec = approve(store, args.id, args.by_person or "", args.on or "",
                  next_review=args.next_review or "", actor=args.actor or "")
    save_store(args.store, store)
    print("%s approved by %s on %s; next review %s"
          % (rec["id"], rec["approval"]["by"], rec["approval"]["on"], rec["review"]["nextOn"]))
    return 0


def _cmd_revise(args):
    store = load_store(args.store)
    rec = revise(store, args.id, args.version or "", args.why or "", actor=args.actor or "")
    save_store(args.store, store)
    print("%s is now version %s and back to draft; the previous approval is in history, "
          "not in force" % (rec["id"], rec["version"]))
    return 0


def _cmd_review(args):
    store = load_store(args.store)
    rec = review(store, args.id, args.on or "", args.next or "", args.why or "",
                 actor=args.actor or "")
    save_store(args.store, store)
    print("%s reviewed on %s; next review %s"
          % (rec["id"], rec["review"]["lastOn"], rec["review"]["nextOn"]))
    return 0


def _cmd_supersede(args):
    store = load_store(args.store)
    rec = supersede(store, args.id, args.on or "", args.why or "",
                    by_policy=args.by_policy or "", actor=args.actor or "")
    save_store(args.store, store)
    print("%s superseded on %s%s — it stays in the register, because the audit question is "
          "what was in force at the time"
          % (rec["id"], rec["supersededOn"],
             (" by %s" % rec["supersededBy"]) if rec["supersededBy"] else
             " with no replacement recorded"))
    return 0


def _cmd_map(args):
    store = load_store(args.store)
    rec = map_requirements(store, args.id, args.requirement or (), actor=args.actor or "")
    save_store(args.store, store)
    print("%s is aimed at %s" % (rec["id"], ", ".join(rec["mappedTo"])))
    return 0


def _cmd_unmap(args):
    store = load_store(args.store)
    rec = unmap_requirement(store, args.id, args.requirement or "", args.why or "",
                            actor=args.actor or "")
    save_store(args.store, store)
    print("%s is aimed at %s" % (rec["id"], ", ".join(rec["mappedTo"]) or "nothing"))
    return 0


def _write(path, text):
    if path:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        print("wrote %s" % path)
    else:
        sys.stdout.write(text)


def _cmd_requirements(args):
    result = analyze(load_store(args.store), _today(args))
    if args.format == "json":
        _write(args.out, json.dumps(result["requirements"], indent=2, ensure_ascii=False) + "\n")
    else:
        _write(args.out, render_requirements_text(result))
    return 0


ATTENTION_LABEL = {
    "reviewDue": "due for review inside the window",
    "noReviewDate": "approved with no next review date",
    "draftOnly": "covered only by a draft",
}


def _cmd_analyze(args):
    result = analyze(load_store(args.store), _today(args))
    # `--json`, not a changed default. `vendor_register.py` and `ai_register.py` take the same
    # flag and `attention-surface`'s PRODUCERS table already calls them with it. Making JSON
    # the default would replace the human summary for everybody running this at a terminal,
    # which is a break for a reason that has nothing to do with them.
    if args.out or getattr(args, "json", False):
        _write(args.out, json.dumps(result, indent=2, ensure_ascii=False) + "\n")
        return 0
    counts = result["stateCounts"]
    print("%s — %d policy record(s), %d requirement(s) in catalogue"
          % (result["meta"].get("orgName") or args.store, result["policyCount"],
             result["requirementCount"]))
    print("  " + ", ".join("%d %s" % (counts[s], s) for s in REQUIREMENT_STATES))
    if result["escalations"]:
        print("  %d escalation(s):" % len(result["escalations"]))
        for e in result["escalations"]:
            print("    [%s] %s" % (e["severity"], e["evidence"]))
    else:
        print("  no escalations")
    # Printed even when empty, and named as an agenda rather than a fault. A reader who sees
    # "no escalations" and nothing else cannot tell a register with three reviews due next
    # week from one with nothing coming at all.
    attention = result["attention"]
    total = sum(len(v) for v in attention.values())
    if total:
        print("  %d on the review agenda (nothing has gone wrong yet):" % total)
        for key in ("reviewDue", "noReviewDate", "draftOnly"):
            if attention[key]:
                print("    %s: %s" % (ATTENTION_LABEL[key], ", ".join(attention[key])))
    else:
        print("  nothing on the review agenda")
    for note in result["limits"]:
        print("* %s" % note)
    return 0


def _cmd_export(args):
    store = load_store(args.store)
    rows = export_rows(store, _today(args))
    if args.format == "json":
        _write(args.out, json.dumps(rows, indent=2, ensure_ascii=False) + "\n")
    else:
        _write(args.out, export_csv(rows))
    return 0


# Named here so the no-deletion guard and the self-test can both read the surface as data
# rather than parsing argparse internals. Every subcommand this engine offers is in this map,
# and there is no entry that removes a record.
COMMANDS = {
    "init": _cmd_init,
    "add": _cmd_add,
    "approve": _cmd_approve,
    "revise": _cmd_revise,
    "review": _cmd_review,
    "supersede": _cmd_supersede,
    "map": _cmd_map,
    "unmap": _cmd_unmap,
    "requirements": _cmd_requirements,
    "analyze": _cmd_analyze,
    "export": _cmd_export,
    "self-test": _cmd_self_test,
}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="policy_register.py",
        description="Which policies exist, who approved them, and what each is aimed at. "
                    "A mapped policy is never evidence that a requirement is met.")
    sub = p.add_subparsers(dest="command", metavar="COMMAND")

    def store_arg(sp):
        sp.add_argument("store", help="path to the .pol register")

    sp = sub.add_parser("init", help="create a register")
    store_arg(sp)
    sp.add_argument("--org", required=True)
    sp.add_argument("--owner", default="")
    sp.add_argument("--scope-note", default="")
    sp.add_argument("--review-interval-days", type=int, default=DEFAULT_REVIEW_INTERVAL_DAYS)
    sp.add_argument("--due-window-days", type=int, default=DEFAULT_DUE_WINDOW_DAYS)

    sp = sub.add_parser("add", help="record a policy document, as a draft")
    store_arg(sp)
    sp.add_argument("--title", default="")
    sp.add_argument("--owner", default="")
    sp.add_argument("--kind", default=KIND_POLICY, help="policy (plan and playbook are "
                                                        "reserved in the schema)")
    sp.add_argument("--version", default="1.0")
    sp.add_argument("--map", action="append", metavar="REQ",
                    help="a requirement this document is aimed at; repeatable")
    sp.add_argument("--review-interval-days", type=int, default=None)
    sp.add_argument("--acknowledge", default="",
                    help="comma-separated: %s" % ",".join(ACK_CADENCES))
    sp.add_argument("--note", default="")
    sp.add_argument("--by", default="", help="who is recording this")

    sp = sub.add_parser("approve", help="record senior approval — a name and a date")
    store_arg(sp)
    sp.add_argument("--id", required=True)
    sp.add_argument("--by", dest="by_person", default="", help="who approved it")
    sp.add_argument("--on", default="", help="the date they approved it")
    sp.add_argument("--next-review", default="")
    sp.add_argument("--actor", default="")

    sp = sub.add_parser("revise", help="issue a new version — back to draft")
    store_arg(sp)
    sp.add_argument("--id", required=True)
    sp.add_argument("--version", default="")
    sp.add_argument("--why", default="")
    sp.add_argument("--actor", default="")

    sp = sub.add_parser("review", help="record a periodic review as an act, with a reason")
    store_arg(sp)
    sp.add_argument("--id", required=True)
    sp.add_argument("--on", default="")
    sp.add_argument("--next", default="")
    sp.add_argument("--why", default="")
    sp.add_argument("--actor", default="")

    sp = sub.add_parser("supersede", help="take a policy out of force; it stays in the file")
    store_arg(sp)
    sp.add_argument("--id", required=True)
    sp.add_argument("--on", default="")
    sp.add_argument("--why", default="")
    sp.add_argument("--by-policy", default="", help="the record that replaces it, if any")
    sp.add_argument("--actor", default="")

    sp = sub.add_parser("map", help="record what a policy is aimed at")
    store_arg(sp)
    sp.add_argument("--id", required=True)
    sp.add_argument("--requirement", action="append", metavar="REQ")
    sp.add_argument("--actor", default="")

    sp = sub.add_parser("unmap", help="narrow what a policy is aimed at")
    store_arg(sp)
    sp.add_argument("--id", required=True)
    sp.add_argument("--requirement", default="")
    sp.add_argument("--why", default="")
    sp.add_argument("--actor", default="")

    sp = sub.add_parser("requirements", help="the requirement view")
    store_arg(sp)
    sp.add_argument("--today", default="")
    sp.add_argument("--format", choices=("text", "json"), default="text")
    sp.add_argument("--out", default="")

    sp = sub.add_parser("analyze", help="the whole read model")
    store_arg(sp)
    sp.add_argument("--today", default="")
    sp.add_argument("--out", default="")
    sp.add_argument("--json", action="store_true",
                    help="the whole read model as JSON on stdout, which is how "
                         "attention-surface and board-pack read this register")

    sp = sub.add_parser("export", help="the register as CSV or JSON")
    store_arg(sp)
    sp.add_argument("--today", default="")
    sp.add_argument("--format", choices=("csv", "json"), default="csv")
    sp.add_argument("--out", default="")

    sub.add_parser("self-test", help="run the engine's own assertions")
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    if not args.command:
        build_parser().print_help()
        return 2
    try:
        return COMMANDS[args.command](args)
    except Refusal as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
