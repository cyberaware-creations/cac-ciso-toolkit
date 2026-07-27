#!/bin/bash
# Do the rendered dashboards fit the device they are read on?
#
#   ./responsive.sh [workdir]
#
# A CISO opens the working view on a phone between meetings; a director opens the
# executive dashboard on theirs. Both were shipped with a page wider than the
# screen — 472px and 892px against a 375px phone — so sections started off-screen
# and the whole page scrolled sideways. Nothing in the other suites could see it:
# every check we had reads the HTML as text, and this defect only exists once a
# layout engine has resolved the CSS.
#
# So this one drives a real headless Chrome over the DevTools protocol and asks
# the page how wide it actually laid out.
#
# Two traps worth knowing, both of which produced a green run over a broken page:
#
#   1. Compare against the DEVICE width, not window.innerWidth. Chrome zooms the
#      visual viewport out to fit overflowing content, so innerWidth grows to meet
#      scrollWidth and the assertion becomes a tautology.
#   2. A grid item's default min-width:auto is min-content, so one long table cell
#      props its column — and the page — open. An overflow-x:auto wrapper does not
#      help until the grid item above it also gets min-width:0.
#
# The printable report is deliberately excluded: it is a fixed 900px print sheet
# with no viewport meta, so a phone scales the whole page to fit, which is the
# correct behaviour for something laid out for paper.
#
# Skips (exit 0) if node or Chrome is missing — this is the one check that cannot
# be stdlib-only, and it must not block a release on a machine without a browser.

set -u
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "$here/../../.." && pwd)"
work="${1:-$(mktemp -d)}"
PY="${PY:-python3}"
RR="$repo/skills/risk-register"
CSF="$repo/skills/nist-csf"
PORT="${CDP_PORT:-9333}"
export CDP_PORT="$PORT"

CHROME="${CHROME:-/Applications/Google Chrome.app/Contents/MacOS/Google Chrome}"
if ! command -v node >/dev/null 2>&1; then
  echo "responsive: SKIP — node not found (needed to speak CDP)."; exit 0
fi
if [ ! -x "$CHROME" ] && ! CHROME="$(command -v google-chrome || command -v chromium)"; then
  echo "responsive: SKIP — no Chrome found. Set CHROME=/path/to/chrome to run it."; exit 0
fi

mkdir -p "$work"
echo "Building a fixture: CSF Profile -> gap export -> register import"
"$PY" "$CSF/scripts/profile_analysis.py" init --name "Responsive Co" \
  --out "$work/p.csfp" --owner CISO >/dev/null
"$PY" "$CSF/scripts/profile_analysis.py" quickstart-target "$work/p.csfp" >/dev/null
for s in PR.AA-01 GV.SC-07 DE.AE-03 ID.AM-01 RS.MA-01 RC.RP-01; do
  "$PY" "$CSF/scripts/profile_analysis.py" set "$work/p.csfp" "$s" \
    --current 0 --target 3 --rationale fixture >/dev/null
done
"$PY" "$CSF/scripts/profile_analysis.py" export-gaps "$work/p.csfp" --out "$work/gaps.csv" >/dev/null
rm -f "$work/r.rr"
"$PY" "$RR/scripts/score_register.py" init "$work/r.rr" --client "Responsive Co" \
  --assessor CISO >/dev/null
"$PY" "$RR/scripts/score_register.py" import-gaps "$work/gaps.csv" \
  --into "$work/r.rr" --write >/dev/null 2>&1
"$PY" "$RR/scripts/score_register.py" set-score "$work/r.rr" R-001 --residual 5 5 --why x >/dev/null
"$PY" "$RR/scripts/score_register.py" set-score "$work/r.rr" R-002 --residual 5 4 --why x >/dev/null

for r in render_board render_dashboard; do
  "$PY" "$RR/renderers/$r.py" "$work/r.rr" "$work/$r.html" --offline >/dev/null || exit 1
done
"$PY" "$CSF/scripts/profile_analysis.py" analyze "$work/p.csfp" > "$work/an.json"
"$PY" "$CSF/renderers/render_executive.py" --in "$work/an.json" \
  --out "$work/csf_exec.html" --offline >/dev/null
"$PY" "$CSF/renderers/render_operational.py" --in "$work/an.json" \
  --out "$work/csf_ops.html" --offline >/dev/null

"$CHROME" --headless=new --disable-gpu --remote-debugging-port="$PORT" \
  --user-data-dir="$work/chrome-profile" --no-first-run \
  >"$work/chrome.log" 2>&1 &
chrome_pid=$!
trap 'kill $chrome_pid 2>/dev/null' EXIT

for _ in $(seq 1 40); do
  curl -sf "http://127.0.0.1:$PORT/json/version" >/dev/null && break
  sleep 0.3
done
if ! curl -sf "http://127.0.0.1:$PORT/json/version" >/dev/null; then
  echo "responsive: SKIP — Chrome did not expose a debugging port."; exit 0
fi

pages=("$work/render_board.html" "$work/render_dashboard.html"
       "$work/csf_exec.html" "$work/csf_ops.html")
fails=0
echo
for vw in 320 375 768 1265; do
  echo "device width ${vw}px"
  node "$here/measure-width.mjs" "$vw" "${pages[@]}" || fails=$((fails + 1))
done

echo
if [ "$fails" -eq 0 ]; then
  echo "responsive: every dashboard fits every tested device width"
else
  echo "responsive: $fails device width(s) FAILED"
fi
exit $([ "$fails" -eq 0 ] && echo 0 || echo 1)
