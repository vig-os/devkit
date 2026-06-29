"""
Container verification tests for Base Development Environment.

These tests verify the container image itself: installed tools, versions,
environment variables, and file structure. They do not require workspace
initialization.

Derived containers can inherit from these test classes to verify that
base functionality is preserved in their containers.
"""

import hashlib
import subprocess
from pathlib import Path

import pytest

# Expected version prefixes for the few tools whose version we still assert.
#
# Under the Nix image the toolchain is pinned by flake.lock, so each tool's exact
# version is determined by nixpkgs and intentionally changes on a nixpkgs bump.
# Fast-movers (gh) and tools whose nixpkgs version simply differs from the old
# Debian pin (just, pre-commit, cargo-binstall, typstyle) are checked for
# presence/run only, not a version prefix — otherwise they'd need updating on
# every nixpkgs bump. System packages (git, curl, tmux, rsync) were already
# presence-only. Refs #635, #666.
EXPECTED_VERSIONS = {
    "uv": "0.11.",  # uv (fast-mover overlaid from nixpkgs-unstable)
    "python": "3.14",  # interpreter major.minor (pinned to python314)
    "ruff": "0.15.",  # nixpkgs-26.05
    "bandit": "1.9.",  # nixpkgs-26.05
    "pip_licenses": "5.",  # PyPI wheel pinned in flake.nix
    "hadolint": "2.14.",  # nixpkgs-26.05
    "taplo": "0.10.",  # nixpkgs-26.05
    "vig_utils": "0.1.",  # our package version
}


def verify_file_identity(host, src_rel, dest_path):
    """
    Verify that a file in the project is identical to its image counterpart.

    Uses SHA-256 checksums for comparison, which works reliably for both
    text and binary files across the local/container boundary.

    Args:
        host: testinfra host object
        src_rel: Source path relative to project root
        dest_path: Full destination path in image

    Raises:
        AssertionError: If files are not identical
    """
    # Local file
    project_root = Path(__file__).parent.parent
    local_src_path = project_root / src_rel
    assert local_src_path.exists(), f"Source path not found: {src_rel}"
    assert local_src_path.is_file(), f"Source path is not a file: {src_rel}"
    local_sha = hashlib.sha256(local_src_path.read_bytes()).hexdigest()

    # Remote file
    assert host.file(dest_path).exists, f"Manifest file not found at {dest_path}"
    assert host.file(dest_path).is_file, f"Path is not a regular file: {dest_path}"
    result = host.run(f"sha256sum {dest_path}")
    assert result.rc == 0, f"sha256sum failed on {dest_path}: {result.stderr}"
    remote_sha = result.stdout.split()[0]

    # Verify that the local and remote files are identical
    assert local_sha == remote_sha, (
        f"Manifest file checksum mismatch: {dest_path}\n"
        f"Source: {src_rel} (sha256: {local_sha})\n"
        f"Destination: {dest_path} (sha256: {remote_sha})"
    )


def assert_tool_on_path(host, tool):
    """
    Assert that a tool is installed and resolvable on PATH.

    Path-agnostic: works for both the Debian image (tools under /usr/bin,
    /usr/local/bin) and the Nix image (tools under the Nix store), since it
    relies on PATH resolution rather than a hardcoded FHS location.

    Args:
        host: testinfra host object
        tool: executable name to resolve (e.g. "gh", "just")

    Returns:
        The resolved absolute path to the tool.
    """
    result = host.run(f"command -v {tool}")
    assert result.rc == 0, f"{tool} not found on PATH: {result.stderr}"
    resolved = result.stdout.strip()
    assert resolved, f"{tool} resolved to an empty path"
    return resolved


def assert_tool_runs(host, *cmd):
    """
    Assert that a tool runs successfully (exit code 0), proving it is installed.

    Path-agnostic replacement for distro-package checks (e.g. dpkg
    `is_installed`): valid for both the Debian and Nix images.

    Args:
        host: testinfra host object
        cmd: command and args to run (e.g. "git", "--version")

    Returns:
        The testinfra CommandResult.
    """
    command = " ".join(cmd)
    result = host.run(command)
    assert result.rc == 0, f"{command} failed (tool not installed?): {result.stderr}"
    return result


