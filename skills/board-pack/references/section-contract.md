# The board section contract (`*.board.json`)

**`contractVersion: 1`** · Canonical definition. Every skill that produces a board section writes
this envelope; every skill that consumes one reads it. The `board-pack` assembler validates against
this file, so a producer that drifts from it fails assembly rather than quietly rendering wrong.

This is not a new format. It is the sidecar `ciso-board-translation` already produces and that
`risk-register` and `nist-csf` already consume via `--translations`, written down once and given a
version so producers and the assembler can evolve together.

## The envelope

```json
{
  "section": "risk" | "posture" | "metrics" | "exceptions" | "incident",
  "executiveSummary": "One paragraph, board language, carrying a trend.",
  "<itemsKey>": { "<id>": "One sentence about this item, in board language." },
  "decisions": ["Each ends on a decision — fund, accept, or decide.",
                {"text": "Or this shape, to declare an altitude.",
                 "altitude": "board" | "management"}],
  "asOf": "YYYY-MM-DD",
  "contractVersion": 1
}
```

Every key is optional on read. An absent key renders a marked placeholder; it never renders
invented content. That rule is older than this contract and outranks it.

## Per-section item keys

The item key is named for what the section is about, and the spelling is exact.

| `section` | item key(s) | producer |
|---|---|---|
| `risk` | `risks`, plus `themes` | `risk-register` |
| `posture` | `gaps` | `nist-csf` |
| `metrics` | `metrics` | `metrics-register` |
| `exceptions` | `acceptances` **and** `exceptions` | `exceptions-register` |
| `vendor` | `arrangements` | `vendor-register` |
| `ai` | `deployments` | `ai-register` |
| `incident` | `incidents` | `incident-materiality` |

`vendor` is keyed on **arrangements, not vendors**. The register is contract-centric: one
provider commonly holds several agreements at different criticalities — the same cloud
provider behind a critical production dependency and a marketing sandbox — and a
vendor-keyed section would force one line per company for facts that differ per agreement.

**`vendor` was added within `contractVersion: 1`, not by bumping it.** The addition is purely
additive: every sidecar ever written omits it and still validates, and a version bump would
refuse all of them to gain nothing. Same reasoning as `boundTo`.

**A pack with no `vendor` sidecar gains one provenance line, and that is a decision.** Adding
the section meant an existing pack started reporting *"the `'vendor'` section is not in this
pack"* — which broke a byte-identity check the implementation plan had listed, and the
difference was that single line: sections, decisions, headlines and escalations were all
unchanged.

The alternative was exempting `vendor` the way `incident` is exempted. That would have restored
byte-identity by making an entire board section **silently absent**, so a reader could not tell
*third parties were considered and there are none* from *nobody asked* — the CAC-AP-1 §2.2
failure wearing different clothes.

`incident` is exempt because a quarter with no incident is a normal quarter, and it carries its
own warning saying exactly that. Third-party risk is a board section in its own right, so its
absence reads like a missing `risk` or `posture` section, which is what it is.

Pinned by two checks in `evals/assembly.sh`: the note must be present on the shipped specimen,
and `incident` must remain the only exemption. Exempting `vendor` fails both.

**`ai` was added the same way, in v0.41.0, and takes the same answer.** Keyed on
`deployments`, not systems: risk lives in the deployment, so one model used to draft copy and
to screen applicants is two rows with different owners, different data and different exposure,
and a system-keyed section would force one sentence to cover both.

It is additive within `contractVersion: 1` on the `vendor` precedent, and a pack with no `ai`
sidecar gains one provenance line for the same reason. The argument is arguably stronger here:
most AI in a firm arrived without a procurement decision, so *we looked at what we run and
there is none* is a genuinely useful thing for a board to be told — and it is indistinguishable
from *nobody asked* unless the pack says which.

`ai` is ordered directly after `vendor` in both audiences. Dependencies first, then the newest
class of dependency: most AI arrives through a third party, so the third-party section is the
context the AI section is read against, and reversing them would have a board meet the models
before it meets who supplies them.

`exceptions` is the one section with two item maps, because an acceptance and an exception are
different objects with one lifecycle. A section may carry both, either, or neither.

### Deprecated: `subcategories`

`nist-csf` accepts `subcategories` as an alias for `gaps`. **`gaps` is canonical** — new producers
write `gaps`, and documentation, examples, and the assembler all use it. The alias keeps working on
read so that no sidecar written before this contract stops rendering; it is not removed, and it is
not to be extended to other sections. A validator may warn on it. It must not reject it.

