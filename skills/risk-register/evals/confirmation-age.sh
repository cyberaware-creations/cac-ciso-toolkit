#!/bin/bash
# Confirmation-age derivation, asserted against a register built by the real CLI.
#
#   ./confirmation-age.sh [workdir]
#
# The four derived fields (lastConfirmedAt, lastConfirmedBy, confirmationAgeDays,
# confirmationBand) come from history[] and nothing else — there is no stored age field
# and there must never be one. So they are asserted through the same Context the
# renderers use, over a register whose history was written by actual commands rather
# than hand-assembled JSON. A hand-built fixture would not catch the failure that
# matters most: a command that writes the wrong event type.
#
# Assertions here pin exact values and exact populations. An earlier suite in this plan
# shipped `all(... for r in rows if r[field])` over a fixture where the filter matched
# nothing — vacuously true, and a mutant banding on the wrong field survived the whole
# set. Where a check filters, it also pins how many rows survived the filter.
#
# Exit 0 = all pass. Exit 1 = at least one failure, listed.

set -u
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "$here/../../.." && pwd)"
work="${1:-$(mktemp -d)}"
PY="${PY:-python3}"
RR="$repo/skills/risk-register"
mkdir -p "$work"

fails=0
chk() {
  printf '%-5s %-58s %s\n' "$1" "$2" "$3"
  [ "$3" = PASS ] || fails=$((fails + 1))
}

SR="$RR/scripts/score_register.py"
rm -f "$work/a.rr"
"$PY" "$SR" init "$work/a.rr" --client "Age Co" \
  --assessor "D. Alleyne" >/dev/null || { echo "FIXTURE FAILED — init"; exit 1; }
"$PY" "$SR" add "$work/a.rr" --title "Supplier concentration" \
  --il 4 --ii 4 --rl 3 --ri 4 --why "fixture" >/dev/null || {
    echo "FIXTURE FAILED — add R-001"; exit 1; }
"$PY" "$SR" add "$work/a.rr" --title "Legacy VPN appliance" \
  --il 5 --ii 4 --rl 4 --ri 4 --why "fixture" >/dev/null || {
    echo "FIXTURE FAILED — add R-002"; exit 1; }
"$PY" "$SR" add "$work/a.rr" --title "Retired file share still reachable" \
  --il 3 --ii 3 --rl 2 --ri 2 --why "fixture" >/dev/null || {
    echo "FIXTURE FAILED — add R-003"; exit 1; }
# R-002 gets a non-affirming event LAST. Its age must still date from `risk-added`.
"$PY" "$SR" set-text "$work/a.rr" R-002 \
  --title "Remote access via an unsupported VPN appliance" --why "reworded" >/dev/null || {
    echo "FIXTURE FAILED — set-text R-002"; exit 1; }
"$PY" "$SR" set-status "$work/a.rr" R-002 monitoring \
  --why "watching" >/dev/null || { echo "FIXTURE FAILED — set-status R-002"; exit 1; }
# R-003 is closed. A closed risk keeps its confirmation date forever, and it must not
# sit in the live freshness distribution — `confirm` deliberately allows confirming a
# closed risk, so excluding it here is the corollary obligation.
"$PY" "$SR" set-status "$work/a.rr" R-003 closed \
  --why "decommissioned and verified" >/dev/null || {
    echo "FIXTURE FAILED — set-status R-003 closed"; exit 1; }
"$PY" "$SR" snapshot "$work/a.rr" --label "Baseline" >/dev/null || {
    echo "FIXTURE FAILED — snapshot"; exit 1; }

"$PY" - "$work" "$RR" <<'PY' > "$work/out.txt"
import json, sys, pathlib, argparse, subprocess
from datetime import date, timedelta
work, rr = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
sys.path.insert(0, str(rr / "renderers"))
sys.path.insert(0, str(rr / "scripts"))
import _common as C
import score_register as sr

SR = str(rr / "scripts" / "score_register.py")


def run(*argv):
    subprocess.run([sys.executable, SR] + list(argv), check=True, capture_output=True)


reg = json.loads((work / "a.rr").read_text())
# Every event this fixture wrote is dated today, so ages are 0 and every risk is
# `within`. The band boundaries themselves are asserted in score_register's self-test;
# what is asserted here is that the derivation reads the right event.
today = max(e["ts"] for e in reg["history"])[:10]


def ctx(path="a.rr", **over):
    args = argparse.Namespace(register=str(work / path), out=str(work / "x.html"),
                              today=today, translations=None, offline=True,
                              age_threshold=180)
    for k, v in over.items():
        setattr(args, k, v)
    return C.Context(args)


out = []


def add(name, good):
    out.append((name, bool(good)))


def add_try(name, thunk):
    """Like add(), but a raising check reports FAIL instead of aborting the suite.

    Used for the tolerance checks specifically: their whole claim is "this does not
    raise", so a traceback is the failure and must be reported as one rather than
    taking the other thirty-odd checks down with it.
    """
    try:
        out.append((name, bool(thunk())))
    except Exception as exc:                                    # noqa: BLE001
        out.append(("%s (raised %r)" % (name, exc), False))


