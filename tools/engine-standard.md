# CAC-EN-1 — the engine standard

**Applies to:** every `skills/*/scripts/*.py` a CISO runs from a terminal
**Implemented by:** `tools/check-twins.py` (the `load_context` twin), `tools/check-commands.py`
**In force since:** v0.82.0
**Sibling standards:** [CAC-LE-1](eval-lint-standard.md), the eval-harness lint ·
[CAC-GP-1](guard-proof-standard.md), the guard-proof standard ·
[CAC-TW-1](check-twins.py), which executes the duplicated functions against one another

---

## The problem, stated exactly

Eleven engines were written over four months, each borrowing from whichever sibling its author
happened to open. Nothing compared them, so the borrowings drifted — and the drift was never
in a place a self-test could see, because a self-test lives inside one skill and every one of
these is a claim about **all** of them.

Two examples, both found by executing the engines against one corpus rather than reading them:

- **Seven `--context` consumers, three different contracts.** One accepted a payload with no
  `contractVersion`; two accepted one with no decided `applicability`; five accepted a raw
  `.biz` store that CAC-AP-1 §2.6 says is the wrong transport. All seven crashed on a
  directory path, *identically* — so a member-to-member guard reported perfect agreement while
  every copy was wrong (BL-226).
- **Three engines returned exit code 2 on a refusal** while eight returned 1, and 2 is also
  what several of them return for a usage error. A well-formed refusal was indistinguishable
  from a mistyped command line to anything scripting the suite.

Neither is a bug in any one engine. Both are the absence of a stated convention, which is what
this file is.

---

## The standard

### EN-1.1 A refusal exits 1

**`1` is a refusal. `2` is a usage error. `0` is success.**

A refusal is the tool *working*: it read the input, understood it, and declined — a missing
`--why`, an unattributed confirmation, a payload it will not read. That is a different outcome
from "I could not parse your command line", and a caller scripting the suite has to be able to
tell them apart.

`2` remains argparse's usage-error code and is what these engines return when no subcommand is
given. Do not reuse it for a refusal.

Converged in v0.82.0: `ai-register`, `vendor-register` and `attention-surface` returned 2 from
their top-level `except Refusal` handler; the other eight returned 1. The item that raised it
(BL-218 Q1) named two of the three. **The third was found by measuring rather than by reading
the item** — which is the argument for this file existing at all.

### EN-1.2 A `--context` consumer holds the strict CAC-AP-1 contract

Every engine that accepts `--context` refuses, in this order, through its own refusal channel:

| input | refuse because |
|---|---|
| a path that does not exist | `FileNotFoundError`, with the path |
| a **directory**, an unreadable file, a broken symlink | `OSError` after `FileNotFoundError` — `IsADirectoryError` is **not** a `FileNotFoundError`, and `--context .` is an ordinary typo |
| a file that is not JSON | the decode error, with line and column where the engine has them |
| anything that is not a JSON **object** | `[]` parses cleanly and then `.get` raises `AttributeError` one line later |
| a raw `.biz` store (`family == "business-context"`) | **naming `business_context.py export`** |
| `contractVersion` absent, or not `CAC-AP-1` | the engine reads one contract and says which |
| `applicability` not a decided object | the narrowing decision belongs to `business-context` and is not re-derived |

**Order is load-bearing in one place.** The `.biz` clause runs **before** the contract clause,
because a raw store carries no `contractVersion` and answering it with the generic contract
message throws away the one sentence that tells the reader what to run.

**A refusal names the fix.** `business_context.py export <file.biz> --out ctx.json` turns a
five-second correction into a five-second correction; a refusal that names no command turns it
into a support question.

**Nothing here is a load-time refusal of a store.** These are refusals of a *payload the user
passed on the command line*, which is a different thing from a register that already exists —
BL-169 D-1 still holds, and no skill fails hard because a store it wants to read is absent.

### EN-1.3 The convention is enforced by execution, never by review

`tools/check-twins.py` registers `load_context` as a `refusal` twin across all seven consumers
and runs every payload above through every copy, comparing each answer **against the stated
contract and against the other copies**. Both, because either alone passes a state the other
fails: agreement is not correctness — the directory crash was unanimous — and a contract with
no cross-check cannot see one copy drifting into a different *message* for the same verdict.

**A row enters that corpus when, and only when, the copies converge on it.** The three contract
rows above were deliberately held out of it while the engines disagreed, with the reason
written into the registry entry rather than the row silently missing. The corpus growing by
exactly what converged is how the convergence is checked rather than asserted.

---

## What this standard does not cover

**Flag names and their shapes.** `--why` on material changes, `--by` on anything a person
assigns: those are per-skill records requirements and each engine states its own.

**Command inventories.** `tools/check-commands.py` (CAC-CD-1) owns whether every command an
engine accepts is a command the docs name.

**Store schemas.** Each skill owns its own, and `references/schema.md` documents it.
