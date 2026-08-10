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
EXPECTED_CHECKS=55
EXPECTED_RENDER_CHECKS=27

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
  --description "If the sole logistics provider fails, then order fulfilment stops" \
  --il 4 --ii 4 --rl 3 --ri 4 --why "fixture" >/dev/null || die "add R-001"
"$PY" "$SR" add "$work/a.rr" --title "Legacy VPN appliance" \
  --description "If the unsupported VPN is exploited, then an attacker reaches the LAN" \
  --il 5 --ii 4 --rl 4 --ri 4 --why "fixture" >/dev/null || die "add R-002"
"$PY" "$SR" add "$work/a.rr" --title "Retired file share still reachable" \
  --description "If the retired share is reached, then stale records are exposed" \
  --il 3 --ii 3 --rl 2 --ri 2 --why "fixture" >/dev/null || die "add R-003"
"$PY" "$SR" add "$work/a.rr" --title "Unpatched internet-facing host" \
  --description "If the host is exploited, then an attacker gains a foothold" \
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

# ---- m.rr: one register that reaches EVERY confirmation state at once -------------
# The board sentence's whole claim is that its numbers add up, and that claim cannot fail
# on a fixture where one clause carries the entire live population: every other clause is
# dropped at zero, and the sum is then "9 == 9" over a single number. Trap A in this file's
# header, and the one Task 5 repeated on a fresh fixture — three of its six panel rows had
# no failing check because every rendered fixture had a nonzero count only in `within`.
#
# So this register is built with TEN risks by the real CLI and then re-dated in the
# derivation block below: within, approaching, beyond, wellBeyond ×2, future-dated,
# unreadable ts, NO AFFIRMING EVENT AT ALL ×2, and one closed risk that must not appear in
# any of them.
#
# The ×2 on undated is not symmetry for its own sake. With undated and unreadableDate both
# at exactly 1, no NUMBER in the sentence can tell them apart and only the captions are
# pinned — so swapping the two count expressions while leaving the captions alone passed the
# whole suite. That is the same vacuity this fixture was built to close, closed for the four
# bands and left open for the two states most easily conflated. Distinct counts make the
# cross-wiring arithmetically visible.
#
# Titles are deliberately long, because a check that no title fragment reaches a board
# sentence proves nothing over titles too short to notice.
"$PY" "$SR" init "$work/m.rr" --client "Mixed Co" --assessor "D. Alleyne" >/dev/null \
  || die "init m.rr"
while IFS= read -r t; do
  [ -n "$t" ] || continue
  # The description is required from v0.78.0 (BL-81) and is not what this suite
  # measures, so it is derived from the title rather than written out per row.
  "$PY" "$SR" add "$work/m.rr" --title "$t" --il 4 --ii 4 --rl 3 --ri 3 \
    --description "If $t is not addressed, then the exposure is realised" \
    --why "fixture" >/dev/null || die "add to m.rr: $t"
done <<'TITLES'
Supplier concentration in a single payment processor
Legacy VPN appliance past vendor support
Privileged access reviews not evidenced quarterly
Backup restoration never tested end to end
Third-party data processor onboarded without an assessment
Detection coverage absent across the finance estate
Incident response plan not exercised since 2024
Unpatched internet-facing file transfer service
Shadow IT sanctioned without a security review
Retired file share still reachable from the corporate LAN
TITLES
"$PY" "$SR" set-status "$work/m.rr" R-010 closed \
  --why "decommissioned and verified" >/dev/null || die "set-status R-010 closed"

set +e
"$PY" - "$work" "$RR" <<'PY' > "$work/out.txt" 2> "$work/err.txt"
import json, os, sys, pathlib, argparse, subprocess, time
from datetime import date, datetime, timedelta, timezone
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
# futureDated is a NAMED SUBSET of `within`, not a fifth band and not a summand. The same
# register read one day earlier gives every live risk an age of -1, which age_band()
# reports as `within` on purpose — so the rollup has to be able to say "these three fresh
# ones are a broken record" without the partition reading 6. Both halves matter: the count
# has to appear when there are future dates, and stay 0 when there are none, or a renderer
# reading it prints a defect disclosure on every clean register.
cfu = ctx(today=(base - timedelta(days=1)).isoformat())
add("futureDated is a named subset of within, not a fifth band",
    cfu.confirmation["futureDated"] == 3
    and [r["id"] for r in cfu.confirmation["futureDatedRisks"]]
    == ["R-001", "R-002", "R-004"]
    and cfu.confirmation["bands"] == {"within": 3, "approaching": 0,
                                      "beyond": 0, "wellBeyond": 0}
    and sum(cfu.confirmation["bands"].values()) + cfu.confirmation["undated"]
    + cfu.confirmation["unreadableDate"] == cfu.confirmation["live"] == 3
    and c.confirmation["futureDated"] == 0
    and c.confirmation["futureDatedRisks"] == [])

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

# One corrupt event must not cost a risk the good confirmation sitting beside it. This is
# the ordering half of the same trap: "not-a-date" sorts above every ISO date ('n' > '2'),
# so a plain lexicographic max hands the latest-affirming slot to the corrupt event and the
# risk reports unreadableDate while holding a readable, genuinely later one. A readable ts
# has to win regardless of how the two compare as strings.
rawmix = json.loads((work / "a.rr").read_text())
_seen = False
for e in rawmix["history"]:
    if e.get("riskId") == "R-001" and e["type"] in AFFIRMING_LITERAL and not _seen:
        e["ts"] = "not-a-date"          # sorts ABOVE any ISO date
        _seen = True
rawmix["history"].append({"ts": base.isoformat() + "T09:00:00Z", "actor": "D. Alleyne",
                          "riskId": "R-001", "type": "risk-confirmed",
                          "rationale": "readable, and later in real time"})
