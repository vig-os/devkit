# Personal vigOS home environment

1. Edit `flake.nix`: username, home directory, system, git identity.
2. First activation on a machine with existing dotfiles:
   `nix run home-manager -- switch --flake .#me -b backup`
3. Afterwards: `home-manager switch --flake .#me`

Everything the org ships is a default you can override — see the
override cookbook in the devkit repo (`docs/home/`).
