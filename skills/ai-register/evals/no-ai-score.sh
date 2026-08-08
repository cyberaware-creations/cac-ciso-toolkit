#!/usr/bin/env bash
# This register emits no AI risk score, and neither computes one internally.
#
# Every AI-governance product on the market produces a number — an AI risk score, a model risk
# rating, a posture grade. The failure is the same one `no-vendor-score.sh` exists for: a
# generated number reads as an assessment, nobody can reproduce it, and it disagrees with
# `risk-register`, which actually owns scoring and does it under L×I against a declared
# appetite. Findings cross one way and are scored once, there.
#
# The specific arithmetic this catches is the tempting one: exposure classes counted and
# multiplied or averaged against a criticality rank. Three lines, a plausible number, and
# indistinguishable on a page from something somebody thought about.
#
#   BEHAVIOURAL — no KEY in an emitted payload is named like a score. Keys only, deliberately:
#   a deployment whose declared purpose is "churn scoring" is a fact about the business, and
#   banning the word in values would mean banning the truth.
#
#   STATIC — no shipped .py multiplies, divides or averages anything touching a criticality, a
#   rank or an exposure count, and none emits a score-shaped key. This is the half that catches
#   the rename: a score called `attentionIndex` escapes the behavioural check completely,
#   because the escape is a rename rather than a calculation.
#
# Anti-vacuity: EXPECTED_CHECKS is asserted; the payload is proved substantial before it is
# inspected; the scan reports its file count. Mutation-tested both ways.
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

A="$skill/scripts/ai_register.py"
S="$work/s.air"
echo "no-ai-score: $($PY -V 2>&1)"

"$PY" "$A" init "$S" --org "Probe Ltd" >/dev/null 2>&1
"$PY" "$A" add-system "$S" --name "Contoso Assist" --provider "Contoso" \
   --version "2026.4" --retrieval-augmented >/dev/null 2>&1
"$PY" "$A" add-system "$S" --name "Churn model" --provider "In-house" --version "3.1" \
   --predictive --hosting self-hosted >/dev/null 2>&1
"$PY" "$A" deploy "$S" --system S-001 --purpose "screening job applicants" \
   --owner "HR Director" --autonomy decides --data-class "applicant personal data" \
   --supports "CRM" --consequential >/dev/null 2>&1
# Named to prove the point about values: "churn scoring" is what this deployment IS.
"$PY" "$A" deploy "$S" --system S-002 --purpose "churn scoring" \
   --owner "Head of Sales" --autonomy recommends >/dev/null 2>&1
cat > "$work/ctx.json" <<'JSON'
{"contractVersion": "CAC-AP-1",
 "crownJewels": [{"system": "CRM", "criticality": "high"}]}
JSON
"$PY" "$A" classify "$S" --deployment D-001 --context "$work/ctx.json" \
   --confirm high --by "R. Calder" >/dev/null 2>&1

n=$("$PY" -c 'import json,sys;print(len(json.load(open(sys.argv[1]))["deployments"]))' \
    "$S" 2>/dev/null || echo 0)
if [ "$n" -ge 2 ]; then
  ok "the probe register produced $n deployments to inspect"
else
  bad "the probe register produced something to inspect" \
      "only $n deployments — every check below would pass over an empty file"
fi

# --- behavioural --------------------------------------------------------------
out=$("$PY" "$here/_aiscore.py" --json "$S" 2>"$work/b.err")
rc=$?
if [ "$rc" -eq 0 ]; then
  ok "no key the engine emits is named like a score, rating, grade or posture ($out)"
elif [ "$rc" -eq 2 ]; then
  bad "the payload is substantial enough to inspect" "$(cat "$work/b.err")"
else
  bad "no key the engine emits is named like a score" "$(cat "$work/b.err")"
fi

# And the value side stays free: a deployment can be for churn scoring without the guard
# objecting, because what a business does is not this tool's to rename.
if grep -q '"purpose": "churn scoring"' "$S"; then
  ok "...while a deployment whose purpose IS churn scoring records unchanged"
else
  bad "a deployment purposed 'churn scoring' records unchanged" \
      "the value was altered or refused — the guard is banning the truth, not the number"
fi

# --- static -------------------------------------------------------------------
scanned=$("$PY" "$here/_aiscore.py" --static "$skill" 2>"$work/s.err")
rc=$?
if [ "$rc" -eq 0 ]; then
  ok "no shipped .py multiplies or averages a criticality against an exposure count"
else
  bad "no shipped .py computes a score internally" "$(cat "$work/s.err")"
fi
# GP-1.7 — the scan asserts WHICH files it read, not merely that it read some. "Not zero"
# passed for months while `_common.py` was excluded: three files of five, and every registered
# mutant planted into `scripts/`, so the exclusion was never exercised. `want` is recomputed
# here from the filesystem rather than taken from the helper, so narrowing the helper's glob or
# growing its exclusion list fails instead of quietly shrinking a number nobody reads.
count=${scanned#scanned }
want=$(ls "$skill"/scripts/*.py "$skill"/renderers/*.py 2>/dev/null | grep -vc '/cac_graphics\.py$')
if [ "${count:-0}" -eq "${want:-0}" ] && [ "${want:-0}" -ge 1 ] 2>/dev/null; then
  ok "and the scan read all $count shipped file(s) — every script and renderer but the brand file"
else
  bad "the static scan covers every shipped .py" \
      "it read ${count:-0} of ${want:-0} — a file this guard is supposed to watch is unread"
fi

# --- the guard's own teeth ----------------------------------------------------
mkdir -p "$work/mutant/scripts"
cp "$A" "$work/mutant/scripts/ai_register.py"
cat >> "$work/mutant/scripts/ai_register.py" <<'PYEOF'


def posture_index(store, rec):
    """The three lines this guard exists to catch."""
    classes = len(rec.get("exposure") or {})
    return {"postureScore": criticality_rank(store, criticality_of(rec)) * classes}
PYEOF
if "$PY" "$here/_aiscore.py" --static "$work/mutant" >/dev/null 2>&1; then
  bad "the static half fails on a planted rank-times-count score" \
      "it passed a file computing criticality_rank() * class count"
else
  ok "the static half fails on a planted rank-times-count score"
fi

echo
if [ "$checks" -ne "$EXPECTED_CHECKS" ]; then
  printf 'no-ai-score: ran %s checks, expected %s\n' "$checks" "$EXPECTED_CHECKS"; exit 1; fi
if [ "$fails" -ne 0 ]; then
  printf 'no-ai-score: %s of %s checks FAILED\n' "$fails" "$checks"; exit 1; fi
printf 'no-ai-score: all %s checks passed\n' "$checks"
