# Board-Pack Skill Suite — Claude Code Handoff

**Target repo:** the `cyber-aware-creations` plugin (shipped **v0.6.0** — the bundle was written against v0.5.1)
**Date:** 2026-07-30

## What's in this bundle

| File | Role |
|---|---|
| `board-pack-suite-implementation-plan-2026-07-30.md` | **The execution plan.** Phased, task-by-task. Start here. |
| `metrics-register-skill-design-2026-07-30.md` | Design spec — #2 `metrics-register` |
| `exceptions-acceptances-skill-design-2026-07-30.md` | Design spec — #3 `exceptions-register` (standalone, rev b) |
| `incident-materiality-skill-design-2026-07-30.md` | Design spec — #4 `incident-materiality` |
| `board-pack-assembler-skill-design-2026-07-30.md` | Design spec — #1 `board-pack` |

**Filed 2026-07-30 (PR #19)** under the repo's existing convention, not the paths suggested below:
the plan and this handoff at `docs/superpowers/plans/2026-07-30-*`, the four specs at
`docs/superpowers/specs/2026-07-30-<skill>-design.md`. Content is unchanged from the bundle apart
from the version ladder.

## How to execute

1. ~~Drop these files into the repo~~ — done; see the paths above.
2. Open Claude Code in the repo.
3. Say: **"Execute the plan in `docs/superpowers/plans/2026-07-30-board-pack-suite-implementation-plan.md`."**

Superpowers (`superpowers:executing-plans`) runs it phase-by-phase with a checkpoint and a plugin version bump at each (**0.7.0 → 0.8.0 → 0.9.0 → 0.10.0** — shifted up one step because 0.6.0 shipped the `nist-csf` crosswalk lenses first; see the version note in the plan). Build order: Phase 0 (section contract) → A (`metrics-register`) → B (`exceptions-register`) → C (`incident-materiality`) → D (`board-pack`).

## Two gates (in the plan, resolved)

- **G1 — DORA-interview gate:** build the `exceptions-register` engine now; hold its marketing/positioning surface until the DORA-scoped interviews validate demand. (Interview guide lives in the project at `research/dora-acceptance-interview-guide-2026-07-30.md` — not needed for the code build.)
- **G2 — Contract sign-off:** confirm the `board.json` section-contract envelope (Phase 0 / T0.1) before retrofitting the two shipped consumers.

## Source-of-truth notes

- The strategy rationale behind these skills lives in the project's `research/feasibility-kill-report-2026-07-18.md` — not required to build, but it's why the guardrails (no confidence vocabulary, no catastrophizing, discoverability caveat, not-legal-advice) exist.
- Everything is additive: each new skill is its own dir; the only touch to shipped code is Phase 0's backward-compatible `contractVersion` stamp and #3's additive `export-acceptances` bridge in `risk-register`. Rollback = delete the new dirs / revert those two commits.
