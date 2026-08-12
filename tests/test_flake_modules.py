"""Capability-module devshell tests (issue #884).

``mkProjectShell`` accepts an opt-in ``modules = [ "<name>" … ]`` string list
(see ``docs/rfcs/ADR-capability-modules.md``). Each shipped module is exposed
as a per-system flake check ``checks.<system>.module-<name>`` (generated from
the ``nix/modules/`` registry), which doubles as the entry point here: these
tests ``nix develop`` a module's shell and assert its contract. For ``native``
(#884): the C/C++ toolchain is on the shell's own PATH, generic ``CC``/``CXX``
are exported, and a trivial setuptools C-extension sdist builds and installs
with ``uv`` (the pycatima-class scenario from #639/#879). For ``node`` (#1027):
``node`` + bundled ``npm`` resolve, and the ``{ name = "node"; version = …; }``
per-module-options form pins the Node major (the mechanism the ADR deferred).
For ``rust`` (#1400, decision in #1427): the bare-form guard (which is the
single most important test — the whole design rests on it) fires at eval, the
explicit ``{ name = "rust"; checks = "none"; }`` opt-out evaluates, the
module's per-option validation throws with a targeted message, and
``lib.mkRustProject`` composes above the module as a callable entry point.

The zero-module parity guarantee (the default dev-shell is byte-identical to
the pre-module builder) is covered by ``tests/test_flake_devshell.py`` staying
green unchanged, not here.

The suite is skipped automatically when ``nix`` is not on PATH (mirroring the
other flake test modules) so it never breaks unrelated lanes.

Refs: #884
"""

from __future__ import annotations

import json
import shutil
import subprocess
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from . import nix_helpers
from .nix_helpers import REPO_ROOT
from .nix_helpers import nix_env as _nix_env

FIXTURE = REPO_ROOT / "tests" / "fixtures" / "native_ext"

pytestmark = pytest.mark.skipif(
    shutil.which("nix") is None,
    reason="nix is not installed; capability-module tests require Nix",
)


@pytest.fixture(scope="session")
def current_system() -> str:
    """The Nix system double for the host (e.g. x86_64-linux)."""
    return nix_helpers.current_system()


def _develop_native(
    current_system: str, script: str, *, pure: bool = True, timeout: int = 1800
) -> subprocess.CompletedProcess[str]:
    """Run a bash script inside the ``native`` module's devshell.

    With ``pure=True`` (default) it uses ``--ignore-environment`` (keeping only
    HOME) so assertions exercise the shell's *own* PATH/env contribution and
    cannot be satisfied by a host toolchain leaking through the inherited
    environment — the same guard ``test_devshell_exposes_python3_and_precommit``
    uses (#729). ``pure=False`` keeps the ambient environment for steps that
    need the host's network/TLS configuration (e.g. uv fetching a build
    backend from PyPI).
    """
    isolation = ["--ignore-environment", "--keep", "HOME"] if pure else []
    return subprocess.run(
        [
            "nix",
            "develop",
            *isolation,
            f"{REPO_ROOT}#checks.{current_system}.module-native",
            "-c",
            "bash",
            "-c",
            script,
        ],
        capture_output=True,
        text=True,
        env=_nix_env(),
        timeout=timeout,
    )


def test_native_module_provides_build_toolchain(current_system: str) -> None:
    """The ``native`` module puts the sdist-building toolchain on PATH (#884).

    ``stdenv.cc`` (cc/c++), ``cmake``, ``gnumake`` and ``pkg-config`` are the
    curated definition of the generic native-build capability — what
    scikit-build-core / setuptools / meson-python sdist builds actually invoke.
    """
    proc = _develop_native(
        current_system,
        "for bin in cc c++ cmake make pkg-config; do command -v $bin; done",
    )
    assert proc.returncode == 0, (
        "native-module devshell is missing toolchain binaries: "
        f"rc={proc.returncode} stdout={proc.stdout.strip()!r} "
        f"stderr={proc.stderr.strip()[:300]}"
    )


def test_native_module_exports_generic_cc_cxx(current_system: str) -> None:
    """The ``native`` module exports ``CC=cc`` / ``CXX=c++`` (#884).

    Generic POSIX names, not store paths: build backends that consult the
    environment resolve them via the module-provided PATH, matching the
    image-side sysconfig sanitize (#879/#893) which rewrote the baked
    interpreter's compiler records to the same generic names.
    """
    proc = _develop_native(current_system, 'printf "\\n%s:%s" "$CC" "$CXX"')
    assert proc.returncode == 0, (
        f"failed to read CC/CXX from the native-module devshell: {proc.stderr[:300]}"
    )
    # The default shellHook banner writes to stdout, so only the last line is
    # the probe's answer.
    got = proc.stdout.splitlines()[-1] if proc.stdout else ""
    assert got == "cc:c++", f"native module must export CC=cc and CXX=c++; got {got!r}"


