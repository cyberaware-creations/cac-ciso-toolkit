#!/usr/bin/env python3
"""exceptions_register.py — the defensible-acceptance register.

A system of record for every time the organisation knowingly accepts a residual risk, or
grants an exception to a control or standard. Two object types, one lifecycle: approved,
re-validated periodically, closed or expired.

The load-bearing feature is the **refusal**. No approver, no justification, no
re-validation date — and for an exception, no compensating control — means the record does
not exist. A register that accepts "R-014, accepted, see email" reproduces the free text it
was built to replace and passes an audit exactly as badly. Every refusal happens before the
file is opened, so a rejected command leaves the store byte-identical.

The second load-bearing idea is that **re-validation is an act, not a timer**. `revalidate`
records that a human re-checked the reasoning and it still holds, with a rationale, on a
date. A clock that resets itself is evidence of nothing.

A lapsed clock surfaces an item; it never expires the reasoning. Overdue acceptances stay in
the inventory and stay visible, because the organisation is still carrying that risk.

Standard library only. Subcommands:

  init          <store.exc> --client 'Name' [--owner ..] [--due-window-days 30]
  accept-add    <store.exc> --title '..' --approver '..' --justification '..'
                            --accepted YYYY-MM-DD --revalidation YYYY-MM-DD [--expiry ..]
  except-add    <store.exc> --title '..' --deviation-from '..' --compensating '..'
                            --approver '..' --justification '..'
                            --accepted YYYY-MM-DD --revalidation YYYY-MM-DD [--expiry ..]
  revalidate    <store.exc> --id A-001 --on YYYY-MM-DD --next YYYY-MM-DD --why '..'
  close         <store.exc> --id A-001 --why '..'
  link          <store.exc> --id A-001 [--risk R-006] [--csf ID.RA-01] [--incident I-001]
  analyze       <store.exc> [--today YYYY-MM-DD] [--out FILE]
  export-inventory <store.exc> [--today ..] [--format csv|json] [--out FILE]
  import-acceptances <store.exc> --from acceptances.json
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
FAMILY = "exceptions-register"
DEFAULT_DUE_WINDOW_DAYS = 30

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
ACCEPT_ID_RE = re.compile(r"^A-\d{3,}$")
EXCEPT_ID_RE = re.compile(r"^X-\d{3,}$")

STATUS_CURRENT = "current"
STATUS_DUE = "revalidation-due"
STATUS_OVERDUE = "revalidation-overdue"
STATUS_EXPIRED = "expired"
STATUS_CLOSED = "closed"
STATUS_BANDS = (STATUS_CURRENT, STATUS_DUE, STATUS_OVERDUE, STATUS_EXPIRED, STATUS_CLOSED)

# The fields without which a record does not exist. Named here rather than checked inline
# so the list is one thing a reader can audit, and so both object types share it.
REQUIRED_COMMON = ("title", "approver", "justification", "acceptedDate", "revalidationDate")
REQUIRED_EXCEPTION_EXTRA = ("deviationFrom", "compensatingControl")

WHY_FIELD_HELP = {
    "title": "an inventory of untitled items cannot be reviewed",
    "approver": "an acceptance nobody approved is a description of a problem, not a decision",
    "justification": "the basis is the artifact — 'we accepted it' is not a record of why",
    "acceptedDate": "when the clock started",
    "revalidationDate": "when somebody must look again",
    "deviationFrom": "an exception has to name the control or standard it departs from",
    "compensatingControl": ("a deviation with nothing offsetting it is not an exception, it is "
                            "an unmanaged gap, and calling it an exception launders it"),
}


class Refusal(Exception):
    """A mutation the engine declines to perform.

    Raised before the store file is opened, so a refused mutation leaves the file
    byte-identical. Asserted in self-test rather than trusted.
    """


# --- Dates --------------------------------------------------------------------

def check_date(value: str, field: str) -> str:
    """Canonical `YYYY-MM-DD`, and a real calendar date, or a refusal."""
    if not isinstance(value, str) or not DATE_RE.match(value):
        raise Refusal(
            f"{field} must be a canonical zero-padded date, YYYY-MM-DD; got {value!r}. "
            f"'2026-7-1' is refused because it sorts after '2026-10-01' as text, and every "
            f"status band here compares dates.")
    try:
        date.fromisoformat(value)
    except ValueError:
        raise Refusal(f"{field} is not a real calendar date: {value!r}")
    return value


def days_between(earlier: str, later: str) -> int:
    return (date.fromisoformat(later) - date.fromisoformat(earlier)).days


def now_ts() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


# --- Store IO -----------------------------------------------------------------

def new_store(client: str, owner: str = "", scope_note: str = "",
              due_window_days: int = DEFAULT_DUE_WINDOW_DAYS) -> dict:
    ts = now_ts()
    return {
        "schemaVersion": SCHEMA_VERSION,
        "family": FAMILY,
        "meta": {"clientName": client, "owner": owner, "scopeNote": scope_note,
                 "asOf": ts[:10]},
        "settings": {"dueWindowDays": int(due_window_days)},
        "acceptances": [],
        "exceptions": [],
        "history": [],
        "createdAt": ts,
        "updatedAt": ts,
    }


def load_store(path: str) -> dict:
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
            f"{path} is not an exceptions register: family is {fam!r}, expected "
            f"{FAMILY!r}. A risk register (.rr), CSF profile (.csfp) or metrics register "
            f"(.mtr) belongs to a different skill.")
    if store.get("schemaVersion") != SCHEMA_VERSION:
        raise Refusal(f"{path} is schemaVersion {store.get('schemaVersion')!r}; "
                      f"this engine reads {SCHEMA_VERSION}")
    for key, kind in (("acceptances", list), ("exceptions", list), ("history", list),
                      ("meta", dict), ("settings", dict)):
        if not isinstance(store.get(key), kind):
            raise Refusal(f"{path} is missing or malformed {key!r}")
    return store


def save_store(path: str, store: dict) -> None:
    """Write the store atomically: a crash mid-write leaves the previous file intact.

    One of ten copies of this pattern, registered as a twin under CAC-TW-1 and compared by
    executing them — `skills/ai-register/scripts/ai_register.py` holds the family list. The
    property compared is the interrupted write, because on the happy path an atomic writer and
    `open(path, "w")` produce identical bytes, which is how two copies stayed non-atomic
    through nine releases with every self-test green (BL-219).
    """
    store["updatedAt"] = now_ts()
    directory = os.path.dirname(os.path.abspath(path)) or "."
    fd, tmp = tempfile.mkstemp(dir=directory, suffix=".exc.tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(store, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def append_history(store: dict, event: str, target: str, actor: str,
                   why: str = "", detail: dict | None = None) -> None:
    entry = {"event": event, "target": target, "actor": actor or "", "ts": now_ts()}
    if why:
        entry["why"] = why
    if detail:
        entry["detail"] = detail
    store["history"].append(entry)


def next_id(store: dict, kind: str) -> str:
    prefix, key, pattern = (("A", "acceptances", ACCEPT_ID_RE) if kind == "acceptance"
                            else ("X", "exceptions", EXCEPT_ID_RE))
    used = [int(r["id"].split("-")[1]) for r in store[key]
            if pattern.match(r.get("id", ""))]
    return "%s-%03d" % (prefix, (max(used) + 1) if used else 1)


def find_record(store: dict, rid: str) -> tuple:
    """Return (record, kind). One lookup for both types — ids are unambiguous by prefix."""
    for r in store["acceptances"]:
        if r.get("id") == rid:
            return r, "acceptance"
    for r in store["exceptions"]:
        if r.get("id") == rid:
            return r, "exception"
    known = ", ".join([r["id"] for r in store["acceptances"]]
                      + [r["id"] for r in store["exceptions"]]) or "none yet"
    raise Refusal(f"no record {rid!r} in this register (have: {known})")


# --- Magnitude: what the acceptance was accepted AGAINST -----------------------
#
# An acceptance is a decision about a quantity — "we will carry this much exposure, on this
# basis, until this date". Re-validating without re-measuring confirms a judgment about a
# number nobody re-checked, which is the failure `--why` exists to prevent one level up: the
# act happens, the record looks complete, and nothing was actually reviewed.
#
# So a record MAY carry the magnitude it was accepted against, and `revalidate` refuses to
# renew one whose magnitude predates the last review. Three properties keep that honest:
#
#   * The register never invents a magnitude, and never demands one it was not given. A
#     hand-entered acceptance with no number is never refused for the absence of one. This
#     skill stands alone without a quantified risk register, and requiring a quantity it was
#     never handed would make an unquantified register unusable rather than more rigorous.
#   * The staleness rule invents no interval. "Older than the last time somebody reviewed
#     this record" comes from the record's own history. A `remeasureWindowDays` setting would
#     be this file naming a number no standard sets — the same objection incident-materiality
#     makes to timing a determination against an invented deadline.
#   * The refusal lands on the MUTATION only. A stale magnitude never removes a record from
#     the inventory, the export, the analysis or any rendered page. Flagged everywhere,
#     blocked at exactly one point: the act that would claim it had been re-checked.
MAGNITUDE_KEYS = ("value", "unit", "band", "measuredAt", "source")


def clean_magnitude(raw, field: str = "magnitude"):
    """Normalise a magnitude, or refuse. `None` stays `None` — absence is legitimate."""
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise Refusal(f"{field} must be an object carrying at least a value and the date it "
                      f"was measured")
    value = raw.get("value")
    if value is None or not str(value).strip():
        raise Refusal(f"{field} carries no value. A magnitude with no number is not a "
                      f"magnitude, and storing one would make the re-measurement check pass "
                      f"over the records that most need it")
    measured = raw.get("measuredAt")
    if measured:
        check_date(str(measured)[:10], f"{field}.measuredAt")
    return {"value": value,
            "unit": str(raw.get("unit") or "").strip(),
            "band": str(raw.get("band") or "").strip() or None,
            "measuredAt": str(measured)[:10] if measured else None,
            "source": str(raw.get("source") or "").strip() or None}


def last_review_point(store: dict, rec: dict, kind: str):
    """The date somebody last stood behind this record: its last re-validation, else its
    acceptance.

    Read out of history rather than stored on the record. It is already in history, and a
    second copy is a second thing that can disagree — the same reason this register keeps no
    derived field. Only well-formed dates count: an unreadable one is not quietly treated as
    "never reviewed", which would fire the refusal below for a reason its message does not
    name.
    """
    dates = []
    for e in store.get("history") or []:
        if e.get("event") != f"{kind}-revalidated" or e.get("target") != rec.get("id"):
            continue
        on = str((e.get("detail") or {}).get("on") or "")[:10]
        if DATE_RE.match(on):
            dates.append(on)
    return max(dates) if dates else rec.get("acceptedDate")


def remeasure_required(store: dict, rec: dict, kind: str) -> tuple:
    """`(required, reason)` — would the NEXT renewal be refused for want of a measurement?

    Named for what it predicts rather than for the number's age, because the two part
    company immediately after a review. Re-measure on the 20th, renew on the 1st, and the
    measurement is twelve days old and already cannot carry the following renewal: each
    review has to stand on a measurement taken since the last one, or "re-measure before you
    renew" degrades into measuring once and citing it forever.

    So this reads True for most of a record's life, which is correct and is also why the
    `remeasureNeeded` attention list narrows it to records whose review is actually due —
    a list containing every record is not a list.

    `undated` and `older-than-last-review` are kept apart rather than collapsed into one
    boolean, because they tell the reader different things: one means nobody wrote down when
    the number was taken, the other means somebody did and it was before the last review.
    """
    mag = rec.get("magnitude")
    if not mag:
        return False, ""
    measured = mag.get("measuredAt")
    if not measured:
        return True, "undated"
    point = last_review_point(store, rec, kind)
    if not point:
        return False, ""
    # Measured ON the review day counts as fresh. The comparison is `<` and not `<=`: a
    # number taken the same day somebody reviewed the record was taken for that review.
    return (measured < point), ("older-than-last-review" if measured < point else "")


# --- The refusal that is the product ------------------------------------------

def _require(fields: dict, names) -> None:
    """Refuse, naming every missing field and why it is required.

    Reporting all of them at once matters: a user who fixes one at a time and is refused
    four times learns that the tool is obstructive. A user told the whole list once learns
    what a record is.
    """
    missing = [n for n in names if not str(fields.get(n) or "").strip()]
    if not missing:
        return
    lines = [f"  - {n}: {WHY_FIELD_HELP[n]}" for n in missing]
    raise Refusal(
        "this record is missing the fields that make it a record:\n"
        + "\n".join(lines)
        + "\n  Nothing was written. A register that accepts an item without these "
          "reproduces the free text it exists to replace.")


# --- Mutations ----------------------------------------------------------------

def accept_add(store: dict, title: str, approver: str, justification: str,
               accepted: str, revalidation: str, expiry: str = "", description: str = "",
               risk_ids=(), csf_ids=(), source_risk_ref: str = "", magnitude=None,
               actor: str = "") -> dict:
    fields = {"title": title, "approver": approver, "justification": justification,
              "acceptedDate": accepted, "revalidationDate": revalidation}
    _require(fields, REQUIRED_COMMON)
    check_date(accepted, "--accepted")
    check_date(revalidation, "--revalidation")
    if expiry:
        check_date(expiry, "--expiry")
    rec = {
        "id": next_id(store, "acceptance"),
        "title": title.strip(),
        "description": description,
        "approver": approver.strip(),
        "justification": justification.strip(),
        "acceptedDate": accepted,
        "revalidationDate": revalidation,
        "expiryDate": expiry or None,
        "status": "active",
        "riskIds": list(risk_ids or []),
        "csfSubcategoryIds": list(csf_ids or []),
        "incidentIds": [],
        "sourceRiskRef": source_risk_ref or None,
        # What this was accepted against, if anything was measured. Optional by design —
        # see the magnitude block above.
        "magnitude": clean_magnitude(magnitude),
        "notes": "",
    }
    store["acceptances"].append(rec)
    append_history(store, "acceptance-added", rec["id"], actor,
                   detail={"title": rec["title"], "approver": rec["approver"]})
    return rec


def except_add(store: dict, title: str, deviation_from: str, compensating: str,
               approver: str, justification: str, accepted: str, revalidation: str,
               expiry: str = "", risk_ids=(), csf_ids=(), magnitude=None,
               actor: str = "") -> dict:
    fields = {"title": title, "approver": approver, "justification": justification,
              "acceptedDate": accepted, "revalidationDate": revalidation,
              "deviationFrom": deviation_from, "compensatingControl": compensating}
    _require(fields, REQUIRED_COMMON + REQUIRED_EXCEPTION_EXTRA)
    check_date(accepted, "--accepted")
    check_date(revalidation, "--revalidation")
    if expiry:
        check_date(expiry, "--expiry")
    rec = {
        "id": next_id(store, "exception"),
        "title": title.strip(),
        "deviationFrom": deviation_from.strip(),
        "compensatingControl": compensating.strip(),
        "approver": approver.strip(),
        "justification": justification.strip(),
        "acceptedDate": accepted,
        "revalidationDate": revalidation,
        "expiryDate": expiry or None,
        "status": "active",
        "riskIds": list(risk_ids or []),
        "csfSubcategoryIds": list(csf_ids or []),
        "incidentIds": [],
        "magnitude": clean_magnitude(magnitude),
        "notes": "",
    }
    store["exceptions"].append(rec)
    append_history(store, "exception-added", rec["id"], actor,
                   detail={"title": rec["title"], "deviationFrom": rec["deviationFrom"]})
    return rec


def revalidate(store: dict, rid: str, on: str, next_date: str, why: str,
               remeasured=None, measured_on: str = "", magnitude_unit: str = "",
               actor: str = "") -> dict:
    """Record that a human re-checked the reasoning and it still holds.

    Refuses without a rationale. Re-validation is the act DORA RTS Art. 3(d)(iv) asks an
    organisation to demonstrate; an event with no stated reason is indistinguishable from
    an automated renewal, which is the practice the requirement exists to rule out.

    Refuses a second way where the record carries a magnitude: renewing against a number
    measured before the last review asserts something nobody checked. `--remeasured` with
    `--measured-on` supplies a fresh one in the same act, which is the point — the fix is to
    do the measuring, not to wave the check away.
    """
    rec, kind = find_record(store, rid)
    if not (why or "").strip():
        raise Refusal(
            f"revalidating {rid} requires --why. Re-validation is an act — somebody "
            f"re-checked the reasoning and it still holds — not a timer reset. Without a "
            f"stated reason the event cannot be told apart from an automated renewal.")
    if rec.get("status") == "closed":
        raise Refusal(f"{rid} is closed; re-open it deliberately rather than "
                      f"re-validating a closed record")
    check_date(on, "--on")
    check_date(next_date, "--next")
    if days_between(on, next_date) <= 0:
        raise Refusal(f"--next ({next_date}) must be after --on ({on}); a re-validation "
                      f"that does not move the clock forward is not a re-validation")

    # Every refusal below is raised before anything is written, like every other refusal in
    # this file, so a rejected re-validation leaves the store byte-identical.
    fresh = None
    if remeasured is not None:
        if not str(measured_on or "").strip():
            raise Refusal(
                f"--remeasured needs --measured-on. A fresh magnitude with no date is the "
                f"same undated number this check exists to catch, and it would pass every "
                f"future review silently.")
        check_date(measured_on, "--measured-on")
        if days_between(measured_on, on) < 0:
            raise Refusal(
                f"--measured-on ({measured_on}) is after --on ({on}): a review cannot cite "
                f"a measurement taken after the review happened.")
        prior = rec.get("magnitude") or {}
        fresh = clean_magnitude({
            "value": remeasured,
            "unit": str(magnitude_unit or "").strip() or prior.get("unit"),
            "band": prior.get("band"),
            "measuredAt": measured_on,
            "source": prior.get("source"),
        }, "--remeasured")
    else:
        stale, reason = remeasure_required(store, rec, kind)
        if stale:
            mag = rec["magnitude"]
            shown = f"{mag['value']}{(' ' + mag['unit']) if mag.get('unit') else ''}"
            when = ("never — the number carries no date" if reason == "undated"
                    else f"{mag['measuredAt']}")
            raise Refusal(
                f"{rid} cannot be re-validated against a magnitude nobody has re-measured.\n"
                f"    accepted against: {shown}\n"
                f"    last measured:    {when}\n"
                f"    last reviewed:    {last_review_point(store, rec, kind)}\n"
                f"  Re-validation records that a human re-checked the reasoning and it still "
                f"holds. This reasoning rests on that number, and renewing without "
                f"re-measuring asserts something nobody checked — the same gap `--why` "
                f"exists to close.\n"
                f"  Either re-measure and say so:   --remeasured <value> --measured-on <date>\n"
                f"  or, if the basis has changed:   close it and record a fresh acceptance.\n"
                f"  Nothing was written, and nothing is hidden: this record still appears in "
                f"the inventory, the export, the analysis and every rendered view. One act is "
                f"refused, not one record.")

    previous = rec["revalidationDate"]
    rec["revalidationDate"] = next_date
    detail = {"on": on, "from": previous, "to": next_date}
    if fresh is not None:
        was = (rec.get("magnitude") or {}).get("value")
        rec["magnitude"] = fresh
        detail["magnitude"] = {"from": was, "to": fresh["value"],
                               "measuredAt": fresh["measuredAt"]}
    append_history(store, f"{kind}-revalidated", rid, actor, why=why, detail=detail)
    return rec


def close_record(store: dict, rid: str, why: str, actor: str = "") -> dict:
    rec, kind = find_record(store, rid)
    if not (why or "").strip():
        raise Refusal(f"closing {rid} requires --why: an inventory that loses items "
                      f"without a reason cannot be reconciled later")
    if rec.get("status") == "closed":
        raise Refusal(f"{rid} is already closed")
    rec["status"] = "closed"
    append_history(store, f"{kind}-closed", rid, actor, why=why)
    return rec


def link_record(store: dict, rid: str, risk_ids=(), csf_ids=(), incident_ids=(),
                actor: str = "") -> dict:
    rec, kind = find_record(store, rid)
    added = {"risk": [], "csf": [], "incident": []}
    for key, ids, slot in (("riskIds", risk_ids, "risk"),
                           ("csfSubcategoryIds", csf_ids, "csf"),
                           ("incidentIds", incident_ids, "incident")):
        for i in ids or ():
            if i not in rec[key]:
                rec[key].append(i)
                added[slot].append(i)
    if any(added.values()):
        append_history(store, f"{kind}-linked", rid, actor, detail=added)
    return rec



def import_acceptances(store: dict, rows: list, actor: str = "") -> dict:
    """Take the risk-register bridge's output into this store.

    Idempotent on `sourceRiskRef`: an intake row whose source risk already has a record
    here updates that record rather than adding a second one. Without that, running the
    export twice would double the inventory, and an inventory that counts a thing twice is
    worse than one that misses it — the reader has no way to tell which is happening.

    Every row still goes through the same refusal as a hand-entered record. An import is
    not a side door: a risk marked accepted with no approver cannot become a record here
    just because it arrived as a file.
    """
    if not isinstance(rows, list):
        raise Refusal("intake must be a JSON array of acceptance objects")
    added, updated, refused = [], [], []
    by_source = {r.get("sourceRiskRef"): r for r in store["acceptances"]
                 if r.get("sourceRiskRef")}
    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            refused.append((f"row {i}", "not an object"))
            continue
        src = row.get("sourceRiskRef")
        try:
            fields = {k: row.get(k, "") for k in REQUIRED_COMMON}
            _require(fields, REQUIRED_COMMON)
            for f, flag in (("acceptedDate", "acceptedDate"),
                            ("revalidationDate", "revalidationDate")):
                check_date(row[f], flag)
            if row.get("expiryDate"):
                check_date(row["expiryDate"], "expiryDate")
            # Validated inside the try so a malformed magnitude refuses that ROW and is
            # reported, rather than aborting the whole intake. One bad row in an export must
            # not cost the other nine their update.
            incoming = clean_magnitude(row.get("magnitude"), "magnitude")
        except Refusal as exc:
            refused.append((src or f"row {i}", str(exc).splitlines()[0]))
            continue
        existing = by_source.get(src) if src else None
        if existing is not None:
            existing.update({
                "title": row["title"], "approver": row["approver"],
                "justification": row["justification"],
                "acceptedDate": row["acceptedDate"],
                "revalidationDate": row["revalidationDate"],
                "expiryDate": row.get("expiryDate") or None,
            })
            # A refresh that carries no magnitude leaves the one already recorded alone. The
            # source register may simply not be scoring that risk any more, and silently
            # blanking the number would clear the re-measurement check on a record nobody
            # re-measured — turning a bridge into a way around the refusal.
            if incoming is not None:
                existing["magnitude"] = incoming
            append_history(store, "acceptance-updated", existing["id"], actor,
                           why=f"refreshed from {src} via export-acceptances")
            updated.append(existing["id"])
        else:
            rec = accept_add(store, row["title"], row["approver"], row["justification"],
                             row["acceptedDate"], row["revalidationDate"],
                             row.get("expiryDate") or "",
                             risk_ids=row.get("riskIds") or [],
                             csf_ids=row.get("csfSubcategoryIds") or [],
                             source_risk_ref=src or "", magnitude=incoming, actor=actor)
            if src:
                by_source[src] = rec
            added.append(rec["id"])
    return {"added": added, "updated": updated, "refused": refused}

# --- Derivations (nothing here is ever stored) --------------------------------

def status_band(rec: dict, today: str, due_window_days: int) -> str:
    """Which band this record sits in, from its dates and `today`.

    `expired` outranks the re-validation bands: past the expiry date is past it, whether or
    not the item was also due for review. `closed` outranks everything, because it is a
    fact about what a human did rather than a derivation about where a date sits.
    """
    if rec.get("status") == "closed":
        return STATUS_CLOSED
    expiry = rec.get("expiryDate")
    if expiry and days_between(expiry, today) > 0:
        return STATUS_EXPIRED
    reval = rec.get("revalidationDate")
    if not reval:
        return STATUS_CURRENT
    remaining = days_between(today, reval)
    if remaining < 0:
        return STATUS_OVERDUE
    if remaining <= due_window_days:
        return STATUS_DUE
    return STATUS_CURRENT


# --- Escalation (contract CAC-EL-1 §1.3) --------------------------------------
#
# Derived, stateless, never written to the store, never a history event. This register owns
# the acceptance clock, so it is the skill entitled to say a clock has run out — and the only
# one. Everybody else carries a read-only marker and flags it.
#
# Two triggers, both about a clock that has already lapsed:
#
#   expired               past its expiry date — nobody's approval covers it any more
#   revalidation-overdue  past its re-validation date, approval still live
#
# `revalidation-due` is deliberately NOT a trigger. A record inside its due window is on
# schedule, and escalating a deadline that has not yet been missed teaches a reader to
# ignore the list by the second quarter. Due is the attention list; overdue is an escalation.
#
# Severity is the reverse of what the band order suggests, and that is the considered part.
# `expired` is critical because the approval itself has lapsed: the organisation is carrying
# a deviation nobody currently endorses. `revalidation-overdue` is high — the approval still
# stands, and what has slipped is the review of it. One is an unapproved exposure; the other
# is an unreviewed approval, and the first is worse.

ESCALATION_SEVERITY_ORDER = ["critical", "high", "medium"]


def escalations(store: dict, today: str) -> list[dict]:
    """Every escalation this register warrants, in the CAC-EL-1 §1.3 shape.

    `subjectKind` is `acceptance` or `exception` — the record's own kind rather than one
    word for both, because a board reads them differently: an accepted risk is a decision
    somebody made, and a control exception is a rule somebody is not following.

    Records that came across the bridge also carry `relatedRef`: the risk id this record is
    the acceptance OF. `risk-register` keeps its own lightweight `accepted` marker and can
    escalate `acceptance-lapsed` on it, so the same expiry can legitimately arrive at a pack
    twice — once on the marker, once on the authoritative record here, and at two severities.
    Declaring the link lets the consumer NOTICE that without either register having to know
    the other exists.

    It is `sourceRiskRef` and deliberately not `riskIds`. `sourceRiskRef` is stamped by
    `export-acceptances` and is the intake idempotency key: it means "this record IS the
    acceptance of that risk", which is identity. `riskIds` means "this relates to that risk",
    which is not — an acceptance linked to R-003 and a dwell escalation on R-003 are two
    different facts about one risk, and joining them would manufacture the false positive
    `possible_duplicate_asks` exists to avoid making.
    """
    window = int((store.get("settings") or {}).get("dueWindowDays")
                 or DEFAULT_DUE_WINDOW_DAYS)

    def _related(rec):
        # Present and null rather than absent when there is no link, matching how every
        # other optional field on these records is written. Absent-versus-null is a
        # distinction a consumer would have to guess at.
        return {"relatedRef": rec.get("sourceRiskRef") or None}

    out = []
    for kind, records in (("acceptance", store["acceptances"]),
                          ("exception", store["exceptions"])):
        for rec in records:
            band = status_band(rec, today, window)
            if band == STATUS_EXPIRED:
                expiry = rec.get("expiryDate")
                days = days_between(expiry, today) if expiry else None
                out.append({
                    "subjectRef": rec["id"], "subjectKind": kind,
                    "trigger": "expired", "severity": "critical",
                    "since": expiry, **_related(rec),
                    "evidence": {
                        "from": expiry, "to": today,
                        "baseline": rec.get("approver") or "",
                        "detail": (f"{rec['title']} expired {expiry}"
                                   + (f", {days} days ago" if days else "")
                                   + " and is still on the register — no current approval "
                                     "covers it"),
                    },
                })
            elif band == STATUS_OVERDUE:
                reval = rec.get("revalidationDate")
                days = -days_between(today, reval) if reval else None
                out.append({
                    "subjectRef": rec["id"], "subjectKind": kind,
                    "trigger": "revalidation-overdue", "severity": "high",
                    "since": reval, **_related(rec),
                    "evidence": {
                        "from": reval, "to": today,
                        "baseline": rec.get("approver") or "",
                        "detail": (f"{rec['title']} was due for re-validation {reval}"
                                   + (f", {days} days ago" if days else "")
                                   + " — the approval stands but nobody has re-checked the "
                                     "reasoning"),
                    },
                })
    out.sort(key=lambda e: (ESCALATION_SEVERITY_ORDER.index(e["severity"]),
                            e["subjectRef"]))
    return out


def derive(store: dict, rec: dict, kind: str, today: str, window: int) -> dict:
    reval = rec.get("revalidationDate")
    expiry = rec.get("expiryDate")
    _rm = remeasure_required(store, rec, kind)
    return {
        "id": rec["id"],
        "kind": kind,
        "title": rec["title"],
        "approver": rec.get("approver", ""),
        "justification": rec.get("justification", ""),
        "deviationFrom": rec.get("deviationFrom"),
        "compensatingControl": rec.get("compensatingControl"),
        "acceptedDate": rec.get("acceptedDate"),
        "revalidationDate": reval,
        "expiryDate": expiry,
        "recordStatus": rec.get("status", "active"),
        "band": status_band(rec, today, window),
        "daysToRevalidation": days_between(today, reval) if reval else None,
        "daysToExpiry": days_between(today, expiry) if expiry else None,
        "riskIds": list(rec.get("riskIds") or []),
        "csfSubcategoryIds": list(rec.get("csfSubcategoryIds") or []),
        "incidentIds": list(rec.get("incidentIds") or []),
        "sourceRiskRef": rec.get("sourceRiskRef"),
        # What it was accepted against, and whether that number has been re-measured since
        # anybody last reviewed it. Reported on every record, including the ones carrying no
        # magnitude at all — a reader can then tell "measured and fresh" from "never
        # quantified", which one boolean would have collapsed.
        "magnitude": dict(rec["magnitude"]) if rec.get("magnitude") else None,
        "remeasureRequired": _rm[0],
        "remeasureReason": _rm[1] or None,
        "lastReviewedOn": last_review_point(store, rec, kind),
    }


# --- CAC-AP-1: the applicability profile, read as data --------------------------------
#
# A consumer of the contract `incident-materiality` proved the shape of.
#
# What narrowing means here is NOT what it means there, and the difference is worth being
# exact about, because getting it wrong would be the token narrowing the contract was
# written to avoid. `incident-materiality` suppresses COMPUTED ROWS — a disclosure window a
# not-listed entity should never have had calculated. This register computes nothing
# per-regime: an acceptance expires on its own date whether or not DORA applies.
#
# So what a profile narrows here is the QUESTION SET, which is exactly what CAC-AP-1 says a
# profile does and all it says. An organisation outside DORA is not asked whether it keeps
# the register of information; one that has declared nothing IS asked, because §2.2 makes
# absence ask more.
#
# What this deliberately does NOT do is ANSWER the question. Nothing in an `.exc` records
# whether a record belongs to a DORA register of information, so a coverage figure would be
# inferred from data that is not there, and this suite refuses to invent the number it asks
# for. That is also why there is no conflict record here as there is in
# `incident-materiality`: a conflict needs both sides stated, and one is missing.

CONTEXT_CONTRACT = "CAC-AP-1"
CONTEXT_SKILL = "exceptions"
CONTEXT_BATTERIES = {
    "dora-register": {"flag": "doraScope", "label": "DORA register of information",
                      "question": "do these records carry the ICT third-party "
                                  "arrangements DORA requires to be listed?"},
}


def load_context(path: str) -> dict:
    """Read an applicability payload. As data — this skill imports no other skill (§2.6).

    Both refusals are deliberate. `--context` was passed on purpose, so a payload that
    cannot be honoured must say so rather than quietly leave the register un-narrowed: a
    full question set would read as a profile that decided nothing applied.

    Twinned with `skills/vendor-register/scripts/vendor_register.py`, which holds
    the family list. Compared under CAC-TW-1 by running all seven `--context`
    consumers against a corpus of malformed payloads (BL-218). What must agree is
    WHICH payloads are refused and what is returned, never the wording: two of the
    seven refuse with `ValueError` and five with a local `Refusal`, and each is that
    engine's own refusal channel.
    """
    try:
        with open(path, encoding="utf-8") as fh:
            payload = json.load(fh)
    except FileNotFoundError:
        raise Refusal(f"no such context payload: {path}")
    except json.JSONDecodeError as exc:
        raise Refusal(f"{path} is not valid JSON (line {exc.lineno}, "
                      f"column {exc.colno}): {exc.msg}")
    if not isinstance(payload, dict):
        raise Refusal(f"{path} must contain a JSON object, got {type(payload).__name__}")
    got = payload.get("contractVersion")
    if got != CONTEXT_CONTRACT:
        raise Refusal(
            f"{path} declares contractVersion {got!r}; this engine reads "
            f"{CONTEXT_CONTRACT!r}. Produce one with "
            f"`business_context.py export <file.biz>`.")
    if not isinstance(payload.get("applicability"), dict):
        raise Refusal(
            f"{path} carries no decided `applicability`, so this skill cannot tell which "
            f"batteries the profile narrowed away. Re-export it with "
            f"`business_context.py export <file.biz>`; the narrowing decision belongs to "
            f"that skill and is not re-derived here.")
    return payload


def applicability_for(payload: dict) -> dict:
    """The profile's decision for this skill, in this skill's own vocabulary.

    The payload arrives DECIDED — §2.2 and §2.3 were applied by `business-context`, and
    re-deriving them here would be the second implementation the contract prevents.

    There is no subject layer. This store has no per-record perimeter to declare one
    against: `incident-materiality` has an incident and a vendor record will have a vendor,
    but an acceptance does not sit in a different perimeter from the register around it.
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