def test_image_oci_config_declares_path(container_image):
    """The image's OCI config.Env must declare PATH including the toolchain (#697).

    ``buildLayeredImage`` symlinks every tool into ``/bin`` but sets no PATH in
    the OCI config. ``podman run`` masks this by injecting a default PATH, but
    docker-compose and ``devcontainer exec`` inherit ``config.Env`` verbatim — so
    without a declared PATH the baked toolchain is off PATH there, and
    pre-commit's ``language: system`` ruff/typos hooks fail with
    ``Executable ... not found`` during an in-container ``git commit``. A
    ``host.run`` check cannot catch this (its shell synthesises a default PATH),
    so assert the declared config directly.
    """
    result = subprocess.run(
        [
            "podman",
            "inspect",
            container_image,
            "--format",
            "{{range .Config.Env}}{{println .}}{{end}}",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"podman inspect failed: {result.stderr}"
    path_lines = [ln for ln in result.stdout.splitlines() if ln.startswith("PATH=")]
    assert path_lines, (
        "image OCI config declares no PATH; docker-compose / devcontainer exec "
        "would run without the baked toolchain on PATH"
    )
    path_dirs = path_lines[0][len("PATH=") :].split(":")
    assert "/bin" in path_dirs, (
        f"image PATH must include /bin (the toolchain symlink dir): {path_lines[0]}"
    )


class TestFhsShims:
    """Test the minimal FHS shims a bare layered image needs (#727)."""

    def test_usr_bin_env_exists(self, host):
        """``/usr/bin/env`` must exist (the universal shebang interpreter).

        A bare ``buildLayeredImage`` has no ``/usr/bin`` at all, so the
        ubiquitous ``#!/usr/bin/env <interp>`` shebang fails with
        ``/usr/bin/env: bad interpreter`` — breaking essentially every
        Node/Python/Ruby CLI (e.g. ``node_modules/.bin/tsc``) for image-mode
        consumers. An FHS base distro would have supplied it. Refs #727.
        """
        env = host.file("/usr/bin/env")
        assert env.exists, "/usr/bin/env not found (universal shebang interpreter)"

    def test_usr_bin_env_shebang_runs(self, host):
        """A ``#!/usr/bin/env <interp>`` script must execute via ``/usr/bin/env``.

        Mirrors how a ``node_modules/.bin`` CLI is launched: the kernel reads the
        shebang and execs ``/usr/bin/env <interp>``. Uses ``bash`` (always in the
        image) as the interpreter so the test asserts the ``/usr/bin/env``
        resolution path itself, not the presence of any one language runtime.
        """
        script = "/tmp/usr_bin_env_shebang_test"
        host.run(f"rm -f {script}")
        try:
            result = host.run(
                f"printf '#!/usr/bin/env bash\\necho shebang-ok\\n' > {script} "
                f"&& chmod +x {script} && {script}"
            )
            assert result.rc == 0, (
                f"#!/usr/bin/env bash script failed to run: {result.stderr}"
            )
            assert "shebang-ok" in result.stdout, (
                f"unexpected shebang script output: {result.stdout!r}"
            )
        finally:
            host.run(f"rm -f {script}")


def _pypi_reachable(host):
    """Best-effort probe: can the image reach PyPI to fetch a wheel?

    The loader-existence assertion is unconditional, but the wheel-import
    assertions need network and the image bakes no warm uv cache, so when the
    suite runs offline (e.g. a hermetic build sandbox) those tests skip rather
    than fail. Refs #736.
    """
    return (
        host.run(
            'python3 -c "import socket,sys; socket.setdefaulttimeout(5); '
            "socket.create_connection(('pypi.org', 443)); sys.exit(0)\""
        ).rc
        == 0
    )


class TestManylinuxRuntime:
    """Runtime support for pre-compiled PyPI (manylinux) wheels (#736).

    The bare Nix layered image is Nix-but-not-NixOS: it shipped neither the FHS
    dynamic loader (``/lib64/ld-linux-x86-64.so.2``) that every manylinux
    x86_64 wheel hardcodes as its ``PT_INTERP``, nor the Nix C++/compression
    runtime on the loader path. So runtime-installed PyPI binaries broke —
    standalone tools (pre-commit's PyPI ruff/typos: ``cannot execute: required
    file not found``) and C extensions dlopened by the baked CPython (numpy,
    scipy, pre-commit's ``pyjson5``: ``ImportError: libstdc++.so.6``). This is
    the image-scope analogue of the dev-shell's #698 fix.
    """

    def test_fhs_loader_exists(self, host):
        """The FHS loader manylinux wheels exec must exist (arch-specific).

        Unconditional (needs no network): a missing loader is the root cause of
        ``cannot execute: required file not found`` for any PyPI-pinned
        standalone tool. The path is arch-specific (the image builds natively
        per arch): x86_64 -> ``/lib64/ld-linux-x86-64.so.2``,
        aarch64 -> ``/lib/ld-linux-aarch64.so.1``. Refs #736.
        """
        arch = host.system_info.arch
        loader_path = (
            "/lib/ld-linux-aarch64.so.1"
            if arch in ("aarch64", "arm64")
            else "/lib64/ld-linux-x86-64.so.2"
        )
        loader = host.file(loader_path)
        assert loader.exists, (
            f"{loader_path} missing; manylinux wheel executables "
            "(e.g. PyPI-pinned pre-commit ruff/typos) cannot exec"
        )

    @pytest.mark.parametrize(
        ("install_spec", "import_name"),
        [
            ("numpy", "numpy"),  # heavy manylinux wheel (libstdc++ / libgcc_s)
            ("pyjson5", "pyjson5"),  # pre-commit pymarkdown's C-extension dep
        ],
        ids=["numpy", "pyjson5"],
    )
    def test_manylinux_wheel_imports(self, host, install_spec, import_name):
        """A runtime-installed manylinux wheel imports under the baked CPython.

        Exercises the C-extension path the loader symlink alone cannot fix: the
        ``.so`` is dlopened by the Nix-store CPython (which uses its own store
        loader, not ``/lib64``), so its ``libstdc++``/``libgcc_s`` must resolve
        via the baked ``LD_LIBRARY_PATH``. Network-guarded — the image ships no
        warm cache. Refs #736.
        """
        if not _pypi_reachable(host):
            pytest.skip("PyPI unreachable; cannot fetch manylinux wheel offline")
        venv = f"/tmp/manylinux_{import_name}"
        host.run(f"rm -rf {venv}")
        try:
            result = host.run(
                f"uv venv {venv} "
                f"&& uv pip install --python {venv}/bin/python {install_spec} "
                f"&& {venv}/bin/python -c "
                f"'import {import_name}; print({import_name}.__file__)'"
            )
            assert result.rc == 0, (
                f"manylinux wheel {install_spec!r} failed to import: "
                f"{result.stdout}\n{result.stderr}"
            )
        finally:
            host.run(f"rm -rf {venv}")


class TestSystemTools:
    """Test that system tools are installed with correct versions."""

    def test_git_installed(self, host):
        """Test that git is installed (path-agnostic, via --version)."""
        assert_tool_runs(host, "git", "--version")

    def test_git_version(self, host):
        """Test that git runs and reports a version."""
        result = host.run("git --version")
        assert result.rc == 0, "git --version failed"
        assert "git version" in result.stdout.lower()

    def test_curl_installed(self, host):
        """Test that curl is installed (path-agnostic, via --version)."""
        assert_tool_runs(host, "curl", "--version")

    def test_curl_version(self, host):
        """Test that curl runs and reports a version."""
        result = host.run("curl --version")
        assert result.rc == 0, "curl --version failed"
        assert "curl" in result.stdout.lower()

    def test_openssh_client_installed(self, host):
        """Test that the openssh client is installed (path-agnostic)."""
        assert_tool_runs(host, "ssh", "-V")

    def test_nano_installed(self, host):
        """Test that nano is installed (path-agnostic, via --version)."""
        assert_tool_runs(host, "nano", "--version")

    def test_gh_installed(self, host):
        """Test that GitHub CLI (gh) is installed (path-agnostic)."""
        assert_tool_on_path(host, "gh")

    def test_gh_version(self, host):
        """Test that gh runs (version is nixpkgs-pinned via flake.lock, not asserted)."""
        result = host.run("gh --version")
        assert result.rc == 0, "gh --version failed"
        assert "gh version" in result.stdout.lower()

    def test_just_installed(self, host):
        """Test that just is installed (path-agnostic)."""
        assert_tool_on_path(host, "just")

    def test_just_version(self, host):
        """Test that just runs (version is nixpkgs-pinned via flake.lock, not asserted)."""
        result = host.run("just --version")
        assert result.rc == 0, "just --version failed"
        assert "just" in result.stdout.lower()

    def test_hadolint_installed(self, host):
        """Test that hadolint is installed (path-agnostic)."""
        assert_tool_on_path(host, "hadolint")

    def test_hadolint_version(self, host):
        """Test that hadolint version is correct."""
        result = host.run("hadolint --version")
        assert result.rc == 0, "hadolint --version failed"
        expected = EXPECTED_VERSIONS["hadolint"]
        assert expected in result.stdout, (
            f"Expected hadolint {expected}, got: {result.stdout}"
        )

    def test_taplo_installed(self, host):
        """Test that taplo (TOML formatter/linter) is installed (path-agnostic)."""
        assert_tool_on_path(host, "taplo")

    def test_taplo_version(self, host):
        """Test that taplo version is correct."""
        result = host.run("taplo --version")
        assert result.rc == 0, "taplo --version failed"
        expected = EXPECTED_VERSIONS["taplo"]
        assert expected in result.stdout, (
            f"Expected taplo {expected}, got: {result.stdout}"
        )

    def test_cargo_binstall(self, host):
        """Test that cargo-binstall runs (version nixpkgs-pinned, not asserted)."""
        result = host.run("cargo-binstall -V")
        assert result.rc == 0, "cargo-binstall -V failed"

    def test_typstyle(self, host):
        """Test that typstyle runs (version nixpkgs-pinned, not asserted)."""
        result = host.run("typstyle --version")
        assert result.rc == 0, "typstyle --version failed"

    def test_just_lsp_installed(self, host):
        """Test that just-lsp is installed."""
        result = host.run("just-lsp --version")
        assert result.rc == 0, "just-lsp --version failed"
        assert "just-lsp" in result.stdout.lower(), (
            f"Expected just-lsp version output, got: {result.stdout}"
        )

    def test_tmux_installed(self, host):
        """Test that tmux is installed (path-agnostic, via -V)."""
        result = assert_tool_runs(host, "tmux", "-V")
        assert "tmux" in result.stdout.lower()

    def test_rsync_installed(self, host):
        """Test that rsync is installed (path-agnostic, via --version)."""
        result = assert_tool_runs(host, "rsync", "--version")
        assert "rsync" in result.stdout.lower()

    def test_tmux_detached_session_survives(self, host):
        """Test that tmux can create a detached session with a background process."""
        session = "test-session"
        host.run(f"tmux kill-session -t {session} 2>/dev/null")
        try:
            result = host.run(f"tmux new-session -d -s {session} 'sleep 60'")
            assert result.rc == 0, f"Failed to create tmux session: {result.stderr}"

            result = host.run("tmux list-sessions")
            assert result.rc == 0, "tmux list-sessions failed"
            assert session in result.stdout, (
                f"Session '{session}' not found in: {result.stdout}"
            )

            result = host.run(f"tmux list-panes -t {session} -F '#{{pane_pid}}'")
            assert result.rc == 0, "Failed to get pane PID"
            pid = result.stdout.strip()
            assert pid, "No PID returned for tmux pane"
            result = host.run(f"kill -0 {pid}")
            assert result.rc == 0, f"Process {pid} is not running"
        finally:
            host.run(f"tmux kill-session -t {session} 2>/dev/null")


class TestPythonEnvironment:
    """Test Python environment setup."""

    def test_python3_installed(self, host):
        """Test that python3 is available."""
        result = host.run("python3 --version")
        assert result.rc == 0, "python3 --version failed"
        expected = EXPECTED_VERSIONS["python"]
        assert f"Python {expected}" in result.stdout, (
            f"Expected Python {expected}, got: {result.stdout}"
        )

    def test_uv_installed(self, host):
        """Test that uv is installed."""
        result = host.run("uv --version")
        assert result.rc == 0, "uv --version failed"
        assert "uv" in result.stdout.lower()
        expected = EXPECTED_VERSIONS["uv"]
        assert expected in result.stdout, (
            f"Expected uv {expected}, got: {result.stdout}"
        )

    def test_uv_venv_workflow(self, host):
        """Test that uv sync creates venv and manages project dependencies correctly."""
        # Use /tmp for test project to avoid conflicts
        test_dir = "/tmp/uv_test_project"
        pyproject_path = f"{test_dir}/pyproject.toml"
        lockfile_path = f"{test_dir}/uv.lock"
        venv_path = f"{test_dir}/.venv"

        # Clean up any existing test directory
        host.run(f"rm -rf {test_dir}")
        host.run(f"mkdir -p {test_dir}")

        try:
            # Step 1: Create a simple pyproject.toml using a here-document
            create_pyproject = f"""cat > {pyproject_path} << 'PYPROJECT_EOF'
[project]
name = "test-project"
version = "0.1.0"
description = "Test project for uv venv workflow"
requires-python = ">=3.12"
dependencies = []
PYPROJECT_EOF"""
            result = host.run(f"cd {test_dir} && {create_pyproject}")
            assert result.rc == 0, f"Failed to create pyproject.toml: {result.stderr}"

            # Step 2: Run uv sync (should create .venv by default)
            # Unset UV_PROJECT_ENVIRONMENT so uv creates a local .venv
            result = host.run(f"cd {test_dir} && UV_PROJECT_ENVIRONMENT= uv sync")
            assert result.rc == 0, f"uv sync failed: {result.stderr}"
            assert host.file(lockfile_path).exists, "uv.lock file was not created"
            assert host.file(venv_path).is_directory, ".venv directory was not created"

            # Step 3: Run uv add with a lightweight package (typing-extensions is very lightweight)
            package_name = "typing-extensions"
            result = host.run(
                f"cd {test_dir} && UV_PROJECT_ENVIRONMENT= uv add {package_name}"
            )
            assert result.rc == 0, f"uv add {package_name} failed: {result.stderr}"

            # Verify package was added to pyproject.toml
            pyproject_content_after = host.file(pyproject_path).content_string
            assert package_name in pyproject_content_after, (
                f"{package_name} was not added to pyproject.toml"
            )

            # Step 4: Run uv sync again
            result = host.run(f"cd {test_dir} && UV_PROJECT_ENVIRONMENT= uv sync")
            assert result.rc == 0, f"Second uv sync failed: {result.stderr}"

            # Verify the package is installed in venv (not system-wide)
            # Use uv run to execute in the venv context
            result = host.run(
                f"cd {test_dir} && UV_PROJECT_ENVIRONMENT= uv run python -c 'import {package_name.replace('-', '_')}; print(\"OK\")'"
            )
            assert result.rc == 0, (
                f"{package_name} is not importable in venv after uv sync"
            )
            assert "OK" in result.stdout, f"Failed to import {package_name} in venv"

            # Verify package is NOT available system-wide (should fail)
            result = host.run(
                f"python3 -c 'import {package_name.replace('-', '_')}; print(\"OK\")'"
            )
            assert result.rc != 0, (
                f"{package_name} should not be available system-wide, only in venv"
            )

            # Step 5: Verify system packages (pre-commit, ruff) are still available
            # This confirms uv sync didn't remove them
            result = host.run("pre-commit --version")
            assert result.rc == 0, (
                "pre-commit was removed by uv sync (should not happen)"
            )
            result = host.run("ruff --version")
            assert result.rc == 0, "ruff was removed by uv sync (should not happen)"

        finally:
            # Clean up test directory
            host.run(f"rm -rf {test_dir}")


class TestDevelopmentTools:
    """Test that development tools are installed."""

    def test_pre_commit_installed(self, host):
        """Test that pre-commit runs (version nixpkgs-pinned via flake.lock)."""
        result = host.run("pre-commit --version")
        assert result.rc == 0, "pre-commit --version failed"
        assert "pre-commit" in result.stdout.lower()

    def test_ruff_installed(self, host):
        """Test that ruff is installed."""
        result = host.run("ruff --version")
        assert result.rc == 0, "ruff --version failed"
        assert "ruff" in result.stdout.lower()
        expected = EXPECTED_VERSIONS["ruff"]
        assert expected in result.stdout, (
            f"Expected ruff {expected}, got: {result.stdout}"
        )

    def test_bandit_installed(self, host):
        """Test that bandit is installed."""
        result = host.run("bandit --version")
        assert result.rc == 0, "bandit --version failed"
        assert "bandit" in result.stdout.lower()
        expected = EXPECTED_VERSIONS["bandit"]
        assert expected in result.stdout, (
            f"Expected bandit {expected}, got: {result.stdout}"
        )

    def test_pip_licenses_installed(self, host):
        """Test that pip-licenses is installed."""
        result = host.run("pip-licenses --version")
        assert result.rc == 0, "pip-licenses --version failed"
        assert "pip-licenses" in result.stdout.lower()
        expected = EXPECTED_VERSIONS["pip_licenses"]
        assert expected in result.stdout, (
            f"Expected pip-licenses {expected}, got: {result.stdout}"
        )

    def test_vig_utils_installed(self, host):
        """Test that vig-utils is installed and importable."""
        result = host.run("python3 -c 'import vig_utils; print(\"OK\")'")
        assert result.rc == 0, (
            f"vig-utils is not installed or not importable: {result.stderr}"
        )
        assert "OK" in result.stdout, "Failed to import vig_utils"

    def test_vig_utils_version(self, host):
        """Test that vig-utils version is correct."""
        result = host.run("python3 -c 'import vig_utils; print(vig_utils.__version__)'")
        assert result.rc == 0, "Failed to get vig-utils version"
        expected = EXPECTED_VERSIONS["vig_utils"]
        assert expected in result.stdout, (
            f"Expected vig-utils {expected}x, got: {result.stdout}"
        )

    @pytest.mark.parametrize(
        "module",
        [
            "vig_utils.gh_issues",
            "vig_utils.validate_commit_msg",
            "vig_utils.check_action_pins",
            "vig_utils.prepare_changelog",
            "vig_utils.prepare_commit_msg_strip_trailers",
            "vig_utils.check_agent_identity",
            "vig_utils.check_pr_agent_fingerprints",
            "vig_utils.resolve_branch",
            "vig_utils.derive_branch_summary",
            "vig_utils.check_skill_names",
            "vig_utils.setup_labels",
            "vig_utils.utils",
        ],
    )
    def test_vig_utils_required_modules_importable(self, host, module):
        """Test that core vig_utils modules are importable."""
        result = host.run(f"python3 -c 'import {module}; print(\"OK\")'")
        assert result.rc == 0, f"{module} is not importable: {result.stderr}"
        assert "OK" in result.stdout

    @pytest.mark.parametrize(
        "name",
        [
            "check-skill-names",
            "derive-branch-summary",
            "gh-issues",
            "resolve-branch",
            "setup-labels",
        ],
    )
    def test_vig_utils_shell_scripts(self, host, name):
        """Test vig-utils shell wrapper commands are callable."""
        result = host.run(f'bash -lc "command -v {name}"')
        assert result.rc == 0, f"{name} command failed: {result.stderr}"


class TestContainerRuntime:
    """Test the container runtime tooling (#740)."""

    def test_podman_installed(self, host):
        """podman is installed (the image's container runtime)."""
        result = assert_tool_runs(host, "podman", "--version")
        assert "podman" in result.stdout.lower()

    def test_docker_shim_on_path(self, host):
        """A `docker` shim must resolve on PATH (#740).

        The image ships `podman` but no `docker` binary. Docker-out-of-Docker
        works because podman honors DOCKER_HOST, but any recipe/script that
        invokes `docker` literally fails with "command not found" without a
        shim. The image bakes a `docker -> podman` wrapper on /usr/local/bin.
        """
        assert_tool_on_path(host, "docker")

    def test_docker_shim_runs_podman(self, host):
        """The `docker` shim must run and report podman's version (#740).

        Proves the wrapper execs podman rather than merely existing on PATH.
        """
        result = host.run("docker --version")
        assert result.rc == 0, f"docker --version failed: {result.stderr}"
        assert "podman" in result.stdout.lower(), (
            f"docker shim did not exec podman: {result.stdout!r}"
        )


class TestNodeEnvironment:
    """Test the Node.js / npm environment (#728)."""

    def test_npm_installed(self, host):
        """npm runs (ships with the nixpkgs nodejs)."""
        result = host.run("npm --version")
        assert result.rc == 0, f"npm --version failed: {result.stderr}"

    def test_npm_global_prefix_bin_on_path(self, host):
        """npm's global prefix bin/ must be writable and on PATH (#728).

        In a bare Nix-built image npm's default prefix is the read-only nodejs
        nix-store path, whose bin/ is not on PATH: ``npm install -g`` reports
        success but the binary lands somewhere nothing can resolve. The image
        bakes ``NPM_CONFIG_PREFIX`` to a writable, on-PATH dir to fix this.
        """
        prefix = host.run("npm config get prefix")
        assert prefix.rc == 0, f"npm config get prefix failed: {prefix.stderr}"
        prefix_dir = prefix.stdout.strip()
        assert prefix_dir, "npm reported an empty global prefix"

        path = host.run("printenv PATH")
        assert f"{prefix_dir}/bin" in path.stdout.split(":"), (
            f"npm global bin {prefix_dir}/bin is not on PATH: {path.stdout.strip()}"
        )

        probe = f"{prefix_dir}/bin/.npm_prefix_write_probe"
        result = host.run(f"touch {probe} && rm {probe}")
        assert result.rc == 0, (
            f"npm global bin {prefix_dir}/bin is not writable: {result.stderr}"
        )

    def test_npm_global_install_resolves_on_path(self, host):
        """A global ``npm install -g`` lands a resolvable binary on PATH (#728).

        Faithful reproduction of the reported bug: install a CLI globally and
        confirm it resolves on PATH afterwards (previously the binary landed in
        the read-only nodejs store path, off PATH, so ``command -v`` failed).

        Scoped to #728: only that the binary is on PATH. Executing it relies on
        the ``#!/usr/bin/env`` shebang interpreter, which #727 provides — this
        test deliberately does not depend on that.
        """
        try:
            install = host.run("npm install -g tsx")
            assert install.rc == 0, f"npm install -g tsx failed: {install.stderr}"
            assert_tool_on_path(host, "tsx")
        finally:
            host.run("npm uninstall -g tsx")


class TestEnvironmentVariables:
    """Test that environment variables are set correctly."""

    @pytest.mark.parametrize(
        ("name", "expected"),
        # DEBIAN_FRONTEND is intentionally omitted: it is a Debian/apt-specific
        # build-time variable that is not meaningful on the Nix image.
        [
            ("LANG", "en_US.UTF-8"),
            ("LANGUAGE", "en_US:en"),
            ("LC_ALL", "en_US.UTF-8"),
            ("PYTHONUNBUFFERED", "1"),
            ("IN_CONTAINER", "true"),
            ("PRE_COMMIT_HOME", "/opt/pre-commit-cache"),
            ("UV_PROJECT_ENVIRONMENT", "/root/assets/workspace/.venv"),
            ("VIRTUAL_ENV", "/root/assets/workspace/.venv"),
            ("NPM_CONFIG_PREFIX", "/usr/local"),
        ],
        ids=[
            "lang",
            "language",
            "lc_all",
            "pythonunbuffered",
            "in_container",
            "pre_commit_home",
            "uv_project_environment",
            "virtual_env",
            "npm_config_prefix",
        ],
    )
    def test_env_vars_set(self, host, name, expected):
        """Test that required environment variables are set to expected values."""
        result = host.run(f"printenv {name}")
        assert result.rc == 0, f"Failed to read {name}"
        assert result.stdout.strip() == expected, (
            f"Expected {name}={expected}, got: {result.stdout.strip()}"
        )

    @pytest.mark.parametrize(
        "tool",
        [
            "cargo-binstall",
            "typstyle",
        ],
        ids=["cargo_binstall_on_path", "cargo_tool_on_path"],
    )
    def test_path_resolves_required_tools(self, host, tool):
        """Test that cargo-installed tools resolve on PATH.

        Path-agnostic replacement for asserting hardcoded install dirs
        (e.g. /root/.cargo/bin) are on PATH: we instead verify the tools
        those dirs provide are reachable, which holds for both the Debian
        and Nix images.
        """
        assert_tool_on_path(host, tool)


class TestFileStructure:
    """Test that expected files and directories exist."""

    def test_workspace_directory_exists(self, host):
        """Test that workspace directory exists."""
        assert host.file("/workspace").is_directory, "Workspace directory not found"

    def test_migration_guide_shipped(self, host):
        """The migration guide ships in the image at /root/assets/MIGRATION.md (#625)."""
        doc = host.file("/root/assets/MIGRATION.md")
        assert doc.exists, "/root/assets/MIGRATION.md not found in image"
        assert doc.is_file, "/root/assets/MIGRATION.md is not a regular file"
        assert "Migrating to the Nix devcontainer" in doc.content_string, (
            "MIGRATION.md does not contain its expected heading"
        )

    def test_precommit_alias_in_bashrc(self, host):
        """Test that precommit alias is defined in .bashrc."""
        bashrc = host.file("/root/.bashrc")
        assert bashrc.exists, ".bashrc not found"
        assert "alias precommit=" in bashrc.content_string, (
            "precommit alias not found in .bashrc"
        )

    def test_assets_directory_exists(self, host):
        """Test that assets directory exists."""
        assert host.file("/root/assets").is_directory, "Assets directory not found"

    def test_assets_workspace_structure(self, host):
        """Test that assets/workspace directory structure is complete."""
        # Define expected directories
        expected_dirs = [
            "/root/assets/workspace",
            "/root/assets/workspace/.devcontainer",
            "/root/assets/workspace/.devcontainer/scripts",
            "/root/assets/workspace/.githooks",
        ]

        # Define expected files
        expected_files = [
            # Workspace root files
            "/root/assets/workspace/.gitignore",
            "/root/assets/workspace/.pre-commit-config.yaml",
            "/root/assets/workspace/.pymarkdown",
            "/root/assets/workspace/.pymarkdown.config.md",
            "/root/assets/workspace/.yamllint",
            "/root/assets/workspace/CHANGELOG.md",
            "/root/assets/workspace/README.md",
            "/root/assets/workspace/LICENSE",
            "/root/assets/workspace/.vig-os",
            # .devcontainer files
            "/root/assets/workspace/.devcontainer/.gitignore",
            "/root/assets/workspace/.devcontainer/CHANGELOG.md",
            "/root/assets/workspace/.devcontainer/README.md",
            "/root/assets/workspace/.devcontainer/devcontainer.json",
            "/root/assets/workspace/.devcontainer/docker-compose.yml",
            "/root/assets/workspace/.devcontainer/docker-compose.project.yaml",
            "/root/assets/workspace/.devcontainer/docker-compose.local.yaml",
            "/root/assets/workspace/.devcontainer/workspace.code-workspace.example",
            # .devcontainer/scripts files
            "/root/assets/workspace/.devcontainer/scripts/post-create.sh",
            "/root/assets/workspace/.devcontainer/scripts/initialize.sh",
            "/root/assets/workspace/.devcontainer/scripts/post-attach.sh",
            "/root/assets/workspace/.devcontainer/scripts/copy-host-user-conf.sh",
            "/root/assets/workspace/.devcontainer/scripts/init-git.sh",
            "/root/assets/workspace/.devcontainer/scripts/init-precommit.sh",
            "/root/assets/workspace/.devcontainer/scripts/setup-git-conf.sh",
            "/root/assets/workspace/.devcontainer/scripts/verify-auth.sh",
            # Git hooks
            "/root/assets/workspace/.githooks/pre-commit",
        ]

        # Define files and folders that should be gitignored (user-specific, not in image)
        gitignored_content = [
            "/root/assets/workspace/.devcontainer/docker-compose.local.yml",
            "/root/assets/workspace/.devcontainer/.conf",
            "/root/assets/workspace/.devcontainer/workspace.code-workspace",
        ]

        # Check all directories exist
        for dir_path in expected_dirs:
            assert host.file(dir_path).is_directory, (
                f"Expected directory not found: {dir_path}"
            )

        # Check all files exist
        for file_path in expected_files:
            assert host.file(file_path).exists, f"Expected file not found: {file_path}"
            assert host.file(file_path).is_file, (
                f"Expected file is not a regular file: {file_path}"
            )
            # Check shell scripts are executable
            if file_path.endswith(".sh"):
                assert host.file(file_path).mode & 0o111, (
                    f"Expected shell script is not executable: {file_path}"
                )

        # Check that gitignored files and folders are gitignored
        for file_path in gitignored_content:
            assert not host.file(file_path).exists, (
                f"Expected file not found: {file_path}"
            )

    def test_workspace_template_pre_commit_hooks_initialized(self, host):
        """Test that the pre-commit cache dir exists at the system cache location.

        The dir is `PRE_COMMIT_HOME=/opt/pre-commit-cache` (set in the image env)
        so init-workspace.sh need not exclude it during copy. Unlike the Debian
        build, a hermetic Nix build cannot pre-fetch the hook repos (no network),
        so we assert the cache *directory* is present; it populates on the first
        `pre-commit run` / `install-hooks`.
        """
        cache_dir = host.file("/opt/pre-commit-cache")
        assert cache_dir.exists, (
            "Pre-commit cache directory not found at /opt/pre-commit-cache"
        )
        assert cache_dir.is_directory, "Pre-commit cache is not a directory"

    def test_template_venv_baked(self, host):
        """Test that the project virtualenv is baked into the image.

        The image advertises ``UV_PROJECT_ENVIRONMENT``/``VIRTUAL_ENV`` at
        ``/root/assets/workspace/.venv``; the consumer post-create.sh runs
        ``sed -i .../.venv/bin/activate`` and aborts under ``set -e`` if the
        activate script is missing (#735). The flake bootstrap pre-creates the
        venv from the baked CPython (no deps; ``just sync`` populates it).
        """
        activate = host.file("/root/assets/workspace/.venv/bin/activate")
        assert activate.exists, (
            "venv activate script not found at "
            "/root/assets/workspace/.venv/bin/activate"
        )
        assert activate.is_file, "venv activate script is not a regular file"

    def test_manifest_files(self, host, parse_manifest):
        """Test that all files in manifest are copied to the image.

        Non-transformed entries are verified via SHA-256 checksum comparison.
        Transformed entries are only checked for existence (content differs
        intentionally due to post-copy transformations).
        """
        manifest_entries = parse_manifest()
        project_root = Path(__file__).parent.parent
        workspace_base = "/root/assets/workspace"

        for src_rel, dest_rel, is_transformed in manifest_entries:
            src_path = project_root / src_rel
            if src_path.is_file():
                if is_transformed:
                    dest_path = f"{workspace_base}/{dest_rel}"
                    assert host.file(dest_path).exists, (
                        f"Transformed manifest file not found at {dest_path}"
                    )
                else:
                    verify_file_identity(host, src_rel, f"{workspace_base}/{dest_rel}")
            elif src_path.is_dir():
                files = sorted(f for f in src_path.rglob("*") if f.is_file())
                assert files, f"Manifest local directory is empty: {src_rel}"
                for file_path in files:
                    rel = file_path.relative_to(project_root)
                    dest_file_rel = f"{dest_rel}/{file_path.relative_to(src_path)}"
                    dest_file_path = f"{workspace_base}/{dest_file_rel}"
                    if is_transformed:
                        assert host.file(dest_file_path).exists, (
                            f"Transformed manifest file not found at {dest_file_path}"
                        )
                    else:
                        verify_file_identity(host, str(rel), dest_file_path)


class TestNixConfiguration:
    """Test that the baked /etc/nix/nix.conf enables the modern Nix CLI.

    The image bakes CppNix but historically shipped no nix.conf, leaving
    `nix-command`/`flakes` disabled by default so ad-hoc on-demand tooling
    (`nix shell nixpkgs#<x>`, `nix run`, `nix eval`) failed without an explicit
    `--extra-experimental-features` flag. Refs #739.
    """

    def test_nix_conf_exists(self, host):
        """/etc/nix/nix.conf is present as a regular file."""
        conf = host.file("/etc/nix/nix.conf")
        assert conf.exists, "/etc/nix/nix.conf not found"
        assert conf.is_file, "/etc/nix/nix.conf is not a regular file"

    def test_nix_conf_enables_experimental_features(self, host):
        """nix.conf turns on the nix-command and flakes experimental features."""
        content = host.file("/etc/nix/nix.conf").content_string
        feature_line = next(
            (
                line
                for line in content.splitlines()
                if line.strip().startswith("experimental-features")
            ),
            None,
        )
        assert feature_line is not None, (
            "no experimental-features setting in /etc/nix/nix.conf"
        )
        assert "nix-command" in feature_line, (
            "nix-command not enabled in /etc/nix/nix.conf"
        )
        assert "flakes" in feature_line, "flakes not enabled in /etc/nix/nix.conf"

    def test_nix_command_works_without_flag(self, host):
        """`nix eval` succeeds without an explicit experimental-features flag."""
        result = host.run('nix eval --expr "1 + 1"')
        assert result.rc == 0, (
            f"nix eval failed without experimental-features flag: {result.stderr}"
        )
        assert result.stdout.strip() == "2", (
            f"unexpected nix eval output: {result.stdout!r}"
        )

    def test_nix_conf_disables_build_users_group(self, host):
        """nix.conf sets an empty ``build-users-group`` (#749).

        The in-image nix runs as root, single-user, daemonless with no
        ``nixbld`` group, so any on-demand ``nix shell``/``nix develop`` that
        needs a local build (not a pure cache substitution) would abort with
        "the group 'nixbld' ... does not exist". An empty ``build-users-group``
        makes root build directly.
        """
        content = host.file("/etc/nix/nix.conf").content_string
        group_lines = [
            line.strip()
            for line in content.splitlines()
            if line.strip().startswith("build-users-group")
        ]
        assert group_lines, "no build-users-group setting in /etc/nix/nix.conf"
        # Must be empty (everything after '=' is blank) so root builds directly.
        value = group_lines[0].split("=", 1)[1].strip()
        assert value == "", (
            f"build-users-group must be empty for single-user in-image nix, got {value!r}"
        )


class TestPlaceholders:
    """Test that placeholders are replaced correctly."""

    def test_image_tag_replaced(self, host):
        """Test that {{IMAGE_TAG}} placeholder is replaced in all asset files."""
        workspace_root = "/root/assets/workspace"

        # Hard-coded list of paths to exclude
        excluded_paths = [
            ".pre-commit-cache",
            ".ruff_cache",
            ".venv",
        ]

        # Build find command with exclusions
        exclude_patterns = " -o ".join(
            [f"-path '*/{path}/*'" for path in excluded_paths]
        )
        find_cmd = (
            f"find {workspace_root} "
            f"\\( {exclude_patterns} \\) -prune "
            r"-o -type f -print"
        )

        result = host.run(find_cmd)
        assert result.rc == 0, f"Failed to find files in {workspace_root}"
        files = result.stdout.strip().split("\n") if result.stdout.strip() else []

        for file_path in files:
            file = host.file(file_path)
            if file.exists and file.is_file:
                try:
                    content = file.content_string
                    assert "{{IMAGE_TAG}}" not in content, (
                        f"{{IMAGE_TAG}} placeholder not replaced in {file_path}"
                    )
                except UnicodeDecodeError:
                    # Skip binary files
                    continue
