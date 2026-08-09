#!/usr/bin/env python3
"""CAC-RW-1 — every skill declares the sources it cites, and the citations do not drift.

The standard is written up in tools/sources-schema.md; this is its implementation.

Why this exists. Before v0.52.0 exactly two source families in the product carried a freshness
stamp. Every legal citation and every NIST publication was undated at the point of use, and the
v0.48.0-v0.51.0 verification pass found twelve defects across six families -- every one an
AMENDMENT failure, where the citation was right when written and the instrument moved underneath
it. None would have been caught by re-reading the repo. This manifest records what to open and
when it was last opened.

Six checks:

  C1  presence  -- every skill has a parsing sources.json (an empty `sources` array is valid)
  C2  shape     -- required fields present, ids unique per skill, checkedOn sane, gate coherent
  C3  rendered  -- a `renderedAs` string appears byte-for-byte in the files the row claims
  C4  usedFor   -- every path a row lists exists in the tree
  C5  do-not-cite -- no withdrawn publication is cited as current, anywhere in the tree
  C6  declared  -- every designation cited in a covered file is declared, or allowlisted

C3 is the one this standard is named for. Renderers keep their literal string rather than
reading this file at runtime (RW-1.5), because every shipped script here runs standalone; the
byte-equality check is what keeps the two copies honest.

C4 and C6 are converses and both are needed. C4 reads the manifest and asks whether the tree
still matches it; C6 reads the tree and asks whether the manifest covers it. Only C4 existed
until v0.57.0, so a citation added to a reference file and never added to sources.json was
invisible to every check here -- never reviewed, never re-checked, never gated, and
indistinguishable from one that had been verified (BL-190). C6 found ten of them on its first
run, in five shipped skills.

Exit 0 when clean, 1 otherwise.

Usage: tools/check-sources.py [--self-test] [--release-gate]
"""
import datetime
import json
import os
import re
import sys

REQUIRED = ("id", "label", "publisher", "instrument", "version",
            "checkedOn", "checkedBy", "gated", "usedFor")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
# The house cadence. A row that keeps it says nothing; a row that leaves it must.
DEFAULT_INTERVAL_DAYS = 365
USAGE = "usage: tools/check-sources.py [--self-test] [--release-gate]"


def _today():
    return datetime.date.today()


def skill_dirs(root):
    """Every directory holding a SKILL.md. Discovered, never listed -- a skill added without a
    manifest must fail rather than be silently absent, which is the same reasoning
    prove-guards.sh applies to guards."""
    base = os.path.join(root, "skills")
    if not os.path.isdir(base):
        return []
    return sorted(d for d in os.listdir(base)
                  if os.path.isfile(os.path.join(base, d, "SKILL.md")))


def load(root, skill):
    """Returns (doc, error). A missing or unparsable manifest is an error, not an empty doc."""
    path = os.path.join(root, "skills", skill, "sources.json")
    if not os.path.isfile(path):
        return None, "no sources.json (an empty `sources` array is the honest answer for a " \
                     "skill that cites nothing -- a missing file is not)"
    try:
        with open(path, encoding="utf-8") as fh:
            doc = json.load(fh)
    except (OSError, ValueError) as exc:
        return None, "could not be read: %s" % exc
    if not isinstance(doc, dict) or not isinstance(doc.get("sources"), list):
        return None, "must be an object with a `sources` array"
    return doc, None


_PLACEHOLDER = ("tbd", "todo", "pending", "n/a", "na", "-", "?", "unknown", "later",
                "not yet", "wip", "xxx", "fixme")


def _is_placeholder(text):
    """A reason that is not a reason. RW-1.11 rests entirely on this field being real."""
    # The named list, plus a floor low enough to catch "x" and high enough to leave a terse
    # honest answer alone. A first draft used 12 characters and rejected "paywalled" -- which
    # punishes concision rather than emptiness, and would have taught authors to pad. The
    # existing self-test caught it, which is the argument for keeping cases that assert the
    # PERMITTED direction alongside the forbidden one.
    t = " ".join(str(text or "").lower().split()).strip(" .!-")
    return t in _PLACEHOLDER or len(t) < 6


def check_shape(skill, doc, today):
    """C2. Every problem is collected rather than raised, so one run reports all of them."""
    problems, seen = [], set()
    for i, row in enumerate(doc["sources"]):
        where = "%s sources[%d]" % (skill, i)
        if not isinstance(row, dict):
            problems.append("%s is not an object" % where)
            continue
        rid = row.get("id")
        if isinstance(rid, str) and rid.strip():
            where = "%s/%s" % (skill, rid)
            if rid in seen:
                problems.append("%s: duplicate id within the skill" % where)
            seen.add(rid)
        for field in REQUIRED:
            if field not in row:
                problems.append("%s: missing `%s`" % (where, field))
            elif field == "gated":
                if not isinstance(row[field], bool):
                    problems.append("%s: `gated` must be true or false" % where)
            elif field == "usedFor":
                if not isinstance(row[field], list) or not row[field]:
                    problems.append("%s: `usedFor` must be a non-empty list" % where)
            elif not isinstance(row[field], str) or not row[field].strip():
                problems.append("%s: `%s` is empty" % (where, field))
        on = row.get("checkedOn")
        if isinstance(on, str) and DATE_RE.match(on):
            try:
                d = datetime.date(*(int(p) for p in on.split("-")))
                if d > today:
                    problems.append("%s: `checkedOn` %s is in the future" % (where, on))
            except ValueError:
                problems.append("%s: `checkedOn` %s is not a real date" % (where, on))
        elif "checkedOn" in row:
            problems.append("%s: `checkedOn` must be YYYY-MM-DD" % where)
        # RW-1.8 -- `unverified` is an allowed and load-bearing value for checkedBy. Most rows
        # in the first manifest record a citation nobody has yet read against its primary
        # source, and saying so is the entire point of the exercise: a manifest that stamped
        # every row as checked on the day it was authored would be a worse lie than the
        # undated citations it replaced. What an unverified row may NOT be is `gated` -- the
        # release gate would then be measuring the age of a check that never happened.
        if row.get("checkedBy") == "unverified":
            if row.get("gated") is True:
                problems.append("%s: `checkedBy` is unverified, so `gated` cannot be true -- the "
                                "gate would be timing a check that never happened" % where)
            # An unverified row must say WHY. Without this the value degrades into a shrug, and
            # the next maintainer cannot tell "nobody got to it" from "the source is paywalled
            # and no amount of trying will change that". Both remaining rows in this repo are
            # the second kind, and knowing that saves someone an afternoon.
            why = row.get("whyUnverified")
            if not isinstance(why, str) or not why.strip():
                problems.append("%s: `checkedBy` is unverified, so `whyUnverified` is required "
                                "-- say what blocked it, or it reads as nobody having tried"
                                % where)
            # RW-1.11. DECIDED 2026-08-09: an unverified row does NOT fail the release gate.
            # It ships with a caveat and a printed count, because the alternative pressures
            # people into stamping `claude-code` on a row nobody read -- which converts a
            # visible gap into an invisible lie, and this manifest exists to prevent exactly
            # that trade.
            #
            # The cost of that decision is that `whyUnverified` is the only thing standing
            # between "we looked and it is paywalled" and "nobody has got to it", so a
            # placeholder there empties the rule out. A reason must be a reason.
            elif _is_placeholder(why):
                problems.append("%s: `whyUnverified` is %r, which is a placeholder rather than "
                                "a reason. An unverified row ships and does not block the "
                                "release (RW-1.11), so this sentence is the ONLY thing "
                                "distinguishing a source nobody can reach from one nobody "
                                "opened. Say which." % (where, why.strip()[:40]))
        # RW-1.13. DECIDED 2026-08-09. Every gated row in this repo carried
        # `reviewIntervalDays: 365`, all twenty-odd of them, which means the number was never a
        # judgement about any instrument — it was a default typed once and copied. The question
        # asked was "does 365 suit the SEC rule"; the honest answer is that nothing had ever
        # decided, for that row or any other.
        #
        # 365 stays the house default and needs no defence. A DEVIATION does: an interval that
        # differs from the default must carry `intervalBecause`, so the next reader can tell a
        # considered cadence from a fiddled one. That inverts the burden onto the only case
        # where a burden is useful.
        iv = row.get("reviewIntervalDays")
        if row.get("gated") is True and isinstance(iv, int) and iv != DEFAULT_INTERVAL_DAYS:
            because = row.get("intervalBecause")
            if not isinstance(because, str) or len(" ".join(because.split())) < 40:
                problems.append("%s: `reviewIntervalDays` is %s, not the %s-day default, so "
                                "`intervalBecause` must say why. An unexplained interval is "
                                "indistinguishable from a typo, and it silently sets how long "
                                "a changed instrument can go unnoticed."
                                % (where, iv, DEFAULT_INTERVAL_DAYS))
        elif "intervalBecause" in row and iv == DEFAULT_INTERVAL_DAYS:
            problems.append("%s: `intervalBecause` on a default-interval row — the default "
                            "needs no defence, and a justification here reads as a deviation "
                            "that is not one" % where)

        # RW-1.12. DECIDED 2026-08-09: `checkedBy: "claude-code"` STAYS, and a human
        # counter-signature is added beside it rather than replacing it.
        #
        # The question was whether a row should carry a person's name. Replacing the machine
        # value with one would be a false provenance: an agent opened the publisher's page,
        # and a manifest whose whole claim is "somebody read the primary source" must not
        # misreport who. Dropping the field for a human-only signature would lose the record
        # of a real check.
        #
        # So both, and they mean different things: `checkedBy` is who READ the source,
        # `reviewedBy` is who ACCEPTED that reading. A row with only the first is not
        # deficient -- most are -- but the counts print, so the number of rows a person has
        # actually endorsed is visible rather than assumed.
        reviewer = row.get("reviewedBy")
        reviewed_on = row.get("reviewedOn")
        if reviewer is not None:
            if not isinstance(reviewer, str) or not reviewer.strip():
                problems.append("%s: `reviewedBy` must be a name, not empty" % where)
            elif reviewer.strip().lower() in ("claude-code", "claude", "ai", "agent"):
                problems.append("%s: `reviewedBy` is %r -- a counter-signature is a PERSON "
                                "accepting the reading. The tool that read it is already "
                                "recorded in `checkedBy`, and a machine countersigning its "
                                "own work is not a second opinion." % (where, reviewer.strip()))
            elif not isinstance(reviewed_on, str) or not DATE_RE.match(reviewed_on or ""):
                problems.append("%s: `reviewedBy` needs a `reviewedOn` date (YYYY-MM-DD) -- an "
                                "undated endorsement cannot age, which is the one thing this "
                                "manifest measures" % where)
            else:
                try:
                    if datetime.date.fromisoformat(reviewed_on) > today:
                        problems.append("%s: `reviewedOn` %s is in the future"
                                        % (where, reviewed_on))
                except ValueError:
                    problems.append("%s: `reviewedOn` %s is not a real date"
                                    % (where, reviewed_on))
        elif reviewed_on is not None:
            problems.append("%s: `reviewedOn` with no `reviewedBy` -- a date signs nothing"
                            % where)

        # RW-1.6 -- a gated row the release gate cannot evaluate is worse than an ungated one,
        # because it looks supervised and is not.
        if row.get("gated") is True:
            iv = row.get("reviewIntervalDays")
            if not isinstance(iv, int) or isinstance(iv, bool) or iv <= 0:
                problems.append("%s: `gated` is true so `reviewIntervalDays` must be a "
                                "positive integer" % where)
    return problems


