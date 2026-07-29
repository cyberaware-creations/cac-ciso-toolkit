#!/bin/bash
# Board-safety regression suite.
#
#   ./board-safety.sh [workdir]
#
# Every check here exists because a real artifact failed it. The board-facing renderers
# are the only place in this toolkit where a bug is *seen by the client's directors*
# rather than by the person who can fix it, so they get asserted against rendered HTML
# rather than by reading the code.
#
# Guarding one renderer is not enough and never was: the title guard was written into the
# executive dashboard first, and the printable report — the artifact most likely to be
# handed round a table on paper — kept exposing raw framework wording for a full release.
#
# Exit 0 = all pass. Exit 1 = at least one failure, listed.

set -u
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "$here/../../.." && pwd)"
work="${1:-$(mktemp -d)}"
# Overridable so the suite can be run on the supported Python floor, not just the
# author's interpreter:  PY=/usr/bin/python3 ./board-safety.sh
PY="${PY:-python3}"
RR="$repo/skills/risk-register"
CSF="$repo/skills/nist-csf"
mkdir -p "$work"

fails=0
chk() {  # chk <id> <description> <PASS|FAIL>
  printf '%-5s %-58s %s\n' "$1" "$2" "$3"
  [ "$3" = PASS ] || fails=$((fails + 1))
}
yn() { [ "$1" -eq 0 ] && echo PASS || echo FAIL; }

echo "Building a fixture: CSF Profile -> gap export -> register import"
"$PY" "$CSF/scripts/profile_analysis.py" init --name "Regression Co" \
  --out "$work/p.csfp" --owner CISO >/dev/null || {
    echo "board-safety: FIXTURE FAILED — profile init errored"; exit 1; }
"$PY" "$CSF/scripts/profile_analysis.py" quickstart-target "$work/p.csfp" >/dev/null || {
    echo "board-safety: FIXTURE FAILED — quickstart-target errored"; exit 1; }
"$PY" "$CSF/scripts/profile_analysis.py" intake add "$work/p.csfp" \
  --label "regression fixture seed" \
  --subjects PR.AA-01 GV.SC-07 DE.AE-03 ID.AM-01 RS.MA-01 RC.RP-01 >/dev/null || {
    echo "board-safety: FIXTURE FAILED — intake add errored"; exit 1; }
for s in PR.AA-01 GV.SC-07 DE.AE-03 ID.AM-01 RS.MA-01 RC.RP-01; do
  "$PY" "$CSF/scripts/profile_analysis.py" set "$work/p.csfp" "$s" \
    --current 0 --target 3 --source in-0001 --confirmed-by fixture \
    --rationale fixture >/dev/null || {
      echo "board-safety: FIXTURE FAILED — could not rate $s"; exit 1; }
done
"$PY" "$CSF/scripts/profile_analysis.py" export-gaps "$work/p.csfp" --out "$work/gaps.csv" >/dev/null || {
  echo "board-safety: FIXTURE FAILED — export-gaps errored"; exit 1; }
rm -f "$work/r.rr"
"$PY" "$RR/scripts/score_register.py" init "$work/r.rr" --client "Regression Co" \
  --assessor CISO >/dev/null || {
    echo "board-safety: FIXTURE FAILED — register init errored"; exit 1; }
# Snapshot BEFORE the import, deliberately. The change log only exists when there is a
# baseline to diff against, so an import-then-render fixture leaves it empty and check 1
# inspects a region that cannot fail. That blind spot shipped: the change log was the
# third route for raw framework wording onto a board page, and this suite passed over it
# for a full release. Do not "simplify" this snapshot away.
"$PY" "$RR/scripts/score_register.py" snapshot "$work/r.rr" \
  --label "Baseline" >/dev/null || {
    echo "board-safety: FIXTURE FAILED — snapshot errored"; exit 1; }
"$PY" "$RR/scripts/score_register.py" import-gaps "$work/gaps.csv" \
  --into "$work/r.rr" --write >/dev/null 2>&1 || {
    echo "board-safety: FIXTURE FAILED — import-gaps errored"; exit 1; }

# A score-only review: the path that used to authorise framework wording for a board.
"$PY" "$RR/scripts/score_register.py" set-score "$work/r.rr" R-001 --residual 5 5 \
  --why "scored, not reworded" >/dev/null || {
    echo "board-safety: FIXTURE FAILED — could not score R-001"; exit 1; }
# An over-appetite risk the board formally accepted, still current.
"$PY" "$RR/scripts/score_register.py" set-score "$work/r.rr" R-002 --residual 5 5 --why x >/dev/null || {
  echo "board-safety: FIXTURE FAILED — could not score R-002"; exit 1; }
"$PY" "$RR/scripts/score_register.py" accept "$work/r.rr" R-002 --approver "Audit Committee" \
  --justification "compensating controls; remediation funded" --revalidate 2099-01-31 \
  --why "board decision" >/dev/null || {
    echo "board-safety: FIXTURE FAILED — could not accept R-002"; exit 1; }

# An over-appetite risk the organisation has since treated out. Check 7 asserts the board
# figures stop counting it — the headline must improve when a risk is closed.
"$PY" "$RR/scripts/score_register.py" set-score "$work/r.rr" R-004 --residual 5 5 \
  --why "worst case before treatment" >/dev/null || {
    echo "board-safety: FIXTURE FAILED — could not score R-004"; exit 1; }
"$PY" "$RR/scripts/score_register.py" set-status "$work/r.rr" R-004 closed \
  --why "treated out; control verified" >/dev/null || {
    echo "board-safety: FIXTURE FAILED — could not close R-004"; exit 1; }

