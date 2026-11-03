# Offline package registry. Derive the local package version from the release
# manifest, so a release bump cannot leave the Typst import version behind.
pkgs:
let
  version = builtins.head (
    builtins.concatMap (
      line:
      let
        match = builtins.match "DEVKIT_VERSION=(.*)" line;
      in
      if match == null then [ ] else match
    ) (pkgs.lib.splitString "\n" (builtins.readFile ../.vig-os))
  );
in
pkgs.runCommand "devkit-typst-packages-${version}" { inherit version; } ''
  mkdir -p "$out/local/devkit-docs/${version}"
  cp -R ${../assets/typst/vendor}/preview "$out/preview"
  cp -R ${../assets/typst/devkit-docs}/. "$out/local/devkit-docs/${version}/"
  cp ${../LICENSE} "$out/local/devkit-docs/${version}/LICENSE"
  cat > "$out/local/devkit-docs/${version}/typst.toml" <<'MANIFEST'
  [package]
  name = "devkit-docs"
  version = "${version}"
  entrypoint = "lib.typ"
  compiler = "0.15.0"
  authors = ["devkit contributors"]
  license = "Apache-2.0"
  description = "Neutral, offline document house style"
  MANIFEST
''
