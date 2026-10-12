---
type: issue
state: closed
created: 2026-10-11T11:18:21Z
updated: 2026-10-12T00:05:12Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1860
comments: 1
labels: bug
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-10-12T08:59:45.891Z
---

# [Issue 1860]: [ci.yml on a persistent self-hosted runner: resolve-toolchain's sparse checkout leaves the shared workspace unmaterialized for later jobs](https://github.com/vig-os/devkit/issues/1860)

## What happened
gerchowl/claude-config (devkit 1.18.0, direnv mode) routed CI onto a persistent self-hosted runner via `DEVKIT_CI_RUNNER` + `DEVKIT_CI_RESOLVE_RUNNER` (#1173 / #1796). Run gerchowl/claude-config 38134220255: `Resolve toolchain` succeeds, then `Lint & Format` and `Tests` both fail at their first step after checkout:

```
##[error]Can't find 'action.yml', 'action.yaml' or 'Dockerfile' under '…/_work/claude-config/claude-config/.github/actions/setup-devkit-toolchain'. Did you forget to run actions/checkout before running your local action?
```

## Cause
All three jobs land on the same runner and share `_work/<repo>/<repo>`. `resolve-toolchain`'s `actions/checkout` uses `sparse-checkout:` (6 patterns, `sparse-checkout-cone-mode: false`; `Updating files: 100% (4/4)`). The next job's checkout reuses that clone: `git sparse-checkout disable` → `git checkout --force -B <branch> …` finishes in ~0.19 s with no `Updating files` line, so the full tree is never materialized. The skip-worktree state also survives the following job's `clean -ffdx` + `reset --hard HEAD`. Hosted and ephemeral runners never see it, because each job gets a fresh machine.

## Expected
A consumer on a persistent self-hosted runner gets a fully materialized checkout in every toolchain job.

## Possible fixes
- Give resolve-toolchain's checkout its own `path:` (e.g. `.devkit-resolve`), so the sparse clone never shares the workspace root with later jobs. This is the smallest change.
- Or drop the sparse checkout when `DEVKIT_CI_RESOLVE_RUNNER` is set (a self-hosted resolve runner).
- Or add `sparse-checkout: ''` / an explicit full checkout in the downstream jobs.

Workaround on the fleet side: the runner's job-start hook deletes clones that carry sparse or skip-worktree state.
---

# [Comment #1]() by [gerchowl]()

_Posted on October 12, 2026 at 12:05 AM_

Fixed in #1866 (merged into dev at 88dfd8bb): resolve-toolchain's sparse checkout now uses its own `path: .devkit-resolve` in every workflow that has one, so it never occupies a persistent runner's shared workspace root. Root clones left with skip-worktree state by older runs aren't repaired by this change; the gerchowl fleet runners clear them in a job-start hook. Consumers pick it up with the next devkit release.

