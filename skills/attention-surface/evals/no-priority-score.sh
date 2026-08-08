#!/usr/bin/env bash
# This surface orders without scoring, and that is the whole difference between it and a queue.
#
# Thirty triggers arrive here, each already carrying a severity its producer computed and can
# defend. The tempting next step is one number that orders them all — a weighted blend of
# severity, age and criticality. Three lines, sorts beautifully, and it is **this skill's own
# opinion about what matters**: a thirty-first voice in a room that already has thirty, and the
# only one with no register behind it.
#
# What is allowed instead: a tuple of three DECLARED facts, compared lexicographically —
# severity as the producer stated it, age since `since`, subject reference for stability. A
# tuple comparison is not arithmetic. Nothing is weighted, nothing is combined, and why any item
# sits where it does can be read off in words.
#
# Two halves, because either alone is escapable:
#
#   BEHAVIOURAL — no key in an emitted review is named like a priority. Keys only: `severity`
#   is the producer's own value and must travel through untouched.
#
#   STATIC — nothing multiplies or averages a severity against an age or a count, and no
#   priority-shaped key is emitted. This is the half that catches the score computed inside and
#   rendered under an innocent name.
#
# Registered under CAC-GP-1: `tools/prove-guards.sh` proves both halves fail when the defect is
# present, on every run.
set -u

PY="${PY:-$(command -v python3)}"
here="$(cd "$(dirname "$0")" && pwd)"
skill="$(cd "$here/.." && pwd)"
repo="$(cd "$skill/../.." && pwd)"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

EXPECTED_CHECKS=8
checks=0
fails=0
ok()  { checks=$((checks + 1)); printf '  ok    %s\n' "$1"; }
bad() { checks=$((checks + 1)); fails=$((fails + 1)); printf '  FAIL  %s\n         %s\n' "$1" "$2"; }

A="$skill/scripts/attention_surface.py"
S="$work/p.att"
echo "no-priority-score: $($PY -V 2>&1)"

# A real review over real producers. An empty one has no keys to be wrong and would pass every
# check below while proving nothing.
"$PY" "$A" init "$S" --org "Probe Ltd" >/dev/null 2>&1
for pair in "risk-register:$repo/skills/risk-register/examples/example-register-v2.rr" \
            "vendor-register:$repo/skills/vendor-register/examples/example-vendors.vnd" \
            "ai-register:$repo/skills/ai-register/examples/example-ai.air" \
            "metrics-register:$repo/skills/metrics-register/examples/example-metrics.mtr"; do
  "$PY" "$A" add-source "$S" --skill "${pair%%:*}" --store "${pair#*:}" >/dev/null 2>&1
done
"$PY" "$A" review "$S" --today 2026-08-07 --json > "$work/r.json" 2>/dev/null

n=$("$PY" -c 'import json,sys;print(json.load(open(sys.argv[1]))["counts"]["items"])' \
    "$work/r.json" 2>/dev/null || echo 0)
if [ "$n" -ge 10 ]; then
  ok "the probe review carries $n item(s) across four producers to inspect"
else
  bad "the probe review produced something to inspect" \
      "only $n item(s) — every check below would pass over an empty file"
fi

# --- behavioural --------------------------------------------------------------
out=$("$PY" "$here/_priorityscan.py" --json "$work/r.json" 2>"$work/b.err")
rc=$?
if [ "$rc" -eq 0 ]; then
  ok "no key in the review is named like a priority, a score or a rank ($out)"
elif [ "$rc" -eq 2 ]; then
  bad "the review is substantial enough to inspect" "$(cat "$work/b.err")"
else
  bad "no key is named like a priority" "$(cat "$work/b.err")"
fi

# The producer's OWN severity must survive. A guard that stripped it would be protecting the
# rule by destroying the input, which is the failure mode of a list that bans its subject.
if "$PY" -c '
import json, sys
d = json.load(open(sys.argv[1], encoding="utf-8"))
sev = {i["severity"] for c in d["clusters"] for i in c["items"]}
if not sev or not sev <= {"critical", "high", "medium"}:
    print("severities seen: %s" % sorted(sev), file=sys.stderr); sys.exit(1)
