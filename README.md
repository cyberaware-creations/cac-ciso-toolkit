# Cyber Aware Creations — CISO Toolkit

A Claude plugin of composable, NIST-aligned skills for security leaders, by
**Cyber Aware Creations, LLC.** Not endorsed by or affiliated with NIST.

## Install

This repository is itself the plugin marketplace — `.claude-plugin/marketplace.json` for Claude and
`.agents/plugins/marketplace.json` for Codex, each pointing at the repository root as the plugin. So
there is nothing to download by hand and no install step beyond pointing your agent at it.

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

Eight skills, in three layers. **Six own data** — each is the system of record for one thing and
persists it in a local file: risks, a CSF Profile, metrics, accepted exceptions, incident
determinations, and the organisation's own business facts. **One owns language** —
`ciso-board-translation` holds the board-facing phrasing the others call rather than each inventing
its own. **One owns the deliverable** — `board-pack` assembles what the producers wrote into a
single document, and owns no data at all.

The seam is deliberate. A producer decides what is true, the translation skill decides how it is
said, and the assembler decides what order a board reads it in. No skill does two of those jobs, so
a fact has exactly one home and changing how something is phrased never edits a store.

`business-context` sits slightly apart from the other five producers: it supplies facts *to* them
rather than reporting on its own. It takes ownership of nothing that already has an owner —
`risk-register` still owns the appetite band, this owns the board sentence the band came from.

### `risk-register`
Build, score, and maintain a cybersecurity risk register that persists in a local `.rr` file and
tracks how risk changes over time. NISTIR 8286 event-statement risks, deterministic Likelihood ×
Impact scoring and banding (SP 800-30), risk-appetite flagging (CSF 2.0 GV.RM), an append-only change
log with rationale, named review snapshots, structured risk acceptance, and reporting — heat matrix,
themes, trend, and operational, executive, and printable board outputs.

- **Deterministic engine** — `scripts/score_register.py` is ported from the Cyber Aware Creations web tool and
  verified identical to it; `self-test` asserts the parity case by case and prints its own count.
- **Tooled persistence** — every mutation (`add`, `set-text`, `set-score`, `accept`, `confirm`,
  `set-status`, `add-theme`, `set-theme`, `snapshot`, `export-csv`) appends a history event and writes
  a schema-valid file, so the audit trail is enforced by tooling, not by hand. `confirm` is how
  "reviewed, and nothing changed" gets recorded without faking a score move.
- **Renderers** — self-contained, brand-consistent HTML dashboards and a printable PDF board report.

### `nist-csf`
Assess and track your program against the **NIST CSF 2.0** as an Organizational Profile that persists
in a local `.csfp` file. Per-Subcategory Current and Target ratings on a 0–3 achievement scale,
deterministic gap analysis and risk-weighted prioritization, coverage rollups by Function and
Category, Tier characterization, an append-only history with rationale, named snapshots with a
"what changed" diff, and an owned action plan — reported to both the team and the board.

**A Profile is built from fragments, not from one sitting.** Nobody rates 106 Subcategories in an
afternoon, and a Profile assembled that way is mostly guesses wearing a number. So the unit of record
is the **source** — a pen test, an audit finding, a vendor questionnaire, a hallway conversation —
recorded once with `intake add` and pointed at whatever Subcategories it speaks to. Ratings accrete
against that log as evidence arrives.

- **Nothing is confirmed anonymously.** Setting a Current rating requires `--source` and
  `--confirmed-by`. This is a hard refusal, not a warning: an unattributed rating is indistinguishable
  from someone's recollection six months later, and the whole point is to be able to tell.
- **Four evidence states, always shown together** — `confirmed`, `evidence-pending` (a source names
  it, nobody has rated it yet), `unrated`, `not-applicable`. Reporting a subset collapses
  evidence-pending into unrated, which erases the distinction the schema exists to draw.
- **`queue` answers "what do I ask next?"** — in three bands: Subcategories with evidence already
  recorded and no rating, then ratings due a second look, then a cold-start order for a Profile with
  nothing in it (37 Subcategories, our editorial judgment, informed by NIST SP 1300 — see
  `references/cold-start-rank.json`, which records what the research actually changed).