def analyze(store: dict, today: str, context: dict = None) -> dict:
    window = int((store.get("settings") or {}).get("dueWindowDays")
                 or DEFAULT_DUE_WINDOW_DAYS)
    rows = ([derive(store, r, "acceptance", today, window) for r in store["acceptances"]]
            + [derive(store, r, "exception", today, window) for r in store["exceptions"]])
    active = [r for r in rows if r["band"] != STATUS_CLOSED]
    out = {
        "meta": dict(store.get("meta") or {}),
        "today": today,
        "dueWindowDays": window,
        "records": rows,
        # Beside `attention`, not inside it. The attention lists are a review agenda; this
        # is what should not have waited for a review. Consumers read it and never re-derive
        # it — this register owns the clock, so nothing downstream is entitled to a second
        # opinion about whether one has run out.
        "escalations": escalations(store, today),
        "attention": {
            "overdue": [r["id"] for r in active if r["band"] == STATUS_OVERDUE],
            "due": [r["id"] for r in active if r["band"] == STATUS_DUE],
            "expired": [r["id"] for r in active if r["band"] == STATUS_EXPIRED],
            # An exception whose compensating control is missing cannot exist — the engine
            # refuses it — so this list catches only records that predate that rule or
            # arrived from an import.
            "noCompensatingControl": [r["id"] for r in active if r["kind"] == "exception"
                                      and not (r["compensatingControl"] or "").strip()],
            "unlinked": [r["id"] for r in active
                         if not (r["riskIds"] or r["csfSubcategoryIds"])],
            # Records whose recorded magnitude predates the last review. These are the ones
            # `revalidate` will refuse until somebody re-measures — surfaced here so the
            # review can plan the measuring rather than discover it at the refusal.
            # Narrowed to records whose review is actually due. `remeasureRequired` reads
            # True for most of a record's life by design (see the function), so listing it
            # unfiltered would put every quantified record on the agenda every quarter and
            # teach a reviewer to skip the list. What belongs here is the intersection: a
            # review that is coming up AND will be refused until somebody measures.
            "remeasureNeeded": [r["id"] for r in active if r["remeasureRequired"]
                                and r["band"] in (STATUS_DUE, STATUS_OVERDUE,
                                                  STATUS_EXPIRED)],
        },
        "counts": {
            "acceptances": len(store["acceptances"]),
            "exceptions": len(store["exceptions"]),
            "active": len(active),
            "closed": len(rows) - len(active),
            # The active inventory split by lifecycle band. Every band appears, including
            # the ones sitting at zero, because this is what a reader compares between two
            # quarters and a band that vanished when it emptied would read as a band that
            # stopped existing. `closed` is excluded: `active` is the population being
            # split, and a part outside the whole would stop the segments summing to it.
            #
            # Computed here rather than by whatever draws it. A count derived downstream is
            # a second number that can disagree with the one printed above it, and a reader
            # has no way to tell which of the two is right.
            "byBand": {b: len([r for r in active if r["band"] == b])
                       for b in STATUS_BANDS if b != STATUS_CLOSED},
        },
    }
    # Additive by construction, as `--context` is in every consumer of CAC-AP-1: the key
    # exists only when a profile was supplied, so a run without one produces the bytes it
    # always did and no consumer has to tell an empty block from an absent one.
    if context is not None:
        out["context"] = applicability_for(context)
    return out


