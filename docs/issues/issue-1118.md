---
type: issue
state: closed
created: 2026-07-15T12:31:24Z
updated: 2026-07-15T14:38:19Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1118
comments: 1
labels: bug, priority:low, area:workspace, effort:small, semver:patch
assignees: c-vigo
milestone: none
projects: none
parent: none
children: none
synced: 2026-07-15T20:04:01.244Z
---

# [Issue 1118]: [direnv-mode install.sh aborts init when container-side 'just sync' fails](https://github.com/vig-os/devkit/issues/1118)

## Summary

During a direnv-mode `install.sh --force` upgrade, **after** the scaffold files
are written successfully, `init-workspace` runs `just sync` (npm ci) inside the
container. In our run this crashed with an npm-internal error and aborted the
whole init:

```
Syncing dependencies...
npm error Exit handler never called!
npm error This is an error with npm itself. Please report this error at:
npm error   <https://github.com/npm/cli/issues>
error: recipe `sync` failed on line 65 with exit code 1
error: Failed to initialize workspace
```

All managed files had already been written correctly, so
`Failed to initialize workspace` is misleading — only a post-scaffold dependency
sync failed.

## Two questions

1. Should `just sync` run in the container at all for a **direnv** consumer? In
   direnv mode, dependencies are installed in the direnv / `nix develop` shell on
   the host, not in the container, so the container-side sync looks redundant.
2. Regardless: a post-scaffold step failing shouldn't abort init once the files
   are already written. Warn and continue (the consumer runs `just sync` /
   `npm ci` in their own shell anyway), so the exit status reflects the scaffold
   result, not an optional post-step.

## Environment

devkit 1.2.1, consumer `vig-os/commit-action` (direnv mode), podman, image
`ghcr.io/vig-os/devcontainer:1.2.1`.

## Impact

The scaffold succeeds but `install.sh` reports failure, which is alarming and
could trigger an unnecessary rollback/retry. The underlying
`npm error Exit handler never called!` may be a separate npm/node issue in the
image worth a look. Surfaced during the upgrade in PR `vig-os/commit-action#80`.

---

# [Comment #1]() by [c-vigo]()

_Posted on July 15, 2026 at 02:38 PM_

Fixed by #1125 (merged into `dev`). The container-side `just sync` is now skipped entirely in direnv/bare modes (host nix/direnv shell owns dependency install), and where it runs (devcontainer/both) a failure warns and continues — init's exit status now reflects the scaffold result. The image-side `npm error Exit handler never called!` root cause remains open for a separate look if it recurs. Ships with the next patch release.

