# `guardrails` capability module (#1488): the semantic-gate capability.
#
# devkit ships 26 hooks to consumers and every one of them is syntactic —
# formatting, whitespace, YAML/TOML validity, typos, commit-message shape.
# Useful, and not one of them can tell you the code does what it says. These
# 15 gates are the semantic half: no fake implementations, no hardcoded magic
# values, no commented-out code, generated docs still matching their source
# command, no debug prints left behind, trunk protection.
#
# ---------------------------------------------------------------------------
# WHY THIS CONTRIBUTES `packages` AND NOTHING ELSE
# ---------------------------------------------------------------------------
# A gate is only useful once a hook entry invokes it, so the obvious design is
# for this module to contribute hook entries too — which is what the ADR
# deferred ("hooks contribution … open design question") and what #1488
# originally proposed as a v2 contract field.
#
# That was wrong, and #1492 settled why. `.pre-commit-config.yaml` is read by
# the runner from a bare git working tree, by CI containers that never enter
# `nix develop`, and by humans reading a PR diff. Its whole lifecycle sits on
# the SCAFFOLD side, not the shell side. The flake CAN generate one, but every
# consumer today owns a committed file, and the generated path refuses to
# overwrite it — so flake-contributed entries would be silently discarded, or
# discarded with a warning on every shell entry. Configured, believed active,
# enforcing nothing: the exact failure these gates exist to catch, caused by
# the module shipping them.
#
# It is also closed at the tool level, independently: neither prek nor
# pre-commit has `include`/`extends` (pre-commit refused it explicitly,
# pre-commit#1203), one `repo:` stanza cannot pull a hook set, and prek's
# workspace mode scopes each sub-config to its own directory tree.
#
# So hook ENTRIES are rendered by the installer from `DEVKIT_MODULES`, and
# this module does the one thing the v1 contract already allows: it puts the
# gate executables on PATH. No contract change, no ADR amendment, no fourth
# field.
#
# And because "the entry is in the file" has never once implied "the gate
# ran" in this org's recorded history, execution is proven separately by the
# canary check (`checks.guardrails-canary`), which feeds every gate a
# known-bad fixture and asserts it rejects it.
pkgs:
{
  gates ? null,
  tools ? true,
  ...
}@options:
let
  inherit (pkgs) lib;

  knownOptions = [
    "gates"
    "tools"
  ];
  unknownOptions = builtins.filter (k: !builtins.elem k knownOptions) (builtins.attrNames options);

  guardrails = pkgs.callPackage ../guardrails.nix { };

  # The full set, derived from what is actually vendored rather than a
  # hand-kept list — a list that can disagree with the directory is one more
  # thing to drift.
  available = lib.pipe (builtins.readDir ../../assets/guardrails/gates) [
    (lib.filterAttrs (n: t: t == "regular" && lib.hasSuffix ".sh" n))
    builtins.attrNames
    (map (n: lib.removeSuffix ".sh" n))
    lib.naturalSort
  ];

  requested = if gates == null then available else gates;
  unknownGates = builtins.filter (g: !builtins.elem g available) requested;
in
if unknownOptions != [ ] then
  throw (
    "guardrails module: unknown option(s): "
    + lib.concatStringsSep ", " unknownOptions
    + "; recognized options are "
    + lib.concatStringsSep ", " knownOptions
  )
else if unknownGates != [ ] then
  throw (
    "guardrails module: unknown gate(s): "
    + lib.concatStringsSep ", " unknownGates
    + "; available: "
    + lib.concatStringsSep ", " available
  )
else
  {
    # One derivation carries every gate, so `gates` selects which are
    # SUPPORTED rather than which are built — there is nothing to save by
    # splitting 3,000 lines of shell into fifteen derivations, and a consumer
    # narrowing the list still wants a coherent `guardrails` CLI.
    packages = [ guardrails ];

    env = lib.optionalAttrs tools {
      # Where `guardrails-trace` appends its per-hook JSONL. Set here so the
      # trace lands in one place per repo rather than wherever each hook
      # happened to run from.
      GUARDRAILS_TRACE_ENABLED = "1";
    };
  }
