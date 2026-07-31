#!/usr/bin/env python3
"""incident_analysis.py — structure and record a materiality determination; run the clocks.

Two halves, and they are deliberately unequal.

The **judgment** half records what a human decided. Six materiality factors, each assessed with
a written rationale by a named person on a date; a determination state with its rationale and its
decider; a disclosure decision with its basis. Every one of these is appended, never overwritten,
because the reconstructable "what did we know and when did we decide it" record is the entire
defensibility story. Nothing here is computed, suggested or defaulted by the engine: it never
emits a materiality verdict, never scores the factors, and never counts how many came back
`bearing`. A materiality determination is a legal judgment made with counsel.

The **clock** half is deterministic and has to be exactly right, because it is the only thing
here the engine actually claims to know. SEC Item 1.05 runs four business days from the
DETERMINATION date — not the discovery date — and an incident under honest assessment therefore
has no running clock at all. DORA runs in clock hours from awareness and from classification, so
its anchors are timestamps and a missing one reports `anchor-missing` rather than a manufactured
midnight.

Scope: SEC Item 1.05 and DORA only. See references/disclosure-clocks.md for every limit.

Standard library only. Subcommands:

  init          <store.inc> --client 'Name' [--owner ..] [--holiday YYYY-MM-DD ...]
  open          <store.inc> --title '..' --discovered YYYY-MM-DD [--regime sec-1.05|dora ...]
  assess-factor <store.inc> --id I-001 --factor data --assessment bearing|no-bearing|unknown
                            --rationale '..' [--related I-002 ...]
  determine     <store.inc> --id I-001 --state assessing|material|not-material|not-yet-determinable
                            --rationale '..' --decider '..' --on YYYY-MM-DD
  set-anchor    <store.inc> --id I-001 [--aware YYYY-MM-DDTHH:MM] [--classified ..]
  set-disclosure <store.inc> --id I-001 --decision pending|file|no-file --basis '..'
  record-filing <store.inc> --id I-001 --window sec-1.05:8-K --at YYYY-MM-DD
  link          <store.inc> --id I-001 [--risk R-006] [--exception A-001]
  close         <store.inc> --id I-001 --why '..'
  analyze       <store.inc> [--today YYYY-MM-DD] [--now ISO-8601] [--out FILE]
  self-test

This tool is not legal advice.
"""
from __future__ import annotations

import argparse
import calendar
import json
import os
import re
import sys
import tempfile
from datetime import date, datetime, timedelta, timezone

SCHEMA_VERSION = 1
FAMILY = "incident-materiality"

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2})?([+-]\d{2}:\d{2}|Z)?$")
INCIDENT_ID_RE = re.compile(r"^I-\d{3,}$")

# The six factors, fixed and documented one by one in references/materiality-factors.md.
FACTOR_KEYS = ("financial", "operational", "data", "regulatory", "reputational", "aggregation")

# Three words, chosen because they do not add up. There is no scale, no weight and no total:
# a materiality determination is a legal standard, not an arithmetic, and a score would invite
# its user to defend a number they did not choose.
ASSESSMENTS = ("bearing", "no-bearing", "unknown")

DETERMINATION_STATES = ("assessing", "material", "not-material", "not-yet-determinable")
DISCLOSURE_DECISIONS = ("pending", "file", "no-file")

REGIMES = ("sec-1.05", "dora")
WINDOWS = {"sec-1.05": ("8-K",), "dora": ("initial", "intermediate", "final")}
# SEC filings are recorded as a date, DORA filings as a timestamp — the two regimes count
# different units, and a filing recorded in the wrong one cannot anchor the next window.
WINDOW_PRECISION = {"sec-1.05:8-K": "date", "dora:initial": "ts",
                    "dora:intermediate": "ts", "dora:final": "ts"}

SEC_BUSINESS_DAYS = 4
DORA_INITIAL_FROM_CLASSIFIED_H = 4
DORA_INITIAL_FROM_AWARE_H = 24
DORA_INTERMEDIATE_FROM_INITIAL_H = 72
DORA_FINAL_FROM_INTERMEDIATE_MONTHS = 1

BAND_NO_DETERMINATION = "no-determination"
BAND_ASSESSING = "assessing"
BAND_NOT_YET = "not-yet-determinable"
BAND_NOT_MATERIAL = "not-material"
BAND_MATERIAL = "material"
BAND_DUE = "disclosure-due"
BAND_OVERDUE = "disclosure-overdue"
BAND_FILED = "filed"
BAND_CLOSED = "closed"
INCIDENT_BANDS = (BAND_NO_DETERMINATION, BAND_ASSESSING, BAND_NOT_YET, BAND_NOT_MATERIAL,
                  BAND_MATERIAL, BAND_DUE, BAND_OVERDUE, BAND_FILED, BAND_CLOSED)

CLOCK_NA = "not-applicable"
CLOCK_NOT_STARTED = "not-started"
CLOCK_ANCHOR_MISSING = "anchor-missing"
CLOCK_DUE = "due"
CLOCK_OVERDUE = "overdue"
CLOCK_FILED = "filed"
CLOCK_STATES = (CLOCK_NA, CLOCK_NOT_STARTED, CLOCK_ANCHOR_MISSING, CLOCK_DUE, CLOCK_OVERDUE,
                CLOCK_FILED)


class Refusal(Exception):
    """A mutation the engine declines to perform.

    Raised before the store file is opened, so a refused mutation leaves the file
    byte-identical. Asserted in self-test rather than trusted.
    """


# --- Dates and timestamps -----------------------------------------------------

def check_date(value: str, field: str) -> str:
    """Canonical `YYYY-MM-DD`, and a real calendar date, or a refusal."""
    if not isinstance(value, str) or not DATE_RE.match(value):
        raise Refusal(
            f"{field} must be a canonical zero-padded date, YYYY-MM-DD; got {value!r}. "
            f"'2026-7-1' is refused because it sorts after '2026-10-01' as text, and every "
            f"clock here compares dates.")
    try:
        date.fromisoformat(value)
    except ValueError:
        raise Refusal(f"{field} is not a real calendar date: {value!r}")
    return value


def check_ts(value: str, field: str) -> str:
    """Canonical `YYYY-MM-DDTHH:MM` (seconds and offset optional), or a refusal.

    A bare date is refused rather than read as midnight. DORA counts clock hours, so a
    date-precision anchor would produce an hour-precision deadline that looks exact and is
    invented — which is worse than a visible gap in the record.
    """
    if not isinstance(value, str) or not TS_RE.match(value):
        extra = ""
        if isinstance(value, str) and DATE_RE.match(value):
            extra = (" A bare date is not enough here: DORA counts clock hours, and reading "
                     "this as midnight would manufacture precision you did not record.")
        raise Refusal(f"{field} must be a canonical timestamp, YYYY-MM-DDTHH:MM "
                      f"(seconds and offset optional); got {value!r}.{extra}")
    try:
        parse_ts(value)
    except ValueError:
        raise Refusal(f"{field} is not a real timestamp: {value!r}")
    return value


