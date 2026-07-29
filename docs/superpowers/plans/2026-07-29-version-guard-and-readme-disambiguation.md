# Version Guard and README Disambiguation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make plugin-version drift impossible to ship, converge the four version strings on
`0.4.2`, and stop the README from letting a reader mistake the 60% coverage guard for a currency
threshold.

**Architecture:** A new build-time script `tools/check-versions.py` performs two checks —
*consistency* (all four version strings agree) and *bump-on-change* (if shipped content moved
against the merge base, the version moved too). It is wired into the existing `evals` workflow on
the same principle that workflow already states: a release checklist a human has to remember is
not a check. The README fix is prose only: it separates *coverage* from *currency* in the two
adjacent bullets that a domain reviewer already fused on reading.

**Tech Stack:** Python 3.9+ stdlib only (`json`, `subprocess`, `pathlib`, `tempfile`), GitHub
Actions, Markdown. No new dependencies — `tools/README.md` documents that constraint and this
plan honours it.

---

## Context an engineer needs before starting

**Why this exists.** Commit `18cfec5` bumped `.claude-plugin/plugin.json` from `0.4.0` to `0.4.1`
and left the other three version strings at `0.4.0`. Because `claude plugin update` reads
`.claude-plugin/marketplace.json`, the `0.4.1` fixes were never reachable by an install. Worse,
four of the five fix commits on that branch (`6e13e38`, `bb5c834`, `bad2010`, `a8dc6da`) bumped
nothing at all. A stale plugin cache has previously cost a bad test run, so this class of bug is
known-expensive here.

**The four version strings** (there is no fifth — `.agents/plugins/marketplace.json` uses
`source: local, path: ./` and carries no version of its own):

| File | JSON path | Current |
|---|---|---|
| `.claude-plugin/plugin.json` | `version` | `0.4.1` |
| `.claude-plugin/marketplace.json` | `version` | `0.4.0` |
| `.claude-plugin/marketplace.json` | `plugins[0].version` | `0.4.0` |
| `.codex-plugin/plugin.json` | `version` | `0.4.0` |

**Target version: `0.4.2`.** Not `0.4.1`. `0.4.1` was never coherently published — marketplace.json
always advertised `0.4.0` — but any clone taken since `18cfec5` has a tree calling itself `0.4.1`.
Reusing that number would make one version string name two different trees, which is the exact
ambiguity that caused the stale-cache incident.

**Repo conventions to follow:**
- `tools/` is build-time only and ships to nobody. Skill `evals/` directories live under `skills/`
  and therefore *do* ship, which is why this check does not go there.
- Python floor is **3.9** (pinned in CI). No `match`, no `X | Y` type unions at runtime, no
  `str.removeprefix` (3.9 has it — fine — but avoid 3.10+ syntax).
- Self-tests print `N/N checks passed` and exit non-zero on failure, matching
  `score_register.py self-test` and `profile_analysis.py self-test`.

**Baseline (measured 2026-07-29, must stay green):** `risk-register` self-test 34/34,
`nist-csf` self-test 472/472.

---

## File Structure

| File | Status | Responsibility |
|---|---|---|
| `tools/check-versions.py` | Create | Both version checks plus its own self-test. Single responsibility: the manifests agree, and they move when shipped content moves. Knows nothing about skills or scoring. |
| `.claude-plugin/plugin.json` | Modify (line 4) | Version string → `0.4.2` |
| `.claude-plugin/marketplace.json` | Modify (lines 8, 14) | Both version strings → `0.4.2` |
| `.codex-plugin/plugin.json` | Modify (line 3) | Version string → `0.4.2` |
| `.github/workflows/evals.yml` | Modify | New `manifests` job invoking the check; `fetch-depth: 0` so the base ref is reachable |
| `tools/README.md` | Modify (lines 1–8) | Scope sentence widened from "regenerate reference data" to also cover repo guards |
| `README.md` | Modify (lines 75–81) | Coverage-vs-currency disambiguation |

---

### Task 1: The consistency check (fails against the repo as it stands)

**Files:**
- Create: `tools/check-versions.py`

This task deliberately ends **red**. The repo is currently in the drifted state, so a correct
check must fail here. Task 2 turns it green by fixing the data, not the check.

