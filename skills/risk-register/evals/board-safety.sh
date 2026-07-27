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
python3 "$CSF/scripts/profile_analysis.py" init --name "Regression Co" \
  --out "$work/p.csfp" --owner CISO >/dev/null
python3 "$CSF/scripts/profile_analysis.py" quickstart-target "$work/p.csfp" >/dev/null
for s in PR.AA-01 GV.SC-07 DE.AE-03; do
  python3 "$CSF/scripts/profile_analysis.py" set "$work/p.csfp" "$s" \
    --current 0 --target 3 --rationale "fixture" >/dev/null
done
python3 "$CSF/scripts/profile_analysis.py" export-gaps "$work/p.csfp" --out "$work/gaps.csv" >/dev/null
rm -f "$work/r.rr"
python3 "$RR/scripts/score_register.py" init "$work/r.rr" --client "Regression Co" \
  --assessor CISO >/dev/null
python3 "$RR/scripts/score_register.py" import-gaps "$work/gaps.csv" \
  --into "$work/r.rr" --write >/dev/null 2>&1

# A score-only review: the path that used to authorise framework wording for a board.
python3 "$RR/scripts/score_register.py" set-score "$work/r.rr" R-001 --residual 5 5 \
  --why "scored, not reworded" >/dev/null
# An over-appetite risk the board formally accepted, still current.
python3 "$RR/scripts/score_register.py" set-score "$work/r.rr" R-002 --residual 5 5 --why x >/dev/null
python3 "$RR/scripts/score_register.py" accept "$work/r.rr" R-002 --approver "Audit Committee" \
  --justification "compensating controls; remediation funded" --revalidate 2099-01-31 \
  --why "board decision" >/dev/null

for r in render_board render_dashboard render_report; do
  python3 "$RR/renderers/$r.py" "$work/r.rr" "$work/$r.html" >/dev/null || exit 1
done
echo

# 1. No provisional raw title appears in any board-facing renderer.
raw=$(python3 - "$work" <<'PY'
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
chk 2 "score-only review keeps the title withheld" "$(python3 -c "
import json;d=json.load(open('$work/r.rr'))
r=[x for x in d['risks'] if x['id']=='R-001'][0]
print('PASS' if r['provisionalTitle'] and not r['provisionalScore'] else 'FAIL')")"

# 3. A current accepted risk is never grouped under 'board decision needed'.
chk 3 "accepted risk kept out of 'board decision needed'" "$(python3 -c "
s=open('$work/render_report.html',encoding='utf-8').read()
if 'board decision needed' not in s: print('FAIL no such section')
else:
    seg=s.split('board decision needed')[1].split('already accepted')[0]
    print('PASS' if 'R-002' not in seg else 'FAIL')")"

# 4. Closure without rationale exits non-zero and leaves the register byte-identical.
before=$(shasum -a 256 "$work/r.rr" | cut -d' ' -f1)
python3 "$RR/scripts/score_register.py" set-status "$work/r.rr" R-003 closed >/dev/null 2>&1
rc=$?
after=$(shasum -a 256 "$work/r.rr" | cut -d' ' -f1)
chk 4 "closure without --why refused, register untouched" \
    "$([ $rc -ne 0 ] && [ "$before" = "$after" ] && echo PASS || echo FAIL)"

# 5. Every artifact whose totals include candidates says so.
chk 5 "provisional disclosure present in board + report" \
    "$(grep -q 'risks are provisional' "$work/render_board.html" &&
       grep -q 'risks are provisional' "$work/render_report.html" && echo PASS || echo FAIL)"

# 6. --offline makes the promise in dashboards.md literally true.
python3 "$RR/renderers/render_board.py" "$work/r.rr" "$work/off.html" --offline >/dev/null
# Passes only when the file contains no absolute URL at all — not merely no font link.
grep -q 'https\?://' "$work/off.html"
chk 6 "--offline emits no external request" "$([ $? -ne 0 ] && echo PASS || echo FAIL)"

echo
if [ "$fails" -eq 0 ]; then
  echo "board-safety: all checks passed"
else
  echo "board-safety: $fails check(s) FAILED"
fi
exit $([ "$fails" -eq 0 ] && echo 0 || echo 1)
