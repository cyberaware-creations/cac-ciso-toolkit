#!/usr/bin/env bash
# The vendored requirement spine cannot drift from the nist-csf artifacts it was cut from.
#
# This skill must run from its own directory with no other skill installed (BL-169 D-1), so
# the twenty SP 800-53 Rev. 5 "-1" controls and CSF GV.PO-01/-02 are VENDORED into
# references/requirements.json. Vendoring buys standalone operation and costs exactly one
# thing: two copies that can disagree, silently, with the wrong one shipping.
#
# There is nothing subtle about how that goes wrong. NIST reissues the CSF export, somebody
# regenerates the crosswalk, a family label changes, and this skill keeps rendering the old
# one against a control id that now means something slightly different. Nothing errors. The
# page still looks right.
#
# So the check is regeneration, not inspection: derive the list again from the two shipped
# nist-csf artifacts and compare, field by field, to what this skill carries. One half, and
# it is behavioural — there is no static shape that could express this.
#
# IF nist-csf IS ABSENT THIS FAILS, and that is deliberate. A build-time check that skipped
# when its source was missing would report a clean bill from a run that read nothing, which
# is the failure shape this whole suite is organised against. The skill still RUNS without
# nist-csf; only this proof needs it.
#
# Anti-vacuity: EXPECTED_CHECKS is asserted; both sources are proved non-trivial before the
# comparison; the count of compared fields is reported rather than implied.
#
# Mutation-tested below and registered in guard-proofs/requirement-drift.json.
set -u

PY="${PY:-$(command -v python3)}"
here="$(cd "$(dirname "$0")" && pwd)"
skill="$(cd "$here/.." && pwd)"
repo="$(cd "$skill/../.." && pwd)"
work="$(mktemp -d)"
. "$here/../../../tools/eval-probe.sh"   # `probe` — a crashed check is not a clean one (BL-121)
trap 'rm -rf "$work"' EXIT

EXPECTED_CHECKS=5
checks=0
fails=0
ok()  { checks=$((checks + 1)); printf '  ok    %s\n' "$1"; }
bad() { checks=$((checks + 1)); fails=$((fails + 1)); printf '  FAIL  %s\n         %s\n' "$1" "$2"; }

CAT="$repo/skills/nist-csf/references/crosswalks/800-53-r5.catalog.json"
CORE="$repo/skills/nist-csf/references/nist-csf-2.0-core.json"
VEND="$skill/references/requirements.json"
echo "requirement-drift: $($PY -V 2>&1)"

missing=""
for f in "$CAT" "$CORE" "$VEND"; do
  [ -f "$f" ] || missing="$missing $(basename "$f")"
done
if [ -z "$missing" ]; then
  ok "all three files this check compares are present"
else
  bad "the files this check compares are present" \
      "absent:$missing — this proof cannot run, and a skipped proof is not a passed one"
  printf '\nrequirement-drift: %s of %s checks FAILED\n' "$fails" "$checks"; exit 1
fi

# Both sources are worth reading before anything is compared against them. A crosswalk that
# had been truncated to nothing would make every comparison below pass trivially.
res=$(probe "$CAT" "$CORE" <<'PY'
import json, re, sys
cat = json.load(open(sys.argv[1], encoding="utf-8"))
core = json.load(open(sys.argv[2], encoding="utf-8"))
problems = []
controls = cat.get("controls") or []
if len(controls) < 100:
    problems.append("the crosswalk holds only %d control(s)" % len(controls))
ones = [c for c in controls if re.match(r"^[A-Z]{2}-1$", c.get("id", ""))]
if len(ones) != 20:
    problems.append("the crosswalk holds %d '-1' control(s), not 20" % len(ones))
if not cat.get("groupings"):
    problems.append("the crosswalk carries no family labels")
gvpo = [c for fn in core.get("hierarchy", []) for c in fn.get("categories", [])
        if c.get("id") == "GV.PO"]
if len(gvpo) != 1:
    problems.append("the CSF core holds %d GV.PO categor(y/ies)" % len(gvpo))
elif len(gvpo[0].get("subcategories") or []) != 2:
    problems.append("GV.PO holds %d subcategor(y/ies), not 2"
                    % len(gvpo[0].get("subcategories") or []))
print("; ".join(problems))
PY
)
if [ -z "$res" ]; then
  ok "the nist-csf sources carry 20 '-1' controls, their family labels, and both GV.PO rows"
