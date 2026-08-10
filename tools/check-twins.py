#!/usr/bin/env python3
"""CAC-TW-1 — a declared twin is COMPARED, not merely declared.

Several functions and constants are duplicated across skills on purpose. Every shipped script
must run standalone — each resolves its own assets off `__file__` and a single skill directory
has to work when copied out on its own — so a shared module would need `sys.path` surgery and
would break outright. The duplication is a decision, recorded at both ends, and this file does
not revisit it.

What it fixes is the enforcement. Each declaration says some version of *"edit the two
together; each skill's own self-test is the only thing pinning them to the same semantics"* —
and a self-test inside one skill CANNOT SEE the other copy. By construction. Nothing under
`skills/*/evals/`, `tools/` or the CI workflow read both sides of any pair and compared them.

The drift arrived before the guard did (BL-191). `evidence_text` is twinned between
`attention-surface` and `board-pack`, and the docstring says so:

    `board-pack`'s renderer holds the twin of this function, and the two agree deliberately:
    the same escalation read by the weekly surface and by the quarterly pack has to produce
    the same sentence.

They did not agree. One tested `is not None`, the other `not in (None, "")`, and on
`{"from": "", "to": 5}` the weekly surface rendered `" -> 5"` while the quarterly pack rendered
`"(structured evidence with no `detail`: from, to)"`. One record, a number on one page and a
no-usable-evidence notice on the other, with a shipped docstring promising that could not
happen.

WHY BEHAVIOUR AND NOT SOURCE. Comparing function bodies is the obvious guard and it is the
wrong one. `_iso_date` reaches its verdict through `strptime` in one file and
`date.fromisoformat` in the other, and both docstrings say so and say why. `AGE_BAND_LABEL` is
twinned with the wording required to DIVERGE, because the two labels sit in different sentence
shapes. And most of all: `is not None` against `not in (None, "")` reads as a stylistic
difference. The audit that found BL-191 executed both functions against one input rather than
reading them side by side, and that is what this file does.

THE REGISTRY CARRIES THE COMPARISON. Not every pair agrees about the same thing, so each entry
declares what is compared:

  behaviour  run every member over a shared corpus; the results must be equal
  verdict    as above, but comparing accepted-or-rejected and the value returned, NOT the
             message — `_iso_date`'s two copies take differently-named parameters and raise
             deliberately different sentences
  derived    as above, through a per-member projection, for twins that agree on a rule while
             returning different shapes (day boundaries against rendered day ranges)
  constant   the values must be equal, through a projection where one side is a subset
  divergent  the KEYS must match and every VALUE must differ — a twin whose wording is
             required not to converge. Without this kind such a pair could only be omitted
             (unguarded and undeclared) or forced to match (wrong).
  atomic     run every member's WRITE with the dump interrupted, and compare what survived
             against a stated contract. Alone among the kinds here it does not compare
             members against member zero, because ten copies that all truncate in place
             would agree with each other perfectly and all be wrong (BL-219).

NAMING. By default every member must name every other member's path in its own source — a
twin declared at one end is a twin the other end's next reader will not know exists. An entry
may instead set `"naming": "hub"`, where each member names members[0] and members[0] lists
them all. That is for families rather than pairs: all-pairs naming of the ten save paths is
ninety references, which is a list nobody maintains and therefore a list that stops being
true. Every copy still stays one hop from the family, which is the property being bought.

Usage:  check-twins.py [repo-root]
        check-twins.py --self-test
"""
import importlib.util
import io
import contextlib
import json
import os
import re
import shutil
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.abspath(os.path.join(_HERE, ".."))

# Projections. Named rather than inlined so the registry below reads as a table.
_RANGES = lambda d: {b: ("0–%dd" % hi if b == "within" else
                         ("over %dd" % (lo - 1) if hi is None else "%d–%dd" % (lo, hi)))
                     for b, (lo, hi) in d.items()}
_STATUSED = lambda d: {k: v for k, v in d.items() if v is not None}

# Callers for the `atomic` kind. The store passed in is deliberately minimal: nothing here
# asserts anything about the CONTENT written, only about what survives when the write is cut
# short, so a fixture shaped like any one engine's schema would be a fixture the other nine
# have to tolerate for no gain. `profile.updated` is the single exception — nist-csf stamps it
# before the dump and would raise a KeyError instead of reaching the write.
_CALL_PATH_FIRST = lambda fn, path: fn(path, {"probe": "interrupted-write"})
_CALL_STORE_FIRST = lambda fn, path: fn({"probe": "interrupted-write"}, path)
_CALL_CSFP = lambda fn, path: fn({"probe": "interrupted-write", "profile": {}}, path,
                                 "2026-01-01T00:00:00Z")
