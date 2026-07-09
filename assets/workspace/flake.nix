{
  description = "Project development environment (vigOS toolchain).";

  # Downstream repos consume the shared toolchain as a flake INPUT, so updating
  # the dev environment means bumping that input — it never overwrites your
  # files. To update: `nix flake update vigos`.
  inputs = {
    # The shared vigOS toolchain (single source of truth).
    # This scaffold deliberately FLOATS on the default branch so a fresh
    # project works before its first pin. Once you depend on stability
    # (especially the vigos.* home-manager module options), pin a release
    # tag instead and bump deliberately:
    #   vigos.url = "github:vig-os/devcontainer?ref=<tag>";
    # Policy: docs/NIX.md "Home-manager modules - versioning & release policy".
    vigos.url = "github:vig-os/devcontainer";
    # Follow vigos's pinned nixpkgs + flake-utils so your tools match the
    # toolchain exactly (one resolved nixpkgs, no drift).
    nixpkgs.follows = "vigos/nixpkgs";
    flake-utils.follows = "vigos/flake-utils";
  };

  outputs =
    {
      self,
      vigos,
      nixpkgs,
      flake-utils,
    }:
    flake-utils.lib.eachDefaultSystem (
      system:
      let
        pkgs = import nixpkgs {
          inherit system;
          overlays = [ vigos.overlays.default ];
          config.allowUnfree = true;
        };

        # ────────────────────────────────────────────────────────────────────
        # Your project tools go here. This block is YOURS: a dev-environment
        # update never overwrites it (scaffold-once / never-overwrite, the same
        # guarantee as justfile.project and docker-compose.project.yaml).
        #
        #   extraPackages = pkgs: [
        #     pkgs.postgresql_16
        #     pkgs.ffmpeg
        #   ];
        # ────────────────────────────────────────────────────────────────────
        extraPackages = pkgs: [
          # add project tools here
        ];
      in
      {
        # The dev shell = the shared vigOS toolchain + your extras.
        # `direnv allow` (via .envrc) or `nix develop` enters it.
        devShells.default = vigos.lib.mkProjectShell {
          inherit pkgs;
          extraPackages = extraPackages pkgs;

          # Opt-in: let the flake GENERATE .pre-commit-config.yaml from the
          # shared base hook set instead of hand-managing the scaffolded
          # YAML — toggle base hooks, add per-hook/global excludes, or add
          # fully custom hooks; hook updates then flow with `nix flake
          # update vigos`, and your customization lives HERE (preserved).
          # Contract + migration steps: docs/MIGRATION.md ("Customizing
          # pre-commit hooks from the project flake"). Uncomment to opt in,
          # then delete .pre-commit-config.yaml and add it to .gitignore
          # (the generated config refuses to overwrite an existing file).
          #
          #   hooks = {
          #     typos.enable = false;                    # toggle a base hook
          #     detect-private-keys.excludes = [ "worker/src/index\\.ts" ];
          #     my-data-check = {                        # fully custom hook
          #       enable = true;
          #       entry = "./scripts/check-dat.sh";
          #       files = "\\.dat$";
          #       language = "system";
          #     };
          #   };
          #   hooksExcludes = [ "^data/stopping/" "\\.dat$" ]; # global excludes
        };

        # Opt-in local dev services (#795): a daemonless process-compose stack
        # (Postgres, SeaweedFS/S3, Redis, …) with service versions from the
        # pinned vigos nixpkgs — no Docker/Podman daemon, no extra flake
        # inputs. Uncomment, then `nix run .#services` (or enable the
        # `services` recipe in justfile.project); service state lands in
        # ./data — add it to .gitignore.
        #
        #   packages.services = vigos.lib.mkProjectServices {
        #     inherit pkgs;
        #     modules = [ { services.postgres."db".enable = true; } ];
        #   };

        # Future (upstream, opt-in): vigos may expose modular language shells —
        # e.g. `vigos.devShells.${system}.{cpp,geant4,dataAnalysis}` — that you
        # select without changing this scaffold. Out of scope today.
      }
    );
}