(work / "mix.rr").write_text(json.dumps(rawmix))
add("the corrupt event the fixture needs really is there and really does sort highest",
    _seen and max(str(e["ts"]) for e in rawmix["history"]
                  if e.get("riskId") == "R-001") == "not-a-date")
cmix = ctx("mix.rr")
add("a readable ts wins over an unreadable one that sorts above it",
    cmix.by_id["R-001"]["lastConfirmedAt"] == base.isoformat()
    and cmix.by_id["R-001"]["confirmationAgeDays"] == 0
    and cmix.by_id["R-001"]["confirmationBand"] == "within")
add("so one corrupt event does not push the risk into unreadableDate",
    cmix.confirmation["unreadableDate"] == 0 and cmix.confirmation["undated"] == 0
    and sum(cmix.confirmation["bands"].values()) == cmix.confirmation["live"] == 3)

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


# ==================== --today is UTC, not the local date =========================
# A live defect, not a style question: score_register writes every ts in UTC and --today
# defaulted to date.today(), the LOCAL date. West of Greenwich an event written this
# evening is dated tomorrow, the age comes back negative, and age_band() reports a
# negative age as `within` — so a register skewed a day forward reads as FRESHER than it
# is, on the board page.
#
# Asserted by forcing two zones 26 hours apart rather than by comparing against the UTC
# date once. `date.today() == utcnow().date()` is true for most of the day on most
# machines, so a single comparison lets the local-date mutant survive by wall clock — the
# assertion would only bind in the evening, in California. Two offsets 26h apart can never
# share a local date, so `east == west` fails for date.today() at every instant, and
# membership in the UTC date sampled either side pins WHICH date it is without a
# midnight-rollover flake.
def _in_zone(tz, thunk):
    """Run `thunk` with TZ forced to `tz`, restoring TZ whatever happens.

    Both the assignment and the tzset are INSIDE the try. With the assignment outside it, a
    platform where time.tzset() does not exist leaks TZ into every check after this one
    instead of restoring it.
    """
    old = os.environ.get("TZ")
    try:
        os.environ["TZ"] = tz
        time.tzset()
        return thunk()
    finally:
        if old is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = old
        time.tzset()


EAST, WEST = "Pacific/Kiritimati", "Etc/GMT+12"      # UTC+14 and UTC-12, 26 hours apart


def _default_today(tz):
    return _in_zone(tz, lambda: C.parse_args([str(work / "a.rr")], "d", "o.html").today)


# THE POSITIVE CONTROL, and the check below is worthless without it. The whole argument is
# that two offsets 26 hours apart can never share a local date, so `east == west` cannot be
# satisfied by date.today(). That argument silently evaporates on an image with no zone
# database — a python:3-alpine or a -slim without tzdata — where both names fail to resolve,
# both collapse to UTC+0, and the local-date mutant passes. So the zones are proved to be
# doing something first: they must yield DIFFERENT local dates, which is exactly the
# property the next check relies on and exactly what a missing tzdata destroys.
_zones_bind = _in_zone(EAST, lambda: date.today().isoformat()) \
    != _in_zone(WEST, lambda: date.today().isoformat())
add("the two test zones really are a day apart (tzdata present)", _zones_bind)
_u1 = datetime.now(timezone.utc).strftime("%Y-%m-%d")
_east = _default_today(EAST)
_west = _default_today(WEST)
_u2 = datetime.now(timezone.utc).strftime("%Y-%m-%d")
# Guarded by the control above rather than merely accompanied by it: without `_zones_bind`
# this reports PASS on a machine where it proved nothing at all.
add("--today defaults to the UTC date and does not move with the local zone",
    _zones_bind and _east == _west and _east in (_u1, _u2))

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

# ================= age_bounds restates age_band's boundaries =====================
# renderers/_common.age_bounds() is the one place the t // 2 arithmetic lives in this
# skill's renderers: the board sentence and render_dashboard's `edges` dict both read it,
# and neither derives a boundary of its own any more. It restates sr.age_band()'s
# boundaries, and two statements of one rule that nothing compares will drift — so every
# edge is walked against the engine, at three cadences including one absurdly small. The
# literal for T=180 is the independent statement rule 3 requires: checked against
# age_band() alone, a mutant that broke both consistently would still agree with itself.
# id_list is the one route by which a count on a board page or an operational row names the
# risks behind it, and the cap is the part no fixture below reaches: the widest list any of
# them produces is three IDs, against caps of 5 and 6. Asserted directly rather than left
# uncovered, escaping included — an id is register data and reaches HTML unquoted otherwise.
# `cap` is passed at every call, here included: it has no default, because the one it had
# was 6 and no caller ever used it.
add("id_list caps, says how many it withheld, and escapes",
    C.id_list([{"id": "R-%03d" % i} for i in range(1, 9)], cap=5)
    == "R-001, R-002, R-003, R-004, R-005 +3 more"
    and C.id_list([{"id": "R-001"}], cap=5) == "R-001"
    and C.id_list([{"id": "R-1 & 2"}], cap=5) == "R-1 &amp; 2"
    and C.id_list([], cap=5) == ""
    and raises(lambda: C.id_list([{"id": "R-001"}])))

add("age_bounds restates age_band's boundaries exactly",
    all(sr.age_band(lo, t) == b
        and (hi is None or (sr.age_band(hi, t) == b and sr.age_band(hi + 1, t) != b))
        for t in (7, 180, 365)
        for b, (lo, hi) in C.age_bounds(t).items())
    and [C.age_bounds(180)[b] for b in sr.AGE_BANDS]
    == [(0, 90), (91, 180), (181, 360), (361, None)])

