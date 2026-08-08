#!/usr/bin/env bash
# The criticality walk, end to end, against the shipped example — and the colour split that
# carries it onto two surfaces.
#
# The engine self-test pins the walk's pure functions. This suite exists for what a module
# cannot see about itself: that the CLI wires `--context` through to a REAL exported payload,
# that the two-hop trace resolves against the shipped `.biz` rather than a fixture written to
# agree with it, and that D-10 survives all the way to rendered HTML.
#
# The load-bearing case is the D-10 pair (checks 7-10). Criticality must be RAG on the
# operational page and NOT RAG on the board page. Checking only one direction would pass a
# renderer that coloured both the same way — which is the failure the split exists to prevent,
# in whichever direction it happened.
#
# Anti-vacuity: EXPECTED_CHECKS is asserted; the fixture is proved to contain both a traced and
# an untraced arrangement before anything is checked against it; and the RAG grounds come from
# the graphics library at run time rather than from hex literals typed in here.
set -u

PY="${PY:-$(command -v python3)}"
here="$(cd "$(dirname "$0")" && pwd)"
skill="$(cd "$here/.." && pwd)"
repo="$(cd "$skill/../.." && pwd)"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

EXPECTED_CHECKS=13
checks=0
fails=0
ok()  { checks=$((checks + 1)); printf '  ok    %s\n' "$1"; }
bad() { checks=$((checks + 1)); fails=$((fails + 1)); printf '  FAIL  %s\n         %s\n' "$1" "$2"; }
eq()  { if [ "$2" = "$3" ]; then ok "$1"; else bad "$1" "expected '$2', got '$3'"; fi; }

V="$skill/scripts/vendor_register.py"
E="$skill/examples/example-vendors.vnd"
B="$repo/skills/business-context"
echo "criticality: $($PY -V 2>&1)"

# A REAL payload from the shipped .biz, not a fixture written to agree with the engine. If the
# crown-jewel shape and the walk ever drift apart, this is where it shows.
"$PY" "$B/scripts/business_context.py" export "$B/examples/example-org.biz" \
   --out "$work/ctx.json" >/dev/null 2>&1
if "$PY" -c '
import json, sys
cj = json.load(open(sys.argv[1], encoding="utf-8"))["crownJewels"]
rated = [c for c in cj if c.get("criticality")]
linked = [c for c in cj if c.get("dependsOn")]
sys.exit(0 if rated and linked else 1)' "$work/ctx.json"; then
  ok "the shipped .biz exports crown jewels carrying a criticality and a dependsOn"
else
  bad "the shipped .biz carries what the walk needs" \
      "no crown jewel declares a criticality or a dependency — every check below would pass \
over a payload the walk cannot use"
fi

"$PY" "$V" analyze "$E" --context "$work/ctx.json" --today 2026-08-07 --out "$work/a.json" \
   >/dev/null 2>&1
