#!/usr/bin/env bash
# Counts, never proportions — proved, not asserted.
#
# "68% of policy requirements covered" is the single most requestable number this skill could
# produce and the one it must not. Two things are wrong with it and only the second is
# obvious.
#
#   The denominator is not what a reader thinks. The twenty-two requirements here are the
#   NIST policy spine — the Policy and Procedures control in each SP 800-53 Rev. 5 family
#   plus CSF GV.PO-01/-02. They are not the organisation's obligations. A percentage of them
#   is a completeness figure for a catalogue nobody claimed was complete, and it will be read
#   as a programme measurement by every board that has ever seen one.
#
#   And a proportion is a coverage claim wearing a number. `no-coverage-claim.sh` forbids the
#   word; a percentage says the same thing in a form that survives every word list.
#
# Two halves, because either alone is escapable:
#
#   BEHAVIOURAL — no float appears anywhere in a produced analysis, and no per-cent sign
#   appears in the analysis, the text requirement view, or the visible text of the rendered
#   page. The float rule is the sharp one: this engine has no legitimate fractional value, so
#   any ratio at all shows up as a type change before anyone has to guess at wording.
#
#   STATIC — no shipped .py defines a function named for a proportion, and no non-docstring
#   string literal formats one. Catches the figure computed for a caller that does not exist
#   yet, which the behavioural half cannot see.
#
# Anti-vacuity: EXPECTED_CHECKS is asserted; the probe register is proved to hold a mix of
# states first, because an analysis with nothing in it has no proportion to express.
#
# Mutation-tested below and registered in guard-proofs/no-coverage-percentage.json.
set -u

PY="${PY:-$(command -v python3)}"
here="$(cd "$(dirname "$0")" && pwd)"
skill="$(cd "$here/.." && pwd)"
work="$(mktemp -d)"
. "$here/../../../tools/eval-probe.sh"   # `probe` — a crashed check is not a clean one (BL-121)
trap 'rm -rf "$work"' EXIT

EXPECTED_CHECKS=9
checks=0
fails=0
ok()  { checks=$((checks + 1)); printf '  ok    %s\n' "$1"; }
bad() { checks=$((checks + 1)); fails=$((fails + 1)); printf '  FAIL  %s\n         %s\n' "$1" "$2"; }

A="$skill/scripts/policy_register.py"
S="$work/s.pol"
echo "no-coverage-percentage: $($PY -V 2>&1)"

"$PY" "$A" init "$S" --org "Probe Ltd" >/dev/null 2>&1
"$PY" "$A" add "$S" --title "Information Security Policy" --owner "CISO" \
   --map AC-1 --map GV.PO-01 >/dev/null 2>&1
"$PY" "$A" approve "$S" --id P-001 --by "The Board" --on 2026-01-05 >/dev/null 2>&1
"$PY" "$A" add "$S" --title "Physical Security Policy" --owner "Facilities" --map PE-1 >/dev/null 2>&1
"$PY" "$A" analyze "$S" --today 2026-06-01 --out "$work/a.json" >/dev/null 2>&1
"$PY" "$A" requirements "$S" --today 2026-06-01 --out "$work/req.txt" >/dev/null 2>&1
(cd "$skill/renderers" && "$PY" render_requirements.py --in "$work/a.json" \
   --out "$work/req.html" --offline) >/dev/null 2>&1

# The probe has something to be wrong about: a mix of states, so a proportion would be a
# number somebody actually wants. On a register where every row read the same, a percentage
# would be 0 or 100 and this guard would be watching an edge case.
res=$(probe "$work/a.json" <<'PY'
import json, sys
data = json.load(open(sys.argv[1], encoding="utf-8"))
counts = data["stateCounts"]
problems = []
present = [k for k, v in counts.items() if v]
if len(present) < 3:
    problems.append("only %d state(s) present (%s); a proportion of this would be trivial"
                    % (len(present), present))
if sum(counts.values()) != data["requirementCount"]:
    problems.append("counts sum to %d but the catalogue holds %d"
                    % (sum(counts.values()), data["requirementCount"]))
print("; ".join(problems))
PY
)
if [ -z "$res" ]; then
  ok "the probe register holds a mix of states, so a proportion would be tempting"
else
  bad "the probe register is worth scanning" "$res"
fi

