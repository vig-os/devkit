---
type: issue
state: closed
created: 2026-09-18T21:49:58Z
updated: 2026-09-21T12:13:19Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1656
comments: 1
labels: feature, area:workspace, effort:small, semver:minor
assignees: c-vigo
milestone: none
projects: none
parent: none
children: none
synced: 2026-09-22T07:36:30.841Z
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

---

# [Comment #1]() by [c-vigo]()

_Posted on September 21, 2026 at 12:13 PM_

Resolved by #1664 (merged to `dev` as e6b4d5c3).

`DEVKIT_FEATURES_DISABLED=release` now takes the eight `[group('release')]` recipes in `.devcontainer/justfile.gh` with it, via a sentinel-bracketed excision in `render_release_optout()` — option (a) from the proposal. This follows the existing `render_actionlint_optout` shape and the `render_workflow_model` precedent, which already prunes `prepare-hotfix` from the same file under `DEVKIT_WORKFLOW=trunk`.

The secondary `gh-templates` question (changelog prose in `pull_request_template.md` and the issue forms) was deliberately left out: those surfaces already degrade gracefully — every issue form carries a `No changelog needed` option and nothing in scaffold CI gates the changelog — whereas the `just` surface exited non-zero. Worth a follow-up issue if it should change.