def check_used_for(root, skill, doc):
    """C4. A manifest that has drifted from the tree describes a repo that no longer exists."""
    problems = []
    for row in doc["sources"]:
        if not isinstance(row, dict) or not isinstance(row.get("usedFor"), list):
            continue
        for rel in row["usedFor"]:
            if not isinstance(rel, str):
                continue
            if not os.path.exists(os.path.join(root, "skills", skill, rel)):
                problems.append("%s/%s: usedFor names %s, which is not in the tree"
                                % (skill, row.get("id", "?"), rel))
    return problems


# ---------------------------------------------------------------------------
# C6 (CAC-RW-1.10) -- the converse of C4.
#
# C4 asks "does every path a row claims exist?" -- manifest against tree. It cannot ask the
# question that matters more: **is every instrument this skill cites actually declared?** A
# citation added to a reference file and never added to sources.json is invisible to every
# check in this file. It is never reviewed, never re-checked, and never gated -- and it looks
# exactly like a citation that was verified, because nothing distinguishes them (BL-190).
#
# The detector is a vocabulary of designation shapes, canonicalised to a stable key so that
# "ISO/IEC 27001:2022" and "ISO 27001" are one designation rather than two. Substring matching
# was tried first and produced false positives on exactly that pair, which is the failure mode
# that gets a check switched off in a fortnight.
#
# Every entry carries a `mustMatch` fixture and the key it must produce, asserted in the
# self-test. A pattern that stops matching would otherwise reduce C6's coverage silently --
# the same reasoning as `mustFlag` in do-not-cite.json (RW-1.9.2).
_CITE_VOCAB = (
    {"id": "nist-sp",
     "pattern": r"\bSP\s*(?P<n>800-\d+[A-Za-z]?)(?:\s*(?:r|rev\.?|revision)\s*(?P<r>\d+))?",
     "key": "sp-{n}{r}",
     "mustMatch": "NIST SP 800-53 Rev. 5, Security and Privacy Controls",
     "expect": "sp-800-53r5"},
    {"id": "nist-ir",
     "pattern": r"\b(?:NIST\s*)?(?:NISTIR|IR)\s*(?P<n>\d{4}[A-Za-z]?)"
                r"(?:\s*(?:r|rev\.?|revision)\s*(?P<r>\d+))?",
     "key": "ir-{n}{r}",
     "mustMatch": "NISTIR 8286A r1 — Identifying and Estimating",
     "expect": "ir-8286ar1"},
    {"id": "nist-cswp",
     "pattern": r"\bCSWP\s*(?P<n>\d+)", "key": "cswp-{n}",
     "mustMatch": "NIST CSWP 29", "expect": "cswp-29"},
    # The E-year is dropped for the same reason ISO's edition year is, below.
    {"id": "nist-ai",
     "pattern": r"\bAI\s*(?P<n>100-\d+)(?:\s*E\d{4})?", "key": "ai-{n}",
     "mustMatch": "NIST AI 100-2 E2025, Adversarial Machine Learning",
     "expect": "ai-100-2"},
    # The edition year is deliberately dropped: a skill declaring ISO/IEC 27001:2022 and prose
    # naming ISO 27001 are the same instrument. Edition drift is C2's job, not C6's.
    #
    # A NIST *revision* is NOT dropped, and the asymmetry is deliberate. `SP 800-171 Rev. 2`
    # and `Rev. 3` are different documents with different obligations — do-not-cite.json
    # watches exactly that distinction — whereas an ISO edition year is how the same standard
    # is written when somebody is being precise. Collapsing revisions would make C6 blind to
    # the amendment failure that every reference defect in this repo has turned out to be.
    {"id": "iso",
     "pattern": r"\bISO(?:/IEC)?\s*(?P<n>\d{4,5}(?:-\d+)?)(?::\d{4})?", "key": "iso-{n}",
     "mustMatch": "ISO/IEC 27001:2022 Annex A", "expect": "iso-27001"},
    {"id": "eu-instrument",
     "pattern": r"\b(?:Regulation|Directive)\s*\(EU\)\s*(?P<n>\d{4}/\d+)", "key": "eu-{n}",
     "mustMatch": "Regulation (EU) 2022/2554", "expect": "eu-2022/2554"},
    # `ss?` is in the section-marker alternation because this repo writes § as ASCII `s` —
    # `17 C.F.R. s 229.106`, `23 NYCRR Part 500, ss 500.9`. Without it the pattern read the
    # prose and not the manifests, so two rows added in the same commit as this check went on
    # reporting themselves undeclared. Anchored immediately after CFR, so a bare `s` elsewhere
    # cannot trigger it.
    {"id": "cfr",
     "pattern": r"\b(?P<t>\d+)\s*C\.?\s?F\.?R\.?\s*(?:§{1,2}|ss?)?\s*(?P<n>\d[\d.]*\d)",
     "key": "cfr-{t}-{n}",
     "mustMatch": "17 C.F.R. § 229.106", "expect": "cfr-17-229.106",
     "alsoMatch": ("17 C.F.R. s 229.106", "47 CFR 64.2011", "17 CFR 232.13")},
    {"id": "nycrr",
     "pattern": r"\b(?P<t>\d+)\s*NYCRR\s*Part\s*(?P<n>\d+)", "key": "nycrr-{t}-{n}",
     "mustMatch": "23 NYCRR Part 500, ss 500.9", "expect": "nycrr-23-500"},
)
_CITE_COMPILED = [(v, re.compile(v["pattern"], re.I)) for v in _CITE_VOCAB]


def cite_keys(text):
    """Every canonical designation key in `text`. Typography is folded first, as for C5."""
    keys = set()
    folded = _dnc_fold(text or "")
    for vocab, pat in _CITE_COMPILED:
        for m in pat.finditer(folded):
            parts = {k: (v or "") for k, v in m.groupdict().items()}
            if "r" in parts and parts["r"]:
                parts["r"] = "r" + parts["r"]
            keys.add(vocab["key"].format(**parts).lower().replace(" ", ""))
    return keys


