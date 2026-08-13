---
type: issue
state: closed
created: 2026-08-13T06:06:21Z
updated: 2026-08-13T08:32:15Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1479
comments: 1
labels: bug, priority:blocking, area:ci, effort:medium, semver:patch
assignees: c-vigo
milestone: 1.9.0
projects: none
parent: none
children: none
synced: 2026-08-13T14:59:10.656Z
---

# [Issue 1479]: [[BUG] Trunk release: prepare-release freezes onto main and cuts the release branch from the same SHA, so the draft release PR has zero commits](https://github.com/vig-os/devkit/issues/1479)

### Description

Under `DEVKIT_WORKFLOW=trunk`, the rendered `prepare-release.yml` freezes the
CHANGELOG onto `main` and then cuts `release/X.Y.Z` **from that same post-freeze
SHA**, while the draft PR is still opened `--base main --head release/X.Y.Z`.
Head and base therefore resolve to the identical commit and `gh pr create` fails
with *"No commits between main and release/X.Y.Z"*.

The gitflow asset is correct — the freeze targets `dev`, so `release/X.Y.Z`
(cut from `dev`) is genuinely ahead of `main` and the PR has content. Trunk is
realized by an anchored `dev` -> `main` substitution in `render_workflow_model()`
(`assets/init-workspace.sh:1452`), which rewrites the **freeze target** but
leaves the **PR base** at `main` (it was already `main`, so no anchor matches).
The two-branch topology the PR depends on collapses into one branch.

This is a topology defect, not a leftover `dev` string: a rendered trunk
`prepare-release.yml` has zero residual `heads/dev` and is actionlint-clean, and
still cannot open its release PR.

Second, related symptom in the same leg: the freeze is a **direct push to the
trunk**. On a trunk repo whose `main` carries a require-PR ruleset, the
`commit-action` push is rejected unless the Commit App is a bypass actor. Under
gitflow this never surfaced because the freeze targets `dev`, whose ruleset does
list `commit-action-bot`. This is the same collision class as #1227
(sync-issues direct push vs require-PR `main`), which was resolved by *not*
pushing to `main` rather than by granting a bypass.

### Steps to Reproduce

1. Scaffold (or upgrade) a repo with `DEVKIT_WORKFLOW=trunk` — e.g.
   `vig-os/org-config`, devkit 1.8.0, `DEVKIT_MODE=direnv`, `DEVKIT_TAG_PREFIX=v`.
2. Ensure `main` is the only long-lived branch (no `dev`, no `sync-main-to-dev.yml`).
3. Dispatch `prepare-release.yml` from `main` with `version=1.1.0`, `dry-run=false`.
4. Observe the `prepare` job freeze the CHANGELOG onto `refs/heads/main`, then
   create `release/1.1.0` at `main`'s post-freeze SHA.
5. Observe the `open-pr` job attempt `gh pr create --base main --head release/1.1.0`.

If the repo's `main` also requires a PR (step 4 above), the run fails earlier, at
the freeze push, masking the empty-PR failure.

### Expected Behavior

`prepare-release.yml` completes on a trunk repo and leaves a draft
`chore: release X.Y.Z` PR containing the changelog freeze, without requiring the
Commit App to hold a bypass on the trunk.

### Actual Behavior

- `open-pr` fails: `gh pr create` returns *"No commits between main and
  release/X.Y.Z"* (head and base are the same commit).
- On a trunk repo with a require-PR ruleset on `main`, the run instead fails at
  the earlier `Commit prepared CHANGELOG to main via API` step, because
  `commit-action` is not a bypass actor on the protected trunk.

Both are reachable only through a live dispatch; the rollback job behaves
correctly in each case (release branch deleted, changelog restore a no-op when
`dev_sha` is empty).

### Environment

- **Devkit version**: 1.8.0 (`DEVKIT_VERSION=1.8.0`), rendered assets at rev `eb314ff`
- **Consumer**: `vig-os/org-config` (public), `DEVKIT_WORKFLOW=trunk`,
  `DEVKIT_MODE=direnv`, `DEVKIT_TAG_PREFIX=v`, `DEVKIT_FLOATING_TAGS=` (empty)