' "$work/r.json" 2>"$work/sev.err"; then
  ok "...while each producer's own declared severity travels through untouched"
else
  bad "the producer's severity survives" "$(cat "$work/sev.err")"
fi

# --- static -------------------------------------------------------------------
scanned=$("$PY" "$here/_priorityscan.py" --static "$skill" 2>"$work/s.err")
rc=$?
if [ "$rc" -eq 0 ]; then
  ok "no shipped .py multiplies or averages a severity against an age or a count"
else
  bad "no shipped .py computes a priority internally" "$(cat "$work/s.err")"
fi
count=${scanned#scanned }
if [ "${count:-0}" -ge 1 ] 2>/dev/null; then
  ok "and the static scan actually read $count shipped file(s), not zero"
else
  bad "the static scan read at least one file" "it read none, so it proved nothing"
fi

# --- ordering is explainable, not computed ------------------------------------
if "$PY" -c '
import importlib.util, sys
spec = importlib.util.spec_from_file_location("att", sys.argv[1])
att = importlib.util.module_from_spec(spec); spec.loader.exec_module(att)
item = {"severity": "high", "since": "2026-01-01", "subjectRef": "R-001"}
key = att.order_key(item, "2026-08-01")
if not isinstance(key, tuple) or len(key) != 3:
    print("order_key is %r, not a three-part tuple" % (key,), file=sys.stderr); sys.exit(1)
# Each part must be traceable to one declared fact, and none may be a blend.
if key[0] != att.severity_rank("high"):
    print("first key is not the declared severity position", file=sys.stderr); sys.exit(1)
if key[2] != "R-001":
    print("third key is not the subject reference", file=sys.stderr); sys.exit(1)
' "$A" 2>"$work/ord.err"; then
  ok "ordering is a three-part tuple of declared facts, not a blended number"
else
  bad "ordering is a tuple of declared facts" "$(cat "$work/ord.err")"
fi

# --- the guard's own teeth ----------------------------------------------------
mkdir -p "$work/mutant/scripts"
cp "$A" "$work/mutant/scripts/attention_surface.py"
cat >> "$work/mutant/scripts/attention_surface.py" <<'PYEOF'


def attention_priority(item, today):
    """The three lines this guard exists to catch."""
    age = days_between(item["since"], today)
    return {"priorityScore": (3 - severity_rank(item["severity"])) * age}
PYEOF
if "$PY" "$here/_priorityscan.py" --static "$work/mutant" >/dev/null 2>&1; then
  bad "the static half fails on a planted severity-times-age score" \
      "it passed a file computing (3 - severity_rank) * age"
else
  ok "the static half fails on a planted severity-times-age score"
fi

"$PY" -c '
import json, sys
d = json.load(open(sys.argv[1], encoding="utf-8"))
d["counts"]["priorityScore"] = 7
json.dump(d, open(sys.argv[2], "w", encoding="utf-8"), indent=2)
' "$work/r.json" "$work/mutant.json"
if "$PY" "$here/_priorityscan.py" --json "$work/mutant.json" >/dev/null 2>&1; then
  bad "the behavioural half fails on a planted priority key" \
      "it passed a review carrying counts.priorityScore"
else
  ok "and the behavioural half fails on a planted priority key"
fi

echo
if [ "$checks" -ne "$EXPECTED_CHECKS" ]; then
  printf 'no-priority-score: ran %s checks, expected %s\n' "$checks" "$EXPECTED_CHECKS"; exit 1; fi
if [ "$fails" -ne 0 ]; then
  printf 'no-priority-score: %s of %s checks FAILED\n' "$fails" "$checks"; exit 1; fi
printf 'no-priority-score: all %s checks passed\n' "$checks"