_HUB_SAVE = "skills/ai-register/scripts/ai_register.py"

# Age-band corpus. Thresholds include 0 and 1 deliberately: `t // 2` is 0 for both, so every
# boundary collapses onto the same value and the four bands have to be told apart with no room
# between them (GP-1.10). Days include every boundary and both sides of it.
_AGE_CORPUS = [(d, t) for t in (0, 1, 2, 7, 180, 365)
               for d in (-5, -1, 0, 1, t // 2, t // 2 + 1, t - 1, t, t + 1,
                         2 * t - 1, 2 * t, 2 * t + 1, 10 ** 6)]

# Every entry below is a duplication somebody chose, with the reason recorded in the source at
# both ends. `members` is (path, symbol) or (path, symbol, projection).
TWINS = (
    {
        "name": "age_band",
        "kind": "behaviour",
        "why": "Three copies, not two. `metrics_analysis.py` says 'The third copy of this "
               "function… and each carries a note pointing at the others' — and neither of "
               "the other two mentions metrics-register at all. A band name reaching a board "
               "page from one skill and a working view from another has to mean one thing.",
        "members": [("skills/nist-csf/scripts/profile_analysis.py", "age_band"),
                    ("skills/risk-register/scripts/score_register.py", "age_band"),
                    ("skills/metrics-register/scripts/metrics_analysis.py", "age_band")],
        "corpus": _AGE_CORPUS,
    },
    {
        "name": "AGE_BANDS",
        "kind": "constant",
        "why": "The key set the three age_band copies return, and the order every renderer "
               "iterates. A fourth name in one skill is a KeyError on one surface and a "
               "silently dropped column on another.",
        "members": [("skills/nist-csf/scripts/profile_analysis.py", "AGE_BANDS"),
                    ("skills/risk-register/scripts/score_register.py", "AGE_BANDS"),
                    ("skills/metrics-register/scripts/metrics_analysis.py", "AGE_BANDS")],
    },
    {
        "name": "_iso_date",
        "kind": "verdict",
        "why": "Dates in both stores are compared as plain strings, so '2026-3-14' sorts "
               "after '2026-12-01' and inverts every overdue and age figure downstream. The "
               "two copies reach the verdict by different routes on purpose; what must agree "
               "is which dates are accepted and what is stored, never the error wording.",
        "members": [("skills/nist-csf/scripts/profile_analysis.py", "_iso_date"),
                    ("skills/risk-register/scripts/score_register.py", "_iso_date")],
        "corpus": [(v, "field") for v in
                   ("2026-03-14", "2026-3-14", "2026-01-1", "2026-1-1", "20270201", "",
                    "   ", "  2026-01-01  ", "2026-13-01", "2026-02-30", "2026-02-29",
                    "not a date", None, True, 0)],
    },
    {
        "name": "evidence_text",
        "kind": "behaviour",
        "why": "BL-191. The same escalation read by the weekly operational surface and by the "
               "quarterly board pack has to produce the same sentence. It did not.",
        "members": [("skills/attention-surface/scripts/attention_surface.py", "evidence_text"),
                    ("skills/board-pack/renderers/render_pack.py", "evidence_text")],
        # The empty-string bounds are the drift itself. `{"from": 0, "to": 5}` is here for the
        # opposite reason: zero IS a recorded value, and it is what a careless "treat falsy as
        # absent" fix would break.
        "corpus": [(e,) for e in (
            {}, {"from": "", "to": 5}, {"from": 5, "to": ""}, {"from": "", "to": ""},
            {"from": 0, "to": 5}, {"from": 5, "to": 0}, {"from": 0, "to": 0},
            {"from": 12, "to": 15, "baseline": "Q3 2026 Board Review", "detail": "moved band"},
            {"from": 12}, {"to": 12}, {"detail": "just a detail"},
            {"baseline": "Q3"}, {"unrecognised": 1}, {"detail": "", "from": 1, "to": 2},
            "a finished sentence", "", None, 0)],
    },
    {
        "name": "AGE_BAND_LABEL",
        "kind": "divergent",
        "why": "Declared at both ends as a twin whose wording must NOT converge: over there a "
               "label is a trailing clause after a date ('confirmed 2026-01-10, beyond "
               "cadence'), here it is the predicate of a counted row ('1 past the cadence'). "
               "The keys are shared because both track AGE_BANDS. Each end says its own "
               "skill's self-test holds it honest — and neither self-test can see the other "
               "key set, which is the whole reason this file exists.",
        "members": [("skills/nist-csf/renderers/_common.py", "AGE_BAND_LABEL"),
                    ("skills/risk-register/renderers/render_dashboard.py", "AGE_BAND_LABEL")],
    },
    {
        "name": "age_bounds / age_band_ranges",
        "kind": "derived",
        "why": "A DECLARED cross-skill twin (risk-register/renderers/_common.py:173) where the "
               "semantics must match and the shape must not: one returns day boundaries, the "
               "other the rendered day ranges. risk-register's own confirmation-age.sh checks "
               "age_bounds against its own age_band — verified, and it is a WITHIN-skill "
               "check. Nothing compared the two skills until here.",
        "members": [("skills/risk-register/renderers/_common.py", "age_bounds", _RANGES),
                    ("skills/nist-csf/renderers/_common.py", "age_band_ranges")],
        "corpus": [(t,) for t in (1, 2, 3, 7, 90, 180, 365, 730)],
    },
    {
        "name": "derive_criticality",
        "kind": "behaviour",
        "why": "The NISTIR 8179 Process E walk, in both third-party and AI registers. Both "
               "read `crownJewels[].criticality` out of a business-context store on the same "
               "byte-identical line, and BL-54's R-3 changes that field's shape — so the next "
               "edit here is one that must land on both copies or produce a governance level "
               "from an unfinished read. Registered BEFORE that change rather than after "
               "(BL-217).",
        "members": [("skills/vendor-register/scripts/vendor_register.py",
                     "derive_criticality"),
                    ("skills/ai-register/scripts/ai_register.py", "derive_criticality")],
        # (record, context) — the record supplies `supports`, the context the crown jewels.
        # Both signatures take them positionally; only the parameter NAME differs.
        "corpus": [
            ({"supports": s}, ctx)
            for s in ("Order capture", "Payment gateway", "", "unknown node")
            for ctx in (
                {},
                {"crownJewels": []},
                # one hop
                {"crownJewels": [{"system": "Order capture", "criticality": "high"}]},
                # two hops, the bound
                {"crownJewels": [{"system": "Order capture", "criticality": "high",
                                  "dependsOn": ["Payment gateway"]}]},
                # three hops — past the bound, must truncate rather than answer
                {"crownJewels": [{"system": "Order capture", "criticality": "high",
                                  "dependsOn": ["Ledger"]},
                                 {"system": "Ledger", "dependsOn": ["Payment gateway"]}]},
                # a cycle
                {"crownJewels": [{"system": "Order capture", "dependsOn": ["Payment gateway"]},
                                 {"system": "Payment gateway",
                                  "dependsOn": ["Order capture"]}]},
                # declared, with nothing to declare
                {"crownJewels": [{"system": "Order capture", "criticality": ""}]},
                {"crownJewels": [{"system": "Order capture", "criticality": "   "}]},
                # THE R-3 CASE. A crown jewel whose criticality is a record rather than a
                # level — the shape R-3 introduces. `str(dict)` is truthy and non-empty, so
                # the pre-0b code sails past its own guard and returns the repr AS the level.
                {"crownJewels": [{"system": "Order capture",
                                  "criticality": {"value": "high", "basis": "board said so"}}]},
                {"crownJewels": [{"system": "Order capture", "criticality": ["high"]}]},
            )
        ],
    },
    {
        "name": "STATUS_SEV / METRIC_STATUS_SEV",
        "kind": "constant",
        "why": "assemble_pack.py maps metric statuses to pack severities and says why in its "
               "own comment: 'warn maps to high, not medium, so the pack agrees with the "
               "metric's own bullet'. Mapping warn to medium would put a yellow chip beside "
               "an amber bullet band for one value. metrics-register's copy carries two "
               "further keys that map to no band at all, which the projection drops — a "
               "statusless metric is not a severity and the pack never renders one.",
        "members": [("skills/board-pack/scripts/assemble_pack.py", "METRIC_STATUS_SEV"),
                    ("skills/metrics-register/renderers/_common.py", "STATUS_SEV", _STATUSED)],
    },
    {
        "name": "the store write",
        "kind": "atomic",
        "naming": "hub",
        "why": "Ten engines, one pattern, and until BL-219 two of them did not follow it — "
               "risk-register and nist-csf, the two largest stores in the suite. They wrote "
               "with `open(path, \"w\")`, which truncates before the dump, so an interrupted "
               "write left a half-written file AND no copy of what had been there. Nothing "
               "could catch it: on the happy path the two writers produce identical bytes, "
               "and every self-test only ever took the happy path. So this executes the "
               "unhappy one.",
        # The third slot is a CALLER, not a projection: the ten copies take (path, store),
        # (store, path) and (store, path, ts), and an adapter per member is the honest way to
        # compare functions that agree about a property while disagreeing about a signature.
        "members": [(_HUB_SAVE, "save", _CALL_PATH_FIRST),
                    ("skills/attention-surface/scripts/attention_surface.py", "save",
                     _CALL_PATH_FIRST),
                    ("skills/business-context/scripts/business_context.py", "save",
                     _CALL_PATH_FIRST),
                    ("skills/exceptions-register/scripts/exceptions_register.py", "save_store",
                     _CALL_PATH_FIRST),
                    ("skills/incident-materiality/scripts/incident_analysis.py", "save_store",
                     _CALL_PATH_FIRST),
                    ("skills/metrics-register/scripts/metrics_analysis.py", "save_store",
                     _CALL_PATH_FIRST),
                    ("skills/policy-register/scripts/policy_register.py", "save_store",
                     _CALL_PATH_FIRST),
                    ("skills/vendor-register/scripts/vendor_register.py", "save",
                     _CALL_PATH_FIRST),
                    ("skills/risk-register/scripts/score_register.py", "save_register",
                     _CALL_STORE_FIRST),
                    ("skills/nist-csf/scripts/profile_analysis.py", "save_store", _CALL_CSFP)],
        # What every copy must do when the dump raises part-way: propagate rather than
        # swallow, leave the previous store byte-identical, and leave no temp file behind.
        "expect": ("KeyboardInterrupt", True, 0),
    },
)