- [ ] **Step 1: Write the script with the consistency check only**

Create `tools/check-versions.py` with exactly this content:

```python
#!/usr/bin/env python3
"""Version-manifest guard.

Four version strings describe this plugin, across three files. They must agree with
each other, and they must move when shipped content moves.

Both halves exist because both halves failed. Commit 18cfec5 bumped
.claude-plugin/plugin.json to 0.4.1 and left the other three at 0.4.0 -- and since
`claude plugin update` reads .claude-plugin/marketplace.json, those 0.4.1 fixes were
not reachable by any install. On the same branch, four of five fix commits bumped
nothing at all.

That is the same shape as the v0.1.4 incident that put evals.yml on every push, and it
gets the same answer, already written at the top of that workflow: a release checklist
a human has to remember is not a check.

  ./tools/check-versions.py                 # consistency only
  ./tools/check-versions.py --base <ref>    # consistency + bump-on-change
  ./tools/check-versions.py --self-test     # exercise both checks in a scratch repo

Exit 0 = all checks passed. Exit 1 = at least one failed, with the reason.
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

# Every version string that describes this plugin. .agents/plugins/marketplace.json is
# deliberately absent: it declares `source: local, path: ./` and carries no version of
# its own, so it inherits and cannot drift.
MANIFESTS = (
    (".claude-plugin/plugin.json", ("version",)),
    (".claude-plugin/marketplace.json", ("version",)),
    (".claude-plugin/marketplace.json", ("plugins", 0, "version")),
    (".codex-plugin/plugin.json", ("version",)),
)

# Path prefixes whose contents reach a user's install. Changing any of them obliges a
# version bump. docs/, tools/, .github/ and the top-level prose files are excluded on
# purpose -- a spec or a CI tweak is not a release.
SHIPPED = ("skills/", "assets/", ".claude-plugin/", ".codex-plugin/", ".agents/")


def _dig(doc, keypath):
    """Walk a JSON document by a tuple of keys/indices."""
    for k in keypath:
        doc = doc[k]
    return doc


def _label(path, keypath):
    return "{}:{}".format(path, ".".join(str(k) for k in keypath))


def read_versions(root="."):
    """[(label, version)] for all four manifest entries."""
    out = []
    for path, keypath in MANIFESTS:
        doc = json.loads((Path(root) / path).read_text(encoding="utf-8"))
        out.append((_label(path, keypath), _dig(doc, keypath)))
    return out


def check_consistency(root="."):
    rows = read_versions(root)
    for label, v in rows:
        print("  {:<52} {}".format(label, v))
    distinct = sorted({v for _, v in rows})
    if len(distinct) == 1:
        print("consistency: all {} version strings agree ({}).".format(
            len(rows), distinct[0]))
        return True
    print("ERROR: {} different versions across {} manifest entries: {}".format(
        len(distinct), len(rows), ", ".join(distinct)))
    print("       `claude plugin update` reads .claude-plugin/marketplace.json.")
    print("       A version that moved only in plugin.json never reaches an install.")
    return False


def main(argv):
    args = list(argv[1:])
    if "--self-test" in args:
        return 0 if self_test() else 1
    base = None
    if "--base" in args:
        i = args.index("--base")
        if i + 1 >= len(args):
            print("ERROR: --base needs a git ref")
            return 1
        base = args[i + 1]
    passed = check_consistency()
    if base is not None:
        passed = check_bump(base) and passed
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
```

`check_bump` and `self_test` are added in Task 3. Until then `--base` and `--self-test`
raise `NameError`, which is fine — nothing calls them yet and Task 3 lands before CI does.

- [ ] **Step 2: Make it executable**

```bash
chmod +x tools/check-versions.py
```

- [ ] **Step 3: Run it and verify it FAILS**

```bash
./tools/check-versions.py; echo "exit=$?"
```

Expected output — this is the red state we want:

```
  .claude-plugin/plugin.json:version                   0.4.1
  .claude-plugin/marketplace.json:version              0.4.0
  .claude-plugin/marketplace.json:plugins.0.version    0.4.0
  .codex-plugin/plugin.json:version                    0.4.0
ERROR: 2 different versions across 4 manifest entries: 0.4.0, 0.4.1
       `claude plugin update` reads .claude-plugin/marketplace.json.
       A version that moved only in plugin.json never reaches an install.
exit=1
```

