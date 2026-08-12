# mkRustProject — the composed entry point for a Rust consumer (#1400,
# decision in #1427).
#
# ---------------------------------------------------------------------------
# WHY THIS IS A LIB FUNCTION AND NOT PART OF THE MODULE CONTRACT
# ---------------------------------------------------------------------------
# A capability module contributes `packages` / `env` / `shellHook`: three
# fields that fold monoidally into ONE derivation, the dev shell. `checks` is
# not that shape. It is a namespaced map of independent peer derivations on a
# different lifecycle (`nix flake check`, not `nix develop`), and building them
# needs the consumer's source tree — project shape a module never sees.
#
# The test that settled it: a `checks` field could be added to the shell
# composition contract WITHOUT touching shell composition at all. If a field
# can be added to a contract without touching what that contract composes, it
# is not part of that contract.
#
# So the module stays v1 and this function composes above it. Crucially it is
# ONE call: it builds the dev shell (by calling mkProjectShell with the rust
# module wired for us) AND the checks AND the packages, and hands all three
# back together. There is no second function a consumer can forget to call,
# which was the whole objection to shipping the checks separately.
#
# The consumer still has to assign the outputs — flake outputs are
# consumer-assigned by construction, and no contract change anywhere in devkit
# could alter that. What this shape buys is that `checks` arrives sitting
# beside `devShell` in one attrset, so dropping it is a visible omission
# rather than an unknown-unknown. The rust module's mandatory `checks` option
# closes the remaining hand-edited path with an eval-time refusal.
#
# Usage:
#
#   perSystem = { system, pkgs, ... }:
#     let
#       rust = inputs.devkit.lib.mkRustProject {
#         inherit pkgs;
#         src = ./.;
#         toolchainHash = "sha256-…";   # for ./rust-toolchain.toml
#         crates = [ "my-cli" ];
#       };
#     in
#     {
#       devShells.default = rust.devShell;
#       checks = rust.checks;
#       packages = rust.packages;
#     };
{
  mkProjectShell,
  crane,
  fenix,
}:

{
  pkgs,
  src,

  # ---- what to build -------------------------------------------------------
  # Cargo package names to build as both `packages.<name>` and
  # `checks.<name>`. Null builds the workspace default as `packages.default`.
  # Named crates are preferred for a workspace: each one is its own derivation,
  # so a break is attributed rather than reported against "the workspace".
  crates ? null,
  # Which of `crates` becomes `packages.default`. Null uses the first.
  defaultCrate ? null,
  # Package name -> attrs merged into that crate's buildPackage call. The
  # escape hatch for per-crate `doCheck`, features, or build commands.
  crateOverrides ? { },

  # ---- toolchain -----------------------------------------------------------
  # A complete Rust toolchain derivation, if you are building one yourself.
  toolchain ? null,
  # Path to a rust-toolchain.toml. Defaults to `${src}/rust-toolchain.toml`
  # when that file exists.
  toolchainFile ? null,
  # fenix requires a content hash for the resolved toolchain. There is no way
  # around it and no sensible default — see the error below for how to get it.
  toolchainHash ? null,

  # ---- source --------------------------------------------------------------
  # Extra files the build needs that crane's cargo-source filter drops:
  # fixtures, .json goldens, templates. Paths relative to `src` (strings) or
  # absolute paths. The well-known tool configs are picked up automatically —
  # see wellKnownConfigFiles below, and read the comment there before assuming
  # you do not need this.
  extraSrcFiles ? [ ],

  # ---- build inputs --------------------------------------------------------
  nativeBuildInputs ? [ ],
  buildInputs ? [ ],
  # Merged into every crane derivation. For CMAKE_*, PKG_CONFIG_PATH, etc.
  buildEnv ? { },

  # ---- behaviour -----------------------------------------------------------
  # Build shipped binaries with `cargo auditable`, embedding the dependency
  # graph in the artifact so a consumer can audit what they actually hold
  # rather than a source tree that has since moved on. Costs one extra tool in
  # the build closure.
  auditable ? true,
  # `cargo deny check`. Defaults on when a deny.toml exists.
  deny ? null,
  # `cargo doc` with warnings denied — catches broken intra-doc links, which
  # nothing else in the suite does.
  doc ? true,
  # `cargo nextest run`. Process-per-test, so an aborting test is reported.
  nextest ? true,
  clippy ? true,
  # Extra args for the clippy check. `--deny warnings` is already applied.
  clippyExtraArgs ? "--all-targets",
  fmt ? true,

  # ---- dev shell -----------------------------------------------------------
  # Cargo tooling on the shell PATH (the rust module's curated map).
  tools ? null,
  linker ? true,
  # Additional capability modules, composed alongside `rust`.
  modules ? [ ],
  extraPackages ? [ ],
  hooks ? null,
  hooksExcludes ? [ ],
  workflow ? "gitflow",
  shellHook ? null,
  # Extra dev-shell environment. Distinct from `buildEnv`, which goes to the
  # build derivations.
  shellEnv ? { },
}:

let
  inherit (pkgs) lib;
  system = pkgs.stdenv.hostPlatform.system;

  # ---------------------------------------------------------------------------
  # Toolchain resolution
  # ---------------------------------------------------------------------------
  defaultToolchainFile = src + "/rust-toolchain.toml";
  resolvedToolchainFile =
    if toolchainFile != null then
      toolchainFile
    else if builtins.pathExists defaultToolchainFile then
      defaultToolchainFile
    else
      null;

  hashError = ''
    mkRustProject: a rust-toolchain.toml was found at

        ${toString resolvedToolchainFile}

    but `toolchainHash` was not set. fenix resolves the toolchain from that
    file as a fixed-output derivation, which needs its content hash; there is
    no default that could be correct.

    To get it, set the placeholder and build once:

        toolchainHash = pkgs.lib.fakeHash;

    Nix will fail with `specified: sha256-AAAA…` / `got: sha256-<real>`. Use
    the `got` value. It changes when you change the pinned channel or the
    component list in rust-toolchain.toml, and the same failure will tell you.

    Not honouring the file is deliberately not an option here: a repo that
    pins a toolchain and then builds with a different one is worse than a repo
    that pins nothing. If you truly want the nixpkgs Rust, pass
    `toolchainFile = null` explicitly.
  '';

  resolvedToolchain =
    if toolchain != null then
      toolchain
    else if resolvedToolchainFile == null then
      null
    else if toolchainHash == null then
      throw hashError
    else
      fenix.packages.${system}.fromToolchainFile {
        file = resolvedToolchainFile;
        sha256 = toolchainHash;
      };

  # `overrideToolchain` takes a FUNCTION, not a bare derivation. The function
  # form is what lets crane splice correctly when cross-compiling; passing the
  # derivation directly works until the day someone cross-compiles, and then
  # fails somewhere far from here.
  craneLib =
    if resolvedToolchain == null then
      crane.mkLib pkgs
    else
      (crane.mkLib pkgs).overrideToolchain (_: resolvedToolchain);

  # ---------------------------------------------------------------------------
  # Source
  #
  # crane's `commonCargoSources` walks the crate directories and allowlists
  # Cargo.{toml,lock}, *.rs and *.toml. Root-level TOOL CONFIGS are outside
  # that walk, and their absence is SILENT: rustfmt, clippy and cargo-deny
  # each fall back to built-in defaults inside the sandbox, so the check
  # passes while enforcing rules nobody wrote. The first consumer shipped that
  # bug twice — a deny.toml banning openssl that banned nothing, and a
  # clippy.toml that was never read by the clippy check meant to enforce it.
  #
  # Including these unconditionally is the fix. `maybeMissing` makes each one
  # a no-op until the file exists, so there is nothing to remember and nothing
  # to keep in sync.
  # ---------------------------------------------------------------------------
  wellKnownConfigFiles = [
    "rustfmt.toml"
    ".rustfmt.toml"
    "clippy.toml"
    ".clippy.toml"
    "deny.toml"
    "about.toml"
    "about.hbs"
    "rust-toolchain.toml"
    "rust-toolchain"
    ".cargo"
  ];

  toSrcPath = f: if builtins.isPath f then f else src + "/${f}";

  cleanSrc = lib.fileset.toSource {
    root = src;
    fileset = lib.fileset.unions (
      [ (craneLib.fileset.commonCargoSources src) ]
      ++ map (f: lib.fileset.maybeMissing (src + "/${f}")) wellKnownConfigFiles
      ++ map (f: lib.fileset.maybeMissing (toSrcPath f)) extraSrcFiles
    );
  };

  denyEnabled = if deny != null then deny else builtins.pathExists (src + "/deny.toml");

  # ---------------------------------------------------------------------------
  # Build
  # ---------------------------------------------------------------------------
  useMold = linker && pkgs.stdenv.hostPlatform.isLinux;

  commonArgs = {
    src = cleanSrc;
    # Keeps host and target dependencies from leaking into each other. On by
    # default because the failure it prevents (a build that works only on the
    # machine that has the library installed) is invisible until it isn't.
    strictDeps = true;
    nativeBuildInputs = nativeBuildInputs ++ lib.optional useMold pkgs.mold;
    buildInputs = buildInputs ++ lib.optionals pkgs.stdenv.hostPlatform.isDarwin [ pkgs.libiconv ];
    # cargo's release profile is expected to set `strip = true` (the pack's
    # Cargo.toml policy). Stripping twice is wasted work, not extra safety.
    dontStrip = true;
  }
  // buildEnv;

  cargoArtifacts = craneLib.buildDepsOnly commonArgs;

  buildCrate =
    name:
    craneLib.buildPackage (
      commonArgs
      // {
        inherit cargoArtifacts;
        pname = name;
        cargoExtraArgs = "-p ${name}";
      }
      // lib.optionalAttrs auditable {
        nativeBuildInputs = commonArgs.nativeBuildInputs ++ [ pkgs.cargo-auditable ];
        cargoBuildCommand = "cargo auditable build --profile release";
      }
      // (crateOverrides.${name} or { })
    );

  workspacePackage = craneLib.buildPackage (
    commonArgs
    // {
      inherit cargoArtifacts;
    }
    // lib.optionalAttrs auditable {
      nativeBuildInputs = commonArgs.nativeBuildInputs ++ [ pkgs.cargo-auditable ];
      cargoBuildCommand = "cargo auditable build --profile release";
    }
    // (crateOverrides.default or { })
  );

  cratePackages = lib.genAttrs (if crates == null then [ ] else crates) buildCrate;

  resolvedDefault =
    if crates == null then
      workspacePackage
    else if defaultCrate != null then
      cratePackages.${defaultCrate} or (throw (
        "mkRustProject: defaultCrate '${defaultCrate}' is not in `crates` "
        + "(${lib.concatStringsSep ", " crates})"
      ))
    else if crates == [ ] then
      throw "mkRustProject: `crates` is an empty list; pass null to build the workspace default, or name at least one crate"
    else
      cratePackages.${builtins.head crates};

  packages = cratePackages // {
    default = resolvedDefault;
  };

  # ---------------------------------------------------------------------------
  # Checks
  #
  # The crate builds are checks too. A `nix flake check` that lints but never
  # compiles the thing being shipped is the failure this pack exists to
  # prevent, so the packages are folded in rather than left to `nix build`.
  # ---------------------------------------------------------------------------
  checks =
    cratePackages
    // lib.optionalAttrs (crates == null) { workspace = workspacePackage; }
    // lib.optionalAttrs clippy {
      clippy = craneLib.cargoClippy (
        commonArgs
        // {
          inherit cargoArtifacts;
          cargoClippyExtraArgs = "${clippyExtraArgs} -- --deny warnings";
        }
      );
    }
    // lib.optionalAttrs fmt {
      # cargoFmt takes only `src` — it does not compile, so handing it
      # cargoArtifacts would just pin an unrelated dependency build.
      fmt = craneLib.cargoFmt { src = cleanSrc; };
    }
    // lib.optionalAttrs nextest {
      nextest = craneLib.cargoNextest (
        commonArgs
        // {
          inherit cargoArtifacts;
          partitions = 1;
          partitionType = "count";
        }
      );
    }
    // lib.optionalAttrs doc {
      doc = craneLib.cargoDoc (
        commonArgs
        // {
          inherit cargoArtifacts;
          env = (commonArgs.env or { }) // {
            RUSTDOCFLAGS = "--deny warnings";
          };
        }
      );
    }
    // lib.optionalAttrs denyEnabled {
      # No separate cargo-audit check: `cargo deny check advisories` already
      # scans the RustSec database, so a second derivation would be a
      # duplicate build for the same signal.
      deny = craneLib.cargoDeny { src = cleanSrc; };
    };

  # ---------------------------------------------------------------------------
  # Dev shell — the rust module, wired with the toolchain we just resolved so
  # the shell and the builds cannot disagree about the compiler version.
  # `checks = "mkRustProject"` is the module's acknowledgement token: it is
  # true here, and it is exactly what a hand-wired consumer cannot honestly
  # claim.
  # ---------------------------------------------------------------------------
  rustModuleEntry = {
    name = "rust";
    checks = "mkRustProject";
    toolchain = resolvedToolchain;
    inherit tools linker;
  };

  devShell = mkProjectShell (
    {
      inherit
        pkgs
        extraPackages
        hooks
        hooksExcludes
        workflow
        ;
      modules = [ rustModuleEntry ] ++ modules;
    }
    // lib.optionalAttrs (shellHook != null) { inherit shellHook; }
  );

  # mkProjectShell owns the shell derivation, so extra env is applied here
  # rather than threaded through it — one override, no new argument on a
  # contract shared with every non-Rust consumer.
  devShellWithEnv = if shellEnv == { } then devShell else devShell.overrideAttrs (_: shellEnv);
in
{
  inherit packages checks;
  devShell = devShellWithEnv;

  # Escape hatches for consumers doing something the arguments above do not
  # cover — an extra crane derivation, a second toolchain, a bespoke check.
  # Exposed deliberately: without them the first unanticipated need forks the
  # whole function.
  inherit craneLib cargoArtifacts commonArgs;
  toolchain = resolvedToolchain;
  src = cleanSrc;
}