# A cross-skill path reference that is NOT an agreement obligation. Listed with its own reason,
# never a shared template — a reason repeated across rows is a classification made by
# boilerplate, which `proof-coverage.py` already refuses for the same cause.
NOT_A_TWIN = (
    {"from": "skills/nist-csf/renderers/_common.py",
     "to": "skills/metrics-register/renderers/_common.py",
     "reason": "A port, not a twin, and the source says so: base_css() was copied with two "
               "selectors deliberately RENAMED because this skill had already taken both "
               "names. A guard demanding they agree would demand the rename be undone."},
)

# A real twin, declared at both ends, that nothing here compares — carrying the reason and
# what specifically is not compared. Counted and printed on every run rather than absorbed:
# an uncompared twin is the state this file exists to end, and a silent entry would read as
# covered. The same call BL-210 made about its 273 unproved checks.
UNCOMPARED = (
    {"from": "skills/nist-csf/renderers/_common.py",
     "to": "skills/risk-register/renderers/_common.py",
     "reason": "A whole-MODULE twin with a declared difference — the register's copy carries "
               "a derivation layer this one deliberately has none of. Not a function pair, so "
               "no corpus fits it. What could be compared is the shared brand tokens; that is "
               "a decision about scope, not something to improvise inside this guard.",
     "not_compared": "everything except the age_bounds/age_band_ranges pair above"},
)

