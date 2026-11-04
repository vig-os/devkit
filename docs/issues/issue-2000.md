---
type: issue
state: open
created: 2026-11-03T09:28:14Z
updated: 2026-11-03T09:28:14Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/2000
comments: 0
labels: feature, area:workspace
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-11-03T12:23:59.228Z
---

# [Issue 2000]: [[FEATURE] GitHub-side bootstrap for new consumers: dev branch, repo merge settings, secret visibility, seeded CONTRIBUTING](https://github.com/vig-os/devkit/issues/2000)

## Description

The scaffold sets up the **working tree**. Everything on the **GitHub side**, which a multi-user gitflow repo needs before its first PR, is left to the user, and is partly undocumented.

## Problem Statement

Steps done by hand for `exoma-ch/ravmatic` (private, gitflow, devkit 1.18.0), after `install.sh`:

1. **Branches.** Init printed `Warning: Branch 'dev' not found ... Create it with: git branch dev` and skipped the scaffold commit ("Existing files detected"; the only prior state was `git init` plus `git remote add`). So the initial commit, `dev`, and pushing both were manual.
2. **Repo settings to match devkit's own** (`vig-os/devkit` itself: merge commits only, `delete_branch_on_merge`, `allow_update_branch`, `merge_commit_title=PR_TITLE`). Nothing applies or documents these for consumers.
3. **Release recipes.** In direnv mode, `justfile.project` carries `prepare-release`, `finalize-release` and `publish-candidate` as *commented* examples. `promote-release`, `abandon-release`, `prepare-hotfix` and a dry-run switch are missing, although the scaffold ships all of those workflows (see #1823).
4. **Seeded docs.** `README.md` is seeded as just `# README`, and no `CONTRIBUTING.md` is seeded. A multi-user consumer must write the branching model, PR target (`dev`), commit standard, release steps and the "merge the sync PR by hand" note from scratch. All of that follows from the manifest (`DEVKIT_WORKFLOW`, enabled feature groups).

## Proposed Solution

- A `just setup-github` recipe (or an `install.sh --setup-github` step, gated on `gh` auth) that is idempotent and prints what it changed. It would: create and push `dev` (gitflow); apply devkit's merge settings; verify that the App secrets for the enabled feature groups are visible to the repo; and list what the plan can't do (see the plan-aware issue).
- Seed a workflow-model-aware `CONTRIBUTING.md` (consumer-owned, never overwritten), rendered from the manifest.
- Ship the release recipes active in every mode (#1823).

## Related

#1765 (guided first setup), #1766 (AX budget for new-repo setup), #1845 (post-scaffold friction, CLAUDE.md), #1823.

