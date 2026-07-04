# Home environment — rollback

| Surface | Roll back with |
|---|---|
| Standalone home-manager (laptops) | `home-manager generations` → run the previous generation's `activate` script |
| Org NixOS servers | `sudo nixos-rebuild --rollback switch` (rolls the whole system, home env included) — coordinate, it is shared |
| Devcontainer | pin the previous image tag in `.vig-os` (`DEVCONTAINER_VERSION=`) |
| Module updates via your flake | `nix flake lock --override-input vigos github:vig-os/devcontainer?ref=<previous-tag>` then switch |

A broken shell after activation: log in with `bash --noprofile --norc`, run
the previous generation's `activate`, then debug at leisure. The
devcontainer is always the working fallback environment.

## x86_64-darwin (Intel Mac) — operational meaning of "best-effort"

The Intel-Mac tier is **eval-checked only**: CI never builds or caches its
closures, and nixpkgs 26.05 is the last release supporting the platform
(support ends 2026-12-31). If your build breaks, the supported fallback is
the amd64 devcontainer image (via podman machine) or the org servers over
SSH, until the pin moves past 26.05 — after which the laptop tier for this
machine is retired.