MIN_REASON = 60
_PYREF = re.compile(r"skills/[A-Za-z0-9_.-]+/[A-Za-z0-9_./-]+\.py")


# ---------------------------------------------------------------------------------------


def _load(repo, rel):
    """Import a shipped script the way it runs: its own directory first on the path.

    Not a package import. Every one of these files is executable on its own and resolves
    siblings off `__file__`, so `spec_from_file_location` with the directory temporarily on
    `sys.path` is the only load that reflects reality — and it needs no `sys.path` surgery in
    the shipped tree, which is the reason the duplication exists in the first place.
    """
    path = os.path.join(repo, rel)
    d = os.path.dirname(os.path.abspath(path))
    sys.path.insert(0, d)
    try:
        name = "cactwin_%d_%s" % (len(sys.modules), re.sub(r"\W", "_", rel))
        spec = importlib.util.spec_from_file_location(name, path)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        spec.loader.exec_module(mod)
        return mod
    finally:
        if d in sys.path:
            sys.path.remove(d)


def _outcome(fn, args, kind):
    """What this pair compares, for one input."""
    try:
        got = fn(*args)
    except Exception as exc:                                    # noqa: BLE001 — see below
        # A raise IS an outcome here. `_iso_date` rejects by raising, and two copies that
        # reject different inputs is exactly the drift being looked for; swallowing it would
        # make the corpus's invalid half assert nothing.
        return ("raised", type(exc).__name__) if kind == "verdict" else \
               ("raised", type(exc).__name__, str(exc))
    return ("returned", got)


