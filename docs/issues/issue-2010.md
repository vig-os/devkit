---
type: issue
state: closed
created: 2026-11-03T11:59:57Z
updated: 2026-11-18T10:26:54Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/2010
comments: 6
labels: bug, area:ci
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-11-19T10:06:58.288Z
---

# [Issue 2010]: [[BUG] setup-devkit-toolchain hangs on cache.nixos.org substitution (direnv, hosted runner) until job timeout](https://github.com/vig-os/devkit/issues/2010)

## What happens

On hosted runners (`ubuntu-26.04`), the **Set up devkit toolchain** step in a direnv-mode consumer sometimes hangs while substituting from `cache.nixos.org`, until the job is cancelled about 14 minutes later. Sibling jobs of the same run, with the same flake and lock, finish the same step in about a minute.

Consumer: `exoma-ch/ravmatic` (private, devkit 1.18.0, flake input pinned `?ref=1.18.0`). Nix 2.35.2 via `cachix/install-nix-action@13d8dd5` (v31.11.1). Three occurrences in about two hours:

| Run / job | Last log line before the hang | Cancelled |
|---|---|---|
| 41622358121 Tests | `copying path '.../python3.13-semgrep-1.161.0'` (stdenv/gcc-wrapper just before) | +20 min |
| 41627136705 Commit Messages | `copying path '.../4xm4476...-stdenv-linux' from 'https://cache.nixos.org'` | 11:24:40 -> 11:38:58 |
| 41629596247 Lint & Format | `copying path '.../79mr0j...-gcc-wrapper-15.3.0'` and `'.../4xm4476...-stdenv-linux'` (same timestamp) | 11:43:04 -> 11:57:11 |

In the healthy jobs of the same run, the same two copies are followed within about 5 s by `building '.../nix-shell-env.drv'` and `devcontainer dev environment loaded (nix)`.

Every hang starts while two small paths are substituted **in parallel** (`gcc-wrapper` + `stdenv-linux`), right after the locally built `guardrails-0-unstable-2026-08-13` derivation. No error is printed. Nix's `stalled-download-timeout` (default 300 s) did not fire, which points at a stuck transfer or lock rather than a slow one.

## Impact

Each hang fails CI Summary and costs a 15-20 minute rerun. With 4 toolchain jobs per PR, roughly one PR in three hit it today.

## Suggestions

- Give the toolchain step its own `timeout-minutes` (e.g. 6), plus an automatic single retry of `nix develop --profile`, so a hang costs minutes instead of the whole job.
- In the action's `extra_nix_config`, set explicit `connect-timeout = 15`, `stalled-download-timeout = 60` and `download-attempts = 3`, so a stuck substitution fails fast and retries.
- Push the closure, including `guardrails` (built locally on every runner today), to `vig-os.cachix.org` so fewer paths are fetched cold. Related: #1784, #1891.

---

# [Comment #1]() by [gerchowl]()

_Posted on November 3, 2026 at 02:10 PM_

Same hang in a second consumer, `vig-os/vigil` (public), on hosted `ubuntu-26.04` runners, 2026-11-03. Three jobs were cancelled at their 30-minute timeout inside **Set up devkit toolchain**:

| Run / job | Job | Hang |
|---|---|---|
| 41632795978 / 125919105454 | Semver compatibility | 12:32:26 -> 13:02:42 |
| 41638554027 / 125942926301 | Rust checks (nix flake check) | 13:21:15 -> 13:51:29 |
| 41631438131 | Lint & Format, Commit Messages, JSON ordering | cancelled before any runner was assigned (`runnerName` null); probably unrelated queueing |

Log of 125942926301: `copying path '…-stdenv-linux' from 'https://cache.nixos.org'` and `building '…rust-1.95.0.drv'` at 13:22:25. Then nothing for 21 minutes, until:

```
13:43:29 warning: unable to download 'https://vig-os.cachix.org/nar/a2065d24-….nar.zst': HTTP error 200 (curl error: Stream error in the HTTP/2 framing layer)
13:51:29 ##[error]The operation was canceled.
```

So it isn't specific to `cache.nixos.org`: a substituter download stalls on an HTTP/2 stream, and Nix waits until the job timeout. Normal duration of the same step is about 1–2 minutes. In both cases a rerun of the same commit passed (the Semver job did, at least).

