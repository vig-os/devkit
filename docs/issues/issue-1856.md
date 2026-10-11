---
type: issue
state: open
created: 2026-10-10T20:40:43Z
updated: 2026-10-10T20:40:43Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1856
comments: 0
labels: none
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-10-11T08:37:36.962Z
---

# [Issue 1856]: [devkit-upgrade: commit step runs the NEW hook config inside the OLD project shell, so newly-added hooks cannot spawn](https://github.com/vig-os/devkit/issues/1856)

## Summary

`devkit-upgrade.yml` fails at **"Commit the upgrade in the project shell"** whenever the target
version adds a pre-commit hook whose helper executable did not exist in the consumer's current
version. `install.sh --force` writes the **new** hook config, but the commit then runs inside the
project shell entered from the **old** pinned devkit — so the new hooks cannot spawn.

Any consumer crossing such a version is blocked, and the upgrade produces no PR.

## Observed

Consumer `gerchowl/pidgy` (private, `DEVKIT_MODE=direnv`, Rust + Nix flake), upgrading
**1.7.0 → 1.18.0** via `workflow_dispatch` with `version=1.18.0`:

```text
trim trailing whitespace ............................................ Passed
branch-name (enforce <type>/<issue>-<summary>) ...................... Failed
- hook id: validate-branch-name
- exit code: 2
  error: Failed to spawn: `validate-branch-name`
    Caused by: No such file or directory (os error 2)
…
actionlint (lint GitHub Actions workflows) .......................... Passed
shellcheck-composite-actions (lint composite action run bodies) ..... Failed
- hook id: shellcheck-composite-actions
- exit code: 2
  error: Failed to spawn: `shellcheck-composite-actions`
    Caused by: No such file or directory (os error 2)
…
##[error]Process completed with exit code 1.
```

Every other hook in the run passed or skipped normally — only the two whose binaries are absent
failed, and both failed to **spawn** rather than to validate.

## Why those two specifically

`validate-branch-name` and `shellcheck-composite-actions` are **new since 1.7.0**:

- `grep -c 'validate-branch-name\|shellcheck-composite-actions'` against the consumer's
  1.7.0-generated `.pre-commit-config.yaml` → **0**
- both are present in 1.18.0's `assets/workspace/.pre-commit-config.yaml` and referenced from
  `assets/init-workspace.sh`

So the ordering is the bug, not the hooks.

## Mechanism

1. The job enters the project shell provided by the **currently pinned** devkit (1.7.0 here).
2. `install.sh --force` regenerates the scaffold, including a `.pre-commit-config.yaml` that
   references 1.18.0's helper executables.
3. The commit runs hooks from the new config, still inside the old shell → `No such file or
   directory`.

The step name — "Commit the upgrade **in the project shell**" — suggests the shell entry is
deliberate so consumer hooks run. The gap is that it is the *pre-upgrade* shell.

## Possible fixes (consumer's view — you'll know the right one)

- Re-enter / rebuild the project shell **after** `install.sh --force`, before committing, so the
  shell matches the config it will run.
- Or have the upgrade commit skip hooks for its own scaffold commit, since the content is
  devkit-generated and already gated upstream, and let the resulting PR's CI do the checking.
- Or make hook definitions tolerate a missing helper during an upgrade commit specifically.

## Impact

This is the failure mode a consumer hits precisely when they are *furthest behind* — the larger
the version gap, the likelier a new hook-with-helper was added in between. It also fails silently
in the sense that the weekly scheduled run produces no PR and no notification, so a repo can sit
stale for months. In this case the consumer's `devkit-upgrade` had also been failing weekly since
2026-09-14 for an unrelated reason (missing App credentials), so this is the second distinct
blocker on the same path.

Happy to test a fix against this consumer — it reproduces on demand via `workflow_dispatch`.

Refs: #1833 (cold adoption of devkit by a Rust project) looks adjacent.

