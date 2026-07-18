---
type: issue
state: closed
created: 2026-07-17T18:43:54Z
updated: 2026-07-17T19:39:04Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1196
comments: 1
labels: bug, priority:low, area:workspace, effort:small, semver:patch
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-07-18T04:54:22.793Z
---

# [Issue 1196]: [init-workspace.sh --preview reports rsync-excluded files as ADDED](https://github.com/vig-os/devkit/issues/1196)

## Description

Found during the vault deploy (exo-pet/vault#31): `init-workspace.sh --preview` listed `.typos.toml` as an ADDED file, but the **actual scaffold run correctly skipped it** (the repo's `_typos.toml` is the SSoT and the template `.typos.toml` is rsync-`--exclude`d). So the preview over-reports changes the real run does not make.

## Root cause (to confirm)

The `--preview` file report is generated before/without applying the same rsync `--exclude` set that the real copy uses — the exclusions are honored at copy time but not reflected in the preview listing.

## Fix

Apply the identical exclude set when computing the preview listing so `--preview` is a faithful dry-run of the actual copy. A preview that lists files the run then skips undermines trust in `--preview` as a safety check before `--force`.

## Impact

Low — cosmetic/UX, but `--preview` is exactly the step a cautious operator relies on before overwriting, so a false ADDED is misleading.

Refs: exo-pet/vault#31.
---

# [Comment #1]() by [c-vigo]()

_Posted on July 17, 2026 at 07:39 PM_

Fixed on `release/1.4.0` via merge 3455d77a (PR #1200) (TDD: failing test + fix). Auto-close didn't fire because the PR targeted the release branch, not the default branch. Ships in 1.4.0.