- **Cold start is nine questions, not 106.** `elicit` asks what a CISO can already answer — *"suppose
  a file server is encrypted tonight, talk me through what actually happens"* — each question
  resolving several Subcategories at once. One answer becomes one recorded source, never several
  ratings: gathering four Subcategories' worth of material in one question saves evidence
  collection, not the four decisions.
- **The scope guard measures coverage, not currency — and suppresses rather than caveats.** Below
  60% of in-scope Subcategories *assessed*, the headline coverage figure does not render at all. A
  percentage with a warning beside it is still a percentage, and people read the number. This binds
  *both* dashboards — otherwise the suppressed figure just reappears one document over. The 60%
  counts how much of the framework anyone has assessed; it says nothing about how old any rating is,
  and no threshold anywhere in this toolkit expires one. Age is governed entirely by the next bullet.
- **Ratings do not expire.** A rating is questioned when newer material is recorded against it, or
  when it carries no confirmation date to compare against — never because a timer ran out. Age is
  reported and the reader judges: a governance outcome and an asset inventory go stale at completely
  different rates, so the engine declines to pick a decay rate on your behalf. There *is* an
  `ageThresholdDays` (default 180), and it is reporting furniture: it counts how many ratings sit
  past it so the number can appear on a dashboard. It flags nothing, gates nothing, suppresses
  nothing, and changes no score. Age is reported in four bands derived from that same threshold `T` —
  `within` (≤ T/2), `approaching` (≤ T), `beyond` (≤ 2T), `wellBeyond` (> 2T) — with identical
  boundaries in all three skills that have a cadence to measure against: over CSF ratings here,
  over risk confirmations in `risk-register`, and over reading dates in `metrics-register`. They
  are **distance-from-cadence labels, not confidence labels**: age is derivable from stored data and
  confidence is not, so the engine reports how old a determination is and the reader judges what that
  means. An inverted check in `risk-register/evals/board-safety.sh` fails if confidence vocabulary
  ever reaches one of its board-facing views, so the claim stays unmade rather than merely un-typed.
- **Bundled framework data** — the full CSF 2.0 Core (6 Functions / 22 Categories / 106
  Subcategories) with all 363 Implementation Examples and the Informative References, generated from
  the NIST CPRT catalog, plus verbatim Tier text from NIST CSWP 29.
- **Framework-neutral engine** — a framework is data, not code. CSF 2.0 is the first one loaded;
  ISO 27001 and CIS attach later as additional data plus crosswalks.
- **Feeds the register** — `export-gaps` emits the gap CSV that `risk-register` imports, so a
  framework gap becomes a scored, owned risk without retyping.
- **Tiers are rigor, never a maturity score.** NIST is explicit about this, and the skill enforces it.
- **Cyber AI Profile overlay, off by default.** Applies NIST IR 8596's AI-relevant emphasis to
  the *same* 106 Subcategories — it adds none, and enabling it adds no assessment work. Three
  independently selectable Focus Areas (Secure / Defend / Thwart, the last applying whether or
  not you use AI at all). It annotates, and optionally resequences the gap table; **no mode
  changes a score, target, gap, coverage figure or Tier.** The source is a preliminary draft,
  so every artifact carrying its output states the dataset version and that status. There is
  deliberately no target-floor mode: the priority-to-target mapping is scale-dependent and
  would mean different things on a 0–3 and a 0–4 Profile.

Profiles written before v0.2.0 keep working: schema v1 is normalized to v2 in memory on load and
stamped on the next write. Their existing ratings carry no attribution — which is exactly what the
Profile now says about them, rather than quietly implying they were sourced.

### `metrics-register`
Maintain security metrics and KRIs as a trended record in a local `.mtr` file, so the same numbers
can be compared period over period instead of re-derived each quarter. Dated readings with their
source, deterministic direction-aware trend and threshold status, and the attention lists a metrics
review actually works from.

