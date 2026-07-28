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
# The printable report used to be excluded here on the grounds that it is laid out
# for paper. That was the wrong call: it is *delivered* as HTML and gets opened on
# a phone, and "scales the whole page to fit" means an unreadable register table.
# It now adapts on screen while its print geometry is untouched — every screen rule
# sits behind `@media screen`, and @page still governs the PDF.
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
  --out "$work/p.csfp" --owner CISO >/dev/null || {
    echo "responsive: FIXTURE FAILED — profile init errored"; exit 1; }
"$PY" "$CSF/scripts/profile_analysis.py" quickstart-target "$work/p.csfp" >/dev/null || {
    echo "responsive: FIXTURE FAILED — quickstart-target errored"; exit 1; }
"$PY" "$CSF/scripts/profile_analysis.py" intake add "$work/p.csfp" \
  --label "regression fixture seed" \
  --subjects PR.AA-01 GV.SC-07 DE.AE-03 ID.AM-01 RS.MA-01 RC.RP-01 >/dev/null || {
    echo "responsive: FIXTURE FAILED — intake add errored"; exit 1; }
for s in PR.AA-01 GV.SC-07 DE.AE-03 ID.AM-01 RS.MA-01 RC.RP-01; do
  "$PY" "$CSF/scripts/profile_analysis.py" set "$work/p.csfp" "$s" \
    --current 0 --target 3 --source in-0001 --confirmed-by fixture \
    --rationale fixture >/dev/null || {
      echo "responsive: FIXTURE FAILED — could not rate $s"; exit 1; }
done
"$PY" "$CSF/scripts/profile_analysis.py" export-gaps "$work/p.csfp" --out "$work/gaps.csv" >/dev/null || {
  echo "responsive: FIXTURE FAILED — export-gaps errored"; exit 1; }

# Spread Current across the Functions so every coverage-ramp colour appears, then
# snapshot and improve so each tile also carries a delta chip. Without this the
# fixture only ever renders two of the five tile fills, and the pairing that was
# actually shipping at 1.57:1 never gets drawn — a suite that cannot reach the
# defect is not covering it.
"$PY" - "$work/p.csfp" <<'SEED' || { echo "responsive: FIXTURE FAILED — SEED heredoc errored"; exit 1; }
import collections, json, sys
path = sys.argv[1]
prof = json.load(open(path))
by = collections.defaultdict(list)
for a in prof["assessments"]:
    by[a["subcategoryId"].split(".")[0]].append(a)
for fid, frac in (("GV", .15), ("ID", .35), ("PR", .60), ("DE", .85), ("RS", 1.0)):
    rows = by[fid]
    for i, a in enumerate(rows):
        a["current"] = a["target"] if i < round(len(rows) * frac) else 0
for a in by["RC"]:                      # keep one Function untargeted
    a["target"] = a["current"] = None
json.dump(prof, open(path, "w"), indent=2)
SEED
"$PY" "$CSF/scripts/profile_analysis.py" snapshot "$work/p.csfp" --label Baseline >/dev/null || {
  echo "responsive: FIXTURE FAILED — snapshot errored"; exit 1; }
"$PY" - "$work/p.csfp" <<'BUMP' || { echo "responsive: FIXTURE FAILED — BUMP heredoc errored"; exit 1; }
import collections, json, sys
path = sys.argv[1]
prof = json.load(open(path))
by = collections.defaultdict(list)
for a in prof["assessments"]:
    by[a["subcategoryId"].split(".")[0]].append(a)
for fid in ("GV", "ID", "PR", "DE"):    # movement -> a delta chip on each tile
    for a in by[fid][:2]:
        if a.get("current") == 0:
            a["current"] = a["target"]
json.dump(prof, open(path, "w"), indent=2)
BUMP
rm -f "$work/r.rr"
"$PY" "$RR/scripts/score_register.py" init "$work/r.rr" --client "Responsive Co" \
  --assessor CISO >/dev/null || {
    echo "responsive: FIXTURE FAILED — register init errored"; exit 1; }
"$PY" "$RR/scripts/score_register.py" import-gaps "$work/gaps.csv" \
  --into "$work/r.rr" --write >/dev/null 2>&1 || {
    echo "responsive: FIXTURE FAILED — import-gaps errored"; exit 1; }
"$PY" "$RR/scripts/score_register.py" set-score "$work/r.rr" R-001 --residual 5 5 --why x >/dev/null || {
  echo "responsive: FIXTURE FAILED — could not score R-001"; exit 1; }
"$PY" "$RR/scripts/score_register.py" set-score "$work/r.rr" R-002 --residual 5 4 --why x >/dev/null || {
  echo "responsive: FIXTURE FAILED — could not score R-002"; exit 1; }

for r in render_board render_dashboard render_report; do
  "$PY" "$RR/renderers/$r.py" "$work/r.rr" "$work/$r.html" --offline >/dev/null || {
    echo "responsive: FIXTURE FAILED — $r.py errored"; exit 1; }
done
"$PY" "$CSF/scripts/profile_analysis.py" analyze "$work/p.csfp" > "$work/an.json" || {
  echo "responsive: FIXTURE FAILED — analyze errored"; exit 1; }
"$PY" "$CSF/renderers/render_executive.py" --in "$work/an.json" \
  --out "$work/csf_exec.html" --offline >/dev/null || {
    echo "responsive: FIXTURE FAILED — render_executive errored"; exit 1; }
"$PY" "$CSF/renderers/render_operational.py" --in "$work/an.json" \
  --out "$work/csf_ops.html" --offline >/dev/null || {
    echo "responsive: FIXTURE FAILED — render_operational errored"; exit 1; }

