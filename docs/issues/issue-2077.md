---
type: issue
state: open
created: 2026-11-17T16:13:49Z
updated: 2026-11-17T19:41:10Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/2077
comments: 3
labels: bug
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-11-17T20:22:45.561Z
---

# [Issue 2077]: [[BUG] 1.19.0 setup-devkit-toolchain: cachix-action fails 'Error: not found: cachix' (stepv adoption PR)](https://github.com/vig-os/devkit/issues/2077)

## What happens
The devkit 1.19.0 adoption PR in `vig-os/stepv` (#193, opened by the devkit-upgrade app) fails in **Set up devkit toolchain**, in every job that uses it: Tests, Lint & Format, Commit Messages and Scaffold Drift. The error is:

```
warning: unable to download 'http://10.0.2.2:8093/nix-cache-info': Could not connect to server (7) …
##[error]Action failed with error: Error: not found: cachix
##[end-action id=__self.__cachix_cachix-action;outcome=failure
```

- **Run:** vig-os/stepv run 42642084643 (re-run 2026-11-17 16:10Z).
- **The same jobs on stepv's main** (devkit 1.17.0 scaffold) pass on the same day, on the same runners.

## Likely cause
The 1.19.0 action adds `cachix/cachix-action` with `cachix-cache: ${{ vars.CACHIX_CACHE }}` and `cachix-auth-token: ${{ secrets.CACHIX_AUTH_TOKEN }}`. In this environment the `cachix` binary isn't on PATH when the action runs. Either the action expects to install it and can't, or it should be skipped when `vars.CACHIX_CACHE` is empty. stepv sets neither the variable nor the secret.

## Ask
- Skip the cachix step when no cache or token is configured.
- Or install cachix itself before using it.

stepv can't adopt 1.19.0 until this is fixed. Related: #2010 (the toolchain hang that blocks stepv's first release).
---

# [Comment #1]() by [gerchowl]()

_Posted on November 17, 2026 at 04:16 PM_

Correction: stepv **does** set `vars.CACHIX_CACHE=gerchowl` and `secrets.CACHIX_AUTH_TOKEN` (since 2026-10-13), so the step is correctly enabled by its `if: inputs.cachix-cache != ''`. The bug is narrower: `cachix/cachix-action@v17` can't find or install the `cachix` binary on this runner. The log shows the runner's local substituter `http://10.0.2.2:8093` unreachable just before the failure. Skipping when the cache isn't configured already works. The ask is that cachix-action install cachix through a path that doesn't depend on that substituter, or that the step fails soft (warn, continue without cachix).

---

# [Comment #2]() by [gerchowl]()

_Posted on November 17, 2026 at 04:17 PM_

Root cause found downstream: the runner's local substituter `10.0.2.2:8093` refuses connections on the ksb ARC runners (gerchowl/g-fleet#1500). So this is fleet infrastructure first. devkit's part is narrower: when that substituter or cachix is unavailable, setup should **fail soft and bounded** (warn and continue without cachix, with a per-step timeout) instead of failing every job or hanging until the job timeout (#2010).

---

# [Comment #3]() by [gerchowl]()

_Posted on November 17, 2026 at 07:41 PM_

The devkit fix is merged to dev in #2082 (1851247a). It missed the 1.19.1 cut, so it ships in the next release. That covers the devkit part only: a failing Configure Cachix step now degrades to a warning. The runner-local substituter is a fleet-side issue.

