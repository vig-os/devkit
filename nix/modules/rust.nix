# `rust` capability module (#1400, decision in #1427): the Rust dev-shell
# capability. One of the ADR's ask-gated candidates; `gerchowl/filesender` is
# the ask.
#
# v1 contract (`pkgs -> options -> { packages, env, shellHook }`, per
# docs/rfcs/ADR-capability-modules.md) — this module contributes packages and
# env only. It deliberately does NOT provide the cargo justfile recipes, the
# .gitignore fragment, the pre-commit hooks or the CodeQL language: those are
# scaffold concerns, not shell contributions, exactly as for `node`.
#
# ---------------------------------------------------------------------------
# WHY THIS MODULE REFUSES TO LOAD BARE
# ---------------------------------------------------------------------------
# A Rust toolchain on PATH is the *easy* half of the capability. The half that
# earns its keep is the check suite — fmt, clippy, nextest, cargo-deny, the
# per-crate builds — and a v1 capability module cannot contribute
# `checks.<system>.*`. Checks need the project's source tree, which is
# consumer-owned project shape, neither ambient here nor derivable from
# options.
#
# So a consumer who writes `modules = [ "rust" ]` and stops would get a
# toolchain, a green `nix flake check` that builds nothing, and CI that
# compiles nothing — the precise silent-green failure the Rust pack exists to
# prevent, delivered by the pack itself. #1427 settled that the fix is
# `lib.mkRustProject` (which wires shell AND checks from one call) plus this
# eval-time refusal for anyone who hand-edits their way around it. Detection
# is not enough here: the record on the first consumer is five separate
# things configured, believed active, and never executed.
#
# Hence the mandatory `checks` option. It has no default on purpose.
pkgs:
{
  checks ? null,
  toolchain ? null,
  tools ? null,
  linker ? true,
  ...
}@options:
let
  inherit (pkgs) lib;

  knownOptions = [
    "checks"
    "toolchain"
    "tools"
    "linker"
  ];
  unknownOptions = builtins.filter (k: !builtins.elem k knownOptions) (builtins.attrNames options);

  # -------------------------------------------------------------------------
  # Curated cargo tooling. A name -> package map rather than free-form
  # derivations so `tools` stays a reviewable list in a consumer's flake and a
  # typo is an eval error, not a silently missing binary.
  # -------------------------------------------------------------------------
  toolMap = {
    # Test runner. Not a nicety: nextest is process-per-test, so a panicking
    # or aborting test is reported rather than taking the runner with it.
    nextest = pkgs.cargo-nextest or null;
    # Supply chain: advisories, licence policy, source bans (deny.toml).
    deny = pkgs.cargo-deny or null;
    # Embeds the dependency graph in the SHIPPED binary, so `cargo audit bin`
    # audits the artifact rather than a source tree that may have moved on.
    auditable = pkgs.cargo-auditable or null;
    audit = pkgs.cargo-audit or null;
    # Third-party attribution text. deny.toml says which licences are allowed;
    # this produces the notice the permissive ones oblige us to distribute.
    about = pkgs.cargo-about or null;
    # Unused dependency detection — the one cargo itself will not tell you.
    shear = pkgs.cargo-shear or null;
    # Coverage. Reported, never gated (see the pack ADR).
    llvm-cov = pkgs.cargo-llvm-cov or null;
    watch = pkgs.cargo-watch or null;
    expand = pkgs.cargo-expand or null;
    machete = pkgs.cargo-machete or null;
    outdated = pkgs.cargo-outdated or null;
    insta = pkgs.cargo-insta or null;
    flamegraph = pkgs.cargo-flamegraph or null;
    criterion = pkgs.cargo-criterion or null;
    mutants = pkgs.cargo-mutants or null;
    semver-checks = pkgs.cargo-semver-checks or null;
    hakari = pkgs.cargo-hakari or null;
    dist = pkgs.cargo-dist or null;
  };

  # The default set is what every tier in the pack ADR needs: run the tests,
  # police the supply chain, produce the attribution file, notice dead deps.
  # Anything tier-specific (semver-checks for `lib`, mutants for `runner`) is
  # opt-in via `tools`, because each one costs build time for every consumer.
  defaultTools = [
    "nextest"
    "deny"
    "auditable"
    "audit"
    "about"
    "shear"
  ];

  requestedTools = if tools == null then defaultTools else tools;

  unknownTools = builtins.filter (t: !(toolMap ? ${t}) || toolMap.${t} == null) requestedTools;

  toolPackages = map (t: toolMap.${t}) requestedTools;

  # -------------------------------------------------------------------------
  # Toolchain. `toolchain` is a complete Rust toolchain derivation — in
  # practice fenix's `fromToolchainFile`, which is what lib.mkRustProject
  # passes so `rust-toolchain.toml` is the single source of truth for the
  # version. Omitted, we fall back to the pinned nixpkgs Rust: a real
  # toolchain, but one that tracks the channel rather than the repo's pin.
  # -------------------------------------------------------------------------
  toolchainPackages =
    if toolchain != null then
      [ toolchain ]
    else
      [
        pkgs.rustc
        pkgs.cargo
        pkgs.clippy
        pkgs.rustfmt
        pkgs.rust-analyzer
      ];

  # mold cuts link time on large debug builds by an order of magnitude, and
  # link time is what a Rust edit-compile loop is actually made of. Linux
  # only: on Darwin the system linker is already the fast path and mold's
  # Mach-O support is not the supported configuration.
  useMold = linker && pkgs.stdenv.hostPlatform.isLinux;

  # `checks` is mandatory and has no default — see the header. The message is
  # the whole point of the guard, so it states the fix, the escape hatch, and
  # why the escape hatch is not the default.
  checksError = ''
    rust module: the `checks` option is required.

    `modules = [ "rust" ]` puts a Rust toolchain on the dev-shell PATH and
    NOTHING ELSE. It cannot add `checks.<system>.*` — a v1 capability module
    contributes packages/env/shellHook only, and checks need your source tree,
    which the module never sees. A repo wired this way compiles nothing in CI
    and reports success. Refs vig-os/devkit#1427.

    Use the composed entry point instead, which wires the shell AND the checks
    from one call:

        rust = inputs.devkit.lib.mkRustProject {
          inherit pkgs;
          src = ./.;
        };
      in {
        devShells.default = rust.devShell;
        checks.''${system}  = rust.checks;
        packages.''${system} = rust.packages;
      }

    If you genuinely want the toolchain WITHOUT the check suite — a scratch
    shell, a repo whose Rust is incidental, a consumer that already owns its
    own checks — say so explicitly:

        modules = [ { name = "rust"; checks = "none"; } ];

    It is spelled out rather than defaulted because the default would be the
    failure mode: silence is exactly how the unwired case reaches CI.
  '';

  validChecks = [
    "mkRustProject"
    "none"
  ];