If it exits 0, the check is wrong — the drift is real and documented above. Stop and fix
the script before continuing.

- [ ] **Step 4: Verify it runs on the Python floor (3.9)**

```bash
python3 -c 'import sys; print(sys.version_info[:2])'
python3 -m py_compile tools/check-versions.py && echo "compiles"
```

Expected: `compiles`. If a 3.9 interpreter is available, prefer
`python3.9 -m py_compile tools/check-versions.py`.

- [ ] **Step 5: Commit**

```bash
git add tools/check-versions.py
git commit -m "test(tools): version-manifest guard, currently failing

Four version strings across three files, and they do not agree: plugin.json
says 0.4.1 while marketplace.json (both entries) and the codex manifest say
0.4.0. Since \`claude plugin update\` reads marketplace.json, the 0.4.1 fixes
were never reachable by an install.

The check is committed red on purpose. The next commit fixes the data.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Converge the manifests on 0.4.2

**Files:**
- Modify: `.claude-plugin/plugin.json:4`
- Modify: `.claude-plugin/marketplace.json:8`
- Modify: `.claude-plugin/marketplace.json:14`
- Modify: `.codex-plugin/plugin.json:3`

- [ ] **Step 1: Set all four strings to 0.4.2**

`.claude-plugin/plugin.json` line 4 — change:

```json
  "version": "0.4.1",
```

to:

```json
  "version": "0.4.2",
```

`.claude-plugin/marketplace.json` line 8 (the marketplace's own version) — change:

```json
  "version": "0.4.0",
```

to:

```json
  "version": "0.4.2",
```

`.claude-plugin/marketplace.json` line 14 (inside `plugins[0]`) — change:

```json
      "version": "0.4.0",
```

to:

```json
      "version": "0.4.2",
```

`.codex-plugin/plugin.json` line 3 — change:

```json
  "version": "0.4.0",
```

to:

```json
  "version": "0.4.2",
```

- [ ] **Step 2: Run the check and verify it PASSES**

```bash
./tools/check-versions.py; echo "exit=$?"
```

Expected:

```
  .claude-plugin/plugin.json:version                   0.4.2
  .claude-plugin/marketplace.json:version              0.4.2
  .claude-plugin/marketplace.json:plugins.0.version    0.4.2
  .codex-plugin/plugin.json:version                    0.4.2
consistency: all 4 version strings agree (0.4.2).
exit=0
```

- [ ] **Step 3: Verify all four files are still valid JSON**

```bash
for f in .claude-plugin/plugin.json .claude-plugin/marketplace.json .codex-plugin/plugin.json .agents/plugins/marketplace.json; do
  python3 -c "import json,sys; json.load(open('$f')); print('ok  $f')"
done
```

Expected: four `ok` lines. A trailing comma or a missing quote from a hand edit shows up here.

- [ ] **Step 4: Commit**

```bash
git add .claude-plugin/plugin.json .claude-plugin/marketplace.json .codex-plugin/plugin.json
git commit -m "chore: converge all four version strings on 0.4.2

0.4.1 was never coherently published -- marketplace.json always advertised
0.4.0, so no \`claude plugin update\` ever delivered it. But clones taken since
18cfec5 carry a tree calling itself 0.4.1, so reusing that number would let one
version string name two different trees. 0.4.2 is a fresh number that does not.

tools/check-versions.py now passes.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: The bump-on-change check, with a self-test

**Files:**
- Modify: `tools/check-versions.py`

This is the check that would have caught four of the five commits on the current branch.

- [ ] **Step 1: Write the self-test first (it will fail — `check_bump` does not exist)**

Insert these functions into `tools/check-versions.py`, immediately **after** `check_consistency`
and **before** `main`:

```python
# -- self-test ------------------------------------------------------------------


def _write_manifests(root, version):
    """Lay down the four version strings in a scratch tree."""
    (root / ".claude-plugin").mkdir(parents=True, exist_ok=True)
    (root / ".codex-plugin").mkdir(parents=True, exist_ok=True)
    (root / ".claude-plugin" / "plugin.json").write_text(
        json.dumps({"version": version}), encoding="utf-8")
    (root / ".claude-plugin" / "marketplace.json").write_text(
        json.dumps({"version": version, "plugins": [{"version": version}]}),
        encoding="utf-8")
    (root / ".codex-plugin" / "plugin.json").write_text(
        json.dumps({"version": version}), encoding="utf-8")