def check_declared(root, skill, doc):
    """C6. Every designation cited in a covered file is declared, or allowlisted with a reason.

    "Covered file" means a file some row already claims in `usedFor` -- the set C4 validates.
    Widening beyond that would be a different check with a different argument; this one asks
    only that the files a manifest already points at agree with the manifest.

    A row declares whatever designations appear in its own `instrument`, `label` or
    `renderedAs`, plus anything in an optional explicit `designations` list. The explicit list
    exists for series rows: `"NIST IR 8286r1, 8286A r1, 8286C r1"` names three publications and
    the detector can only see the first, because a bare `8286A r1` with no `IR` prefix is not a
    shape worth matching in open prose. Guessing there would trade false negatives for false
    positives, and a noisy check is a check somebody turns off.
    """
    problems = []
    declared, covered = set(), []
    for row in doc["sources"]:
        if not isinstance(row, dict):
            continue
        for field in ("instrument", "label", "renderedAs"):
            declared |= cite_keys(str(row.get(field) or ""))
        extra = row.get("designations")
        if isinstance(extra, list):
            for d in extra:
                if isinstance(d, str) and d.strip():
                    declared.add(d.strip().lower())
        for rel in (row.get("usedFor") or []):
            if isinstance(rel, str) and rel not in covered:
                covered.append(rel)

    allow = {}
    raw_allow = doc.get("citationAllowlist")
    if raw_allow is not None:
        if not isinstance(raw_allow, list):
            return ["%s: citationAllowlist must be a list" % skill]
        for i, item in enumerate(raw_allow):
            if not isinstance(item, dict):
                problems.append("%s: citationAllowlist[%d] must be an object" % (skill, i))
                continue
            key = str(item.get("designation") or "").strip().lower()
            why = str(item.get("reason") or "").strip()
            if not key:
                problems.append("%s: citationAllowlist[%d] has no `designation`" % (skill, i))
                continue
            # An allowlist whose entries need no reason is a way to switch C6 off one line at a
            # time, and it would read as considered judgement while being the opposite.
            if not why:
                problems.append("%s: citationAllowlist entry %r has no `reason` — an "
                                "undeclared citation is allowed only with an argument for why"
                                % (skill, key))
                continue
            allow[key] = why

    for rel in covered:
        path = os.path.join(root, "skills", skill, rel)
        try:
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
        except (OSError, UnicodeDecodeError):
            continue
        for key in sorted(cite_keys(text) - declared - set(allow)):
            problems.append("%s/%s: cites %s, which no row in sources.json declares — add a "
                            "verified row, or allowlist it with a reason" % (skill, rel, key))

    return problems


def check_rendered(root, skill, doc):
    """C3. `renderedAs` must appear byte-for-byte in at least one file the row claims.

    Byte-for-byte and not normalised: the whole point is to catch the character that drifted.
    Searching only the row's own `usedFor` files rather than the whole skill is deliberate --
    it makes the row say where its citation lives, so a reader can find it without grepping.
    """
    problems = []
    for row in doc["sources"]:
        if not isinstance(row, dict):
            continue
        rendered = row.get("renderedAs")
        if rendered is None:
            continue  # RW-1.4 -- absence is meaningful, not incomplete
        if not isinstance(rendered, str) or not rendered.strip():
            problems.append("%s/%s: `renderedAs` is present but empty -- omit it instead"
                            % (skill, row.get("id", "?")))
            continue
        found = False
        for rel in row.get("usedFor") or []:
            path = os.path.join(root, "skills", skill, rel)
            try:
                with open(path, encoding="utf-8") as fh:
                    if rendered in fh.read():
                        found = True
                        break
            except (OSError, UnicodeDecodeError):
                continue
        if not found:
            problems.append("%s/%s: renderedAs %r appears in none of its usedFor files -- "
                            "either the renderer drifted or the manifest did"
                            % (skill, row.get("id", "?"), rendered[:70]))
    return problems


# Every path here is a file that must contain watched designations in order to do its job:
# the registry itself, the code that reads it, the schema that documents it, and the changelog
# that records why each was added. They are exempt because a citation in them is the subject,
# not a recommendation.
#
# `docs/` and `research/` were on this list until v0.57.0 and had no such justification
# (BL-194). Nothing in either directory is about the registry; they are ordinary prose, which
# is exactly where a withdrawn publication gets cited by reflex. The exemption was reasoning by
# directory name rather than by role, and it made C5 blind to 24 shipped files. Removing them
# found no existing violation — which is the outcome to expect and not a reason to have left
# the hole open, because C5's whole purpose is the citation nobody has written yet.
#
# The test for adding anything here: does this file need the string in order to police the
# string? If not, it is in scope.
_DNC_EXEMPT = ("CHANGELOG.md", "tools/do-not-cite.json",
               "tools/check-sources.py", "tools/sources-schema.md")
_DNC_NAMES = ("NOTICE", "README")

# Typography normalisation. A citation written with a non-breaking hyphen, an en-dash or a
# non-breaking space is the same citation, and the first version of this check did not match
# any of them -- "SP 800‑61 Rev. 2" sailed straight through. Every mapping here is
# ONE character to ONE character, so match offsets and therefore reported line numbers stay
# exact; a length-changing normalisation would report the wrong line.
_DNC_FOLD = {ord(c): "-" for c in "‐‑‒–—―−­"}
_DNC_FOLD[0x00a0] = " "   # non-breaking space
_DNC_FOLD[0x2007] = " "   # figure space
_DNC_FOLD[0x202f] = " "   # narrow no-break space


def _dnc_fold(text):
    """Normalise typography without moving a single character offset."""
    return text.translate(_DNC_FOLD)


_DNC_URL = re.compile(r"(?:https?://|ftp://|www\.)\S+", re.I)


def _dnc_blank_urls(line):
    """Blank URL runs to spaces, preserving length so offsets stay exact.

    A marker inside a link target is not prose about a publication. `See
    https://csrc.nist.gov/withdrawn/ and use SP 800-61 Rev. 2.` put the word "withdrawn"
    nearer the citation than anything else on the line and laundered it. Found by inventing
    adversarial cases after the four reported ones were fixed, which is the only reason it is
    here -- the reported four would have left it open.
    """
    return _DNC_URL.sub(lambda m: " " * len(m.group(0)), line)


def _all_positions(haystack, needle):
    """Every WHOLE-WORD occurrence, not just the first -- one line can carry several markers.

    Whole-word matters: plain substring search let `obsoleteFlag` count as the marker
    "obsolete" and excuse a citation beside it. An identifier that happens to contain a
    marker is not a warning about anything.
    """
    out = []
    for m in re.finditer(r"(?<![a-z0-9])%s(?![a-z0-9])" % re.escape(needle), haystack):
        out.append(m.start())
    return out


# A clause ends at a sentence terminator, a semicolon, or a table-cell pipe.
#
# NOT at a comma and NOT at a dash. `SP 800-61 Rev. 2, withdrawn in 2025, ...` and
# `SP 800-61 Rev. 2 — withdrawn` are the two commonest honest forms in this repo, and a rule
# that split on either would reject the warning it exists to permit.
_DNC_CLAUSE_END = re.compile(r"[;|]|[.!?](?=\s|$)")

# `Rev.` is not the end of a sentence, and getting that wrong breaks every honest form at once.
#
# The publication patterns deliberately match only the STEM — `SP 800-61`, not `SP 800-61
# Rev. 2` — so that a bare citation with no revision is caught too. That means the full stop in
# `Rev. 2` falls OUTSIDE the matched span, where an in-span exclusion cannot help it. Six
# acceptance cases went red on exactly this before the list existed.
#
# Scoped as tightly as it can be: the abbreviation must be one of these AND the next thing must
# be a number. `The tool was retired. 2 more follow.` still ends a clause, because `retired` is
# not on the list.
_DNC_ABBREV = ("rev", "r", "no", "vol", "ed", "pt", "sec", "art", "app", "fig", "ch",
               "para", "cl", "ss", "nos", "pp")
_DNC_ABBREV_DOT = re.compile(
    r"(?<![a-z0-9])(?:%s)\.$" % "|".join(_DNC_ABBREV), re.I)


def _dnc_clauses(line, spans):
    """Split a line into clauses, cutting only OUTSIDE every citation span.

    Two things stop the splitter severing a citation from its own warning:

      * cuts are never taken at an offset a matched publication occupies, and
      * a full stop closing a citation abbreviation followed by a number — `Rev. 2`, `No. 5`
        — is not a sentence end.

    The second is not belt-and-braces. The publication patterns match the STEM only, so the
    stop in `Rev. 2` is outside every span and the first rule never sees it.

    Offsets are preserved end to end: the caller folds typography and blanks URLs with
    length-preserving substitutions, so a clause's (start, end) indexes the real line.

    Returns a list of (start, end) covering the whole line; never empty.
    """
    cuts = []
    for m in _DNC_CLAUSE_END.finditer(line):
        i = m.start()
        if any(s <= i < e for s, e in spans):
            continue
        if line[i] == "." and _DNC_ABBREV_DOT.search(line[:i + 1]):
            rest = line[i + 1:].lstrip()
            if rest[:1].isdigit():
                continue
        cuts.append(m.end())
    out, prev = [], 0
    for c in cuts + [len(line)]:
        if c > prev:
            out.append((prev, c))
            prev = c
    return out or [(0, len(line))]


