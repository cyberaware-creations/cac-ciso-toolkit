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
    if expected == "either":
        return actual in ("nist-csf", "risk-register")
    if expected == "neither":
        return actual == "none"
    return actual == expected


def main():
    prompts_path, out = sys.argv[1], sys.argv[2]
    cases = [l.rstrip("\n").split("\t") for l in open(prompts_path) if l.strip()]

    total, rows, missing = 0.0, [], []
    for cid, expected, _prompt in cases:
        run = parse_run(os.path.join(out, "runs", f"{cid}.jsonl"))
        if run is None:
            missing.append(cid)
            continue
        total += run["cost"]
        actual = run["skills"][0] if run["skills"] else "none"
        ok = verdict(expected, actual)
        extra = run["skills"][1:]
        rows.append({"id": cid, "expected": expected, "actual": actual,
                     "also": extra, "scripts": run["scripts"], "pass": ok,
                     "cost": run["cost"], "dur_s": run["dur_s"], "answer": run["result"]})
        also = f"  (+{', '.join(extra)})" if extra else ""
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