def _git_commit(root, message):
    """Commit everything in a scratch repo, with identity supplied inline so the
    check never depends on the runner's global git config."""
    subprocess.run(["git", "-C", str(root), "add", "-A"], check=True,
                   capture_output=True)
    subprocess.run(
        ["git", "-C", str(root),
         "-c", "user.email=selftest@example.invalid", "-c", "user.name=selftest",
         "commit", "-q", "-m", message],
        check=True, capture_output=True)
    return subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"],
                          check=True, capture_output=True, text=True).stdout.strip()


def self_test():
    checks = []

    def ok(cond, label):
        checks.append(bool(cond))
        print("{:<4} {}".format("PASS" if cond else "FAIL", label))

    with tempfile.TemporaryDirectory() as tmp:
        # -- consistency, no git needed --
        agree = Path(tmp) / "agree"
        agree.mkdir()
        _write_manifests(agree, "1.2.3")
        ok(check_consistency(str(agree)) is True,
           "four matching version strings pass consistency")

        drift = Path(tmp) / "drift"
        drift.mkdir()
        _write_manifests(drift, "1.2.3")
        (drift / ".codex-plugin" / "plugin.json").write_text(
            json.dumps({"version": "1.2.4"}), encoding="utf-8")
        ok(check_consistency(str(drift)) is False,
           "one divergent version string fails consistency")

        # -- bump-on-change, needs a real repo --
        repo = Path(tmp) / "repo"
        repo.mkdir()
        subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True,
                       capture_output=True)
        _write_manifests(repo, "1.0.0")
        (repo / "skills").mkdir()
        (repo / "skills" / "SKILL.md").write_text("v1\n", encoding="utf-8")
        (repo / "docs").mkdir()
        (repo / "docs" / "note.md").write_text("note\n", encoding="utf-8")
        base = _git_commit(repo, "base")

        # shipped file changed, version did not -> must fail
        (repo / "skills" / "SKILL.md").write_text("v2\n", encoding="utf-8")
        _git_commit(repo, "shipped change, no bump")
        ok(check_bump(base, str(repo)) is False,
           "shipped change without a version bump fails")

        # same change, now with a bump -> must pass
        _write_manifests(repo, "1.0.1")
        _git_commit(repo, "bump")
        ok(check_bump(base, str(repo)) is True,
           "shipped change with a version bump passes")

        # docs-only change against the new base -> no bump required
        base2 = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"],
                               check=True, capture_output=True,
                               text=True).stdout.strip()
        (repo / "docs" / "note.md").write_text("note v2\n", encoding="utf-8")
        _git_commit(repo, "docs only")
        ok(check_bump(base2, str(repo)) is True,
           "docs-only change needs no version bump")

    print("\nself-test: {}/{} checks passed".format(sum(checks), len(checks)))
    return all(checks)
```

- [ ] **Step 2: Run the self-test and verify it fails on the missing function**

```bash
./tools/check-versions.py --self-test; echo "exit=$?"
```

Expected: the two consistency checks print `PASS`, then a traceback ending in
`NameError: name 'check_bump' is not defined`. That is the red state.

- [ ] **Step 3: Implement `check_bump`**

Insert this function immediately **after** `check_consistency` and **before** the
`# -- self-test` divider added in Step 1:

```python
def _git(args, root="."):
    return subprocess.run(["git", "-C", str(root)] + args, check=True,
                          capture_output=True, text=True).stdout


def check_bump(base, root="."):
    """If anything under SHIPPED changed against `base`, the version must have moved.

    Diffs with `base...HEAD` (three dots) so the comparison is against the merge base,
    not the tip of the base branch -- otherwise unrelated commits landing on main
    while a PR is open would be counted as this PR's changes.
    """
    try:
        changed = _git(["diff", "--name-only", "{}...HEAD".format(base)], root).split()
    except subprocess.CalledProcessError:
        print("ERROR: cannot diff against base ref {!r}.".format(base))
        print("       Does this checkout have full history? CI needs fetch-depth: 0.")
        return False

    shipped = sorted(f for f in changed if f.startswith(SHIPPED))
    if not shipped:
        print("bump: no shipped file changed against {}; no bump required.".format(base))
        return True

    path, keypath = MANIFESTS[0]
    try:
        before = _dig(json.loads(_git(["show", "{}:{}".format(base, path)], root)),
                      keypath)
    except (subprocess.CalledProcessError, KeyError, ValueError):
        print("bump: {} unreadable at {}; treating as a first release.".format(
            path, base))
        return True

    now = _dig(json.loads((Path(root) / path).read_text(encoding="utf-8")), keypath)
    if now != before:
        print("bump: {} shipped file(s) changed and the version moved {} -> {}.".format(
            len(shipped), before, now))
        return True

    print("ERROR: {} shipped file(s) changed against {}, but the version is still "
          "{}.".format(len(shipped), base, now))
    for f in shipped[:10]:
        print("         {}".format(f))
    if len(shipped) > 10:
        print("         ... and {} more".format(len(shipped) - 10))
    print("       An unchanged version makes `claude plugin update` a silent no-op.")
    return False
```

- [ ] **Step 4: Run the self-test and verify it passes**

```bash
./tools/check-versions.py --self-test; echo "exit=$?"
```

Expected — five checks, all passing (interleaved with the manifest listings
`check_consistency` prints):

```
PASS four matching version strings pass consistency
PASS one divergent version string fails consistency
PASS shipped change without a version bump fails
PASS shipped change with a version bump passes
PASS docs-only change needs no version bump

self-test: 5/5 checks passed
exit=0
```

- [ ] **Step 5: Verify the real repo still passes consistency**

```bash
./tools/check-versions.py; echo "exit=$?"
```

Expected: `consistency: all 4 version strings agree (0.4.2).` and `exit=0`.

- [ ] **Step 6: Verify it compiles on the Python floor**

```bash
python3 -m py_compile tools/check-versions.py && echo "compiles"
```

Expected: `compiles`.

- [ ] **Step 7: Commit**

```bash
git add tools/check-versions.py
git commit -m "feat(tools): fail a PR that changes shipped content without a bump

Consistency alone would not have caught the real failure: four of the five fix
commits on this branch bumped nothing at all, and each was internally consistent
at 0.4.0. This adds the check that fires on them.

Scoped to skills/, assets/ and the three manifest directories. A change to docs/,
tools/ or .github/ is not a release and needs no bump. Diffs against the merge
base rather than the base tip, so commits landing on main while a PR is open are
not attributed to the PR.

Self-test builds a scratch git repo and exercises both directions of both checks.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Wire the guard into CI

**Files:**
- Modify: `.github/workflows/evals.yml`

- [ ] **Step 1: Add the `manifests` job**

Append this job to the end of `.github/workflows/evals.yml`, at the same indentation as the
existing `floor:` and `rendered:` jobs (two spaces):

```yaml
  manifests:
    # A version that only moves in one of four places is the same class of bug as the
    # v0.1.4 Python-3.12 construct: a release step a human had to remember. 18cfec5
    # bumped plugin.json to 0.4.1 and left marketplace.json -- which is the file
    # `claude plugin update` actually reads -- at 0.4.0, so those fixes reached nobody.
    name: Version manifests agree, and moved
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          # check-versions.py diffs against the merge base. A shallow clone has no
          # merge base, and the check would report an error it cannot resolve.
          fetch-depth: 0

      - uses: actions/setup-python@v5
        with:
          python-version: '3.9'

      - name: The guard's own self-test
        run: ./tools/check-versions.py --self-test

      - name: All four version strings agree
        run: ./tools/check-versions.py

      - name: Shipped changes carry a version bump
        if: github.event_name == 'pull_request'
        run: ./tools/check-versions.py --base "${{ github.event.pull_request.base.sha }}"
```

- [ ] **Step 2: Verify the workflow file is valid YAML**

```bash
python3 -c "
import json, sys
try:
    import yaml
except ImportError:
    print('pyyaml absent; skipping (CI will parse it)'); sys.exit(0)
