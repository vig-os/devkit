---
type: issue
state: closed
created: 2026-07-13T07:12:52Z
updated: 2026-07-13T10:58:35Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/996
comments: 2
labels: refactor, area:ci, effort:small, semver:patch
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-07-13T15:17:52.945Z
---

# [Issue 996]: [Migrate devkit-own sync-main-to-dev.yml off the container/resolve-image pattern](https://github.com/vig-os/devkit/issues/996)

### Description

`.github/workflows/sync-main-to-dev.yml` is the last devkit-own workflow still
running `container: ghcr.io/vig-os/devcontainer:<tag>` via a `resolve-image`
job — a near-verbatim stale copy of the scaffold template. Every other
devkit-own workflow (ci, release, prepare-release, promote-release) runs
host+Nix via `.github/actions/setup-env`.

### Acceptance Criteria

- [ ] `sync-main-to-dev.yml` provisions via `setup-env` (or adopts the new
      mode-aware template from #991); no `container:` / resolve-image
- [ ] Devkit-own `.github/actions/resolve-image/` removed if no consumer remains

### Related Issues

Related to #988/#991 (not a blocking sub-issue).
---

# [Comment #1]() by [c-vigo]()

_Posted on July 13, 2026 at 10:16 AM_

Scope note from planning: THREE devkit-own workflows still run resolve-image + `container:` — `sync-main-to-dev.yml`, `sync-issues.yml`, and `renovate-changelog-build.yml` (the last is synced to the scaffold via `scripts/manifest.toml` ReplaceBlock transforms that rewrite it into the mode-aware template variant, so its conversion must either rework those transforms or de-couple the template copy — to be decided in the PR). After all three convert to `setup-env`, `.github/actions/resolve-image/` is deleted per the AC.

---

# [Comment #2]() by [c-vigo]()

_Posted on July 13, 2026 at 10:58 AM_

Resolved by #1012 (merged to `dev`). Closing.

