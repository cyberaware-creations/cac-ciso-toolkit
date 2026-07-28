#!/usr/bin/env python3
"""Score a trigger-routing run.

    ./score-triggers.py prompts.tsv <output-dir>

Reads the `stream-json` transcripts written by run-triggers.sh and decides which skill
each prompt routed to.

Detection is by **`Skill` tool-use events**, not by reading the prose. That distinction
was learned the hard way: two runs of the same prompt produced answers that plainly came
from the same skill, but only one of them named it. The tool-use event is the ground
truth — the prose is a paraphrase of it.

Bash invocations of the skills' scripts are captured separately as corroboration. They
are not the verdict: a sandboxed run can route correctly and still never get permission
to execute anything.
"""
import json
import os
import re
import sys

SCRIPT_TO_SKILL = {
    "profile_analysis": "nist-csf",
    "csfa_compat": "nist-csf",
    "score_register": "risk-register",
}

# The skills this repo ships. Routing is a claim about THESE — whether a prompt
# reaches the right one of ours, or correctly reaches none of them.
#
# Anything else the operator happens to have installed is not a property of this
# repo, and must not decide a verdict. The 0.4.0 run failed X1 ("write us an
# acceptable use policy") because it reached `brainstorming`, a superpowers
# skill: the case was right that none of OUR skills should fire, and the scorer
# called it a failure anyway. A result that changes with the operator's plugin
# list is not measuring this repo.
OURS = ("nist-csf", "risk-register", "ciso-board-translation")


def parse_run(path):
    """Pull skills, corroborating scripts, cost and the final answer out of one transcript."""
    skills, scripts, cost, dur, result = [], [], None, 0, ""
    if not os.path.exists(path):
        return None
    for line in open(path):
        line = line.strip()
        if not line:
            continue
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        if ev.get("type") == "result":
            cost = ev.get("total_cost_usd")
            dur = ev.get("duration_ms") or 0
            result = ev.get("result") or ""
        content = (ev.get("message") or {}).get("content")
        if not isinstance(content, list):
            continue
        for blk in content:
            if not (isinstance(blk, dict) and blk.get("type") == "tool_use"):
                continue
            name, inp = blk.get("name"), blk.get("input") or {}
            if name == "Skill":
                # "cyber-aware-creations:nist-csf" -> "nist-csf"
                raw = inp.get("skill") or inp.get("command") or ""
                if raw:
                    skills.append(str(raw).split(":")[-1])
            elif name == "Bash":
                for m in re.findall(r"(profile_analysis|score_register|csfa_compat)\.py",
                                    inp.get("command", "")):
                    scripts.append(SCRIPT_TO_SKILL[m])
    return {"skills": skills, "scripts": sorted(set(scripts)),
            "cost": cost or 0.0, "dur_s": round(dur / 1000, 1), "result": result}


def verdict(expected, actual):
    """Does `actual` satisfy `expected`?

    `expected` is either the keyword `neither`, or one or more of OUR skill
    names separated by `|`. A pipe list is how a genuinely ambiguous prompt is
    written down: A4 ("what should I show the board about our security
    posture?") is answerable by nist-csf, risk-register OR
    ciso-board-translation, and the 0.4.0 run scored a defensible
    ciso-board-translation answer as a failure because the old `either` keyword
    silently meant just the first two.
    """
    if expected == "neither":
        return actual == "none"
    return actual in {e.strip() for e in expected.split("|")}


def _classify(path):
    """The routing decision for one transcript, as main() makes it."""
    run = parse_run(path)
    ours = [sk for sk in run["skills"] if sk in OURS]
    foreign = [sk for sk in run["skills"] if sk not in OURS]
    return (ours[0] if ours else "none"), foreign


