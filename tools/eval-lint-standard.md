# CAC-LE-1 — the eval-harness lint standard

**Applies to:** every `skills/*/evals/*.sh` in `cac-ciso-toolkit`
**Implemented by:** `tools/lint-evals.py`, run in CI on the 3.9 floor
**In force since:** v0.43.1
**Sibling standard:** [CAC-GP-1](guard-proof-standard.md), the guard-proof standard

---

## The problem, stated exactly

`skills/risk-register/evals/board-safety.sh` gained a new check written with `ok` and `bad`.
**That suite declares `chk`, and neither of the other two.**

The house convention in these suites is `set -u` without `set -e`, chosen deliberately so that
one failing check does not abort the forty after it. Under that convention an unrecognised
command is a **silent no-op**. The shell wrote `ok: command not found` to stderr, the failure
counter never moved, and the suite printed `all checks passed` and exited 0.

The check was never registered, so it could not fail. Its greenness was indistinguishable from
a real pass — and it was reported, in good faith, as one of nine suites verified green. Eight
had run. One had not.

The tell was in the output the whole time. That suite printed `all checks passed`; every other
suite prints `all N checks passed`. A missing number, read as a formatting difference.

This is the failure class [CAC-GP-1](guard-proof-standard.md) exists for — *a check that has
stopped checking goes on printing `ok` forever* — one layer further down, in the harness rather
than in what the harness tests. It gets the same treatment: **made data, and re-run every time.**

---

## The standard

### LE-1.1 A suite may only call harness helpers it defines

For each `evals/*.sh`, every name in the harness vocabulary that the script **calls** must also
be **defined** in that script, or in a file it sources.

The vocabulary is a closed list — `ok`, `bad`, `chk`, `eq`, `ne`, `yn`, `skip`, `probe`,
`pass_line`, `fail_line` — and closed on purpose. A general "undefined function" linter would
drown in the real commands these scripts legitimately run, and a check nobody reads is the thing
being fixed here, not a thing to add more of.

Nothing else is inspected. This is not a shell linter. It answers one question, which is the
question that was missed.

### LE-1.2 The parser must not cry wolf

A linter with a false positive on a real file is a linter somebody switches off, so the two
places these suites embed non-shell code are stripped before matching:

- **Quoted heredoc bodies** (`<<'PY'`, `<<"PY"`) are Python, not shell. An *unquoted* heredoc is
  still shell-expanded, so a helper named in one is a genuine reference and stays visible.
- **Single-quoted `python3 -c '...'` payloads**, for the same reason in different syntax.
  `nist-csf/evals/run-conversations.sh` embeds a Python program that has a local variable called
  `bad` — which is a harness helper in eight of these suites. A *double*-quoted payload is
  shell-expanded and stays visible.

Both exclusions were written because the first run over the real repo reported them, and both
are registered in the self-test so the narrowing cannot be widened by accident.

### LE-1.3 An empty run is a failure

`lint-evals.py` discovers suites rather than taking a list. Finding none exits 1 with
*"found no shell suites to lint, which is itself a failure"*. The same anti-vacuity rule
`prove-guards.sh` applies to guards, and `EXPECTED_CHECKS` applies inside each suite: a run that
silently examined nothing must not look like a run that found nothing wrong.

### LE-1.4 The linter has its own self-test, and it runs first

`--self-test` exercises the matcher against cases in both directions, including a commented-out
call (not a call), a call in an `else` arm (a call), and the two false positives above. It is a
separate CI step, ordered before the lint itself, because a broken matcher would otherwise
report a clean repo.

### LE-1.5 It runs in CI, on the floor

Two steps in `.github/workflows/evals.yml`, listed individually, for the reason that file
already gives about globs.

---

## Scope, and what this does not cover

This checks that a called helper is **declared**. It does not check that a declared helper is
**counted** — that is `EXPECTED_CHECKS`, asserted inside each suite, and the two are
complementary: LE-1 catches a check that never ran, `EXPECTED_CHECKS` catches a check that
vanished.

It also does not check *captured* output. A suite that reads a probe's stdout in command
substitution, where an exception produces empty output the suite treats as "no problems found",
passes this lint and is wrong — `board-pack/evals/assembly.sh` did exactly that, and passed
while looking directly at the defect it was written for. That is a candidate second rule for
this standard, tracked as BL-121, and it belongs here when it lands.

---

*A Cyber Aware Creation · Not affiliated with NIST.*