# =========== the mixed fixture: every state at once, for the board sentence ==========
# Re-dated here rather than in the shell because `base` and `today` above are the same
# reference date the renders are given, so a run that straddles UTC midnight cannot leave
# the fixture and the render a day apart. Ages are set through AFFIRMING_LITERAL, not
# through sr.AGE_AFFIRMING: rule 3 again.
#
#   R-001    age 0        within
#   R-002    age 120      approaching   (T=180: 91–180)
#   R-003    age 200      beyond        (T=180: 181–360)
#   R-004    age 400      wellBeyond    named second — 400 days
#   R-005    age 500      wellBeyond    named first  — oldest
#   R-006    ts unreadable              confirmed, distance unknown          -> 1 of these
#   R-007    no affirming event         never confirmed                      -> 2 of these,
#   R-009    no affirming event         never confirmed                         so the two
#                                                                              non-band
#                                                                              states differ
#                                                                              by count and
#                                                                              not only by
#                                                                              caption
#   R-008    age -3       future-dated  lands in `within` per age_band, and must not be
#                                       reported there
#   R-010    closed                     in none of the above
MIXED_AGES = {"R-001": 0, "R-002": 120, "R-003": 200, "R-004": 400, "R-005": 500,
              "R-008": -3}
MIXED_UNDATED = ("R-007", "R-009")
rawm = json.loads((work / "m.rr").read_text())
keep = []
for e in rawm["history"]:
    rid = e.get("riskId")
    if e["type"] in AFFIRMING_LITERAL and rid in MIXED_AGES:
        e["ts"] = (base - timedelta(days=MIXED_AGES[rid])).isoformat() + "T09:00:00Z"
    elif e["type"] in AFFIRMING_LITERAL and rid == "R-006":
        e["ts"] = "2026-02-30T09:00:00Z"          # lexically fine, arithmetically not
    elif e["type"] in AFFIRMING_LITERAL and rid in MIXED_UNDATED:
        continue                                   # never affirmed at all
    keep.append(e)
rawm["history"] = keep
(work / "m.rr").write_text(json.dumps(rawm))
# A sidecar so the board can be rendered down BOTH summary_block branches. Without it only
# the placeholder branch is ever exercised, and deleting the freshness call from the
# narrative branch would ship silently.
(work / "tr.json").write_text(json.dumps({
    "executiveSummary": "Exposure is concentrated in supplier and remote-access risk; "
                        "two of the four themes moved the wrong way this quarter."}))

