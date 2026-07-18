---
type: issue
state: open
created: 2026-07-17T18:43:37Z
updated: 2026-07-17T18:43:37Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1194
comments: 0
labels: chore, priority:high, area:ci, effort:medium, area:testing
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-07-18T04:54:23.439Z
---

# [Issue 1194]: [devkit-smoke-test has no direnv-mode lane — two blocking rc bugs escaped to consumers](https://github.com/vig-os/devkit/issues/1194)

## Description

The 1.4.0 release cycle cut four release candidates; **two of the three blocking findings were invisible to the pre-consumer smoke test** because `vig-os/devkit-smoke-test` deploys in **container mode only**, and both bugs live on the **direnv** CI code path:

| Finding | Mode affected | Caught by smoke test? |
|---|---|---|
| #1187 (fromJSON manifest) | all modes (manifest load) | yes |
| #1189 (shellHook banner corrupts GITHUB_ENV) | direnv only | **no** — surfaced only on consumer PRs |
| #1192 (install-nix-action aborts on preinstalled Nix) | direnv + self-hosted | **no** — surfaced only on exo-fleet |

Both #1189 and #1192 are in `setup-devkit-toolchain`'s `if: inputs.mode == 'direnv'` branch, which the container-mode smoke consumer never executes. They were only found once real consumers (org-config, sync-issues-action, exo-fleet) ran their CI — i.e. after the RC was published and hand-validated. That is exactly the round-trip the smoke test exists to prevent.

## Suggested fix

Add direnv-mode coverage to the pre-consumer gate. Options (pick one):

1. **A direnv lane in devkit-smoke-test** — a second deploy/CI job (or matrix leg) that scaffolds `--mode direnv` and runs the managed `ci.yml` on a hosted runner, so the `setup-devkit-toolchain` direnv path (Detect host Nix → install/config → dev-shell → shellHook env forward) executes every release.
2. **A dedicated direnv smoke consumer repo** mirroring devkit-smoke-test's role for the host modes.

A self-hosted-runner leg (the #1173 path that hit #1192) is harder to add to a public gate; at minimum document that `DEVKIT_CI_RUNNER` + preinstalled-Nix is exercised only by downstream consumers, or add a job that fakes a preinstalled-Nix runner (Nix already on PATH) to force the host-Nix branch.

## Impact

Process gap, not a runtime bug — but it is the direct cause of two extra RC round-trips (rc2, rc3→rc4) this cycle. Highest-value item in the post-1.4.0 cleanup.

Refs: rollout validation PRs vig-os/org-config#54, vig-os/sync-issues-action#143, exo-pet/exo-fleet#230; findings #1189, #1192.
