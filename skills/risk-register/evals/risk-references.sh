#!/usr/bin/env bash
# A risk can say WHERE IT CAME FROM, and the record asserts nothing beyond that (BL-117).
#
# NIST IR 8286r1 s 3.2.2 names ATT&CK as a threat-modelling technique. A CISO who enumerates
# threats that way produces risks, and until v0.96.0 the register had nowhere to say so. The
# board question this closes is not a technical one: *what did we look at to find these, and
# what did we not look at?*
#
# THE TRAP THIS FIELD EXISTS TO AVOID is not that references were missing — it is where a CISO
# would have put them instead. `sourceRef` and `csfSubcategoryId` both look like the answer and
# both are `merge_import` MATCHING KEYS. Typing `ATT&CK T1566.001` into either means the next
# import carrying that string silently UPDATES an assessed risk rather than adding a new one:
# invisible, and destructive of a score somebody set. That property is asserted in the engine
# self-test, where `merge_import` lives, and it fails if `references` is ever added to the
# match chain. This suite covers the rest — the command, the audit trail, and the surface.
#
# WHAT IS DELIBERATELY NOT HERE. No coverage percentage, no count against ATT&CK, no "techniques
# you have not considered". Every one of those needs the bundled matrix this field exists to
# avoid, and each would be the tool asserting completeness it cannot possibly know. The last
# check pins that silence, because it is the kind of thing a later well-meaning change adds.
#
# ⚠️ Classified `not-a-guard` in tools/guard-registry.json, honestly: this asserts what the
# product DOES, not a defect-cannot-occur property. The defect-cannot-occur half of BL-117 is
# the `merge_import` assertion in the self-test.
set -u

PY="${PY:-$(command -v python3)}"
here="$(cd "$(dirname "$0")" && pwd)"
skill="$(cd "$here/.." && pwd)"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

EXPECTED_CHECKS=11
checks=0
fails=0
ok()  { checks=$((checks + 1)); printf '  ok    %s\n' "$1"; }
bad() { checks=$((checks + 1)); fails=$((fails + 1)); printf '  FAIL  %s\n         %s\n' "$1" "$2"; }
eq()  { if [ "$2" = "$3" ]; then ok "$1"; else bad "$1" "expected '$2', got '$3'"; fi; }

echo "risk-references: $($PY -V 2>&1)"

S="$skill/scripts/score_register.py"
cp "$skill/examples/example-register-v2.rr" "$work/r.rr"

# --- T1. A register written before this key existed still loads ----------------------
# The normalisation loop backfills `[]`. A v1 store that has never seen `set-refs` must not
# need migrating, and every risk in it must read as "none declared" rather than as broken.
pre="$("$PY" - "$S" "$work/r.rr" <<'PY'
import importlib.util, sys
spec = importlib.util.spec_from_file_location("sr", sys.argv[1])
sr = importlib.util.module_from_spec(spec); spec.loader.exec_module(sr)
reg = sr.load_register(sys.argv[2])
vals = [r.get("references") for r in reg["risks"]]
print("%s %s" % (len(vals), sorted({repr(v) for v in vals})))
PY
)"
eq "a register with no references key loads, every risk backfilled to [] not None" \
   "11 ['[]']" "$pre"

# --- T3/T4. The command, the refusal, and the audit trail ----------------------------
before="$("$PY" -c "import hashlib,sys;print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())" "$work/r.rr")"
refusal="$("$PY" "$S" set-refs "$work/r.rr" R-001 --ref 'ATT&CK T1566.001' 2>&1 || true)"
after="$("$PY" -c "import hashlib,sys;print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())" "$work/r.rr")"
case "$refusal" in
  *"--why is required"*) ok "set-refs without --why is refused" ;;
  *) bad "set-refs without --why is refused" "got: $refusal" ;;
esac
# The property that makes the refusal trustworthy rather than merely loud. Validation runs
# BEFORE the store is opened, so a refused command cannot leave a half-applied register.
eq "...and the refusal leaves the register byte-identical" "$before" "$after"

"$PY" "$S" set-refs "$work/r.rr" R-001 --ref 'ATT&CK T1566.001' 'ID.RA-03' \
  --why 'Q3 threat-modelling workshop, plus the CSF gap review.' >/dev/null 2>&1

# --- T2. `add --ref`, multi-value, and the join that must not happen ------------------
"$PY" "$S" add "$work/r.rr" \
  --title 'Spoofed login page harvests staff credentials' \
  --description 'If a member of staff authenticates to a spoofed page, then an attacker holds working credentials.' \
  --il 3 --ii 4 --rl 2 --ri 4 --ref 'ATT&CK T1566.002' 'ATT&CK T1078' \
  --why 'threat model' >/dev/null 2>&1
"$PY" "$S" add "$work/r.rr" \
  --title 'Backup restore fails at the point it is needed' \
  --description 'If a restore is attempted during an incident, then the recovery window is missed.' \
  --il 2 --ii 4 --rl 2 --ri 3 --why 'no reference' >/dev/null 2>&1

