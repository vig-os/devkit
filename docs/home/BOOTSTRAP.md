# Home environment — bootstrap

The vigOS terminal home environment ships as home-manager modules from this
repo (`vigos.*`, see the [ADR](../rfcs/ADR-home-environment-modules.md)).
Everything here is **opt-in**: the devcontainer and per-project dev-shells
work without any of it.

## 1. Install Nix

Use the [Determinate Systems installer](https://install.determinate.systems)
(flakes enabled by default, clean uninstall, survives macOS upgrades):

```bash
curl --proto '=https' --tlsv1.2 -sSf -L https://install.determinate.systems/nix | sh -s -- install
```

## 2. macOS only: trust the binary caches

On a multi-user install, cache settings in `~/.config/nix/nix.conf` are
**silently ignored** unless you are a trusted user — everything then builds
from source and Nix "feels broken". Add yourself in the **system**
`/etc/nix/nix.conf`:

```
trusted-users = root <your-username>
```

then restart the daemon (`sudo launchctl kickstart -k system/org.nixos.nix-daemon`).
The flake's `nixConfig` carries the `vig-os` Cachix substituter; with
trusted-user status, `accept-flake-config` makes it effective.

## 3. Scaffold your personal flake

```bash
mkdir -p ~/my-home && cd ~/my-home
nix flake init -t github:vig-os/devcontainer#personal
$EDITOR flake.nix   # username, homeDirectory, system, git identity
```

## 4. First activation

Home-manager refuses to overwrite dotfiles it does not manage. On a machine
with an existing `~/.bashrc` / `~/.zshrc` / `~/.gitconfig`, let it back them
up:

```bash
nix run home-manager -- switch --flake .#me -b backup
```

Your old files land next to the originals as `*.backup`; merge anything you
want to keep into your flake (see the [cookbook](COOKBOOK.md)), then delete
the backups. Afterwards, plain `home-manager switch --flake .#me`.

## 5. One home-manager mode per user per host

Centrally-managed (the NixOS-module route on org servers) and standalone
home-manager share activation state and must **never** be mixed for the same
user on one machine. Different users on one host may differ. On org servers
your home environment is managed for you if you opted in — do not run
standalone `home-manager switch` there.

## Uninstall

`home-manager uninstall` removes the environment (your `*.backup` files
remain); the Determinate installer ships `/nix/nix-installer uninstall`.
