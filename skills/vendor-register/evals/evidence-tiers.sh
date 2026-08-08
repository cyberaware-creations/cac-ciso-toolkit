#!/usr/bin/env bash
# What a tier means, and what does not change it — from the CLI, against real stores.
#
# Three rules, and each is the kind that gets "helpfully" relaxed by somebody who finds it
# inconvenient at the wrong moment:
#
#   1. T1 refuses without a scope AND a period. An artifact whose limits are not written down
#      gets read as though it had none.
#   2. A bridge letter is T3 and does NOT extend an expired T1. A management assertion is not
#      an audited artifact, and this is the specific relaxation the reference doc names.
#   3. Grace has boundaries, and past them evidence covers nothing.
#
# Each is checked in BOTH directions where a direction exists: the refusal fires, and the
# legitimate case still goes through. A guard that refuses everything is not a guard.
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

V="$skill/scripts/vendor_register.py"
S="$work/e.vnd"
echo "evidence-tiers: $($PY -V 2>&1)"

"$PY" "$V" init "$S" --org "Tier Ltd" >/dev/null 2>&1
"$PY" "$V" add-vendor "$S" --name "Contoso Cloud" >/dev/null 2>&1
"$PY" "$V" add-arrangement "$S" --vendor V-001 --services hosting --owner CTO >/dev/null 2>&1
before=$(md5 -q "$S" 2>/dev/null || md5sum "$S" | cut -d' ' -f1)

# --- 1-4. a T1 has to say what it covers and when -----------------------------
if "$PY" "$V" ingest "$S" --arrangement VA-001 --kind soc2-type2 --tier T1 \
     --source "auditor PDF" >/dev/null 2>"$work/1.err"; then
  bad "a T1 with no scope and no period is refused" "it was accepted"
else
  if grep -qF "cannot expire" "$work/1.err"; then
    ok "a T1 with no scope and no period is refused, and the refusal says why both matter"
  else
    ok "a T1 with no scope and no period is refused"
  fi
fi
if "$PY" "$V" ingest "$S" --arrangement VA-001 --kind soc2-type2 --tier T1 \
     --source "auditor PDF" --scope "the hosting platform" >/dev/null 2>&1; then
  bad "a T1 with a scope but no period is refused" "it was accepted"
else
  ok "a T1 with a scope but no period is refused"
fi
if "$PY" "$V" ingest "$S" --arrangement VA-001 --kind trust-page --tier T4 \
     --source "their site" --url "https://example.test/trust" >/dev/null 2>&1; then
  bad "a URL source with no retrieval date is refused" "it was accepted"
else
  ok "a URL source with no retrieval date is refused"
fi
after=$(md5 -q "$S" 2>/dev/null || md5sum "$S" | cut -d' ' -f1)
if [ "$before" = "$after" ]; then
  ok "and none of those refusals touched the store"
else
  bad "a refused ingest leaves the store byte-identical" "the file changed"
fi

# --- 5-6. the legitimate cases still go through -------------------------------
if "$PY" "$V" ingest "$S" --arrangement VA-001 --kind soc2-type2 --tier T1 \
     --source "auditor PDF" --scope "the hosting platform, excluding payments" \
     --period-start 2025-01-01 --period-end 2025-12-31 >/dev/null 2>&1; then
  ok "a T1 that states its scope and period is accepted"
else
  bad "a complete T1 is accepted" "it was refused — the guard rejects everything"
fi
if "$PY" "$V" ingest "$S" --arrangement VA-001 --kind questionnaire --tier T3 \
     --source "their completed CAIQ" >/dev/null 2>&1; then
  ok "a T3 needs neither, because it can satisfy nothing to begin with"
else
  bad "a T3 is accepted without scope or period" "it was refused"
fi

# --- 7-9. grace has boundaries ------------------------------------------------
status() {  # status <today>
  "$PY" -c '
import importlib.util, json, sys
spec = importlib.util.spec_from_file_location("vr", sys.argv[1])
vr = importlib.util.module_from_spec(spec); spec.loader.exec_module(vr)
store = json.load(open(sys.argv[2], encoding="utf-8"))
ev = store["arrangements"][0]["evidence"][0]
print(vr.evidence_status(ev, sys.argv[3], 365))' "$V" "$S" "$1"
}
[ "$(status 2025-06-01)" = "current" ] \
  && ok "inside its period, a T1 is current" \
  || bad "inside its period a T1 is current" "got $(status 2025-06-01)"
[ "$(status 2026-11-30)" = "in-grace" ] \
  && ok "eleven months past the period end it is in grace" \
  || bad "eleven months past the period end it is in grace" "got $(status 2026-11-30)"
[ "$(status 2027-02-01)" = "expired" ] \
  && ok "thirteen months past it, it has expired" \
  || bad "thirteen months past it, it has expired" "got $(status 2027-02-01)"

# --- 10-11. THE relaxation this suite exists to prevent -----------------------
#
# A bridge letter is a management assertion covering the gap since a report's period closed.
# Treating one as extending that report's currency is the single most tempting shortcut here,
# and it converts an audited artifact into an unaudited one without anybody noticing.
"$PY" "$V" ingest "$S" --arrangement VA-001 --kind bridge-letter --tier T3 \
   --source "management letter covering Jan-Jun 2026" >/dev/null 2>&1
if [ "$(status 2027-02-01)" = "expired" ]; then
  ok "ingesting a bridge letter leaves the expired T1 EXPIRED"
else
  bad "a bridge letter does not extend a T1's currency" \
      "the T1 became $(status 2027-02-01) — a management assertion is not an audited artifact"
fi
if "$PY" -c '
import importlib.util, json, sys
spec = importlib.util.spec_from_file_location("vr", sys.argv[1])
vr = importlib.util.module_from_spec(spec); spec.loader.exec_module(vr)
store = json.load(open(sys.argv[2], encoding="utf-8"))
kinds = {e["kind"]: e["tier"] for e in store["arrangements"][0]["evidence"]}
sys.exit(0 if kinds.get("bridge-letter") == "T3"
         and "bridge-letter" not in [k for k, t in kinds.items() if t in vr.SATISFYING_TIERS]
         else 1)' "$V" "$S"; then
  ok "...because it is stored as T3, which is not a tier that can satisfy anything"
else
  bad "a bridge letter is stored as T3" "it was recorded at a satisfying tier"
fi

echo
if [ "$checks" -ne "$EXPECTED_CHECKS" ]; then
  printf 'evidence-tiers: ran %s checks, expected %s\n' "$checks" "$EXPECTED_CHECKS"; exit 1; fi
if [ "$fails" -ne 0 ]; then
  printf 'evidence-tiers: %s of %s checks FAILED\n' "$fails" "$checks"; exit 1; fi
printf 'evidence-tiers: all %s checks passed\n' "$checks"
