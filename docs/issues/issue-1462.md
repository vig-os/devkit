---
type: issue
state: closed
created: 2026-08-12T10:55:11Z
updated: 2026-08-12T12:00:14Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1462
comments: 1
labels: bug, priority:high, area:ci, effort:medium, semver:patch
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-08-12T13:33:35.659Z
---

# [Issue 1462]: [[BUG] release.yml rollback resets the branch tree to a stale PRE_SHA and destroys unrelated merged commits](https://github.com/vig-os/devkit/issues/1462)

### Description

`release.yml`'s **Rollback on Failure** job destroys unrelated merged commits on a release branch. It caused #1459 today, wiping the merged content of #1447 and #1448 off `release/1.8.0`.

The "Rollback release branch" step (`.github/workflows/release.yml:1551`) builds a commit whose **tree is `PRE_SHA`** — the branch tip captured when `validate` started — parented onto the current tip:

```sh
TREE_SHA=$(gh api "repos/$REPO/git/commits/$PRE_SHA" --jq '.tree.sha')
CURRENT_SHA=$(gh api "repos/$REPO/git/refs/$BRANCH_REF" --jq '.object.sha')
if [ "$CURRENT_SHA" = "$PRE_SHA" ]; then exit 0; fi   # only no-ops on an EXACT match
REVERT_SHA=$(gh api -X POST … -f tree="$TREE_SHA" -f "parents[]=$CURRENT_SHA" …)
```

That is a tree-level reset expressed as a commit. Two properties make it destructive:

1. **It runs when `validate` fails.** The job's `if:` fires on failure/cancellation of `validate`, `finalize`, `build-and-test`, `vulnix-gate` **or** `publish`. In both incidents today `Finalize Release` was **skipped** — nothing had been written, so there was nothing to roll back — yet the tree was reset anyway.
2. **`PRE_SHA` is a run-start snapshot.** The `CURRENT_SHA = PRE_SHA` guard only catches the case where *nothing at all* moved. If anything merged after the run started, the guard passes and the reset silently discards it.

Net effect: **any commit merged to a release branch while a `release.yml` run is in flight is destroyed if that run later fails**, whether or not it has anything to do with the release.

### Steps to Reproduce

1. Dispatch `release.yml` against a release branch in a way that fails `validate` (e.g. a candidate whose tag already exists, or a draft release PR).
2. While it runs, merge any PR into that release branch.
3. The rollback job creates `revert: undo finalize release <version> (workflow rollback)` and the merged work is gone from the branch.

Observed today:

| Rollback | Run | Validate failure | Destroyed |
|---|---|---|---|
| `71cd72fb` | `31583273344` | `Candidate tag '1.8.0-rc2' already exists on origin` | #1447 (fix + 102 lines of tests + changelog) |
| `c1cc5d82` | `31584765199` | release PR was a draft with `REVIEW_REQUIRED` | #1448 (77-line recipe + 241-line bats file + changelog) |

### Expected Behavior

A rollback should undo **only what the run wrote**, and should decline rather than clobber when it cannot do so safely.

### Proposed Solution

Not prescriptive — the maintainer should weigh these:

1. **Do not roll back when `finalize` never ran.** If `needs.finalize.result == 'skipped'`, there is no finalize commit; the job should no-op. This alone prevents both incidents.
2. **Refuse when the branch has moved beyond `PRE_SHA`.** Verify `CURRENT_SHA` is either `PRE_SHA` or a descendant whose only commits are the finalize commits this run created. Otherwise fail loudly and leave the branch alone — a human can revert one commit far more cheaply than reconstructing lost merges.
3. **Revert the finalize commit specifically** (by SHA, recorded as a `finalize` job output) instead of resetting the tree wholesale.
4. Consider a concurrency group so a release run and release-branch merges cannot interleave.

Note the file already states a forward-fix policy for post-publish failures ("automation does not delete tags or reset branches") — that principle should extend to pre-publish branch content.

### Impact

Silent data loss on the branch a release is cut from, at exactly the moment people are landing last-minute fixes. Both PRs stayed green and their issues stayed closed, so nothing surfaced it — #1459 was caught only because an unrelated merge hit a conflict against a file that should have existed.

**Interim operating rule until this is fixed: never merge into a release branch while a `release.yml` run is in flight.**

---

# [Comment #1]() by [c-vigo]()

_Posted on August 12, 2026 at 12:00 PM_

Fixed by PR #1467, squash-merged into release/1.8.0 @633591f2 (release-branch merges don't auto-close). The rollback now no-ops when finalize never ran and for candidates, and otherwise refuses to touch the branch unless the tip is provably this run's own finalize commit (optionally with the sync-issues commit on top, gated on its fixed message/author — squash merges are single-parent, so parentage alone can't exclude foreign PRs). All three copies fixed (devkit release.yml, scaffold release-core.yml + orchestrator, whose old rollback was an unguarded reset+force-push); pinned by tests/test_release_rollback_guard.py executing the real scripts against a stubbed Git Data API. Concurrency group (proposal 4) deliberately not done. The interim don't-merge-mid-run rule is now courtesy rather than a data-integrity requirement. Ships in 1.8.0.