def test_native_module_builds_c_extension_sdist_with_uv(
    current_system: str, tmp_path: Path
) -> None:
    """A trivial C-extension sdist builds and installs with uv in the shell (#884).

    End-to-end acceptance for the module: package the fixture as an sdist
    (``uv build --sdist``), then compile-install it into a fresh venv
    (``uv pip install <sdist>``) and import it — exactly the path ``uv sync``
    takes for a dependency with no ``cp314`` wheel (pycatima-class, #639/#879).
    The devshell pins ``UV_PYTHON`` to the store CPython and forbids managed
    downloads, so the compile runs against the same interpreter the consumer
    contract prescribes.
    """
    project = tmp_path / "native-ext"
    shutil.copytree(FIXTURE, project)
    script = (
        "set -euo pipefail\n"
        f"cd {project}\n"
        "uv build --sdist --out-dir dist\n"
        "uv venv .venv\n"
        "uv pip install --python .venv/bin/python dist/native_ext-0.1.0.tar.gz\n"
        '.venv/bin/python -c "import native_ext; '
        "assert native_ext.answer() == 42; print('sdist-ok')\"\n"
    )
    proc = _develop_native(current_system, script, pure=False)
    assert proc.returncode == 0 and "sdist-ok" in proc.stdout, (
        "uv sdist build/install failed inside the native-module devshell: "
        f"rc={proc.returncode}\nstdout:\n{proc.stdout}\nstderr:\n{proc.stderr[-2000:]}"
    )


# ---------------------------------------------------------------------------
# node module (#1027) — the Node/TypeScript capability. v1 contract (packages
# only): `nodejs` (which bundles npm) in the dev-shell, with a selectable major
# version via the ADR's per-module-options migration path — a `modules` entry
# may be `{ name = "node"; version = 22; }` (attrset) alongside the plain
# `"node"` string (nixpkgs default). See docs/rfcs/ADR-capability-modules.md.
# ---------------------------------------------------------------------------


def _develop_module(
    current_system: str, module: str, script: str, *, timeout: int = 1800
) -> subprocess.CompletedProcess[str]:
    """Run a bash script inside the generated ``module-<module>`` devshell.

    Purity guard (``--ignore-environment``, keeping only HOME) as in
    ``_develop_native``: the assertions must exercise the module's OWN PATH
    contribution and never be satisfied by a host toolchain leaking through.
    """
    return subprocess.run(
        [
            "nix",
            "develop",
            "--ignore-environment",
            "--keep",
            "HOME",
            f"{REPO_ROOT}#checks.{current_system}.module-{module}",
            "-c",
            "bash",
            "-c",
            script,
        ],
        capture_output=True,
        text=True,
        env=_nix_env(),
        timeout=timeout,
    )


def _develop_expr(
    expr: str, script: str, *, timeout: int = 1800
) -> subprocess.CompletedProcess[str]:
    """Run a bash script inside an ad-hoc devshell built from a Nix expression.

    Used for the versioned module form, which the registry-generated
    ``module-node`` check (plain-string default) cannot express: it builds
    ``flake.lib.mkProjectShell`` directly with an attrset ``modules`` entry.
    ``--impure`` is required for ``builtins.getFlake`` on the local path.
    """
    return subprocess.run(
        [
            "nix",
            "develop",
            "--impure",
            "--ignore-environment",
            "--keep",
            "HOME",
            "--expr",
            expr,
            "-c",
            "bash",
            "-c",
            script,
        ],
        capture_output=True,
        text=True,
        env=_nix_env(),
        timeout=timeout,
    )


def test_node_module_provides_node_and_npm(current_system: str) -> None:
    """The ``node`` module puts ``node`` and its bundled ``npm`` on PATH (#1027).

    The plain-string ``modules = [ "node" ]`` form (exercised through the
    registry-generated ``module-node`` check) contributes the nixpkgs-default
    ``nodejs``, which bundles ``npm`` — both must resolve from the shell's own
    PATH, not the host's.
    """
    proc = _develop_module(
        current_system,
        "node",
        "command -v node && command -v npm && node --version && npm --version",
    )
    assert proc.returncode == 0, (
        "node-module devshell is missing node/npm: "
        f"rc={proc.returncode} stdout={proc.stdout.strip()!r} "
        f"stderr={proc.stderr.strip()[:300]}"
    )


