#!/usr/bin/env python3
"""metrics_analysis.py — deterministic engine for the metrics-register skill.

A system of record for board metrics over time. The other two stateful skills in this
toolkit were parity ports of a web engine; this one is greenfield, so the golden fixture
is authored here rather than inherited, and every expectation in `self-test` was worked
out by hand before the code that satisfies it.

What the engine owns:
  - the `.mtr` store: metric definitions, an append-only reading history, a change log
  - direction-aware derivations: trend, delta, threshold status, staleness
  - attention lists and rollups

What it deliberately does not own:
  - board language. Every board-facing sentence comes from `ciso-board-translation`
    through a `--translations` sidecar; this engine supplies figures and structure.
  - benchmarks. There is no "industry average" here and there will not be one.

The load-bearing rule is `direction`. Up is not good: a rising dwell time or click rate
is a metric getting worse. Nothing infers direction from a name or an archetype, and
`add-metric` refuses without it, so stating the opposite of the truth is unreachable
rather than merely unlikely.

Standard library only — no dependencies. Subcommands:

  init         <store.mtr> --client 'Name' [--owner ..] [--cadence-days 90]
  add-metric   <store.mtr> --name '..' --direction higher-better|lower-better
                           [--archetype ..] [--unit ..] [--owner ..]
  record       <store.mtr> --metric M-001 --period 2026-Q3 --value 91.4 --date YYYY-MM-DD
                           [--source ..] [--actor ..] [--note ..]
  set-threshold <store.mtr> --metric M-001 [--target ..] [--warn ..] [--critical ..]
                           [--why '..']
  link         <store.mtr> --metric M-001 [--csf ID.RA-01] [--risk R-006]
  analyze      <store.mtr> [--today YYYY-MM-DD] [--out FILE]
  self-test
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
FAMILY = "metrics-register"

ARCHETYPES = ("patch-coverage", "phishing-click", "dwell-time", "third-party",
              "mfa-coverage", "framework-maturity", "backup-recovery", "custom")
UNITS = ("percent", "count", "days", "currency", "ratio")
DIRECTIONS = ("higher-better", "lower-better")
DEFAULT_CADENCE_DAYS = 90

# --- Which graphic renders this metric ----------------------------------------
# Resolved here, once, and emitted in `analyze` output so that no renderer decides
# it again. The same metric must render as the same mark in the operational view,
# the executive view and the board pack; a renderer that picks its own mark is how
# one number becomes a bullet on one page and a gauge on the next.
VIZ_KINDS = ("bullet", "progress", "tank", "gauge", "sparkline", "slope",
             "line", "column", "bar", "tile")

# Defaults per archetype (graphics standard section 6.2). Override deliberately
# with an explicit `viz` on the metric.
VIZ_BY_ARCHETYPE = {
    "patch-coverage":     "bullet",
    "phishing-click":     "bullet",
    "dwell-time":         "line",
    "third-party":        "bar",
    "mfa-coverage":       "progress",
    "framework-maturity": "bar",
    "backup-recovery":    "bullet",
    "custom":             "bullet",
}

# A metric with no agreed limit is not a status. It renders as a bare number in
# the measure colour -- no gauge, no RAG -- because colouring it would invent a
# threshold nobody agreed to. This outranks the archetype default: a missing
# threshold is a statement about the data, while the archetype only describes its
# shape.
VIZ_NO_THRESHOLD = "tile"


def resolve_viz(metric: dict, has_threshold: bool) -> str:
    """The mark this metric renders as.

    Explicit `viz` wins, then the no-threshold rule, then the archetype default,
    then `bullet`.

    An explicit `viz` is honoured even without a threshold: an author who names a
    mark has said something deliberate, and silently overriding it would make the
    field a suggestion. The colour contract still holds either way -- a metric
    with no threshold renders in the measure colour whatever its shape -- so the
    override changes how it is drawn, never what it claims.
    """
    explicit = metric.get("viz")
    if explicit:
        return explicit
    if not has_threshold:
        return VIZ_NO_THRESHOLD
    return VIZ_BY_ARCHETYPE.get(metric.get("archetype"), "bullet")


DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
METRIC_ID_RE = re.compile(r"^M-\d{3,}$")

# Trend is a verdict about movement, resolved through `direction`, never about the raw
# sign of the delta. `no-prior` is its own value: one reading is not a trend, and
# reporting "holding" off a single point would claim stability nobody has evidence for.
TREND_GAINING = "gaining"
TREND_HOLDING = "holding"
TREND_SLIPPING = "slipping"
TREND_NO_PRIOR = "no-prior"
TRENDS = (TREND_GAINING, TREND_HOLDING, TREND_SLIPPING, TREND_NO_PRIOR)

STATUS_OK = "ok"
STATUS_WARN = "warn"
STATUS_CRITICAL = "critical"
STATUS_NO_THRESHOLD = "no-threshold"
STATUS_NO_READING = "no-reading"
STATUSES = (STATUS_OK, STATUS_WARN, STATUS_CRITICAL,
            STATUS_NO_THRESHOLD, STATUS_NO_READING)

# --- Age bands ----------------------------------------------------------------
# The third copy of this function. The others are:
#   skills/risk-register/scripts/score_register.py
#   skills/nist-csf/scripts/profile_analysis.py
# and each carries a note pointing at the others. Deliberately duplicated: the obvious
# cleanup — one shared module — is rejected because every shipped script must run
# standalone, so a cross-skill import needs sys.path surgery and breaks outright the
# moment a single skill directory is used on its own. The obligation that replaces it:
# the copies are edited together, and each skill's own self-test is the only thing
# pinning them to the same semantics. Grep the sibling paths before moving a boundary.
#
#   within       d <= T//2
#   approaching  d <= T
#   beyond       d <= 2T
#   wellBeyond   d >  2T
AGE_BANDS = ("within", "approaching", "beyond", "wellBeyond")


def age_band(days: int, threshold_days: int) -> str:
    """Which band `days` of age falls in, relative to threshold `threshold_days`.

    Boundaries are inclusive of the lower band: at exactly T a reading is `approaching`,
    not yet `beyond`. The threshold is a cadence somebody chose to aim at, and hitting it
    is meeting it.

    These are not confidence words. The engine reports how old a reading is; it never
    claims how sure anyone should be that the number is still true. A decay rate is not
    derivable from an age, and naming a band after one would commit this engine to
    exactly the claim it declines to make.

    A negative `days` — a reading dated in the future — reports as `within`, matching the
    siblings. This is a pure distance measurement; a future-dated reading is a file defect
    and belongs wherever the file is validated, not hidden inside a band a reader would
    take as good news.
    """
    if days <= threshold_days // 2:
        return "within"
    if days <= threshold_days:
        return "approaching"
    if days <= threshold_days * 2:
        return "beyond"
    return "wellBeyond"


class Refusal(Exception):
    """A mutation the engine declines to perform.

    Raised before the store file is opened, so a refused mutation leaves the file
    byte-identical. That property is asserted in self-test rather than trusted: a
    half-written store is worse than a rejected command, because only one of them is
    obvious at the moment it happens.
    """


# --- Dates --------------------------------------------------------------------

def check_date(value: str, field: str) -> str:
    """Canonical `YYYY-MM-DD` or a refusal. Zero-padded, and a real calendar date.

    Unpadded dates are refused because every derivation here sorts readings by date, and
    `2026-7-1` sorts after `2026-10-01` as a string. The refusal happens at the boundary
    so the wrong ordering can never reach the arithmetic.
    """
    if not isinstance(value, str) or not DATE_RE.match(value):
        raise Refusal(
            f"{field} must be a canonical zero-padded date, YYYY-MM-DD; got {value!r}. "
            f"'2026-7-1' is refused because it sorts after '2026-10-01' as text, and "
            f"every trend and staleness figure here sorts by date.")
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
              cadence_days: int = DEFAULT_CADENCE_DAYS) -> dict:
    ts = now_ts()
    return {
        "schemaVersion": SCHEMA_VERSION,
        "family": FAMILY,
        "meta": {"clientName": client, "owner": owner, "scopeNote": scope_note,
                 "asOf": ts[:10]},
        "settings": {"cadenceDays": int(cadence_days)},
        "metrics": [],
        "readings": [],
        "history": [],
        "createdAt": ts,
        "updatedAt": ts,
    }


def load_store(path: str) -> dict:
    """Load and structurally validate a `.mtr` store."""
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
    # `family` is checked before anything else so a .rr or .csfp handed to this engine is
    # refused by name rather than half-read into a shape that happens to parse.
    fam = store.get("family")
    if fam != FAMILY:
        raise Refusal(
            f"{path} is not a metrics register: family is {fam!r}, expected {FAMILY!r}. "
            f"A risk register (.rr) or CSF profile (.csfp) belongs to a different skill.")
    if store.get("schemaVersion") != SCHEMA_VERSION:
        raise Refusal(f"{path} is schemaVersion {store.get('schemaVersion')!r}; "
                      f"this engine reads {SCHEMA_VERSION}")
    for key, kind in (("metrics", list), ("readings", list), ("history", list),
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
    fd, tmp = tempfile.mkstemp(dir=directory, suffix=".mtr.tmp")
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


def next_metric_id(store: dict) -> str:
    used = []
    for m in store["metrics"]:
        mid = m.get("id", "")
        if METRIC_ID_RE.match(mid):
            used.append(int(mid.split("-")[1]))
    return "M-%03d" % ((max(used) + 1) if used else 1)


def find_metric(store: dict, metric_id: str) -> dict:
    for m in store["metrics"]:
        if m.get("id") == metric_id:
            return m
    known = ", ".join(m.get("id", "?") for m in store["metrics"]) or "none yet"
    raise Refusal(f"no metric {metric_id!r} in this register (have: {known})")


# --- Mutations ----------------------------------------------------------------

def add_metric(store: dict, name: str, direction: str, archetype: str | None = None,
               unit: str = "percent", owner: str = "", vanity_risk: bool = False,
               notes: str = "", actor: str = "", viz: str | None = None) -> dict:
    """Define a metric. Refuses without a direction — see the module docstring."""
    if not (name or "").strip():
        raise Refusal("a metric needs a name")
    if direction not in DIRECTIONS:
        raise Refusal(
            f"direction must be one of {', '.join(DIRECTIONS)}; got {direction!r}. "
            f"There is no default: a rising dwell time is a metric getting worse, and "
            f"an engine that guessed would state the opposite of the truth in board "
            f"language.")
    if unit not in UNITS:
        raise Refusal(f"unit must be one of {', '.join(UNITS)}; got {unit!r}")
    if archetype is not None and archetype not in ARCHETYPES:
        raise Refusal(
            f"archetype must be one of {', '.join(ARCHETYPES)} or omitted; "
            f"got {archetype!r}")
    if viz is not None and viz not in VIZ_KINDS:
        raise Refusal(
            f"viz must be one of {', '.join(VIZ_KINDS)} or omitted; got {viz!r}. "
            f"An unrecognised mark would fall through to the archetype default, "
            f"and the metric would render as something nobody chose.")
    metric = {
        "id": next_metric_id(store),
        "name": name.strip(),
        "archetype": archetype,
        "unit": unit,
        "direction": direction,
        "threshold": {},
        "owner": owner,
        "csfSubcategoryIds": [],
        "riskIds": [],
        "vanityRisk": bool(vanity_risk),
        "viz": viz,
        "notes": notes,
    }
    store["metrics"].append(metric)
    append_history(store, "metric-added", metric["id"], actor,
                   detail={"name": metric["name"], "direction": direction})
    return metric


def record_reading(store: dict, metric_id: str, period: str, value: float,
                   on_date: str, source: str = "", actor: str = "",
                   note: str = "") -> dict:
    """Append a reading. Never overwrites: a correction is a new reading with a note."""
    find_metric(store, metric_id)
    if not (period or "").strip():
        raise Refusal("a reading needs a period label, e.g. '2026-Q3'")
    try:
        value = float(value)
    except (TypeError, ValueError):
        raise Refusal(f"value must be a number; got {value!r}")
    check_date(on_date, "--date")
    reading = {"metricId": metric_id, "period": period.strip(), "value": value,
               "date": on_date, "source": source, "actor": actor, "ts": now_ts(),
               "note": note}
    store["readings"].append(reading)
    append_history(store, "reading-recorded", metric_id, actor,
                   detail={"period": reading["period"], "value": value, "date": on_date})
    return reading


def set_threshold(store: dict, metric_id: str, target=None, warn=None, critical=None,
                  why: str = "", actor: str = "") -> dict:
    """Set thresholds, refusing a set incoherent for the metric's direction.

    Moving a threshold changes what the same number *means*, so replacing an existing one
    requires `--why`. Without that a register cannot answer "was this always green, or did
    we move the line?", which is the question a board asks second.
    """
    metric = find_metric(store, metric_id)
    given = {k: v for k, v in (("target", target), ("warn", warn),
                               ("critical", critical)) if v is not None}
    if not given:
        raise Refusal("set-threshold needs at least one of --target, --warn, --critical")
    merged = dict(metric.get("threshold") or {})
    replacing = {k: merged[k] for k in given if k in merged and merged[k] != given[k]}
    if replacing and not (why or "").strip():
        raise Refusal(
            f"moving an existing threshold on {metric_id} requires --why "
            f"(replacing {replacing}). A threshold move changes what the number means, "
            f"and a register that allows it silently cannot say whether a metric was "
            f"always green or the line moved.")
    for k, v in given.items():
        merged[k] = float(v)
    direction = metric["direction"]
    ordered = _threshold_order(merged, direction)
    if ordered is not None:
        raise Refusal(ordered)
    metric["threshold"] = merged
    append_history(store, "threshold-set", metric_id, actor, why=why, detail=dict(given))
    return metric


def _threshold_order(threshold: dict, direction: str) -> str | None:
    """Return an error string if the set is incoherent for `direction`, else None.

    For higher-better a value falls through critical <= warn <= target as it worsens; for
    lower-better the order reverses. A `warn` on the wrong side of `critical` is not a
    threshold anyone can breach in the intended order — it is a typo, and it would
    silently produce a metric that reports `warn` while it is past `critical`.
    """
    t, w, c = threshold.get("target"), threshold.get("warn"), threshold.get("critical")
    pairs = []
    if direction == "higher-better":
        if c is not None and w is not None:
            pairs.append((c, w, "critical", "warn"))
        if w is not None and t is not None:
            pairs.append((w, t, "warn", "target"))
        if c is not None and t is not None and w is None:
            pairs.append((c, t, "critical", "target"))
        for lo, hi, lo_name, hi_name in pairs:
            if lo > hi:
                return (f"for a higher-better metric {lo_name} must not exceed "
                        f"{hi_name} ({lo} > {hi}); as the number falls it should cross "
                        f"{hi_name} first")
    else:
        if t is not None and w is not None:
            pairs.append((t, w, "target", "warn"))
        if w is not None and c is not None:
            pairs.append((w, c, "warn", "critical"))
        if t is not None and c is not None and w is None:
            pairs.append((t, c, "target", "critical"))
        for lo, hi, lo_name, hi_name in pairs:
            if lo > hi:
                return (f"for a lower-better metric {lo_name} must not exceed "
                        f"{hi_name} ({lo} > {hi}); as the number rises it should cross "
                        f"{hi_name} first")
    return None


def link_metric(store: dict, metric_id: str, csf_ids=(), risk_ids=(),
                actor: str = "") -> dict:
    """Attach CSF Subcategory and risk ids. Not resolved against those stores — see below."""
    metric = find_metric(store, metric_id)
    added = {"csf": [], "risk": []}
    for sid in csf_ids or ():
        if sid not in metric["csfSubcategoryIds"]:
            metric["csfSubcategoryIds"].append(sid)
            added["csf"].append(sid)
    for rid in risk_ids or ():
        if rid not in metric["riskIds"]:
            metric["riskIds"].append(rid)
            added["risk"].append(rid)
    if added["csf"] or added["risk"]:
        append_history(store, "metric-linked", metric_id, actor, detail=added)
    return metric


# --- Derivations (nothing here is ever stored) --------------------------------

def readings_for(store: dict, metric_id: str) -> list[dict]:
    """This metric's readings, oldest first, ordered by date then write time.

    `ts` breaks ties so a correction recorded later for the same period wins, while the
    reading it corrects stays in the file and in this list.
    """
    rows = [r for r in store["readings"] if r.get("metricId") == metric_id]
    return sorted(rows, key=lambda r: (r.get("date", ""), r.get("ts", "")))


def trend(latest: float, prior: float | None, direction: str) -> str:
    """Direction-aware movement verdict. `prior is None` is `no-prior`, never `holding`."""
    if prior is None:
        return TREND_NO_PRIOR
    if latest == prior:
        return TREND_HOLDING
    rising = latest > prior
    better = rising if direction == "higher-better" else not rising
    return TREND_GAINING if better else TREND_SLIPPING


def threshold_status(value: float | None, threshold: dict, direction: str) -> str:
    """`ok` / `warn` / `critical`, resolved through direction. Critical wins over warn."""
    if value is None:
        return STATUS_NO_READING
    threshold = threshold or {}
    crit, warn = threshold.get("critical"), threshold.get("warn")
    if crit is None and warn is None:
        return STATUS_NO_THRESHOLD
    if direction == "higher-better":
        if crit is not None and value < crit:
            return STATUS_CRITICAL
        if warn is not None and value < warn:
            return STATUS_WARN
    else:
        if crit is not None and value > crit:
            return STATUS_CRITICAL
        if warn is not None and value > warn:
            return STATUS_WARN
    return STATUS_OK


def derive_metric(store: dict, metric: dict, today: str) -> dict:
    """Everything computed about one metric. Never written back to the store."""
    rows = readings_for(store, metric["id"])
    cadence = int((store.get("settings") or {}).get("cadenceDays") or DEFAULT_CADENCE_DAYS)
    latest = rows[-1] if rows else None
    prior = rows[-2] if len(rows) > 1 else None
    latest_value = latest["value"] if latest else None
    prior_value = prior["value"] if prior else None
    age = days_between(latest["date"], today) if latest else None
    thr = metric.get("threshold") or {}
    # "Has a threshold" means the engine can band it, which needs warn or critical.
    # A lone `target` is an aim, not a limit: threshold_status ignores it, so a
    # metric carrying only a target has no status and must not draw a RAG mark.
    banded = thr.get("warn") is not None or thr.get("critical") is not None
    return {
        "metricId": metric["id"],
        "name": metric["name"],
        "archetype": metric.get("archetype"),
        "viz": resolve_viz(metric, banded),
        "unit": metric.get("unit"),
        "direction": metric["direction"],
        "owner": metric.get("owner") or "",
        "vanityRisk": bool(metric.get("vanityRisk")),
        "threshold": dict(metric.get("threshold") or {}),
        "csfSubcategoryIds": list(metric.get("csfSubcategoryIds") or []),
        "riskIds": list(metric.get("riskIds") or []),
        "readingCount": len(rows),
        # The series itself, oldest first, so a renderer can draw a trend without
        # re-reading the store. Values only: a sparkline plots magnitude over
        # position, and shipping the full reading objects here would invite a
        # renderer to start deriving things the engine already decided.
        "readings": [r["value"] for r in rows],
        "value": latest_value,
        "period": latest["period"] if latest else None,
        "date": latest["date"] if latest else None,
        "priorValue": prior_value,
        "delta": (latest_value - prior_value) if (latest and prior) else None,
        "trend": trend(latest_value, prior_value, metric["direction"]) if latest
                 else TREND_NO_PRIOR,
        "status": threshold_status(latest_value, metric.get("threshold"),
                                   metric["direction"]),
        "ageDays": age,
        "ageBand": age_band(age, cadence) if age is not None else None,
    }


# --- Escalation (contract CAC-EL-1 §1.3) --------------------------------------
#
# Derived, stateless, never written to the store, never a history event. A metric escalates
# when it has moved for the worse without anyone being asked to look — a narrower claim than
# "needs attention", and the difference is the point. `attention` lists what a review works
# through; this lists what should have interrupted somebody before the review.
#
# Two triggers, and the exclusion is as deliberate as the inclusions:
#
#   threshold-breached   past a limit its owner set
#   sustained-slip       moving the wrong way N readings running, without breaching
#
# `stale` is NOT a trigger. This skill states that age is "an age statement, not a claim
# about whether the number is still true", exactly as risk-register says scores do not
# expire. A metric nobody has re-measured has not moved for the worse — nobody knows whether
# it moved at all — and escalating it would assert a decay this engine cannot observe. It
# stays on the attention list, where a question about freshness belongs.

ESCALATION_DEFAULTS = {
    "sustainedSlipReadings": 2,   # consecutive slipping readings, no breach
    "warnEscalates": True,        # a warn breach escalates too, not only critical
}

ESCALATION_SEVERITY_ORDER = ["critical", "high", "medium"]


def _unit_suffix(unit: str) -> str:
    """`%` for a percentage, a spaced word otherwise, nothing when the unit is unrecorded.

    Never a guessed symbol — the same rule risk-register applies to currency. A figure
    rendered in the wrong unit is worse than one rendered bare, because only the second is
    obviously incomplete to whoever reads it.
    """
    if unit == "percent":
        return "%"
    return f" {unit}" if unit else ""


def _escalation_policy(store: dict) -> dict:
    """The store's thresholds, merged per key over the defaults.

    Not validated here, matching the house rule: a write path refuses a bad value, and a
    file already carrying one still loads and still reports.
    """
    return {**ESCALATION_DEFAULTS,
            **((store.get("settings") or {}).get("escalation") or {})}


def escalations(store: dict, today: str) -> list[dict]:
    """Every escalation this register warrants, in the CAC-EL-1 §1.3 shape.

    `subjectKind` is `metric` and `subjectRef` the metric id, so a consumer aggregating
    across skills can put a breached metric beside a crossed risk band without knowing
    anything about either skill.

    `today` is accepted for signature parity across the suite and because a future
    date-derived trigger will need it. Neither trigger here reads it: both are answered by
    the reading series alone, and taking a date it does not use would be the kind of
    unused-parameter that later gets quietly wired to something.
    """
    policy = _escalation_policy(store)
    out = []
    for metric in store["metrics"]:
        rows = readings_for(store, metric["id"])
        if not rows:
            continue
        direction = metric["direction"]
        thr = metric.get("threshold") or {}
        latest = rows[-1]
        status = threshold_status(latest["value"], thr, direction)

        if status in (STATUS_WARN, STATUS_CRITICAL):
            if status == STATUS_WARN and not policy.get("warnEscalates", True):
                continue
            # How long it has been past a limit, counted back through the readings. A breach
            # on its third consecutive reading is a different conversation from one that
            # appeared this quarter, and the count is what distinguishes them.
            run = 0
            for r in reversed(rows):
                if threshold_status(r["value"], thr, direction) in (STATUS_WARN,
                                                                    STATUS_CRITICAL):
                    run += 1
                else:
                    break
            first = rows[len(rows) - run]
            limit = thr.get("critical") if status == STATUS_CRITICAL else thr.get("warn")
            suffix = _unit_suffix(metric.get("unit") or "")
            word = "reading" if run == 1 else "consecutive readings"
            out.append({
                "subjectRef": metric["id"], "subjectKind": "metric",
                "trigger": "threshold-breached",
                "severity": "critical" if status == STATUS_CRITICAL else "high",
                "since": first["date"],
                "evidence": {
                    "from": limit, "to": latest["value"],
                    "baseline": first["period"] or "",
                    "detail": (f"{metric['name']} is {latest['value']}{suffix} against a "
                               f"{status} limit of {limit}{suffix}, for {run} {word}"),
                },
            })
            continue

        # Not breached — but has it been moving the wrong way anyway? A breach is the louder
        # story and suppresses this, exactly as a crossed band suppresses drift in
        # risk-register: the same movement reported twice reads as two problems.
        need = policy.get("sustainedSlipReadings", 2)
        run = 0
        for i in range(len(rows) - 1, 0, -1):
            if trend(rows[i]["value"], rows[i - 1]["value"], direction) == TREND_SLIPPING:
                run += 1
            else:
                break
        if run >= need >= 1:
            first = rows[len(rows) - 1 - run]
            out.append({
                "subjectRef": metric["id"], "subjectKind": "metric",
                "trigger": "sustained-slip", "severity": "medium",
                "since": first["date"],
                "evidence": {
                    "from": first["value"], "to": latest["value"],
                    "baseline": first["period"] or "",
                    "detail": (f"{metric['name']} has moved the wrong way for {run} "
                               f"consecutive readings without passing a limit"),
                },
            })

    out.sort(key=lambda e: (ESCALATION_SEVERITY_ORDER.index(e["severity"]),
                            e["subjectRef"]))
    return out


def attention(rows: list[dict]) -> dict:
    """The lists a review works from. Membership rules are stated, not implied.

    `stale` is the two bands past the chosen cadence — an age statement, not a claim about
    whether the number is still true.
    """
    return {
        "breached": [r["metricId"] for r in rows
                     if r["status"] in (STATUS_WARN, STATUS_CRITICAL)],
        "worsening": [r["metricId"] for r in rows if r["trend"] == TREND_SLIPPING],
        "stale": [r["metricId"] for r in rows
                  if r["ageBand"] in ("beyond", "wellBeyond")],
        "unmeasured": [r["metricId"] for r in rows if r["readingCount"] == 0],
        "unowned": [r["metricId"] for r in rows if not r["owner"]],
        "untagged": [r["metricId"] for r in rows if r["archetype"] is None],
        "vanity": [r["metricId"] for r in rows if r["vanityRisk"]],
    }


def rollups(rows: list[dict]) -> dict:
    """Counts by archetype and by CSF Function. Counts only — no scores are averaged.

    Averaging a percent, a day count and a currency figure would produce a number with no
    unit and no meaning, so the rollup counts membership and breach instead.
    """
    by_arch: dict[str, dict] = {}
    for r in rows:
        key = r["archetype"] or "untagged"
        slot = by_arch.setdefault(key, {"metrics": 0, "breached": 0, "worsening": 0})
        slot["metrics"] += 1
        if r["status"] in (STATUS_WARN, STATUS_CRITICAL):
            slot["breached"] += 1
        if r["trend"] == TREND_SLIPPING:
            slot["worsening"] += 1
    by_fn: dict[str, dict] = {}
    for r in rows:
        for sid in r["csfSubcategoryIds"]:
            fn = sid.split(".")[0]
            slot = by_fn.setdefault(fn, {"metrics": 0, "breached": 0})
            slot["metrics"] += 1
            if r["status"] in (STATUS_WARN, STATUS_CRITICAL):
                slot["breached"] += 1
    return {"byArchetype": by_arch, "byCsfFunction": by_fn}


# --- CAC-AP-1: the applicability profile, read as data --------------------------------
#
# A consumer of the contract `incident-materiality` proved the shape of.
#
# What narrowing means here is NOT what it means there, and the difference is worth being
# exact about, because getting it wrong would be the token narrowing the contract was
# written to avoid. `incident-materiality` suppresses COMPUTED ROWS — a disclosure window a
# not-listed entity should never have had calculated. This register computes nothing
# per-domain: a reading is trended the same whether it measures OT or payroll.
#
# So what a profile narrows here is the QUESTION SET, which is exactly what CAC-AP-1 says a
# profile does and all it says. An organisation with no OT is not asked whether it tracks
# OT metrics; one that has declared nothing IS asked, because §2.2 makes absence ask more.
#
# What this deliberately does NOT do is ANSWER the question. Nothing in a `.mtr` records
# whether a metric measures OT — `archetype` is the metric's KIND, not its subject — so a
# coverage figure would be inferred from data that is not there, and this suite refuses to
# invent the number it asks for. That is also why there is no conflict record here as there
# is in `incident-materiality`: a conflict needs both sides stated, and one is missing.

CONTEXT_CONTRACT = "CAC-AP-1"
CONTEXT_SKILL = "metrics"
CONTEXT_BATTERIES = {
    "ot-coverage": {"flag": "otPresent", "label": "OT coverage",
                    "question": "does this register track metrics for the operational "
                                "technology in the estate?"},
}


def load_context(path: str) -> dict:
    """Read an applicability payload. As data — this skill imports no other skill (§2.6).

    Both refusals are deliberate. `--context` was passed on purpose, so a payload that
    cannot be honoured must say so rather than quietly leave the register un-narrowed: a
    full question set would read as a profile that decided nothing applied.
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
    but a metric does not sit in a different perimeter from the register around it.
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
    rows = [derive_metric(store, m, today) for m in store["metrics"]]
    cadence = int((store.get("settings") or {}).get("cadenceDays") or DEFAULT_CADENCE_DAYS)
    out = {
        "meta": dict(store.get("meta") or {}),
        "today": today,
        "cadenceDays": cadence,
        "metrics": rows,
        "attention": attention(rows),
        # Top-level, beside `attention` rather than inside it, because they answer different
        # questions. `attention` is the review agenda; this is what should not have waited
        # for a review. Consumers read this list and never re-derive it.
        "escalations": escalations(store, today),
        "rollups": rollups(rows),
        "counts": {
            "metrics": len(rows),
            "measured": sum(1 for r in rows if r["readingCount"] > 0),
            "readings": len(store["readings"]),
        },
    }
    # Additive by construction, as `--context` is in every consumer of CAC-AP-1: the key
    # exists only when a profile was supplied, so a run without one produces the bytes it
    # always did and no consumer has to tell an empty block from an absent one.
    if context is not None:
        out["context"] = applicability_for(context)
    return out