def export_inventory(store: dict, today: str) -> list:
    """The active inventory, flattened. This is the artifact an auditor is handed.

    Closed records are excluded — the inventory answers "what are we carrying now" — but
    they remain in the store and in the change log, so the exclusion is a view, not a
    deletion. Overdue and expired items are INCLUDED: the organisation is still carrying
    them, and an inventory that hid them would be the one thing worse than not having one.
    """
    rows = []
    for r in analyze(store, today)["records"]:
        if r["band"] == STATUS_CLOSED:
            continue
        rows.append({
            "id": r["id"],
            "type": r["kind"],
            "title": r["title"],
            "deviationFrom": r["deviationFrom"] or "",
            "compensatingControl": r["compensatingControl"] or "",
            "approver": r["approver"],
            "justification": r["justification"],
            "acceptedDate": r["acceptedDate"] or "",
            "revalidationDate": r["revalidationDate"] or "",
            "expiryDate": r["expiryDate"] or "",
            "status": r["band"],
            "linkedRisks": ";".join(r["riskIds"]),
            "linkedCsf": ";".join(r["csfSubcategoryIds"]),
        })
    return rows


INVENTORY_COLUMNS = ("id", "type", "title", "deviationFrom", "compensatingControl",
                     "approver", "justification", "acceptedDate", "revalidationDate",
                     "expiryDate", "status", "linkedRisks", "linkedCsf")


