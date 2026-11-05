---
type: issue
state: open
created: 2026-11-04T12:11:21Z
updated: 2026-11-04T12:11:21Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/2039
comments: 0
labels: bug
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-11-05T09:17:49.330Z
---

# [Issue 2039]: [direnv scaffold: nix flake metadata .path is not realised on Nix 2.35 (install.sh, consumer ci.yml)](https://github.com/vig-os/devkit/issues/2039)

## Problem

The container-free scaffold (#1871) gets the devkit source with
`nix flake metadata --json github:vig-os/devkit/<tag> | jq -er .path` and then copies `$src/assets`. On **Nix 2.35** (`cachix/install-nix-action` currently installs 2.35.2), `flake metadata` reports the source store path **without realising it**. The copy then fails:

```
info: Fetching devkit 1.19.0-rc2 via nix...
cp: cannot stat '/nix/store/p0np527w6bvqx48b2k98cf2n9mviwync-source/assets': No such file or directory
error: Could not prepare the devkit assets from the flake source
```

This failed the Direnv Smoke lane of the 1.19.0-rc2 smoke test. It blocks 1.19.0.

## Evidence (each against a fresh, empty `--store`)

- Nix 2.35.3, `flake metadata --json … | jq .path`: path reported, `nix path-info` says `path … is not valid`, and there is no `assets/`.
- Nix 2.34.8, same command: path realised, `assets/` present.
- Nix 2.35.3, `flake prefetch --json … | jq .storePath`: path realised, `assets/` present.

## Affected sites

- `install.sh` (`devkit_flake_assets` fetch; also the `--dry-run` plan text that prints the command)
- `assets/workspace/.github/workflows/ci.yml` (Scaffold Drift in direnv mode), plus any devkit-side copy or drift pin
- `tests/bats/install.bats` stub for `flake metadata`

## Fix

Use `nix flake prefetch --json <ref> | jq -er .storePath`, which realises the source on 2.34 and 2.35.
