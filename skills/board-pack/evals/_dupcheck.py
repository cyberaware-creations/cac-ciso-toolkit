#!/usr/bin/env python3
"""Assert the duplicate-escalation flag on an assembled pack. Used by assembly.sh.

Split into its own file rather than a heredoc inside the suite: the check needs to reason
over the warning text AND the escalation list together, and a nested heredoc inside a
command substitution is how a shell suite acquires a parse error nobody notices until it
silently stops running.
"""
import json
import sys

pack = json.load(open(sys.argv[1]))
notes = [w for w in pack["provenance"]["warnings"] if "linked to the same record" in w]
esc = pack.get("escalations") or []
problems = []

if len(notes) != 1:
    problems.append("expected exactly one duplicate-escalation warning, got %d" % len(notes))
else:
    for needle in ("R-010", "A-001", "risk", "exceptions", "not merged",
                   "disagree on severity"):
        if needle not in notes[0]:
            problems.append("the warning does not mention %r" % needle)

# Both entries must still stand. Flagging a duplicate and then dropping one would be the
# assembler deciding which clock-owner was right, which is the thing it must never do.
refs = sorted((e["section"], e["subjectRef"]) for e in esc
              if e["subjectRef"] in ("R-010", "A-001"))
if refs != [("exceptions", "A-001"), ("risk", "R-010")]:
    problems.append("both escalations must still stand; got %r" % (refs,))

# If the two producers ever agreed on severity this fixture would stop exercising the
# sharpest half of the warning, and would keep passing while proving less.
sev = {e["subjectRef"]: e["severity"] for e in esc
       if e["subjectRef"] in ("R-010", "A-001")}
if len(sev) == 2 and sev["R-010"] == sev["A-001"]:
    problems.append("the fixture no longer exercises the severity disagreement")

print("\n".join(problems))