def parse_ts(value: str) -> datetime:
    dt = datetime.fromisoformat(value[:-1] + "+00:00" if value.endswith("Z") else value)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def fmt_ts(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def days_between(earlier: str, later: str) -> int:
    return (date.fromisoformat(later) - date.fromisoformat(earlier)).days


def hours_between(earlier: str, later: str) -> float:
    return (parse_ts(later) - parse_ts(earlier)).total_seconds() / 3600.0


def now_ts() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def is_business_day(d: date, holidays) -> bool:
    return d.weekday() < 5 and d.isoformat() not in holidays


def business_days_after(anchor: str, n: int, holidays=()) -> str:
    """The date `n` business days after `anchor`.

    The anchor day is day zero and is never counted, whether or not it is itself a business
    day — which is why a Friday determination and a Saturday determination land on the same
    deadline. A business day is any day that is not a Saturday, not a Sunday, and not in the
    supplied holiday calendar. Worked examples live in references/disclosure-clocks.md and are
    pinned in self-test.
    """
    hol = set(holidays or ())
    d = date.fromisoformat(anchor)
    counted = 0
    while counted < n:
        d += timedelta(days=1)
        if is_business_day(d, hol):
            counted += 1
    return d.isoformat()


def business_days_between(start: str, end: str, holidays=()) -> int:
    """Signed count of business days from `start` to `end`, excluding `start`."""
    hol = set(holidays or ())
    a, b = date.fromisoformat(start), date.fromisoformat(end)
    step = 1 if b >= a else -1
    count, d = 0, a
    while d != b:
        d += timedelta(days=step)
        if is_business_day(d, hol):
            count += step
    return count


def add_months(dt: datetime, n: int) -> datetime:
    year = dt.year + (dt.month - 1 + n) // 12
    month = (dt.month - 1 + n) % 12 + 1
    day = min(dt.day, calendar.monthrange(year, month)[1])
    return dt.replace(year=year, month=month, day=day)


# --- Store IO -----------------------------------------------------------------

def new_store(client: str, owner: str = "", scope_note: str = "", holidays=()) -> dict:
    ts = now_ts()
    return {
        "schemaVersion": SCHEMA_VERSION,
        "family": FAMILY,
        "meta": {"clientName": client, "owner": owner, "scopeNote": scope_note,
                 "asOf": ts[:10]},
        "settings": {"holidays": sorted(set(holidays or ()))},
        "incidents": [],
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
            f"{path} is not an incident store: family is {fam!r}, expected {FAMILY!r}. "
            f"A risk register (.rr), CSF profile (.csfp), metrics register (.mtr) or "
            f"exceptions register (.exc) belongs to a different skill.")
    if store.get("schemaVersion") != SCHEMA_VERSION:
        raise Refusal(f"{path} is schemaVersion {store.get('schemaVersion')!r}; "
                      f"this engine reads {SCHEMA_VERSION}")
    for key, kind in (("incidents", list), ("history", list), ("meta", dict),
                      ("settings", dict)):
        if not isinstance(store.get(key), kind):
            raise Refusal(f"{path} is missing or malformed {key!r}")
    return store


def save_store(path: str, store: dict) -> None:
    store["updatedAt"] = now_ts()
    directory = os.path.dirname(os.path.abspath(path)) or "."
    fd, tmp = tempfile.mkstemp(dir=directory, suffix=".inc.tmp")
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
                   why: str = "", detail: dict = None) -> None:
    entry = {"event": event, "target": target, "actor": actor or "", "ts": now_ts()}
    if why:
        entry["why"] = why
    if detail:
        entry["detail"] = detail
    store["history"].append(entry)


def next_id(store: dict) -> str:
    used = [int(r["id"].split("-")[1]) for r in store["incidents"]
            if INCIDENT_ID_RE.match(r.get("id", ""))]
    return "I-%03d" % ((max(used) + 1) if used else 1)


def find_incident(store: dict, iid: str) -> dict:
    for r in store["incidents"]:
        if r.get("id") == iid:
            return r
    known = ", ".join(r["id"] for r in store["incidents"]) or "none yet"
    raise Refusal(f"no incident {iid!r} in this store (have: {known})")


def holidays_of(store: dict) -> set:
    return set((store.get("settings") or {}).get("holidays") or ())


def _one_of(value: str, allowed, flag: str) -> str:
    if value not in allowed:
        raise Refusal(f"{flag} must be one of {', '.join(allowed)}; got {value!r}")
    return value


def _required_text(value: str, flag: str, why: str) -> str:
    if not str(value or "").strip():
        raise Refusal(f"{flag} is required: {why}")
    return str(value).strip()


# --- Mutations ----------------------------------------------------------------

def open_incident(store: dict, title: str, discovered: str, scope_note: str = "",
                  regimes=(), actor: str = "") -> dict:
    _required_text(title, "--title", "an untitled incident cannot be reviewed")
    check_date(discovered, "--discovered")
    regs = list(dict.fromkeys(regimes or ()))
    for r in regs:
        _one_of(r, REGIMES, "--regime")
    rec = {
        "id": next_id(store),
        "title": title.strip(),
        "discoveredAt": discovered,
        "scopeNote": scope_note or "",
        "status": "open",
        "factors": [],
        "determinations": [],
        "disclosure": {"regimes": regs, "decision": "pending", "basis": "", "filings": {}},
        "anchors": {"awareAt": None, "classifiedAt": None},
        "linkedRiskIds": [],
        "linkedExceptionIds": [],
        "notes": "",
    }
    store["incidents"].append(rec)
    append_history(store, "incident-opened", rec["id"], actor,
                   detail={"title": rec["title"], "discoveredAt": discovered,
                           "regimes": regs})
    return rec


def assess_factor(store: dict, iid: str, key: str, assessment: str, rationale: str,
                  related=(), actor: str = "") -> dict:
    """Append one factor assessment. Never replaces an earlier one.

    Re-assessing a factor after the forensics report lands adds a second entry and leaves the
    first in place. The sequence is the answer to "when did you know?", and an implementation
    that overwrote would destroy the record exactly where it is most needed.
    """
    inc = find_incident(store, iid)
    _one_of(key, FACTOR_KEYS, "--factor")
    _one_of(assessment, ASSESSMENTS, "--assessment")
    _required_text(
        rationale, "--rationale",
        "an assessment with no rationale is a ticked box, and a ticked box is not a record "
        "of a judgment. The basis is the artifact here, not the verdict.")
    entry = {
        "key": key,
        "assessment": assessment,
        "rationale": rationale.strip(),
        "relatedIncidentIds": list(related or []),
        "actor": actor or "",
        "ts": now_ts(),
    }
    inc["factors"].append(entry)
    append_history(store, "factor-assessed", iid, actor,
                   detail={"factor": key, "assessment": assessment})
    return entry


