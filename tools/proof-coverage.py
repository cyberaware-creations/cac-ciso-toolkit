#!/usr/bin/env python3
"""CAC-GP-1.11 — how much of each guard has actually been demonstrated to fail?

`prove-guards.sh` asks *"did the check I nominated fail under mutation?"*. It never asks
*"is the nominated check one of the checks this guard runs, and what about the others?"* The
proof file was both the claim and the yardstick, so a guard running twenty checks and
registering one mutation reported the same `each proved in both directions` as a guard whose
every check is covered (BL-210).

This computes the two things the runner could not see.

  UNPUBLISHED — a `defeats` entry naming a string that never appears in the guard's clean run.
    Measured at 33 of 83 entries, 40%, across 15 of 36 guards. The cause is that suites print
    one label when a check passes and a different one when it fails:

        ok  "no shipped .py assigns a closed-state field on an exposure class"
        bad "no shipped .py assigns a closed-state field"

    GP-1.9 matches the mutated run, so the proof still worked — but the check had no stable
    identity, and a check nobody can name is a check nobody can count. Interpolating a value
    into the label (`ok "... ($out)"`) breaks it the same way and is worse, because the name
    then changes with the data.

  UNPROVED — a published check in no mutation's `defeats` and in no waiver.

A WAIVER is a decision on the record, not an exemption from having one. Most checks reasonably
carry one: an anti-vacuity assertion that a fixture was built is a precondition, not a guarded
property, and writing a mutation for it would prove only that the fixture still works. What a
waiver may not be is silent, or shared: `guard-registry.json` has 13 of 21 `not-a-guard` rows
carrying one byte-identical template reason, and that is what classification-by-boilerplate
looks like from the outside. So a reason repeated across guards is refused here.

Usage:  proof-coverage.py <labels-dir> <repo-root>

`labels-dir` holds one file per guard, named for its registry path with `/` as `__`, each
containing the check labels that guard published on its clean run, one per line.
"""
import json
import os
import sys

# A guard may waive checks it does not prove, in its own proof file:
#
#   "waived": {
#     "reason": "why THESE checks are not guarded properties, in this guard's own terms",
#     "checks": ["exact label", "exact label"]
#   }
#
# Listed exactly rather than by pattern, and that is the load-bearing part: a check added
# later is neither proved nor waived, so the run goes red and somebody decides. A glob would
# absorb it silently, which is the failure this whole standard exists to end.
MIN_REASON = 40


def _labels(path):
    with open(path, encoding="utf-8") as fh:
        return [l.rstrip("\n") for l in fh if l.strip()]


def _self_test():
    """The checker's own tests, because a checker nobody checked is the thing it forbids.

    Each case builds a throwaway repo — a registry, one guard's proof file, one labels file —
    and asserts the checker's verdict. Written after the checker had already reported a clean
    bill it should not have: an early version compared `defeats` against labels harvested with
    a regex that dropped the two-space prefix, so every entry looked unpublished at once.
    """
    import shutil, tempfile
    results = []

    def case(name, registry, proof, labels, want_rc, want_needle=""):
        root = tempfile.mkdtemp()
        try:
            os.makedirs(os.path.join(root, "tools"))
            with open(os.path.join(root, "tools/guard-registry.json"), "w") as fh:
                json.dump(registry, fh)
            gp = os.path.join(root, "skills/s/evals/guard-proofs")
            os.makedirs(gp)
            if proof is not None:
                with open(os.path.join(gp, "g.json"), "w") as fh:
                    json.dump(proof, fh)
            ld = tempfile.mkdtemp()
            with open(os.path.join(ld, "skills__s__evals__g.sh"), "w") as fh:
                fh.write("\n".join(labels))
            out, rc = _capture(ld, root)
            ok = (rc == want_rc) and (want_needle in out)
            results.append((ok, name, out.strip().split("\n")[-1][:90]))
        finally:
            shutil.rmtree(root, ignore_errors=True)

    REG = {"scripts": [{"path": "skills/s/evals/g.sh", "role": "guard"}]}
    mut = lambda d: {"mutations": [{"half": "h", "defeats": d}]}

    case("a fully proved guard is clean", REG, mut(["a", "b"]), ["a", "b"], 0, "COVERAGE 1 2 2 0")
    case("an unproved check is counted, not fatal", REG, mut(["a"]), ["a", "b"], 0,
         "COVERAGE 1 2 1 0")
    case("a defeats entry the clean run never publishes fails", REG, mut(["ghost"]),
         ["a", "b"], 1, "never publishes")
    case("a guard proving none of its own checks fails", REG, mut(["ghost"]), ["a"], 1,
         "not one of its 1 checks")
    p2 = mut(["a"]); p2["waived"] = {"reason": "x", "checks": ["b"]}
    case("a waiver with no usable reason fails", REG, p2, ["a", "b"], 1, "not one")
    p3 = mut(["a"]); p3["waived"] = {
        "reason": "these are fixture preconditions for this guard, not guarded properties",
        "checks": ["b"]}
    case("a waiver with a real reason is counted as waived", REG, p3, ["a", "b"], 0,
         "COVERAGE 1 2 1 1")
    p4 = mut(["a"]); p4["waived"] = {
        "reason": "these are fixture preconditions for this guard, not guarded properties",
        "checks": ["nope"]}
    case("a waiver naming a check that does not exist fails", REG, p4, ["a", "b"], 1,
         "which this guard does not run")

    for ok, name, tail in results:
        print("  %-4s %s" % ("ok" if ok else "FAIL", name))
        if not ok:
            print("       got: %s" % tail)
    bad = [r for r in results if not r[0]]
    print("proof-coverage self-test: %d/%d checks passed" % (len(results) - len(bad),
                                                             len(results)))
    return 1 if bad else 0


