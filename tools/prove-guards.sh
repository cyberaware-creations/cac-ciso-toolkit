#!/usr/bin/env bash
# CAC-GP-1 — every guard must FAIL when its defect is present. Proved on each run.
#
# The suite's guards each exist because a specific defect would otherwise look like a feature:
# no vendor score, no closed state on an attack class, no percent-of-revenue materiality, no
# vendor assertion closing a requirement. Each is one line away from being "helpfully" added,
# and each looks like an obvious gap to somebody who was not in the conversation where it was
# decided. **The guards are the memory.** This is what makes sure the memory still works.
#
# Most of those guards record, in prose, that they were mutation-tested. That sentence is true
# and the proof behind it is a paragraph: performed once, against code that has since moved,
# and re-run by nothing. A guard that stops detecting its own defect — because a function was
# renamed, a scan path narrowed, a regex loosened — goes on printing `ok` forever, and the
# printing is indistinguishable from working. This makes the mutation data instead of prose.
#
# The standard, implemented here:
#
#   GP-1.1  Every guard registers at least one mutation in evals/guard-proofs/<name>.json,
#           and a guard with two halves registers one for EACH half. Otherwise half the guard
#           is proven and half is assumed, which is worse than knowing neither is.
#   GP-1.2  An unregistered guard is a FAILURE, not a skip. A skip lets the standard erode the
#           way a globbed eval list does — silently, and looking green.
#   GP-1.3  Every proof runs on a fresh copy. A run that dies halfway must not be able to
#           leave a mutated working tree behind, looking fine and not being fine.
#   GP-1.4  Both directions, in that order: clean must PASS, then mutated must FAIL. Reporting
#           only the second is the common mistake — a permanently broken guard would "pass" a
#           test that only looks for failure.
#   GP-1.5  A stale mutation is a FAILURE. If `find` no longer matches, the code moved and the
#           proof did not follow it, which is precisely when a guard quietly stops guarding.
#   GP-1.6  Runs in CI, on the floor, listed individually.
#   GP-1.9  A mutation names the checks it defeats, and the mutated run must fail EXACTLY
#           those. "The guard exited non-zero" is not evidence that the registered half was
#           the half that caught it — a two-half guard whose halves both trip on one mutation
#           proves neither of them independently, and reports a clean pass/fail pair while
#           doing it. Naming the checks makes the blast radius data.
#
# Usage: tools/prove-guards.sh [guard-name ...]
set -u

PY="${PY:-$(command -v python3)}"
repo="$(cd "$(dirname "$0")/.." && pwd)"
only=("$@")

# Anti-vacuity, matching the house convention. A proof run that silently exercised nothing is
# the thing this file exists to prevent, so the counts are asserted rather than printed.
EXPECTED_GUARDS=40
EXPECTED_HALVES=75

# GP-1.11 — a RATCHET, not an equality. `EXPECTED_GUARDS` and `EXPECTED_HALVES` are exact
# because a guard appearing or vanishing is always worth a human look. This one is a floor:
# the number of checks demonstrated to fail may rise freely and may never fall.
#
# A floor rather than a target because the honest end state is not 356 of 356. Some checks are
# preconditions — a fixture was built, a scan read four files — and a mutation for those would
# only prove the fixture still works. Others are the guarded property itself and genuinely
# need one. Sorting the 273 into those two piles is real work and is filed separately; what
# this line does is stop the ratio sliding backwards while nobody is looking, which is exactly
# how it reached 14% without anyone deciding to.
EXPECTED_PROVED=101

guards_seen=0
halves_seen=0

# GP-1.11 — where each guard's PUBLISHED check labels are collected, harvested from the clean
# run the runner already performs. Nothing new is executed for this; what was missing was ever
# reading the clean output for anything but its exit status.
labels_dir="$(mktemp -d)"
trap 'rm -rf "$labels_dir"' EXIT
fails=0

pass_line() { printf '  ok    %s\n' "$1"; }
fail_line() { fails=$((fails + 1)); printf '  FAIL  %s\n         %s\n' "$1" "$2"; }

