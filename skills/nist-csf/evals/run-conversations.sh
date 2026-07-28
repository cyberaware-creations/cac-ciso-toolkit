#!/bin/bash
# Run the conversational-behaviour eval headlessly.
#
#   ./run-conversations.sh <output-dir> [id ...]
#
# Every case is a fresh `claude -p` session, which is what makes this a valid behaviour
# test — a warm session has already been told the anti-drift rules, which is exactly what
# this suite is trying to find out.
#
# Each case runs in its own working directory **seeded with a copy of its fixture store**.
# That is the deliberate opposite of run-triggers.sh, which runs every case in an empty
# directory: routing is decided before any file is read, so an empty cwd is the honest
# setup there. Here the store IS the thing under test — the binding checks are a diff of
# the .csfp before and after — so the run must have a real store in front of it. Each case
# gets its own copy so one case's writes cannot leak into the next, and so nothing touches
# the fixtures in the repo.
#
# BEFORE YOU RUN THIS: the installed plugin must match your working tree. See
# conversation-prompts.md ("Refresh the plugin first") — `claude plugin update` is a no-op
# when the version number hasn't changed, so an edited SKILL.md will NOT be under test.

set -u
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
out="${1:?usage: run-conversations.sh <output-dir> [id ...]}"; shift || true
only=("$@")
maxjobs="${MAXJOBS:-3}"

mkdir -p "$out/runs" "$out/work" "$out/before"
# Each run `cd`s into its own working directory, so every path handed to it has to be
# absolute. Resolve the output dir once here rather than trusting the caller to pass one.
out="$(cd "$out" && pwd)"

# The case table is JSON, and the loop below eats TSV. Flatten it in one place, up front,
# and refuse to run at all if a prompt carries a tab or a newline: split on $'\t' those
# would silently truncate a prompt or shift a column, and the suite would score a case it
# never actually asked. Failing here costs nothing; failing after six paid runs does not.
cases_tsv="$out/cases.tsv"
python3 -c '
import json, sys
cases = json.load(open(sys.argv[1]))["cases"]
bad = [c["id"] for c in cases
       if any(ch in c["prompt"] for ch in ("\t", "\n", "\r"))]
if bad:
    sys.exit("conversations.json: prompt contains a tab or newline in %s — the runner "
             "splits cases on tabs and cannot carry it intact." % ", ".join(bad))
for c in cases:
    print("\t".join([c["id"], c["fixture"], c["prompt"]]))
' "$here/conversations.json" > "$cases_tsv" || {
  echo "Could not build the case table from conversations.json — nothing was run." >&2
  exit 2
}

run_one() {
  local id="$1" fixture="$2" prompt="$3"
  local wd="$out/work/$id"
  mkdir -p "$wd"
  # Two copies of the same fixture: one the run mutates, one kept pristine as the
  # before-image the scorer diffs against.
  cp "$here/fixtures/stores/$fixture" "$wd/$fixture"
  cp "$here/fixtures/stores/$fixture" "$out/before/$id.csfp"
  ( cd "$wd" && claude -p "$prompt" \
      --output-format stream-json --verbose --max-turns 20 \
      > "$out/runs/$id.jsonl" 2> "$out/runs/$id.err" </dev/null )
  echo "  $id done"
}

while IFS=$'\t' read -r id fixture prompt; do
  [ -z "${id:-}" ] && continue
  if [ ${#only[@]} -gt 0 ]; then
    printf '%s\n' "${only[@]}" | grep -qx "$id" || continue
  fi
  while [ "$(jobs -rp | wc -l)" -ge "$maxjobs" ]; do wait -n 2>/dev/null || sleep 1; done
  run_one "$id" "$fixture" "$prompt" &
done < "$cases_tsv"
wait

echo "ALL DONE — scoring"
python3 "$here/score-conversations.py" "$out"