for r in render_board render_dashboard render_report; do
  "$PY" "$RR/renderers/$r.py" "$work/r.rr" "$work/$r.html" >/dev/null || {
    echo "board-safety: FIXTURE FAILED — $r.py errored"; exit 1; }
done
echo

# 1. No provisional raw title appears in any board-facing renderer.
raw=$("$PY" - "$work" <<'PY'
import json, re, sys, pathlib
work = pathlib.Path(sys.argv[1])
reg = json.loads((work / "r.rr").read_text())
titles = [r["title"] for r in reg["risks"] if r.get("provisionalTitle")]
leaks = []
for name in ("render_board", "render_report"):          # board-facing only
    html = (work / f"{name}.html").read_text()
    for t in titles:
        body = t.split(": ", 1)[-1].rstrip("…").strip()
        if len(body) > 30 and body[:60] in html:
            leaks.append(f"{name}:{t[:40]}")
print("|".join(leaks[:3]))
PY
)
chk 1 "no provisional raw title in any board renderer" "$([ -z "$raw" ] && echo PASS || echo "FAIL $raw")"

# 2. Score review alone does not authorize raw framework wording for a board.
chk 2 "score-only review keeps the title withheld" "$("$PY" -c "
import json;d=json.load(open('$work/r.rr'))
r=[x for x in d['risks'] if x['id']=='R-001'][0]
print('PASS' if r['provisionalTitle'] and not r['provisionalScore'] else 'FAIL')")"

# 3. A current accepted risk is never grouped under 'board decision needed'.
chk 3 "accepted risk kept out of 'board decision needed'" "$("$PY" -c "
s=open('$work/render_report.html',encoding='utf-8').read()
if 'board decision needed' not in s: print('FAIL no such section')
else:
    seg=s.split('board decision needed')[1].split('already accepted')[0]
    print('PASS' if 'R-002' not in seg else 'FAIL')")"

# 4. Closure without rationale exits non-zero and leaves the register byte-identical.
before=$(shasum -a 256 "$work/r.rr" | cut -d' ' -f1)
"$PY" "$RR/scripts/score_register.py" set-status "$work/r.rr" R-003 closed >/dev/null 2>&1
rc=$?
after=$(shasum -a 256 "$work/r.rr" | cut -d' ' -f1)
chk 4 "closure without --why refused, register untouched" \
    "$([ $rc -ne 0 ] && [ "$before" = "$after" ] && echo PASS || echo FAIL)"

# 5. Every artifact whose totals include candidates says so.
chk 5 "provisional disclosure present in board + report" \
    "$(grep -q 'risks are provisional' "$work/render_board.html" &&
       grep -q 'risks are provisional' "$work/render_report.html" && echo PASS || echo FAIL)"

# 6. --offline makes the promise in dashboards.md literally true.
"$PY" "$RR/renderers/render_board.py" "$work/r.rr" "$work/off.html" --offline >/dev/null || {
  echo "board-safety: FIXTURE FAILED — offline render_board errored"; exit 1; }
# Passes only when the file contains no absolute URL at all — not merely no font link.
grep -q 'https\?://' "$work/off.html"
chk 6 "--offline emits no external request" "$([ $? -ne 0 ] && echo PASS || echo FAIL)"

# 7. A closed risk is not counted as over appetite, and is not a top risk.
#
# The engine's summarize() counts every risk regardless of status — that is web-engine
# parity and it stays. The renderers must not repeat it: a headline that never improves
# as risks are treated out is a board figure that cannot be acted on, and the same page
# was reporting the count two different ways (KPI tile from summary, attention panel from
# the live set) inches apart.
chk 7 "closed risk excluded from board over-appetite figures" "$("$PY" - "$work" "$RR" <<'PY'
import json, re, sys, pathlib
work, rr = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
sys.path.insert(0, str(rr / "scripts"))
import score_register as sr

reg = json.loads((work / "r.rr").read_text())
size, appetite = reg["settings"]["matrixSize"], reg["settings"]["appetite"]
closed = [r for r in reg["risks"] if r.get("status") == "closed"]
live = [r for r in reg["risks"] if r.get("status") != "closed"]
expected = sum(1 for r in live if sr.over_appetite(
    sr.exposure(r["residual"]["likelihood"], r["residual"]["impact"]), size, appetite))
whole = sum(1 for r in reg["risks"] if sr.over_appetite(
    sr.exposure(r["residual"]["likelihood"], r["residual"]["impact"]), size, appetite))

problems = []
if not closed:
    problems.append("fixture has no closed risk")
elif expected == whole:
    # Without this the check passes for the wrong reason: if no closed risk is over
    # appetite, filtering and not filtering give the same number.
    problems.append("fixture's closed risk is not over appetite — check proves nothing")

board = (work / "render_board.html").read_text()
m = re.search(r'<div class="n">(\d+) of (\d+)(?: live)? risks</div>', board)
if not m:
    problems.append("board headline not found")
elif int(m.group(1)) != expected:
    problems.append(f"board headline says {m.group(1)} over appetite, live count is {expected}")
elif int(m.group(2)) != len(live):
    problems.append(f"board headline denominator {m.group(2)}, live count is {len(live)}")

for rid in (r["id"] for r in closed):
    for name in ("render_board", "render_dashboard"):
        for block in (work / f"{name}.html").read_text().split('class="toprisk"')[1:]:
            if rid in block[:500]:
                problems.append(f"{name}: closed {rid} listed as a top risk")

print("PASS" if not problems else "FAIL " + "; ".join(problems[:2]))
PY
)"

echo
if [ "$fails" -eq 0 ]; then
  echo "board-safety: all checks passed"
else
  echo "board-safety: $fails check(s) FAILED"
fi
exit $([ "$fails" -eq 0 ] && echo 0 || echo 1)
