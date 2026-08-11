#!/usr/bin/env bash
# The posture report says what is RECORDED, and never how good it is (BL-222).
#
# The framing, in Darren's words: *"We are not creating a scoring — we are evaluating the
# completeness of the defensibility of the program. They could write a policy stating there are
# to be no authentications… the tool would be able to show you addressed that (even though
# that's a huge security issue)."*
#
# So the report answers **can you show your work?** and never **is your work any good?** Those
# are different questions and only the first is answerable from records. A CISO who showed an
# auditor a report claiming the second would be less defensible than one who showed a
# spreadsheet, because the report looks like a system.
#
# TWO HALVES:
#
#   1. NO-SCORE — no float anywhere in the payload, and no `%` in the JSON or the text. A
#      maturity number is the largest version of the mistake `vendor-register` refuses with a
#      vendor score and `incident-materiality` refuses with a materiality verdict, and this is
#      the page most likely to be read as a verdict because it is the page that aggregates.
#
#   2. ALL-MAPPED — every one of the 106 Subcategories in the shipped Core resolves to an
#      owner or is explicitly unowned. The map is authored at CATEGORY grain, so a forgotten
#      category silently drops every outcome under it; this is the check that makes the
#      compression safe. The expected set is derived from the CORE, never from a hand-kept
#      list, and joined to `CORE_EXPECTED` rather than re-counted.
#
# The probe builds a Profile with a MIX of states and an unreadable store, so a percentage
# would be tempting to compute and an `unknown` has something to be confused with.
set -u

PY="${PY:-$(command -v python3)}"
here="$(cd "$(dirname "$0")" && pwd)"
skill="$(cd "$here/.." && pwd)"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

EXPECTED_CHECKS=12
checks=0
fails=0
ok()  { checks=$((checks + 1)); printf '  ok    %s\n' "$1"; }
bad() { checks=$((checks + 1)); fails=$((fails + 1)); printf '  FAIL  %s\n         %s\n' "$1" "$2"; }
eq()  { if [ "$2" = "$3" ]; then ok "$1"; else bad "$1" "expected '$2', got '$3'"; fi; }

echo "posture-no-score: $($PY -V 2>&1)"

E="$skill/scripts/profile_analysis.py"
"$PY" "$E" init --name "Thameside plc" --out "$work/p.csfp" >/dev/null 2>&1 || {
  printf 'posture-no-score: FIXTURE FAILED — init errored\n'; exit 1; }

# A declared store that is NOT there, so `unknown` has to be distinguishable from `no record`.
"$PY" "$E" posture "$work/p.csfp" --risk "$work/absent.rr" --json > "$work/r.json" 2>/dev/null
"$PY" "$E" posture "$work/p.csfp" --risk "$work/absent.rr" > "$work/r.txt" 2>/dev/null

# --- HALF 1: NO SCORE ------------------------------------------------------------------
# A recursive walk, not a top-level scan: a maturity number would arrive nested inside an
# outcome row, which is exactly where a shallow check would miss it.
eq "no float appears ANYWHERE in the posture payload, at any depth" "no-floats" \
   "$("$PY" - "$work/r.json" <<'PYEOF'
import json, sys
def walk(o):
    if isinstance(o, float): return True
    if isinstance(o, dict): return any(walk(v) for v in o.values())
    if isinstance(o, list): return any(walk(v) for v in o)
    return False
print("FLOAT-FOUND" if walk(json.load(open(sys.argv[1]))) else "no-floats")
PYEOF
)"
eq "...and no percent sign in the JSON" "0" \
   "$($PY -c 'import sys;print(open(sys.argv[1],encoding="utf-8").read().count("%"))' "$work/r.json")"
eq "...nor in the rendered text" "0" \
   "$($PY -c 'import sys;print(open(sys.argv[1],encoding="utf-8").read().count("%"))' "$work/r.txt")"
# The vocabulary of a scale, not just the arithmetic of one. A band called `level 3` would
# carry no float and still be a maturity score.
scale="$(grep -Eio 'maturity|out of 5|level [0-9]|score of|[0-9]+/[0-9]+' "$work/r.txt" | head -3 || true)"
eq "...and no vocabulary of a scale — maturity, levels, N-out-of-M" "" "$scale"

