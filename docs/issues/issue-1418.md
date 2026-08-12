---
type: issue
state: closed
created: 2026-08-11T09:27:13Z
updated: 2026-08-11T09:50:37Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1418
comments: 1
labels: feature, area:testing
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-08-12T04:13:06.442Z
---

# [Issue 1418]: [[FEATURE] Close coverage gaps from the test-suite audit: generate.py units, image tools, release ceilings, devc-upgrade, just doctor](https://github.com/vig-os/devkit/issues/1418)

## Description

The #1413 audit surfaced behaviors with no direct test coverage (out of scope there — pruning only). Close them:

- **`docs/generate.py` `load_skills`/`group_skills`**: only covered transitively via `test_generate_docs_actual`; no unit tests for skill parsing/grouping (malformed front matter, empty skills dir, grouping keys).
- **Image tests for locale, nvim, actionlint**: shipped in the image since 1.3.0 with no `test_image.py` coverage (locale generation/`LANG`, nvim runs, actionlint runs) — the audit's earlier trains flagged this gap.
- **Scaffold release token ceilings**: `test_workflow_release_extension.py` pins the extension seam's permission ceiling only; the scaffold `release-core.yml`/`release-publish.yml` job-level `permissions` blocks are unpinned — add shape tests so a permissions widening can't land silently.
- **Behavioral `devc-upgrade` coverage**: `just.bats` has only two (now-tightened) parser greps; add stub-driven behavioral tests for the `devc-upgrade` recipe (version parse from `.vig-os`, install.sh invocation args, runtime-missing error path) using the logging-stub pattern from `clean.bats`/`install.bats`.
- **`just doctor` host diagnostic**: replace the deleted `TestHostGitSignatureSetup` class (host git-signing/ssh/gh preflight, deleted in #1413 because skip-on-failure tests are not tests) with a `doctor` just recipe that reports host prerequisites as diagnostics, plus a bats test for its output shape.

## Problem Statement

These behaviors can regress silently today; the audit deleted the pseudo-tests that pretended to cover the host-preflight part.

## Proposed Solution

See Description bullets; each lands with its own test-first commit where testable.

## Impact

Test coverage and developer diagnostics only; one new user-facing `just doctor` recipe.

## Changelog Category

Added

## Additional Context

Refs: #1413 (out-of-scope list), #1103 (slimming-era image-test gap note)

---

# [Comment #1]() by [c-vigo]()

_Posted on August 11, 2026 at 09:50 AM_

Implemented in PR #1419 (merged to dev @662cc8a1): load_skills/group_skills unit tests, nvim/actionlint/locale image tests (executed live in the PR's Image Tests lane), scaffold release-core/release-publish permission-ceiling pins, behavioral devc-upgrade bats coverage via stubbed curl/podman, and the new `just doctor` host-diagnostics recipe (test-first) with changelog entry.

