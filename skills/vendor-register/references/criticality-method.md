# The criticality walk, as implemented

**Read this before changing anything in `derive_criticality`.** It records what was collapsed
and what was bounded, each with its reason, so a later reader can tell a deliberate
simplification from an oversight.

## Sourcing, stated plainly

The method follows **NISTIR 8179's Criticality Analysis Process Model** in *shape*: a bottom-up
trace from a component to the workflow it supports, reconciled and then assigned by a person.
The design record this was built from is `strategy/vendor-register-skill-design-2026-08-07.md`
(rev g), with its methodology companion.

**Neither document is in this repository**, and NISTIR 8179, NISTIR 8276 and SP 800-161r1 are
not bundled here the way the CSF Core and the 800-53 crosswalk are. So this file describes what
the code does and attributes the shape to 8179; it does not quote or paraphrase the publication,
and nothing here should be read as a citation you can rely on without checking the source. What
*is* verifiable from this repository is the `GV.SC` and `SR` mapping — see `scsrm-mapping.md`.

## Where each process lives

| Process | Home | Why |
|---|---|---|
| **A** — define the procedure | `vendor-register` settings | The scale and cadences, declared once |
| **B** — workflows and their baseline criticality | **`business-context`** crown jewels | It is a business judgement, and it belongs where business judgements live |
| **C / D** — systems and components | The arrangement | A third party supplies exactly the systems and components these ask about |
| **E** — reconcile and assign the final level | `vendor-register` | As derivation plus escalation where levels disagree |

## What was collapsed, and why

**C and D are one act with an optional `--layer`.** 8179 splits them by role; most
organisations have one person doing both. The layer is *kept* rather than dropped because
`SR-11` component authenticity only applies at the component layer, so the distinction still
carries information even where the roles do not.

**The twenty-one sub-processes are not run per arrangement.** Nobody runs them against two
hundred vendors, and Process E is a reconciliation *across* levels rather than a per-component
re-derivation. What is implemented is the trace and the reconciliation; the rest is the
procedure an organisation declares in `settings`.

## What was bounded, and why

**Two hops**: `arrangement → system/component → workflow`, which is C/D → B.

Beyond the bound the walk stops and records `truncated`. The rule that matters more than the
depth:

> A trace that cannot reach a workflow with a declared criticality yields **`untraced`**, never
> **`low`**.

This is CAC-AP-1 §2.2 applied to criticality. Absence must not read as unimportant, and an
arrangement nobody could trace is exactly the one worth looking at.

Three properties enforce it, and each is mutation-tested in the engine's self-test:

1. **`untraced` is not a member of the scale.** `set-scale` refuses to add it.
2. **`criticality_rank` raises on it** rather than returning a number. A single
   `sorted(key=rank)` placing it at the bottom would silently downgrade every untraceable
   arrangement, and the board table would look complete.
3. **A truncated walk returns `untraced` *and* `truncated`** — never one or the other. A
   confident level from an unfinished walk is the worst outcome available.

`untraced` is also distinct from `unclassified`. Nobody ran the walk, versus we ran it and could
not finish. The actions differ, so the triggers do.

## Cycles

The walk carries a `seen` set and stops on re-entry. A cycle reports `truncated`, because there
was more chain and we did not follow it — which is true, and is the honest reading.

## The scale is a setting

8179 declines to prescribe levels, so this does not either. `low, moderate, high` ships as the
default and `set-scale` replaces it. Two disciplines make that safe:

- **Existing values are never remapped.** Remapping would restate somebody's judgement in words
  they did not choose. A change that would orphan a confirmed level is refused, naming the
  arrangements, so re-confirming them is the human's deliberate act.
- **Every assigned value records its `scaleVersion`.** A level read a year later means nothing
  without the scale it was assigned under — the same discipline that lets `risk-register` judge
  "it was over appetite *then*" by the appetite in force then.

## Derivation proposes; a person assigns

`--confirm` without `--by` is refused. A confirmed level that *differs* from the derived one is
stored without complaint and escalates as `criticality-conflict` — Process E exists for
consistency across layers, so a disagreement is a finding rather than an error. The register
reports it and never resolves it: choosing a side would mean overruling either the trace or the
person who signed it, and that is not the tool's call.

## Not implemented, and named as such

A **measure-based** scale — time lost, cost to recover — is more useful than a ranking and is
much harder to default. It is not shipped, because no organisation should be handed one it did
not choose. `set-scale` will accept one as an ordered list of labels; what the register will not
do is invent the measure.

---

*A Cyber Aware Creation · Not affiliated with NIST. Not legal advice.*
