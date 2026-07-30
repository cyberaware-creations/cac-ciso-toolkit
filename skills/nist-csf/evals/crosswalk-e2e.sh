#!/usr/bin/env bash
# End-to-end crosswalk suite: golden .csfa -> convert -> analyze -> render, asserting
# the headline numbers and the licensing gate at every step.
#
# Deterministic and offline. Runs on the declared Python floor, because the floor is
# where a construct like a nested same-quote f-string fails — and one shipped in this
# feature's first renderer draft.
#
# The suite refuses to report success over a partial run: EXPECTED_CHECKS below is
# asserted at the end, so a case that silently stops executing fails loudly instead
# of printing a green count over half a suite. That guard is the lesson of the
# confirmation-age suite next door.
set -u

PY="${PY:-$(command -v python3)}"
here="$(cd "$(dirname "$0")" && pwd)"
skill="$(cd "$here/.." && pwd)"
repo="$(cd "$skill/../.." && pwd)"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

EXPECTED_CHECKS=39
checks=0
fails=0

ok() {  # ok <label>
  checks=$((checks + 1))
  printf '  ok    %s\n' "$1"
}
bad() {  # bad <label> <detail>
  checks=$((checks + 1))
  fails=$((fails + 1))
  printf '  FAIL  %s\n         %s\n' "$1" "$2"
}
is() {  # is <label> <got> <want>
  if [ "$2" = "$3" ]; then ok "$1"; else bad "$1" "expected '$3', got '$2'"; fi
}
has() {  # has <label> <file> <needle>
  if grep -q -- "$3" "$2"; then ok "$1"; else bad "$1" "missing: $3"; fi
}
hasnt() {  # hasnt <label> <file> <needle>
  if grep -q -- "$3" "$2"; then bad "$1" "present but forbidden: $3"; else ok "$1"; fi
}

echo "crosswalk-e2e: $($PY -V 2>&1)"

golden="$skill/evals/fixtures/crosswalk-golden.csfa"
store="$work/golden.csfp"
analysis="$work/analysis.json"
report="$work/crosswalk.html"

# --- 1. the licensing gate, on the data as shipped --------------------------------
if $PY "$repo/tools/crosswalks/validate_crosswalks.py" >"$work/val.txt" 2>&1; then
  ok "build-time validator passes on the bundled data"
else
  bad "build-time validator passes on the bundled data" "$(tail -3 "$work/val.txt")"
fi
has "validator reports all three catalogues" "$work/val.txt" "3 catalogs"

if $PY "$skill/scripts/profile_analysis.py" validate >"$work/v2.txt" 2>&1; then
  ok "shipped integrity check passes"
else
  bad "shipped integrity check passes" "$(tail -3 "$work/v2.txt")"
fi

# --- 2. the golden fixture converts through the real parse gate -------------------
if $PY "$skill/scripts/csfa_compat.py" convert "$golden" --out "$store" >"$work/conv.txt" 2>&1; then
  ok "golden .csfa converts via the CLI parse gate"
else
  bad "golden .csfa converts via the CLI parse gate" "$(tail -3 "$work/conv.txt")"
fi
is "converted Profile keeps the tool's 0-4 scale" \
   "$($PY -c "import json,sys;print(json.load(open(sys.argv[1]))['profile']['settings']['scale']['max'])" "$store")" "4"

# --- 3. a lens is opt-in ----------------------------------------------------------
$PY "$skill/scripts/profile_analysis.py" analyze "$store" --today 2026-07-29 >"$work/plain.json" 2>/dev/null
is "analyze without --crosswalk emits no crosswalks key" \
   "$($PY -c "import json,sys;print('crosswalks' in json.load(open(sys.argv[1])))" "$work/plain.json")" "False"

if $PY "$skill/scripts/profile_analysis.py" analyze "$store" --crosswalk not-a-framework \
     >/dev/null 2>"$work/badlens.txt"; then
  bad "an unknown lens is refused" "analyze exited 0"
else
  ok "an unknown lens is refused"
fi
has "the refusal names the available lenses" "$work/badlens.txt" "iso-27001-2022"

# --- 4. analyze with all three lenses ---------------------------------------------
$PY "$skill/scripts/profile_analysis.py" analyze "$store" --today 2026-07-29 \
  --crosswalk iso-27001-2022 --crosswalk cis-8.1 --crosswalk 800-53-r5 \
  --out "$analysis" >/dev/null 2>&1
if [ -s "$analysis" ]; then ok "analyze wrote a crosswalk analysis"; else
  bad "analyze wrote a crosswalk analysis" "empty or missing $analysis"; fi

# Headline numbers, hand-verified in evals/fixtures/crosswalk-golden-expected.json.
read_num() {  # read_num <python-expression-over-d>
  $PY -c "
import json,sys
d=json.load(open(sys.argv[1]))['crosswalks']
print($1)" "$analysis" 2>/dev/null
}
is "ISO scores 88 mapped controls"        "$(read_num "len(d['iso-27001-2022']['controls'])")" "88"
is "ISO reports 28 controls outside CSF"  "$(read_num "len(d['iso-27001-2022']['completeness']['controlsOutsideCSF'])")" "28"
# The other 3 of the 31 unmapped are referenced by the source at Category level, so CSF
# does reach them — telling a reader to assess them from scratch would be false. They
# get their own list; this pins that they left the outside-CSF one.
is "ISO reports 3 reached at Category level only" \
   "$(read_num "len(d['iso-27001-2022']['completeness']['controlsCategoryOnly'])")" "3"
