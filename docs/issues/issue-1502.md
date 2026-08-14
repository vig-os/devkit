---
type: issue
state: closed
created: 2026-08-14T06:47:04Z
updated: 2026-08-14T08:48:23Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1502
comments: 3
labels: bug, priority:high, area:ci, effort:small, semver:patch
assignees: none
milestone: 1.10.0
projects: none
parent: none
children: none
synced: 2026-08-14T16:05:16.366Z
---

# [Issue 1502]: [[BUG] Release finalize: the sync-mirror fold passes newline-separated FILE_PATHS to commit-action (which splits on commas), so the archive silently never lands](https://github.com/vig-os/devkit/issues/1502)

### Description

The mirror-archive fold in `release-core.yml` (mirror-mode consumers, #1424) passes
its file list to `vig-os/commit-action` **newline-separated**, but that action
parses `FILE_PATHS` as **comma-separated**. The entire multi-line blob is therefore
treated as a single path, fails the `fs.existsSync` filter, and the action logs
`No files to commit` and returns **successfully**.

Net effect: the archive fold is a silent no-op. Every step is green, the job log
even states `Folding 92 mirror archive path(s) into the release branch`, and
nothing is committed. For a consumer that relies on the fold for QMS traceability,
the issue/PR snapshot silently never reaches the release branch — and therefore
never reaches `main` at promote.

The same workflow gets the contract right 135 lines earlier for the finalization
commit (`release-core.yml:540`):

```yaml
FILE_PATHS: ${{ steps.bundle.outputs.has_bundle == 'true' && format('CHANGELOG.md,{0}', steps.artifact.outputs.dist_paths) || 'CHANGELOG.md' }}
```

That path is comma-joined. The fold path is not. Single-file callers (the changelog
freeze, `FILE_PATHS: CHANGELOG.md`) can never expose the bug because they need no
separator, which is why this survived until the first multi-file fold ran.

### Steps to Reproduce

1. A trunk-mode consumer with `DEVKIT_SYNC_TARGET=sync/issue-mirror` whose mirror
   branch carries `docs/issues` and/or `docs/pull-requests` that the release
   branch does not (e.g. `vig-os/org-config`, first release through the train).
2. Run the release train to a **final** kind: `prepare-release.yml`, then
   `release.yml` with `release-kind=final`.
3. Watch the `Finalize Release Core` job, steps *Stage sync mirror archive for fold*
   -> *Commit folded archive to the release branch*.
4. Inspect the release branch afterwards (via the API, not a possibly-stale local
   ref): `gh api repos/OWNER/REPO/contents/docs?ref=release/X.Y.Z`.

### Expected Behavior

The 92 changed archive paths are committed to `release/X.Y.Z` as
`chore: fold sync mirror archive into release X.Y.Z`, so the snapshot rides the
release PR into `main` at promote — and if for any reason zero files are
committed after a non-zero path list was computed, the step **fails loudly**
rather than reporting success.

### Actual Behavior

`commit-action` logs `No files to commit` and exits 0. No commit is created, the
release branch head is unchanged, and the job is green.

Observed on `vig-os/org-config` release `v1.1.0`
([run 31774787793](https://github.com/vig-os/org-config/actions/runs/31774787793)):

```text
Folding 92 mirror archive path(s) into the release branch.
##[group]Run vig-os/commit-action@0361e9aa65b64711a18286ac5dfdcba7cc7a2ac7
  TARGET_BRANCH: refs/heads/release/1.1.0
  COMMIT_MESSAGE: chore: fold sync mirror archive into release 1.1.0
  FILE_PATHS: docs/issues/issue-1.md
docs/issues/issue-100.md
docs/issues/issue-101.md
  ... (92 paths, newline-separated)
Using TARGET_BRANCH: release/1.1.0
No files to commit
```

Release branch after the run: still at the finalize commit `6048a3c`, `docs/`
contains only `.gitkeep`, `COMMIT_MESSAGE_STANDARD.md`, `DOWNSTREAM_RELEASE.md`,
`adr`, `runbooks` — no `issues`, no `pull-requests`. The mirror branch still holds
all 55 issue files, so nothing was lost, but nothing was folded either.

### Environment

- **Devkit version**: 1.9.0 (`DEVKIT_VERSION=1.9.0`), consumer `vig-os/org-config`
- **Consumer config**: `DEVKIT_WORKFLOW=trunk`, `DEVKIT_MODE=direnv`,
  `DEVKIT_TAG_PREFIX=v`, `DEVKIT_SYNC_TARGET=sync/issue-mirror`
- **Action**: `vig-os/commit-action@0361e9aa65b64711a18286ac5dfdcba7cc7a2ac7` (v0.3.2)
- **Runner**: GitHub-hosted `ubuntu-24.04`; failure is logic, not host-dependent

### Additional Context

**The consumer's contract is documented and unambiguous** —
`vig-os/commit-action` `README.md:51`:

> `FILE_PATHS` - Comma-separated list of file paths or directories (or auto-detects from git status)

**The producer** (`release-core.yml:658-663`) emits a newline-delimited heredoc
output:

```bash
CHANGED="$(git status --porcelain -- docs/issues docs/pull-requests | awk '{print $2}')"
...
{
  echo "file_paths<<PATHS_EOF"
  printf '%s\n' "$CHANGED"
  echo "PATHS_EOF"
} >> "$GITHUB_OUTPUT"
```

**Where it dies** — `commit-action` `src/commit-runner.ts:134-152`:

```ts
const paths = process.env.FILE_PATHS.split(',')      // one giant string
  .map((p) => p.trim())
  .filter((p) => p.length > 0);
for (const pathItem of paths) {
  if (fs.existsSync(pathItem)) { ... }               // false -> nothing pushed
}
...
if (filePaths.length === 0 && !allowEmpty) {
  core.info('No files to commit');                   // success, not failure
  return;
}
```

This is the second silent-success defect found in this release train in as many
days (cf. #1479, where a trunk render produced an unopenable PR). Both were
invisible to review and to the existing tests, and both surfaced only on a real
run — which is the part worth fixing structurally, not just the separator.

### Possible Solution

**Primary (one line, devkit side).** Join the fold list with commas, matching the
convention `release-core.yml:540` already uses:

```bash
CHANGED="$(git status --porcelain -- docs/issues docs/pull-requests | awk '{print $2}' | paste -sd, -)"
```

and emit it as a single-line output rather than a heredoc.

**Guard (devkit side, recommended regardless).** The step already knows how many
paths it computed. After the commit-action step, assert the branch actually moved
— or have the fold step fail when `eligible == 'true'` produced no new commit. A
leg that announces "Folding 92 paths" and commits zero must not be green.

**Robustness (commit-action side, optional).** Accept newlines as a separator
alongside commas (`.split(/[,\n]/)`); a path list is far more naturally
newline-delimited in shell, and the current strictness fails open. If accepted,
note that comma-splitting also makes paths containing commas unrepresentable.

**Unrelated latent bug in the same line.** `awk '{print $2}'` mis-parses
`git status --porcelain` for renames (`R  old -> new` yields `old`) and truncates
paths containing spaces. `git status --porcelain -z` with NUL parsing, or
`git diff --name-only`, would be correct for both.

Refs #1424, #1479.

---

# [Comment #1]() by [c-vigo]()

_Posted on August 14, 2026 at 06:58 AM_

Cross-link: #1503 (promote's `reset-sync-mirror` 403s because checkout's persisted extraheader overrides the App token).

**Ordering matters between these two.** With this issue fixed first, the archive folds normally and the reset is safe. With #1503 fixed first while this one is still open, the next promote force-pushes `sync/issue-mirror` onto a `main` that carries no archive — deleting the only ref holding the snapshots.

On `vig-os/org-config` v1.1.0 the 403 is the sole reason the 55 issue files still exist. Please land this one first, or land #1503 together with the guard proposed there.

---

# [Comment #2]() by [c-vigo]()

_Posted on August 14, 2026 at 07:59 AM_

Fix is up in #1507, together with #1503 (same rendering block; landing them separately would let the reset ship ahead of the fold, which is the destructive ordering).

The fold list is now comma-joined from `git diff --cached --name-only -z`, which also resolves the `awk '{print $2}'` mis-parses noted here — with one correction: the rename shape is **unreachable** in this fold. `git checkout FETCH_HEAD -- docs/issues` writes only what the mirror has and never deletes, so porcelain would never emit `R old -> new`. The reachable defect was the C-quoted path containing spaces; `-z` fixes the whole class regardless.

The step also fails loudly now if any path contains a comma (unrepresentable in `FILE_PATHS`), and the re-pull step asserts the post-condition instead of trusting commit-action's exit code.

---

# [Comment #3]() by [c-vigo]()

_Posted on August 14, 2026 at 08:48 AM_

Fixed on `dev` in #1507 (`c7af6a0c`), together with #1503 — same rendering block in `assets/init-workspace.sh`, and landing #1503 first is the destructive ordering.

**What shipped**
- The fold list is comma-joined from `git diff --cached --name-only -z`, matching commit-action's `FILE_PATHS` contract. The `tr` runs inside the pipeline because command substitution silently drops NUL bytes.
- The step now fails loudly on a path containing a comma, which `FILE_PATHS` cannot represent, instead of mis-splitting it.
- `Re-pull release branch after fold` became `Re-pull release branch and verify the fold landed`: it asserts the post-condition — the release branch carries the mirror's archive — rather than trusting commit-action's exit code. A leg that announces N paths and commits zero is now red.

**One correction to the report.** The `awk '{print $2}'` rename mis-parse is unreachable in this fold: `git checkout FETCH_HEAD -- docs/issues` writes only what the mirror has and never deletes, so porcelain cannot emit `R old -> new`. The reachable defect was the C-quoted path containing spaces; `-z` fixes the whole class either way.

**On the structural half.** `tests/bats/release-mirror-fold.bats` now extracts the rendered `run:` blocks and executes them against a throwaway repo whose `origin` is a local bare clone — real fetch/checkout/diff, real `$GITHUB_OUTPUT`. The two steps that genuinely need GitHub (commit-action, the force-push) stay uncovered, which is precisely why both are now gated on a locally verifiable precondition.

**Rollout:** rendered at scaffold time, so `vig-os/org-config` picks this up via a `devkit-upgrade` adoption PR after 1.9.1.

