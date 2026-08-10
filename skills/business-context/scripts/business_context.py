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
               [--criticality '..' --criticality-basis '..']
               [--sensitivity '..' --sensitivity-basis '..']
               <file.biz> --segment '..' | --goal '..' | --obligation '..'
               <file.biz> --board-tolerance '..' --by 'Name' --on YYYY-MM-DD
  set-revenue  <file.biz> --exact 412000000 --currency USD --fiscal-year FY26 --by .. --basis ..
  review       <file.biz> --label 'FY27 planning' --why '...'
  show         <file.biz> [--json] [--render-revenue band|exact]
  archetype    <file.biz> [--json]        depth advice, never scope
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
    """Write the store atomically: a crash mid-write leaves the previous file intact.

    One of ten copies of this pattern, registered as a twin under CAC-TW-1 and compared by
    executing them — `skills/ai-register/scripts/ai_register.py` holds the family list. The
    property compared is the interrupted write, because on the happy path an atomic writer and
    `open(path, "w")` produce identical bytes, which is how two copies stayed non-atomic
    through nine releases with every self-test green (BL-219).
    """
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

# ONE FLAG, ONE FACT — and `one-fact-per-flag.sh` fails the build rather than trusting the
# next reader to notice.
#
# `listedEntity` used to read "shares admitted to trading — the SEC Item 1.05 perimeter".
# Two facts joined by an em dash, and the second one is a mapping in disguise: for twelve
# releases that sentence gated a four-business-day Form 8-K deadline off a listing fact. A
# London-listed plc with no Exchange Act obligation was handed a clock it does not owe; an
# unlisted US issuer reporting under §15(d) was denied one it does. Neither failure is in any
# line of arithmetic. The wrong fact was selected one layer up, in this table, and every
# review passed because nothing here looks like an inference (BL-175).
KNOWN_FLAGS = {
    "listedEntity": "shares admitted to trading on a public exchange",
    # SEPARATELY DECLARED, and never inferred from `listedEntity` in either direction. Item
    # 1.05 reaches registrants subject to Exchange Act reporting: that takes in unlisted
    # §15(d) reporters and leaves out plenty of companies whose shares trade somewhere.
    # Which side of that line an organisation sits on is a securities-law determination, so
    # counsel declares it here for the same reason `incident-materiality` refuses to emit a
    # materiality verdict — a generated answer would be discoverable alongside the filing it
    # disagreed with.
    "secItem105Scope": "required to file current reports on Form 8-K under the Exchange Act",
    "euEntity": "an establishment in the EU",
    "doraScope": "in scope for DORA as a financial entity or critical ICT provider",
    "nydfsScope": "a NYDFS Part 500 covered entity",
    # The companion to `nydfsScope`, and a SEPARATE FACT from it: an entity can be a covered
    # entity and still be exempt from most of the Part. Records WHICH LIMB of 23 NYCRR
    # §500.19 counsel says applies — `500.19(a)`, `500.19(c)`, `500.19(g)`, or `none` — because
    # the limbs reach different sections and a bare yes/no could not say which (BL-188).
    #
    # It GATES NOTHING, deliberately. §500.19 exempts section by section: (a) reaches §500.15
    # and not §500.12, (c) and (d) reach both, and only (b), (e) and (g) reach the whole Part
    # including §500.17. The applicability engine gates whole batteries, so mapping a
    # section-level exemption onto a battery gate would either overstate it — dropping the
    # notification question for a firm that still owes it — or understate it to the point of
    # being decorative. `nydfs-notification` stays gated on `nydfsScope` alone; this flag is
    # read by the exceptions register and the board receipts, which speak at section level.
    #
    # NEVER COMPUTED. The tests read like arithmetic — a headcount, a revenue figure, an asset
    # total — and that is the trap: affiliate aggregation, what counts as operating under a
    # license, and whether an entity "otherwise qualifies as a covered entity" are legal
    # determinations. Same rule as `secItem105Scope`, same reason.
    "nydfsExemption": "the declared NYDFS Part 500 section 500.19 exemption limb, if any",
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
                    depends_on=None, sensitivity: str = "",
                    sensitivity_basis: str = "",
                    criticality_basis: str = "") -> dict:
    """Record a system the business cannot lose, and optionally how critical and how sensitive.

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

    SENSITIVITY IS A DIFFERENT QUESTION FROM CRITICALITY, which is why it is a second field
    and not a second word for the first. Criticality is *how much the business depends on
    this* — what stops when it stops. Sensitivity is *what it holds* — the consequence of the
    contents being seen rather than of the system being gone. A payroll file nobody's day
    depends on can be the most sensitive thing in the estate, and a build server everything
    depends on can hold nothing worth reading. Collapsing them makes one of those two systems
    invisible, and which one depends only on which word the register happened to use.

    Free text with a REQUIRED basis, decided 2026-08-09 (BL-216 Q-1). No scale, for the same
    reason criticality has none — the organisation's own classification scheme is the answer,
    and imposing `low/moderate/high` here would make this skill the author of a data
    classification policy it has no business writing. The basis is what makes free text
    defensible: `--sensitivity 'Special category under UK GDPR Art. 9'` with a basis naming
    who determined that and from what is a record an assessor can follow. The same words with
    no basis is an adjective.

    Stored through `declared()`, so the value carries its own `declaredBy`, `declaredOn` and
    `basis`, rather than leaning on the record-level `basis` — which answers a different
    question again, namely why this system is a crown jewel at all.

    CRITICALITY IS WRITTEN AS A `declared()` RECORD TOO, since v0.74.0, and carries its own
    REQUIRED basis for the same reason sensitivity does — the record-level `basis` answers
    why this system is a crown jewel at all, which is a different question from why it was
    ranked where it was. A level with no basis is the thing a vendor criticality walk will
    later hand to a board.

    ⚠️ TWO SHAPES LIVE ON DISK, INDEFINITELY, AND THAT IS THE DECISION — NOT DRIFT.
    A `.biz` written before v0.74.0 holds `criticality` as a bare string; one written after
    holds a `declared()` record. Both are legal, both stay legal, and nothing converts.

    That was decided deliberately (BL-216 Q-2, 2026-08-10) against the cleaner alternative of
    bumping `SCHEMA_VERSION` and refusing the old shape. BL-169 D-2 says stopping part-way
    must leave a loadable store; a product whose argument is *your records persist and stay
    defensible* does not ship a version bump that refuses a CISO's file. The polymorphism is
    affordable because there is exactly ONE read point per consuming skill —
    `declared_criticality()` in `vendor-register` and `ai-register`, which reads either shape
    and refuses everything else. It is guarded by `evals/criticality-shapes.sh`, whose two
    halves fail if either branch is removed.

    **Do not "fix" this by forcing one shape.** Forcing the record shape is the breaking read
    this decision declined; forcing the bare string throws away the basis. The asymmetry
    against `sensitivity` — which has no bare-string legacy and therefore only ever had one
    shape — is a fact about when each field was introduced, not an inconsistency to resolve.
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
    crit, crit_basis = str(criticality or "").strip(), str(criticality_basis or "").strip()
    if crit and not crit_basis:
        raise Refusal(
            "declaring --criticality %r requires --criticality-basis.\n"
            "  This skill validates no scale — a consumer that owns one checks the value, "
            "and this level is the top of a criticality walk that ends on a board page. The "
            "basis is what a reader follows back: who ranked it there, and against what. "
            "The record-level --basis answers why this is a crown jewel at all, which is a "
            "different question." % crit)
    if crit_basis and not crit:
        raise Refusal(
            "--criticality-basis was given with no --criticality. A basis for nothing is "
            "not a record; say what was ranked, or leave both off.")
    sens, sens_basis = str(sensitivity or "").strip(), str(sensitivity_basis or "").strip()
    if sens and not sens_basis:
        raise Refusal(
            "declaring --sensitivity %r requires --sensitivity-basis.\n"
            "  There is no scale here: sensitivity is whatever the organisation's own "
            "classification says, so the words alone carry no meaning a reader can check. "
            "The basis is what a determination is made of — who decided, and from what. "
            "Without it this is an adjective on a record an assessor is entitled to follow."
            % sens)
    if sens_basis and not sens:
        raise Refusal(
            "--sensitivity-basis was given with no --sensitivity. A basis for nothing is "
            "not a record; say what was determined, or leave both off.")
    rec = {"system": system.strip(), "enables": enables.strip(),
           "atStake": at_stake.strip(),
           "declaredBy": str(by or "").strip(), "declaredOn": utc_today(),
           "basis": str(basis or "").strip()}
    if crit:
        rec["criticality"] = declared(crit, str(by or "").strip(), utc_today(), crit_basis)
    if sens:
        rec["sensitivity"] = declared(sens, str(by or "").strip(), utc_today(), sens_basis)
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



# --- The archetype layer: depth, never scope ----------------------------------
#
# A release test held sector, jurisdictions, regulatory scope, AI, OT, data, cloud, vendors and
# concentration constant, moved ONLY revenue (USD 5m -> USD 50bn) and headcount (1-50 ->
# 100,000+), and got byte-for-byte identical applicability objects back.
#
# That is correct and must stay correct. **Size does not create a legal obligation.** A
# Fortune 100 and an SMB with the same declared facts owe the same duties, and a profile that
# invented an exemption for a small company would be doing precisely what CAC-AP-1 exists to
# stop.
#
# But it did mean the toolkit had nothing to say about size at all, and size genuinely changes
# how much assurance is proportionate. So: a second, explicitly NON-REGULATORY layer. It reads
# only declared size facts, returns advice about DEPTH — evidence, cadence, role separation,
# metrics breadth, third-party coverage, AI governance, pack density — and travels in its own
# payload key. `archetype-advisory.sh` asserts it never reaches the applicability decision.
#
# §2.2 applies to it in its own register: no size declared means `undeclared`, which recommends
# the FULL depth. A tool that read a missing revenue figure as "probably small" would recommend
# a thin programme to whoever had not got round to filling in the form.

ARCHETYPE_ORDER = ("undeclared", "small", "midmarket", "large", "enterprise")


def archetypes_path() -> str:
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "references", "archetypes.json")


def load_archetypes(path: str = "") -> dict:
    """The dataset, refusing one that could not do its job."""
    try:
        with open(path or archetypes_path(), encoding="utf-8") as fh:
            data = json.load(fh)
    except FileNotFoundError:
        raise Refusal("no archetype dataset at %s" % (path or archetypes_path()))
    except ValueError as exc:
        raise Refusal("the archetype dataset is not valid JSON: %s" % exc)
    by_id = {a["id"]: a for a in (data.get("archetypes") or []) if a.get("id")}
    missing = [k for k in ARCHETYPE_ORDER if k not in by_id]
    if missing:
        raise Refusal("the archetype dataset is missing %s — a broken dataset would return "
                      "advice for a band nobody defined" % ", ".join(missing))
    data["byId"] = by_id
    return data


def _band_from(value, table: dict) -> str:
    """Which archetype a declared band string falls in, or "" for unrecognised.

    Unrecognised contributes NOTHING rather than being coerced. `headcountBand` is a free
    declaration, not an enum — this skill owns no org-size scale any more than it owns a
    criticality scale — and guessing which end of the ladder an unfamiliar string belongs on
    is exactly the inference the suite refuses everywhere else.
    """
    text = str(value or "").strip().lower()
    if not text:
        return ""
    for name in ARCHETYPE_ORDER[1:]:
        if any(text == str(v).strip().lower() for v in table.get(name) or []):
            return name
    return ""


def declared_headcount(store: dict):
    """The headcount band as declared, whichever shape the flag was written in."""
    raw = (store.get("profile") or {}).get("headcountBand")
    if isinstance(raw, dict):
        return raw.get("value")
    return raw


def archetype_for(store: dict, data: dict = None) -> dict:
    """The depth advice for this organisation's declared size. Never its scope.

    The HIGHER of the two declared bands wins. A 40-person company turning over USD 2bn is not
    a small organisation, and neither is a 30,000-person company on thin margins — so taking
    the higher band lets an unusual size fact raise the recommended depth instead of averaging
    away against the other one.
    """
    data = data or load_archetypes()
    rev = store["context"].get("revenue")
    from_revenue = _band_from(revenue_band(rev["exact"]) if rev else "",
                              data.get("revenueBands") or {})
    from_headcount = _band_from(declared_headcount(store),
                                data.get("headcountBands") or {})
    seen = [b for b in (from_revenue, from_headcount) if b]
    chosen = max(seen, key=ARCHETYPE_ORDER.index) if seen else "undeclared"
    entry = dict(data["byId"][chosen])
    entry["basis"] = {
        "fromRevenue": from_revenue or None,
        "fromHeadcount": from_headcount or None,
        "rule": ("the higher of the two declared bands" if len(seen) == 2
                 else "the one size fact on record" if len(seen) == 1
                 else "nothing declared, so the full depth is recommended — absence asks "
                      "more, exactly as it does for a profile flag"),
    }
    entry["appliesTo"] = "depth of assurance only"
    entry["neverAffects"] = ["applicability", "materiality", "any question set"]
    return entry


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
        # NOT `listedEntity` — see the KNOWN_FLAGS comment and BL-175. The gate is the
        # Exchange Act reporting obligation, declared by counsel; a listing is neither
        # necessary nor sufficient for it.
        "sec-item-105": "secItem105Scope",
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


def undeclared_record(battery: str, flag: str, field=None) -> dict:
    """One battery that is asked BECAUSE nobody has declared its gate (CAC-AP-1 §2.4.1).

    §2.2 already says absence asks. What it never said is that the asking leaves a trace, and
    that omission is the whole of BL-175: a battery asked on a declaration and a battery asked
    on silence arrive at the consumer as the same entry in the same list, so a consumer that
    computes something from "asked" cannot tell whether anybody said it applied.

    For a question set that costs a few minutes, the two really are the same. For a statutory
    filing deadline they are not, and decision AP-2 settles which way: ask the battery,
    withhold the date. This record is what makes the second half expressible at all.

    `source` distinguishes a flag NOBODY ENTERED (`absent`) from one somebody entered as
    "we do not know yet" (`profile`, carrying its declarer, date and basis). Both are
    not-declared and both ask; only the second has a person attached, and a reader chasing
    the gap needs to know whether there is anyone to chase.
    """
    rec = {"battery": battery, "label": BATTERY_LABEL.get(battery, battery),
           "flag": flag, "source": "profile" if isinstance(field, dict) else "absent",
           "declaredBy": "", "declaredOn": "", "basis": ""}
    if isinstance(field, dict):
        rec["declaredBy"] = str(field.get("declaredBy") or "")
        rec["declaredOn"] = str(field.get("declaredOn") or "")
        rec["basis"] = str(field.get("basis") or "")
    rec["sentence"] = undeclared_sentence(rec)
    return rec


def undeclared_sentence(rec: dict) -> str:
    """The §2.4.1 sentence, and it must not read like the §2.4 one.

    *No answer because nobody said* and *no answer because somebody said no* are different
    facts, and AP-2 is explicit that a reader must never have to work out which one they are
    looking at. So this sentence never contains the word "not assessed" — the battery WAS
    assessed — and it always names the flag that would settle it, because the reader's next
    action is to go and get that declaration.
    """
    label = rec.get("label") or rec.get("battery")
    flag = rec.get("flag")
    if rec.get("source") == "profile":
        who = rec.get("declaredBy") or "an unattributed entry"
        when = rec.get("declaredOn")
        attribution = ("recorded %s by %s" % (when, who)) if when else ("recorded by %s" % who)
        basis = str(rec.get("basis") or "").strip()
        tail = (" — %s" % (basis if basis.endswith((".", "!", "?")) else basis + ".")
                ) if basis else "."
        return ("%s — asked in full. Organisation profile: `%s` is recorded with no value, "
                "%s, so scope has not been declared either way%s"
                % (label, flag, attribution, tail))
    return ("%s — asked in full. Organisation profile: `%s` is not declared. Nobody has said "
            "whether this applies, which is not the same as saying it does not (CAC-AP-1 "
            "§2.2), so the battery is asked and nothing is inferred from the silence."
            % (label, flag))


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

    Returns {"ask": [...], "skipped": [ {...}, ... ], "undeclared": [ {...}, ... ]}.

    `undeclared` is a SUBSET OF `ask`, never a third alternative to it — §2.2 is unchanged
    and absence still asks everything. It says which of those questions are being asked
    because nobody has declared the gate, so a consumer that would otherwise compute
    something off `ask` can tell a declared yes from a silence. See `undeclared_record`.
    """
    profile = profile or {}
    subject = subject or {}
    ask, skipped, undeclared = [], [], []
    for battery, gate in question_sets.items():
        # §2.3 first: the subject outranks the profile, in both directions. A subject
        # declaration settles the gate, so a battery reaching here is never `undeclared`
        # regardless of what the profile is missing.
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
            undeclared.append(undeclared_record(battery, gate, field=field))
        elif declared_value:
            ask.append(battery)
        else:
            skipped.append(skip_record(battery, gate, "profile", field=field))
    return {"ask": sorted(ask), "skipped": sorted(skipped, key=lambda r: r["battery"]),
            "undeclared": sorted(undeclared, key=lambda r: r["battery"])}


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
    # `listed` still means `listedEntity` and deliberately does NOT reach the SEC gate: the
    # short form of the wrong flag is how the conflation would come back. `sec` is its own
    # alias because the flag it names is its own fact (BL-175).
    aliases = {"ai": "aiInUse", "listed": "listedEntity", "dora": "doraScope",
               "sec": "secItem105Scope", "nydfs": "nydfsScope", "ot": "otPresent",
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
        # ADVICE, in its own key, deliberately outside `applicability` rather than inside it.
        # A consumer that read this as scope would be inventing an exemption for a small
        # company, which is the one thing CAC-AP-1 exists to prevent. `archetype-advisory.sh`
        # asserts the two never touch, and asserts that moving ONLY the size facts leaves
        # every applicability decision byte-identical.
        "archetype": archetype_for(store),
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
        store = new_store("Acme Manufacturing", "R. Calder")
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
        refuses(lambda: declare_flag(store, "aiInUse", True, "R. Calder", ""),
                "a flag with no --basis is refused", "requires --basis")
        refuses(lambda: declare_flag(store, "aiInUse", True, "", "a reason"),
                "a flag with no --by is refused", "requires --by")
        refuses(lambda: declare_flag(store, "", True, "D", "b"), "a flag with no name")
        eq(open(path, "rb").read(), before,
           "and every refusal leaves the file byte-identical")

        n_hist = len(store["history"])
        val, warn = declare_flag(store, "aiInUse", "true", "R. Calder",
                                 "Legal ops deployed a contract-review assistant in May")
        eq(val, True, "'true' from a shell is the boolean True")
        eq(warn, "", "a documented flag warns about nothing")
        eq(len(store["history"]) - n_hist, 1, "a valid declare appends exactly one entry")
        eq(store["history"][-1]["detail"]["declaredBy"], "R. Calder",
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

        _, warn = declare_flag(store, "quantumReadiness", "false", "R. Calder",
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
                             by="R. Calder", basis="FY26 planning review")
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
        scratch = new_store("Scratch Ltd", "R. Calder")
        # A level with no basis is refused, both directions, exactly as sensitivity is. The
        # record-level `basis` answers why this is a crown jewel at all; this one answers who
        # ranked it there and against what, and it is the question a board page raises.
        refuses(lambda: add_crown_jewel(scratch, "Plant historian", "x", "y",
                                        criticality="high"),
                "a criticality with no basis is refused", "criticality-basis")
        refuses(lambda: add_crown_jewel(scratch, "Plant historian", "x", "y",
                                        criticality_basis="board minute"),
                "a criticality basis with nothing ranked is refused", "basis for nothing")
        rated = add_crown_jewel(scratch, "Plant historian", "production scheduling",
                                "a day of lost output", by="Head of Engineering",
                                criticality="high",
                                criticality_basis="FY26 business impact analysis",
                                depends_on=["SCADA gateway", " "])
        eq(rated["criticality"]["value"], "high", "a declared level is recorded as given")
        eq(rated["criticality"]["basis"], "FY26 business impact analysis",
           "and carries its own basis, not the record's")
        eq(rated["criticality"]["declaredBy"], "Head of Engineering", "and who ranked it")
        eq(rated["dependsOn"], ["SCADA gateway"],
           "and blank dependencies are dropped rather than stored as empty rows")
        # No scale is checked here on purpose: this skill does not own one, and validating
        # would mean deciding what a criticality level is allowed to be for everybody.
        odd = add_crown_jewel(scratch, "Ledger", "statutory reporting", "the audit opinion",
                              criticality="tier-0", criticality_basis="our own tiering")
        eq(odd["criticality"]["value"], "tier-0",
           "an organisation's own ranking is recorded, not corrected against a scale")
        eq([c["system"] for c in context_payload(scratch)["crownJewels"]
            if c.get("criticality")], ["Plant historian", "Ledger"],
           "and a declared level travels in the CAC-AP-1 payload")

        # --- sensitivity: what it HOLDS, not what stops when it stops ------------
        # A second field and not a second word for criticality. A payroll file nobody's day
        # depends on can be the most sensitive thing in the estate; collapsing the two makes
        # one of those systems invisible, and which one depends only on the word chosen.
        ok("sensitivity" not in cj,
           "a crown jewel with no sensitivity declared carries no key, not an empty one")
        refuses(lambda: add_crown_jewel(scratch, "HR file", "payroll", "a reportable breach",
                                        sensitivity="Special category, UK GDPR Art. 9"),
                "sensitivity without a basis is refused", "adjective")
        refuses(lambda: add_crown_jewel(scratch, "HR file", "payroll", "a reportable breach",
                                        sensitivity_basis="DPO assessment, 2026-07-01"),
                "a basis with nothing determined is refused", "basis for nothing")
        sens = add_crown_jewel(scratch, "HR file", "payroll", "a reportable breach",
                               by="DPO", sensitivity="Special category, UK GDPR Art. 9",
                               sensitivity_basis="DPO record-of-processing review 2026-07-01")
        eq(sens["sensitivity"]["value"], "Special category, UK GDPR Art. 9",
           "a declared sensitivity is recorded verbatim, with no scale imposed")
        eq(sens["sensitivity"]["basis"], "DPO record-of-processing review 2026-07-01",
           "and carries its own basis, not the record's")
        eq(sens["sensitivity"]["declaredBy"], "DPO", "and who determined it")
        ok("criticality" not in sens,
           "sensitivity and criticality are independent — declaring one declares nothing "
           "about the other")
        # Both attributes are now `declared()` records on write. The bare-string shape is not
        # gone — it is what every `.biz` written before v0.74.0 holds, and BL-216 Q-2 decided
        # those keep loading rather than being converted or refused. This engine only ever
        # WRITES the record; the two consuming skills READ both, guarded by
        # evals/criticality-shapes.sh.
        ok(isinstance(rated["criticality"], dict)
           and isinstance(sens["sensitivity"], dict),
           "both attributes are written as declared records, each with its own basis")
        # And the promise the decision rests on, proved rather than asserted: a store written
        # in the pre-v0.74.0 shape LOADS, and comes back with its bare string intact. If a
        # converter or a schema bump ever creeps in, this is the check that fails.
        legacy = new_store("Legacy Ltd", "R. Calder")
        legacy["context"]["crownJewels"].append(
            {"system": "CRM", "enables": "renewals", "atStake": "the client data",
             "criticality": "high"})
        legacy_path = os.path.join(os.path.dirname(path), "legacy.biz")
        save(legacy_path, legacy)
        eq(load(legacy_path)["context"]["crownJewels"][0]["criticality"], "high",
           "a store written before v0.74.0 loads, and its bare string is not converted")

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

        # --- the archetype layer: depth, never scope -----------------------------
        # The one rule most likely to be broken by someone being helpful: a store with no
        # size declared must get the FULL depth, not the smallest band. See
        # evals/archetype-advisory.sh for the A/B that keeps it out of applicability.
        bare = archetype_for(new_store("Nobody Ltd"))
        eq(bare["id"], "undeclared", "no size declared yields `undeclared`, never `small`")
        ok("absence asks" in bare["basis"]["rule"],
           "...and says why, in the words CAC-AP-1 uses for a missing flag")
        ok(bool(bare["evidenceDepth"] and bare["thirdPartyCoverage"]),
           "...carrying real advice rather than an empty band")
        eq(archetype_for(new_store("X"))["appliesTo"], "depth of assurance only",
           "every archetype states what it is for")
        big = new_store("Odd Ltd")
        set_revenue(big, exact=2e9, currency="USD", fiscal_year="FY26", by="C", basis="b")
        declare_flag(big, "headcountBand", "1-50", by="D", basis="b")
        eq(archetype_for(big)["id"], "large",
           "the higher of two declared bands wins, so an unusual size fact raises depth")
        odd = new_store("Weird Ltd")
        declare_flag(odd, "headcountBand", "a few hundred-ish", by="D", basis="b")
        eq(archetype_for(odd)["basis"]["fromHeadcount"], None,
           "an unrecognised band contributes nothing rather than being coerced")

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
        #
        # The gate is `secItem105Scope`, the real one, not a stand-in. A contract test
        # written against a flag the shipped question set does not use would keep passing
        # through exactly the repointing this section exists to protect (BL-175).
        QS = {"sec-item-105": "secItem105Scope", "dora-windows": "doraScope"}

        # 1. Empty profile -> EVERY battery asked, nothing skipped. Absence asks more.
        got = applies({}, QS)
        eq(got["ask"], ["dora-windows", "sec-item-105"], "an empty profile asks everything")
        eq(got["skipped"], [], "and skips nothing")
        eq([r["battery"] for r in got["undeclared"]], ["dora-windows", "sec-item-105"],
           "and every one of those asks is recorded as resting on a silence, not an answer")

        # 2. Flag present but value None -> still asked. `None` is not-declared, and a
        #    wrapper with a null value is exactly how a half-filled form arrives.
        got = applies({"secItem105Scope": declared(None, "D. G.", "2026-01-01", "unknown")},
                      QS)
        ok("sec-item-105" in got["ask"],
           "a flag declared with a null value asks, rather than narrowing")
        eq(got["skipped"], [], "and is not recorded as a skip")
        # ...but it IS recorded as undeclared, and with its declarer, because somebody
        # entered "we do not know yet" and there is a person to go back to.
        und = [r for r in got["undeclared"] if r["battery"] == "sec-item-105"][0]
        eq((und["source"], und["declaredBy"]), ("profile", "D. G."),
           "a recorded null carries who recorded it, unlike a flag nobody ever entered")
        eq([r["source"] for r in applies({}, QS)["undeclared"]], ["absent", "absent"],
           "while a flag nobody entered is `absent`, and has nobody attached to chase")

        # The same, unwrapped: a bare None in the profile is not-declared too.
        eq(applies({"secItem105Scope": None}, QS)["ask"],
           ["dora-windows", "sec-item-105"], "a bare null flag asks as well")

        # 3. Flag false -> skipped, WITH its provenance. §2.4: an auditor must be able to
        #    tell a question correctly out of scope from one nobody asked.
        prof = {"secItem105Scope": declared(False, "R. Calder", "2026-07-14",
                                            "No class of securities registered under the "
                                            "Exchange Act; no s.15(d) obligation")}
        got = applies(prof, QS)
        eq(got["ask"], ["dora-windows"], "a false flag removes its battery")
        eq([r["battery"] for r in got["skipped"]], ["sec-item-105"], "and records the skip")
        eq([r["battery"] for r in got["undeclared"]], ["dora-windows"],
           "a skipped battery is not also undeclared — it was answered, with a no")
        rec = got["skipped"][0]
        eq(rec["declaredBy"], "R. Calder", "the skip carries who declared it")
        eq(rec["declaredOn"], "2026-07-14", "and when")
        ok(rec["basis"].startswith("No class of securities"), "and on what basis")
        sentence = skip_sentence(rec)
        for needle in ("secItem105Scope", "2026-07-14", "R. Calder", "not assessed"):
            ok(needle in sentence, "the rendered skip names %s" % needle)

        # AP-2's third row, and the reason this whole section grew a list. `not assessed`
        # and `asked with nothing declared` must not read alike, because a reader who cannot
        # tell them apart cannot tell a settled no from an unanswered question — and one of
        # those is the London-listed non-registrant that gets no 8-K clock.
        u_sent = applies({}, QS)["undeclared"][1]["sentence"]
        ok("not assessed" not in u_sent,
           "the undeclared sentence never says `not assessed` — the battery WAS assessed")
        for needle in ("secItem105Scope", "asked in full", "not declared"):
            ok(needle in u_sent, "and it names %s" % needle)

        # 4. Flag false AND the subject declares true -> ASKED. This is the design's
        #    vendor-with-AI case: the org declared no AI, this vendor processes data with a
        #    model, and the assessor in front of the evidence outranks the profile.
        got = applies(prof, QS, subject={"secItem105Scope": True})
        ok("sec-item-105" in got["ask"],
           "a subject declaring true re-adds a battery the profile removed")
        eq(got["skipped"], [], "and nothing is skipped")
        eq([r["battery"] for r in got["undeclared"]], ["dora-windows"],
           "and the re-added battery is NOT undeclared: the subject declared it")

        # 5. Flag true AND the subject declares false -> skipped, naming the SUBJECT.
        #    The override runs in both directions or it is not an override.
        got = applies({"secItem105Scope": declared(True, "D. G.", "2026-01-01", "registrant")},
                      QS, subject={"secItem105Scope": False})
        eq(got["ask"], ["dora-windows"], "a subject declaring false removes it")
        eq(got["skipped"][0]["source"], "subject", "and the skip names the subject")
        ok("overrides the organisation profile" in skip_sentence(got["skipped"][0]),
           "which the rendered sentence says in as many words")

        # A subject declaring TRUE over a profile silence settles the gate. Without this the
        # subject layer could re-add a battery and leave it marked undeclared, and the
        # consumer would withhold a deadline the assessor had just declared into existence.
        got = applies({}, QS, subject={"secItem105Scope": True})
        eq([r["battery"] for r in got["undeclared"]], ["dora-windows"],
           "a subject declaration settles a gate the profile left silent")

        # A subject that declares None says nothing, and falls through to the profile
        # rather than being read as False.
        got = applies(prof, QS, subject={"secItem105Scope": None})
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
            eq(applies({"secItem105Scope": empty}, QS)["skipped"], [],
               "not-declared (%r) never narrows" % (empty,))
            eq([r["battery"] for r in applies({"secItem105Scope": empty}, QS)["undeclared"]],
               ["dora-windows", "sec-item-105"],
               "and not-declared (%r) is recorded as such" % (empty,))
        eq([r["battery"] for r in applies({"secItem105Scope": False}, QS)["skipped"]],
           ["sec-item-105"], "while a bare False does narrow")
        eq([r["battery"] for r in applies({"secItem105Scope": declared(False)}, QS)["skipped"]],
           ["sec-item-105"], "as does a wrapped False")

        # Every battery is accounted for: asked or skipped, never dropped. And `undeclared`
        # is a SUBSET of `ask`, never a third bucket beside it — a consumer that iterated
        # `ask` and got a short list would be narrowing on absence, which is §2.2 inverted.
        for prof2 in ({}, prof,
                      {"secItem105Scope": declared(False), "doraScope": declared(False)}):
            r = applies(prof2, QS)
            eq(sorted(r["ask"] + [x["battery"] for x in r["skipped"]]), sorted(QS),
               "every battery is either asked or skipped, for profile %r" % (prof2,))
            ok(all(x["battery"] in r["ask"] for x in r["undeclared"]),
               "and every undeclared battery is one of the asked ones, for %r" % (prof2,))

        # --- T8: the CLI surface ----------------------------------------------
        store = load(path)
        # The worked store needs a false flag for the narrowing below to be real rather
        # than a lucky absence — absence asks everything, so a store with nothing declared
        # would "pass" a narrowing test by never narrowing.
        declare_flag(store, "listedEntity", "false", "R. Calder",
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
        # Every gate is a documented flag. An undocumented gate would narrow a question set
        # off a field no reader of KNOWN_FLAGS could find, which is the BL-175 shape with the
        # documentation missing rather than wrong.
        for skill, sets in QUESTION_SETS.items():
            for battery, gate in sets.items():
                ok(gate in KNOWN_FLAGS, "%s is gated on a documented flag (%s)"
                   % (battery, gate))
        # `nydfsExemption` DOES NOT GATE, and that is a decision rather than an oversight
        # (BL-188). §500.19 exempts section by section — (a) reaches §500.15 and not §500.12,
        # (c) and (d) reach both, only (b)/(e)/(g) reach the whole Part including §500.17 —
        # and this engine gates whole batteries. Wiring it to `nydfs-notification` would drop
        # the notification question for firms that still owe it. Asserted here because the
        # obvious "improvement" is to wire it up, and it would be silent.
        ok("nydfsExemption" in KNOWN_FLAGS, "the §500.19 exemption limb is a documented flag")
        eq([b for s in QUESTION_SETS.values() for b, g in s.items()
            if g == "nydfsExemption"], [],
           "...and it gates no battery: a section-level exemption cannot gate a whole one")
        eq(QUESTION_SETS["incident"]["nydfs-notification"], "nydfsScope",
           "the notification battery is still gated on covered-entity status alone")
        eq(parse_subject_declares(["ai=true"]), {"aiInUse": True}, "the ai alias resolves")
        eq(parse_subject_declares(["listedEntity=false"]), {"listedEntity": False},
           "and a full flag name passes through")
        refuses(lambda: parse_subject_declares(["ai"]), "a malformed subject declaration")

        eq(parse_subject_declares(["sec=true"]), {"secItem105Scope": True},
           "the sec alias resolves to the Exchange Act flag")
        eq(parse_subject_declares(["listed=true"]), {"listedEntity": True},
           "and `listed` still means the listing fact, which no longer gates the SEC battery")

        # THE MIGRATION, asserted on the unmodified fixture (BL-175 T3).
        #
        # This store declares `listedEntity: false` and nothing about SEC scope — which is
        # every store written before this change. Under the old mapping it SKIPPED the SEC
        # battery, and the skip sentence quoted the declarer and the date, so it read as a
        # settled legal answer. It was not one: the same shape is an unlisted issuer
        # reporting under Exchange Act s.15(d), which is squarely inside Item 1.05 and was
        # being silently dropped.
        #
        # No migration code runs. The rule does the work: SEC scope is undeclared here, and
        # undeclared asks.
        res = applies_for(store, "incident")
        ok("sec-item-105" in res["ask"],
           "a store carrying only listedEntity now ASKS the SEC battery rather than "
           "skipping it — the s.15(d) suppression closes without a migration step")
        eq([r["battery"] for r in res["skipped"]], [],
           "and the false listing flag narrows nothing, because it never gated this")
        u = [r for r in res["undeclared"] if r["battery"] == "sec-item-105"][0]
        ok("secItem105Scope" in u["sentence"],
           "...and the reason names the flag that would settle it")
        ok("dora-windows" in res["ask"],
           "while doraScope, declared true later, is still asked")

        # Now declare SEC scope false, so the rest of this file exercises a real narrowing
        # rather than the absence above.
        declare_flag(store, "secItem105Scope", "false", "R. Calder",
                     "No registered class and no s.15(d) obligation; confirmed by counsel")
        save(path, store)
        store = load(path)

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
        ok("R. Calder" in payload["applicability"]["incident"]["skipped"][0]["sentence"],
           "...naming the declarer, so the consumer embeds it rather than rebuilding it")
        # §2.4.1 travels too, or the consumer re-derives it from the raw flags —
        # which is the re-implementation §2.2 already forbids, one clause along.
        eq([r["battery"] for r in payload["applicability"]["incident"]["undeclared"]],
           ["nydfs-notification"],
           "the undeclared batteries travel beside the asked and the skipped")
        eq(sorted(payload["applicability"]["posture"]["undeclared"][0]),
           ["basis", "battery", "declaredBy", "declaredOn", "flag", "label", "sentence",
            "source"],
           "in a fixed shape a consumer can rely on")
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
                             criticality_basis=args.criticality_basis,
                             depends_on=args.depends_on,
                             sensitivity=args.sensitivity,
                             sensitivity_basis=args.sensitivity_basis)
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


def _cmd_archetype(args) -> int:
    store = load(args.store)
    a = archetype_for(store)
    if args.json:
        print(json.dumps(a, indent=2, ensure_ascii=False))
        return 0
    print("%s — %s" % (store["meta"]["orgName"] or "(unnamed)", a["title"]))
    print("  %s" % a["meaning"])
    print("  basis: %s (revenue: %s; headcount: %s)"
          % (a["basis"]["rule"], a["basis"]["fromRevenue"] or "not declared",
             a["basis"]["fromHeadcount"] or "not declared"))
    print()
    for key, label in (("evidenceDepth", "evidence"), ("reviewCadence", "cadence"),
                       ("roleSeparation", "roles"), ("metricsBreadth", "metrics"),
                       ("thirdPartyCoverage", "third parties"),
                       ("aiGovernanceDepth", "AI"), ("boardPackDensity", "board pack")):
        if a.get(key):
            print("  %-14s %s" % (label + ":", a[key]))
    for key in ("watchFor", "whyNotSmallest"):
        if a.get(key):
            print("\n  %s" % a[key])
    print("\n  This is ADVICE ABOUT DEPTH and nothing else. It changes no question set, no "
          "regulatory\n  scope and no materiality threshold: two organisations with the same "
          "declared facts owe\n  the same duties whatever their size. Run `applies` for what "
          "actually applies to you.")
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
                         "Optional; absent means not declared, never 'not critical'. "
                         "Requires --criticality-basis.")
    sp.add_argument("--criticality-basis", default="",
                    help="who ranked it there and against what. Required whenever "
                         "--criticality is given: no scale is validated here, so the basis "
                         "is the only thing a reader can follow back.")
    sp.add_argument("--depends-on", action="append", default=[],
                    help="a component this system relies on. Repeatable. Lets a consumer "
                         "trace from a supplied component back to this system.")
    # A different question from criticality: what it HOLDS, not what stops when it stops.
    # Free text with a required basis (BL-216 Q-1) — no scale, because the organisation's own
    # classification is the answer and this skill does not write one.
    sp.add_argument("--sensitivity", default="",
                    help="what this system holds, in the organisation's own classification "
                         "— a different question from how much depends on it. Free text. "
                         "Requires --sensitivity-basis.")
    sp.add_argument("--sensitivity-basis", default="",
                    help="who determined that sensitivity and from what. Required whenever "
                         "--sensitivity is given: without it the value is an adjective.")
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

    sp = sub.add_parser("archetype",
                        help="depth advice for the declared size — never scope")
    sp.add_argument("store")
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(fn=_cmd_archetype)

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