else
  bad "the nist-csf sources are worth comparing against" "$res"
fi

# --- regenerate and compare -----------------------------------------------------------
compare() {  # compare <vendored-file>  -> prints differences, empty when identical
  probe "$1" "$CAT" "$CORE" <<'PY'
import json, re, sys
vend = json.load(open(sys.argv[1], encoding="utf-8"))
cat = json.load(open(sys.argv[2], encoding="utf-8"))
core = json.load(open(sys.argv[3], encoding="utf-8"))

fam = {g["id"]: g["label"] for g in cat["groupings"]}
want = []
for c in sorted((c for c in cat["controls"] if re.match(r"^[A-Z]{2}-1$", c["id"])),
                key=lambda c: c["id"]):
    want.append({"id": c["id"], "catalogue": "sp-800-53r5", "label": c["label"],
                 "familyId": c["groupingId"], "familyLabel": fam[c["groupingId"]]})
for fn in core["hierarchy"]:
    for cate in fn.get("categories", []):
        if cate["id"] != "GV.PO":
            continue
        for s in cate["subcategories"]:
            want.append({"id": s["id"], "catalogue": "csf-2-0", "label": s["text"],
                         "familyId": "GV.PO", "familyLabel": cate["name"],
                         "implementationExamples": list(s["examples"])})

got = vend.get("requirements") or []
problems = []
if len(got) != len(want):
    problems.append("the vendored spine holds %d requirement(s); the sources yield %d"
                    % (len(got), len(want)))
compared = 0
for i, expected in enumerate(want):
    actual = got[i] if i < len(got) else {}
    for key, value in expected.items():
        compared += 1
        if actual.get(key) != value:
            problems.append("%s.%s vendored as %r; the source says %r"
                            % (expected["id"], key, actual.get(key), value))
extra = [k for row in got for k in row if k not in
         ("id", "catalogue", "label", "familyId", "familyLabel", "implementationExamples")]
if extra:
    problems.append("the vendored rows carry fields the sources do not: %s"
                    % sorted(set(extra)))
print("compared %d" % compared)
for p in problems:
    print(p)
PY
}

res=$(compare "$VEND")
compared=$(printf '%s\n' "$res" | head -1); compared=${compared#compared }
found=$(printf '%s\n' "$res" | tail -n +2 | tr '\n' ' ')
if [ -z "${found// /}" ]; then
  ok "the vendored spine regenerates identically from the nist-csf sources"
else
  bad "the vendored spine regenerates identically from the nist-csf sources" "$found"
fi
# 20 controls x 5 fields + 2 subcategories x 6 fields = 112. Written out rather than derived,
# so a shrinking comparison fails here instead of quietly checking less.
if [ "${compared:-0}" -eq 112 ] 2>/dev/null; then
  ok "and the comparison covered all 112 fields, not a subset"
else
  bad "the comparison covers every field" \
      "it compared ${compared:-0} of 112 — the check narrowed without anyone deciding to"
fi

# --- the guard's own teeth --------------------------------------------------------------
#
# A label edited in the vendored copy. This is what drift looks like from the inside: one
# string, plausible, and no other test in the repo has any opinion about it.
"$PY" -c '
import json, sys
data = json.load(open(sys.argv[1], encoding="utf-8"))
for row in data["requirements"]:
    if row["id"] == "PE-1":
        row["familyLabel"] = "Physical and Environmental Security"
json.dump(data, open(sys.argv[2], "w", encoding="utf-8"), indent=2)
' "$VEND" "$work/mutant.json"
res=$(compare "$work/mutant.json")
found=$(printf '%s\n' "$res" | tail -n +2 | tr '\n' ' ')
if [ -n "${found// /}" ]; then
  ok "the check fails on a single edited family label in the vendored copy"
else
  bad "the check fails on an edited vendored label" \
      "it passed a copy whose PE-1 family label had been rewritten"
fi

echo
if [ "$checks" -ne "$EXPECTED_CHECKS" ]; then
  printf 'requirement-drift: ran %s checks, expected %s\n' "$checks" "$EXPECTED_CHECKS"; exit 1; fi
if [ "$fails" -ne 0 ]; then
  printf 'requirement-drift: %s of %s checks FAILED\n' "$fails" "$checks"; exit 1; fi
printf 'requirement-drift: all %s checks passed\n' "$checks"
