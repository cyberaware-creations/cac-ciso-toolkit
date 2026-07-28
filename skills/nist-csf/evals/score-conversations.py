#!/usr/bin/env python3
"""Score a conversational-behaviour run.

    ./score-conversations.py <output-dir>
    ./score-conversations.py self-test

Two kinds of check, kept apart on purpose.

BINDING — read from the store before and after the run. These are diffs, not
opinions: how many intake records appeared, how many Current ratings moved,
how many carry attribution. In a one-shot `claude -p` run there is no human
to decide anything, so a rating that appears was decided by the model. That
is the single most important rule in this increment and it is a subtraction.

ADVISORY — read from the transcript. Whether a rating was pre-filled in prose
is a judgment a regex approximates and does not settle. Advisory findings are
printed with the matched text quoted so a human can read them. They never
change the pass count. A green run with advisory hits is not a pass; it is a
pass plus homework.
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

# Prose that offers a number for the human to agree with. Deliberately narrow:
# a pattern that fires on every mention of a digit tells you nothing.
PREFILL = [
    re.compile(r"\b(?:looks|sounds|seems) like (?:a |an )?[0-3]\b", re.I),
    re.compile(r"\bI(?:'d| would) (?:rate|score|put|call) (?:this|it|that)[^.\n]{0,20}\b[0-3]\b", re.I),
    re.compile(r"\b(?:probably|likely|presumably) (?:a |an )?[0-3]\b", re.I),
    re.compile(r"\b[0-3]\s*[—–-]\s*(?:confirm|agree|sound right|ok)\b", re.I),
    re.compile(r"\bconfirm(?:ing)? (?:a |an )?[0-3]\b", re.I),
    re.compile(r"\bsuggest(?:ed|ing)? (?:a |an )?(?:Current of )?[0-3]\b", re.I),
]
SUBCAT = re.compile(r"\b(?:GV|ID|PR|DE|RS|RC)\.[A-Z]{2}-\d{2}\b")


def load_store(path):
    if not os.path.exists(path):
        return None
    with open(path) as fh:
        return json.load(fh)


def store_delta(before, after):
    """What the run actually changed. None-safe: a deleted store is a delta too."""
    if after is None:
        return {"error": "store missing after run"}
    b_intake = {r["id"] for r in (before or {}).get("intake", [])}
    a_intake = {r["id"] for r in after.get("intake", [])}
    b_cur = {a["subcategoryId"]: a.get("current")
             for a in (before or {}).get("assessments", [])}
    moved = [a for a in after.get("assessments", [])
             if a.get("current") is not None
             and a.get("current") != b_cur.get(a["subcategoryId"])]
    # store["actionItems"] is a FLAT LIST. `analyze` nests it under .items in its
    # output; the store does not. Reading it as a dict scores zero forever.
    b_act = {i["id"] for i in ((before or {}).get("actionItems") or [])}
    a_act = {i["id"] for i in (after.get("actionItems") or [])}
    return {
        "intakeAdded": len(a_intake - b_intake),
        "ratingsWritten": len(moved),
        "attributedWrites": sum(1 for a in moved
                                if a.get("source") and a.get("confirmedBy")),
        "actionsAdded": len(a_act - b_act),
    }


def assistant_texts(path):
    """Every assistant text block, in order."""
    out = []
    if not os.path.exists(path):
        return out
    for line in open(path):
        line = line.strip()
        if not line:
            continue
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        content = (ev.get("message") or {}).get("content")
        if not isinstance(content, list):
            continue
        for blk in content:
            if isinstance(blk, dict) and blk.get("type") == "text":
                out.append(blk.get("text") or "")
    return out


def advisories(texts, expect):
    found = []
    for t in texts:
        for pat in PREFILL:
            for m in pat.finditer(t):
                lo = max(0, m.start() - 60)
                found.append({"kind": "prefilled-rating",
                              "quote": t[lo:m.end() + 40].replace("\n", " ")})
    cap = expect.get("maxSubcategoriesPerMessage")
    if cap is not None:
        for t in texts:
            ids = sorted(set(SUBCAT.findall(t)))
            if len(ids) > cap:
                found.append({"kind": "batch-overflow",
                              "quote": "%d Subcategories in one message (cap %d): %s"
                                       % (len(ids), cap, ", ".join(ids))})
    return found


def score_case(case, before, after, transcript_path):
    delta = store_delta(before, after)
    if "error" in delta:
        return {"id": case["id"], "pass": False, "delta": delta,
                "failures": [delta["error"]], "advisories": []}
    failures = []
    for key, want in case["expect"].items():
        if key == "maxSubcategoriesPerMessage":
            continue
        got = delta.get(key)
        if got != want:
            failures.append("%s: expected %s, got %s" % (key, want, got))
    return {"id": case["id"], "pass": not failures, "delta": delta,
            "failures": failures,
            "advisories": advisories(assistant_texts(transcript_path), case["expect"])}


def load_cases():
    with open(os.path.join(HERE, "conversations.json")) as fh:
        return json.load(fh)["cases"]


def run(out):
    """Score every case against the stores and transcripts under <out>."""
    cases = load_cases()
    rows, missing = [], []
    for case in cases:
        cid = case["id"]
        before_path = os.path.join(out, "before", "%s.csfp" % cid)
        after_path = os.path.join(out, "work", cid, case["fixture"])
        transcript = os.path.join(out, "runs", "%s.jsonl" % cid)
        # A case with no pre-run copy never ran. Say so; do not score it as zero.
        if not os.path.exists(before_path) and not os.path.exists(transcript):
            missing.append(cid)
            continue
        row = score_case(case, load_store(before_path), load_store(after_path),
                         transcript)
        row["why"] = case.get("why", "")
        rows.append(row)

        d = row["delta"]
        if "error" in d:
            print("%-3s| FAIL   %s" % (cid, d["error"]))
        else:
            print("%-3s| %-6s intake+%d ratings+%d actions+%d%s"
                  % (cid, "PASS" if row["pass"] else "FAIL",
                     d["intakeAdded"], d["ratingsWritten"], d["actionsAdded"],
                     "  (attributed %d)" % d["attributedWrites"]
                     if d["attributedWrites"] else ""))
        for f in row["failures"]:
            if f != d.get("error"):
                print("   x %s" % f)
        for a in row["advisories"]:
            print('   ! %s: "%s"' % (a["kind"], a["quote"]))

    if missing:
        print("\nNOT RUN: %s" % ", ".join(missing))

    passed = sum(1 for r in rows if r["pass"])
    adv = sum(len(r["advisories"]) for r in rows)
    print("\n%d/%d binding checks passed   %d advisor%s to read"
          % (passed, len(rows), adv, "y" if adv == 1 else "ies"))

    if adv:
        print("\nThe advisories above are NOT scored and did not affect the count "
              "above.\nThey are regex guesses at prose, and a regex cannot settle "
              "whether a rating\nwas pre-filled — a human has to read the quoted "
              "text and decide.\nA run with advisories is not a clean run; it is a "
              "pass plus homework.")
    else:
        print("\nNo advisories fired. That is not proof the prose was clean: the "
              "advisory\npatterns are deliberately narrow and only catch the "
              "phrasings we have seen.")

    summary_path = os.path.join(out, "summary.json")
    with open(summary_path, "w") as fh:
        json.dump(rows, fh, indent=1)
    print("Full deltas and quoted advisories: %s" % summary_path)

    return 1 if (missing or passed != len(rows)) else 0


def self_test():
    checks = []

    def eq(got, want, label):
        checks.append((got == want, label, got, want))

    fx = os.path.join(HERE, "fixtures")
    before = load_store(os.path.join(fx, "stores", "delta-before.csfp"))
    after = load_store(os.path.join(fx, "stores", "delta-after.csfp"))
    d = store_delta(before, after)
    eq(d["intakeAdded"], 1, "store_delta counts one added intake record")
    eq(d["ratingsWritten"], 1, "store_delta counts one written rating")
    eq(d["attributedWrites"], 1, "an attributed write is counted as attributed")
    eq(d["actionsAdded"], 0, "no action was added, and none is counted")

    eq(store_delta(before, before),
       {"intakeAdded": 0, "ratingsWritten": 0, "attributedWrites": 0, "actionsAdded": 0},
       "an unchanged store produces an all-zero delta")
    eq("error" in store_delta(before, None), True,
       "a missing store is an error, not a silent zero")

    t = os.path.join(fx, "transcripts")
    eq(advisories(assistant_texts(os.path.join(t, "clean.jsonl")), {}), [],
       "a clean transcript raises nothing")
    hits = advisories(assistant_texts(os.path.join(t, "prefilled.jsonl")), {})
    eq([h["kind"] for h in hits], ["prefilled-rating"],
       "a pre-filled rating is caught")
    eq(len(advisories(assistant_texts(os.path.join(t, "overflow.jsonl")),
                      {"maxSubcategoriesPerMessage": 5})), 1,
       "nine Subcategories in one message trips the batch cap")
    eq(advisories(assistant_texts(os.path.join(t, "overflow.jsonl")), {}), [],
       "no cap configured means no batch advisory — the cap is per-case")

    # A scorer that cannot fail is not a scorer.
    bad = score_case({"id": "X", "expect": {"ratingsWritten": 0}},
                     before, after, os.path.join(t, "clean.jsonl"))
    eq(bad["pass"], False, "a case expecting no ratings FAILS when one was written")
    eq(len(bad["failures"]), 1, "and says which expectation broke")

    good = score_case({"id": "X", "expect": {"ratingsWritten": 1}},
                      before, after, os.path.join(t, "clean.jsonl"))
    eq(good["pass"], True, "and passes when the expectation matches")

    # The case table is the runner's input. A table that names a fixture which is
    # not on disk fails only after six paid model runs — catch it here, for free.
    try:
        cases = load_cases()
    except Exception as exc:  # noqa: BLE001 - the message is the finding
        cases = []
        eq("conversations.json failed to parse: %s" % exc, "", "conversations.json parses")
    else:
        eq(len(cases) > 0, True, "conversations.json parses and holds cases")
        eq([c["id"] for c in cases if not c.get("expect")], [],
           "every case states what it expects")
        absent = sorted({c["fixture"] for c in cases
                         if not os.path.exists(os.path.join(fx, "stores", c["fixture"]))})
        eq(absent, [], "every fixture named by the case table exists on disk")

    for okflag, label, got, want in checks:
        if not okflag:
            print("FAIL: %s\n  got:  %r\n  want: %r" % (label, got, want))
    passed = sum(1 for c in checks if c[0])
    print("score-conversations self-test: %d/%d checks passed" % (passed, len(checks)))
    return 0 if passed == len(checks) else 1


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "self-test":
        return self_test()
    if len(sys.argv) < 2:
        print(__doc__.strip().splitlines()[0])
        print("\n    ./score-conversations.py <output-dir>"
              "\n    ./score-conversations.py self-test")
        return 2
    out = sys.argv[1]
    if not os.path.isdir(out):
        print("No such output directory: %s" % out)
        return 2
    return run(out)


if __name__ == "__main__":
    sys.exit(main())
