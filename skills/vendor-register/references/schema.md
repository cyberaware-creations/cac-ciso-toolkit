# `.vnd` schema

`schemaVersion: 1`, `family: "vendor-register"`. Plain JSON, written atomically.

**Validation guards writes, not reads.** A store carrying a bad value still opens: a register
that refuses to load because one field is wrong is a register nobody can fix. Every refusal
happens *before* the file is opened, so a refused command leaves it byte-identical — asserted in
the self-test rather than trusted.

## Top level

| Key | Holds |
|---|---|
| `meta` | `orgName`, `preparedBy`, `scopeNote`, `asOf` |
| `settings` | The scale, its version, cadences, staleness windows, trace depth, optional `consolidation` |
| `vendors` | The legal providers |
| `arrangements` | The agreements. This is the register |
| `history` | Append-only. Every mutation, with an actor and a rationale |
| `snapshots` | Frozen reviews — settings *and* every criticality block |

Settings are merged **per key** on load, so a store written before a setting existed gains it
rather than losing every setting it did have.

## `vendor`

```json
{"id": "V-001", "name": "Contoso Cloud", "jurisdiction": "IE",
 "groupParent": "", "identifiers": {}, "designations": []}
```

`designations` are **declared**, never bundled. No regulatory list drives engine behaviour: a
register whose behaviour changed when somebody refreshed a bundled file would be unauditable.

## `arrangement`

```json
{"id": "VA-001", "vendorRef": "V-001", "entityRef": "Northwind Manufacturing",
 "services": "production hosting for the plant historian",
 "supports": "SCADA gateway", "owner": "Head of Engineering",
 "startsOn": "2023-04-01", "endsOn": "", "cost": "",
 "gvsc": ["GV.SC-05", "GV.SC-10"], "sr": ["SR-6"],
 "subcontractors": [], "requirements": [], "assessments": [],
 "exit": {"documentedOn": "2024-02-10", "testedOn": "", "note": "..."},
 "criticality": { ... }, "retired": null, "priorArrangementRef": ""}
```

Ids are **`VA-###`**, not `A-###`. `board-pack` flags two sections asking the board about the
same record by regexing ids out of decision prose, and `exceptions-register` already mints
`A-001`; an arrangement and an acceptance sharing an id would reach the board as one ask
arriving twice.

**`supports` is the start of the criticality walk.** Without it the trace has nowhere to begin
and the arrangement derives `untraced` — which is correct, and loud.

**`exit` has two dates and they mean different things.** A written but never-exercised exit plan
is the sector's most common paper control; collapsing them into one boolean is what lets it pass.

**`retired` is terminal.** A resumed relationship opens a new arrangement carrying
`priorArrangementRef`. A successor pointing at a *live* arrangement is refused — two running at
once are two arrangements.

## The `criticality` block

Three fields, not one:

```json
{"derived": "high", "derivedOn": "2026-08-07",
 "trace": ["SCADA gateway", "Plant historian (Dublin)"],
 "truncated": false, "derivedFromLevel": "high", "layer": "system",
 "confirmed": {"value": "high", "by": "Head of Engineering", "on": "2026-08-07",
               "basis": "FY26 review; the historian stops both lines",
               "scaleVersion": "v1", "againstDerived": "high"}}
```

| Field | Means |
|---|---|
| `derived` | What the walk reached, or `untraced` |
| `trace` | The path it walked, in order |
| `truncated` | There was more chain than the hop budget allowed |
| `confirmed` | What a **named person** assigned. `null` until they do |
| `scaleVersion` | The scale that level was assigned under |
| `againstDerived` | What the walk said *at the time of confirmation*, so a workflow that later became more critical re-opens the question instead of hiding behind a stale sign-off |

`untraced` and `unclassified` are **states, not levels**. Neither may be a member of
`criticalityScale`, and `criticality_rank` raises on both. See `criticality-method.md`.

## Provenance

Declared fields use `{value, declaredBy, declaredOn, basis}` — the same shape
`business-context` uses. **The shape is reused; the module is not imported.** Every shipped
script runs standalone, and CAC-AP-1 §2.6 makes the transport between skills data rather than an
import.

A **bare** value loads and is reported as unattributed rather than refused. A register that
rejects a hand-edited file is one people stop hand-editing, and then stop using.

## `--context`

An exported CAC-AP-1 payload, never a raw `.biz`. Passing a `.biz` is refused with the command
that produces a payload from it, because reading the store directly would put the narrowing
decision in the wrong skill.

With **no** context, every arrangement derives `untraced` and nothing is refused.

---

*A Cyber Aware Creation · Not affiliated with NIST. Not legal advice.*
