---
type: issue
state: open
created: 2026-10-11T21:49:28Z
updated: 2026-10-11T21:49:28Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1865
comments: 0
labels: none
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-10-12T08:59:43.780Z
---

# [Issue 1865]: [scaffold-drift cannot run on a darwin DEVKIT_CI_RUNNER: it shells out to docker and runs the Linux devkit image](https://github.com/vig-os/devkit/issues/1865)

Second darwin blocker found while routing a direnv consumer onto a self-hosted macOS runner (companion to #1864, which is the `tac` one).

## Symptom

`gerchowl/pidgy`, devkit 1.18.0, `DEVKIT_MODE=direnv`, `DEVKIT_CI_RUNNER=self-hosted,macOS,ARM64,sage`:

```
Authenticating to ghcr.io as 'gerchowl'
/Users/admin/actions-runner/_work/_temp/41d856ca-….sh: line 8: docker: command not found
##[error]Process completed with exit code 127
```

with step env:

```
IMAGE: ghcr.io/vig-os/devcontainer:1.18.0
IMAGE_TAG: 1.18.0
```

## Why this one is architectural, not a missing binary

Unlike #1864, installing the missing tool does not fix it. The `scaffold-drift` lane re-runs the pinned scaffold by **running the devkit container image**, and that image is `linux/amd64`. On a macOS runner there is no Docker daemon, and even with podman installed the Linux image cannot execute natively — it would need a Linux VM, on a runner that is already a VM.

So `scaffold-drift` and a darwin `DEVKIT_CI_RUNNER` are mutually exclusive as currently built. This generalises a constraint already visible elsewhere: darwin is incompatible with `DEVKIT_MODE=both`/`devcontainer`, because those resolve a Linux job container. What is new here is that it bites in **direnv** mode too, where every other lane is container-free and works fine.

## Why the current escape hatch is unsatisfying

`DEVKIT_DRIFT_CHECK=false` turns the gate off, and the job's own error message suggests it. That is what I am doing in the consumer for now, because the alternative is one permanently-red lane that destroys the signal value of the whole run. But it trades away a gate that catches real problems — a `DEVKIT_VERSION` bump without a re-scaffold, or a hand-edited managed file. The consumer that most needs drift detection (one pinned to an older devkit) is exactly the one that now has to disable it.

## Options, roughly in order of preference

1. **Pin this lane independently.** A `DEVKIT_CI_DRIFT_RUNNER` key (or reuse `DEVKIT_CI_RESOLVE_RUNNER`'s hosted default) so `scaffold-drift` stays on `ubuntu-26.04` while the Nix-native lanes move to the self-hosted runner. Smallest change, and it matches the precedent already in `ci.yml` — `dependency-review` is hardcoded hosted for an analogous reason.
2. **Make the drift check Nix-native.** If the scaffold assets were reachable as a flake output rather than only by running the image, the lane would be platform-agnostic and would not need a container runtime at all. Bigger change, removes a whole class of this problem.
3. **Detect and skip with a loud notice** when the runner is darwin, rather than failing with `command not found`. Strictly better than the current behaviour even if 1 or 2 lands later — the present failure mode looks like a broken runner, not an unsupported combination.

Option 1 would let a consumer keep full coverage: drift on hosted (it is a cheap job), everything else self-hosted.

## Context

The motivation for self-hosted here is that hosted minutes are unavailable — an account spending limit fails every run before its first step — so "just run it on `ubuntu-26.04`" is not currently an option for this consumer. That makes the hosted/self-hosted split per lane (option 1) the pragmatic shape: it needs hosted minutes only for the two small jobs that genuinely require Linux.
