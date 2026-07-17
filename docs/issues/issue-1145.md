---
type: issue
state: closed
created: 2026-07-16T06:01:03Z
updated: 2026-07-16T08:56:15Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1145
comments: 1
labels: bug, priority:medium, area:workspace, effort:small, semver:patch
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-07-17T05:20:03.506Z
---

# [Issue 1145]: [[BUG] #1111 gitignore migration leaks scaffold-committed files (.envrc) and language-template junk into .gitignore.project](https://github.com/vig-os/devkit/issues/1145)

### Description

The #1111 migration ("Migrated from the managed root .gitignore on upgrade") copies every entry from the consumer's old root `.gitignore` that is not in the regenerated managed base into `.gitignore.project` — verbatim, with no filtering. Observed on the sync-issues-action 1.3.0 deploy (vig-os/sync-issues-action#106, PR #108), where the old file was the pre-1.3.0 Python-template `.gitignore`:

1. **It migrated `.envrc`** — the old Python template ignored it, but in direnv mode `.envrc` is a scaffold-COMMITTED file ("committed for nix-direnv onboarding", #640). Since `.gitignore.project` is appended to the regenerated root `.gitignore`, the migrated entry silently shadows the scaffold's intent: the fresh `.envrc` stays untracked and direnv onboarding breaks for every other clone. `git check-ignore -v .envrc` confirmed the appended block won.
2. **~90 lines of Python-template noise** (`__pycache__/`, `.tox/`, `celerybeat-schedule`, `marimo/`, …) landed in a Node repo's consumer-owned file, obscuring the handful of real repo-specific entries (`dist/*` un-ignore set, `test_output`).

Hand-fixed in sync-issues-action PR #108 by rewriting `.gitignore.project`; every future migrated consumer hits the same thing.

### Steps to Reproduce

1. Take a consumer whose root `.gitignore` is a pre-1.3.0 managed template (Python-flavored) — or any old `.gitignore` containing `.envrc`.
2. Run `install.sh --version 1.3.0 --mode direnv --force`.
3. Inspect `.gitignore.project` → contains `.envrc` and the old template entries; `git check-ignore .envrc` → ignored.

### Expected Behavior

The migration should at minimum drop entries that shadow files the scaffold itself commits (`.envrc`; consider `.gitignore.project`, `justfile`, `flake.nix` for robustness). Ideally it should also skip entries that belong to a devkit language template (old or current) rather than treating them as repo-specific — the point of the migration is to preserve CONSUMER-authored ignores, not stale template bodies.

### Additional Context

Found during the sync-issues-action deployment 2026-07-15. Related: #1111 (original migration), #640 (`.envrc` committed contract), #1092 (append mechanism).
---

# [Comment #1]() by [c-vigo]()

_Posted on July 16, 2026 at 08:56 AM_

Fixed by #1146 (merged to dev). `migrate_root_gitignore()` now (1) never migrates entries shadowing scaffold-committed files (`.envrc`, `flake.nix`/`flake.lock`, `justfile`/`justfile.project`, `.vig-os`, `.gitignore.project`) and (2) builds the managed-entry filter from ALL `gitignore.d` fragments, so stale cross-language template lines no longer migrate as consumer entries. Covered by two new bats tests (incl. a `git check-ignore` assertion that the scaffolded `.envrc` stays committable); full init-workspace suite 208/208. Closing manually — dev merges don't auto-close. Ships to consumers with the next devkit release.

