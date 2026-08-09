#!/usr/bin/env bash
# A policy record is never removed — proved, not asserted.
#
# The audit question is not "what is your policy on this" but "what was in force on the date
# of the incident". A register that can only answer the first one answers the wrong question,
# and it answers it with total confidence, which is worse than not answering.
#
# So supersession is the only way a document leaves force, and there is no delete command.
# That absence is the guard: an absence cannot be regression-tested by using it, only by
# proving that nothing has quietly added it back. The pressure to add one is ordinary and
# constant — somebody records a policy twice, or fat-fingers a title, and the obvious fix is
# a `remove` subcommand.
#
# Two halves, because either alone is escapable:
#
#   BEHAVIOURAL — a full lifecycle driven through the real CLI, with the record count
#   asserted after EVERY mutation. It never decreases, and the superseded document is still
#   in the store, still in the export, and still on the rendered page afterwards.
#
#   STATIC — no subcommand is named for deletion, and no shipped .py shortens the policies
#   list: no `del`, no `.remove`/`.pop`/`.clear` on it, no rebinding it to a filtered copy.
#   Catches the code path that exists but is not yet wired to a command, which the
#   behavioural half cannot reach.
#
# `unmap` is the deliberate near-miss and it is why the static half reads the TARGET rather
# than the method name. Narrowing what a document is aimed at removes a mapping, not a
# record, and a guard that could not tell those apart would have to ban one of them wrongly.
#
# Anti-vacuity: EXPECTED_CHECKS is asserted; the lifecycle is proved to have actually
# superseded something before the survival checks run; the static scan reports how many files
# it read and the count is recomputed here from the filesystem.
#
# Mutation-tested below and registered in guard-proofs/no-deletion.json.
set -u

PY="${PY:-$(command -v python3)}"
here="$(cd "$(dirname "$0")" && pwd)"
skill="$(cd "$here/.." && pwd)"
work="$(mktemp -d)"
. "$here/../../../tools/eval-probe.sh"   # `probe` — a crashed check is not a clean one (BL-121)
trap 'rm -rf "$work"' EXIT

EXPECTED_CHECKS=10
checks=0
fails=0
ok()  { checks=$((checks + 1)); printf '  ok    %s\n' "$1"; }
bad() { checks=$((checks + 1)); fails=$((fails + 1)); printf '  FAIL  %s\n         %s\n' "$1" "$2"; }

A="$skill/scripts/policy_register.py"
S="$work/s.pol"
echo "no-deletion: $($PY -V 2>&1)"