## Rules carried over from the shipped sidecar

1. **The per-item map is nested.** `{"risks": {"R-001": "..."}}`, never a flat `{"R-001": "..."}`.
   A flat map is the dangerous failure: it parses, so the render "succeeds", and every narrative
   silently falls back to a placeholder while the deck looks finished. Both shipped loaders detect
   this shape and refuse with a message naming the fix; a new producer must do the same.
2. **One sentence per key**, in board language, about that item.
3. **`executiveSummary` is one paragraph** and carries a direction, not just a state.
4. **Each entry in `decisions[]` ends on a decision** — something to fund, accept, or decide.
   An entry is **either a string or `{"text", "altitude"}`**; see below.
5. **Placeholder beats fabrication.** A slot with no translation renders as visibly unfilled. No
   producer or consumer invents a sentence, a number, or a decision to complete a section.
6. **No confidence vocabulary** reaches a board-facing view. Age is distance from a chosen cadence;
   a decay rate is not derivable and is never named as one. Enforced by
   `risk-register/evals/board-safety.sh` checks 9 and 10, which every board-facing producer inherits.

## Decision altitude

A `decisions[]` entry may be a **bare string**, or an **object**:

```json
{"text": "Fund network segmentation, or record the board's acceptance.", "altitude": "board"}
{"text": "Name a control owner for GV.SC-01.", "altitude": "management"}
```

`altitude` is `"board"`, `"management"`, or **absent**. Anything else is refused rather than
defaulted — a silent default would re-file somebody's board decision without telling them.

**Absent means unclassified, not `"board"`.** An unclassified ask still renders in front of
the board, and the difference matters: the assembler is recording that nobody said, rather
than concluding that somebody did. Of the two ways to be wrong, a board reading an ask it
did not need costs a minute; a board decision quietly filed as a management action is a
decision nobody takes.

**The producer declares it. Nothing infers it.** Only the skill that raised the ask knows
whether it needs a board, and no amount of reading the sentence tells the assembler. This is
the vanity flag's rule applied to decisions: a human sets it, the engine reports it, and
nothing pattern-matches its way to a governance judgement.

**Merging.** Two sections wording one ask identically but filing it at different altitudes is
a disagreement between producers, not a conflict to resolve silently. The merged entry keeps
`"board"`.

**Why this is not a `contractVersion` bump.** The string form is unchanged and still means
exactly what it meant; the object form is an addition beside it, and a sidecar of bare
strings renders today exactly as it did before this existed. Bumping would have made every
v1 consumer refuse a v2 sidecar outright — a large break in exchange for a purely additive
capability. Worth knowing: **no producer loader reads `decisions`**, so the object form is
seen by the assembler alone.

## `contractVersion`

- **Absent means 1.** Every sidecar written before this contract existed is a valid v1 document, and
  consumers read it as one. This is why the retrofit is additive: nothing in the wild breaks.
- **A version a consumer does not know is refused, loudly.** A v2 sidecar handed to a v1 consumer
  must fail with a message naming the version, not render on a best-effort basis — a section that
  half-renders is worse than one that does not render, because only one of those gets noticed.
- **Bump it when the shape changes**, not when content conventions change. Adding an optional key is
  not a version bump; renaming an item key, changing nesting, or changing what an existing key means
  is.

## `section`

Names which section the document is. A consumer that expects one section and is handed another
refuses — passing `metrics.board.json` to the risk renderer is a mistake worth catching at the
seam rather than discovering in a board pack. Absent `section` is allowed for backward
compatibility and skips the check.

## Passthrough keys

`generatedBy` and any other key not named here are ignored by consumers and preserved by producers.
The contract does not own them. `ciso-board-translation` stamps `generatedBy`; nothing reads it.

## Where this is enforced

| Rule | Enforced by |
|---|---|
| nesting / flat-map refusal | both shipped loaders, at `--translations` load |
| unknown `contractVersion` | both shipped loaders |
| `section` mismatch | both shipped loaders |
| per-section item-key spelling | `board-pack` assembler (Phase D) |
| decision shape / unknown `altitude` | `board-pack` assembler, at sidecar validation |
| `asOf` alignment across sections | `board-pack` assembler (Phase D), as a surfaced warning |
| no confidence vocabulary | `board-safety.sh` checks 9 and 10 |

---

*A Cyber Aware Creation · Not affiliated with NIST.*