def _dnc_clause_of(clauses, pos):
    for s, e in clauses:
        if s <= pos < e:
            return (s, e)
    return clauses[-1]


_DNC_ROW = ("id", "label", "pattern", "status", "supersededBy", "why", "mustFlag")
_DNC_STATUS = ("withdrawn", "superseded")


def validate_registry(doc):
    """RW-1.9.2. The registry is trusted by C5, so C5 must not trust it blindly.

    A malformed row used to pass green: the fields C5 reads to BUILD its error message --
    `status`, `supersededBy` -- are only touched when something matches, so an entry missing
    both sat in the file looking like protection and would have crashed the first time it
    caught anything. And a pattern matching nothing at all was indistinguishable from a
    pattern guarding a publication nobody cites.

    Hence `mustFlag`: every entry carries a string its own pattern MUST match, and optionally
    a `mustNotFlag` it must not. These are executable fixtures, not documentation. A pattern
    that has stopped matching its own example is reported here rather than discovered the day
    somebody cites the publication it was supposed to be watching.

    Returns a list of problems; empty means usable.
    """
    problems = []
    if not isinstance(doc, dict):
        return ["do-not-cite.json is not an object"]
    markers = doc.get("markers")
    if not isinstance(markers, list) or not markers:
        problems.append("`markers` must be a non-empty list -- with none, no warning could "
                        "ever excuse a citation and every honest mention would fail")
    else:
        for i, m in enumerate(markers):
            if not isinstance(m, str) or not m.strip():
                problems.append("markers[%d] is empty" % i)
    entries = doc.get("entries")
    if not isinstance(entries, list) or not entries:
        return problems + ["`entries` must be a non-empty list; C5 would pass vacuously"]
    seen = set()
    for i, e in enumerate(entries):
        where = "entries[%d]" % i
        if not isinstance(e, dict):
            problems.append("%s is not an object" % where)
            continue
        if isinstance(e.get("id"), str) and e["id"].strip():
            where = "entry %s" % e["id"]
            if e["id"] in seen:
                problems.append("%s: duplicate id" % where)
            seen.add(e["id"])
        for f in _DNC_ROW:
            if not isinstance(e.get(f), str) or not e[f].strip():
                problems.append("%s: `%s` is missing or empty" % (where, f))
        if e.get("status") not in _DNC_STATUS and "status" in e:
            problems.append("%s: `status` is %r, expected one of %s"
                            % (where, e.get("status"), " / ".join(_DNC_STATUS)))
        pat = None
        if isinstance(e.get("pattern"), str):
            try:
                pat = re.compile(e["pattern"], re.I)
            except re.error as exc:
                problems.append("%s: `pattern` does not compile: %s" % (where, exc))
        if pat is not None:
            mf = e.get("mustFlag")
            if isinstance(mf, str) and mf.strip() and not pat.search(_dnc_fold(mf)):
                problems.append("%s: `pattern` does not match its own `mustFlag` %r -- the "
                                "fixture says this entry guards something the pattern no "
                                "longer catches" % (where, mf))
            mn = e.get("mustNotFlag")
            if isinstance(mn, str) and mn.strip() and pat.search(_dnc_fold(mn)):
                problems.append("%s: `pattern` matches its `mustNotFlag` %r -- it is flagging "
                                "the edition that replaced the withdrawn one"
                                % (where, mn))
    return problems


def check_do_not_cite(root="."):
    """C5. A withdrawn publication may be discussed, never cited as current.

    sources.json watches what a skill DOES cite and structurally cannot see a publication the
    skill has not cited yet -- and that is the more dangerous class, because the defect arrives
    fresh rather than sitting in text somebody could review. SP 800-61 Rev. 2 is the worked
    example: withdrawn, and its four-phase incident lifecycle is still repeated by nearly every
    secondary source, so the first author to write incident-response content reaches for it by
    reflex.

    The rule is not a ban on the string. Naming a withdrawn document in order to say it is
    withdrawn is exactly what this repo should do, and this file does it constantly. What fails
    is the string with no withdrawal marker BOUND TO IT -- a citation, rather than a caution.

    "Bound to it" is the whole of RW-1.9.1, and it replaces a proximity window that failed open
    four ways (BL-194). A marker excuses a match only when ALL THREE hold:

      (a) the marker is on the SAME LINE as the match,
      (b) the marker is in the SAME CLAUSE as the match, and
      (c) of every watched publication in that clause, the one nearest the marker is this match.

    (a) kills "unrelated prose nearby": `Our old policy was withdrawn last year.` on the line
    above a bare citation no longer excuses it. (c) kills the cross-publication case:
    `SP 800-53A Rev. 4 is withdrawn and SP 800-61 Rev. 2 is current.` -- the marker sits nearer
    800-53A, so it does not launder the 800-61 citation sharing its clause.

    (b) IS WHY BL-201 EXISTS, and it is worth stating plainly because the gap it closes was
    invisible for three releases. (c) is a COMPARATIVE test, and a comparison needs something to
    compare against. When the citation is the only watched publication in its clause -- the
    common case, not the exotic one -- `all(...)` iterates over the match itself and evaluates
    `mine <= mine`. Always true. So (c) was satisfied vacuously and the rule collapsed to (a):
    ANY marker anywhere on the line excused the citation. This passed, and cites withdrawn
    guidance as current:

        The predecessor platform was retired. Follow SP 800-61 Rev. 2 for incident handling.

    The rule was designed and documented against two publications, where "nearest" means
    something. At n=1 the word has no referent. (b) supplies the absolute binding that (c)
    cannot: the marker has to be in the same clause, so a warning about a different subject in
    a different sentence no longer launders anything. Registered here alongside BL-121's
    `[ -z "$res" ]` and BL-176's `len(bounds) == 1` as the same shape -- a test that reads as
    discriminating and stops discriminating when its input is minimal. Read a guard for what it
    does at n=0 and n=1, not at n=typical.

    A clause ends at `.`/`!`/`?`/`;`/`|`, never at a comma or a dash, and never at a full stop
    inside a citation -- see `_dnc_clauses`.

    This is stricter than the window it replaces, and deliberately so: `X.\\nIt is withdrawn.`
    now fails where it used to pass. For a check whose failure mode is passing silently, a rule
    an author can be told in one sentence -- *put the warning in the same sentence as the
    citation* -- is worth more than one that accommodates every phrasing and catches nothing.
    """
    path = os.path.join(root, "tools", "do-not-cite.json")
    if not os.path.isfile(path):
        print("ERROR: tools/do-not-cite.json is missing; C5 checked nothing.")
        return False
    try:
        with open(path, encoding="utf-8") as fh:
            doc = json.load(fh)
    except (OSError, ValueError) as exc:
        print("ERROR: tools/do-not-cite.json could not be read: %s" % exc)
        return False
    bad = validate_registry(doc)
    if bad:
        print("ERROR: tools/do-not-cite.json is malformed (CAC-RW-1.9.2):")
        for b in bad:
            print("         %s" % b)
        print("       C5 trusts this file, so it is validated before use. See "
              "tools/sources-schema.md.")
        return False
    entries = doc["entries"]
    markers = [m.lower() for m in doc["markers"]]
    pats = [(e, re.compile(e["pattern"], re.I)) for e in entries]

    problems, scanned = [], 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in (".git", "__pycache__", "node_modules")]
        for fn in filenames:
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, root).replace(os.sep, "/")
            if any(rel == e or rel.startswith(e) for e in _DNC_EXEMPT):
                continue
            if (os.path.splitext(fn)[1].lower() not in (".md", ".py", ".json", ".sh")
                    and fn not in _DNC_NAMES):
                continue
            try:
                with open(full, encoding="utf-8") as fh:
                    text = fh.read()
            except (OSError, UnicodeDecodeError):
                continue
            scanned += 1
            # Fold typography first, and only then match, so a non-breaking hyphen cannot
            # smuggle a citation past the pattern. The fold is 1:1, so `lineno` below is still
            # computed against offsets that correspond to the file on disk.
            folded = _dnc_fold(text)
            for lineno, raw in enumerate(folded.split("\n"), 1):
                low = _dnc_blank_urls(raw.lower())
                # Every watched publication on this line, in order. Needed for the binding
                # rule: a marker belongs to whichever publication it sits nearest.
                on_line = []
                for entry, pat in pats:
                    for m in pat.finditer(raw):
                        on_line.append((m.start(), m.end(), entry, m.group(0).strip()))
                if not on_line:
                    continue
                marks = [i for k in markers for i in _all_positions(low, k)]
                spans = [(s, e) for s, e, _, _ in on_line]
                clauses = _dnc_clauses(low, spans)
                for start, end, entry, hit in on_line:
                    clause = _dnc_clause_of(clauses, start)
                    # (c) is scoped to the clause: a publication in another sentence is not a
                    # candidate for a marker it could never have been bound to anyway.
                    rivals = [(s2, e2) for s2, e2 in spans
                              if _dnc_clause_of(clauses, s2) == clause]
                    excused = False
                    for mi in marks:
                        # (b) same-clause binding. This is what carries the rule when the
                        # citation is the only publication in its clause, which is the common
                        # case and the one (c) alone could not judge (BL-201).
                        if not (clause[0] <= mi < clause[1]):
                            continue

                        # (c) nearest-publication binding. Distance is measured to the span,
                        # so a marker inside a citation counts as zero away from it.
                        def _dist(s, e, _mi=mi):
                            return 0 if s <= _mi <= e else min(abs(_mi - s), abs(_mi - e))
                        mine = _dist(start, end)
                        if all(mine <= _dist(s2, e2) for s2, e2 in rivals):
                            excused = True
                            break
                    if excused:
                        continue
                    problems.append("%s:%d: %s (%s) cited with no withdrawal marker bound to "
                                    "it in the same clause — say so beside it, or use %s"
                                    % (rel, lineno, hit, entry["status"],
                                       entry["supersededBy"].split(" — ")[0]))
    if not scanned:
        print("ERROR: the do-not-cite scan read no files; its glob stopped matching.")
        return False
    if problems:
        print("ERROR: withdrawn or superseded publications cited as current (CAC-RW-1.9):")
        for p in problems:
            print("         %s" % p)
        print("       Naming one to say it is withdrawn is fine — put the word near it. "
              "Citing one as guidance is not. See tools/do-not-cite.json.")
        return False
    print("do-not-cite: %d file(s), %d withdrawn publication(s) watched, none cited as current."
          % (scanned, len(entries)))
    return True