# Pinned HERE, not implied by the render checks that depend on it. Every board-sentence
# check below is only as strong as this fixture: if the mixed register collapsed back into
# "everything is `within`", the sum would be 8 == 8 over one clause and six checks would
# pass over nothing.
cm = ctx("m.rr")
add("the mixed fixture reaches every confirmation state at once",
    cm.confirmation["bands"] == {"within": 2, "approaching": 1,
                                 "beyond": 1, "wellBeyond": 2}
    # Different numbers, deliberately: equal counts here make every downstream check blind
    # to the two being cross-wired.
    and cm.confirmation["undated"] == 2 and cm.confirmation["unreadableDate"] == 1
    and cm.confirmation["futureDated"] == 1
    and [r["id"] for r in cm.confirmation["futureDatedRisks"]] == ["R-008"]
    and [r["id"] for r in cm.confirmation["wellBeyond"]] == ["R-005", "R-004"]
    and cm.confirmation["live"] == 9 and len(cm.risks) == 10
    and cm.by_id["R-010"]["status"] == "closed")

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
day_off() { "$PY" -c 'import datetime,sys
print((datetime.date.fromisoformat(sys.argv[1])
       + datetime.timedelta(days=int(sys.argv[2]))).isoformat())' "$today" "$1"; }
yday="$(day_off -1)"  || die "could not compute the day before $today"
t120="$(day_off 120)" || die "could not compute $today + 120"
t200="$(day_off 200)" || die "could not compute $today + 200"
t400="$(day_off 400)" || die "could not compute $today + 400"

# NINE renders, because a panel is only as testable as the states a fixture can reach.
# Four registers the derivation block already built — a.rr all-dated, u.rr one unreadable
# ts, b.rr no affirming event at all, m.rr every state at once — read as of five different
# days and two cadences:
#
#   dash_a       $today       T=180   every live risk age 0            -> within 3
#   dash_u       $today       T=180   one unreadable ts                -> within 2, unread. 1
#   dash_b       $today       T=180   no affirming event               -> undated 3
#   dash_fut     $today - 1   T=180   ages of -1: future-dated records
#   dash_appr    $today + 120 T=180   ages of 120                      -> approaching 3
#   dash_beyond  e.rr + 200   T=180   ages of 200, later edits ignored -> beyond 3
#   dash_far     $today + 400 T=180   ages of 400                      -> wellBeyond 3
#   dash_t365    $today + 400 T=365   the SAME 400 days, other cadence -> beyond 3
#   dash_m       $today       T=180   m.rr: every state at once, and only ONE of the three
#                                     `within` risks is future-dated
#
# The last five are not padding. With only the first three, every dated risk sits in
# `within` and nothing rendered can distinguish a band count from the constant 0: pinning
# [3,0,0,0,0,0] on a fixture that cannot produce a nonzero `beyond` is the vacuity class
# this plan tabulated. And read at T=180 alone the ranges cannot tell "derived from t" from
# "the argparse default", which is the mutant that survived a whole earlier suite — so the
# eighth render puts the same 400-day age against a different cadence, exactly as the
# derivation block's 180/1000 pair does for the bands.
#
# dash_m closes the last one of that class on this panel. On dash_fut all three live risks
# are future-dated, so `bands["within"]` and `futureDated` are BOTH 3 and the row's
# disclosure cannot tell one from the other — wiring the count to the band count survives.
# m.rr puts 2 in `within` of which 1 is future-dated, so the two numbers differ and the
# panel has to be reading the right one. It is the same register the board sentence is
# asserted on, deliberately: the two artifacts are read side by side over one register, and
# rendering both from m.rr is what lets them be compared.
for fx in a u b; do
  "$PY" "$RR/renderers/render_dashboard.py" "$work/$fx.rr" "$work/dash_$fx.html" \
    --offline --today "$today" >/dev/null || die "render_dashboard errored on $fx.rr"
done
"$PY" "$RR/renderers/render_dashboard.py" "$work/a.rr" "$work/dash_fut.html" \
  --offline --today "$yday" >/dev/null || die "render_dashboard errored at --today $yday"
"$PY" "$RR/renderers/render_dashboard.py" "$work/a.rr" "$work/dash_appr.html" \
  --offline --today "$t120" >/dev/null || die "render_dashboard errored at --today $t120"
"$PY" "$RR/renderers/render_dashboard.py" "$work/e.rr" "$work/dash_beyond.html" \
  --offline --today "$t200" >/dev/null || die "render_dashboard errored on e.rr"
"$PY" "$RR/renderers/render_dashboard.py" "$work/a.rr" "$work/dash_far.html" \
  --offline --today "$t400" >/dev/null || die "render_dashboard errored at --today $t400"
"$PY" "$RR/renderers/render_dashboard.py" "$work/a.rr" "$work/dash_t365.html" \
  --offline --today "$t400" --age-threshold 365 >/dev/null \
  || die "render_dashboard errored at --age-threshold 365"
"$PY" "$RR/renderers/render_dashboard.py" "$work/m.rr" "$work/dash_m.html" \
  --offline --today "$today" >/dev/null || die "render_dashboard errored on m.rr"

# THREE board renders of the mixed register. Operational views get the distribution; the
# board gets one sentence, so the sentence is asserted on rendered prose — the defect this
# guards against lives in the wording, and a check against ctx.confirmation would pass over
# a sentence that says the opposite of it.
#
#   board_m180   T=180, no sidecar   the placeholder branch of summary_block
#   board_mtr    T=180, --translations  the narrative branch — same sentence, other branch
#   board_m365   T=365, no sidecar   identical data, another cadence, therefore other ranges
#
# The third is not padding. Read at T=180 alone, "within the last 90 days" cannot tell a
# boundary derived from t from a hardcoded 90, because 180 is also the argparse default —
# the mutant that survived a whole earlier suite. The second exists because summary_block
# has two branches and the sentence has to be on both: without it, deleting the call from
# the narrative branch ships, and a board pack rendered WITH board language is the one that
# reaches a board.
"$PY" "$RR/renderers/render_board.py" "$work/m.rr" "$work/board_m180.html" \
  --offline --today "$today" >/dev/null || die "render_board errored on m.rr"
"$PY" "$RR/renderers/render_board.py" "$work/m.rr" "$work/board_mtr.html" \
  --offline --today "$today" --translations "$work/tr.json" >/dev/null \
  || die "render_board errored on m.rr with --translations"
"$PY" "$RR/renderers/render_board.py" "$work/m.rr" "$work/board_m365.html" \
  --offline --today "$today" --age-threshold 365 >/dev/null \
  || die "render_board errored on m.rr at --age-threshold 365"
# A FOURTH board render, on the shipped example register with an --today behind every
# confirmation in it. references/dashboards.md tells the reader to pass --today for a
# reproducible "as of" view, and doing so makes every sound record "dated after the
# reference date": nine good records that a clause calling them a defect would libel on a
# board page. Rendered from examples/ rather than a built fixture on purpose — this is the
# artifact a user gets by following the documentation.
"$PY" "$RR/renderers/render_board.py" "$RR/examples/example-register-v2.rr" \
  "$work/board_asof.html" --offline --today 2026-06-30 >/dev/null \
  || die "render_board errored on the shipped example at --today 2026-06-30"

# TWO renders of the PRINTABLE REPORT, which is the second board-facing artifact and the one
# board-safety.sh's own header is about: the title guard was written into the executive
# dashboard first and the report kept exposing raw framework wording for a full release
# afterwards. A board caveat wired into one of two board pages is that mistake in progress,
# so the report's freshness sentence gets asserted on rendered prose exactly as the board's
# does — same register, same reference date, so the two sentences can be compared directly
# rather than each being checked against its own idea of the register.
#
# Both branches of exec_summary(), for the same reason board_m180/board_mtr are both here:
# the placeholder branch is the page most likely to be read off the numbers alone, and the
# narrative branch is the one a real board pack takes. Deleting the call from either has to
# fail, and with one render only, one of the two deletions ships.
#
#   report_m180  T=180, no sidecar      the placeholder branch
#   report_mtr   T=180, --translations  the narrative branch
"$PY" "$RR/renderers/render_report.py" "$work/m.rr" "$work/report_m180.html" \
  --offline --today "$today" >/dev/null || die "render_report errored on m.rr"
"$PY" "$RR/renderers/render_report.py" "$work/m.rr" "$work/report_mtr.html" \
  --offline --today "$today" --translations "$work/tr.json" >/dev/null \
  || die "render_report errored on m.rr with --translations"

set +e
"$PY" - "$work" "$RR" "$today" <<'PY' > "$work/render_out.txt" 2> "$work/render_err.txt"
import argparse, json, pathlib, re, sys
from datetime import date, timedelta
work, rr, today = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2]), sys.argv[3]
sys.path.insert(0, str(rr / "renderers"))
sys.path.insert(0, str(rr / "scripts"))
import _common as C
import render_dashboard as rd
import score_register as sr

HTML = {k: (work / ("dash_%s.html" % k)).read_text()
        for k in ("a", "u", "b", "fut", "appr", "beyond", "far", "t365", "m")}
BOARD = {k: (work / ("board_%s.html" % k)).read_text()
         for k in ("m180", "mtr", "m365", "asof")}
REPORT = {k: (work / ("report_%s.html" % k)).read_text() for k in ("m180", "mtr")}

emitted = [0]


def add(name, good):
    emitted[0] += 1
    print(("PASS" if good else "FAIL") + "\t" + name, flush=True)


