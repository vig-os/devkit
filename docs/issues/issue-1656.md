---
type: issue
state: open
created: 2026-09-18T21:49:58Z
updated: 2026-09-18T21:49:58Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1656
comments: 0
labels: feature, area:workspace, effort:small, semver:minor
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-09-19T07:15:10.915Z
---

# [Issue 1656]: [[FEATURE] Release-disabled consumers keep release-only just recipes that assume a CHANGELOG](https://github.com/vig-os/devkit/issues/1656)

## Problem

[#1651](https://github.com/vig-os/devkit/issues/1651) puts the root `CHANGELOG.md` in the `release` feature group, so a consumer with `DEVKIT_FEATURES_DISABLED=release` is no longer handed a changelog it never writes.

The scaffolded `.devcontainer/justfile.gh` still ships release-adjacent recipes that assume one exists — `reset-changelog` (`prepare-changelog reset CHANGELOG.md`) and `changelog-preview`. `justfile.gh` is not part of the `release` group, so a release-disabled repo keeps them, and `reset-changelog` now fails on a missing file rather than on a missing workflow.

This is pre-existing in kind: the whole release-dispatch recipe set (`prepare-release`, `promote-release`, `finalize-release`, `abandon-release`, …) already ships to repos whose release workflows were pruned, where the recipes can only fail at dispatch time. #1651 just makes one of them fail earlier and more confusingly.

## Proposal

Decide what the `release` opt-out means for the `just` surface, then make it consistent:

- either add the release recipes to the `release` feature group (a rendered/pruned `justfile.gh` section, or a separate managed file the group can exclude);
- or have each release recipe fail fast with a clear "this repo has the `release` feature disabled (`DEVKIT_FEATURES_DISABLED`)" message instead of a missing-file/missing-workflow error.

The same question applies, more weakly, to the changelog references in `.github/pull_request_template.md` and the issue templates — those live in the separately opt-outable `gh-templates` group, so a repo that disables `release` but keeps `gh-templates` still gets asked for a changelog entry it has no file for.

## Scope note

Split out of #1651 rather than bundled: that PR is a scaffold-shape change, this is a question about what a feature group owns.

