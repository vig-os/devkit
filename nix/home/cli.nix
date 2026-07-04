# vigos.cli — skeleton (#818); behavior lands with wave 1 (#821).
{ lib, ... }:
{
  options.vigos.cli.enable = lib.mkEnableOption "the vigOS modern-unix CLI configuration (config only; packages ship via vigos.packages)";
}
