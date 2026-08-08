#!/usr/bin/env python3
"""business_context.py — the organisation's own facts, and what they make applicable.

Every skill in this suite asks the CISO to declare something and then refuses to invent it.
`risk-register` takes an appetite band. `metrics-register` takes target, warn and critical.
`exceptions-register` demands an approver and a justification. `incident-materiality` walks
six factors and emits no verdict.

The discipline is right. What was missing is anywhere to record WHY the declared number is
that number — an appetite of `medium` traced to nothing, and a materiality assessment weighed
financial impact against a revenue base that lived in somebody's head.

This store holds those facts, and one thing more: the **applicability profile** (CAC-AP-1),
which lets every other skill ask only the questions that apply. Solved once here as a contract
each skill implements, rather than five times in five engines.

Two clauses carry the whole contract, and both are the opposite of the obvious default:

  * ABSENCE ASKS MORE. A missing profile, or a missing flag, means *not declared* — never
    *does not apply*. Silently narrowing scope on absent data produces an assessment that
    looks complete and is not.
  * THE SUBJECT OUTRANKS THE PROFILE. An org that declared no AI still gets the full AI
    battery on a vendor whose own record says it processes data with a model.

Standard library only. Subcommands:

  init         <file.biz> --org 'Name' [--prepared-by ..] [--fiscal-year-end ..]
  declare      <file.biz> --flag aiInUse --value true --by 'Name' --basis '...'
  set-fact     <file.biz> --crown-jewel 'CRM' --enables '..' --at-stake '..' --by .. --basis ..
               <file.biz> --segment '..' | --goal '..' | --obligation '..'
               <file.biz> --board-tolerance '..' --by 'Name' --on YYYY-MM-DD
  set-revenue  <file.biz> --exact 412000000 --currency USD --fiscal-year FY26 --by .. --basis ..
  review       <file.biz> --label 'FY27 planning' --why '...'
  show         <file.biz> [--json] [--render-revenue band|exact]
  applies      <file.biz> --skill incident [--subject-declares listedEntity=true]
  export       <file.biz> --context [--out FILE]
  escalations  <file.biz> [--today YYYY-MM-DD] [--json]
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
FAMILY = "business-context"
DEFAULT_REVIEW_CADENCE_DAYS = 365

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class Refusal(Exception):
    """A mutation the engine declines to perform.

    Raised before the store file is opened, so a refused command leaves the file
    byte-identical. Asserted in self-test rather than trusted.
    """


# --- Dates --------------------------------------------------------------------

def check_date(value: str, field: str) -> str:
    """Canonical `YYYY-MM-DD`, and a real calendar date, or a refusal."""
    if not isinstance(value, str) or not DATE_RE.match(value):
        raise Refusal(
            "%s must be a canonical zero-padded date, YYYY-MM-DD; got %r. "
            "'2026-7-1' is refused because it sorts after '2026-10-01' as text, and the "
            "review cadence compares dates." % (field, value))
    try:
        date.fromisoformat(value)
    except ValueError:
        raise Refusal("%s is not a real calendar date: %r" % (field, value))
    return value


def days_between(earlier: str, later: str) -> int:
    return (date.fromisoformat(later) - date.fromisoformat(earlier)).days


def now_ts() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def utc_today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


# --- Store IO -----------------------------------------------------------------
#
# D-5 MEASURE 1, and it is a deliberate reservation rather than an accident of layout:
# `profile` sits at the TOP LEVEL of the document, never nested under an entity.
#
# v1 assumes one organisation with one regulatory perimeter. That is right for the CISO this
# suite serves best and wrong for a group with several regulated subsidiaries, where the
# perimeter is genuinely per-entity. When that case arrives, a future `entities[]` INHERITS
# from this top-level profile, each entity carrying only the flags that differ — which makes
# the change additive, leaves every existing `.biz` valid, and needs no migration.
#
# Nest the profile under an entity now and that reversal costs a migration instead. This
# comment exists because the first person to add groups will otherwise do exactly that.

def new_store(org: str, prepared_by: str = "", scope_note: str = "",
              fiscal_year_end: str = "") -> dict:
    ts = now_ts()
    return {
        "schemaVersion": SCHEMA_VERSION,
        "family": FAMILY,
        "meta": {"orgName": org, "preparedBy": prepared_by, "scopeNote": scope_note,
                 "fiscalYearEnd": fiscal_year_end, "asOf": ts[:10]},
        "settings": {"reviewCadenceDays": DEFAULT_REVIEW_CADENCE_DAYS},
        "profile": {},
        "context": {"segments": [], "crownJewels": [], "strategicGoals": [],
                    "boardTolerance": [], "obligations": [], "revenue": None},
        "history": [],
        "snapshots": [],
        "createdAt": ts,
        "updatedAt": ts,
    }


def load(path: str) -> dict:
    """Read a `.biz`. Defaults are merged PER KEY, never wholesale.

    A file that set one field keeps the shipped values for the rest — the same rule
    `score_register.py` applies to its settings. Validation guards writes and never loads:
    a store carrying a bad value still opens, so a bad write can be inspected and corrected
    rather than locking the owner out of their own document.
    """
    try:
        with open(path, encoding="utf-8") as fh:
            obj = json.load(fh)
    except FileNotFoundError:
        raise Refusal("no such store: %s" % path)
    except ValueError as exc:
        raise Refusal("%s is not valid JSON: %s" % (path, exc))
    if not isinstance(obj, dict):
        raise Refusal("%s must contain a JSON object, got %s" % (path, type(obj).__name__))
    fam = obj.get("family")
    if fam != FAMILY:
        raise Refusal(
            "%s is not a business-context store: family is %r, expected %r. A risk register "
            "(.rr), metrics register (.mtr) or exceptions register (.exc) belongs to a "
            "different skill." % (path, fam, FAMILY))
    if obj.get("schemaVersion") != SCHEMA_VERSION:
        raise Refusal("%s is schemaVersion %r; this engine reads %d"
                      % (path, obj.get("schemaVersion"), SCHEMA_VERSION))
    obj["meta"] = {"orgName": "", "preparedBy": "", "scopeNote": "", "fiscalYearEnd": "",
                   "asOf": "", **(obj.get("meta") or {})}
    obj["settings"] = {"reviewCadenceDays": DEFAULT_REVIEW_CADENCE_DAYS,
                       **(obj.get("settings") or {})}
    obj.setdefault("profile", {})
    ctx = obj.get("context") or {}
    obj["context"] = {"segments": [], "crownJewels": [], "strategicGoals": [],
                      "boardTolerance": [], "obligations": [], "revenue": None, **ctx}
    obj.setdefault("history", [])
    obj.setdefault("snapshots", [])
    return obj


def save(path: str, store: dict) -> None:
    store["updatedAt"] = now_ts()
    directory = os.path.dirname(os.path.abspath(path)) or "."
    fd, tmp = tempfile.mkstemp(dir=directory, suffix=".biz.tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(store, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def append_history(store: dict, event: str, target: str, why: str = "",
                   detail: dict = None) -> None:
    entry = {"event": event, "target": target, "ts": now_ts()}
    if why:
        entry["why"] = why
    if detail:
        entry["detail"] = detail
    store["history"].append(entry)


# --- Provenance ---------------------------------------------------------------
#
# Every declared value carries who said it, when, and on what basis — the pattern `nist-csf`
# uses for a confirmed rating. A bare scalar is LEGAL ON READ and reported as unattributed
# rather than refused: validation guards writes, and an existing file stays openable.

def declared(value, by: str = "", on: str = "", basis: str = "") -> dict:
    return {"value": value, "declaredBy": by, "declaredOn": on, "basis": basis}


def value_of(field):
    """The value inside a wrapper, or a bare scalar unchanged.

    Returns None for a wrapper whose `value` is None, which the applicability engine treats
    as NOT DECLARED — see `applies`. That distinction is the contract's load-bearing one and
    is why this returns the value rather than the wrapper's truthiness.
    """
    if isinstance(field, dict) and "value" in field:
        return field.get("value")
    return field


def is_attributed(field) -> bool:
    return isinstance(field, dict) and bool(str(field.get("declaredBy") or "").strip())


# --- The profile --------------------------------------------------------------
#
# Declared, never inferred. This skill does not decide that you are in scope for DORA;
# being an EU entity does not set DORA scope, and a lawyer decides that.
#
# The enumeration is documentation, not a gate. An unknown flag is ACCEPTED WITH A WARNING
# rather than refused: the regulatory perimeter list will outgrow anything written here, and
# a register that refuses tomorrow's regime is worse than one that records it unrecognised.

KNOWN_FLAGS = {
    "listedEntity": "shares admitted to trading — the SEC Item 1.05 perimeter",
    "euEntity": "an establishment in the EU",
    "doraScope": "in scope for DORA as a financial entity or critical ICT provider",
    "nydfsScope": "a NYDFS Part 500 covered entity",
    "ukEntity": "an establishment in the UK",
    "aiInUse": "AI or machine-learning systems in production use",
    "otPresent": "operational technology or ICS in the estate",
    "cloudPosture": "cloud / on-prem / hybrid",
    "regulatedDataHeld": "regulated data classes held (health, card, personal)",
    "criticalVendorCount": "count of vendors assessed as critical",
    "concentrationConcern": "a declared concentration risk in the vendor base",
    "primarySector": "primary sector",
    "secondarySector": "secondary sector",
    "headcountBand": "headcount band",
    "jurisdictions": "jurisdictions of operation",
}


def parse_flag_value(raw: str):
    """`true` / `false` / a number / a JSON literal / otherwise the string itself.

    Deliberately NOT Python truthiness: the string "false" is False here, because a flag
    written from a shell would otherwise declare the opposite of what the user typed.
    """
    text = str(raw).strip()
    low = text.lower()
    if low in ("true", "yes"):
        return True
    if low in ("false", "no"):
        return False
    if low in ("null", "none", ""):
        return None
    try:
        return json.loads(text)
    except ValueError:
        return text


def declare_flag(store: dict, flag: str, raw_value, by: str, basis: str,
                 on: str = "") -> tuple:
    """Write one profile flag with its provenance. Returns (value, warning_or_empty).

    Refuses without `--basis`. This is the skill's version of the refusal discipline
    `exceptions-register` applies to a justification, and it is sharper here: a flag that
    narrows another skill's question set and cannot say why is WORSE than an absent flag,
    because an absent flag asks everything (CAC-AP-1 §2.2) while a wrong one quietly asks
    less. The cheapest way to get a narrower assessment than the facts justify is to declare
    a flag nobody can defend.
    """
    flag = str(flag or "").strip()
    if not flag:
        raise Refusal("declare needs --flag")
    if not str(by or "").strip():
        raise Refusal(
            "declaring %r requires --by. A flag narrows what every other skill asks; an "
            "unattributed one cannot be questioned later by the person it would have to be "
            "questioned with." % flag)
    if not str(basis or "").strip():
        raise Refusal(
            "declaring %r requires --basis. A flag that narrows another skill's question "
            "set and cannot say why is worse than no flag at all: absence asks everything, "
            "so the only thing an unjustified flag can do is ask less." % flag)
    on = check_date(on, "--on") if on else utc_today()
    value = parse_flag_value(raw_value) if isinstance(raw_value, str) else raw_value
    warning = ""
    if flag not in KNOWN_FLAGS:
        warning = ("%r is not in the documented flag set; recorded as declared. Consumers "
                   "that do not know it will ask their full question set." % flag)
    prior = value_of(store["profile"].get(flag)) if flag in store["profile"] else None
    store["profile"][flag] = declared(value, str(by).strip(), on, str(basis).strip())
    append_history(store, "flag-declared", flag, why=str(basis).strip(),
                   detail={"from": prior, "to": value, "declaredBy": str(by).strip(),
                           "declaredOn": on})
    return value, warning


# --- The context record -------------------------------------------------------
#
# The crown-jewel row is the one that earns this skill. It is the join between a technical
# asset and a business consequence — the join `ciso-board-translation` currently has to be
# told by hand, every single time.
#
# `atStake` is required for exactly that reason. A system with `enables` but nothing at stake
# is an asset inventory row, and an asset inventory is not what this file is for: if a fact
# does not change what a security question asks or what a security number means, it does not
# belong here.

def add_crown_jewel(store: dict, system: str, enables: str, at_stake: str,
                    by: str = "", basis: str = "", criticality: str = "",
                    depends_on=None) -> dict:
    """Record a system the business cannot lose, and optionally how critical it is.

    `criticality` and `dependsOn` exist for one consumer — a criticality analysis walking
    from a third-party arrangement back to the workflow it supports. They are the business
    judgement at the top of that walk, and they live here because that is what they are: a
    statement about what the organisation cannot lose, not about any vendor.

    Both are OPTIONAL and both are additive by construction. A crown jewel declared without
    them carries neither key, so every `.biz` written before this existed loads unchanged and
    exports byte-identically. Absence means not declared, never `not critical` — CAC-AP-1
    §2.2 applies to this field exactly as it does to a profile flag, and a consumer that read
    a missing level as the bottom of its scale would silently downgrade every system nobody
    has got to yet.

    No scale is validated here, deliberately. This skill does not own one: the levels are
    whatever the organisation ranks by, and the consumer that has a scale checks the value
    against it and reports a disagreement rather than coercing one. Validating here would
    mean this skill deciding what a criticality level is allowed to be.
    """
    missing = [n for n, v in (("--crown-jewel", system), ("--enables", enables),
                              ("--at-stake", at_stake)) if not str(v or "").strip()]
    if missing:
        raise Refusal(
            "a crown jewel needs %s.\n"
            "  `enables` is what the business does with it; `at-stake` is what is lost when "
            "it is not there. Without the second it is an asset inventory row, and the join "
            "to a business consequence — the whole reason this record exists — is missing."
            % ", ".join(missing))
    rec = {"system": system.strip(), "enables": enables.strip(),
           "atStake": at_stake.strip(),
           "declaredBy": str(by or "").strip(), "declaredOn": utc_today(),
           "basis": str(basis or "").strip()}
    if str(criticality or "").strip():
        rec["criticality"] = criticality.strip()
    depends = [str(d).strip() for d in (depends_on or []) if str(d or "").strip()]
    if depends:
        rec["dependsOn"] = depends
    store["context"]["crownJewels"].append(rec)
    append_history(store, "crown-jewel-added", rec["system"], why=rec["atStake"],
                   detail={"enables": rec["enables"]})
    return rec


def add_board_tolerance(store: dict, quote: str, by: str, on: str = "") -> dict:
    """The board's voiced tolerance, stored VERBATIM.

    Never paraphrased and never summarised on write. This is the sentence a risk appetite
    band was derived from — `risk-register` owns the band, this owns the words behind it —
    and a paraphrase is a second-hand quote in the one place a reader most needs a
    first-hand one.
    """
    if not str(quote or "").strip():
        raise Refusal("--board-tolerance needs the words that were actually said")
    if not str(by or "").strip():
        raise Refusal(
            "--board-tolerance requires --by. An unattributed board quote is a rumour, and "
            "it is the kind of rumour that ends up justifying an appetite band.")
    on = check_date(on, "--on") if on else utc_today()
    rec = {"quote": quote, "declaredBy": str(by).strip(), "declaredOn": on}
    store["context"]["boardTolerance"].append(rec)
    append_history(store, "board-tolerance-recorded", str(by).strip(), why=quote[:120])
    return rec


def add_listed(store: dict, key: str, text: str, label: str) -> str:
    if not str(text or "").strip():
        raise Refusal("%s needs a value" % label)
    store["context"][key].append(text.strip())
    append_history(store, key + "-added", text.strip()[:60])
    return text.strip()


# --- Revenue (D-2) ------------------------------------------------------------
#
# Stored exact, rendered as a band.
#
# The exact figure exists because `incident-materiality`'s financial factor needs an honest
# denominator, and a banded denominator is not one. The band exists because the rendered
# artifact is what circulates, and a document naming the revenue to the pound travels further
# than anyone intends.
#
# The band is DERIVED AT RENDER and never stored, so it cannot drift from the figure it
# describes — the same derived-not-stored rule the rest of the suite applies to exposure,
# status bands and confirmation age. Storing both would create two answers to one question,
# and the stored one would be the stale one.

REVENUE_LADDER = ((10e6, "<10m"), (50e6, "10-50m"), (100e6, "50-100m"),
                  (250e6, "100-250m"), (500e6, "250-500m"), (1e9, "500m-1bn"),
                  (5e9, "1-5bn"), (float("inf"), ">5bn"))


def revenue_band(exact) -> str:
    """The band a figure falls in. Boundaries belong to the band ABOVE them.

    10,000,000 is "10-50m", not "<10m": a ladder whose edges fall the other way reports a
    company at exactly its boundary as smaller than it is, and every edge in this ladder is a
    round number that real revenue figures land on far more often than chance.
    """
    if exact is None:
        return ""
    for ceiling, label in REVENUE_LADDER:
        if float(exact) < ceiling:
            return label
    return REVENUE_LADDER[-1][1]


def set_revenue(store: dict, exact, currency: str, fiscal_year: str,
                by: str, basis: str) -> dict:
    if exact is None or str(exact).strip() == "":
        raise Refusal("set-revenue needs --exact. The band is derived from it and is never "
                      "stored, so there is nothing to record without the figure.")
    try:
        value = float(exact)
    except (TypeError, ValueError):
        raise Refusal("--exact must be a number; got %r" % exact)
    if value < 0:
        raise Refusal("--exact must not be negative; got %r" % exact)
    if not str(currency or "").strip():
        raise Refusal(
            "--currency is required. A revenue base in an unnamed currency is the false "
            "precision this file exists to remove, and the materiality factor that reads it "
            "would be weighing a number against the wrong one.")
    if not str(fiscal_year or "").strip():
        raise Refusal("--fiscal-year is required: a revenue base with no period is not a base")
    if not str(by or "").strip() or not str(basis or "").strip():
        raise Refusal("set-revenue requires --by and --basis, like every declared value here")
    rec = {"exact": value, "currency": str(currency).strip().upper(),
           "fiscalYear": str(fiscal_year).strip(), "declaredBy": str(by).strip(),
           "declaredOn": utc_today(), "basis": str(basis).strip()}
    store["context"]["revenue"] = rec
    # The band is deliberately absent from what is written, and named here so a later reader
    # does not "fix" the omission.
    append_history(store, "revenue-set", rec["fiscalYear"], why=rec["basis"],
                   detail={"currency": rec["currency"]})
    return rec


# --- Snapshots (CAC-AP-1 §2.5) ------------------------------------------------

def review(store: dict, label: str, why: str) -> dict:
    """Freeze the profile AND the context under a label.

    A determination made in Q1 was made against Q1's profile. `risk-register` already freezes
    `settings` per snapshot so that "it was over appetite then" is judged by the appetite in
    force then; the same reasoning applies with more force here, because this profile decides
    which questions another skill asked at all.

    Both bodies are frozen, not just the profile: a materiality assessment weighed against
    last year's revenue base is as misread as one narrowed by last year's perimeter.
    """
    if not str(label or "").strip():
        raise Refusal("review needs --label: an unnamed snapshot cannot be cited later")
    if not str(why or "").strip():
        raise Refusal(
            "review requires --why. A snapshot with no reason is a timer going off, and the "
            "point of a review is that a human looked — the same distinction "
            "exceptions-register draws between re-validation and a clock resetting itself.")
    snap = {
        "label": str(label).strip(),
        "ts": now_ts(),
        "why": str(why).strip(),
        "profile": json.loads(json.dumps(store["profile"])),
        "context": json.loads(json.dumps(store["context"])),
    }
    store["snapshots"].append(snap)
    append_history(store, "reviewed", snap["label"], why=snap["why"])
    return snap


def last_review(store: dict):
    """The newest snapshot, by insertion order rather than by timestamp.

    Snapshots are append-only, so insertion order is the truth. Sorting by `ts` would let two
    machines with skewed clocks silently reorder which profile counts as current — the same
    reasoning score_register.py applies to its baseline.
    """
    snaps = store.get("snapshots") or []
    return snaps[-1] if snaps else None


# --- CAC-AP-1: the narrowing engine -------------------------------------------
#
# This is the whole contract, and it is the only place the narrowing logic lives. Every other
# skill reads the result as data; none of them re-implements it, and none of them imports
# this module.
#
# Two clauses carry it, and both are the opposite of what a first draft does:
#
#   §2.2 ABSENCE ASKS EVERYTHING. A missing profile, a missing flag, or a flag whose value is
#   None, means NOT DECLARED — never "does not apply". The dangerous default is the inverse:
#   narrowing on absent data produces an assessment that looks complete and is not, which is
#   the same failure class as a flat translations map rendering a finished-looking deck full
#   of placeholders.
#
#   `None` and `False` are therefore distinguished EXPLICITLY, never by truthiness. They are
#   different answers: False is "we looked, and it does not apply"; None is "nobody has said".
#   Collapsing them with `if not declared:` is the single change that would silently narrow
#   every assessment in the suite, and nothing on any rendered page would show it happened.
#
#   §2.3 THE SUBJECT OUTRANKS THE PROFILE. A subject-level declaration is applied AFTER the
#   profile and overrides it in BOTH directions — it can re-add a battery the profile removed
#   and remove one the profile kept. The profile's job is to keep the default question set
#   proportionate, not to overrule the assessor standing in front of the evidence.
#
# The question sets are declared here rather than by each consumer so that "which batteries
# exist" is one auditable list, and a consumer that forgets one cannot silently ask less.

QUESTION_SETS = {
    "incident": {
        "sec-item-105": "listedEntity",
        "dora-windows": "doraScope",
        "nydfs-notification": "nydfsScope",
    },
    "vendor": {
        "ai-processing": "aiInUse",
        "dora-ict-provider": "doraScope",
        "ot-connectivity": "otPresent",
        "regulated-data": "regulatedDataHeld",
    },
    "risk": {"ot-scenarios": "otPresent", "ai-scenarios": "aiInUse"},
    "metrics": {"ot-coverage": "otPresent"},
    "exceptions": {"dora-register": "doraScope"},
    # `posture` is `nist-csf`, named for the board section it produces rather than for the
    # skill, because that is the word every other consumer of this payload already uses.
    #
    # One battery, and it is the strongest gate in this table. The NIST Cyber AI Profile
    # (IR 8596) reweights the same 106 Subcategories for AI relevance, so applying it to an
    # organisation that runs no AI is exactly the disproportionate assessment a profile
    # exists to prevent — and leaving it off one that does is a real gap in the assessment.
    #
    # It is also the only battery any consumer can currently ANSWER. A `.csfp` records
    # whether the overlay is enabled, so unlike the registers this consumer holds both sides
    # of the question and can report a disagreement in either direction.
    "posture": {"ai-overlay": "aiInUse"},
}

BATTERY_LABEL = {
    "sec-item-105": "SEC Item 1.05 disclosure window",
    "dora-windows": "DORA reporting windows",
    "nydfs-notification": "NYDFS Part 500 notification",
    "ai-processing": "AI processing",
    "dora-ict-provider": "DORA critical ICT provider",
    "ot-connectivity": "OT connectivity",
    "regulated-data": "regulated data handling",
    "ot-scenarios": "OT scenarios",
    "ai-scenarios": "AI scenarios",
    "ot-coverage": "OT coverage",
    "dora-register": "DORA register of information",
    "ai-overlay": "NIST Cyber AI Profile overlay (IR 8596)",
}


def skip_record(battery: str, flag: str, source: str, field=None,
                subject_value=None) -> dict:
    """One skipped battery, carrying everything §2.4 needs to render it.

    An auditor cannot otherwise tell a question that was correctly out of scope from one
    nobody asked, and those are very different findings.
    """
    rec = {"battery": battery, "label": BATTERY_LABEL.get(battery, battery),
           "flag": flag, "source": source, "declaredBy": "", "declaredOn": "", "basis": ""}
    if source == "profile" and isinstance(field, dict):
        rec["declaredBy"] = str(field.get("declaredBy") or "")
        rec["declaredOn"] = str(field.get("declaredOn") or "")
        rec["basis"] = str(field.get("basis") or "")
    if source == "subject":
        rec["subjectValue"] = subject_value
    # The rendered sentence travels WITH the record rather than being rebuilt by whoever
    # reads it. §2.4 calls this "the sentence a consumer embeds verbatim", and a consumer
    # that reassembles it from the parts is a second author of the same sentence — the two
    # drift the first time either changes, and the drift lands in a disclosure record.
    rec["sentence"] = skip_sentence(rec)
    return rec


def skip_sentence(rec: dict) -> str:
    """The §2.4 sentence a consumer embeds verbatim in its artifact.

    Not a log line. This is what a reader of the finished document sees where the battery
    would have been, and it has to answer "why is this missing" without them going anywhere
    else to find out.
    """
    label = rec.get("label") or rec.get("battery")
    if rec.get("source") == "subject":
        return ("%s — not assessed. The subject declares %s: %r, which overrides the "
                "organisation profile." % (label, rec.get("flag"), rec.get("subjectValue")))
    who = rec.get("declaredBy") or "an unattributed declaration"
    when = rec.get("declaredOn")
    attribution = ("declared %s by %s" % (when, who)) if when else ("declared by %s" % who)
    # The basis is somebody's own sentence and usually ends in a full stop; appending one
    # unconditionally produced "…Delaware entity.." in the worked example. Trailing
    # punctuation is stripped from the join rather than from the stored text, which stays
    # exactly as it was written.
    basis = str(rec.get("basis") or "").strip()
    if basis:
        return ("%s — not assessed. Organisation profile: `%s: false`, %s — %s"
                % (label, rec.get("flag"), attribution,
                   basis if basis.endswith((".", "!", "?")) else basis + "."))
    return ("%s — not assessed. Organisation profile: `%s: false`, %s."
            % (label, rec.get("flag"), attribution))


def applies(profile: dict, question_sets: dict, subject: dict = None) -> dict:
    """Which batteries to ask, and which were skipped and why.

    `question_sets` maps battery id -> the profile flag that gates it.
    `subject` maps the same flag names -> the subject's own declaration.

    Returns {"ask": [...], "skipped": [ {...}, ... ]}.
    """
    profile = profile or {}
    subject = subject or {}
    ask, skipped = [], []
    for battery, gate in question_sets.items():
        # §2.3 first: the subject outranks the profile, in both directions.
        if gate in subject:
            declared_subject = subject[gate]
            if declared_subject is None:
                pass                      # subject said nothing about it; fall through
            elif declared_subject:
                ask.append(battery)
                continue
            else:
                skipped.append(skip_record(battery, gate, "subject",
                                           subject_value=declared_subject))
                continue
        field = profile.get(gate) if gate in profile else None
        declared_value = value_of(field) if field is not None else None
        # §2.2: absent, or declared-as-None, asks. `is None` and not truthiness — see the
        # block comment above; this line is the contract.
        if declared_value is None:
            ask.append(battery)
        elif declared_value:
            ask.append(battery)
        else:
            skipped.append(skip_record(battery, gate, "profile", field=field))
    return {"ask": sorted(ask), "skipped": sorted(skipped, key=lambda r: r["battery"])}


def applies_for(store: dict, skill: str, subject: dict = None) -> dict:
    if skill not in QUESTION_SETS:
        raise Refusal(
            "unknown --skill %r. Known: %s.\n"
            "  Refused rather than answered: a typo that quietly returned an empty question "
            "set would narrow an assessment to nothing and look like a clean result."
            % (skill, ", ".join(sorted(QUESTION_SETS))))
    return applies(store.get("profile") or {}, QUESTION_SETS[skill], subject)


def parse_subject_declares(pairs) -> dict:
    """`--subject-declares ai=true` -> {"aiInUse": True}, via the documented aliases."""
    aliases = {"ai": "aiInUse", "listed": "listedEntity", "dora": "doraScope",
               "nydfs": "nydfsScope", "ot": "otPresent",
               "regulated-data": "regulatedDataHeld"}
    out = {}
    for raw in (pairs or []):
        if "=" not in raw:
            raise Refusal("--subject-declares wants flag=value; got %r" % raw)
        key, _, val = raw.partition("=")
        key = key.strip()
        out[aliases.get(key, key)] = parse_flag_value(val)
    return out


# --- The consumer payload (transport is data, never imports) -------------------

def context_payload(store: dict) -> dict:
    """The flat, versioned payload a consumer reads via `--context`.

    The suite forbids cross-skill imports and every shipped script runs standalone, so the
    profile travels the way translations already do: as a file, read as data.

    `profileVersion` is always present, `unreviewed` when there is no snapshot, because a
    consumer that freezes what it used needs something to name — and "absent" is not a
    version a determination can cite a year later.
    """
    snap = last_review(store)
    rev = store["context"].get("revenue")
    return {
        "contractVersion": "CAC-AP-1",
        "schemaVersion": SCHEMA_VERSION,
        "orgName": store["meta"].get("orgName", ""),
        "profileVersion": snap["label"] if snap else "unreviewed",
        "profileReviewedOn": (snap["ts"][:10] if snap else ""),
        "profile": json.loads(json.dumps(store.get("profile") or {})),
        # The profile-layer narrowing, already decided, one entry per consuming skill.
        #
        # This is a Phase 5 finding, not an original part of the payload. Building the first
        # real consumer showed the contract asking for two things that cannot both be true:
        # §2.6 forbids importing this module, and the contract reference says the narrowing
        # logic "lives in exactly one place ... a consumer re-implementing it is a second
        # source of truth". Shipping only the raw flags forced every consumer to re-implement
        # §2.2 — and §2.2 is the clause where `if not declared:` passes every other test
        # anyone writes and silently narrows the assessment.
        #
        # So the decision travels instead of the raw material. A consumer reads its own
        # entry and applies only §2.3, whose data — the subject in front of it — exists
        # nowhere but the consumer. The flags stay in the payload beside this, because a
        # reader of the artifact needs to see what was declared, not just what it implied.
        "applicability": {skill: applies(store.get("profile") or {}, sets)
                          for skill, sets in sorted(QUESTION_SETS.items())},
        # Exact, deliberately. The consumer that needs this is the materiality financial
        # factor, and a banded denominator is not an honest one. Rendering is the renderer's
        # problem; see `revenue_band` and D-2.
        "revenue": (json.loads(json.dumps(rev)) if rev else None),
        "crownJewels": json.loads(json.dumps(store["context"].get("crownJewels") or [])),
    }


# --- Escalation (CAC-EL-1 §1.3) -----------------------------------------------
#
# ONE trigger in v1, and the restraint is the decision (D-3).
#
# `profile-stale` earns its place by being unlike every other escalation in the suite: it is
# not an exposure. A crossed band, a breached threshold, an expired acceptance — each says
# something got worse. This says the lens every other skill is looking through has not been
# checked, so the exposures they report may be measured against a perimeter that moved.
#
# `fact-unattributed` is DELIBERATELY DEFERRED. A freshly built `.biz` is nearly all
# unattributed, so shipping it would escalate on almost every field of a first run and teach
# the owner to skim the list — which costs more than the check is worth. Revisit with volume
# data from a real file, the same reasoning the exposure plan applied to acknowledgement.

ESCALATION_SEVERITY_ORDER = ["critical", "high", "medium"]


def escalations(store: dict, today: str = "") -> list:
    """Every escalation this store warrants, in the CAC-EL-1 §1.3 shape.

    `subjectKind` is `context`. Derived on every run, never stored, never a history event —
    and nothing here blocks: a stale profile still exports, still narrows, still renders.
    """
    today = today or utc_today()
    cadence = int((store.get("settings") or {}).get("reviewCadenceDays")
                  or DEFAULT_REVIEW_CADENCE_DAYS)
    snap = last_review(store)
    org = store["meta"].get("orgName") or "this organisation"
    if snap is None:
        # A store that has never been reviewed is not stale — it is new. Escalating it on
        # the first run is exactly the noise `fact-unattributed` was deferred to avoid, and
        # the owner has nothing to act on: there is no earlier review to compare against.
        return []
    reviewed_on = str(snap.get("ts") or "")[:10]
    if not DATE_RE.match(reviewed_on):
        return []
    age = days_between(reviewed_on, today)
    if age <= cadence:
        return []
    return [{
        "subjectRef": org,
        "subjectKind": "context",
        "trigger": "profile-stale",
        "severity": "high",
        "since": reviewed_on,
        "evidence": {
            "from": reviewed_on, "to": today, "baseline": snap.get("label", ""),
            "detail": ("the applicability profile was last reviewed %s, %d days ago against "
                       "a %d-day cadence. Every skill reading it is narrowing its questions "
                       "on a perimeter nobody has confirmed since — this is not an exposure, "
                       "it is the reason an exposure may be measured wrongly."
                       % (reviewed_on, age, cadence)),
        },
    }]


# --- Self-test ----------------------------------------------------------------
#
# Every expectation here was worked from the design doc and the CAC-AP-1 contract before the
# code that satisfies it. The applicability checks in particular are the ones the contract
# lives or dies on: get absence-vs-false backwards and every assessment in the suite quietly
# narrows, with nothing on any page to show it happened.

def _cmd_self_test(_args) -> int:
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
        path = os.path.join(work, "t.biz")

        # --- T1: the envelope ------------------------------------------------
        store = new_store("Acme Manufacturing", "D. Galleyne")
        save(path, store)
        eq(load(path)["meta"]["orgName"], "Acme Manufacturing", "init writes the org name")
        eq({k: v for k, v in load(path).items() if k != "updatedAt"},
           {k: v for k, v in store.items() if k != "updatedAt"},
           "a fresh store round-trips through save/load unchanged")
        eq(load(path)["profile"], {},
           "the profile starts empty — absence is not a negative")
        ok("entities" not in load(path),
           "and sits at the top level, so a future entities[] can inherit from it")

        # Defaults merge PER KEY. A file that set one field keeps the shipped values for
        # the rest, rather than losing them to a wholesale replacement.
        sparse = os.path.join(work, "sparse.biz")
        with open(sparse, "w", encoding="utf-8") as fh:
            json.dump({"schemaVersion": 1, "family": FAMILY,
                       "meta": {"orgName": "Sparse Co"}}, fh)
        loaded = load(sparse)
        eq(loaded["meta"]["orgName"], "Sparse Co", "a sparse file keeps what it set")
        eq(loaded["meta"]["preparedBy"], "", "and gains the keys it omitted")
        eq(loaded["settings"]["reviewCadenceDays"], DEFAULT_REVIEW_CADENCE_DAYS,
           "including settings, merged per key rather than wholesale")
        eq(loaded["context"]["crownJewels"], [], "and the context bodies")

        other = os.path.join(work, "other.exc")
        with open(other, "w", encoding="utf-8") as fh:
            json.dump({"schemaVersion": 1, "family": "exceptions-register"}, fh)
        refuses(lambda: load(other),
                "an exceptions register handed to this engine is refused by family",
                "not a business-context store")

        # A store carrying a value this engine would refuse to WRITE still opens. Validation
        # guards writes, never loads: locking an owner out of their own document to punish a
        # bad field helps nobody.
        odd = os.path.join(work, "odd.biz")
        with open(odd, "w", encoding="utf-8") as fh:
            json.dump({"schemaVersion": 1, "family": FAMILY,
                       "profile": {"aiInUse": True}}, fh)      # bare, unattributed
        eq(value_of(load(odd)["profile"]["aiInUse"]), True,
           "a bare unattributed flag is legal on read")
        eq(is_attributed(load(odd)["profile"]["aiInUse"]), False, "and reported as such")

        # --- T2: the provenance wrapper --------------------------------------
        eq(value_of(True), value_of(declared(True, "D. G.", "2026-07-14", "because")),
           "value_of reads a bare scalar and a wrapper identically")
        eq(is_attributed(declared(True, "D. G.", "2026-07-14", "b")), True,
           "an attributed wrapper is attributed")
        eq(is_attributed(declared(True)), False,
           "and one with no declarer is not, however complete it looks")
        eq(value_of(declared(None)), None,
           "a wrapper whose value is None reads as None, never as False")
        eq(value_of(declared(False)), False, "and a declared False reads as False")

        # --- T3: declare -----------------------------------------------------
        store = load(path)
        before = open(path, "rb").read()
        refuses(lambda: declare_flag(store, "aiInUse", True, "D. Galleyne", ""),
                "a flag with no --basis is refused", "requires --basis")
        refuses(lambda: declare_flag(store, "aiInUse", True, "", "a reason"),
                "a flag with no --by is refused", "requires --by")
        refuses(lambda: declare_flag(store, "", True, "D", "b"), "a flag with no name")
        eq(open(path, "rb").read(), before,
           "and every refusal leaves the file byte-identical")

        n_hist = len(store["history"])
        val, warn = declare_flag(store, "aiInUse", "true", "D. Galleyne",
                                 "Legal ops deployed a contract-review assistant in May")
        eq(val, True, "'true' from a shell is the boolean True")
        eq(warn, "", "a documented flag warns about nothing")
        eq(len(store["history"]) - n_hist, 1, "a valid declare appends exactly one entry")
        eq(store["history"][-1]["detail"]["declaredBy"], "D. Galleyne",
           "and the entry carries who declared it")
        eq(value_of(store["profile"]["aiInUse"]), True, "the flag is readable")
        eq(is_attributed(store["profile"]["aiInUse"]), True, "and attributed")

        # The string "false" is False. Python truthiness would make it True, and a flag
        # written from a shell would then declare the opposite of what was typed.
        eq(parse_flag_value("false"), False, "'false' is False, not a truthy string")
        eq(parse_flag_value("no"), False, "and so is 'no'")
        eq(parse_flag_value("true"), True, "'true' is True")
        eq(parse_flag_value("null"), None, "'null' is None — not declared")
        eq(parse_flag_value("42"), 42, "a number is a number")
        eq(parse_flag_value("hybrid"), "hybrid", "and anything else is itself")

        _, warn = declare_flag(store, "quantumReadiness", "false", "D. Galleyne",
                               "Not assessed this cycle")
        ok(warn, "an undocumented flag is accepted with a warning, never refused")
        eq(value_of(store["profile"]["quantumReadiness"]), False, "and is recorded")

        refuses(lambda: declare_flag(store, "aiInUse", True, "D", "b", on="2026-7-1"),
                "a non-canonical date is refused", "zero-padded")


        # --- T4: crown jewels and the narrative record ------------------------
        store = load(path)
        before = open(path, "rb").read()
        refuses(lambda: add_crown_jewel(store, "CRM", "client relationships", ""),
                "a crown jewel with no atStake is refused", "asset inventory row")
        refuses(lambda: add_crown_jewel(store, "", "x", "y"), "one with no system")
        refuses(lambda: add_crown_jewel(store, "CRM", "", "y"), "one with no enables")
        eq(open(path, "rb").read(), before, "and none of them touched the file")

        cj = add_crown_jewel(store, "CRM", "every client renewal conversation",
                             "the client data 60% of revenue depends on",
                             by="D. Galleyne", basis="FY26 planning review")
        eq(cj["atStake"], "the client data 60% of revenue depends on",
           "a crown jewel records what is lost, not just what it does")
        eq(len(store["context"]["crownJewels"]), 1, "and lands once")

        # Criticality and dependsOn: optional, additive, and never invented.
        #
        # The load-bearing case is the first. A crown jewel declared without a level must
        # carry NO key at all, not an empty string — every `.biz` written before these
        # fields existed has to load and export byte-identically, and a consumer has to be
        # able to tell "not declared" from "declared as nothing". An empty string would
        # collapse those two, which is the CAC-AP-1 §2.2 failure in a different costume.
        ok("criticality" not in cj and "dependsOn" not in cj,
           "a crown jewel with no level declared carries neither key, not an empty one")
        # On a scratch store: the export cases below pin this one to a single crown jewel,
        # and a fixture quietly gaining rows is how a downstream assertion starts passing
        # for the wrong reason.
        scratch = new_store("Scratch Ltd", "D. Galleyne")
        rated = add_crown_jewel(scratch, "Plant historian", "production scheduling",
                                "a day of lost output", by="Head of Engineering",
                                criticality="high", depends_on=["SCADA gateway", " "])
        eq(rated["criticality"], "high", "a declared level is recorded as given")
        eq(rated["dependsOn"], ["SCADA gateway"],
           "and blank dependencies are dropped rather than stored as empty rows")
        # No scale is checked here on purpose: this skill does not own one, and validating
        # would mean deciding what a criticality level is allowed to be for everybody.
        odd = add_crown_jewel(scratch, "Ledger", "statutory reporting", "the audit opinion",
                              criticality="tier-0")
        eq(odd["criticality"], "tier-0",
           "an organisation's own ranking is recorded, not corrected against a scale")
        eq([c["system"] for c in context_payload(scratch)["crownJewels"]
            if c.get("criticality")], ["Plant historian", "Ledger"],
           "and a declared level travels in the CAC-AP-1 payload")

        # The board's own words, verbatim. Quotes and non-ASCII survive a round trip,
        # because the one thing this field must never do is paraphrase.
        quote = ('We will not accept a "material" outage in the payments rail — '
                 "not for a quarter's savings. Chair, 14 July, £2m ceiling discussed.")
        refuses(lambda: add_board_tolerance(store, quote, ""),
                "an unattributed board quote is refused", "rumour")
        refuses(lambda: add_board_tolerance(store, "", "Chair"), "an empty quote")
        add_board_tolerance(store, quote, "Chair", on="2026-07-14")
        save(path, store)
        eq(load(path)["context"]["boardTolerance"][0]["quote"], quote,
           "a tolerance quote round-trips with its quotes and non-ASCII unchanged")

        # ...and is READABLE. Storing the sentence and having no way to read it back is the
        # gap B4 found: the question arrives as "I want the exact words on file", and a skill
        # that cannot print them sends the reader looking for a document instead.
        lines = []
        eq(print_board_tolerance(store, lines.append), 1, "one quote is on file")
        ok(any(quote in ln for ln in lines),
           "and `show` prints it verbatim, not a paraphrase or a count")
        ok(any("Chair" in ln and "2026-07-14" in ln for ln in lines),
           "with the person who said it and the date, so it can be cited")
        empty = []
        eq(print_board_tolerance(new_store("Nobody Ltd"), empty.append), 0, "none on file")
        ok(any("NONE RECORDED" in ln for ln in empty),
           "and an empty store SAYS nothing is recorded rather than omitting the heading")
        ok(any("different fact" in ln for ln in empty),
           "...naming the distinction, because unrecorded is not the same as unsaid")

        # --- T5: revenue, and the ladder --------------------------------------
        # Every boundary belongs to the band ABOVE it. A ladder whose edges fall the other
        # way reports a company sitting exactly on a round number as smaller than it is,
        # and round numbers are where real revenue figures land.
        for figure, want in ((0, "<10m"), (9_999_999, "<10m"), (10e6, "10-50m"),
                             (49_999_999, "10-50m"), (50e6, "50-100m"),
                             (100e6, "100-250m"), (250e6, "250-500m"),
                             (500e6, "500m-1bn"), (1e9, "1-5bn"), (5e9, ">5bn"),
                             (50e9, ">5bn")):
            eq(revenue_band(figure), want, "revenue_band(%r)" % figure)
        eq(revenue_band(None), "", "no figure yields no band, never a default one")

        store = load(path)
        before = open(path, "rb").read()
        for label, kw in (("no --exact", dict(exact=None, currency="USD", fiscal_year="FY26",
                                              by="D", basis="b")),
                          ("no --currency", dict(exact=1.0, currency="", fiscal_year="FY26",
                                                 by="D", basis="b")),
                          ("no --fiscal-year", dict(exact=1.0, currency="USD",
                                                    fiscal_year="", by="D", basis="b")),
                          ("no --basis", dict(exact=1.0, currency="USD",
                                              fiscal_year="FY26", by="D", basis="")),
                          ("a negative figure", dict(exact=-5, currency="USD",
                                                     fiscal_year="FY26", by="D", basis="b")),
                          ("a non-number", dict(exact="lots", currency="USD",
                                                fiscal_year="FY26", by="D", basis="b"))):
            refuses(lambda kw=kw: set_revenue(store, **kw), "set-revenue with %s" % label)
        eq(open(path, "rb").read(), before, "and every one left the file byte-identical")

        set_revenue(store, 412_000_000, "usd", "FY26", "CFO", "FY26 audited accounts")
        save(path, store)
        rev = load(path)["context"]["revenue"]
        eq(rev["exact"], 412000000.0, "the exact figure is stored")
        eq(rev["currency"], "USD", "and the currency is normalised")
        eq(revenue_band(rev["exact"]), "250-500m", "the band derives from it")

        # Derived, never stored. The whole point of a derived band is that it cannot go
        # stale against the figure; a stored one could, and would be the one people read.
        blob = json.dumps(load(path))
        ok(not any(lbl in blob for _c, lbl in REVENUE_LADDER),
           "no band label is written anywhere into the store")
        ok("band" not in json.dumps(load(path)["context"]["revenue"]),
           "and the revenue record itself carries no band key")

        # --- T6: snapshots freeze both bodies ---------------------------------
        store = load(path)
        refuses(lambda: review(store, "", "why"), "a snapshot with no label")
        refuses(lambda: review(store, "FY26", ""), "a snapshot with no --why", "a human looked")

        declare_flag(store, "doraScope", "false", "GC", "No EU financial entity in the group")
        review(store, "FY26 close", "Annual profile review with the GC and the CFO")
        # Change the flag AFTER the snapshot. The snapshot must still report what was true
        # when the determination that cites it was made.
        declare_flag(store, "doraScope", "true", "GC",
                     "Dublin subsidiary authorised in November")
        save(path, store)
        frozen = load(path)["snapshots"][-1]
        eq(value_of(frozen["profile"]["doraScope"]), False,
           "the snapshot still reports the profile as it stood")
        eq(value_of(load(path)["profile"]["doraScope"]), True,
           "while the live profile has moved on")
        eq(frozen["context"]["revenue"]["exact"], 412000000.0,
           "and the context is frozen too, not just the profile")
        eq(len(load(path)["snapshots"]), 1, "snapshots are append-only")
        eq(last_review(load(path))["label"], "FY26 close", "the current review is found")
        eq(last_review(new_store("X")), None, "and a store with none has no review")

        # TWO snapshots, or this proves nothing: with one, the newest and the oldest are the
        # same record and `snaps[0]` passes every check `snaps[-1]` does. `last_review`
        # stamps `profileVersion` onto the export payload, so returning the oldest would
        # label every consumer's read with a profile version that stopped being true.
        store = load(path)
        review(store, "FY27 planning", "Second review, after the Dublin authorisation")
        eq(last_review(store)["label"], "FY27 planning",
           "the newest of two snapshots is the later one")
        eq(len(store["snapshots"]), 2, "and both are kept")

        # Insertion order is the truth, not the timestamp. Snapshots are append-only, and
        # sorting by `ts` would let two machines with skewed clocks silently reorder which
        # profile counts as current — the same reasoning score_register.py applies to its
        # baseline.
        store["snapshots"][-1]["ts"] = "2020-01-01T00:00:00+00:00"
        eq(last_review(store)["label"], "FY27 planning",
           "even when the later snapshot carries the earlier timestamp")


        # --- T7: the contract. These five are what it lives or dies on. --------
        QS = {"sec-item-105": "listedEntity", "dora-windows": "doraScope"}

        # 1. Empty profile -> EVERY battery asked, nothing skipped. Absence asks more.
        got = applies({}, QS)
        eq(got["ask"], ["dora-windows", "sec-item-105"], "an empty profile asks everything")
        eq(got["skipped"], [], "and skips nothing")

        # 2. Flag present but value None -> still asked. `None` is not-declared, and a
        #    wrapper with a null value is exactly how a half-filled form arrives.
        got = applies({"listedEntity": declared(None, "D. G.", "2026-01-01", "unknown")}, QS)
        ok("sec-item-105" in got["ask"],
           "a flag declared with a null value asks, rather than narrowing")
        eq(got["skipped"], [], "and is not recorded as a skip")

        # The same, unwrapped: a bare None in the profile is not-declared too.
        eq(applies({"listedEntity": None}, QS)["ask"],
           ["dora-windows", "sec-item-105"], "a bare null flag asks as well")

        # 3. Flag false -> skipped, WITH its provenance. §2.4: an auditor must be able to
        #    tell a question correctly out of scope from one nobody asked.
        prof = {"listedEntity": declared(False, "D. Galleyne", "2026-07-14",
                                         "Privately held; no admitted securities")}
        got = applies(prof, QS)
        eq(got["ask"], ["dora-windows"], "a false flag removes its battery")
        eq([r["battery"] for r in got["skipped"]], ["sec-item-105"], "and records the skip")
        rec = got["skipped"][0]
        eq(rec["declaredBy"], "D. Galleyne", "the skip carries who declared it")
        eq(rec["declaredOn"], "2026-07-14", "and when")
        eq(rec["basis"], "Privately held; no admitted securities", "and on what basis")
        sentence = skip_sentence(rec)
        for needle in ("listedEntity", "2026-07-14", "D. Galleyne", "not assessed"):
            ok(needle in sentence, "the rendered skip names %s" % needle)

        # 4. Flag false AND the subject declares true -> ASKED. This is the design's
        #    vendor-with-AI case: the org declared no AI, this vendor processes data with a
        #    model, and the assessor in front of the evidence outranks the profile.
        got = applies(prof, QS, subject={"listedEntity": True})
        ok("sec-item-105" in got["ask"],
           "a subject declaring true re-adds a battery the profile removed")
        eq(got["skipped"], [], "and nothing is skipped")

        # 5. Flag true AND the subject declares false -> skipped, naming the SUBJECT.
        #    The override runs in both directions or it is not an override.
        got = applies({"listedEntity": declared(True, "D. G.", "2026-01-01", "listed")},
                      QS, subject={"listedEntity": False})
        eq(got["ask"], ["dora-windows"], "a subject declaring false removes it")
        eq(got["skipped"][0]["source"], "subject", "and the skip names the subject")
        ok("overrides the organisation profile" in skip_sentence(got["skipped"][0]),
           "which the rendered sentence says in as many words")

        # A subject that declares None says nothing, and falls through to the profile
        # rather than being read as False.
        got = applies(prof, QS, subject={"listedEntity": None})
        eq([r["battery"] for r in got["skipped"]], ["sec-item-105"],
           "a subject declaring null does not override; the profile still decides")
        # The SOURCE, not just the battery. A subject-null wrongly read as false skips the
        # same battery for the wrong reason, and the rendered sentence then tells an auditor
        # the subject declined a question the subject never mentioned.
        eq(got["skipped"][0]["source"], "profile",
           "and the skip is attributed to the profile, not to a subject that said nothing")
        ok("overrides the organisation profile" not in skip_sentence(got["skipped"][0]),
           "so the sentence does not claim an override that never happened")

        # The falsy trap, stated as its own check. Every one of these is NOT-DECLARED and
        # must ask; only an explicit False may narrow. `if not declared:` passes every other
        # test in this file and fails this one.
        for empty in (None, declared(None)):
            eq(applies({"listedEntity": empty}, QS)["skipped"], [],
               "not-declared (%r) never narrows" % (empty,))
        eq([r["battery"] for r in applies({"listedEntity": False}, QS)["skipped"]],
           ["sec-item-105"], "while a bare False does narrow")
        eq([r["battery"] for r in applies({"listedEntity": declared(False)}, QS)["skipped"]],
           ["sec-item-105"], "as does a wrapped False")

        # Every battery is accounted for: asked or skipped, never dropped.
        for prof2 in ({}, prof, {"listedEntity": declared(False), "doraScope": declared(False)}):
            r = applies(prof2, QS)
            eq(sorted(r["ask"] + [x["battery"] for x in r["skipped"]]), sorted(QS),
               "every battery is either asked or skipped, for profile %r" % (prof2,))

        # --- T8: the CLI surface ----------------------------------------------
        store = load(path)
        # The worked store needs a false flag for the narrowing below to be real rather
        # than a lucky absence — absence asks everything, so a store with nothing declared
        # would "pass" a narrowing test by never narrowing.
        declare_flag(store, "listedEntity", "false", "D. Galleyne",
                     "Privately held; no admitted securities")
        save(path, store)
        store = load(path)
        refuses(lambda: applies_for(store, "vendorr"),
                "an unknown --skill is refused", "look like a clean result")
        ok("incident" in QUESTION_SETS and "vendor" in QUESTION_SETS,
           "the documented skills are present")
        for skill, sets in QUESTION_SETS.items():
            for battery in sets:
                ok(battery in BATTERY_LABEL, "%s has a human label" % battery)
        eq(parse_subject_declares(["ai=true"]), {"aiInUse": True}, "the ai alias resolves")
        eq(parse_subject_declares(["listedEntity=false"]), {"listedEntity": False},
           "and a full flag name passes through")
        refuses(lambda: parse_subject_declares(["ai"]), "a malformed subject declaration")

        # The worked store declares listedEntity false, so `incident` must skip the SEC
        # battery and say why.
        res = applies_for(store, "incident")
        ok("sec-item-105" in [r["battery"] for r in res["skipped"]],
           "the store's false flag narrows the incident question set")
        ok("dora-windows" in res["ask"],
           "while doraScope, declared true later, is still asked")

        # --- T9: the consumer payload -----------------------------------------
        payload = context_payload(store)
        eq(payload["contractVersion"], "CAC-AP-1", "the payload names its contract")
        # `FY26 close` and not `FY27 planning`: T6's second snapshot was made on an
        # in-memory store so its timestamp could be doctored, and was deliberately never
        # saved — persisting a back-dated ts to satisfy a later test would put a fiction
        # in the fixture every subsequent check reads.
        eq(payload["profileVersion"], "FY26 close",
           "the profile version is the newest snapshot the FILE holds")
        eq(context_payload(new_store("Fresh"))["profileVersion"], "unreviewed",
           "a never-reviewed store still carries a version a consumer can cite")
        eq(payload["revenue"]["exact"], 412000000.0,
           "revenue travels EXACT — the denominator is the consumer's whole reason to read")
        ok("band" not in json.dumps(payload["revenue"]),
           "and carries no band; rendering is the renderer's problem")
        eq([c["system"] for c in payload["crownJewels"]], ["CRM"], "crown jewels travel")
        # The decided narrowing, one entry per consuming skill (the Phase 5 finding).
        eq(sorted(payload["applicability"]), sorted(QUESTION_SETS),
           "every skill in the question sets gets a decided entry, so none is silently absent")
        eq([r["battery"] for r in payload["applicability"]["incident"]["skipped"]],
           ["sec-item-105"],
           "the decision travels, so a consumer never re-implements §2.2")
        ok("dora-windows" in payload["applicability"]["incident"]["ask"],
           "and the batteries still asked travel beside the skipped ones")
        ok(payload["applicability"]["incident"]["skipped"][0]["sentence"].startswith(
            "SEC Item 1.05 disclosure window — not assessed."),
           "each skip carries its own rendered §2.4 sentence")
        ok("D. Galleyne" in payload["applicability"]["incident"]["skipped"][0]["sentence"],
           "...naming the declarer, so the consumer embeds it rather than rebuilding it")
        # Absence must reach the payload as `ask`, not as a missing entry. A consumer reading
        # `applicability` sees the same thing `applies()` decided, including for a store that
        # has declared nothing at all.
        eq(context_payload(new_store("Fresh"))["applicability"]["incident"]["skipped"], [],
           "an undeclared profile skips nothing in the payload either")
        eq(sorted(context_payload(new_store("Fresh"))["applicability"]["incident"]["ask"]),
           sorted(QUESTION_SETS["incident"]),
           "...and asks every battery, which is §2.2 surviving the transport")
        # A payload that shared structure with the store would let a consumer mutate it.
        # Compared against the LIVE store object, not a fresh load() from disk: a payload
        # that aliased the store would be invisible to a re-read, because nothing was
        # written. The first version of this check did exactly that and passed either way.
        payload["profile"]["listedEntity"] = "tampered"
        payload["crownJewels"].append({"system": "injected"})
        eq(value_of(store["profile"]["listedEntity"]), False,
           "the payload is a copy; a consumer cannot reach back into the store")
        eq([c["system"] for c in store["context"]["crownJewels"]], ["CRM"],
           "and appending to the payload's lists does not append to the store's")
        json.dumps(payload)          # must be serialisable — it travels as a file
        checks[0] += 1

        # --- T10: profile-stale, and nothing else ------------------------------
        fresh = new_store("Never Reviewed Ltd")
        eq(escalations(fresh, "2027-01-01"), [],
           "a store with no review escalates nothing — it is new, not stale")

        st = new_store("Acme")
        review(st, "FY26", "annual review")
        st["snapshots"][-1]["ts"] = "2026-01-15T00:00:00+00:00"
        eq(escalations(st, "2026-06-01"), [],
           "a profile inside its cadence escalates nothing")
        eq(escalations(st, "2027-01-15"), [],
           "and one exactly at the cadence is not yet stale")
        got = escalations(st, "2027-01-16")
        eq([(e["trigger"], e["severity"], e["subjectKind"]) for e in got],
           [("profile-stale", "high", "context")], "one day past it escalates, once")
        eq(sorted(got[0]), ["evidence", "severity", "since", "subjectKind", "subjectRef",
                            "trigger"], "in the six-key CAC-EL-1 shape")
        eq(got[0]["subjectRef"], "Acme", "naming the organisation")
        eq(got[0]["since"], "2026-01-15", "dated from the review, not from today")
        eq(got[0]["evidence"]["baseline"], "FY26", "and citing the snapshot it went stale from")
        ok("not an exposure" in got[0]["evidence"]["detail"],
           "the detail says what kind of thing this is")

        st["settings"]["reviewCadenceDays"] = 90
        ok(escalations(st, "2026-06-01"), "a shorter cadence brings it forward")

        # D-3: one trigger, and the self-test is where that stays true. A second one added
        # without revisiting the decision would show up here.
        triggers = {e["trigger"] for e in escalations(st, "2027-06-01")}
        eq(triggers, {"profile-stale"}, "exactly one trigger ships in v1")
        unattributed = new_store("Bare Co")
        unattributed["profile"]["aiInUse"] = True          # bare, no declaredBy
        review(unattributed, "first", "initial")
        eq(escalations(unattributed, unattributed["snapshots"][-1]["ts"][:10]), [],
           "and an unattributed fact escalates nothing — fact-unattributed is deferred")
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

def _cmd_init(args) -> int:
    if os.path.exists(args.store):
        raise Refusal(
            "%s already exists. `init` refuses rather than overwriting: this file holds the "
            "revenue base, the crown jewels and the board's own words, and there is no "
            "version of losing it that is recoverable from here." % args.store)
    store = new_store(args.org, args.prepared_by, args.scope_note, args.fiscal_year_end)
    if args.fiscal_year_end:
        check_date(args.fiscal_year_end, "--fiscal-year-end")
    save(args.store, store)
    print("Created %s for %s" % (args.store, args.org))
    print("  Nothing is declared yet, and that is the safe state: a consumer with no profile "
          "asks its full question set.")
    print("  Next: declare a flag with --by and --basis, or set-fact a crown jewel.")
    return 0


def _cmd_declare(args) -> int:
    store = load(args.store)
    value, warning = declare_flag(store, args.flag, args.value, args.by, args.basis,
                                  on=args.on or "")
    save(args.store, store)
    print("%s = %r  (declared by %s)" % (args.flag, value, args.by))
    if warning:
        print("  note: %s" % warning)
    return 0


def _cmd_set_fact(args) -> int:
    store = load(args.store)
    wrote = []
    if args.crown_jewel or args.enables or args.at_stake:
        cj = add_crown_jewel(store, args.crown_jewel, args.enables, args.at_stake,
                             by=args.by, basis=args.basis,
                             criticality=args.criticality,
                             depends_on=args.depends_on)
        wrote.append("crown jewel %r — at stake: %s" % (cj["system"], cj["atStake"]))
    if args.board_tolerance:
        add_board_tolerance(store, args.board_tolerance, args.by, on=args.on or "")
        wrote.append("board tolerance, verbatim, attributed to %s" % args.by)
    for flag, key, label in (("segment", "segments", "--segment"),
                             ("goal", "strategicGoals", "--goal"),
                             ("obligation", "obligations", "--obligation")):
        for text in (getattr(args, flag) or []):
            add_listed(store, key, text, label)
            wrote.append("%s %r" % (flag, text.strip()[:48]))
    if not wrote:
        raise Refusal("set-fact needs something to record: --crown-jewel with --enables and "
                      "--at-stake, --board-tolerance, --segment, --goal or --obligation")
    save(args.store, store)
    for line in wrote:
        print("recorded %s" % line)
    return 0


def _cmd_set_revenue(args) -> int:
    store = load(args.store)
    rec = set_revenue(store, args.exact, args.currency, args.fiscal_year,
                      args.by, args.basis)
    save(args.store, store)
    print("revenue %s %s for %s — renders as %s"
          % (rec["currency"], format(int(rec["exact"]), ","), rec["fiscalYear"],
             revenue_band(rec["exact"])))
    print("  The exact figure is stored so the materiality denominator is honest; the band "
          "is what renders, and is derived every time rather than stored.")
    return 0


def _cmd_review(args) -> int:
    store = load(args.store)
    snap = review(store, args.label, args.why)
    save(args.store, store)
    print("snapshot %r — profile and context frozen as they stand" % snap["label"])
    return 0


def _cmd_show(args) -> int:
    store = load(args.store)
    rev = store["context"]["revenue"]
    snap = last_review(store)
    if args.json:
        out = json.loads(json.dumps(store))
        if rev and args.render_revenue == "band":
            out["context"]["revenue"] = {k: v for k, v in rev.items() if k != "exact"}
            out["context"]["revenue"]["band"] = revenue_band(rev["exact"])
        print(json.dumps(out, indent=2, ensure_ascii=False))
        return 0
    print("%s — business context" % (store["meta"]["orgName"] or "(unnamed)"))
    print("  profile version: %s" % (snap["label"] if snap else "unreviewed"))
    if rev:
        if args.render_revenue == "exact":
            print("  revenue: %s %s (%s) — EXACT figure shown by --render-revenue exact"
                  % (rev["currency"], format(int(rev["exact"]), ","), rev["fiscalYear"]))
        else:
            print("  revenue: %s %s (%s)"
                  % (revenue_band(rev["exact"]), rev["currency"], rev["fiscalYear"]))
    unattributed = [k for k, v in store["profile"].items() if not is_attributed(v)]
    print("  declared flags: %d%s" % (len(store["profile"]),
                                      "" if not unattributed
                                      else "  (%d unattributed: %s)"
                                           % (len(unattributed), ", ".join(unattributed))))
    for cj in store["context"]["crownJewels"]:
        print("  crown jewel: %s -> %s" % (cj["system"], cj["atStake"]))
    for seg in store["context"]["segments"]:
        print("  segment: %s" % seg)
    for goal in store["context"]["strategicGoals"]:
        print("  strategic goal: %s" % goal)
    for ob in store["context"]["obligations"]:
        print("  contractual obligation: %s" % ob)
    print_board_tolerance(store)
    return 0


# The read side of the one thing this skill is most often asked out loud: *what did the board
# actually say?* The write side stored the sentence verbatim from the first release, refused an
# unattributed one, and then nothing rendered it — `show` printed the org, the profile version,
# the revenue band and the crown jewels, and the quote was reachable only through `--json`.
#
# That gap is what B4 found. Asked "I want the exact words on file", a session with no read path
# goes looking for a *file*: the working directory, then Drive, then Notion. Adding retrieval
# vocabulary to the description without this would have routed the question here and then
# answered it with a page that does not mention the board.
#
# Absence prints too, and prints loudly. "Nothing recorded" and "the board said nothing" are
# different facts, and the first is the one that can be fixed this afternoon — the same rule
# CAC-AP-1 §2.2 applies to a profile flag, and the same reason `attention-surface` prints
# NOT READ rather than showing a short list.

def print_board_tolerance(store: dict, emit=print) -> int:
    """The board's own words, read back unparaphrased. Returns how many were on file."""
    quotes = store["context"]["boardTolerance"]
    if not quotes:
        emit("  the board's words on tolerance: NONE RECORDED — nobody has written down what "
             "the board said.")
        emit("    That is a different fact from the board having said nothing, and it is not "
             "answered by searching for a document: this register is where the sentence "
             "lives. Ask whoever was in the room and record it with --board-tolerance.")
        return 0
    emit("  the board's words on tolerance (%d), verbatim — this is what is on file:"
         % len(quotes))
    for rec in quotes:
        emit("    “%s”" % rec["quote"])
        emit("      — %s, %s" % (rec["declaredBy"], rec["declaredOn"]))
    return len(quotes)