d = yaml.safe_load(open('.github/workflows/evals.yml'))
print('jobs:', sorted(d['jobs']))
assert 'manifests' in d['jobs'], 'manifests job missing'
print('ok')
"
```

Expected: `jobs: ['floor', 'manifests', 'rendered']` then `ok` — or the skip line if
PyYAML is not installed, which is acceptable since the workflow is parsed by GitHub anyway.

- [ ] **Step 3: Simulate the PR check locally against main**

```bash
./tools/check-versions.py --base "$(git merge-base main HEAD)"; echo "exit=$?"
```

Expected: `exit=0`, reporting that shipped files changed and the version moved
`0.4.0 -> 0.4.2`. (Shipped files changed on this branch include
`skills/risk-register/references/schema.md` from the earlier name fix.)

- [ ] **Step 4: Confirm the pre-existing suites are still green**

```bash
python3 skills/risk-register/scripts/score_register.py self-test | tail -2
python3 skills/nist-csf/scripts/profile_analysis.py self-test | tail -1
```

Expected: `34/34 checks passed.` and `self-test: 472/472 checks passed`. Neither should have
moved — this plan touches no engine code.

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/evals.yml
git commit -m "ci: run the version guard on every push and PR

Both checks, plus the guard's own self-test so a broken guard cannot report a
green tick. fetch-depth: 0 because the bump check diffs against the merge base
and a shallow clone has none.

The bump check is PR-only: a push to main has no meaningful base to compare
against.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: Widen the `tools/` scope statement

**Files:**
- Modify: `tools/README.md:1-8`

`tools/README.md` currently says everything in the directory "regenerate[s] bundled reference
data from its published sources." `check-versions.py` does not, so the description is now false.
The load-bearing claim — *not part of the plugin* — stays exactly as it is.

- [ ] **Step 1: Replace the opening paragraphs**

Change lines 1–8 from:

```markdown
# Build-time tools

**Not part of the plugin.** Nothing here ships to users or is loaded by a skill. These scripts
regenerate bundled reference data from its published sources.

They exist so that `skills/nist-csf/references/nist-csf-2.0-core.json` is reproducible. Without
them the file is a 389K blob nobody can regenerate, verify, or update when NIST publishes a
revision.
```

to:

```markdown
# Build-time tools

**Not part of the plugin.** Nothing here ships to users or is loaded by a skill. These scripts
either regenerate bundled reference data from its published sources, or guard a repo-wide
invariant that no single skill owns.

The generators exist so that `skills/nist-csf/references/nist-csf-2.0-core.json` is reproducible.
Without them the file is a 389K blob nobody can regenerate, verify, or update when NIST publishes
a revision.

The guards live here rather than in a skill's `evals/` directory for the same reason everything
else here does: `skills/**` ships to users, and a check about the repo's own manifests is not
something a user should be shipped.

| Guard | What it enforces |
|---|---|
| `check-versions.py` | The four plugin version strings agree, and they move whenever shipped content moves. Run by the `manifests` job in `.github/workflows/evals.yml`. |
```

- [ ] **Step 2: Verify the file still reads correctly**

```bash
head -25 tools/README.md
```

Expected: the new opening, with the "Regenerating the CSF 2.0 Core" heading still intact
below it.

- [ ] **Step 3: Commit**

```bash
git add tools/README.md
git commit -m "docs(tools): the directory holds guards as well as generators

check-versions.py does not regenerate reference data, so the opening description
no longer covered everything in the directory. Records why guards live here and
not in a skill's evals/ -- skills/** ships, and a check about our own manifests
should not.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: Separate coverage from currency in the README

**Files:**
- Modify: `README.md:75-81`

An external reviewer with strong domain credentials read these two adjacent bullets and fused
them into "a 60% currency threshold", then built a whole design critique on that reading. The
bullets are individually accurate; the failure is that nothing tells the reader they govern
different things. This task fixes only the disambiguation. The age-band wording arrives with the
graded-age implementation (§5 of
`docs/superpowers/specs/2026-07-29-staleness-graded-age-design.md`) and must **not** be added
here — it would describe behaviour that does not exist yet.

- [ ] **Step 1: Replace both bullets**

Change `README.md` lines 75–81 from:

