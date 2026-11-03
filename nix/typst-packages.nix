# The package has its own semver; devkit upgrades retain compatible imports.
pkgs:
let
  version =
    (builtins.fromTOML (builtins.readFile ../assets/typst/devkit-docs/typst.toml)).package.version;
in
pkgs.runCommand "devkit-typst-packages-${version}" { inherit version; } ''
  mkdir -p "$out/local/devkit-docs/${version}"
  cp -R ${../assets/typst/releases/devkit-docs}/. "$out/local/devkit-docs/"
  cp ${../assets/typst/devkit-docs.lock.json} "$out/devkit-docs.lock.json"
  cp -R ${../assets/typst/vendor}/preview "$out/preview"
  cp -R ${../assets/typst/devkit-docs}/. "$out/local/devkit-docs/${version}/"
  for package in "$out"/local/devkit-docs/*; do
    chmod u+w "$package"
    cp ${../LICENSE} "$package/LICENSE"
  done
''
