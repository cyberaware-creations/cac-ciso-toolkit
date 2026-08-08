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
#
# Usage: tools/prove-guards.sh [guard-name ...]
set -u

PY="${PY:-$(command -v python3)}"
repo="$(cd "$(dirname "$0")/.." && pwd)"
only=("$@")

# Anti-vacuity, matching the house convention. A proof run that silently exercised nothing is
# the thing this file exists to prevent, so the counts are asserted rather than printed.
EXPECTED_GUARDS=9
EXPECTED_HALVES=18

guards_seen=0
halves_seen=0
fails=0

pass_line() { printf '  ok    %s\n' "$1"; }
fail_line() { fails=$((fails + 1)); printf '  FAIL  %s\n         %s\n' "$1" "$2"; }

echo "prove-guards (CAC-GP-1): $($PY -V 2>&1)"
echo

# --- discover guards by convention (GP-1.2) -----------------------------------
#
# The same convention the registry documents: `no-*.sh`, plus the two named guards whose
# subject is a boundary rather than an absence. Discovered rather than listed, so a new guard
# is registered or fails — it cannot be quietly omitted.
# Built with `while read` rather than `mapfile`, which is bash 4 and macOS ships 3.2 — the
# same floor discipline the Python 3.9 rule applies to the engines.
guards=()
while IFS= read -r line; do
  [ -n "$line" ] && guards+=("$line")
done < <(ls "$repo"/skills/*/evals/no-*.sh \
            "$repo"/skills/*/evals/proposal-boundary.sh \
            "$repo"/skills/*/evals/evidence-tiers.sh \
            "$repo"/skills/*/evals/outcome-framing.sh 2>/dev/null | sort)

if [ "${#guards[@]}" -eq 0 ]; then
  echo "prove-guards: found no guards at all — the layout moved and this proved nothing"
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

    # GP-1.5 — apply, and a `find` that no longer matches is a failure.
    applied=$("$PY" - "$work" "$proof" "$i" <<'PYEOF'
import json, pathlib, sys
work, proof_path, index = pathlib.Path(sys.argv[1]), sys.argv[2], int(sys.argv[3])
m = json.load(open(proof_path, encoding="utf-8"))["mutations"][index]
target = work / m["file"]
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

    # GP-1.4 step 2 — mutated must FAIL.
    if PY="$PY" bash "$work/$rel" >"$work/.dirty.out" 2>&1; then
      fail_line "$label: the guard FAILS on the mutated copy" \
                "it passed — the guard no longer detects the defect it exists for"
    else
      pass_line "$label — passes clean, fails mutated"
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
