{
  description = "vigOS devcontainer – toolchain SSoT (dev-shell + image basis)";

  inputs = {
    # Pinned stable channel: the controlled version document (flake.lock).
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-25.05";
    # Secondary channel, overlaid only for fast-moving tools (uv, gh, claude).
    nixpkgs-unstable.url = "github:NixOS/nixpkgs/nixpkgs-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs =
    {
      self,
      nixpkgs,
      nixpkgs-unstable,
      flake-utils,
    }:
    let
      # ---------------------------------------------------------------------
      # Overlay: pull fast-movers from nixpkgs-unstable.
      #
      # The stable channel (nixos-25.05) lags on tools that ship frequently and
      # whose latest version we want in both the dev-shell and the image. We
      # overlay only those few packages from unstable; everything else stays on
      # the pinned stable channel for reproducibility.
      # ---------------------------------------------------------------------
      fastMovers = [
        "uv"
        "gh"
        # claude (claude-code) is an agent CLI that moves very fast; track unstable.
        "claude-code"
      ];

      overlay =
        final: prev:
        let
          unstable = import nixpkgs-unstable {
            inherit (final) system;
            config.allowUnfree = true;
          };
        in
        builtins.listToAttrs (
          map (name: {
            inherit name;
            value = unstable.${name};
          }) fastMovers
        );

      # ---------------------------------------------------------------------
      # devTools — the single source of truth for the toolchain.
      #
      # This list is the shared basis for the dev-shell now and the image later
      # (#634). Adding a tool here adds it everywhere; the per-tool parity test
      # (tests/test_flake_devshell.py) reads `devShellTools` so it can never
      # drift from this list.
      # ---------------------------------------------------------------------
      devTools =
        pkgs:
        with pkgs;
        [
          # Build automation
          just

          # Version control & GitHub (gh from unstable via overlay)
          git
          gh
          lazygit
          delta

          # Python tooling (uv from unstable via overlay)
          uv

          # Node.js (bats, devcontainer CLI via npm)
          nodejs

          # Shell & JSON utilities
          jq
          tmux
          shellcheck

          # Linting
          hadolint
          taplo

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
        ];

      # Binary names exposed for the parity test. Prefer the package's declared
      # `meta.mainProgram` (the canonical executable name, e.g. ripgrep -> rg,
      # neovim -> nvim, claude-code -> claude); fall back to the pname.
      devShellToolNames =
        pkgs:
        map (
          drv: drv.meta.mainProgram or drv.pname or (builtins.parseDrvName drv.name).name
        ) (devTools pkgs);

      # ---------------------------------------------------------------------
      # mkProjectShell — reusable dev-shell builder for downstream repos.
      #
      # Consumers can build a shell with the shared toolchain plus their own
      # extra packages:
      #   devShells.default = inputs.devcontainer.lib.mkProjectShell {
      #     inherit pkgs;
      #     extraPackages = [ pkgs.foo ];
      #   };
      # ---------------------------------------------------------------------
      mkProjectShell =
        {
          pkgs,
          extraPackages ? [ ],
          shellHook ? ''echo "devcontainer dev environment loaded (nix)"'',
        }:
        pkgs.mkShell {
          packages = (devTools pkgs) ++ extraPackages;
          inherit shellHook;
        };
    in
    flake-utils.lib.eachDefaultSystem (
      system:
      let
        pkgs = import nixpkgs {
          inherit system;
          overlays = [ overlay ];
          config.allowUnfree = true;
        };
      in
      {
        devShells.default = mkProjectShell { inherit pkgs; };

        # Binary names of every tool in devTools — read by the parity test.
        devShellTools = devShellToolNames pkgs;

        packages = {
          # Stub for the Nix-built devcontainer image. The real image is built
          # in T2.1 (#634); this placeholder keeps the output present and
          # buildable so downstream wiring (#632) can reference it early.
          devcontainerImage = pkgs.runCommand "devcontainer-image-stub" { } ''
            mkdir -p "$out"
            cat > "$out/README" <<'EOF'
            devcontainerImage is a placeholder stub.

            The real Nix-built devcontainer image is delivered in T2.1 (#634).
            The toolchain it will bake is the `devTools` list in flake.nix
            (this repo's SSoT), shared with the dev-shell.
            EOF
          '';
        };
      }
    )
    // {
      # System-independent reusable outputs.
      lib = { inherit mkProjectShell devTools; };
      overlays.default = overlay;
    };
}
