# Capability-module registry (#884, docs/rfcs/ADR-capability-modules.md).
#
# Maps a module name (the string consumers pass in mkProjectShell's
# `modules = [ "<name>" … ]`) to its definition: a function
# `pkgs -> { packages, env, shellHook }` (all fields optional — the v1
# contract). mkProjectShell resolves names against this attrset and the
# flake generates a per-system `checks.<system>.module-<name>` devshell
# build for every entry, so a module cannot ship without its check.
#
# Candidate modules — geant4, rust, fortran/f2py, root — are deliberately
# NOT defined until a concrete consumer asks (YAGNI; see the ADR).
{
  native = import ./native.nix;
}
