---
type: issue
state: closed
created: 2026-10-01T12:16:08Z
updated: 2026-10-01T12:55:44Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1793
comments: 1
labels: bug, area:ci
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-10-02T08:18:23.900Z
---

# [Issue 1793]: [fix(smoke-test): bind the listener's deploy job to DEVKIT_COMMIT_APP_ENVIRONMENT](https://github.com/vig-os/devkit/issues/1793)

## Problem

`render_commit_app_environment()` (`assets/init-workspace.sh`, #1710) binds a fixed list of nine token-minting jobs to `DEVKIT_COMMIT_APP_ENVIRONMENT`. The smoke-test listener `assets/smoke-test/.github/workflows/repository-dispatch.yml` is not on that list, yet its `deploy` job mints the commit App token (`Generate commit app token for signed commits`, `secrets.COMMIT_APP_CLIENT_ID` / `secrets.COMMIT_APP_PRIVATE_KEY`).

Harmless while the org/repo copies of the `COMMIT_APP_*` pair still exist: the unbound job reads them. But the documented end state (MIGRATION.md, "Move the secrets ... then remove the organization/repository copies") leaves the listener's `deploy` with no credentials, so the very first step of the next release train's smoke gate fails.

## Expected

With `DEVKIT_COMMIT_APP_ENVIRONMENT` set, `repository-dispatch.yml:deploy` also renders `environment: '<name>'` (and any other COMMIT_APP-minting job in that workflow, if present). The listener runs from the default branch, which the environment's branch policy already admits (`main`).

## Acceptance criteria

- [ ] `repository-dispatch.yml:deploy` added to the render list (only when the file is shipped, i.e. smoke-test scaffolds)
- [ ] Test pinning the binding on a `--smoke-test` scaffold, and no binding when the knob is empty
- [ ] MIGRATION.md "Which jobs get the key" list updated
- [ ] Audit: no other shipped workflow mints `COMMIT_APP_*` outside the list

## Context

Found while preparing the first live adoption on devkit-smoke-test (environment `commit-app`). Must ship before the fallback org secrets are removed from smoke-test's scope (planned for the train after next). Related: #1710.

---

# [Comment #1]() by [c-vigo]()

_Posted on October 1, 2026 at 12:55 PM_

Fixed on `dev` in #1794: `repository-dispatch.yml:deploy` is now in `render_commit_app_environment()`'s list, so a `--smoke-test` scaffold with `DEVKIT_COMMIT_APP_ENVIRONMENT` set binds the listener too. Reaches devkit-smoke-test with the next train; the org-secret fallback can be dropped from smoke-test's scope the train after (tracked in vig-os/devkit-smoke-test#440).

