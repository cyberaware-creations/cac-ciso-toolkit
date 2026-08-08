#!/usr/bin/env bash
# The three ways a projection can lie by omission, each checked in both directions.
#
# This skill computes nothing. Its whole failure surface is what it fails to show, and there are
# exactly three shapes of that:
#
#   1. **An unmapped trigger disappears.** A new producer emits something `clusters.json` has no
#      home for, and it silently does not render. The list looks complete and is not.
#   2. **An unread source looks clean.** A producer's store is missing or its analyze fails, and
#      the surface shows a short list with no explanation. Quiet and unread must not look alike.
#   3. **A malformed item is dropped.** A producer stops honouring CAC-EL-1's six keys, and the
#      item vanishing hides exactly the change worth knowing about.
#
# Each is checked positively — the thing appears — and negatively — the group is ABSENT when it
# has nothing in it, so it reads as a finding rather than as furniture.
set -u

PY="${PY:-$(command -v python3)}"
here="$(cd "$(dirname "$0")" && pwd)"
skill="$(cd "$here/.." && pwd)"
repo="$(cd "$skill/../.." && pwd)"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

EXPECTED_CHECKS=12
checks=0
fails=0
ok()  { checks=$((checks + 1)); printf '  ok    %s\n' "$1"; }
bad() { checks=$((checks + 1)); fails=$((fails + 1)); printf '  FAIL  %s\n         %s\n' "$1" "$2"; }

A="$skill/scripts/attention_surface.py"
C="$skill/references/clusters.json"
echo "clusters: $($PY -V 2>&1)"

# --- 1-2. every trigger a producer can emit has a home ------------------------
out=$("$PY" "$here/_triggerscan.py" "$repo" "$C" 2>"$work/t.err")
rc=$?
if [ "$rc" -eq 0 ]; then
  ok "every trigger the shipped producers can emit is mapped to a cluster ($out)"
elif [ "$rc" -eq 2 ]; then
  bad "the trigger scan found triggers to check" "$(cat "$work/t.err")"
else
  bad "every emitted trigger is mapped" "$(cat "$work/t.err")"
fi
# The scan's own teeth: remove a mapping and it must go red. Read from the producers rather
# than a hand-kept list precisely so this cannot rot, so the rot has to be provable.
"$PY" -c '
import json, sys
d = json.load(open(sys.argv[1], encoding="utf-8"))
for c in d["clusters"]:
    if "untraced" in (c.get("triggers") or []):
        c["triggers"].remove("untraced")
json.dump(d, open(sys.argv[2], "w", encoding="utf-8"), indent=2)
' "$C" "$work/gapped.json"
if "$PY" "$here/_triggerscan.py" "$repo" "$work/gapped.json" >/dev/null 2>&1; then
  bad "the scan fails when a mapping is removed" "it passed with `untraced` unmapped"
else
  ok "...and the scan goes red when one mapping is removed"
fi

# --- 3-5. the loader refuses a dataset that would mislead ---------------------
if "$PY" -c '
import importlib.util, json, os, sys
spec = importlib.util.spec_from_file_location("att", sys.argv[1])
att = importlib.util.module_from_spec(spec); spec.loader.exec_module(att)
work = sys.argv[2]
cases = [
    ({"clusters": []}, "broken dataset"),
    ({"clusters": [{"id": "a", "triggers": ["x"]}, {"id": "b", "triggers": ["x"]}]},
     "count it twice"),
]
for i, (doc, needle) in enumerate(cases):
    path = os.path.join(work, "c%d.json" % i)
    json.dump(doc, open(path, "w", encoding="utf-8"))
    try:
        att.load_clusters(path)
    except att.Refusal as exc:
        if needle not in str(exc):
            print("refused, but not for the stated reason: %s" % exc, file=sys.stderr)
            sys.exit(1)
        continue
    print("accepted %r" % doc, file=sys.stderr); sys.exit(1)
' "$A" "$work" 2>"$work/l.err"; then
  ok "an empty mapping and a duplicated trigger are both refused, with the reason"
else
  bad "the loader refuses a misleading dataset" "$(cat "$work/l.err")"
fi
if "$PY" -c '
import importlib.util, sys
spec = importlib.util.spec_from_file_location("att", sys.argv[1])
att = importlib.util.module_from_spec(spec); spec.loader.exec_module(att)
cl = att.load_clusters()
assert len(cl["clusters"]) >= 5, len(cl["clusters"])
assert len(cl["byTrigger"]) >= 25, len(cl["byTrigger"])
' "$A" 2>"$work/ship.err"; then
  ok "...while the shipped dataset loads, so the guard is not refusing everything"
else
  bad "the shipped dataset loads" "$(cat "$work/ship.err")"
fi
if "$PY" -c '
import json, sys
d = json.load(open(sys.argv[1], encoding="utf-8"))
missing = [c["id"] for c in d["clusters"] if not (c.get("meaning") or "").strip()]
if missing:
    print("clusters with no meaning: %s" % ", ".join(missing), file=sys.stderr); sys.exit(1)
' "$C" 2>"$work/m.err"; then
  ok "and every cluster says what it means, so a title never has to be guessed at"