- **Direction is required at definition time** — `higher-better` or `lower-better`. Without it,
  "87% → 91%" is not an improvement, it is just a different number, and the engine refuses to
  guess from the metric's name. Every trend verdict in the skill is derived from that declaration.
- **Six attention lists, from the same data** — `breached`, `worsening`, `stale`, `unowned`,
  `untagged` and `vanity`. `unowned` is the one nobody asks for and everybody needs: a metric with
  no owner has no one to move it.
- **The vanity flag is declared, not inferred.** Whether a metric mostly flatters the programme is
  a judgment about what it is *for*, and no amount of reading its history reveals that. So a human
  sets it and the engine reports it, rather than guessing from a line that only goes up.
- **Archetypes are tagged here and explained elsewhere.** Each metric carries an archetype tag
  resolved against `ciso-board-translation` at render time. What an archetype *means*, and what
  trap it hides, is that skill's content and is deliberately not duplicated — ask this skill and
  it will hand you off.
- **Age bands, not expiry** — the same `within` / `approaching` / `beyond` / `wellBeyond` bands as
  the CSF Profile and the register, over reading dates here. Distance from cadence, never a
  confidence claim, and nothing expires on a timer.

### `exceptions-register`
The defensible record of what the organisation knowingly accepted — risk acceptances and control
exceptions with their compensating controls — persisted in a local `.exc` file, so an auditor, a
regulator or a board can be shown the basis, the approver, and whether the reasoning still holds.

- **Three things are non-negotiable, and their absence is a refusal.** No approver, no
  justification, or no re-validation date means the record is not written. Not a warning: an
  exception with no named approver is indistinguishable from a decision nobody made. The refusal
  is raised *before the file is opened*, so a rejected mutation leaves the store byte-identical.
- **Re-validation is an act, never a timer reset.** Extending an acceptance records who looked at
  it again and why. A register where dates advance without anyone re-deciding is the failure mode
  this skill exists to prevent.
- **Status is derived from the dates, never stored** — `current`, `due`, `overdue`, `expired`. A
  stored status is a second source of truth that goes wrong quietly.
- **Exports the evidence artifact, not a screenshot of one** — the active inventory as CSV or JSON,
  which is the form a DORA or NYDFS reviewer asks for.
- **Fed one-way from the register.** `risk-register`'s `export-acceptances` pushes accepted risks
  in; this skill owns the lifecycle from there, and the register does not duplicate it.

### `incident-materiality`
Structure and record a cybersecurity incident materiality determination, and run the disclosure
clocks that follow from it — the six factors the judgment turns on, each recorded with its
reasoning, the person, and the date, in a local `.inc` file.

- **It never emits a verdict. No score, no scale, no threshold.** This is the sharpest constraint
  in the toolkit and it is not squeamishness: materiality is a legal judgment made with counsel,
  and a generated number would be **discoverable alongside the determination it disagreed with**.
  A tool that quietly said "62% material" would hand a plaintiff the exhibit. So the skill
  structures the judgment, records who made it, and stops.
- **Three assessments that deliberately do not add up** — `bearing`, `no-bearing`, `unknown`.
  There is no arithmetic to do on them, which is the point: six factors do not sum to an answer.
- **The SEC clock runs from determination, not discovery.** Four business days from the
  determination date — so an incident still under assessment has *no window open yet*, which is
  the part most often misread. The obligation in the meantime is to determine "without
  unreasonable delay", which has no numeric threshold; the skill does not invent one.
- **DORA windows in clock hours** — initial at the earlier of classification + 4h and awareness +
  24h, intermediate 72h from the initial notification *as filed*, final one month from the
  intermediate. Clock hours, not business days, and each anchored to an act rather than a date.
- **Aggregation moves the discovery date backwards, not the deadline.** Treating related
  occurrences as one series bears on "without unreasonable delay"; it does not shorten the
  four-day window.
- Every view carries three standing blocks — not legal advice, no verdict is being offered, and
  the rule the clock is running under — because these outputs are read under exactly the
  conditions where a caveat gets separated from its number.

