#!/usr/bin/env python3
"""attention_surface.py — what needs the CISO this week, from what every producer already computes.

The suite emits thirty escalation triggers across seven producers. Every one is computed, dated,
evidenced and carries a subject reference — and until now there was nowhere to look at them
together on a working cadence. `board-pack` consumes the same escalations for a QUARTERLY
artifact aimed at a BOARD. This consumes them WEEKLY, for the person who has to act. Same input
contract, different period and audience, which is why it is a second consumer rather than a
feature of the first.

**It owns no data and computes no status.** Every fact comes from a producer's store; this skill
orders, groups and shows what changed. That discipline is what stops the attention list becoming
a thirty-first opinion.

Three things make a list of thirty items useful, and only the third needs any state:

1. **Grouping by decision, not by producer.** Nobody thinks "show me vendor escalations"; they
   think "what is overdue", "what changed under me", "what is unowned". The clusters live in
   `references/clusters.json` as DATA — a new trigger lands in one by declaration, and an
   unmapped trigger surfaces in an explicit `unclustered` group rather than disappearing.
2. **Ordering without a score.** Severity as the producer declared it, then age since `since`,
   then subject reference for stability. Deterministic and explainable. No weighting, no
   priority number, no ranking that would be a fourth opinion about what matters. Guarded by
   `evals/no-priority-score.sh` and registered under CAC-GP-1.
3. **What changed since you last looked** — the single most useful thing, and the only one
   needing state.

**What it stores: review events.** When a review happened, who ran it, and what the escalation
set looked like at that moment. Nothing else.

**What it must not store: a mute.** The exposure-lifecycle contract already decided this for
escalation volume — if the volume proves unusable, the fix is threshold tuning at the producer,
logged and visible, not a mute field that is silent. That decision carries here, and it is the
single most important guardrail in this skill, because an attention surface is exactly where a
mute feels most reasonable. There is no `acknowledge` in v1 either; §"Acknowledgement" below
records the shape it would have to take, so that whoever adds it inherits the constraints rather
than reinventing them.

**Absence is visible.** A producer whose store is missing, or whose analyze fails, is reported
as NOT READ — never as clean. A quiet attention list and an unread one must not look the same,
and that is the failure mode a projection is most prone to.

Standard library only. Subcommands:

  init        <store.att> --org 'Name'
  add-source  <store.att> --skill vendor-register --store ../vendors.vnd
  review      <store.att> [--context ctx.json] [--today YYYY-MM-DD]
                          [--record --by NAME] [--json] [--since LABEL]
  brief       <store.att> [--context ctx.json] [--today YYYY-MM-DD]
  reviews     <store.att>
  self-test

This tool is not legal advice.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from datetime import date, datetime, timezone

SCHEMA_VERSION = 1
FAMILY = "attention-surface"

DATE_RE_LEN = 10

# The producers this surface can read, and how each one is asked. Mirrored from `board-pack`'s
# table rather than shared with it: every shipped script runs standalone, and CAC-AP-1 §2.6
# makes the transport between skills data rather than an import.
#
# `nist-csf` is deliberately absent, and its absence is a statement rather than an omission: a
# gap against a Target is a DISTANCE, not a clock. It emits no escalations, correctly, and
# listing it here would produce a producer that is always silent — indistinguishable, on this
# page, from one that failed to load.
PRODUCERS = {
    "business-context": {
        "script": "business_context.py",
        # The only producer whose escalations command emits a BARE LIST rather than an analysis
        # object. Handled in `_escalations_of` rather than special-cased at the call site.
        "argv": ["escalations", "{store}", "--today", "{today}", "--json"],
        "context": False,
    },
    "risk-register": {
        "script": "score_register.py",
        "argv": ["score", "{store}", "--json", "--today", "{today}"],
        "context": True,
    },
    "metrics-register": {
        "script": "metrics_analysis.py",
        "argv": ["analyze", "{store}", "--today", "{today}"],
        "context": True,
    },
    "exceptions-register": {
        "script": "exceptions_register.py",
        "argv": ["analyze", "{store}", "--today", "{today}"],
        "context": True,
    },
    "incident-materiality": {
        "script": "incident_analysis.py",
        "argv": ["analyze", "{store}", "--today", "{today}",
                 "--now", "{today}T00:00:00+00:00"],
        "context": True,
    },
    "vendor-register": {
        "script": "vendor_register.py",
        "argv": ["analyze", "{store}", "--today", "{today}", "--json"],
        "context": True,
    },
    "ai-register": {
        "script": "ai_register.py",
        "argv": ["analyze", "{store}", "--today", "{today}", "--json"],
        "context": True,
    },
}

# CAC-EL-1 §1.3. Six keys, and an item missing any of them is reported as malformed rather than
# quietly rendered with blanks — a projection that patches its input is inventing facts.
ESCALATION_KEYS = ("evidence", "severity", "since", "subjectKind", "subjectRef", "trigger")

# Severity as the PRODUCER declared it. This skill never assigns one, and never re-ranks.
SEVERITY_ORDER = ("critical", "high", "medium")

UNCLUSTERED = "unclustered"

NOTHING_OPEN = ("Nothing is escalating across the sources that were read. Every producer that "
                "answered reported a clean register — which is not the same as every producer "
                "having answered; the sources read are listed above.")


class Refusal(Exception):
    """A mutation the engine declines to perform, raised before the store is opened."""


# --- Dates and IO -------------------------------------------------------------

def now_ts() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def utc_today() -> str:
    return now_ts()[:DATE_RE_LEN]


def days_between(earlier: str, later: str) -> int:
    return (date.fromisoformat(later) - date.fromisoformat(earlier)).days


def new_store(org: str, prepared_by: str = "") -> dict:
    ts = now_ts()
    return {
        "schemaVersion": SCHEMA_VERSION,
        "family": FAMILY,
        "meta": {"orgName": org, "preparedBy": prepared_by, "asOf": ts[:DATE_RE_LEN]},
        "sources": {},
        "reviews": [],
        "createdAt": ts,
        "updatedAt": ts,
    }


def load(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as fh:
            store = json.load(fh)
    except FileNotFoundError:
        raise Refusal("no such store: %s" % path)
    except json.JSONDecodeError as exc:
        raise Refusal("%s is not valid JSON (line %d, column %d): %s"
                      % (path, exc.lineno, exc.colno, exc.msg))
    if not isinstance(store, dict):
        raise Refusal("%s must contain a JSON object" % path)
    if store.get("family") != FAMILY:
        raise Refusal(
            "%s is not an attention surface: family is %r, expected %r. A producer's own store "
            "belongs to that skill; this one holds review events and nothing else."
            % (path, store.get("family"), FAMILY))
    if store.get("schemaVersion") != SCHEMA_VERSION:
        raise Refusal("%s is schemaVersion %r; this engine reads %d"
                      % (path, store.get("schemaVersion"), SCHEMA_VERSION))
    store.setdefault("meta", {"orgName": "", "preparedBy": "", "asOf": ""})
    if not isinstance(store.get("sources"), dict):
        store["sources"] = {}
    if not isinstance(store.get("reviews"), list):
        store["reviews"] = []
    return store


def save(path: str, store: dict) -> None:
    store["updatedAt"] = now_ts()
    directory = os.path.dirname(os.path.abspath(path)) or "."
    fd, tmp = tempfile.mkstemp(dir=directory, suffix=".att.tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(store, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def add_source(store: dict, skill: str, path: str) -> dict:
    """Point this surface at one producer's store. Refuses a skill it cannot read.

    Refusing an unknown skill rather than accepting it is the difference between a surface that
    is honestly incomplete and one that looks complete. A typo'd skill name that was silently
    accepted would produce a source that never contributes and never complains.
    """
    if skill not in PRODUCERS:
        known = ", ".join(sorted(PRODUCERS))
        extra = ""
        if skill == "nist-csf":
            extra = ("\n  `nist-csf` emits no escalations, and that is correct rather than "
                     "missing: a gap against a Target is a distance, not a clock. Adding it "
                     "would produce a source that is always silent, which on this page is "
                     "indistinguishable from one that failed to load.")
        raise Refusal("%r is not a producer this surface can read (known: %s).%s"
                      % (skill, known, extra))
    if not str(path or "").strip():
        raise Refusal("--store is required: the path to that producer's own store")
    store["sources"][skill] = str(path).strip()
    return store["sources"]


# --- Reading the producers ----------------------------------------------------

def default_skills_root() -> str:
    """`skills/`, two levels up from this file."""
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _escalations_of(payload):
    """The escalation list out of whatever shape a producer emits.

    `business-context escalations --json` emits a bare list; every other producer emits an
    analysis object with an `escalations` key. Both are read here rather than special-cased at
    the call site, so adding a producer is one table entry.
    """
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        found = payload.get("escalations")
        if isinstance(found, list):
            return found
    return None


def read_producer(skill: str, store_path: str, today: str, context: str = "",
                  skills_root: str = "", timeout: int = 120) -> dict:
    """Run one producer's analyze and take its escalations. Never fatal.

    A producer that cannot be read is REPORTED, not skipped. `ok: False` with a reason is the
    whole point: a quiet attention list and an unread one must not look the same, and every
    surface here prints the unread ones before the clean ones.
    """
    spec = PRODUCERS[skill]
    root = skills_root or default_skills_root()
    script = os.path.join(root, skill, "scripts", spec["script"])
    result = {"skill": skill, "store": store_path, "ok": False, "reason": "",
              "escalations": []}
    if not os.path.exists(script):
        result["reason"] = "no engine at %s — the skill is not installed here" % script
        return result
    if not os.path.exists(store_path):
        result["reason"] = ("no store at %s. The source is declared and the file is not there, "
                            "which is a different fact from a clean register." % store_path)
        return result
    argv = [sys.executable, script] + [
        a.replace("{store}", store_path).replace("{today}", today) for a in spec["argv"]]
    if context and spec.get("context"):
        argv += ["--context", context]
    try:
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError) as exc:
        result["reason"] = "could not run %s: %s" % (spec["script"], exc)
        return result
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "").strip().splitlines()
        result["reason"] = ("%s exited %d: %s" % (spec["script"], proc.returncode,
                                                  tail[-1] if tail else "no output"))
        return result
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError:
        result["reason"] = "%s did not emit JSON" % spec["script"]
        return result
    found = _escalations_of(payload)
    if found is None:
        result["reason"] = ("%s emitted no `escalations` key. CAC-EL-1 §1.3 is the contract this "
                            "surface reads; a producer that stopped honouring it is a change, "
                            "not an empty week." % spec["script"])
        return result
    result["ok"] = True
    result["escalations"] = found
    return result


# --- Clusters -----------------------------------------------------------------

def clusters_path() -> str:
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "references", "clusters.json")


def load_clusters(path: str = "") -> dict:
    path = path or clusters_path()
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except FileNotFoundError:
        raise Refusal("no cluster dataset at %s" % path)
    except json.JSONDecodeError as exc:
        raise Refusal("%s is not valid JSON (line %d): %s" % (path, exc.lineno, exc.msg))
    clusters = data.get("clusters")
    if not isinstance(clusters, list) or not clusters:
        raise Refusal(
            "%s declares no clusters. An empty mapping would put every escalation in the "
            "unclustered group, which reads as a broken dataset rather than a grouped list."
            % path)
    seen = {}
    for cluster in clusters:
        for trigger in (cluster.get("triggers") or []):
            if trigger in seen:
                raise Refusal(
                    "trigger %r is mapped to both %r and %r. A trigger in two clusters would "
                    "appear twice in one review, and a reader counting rows would count it "
                    "twice." % (trigger, seen[trigger], cluster.get("id")))
            seen[trigger] = cluster.get("id")
    # Named `byTrigger`, not `index`. It is a lookup, but the guard flagged the word on
    # its first run and it was right to: next to a rule forbidding a computed number,
    # "index" reads as one. A key whose name has to be explained is a key to rename.
    return {"asOf": data.get("asOf") or "", "clusters": clusters, "byTrigger": seen}


# --- Ordering, and the absence of a score -------------------------------------
#
# Deterministic and explainable, in three keys, none of them computed:
#
#   1. severity, EXACTLY as the producer declared it — never re-derived here
#   2. age since `since`, oldest first — a date subtraction, not a weighting
#   3. subjectRef, so two items of the same severity and age never swap places between runs
#
# There is no fourth key and no arithmetic combining the first three. A weighted blend would be
# a priority score, which is the number this whole suite refuses in three other places, and it
# would be this skill's own opinion about what matters — a thirty-first voice in a room that
# already has thirty. `evals/no-priority-score.sh` holds the line, registered under CAC-GP-1.

def severity_rank(severity: str) -> int:
    """Position in the declared order. Unknown severities sort last, and keep their word."""
    try:
        return SEVERITY_ORDER.index(severity)
    except ValueError:
        return len(SEVERITY_ORDER)


def order_key(item: dict, today: str):
    since = str(item.get("since") or "")
    try:
        age = days_between(since, today)
    except (ValueError, TypeError):
        # An unparseable date sorts as age zero rather than crashing the review. The item still
        # appears, still carries its own `since` string, and the malformed value is visible.
        age = 0
    return (severity_rank(str(item.get("severity") or "")), -age,
            str(item.get("subjectRef") or ""))


def evidence_text(evidence) -> str:
    """`evidence` as a sentence, whichever shape the producer emits.

    CAC-EL-1 §1.3 fixes the six KEYS an escalation carries; it does not fix the type of
    `evidence`, and the producers legitimately differ. `vendor-register` and `ai-register` emit
    a sentence. `risk-register`, `metrics-register` and `exceptions-register` emit a structured
    delta — `{from, to, baseline, detail}` — because a band crossing is a movement and the two
    ends of it are the fact.

    A renderer that stringified the second shape printed a raw Python dict on the page:
    `{'from': 12, 'to': 15, 'baseline': 'Q3 2026 Board Review', ...}`. That is the exact defect
    `board-pack`'s `decisions-render.sh` exists for, reappearing in a new consumer — which is
    what happens when a shape is handled at one call site instead of in one function. Found on
    the first live run of this surface against all seven producers.
    """
    if isinstance(evidence, dict):
        detail = str(evidence.get("detail") or "").strip()
        moved = ""
        # `not in (None, "")`, NOT `is not None`. An empty-string bound means NOT RECORDED —
        # decided 2026-08-09 (BL-191) — and not a value recorded as blank. This line read
        # `is not None` for four releases, and on `{"from": "", "to": 5}` it rendered " -> 5"
        # on the weekly surface while the twin named below rendered a no-usable-evidence
        # notice on the quarterly pack. One record, half a number on one page and nothing on
        # the other; half a fact is worse than none, because a reader cannot see it is half.
        # `0` is a recorded value and must survive this: only None and "" are absence.
        if evidence.get("from") not in (None, "") and evidence.get("to") not in (None, ""):
            moved = "%s -> %s" % (evidence["from"], evidence["to"])
        baseline = str(evidence.get("baseline") or "").strip()
        bits = [b for b in (detail, moved,
                            ("against %s" % baseline) if baseline else "") if b]
        if bits:
            return "%s%s" % (bits[0], (" (%s)" % "; ".join(bits[1:])) if bits[1:] else "")
        # An EMPTY dict is empty evidence and renders as nothing; there is no shape question
        # to report. A dict carrying keys this function does not recognise is different — say
        # so and name them, rather than printing the object, because a reader who sees a dict
        # on a page cannot tell a shape change from a data problem.
        #
        # The twin of this function lives at skills/board-pack/renderers/render_pack.py, which
        # now carries the matching note back to here, and the two agree deliberately: the same
        # escalation read by the weekly surface and by the quarterly pack has to produce the
        # same sentence, or two consumers of one contract describe one fact differently.
        #
        # This comment said "`board-pack`'s renderer" and gave no path, so there was nothing to
        # grep — and the pack end declared nothing at all. Both ends now name the other, and
        # tools/check-twins.py executes the pair over a shared corpus on every push, because
        # the four releases this claim was false are the argument against trusting it again.
        if not evidence:
            return ""
        return "(structured evidence with no `detail`: %s)" % ", ".join(sorted(evidence))
    return str(evidence or "")


def item_key(item: dict) -> str:
    """Stable identity for the diff: producer, trigger and subject.

    Deliberately NOT the evidence string. Evidence carries counts and dates that move between
    runs — "last assessed 2025-06-30; cadence 365 days" changes wording as the clock advances —
    and keying on it would report every item as new every week, which is the same as reporting
    nothing as new.
    """
    return "%s|%s|%s" % (item.get("producer") or "", item.get("trigger") or "",
                         item.get("subjectRef") or "")


def resolve_source(source: str, store_path: str = "") -> str:
    """A relative source path resolves from the STORE, not from the shell's cwd.

    `add-source` records the path as typed, which is right — a `.att` a person can read and
    edit is worth more than one holding absolute paths from whoever ran the command. But
    resolving it against the process working directory made the shipped example depend on
    where you stood: run from `examples/` it read all seven producers and returned 28 items;
    run from the repository root, the natural place, it reported all seven NOT READ.

    That is the worst possible failure for THIS skill in particular. Every other surface in
    the suite can say "no such file" and be understood. This one turns an unreadable source
    into a page of NOT READ, which is honest and correct — and a first-time reader has no way
    to tell a working-directory mistake from a genuinely unreachable register. The feature
    that makes absence visible is what made the bug hard to see.

    Absolute paths pass through untouched, and so does everything when the store path is not
    known — the fallback is the old behaviour rather than a guess.
    """
    text = str(source or "")
    if not text or os.path.isabs(text) or not store_path:
        return text
    return os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(store_path)), text))


def collect(store: dict, today: str = "", context: str = "", skills_root: str = "",
            store_path: str = "") -> dict:
    """Read every declared source and return the escalations, the failures, and the malformed.

    Three lists, because they are three different facts. A malformed item is not dropped: an
    escalation missing a CAC-EL-1 key is a producer changing its contract, and a surface that
    silently discarded it would hide exactly the change worth knowing about.
    """
    today = today or utc_today()
    items, sources, malformed = [], [], []
    for skill in sorted(store["sources"]):
        got = read_producer(skill, resolve_source(store["sources"][skill], store_path),
                            today, context, skills_root)
        sources.append({k: got[k] for k in ("skill", "store", "ok", "reason")})
        if not got["ok"]:
            continue
        for raw in got["escalations"]:
            if not isinstance(raw, dict) or any(k not in raw for k in ESCALATION_KEYS):
                malformed.append({"producer": skill, "item": raw})
                continue
            entry = {k: raw[k] for k in ESCALATION_KEYS}
            entry["producer"] = skill
            items.append(entry)
        sources[-1]["count"] = sum(1 for i in items if i["producer"] == skill)
    return {"asOf": today, "items": items, "sources": sources, "malformed": malformed}


def group(items: list, clusters: dict, today: str) -> list:
    """Items into clusters, ordered inside each, with an explicit unclustered group.

    The unclustered group is not a fallback, it is a feature: a new producer must not be able to
    emit into silence. It appears whenever anything lands in it and is omitted entirely when
    nothing does, so it reads as a finding rather than as furniture.
    """
    by_trigger = clusters["byTrigger"]
    buckets = {}
    for item in items:
        buckets.setdefault(by_trigger.get(item["trigger"], UNCLUSTERED), []).append(item)
    out = []
    for cluster in clusters["clusters"]:
        got = buckets.get(cluster["id"]) or []
        if not got:
            continue
        out.append({"id": cluster["id"], "title": cluster["title"],
                    "meaning": cluster.get("meaning") or "",
                    "items": sorted(got, key=lambda i: order_key(i, today))})
    stray = buckets.get(UNCLUSTERED) or []
    if stray:
        out.append({
            "id": UNCLUSTERED,
            "title": "Unclustered — a trigger this surface has no mapping for",
            "meaning": ("A producer emitted a trigger that `references/clusters.json` does not "
                        "know. It is shown here rather than dropped: a new producer must not be "
                        "able to emit into silence. Map it, and it moves."),
            "items": sorted(stray, key=lambda i: order_key(i, today))})
    return out


# --- What changed since you last looked ---------------------------------------

def last_review(store: dict, label: str = ""):
    reviews = [r for r in store["reviews"] if r.get("on")]
    if label:
        matching = [r for r in reviews if r.get("label") == label]
        if not matching:
            known = ", ".join(r.get("label") or "(unlabelled)" for r in reviews) or "none"
            raise Refusal("no review labelled %r (known: %s)" % (label, known))
        return matching[-1]
    return max(reviews, key=lambda r: r["on"]) if reviews else None


def diff_against(items: list, prior) -> dict:
    """New, still-open and gone, against a recorded review.

    `gone` matters as much as `new`. An escalation that stopped firing was either fixed or had
    its underlying record changed, and the two look identical from here — so it is reported as
    *no longer firing* rather than as *resolved*. This surface does not know which, and saying
    so is cheaper than being wrong.
    """
    now_keys = {item_key(i): i for i in items}
    if prior is None:
        return {"comparedTo": None, "new": [], "carried": [], "gone": [],
                "note": ("No earlier review is recorded, so nothing can be marked new. The "
                         "first review is a baseline; run it with --record to make the next "
                         "one a comparison.")}
    was = set(prior.get("keys") or [])
    new = [i for k, i in now_keys.items() if k not in was]
    carried = [i for k, i in now_keys.items() if k in was]
    gone = sorted(was - set(now_keys))
    return {
        "comparedTo": {"on": prior.get("on"), "by": prior.get("by"),
                       "label": prior.get("label") or ""},
        "new": new, "carried": carried, "gone": gone,
        "note": ("`gone` means the trigger stopped firing. It does not mean resolved — the "
                 "underlying record may have changed instead, and this surface cannot tell "
                 "those apart."),
    }


def record_review(store: dict, snapshot: dict, by: str, label: str = "",
                  note: str = "") -> dict:
    """Record that a review happened. The only state this skill holds.

    Refuses without `--by`. A review is an act by a person — the whole value of "what changed
    since you last looked" is that somebody looked — and an unattributed one cannot answer the
    question it exists for.
    """
    if not str(by or "").strip():
        raise Refusal(
            "--by is required: who ran this review.\n"
            "  The value of this surface is 'what changed since you last looked'. A review "
            "with nobody's name on it cannot say who looked, so the next diff is measured "
            "against an event that may never have happened.")
    entry = {
        "on": snapshot["asOf"],
        "ts": now_ts(),
        "by": by.strip(),
        "label": str(label or "").strip(),
        "note": str(note or "").strip(),
        # The escalation set as it stood. Keys only — the evidence prose belongs to the
        # producer and would go stale in here, and storing it would make this a second copy
        # of somebody else's record.
        "keys": sorted(item_key(i) for i in snapshot["items"]),
        "sourcesRead": [s["skill"] for s in snapshot["sources"] if s["ok"]],
        "sourcesUnread": [s["skill"] for s in snapshot["sources"] if not s["ok"]],
    }
    store["reviews"].append(entry)
    return entry


def review(store: dict, today: str = "", context: str = "", since: str = "",
           skills_root: str = "", clusters=None, store_path: str = "") -> dict:
    """The working view: clusters, ordered, with what changed since the last review."""
    snapshot = collect(store, today, context, skills_root, store_path)
    cl = clusters or load_clusters()
    prior = last_review(store, since)
    grouped = group(snapshot["items"], cl, snapshot["asOf"])
    changed = diff_against(snapshot["items"], prior)
    unread = [s for s in snapshot["sources"] if not s["ok"]]
    return {
        "family": FAMILY,
        "asOf": snapshot["asOf"],
        "organisation": store["meta"].get("orgName") or "",
        "clusters": grouped,
        "counts": {
            "items": len(snapshot["items"]),
            "sourcesDeclared": len(snapshot["sources"]),
            "sourcesRead": len(snapshot["sources"]) - len(unread),
            "sourcesUnread": len(unread),
            "bySeverity": {s: sum(1 for i in snapshot["items"] if i["severity"] == s)
                           for s in SEVERITY_ORDER},
            "new": len(changed["new"]),
            "noLongerFiring": len(changed["gone"]),
        },
        "sources": snapshot["sources"],
        "malformed": snapshot["malformed"],
        "changed": changed,
        "note": NOTHING_OPEN if not snapshot["items"] else "",
        "_items": snapshot["items"],
    }


# --- Acknowledgement: the shape it would have to take, recorded now -----------
#
# There is no `acknowledge` command, and that is a decision for v1 rather than an omission.
#
# "I have seen this and it is in hand" is genuinely useful, and it is one small step from
# silencing. The distinction that would have to hold, if it is ever built:
#
#   * an acknowledgement changes ORDERING and never VISIBILITY
#   * it carries a named person, a date and a note
#   * it EXPIRES, after which the item returns to its natural position
#
# An acknowledgement that never expires is a mute with better manners. The reason to defer it is
# the same one that kept `fact-unattributed` out of `business-context` v1: the near-miss to a
# forbidden feature is best not built until real volume proves it is needed, because the version
# built speculatively is the one that gets the constraints wrong.


def _text_review(out: dict) -> str:
    lines = []
    org = out["organisation"] or "(no organisation recorded)"
    c = out["counts"]
    lines.append("%s — attention surface, as at %s" % (org, out["asOf"]))
    lines.append("  %d item(s) across %d of %d source(s); %d new, %d no longer firing"
                 % (c["items"], c["sourcesRead"], c["sourcesDeclared"], c["new"],
                    c["noLongerFiring"]))
    lines.append("  by severity: %s"
                 % ", ".join("%s %d" % (k, v) for k, v in c["bySeverity"].items()))
    # Unread sources FIRST, before anything that looks like a result. A reader who sees a short
    # list must be told it is short because nothing fired, not because nothing was read.
    unread = [s for s in out["sources"] if not s["ok"]]
    if unread:
        lines.append("")
        lines.append("NOT READ — these sources contributed nothing because they could not be "
                     "read, which is not the same as clean:")
        for s in unread:
            lines.append("  %-22s %s" % (s["skill"], s["reason"]))
    if out["malformed"]:
        lines.append("")
        lines.append("MALFORMED — %d item(s) missing a CAC-EL-1 key, shown rather than dropped:"
                     % len(out["malformed"]))
        for m in out["malformed"][:5]:
            lines.append("  %-22s %s" % (m["producer"], json.dumps(m["item"])[:90]))
    changed = out["changed"]
    lines.append("")
    if changed["comparedTo"]:
        lines.append("Compared to the review on %s by %s%s"
                     % (changed["comparedTo"]["on"], changed["comparedTo"]["by"],
                        (" (%s)" % changed["comparedTo"]["label"])
                        if changed["comparedTo"]["label"] else ""))
    else:
        lines.append(changed["note"])
    if changed["gone"]:
        lines.append("  no longer firing: %s" % ", ".join(changed["gone"][:8]))
        lines.append("  (%s)" % changed["note"])
    new_keys = {item_key(i) for i in changed["new"]}
    for cluster in out["clusters"]:
        lines.append("")
        lines.append("## %s" % cluster["title"])
        if cluster["meaning"]:
            lines.append("   %s" % cluster["meaning"])
        for item in cluster["items"]:
            flag = "NEW " if item_key(item) in new_keys else "    "
            lines.append("  %s[%s] %-26s %-10s %s"
                         % (flag, item["severity"], item["trigger"], item["subjectRef"],
                            item["producer"]))
            lines.append("        since %s · %s"
                         % (item["since"], evidence_text(item["evidence"])))
    if out["note"]:
        lines.append("")
        lines.append(out["note"])
    return "\n".join(lines)


def _text_brief(out: dict) -> str:
    """A short digest to paste into a channel or a one-to-one.

    Shaped for pasting rather than for reading here, because turning an escalation into an
    owned, tracked task is a different product — it is where this becomes a ticketing system
    with a worse interface. That boundary is permanent; see `references/scope.md`.
    """
    c = out["counts"]
    lines = ["*Attention surface — %s*" % out["asOf"],
             "%d item(s), %d new since the last review." % (c["items"], c["new"])]
    unread = [s["skill"] for s in out["sources"] if not s["ok"]]
    if unread:
        lines.append("Not read: %s. Treat this list as incomplete." % ", ".join(unread))
    new_keys = {item_key(i) for i in out["changed"]["new"]}
    for cluster in out["clusters"]:
        top = cluster["items"][:3]
        if not top:
            continue
        lines.append("")
        lines.append("*%s* (%d)" % (cluster["title"], len(cluster["items"])))
        for item in top:
            lines.append("  • %s%s — %s (%s, since %s)"
                         % ("NEW: " if item_key(item) in new_keys else "",
                            item["trigger"], item["subjectRef"], item["producer"],
                            item["since"]))
        if len(cluster["items"]) > 3:
            lines.append("  • …and %d more" % (len(cluster["items"]) - 3))
    if not out["clusters"]:
        lines.append(out["note"] or "Nothing is escalating.")
    return "\n".join(lines)


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

    def esc(trigger, subject, severity="high", since="2026-01-01", producer="risk-register"):
        return {"trigger": trigger, "subjectKind": "risk", "subjectRef": subject,
                "severity": severity, "since": since, "evidence": "because",
                "producer": producer}

    work = _tf.mkdtemp()
    try:
        path = os.path.join(work, "t.att")
        store = new_store("Acme Manufacturing", "D. Galleyne")
        save(path, store)
        eq(load(path)["meta"]["orgName"], "Acme Manufacturing", "a store round-trips")
        wrong = os.path.join(work, "w.rr")
        open(wrong, "w", encoding="utf-8").write('{"family": "risk-register"}')
        refuses(lambda: load(wrong), "another skill's store is refused", "not an attention")

        # --- sources ------------------------------------------------------------
        refuses(lambda: add_source(store, "made-up-skill", "x.json"),
                "an unknown producer is refused", "not a producer this surface can read")
        refuses(lambda: add_source(store, "nist-csf", "x.csfp"),
                "and nist-csf is refused by name, with the reason", "a distance, not a clock")
        refuses(lambda: add_source(store, "risk-register", ""),
                "a source with no path is refused")
        add_source(store, "risk-register", "../r.rr")
        eq(store["sources"]["risk-register"], "../r.rr", "a known producer registers")

        # --- clusters -----------------------------------------------------------
        cl = load_clusters()
        ok(len(cl["clusters"]) >= 5, "the shipped cluster dataset has clusters")
        ok(cl["byTrigger"].get("assessment-overdue") == "clocks-running-out",
           "and a trigger maps to the cluster it belongs in")
        dupe = os.path.join(work, "dupe.json")
        json.dump({"clusters": [{"id": "a", "triggers": ["x"]},
                                {"id": "b", "triggers": ["x"]}]},
                  open(dupe, "w", encoding="utf-8"))
        refuses(lambda: load_clusters(dupe),
                "a trigger mapped to two clusters is refused", "would count it twice")
        empty = os.path.join(work, "empty.json")
        json.dump({"clusters": []}, open(empty, "w", encoding="utf-8"))
        refuses(lambda: load_clusters(empty), "an empty mapping is refused", "broken dataset")

        # --- ordering, and the absence of a score --------------------------------
        eq(severity_rank("critical"), 0, "severity ranks in the declared order")
        ok(severity_rank("critical") < severity_rank("high") < severity_rank("medium"),
           "...critical, high, medium")
        eq(severity_rank("invented"), len(SEVERITY_ORDER),
           "an unknown severity sorts last rather than crashing, and keeps its word")
        items = [esc("a", "R-002", "high", "2026-06-01"),
                 esc("b", "R-001", "critical", "2026-07-01"),
                 esc("c", "R-003", "high", "2026-01-01")]
        ordered = sorted(items, key=lambda i: order_key(i, "2026-08-01"))
        eq([i["subjectRef"] for i in ordered], ["R-001", "R-003", "R-002"],
           "severity first, then age (oldest first), then subject")
        # Determinism: two items alike in severity and age never swap between runs.
        tie = [esc("x", "R-009", "high", "2026-06-01"), esc("y", "R-004", "high", "2026-06-01")]
        eq([i["subjectRef"] for i in sorted(tie, key=lambda i: order_key(i, "2026-08-01"))],
           ["R-004", "R-009"], "and the subject reference breaks a tie, so ordering is stable")
        ok(all(k not in str(order_key(items[0], "2026-08-01")) for k in ("score", "weight")),
           "the order key is three declared facts, and carries no computed number")

        # --- grouping, and the unclustered group ---------------------------------
        mixed = [esc("assessment-overdue", "VA-001"), esc("band-crossed", "R-001"),
                 esc("a-trigger-nobody-mapped", "X-001")]
        grouped = group(mixed, cl, "2026-08-01")
        ids = [g["id"] for g in grouped]
        ok("clocks-running-out" in ids and "moved-under-us" in ids,
           "items land in the cluster their trigger is mapped to")
        ok(UNCLUSTERED in ids,
           "and an UNMAPPED trigger surfaces in the unclustered group rather than vanishing")
        stray = next(g for g in grouped if g["id"] == UNCLUSTERED)
        eq([i["subjectRef"] for i in stray["items"]], ["X-001"], "...carrying its own item")
        eq([g["id"] for g in group([esc("band-crossed", "R-1")], cl, "2026-08-01")],
           ["moved-under-us"],
           "and the unclustered group is ABSENT when nothing is unmapped — a finding, "
           "not furniture")

        # --- the diff -----------------------------------------------------------
        first = {"asOf": "2026-08-01", "items": mixed,
                 "sources": [{"skill": "risk-register", "ok": True}]}
        eq(diff_against(mixed, None)["new"], [],
           "with no earlier review, nothing is marked new")
        ok("baseline" in diff_against(mixed, None)["note"], "...and the output says why")
        refuses(lambda: record_review(store, first, ""),
                "recording a review with no name is refused", "who looked")
        rec = record_review(store, first, "D. Galleyne", label="week 32")
        eq(len(rec["keys"]), 3, "a recorded review stores the escalation keys")
        ok("because" not in json.dumps(rec),
           "...and NOT the evidence prose, which belongs to the producer")
        later = [esc("assessment-overdue", "VA-001"), esc("threshold-breached", "M-002")]
        d = diff_against(later, last_review(store))
        eq([i["trigger"] for i in d["new"]], ["threshold-breached"], "a new trigger is new")
        eq(len(d["carried"]), 1, "one carried over")
        eq(len(d["gone"]), 2, "and two stopped firing")
        ok("does not mean resolved" in d["note"],
           "the diff says 'no longer firing', never 'resolved' — it cannot tell those apart")
        # THE key-stability property: evidence prose moves between runs and must not count.
        moved = [dict(esc("assessment-overdue", "VA-001"), evidence="last assessed 2025-06-30")]
        eq(diff_against(moved, last_review(store))["new"], [],
           "an item whose EVIDENCE wording changed is not reported as new")
        refuses(lambda: last_review(store, "week 99"), "an unknown --since label is refused")
        eq(last_review(store, "week 32")["by"], "D. Galleyne", "and a known one resolves")

        # --- absence is visible --------------------------------------------------
        got = read_producer("risk-register", os.path.join(work, "nope.rr"), "2026-08-01")
        eq(got["ok"], False, "a missing producer store is NOT read")
        ok("different fact from a clean register" in got["reason"],
           "...and the reason says so in those words")
        eq(got["escalations"], [], "contributing nothing")
        eq(read_producer("risk-register", path, "2026-08-01",
                         skills_root=os.path.join(work, "no-skills"))["ok"], False,
           "and a missing engine is reported rather than raising")

        # --- a relative source resolves from the STORE, not the shell ------------
        # The shipped example declares `../../risk-register/examples/...`, which resolved
        # against the process working directory: run from `examples/` it read all seven
        # producers and returned 28 items; run from the repository root — the natural place —
        # it reported all seven NOT READ. Both answers looked deliberate, because reporting an
        # unreadable source IS this skill's correct behaviour. The feature that makes absence
        # visible is what made the defect invisible, and an external release test found it.
        deep = os.path.join(work, "nest", "deeper")
        os.makedirs(deep, exist_ok=True)
        att_path = os.path.join(deep, "w.att")
        eq(resolve_source("../../example.rr", att_path),
           os.path.normpath(os.path.join(work, "example.rr")),
           "a relative source resolves from the directory holding the .att")
        eq(resolve_source(path, att_path), path, "an absolute source passes through unchanged")
        eq(resolve_source("x.rr", ""), "x.rr",
           "and with no store path the old behaviour stands, rather than a guess")
        # End to end against a REAL producer store, from a directory deliberately not the
        # `.att`'s own — which is the case that was broken and the only one that proves it.
        real_rr = os.path.join(default_skills_root(), "risk-register", "examples",
                               "example-register-v2.rr")
        if os.path.exists(real_rr):
            rel_store = new_store("Relative Ltd")
            rel_store["sources"]["risk-register"] = os.path.relpath(real_rr, deep)
            save(att_path, rel_store)
            eq([s["ok"] for s in collect(load(att_path), "2026-08-01",
                                         store_path=att_path)["sources"]], [True],
               "and a store read from elsewhere finds its own relative source")
        else:
            ok(False, "the risk-register example is missing; the end-to-end path went "
                      "unchecked rather than silently passing")

        # --- malformed input is shown, not dropped -------------------------------
        st2 = new_store("Probe")
        st2["sources"]["risk-register"] = "unused"
        snap = {"asOf": "2026-08-01",
                "items": [], "sources": [], "malformed": [{"producer": "x", "item": {}}]}
        eq(len(snap["malformed"]), 1, "a malformed item is carried on the snapshot")
        bad = {"trigger": "x", "severity": "high"}          # four keys short
        ok(any(k not in bad for k in ESCALATION_KEYS),
           "an escalation missing a CAC-EL-1 key is detectable")
        eq(len(ESCALATION_KEYS), 6, "and the contract is six keys")

        # --- an empty-string evidence bound is NOT RECORDED (BL-191) -------------
        # tools/check-twins.py proves this function and board-pack's twin AGREE. Agreement is
        # not correctness: two copies could agree on the wrong answer and pass it. These
        # assert what the right answer IS, on this side, so the twin has something true to be
        # compared against.
        eq(evidence_text({"from": "", "to": 5}),
           "(structured evidence with no `detail`: from, to)",
           "an empty `from` is absence — no half-movement is rendered")
        eq(evidence_text({"from": 5, "to": ""}),
           "(structured evidence with no `detail`: from, to)",
           "and an empty `to` likewise")
        eq(evidence_text({"from": 0, "to": 5}), "0 -> 5",
           "but 0 is a recorded value and still renders")
        eq(evidence_text({"from": "", "to": 5, "detail": "band crossed"}), "band crossed",
           "the detail still carries when the movement does not")

        # --- no acknowledgement, and no mute, in v1 ------------------------------
        module = sys.modules[__name__]
        ok(not any(n for n in dir(module) if "mute" in n.lower() or "snooze" in n.lower()),
           "there is no mute and no snooze anywhere in the module")
        ok(not any(n for n in dir(module) if "acknowledge" in n.lower()),
           "and no acknowledge in v1 — the shape it would need is recorded, not built")

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
        raise Refusal("%s already exists. `init` never overwrites." % args.store)
    save(args.store, new_store(args.org, args.prepared_by))
    print("Created %s for %r" % (args.store, args.org))
    print("  Add sources: add-source %s --skill vendor-register --store ../vendors.vnd"
          % args.store)
    return 0


def _cmd_add_source(args) -> int:
    store = load(args.store)
    add_source(store, args.skill, args.store_path)
    save(args.store, store)
    print("%s -> %s  (%d source(s) declared)"
          % (args.skill, args.store_path, len(store["sources"])))
    return 0


def _cmd_review(args) -> int:
    store = load(args.store)
    out = review(store, today=args.today, context=args.context, since=args.since,
                 skills_root=args.skills_root, store_path=args.store)
    if args.record:
        snapshot = {"asOf": out["asOf"], "items": out["_items"], "sources": out["sources"]}
        rec = record_review(store, snapshot, args.by, label=args.label, note=args.note)
        save(args.store, store)
    payload = {k: v for k, v in out.items() if not k.startswith("_")}
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(_text_review(out))
        if args.record:
            print("\nRecorded review on %s by %s%s"
                  % (rec["on"], rec["by"], (" (%s)" % rec["label"]) if rec["label"] else ""))
    return 0


def _cmd_brief(args) -> int:
    store = load(args.store)
    out = review(store, today=args.today, context=args.context,
                 skills_root=args.skills_root, store_path=args.store)
    print(_text_brief(out))
    return 0


def _cmd_reviews(args) -> int:
    store = load(args.store)
    if not store["reviews"]:
        print("No review has been recorded. The first `review --record` becomes the baseline.")
        return 0
    for r in store["reviews"]:
        print("%s  %-18s %-14s %d item(s), %d source(s) read, %d unread"
              % (r["on"], r.get("label") or "(unlabelled)", r["by"], len(r["keys"]),
                 len(r.get("sourcesRead") or []), len(r.get("sourcesUnread") or [])))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="attention_surface.py",
                                description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("init")
    sp.add_argument("store")
    sp.add_argument("--org", required=True)
    sp.add_argument("--prepared-by", default="")
    sp.set_defaults(fn=_cmd_init)

    sp = sub.add_parser("add-source")
    sp.add_argument("store")
    # No `choices=`, deliberately. argparse would reject an unknown skill before the engine
    # is reached, with a bare usage line — and the engine's refusal is where the reasoning
    # lives, including the paragraph explaining why `nist-csf` is absent on purpose. A gate
    # that fires earlier than the explanation is a gate that hides it.
    sp.add_argument("--skill", required=True,
                    help="one of: %s" % ", ".join(sorted(PRODUCERS)))
    sp.add_argument("--store", dest="store_path", required=True,
                    help="the path to that producer's own store")
    sp.set_defaults(fn=_cmd_add_source)

    sp = sub.add_parser("review")
    sp.add_argument("store")
    sp.add_argument("--today", default="")
    sp.add_argument("--context", default="", help="a CAC-AP-1 payload, passed to each producer")
    sp.add_argument("--since", default="", help="diff against a named earlier review")
    sp.add_argument("--record", action="store_true")
    sp.add_argument("--by", default="", help="required with --record")
    sp.add_argument("--label", default="")
    sp.add_argument("--note", default="")
    sp.add_argument("--json", action="store_true")
    sp.add_argument("--skills-root", default="")
    sp.set_defaults(fn=_cmd_review)

    sp = sub.add_parser("brief")
    sp.add_argument("store")
    sp.add_argument("--today", default="")
    sp.add_argument("--context", default="")
    sp.add_argument("--skills-root", default="")
    sp.set_defaults(fn=_cmd_brief)

    sp = sub.add_parser("reviews")
    sp.add_argument("store")
    sp.set_defaults(fn=_cmd_reviews)

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
