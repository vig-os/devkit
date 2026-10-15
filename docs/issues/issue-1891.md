---
type: issue
state: open
created: 2026-10-14T20:10:21Z
updated: 2026-10-14T20:10:21Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1891
comments: 0
labels: feature, area:ci
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-10-15T07:15:43.849Z
---

# [Issue 1891]: [[FEATURE] Nix cache profile driven by repo visibility and CI runner (cachix / actions / substituter)](https://github.com/vig-os/devkit/issues/1891)

## Problem

#1784 plans one Nix cache setup for every consumer: a seeded CI cache with `nix-community/cache-nix-action` plus an
opt-in Cachix push for releases. Which cache is right depends on two facts devkit already knows at setup time:
**repo visibility** and **where CI runs** (`DEVKIT_CI_RUNNER`).

- **Cachix:** the free tier is for public (open-source) caches; private token-protected caches need a paid
  plan. A public cache matters because **external users** can pull the builds (`nix run github:…`, downstream
  flakes).
- **GitHub Actions cache** (what `cache-nix-action` uses): free up to 10 GB per repo for public and private
  repos alike, LRU-evicted, with entries dropped after 7 days unused. It only serves that repo's own jobs, and
  raising the limit needs a paid plan.
- **Self-hosted runners with a local substituter** (attic or a LAN cache, configured on the runner): the right
  cache already exists. Cachix there costs money, and the Actions cache adds an upload/download round trip to
  github.com for paths the LAN cache already serves.

Seen in a solo consumer (private repo, Free-plan org, `--mode direnv`, CI on self-hosted Kubernetes ARC pods with
a per-pod `/nix`, substituting from cache.nixos.org plus a LAN attic cache). Neither Cachix nor the Actions cache
helps there. The managed setup still threads `CACHIX_CACHE` / `CACHIX_AUTH_TOKEN` through, which also shows
#1881's exposure risk.

## Proposal

A `.vig-os` key, e.g. `DEVKIT_NIX_CACHE=auto|cachix|actions|substituter|none`, resolved by `resolve-toolchain`
and honoured by `setup-devkit-toolchain`:

| visibility | runner | `auto` resolves to |
|---|---|---|
| public | any | `cachix` (public, free; release push per #1784) + `actions` for CI speed |
| private | hosted | `actions` (`cache-nix-action`, free within 10 GB); Cachix only if set explicitly |
| private | self-hosted | `substituter`: trust the runner's nix.conf substituters, add nothing |

- **`substituter`** accepts any Nix binary cache, not only Cachix: `DEVKIT_NIX_SUBSTITUTERS` plus trusted keys for
  repos whose runners don't preconfigure one. attic is the common self-hosted case.
- **Install time:** `install.sh` / the solo guide picks the profile from `gh repo view --json visibility` and the
  chosen runner, and writes it into `.vig-os`. A `just doctor` style check flags a mismatch, e.g. Cachix on a
  private Free-plan repo with no paid cache.
- **Push boundary:** every profile stays pull-only on PR events (#1881). Writes come only from trusted events.
  For `substituter`, that means documenting a "warm the cache after `flake.lock` changes from trusted
  infrastructure" pattern rather than a CI push.

## Related

#1784 (seeded CI cache + release push: the `actions` and `cachix` implementations), #1881 (push token on PRs),
#1876 (event-scoped runners), #1890 (direnv docs), #1776 (cache spike).

