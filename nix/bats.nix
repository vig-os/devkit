# bats with its helper libraries (support/assert/file), wrapped so
# BATS_LIB_PATH can be derived from one place. Shared by the devTools list
# (nix/devtools.nix), mkProjectShell, and the image env. Refs #695, #818.
#
# The symlinkJoin also gives bats a parallel runner: `bats --jobs N` shells out
# to one (bats-exec-suite) to spread test FILES across jobs, and nixpkgs'
# resholved bats resolves everything else (flock, coreutils) to absolute store
# paths but leaves that one lookup on PATH. Riding with bats keeps the runner off
# every consumer's PATH — bats is its only consumer.
#
# The runner is shenwei356/rush, which bats supports natively: bats-exec-suite
# reads BATS_PARALLEL_BINARY_NAME, defaulted here so `bats -j` needs nothing from
# the caller. It is NOT GNU parallel, which bats also accepts: parallel is a perl
# script, and this wrapper ships in the image env, so it re-imported perl into the
# image's runtime closure — the eviction #1108 performed to retire a standing CVE
# exception batch — and the nightly vulnix gate found perl 5.42.0 there with three
# unexcepted HIGH/CRITICAL findings. rush is Go: no interpreter behind it, and a
# 47 MiB closure against parallel's 121 MiB. Refs #1708.
#
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
      --prefix PATH : ${pkgs.lib.makeBinPath [ pkgs.rush-parallel ]} \
      --set-default BATS_PARALLEL_BINARY_NAME rush
  '';
}