def _interrupted_write(fn, call):
    """Run one save path with the dump cut short, and report what survived.

    `json.dump` is replaced rather than the file object being sabotaged, because that is the
    one line every one of these functions has in common and the failure it models — the
    process stopping part-way through serialising — is the one BL-219 is about.

    KeyboardInterrupt, and not a plain Exception, for two reasons. It is what an operator
    actually sends. And it is the only input that tells `except BaseException` apart from
    `except Exception`: a copy narrowed to the latter cleans up after every failure it was
    tested with and leaves its temp file behind on the one it was not.

    Returns (what propagated, whether the previous store is byte-identical, temp files left).
    """
    def _cut_short(*_args, **_kwargs):
        raise KeyboardInterrupt("the dump was interrupted (check-twins fault injection)")

    d = tempfile.mkdtemp(prefix="cac-tw-atomic-")
    try:
        path = os.path.join(d, "store.json")
        before = '{"the store that was already here": "must survive"}\n'
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(before)
        real = json.dump
        json.dump = _cut_short
        try:
            call(fn, path)
            raised = "nothing — an interrupted dump did not propagate"
        except BaseException as exc:                            # noqa: BLE001 — the point
            raised = type(exc).__name__
        finally:
            json.dump = real
        with open(path, encoding="utf-8") as fh:
            preserved = fh.read() == before
        return (raised, preserved,
                len([f for f in os.listdir(d) if f != "store.json"]))
    finally:
        shutil.rmtree(d, ignore_errors=True)


def run(repo, twins, not_a_twin, uncompared, scan=True):
    """Every check, against an explicit registry. Returns (problems, counts)."""
    problems = []
    compared = 0
    pairs = set()          # ordered (from, to) file pairs the registry accounts for
    reasons = {}

    for entry in twins:
        name, kind = entry["name"], entry["kind"]
        members = entry["members"]
        if len(members) < 2:
            problems.append("%s: declares %d member(s). A twin needs two."
                            % (name, len(members)))
            continue
        for a in members:
            for b in members:
                if a[0] != b[0]:
                    pairs.add((a[0], b[0]))

        # 1. Each member exists and still defines the symbol. A rename that leaves the twin
        #    behind must be a failure, not a silently skipped comparison.
        loaded, missing = [], False
        for m in members:
            rel, sym = m[0], m[1]
            if not os.path.exists(os.path.join(repo, rel)):
                problems.append("%s: member %s does not exist." % (name, rel))
                missing = True
                continue
            mod = _load(repo, rel)
            if not hasattr(mod, sym):
                problems.append(
                    "%s: %s no longer defines %r. A twin whose symbol was renamed on one side "
                    "is drift that has already happened." % (name, rel, sym))
                missing = True
                continue
            proj = m[2] if len(m) > 2 else (lambda x: x)
            loaded.append((rel, getattr(mod, sym), proj))
        if missing:
            continue

        # 2. Every member names every other member's path in its own source. The house
        #    instruction is "grep the sibling path", so the path is the artifact — a prose
        #    reference to "board-pack's renderer" is not one, and that is the pair that drifted.
        #
        #    Under `"naming": "hub"` the obligation is spoke-to-hub and hub-to-all instead.
        #    See NAMING in the module docstring for why a ten-member family is not all-pairs.
        hub = loaded[0][0] if entry.get("naming") == "hub" else None
        for rel, _sym, _p in loaded:
            body = open(os.path.join(repo, rel), encoding="utf-8").read()
            for other, _s2, _p2 in loaded:
                if other == rel or (hub and rel != hub and other != hub):
                    continue
                if other not in body:
                    problems.append(
                        "%s: %s does not name %s anywhere in its source. A twin declared at "
                        "one end is a twin the other end's next reader will not know exists."
                        % (name, rel, other))

        # 3. The comparison itself.
        if kind == "atomic":
            # Against a stated contract, not against member zero. Every other kind here asks
            # whether the copies agree; this one asks whether each copy is right, because the
            # defect it exists for was two copies agreeing with each other and neither with
            # the pattern.
            expect = entry.get("expect")
            if not expect:
                problems.append(
                    "%s: kind 'atomic' with no `expect`. Comparing the members against each "
                    "other alone would pass a family that truncates in unison." % name)
                continue
            for rel, fn, call in loaded:
                compared += 1
                got = _interrupted_write(fn, call)
                if got != expect:
                    problems.append(
                        "%s: %s comes out of an interrupted write as %r; the contract is %r "
                        "— (what propagated, the previous store survived byte-identical, "
                        "temp files left behind)." % (name, rel, got, expect))
            continue

        if kind in ("constant", "divergent"):
            vals = [(rel, proj(obj)) for rel, obj, proj in loaded]
            base_rel, base = vals[0]
            for rel, v in vals[1:]:
                if kind == "constant":
                    compared += 1
                    if v != base:
                        problems.append("%s: %s has %r; %s has %r."
                                        % (name, base_rel, base, rel, v))
                else:
                    compared += 1
                    if set(v) != set(base):
                        problems.append(
                            "%s: key sets differ — %s has %s, %s has %s. The keys are the "
                            "shared half of a divergent twin and must match."
                            % (name, base_rel, sorted(base), rel, sorted(v)))
                        continue
                    same = sorted(k for k in base if base[k] == v[k])
                    if same:
                        problems.append(
                            "%s: %s and %s now render %s identically. This twin's wording is "
                            "declared divergent at both ends — the two sit in different "
                            "sentence shapes and converging them is the defect, not the fix."
                            % (name, base_rel, rel, ", ".join(repr(k) for k in same)))
            continue

        corpus = entry.get("corpus") or []
        if not corpus:
            problems.append(
                "%s: kind %r with an empty corpus. Nothing was executed, so a clean result "
                "here means the guard ran and asked nothing." % (name, kind))
            continue

        base_rel, base_fn, base_proj = loaded[0]
        for args in corpus:
            base_out = _outcome(lambda *a: base_proj(base_fn(*a)), args, kind)
            for rel, fn, proj in loaded[1:]:
                compared += 1
                out = _outcome(lambda *a: proj(fn(*a)), args, kind)
                if out != base_out:
                    problems.append(
                        "%s: on %s\n           %s -> %r\n           %s -> %r"
                        % (name, ", ".join(repr(a) for a in args),
                           base_rel, base_out, rel, out))

    for row in list(not_a_twin) + list(uncompared):
        pairs.add((row["from"], row["to"]))
        reason = str(row.get("reason") or "").strip()
        if len(reason) < MIN_REASON:
            problems.append("%s -> %s: classified with no usable reason. %r is not one."
                            % (row["from"], row["to"], reason))
        elif reason in reasons:
            problems.append(
                "%s -> %s: its reason is byte-identical to %s. A reason shared between rows "
                "is a template, and a template is classification-by-boilerplate."
                % (row["from"], row["to"], reasons[reason]))
        else:
            reasons[reason] = "%s -> %s" % (row["from"], row["to"])
        if not os.path.exists(os.path.join(repo, row["from"])):
            problems.append("%s -> %s: the referring file does not exist; the row has rotted."
                            % (row["from"], row["to"]))

    # 4. The scan asserts what it read (GP-1.7). Every cross-skill reference to another
    #    skill's shipped .py must be accounted for by one of the three tables. The word "twin"
    #    is NOT the tell — `AGE_BAND_LABEL`'s declaration says "carries the matching note back
    #    to here" and a twin-vocabulary grep misses it entirely. The path is the tell.
    #
    #    References to another skill's evals/*.sh are excluded by the .py-only match: those say
    #    "this is the eval that guards me", which is a different relation and not an agreement.
    seen_refs = 0
    if scan:
        for rel in sorted(_shipped_py(repo)):
            skill = rel.split("/")[1]
            body = open(os.path.join(repo, rel), encoding="utf-8").read()
            for ref in sorted(set(_PYREF.findall(body))):
                if ref.split("/")[1] == skill or not os.path.exists(os.path.join(repo, ref)):
                    continue
                seen_refs += 1
                if (rel, ref) not in pairs:
                    problems.append(
                        "%s names %s and no table accounts for it. Register it as a twin, or "
                        "record why it is not one — an unclassified cross-skill reference is "
                        "how the next twin gets declared and never compared." % (rel, ref))
        if not seen_refs:
            problems.append(
                "the scan found no cross-skill reference at all, so it asserted nothing. "
                "Either every declaration was deleted or the scan stopped reading.")

    return problems, (len(twins), compared, len(uncompared), seen_refs)


