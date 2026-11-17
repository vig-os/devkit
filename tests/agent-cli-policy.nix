# Evaluation-only regression guard; no tool closures are built.
# nix eval --impure --json --expr 'import ./tests/agent-cli-policy.nix {}'
{
  flake ? builtins.getFlake (toString ../.),
  system ? builtins.currentSystem,
}:
let
  pkgs = import flake.inputs.nixpkgs {
    inherit system;
    overlays = [ flake.overlays.default ];
    config.allowUnfree = true;
  };
  lib = pkgs.lib;
  hasAgent = packages: builtins.any (p: lib.getName p == "claude-code") packages;
  scaffold = (import ../assets/workspace/flake.nix).outputs {
    self = ../assets/workspace;
    vigos = flake;
    inherit (flake.inputs) nixpkgs flake-utils;
  };
  default = flake.devShells.${system}.default;
  consumer = flake.lib.mkProjectShell { inherit pkgs; };
  optedIn = flake.lib.mkProjectShell {
    inherit pkgs;
    withAgentCli = true;
  };
  rust = flake.lib.mkRustProject {
    inherit pkgs;
    src = ../templates/rust;
  };
  rustOptedIn = flake.lib.mkRustProject {
    inherit pkgs;
    src = ../templates/rust;
    withAgentCli = true;
  };
  machineWith =
    extra:
    lib.evalModules {
      specialArgs = { inherit pkgs; };
      modules = [
        flake.nixosModules.default
        {
          options.environment.systemPackages = lib.mkOption { type = lib.types.listOf lib.types.package; };
          options.nixpkgs.overlays = lib.mkOption { type = lib.types.listOf lib.types.raw; };
          config.programs.vigos-devtools.enable = true;
        }
        extra
      ];
    };
  machine = machineWith { };
  machineOptedIn = machineWith { programs.vigos-devtools.agentCli.enable = true; };
  homeWith =
    extra:
    lib.evalModules {
      specialArgs = { inherit pkgs; };
      modules = [
        ../nix/home/packages.nix
        {
          options.home.packages = lib.mkOption { type = lib.types.listOf lib.types.package; };
          options.home.sessionVariables = lib.mkOption {
            type = lib.types.attrsOf lib.types.str;
            default = { };
          };
        }
        extra
      ];
    };
  home = homeWith { vigos.packages.enable = true; };
  # Legacy option name, shimmed by mkRenamedOptionModule in packages.nix.
  homeLegacy = homeWith { programs.vigos-devtools.enable = true; };
  homeOptedIn = homeWith {
    vigos.packages = {
      enable = true;
      agentCli.enable = true;
    };
  };
  autoupdaterOff = cfg: (cfg.config.home.sessionVariables.DISABLE_AUTOUPDATER or null) == "1";
in
assert !hasAgent default.nativeBuildInputs;
assert !hasAgent consumer.nativeBuildInputs;
assert !hasAgent scaffold.devShells.${system}.default.nativeBuildInputs;
assert !hasAgent (flake.lib.devTools pkgs);
assert hasAgent optedIn.nativeBuildInputs;
assert builtins.elem pkgs.claude-code optedIn.nativeBuildInputs;
assert hasAgent flake.devShells.${system}.with-agent-cli.nativeBuildInputs;
assert !hasAgent rust.devShell.nativeBuildInputs;
assert hasAgent rustOptedIn.devShell.nativeBuildInputs;
# Machine-level surfaces leave claude to the machine unless opted in (#2076).
assert !hasAgent home.config.home.packages;
assert !hasAgent homeLegacy.config.home.packages;
assert !autoupdaterOff home;
assert hasAgent homeOptedIn.config.home.packages;
assert builtins.elem pkgs.claude-code homeOptedIn.config.home.packages;
assert autoupdaterOff homeOptedIn;
assert !hasAgent machine.config.environment.systemPackages;
assert hasAgent machineOptedIn.config.environment.systemPackages;
{
  agentCliPolicy = true;
}