def determine(store: dict, iid: str, state: str, rationale: str, decider: str,
              on: str, actor: str = "") -> dict:
    """Append a determination. The engine never writes one by itself.

    Nothing in this tool computes, suggests or defaults a state. The factors are recorded so a
    human can reason from them; the reasoning and the conclusion belong to that human, made
    with counsel. `determinedAt` is required and is not allowed to default to today, because
    it is the anchor the Item 1.05 clock runs from.
    """
    inc = find_incident(store, iid)
    _one_of(state, DETERMINATION_STATES, "--state")
    _required_text(rationale, "--rationale",
                   "a determination without its basis is not a record of a judgment, and the "
                   "basis is the whole artifact")
    _required_text(decider, "--decider",
                   "a determination nobody made is not a determination; name who made it")
    check_date(on, "--on")
    current = current_determination(inc)
    entry = {"state": state, "rationale": rationale.strip(), "decider": decider.strip(),
             "determinedAt": on, "ts": now_ts()}
    inc["determinations"].append(entry)
    append_history(store, "determination-recorded", iid, actor,
                   detail={"state": state, "from": current["state"] if current else None,
                           "determinedAt": on, "decider": entry["decider"]})
    return entry


def set_anchor(store: dict, iid: str, aware: str = "", classified: str = "",
               actor: str = "") -> dict:
    inc = find_incident(store, iid)
    if not (aware or classified):
        raise Refusal("set-anchor needs --aware or --classified (or both)")
    if aware:
        check_ts(aware, "--aware")
        inc["anchors"]["awareAt"] = aware
    if classified:
        check_ts(classified, "--classified")
        inc["anchors"]["classifiedAt"] = classified
    append_history(store, "anchor-set", iid, actor,
                   detail={k: v for k, v in (("awareAt", aware),
                                             ("classifiedAt", classified)) if v})
    return inc["anchors"]


def set_disclosure(store: dict, iid: str, decision: str, basis: str, regimes=(),
                   actor: str = "") -> dict:
    inc = find_incident(store, iid)
    _one_of(decision, DISCLOSURE_DECISIONS, "--decision")
    if decision != "pending":
        _required_text(basis, "--basis",
                       "a disclosure decision with no recorded basis is the one thing a "
                       "regulator will ask about and the one thing you will not have")
    if regimes:
        for r in regimes:
            _one_of(r, REGIMES, "--regime")
        inc["disclosure"]["regimes"] = list(dict.fromkeys(regimes))
    inc["disclosure"]["decision"] = decision
    if basis:
        inc["disclosure"]["basis"] = basis.strip()
    append_history(store, "disclosure-set", iid, actor,
                   detail={"decision": decision, "regimes": inc["disclosure"]["regimes"]})
    return inc["disclosure"]


def record_filing(store: dict, iid: str, window: str, at: str, actor: str = "") -> dict:
    inc = find_incident(store, iid)
    if window not in WINDOW_PRECISION:
        raise Refusal(f"--window must be one of {', '.join(sorted(WINDOW_PRECISION))}; "
                      f"got {window!r}")
    regime = window.split(":", 1)[0]
    if regime not in (inc["disclosure"]["regimes"] or ()):
        raise Refusal(
            f"{iid} is not tracked against {regime}; set-disclosure --regime {regime} first. "
            f"Recording a filing under a regime the incident is not in scope for would put a "
            f"date in the record that nothing owed.")
    if WINDOW_PRECISION[window] == "date":
        check_date(at, "--at")
    else:
        check_ts(at, "--at")
    inc["disclosure"]["filings"][window] = at
    append_history(store, "filing-recorded", iid, actor, detail={"window": window, "at": at})
    return inc["disclosure"]["filings"]


def link_incident(store: dict, iid: str, risk_ids=(), exception_ids=(),
                  actor: str = "") -> dict:
    inc = find_incident(store, iid)
    added = {"risk": [], "exception": []}
    for key, ids, slot in (("linkedRiskIds", risk_ids, "risk"),
                           ("linkedExceptionIds", exception_ids, "exception")):
        for i in ids or ():
            if i not in inc[key]:
                inc[key].append(i)
                added[slot].append(i)
    if any(added.values()):
        append_history(store, "incident-linked", iid, actor, detail=added)
    return inc


def close_incident(store: dict, iid: str, why: str, actor: str = "") -> dict:
    inc = find_incident(store, iid)
    _required_text(why, "--why",
                   "an incident that leaves the workspace without a reason cannot be "
                   "reconciled later")
    if inc.get("status") == "closed":
        raise Refusal(f"{iid} is already closed")
    inc["status"] = "closed"
    append_history(store, "incident-closed", iid, actor, why=why)
    return inc


# --- Derivations (nothing here is ever stored) --------------------------------

def current_determination(inc: dict):
    dets = inc.get("determinations") or []
    return dets[-1] if dets else None


def current_factors(inc: dict) -> dict:
    """Latest assessment per key. Earlier ones stay in the record and are returned too."""
    out = {}
    for f in inc.get("factors") or []:
        out[f["key"]] = f
    return out


def _clock(regime: str, window: str, state: str, anchor=None, anchor_kind: str = "",
           deadline=None, filed=None, note: str = "", **extra) -> dict:
    row = {"regime": regime, "window": window, "state": state, "anchor": anchor,
           "anchorKind": anchor_kind, "deadline": deadline, "filedAt": filed, "note": note}
    row.update(extra)
    return row


def sec_clock(inc: dict, today: str, holidays) -> dict:
    """Item 1.05: four business days from the DETERMINATION date, not the discovery date.

    Getting this backwards fails in both directions. Anchoring on discovery invents a deadline
    that does not exist and would eventually push somebody into filing something they had not
    yet decided was true; so an incident under honest assessment reports `not-started`, with no
    deadline and nothing red. That is not a loophole — `analyze` separately reports the days
    elapsed with no determination recorded — but it is not a deadline either.
    """
    regime, window = "sec-1.05", "8-K"
    key = "sec-1.05:8-K"
    if regime not in (inc["disclosure"]["regimes"] or ()):
        return _clock(regime, window, CLOCK_NA,
                      note="this incident is not tracked against SEC Item 1.05")
    det = current_determination(inc)
    filed = (inc["disclosure"]["filings"] or {}).get(key)
    if det is None or det["state"] != "material":
        reason = ("no determination has been recorded" if det is None
                  else f"the current determination is {det['state']!r}")
        return _clock(regime, window, CLOCK_NOT_STARTED, filed=filed,
                      note=f"the Item 1.05 clock starts at a determination of material; "
                           f"{reason}")
    anchor = det["determinedAt"]
    deadline = business_days_after(anchor, SEC_BUSINESS_DAYS, holidays)
    state = (CLOCK_FILED if filed
             else CLOCK_OVERDUE if days_between(today, deadline) < 0 else CLOCK_DUE)
    return _clock(regime, window, state, anchor=anchor, anchor_kind="determination",
                  deadline=deadline, filed=filed,
                  daysRemaining=days_between(today, deadline),
                  businessDaysRemaining=business_days_between(today, deadline, holidays),
                  note=f"{SEC_BUSINESS_DAYS} business days from the determination on {anchor}")