def inventory_csv(rows: list) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(INVENTORY_COLUMNS), lineterminator="\n")
    w.writeheader()
    for r in rows:
        w.writerow(r)
    return buf.getvalue()


# --- Self-test ----------------------------------------------------------------
#
# Every expectation was worked by hand from schema.md before the code that satisfies it.
# The cases were chosen to be the ones a plausible implementation gets wrong: the boundary
# of a status band, expiry outranking re-validation, and — the centrepiece — that a refused
# command leaves the file untouched.

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

    # --- status bands, hand-worked against a 30-day due window --------------------
    def band(reval=None, expiry=None, status="active", today="2026-07-31", window=30):
        return status_band({"revalidationDate": reval, "expiryDate": expiry,
                            "status": status}, today, window)
    eq(STATUS_BANDS, ("current", "revalidation-due", "revalidation-overdue",
                      "expired", "closed"), "STATUS_BANDS")
    eq(band(reval="2026-12-01"), STATUS_CURRENT, "far-off re-validation is current")
    # The boundary, worked by hand: 2026-07-31 + 30 days is 2026-08-30, and the rule is
    # `remaining <= window`, so 30 days out is already due and 31 days out is not. One day
    # separates these two rows, which is why both are here.
    eq(band(reval="2026-08-31"), STATUS_CURRENT, "31 days out is still current")
    eq(band(reval="2026-08-30"), STATUS_DUE, "exactly 30 days out is inside the window")
    eq(band(reval="2026-08-31", window=31), STATUS_DUE, "the window is the only tunable")
    eq(band(reval="2026-07-31"), STATUS_DUE, "due today is due, not yet overdue")
    eq(band(reval="2026-07-30"), STATUS_OVERDUE, "yesterday is overdue")
    # Expiry outranks the re-validation bands.
    eq(band(reval="2026-12-01", expiry="2026-07-30"), STATUS_EXPIRED,
       "past expiry is expired even when re-validation is far off")
    eq(band(reval="2026-07-01", expiry="2026-07-30"), STATUS_EXPIRED,
       "expiry outranks overdue re-validation")
    eq(band(reval="2026-12-01", expiry="2026-07-31"), STATUS_CURRENT,
       "expiring today has not expired yet")
    eq(band(reval="2026-07-01", status="closed"), STATUS_CLOSED,
       "closed outranks everything — it is a fact, not a derivation")

    work = _tf.mkdtemp()
    try:
        path = os.path.join(work, "t.exc")
        store = new_store("Acme", due_window_days=30)
        save_store(path, store)
        store = load_store(path)

        a1 = accept_add(store, "40-day patch window on internet-facing systems", "CISO",
                        "Vendor cadence is quarterly; monitoring compensates.",
                        "2026-07-01", "2027-01-01", expiry="2027-07-01",
                        risk_ids=["R-006"], actor="t")
        x1 = except_add(store, "Finance without phishing-resistant MFA", "NYDFS-500.12",
                        "Callback verification on payment changes over $10k.", "CFO",
                        "Token rollout blocked until the ERP upgrade completes.",
                        "2026-05-01", "2026-08-15", expiry="2026-09-30",
                        risk_ids=["R-007"], actor="t")
        eq(a1["id"], "A-001", "acceptance ids are A-prefixed")
        eq(x1["id"], "X-001", "exception ids are X-prefixed")
        eq(a1["status"], "active", "a new record is active")

        out = analyze(store, "2026-07-31")
        by = {r["id"]: r for r in out["records"]}
        eq(by["A-001"]["band"], STATUS_CURRENT, "A-001 re-validates in 2027")
        eq(by["X-001"]["band"], STATUS_DUE, "X-001 re-validates in 15 days")
        eq(by["X-001"]["daysToRevalidation"], 15, "days to re-validation is a plain distance")
        eq(by["A-001"]["kind"], "acceptance", "kind travels with the derived row")
        eq({k: v for k, v in out["counts"].items() if k != "byBand"},
           {"acceptances": 1, "exceptions": 1, "active": 2, "closed": 0},
           "headline counts")

        # The band split is a partition of `active`, and the two must agree. A mix whose
        # segments do not sum to the total it is drawn beside is a chart that contradicts
        # the number printed above it.
        by_band = out["counts"]["byBand"]
        eq(sum(by_band.values()), out["counts"]["active"],
           "the band split sums to the active count it partitions")
        eq(by_band, {STATUS_CURRENT: 1, STATUS_DUE: 1, STATUS_OVERDUE: 0, STATUS_EXPIRED: 0},
           "every band is present, including the empty ones")
        ok(STATUS_CLOSED not in by_band,
           "closed is excluded — it is not part of the population being split")
        eq(out["attention"]["due"], ["X-001"], "the due list")
        eq(out["attention"]["overdue"], [], "nothing overdue yet")
        eq(out["attention"]["unlinked"], [], "both records carry a risk link")

        # --- escalation (CAC-EL-1 §1.3) --------------------------------------
        # A record inside its due window is on schedule. Escalating a deadline nobody has
        # missed yet is how a list stops being read.
        eq(escalations(store, "2026-07-31"), [],
           "a record inside its due window escalates nothing")

        def _rec(rid, reval, expiry, closed=False):
            return {"id": rid, "title": f"{rid} title", "approver": "CFO",
                    "justification": "j", "acceptedDate": "2026-01-01",
                    "revalidationDate": reval, "expiryDate": expiry,
                    "status": "closed" if closed else "active",
                    "riskIds": [], "csfSubcategoryIds": [], "incidentIds": []}

        def _store(acc=(), exc=()):
            s = new_store("Fixture Co")
            s["acceptances"] = list(acc)
            s["exceptions"] = list(exc)
            return s

        # Overdue re-validation: the approval stands, the review of it has slipped.
        over = _store(acc=[_rec("A-100", "2026-01-15", "2027-01-01")])
        eq([(e["trigger"], e["severity"], e["subjectKind"])
            for e in escalations(over, "2026-07-31")],
           [("revalidation-overdue", "high", "acceptance")],
           "a missed re-validation escalates as high")

        # Expired outranks it, and is worse: nobody's approval covers the deviation now.
        exp = _store(acc=[_rec("A-101", "2026-01-15", "2026-06-01")])
        eq([(e["trigger"], e["severity"]) for e in escalations(exp, "2026-07-31")],
           [("expired", "critical")],
           "an expired record escalates as critical, and only once")

        # A closed record escalates nothing. Closing is a human act, and the clock on a
        # record somebody deliberately ended is not still running.
        eq(escalations(_store(acc=[_rec("A-102", "2020-01-01", "2020-06-01", closed=True)]),
                       "2026-07-31"), [],
           "a closed record escalates nothing, however old its dates")

        # subjectKind distinguishes the two record types: an accepted risk is a decision
        # somebody made, a control exception is a rule somebody is not following.
        both = _store(acc=[_rec("A-103", "2026-01-15", "2027-01-01")],
                      exc=[_rec("X-103", "2026-01-15", "2027-01-01")])
        eq(sorted(e["subjectKind"] for e in escalations(both, "2026-07-31")),
           ["acceptance", "exception"],
           "acceptances and exceptions carry their own subjectKind")

        # The §1.3 shape, and worst-first ordering across both record types.
        mixed = _store(acc=[_rec("A-200", "2026-01-15", "2027-01-01")],
                       exc=[_rec("X-100", "2026-01-15", "2026-06-01")])
        got = escalations(mixed, "2026-07-31")
        # subjectKind is asserted on BOTH branches. Checking it only where records are
        # overdue leaves the expired branch free to hardcode one kind, and an expired
        # control exception reported as an accepted risk is precisely the confusion the
        # two words exist to prevent.
        eq([(e["severity"], e["subjectRef"], e["subjectKind"]) for e in got],
           [("critical", "X-100", "exception"), ("high", "A-200", "acceptance")],
           "escalations sort worst-first, and each keeps its own kind on either branch")
        eq(sorted(got[0]), ["evidence", "relatedRef", "severity", "since", "subjectKind",
                            "subjectRef", "trigger"],
           "every escalation carries the six contract keys, plus the optional link")
        eq(got[0]["relatedRef"], None,
           "which is null on a hand-entered record — it is the acceptance OF nothing here")
        eq(sorted(got[0]["evidence"]), ["baseline", "detail", "from", "to"],
           "and its evidence names the comparison that fired it")

        # And it reaches analyze(), where board-pack reads it.
        eq(len(analyze(mixed, "2026-07-31")["escalations"]), 2,
           "analyze carries the escalation list")

        # --- re-measurement before renewal ----------------------------------------
        #
        # An acceptance is a decision about a quantity. Renewing it without re-measuring
        # confirms a judgment about a number nobody re-checked — the gap `--why` closes one
        # level up. Every case below is built on its own store, because this refusal turns
        # on history and a fixture carrying somebody else's re-validation would decide it.
        def _mstore(mag=None, accepted="2026-01-01"):
            s = new_store("Magnitude Co")
            accept_add(s, "Patch window", "CISO", "Vendor cadence is quarterly.",
                       accepted, "2026-09-01", magnitude=mag, actor="t")
            return s

        _mag = {"value": 12, "unit": "residual exposure", "measuredAt": "2026-02-01",
                "source": "risk-register"}

        # A record with NO magnitude is never refused. This register stands alone without a
        # quantified risk register, and demanding a number it was never given would make an
        # unquantified register unusable rather than more rigorous.
        plain = _mstore()
        eq(plain["acceptances"][0]["magnitude"], None,
           "a record recorded without a magnitude carries none, rather than a zero")
        revalidate(plain, "A-001", "2026-08-01", "2027-08-01", "Re-checked with the board.",
                   actor="t")
        eq(plain["acceptances"][0]["revalidationDate"], "2027-08-01",
           "and re-validates freely — no magnitude means nothing to re-measure")

        # Measured AFTER the acceptance: fresh, and renews.
        fresh = _mstore(mag=_mag)
        eq(fresh["acceptances"][0]["magnitude"]["measuredAt"], "2026-02-01",
           "the magnitude is stored with the date it was measured")
        eq(remeasure_required(fresh, fresh["acceptances"][0], "acceptance"), (False, ""),
           "measured after the acceptance, so nothing is stale")
        revalidate(fresh, "A-001", "2026-08-01", "2027-08-01", "Re-checked.", actor="t")
        eq(fresh["acceptances"][0]["revalidationDate"], "2027-08-01",
           "a fresh magnitude renews without ceremony")

        # ...and now it is stale, because that re-validation moved the review point past it.
        eq(last_review_point(fresh, fresh["acceptances"][0], "acceptance"), "2026-08-01",
           "the review point advances to the last re-validation")
        eq(remeasure_required(fresh, fresh["acceptances"][0], "acceptance"),
           (True, "older-than-last-review"),
           "the same magnitude is now older than the last review")
        refuses(lambda: revalidate(fresh, "A-001", "2027-01-01", "2028-01-01", "Still fine."),
                "renewing twice against one measurement is refused",
                "cannot be re-validated against a magnitude nobody has re-measured")
        eq(fresh["acceptances"][0]["revalidationDate"], "2027-08-01",
           "and the refused renewal moved nothing")

        # The refusal says what it does NOT do. A reader who thinks a stale magnitude hides
        # the record will go looking for it in the wrong place.
        _msg = ""
        try:
            revalidate(fresh, "A-001", "2027-01-01", "2028-01-01", "Still fine.")
        except Refusal as exc:
            _msg = str(exc)
        ok("--remeasured" in _msg and "--measured-on" in _msg,
           "the refusal names the flags that resolve it")
        ok("close it and record a fresh acceptance" in _msg,
           "and the other legitimate way out, when the basis itself changed")
        ok("still appears in the inventory" in _msg,
           "and states that the record is not hidden — one act refused, not one record")

        # --- and the way through: re-measure, in the same act ---------------------
        revalidate(fresh, "A-001", "2027-01-01", "2028-01-01", "Re-measured with IT.",
                   remeasured=8, measured_on="2026-12-20", actor="t")
        eq(fresh["acceptances"][0]["magnitude"]["value"], 8, "the fresh magnitude is stored")
        eq(fresh["acceptances"][0]["magnitude"]["measuredAt"], "2026-12-20",
           "with the date it was taken")
        eq(fresh["acceptances"][0]["magnitude"]["unit"], "residual exposure",
           "the unit carries over — a re-measurement is the same quantity, measured again")
        eq(fresh["acceptances"][0]["revalidationDate"], "2028-01-01",
           "and the clock moves")
        _mh = [e for e in fresh["history"] if (e.get("detail") or {}).get("magnitude")]
        eq(len(_mh), 1, "the re-measurement is one history entry, not a silent overwrite")
        eq(_mh[0]["detail"]["magnitude"], {"from": 12, "to": 8, "measuredAt": "2026-12-20"},
           "and it records what the number was, what it became, and when")

        # An undated magnitude is stale on its own terms, and says so differently. The two
        # reasons are kept apart because they tell the reader different things.
        undated = _mstore(mag={"value": 12, "unit": "residual exposure"})
        eq(undated["acceptances"][0]["magnitude"]["measuredAt"], None,
           "an undated magnitude is stored with a null date, not today's")
        eq(remeasure_required(undated, undated["acceptances"][0], "acceptance"),
           (True, "undated"), "and is stale for a reason of its own")
        refuses(lambda: revalidate(undated, "A-001", "2026-08-01", "2027-08-01", "Fine."),
                "an undated magnitude is refused too", "never — the number carries no date")

        # The boundary, pinned. Measured ON the review day was measured FOR that review.
        onday = _mstore(mag={**_mag, "measuredAt": "2026-01-01"}, accepted="2026-01-01")
        eq(remeasure_required(onday, onday["acceptances"][0], "acceptance"), (False, ""),
           "a magnitude measured on the review date itself is fresh, not stale")
        before_day = _mstore(mag={**_mag, "measuredAt": "2025-12-31"}, accepted="2026-01-01")
        eq(remeasure_required(before_day, before_day["acceptances"][0], "acceptance")[0], True,
           "and one measured the day before it is not")

        # Refusals around the re-measurement flags themselves.
        refuses(lambda: revalidate(_mstore(mag=_mag), "A-001", "2026-08-01", "2027-08-01",
                                   "ok", remeasured=8),
                "--remeasured without --measured-on is refused", "needs --measured-on")
        refuses(lambda: revalidate(_mstore(mag=_mag), "A-001", "2026-08-01", "2027-08-01",
                                   "ok", remeasured=8, measured_on="2026-09-15"),
                "a measurement dated after the review is refused", "after --on")
        refuses(lambda: accept_add(new_store("C"), "t", "CISO", "j", "2026-01-01",
                                   "2027-01-01", magnitude={"unit": "exposure"}),
                "a magnitude with no value is refused", "carries no value")
        refuses(lambda: accept_add(new_store("C"), "t", "CISO", "j", "2026-01-01",
                                   "2027-01-01",
                                   magnitude={"value": 3, "measuredAt": "2026-1-1"}),
                "a magnitude with a non-canonical date is refused", "zero-padded")

        # Nothing here filters, hides or blocks a derivation. The refusal lands on one act.
        # Renewed on 2026-08-01 to a review date close enough to be DUE at the `today`
        # below, so this record sits in the intersection the list is narrowed to: its
        # magnitude predates that renewal AND its next review is in range.
        stale_store = _mstore(mag=_mag)
        revalidate(stale_store, "A-001", "2026-08-01", "2026-09-15", "First.", actor="t")
        _sa = analyze(stale_store, "2026-09-01")
        eq(_sa["records"][0]["band"], STATUS_DUE, "the fixture's review really is due")
        eq(_sa["counts"]["active"], 1, "a stale magnitude still counts in the inventory")
        eq([r["id"] for r in _sa["records"]], ["A-001"], "and still appears in the analysis")
        eq(_sa["attention"]["remeasureNeeded"], ["A-001"],
           "surfaced on its own attention list once the review is actually due, so the "
           "measuring can be planned rather than discovered at the refusal")
        eq(_sa["records"][0]["remeasureReason"], "older-than-last-review",
           "with the reason carried, not just a boolean")
        eq(len(export_inventory(stale_store, "2026-09-01")), 1,
           "and still exports — the evidence artifact never drops it")
        # A record just re-measured and renewed is NOT on the list, and the reason it is not
        # is the reason this list is filtered rather than raw. `remeasureRequired` is already
        # True for it — the measurement it cited cannot carry the following renewal — but its
        # next review is a year out, so putting it on a review agenda now would be noise.
        # The first draft of this asserted the raw predicate here and failed, which is what
        # surfaced the distinction.
        _renewed = analyze(fresh, "2026-09-01")
        eq(_renewed["attention"]["remeasureNeeded"], [],
           "a record whose review is a year out stays off the agenda")
        eq(_renewed["records"][0]["remeasureRequired"], True,
           "even though its next renewal will still need a fresh measurement")
        eq(_renewed["records"][0]["band"], STATUS_CURRENT,
           "which is exactly the difference: required, but not yet due")
        # And it appears the moment the review comes into range.
        eq(analyze(fresh, "2027-12-15")["attention"]["remeasureNeeded"], ["A-001"],
           "and joins the agenda once its review is in the due window")

        # Exceptions carry it too, on the same terms as acceptances.
        xs = new_store("Exception Co")
        except_add(xs, "No MFA in finance", "NYDFS-500.12", "Out-of-band callback",
                   "CFO", "ERP upgrade blocks rollout.", "2026-01-01", "2026-09-01",
                   magnitude={"value": 9, "unit": "residual exposure",
                              "measuredAt": "2026-02-01"}, actor="t")
        revalidate(xs, "X-001", "2026-08-01", "2027-08-01", "Re-checked.", actor="t")
        refuses(lambda: revalidate(xs, "X-001", "2027-01-01", "2028-01-01", "Fine."),
                "an exception is refused on the same terms as an acceptance",
                "nobody has re-measured")

        # --- the bridge carries it ------------------------------------------------
        # `export-acceptances` stamps the magnitude; intake must keep it, or the refusal
        # above never fires for the records that came from the register that measured them.
        imported = new_store("Imported Co")
        import_acceptances(imported, [{
            "title": "Patch window", "approver": "CISO", "justification": "j",
            "acceptedDate": "2026-01-01", "revalidationDate": "2026-09-01",
            "sourceRiskRef": "R-006",
            "magnitude": {"value": 6, "unit": "residual exposure", "band": "medium",
                          "measuredAt": "2026-02-01", "source": "risk-register"},
        }], actor="t")
        eq(imported["acceptances"][0]["magnitude"]["value"], 6,
           "intake keeps the magnitude the bridge measured")
        eq(imported["acceptances"][0]["magnitude"]["source"], "risk-register",
           "and where it came from")

        # A refresh carrying no magnitude leaves the recorded one alone. Blanking it would
        # clear the re-measurement check on a record nobody re-measured, turning the bridge
        # into a way around the refusal.
        import_acceptances(imported, [{
            "title": "Patch window", "approver": "CISO", "justification": "j",
            "acceptedDate": "2026-01-01", "revalidationDate": "2026-10-01",
            "sourceRiskRef": "R-006",
        }], actor="t")
        eq(imported["acceptances"][0]["magnitude"]["value"], 6,
           "a magnitude-less refresh does not blank the magnitude already recorded")
        eq(imported["acceptances"][0]["revalidationDate"], "2026-10-01",
           "though it still refreshes everything else")
        _bad = import_acceptances(imported, [{
            "title": "Broken", "approver": "CISO", "justification": "j",
            "acceptedDate": "2026-01-01", "revalidationDate": "2026-10-01",
            "sourceRiskRef": "R-007", "magnitude": {"unit": "exposure"},
        }], actor="t")
        eq([r[0] for r in _bad["refused"]], ["R-007"],
           "a malformed magnitude refuses its own row and is reported")
        eq(len(imported["acceptances"]), 1,
           "and costs the other rows nothing — one bad row is not a failed intake")

        # --- the declared link across the bridge ----------------------------------
        # `risk-register` can escalate `acceptance-lapsed` on its own marker for the same
        # expiry this register escalates on the authoritative record. Declaring the source
        # risk lets a consumer notice one fact arriving twice without either register
        # knowing the other exists.
        linked = new_store("Linked Co")
        import_acceptances(linked, [{
            "title": "Vendor CRM records", "approver": "CISO", "justification": "j",
            "acceptedDate": "2026-01-01", "revalidationDate": "2026-02-01",
            "expiryDate": "2026-03-01", "sourceRiskRef": "R-010",
        }], actor="t")
        _le = escalations(linked, "2026-07-31")
        eq([(e["subjectRef"], e["trigger"], e["relatedRef"]) for e in _le],
           [("A-001", "expired", "R-010")],
           "an imported record declares the risk it is the acceptance of")

        # `riskIds` is NOT the join. An acceptance that merely relates to a risk is not the
        # same fact as an escalation about that risk, and treating it as one would invent
        # the false positive this link exists to avoid.
        related_only = new_store("Related Co")
        accept_add(related_only, "Merely linked", "CISO", "j", "2026-01-01", "2026-02-01",
                   expiry="2026-03-01", risk_ids=["R-003"], actor="t")
        eq([e["relatedRef"] for e in escalations(related_only, "2026-07-31")], [None],
           "a riskIds link is not identity, and does not become a relatedRef")

        # --- the refusals. This is the product. -----------------------------------
        save_store(path, store)
        before = open(path, "rb").read()

        refuses(lambda: accept_add(store, "No approver", "", "because", "2026-07-01",
                                   "2027-01-01"),
                "an acceptance with no approver is refused", "approver")
        refuses(lambda: accept_add(store, "No justification", "CISO", "", "2026-07-01",
                                   "2027-01-01"),
                "an acceptance with no justification is refused", "justification")
        refuses(lambda: accept_add(store, "No re-validation date", "CISO", "because",
                                   "2026-07-01", ""),
                "an acceptance with no re-validation date is refused", "revalidationDate")
        refuses(lambda: accept_add(store, "", "CISO", "because", "2026-07-01", "2027-01-01"),
                "an untitled acceptance is refused", "title")
        # All four at once, and the refusal names every one of them rather than the first.
        try:
            accept_add(store, "", "", "", "", "")
        except Refusal as exc:
            checks[0] += 1
            named = sum(1 for f in REQUIRED_COMMON if f in str(exc))
            if named != len(REQUIRED_COMMON):
                fails.append(f"a refusal names every missing field: named {named} of "
                             f"{len(REQUIRED_COMMON)}")
        refuses(lambda: except_add(store, "No compensating control", "CIS-4.1", "", "CISO",
                                   "because", "2026-07-01", "2027-01-01"),
                "an exception with no compensating control is refused", "launders it")
        refuses(lambda: except_add(store, "No deviation named", "", "callback", "CISO",
                                   "because", "2026-07-01", "2027-01-01"),
                "an exception that names no standard is refused", "deviationFrom")
        refuses(lambda: accept_add(store, "Bad date", "CISO", "because", "2026-7-1",
                                   "2027-01-01"),
                "an unpadded date is refused", "canonical zero-padded")
        refuses(lambda: accept_add(store, "Impossible date", "CISO", "because",
                                   "2026-02-30", "2027-01-01"),
                "an impossible calendar date is refused")
        refuses(lambda: revalidate(store, "A-001", "2026-07-31", "2027-07-01", ""),
                "re-validating without a rationale is refused", "not a timer reset")
        refuses(lambda: revalidate(store, "A-999", "2026-07-31", "2027-07-01", "x"),
                "re-validating an unknown id is refused")
        refuses(lambda: revalidate(store, "A-001", "2026-07-31", "2026-07-31", "x"),
                "a re-validation that does not move the clock forward is refused",
                "must be after")
        refuses(lambda: close_record(store, "A-001", ""),
                "closing without a reason is refused", "cannot be reconciled")

        ok(open(path, "rb").read() == before,
           "every refusal left the store byte-identical")

        # --- re-validation is an act, and it lands in history ----------------------
        revalidate(store, "X-001", "2026-07-31", "2027-07-31",
                   why="Reviewed with CFO; ERP upgrade slipped to Q1, exception still needed.",
                   actor="t")
        eq(store["exceptions"][0]["revalidationDate"], "2027-07-31", "the clock moved")
        ev = [h for h in store["history"] if h["event"] == "exception-revalidated"]
        eq(len(ev), 1, "one re-validation event")
        ok(ev[0].get("why"), "the rationale is in the change log, not just in the diff")
        eq(ev[0]["detail"]["from"], "2026-08-15", "the event records what the date was")

        # An expired record is still expired after re-validation: expiry is its own date.
        eq(status_band(store["exceptions"][0], "2026-10-01", 30), STATUS_EXPIRED,
           "re-validating does not move the expiry date")

        # --- a lapsed clock surfaces, it never deletes -----------------------------
        # A-001 re-validates 2027-01-01 and expires 2027-07-01, so at 2027-06-01 it is
        # past re-validation but not yet expired — overdue is the right band.
        late = analyze(store, "2027-06-01")
        eq(late["attention"]["overdue"], ["A-001"], "a lapsed re-validation date surfaces")
        eq({r["id"]: r["band"] for r in late["records"]}["A-001"], STATUS_OVERDUE,
           "an acceptance past its re-validation date reports overdue")
        ok(any(r["id"] == "A-001" for r in export_inventory(store, "2027-06-01")),
           "and it stays IN the inventory — the organisation is still carrying it")

        # --- close removes from the inventory but not from the store ---------------
        close_record(store, "A-001", why="Patching programme funded; risk no longer accepted.",
                     actor="t")
        eq(len(store["acceptances"]), 1, "closing does not delete the record")
        inv = export_inventory(store, "2027-06-01")
        ok(not any(r["id"] == "A-001" for r in inv),
           "a closed record leaves the active inventory")
        refuses(lambda: close_record(store, "A-001", "again"),
                "closing an already-closed record is refused")
        refuses(lambda: revalidate(store, "A-001", "2027-06-01", "2028-01-01", "x"),
                "re-validating a closed record is refused", "closed")

        # --- the export is the artifact an auditor is handed -----------------------
        store2 = new_store("Export Co")
        accept_add(store2, "Accepted A", "CISO", "because", "2026-01-01", "2027-01-01")
        except_add(store2, "Exception B", "CIS-4.1", "monitoring", "CISO", "because",
                   "2026-01-01", "2027-01-01")
        rows = export_inventory(store2, "2026-07-31")
        eq(len(rows), 2, "both types appear in one inventory")
        eq(sorted(r["type"] for r in rows), ["acceptance", "exception"], "type column")
        csv_text = inventory_csv(rows)
        eq(csv_text.splitlines()[0], ",".join(INVENTORY_COLUMNS), "CSV header is the contract")
        eq(len(csv_text.strip().splitlines()), 3, "header plus two rows")
        ok("justification" in csv_text.splitlines()[0],
           "the justification travels with the export — it is the artifact, not a note")

        # --- family guard ----------------------------------------------------------
        other = os.path.join(work, "other.mtr")
        with open(other, "w", encoding="utf-8") as fh:
            json.dump({"schemaVersion": 1, "family": "metrics-register"}, fh)
        refuses(lambda: load_store(other),
                "a metrics register handed to this engine is refused by family",
                "not an exceptions register")

        # Round-trip changes nothing derived.
        save_store(path, store)
        eq(analyze(load_store(path), "2026-07-31"), analyze(store, "2026-07-31"),
           "save/load round-trips without changing a derived figure")
    finally:
        shutil.rmtree(work, ignore_errors=True)

    if fails:
        print("FAILED:")
        for f in fails: print(f"  - {f}")
        print(f"self-test: {checks[0] - len(fails)}/{checks[0]} checks passed")
        return 1
    print(f"self-test: {checks[0]}/{checks[0]} checks passed")
    return 0


