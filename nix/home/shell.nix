# vigos.shell — skeleton (#818); behavior lands with wave 1 (#821).
{ lib, ... }:
{
  options.vigos.shell.enable = lib.mkEnableOption "the vigOS shell environment (bash+zsh, starship, atuin, secretsEnv)";
}
