# Tinymist 0.15 does not read TYPST_IGNORE_SYSTEM_FONTS. Bridge the docs
# policy to its compile, preview and LSP flags without rebuilding the compiler.
pkgs:
pkgs.symlinkJoin {
  name = "tinymist-${pkgs.tinymist.version}";
  inherit (pkgs.tinymist) pname version;
  paths = [ pkgs.tinymist ];
  passthru.unwrapped = pkgs.tinymist;
  postBuild = ''
    unlink "$out/bin/tinymist"
    cp ${pkgs.writeShellScript "docs-tinymist" ''
      flags=()
      case "''${1:-}" in
        --log-filter) flags=("$1" "$2"); shift 2 ;;
        --log-filter=*) flags=("$1"); shift ;;
      esac
      case "''${1:-lsp}" in
        compile|preview|lsp)
          mode="''${1:-lsp}"
          if [ "$#" -gt 0 ]; then shift; fi
          exec ${import ./vig-utils.nix pkgs}/bin/typst-with-packages ${import ./typst-packages.nix pkgs} ${pkgs.tinymist}/bin/tinymist "''${flags[@]}" "$mode" --ignore-system-fonts "$@"
          ;;
        *) exec ${import ./vig-utils.nix pkgs}/bin/typst-with-packages ${import ./typst-packages.nix pkgs} ${pkgs.tinymist}/bin/tinymist "''${flags[@]}" "$@" ;;
      esac
    ''} "$out/bin/tinymist"
  '';
}
