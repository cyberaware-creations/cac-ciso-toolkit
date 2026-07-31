# Trigger routing checklist — `metrics-register`

Confirms the skill fires when a request needs **state** — a number compared against last
period — and stays quiet when `ciso-board-translation` should handle a one-shot ask.

**Status: not yet run.** The cases below are authored; the harness that runs them
(`run-triggers.sh` + `score-triggers.py`) lives in `skills/nist-csf/evals/` and shells out
to `claude -p` once per prompt against the *installed* plugin. Bump the plugin version and
reinstall before running, or the run scores a stale build.

## The boundary this has to pin

`metrics-register` and `ciso-board-translation` both fire on "a metric for the board", and
they are the pair most likely to cannibalise each other. The distinction is **state**:

- needs last quarter's value, or writes one down → **metrics-register**
- one number, in isolation, nothing stored → **ciso-board-translation**

A secondary boundary runs against `risk-register`: a KRI *linked to* a risk is still a
metric, and the register is not where its readings live.

## Cases

| id | expected | prompt |
|---|---|---|
| M1 | metrics-register | Start tracking our patch coverage so I can show the trend at each board meeting. |
| M2 | metrics-register | Add this quarter's numbers: phishing click rate 6.8%, dwell time 8 days. |
| M3 | metrics-register | Which of our metrics are breaching their thresholds? |
| M4 | metrics-register | Which numbers have we not refreshed since the last review? |
| M5 | metrics-register | Show me how MFA coverage has moved over the last three quarters. |
| M6 | metrics-register | Build the metrics section for the Q3 board pack. |
| M7 | metrics-register | Set a warning threshold of 90% on our patch SLA metric. |
| M8 | metrics-register | Our dwell time went from 11 days to 8 — is that good or bad? |
| T1 | ciso-board-translation | How should I phrase 87% patch coverage for the board? |
| T2 | ciso-board-translation | What's the trap in reporting a phishing click rate? |
| T3 | ciso-board-translation | Give me a board sentence for "we blocked 2 million attacks". |
| T4 | ciso-board-translation | What are the seven metric archetypes? |
| R1 | risk-register | Score our ransomware risk and tell me if it's within appetite. |
| R2 | risk-register | Which risks are past their review date? |
| C1 | nist-csf | How complete are we against CSF Recover? |

### Why the tricky ones are here

**M8** ("11 days to 8 — is that good or bad?") looks like a one-shot translation ask and is
not. It names two values in sequence, which is a comparison, and the answer depends on the
metric's direction — exactly what the register stores and the translation skill does not.
If this routes to `ciso-board-translation` the description boundary is too soft.

**T3** ("we blocked 2 million attacks") is the mirror image. It is a single number with no
prior and nothing to store, so it belongs to the translation skill even though this skill
has a vanity flag for precisely that shape of number. Owning a *concept* is not owning a
*request*.

**R2** ("risks past their review date") uses "past their date" language that this skill also
uses for stale readings. Different object, different store.

## Adding a case

One row here and one line in a `prompts.tsv` (`id · expected · prompt`). Keep the ratio of
negative cases high: a description that fires on everything scores well on positives alone
and is worse than useless in a plugin with four skills.

---

*A Cyber Aware Creation · Not affiliated with NIST.*
