---
type: issue
state: closed
created: 2026-09-28T21:39:18Z
updated: 2026-09-29T16:06:20Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1756
comments: 2
labels: none
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-09-30T08:17:48.185Z
---

# [Issue 1756]: [devkit-upgrade PR bumps .vig-os + .pre-commit-config.yaml but not the consumer's flake vigos input — new hooks fail to spawn](https://github.com/vig-os/devkit/issues/1756)

## Symptom

The devkit-upgrade bot PR that adopts 1.17.0 fails its own `Lint & Format` job in a direnv-mode
consumer:

```
shellcheck-composite-actions (lint composite action run bodies)....Failed
  error: Failed to spawn: `shellcheck-composite-actions`
    cause: No such file or directory (os error 2)
error: recipe `precommit` failed on line 46 with exit code 1
```

Seen on vig-os/tessera#445 (`chore: adopt devkit 1.17.0`, author `app/vigos-devkit-upgrade`), run
[36420631864](https://github.com/vig-os/tessera/actions/runs/36420631864).

## Cause

The upgrade PR changes exactly these files:

```
.github/workflows/codeql.yml
.github/workflows/scorecard.yml
.pre-commit-config.yaml      <-- adds the shellcheck-composite-actions hook
.vig-os                      <-- DEVKIT_VERSION 1.16.0 -> 1.17.0
zizmor.yml
```

It does **not** touch `flake.nix` / `flake.lock`. In `DEVKIT_MODE=direnv` the hook binaries come from
the consumer's dev-shell, which is pinned independently:

```nix
# flake.nix
vigos.url = "github:vig-os/devkit/1.16.0";
```

So the regenerated `.pre-commit-config.yaml` references a tool that only devkit 1.17.0's overlay
provides, while the dev-shell is still built from 1.16.0. The scaffold and the toolchain that has to
run it are bumped by two different mechanisms, and the upgrade PR only moves one of them.

This is not specific to `shellcheck-composite-actions` — any release that adds a hook backed by a new
binary breaks the adoption PR the same way. The failure is also self-inflicted by the PR that is
supposed to be the safe, reviewable upgrade path, so it lands on every consumer at once.

## Suggested fix

Have `devkit-upgrade.yml` rewrite the pinned devkit ref in the consumer's flake as part of the
adoption commit, alongside `DEVKIT_VERSION` — i.e. bump `github:vig-os/devkit/<old>` to the version
it is adopting and refresh `flake.lock` for that input. `DEVKIT_VERSION` in `.vig-os` and the flake
input are two encodings of the same number, so the upgrade should move them together (or the flake
should read the version from `.vig-os` so there is only one).

A narrower alternative, if rewriting a consumer's flake is out of scope: make the upgrade PR body
state that the flake input must be bumped in the same PR, and have the adoption fail loudly with that
message rather than as an opaque "failed to spawn".

Note `DEVKIT_MODE=devcontainer` consumers presumably do not see this, since their tooling comes from
the image tag that `.vig-os` already pins — which would explain why it has not surfaced before.

Filed from vig-os/tessera (`DEVKIT_MODE=direnv`).
---

# [Comment #1]() by [c-vigo]()

_Posted on September 29, 2026 at 02:34 PM_

Addressed together with #1752 in #1768 (to `dev`, rides the next release).

What changes for a direnv consumer with a pinned devkit input:

- New `.vig-os` key `DEVKIT_FLAKE_PIN_ADVANCE=true` makes every `install.sh --force` upgrade — including the weekly adoption PR — rewrite a pinned release ref to the new `DEVKIT_VERSION` (form preserved) and run `nix flake update <input>` in the same step, atomically. Default (empty) stays exactly as today.
- The scaffolded `ci.yml` now fails its `resolve-toolchain` job when a pinned release ref differs from `DEVKIT_VERSION`, with the remedy in the error — so the failure is explicit instead of `Failed to spawn` in lint. This gate does not depend on `DEVKIT_DRIFT_CHECK`.

Expected on this repo at the first adoption of that release: the adoption PR is red at `Check flake pin lockstep` once. Remedy in one commit on the adoption branch — bump the pin to the PR's `DEVKIT_VERSION`, run `nix flake update vigos`, set `DEVKIT_FLAKE_PIN_ADVANCE=true` in `.vig-os` — and merge before the next Monday 06:00 UTC `devkit-upgrade` run, which force-updates the branch. Since this repo has `DEVKIT_DRIFT_CHECK=false`, setting the key on `dev` ahead of the adoption is also safe and makes that PR green on its own.

Leaving this open until that first red-then-green adoption is observed live.

---

# [Comment #2]() by [c-vigo]()

_Posted on September 29, 2026 at 04:06 PM_

Resolved by #1768 (merged to `dev` as 9adbe219, rides the next release). At adoption time the knob is set with a commit on the adoption PR: bump the pin, `nix flake update vigos`, set `DEVKIT_FLAKE_PIN_ADVANCE=true` in `.vig-os`. From then on every upgrade moves the pin with the scaffold, and the new CI gate fails a PR whose pin lags `DEVKIT_VERSION` instead of `Failed to spawn`.

