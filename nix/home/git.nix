# vigos.git — skeleton (#818); behavior lands with wave 1 (#821).
{ lib, ... }:
{
  options.vigos.git.enable = lib.mkEnableOption "the vigOS git environment (identity, optional SSH signing, gh, lazygit, delta)";
}
