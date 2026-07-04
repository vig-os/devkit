# vigos.multiplexer — skeleton (#818); behavior lands with wave 1 (#821).
{ lib, ... }:
{
  options.vigos.multiplexer.enable = lib.mkEnableOption "the vigOS tmux configuration";
}