def test_node_module_version_option_pins_major(current_system: str) -> None:
    """``{ name = "node"; version = 22; }`` selects ``pkgs.nodejs_22`` (#1027).

    The per-module-options migration path the ADR deferred: an attrset entry
    carries a ``version`` that maps to ``pkgs.nodejs_<major>``. Build that shell
    directly (the registry check only covers the default form) and assert the
    running interpreter is the pinned major.

    A maintained LTS major (22) is used deliberately: the pinned nixpkgs marks
    EOL majors (e.g. nodejs_20) insecure, so pinning one throws unless the
    consumer opts into ``permittedInsecurePackages`` — a nixpkgs policy the
    module surfaces rather than masks (documented in docs/NIX.md).
    """
    expr = f"""
    let
      flake = builtins.getFlake "path:{REPO_ROOT}";
      system = builtins.currentSystem;
      pkgs = import flake.inputs.nixpkgs {{
        inherit system;
        overlays = [ flake.overlays.default ];
        config.allowUnfree = true;
      }};
    in flake.lib.mkProjectShell {{
      inherit pkgs;
      modules = [ {{ name = "node"; version = 22; }} ];
    }}
    """
    proc = _develop_expr(expr, "node --version")
    assert proc.returncode == 0, (
        f"failed to build/enter the versioned node devshell: {proc.stderr[-500:]}"
    )
    got = proc.stdout.strip().splitlines()[-1] if proc.stdout else ""
    assert got.startswith("v22."), (
        f"node module version=22 must run Node 22.x; got {got!r}"
    )


def test_node_module_rejects_unknown_option(current_system: str) -> None:
    """An unrecognized module option fails at eval time with a clear message (#1027).

    The options mechanism is intentionally strict: only keys the module declares
    are accepted, so a mistyped or unsupported knob (here ``channel``) is a hard
    eval error, never a silently-ignored no-op.
    """
    expr = f"""
    let
      flake = builtins.getFlake "path:{REPO_ROOT}";
      system = builtins.currentSystem;
      pkgs = import flake.inputs.nixpkgs {{
        inherit system;
        overlays = [ flake.overlays.default ];
        config.allowUnfree = true;
      }};
    in (flake.lib.mkProjectShell {{
      inherit pkgs;
      modules = [ {{ name = "node"; channel = 20; }} ];
    }}).drvPath
    """
    result = subprocess.run(
        ["nix", "eval", "--impure", "--expr", expr],
        capture_output=True,
        text=True,
        env=_nix_env(),
        timeout=300,
    )
    assert result.returncode != 0, "unknown node option must fail eval, not pass"
    assert "channel" in result.stderr and "node" in result.stderr, (
        f"error must name the offending option and module; got: {result.stderr[-500:]}"
    )


# ---------------------------------------------------------------------------
# docs module (#1178) — the document-edition capability. v1 contract (packages
# only): `typst` and `typstyle` on the dev-shell PATH so a document-oriented
# consumer (exo-pet/vault, future qms, EXOMA presentations/grants) opts in with
# `modules = [ "docs" ]` instead of a PyPI typst pin. No version option in v1 —
# nixpkgs carries a single typst per pin and the module tracks that pin. See
# docs/rfcs/ADR-capability-modules.md.
# ---------------------------------------------------------------------------


def test_docs_module_provides_typst_and_typstyle(current_system: str) -> None:
    """The ``docs`` module puts ``typst`` and ``typstyle`` on PATH (#1178).

    The plain-string ``modules = [ "docs" ]`` form (exercised through the
    registry-generated ``module-docs`` check — which is also the proof the
    registry resolves the name) contributes the nixpkgs-pinned ``typst`` and
    ``typstyle``; both must resolve from the shell's own PATH, not the host's.
    """
    proc = _develop_module(
        current_system,
        "docs",
        "command -v typst && command -v typstyle "
        "&& typst --version && typstyle --version",
    )
    assert proc.returncode == 0, (
        "docs-module devshell is missing typst/typstyle: "
        f"rc={proc.returncode} stdout={proc.stdout.strip()!r} "
        f"stderr={proc.stderr.strip()[:300]}"
    )


