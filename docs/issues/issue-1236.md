---
type: issue
state: closed
created: 2026-07-21T09:15:47Z
updated: 2026-07-21T11:58:56Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1236
comments: 1
labels: bug, area:ci, effort:small
assignees: none
milestone: 1.4.1
projects: none
parent: none
children: none
synced: 2026-07-22T05:26:39.012Z
---

# [Issue 1236]: [nix-dev discovery image can go stale: dev push trigger only watches flake files](https://github.com/vig-os/devkit/issues/1236)

## Description

`nix-image.yml` is the lane that keeps the mutable `ghcr.io/vig-os/devcontainer:nix-dev` tag (plus `-amd64`/`-arm64` and the multi-arch index) tracking `dev`. Its push trigger is path-filtered:

```yaml
on:
  push:
    branches:
      - 'feature/625-nix-claude-migration'
      - 'dev'
    paths:
      - 'flake.nix'
      - 'flake.lock'
      - '.github/workflows/nix-image.yml'
```

But the image content is not a function of `flake.nix`/`flake.lock` alone — the flake bakes repo content that lives outside those paths (workspace scaffold assets, `scripts/`, home/config fragments). A `dev` push that changes only those files changes the image **without rebuilding or repushing `nix-dev`**, so the discovery tag silently drifts behind `dev`.

## Steps to Reproduce

1. Land a change on `dev` that touches baked content but not `flake.nix`/`flake.lock` (e.g. a scaffold asset under the assets tree or a script in `scripts/`).
2. Observe no `Nix Image (discovery)` run is triggered.
3. `ghcr.io/vig-os/devcontainer:nix-dev` still serves the previous build; anyone pulling it to try the dev-branch change doesn't get it.

## Expected Behavior

`nix-dev` is a trustworthy rolling image of `dev`: every push that can affect the image rebuilds, tests (portable testinfra + runtime smoke, both arches), and repushes the tag.

## Actual Behavior

Only flake-file pushes rebuild it; other image-affecting pushes leave the tag stale with no signal.

## Possible Solution

Widen (or drop) the `paths:` filter on the `dev` push trigger. Given the flake copies repo content at build time, a precise allowlist is fragile — the simplest robust option is to drop the filter for `dev` and let Cachix/eval caching keep no-op rebuilds cheap. Alternatively enumerate the baked source paths next to the flake outputs they feed so the filter has an SSoT.

Scope note (from the nightly-build investigation, 2026-07-21): the decision is to **keep `nix-dev` as the only rolling/dev tag** — no scheduled nightly build and no `nightly` alias tag. The flake is fully pinned, so a cron rebuild of an unchanged `dev` adds nothing; correctness of the event-driven trigger is the whole fix.

## Changelog Category

Fixed
---

# [Comment #1]() by [c-vigo]()

_Posted on July 21, 2026 at 11:58 AM_

Fixed on dev via PR #1242 (merge commit 79b018a1): dropped the nix-image.yml dev push paths filter — the image bakes assets/, docs/MIGRATION.md, packages/vig-utils, nix/home and scripts/, so an allowlist was inherently drifty. Every dev push now rebuilds nix-dev; Cachix keeps no-op rebuilds cheap. Ships with 1.4.1.

