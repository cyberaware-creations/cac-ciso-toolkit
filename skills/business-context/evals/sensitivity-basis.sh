#!/usr/bin/env bash
# A declared sensitivity carries a basis, and the basis reaches the page.
#
# Sensitivity is FREE TEXT (BL-216 Q-1, decided 2026-08-09). There is no scale, deliberately:
# the organisation's own classification is the answer, and imposing `low/moderate/high` here
# would make this skill the author of a data-classification policy it has no business writing.
#
# Free text with no basis is an adjective. `--sensitivity 'highly sensitive'` tells a reader
# nothing they can check, and it will sit on a crown-jewel record an assessor is entitled to
# follow. The basis — who determined it, and from what — is the entire difference between a
# determination and a word somebody typed. So the engine refuses one without the other.
#
# TWO HALVES, and the second is the one that would otherwise rot:
#
#   1. REFUSED — the engine refuses a sensitivity with no basis, and accepts one with a basis.
#      Both directions, through the real API, because a guard that only proves the refusal
#      cannot tell "refuses correctly" from "refuses everything".
#
#   2. VISIBLE — the basis reaches the rendered page. A required field nobody can see decays
#      into ceremony: the rule is enforced on write, and if the read surface drops it then the
#      person the basis exists for never encounters it. `render_context.py` showed neither
#      criticality nor sensitivity until v0.68.2, so this is not a hypothetical risk about a
#      renderer — it is the state this skill was actually in.
#
# Either half alone passes a broken state. An engine that refuses correctly while the renderer
# drops the basis satisfies the letter of the rule and none of its purpose; a renderer that
# prints a basis the engine never required prints whatever happened to be typed.
set -u

PY="${PY:-$(command -v python3)}"
here="$(cd "$(dirname "$0")" && pwd)"
skill="$(cd "$here/.." && pwd)"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

EXPECTED_CHECKS=8
checks=0
fails=0
ok()  { checks=$((checks + 1)); printf '  ok    %s\n' "$1"; }
bad() { checks=$((checks + 1)); fails=$((fails + 1)); printf '  FAIL  %s\n         %s\n' "$1" "$2"; }

E="$skill/scripts/business_context.py"
R="$skill/renderers/render_context.py"
echo "sensitivity-basis: $($PY -V 2>&1)"

# --- half 1: REFUSED, in both directions --------------------------------------
"$PY" - "$E" >"$work/refuse.out" 2>"$work/refuse.err" <<'PYEOF'
import importlib.util, sys
spec = importlib.util.spec_from_file_location("bc", sys.argv[1])
bc = importlib.util.module_from_spec(spec); spec.loader.exec_module(bc)

s = bc.new_store("Fixture Ltd", "Tester")
args = ("HR file", "payroll", "a reportable breach")


def outcome(**kw):
    try:
        return ("ok", bc.add_crown_jewel(bc.new_store("F", "T"), *args, **kw))
    except bc.Refusal as exc:
        return ("refused", str(exc))


kind, detail = outcome(sensitivity="Special category, UK GDPR Art. 9")
print("NOBASIS %s" % kind)
if kind == "refused" and "adjective" not in detail:
    print("NOBASIS-REASON the refusal does not say why a basis is load-bearing: %r" % detail[:120])

kind, _ = outcome(sensitivity_basis="DPO review 2026-07-01")
print("BASISONLY %s" % kind)

kind, rec = outcome(by="DPO", sensitivity="Special category, UK GDPR Art. 9",
                    sensitivity_basis="DPO record-of-processing review 2026-07-01")
print("WITHBASIS %s" % kind)
if kind == "ok":
    sens = rec.get("sensitivity")
    # The value and the basis are separate fields on a declared() record. A single blob
    # would satisfy "the basis is stored" and be unreadable by anything downstream.
    if isinstance(sens, dict) and sens.get("value") and sens.get("basis"):
        print("SHAPE ok")
    else:
        print("SHAPE the sensitivity is not a declared record with its own basis: %r" % (sens,))

