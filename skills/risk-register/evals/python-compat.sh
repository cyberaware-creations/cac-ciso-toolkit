#!/bin/bash
# Does every shipped .py compile on the oldest Python we claim to support?
#
#   ./python-compat.sh [interpreter]
#
# Run this before every release. It is the cheapest check in the repo and it catches a
# class of bug that no amount of behavioural testing will: syntax the *author's*
# interpreter accepts and the *user's* rejects.
#
# That is not hypothetical. v0.1.4 shipped an escaped quote inside an f-string expression
# — legal from Python 3.12 (PEP 701), a hard SyntaxError before it. Every test passed,
# because they ran on 3.14. On the 3.11 container the module could not be imported at
# all, so the entire CISO working view was missing rather than degraded.
#
# Note for anyone tempted by a pure-Python shortcut: `ast.parse(src, feature_version=...)`
# does NOT catch this. The f-string change was in the tokenizer, and feature_version does
# not roll the tokenizer back — it reports the file as fine on (3, 9). Only a real old
# interpreter tells the truth, which is why this script insists on one.
#
# Discovery includes untracked-but-not-ignored files (`--others --exclude-standard`), not
# just tracked ones. A brand-new script is exactly the file most likely to carry syntax
# the floor rejects, and it is untracked right up until the commit that ships it. Listing
# only tracked files skipped it silently while still printing "all N shipped files compile"
# — a count that reads as coverage it did not have.

set -u
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "$here/../../.." && pwd)"

# The supported floor. macOS ships 3.9.6 at /usr/bin/python3, which makes this free to
# check on any Mac. Raise the floor here and in README.md together, never separately.
FLOOR_MAJOR=3
FLOOR_MINOR=9
PY="${1:-/usr/bin/python3}"

if ! command -v "$PY" >/dev/null 2>&1 && [ ! -x "$PY" ]; then
  echo "python-compat: no interpreter at '$PY'."
  echo "  Pass one explicitly: ./python-compat.sh /path/to/python3.9"
  echo "  Checking against your default python3 would defeat the point of this test."
  exit 2
fi

ver=$("$PY" -c 'import sys;print("%d.%d.%d"%sys.version_info[:3])')
major=$("$PY" -c 'import sys;print(sys.version_info[0])')
minor=$("$PY" -c 'import sys;print(sys.version_info[1])')
echo "Checking against Python $ver  (declared floor: $FLOOR_MAJOR.$FLOOR_MINOR)"

if [ "$major" -gt "$FLOOR_MAJOR" ] || [ "$minor" -gt "$FLOOR_MINOR" ]; then
  echo "  WARNING: this interpreter is NEWER than the declared floor."
  echo "  A pass here does not prove the floor is met. Find a $FLOOR_MAJOR.$FLOOR_MINOR."
fi

cd "$repo" || exit 2
fails=0
count=0
while IFS= read -r f; do
  count=$((count + 1))
  if ! out=$("$PY" -m py_compile "$f" 2>&1); then
    echo "FAIL  $f"
    echo "$out" | sed -n '2,5p' | sed 's/^/        /'
    fails=$((fails + 1))
  fi
done < <(git ls-files --cached --others --exclude-standard '*.py')

# Bytecode from a non-default interpreter is noise in the working tree.
find "$repo/skills" "$repo/tools" -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null

echo
if [ "$fails" -eq 0 ]; then
  echo "python-compat: all $count shipped files compile on $ver"
else
  echo "python-compat: $fails of $count files FAILED on $ver"
fi
exit $([ "$fails" -eq 0 ] && echo 0 || echo 1)
