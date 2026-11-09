---
type: issue
state: open
created: 2026-11-08T10:50:35Z
updated: 2026-11-08T10:50:35Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/2065
comments: 0
labels: bug
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-11-09T09:33:49.352Z
---

# [Issue 2065]: [setup-devkit-toolchain: Nix fetches GitHub flake-input tarballs unauthenticated, so GitHub's unauthenticated timeouts (504) fail CI before tests](https://github.com/vig-os/devkit/issues/2065)

Seen on exo-pet/MPECT PR #382, 2026-11-08. Run 42470903925 failed twice before any test ran, during `Set up devkit toolchain`:
- attempt 1: an HTTP 504 downloading numtide/flake-utils;
- attempt 2: `unable to download 'https://github.com/nix-systems/default/archive/da67096a….tar.gz': HTTP error 504`.

githubstatus.com had an open incident at the time: *"Increase in timeouts for some unauthenticated users"*. The same URL returned 200 from an authenticated workstation.

**Root cause:** the toolchain step lets Nix fetch `github:` flake inputs as anonymous tarball downloads. They are not in the binary cache (`10.0.2.2:8093` was also briefly disabled in an earlier run), so every cold runner refetches them unauthenticated and is exposed to GitHub's anonymous rate limits and timeouts.

**Suggested fix:**
- configure Nix `access-tokens = github.com=${{ github.token }}` (or the App token) in setup-devkit-toolchain, via `NIX_CONFIG` or extra-nix-config, so tarball fetches are authenticated;
- and/or pre-seed or cache the locked flake-input sources on the runner.

Without one of these, CI is fragile at exactly the moment GitHub degrades anonymous access.
