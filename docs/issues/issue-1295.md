---
type: issue
state: open
created: 2026-07-29T13:33:54Z
updated: 2026-07-29T13:33:54Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1295
comments: 0
labels: feature, priority:high, area:workflow, effort:medium, semver:minor
assignees: none
milestone: 1.5.0
projects: none
parent: none
children: none
synced: 2026-07-30T05:15:33.766Z
---

# [Issue 1295]: [feat(workflow): scaffold-drift check in consumer CI (pin bumped without re-scaffold)](https://github.com/vig-os/devkit/issues/1295)

### Description

Add a job to the scaffolded consumer `ci.yml` that fails when the working tree's managed files do not match what the pinned devkit version would scaffold — i.e. when `.vig-os` `DEVKIT_VERSION` was bumped without re-running the scaffold, or managed files were hand-edited. Opt-out via `.vig-os`, default enabled.

### Problem Statement

The documented failure mode (`init-workspace.sh` #1093 warning) — flake-delivered hooks and scaffold-delivered files skewing apart — is completely unguarded in consumer CI today. A pin-only bump PR merges green: nothing re-runs the scaffold or diffs against it. Any upgrade automation (see the companion self-polling devkit-upgrade workflow issue) must be backstopped by this check; it equally protects manual bumps.

### Proposed Solution

- New `ci.yml` job (scaffold template): pull `ghcr.io/vig-os/devcontainer:$DEVKIT_VERSION` (read from `.vig-os` via the existing `resolve-toolchain` action), run the scaffold in preview/diff mode, fail on drift in managed files.
- Preferred mechanism: `install.sh --preview` (exists today, prints add/overwrite/preserve/delete without touching files) — may need a machine-readable / exit-code mode as part of this issue; alternative is re-scaffold-into-tempdir + `git diff --exit-code` over the managed set.
- `*.project` files and preserved `.vig-os` values are exempt by construction (the scaffold already preserves them).
- Cost control: gate the job on a `paths` filter (`.vig-os`, `flake.lock`, managed-file globs) or run on PRs only — the image pull is ~1.5 GiB.
- **Opt-out knob**: `.vig-os` key `DEVKIT_DRIFT_CHECK=true|false`, default `true`. The job reads it and self-skips when disabled (runtime gate, so flipping the knob needs no re-scaffold). Align naming/mechanism with the #1284 manifest-driven opt-outs work if that lands first.
- Also advances the drift half of the flake-side guards (#1093 lockstep warning covers pinned inputs only; #1263 shell-entry guard is advisory) into an enforced CI gate for floating-input consumers.

### Alternatives Considered

- Extending the #1093 scaffold-time warning: only fires during upgrades, not on the skewed PR itself.
- Hosted-Renovate pin tracking: watches the version string but cannot detect (or prevent) scaffold skew — the gap this issue closes.

### Impact

Consumers gain a hard gate against skewed upgrades; devkit's own repo is unaffected. Backward compatible: new job in the scaffolded `ci.yml`, lands at next adoption, opt-out available. Prerequisite for the self-polling devkit-upgrade workflow.

### Changelog Category

Added