echo "prove-guards (CAC-GP-1): $($PY -V 2>&1)"
echo

# --- discover guards by convention (GP-1.2) -----------------------------------
#
# GP-1.8 — discovery reads tools/guard-registry.json, and the registry must account for EVERY
# skills/*/evals/*.sh on disk.
#
# It used to glob four filename patterns. Eight real guards escaped: seven copies of
# decisions-render.sh and ai-register/exposure.sh, none ever mutation-tested — and because the
# GP-1.7 registry check filtered through the same globs, it compared the doc against the blind
# spot and reported a clean bill (BL-101).
#
# No filename rule could have caught both: seven shared a name no convention anticipated and
# the eighth shared nothing with anything. A marker line inside each guard was the other
# candidate and was rejected, because a marker cannot detect its own absence — the failure
# here is an OMISSION, and only a list that must cover everything can fail on one.
#
# Hence the coverage assertion below. Classifying non-guards is not bookkeeping overhead; it
# is the mechanism. A new eval script in none of the three roles fails this run.
registry="$repo/tools/guard-registry.json"
if [ ! -f "$registry" ]; then
  echo "prove-guards: $registry is missing — discovery has no source of truth"
  exit 1
fi

coverage=$("$PY" - "$registry" "$repo" <<'PYEOF'
import glob, json, os, sys
reg_path, repo = sys.argv[1], sys.argv[2]
try:
    doc = json.load(open(reg_path, encoding="utf-8"))
    rows = doc["scripts"]
except (OSError, ValueError, KeyError) as exc:
    print("BAD registry unusable: %s" % exc); raise SystemExit(0)
ROLES = ("guard", "candidate", "not-a-guard")
listed, bad = {}, []
for i, r in enumerate(rows):
    p, role = r.get("path"), r.get("role")
    if not isinstance(p, str) or role not in ROLES:
        bad.append("scripts[%d]: needs `path` and a `role` of %s" % (i, "/".join(ROLES)))
        continue
    if p in listed:
        bad.append("%s: listed twice" % p)
    listed[p] = role
    if role == "guard" and not str(r.get("forbids") or "").strip():
        bad.append("%s: a guard must say what it `forbids`" % p)
    if role != "guard" and not str(r.get("reason") or "").strip():
        bad.append("%s: a %s must carry a `reason`" % (p, role))
    # `permanent` is a settled verdict that it can never be enrolled, so it is meaningful on a
    # candidate and nowhere else. An enrolled guard marked permanent, or a not-a-guard marked
    # permanent, is somebody misreading the field rather than using it.
    if "permanent" in r:
        if r["permanent"] is not True:
            bad.append("%s: `permanent` is a settled true/absent flag, got %r"
                       % (p, r["permanent"]))
        elif role != "candidate":
            bad.append("%s: only a candidate can be `permanent`, this is a %s" % (p, role))
on_disk = set(os.path.relpath(p, repo) for p in glob.glob(os.path.join(repo, "skills/*/evals/*.sh")))
missing = sorted(on_disk - set(listed))
phantom = sorted(set(listed) - on_disk)
for m in missing:
    bad.append("%s exists on disk and is in no role — classify it, or a guard can be born "
               "invisible again" % m)
for p in phantom:
    bad.append("%s is in the registry and not on disk" % p)
if bad:
    print("BAD " + " | ".join(bad)); raise SystemExit(0)
guards = sorted(p for p, r in listed.items() if r == "guard")
cands = [r for r in rows if r.get("role") == "candidate"]
# Two kinds, counted apart. A `candidate` used to mean "guard-shaped, not yet enrolled",
# and the summary line said so. One of them is now a settled verdict rather than a queue
# entry: `archetype-advisory.sh` cannot be mutation-tested because the defect it forbids
# is unexpressible through the signature of the function that would have to contain it.
# Printing it as "not yet enrolled" would be a small, permanent lie in the one line a
# reader trusts for scope, so the decision is data and the count is split.
perm = sum(1 for r in cands if r.get("permanent") is True)
print("OK %d %d %d" % (len(on_disk), len(cands) - perm, perm))
for g in guards:
    print(g)
PYEOF
)
if [ "${coverage%% *}" = "BAD" ]; then
  echo "prove-guards: guard-registry.json does not account for the tree"
  printf '  %s\n' "${coverage#BAD }"
  exit 1
