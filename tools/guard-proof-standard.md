# CAC-GP-1 — the guard-proof standard

**Applies to:** every skill in `cac-ciso-toolkit`
**Implemented by:** `tools/prove-guards.sh`, run in CI on the 3.9 floor
**In force since:** v0.41.3 — GP-1.7 added in v0.45.0
**Sibling standard:** [CAC-LE-1](eval-lint-standard.md), the eval-harness lint

*"Since", not "as of", deliberately. The line here read `as of v0.41.3` and was two minors
behind within a fortnight. A version that claims currency rots; one that marks a starting point
does not. The same reasoning took the guard counts out of the prose below and left them in the
one place that asserts them.*

---

## The problem, stated exactly

The suite's guards each exist because a specific defect would otherwise look like a feature,
and each is unusually well written — `no-closed-state.sh` explains in its own header why
somebody will eventually reach for the change it forbids, and runs a behavioural and a static
half because either alone is escapable.

Most of them also record that they were mutation-tested. For example:

> *Mutation-tested. `exposure["mitigated"] = True` fails the static half; writing the same key
> into the store fails the behavioural half. A guard never seen to fail is not known to work.*

**That sentence is true and the proof behind it was prose.** It was performed once, against code
that has since moved, and nothing re-ran it. A guard that stops detecting its own defect —
because a function was renamed, a scan path narrowed, a regex loosened — goes on printing `ok`
forever, and the printing is indistinguishable from working.

This is the failure class the repo already names elsewhere: *an eval CI does not name is an eval
that never runs*, and *a loop over `evals/*.sh` goes green the day someone renames a directory*.
A guard proved once and trusted thereafter is that failure with a longer fuse.

**The fix is to make the mutation data instead of prose, and to run it.**

---

## The standard

### GP-1.1 Every guard registers a mutation

A **guard** is any eval whose purpose is to prove a defect *cannot* occur. Each registers at
least one mutation in `<skill>/evals/guard-proofs/<guard-name>.json`.

```json
{
  "guard": "skills/ai-register/evals/no-closed-state.sh",
  "forbids": "any mitigated / resolved / closed / accepted state on an attack class",
  "note": "The obvious next feature, and a one-line change nothing else would object to.",
  "mutations": [
    {
      "half": "static",
      "why": "a closed-state field declared in shipped code, even if never executed",
      "file": "skills/ai-register/scripts/ai_register.py",
      "find": "def accept_exposure(*_args, **_kwargs):",
      "replace": "def _apply_outcome(store, did, cls):\n    ...\n\n\ndef accept_exposure(*_args, **_kwargs):"
    }
  ]
}
```

**A guard with two halves registers a mutation for each half**, and each mutation must defeat
*its own* half specifically. Otherwise half the guard is proven and half is assumed, which is
worse than knowing neither is.

That constraint is load-bearing, and `no-closed-state` shows why. Its static half reads string
literals out of the AST; its behavioural half reads a real store. A mutation writing
`exposure[cls]["mitigated"] = True` trips *both*, so it proves neither independently. The
registered behavioural mutation writes the key as `"mitig" + "ated"` — invisible to a literal
scan, and caught in the store. That is the escape a static-only guard would miss, which is
precisely the thing the behavioural half exists for.

### GP-1.2 An unregistered guard is a failure, not a skip

`prove-guards.sh` discovers guards by convention and **fails when one has no proof file**. A
skip would let the standard erode exactly the way a globbed eval list does — silently, and
looking green.

### GP-1.3 The proof runs on a copy, never the working tree

Each half runs against a fresh copy. A failed or interrupted run cannot leave a mutated repo
behind. This is not fastidiousness: a proof that mutates the working tree and dies halfway
leaves a repo that looks fine and is not.

### GP-1.4 Both directions, in that order

1. **Clean → the guard must PASS.** If it fails here, either the guard is broken or the tree is
   dirty, and nothing about the mutation result would mean anything.
2. **Mutated → the guard must FAIL.**

Reporting only step 2 is the common mistake. A guard that always fails would "pass" a mutation
test that only looks for failure.

### GP-1.5 A stale mutation is a failure

If `find` no longer matches, the run **fails**, naming the guard and the string. The code moved
and the proof did not follow it — precisely the condition where a guard quietly stops guarding.
Maintaining the mutation alongside the code is the point, not an overhead.

