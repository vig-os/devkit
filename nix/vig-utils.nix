# vig-utils packaged from THIS flake's `packages/vig-utils` (#993, #666).
#
# A pure-Python hatchling package (single runtime dep `rich`) whose console
# scripts (prepare-changelog, validate-commit-msg, check-agent-identity, …)
# are the devkit's own automation surface.
#
# A function of `pkgs`, mirroring nix/pymarkdown.nix, so the definition works
# with or without `overlays.default` applied. Two consumers:
#
#   - flake.nix's `vigUtilsOverlay`, which exposes it as `pkgs.vig-utils` for
#     the toolchain SSoT (nix/devtools.nix -> dev-shell, image, home module);
#   - the commit-message/agent-identity hook fragments in nix/hooks.nix, whose
#     consumer surface must resolve the binaries from a plain `pkgs` — a
#     consumer's `.pre-commit-config.yaml` is generated before their overlay
#     is anyone's concern, and their project venv has no vig-utils (#1434).
#
# The devkit pin in a consumer's `flake.lock` governs the version.
pkgs:
pkgs.python314.pkgs.buildPythonPackage {
  pname = "vig-utils";
  version = "0.1.0";
  pyproject = true;
  src = ../packages/vig-utils;
  build-system = [ pkgs.python314.pkgs.hatchling ];
  dependencies = [ pkgs.python314.pkgs.rich ];
  pythonImportsCheck = [ "vig_utils" ];
  # The package's own tests need pytest + the repo; CI covers them.
  doCheck = false;
}
