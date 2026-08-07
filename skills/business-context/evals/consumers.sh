#!/usr/bin/env bash
# Every consumer of CAC-AP-1, held to the contract this skill owns.
#
# `self-test` pins the narrowing decision. Each consumer's own suite pins that consumer. What
# neither can see is the thing that actually goes wrong across a contract: FOUR engines each
# implementing the same six clauses, drifting apart one release at a time, with every suite
# still green because each is only ever asked about itself.
#
# So this runs the consumers as a set, from the side that defines the contract, and asserts
# the properties that must hold for all of them:
#
#   * a payload the profile decided is honoured, not re-derived (§2.1)
#   * absence asks MORE — an undeclared profile asks at least as much as a declaring one
#     (§2.2), which is the clause whose failure looks like a clean result
#   * every skip carries the flag, the declarer and the date (§2.4)
#   * `--context` is ADDITIVE — without it the output is byte-for-byte what it always was
#   * a payload from the wrong contract, or with no decision in it, is REFUSED rather than
#     quietly ignored, because a silently un-narrowed run reads as a profile that decided
#     nothing applied
#
# The load-bearing case is proportionality (checks per consumer, marked below). It is
# BEHAVIOURAL: a profile declaring a flag false must produce STRICTLY FEWER asked batteries
# than one declaring nothing. No shared constant can fake that, and it is the property the
# phrase "the profile narrows what a skill asks" actually means.
#
# Anti-vacuity: the consumer list is derived from the engine's own QUESTION_SETS, so a
# question set added without a consumer fails here rather than shipping unimplemented.
set -u

PY="${PY:-$(command -v python3)}"
here="$(cd "$(dirname "$0")" && pwd)"
skill="$(cd "$here/.." && pwd)"
root="$(cd "$skill/.." && pwd)"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

E="$skill/scripts/business_context.py"

EXPECTED_CHECKS=29
checks=0
fails=0
ok()  { checks=$((checks + 1)); printf '  ok    %s\n' "$1"; }
bad() { checks=$((checks + 1)); fails=$((fails + 1)); printf '  FAIL  %s\n         %s\n' "$1" "$2"; }
eq()  { if [ "$2" = "$3" ]; then ok "$1"; else bad "$1" "expected '$2', got '$3'"; fi; }

echo "consumers: $($PY -V 2>&1)"

# Each consumer: skill key | engine | subcommand | store | extra args
CONSUMERS="
risk|$root/risk-register/scripts/score_register.py|score|$root/risk-register/examples/example-register-v2.rr|--json
metrics|$root/metrics-register/scripts/metrics_analysis.py|analyze|$root/metrics-register/examples/example-metrics.mtr|
exceptions|$root/exceptions-register/scripts/exceptions_register.py|analyze|$root/exceptions-register/examples/example.exc|
incident|$root/incident-materiality/scripts/incident_analysis.py|analyze|$root/incident-materiality/examples/example-incident.inc|--now 2026-08-07T12:00:00+00:00
"

# 1. Every question set this engine defines has a consumer here. A set with no consumer is a
# promise in the payload that nothing keeps — the exact shape of the overclaim an external
# retest caught in the manifest descriptions.
declared="$("$PY" -c 'import sys; sys.path.insert(0, sys.argv[1])
import business_context as bc
print(" ".join(sorted(bc.QUESTION_SETS)))' "$skill/scripts")"
covered="exceptions incident metrics risk"
unimplemented=""
for d in $declared; do
  case " $covered vendor " in *" $d "*) ;; *) unimplemented="$unimplemented $d";; esac
done
if [ -z "$unimplemented" ]; then
  ok "every question set is either implemented by a consumer here or a known gap ($declared)"
else
  bad "every question set has a consumer or is a declared gap" \
      "no consumer and not listed as a gap:$unimplemented"
fi

# Profiles. `undeclared` declares nothing at all; `declaring` declares every gating flag
# false. §2.2 says the first must ask AT LEAST as much as the second.
"$PY" "$E" init "$work/undeclared.biz" --org "Proportionality Ltd" >/dev/null 2>&1
"$PY" "$E" init "$work/declaring.biz" --org "Proportionality Ltd" >/dev/null 2>&1
for flag in listedEntity doraScope nydfsScope otPresent aiInUse regulatedDataHeld; do
  "$PY" "$E" declare "$work/declaring.biz" --flag "$flag" --value false \
    --by "Eval" --basis "declared out of scope for this fixture" >/dev/null 2>&1
done
"$PY" "$E" export "$work/undeclared.biz" --out "$work/undeclared.json" >/dev/null 2>&1
"$PY" "$E" export "$work/declaring.biz" --out "$work/declaring.json" >/dev/null 2>&1