fi

guards=()
scripts_seen=0
candidates_seen=0
permanent_seen=0
while IFS= read -r line; do
  case "$line" in
    OK\ *) scripts_seen="$(echo "$line" | cut -d' ' -f2)"
           candidates_seen="$(echo "$line" | cut -d' ' -f3)"
           permanent_seen="$(echo "$line" | cut -d' ' -f4)" ;;
    "")    ;;
    *)     guards+=("$repo/$line") ;;
  esac
done <<< "$coverage"

if [ "${#guards[@]}" -eq 0 ]; then
  echo "prove-guards: the registry declares no guards — this proved nothing"
  exit 1
fi

for guard in "${guards[@]}"; do
  name="$(basename "$guard" .sh)"
  skill="$(cd "$(dirname "$(dirname "$guard")")" && pwd)"
  rel="${guard#$repo/}"
  proof="$skill/evals/guard-proofs/$name.json"

  if [ ${#only[@]} -gt 0 ]; then
    printf '%s\n' "${only[@]}" | grep -qx "$name" || continue
  fi

  # GP-1.2 — no proof file is a failure, not a skip.
  if [ ! -f "$proof" ]; then
    fail_line "$name registers a mutation" \
              "no $proof — an unregistered guard is untested, and looks identical to a tested one"
    guards_seen=$((guards_seen + 1))
    continue
  fi
  guards_seen=$((guards_seen + 1))

  halves=$("$PY" -c '
import json, sys
proof = json.load(open(sys.argv[1], encoding="utf-8"))
print(len(proof.get("mutations") or []))' "$proof")
  if [ "${halves:-0}" -lt 1 ]; then
    fail_line "$name registers at least one mutation" "the proof file lists none"
    continue
  fi

  # GP-1.9 (first half) — the halves must be TELLABLE APART before any of them is run.
  #
  # GP-1.1 has always required that a mutation defeat its own half specifically. Nothing
  # enforced it, and two guards were violating it. `proposal-boundary`'s behavioural mutation
  # added "T3" to SATISFYING_TIERS, which is also an inlined tier list, so the static half
  # caught it too; `evidence-tiers`' scope-and-period mutation let an undated T1 into the store
  # at index 0, which the expiry half was reading positionally. Both reported the textbook
  # clean-pass/mutated-fail on both halves while proving one thing twice (BL-102).
  #
  # The rule is distinguishability, not disjointness. `outcome-framing`'s two mutations both
  # trip "the checker's own tests pass" — a meta-check belonging to neither half — and that is
  # legitimate. What is not legitimate is two halves with identical failure signatures.
  distinct=$("$PY" - "$proof" <<'PYEOF'
import json, sys
muts = json.load(open(sys.argv[1], encoding="utf-8"))["mutations"]
bad = []
sets = []
for i, m in enumerate(muts):
    d = m.get("defeats")
    half = m.get("half") or "unnamed"
    if not isinstance(d, list) or not d or not all(isinstance(x, str) and x.strip() for x in d):
        bad.append("[%s] has no `defeats` list — name the checks the mutated run must fail, "
                   "or a non-zero exit for any reason at all counts as proof" % half)
    sets.append((half, set(d if isinstance(d, list) else [])))
if not bad and len(sets) > 1:
    for i, (half, s) in enumerate(sets):
        others = set().union(*[o for j, (_, o) in enumerate(sets) if j != i])
        if not (s - others):
            bad.append("[%s] defeats nothing the other half/halves do not also defeat — the "
                       "two halves are indistinguishable, so one of them is unproved" % half)
print(" | ".join(bad))
PYEOF
)
  if [ -n "$distinct" ]; then
    fail_line "$name: each half is separately identifiable (GP-1.9)" "$distinct"
    continue
  fi

  i=0
  while [ "$i" -lt "$halves" ]; do
    half=$("$PY" -c '
import json, sys
m = json.load(open(sys.argv[1], encoding="utf-8"))["mutations"][int(sys.argv[2])]
print(m.get("half") or "unnamed")' "$proof" "$i")
    halves_seen=$((halves_seen + 1))
    label="$name [$half]"

    # GP-1.3 — a fresh copy per half. `.git` is excluded because copying it is 25MB of
    # nothing: a guard reads the working tree, never the history.
    work="$(mktemp -d)"
    ( cd "$repo" && tar -cf - --exclude .git --exclude .claude . ) | ( cd "$work" && tar -xf - )

    # GP-1.4 step 1 — clean must PASS. If it does not, either the guard is broken or the tree
    # is dirty, and nothing about the mutation result below would mean anything.
    if ! PY="$PY" bash "$work/$rel" >"$work/.clean.out" 2>&1; then
      fail_line "$label: the guard passes on a clean copy" \
                "$(tail -3 "$work/.clean.out" | tr '\n' ' ')"
      rm -rf "$work"
      i=$((i + 1))
      continue
    fi

    # GP-1.11 — harvest what the clean run PUBLISHED. Two reporting shapes, the same two
    # `labels()` below reads for the mutated run, so a check is named identically on the way in
    # and on the way out. Written once per guard; every half runs the same script.
    lkey="${rel//\//__}"
    if [ ! -f "$labels_dir/$lkey" ]; then
      "$PY" - "$work/.clean.out" > "$labels_dir/$lkey" <<'PYEOF'
import re, sys
OK = re.compile(r"^ *ok +(\S.*?) *$")
CHK = re.compile(r"^\S{1,6} +(\S.*?) +PASS\b.*$")
seen = []
for line in open(sys.argv[1], encoding="utf-8", errors="replace"):
    m = OK.match(line.rstrip("\n")) or CHK.match(line.rstrip("\n"))
    if m and m.group(1) not in seen:
        seen.append(m.group(1))
print("\n".join(seen))
PYEOF
    fi

    # GP-1.5 — apply, and a `find` that no longer matches is a failure.
    #
    # Two forms. The usual one edits a file: `find` must match exactly once, and a `find`
    # that has stopped matching means the code moved and the proof did not follow it.
    #
    # `"create": true` ADDS a file that is not in the tree, and exists for one property
    # that the editing form structurally cannot express: **a guard that surveys a set must
    # read the set from the tree, not from a list it carries.** No edit can demonstrate
    # that, because every edit lands in a file the list already names — which is exactly
    # how eight board-safety suites went on asserting the length of their own tuple while
    # a shipped renderer sat outside it (GP-1.7, BL-211). The staleness rule inverts with
    # the form: here, a target that already EXISTS is the stale mutation, because the file
    # has since been written for real and the proof is now testing something else.
    applied=$("$PY" - "$work" "$proof" "$i" <<'PYEOF'
import json, pathlib, sys
work, proof_path, index = pathlib.Path(sys.argv[1]), sys.argv[2], int(sys.argv[3])
m = json.load(open(proof_path, encoding="utf-8"))["mutations"][index]
target = work / m["file"]
if m.get("create"):
    if "find" in m:
        print("MALFORMED a create mutation writes a whole file and has no `find`")
        raise SystemExit(0)
    if target.exists():
        print("STALE %s now exists — the mutation adds a file the tree does not have, and "
              "this one has since been written for real" % m["file"]); raise SystemExit(0)
    if not target.parent.is_dir():
        print("MISSING the directory %s" % m["file"].rsplit("/", 1)[0]); raise SystemExit(0)
    target.write_text(m["replace"], encoding="utf-8")
    print("OK"); raise SystemExit(0)
if not target.exists():
    print("MISSING %s" % m["file"]); raise SystemExit(0)
text = target.read_text(encoding="utf-8")
count = text.count(m["find"])
if count != 1:
    print("STALE %d occurrence(s) of %r" % (count, m["find"][:60])); raise SystemExit(0)
target.write_text(text.replace(m["find"], m["replace"], 1), encoding="utf-8")
print("OK")
PYEOF
)
    case "$applied" in
      OK) ;;
      *)  fail_line "$label: the registered mutation still applies (GP-1.5)" \
                    "$applied — the code moved and the proof did not follow it"
          rm -rf "$work"; i=$((i + 1)); continue ;;
    esac

    # GP-1.4 step 2 — mutated must FAIL, and GP-1.9 — it must fail EXACTLY the named checks.
    if PY="$PY" bash "$work/$rel" >"$work/.dirty.out" 2>&1; then
      fail_line "$label: the guard FAILS on the mutated copy" \
                "it passed — the guard no longer detects the defect it exists for"
    else
      aimed=$("$PY" - "$proof" "$i" "$work/.clean.out" "$work/.dirty.out" <<'PYEOF'
import json, re, sys
proof_path, index, clean_path, dirty_path = sys.argv[1], int(sys.argv[2]), sys.argv[3], sys.argv[4]
# Two reporting shapes, because the suites use two. Most print `  FAIL  <label>`; the `chk`
# idiom prints `<id>  <label>  FAIL`. Reading only the first made GP-1.9 report
# "the mutated run named no failing check at all" for a mutation that HAD been caught and
# named — a false negative, but the right kind: it refused to accept a non-zero exit as proof.
FAIL = re.compile(r"^ *FAIL +(\S.*?) *$")
CHK = re.compile(r"^\S{1,6} +(\S.*?) +FAIL\b.*$")


def labels(path):
    seen = []
    for line in open(path, encoding="utf-8", errors="replace"):
        line = line.rstrip("\n")
        if "checks FAILED" in line or "check(s) FAILED" in line:
            continue
        m = FAIL.match(line) or CHK.match(line)
        if m and m.group(1) not in seen:
            seen.append(m.group(1))
    return seen


want = json.load(open(proof_path, encoding="utf-8"))["mutations"][index]["defeats"]
got, clean = labels(dirty_path), labels(clean_path)
bad = []
already = [x for x in want if x in clean]
if already:
    bad.append("already failing before the mutation: %s" % "; ".join(already))
missing = [x for x in want if x not in got]
if missing:
    bad.append("registered but not defeated: %s" % "; ".join(missing))
extra = [x for x in got if x not in want]
if extra:
    bad.append("defeated but not registered: %s" % "; ".join(extra))
if not got:
    bad.append("the mutated run named no failing check at all — it failed for some reason "
               "this proof cannot see, which is not the same as being caught")
print(" | ".join(bad))
PYEOF
)
      if [ -n "$aimed" ]; then
        fail_line "$label: the mutation defeats exactly its registered checks (GP-1.9)" "$aimed"
      else
        pass_line "$label — passes clean, fails mutated on exactly its $(
          "$PY" -c 'import json,sys;print(len(json.load(open(sys.argv[1]))["mutations"][int(sys.argv[2])]["defeats"]))' \
          "$proof" "$i") registered check(s)"
      fi
    fi
    rm -rf "$work"
    i=$((i + 1))
  done
done

# GP-1.7 (second half) — the registry documents exactly the guards that exist.
#
# The counts above are asserted in code, so they cannot drift. The registry table in
# `guard-proof-standard.md` is prose, and it drifted immediately: it read "eight guards,
# sixteen halves" for two minor versions after the ninth landed, and `outcome-framing.sh` was
# absent from the table altogether. Nothing broke — which is the problem. The document a
# maintainer reads to learn the rule disagreed with the rule, and no run said so.
if [ ${#only[@]} -eq 0 ]; then
  registry=$("$PY" - "$repo/tools/guard-proof-standard.md" "${guards[@]}" <<'PYEOF'
import pathlib, re, sys
doc = pathlib.Path(sys.argv[1])
if not doc.exists():
    print("tools/guard-proof-standard.md is missing"); raise SystemExit(0)
listed = set(re.findall(r"^\|\s*`([a-z0-9-]+\.sh)`", doc.read_text(encoding="utf-8"), re.M))
found = {pathlib.Path(g).name for g in sys.argv[2:]}
if not listed:
    print("the registry table has no rows — its format moved and this checked nothing")
elif found - listed:
    print("guard(s) missing from the registry table: %s" % ", ".join(sorted(found - listed)))
elif listed - found:
    print("registry row(s) with no guard on disk: %s" % ", ".join(sorted(listed - found)))
PYEOF
)
  if [ -n "$registry" ]; then
    fail_line "guard-proof-standard.md documents every guard" "$registry"
  else
    pass_line "the registry documents exactly the ${#guards[@]} guards that exist"
  fi
fi

# GP-1.11 — how much of each guard has been DEMONSTRATED, not merely declared.
#
# `51 halves, each proved` was true and misleading at once: halves are counted from the proof
# file, so a guard running twenty checks and registering one mutation was "fully proved" by
# definition. Measured across the tree, 50 of 356 checks had ever been shown to fail. The
# number now travels with the claim (BL-210).
cov_line=""
if [ ${#only[@]} -eq 0 ]; then
  cov_out=$("$PY" "$repo/tools/proof-coverage.py" "$labels_dir" "$repo")
  cov_rc=$?
  cov_line=$(printf '%s\n' "$cov_out" | "$PY" -c '
import sys
for line in sys.stdin:
    if line.startswith("COVERAGE "):
        _, g, total, proved, waived, pct = line.split()
        print("%s of %s checks proved by a mutation (%s%%), %s waived with a reason"
              % (proved, total, pct, waived))
        break
')
  while IFS= read -r problem; do
    case "$problem" in
      "PROBLEM "*) fail_line "every check is proved or waived (GP-1.11)" "${problem#PROBLEM }" ;;
    esac
  done <<COVEOF
$cov_out
COVEOF
  if [ "$cov_rc" -eq 0 ]; then
    pass_line "every mutation names a check the guard publishes, and every guard proves at least one"
  fi
  cov_proved=$(printf '%s\n' "$cov_out" | awk '/^COVERAGE /{print $4}')
  if [ "${cov_proved:-0}" -lt "$EXPECTED_PROVED" ]; then
    fail_line "the proved-check count has not gone backwards (GP-1.11)" \
              "$cov_proved proved, floor is $EXPECTED_PROVED — a check that used to be "\
"demonstrated no longer is. Restore it, or lower the floor deliberately and say why."
  elif [ "${cov_proved:-0}" -gt "$EXPECTED_PROVED" ]; then
    pass_line "proved checks rose to $cov_proved — raise EXPECTED_PROVED to hold the gain"
  fi
fi

echo
if [ ${#only[@]} -eq 0 ]; then
  if [ "$guards_seen" -ne "$EXPECTED_GUARDS" ]; then
    printf 'prove-guards: exercised %s guard(s), expected %s — a guard appeared or vanished\n' \
           "$guards_seen" "$EXPECTED_GUARDS"
    exit 1
  fi
  if [ "$halves_seen" -ne "$EXPECTED_HALVES" ]; then
    printf 'prove-guards: exercised %s half/halves, expected %s\n' \
           "$halves_seen" "$EXPECTED_HALVES"
    exit 1
  fi
fi
if [ "$fails" -ne 0 ]; then
  # Counted as failures, not "N of M" — a guard with no proof file contributes a failure and
  # no half, and "1 of 0 FAILED" is the kind of nonsense that makes a reader distrust the
  # number next to it.
  printf 'prove-guards: %s failure(s); %s half/halves were exercised\n' "$fails" "$halves_seen"
  exit 1
fi
printf 'prove-guards: %s guard(s), %s half/halves, each proved in both directions\n' \
       "$guards_seen" "$halves_seen"
if [ ${#only[@]} -eq 0 ]; then
  printf '             %s\n' "$cov_line"
fi
printf '             %s eval script(s) classified; %s candidate(s) awaiting enrolment, '\
'%s permanent (unmutatable by design)\n' \
       "$scripts_seen" "$candidates_seen" "$permanent_seen"
