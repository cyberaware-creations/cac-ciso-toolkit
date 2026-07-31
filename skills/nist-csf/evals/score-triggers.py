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
OURS = ("nist-csf", "risk-register", "ciso-board-translation", "metrics-register",
        "exceptions-register", "incident-materiality")


def parse_run(path):
    """Pull skills, corroborating scripts, cost, the final answer and run health out of
    one transcript.

    `errored` matters as much as the routing. A run can hit the turn cap, die with
    `is_error: true` and produce zero assistant text, yet still have made its Skill call
    minutes earlier — routing is decided long before a run ends. Inferring the verdict
    from tool calls alone reported one such run as `A3 | expect nist-csf got nist-csf
    PASS $0.411 70.9s`: a cost, a duration, a green tick, and no answer at all. A3 is one
    of the cases carrying behavioural requirements, so what it silently counted toward
    "20/20 passed" was a run in which nothing could have been read.
    """
    skills, scripts, cost, dur, result = [], [], None, 0, ""
    errored, subtype = False, ""
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
            subtype = ev.get("subtype") or ""
            # A missing answer is an error even when the runner did not say so.
            errored = bool(ev.get("is_error")) or subtype not in ("", "success")
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
            "cost": cost or 0.0, "dur_s": round(dur / 1000, 1), "result": result,
            "errored": errored, "subtype": subtype, "answered": bool(result.strip())}


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


def mark(expected, run):
    """PASS / FAIL / ERROR for one run — the whole scoring decision, in one place.

    Factored out so the self-test can assert the decision itself rather than only the
    parsing beneath it. The 0.4.0 defect lived in main()'s inline logic, where no check
    could reach it: parse_run() could have reported `is_error` perfectly and the verdict
    would still have come out PASS.
    """
    actual = _decide(run)
    if run["errored"] or not run["answered"]:
        return "ERROR", actual
    return ("PASS" if verdict(expected, actual) else "FAIL"), actual


def _decide(run):
    """Which of ours the run reached, or 'none'."""
    ours = [sk for sk in run["skills"] if sk in OURS]
    return ours[0] if ours else "none"


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

    # The A3 defect, reproduced: a run that routed correctly and then died.
    err = parse_run(f("errored-max-turns.jsonl"))
    eq(_classify(f("errored-max-turns.jsonl"))[0], "nist-csf",
       "an errored run still shows where it routed — routing happens before the run dies")
    eq(verdict("nist-csf", "nist-csf"), True,
       "and by routing alone it would satisfy its expectation")
    eq((err["errored"], err["answered"]), (True, False),
       "but the transcript is marked errored and answerless, so it cannot be scored — "
       "the 0.4.0 A3 run was reported PASS with a cost, a duration and no answer at all")
    eq(err["subtype"], "error_max_turns", "the terminal subtype is carried for the report")
    eq(mark("nist-csf", err), ("ERROR", "nist-csf"),
       "and the scoring decision itself returns ERROR, not PASS — this is the check "
       "that reaches where the 0.4.0 defect actually lived")

    ok_run = parse_run(f("ours.jsonl"))
    eq((ok_run["errored"], ok_run["answered"]), (False, True),
       "a healthy run is not swept up by the same guard")
    eq(mark("nist-csf", ok_run), ("PASS", "nist-csf"),
       "and still scores normally")
    eq(mark("risk-register", ok_run), ("FAIL", "nist-csf"),
       "including scoring a genuine routing miss as FAIL, not ERROR")

    blank = parse_run(f("answerless.jsonl"))
    eq((blank["errored"], blank["answered"]), (False, False),
       "a run the runner called successful but which produced only whitespace is "
       "answerless too — is_error alone would have missed it")

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
        foreign = [sk for sk in run["skills"] if sk not in OURS]
        # An errored or answerless run is neither a pass nor a routing failure — it is a
        # run that did not happen. Scoring it either way makes a claim the transcript
        # does not support, so it gets its own state and is excluded from the total.
        mark_, actual = mark(expected, run)
        broken, ok = mark_ == "ERROR", mark_ == "PASS"
        extra = [sk for sk in run["skills"] if sk in OURS][1:]
        rows.append({"id": cid, "expected": expected, "actual": actual,
                     "also": extra, "foreign": foreign, "scripts": run["scripts"],
                     "pass": ok, "errored": broken,
                     "subtype": run["subtype"], "answered": run["answered"],
                     "cost": run["cost"], "dur_s": run["dur_s"],
                     "answer": run["result"]})
        also = f"  (+{', '.join(extra)})" if extra else ""
        if foreign:
            also += f"  [non-toolkit: {', '.join(foreign)}]"
        if broken:
            why = run["subtype"] or ("no answer" if not run["answered"] else "is_error")
            also += f"  [{why}; routed to {actual}, but nothing was produced to read]"
        print(f'{cid:>3} | expect {expected:<13} got {actual:<16} '
              f'{mark_}{also}  ${run["cost"]:.3f} {run["dur_s"]}s')

    if missing:
        print(f'\nNOT RUN: {", ".join(missing)}')
    errored = [r["id"] for r in rows if r["errored"]]
    scored = [r for r in rows if not r["errored"]]
    passed = sum(1 for r in scored if r["pass"])
    print(f'\n{passed}/{len(scored)} passed   ${total:.2f} total')
    if errored:
        print(f'ERRORED (not scored, re-run before quoting a total): {", ".join(errored)}')

    with open(os.path.join(out, "summary.json"), "w") as fh:
        json.dump(rows, fh, indent=1)
    print(f'Full transcripts and answers: {os.path.join(out, "summary.json")}')

    # Routing is machine-checkable; the ambiguous cases are not. Say so rather than
    # letting a green line imply the answer was read.
    if any(r["id"].startswith("A") for r in rows):
        print("\nNote: A1-A5 also carry behavioural requirements that this script does "
              "NOT check.\nRead their `answer` field against trigger-prompts.md before "
              "recording them as passed.")
    return 1 if (missing or errored or passed != len(scored)) else 0


if __name__ == "__main__":
    sys.exit(main())
