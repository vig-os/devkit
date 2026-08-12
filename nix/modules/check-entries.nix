# How the generated per-module smoke check instantiates each capability module.
#
# flake.nix builds `checks.<system>.module-<name>` for every entry in the
# registry (nix/modules/default.nix) so a module cannot ship without its check.
# The generator's default instantiation is the plain name string — the same
# thing a consumer writes for a module that needs no configuration.
#
# A module whose options are MANDATORY cannot be instantiated that way: the
# bare name throws by design. This file is the generator's answer — a name ->
# `modules` entry override, consulted only for the names present here.
#
# Keep this small and keep it justified. An entry here is a statement that the
# module's zero-option form is deliberately unusable, not that the check was
# inconvenient to write.
{
  # `rust` refuses the bare form so nobody wires a toolchain without the check
  # suite (#1427; the reasoning is in the module header). The smoke check is
  # exactly the sanctioned toolchain-only case: it builds the devshell to prove
  # the module evaluates and its packages resolve, and owns no source tree to
  # run checks against. The deeper end-to-end coverage lives in
  # tests/test_flake_modules.py.
  rust = {
    name = "rust";
    checks = "none";
  };
}
