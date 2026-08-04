---
type: issue
state: closed
created: 2026-08-04T11:12:14Z
updated: 2026-08-04T11:33:16Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1344
comments: 1
labels: bug, priority:high, area:workspace, effort:small, semver:patch
assignees: none
milestone: 1.6.0
projects: none
parent: none
children: none
synced: 2026-08-04T12:17:53.114Z
---

# [Issue 1344]: [fix(workspace): scaffold rsync quick-check skips same-size template updates on epoch-mtime consumer trees](https://github.com/vig-os/devkit/issues/1344)

## Found by

The scaffold-drift CI gate (#1295), on its **first live exercise**: 4 of 5 devkit 1.6.0-rc1 consumer lanes (org-config#85, sync-issues-action#160, commit-action#124, exo-fleet#268) went red on `Scaffold Drift` with a one-hunk diff — `.github/workflows/scorecard.yml` still carrying `codeql-action/upload-sarif@e4fba868` where rc1 scaffolds `@d1ba80a1` (#1330). The 5th lane (vault#48), run from a **freshly created git worktree**, committed the correct new digest and passed.

## Root cause

`init-workspace.sh` copies the template with `rsync -avL` (no `--checksum`). rsync's quick-check skips any file whose **size and mtime both match** the source:

- The image template files are symlinks into the Nix store; dereferenced (`-L`) they carry the store's canonical **mtime epoch+1**.
- `-a` implies `-t`, so every *previous* nix-image scaffold stamped the consumer's managed files with that same **epoch+1** mtime (verified: `scorecard.yml` in the failing clones is `1970-01-01 00:00:01Z`).
- The #1330 digest bump swaps 40 hex chars for 40 hex chars — **file size unchanged** (2499 bytes).

Same size + same mtime → rsync silently declares the file up-to-date and the template change is never delivered. Reproduced with `rsync -avL --dry-run --itemize-changes` inside the rc1 container against an affected clone: `.f...p..... scorecard.yml` (perms-only, no data transfer).

## Impact

Any **host-side upgrade of a previously nix-scaffolded consumer** silently drops managed-file changes whose size happens to be unchanged (digest-for-digest bumps are the canonical case). CI paths (drift gate, devkit-upgrade.yml) are unaffected because fresh checkouts have current mtimes — so the failure mode is local upgrades producing commits that the drift gate then correctly rejects.

## Fix

Add `--checksum` to the scaffold rsync (template is small; the cost is negligible) so the quick-check compares content, not size+mtime. Audit the other rsync invocations in `init-workspace.sh` for the same pattern.

Blocker for the 1.6.0 train: fix on `release/1.6.0`, cut rc2, re-bump the five lanes.
---

# [Comment #1]() by [c-vigo]()

_Posted on August 4, 2026 at 11:33 AM_

Fixed on release/1.6.0 via PR #1345 (--checksum on all three template rsync invocations; TDD bats coverage). Ships in 1.6.0-rc2 — live proof will be the scorecard.yml diff finally appearing in the four previously-red consumer lanes on the rc2 re-bump.