# --- Self-test ----------------------------------------------------------------
#
# Greenfield, so there is no upstream to be at parity WITH. Every expectation below was
# worked out by hand from schema.md before the code that satisfies it, and the cases were
# chosen to be the ones where a plausible implementation is wrong: polarity, the boundary
# of a band, one reading rather than two, and a refusal that must leave the file untouched.

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
            fails.append(f"{label}: expected {expected!r}, got {actual!r}")

    def refuses(fn, label, needle=""):
        checks[0] += 1
        try:
            fn()
        except Refusal as exc:
            if needle and needle not in str(exc):
                fails.append(f"{label}: refused, but not for the stated reason: {exc}")
            return
        fails.append(f"{label}: did not refuse")

    # --- age_band: the third copy, pinned to the same boundaries as its siblings ---
    eq(AGE_BANDS, ("within", "approaching", "beyond", "wellBeyond"), "AGE_BANDS")
    eq(age_band(0, 180), "within", "age_band(0,180)")
    eq(age_band(90, 180), "within", "age_band(90,180) is the T//2 edge")
    eq(age_band(91, 180), "approaching", "age_band(91,180)")
    eq(age_band(180, 180), "approaching", "age_band(180,180) — meeting the cadence is meeting it")
    eq(age_band(181, 180), "beyond", "age_band(181,180)")
    eq(age_band(360, 180), "beyond", "age_band(360,180) is the 2T edge")
    eq(age_band(361, 180), "wellBeyond", "age_band(361,180)")
    eq(age_band(-5, 180), "within", "a future-dated reading is a distance, not a verdict")

    # --- trend: polarity is the whole point ---------------------------------------
    eq(trend(10, 8, "higher-better"), TREND_GAINING, "higher-better rising is gaining")
    eq(trend(10, 8, "lower-better"), TREND_SLIPPING,
       "lower-better rising is SLIPPING — the case a naive engine gets backwards")
    eq(trend(8, 10, "lower-better"), TREND_GAINING, "lower-better falling is gaining")
    eq(trend(8, 10, "higher-better"), TREND_SLIPPING, "higher-better falling is slipping")
    eq(trend(5, 5, "higher-better"), TREND_HOLDING, "equal is holding")
    eq(trend(5, None, "higher-better"), TREND_NO_PRIOR,
       "one reading is no-prior, never holding — holding would claim evidence of stability")

    # --- threshold status: polarity again, and critical beating warn ---------------
    hb = {"target": 95, "warn": 90, "critical": 80}
    eq(threshold_status(96, hb, "higher-better"), STATUS_OK, "above target is ok")
    eq(threshold_status(90, hb, "higher-better"), STATUS_OK,
       "exactly at warn is not yet breached")
    eq(threshold_status(89.9, hb, "higher-better"), STATUS_WARN, "just under warn is warn")
    eq(threshold_status(80, hb, "higher-better"), STATUS_WARN, "exactly at critical is warn")
    eq(threshold_status(79.9, hb, "higher-better"), STATUS_CRITICAL, "under critical is critical")
    lb = {"target": 5, "warn": 10, "critical": 20}
    eq(threshold_status(4, lb, "lower-better"), STATUS_OK, "below target is ok (lower-better)")
    eq(threshold_status(11, lb, "lower-better"), STATUS_WARN, "over warn is warn (lower-better)")
    eq(threshold_status(21, lb, "lower-better"), STATUS_CRITICAL,
       "over critical is critical (lower-better)")
    eq(threshold_status(None, hb, "higher-better"), STATUS_NO_READING, "no reading, no status")
    eq(threshold_status(50, {}, "higher-better"), STATUS_NO_THRESHOLD,
       "no threshold is a legitimate state, not a breach")

    # --- a store built by the real functions ---------------------------------------
    work = _tf.mkdtemp()
    try:
        path = os.path.join(work, "t.mtr")
        store = new_store("Acme", owner="CISO", cadence_days=90)
        save_store(path, store)
        store = load_store(path)

        m1 = add_metric(store, "Critical patches within SLA", "higher-better",
                        archetype="patch-coverage", unit="percent", owner="Infra")
        m2 = add_metric(store, "Median dwell time", "lower-better",
                        archetype="dwell-time", unit="days")
        m3 = add_metric(store, "Attacks blocked", "higher-better", unit="count",
                        vanity_risk=True, owner="SOC")
        eq([m["id"] for m in store["metrics"]], ["M-001", "M-002", "M-003"], "ids allocate in order")
        eq(m2["owner"], "", "an unowned metric keeps an empty owner rather than a guess")

        set_threshold(store, "M-001", target=95, warn=90, critical=80)
        set_threshold(store, "M-002", target=5, warn=10, critical=20)

        record_reading(store, "M-001", "2026-Q2", 93, "2026-04-01", actor="t")
        record_reading(store, "M-001", "2026-Q3", 88, "2026-07-01", actor="t")
        record_reading(store, "M-002", "2026-Q2", 8, "2026-04-01", actor="t")
        record_reading(store, "M-002", "2026-Q3", 14, "2026-07-01", actor="t")
        record_reading(store, "M-003", "2026-Q3", 2000000, "2026-07-01", actor="t")

        out = analyze(store, "2026-07-31")
        by = {r["metricId"]: r for r in out["metrics"]}

        # M-001: 93 -> 88 on a higher-better metric. Falling, and 88 is under warn 90
        # but not under critical 80.
        eq(by["M-001"]["trend"], TREND_SLIPPING, "M-001 fell on a higher-better metric")
        eq(by["M-001"]["delta"], -5, "M-001 delta is the raw signed difference")
        eq(by["M-001"]["status"], STATUS_WARN, "M-001 is past warn, short of critical")
        # M-002: 8 -> 14 on a lower-better metric. Rising IS worse, and 14 is over warn 10.
        eq(by["M-002"]["trend"], TREND_SLIPPING,
           "M-002 rose on a lower-better metric, which is slipping")
        eq(by["M-002"]["delta"], 6, "M-002 delta stays positive even though it worsened")
        eq(by["M-002"]["status"], STATUS_WARN, "M-002 is over warn")
        # M-003: one reading, no threshold, flagged vanity.
        eq(by["M-003"]["trend"], TREND_NO_PRIOR, "M-003 has a single reading")
        eq(by["M-003"]["status"], STATUS_NO_THRESHOLD, "M-003 has no thresholds")
        eq(by["M-003"]["delta"], None, "no prior reading, no delta")

        # Age: 2026-07-01 to 2026-07-31 is 30 days against a 90-day cadence -> within.
        eq(by["M-001"]["ageDays"], 30, "age is measured from the latest reading")
        eq(by["M-001"]["ageBand"], "within", "30 days against a 90-day cadence is within")
        # Worked by hand: 2026-07-01 -> 2026-09-29 is exactly 90 days, and meeting the
        # cadence is meeting it. One day of arithmetic separates these two rows, which is
        # why both are here rather than one.
        eq(analyze(store, "2026-09-29")["metrics"][0]["ageBand"], "approaching",
           "exactly 90 days against a 90-day cadence is still approaching")
        eq(analyze(store, "2026-10-01")["metrics"][0]["ageBand"], "beyond",
           "92 days is past the cadence, so beyond")

        att = out["attention"]
        eq(sorted(att["breached"]), ["M-001", "M-002"], "both breached metrics are listed")
        eq(sorted(att["worsening"]), ["M-001", "M-002"], "both slipping metrics are listed")
        eq(att["vanity"], ["M-003"], "the vanity flag is the author's, not inferred")
        eq(att["unowned"], ["M-002"], "the metric with no owner is surfaced")
        eq(att["untagged"], ["M-003"], "only a null archetype is untagged")
        eq(att["stale"], [], "nothing is stale at 30 days")
        eq(att["unmeasured"], [], "every metric has a reading")

        eq(out["rollups"]["byArchetype"]["patch-coverage"],
           {"metrics": 1, "breached": 1, "worsening": 1}, "archetype rollup counts")
        eq(out["counts"], {"metrics": 3, "measured": 3, "readings": 5}, "headline counts")

        # A correction is a new reading, not an overwrite: the earlier one survives and
        # the later one drives the derivation.
        record_reading(store, "M-001", "2026-Q3", 91, "2026-07-01",
                       note="restated after re-pull", actor="t")
        eq(len(readings_for(store, "M-001")), 3, "the corrected reading is still in the file")
        fixed = {r["metricId"]: r for r in analyze(store, "2026-07-31")["metrics"]}
        eq(fixed["M-001"]["value"], 91, "the later write for the same date wins")
        eq(fixed["M-001"]["status"], STATUS_OK, "and 91 clears warn 90")

        # --- refusals, each leaving the file byte-identical ------------------------
        save_store(path, store)
        before = open(path, "rb").read()

        refuses(lambda: add_metric(store, "No direction", "sideways"),
                "a metric with an invented direction is refused", "direction must be one of")
        refuses(lambda: add_metric(store, "", "higher-better"),
                "a metric with no name is refused")
        refuses(lambda: add_metric(store, "Bad unit", "higher-better", unit="furlongs"),
                "an unknown unit is refused")
        refuses(lambda: add_metric(store, "Bad archetype", "higher-better",
                                   archetype="not-an-archetype"),
                "an unknown archetype is refused")
        refuses(lambda: add_metric(store, "Bad viz", "higher-better", viz="pie"),
                "an unknown viz is refused")

        # --- viz resolution -------------------------------------------------
        # Every archetype resolves to the mark the graphics standard documents.
        # Asserted per archetype rather than in bulk: a bulk check over the same
        # dict that supplies the answer proves only that the dict equals itself.
        for arch, want in (("patch-coverage", "bullet"),
                           ("phishing-click", "bullet"),
                           ("dwell-time", "line"),
                           ("third-party", "bar"),
                           ("mfa-coverage", "progress"),
                           ("framework-maturity", "bar"),
                           ("backup-recovery", "bullet"),
                           ("custom", "bullet")):
            eq(resolve_viz({"archetype": arch}, True), want,
               f"{arch} resolves to {want}")

        # A metric with no band is not a status: bare number, no gauge, no RAG.
        # This outranks the archetype default, so it must hold for an archetype
        # whose default is something else entirely.
        eq(resolve_viz({"archetype": "patch-coverage"}, False), "tile",
           "no threshold outranks the archetype default")
        eq(resolve_viz({"archetype": None}, False), "tile",
           "no archetype and no threshold resolves to tile")
        eq(resolve_viz({"archetype": None}, True), "bullet",
           "a banded metric with no archetype falls back to bullet")

        # An explicit viz is deliberate and wins over both, or the field is only
        # a suggestion. The colour contract is enforced separately, by the
        # renderer, so an override changes the shape and never the claim.
        eq(resolve_viz({"archetype": "dwell-time", "viz": "gauge"}, True), "gauge",
           "an explicit viz overrides the archetype default")
        eq(resolve_viz({"archetype": "patch-coverage", "viz": "column"}, False),
           "column", "an explicit viz is honoured with no threshold too")

        # A lone `target` is an aim, not a limit -- threshold_status ignores it --
        # so a metric carrying only a target has no status and must not draw RAG.
        target_only = add_metric(store, "Target only", "higher-better",
                                 archetype="patch-coverage")
        set_threshold(store, target_only["id"], target=95.0)
        record_reading(store, target_only["id"], "2026-Q3", 90.0, "2026-07-01")
        d_target = derive_metric(store, target_only, "2026-08-04")
        eq(d_target["status"], STATUS_NO_THRESHOLD,
           "a target with no warn/critical yields no status")
        eq(d_target["viz"], "tile",
           "...and resolves to a tile, not its archetype's bullet")
        refuses(lambda: record_reading(store, "M-001", "2026-Q4", 90, "2026-7-1"),
                "an unpadded date is refused", "canonical zero-padded")
        refuses(lambda: record_reading(store, "M-001", "2026-Q4", 90, "2026-02-30"),
                "an impossible calendar date is refused")
        refuses(lambda: record_reading(store, "M-999", "2026-Q4", 90, "2026-10-01"),
                "a reading for an unknown metric is refused")
        refuses(lambda: record_reading(store, "M-001", "", 90, "2026-10-01"),
                "a reading with no period label is refused")
        refuses(lambda: record_reading(store, "M-001", "2026-Q4", "not-a-number", "2026-10-01"),
                "a non-numeric value is refused")
        refuses(lambda: set_threshold(store, "M-001", warn=70),
                "moving a threshold without --why is refused", "requires --why")
        refuses(lambda: set_threshold(store, "M-001"),
                "set-threshold with nothing to set is refused")
        # Polarity applies to the coherence check too: for higher-better, critical must
        # not sit above warn.
        refuses(lambda: set_threshold(store, "M-003", warn=10, critical=50),
                "an incoherent higher-better threshold set is refused", "must not exceed")
        refuses(lambda: set_threshold(store, "M-002", warn=20, critical=10, why="x"),
                "an incoherent lower-better threshold set is refused", "must not exceed")

        # Nothing above touched the file. This is the property that makes a refusal safe
        # to retry, and it is asserted rather than trusted.
        ok(open(path, "rb").read() == before,
           "every refusal left the store byte-identical")

        # A --why makes the threshold move legitimate, and it lands in history.
        set_threshold(store, "M-001", warn=85, why="board lowered the bar for one quarter")
        eq(store["metrics"][0]["threshold"]["warn"], 85, "the threshold moved")
        ok(any(h["event"] == "threshold-set" and h.get("why") for h in store["history"]),
           "the reason is in the change log, not just in the diff")

        # Cross-store links are recorded, not resolved: the other store may not exist.
        link_metric(store, "M-001", csf_ids=["ID.RA-01", "PR.PS-02"], risk_ids=["R-006"])
        eq(store["metrics"][0]["csfSubcategoryIds"], ["ID.RA-01", "PR.PS-02"], "csf links land")
        link_metric(store, "M-001", csf_ids=["ID.RA-01"])
        eq(store["metrics"][0]["csfSubcategoryIds"], ["ID.RA-01", "PR.PS-02"],
           "linking the same id twice does not duplicate it")
        save_store(path, store)
        roll = analyze(load_store(path), "2026-07-31")["rollups"]["byCsfFunction"]
        eq(sorted(roll), ["ID", "PR"], "CSF rollup keys off the Function prefix")

        # --- the store is a different family from its siblings ---------------------
        other = os.path.join(work, "other.rr")
        with open(other, "w", encoding="utf-8") as fh:
            json.dump({"schemaVersion": 2, "risks": []}, fh)
        refuses(lambda: load_store(other),
                "a risk register handed to this engine is refused by family", "not a metrics register")

        # A round-trip through the file changes nothing derived.
        eq(analyze(load_store(path), "2026-07-31"), analyze(store, "2026-07-31"),
           "save/load round-trips without changing a single derived figure")

        # --- escalation (CAC-EL-1 §1.3) --------------------------------------
        # Built by hand so each trigger is isolated. A fixture that fires two at once
        # cannot show which one a check is proving.

        def _st(metrics_and_readings, **settings):
            s = new_store("Fixture Co")
            if settings:
                s["settings"]["escalation"] = dict(settings)
            for mid, direction, thr, unit, series in metrics_and_readings:
                s["metrics"].append({"id": mid, "name": mid, "direction": direction,
                                     "unit": unit, "threshold": dict(thr),
                                     "archetype": None, "owner": "o",
                                     "csfSubcategoryIds": [], "riskIds": [],
                                     "vanityRisk": False})
                for i, v in enumerate(series):
                    s["readings"].append({"metricId": mid, "period": f"P{i + 1}",
                                          "date": f"2026-0{i + 1}-01", "value": v,
                                          "source": "t"})
            return s

        # Severity comes from which limit was passed, never from the size of the miss.
        crit = _st([("M-001", "higher-better", {"warn": 90, "critical": 80}, "percent",
                     [95.0, 75.0])])
        eq([(e["trigger"], e["severity"]) for e in escalations(crit, "2026-07-31")],
           [("threshold-breached", "critical")], "past critical escalates as critical")
        warn = _st([("M-001", "higher-better", {"warn": 90, "critical": 80}, "percent",
                     [95.0, 85.0])])
        eq([e["severity"] for e in escalations(warn, "2026-07-31")], ["high"],
           "past warn escalates as high")
        eq(escalations(_st([("M-001", "higher-better", {"warn": 90, "critical": 80},
                             "percent", [95.0, 85.0])], warnEscalates=False),
                       "2026-07-31"), [],
           "warnEscalates off suppresses the warn breach and only that")

        # Polarity. A lower-better metric that RISES is slipping, and the naive
        # implementation reports it as an improvement — the defect this suite exists for.
        low = _st([("M-001", "lower-better", {"warn": 5, "critical": 10}, "percent",
                    [2.0, 6.0])])
        eq([e["severity"] for e in escalations(low, "2026-07-31")], ["high"],
           "a lower-better metric rising past warn escalates")

        # sustained-slip: exactly N, not N-1, and a breach suppresses it entirely.
        slip = _st([("M-001", "higher-better", {"warn": 10, "critical": 5}, "percent",
                     [99.0, 98.0, 97.0])])
        eq([(e["trigger"], e["severity"]) for e in escalations(slip, "2026-07-31")],
           [("sustained-slip", "medium")], "two slipping readings escalate as drift")
        eq([e["trigger"] for e in escalations(
               _st([("M-001", "higher-better", {"warn": 10, "critical": 5}, "percent",
                     [99.0, 98.0])]), "2026-07-31")], [],
           "one slipping reading does not")
        # Polarity again, and this time for the drift trigger rather than the breach. A
        # lower-better metric that RISES is slipping, and every higher-better fixture above
        # has falling values — so a naive `value < prior` agrees with the correct answer on
        # all of them and disagrees only here. Dwell time creeping 2 -> 3 -> 4 days, still
        # well inside its limits, is exactly the movement a board wants before the breach.
        eq([(e["trigger"], e["severity"]) for e in escalations(
               _st([("M-001", "lower-better", {"warn": 50, "critical": 100}, "days",
                     [2.0, 3.0, 4.0])]), "2026-07-31")],
           [("sustained-slip", "medium")],
           "a lower-better metric creeping upward inside its limits still slips")
        eq([e["trigger"] for e in escalations(
               _st([("M-001", "higher-better", {"warn": 10, "critical": 5}, "percent",
                     [99.0, 98.0, 97.0])], sustainedSlipReadings=3), "2026-07-31")], [],
           "and a raised threshold stops it firing")
        eq([e["trigger"] for e in escalations(
               _st([("M-001", "higher-better", {"warn": 90, "critical": 80}, "percent",
                     [99.0, 95.0, 85.0])]), "2026-07-31")], ["threshold-breached"],
           "a breach suppresses the slip — one movement, reported once")

        # A metric with no readings escalates nothing rather than escalating from nothing.
        eq(escalations(_st([("M-001", "higher-better", {"warn": 90}, "percent", [])]),
                       "2026-07-31"), [], "no readings, no escalation")

        # The §1.3 shape, and the ordering a consumer depends on.
        shape = escalations(crit, "2026-07-31")[0]
        eq(sorted(shape), ["evidence", "severity", "since", "subjectKind", "subjectRef",
                           "trigger"], "every escalation carries the six contract keys")
        eq(sorted(shape["evidence"]), ["baseline", "detail", "from", "to"],
           "and its evidence names the comparison that fired it")
        eq(shape["subjectKind"], "metric", "subjectKind is metric, not risk")
        mixed = _st([("M-003", "higher-better", {"warn": 10, "critical": 5}, "percent",
                      [99.0, 98.0, 97.0]),
                     ("M-001", "higher-better", {"warn": 90, "critical": 80}, "percent",
                      [95.0, 75.0]),
                     ("M-002", "higher-better", {"warn": 90, "critical": 80}, "percent",
                      [95.0, 85.0])])
        eq([(e["severity"], e["subjectRef"]) for e in escalations(mixed, "2026-07-31")],
           [("critical", "M-001"), ("high", "M-002"), ("medium", "M-003")],
           "escalations sort worst-first, then by subject")

        # Staleness is deliberately NOT a trigger. An old reading is an age statement, and
        # this engine does not claim a number decayed because nobody re-measured it.
        stale = _st([("M-001", "higher-better", {"warn": 90, "critical": 80}, "percent",
                      [95.0])])
        eq(escalations(stale, "2029-01-01"), [],
           "a years-old reading inside its limits escalates nothing")

        # And it reaches analyze(), where every consumer reads it.
        eq(len(analyze(crit, "2026-07-31")["escalations"]), 1,
           "analyze carries the escalation list")
    finally:
        shutil.rmtree(work, ignore_errors=True)

    if fails:
        print("FAILED:")
        for f in fails:
            print(f"  - {f}")
        print(f"self-test: {checks[0] - len(fails)}/{checks[0]} checks passed")
        return 1
    print(f"self-test: {checks[0]}/{checks[0]} checks passed")
    return 0


