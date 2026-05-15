"""
Container verification tests for Base Development Environment.

These tests verify the container image itself: installed tools, versions,
environment variables, and file structure. They do not require workspace
initialization.

Derived containers can inherit from these test classes to verify that
base functionality is preserved in their containers.
"""

import hashlib
from pathlib import Path

import pytest

# Expected versions for installed tools
# These should be updated when the Containerfile is updated
EXPECTED_VERSIONS = {
    "git": "2.",  # Major version check (from apt package)
    "curl": "8.",  # Major version check (from apt package)
    "gh": "2.92.",  # Minor version check (GitHub CLI, manually installed from latest release)
    "uv": "0.11.",  # Minor version check (manually installed from latest release)
    "python": "3.12",  # Python (from base image)
    "pre_commit": "4.5.",  # Minor version check (installed via uv pip)
    "ruff": "0.15.",  # Minor version check (installed via uv pip)
    "bandit": "1.9.",  # Minor version check (installed via uv pip)
    "pip_licenses": "5.",  # Major version check (installed via uv pip)
    "just": "1.51.",  # Minor version check (manually installed from latest release)
    "hadolint": "2.14.",  # Minor version check (manually installed from pinned release)
    "taplo": "0.10.",  # Minor version check (manually installed from latest release)
    "cargo-binstall": "1.19.",  # Minor version check (installed from latest release),
    "typstyle": "0.14.",  # Minor version check (installed from latest release)
    "vig_utils": "0.1.",  # Minor version check (installed via uv pip)
    "tmux": "3.3",  # Major.minor version check (from apt package)
    "rsync": "3.2",  # Major.minor version check (from apt package)
    # ── Agent-CLI / TUI-debug toolkit (#545) ───────────────────────────────
    # Only major-line checks; latest-of-line tracked elsewhere.
    "ripgrep": "13.",  # apt package
    "fd": "8.",  # apt fd-find package, symlinked as fd
    "bat": "0.",  # apt bat package, symlinked as bat
    "fzf": "0.",  # apt package
    "expect": "5.",  # apt package
    "nvim": "0.7",  # apt neovim package (Debian bookworm pins 0.7.x)
    "eza": "0.",  # binary release
    "delta": "0.",  # binary release
    "lazygit": "0.",  # binary release
    "zoxide": "0.",  # binary release
    "starship": "1.",  # binary release
    "freeze": "0.",  # binary release (charm-freeze)
    "claude": "2.",  # binary install via official installer
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


class TestSystemTools:
    """Test that system tools are installed with correct versions."""

    def test_git_installed(self, host):
        """Test that git is installed."""
        assert host.package("git").is_installed, "Git is not installed"

    def test_git_version(self, host):
        """Test that git version is correct."""
        result = host.run("git --version")
        assert result.rc == 0, "git --version failed"
        assert "git version" in result.stdout.lower()
        expected = EXPECTED_VERSIONS["git"]
        assert expected in result.stdout, (
            f"Expected git {expected}x, got: {result.stdout}"
        )

    def test_curl_installed(self, host):
        """Test that curl is installed."""
        assert host.package("curl").is_installed, "curl is not installed"

    def test_curl_version(self, host):
        """Test that curl version is correct."""
        result = host.run("curl --version")
        assert result.rc == 0, "curl --version failed"
        assert "curl" in result.stdout.lower()
        expected = EXPECTED_VERSIONS["curl"]
        assert expected in result.stdout, (
            f"Expected curl {expected}x, got: {result.stdout}"
        )

    def test_openssh_client_installed(self, host):
        """Test that openssh-client is installed."""
        assert host.package("openssh-client").is_installed, (
            "openssh-client is not installed"
        )

    def test_nano_installed(self, host):
        """Test that nano is installed."""
        assert host.package("nano").is_installed, "nano is not installed"

    def test_gh_installed(self, host):
        """Test that GitHub CLI (gh) is installed."""
        # gh is manually installed, so check for the binary file
        assert host.file("/usr/local/bin/gh").exists, "GitHub CLI (gh) binary not found"
        assert host.file("/usr/local/bin/gh").is_file, "GitHub CLI (gh) is not a file"

    def test_gh_version(self, host):
        """Test that gh version is correct."""
        result = host.run("gh --version")
        assert result.rc == 0, "gh --version failed"
        assert "gh version" in result.stdout.lower()
        expected = EXPECTED_VERSIONS["gh"]
        assert expected in result.stdout, (
            f"Expected gh {expected}, got: {result.stdout}"
        )

    def test_just_installed(self, host):
        """Test that just is installed."""
        # just is manually installed, so check for the binary file
        assert host.file("/usr/local/bin/just").exists, "just binary not found"
        assert host.file("/usr/local/bin/just").is_file, "just is not a file"

    def test_just_version(self, host):
        """Test that just version is correct."""
        result = host.run("just --version")
        assert result.rc == 0, "just --version failed"
        assert "just" in result.stdout.lower()
        expected = EXPECTED_VERSIONS["just"]
        assert expected in result.stdout, (
            f"Expected just {expected}, got: {result.stdout}"
        )

    def test_hadolint_installed(self, host):
        """Test that hadolint is installed."""
        # hadolint is manually installed, so check for the binary file
        assert host.file("/usr/local/bin/hadolint").exists, "hadolint binary not found"
        assert host.file("/usr/local/bin/hadolint").is_file, "hadolint is not a file"

    def test_hadolint_version(self, host):
        """Test that hadolint version is correct."""
        result = host.run("hadolint --version")
        assert result.rc == 0, "hadolint --version failed"
        expected = EXPECTED_VERSIONS["hadolint"]
        assert expected in result.stdout, (
            f"Expected hadolint {expected}, got: {result.stdout}"
        )

    def test_taplo_installed(self, host):
        """Test that taplo (TOML formatter/linter) is installed."""
        assert host.file("/usr/local/bin/taplo").exists, "taplo binary not found"
        assert host.file("/usr/local/bin/taplo").is_file, "taplo is not a file"

    def test_taplo_version(self, host):
        """Test that taplo version is correct."""
        result = host.run("taplo --version")
        assert result.rc == 0, "taplo --version failed"
        expected = EXPECTED_VERSIONS["taplo"]
        assert expected in result.stdout, (
            f"Expected taplo {expected}, got: {result.stdout}"
        )

    def test_cursor_agent_installed(self, host):
        """Test that cursor-agent CLI (agent) is installed."""
        result = host.run("agent --version")
        if result.rc != 0:
            pytest.skip("cursor-agent not available (external CDN issue)")

    def test_cargo_binstall(self, host):
        """Test that cargo-binstall is installed and right version."""
        result = host.run("cargo-binstall -V")
        assert result.rc == 0, "cargo-binstall -V failed"
        expected = EXPECTED_VERSIONS["cargo-binstall"]
        assert expected in result.stdout, (
            f"Expected cargo-binstall {expected}, got: {result.stdout}"
        )

    def test_typstyle(self, host):
        """Test that typstyle is installed and right version."""
        result = host.run("typstyle --version")
        assert result.rc == 0, "typstyle --version failed"
        expected = EXPECTED_VERSIONS["typstyle"]
        assert expected in result.stdout, (
            f"Expected typstyle {expected}, got: {result.stdout}"
        )

    def test_just_lsp_installed(self, host):
        """Test that just-lsp is installed."""
        result = host.run("just-lsp --version")
        assert result.rc == 0, "just-lsp --version failed"
        assert "just-lsp" in result.stdout.lower(), (
            f"Expected just-lsp version output, got: {result.stdout}"
        )

    def test_tmux_installed(self, host):
        """Test that tmux is installed."""
        assert host.package("tmux").is_installed, "tmux is not installed"

    def test_tmux_version(self, host):
        """Test that tmux version is correct."""
        result = host.run("tmux -V")
        assert result.rc == 0, "tmux -V failed"
        expected = EXPECTED_VERSIONS["tmux"]
        assert expected in result.stdout, (
            f"Expected tmux {expected}, got: {result.stdout}"
        )

    def test_rsync_installed(self, host):
        """Test that rsync is installed."""
        assert host.package("rsync").is_installed, "rsync is not installed"

    def test_rsync_version(self, host):
        """Test that rsync version is correct."""
        result = host.run("rsync --version")
        assert result.rc == 0, "rsync --version failed"
        expected = EXPECTED_VERSIONS["rsync"]
        assert expected in result.stdout, (
            f"Expected rsync {expected}, got: {result.stdout}"
        )

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


class TestAgentToolkit:
    """
    Agent-CLI + TUI-debug + Claude Code toolkit (issue #545).

    Verifies the bundle that closes recurring gaps for AI-assisted development:
      - modern CLI replacements (rg/fd/bat/eza/delta) — what agents reach for
      - TUI debug primitives (tmux already, expect, freeze)
      - in-container editor (neovim) for git commit/edit fallback
      - Claude Code baked + IS_SANDBOX=1 + cc/cld aliases

    Each tool gets two asserts: presence on PATH (or expected install path)
    and a successful --version invocation. Version-string checks use
    EXPECTED_VERSIONS' loose major-line prefixes — tight pins live elsewhere.
    """

    # ── apt-installed essentials ─────────────────────────────────────────────

    def test_ripgrep_installed(self, host):
        assert host.package("ripgrep").is_installed, "ripgrep not installed"

    def test_ripgrep_version(self, host):
        result = host.run("rg --version")
        assert result.rc == 0, f"rg --version failed: {result.stderr}"
        expected = EXPECTED_VERSIONS["ripgrep"]
        assert expected in result.stdout, (
            f"Expected rg {expected}x, got: {result.stdout}"
        )

    def test_fd_installed(self, host):
        # Debian's fd-find ships as `fdfind`; we add /usr/local/bin/fd symlink.
        assert host.file("/usr/local/bin/fd").exists, "fd symlink missing"
        assert host.file("/usr/bin/fdfind").exists, "fdfind binary missing"

    def test_fd_version(self, host):
        result = host.run("fd --version")
        assert result.rc == 0, f"fd --version failed: {result.stderr}"
        expected = EXPECTED_VERSIONS["fd"]
        assert expected in result.stdout, (
            f"Expected fd {expected}x, got: {result.stdout}"
        )

    def test_bat_installed(self, host):
        assert host.file("/usr/local/bin/bat").exists, "bat symlink missing"
        assert host.file("/usr/bin/batcat").exists, "batcat binary missing"

    def test_bat_version(self, host):
        result = host.run("bat --version")
        assert result.rc == 0, f"bat --version failed: {result.stderr}"
        expected = EXPECTED_VERSIONS["bat"]
        assert expected in result.stdout, (
            f"Expected bat {expected}x, got: {result.stdout}"
        )

    def test_fzf_installed(self, host):
        assert host.package("fzf").is_installed, "fzf not installed"

    def test_fzf_version(self, host):
        result = host.run("fzf --version")
        assert result.rc == 0, f"fzf --version failed: {result.stderr}"
        expected = EXPECTED_VERSIONS["fzf"]
        assert expected in result.stdout, (
            f"Expected fzf {expected}x, got: {result.stdout}"
        )

    def test_expect_installed(self, host):
        assert host.package("expect").is_installed, "expect not installed"

    def test_expect_version(self, host):
        # `expect -v` returns version
        result = host.run("expect -v")
        assert result.rc == 0, f"expect -v failed: {result.stderr}"
        expected = EXPECTED_VERSIONS["expect"]
        assert expected in result.stdout, (
            f"Expected expect {expected}x, got: {result.stdout}"
        )

    def test_neovim_installed(self, host):
        assert host.package("neovim").is_installed, "neovim not installed"

    def test_neovim_version(self, host):
        result = host.run("nvim --version")
        assert result.rc == 0, f"nvim --version failed: {result.stderr}"
        expected = EXPECTED_VERSIONS["nvim"]
        assert expected in result.stdout, (
            f"Expected nvim {expected}x, got: {result.stdout}"
        )

    # ── binary release downloads ─────────────────────────────────────────────

    def test_eza_installed(self, host):
        assert host.file("/usr/local/bin/eza").exists, "eza binary missing"

    def test_eza_version(self, host):
        result = host.run("eza --version")
        assert result.rc == 0, f"eza --version failed: {result.stderr}"
        expected = EXPECTED_VERSIONS["eza"]
        assert expected in result.stdout, (
            f"Expected eza {expected}x, got: {result.stdout}"
        )

    def test_delta_installed(self, host):
        assert host.file("/usr/local/bin/delta").exists, "delta binary missing"

    def test_delta_version(self, host):
        result = host.run("delta --version")
        assert result.rc == 0, f"delta --version failed: {result.stderr}"
        expected = EXPECTED_VERSIONS["delta"]
        assert expected in result.stdout, (
            f"Expected delta {expected}x, got: {result.stdout}"
        )

    def test_lazygit_installed(self, host):
        assert host.file("/usr/local/bin/lazygit").exists, "lazygit binary missing"

    def test_lazygit_version(self, host):
        result = host.run("lazygit --version")
        assert result.rc == 0, f"lazygit --version failed: {result.stderr}"
        expected = EXPECTED_VERSIONS["lazygit"]
        assert expected in result.stdout, (
            f"Expected lazygit {expected}x, got: {result.stdout}"
        )

    def test_zoxide_installed(self, host):
        assert host.file("/usr/local/bin/zoxide").exists, "zoxide binary missing"

    def test_zoxide_version(self, host):
        result = host.run("zoxide --version")
        assert result.rc == 0, f"zoxide --version failed: {result.stderr}"
        expected = EXPECTED_VERSIONS["zoxide"]
        assert expected in result.stdout, (
            f"Expected zoxide {expected}x, got: {result.stdout}"
        )

    def test_starship_installed(self, host):
        assert host.file("/usr/local/bin/starship").exists, "starship binary missing"

    def test_starship_version(self, host):
        result = host.run("starship --version")
        assert result.rc == 0, f"starship --version failed: {result.stderr}"
        expected = EXPECTED_VERSIONS["starship"]
        assert expected in result.stdout, (
            f"Expected starship {expected}x, got: {result.stdout}"
        )

    def test_freeze_installed(self, host):
        assert host.file("/usr/local/bin/freeze").exists, "freeze binary missing"

    def test_freeze_version(self, host):
        result = host.run("freeze --version")
        assert result.rc == 0, f"freeze --version failed: {result.stderr}"
        expected = EXPECTED_VERSIONS["freeze"]
        assert expected in result.stdout, (
            f"Expected freeze {expected}x, got: {result.stdout}"
        )

    # ── Claude Code + sandbox + aliases ──────────────────────────────────────

    def test_claude_installed(self, host):
        # Installed by the official installer to ~/.local/bin/claude, then
        # symlinked to /usr/local/bin/claude so it's on the default PATH.
        assert host.file("/usr/local/bin/claude").exists, "claude symlink missing"

    def test_claude_version(self, host):
        result = host.run("claude --version")
        assert result.rc == 0, f"claude --version failed: {result.stderr}"
        expected = EXPECTED_VERSIONS["claude"]
        assert expected in result.stdout, (
            f"Expected claude {expected}x, got: {result.stdout}"
        )

    def test_is_sandbox_env_set(self, host):
        # IS_SANDBOX=1 is what lets `claude --dangerously-skip-permissions`
        # run as root inside the container without the uid-0 refusal. Set as
        # a layer ENV so it's present in every shell + every claude invocation.
        result = host.run("printenv IS_SANDBOX")
        assert result.rc == 0, "IS_SANDBOX env var not set"
        assert result.stdout.strip() == "1", (
            f"Expected IS_SANDBOX=1, got: {result.stdout!r}"
        )

    def test_cc_alias_in_bashrc(self, host):
        # The cc/cld aliases are user-facing ergonomics; verify the literal
        # strings landed in /root/.bashrc rather than executing the aliases
        # (testinfra `host.run` runs non-interactively; aliases would not
        # be expanded).
        bashrc = host.file("/root/.bashrc")
        assert bashrc.exists, "/root/.bashrc missing"
        content = bashrc.content_string
        assert 'alias cc="claude"' in content, "cc alias not in /root/.bashrc"
        assert 'alias cld="claude --dangerously-skip-permissions"' in content, (
            "cld alias not in /root/.bashrc"
        )


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
        """Test that pre-commit is installed."""
        result = host.run("pre-commit --version")
        assert result.rc == 0, "pre-commit --version failed"
        assert "pre-commit" in result.stdout.lower()
        expected = EXPECTED_VERSIONS["pre_commit"]
        assert expected in result.stdout, (
            f"Expected pre-commit {expected}, got: {result.stdout}"
        )

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


class TestEnvironmentVariables:
    """Test that environment variables are set correctly."""

    @pytest.mark.parametrize(
        ("name", "expected"),
        [
            ("DEBIAN_FRONTEND", "noninteractive"),
            ("LANG", "en_US.UTF-8"),
            ("LANGUAGE", "en_US:en"),
            ("LC_ALL", "en_US.UTF-8"),
            ("PYTHONUNBUFFERED", "1"),
            ("IN_CONTAINER", "true"),
            ("PRE_COMMIT_HOME", "/opt/pre-commit-cache"),
            ("UV_PROJECT_ENVIRONMENT", "/root/assets/workspace/.venv"),
            ("VIRTUAL_ENV", "/root/assets/workspace/.venv"),
        ],
        ids=[
            "debian_frontend",
            "lang",
            "language",
            "lc_all",
            "pythonunbuffered",
            "in_container",
            "pre_commit_home",
            "uv_project_environment",
            "virtual_env",
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
        "path_entry",
        [
            "/root/.local/bin",
            "/root/.cargo/bin",
        ],
        ids=["cursor_agent_path", "cargo_path"],
    )
    def test_path_contains_required_entries(self, host, path_entry):
        """Test that PATH includes required binary locations."""
        result = host.run("printenv PATH")
        assert result.rc == 0, "Failed to read PATH"
        path_entries = result.stdout.strip().split(":")
        assert path_entry in path_entries, (
            f"Expected PATH to contain {path_entry}, got: {result.stdout.strip()}"
        )


class TestFileStructure:
    """Test that expected files and directories exist."""

    def test_workspace_directory_exists(self, host):
        """Test that workspace directory exists."""
        assert host.file("/workspace").is_directory, "Workspace directory not found"

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
        """Test that pre-commit hooks are pre-initialized at system cache location."""
        # Pre-commit cache is built to /opt/pre-commit-cache (not in workspace assets)
        # This allows init-workspace.sh to skip excluding it during copy
        cache_dir = host.file("/opt/pre-commit-cache")
        assert cache_dir.exists, (
            "Pre-commit cache directory not found at /opt/pre-commit-cache"
        )
        assert cache_dir.is_directory, "Pre-commit cache is not a directory"
        # Verify the cache directory is not empty (contains installed hooks)
        result = host.run('test -n "$(ls -A /opt/pre-commit-cache 2>/dev/null)"')
        assert result.rc == 0, (
            "Pre-commit cache directory is empty - hooks were not initialized"
        )

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
