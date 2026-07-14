# `node` capability module (#1027): the Node/TypeScript dev-shell capability.
# v1 contract (packages only, per docs/rfcs/ADR-capability-modules.md): puts
# `nodejs` — which bundles `npm` — on the dev-shell PATH so a consumer opts in
# with `modules = [ "node" ]` instead of hand-wiring `extraPackages = [
# pkgs.nodejs ]`. It deliberately does NOT provide the npm justfile recipes,
# the .gitignore fragment, the pre-commit hooks or the CodeQL language — those
# are scaffold concerns (the language-aware scaffold, #1024/#1025, and the
# first-scaffold npm recipe seeding in init-workspace.sh), not shell
# contributions.
#
# This is the first module that needs configuration, so it also exercises the
# per-module-options mechanism the ADR deferred: mkProjectShell calls a module
# as `pkgs -> options -> contribution`, where `options` is the attrset entry's
# fields minus `name`. The only recognized option is `version` (a Node major,
# e.g. 20), mapping to `pkgs.nodejs_<major>`; omitted, it uses the nixpkgs
# default `pkgs.nodejs`. Unknown option keys and unavailable versions fail at
# eval time with a clear message.
pkgs:
{
  version ? null,
  ...
}@options:
let
  # Only `version` is a recognized option — reject anything else loudly so a
  # typo (or an unsupported knob) is a hard eval error, never a silent no-op.
  knownOptions = [ "version" ];
  unknownOptions = builtins.filter (k: !builtins.elem k knownOptions) (builtins.attrNames options);

  # Resolve the Node package: a `version` major selects `pkgs.nodejs_<major>`;
  # null uses the nixpkgs default. An unavailable major (not packaged in the
  # pinned nixpkgs) fails at eval time rather than silently degrading.
  nodeAttr = "nodejs_${toString version}";
  nodePkg =
    if version == null then
      pkgs.nodejs
    else
      pkgs.${nodeAttr} or (throw (
        "node module: unavailable Node version '${toString version}' "
        + "(pkgs.${nodeAttr} is not in the pinned nixpkgs)"
      ));
in
if unknownOptions != [ ] then
  throw (
    "node module: unknown option(s): "
    + pkgs.lib.concatStringsSep ", " unknownOptions
    + "; the only recognized option is 'version'"
  )
else
  {
    # nodejs bundles npm, so a single package covers both `node` and `npm`.
    packages = [ nodePkg ];

    # The toolchain SSoT (nix/devtools.nix) already ships `nodejs` for the
    # @devcontainers/cli, and the ADR composition orders devTools BEFORE module
    # packages — so an appended module/extraPackages node is shadowed on PATH by
    # that default. When a consumer pins a specific `version`, prepend it in the
    # shellHook (a v1-contract fragment, exactly how the native module exports
    # CC/CXX) so the pinned major actually wins `node`/`npm` lookup. Fires ONLY
    # for an explicit version: the default form is a pure package contribution
    # (same major as the SSoT node, so nothing to override).
    shellHook = pkgs.lib.optionalString (version != null) ''
      export PATH="${nodePkg}/bin:$PATH"
    '';
  }
