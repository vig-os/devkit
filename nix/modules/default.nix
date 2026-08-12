# Capability-module registry (#884, docs/rfcs/ADR-capability-modules.md).
#
# Maps a module name (the string consumers pass in mkProjectShell's
# `modules = [ "<name>" … ]`) to its definition: a function
# `pkgs -> options -> { packages, env, shellHook }` (contribution fields all
# optional — the v1 contract). `options` is the per-entry attrset a consumer
# passes via `{ name = "<name>"; … }` minus `name` (empty `{}` for the plain
# string form). mkProjectShell resolves names against this attrset and the
# flake generates a per-system `checks.<system>.module-<name>` devshell
# build for every entry, so a module cannot ship without its check. A module
# whose options are mandatory overrides how that check instantiates it — see
# ./check-entries.nix.
#
# Candidate modules — geant4, fortran/f2py, root — are deliberately NOT
# defined until a concrete consumer asks (YAGNI; see the ADR). `rust` was such
# a candidate and shipped on gerchowl/filesender's ask (#1400).
{
  native = import ./native.nix;
  node = import ./node.nix;
  docs = import ./docs.nix;
  rust = import ./rust.nix;
}