### `business-context`
The organisation's own facts, in a local `.biz` file — revenue base, crown jewels, board-voiced
risk tolerance, segments, strategic goals, contractual obligations — plus the **applicability
profile** (CAC-AP-1) that narrows what a consuming skill asks. The profile is a *contract*
skills implement one at a time: `risk-register`, `metrics-register`, `exceptions-register` and
`incident-materiality` read it today; `nist-csf` does not yet. A pack built from a profile names
on its provenance page which sections read it and which asked their full question set.

What a profile narrows is the **question set**, not the arithmetic. `incident-materiality` is the
one consumer that also suppresses computed rows, because a disclosure window is only owed by an
entity the regime covers. The registers score, trend and expire records identically either way —
so what a profile changes there is which completeness questions get asked, and none of them
answers those questions from data the store does not hold.

- **It fills the one gap the other skills left.** Each of them correctly refuses to invent the
  number it asks for: `risk-register` takes an appetite band, `metrics-register` takes thresholds,
  `incident-materiality` walks six factors and emits no verdict. What had nowhere to live was
  **why the declared number is that number** — an appetite of `medium` traced to nothing, a
  materiality assessment weighed against a revenue base that lived in someone's head.
- **Declares, never infers.** Being an EU entity does not set DORA scope; a lawyer decides that
  and this records what they decided. Every flag carries who declared it, when, and on what
  basis, and one that cannot say why is refused — because absence asks everything, so the only
  thing an unjustified flag can do is ask *less*.
- **Absence is not a negative (§2.2).** A missing profile, a missing flag, or a flag whose value
  is `null` means *not declared*, never *does not apply*. `None` and `False` are distinguished
  explicitly and never by truthiness. This is the clause that, got backwards, silently narrows
  every assessment in the suite while the output still looks complete.
- **The subject outranks the profile, in both directions (§2.3).** An org that declared no AI
  still gets the full AI battery on a vendor whose own record says it processes data with a
  model; a subject may equally remove a battery the profile kept. A subject that declares
  nothing overrides nothing.
- **Every skip is visible (§2.4).** A narrowed battery is recorded with its reason and rendered
  where the question would have been, because an auditor cannot otherwise tell a question that
  was correctly out of scope from one nobody asked.
- **Revenue stored exact, rendered as a band.** Exact because a materiality denominator must be
  honest; banded because the rendered artifact is what circulates. The band is derived at render
  from a fixed ladder and never stored, so it cannot drift from the figure it describes.
  `--render-revenue exact` overrides *and writes the override into the provenance line*.
- **No derived materiality, and it is enforced.** Holding a revenue figure creates an obvious
  temptation to compute a percent-of-revenue rule. There is none.
  `evals/no-derived-materiality.sh` walks the AST — following the figure through a local
  binding, not merely by name — and runs the guard against a deliberately poisoned copy, so it
  is known to work rather than assumed to.
- **One escalation, deliberately.** `profile-stale` is unlike every other escalation in the
  suite: it is not an exposure. A crossed band says something got worse; this says the lens every
  other skill looks through has not been checked.
- **`incident-materiality` is the worked consumer.** `--context` there is optional, and an absent
  one leaves that engine's output byte-identical to what it produced before the contract existed.
  Item 1.05 is asked only of a listed entity and the DORA windows only of a DORA-scoped one, and
  a determination made with a profile freezes the version it was made against.

The store is more sensitive than any register it feeds — it names what the business cannot lose
alongside what the business is worth, and `SKILL.md` opens with a handling note for that reason.

### `ciso-board-translation`
The reusable "moat" skill. Turns a raw security fact — a metric, a risk, or a quarter of program
work — into board-ready language a director acts on, using the four-question method, a curated
board-question bank, and sourced regulatory receipts (Caremark, DORA RTS, SEC Item 106, NYDFS Part
500) with their honest limits kept intact. Every board-facing sentence in the suite comes from here.

### `board-pack`
Assembles the quarterly board pack or audit-committee pack from the section objects the other
skills produce, and outputs it as a print-ready document and an editable PowerPoint deck.

