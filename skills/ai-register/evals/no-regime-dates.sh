#!/usr/bin/env bash
# Regulatory dates live in data, never in prose — and no obligation ships unattributable.
#
# Two failures, one guard.
#
# The first is rot. A refusal message that says a regime "applies from" some year is a
# statement of law, and it is a statement nobody will re-read. Regulations are amended,
# transition periods move, and a stale date inside a refusal is a wrong statement of law
# delivered at the exact moment somebody is trying to do the right thing. Dates belong in
# `references/regimes.json`, behind an `asOf`, where a reader can see how old they are.
#
# The second is attribution. An obligation is the only thing this skill would say about what a
# REGULATOR requires of the reader; everything else it says is about their own register. One
# that cannot cite the article it comes from, or name the function that owns it, does not ship.
#
# The static half is deliberately narrow, and the narrowing is the point: every script here is
# full of four-digit years in test fixtures and example dates, and banning those would ban the
# test data. What is banned is a year in a sentence that is ALSO about a regulation.
#
# Mutation-tested both ways: a planted "applies from <year>" goes red, and so does an
# obligation with its source removed.
set -u

PY="${PY:-$(command -v python3)}"
here="$(cd "$(dirname "$0")" && pwd)"
skill="$(cd "$here/.." && pwd)"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

EXPECTED_CHECKS=10
checks=0
fails=0
ok()  { checks=$((checks + 1)); printf '  ok    %s\n' "$1"; }
bad() { checks=$((checks + 1)); fails=$((fails + 1)); printf '  FAIL  %s\n         %s\n' "$1" "$2"; }

A="$skill/scripts/ai_register.py"
J="$skill/references/regimes.json"
echo "no-regime-dates: $($PY -V 2>&1)"

# --- static -------------------------------------------------------------------
scanned=$("$PY" "$here/_regimescan.py" --static "$skill" 2>"$work/s.err")
rc=$?
if [ "$rc" -eq 0 ]; then
  ok "no shipped .py puts a year inside a sentence about a regulation"
else
  bad "no regulatory date appears in prose" "$(cat "$work/s.err")"
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

# The narrowing, proved rather than described: ordinary dates are untouched.
if grep -q '2026-' "$A"; then
  ok "...while ordinary dates in fixtures and examples are left alone"
else
  bad "the scan permits ordinary dates" \
      "there are no plain dates left in the file, so this proves nothing about the narrowing"
fi

# --- the dataset --------------------------------------------------------------
out=$("$PY" "$here/_regimescan.py" --data "$J" 2>"$work/d.err")
rc=$?
if [ "$rc" -eq 0 ]; then
  ok "every shipped obligation carries a source and an owning function ($out)"
else
  bad "every obligation is attributable and owned" "$(cat "$work/d.err")"
fi
if "$PY" -c '
import json, sys
d = json.load(open(sys.argv[1], encoding="utf-8"))
sys.exit(0 if d.get("regimes") == [] and str(d.get("asOf") or "").strip() else 1)' "$J"; then
  ok "the dataset ships EMPTY and still carries an asOf — the mechanism, not the content"
else
  bad "the dataset ships empty with an asOf" \
      "either regime content appeared without a verification pass, or the asOf went missing"
fi

# --- the loader's refusals ----------------------------------------------------
if "$PY" -c '
import importlib.util, sys
spec = importlib.util.spec_from_file_location("ar", sys.argv[1])
ar = importlib.util.module_from_spec(spec); spec.loader.exec_module(ar)
pool = []
cases = [
    ({"id": "x", "aiRole": "deployer"}, "not an overlay"),
    ({"id": "x", "flag": "f"}, "usually a deployer"),
    ({"id": "x", "flag": "f", "aiRole": "deployer",
      "obligations": [{"id": "o", "owningFunction": "Legal"}]}, "checked claim"),
    ({"id": "x", "flag": "f", "aiRole": "deployer",
      "obligations": [{"id": "o", "source": "Article 1"}]}, "owned by nobody"),
]
for regime, needle in cases:
    try:
        ar.register_regime(regime, into=pool)
    except ar.Refusal as exc:
        if needle not in str(exc):
            print("refused, but not for the stated reason: %s" % exc, file=sys.stderr)
            sys.exit(1)
        continue
    print("accepted %r" % regime, file=sys.stderr); sys.exit(1)