def _cmd_applies(args) -> int:
    store = load(args.store)
    subject = parse_subject_declares(args.subject_declares)
    res = applies_for(store, args.skill, subject)
    if args.json:
        print(json.dumps({**res, "skill": args.skill,
                          "sentences": [skip_sentence(r) for r in res["skipped"]]},
                         indent=2, ensure_ascii=False))
        return 0
    print("%s — question set for %r" % (store["meta"]["orgName"] or "(unnamed)", args.skill))
    print("  ask (%d):" % len(res["ask"]))
    for battery in res["ask"]:
        print("    - %s" % BATTERY_LABEL.get(battery, battery))
    if not res["skipped"]:
        print("  skipped: none — nothing in the profile narrows this set.")
        return 0
    print("  skipped (%d), each with its reason:" % len(res["skipped"]))
    for rec in res["skipped"]:
        print("    - %s" % skip_sentence(rec))
    return 0


def _cmd_export(args) -> int:
    store = load(args.store)
    payload = context_payload(store)
    text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text)
        print("Wrote %s — profile version %r, %d flags, %d crown jewels"
              % (args.out, payload["profileVersion"], len(payload["profile"]),
                 len(payload["crownJewels"])))
    else:
        sys.stdout.write(text)
    return 0


def _cmd_escalations(args) -> int:
    store = load(args.store)
    recs = escalations(store, args.today or "")
    if args.json:
        print(json.dumps(recs, indent=2, ensure_ascii=False))
        return 0
    if not recs:
        print("Nothing escalated.")
        return 0
    for rec in recs:
        print("%-8s %-14s %s" % (rec["severity"], rec["trigger"], rec["subjectRef"]))
        print("    %s" % rec["evidence"]["detail"])
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="business_context.py",
        description="The organisation's own facts, and what they make applicable.",
        epilog="This tool is not legal advice.",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd")

    sp = sub.add_parser("init", help="create a .biz store")
    sp.add_argument("store")
    sp.add_argument("--org", required=True)
    sp.add_argument("--prepared-by", default="")
    sp.add_argument("--scope-note", default="")
    sp.add_argument("--fiscal-year-end", default="")
    sp.set_defaults(fn=_cmd_init)

    sp = sub.add_parser("declare", help="declare a profile flag, with its basis")
    sp.add_argument("store")
    sp.add_argument("--flag", required=True)
    sp.add_argument("--value", required=True)
    sp.add_argument("--by", default="")
    sp.add_argument("--basis", default="")
    sp.add_argument("--on", default="")
    sp.set_defaults(fn=_cmd_declare)

    sp = sub.add_parser("set-fact", help="record a business fact")
    sp.add_argument("store")
    sp.add_argument("--crown-jewel", default="")
    sp.add_argument("--enables", default="")
    sp.add_argument("--at-stake", default="")
    # Optional, and the key is absent unless given. See add_crown_jewel: this is the top of
    # a criticality walk a consumer runs, not a level this skill knows how to check.
    sp.add_argument("--criticality", default="",
                    help="how critical this system is, in the organisation's own ranking. "
                         "Optional; absent means not declared, never 'not critical'.")
    sp.add_argument("--depends-on", action="append", default=[],
                    help="a component this system relies on. Repeatable. Lets a consumer "
                         "trace from a supplied component back to this system.")
    sp.add_argument("--board-tolerance", default="",
                    help="the board's words, verbatim — never paraphrased on write")
    sp.add_argument("--segment", action="append", default=[])
    sp.add_argument("--goal", action="append", default=[])
    sp.add_argument("--obligation", action="append", default=[])
    sp.add_argument("--by", default="")
    sp.add_argument("--basis", default="")
    sp.add_argument("--on", default="")
    sp.set_defaults(fn=_cmd_set_fact)

    sp = sub.add_parser("set-revenue", help="the revenue base — stored exact, rendered banded")
    sp.add_argument("store")
    sp.add_argument("--exact", default=None)
    sp.add_argument("--currency", default="")
    sp.add_argument("--fiscal-year", default="")
    sp.add_argument("--by", default="")
    sp.add_argument("--basis", default="")
    sp.set_defaults(fn=_cmd_set_revenue)

    sp = sub.add_parser("review", help="snapshot, freezing profile and context")
    sp.add_argument("store")
    sp.add_argument("--label", default="")
    sp.add_argument("--why", default="")
    sp.set_defaults(fn=_cmd_review)

    sp = sub.add_parser("show", help="what this store holds")
    sp.add_argument("store")
    sp.add_argument("--json", action="store_true")
    sp.add_argument("--render-revenue", choices=("band", "exact"), default="band")
    sp.set_defaults(fn=_cmd_show)

    sp = sub.add_parser("applies", help="the question set that applies, and the skips")
    sp.add_argument("store")
    sp.add_argument("--skill", required=True,
                    help="one of: " + ", ".join(sorted(QUESTION_SETS)))
    sp.add_argument("--subject-declares", action="append", default=[], metavar="flag=value",
                    help="the subject's own declaration; outranks the profile (CAC-AP-1 §2.3)")
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(fn=_cmd_applies)

    sp = sub.add_parser("export", help="the payload consumers read via --context")
    sp.add_argument("store")
    sp.add_argument("--context", action="store_true",
                    help="accepted for symmetry with the documented call; the payload is "
                         "the only export this command has")
    sp.add_argument("--out", default="")
    sp.set_defaults(fn=_cmd_export)

    sp = sub.add_parser("escalations", help="what this store raises without being asked")
    sp.add_argument("store")
    sp.add_argument("--today", default="")
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(fn=_cmd_escalations)

    sp = sub.add_parser("self-test", help="verify the engine")
    sp.set_defaults(fn=_cmd_self_test)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    if not getattr(args, "fn", None):
        build_parser().print_help()
        return 2
    try:
        return args.fn(args)
    except Refusal as exc:
        print("refused: %s" % exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
