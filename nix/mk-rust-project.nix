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
  # `cargo test --doc`. nextest cannot run doctests (its process-per-test model
  # has nowhere to put them) and the `doc` check only lints rustdoc, so without
  # this nothing executes them — and a consumer whose doctests ran under
  # `cargo test` loses them on adoption, silently. #1400's stage table assigns
  # both to pre-push for exactly that reason.
  doctest ? true,

  # ---- cargo invocation ----------------------------------------------------
  # Appended to the cargo command line of EVERY derivation: the dependency
  # build, the checks and the packages. This is where features live —
  # `--all-features`, `--features a,b`, `--no-default-features`.
  #
  # It matters that this is one argument reaching all of them rather than a
  # per-check knob. A default-features build means the gated code is never
  # compiled, so clippy never sees it and its tests never run, and the suite
  # reports success over the gap. `clippyExtraArgs` covers clippy alone and is
  # deliberately left as-is: it carries lint flags, not feature selection.
  cargoExtraArgs ? "",

  # ---- performance ratchet -------------------------------------------------
  # Defaults on when the baseline file exists, off otherwise — same rule as
  # `deny`, so adopting it is `just perf-seal` and adopting nothing is doing
  # nothing. See the long comment at the ratchet itself for what it measures
  # and, more importantly, what it refuses to measure.
  perfRatchet ? null,
  perfBaselineFile ? null,
  # Growth beyond this fails. Overridable per repo in the baseline file.
  perfTolerancePct ? 5,

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
  # Consumer guards (#1450)
  #
  # Both replace a failure that was opaque, partial, or both. They follow the
  # toolchainHash error's shape deliberately: say what happened, say why there
  # is no default that could be right, and give the exact line to add.
  # ---------------------------------------------------------------------------

  # mkProjectShell pulls nix/devtools.nix, which references `vig-utils` — a
  # package only devkit's overlay provides. Without it the shell died on
  # `undefined variable 'vig-utils'`: an error inside devkit, naming something
  # the consumer has never seen, from a file they did not open.
  #
  # Checked lazily, on the dev shell alone. `checks` and `packages` never touch
  # mkProjectShell and are perfectly usable against a plain nixpkgs, so an
  # eager throw would break a working configuration to improve a message.
  overlayError = ''
    mkRustProject: the `pkgs` you passed does not carry devkit's overlay.

    The dev shell is built by mkProjectShell, whose toolchain list
    (nix/devtools.nix) resolves `vig-utils` and the fast-movers from
    `devkit.overlays.default`. Without the overlay this fails deep inside
    devkit on a name that means nothing at your call site.

    Build your pkgs with it:

        pkgs = import nixpkgs {
          inherit system;
          overlays = [ devkit.overlays.default ];
        };

    Note that `checks` and `packages` do NOT need the overlay — they never go
    through mkProjectShell. That asymmetry is why this is a thrown error and
    not a note in the docs: without it, a repo can have a green
    `nix flake check` and a dev shell that has never once evaluated.
  '';

  hasOverlay = pkgs ? vig-utils;

  # A flake's `src` is the git tree, so a repo that gitignores its lockfile
  # hands crane a source without one. crane's own message is good, but it is
  # only reachable from the derivations that vendor — `cargoFmt` takes `src`
  # alone and passed regardless, which made a total failure look partial.
  lockError = ''
    mkRustProject: no Cargo.lock at

        ${toString src}

    Every check here builds from the FLAKE's source, which is your git tree —
    so a lockfile that is untracked or gitignored does not exist as far as the
    build is concerned, however plainly it sits in your working directory.

    Library crates hit this most: not committing Cargo.lock was the convention
    for years, and `cargo new --lib` wrote that .gitignore for you. Current
    Cargo guidance is to commit it for libraries too, and a pinned build needs
    it regardless, so the fix is:

        git add Cargo.lock        # remove it from .gitignore first

    Staging alone (`git add -N`) is enough for Nix to see it, but a lockfile
    that is never committed makes the build reproducible only on your machine.
  '';

  hasLock = builtins.pathExists (src + "/Cargo.lock");

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

  # The lock guard sits here rather than on the derivations that vendor, so
  # that `fmt` — which consumes only this — fails with the rest instead of
  # passing alone (#1450).
  cleanSrc =
    if !hasLock then
      throw lockError
    else
      lib.fileset.toSource {
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
  // lib.optionalAttrs (cargoExtraArgs != "") { inherit cargoExtraArgs; }
  # Still last, so an escape-hatch override beats everything above it. Note
  # that it is a raw commonArgs merge, not an env-var attrset — the name is
  # historical.
  // buildEnv;

  cargoArtifacts = craneLib.buildDepsOnly commonArgs;

  # crane's buildPackage runs `cargo test` as part of the build. With the
  # nextest check enabled that is the same suite twice, on two derivations,
  # for one signal — so the package builds compile only and the test run lives
  # in `checks.nextest`, which is also what CI invokes. Without nextest the
  # build keeps its tests, because otherwise nothing would run them.
  packageDefaults = lib.optionalAttrs nextest { doCheck = false; };

  buildCrate =
    name:
    craneLib.buildPackage (
      commonArgs
      // packageDefaults
      // {
        inherit cargoArtifacts;
        pname = name;
        # Composed, not assigned: `cargoExtraArgs` is also where a consumer's
        # feature selection lives, and overwriting it here would silently give
        # a workspace's per-crate builds a different feature set from every
        # check that ran against them (#1450).
        cargoExtraArgs = lib.concatStringsSep " " (
          lib.optional (cargoExtraArgs != "") cargoExtraArgs ++ [ "-p ${name}" ]
        );
      }
      // lib.optionalAttrs auditable {
        nativeBuildInputs = commonArgs.nativeBuildInputs ++ [ pkgs.cargo-auditable ];
        cargoBuildCommand = "cargo auditable build --profile release";
      }
      // (crateOverrides.${name} or { })
    );

  workspacePackage = craneLib.buildPackage (
    commonArgs
    // packageDefaults
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

  # Exposed unconditionally, including before a baseline exists — sealing the
  # first one is how you adopt the ratchet, so it must work when it is off.
  perfPackages = {
    perf-seal = perfSeal;
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
    // lib.optionalAttrs doctest {
      # nextest cannot run doctests — its process-per-test model has nowhere
      # to put them — and `doc` below only lints rustdoc. Without this the
      # suite looks complete while executing none of the examples in the
      # public API docs, which for a library is often the only place a usage
      # path is exercised end to end.
      doctest = craneLib.cargoDocTest (
        commonArgs
        // {
          inherit cargoArtifacts;
        }
      );
    }
    // lib.optionalAttrs doc {
      doc = craneLib.cargoDoc (
        commonArgs
        // {
          inherit cargoArtifacts;
          # Top-level rather than under `env`, so a consumer's `buildEnv`
          # cannot collide with it through two different mechanisms.
          RUSTDOCFLAGS = "--deny warnings";
        }
      );
    }
    // lib.optionalAttrs denyEnabled {
      # No separate cargo-audit check: `cargo deny check advisories` already
      # scans the RustSec database, so a second derivation would be a
      # duplicate build for the same signal.
      deny = craneLib.cargoDeny { src = cleanSrc; };
    }
    // lib.optionalAttrs perfEnabled { perf-ratchet = perfRatchetCheck; };

  # ---------------------------------------------------------------------------
  # Performance ratchet
  #
  # WHAT THIS DELIBERATELY DOES NOT DO: time anything. Wall-clock benchmarks
  # on shared CI runners are noise — neighbours, thermal state and scheduler
  # luck move them more than most real regressions do — and a gate that fires
  # on noise is a gate people learn to re-run until it passes. The pack ADR
  # already says coverage is reported and never gated; the same reasoning
  # applies harder here, because a flaky perf gate teaches `--no-verify`.
  #
  # What it measures instead is deterministic given a locked toolchain and a
  # locked dependency graph, so a change means a change:
  #
  #   * SHIPPED BINARY SIZE, per binary. Catches the dependency that quietly
  #     added two megabytes, the accidental monomorphization blowup, the
  #     debug info that stopped being stripped.
  #   * DEPENDENCY GRAPH SIZE, from Cargo.lock. Catches supply-chain creep,
  #     which is a build-time, audit-surface and compile-time cost at once.
  #
  # Neither needs anyone to have written a benchmark, which is the point: a
  # ratchet nobody has to author is a ratchet that is actually in place. Repos
  # doing real performance work should add criterion/divan benches and run
  # them OFF the CI critical path — `tools = [ "@perf" ]` puts the kit on
  # PATH for that.
  #
  # It is a RATCHET, not a limit: growth past the tolerance fails, and a
  # measured shrink is reported so the win can be banked by re-sealing. The
  # baseline is committed, so the diff shows who spent the budget and when.
  # ---------------------------------------------------------------------------
  resolvedBaselineFile =
    if perfBaselineFile != null then perfBaselineFile else src + "/.repo/perf-baseline.toml";
  baselineExists = builtins.pathExists resolvedBaselineFile;
  perfEnabled = if perfRatchet != null then perfRatchet else baselineExists;

  baseline =
    if baselineExists then builtins.fromTOML (builtins.readFile resolvedBaselineFile) else { };
  tolerance = baseline.tolerance_pct or perfTolerancePct;

  # Cargo.lock is TOML, so the graph size is an eval-time read — no build, no
  # network, no cargo invocation.
  cargoLockFile = src + "/Cargo.lock";
  lockCrateCount =
    if builtins.pathExists cargoLockFile then
      builtins.length ((builtins.fromTOML (builtins.readFile cargoLockFile)).package or [ ])
    else
      null;

  baselineBinaries = baseline.binaries or { };
  baselineLines = lib.concatStringsSep "\n" (
    lib.mapAttrsToList (n: v: "${n} ${toString v.bytes}") baselineBinaries
  );

  measuredPackages = if crates == null then { workspace = workspacePackage; } else cratePackages;

  perfRatchetCheck = pkgs.runCommand "rust-perf-ratchet" { } ''
    set -euo pipefail
    printf '%s\n' ${lib.escapeShellArg baselineLines} > baseline.txt
    tolerance=${toString tolerance}
    status=0
    echo "perf ratchet — tolerance ${toString tolerance}%"
    echo

    check_metric() {
      name="$1"; actual="$2"; expected="$3"; unit="$4"
      if [ -z "$expected" ]; then
        echo "  NEW      $name = $actual $unit (no baseline entry)"
        echo "$name = $actual" >> new-entries.txt
        return
      fi
      # Integer percent-delta; avoids depending on bc/awk floats.
      delta=$(( (actual - expected) * 100 / (expected > 0 ? expected : 1) ))
      if [ "$delta" -gt "$tolerance" ]; then
        echo "  REGRESS  $name = $actual $unit (baseline $expected, +''${delta}%)"
        status=1
      elif [ "$delta" -lt "-$tolerance" ]; then
        echo "  IMPROVED $name = $actual $unit (baseline $expected, ''${delta}%) — re-seal to bank it"
      else
        echo "  ok       $name = $actual $unit (baseline $expected, ''${delta}%)"
      fi
    }

    ${lib.concatStringsSep "\n" (
      lib.mapAttrsToList (_: drv: ''
        if [ -d ${drv}/bin ]; then
          for f in ${drv}/bin/*; do
            [ -f "$f" ] || continue
            bin=$(basename "$f")
            actual=$(wc -c < "$f" | tr -d ' ')
            expected=$(awk -v k="$bin" '$1 == k { print $2 }' baseline.txt)
            check_metric "binary/$bin" "$actual" "$expected" bytes
          done
        fi
      '') measuredPackages
    )}

    ${lib.optionalString (lockCrateCount != null) ''
      check_metric "graph/crates" ${toString lockCrateCount} \
        ${toString (baseline.graph.crates or "")} crates
    ''}

    echo
    if [ "$status" -ne 0 ]; then
      cat <<'MSG'
    A measured budget was exceeded.

    This is deterministic, not a flaky timing check: same toolchain, same
    Cargo.lock, same bytes. Something in this change actually made the
    artifact bigger or the graph wider.

      cargo bloat --release --crates     # which dependency took the bytes
      cargo llvm-lines --release         # which generic exploded
      cargo tree --duplicates            # two versions of the same crate

    If the growth is intended — a real feature, a dependency you chose —
    re-seal the baseline in the same commit, so the diff records who spent
    the budget and why:

      just perf-seal
    MSG
    fi
    ${lib.optionalString (!baselineExists) ''
      echo "No baseline at ${toString resolvedBaselineFile} — reporting only."
      echo "Seal one with \`just perf-seal\` to start ratcheting."
      status=0
    ''}
    [ "$status" -eq 0 ] || exit 1
    touch $out
  '';

  # `nix run .#perf-seal > .repo/perf-baseline.toml` — emits the current
  # measurements as the file itself, so sealing is never hand-transcribed.
  perfSeal = pkgs.writeShellScriptBin "perf-seal" ''
    set -euo pipefail
    echo "schema = 1"
    echo "tolerance_pct = ${toString tolerance}"
    echo
    ${lib.optionalString (lockCrateCount != null) ''
      echo "[graph]"
      echo "crates = ${toString lockCrateCount}"
      echo
    ''}
    echo "[binaries]"
    ${lib.concatStringsSep "\n" (
      lib.mapAttrsToList (_: drv: ''
        if [ -d ${drv}/bin ]; then
          for f in ${drv}/bin/*; do
            [ -f "$f" ] || continue
            printf '%s = { bytes = %s }\n' "$(basename "$f")" "$(wc -c < "$f" | tr -d ' ')"
          done
        fi
      '') measuredPackages
    )}
  '';

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

  devShell =
    if !hasOverlay then
      throw overlayError
    else
      mkProjectShell (
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
  inherit checks;
  packages = packages // perfPackages;
  devShell = devShellWithEnv;

  # Escape hatches for consumers doing something the arguments above do not
  # cover — an extra crane derivation, a second toolchain, a bespoke check.
  # Exposed deliberately: without them the first unanticipated need forks the
  # whole function.
  inherit craneLib cargoArtifacts commonArgs;
  toolchain = resolvedToolchain;
  src = cleanSrc;
}
