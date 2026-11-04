---
type: issue
state: open
created: 2026-10-25T16:19:38Z
updated: 2026-10-25T16:19:38Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1910
comments: 0
labels: none
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-10-26T07:40:28.144Z
---

# [Issue 1910]: [[BUG] SECURITY.md and COMMIT_MESSAGE_STANDARD.md render without regard to DEVKIT_FEATURES_DISABLED / DEVKIT_REFS_POLICY](https://github.com/vig-os/devkit/issues/1910)

**Version:** devkit 1.18.0, `--mode direnv --workflow gitflow`, solo profile (`docs/SOLO_ADOPTION.md`):
`DEVKIT_FEATURES_DISABLED=release,sync-issues,scanning,skills,worktree,gh-templates`, `DEVKIT_REFS_POLICY=optional`.

## Problem
Two managed files render text that contradicts the repo's own `.vig-os`:

1. `SECURITY.md` ("Security Practices") states *"OpenSSF Scorecard runs weekly"* and *"CodeQL static analysis scans the project and GitHub Actions workflows"*, and ships an "OpenSSF Scorecard accepted findings" section. With the `scanning` group disabled (`codeql.yml` / `scorecard.yml` are not scaffolded) neither claim is true — a published security policy promising scans that do not exist.
2. `docs/COMMIT_MESSAGE_STANDARD.md` says the `Refs:` line is *"Mandatory for most types"*, *"At least one reference to a GitHub issue must be present"*, and the Exemptions section lists only `chore`. With `DEVKIT_REFS_POLICY=optional` (or `DEVKIT_REFS_OPTIONAL_TYPES`) the hook and CI `validate-commit-range` accept every type without `Refs:`, so the document describes a different policy than the one enforced. (It does say "This section documents the stock default", but the rest of the text is unconditional.)

Both files are copied verbatim, so the render ignores `DEVKIT_FEATURES_DISABLED` / `DEVKIT_REFS_POLICY`.

## Why a consumer can't fix it durably
Neither file is in `PRESERVE_FILES` (`assets/init-workspace.sh`), so both are managed: the banner says *"local edits are lost"*, `install.sh --force` rewrites them, and the `ci.yml` **Scaffold Drift** job (re-scaffold + `git diff --cached`) goes red on any local edit. The only seams are `DEVKIT_UPGRADE_EXCLUDE` (covers the `devkit-upgrade` workflow only, not manual `--force` and not the drift job) and `DEVKIT_DRIFT_CHECK=false` (switches off the whole gate).

## Suggested fix
Render both files from the manifest: drop the scan lines/section from `SECURITY.md` when `scanning` is disabled, and make the `Refs:` wording/Exemptions section follow `DEVKIT_REFS_POLICY` / `DEVKIT_REFS_OPTIONAL_TYPES` (as is already done for the hook). Alternatively make them preserved-class, or let `DEVKIT_UPGRADE_EXCLUDE` also be honored by the drift job.

Found while adopting devkit in nerdmachines/inox.

