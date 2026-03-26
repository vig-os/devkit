---
type: issue
state: closed
created: 2026-03-25T18:36:48Z
updated: 2026-03-26T10:39:36Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devcontainer/issues/446
comments: 0
labels: chore, area:ci
assignees: c-vigo
milestone: none
projects: none
parent: none
children: none
synced: 2026-03-26T17:53:31.585Z
---

# [Issue 446]: [[CHORE] Enforce immutable git tags and GitHub releases; align rollback workflows](https://github.com/vig-os/devcontainer/issues/446)

## Chore Type
CI / Build change

## Description
Git tags and GitHub Releases should be treated as **immutable**: once published, they must not be rewritten or deleted by automation (or by default repo policy). Today, failed release runs can still **delete** a created tag during rollback (e.g. `release.yml`), which conflicts with immutability and with stricter repo settings.

This issue covers:
1. **Repository configuration** — enable settings/rules so tags (and releases, where applicable) cannot be casually updated or removed (e.g. tag protection / rulesets, immutable release behavior as offered by GitHub for the org/repo).
2. **Workflow alignment** — update **rollback** jobs so they no longer rely on **deleting** tags (or mutating published releases). Compensation should be documented and implemented (e.g. branch-only rollback, failure issues with manual guidance, follow-up patch release), consistent with “publish” vs “post-publish” stages already called out in release docs.

## Acceptance Criteria
- [ ] Repository (and org, if required) is configured so release tags and GitHub Releases match the project’s **immutability** policy (document **what** was enabled and **where** in runbooks or release docs, single source of truth).
- [ ] Rollback paths in CI (at minimum `.github/workflows/release.yml` and the mirrored workspace workflow under `assets/workspace/.github/workflows/release.yml` if still authoritative) **do not** attempt tag deletion when immutability is enforced; behavior is explicit in logs and in the rollback issue body.
- [ ] `docs/RELEASE_CYCLE.md`, `docs/DOWNSTREAM_RELEASE.md`, or other canonical release docs are updated if user-visible rollback behavior changes.
- [ ] No regression in failure visibility (failed releases still produce clear issues / logs).

## Implementation Notes
- Current rollback deletes the remote tag via GitHub API, e.g. `gh api ... -X DELETE` on `git/refs/tags/$TAG` in `.github/workflows/release.yml` (and workspace copy).
- Confirm interaction with **protected tags**, **rulesets**, and **immutable releases** (GitHub product names/settings may vary by plan); adjust app/token permissions if rollback strategy changes.
- `prepare-release.yml` rollback appears focused on **branch** / changelog cleanup; verify no hidden tag mutation paths.

## Related Issues
- Historical rollback issues note “Release tag deleted (if created)” — behavior will change once this is done.

## Priority
Medium

## Changelog Category
Changed

## Additional Context
Aligns supply-chain / audit expectations: released refs should remain stable; failed pipelines should clean up **mutable** state without assuming tags can be removed.