# --- CLI ----------------------------------------------------------------------

def _cmd_init(args):
    if os.path.exists(args.store):
        raise Refusal(f"{args.store} already exists; init would overwrite it")
    store = new_store(args.client, args.owner, args.scope_note, args.due_window_days)
    append_history(store, "register-created", args.store, args.actor)
    save_store(args.store, store)
    print(f"Created {args.store}")
    print(f"  re-validation shows as due {store['settings']['dueWindowDays']} days ahead.")
    print("  Next: accept-add or except-add. Both refuse without approver, "
          "justification and a re-validation date.")
    return 0


def _num(raw, flag: str):
    """A magnitude from the command line. `None` stays `None` — the flag is optional.

    Integral input stays an int so a store written by the CLI and one written by the
    risk-register bridge hold the same JSON for the same number; `6.0` and `6` are the same
    measurement and should not read as two.
    """
    if raw is None:
        return None
    text = str(raw).strip()
    try:
        return int(text)
    except ValueError:
        pass
    try:
        return float(text)
    except ValueError:
        raise Refusal(f"{flag} must be a number; got {raw!r}. A magnitude that is not a "
                      f"quantity cannot be compared with the next measurement of it.")


def _magnitude_from_args(args):
    """Build a magnitude from the add-command flags, or `None` if none were given.

    `--measured-on` without `--magnitude` is refused rather than ignored: it means the
    caller believes they recorded a measurement, and silently dropping it would leave the
    record looking quantified to its author and unquantified to the engine.
    """
    value = _num(getattr(args, "magnitude", None), "--magnitude")
    measured = str(getattr(args, "measured_on", "") or "").strip()
    if value is None:
        if measured:
            raise Refusal("--measured-on was given without --magnitude: there is no "
                          "measurement for that date to belong to")
        return None
    return {"value": value, "unit": getattr(args, "magnitude_unit", "") or "",
            "measuredAt": measured or None, "source": "recorded here"}