def self_test():
    """Assert the scorer against hand-authored transcripts.

    This suite had none until the 0.4.0 run produced two failures that were both
    defects in the scoring rather than in the skills. A scorer making pass/fail
    claims with nothing verifying it is the same defect it exists to catch.
    """
    checks = []

    def eq(got, want, label):
        checks.append((got == want, label, got, want))

    fx = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "trigger")
    f = lambda n: os.path.join(fx, n)

    eq(_classify(f("ours.jsonl")), ("nist-csf", []),
       "a run that invokes one of ours reports it")
    eq(_classify(f("none.jsonl")), ("none", []),
       "a run that invokes nothing reports none")
    eq(_classify(f("board.jsonl")), ("ciso-board-translation", []),
       "ciso-board-translation is one of ours and is reported as such")

    # The X1 defect, reproduced.
    eq(_classify(f("foreign-only.jsonl")), ("none", ["brainstorming"]),
       "a run that reaches ONLY a non-toolkit skill reports none of ours, and "
       "names the foreign skill separately")
    eq(verdict("neither", _classify(f("foreign-only.jsonl"))[0]), True,
       "so `neither` PASSES when only a non-toolkit skill fired — the 0.4.0 X1 "
       "failure was the scorer's, not the skill's")

    # Order must not let a foreign skill win.
    eq(_classify(f("foreign-then-ours.jsonl")), ("risk-register", ["brainstorming"]),
       "a foreign skill firing FIRST does not displace ours in the verdict")

    # The A4 defect, reproduced.
    eq(verdict("nist-csf|risk-register|ciso-board-translation", "ciso-board-translation"),
       True, "a pipe list accepts every skill it names")
    eq(verdict("nist-csf|risk-register", "ciso-board-translation"), False,
       "and rejects one it does not — the widening is targeted, not a blanket pass")
    eq(verdict("nist-csf|risk-register", "nist-csf"), True,
       "a pipe list still accepts its first alternative")
    eq(verdict("nist-csf", "risk-register"), False,
       "a single expectation is still exact")
    eq(verdict("neither", "nist-csf"), False,
       "`neither` still fails when one of ours DOES fire — this is the case that "
       "catches over-triggering, and it must not have been loosened")

    # Every expectation in the shipped table is satisfiable.
    tsv = os.path.join(os.path.dirname(os.path.abspath(__file__)), "prompts.tsv")
    for line in open(tsv, encoding="utf-8"):
        if not line.strip():
            continue
        cid, exp, _ = line.rstrip("\n").split("\t")
        names = {e.strip() for e in exp.split("|")} if exp != "neither" else set()
        bad = names - set(OURS)
        eq(bad, set(), f"{cid} expects only skills this repo ships")

    for okflag, label, got, want in checks:
        if not okflag:
            print(f"FAIL: {label}\n  got:  {got!r}\n  want: {want!r}")
    passed = sum(1 for c in checks if c[0])
    print(f"score-triggers self-test: {passed}/{len(checks)} checks passed")
    return 0 if passed == len(checks) else 1


def main():
    if len(sys.argv) == 2 and sys.argv[1] == "self-test":
        return self_test()
    prompts_path, out = sys.argv[1], sys.argv[2]
    cases = [l.rstrip("\n").split("\t") for l in open(prompts_path) if l.strip()]

    total, rows, missing = 0.0, [], []
    for cid, expected, _prompt in cases:
        run = parse_run(os.path.join(out, "runs", f"{cid}.jsonl"))
        if run is None:
            missing.append(cid)
            continue
        total += run["cost"]
        ours = [sk for sk in run["skills"] if sk in OURS]
        foreign = [sk for sk in run["skills"] if sk not in OURS]
        actual = ours[0] if ours else "none"
        ok = verdict(expected, actual)
        extra = ours[1:]
        rows.append({"id": cid, "expected": expected, "actual": actual,
                     "also": extra, "foreign": foreign, "scripts": run["scripts"],
                     "pass": ok, "cost": run["cost"], "dur_s": run["dur_s"],
                     "answer": run["result"]})
        also = f"  (+{', '.join(extra)})" if extra else ""
        if foreign:
            also += f"  [non-toolkit: {', '.join(foreign)}]"
        print(f'{cid:>3} | expect {expected:<13} got {actual:<16} '
              f'{"PASS" if ok else "FAIL"}{also}  ${run["cost"]:.3f} {run["dur_s"]}s')

    if missing:
        print(f'\nNOT RUN: {", ".join(missing)}')
    passed = sum(1 for r in rows if r["pass"])
    print(f'\n{passed}/{len(rows)} passed   ${total:.2f} total')

    with open(os.path.join(out, "summary.json"), "w") as fh:
        json.dump(rows, fh, indent=1)
    print(f'Full transcripts and answers: {os.path.join(out, "summary.json")}')

    # Routing is machine-checkable; the ambiguous cases are not. Say so rather than
    # letting a green line imply the answer was read.
    if any(r["id"].startswith("A") for r in rows):
        print("\nNote: A1-A5 also carry behavioural requirements that this script does "
              "NOT check.\nRead their `answer` field against trigger-prompts.md before "
              "recording them as passed.")
    return 1 if (missing or passed != len(rows)) else 0


if __name__ == "__main__":
    sys.exit(main())