def check_sources(root="."):
    skills = skill_dirs(root)
    if not skills:
        print("ERROR: no skills found; the layout moved and this checked nothing.")
        return False
    problems, rows, unverified, countersigned = [], 0, 0, 0
    for skill in skills:
        doc, err = load(root, skill)
        if err:
            problems.append("%s: %s" % (skill, err))
            continue
        rows += len(doc["sources"])
        unverified += sum(1 for r in doc["sources"]
                          if isinstance(r, dict) and r.get("checkedBy") == "unverified")
        countersigned += sum(1 for r in doc["sources"]
                             if isinstance(r, dict) and str(r.get("reviewedBy") or "").strip())
        problems.extend(check_shape(skill, doc, _today()))
        problems.extend(check_used_for(root, skill, doc))
        problems.extend(check_rendered(root, skill, doc))
        problems.extend(check_declared(root, skill, doc))
    if problems:
        print("ERROR: source manifest problems (CAC-RW-1):")
        for p in problems:
            print("         %s" % p)
        print("       See tools/sources-schema.md.")
        return False
    # Printed on every run, not buried: the count of citations nobody has read against the
    # primary source is the number this whole standard exists to drive down, and a manifest
    # that reported only its own green tick would hide it.
    print("sources: %d skill(s), %d declared source(s), citations match their renderers."
          % (len(skills), rows))
    # RW-1.12. Printed every run, like the unverified count and for the same reason: the
    # number of rows a PERSON has endorsed is the one this standard would rather not have to
    # guess at. Zero is an honest answer and prints as one.
    print("         %d of %d countersigned by a person (reviewedBy); the rest record only "
          "who read the source." % (countersigned, rows))
    if unverified:
        print("         %d of %d not yet verified against a primary source "
              "(checkedBy: unverified) — none of them gated." % (unverified, rows))
    return True


def release_gate(root="."):
    """RW-1.6. A gated source older than its interval blocks the release."""
    overrides = {}
    opath = os.path.join(root, "tools", "release-overrides.json")
    if os.path.isfile(opath):
        try:
            with open(opath, encoding="utf-8") as fh:
                raw = json.load(fh)
            for o in (raw.get("overrides") or []):
                # An override with no reason is not an override. Owner and date are required
                # for the same reason the exceptions-register refuses an unapproved acceptance:
                # somebody has to be answerable for the decision to ship anyway.
                if all(isinstance(o.get(k), str) and o[k].strip()
                       for k in ("source", "reason", "owner", "date")):
                    overrides[o["source"]] = o
        except (OSError, ValueError) as exc:
            print("ERROR: tools/release-overrides.json could not be read: %s" % exc)
            return False
    today, stale, used = _today(), [], []
    for skill in skill_dirs(root):
        doc, err = load(root, skill)
        if err:
            print("ERROR: %s: %s" % (skill, err))
            return False
        for row in doc["sources"]:
            if not isinstance(row, dict) or row.get("gated") is not True:
                continue
            on, iv = row.get("checkedOn"), row.get("reviewIntervalDays")
            if not (isinstance(on, str) and DATE_RE.match(on) and isinstance(iv, int)):
                continue  # C2 already reports this; the gate does not double-report
            age = (today - datetime.date(*(int(p) for p in on.split("-")))).days
            if age <= iv:
                continue
            key = "%s/%s" % (skill, row["id"])
            ov = overrides.get(key)
            if ov:
                used.append("%s -- %s (%s, %s)" % (key, ov["reason"], ov["owner"], ov["date"]))
            else:
                stale.append("%s: checked %s, %d days ago, interval %d"
                             % (key, on, age, iv))
    for u in used:
        print("  override  %s" % u)
    if stale:
        print("ERROR: gated sources are past their review interval (CAC-RW-1.6):")
        for s in stale:
            print("         %s" % s)
        print("       Re-verify against the primary source and update `checkedOn`, or record "
              "an override in tools/release-overrides.json with a reason, owner and date.")
        return False
    print("release-gate: every gated source is within its review interval.")
    return True


