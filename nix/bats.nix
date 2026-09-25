# bats with its helper libraries (support/assert/file), wrapped so
# BATS_LIB_PATH can be derived from one place. Shared by the devTools list
# (nix/devtools.nix), mkProjectShell, and the image env. Refs #695, #818.
#
# The symlinkJoin adds GNU parallel to bats' own PATH: `bats --jobs N` shells
# out to a `parallel` binary (bats-exec-suite) to spread test FILES across
# jobs, and nixpkgs' resholved bats resolves everything else (flock, coreutils)
# to absolute store paths but leaves that one lookup on PATH. Riding with bats
# keeps parallel off every consumer's PATH — bats is its only consumer.
# `meta` must be carried over: flake.nix's devShellToolNames reads
# meta.mainProgram to name the binary ("bats"), and symlinkJoin sets no pname.
# Refs #1687.
pkgs:
let
  batsWithLibs = pkgs.bats.withLibraries (p: [
    p.bats-support
    p.bats-assert
    p.bats-file
  ]);
in
pkgs.symlinkJoin {
  inherit (batsWithLibs) name meta;
  paths = [ batsWithLibs ];
  nativeBuildInputs = [ pkgs.makeWrapper ];
  postBuild = ''
    rm "$out/bin/bats"
    makeWrapper "${batsWithLibs}/bin/bats" "$out/bin/bats" \
      --prefix PATH : ${pkgs.lib.makeBinPath [ pkgs.parallel ]}
  '';
}
