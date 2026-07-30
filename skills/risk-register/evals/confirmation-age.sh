#!/bin/bash
# Confirmation-age derivation, asserted against a register built by the real CLI.
#
#   ./confirmation-age.sh [workdir]          PY=/usr/bin/python3 ./confirmation-age.sh
#
# The four derived fields (lastConfirmedAt, lastConfirmedBy, confirmationAgeDays,
# confirmationBand) come from history[] and nothing else — there is no stored age field
# and there must never be one. So they are asserted through the same Context the
# renderers use, over a register whose history was written by actual commands rather
# than hand-assembled JSON. A hand-built fixture would not catch the failure that
# matters most: a command that writes the wrong event type.
#
# THREE anti-vacuity rules this file follows, each from a mutant that survived a version
# of it:
#
#   1. A partial run must FAIL, not pass. The derivation below is one Python heredoc: any
#      uncaught exception ends the block early and every check after that point silently
#      vanishes. Injecting `raise SystemExit` after the first subprocess call once
#      produced "1 check, all checks passed, exit 0". So the block's exit status is
#      checked, it prints a completion sentinel carrying its own count, and that count is
#      compared against EXPECTED_CHECKS below. python-compat.sh guards its own version of
#      this with `if [ "$count" -eq 0 ]`; this is the same guard made exact rather than
#      merely non-zero, because 45 of 46 checks is also a false green.
#   2. Where a check filters, it also pins how many rows survived the filter. `all(...)`
#      over a filter matching nothing is green over nothing.
#   3. Where a check asserts a property of a constant in score_register.py, the fixture
#      must NOT be derived from that same constant, or a mutant moves both sides together
#      and the check cannot fail. See AFFIRMING_LITERAL.
#
# Exit 0 = all pass. Exit 1 = at least one failure, or a partial run, listed.

set -u
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "$here/../../.." && pwd)"
work="${1:-$(mktemp -d)}"
PY="${PY:-python3}"
RR="$repo/skills/risk-register"
mkdir -p "$work"

# Every check each block emits on a whole run. A partial run is a failure, and the only
# way to notice one is to know how many checks a whole run produces. Update these
# deliberately when adding a check — that is the point of them.
#
# Two counts because there are two verdict streams: the derivation block asserts the
# four derived fields and the rollup through the Context, and the rendered-HTML block
# asserts what the operational panel and the attention cards actually say. A check added
# to one does not change the other, and neither number is the total.
EXPECTED_CHECKS=46
EXPECTED_RENDER_CHECKS=9

fails=0
chk() {
  printf '%-5s %-58s %s\n' "$1" "$2" "$3"
  [ "$3" = PASS ] || fails=$((fails + 1))
}
die() { echo "confirmation-age: FIXTURE FAILED — $1"; exit 1; }

# Read one verdict stream, and refuse to report success over a partial run.
#
#   read_verdicts <out.txt> <err.txt> <exit status> <expected count> <label>
#
# The three guards from rule 1 above, in one implementation because there are two streams
# now. Two copies of this logic would be two rules that have to agree forever, and the
# second copy is exactly where a missing guard would sit unnoticed — a block whose count
# nobody pinned reports every check it managed to reach as a pass.
read_verdicts() {
  local out="$1" err="$2" rc="$3" expected="$4" label="$5"
  local seen=0 sentinel="" verdict name
  while IFS=$'\t' read -r verdict name; do
    if [ "$verdict" = "#DONE" ]; then sentinel="$name"; continue; fi
    chk "$n" "$name" "$verdict"
    n=$((n + 1)); seen=$((seen + 1))
  done < "$out"
  if [ "$rc" -ne 0 ]; then
    chk "$n" "the $label block ran to completion (exit $rc)" FAIL
    n=$((n + 1))
    echo
    echo "  stderr from the $label block:"
    sed 's/^/    /' "$err"
    echo
  fi
  if [ "$sentinel" != "$seen" ]; then
    chk "$n" "every emitted $label check was read (sentinel '${sentinel:-none}' vs $seen read)" FAIL
    n=$((n + 1))
  fi
  if [ "$seen" -ne "$expected" ]; then
    chk "$n" "all $expected $label checks ran (got $seen)" FAIL
    n=$((n + 1))
  fi
}