def _shipped_py(repo):
    out = []
    for root, dirs, files in os.walk(os.path.join(repo, "skills")):
        dirs[:] = [d for d in dirs if d not in ("__pycache__", ".git")]
        for f in files:
            if f.endswith(".py"):
                out.append(os.path.relpath(os.path.join(root, f), repo))
    return out


def main(argv):
    repo = argv[1] if len(argv) > 1 and not argv[1].startswith("-") else _REPO
    problems, (n, compared, unc, refs) = run(repo, TWINS, NOT_A_TWIN, UNCOMPARED)
    for p in problems:
        print("PROBLEM %s" % p)
    print("check-twins (CAC-TW-1): %d declared twin(s), %d comparison(s) executed, "
          "%d cross-skill reference(s) classified" % (n, compared, refs))
    if unc:
        for row in UNCOMPARED:
            print("  UNCOMPARED %s <-> %s — not compared: %s"
                  % (row["from"], row["to"], row["not_compared"]))
    if not problems:
        print("  ok    every declared twin agrees about what it declares it agrees about")
    return 1 if problems else 0


# ---------------------------------------------------------------------------------------


def _self_test():
    """Synthetic twins, built agreeing and then broken one way at a time.

    Against fixtures rather than the shipped tree, for the reason BL-205 spelled out: the real
    twins are meant to agree, so a guard run against them alone reports the same thing whether
    it works or not.
    """
    results = []

    AGREE = "def f(x):\n    return 'v%s' % x\nK = {'a': 1}\nL = {'a': 'one'}\n"
    DRIFT = "def f(x):\n    return 'v%s' % (x or 0)\nK = {'a': 2}\nL = {'a': 'one'}\n"
    # Same keys, different wording — a divergent twin in its CORRECT state. Without this the
    # convergence check could fire on everything and no case would notice.
    WORDED = "def f(x):\n    return 'v%s' % x\nK = {'a': 1}\nL = {'a': 'ONE, said twice'}\n"

    # Three writers that are BYTE-IDENTICAL in what they produce on the happy path and can
    # only be told apart by cutting the dump short. That is the kind's whole premise, so the
    # fixtures have to have the property too, or the cases below would pass for other reasons.
    _HEAD = "import json\nimport os\nimport tempfile\n\n\n"
    SAVES = _HEAD + (
        "def save(path, store):\n"
        "    d = os.path.dirname(os.path.abspath(path)) or '.'\n"
        "    fd, tmp = tempfile.mkstemp(dir=d, suffix='.tmp')\n"
        "    try:\n"
        "        with os.fdopen(fd, 'w', encoding='utf-8') as fh:\n"
        "            json.dump(store, fh)\n"
        "        os.replace(tmp, path)\n"
        "    except BaseException:\n"
        "        if os.path.exists(tmp):\n"
        "            os.unlink(tmp)\n"
        "        raise\n")
    TRUNCATES = _HEAD + ("def save(path, store):\n"
                         "    with open(path, 'w', encoding='utf-8') as fh:\n"
                         "        json.dump(store, fh)\n")
    # Cleans up after every failure it would be tested with, and leaks on the one it would not.
    NARROW = SAVES.replace("except BaseException:", "except Exception:")

    def build(root, one=AGREE, two=AGREE, decl=True):
        for skill, body, other in (("alpha", one, "skills/beta/scripts/b.py"),
                                   ("beta", two, "skills/alpha/scripts/a.py")):
            d = os.path.join(root, "skills", skill, "scripts")
            os.makedirs(d)
            head = ("# twin: %s\n" % other) if decl else "# no declaration here\n"
            with open(os.path.join(d, "a.py" if skill == "alpha" else "b.py"), "w") as fh:
                fh.write(head + body)
        return root

    A, B = "skills/alpha/scripts/a.py", "skills/beta/scripts/b.py"
    G = "skills/gamma/scripts/c.py"

    def build_hub(root, one=AGREE, two=AGREE, decl=True):
        """Three copies in hub shape: alpha lists both spokes, each spoke names only alpha.

        Deliberately NOT all-pairs — beta and gamma never mention each other. That is the tree
        the `naming` rule has to accept under "hub" and reject by default.
        """
        for skill, fname, body, others in (("alpha", "a.py", one, [B, G]),
                                           ("beta", "b.py", two, [A]),
                                           ("gamma", "c.py", two, [A] if decl else [])):
            d = os.path.join(root, "skills", skill, "scripts")
            os.makedirs(d)
            head = "".join("# twin: %s\n" % o for o in others) or "# no declaration here\n"
            with open(os.path.join(d, fname), "w") as fh:
                fh.write(head + body)
        return root

    def entry(kind, sym="f", corpus=((1,), ("", ), (0,))):
        e = {"name": "t", "kind": kind, "why": "x",
             "members": [(A, sym), (B, sym)]}
        if kind not in ("constant", "divergent"):
            e["corpus"] = list(corpus)
        return e

    def atomic(members=None, expect=("KeyboardInterrupt", True, 0), naming=None):
        e = {"name": "t", "kind": "atomic", "why": "x", "expect": expect,
             "members": members or [(A, "save", _CALL_PATH_FIRST),
                                    (B, "save", _CALL_PATH_FIRST)]}
        if naming:
            e["naming"] = naming
        return e

    THREE = [(A, "save", _CALL_PATH_FIRST), (B, "save", _CALL_PATH_FIRST),
             (G, "save", _CALL_PATH_FIRST)]

    def case(label, twins, want_rc, needle="", one=AGREE, two=AGREE, decl=True,
             nat=(), unc=(), scan=False, builder=None):
        root = tempfile.mkdtemp()
        try:
            (builder or build)(root, one, two, decl)
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                problems, _ = run(root, twins, nat, unc, scan=scan)
            out = "\n".join(problems)
            rc = 1 if problems else 0
            ok = rc == want_rc and (needle in out)
            results.append((ok, label, (out or "(clean)").split("\n")[0][:100]))
        finally:
            shutil.rmtree(root, ignore_errors=True)

    case("an agreeing behaviour twin passes", [entry("behaviour")], 0)
    case("a drifted behaviour twin fails, naming the input", [entry("behaviour")], 1,
         "on ''", two=DRIFT)
    case("a member that does not name its partner fails", [entry("behaviour")], 1,
         "does not name", decl=False)
    case("a renamed symbol fails rather than being skipped", [entry("behaviour", sym="gone")],
         1, "no longer defines")
    case("an empty corpus fails — nothing executed is not a pass",
         [entry("behaviour", corpus=())], 1, "empty corpus")
    case("a one-member entry fails", [{"name": "t", "kind": "behaviour", "why": "x",
                                       "members": [(A, "f")], "corpus": [(1,)]}], 1,
         "A twin needs two")
    case("an agreeing constant passes", [entry("constant", sym="K")], 0)
    case("a constant that differs fails", [entry("constant", sym="K")], 1, "has {'a': 1}",
         two=DRIFT)
    case("a divergent twin whose wording still differs passes", [entry("divergent", sym="L")],
         0, two=WORDED)
    case("a divergent twin whose values have converged fails", [entry("divergent", sym="L")],
         1, "render 'a' identically")
    case("a divergent twin whose keys differ fails", [entry("divergent", sym="L")], 1,
         "key sets differ",
         two="def f(x):\n    return x\nK = {'a': 1}\nL = {'b': 'two'}\n")
    case("a member file that does not exist fails",
         [{"name": "t", "kind": "behaviour", "why": "x", "corpus": [(1,)],
           "members": [(A, "f"), ("skills/gamma/scripts/c.py", "f")]}], 1, "does not exist")
    case("an unclassified cross-skill reference fails the scan", [], 1,
         "no table accounts for it", scan=True)
    case("...and the same tree passes once the pair is registered", [entry("behaviour")], 0,
         scan=True)
    # The scan's own anti-vacuity. A tree with no declarations left in it must not report a
    # clean scan — that is the same reading-nothing-and-calling-it-clean this file guards.
    case("a scan that finds no cross-skill reference at all fails", [entry("behaviour")], 1,
         "asserted nothing", decl=False, scan=True)
    case("a classified non-twin with a real reason passes", [entry("behaviour")], 0,
         nat=({"from": A, "to": B,
               "reason": "a port with two selectors deliberately renamed, so demanding they "
                         "agree would demand the rename be undone"},))
    case("a classification with no usable reason fails", [entry("behaviour")], 1,
         "no usable reason", nat=({"from": A, "to": B, "reason": "nope"},))
    case("two classifications sharing one reason fail", [entry("behaviour")], 1,
         "byte-identical",
         nat=({"from": A, "to": B, "reason": "the same forty-plus character template reused "
                                             "across two rows, which is the defect"},
              {"from": B, "to": A, "reason": "the same forty-plus character template reused "
                                             "across two rows, which is the defect"}))
    case("a classification naming a file that does not exist fails", [entry("behaviour")], 1,
         "has rotted",
         nat=({"from": "skills/gone/x.py", "to": B,
               "reason": "a row left behind by a rename, which is exactly how a "
                         "classification table stops describing the tree"},))

    # --- the atomic kind (BL-219) -------------------------------------------------------
    case("an atomic twin whose copies both survive an interrupted write passes",
         [atomic()], 0, one=SAVES, two=SAVES)
    case("a copy that truncates in place fails, saying the store did not survive",
         [atomic()], 1, "('KeyboardInterrupt', False, 0)", one=SAVES, two=TRUNCATES)
    case("a copy narrowed to `except Exception` fails on the temp file it leaves behind",
         [atomic()], 1, "('KeyboardInterrupt', True, 1)", one=SAVES, two=NARROW)
    # The case that makes the kind's stated contract load-bearing rather than decorative:
    # two copies that truncate in unison agree with each other completely.
    case("an atomic entry with no contract fails rather than comparing copies to each other",
         [atomic(expect=None)], 1, "no `expect`", one=TRUNCATES, two=TRUNCATES)

    # --- hub naming ---------------------------------------------------------------------
    case("under hub naming a spoke need not name the other spoke",
         [atomic(members=THREE, naming="hub")], 0, one=SAVES, two=SAVES, builder=build_hub)
    case("...while the default is still all-pairs, so the same tree fails without it",
         [atomic(members=THREE)], 1, "does not name", one=SAVES, two=SAVES,
         builder=build_hub)
    case("...and under hub naming a spoke that names nothing still fails",
         [atomic(members=THREE, naming="hub")], 1, "does not name", one=SAVES, two=SAVES,
         decl=False, builder=build_hub)

    for ok, label, tail in results:
        print("  %-4s %s" % ("ok" if ok else "FAIL", label))
        if not ok:
            print("       got: %s" % tail)
    bad = [r for r in results if not r[0]]
    print("\ncheck-twins self-test: %d/%d checks passed" % (len(results) - len(bad),
                                                            len(results)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(_self_test() if "--self-test" in sys.argv[1:] else main(sys.argv))