def cx(path="a.rr", **over):
    """A Context over one of the fixture registers, for the two checks that need one."""
    args = argparse.Namespace(register=str(work / path), out=str(work / "y.html"),
                              today=today, translations=None, offline=True,
                              age_threshold=C.DEFAULT_AGE_THRESHOLD)
    for k, v in over.items():
        setattr(args, k, v)
    return C.Context(args)


# The six rows and the four rendered ranges, as independent literals. NOT read from
# render_dashboard.AGE_BAND_LABEL or recomputed from the threshold: rule 3 in the header —
# a fixture derived from the constant under test moves with the mutant, and a cumulative
# range built from the same expression as the panel's cannot disagree with it.
BANDS = ["inside the cadence", "nearing the cadence", "past the cadence",
         "far past the cadence"]
RANGES = ["0–90d", "91–180d", "181–360d", "over 360d"]           # T=180, the default
RANGES_365 = ["0–182d", "183–365d", "366–730d", "over 730d"]     # T=365, and 365//2 == 182
UNDATED = "with no confirmation on record"
UNREADABLE = "confirmed, but the date will not parse"
LABELS = BANDS + [UNDATED, UNREADABLE]
NOTES = ["no affirming event exists at all — not an age of zero",
         "an affirming event exists — only the distance is unknown"]
# What the same four rows would say if the ranges were made cumulative — the defect that
# shipped once on the board renderer, where "within 360 days" captioned the count of
# determinations PAST the cadence.
CUMULATIVE = ["0–180d", "0–360d"]
# Causes no surface in this skill may claim for a future-dated confirmation. Shared by the
# operational panel and the board sentence deliberately: the rule is the same on both, and
# the difference between them is how blunt the FACT may be, not whether a diagnosis is
# allowed. references/dashboards.md tells the reader to pass --today for a reproducible
# "as of" view, which puts entirely sound records in that state, so "a file defect" is not a
# stricter statement of the truth — it is a false one. It shipped on both pages.
DIAGNOSES = ["record defect", "file defect", "broken record", "not a recent review",
             "rather than a recent review", "hand-edited", "clock"]

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


def vec(p):
    """The six counts, in row order."""
    return [k for k, _, _ in p["rows"]]


def labels(p):
    return [lab for _, lab, _ in p["rows"]]


# Deleting the call to confirmation_panel() has to fail something, and the denominator is
# pinned at the same time: the register holds 4 risks and 1 is closed, so a rollup that lets
# the closed one in reads 4 here. Read on all three fixtures, because `live` taken as
# sum(bands.values()) is right on a.rr and silently drops both non-band states on the other
# two — while the caption above it still says it accounts for every live risk.
add("the panel renders with the live population as its denominator",
    pa is not None and pu is not None and pb is not None
    and (pa["live"], pu["live"], pb["live"]) == (3, 3, 3))
# Ranges checked as (label, range) pairs, not as a set of substrings: "181–360d" present
# somewhere in the panel does not say it is sitting on the row it describes.
add("the band ranges are exclusive, not cumulative",
    [(lab, note) for _, lab, note in pa["rows"][:4]] == list(zip(BANDS, RANGES))
    and not any(x in pa["markup"] for x in CUMULATIVE))
# The same four rows at T=365 — 400 days of age against a cadence that is not the argparse
# default. Read at 180 alone, "0–90d" cannot tell a boundary derived from t from a hardcoded
# 90, because 180 is also the default: `half = 90` survives every check above it. The
# derivation block learned this in writing about thresholdDays; the ranges have the same
# hole, and the caption's own denominator is pinned with them.
pt = panel("t365")
add("the ranges rescale with the cadence, they are not the argparse default",
    [(lab, note) for _, lab, note in pt["rows"][:4]] == list(zip(BANDS, RANGES_365))
    and "against the 365-day cadence" in HTML["t365"]
    and RANGES_365[0] not in HTML["a"])
# Full triples, so the sub-notes are pinned too. With labels and counts alone, swapping the
# undated row's note for "confirmed within the cadence" — a flattering caption contradicting
# its own correct label — passed everything.
add("the six rows partition the live population, band by band",
    pa["rows"] == list(zip([3, 0, 0, 0, 0, 0], LABELS, RANGES + NOTES))
    and sum(vec(pa)) == pa["live"] == 3)
# The two non-band states are the ones a renderer conflates. u.rr has a confirmation with
# a named confirmer and an unreadable ts; b.rr has no affirming event at all. Folding the
# two rows into one leaves five rows and fails both halves.
add("undated and unreadableDate are never folded into one line",
    [(k, lab) for k, lab, _ in pu["rows"]] == list(zip([2, 0, 0, 0, 0, 1], LABELS))
    and [(k, lab) for k, lab, _ in pb["rows"]] == list(zip([0, 0, 0, 0, 3, 0], LABELS))
    and UNDATED != UNREADABLE)
# Every band count read from its own band. Nothing above this can fail if `approaching`,
# `beyond` and `wellBeyond` are hardcoded to 0 or read from each other's keys, because on
# a.rr, u.rr and b.rr they ARE 0 — every dated risk in those three is age 0. So the same
# three risks are read at three ages, one per band, and the vector is pinned each time. The
# fourth arm is the payoff of the eighth render: identical data, identical ages, a different
# cadence, and therefore a different row — a band count wired to a constant cannot do that.
pap, pbe, pfa = panel("appr"), panel("beyond"), panel("far")
add("every band count is read from its own band, not from a neighbour or a constant",
    vec(pap) == [0, 3, 0, 0, 0, 0] and vec(pbe) == [0, 0, 3, 0, 0, 0]
    and vec(pfa) == [0, 0, 0, 3, 0, 0] and vec(pt) == [0, 0, 3, 0, 0, 0]
    and labels(pap) == labels(pbe) == labels(pfa) == LABELS)
