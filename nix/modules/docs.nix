# `docs` capability module (#1178): the document-edition dev-shell capability.
# v1 contract (packages only, per docs/rfcs/ADR-capability-modules.md): puts
# `typst` (the document compiler), `typstyle` (its formatter), `tinymist`
# (the Typst language server with diagnostics and preview), and `poppler-utils`
# (PDF reading) on the dev-shell PATH. Document-oriented consumers opt in with
# `modules = [ "docs" ]` instead of a PyPI typst pin or hand-wiring packages.
#
# `poppler-utils` (#1573) supplies `pdftotext`/`pdftoppm` for PDF reading.
# OCR tools carry much larger closures and remain consumer-owned until a
# dedicated capability is justified.
#
# Takes no options (`_options`): there is NO version knob in v1. The Typst
# toolchain tracks nixpkgs-unstable via flake.nix's fastMovers overlay; the
# three tools share a Typst minor version. Typst output can change between
# versions, so consumers regenerate `generated/` artifacts once under the
# updated pinned toolchain.
#
# Deliberate v1 exclusions (see docs/NIX.md): pandoc/LaTeX (ask-gated until a
# consumer needs them), headless drawio/excalidraw export (electron-shaped, stays
# repo-owned), and Python doc-processing libs (pymupdf4llm, openpyxl) which
# belong in the consumer's own pyproject.toml via uv, not in a nix module.
pkgs: _options: {
  packages = with pkgs; [
    typst
    typstyle
    tinymist
    poppler-utils
  ];
}
