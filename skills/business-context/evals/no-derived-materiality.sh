#!/usr/bin/env bash
# The one guardrail this skill cannot be trusted to keep by intention alone.
#
# Holding a revenue figure creates an obvious temptation: divide an impact by it and call the
# result a materiality threshold. It must not exist.
#
# `incident-materiality` refuses to emit a verdict precisely because a generated number is
# discoverable alongside the determination it disagreed with — "the tool scored it 3.2, below
# our threshold" is not a defensible position, and a plaintiff does not need it to be. This
# skill supplies the denominator so a human can weigh it. Supplying the denominator must not
# smuggle the verdict back in through the back door.
#
# TWO checks, because either alone is weak:
#
#   1. BEHAVIOURAL — no key in any output names a derived materiality figure. Catches a
#      threshold that arrives through the payload, whatever the code looks like.
#   2. STATIC — no shipped .py divides by, or takes a percentage of, the revenue field.
#      Catches the arithmetic before it ever reaches an output, including on a code path no
#      fixture happens to exercise.
#
# A guard never seen to fail is not known to work: evals/_derivedcheck.py is run against a
# deliberately poisoned copy at the end, and this suite fails if the poison goes undetected.
set -u

PY="${PY:-$(command -v python3)}"
here="$(cd "$(dirname "$0")" && pwd)"
skill="$(cd "$here/.." && pwd)"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

EXPECTED_CHECKS=7
checks=0
fails=0
ok()  { checks=$((checks + 1)); printf '  ok    %s\n' "$1"; }
bad() { checks=$((checks + 1)); fails=$((fails + 1)); printf '  FAIL  %s\n         %s\n' "$1" "$2"; }

echo "no-derived-materiality: $($PY -V 2>&1)"

B="$skill/scripts/business_context.py"
S="$work/t.biz"
"$PY" "$B" init "$S" --org 'Guard Co' >/dev/null
"$PY" "$B" declare "$S" --flag listedEntity --value false --by 'D. G.' \
  --basis 'Privately held' >/dev/null
"$PY" "$B" set-revenue "$S" --exact 412000000 --currency USD --fiscal-year FY26 \
  --by CFO --basis 'FY26 audited accounts' >/dev/null
"$PY" "$B" set-fact "$S" --crown-jewel CRM --enables 'renewals' \
  --at-stake 'client data' --by 'D. G.' --basis 'FY26' >/dev/null

# 1-3. Behavioural: every output this skill can emit, scanned for a derived figure.
for cmd in "export $S" "show $S --json" "applies $S --skill incident --json"; do
  out="$("$PY" "$B" $cmd 2>/dev/null)"
  hit="$("$PY" "$here/_derivedcheck.py" --stdin <<<"$out")"
  label="$(echo "$cmd" | cut -d' ' -f1)"
  if [ "$hit" = "clean" ]; then
    ok "no derived materiality figure in \`$label\` output"
  else
    bad "no derived materiality figure in \`$label\` output" "$hit"
  fi
done

# 4. Static: the shipped source itself.
static="$("$PY" "$here/_derivedcheck.py" --source "$skill")"
if [ "$static" = "clean" ]; then
  ok "no shipped .py divides by or percentages the revenue base"
else
  bad "no shipped .py divides by or percentages the revenue base" "$static"
fi

# 5-6. THE GUARD, SEEN TO FAIL. A copy of the skill is poisoned with the exact line this
# check exists to stop, and with a poisoned output. Both must be detected; if either slips
# through, this suite has been reporting a clean bill on a check that cannot see anything.
poison="$work/poisoned"
mkdir -p "$poison/scripts"
cp "$B" "$poison/scripts/business_context.py"
cat >> "$poison/scripts/business_context.py" <<'PYPOISON'


def materiality_threshold(impact, store):
    """Deliberate poison for the eval. Never ship this."""
    revenue = store["context"]["revenue"]["exact"]
    return impact / revenue * 100
PYPOISON
if [ "$("$PY" "$here/_derivedcheck.py" --source "$poison")" != "clean" ]; then
  ok "the static check catches a division by the revenue base when one is introduced"
else
  bad "the static check catches a division by the revenue base" \
      "the poisoned copy passed — this guard cannot see the thing it exists for"
fi
if [ "$("$PY" "$here/_derivedcheck.py" --stdin <<<'{"materialityThreshold": 0.5}')" != "clean" ]; then
  ok "and the behavioural check catches a derived key in an output"
else
  bad "the behavioural check catches a derived key in an output" "poisoned payload passed"
fi

# 7. The poison above names the revenue base directly in the division, which is the easy
# case. This one is the shape the code actually takes — the figure is pulled into a local
# first, and the division then mentions nothing on the revenue list at all. It went
# undetected when it was tried against a real renderer, which is why `_derivedcheck` now
# follows the binding; without this case that would be a fix with no test behind it.
poison2="$work/poisoned-local"
mkdir -p "$poison2/scripts"
cat > "$poison2/scripts/renderer.py" <<'PYPOISON'
def line(revenue, impact):
    """Deliberate poison for the eval. Never ship this."""
    exact = revenue.get("exact")
    return "%.2f of revenue" % (impact / exact * 100)
PYPOISON
if [ "$("$PY" "$here/_derivedcheck.py" --source "$poison2")" != "clean" ]; then
  ok "...and catches it through a local the revenue base was assigned into first"
else
  bad "the static check follows the revenue base through a local binding" \
      "the poisoned copy passed — the division names nothing on the revenue list, which is exactly how real code would be written"
fi

echo
if [ "$checks" -ne "$EXPECTED_CHECKS" ]; then
  printf 'no-derived-materiality: ran %s checks, expected %s\n' "$checks" "$EXPECTED_CHECKS"
  exit 1
fi
if [ "$fails" -ne 0 ]; then
  printf 'no-derived-materiality: %s of %s checks FAILED\n' "$fails" "$checks"
  exit 1
fi
printf 'no-derived-materiality: all %s checks passed\n' "$checks"