# Not "is the hex we expect" but "is it readable, and did anyone hand-copy a colour". The
# panel takes .warnmark, the class this page already uses for a broken record, so the
# judgement lives once in CSS; BAND as text runs 1.68:1 (medium) to 5.44:1 (critical), with
# `high` at 2.61:1, and four hand-copied copies of one such judgement is what text_on()
# exists to prevent. Both halves are needed: the ratio catches BAND swapped for BAND_TEXT in
# the CSS rule, the emptiness catches a colour re-inlined into the panel to dodge the class.
inline = re.findall(r"color:(#[0-9A-Fa-f]{6})", pa["markup"])
css = re.search(r"<style>(.*?)</style>", HTML["a"], re.S).group(1)
used = sorted({c for grp in re.findall(r'class="([^"]+)"', pa["markup"]) for c in grp.split()})
declared = {}
for cls in used:
    rule = re.search(r"\.%s\{([^}]*)\}" % re.escape(cls), css)
    hit = re.search(r"color:(#[0-9A-Fa-f]{6})", rule.group(1)) if rule else None
    if hit:
        declared[cls] = hit.group(1)
add("the panel hand-inlines no colour, and every class it does use clears AA",
    not inline and "warnmark" in declared
    and all(C.contrast_ratio(v, C.WB_SURF) >= 4.5 for v in declared.values()))
# The keys, against the engine's own tuple rather than against a second copy of the list.
# A missing key only raises KeyError at render time and an extra one is silent, so nothing
# in the renderer notices either. nist-csf pins the equivalent in its self-test and says
# outright that it is not optional; this is that check for this side.
add("AGE_BAND_LABEL covers exactly the engine's four bands, no more",
    sorted(rd.AGE_BAND_LABEL) == sorted(sr.AGE_BANDS) and len(sr.AGE_BANDS) == 4)

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

# ---- what the panel does with the states the cards refuse to flatter -------------
# The same page, one card apart, must not say two things. age_band() reports a negative age
# as `within` on purpose, so those records land on the "0–90d" row — false in the flattering
# direction, and the exact shape of the labelling defect this panel's own comments cite.
# Disclosed on the row rather than rebanded; the arithmetic in age_band() is untouched.
pfu, pm = panel("fut"), panel("m")
yday = (date.fromisoformat(today) - timedelta(days=1)).isoformat()
add("the within row discloses future-dated records instead of absorbing them",
    pfu["rows"][0][0] == 3
    and ("includes 3 dated after the %s reference date (R-001, R-002, R-004), so no age "
         "can be measured for them" % yday) in pfu["rows"][0][2]
    # ...and only when there are any. A note that always says it says nothing.
    and pa["rows"][0][2] == RANGES[0])
# The count on that note, against a fixture where it is NOT the band count. On dash_fut all
# three live risks are future-dated, so `bands["within"]` and `futureDated` are both 3 and
# wiring the disclosure to the band — or rebuilding the list with a comprehension that drifts
# from the rollup's — passes the check above. m.rr puts 2 risks in `within` of which 1 is
# future-dated, so the row must print 2 and disclose 1, and no single number satisfies both.
# The whole vector is pinned with it, because this is the only render where all six rows are
# nonzero at once and the panel's own "these six rows account for all N" claim can be checked
# against a real distribution rather than against one clause carrying everybody.
add("the disclosure counts the future-dated records, not the whole within band",
    vec(pm) == [2, 1, 1, 2, 2, 1] and sum(vec(pm)) == pm["live"] == 9
    and labels(pm) == LABELS
    and pm["rows"][0][2].startswith(RANGES[0] + " · includes 1 dated after the ")
    and ("includes 1 dated after the %s reference date (R-008), so no age can be measured "
         "for them" % today) in pm["rows"][0][2]
    and pm["rows"][3][2] == "over 360d · R-005, R-004")
# The fact, never the cause — the same rule the board sentence is held to, asserted here on
# the operational page. This reader is the one who can go and look at the file, which lowers
# the bar on how blunt the fact may be and does not license a diagnosis: the row said "a
# negative age is a file defect", which is simply false on the documented --today workflow.
# Asserted on both fixtures that reach the state, and the positive half is what stops it
# being an inverted check that reads a page with no such note on it.
add("the panel's future-dated note states the fact and never diagnoses a cause",
    not any(d in p["markup"] for p in (pfu, pm) for d in DIAGNOSES)
    and all("dated after the" in p["markup"] and "so no age can be measured for them"
            in p["markup"] for p in (pfu, pm)))
# A count the reader cannot act on is not a work queue. A wellBeyond risk that is not over
# appetite, overdue, unowned or accepted appears on no attention card and in no column of
# the register table, so the row names it. IDs, never titles.
add("the wellBeyond row names the risks it counts",
    pfa["rows"][3][2] == "over 360d · R-001, R-002, R-004"
    and pa["rows"][3][2] == RANGES[3]
    and not any(r["title"][:20] in pfa["markup"] for r in cx().risks))
# Not an attention list. Inside attgrid under "Needs attention" the panel said that risks
# INSIDE the cadence are risks needing attention, and gave .cnt two meanings on one screen.
add("the panel is its own section, not one of the attention lists",
    "Confirmation age" not in rd.attention_lists(cx())
    and "<h2>How old these determinations are</h2>" in HTML["a"]
    and "<h2>Needs attention</h2>" in HTML["a"])

# ======================= what the BOARD sentence actually says ======================
# Operational views get the distribution; board views get one sentence. Everything below is
# asserted on rendered prose rather than on ctx.confirmation, because every defect it guards
# against is a defect of the WORDING: a clause that reports a cumulative range over an
# exclusive count, a remainder left silent so the numbers do not add up, an unreadable date
# captioned as an absent confirmation, a title where an ID belongs. The rollup can be
# perfectly correct while the sentence over it is false and flattering, and that combination
# has shipped on this renderer before.
FRESH = re.compile(r'<div class="note freshness">(.*?)</div>', re.S)