if pool:
    print("a refusal still registered something", file=sys.stderr); sys.exit(1)
' "$A" 2>"$work/r.err"; then
  ok "the loader refuses a regime with no flag, no role, no source or no owning function"
else
  bad "the loader refuses what it cannot attribute" "$(cat "$work/r.err")"
fi

# --- the vocabulary, probed against phrasings it must and must not catch ------
#
# An audit found the first version chasing VERBS, and verbs leak: it matched `applies from` and
# missed `apply from` — one letter of subject-verb agreement — plus `take effect on` and
# `begin`. All three are what a well-meaning author actually writes. The list leads with nouns
# now, and the ten phrasings are registered in the probe so the leak cannot reopen.
out=$("$PY" "$here/_regimescan.py" --vocab-probe 2>"$work/v.err")
rc=$?
if [ "$rc" -eq 0 ]; then
  ok "the vocabulary catches every registered phrasing, and none of the negatives ($out)"
else
  bad "the vocabulary catches what it claims to" "$(cat "$work/v.err")"
fi

# --- the guard's own teeth ----------------------------------------------------
mkdir -p "$work/mutant/scripts"
cp "$A" "$work/mutant/scripts/ai_register.py"
cat >> "$work/mutant/scripts/ai_register.py" <<'PYEOF'


HELPFUL = "This regulation applies from 2027 for deployers of high-risk systems."
PYEOF
if "$PY" "$here/_regimescan.py" --static "$work/mutant" >/dev/null 2>&1; then
  bad "the static half fails on a planted regulatory date" \
      "it passed a string reading 'This regulation applies from <year>'"
else
  ok "the static half fails on a planted regulatory date"
fi

# And on one the ORIGINAL vocabulary let through. This mutant exists because the first version
# of the guard would have passed it: no named regime, no `regulation`, and a verb in the plural.
mkdir -p "$work/mutant2/scripts"
cp "$A" "$work/mutant2/scripts/ai_register.py"
cat >> "$work/mutant2/scripts/ai_register.py" <<'PYEOF'


HELPFUL = "Deployer obligations begin 2 December 2027 for high-risk systems."
PYEOF
if "$PY" "$here/_regimescan.py" --static "$work/mutant2" >/dev/null 2>&1; then
  bad "the static half fails on a phrasing the first vocabulary missed" \
      "it passed 'Deployer obligations begin <date>' — the leak the audit found is open again"
else
  ok "...and on 'obligations begin <date>', which the first vocabulary let through"
fi

"$PY" -c '
import json, sys
d = json.load(open(sys.argv[1], encoding="utf-8"))
d["regimes"] = [{"id": "example", "flag": "exampleScope", "aiRole": "deployer",
                 "obligations": [{"id": "o1", "requirement": "do the thing",
                                  "owningFunction": "Legal"}]}]
json.dump(d, open(sys.argv[2], "w", encoding="utf-8"), indent=2)
' "$J" "$work/mutant.json"
if "$PY" "$here/_regimescan.py" --data "$work/mutant.json" >/dev/null 2>&1; then
  bad "the dataset half fails on an obligation with no source" \
      "it passed an obligation that cannot say where it came from"
else
  ok "and the dataset half fails on an obligation with no source"
fi

echo
if [ "$checks" -ne "$EXPECTED_CHECKS" ]; then
  printf 'no-regime-dates: ran %s checks, expected %s\n' "$checks" "$EXPECTED_CHECKS"; exit 1; fi
if [ "$fails" -ne 0 ]; then
  printf 'no-regime-dates: %s of %s checks FAILED\n' "$fails" "$checks"; exit 1; fi
printf 'no-regime-dates: all %s checks passed\n' "$checks"
