---
type: issue
state: closed
created: 2026-07-14T08:59:58Z
updated: 2026-07-14T10:12:29Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1046
comments: 1
labels: bug, priority:medium, area:workspace, effort:small, area:docs, semver:patch
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-07-14T20:06:28.756Z
---

# [Issue 1046]: [[BUG] Scaffolded promote-release.yml references docs/DOWNSTREAM_RELEASE.md, which the scaffold does not ship](https://github.com/vig-os/devkit/issues/1046)

## Description

The scaffolded `promote-release.yml` tells consumers to "See `docs/DOWNSTREAM_RELEASE.md`" (`assets/workspace/.github/workflows/promote-release.yml:9`), but the scaffold does not ship that file: `assets/workspace/docs/` contains only `COMMIT_MESSAGE_STANDARD.md` and `container-ci-quirks.md`. Every consumer therefore carries a dangling doc reference for its primary release-process documentation.

## Steps to Reproduce

1. Scaffold a consumer repo with devkit 1.1.0 (e.g. `vig-os/commit-action`, `DEVKIT_MODE=direnv`).
2. `grep -rn "DOWNSTREAM_RELEASE" .github/workflows/` → hit in `promote-release.yml`.
3. `ls docs/` → `COMMIT_MESSAGE_STANDARD.md` only. `docs/DOWNSTREAM_RELEASE.md` does not exist in the consumer repo.

## Expected Behavior

The consumer-facing release documentation referenced by the scaffolded workflows is resolvable from inside the consumer repo — either the file ships with the scaffold or the reference points at devkit's canonical copy.

## Actual Behavior

`docs/DOWNSTREAM_RELEASE.md` exists only in the devkit repo itself. In consumers, the header comment of the promote workflow — the entry point an operator reads before running a release — points at a file that is not there.

## Environment

- **Consumer**: `vig-os/commit-action` (TypeScript action)
- **Devkit version**: 1.1.0 (`DEVKIT_VERSION=1.1.0`)
- **Delivery mode**: `direnv`

## Possible Solution

Either:

1. **Ship it**: add `docs/DOWNSTREAM_RELEASE.md` to `assets/workspace/docs/` — it is the consumer-project release contract, so the consumer repo is arguably its natural home (managed file, refreshed on scaffold upgrades); or
2. **Point upstream**: rewrite the reference to the canonical URL, e.g. `https://github.com/vig-os/devkit/blob/main/docs/DOWNSTREAM_RELEASE.md`, keeping a single source of truth and avoiding a copy that can go stale.

Option 2 is the smaller change and honors SSoT; option 1 keeps consumers self-contained (useful for private/offline work). Whichever is chosen, a scaffold-lint idea from #1034 generalizes here: *scaffolded files must not reference repo paths the scaffold does not ship*.

---

# [Comment #1]() by [c-vigo]()

_Posted on July 14, 2026 at 10:12 AM_

Fixed in #1051 (merged to dev), Option 1 per maintainer decision: docs/DOWNSTREAM_RELEASE.md ships as a managed, manifest-synced scaffold file (root = SSoT). Known follow-up flagged in the PR: the doc's cross-links to devkit-internal docs (and scaffolded ci.yml's ADR reference) are the same dangling-reference class — separate issue candidates.

