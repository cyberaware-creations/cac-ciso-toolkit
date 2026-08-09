#!/usr/bin/env bash
# A mapped policy never means the requirement is met — proved, not asserted.
#
# This is the rule the whole skill exists to hold, and it is the one most likely to be
# relaxed later, for the same reason as ai-register's no-closed-state: its absence looks like
# a gap rather than a decision. Somebody will open the requirement view, see twelve rows with
# an approved policy against them, and reach for the obvious next feature — a column saying
# `covered`. It is a one-line change, nothing else in the codebase would object, and the
# result is a register asserting the single most common quiet untruth in this industry: that
# having a policy for something means the something is controlled.
#
# A CISO who showed an auditor a register making that claim would be LESS defensible than one
# who showed a spreadsheet, because the register looks like a system.
#
# Three checks in two halves, because either half alone is escapable:
#
#   BEHAVIOURAL — nothing in a produced analysis, at any depth, in a key or in a status
#   value, says a requirement is met; and no chip on the rendered page carries a coverage
#   word. Chips are scanned separately because a chip IS the verdict a reader takes away.
#
#   STATIC — no shipped .py names a function for coverage, assigns a coverage field, or holds
#   a coverage token as a value. Catches the field computed and rendered but never persisted,
#   which the behavioural half cannot see.
#
# Anti-vacuity: EXPECTED_CHECKS is asserted; the probe register is proved to carry approved
# policies mapped to requirements before anything is checked against it (an empty register
# has nothing to be wrong about); each scan reports how much it read and the count is
# recomputed here from the filesystem rather than taken from the scanner.
#
# Mutation-tested below and registered in guard-proofs/no-coverage-claim.json.
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
echo "no-coverage-claim: $($PY -V 2>&1)"

# A register with real content. An empty one has no requirement to be wrong about and would
# pass every check below while proving nothing — which is why the probe asserts the counts.
"$PY" "$A" init "$S" --org "Probe Ltd" >/dev/null 2>&1
"$PY" "$A" add "$S" --title "Information Security Policy" --owner "CISO" \
   --map AC-1 --map GV.PO-01 >/dev/null 2>&1
"$PY" "$A" approve "$S" --id P-001 --by "The Board" --on 2026-01-05 >/dev/null 2>&1
"$PY" "$A" add "$S" --title "Physical Security Policy" --owner "Facilities" \
   --map PE-1 >/dev/null 2>&1
"$PY" "$A" analyze "$S" --today 2026-06-01 --out "$work/a.json" >/dev/null 2>&1
(cd "$skill/renderers" && "$PY" render_requirements.py --in "$work/a.json" \
   --out "$work/req.html" --offline) >/dev/null 2>&1

# This asserts the SHAPE of the fixture, deliberately not the state slugs. An earlier draft
# checked that AC-1 read `approved-policy`, which meant the mutation that renames that state
# to `covered` defeated this check too — and a precondition that fails for the same reason as
# the rule makes one mutation look like proof of two independent things. The fixture's job is
# to be worth scanning; the rule's job is to be right about it.
res=$(probe "$work/a.json" <<'PY'
import json, sys
data = json.load(open(sys.argv[1], encoding="utf-8"))
rows = {r["id"]: r for r in data["requirements"]}
problems = []
if len(data["policies"]) != 2:
    problems.append("expected 2 policy records, got %d" % len(data["policies"]))
if len(rows.get("AC-1", {}).get("policies") or []) != 1:
    problems.append("AC-1 should have exactly one document mapped to it")
elif rows["AC-1"]["policies"][0].get("state") != "approved":
    problems.append("the document mapped to AC-1 should be approved, reads %r"
                    % rows["AC-1"]["policies"][0].get("state"))
if len(rows.get("PE-1", {}).get("policies") or []) != 1:
    problems.append("PE-1 should have exactly one document mapped to it")
if rows.get("SR-1", {}).get("policyCount") != 0:
    problems.append("SR-1 should have nothing mapped to it")
print("; ".join(problems))
PY
)
if [ -z "$res" ]; then
  ok "the probe register carries an approved document, a draft one and an unmapped requirement"
else
  bad "the probe register is worth scanning" "$res"
fi

# --- behavioural ---------------------------------------------------------------
scanned=$("$PY" "$here/_coverage.py" --analysis "$work/a.json" 2>"$work/b.err")
rc=$?
if [ "$rc" -eq 0 ]; then
  ok "no key or status in the analysis says a requirement is met"
elif [ "$rc" -eq 2 ]; then
  bad "the analysis was actually inspected" "$(cat "$work/b.err")"
else
  bad "no key or status in the analysis says a requirement is met" "$(cat "$work/b.err")"