def dora_clocks(inc: dict, now_iso: str) -> list:
    """The three DORA windows, in clock hours.

    Each anchors on the previous step rather than on the incident: `intermediate` runs from the
    initial notification and `final` from the intermediate report, so a missed initial
    notification does not silently produce a phantom intermediate deadline. Where an anchor
    timestamp was never recorded the window reports `anchor-missing` — the engine will not read
    a bare date as midnight to manufacture hour precision.
    """
    regime = "dora"
    if regime not in (inc["disclosure"]["regimes"] or ()):
        return [_clock(regime, w, CLOCK_NA,
                       note="this incident is not tracked against DORA")
                for w in WINDOWS[regime]]
    filings = inc["disclosure"]["filings"] or {}
    anchors = inc.get("anchors") or {}
    rows = []

    def finish(window, anchor, anchor_kind, deadline, note):
        filed = filings.get(f"dora:{window}")
        state = (CLOCK_FILED if filed
                 else CLOCK_OVERDUE if hours_between(deadline, now_iso) > 0 else CLOCK_DUE)
        return _clock(regime, window, state, anchor=anchor, anchor_kind=anchor_kind,
                      deadline=deadline, filed=filed,
                      hoursRemaining=round(hours_between(now_iso, deadline), 2), note=note)

    # initial — the EARLIER of classification+4h and awareness+24h, so classifying late does
    # not extend the awareness cap.
    aware, classified = anchors.get("awareAt"), anchors.get("classifiedAt")
    bounds = []
    if classified:
        bounds.append((fmt_ts(parse_ts(classified)
                              + timedelta(hours=DORA_INITIAL_FROM_CLASSIFIED_H)),
                       classified, "classification",
                       f"{DORA_INITIAL_FROM_CLASSIFIED_H} hours from classification as major"))
    if aware:
        bounds.append((fmt_ts(parse_ts(aware) + timedelta(hours=DORA_INITIAL_FROM_AWARE_H)),
                       aware, "awareness",
                       f"{DORA_INITIAL_FROM_AWARE_H} hours from becoming aware"))
    if not bounds:
        rows.append(_clock(regime, "initial", CLOCK_ANCHOR_MISSING,
                           filed=filings.get("dora:initial"),
                           note="neither awareAt nor classifiedAt is recorded; set-anchor "
                                "them. DORA counts clock hours and this engine will not read "
                                "a date as midnight to invent a deadline."))
    else:
        deadline, anchor, kind, note = min(bounds, key=lambda b: parse_ts(b[0]))
        if len(bounds) == 1:
            note += " (the other anchor is not recorded, so this bound is used alone)"
        rows.append(finish("initial", anchor, kind, deadline, note))

    # intermediate — 72h from the initial notification actually filed.
    init_filed = filings.get("dora:initial")
    if not init_filed:
        rows.append(_clock(regime, "intermediate", CLOCK_NOT_STARTED,
                           note=f"{DORA_INTERMEDIATE_FROM_INITIAL_H} hours from the initial "
                                f"notification; none is recorded yet"))
    else:
        rows.append(finish(
            "intermediate", init_filed, "initial-notification",
            fmt_ts(parse_ts(init_filed)
                   + timedelta(hours=DORA_INTERMEDIATE_FROM_INITIAL_H)),
            f"{DORA_INTERMEDIATE_FROM_INITIAL_H} hours from the initial notification"))

    # final — one month from the intermediate report actually filed.
    inter_filed = filings.get("dora:intermediate")
    if not inter_filed:
        rows.append(_clock(regime, "final", CLOCK_NOT_STARTED,
                           note="one month from the intermediate report; none is recorded yet"))
    else:
        rows.append(finish(
            "final", inter_filed, "intermediate-report",
            fmt_ts(add_months(parse_ts(inter_filed), DORA_FINAL_FROM_INTERMEDIATE_MONTHS)),
            "one month from the intermediate report"))
    return rows


def incident_band(inc: dict, clocks: list) -> str:
    """One word for where this incident stands. A running clock outranks the determination.

    The ordering matters and it is not obvious. An incident can be determined **not material**
    for Item 1.05 and still owe a DORA report on a live clock — "not material" and "no
    notification duty" are different questions with different tests, and a band that read the
    determination first would hide the one of the two that has a deadline. So the clocks are
    checked first, and the determination state answers only when nothing is owed.

    `anchor-missing` deliberately does not drive the band: it is a gap in the record rather
    than a deadline, and it has its own attention list.
    """
    if inc.get("status") == "closed":
        return BAND_CLOSED
    if any(c["state"] == CLOCK_OVERDUE for c in clocks):
        return BAND_OVERDUE
    if any(c["state"] == CLOCK_DUE for c in clocks):
        return BAND_DUE
    det = current_determination(inc)
    if det is None:
        return BAND_NO_DETERMINATION
    if det["state"] == "assessing":
        return BAND_ASSESSING
    if det["state"] == "not-yet-determinable":
        return BAND_NOT_YET
    if det["state"] == "not-material":
        return BAND_NOT_MATERIAL
    applicable = [c for c in clocks if c["state"] != CLOCK_NA]
    if applicable and all(c["state"] == CLOCK_FILED for c in applicable):
        return BAND_FILED
    return BAND_MATERIAL


def derive(inc: dict, today: str, now_iso: str, holidays) -> dict:
    clocks = [sec_clock(inc, today, holidays)] + dora_clocks(inc, now_iso)
    latest = current_factors(inc)
    det = current_determination(inc)
    assessed = [k for k in FACTOR_KEYS if k in latest]
    return {
        "id": inc["id"],
        "title": inc["title"],
        "discoveredAt": inc["discoveredAt"],
        "scopeNote": inc.get("scopeNote", ""),
        "recordStatus": inc.get("status", "open"),
        "band": incident_band(inc, clocks),
        "regimes": list(inc["disclosure"]["regimes"] or []),
        "determination": det,
        "determinations": list(inc.get("determinations") or []),
        # Completeness, not a score: WHICH factors were assessed, never how many came back
        # `bearing`. A count of bearing factors is a score wearing different clothes, and the
        # moment it exists somebody treats 4-of-6 as a threshold.
        "factorsAssessed": assessed,
        "factorsUnassessed": [k for k in FACTOR_KEYS if k not in latest],
        "factorsLatest": {k: latest[k] for k in assessed},
        "factorHistory": list(inc.get("factors") or []),
        "relatedIncidentIds": list(
            (latest.get("aggregation") or {}).get("relatedIncidentIds") or []),
        "clocks": clocks,
        "disclosure": {"decision": inc["disclosure"]["decision"],
                       "basis": inc["disclosure"]["basis"],
                       "filings": dict(inc["disclosure"]["filings"] or {})},
        "anchors": dict(inc.get("anchors") or {}),
        "linkedRiskIds": list(inc.get("linkedRiskIds") or []),
        "linkedExceptionIds": list(inc.get("linkedExceptionIds") or []),
        # Elapsed time with nothing determined. Reported as a plain distance and never judged:
        # Item 1.05 requires the determination "without unreasonable delay" and sets no number
        # of days, so a tool that named one would be manufacturing a standard the rule declines
        # to set, then handing over a record of the day you crossed it.
        "daysSinceDiscovery": days_between(inc["discoveredAt"], today),
        "awaitingDetermination": det is None or det["state"] in ("assessing",
                                                                 "not-yet-determinable"),
        "notes": inc.get("notes", ""),
    }


