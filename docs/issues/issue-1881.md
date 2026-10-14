---
type: issue
state: open
created: 2026-10-13T10:13:01Z
updated: 2026-10-13T10:13:01Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1881
comments: 0
labels: none
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-10-14T07:24:35.726Z
---

# [Issue 1881]: [security(ci): managed ci.yml passes the Cachix push token to same-repo pull_request runs (cache poisoning)](https://github.com/vig-os/devkit/issues/1881)

**Security: the managed `ci.yml` gives the Cachix push token to pull-request runs from branches in the same repository.** Code in those runs is unreviewed and runs on a runner with sudo, so it can push arbitrary store paths into the consumer's binary cache.

Cachix signs uploads with the cache's own key, so whatever is pushed is trusted. That includes fake contents under a real dependency's store path, which a later release build would install. Found in vig-os/stepv while wiring Cachix for vig-os/stepv#81. The managed file can't be fixed downstream, because devkit regenerates it.

## Observed
In vig-os/stepv, the devkit-managed `.github/workflows/ci.yml` passes `secrets.CACHIX_AUTH_TOKEN` to the nix setup step on `pull_request` events from same-repo branches. As a result, `skipPush` is false and `~/.config/cachix/cachix.dhall` is written, readable by every later step.

## Expected (what vig-os/stepv#81 does in its own workflows)
- On `pull_request`, the run pulls only: `skipPush: true`, and NO `authToken` at all, so no token reaches disk or the environment.
- Only trusted events push: `push` to the default branch, release tags, and `workflow_dispatch` on the default branch.
- A PR-only guard step fails the run if `cachix.dhall` or `CACHIX_AUTH_TOKEN` exists.

## Acceptance
- [ ] The managed `ci.yml` follows the push boundary above, for every job that uses Cachix.
- [ ] A consumer's PR run log shows pull-only, with no token.
- [ ] The docs state who can push.

Related: #1784 (seeded CI cache, plus an opt-in trusted release-cache push), which is the feature this hole sits in.