- **It owns no data and computes nothing.** Every figure is read from the producing skill's own
  analysis rather than recomputed, and every sentence comes from `ciso-board-translation`. A slot
  with no translation renders a **visible placeholder**, never an invented line — a board pack is
  the one artifact where a plausible sentence is worse than an obvious hole.
- **A versioned section contract.** Each producer writes a `*.board.json` the assembler validates
  before reading; a section that does not meet the contract is reported, not guessed at.
- **The audience changes the reading order, never the facts.** The audit-committee pack leads with
  incidents and exceptions where the board pack leads with posture. Same content, same
  disclaimers — there is no franker version.
- **One decisions list, merged textually and never semantically.** Consolidating what the board is
  actually being asked to approve is the job no single producer can do. Where two sections raise
  asks naming the same record, that is *flagged for a human*, not silently merged.
- **A real `.pptx`, written with the standard library.** No dependency: the OPC container is
  written by hand from `zipfile` and structurally verified — every relationship resolves and every
  part has a content type. What that cannot check is how it *renders*, so the renderer says as
  much when it writes the deck: open it once before it goes to a board. Doing exactly that is what
  caught two slides sharing a title, which no structural check could see.
- **A provenance page records what was missing**, so a thin pack reads as thin rather than complete.

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
    evals/                     board-safety, confirmation-age, python-compat, responsive suites
  nist-csf/
    SKILL.md
    scripts/profile_analysis.py  CSF Profile engine + persistence (stdlib only)
    scripts/csfa_compat.py     web-tool .csfa import/export
    renderers/                 render_operational / render_executive
    references/                CSF 2.0 Core data, schema, assessment & review, dashboards,
                               scale & scoring, authored guidance, cold-start rank,
                               elicitation bank, Cyber AI overlay + dataset,
                               framework abstraction
    assets/                    brand tokens
    examples/                  worked Profiles (v1 and v2), worked .csfa + gap CSV
    evals/                     board-safety, crosswalk-e2e, trigger-routing and
                               conversational-behaviour suites
  metrics-register/
    SKILL.md
    scripts/metrics_analysis.py  metrics + KRI engine, trend and thresholds (stdlib only)
    renderers/                 render_operational / render_executive
    references/                schema, metrics method, archetype bridge
    examples/                  worked .mtr + its board translations
    evals/                     metric-trend, board-safety, trigger-routing suites
  exceptions-register/
    SKILL.md
    scripts/exceptions_register.py  acceptance + exception lifecycle (stdlib only)
    renderers/                 render_inventory / render_board
    references/                schema, exceptions method
    examples/                  worked .exc + its board translations
    evals/                     revalidation-lifecycle, board-safety, trigger-routing suites
  incident-materiality/
    SKILL.md
    scripts/incident_analysis.py  six factors + SEC and DORA disclosure clocks (stdlib only)
    renderers/                 render_worksheet / render_board
    references/                schema, materiality factors, disclosure clocks
    examples/                  worked .inc + its board translations
    evals/                     disclosure-clock, applicability, board-safety,
                               trigger-routing suites
  business-context/
    SKILL.md
    scripts/business_context.py  org facts + the applicability profile (stdlib only)
    renderers/render_context.py  the framing a board pack opens on
    references/                schema, the CAC-AP-1 applicability contract
    examples/                  worked .biz
    evals/                     no-derived-materiality, board-safety, trigger-routing suites
  ciso-board-translation/
    SKILL.md
    references/                four-questions, board-question bank, receipts, metric archetypes
  board-pack/
    SKILL.md
    scripts/assemble_pack.py   contract validation + assembly, owns no data (stdlib only)
    scripts/pptx_writer.py     OOXML/OPC writer built on zipfile — no dependency
    renderers/render_pack.py   print-ready HTML + the deck, from one content model
    references/                pack structure, the versioned section contract
    examples/                  worked manifest + assembled pack
    evals/                     assembly, section-contract, board-safety, trigger-routing suites
tools/                         build-time only, never shipped — regenerates the bundled
                               reference data from its published sources. See tools/README.md.
