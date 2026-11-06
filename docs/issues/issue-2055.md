---
type: issue
state: open
created: 2026-11-06T02:51:31Z
updated: 2026-11-06T02:51:31Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/2055
comments: 0
labels: bug, area:workflow
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-11-06T09:11:25.063Z
---

# [Issue 2055]: [Record checkout SHA runs git before the container workspace is a safe.directory (dubious ownership)](https://github.com/vig-os/devkit/issues/2055)

## Problem

#2031 (`05217f5c`, "pin API file commits to checkout revisions") added a `Record checkout SHA` step: `CHECKOUT_SHA=$(git rev-parse HEAD)`, placed right after `actions/checkout` and **before** `Set up devkit toolchain`. In a `container:` job the workspace (`/__w/...`) is owned by a different uid than the container user, and nothing has marked it as a git `safe.directory` yet. So git refuses:

```
fatal: detected dubious ownership in repository at '/__w/devkit-smoke-test/devkit-smoke-test'
##[error]Process completed with exit code 128.
```

This failed the 1.19.0-rc4 smoke test: Prepare Release, run 42151390302, in both `Prepare Release Branch` and the rollback job. 1.18.2 passed.

## Scope

The step appears in 7 consumer workflows under `assets/workspace/.github/workflows/`: prepare-release (×2), prepare-hotfix, release-core, abandon-release, sync-issues and sync-main-to-dev. It also appears in 11 places in devkit's own `.github/workflows/`. In container-mode consumers, the daily `sync-issues` and `sync-main-to-dev` would fail too.

## Fix

Take the SHA from `actions/checkout`'s own `commit` output (`steps.<id>.outputs.commit`), which needs no git call. Add a static guard so no step runs git in a container job before the safe-directory setup.

Blocks 1.19.0.
