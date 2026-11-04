# Preserve the compiler's provenance while sharing local packages with consumers.
pkgs:
pkgs.symlinkJoin {
  name = "typst-${pkgs.typst.version}";
  inherit (pkgs.typst) pname version;
  paths = [ pkgs.typst ];
  passthru.unwrapped = pkgs.typst;
  postBuild = ''
    unlink "$out/bin/typst"
    cp ${pkgs.writeShellScript "docs-typst" ''
      exec ${import ./vig-utils.nix pkgs}/bin/typst-with-packages ${import ./typst-packages.nix pkgs} ${pkgs.typst}/bin/typst "$@"
    ''} "$out/bin/typst"
  '';
}
