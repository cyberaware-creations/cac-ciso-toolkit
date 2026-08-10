# CAC-AP-1 — the applicability contract

**Normative.** Written for **consumers**: a skill author implementing `--context` should need
only this file.

`business-context` owns the applicability profile. Every other skill reads it and narrows its
question set accordingly. This document is the whole of what a consumer must implement.

---

## §2.1 One profile, one owner

`business-context` owns the applicability profile. **No other skill writes it.** Every skill
may read it and **must operate without it** — the profile is an optimisation on the question
set, never a prerequisite.

## §2.2 Absence is not a negative

A missing profile, or a missing flag within one, means **not declared**. It never means *does
not apply*. A skill with no profile asks its full question set.

This clause exists because the inverse is the dangerous default: silently narrowing scope on
absent data produces an assessment that looks complete and isn't — the same failure class as a
flat translations map rendering a finished-looking deck full of placeholders.

**In code, this means `None` and `False` are distinguished explicitly and never by
truthiness:**

| Profile state | Meaning | Behaviour |
|---|---|---|
| flag absent | not declared | **ask** |
| `{"value": null}` | not declared | **ask** |
| `{"value": false}` | declared, does not apply | **skip**, with a reason |
| `{"value": true}` | declared, applies | **ask** |

`if not declared:` passes every other test you will write and fails only this one. It is the
single change that silently narrows every assessment in the suite, with nothing on any
rendered page to show it happened.

## §2.3 A skill may narrow, never answer — and the subject outranks the profile

The profile removes questions that cannot apply. **It never supplies an answer** on the
subject's behalf.

Where a subject-level declaration contradicts the org-level profile, **the subject wins.** An
org that has declared no AI in use still gets the full AI battery on a vendor whose record says
it processes data with a model.

The override runs in **both directions**: a subject declaration may re-add a battery the
profile removed *and* remove one the profile kept. A subject that declares nothing (`null`)
does not override — the profile still decides.

The profile's job is to keep the default question set proportionate, not to overrule the
assessor standing in front of the evidence.

## §2.4 Every conditional is declared and visible

When a skill omits a battery because the profile said it did not apply, it **records that it
skipped it, and why** — carried into the artifact, not swallowed.

> *SEC Item 1.05 disclosure window — not assessed. Organisation profile:
> `secItem105Scope: false`, declared 2026-03-02 by General Counsel — no class of securities
> registered under the Exchange Act and no s.15(d) reporting obligation.*

An auditor cannot otherwise distinguish a question that was correctly out of scope from one
nobody asked, and those are very different findings. This mirrors the provenance page
`board-pack` already writes for missing sections.

The skip record carries everything the sentence needs:

```json
{"battery": "sec-item-105", "label": "SEC Item 1.05 disclosure window",
 "flag": "secItem105Scope", "source": "profile",
 "declaredBy": "General Counsel", "declaredOn": "2026-03-02", "basis": "..."}
```

`source` is `profile` or `subject`. A skip attributed to the wrong one tells an auditor the
subject declined a question the subject never mentioned.

**The gate must be the flag that names the regime.** `sec-item-105` is gated on
`secItem105Scope` — an Exchange Act reporting obligation, declared by counsel — and NOT on
`listedEntity`, which states only that shares trade somewhere. Those are different facts in
both directions: an unlisted US issuer reporting under s.15(d) is inside the Item 1.05
perimeter, and plenty of listed companies are outside it. Gating a statutory deadline on the
neighbouring fact is BL-175, and `one-fact-per-flag.sh` fails the build on it now — in both
directions, because the repo shipped a clean-looking definition on a battery gated by the
wrong flag for twelve releases.

### §2.4.1 An answered question and an unanswered one are not the same record

§2.2 says absence asks. What it did not say, until BL-175, is that the asking must **leave a
trace** — and the omission was not cosmetic.

A battery asked because somebody declared its gate true, and a battery asked because nobody
has declared it at all, arrived at the consumer as the same entry in the same `ask` list. For a
question set that costs a few minutes, they really are the same. For a **statutory filing
deadline** they are not: computing a four-business-day Form 8-K window for an organisation that
may owe no such filing manufactures a legal date, and a manufactured date gets acted on.

So `applies()` also returns `undeclared` — a **subset of `ask`**, never a third alternative to
it:

```json
{"battery": "sec-item-105", "label": "SEC Item 1.05 disclosure window",
 "flag": "secItem105Scope", "source": "absent",
 "declaredBy": "", "declaredOn": "", "basis": "",
 "sentence": "SEC Item 1.05 disclosure window — asked in full. Organisation profile: ..."}
```

`source` is `absent` where the flag was never entered, or `profile` where somebody entered it
with a null value — the second carries a declarer, a date and a basis, because *we do not know
yet, and here is who said so* is a different record from silence, and a reader chasing the gap
needs to know whether there is anyone to chase.

**The sentence never says "not assessed".** The battery *was* assessed. Per decision AP-2 a
reader must never have to work out whether a missing window means *nobody said* or *counsel
said no*, so the two sentences share no wording and, on a rendered page, no heading.

What a consumer does with the list is the consumer's own rule; this clause only guarantees the
list exists. `incident-materiality` withholds the deadline, renders the window as
`scope-not-declared` naming the flag, and escalates the missing declaration where the incident
is tracked against that regime — the withholding and the attention together, because either
alone fails in one of the two directions. A consumer with nothing to compute may ignore the
list; it changes no question set.

