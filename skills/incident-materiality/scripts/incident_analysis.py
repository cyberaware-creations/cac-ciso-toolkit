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
# Decision AP-2's third row, and it exists because the other five could not say this.
#
# `not-applicable` means nobody tracked the regime. `not-started` means the anchor event has
# not happened yet. Neither of them means WE DO NOT KNOW WHETHER THIS REGIME REACHES YOU —
# and with no word for that, an undeclared perimeter had to borrow one of the others. What it
# borrowed was silence: the clock simply computed, and a four-business-day Form 8-K deadline
# was produced for organisations that owe no such filing (BL-175).
#
# The rule, from AP-2: ask the battery, withhold the date, name the flag that would settle
# it. This state is the withholding, and it is visible rather than absent — a missing row and
# a row saying "nobody has told us" are different facts, and only one of them is actionable.
CLOCK_SCOPE_UNDECLARED = "scope-not-declared"
CLOCK_DUE = "due"
CLOCK_OVERDUE = "overdue"
CLOCK_FILED = "filed"
CLOCK_STATES = (CLOCK_NA, CLOCK_NOT_STARTED, CLOCK_ANCHOR_MISSING, CLOCK_SCOPE_UNDECLARED,
                CLOCK_DUE, CLOCK_OVERDUE, CLOCK_FILED)

# --- Escalation policy (CAC-EL-1 §1.3) ----------------------------------------
#
# What escalates here is narrower than anywhere else in the suite, and the narrowness is the
# design. This engine emits no verdict, so an escalation may only ever report one of four
# facts about the store: a DEADLINE THAT PASSED, an ANCHOR THAT IS ABSENT, a PERIMETER NOBODY
# DECLARED, or a RECORD THAT MOVED. None of the four says an incident is material, and none
# says a determination was wrong.
#
# `scopeUndeclared` is the newest, and it is what pays for AP-2. Withholding a deadline
# because nobody declared the perimeter is the honest answer, and on its own it would trade a
# manufactured date for a silent one: a genuine registrant who never filled in the profile
# would see an empty deadline column with nothing to say it was empty for a fixable reason.
# So the withheld window escalates on the MISSING DECLARATION rather than on a deadline the
# engine refuses to compute. That is a fact about the record, not a judgment about the regime
# — the same line `anchorMissing` already draws.
#
# Deliberately NOT escalated, each for a reason worth keeping:
#
#   * Elapsed days with no determination. Item 1.05 requires the determination "without
#     unreasonable delay" and names no number of days. `derive` reports the elapsed distance
#     and declines to judge it; an escalation would BE that judgment — manufacturing the
#     standard the rule declines to set, then producing a dated, discoverable record of the
#     day this organisation supposedly crossed it.
#   * A window that is DUE. Inside the window is on schedule. Due is the attention list and
#     overdue is the escalation — the same line exceptions-register draws between
#     `revalidation-due` and `revalidation-overdue`.
#   * Unassessed factors. Already reported as completeness. A gap in the worksheet is not a
#     clock that ran out.
#   * Anything counting `bearing` factors. That is a score wearing different clothes, and the
#     moment one exists somebody reads 4-of-6 as a threshold.
#
# Note what is missing from the defaults: a number. Every other register in the suite tunes an
# escalation with a count or a window. The only quantities this one could tune are the ones
# the SEC and DORA already set, and they are not this file's to move.
ESCALATION_DEFAULTS = {
    "windowOverdue": True,
    "anchorMissing": True,
    "scopeUndeclared": True,
    "supersededDetermination": True,
}
ESCALATION_SEVERITY_ORDER = ["critical", "high", "medium"]

# The two states in which the organisation has settled on an answer. `assessing` and
# `not-yet-determinable` say in as many words that the work is still running, so facts landing
# after them are the process working rather than a record moving underneath a conclusion.
SETTLED_DETERMINATIONS = ("material", "not-material")

# --- The applicability profile (CAC-AP-1), read as data -----------------------
#
# `--context <file.biz payload>` is OPTIONAL and absent is the normal case. Everything this
# block adds is additive and appears nowhere unless a payload was supplied, so a run without
# one produces the same bytes it produced before any of this existed. That is asserted in
# evals/applicability.sh rather than intended here.
#
# The profile NARROWS the question set and never answers a question. Two batteries are
# genuinely conditional in this skill and both are gated on something a lawyer declares, not
# on anything this engine could infer:
#
#   sec-item-105  — Item 1.05 applies to a registrant. A private company has no 8-K.
#   dora-windows  — the three report windows apply to a DORA-scoped entity.
#
# That comment was right about `sec-item-105` and the mapping under it selected on the wrong
# flag for twelve releases: `listedEntity`, a listing fact, standing in for an Exchange Act
# reporting obligation. Nothing here looked like an inference, which is why every review
# passed — the inference was in the mapping, not in the arithmetic. `secItem105Scope` is the
# declared fact now, and `flags-declared.sh` fails if this table selects on a flag whose own
# definition does not name the regime it gates (BL-175).
#
# THE THIRD STATE. A battery can now arrive asked-but-undeclared: §2.2 says absence asks, and
# AP-2 adds that absence must not compute. `narrow_clocks` withholds the deadline and leaves a
# `scope-not-declared` row in its place, and `scopeUndeclared` escalates it where the incident
# is tracked against the regime anyway — so nothing is invented and nothing is lost.
#
# What the payload carries is the DECIDED narrowing, not the raw flags: `business-context`
# owns §2.2 (absent and null both mean *not declared*, so both ask) and ships its answer.
# This file deliberately does not re-implement that clause — `if not declared:` reads
# correctly, passes every test anyone writes, and silently narrows every assessment in the
# suite. One copy of it, in the skill that owns it.
#
# §2.3 IS implemented here, because its data is here: the subject declaration lives on the
# incident record and the organisation profile has never seen it.
CONTEXT_CONTRACT = "CAC-AP-1"
CONTEXT_SKILL = "incident"
CONTEXT_BATTERIES = {
    "sec-item-105": {"flag": "secItem105Scope", "regime": "sec-1.05",
                     "label": "SEC Item 1.05 disclosure window"},
    "dora-windows": {"flag": "doraScope", "regime": "dora",
                     "label": "DORA reporting windows"},
}


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
    """Write the store atomically: a crash mid-write leaves the previous file intact.

    One of ten copies of this pattern, registered as a twin under CAC-TW-1 and compared by
    executing them — `skills/ai-register/scripts/ai_register.py` holds the family list. The
    property compared is the interrupted write, because on the happy path an atomic writer and
    `open(path, "w")` produce identical bytes, which is how two copies stayed non-atomic
    through nine releases with every self-test green (BL-219).
    """
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


# --- CAC-AP-1 consumer surface ------------------------------------------------