def _self_test():
    import shutil
    import tempfile
    checks = []

    def ok(cond, label):
        checks.append(bool(cond))
        print("{:<4} {}".format("PASS" if cond else "FAIL", label))

    def tree(tmp, name, sources, extra=None):
        """A minimal repo: one skill, its SKILL.md, and whatever files the rows claim."""
        root = os.path.join(tmp, name)
        sk = os.path.join(root, "skills", "demo")
        os.makedirs(sk)
        with open(os.path.join(sk, "SKILL.md"), "w", encoding="utf-8") as fh:
            fh.write("# demo\n")
        for rel, body in (extra or {}).items():
            p = os.path.join(sk, rel)
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "w", encoding="utf-8") as fh:
                fh.write(body)
        with open(os.path.join(sk, "sources.json"), "w", encoding="utf-8") as fh:
            json.dump({"schemaVersion": 1, "skill": "demo", "sources": sources}, fh)
        return root

    def row(**kw):
        base = {"id": "s1", "label": "L", "publisher": "P", "instrument": "I",
                "version": "V", "checkedOn": "2026-01-01", "checkedBy": "claude-code",
                "gated": False, "usedFor": ["SKILL.md"]}
        base.update(kw)
        return base

    with tempfile.TemporaryDirectory() as tmp:
        ok(check_sources(tree(tmp, "clean", [row()])) is True,
           "a complete row passes")
        # RW-1.1 -- a skill that cites nothing is valid; a skill with no file is not.
        ok(check_sources(tree(tmp, "empty", [])) is True,
           "an empty sources array is valid (board-pack cites nothing)")
        missing = tree(tmp, "missing", [])
        os.remove(os.path.join(missing, "skills", "demo", "sources.json"))
        ok(check_sources(missing) is False,
           "a missing sources.json fails -- absence is not an empty array")

        for field in REQUIRED:
            bad = row()
            del bad[field]
            ok(check_sources(tree(tmp, "no_" + field, [bad])) is False,
               "a row missing `%s` fails" % field)

        ok(check_sources(tree(tmp, "dupe", [row(), row()])) is False,
           "a duplicate id within a skill fails")
        ok(check_sources(tree(tmp, "future",
                              [row(checkedOn="2099-01-01")])) is False,
           "a future checkedOn fails")
        ok(check_sources(tree(tmp, "baddate", [row(checkedOn="08-08-2026")])) is False,
           "a malformed checkedOn fails")
        ok(check_sources(tree(tmp, "gatenoiv", [row(gated=True)])) is False,
           "gated with no reviewIntervalDays fails -- it would look supervised and not be")
        ok(check_sources(tree(tmp, "gateok",
                              [row(gated=True, reviewIntervalDays=365)])) is True,
           "gated with a positive interval passes")
        ok(check_sources(tree(tmp, "ghost", [row(usedFor=["renderers/gone.py"])])) is False,
           "C4: a usedFor path not in the tree fails")

        # RW-1.8 -- unverified rows are allowed and counted, must say why, never gated.
        ok(check_sources(tree(tmp, "unver", [row(checkedBy="unverified",
                                                 whyUnverified="paywalled")])) is True,
           "an unverified row with a reason is valid -- saying so beats a check never made")
        ok(check_sources(tree(tmp, "unvernowhy", [row(checkedBy="unverified")])) is False,
           "an unverified row with no `whyUnverified` fails -- otherwise it reads as a shrug")
        ok(check_sources(tree(tmp, "unvergate",
                              [row(checkedBy="unverified", whyUnverified="paywalled",
                                   gated=True, reviewIntervalDays=365)])) is False,
           "an unverified row that is gated fails -- the gate would time a check never made")

        # C3, both directions -- the check this standard is named for.
        cite = "DORA RTS (EU) 2024/1774 Art. 3(d)"
        ok(check_sources(tree(tmp, "c3ok", [row(usedFor=["renderers/r.py"],
                                                renderedAs=cite)],
                              {"renderers/r.py": "x = '%s'\n" % cite})) is True,
           "C3: a renderedAs found byte-for-byte passes")
        ok(check_sources(tree(tmp, "c3drift", [row(usedFor=["renderers/r.py"],
                                                   renderedAs=cite)],
                              {"renderers/r.py": "x = 'DORA RTS Art. 3(d)'\n"})) is False,
           "C3: a renderer that dropped the instrument fails")
        ok(check_sources(tree(tmp, "c3char", [row(usedFor=["renderers/r.py"],
                                                  renderedAs=cite)],
                              {"renderers/r.py": "x = '%s'\n" % cite.replace("3(d)", "3(e)")}
                              )) is False,
           "C3: one altered character fails -- byte equality, not resemblance")
        ok(check_sources(tree(tmp, "c3none", [row()])) is True,
           "C3: no renderedAs is valid, and means this source does not render (RW-1.4)")
        ok(check_sources(tree(tmp, "c3empty", [row(renderedAs="  ")])) is False,
           "C3: an empty renderedAs fails -- omit it instead of shipping a blank claim")

        # The release gate.
        old = (_today() - datetime.timedelta(days=400)).isoformat()
        stale_root = tree(tmp, "stale", [row(gated=True, reviewIntervalDays=365,
                                             checkedOn=old)])
        ok(release_gate(stale_root) is False,
           "release-gate fails on a gated source past its interval")
        ok(release_gate(tree(tmp, "fresh", [row(gated=True, reviewIntervalDays=365,
                                                checkedOn=_today().isoformat())])) is True,
           "release-gate passes on a freshly checked source")

        def with_override(name, entry):
            r = tree(tmp, name, [row(gated=True, reviewIntervalDays=365, checkedOn=old)])
            os.makedirs(os.path.join(r, "tools"))
            with open(os.path.join(r, "tools", "release-overrides.json"), "w",
                      encoding="utf-8") as fh:
                json.dump({"overrides": [entry]}, fh)
            return r

        ok(release_gate(with_override("ovok", {
            "source": "demo/s1", "reason": "EUR-Lex unreachable; re-check booked",
            "owner": "D. Galleyne", "date": "2026-08-08"})) is True,
           "a reasoned override lets the release through")
        ok(release_gate(with_override("ovempty", {
            "source": "demo/s1", "reason": "   ",
            "owner": "D. Galleyne", "date": "2026-08-08"})) is False,
           "an override with an empty reason still fails")
        ok(release_gate(with_override("ovnoowner", {
            "source": "demo/s1", "reason": "busy", "date": "2026-08-08"})) is False,
           "an override with no owner still fails -- somebody is answerable")

        # Anti-vacuity, the same rule CAC-GP-1 and CAC-LE-1 apply.
        bare = os.path.join(tmp, "bare")
        os.makedirs(bare)
        ok(check_sources(bare) is False,
           "a tree with no skills fails instead of passing vacuously")
        ok(check_do_not_cite(bare) is False,
           "C5 with no do-not-cite.json fails rather than checking nothing")
        shutil.rmtree(bare, ignore_errors=True)

        # -- The three decisions of 2026-08-09, each recorded as a check rather than a note.
        ok(check_sources(tree(tmp, "phtodo", [row(checkedBy="unverified",
                                                  whyUnverified="TODO")])) is False,
           "RW-1.11: a placeholder `whyUnverified` fails -- the gate lets the row ship, so "
           "this sentence is all that separates unreachable from unopened")
        ok(check_sources(tree(tmp, "phreal", [row(checkedBy="unverified",
                                                  whyUnverified="paywalled; no institutional "
                                                                "access")])) is True,
           "RW-1.11: a real reason passes, and still does not block the release")
        ok(check_sources(tree(tmp, "csself", [row(reviewedBy="claude-code",
                                                  reviewedOn="2026-01-01")])) is False,
           "RW-1.12: a machine countersigning its own reading fails")
        ok(check_sources(tree(tmp, "csnodate", [row(reviewedBy="D Galleyne")])) is False,
           "RW-1.12: `reviewedBy` with no `reviewedOn` fails -- an endorsement that cannot age")
        ok(check_sources(tree(tmp, "csorphan", [row(reviewedOn="2026-01-01")])) is False,
           "RW-1.12: `reviewedOn` with no `reviewedBy` fails -- a date signs nothing")
        ok(check_sources(tree(tmp, "csok", [row(reviewedBy="D Galleyne",
                                                reviewedOn="2026-01-01")])) is True,
           "RW-1.12: a dated human counter-signature passes, beside `checkedBy`")
        ok(check_sources(tree(tmp, "ivbare", [row(gated=True,
                                                  reviewIntervalDays=180)])) is False,
           "RW-1.13: an interval off the house default with no `intervalBecause` fails")
        ok(check_sources(tree(tmp, "ivwhy", [row(gated=True, reviewIntervalDays=180,
                                                 intervalBecause="a disclosure clock where the "
                                                 "harm from a missed amendment is asymmetric")]))
           is True, "RW-1.13: the same interval with a stated reason passes")
        ok(check_sources(tree(tmp, "ivdefault", [row(gated=True, reviewIntervalDays=365,
                                                     intervalBecause="a" * 60)])) is False,
           "RW-1.13: `intervalBecause` on a default-interval row fails -- the default needs no "
           "defence, and a justification reads as a deviation that is not one")

        # -- C6 (BL-190). The converse of C4: a citation nothing declares.
        #
        # The vocabulary fixtures come first. A detector that has quietly stopped matching
        # reports "no undeclared citations" in exactly the tone of a detector that works, so
        # each pattern must be seen to produce the key it claims. This is `mustFlag` from
        # do-not-cite.json applied to the other direction.
        for v in _CITE_VOCAB:
            ok(v["expect"] in cite_keys(v["mustMatch"]),
               "C6 vocab %s: %r yields %s" % (v["id"], v["mustMatch"][:34], v["expect"]))
            for extra in v.get("alsoMatch", ()):
                ok(cite_keys(extra), "C6 vocab %s: %r is still matched" % (v["id"], extra))
        ok(not cite_keys("no designations here, just prose about risk appetite"),
           "C6 vocab: ordinary prose yields no keys -- the detector is not matching noise")

        def c6(name, skill_files, sources, allowlist=None):
            root = os.path.join(tmp, name)
            sk = os.path.join(root, "skills", "demo")
            os.makedirs(sk)
            with open(os.path.join(sk, "SKILL.md"), "w", encoding="utf-8") as fh:
                fh.write("# demo\n")
            for rel, body in skill_files.items():
                p = os.path.join(sk, *rel.split("/"))
                os.makedirs(os.path.dirname(p), exist_ok=True)
                with open(p, "w", encoding="utf-8") as fh:
                    fh.write(body)
            doc = {"schemaVersion": 1, "skill": "demo", "sources": sources}
            if allowlist is not None:
                doc["citationAllowlist"] = allowlist
            with open(os.path.join(sk, "sources.json"), "w", encoding="utf-8") as fh:
                json.dump(doc, fh)
            return root

        cited = {"references/r.md": "We follow NIST SP 800-53 Rev. 5 for controls.\n"}
        ok(check_sources(c6("c6bad", cited,
                            [row(usedFor=["references/r.md"])])) is False,
           "C6: a citation in a covered file that no row declares fails")
        ok(check_sources(c6("c6ok", cited,
                            [row(instrument="NIST SP 800-53 Rev. 5",
                                 usedFor=["references/r.md"])])) is True,
           "C6: the same citation passes once a row declares it")
        # Revisions are NOT collapsed. This is the amendment failure every reference defect in
        # this repo has turned out to be, so a row pinned to r4 must not launder a r5 citation.
        ok(check_sources(c6("c6rev", cited,
                            [row(instrument="NIST SP 800-53 Rev. 4",
                                 usedFor=["references/r.md"])])) is False,
           "C6: a row declaring Rev. 4 does not cover a Rev. 5 citation")
        ok(check_sources(c6("c6iso",
                            {"references/r.md": "held an ISO 27001 certificate\n"},
                            [row(instrument="ISO/IEC 27001:2022 Annex A",
                                 usedFor=["references/r.md"])])) is True,
           "C6: an ISO edition year IS collapsed -- 27001:2022 declares ISO 27001")
        ok(check_sources(c6("c6desig", cited,
                            [row(instrument="the 800-53 family",
                                 designations=["sp-800-53r5"],
                                 usedFor=["references/r.md"])])) is True,
           "C6: an explicit `designations` list declares what prose cannot be parsed for")
        # Scope. C6 asks only that the files a manifest already points at agree with it.
        ok(check_sources(c6("c6scope", dict(cited, **{"references/other.md":
                                                      "See NIST IR 8179.\n"}),
                            [row(instrument="NIST SP 800-53 Rev. 5",
                                 usedFor=["references/r.md"])])) is True,
           "C6: a file no row claims is out of scope -- C6 is the converse of C4, not a "
           "whole-tree scan")

        # The allowlist, and the reason that makes it an argument rather than an off switch.
        ok(check_sources(c6("c6allow", cited, [row(usedFor=["references/r.md"])],
                            allowlist=[{"designation": "sp-800-53r5",
                                        "reason": "named as a crosswalk target, not relied on"}])
           ) is True, "C6: an allowlisted designation with a reason passes")
        ok(check_sources(c6("c6noreason", cited, [row(usedFor=["references/r.md"])],
                            allowlist=[{"designation": "sp-800-53r5", "reason": ""}])) is False,
           "C6: an allowlist entry with an EMPTY reason fails -- otherwise the allowlist is a "
           "way to switch C6 off one line at a time")
        ok(check_sources(c6("c6nokey", cited, [row(usedFor=["references/r.md"])],
                            allowlist=[{"reason": "because"}])) is False,
           "C6: an allowlist entry with no `designation` fails")
        ok(check_sources(c6("c6wrongkey", cited, [row(usedFor=["references/r.md"])],
                            allowlist=[{"designation": "sp-800-53r4",
                                        "reason": "wrong revision"}])) is False,
           "C6: allowlisting a DIFFERENT designation does not excuse this one")

        # -- C5, both directions --
        #
        # The rule is not "never write the string". Naming a withdrawn publication in order to
        # say it is withdrawn is what this repo should do. Both cases are registered, because a
        # ban that also forbids the warning would get switched off within a week.
        def dnc(name, body, entries=None, markers=None, files=None):
            root = os.path.join(tmp, name)
            os.makedirs(os.path.join(root, "tools"))
            os.makedirs(os.path.join(root, "skills", "demo"))
            with open(os.path.join(root, "skills", "demo", "SKILL.md"), "w",
                      encoding="utf-8") as fh:
                fh.write(body)
            # `files` plants content at an arbitrary repo-relative path. Needed for BL-194's
            # scope cases: the defect there was WHICH files C5 read, not what it did with them.
            for rel, text in (files or {}).items():
                p = os.path.join(root, *rel.split("/"))
                os.makedirs(os.path.dirname(p), exist_ok=True)
                with open(p, "w", encoding="utf-8") as fh:
                    fh.write(text)
            with open(os.path.join(root, "tools", "do-not-cite.json"), "w",
                      encoding="utf-8") as fh:
                json.dump({"schemaVersion": 1,
                           "markers": markers if markers is not None else ["withdrawn"],
                           "entries": entries if entries is not None else [
                               {"id": "e", "label": "L",
                                "pattern": r"SP\s*800-61(?!\s*(?:r|Rev\.?\s*)3)",
                                "status": "withdrawn",
                                "supersededBy": "SP 800-61 Rev. 3 — Final, 3 April 2025",
                                "why": "w",
                                "mustFlag": "SP 800-61 Rev. 2"}]}, fh)
            return root

        def _row(**kw):
            base = {"id": "e", "label": "L", "pattern": r"SP\s*800-61",
                    "status": "withdrawn", "supersededBy": "SP 800-61 Rev. 3 — x",
                    "why": "w", "mustFlag": "SP 800-61 Rev. 2"}
            base.update(kw)
            return base

        ok(check_do_not_cite(dnc("d1", "Follow SP 800-61 Rev. 2 for incident handling.\n"))
           is False, "C5: a withdrawn publication cited as guidance fails")
        ok(check_do_not_cite(dnc("d2", "SP 800-61 Rev. 2 is withdrawn; use Rev. 3.\n"))
           is True, "C5: the same string WITH a withdrawal marker passes -- warning, not citing")
        ok(check_do_not_cite(dnc("d3", "We follow SP 800-61 Rev. 3.\n")) is True,
           "C5: the current revision is not matched at all")
        ok(check_do_not_cite(dnc("d4", "See SP 800-61 for the lifecycle.\n")) is False,
           "C5: the bare original, with no revision, fails too")
        far = "SP 800-61 Rev. 2 is the standard.\n" + ("filler. " * 90) + "\nwithdrawn\n"
        ok(check_do_not_cite(dnc("d5", far)) is False,
           "C5: a marker far away does not excuse a bare citation")
        # RW-1.9.1 changed this one deliberately. Under the old proximity window a marker on
        # the NEXT line excused the citation, which is how three of the four BL-194 fail-open
        # cases got through. Same-line binding is stricter and this case now fails; the cost is
        # that hard-wrapped prose must carry the warning on the citation's line, which is
        # better writing anyway.
        ok(check_do_not_cite(dnc("d6", "SP 800-61 Rev. 2.\nThat edition is withdrawn.\n"))
           is False, "C5: a marker on the NEXT line no longer excuses it (RW-1.9.1)")
        ok(check_do_not_cite(dnc("d7", "x\n", entries=[])) is False,
           "C5: an empty entry list fails rather than passing vacuously")
        # BL-204. The "no do-not-cite.json" case earlier stops at the missing registry and
        # never reaches the scan, so the "read no files" bail was asserted by nothing —
        # suppressing that guard left this entire suite green. Its own comment calls an empty
        # scan the failure that reports success forever, and that sentence was guarding itself.
        #
        # A VALID registry with nothing scannable beside it. `tools/do-not-cite.json` is
        # itself on the exempt list, so it does not count as a file read.
        d8 = dnc("d8", "x\n")
        os.remove(os.path.join(d8, "skills", "demo", "SKILL.md"))
        ok(check_do_not_cite(d8) is False,
           "BL-204: C5 with a valid registry but nothing to scan fails — an empty scan is "
           "not a clean bill")

        # -- BL-194. The four reported fail-open cases, plus two invented after fixing them.
        #
        # The plan warned against adding four cases and stopping: four named cases produce a
        # guard that passes four named cases. A and B below were invented independently AFTER
        # the reported four were closed, and both still failed open — which is the evidence
        # that the reported list was not the class.
        ok(check_do_not_cite(dnc("u1", "Follow SP 800‑61 Rev. 2 for IR.\n")) is False,
           "BL-194/1: a non-breaking hyphen U+2011 does not smuggle a citation past")
        ok(check_do_not_cite(dnc("u2", "Follow SP 800–61 Rev. 2 for IR.\n")) is False,
           "BL-194/1b: nor an en-dash U+2013")
        ok(check_do_not_cite(dnc("u3",
                                 "Our old policy was withdrawn.\nUse SP 800-61 Rev. 2.\n"))
           is False, "BL-194/2: unrelated prose saying 'withdrawn' nearby does not excuse")
        ok(check_do_not_cite(
            dnc("u4", "SP 800-53A Rev. 4 is withdrawn. Follow SP 800-61 Rev. 2.\n",
                entries=[_row(), _row(id="f", pattern=r"SP\s*800-53A(?!\s*(?:r|Rev\.?\s*)5)",
                              supersededBy="SP 800-53A Rev. 5 — x",
                              mustFlag="SP 800-53A Rev. 4")])) is False,
           "BL-194/3: a warning about ANOTHER publication on the line does not launder this one")
        ok(check_do_not_cite(dnc("u5",
                                 "See https://x.test/withdrawn/ and use SP 800-61 Rev. 2.\n"))
           is False, "BL-194/A: a marker inside a URL is not prose about the publication")
        # `markers` MUST name "obsolete" here, and this case did not. Without it the word was
        # never a marker candidate at all, so the citation was caught for a reason that had
        # nothing to do with whole-word matching — and replacing `_all_positions` with a plain
        # substring search left the whole suite green. Found while mutation-testing BL-201;
        # the same shape as BL-201 itself, one function along.
        #
        # The `;` also had to go. It is a clause boundary now, which would separate the
        # identifier from the citation and catch it for the wrong reason a second time.
        ok(check_do_not_cite(dnc("u6", "The obsoleteFlag is set, so use SP 800-61 Rev. 2.\n",
                                 markers=["withdrawn", "obsolete"])) is False,
           "BL-194/B: a marker as a substring of an identifier is not a warning")
        ok(check_do_not_cite(dnc("u7", "SP 800-61 Rev. 2 is withdrawn; use Rev. 3.\n")) is True,
           "BL-194 control: a genuine same-line warning still passes")

        # -- BL-201. Clause binding, because "nearest" needs something to be nearer than.
        #
        # The fourth BL-194 fail-open, closed three releases later. (c) is comparative, so with
        # one publication on the line it compared the match against itself and always passed,
        # leaving only same-line binding. Every case below is a SINGLE publication -- the shape
        # the rule was never designed against.
        ok(check_do_not_cite(
            dnc("c1", "The predecessor platform was retired. Follow SP 800-61 Rev. 2 for IR.\n",
                markers=["withdrawn", "retired"])) is False,
           "BL-201: a marker in a PREVIOUS SENTENCE does not excuse the only publication on "
           "the line -- the exact sentence three release tests reported")
        ok(check_do_not_cite(
            dnc("c2", "SP 800-61 Rev. 2 is withdrawn; use Rev. 3.\n")) is True,
           "BL-201 control: the honest single-publication form is still excused")
        ok(check_do_not_cite(
            dnc("c3", "SP 800-61 Rev. 2 — withdrawn, use Rev. 3.\n")) is True,
           "BL-201: a dash and a comma do not end a clause, so the commonest honest forms "
           "still pass")
        ok(check_do_not_cite(
            dnc("c4", "SP 800-61 Rev. 2, withdrawn in 2025, is superseded.\n")) is True,
           "BL-201: nor does comma-delimited apposition around the marker")
        ok(check_do_not_cite(
            dnc("c5", "| SP 800-61 Rev. 2 | our old scanner was withdrawn |\n",
                markers=["withdrawn"])) is False,
           "BL-201: a table cell is a clause -- a marker in a DIFFERENT cell does not excuse")
        ok(check_do_not_cite(
            dnc("c6", "Withdrawn: SP 800-61 Rev. 2 should not be cited.\n")) is True,
           "BL-201: a marker before the citation in the same clause still excuses it")
        ok(check_do_not_cite(
            dnc("c7", "SP 800-53A Rev. 4 is withdrawn and SP 800-61 Rev. 2 is current.\n",
                entries=[_row(), _row(id="f", pattern=r"SP\s*800-53A(?!\s*(?:r|Rev\.?\s*)5)",
                              supersededBy="SP 800-53A Rev. 5 — x",
                              mustFlag="SP 800-53A Rev. 4")])) is False,
           "BL-201: (c) still does its own job -- two publications in ONE clause, the marker "
           "binds to the nearer and does not launder the other")
        # The abbreviation exemption, tested from the direction that would quietly widen it.
        # `Rev. 2` must not end a clause; `retired. 2` must. Without this case the exemption
        # could be loosened to "any full stop followed by a digit" and every acceptance case
        # above would still pass -- while the reported laundering sentence, rephrased with a
        # number after it, would slip through again.
        ok(check_do_not_cite(
            dnc("c8", "The scanner was retired. 2 old tools still cite SP 800-61 Rev. 2\n",
                markers=["withdrawn", "retired"])) is False,
           "BL-201: a real sentence ending before a DIGIT still ends a clause -- the "
           "abbreviation exemption is `Rev.`-shaped, not `any dot before a number`")

        # -- BL-201, the three cases mutation-testing added.
        #
        # The first draft of the eight cases above passed, and then three separate reversions
        # of the fix left it entirely green: clause-scoping (c), the width of the abbreviation
        # exemption, and the in-span cut exclusion were all asserted by nothing. Each case
        # below was built to go red for exactly one of them. A suite that returns the right
        # verdict can still be returning it for the wrong reason, and only running the broken
        # version tells you which.
        ok(check_do_not_cite(
            dnc("c9", "SP 800-61 Rev. 2 is withdrawn. Withdrawn aside, consider also "
                      "SP 800-53A Rev. 4.\n",
                entries=[_row(), _row(id="f", pattern=r"SP\s*800-53A(?!\s*(?:r|Rev\.?\s*)5)",
                              supersededBy="SP 800-53A Rev. 5 — x",
                              mustFlag="SP 800-53A Rev. 4")])) is True,
           "BL-201: nearest-publication is judged WITHIN the clause -- a publication in "
           "another sentence cannot steal a marker and cause a false positive")
        # The in-span cut exclusion. The abbreviation list happens to cover every pattern in
        # today's registry -- `Rev. 1`, `Rev. 2`, `Rev. 4` are all followed by a digit -- so
        # this is the only case that fails when the general rule is removed. It is one letter
        # from mattering in production: the registry already carries patterns whose span
        # contains `Rev. N` (SP 800-18), and a lettered part or an appendix would land here
        # with nothing else to catch it.
        ok(check_do_not_cite(
            dnc("c10", "SP 800-61 Rev. Two is withdrawn.\n",
                entries=[_row(pattern=r"SP\s*800-61\s*Rev\.\s*Two",
                              mustFlag="SP 800-61 Rev. Two")])) is True,
           "BL-201: a full stop INSIDE a matched citation never ends a clause, whatever "
           "follows it -- the general rule the abbreviation list only patches")

        # -- BL-194, second half. WHICH files C5 reads.
        #
        # Every case above tests what C5 does with a line it reads. `docs/` and `research/`
        # were exempt by directory name, so C5 never read them at all — a check that reports
        # success without having tested anything, in the most literal form the repo has found
        # yet. The cases below fix the scope in place: if either name returns to _DNC_EXEMPT,
        # these fail.
        planted = "Follow SP 800-61 Rev. 2 for incident handling.\n"
        ok(check_do_not_cite(dnc("x1", "clean\n", files={"docs/guide.md": planted})) is False,
           "BL-194: a forbidden citation planted under docs/ fails — docs/ is in scope")
        ok(check_do_not_cite(dnc("x2", "clean\n",
                                 files={"research/notes.md": planted})) is False,
           "BL-194: and under research/ — the other removed exemption")
        ok(check_do_not_cite(dnc("x3", "clean\n",
                                 files={"docs/deep/nested/note.md": planted})) is False,
           "BL-194: nested under docs/ too, not just its top level")
        ok(check_do_not_cite(dnc("x4", "clean\n",
                                 files={"docs/guide.md":
                                        "SP 800-61 Rev. 2 is withdrawn; use Rev. 3.\n"}))
           is True, "BL-194 control: a genuine warning under docs/ still passes — the "
                    "directory came into scope, the rule did not change")
        # The exemptions that REMAIN are load-bearing, and deleting them is the opposite
        # over-correction. Each of these files must carry watched designations to do its job.
        ok(check_do_not_cite(dnc("x5", "clean\n", files={"CHANGELOG.md": planted})) is True,
           "BL-194: CHANGELOG.md stays exempt — it records why an entry was added")
        ok(check_do_not_cite(dnc("x6", "clean\n",
                                 files={"tools/sources-schema.md": planted})) is True,
           "BL-194: tools/sources-schema.md stays exempt — it documents the registry")

        # -- BL-195. The registry is trusted, so it is validated before use.
        ok(check_do_not_cite(dnc("r1", "clean\n",
                                 entries=[{"id": "x", "pattern": r"SP\s*800-61"}])) is False,
           "BL-195: an entry missing status/supersededBy/why/mustFlag fails")
        ok(check_do_not_cite(dnc("r2", "clean\n", markers=[])) is False,
           "BL-195: an empty markers list fails -- no warning could ever excuse anything")
        ok(check_do_not_cite(dnc("r3", "clean\n",
                                 entries=[_row(), _row()])) is False,
           "BL-195: a duplicate entry id fails")
        ok(check_do_not_cite(dnc("r4", "clean\n",
                                 entries=[_row(pattern="SP 800-61 (")])) is False,
           "BL-195: a pattern that does not compile fails")
        ok(check_do_not_cite(dnc("r5", "clean\n",
                                 entries=[_row(status="deprecated")])) is False,
           "BL-195: an unknown status fails")
        ok(check_do_not_cite(dnc("r6", "clean\n",
                                 entries=[_row(pattern=r"SP\s*800-99")])) is False,
           "BL-195: a pattern that does not match its own mustFlag fails -- the fixture is "
           "what stops a dead pattern looking like protection")
        ok(check_do_not_cite(dnc("r7", "clean\n",
                                 entries=[_row(mustNotFlag="SP 800-61 Rev. 2")])) is False,
           "BL-195: a pattern that matches its mustNotFlag fails -- it would flag the "
           "replacement edition")

    print("\ncheck-sources self-test: %d checks, %d failed"
          % (len(checks), sum(1 for c in checks if not c)))
    # A floor, because until BL-201 this suite reported its count and asserted nothing about
    # it. A deleted case would have shown up as a smaller number in a line nobody diffs, and
    # "0 failed" reads identically whether 99 checks ran or nine did. The number only has to
    # move when cases are deliberately removed, and then somebody has to say why here.
    _FLOOR = 102
    if len(checks) < _FLOOR:
        print("FAILED: only %d checks ran, expected at least %d — cases have been removed. "
              "Lower the floor deliberately or put them back." % (len(checks), _FLOOR))
        return False
    return all(checks)


def main(argv):
    if "--self-test" in argv:
        return 0 if _self_test() else 1
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for arg in argv:
        if arg not in ("--release-gate",):
            print("ERROR: unknown argument %r.\n       %s" % (arg, USAGE))
            return 1
    passed = check_sources(root)
    passed = check_do_not_cite(root) and passed
    if "--release-gate" in argv:
        passed = release_gate(root) and passed
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
