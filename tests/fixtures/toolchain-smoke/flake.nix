# Minimal consumer: exercise the action without devkit's Linux image tooling.
{
  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-26.05";
  outputs =
    { nixpkgs, ... }:
    {
      devShells = nixpkgs.lib.genAttrs [ "x86_64-linux" "x86_64-darwin" "aarch64-darwin" ] (
        system:
        let
          pkgs = import nixpkgs { inherit system; };
        in
        {
          default = pkgs.mkShell {
            packages = [
              pkgs.prek
              pkgs.just
              (pkgs.python3.withPackages (ps: [
                ps.pytest
                ps.pyyaml
              ]))
            ];
            shellHook = ''
              echo "toolchain smoke shellHook loaded"
              export DEVKIT_SMOKE_VALUE='first line
              second line with = and $literal'
              export PYTHONPATH=""
              export DEVKIT_SMOKE_EMPTY=""
              export DEVKIT_SMOKE_CHANGED="from shellHook"
            '';
          };
        }
      );
    };
}
