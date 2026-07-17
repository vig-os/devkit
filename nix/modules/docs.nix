# `docs` capability module (#1178): the document-edition dev-shell capability.
# v1 contract (packages only, per docs/rfcs/ADR-capability-modules.md): puts
# `typst` (the document compiler) and `typstyle` (its formatter) on the
# dev-shell PATH so a document-oriented consumer opts in with
# `modules = [ "docs" ]` instead of a PyPI typst pin or hand-wiring
# `extraPackages`. First consumer: exo-pet/vault; qms and EXOMA
# presentations/grants share the same profile.
#
# Takes no options (`_options`): unlike `node`, there is NO version knob in v1 —
# nixpkgs carries a single `typst`/`typstyle` per pin, so the module simply
# tracks the toolchain nixpkgs pin rather than exposing a selectable version.
# typst output is not stable across versions, so a consumer's `generated/`
# artifacts are regenerated once under the pinned toolchain; pin-tracking beats
# maintaining a bespoke version overlay.
#
# Deliberate v1 exclusions (see docs/NIX.md): pandoc/LaTeX (ask-gated until a
# consumer needs them), headless drawio/excalidraw export (electron-shaped, stays
# repo-owned), and Python doc-processing libs (pymupdf4llm, openpyxl) which
# belong in the consumer's own pyproject.toml via uv, not in a nix module.
pkgs: _options: {
  packages = with pkgs; [
    typst
    typstyle
  ];
}