Suggested root-cause fix in the toolchain action's nix.conf: set `stalled-download-timeout` (e.g. 60) so a stalled transfer fails fast and is retried; also consider `http2 = false` given the framing error. Raising job timeouts would only hide it.

---

# [Comment #2]() by [gerchowl]()

_Posted on November 16, 2026 at 01:39 PM_

The same hang hits a third consumer, `vig-os/stepv` (public, hosted `ubuntu-26.04`), and now it blocks a **release**:

| Run / job | Job | Last log line before the hang | Cancelled |
|---|---|---|---|
| 43868408399 | Prepare Release Branch (`prepare-release.yml`, 0.1.0) | `building '/nix/store/ahb0kr7g…-rust-1.96.0.drv'...` at 13:14:23 | 13:27:45 |
| 43868408399 | Roll Back Prepare Release | same step | 13:38:09 |
| 42598328727 (2026-11-09) | Lint & Format, Commit Messages, Tests | `copying path '…-rust-1.96.0' from 'https://gerchowl.cachix.org'` | after the 15-min timeout, twice |

The same release's dry run (43868346593) passed minutes earlier, and its validate job finished the step normally. The rollback job hung in the same step, so the rollback itself can't run. In this case it was harmless, because nothing had been pushed yet.

**Ask:**
- a per-step timeout plus retry around the substitution;
- or prefetch the toolchain closure in a short separate step whose timeout fails fast and retries;
- and a rollback job that doesn't depend on the full devkit toolchain.

---

# [Comment #3]() by [gerchowl]()

_Posted on November 16, 2026 at 02:05 PM_

Update from stepv: this is **deterministic for `prepare-release.yml`'s Prepare Release Branch job**, 2 of 2. The retry, run 43877817364, hung at exactly the same line: `building '/nix/store/ahb0kr7g…-rust-1.96.0.drv'...` at 13:41:24, cancelled at 13:54:36. In the same hour, the PR CI jobs on stepv (e.g. `feature/141-graph-colours`, 13:55) set up the same toolchain fine. So the Prepare job seems to **build** `rust-1.96.0.drv` (the joined toolchain) locally instead of substituting it, and that build never finishes. It may be missing the substituters or trusted keys the CI jobs have, or a sandbox/IO difference. stepv can't release until this is fixed. The workflow is devkit-managed, so stepv can't patch it.

---

# [Comment #4]() by [gerchowl]()

_Posted on November 17, 2026 at 04:20 PM_

Root cause for the stepv Prepare Release hang: in the scaffold, only `ci.yml` passes `cachix-cache: ${{ vars.CACHIX_CACHE }}` to `setup-devkit-toolchain`. The release-lane workflows (prepare-release, prepare-hotfix, release, release-core, release-publish, promote-release, abandon-release, sync-issues, sync-main-to-dev, devkit-upgrade) call it without that input.

In stepv run 43877817364, "Configure Cachix" was skipped and 0 paths came from the consumer cache. The job then built the consumer-only derivations from source, including a patched `opencascade-occt-7.9.3`, and was cancelled at its 15-minute timeout. The `rust-1.96.0.drv` line is only the last build to *start*. The same hour, CI run 43880461559 pulled both paths from the consumer cache in seconds.

A fix is in progress on `bugfix/2010-release-lane-cachix`:
1. Pass the Cachix input (pull-only) at every call site, with a guard test.
2. Bound the realisation, using Nix's network timeouts plus an explicit wall-clock error.
3. Let a failing Cachix step degrade to a warning instead of failing the job (the devkit part of #2077).
4. Stop the rollback and cleanup jobs from realising the dev-shell.

---

# [Comment #5]() by [gerchowl]()

_Posted on November 17, 2026 at 07:41 PM_

The devkit fix is merged to dev in #2082 (1851247a). It missed the 1.19.1 cut, so it ships in the next release.

---

# [Comment #6]() by [gerchowl]()

_Posted on November 18, 2026 at 10:26 AM_

Shipped in [1.19.2](https://github.com/vig-os/devkit/releases/tag/1.19.2), via #2082. Consumers get it through the scheduled devkit-upgrade PR, or by running the upgrade now. Once on 1.19.2, stepv's `prepare-release.yml` pulls its toolchain from the `vars.CACHIX_CACHE` cache, so the patched OCCT and the rust toolchain no longer build locally. Toolchain setup is now limited to 6 minutes and ends with an explicit error if it runs over. Follow-ups are in #2085.

