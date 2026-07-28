# The Cyber AI Profile overlay — contract and caveats

An overlay applies emphasis from another published profile to the **same** 106 CSF
Subcategories. It adds none, introduces no second framework, and creates no second assessment
surface. `frameworkRef` stays `csf-2.0`.

**Enabling adds no assessment work.** The overlay reweights Subcategories you have already
rated, or have yet to rate, exactly as before. The reasonable assumption is the opposite, so
say it out loud when a user asks.

---

## The source, and what it is not

`references/cyber-ai-profile.json` carries the proposed priorities from **NIST IR 8596,
*Cybersecurity Framework Profile for Artificial Intelligence***.

| | |
|---|---|
| Stage | **Initial Preliminary Draft** |
| Published | 2025-12-16 |
| Comments closed | 2026-01-30 |
| Landing page | `https://csrc.nist.gov/pubs/ir/8596/iprd` |

An **initial public draft is expected during 2026** and will supersede this. The dataset is a
swappable file with its own version stamp; following a redraft costs a re-run of
`tools/extract_cyber_ai.py` and a version bump, not a re-transcription.

Four things must travel with any output derived from it:

1. **It is a preliminary draft.** Not final, not a standard, not a control set.
2. **NIST calls priority determination a subjective exercise**, based on field observation and
   subject-matter expertise, and states the level may be higher or lower for an individual
   organization based on environment, needs and risk tolerance.
3. **Priority indicates sequencing, not required maturity.** 1 = High (address most
   immediately given available resources), 2 = Moderate, 3 = Foundational. NIST is explicit
   that Foundational is **not** low priority and that priorities do not reflect difficulty of
   achievement.
4. **Any target-floor interpretation would be ours, not NIST's** — see "Why there is no floor
   mode" below.

The renderers put the dataset version and source status in both dashboard footers, and the
ordering disclosure next to the affected table. That is a contract, not a courtesy: a report
outlives the conversation that produced it.

---

## The three Focus Areas

Independently selectable, and the scoping conversation is three plain questions:

| Focus Area | Ask | Applies when |
|---|---|---|
| **Secure** | *Do you build or deploy AI systems?* | You have AI in your estate to protect |
| **Defend** | *Does your security programme use AI?* | You use AI in defence — this is the only area carrying "Sample Opportunities" |
| **Thwart** | — stated, not asked | **Always.** Attackers use AI against you whether or not you use any |

Saying the third out loud is what makes the overlay legible to a CISO who has banned internal
AI use. Their answer to the first two may be "no"; Thwart still applies.

```bash
python3 scripts/profile_analysis.py overlay list acme.csfp
python3 scripts/profile_analysis.py overlay enable acme.csfp --focus secure thwart
python3 scripts/profile_analysis.py overlay disable acme.csfp
```

Focus areas are **space-separated**. `--focus secure,thwart` is refused by name — the flag
parser does not split on commas, so a comma form would otherwise become one unrecognised area.

Enable and disable each append a `history` event. The change alters what every report says.

### Effective priority is the minimum

For a Subcategory, effective priority is the **lowest** (most urgent) proposed priority across
the *selected* areas. NIST's scale runs 1 = most urgent, so minimum means "the most urgent
selected area wins".

The property that matters: **deselecting a Focus Area can only relax, never tighten.** A CISO
who decides "we don't build AI systems, drop Secure" cannot accidentally make something look
more urgent than it was.

A Subcategory the dataset says nothing about resolves to **nothing at all** — never a default.
A default would let an absent entry participate in ordering as though the source had spoken
about it.

---

## The two modes

| Mode | Changes | Does not change |
|---|---|---|
| `advisory` | Annotates gap rows with effective priority and per-area detail; adds an overlay block to `analyze` | Anything computed, including row order |
| `reorder` *(default on enable)* | The order of the `gaps` table, and the playbook derived from its head | Any score, target, gap, coverage figure, or Tier |

