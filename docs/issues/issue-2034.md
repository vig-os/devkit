---
type: issue
state: open
created: 2026-11-04T08:47:41Z
updated: 2026-11-04T08:47:41Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/2034
comments: 0
labels: none
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-11-04T08:54:27.914Z
---

# [Issue 2034]: [test_migration_docs_and_changelog_match_the_new_contract breaks when the changelog is frozen for a release](https://github.com/vig-os/devkit/issues/2034)

`tests/test_seeded_hook_runner_migration.py::test_migration_docs_and_changelog_match_the_new_contract` asserts that `[#1929]` is in the FIRST `### Added` list of CHANGELOG.md, which is under `## Unreleased`. prepare-release 1.19.0 moved the entries into `## [1.19.0] - TBD`, so the test fails on release/1.19.0 (#2033) and now on dev.

Fix: assert the entry exists under an `### Added` heading in Unreleased OR in the pending or most recent release section, without depending on which section is first. Also scan the repo's tests for the same brittle pattern (`changelog.split("### Added", 1)` and the like) and fix them all.

Refs: #1929
