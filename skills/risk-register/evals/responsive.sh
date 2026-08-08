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
MX="$repo/skills/metrics-register"
XR="$repo/skills/exceptions-register"
IM="$repo/skills/incident-materiality"
BP="$repo/skills/board-pack"
BC="$repo/skills/business-context"
VR="$repo/skills/vendor-register"
AR="$repo/skills/ai-register"
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

# metrics-register, both surfaces. The board view is rendered WITH its sidecar and the
# operational view without one, so the pass covers a page full of narrative and a page
# full of table — the two shapes that fail differently at 320px.
"$PY" "$MX/scripts/metrics_analysis.py" analyze "$MX/examples/example-metrics.mtr" \
  --today 2026-07-31 --out "$work/mx.json" >/dev/null || {
    echo "responsive: FIXTURE FAILED — metrics analyze errored"; exit 1; }
(cd "$MX/renderers" && "$PY" render_executive.py --in "$work/mx.json" \
  --translations "$MX/examples/example-translations.json" \
  --out "$work/mx_exec.html" --offline) >/dev/null || {
    echo "responsive: FIXTURE FAILED — metrics render_executive errored"; exit 1; }
(cd "$MX/renderers" && "$PY" render_operational.py --in "$work/mx.json" \
  --out "$work/mx_ops.html" --offline) >/dev/null || {
    echo "responsive: FIXTURE FAILED — metrics render_operational errored"; exit 1; }

# exceptions-register, both surfaces. The board view carries its sidecar; the inventory is
# the widest table in the suite (six columns of prose), which is the shape that overflows.
"$PY" "$XR/scripts/exceptions_register.py" analyze "$XR/examples/example.exc" \
  --today 2026-07-31 --out "$work/xr.json" >/dev/null || {
    echo "responsive: FIXTURE FAILED — exceptions analyze errored"; exit 1; }
(cd "$XR/renderers" && "$PY" render_board.py --in "$work/xr.json" \
  --translations "$XR/examples/example-translations.json" \
  --out "$work/xr_board.html" --offline) >/dev/null || {
    echo "responsive: FIXTURE FAILED — exceptions render_board errored"; exit 1; }
(cd "$XR/renderers" && "$PY" render_inventory.py --in "$work/xr.json" \
  --out "$work/xr_inv.html" --offline) >/dev/null || {
    echo "responsive: FIXTURE FAILED — exceptions render_inventory errored"; exit 1; }

# vendor-register, both surfaces. The operational table is seven columns wide and one of them
# is a trace rendered as `A -> B -> ...`, which is the shape that refuses to wrap; the board
# view carries its sidecar. Rendered against a REAL exported profile, so the criticality chips
# on the page are the ones the walk actually produced rather than placeholders.
"$PY" "$BC/scripts/business_context.py" export "$BC/examples/example-org.biz" \
  --out "$work/vr_ctx.json" >/dev/null || {
    echo "responsive: FIXTURE FAILED — business-context export for vendor errored"; exit 1; }
"$PY" "$VR/scripts/vendor_register.py" analyze "$VR/examples/example-vendors.vnd" \
  --context "$work/vr_ctx.json" --today 2026-07-31 --out "$work/vr.json" >/dev/null || {
    echo "responsive: FIXTURE FAILED — vendor analyze errored"; exit 1; }
(cd "$VR/renderers" && "$PY" render_board.py --in "$work/vr.json" \
  --translations "$VR/examples/example-translations.json" \
  --out "$work/vr_board.html" --offline) >/dev/null || {
    echo "responsive: FIXTURE FAILED — vendor render_board errored"; exit 1; }
(cd "$VR/renderers" && "$PY" render_operational.py --in "$work/vr.json" \
  --out "$work/vr_ops.html" --offline) >/dev/null || {
    echo "responsive: FIXTURE FAILED — vendor render_operational errored"; exit 1; }

# ai-register, both surfaces. The operational table is NINE columns — the widest in the suite —
# and two of them refuse to wrap: a trace rendered as `A -> B -> ...`, and a stack of exposure
# chips per row. The board view carries its sidecar. Rendered against the skill's own exported
# profile rather than a generic one, so the criticality chips are the ones the walk produced.
"$PY" "$AR/scripts/ai_register.py" analyze "$AR/examples/example-ai.air" \
  --context "$AR/examples/example-context.json" --today 2026-08-07 \
  --out "$work/ar.json" >/dev/null || {
    echo "responsive: FIXTURE FAILED — ai analyze errored"; exit 1; }
