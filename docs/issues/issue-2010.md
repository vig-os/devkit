---
type: issue
state: open
created: 2026-11-03T11:59:57Z
updated: 2026-11-03T14:10:02Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/2010
comments: 1
labels: bug, area:ci
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-11-04T08:54:32.454Z
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