# --- behavioural ----------------------------------------------------------------
res=$(probe "$work/a.json" <<'PY'
import json, sys
data = json.load(open(sys.argv[1], encoding="utf-8"))
found = []

def walk(node, where):
    if isinstance(node, dict):
        for k, v in node.items():
            walk(v, "%s.%s" % (where, k))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            walk(v, "%s[%d]" % (where, i))
    elif isinstance(node, float):
        found.append("%s = %r" % (where, node))

walk(data, "")
print("; ".join(found[:5]))
PY
)
if [ -z "$res" ]; then
  ok "no float appears anywhere in the analysis — every figure is a count"
else
  bad "no float appears anywhere in the analysis" "$res"
fi

hit=""
for f in "$work/a.json" "$work/req.txt"; do
  grep -q '%' "$f" && hit="$hit $(basename "$f")"
done
if [ -z "$hit" ]; then
  ok "no per-cent sign in the analysis JSON or the text requirement view"
else
  bad "no per-cent sign in the analysis JSON or the text requirement view" "found in:$hit"
fi

# The rendered page, visible text only. CSS legitimately carries `width:100%`, so the
# stylesheet is stripped first — a check that flagged its own layout rules would be turned
# off within a week.
res=$(probe "$work/req.html" <<'PY'
import re, sys
html = open(sys.argv[1], encoding="utf-8").read()
body = re.sub(r"<style>.*?</style>", " ", html, flags=re.S)
text = re.sub(r"<[^>]+>", " ", body)
hits = re.findall(r"[^\s]{0,24}%[^\s]{0,12}", text)
print("; ".join(hits[:5]))
PY
)
if [ -z "$res" ]; then
  ok "and none in the visible text of the rendered page"
else
  bad "no per-cent sign in the visible text of the rendered page" "$res"
fi

# The counts are reported, and reported as counts. Absence alone would pass on a page that
# said nothing at all.
if grep -q "Of 22 requirements" "$work/req.txt"; then
  ok "the text view states the catalogue size as a count"
else
  bad "the text view states the catalogue size as a count" \
      "no 'Of 22 requirements' line — the counts may have stopped being reported entirely"
fi

