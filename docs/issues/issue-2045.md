---
type: issue
state: open
created: 2026-11-04T13:35:50Z
updated: 2026-11-04T13:46:36Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/2045
comments: 1
labels: bug
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-11-05T09:17:45.934Z
---

# [Issue 2045]: [ci: org-level CI_RUNNER_* variables route container-mode consumers onto runners without a container runtime](https://github.com/vig-os/devkit/issues/2045)

## Problem

The 1.19.0 runner selection (#1907/#1909, ADR-site-agnostic-projects §5) routes every lane to `vars.CI_RUNNER_*` whenever those variables are set. GitHub Actions `vars.*` also resolves **organisation-level** variables, and from an expression you cannot tell an org variable apart from a repo variable.

In an org that sets `CI_RUNNER_*` at org level (visibility: all) for its self-hosted pool, every **container-mode** consumer in that org picks those runners up on adopting 1.19.0, even though it never opted in. If the pool has no container runtime (for example nix-native ephemeral runners without a docker socket), every `container:` lane fails at `Initialize containers`:

```
failed to connect to the docker API at unix:///var/run/docker.sock
##[error]Value cannot be null. (Parameter 'network')
```

Scaffold Drift fails the same way (`docker run` on the host).

ADR §5 assumes: "A container-mode consumer's runners already need a container runtime for the `container:` lanes, so any class it routes is container-capable." That holds for repo-level variables a consumer sets on purpose. It does not hold for variables inherited from the org.

## Evidence

The 1.19.0-rc3 smoke test failed in the smoke repo: deploy PR CI on the org pool. 1.18.2 ran the same jobs on hosted `ubuntu-26.04` and passed.

Consumer rollout is automated (`devkit-upgrade`), so every container-mode repo in such an org would break on adoption. This blocks 1.19.0.

## Design question

Where should "this runner pool can run `container:` jobs" live, and what is the default when it is absent? See the owner decision linked from the release PR.
---

# [Comment #1]() by [gerchowl]()

_Posted on November 4, 2026 at 01:46 PM_

**Decision (owner, 2026-11-04): opt-in key in `.vig-os`.**

- New `.vig-os` key `DEVKIT_CI_CONTAINER_RUNNERS` (`true`/`false`, default `false`).
- Container-ish modes (`devcontainer`, `both`): lanes use the `CI_RUNNER_*` labels only when the key is `true`. Otherwise every lane runs on hosted `ubuntu-26.04`, as in 1.18.x, and the resolver emits a notice that names the key.
- `direnv` and `bare` modes are unchanged: they keep honouring `CI_RUNNER_*`.
- Rationale: whether a container-mode repo's runners can run `container:` jobs is not something an inherited org variable can prove, so the repo states it explicitly. No consumer breaks on upgrade, and no infra change is needed.