(cd "$AR/renderers" && "$PY" render_board.py --in "$work/ar.json" \
  --translations "$AR/examples/example-translations.json" \
  --out "$work/ar_board.html" --offline) >/dev/null || {
    echo "responsive: FIXTURE FAILED — ai render_board errored"; exit 1; }
(cd "$AR/renderers" && "$PY" render_operational.py --in "$work/ar.json" \
  --out "$work/ar_ops.html" --offline) >/dev/null || {
    echo "responsive: FIXTURE FAILED — ai render_operational errored"; exit 1; }

# incident-materiality, both surfaces. The worksheet is the densest page in the suite —
# four incidents, each with a six-row factor table carrying a paragraph of prose per row —
# which is the shape that overflows at 320px if a wrapper is missing a min-width:0.
"$PY" "$IM/scripts/incident_analysis.py" analyze "$IM/examples/example-incident.inc" \
  --today 2026-07-31 --now 2026-07-31T09:00:00+00:00 --out "$work/im.json" >/dev/null || {
    echo "responsive: FIXTURE FAILED — incident analyze errored"; exit 1; }
(cd "$IM/renderers" && "$PY" render_board.py --in "$work/im.json" \
  --translations "$IM/examples/example-translations.json" \
  --out "$work/im_board.html" --offline) >/dev/null || {
    echo "responsive: FIXTURE FAILED — incident render_board errored"; exit 1; }
(cd "$IM/renderers" && "$PY" render_worksheet.py --in "$work/im.json" \
  --out "$work/im_ws.html" --offline) >/dev/null || {
    echo "responsive: FIXTURE FAILED — incident render_worksheet errored"; exit 1; }

# board-pack: the assembled deliverable. It is the widest page in the suite by content —
# five sections of prose plus a ten-tile figure strip — and the only one carrying @page
# rules, so it is the one where a screen fix can silently break the print geometry.
"$PY" "$BP/scripts/assemble_pack.py" assemble "$BP/examples/pack.manifest.json" \
  --out "$work/pack.json" >/dev/null 2>&1 || {
    echo "responsive: FIXTURE FAILED — pack assemble errored"; exit 1; }
(cd "$BP/renderers" && "$PY" render_pack.py --in "$work/pack.json" \
  --html "$work/bp_pack.html" --no-pptx) >/dev/null || {
    echo "responsive: FIXTURE FAILED — render_pack errored"; exit 1; }

# The same pack under an applicability profile that DISAGREES with its own incident records.
# This page exists only when there is a conflict, which is exactly why it needs its own
# fixture: the plain pack above never renders it, so a board-facing page carrying a
# legal-perimeter warning would otherwise ship without a single resolved-layout or contrast
# measurement. It is also the most severity-coloured page in the suite — the one place a
# rule and a heading take a critical band on the note ground — so it is where a contrast
# regression would land first.
"$PY" "$BP/evals/_ctxmanifest.py" "$BP/examples/pack.manifest.json" \
  "$work/ctx.manifest.json" "$BC/examples/example-org.biz" || {
    echo "responsive: FIXTURE FAILED — could not build a context manifest"; exit 1; }
"$PY" "$BP/scripts/assemble_pack.py" assemble "$work/ctx.manifest.json" \
  --out "$work/ctxpack.json" >/dev/null 2>&1 || {
    echo "responsive: FIXTURE FAILED — context pack assemble errored"; exit 1; }
"$PY" -c 'import json,sys
d = json.load(open(sys.argv[1]))
sys.exit(0 if d.get("contextConflicts") else 1)' "$work/ctxpack.json" || {
    echo "responsive: FIXTURE FAILED — the context pack carries no conflict, so the page"
    echo "            below would be absent and its checks would pass over nothing"; exit 1; }
(cd "$BP/renderers" && "$PY" render_pack.py --in "$work/ctxpack.json" \
  --html "$work/bp_conflict.html" --no-pptx) >/dev/null || {
    echo "responsive: FIXTURE FAILED — conflict render_pack errored"; exit 1; }