def _capture(labels_dir, repo):
    import io, contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = main(["proof-coverage.py", labels_dir, repo])
    return buf.getvalue(), rc


def main(argv):
    if "--self-test" in argv:
        return _self_test()
    if len(argv) != 3:
        print(__doc__.strip())
        return 2
    labels_dir, repo = argv[1], argv[2]

    reg = json.load(open(os.path.join(repo, "tools/guard-registry.json"), encoding="utf-8"))
    guards = [s["path"] for s in reg["scripts"] if s.get("role") == "guard"]

    problems, reasons_seen = [], {}
    total = proved_n = waived_n = 0
    for g in sorted(guards):
        skill, name = g.split("/")[1], os.path.basename(g)
        proof = os.path.join(repo, "skills", skill, "evals", "guard-proofs",
                             name[:-3] + ".json")
        lf = os.path.join(labels_dir, g.replace("/", "__"))
        if not os.path.exists(lf):
            # Not a failure here: the guard never reached a clean run, and prove-guards.sh has
            # already said so far more precisely than this could.
            continue
        published = _labels(lf)
        if not published:
            problems.append("%s: published no check labels on a clean run, so nothing here "
                            "can be counted. A guard whose checks cannot be named cannot be "
                            "shown to cover anything." % g)
            continue

        defeats, waived, reason = set(), set(), ""
        if os.path.exists(proof):
            doc = json.load(open(proof, encoding="utf-8"))
            for m in doc.get("mutations") or []:
                defeats |= set(m.get("defeats") or [])
            w = doc.get("waived") or {}
            reason = str(w.get("reason") or "").strip()
            waived = set(w.get("checks") or [])

        pub = set(published)

        # 1. Every `defeats` entry names a check the clean run published.
        for d in sorted(defeats - pub):
            problems.append(
                "%s: mutation defeats %r, which the clean run never publishes. Either the "
                "check prints a different label when it fails than when it passes, or the "
                "label carries interpolated data — and a check whose name changes cannot be "
                "counted, waived or found by the next reader." % (g, d))

        # 2. Every waived entry names a check that exists.
        for w0 in sorted(waived - pub):
            problems.append(
                "%s: waives %r, which this guard does not run. A waiver for a check that does "
                "not exist hides nothing and rots silently." % (g, w0))

        # 3. A guard that proves NOTHING is a hard failure. Everything else is counted.
        #
        # Mass-waiving the rest was the obvious move and it is the wrong one. Reading the 273
        # unproved checks, a real fraction are the guarded property itself — `ai-register`'s
        # "no decision renders as a raw Python dict — the defect this suite exists for" was
        # among them. A waiver on that is not a decision, it is the same false comfort in a
        # new wrapper, and it would read as settled. Classifying all 273 into needs-a-mutation
        # versus genuinely-a-precondition is real work and it is not this item's; what this
        # item owes is the NUMBER, made true and impossible to walk backwards from.
        #
        # So: unproved checks are counted and printed, never silently absorbed, and the total
        # is ratcheted by prove-guards.sh so it can only go up.
        if not (set(published) & defeats):
            problems.append(
                "%s: not one of its %d checks is defeated by any registered mutation. Whatever "
                "the proof file demonstrates, it is not this guard." % (g, len(published)))

        # 4. A waiver needs a reason, and the reason must be this guard's own.
        if waived and len(reason) < MIN_REASON:
            problems.append(
                "%s: waives %d check(s) with no usable reason. A waiver is a decision on the "
                "record; %r is not one." % (g, len(waived), reason))
        elif waived:
            twin = reasons_seen.get(reason)
            if twin:
                problems.append(
                    "%s: its waiver reason is byte-identical to %s. A reason shared between "
                    "guards is a template, and a template is what classification-by-"
                    "boilerplate looks like from the outside — say why THESE checks, in this "
                    "guard, are not guarded properties." % (g, twin))
            else:
                reasons_seen[reason] = g

        total += len(pub)
        proved_n += len(pub & defeats)
        waived_n += len(pub & waived)

    unproved = total - proved_n - waived_n
    pct = (100.0 * proved_n / total) if total else 0.0
    print("COVERAGE %d %d %d %d %.0f" % (len(guards), total, proved_n, waived_n, pct))
    for p in problems:
        print("PROBLEM %s" % p)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
