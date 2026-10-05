---
type: issue
state: closed
created: 2026-09-28T12:10:34Z
updated: 2026-10-01T17:46:36Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1749
comments: 1
labels: feature
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-10-02T08:18:26.476Z
---

# [Issue 1749]: [[FEATURE] promote-release: generalise candidate tag cleanup to the configured pre-release format](https://github.com/vig-os/devkit/issues/1749)

### Description

`promote-release.yml`'s best-effort cleanup only prunes candidate tags matching `<prefix>X.Y.Z-rc[0-9]+` with no GitHub Release. Since #1746 a repo can publish candidates in any pre-release format (`DEVKIT_PRERELEASE_FORMAT`, e.g. `alpha.{N}`), and those tags are never cleaned up.

### Problem Statement

A repo on `alpha.{N}` accumulates `vX.Y.Z-alpha.N` tags forever, while an `rc{N}` repo gets them pruned at promote. The cleanup is harmless when it misses (it never deletes anything unexpected), but the behaviour silently differs by format.

### Proposed Solution

- Thread the resolved pre-release format (`resolve-toolchain`'s `prerelease-format` output) into the promote cleanup and derive the tag pattern from it — reuse `release-version`'s format parsing (for example a `--list-pattern` mode) instead of a second hand-rolled regex.
- Decide the policy for tags of a *previous* format of the same `X.Y.Z` (a mid-series label switch): prune them too, or leave them.
- Keep the existing guard: only tags with **no** GitHub Release are ever deleted.

### Alternatives Considered

- Prune every `<prefix>X.Y.Z-*` tag without a Release: simpler, but deletes tags from formats the repo never configured.

### Additional Context

- Parent: #1746 (introduced the format). Cleanup history: #463, #583, #880.

### Impact

Promote-time cleanup only; no change for `rc{N}` repos.

### Changelog Category

Changed

---

# [Comment #1]() by [c-vigo]()

_Posted on October 1, 2026 at 05:46 PM_

Resolved by #1802 (merged to `dev`, ships with the next release): the scaffolded promote cleanup derives its tag match from the resolved `DEVKIT_PRERELEASE_FORMAT` via the new `release-version --list-pattern` (POSIX ERE, passed to jq with `--arg`). Policy: tags of a *previously* configured format for the same X.Y.Z are left alone; only tags with no GitHub Release are ever deleted. Devkit's own promote-release keeps literal `rc{N}` (it sets no format and also prunes per-arch image tags).

