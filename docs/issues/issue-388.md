---
type: issue
state: closed
created: 2026-03-20T07:11:31Z
updated: 2026-03-20T08:30:05Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devcontainer/issues/388
comments: 0
labels: docs, area:ci, area:workflow, effort:small
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-03-21T04:09:46.691Z
---

# [Issue 388]: [[DOCS] Include release_kind in smoke-test dispatch payload header comment](https://github.com/vig-os/devcontainer/issues/388)

## Description

The header comment in `assets/smoke-test/.github/workflows/repository-dispatch.yml` documents optional `client_payload` keys but omits `client_payload.release_kind`, which is now supported and validated by the workflow.

This causes documentation drift between accepted dispatch inputs and the documented payload contract.

## Documentation Type

Fix incorrect or outdated content

## Target Files

- `assets/smoke-test/.github/workflows/repository-dispatch.yml` (header comment under `# Dispatch payload`)

## Related Code Changes

- Follow-up to smoke-test manual deploy PR discussion: https://github.com/vig-os/devcontainer-smoke-test/pull/41
- Related release orchestration fix: #386

## Acceptance Criteria

- [ ] Header comment optional payload list includes `client_payload.release_kind`
- [ ] Ordering/formatting of optional payload keys remains readable and consistent
- [ ] Commented dispatch contract matches actual validation logic in the workflow

## Changelog Category

No changelog needed

## Additional Context

This is a documentation consistency follow-up only; behavior is already implemented.
