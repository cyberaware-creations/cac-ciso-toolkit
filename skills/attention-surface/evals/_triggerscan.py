"""Every trigger the shipped producers can emit has a cluster, and an unknown one still shows.

A projection's characteristic failure is silence. If a producer emits a trigger this surface has
no mapping for, the wrong outcome is that it quietly does not appear — the CISO reads a list that
looks complete and is not, and nothing anywhere says otherwise.

Two properties, and both matter:

  **Mapped** — every trigger a shipped producer can emit is in `references/clusters.json`. Read
  out of the producers' own source, not out of a hand-kept list, because a hand-kept list is the
  thing that goes stale. New producer, new trigger, failing check.

  **Visible when unmapped** — the check above will eventually fail for a legitimate reason
  (somebody adds a trigger before mapping it), and on that day the surface must still show the
  item. That is what the `unclustered` group is for, and `clusters.sh` proves it separately.

Anti-vacuity: the scan asserts it found a plausible number of triggers. A regex that stopped
matching would otherwise report "every trigger is mapped" over an empty set.

Usage: _triggerscan.py <repo-root> <clusters.json>
"""

from __future__ import annotations

import json
import pathlib
import re
import sys

# The two shapes a producer uses to raise one. Both are matched, because both are in use:
# `vendor-register` and `ai-register` call a local `add("trigger", ...)` helper; the others
# build the dict inline with a `"trigger": "..."` key.
PATTERNS = (re.compile(r'\badd\(\s*"([a-z][a-z0-9-]+)"'),
            re.compile(r'"trigger":\s*"([a-z][a-z0-9-]+)"'))

# Below this, the scan has clearly stopped matching rather than found a small suite.
MINIMUM = 25


def triggers_in(repo: pathlib.Path):
    found = {}
    for path in sorted(repo.glob("skills/*/scripts/*.py")):
        skill = path.parts[-3]
        text = path.read_text(encoding="utf-8")
        for pattern in PATTERNS:
            for name in pattern.findall(text):
                found.setdefault(name, set()).add(skill)
    return found


def main(argv):
    if len(argv) != 3:
        print(__doc__, file=sys.stderr)
        return 2
    repo, clusters_path = pathlib.Path(argv[1]), pathlib.Path(argv[2])
    found = triggers_in(repo)
    if len(found) < MINIMUM:
        print("found only %d trigger(s) across the producers, expected at least %d — the scan "
              "stopped matching and this guard proved nothing" % (len(found), MINIMUM),
              file=sys.stderr)
        return 2
    data = json.loads(clusters_path.read_text(encoding="utf-8"))
    mapped = {t for c in (data.get("clusters") or []) for t in (c.get("triggers") or [])}
    missing = sorted(set(found) - mapped)
    print("scanned %d trigger(s) across %d producer(s); %d mapped"
          % (len(found), len({s for ss in found.values() for s in ss}), len(mapped)), flush=True)
    if missing:
        print("\n".join("%s (emitted by %s) has no cluster"
                        % (t, ", ".join(sorted(found[t]))) for t in missing), file=sys.stderr)
        print("\nAdd each to references/clusters.json. Until then it lands in the unclustered "
              "group, which is visible but is not a home.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
