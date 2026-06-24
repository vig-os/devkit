---
type: issue
state: open
created: 2026-06-23T19:44:57Z
updated: 2026-06-23T19:44:57Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devcontainer/issues/664
comments: 0
labels: bug
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-06-24T06:13:08.526Z
---

# [Issue 664]: [bugfix: Nix image scaffolds dangling, read-only symlinks into a new workspace](https://github.com/vig-os/devcontainer/issues/664)

## Context

Discovered during local testing of the Nix-image install flow (epic #625, prepping the #639 cutover).

`dockerTools.buildLayeredImage` represents the baked workspace template as **symlinks into `/nix/store`** — e.g. `/root/assets/workspace/flake.nix -> /nix/store/<hash>-devcontainer-bootstrap/root/assets/workspace/flake.nix`. `assets/init-workspace.sh` scaffolds a new workspace with `rsync -a` (`-a` implies `-l`, copy symlinks as symlinks). So a real install (host project dir bind-mounted into the container) produces **dangling symlinks** on the host — the store path exists only inside the image — and even when resolved they are **read-only** (`0444`, from the immutable store).

This is **Nix-image-specific**: the Debian `Containerfile` `COPY`s the assets as real, writable files, so the published image is unaffected.

## Why CI missed it

The install/integration tests (`test_integration.py`, `test_install_script.py`) run against the **Debian** image (the `build-image` action's default). The Nix image only gets the portable **testinfra** suite (`nix-image.yml`), which never exercises the init/scaffold flow. So this was latent.

## Repro

```bash
nix build .#devcontainerImage && docker load -i result
docker run --rm -v /tmp/dummy:/workspace ghcr.io/vig-os/devcontainer:<tag> \
  /root/assets/init-workspace.sh --no-prompts --mode both
ls -la /tmp/dummy/flake.nix   # => symlink into /nix/store (dangling on host)
```

## Fix

- `assets/init-workspace.sh`: rsync with `--copy-links` (dereference the store symlinks into real files) and `chmod -R u+w "$WORKSPACE_DIR"` after scaffolding (restore writability; keep the existing `+x` on `*.sh`/`.githooks`). Debian-safe (no-op there).

## Regression guard

- A static bats assertion that the scaffold rsync uses `--copy-links` and the workspace is made writable.
- A behavioural step in `nix-image.yml` that scaffolds via the **real Nix image** and asserts there are no dangling symlinks (`find -xtype l`) and that `flake.nix` is a regular, writable file.

## Acceptance criteria

- A workspace scaffolded from the Nix image contains real, writable files (no `/nix/store` symlinks).
- The install/scaffold flow is exercised against the Nix image in CI so this cannot regress.

Refs: #625, #634, #639
