#!/usr/bin/env python3
"""Does every board sentence carry a consequence, and every decision end on a decision?

`board-safety.sh` has always checked for **absence** — no confidence vocabulary, no reworded
score, no percent-of-revenue derivation. It never checked for **presence**. A sidecar reading

    "Patch compliance fell to 88%."

passes every test in the suite. It names a thing, gives no consequence, and asks nothing. The
translation contract requires four elements of a board sentence — what is exposed, what it means
for us, the trend, and a decision — and two of those were guidance that nothing tested.

The shipped examples are strong because an author was careful, not because the toolkit insists.
That is exactly the class of property this repo elsewhere converts into a test.

**A floor, not a per-sentence gate.** This is a linguistic check on prose a human or a model
wrote, not a deterministic property of a store, so it will have false negatives: a well-written
sentence in unusual phrasing. Therefore

  * every `decisions[]` entry must pass — that one is unambiguous and there is no floor on it;
  * item sentences must clear a **share**, defaulting to 80%, and individual misses are warnings;
  * every failure NAMES the sentence it rejected, truncated, with its item id, so a false
    negative costs a ten-second read;
  * the vocabulary is data (`ciso-board-translation/references/consequence-vocabulary.json`) and
    extending it is the intended response.

**What it must never become: a style checker.** It tests that a required element is present. It
has no opinion about whether the prose is good.

Usage:
  _outcomescan.py <sidecar.json> [--vocab PATH] [--floor 0.8] [--json]
  _outcomescan.py --self-test
"""
from __future__ import annotations

import json
import os
import re
import sys

DEFAULT_FLOOR = 0.80

# Keys of the sidecar envelope. Everything else is an item map, which is how the assembler
# already treats it — so a producer adding a map gets checked without editing this file.
ENVELOPE = {"_comment", "section", "contractVersion", "generatedBy", "asOf",
            "executiveSummary", "decisions", "boundTo", "opportunities"}


def vocab_path() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.normpath(os.path.join(
        here, "..", "..", "ciso-board-translation", "references",
        "consequence-vocabulary.json"))


def load_vocab(path: str = "") -> dict:
    with open(path or vocab_path(), encoding="utf-8") as fh:
        v = json.load(fh)
    for key in ("connectives", "consequenceNouns", "decisionVerbs"):
        if not v.get(key):
            raise ValueError("the vocabulary is missing %r — an empty list would pass "
                             "everything and prove nothing" % key)
    return v


def _words(text: str):
    return re.findall(r"[a-z][a-z'\-]*", text.lower())


def has_consequence(text: str, vocab: dict) -> bool:
    """A connective AND a consequence noun. Either alone is not enough.

    `so` turns up in prose that concludes nothing; `revenue` turns up in sentences that merely
    mention it. Requiring both is what keeps this a presence test rather than a vibe.
    """
    low = " %s " % str(text or "").lower()
    if not any(c in low for c in vocab["connectives"]):
        return False
    words = set(_words(low))
    return any(n in words for n in vocab["consequenceNouns"])


def is_decision(text: str, vocab: dict) -> bool:
    """A leading decision verb, or an explicit `or` fork.

    The fork — *fund it, or record the board's acceptance* — is the house style and the
    strongest form, because it makes declining a minuted position rather than an absence. It is
    not required: an entry opening on `Note` or `Approve` is a decision too.
    """
    text = str(text or "").strip()
    if not text:
        return False
    first = (_words(text) or [""])[0]
    if first in {v.lower() for v in vocab["decisionVerbs"]}:
        return True
    low = " %s " % text.lower()
    return any(m in low for m in vocab.get("decisionForkMarkers") or [" or "])


def opportunity_words_in(text: str, vocab: dict):
    low = str(text or "").lower()
    return [w for w in (vocab.get("opportunityVocabulary") or {}).get("words") or []
            if w in low]


def item_maps(sidecar: dict) -> dict:
    return {k: v for k, v in sidecar.items()
            if k not in ENVELOPE and isinstance(v, dict)}