def _cmd_accept_add(args):
    store = load_store(args.store)
    r = accept_add(store, args.title, args.approver, args.justification, args.accepted,
                   args.revalidation, args.expiry, args.description, args.risk, args.csf,
                   args.source_risk_ref, magnitude=_magnitude_from_args(args),
                   actor=args.actor)
    save_store(args.store, store)
    print(f"{r['id']}: {r['title']}  (approved by {r['approver']}, "
          f"re-validate by {r['revalidationDate']})")
    return 0


def _cmd_except_add(args):
    store = load_store(args.store)
    r = except_add(store, args.title, args.deviation_from, args.compensating, args.approver,
                   args.justification, args.accepted, args.revalidation, args.expiry,
                   args.risk, args.csf, magnitude=_magnitude_from_args(args),
                   actor=args.actor)
    save_store(args.store, store)
    print(f"{r['id']}: {r['title']}  (deviates from {r['deviationFrom']}, "
          f"re-validate by {r['revalidationDate']})")
    return 0


def _cmd_revalidate(args):
    store = load_store(args.store)
    r = revalidate(store, args.id, args.on, args.next, args.why,
                   remeasured=_num(args.remeasured, "--remeasured"),
                   measured_on=args.measured_on, magnitude_unit=args.magnitude_unit,
                   actor=args.actor)
    save_store(args.store, store)
    print(f"{r['id']} re-validated on {args.on}; next review {r['revalidationDate']}")
    mag = r.get("magnitude")
    if mag and mag.get("measuredAt") == args.measured_on and args.remeasured is not None:
        print(f"  re-measured to {mag['value']}"
              f"{(' ' + mag['unit']) if mag.get('unit') else ''} on {mag['measuredAt']}")
    return 0