is "and A.5.33 is one of them, not outside CSF" \
   "$(read_num "'A.5.33' in d['iso-27001-2022']['completeness']['controlsCategoryOnly'] and 'A.5.33' not in d['iso-27001-2022']['completeness']['controlsOutsideCSF']")" "True"
# Every catalogue declares whether it holds its framework's full control set. Without
# it an empty outside-CSF list is ambiguous between "CSF reaches everything" and
# "nothing else is catalogued" — opposite claims, and two of these three are the second.
is "ISO declares a full catalogue"        "$(read_num "d['iso-27001-2022']['completeness']['catalogueScope']")" "full"
is "CIS declares a referenced subset"     "$(read_num "d['cis-8.1']['completeness']['catalogueScope']")" "referenced-subset"
is "800-53 declares a referenced subset"  "$(read_num "d['800-53-r5']['completeness']['catalogueScope']")" "referenced-subset"
is "CIS scores 49 mapped controls"        "$(read_num "len(d['cis-8.1']['controls'])")" "49"
is "800-53 scores 206 mapped controls"    "$(read_num "len(d['800-53-r5']['controls'])")" "206"
is "CIS 1.1 is the weakest link, 1"       "$(read_num "[c['score'] for c in d['cis-8.1']['controls'] if c['controlId']=='CIS 1.1'][0]")" "1"
# 3 of 4 is 0.75, which is short of the 0.85 strong floor. This is the assertion that
# fails if bands are ever computed against a fixed maximum again.
is "CIS 5.1 scores 3 and bands moderate on a 0-4 scale" \
   "$(read_num "[c['band'] for c in d['cis-8.1']['controls'] if c['controlId']=='CIS 5.1'][0]")" "moderate"
is "every lens states the scale it banded against" \
   "$(read_num "len({k for k,v in d.items() if v['scale']['max']==4})")" "3"
is "every lens states its aggregation" \
   "$(read_num "len({k for k,v in d.items() if v['aggregation']=={'control':'min','grouping':'mean'}})")" "3"

# Suppression: a band drawn from too thin a basis is withheld, not caveated. CIS 14.1
# has 1 of 2 in-scope contributors rated (50%), under the 60% this Profile requires.
is "CIS 14.1 band is withheld as too thinly rated" \
   "$(read_num "[c['band'] for c in d['cis-8.1']['controls'] if c['controlId']=='CIS 14.1'][0]")" "insufficient"
is "a withheld band carries no score" \
   "$(read_num "[str(c['score']) for c in d['cis-8.1']['controls'] if c['controlId']=='CIS 14.1'][0]")" "None"
is "a fully-rated control is not withheld" \
   "$(read_num "[c['band'] for c in d['cis-8.1']['controls'] if c['controlId']=='CIS 5.1'][0]")" "moderate"
is "every lens states the threshold it withheld against" \
   "$(read_num "len({k for k,v in d.items() if v['suppression']['thresholdPct']==60})")" "3"
# A withheld control must not reach its theme at its withheld value.
is "CIS-14 theme is withheld once its only control is" \
   "$(read_num "[g['band'] for g in d['cis-8.1']['groupings'] if g['groupingId']=='CIS-14'][0]")" "insufficient"

# --- 5. render ---------------------------------------------------------------------
if (cd "$skill/renderers" && $PY render_crosswalk.py --in "$analysis" --out "$report" --offline) \
     >"$work/render.txt" 2>&1; then
  ok "renderer produced a report"
else
  bad "renderer produced a report" "$(tail -3 "$work/render.txt")"
fi

has "report carries the ISO/CIS non-affiliation footer" "$report" "Not affiliated with NIST, ISO, or CIS"
has "report states it is not an audit"                  "$report" "not an audit or certification"
has "report names the rating scale"                     "$report" "rating scale"
has "800-53 titles are verbatim"                        "$report" "Audit Record Review, Analysis, and Reporting"
has "ISO labels are ours"                               "$report" "our own paraphrases"
has "report names the withheld state"                   "$report" "too little rated"
has "an un-enumerable list says so, not blank"          "$report" "This list cannot be produced"
has "Category-only controls are told apart from unreached ones" \
                                                        "$report" "only at Category level"
# --offline must make the file self-contained: no outbound request when it is opened.
hasnt "offline report makes no font request"            "$report" "fonts.googleapis.com"

# Band words must be present as text, not implied by fill colour alone.
missing_band=""
for band in strong moderate weak minimal; do
  grep -q ">$band<" "$report" || missing_band="$missing_band $band"
done
if [ -z "$missing_band" ]; then ok "every band word appears as text"; else
  bad "every band word appears as text" "absent:$missing_band"; fi

# A renderer given an analysis with no lenses must refuse, not emit an empty shell.
if (cd "$skill/renderers" && $PY render_crosswalk.py --in "$work/plain.json" \
      --out "$work/empty.html") >"$work/refuse.txt" 2>&1; then
  bad "renderer refuses an analysis with no lenses" "it exited 0"
else
  ok "renderer refuses an analysis with no lenses"
fi

# --- 6. the guard against a partial run -------------------------------------------
echo
if [ "$checks" -ne "$EXPECTED_CHECKS" ]; then
  printf 'crosswalk-e2e: INCOMPLETE — ran %d of %d checks. Some case stopped early;\n' \
         "$checks" "$EXPECTED_CHECKS"
  printf '  a green count over a partial suite is worse than a red one.\n'
  exit 1
fi
if [ "$fails" -ne 0 ]; then
  printf 'crosswalk-e2e: %d of %d checks FAILED\n' "$fails" "$checks"
  exit 1
fi
printf 'crosswalk-e2e: all %d checks passed\n' "$checks"