# The crosswalk report. Three lenses of a wide table — the widest tabular page in the
# suite — and the one shipped renderer this browser suite had never opened. Its own
# end-to-end eval covers the data and the licensing gate; neither of those is a resolved
# layout, and a resolved layout is the only place a width or contrast defect exists.
"$PY" "$CSF/scripts/profile_analysis.py" analyze "$work/p.csfp" \
  --crosswalk iso-27001-2022 --crosswalk cis-8.1 --crosswalk 800-53-r5 \
  > "$work/xw.json" || {
    echo "responsive: FIXTURE FAILED — crosswalk analyze errored"; exit 1; }
(cd "$CSF/renderers" && "$PY" render_crosswalk.py --in "$work/xw.json" \
  --out "$work/csf_xw.html" --offline) >/dev/null || {
    echo "responsive: FIXTURE FAILED — render_crosswalk errored"; exit 1; }

# business-context framing. A short page, which is exactly why it is here: the pages that
# fail at 320px are the ones nobody expected to. It carries a blockquote of board-room
# prose and a revenue figure that must not wrap into nonsense.
(cd "$BC/renderers" && "$PY" render_context.py --in "$BC/examples/example-org.biz" \
  --out "$work/bc_framing.html" --offline) >/dev/null || {
    echo "responsive: FIXTURE FAILED — render_context errored"; exit 1; }

# The same pages again UNDER A CLIENT BRAND, using the exact JSON block the SKILL.md files
# tell a user to write.
#
# Every page above is the CAC palette, so for five releases the browser measured one
# palette and the `--brand` path was measured by nobody. The shell's contrast floor is not
# a substitute: it is a MODEL of what the page sets, and the page is the truth. When those
# two disagree the floor wins silently, which is exactly what happened — the floor scored
# `patina on ink` as a 3:1 graphical rule while the rendered kicker is 11px/700 text owing
# 4.5:1, so the documented brand was accepted at 4.13:1 and every branded page shipped
# under AA.
#
# Keeping the fixture identical to the documented block is the point. A brand invented here
# would test the code and not the advice, and the advice is what a client actually pastes.
cat > "$work/brand.json" <<'BRANDJSON'
{"ink": "#101820", "muted": "#5A4436", "patina": "#C0701F", "bg": "#FAF7F2",
 "measure": "#8A4B12", "measureTrack": "#EFE0D2", "patinaText": "#8A4B12",
 "wordmark": "Northwind Group", "mark": "Northwind", "whiteLabel": true}
BRANDJSON
(cd "$MX/renderers" && "$PY" render_executive.py --in "$work/mx.json" \
  --translations "$MX/examples/example-translations.json" \
  --out "$work/mx_exec_brand.html" --brand "$work/brand.json" --offline) >/dev/null || {
    echo "responsive: FIXTURE FAILED — branded metrics render_executive errored"; exit 1; }
(cd "$IM/renderers" && "$PY" render_worksheet.py --in "$work/im.json" \
  --out "$work/im_ws_brand.html" --brand "$work/brand.json" --offline) >/dev/null || {
    echo "responsive: FIXTURE FAILED — branded incident render_worksheet errored"; exit 1; }

# EMPTY STORES. Every fixture above is populated, and that is how a headline figure with
# no denominator survived: "3 metrics past a threshold" looks fine beside a populated
# register, and on an empty one it becomes "0 past a threshold" with no population at all
# — a healthy-looking metrics programme that has never been measured. The suite's own note
# further up says a state it cannot reach is a state it does not cover; these are the
# states the newer skills could not reach.
#
# They are also the layouts most likely to break quietly: a table with no rows, a chart
# with nothing to plot, a tile whose value is absent rather than zero.
"$PY" "$MX/scripts/metrics_analysis.py" init "$work/empty.mtr" --client "Empty Co" \
  >/dev/null 2>&1
"$PY" "$MX/scripts/metrics_analysis.py" analyze "$work/empty.mtr" --today 2026-07-31 \
  --out "$work/mx_empty.json" >/dev/null || {
    echo "responsive: FIXTURE FAILED — empty metrics analyze errored"; exit 1; }
(cd "$MX/renderers" && "$PY" render_executive.py --in "$work/mx_empty.json" \
  --out "$work/mx_exec_empty.html" --offline) >/dev/null || {
    echo "responsive: FIXTURE FAILED — empty metrics render_executive errored"; exit 1; }

