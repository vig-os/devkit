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
          # -----------------------------------------------------------------
          # devcontainerImage — Nix-built devcontainer image (T2.1, #634).
          #
          # Assembled entirely by Nix via `dockerTools.buildLayeredImage` (NOT
          # a Dockerfile `FROM`) so the build is bit-reproducible — the epic's
          # "identical image digest on rebuild" criterion can hold. The Nix
          # package manager (CppNix, `pkgs.nix`) is part of the closure so
          # `nix`/`direnv` are live inside the container, identical to the
          # direnv path; `nix2container` stays reserved for production images.
          #
          # Evaluator decision (#634): ship upstream CppNix (`pkgs.nix`) as the
          # in-container evaluator. It is the channel default, needs no overlay,
          # and the flake is installer-agnostic, so swapping to `pkgs.lix` later
          # is a one-line change. `pkgs.lix` is left out for now to keep the
          # closure smaller.
          #
          # pre-commit vs prek (#40): this image bakes upstream `pre-commit`
          # (matches the Debian build and the pinned pyproject version).
          # Migrating the cache layer to `prek` is deferred to #40; both are in
          # nixpkgs, so it is a drop-in swap once that issue lands.
          devcontainerImage =
            let
              python = pkgs.python314;

              # The toolchain SSoT plus the runtime substrate a bare layered
              # image lacks (an FHS base distro would provide these; here we add
              # them explicitly — this is the discovery surface for FHS gaps).
              imageTools =
                (devTools pkgs)
                ++ (with pkgs; [
                  # Nix package manager in the closure (CppNix).
                  nix
                  direnv
                  nix-direnv

                  # Locale support without locale-gen.
                  glibcLocales

                  # Python + uv-managed venv bootstrap.
                  python
                  pre-commit

                  # Base runtime substrate (no FHS base distro to inherit).
                  bashInteractive
                  coreutils-full
                  findutils
                  gnugrep
                  gnused
                  gawk
                  gnutar
                  gzip
                  which
                  cacert
                  curl
                  openssh
                  nano
                  rsync

                  # /etc/passwd + /etc/group with a root (uid 0) entry. A bare
                  # layered image has no FHS user database, so anything that
                  # resolves the current uid (ssh, tmux, git) fails with
                  # "No user exists for uid 0". fakeNss provides the minimal
                  # nss files an FHS base distro would have supplied.
                  dockerTools.fakeNss
                ]);

              # Bake the workspace assets, pre-commit cache dir and template
              # .venv scaffold as a normal image layer. UV_PYTHON pins the Nix
              # interpreter and UV_PYTHON_DOWNLOADS=never forbids uv from
              # fetching a managed CPython (absent in the sandbox anyway). The
              # venv/pre-commit population needs network, so it is best-effort
              # here and the directories are created unconditionally.
              bootstrap =
                pkgs.runCommand "devcontainer-bootstrap"
                  {
                    nativeBuildInputs = [
                      pkgs.coreutils
                      pkgs.findutils
                    ];
                  }
                  ''
                    mkdir -p "$out/root/assets"
                    cp -r ${./assets}/. "$out/root/assets/"
                    chmod -R u+w "$out/root/assets"
                    find "$out/root/assets" -type f -name "*.sh" -exec chmod +x {} \;

                    # /root/.bashrc with carried aliases: precommit (Debian
                    # build) plus cc/cld (#545).
                    cat > "$out/root/.bashrc" <<'BASHRC'
                    alias precommit="pre-commit run"
                    alias cc="claude"
                    alias cld="claude --dangerously-skip-permissions"
                    BASHRC

                    mkdir -p "$out/opt/pre-commit-cache"
                    mkdir -p "$out/workspace"

                    # /tmp with the sticky bit. A bare layered image has no
                    # /tmp; tools that need a scratch/socket dir (tmux, uv,
                    # pytest) fail without it ("no suitable socket path"). An
                    # FHS base distro would have supplied it.
                    mkdir -p "$out/tmp"
                    chmod 1777 "$out/tmp"
                  '';
            in
            pkgs.dockerTools.buildLayeredImage {
              # Name matches the published repo so the portable testinfra
              # (#635), which targets ghcr.io/vig-os/devcontainer:<tag>, runs
              # unchanged against the loaded image under a unique tag.
              name = "ghcr.io/vig-os/devcontainer";
              tag = "nix-wt634";

              contents = imageTools ++ [ bootstrap ];

              # Deterministic epoch timestamp keeps the digest reproducible.
              created = "1970-01-01T00:00:00Z";

              config = {
                Cmd = [ "${pkgs.bashInteractive}/bin/bash" ];
                WorkingDir = "/workspace";
                Env = [
                  "LANG=en_US.UTF-8"
                  "LANGUAGE=en_US:en"
                  "LC_ALL=en_US.UTF-8"
                  "LOCALE_ARCHIVE=${pkgs.glibcLocales}/lib/locale/locale-archive"
                  "PYTHONUNBUFFERED=1"
                  "IN_CONTAINER=true"
                  # #545: the container is the trust boundary; bypass the uid-0
                  # check for `claude --dangerously-skip-permissions`.
                  "IS_SANDBOX=1"
                  "PRE_COMMIT_HOME=/opt/pre-commit-cache"
                  "UV_PROJECT_ENVIRONMENT=/root/assets/workspace/.venv"
                  "VIRTUAL_ENV=/root/assets/workspace/.venv"
                  "UV_PYTHON_DOWNLOADS=never"
                  "UV_PYTHON=${python}/bin/python3.14"
                  "SSL_CERT_FILE=${pkgs.cacert}/etc/ssl/certs/ca-bundle.crt"
                  "NIX_SSL_CERT_FILE=${pkgs.cacert}/etc/ssl/certs/ca-bundle.crt"
                  "HOME=/root"
                ];
                Labels = {
                  "org.opencontainers.image.title" = "vigOS development environment";
                  "org.opencontainers.image.source" =
                    "https://github.com/vig-os/devcontainer";
                  "org.opencontainers.image.licenses" = "MIT";
                };
              };
            };
        };
      }
    )
    // {
      # System-independent reusable outputs.
      lib = { inherit mkProjectShell devTools; };
      overlays.default = overlay;
    };
}
