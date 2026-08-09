# shellcheck shell=bash
# `probe` — a captured Python check that CRASHED must not read as "nothing to report".
#
# Sourced, not copied. The reason this file exists at all is that the fix WAS written once, in
# `board-pack/evals/assembly.sh` at v0.43.1, and then copied nowhere. Nine `board-safety.sh`
# suites went on running the broken idiom for fourteen versions (BL-121). A helper that has to
# be re-typed into each suite is a helper that will diverge again; one that is sourced cannot.
#
# CAC-LE-1 permits this explicitly — `lint-evals.py` follows `source`/`.` one level when
# deciding whether a suite declares the helpers it calls, so a suite that sources this file
# may call `probe` and one that does not, may not.
#
# --- the defect -------------------------------------------------------------------------
#
# The idiom throughout these suites is:
#
#     hit=$($PY - "$file" <<'PY'
#     ...print anything wrong...
#     PY
#     )
#     if [ -z "$hit" ]; then ok "nothing wrong"; else bad "..." "$hit"; fi
#
# **Command substitution discards the exit status.** A Python traceback goes to stderr and
# leaves stdout empty, which is byte-for-byte what a clean run produces. So the check prints
# `ok`, increments the pass count, and the suite exits zero — while the thing it was written
# to examine was never examined.
#
# It is not hypothetical. The v0.43.0 chart comparison raised `KeyError: 'title'` on two
# malformed figure adapters, printed a traceback to the terminal, and reported *"every chart
# in the model is drawn"*. The defect it existed to catch was directly in front of it and it
# passed. **A test that cannot fail is worse than a missing test, because the missing one does
# not appear in the pass count.**
#
# --- the fix ----------------------------------------------------------------------------
#
# Read the status explicitly and turn a crash into a problem string, which every call site
# already knows how to fail on. The traceback is quoted into the failure rather than left on
# the terminal for somebody to happen to notice.
#
# `probe` returns 0 even on a crash, deliberately: the caller's contract is "empty means
# clean, non-empty means a problem", and a non-zero return here would abort suites that run
# under `set -e` while saying nothing about what went wrong.
#
# Requires `$PY` and a writable `$work`, both of which every suite already sets.
#
# Two call shapes, because the suites use both and getting this wrong is the defect again:
#
#   probe "$file" <<'PY' ... PY     the script arrives on stdin  ->  "$PY" -  "$file"
#   probe -c "print(...)"           the script is an argument    ->  "$PY" -c "print(...)"
#
# Without the `-c` branch, `probe -c "code"` would run `"$PY" - -c "code"`: Python reads an
# empty program from stdin, prints nothing, and exits 0. The caller sees an empty capture and
# calls it clean — a check that cannot fail, introduced by the helper written to prevent
# checks that cannot fail. Caught while migrating the nine suites, by diffing every suite's
# output against its pre-migration output rather than by reading the change.
probe() {  # probe <argv...>  — the Python script arrives on stdin, or via -c
  local out status err
  err="${work:-${TMPDIR:-/tmp}}/probe.$$.err"
  if [ "${1:-}" = "-c" ]; then
    out="$("$PY" "$@" 2>"$err")"
  else
    out="$("$PY" - "$@" 2>"$err")"
  fi
  status=$?
  if [ "$status" -ne 0 ]; then
    printf 'THE CHECK ITSELF FAILED — python exited %s and its output cannot be trusted: %s' \
           "$status" "$(tr '\n' ' ' <"$err" | tail -c 400)"
    rm -f "$err"
    return 0
  fi
  rm -f "$err"
  printf '%s' "$out"
}