def analyze(store: dict, today: str, now_iso: str) -> dict:
    holidays = holidays_of(store)
    rows = [derive(inc, today, now_iso, holidays) for inc in store["incidents"]]
    live = [r for r in rows if r["band"] != BAND_CLOSED]
    return {
        "meta": dict(store.get("meta") or {}),
        "today": today,
        "now": now_iso,
        "holidays": sorted(holidays),
        "incidents": rows,
        "attention": {
            "overdue": [r["id"] for r in live if r["band"] == BAND_OVERDUE],
            "due": [r["id"] for r in live if r["band"] == BAND_DUE],
            "noDetermination": [r["id"] for r in live
                                if r["band"] == BAND_NO_DETERMINATION],
            "awaitingDetermination": [r["id"] for r in live if r["awaitingDetermination"]],
            "anchorMissing": [r["id"] for r in live
                              if any(c["state"] == CLOCK_ANCHOR_MISSING
                                     for c in r["clocks"])],
            "incompleteFactors": [r["id"] for r in live if r["factorsUnassessed"]],
            # An incident linked to an accepted risk or a granted exception is the most useful
            # and the most dangerous connection in the toolkit. It is surfaced rather than
            # buried, with the discoverability caveat rendered wherever it appears.
            "realizedAcceptedRisk": [r["id"] for r in live if r["linkedExceptionIds"]],
        },
        "counts": {
            "incidents": len(rows),
            "open": len(live),
            "closed": len(rows) - len(live),
        },
    }


