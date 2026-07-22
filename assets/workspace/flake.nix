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
    #   vigos.url = "github:vig-os/devkit?ref=<tag>";
    # Policy: https://github.com/vig-os/devkit/blob/main/docs/NIX.md
    # "Home-manager modules - versioning & release policy".
    vigos.url = "github:vig-os/devkit";
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

        # Workflow model (#1224): read DEVKIT_WORKFLOW from .vig-os and forward
        # it to mkProjectShell so the flake-generated pre-commit branch guard
        # follows the model — a `trunk` workspace drops the dev-branch clause,
        # mirroring the scaffolded .pre-commit-config.yaml. `gitflow` (the
        # default) and an absent/blank value are inert. Managed line; leave it.
        workflow =
          let
            vigOsPath = self + "/.vig-os";
            declared = builtins.filter (l: nixpkgs.lib.hasPrefix "DEVKIT_WORKFLOW=" l) (
              nixpkgs.lib.splitString "\n" (builtins.readFile vigOsPath)
            );
            value =
              if declared == [ ] then
                ""
              else
                nixpkgs.lib.removePrefix "DEVKIT_WORKFLOW=" (builtins.head declared);
          in
          if builtins.pathExists vigOsPath && value == "trunk" then "trunk" else "gitflow";
      in
      {
        # The dev shell = the shared vigOS toolchain + your extras.
        # `direnv allow` (via .envrc) or `nix develop` enters it.
        devShells.default = vigos.lib.mkProjectShell (
          {
            inherit pkgs;
            extraPackages = extraPackages pkgs;

            # Opt-in: let the flake GENERATE .pre-commit-config.yaml from the
            # shared base hook set instead of hand-managing the scaffolded
            # YAML — toggle base hooks, add per-hook/global excludes, or add
            # fully custom hooks; hook updates then flow with `nix flake
            # update vigos`, and your customization lives HERE (preserved).
            # Contract + migration steps:
            # https://github.com/vig-os/devkit/blob/main/docs/MIGRATION.md ("Customizing
            # pre-commit hooks from the project flake"). Uncomment to opt in, then
            # delete .pre-commit-config.yaml (the generated config refuses to
            # overwrite an existing file). The generated store symlink is ignored
            # automatically on (re)scaffold (#1092); add durable root ignores you
            # own to .gitignore.project.
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
          }
          # Forwarded only when the resolved devkit accepts it (#1249): the vigos
          # input floats to main, which may predate the argument; older builders
          # then fall back to their gitflow default instead of failing eval.
          // nixpkgs.lib.optionalAttrs (builtins.functionArgs vigos.lib.mkProjectShell ? workflow) {
            # Branch guard follows the workspace workflow model (#1224).
            inherit workflow;
          }
        );

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
