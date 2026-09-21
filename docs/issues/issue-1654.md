---
type: issue
state: open
created: 2026-09-18T21:34:54Z
updated: 2026-09-18T21:34:54Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1654
comments: 0
labels: feature, area:workspace, effort:medium, semver:minor
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-09-19T07:15:11.329Z
---

# [Issue 1654]: [[FEATURE] Auto-fold a byte-exact retired hook block in a preserved .pre-commit-config.yaml](https://github.com/vig-os/devkit/issues/1654)

## Problem

[#1652](https://github.com/vig-os/devkit/issues/1652) makes a retired hook block in a **preserved** `.pre-commit-config.yaml` visible: the scaffold warns with `file:line` and the adoption PR body carries a `preserved-hook-drift:` marker. That helps every consumer who still gets an adoption PR.

It does not help the ones that need it most. The pre-#1170 pymarkdown hook breaks `prek`, and `devkit-upgrade.yml` commits **in the project shell with the hooks running** — so the upgrade fails at the commit step, before the branch is published and before any PR exists. Those repos see a red scheduled run and a failure-report issue, and the notice that would explain it never reaches a reviewer.

## Proposal

Fold a known-bad block automatically when — and only when — it is unambiguously devkit's own retired output:

- the block matches the historical template shape **exactly** (byte-match against the retired block, not just the `repo:` line);
- the replacement is the current template's block for the same hook id;
- everything else in the consumer's file is untouched (their global/per-hook `exclude:` patterns, ordering, comments);
- the fold is reported loudly (a `preserved-hook-fold:` line alongside the existing `preserved-hook-drift:` channel) and shows up as a normal reviewable hunk in the adoption diff.

Precedent for surgically editing a consumer-owned file this way: `migrate_root_gitignore` ([#1145](https://github.com/vig-os/devkit/issues/1145)).

## Open questions

- Opt-in knob, or default-on for byte-exact matches only? Default-on is what unsticks the broken repos; an exact-match gate is what makes it safe.
- Does the fold belong in `install.sh`/`init-workspace.sh` (every upgrade path) or only in `devkit-upgrade.yml` (the automated lane that is actually blocked)?

## Scope note

Deliberately split out of #1652, which stays a read-only guard: rewriting a preserved consumer file is a different risk class and deserves its own issue, tests and review.

