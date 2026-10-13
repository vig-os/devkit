---
type: issue
state: open
created: 2026-10-13T00:20:31Z
updated: 2026-10-13T00:20:31Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1876
comments: 0
labels: none
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-10-13T09:14:40.847Z
---

# [Issue 1876]: [Event-scoped CI runner: send main-branch CI to a restricted runner while PR CI and the release train stay elsewhere](https://github.com/vig-os/devkit/issues/1876)

## Problem

`DEVKIT_CI_RUNNER` (`.vig-os`) and `DEVKIT_CI_RESOLVE_RUNNER` (repo/org variable) choose one runner for every event. A consumer cannot send trusted main-branch CI to a restricted self-hosted runner while keeping PR CI and the release train elsewhere.

That split is what restricted runner groups require. A group with `restricted_to_workflows` admits only `<repo>/.github/workflows/<file>@refs/heads/main`. A `pull_request` job that targets those labels stays queued forever. Build-only pools must also never run jobs that hold secrets. Two cases:

- **exo-pet/MPECT on ksb** (`self-hosted, Linux, X64, ksb, build-only, no-kvm, exo-pet`): main-branch CI should run there; PRs and releases must not.
- **#1869** (fix for #1863, merged into dev) routes `prepare-release`, `release`, `release-core`, `release-publish`, `promote-release` and the extension hooks through the same two knobs. After it ships, any consumer that points `DEVKIT_CI_RUNNER` at a build-only/no-secrets pool also sends its secret-bearing release jobs there.

`ci.yml` also has no `push` trigger, so main-branch CI cannot reach any runner through the managed file.

## Proposal

1. **An event-scoped runner key**, for example `DEVKIT_CI_RUNNER_MAIN`, plus an optional `DEVKIT_CI_RESOLVE_RUNNER_MAIN` variable.
   - `resolve-toolchain` emits it as `runner-json` only when the event is `push`, `schedule` or `workflow_dispatch` and the ref is the default branch.
   - Every other event keeps `DEVKIT_CI_RUNNER`, or the hosted default.
2. **An opt-in `push: branches: [<default>]` trigger for `ci.yml`**, rendered at scaffold time, for example `DEVKIT_CI_PUSH=true`. The existing `cancel-in-progress: != 'push'` guard already anticipates it.
3. **A separate `DEVKIT_RELEASE_RUNNER` for the release train.**
   - It should not inherit `DEVKIT_CI_RUNNER`, or should at least refuse labels marked `build-only`.
   - Release jobs hold secrets: `COMMIT_APP_*`, publishing tokens.
4. **The secret-bearing CI lanes need a fallback on a no-secrets runner.** `setup-devkit-toolchain` takes `cachix-auth-token` and the `container.credentials` use `GHCR_PULL_TOKEN`. When the main-branch runner is marked build-only, these should drop to anonymous pulls.

## Workaround in MPECT meanwhile

MPECT adds its own `ksb-main.yml` (push main / schedule / dispatch, ksb labels, `nix develop --command just ci-ksb`) and `ksb-pr.yml`. PR CI and releases stay on the managed workflows. Both runner knobs must stay off ksb, before and after #1869.