c = ctx()
by = c.by_id
add("R-001 dates from risk-added", by["R-001"]["lastConfirmedAt"] == today)
add("R-001 names the actor", by["R-001"]["lastConfirmedBy"] == "D. Alleyne")
add("R-001 age is 0 days", by["R-001"]["confirmationAgeDays"] == 0)
add("R-001 bands as within", by["R-001"]["confirmationBand"] == "within")
# The load-bearing one: set-text and set-status both landed after risk-added on R-002,
# and neither of them may reset its age. Pinned as an exact tail rather than a
# membership test, so a fixture that stopped writing them cannot pass this vacuously.
r2_hist = [e["type"] for e in by["R-002"]["history"]]
add("R-002 history really does end non-affirming",
    r2_hist == ["risk-added", "risk-updated", "status-changed"])
add("R-002 still dates from risk-added", by["R-002"]["lastConfirmedAt"] == today)

# ...but on its own that check cannot fail. Every event the CLI just wrote shares one
# date, so "dates from risk-added" is true whichever event the derivation picks — a
# mutant treating status-changed as affirming passed it. So it is re-asserted over a
# re-dated copy: the same event types written by the same real commands, with the
# non-affirming ones moved 200 days after the risk-added they must not displace.
rawe = json.loads((work / "a.rr").read_text())
base = date.fromisoformat(today)
for e in rawe["history"]:
    off = 0 if e["type"] in sr.AGE_AFFIRMING else 200
    e["ts"] = (base + timedelta(days=off)).isoformat() + "T00:00:00Z"
(work / "e.rr").write_text(json.dumps(rawe))
later = (base + timedelta(days=200)).isoformat()
ce = ctx("e.rr", today=later)
add("a later non-affirming event does not reset R-002's age",
    ce.by_id["R-002"]["lastConfirmedAt"] == today
    and ce.by_id["R-002"]["confirmationAgeDays"] == 200
    and ce.by_id["R-002"]["confirmationBand"] == "beyond")
add("nor does it move R-002 out of its band in the rollup",
    ce.confirmation["bands"] == {"within": 0, "approaching": 0,
                                 "beyond": 2, "wellBeyond": 0}
    and ce.confirmation["undated"] == 0 and ce.confirmation["live"] == 2)

# --- derived, never stored -------------------------------------------------------
raw_text = (work / "a.rr").read_text()
add("no age field is persisted to the register",
    not any(k in raw_text for k in ("lastConfirmedAt", "confirmationAgeDays",
                                    "confirmationBand", "lastConfirmedBy")))

# A confirm resets the age; nothing else about the risk moves.
run("confirm", str(work / "a.rr"), "R-001", "--why", "reviewed, unchanged")
c2 = ctx()
ev = c2.by_id["R-001"]["history"][-1]
add("confirm becomes the affirming event", ev["type"] == "risk-confirmed")
add("confirm keeps the age at 0", c2.by_id["R-001"]["confirmationAgeDays"] == 0)

# --- the rollup counts live risks only, and partitions them exactly --------------
add("rollup bands are exactly the live population",
    c2.confirmation["bands"] == {"within": 2, "approaching": 0,
                                 "beyond": 0, "wellBeyond": 0})
add("rollup undated is 0 here", c2.confirmation["undated"] == 0)
# 3 risks in the register, 1 closed. If the closed one leaks in, `live` reads 3.
add("rollup excludes the closed risk",
    c2.confirmation["live"] == 2 and len(c2.risks) == 3
    and c2.by_id["R-003"]["status"] == "closed")
add("bands plus undated partition the live population exactly",
    sum(c2.confirmation["bands"].values()) + c2.confirmation["undated"]
    == c2.confirmation["live"] == 2)
add("rollup reports its own threshold", c2.confirmation["thresholdDays"] == 180)

# --- honest absence -------------------------------------------------------------
# A register with a v1-style history — no affirming event at all — must yield None,
# not a guess and not a crash.
raw = json.loads((work / "a.rr").read_text())
raw["history"] = [e for e in raw["history"] if e["type"] not in sr.AGE_AFFIRMING]
(work / "b.rr").write_text(json.dumps(raw))
cb = ctx("b.rr")
add("no affirming event yields None, not a guess",
    cb.by_id["R-001"]["lastConfirmedAt"] is None
    and cb.by_id["R-001"]["lastConfirmedBy"] is None
    and cb.by_id["R-001"]["confirmationAgeDays"] is None
    and cb.by_id["R-001"]["confirmationBand"] is None)
add("undated risks are counted, not hidden or banded",
    cb.confirmation["undated"] == 2 and cb.confirmation["live"] == 2
    and cb.confirmation["bands"] == {"within": 0, "approaching": 0,
                                     "beyond": 0, "wellBeyond": 0})

# --- --age-threshold reaches the derivation, and changes an answer ---------------
# Not "is it stored on the Context" — the same register, aged 400 days, must band
# differently under two cadences. Dropping the kwarg leaves the first of these wrong.
aged = (date.fromisoformat(today) + timedelta(days=400)).isoformat()
add("400 days is wellBeyond at T=180",
    ctx(today=aged, age_threshold=180).by_id["R-001"]["confirmationBand"] == "wellBeyond")
