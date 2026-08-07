#!/usr/bin/env python3
"""The library's banding against the REAL engine. Used by graphics-contract.sh.

The library cannot import the engine — it is standard-library-only and ships
vendored into six skills — so its own self-test compares against a hand-written
mirror of `threshold_status`. A mirror is a second source of truth: it can drift
from the engine, and when it does, both sides stay green while the page shows a
chip and a bar that disagree.

This suite CAN import both, so it does. It is the only place the two real
implementations are ever compared.

Every threshold is probed at exactly its own value, not only either side of it.
The disagreement this was written after was `>=` against `>` on lower-better
metrics, which is invisible to any sampler that does not land on the boundary —
and the library's own sweep, 120 samples wide, never did.
"""
import pathlib
import sys

root = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(root / "tools"))
sys.path.insert(0, str(root / "skills" / "metrics-register" / "scripts"))
import cac_graphics as G          # noqa: E402
import metrics_analysis as M      # noqa: E402

STATUS_TO_SEV = {"ok": "good", "warn": "high", "critical": "critical"}

# Real shapes, including the two phrasings that read exactly on a boundary:
# "patch within 30 days" and "click rate under 5 percent".
CASES = [
    ("higher-better", {"target": 95.0, "warn": 90.0, "critical": 80.0}, 0, 100),
    ("higher-better", {"target": 99.0, "warn": 95.0, "critical": 90.0}, 0, 100),
    ("lower-better",  {"target": 2.0,  "warn": 5.0,  "critical": 10.0}, 0, 15),
    ("lower-better",  {"target": 15.0, "warn": 30.0, "critical": 60.0}, 0, 90),
    ("lower-better",  {"target": 4.0,  "warn": 8.0,  "critical": 12.0}, 0, 20),
    ("higher-better", {"warn": 90.0}, 0, 100),          # warn only
    ("lower-better",  {"critical": 12.0}, 0, 20),       # critical only
]

problems, samples, boundaries = [], 0, 0
for direction, thr, lo, hi in CASES:
    zones = G.zones_from_threshold(thr, direction)
    edges = [t for k, t in thr.items() if k != "target" and t is not None]
    probes = [lo + (hi - lo) * (i + 0.5) / 30 for i in range(30)]
    probes += [t + d for t in edges for d in (-1e-9, 0.0, 1e-9)]
    for v in sorted(set(probes)):
        samples += 1
        if v in edges:
            boundaries += 1
        want = STATUS_TO_SEV.get(M.threshold_status(v, thr, direction))
        got = G._zone_sev(v, zones, direction)
        if want is None:                 # no-reading / no-threshold: not banded
            continue
        if want != got:
            problems.append("%s %s at %g: engine %s, library %s"
                            % (direction, thr, v, want, got))

# Count what was compared. A parity check that silently stopped probing
# boundaries is exactly the failure this file exists to replace.
if boundaries < 2 * len([c for c in CASES if len(c[1]) > 1]):
    problems.append("only %d exact boundaries were probed; the sampler is not "
                    "landing on thresholds and this check proves nothing"
                    % boundaries)
if samples < 200:
    problems.append("only %d samples ran" % samples)

print("PASS %d samples, %d of them exact boundaries" % (samples, boundaries)
      if not problems else "FAIL " + "; ".join(problems[:3]))