state="$("$PY" - "$work/r.rr" <<'PY'
import json, sys
d = json.load(open(sys.argv[1], encoding="utf-8"))
by = {r["id"]: r.get("references") for r in d["risks"]}
ev = [e for e in d["history"] if e["type"] == "references-set"]
print(json.dumps({
    "set_refs": by.get("R-001"),
    "added_with": by.get("R-012"),
    "added_without": by.get("R-013"),
    "events": len(ev),
    "frm": ev[0].get("from") if ev else None,
    "to": ev[0].get("to") if ev else None,
    "why": bool(ev and ev[0].get("rationale")),
}, sort_keys=True))
PY
)"
get() { "$PY" -c "import json,sys;print(json.dumps(json.loads(sys.argv[1])[sys.argv[2]]))" "$state" "$1"; }

# TWO references, not one string reading "ATT&CK T1566.001 ID.RA-03". `_s()` — which sits
# directly above `_reflist` in the source — JOINS, and would have stored exactly that.
eq "set-refs stores a multi-value flag as a LIST, never joined into one string" \
   '["ATT&CK T1566.001", "ID.RA-03"]' "$(get set_refs)"
eq "add --ref stores its list too" \
   '["ATT&CK T1566.002", "ATT&CK T1078"]' "$(get added_with)"
# `[]`, not `null`. A consumer iterating references must never have to None-guard.
eq "...and add WITHOUT --ref stores an empty list, not null" "[]" "$(get added_without)"
eq "the change is on the history, once" "1" "$(get events)"
# From AND to, because replace-wholesale makes a full overwrite one typo away. The previous
# value in the event is what makes that recoverable from the register itself.
eq "...carrying the previous value as well as the new one, so an overwrite is recoverable" \
   '[] ["ATT&CK T1566.001", "ID.RA-03"]' "$(get frm) $(get to)"

# --- T7. The surface ------------------------------------------------------------------
(cd "$skill/renderers" && "$PY" render_dashboard.py "$work/r.rr" "$work/d.html") >/dev/null 2>&1 || {
  printf 'risk-references: FIXTURE FAILED — render_dashboard errored\n'; exit 1; }

render="$("$PY" - "$work/d.html" <<'PY'
import re, sys
h = open(sys.argv[1], encoding="utf-8").read()
lists = re.findall(r'"references": (\[[^\]]*\])', h)
print("%s %s %s %s" % (
    "found-via" if "Found via" in h else "no-label",
    "cited" if "ATT&CK T1566.001" in h else "missing",
    sum(1 for x in lists if x == "[]"),
    len(lists)))
PY
)"
# A risk WITH references renders them...
eq "a risk with references renders them under their own label" \
   "found-via cited 11 13" "$render"
# ...and one WITHOUT renders nothing at all. Not an em-dash, not "none recorded". Eleven of
# the thirteen risks on this page have no references, and a placeholder on each would turn an
# affordance nobody has used yet into eleven lines of visual debt.
absent="$("$PY" - "$work/d.html" <<'PY'
import re, sys
h = open(sys.argv[1], encoding="utf-8").read()
# The label is emitted only inside the has-references branch, so counting labels against
# risks-with-references is what proves the empty ones drew nothing.
print("%d %d" % (h.count("Found via"), len(re.findall(r'"references": \[".*?"\]', h))))
PY
)"
eq "...and a risk without them renders NOTHING — no em-dash, no placeholder" "1 2" "$absent"

# --- The silence that is the point ----------------------------------------------------
# D-4: the tool asserts nothing about the reference. This is the check that will be under
# pressure, because a coverage percentage looks like value and is one join away from being
# computable. It cannot be computed honestly without the matrix this field exists to avoid.
#
# Scoped to what a READER IS SHOWN — the rendered page and the command's own output — and
# deliberately not to the source. A first draft grepped `score_register.py` too and failed on
# this suite's own sibling prose: the docstring that says the tool must never report
# "techniques you have not considered" matched the pattern for reporting it. A check that
# cannot tell a prohibition from a violation is a check that trains people to delete the
# comment explaining the rule.
"$PY" "$S" set-refs "$work/r.rr" R-001 --ref 'ATT&CK T1566.001' \
  --why 'narrowing to the one technique' >"$work/say.txt" 2>&1
claims="$(grep -Eoi 'coverage of ATT&CK|ATT&CK coverage|techniques covered|% of techniques|have not considered|[0-9]+ of [0-9]+ techniques' \
  "$work/d.html" "$work/say.txt" 2>/dev/null | head -5 || true)"
eq "nothing a reader is SHOWN claims coverage or completeness against ATT&CK" "" "$claims"

echo
if [ "$checks" -ne "$EXPECTED_CHECKS" ]; then
  printf 'risk-references: ran %d checks, expected %d — a case stopped executing\n' \
         "$checks" "$EXPECTED_CHECKS"; exit 1; fi
if [ "$fails" -ne 0 ]; then
  printf 'risk-references: %d of %d checks FAILED\n' "$fails" "$checks"; exit 1; fi
printf 'risk-references: all %d checks passed\n' "$checks"
