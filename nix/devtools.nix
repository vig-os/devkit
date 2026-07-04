# The vigOS toolchain SSoT - one list, delivered everywhere: the dev-shell,
# the Nix-built image, and the vigos.packages home module. Lives outside
# flake.nix so the vigos.* path modules (nix/home/) can share it without
# duplicating the list. Refs #818.
pkgs: with pkgs; [
  # Build automation
  just

  # Git-hook runner: prek (Rust drop-in for the Python pre-commit,
  # faster and one fewer manylinux/FHS consumer). The SSoT runner for
  # the `.githooks` hooks and the flake's `checks.pre-commit`. Refs #778.
  prek

  # Version control & GitHub (gh from unstable via overlay)
  git
  gh
  lazygit
  delta

  # Python tooling (uv from unstable via overlay)
  uv

  # Node.js (devcontainer CLI via npm)
  nodejs

  # Shell testing: bats core + helper libraries (support/assert/file).
  # Wrapped so BATS_LIB_PATH is exported for bats_load_library. Refs #695.
  (batsWithLibs pkgs)

  # Shell & JSON utilities
  jq
  tmux
  shellcheck

  # Linting
  taplo
  nixfmt-rfc-style # nix file formatter (treefmt `nix fmt`, pre-commit hook)
  ruff # python linter/formatter (pre-commit ruff/ruff-format hooks)
  typos # source typo checker (pre-commit typos hook)
  deadnix # dead-Nix-code linter (flake `checks.deadnix`)
  statix # nix anti-pattern linter (flake `checks.statix`)

  # Container runtime
  podman

  # Agent / terminal toolkit (absorbed from #545)
  ripgrep # rg
  fd
  bat
  eza
  zoxide
  starship
  charm-freeze # freeze (charmbracelet terminal screenshots)
  expect
  neovim # nvim
  claude-code # claude
]