else
  bad "every cluster carries a meaning" "$(cat "$work/m.err")"
fi

# --- 6-7. an unmapped trigger surfaces, and the group is absent otherwise -----
if "$PY" -c '
import importlib.util, sys
spec = importlib.util.spec_from_file_location("att", sys.argv[1])
att = importlib.util.module_from_spec(spec); spec.loader.exec_module(att)
cl = att.load_clusters()
def esc(t):
    return {"trigger": t, "subjectKind": "x", "subjectRef": "X-1", "severity": "high",
            "since": "2026-01-01", "evidence": "because", "producer": "risk-register"}
groups = att.group([esc("a-trigger-from-the-future")], cl, "2026-08-01")
ids = [g["id"] for g in groups]
if att.UNCLUSTERED not in ids:
    print("an unmapped trigger did NOT surface: %s" % ids, file=sys.stderr); sys.exit(1)
if not any(i["subjectRef"] == "X-1" for g in groups for i in g["items"]):
    print("it surfaced as a heading with no item", file=sys.stderr); sys.exit(1)
' "$A" 2>"$work/u.err"; then
  ok "an unmapped trigger surfaces in the unclustered group, carrying its item"
else
  bad "an unmapped trigger surfaces" "$(cat "$work/u.err")"
fi
if "$PY" -c '
import importlib.util, sys
spec = importlib.util.spec_from_file_location("att", sys.argv[1])
att = importlib.util.module_from_spec(spec); spec.loader.exec_module(att)
cl = att.load_clusters()
mapped = {"trigger": "untraced", "subjectKind": "x", "subjectRef": "X-1",
          "severity": "high", "since": "2026-01-01", "evidence": "b", "producer": "p"}
ids = [g["id"] for g in att.group([mapped], cl, "2026-08-01")]
if att.UNCLUSTERED in ids:
    print("the unclustered group appeared with nothing in it", file=sys.stderr); sys.exit(1)
' "$A" 2>"$work/e.err"; then
  ok "...and is ABSENT when nothing is unmapped — a finding, not furniture"
else
  bad "the unclustered group is absent when empty" "$(cat "$work/e.err")"
fi

# --- 8-10. absence is visible -------------------------------------------------
S="$work/a.att"
"$PY" "$A" init "$S" --org "Probe Ltd" >/dev/null 2>&1
"$PY" "$A" add-source "$S" --skill risk-register \
   --store "$repo/skills/risk-register/examples/example-register-v2.rr" >/dev/null 2>&1
"$PY" "$A" add-source "$S" --skill vendor-register --store "$work/not-there.vnd" >/dev/null 2>&1
"$PY" "$A" review "$S" --today 2026-08-07 > "$work/txt.out" 2>&1
if grep -qF "NOT READ" "$work/txt.out"; then
  ok "a source whose store is missing is reported as NOT READ"
else
  bad "an unread source is reported" "the page shows a short list with no explanation"
fi
if grep -qF "different fact from a clean register" "$work/txt.out"; then
  ok "...and the page says in words why that is not the same as clean"
else
  bad "the unread reason is on the page" "the words are missing"
fi
# The unread block must come BEFORE anything that looks like a result. A reader who sees a
# short list has to be told it is short because nothing fired, not because nothing was read.
if "$PY" -c '
import sys
text = open(sys.argv[1], encoding="utf-8").read()
if "NOT READ" not in text:
    print("no NOT READ block", file=sys.stderr); sys.exit(1)
first_cluster = text.find("## ")
if first_cluster != -1 and text.find("NOT READ") > first_cluster:
    print("the unread block appears AFTER the first cluster", file=sys.stderr); sys.exit(1)
' "$work/txt.out" 2>"$work/o.err"; then
  ok "and it sits above the first cluster, before anything that reads as a result"
else
  bad "the unread block comes first" "$(cat "$work/o.err")"
fi

# --- 11-12. a malformed item is shown, not dropped ----------------------------
if "$PY" -c '
import importlib.util, sys
spec = importlib.util.spec_from_file_location("att", sys.argv[1])
att = importlib.util.module_from_spec(spec); spec.loader.exec_module(att)
if len(att.ESCALATION_KEYS) != 6:
    print("CAC-EL-1 is six keys; found %d" % len(att.ESCALATION_KEYS), file=sys.stderr)
    sys.exit(1)
' "$A" 2>"$work/k.err"; then
  ok "the CAC-EL-1 contract this surface reads is six keys"
else
  bad "the escalation contract is six keys" "$(cat "$work/k.err")"
fi
if grep -q "escalations" "$A" && grep -qF "malformed" "$A"; then
  ok "and an item missing one is carried as malformed rather than discarded"
else
  bad "malformed items are carried" "no malformed handling in the engine"
fi

echo
if [ "$checks" -ne "$EXPECTED_CHECKS" ]; then
  printf 'clusters: ran %s checks, expected %s\n' "$checks" "$EXPECTED_CHECKS"; exit 1; fi
if [ "$fails" -ne 0 ]; then
  printf 'clusters: %s of %s checks FAILED\n' "$fails" "$checks"; exit 1; fi
printf 'clusters: all %s checks passed\n' "$checks"
