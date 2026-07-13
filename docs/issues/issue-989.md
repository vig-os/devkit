---
type: issue
state: closed
created: 2026-07-13T06:14:15Z
updated: 2026-07-13T09:44:44Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/989
comments: 1
labels: bug, area:ci, area:workspace, effort:medium, semver:minor
assignees: none
milestone: Backlog
projects: none
parent: 988
children: none
synced: 2026-07-13T15:17:55.447Z
---

# [Issue 989]: [[BUG] direnv/bare scaffold ships container-only artifacts](https://github.com/vig-os/devkit/issues/989)

### Description

`--mode direnv` and `--mode bare` deploys still scaffold **container-only
artifacts** into repos that are, by definition, container-less:

- `.github/actions/resolve-image/action.yml` (resolves a devcontainer image tag)
- `docs/container-ci-quirks.md`
- `container:`-based jobs in the scaffolded `ci.yml` and release workflows

In a `direnv`/`bare` repo these are dead weight and misleading (they imply the
image is required).

### Reproduction

```bash
WORKSPACE_DIR=<target> TEMPLATE_DIR=<devkit>/assets/workspace \
SHORT_NAME=x ORG_NAME=vigOS GITHUB_REPOSITORY=vig-os/x VIG_OS_VERSION=1.0.1 \
bash assets/init-workspace.sh --mode direnv --preview --no-prompts
```

Preview lists `resolve-image/action.yml`, `container-ci-quirks.md`, and the
`container:` workflows among ADDED files.

### Acceptance Criteria

- [ ] `direnv`/`bare` scaffolds omit (or neutralize) container-only artifacts.
- [ ] Preview/report reflects the mode-filtered file set.

### Implementation Notes

Largely absorbed by D3 once the toolchain preamble is mode-aware — the
`container:`/`resolve-image` pieces become no-ops in non-container modes. This
issue also covers the pure-doc/asset leaks (`container-ci-quirks.md`).

### Related Issues

Part of the mode-aware scaffold epic.


Part of #988.

---

# [Comment #1]() by [c-vigo]()

_Posted on July 13, 2026 at 09:44 AM_

Merged into the epic branch via #1007 (residual scope; the workflow/action coupling was retired by #991 via #1005/#1006). direnv/bare scaffolds no longer receive docs/container-ci-quirks.md; preview reflects the mode-filtered set. Verified: 246/246 bats green.