@pytest.mark.parametrize(
    "bad_version",
    ['"22"', "{ }"],
    ids=["string", "attrset"],
)
def test_node_module_rejects_non_int_version(
    current_system: str, bad_version: str
) -> None:
    """A non-integer ``version`` fails at eval time with a clear message (#1080).

    ``version`` must be an integer Node major. Before the ``builtins.isInt``
    guard, a non-int slipped into the ``nodejs_${toString version}``
    interpolation: a string was silently accepted and a set/path/derivation
    surfaced Nix's generic "cannot coerce to string" error instead of the
    module-scoped throw the other invalid inputs (unknown option keys,
    unavailable majors) already get.
    """
    expr = f"""
    let
      flake = builtins.getFlake "path:{REPO_ROOT}";
      system = builtins.currentSystem;
      pkgs = import flake.inputs.nixpkgs {{
        inherit system;
        overlays = [ flake.overlays.default ];
        config.allowUnfree = true;
      }};
    in (flake.lib.mkProjectShell {{
      inherit pkgs;
      modules = [ {{ name = "node"; version = {bad_version}; }} ];
    }}).drvPath
    """
    result = subprocess.run(
        ["nix", "eval", "--impure", "--expr", expr],
        capture_output=True,
        text=True,
        env=_nix_env(),
        timeout=300,
    )
    assert result.returncode != 0, "non-int node version must fail eval, not pass"
    assert (
        "invalid Node version" in result.stderr and "integer major" in result.stderr
    ), (
        f"error must be the module-scoped invalid-version throw; got: {result.stderr[-500:]}"
    )


# ---------------------------------------------------------------------------
# rust module (#1400, decision in #1427) — the Rust dev-shell capability. v1
# contract (packages + env + shellHook) with a MANDATORY ``checks`` option and
# no default: the whole point of the module is to refuse the bare
# ``modules = [ "rust" ]`` form loudly, because a v1 module cannot contribute
# ``checks.<system>.*`` and a hand-wired Rust repo with a green ``nix flake
# check`` that compiles nothing is exactly the failure the language pack
# exists to prevent. ``lib.mkRustProject`` composes above ``mkProjectShell``
# and wires shell + checks + packages from one call; the check-entries
# registry (nix/modules/check-entries.nix) is how the generated per-module
# smoke check instantiates a module whose options are mandatory. See
# docs/rfcs/ADR-capability-modules.md and nix/mk-rust-project.nix.
# ---------------------------------------------------------------------------


def _rust_module_expr(entry: str) -> str:
    """A ``mkProjectShell`` expression whose sole module entry is ``entry``.

    Shared by the guard/opt-out/option-validation tests — each one only differs
    in the attrset (or bare string) it hands to ``modules``. ``.drvPath`` forces
    evaluation to the derivation, which is the only stage where the module's
    guards fire (the shell body never runs, so throws surface as eval errors).
    """
    return f"""
    let
      flake = builtins.getFlake "path:{REPO_ROOT}";
      system = builtins.currentSystem;
      pkgs = import flake.inputs.nixpkgs {{
        inherit system;
        overlays = [ flake.overlays.default ];
        config.allowUnfree = true;
      }};
    in (flake.lib.mkProjectShell {{
      inherit pkgs;
      modules = [ {entry} ];
    }}).drvPath
    """


def _nix_eval_expr(
    expr: str, *, timeout: int = 300
) -> subprocess.CompletedProcess[str]:
    """Run ``nix eval --impure --expr`` and return the completed process.

    Used by the guard/option-validation tests, which assert on the error
    surfaced in ``stderr`` — a non-zero exit is the expected shape.
    """
    return subprocess.run(
        ["nix", "eval", "--impure", "--expr", expr],
        capture_output=True,
        text=True,
        env=_nix_env(),
        timeout=timeout,
    )


def test_rust_is_in_capability_module_registry() -> None:
    """``rust`` is one of the shipped capability modules (#1400).

    Reads the registry names via the same generated per-module check
    ``checks.<system>.module-<name>`` the other modules are asserted through —
    a check whose existence is proof the flake resolved the ``rust`` entry in
    ``nix/modules/default.nix``. Kept parallel to how ``native``/``node``/
    ``docs`` are exercised so a new entry cannot ship without extending the
    per-family assertions below.
    """
    system = nix_helpers.current_system()
    names = set(
        nix_helpers.nix_eval_json(
            f"{REPO_ROOT}#checks.{system}", apply="builtins.attrNames"
        )
    )
    assert "module-rust" in names, (
        "the flake must expose checks.<system>.module-rust from the "
        f"nix/modules/ registry; got: {sorted(n for n in names if n.startswith('module-'))}"
    )


