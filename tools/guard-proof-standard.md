# CAC-GP-1 — the guard-proof standard

**Applies to:** every skill in `cac-ciso-toolkit`
**Implemented by:** `tools/prove-guards.sh`, run in CI on the 3.9 floor
**In force since:** v0.41.3 — GP-1.7 added in v0.45.0, GP-1.8 and GP-1.9 in v0.56.0,
GP-1.10 in v0.64.1, GP-1.11 in v0.67.0
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
      "defeats": ["no shipped .py assigns a closed-state field"],
      "file": "skills/ai-register/scripts/ai_register.py",
      "find": "def accept_exposure(*_args, **_kwargs):",
      "replace": "def _apply_outcome(store, did, cls):\n    ...\n\n\ndef accept_exposure(*_args, **_kwargs):"
    }
  ]
}
```

**A guard with two halves registers a mutation for each half**, and each mutation must defeat
*its own* half specifically. Otherwise half the guard is proven and half is assumed, which is
worse than knowing neither is. `defeats` is how that is enforced rather than intended — see
GP-1.9, which found two guards quietly failing this rule.

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

**That sentence is not yet true of the ten `board-safety.sh` suites, and this is the record of
it.** They carry a hardcoded `FILES` tuple instead, so the count they assert is the length of
their own list rather than of the tree. Measured: `risk-register` scans 3 of 5 shipped files —
`_common.py`, `render_board.py` and `render_report.py` among the missing — `nist-csf` 4 of 6,
`metrics-register` 3 of 4, and `ai-register` and `vendor-register` scan through a different
idiom again. A file added to a skill tomorrow joins none of them. That is BL-211, filed with
these numbers rather than left as an aspiration in this paragraph — a standard describing
behaviour it does not have is the same defect one level up.

*The registry.* Same rule applied to this document. `prove-guards.sh` now compares the table
below against the guards it discovers and fails on either mismatch. That table said *"eight
guards, sixteen halves"* for two minor versions after the ninth landed, with `outcome-framing.sh`
missing from it entirely — harmless to the runner, and the exact failure this standard exists to
name. When the check was written it found that omission on its first run.

### GP-1.8 Discovery is a registry that must cover the tree, not a filename convention

GP-1.2 says an unregistered guard is a failure. That is only true if the runner can *see* the
guard. It could not. Discovery globbed `evals/no-*.sh` plus three literal filenames, and **eight
real guards were invisible to it** — seven copies of `decisions-render.sh`, whose name no
convention anticipated, and `ai-register/exposure.sh`, whose name resembles nothing. None had
ever been mutation-tested. Worse, the GP-1.7 registry check filtered through the same globs, so
it compared the document against the blind spot and reported a clean bill.

No filename rule could have caught this, because **the failure is an omission, and an omission
has no filename.** A marker line inside each guard was the other candidate and fails for the
same reason: a marker cannot detect its own absence.

Discovery now reads `tools/guard-registry.json`, which assigns every `skills/*/evals/*.sh` on
disk exactly one of three roles — `guard`, `candidate`, `not-a-guard` — and **a script in none
of them fails the run.** Classifying non-guards is not bookkeeping; it is the mechanism. Only a
list obliged to cover everything can fail on something missing.

`candidate` is a real verdict, not a waiting room: guard-shaped, deliberately not enrolled.
The count prints on every run, and it fell from eleven to one across v0.60.0 and v0.61.0 —
which is what a printed number is for.

**A candidate may be `permanent`, and one is.** `business-context/evals/archetype-advisory.sh`
cannot be mutation-tested, and the reason is worth more than an enrolment would have been. It
runs an A/B holding every declared fact constant and moving only revenue and headcount,
asserting the applicability objects come back byte-identical. To defeat it, a mutation must
make A and B **differ** — but `applies(profile, question_sets, subject)` never receives the
store, so revenue and headcount are **structurally unreachable from the function that decides
scope**. The separation this suite protects is enforced by the call signature, not by
convention, and a mutation would have to widen that signature first, which is a design change
and not a proof.

Enrolling it would mean registering a mutation that trips an adjacent check and calling the
guard proved: the exact failure GP-1.9 exists for. So the third answer is recorded as data —
`"permanent": true` on the registry row — and the run counts the two kinds apart:

```
48 eval script(s) classified; 0 candidate(s) awaiting enrolment, 1 permanent (unmutatable by design)
```

Printing a settled verdict as *"not yet enrolled"* would be a small, permanent untruth in the
one line a reader trusts for scope. `permanent` is valid on a candidate and nowhere else, and
the registry check enforces that. **If `applies()` ever gains access to the store the row must
be revisited** — the defect becomes expressible, and a mutation becomes both possible and
required.

### GP-1.9 A mutation names the checks it defeats, and defeats exactly those

GP-1.1 has required since the beginning that each mutation defeat *its own half* specifically.
Nothing enforced it. The runner asked one question — did the guard exit non-zero? — and a
non-zero exit is not evidence that the registered half was the half that caught it.

Two guards were violating GP-1.1 in exactly that way, both reporting the textbook
clean-pass/mutated-fail while proving one thing twice:

- **`proposal-boundary`.** The behavioural mutation added `"T3"` to `SATISFYING_TIERS`. That is
  also an inlined tier list, so the *static* half flagged it too. It now assembles the tier as
  `"T" + "3"` — invisible to a literal scan, for the same reason `no-closed-state`'s
  behavioural mutation writes `"mitig" + "ated"`.
- **`evidence-tiers`.** Disabling the T1 scope-and-period refusal let an undated T1 into the
  store, and the *expiry* half was reading `evidence[0]` positionally — so three expiry
  assertions failed for a reason with nothing to do with expiry. **The mutation was not the
  defect here; the guard was.** The expiry half now selects the dated T1 by its period, and
  asserts there is exactly one.

Each mutation therefore carries a `defeats` list naming the checks the mutated run must fail,
and the runner asserts the set **exactly**: every named check fails, no unnamed check fails,
and none of them was already failing on the clean copy. A mutation whose blast radius grows —
because the guard changed, or because it was aimed loosely — fails the run instead of passing
it. Blast radius is data now, and it is reviewable in the proof file.

The cross-half rule is **distinguishability, not disjointness.** `outcome-framing`'s two
mutations both trip *"the checker's own tests pass"*, a meta-check belonging to neither half,
and that is legitimate; each still defeats one check the other does not. What is forbidden is
two halves with identical failure signatures, because then one of them is unproved and nothing
says so.

*Proved against itself.* Deleting a `defeats` list fails the run; giving two halves the same
list fails it; naming a check the guard never prints fails it. All three were run.

### GP-1.10 A check is read at n=0 and n=1, not at n=typical

**Five checks in this repository have now failed the same way**, which is what promotes this
from an observation to a clause:

| | The check | What it could not tell apart |
|---|---|---|
| BL-121 | `[ -z "$res" ]` | a clean scan from a crashed one — 51 checks, nine suites |
| BL-176 | `len(bounds) == 1` | a missing anchor from a legally excluded one |
| BL-201 | `all(...)` over a singleton | *nearest* from *only* — shipped clean for three releases |
| BL-194/B | a fixture that never set up the thing it tested | nothing; the assertion was right and the setup was not |
| BL-204 | two whole functions called by no test | a guard that works from one that has never run |

Every one of them **returned the correct answer on every case its author wrote.** That is the
defining property: these are not sloppy checks, they are checks whose discriminating power
disappears exactly where nobody looked.

So, when writing or reviewing a guard:

* **Ask what it does when its input is empty or has one element.** A comparison needs something
  to compare against; an `all()` over nothing is true; an empty scan reports success.
* **A count that is printed is not a count that is asserted.** `check-sources.py` and
  `check-versions.py` both printed their own check totals for months while asserting nothing
  about them. Both now carry a floor.
* **Prove it by breaking it.** This is the only step that actually finds the shape. BL-204 swept
  274 mechanical mutations across the five tool checks; the two most valuable findings —
  `check_maker_name` and `check_import_time_palette`, both shipping in CI, both printing a
  reassuring line every run — were called by **nothing** in their own suite, and no amount of
  reading had noticed in the releases they had been there.

GP-1.1 already requires this of `skills/*/evals/*.sh`. The tool checks in `tools/` sit outside
that registry and had no equivalent discipline; this clause is what they are held to instead.

### GP-1.11 A check is proved, or it is counted as unproved — never assumed

GP-1.1 requires a mutation per half. **Halves are counted from the proof file**, so the
framework's own yardstick was the claim being made:

```bash
halves=$("$PY" -c 'print(len(proof.get("mutations") or []))' "$proof")
```

A guard running twenty checks and registering one mutation reported the same
`each proved in both directions` as one whose every check is covered. Measured across the
tree: **50 of 356 checks had ever been demonstrated to fail — 14%.** The sentence was true
and misleading at once, which is worse than a sentence that is merely wrong (BL-210).

**Two things were needed before the ratio could even be computed.**

*A check must have a stable name.* Suites printed one label on success and another on failure:

```bash
ok  "no shipped .py assigns a closed-state field on an exposure class"
bad "no shipped .py assigns a closed-state field"
```

GP-1.9 matches the mutated run, so the proof worked — but **33 of 83 `defeats` entries, 40%,
across 15 of 36 guards, named a string no clean run ever published.** A check whose name
changes with the branch, or with interpolated data (`ok "... ($scanned read)"`), cannot be
counted, waived, or found by the next reader. The runner now fails on it.

*The runner must read the clean run.* It always performed one — GP-1.4 step 1 — and only ever
looked at the exit status. The published labels were there the whole time.

**What is enforced.** Every `defeats` entry names a check the clean run publishes; every
waived check exists; every guard defeats at least one of its own checks; and a waiver carries
a reason that is not byte-identical to another guard's — because `guard-registry.json` already
has 13 of 21 `not-a-guard` rows sharing one template, and that is what
classification-by-boilerplate looks like from the outside.

**What is counted, not enforced.** The remaining unproved checks. Mass-waiving them was the
obvious move and is the wrong one: reading them, a real fraction *are* the guarded property —
`ai-register`'s *"no decision renders as a raw Python dict — the defect this suite exists for"*
was among them. A waiver there is not a decision, it is the same false comfort in a new
wrapper, and it would read as settled. So the number is printed on every run and
`EXPECTED_PROVED` is a **ratchet**: it may rise freely and may never fall. Sorting the
remainder into needs-a-mutation and genuinely-a-precondition is separate, filed work.

A floor rather than an equality, deliberately. The honest end state is not 356 of 356 — an
anti-vacuity assertion that a fixture was built is a precondition, and a mutation for it would
prove only that the fixture still works.

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
| `decisions-render.sh` | `ai-register` | a decision rendered as a raw Python dict repr instead of its text | render |
| `decisions-render.sh` | `exceptions-register` | a decision rendered as a raw Python dict repr instead of its text | render |
| `decisions-render.sh` | `incident-materiality` | a decision rendered as a raw Python dict repr instead of its text | render |
| `decisions-render.sh` | `metrics-register` | a decision rendered as a raw Python dict repr instead of its text | render |
| `decisions-render.sh` | `nist-csf` | a decision rendered as a raw Python dict repr instead of its text | render |
| `decisions-render.sh` | `risk-register` | a decision rendered as a raw Python dict repr instead of its text | render |
| `decisions-render.sh` | `vendor-register` | a decision rendered as a raw Python dict repr instead of its text | render |
| `exposure.sh` | `ai-register` | a hand-selectable exposure class — the guard is the ABSENCE of a command | absence · derivation |
| `board-safety.sh` | `ai-register` | a board artifact that does not say it is not legal advice | legal-advice |
| `board-safety.sh` | `risk-register` | raw framework wording reaching a board renderer | raw-title |
| `questions.sh` | `vendor-register` | a vendor assertion shrinking the question set | subtraction |
| `board-safety.sh` | `board-pack` | catastrophizing or false-confidence vocabulary in a board renderer | source-scan |
| `board-safety.sh` | `business-context` | catastrophizing or false-confidence vocabulary in a board renderer | source-scan |
| `board-safety.sh` | `exceptions-register` | catastrophizing or false-confidence vocabulary in a board renderer | source-scan |
| `board-safety.sh` | `incident-materiality` | catastrophizing, false confidence, or a materiality conclusion stated as fact | source-scan |
| `board-safety.sh` | `metrics-register` | catastrophizing or false-confidence vocabulary in a board renderer | source-scan |
| `board-safety.sh` | `nist-csf` | catastrophizing or false-confidence vocabulary in a board renderer | source-scan |
| `board-safety.sh` | `vendor-register` | a board artifact that does not say it is not legal advice | legal-advice |
| `board-safety.sh` | `policy-register` | catastrophizing or false-confidence vocabulary in the reader-facing renderer | source-scan |
| `no-coverage-claim.sh` | `policy-register` | any state, key, token or chip saying a requirement is met because a policy maps to it | static · behavioural |
| `no-coverage-percentage.sh` | `policy-register` | a proportion, percentage or float in the requirement view — counts only | behavioural · static |
| `no-deletion.sh` | `policy-register` | any path that removes a policy record; supersession is the only way out of force | static · behavioural |
| `requirement-drift.sh` | `policy-register` | a vendored requirement spine that no longer matches the nist-csf artifacts | regeneration |
| `one-fact-per-flag.sh` | `business-context` | a profile flag that states two facts, or a battery gated on a flag that does not name its regime | static · mapping |
| `scope-withheld.sh` | `incident-materiality` | a statutory deadline computed for a perimeter nobody declared, or withheld without saying so | no-manufactured-date · no-silent-withholding |
| `nydfs-exemptions.sh` | `exceptions-register` | a stated NYDFS obligation with no §500.19 exemption beside it, or a qualification threshold printed without its determination caveat | stated · not-computed |
| `two-directional-limits.sh` | `incident-materiality` | a regulatory limit that scopes only outward, or DORA Art. 16 named beside reporting without what it actually disapplies | inward-stated · no-borrowed-limit |

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

Four layers, each catching what the one above cannot:

| Layer | Catches | Rule |
|---|---|---|
| Registry covers the tree | a guard nothing ever looked at | GP-1.8 |
| Proof file exists | a guard nothing ever mutated | GP-1.2 |
| Clean passes, mutated fails | a mutation that landed on nothing | GP-1.4 · GP-1.5 |
| Mutated fails exactly its named checks | a mutation that proved the *other* half | GP-1.9 |

The counts sit at the top of `prove-guards.sh` because a number asserted in code cannot drift
the way the sentence describing it can.

---

*A Cyber Aware Creation · Not affiliated with NIST.*
