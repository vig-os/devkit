{
  description = "vigOS devcontainer – toolchain SSoT (dev-shell + image basis)";

  inputs = {
    # Pinned stable channel: the controlled version document (flake.lock).
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-26.05";
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
      # The stable channel (nixos-26.05) lags on tools that ship frequently and
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
        pkgs: with pkgs; [
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
          nixfmt-rfc-style # nix file formatter (flake `formatter`, pre-commit hook)

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
        map (drv: drv.meta.mainProgram or drv.pname or (builtins.parseDrvName drv.name).name) (
          devTools pkgs
        );

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
      # uv's Python-download metadata, pinned to the uv release we provision.
      #
      # The nixpkgs build of uv ships with its embedded Python-download list
      # stripped (Nix is expected to supply interpreters), so `uv sync` cannot
      # fetch a managed CPython on its own — it reports "No interpreter found
      # ... in managed installations or search path". The dev-shell carries no
      # Python on PATH (the project venv is uv-managed), so uv must fetch a
      # CPython matching `requires-python` (>=3.14,<3.15). Pointing uv at
      # upstream's download-metadata.json (pinned to the provisioned uv version)
      # restores that capability without un-pinning nixpkgs. The IMAGE does not
      # use this: it bakes the interpreter (pythonEnv) + the toolchain from
      # nixpkgs and sets UV_PYTHON_DOWNLOADS=never. Refs #632, #666.
      uvPythonDownloadsJsonUrl = "https://raw.githubusercontent.com/astral-sh/uv/0.11.23/crates/uv-python/download-metadata.json";

      mkProjectShell =
        {
          pkgs,
          extraPackages ? [ ],
          shellHook ? ''echo "devcontainer dev environment loaded (nix)"'',
        }:
        pkgs.mkShell {
          packages = (devTools pkgs) ++ extraPackages;
          inherit shellHook;

          # Let the nixpkgs uv resolve managed Python downloads (see note above).
          UV_PYTHON_DOWNLOADS_JSON_URL = uvPythonDownloadsJsonUrl;
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

        python = pkgs.python314;

        # vig-utils packaged for the image (T2.4, #666): a pure-Python hatchling
        # package (single runtime dep `rich`) built by Nix, so `import vig_utils`
        # and its console scripts (check-expirations, vulnix-gate, …) are present
        # without a network-populated uv venv (impossible in a hermetic build).
        vigUtils = python.pkgs.buildPythonPackage {
          pname = "vig-utils";
          version = "0.1.0";
          pyproject = true;
          src = ./packages/vig-utils;
          build-system = [ python.pkgs.hatchling ];
          dependencies = [ python.pkgs.rich ];
          pythonImportsCheck = [ "vig_utils" ];
          # The package's own tests need pytest + the repo; CI covers them.
          doCheck = false;
        };

        # pip-licenses is not packaged in nixpkgs, so install it from its PyPI
        # wheel (pinned to the project's locked version + hash). Using the wheel
        # avoids its setuptools-scm/setuptools>=82 build backend; its only runtime
        # dep, prettytable, is in nixpkgs. Refs #666.
        pipLicenses = python.pkgs.buildPythonPackage {
          pname = "pip-licenses";
          version = "5.5.5";
          format = "wheel";
          src = pkgs.fetchurl {
            url = "https://files.pythonhosted.org/packages/2a/9a/6acfdb8d463eac7cdae7534d35d72237eca63f5fbafe797289d8a5fae447/pip_licenses-5.5.5-py3-none-any.whl";
            sha256 = "f4c4c6d9e6a03612cf59f29f19dc8ab54904d82e055b8e191498f2279a224e14";
          };
          dependencies = [ python.pkgs.prettytable ];
          pythonImportsCheck = [ "piplicenses" ];
        };

        # The image's Python interpreter, with the project's Python tools
        # (vig-utils + pip-licenses) and their console scripts on PATH. Replaces
        # the bare interpreter in imageTools.
        pythonEnv = python.withPackages (_ps: [
          vigUtils
          pipLicenses
        ]);

        # The toolchain SSoT plus the runtime substrate a bare layered image
        # lacks (an FHS base distro would provide these; here we add them
        # explicitly — this is the discovery surface for FHS gaps). Shared by
        # the image (`devcontainerImage`) and its vulnix scan target
        # (`devcontainerImageEnv`, #637).
        imageTools =
          (devTools pkgs)
          ++ (with pkgs; [
            # Nix package manager in the closure (CppNix).
            nix
            direnv
            nix-direnv

            # Locale support without locale-gen.
            glibcLocales

            # Python (with vig-utils baked) + the project Python toolchain.
            # The Debian image installed these via `uv pip install` at build;
            # the hermetic Nix build takes them from nixpkgs instead (#666).
            pythonEnv
            pre-commit
            ruff
            bandit

            # Rust/cargo + just LSP/formatter tools. The Debian image installed
            # these via cargo-binstall; Nix-native from nixpkgs here (#666).
            cargo-binstall
            just-lsp
            typstyle

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
      in
      {
        devShells.default = mkProjectShell { inherit pkgs; };

        # Binary names of every tool in devTools — read by the parity test.
        devShellTools = devShellToolNames pkgs;

        # ------------------------------------------------------------------
        # formatter — `nix fmt` formats every *.nix file with nixfmt-rfc-style.
        #
        # Same package as the `nixfmt` pre-commit hook (sourced from devTools)
        # so editor `nix fmt`, the hook, and the `checks.format` gate below all
        # agree on one formatting. Refs #674.
        # ------------------------------------------------------------------
        formatter = pkgs.nixfmt-rfc-style;

        # ------------------------------------------------------------------
        # checks — lightweight flake quality gates run by `nix flake check`.
        #
        # Kept deliberately lightweight. The richer dev-shell/image parity test
        # (tests/test_flake_devshell.py) is NOT wrapped as a flake check: nix
        # checks build in a sandbox with no recursive nix access, so a check
        # that itself runs `nix eval`/`nix develop` cannot work here. That test
        # therefore stays in CI as a pytest (the project-checks job), and the
        # flake checks cover what a sandbox can: the flake formats cleanly, the
        # dev-shell builds, and devShellTools evaluates. Refs #674.
        checks = {
          # Every *.nix file is nixfmt-clean (the `nix fmt` idempotency gate).
          format = pkgs.runCommand "nixfmt-check" { nativeBuildInputs = [ pkgs.nixfmt-rfc-style ]; } ''
            nixfmt --check ${./flake.nix}
            touch "$out"
          '';

          # The dev-shell evaluates and its closure builds.
          devShell = self.devShells.${system}.default;

          # devShellTools (the parity-test SSoT) evaluates to a non-empty list.
          devShellTools = pkgs.runCommand "devshell-tools-eval" { } ''
            count=${toString (builtins.length (devShellToolNames pkgs))}
            test "$count" -gt 0
            touch "$out"
          '';
        };

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

                    # Bake the devcontainer version into the scaffolded `.vig-os`,
                    # replacing the {{IMAGE_TAG}} placeholder. The Debian build
                    # relied on the IMAGE_TAG build-arg; the reproducible Nix image
                    # reads the repo's pinned DEVCONTAINER_VERSION, so a scaffolded
                    # workspace pins the devcontainer release it was built from. #642.
                    dcver="$(sed -n 's/^DEVCONTAINER_VERSION=//p' ${./.vig-os})"
                    sed -i "s/{{IMAGE_TAG}}/$dcver/g" "$out/root/assets/workspace/.vig-os"

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
                  "org.opencontainers.image.source" = "https://github.com/vig-os/devcontainer";
                  "org.opencontainers.image.licenses" = "MIT";
                };
              };
            };

          # devcontainerImageEnv — vulnix scan target (T3.1, #637). A buildEnv
          # whose runtime closure equals the image's package set (imageTools),
          # so `vulnix --closure` sees exactly what ships in the image. The OCI
          # tarball itself is gzipped and exposes no scannable store references,
          # hence this dedicated env rather than scanning the image output.
          devcontainerImageEnv = pkgs.buildEnv {
            name = "devcontainer-image-env";
            paths = imageTools;
            ignoreCollisions = true;
          };

          # vulnix — pinned CVE scanner (#637) from the locked nixpkgs so the
          # nightly scan is reproducible rather than tracking a rolling channel.
          vulnix = pkgs.vulnix;
        };
      }
    )
    // {
      # System-independent reusable outputs.
      lib = { inherit mkProjectShell devTools; };
      overlays.default = overlay;
    };
}