# --- static -----------------------------------------------------------------------
#
# `probe` reports a crashed check as OUTPUT and returns 0 on purpose (BL-121), so the exit
# status is not the signal here — the output is. First line is the count, anything after it
# is a finding.
#
# TWO EXEMPTIONS, both found by running this against the code it guards rather than by
# reasoning about it, and both narrow:
#
#   CSS. `width:100%%` is a layout rule, not a figure. So `%%` is only a finding when a
#   numeric conversion sits immediately before it — `%d%%`, `%.1f%%` — which is what
#   formatting a percentage actually looks like. A guard that flagged its own stylesheet
#   would be switched off inside a week.
#
#   Test labels. The self-test's own check is named "no analyze output contains a percent
#   sign". A scan that flags the sentence describing the rule, in the test that enforces the
#   rule, teaches everyone to work around it — and rewording the label to slip past a guard
#   is precisely the behaviour this suite exists to make impossible. So the first string
#   argument of a check/refuses/ok/bad call is exempt, and nothing else is.
res=$(probe "$skill" <<'PY'
import ast, pathlib, re, sys
root = pathlib.Path(sys.argv[1])
files = sorted(p for p in list(root.glob("scripts/*.py")) + list(root.glob("renderers/*.py"))
               if p.name != "cac_graphics.py")
NAME_BITS = ("percent", "pct", "ratio", "proportion", "share_of", "fraction")
FORMATS_PCT = re.compile(r"%[-+ #0-9.]*[dioufeEgGs]%%")
LABEL_CALLS = ("check", "refuses", "ok", "bad")
problems, scanned = [], 0
for path in files:
    scanned += 1
    tree = ast.parse(path.read_text(encoding="utf-8"))
    exempt = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            doc = ast.get_docstring(node, clean=False)
            if doc is not None:
                exempt.add(doc)
        elif (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
              and node.func.id in LABEL_CALLS and node.args
              and isinstance(node.args[0], ast.Constant)
              and isinstance(node.args[0].value, str)):
            exempt.add(node.args[0].value)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            low = node.name.lower()
            for bit in NAME_BITS:
                if bit in low:
                    problems.append("%s:%d def %s — named for a proportion"
                                    % (path.name, node.lineno, node.name))
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            if node.value in exempt:
                continue
            low = node.value.lower()
            if FORMATS_PCT.search(node.value) or "percent" in low or "per cent" in low:
                problems.append("%s:%d formats a percentage: %r"
                                % (path.name, node.lineno, node.value[:60]))
print("scanned %d" % scanned)
for p in problems:
    print(p)
PY
)
count=$(printf '%s\n' "$res" | head -1)
count=${count#scanned }
found=$(printf '%s\n' "$res" | tail -n +2 | tr '\n' ' ')
if [ -z "${found// /}" ]; then
  ok "no shipped .py defines or formats a proportion"
else
  bad "no shipped .py defines or formats a proportion" "$found"
fi
want=$(ls "$skill"/scripts/*.py "$skill"/renderers/*.py 2>/dev/null | grep -vc '/cac_graphics\.py$')
if [ "${count:-0}" -eq "${want:-0}" ] && [ "${want:-0}" -ge 1 ] 2>/dev/null; then
  ok "and the scan read all $count shipped file(s)"
else
  bad "the static scan covers every shipped .py" "it read ${count:-0} of ${want:-0}"
fi

# --- the guard's own teeth ----------------------------------------------------------
"$PY" -c '
import json, sys
data = json.load(open(sys.argv[1], encoding="utf-8"))
counts = data["stateCounts"]
data["declaredShare"] = round(
    100.0 * (counts["approved-policy"] / float(data["requirementCount"])), 1)
json.dump(data, open(sys.argv[2], "w", encoding="utf-8"), indent=2)
' "$work/a.json" "$work/mutant.json"
res=$(probe "$work/mutant.json" <<'PY'
import json, sys
data = json.load(open(sys.argv[1], encoding="utf-8"))
found = []

def walk(node, where):
    if isinstance(node, dict):
        for k, v in node.items():
            walk(v, "%s.%s" % (where, k))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            walk(v, "%s[%d]" % (where, i))
    elif isinstance(node, float):
        found.append("%s = %r" % (where, node))

walk(data, "")
print("; ".join(found[:5]))
PY
)
if [ -n "$res" ]; then
  ok "the behavioural half fails on a proportion written into the analysis"
else
  bad "the behavioural half fails on a proportion written into the analysis" \
      "it passed an analysis carrying declaredShare as a float"
fi

# The static half, against a copy carrying a function that computes the figure but never
# emits it. This is the way in that matters: the number gets written for a caller that does
# not exist yet, ships, and reaches a page two releases later.
mkdir -p "$work/mutant/scripts"
cp "$A" "$work/mutant/scripts/policy_register.py"
cat >> "$work/mutant/scripts/policy_register.py" <<'PYEOF'


def declared_percent(counts, total):
    return "%.1f%% declared" % (100.0 * counts["approved-policy"] / total)
PYEOF
res=$(probe "$work/mutant" <<'PY'
import ast, pathlib, re, sys
root = pathlib.Path(sys.argv[1])
NAME_BITS = ("percent", "pct", "ratio", "proportion", "share_of", "fraction")
FORMATS_PCT = re.compile(r"%[-+ #0-9.]*[dioufeEgGs]%%")
problems = []
for path in sorted(root.glob("scripts/*.py")):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and any(b in node.name.lower() for b in NAME_BITS):
            problems.append("def %s" % node.name)
        elif (isinstance(node, ast.Constant) and isinstance(node.value, str)
              and FORMATS_PCT.search(node.value)):
            problems.append("format %r" % node.value[:40])
print("; ".join(problems))
PY
)
if [ -n "$res" ]; then
  ok "and the static half fails on a proportion computed but never emitted"
else
  bad "the static half fails on a proportion computed but never emitted" \
      "it passed a file defining declared_percent() returning '%.1f%%'"
fi

echo
if [ "$checks" -ne "$EXPECTED_CHECKS" ]; then
  printf 'no-coverage-percentage: ran %s checks, expected %s\n' "$checks" "$EXPECTED_CHECKS"; exit 1; fi
if [ "$fails" -ne 0 ]; then
  printf 'no-coverage-percentage: %s of %s checks FAILED\n' "$fails" "$checks"; exit 1; fi
printf 'no-coverage-percentage: all %s checks passed\n' "$checks"
