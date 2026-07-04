# Umbrella module: every vigos.* module, each disabled by default (#818).
# Import this for the full option surface, or pick individual modules —
# path-based imports dedup, so mixing both never conflicts.
{
  imports = [
    ./packages.nix
    ./shell.nix
    ./multiplexer.nix
    ./cli.nix
    ./direnv.nix
    ./git.nix
  ];
}