count_records() { "$PY" -c '
import json, sys
print(len(json.load(open(sys.argv[1], encoding="utf-8"))["policies"]))
' "$1" 2>/dev/null || echo -1; }

# --- behavioural: the count after every single mutation --------------------------
"$PY" "$A" init "$S" --org "Probe Ltd" >/dev/null 2>&1
seen=$(count_records "$S")
low=$seen
trail="$seen"
run_step() {
  "$PY" "$A" "$@" >/dev/null 2>&1
  n=$(count_records "$S")
  trail="$trail,$n"
  if [ "$n" -lt "$low" ] 2>/dev/null; then low=$n; fi
  if [ "$n" -lt "$seen" ] 2>/dev/null; then shrank="$shrank $1"; fi
  seen=$n
}
shrank=""
run_step add "$S" --title "Crypto Standard" --owner "IT" --version 1.0 --map SC-1 --map AC-1
run_step approve "$S" --id P-001 --by "The Board" --on 2025-03-01
run_step review "$S" --id P-001 --on 2026-01-05 --next 2027-01-05 --why "Annual review, no change."
run_step revise "$S" --id P-001 --version 2.0 --why "Rewritten for the new KMS."
run_step approve "$S" --id P-001 --by "The Board" --on 2026-02-01
run_step unmap "$S" --id P-001 --requirement AC-1 --why "Mapped in error."
run_step add "$S" --title "Crypto Standard" --owner "IT" --version 3.0 --map SC-1
run_step approve "$S" --id P-002 --by "The Board" --on 2026-06-01
run_step supersede "$S" --id P-001 --on 2026-06-01 --why "Replaced by the 3.0 issue." --by-policy P-002

if [ -z "$shrank" ] && [ "$seen" -eq 2 ]; then
  ok "the record count never decreased across nine mutations ($trail)"
else
  bad "the record count never decreases across a full lifecycle" \
      "shrank at:${shrank:- (none)}; trail $trail, ended at $seen"
fi

# The lifecycle is proved to have DONE the thing before anything is asserted about survival.
# Without this, every check below would pass on a register where supersede silently failed.
res=$(probe "$S" <<'PY'
import json, sys
store = json.load(open(sys.argv[1], encoding="utf-8"))
by_id = {p["id"]: p for p in store["policies"]}
problems = []
if by_id.get("P-001", {}).get("state") != "superseded":
    problems.append("P-001 should be superseded, reads %r" % by_id.get("P-001", {}).get("state"))
if by_id.get("P-001", {}).get("supersededBy") != "P-002":
    problems.append("P-001 should name P-002 as its replacement")
if by_id.get("P-002", {}).get("supersedes") != "P-001":
    problems.append("P-002 should record what it replaced")
events = [h["event"] for h in store["history"]]
for want in ("add", "approve", "review", "revise", "unmap", "supersede"):
    if want not in events:
        problems.append("the lifecycle never ran %r" % want)
print("; ".join(problems))
PY
)
if [ -z "$res" ]; then
  ok "and the lifecycle really did supersede a document, so the checks below mean something"
else
  bad "the lifecycle actually exercised supersession" "$res"
fi

"$PY" "$A" analyze "$S" --today 2026-07-01 --out "$work/a.json" >/dev/null 2>&1
"$PY" "$A" export "$S" --today 2026-07-01 --format csv --out "$work/e.csv" >/dev/null 2>&1
(cd "$skill/renderers" && "$PY" render_requirements.py --in "$work/a.json" \
   --out "$work/req.html" --offline) >/dev/null 2>&1

res=$(probe "$work/a.json" <<'PY'
import json, sys
data = json.load(open(sys.argv[1], encoding="utf-8"))
ids = [p["id"] for p in data["policies"]]
problems = []
if "P-001" not in ids:
    problems.append("the superseded record is gone from the analysis: %s" % ids)
rows = {r["id"]: r for r in data["requirements"]}
mapped = [p["id"] for p in rows["SC-1"]["policies"]]
if "P-001" not in mapped:
    problems.append("the superseded record no longer appears against SC-1: %s" % mapped)
print("; ".join(problems))
PY
)
if [ -z "$res" ]; then
  ok "the superseded document is still in the analysis and still against its requirement"
else
  bad "the superseded document survives into the analysis" "$res"
fi

if grep -q '^P-001,' "$work/e.csv"; then
  ok "and still in the CSV export an auditor is handed"
else
  bad "the superseded document is in the CSV export" \
      "P-001 is absent from $(wc -l <"$work/e.csv" | tr -d ' ') line(s)"
fi

if grep -q 'P-001' "$work/req.html" && grep -q 'superseded' "$work/req.html"; then
  ok "and still on the rendered page, marked as superseded"
else
  bad "the superseded document is on the rendered page" "P-001 or its state is absent"
fi

# --- static: the CLI surface ---------------------------------------------------------
res=$(probe "$skill" <<'PY'
import importlib.util, pathlib, re, sys
root = pathlib.Path(sys.argv[1])
DELETEY = re.compile(r"delete|remove|destroy|purge|drop|expunge|erase|forget", re.I)
spec = importlib.util.spec_from_file_location("pr", str(root / "scripts" / "policy_register.py"))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
problems = ["the CLI exposes %r" % c for c in sorted(mod.COMMANDS) if DELETEY.search(c)]
if len(mod.COMMANDS) < 8:
    problems.append("COMMANDS holds only %d entries; this check may be reading the wrong "
                    "surface, in which case its silence means nothing" % len(mod.COMMANDS))
print("; ".join(problems))
PY
)
if [ -z "$res" ]; then
  ok "no subcommand in COMMANDS is named for removing a record"
else
  bad "no subcommand is named for removing a record" "$res"
fi

# --- static: the code paths -----------------------------------------------------------
#
# WHAT COUNTS AS "THE RECORDS LIST" had to be narrowed after the first run, and the
# narrowing is the interesting part. Matching any `["policies"]` flagged three innocent
# things: a requirement row's own list of the documents aimed at it, a local accumulator in
# `analyze`, and the renderer's `Context.policies` read-model field. None of those is the
# store, and a guard that cried wolf on all three would be deleted rather than fixed.
#
# So the target has to be the STORE's list — `store["policies"]` and its aliases — reached
# through a name that plausibly holds a loaded register. That is narrower than "anything
# called policies" and wider than one hard-coded spelling. The behavioural half above is what
# covers a removal performed somewhere this pattern cannot see, which is why neither half is
# asked to be exhaustive on its own.
res=$(probe "$skill" <<'PY'
import ast, pathlib, re, sys
root = pathlib.Path(sys.argv[1])
DELETEY = re.compile(r"delete|remove|destroy|purge|drop|expunge|erase|forget", re.I)
STOREISH = re.compile(r"^(store|register|reg|db|s)$", re.I)
problems = []


def is_store_records(node):
    """`store["policies"]` — the list load_store and save_store round-trip."""
    if not isinstance(node, ast.Subscript):
        return False
    sl = node.slice
    if not (isinstance(sl, ast.Constant) and sl.value == "policies"):
        return False
    base = node.value
    if isinstance(base, ast.Name):
        return bool(STOREISH.match(base.id))
    if isinstance(base, ast.Attribute):
        return bool(STOREISH.match(base.attr))
    if isinstance(base, ast.Call):          # load_store(path)["policies"]
        fn = base.func
        name = fn.id if isinstance(fn, ast.Name) else getattr(fn, "attr", "")
        return "store" in name.lower()
    return False


files = sorted(p for p in list(root.glob("scripts/*.py")) + list(root.glob("renderers/*.py"))
               if p.name != "cac_graphics.py")
scanned = 0
for path in files:
    scanned += 1
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Delete):
            for t in node.targets:
                if is_store_records(t) or (isinstance(t, ast.Subscript)
                                           and is_store_records(t.value)):
                    problems.append("%s:%d deletes from the store's records list"
                                    % (path.name, node.lineno))
        elif (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
              and node.func.attr in ("remove", "pop", "clear")
              and is_store_records(node.func.value)):
            problems.append("%s:%d calls .%s() on the store's records list"
                            % (path.name, node.lineno, node.func.attr))
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if is_store_records(t):
                    problems.append("%s:%d rebinds the store's records list — a filtered "
                                    "copy is a deletion with better manners"
                                    % (path.name, node.lineno))
        elif (isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
              and DELETEY.search(node.name)):
            problems.append("%s:%d def %s — named for removal"
                            % (path.name, node.lineno, node.name))
print("scanned %d" % scanned)
for p in problems:
    print(p)
PY
)
count=$(printf '%s\n' "$res" | head -1); count=${count#scanned }
found=$(printf '%s\n' "$res" | tail -n +2 | tr '\n' ' ')
if [ -z "${found// /}" ]; then
  ok "no shipped .py shortens the store's records list"
else
  bad "no shipped .py shortens the store's records list" "$found"
fi
want=$(ls "$skill"/scripts/*.py "$skill"/renderers/*.py 2>/dev/null | grep -vc '/cac_graphics\.py$')
if [ "${count:-0}" -eq "${want:-0}" ] && [ "${want:-0}" -ge 1 ] 2>/dev/null; then
  ok "and the scan read all $count shipped file(s)"
else
  bad "the static scan covers every shipped .py" "it read ${count:-0} of ${want:-0}"
fi

# --- the guard's own teeth -----------------------------------------------------------
mkdir -p "$work/mutant/scripts" "$work/mutant/renderers"
cp "$A" "$work/mutant/scripts/policy_register.py"
cp "$skill"/renderers/*.py "$work/mutant/renderers/" 2>/dev/null
cat >> "$work/mutant/scripts/policy_register.py" <<'PYEOF'


def _tidy(store, pid):
    store["policies"] = [p for p in store["policies"] if p.get("id") != pid]


COMMANDS["forget"] = _tidy
PYEOF
res=$(probe "$work/mutant" <<'PY'
import ast, importlib.util, pathlib, re, sys
root = pathlib.Path(sys.argv[1])
DELETEY = re.compile(r"delete|remove|destroy|purge|drop|expunge|erase|forget", re.I)
problems = []
spec = importlib.util.spec_from_file_location("prm", str(root / "scripts" / "policy_register.py"))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
problems += ["command %s" % c for c in mod.COMMANDS if DELETEY.search(c)]
for path in sorted(root.glob("scripts/*.py")):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if (isinstance(t, ast.Subscript) and isinstance(t.slice, ast.Constant)
                        and t.slice.value == "policies"):
                    problems.append("%s:%d rebinds the records list" % (path.name, node.lineno))
print("; ".join(problems))
PY
)
if [ -n "$res" ]; then
  ok "the static half fails on a planted filter-and-rebind under an innocent name"
else
  bad "the static half fails on a planted deletion" \
      "it passed a module rebinding store['policies'] and registering a 'forget' command"
fi

# The behavioural half, against a store a deletion has already been applied to. This is the
# half that catches the removal done outside this module — an import path, a migration, a
# helper in a renderer — where no static pattern in this skill would ever see it.
"$PY" -c '
import json, sys
store = json.load(open(sys.argv[1], encoding="utf-8"))
store["policies"] = [p for p in store["policies"] if p.get("state") != "superseded"]
json.dump(store, open(sys.argv[2], "w", encoding="utf-8"), indent=2)
' "$S" "$work/mutant.pol"
"$PY" "$A" analyze "$work/mutant.pol" --today 2026-07-01 --out "$work/m.json" >/dev/null 2>&1
res=$(probe "$work/m.json" <<'PY'
import json, sys
data = json.load(open(sys.argv[1], encoding="utf-8"))
ids = [p["id"] for p in data["policies"]]
rows = {r["id"]: r for r in data["requirements"]}
problems = []
if "P-001" not in ids:
    problems.append("the superseded record is gone from the analysis")
if "P-001" not in [p["id"] for p in rows["SC-1"]["policies"]]:
    problems.append("the superseded record no longer appears against SC-1")
print("; ".join(problems))
PY
)
if [ -n "$res" ]; then
  ok "and the behavioural half fails on a store the record was removed from"
else
  bad "the behavioural half fails on a store the record was removed from" \
      "it passed an analysis with the superseded document dropped"
fi

echo
if [ "$checks" -ne "$EXPECTED_CHECKS" ]; then
  printf 'no-deletion: ran %s checks, expected %s\n' "$checks" "$EXPECTED_CHECKS"; exit 1; fi
if [ "$fails" -ne 0 ]; then
  printf 'no-deletion: %s of %s checks FAILED\n' "$fails" "$checks"; exit 1; fi
printf 'no-deletion: all %s checks passed\n' "$checks"
