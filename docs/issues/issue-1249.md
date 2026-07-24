---
type: issue
state: closed
created: 2026-07-22T12:58:48Z
updated: 2026-07-23T15:59:30Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1249
comments: 1
labels: bug, priority:blocking, area:workspace, effort:small, semver:patch
assignees: none
milestone: 1.4.1
projects: none
parent: none
children: none
synced: 2026-07-24T05:27:31.286Z
---

# [Issue 1249]: [Scaffolded flake breaks on fresh install while devkit main predates the workflow argument](https://github.com/vig-os/devkit/issues/1249)

## Description

The scaffolded `flake.nix` (#1224) unconditionally forwards the new `workflow` argument to `vigos.lib.mkProjectShell`, but its `vigos` input ships **unpinned** (`github:vig-os/devkit`), so a fresh scaffold resolves devkit from `main`. Until 1.4.1 is promoted, `main` (= 1.4.0, `d16541f5`) has no `workflow` parameter, and every fresh direnv scaffold dies on first shell entry:

```
error: function 'mkProjectShell' called with unexpected argument 'workflow'
at «github:vig-os/devkit/d16541f5…»/flake.nix:241:9
```

## Live impact (release-blocking)

- devkit-smoke-test `release/1.4.1` PR #288: both **Direnv Smoke** jobs (fresh-install and preinstalled) fail with exactly this eval error.
- The smoke-test rc1 Release dispatch then fails on `ERROR: PR #288 has failed CI checks`.
- This **deadlocks the promote precondition**: devkit promote requires smoke-test's published final 1.4.1, but smoke-test's direnv gate cannot go green until devkit `main` carries the `workflow` argument — i.e. after promote.

Also reproduced locally: a fresh `install.sh --version 1.4.1-rc1 --mode direnv` scaffold cannot enter its shell (works after hand-pinning `vigos.url` to `?ref=1.4.1-rc1`).

Upgrades are NOT affected: `flake.nix` is on the preserve list (#640), so existing consumers keep their own flake.

## Expected Behavior

The template must stay compatible with the floating `vigos` input resolving to an older devkit. Forward `workflow` defensively — only when the resolved builder accepts it:

```nix
devShells.default = vigos.lib.mkProjectShell (
  { inherit pkgs; extraPackages = extraPackages pkgs; ... }
  // nixpkgs.lib.optionalAttrs
       (builtins.functionArgs vigos.lib.mkProjectShell ? workflow)
       { inherit workflow; }
);
```

This keeps the unpinned-input design (consumers ride main releases via `nix flake update`) while making new-template + old-devkit combinations degrade gracefully (gitflow default) instead of failing eval. Same rule for any future forwarded argument.

Fix targets `release/1.4.1` (rc respin), like #1216 in the 1.4.0 train.

Found during 1.4.1-rc1 validation, 2026-07-21.

---

# [Comment #1]() by [c-vigo]()

_Posted on July 23, 2026 at 03:59 PM_

Fixed by PR #1252 (functionArgs-guarded `workflow` forwarding; follow-up e60518b0 for the #1167 awk anchor), merged into `release/1.4.1`. Live-proven by the automatic smoke-test chain (Direnv Smoke green at rc2–rc4 and final). Shipped in [1.4.1](https://github.com/vig-os/devkit/releases/tag/1.4.1). Closing.

