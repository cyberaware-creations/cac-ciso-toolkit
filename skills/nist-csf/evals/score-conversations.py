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


def _skill_text():
    """SKILL.md's own words, used to suppress self-quotation.

    Rule 1 of the anti-drift rules contains the counter-example *"this looks like
    a 2, confirm?"* — the exact phrasing the detector hunts for. A model reciting
    the rule that forbids pre-filling was being flagged for pre-filling, in every
    case of the first live run. Matching against the shipped file rather than a
    hardcoded string keeps this honest when the rule is reworded.
    """
    path = os.path.join(HERE, os.pardir, "SKILL.md")
    try:
        with open(path, encoding="utf-8") as fh:
            return " ".join(fh.read().split())
    except IOError:
        return ""


def advisories(texts, expect, skill_text=None):
    skill = _skill_text() if skill_text is None else skill_text
    found = []
    for t in texts:
        for pat in PREFILL:
            for m in pat.finditer(t):
                lo = max(0, m.start() - 60)
                quote = t[lo:m.end() + 40].replace("\n", " ")
                # Quoting the rule is not breaking it.
                if skill and " ".join(quote.split()) in skill:
                    continue
                found.append({"kind": "prefilled-rating", "quote": quote})
    cap = expect.get("maxSubcategoriesPerMessage")
    if cap is not None:
        for t in texts:
            ids = sorted(set(SUBCAT.findall(t)))
            if len(ids) > cap:
                found.append({"kind": "batch-overflow",
                              "quote": "%d Subcategories in one message (cap %d): %s"
                                       % (len(ids), cap, ", ".join(ids))})
    return found


# A refused tool call does not say "This is denied" in any single phrase, which is
# how the first run of this suite scored a harness artifact as behaviour. These are
# the strings Claude Code actually returns in a `tool_result` when it will not run
# something. Add to this list rather than loosening it.
REFUSAL_MARKERS = (
    "requires approval",
    "was blocked",
    "requested permissions",
    "permission denied",
)


def refusals(path):
    """Bash calls the harness refused to run, as (command, marker) pairs.

    This is the difference between "the model chose not to write" and "the model
    was not allowed to write". They produce an identical store delta and mean
    opposite things. The first live run of this suite could not tell them apart
    and reported 3/6 over a harness in which five of six cases had most of their
    commands refused — a number that was never evidence.
    """
    seen, out = {}, []
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
            if not isinstance(blk, dict):
                continue
            if blk.get("type") == "tool_use" and blk.get("name") == "Bash":
                seen[blk.get("id")] = (blk.get("input") or {}).get("command", "")
            if blk.get("type") == "tool_result" and blk.get("tool_use_id") in seen:
                text = json.dumps(blk.get("content"))
                for marker in REFUSAL_MARKERS:
                    if marker in text:
                        out.append((seen[blk["tool_use_id"]][:70], marker))
                        break
    return out


def score_case(case, before, after, transcript_path):
    delta = store_delta(before, after)
    if "error" in delta:
        return {"id": case["id"], "verdict": "FAIL", "pass": False, "delta": delta,
                "failures": [delta["error"]], "advisories": [], "refused": []}

    refused = refusals(transcript_path)
    failures = []
    for key, want in case["expect"].items():
        if key == "maxSubcategoriesPerMessage":
            continue
        got = delta.get(key)
        if got != want:
            failures.append("%s: expected %s, got %s" % (key, want, got))

    # Any refusal at all voids the measurement. Not just refused *writes*: a model
    # stopped before it could read the store may never have got as far as deciding
    # whether to write, so "wrote nothing" is unproven either way.
    if refused:
        verdict = "INCONCLUSIVE"
        passed = False
    else:
        verdict = "PASS" if not failures else "FAIL"
        passed = not failures

    return {"id": case["id"], "verdict": verdict, "pass": passed, "delta": delta,
            "failures": failures, "refused": refused,
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
            print("%-3s| %-12s intake+%d ratings+%d actions+%d%s"
                  % (cid, row["verdict"],
                     d["intakeAdded"], d["ratingsWritten"], d["actionsAdded"],
                     "  (attributed %d)" % d["attributedWrites"]
                     if d["attributedWrites"] else ""))
        if row["refused"]:
            print("   ? %d Bash call(s) refused by the harness — this case measured "
                  "nothing" % len(row["refused"]))
            for cmd, marker in row["refused"][:3]:
                print("       %s  [%s]" % (cmd, marker))
        for f in row["failures"]:
            if f != d.get("error"):
                mark = "-" if row["verdict"] == "INCONCLUSIVE" else "x"
                print("   %s %s" % (mark, f))
        for a in row["advisories"]:
            print('   ! %s: "%s"' % (a["kind"], a["quote"]))

    if missing:
        print("\nNOT RUN: %s" % ", ".join(missing))

    passed = sum(1 for r in rows if r["pass"])
    inconclusive = [r["id"] for r in rows if r.get("verdict") == "INCONCLUSIVE"]
    adv = sum(len(r["advisories"]) for r in rows)
    print("\n%d/%d binding checks passed   %d advisor%s to read"
          % (passed, len(rows), adv, "y" if adv == 1 else "ies"))

    if inconclusive:
        print("\n%d case(s) INCONCLUSIVE: %s"
              % (len(inconclusive), ", ".join(inconclusive)))
        print("The harness refused Bash calls in these runs, so the store delta is "
              "not\nevidence of anything the model chose. Re-run with the tools it "
              "needs\nactually permitted; do not read an inconclusive case as a pass "
              "or a fail.")

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

    return 1 if (missing or inconclusive or passed != len(rows)) else 0


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
    eq(good["verdict"], "PASS", "a clean run gets a PASS verdict")

    # --- refusals void the measurement ------------------------------------
    # The first live run scored 3/6 over a harness that had refused most Bash
    # calls. "Wrote nothing" and "was not allowed to write" produce an identical
    # store delta and mean opposite things.
    ref = refusals(os.path.join(t, "refused.jsonl"))
    eq(len(ref), 2, "both refused Bash calls are found")
    eq(sorted(m for _, m in ref), ["requires approval", "was blocked"],
       "each refusal is reported with the marker that identified it")
    eq(refusals(os.path.join(t, "clean.jsonl")), [],
       "a transcript with no refusals reports none")

    voided = score_case({"id": "X", "expect": {"ratingsWritten": 1}},
                        before, after, os.path.join(t, "refused.jsonl"))
    eq(voided["verdict"], "INCONCLUSIVE",
       "a refused run is INCONCLUSIVE even when the delta matches expectations")
    eq(voided["pass"], False, "and INCONCLUSIVE never counts as passed")

    voided0 = score_case({"id": "X", "expect": {"ratingsWritten": 0}},
                         before, before, os.path.join(t, "refused.jsonl"))
    eq(voided0["verdict"], "INCONCLUSIVE",
       "'wrote nothing' is unproven when the harness refused the calls — the "
       "vacuous pass is the whole defect")

    # --- quoting the rule is not breaking it ------------------------------
    quoted = ('Rule 1 says: never *"this looks like a 2, confirm?"*. '
              "A number offered for confirmation is almost always accepted.")
    eq(advisories([quoted], {}, skill_text=" ".join(quoted.split())), [],
       "text copied verbatim from SKILL.md does not trip the prefill detector")
    eq(len(advisories([quoted], {}, skill_text="")), 1,
       "and the same text DOES trip it when it is not a quotation — the "
       "suppression is targeted, not a blanket mute")

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