# Logged so a CI run proves which interpreter actually executed. A PY= override that was
# quietly ignored would otherwise leave a pass on 3.13 looking like a pass on the floor.
echo "confirmation-age: $("$PY" -c 'import sys; print(sys.version.split()[0], sys.executable)')"
echo

SR="$RR/scripts/score_register.py"
rm -f "$work"/*.rr
"$PY" "$SR" init "$work/a.rr" --client "Age Co" --assessor "D. Alleyne" >/dev/null \
  || die "init"
"$PY" "$SR" add "$work/a.rr" --title "Supplier concentration" \
  --il 4 --ii 4 --rl 3 --ri 4 --why "fixture" >/dev/null || die "add R-001"
"$PY" "$SR" add "$work/a.rr" --title "Legacy VPN appliance" \
  --il 5 --ii 4 --rl 4 --ri 4 --why "fixture" >/dev/null || die "add R-002"
"$PY" "$SR" add "$work/a.rr" --title "Retired file share still reachable" \
  --il 3 --ii 3 --rl 2 --ri 2 --why "fixture" >/dev/null || die "add R-003"
"$PY" "$SR" add "$work/a.rr" --title "Unpatched internet-facing host" \
  --il 4 --ii 5 --rl 3 --ri 3 --why "fixture" >/dev/null || die "add R-004"
# R-002 gets a non-affirming event LAST. Its age must still date from `risk-added`.
"$PY" "$SR" set-text "$work/a.rr" R-002 \
  --title "Remote access via an unsupported VPN appliance" --why "reworded" >/dev/null \
  || die "set-text R-002"
"$PY" "$SR" set-status "$work/a.rr" R-002 monitoring --why "watching" >/dev/null \
  || die "set-status R-002 monitoring"
# R-003 is closed. A closed risk keeps its confirmation date forever, and it must not sit
# in the live freshness distribution — `confirm` deliberately allows confirming a closed
# risk, so excluding it here is the corollary obligation.
"$PY" "$SR" set-status "$work/a.rr" R-003 closed \
  --why "decommissioned and verified" >/dev/null || die "set-status R-003 closed"
"$PY" "$SR" snapshot "$work/a.rr" --label "Baseline" >/dev/null || die "snapshot"

set +e
"$PY" - "$work" "$RR" <<'PY' > "$work/out.txt" 2> "$work/err.txt"
import json, sys, pathlib, argparse, subprocess
from datetime import date, timedelta
work, rr = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
sys.path.insert(0, str(rr / "renderers"))
sys.path.insert(0, str(rr / "scripts"))
import _common as C
import score_register as sr

SR = str(rr / "scripts" / "score_register.py")

# The five age-affirming event types, written out as an independent literal and NOT read
# from sr.AGE_AFFIRMING. Rule 3 in the header: the fixture below re-dates non-affirming
# events so "a later edit does not reset the age" can actually fail, and the mandatory
# mutant for that property is adding risk-updated/status-changed to sr.AGE_AFFIRMING.
# Reading the constant here would re-date the fixture in lockstep with the mutant and
# report every check green. Two independent statements of one taxonomy is the only
# arrangement in which either can contradict the other.
AFFIRMING_LITERAL = {"risk-added", "score-changed", "risk-confirmed", "risk-accepted",
                     "acceptance-revalidated"}


def run(*argv):
    subprocess.run([sys.executable, SR] + list(argv), check=True, capture_output=True)


def raises(thunk):
    try:
        thunk()
        return False
    except Exception:                                           # noqa: BLE001
        return True


reg = json.loads((work / "a.rr").read_text())
# Every event this fixture wrote is dated today, so ages are 0 and every risk is
# `within`. The band boundaries themselves are asserted in score_register's self-test;
# what is asserted here is that the derivation reads the right event.
today = max(e["ts"] for e in reg["history"])[:10]
base = date.fromisoformat(today)

emitted = [0]


def add(name, good):
    """Emit one verdict, immediately and unbuffered.

    Streamed rather than accumulated and printed at the end. With a deferred print, a
    block that died halfway printed *nothing at all* — so a regression anywhere showed up
    only as "the block did not complete", with no indication of which checks had already
    passed or how far it got. Flushing per line means a partial run is still diagnostic,
    while the sentinel and count guards in the shell keep it a failure.
    """
    emitted[0] += 1
    print(("PASS" if good else "FAIL") + "\t" + name, flush=True)


def add_try(name, thunk):
    """Like add(), but a raising check reports FAIL instead of aborting the suite.

    Only for checks whose whole claim is "this does not raise": there, a traceback IS the
    failure and has to be reported as one. Every other check stays unguarded on purpose,
    which is what the completion sentinel at the bottom is for.
    """
    try:
        add(name, thunk())
    except Exception as exc:                                    # noqa: BLE001
        add("%s (raised %r)" % (name, exc), False)


def ctx(path="a.rr", **over):
    args = argparse.Namespace(register=str(work / path), out=str(work / "x.html"),
                              today=today, translations=None, offline=True,
                              age_threshold=C.DEFAULT_AGE_THRESHOLD)
    for k, v in over.items():
        setattr(args, k, v)
    return C.Context(args)


# ================ a malformed date must not become a traceback ===================
# FIRST, deliberately. Almost every check below calls ctx() unguarded, so if the date
# arithmetic starts raising, the block dies before reaching the checks that name the
# problem and the failure reports as "the derivation block did not run to completion" —
# true, but it does not say why. Asserting tolerance up front means a tolerance
# regression reports as itself.
#
# _days_since is called directly because the Context path alone would not reach it:
# _overdue() compares strings, so a date reading as "not overdue" never gets to the
# arithmetic at all.
past = (base - timedelta(days=30)).isoformat()
add_try("_days_since is tolerant of nonsense and absence",
        lambda: (C._days_since("not-a-date", today) is None
                 and C._days_since("", today) is None
                 and C._days_since(None, today) is None
                 and C._days_since("2026-02-30", today) is None
                 and C._days_since(past, today) == 30))
# And end to end, with a date that IS lexically overdue and arithmetically impossible —
# the shape a real typo takes. _overdue() flags it, so the age code definitely runs.
rawc = json.loads((work / "a.rr").read_text())
rawc["risks"][0]["reviewDate"] = "2026-02-30"
(work / "c.rr").write_text(json.dumps(rawc))
add_try("a malformed reviewDate degrades rather than crashing",
        lambda: (ctx("c.rr").by_id["R-001"]["reviewOverdue"] is True
                 and ctx("c.rr").by_id["R-001"]["reviewOverdueDays"] is None))

# ============================== per-risk derivation ===============================
c = ctx()
by = c.by_id
add("R-001 dates from risk-added", by["R-001"]["lastConfirmedAt"] == today)
add("R-001 names the actor", by["R-001"]["lastConfirmedBy"] == "D. Alleyne")
add("R-001 age is 0 days", by["R-001"]["confirmationAgeDays"] == 0)
add("R-001 bands as within", by["R-001"]["confirmationBand"] == "within")
# Pinned as an exact tail rather than a membership test, so a fixture that stopped
# writing these events cannot pass this vacuously.
add("R-002 history really does end non-affirming",
    [e["type"] for e in by["R-002"]["history"]]
    == ["risk-added", "risk-updated", "status-changed"])
add("R-002 still dates from risk-added", by["R-002"]["lastConfirmedAt"] == today)

# ...but on its own that check cannot fail. Every event the CLI just wrote shares one
# date, so "dates from risk-added" is true whichever event the derivation picks — a
# mutant treating status-changed as affirming passed it. So it is re-asserted over a
# re-dated copy: the same event types written by the same real commands, with the
# non-affirming ones moved 200 days after the risk-added they must not displace.
rawe = json.loads((work / "a.rr").read_text())
for e in rawe["history"]:
    off = 0 if e["type"] in AFFIRMING_LITERAL else 200
    e["ts"] = (base + timedelta(days=off)).isoformat() + "T00:00:00Z"
(work / "e.rr").write_text(json.dumps(rawe))
ce = ctx("e.rr", today=(base + timedelta(days=200)).isoformat())
add("a later non-affirming event does not reset R-002's age",
    ce.by_id["R-002"]["lastConfirmedAt"] == today
    and ce.by_id["R-002"]["confirmationAgeDays"] == 200
    and ce.by_id["R-002"]["confirmationBand"] == "beyond")
add("nor does it move R-002 out of its band in the rollup",
    ce.confirmation["bands"] == {"within": 0, "approaching": 0,
                                 "beyond": 3, "wellBeyond": 0}
    and ce.confirmation["undated"] == 0
    and ce.confirmation["unreadableDate"] == 0
    and ce.confirmation["live"] == 3)

# ================================= the rollup ====================================
add("rollup bands are exactly the live population",
    c.confirmation["bands"] == {"within": 3, "approaching": 0,
                                "beyond": 0, "wellBeyond": 0})
add("rollup undated and unreadableDate are 0 here",
    c.confirmation["undated"] == 0 and c.confirmation["unreadableDate"] == 0)
# 4 risks in the register, 1 closed. If the closed one leaks in, `live` reads 4.
add("rollup excludes the closed risk",
    c.confirmation["live"] == 3 and len(c.risks) == 4
    and c.by_id["R-003"]["status"] == "closed")
add("bands, undated and unreadableDate partition the live population",
    sum(c.confirmation["bands"].values()) + c.confirmation["undated"]
    + c.confirmation["unreadableDate"] == c.confirmation["live"] == 3)

# ============================ honest absence, state 1 ============================
# A register with a v1-style history — no affirming event at all — must yield None, not
# a guess and not a crash. Stripped by the independent literal, not by the constant.
raw = json.loads((work / "a.rr").read_text())
raw["history"] = [e for e in raw["history"] if e["type"] not in AFFIRMING_LITERAL]
(work / "b.rr").write_text(json.dumps(raw))
cb = ctx("b.rr")
add("no affirming event yields None, not a guess",
    cb.by_id["R-001"]["lastConfirmedAt"] is None
    and cb.by_id["R-001"]["lastConfirmedBy"] is None
    and cb.by_id["R-001"]["confirmationAgeDays"] is None
    and cb.by_id["R-001"]["confirmationBand"] is None)
add("undated risks are counted, not hidden or banded",
    cb.confirmation["undated"] == 3 and cb.confirmation["live"] == 3
    and cb.confirmation["unreadableDate"] == 0
    and cb.confirmation["bands"] == {"within": 0, "approaching": 0,
                                     "beyond": 0, "wellBeyond": 0})

# ======================= unreadable date, state 2 (distinct) =====================
# An affirming event whose ts is unreadable is NOT the same thing as no affirming event.
# The confirmation and the confirmer are on record; only the distance is unknown. A
# renderer captioning `undated` as "never confirmed" must not be handed this risk.
rawu = json.loads((work / "a.rr").read_text())
for e in rawu["history"]:
    if e.get("riskId") == "R-001" and e["type"] in AFFIRMING_LITERAL:
        e["ts"] = "2026-02-30T09:00:00Z"
(work / "u.rr").write_text(json.dumps(rawu))
cu = ctx("u.rr")
add("an unreadable ts keeps the confirmer and drops only the distance",
    cu.by_id["R-001"]["lastConfirmedAt"] == "2026-02-30"
    and cu.by_id["R-001"]["lastConfirmedBy"] == "D. Alleyne"
    and cu.by_id["R-001"]["confirmationAgeDays"] is None
    and cu.by_id["R-001"]["confirmationBand"] is None)
add("an unreadable ts is counted apart from undated",
    cu.confirmation["unreadableDate"] == 1 and cu.confirmation["undated"] == 0
    and cu.confirmation["bands"] == {"within": 2, "approaching": 0,
                                     "beyond": 0, "wellBeyond": 0}
    and cu.confirmation["live"] == 3)
add("...and the three still partition the live population",
    sum(cu.confirmation["bands"].values()) + cu.confirmation["undated"]
    + cu.confirmation["unreadableDate"] == cu.confirmation["live"])

# =================== --age-threshold reaches the derivation ======================
# Not "is it stored on the Context" — the same register, aged 400 days, must band
# differently under two cadences. Dropping the kwarg leaves the first of these wrong.
aged = (base + timedelta(days=400)).isoformat()
c_180 = ctx(today=aged, age_threshold=180)
c_1000 = ctx(today=aged, age_threshold=1000)
add("400 days is wellBeyond at T=180",
    c_180.by_id["R-001"]["confirmationBand"] == "wellBeyond")
add("the same 400 days is within at T=1000",
    c_1000.by_id["R-001"]["confirmationBand"] == "within")
add("the rollup follows the threshold too",
    c_180.confirmation["bands"] == {"within": 0, "approaching": 0,
                                    "beyond": 0, "wellBeyond": 3}
    and c_1000.confirmation["bands"] == {"within": 3, "approaching": 0,
                                         "beyond": 0, "wellBeyond": 0})
# thresholdDays is the denominator a board page prints. Read at 180 alone this cannot
# tell "reports its own threshold" from "reports the constant 180", because 180 is also
# the argparse default — a mutant hardcoding it survived the whole suite.
add("rollup reports its own threshold, not the default",
    c_180.confirmation["thresholdDays"] == 180
    and c_1000.confirmation["thresholdDays"] == 1000)
add("the rollup names the wellBeyond risks, live only",
    [r["id"] for r in c_180.confirmation["wellBeyond"]] == ["R-001", "R-002", "R-004"]
    and c_1000.confirmation["wellBeyond"] == [])
add("--age-threshold is rejected at zero or below",
    all(_rc != 0 for _rc in [subprocess.run(
        [sys.executable, str(rr / "renderers" / "render_board.py"), str(work / "a.rr"),
         str(work / "rej.html"), "--offline", "--age-threshold", bad],
        capture_output=True).returncode for bad in ("0", "-5")]))
# The threshold is REQUIRED with no Context-side fallback, following nist-csf's
# attention_lists(): a default here would be a second place the module holds it, and
# `or 180` silently rewrote the age_threshold=0 that parse_args refuses into 180 for any
# caller building the Namespace by hand — this suite's own ctx() being one.
add("a Context built without a threshold refuses rather than assuming 180",
    raises(lambda: C.Context(argparse.Namespace(
        register=str(work / "a.rr"), out=str(work / "x.html"), today=today,
        translations=None, offline=True))))
add("an explicit 0 is not silently rewritten to 180",
    ctx(age_threshold=0).confirmation["thresholdDays"] == 0)
add("DEFAULT_AGE_THRESHOLD is the only default, and argparse uses it",
    C.parse_args([str(work / "a.rr")], "d", "o.html").age_threshold
    == C.DEFAULT_AGE_THRESHOLD == 180)

# ============================== reviewOverdueDays ================================
# A missed deadline is a fact with a magnitude, still boolean-gated. Both halves are
# asserted against a register with a real overdue date, so neither is vacuous.
rawd = json.loads((work / "a.rr").read_text())
rawd["risks"][0]["reviewDate"] = past          # R-001, live   -> 30
rawd["risks"][2]["reviewDate"] = past          # R-003, closed -> None
(work / "d.rr").write_text(json.dumps(rawd))
cd = ctx("d.rr")
add("an overdue review carries its day count",
    cd.by_id["R-001"]["reviewOverdue"] is True
    and cd.by_id["R-001"]["reviewOverdueDays"] == 30)
add("a closed risk past its review date is neither overdue nor counted",
    cd.by_id["R-003"]["reviewOverdue"] is False
    and cd.by_id["R-003"]["reviewOverdueDays"] is None)
not_overdue = [r for r in cd.risks if not r["reviewOverdue"]]
add("not-overdue carries no day count",
    len(not_overdue) == 3 and all(r["reviewOverdueDays"] is None for r in not_overdue))

# =============================== ts robustness ===================================
# History is append-only, so on a tied ts the later-appended event is the later
# assertion. Defensive rather than a live defect — see _confirmation's docstring.
rawt = json.loads((work / "a.rr").read_text())
ts = rawt["history"][0]["ts"]
rawt["history"] = [
    {"ts": ts, "actor": "First Writer", "type": "score-changed", "riskId": "R-001"},
    {"ts": ts, "actor": "Second Writer", "type": "risk-confirmed", "riskId": "R-001"},
]
(work / "t.rr").write_text(json.dumps(rawt))
add("on a tied ts the later-appended affirming event wins",
    ctx("t.rr").by_id["R-001"]["lastConfirmedBy"] == "Second Writer")
# A heterogeneous ts raises TypeError out of the sort key and kills the whole render,
# one line from the code written to stop exactly that.
rawh = json.loads((work / "a.rr").read_text())
rawh["history"] = [
    {"ts": 20260726, "actor": "Numeric Writer", "type": "score-changed", "riskId": "R-001"},
    {"ts": ts, "actor": "String Writer", "type": "risk-confirmed", "riskId": "R-001"},
]
(work / "h.rr").write_text(json.dumps(rawh))
add_try("a numeric ts beside a string one does not crash the render",
        lambda: ctx("h.rr").by_id["R-001"]["lastConfirmedBy"] is not None)

# ============= a 'nothing changed' rationale never captions a change =============
SCORE_WHY = "third-party review found no compensating control"
CONFIRM_WHY = "reviewed at the forum; unchanged"
STATUS_WHY = "compensating control now in place, watching"
ACCEPT_WHY = "audit committee tolerates this until the platform migration lands"

# A confirm resets the age; nothing else about the risk moves.
run("confirm", str(work / "a.rr"), "R-001", "--why", "reviewed, unchanged")
c2 = ctx()
add("confirm becomes the affirming event",
    c2.by_id["R-001"]["history"][-1]["type"] == "risk-confirmed")
add("confirm keeps the age at 0", c2.by_id["R-001"]["confirmationAgeDays"] == 0)

run("set-score", str(work / "a.rr"), "R-001", "--residual", "5", "5", "--why", SCORE_WHY)
run("confirm", str(work / "a.rr"), "R-001", "--why", CONFIRM_WHY)
# Two further CHANGE_EXPLAINING members exercised end to end rather than merely listed.
# Reducing the frozenset to {"score-changed"} passed the whole suite before these existed.
run("set-status", str(work / "a.rr"), "R-002", "in-treatment", "--why", STATUS_WHY)
run("accept", str(work / "a.rr"), "R-004", "--approver", "Audit Committee",
    "--justification", "compensating monitoring in place", "--revalidate", "2027-01-31",
    "--why", ACCEPT_WHY)
c3 = ctx()
chg = {ch["id"]: ch for ch in c3.diff["changes"]}
add("the confirmation really is the newest rationale for R-001",
    [e.get("rationale") for e in c3.by_id["R-001"]["history"]][-1] == CONFIRM_WHY)
add("score-changed explains the move, not the re-affirmation",
    chg["R-001"]["kind"] == "worsened" and chg["R-001"]["rationale"] == SCORE_WHY)
add("status-changed explains a status move",
    chg["R-002"]["detail"] == "monitoring → in-treatment"
    and chg["R-002"]["rationale"] == STATUS_WHY)
add("risk-accepted explains an acceptance",
    "accepted by Audit Committee" in chg["R-004"]["detail"]
    and chg["R-004"]["rationale"] == ACCEPT_WHY)
add("a confirmation rationale is still kept in history",
    CONFIRM_WHY in [e.get("rationale") for e in c3.by_id["R-001"]["history"]])

# The partition, not merely a subset. score_register.py's own note says why at length: a
# subset check forces a new type to be *registered* and nothing more, leaving it
# classified by omission — the default the mechanism exists to prevent. Checked against
# score_register's taxonomy rather than against a second copy of either list.
CE, NCE = C.Context.CHANGE_EXPLAINING, C.Context.NOT_CHANGE_EXPLAINING
add("risk-confirmed cannot caption a change", "risk-confirmed" in NCE)
add("no event type both explains a change and does not", CE & NCE == frozenset())
add("every known event type is classified either way", CE | NCE == sr.KNOWN_EVENT_TYPES)
add("both halves are non-empty", bool(CE) and bool(NCE))
# The types carrying no riskId are inert in the picker whichever list they sit in, so
# they belong on the not-explaining side and saying so keeps the list honest.
add("the riskId-less types are on the not-explaining side",
    {"snapshot-created", "register-created", "import-merged", "settings-changed"} <= NCE)

# ============================ derived, never stored ==============================
# Read LAST, after confirm / set-score / set-status / accept have all written, so it can
# see a field persisted by any of those paths and not only by init and add.
raw_text = (work / "a.rr").read_text()
add("no age field is persisted to the register",
    not any(k in raw_text for k in ("lastConfirmedAt", "confirmationAgeDays",
                                    "confirmationBand", "lastConfirmedBy",
                                    "reviewOverdueDays")))

# The completion sentinel, reached only if nothing above raised. Without it, a block
# dying halfway reports every check it managed to reach as a pass and the suite exits 0.
print("#DONE\t%d" % emitted[0], flush=True)
PY
py_rc=$?
set -u

n=1
read_verdicts "$work/out.txt" "$work/err.txt" "$py_rc" "$EXPECTED_CHECKS" derivation

# The board page is the artifact directors read, so the rationale rule is asserted on
# rendered output as well as on the derivation.
"$PY" "$RR/renderers/render_board.py" "$work/a.rr" "$work/board.html" --offline \
  >/dev/null || die "render_board errored"
if grep -q "third-party review found no compensating control" "$work/board.html" \
   && grep -q "compensating control now in place, watching" "$work/board.html" \
   && ! grep -q "reviewed at the forum" "$work/board.html"; then
  chk "$n" "rendered board change log carries the change rationales" PASS
else
  chk "$n" "rendered board change log carries the change rationales" FAIL
fi
n=$((n + 1))

# ===================== what the working view actually says ========================
# The operational panel is the deliverable, so it is asserted on rendered HTML rather
# than on the rollup it reads: every property below — an exclusive range, three non-band
# states kept apart, a note that sits BESIDE the review date — is a property of the prose,
# and a check against ctx.confirmation would pass over a panel that says the opposite.
#
# --today is passed explicitly. score_register writes ts in UTC while --today defaults to
# the local date, so on any machine west of Greenwich an unpinned render reports every
# event written this evening as -1 days old and "confirmed 0d ago" is flaky by timezone.
today="$("$PY" -c 'import json,sys
print(max(e["ts"] for e in json.load(open(sys.argv[1]))["history"])[:10])' "$work/a.rr")" \
  || die "could not read the register's newest timestamp"
yday="$("$PY" -c 'import datetime,sys
print((datetime.date.fromisoformat(sys.argv[1]) - datetime.timedelta(days=1)).isoformat())' \
  "$today")" || die "could not compute the day before $today"

# Four registers the derivation block already built, each reaching a state the others
# cannot: a.rr all-dated, u.rr one unreadable ts, b.rr no affirming event at all. The
# fourth render is a.rr as of YESTERDAY, which is the future-dated case — the only way to
# reach it without hand-editing a ts, and the case a UTC/local skew produces by itself.
for fx in a u b; do
  "$PY" "$RR/renderers/render_dashboard.py" "$work/$fx.rr" "$work/dash_$fx.html" \
    --offline --today "$today" >/dev/null || die "render_dashboard errored on $fx.rr"
done
"$PY" "$RR/renderers/render_dashboard.py" "$work/a.rr" "$work/dash_fut.html" \
  --offline --today "$yday" >/dev/null || die "render_dashboard errored at --today $yday"

set +e
"$PY" - "$work" "$RR" "$today" <<'PY' > "$work/render_out.txt" 2> "$work/render_err.txt"
import pathlib, re, sys
work, rr, today = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2]), sys.argv[3]
sys.path.insert(0, str(rr / "renderers"))
sys.path.insert(0, str(rr / "scripts"))
import _common as C

HTML = {k: (work / ("dash_%s.html" % k)).read_text() for k in ("a", "u", "b", "fut")}

emitted = [0]


def add(name, good):
    emitted[0] += 1
    print(("PASS" if good else "FAIL") + "\t" + name, flush=True)


# The six rows and the four rendered ranges, as independent literals. NOT read from
# render_dashboard.AGE_BAND_LABEL or recomputed from the threshold: rule 3 in the header —
# a fixture derived from the constant under test moves with the mutant, and a cumulative
# range built from the same expression as the panel's cannot disagree with it.
BANDS = ["inside the cadence", "nearing the cadence", "past the cadence",
         "far past the cadence"]
RANGES = ["0–90d", "91–180d", "181–360d", "over 360d"]
UNDATED = "with no confirmation on record"
UNREADABLE = "confirmed, but the date will not parse"
LABELS = BANDS + [UNDATED, UNREADABLE]
# What the same four rows would say if the ranges were made cumulative — the defect that
# shipped once on the board renderer, where "within 360 days" captioned the count of
# determinations PAST the cadence.
CUMULATIVE = ["0–180d", "0–360d"]

PANEL = re.compile(r'<h3>Confirmation age <span class="cnt">(\d+)</span></h3>(.*?)</ul>',
                   re.S)


def panel(key):
    """The rendered panel as (live, [(count, label, note)], markup), or None if absent."""
    m = PANEL.search(HTML[key])
    if not m:
        return None
    rows = []
    for li in re.findall(r"<li>(.*?)</li>", m.group(2), re.S):
        head, _, note = li.partition('<span class="d">')
        lead = re.match(r"<b>(\d+)</b>", head)      # the count leads the row, or this dies
        rows.append((int(lead.group(1)),
                     re.sub(r"<[^>]+>", "", head[lead.end():]).strip(),
                     re.sub(r"<[^>]+>", "", note).strip()))
    return {"live": int(m.group(1)), "rows": rows, "markup": m.group(2)}


pa, pu, pb = panel("a"), panel("u"), panel("b")

# Deleting the call to confirmation_panel() has to fail something, and the denominator is
# pinned at the same time: the register holds 4 risks and 1 is closed, so a rollup that
# lets the closed one in reads 4 here.
add("the panel renders with the live population as its denominator",
    pa is not None and pa["live"] == 3)
# Ranges checked as (label, range) pairs, not as a set of substrings: "181–360d" present
# somewhere in the panel does not say it is sitting on the row it describes.
add("the band ranges are exclusive, not cumulative",
    [(lab, note) for _, lab, note in pa["rows"][:4]] == list(zip(BANDS, RANGES))
    and not any(x in pa["markup"] for x in CUMULATIVE))
add("the six rows partition the live population, band by band",
    [lab for _, lab, _ in pa["rows"]] == LABELS
    and [k for k, _, _ in pa["rows"]] == [3, 0, 0, 0, 0, 0]
    and sum(k for k, _, _ in pa["rows"]) == pa["live"] == 3)
# The two non-band states are the ones a renderer conflates. u.rr has a confirmation with
# a named confirmer and an unreadable ts; b.rr has no affirming event at all. Folding the
# two rows into one leaves five rows and fails both halves.
add("undated and unreadableDate are never folded into one line",
    [(k, lab) for k, lab, _ in pu["rows"]] == list(zip([2, 0, 0, 0, 0, 1], LABELS))
    and [(k, lab) for k, lab, _ in pb["rows"]] == list(zip([0, 0, 0, 0, 3, 0], LABELS))
    and UNDATED != UNREADABLE)
# BAND is a fill ramp: as text on the white card it runs 1.68–2.61:1. Asserted as a
# measured ratio rather than as an expected hex, so the check states the property that
# matters and cannot be satisfied by a different unreadable colour. The panel is drawn
# with a coloured word in every state, so this is never vacuous — and the count is pinned
# so a colour added without a contrast opinion cannot slip past it.
inline = re.findall(r"color:(#[0-9A-Fa-f]{6})", pa["markup"])
add("every coloured word in the panel clears AA on the card surface",
    len(inline) == 1 and all(C.contrast_ratio(c, C.WB_SURF) >= 4.5 for c in inline))

# ---- the per-risk note on an attention card -------------------------------------
# Beside the existing detail, not instead of it: a review date is a deadline somebody
# committed to and the confirmation age is how long since anyone acted on it. Asserted as
# one string so replacing the detail fails even though both halves would still be present.
add("the per-risk note sits beside the existing detail, not instead of it",
    "residual 25 Critical · confirmed 0d ago · D. Alleyne" in HTML["a"])
add("an unreadable date is not captioned 'never confirmed'",
    "confirmed, but the date cannot be read: 2026-02-30 · D. Alleyne" in HTML["u"]
    and "never confirmed" not in HTML["u"])
add("a genuinely unconfirmed risk says so on its card",
    "no owner assigned · never confirmed" in HTML["b"])
add("a future-dated confirmation is named rather than printed as negative days",
    ("confirmed %s, dated in the future" % today) in HTML["fut"]
    and "-1d ago" not in HTML["fut"])

print("#DONE\t%d" % emitted[0], flush=True)
PY
render_rc=$?
set -u

read_verdicts "$work/render_out.txt" "$work/render_err.txt" "$render_rc" \
  "$EXPECTED_RENDER_CHECKS" rendered-HTML

echo
if [ "$fails" -eq 0 ]; then
  echo "confirmation-age: all $((n - 1)) checks passed"
else
  echo "confirmation-age: $fails check(s) FAILED"
fi
exit $([ "$fails" -eq 0 ] && echo 0 || echo 1)