docs/superpowers/              implementation plans and verification notes
```

**Bundled reference data is reproducible, not just present.** The CSF 2.0 Core, the authored
guidance, and the Cyber AI Profile dataset are each regenerated by a script in `tools/` from a
named public source, so a NIST revision costs a re-run rather than a re-transcription. The
Core's provenance is a sha256 of its source spreadsheet, which is vendored alongside it — so
you can check that what ships is what was built.

## Requirements

**Python 3.9 or newer. Standard library only — no dependencies, no install step.**

3.9 is the floor because it is what macOS ships at `/usr/bin/python3`, which makes the floor free to
test on any Mac. Nothing here needs anything newer.

That floor is enforced, not asserted:

```bash
./skills/risk-register/evals/python-compat.sh            # compiles every shipped file on 3.9
PY=/usr/bin/python3 ./skills/risk-register/evals/board-safety.sh   # and runs the suite there
./skills/risk-register/evals/confirmation-age.sh         # age bands, the three outcomes, the board line
./skills/risk-register/evals/responsive.sh               # width + WCAG AA contrast, in a browser

python3 skills/risk-register/scripts/score_register.py self-test   # web-engine parity
python3 skills/nist-csf/scripts/profile_analysis.py self-test      # engine math vs a fixed fixture
python3 skills/nist-csf/scripts/csfa_compat.py self-test           # .csfa port + gaps-CSV parity
python3 skills/nist-csf/evals/score-conversations.py self-test     # the eval scorer's own tests
python3 skills/nist-csf/evals/score-triggers.py self-test         # routing scorer's own tests

python3 skills/metrics-register/scripts/metrics_analysis.py self-test      # trend + threshold math
python3 skills/exceptions-register/scripts/exceptions_register.py self-test  # lifecycle + refusals
python3 skills/incident-materiality/scripts/incident_analysis.py self-test   # clocks + banding
python3 skills/business-context/scripts/business_context.py self-test      # §2.2/§2.3 narrowing
python3 skills/board-pack/scripts/assemble_pack.py self-test               # contract + assembly

./skills/metrics-register/evals/metric-trend.sh          # direction-aware trend, end to end
./skills/exceptions-register/evals/revalidation-lifecycle.sh  # re-validation as an act, not a reset
./skills/incident-materiality/evals/disclosure-clock.sh  # SEC and DORA windows, and the band order
./skills/incident-materiality/evals/applicability.sh     # CAC-AP-1 across the file boundary
./skills/business-context/evals/no-derived-materiality.sh  # the guard, seen to fail on a poisoned copy
./skills/board-pack/evals/assembly.sh                    # ordering, merge, refusals, a sound .pptx
./skills/board-pack/evals/section-contract.sh            # the contract every producer writes to
./skills/board-pack/evals/deck-contrast.sh               # WCAG AA in the .pptx, from its own XML
./skills/board-pack/evals/deck-fit.sh                    # the deck holds what the pack put in it

./skills/nist-csf/evals/board-safety.sh                   # each of these six guards its own views
./skills/metrics-register/evals/board-safety.sh
./skills/exceptions-register/evals/board-safety.sh
./skills/incident-materiality/evals/board-safety.sh
./skills/business-context/evals/board-safety.sh
./skills/board-pack/evals/board-safety.sh