q() { "$PY" -c 'import json,sys
a = json.load(open(sys.argv[1]))
print(eval(sys.argv[2]))' "$work/a.json" "$1"; }

# --- the fixture is worth checking against ------------------------------------
traced=$(q 'len([r for r in a["arrangements"] if r["criticality"] not in ("untraced","unclassified")])')
untraced=$(q 'len([r for r in a["arrangements"] if r["criticality"] == "untraced"])')
if [ "$traced" -ge 1 ] && [ "$untraced" -ge 1 ]; then
  ok "the example carries both traced ($traced) and untraced ($untraced) arrangements"
else
  bad "the example carries both traced and untraced arrangements" \
      "traced=$traced untraced=$untraced — a one-sided fixture proves one direction"
fi

# --- the walk -----------------------------------------------------------------
eq "a two-hop dependency resolves through the component to the workflow" \
   "['SCADA gateway', 'Plant historian (Dublin)']" \
   "$(q '[r["trace"] for r in a["arrangements"] if r["id"] == "VA-001"][0]')"
eq "...and inherits that workflow's declared criticality" "high" \
   "$(q '[r["derived"] for r in a["arrangements"] if r["id"] == "VA-001"][0]')"
# THE rule. An arrangement supporting nothing declared must not land at the bottom of the scale.
eq "an arrangement the walk cannot trace is 'untraced', never the lowest level" "untraced" \
   "$(q '[r["criticality"] for r in a["arrangements"] if r["id"] == "VA-003"][0]')"
eq "and 'untraced' never appears as a member of the scale" "False" \
   "$(q '"untraced" in a["scale"]')"
# A confirmed level differing from the derived one is a finding, not an error, and is CARRIED.
eq "a derived/confirmed disagreement is reported rather than resolved" "True" \
   "$(q 'any(e["trigger"] == "criticality-conflict" for e in a["escalations"])')"

# --- no context at all: untraced everywhere, and never a refusal ---------------
#
# Classified fresh, NOT re-analysed. `analyze` reports the criticality that was stored when the
# walk ran; re-deriving at analyze time would silently rewrite a judgement somebody signed. So
# the standalone case has to be built by classifying with no profile, which is what a user with
# no `.biz` actually does.
"$PY" "$V" init "$work/solo.vnd" --org "Solo Ltd" >/dev/null 2>&1
"$PY" "$V" add-vendor "$work/solo.vnd" --name "Some Provider" >/dev/null 2>&1
for svc in "hosting" "payroll" "logging"; do
  "$PY" "$V" add-arrangement "$work/solo.vnd" --vendor V-001 --services "$svc" \
     --owner "An Owner" --supports "Plant historian (Dublin)" >/dev/null 2>&1
done
solo_rc=0
for aid in VA-001 VA-002 VA-003; do
  "$PY" "$V" classify "$work/solo.vnd" --arrangement "$aid" >/dev/null 2>&1 || solo_rc=1
done
"$PY" "$V" analyze "$work/solo.vnd" --today 2026-08-07 --out "$work/solo.json" >/dev/null 2>&1
d=$("$PY" -c 'import json,sys
a = json.load(open(sys.argv[1]))
print(len([r for r in a["arrangements"] if r["derived"] == "untraced"]))' "$work/solo.json")
if [ "$solo_rc" -eq 0 ] && [ "$d" -eq 3 ]; then
  ok "with no profile at all, every derivation is untraced ($d/3) and nothing is refused"
else
  bad "with no profile, every derivation is untraced and nothing refuses" \
      "$d/3 untraced, classify exit $solo_rc — §2.1 says this skill works standalone"
fi

# --- D-10, on rendered HTML ---------------------------------------------------
( cd "$skill/renderers" \
  && "$PY" render_operational.py --in "$work/a.json" --out "$work/op.html" \
  && "$PY" render_board.py --in "$work/a.json" --out "$work/bd.html" \
       --translations "$skill/examples/example-translations.json" ) >/dev/null 2>&1

# RAG grounds read from the graphics library at run time. A checker that shared hex literals
# with the renderer would prove only that somebody typed the same string twice.
"$PY" "$here/_critprobe.py" - ragset > "$work/rag.txt"
crit_ops=$("$PY" "$here/_critprobe.py" "$work/op.html" crit)
crit_bd=$("$PY" "$here/_critprobe.py" "$work/bd.html" crit)
trig_bd=$("$PY" "$here/_critprobe.py" "$work/bd.html" trig)

rag_hits() {  # <lines> -> count of backgrounds that are RAG grounds
  printf '%s\n' "$1" | awk -F'\t' 'NF==2{print $2}' | grep -c -F -f "$work/rag.txt" || true
}
lvl_lines() { printf '%s\n' "$1" | grep -vP '^(untraced|unclassified)\t' 2>/dev/null \
                || printf '%s\n' "$1" | grep -v -E '^(untraced|unclassified)	'; }

if [ "$(rag_hits "$(lvl_lines "$crit_ops")")" -ge 1 ]; then
  ok "operational: a real criticality level is RAG-coloured — triage for a reader who knows the scale"
else
  bad "operational RAG-colours a real criticality level" "none of them was"
fi
if [ "$(rag_hits "$crit_bd")" -eq 0 ]; then
  ok "board: NO criticality mark is RAG — it is a classification, and colour is kept for decisions"
else
  bad "board keeps RAG off criticality marks" "$(printf '%s' "$crit_bd")"
fi
if [ "$(rag_hits "$trig_bd")" -ge 1 ]; then
  ok "...and the board DOES use RAG, on the escalations — so the split is a choice, not a blank page"
else
  bad "the board uses RAG on escalations" "nothing was RAG, so the check above proves nothing"
fi
un=$(printf '%s\n%s\n' "$crit_ops" "$crit_bd" | grep -E '^untraced	' || true)
if [ -n "$un" ] && [ "$(rag_hits "$un")" -eq 0 ]; then
  ok "untraced is neutral on BOTH surfaces — it is not a severity and never borrows one"
else
  bad "untraced is neutral on both surfaces" "${un:-no untraced mark was rendered at all}"
fi
if [ "$(printf '%s\n%s\n' "$crit_ops" "$crit_bd" | awk -F'\t' 'NF==2 && $1==""' | wc -l)" -eq 0 ]; then
  ok "and every criticality mark carries its word, so colour never carries the meaning alone"
else
  bad "every criticality mark carries its word" "one rendered with no text"
fi

if [ "$checks" -ne "$EXPECTED_CHECKS" ]; then
  printf 'criticality: ran %s checks, expected %s\n' "$checks" "$EXPECTED_CHECKS"; exit 1; fi
if [ "$fails" -ne 0 ]; then
  printf 'criticality: %s of %s checks FAILED\n' "$fails" "$checks"; exit 1; fi
printf 'criticality: all %s checks passed\n' "$checks"
