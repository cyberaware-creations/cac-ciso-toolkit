#!/usr/bin/env bash
# The guard that stops this skill becoming every other third-party tool.
#
# Every commercial vendor-risk product emits a score, and it is the same failure this suite
# refuses everywhere else: a generated number that looks like an assessment, that nobody can
# reproduce, and that disagrees with the register which actually owns scoring. Findings go to
# `risk-register` through a one-way bridge and are scored once, there, under L×I and SP
# 800-30 with an appetite to judge them against.
#
# Two halves, because either alone is escapable:
#
#   BEHAVIOURAL — nothing the engine emits is named like a score. Catches the key somebody
#   adds to `analyze` output next year.
#
#   STATIC — no shipped .py multiplies or averages a criticality against a finding count or
#   a severity. Catches the score computed internally and rendered under an innocent name,
#   which the behavioural half cannot see because it is a rename, not a calculation.
#
# Anti-vacuity: EXPECTED_CHECKS is asserted; the fixture is proved non-empty before anything
# is checked against it; the static scan reports how many files it read so a glob that
# stopped matching cannot pass silently. Mutation-tested by introducing a real
# `criticality_rank * finding_count` — a guard never seen to fail is not known to work.
set -u

PY="${PY:-$(command -v python3)}"
here="$(cd "$(dirname "$0")" && pwd)"
skill="$(cd "$here/.." && pwd)"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

EXPECTED_CHECKS=6
checks=0
fails=0
ok()  { checks=$((checks + 1)); printf '  ok    %s\n' "$1"; }
bad() { checks=$((checks + 1)); fails=$((fails + 1)); printf '  FAIL  %s\n         %s\n' "$1" "$2"; }

V="$skill/scripts/vendor_register.py"
echo "no-vendor-score: $($PY -V 2>&1)"

# A register with real content, not an empty one. An empty analysis has no keys to be wrong
# and would pass every check below while proving nothing.
"$PY" "$V" init "$work/s.vnd" --org "Probe Ltd" >/dev/null 2>&1
"$PY" "$V" add-vendor "$work/s.vnd" --name "Contoso Cloud" >/dev/null 2>&1
"$PY" "$V" add-arrangement "$work/s.vnd" --vendor V-001 --services "production hosting" \
   --owner "CTO" --supports "Plant historian (Dublin)" >/dev/null 2>&1
"$PY" "$V" add-arrangement "$work/s.vnd" --vendor V-001 --services "marketing sandbox" \
   --owner "CMO" >/dev/null 2>&1
cat > "$work/ctx.json" <<'JSON'
{"contractVersion": "CAC-AP-1",
 "crownJewels": [{"system": "Plant historian (Dublin)", "criticality": "high",
                  "dependsOn": ["SCADA gateway"]}]}
JSON
"$PY" "$V" classify "$work/s.vnd" --arrangement VA-001 --context "$work/ctx.json" \
   --confirm high --by "D. Galleyne" >/dev/null 2>&1
"$PY" "$V" classify "$work/s.vnd" --arrangement VA-002 --context "$work/ctx.json" \
   >/dev/null 2>&1
"$PY" "$V" analyze "$work/s.vnd" --context "$work/ctx.json" --out "$work/a.json" >/dev/null 2>&1

n=$("$PY" -c 'import json,sys;print(len(json.load(open(sys.argv[1]))["arrangements"]))' \
    "$work/a.json" 2>/dev/null || echo 0)
if [ "$n" -ge 2 ]; then
  ok "the probe register produced an analysis with $n arrangements to inspect"
else
  bad "the probe register produced something to inspect" \
      "only $n arrangements — every check below would pass over an empty file"
fi

# --- behavioural --------------------------------------------------------------
if "$PY" "$here/_scoreprobe.py" "$work/a.json" --keys 2>"$work/keys.err"; then
  ok "no key the engine emits is named like a score"
else
  bad "no key the engine emits is named like a score" "$(cat "$work/keys.err")"
fi
if "$PY" "$here/_scoreprobe.py" "$work/a.json" --counts 2>"$work/counts.err"; then
  ok "criticality is counted per named level, never aggregated into one number"
else
  bad "criticality is counted per named level" "$(cat "$work/counts.err")"
fi

# --- static -------------------------------------------------------------------
scanned=$("$PY" "$here/_scorescan.py" "$skill" 2>"$work/static.err")
rc=$?
if [ "$rc" -eq 0 ]; then
  ok "no shipped file multiplies or averages a criticality against a count or severity"
else
  bad "no shipped file computes a score internally" "$(cat "$work/static.err")"
fi
# A glob that stopped matching is a guard reading nothing, which passes in silence.
count=${scanned#scanned }
if [ "${count:-0}" -ge 1 ] 2>/dev/null; then
  ok "and the static scan actually read $count shipped file(s), not zero"
else
  bad "the static scan read at least one file" "it read none, so it proved nothing"
fi

# The arithmetic route to a score, closed at source: you cannot average what you cannot rank.
if "$PY" -c '
import importlib.util, sys
spec = importlib.util.spec_from_file_location("vr", sys.argv[1])
vr = importlib.util.module_from_spec(spec); spec.loader.exec_module(vr)
store = vr.new_store("x")
for state in (vr.UNTRACED, vr.UNCLASSIFIED):
    try:
        vr.criticality_rank(store, state)
    except vr.Refusal:
        continue
    print("%s was given a rank" % state, file=sys.stderr)
    sys.exit(1)
' "$V" 2>"$work/rank.err"; then
  ok "and neither untraced nor unclassified can be given a numeric rank at all"
else
  bad "untraced and unclassified cannot be ranked" "$(cat "$work/rank.err")"
fi

if [ "$checks" -ne "$EXPECTED_CHECKS" ]; then
  printf 'no-vendor-score: ran %s checks, expected %s\n' "$checks" "$EXPECTED_CHECKS"
  exit 1
fi
if [ "$fails" -ne 0 ]; then
  printf 'no-vendor-score: %s of %s checks FAILED\n' "$fails" "$checks"; exit 1; fi
printf 'no-vendor-score: all %s checks passed\n' "$checks"