"$PY" "$XR/scripts/exceptions_register.py" init "$work/empty.exc" --client "Empty Co" \
  >/dev/null 2>&1
"$PY" "$XR/scripts/exceptions_register.py" analyze "$work/empty.exc" --today 2026-07-31 \
  --out "$work/xr_empty.json" >/dev/null || {
    echo "responsive: FIXTURE FAILED — empty exceptions analyze errored"; exit 1; }
(cd "$XR/renderers" && "$PY" render_inventory.py --in "$work/xr_empty.json" \
  --out "$work/xr_inv_empty.html" --offline) >/dev/null || {
    echo "responsive: FIXTURE FAILED — empty exceptions render_inventory errored"; exit 1; }

"$PY" "$IM/scripts/incident_analysis.py" init "$work/empty.inc" --client "Empty Co" \
  >/dev/null 2>&1
"$PY" "$IM/scripts/incident_analysis.py" analyze "$work/empty.inc" --today 2026-07-31 \
  --out "$work/im_empty.json" >/dev/null || {
    echo "responsive: FIXTURE FAILED — empty incident analyze errored"; exit 1; }
(cd "$IM/renderers" && "$PY" render_worksheet.py --in "$work/im_empty.json" \
  --out "$work/im_ws_empty.html" --offline) >/dev/null || {
    echo "responsive: FIXTURE FAILED — empty incident render_worksheet errored"; exit 1; }

"$PY" "$BC/scripts/business_context.py" init "$work/empty.biz" --org "Empty Co" \
  >/dev/null 2>&1
(cd "$BC/renderers" && "$PY" render_context.py --in "$work/empty.biz" \
  --out "$work/bc_empty.html" --offline) >/dev/null || {
    echo "responsive: FIXTURE FAILED — empty render_context errored"; exit 1; }

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
# Prove the confirmation-age bands actually reach both pages, and reach them saying the
# same thing. Rendering alone proved nothing: the executive band strip could be deleted
# outright and every check in this suite still passed, and for a while that strip labelled
# `beyond` — ratings PAST the cadence — as "within 360 days", the opposite valence to the
# operational view's "beyond cadence", on the board-facing page of the two. --today is
# fixed above, so these counts and ranges are deterministic and can be pinned exactly.
grep -q "beyond cadence (181–360d)" "$work/csf_exec_v2ex.html" || {
    echo "responsive: FIXTURE FAILED — executive page shows no graded age bands"; exit 1; }
grep -q "well beyond cadence (over 360d)" "$work/csf_exec_v2ex.html" || {
    echo "responsive: FIXTURE FAILED — executive age bands are not exclusive ranges"; exit 1; }
grep -q "beyond cadence (198d)" "$work/csf_ops_v2ex.html" || {
    echo "responsive: FIXTURE FAILED — stalest rows carry no confirmation-age band"; exit 1; }

# An overlay-enabled Profile. The Cyber AI overlay adds an ordering disclosure to
# the operational gap table and the executive shortfall list, plus a provenance
# line in both footers — new text in a new place, which is exactly where this
# repo's render defects have historically hidden. Reorder mode is used because it
# is the default on enable and the only mode that replaces an existing caption.
cp "$CSF/examples/example-profile.csfp" "$work/overlay.csfp"
"$PY" "$CSF/scripts/profile_analysis.py" overlay enable "$work/overlay.csfp" \
  --focus secure thwart --mode reorder >/dev/null || {
    echo "responsive: FIXTURE FAILED — overlay enable errored"; exit 1; }
"$PY" "$CSF/scripts/profile_analysis.py" analyze "$work/overlay.csfp" \
  --today 2026-07-27 > "$work/overlay.json" || {
    echo "responsive: FIXTURE FAILED — overlay analyze errored"; exit 1; }
"$PY" "$CSF/renderers/render_executive.py" --in "$work/overlay.json" \
  --out "$work/csf_exec_overlay.html" --offline >/dev/null || {
    echo "responsive: FIXTURE FAILED — overlay render_executive errored"; exit 1; }
"$PY" "$CSF/renderers/render_operational.py" --in "$work/overlay.json" \
  --out "$work/csf_ops_overlay.html" --offline >/dev/null || {
    echo "responsive: FIXTURE FAILED — overlay render_operational errored"; exit 1; }
