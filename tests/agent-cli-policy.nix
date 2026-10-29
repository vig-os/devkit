# Evaluation-only regression guard; no tool closures are built.
# nix eval --impure --json --file tests/agent-cli-policy.nix
let
  flake = builtins.getFlake (toString ../.);
  system = builtins.currentSystem;
  pkgs = import flake.inputs.nixpkgs {
    inherit system;
    overlays = [ flake.overlays.default ];
    config.allowUnfree = true;
  };
  lib = pkgs.lib;
  hasAgent = packages: builtins.any (p: lib.getName p == "claude-code") packages;
  default = flake.devShells.${system}.default;
  consumer = flake.lib.mkProjectShell { inherit pkgs; };
  optedIn = flake.lib.mkProjectShell {
    inherit pkgs;
    withAgentCli = true;
  };
  home = lib.evalModules {
    specialArgs = { inherit pkgs; };
    modules = [
      ../nix/home/packages.nix
      { options.home.packages = lib.mkOption { type = lib.types.listOf lib.types.package; }; }
      { programs.vigos-devtools.enable = true; }
    ];
  };
in
assert !hasAgent default.nativeBuildInputs;
assert !hasAgent consumer.nativeBuildInputs;
assert !hasAgent (flake.lib.devTools pkgs);
assert hasAgent optedIn.nativeBuildInputs;
assert builtins.elem pkgs.claude-code optedIn.nativeBuildInputs;
assert hasAgent flake.devShells.${system}.with-agent-cli.nativeBuildInputs;
assert hasAgent home.config.home.packages;
{
  agentCliPolicy = true;
}
