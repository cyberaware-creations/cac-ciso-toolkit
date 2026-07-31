#!/bin/bash
# Run the trigger-routing checklist headlessly.
#
#   ./run-triggers.sh <output-dir> [id ...]
#
# Every `claude -p` invocation is a fresh session, which is what makes this a valid
# routing test — a warm session has already seen the skill and biases the result.
#
# Each case runs in its own empty working directory, deliberately. Routing is decided
# before any file is read, and an empty cwd keeps the runs from writing into your repo
# or from finding one case's leftovers in the next case's directory.
#
# BEFORE YOU RUN THIS: the installed plugin must match your working tree. See
# trigger-prompts.md ("Refresh the plugin first") — `claude plugin update` is a no-op
# when the version number hasn't changed, so an edited skill will NOT be under test.

set -u
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
out="${1:?usage: run-triggers.sh <output-dir> [id ...]}"; shift || true
only=("$@")
maxjobs="${MAXJOBS:-5}"
# The case list is a parameter, not a fixture. A second skill's routing checklist is a
# different set of prompts scored the same way, and duplicating a hundred lines of harness
# to hold one file path is how the two copies drift.
prompts="${PROMPTS:-$here/prompts.tsv}"
[ -r "$prompts" ] || { echo "no readable prompts file at $prompts"; exit 2; }

mkdir -p "$out/runs" "$out/work"
# Each run `cd`s into its own working directory, so every path handed to it has to be
# absolute. A relative output dir resolves against the *case* directory once inside the
# subshell, the redirect fails, and every transcript lands nowhere — which reads as
# "the model produced nothing", not as "the script was called wrong".
out="$(cd "$out" && pwd)"

run_one() {
  local id="$1" prompt="$2"
  local wd="$out/work/$id"
  mkdir -p "$wd"
  ( cd "$wd" && claude -p "$prompt" \
      --output-format stream-json --verbose --max-turns 12 \
      > "$out/runs/$id.jsonl" 2> "$out/runs/$id.err" </dev/null )
  echo "  $id done"
}

while IFS=$'\t' read -r id exp prompt; do
  [ -z "${id:-}" ] && continue
  if [ ${#only[@]} -gt 0 ]; then
    printf '%s\n' "${only[@]}" | grep -qx "$id" || continue
  fi
  while [ "$(jobs -rp | wc -l)" -ge "$maxjobs" ]; do wait -n 2>/dev/null || sleep 1; done
  run_one "$id" "$prompt" &
done < "$prompts"
wait

echo "ALL DONE — scoring"
python3 "$here/score-triggers.py" "$prompts" "$out"