# Prove the fixture is actually exercising the disclosure, not just rendering.
grep -q "Cyber AI Profile overlay" "$work/csf_ops_overlay.html" || {
    echo "responsive: FIXTURE FAILED — operational page carries no overlay disclosure"; exit 1; }
grep -q "Cyber AI Profile overlay" "$work/csf_exec_overlay.html" || {
    echo "responsive: FIXTURE FAILED — executive page carries no overlay disclosure"; exit 1; }
# This one is built from the v1 example, whose ratings carry no confirmedAt at all — so it
# is the fixture that exercises the other branch: a stalest row must say the confirmation
# date is missing rather than be handed a band it has not earned.
grep -q "no confirmation date" "$work/csf_ops_overlay.html" || {
    echo "responsive: FIXTURE FAILED — an unconfirmed stalest row claims a band"; exit 1; }

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
       "$work/csf_exec_v2ex.html" "$work/csf_ops_v2ex.html"
       "$work/csf_exec_overlay.html" "$work/csf_ops_overlay.html"
       "$work/mx_exec.html" "$work/mx_ops.html"
       "$work/xr_board.html" "$work/xr_inv.html"
       "$work/im_board.html" "$work/im_ws.html"
       "$work/bp_pack.html" "$work/bp_conflict.html"
       "$work/csf_xw.html" "$work/bc_framing.html"
       "$work/vr_board.html" "$work/vr_ops.html"
       "$work/ar_board.html" "$work/ar_ops.html"
       "$work/mx_exec_brand.html" "$work/im_ws_brand.html"
       "$work/mx_exec_empty.html" "$work/xr_inv_empty.html"
       "$work/im_ws_empty.html" "$work/bc_empty.html")

# Every shipped renderer must have produced one of the pages above.
#
# `render_crosswalk.py` was missing from this suite for four releases and was found by an
# external tester rather than here; `render_context.py` would have been the next one, and
# it shipped hours ago. That is the failure the CI file names about globbed evals, in the
# other direction: a hand-maintained list nobody checks against reality stops matching it
# silently.
#
# So the list is declared and then checked against the filesystem. What this proves is
# that no shipped renderer is UNACCOUNTED FOR — a new one fails this suite until somebody
# points it at a fixture and names it here. What it cannot prove is that each entry's page
# really came from that renderer; that is carried by the FIXTURE FAILED guards above,
# every one of which aborts the run if its render command errors.
covered=(
  "risk-register/render_board"          "risk-register/render_dashboard"
  "risk-register/render_report"
  "nist-csf/render_executive"           "nist-csf/render_operational"
  "nist-csf/render_crosswalk"
  "metrics-register/render_executive"   "metrics-register/render_operational"
  "exceptions-register/render_board"    "exceptions-register/render_inventory"
  "incident-materiality/render_board"   "incident-materiality/render_worksheet"
  "board-pack/render_pack"
  "business-context/render_context"
  "vendor-register/render_board"        "vendor-register/render_operational"
  "ai-register/render_board"            "ai-register/render_operational"
)
shipped=""
for rp in "$repo"/skills/*/renderers/render_*.py; do
  shipped="$shipped $(basename "$(dirname "$(dirname "$rp")")")/$(basename "$rp" .py)"
done
missing=""
for s in $shipped; do
  hit=""
  for c in "${covered[@]}"; do [ "$c" = "$s" ] && hit=1; done
  [ -n "$hit" ] || missing="$missing $s"
done
stale=""
for c in "${covered[@]}"; do
  hit=""
  for s in $shipped; do [ "$c" = "$s" ] && hit=1; done
  [ -n "$hit" ] || stale="$stale $c"
done
if [ -n "$missing" ]; then
  echo "responsive: FIXTURE FAILED — shipped renderer(s) this suite never opens:$missing"
  echo "            Build a page from each, add it to \`pages\`, and name it in \`covered\`."
  echo "            A renderer this suite does not open is one whose layout nobody measured."
  exit 1
fi
if [ -n "$stale" ]; then
  echo "responsive: FIXTURE FAILED — \`covered\` names renderer(s) that no longer ship:$stale"
  exit 1
fi
echo "coverage: ${#pages[@]} pages, from all ${#covered[@]} shipped renderers"

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
