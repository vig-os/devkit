---
type: issue
state: closed
created: 2026-07-17T18:44:07Z
updated: 2026-07-17T19:39:07Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1198
comments: 1
labels: bug, priority:low, area:ci, effort:small, semver:patch
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-07-18T04:54:22.229Z
---

# [Issue 1198]: [Detect host Nix step logs an empty nix --version](https://github.com/vig-os/devkit/issues/1198)

## Description

Cosmetic follow-up to #1192. The `Detect host Nix` step added to `setup-devkit-toolchain` logs:

```
Host Nix present: /nix/var/nix/profiles/default/bin/nix ()
```

i.e. `$(nix --version)` expanded to empty on exo-fleet's meatgrinder runner (multi-user host Nix). Confirmed on exo-pet/exo-fleet#230's green rc4 run — purely a log-line issue, the step correctly detected host Nix and took the right branch.

## Root cause (to confirm)

`nix --version` may write to stderr, or the multi-user nix wrapper on that host emits the version elsewhere, so the command-substitution captured nothing.

## Fix

Capture `2>&1` in the version substitution, or drop the version from the log line if it isn't reliably available. Trivial.

## Impact

None functional — log cosmetics only.

Refs: #1192, exo-pet/exo-fleet#230.
---

# [Comment #1]() by [c-vigo]()

_Posted on July 17, 2026 at 07:39 PM_

Fixed on `release/1.4.0` via merge 0efbe3eb (PR #1201) (TDD: failing test + fix). Auto-close didn't fire because the PR targeted the release branch, not the default branch. Ships in 1.4.0.