def test_rust_module_check_evaluates(current_system: str) -> None:
    """``checks.<system>.module-rust`` evaluates to a real derivation (#1400).

    The generated smoke check MUST reach a drvPath — the registry entry, the
    ``rust`` module import and the ``check-entries.nix`` override for the
    mandatory-options form all have to resolve before this returns a store
    path. Only asks for ``.drvPath`` (cheap eval) rather than building the
    devshell, which would pull the Rust toolchain into the cache; the deeper
    end-to-end tests own that cost when they need it.
    """
    drv = nix_helpers.nix_eval_raw(
        f"{REPO_ROOT}#checks.{current_system}.module-rust.drvPath"
    )
    assert drv.startswith("/nix/store/") and drv.endswith(".drv"), (
        f"module-rust must evaluate to a .drv path; got {drv!r}"
    )


def test_rust_module_bare_form_throws_with_mkrustproject_guidance() -> None:
    """``modules = [ "rust" ]`` fails at eval with the ``mkRustProject`` fix (#1427).

    THIS is the single most important test — the whole design rests on it. The
    ``rust`` module's ``checks`` option is mandatory with no default so a
    hand-written bare entry never silently produces a toolchain-only shell
    (the failure mode: five things believed active, none of them run, CI green
    compiling nothing). The eval error must name the composed entry point
    (``mkRustProject``) and the option (``checks``) so the message itself
    routes the reader to the fix and to the deliberate opt-out spelled out in
    the module header.
    """
    result = _nix_eval_expr(_rust_module_expr('"rust"'))
    assert result.returncode != 0, (
        'bare `modules = [ "rust" ]` MUST fail eval — this is the guard the '
        "language pack rests on; got a successful eval instead"
    )
    stderr = result.stderr
    assert "mkRustProject" in stderr, (
        f"guard message must name mkRustProject (the fix); got: {stderr[-800:]}"
    )
    assert "checks" in stderr, (
        "guard message must name the `checks` option (the mandatory knob); "
        f"got: {stderr[-800:]}"
    )


def test_rust_module_explicit_opt_out_evaluates() -> None:
    """``{ name = "rust"; checks = "none"; }`` is the sanctioned toolchain-only form.

    The deliberate opt-out from the guard above (#1427): a scratch shell, a
    repo whose Rust is incidental, a consumer that already owns its own
    checks. It is spelled out because a default would BE the failure mode.
    Evaluate to a drvPath to confirm the module returns a valid contribution
    (packages/env/shellHook) instead of throwing.
    """
    result = _nix_eval_expr(_rust_module_expr('{ name = "rust"; checks = "none"; }'))
    assert result.returncode == 0, (
        'explicit opt-out `{ name = "rust"; checks = "none"; }` must '
        f"evaluate; got: {result.stderr[-500:]}"
    )
    assert result.stdout.strip().startswith('"/nix/store/'), (
        f"opt-out form must return a store drvPath; got: {result.stdout!r}"
    )


def test_rust_module_rejects_unknown_option() -> None:
    """An unrecognized ``rust`` option fails eval and names the option (#1400).

    Every rust option is enumerated in ``knownOptions``; anything else throws
    before the module returns a contribution, so a typo (or an unsupported
    knob) is a hard eval error rather than a silently-ignored no-op — the same
    strictness the ``node`` module applies (see
    ``test_node_module_rejects_unknown_option``).
    """
    result = _nix_eval_expr(
        _rust_module_expr('{ name = "rust"; checks = "none"; frobnicate = 1; }')
    )
    assert result.returncode != 0, "unknown rust option must fail eval, not pass"
    assert "frobnicate" in result.stderr and "rust module" in result.stderr, (
        "error must name the offending option and the module; "
        f"got: {result.stderr[-500:]}"
    )


def test_rust_module_rejects_invalid_checks_value() -> None:
    """A ``checks`` value outside ``{"mkRustProject","none"}`` fails eval (#1427).

    The ``checks`` option is the module's acknowledgement token: the
    mkRustProject-set value or the deliberate opt-out are the only honest
    answers. Any other string (e.g. ``"yes"``) is a hand-edited fake and must
    throw with a message naming both valid values.
    """
    result = _nix_eval_expr(_rust_module_expr('{ name = "rust"; checks = "yes"; }'))
    assert result.returncode != 0, "invalid `checks` value must fail eval, not pass"
    stderr = result.stderr
    assert "rust module" in stderr and "checks" in stderr, (
        f"error must name the module and the option; got: {stderr[-500:]}"
    )
    # Both sanctioned values are surfaced in the message so the reader learns
    # what the correct answers are, not just that theirs is wrong.
    assert "mkRustProject" in stderr and "none" in stderr, (
        "error must enumerate the two valid `checks` values (mkRustProject, "
        f"none); got: {stderr[-500:]}"
    )