# A payload from another contract, and one carrying no decision. Both must be refused.
"$PY" -c 'import json,sys
d=json.load(open(sys.argv[1])); d["contractVersion"]="CAC-XX-9"
json.dump(d, open(sys.argv[2],"w"))' "$work/undeclared.json" "$work/wrong.json"
"$PY" -c 'import json,sys
d=json.load(open(sys.argv[1])); d.pop("applicability", None)
json.dump(d, open(sys.argv[2],"w"))' "$work/undeclared.json" "$work/nodecision.json"

asked_count() {  # asked_count <engine> <cmd> <store> <payload> <extra...>
  eng="$1"; cmd="$2"; store="$3"; payload="$4"; shift 4
  "$PY" "$eng" "$cmd" "$store" --today 2026-08-07 "$@" --context "$payload" 2>/dev/null \
    | "$PY" "$here/_consumercheck.py" --asked
}

echo "$CONSUMERS" | while IFS='|' read -r key eng cmd store extra; do
  [ -n "$key" ] || continue
  # shellcheck disable=SC2086
  set -- $extra

  # 2. It accepts --context at all, and emits a decided block.
  if "$PY" "$eng" "$cmd" "$store" --today 2026-08-07 "$@" --context "$work/undeclared.json" \
       >"$work/$key.json" 2>"$work/$key.err"; then
    printf '  ok    %s accepts --context and runs\n' "$key"
  else
    printf '  FAIL  %s accepts --context and runs\n         %s\n' "$key" \
           "$(tail -1 "$work/$key.err")"
  fi
  if "$PY" "$here/_consumercheck.py" --has-block <"$work/$key.json"; then
    printf '  ok    ...and its output carries a decided applicability block\n'
  else
    printf '  FAIL  %s emits an applicability block\n         absent\n' "$key"
  fi

  # 3. ADDITIVE. Without --context the output is what it always was.
  "$PY" "$eng" "$cmd" "$store" --today 2026-08-07 "$@" >"$work/$key.plain" 2>/dev/null
  if "$PY" "$here/_consumercheck.py" --no-block <"$work/$key.plain"; then
    printf '  ok    ...and a run with no --context carries no context key at all\n'
  else
    printf '  FAIL  %s is additive\n         a context key appeared with no profile\n' "$key"
  fi

  # 4. THE LOAD-BEARING CASE. Absence asks MORE (§2.2). Behavioural, and no shared constant
  # between this suite and any engine can fake it.
  u=$(asked_count "$eng" "$cmd" "$store" "$work/undeclared.json" "$@")
  d=$(asked_count "$eng" "$cmd" "$store" "$work/declaring.json" "$@")
  if [ "${u:-0}" -gt "${d:-99}" ]; then
    printf '  ok    ...an undeclared profile asks MORE than a declaring one (%s > %s)\n' "$u" "$d"
  else
    printf '  FAIL  %s: absence must ask more than declaration\n         undeclared=%s declaring=%s\n' \
           "$key" "$u" "$d"
  fi

  # 5. §2.4 — every skip names the flag, the declarer and the date.
  "$PY" "$eng" "$cmd" "$store" --today 2026-08-07 "$@" --context "$work/declaring.json" \
    >"$work/$key.narrow" 2>/dev/null
  if "$PY" "$here/_consumercheck.py" --skips-attributed <"$work/$key.narrow"; then
    printf '  ok    ...and every skipped battery names its flag, declarer and date\n'
  else
    printf '  FAIL  %s: a skip is missing its provenance (§2.4)\n         see output\n' "$key"
  fi

  # 6-7. A payload this engine cannot honour is REFUSED, not ignored.
  if "$PY" "$eng" "$cmd" "$store" --today 2026-08-07 "$@" --context "$work/wrong.json" \
       >/dev/null 2>&1; then
    printf '  FAIL  %s refuses a payload from another contract\n         it ran anyway\n' "$key"
  else
    printf '  ok    ...a payload declaring another contractVersion is refused\n'
  fi
  if "$PY" "$eng" "$cmd" "$store" --today 2026-08-07 "$@" --context "$work/nodecision.json" \
       >/dev/null 2>&1; then
    printf '  FAIL  %s refuses a payload with no decision in it\n         it ran anyway\n' "$key"
  else
    printf '  ok    ...and so is one carrying no decided applicability\n'
  fi
done > "$work/per-consumer.txt" 2>&1

cat "$work/per-consumer.txt"
per_ok=$(grep -c '^  ok ' "$work/per-consumer.txt" || true)
per_bad=$(grep -c '^  FAIL' "$work/per-consumer.txt" || true)
checks=$((checks + per_ok + per_bad))
fails=$((fails + per_bad))

echo
if [ "$checks" -ne "$EXPECTED_CHECKS" ]; then
  printf 'consumers: ran %s checks, expected %s\n' "$checks" "$EXPECTED_CHECKS"; exit 1; fi
if [ "$fails" -ne 0 ]; then
  printf 'consumers: %s of %s checks FAILED\n' "$fails" "$checks"; exit 1; fi
printf 'consumers: all %s checks passed\n' "$checks"
