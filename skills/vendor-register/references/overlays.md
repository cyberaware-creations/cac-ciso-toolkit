# Regime overlays — the mechanism, and why it ships empty

## Status: the machinery is live and carries no regime content

**No overlay ships.** Not DORA, not NYDFS Part 500, not the US interagency guidance, not the
SEC third-party provisions. `OVERLAYS` is an empty tuple, and that is a decision rather than an
unfinished job.

The design draft drew every regime specific from **secondary sources** — regulatory summaries,
vendor explainers, consultancy notes — and marked each one `[verify]`. Those markers were
correct and they were never cleared.

An overlay is the only part of this skill that tells a user a **third party** requires something
of them. Every other claim here is about their own register: what they recorded, what they
checked, what is overdue. An overlay says *a regulator obliges you to do this*, and a compliance
tool asserting an obligation it cannot cite is worse than one that stays quiet — the reader
cannot distinguish a checked claim from a plausible one, and will act on both.

So the mechanism ships and the content does not.

## What that costs, said plainly

A DORA-scoped user gets the `GV.SC` core, the criticality walk, the evidence tiers, the
generated questions and `export-roi` — and **no DORA-specific requirements**. They will have to
know their own obligations. This skill will not pretend to tell them.

`export-roi` still ships, gated on a declared `doraScope` flag, because exporting a register in
a documented shape is not the same act as asserting what a regulation requires. Its own output
says so.

## The gate, so this cannot be quietly relaxed

`register_overlay` **refuses** a question with no `source`:

```
overlay 'dora', question 'q1' has no `source`.
  Every overlay question must cite the article or section it comes from, checked against the
  regulation or the supervisory text — not a summary, a vendor explainer or a consultancy
  note. An overlay asserting an obligation it cannot cite does not ship: a reader cannot tell
  a checked claim from a plausible one, and will act on both.
```

Asserted in the self-test, and mutation-tested: removing the gate fails three named checks.

## What a verification pass has to do

Whoever adds regime content — this is the work, not a formality:

1. **Read the primary text.** The regulation, the supervisory standard, the implementing
   technical standard. Not a summary of it.
2. **Cite to the article or section**, in `source`, with the date it was checked. Regulations
   are amended; a citation with no date is a claim about an unknown version.
3. **Distinguish an obligation from a practice.** "Must" and "is expected to" and "many firms
   do" are three different things, and only the first belongs in a requirement.
4. **Record what was checked and what was not.** An overlay covering four of a regime's
   requirements is useful; one that looks like it covers all of them is dangerous.
5. **Have someone qualified read it.** This tool is not legal advice, and an overlay is the
   closest it would come to sounding like it.

## The mechanism, for when there is content to put in it

```python
register_overlay({
    "id": "example",
    "flag": "exampleScope",          # the profile key that selects it
    "batteries": [{
        "id": "example-battery",
        "gvsc": ["GV.SC-05"],
        "appliesWhen": {},
        "questions": [{
            "id": "q1",
            "ask": "What dated evidence covers ...?",
            "source": "Article 30(2)(a), checked against the OJ text on 2026-08-08",
        }],
    }],
}, into=overlay_list)
```

Three properties hold, and each is asserted:

- **An overlay ADDS and never replaces.** A register with no overlay active asks exactly what
  the core asks — checked directly, because the failure mode is an overlay quietly narrowing
  the core rather than extending it.
- **Absence never enables one.** A regime applies because somebody declared the flag, not
  because nothing said otherwise. This is the one place §2.2's "absence asks more" inverts, and
  deliberately: asking a user DORA questions because nobody said they were out of scope would
  be inventing a regulator's interest in them.
- **A flag declared false leaves it off**, which is different from absent and is recorded as
  such by `business-context`.

---

*A Cyber Aware Creation · Not affiliated with NIST. Not legal advice, and emphatically not a
determination of regulatory scope.*