**Reading it is optional and its absence is not `true`.** A payload written before this clause
carries no `undeclared` key, and the honest reading of that is *the profile layer never said* —
so a consumer must treat the missing key as an empty list and compute exactly as it always did.
Reading it as "everything is undeclared" would withhold every deadline in the store the moment
one skill was upgraded ahead of another.

## §2.5 The profile is frozen by snapshot

A determination made in Q1 was made against Q1's profile. Skills that snapshot must **freeze
the profile values they used**, exactly as `risk-register` freezes `settings` per snapshot and
judges "it was over appetite then" by the appetite in force then.

The payload carries `profileVersion` for this purpose. It is always present — `unreviewed` when
the store has no snapshot — because a consumer freezing what it used needs something to name,
and "absent" is not a version a determination can cite a year later.

## §2.6 Transport is data, not imports

The suite forbids cross-skill imports; every shipped script runs standalone. The profile
therefore travels the way translations already do — an optional `--context <file.biz>` flag on
each consuming skill, read as data. **No skill imports another.**

---

## The payload

`business_context.py export <file.biz>` emits:

```json
{
  "contractVersion": "CAC-AP-1",
  "schemaVersion": 1,
  "orgName": "Northwind Manufacturing",
  "profileVersion": "FY26 close",
  "profileReviewedOn": "2026-08-07",
  "profile": { "secItem105Scope": {"value": false, "declaredBy": "...", "declaredOn": "...", "basis": "..."} },
  "applicability": {
    "incident": {
      "ask": ["dora-windows", "nydfs-notification"],
      "skipped": [{"battery": "sec-item-105", "label": "SEC Item 1.05 disclosure window",
                   "flag": "secItem105Scope", "source": "profile",
                   "declaredBy": "General Counsel", "declaredOn": "2026-03-02",
                   "basis": "No registered class and no s.15(d) obligation.",
                   "sentence": "SEC Item 1.05 disclosure window — not assessed. ..."}],
      "undeclared": [{"battery": "nydfs-notification", "label": "NYDFS Part 500 notification",
                      "flag": "nydfsScope", "source": "absent",
                      "declaredBy": "", "declaredOn": "", "basis": "",
                      "sentence": "NYDFS Part 500 notification — asked in full. ..."}]
    }
  },
  "revenue": {"exact": 412000000.0, "currency": "EUR", "fiscalYear": "FY26", "...": "..."},
  "crownJewels": [{"system": "...", "enables": "...", "atStake": "...",
                   "criticality": "high", "dependsOn": ["..."],
                   "sensitivity": {"value": "...", "declaredBy": "...",
                                   "declaredOn": "...", "basis": "..."}}]
}
```

**`applicability` carries the decision, not the raw material.** §2.2 is decided here, once, and
shipped — a consumer reads its own entry rather than re-deriving `None`-versus-`False` from
`profile`. That clause is the one where `if not declared:` reads correctly, passes every other
test anyone writes, and silently narrows every assessment in the suite; it exists in one place.
`profile` travels alongside it because a reader of the finished artifact needs to see what was
declared, not only what it implied.

Every skip record carries its own rendered **`sentence`** — the §2.4 text a consumer embeds
verbatim. A consumer that reassembles the sentence from the parts becomes a second author of it,
and the two versions drift the first time either changes.

**Revenue travels exact.** The consumer that needs it is a materiality financial factor, and a
banded denominator is not an honest one. Rendering it as a band is the renderer's job — see
`references/schema.md`.

**And it must never become a threshold.** Supplying the denominator must not smuggle a computed
verdict in through the back door: `incident-materiality` emits no verdict by design, precisely
because a generated number is discoverable alongside the determination it disagreed with. This
is enforced, not requested — see `evals/no-derived-materiality.sh`.

## Implementing `--context` in a consumer

1. Accept `--context <file>` as **optional**. Absent → your existing behaviour, unchanged. Make
   this structural: add your context keys only when a payload was supplied, so an un-narrowed
   run produces the same bytes it always did rather than the same bytes plus an empty field.
2. Read it as JSON. Do not import `business_context.py`. Refuse a payload whose
   `contractVersion` you do not read, and one carrying no `applicability` — a `--context` that
   cannot be honoured must say so, because a silent full question set looks exactly like a
   profile that decided nothing applied.
3. Read `applicability["<your skill>"]` for the profile's decision. **Do not re-derive it from
   `profile`** — §2.2 is decided upstream.
4. Apply §2.3 yourself, because only you hold the subject: a subject declaration overrides in
   both directions, and a subject declaring `null` overrides nothing.
5. Record every skip in your own artifact, per §2.4, embedding the record's `sentence` verbatim.
   A battery you do not implement is named rather than dropped, so a reader can tell a question
   belonging to another skill from one you forgot.
6. If you freeze anything — a snapshot, a determination — freeze `profileVersion` alongside your
   own frozen values, per §2.5.

Steps 3 and 4 are the whole split, and it is deliberate. §2.2 lives in exactly one place,
`business_context.applies()`, whose self-test is where it is pinned; a consumer re-implementing
it is a second source of truth and the two will disagree the first time either changes. §2.3
cannot live there, because the subject in front of the consumer has never been seen by the
profile.

The worked implementation is `incident-materiality` — `--context` on `analyze` and `determine`,
`declare-context` for the subject layer, and `evals/applicability.sh` for what a consumer's own
suite should assert.

---

*A Cyber Aware Creation · Not affiliated with NIST.*
