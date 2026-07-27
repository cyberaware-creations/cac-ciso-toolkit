# Cyber Aware Creations — CISO Toolkit

A Claude plugin of composable, NIST-aligned skills for security leaders, by
**Cyber Aware Creations, LLC.** Not endorsed by or affiliated with NIST.

## Install

This repository is itself the plugin marketplace — `.claude-plugin/marketplace.json` is the
catalogue, so there is nothing to download by hand and no install step beyond pointing your agent at
it.

**Claude Code**

```
/plugin marketplace add cyberaware-creations/cac-ciso-toolkit
/plugin install cyber-aware-creations
```

**Codex**

```
codex plugin marketplace add cyberaware-creations/cac-ciso-toolkit
```

Then open **Plugins → Personal** and install it. The CLI and the desktop app read the same catalogue.

Nothing runs until you invoke a skill, and when one does run it runs locally against your own files
— see [Design principles](#design-principles). The only requirement is a Python 3.9+ interpreter you
already have; see [Requirements](#requirements).

## Skills

### `risk-register`
Build, score, and maintain a cybersecurity risk register that persists in a local `.rr` file and
tracks how risk changes over time. NISTIR 8286 event-statement risks, deterministic Likelihood ×
Impact scoring and banding (SP 800-30), risk-appetite flagging (CSF 2.0 GV.RM), an append-only change
log with rationale, named review snapshots, structured risk acceptance, and reporting — heat matrix,
themes, trend, and operational, executive, and printable board outputs.

- **Deterministic engine** — `scripts/score_register.py` is ported from the Limen Labs web tool and
  verified identical to it (`self-test` → 34/34 parity checks).
- **Tooled persistence** — every mutation (`add`, `set-score`, `accept`, `set-status`, `snapshot`,
  `export-csv`) appends a history event and writes a schema-valid file, so the audit trail is
  enforced by tooling, not by hand.
- **Renderers** — self-contained, brand-consistent HTML dashboards and a printable PDF board report.

### `nist-csf`
Assess and track your program against the **NIST CSF 2.0** as an Organizational Profile that persists
in a local `.csfp` file. Per-Subcategory Current and Target ratings on a 0–3 achievement scale,
deterministic gap analysis and risk-weighted prioritization, coverage rollups by Function and
Category, Tier characterization, an append-only history with rationale, named snapshots with a
"what changed" diff, and an owned action plan — reported to both the team and the board.

- **Bundled framework data** — the full CSF 2.0 Core (6 Functions / 22 Categories / 106
  Subcategories) with all 363 Implementation Examples and the Informative References, generated from
  the NIST CPRT catalog, plus verbatim Tier text from NIST CSWP 29.
- **Framework-neutral engine** — a framework is data, not code. CSF 2.0 is the first one loaded;
  ISO 27001 and CIS attach later as additional data plus crosswalks.
- **Feeds the register** — `export-gaps` emits the gap CSV that `risk-register` imports, so a
  framework gap becomes a scored, owned risk without retyping.
- **Tiers are rigor, never a maturity score.** NIST is explicit about this, and the skill enforces it.

### `ciso-board-translation`
The reusable "moat" skill. Turns a raw security fact — a metric, a risk, or a quarter of program
work — into board-ready language a director acts on, using the four-question method, a curated
board-question bank, and sourced regulatory receipts (Caremark, DORA RTS, SEC Item 106, NYDFS Part
500) with their honest limits kept intact. `risk-register` calls it for all board-facing output.

## Layout

```
.claude-plugin/plugin.json     plugin manifest
skills/
  risk-register/
    SKILL.md
    scripts/score_register.py  scoring + CSF import + persistence (stdlib only)
    renderers/                 render_dashboard / render_board / render_report
    references/                schema, history & review, dashboards, CSF import, fixtures
    assets/                    brand tokens, PDF report layout
    examples/                  worked v2 register
    evals/                     board-safety, python-compat, responsive suites
  nist-csf/
    SKILL.md
    scripts/profile_analysis.py  CSF Profile engine + persistence (stdlib only)
    renderers/                 render_operational / render_executive
    references/                CSF 2.0 Core data, schema, assessment & review, dashboards,
                               framework abstraction
    assets/                    brand tokens
    examples/                  worked example Profile
    evals/                     trigger-routing checklist
  ciso-board-translation/
    SKILL.md
    references/                four-questions, board-question bank, receipts, metric archetypes
```

## Requirements

**Python 3.9 or newer. Standard library only — no dependencies, no install step.**

3.9 is the floor because it is what macOS ships at `/usr/bin/python3`, which makes the floor free to
test on any Mac. Nothing here needs anything newer.

That floor is enforced, not asserted:

```bash
./skills/risk-register/evals/python-compat.sh            # compiles every shipped file on 3.9
PY=/usr/bin/python3 ./skills/risk-register/evals/board-safety.sh   # and runs the suite there
./skills/risk-register/evals/responsive.sh               # width + WCAG AA contrast, in a browser
```

Run all three before any release. `responsive.sh` is the one check that isn't stdlib-only — it
drives a headless Chrome over the DevTools protocol. Both of the things it measures are properties
of a *resolved layout*, not of the CSS text: how wide the page actually laid out, and what colour a
given piece of text actually ends up on once alpha fills, ancestor backgrounds and `opacity` have
composited. Reading the stylesheet cannot answer either, which is where four shipped defects hid —
a banner at 1.01:1, delta chips at 1.57:1, and two pages wider than the phone. It skips cleanly if
Chrome or node is absent. v0.1.4 shipped a syntax construct that is only legal from Python 3.12,
and every test passed because they all ran on 3.14 — on an older interpreter the module could not be
imported at all, so a whole dashboard was missing rather than degraded. Testing on the author's
interpreter proves nothing about the user's.

## Design principles

- **Local-only, structure not data.** Everything runs on the user's own machine against the risks
  they provide. Nothing is uploaded anywhere. Rendered dashboards link Google Fonts by default;
  pass `--offline` for artifacts that must make no outbound request at all.
- **Deterministic where it must be.** Scoring and banding are scripted, never eyeballed.
- **Composable.** Board language lives in one skill and is reused across the suite.

## Licence

Apache License 2.0 — see [LICENSE](LICENSE) and [NOTICE](NOTICE).

You may use, modify, and distribute this work, including commercially. If you redistribute it or a
derivative, **retain the `NOTICE` file and credit Cyber Aware Creations, LLC.**, and mark any files
you changed. Deliverables generated by these skills carry the footer *"A Cyber Aware Creation · Not
affiliated with NIST"* — keep it.

Copyright 2026 Cyber Aware Creations, LLC.

*Not legal advice. Regulatory receipts carry their stated limits; do not present them to a board as
legal advice.*