in
if unknownOptions != [ ] then
  throw (
    "rust module: unknown option(s): "
    + lib.concatStringsSep ", " unknownOptions
    + "; recognized options are "
    + lib.concatStringsSep ", " knownOptions
  )
else if checks == null then
  throw checksError
else if !builtins.elem checks validChecks then
  throw (
    "rust module: invalid `checks` value "
    + builtins.toJSON checks
    + "; expected \"mkRustProject\" (set for you by lib.mkRustProject) or "
    + "\"none\" (deliberate opt-out — toolchain only, no check suite)"
  )
else if unknownTools != [ ] then
  throw (
    "rust module: unknown or unavailable tool(s): "
    + lib.concatStringsSep ", " unknownTools
    + "; available: "
    + lib.concatStringsSep ", " (builtins.filter (n: toolMap.${n} != null) (builtins.attrNames toolMap))
  )
else
  {
    packages = toolchainPackages ++ toolPackages ++ lib.optional useMold pkgs.mold;

    env = {
      # Point rust-analyzer and friends at the toolchain's own sources. Without
      # it, "go to definition" on a std symbol lands nowhere in a Nix shell,
      # because there is no rustup to infer the sysroot from.
      RUST_SRC_PATH =
        if toolchain != null then
          "${toolchain}/lib/rustlib/src/rust/library"
        else
          "${pkgs.rustPlatform.rustLibSrc}";
      # Full backtraces by default in a dev shell. This is the environment
      # where you are debugging; the cost of the flag is zero unless you panic.
      RUST_BACKTRACE = "1";
    };

    # The toolchain SSoT (nix/devtools.nix) does not ship Rust, so unlike the
    # node module there is nothing to shadow — the package contribution above
    # already wins PATH. This fragment exists only for mold, which cannot be
    # selected by PATH order: it has to be requested through rustflags.
    #
    # Deliberately additive to RUSTFLAGS rather than assigning it, so a repo's
    # own .cargo/config.toml or a caller's export is not silently discarded.
    shellHook = lib.optionalString useMold ''
      export RUSTFLAGS="''${RUSTFLAGS:+$RUSTFLAGS }-C link-arg=-fuse-ld=mold"
    '';
  }