- **Branches**: `main` + `sync/issue-mirror` only; no `dev`, no `sync-main-to-dev.yml`
- **Rulesets on the consumer**: `Main protection` (scoped `refs/heads/main`;
  requires 1 approving review + code-owner review; bypass actors:
  `#OrganizationAdmin` only) and `Signed commits` (`~ALL`, signatures only)
- **OS / runtime**: GitHub-hosted `ubuntu-24.04`; failure is server-side, not host-dependent

### Additional Context

**Evidence in the shipped gitflow asset** (`assets/workspace/.github/workflows/prepare-release.yml`):

| Line | Content | Trunk render |
|------|---------|--------------|
| `:239` | `TARGET_BRANCH: refs/heads/dev` | -> `refs/heads/main` (rewritten) |
| `:278` | release branch created at the post-freeze head | unchanged (now `main`'s head) |
| `:391`, `:397` | `--base main` | **unchanged — no anchor matches** |

**Why #1206 could not catch this.** The spike's deliverable 1 states *"A local
git simulation of these legs is acceptable for the spike (full live-CI is the
later end-to-end verification)"*, with pass criteria including "PR merged to
main". A pull request cannot be created in a local git simulation, so GitHub's
same-SHA refusal was structurally unreachable by that proof. The gap is in the
verification method rather than the reviewed logic — worth noting because the
`tests/test_workflow_model.py` invariants (zero residual `heads/dev`,
actionlint-clean) all pass on the defective render.

**Blast radius.** Every trunk consumer's release train. `vig-os/org-config` is
currently blocked from cutting `v1.1.0` by exactly this; its `v1.0.0` and
`v1.0.1` were hand-cut (both are *annotated* tags, whereas `release-publish.yml`
creates lightweight refs, and no freeze/finalize commit or `release/*` branch
exists in its history), so the train has never executed there and the defect
stayed latent through two releases.

### Possible Solution

**Preferred — freeze onto the release branch under trunk.** Cut
`release/X.Y.Z` from `main` *first*, then commit the changelog freeze to the
release branch instead of the trunk. The PR then carries exactly one commit, and
`main` receives the frozen changelog when the release PR merges at promote time.
This is the natural trunk analogue of gitflow's shape, and it resolves both
symptoms at once:

- head != base, so `open-pr` succeeds;
- the freeze no longer touches the protected trunk, so **no Commit App bypass on
  `main` is required** — consistent with how #1227 was resolved.

Note this makes the freeze target branch-model-dependent rather than a pure
`dev` -> `main` rename, so `render_workflow_model()` would need a real anchored
edit of the freeze/branch-creation ordering, not just the branch literal — or,
cleaner, the asset could take the freeze target as a rendered variable with
gitflow = `dev` and trunk = `$RELEASE_BRANCH`.

**Alternative — keep freezing onto the trunk.** Then `prepare-release-extension.yml`
must be relied on to add a commit to the release branch before `open-pr` (the
seam already runs in the right place: `open-pr` needs `[validate, prepare,
extension]`, and the extension is invoked with `secrets: inherit`), and the
scaffold documentation must state that a trunk consumer's trunk ruleset has to
grant the Commit App a bypass. This trades a governance weakening for a smaller
diff, and leaves every trunk consumer with a mandatory extension implementation.

Either way, the regression test needs to assert against a real GitHub PR
creation (or an explicit same-SHA guard in the workflow), since the local-git
simulation cannot express this failure.

Refs #1205, #1206, #1227.

---

# [Comment #1]() by [c-vigo]()

_Posted on August 13, 2026 at 08:32 AM_

Fixed on `dev` via #1483 (merged as `4c2a6931`).

Closing manually: a PR merged into `dev` does not auto-close its issue in this repo — the `Closes` keyword only fires for PRs targeting the default branch. Ships in the next release train.