def test_rust_module_rejects_unknown_tool() -> None:
    """An unknown ``tools`` name fails eval and names it (#1400).

    The curated ``toolMap`` in the module is a name -> package map, chosen so a
    consumer's ``tools`` list stays reviewable and a typo becomes an eval
    error rather than a silently-missing cargo helper on the shell PATH. The
    error must name the offending tool so the reader can fix or drop it.
    """
    result = _nix_eval_expr(
        _rust_module_expr(
            '{ name = "rust"; checks = "none"; tools = [ "not-a-cargo-tool" ]; }'
        )
    )
    assert result.returncode != 0, "unknown rust tool name must fail eval, not pass"
    stderr = result.stderr
    assert "not-a-cargo-tool" in stderr and "rust module" in stderr, (
        f"error must name the offending tool and the module; got: {stderr[-500:]}"
    )


def test_mk_rust_project_is_exposed_as_a_function() -> None:
    """``lib.mkRustProject`` is a callable function (#1400).

    The composed entry point sits above ``mkProjectShell`` and returns
    ``{ devShell, checks, packages, craneLib, cargoArtifacts, commonArgs,
    toolchain, src }`` from a single call. Kept as a cheap schema smoke test:
    calling it needs a Rust source tree (project shape a devkit test cannot
    ambiently supply), so the deep end-to-end coverage of the shape lives in
    the first consumer (gerchowl/filesender). ``--apply`` reduces the raw
    function to a discriminator string — ``nix eval --raw`` on a bare function
    is a type error, hence the direct subprocess call.
    """
    result = subprocess.run(
        [
            "nix",
            "eval",
            "--raw",
            f"{REPO_ROOT}#lib.mkRustProject",
            "--apply",
            'f: if builtins.isFunction f then "ok" else "not-a-function"',
        ],
        capture_output=True,
        text=True,
        env=_nix_env(),
        timeout=120,
    )
    assert result.returncode == 0 and result.stdout.strip() == "ok", (
        "lib.mkRustProject must be a function; "
        f"rc={result.returncode} stdout={result.stdout!r} "
        f"stderr={result.stderr[-500:]}"
    )


def test_zero_module_shell_unaffected_by_rust_module(current_system: str) -> None:
    """The default dev-shell's drvPath is byte-identical to the no-modules build (#884, #1400).

    The ADR's zero-module invariant, re-asserted after the Rust pack shipped:
    adding a module to the registry must not perturb the shell a consumer who
    never asks for it gets. This is the same shape as ``TestZeroHooksParity``
    (tests/test_flake_hooks.py) — compare the flake's own
    ``devShells.<system>.default.drvPath`` to a freshly-built
    ``mkProjectShell { inherit pkgs; }`` and require equality — but pinned
    here so a future module cannot silently leak into the default path.
    """
    expr = f"""
    let
      flake = builtins.getFlake "path:{REPO_ROOT}";
      system = "{current_system}";
      pkgs = import flake.inputs.nixpkgs {{
        inherit system;
        overlays = [ flake.overlays.default ];
        config.allowUnfree = true;
      }};
    in {{
      default = flake.devShells.${{system}}.default.drvPath;
      zeroModules = (flake.lib.mkProjectShell {{ inherit pkgs; }}).drvPath;
    }}
    """
    result = subprocess.run(
        ["nix", "eval", "--impure", "--json", "--expr", expr],
        capture_output=True,
        text=True,
        env=_nix_env(),
        timeout=300,
    )
    assert result.returncode == 0, result.stderr
    paths = json.loads(result.stdout)
    assert paths["default"] == paths["zeroModules"], (
        "adding the rust module must not perturb the zero-module default "
        f"dev-shell drv; got {paths!r}"
    )