python3 tools/crosswalks/validate_crosswalks.py --self-test  # the crosswalk checker's own tests
./tools/check-versions.py                                # the four plugin version strings agree
./tools/check-versions.py --self-test                    # and the guard's own tests
./tools/check-versions.py --base main                    # ...and that a shipped change bumped them
```

Each prints its own count. Don't pin those counts in prose — three of them have already gone
stale here, and a number nobody maintains stops being true silently.

Run them from a **clone**, not from the installed plugin. `python-compat.sh` discovers files
through git and now exits 2 rather than reporting "all 0 shipped files compile" when it cannot
— which is what it did, and exited 0, for anyone who followed this instruction from
`~/.claude/plugins/`.

Run all of these before any release. `responsive.sh` is the one check that isn't stdlib-only — it
drives a headless Chrome over the DevTools protocol. Both of the things it measures are properties
of a *resolved layout*, not of the CSS text: how wide the page actually laid out, and what colour a
given piece of text actually ends up on once alpha fills, ancestor backgrounds and `opacity` have
composited. Reading the stylesheet cannot answer either, which is where four shipped defects hid —
a banner at 1.01:1, delta chips at 1.57:1, and two pages wider than the phone. It skips cleanly if
Chrome or node is absent. v0.1.4 shipped a syntax construct that is only legal from Python 3.12,
and every test passed because they all ran on 3.14 — on an older interpreter the module could not be
imported at all, so a whole dashboard was missing rather than degraded. Testing on the author's
interpreter proves nothing about the user's.

**The seven `board-safety.sh` suites are not copies of each other.** Each is *inverted*: it passes
only if forbidden language never reaches a rendered artifact, so the claim stays unmade rather than
merely un-typed. All seven reject confidence vocabulary attached to an age band. Four of them add a
catastrophizing guard, written after a shipped metrics example described an untested backup restore
as the difference between a bad week and "an existential event" — a sentence that was arguably
right about the stakes and wrong about this toolkit's job. `board-pack` adds the strictest check of
the set: every sentence the pack presents as board prose must appear **verbatim** in a producer's
translation sidecar. Not paraphrased, not trimmed, not joined. The assembler is not permitted to
improve the prose on its way past.

`nist-csf`'s suite additionally pins the two claims specific to a Profile. **A Tier is a considered
judgment and not a score** calculated from the ratings, which is the single easiest thing for a
board to misread off a dashboard. And **a withheld coverage figure stays withheld everywhere** —
both dashboards *and* stdout, because an agent reads what a renderer prints and repeats it, so a
number suppressed in the page and printed to the terminal has not been suppressed. That last
property was stated in a source comment and tested by nothing.

Two words are deliberately *not* banned. `severe`, `critical` and `major` are the frameworks' own
classification vocabulary, and banning them would ban the subject matter. And `trust` survives in
`nist-csf` because the evidence bar ends *"none of this says how much to trust a rating"* — banning
the word would ban the sentence that makes the refusal, so the suite pins that sentence instead.

## Design principles

- **Local-only, structure not data.** Everything runs on the user's own machine against the risks
  they provide. Nothing is uploaded anywhere. Rendered dashboards link Google Fonts by default;
  pass `--offline` for artifacts that must make no outbound request at all.
- **Deterministic where it must be.** Scoring and banding are scripted, never eyeballed.
- **Composable.** Board language lives in one skill and is reused across the suite. A fact has one
  home; the skill that owns it is the only one that writes it.
- **Derived, never stored.** Status, banding, trend, age and clock state are computed from the
  stored facts every time they are shown. A stored derivation is a second source of truth that
  goes wrong quietly, and disagrees with the first exactly when someone is relying on it.
- **Append-only, and a refusal costs nothing.** Every mutation appends a history event with its
  rationale. Where a skill refuses one, the refusal is raised *before the file is opened*, so a
  rejected write leaves the store byte-identical rather than half-applied.
- **A placeholder beats a fabrication.** Where a board-facing slot has no sourced content, the
  artifact shows a visible hole. Governance documents are read by people who will act on them, and
  a plausible invented sentence is worse than an obvious gap — it is indistinguishable from a fact.
- **The tools decline to make judgments that are not theirs.** No materiality verdict, no maturity
  score from a Tier, no confidence figure attached to an age, no decay rate chosen on your behalf.
  Each of those is a decision a named person makes; the toolkit's job is to structure it, record
  who made it, and get out of the way.

## Licence

Apache License 2.0 — see [LICENSE](LICENSE) and [NOTICE](NOTICE).

You may use, modify, and distribute this work, including commercially. If you redistribute it or a
derivative, **retain the `NOTICE` file and credit Cyber Aware Creations, LLC.**, and mark any files
you changed. Deliverables generated by these skills carry the footer *"A Cyber Aware Creation · Not
affiliated with NIST"* — keep it.

Copyright 2026 Cyber Aware Creations, LLC.

*Not legal advice. Regulatory receipts carry their stated limits; do not present them to a board as
legal advice.*
