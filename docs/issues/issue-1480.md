---
type: issue
state: closed
created: 2026-08-13T07:30:04Z
updated: 2026-08-14T13:09:34Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1480
comments: 1
labels: bug, priority:high, area:workspace, effort:medium, semver:patch
assignees: none
milestone: 1.10.0
projects: none
parent: none
children: none
synced: 2026-08-14T16:05:18.195Z
---

# [Issue 1480]: [install.sh --force is not atomic: a mid-run failure leaves .vig-os wiped](https://github.com/vig-os/devkit/issues/1480)

## What happened

Upgrading `gerchowl/filesender` from 1.6.0 to 1.8.0 with the documented command:

```
curl -sSfL .../install.sh | bash -s -- --force --version 1.8.0 --docker .
```

The run **failed**:

```
sent 291,262 bytes  received 528 bytes  583,580.00 bytes/sec
chmod: fts_read failed: No such file or directory
error: Failed to initialize workspace
```

That is `assets/init-workspace.sh:2232`, `chmod -R u+w "$WORKSPACE_DIR"`.

## Why it matters — the failure is destructive, not a no-op

By the time the `chmod` ran, the script had already rsynced the new scaffold **and** rewritten `.vig-os`. The abort left the manifest with its resolved identity **blanked**:

```diff
-DEVKIT_MODE=direnv
+DEVKIT_MODE=
-DEVKIT_PROJECT=filesender
-DEVKIT_ORG=vigOS
-DEVKIT_REPO=gerchowl/filesender
+DEVKIT_PROJECT=
+DEVKIT_ORG=
+DEVKIT_REPO=
-DEVKIT_FEATURES_DISABLED=skills,worktree
+DEVKIT_FEATURES_DISABLED=
```

Also gone: the Rust `.gitignore` section (`/target/`, `**/*.rs.bk`) and the repo-specific ignore block (`/target`, `.direnv`, `result`, `result-*`) — so a 4 GB `target/` and a nix `result` symlink became untracked-and-visible in `git status`.

**`.vig-os` is the input to the very operation that just wiped it.** A re-run after this failure resolves against an empty manifest: no mode, no identity, and — the one that would go unnoticed longest — **no `DEVKIT_FEATURES_DISABLED`, silently re-enabling `skills` and `worktree` for a repo that deliberately opted out.**

I recovered with `git checkout -- .` only because the tree happened to be clean and pushed. A consumer with uncommitted work at upgrade time has no such exit.

## Not claiming a root cause

A retry from the clean tree **succeeded**, with identity and feature opt-outs preserved. I could not reproduce the `chmod` failure afterwards — `chmod -R u+w .` over the same tree exits 0, and a synthetic nix `result` symlink does not trigger it. Whatever the trigger was, it was transient.

The non-atomicity is the reportable part and it holds regardless of the trigger.

Worth noting separately: `chmod -R u+w "$WORKSPACE_DIR"` walks the consumer's **entire** workspace. On this repo that is a 4 GB Cargo `target/` plus `.git`, none of which devkit needs to make writable. That is both slow and a large surface for exactly this class of transient walk failure.

## Suggestions

1. **Make `.vig-os` atomic.** Write to a temp file and `mv` it into place as the last step, or snapshot-and-restore it on any non-zero exit. It is the operation's own input; it should be the last thing to change and the first thing restored.
2. **`trap`-based rollback** on failure, or at minimum a loud message naming what was left half-applied and telling the user to `git checkout -- .`. Right now `error: Failed to initialize workspace` gives no hint that the manifest was modified.
3. **Scope the chmod** to the paths devkit actually writes, rather than `-R` over the whole workspace. `.git/`, `target/`, `node_modules/` and `result` symlinks have no business in that walk.
4. **Preflight**: refuse `--force` on a dirty tree unless `--skip-preflight` is passed. The recovery path assumes a clean tree, so the tool should require one.

## Related, and the reason `result` was loose in the first place

devkit's nix detection requires `*.nix` files **beyond** `flake.nix`, so a single-`flake.nix` repo is never nix-detected and never gets the `nix.gitignore` fragment. That is already filed as ask 3 on #1400 and was independently confirmed by the second Rust-pack consumer. Every Rust language-pack repo is a single-`flake.nix` repo by construction, so this will keep producing untracked `result` symlinks in exactly the repos the pack targets.

Refs: #1400

---

# [Comment #1]() by [c-vigo]()

_Posted on August 14, 2026 at 01:09 PM_

Delivered by #1513 (merged to dev): init-workspace.sh now snapshots .vig-os and the root .gitignore before the template copy and restores them byte-for-byte on any failing exit inside the refill window, with a loud message naming what was restored. The u+w permission sweep is scoped to template-derived paths — consumer .git/target/node_modules trees are no longer walked. The dirty-tree preflight (suggestion 4) already existed via install.sh's run_preflight_guard (#1283); the nix-detection gap stays tracked on #1400.