def fresh_text(html):
    """The freshness sentence of any rendered page as plain text, or None if it has none."""
    m = FRESH.search(html)
    return re.sub(r"<[^>]+>", "", m.group(1)).strip() if m else None


def sentence(key):
    return fresh_text(BOARD[key])


s180, str_, s365 = sentence("m180"), sentence("mtr"), sentence("m365")
# The documented as-of workflow, on the SHIPPED example register: --today behind every
# confirmation in the file. Every record in it is sound, and the future-dated clause has to
# be true of them anyway. This is the fixture the reviewer's finding was reproduced on.
s_asof = sentence("asof")
# Every check below leads with this rather than substring-testing a None and taking the
# whole block down with a TypeError. A missing sentence must report as the failure it is —
# "cites IDs, never titles" and "is never captioned as absent" would BOTH be vacuously true
# of a sentence that does not exist, so the guard is `is not None`, never `or ""`.
rendered = s180 is not None and str_ is not None and s365 is not None

# Both branches of summary_block. The narrative branch is the one a real board pack takes,
# and the two must carry the SAME sentence — a freshness line that differs by whether board
# language was supplied is two sentences to keep in step forever.
add("the freshness sentence renders on both summary_block branches",
    s180 is not None and str_ is not None and s180 == str_
    and BOARD["m180"].count('class="note freshness"') == 1
    and BOARD["mtr"].count('class="note freshness"') == 1
    # ...and the two pages really are the two different branches, or this compares one
    # rendering with a copy of itself and cannot fail.
    and "Executive narrative from the ciso-board-translation skill" in BOARD["mtr"]
    and C.PLACEHOLDER in BOARD["m180"])

# THE SECOND BOARD-FACING RENDERER, and the reason this check exists rather than being left
# to whoever remembers. board-safety.sh's header records what happened last time: the title
# guard was written into the executive dashboard first, and the printable report — the artifact
# most likely to be handed round a table on paper — kept exposing raw framework wording for a
# full release. freshness_line() lives in _common.py so that both renderers call one sentence;
# this asserts that both actually do.
#
# Identical prose, not merely "a sentence is present". The same register at the same reference
# date must produce the same caveat on both pages, because a director and the CISO read these
# artifacts over one register and two freshness wordings would be two things to keep in step
# forever. Compared against s180 — the board's own — rather than against a literal, so the two
# cannot drift apart while both still matching a copied expectation.
#
# Both branches of exec_summary(), and the two pages are proved to BE the two branches: with
# one render only, deleting the call from the other branch ships. The report's attribution note
# is worded differently from the board's ("generated by" against "from"), which is why the
# branch is identified by that page's own string and not by the board's.
r180, rtr = fresh_text(REPORT["m180"]), fresh_text(REPORT["mtr"])
add("the printable report carries the same freshness sentence, on both branches",
    r180 is not None and rtr is not None and rendered
    and r180 == rtr == s180
    and REPORT["m180"].count('class="note freshness"') == 1
    and REPORT["mtr"].count('class="note freshness"') == 1
    and "Executive narrative generated by the ciso-board-translation skill" in REPORT["mtr"]
    and C.PLACEHOLDER in REPORT["m180"])


def sum_problem(s):
    """"" if the clause counts sum to the sentence's own denominator, else why not.

    The leading integer of each semicolon-separated clause, against the "Of N live risks"
    the sentence opens with. Digits inside day ranges and inside parenthesised risk IDs are
    not clause leads and are not counted.
    """
    if s is None:
        return "no freshness sentence rendered at all"
    m = re.match(r"Of (\d+) live risks?: (.*?)\. Age is reported so the board", s, re.S)
    if not m:
        return "sentence is not in the expected shape: %.90s" % s
    total = int(m.group(1))
    parts = [c.strip() for c in m.group(2).split(";")]
    counts = [int(re.match(r"(\d+)", p).group(1)) for p in parts if re.match(r"(\d+)", p)]
    if len(counts) != len(parts):
        return "a clause does not begin with a count: %r" % (parts,)
    if sum(counts) != total:
        return "clauses sum to %d, sentence says %d live risks" % (sum(counts), total)
    return ""


# The clause counts are pinned as well as summed. A sum alone cannot fail on a register
# where one clause carries everybody: seven clauses at T=180 and six at T=365 (wellBeyond
# empties at the wider cadence) is what makes the sum a real constraint.
#
# WHAT THIS CHECK DOES NOT CATCH, stated because the comment here previously claimed the
# opposite: a denominator computed AS the sum of the clauses passes, and was verified to
# pass. The partition guarantees sum == live, so the two expressions agree on every register
# that satisfies the rollup's own invariant, and no fixture can separate them. What the sum
# does catch is the defect it was written for — a clause dropped, doubled, or made cumulative
# so the printed numbers stop accounting for the printed denominator. The independent literal
# below ("Of 9 live risks", against a register of ten with one closed) is what pins the
# denominator itself.
add("the freshness clauses sum to the sentence's own denominator, at two cadences",
    rendered and sum_problem(s180) == "" and sum_problem(s365) == ""
    and s180.startswith("Of 9 live risks: ")
    and len(s180.split(";")) == 7 and len(s365.split(";")) == 6)

# IDs only, never titles. An imported gap carries raw CSF framework wording until somebody
# rewords it; that wording has reached a board page by three separate routes already, and
# this sentence must not be a fourth. Non-vacuous by construction: every title in m.rr is
# long enough that a fragment of it would be unmistakable.
mreg = json.loads((work / "m.rr").read_text())
mtitles = [r["title"] for r in mreg["risks"]]
add("the freshness sentence cites IDs and never titles",
    rendered and len([t for t in mtitles if len(t) > 25]) == 10
    and not any(t[:25] in s180 for t in mtitles)
    and not any(t[:25] in s365 for t in mtitles)
    # ...and it does name the risks it counts, or "contains no title" is also true of a
    # sentence that names nothing at all.
    and "(R-005, R-004)" in s180 and "(R-008)" in s180)