add("the same 400 days is within at T=1000",
    ctx(today=aged, age_threshold=1000).by_id["R-001"]["confirmationBand"] == "within")
roll_aged = ctx(today=aged, age_threshold=180).confirmation
add("the rollup follows the threshold too",
    roll_aged["bands"] == {"within": 0, "approaching": 0, "beyond": 0, "wellBeyond": 2}
    and roll_aged["undated"] == 0 and roll_aged["live"] == 2
    and roll_aged["thresholdDays"] == 180)
add("the rollup names the wellBeyond risks, live only",
    [r["id"] for r in roll_aged["wellBeyond"]] == ["R-001", "R-002"])
add("--age-threshold is rejected at zero or below",
    all(_rc != 0 for _rc in [subprocess.run(
        [sys.executable, str(rr / "renderers" / "render_board.py"), str(work / "a.rr"),
         str(work / "rej.html"), "--offline", "--age-threshold", bad],
        capture_output=True).returncode for bad in ("0", "-5")]))

# --- reviewOverdueDays ----------------------------------------------------------
# A missed deadline is a fact with a magnitude, still boolean-gated. Both halves are
# asserted against a register with a real overdue date, so neither is vacuous.
rawd = json.loads((work / "a.rr").read_text())
past = (date.fromisoformat(today) - timedelta(days=30)).isoformat()
rawd["risks"][0]["reviewDate"] = past          # R-001, live  -> 30
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
    len(not_overdue) == 2 and all(r["reviewOverdueDays"] is None for r in not_overdue))

# --- a malformed date must not turn a board night into a traceback --------------
# `_days_since` directly, because the Context path alone would not reach it: _overdue()
# compares strings, so a date that reads as "not overdue" never gets to the arithmetic.
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

# --- tied timestamps ------------------------------------------------------------
# _now() has second resolution and one `set-score` can write two score-changed events,
# so two affirming events sharing a ts is reachable. History is append-only, so the
# later-appended one is the later assertion and wins.
rawt = json.loads((work / "a.rr").read_text())
ts = rawt["history"][0]["ts"]
rawt["history"] = [
    {"ts": ts, "actor": "First Writer", "type": "score-changed", "riskId": "R-001"},
    {"ts": ts, "actor": "Second Writer", "type": "risk-confirmed", "riskId": "R-001"},
]
(work / "t.rr").write_text(json.dumps(rawt))
add("on a tied ts the later-appended affirming event wins",
    ctx("t.rr").by_id["R-001"]["lastConfirmedBy"] == "Second Writer")

# --- a 'nothing changed' rationale must never caption a change ------------------
SCORE_WHY = "third-party review found no compensating control"
CONFIRM_WHY = "reviewed at the forum; unchanged"
run("set-score", str(work / "a.rr"), "R-001", "--residual", "5", "5", "--why", SCORE_WHY)
run("confirm", str(work / "a.rr"), "R-001", "--why", CONFIRM_WHY)
c3 = ctx()
chg = {ch["id"]: ch for ch in c3.diff["changes"]}
add("the confirmation really is the newest rationale for R-001",
    [e.get("rationale") for e in c3.by_id["R-001"]["history"]][-1] == CONFIRM_WHY)
add("the change log explains the move, not the re-affirmation",
    chg["R-001"]["kind"] == "worsened" and chg["R-001"]["rationale"] == SCORE_WHY)
add("risk-confirmed cannot caption a change",
    "risk-confirmed" not in C.Context.CHANGE_EXPLAINING)
# Two hand-maintained lists cannot disagree unless one side is independent, so this
# checks CHANGE_EXPLAINING against the taxonomy score_register partitions and asserts.
add("every change-explaining type is a known event type",
    C.Context.CHANGE_EXPLAINING - sr.KNOWN_EVENT_TYPES == set())
add("a confirmation rationale is still kept in history",
    CONFIRM_WHY in [e.get("rationale") for e in c3.by_id["R-001"]["history"]])

for name, good in out:
    print(("PASS" if good else "FAIL") + "\t" + name)
PY

n=1
while IFS=$'\t' read -r verdict name; do
  chk "$n" "$name" "$verdict"
  n=$((n + 1))
done < "$work/out.txt"

# The board page is the artifact directors read, so the rationale rule is asserted on
# rendered output as well as on the derivation.
"$PY" "$RR/renderers/render_board.py" "$work/a.rr" "$work/board.html" --offline >/dev/null || {
  echo "FIXTURE FAILED — render_board errored"; exit 1; }
if grep -q "third-party review found no compensating control" "$work/board.html" \
   && ! grep -q "reviewed at the forum" "$work/board.html"; then
  chk "$n" "rendered board change log carries the score rationale" PASS
else
  chk "$n" "rendered board change log carries the score rationale" FAIL
fi
n=$((n + 1))

echo
if [ "$fails" -eq 0 ]; then
  echo "confirmation-age: all checks passed"
else
  echo "confirmation-age: $fails check(s) FAILED"
fi
exit $([ "$fails" -eq 0 ] && echo 0 || echo 1)