def check(sidecar: dict, vocab: dict, floor: float = DEFAULT_FLOOR) -> dict:
    """Everything the callers need, computed once.

    `failures` are hard: a decisions entry that is not a decision, or opportunity vocabulary
    inside a risk sentence. `warnings` are the per-item consequence misses, which fail the run
    only in aggregate, through the floor.
    """
    section = sidecar.get("section") or "(unnamed)"
    failures, warnings = [], []
    items_total = items_with = 0

    for map_name, mapping in sorted(item_maps(sidecar).items()):
        for item_id, text in sorted(mapping.items()):
            if not isinstance(text, str):
                continue
            items_total += 1
            if has_consequence(text, vocab):
                items_with += 1
            else:
                warnings.append("%s.%s.%s carries no consequence clause: %r"
                                % (section, map_name, item_id, text[:90]))
            # No blending, and this direction IS hard. An optimistic tail on a loss statement
            # reads as softening it, which is worse than either element alone.
            blended = opportunity_words_in(text, vocab)
            if blended:
                failures.append("%s.%s.%s blends opportunity into a risk sentence (%s): %r"
                                % (section, map_name, item_id, ", ".join(blended), text[:90]))

    decisions = sidecar.get("decisions") or []
    decisions_total = decisions_with = 0
    for entry in decisions:
        text = entry.get("text") if isinstance(entry, dict) else entry
        decisions_total += 1
        if is_decision(text, vocab):
            decisions_with += 1
        else:
            failures.append("%s decision does not end on a decision: %r"
                            % (section, str(text)[:90]))

    share = (items_with / items_total) if items_total else None
    # The floor is a SHARE, and at least one miss is always tolerated. That second clause is
    # not a fudge, it is the design: this check has acknowledged false negatives, and on a
    # four-item section an 80% floor is a 100% gate wearing a percentage. A gate is what the
    # design said this must not be — "a floor, not a per-sentence gate" — so a section small
    # enough that the share cannot express one allowed miss gets the one miss anyway.
    #
    # A section that misses TWO has a pattern rather than an unusual phrasing, which is the
    # thing worth failing on.
    allowed = max(1, int(round(items_total * (1 - floor)))) if items_total else 0
    missed = items_total - items_with
    if items_total and missed > allowed:
        failures.append("%s: %d of %d item sentences carry a consequence (%.0f%%); %d missed "
                        "and at most %d is tolerated at a %.0f%% floor"
                        % (section, items_with, items_total, (share or 0) * 100, missed,
                           allowed, floor * 100))
    return {"section": section, "itemsTotal": items_total, "itemsWithConsequence": items_with,
            "decisionsTotal": decisions_total, "decisionsWithDecision": decisions_with,
            "share": share, "floor": floor, "failures": failures, "warnings": warnings}


# --- self-test ----------------------------------------------------------------
#
# The five cases the design named, written before the checker was wired into anything.

def self_test() -> int:
    vocab = load_vocab()
    passed, failed = 0, []

    def ok(cond, label):
        nonlocal passed
        if cond:
            passed += 1
        else:
            failed.append(label)

    ok(not has_consequence("Patch compliance fell to 88%.", vocab),
       "a bare figure carries no consequence")
    shipped = ("A day of lost output is roughly a week of aftermarket margin, and the exit "
               "strategy has been written but never exercised — so the plan to leave is a "
               "document, not a demonstrated capability.")
    ok(has_consequence(shipped, vocab), "the shipped worked sentence carries one")
    ok(not is_decision("We should look at this.", vocab), "a wish is not a decision")
    fork = ("Fund a tested failover for the plant historian, or record the board's acceptance "
            "that the group's single production dependency has an untested exit for a further "
            "year.")
    ok(is_decision(fork, vocab), "the shipped fork decision passes")
    empty = check({"section": "empty"}, vocab)
    ok(empty["itemsTotal"] == 0 and empty["share"] is None and not empty["failures"],
       "an empty section reports zero totals and does not divide by zero")

    # Two more the design implies and the plan tests separately.
    ok(has_consequence("Ninety per cent, so the obligation is met.", vocab)
       and not has_consequence("Ninety per cent, so it improved.", vocab),
       "a connective alone is not enough — the noun has to be there too")
    blended = check({"section": "risk", "risks": {
        "R-1": "Exposure rose to critical, which matters because the renewal is at risk, "
               "and this also unlocks faster onboarding."}}, vocab)
    ok(any("blends opportunity" in f for f in blended["failures"]),
       "an optimistic tail on a risk sentence is a hard failure")

    print("_outcomescan self-test: %d/%d checks passed" % (passed, passed + len(failed)))
    for f in failed:
        print("  FAIL  %s" % f)
    return 1 if failed else 0


def main(argv) -> int:
    if "--self-test" in argv:
        return self_test()
    if not argv:
        print(__doc__, file=sys.stderr)
        return 2
    path = argv[0]
    vocab = load_vocab(argv[argv.index("--vocab") + 1] if "--vocab" in argv else "")
    floor = float(argv[argv.index("--floor") + 1]) if "--floor" in argv else DEFAULT_FLOOR
    with open(path, encoding="utf-8") as fh:
        result = check(json.load(fh), vocab, floor)
    if "--json" in argv:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print("%s: %d/%d item sentences carry a consequence; %d/%d decisions decide"
              % (result["section"], result["itemsWithConsequence"], result["itemsTotal"],
                 result["decisionsWithDecision"], result["decisionsTotal"]))
        for w in result["warnings"]:
            print("  warn  %s" % w, file=sys.stderr)
        for f in result["failures"]:
            print("  FAIL  %s" % f, file=sys.stderr)
    return 1 if result["failures"] else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