# ...and the report is NOT simply empty of numbers, which would pass everything above while
# reporting nothing. Counts are integers and they are present.
eq "counts ARE reported, as integers — the guard bounds the report, it does not gut it" "5" \
   "$("$PY" -c 'import json,sys
d = json.load(open(sys.argv[1]))
print(sum(1 for v in d["counts"].values() if isinstance(v, int) and not isinstance(v, bool)))' "$work/r.json")"

# --- HALF 2: EVERY OUTCOME RESOLVES ----------------------------------------------------
# Derived from the CORE and joined to CORE_EXPECTED, never re-counted here.
eq "every Subcategory in the shipped Core resolves to an owner or is explicitly unowned" \
   "106 106 0" \
   "$("$PY" - "$E" <<'PYEOF'
import importlib.util, sys
spec = importlib.util.spec_from_file_location("pa", sys.argv[1])
pa = importlib.util.module_from_spec(spec); spec.loader.exec_module(pa)
core = pa.load_core()
mapped = pa.expand_outcome_owners(core, pa.load_outcome_owners())
want = pa.CORE_EXPECTED["subcategories"]
missing = [s["id"] for f in core["hierarchy"] for c in f.get("categories", [])
           for s in c.get("subcategories", []) if s["id"] not in mapped]
print("%d %d %d" % (want, len(mapped), len(missing)))
PYEOF
)"
# ...and every resolution names WHY, so a reader can tell routing from a guess.
eq "...and every one carries a \`means\` sentence" "0" \
   "$("$PY" - "$E" <<'PYEOF'
import importlib.util, sys
spec = importlib.util.spec_from_file_location("pa", sys.argv[1])
pa = importlib.util.module_from_spec(spec); spec.loader.exec_module(pa)
m = pa.expand_outcome_owners(pa.load_core(), pa.load_outcome_owners())
print(sum(1 for v in m.values() if not str(v.get("means") or "").strip()))
PYEOF
)"

# --- UNKNOWN IS NOT NO-RECORD ----------------------------------------------------------
eq "an unreadable store yields \`unknown\`, never \`no record\`, for the outcomes it owns" "True" \
   "$("$PY" -c 'import json,sys
d = json.load(open(sys.argv[1]))
print(d["counts"]["unknown"] > 0 and bool(d["notRead"]))' "$work/r.json")"
case "$(cat "$work/r.txt")" in
  *"a different fact from a clean register"*)
    ok "...and says so in the words attention-surface uses, copied not paraphrased" ;;
  *) bad "the unread wording is copied verbatim" "phrase absent" ;;
esac
# POSITION, not merely presence. A reader who meets bands first has formed a view before
# learning a store was missing.
eq "...and the NOT READ block precedes anything that looks like a result" "True" \
   "$("$PY" -c 'import sys
t = open(sys.argv[1], encoding="utf-8").read()
print(t.index("NOT READ") < t.index("BANDS") < t.index("BY OUTCOME"))' "$work/r.txt")"

# --- D-7: THE CAVEAT IS A BLOCK ABOVE THE RESULTS --------------------------------------
eq "the limit sentence is a block ABOVE the bands, not a footnote" "True" \
   "$("$PY" -c 'import sys
t = open(sys.argv[1], encoding="utf-8").read()
print(t.index("WHAT THIS REPORT DOES NOT SAY") < t.index("BANDS"))' "$work/r.txt")"
# ⚠️ It must name the bands this report ACTUALLY has. "addressed" appears in no band name, so
# a caveat about "addressed" would describe a state that does not exist here.
case "$(cat "$work/r.txt")" in
  *"\`well-evidenced\` means a record exists"*)
    ok "...and it names a real band rather than a state the report does not have" ;;
  *) bad "the caveat names a real band" "it does not quote well-evidenced" ;;
esac

echo
if [ "$checks" -ne "$EXPECTED_CHECKS" ]; then
  printf 'posture-no-score: ran %d checks, expected %d — a case stopped executing\n' \
         "$checks" "$EXPECTED_CHECKS"; exit 1; fi
if [ "$fails" -ne 0 ]; then
  printf 'posture-no-score: %d of %d checks FAILED\n' "$fails" "$checks"; exit 1; fi
printf 'posture-no-score: all %d checks passed\n' "$checks"
