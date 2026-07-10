{
  description = "vigOS devcontainer – toolchain SSoT (dev-shell + image basis)";

  inputs = {
    # Pinned stable channel: the controlled version document (flake.lock).
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-26.05";
    # Secondary channel, overlaid only for fast-moving tools (uv, gh, claude).
    nixpkgs-unstable.url = "github:NixOS/nixpkgs/nixpkgs-unstable";
    flake-utils.url = "github:numtide/flake-utils";
    # treefmt-nix: one multi-language `nix fmt` entrypoint + a formatting check,
    # unifying the per-language formatters (nixfmt, ruff, taplo) the pre-commit
    # hooks already run. Follows the pinned nixpkgs for reproducibility. Refs #777.
    treefmt-nix.url = "github:numtide/treefmt-nix";
    treefmt-nix.inputs.nixpkgs.follows = "nixpkgs";
    # git-hooks.nix: the Nix SSoT for the pre-commit hooks. Its `run` builds a
    # sandbox-pure `checks.pre-commit`, driven by the `prek` runner (Rust, faster
    # than the Python `pre-commit`). Follows the pinned nixpkgs so the hook
    # toolchain matches the dev-shell/image. Refs #778 (supersedes #40).
    git-hooks-nix.url = "github:cachix/git-hooks.nix";
    git-hooks-nix.inputs.nixpkgs.follows = "nixpkgs";
    # process-compose-flake + services-flake: daemonless local dev services
    # (ADR-nix-devenv-strategy, axis 3). Both are dependency-free flakes (no
    # inputs of their own), so there is nothing to `follows` and the lock gains
    # exactly two leaf entries. Consumed by mkProjectServices. Refs #795.
    process-compose-flake.url = "github:Platonic-Systems/process-compose-flake";
    services-flake.url = "github:juspay/services-flake";
    # home-manager powers the vigos.* home environment — the ONLY input the
    # module product adds (ADR-home-environment-modules axis 3). The release
    # branch matches the nixos-26.05 pin; follows keeps one resolved nixpkgs.
    # Refs #819.
    home-manager.url = "github:nix-community/home-manager/release-26.05";
    home-manager.inputs.nixpkgs.follows = "nixpkgs";
  };

  outputs =
    {
      self,
      nixpkgs,
      nixpkgs-unstable,
      flake-utils,
      treefmt-nix,
      git-hooks-nix,
      process-compose-flake,
      services-flake,
      home-manager,
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

      # bats + helper libraries as one wrapped package. The wrapper exports a
      # BATS_LIB_PATH covering bats-support/-assert/-file so `bats_load_library`
      # (tests/bats/test_helper.bash) resolves them from the Nix store — the
      # flake SSoT — replacing the npm (node_modules) / Debian (/usr/lib)
      # resolution that does not exist on the Nix toolchain. Refs #695.
      batsWithLibs = import ./nix/bats.nix;

      # Import nixpkgs-unstable for a given system (allowUnfree covers
      # claude-code). Evaluated once per system in the per-system `let` below and
      # threaded into the overlay, rather than re-imported inside the overlay
      # fixpoint on each application. Refs #774.
      importUnstable =
        system:
        import nixpkgs-unstable {
          inherit system;
          config.allowUnfree = true;
        };

      # Build the fast-mover overlay from an already-imported `unstable` pkgs set,
      # so the unstable import is hoisted out of the overlay closure (see
      # importUnstable above).
      mkFastMoverOverlay =
        unstable: _final: _prev:
        builtins.listToAttrs (
          map (name: {
            inherit name;
            value = unstable.${name};
          }) fastMovers
        );

      # System-independent overlay for downstream consumers (overlays.default).
      # No concrete system is known here, so it imports unstable inside the
      # fixpoint; the in-flake path below uses the hoisted importUnstable.
      overlay = final: prev: mkFastMoverOverlay (importUnstable final.system) final prev;

      # ---------------------------------------------------------------------
      # vigos home environment (#819): self-pkgs + the ci homeConfigurations.
      # ---------------------------------------------------------------------
      # pkgs for the flake's own homeConfigurations (self-pkgs): the same
      # stable base + fast-mover overlay + allowUnfree combination as the
      # per-system dev-shell pkgs, so claude-code and friends resolve to the
      # very same versions across dev-shell, image, and home modules.
      mkHomePkgs =
        system:
        import nixpkgs {
          inherit system;
          overlays = [ (mkFastMoverOverlay (importUnstable system)) ];
          config.allowUnfree = true;
        };

      # Every system the home modules target. x86_64-darwin evaluates but is
      # never built in CI (best-effort tier, ADR platform table).
      hmSystems = [
        "x86_64-linux"
        "aarch64-linux"
        "aarch64-darwin"
        "x86_64-darwin"
      ];

      # The two CI profiles: minimal exercises one module, full exercises the
      # whole option surface. Kept in lockstep with nix/home/.
      hmProfiles = {
        minimal = {
          vigos.shell.enable = true;
        };
        full = {
          vigos = {
            packages.enable = true;
            claude.enable = true;
            sesh.enable = true;
            ghdash.enable = true;
            editor.enable = true;
            shell.enable = true;
            multiplexer.enable = true;
            cli.enable = true;
            direnv.enable = true;
            git.enable = true;
          };
        };
      };

      # ci-<profile>-<system> homeConfigurations: synthetic user, pinned
      # stateVersion — schema-asserted by tests/test_flake_checks.py.
      ciHomeConfigurations = nixpkgs.lib.listToAttrs (
        nixpkgs.lib.concatMap (
          system:
          map (profile: {
            name = "ci-${profile}-${system}";
            value = home-manager.lib.homeManagerConfiguration {
              pkgs = mkHomePkgs system;
              modules = [
                ./nix/home/default.nix
                {
                  home = {
                    username = "ci";
                    homeDirectory = if nixpkgs.lib.hasSuffix "-darwin" system then "/Users/ci" else "/home/ci";
                    stateVersion = "26.05";
                  };
                }
                hmProfiles.${profile}
              ];
            };
          }) (builtins.attrNames hmProfiles)
        ) hmSystems
      );

      # ---------------------------------------------------------------------
      # devTools — the single source of truth for the toolchain.
      #
      # This list is the shared basis for the dev-shell now and the image later
      # (#634). Adding a tool here adds it everywhere; the per-tool parity test
      # (tests/test_flake_devshell.py) reads `devShellTools` so it can never
      # drift from this list.
      # ---------------------------------------------------------------------
      devTools = import ./nix/devtools.nix;

      # Capability-module registry (#884): name -> (pkgs -> { packages, env,
      # shellHook }). Consumed by mkProjectShell's `modules` argument and by
      # the generated per-module `checks.<system>.module-<name>` below. See
      # docs/rfcs/ADR-capability-modules.md for the v1 contract.
      capabilityModules = import ./nix/modules/default.nix;

      # One definition of the pre-commit hook set (#883): nix/hooks.nix
      # renders the sandbox-pure `checks.pre-commit` gate, the PATH-portable
      # committed `.pre-commit-config.yaml` + scaffold copy (drift-gated by
      # tests/test_flake_hooks.py via `lib.hooksPortable`), and the consumer
      # generation surface (mkProjectShell's `hooks`/`hooksExcludes`).
      hooksModule = import ./nix/hooks.nix { inherit (nixpkgs) lib; };

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
      #     modules = [ "native" ];           # opt-in capability modules (#884)
      #     extraPackages = [ pkgs.foo ];
      #     hooks = { pymarkdown.enable = false; };  # opt-in generated hooks (#883)
      #   };
      mkProjectShell =
        {
          pkgs,
          modules ? [ ],
          extraPackages ? [ ],
          hooks ? null,
          hooksExcludes ? [ ],
          shellHook ? ''echo "devcontainer dev environment loaded (nix)"'',
        }:
        let
          # ------------------------------------------------------------------
          # Capability modules (#884) — resolve the requested names against the
          # nix/modules/ registry and fold their contributions (v1 contract:
          # packages + env + shellHook fragments only; composition rules in
          # docs/rfcs/ADR-capability-modules.md). With `modules = [ ]` every
          # merge below is the identity — empty list, empty attrset, empty
          # string — so the zero-module shell stays byte-identical to the
          # pre-#884 builder (parity: tests/test_flake_devshell.py). Kept as
          # one self-contained block so #883's `hooks` argument can land
          # beside it without conflict.
          # ------------------------------------------------------------------
          moduleDefs = map (
            name:
            (capabilityModules.${name} or (throw (
              "mkProjectShell: unknown capability module '${name}'; available: "
              + pkgs.lib.concatStringsSep ", " (builtins.attrNames capabilityModules)
            ))
            )
              pkgs
          ) modules;
          # Appended AFTER extraPackages: earlier entries win PATH lookup, so
          # the per-repo escape hatch overrides a module's tool choice.
          modulePackages = pkgs.lib.concatMap (m: m.packages or [ ]) moduleDefs;
          # Left-to-right merge (later module wins); the builder's own env
          # pins (UV_PYTHON, UV_PYTHON_DOWNLOADS, …) always win — see the
          # mkShell attrset merge below.
          moduleEnv = pkgs.lib.foldl' (acc: m: acc // (m.env or { })) { } moduleDefs;
          # Newline-terminated fragments, before the consumer shellHook (the
          # consumer keeps the last word).
          moduleShellHook = pkgs.lib.concatMapStrings (
            m: pkgs.lib.optionalString ((m.shellHook or "") != "") ((m.shellHook or "") + "\n")
          ) moduleDefs;

          # ------------------------------------------------------------------
          # Flake-generated pre-commit config (#883) — OPT-IN. Passing `hooks`
          # (an attrset, even empty) or `hooksExcludes` composes the shared
          # base hook set (nix/hooks.nix consumer profile) with the consumer's
          # per-hook overrides / custom hooks / global excludes via
          # git-hooks.nix. Only the RENDERED CONFIG is consumed: entering the
          # shell installs `.pre-commit-config.yaml` (a symlink to the store —
          # gitignore it) via the builder's own snippet below, NOT
          # git-hooks.nix's installation script (install.enable = false).
          # That stock script would unset/reset `core.hooksPath` and install
          # only the pre-commit stage into `.git/hooks`, silently bypassing
          # the scaffold's `.githooks` entry point (sanctioned-environment
          # guard, consumer-owned scripts) — PR #908 review. The snippet
          # keeps git-hooks.nix's refusal semantics: a regular (non-symlink)
          # `.pre-commit-config.yaml` (#878) is never overwritten — the
          # consumer deletes it to complete the opt-in (docs/MIGRATION.md).
          # `.githooks/pre-commit` runs `prek run`, which reads the repo-root
          # config, so the generated hooks execute through the existing wiring.
          # With the default `hooks = null` every fragment below is empty and
          # the shell stays byte-identical to the no-hooks builder (parity:
          # tests/test_flake_devshell.py, tests/test_flake_hooks.py).
          # ------------------------------------------------------------------
          hooksEnabled = hooks != null || hooksExcludes != [ ];
          consumerHooksBase = hooksModule.consumer pkgs;
          # Base values at priority 999: they beat git-hooks.nix's own
          # built-in hook defaults (mkDefault, 1000 — equal priorities would
          # conflict, e.g. the built-in nixfmt entry vs the base one) and
          # lose to any consumer fragment (plain assignment, 100), so e.g.
          # `typos.enable = false` wins while untouched fields keep their
          # base value (module-system merge).
          consumerHooksDefaults = pkgs.lib.mapAttrs (
            _: hook: pkgs.lib.mapAttrs (_: pkgs.lib.mkOverride 999) hook
          ) consumerHooksBase.hooks;
          hooksRun = git-hooks-nix.lib.${pkgs.stdenv.hostPlatform.system}.run {
            # Only the rendered config + installation script are consumed; the
            # sandbox check derivation (which would need the project tree) is
            # never built, so a placeholder src suffices.
            src = pkgs.emptyDirectory;
            package = pkgs.prek;
            imports = [
              {
                config = {
                  hooks = consumerHooksDefaults;
                  excludes = consumerHooksBase.excludes ++ hooksExcludes;
                  # Never let git-hooks.nix install into `.git/hooks` or rewire
                  # `core.hooksPath` — the config-only snippet below owns the
                  # shellHook and `.githooks` stays the entry point (#908).
                  install.enable = false;
                };
              }
              { config.hooks = if hooks == null then { } else hooks; }
            ];
          };
          # Config-only installation snippet (replaces hooksRun.shellHook):
          # maintain the `.pre-commit-config.yaml` -> store symlink exactly
          # like git-hooks.nix's installationScript — staleness check, refusal
          # on a regular file (#878), GC root when nix-store is available —
          # minus every `.git/hooks` / `core.hooksPath` mutation (#908).
          hooksConfigFile = hooksRun.config.configFile;
          hooksConfigInstall = ''
            if ! ${pkgs.gitMinimal}/bin/git rev-parse --git-dir &> /dev/null; then
              echo 1>&2 "WARNING: vigos hooks: .git not found; skipping generated pre-commit config installation."
            else
              GIT_WC=$(${pkgs.gitMinimal}/bin/git rev-parse --show-toplevel)
              if ! readlink "$GIT_WC/.pre-commit-config.yaml" >/dev/null \
                || [[ $(readlink "$GIT_WC/.pre-commit-config.yaml") != ${hooksConfigFile} ]]; then
                if [ -e "$GIT_WC/.pre-commit-config.yaml" ] && [ ! -L "$GIT_WC/.pre-commit-config.yaml" ]; then
                  echo 1>&2 "vigos hooks: WARNING: Refusing to install the generated config over an existing .pre-commit-config.yaml"
                  echo 1>&2 ""
                  echo 1>&2 "  To complete the flake-generated hooks opt-in (docs/MIGRATION.md):"
                  echo 1>&2 "    1. Port your customizations into mkProjectShell's hooks/hooksExcludes."
                  echo 1>&2 "    2. Remove .pre-commit-config.yaml"
                  echo 1>&2 "    3. Add .pre-commit-config.yaml to .gitignore"
                else
                  echo 1>&2 "vigos hooks: installing generated .pre-commit-config.yaml"
                  [ -L "$GIT_WC/.pre-commit-config.yaml" ] && unlink "$GIT_WC/.pre-commit-config.yaml"
                  if command -v nix-store >/dev/null 2>&1; then
                    nix-store --add-root "$GIT_WC/.pre-commit-config.yaml" --indirect --realise ${hooksConfigFile} >/dev/null
                  else
                    ln -fs ${hooksConfigFile} "$GIT_WC/.pre-commit-config.yaml"
                  fi
                fi
              fi
            fi
          '';
          hooksShellHook = pkgs.lib.optionalString hooksEnabled (hooksConfigInstall + "\n");

          # uv's Python-download metadata, pinned to the uv release we provision.
          # The nixpkgs build of uv ships with its embedded Python-download list
          # stripped, so it cannot fetch a managed CPython on its own. CI
          # provisions FROM this dev-shell on an FHS runner and forwards this URL
          # (see the setup-env action) so the runner's uv can download a managed
          # CPython for `uv sync` / pre-commit — a Nix-store interpreter cannot
          # load pre-commit's manylinux-wheel C extensions outside `nix develop`.
          # Derived from `pkgs.uv.version` so it tracks the overlaid (floating)
          # uv and cannot drift from a literal pin. Refs #632, #666, #683, #774.
          uvPythonDownloadsJsonUrl = "https://raw.githubusercontent.com/astral-sh/uv/${pkgs.uv.version}/crates/uv-python/download-metadata.json";

          # CPython matching `requires-python` (>=3.14,<3.15). The dev-shell
          # carries no Python on PATH (the project venv is uv-managed). Pin a
          # Nix store CPython via UV_PYTHON and forbid downloads
          # (UV_PYTHON_DOWNLOADS=never): the nixpkgs uv would otherwise fetch a
          # generic, dynamically-linked managed CPython a NixOS host cannot
          # execute out of the box (no FHS ld-linux), so `uv sync` (`just init`)
          # aborted there (#683). A store interpreter is patched to the store
          # loader and runs in the dev-shell on both NixOS and FHS hosts. The
          # IMAGE path sets the same two vars (baking pythonEnv). Refs #666, #683.
          python = pkgs.python314;

          # The C++ runtime (libstdc++.so.6). The `pymarkdown` pre-commit hook
          # runs from pre-commit's OWN manylinux-wheel Python env (not the project
          # venv), whose dependency `pyjson5` is a C extension linked against
          # `libstdc++.so.6`. On a NixOS host that library is not on the loader
          # path outside an FHS environment, so the hook aborts with
          # `ImportError: libstdc++.so.6: cannot open shared object file`. Exposing
          # the Nix C++ runtime on LD_LIBRARY_PATH lets the wheel resolve it; it is
          # the same libstdc++ the Nix toolchain itself links (`stdenv.cc.cc.lib`).
          # pymarkdown is not in nixpkgs, so the #697 "add to devTools +
          # language:system" recipe does not apply here. Refs #698.
          ldLibraryPath = "${pkgs.stdenv.cc.cc.lib}/lib";

          # Inject it ONLY on NixOS, where it is both required (above) and ABI-safe
          # (the system glibc IS the Nix glibc). On an FHS host the system
          # libstdc++ already resolves the wheel, and exporting the Nix one — built
          # against a newer glibc — leaks into host binaries (every `just` recipe's
          # `#!/usr/bin/env bash`, plus anything an `/etc/ld.so.preload` agent pulls
          # `libstdc++` into), dragging in the Nix `libm.so.6` and aborting them with
          # `version 'GLIBC_ABI_DT_X86_64_PLT' not found`. `/etc/NIXOS` marks NixOS.
          # mkShell may itself inject an LD_LIBRARY_PATH from propagated libs;
          # APPEND rather than clobber so that value (and any host-set one) survives.
          # Refs #703.
          ldLibraryPathHook = ''
            if [ -e /etc/NIXOS ]; then
              export LD_LIBRARY_PATH="''${LD_LIBRARY_PATH:+$LD_LIBRARY_PATH:}${ldLibraryPath}"
            fi
          '';

          # The dev-shell's `neovim` must not inherit the user's personal
          # `~/.config/nvim`. nixvim (and other launchers like a LazyVim
          # lockfile) emit a config at the standard XDG path that assumes a
          # specific wrapper — e.g. nixvim's `init.lua` only finds its plugins
          # when launched by its wrapper's `--cmd "set packpath^=…"`. A bare
          # `nvim` auto-sources that config but lacks the packpath, so it crashes
          # on startup (`module 'catppuccin' not found`). NVIM_APPNAME redirects
          # config/data/state lookups to `~/.config/vigos-dev` (which does not
          # exist), so the shell's nvim starts vanilla and isolated. Refs #723.
          nvimIsolationHook = ''
            export NVIM_APPNAME="vigos-dev"
          '';
        in
        pkgs.mkShell (
          # Module env first: the builder's attrset below wins any collision,
          # so a capability module can never break the Python bootstrap pins
          # (UV_PYTHON, UV_PYTHON_DOWNLOADS, …). Refs #884.
          moduleEnv
          // {
            # The toolchain SSoT, plus a bare Python interpreter so the downstream
            # dev-shell matches the image's PATH (`python`/`python3`). The bare
            # interpreter is not in `devTools`: the image already provides it via
            # `pythonEnv` in `imageTools`, and a bare interpreter in the SSoT would
            # collide with `pythonEnv` there. The hook runner (`prek`) lives in
            # `devTools`, so it reaches both the dev-shell and the image from one
            # place — the former standalone `pre-commit` here is dropped (#778).
            # Safe for CI despite the FHS pymarkdown/manylinux constraint: the
            # dev-shell pins `UV_PYTHON` (below) to this same store CPython, and
            # the CI PATH-forwarding (setup-env) filters this interpreter out so
            # `uv` still builds the runner venv from a downloaded managed CPython.
            # No new LD_LIBRARY_PATH, so the #703 FHS leak-guard is unaffected.
            # Refs #729, #778.
            packages =
              (devTools pkgs)
              ++ [
                python
              ]
              ++ extraPackages
              ++ modulePackages;
            shellHook =
              ldLibraryPathHook + "\n" + nvimIsolationHook + "\n" + moduleShellHook + hooksShellHook + shellHook;

            UV_PYTHON = "${python}/bin/python3.14";
            UV_PYTHON_DOWNLOADS = "never";

            # Resolve the bats helper libraries from the Nix store. The wrapper
            # also sets this when `bats` runs, but exporting it in the dev-shell
            # makes the path visible (and works for a bare `bats` too). Refs #695.
            BATS_LIB_PATH = "${batsWithLibs pkgs}/share/bats";

            # For CI only: the pin above means downloads never happen in the
            # dev-shell, but CI forwards this URL (NOT UV_PYTHON) so its FHS runner
            # downloads a managed CPython for pre-commit's manylinux-wheel hooks,
            # which a Nix-store interpreter cannot load there. Refs #632, #683.
            UV_PYTHON_DOWNLOADS_JSON_URL = uvPythonDownloadsJsonUrl;
          }
          # Expose the rendered hook config for tests/tooling ONLY when the
          # consumer opted in, so the zero-hooks derivation is untouched.
          # passthru is not part of the derivation environment. Refs #883.
          // pkgs.lib.optionalAttrs hooksEnabled {
            passthru = {
              inherit hooksConfigFile;
            };
          }
        );

      # ---------------------------------------------------------------------
      # mkProjectServices — reusable local dev-services builder (#795).
      #
      # Boots declared services (Postgres, SeaweedFS, Redis, …) as native processes via
      # process-compose + services-flake — no Docker/Podman daemon — with the
      # service versions coming from the caller's `pkgs` (the pinned nixpkgs
      # lock, never out-of-lock image tags). services-flake is consumed through
      # process-compose-flake's standalone `evalModules` (its documented
      # no-flake-parts path), so this flake stays on flake-utils; see
      # docs/NIX.md for the recorded decision. Consumers need NO extra flake
      # inputs — both service flakes resolve from THIS flake's lock:
      #   packages.services = inputs.devcontainer.lib.mkProjectServices {
      #     inherit pkgs;
      #     modules = [ { services.postgres."db".enable = true; } ];
      #   };
      # Run with `nix run .#services` (add `--tui=false` for headless); state
      # lands under ./data in the invocation cwd — gitignore it.
      mkProjectServices =
        {
          pkgs,
          modules ? [ ],
          name ? "services",
        }:
        ((import process-compose-flake.lib { inherit pkgs; }).evalModules {
          inherit name;
          modules = [ services-flake.processComposeModules.default ] ++ modules;
        }).config.outputs.package;
    in
    flake-utils.lib.eachDefaultSystem (
      system:
      let
        # Imported once per system and reused by the overlay below.
        unstable = importUnstable system;
        pkgs = import nixpkgs {
          inherit system;
          overlays = [ (mkFastMoverOverlay unstable) ];
          config.allowUnfree = true;
        };

        # treefmt-nix: one `nix fmt` entrypoint + a `checks.formatting` gate over
        # the whole repo. The enabled programs mirror the pre-commit formatters —
        # nixfmt-rfc-style (same package as devTools/the hook), ruff-format, and
        # taplo — so the editor `nix fmt`, the hooks, and the flake check all
        # agree on one formatting. Refs #777.
        treefmtEval = treefmt-nix.lib.evalModule pkgs {
          projectRootFile = "flake.nix";
          programs = {
            nixfmt = {
              enable = true;
              package = pkgs.nixfmt-rfc-style;
            };
            ruff-format.enable = true;
            taplo.enable = true;
          };
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

        # ------------------------------------------------------------------
        # preCommitCheck — the sandbox-pure profile of the ONE hook-set
        # definition (nix/hooks.nix, #883), run by the `prek` runner as
        # `checks.pre-commit` under `nix flake check`. Refs #778 (supersedes #40).
        #
        # `checks.pre-commit` builds in the Nix sandbox: NO network, NO project
        # venv. nix/hooks.nix marks which hooks are pure under those
        # constraints (`check` fragments, wired here to the hermetic Nix
        # binaries: treefmtEval's wrapper, ${vigUtils}/bin/…, the 3.14
        # pre-commit-hooks build for debug-statements); the impure /
        # generator / stage-gated hooks stay RUNNER-ONLY in the committed
        # `.pre-commit-config.yaml`, which the SAME definition renders and
        # tests/test_flake_hooks.py drift-gates. See docs/NIX.md
        # ("One hook definition, three renders").
        preCommitCheck = git-hooks-nix.lib.${system}.run (
          {
            src = ./.;
            # Run the hooks with prek (Rust) instead of the Python pre-commit.
            package = pkgs.prek;
          }
          // hooksModule.checkArgs {
            inherit pkgs vigUtils python;
            treefmtWrapper = treefmtEval.config.build.wrapper;
          }
        );

        # The toolchain SSoT plus the runtime substrate a bare layered image
        # lacks (an FHS base distro would provide these; here we add them
        # explicitly — this is the discovery surface for FHS gaps). Shared by
        # the image (`devkitImage`) and its vulnix scan target
        # (`devkitImageEnv`, #637).
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
            # The git-hook runner is `prek` (via devTools); the standalone
            # Python `pre-commit` that used to sit here is dropped (#778).
            pythonEnv
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

            # /usr/bin/env -> coreutils env. A bare layered image has no
            # /usr/bin at all, so the ubiquitous `#!/usr/bin/env <interp>`
            # shebang fails with "/usr/bin/env: bad interpreter" — breaking
            # essentially every Node/Python/Ruby CLI (e.g.
            # node_modules/.bin/tsc) for image-mode consumers. usrBinEnv is
            # the minimal shim an FHS base distro would have supplied. #727.
            dockerTools.usrBinEnv
          ]);

        # servicesPoC — the #795 validating PoC: SeaweedFS (S3) + Postgres via
        # mkProjectServices, exposed as `nix run .#services`. The issue named
        # MinIO for the S3 half, but nixpkgs marks minio abandoned upstream
        # with unfixed CVEs (knownVulnerabilities) on both channels, so the
        # blessed PoC uses the maintained, S3-compatible SeaweedFS instead —
        # recorded in docs/NIX.md and on #795. Non-default ports so a CI
        # runner's own postgres (5432) or process-compose's API default (8080,
        # the seaweedfs volume default) cannot collide; postgres must opt into
        # TCP (listen_addresses defaults to "" = unix-socket-only). Booted
        # end-to-end — no container daemon — by tests/test_flake_services.py.
        servicesPoC = mkProjectServices {
          inherit pkgs;
          modules = [
            {
              services.postgres."pg" = {
                enable = true;
                listen_addresses = "127.0.0.1";
                port = 5433;
              };
              services.seaweedfs."s3" = {
                enable = true;
                volume.port = 8380;
                filer.enable = true;
                filer.port = 8388;
                s3.enable = true;
                s3.port = 8333;
              };
            }
          ];
        };
      in
      {
        devShells.default = mkProjectShell { inherit pkgs; };

        # Binary names of every tool in devTools — read by the parity test.
        devShellTools = devShellToolNames pkgs;

        # ------------------------------------------------------------------
        # formatter — `nix fmt` runs treefmt over every supported language
        # (nixfmt-rfc-style for *.nix, ruff-format for *.py, taplo for *.toml).
        #
        # treefmt wraps the same underlying formatters the pre-commit hooks use,
        # so editor `nix fmt`, the hooks, and the `checks.formatting` gate below
        # all agree on one formatting. Refs #674, #777.
        # ------------------------------------------------------------------
        formatter = treefmtEval.config.build.wrapper;

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
          # The tree is treefmt-clean (nixfmt + ruff-format + taplo). Supersedes
          # the former nixfmt-only `format` gate: treefmt covers every language
          # its enabled programs handle across the repo, not just *.nix, and is
          # the same wrapper `nix fmt` runs. Refs #674, #774, #777.
          formatting = treefmtEval.config.build.check self;

          # flake.nix carries no dead Nix code. Scoped to the authored flake (the
          # toolchain SSoT): the downstream scaffold (assets/workspace/flake.nix)
          # and the example (examples/…/flake.nix) keep the idiomatic
          # `{ self, … }` output signature, whose intentionally-unused args
          # deadnix would otherwise flag. Refs #777.
          deadnix = pkgs.runCommand "deadnix-check" { nativeBuildInputs = [ pkgs.deadnix ]; } ''
            deadnix --fail ${./flake.nix} ${./nix}
            touch "$out"
          '';

          # flake.nix is free of the anti-patterns statix lints (e.g. manual
          # `inherit`). Same authored-flake scoping rationale as deadnix. Refs #777.
          statix = pkgs.runCommand "statix-check" { nativeBuildInputs = [ pkgs.statix ]; } ''
            statix check ${./flake.nix}
            statix check ${./nix}
            touch "$out"
          '';

          # The sandbox-pure subset of the pre-commit hooks, run by the prek
          # runner via git-hooks.nix (see preCommitCheck above). Refs #778.
          pre-commit = preCommitCheck;

          # The dev-shell evaluates and its closure builds.
          devShell = self.devShells.${system}.default;

          # devShellTools (the parity-test SSoT) evaluates to a non-empty list.
          devShellTools = pkgs.runCommand "devshell-tools-eval" { } ''
            count=${toString (builtins.length (devShellToolNames pkgs))}
            test "$count" -gt 0
            touch "$out"
          '';
        }
        # One devshell build per capability module (#884), generated from the
        # nix/modules/ registry so a module cannot ship without its check —
        # `module-<name>` evaluates and builds on every default system
        # (x86_64-linux in Tier-0 CI; the others via `--all-systems` eval).
        # tests/test_flake_modules.py reuses these as its `nix develop` entry
        # points for the deeper smoke tests (toolchain on PATH, uv sdist build).
        // pkgs.lib.mapAttrs' (
          name: _:
          pkgs.lib.nameValuePair "module-${name}" (mkProjectShell {
            inherit pkgs;
            modules = [ name ];
          })
        ) capabilityModules
        # The ci homeConfigurations build as Tier-0 checks. x86_64-darwin is
        # the eval-only best-effort tier (ADR platform table): it exists as a
        # homeConfiguration but gets no build leg. Refs #819.
        // pkgs.lib.optionalAttrs (system != "x86_64-darwin") {
          hm-minimal = self.homeConfigurations."ci-minimal-${system}".activationPackage;
          hm-full = self.homeConfigurations."ci-full-${system}".activationPackage;
        };

        # ------------------------------------------------------------------
        # packages — the cross-platform services PoC plus the Linux-only
        # image set.
        # ------------------------------------------------------------------
        packages = {
          # The #795 SeaweedFS+Postgres local-services PoC (servicesPoC above):
          # `nix run .#services` — pure module eval, cross-platform.
          services = servicesPoC;
        }
        # The image and its scan targets are Linux-only (dockerTools.* fails to
        # even evaluate on darwin), so expose them only on *-linux systems.
        # Without this guard `nix flake check --all-systems` aborts during the
        # darwin eval. The dev-shell and services stay cross-platform. Refs #774.
        // pkgs.lib.optionalAttrs (pkgs.lib.hasSuffix "-linux" system) {
          # -----------------------------------------------------------------
          # devkitImage — Nix-built devcontainer image (T2.1, #634).
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
          # pre-commit -> prek (#778, closes #40): the image ships the `prek`
          # runner (Rust, via devTools) and no longer bakes the Python
          # `pre-commit` — one fewer manylinux/FHS consumer. prek runs the
          # committed `.pre-commit-config.yaml`; the flake's `checks.pre-commit`
          # runs the sandbox-pure subset under `nix flake check`.
          devkitImage =
            let
              # Nix C++/compression runtime exposed on the loader path so
              # runtime-installed manylinux wheels resolve their NEEDED libs.
              # stdenv.cc.cc.lib carries libstdc++.so.6 + libgcc_s.so.1; zlib
              # carries libz.so.1 — the libraries pre-compiled PyPI wheels link
              # against. Set as LD_LIBRARY_PATH (config.Env) so it is honoured
              # both by standalone wheel executables (via the /lib64 loader
              # below) and, crucially, by C-extension .so files dlopened by the
              # baked Nix CPython (numpy, scipy, pre-commit's pyjson5) — those
              # never traverse /lib64, so the loader symlink alone cannot fix
              # them. The image-scope analogue of the dev-shell's #698 fix, but
              # UNGATED: an all-Nix container has no foreign FHS host binaries
              # to pollute, so the #698 /etc/NIXOS ABI gate never applies. #736.
              manylinuxLibPath = pkgs.lib.makeLibraryPath [
                pkgs.stdenv.cc.cc.lib
                pkgs.zlib
              ];

              # The FHS loader name/dir manylinux wheels hardcode are
              # arch-specific: x86_64 -> /lib64/ld-linux-x86-64.so.2,
              # aarch64 -> /lib/ld-linux-aarch64.so.1. Derive from the build
              # platform so the multi-arch image is correct on both. Refs #736.
              fhsLoaderName =
                if pkgs.stdenv.hostPlatform.isAarch64 then "ld-linux-aarch64.so.1" else "ld-linux-x86-64.so.2";
              fhsLoaderDir = if pkgs.stdenv.hostPlatform.isAarch64 then "lib" else "lib64";

              # Authoritative built-tag record (#921). The real publish tag (RCs
              # included) is only known at the workflow/publish layer: a plain
              # `nix build` derives the version from the checked-in `./.vig-os`
              # repo pin, which advances only at finalize and so is stale for
              # release candidates. The release build-image action runs
              # `nix build --impure` with `VIG_OS_VERSION` set to the true
              # publish tag; that single, named, explicit env read is the ONLY
              # impurity, and it is empty under a plain (pure) `nix build` —
              # `builtins.getEnv` returns "" in pure eval — so the repo-pin
              # fallback in the bootstrap below keeps `nix build` bit-
              # reproducible. Baked as /root/assets/VERSION so init-workspace.sh
              # can stamp a scaffolded `.vig-os` with the real tag on a raw
              # `podman run` upgrade that forwards no env (install.sh aside).
              imageVersionOverride = builtins.getEnv "VIG_OS_VERSION";

              # Bake the workspace assets, pre-commit cache dir and template
              # .venv scaffold as a normal image layer. UV_PYTHON pins the Nix
              # interpreter and UV_PYTHON_DOWNLOADS=never forbids uv from
              # fetching a managed CPython (absent in the sandbox anyway). The
              # venv/pre-commit population needs network, so it is best-effort
              # here and the directories are created unconditionally.
              bootstrap =
                pkgs.runCommand "devkit-bootstrap"
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

                    # Ship the migration guide in the image (canonical copy is
                    # docs/MIGRATION.md; docs/ is not otherwise baked). Lets a
                    # user read the new-environment paradigm + consumer contract
                    # from inside the container. Refs #625.
                    cp ${./docs/MIGRATION.md} "$out/root/assets/MIGRATION.md"
                    chmod u+w "$out/root/assets/MIGRATION.md"

                    # Resolve the built tag: the explicit VIG_OS_VERSION override
                    # (release build, via --impure) when present, else the repo's
                    # pinned version. Empty override => pure/plain `nix build`, so
                    # this is the reproducible repo pin (#921/#642). Prefer the
                    # renamed DEVKIT_VERSION key, falling back to the legacy
                    # DEVCONTAINER_VERSION so an un-migrated pin still builds (#781).
                    dcver="$(sed -n 's/^DEVKIT_VERSION=//p' ${./.vig-os})"
                    [ -n "$dcver" ] || dcver="$(sed -n 's/^DEVCONTAINER_VERSION=//p' ${./.vig-os})"
                    imageVersion="${imageVersionOverride}"
                    [ -n "$imageVersion" ] || imageVersion="$dcver"

                    # Authoritative built-tag record (#921): a distinct, machine-
                    # readable copy of the true tag that init-workspace.sh reads to
                    # stamp a scaffolded `.vig-os` when no VIG_OS_VERSION env is
                    # forwarded (raw `podman run ... init-workspace.sh` upgrade).
                    printf '%s\n' "$imageVersion" > "$out/root/assets/VERSION"

                    # Bake the devcontainer version into the scaffolded `.vig-os`,
                    # replacing the {{IMAGE_TAG}} placeholder. The Debian build
                    # relied on the IMAGE_TAG build-arg; the reproducible Nix image
                    # reads the repo's pinned DEVKIT_VERSION, so a scaffolded
                    # workspace pins the devkit release it was built from. #642.
                    sed -i "s/{{IMAGE_TAG}}/$imageVersion/g" "$out/root/assets/workspace/.vig-os"

                    # Bake the build-time placeholder manifest so
                    # init-workspace.sh takes its fast substitution path instead
                    # of a slow runtime find+grep over the whole scaffold (#718).
                    # Lists every workspace asset carrying a substitution token,
                    # at the in-image runtime path (/root/assets/workspace/...),
                    # sorted for bit-reproducibility. The token set mirrors the
                    # runtime fallback in init-workspace.sh; the Debian
                    # Containerfile generated this file the same way.
                    { grep -rl \
                        '{{SHORT_NAME}}\|{{ORG_NAME}}\|{{GITHUB_REPOSITORY}}' \
                        "$out/root/assets/workspace" \
                        --exclude-dir=.git \
                        --exclude-dir=.venv \
                        --exclude-dir=.pre-commit-cache \
                        2>/dev/null || true; } \
                      | sed "s|$out||" | LC_ALL=C sort \
                      > "$out/root/assets/.placeholder-manifest.txt"

                    # /root/.bashrc with carried aliases: precommit (now the prek
                    # runner, #778) plus cc/cld (#545).
                    cat > "$out/root/.bashrc" <<'BASHRC'
                    alias precommit="prek run"
                    alias cc="claude"
                    alias cld="claude --dangerously-skip-permissions"
                    BASHRC

                    # Pre-create the project virtualenv from the baked CPython
                    # so /root/assets/workspace/.venv/bin/activate exists in the
                    # image. The published 0.3.x consumer post-create.sh runs
                    # `sed -i .../.venv/bin/activate` as its first venv step and
                    # aborts under `set -e` when the file is missing (#735).
                    # Hermetic and network-free: no packages are installed; the
                    # consumer's `just sync` (uv) populates the venv at
                    # post-create. The path matches UV_PROJECT_ENVIRONMENT /
                    # VIRTUAL_ENV (config.Env). `venv` bakes the build-time $out
                    # prefix into activate/pyvenv.cfg, so rewrite it to the
                    # runtime image path so VIRTUAL_ENV resolves to
                    # /root/assets/workspace/.venv inside the container.
                    venvdir="$out/root/assets/workspace/.venv"
                    ${python}/bin/python3 -m venv "$venvdir"
                    find "$venvdir/bin" -maxdepth 1 -type f \
                      -exec sed -i "s|$out||g" {} +
                    sed -i "s|$out||g" "$venvdir/pyvenv.cfg"
                    # `python -m venv` writes VIRTUAL_ENV_PROMPT unquoted
                    # (VIRTUAL_ENV_PROMPT=.venv), but the consumer post-create.sh
                    # rewrites the *double-quoted* form
                    # (VIRTUAL_ENV_PROMPT="..." -> the project short name). Without
                    # quotes that sed no-ops and the prompt is never renamed.
                    # Normalize to the quoted "template-project" the template
                    # expects so the rename applies. Refs #735.
                    sed -i -E 's/^([[:space:]]*VIRTUAL_ENV_PROMPT=).*/\1"template-project"/' \
                      "$venvdir/bin/activate"

                    mkdir -p "$out/opt/prek-cache"
                    mkdir -p "$out/workspace"

                    # Writable global-install prefix for npm. npm's default
                    # prefix is the read-only nodejs nix-store path, whose bin/
                    # is off PATH — so `npm install -g <tool>` reports success
                    # but the binary lands where nothing can resolve it. Create
                    # the FHS /usr/local/bin (already on the baked PATH) so the
                    # prefix exists and is writable at runtime; NPM_CONFIG_PREFIX
                    # (config.Env) points npm here. Refs #728.
                    mkdir -p "$out/usr/local/bin"

                    # docker -> podman compatibility shim. The image ships
                    # `podman` but no `docker` binary. Docker-out-of-Docker
                    # works because podman honors DOCKER_HOST (set by the
                    # consumer docker-compose.yml), but any recipe/script that
                    # invokes `docker` literally fails with "command not found".
                    # A tiny wrapper on the (already on-PATH) /usr/local/bin
                    # execs the baked podman, so docker-literal callers get a
                    # working binary without pulling in the Docker engine. The
                    # heredoc is quoted so `$@` is written verbatim; the store
                    # paths are interpolated by Nix at eval time. Refs #740.
                    cat > "$out/usr/local/bin/docker" <<'DOCKERSHIM'
                    #!${pkgs.runtimeShell}
                    exec ${pkgs.podman}/bin/podman "$@"
                    DOCKERSHIM
                    chmod +x "$out/usr/local/bin/docker"

                    # /tmp with the sticky bit. A bare layered image has no
                    # /tmp; tools that need a scratch/socket dir (tmux, uv,
                    # pytest) fail without it ("no suitable socket path"). An
                    # FHS base distro would have supplied it.
                    mkdir -p "$out/tmp"
                    chmod 1777 "$out/tmp"

                    # FHS dynamic loader for runtime-installed manylinux wheels.
                    # A bare Nix layered image lacks the loader every manylinux
                    # wheel hardcodes as its PT_INTERP, so PyPI-pinned standalone
                    # tools (e.g. pre-commit's ruff/typos) abort with "cannot
                    # execute: required file not found". Symlink the Nix glibc
                    # loader there; being newer it runs old-glibc wheels (glibc is
                    # backward compatible). Paired with LD_LIBRARY_PATH
                    # (config.Env) for the C++/z runtime the wheels need. The
                    # loader name and FHS dir are ARCH-SPECIFIC — x86_64 wheels
                    # want /lib64/ld-linux-x86-64.so.2, aarch64 wheels want
                    # /lib/ld-linux-aarch64.so.1 — so derive both from the build
                    # platform (the image builds natively per arch). Refs #736.
                    mkdir -p "$out/${fhsLoaderDir}"
                    ln -s ${pkgs.glibc}/lib/${fhsLoaderName} \
                      "$out/${fhsLoaderDir}/${fhsLoaderName}"
                    # /etc/nix/nix.conf enabling the experimental features the
                    # modern Nix CLI needs. The image bakes CppNix but shipped
                    # no nix.conf, so `nix-command`/`flakes` were off by default
                    # and ad-hoc on-demand tooling (`nix shell nixpkgs#<x>`,
                    # `nix run`, `nix eval`) failed without an explicit
                    # `--extra-experimental-features` flag. Refs #739.
                    #
                    # `accept-flake-config` is deliberately NOT baked: setting it
                    # `true` made any in-container `nix run github:attacker/flake`
                    # silently accept that flake's `substituters`/
                    # `trusted-public-keys` — a cache-redirection supply-chain
                    # trapdoor. Instead the trusted caches are pinned EXPLICITLY
                    # below so normal builds still substitute from them, while a
                    # foreign flake's `nixConfig` needs a per-invocation
                    # `--accept-flake-config`. The substituters + public keys
                    # mirror CONTRIBUTE.md (cache.nixos.org + the public vig-os
                    # Cachix cache); the keys are PUBLIC. Refs #773.
                    #
                    # Pinning the flake registry `nixpkgs` to the image's locked
                    # input is deferred: it needs that input's store path threaded
                    # in here and is not a one-liner, so on-demand `nix shell`
                    # tracks the channel default for now. Refs #739.
                    #
                    # `build-users-group =` (empty): the in-image nix runs as
                    # root, single-user, daemonless (no `nixbld` group, store
                    # owned root:root). Without this, any on-demand `nix shell`/
                    # `nix develop` that needs a LOCAL build (not a pure cache
                    # substitution) aborts with "the group 'nixbld' ... does not
                    # exist" — e.g. a rust-overlay toolchain. Empty disables the
                    # build-user drop so root builds directly (standard rootless/
                    # in-container setting). Refs #749.
                    mkdir -p "$out/etc/nix"
                    cat > "$out/etc/nix/nix.conf" <<'NIXCONF'
                    experimental-features = nix-command flakes
                    substituters = https://cache.nixos.org https://vig-os.cachix.org
                    trusted-public-keys = cache.nixos.org-1:6NCHdD59X431o0gWypbMrAURkbJ16ZPMQFGspcDShjY= vig-os.cachix.org-1:yoOYRi3bvnM6ThxO0joLt7vtzhTfkq3r6jykeUMg7Bk=
                    build-users-group =
                    NIXCONF
                  '';
            in
            pkgs.dockerTools.buildLayeredImage {
              # Name matches the published repo so the portable testinfra
              # (#635), which targets ghcr.io/vig-os/devkit:<tag>, runs
              # unchanged against the loaded image under a unique tag.
              name = "ghcr.io/vig-os/devkit";
              # Disposable discovery tag, matching the CI workflow's
              # INDEX_TAG (.github/workflows/nix-image.yml). The versioned
              # / :latest cutover is handled separately (#639).
              tag = "nix-dev";

              contents = imageTools ++ [ bootstrap ];

              # Sanitize the baked CPython's sysconfig compiler records (#879).
              # nixpkgs' python bakes its Nix build toolchain into sysconfig
              # (`_sysconfigdata*.py` / `_sysconfig_vars*.json` / config Makefile):
              # CC='gcc', CXX='g++', and link commands starting with those names.
              # The image deliberately ships no compiler (consumer contract:
              # toolchains come from the project flake — documented via #882),
              # so those are phantom names: PEP 517 backends inherit them
              # verbatim — scikit-build-core exports CC/CXX into the
              # environment, making CMake hard-fail on the missing 'g++'
              # instead of doing PATH discovery, and setuptools invokes the
              # literal 'gcc'. Rewriting the first tokens to the generic POSIX
              # 'cc'/'c++' restores PATH discovery against whatever toolchain
              # the project provides (and yields an honest "no compiler found"
              # when none does).
              #
              # Mechanism: a last-layer shadow copy, not a CPython rebuild.
              # fakeRootCommands runs in the image-root staging dir, so files
              # created under ./nix/store/<python>/... are tarred into the
              # customisation layer (ordered last) and override the python
              # layer's copies at container runtime; the dev-shell toolchain
              # and every python-dependent derivation stay fully cached. The
              # python layer's stale `_sysconfigdata*.pyc` are hash-based
              # (CHECKED_HASH), so the interpreter detects the changed source
              # and recompiles instead of serving the old values. Note
              # `enableFakechroot` can NOT do this: its layer tar excludes
              # ./nix/store. Deterministic (fixed sed over fixed input), so
              # digest reproducibility is preserved.
              fakeRootCommands = ''
                pylib=${python}/lib/python${python.pythonVersion}
                shadow=.$pylib
                mkdir -p "$shadow"
                cp "$pylib"/_sysconfigdata__*.py "$pylib"/_sysconfig_vars__*.json "$shadow/"
                cfg="$(basename "$pylib"/config-*)"
                mkdir -p "$shadow/$cfg"
                cp "$pylib/$cfg/Makefile" "$shadow/$cfg/"
                chmod -R u+w "$shadow"
                sed -i -E \
                  -e "s/'(CC|LINKCC|LDSHARED|BLDSHARED)': 'gcc(['[:space:]])/'\1': 'cc\2/" \
                  -e "s/'(CXX|LDCXXSHARED)': 'g\+\+(['[:space:]])/'\1': 'c++\2/" \
                  "$shadow"/_sysconfigdata__*.py
                sed -i -E \
                  -e 's/"(CC|LINKCC|LDSHARED|BLDSHARED)": "gcc(["[:space:]])/"\1": "cc\2/' \
                  -e 's/"(CXX|LDCXXSHARED)": "g\+\+(["[:space:]])/"\1": "c++\2/' \
                  "$shadow"/_sysconfig_vars__*.json
                sed -i -E \
                  -e 's/^(CC=[[:space:]]*)gcc$/\1cc/' \
                  -e 's/^(CXX=[[:space:]]*)g\+\+$/\1c++/' \
                  "$shadow/$cfg/Makefile"
              '';

              # Deterministic epoch timestamp keeps the digest reproducible.
              created = "1970-01-01T00:00:00Z";

              config = {
                Cmd = [ "${pkgs.bashInteractive}/bin/bash" ];
                WorkingDir = "/workspace";
                Env = [
                  # Declare PATH explicitly. buildLayeredImage symlinks every
                  # tool's bin into /bin but sets no PATH in the OCI config; a
                  # Debian base used to provide one. `podman run` masks this by
                  # injecting a default PATH, but the docker-compose +
                  # `devcontainer exec` path (and VS Code) does not, so the
                  # baked toolchain was off PATH there — breaking pre-commit's
                  # `language: system` ruff/typos hooks (`Executable not found`)
                  # during an in-container `git commit`. Refs #697, #698.
                  "PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
                  "LANG=en_US.UTF-8"
                  "LANGUAGE=en_US:en"
                  "LC_ALL=en_US.UTF-8"
                  "LOCALE_ARCHIVE=${pkgs.glibcLocales}/lib/locale/locale-archive"
                  # Expose the Nix C++/compression runtime on the loader path
                  # for runtime-installed manylinux wheels (see manylinuxLibPath
                  # above). Required for the C-extension .so files the baked Nix
                  # CPython dlopens (numpy/scipy/pyjson5), which never traverse
                  # the /lib64 loader. Ungated image analogue of #698. #736.
                  "LD_LIBRARY_PATH=${manylinuxLibPath}"
                  "PYTHONUNBUFFERED=1"
                  "IN_CONTAINER=true"
                  # #545: the container is the trust boundary; bypass the uid-0
                  # check for `claude --dangerously-skip-permissions`.
                  "IS_SANDBOX=1"
                  "PREK_HOME=/opt/prek-cache"
                  "UV_PROJECT_ENVIRONMENT=/root/assets/workspace/.venv"
                  "VIRTUAL_ENV=/root/assets/workspace/.venv"
                  # Point npm's global prefix at the writable, on-PATH
                  # /usr/local (its bin/ is baked by the bootstrap layer) so
                  # `npm install -g` lands runnable CLIs on PATH. Refs #728.
                  "NPM_CONFIG_PREFIX=/usr/local"
                  "UV_PYTHON_DOWNLOADS=never"
                  "UV_PYTHON=${python}/bin/python3.14"
                  "BATS_LIB_PATH=${batsWithLibs pkgs}/share/bats"
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

          # devkitImageEnv — vulnix scan target (T3.1, #637). A buildEnv
          # whose runtime closure equals the image's package set (imageTools),
          # so `vulnix --closure` sees exactly what ships in the image. The OCI
          # tarball itself is gzipped and exposes no scannable store references,
          # hence this dedicated env rather than scanning the image output.
          devkitImageEnv = pkgs.buildEnv {
            name = "devcontainer-image-env";
            paths = imageTools;
            ignoreCollisions = true;
          };

          # vulnix — pinned CVE scanner (#637) from the locked nixpkgs so the
          # nightly scan is reproducible rather than tracking a rolling channel.
          # The upstream-hardcoded 10 s connect/read timeout on the NVD feed
          # downloads dies on nvd.nist.gov's throttling stalls
          # (nix-community/vulnix#171); bump it to 60 s until upstream grows
          # retry/timeout options.
          vulnix = pkgs.vulnix.overrideAttrs (old: {
            postPatch = (old.postPatch or "") + ''
              substituteInPlace src/vulnix/nvd.py \
                --replace-fail "timeout=10" "timeout=60"
            '';
          });

          # nix-fast-build — the Tier-0 CI driver that evaluates and builds every
          # `checks.<system>` derivation in parallel with an eval cache (#779).
          # Exposed as a package (NOT devTools) so CI runs it reproducibly via
          # `nix run .#nix-fast-build` from the pinned nixpkgs, without baking a
          # CI-only tool into the dev-shell or the image closure. Refs #779.
          inherit (pkgs) nix-fast-build;
        };

        # ------------------------------------------------------------------
        # apps — `nix run .#install` bootstraps a consumer project;
        # `nix run .#services` boots the #795 local-services PoC.
        #
        # Wraps the host-level install.sh (the behavior SSoT: pulls the published
        # image and scaffolds a workspace) so consumers can run it straight from
        # the flake without a prior `curl | bash`. writeShellScriptBin (not
        # writeShellApplication) preserves install.sh's own shebang, `set` flags,
        # and ambient-PATH tool resolution (curl/git/docker) unchanged. Refs #777.
        # ------------------------------------------------------------------
        apps = {
          install = flake-utils.lib.mkApp {
            drv = pkgs.writeShellScriptBin "install" (builtins.readFile ./install.sh);
            name = "install";
          };
          services = flake-utils.lib.mkApp {
            drv = servicesPoC;
            name = "services";
          };
          default = self.apps.${system}.install;
        };
      }
    )
    // {
      # System-independent reusable outputs.
      lib = {
        inherit
          mkProjectShell
          mkProjectServices
          devTools
          ;
        # PATH-portable renders of the one hook-set definition (#883):
        # `runner` must match the committed .pre-commit-config.yaml,
        # `scaffold` the assets/workspace copy (tests/test_flake_hooks.py).
        hooksPortable = hooksModule.portable;
      };
      overlays.default = overlay;

      # ----------------------------------------------------------------------
      # nixosModules / homeManagerModules — install the shared toolchain as
      # importable NixOS or home-manager config.
      #
      # A consumer imports the module and flips one option to get exactly the
      # `devTools` set the dev-shell and image ship — the same SSoT, no drift.
      # The fast-mover overlay (uv/gh/claude-code from unstable) is applied so
      # those resolve to the intended versions; claude-code is unfree, so the
      # consumer must allow it (documented in docs/NIX.md). Refs #777.
      # ----------------------------------------------------------------------
      nixosModules.default =
        {
          config,
          lib,
          pkgs,
          ...
        }:
        {
          options.programs.vigos-devtools.enable = lib.mkEnableOption "the vigOS devcontainer toolchain (devTools)";
          config = lib.mkIf config.programs.vigos-devtools.enable {
            nixpkgs.overlays = [ overlay ];
            environment.systemPackages = devTools pkgs;
          };
        };

      # ----------------------------------------------------------------------
      # vigos.* home modules (#818) - the terminal home environment as
      # per-concern home-manager modules (ADR-home-environment-modules).
      # Exported as PATHS, not imported functions: the module system dedups
      # path imports, so importing the `default` umbrella plus an individual
      # module never double-declares options. The legacy
      # `programs.vigos-devtools.enable` is shimmed in packages.nix
      # (mkRenamedOptionModule, one release - docs/NIX.md policy).
      # `homeModules` is the newer-convention alias of the same set.
      # ----------------------------------------------------------------------
      homeManagerModules = {
        default = ./nix/home/default.nix;
        packages = ./nix/home/packages.nix;
        shell = ./nix/home/shell.nix;
        multiplexer = ./nix/home/multiplexer.nix;
        cli = ./nix/home/cli.nix;
        direnv = ./nix/home/direnv.nix;
        git = ./nix/home/git.nix;
        claude = ./nix/home/claude.nix;
        sesh = ./nix/home/sesh.nix;
        ghdash = ./nix/home/ghdash.nix;
        editor = ./nix/home/editor.nix;
      };
      homeModules = self.homeManagerModules;

      # The ci matrix plus `demo` — onboarding sugar built from the same
      # modules (full profile, synthetic user). Refs #827.
      homeConfigurations = ciHomeConfigurations // {
        demo = home-manager.lib.homeManagerConfiguration {
          pkgs = mkHomePkgs "x86_64-linux";
          modules = [
            ./nix/home/default.nix
            {
              home = {
                username = "demo";
                homeDirectory = "/home/demo";
                stateVersion = "26.05";
              };
            }
            hmProfiles.full
          ];
        };
      };

      # `nix flake init -t github:vig-os/devcontainer#personal` scaffolds a
      # ~40-line personal flake importing the vigos.* modules. NOT in the
      # deadnix/statix scope: like the workspace scaffold, the template keeps
      # idiomatic possibly-unused args. Refs #827.
      templates.personal = {
        path = ./templates/personal;
        description = "Personal home-manager flake importing the vigOS home modules";
      };

      # `nix flake init -t github:vig-os/devcontainer#python` restores an opt-in
      # Python package layout (pyproject + src/ + pytest) onto the now
      # language-neutral scaffold (#929). `nix flake init -t` does no token
      # substitution, so the template uses a concrete `example_pkg` the user
      # renames (see templates/python/README.md). Refs #930.
      templates.python = {
        path = ./templates/python;
        description = "Opt-in Python project starter (pyproject + src/ + pytest)";
      };
    };
}