# --- Self-test ----------------------------------------------------------------
#
# Every expectation was worked by hand from disclosure-clocks.md before the code that satisfies
# it. The clock cases are the parity-critical ones: a weekend miscount is the only failure this
# engine can have that nobody notices until it matters.

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

    # --- business-day arithmetic, hand-worked -------------------------------------
    # The table in references/disclosure-clocks.md, pinned. 2026-07-06 is a Monday.
    eq(date.fromisoformat("2026-07-06").weekday(), 0, "2026-07-06 is a Monday")
    eq(business_days_after("2026-07-06", 4), "2026-07-10", "Monday + 4 business days is Friday")
    eq(business_days_after("2026-07-10", 4), "2026-07-16",
       "Friday + 4 business days skips the weekend and lands Thursday")
    eq(business_days_after("2026-07-11", 4), "2026-07-16",
       "a Saturday determination lands on the same day as the Friday one")
    eq(business_days_after("2026-07-12", 4), "2026-07-16",
       "and so does a Sunday one — the anchor day is never counted")
    eq(business_days_after("2026-07-14", 4, {"2026-07-17"}), "2026-07-21",
       "a holiday inside the window pushes the deadline out by one business day")
    eq(business_days_after("2026-07-14", 4), "2026-07-20",
       "the same determination with no holiday calendar lands one day earlier")
    eq(business_days_after("2026-12-31", 4, {"2027-01-01"}), "2027-01-07",
       "the count crosses a year boundary")
    eq(business_days_between("2026-07-06", "2026-07-10"), 4, "business days between, forward")
    eq(business_days_between("2026-07-13", "2026-07-10"), -1,
       "business days between, backward, is signed")
    eq(add_months(parse_ts("2026-01-31T09:00"), 1).isoformat()[:10], "2026-02-28",
       "one month from the 31st clamps to the end of a short month")

    # --- timestamps ----------------------------------------------------------------
    refuses(lambda: check_ts("2026-07-06", "--aware"),
            "a bare date is refused where a timestamp is required", "manufacture precision")
    eq(check_ts("2026-07-06T09:30", "--aware"), "2026-07-06T09:30", "a minute-precision stamp")
    eq(check_ts("2026-07-06T09:30:00Z", "--aware"), "2026-07-06T09:30:00Z", "Z is accepted")
    eq(round(hours_between("2026-07-06T09:00Z", "2026-07-07T09:00Z")), 24, "24 hours apart")

    work = _tf.mkdtemp()
    try:
        path = os.path.join(work, "t.inc")
        store = new_store("Acme", holidays=["2026-07-17"])
        save_store(path, store)
        store = load_store(path)

        i1 = open_incident(store, "Vendor payroll portal breach", "2026-07-06",
                           regimes=["sec-1.05"], actor="t")
        eq(i1["id"], "I-001", "incident ids are I-prefixed")
        eq(i1["status"], "open", "a new incident is open")
        eq(i1["disclosure"]["decision"], "pending", "disclosure starts pending")

        # --- the clock has NOT started -------------------------------------------
        out = analyze(store, "2026-07-13", "2026-07-13T00:00:00+00:00")
        row = out["incidents"][0]
        eq(row["band"], BAND_NO_DETERMINATION, "no determination yet")
        sec = [c for c in row["clocks"] if c["regime"] == "sec-1.05"][0]
        eq(sec["state"], CLOCK_NOT_STARTED, "the Item 1.05 clock has not started")
        eq(sec["deadline"], None, "and there is therefore no deadline")
        eq(row["daysSinceDiscovery"], 7, "elapsed days since discovery are reported plainly")
        eq(out["attention"]["noDetermination"], ["I-001"], "and it is an open item")
        eq(out["attention"]["incompleteFactors"], ["I-001"], "no factor assessed yet")
        eq(row["factorsUnassessed"], list(FACTOR_KEYS), "all six are outstanding")

        # --- factors are appended, with a rationale, and never scored --------------
        assess_factor(store, "I-001", "data", "unknown",
                      "Exfiltration not confirmed as of 9 July; forensics ongoing.", actor="t")
        assess_factor(store, "I-001", "data", "bearing",
                      "Forensics confirmed names and work email for ~1,900 employees; "
                      "no financial or health data.", actor="t")
        eq(len(store["incidents"][0]["factors"]), 2,
           "re-assessing appends; the earlier assessment stays in the record")
        eq(current_factors(store["incidents"][0])["data"]["assessment"], "bearing",
           "the current assessment is the most recent one")
        assess_factor(store, "I-001", "aggregation", "no-bearing",
                      "Considered against the March phishing cluster; different actor, "
                      "different vector, not a related series.", related=["I-999"], actor="t")
        eq(derive(store["incidents"][0], "2026-07-13", "2026-07-13T00:00:00+00:00",
                  set())["relatedIncidentIds"], ["I-999"],
           "the aggregation factor carries the incidents considered alongside")

        refuses(lambda: assess_factor(store, "I-001", "data", "bearing", ""),
                "a factor assessment with no rationale is refused", "ticked box")
        refuses(lambda: assess_factor(store, "I-001", "vibes", "bearing", "because"),
                "an unknown factor key is refused", "--factor")
        refuses(lambda: assess_factor(store, "I-001", "data", "high", "because"),
                "a made-up assessment value is refused", "--assessment")
        refuses(lambda: assess_factor(store, "I-002", "data", "bearing", "because"),
                "assessing an unknown incident is refused")

        # --- determinations are appended, never overwritten -----------------------
        save_store(path, store)
        before = open(path, "rb").read()
        refuses(lambda: determine(store, "I-001", "material", "", "GC", "2026-07-14"),
                "a determination with no rationale is refused", "the basis is the whole")
        refuses(lambda: determine(store, "I-001", "material", "because", "", "2026-07-14"),
                "a determination with no decider is refused", "name who made it")
        refuses(lambda: determine(store, "I-001", "material", "because", "GC", "2026-7-14"),
                "an unpadded determination date is refused", "canonical zero-padded")
        refuses(lambda: determine(store, "I-001", "material", "because", "GC", "2026-02-30"),
                "an impossible determination date is refused")
        refuses(lambda: determine(store, "I-001", "probably", "because", "GC", "2026-07-14"),
                "a made-up determination state is refused", "--state")
        refuses(lambda: close_incident(store, "I-001", ""),
                "closing without a reason is refused", "reconciled later")
        refuses(lambda: record_filing(store, "I-001", "dora:initial", "2026-07-14T09:00"),
                "recording a DORA filing on an incident not tracked against DORA is refused",
                "nothing owed")
        refuses(lambda: set_disclosure(store, "I-001", "file", ""),
                "a disclosure decision with no basis is refused", "will not have")
        ok(open(path, "rb").read() == before,
           "every refusal left the store byte-identical")

        determine(store, "I-001", "assessing",
                  "Scope not yet established; forensics engaged 8 July.", "CISO",
                  "2026-07-09", actor="t")
        out = analyze(store, "2026-07-13", "2026-07-13T00:00:00+00:00")
        row = out["incidents"][0]
        eq(row["band"], BAND_ASSESSING, "an incident under assessment reports assessing")
        eq([c for c in row["clocks"] if c["regime"] == "sec-1.05"][0]["state"],
           CLOCK_NOT_STARTED, "and the Item 1.05 clock still has not started")
        ok(row["awaitingDetermination"], "it is still awaiting a determination")

        determine(store, "I-001", "not-material",
                  "Contact data only; no financial impact; no operational disruption.",
                  "General Counsel", "2026-07-13", actor="t")
        eq(analyze(store, "2026-07-13", "2026-07-13T00:00:00+00:00")["incidents"][0]["band"],
           BAND_NOT_MATERIAL, "a not-material determination reports not-material")
        eq([c for c in analyze(store, "2026-07-13",
                               "2026-07-13T00:00:00+00:00")["incidents"][0]["clocks"]
            if c["regime"] == "sec-1.05"][0]["state"], CLOCK_NOT_STARTED,
           "and no Item 1.05 clock runs on a not-material determination")

        # The change that matters. It is appended; the earlier calls stay.
        determine(store, "I-001", "material",
                  "Forensics established exfiltration of employee records; "
                  "remediation cost and customer notification now expected to be significant.",
                  "General Counsel", "2026-07-14", actor="t")
        dets = store["incidents"][0]["determinations"]
        eq(len(dets), 3, "three determinations recorded, none overwritten")
        eq([d["state"] for d in dets], ["assessing", "not-material", "material"],
           "the whole sequence survives — this is the 'when did you know' record")
        eq(dets[0]["determinedAt"], "2026-07-09",
           "and the first determination still carries its own date")

        # --- the clock anchors on the determination, not the discovery -------------
        out = analyze(store, "2026-07-16", "2026-07-16T00:00:00+00:00")
        row = out["incidents"][0]
        sec = [c for c in row["clocks"] if c["regime"] == "sec-1.05"][0]
        eq(sec["anchorKind"], "determination", "the anchor is the determination")
        eq(sec["anchor"], "2026-07-14", "not the 2026-07-06 discovery date")
        # 2026-07-14 is a Tuesday and 2026-07-17 is a holiday in this store, so:
        # Wed 15 (1), Thu 16 (2), Fri 17 holiday, Mon 20 (3), Tue 21 (4).
        eq(sec["deadline"], "2026-07-21", "four business days, holiday included")
        eq(sec["state"], CLOCK_DUE, "and it is running")
        eq(sec["daysRemaining"], 5, "five calendar days remain")
        eq(sec["businessDaysRemaining"], 2, "but only two business days")
        eq(row["band"], BAND_DUE, "the incident band follows the clock")
        eq(out["attention"]["due"], ["I-001"], "and it lands on the due list")
        ok("determination" in sec["note"], "the note states what the clock is counting from")

        late = analyze(store, "2026-07-22", "2026-07-22T00:00:00+00:00")
        eq(late["incidents"][0]["band"], BAND_OVERDUE, "past the deadline, unfiled, is overdue")
        eq(late["attention"]["overdue"], ["I-001"], "and it lands on the overdue list")
        eq(late["incidents"][0]["clocks"][0]["daysRemaining"], -1, "days remaining goes signed")

        set_disclosure(store, "I-001", "file",
                       "Determined material 14 July; 8-K to be filed within the window.",
                       actor="t")
        record_filing(store, "I-001", "sec-1.05:8-K", "2026-07-20", actor="t")
        filed = analyze(store, "2026-07-22", "2026-07-22T00:00:00+00:00")
        eq(filed["incidents"][0]["clocks"][0]["state"], CLOCK_FILED, "a filing stops the clock")
        eq(filed["incidents"][0]["band"], BAND_FILED, "and the incident reports filed")
        eq(filed["attention"]["overdue"], [], "an overdue flag clears on filing, not before")
        refuses(lambda: record_filing(store, "I-001", "sec-1.05:8-K", "2026-7-20"),
                "an unpadded filing date is refused", "canonical zero-padded")
        refuses(lambda: record_filing(store, "I-001", "sec:8K", "2026-07-20"),
                "an unknown window is refused", "--window")

        # --- DORA: hours, and an honest gap where an anchor is missing --------------
        i2 = open_incident(store, "Core banking payment rail outage", "2026-07-06",
                           regimes=["dora"], actor="t")
        eq(i2["id"], "I-002", "ids increment")
        d = analyze(store, "2026-07-07", "2026-07-07T00:00:00+00:00")["incidents"][1]
        init = [c for c in d["clocks"] if c["window"] == "initial"][0]
        eq(init["state"], CLOCK_ANCHOR_MISSING, "no anchor means no deadline, and it shows")
        eq(init["deadline"], None, "the engine does not read a date as midnight")
        eq([c for c in d["clocks"] if c["regime"] == "sec-1.05"][0]["state"], CLOCK_NA,
           "and an incident outside a regime reports not-applicable, not not-started")
        eq(analyze(store, "2026-07-07",
                   "2026-07-07T00:00:00+00:00")["attention"]["anchorMissing"], ["I-002"],
           "a missing anchor is an open item")

        refuses(lambda: set_anchor(store, "I-002", aware="2026-07-06"),
                "a date-precision DORA anchor is refused", "clock hours")
        # Aware 06:00, classified 09:00. Awareness + 24h = 07-07T06:00; classification + 4h =
        # 07-06T13:00. The earlier of the two governs, so classifying does not buy time.
        set_anchor(store, "I-002", aware="2026-07-06T06:00:00+00:00",
                   classified="2026-07-06T09:00:00+00:00", actor="t")
        d = analyze(store, "2026-07-06", "2026-07-06T10:00:00+00:00")["incidents"][1]
        init = [c for c in d["clocks"] if c["window"] == "initial"][0]
        eq(init["deadline"], "2026-07-06T13:00:00+00:00",
           "the initial window is the EARLIER of classification+4h and awareness+24h")
        eq(init["anchorKind"], "classification", "and it says which anchor governed")
        eq(init["state"], CLOCK_DUE, "running at 10:00")
        eq(init["hoursRemaining"], 3.0, "three hours remain")
        d = analyze(store, "2026-07-06", "2026-07-06T14:00:00+00:00")["incidents"][1]
        eq([c for c in d["clocks"] if c["window"] == "initial"][0]["state"], CLOCK_OVERDUE,
           "and overdue an hour after")

        inter = [c for c in d["clocks"] if c["window"] == "intermediate"][0]
        eq(inter["state"], CLOCK_NOT_STARTED,
           "the intermediate window anchors on the initial notification, not the incident")
        eq(inter["deadline"], None, "so a missed initial produces no phantom deadline")

        record_filing(store, "I-002", "dora:initial", "2026-07-06T12:30:00+00:00", actor="t")
        d = analyze(store, "2026-07-07", "2026-07-07T00:00:00+00:00")["incidents"][1]
        inter = [c for c in d["clocks"] if c["window"] == "intermediate"][0]
        eq(inter["deadline"], "2026-07-09T12:30:00+00:00",
           "72 hours from the initial notification")
        eq(inter["anchorKind"], "initial-notification", "anchored on the filing")
        record_filing(store, "I-002", "dora:intermediate", "2026-07-09T10:00:00+00:00",
                      actor="t")
        fin = [c for c in analyze(store, "2026-07-10",
                                  "2026-07-10T00:00:00+00:00")["incidents"][1]["clocks"]
               if c["window"] == "final"][0]
        eq(fin["deadline"], "2026-08-09T10:00:00+00:00",
           "one month from the intermediate report")

        # --- a running clock outranks the determination ----------------------------
        # The conflation this guards against: "not material for Item 1.05" does not mean
        # "no notification duty". I-002 is now in both regimes, is NOT material for the
        # securities question, and still owes a DORA final report on a live clock. A band
        # that read the determination first would report `not-material` and hide the
        # deadline — which is the one of the two facts that has a date attached.
        set_disclosure(store, "I-002", "no-file",
                       "Reported to the NCA under DORA; not material for Item 1.05.",
                       regimes=["sec-1.05", "dora"], actor="t")
        determine(store, "I-002", "not-material",
                  "Latency only; no data affected, no revenue impact beyond the SLA credit.",
                  "General Counsel", "2026-07-09", actor="t")
        two = analyze(store, "2026-07-10", "2026-07-10T00:00:00+00:00")["incidents"][1]
        eq(two["determination"]["state"], "not-material", "the determination is not-material")
        eq(two["band"], BAND_DUE,
           "but the band reports the live DORA window, not the securities determination")
        eq([c["state"] for c in two["clocks"] if c["regime"] == "sec-1.05"],
           [CLOCK_NOT_STARTED], "with no Item 1.05 clock running at all")

        # --- the engine emits no verdict and no score -------------------------------
        text = json.dumps(analyze(store, "2026-07-22", "2026-07-22T00:00:00+00:00"))
        for word in ("score", "Score", "materialityScore", "recommend", "verdict"):
            ok(word not in text, f"no {word!r} anywhere in the analysis output")
        row = analyze(store, "2026-07-22", "2026-07-22T00:00:00+00:00")["incidents"][0]
        ok("factorsAssessed" in row and "factorsUnassessed" in row,
           "completeness is reported as which factors, not how many")
        ok(not any("bearing" in k.lower() for k in row),
           "and nothing in the derived row counts the bearing assessments")

        # --- links, closing, and the family guard -----------------------------------
        link_incident(store, "I-001", risk_ids=["R-006"], exception_ids=["A-001"], actor="t")
        out = analyze(store, "2026-07-22", "2026-07-22T00:00:00+00:00")
        eq(out["attention"]["realizedAcceptedRisk"], ["I-001"],
           "an incident that realizes an accepted risk is surfaced, not buried")
        close_incident(store, "I-002", "Service restored; reported and closed with the NCA.",
                       actor="t")
        eq(len(store["incidents"]), 2, "closing does not delete the record")
        out = analyze(store, "2026-07-22", "2026-07-22T00:00:00+00:00")
        eq(out["counts"], {"incidents": 2, "open": 1, "closed": 1}, "headline counts")
        eq(out["incidents"][1]["band"], BAND_CLOSED, "closed outranks every derivation")
        refuses(lambda: close_incident(store, "I-002", "again"),
                "closing an already-closed incident is refused")

        other = os.path.join(work, "other.exc")
        with open(other, "w", encoding="utf-8") as fh:
            json.dump({"schemaVersion": 1, "family": "exceptions-register"}, fh)
        refuses(lambda: load_store(other),
                "an exceptions register handed to this engine is refused by family",
                "not an incident store")

        save_store(path, store)
        eq(analyze(load_store(path), "2026-07-22", "2026-07-22T00:00:00+00:00"),
           analyze(store, "2026-07-22", "2026-07-22T00:00:00+00:00"),
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
    for h in args.holiday:
        check_date(h, "--holiday")
    store = new_store(args.client, args.owner, args.scope_note, args.holiday)
    append_history(store, "store-created", args.store, args.actor)
    save_store(args.store, store)
    print(f"Created {args.store}")
    if args.holiday:
        print(f"  {len(args.holiday)} holidays supplied for the business-day clock.")
    else:
        print("  No holiday calendar supplied. A federal holiday will be counted as a "
              "business day, so an Item 1.05 deadline lands one day early per holiday in "
              "the window — the safe direction, and still wrong. Supply --holiday dates.")
    print("  Next: open an incident. The Item 1.05 clock starts at a determination, "
          "not at discovery.")
    return 0


def _cmd_open(args):
    store = load_store(args.store)
    r = open_incident(store, args.title, args.discovered, args.scope_note, args.regime,
                      args.actor)
    save_store(args.store, store)
    print(f"{r['id']}: {r['title']}  (discovered {r['discoveredAt']}, "
          f"regimes: {', '.join(r['disclosure']['regimes']) or 'none set'})")
    return 0


def _cmd_assess(args):
    store = load_store(args.store)
    e = assess_factor(store, args.id, args.factor, args.assessment, args.rationale,
                      args.related, args.actor)
    save_store(args.store, store)
    print(f"{args.id} · {e['key']}: {e['assessment']}")
    return 0


def _cmd_determine(args):
    store = load_store(args.store)
    e = determine(store, args.id, args.state, args.rationale, args.decider, args.on,
                  args.actor)
    save_store(args.store, store)
    print(f"{args.id} determined {e['state']} on {e['determinedAt']} by {e['decider']}")
    if e["state"] == "material":
        holidays = holidays_of(store)
        print(f"  Item 1.05 clock starts here: {SEC_BUSINESS_DAYS} business days to "
              f"{business_days_after(e['determinedAt'], SEC_BUSINESS_DAYS, holidays)}"
              + ("" if holidays else " (no holiday calendar supplied)"))
    print("  This tool does not make the determination. Involve counsel.")
    return 0


def _cmd_set_anchor(args):
    store = load_store(args.store)
    a = set_anchor(store, args.id, args.aware, args.classified, args.actor)
    save_store(args.store, store)
    print(f"{args.id} anchors — aware: {a['awareAt'] or '—'} · "
          f"classified: {a['classifiedAt'] or '—'}")
    return 0


def _cmd_set_disclosure(args):
    store = load_store(args.store)
    d = set_disclosure(store, args.id, args.decision, args.basis, args.regime, args.actor)
    save_store(args.store, store)
    print(f"{args.id} disclosure: {d['decision']} "
          f"({', '.join(d['regimes']) or 'no regime set'})")
    return 0


def _cmd_record_filing(args):
    store = load_store(args.store)
    f = record_filing(store, args.id, args.window, args.at, args.actor)
    save_store(args.store, store)
    print(f"{args.id} filings: " + ", ".join(f"{k} @ {v}" for k, v in sorted(f.items())))
    return 0


def _cmd_link(args):
    store = load_store(args.store)
    r = link_incident(store, args.id, args.risk, args.exception, args.actor)
    save_store(args.store, store)
    print(f"{r['id']} → risks {r['linkedRiskIds'] or '—'} · "
          f"exceptions {r['linkedExceptionIds'] or '—'}")
    if r["linkedExceptionIds"]:
        print("  These records are discoverable. Keep them governance-level and factual, "
              "and involve counsel on anything touching disclosure.")
    return 0


def _cmd_close(args):
    store = load_store(args.store)
    close_incident(store, args.id, args.why, args.actor)
    save_store(args.store, store)
    print(f"{args.id} closed")
    return 0


def _when(args):
    today = check_date(args.today, "--today") if args.today else date.today().isoformat()
    if args.now:
        now_iso = check_ts(args.now, "--now")
    elif args.today:
        # --today pins the DORA comparison to the start of that day, so a pinned review is
        # reproducible. A DORA review that cares about hours should pass --now.
        now_iso = f"{today}T00:00:00+00:00"
    else:
        now_iso = now_ts()
    return today, now_iso


def _cmd_analyze(args):
    today, now_iso = _when(args)
    out = analyze(load_store(args.store), today, now_iso)
    text = json.dumps(out, indent=2, ensure_ascii=False)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
        print(f"wrote {args.out}")
    else:
        print(text)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="incident_analysis.py",
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
    sp.add_argument("--holiday", action="append", default=[],
                    help="a non-business day for the Item 1.05 clock; repeatable")
    sp.set_defaults(fn=_cmd_init)

    sp = sub.add_parser("open", help="open an incident record"); common(sp)
    sp.add_argument("--title", default="")
    sp.add_argument("--discovered", default="")
    sp.add_argument("--scope-note", default="")
    sp.add_argument("--regime", action="append", default=[], choices=list(REGIMES))
    sp.set_defaults(fn=_cmd_open)

    sp = sub.add_parser("assess-factor", help="record one factor assessment with its basis")
    common(sp)
    sp.add_argument("--id", required=True)
    sp.add_argument("--factor", default="", choices=list(FACTOR_KEYS))
    sp.add_argument("--assessment", default="", choices=list(ASSESSMENTS))
    sp.add_argument("--rationale", default="")
    sp.add_argument("--related", action="append", default=[])
    sp.set_defaults(fn=_cmd_assess)

    sp = sub.add_parser("determine", help="record a determination — the human's, not the tool's")
    common(sp)
    sp.add_argument("--id", required=True)
    sp.add_argument("--state", default="", choices=list(DETERMINATION_STATES))
    sp.add_argument("--rationale", default="")
    sp.add_argument("--decider", default="")
    sp.add_argument("--on", default="", help="the determination date — the Item 1.05 anchor")
    sp.set_defaults(fn=_cmd_determine)

    sp = sub.add_parser("set-anchor", help="record the DORA awareness/classification stamps")
    common(sp)
    sp.add_argument("--id", required=True)
    sp.add_argument("--aware", default="")
    sp.add_argument("--classified", default="")
    sp.set_defaults(fn=_cmd_set_anchor)

    sp = sub.add_parser("set-disclosure"); common(sp)
    sp.add_argument("--id", required=True)
    sp.add_argument("--decision", default="", choices=list(DISCLOSURE_DECISIONS))
    sp.add_argument("--basis", default="")
    sp.add_argument("--regime", action="append", default=[], choices=list(REGIMES))
    sp.set_defaults(fn=_cmd_set_disclosure)

    sp = sub.add_parser("record-filing"); common(sp)
    sp.add_argument("--id", required=True)
    sp.add_argument("--window", default="", help="e.g. sec-1.05:8-K, dora:initial")
    sp.add_argument("--at", default="")
    sp.set_defaults(fn=_cmd_record_filing)

    sp = sub.add_parser("link"); common(sp)
    sp.add_argument("--id", required=True)
    sp.add_argument("--risk", action="append", default=[])
    sp.add_argument("--exception", action="append", default=[])
    sp.set_defaults(fn=_cmd_link)

    sp = sub.add_parser("close"); common(sp)
    sp.add_argument("--id", required=True)
    sp.add_argument("--why", default="")
    sp.set_defaults(fn=_cmd_close)

    sp = sub.add_parser("analyze"); common(sp)
    sp.add_argument("--today", default=None)
    sp.add_argument("--now", default=None,
                    help="ISO-8601 instant for the DORA hour comparisons")
    sp.add_argument("--out", default=None)
    sp.set_defaults(fn=_cmd_analyze)

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