fi
count=${scanned#scanned }
if [ "${count:-0}" -eq 22 ] 2>/dev/null; then
  ok "and it read all 22 requirement rows, not a subset"
else
  bad "the analysis scan covers every requirement row" \
      "it read ${count:-0} of 22 — a row this guard is supposed to watch went uninspected"
fi

chips=$("$PY" "$here/_coverage.py" --page "$work/req.html" 2>"$work/c.err")
rc=$?
if [ "$rc" -eq 0 ]; then
  ok "no chip on the rendered page carries a coverage verdict"
elif [ "$rc" -eq 2 ]; then
  bad "the rendered page's chips were actually inspected" "$(cat "$work/c.err")"
else
  bad "no chip on the rendered page carries a coverage verdict" "$(cat "$work/c.err")"
fi

# The claim in one assertion: an approved policy leaves the requirement in a state that
# describes the DOCUMENT. Reading the meaning text rather than the slug, because the slug
# could be renamed to something innocent while the page still said "covered".
res=$(probe "$work/a.json" <<'PY'
import json, sys
data = json.load(open(sys.argv[1], encoding="utf-8"))
rows = {r["id"]: r for r in data["requirements"]}
means = rows["AC-1"]["means"]
problems = []
if "does not say the requirement is met" not in means:
    problems.append("the approved-policy meaning no longer disclaims the coverage reading: %r"
                    % means[:120])
if not any("not evidence that the requirement is met" in n for n in data.get("limits", [])):
    problems.append("the analysis no longer carries the limit that says a mapping is not "
                    "evidence")
if len(data.get("stateMeans") or {}) != 4:
    problems.append("there are now %d requirement states" % len(data.get("stateMeans") or {}))
print("; ".join(problems))
PY
)
if [ -z "$res" ]; then
  ok "a requirement with an approved policy still says, in words, that it is not met"
else
  bad "a requirement with an approved policy disclaims the coverage reading" "$res"
fi

# --- static ---------------------------------------------------------------------
scanned=$("$PY" "$here/_coverage.py" --static "$skill" 2>"$work/s.err")
rc=$?
if [ "$rc" -eq 0 ]; then
  ok "no shipped .py names, assigns or holds a coverage verdict"
else
  bad "no shipped .py names, assigns or holds a coverage verdict" "$(cat "$work/s.err")"
fi
# GP-1.7 — the scan asserts WHICH files it read. `want` is recomputed from the filesystem
# rather than taken from the helper, so narrowing the helper's glob fails here instead of
# quietly shrinking a number nobody reads.
count=${scanned#scanned }
want=$(ls "$skill"/scripts/*.py "$skill"/renderers/*.py 2>/dev/null | grep -vc '/cac_graphics\.py$')
if [ "${count:-0}" -eq "${want:-0}" ] && [ "${want:-0}" -ge 1 ] 2>/dev/null; then
  ok "and the scan read all $count shipped file(s) — every script and renderer but the brand file"
else
  bad "the static scan covers every shipped .py" \
      "it read ${count:-0} of ${want:-0} — a file this guard is supposed to watch is unread"
fi

# --- the guard's own teeth --------------------------------------------------------
#
# Both halves run against a deliberately broken copy. A guard nobody has watched fail is not
# known to work, and this is the rule where that matters most.
mkdir -p "$work/mutant/scripts"
cp "$A" "$work/mutant/scripts/policy_register.py"
cat >> "$work/mutant/scripts/policy_register.py" <<'PYEOF'


def _roll_up(row):
    row["covered"] = bool(row.get("policies"))
    return row
PYEOF
if "$PY" "$here/_coverage.py" --static "$work/mutant" >/dev/null 2>&1; then
  bad "the static half fails on a planted coverage ASSIGNMENT" \
      "it passed a file that assigns row['covered'] under an innocent name"
else
  ok "the static half fails on a planted coverage assignment"
fi

"$PY" -c '
import json, sys
data = json.load(open(sys.argv[1], encoding="utf-8"))
for row in data["requirements"]:
    if row["state"] == "approved-policy":
        row["state"] = "cov" + "ered"
json.dump(data, open(sys.argv[2], "w", encoding="utf-8"), indent=2)
' "$work/a.json" "$work/mutant.json"
if "$PY" "$here/_coverage.py" --analysis "$work/mutant.json" >/dev/null 2>&1; then
  bad "the behavioural half fails on a coverage state written at runtime" \
      "it passed an analysis whose rows read 'covered'"
else
  ok "and the behavioural half fails on a coverage state written into the output"
fi

echo
if [ "$checks" -ne "$EXPECTED_CHECKS" ]; then
  printf 'no-coverage-claim: ran %s checks, expected %s\n' "$checks" "$EXPECTED_CHECKS"; exit 1; fi
if [ "$fails" -ne 0 ]; then
  printf 'no-coverage-claim: %s of %s checks FAILED\n' "$fails" "$checks"; exit 1; fi
printf 'no-coverage-claim: all %s checks passed\n' "$checks"