# The three non-band states, kept apart in the prose. `unreadableDate` means a confirmation
# and a confirmer ARE on record and only the distance is unknown; captioning it as an absent
# confirmation is the one thing that state exists to prevent.
# Pinned with their COUNTS attached, and the counts differ (2 undated, 1 unreadable). With
# both at 1 the two clauses were distinguishable only by caption, so swapping the two count
# expressions while leaving the captions in place passed all 73 checks — the exact
# cross-wiring the two states exist to prevent. Now each caption carries the other's number
# under that swap and both halves fail.
add("an unreadable confirmation date is never captioned as an absent one",
    rendered and "1 confirmed on a date the register cannot read" in s180
    and "2 carrying no confirmation record" in s180
    and s180.count("carrying no confirmation record") == 1
    and s180.count("confirmed on a date the register cannot read") == 1
    and "never confirmed" not in s180)

# Exclusive, and derived from the cadence rather than from the argparse default. The
# ranges are independent literals here, not recomputed from t: a range built from the same
# expression as the sentence's cannot disagree with it. CUMULATIVE is the shape of the
# defect that shipped on this very renderer — "within 360 days" captioning the count of
# determinations PAST the chosen cadence.
R180 = ["1 confirmed within the last 90 days", "between 91 and 180 days ago",
        "between 181 and 360 days ago", "not confirmed in over 360 days"]
R365 = ["2 confirmed within the last 182 days", "between 183 and 365 days ago",
        "between 366 and 730 days ago"]
CUM = ["between 0 and 180 days", "between 0 and 360 days", "within the last 180 days",
       "within the last 360 days", "in over 180 days"]
add("the sentence's ranges are exclusive and rescale with the cadence",
    rendered and all(x in s180 for x in R180) and all(x in s365 for x in R365)
    and not any(x in s180 or x in s365 for x in CUM)
    and R365[0] not in s180 and R180[0] not in s365
    # wellBeyond empties at T=365, and a zero clause is dropped rather than printed as 0.
    and "not confirmed in over" not in s365)

# A future-dated confirmation has a negative age, and age_band() reports that as `within` on
# purpose. So the rollup's `within` count is 2 while the sentence's freshest clause says 1:
# it is subtracted out and named rather than absorbed into the best news on the page. Both
# halves are the check — the rollup number and the prose number must DIFFER here, which is
# what makes it impossible to satisfy by reporting the band count verbatim.
add("a future-dated confirmation is named, not absorbed into the freshest clause",
    rendered and ("1 dated after the %s reference date" % today) in s180
    and "(R-008)" in s180
    and "1 confirmed within the last 90 days" in s180
    and cx("m.rr").confirmation["bands"]["within"] == 2
    and cx("m.rr").confirmation["futureDated"] == 1)
# ...and it states the FACT, never the cause. references/dashboards.md tells the reader to
# pass --today for a reproducible "as of" view, so an as-of date behind the register puts
# every SOUND record in this clause — nine of them on the shipped example at --today
# 2026-06-30. Calling those "a record defect" libels good records on a board page over a
# documented workflow, and no wording here may diagnose a cause this code cannot know.
# Asserted on the as-of render, where the population is entirely sound, and on the mixed
# one, where it is genuinely skewed: the same clause has to be true of both. DIAGNOSES is
# declared once at the top of this block and shared with the operational panel's version of
# this check — one rule, two surfaces.
add("the future-dated clause states the fact and never diagnoses a cause",
    rendered and s_asof is not None
    # The as-of fixture is the non-vacuity guard: without a sound population in this
    # clause, "no diagnosis present" is also true of a page that never renders the clause.
    and "9 dated after the 2026-06-30 reference date" in s_asof
    and not any(d in s_asof or d in s180 for d in DIAGNOSES)
    and "so no age can be measured for them" in s_asof)
# The closing clause is load-bearing prose: a distribution of ages on a board page invites
# the reading that old determinations have been marked down, and this is the sentence that
# denies it. Pinned on its own rather than left to sum_problem's right anchor, where anyone
# rewording it got an arithmetic failure about arithmetic that was fine.
# The reference date is a UTC calendar date, so every surface that prints it says so. On the
# evening of 2026-07-29 PDT the board page read "As of 2026-07-30" — tomorrow's date, to a
# reader who had asked for no such thing. The date was right; the label was missing. Asserted
# on all THREE renderers, and with the negative lookahead so that "UTC appears somewhere"
# cannot stand in for "every printed reference date carries it".
#
# The printable report is included because it is the one page that does NOT get its line from
# as_of_line(): cover() builds its own "As of {ctx.today} {ctx.ZONE}", since as_of_line()'s
# trailing snapshot clause is already printed on that cover as its own badge. So it is the
# surface where an unstamped date can reappear without touching the shared helper, and it is
# the surface that gets printed — it shipped unstamped for exactly that reason.
add("the reference date is stamped with its zone wherever it is printed",
    ("As of %s UTC" % today) in BOARD["m180"]
    and ("generated %s UTC from m.rr" % today) in BOARD["m180"]
    and "As of 2026-06-30 UTC" in BOARD["asof"]
    and ("As of %s UTC" % today) in HTML["a"]
    and ("As of %s UTC" % today) in REPORT["m180"]
    and ("generated %s UTC from m.rr" % today) in REPORT["m180"]
    and all(re.search(r"As of \d{4}-\d\d-\d\d(?! UTC)", h) is None
            for h in (BOARD["m180"], BOARD["asof"], HTML["a"], REPORT["m180"])))
add("the sentence closes by denying that age suppresses or rescores anything",
    rendered and s180.endswith("Age is reported so the board can weigh it, and nothing on "
                               "this page is rescored or re-ranked because of it.")
    and s_asof.endswith("because of it."))

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
