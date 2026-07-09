"""
Integration tests for install.sh — full deployment workflow.

These tests require a built container image (ghcr.io/vig-os/devcontainer:<tag>)
and are run by the test-integration CI job, NOT project-checks.

Tests the full install.sh workflow which:
1. Pulls the container image
2. Runs init-workspace.sh with --no-prompts
3. Runs host-side user configuration (copy-host-user-conf.sh)
4. Creates a fully initialized workspace
"""

import atexit
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest


class TestInstallScriptIntegration:
    """Integration tests for install.sh - full deployment workflow.

    These tests run the full install.sh workflow which:
    1. Pulls the container image
    2. Runs init-workspace.sh with --no-prompts
    3. Creates a fully initialized workspace
    """

    @pytest.fixture(scope="class")
    @staticmethod
    def install_workspace(container_image):
        """
        Deploy devcontainer using install.sh (not init-workspace.sh directly).
        Tests the full user-facing workflow.

        This fixture uses install.sh which:
        - Derives SHORT_NAME from directory name
        - Uses default ORG_NAME (vigOS/devc)
        - Runs non-interactively
        """
        project_root = Path(__file__).resolve().parents[1]
        tests_dir = project_root / "tests"
        install_script = project_root / "install.sh"

        # Create temp directory with a name that tests sanitization
        # Name has hyphens and mixed case to verify sanitization
        tests_tmp_dir = tests_dir / "tmp"
        tests_tmp_dir.mkdir(parents=True, exist_ok=True)
        workspace_dir = tempfile.mkdtemp(
            dir=str(tests_tmp_dir), prefix="Install-Test-Project-"
        )
        workspace_path = Path(workspace_dir)

        def cleanup():
            if workspace_path.exists():
                shutil.rmtree(workspace_path, ignore_errors=True)

        atexit.register(cleanup)

        # Extract version from container_image (e.g., "ghcr.io/vig-os/devcontainer:dev" -> "dev")
        version = container_image.split(":")[-1]

        # Run install.sh
        print(f"\n[DEBUG] Running install.sh with version={version}")
        print(f"[DEBUG] Target directory: {workspace_path}")

        result = subprocess.run(
            [
                str(install_script),
                "--version",
                version,
                "--podman",
                "--skip-pull",
                str(workspace_path),
            ],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(project_root),
        )

        if result.returncode != 0:
            cleanup()
            pytest.fail(
                f"install.sh failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
            )

        print("[DEBUG] install.sh completed successfully")

        yield workspace_path
        cleanup()

    def test_install_creates_devcontainer_directory(self, install_workspace):
        """Test install.sh creates .devcontainer directory."""
        devcontainer_dir = install_workspace / ".devcontainer"
        assert devcontainer_dir.exists(), ".devcontainer directory not created"
        assert devcontainer_dir.is_dir(), ".devcontainer is not a directory"

    def test_dry_run_smoke_test_flag_forwarded(self):
        """Test install.sh forwards --smoke-test to init-workspace.sh in dry-run."""
        project_root = Path(__file__).resolve().parents[1]
        install_script = project_root / "install.sh"

        result = subprocess.run(
            [str(install_script), "--dry-run", "--smoke-test", "."],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(project_root),
        )

        assert result.returncode == 0, (
            f"install.sh --dry-run --smoke-test failed:\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
        assert "--smoke-test" in result.stdout, (
            "Expected --smoke-test to be forwarded in dry-run command output"
        )

    def test_dry_run_name_sanitization_trims_trailing_separator(self):
        """Test --name sanitization trims trailing separators for valid package name."""
        project_root = Path(__file__).resolve().parents[1]
        install_script = project_root / "install.sh"

        result = subprocess.run(
            [str(install_script), "--dry-run", "--name", "Install-Test-Project-", "."],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(project_root),
        )

        assert result.returncode == 0, (
            f"install.sh --dry-run --name failed:\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
        assert "SHORT_NAME=install_test_project" in result.stdout, (
            "Expected sanitized name without trailing underscore in dry-run output"
        )
        assert "SHORT_NAME=install_test_project_" not in result.stdout, (
            "Sanitized name should not end with an underscore"
        )

    def test_install_creates_devcontainer_json(self, install_workspace):
        """Test install.sh creates devcontainer.json."""
        devcontainer_json = install_workspace / ".devcontainer" / "devcontainer.json"
        assert devcontainer_json.exists(), "devcontainer.json not created"

    def test_install_does_not_scaffold_pyproject(self, install_workspace):
        """The scaffold is language-neutral (#929): no pyproject.toml is shipped.

        Python is opt-in via `nix flake init -t ...#python` (#930).
        """
        pyproject = install_workspace / "pyproject.toml"
        assert not pyproject.exists(), (
            "pyproject.toml should not be scaffolded by a language-neutral template"
        )

    def test_install_derives_short_name_from_directory(self, install_workspace):
        """Test SHORT_NAME is correctly derived from directory name.

        Directory name starts with "Install-Test-Project-" which should
        become "install_test_project_..." (lowercase, underscores). Read it
        back from justfile.project (`project := "{{SHORT_NAME}}"`), a
        placeholder-bearing file the language-neutral scaffold still ships.
        """
        justfile_project = install_workspace / "justfile.project"
        content = justfile_project.read_text()

        # The directory name is "Install-Test-Project-XXXXX"
        # SHORT_NAME should be sanitized to lowercase with underscores
        assert "install_test_project" in content.lower(), (
            f"SHORT_NAME not derived correctly from directory name.\n"
            f"Expected 'install_test_project' in justfile.project, got:\n{content[:500]}"
        )

    def test_install_uses_default_org_name(self, install_workspace):
        """Test ORG_NAME defaults to vigOS."""
        license_file = install_workspace / "LICENSE"
        assert license_file.exists(), "LICENSE file not created"

        content = license_file.read_text()
        assert "vigOS" in content, (
            f"Expected 'vigOS' in LICENSE (default ORG_NAME), "
            f"but found: {content[-500:]}"
        )

    def test_install_replaces_short_name_placeholder(self, install_workspace):
        """Test {{SHORT_NAME}} placeholder is replaced everywhere."""
        for file_path in install_workspace.rglob("*"):
            if file_path.is_file():
                try:
                    content = file_path.read_text()
                    assert "{{SHORT_NAME}}" not in content, (
                        f"{{{{SHORT_NAME}}}} placeholder not replaced in {file_path}"
                    )
                except UnicodeDecodeError:
                    # Skip binary files
                    continue

    def test_install_replaces_image_tag_placeholder(self, install_workspace):
        """Test {{IMAGE_TAG}} placeholder is replaced everywhere."""
        for file_path in install_workspace.rglob("*"):
            if file_path.is_file():
                try:
                    content = file_path.read_text()
                    assert "{{IMAGE_TAG}}" not in content, (
                        f"{{{{IMAGE_TAG}}}} placeholder not replaced in {file_path}"
                    )
                except UnicodeDecodeError:
                    continue

    def test_install_does_not_scaffold_src(self, install_workspace):
        """The language-neutral scaffold ships no src/ package dir (#929).

        Python is opt-in via `nix flake init -t ...#python` (#930).
        """
        src_dir = install_workspace / "src"
        assert not src_dir.exists(), (
            "src/ should not be scaffolded by a language-neutral template"
        )

    def test_install_does_not_scaffold_tests(self, install_workspace):
        """The language-neutral scaffold ships no tests/ dir (#929)."""
        tests_dir = install_workspace / "tests"
        assert not tests_dir.exists(), (
            "tests/ should not be scaffolded by a language-neutral template"
        )

    def test_install_creates_githooks(self, install_workspace):
        """Test .githooks directory is created."""
        githooks_dir = install_workspace / ".githooks"
        assert githooks_dir.exists(), ".githooks directory not created"

    def test_install_replaces_org_name_placeholder(self, install_workspace):
        """Test {{ORG_NAME}} placeholder is replaced everywhere."""
        for file_path in install_workspace.rglob("*"):
            if file_path.is_file():
                try:
                    content = file_path.read_text()
                    assert "{{ORG_NAME}}" not in content, (
                        f"{{{{ORG_NAME}}}} placeholder not replaced in {file_path}"
                    )
                except UnicodeDecodeError:
                    # Skip binary files
                    continue

    def test_install_creates_pre_commit_config(self, install_workspace):
        """Test .pre-commit-config.yaml is created."""
        precommit_config = install_workspace / ".pre-commit-config.yaml"
        assert precommit_config.exists(), ".pre-commit-config.yaml not created"

    def test_install_creates_conf_directory(self, install_workspace):
        """Test install.sh creates .devcontainer/.conf/ via user config script."""
        conf_dir = install_workspace / ".devcontainer" / ".conf"
        assert conf_dir.exists(), (
            ".devcontainer/.conf/ directory not created by copy-host-user-conf.sh"
        )
        assert conf_dir.is_dir(), ".devcontainer/.conf/ is not a directory"

    def test_install_conf_directory_contains_expected_files(self, install_workspace):
        """Test .devcontainer/.conf/ contains expected configuration files.

        Files are split into two categories:
        - Required: always created by copy-host-user-conf.sh (git config)
        - Optional: only created when host has the corresponding tool/config
          (SSH key, allowed-signers, gh CLI auth, gh CLI config directory)
        """
        conf_dir = install_workspace / ".devcontainer" / ".conf"

        # Required files — always generated from git config
        required_files = {
            ".gitconfig.global",
            ".gitconfig",
        }

        for filename in required_files:
            file_path = conf_dir / filename
            assert file_path.exists(), (
                f"Expected file '{filename}' not found in .devcontainer/.conf/"
            )
            assert file_path.is_file(), f"'{filename}' exists but is not a regular file"

        # Optional files — depend on host environment (SSH key, git
        # allowed-signers, gh CLI authentication).  Warn instead of failing so
        # the test is stable in CI where these may not be configured.
        optional_files = {
            "id_ed25519_github.pub": "SSH public key (~/.ssh/id_ed25519_github.pub)",
            "allowed-signers": "Git allowed-signers (~/.config/git/allowed-signers)",
            ".gh_token": "GitHub CLI authentication (gh auth login)",
        }

        for filename, description in optional_files.items():
            file_path = conf_dir / filename
            if not file_path.exists():
                import warnings

                warnings.warn(
                    f"{filename} not found in .devcontainer/.conf/ "
                    f"(this is optional if {description} is not available on host)",
                    stacklevel=2,
                )
            else:
                assert file_path.is_file(), (
                    f"'{filename}' exists but is not a regular file"
                )

        # Optional subdirectory — gh CLI config (~/.config/gh)
        gh_dir = conf_dir / "gh"
        if not gh_dir.exists():
            import warnings

            warnings.warn(
                "gh/ subdirectory not found in .devcontainer/.conf/ "
                "(this is optional if ~/.config/gh is not present on host)",
                stacklevel=2,
            )
        else:
            assert gh_dir.is_dir(), "'gh' exists but is not a directory"

            # Check gh/ subdirectory contents
            expected_gh_files = {"config.yml", "hosts.yml"}
            for filename in expected_gh_files:
                file_path = gh_dir / filename
                assert file_path.exists(), (
                    f"Expected file '{filename}' not found in .devcontainer/.conf/gh/"
                )
                assert file_path.is_file(), (
                    f"'{filename}' exists in gh/ but is not a regular file"
                )

    def test_install_creates_git_repository(self, install_workspace):
        """Test install.sh initializes a git repository."""
        git_dir = install_workspace / ".git"
        assert git_dir.exists(), ".git directory not created"
        assert git_dir.is_dir(), ".git is not a directory"

    def test_install_initial_commit(self, install_workspace):
        """Test git repository has correct initial commit."""
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(install_workspace),
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, "Failed to get HEAD commit"
        assert result.stdout.strip(), "No initial commit found"

        result = subprocess.run(
            ["git", "log", "-1", "--pretty=%s"],
            cwd=str(install_workspace),
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, "Failed to get commit message"
        assert result.stdout.strip() == "chore: initial project scaffold", (
            f"Expected 'chore: initial project scaffold', got: {result.stdout.strip()}"
        )

    def test_install_git_branches(self, install_workspace):
        """Test git repository has main and dev branches."""
        result = subprocess.run(
            ["git", "rev-parse", "--verify", "main"],
            cwd=str(install_workspace),
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, "main branch not found"

        result = subprocess.run(
            ["git", "rev-parse", "--verify", "dev"],
            cwd=str(install_workspace),
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, "dev branch not found"

    def test_install_git_all_files_committed(self, install_workspace):
        """Test all workspace files are committed (no uncommitted changes)."""
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(install_workspace),
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, "Failed to check git status"
        # Should be empty (no uncommitted changes)
        assert not result.stdout.strip(), f"Found uncommitted changes:\n{result.stdout}"


class TestHostScriptShebangPortability:
    """Assert host-executed scripts use a portable shebang.

    These scripts run on the *host* (not inside the container), so they must
    not hardcode ``#!/bin/bash``: NixOS and other distros that follow the
    Filesystem Hierarchy Standard loosely have no ``/bin/bash``, which makes
    them fail to execute. The portable form ``#!/usr/bin/env bash`` resolves
    ``bash`` via ``PATH`` and works everywhere. Refs #687.

    This is a pure content check — it needs no built container image — so it
    runs in any pytest invocation that collects this module.
    """

    # Host-executed scripts that must carry the portable shebang. Scoped to
    # the three scripts in issue #687; the broader in-container sweep is out
    # of scope.
    HOST_SCRIPTS = (
        "install.sh",
        "assets/workspace/.devcontainer/scripts/initialize.sh",
        "assets/workspace/.devcontainer/scripts/version-check.sh",
    )

    PORTABLE_SHEBANG = "#!/usr/bin/env bash"

    @pytest.mark.parametrize("rel_path", HOST_SCRIPTS)
    def test_host_script_uses_portable_shebang(self, rel_path):
        """Each host-executed script must start with #!/usr/bin/env bash."""
        project_root = Path(__file__).resolve().parents[1]
        script = project_root / rel_path
        assert script.exists(), f"Expected host script not found: {rel_path}"

        first_line = script.read_text().splitlines()[0]
        assert first_line == self.PORTABLE_SHEBANG, (
            f"{rel_path} must use the portable shebang "
            f"'{self.PORTABLE_SHEBANG}' (NixOS has no /bin/bash), "
            f"but found: {first_line!r}"
        )