```markdown
- **The scope guard suppresses rather than caveats.** Below 60% of in-scope Subcategories assessed,
  the headline coverage figure does not render at all. A percentage with a warning beside it is still
  a percentage, and people read the number. This binds *both* dashboards — otherwise the suppressed
  figure just reappears one document over.
- **Ratings do not expire.** A rating is questioned when newer material is recorded against it, or
  when it carries no confirmation date to compare against — not because a timer ran out. Age is
  reported; the reader judges.
```

to:

```markdown
- **The scope guard measures coverage, not currency — and suppresses rather than caveats.** Below
  60% of in-scope Subcategories *assessed*, the headline coverage figure does not render at all. A
  percentage with a warning beside it is still a percentage, and people read the number. This binds
  *both* dashboards — otherwise the suppressed figure just reappears one document over. The 60%
  counts how much of the framework anyone has assessed; it says nothing about how old any rating is,
  and no threshold anywhere in this toolkit expires one. Age is governed entirely by the next bullet.
- **Ratings do not expire.** A rating is questioned when newer material is recorded against it, or
  when it carries no confirmation date to compare against — never because a timer ran out. Age is
  reported and the reader judges: a governance outcome and an asset inventory go stale at completely
  different rates, so the engine declines to pick a decay rate on your behalf.
```

- [ ] **Step 2: Verify both concepts are now named explicitly**

```bash
grep -n "coverage, not currency" README.md
grep -n "no threshold anywhere in this toolkit expires one" README.md
grep -n "declines to pick a decay rate" README.md
```

Expected: one line number from each — 75, 79 and 84 respectively, give or take the reflow.
Zero hits from any of them means the edit did not land.

- [ ] **Step 3: Confirm no band wording leaked in early**

```bash
grep -ni "ageThresholdDays\|age band\|wellBeyond" README.md || echo "clean — no unimplemented behaviour described"
```

Expected: `clean — no unimplemented behaviour described`. Any hit means Task 6 has
described the graded-age feature before it exists.

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: the 60% guard is coverage, not currency — say so

A reviewer with RMF/FedRAMP credentials read these two adjacent bullets, fused
them into 'a 60% currency threshold', and wrote a design critique on that basis.
Each bullet was accurate alone; nothing told the reader they govern different
things.

Names the distinction outright and points the reader from one bullet to the
other. Deliberately does not mention age bands: that behaviour is specified but
not yet built.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

## Final verification

- [ ] **Run everything that CI will run**

```bash
cd "$(git rev-parse --show-toplevel)"
./tools/check-versions.py --self-test | tail -2
./tools/check-versions.py | tail -1
./tools/check-versions.py --base "$(git merge-base main HEAD)" | tail -1
python3 skills/risk-register/scripts/score_register.py self-test | tail -2
python3 skills/nist-csf/scripts/profile_analysis.py validate | tail -1
python3 skills/nist-csf/scripts/profile_analysis.py self-test | tail -1
python3 skills/nist-csf/scripts/csfa_compat.py self-test | tail -1
./skills/risk-register/evals/python-compat.sh "$(command -v python3)" | tail -3
PY="$(command -v python3)" ./skills/risk-register/evals/board-safety.sh | tail -3
```

Expected: `5/5 checks passed`, `all 4 version strings agree (0.4.2)`, a bump line reporting
`0.4.0 -> 0.4.2`, `34/34 checks passed.`, `472/472 checks passed`, and clean runs from
`csfa_compat`, `python-compat.sh` and `board-safety.sh`.

- [ ] **Confirm the tree is clean and the history reads correctly**

```bash
git status --short
git log --oneline -6
```

Expected: no modified files, and six new commits in the order test → fix → feature → ci →
docs → docs.

---

## Out of scope

Named so they do not get pulled in:

- **The graded-age implementation itself.** That is
  `docs/superpowers/specs/2026-07-29-staleness-graded-age-design.md` and needs its own plan.
- **Retroactively bumping the four commits that skipped a version.** History is not rewritten;
  `0.4.2` covers all of them.
- **An automated guard on the README wording.** A grep asserting prose survives a rewrite is
  brittle and would fail on legitimate rewording. The spec's §5 docs pass revisits this section
  anyway.
- **Publishing or tagging `0.4.2`.** This plan changes the manifests; releasing is a separate,
  human-initiated act.
