---
type: issue
state: closed
created: 2026-06-23T15:27:04Z
updated: 2026-06-23T15:37:15Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devcontainer/issues/657
comments: 1
labels: bug
assignees: c-vigo
milestone: none
projects: none
parent: none
children: none
synced: 2026-06-24T06:13:08.890Z
---

# [Issue 657]: [derive-branch-summary errors on --help, blocking `just wt-start`](https://github.com/vig-os/devcontainer/issues/657)

## Summary

`just wt-start <issue>` aborts at its prerequisite guard and never creates a worktree.

The guard probes helper-CLI availability with `--help`:

```sh
if ! uv run derive-branch-summary --help >/dev/null 2>&1; then
    echo "[ERROR] derive-branch-summary command not available."
    ...
    exit 1
fi
```

But `derive-branch-summary.sh` does `TITLE="${1:?Usage...}"`, so `--help` is taken as the
*issue title*, runs the agent/`BRANCH_SUMMARY_CMD` path, fails, and exits 1. The guard then
concludes the command is "not available" and aborts the launcher.

`resolve-branch` tolerates `--help` only by accident — its script ignores args and just reads
stdin (`head -1 | cut -f1`), so it exits 0. The underlying summary functionality works; only
the `--help` probe is broken.

## Repro

```
$ uv run derive-branch-summary --help; echo $?
[ERROR] Failed to derive branch summary from title: --help
1
```

## Fix

Make `derive-branch-summary.sh` handle `-h|--help` by printing its usage block and exiting 0,
matching the implicit contract the `wt-start` guard relies on. Cover with a test in
`packages/vig-utils/tests/test_shell_entrypoints.py`.

## Notes

Pre-existing, generally applicable (affects `dev`/`main` too). Fixing on the
`feature/625-nix-claude-migration` epic branch to unblock the epic's parallel-worktree workflow
now; it propagates to `dev` when the epic merges.
---

# [Comment #1]() by [c-vigo]()

_Posted on June 23, 2026 at 03:37 PM_

Fixed in #658, merged into the epic branch `feature/625-nix-claude-migration`. Propagates to `dev`/`main` when the epic merges.

