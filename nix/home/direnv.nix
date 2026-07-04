# vigos.direnv — skeleton (#818); behavior lands with wave 1 (#821).
{ lib, ... }:
{
  options.vigos.direnv.enable = lib.mkEnableOption "direnv + nix-direnv integration";
}