# --- CLI ----------------------------------------------------------------------

def _emit(obj, out: str | None) -> None:
    text = json.dumps(obj, indent=2, ensure_ascii=False)
    if out:
        with open(out, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
        print(f"wrote {out}")
    else:
        print(text)


def _cmd_init(args):
    if os.path.exists(args.store):
        raise Refusal(f"{args.store} already exists; init would overwrite it")
    store = new_store(args.client, args.owner, args.scope_note, args.cadence_days)
    append_history(store, "register-created", args.store, args.actor)
    save_store(args.store, store)
    print(f"Created {args.store}")
    print(f"  cadence {store['settings']['cadenceDays']} days · no metrics yet.")
    print("  Next: add-metric, then record a reading for the current period.")
    return 0


def _cmd_add_metric(args):
    store = load_store(args.store)
    m = add_metric(store, args.name, args.direction, args.archetype, args.unit,
                   args.owner, args.vanity_risk, args.notes, args.actor,
                   viz=args.viz)
    save_store(args.store, store)
    print(f"{m['id']}: {m['name']} ({m['direction']}, {m['unit']})")
    return 0


def _cmd_record(args):
    store = load_store(args.store)
    r = record_reading(store, args.metric, args.period, args.value, args.date,
                       args.source, args.actor, args.note)
    save_store(args.store, store)
    print(f"{r['metricId']} {r['period']}: {r['value']} ({r['date']})")
    return 0


def _cmd_set_threshold(args):
    store = load_store(args.store)
    m = set_threshold(store, args.metric, args.target, args.warn, args.critical,
                      args.why, args.actor)
    save_store(args.store, store)
    print(f"{m['id']} thresholds: {json.dumps(m['threshold'])}")
    return 0


def _cmd_link(args):
    store = load_store(args.store)
    m = link_metric(store, args.metric, args.csf, args.risk, args.actor)
    save_store(args.store, store)
    print(f"{m['id']} → CSF {m['csfSubcategoryIds'] or '—'} · risks {m['riskIds'] or '—'}")
    return 0


def _cmd_analyze(args):
    store = load_store(args.store)
    today = check_date(args.today, "--today") if args.today else date.today().isoformat()
    context = load_context(args.context) if args.context else None
    _emit(analyze(store, today, context), args.out)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="metrics_analysis.py",
        description=__doc__.split("\n")[0],
        formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd")

    def store_arg(sp):
        sp.add_argument("store", help="path to the .mtr store")
        sp.add_argument("--actor", default="", help="who is making this change")

    sp = sub.add_parser("init", help="create a new register")
    store_arg(sp)
    sp.add_argument("--client", required=True)
    sp.add_argument("--owner", default="")
    sp.add_argument("--scope-note", default="")
    sp.add_argument("--cadence-days", type=int, default=DEFAULT_CADENCE_DAYS)
    sp.set_defaults(fn=_cmd_init)

    sp = sub.add_parser("add-metric", help="define a metric")
    store_arg(sp)
    sp.add_argument("--name", required=True)
    sp.add_argument("--direction", required=True, choices=list(DIRECTIONS),
                    help="higher-better or lower-better; there is no default")
    sp.add_argument("--archetype", default=None, choices=list(ARCHETYPES))
    sp.add_argument("--viz", default=None, choices=list(VIZ_KINDS),
                    help="override the mark this metric renders as; omitted "
                         "resolves from the archetype")
    sp.add_argument("--unit", default="percent", choices=list(UNITS))
    sp.add_argument("--owner", default="")
    sp.add_argument("--vanity-risk", action="store_true",
                    help="flag a big-number metric that measures effort, not risk")
    sp.add_argument("--notes", default="")
    sp.set_defaults(fn=_cmd_add_metric)

    sp = sub.add_parser("record", help="append a reading")
    store_arg(sp)
    sp.add_argument("--metric", required=True)
    sp.add_argument("--period", required=True)
    sp.add_argument("--value", required=True)
    sp.add_argument("--date", required=True)
    sp.add_argument("--source", default="")
    sp.add_argument("--note", default="")
    sp.set_defaults(fn=_cmd_record)

    sp = sub.add_parser("set-threshold", help="set target/warn/critical")
    store_arg(sp)
    sp.add_argument("--metric", required=True)
    sp.add_argument("--target", type=float, default=None)
    sp.add_argument("--warn", type=float, default=None)
    sp.add_argument("--critical", type=float, default=None)
    sp.add_argument("--why", default="", help="required when replacing a threshold")
    sp.set_defaults(fn=_cmd_set_threshold)

    sp = sub.add_parser("link", help="link a metric to CSF Subcategories and risks")
    store_arg(sp)
    sp.add_argument("--metric", required=True)
    sp.add_argument("--csf", action="append", default=[])
    sp.add_argument("--risk", action="append", default=[])
    sp.set_defaults(fn=_cmd_link)

    sp = sub.add_parser("analyze", help="emit the derived JSON")
    store_arg(sp)
    sp.add_argument("--today", default=None)
    sp.add_argument("--out", default=None)
    sp.add_argument("--context", default=None, metavar="FILE",
                    help="a CAC-AP-1 applicability payload from "
                         "`business_context.py export`")
    sp.set_defaults(fn=_cmd_analyze)

    sp = sub.add_parser("self-test", help="assert the engine against hand-worked cases")
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
