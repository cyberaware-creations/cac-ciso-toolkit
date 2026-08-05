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
               risk_ids=(), csf_ids=(), source_risk_ref: str = "",
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
        "notes": "",
    }
    store["acceptances"].append(rec)
    append_history(store, "acceptance-added", rec["id"], actor,
                   detail={"title": rec["title"], "approver": rec["approver"]})
    return rec


def except_add(store: dict, title: str, deviation_from: str, compensating: str,
               approver: str, justification: str, accepted: str, revalidation: str,
               expiry: str = "", risk_ids=(), csf_ids=(), actor: str = "") -> dict:
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
        "notes": "",
    }
    store["exceptions"].append(rec)
    append_history(store, "exception-added", rec["id"], actor,
                   detail={"title": rec["title"], "deviationFrom": rec["deviationFrom"]})
    return rec


def revalidate(store: dict, rid: str, on: str, next_date: str, why: str,
               actor: str = "") -> dict:
    """Record that a human re-checked the reasoning and it still holds.

    Refuses without a rationale. Re-validation is the act DORA RTS Art. 3(d)(iv) asks an
    organisation to demonstrate; an event with no stated reason is indistinguishable from
    an automated renewal, which is the practice the requirement exists to rule out.
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
    previous = rec["revalidationDate"]
    rec["revalidationDate"] = next_date
    append_history(store, f"{kind}-revalidated", rid, actor, why=why,
                   detail={"on": on, "from": previous, "to": next_date})
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
            append_history(store, "acceptance-updated", existing["id"], actor,
                           why=f"refreshed from {src} via export-acceptances")
            updated.append(existing["id"])
        else:
            rec = accept_add(store, row["title"], row["approver"], row["justification"],
                             row["acceptedDate"], row["revalidationDate"],
                             row.get("expiryDate") or "",
                             risk_ids=row.get("riskIds") or [],
                             csf_ids=row.get("csfSubcategoryIds") or [],
                             source_risk_ref=src or "", actor=actor)
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


def derive(store: dict, rec: dict, kind: str, today: str, window: int) -> dict:
    reval = rec.get("revalidationDate")
    expiry = rec.get("expiryDate")
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
    }


def analyze(store: dict, today: str) -> dict:
    window = int((store.get("settings") or {}).get("dueWindowDays")
                 or DEFAULT_DUE_WINDOW_DAYS)
    rows = ([derive(store, r, "acceptance", today, window) for r in store["acceptances"]]
            + [derive(store, r, "exception", today, window) for r in store["exceptions"]])
    active = [r for r in rows if r["band"] != STATUS_CLOSED]
    return {
        "meta": dict(store.get("meta") or {}),
        "today": today,
        "dueWindowDays": window,
        "records": rows,
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


def _cmd_accept_add(args):
    store = load_store(args.store)
    r = accept_add(store, args.title, args.approver, args.justification, args.accepted,
                   args.revalidation, args.expiry, args.description, args.risk, args.csf,
                   args.source_risk_ref, args.actor)
    save_store(args.store, store)
    print(f"{r['id']}: {r['title']}  (approved by {r['approver']}, "
          f"re-validate by {r['revalidationDate']})")
    return 0


def _cmd_except_add(args):
    store = load_store(args.store)
    r = except_add(store, args.title, args.deviation_from, args.compensating, args.approver,
                   args.justification, args.accepted, args.revalidation, args.expiry,
                   args.risk, args.csf, args.actor)
    save_store(args.store, store)
    print(f"{r['id']}: {r['title']}  (deviates from {r['deviationFrom']}, "
          f"re-validate by {r['revalidationDate']})")
    return 0


def _cmd_revalidate(args):
    store = load_store(args.store)
    r = revalidate(store, args.id, args.on, args.next, args.why, args.actor)
    save_store(args.store, store)
    print(f"{r['id']} re-validated on {args.on}; next review {r['revalidationDate']}")
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
    out = analyze(load_store(args.store), _today(args))
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
    sp.set_defaults(fn=_cmd_except_add)

    sp = sub.add_parser("revalidate", help="record that a human re-checked the reasoning")
    common(sp)
    sp.add_argument("--id", required=True)
    sp.add_argument("--on", required=True)
    sp.add_argument("--next", required=True)
    sp.add_argument("--why", default="")
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