def test_rust_tool_group_expands_and_skips_unavailable_members() -> None:
    """``tools = [ "@perf" ]`` expands, dropping members this platform lacks (#1400).

    A group is a request for *this platform's* kit, so members that are not
    packaged here (heaptrack, valgrind and poop are Linux-only) are skipped
    rather than failing eval. Without this, every consumer writes the same
    ``optionals stdenv.isLinux`` by hand and some of them get it wrong.
    """
    with_group = _nix_eval_expr(
        _rust_module_expr('{ name = "rust"; checks = "none"; tools = [ "@perf" ]; }')
    )
    assert with_group.returncode == 0, (
        f"@perf group must evaluate on this platform; got: {with_group.stderr[-500:]}"
    )

    # The shell derivation must actually differ from a no-tools one. Asserting
    # only that it evaluates would pass even if the group silently expanded to
    # nothing -- which is exactly the "configured, contributes nothing" failure
    # this suite exists to catch.
    without = _nix_eval_expr(
        _rust_module_expr('{ name = "rust"; checks = "none"; tools = [ ]; }')
    )
    assert without.returncode == 0, (
        f"empty tools must evaluate; got: {without.stderr[-500:]}"
    )
    assert with_group.stdout != without.stdout, (
        "@perf expanded to no packages -- the group contributed nothing"
    )


def test_rust_explicit_unavailable_tool_still_throws() -> None:
    """A tool named EXPLICITLY is not silently skipped (#1400).

    The asymmetry against groups is deliberate and is the reason groups exist:
    asking for ``@perf`` is asking for whatever this platform has, but naming
    ``heaptrack`` is a request that can only be met or refused. Silently
    dropping it would hand someone a shell missing the one tool they asked
    for -- configured, believed present, never there.
    """
    result = _nix_eval_expr(
        _rust_module_expr(
            '{ name = "rust"; checks = "none"; tools = [ "heaptrack" ]; }'
        )
    )
    if result.returncode == 0:
        # Linux: heaptrack IS available, so there is nothing to refuse.
        return
    assert "heaptrack" in result.stderr and "unavailable-on" in result.stderr, (
        f"error must name the tool and the platform; got: {result.stderr[-500:]}"
    )


def test_rust_module_rejects_unknown_tool_group() -> None:
    """A mistyped group name fails eval and lists the real groups (#1400)."""
    result = _nix_eval_expr(
        _rust_module_expr('{ name = "rust"; checks = "none"; tools = [ "@perff" ]; }')
    )
    assert result.returncode != 0, "unknown tool group must fail eval, not pass"
    assert "unknown tool group" in result.stderr and "@perf" in result.stderr, (
        f"error must name the group and list the available ones; got: {result.stderr[-500:]}"
    )


# ---------------------------------------------------------------------------
# mkRustProject consumer guards (#1450) — found by adopting the pack on a
# second consumer (gerchowl/squelch: single-crate, no binaries, heavily
# feature-gated). The two guards below turn failures that were opaque or
# partial into ones that name the fix; the two coverage tests pin behaviour
# the pack promised in #1400 but did not ship.
#
# These need project shape, which is why the older mkRustProject coverage
# stops at a schema smoke test. A dependency-free crate keeps the lockfile a
# literal, so the whole set runs at EVAL time — no vendoring, no network, no
# compile.
# ---------------------------------------------------------------------------


def _minimal_crate(root: Path, *, with_lock: bool = True) -> Path:
    """Write the smallest crate crane will accept, and return its path."""
    (root / "src").mkdir(parents=True, exist_ok=True)
    (root / "Cargo.toml").write_text(
        '[package]\nname = "fixture"\nversion = "0.0.0"\nedition = "2021"\n'
    )
    (root / "src" / "lib.rs").write_text("pub fn answer() -> u8 { 42 }\n")
    if with_lock:
        (root / "Cargo.lock").write_text(
            'version = 3\n\n[[package]]\nname = "fixture"\nversion = "0.0.0"\n'
        )
    return root


def _mk_rust_project_expr(
    src: Path, attr: str, *, overlay: bool = True, extra: str = ""
) -> str:
    """An expression selecting ``attr`` off a ``mkRustProject`` call on ``src``."""
    overlays = "[ flake.overlays.default ]" if overlay else "[ ]"
    return f"""
    let
      flake = builtins.getFlake "path:{REPO_ROOT}";
      system = builtins.currentSystem;
      pkgs = import flake.inputs.nixpkgs {{
        inherit system;
        overlays = {overlays};
        config.allowUnfree = true;
      }};
      rust = flake.lib.mkRustProject {{
        inherit pkgs;
        src = {src};
        {extra}
      }};
    in {attr}
    """