# A second CSF pair, deliberately below the scope threshold. The first fixture seeds
# ratings across every Function, so it renders the headline path only — the scope
# guard, the four-way evidence bar and the by-source cards would never be drawn.
# A suite that cannot reach a state is not covering it, which is how three render
# defects already reached a user.
"$PY" "$CSF/scripts/profile_analysis.py" init --name "Partial Co" \
  --out "$work/partial.csfp" --owner CISO >/dev/null || {
    echo "responsive: FIXTURE FAILED — partial profile init errored"; exit 1; }
"$PY" "$CSF/scripts/profile_analysis.py" quickstart-target "$work/partial.csfp" >/dev/null || {
    echo "responsive: FIXTURE FAILED — partial quickstart-target errored"; exit 1; }
"$PY" "$CSF/scripts/profile_analysis.py" intake add "$work/partial.csfp" \
  --label "architecture review with the infrastructure team, covering discovery and data flows" \
  --subjects ID.AM-01 ID.AM-02 ID.AM-03 ID.AM-05 PR.AA-01 --source-date 2025-03-14 \
  --recorded-by CISO >/dev/null || {
    echo "responsive: FIXTURE FAILED — partial intake add in-0001 errored"; exit 1; }
"$PY" "$CSF/scripts/profile_analysis.py" intake add "$work/partial.csfp" \
  --label "backup restore test debrief" --subjects PR.DS-11 RC.RP-01 \
  --source-date 2026-06-30 --recorded-by CISO >/dev/null || {
    echo "responsive: FIXTURE FAILED — partial intake add in-0002 errored"; exit 1; }
"$PY" "$CSF/scripts/profile_analysis.py" set "$work/partial.csfp" ID.AM-01 --current 2 \
  --source in-0001 --confirmed-by CISO --rationale fixture --ts 2025-03-20T00:00:00Z >/dev/null || {
    echo "responsive: FIXTURE FAILED — could not rate partial ID.AM-01"; exit 1; }
"$PY" "$CSF/scripts/profile_analysis.py" set "$work/partial.csfp" RC.RP-01 --current 1 \
  --source in-0002 --confirmed-by CISO --rationale fixture --ts 2026-01-10T00:00:00Z >/dev/null || {
    echo "responsive: FIXTURE FAILED — could not rate partial RC.RP-01"; exit 1; }
"$PY" "$CSF/scripts/profile_analysis.py" set "$work/partial.csfp" PR.AA-06 \
  --applicability not-applicable --rationale fixture >/dev/null || {
    echo "responsive: FIXTURE FAILED — could not mark PR.AA-06 not-applicable"; exit 1; }
"$PY" "$CSF/scripts/profile_analysis.py" analyze "$work/partial.csfp" \
  --today 2026-07-27 > "$work/partial.json" || {
    echo "responsive: FIXTURE FAILED — partial analyze errored"; exit 1; }
"$PY" "$CSF/renderers/render_executive.py" --in "$work/partial.json" \
  --out "$work/csf_exec_partial.html" --offline >/dev/null || {
    echo "responsive: FIXTURE FAILED — partial render_executive errored"; exit 1; }
"$PY" "$CSF/renderers/render_operational.py" --in "$work/partial.json" \
  --out "$work/csf_ops_partial.html" --offline >/dev/null || {
    echo "responsive: FIXTURE FAILED — partial render_operational errored"; exit 1; }

# The shipped v2 example fixture, rendered too. It is suppressed like the partial
# fixture above and shares the same four-way states, but its four intake sources
# (one all-confirmed, one all-pending, two mixed) exercise source-card state
# variety and a wider by-source grid that a two-source fixture cannot reach, and
# its >12-month age spread across four dated confirmations is a genuinely
# different data shape from the partial fixture's two.
"$PY" "$CSF/scripts/profile_analysis.py" analyze "$CSF/examples/example-profile-v2.csfp" \
  --today 2026-07-27 > "$work/v2ex.json" || {
    echo "responsive: FIXTURE FAILED — v2 example analyze errored"; exit 1; }
"$PY" "$CSF/renderers/render_executive.py" --in "$work/v2ex.json" \
  --out "$work/csf_exec_v2ex.html" --offline >/dev/null || {
    echo "responsive: FIXTURE FAILED — v2 example render_executive errored"; exit 1; }
"$PY" "$CSF/renderers/render_operational.py" --in "$work/v2ex.json" \
  --out "$work/csf_ops_v2ex.html" --offline >/dev/null || {
    echo "responsive: FIXTURE FAILED — v2 example render_operational errored"; exit 1; }

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

pages=("$work/render_board.html" "$work/render_dashboard.html" "$work/render_report.html"
       "$work/csf_exec.html" "$work/csf_ops.html"
       "$work/csf_exec_partial.html" "$work/csf_ops_partial.html"
       "$work/csf_exec_v2ex.html" "$work/csf_ops_v2ex.html")
fails=0
echo
for vw in 320 375 768 1265; do
  echo "device width ${vw}px"
  node "$here/measure-width.mjs" "$vw" "${pages[@]}" || fails=$((fails + 1))
done

# Contrast rides along on the same browser: it needs the identical fixture and the
# identical resolved layout, and starting Chrome twice to ask two questions about
# one page is waste. A colour pairing is only knowable once the page is laid out —
# which surface an element lands on, what an 8-digit alpha composites to over it,
# and what `opacity` does to the result are all layout facts, not CSS text.
echo
echo "contrast (WCAG AA)"
node "$here/contrast-check.mjs" "${pages[@]}" || fails=$((fails + 1))

echo
if [ "$fails" -eq 0 ]; then
  echo "responsive: every artifact fits every tested width and meets AA contrast"
else
  echo "responsive: $fails check(s) FAILED"
fi
exit $([ "$fails" -eq 0 ] && echo 0 || echo 1)