def _cmd_close(args):
    store = load_store(args.store)
    r = close_record(store, args.id, args.why, args.actor)
    save_store(args.store, store)
    print(f"{r['id']} closed")
    return 0


def _cmd_link(args):
    store = load_store(args.store)
    r = link_record(store, args.id, args.risk, args.csf, args.incident, args.actor)
    save_store(args.store, store)
    print(f"{r['id']} → risks {r['riskIds'] or '—'} · CSF {r['csfSubcategoryIds'] or '—'}"
          f" · incidents {r['incidentIds'] or '—'}")
    return 0


def _today(args) -> str:
    return check_date(args.today, "--today") if args.today else date.today().isoformat()


def _cmd_analyze(args):
    context = load_context(args.context) if args.context else None
    out = analyze(load_store(args.store), _today(args), context)
    text = json.dumps(out, indent=2, ensure_ascii=False)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
        print(f"wrote {args.out}")
    else:
        print(text)
    return 0


def _cmd_export(args):
    rows = export_inventory(load_store(args.store), _today(args))
    text = (inventory_csv(rows) if args.format == "csv"
            else json.dumps(rows, indent=2, ensure_ascii=False) + "\n")
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text)
        print(f"wrote {args.out} — {len(rows)} active records")
    else:
        sys.stdout.write(text)
    return 0