def test_mk_rust_project_refuses_pkgs_without_the_devkit_overlay(
    tmp_path: Path,
) -> None:
    """A ``pkgs`` lacking ``overlays.default`` is named as such, not as ``vig-utils``.

    ``mkProjectShell`` pulls ``nix/devtools.nix``, which references
    ``vig-utils`` — a package only the overlay provides. Without the overlay
    the dev shell died with ``undefined variable 'vig-utils'``, pointing inside
    devkit at a name the consumer has never seen.

    The reason this is a guard rather than a docs fix: ``checks`` and
    ``packages`` never touch ``mkProjectShell``, so they evaluate fine without
    the overlay. The unguarded result is a repo whose ``nix flake check`` is
    green and whose ``nix develop`` is broken — the silent split the pack
    exists to close, one layer up.
    """
    src = _minimal_crate(tmp_path)
    result = _nix_eval_expr(
        _mk_rust_project_expr(src, "rust.devShell.drvPath", overlay=False)
    )
    assert result.returncode != 0, (
        "a pkgs without devkit's overlay must fail eval, not produce a shell"
    )
    assert "overlays.default" in result.stderr, (
        "the error must name the overlay the consumer has to add; "
        f"got: {result.stderr[-800:]}"
    )
    assert "undefined variable" not in result.stderr, (
        "the raw nixpkgs error must be replaced, not merely preceded; "
        f"got: {result.stderr[-800:]}"
    )


def test_mk_rust_project_names_a_missing_cargo_lock(tmp_path: Path) -> None:
    """A source tree with no ``Cargo.lock`` fails with the library case spelled out.

    A flake's ``src`` is the git tree, so a repo that gitignores its lockfile —
    the long-standing library convention — hands crane a source without one.
    crane's own message is good but reachable only from the derivations that
    vendor: ``fmt`` takes ``src`` alone and passed regardless, so a consumer
    who built one check first saw green.

    Asserted through ``fmt`` for exactly that reason.
    """
    src = _minimal_crate(tmp_path, with_lock=False)
    result = _nix_eval_expr(_mk_rust_project_expr(src, "rust.checks.fmt.drvPath"))
    assert result.returncode != 0, (
        "fmt must not evaluate against a lockless tree — it passing is what "
        "made the missing lockfile look like a partial success"
    )
    assert "Cargo.lock" in result.stderr, (
        f"the error must name Cargo.lock; got: {result.stderr[-800:]}"
    )


def test_mk_rust_project_ships_a_doctest_check(tmp_path: Path) -> None:
    """``checks.doctest`` exists (#1400's stage table, unshipped in #1429).

    #1400 assigns pre-push ``nextest`` **and** ``cargo test --doc``. nextest
    cannot run doctests by design, and ``cargoDoc`` only lints rustdoc, so a
    consumer whose doctests ran under ``cargo test`` lost them on adoption
    without being told.
    """
    src = _minimal_crate(tmp_path)
    result = subprocess.run(
        [
            "nix",
            "eval",
            "--impure",
            "--json",
            "--expr",
            _mk_rust_project_expr(src, "builtins.attrNames rust.checks"),
        ],
        capture_output=True,
        text=True,
        env=_nix_env(),
        timeout=300,
    )
    assert result.returncode == 0, result.stderr[-1500:]
    names = json.loads(result.stdout)
    assert "doctest" in names, (
        f"the default check suite must run doctests; got {names!r}"
    )


def test_mk_rust_project_threads_cargo_extra_args(tmp_path: Path) -> None:
    """``cargoExtraArgs`` reaches every derivation through ``commonArgs``.

    The checks built default features only, and nothing reached
    ``buildDepsOnly`` / ``nextest`` / ``doc`` / the package builds —
    ``clippyExtraArgs`` covers clippy alone. A feature-gated crate therefore
    got less linting from the pack than from a bare ``cargo clippy
    --all-features``, because the gated code was never compiled.
    """
    src = _minimal_crate(tmp_path)
    result = subprocess.run(
        [
            "nix",
            "eval",
            "--impure",
            "--raw",
            "--expr",
            _mk_rust_project_expr(
                src,
                "rust.commonArgs.cargoExtraArgs",
                extra='cargoExtraArgs = "--all-features";',
            ),
        ],
        capture_output=True,
        text=True,
        env=_nix_env(),
        timeout=300,
    )
    assert result.returncode == 0, result.stderr[-1500:]
    assert "--all-features" in result.stdout, (
        f"cargoExtraArgs must land in commonArgs; got {result.stdout!r}"
    )
