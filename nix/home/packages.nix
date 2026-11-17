# vigos.packages — the shared toolchain (devTools) as home packages.
#
# The #777 package-only module re-keyed into the vigos.* namespace (#818).
# The legacy `programs.vigos-devtools.enable` option is shimmed here (and
# only here) via mkRenamedOptionModule for one release — docs/NIX.md policy.
#
# Packages come from the `pkgs` this module is evaluated with. The flake's
# own homeConfigurations pass devkit's pinned nixpkgs + fast-mover overlay
# (self-pkgs), so tool versions match the dev-shell and image. A consumer
# passing its own pkgs applies `overlays.default` itself (home-manager
# rejects a module-set `nixpkgs.overlays` with an external pkgs).
#
# The agent CLI (claude-code) is opt-in via `vigos.packages.agentCli.enable`
# (default off, #2076): most machines run their own `claude` (a wrapper that
# picks a release channel and loads per-profile credentials, or a native
# install with its own updater), and a devkit-pinned copy would sit beside or
# ahead of it on PATH. Opting in installs devkit's pin, needs unfree allowed,
# and hands updates to Nix (DISABLE_AUTOUPDATER=1).
{
  config,
  lib,
  pkgs,
  ...
}:
let
  cfg = config.vigos.packages;
in
{
  imports = [
    (lib.mkRenamedOptionModule [ "programs" "vigos-devtools" "enable" ] [ "vigos" "packages" "enable" ])
  ];
  options.vigos.packages = {
    enable = lib.mkEnableOption "the vigOS toolchain (devTools) as home packages";
    agentCli.enable = lib.mkEnableOption "devkit's pinned agent CLI (claude-code); shadows any machine `claude`";
  };
  config = lib.mkIf cfg.enable (
    lib.mkMerge [
      { home.packages = (import ../devtools.nix) pkgs; }
      (lib.mkIf cfg.agentCli.enable {
        home.packages = (import ../agent-tools.nix) pkgs;
        # Nix owns this claude's updates; the native self-updater stays off.
        home.sessionVariables.DISABLE_AUTOUPDATER = lib.mkDefault "1";
      })
    ]
  );
}
