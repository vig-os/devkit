---
type: issue
state: open
created: 2026-10-08T08:51:56Z
updated: 2026-10-10T09:07:48Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1850
comments: 1
labels: bug, area:workflow, semver:patch
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-10-11T08:37:37.324Z
---

# [Issue 1850]: [[BUG] release-core validate fails with 'Resource not accessible by integration': the Release App needs checks:read and statuses:read](https://github.com/vig-os/devkit/issues/1850)

## What happens

In a downstream consumer on devkit 1.18.0, `release.yml` (final, including `dry-run: true`) fails in **Release Core / Validate Release Core → Find and verify PR**:

```
GraphQL: Resource not accessible by integration (repository.pullRequests.nodes.0.statusCheckRollup.nodes.0.commit.statusCheckRollup)
```

The step reads the release PR's `statusCheckRollup` (the CI-green gate) with the Release App token (`steps.auth.outputs.token`). The App installation granted `actions`, `contents`, `issues`, `packages` and `pull_requests` but **not** `checks: read` or `statuses: read`. Without those, GitHub refuses the rollup query.

## Fix applied downstream

After adding **Checks: read** and **Commit statuses: read** to the Release App and accepting the updated permissions on the consuming org's installation, the gate passes.

## Ask

- Document the full required permission set for the Release App (and the Commit App) in `docs/DOWNSTREAM_RELEASE.md`. `checks: read` and `statuses: read` are currently not listed anywhere.
- Optionally, preflight it: fail early in `validate` with a clear message naming the missing permission, instead of the raw GraphQL error after three retries.

## Related, same release

The changelog-freeze trailing blank line (#1842) also blocked this release: CI on the release PR went red until it was fixed by hand.
---

# [Comment #1]() by [gerchowl]()

_Posted on October 10, 2026 at 09:07 AM_

Hit this in gerchowl/claude-config on the 0.2.0 final release, 2026-10-10. Run https://github.com/gerchowl/claude-config/actions/runs/38040029496: `Validate Release Core` failed with `Resource not accessible by integration (repository.pullRequests.nodes.0.statusCheckRollup...)`. The RELEASE_APP was provisioned with contents/issues/pull_requests/actions, as the adoption docs said, and with no checks or statuses scope. The provisioning docs or template should list `checks: read` and `statuses: read`.