# Absence is absence: a crown jewel that declares no sensitivity carries no key. CAC-AP-1
# §2.2 — a missing field means NOT DECLARED, and an empty one invites a reader to treat it
# as "assessed, nothing found".
plain = bc.add_crown_jewel(bc.new_store("F", "T"), *args)
print("ABSENT %s" % ("ok" if "sensitivity" not in plain else "an empty key was written"))
PYEOF

if [ ! -s "$work/refuse.out" ]; then
  bad "the refusal half ran at all" "$(tail -3 "$work/refuse.err")"
else
  for want in "NOBASIS refused:a sensitivity with no basis is refused" \
              "BASISONLY refused:a basis with nothing determined is refused" \
              "WITHBASIS ok:...and a sensitivity WITH a basis is accepted" \
              "SHAPE ok:the value and its basis are separate fields, not one blob" \
              "ABSENT ok:a crown jewel declaring no sensitivity carries no key"; do
    line="${want%%:*}"; label="${want#*:}"
    if grep -qx "$line" "$work/refuse.out"; then
      ok "$label"
    else
      bad "$label" "$(grep "^${line%% *}" "$work/refuse.out" || echo 'the check printed nothing')"
    fi
  done
  if grep -q '^NOBASIS-REASON' "$work/refuse.out"; then
    bad "the refusal says why a basis is load-bearing" \
        "$(grep '^NOBASIS-REASON' "$work/refuse.out")"
  else
    ok "the refusal says why a basis is load-bearing"
  fi
fi

# --- half 2: VISIBLE, on the rendered page ------------------------------------
"$PY" - "$E" "$work/f.biz" <<'PYEOF'
import importlib.util, sys
spec = importlib.util.spec_from_file_location("bc", sys.argv[1])
bc = importlib.util.module_from_spec(spec); spec.loader.exec_module(bc)
s = bc.new_store("Fixture Ltd", "Tester")
bc.add_crown_jewel(s, "HR file", "payroll", "a reportable breach", by="DPO",
                   criticality="high",
                   criticality_basis="FY26 business impact analysis",
                   sensitivity="Special category, UK GDPR Art. 9",
                   sensitivity_basis="DPO record-of-processing review 2026-07-01")
bc.save(sys.argv[2], s)
PYEOF

if (cd "$skill/renderers" && "$PY" "$R" --in "$work/f.biz" --out "$work/f.html") \
     >/dev/null 2>"$work/render.err" && [ -s "$work/f.html" ]; then
  page=$(cat "$work/f.html")
  missing=""
  # The value AND the basis. Printing the value alone is the failure this half exists for:
  # it looks complete and drops the only part that makes free text checkable.
  case "$page" in
    *"Special category, UK GDPR Art. 9"*) ;;
    *) missing="the sensitivity value" ;;
  esac
  case "$page" in
    *"DPO record-of-processing review 2026-07-01"*) ;;
    *) missing="${missing:+$missing and }its basis" ;;
  esac
  if [ -z "$missing" ]; then
    ok "the sensitivity and its basis both reach the rendered page"
  else
    bad "the sensitivity and its basis both reach the rendered page" \
        "$missing is not on the page"
  fi
  # Criticality is on the same page for the same reason, and was equally invisible before
  # v0.68.2. It is checked here rather than in a suite of its own because the failure is one
  # failure: this renderer dropping what the record carries.
  case "$page" in
    *"Criticality: high"*) ok "and the declared criticality reaches it too" ;;
    *) bad "and the declared criticality reaches it too" \
           "the crown jewel's criticality is not on the page" ;;
  esac
else
  bad "the sensitivity and its basis both reach the rendered page" \
      "$(tail -3 "$work/render.err")"
  bad "and the declared criticality reaches it too" "the render did not produce a page"
fi

if [ "$checks" -ne "$EXPECTED_CHECKS" ]; then
  printf 'sensitivity-basis: ran %d checks, expected %d — a case stopped executing\n' \
         "$checks" "$EXPECTED_CHECKS"; exit 1; fi
if [ "$fails" -ne 0 ]; then
  printf 'sensitivity-basis: %d of %d checks FAILED\n' "$fails" "$checks"; exit 1; fi
printf 'sensitivity-basis: all %d checks passed\n' "$checks"