A stale mutation is not hypothetical. Writing this standard's own proofs, a first attempt used
an anchor that no longer matched: the mutation silently failed to apply, the guard ran against
an unmutated tree, and the run printed **PASS** — which reads as *"the guard missed it"* to
anybody not checking whether the injection landed. GP-1.5 exists because that already happened.

### GP-1.6 The proof runs in CI, on the floor

Listed individually in `.github/workflows/evals.yml`, for the reason that file already gives
about globs.

### GP-1.7 A scan asserts what it read, and the registry asserts what exists

Two halves of one rule: **a guard that surveys a set must assert the set, not its non-emptiness.**

*The file set.* Every static half walks `scripts/*.py` and `renderers/*.py` and prints the count
it read, and each guard asserted that count was **at least one** — real anti-vacuity, and not
enough. Five scan helpers excluded `renderers/_common.py` alongside `cac_graphics.py`, under a
comment that only ever justified the brand file. `cac_graphics.py` is vendored byte-identical
from `tools/` and guarded there; `_common.py` is 500 lines of board-visible prose — the
placeholder, the caveat, the *Not legal advice* footer — and is the likeliest place in the skill
that somebody adds the sentence the guard forbids. The scans read three files of five and said
so, truthfully, in a sentence whose only claim was "not zero".

Nothing caught it because **every registered mutation planted into `scripts/`**, so the exclusion
was never once exercised. Four live guards were provably blind: planting each guard's own
registered defect into its `_common.py` passed all four.

Each guard now recomputes the expected file list from the filesystem and asserts the scan read
**all** of it. The recomputation is deliberately in the guard rather than the helper — a helper
that both narrows its glob and reports what it should have read proves nothing.

*The registry.* Same rule applied to this document. `prove-guards.sh` now compares the table
below against the guards it discovers and fails on either mismatch. That table said *"eight
guards, sixteen halves"* for two minor versions after the ninth landed, with `outcome-framing.sh`
missing from it entirely — harmless to the runner, and the exact failure this standard exists to
name. When the check was written it found that omission on its first run.

---

## Registry

| Guard | Skill | Forbids | Halves |
|---|---|---|---|
| `no-derived-materiality.sh` | `business-context` | a percent-of-revenue materiality threshold | static · behavioural |
| `no-vendor-score.sh` | `vendor-register` | a computed vendor risk score | behavioural · static |
| `proposal-boundary.sh` | `vendor-register` | the reading layer closing anything; T3/T4 satisfying | behavioural · static |
| `evidence-tiers.sh` | `vendor-register` | a T1 with no scope or period; a bridge letter extending currency | scope-and-period · expiry |
| `no-closed-state.sh` | `ai-register` | a `mitigated`/`resolved`/`accepted` state on an attack class | static · behavioural |
| `no-ai-score.sh` | `ai-register` | a computed AI risk score | behavioural · static |
| `no-regime-dates.sh` | `ai-register` | a regulatory date in prose; an uncited obligation | static · dataset |
| `no-priority-score.sh` | `attention-surface` | a computed priority ordering the escalations | static · behavioural |
| `outcome-framing.sh` | `board-pack` | a board sentence with no consequence; a decisions entry that decides nothing | consequence-floor · decision-hard-rule |

Every guard above, both halves, proved in both directions on every run. **The table is checked,
not maintained by memory** — `prove-guards.sh` fails if a guard on disk is missing a row, or a
row names a guard that is gone (GP-1.7). No count is written here on purpose: the numbers live
in `EXPECTED_GUARDS` and `EXPECTED_HALVES`, where they are asserted rather than described.

**`evidence-tiers.sh` was the reason to do this first.** Every other guard had at least been
proved once; that one carried no such record, and it protects the rule most exposed to
commercial pressure — *"the vendor's trust centre says exactly what we need, why can't it
count?"* Both its halves are now proved: removing the T1 scope-and-period refusal, and removing
the end of the grace window so nothing can ever expire.

---

## Anti-vacuity

`EXPECTED_GUARDS` and `EXPECTED_HALVES` are asserted, and the run prints both counts. A proof
run that silently exercised nothing is the thing this document exists to prevent. Adding a guard
without registering it fails; registering one and deleting the guard fails too.

---

*A Cyber Aware Creation · Not affiliated with NIST.*
