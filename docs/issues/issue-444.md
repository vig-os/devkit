---
type: issue
state: closed
created: 2026-03-25T17:21:28Z
updated: 2026-03-26T07:32:03Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devcontainer/issues/444
comments: 0
labels: chore, priority:medium, area:ci, effort:small
assignees: c-vigo
milestone: none
projects: none
parent: none
children: none
synced: 2026-03-26T17:53:31.912Z
---

# [Issue 444]: [[CHORE] Remove PR Title Check workflow from CI](https://github.com/vig-os/devcontainer/issues/444)

## Chore Type
CI / Build change

## Description
Remove the **PR Title Check** GitHub Actions workflow (`pr-title-check.yml`). It produces too many false positives and blocks otherwise valid PRs (e.g. release automation).

Example failure: https://github.com/vig-os/devcontainer/actions/runs/23553640179

Rationale: PR title enforcement duplicates concerns already covered locally (e.g. commit-msg / pre-commit) and is brittle for bot-driven or conventionally titled release PRs.

## Acceptance Criteria
- [ ] `PR Title Check` / `pr-title-check.yml` is removed or clearly disabled so it no longer appears as a required PR check.
- [ ] Any references that assume this check exists are updated (e.g. docs, tests that list workflow job names) if they would otherwise fail or mislead.
- [ ] `CHANGELOG.md` updated under **Removed** (user-visible CI change) if applicable per project rules.

## Implementation Notes
- Primary file: `.github/workflows/pr-title-check.yml` (delete or replace with a no-op only if deletion is not desired — default preference: delete).
- Follow-up: confirm branch protection no longer lists "Validate PR Title" as required (repo settings; may be outside this repo's diff).

## Related Issues
Related context: #276, #221

## Priority
Medium

## Changelog Category
Removed

## Additional Context
None

