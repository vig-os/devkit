---
type: issue
state: closed
created: 2026-07-14T11:46:47Z
updated: 2026-07-14T15:14:47Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1062
comments: 1
labels: bug, priority:low, area:workspace, area:docs, effort:medium, semver:patch
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-07-14T20:06:24.199Z
---

# [Issue 1062]: [[BUG] Remaining scaffolded references to unshipped devkit docs (composite actions, flake.nix, issue template, skills)](https://github.com/vig-os/devkit/issues/1062)

## Problem

The #1057 lint was deliberately scoped conservatively (workflow header comments + `docs/*.md` cross-links) to keep false positives at zero. Its development surfaced further genuine instances of the #1046/#1056 dangling-reference class that remain unfixed and outside the lint's current reach — all point at devkit-only docs a consumer never receives:

- `assets/workspace/.github/actions/resolve-toolchain/action.yml` and `setup-devkit-toolchain/action.yml` comment refs (ADR-conditional-container-toolchain.md, MIGRATION.md)
- `assets/workspace/flake.nix` comments (NIX.md, MIGRATION.md)
- `assets/workspace/.github/ISSUE_TEMPLATE/docs.yml` (docs/templates/CONTRIBUTE.md, docs/RELEASE_CYCLE.md)
- `.claude/skills/pr_create/SKILL.md`, `.claude/skills/pr_post-merge/SKILL.md` (docs/RELEASE_CYCLE.md), and other skills referencing repo-root CLAUDE.md/templates
- Prose in `docs/container-ci-quirks.md`; historical entries in `.devcontainer/CHANGELOG.md` (likely exempt — history is immutable)

## Fix

Rewrite to absolute canonical URLs (as #1056 did) and extend the lint's extractors file-type by file-type, keeping the zero-false-positive bar. Changelog history should be allowlisted, not rewritten.

Refs: #1056, #1057, #1046
---

# [Comment #1]() by [c-vigo]()

_Posted on July 14, 2026 at 03:14 PM_

Fixed in #1066 (merged to dev): all 16 remaining unshipped-doc references rewritten to absolute canonical URLs (SSoT copies edited, manifest-synced scaffold regenerated), and the scaffold lint's rule 1 extended to composite actions, flake.nix, issue templates, skills, and docs prose — empty allowlist, changelog history excluded by construction.