**No mode changes a number.** `advisory` is asserted equal to the disabled run across
`coverage`, `completeness`, `tiers`, `attention`, `queue`, `evidence`, `playbook`, `tracked`,
`actionItems` and `framework`, plus every gap value *and* row order. `reorder` is asserted
equal on all of those except order.

`reorder` is the default because it is the honest use of a sequencing signal: it changes what
you work on first without asserting a maturity level the source does not claim.

The sort is two-pass and stable, so within a priority band the previous severity ordering is
preserved — `reorder` **refines** the existing order rather than replacing it. Subcategories
the dataset says nothing about sort after every ranked one.

---

## What the overlay deliberately does not touch

### `queue` and `elicit`

`reorder` reorders the **`gaps` table only**. It does not reorder the confirmation queue or
the cold-start elicitation questions. **This is a decision, not an omission.**

The queue answers *"what do I have material for?"* — an evidence question. The overlay has
nothing to say about which Subcategory somebody has already collected evidence on. And the
queue's cold-start band is ordered by `references/cold-start-rank.json`, which is **Cyber Aware
Creations' own editorial judgment**, informed by NIST SP 1300 and carrying its own record of
what informed it. Layering IR 8596 priority over it would put two editorial orderings in
silent competition, with no way for a reader to tell which produced a given row.

The same applies to `references/elicitation.json`.

### The executive shortfall list

The board view's "Where the biggest shortfalls are" renders `attention.largestGaps`, which
`analyze` computes fresh from severity. The overlay does **not** reorder it — "what is biggest"
and "what should I do first" are different questions, and the board view asks the first.

Because a reader who knows the overlay is on might reasonably assume otherwise, that section
says explicitly that it is ordered by gap size and points at where the AI-prioritized order
lives. See `dashboards.md` rule 9.

---

## Why there is no floor mode

An earlier design specified a third mode, `floor`, resolving
`effectiveTarget = max(csfTarget, aiFloor)` with proposed priority mapped 1→4, 2→3, 3→2.

It is not implemented, and `--mode floor` is refused with its reason rather than as an unknown
value — because anyone who read that design will type it.

**The mapping is off-scale.** The native achievement scale is **0–3**; the engine refuses a
target of 4:

```
error: --target 4 is outside the scale 0..3
```

**And worse than a clamp, the scale is per-Profile.** Native Profiles run 0–3; Profiles
converted from the web tool keep **0–4**, deliberately unrescaled, because
`scale-and-scoring.md` states there is no honest mapping between them — a "2" on one is not a
"2" on the other. A fixed priority-to-target table would therefore mean different things on
two Profiles that both load in this tool, silently.

`advisory` and `reorder` deliver the value without asserting a maturity claim on
preliminary-draft authority. If a floor is ever added, the shape is to **refuse it on
non-native scales** rather than to rescale.

---

## The store block

```json
"overlays": {
  "cyberAi": {
    "enabled": false,
    "focusAreas": [],
    "mode": "advisory",
    "datasetVersion": null
  }
}
```

Defaults are inert: an absent `overlays` block normalizes to disabled, no areas, `advisory`.
Note the asymmetry — normalization falls back to `advisory` (the mode that changes nothing)
while `overlay enable` defaults to `reorder` (the mode worth choosing). The safe fallback and
the useful choice are different questions, and a normalization bug should produce a Profile
that reports nothing rather than one that silently resequences a board's top five.

`datasetVersion` records which dataset produced the last analysis and is stamped into
snapshots, so a stored report always states which data produced it. A dataset swap is a file
replacement plus a version bump; Profiles stamped with an older version keep reporting that
version until re-analyzed.

## Regenerating the dataset

See `tools/README.md`. Verification method and results for the shipped dataset are in
`docs/superpowers/notes/2026-07-28-ir8596-dataset-verification.md` — 318 values cross-checked
against a second extraction library, plus six Subcategories read off rendered pages.