def load_context(path: str) -> dict:
    """Read an applicability payload. As data — this skill imports no other skill.

    Both refusals below are deliberate. `--context` was passed on purpose, so a payload that
    cannot be honoured must say so rather than quietly leave the assessment un-narrowed: the
    user would read a full question set as a profile that decided nothing applied.
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


def subject_value(field):
    """A wrapped subject declaration or a bare scalar. Bare is legal on read."""
    return field.get("value") if isinstance(field, dict) else field


def _subject_record(battery: str, spec: dict, field, value: bool, kind: str) -> dict:
    """A skip or an override attributed to the incident's own declaration.

    Built here rather than reused from the payload because the payload cannot contain it: the
    subject declaration exists only on this record. It is also RICHER than the org-level form
    — a subject declaration made through `declare-context` carries its own declarer, date and
    basis, so the sentence can say who decided that this incident sits inside a different
    perimeter from the organisation around it.
    """
    by = str((field or {}).get("declaredBy") or "") if isinstance(field, dict) else ""
    on = str((field or {}).get("declaredOn") or "") if isinstance(field, dict) else ""
    basis = str((field or {}).get("basis") or "").strip() if isinstance(field, dict) else ""
    attribution = (f"declared {on} by {by}" if on and by
                   else f"declared by {by}" if by else "an unattributed declaration")
    lead = ("not assessed" if kind == "skip" else "assessed despite the organisation profile")
    tail = (basis if basis.endswith((".", "!", "?")) else basis + ".") if basis else ""
    sentence = (f"{spec['label']} — {lead}. This incident declares "
                f"`{spec['flag']}: {str(bool(value)).lower()}`, {attribution}"
                + (f" — {tail}" if tail else "."))
    return {"battery": battery, "label": spec["label"], "flag": spec["flag"],
            "source": "subject", "subjectValue": bool(value), "declaredBy": by,
            "declaredOn": on, "basis": basis, "sentence": sentence}


def applicability_for(payload: dict, inc: dict) -> dict:
    """§2.3 applied on top of the profile-layer decision the payload already made.

    The profile's answer arrives decided. What happens here is only the subject layer, and
    only the part of it that cannot be decided anywhere else: `None` does not override, a
    declaration in either direction does, and both are recorded.
    """
    base = (payload.get("applicability") or {}).get(CONTEXT_SKILL) or {}
    profile_ask = set(base.get("ask") or ())
    profile_skipped = {r.get("battery"): r for r in (base.get("skipped") or ())}
    # §2.4.1. Read with `.get`: a payload written by an older `business-context` has no
    # such key — and the honest reading of its absence is that the profile layer never said
    # which asks rested on a declaration. `.get(..., [])` treats that as "none undeclared",
    # which computes clocks exactly as that older payload always did rather than withholding
    # every deadline in the store on an upgrade.
    profile_undeclared = {r.get("battery"): r for r in (base.get("undeclared") or ())}
    declares = inc.get("contextDeclares") or {}
    tracked = list((inc.get("disclosure") or {}).get("regimes") or ())

    asked, skipped, overrides, undeclared = [], [], [], []
    for battery in sorted(CONTEXT_BATTERIES):
        spec = CONTEXT_BATTERIES[battery]
        if battery not in profile_ask and battery not in profile_skipped:
            continue                 # the profile's question set does not carry this battery
        field = declares.get(spec["flag"])
        declared = subject_value(field)
        # §2.3, and `is None` rather than truthiness: a subject that recorded "we do not know"
        # has said something worth keeping and has still not overridden anything.
        if spec["flag"] in declares and declared is not None:
            if declared:
                asked.append(battery)
                # Recorded as an override only where it CHANGED the answer. The removing
                # direction is already fully carried by its skip record, whose `source` is
                # `subject`; listing it twice would read as two separate findings.
                if battery in profile_skipped:
                    overrides.append(_subject_record(battery, spec, field, True, "override"))
                # A subject declaration SETTLES the gate, including one the profile left
                # silent — so this battery does not reach `undeclared` and its clock runs.
                # That is the recorded route out of a withheld deadline: declare the scope on
                # the incident, with a declarer and a date, and the window computes.
            else:
                skipped.append(_subject_record(battery, spec, field, False, "skip"))
        elif battery in profile_skipped:
            skipped.append(dict(profile_skipped[battery]))
        else:
            asked.append(battery)
            if battery in profile_undeclared:
                undeclared.append(dict(profile_undeclared[battery]))

    # A battery the profile narrowed away, on an incident that is tracked against that regime
    # anyway. Reported, never resolved: §2.3 says the profile keeps the default question set
    # proportionate and does not overrule the assessor standing in front of the evidence, so
    # the window is still computed and the disagreement is put where a human will see it.
    conflicts = []
    for rec in skipped:
        spec = CONTEXT_BATTERIES[rec["battery"]]
        if spec["regime"] not in tracked:
            continue
        conflicts.append({
            "battery": rec["battery"], "flag": spec["flag"], "regime": spec["regime"],
            "source": rec.get("source", ""),
            "sentence": (f"{spec['label']} — this incident is tracked against "
                         f"{spec['regime']} while the applicable declaration says it does "
                         f"not apply. The window is still computed: a profile narrows the "
                         f"default question set and does not overrule an assessor who "
                         f"opened the clock. Resolve the disagreement in one place or the "
                         f"other. Declaration: {rec.get('sentence', '')}"),
        })

    return {
        "profileVersion": str(payload.get("profileVersion") or ""),
        "asked": sorted(asked),
        "skipped": sorted(skipped, key=lambda r: r["battery"]),
        # A SUBSET of `asked`, never a fourth bucket beside it. Every battery here was asked
        # in full; what the list adds is that nobody had declared the gate when it was.
        "undeclared": sorted(undeclared, key=lambda r: r["battery"]),
        "overrides": sorted(overrides, key=lambda r: r["battery"]),
        "conflicts": sorted(conflicts, key=lambda r: r["battery"]),
        # The raw subject declarations, including any recorded `null`. A null that vanished
        # from the record would be indistinguishable from never having asked the question,
        # which is the same failure §2.4 exists to prevent one level up.
        "subjectDeclared": json.loads(json.dumps(declares)),
    }


def narrow_clocks(clocks: list, view: dict, inc: dict) -> list:
    """Drop the windows of a battery that was not asked, and withhold the ones nobody scoped.

    Two different things happen here and they must not look alike on the page.

    SKIPPED — somebody declared the regime out. Its windows are not computed at all; that is
    what narrowing a question set means. The rows do not become `not-applicable`, they are
    absent, and the skip record carries the sentence that explains where they went.

    UNDECLARED — nobody has said either way. The window is NOT computed and it is also not
    absent: it renders as `scope-not-declared`, naming the flag that would settle it. This is
    decision AP-2, and both halves of it matter. Computing would manufacture a legal date for
    an organisation that may owe no filing — the London-listed non-registrant every release
    test since v0.48.0 has reproduced. Dropping the row would leave a firm that simply has
    not filled in its profile looking identically clean to one that is genuinely out of
    scope, which is the §15(d) suppression from the other direction.

    The one exception belongs to SKIPPED only: an incident explicitly tracked against the
    regime keeps its clock, and the disagreement is reported as a conflict. That exception is
    why narrowing can never suppress an escalation — a regime nobody tracked produced a
    `not-applicable` row, and `not-applicable` escalates nothing.

    It is deliberately NOT extended to UNDECLARED, and the difference is the point. A skip is
    an answer, so an assessor who tracked the regime anyway is contradicting an answer and the
    engine reports the contradiction rather than picking a side. A silence is not an answer,
    so there is nothing to contradict and nothing to compute a date from. What the tracking
    does earn is attention: `scopeUndeclared` escalates precisely this case, so the window
    goes withheld without going quiet.
    """
    tracked = list((inc.get("disclosure") or {}).get("regimes") or ())
    dropped = {CONTEXT_BATTERIES[r["battery"]]["regime"] for r in view["skipped"]
               if CONTEXT_BATTERIES[r["battery"]]["regime"] not in tracked}
    unscoped = {CONTEXT_BATTERIES[r["battery"]]["regime"]: r
                for r in view.get("undeclared") or ()}
    out = []
    for c in clocks:
        if c["regime"] in dropped:
            continue
        rec = unscoped.get(c["regime"])
        # An untracked regime already reports `not-applicable` with no date on it. There is
        # nothing to withhold, and replacing that row would trade a true statement for a
        # vaguer one.
        if rec is None or c["state"] == CLOCK_NA:
            out.append(c)
            continue
        out.append(_clock(
            c["regime"], c["window"], CLOCK_SCOPE_UNDECLARED,
            note=("no window is computed: `%s` is not declared, so whether this regime "
                  "reaches this organisation has not been established. Declare it on the "
                  "organisation profile, or on this incident with `declare-context`, and "
                  "the window computes from the same anchor it always would. This is not a "
                  "finding that the regime does not apply — %s"
                  % (rec["flag"], rec["sentence"])),
            filed=(inc.get("disclosure") or {}).get("filings", {}).get(
                "%s:%s" % (c["regime"], c["window"])),
            scopeFlag=rec["flag"]))
    return out


def unimplemented_batteries(payload: dict) -> list:
    """Batteries the profile answered that this skill has no question for.

    Named rather than dropped. A reader comparing the profile against this analysis would
    otherwise find a declared answer with nothing on the page it could have affected, and
    have no way to tell a battery that belongs to another skill from one this skill forgot.
    """
    base = (payload.get("applicability") or {}).get(CONTEXT_SKILL) or {}
    seen = list(base.get("ask") or ()) + [r.get("battery") for r in (base.get("skipped") or ())]
    return sorted({b for b in seen if b not in CONTEXT_BATTERIES})


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


def parse_subject_flag(raw: str):
    """`true`/`false`/`null` for a subject declaration. Never a bare truthiness test."""
    text = str(raw if raw is not None else "").strip().lower()
    if text in ("true", "yes", "1"):
        return True
    if text in ("false", "no", "0"):
        return False
    if text in ("null", "none", "unknown"):
        return None
    raise Refusal(f"--value must be true, false or null; got {raw!r}. "
                  f"`null` is not `false`: it records that the question was asked of this "
                  f"incident and nobody could answer it, which does not override the "
                  f"organisation profile.")


def declare_context(store: dict, iid: str, flag: str, value, by: str, basis: str,
                    on: str = "", actor: str = "") -> dict:
    """Declare, at this incident, something the organisation profile decides org-wide.

    This is the §2.3 subject declaration. It is refused without a declarer and a basis for
    the same reason `business-context` refuses a flag without one: a declaration that
    narrows what gets asked and cannot say why is worse than no declaration at all, because
    absence asks everything and only a declaration can ask less.

    The record is never initialised empty on `open`. An incident that has declared nothing
    carries no `contextDeclares` key, so a store written before this existed is not a store
    with an empty answer in it.
    """
    inc = find_incident(store, iid)
    _required_text(flag, "--flag", "name the profile flag this incident declares differently")
    _required_text(by, "--by",
                   "a subject declaration nobody made cannot be weighed against the "
                   "organisation profile it overrides")
    _required_text(basis, "--basis",
                   "this narrows or widens what gets asked of a disclosure decision; a "
                   "declaration that cannot say why is worse than an absent one, because "
                   "absence asks everything")
    if on:
        check_date(on, "--on")
    known = {spec["flag"] for spec in CONTEXT_BATTERIES.values()}
    if flag not in known:
        # Accepted with a warning, matching how `business-context` treats an unknown flag:
        # the regulatory perimeter will outgrow this enumeration, and a record that refuses
        # tomorrow's regime is worse than one that keeps it unrecognised.
        print(f"warning: {flag!r} gates no battery in this skill (known: "
              f"{', '.join(sorted(known))}); recorded, but it narrows nothing here",
              file=sys.stderr)
    field = {"value": value, "declaredBy": by.strip(), "declaredOn": on,
             "basis": basis.strip()}
    inc.setdefault("contextDeclares", {})[flag] = field
    append_history(store, "context-declared", iid, actor,
                   detail={"flag": flag, "value": value, "declaredBy": field["declaredBy"]})
    return field


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
              on: str, actor: str = "", context: dict = None) -> dict:
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
    # CAC-AP-1 §2.5 — the profile in force when this was decided, frozen into the record.
    #
    # A determination made in Q1 was made against Q1's perimeter, and the questions it did
    # not ask are part of what it means. Without this, a reader a year later finds a
    # determination that never considered Item 1.05 and no way to tell whether that was
    # because the organisation was private at the time or because somebody forgot. The
    # `--context` version and the skips are frozen; the flags themselves are not, because
    # the payload names a `profileVersion` a reader can go and read in full.
    if context:
        view = applicability_for(context, inc)
        entry["contextFrozen"] = {
            "contractVersion": CONTEXT_CONTRACT,
            "profileVersion": str(context.get("profileVersion") or ""),
            "profileReviewedOn": str(context.get("profileReviewedOn") or ""),
            "asked": list(view["asked"]),
            "skipped": json.loads(json.dumps(view["skipped"])),
        }
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

    # initial — Article 5(1)(a) and Article 5(2) of Commission Delegated Regulation (EU)
    # 2025/301.
    #
    # 5(1)(a) sets two bounds: four hours from classification as major, AND no later than 24
    # hours from awareness. Both bind, so the EARLIER governs — classifying promptly cannot be
    # used to run past the awareness cap.
    #
    # 5(2) is the carve-out this engine had wrong until v0.49.0. Where the entity has NOT
    # classified the incident as major within 24 hours of awareness and classifies it later,
    # the notification is due "within four hours from the classification". The awareness cap
    # has already lapsed; it does not make the report retrospectively overdue. Taking min()
    # unconditionally produced a deadline in the past and reported OVERDUE on an incident that
    # was inside its window — a FALSE OVERDUE, the one direction this file argues a clock must
    # never fail in, because it pushes somebody into filing before they are ready.
    aware, classified = anchors.get("awareAt"), anchors.get("classifiedAt")
    late_classification = bool(
        aware and classified
        and parse_ts(classified) > parse_ts(aware) + timedelta(hours=DORA_INITIAL_FROM_AWARE_H))
    bounds = []
    if classified:
        bounds.append((fmt_ts(parse_ts(classified)
                              + timedelta(hours=DORA_INITIAL_FROM_CLASSIFIED_H)),
                       classified, "classification",
                       f"{DORA_INITIAL_FROM_CLASSIFIED_H} hours from classification as major"
                       + (f"; classification came more than {DORA_INITIAL_FROM_AWARE_H}h after "
                          "awareness, so Art. 5(2) of RTS 2025/301 governs and the awareness "
                          "cap no longer binds" if late_classification else "")))
    if aware and not late_classification:
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


def derive(inc: dict, today: str, now_iso: str, holidays, context: dict = None) -> dict:
    clocks = [sec_clock(inc, today, holidays)] + dora_clocks(inc, now_iso)
    view = applicability_for(context, inc) if context else None
    if view:
        clocks = narrow_clocks(clocks, view, inc)
    latest = current_factors(inc)
    det = current_determination(inc)
    assessed = [k for k in FACTOR_KEYS if k in latest]
    # The context block is added at the END of this dict, and only when a payload was
    # supplied. Both matter: a key that appears empty on an un-narrowed run would change
    # every output this skill has ever produced, and appending rather than inserting keeps
    # the un-narrowed prefix of the JSON identical rather than merely equivalent.
    extra = {"context": view} if view else {}
    return dict({
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
    }, **extra)


def _escalation_policy(store: dict) -> dict:
    policy = dict(ESCALATION_DEFAULTS)
    policy.update((store.get("settings") or {}).get("escalation") or {})
    return policy


def _factors_as_of(inc: dict, at: datetime) -> dict:
    """Latest assessment per factor key as the record stood at `at`.

    Compared on the recording timestamp `ts`, never on any date a human supplied. `determinedAt`
    is deliberately back-datable — it is the Item 1.05 anchor and often records a decision made
    before it was typed in — so measuring "what did the record say when this was written" against
    it would compare two different clocks. Both `ts` values come from `now_ts()`.
    """
    out = {}
    for f in inc.get("factors") or []:
        if f.get("ts") and parse_ts(f["ts"]) <= at:
            out[f["key"]] = f
    return out


def escalations(store: dict, today: str, now_iso: str, context: dict = None) -> list:
    """Every escalation this workspace warrants, in the CAC-EL-1 §1.3 shape.

    `subjectKind` is always `incident` — unlike exceptions-register, which distinguishes an
    accepted risk from a control exception, there is one kind of object here.

    Derived on every run, never stored, never a history event, and nothing below blocks: an
    overdue window still renders, still exports, still counts. The clocks are read from
    `derive`, not recomputed, so an escalation can never disagree with the worksheet beside it
    about whether a deadline passed.
    """
    policy = _escalation_policy(store)
    holidays = holidays_of(store)
    out = []
    for inc in store["incidents"]:
        if inc.get("status") == "closed":
            continue
        # The same narrowed clocks the worksheet shows, for the reason in the docstring: an
        # escalation must never disagree with the page beside it about whether a deadline
        # exists. Narrowing cannot in fact move an escalation — see `narrow_clocks` — and
        # evals/applicability.sh asserts that rather than leaving it as a claim.
        row = derive(inc, today, now_iso, holidays, context)
        iid = inc["id"]

        if policy.get("windowOverdue"):
            for c in row["clocks"]:
                if c["state"] != CLOCK_OVERDUE:
                    continue
                key = "{}:{}".format(c["regime"], c["window"])
                out.append({
                    "subjectRef": iid, "subjectKind": "incident",
                    "trigger": "window-overdue", "severity": "critical",
                    "since": c["deadline"],
                    "evidence": {
                        "from": c["anchor"] or "",
                        # The "now" this window is measured against, at the window's own
                        # precision. WINDOW_PRECISION is the table the clocks themselves use;
                        # reading it here rather than restating it keeps one answer to which
                        # regime counts days and which counts hours.
                        "to": today if WINDOW_PRECISION.get(key) == "date" else now_iso,
                        "baseline": key,
                        "detail": ("the {} window closed {} and no filing is recorded against "
                                   "it — {}".format(key, c["deadline"], c["note"])),
                    },
                })

        if policy.get("anchorMissing"):
            absent = [c for c in row["clocks"] if c["state"] == CLOCK_ANCHOR_MISSING]
            if absent:
                out.append({
                    "subjectRef": iid, "subjectKind": "incident",
                    "trigger": "anchor-missing", "severity": "high",
                    # The gap has held since the incident was opened; `discoveredAt` is the
                    # earliest recorded date it can honestly be dated from.
                    "since": inc["discoveredAt"],
                    "evidence": {
                        "from": inc["discoveredAt"], "to": today,
                        "baseline": ", ".join("{}:{}".format(c["regime"], c["window"])
                                              for c in absent),
                        "detail": ("tracked against a regime that counts clock hours with no "
                                   "anchor timestamp recorded, so no deadline can be computed "
                                   "— set-anchor the awareness or classification time. This "
                                   "escalates on sight and deliberately: the initial "
                                   "notification runs at most 24 hours from awareness, and "
                                   "there is no interval in which an unrecorded anchor is "
                                   "comfortable."),
                    },
                })

        # AP-2's withheld window, made visible. This fires ONLY where the incident is tracked
        # against the regime — a withheld window on a regime nobody opened is an unanswered
        # profile question, which is `business-context`'s `profile-stale` territory and not an
        # exposure on this incident. Tracked and unscoped is different: somebody has decided
        # this incident sits inside that regime and there is a deadline nobody can compute.
        #
        # `high`, not `critical`. A missed deadline has already happened; this one is a gap
        # that can be closed by declaring a fact, and ranking it alongside `window-overdue`
        # would put a form-filling task at the top of the same list as a lapsed filing.
        if policy.get("scopeUndeclared"):
            unscoped = [c for c in row["clocks"] if c["state"] == CLOCK_SCOPE_UNDECLARED]
            if unscoped:
                flags = sorted({c.get("scopeFlag", "") for c in unscoped if c.get("scopeFlag")})
                out.append({
                    "subjectRef": iid, "subjectKind": "incident",
                    "trigger": "scope-undeclared", "severity": "high",
                    "since": inc["discoveredAt"],
                    "evidence": {
                        "from": inc["discoveredAt"], "to": today,
                        "baseline": ", ".join("{}:{}".format(c["regime"], c["window"])
                                              for c in unscoped),
                        "detail": ("this incident is tracked against a regime whose "
                                   "applicability nobody has declared ({}), so no deadline "
                                   "is computed and none is invented. Declare it on the "
                                   "organisation profile or on this incident and the window "
                                   "computes. Until then this is an open question, not a "
                                   "finding that the regime does not "
                                   "apply.".format(", ".join(flags) or "no flag named")),
                    },
                })

        # The §1.2 lapse, in the only form this skill can honestly detect: a determination the
        # organisation settled on, and factors that moved on the record after it was written.
        #
        # Severity does NOT vary with which way a factor moved, and that is the whole care of
        # this trigger. Ranking "a factor turned `bearing` after a `not-material` determination"
        # above the other direction would be the engine grading a legal judgment, and a graded
        # judgment is discoverable as an exhibit arguing against the organisation's own
        # conclusion — the exact failure the no-verdict rule exists to prevent. So: one
        # severity, the assessor's own recorded words quoted back, and a detail line that says
        # in as many words what this does and does not claim.
        if policy.get("supersededDetermination"):
            det = current_determination(inc)
            if det and det["state"] in SETTLED_DETERMINATIONS and det.get("ts"):
                at = parse_ts(det["ts"])
                before, now_f = _factors_as_of(inc, at), current_factors(inc)
                moved = []
                for key in FACTOR_KEYS:
                    cur, was = now_f.get(key), before.get(key)
                    if cur is None or not cur.get("ts") or parse_ts(cur["ts"]) <= at:
                        continue
                    # Compared latest-against-as-of, never entry-by-entry. A factor assessed
                    # `bearing` → `unknown` → `bearing` after the determination has, on the
                    # record, not moved — and reporting it twice would make one unchanged
                    # factor look like two new facts.
                    if was is not None and was["assessment"] == cur["assessment"]:
                        continue
                    moved.append((key, was, cur))
                if moved:
                    named = ", ".join(
                        "{} ({} → {})".format(
                            key, was["assessment"] if was else "unassessed", cur["assessment"])
                        for key, was, cur in moved)
                    out.append({
                        "subjectRef": iid, "subjectKind": "incident",
                        "trigger": "determination-superseded", "severity": "high",
                        "since": min(cur["ts"] for _, _, cur in moved),
                        "evidence": {
                            "from": det["determinedAt"], "to": today,
                            "baseline": det["state"],
                            "detail": (
                                "the determination of {!r} recorded on {} by {} has not been "
                                "revisited, and the record has since moved on {}. This reports "
                                "that the facts changed after the determination was written, "
                                "not that the determination was wrong — the judgment is the "
                                "decider's to make again, or to let stand.".format(
                                    det["state"], det["determinedAt"], det["decider"], named)),
                        },
                    })

    # Worst first, then by incident, then by trigger. The third key currently decides
    # nothing: the blocks above emit in the order `window-overdue`, `anchor-missing`,
    # `determination-superseded`, which for a same-severity tie is already alphabetical, and
    # a stable sort would preserve it anyway. It is here so that reordering those blocks
    # cannot silently reorder a board pack — deliberately unreachable, and no self-test below
    # pretends to prove otherwise, because none can.
    out.sort(key=lambda e: (ESCALATION_SEVERITY_ORDER.index(e["severity"]),
                            e["subjectRef"], e["trigger"]))
    return out


def analyze(store: dict, today: str, now_iso: str, context: dict = None) -> dict:
    holidays = holidays_of(store)
    rows = [derive(inc, today, now_iso, holidays, context) for inc in store["incidents"]]
    live = [r for r in rows if r["band"] != BAND_CLOSED]
    # As on the rows: present only when a payload was supplied, appended last. `attention`
    # deliberately gains no key — its shape is read by two renderers and a board pack, and a
    # list that exists only sometimes is worse than one that lives where it belongs.
    extra = {}
    if context:
        extra["context"] = {
            "contractVersion": CONTEXT_CONTRACT,
            "orgName": str(context.get("orgName") or ""),
            "profileVersion": str(context.get("profileVersion") or ""),
            "profileReviewedOn": str(context.get("profileReviewedOn") or ""),
            # Exact, and never a denominator. The consumer of this figure is a human weighing
            # a financial impact against the size of the business; nothing in this file
            # divides by it, and evals/no-derived-materiality.sh walks the AST to prove it.
            "revenueBase": json.loads(json.dumps(context.get("revenue"))) if
            context.get("revenue") else None,
            "unimplementedBatteries": unimplemented_batteries(context),
            "conflicts": [dict({"id": r["id"]}, **c)
                          for r in rows for c in r["context"]["conflicts"]],
            # The PROFILE-LAYER decision, rolled up beside the conflicts and for the same
            # reason: a consumer should not have to walk every record to learn what the
            # organisation's profile decided. It is the profile layer specifically, because
            # that is the only part that is uniform across the store — §2.3 lets any single
            # incident declare its way in or out, so a rolled-up "asked" that blended the
            # subject layer would be true of no record in particular.
            #
            # Every other consumer of CAC-AP-1 puts exactly these two keys at the top level.
            # They have no subject layer, so for them this IS the whole answer; here it is
            # the org-level half of it, and `subjectMayAdjust` says so rather than leaving a
            # reader to discover the difference from a record that disagrees with it.
            "asked": sorted((context.get("applicability") or {})
                            .get(CONTEXT_SKILL, {}).get("ask") or []),
            "skipped": sorted(((context.get("applicability") or {})
                               .get(CONTEXT_SKILL, {}).get("skipped") or []),
                              key=lambda r: r.get("battery") or ""),
            "subjectMayAdjust": True,
        }
    return dict({
        "meta": dict(store.get("meta") or {}),
        "today": today,
        "now": now_iso,
        "holidays": sorted(holidays),
        "incidents": rows,
        "escalations": escalations(store, today, now_iso, context),
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
            # Open incidents split by band. Every band appears, including the empty ones,
            # so the shape can be read against last quarter's — a band that disappeared
            # when it emptied would look like a band that stopped applying. `closed` is
            # excluded because `open` is the population being split, and a part outside
            # the whole would stop the segments summing to the total beside them.
            #
            # This belongs here and not in whatever draws it. Three of these bands are
            # states of a statutory clock, and a count of them recomputed downstream is a
            # second answer to a regulatory question that must only have one.
            "byBand": {b: len([r for r in live if r["band"] == b])
                       for b in INCIDENT_BANDS if b != BAND_CLOSED},
        },
    }, **extra)


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

        # Art. 5(2) of RTS 2025/301 — the carve-out this engine had wrong until v0.49.0.
        # Aware 07-06T06:00, classified 07-08T09:00: more than 24h later. Under 5(2) the
        # deadline is classification + 4h = 07-08T13:00. Taking the earlier bound would give
        # 07-07T06:00, a deadline already in the past, and report OVERDUE on an incident with
        # four hours still to run. A false overdue is the one direction a clock must not fail
        # in, so it is pinned here in both the deadline and the state.
        set_anchor(store, "I-002", aware="2026-07-06T06:00:00+00:00",
                   classified="2026-07-08T09:00:00+00:00", actor="t")
        d = analyze(store, "2026-07-08", "2026-07-08T10:00:00+00:00")["incidents"][1]
        init = [c for c in d["clocks"] if c["window"] == "initial"][0]
        eq(init["deadline"], "2026-07-08T13:00:00+00:00",
           "late classification: Art. 5(2) gives four hours from classification")
        eq(init["anchorKind"], "classification", "and the awareness cap does not govern")
        eq(init["state"], CLOCK_DUE,
           "NOT overdue — the lapsed awareness cap must not backdate the deadline")
        eq(init["hoursRemaining"], 3.0, "three hours remain under 5(2)")
        ok("Art. 5(2)" in init["note"], "and the note cites the provision that governed")
        # Restore the prompt-classification anchors the rest of this block builds on.
        set_anchor(store, "I-002", aware="2026-07-06T06:00:00+00:00",
                   classified="2026-07-06T09:00:00+00:00", actor="t")
        d = analyze(store, "2026-07-06", "2026-07-06T14:00:00+00:00")["incidents"][1]

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

        # --- escalation (CAC-EL-1 §1.3) ---------------------------------------------
        #
        # Built on its own store. The shared one above has accumulated determinations,
        # filings and a closed incident, and a trigger that fires for the wrong reason in a
        # busy fixture is indistinguishable from one that works.
        #
        # `ts` is stamped explicitly wherever the assertion turns on ordering. Both
        # `determine` and `assess_factor` stamp `now_ts()`, so in a fixture built inside one
        # second the determination and the factor after it would share a timestamp and the
        # supersession test would pass or fail on how fast the machine ran.
        def _at(entry, ts):
            entry["ts"] = ts
            return entry

        def _esc(st, today_, now_=None):
            return analyze(st, today_, now_ or (today_ + "T00:00:00+00:00"))["escalations"]

        est = new_store("Escalation Co", "CISO")
        open_incident(est, "Payroll portal breach", "2026-07-06",
                      regimes=["sec-1.05"], actor="t")
        _at(determine(est, "I-001", "material", "Export of SSN confirmed.", "GC",
                      "2026-07-14", actor="t"), "2026-07-14T10:00:00+00:00")
        eq(business_days_after("2026-07-14", 4), "2026-07-20",
           "the 8-K deadline this section is pinned against")

        # A window still inside its deadline is the attention list, not an escalation — the
        # same line exceptions-register draws at `revalidation-due`.
        eq(_esc(est, "2026-07-16"), [],
           "a window that is due but not yet past escalates nothing")
        due = analyze(est, "2026-07-16", "2026-07-16T00:00:00+00:00")
        eq(due["attention"]["due"], ["I-001"],
           "and it is still on the attention list, where a live deadline belongs")

        over = _esc(est, "2026-07-22")
        eq([(e["subjectRef"], e["trigger"], e["severity"]) for e in over],
           [("I-001", "window-overdue", "critical")], "a passed deadline with no filing")
        eq(over[0]["since"], "2026-07-20", "dated from the deadline, not from today")
        eq(over[0]["evidence"]["baseline"], "sec-1.05:8-K",
           "the baseline names the window, so two windows never merge into one line")
        eq(over[0]["evidence"]["from"], "2026-07-14",
           "and `from` is the anchor the deadline was computed from")
        eq(over[0]["evidence"]["to"], "2026-07-22",
           "measured against today, because Item 1.05 counts days and not hours")
        eq(over[0]["subjectKind"], "incident", "one kind of object here, always named")
        for e in over:
            eq(sorted(e), sorted(["subjectRef", "subjectKind", "trigger", "severity",
                                  "since", "evidence"]), "the §1.3 record shape, exactly")

        record_filing(est, "I-001", "sec-1.05:8-K", "2026-07-21", actor="t")
        eq(_esc(est, "2026-07-22"), [],
           "and it clears when the filing is recorded — derived, never stored")

        # --- the exclusion that matters most ----------------------------------------
        # Item 1.05 requires the determination "without unreasonable delay" and names no
        # number of days. An incident sitting undetermined for a month escalates NOTHING,
        # however uncomfortable that reads: the alternative is this engine inventing the
        # threshold the rule declines to set, then writing down the date it was crossed.
        slow = new_store("Slow Co", "CISO")
        open_incident(slow, "Undetermined for weeks", "2026-07-01",
                      regimes=["sec-1.05"], actor="t")
        eq(_esc(slow, "2026-08-15"), [],
           "45 days with no determination escalates nothing, and deliberately")
        row_slow = analyze(slow, "2026-08-15", "2026-08-15T00:00:00+00:00")
        eq(row_slow["incidents"][0]["daysSinceDiscovery"], 45,
           "the elapsed distance is still reported — declining to judge is not declining "
           "to count")
        eq(row_slow["attention"]["noDetermination"], ["I-001"],
           "and it is on the attention list, which is where the question belongs")

        # --- anchor-missing ---------------------------------------------------------
        dor = new_store("DORA Co", "CISO")
        open_incident(dor, "Payment rail outage", "2026-07-06", regimes=["dora"], actor="t")
        anc = _esc(dor, "2026-07-07")
        eq([(e["trigger"], e["severity"], e["evidence"]["baseline"]) for e in anc],
           [("anchor-missing", "high", "dora:initial")],
           "a regime counting clock hours with no anchor recorded")
        eq(anc[0]["since"], "2026-07-06",
           "dated from discovery — the earliest date the gap can honestly be dated from")
        set_anchor(dor, "I-001", aware="2026-07-06T06:00:00+00:00", actor="t")
        eq([e["trigger"] for e in _esc(dor, "2026-07-06", "2026-07-06T10:00:00+00:00")], [],
           "and it clears the moment an anchor exists")
        # DORA counts hours, so its overdue evidence must be measured in hours too.
        late_dora = _esc(dor, "2026-07-07", "2026-07-07T12:00:00+00:00")
        eq([e["trigger"] for e in late_dora], ["window-overdue"],
           "24 hours from awareness, passed, with nothing filed")
        eq(late_dora[0]["evidence"]["to"], "2026-07-07T12:00:00+00:00",
           "measured against the clock time, because DORA counts hours and not days")
        eq(late_dora[0]["since"], "2026-07-07T06:00:00+00:00",
           "and dated from the hour the window closed")

        # --- determination-superseded -----------------------------------------------
        sup = new_store("Superseded Co", "CISO")
        open_incident(sup, "Vendor breach", "2026-07-06", regimes=["sec-1.05"], actor="t")
        _at(assess_factor(sup, "I-001", "data", "unknown", "Exfiltration not confirmed.",
                          actor="t"), "2026-07-10T09:00:00+00:00")
        _at(determine(sup, "I-001", "not-material", "No confirmed export.", "GC",
                      "2026-07-14", actor="t"), "2026-07-14T10:00:00+00:00")
        eq(_esc(sup, "2026-07-20"), [],
           "a settled determination with a record that has not moved escalates nothing")

        _at(assess_factor(sup, "I-001", "data", "bearing",
                          "Forensics confirmed export of 1,940 records.", actor="t"),
            "2026-07-18T09:00:00+00:00")
        moved = _esc(sup, "2026-07-20")
        eq([(e["trigger"], e["severity"]) for e in moved],
           [("determination-superseded", "high")],
           "a factor recorded after a settled determination that changed its answer")
        eq(moved[0]["since"], "2026-07-18T09:00:00+00:00",
           "dated from the moment the record moved, not from the determination")
        eq(moved[0]["evidence"]["baseline"], "not-material",
           "the baseline is the determination the record moved out from under")
        ok("data (unknown → bearing)" in moved[0]["evidence"]["detail"],
           "and the detail quotes the assessor's own recorded words, both of them")
        ok("not that the determination was wrong" in moved[0]["evidence"]["detail"],
           "with the record carrying its own statement of what it does not claim")

        # The two clocks, kept apart. `determinedAt` is back-datable by design — it is the
        # Item 1.05 anchor and often records a decision made days before anyone typed it in.
        # Here the determination is dated the 14th but was WRITTEN on the 18th, after the
        # forensics factor landed on the 16th. The record therefore already contained that
        # factor when the determination was made, and nothing has been superseded. Keying
        # the as-of comparison on `determinedAt` instead of `ts` reverses this answer and
        # reports a determination as stale on the strength of a fact it was made with.
        back = new_store("Backdated Co", "CISO")
        open_incident(back, "Vendor breach", "2026-07-06", regimes=["sec-1.05"], actor="t")
        _at(assess_factor(back, "I-001", "data", "bearing", "Export confirmed.", actor="t"),
            "2026-07-16T09:00:00+00:00")
        _at(determine(back, "I-001", "not-material", "Export confirmed but immaterial.",
                      "GC", "2026-07-14", actor="t"), "2026-07-18T10:00:00+00:00")
        ok(back["incidents"][0]["factors"][0]["ts"]
           < back["incidents"][0]["determinations"][0]["ts"]
           and back["incidents"][0]["determinations"][0]["determinedAt"]
           < back["incidents"][0]["factors"][0]["ts"][:10],
           "the fixture really is back-dated: written after the factor, dated before it")
        eq(_esc(back, "2026-07-20"), [],
           "a determination written after a factor is not superseded by it, however it "
           "is dated")

        # `since` is when the record FIRST moved, so two factors moving on different days
        # date the escalation from the earlier. With one moved factor min and max agree and
        # the distinction is untested.
        two = new_store("Two Factors Co", "CISO")
        open_incident(two, "Vendor breach", "2026-07-06", regimes=["sec-1.05"], actor="t")
        _at(determine(two, "I-001", "not-material", "Nothing confirmed.", "GC",
                      "2026-07-14", actor="t"), "2026-07-14T10:00:00+00:00")
        _at(assess_factor(two, "I-001", "data", "bearing", "Export confirmed.", actor="t"),
            "2026-07-16T09:00:00+00:00")
        _at(assess_factor(two, "I-001", "financial", "bearing", "Costs exceed retention.",
                          actor="t"), "2026-07-18T09:00:00+00:00")
        two_esc = _esc(two, "2026-07-20")
        eq(len(two_esc), 1, "two moved factors are one determination that moved, not two")
        eq(two_esc[0]["since"], "2026-07-16T09:00:00+00:00",
           "dated from the first movement, not the most recent one")
        for part in ("data (unassessed → bearing)", "financial (unassessed → bearing)"):
            ok(part in two_esc[0]["evidence"]["detail"],
               f"and both movements are named: {part}")

        # Severity does NOT vary with which way the factor moved. Ranking one direction
        # above the other would be this engine grading a legal judgment, and a graded
        # judgment is discoverable as an exhibit arguing against the organisation's own
        # conclusion. This is the check that fails if somebody later "improves" it.
        rev = new_store("Reverse Co", "CISO")
        open_incident(rev, "Vendor breach", "2026-07-06", regimes=["sec-1.05"], actor="t")
        _at(assess_factor(rev, "I-001", "data", "bearing", "Export suspected.", actor="t"),
            "2026-07-10T09:00:00+00:00")
        _at(determine(rev, "I-001", "material", "Assume export.", "GC", "2026-07-14",
                      actor="t"), "2026-07-14T10:00:00+00:00")
        _at(assess_factor(rev, "I-001", "data", "no-bearing", "Forensics found no export.",
                          actor="t"), "2026-07-18T09:00:00+00:00")
        rev_esc = [e for e in _esc(rev, "2026-07-19")
                   if e["trigger"] == "determination-superseded"]
        eq([e["severity"] for e in rev_esc], ["high"],
           "the same severity whichever way the record moved — the engine grades no "
           "judgment, in either direction")

        # A factor re-affirmed after the determination has not moved, and a factor that
        # wandered and came back has not moved either. Both would read as fresh facts if
        # this compared entry-by-entry instead of latest-against-as-of.
        same = new_store("Reaffirmed Co", "CISO")
        open_incident(same, "Vendor breach", "2026-07-06", regimes=["sec-1.05"], actor="t")
        _at(assess_factor(same, "I-001", "data", "bearing", "Export confirmed.", actor="t"),
            "2026-07-10T09:00:00+00:00")
        _at(determine(same, "I-001", "material", "Export confirmed.", "GC", "2026-07-14",
                      actor="t"), "2026-07-14T10:00:00+00:00")
        _at(assess_factor(same, "I-001", "data", "unknown", "Vendor retracted the report.",
                          actor="t"), "2026-07-16T09:00:00+00:00")
        _at(assess_factor(same, "I-001", "data", "bearing", "Retraction withdrawn.",
                          actor="t"), "2026-07-18T09:00:00+00:00")
        eq([e["trigger"] for e in _esc(same, "2026-07-19")], [],
           "a factor that wandered and came back has not moved, and is not reported twice")

        # An unsettled determination is the work still running, not a record moving under a
        # conclusion. Facts are supposed to arrive while a team is assessing.
        for unsettled in ("assessing", "not-yet-determinable"):
            wip = new_store("WIP Co", "CISO")
            open_incident(wip, "Under assessment", "2026-07-06", regimes=["sec-1.05"],
                          actor="t")
            _at(determine(wip, "I-001", unsettled, "Still working.", "GC", "2026-07-14",
                          actor="t"), "2026-07-14T10:00:00+00:00")
            _at(assess_factor(wip, "I-001", "data", "bearing", "Export confirmed.",
                              actor="t"), "2026-07-18T09:00:00+00:00")
            eq(_esc(wip, "2026-07-20"), [],
               f"a {unsettled!r} determination is not superseded by new facts")

        # --- closed, policy, ordering, and the no-verdict guard ---------------------
        close_incident(sup, "I-001", "Re-determined and disclosed.", actor="t")
        eq(_esc(sup, "2026-07-20"), [], "a closed incident escalates nothing")

        for key, fixture, today_ in (("windowOverdue", est, "2026-07-22"),
                                     ("anchorMissing", dor, "2026-07-07"),
                                     ("supersededDetermination", rev, "2026-07-19")):
            off = json.loads(json.dumps(fixture))
            off.setdefault("settings", {})["escalation"] = {key: False}
            ok(not [e for e in analyze(off, today_, today_ + "T00:00:00+00:00")["escalations"]
                    if e["trigger"] != "anchor-missing" or key == "anchorMissing"],
               f"{key} off suppresses its trigger")
            ok(ESCALATION_DEFAULTS[key] is True, f"{key} is on by default")
        eq(sorted(ESCALATION_DEFAULTS), ["anchorMissing", "scopeUndeclared",
                                         "supersededDetermination", "windowOverdue"],
           "four toggles and no numbers — the only quantities that could be tuned here "
           "are the ones the SEC and DORA already set")
        ok(not any(isinstance(v, (int, float)) and not isinstance(v, bool)
                   for v in ESCALATION_DEFAULTS.values()),
           "and none of them is a threshold this engine invented")

        # `scope-undeclared`, on a fixture that already produces an OVERDUE 8-K window.
        #
        # The overdue window is the point. Without a profile this store escalates
        # `window-overdue` on a computed deadline; supply a profile that has never declared
        # SEC scope and that deadline must disappear — no manufactured date — while the
        # attention does not. Written on a store with no live window, this check would pass
        # whether or not the withholding suppressed anything.
        unscoped_store = new_store("Unscoped Co", "CISO")
        open_incident(unscoped_store, "Payroll portal breach", "2026-07-06",
                      regimes=["sec-1.05"], actor="t")
        _at(determine(unscoped_store, "I-001", "material", "Export of SSN confirmed.", "GC",
                      "2026-07-14", actor="t"), "2026-07-14T10:00:00+00:00")
        unscoped_ctx = {"contractVersion": CONTEXT_CONTRACT, "profileVersion": "FY26",
                        "applicability": {"incident": {
                            "ask": ["sec-item-105"], "skipped": [],
                            "undeclared": [{"battery": "sec-item-105",
                                            "label": "SEC Item 1.05 disclosure window",
                                            "flag": "secItem105Scope", "source": "absent",
                                            "declaredBy": "", "declaredOn": "", "basis": "",
                                            "sentence": "asked in full; not declared."}]}}}
        plain = analyze(unscoped_store, "2026-07-22",
                        "2026-07-22T00:00:00+00:00")["escalations"]
        eq([e["trigger"] for e in plain], ["window-overdue"],
           "with no profile the fixture escalates on a computed, overdue 8-K deadline")
        with_ctx = analyze(unscoped_store, "2026-07-22", "2026-07-22T00:00:00+00:00",
                           unscoped_ctx)["escalations"]
        eq([e["trigger"] for e in with_ctx], ["scope-undeclared"],
           "and once the perimeter is undeclared, the manufactured deadline goes and the "
           "attention stays — the whole of AP-2 in one swap")
        eq(with_ctx[0]["severity"], "high",
           "high, not critical: a fact nobody recorded is not a deadline that passed")
        ok("secItem105Scope" in with_ctx[0]["evidence"]["detail"],
           "and the escalation names the declaration that would close it")
        off = json.loads(json.dumps(unscoped_store))
        off.setdefault("settings", {})["escalation"] = {"scopeUndeclared": False}
        eq(analyze(off, "2026-07-22", "2026-07-22T00:00:00+00:00",
                   unscoped_ctx)["escalations"], [],
           "scopeUndeclared off suppresses its trigger, and nothing else reappears")

        # Worst first, then by incident, then by trigger — so a pack reading three
        # producers gets one deterministic order.
        many = new_store("Many Co", "CISO")
        open_incident(many, "Second", "2026-07-06", regimes=["dora"], actor="t")
        open_incident(many, "First", "2026-07-06", regimes=["sec-1.05"], actor="t")
        _at(determine(many, "I-002", "material", "Material.", "GC", "2026-07-14",
                      actor="t"), "2026-07-14T10:00:00+00:00")
        _at(assess_factor(many, "I-002", "data", "bearing", "Export confirmed.", actor="t"),
            "2026-07-18T09:00:00+00:00")
        eq([(e["severity"], e["subjectRef"], e["trigger"]) for e in _esc(many, "2026-07-22")],
           [("critical", "I-002", "window-overdue"),
            ("high", "I-001", "anchor-missing"),
            ("high", "I-002", "determination-superseded")],
           "severity first, then incident, then trigger")

        # Two triggers at the same severity on the SAME incident. This pins the order that
        # reaches a pack; it does NOT prove the `trigger` sort key, and is not labelled as
        # though it did. Emission order already matches alphabetical for a same-severity tie
        # and the sort is stable, so removing that key changes no output and no test here
        # would catch it. Said plainly rather than dressed up: a check that cannot fail is
        # worth less than an honest note about why.
        tie = new_store("Tie Co", "CISO")
        open_incident(tie, "Payment rail outage", "2026-07-06", regimes=["dora"], actor="t")
        _at(assess_factor(tie, "I-001", "data", "unknown", "Not confirmed.", actor="t"),
            "2026-07-10T09:00:00+00:00")
        _at(determine(tie, "I-001", "not-material", "Nothing confirmed.", "GC",
                      "2026-07-14", actor="t"), "2026-07-14T10:00:00+00:00")
        _at(assess_factor(tie, "I-001", "data", "bearing", "Export confirmed.", actor="t"),
            "2026-07-18T09:00:00+00:00")
        eq([(e["severity"], e["subjectRef"], e["trigger"]) for e in _esc(tie, "2026-07-20")],
           [("high", "I-001", "anchor-missing"),
            ("high", "I-001", "determination-superseded")],
           "one incident, two triggers: the order that reaches a pack, pinned")

        # The no-verdict guard, run over output that actually carries escalations. The
        # check above it runs on a store whose escalation list is empty, so on its own it
        # would pass no matter what this section wrote into a detail line.
        esc_text = json.dumps(analyze(many, "2026-07-22", "2026-07-22T00:00:00+00:00"))
        ok(any(e["trigger"] for e in _esc(many, "2026-07-22")),
           "the no-verdict guard below is reading output that has escalations in it")
        for word in ("score", "Score", "recommend", "verdict", "unreasonable"):
            ok(word not in esc_text, f"no {word!r} in an analysis carrying escalations")

        # --- links, closing, and the family guard -----------------------------------
        link_incident(store, "I-001", risk_ids=["R-006"], exception_ids=["A-001"], actor="t")
        out = analyze(store, "2026-07-22", "2026-07-22T00:00:00+00:00")
        eq(out["attention"]["realizedAcceptedRisk"], ["I-001"],
           "an incident that realizes an accepted risk is surfaced, not buried")
        close_incident(store, "I-002", "Service restored; reported and closed with the NCA.",
                       actor="t")
        eq(len(store["incidents"]), 2, "closing does not delete the record")
        out = analyze(store, "2026-07-22", "2026-07-22T00:00:00+00:00")
        eq({k: v for k, v in out["counts"].items() if k != "byBand"},
           {"incidents": 2, "open": 1, "closed": 1}, "headline counts")

        # The band split partitions the open incidents, and the two have to agree. A mix
        # whose segments do not sum to the count printed beside it is a chart that
        # contradicts its own caption.
        by_band = out["counts"]["byBand"]
        eq(sum(by_band.values()), out["counts"]["open"],
           "the band split sums to the open count it partitions")
        eq(sorted(by_band), sorted(b for b in INCIDENT_BANDS if b != BAND_CLOSED),
           "every band is present, including the empty ones")
        ok(BAND_CLOSED not in by_band,
           "closed is excluded — it is not part of the population being split")
        eq(out["incidents"][1]["band"], BAND_CLOSED, "closed outranks every derivation")
        refuses(lambda: close_incident(store, "I-002", "again"),
                "closing an already-closed incident is refused")

        # --- CAC-AP-1 §2.3, at the function boundary -------------------------------
        #
        # evals/applicability.sh drives all of this through the CLI, which is where it
        # matters. It is pinned here as well because the clause below is the one that reads
        # correctly while being wrong: a subject that declared `null` has said something,
        # and `if declares.get(flag):` treats that identically to `false` — silently removing
        # a disclosure question on the strength of a record that says nobody knew.
        payload = {
            "contractVersion": CONTEXT_CONTRACT, "profileVersion": "FY26",
            "applicability": {"incident": {
                "ask": ["dora-windows"],
                "skipped": [{"battery": "sec-item-105",
                             "label": "SEC Item 1.05 disclosure window",
                             "flag": "secItem105Scope", "source": "profile",
                             "declaredBy": "GC", "declaredOn": "2026-01-02",
                             "basis": "No registered class; no s.15(d) obligation.",
                             "sentence": "SEC Item 1.05 disclosure window — not assessed."}]}},
        }
        bare = {"id": "X", "disclosure": {"regimes": []}}
        eq(applicability_for(payload, bare)["asked"], ["dora-windows"],
           "the profile's decision arrives decided and is used as-is")
        eq([r["battery"] for r in applicability_for(payload, bare)["skipped"]],
           ["sec-item-105"], "...including which battery it removed")

        def _decl(value, regimes=(), flag="secItem105Scope"):
            return {"id": "X", "disclosure": {"regimes": list(regimes)},
                    "contextDeclares": {flag: {
                        "value": value, "declaredBy": "GC", "declaredOn": "2026-02-02",
                        "basis": "The affected entity files its own current reports."}}}

        eq("sec-item-105" in applicability_for(payload, _decl(True))["asked"], True,
           "a subject declaring true re-adds a battery the profile removed")
        eq([r["battery"] for r in applicability_for(payload, _decl(True))["overrides"]],
           ["sec-item-105"], "...and the override is recorded, not merely acted on")
        eq([r["source"] for r in applicability_for(payload, _decl(None))["skipped"]],
           ["profile"],
           "a subject declaring NULL does not override — null is not false")
        eq("secItem105Scope" in applicability_for(payload, _decl(None))["subjectDeclared"],
           True, "...and the null is still carried, so the gap stays visible")
        # The other direction, on the battery the profile kept.
        dora_no = {"id": "X", "disclosure": {"regimes": []},
                   "contextDeclares": {"doraScope": {"value": False, "declaredBy": "GC",
                                                     "declaredOn": "2026-02-02",
                                                     "basis": "Outside the entity."}}}
        eq([r["source"] for r in applicability_for(payload, dora_no)["skipped"]
            if r["battery"] == "dora-windows"], ["subject"],
           "a subject declaring false removes a battery the profile kept")
        ok("GC" in [r for r in applicability_for(payload, dora_no)["skipped"]
                    if r["battery"] == "dora-windows"][0]["sentence"],
           "...and the sentence carries the subject's own declarer, which the profile "
           "could not have supplied")

        # Narrowing drops windows, and never for a regime the incident actually tracks.
        fake_clocks = [{"regime": "sec-1.05", "window": "8-K"},
                       {"regime": "dora", "window": "initial"}]
        view = applicability_for(payload, bare)
        eq([c["regime"] for c in narrow_clocks(fake_clocks, view, bare)], ["dora"],
           "a skipped battery's windows are absent, not `not-applicable`")
        tracked = {"id": "X", "disclosure": {"regimes": ["sec-1.05"]}}
        tview = applicability_for(payload, tracked)
        eq([c["regime"] for c in narrow_clocks(fake_clocks, tview, tracked)],
           ["sec-1.05", "dora"],
           "an incident tracked against the regime keeps its window — the profile narrows "
           "the default question set and does not overrule the assessor")
        eq([c["battery"] for c in tview["conflicts"]], ["sec-item-105"],
           "...and the disagreement is reported instead")
        # --- AP-2: ask the battery, withhold the date (BL-175) ---------------------
        #
        # These are the two cases every release test from v0.48.0 to v0.63.0 reproduced, run
        # here through the same functions the CLI uses. Both failed on ONE wrong flag, in
        # opposite directions, and both are asserted in both directions below.
        def _undeclared_payload(flag="secItem105Scope", source="absent"):
            return {"contractVersion": CONTEXT_CONTRACT, "profileVersion": "FY26",
                    "applicability": {"incident": {
                        "ask": ["dora-windows", "sec-item-105"],
                        "skipped": [],
                        "undeclared": [{
                            "battery": "sec-item-105",
                            "label": "SEC Item 1.05 disclosure window",
                            "flag": flag, "source": source, "declaredBy": "",
                            "declaredOn": "", "basis": "",
                            "sentence": ("SEC Item 1.05 disclosure window — asked in full. "
                                         "Organisation profile: `%s` is not declared."
                                         % flag)}]}}}

        und_payload = _undeclared_payload()
        real_clocks = [{"regime": "sec-1.05", "window": "8-K", "state": CLOCK_DUE,
                        "anchor": "2026-07-14", "anchorKind": "determination",
                        "deadline": "2026-07-20", "filedAt": None, "note": "4 business days"},
                       {"regime": "dora", "window": "initial", "state": CLOCK_NA,
                        "anchor": None, "anchorKind": "", "deadline": None,
                        "filedAt": None, "note": "not tracked"}]

        # CASE 1 — the London-listed non-registrant. Scope undeclared, incident tracked
        # against sec-1.05 anyway. The battery is asked and the DATE IS NOT COMPUTED.
        c1_inc = {"id": "X", "disclosure": {"regimes": ["sec-1.05"], "filings": {}}}
        c1 = applicability_for(und_payload, c1_inc)
        ok("sec-item-105" in c1["asked"], "an undeclared perimeter still asks the battery")
        eq([r["battery"] for r in c1["undeclared"]], ["sec-item-105"],
           "...and the payload's §2.4.1 record travels through to the consumer")
        eq(c1["conflicts"], [],
           "a silence is not a disagreement — nothing was declared to conflict with")
        c1_clocks = narrow_clocks(real_clocks, c1, c1_inc)
        sec_row = [c for c in c1_clocks if c["regime"] == "sec-1.05"][0]
        eq(sec_row["state"], CLOCK_SCOPE_UNDECLARED,
           "the Item 1.05 window is withheld, not computed — no manufactured legal date")
        eq(sec_row["deadline"], None, "and it carries no deadline at all")
        eq(sec_row["scopeFlag"], "secItem105Scope",
           "naming the flag that would settle it, which is the reader's next action")
        ok("not declared" in sec_row["note"] and "does not apply" in sec_row["note"],
           "and saying in as many words that this is not a finding of non-applicability")

        # The row must be PRESENT. Dropping it would make a firm that has not filled in its
        # profile look identical to one that is genuinely out of scope, which is the §15(d)
        # suppression arriving through the other door.
        eq(len(c1_clocks), 2, "the withheld window is a visible row, not an absence")

        # ...and it must not read like a skip. AP-2: a reader must never have to guess which
        # of the two they are looking at.
        skipped_view = applicability_for(payload, {"id": "X",
                                                   "disclosure": {"regimes": ["sec-1.05"]}})
        skip_sent = skipped_view["skipped"][0]["sentence"]
        ok("not assessed" in skip_sent and "not assessed" not in sec_row["note"],
           "`declared out` and `nobody said` do not share a sentence")

        # CASE 2 — the unlisted s.15(d) reporter, and the direction that SUPPRESSED a real
        # obligation. Its profile declares the listing flag false and says nothing about SEC
        # scope, which is every store written before this change.
        legacy = {"contractVersion": CONTEXT_CONTRACT, "profileVersion": "FY26",
                  "applicability": {"incident": _undeclared_payload()["applicability"]
                                    ["incident"]}}
        eq("sec-item-105" in applicability_for(legacy, bare)["asked"], True,
           "an unlisted s.15(d) reporter is ASKED the SEC battery rather than skipped")

        # Untracked and unscoped: the row already says `not-applicable` with no date on it.
        # There is nothing to withhold, and replacing a true statement with a vaguer one is
        # not an improvement.
        na_clocks = [dict(real_clocks[0], state=CLOCK_NA, deadline=None)]
        eq([c["state"] for c in narrow_clocks(na_clocks, applicability_for(und_payload, bare),
                                              bare)],
           [CLOCK_NA], "an untracked regime keeps `not-applicable`; there is no date to hold")

        # THE WAY OUT, and it must work or the withholding is a dead end. A subject
        # declaration settles the gate and the window computes from the same anchor.
        declared_inc = _decl(True, regimes=["sec-1.05"])
        dview = applicability_for(und_payload, declared_inc)
        eq(dview["undeclared"], [],
           "a subject declaring scope settles it, and the battery is no longer undeclared")
        eq([c["state"] for c in narrow_clocks(real_clocks, dview, declared_inc)
            if c["regime"] == "sec-1.05"], [CLOCK_DUE],
           "...so the deadline computes, from the anchor it always would have used")

        # A subject declaring FALSE over a profile silence is a skip, not a withholding —
        # somebody answered, and the answer is no.
        no_inc = _decl(False, regimes=[])
        nview = applicability_for(und_payload, no_inc)
        eq(([r["battery"] for r in nview["skipped"]], nview["undeclared"]),
           (["sec-item-105"], []),
           "a subject declaring false answers the question rather than leaving it open")

        # A PAYLOAD FROM AN OLDER `business-context` has no `undeclared` key at all. Reading
        # its absence as "everything is undeclared" would withhold every deadline in the
        # store the moment one skill was upgraded before the other.
        old_payload = {"contractVersion": CONTEXT_CONTRACT, "profileVersion": "FY26",
                       "applicability": {"incident": {"ask": ["sec-item-105"],
                                                      "skipped": []}}}
        oview = applicability_for(old_payload, c1_inc)
        eq(oview["undeclared"], [], "a payload with no §2.4.1 key withholds nothing")
        eq([c["state"] for c in narrow_clocks(real_clocks, oview, c1_inc)
            if c["regime"] == "sec-1.05"], [CLOCK_DUE],
           "...and its clocks compute exactly as that payload always made them compute")

        eq(unimplemented_batteries(
            {"applicability": {"incident": {"ask": ["nydfs-notification"], "skipped": []}}}),
           ["nydfs-notification"],
           "a battery this skill has no question for is named, not silently dropped")

        eq(parse_subject_flag("null"), None, "`null` parses to None, not to False")
        eq(parse_subject_flag("false"), False, "and `false` parses to False")
        refuses(lambda: parse_subject_flag("maybe"), "an unparseable subject value")
        bad_ctx = os.path.join(work, "bad-context.json")
        with open(bad_ctx, "w", encoding="utf-8") as fh:
            json.dump({"contractVersion": "CAC-AP-2", "applicability": {}}, fh)
        refuses(lambda: load_context(bad_ctx), "a payload from another contract version",
                CONTEXT_CONTRACT)
        with open(bad_ctx, "w", encoding="utf-8") as fh:
            json.dump({"contractVersion": CONTEXT_CONTRACT}, fh)
        refuses(lambda: load_context(bad_ctx),
                "a payload with no decided applicability, rather than a silent full ask",
                "business_context.py export")

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
    context = load_context(args.context) if getattr(args, "context", None) else None
    e = determine(store, args.id, args.state, args.rationale, args.decider, args.on,
                  args.actor, context)
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


def _cmd_declare_context(args):
    store = load_store(args.store)
    field = declare_context(store, args.id, args.flag, parse_subject_flag(args.value),
                            args.by, args.basis, args.on, args.actor)
    save_store(args.store, store)
    print(f"{args.id}: {args.flag} declared {field['value']!r} by {field['declaredBy']}")
    return 0


def _cmd_analyze(args):
    today, now_iso = _when(args)
    context = load_context(args.context) if args.context else None
    out = analyze(load_store(args.store), today, now_iso, context)
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
    sp.add_argument("--context", default=None, metavar="FILE",
                    help="a CAC-AP-1 payload; freezes the profile version and the batteries "
                         "not asked into this determination (§2.5)")
    sp.set_defaults(fn=_cmd_determine)

    sp = sub.add_parser("declare-context",
                        help="declare, at this incident, something the org profile decides "
                             "org-wide (CAC-AP-1 §2.3)")
    common(sp)
    sp.add_argument("--id", required=True)
    sp.add_argument("--flag", default="",
                    help="e.g. listedEntity, doraScope")
    sp.add_argument("--value", default="",
                    help="true, false or null — null records that nobody could answer, "
                         "which does not override the organisation profile")
    sp.add_argument("--by", default="")
    sp.add_argument("--on", default="")
    sp.add_argument("--basis", default="")
    sp.set_defaults(fn=_cmd_declare_context)

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
    sp.add_argument("--context", default=None, metavar="FILE",
                    help="a CAC-AP-1 applicability payload from "
                         "`business_context.py export`; optional, and absent leaves every "
                         "byte of this output as it was")
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
