---
type: issue
state: closed
created: 2026-08-12T10:32:29Z
updated: 2026-08-12T10:49:13Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1459
comments: 1
labels: bug, priority:high, area:ci, effort:small, semver:patch
assignees: none
milestone: 1.8.0
projects: none
parent: none
children: none
synced: 2026-08-12T13:33:36.167Z
---

# [Issue 1459]: [[BUG] release/1.8.0 lost the #1447 and #1448 content to failed-run rollbacks](https://github.com/vig-os/devkit/issues/1459)

### Description

Two failed `release.yml` dispatches silently stripped merged work off `release/1.8.0`. The content of **#1447** and **#1448** is gone from the branch even though both PRs (#1449, #1451) merged green.

| Rollback commit | Time | Triggering run | Content destroyed |
|---|---|---|---|
| `71cd72fb` | 09:49Z | `31583273344` (09:31Z, failed: `Candidate tag '1.8.0-rc2' already exists on origin`) | **#1447** — `nix/hooks.nix` consumer-entry fix, 102 lines of `tests/test_flake_hooks.py`, changelog entry |
| `c1cc5d82` | 09:59Z | `31584765199` (09:50Z, failed: validate's PR gate — #1441 is a draft with `REVIEW_REQUIRED`) | **#1448** — 77-line `assets/workspace/justfile` `doctor` recipe, 241-line `tests/bats/consumer-doctor.bats`, changelog entry |

Verified missing on the current tip (`7e64013b`): the `check-expirations` store-path entry, `TestNoConsumerHookResolvesVigUtilsThroughTheVenv`, the consumer `doctor` recipe, `tests/bats/consumer-doctor.bats`, and both changelog entries. #1453's fix survived only because it merged after the last rollback.

### Impact

Two merged, CI-green, issue-closed fixes are absent from the release branch. Both issues are closed, so without this restoration 1.8.0 would ship claiming fixes it does not contain, and the changelog would omit them.

### Root cause

`release.yml`'s **Rollback on Failure** job (`.github/workflows/release.yml:1551`, "Rollback release branch") builds a commit whose **tree is `PRE_SHA`** — the branch tip captured when `validate` started — parented onto the current tip. That is a tree-level reset expressed as a commit.

Two properties make it destructive:

1. It runs when **`validate`** fails. In both runs `Finalize Release` was **skipped** — there was nothing to roll back — yet the tree was reset anyway.
2. `PRE_SHA` is a run-start snapshot, so **anything merged to the release branch while a release run is in flight is destroyed if that run fails**, regardless of whether it had anything to do with the release.

The trigger was merging into the release branch while a run was live. The defect is that a rollback for a step that never executed discards unrelated merged commits. **That defect is tracked separately — this issue covers only restoring the lost content.**

### Proposed Solution

Revert the two rollback commits on `release/1.8.0`:

```
git revert --no-commit c1cc5d82 71cd72fb
```

Verified to apply cleanly with no conflicts, restoring 490 insertions across 6 files, and leaving exactly one #1434 title bullet plus the legitimate cross-reference from #1447's entry.

### Additional Context

Must land before 1.8.0 is finalized. Note `1.8.0-rc2` is tagged at `b60b306a`, which predates #1447, #1448, #1453 and #1454 — after restoration the branch matches no existing RC.

Interim operating rule until the rollback defect is fixed: **never merge into a release branch while a `release.yml` run is in flight.**

---

# [Comment #1]() by [c-vigo]()

_Posted on August 12, 2026 at 10:49 AM_

Restored by #1460, merged to `release/1.8.0` as 9cce85ed.

Verified on the tip:

| item | present |
|---|---|
| `check-expirations` store-path entry (`nix/hooks.nix`) | yes |
| `TestNoConsumerHookResolvesVigUtilsThroughTheVenv` | yes |
| consumer `doctor` recipe (`assets/workspace/justfile`) | yes |
| `tests/bats/consumer-doctor.bats` | yes |
| devkit's own `doctor` hooksPath diagnostic (#1430) | yes |
| changelog entries #1447 / #1448 | yes / yes |
| #1434 title bullet (#1453) | 1 title bullet + 1 legitimate cross-reference from #1447's entry |

A clean `git revert --no-commit c1cc5d82 71cd72fb` — no hand edits, no conflicts, 490 insertions across 6 files.

Local evidence before pushing: `bats tests/bats/` **496 ok / 0 not ok**, exactly the pre-loss baseline (so #1448's 14 tests are back and green); `test_flake_hooks` 63 passed (#1447's tests green); full pytest 780 passed / 20 skipped / 1 failed (the known stale-image `test_manifest_files`, which reproduces on a clean `dev`); `prek run --all-files` exit 0. PR CI 14/14 green.

Merged only after confirming zero `release.yml` runs in flight, so the recovery could not fall to the same defect.

The underlying workflow defect is filed separately. Interim rule until it is fixed: **never merge into a release branch while a `release.yml` run is in flight.**

Note `1.8.0-rc2` (tagged at `b60b306a`) now predates #1447, #1448, #1453 and — once it lands — #1454, so the branch matches no existing RC.

