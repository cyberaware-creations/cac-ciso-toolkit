# `.att` store schema

`schemaVersion: 1`, `family: "attention-surface"`. JSON, written atomically.

**The smallest store in the suite, deliberately.** A pure projection cannot know what is new, and
a review timestamp is the minimum state that makes "what changed" possible. Everything else this
surface shows is read from a producer at run time and never copied in here — a second copy of
somebody else's record is a second thing to go stale.

```jsonc
{
  "schemaVersion": 1,
  "family": "attention-surface",
  "meta": { "orgName": "", "preparedBy": "", "asOf": "YYYY-MM-DD" },
  "sources": { "vendor-register": "../vendors.vnd" },
  "reviews": [ ... ],
  "createdAt": "…", "updatedAt": "…"
}
```

## `sources`

`skill -> path to that producer's own store`. `add-source` refuses a skill this surface cannot
read, and refuses `nist-csf` by name with the reason: it emits no escalations, so a source
entry for it would be permanently silent and indistinguishable from a broken one.

The producer table — which script, which argv, whether it takes `--context` — lives in the
engine, mirrored from `board-pack` rather than shared with it. Every shipped script runs
standalone, and CAC-AP-1 §2.6 makes the transport between skills data rather than an import.

## `reviews[]`

| field | notes |
|---|---|
| `on` | the `asOf` the review was run for |
| `ts` | when it was recorded |
| `by` | **required.** A review is an act by a person; the whole value of "what changed since you last looked" is that somebody looked |
| `label` | optional, and what `--since` resolves against |
| `note` | free text |
| `keys` | the escalation set as it stood — `producer\|trigger\|subjectRef`, sorted |
| `sourcesRead` | which producers answered |
| `sourcesUnread` | which did not. Kept because a diff against a review that could not read half the estate means something different from one that could |

### Why `keys` and not the items

`keys` holds identities, never evidence prose. Evidence carries counts and dates that move
between runs — *"last assessed 2025-06-30; cadence 365 days"* rewords itself as the clock
advances — so keying on it would mark every item new every week, which is the same as marking
none. Storing the prose would also make this store a stale copy of the producer's record.

## What is NOT in this store

- **No mute, no snooze, no acknowledgement.** See `scope.md`.
- **No escalations.** They are read at run time, every time. A cached copy would let this
  surface disagree with the register it is projecting.
- **No severity, criticality, band or status of its own.**
- **No priority, score, rank or weight.**

---

*A Cyber Aware Creation · Not affiliated with NIST. Not legal advice.*
