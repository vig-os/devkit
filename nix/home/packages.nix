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
# rejects a module-set `nixpkgs.overlays` with an external pkgs) and must
# allow unfree for claude-code.
{
  config,
  lib,
  pkgs,
  ...
}:
{
  imports = [
    (lib.mkRenamedOptionModule [ "programs" "vigos-devtools" "enable" ] [ "vigos" "packages" "enable" ])
  ];
  options.vigos.packages.enable = lib.mkEnableOption "the vigOS toolchain (devTools) as home packages";
  config = lib.mkIf config.vigos.packages.enable {
    home.packages = (import ../devtools.nix) pkgs;
  };
}