def _cmd_import(args):
    store = load_store(args.store)
    try:
        with open(args.src, encoding="utf-8") as fh:
            rows = json.load(fh)
    except FileNotFoundError:
        raise Refusal(f"no such intake file: {args.src}")
    except json.JSONDecodeError as exc:
        raise Refusal(f"{args.src} is not valid JSON: {exc.msg}")
    res = import_acceptances(store, rows, args.actor)
    save_store(args.store, store)
    print(f"added {len(res['added'])}, updated {len(res['updated'])}, "
          f"refused {len(res['refused'])}")
    for rid, why in res["refused"]:
        print(f"  refused {rid}: {why}", file=sys.stderr)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="exceptions_register.py",
                                description=__doc__.split("\n")[0],
                                epilog="This tool is not legal advice.",
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd")

    def common(sp):
        sp.add_argument("store")
        sp.add_argument("--actor", default="")

    sp = sub.add_parser("init"); common(sp)
    sp.add_argument("--client", required=True)
    sp.add_argument("--owner", default="")
    sp.add_argument("--scope-note", default="")
    sp.add_argument("--due-window-days", type=int, default=DEFAULT_DUE_WINDOW_DAYS)
    sp.set_defaults(fn=_cmd_init)

    sp = sub.add_parser("accept-add", help="record an accepted residual risk"); common(sp)
    sp.add_argument("--title", default="")
    sp.add_argument("--approver", default="")
    sp.add_argument("--justification", default="")
    sp.add_argument("--accepted", default="")
    sp.add_argument("--revalidation", default="")
    sp.add_argument("--expiry", default="")
    sp.add_argument("--description", default="")
    sp.add_argument("--risk", action="append", default=[])
    sp.add_argument("--csf", action="append", default=[])
    sp.add_argument("--source-risk-ref", default="")
    sp.add_argument("--magnitude", default=None,
                    help="what this was accepted against, as a number")
    sp.add_argument("--magnitude-unit", default="",
                    help="what that number counts (e.g. 'residual exposure')")
    sp.add_argument("--measured-on", default="", help="the date it was measured")
    sp.set_defaults(fn=_cmd_accept_add)

    sp = sub.add_parser("except-add", help="record a control/policy deviation"); common(sp)
    sp.add_argument("--title", default="")
    sp.add_argument("--deviation-from", default="")
    sp.add_argument("--compensating", default="")
    sp.add_argument("--approver", default="")
    sp.add_argument("--justification", default="")
    sp.add_argument("--accepted", default="")
    sp.add_argument("--revalidation", default="")
    sp.add_argument("--expiry", default="")
    sp.add_argument("--risk", action="append", default=[])
    sp.add_argument("--csf", action="append", default=[])
    sp.add_argument("--magnitude", default=None,
                    help="what this was accepted against, as a number")
    sp.add_argument("--magnitude-unit", default="",
                    help="what that number counts (e.g. 'residual exposure')")
    sp.add_argument("--measured-on", default="", help="the date it was measured")
    sp.set_defaults(fn=_cmd_except_add)

    sp = sub.add_parser("revalidate", help="record that a human re-checked the reasoning")
    common(sp)
    sp.add_argument("--id", required=True)
    sp.add_argument("--on", required=True)
    sp.add_argument("--next", required=True)
    sp.add_argument("--why", default="")
    sp.add_argument("--remeasured", default=None,
                    help="a fresh magnitude, measured for THIS review")
    sp.add_argument("--measured-on", default="", help="the date --remeasured was taken")
    sp.add_argument("--magnitude-unit", default="",
                    help="only needed when establishing a magnitude this record never had")
    sp.set_defaults(fn=_cmd_revalidate)

    sp = sub.add_parser("close"); common(sp)
    sp.add_argument("--id", required=True)
    sp.add_argument("--why", default="")
    sp.set_defaults(fn=_cmd_close)

    sp = sub.add_parser("link"); common(sp)
    sp.add_argument("--id", required=True)
    sp.add_argument("--risk", action="append", default=[])
    sp.add_argument("--csf", action="append", default=[])
    sp.add_argument("--incident", action="append", default=[])
    sp.set_defaults(fn=_cmd_link)

    sp = sub.add_parser("analyze"); common(sp)
    sp.add_argument("--today", default=None)
    sp.add_argument("--out", default=None)
    sp.add_argument("--context", default=None, metavar="FILE",
                    help="a CAC-AP-1 applicability payload from "
                         "`business_context.py export`")
    sp.set_defaults(fn=_cmd_analyze)

    sp = sub.add_parser("export-inventory", help="the DORA evidence artifact"); common(sp)
    sp.add_argument("--today", default=None)
    sp.add_argument("--format", choices=("csv", "json"), default="csv")
    sp.add_argument("--out", default=None)
    sp.set_defaults(fn=_cmd_export)

    sp = sub.add_parser("import-acceptances",
                        help="take risk-register's export-acceptances output"); common(sp)
    sp.add_argument("--from", dest="src", required=True,
                    help="JSON written by score_register.py export-acceptances")
    sp.set_defaults(fn=_cmd_import)

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


if __name__ == "__main__":
    sys.exit(main())
