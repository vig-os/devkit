"""
DevContainer integration tests for Base Development Environment.

These tests verify that the container works correctly as a devcontainer,
including template initialization, configuration files, and scripts.

Derived containers can inherit from these test classes to verify that
devcontainer functionality works correctly in their containers too.
"""

import os
import re
import subprocess
import time
from pathlib import Path

import pytest
import yaml

from .conftest import _build_podman_cmd, _load_jsonc, _run_noninteractive_init, dc_exec

# Scaffold sources for content-only assertions (TestVersionCheckScaffold):
# deployment of these files into a workspace is covered by the structure and
# manifest tests, so content pins read the assets directly and need no
# container or workspace fixture.
_WORKSPACE_ASSETS = Path(__file__).resolve().parents[1] / "assets" / "workspace"


class TestDevContainerStructure:
    """Test that devcontainer structure is created correctly."""

    def test_devcontainer_directory_exists(self, initialized_workspace):
        """Test that .devcontainer directory exists."""
        devcontainer_dir = initialized_workspace / ".devcontainer"
        assert devcontainer_dir.exists(), ".devcontainer directory not found"
        assert devcontainer_dir.is_dir(), ".devcontainer is not a directory"

    def test_devcontainer_scripts_directory_exists(self, initialized_workspace):
        """Test that scripts directory exists."""
        scripts_dir = initialized_workspace / ".devcontainer" / "scripts"
        assert scripts_dir.exists(), ".devcontainer/scripts directory not found"
        assert scripts_dir.is_dir(), ".devcontainer/scripts is not a directory"

    def test_setup_scripts_exist(self, initialized_workspace):
        """Test that all setup scripts exist and are executable."""
        scripts_dir = initialized_workspace / ".devcontainer" / "scripts"
        expected_scripts = [
            "copy-host-user-conf.sh",
            "init-git.sh",
            "setup-git-conf.sh",
            "verify-auth.sh",
            "init-precommit.sh",
            "post-attach.sh",
            "post-create.sh",
            "initialize.sh",
        ]

        for script_name in expected_scripts:
            script = scripts_dir / script_name
            assert script.exists(), f"{script_name} not found"
            assert script.is_file(), f"{script_name} is not a file"
            assert script.stat().st_mode & 0o111, f"{script_name} is not executable"

    def test_template_files_copied(self, initialized_workspace):
        """Test that minimal template files are copied to workspace."""
        # Check for README.md
        readme = initialized_workspace / "README.md"
        assert readme.exists(), "README.md not found in workspace"

        # Check for CHANGELOG.md
        changelog = initialized_workspace / "CHANGELOG.md"
        assert changelog.exists(), "CHANGELOG.md not found in workspace"


class TestDevContainerJson:
    """Test devcontainer.json configuration."""

    def test_devcontainer_json_valid(self, initialized_workspace):
        """Test that devcontainer.json is valid JSON."""
        devcontainer_json = (
            initialized_workspace / ".devcontainer" / "devcontainer.json"
        )

        config = _load_jsonc(devcontainer_json)

        assert isinstance(config, dict), "devcontainer.json is not a valid JSON object"

    def test_devcontainer_json_name(self, initialized_workspace):
        """Test that devcontainer.json has correct name."""
        devcontainer_json = (
            initialized_workspace / ".devcontainer" / "devcontainer.json"
        )

        config = _load_jsonc(devcontainer_json)

        assert "name" in config, "devcontainer.json missing 'name' field"

        # Verify name is not empty
        assert len(config["name"]) > 0, "Name should not be empty"

        # The name should contain the project name (test_project) from init-workspace
        assert "test_project" in config["name"].lower(), (
            f"Expected name to contain 'test_project', got: {config['name']}"
        )

    def test_devcontainer_json_docker_compose_file(self, initialized_workspace):
        """Test that devcontainer.json references docker-compose.yml."""
        devcontainer_json = (
            initialized_workspace / ".devcontainer" / "devcontainer.json"
        )

        config = _load_jsonc(devcontainer_json)

        assert "dockerComposeFile" in config, (
            "devcontainer.json missing 'dockerComposeFile' field"
        )
        # dockerComposeFile can be a string or array (includes override file)
        docker_compose_files = config["dockerComposeFile"]
        if isinstance(docker_compose_files, str):
            assert docker_compose_files == "docker-compose.yml", (
                f"Expected dockerComposeFile='docker-compose.yml', got: {docker_compose_files}"
            )
        elif isinstance(docker_compose_files, list):
            assert "docker-compose.yml" in docker_compose_files, (
                f"Expected 'docker-compose.yml' in {docker_compose_files}"
            )
            assert "docker-compose.project.yaml" in docker_compose_files, (
                f"Expected 'docker-compose.project.yaml' in {docker_compose_files}"
            )
        else:
            pytest.fail(
                f"Unexpected dockerComposeFile type: {type(docker_compose_files)}"
            )

    def test_devcontainer_json_service(self, initialized_workspace):
        """Test that devcontainer.json specifies the service name."""
        devcontainer_json = (
            initialized_workspace / ".devcontainer" / "devcontainer.json"
        )

        config = _load_jsonc(devcontainer_json)

        assert "service" in config, "devcontainer.json missing 'service' field"
        # Service name is derived from SHORT_NAME (test_project in tests)
        assert config["service"] in ["devcontainer", "test_project"], (
            f"Expected service='devcontainer' or 'test_project', got: {config['service']}"
        )

    def test_devcontainer_json_workspace_folder(self, initialized_workspace):
        """Test that workspaceFolder is set correctly to project subdirectory."""
        devcontainer_json = (
            initialized_workspace / ".devcontainer" / "devcontainer.json"
        )

        config = _load_jsonc(devcontainer_json)

        assert "workspaceFolder" in config, (
            "devcontainer.json missing 'workspaceFolder' field"
        )
        # workspaceFolder should be /workspace/<project_name>, not /workspace
        assert "/workspace/" in config["workspaceFolder"], (
            f"Expected workspaceFolder to be in /workspace/ subdirectory, got: {config['workspaceFolder']}"
        )
        assert config["workspaceFolder"] != "/workspace", (
            "workspaceFolder should be a subdirectory, not '/workspace' directly"
        )
        # Should contain the project name (test_project)
        assert "test_project" in config["workspaceFolder"].lower(), (
            f"workspaceFolder should contain project name, got: {config['workspaceFolder']}"
        )

    def test_devcontainer_json_vscode_extensions(self, initialized_workspace):
        """Test that VS Code extensions are configured."""
        devcontainer_json = (
            initialized_workspace / ".devcontainer" / "devcontainer.json"
        )

        config = _load_jsonc(devcontainer_json)

        assert "customizations" in config, (
            "devcontainer.json missing 'customizations' field"
        )
        assert "vscode" in config["customizations"], (
            "devcontainer.json missing 'vscode' customizations"
        )
        assert "extensions" in config["customizations"]["vscode"], (
            "devcontainer.json missing 'extensions' in vscode customizations"
        )

        extensions = config["customizations"]["vscode"]["extensions"]
        assert isinstance(extensions, list), "Extensions should be a list"
        assert len(extensions) > 0, "No VS Code extensions configured"

    def test_devcontainer_json_vscode_settings(self, initialized_workspace):
        """Test that VS Code settings are configured."""
        devcontainer_json = (
            initialized_workspace / ".devcontainer" / "devcontainer.json"
        )

        config = _load_jsonc(devcontainer_json)

        assert "settings" in config["customizations"]["vscode"], (
            "devcontainer.json missing 'settings' in vscode customizations"
        )

        settings = config["customizations"]["vscode"]["settings"]
        assert "python.defaultInterpreterPath" in settings, (
            "Python interpreter path not configured"
        )
        assert (
            settings["python.defaultInterpreterPath"]
            == "/root/assets/workspace/.venv/bin/python"
        ), (
            f"Expected Python path '/root/assets/workspace/.venv/bin/python', got: {settings['python.defaultInterpreterPath']}"
        )

    def test_devcontainer_json_initialize_command(self, initialized_workspace):
        """Test that initializeCommand is configured."""
        devcontainer_json = (
            initialized_workspace / ".devcontainer" / "devcontainer.json"
        )

        config = _load_jsonc(devcontainer_json)

        assert "initializeCommand" in config, (
            "devcontainer.json missing 'initializeCommand' field"
        )
        assert config["initializeCommand"] == ".devcontainer/scripts/initialize.sh", (
            "Expected initializeCommand='.devcontainer/scripts/initialize.sh', "
            f"got: {config['initializeCommand']}"
        )

    def test_devcontainer_json_post_attach_command(self, initialized_workspace):
        """Test that postAttachCommand is configured correctly."""
        devcontainer_json = (
            initialized_workspace / ".devcontainer" / "devcontainer.json"
        )

        config = _load_jsonc(devcontainer_json)

        assert "postAttachCommand" in config, (
            "devcontainer.json missing 'postAttachCommand' field"
        )
        # postAttachCommand should reference .devcontainer inside project subdirectory
        expected_command = (
            "/workspace/test_project/.devcontainer/scripts/post-attach.sh"
        )
        assert config["postAttachCommand"] == expected_command, (
            f"Expected postAttachCommand='{expected_command}', "
            f"got: {config['postAttachCommand']}"
        )

    def test_devcontainer_json_post_create_command(self, initialized_workspace):
        """Test that postCreateCommand is configured correctly."""
        devcontainer_json = (
            initialized_workspace / ".devcontainer" / "devcontainer.json"
        )

        config = _load_jsonc(devcontainer_json)

        assert "postCreateCommand" in config, (
            "devcontainer.json missing 'postCreateCommand' field"
        )
        # postCreateCommand should reference .devcontainer inside project subdirectory
        expected_command = (
            "/workspace/test_project/.devcontainer/scripts/post-create.sh"
        )
        assert config["postCreateCommand"] == expected_command, (
            f"Expected postCreateCommand='{expected_command}', "
            f"got: {config['postCreateCommand']}"
        )

    def test_devcontainer_json_no_redundant_container_env(self, initialized_workspace):
        """Test that containerEnv only has socket-related env vars (others should be in docker-compose.yml)."""
        devcontainer_json = (
            initialized_workspace / ".devcontainer" / "devcontainer.json"
        )

        config = _load_jsonc(devcontainer_json)

        # containerEnv is allowed for podman socket configuration
        if "containerEnv" in config:
            container_env = config["containerEnv"]
            # Only CONTAINER_HOST and DOCKER_HOST should be here (for podman socket)
            allowed_keys = {"CONTAINER_HOST", "DOCKER_HOST"}
            actual_keys = set(container_env.keys())
            assert actual_keys == allowed_keys, (
                f"containerEnv should only contain {allowed_keys}, got: {actual_keys}"
            )


class TestDevContainerDockerCompose:
    """Test docker-compose.yml configuration."""

    def test_docker_compose_yml_valid(self, initialized_workspace):
        """Test that docker-compose.yml is valid YAML."""
        docker_compose_yml = (
            initialized_workspace / ".devcontainer" / "docker-compose.yml"
        )

        with docker_compose_yml.open() as f:
            config = yaml.safe_load(f)

        assert isinstance(config, dict), "docker-compose.yml is not a valid YAML object"
        # Note: 'version' field is deprecated in modern docker-compose (1.27.0+)
        assert "services" in config, "docker-compose.yml missing 'services' field"

    def test_docker_compose_yml_service_exists(self, initialized_workspace):
        """Test that devcontainer service exists in docker-compose.yml."""
        docker_compose_yml = (
            initialized_workspace / ".devcontainer" / "docker-compose.yml"
        )

        with docker_compose_yml.open() as f:
            config = yaml.safe_load(f)

        assert "devcontainer" in config["services"], (
            "docker-compose.yml missing 'devcontainer' service"
        )

    def test_docker_compose_yml_image(self, initialized_workspace):
        """Test that docker-compose.yml has correct image reference."""
        docker_compose_yml = (
            initialized_workspace / ".devcontainer" / "docker-compose.yml"
        )

        with docker_compose_yml.open() as f:
            config = yaml.safe_load(f)

        service = config["services"]["devcontainer"]
        assert "image" in service, "devcontainer service missing 'image' field"

        # docker-compose now references version from .env / .vig-os
        expected_image = "ghcr.io/vig-os/devcontainer:${DEVCONTAINER_VERSION:-latest}"
        assert service["image"] == expected_image, (
            f"Expected image to be {expected_image}, got: {service['image']}"
        )

    def test_docker_compose_yml_volumes(self, initialized_workspace):
        """Test that docker-compose.yml has volume mount configured to subdirectory."""
        docker_compose_yml = (
            initialized_workspace / ".devcontainer" / "docker-compose.yml"
        )

        with docker_compose_yml.open() as f:
            config = yaml.safe_load(f)

        service = config["services"]["devcontainer"]
        assert "volumes" in service, "devcontainer service missing 'volumes' field"
        assert isinstance(service["volumes"], list), "volumes should be a list"
        assert len(service["volumes"]) > 0, "No volumes configured"

        # Check that workspace folder is mounted to subdirectory
        volumes_str = " ".join(service["volumes"])
        # Should use relative path (..) for mounting
        assert ".." in volumes_str, (
            f"Expected relative path (..) or localWorkspaceFolder in volumes, got: {service['volumes']}"
        )
        # Should mount to /workspace/test_project (or /workspace/devcontainer before replacement)
        assert "/workspace/" in volumes_str, (
            f"Expected mount to /workspace/ subdirectory, got: {service['volumes']}"
        )
        # Check that it's not mounting directly to /workspace
        assert (
            ":/workspace:" not in volumes_str and ':/workspace"' not in volumes_str
        ), (
            f"Should mount to subdirectory, not directly to /workspace, got: {service['volumes']}"
        )

    def test_docker_compose_yml_environment(self, initialized_workspace):
        """Test that docker-compose.yml has environment variables configured."""
        docker_compose_yml = (
            initialized_workspace / ".devcontainer" / "docker-compose.yml"
        )

        with docker_compose_yml.open() as f:
            config = yaml.safe_load(f)

        service = config["services"]["devcontainer"]
        assert "environment" in service, (
            "devcontainer service missing 'environment' field"
        )
        assert isinstance(service["environment"], list), "environment should be a list"

        # Check for runtime-only environment variable overrides
        # (PRE_COMMIT_HOME, UV_PROJECT_ENVIRONMENT, VIRTUAL_ENV, PYTHONUNBUFFERED,
        #  IN_CONTAINER are set in the image via Containerfile ENV)
        env_vars = {
            item.split("=")[0]: item.split("=")[1] if "=" in item else None
            for item in service["environment"]
        }

        assert "CONTAINER_HOST" in env_vars, (
            "CONTAINER_HOST environment variable not found"
        )
        assert "DOCKER_HOST" in env_vars, "DOCKER_HOST environment variable not found"

    def test_docker_compose_yml_command(self, initialized_workspace):
        """Test that docker-compose.yml has command configured."""
        docker_compose_yml = (
            initialized_workspace / ".devcontainer" / "docker-compose.yml"
        )

        with docker_compose_yml.open() as f:
            config = yaml.safe_load(f)

        service = config["services"]["devcontainer"]
        assert "command" in service, "devcontainer service missing 'command' field"
        assert service["command"] == "sleep infinity", (
            f"Expected command='sleep infinity', got: {service['command']}"
        )

    def test_docker_compose_yml_user(self, initialized_workspace):
        """Test that docker-compose.yml has user configured."""
        docker_compose_yml = (
            initialized_workspace / ".devcontainer" / "docker-compose.yml"
        )

        with docker_compose_yml.open() as f:
            config = yaml.safe_load(f)

        service = config["services"]["devcontainer"]
        assert "user" in service, "devcontainer service missing 'user' field"
        assert service["user"] == "root", (
            f"Expected user='root', got: {service['user']}"
        )

    def test_docker_compose_yml_interactive_settings(self, initialized_workspace):
        """Test that docker-compose.yml has interactive settings configured."""
        docker_compose_yml = (
            initialized_workspace / ".devcontainer" / "docker-compose.yml"
        )

        with docker_compose_yml.open() as f:
            config = yaml.safe_load(f)

        service = config["services"]["devcontainer"]
        assert "stdin_open" in service, (
            "devcontainer service missing 'stdin_open' field"
        )
        assert service["stdin_open"] is True, (
            f"Expected stdin_open=True, got: {service['stdin_open']}"
        )
        assert "tty" in service, "devcontainer service missing 'tty' field"
        assert service["tty"] is True, f"Expected tty=True, got: {service['tty']}"


class TestVigOsConfig:
    """Test .vig-os configuration as version source of truth."""

    def test_vig_os_contains_devkit_version(self, initialized_workspace):
        """Test that .vig-os contains the renamed DEVKIT_VERSION key (#781)."""
        vig_os_file = initialized_workspace / ".vig-os"
        content = vig_os_file.read_text(encoding="utf-8")
        assert "DEVKIT_VERSION=" in content, "DEVKIT_VERSION key not found in .vig-os"
        assert "{{IMAGE_TAG}}" not in content, (
            "IMAGE_TAG placeholder should be replaced in .vig-os"
        )

    def test_init_workspace_pins_requested_version(self, container_image, tmp_path):
        """VIG_OS_VERSION override pins the scaffolded .vig-os (#852).

        The image bakes the release it was built from into the scaffolded
        .vig-os, which is stale for release candidates (the repo pin only
        advances at finalize). install.sh forwards the requested --version as
        VIG_OS_VERSION; init-workspace must honor it over the baked value.
        """
        from .conftest import is_running_in_container

        if is_running_in_container():
            pytest.skip("host-path mount test; covered on the CI host runner")

        workspace = tmp_path / "version-pin-ws"
        workspace.mkdir()
        cmd = _build_podman_cmd(
            container_image,
            f"{workspace}:/workspace",
            smoke_test=True,
            extra_env={"VIG_OS_VERSION": "9.9.9-rc9"},
        )
        _run_noninteractive_init(cmd)

        vig_os_file = workspace / ".vig-os"
        assert vig_os_file.exists(), ".vig-os not scaffolded"
        content = vig_os_file.read_text(encoding="utf-8")
        assert "DEVKIT_VERSION=9.9.9-rc9" in content, (
            f".vig-os does not pin the requested version:\n{content}"
        )

    def test_initialize_writes_devcontainer_version_to_env(self, initialized_workspace):
        """Test initialize.sh writes DEVCONTAINER_VERSION to .devcontainer/.env."""
        init_script = (
            initialized_workspace / ".devcontainer" / "scripts" / "initialize.sh"
        )
        env_file = initialized_workspace / ".devcontainer" / ".env"

        if env_file.exists():
            env_file.unlink()

        result = subprocess.run(
            [str(init_script)],
            capture_output=True,
            text=True,
            cwd=str(initialized_workspace),
            timeout=10,
        )
        assert result.returncode == 0, (
            f"initialize.sh failed\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )
        assert env_file.exists(), ".devcontainer/.env was not created by initialize.sh"

        env_content = env_file.read_text(encoding="utf-8")
        assert "DEVCONTAINER_VERSION=" in env_content, (
            "initialize.sh did not write DEVCONTAINER_VERSION to .env"
        )

    def test_initialize_does_not_execute_vig_os_shell_content(
        self, initialized_workspace
    ):
        """Test initialize.sh parses .vig-os as data, not executable shell."""
        init_script = (
            initialized_workspace / ".devcontainer" / "scripts" / "initialize.sh"
        )
        vig_os_file = initialized_workspace / ".vig-os"
        env_file = initialized_workspace / ".devcontainer" / ".env"
        marker_file = initialized_workspace / ".issue285_init_marker"
        original_vig_os = (
            vig_os_file.read_text(encoding="utf-8") if vig_os_file.exists() else None
        )

        try:
            if env_file.exists():
                env_file.unlink()
            if marker_file.exists():
                marker_file.unlink()

            vig_os_file.write_text(
                "\n".join(
                    [
                        "DEVCONTAINER_VERSION=1.2.3",
                        f'EVIL=$(touch "{marker_file}")',
                        "UNRELATED_KEY=ignored",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            result = subprocess.run(
                [str(init_script)],
                capture_output=True,
                text=True,
                cwd=str(initialized_workspace),
                timeout=10,
            )

            assert result.returncode == 0, (
                f"initialize.sh failed\nstdout: {result.stdout}\nstderr: {result.stderr}"
            )
            assert marker_file.exists() is False, (
                "initialize.sh executed shell content from .vig-os"
            )
            assert env_file.exists(), (
                ".devcontainer/.env was not created by initialize.sh"
            )
            env_content = env_file.read_text(encoding="utf-8")
            assert "DEVCONTAINER_VERSION=1.2.3" in env_content
        finally:
            if original_vig_os is None:
                if vig_os_file.exists():
                    vig_os_file.unlink()
            else:
                vig_os_file.write_text(original_vig_os, encoding="utf-8")


class TestPlaceholders:
    """Test that placeholders are replaced correctly."""

    def test_placeholders_replaced(self, initialized_workspace):
        """Test that placeholders are replaced in all asset files."""
        # Hard-coded list of paths to exclude
        excluded_paths = [
            ".pre-commit-cache",
            ".ruff_cache",
        ]

        # Find all files recursively, excluding specified paths at iteration level
        files = (
            file_path
            for file_path in initialized_workspace.rglob("*")
            if file_path.is_file()
            and not any(
                excluded_path in file_path.parts for excluded_path in excluded_paths
            )
        )

        # Check each file for placeholders
        for file_path in files:
            try:
                content = file_path.read_text(encoding="utf-8")
                # Check for unreplaced placeholders (not literal strings)
                for placeholder in ["{{IMAGE_TAG}}", "{{SHORT_NAME}}", "{{ORG_NAME}}"]:
                    assert placeholder not in content, (
                        f"{placeholder} placeholder not replaced in {file_path}"
                    )
            except UnicodeDecodeError:
                # Skip binary files
                continue

    def test_org_name_replaced(self, initialized_workspace):
        """Test that the organization name is substituted in specific asset files.

        Placeholder absence across the whole tree is covered by
        test_placeholders_replaced; this asserts the positive substitution.
        """
        files = [
            initialized_workspace / "LICENSE",
        ]

        for file in files:
            content = file.read_text(encoding="utf-8")
            assert "Test Org" in content, f"Organization name not replaced in {file}"

    def test_short_name_replaced(self, initialized_workspace):
        """Test that the short name is substituted in specific asset files.

        Placeholder absence across the whole tree is covered by
        test_placeholders_replaced; this asserts the positive substitution.
        """
        files = [
            initialized_workspace / ".devcontainer" / "devcontainer.json",
            initialized_workspace / ".devcontainer" / "scripts" / "post-create.sh",
        ]

        for file in files:
            content = file.read_text(encoding="utf-8")
            assert "test_project" in content, f"Short name not replaced in {file}"


class TestSmokeRepo:
    """Tests for smoke-test-specific asset deployment."""

    def test_smoke_test_flag_deploys_assets(self, initialized_smoke_workspace):
        """Test --smoke-test deploys specific assets."""
        project_root = Path(__file__).resolve().parents[1]
        smoke_test_assets_dir = project_root / "assets" / "smoke-test"
        smoke_test_files = [
            path for path in smoke_test_assets_dir.rglob("*") if path.is_file()
        ]

        assert smoke_test_files, "No smoke-test assets found in assets/smoke-test"
        for source_file in smoke_test_files:
            relative_path = source_file.relative_to(smoke_test_assets_dir)
            deployed_path = initialized_smoke_workspace / relative_path
            assert deployed_path.exists(), f"{relative_path} not deployed"

    def test_smoke_redeploy_preserves_synced_docs_directories(
        self, initialized_smoke_workspace, container_image
    ):
        """Regression: smoke re-deploy must not delete docs synced by sync-issues."""
        docs_issues = initialized_smoke_workspace / "docs" / "issues"
        docs_pull_requests = initialized_smoke_workspace / "docs" / "pull-requests"
        docs_issues.mkdir(parents=True, exist_ok=True)
        docs_pull_requests.mkdir(parents=True, exist_ok=True)

        issues_sentinel = docs_issues / "keep.md"
        prs_sentinel = docs_pull_requests / "keep.md"
        issues_sentinel.write_text("keep issue docs", encoding="utf-8")
        prs_sentinel.write_text("keep PR docs", encoding="utf-8")

        cmd = _build_podman_cmd(
            container_image,
            f"{initialized_smoke_workspace}:/workspace",
            smoke_test=True,
        )
        _run_noninteractive_init(cmd)

        assert docs_issues.exists(), (
            "docs/issues directory was deleted by smoke re-deploy"
        )
        assert docs_pull_requests.exists(), (
            "docs/pull-requests directory was deleted by smoke re-deploy"
        )
        assert issues_sentinel.exists(), (
            "docs/issues sentinel was deleted by smoke re-deploy"
        )
        assert prs_sentinel.exists(), (
            "docs/pull-requests sentinel was deleted by smoke re-deploy"
        )

    def test_default_init_does_not_deploy_repository_dispatch(
        self, initialized_workspace
    ):
        """Test default init does not deploy repository-dispatch workflow."""
        dispatch_workflow = (
            initialized_workspace / ".github" / "workflows" / "repository-dispatch.yml"
        )
        assert not dispatch_workflow.exists(), (
            "repository-dispatch.yml should not be deployed without --smoke-test"
        )

    def test_smoke_workspace_changelog_available_in_devcontainer_and_root(
        self, initialized_smoke_workspace
    ):
        """Smoke template should ship root and devcontainer changelogs with distinct roles."""
        root_changelog = initialized_smoke_workspace / "CHANGELOG.md"
        devcontainer_changelog = (
            initialized_smoke_workspace / ".devcontainer" / "CHANGELOG.md"
        )

        assert root_changelog.exists(), "Root CHANGELOG.md not found in smoke workspace"
        assert devcontainer_changelog.exists(), (
            ".devcontainer/CHANGELOG.md not found in smoke workspace"
        )
        root_content = root_changelog.read_text(encoding="utf-8")
        devcontainer_content = devcontainer_changelog.read_text(encoding="utf-8")

        # The root changelog is the CONSUMER's own history: on a fresh deploy it
        # is bootstrapped from the workspace scaffold (## Unreleased skeleton,
        # no release sections). It must NOT be a copy of devkit's changelog —
        # deploying devkit's dated/linked ## [X.Y.Z] headings into the consumer
        # rewrites its frozen release sections and guarantees a main<->dev sync
        # conflict at every smoke release (#1403).
        first_h2 = re.search(r"^## .+$", root_content, re.MULTILINE)
        assert first_h2 is not None, "Root changelog should have a top-level ## heading"
        assert first_h2.group(0).rstrip("\r\n") == "## Unreleased", (
            "Root changelog top section should be ## Unreleased"
        )
        assert not re.search(r"^## \[\d+\.\d+\.\d+\]", root_content, re.MULTILINE), (
            "Root changelog must not carry devkit release sections (#1403); "
            "a fresh smoke deploy bootstraps the scaffold skeleton only"
        )
        assert root_content != devcontainer_content, (
            "Root changelog must not be a byte copy of devkit's changelog (#1403)"
        )
        assert re.search(
            r"^## \[\d+\.\d+\.\d+\]", devcontainer_content, re.MULTILINE
        ), ".devcontainer changelog should include semver release history"


class TestDevContainerGit:
    """Test that git configuration files are set up."""

    def test_pre_commit_hook_exists(self, initialized_workspace):
        """Test that pre-commit hook exists."""
        pre_commit_hook = initialized_workspace / ".githooks" / "pre-commit"
        assert pre_commit_hook.exists(), "pre-commit hook not found"
        assert pre_commit_hook.is_file(), "pre-commit hook is not a file"
        assert pre_commit_hook.stat().st_mode & 0o111, (
            "pre-commit hook is not executable"
        )

    def test_pre_commit_config_exists(self, initialized_workspace):
        """Test that .pre-commit-config.yaml exists."""
        precommit_config = initialized_workspace / ".pre-commit-config.yaml"
        assert precommit_config.exists(), ".pre-commit-config.yaml not found"
        assert precommit_config.is_file(), ".pre-commit-config.yaml is not a file"


class TestDevContainerUserConf:
    """Test that user configuration files are set up."""

    def test_venv_prompt_name(self, devcontainer_up):
        """Test that .venv/bin/activate in the image does not contain 'template-project', but is renamed to `test_project`."""
        activate_path = "/root/assets/workspace/.venv/bin/activate"
        result = dc_exec(devcontainer_up, "bash", "-c", f"cat {activate_path}")
        assert result.returncode == 0, (
            f"Failed to read {activate_path}\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )
        assert "template-project" not in result.stdout, (
            f"{activate_path} still contains 'template-project'; "
            "should be replaced with project short name during container init (e.g. post-create)"
        )
        assert "test_project" in result.stdout, (
            f"{activate_path} does not contain 'test_project'; "
            "should be renamed to project short name during container init (e.g. post-create)"
        )

    def test_conf_directory_files(self, devcontainer_up):
        """Test that .devcontainer/.conf has the generated .gitconfig and no leftover token."""
        conf_dir = "/workspace/test_project/.devcontainer/.conf"

        # .gitconfig is always generated
        result = dc_exec(devcontainer_up, "test", "-f", f"{conf_dir}/.gitconfig")
        assert result.returncode == 0, (
            f".gitconfig not found in {conf_dir}\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )

        # GitHub CLI token file must NOT exist (should be deleted after authentication)
        result = dc_exec(devcontainer_up, "test", "!", "-f", f"{conf_dir}/.gh_token")
        assert result.returncode == 0, (
            f".gh_token file still exists in {conf_dir} - token was not deleted after authentication\n"
            f"This is a security risk as the token should be removed after use.\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )

    def test_files_copied_to_home(self, devcontainer_up):
        """Files staged in .devcontainer/.conf are copied to their home destinations.

        ``.gitconfig`` is always generated, so its home copy is a hard assert.
        The SSH public key, allowed-signers file, and gh config dir are staged
        only when present on the host, so each is asserted conditionally:
        staged in .conf -> must have been copied home.
        """
        conf_dir = "/workspace/test_project/.devcontainer/.conf"

        result = dc_exec(devcontainer_up, "bash", "-c", "test -f $HOME/.gitconfig")
        assert result.returncode == 0, (
            f".gitconfig not found in $HOME/.gitconfig\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )

        optional_copies = [
            (
                f"{conf_dir}/id_ed25519_github.pub",
                "-f",
                "test -f $HOME/.ssh/id_ed25519_github.pub",
            ),
            (
                f"{conf_dir}/allowed-signers",
                "-f",
                "test -f $HOME/.config/git/allowed-signers",
            ),
            (f"{conf_dir}/gh", "-d", "test -d $HOME/.config/gh"),
        ]
        for conf_path, test_flag, home_probe in optional_copies:
            staged = dc_exec(devcontainer_up, "test", test_flag, conf_path)
            if staged.returncode != 0:
                # Not staged on this host (host-dependent, optional file).
                continue
            copied = dc_exec(devcontainer_up, "bash", "-c", home_probe)
            assert copied.returncode == 0, (
                f"{conf_path} is staged in .conf but was not copied home "
                f"({home_probe})\n"
                f"stdout: {copied.stdout}\n"
                f"stderr: {copied.stderr}"
            )

    def test_setup_git_conf_falls_back_to_nano_for_invalid_editor(
        self, devcontainer_up
    ):
        """Regression: setup-git-conf should enforce a usable editor fallback."""
        result = dc_exec(
            devcontainer_up,
            "bash",
            "-c",
            (
                "set -e && "
                "cd /workspace/test_project && "
                "orig_conf=.devcontainer/.conf/.gitconfig && "
                "bak_conf=.devcontainer/.conf/.gitconfig.test-bak && "
                '[ -f "$orig_conf" ] && cp "$orig_conf" "$bak_conf" || true && '
                "export HOME=/tmp/setup-git-conf-home && "
                'rm -rf "$HOME" && mkdir -p "$HOME" && '
                'cleanup(){ rm -rf "$HOME"; if [ -f "$bak_conf" ]; then mv "$bak_conf" "$orig_conf"; else rm -f "$orig_conf"; fi; } && '
                "trap cleanup EXIT && "
                "printf '[core]\\n\\teditor = missing-editor-command-zzzz-12345\\n' > \"$orig_conf\" && "
                ".devcontainer/scripts/setup-git-conf.sh >/tmp/setup-git-conf.log 2>&1 && "
                "git config --global --get core.editor"
            ),
            timeout=60,
        )

        assert result.returncode == 0, (
            f"Failed to re-run setup-git-conf.sh\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )
        assert result.stdout.strip() == "nano", (
            "setup-git-conf.sh should replace invalid core.editor with nano\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )


class TestDevContainerCLI:
    """Tests for the devcontainer CLI environment."""

    def test_devcontainer_runs_image_under_test(self, devcontainer_up, container_tag):
        """The running devcontainer must use the freshly-built image under test.

        The scaffolded docker-compose.yml pins the runtime image as
        ``ghcr.io/vig-os/devcontainer:${DEVCONTAINER_VERSION:-latest}`` and
        ``initialize.sh`` writes the pinned ``DEVCONTAINER_VERSION`` (from the
        scaffolded ``.vig-os``) into ``.env``. Without an override the suite
        would validate fresh scaffolding running inside an old *published*
        image, not the image actually being built. The ``devcontainer_up``
        fixture overrides ``DEVCONTAINER_VERSION`` to ``TEST_CONTAINER_TAG`` so
        compose resolves the image to the build under test. Refs #701.
        """
        workspace_path = devcontainer_up.resolve()

        result = subprocess.run(
            [
                "podman",
                "ps",
                "--filter",
                f"name={workspace_path.name}",
                "--format",
                "{{.Image}}",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, (
            f"Failed to list running devcontainer\nstderr: {result.stderr}"
        )
        images = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        assert images, (
            f"No running devcontainer found for workspace {workspace_path.name}"
        )

        expected_image = f"ghcr.io/vig-os/devcontainer:{container_tag}"
        assert any(expected_image in image for image in images), (
            f"Devcontainer is running from {images}, but the suite must validate "
            f"the image under test ({expected_image}). DEVCONTAINER_VERSION is not "
            f"being overridden to TEST_CONTAINER_TAG."
        )

    def test_ssh_github_authentication(self, devcontainer_up):
        """Test that SSH authentication to GitHub works in the devcontainer."""
        # First check if SSH keys are available in the container
        keys_result = dc_exec(
            devcontainer_up,
            "bash",
            "-c",
            "test -f ~/.ssh/id_ed25519_github.pub && echo 'keys_found' || echo 'no_keys'",
        )

        # If no SSH keys are available, skip the test
        if "no_keys" in keys_result.stdout:
            pytest.skip(
                "SSH keys not available in devcontainer. "
                "SSH keys need to be set up via .devcontainer/.conf/ for this test to run."
            )

        # Test SSH connection to GitHub
        # This verifies that SSH keys are properly configured
        result = dc_exec(
            devcontainer_up,
            "ssh",
            "-T",
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            "UserKnownHostsFile=/dev/null",
            "-i",
            "~/.ssh/id_ed25519_github",
            "git@github.com",
            timeout=10,
        )

        # SSH to GitHub returns exit code 1 on success (it's a test connection)
        # Exit code 255 means connection/auth failed
        if result.returncode == 255:
            # Check if it's a permission denied (keys not authorized) vs connection error
            if "Permission denied" in result.stderr:
                # Keys exist but aren't authorized - this is acceptable for testing
                # Ensure this is an auth failure, not a connectivity/hostname failure.
                assert (
                    "Could not resolve hostname" not in result.stderr
                    and "Name or service not known" not in result.stderr
                ), (
                    f"SSH connection failed unexpectedly\n"
                    f"stdout: {result.stdout}\n"
                    f"stderr: {result.stderr}"
                )
            else:
                pytest.fail(
                    f"SSH connection to GitHub failed\n"
                    f"stdout: {result.stdout}\n"
                    f"stderr: {result.stderr}"
                )
        elif result.returncode == 1:
            # Success - GitHub responded (exit 1 is normal for test connections)
            output = result.stdout + result.stderr
            assert (
                "successfully authenticated" in output
                or "does not provide shell access" in output
                or "Hi " in output
            ), (
                f"Unexpected SSH response from GitHub\n"
                f"stdout: {result.stdout}\n"
                f"stderr: {result.stderr}"
            )
        else:
            pytest.fail(
                f"Unexpected ssh exit code {result.returncode} "
                "(expected 1 on a successful test connection or 255 on failure)\n"
                f"stdout: {result.stdout}\n"
                f"stderr: {result.stderr}"
            )

    def test_pre_commit_hook(self, devcontainer_up):
        """Test that pre-commit hook runs successfully on a dummy file."""

        workspace_path = devcontainer_up.resolve()

        # Create a dummy Python file to test pre-commit
        test_file = workspace_path / "test_file.py"
        test_file.write_text("def hello():\n    print('hello')\n")

        # Run pre-commit on the file
        result = dc_exec(
            devcontainer_up,
            "bash",
            "-c",
            "cd /workspace/test_project && prek run --files test_file.py",
            timeout=120,  # prek can take a while on first run
        )

        # prek should succeed (exit code 0) or pass with warnings
        # Exit code 1 means hooks failed, which is also acceptable for testing
        # We just want to verify the hook runner (prek, #778) runs
        assert result.returncode in [0, 1], (
            f"prek failed unexpectedly\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )

        # Verify the hook runner actually ran (check for prek/hook output)
        assert "prek" in result.stdout.lower() or "ruff" in result.stdout.lower(), (
            f"prek doesn't appear to have run\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )

        # Clean up
        test_file.unlink()

    def test_git_commit_ssh_signature(self, devcontainer_up):
        """Test that git commits are signed with SSH signature."""

        workspace_path = devcontainer_up.resolve()

        # Check if SSH agent is available on the host
        ssh_auth_sock = os.environ.get("SSH_AUTH_SOCK")
        if not ssh_auth_sock or not Path(ssh_auth_sock).exists():
            pytest.skip(
                "SSH agent not available on host. "
                "Start SSH agent with 'eval $(ssh-agent)' and add your key with 'ssh-add'."
            )

        # Check if SSH keys and git signing are configured
        config_result = dc_exec(
            devcontainer_up,
            "bash",
            "-c",
            (
                "cd /workspace/test_project && "
                "git config --get gpg.format 2>/dev/null | grep -q ssh && echo 'ssh_signing_configured' || echo 'not_configured'"
            ),
        )

        # If SSH signing is not configured, skip the test
        if "not_configured" in config_result.stdout:
            pytest.skip(
                "SSH signing not configured in git. "
                "Git commit signing requires SSH keys and git config to be set up."
            )

        # Create a test file to commit
        test_file = workspace_path / "test_commit.txt"
        test_file.write_text("Test commit for signature verification\n")

        # SSH agent forwarding is automatically configured by the devcontainer_up fixture
        # if SSH_AUTH_SOCK is available. The socket should be mounted at /tmp/ssh-agent.sock
        # and SSH_AUTH_SOCK should be set to that path in the container environment.
        result = dc_exec(
            devcontainer_up,
            "bash",
            "-c",
            (
                "cd /workspace/test_project && "
                "git config user.name 'Test User' && "
                "git config user.email 'test@example.com' && "
                "git add test_commit.txt && "
                "git commit -m 'test(api): a dummy test\n\nRefs: #1' && "
                "git log -1 --show-signature"
            ),
            timeout=30,
        )

        if result.returncode != 0:
            # If commit failed due to SSH agent, that's acceptable - the important
            # thing is that git signing is configured
            if (
                "Couldn't get agent socket" in result.stderr
                or "failed to write commit object" in result.stderr
            ):
                pytest.skip(
                    "SSH agent forwarding failed. "
                    "Make sure SSH agent is running and SSH_AUTH_SOCK is set."
                )
            else:
                pytest.fail(
                    f"Git commit failed\n"
                    f"stdout: {result.stdout}\n"
                    f"stderr: {result.stderr}"
                )

        # Verify the commit was signed
        output = result.stdout + result.stderr
        assert (
            'Good "git" signature' in output
            or "Good signature" in output
            or "Signature made" in output
        ), (
            f"Commit signature not found or invalid\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}\n"
            f"Expected 'Good \"git\" signature' or 'Good signature' or 'Signature made' in output"
        )

        # Clean up - reset the commit
        dc_exec(
            devcontainer_up,
            "bash",
            "-c",
            "cd /workspace && git reset --soft HEAD~1 && git reset test_commit.txt",
        )
        test_file.unlink()

    def test_github_cli_authentication(self, devcontainer_up):
        """Test that GitHub CLI authentication works in the devcontainer."""
        # Test gh auth status in the container
        result = dc_exec(devcontainer_up, "gh", "auth", "status", timeout=10)

        # gh auth status returns exit code 0 on success, 1 on failure
        if result.returncode != 0:
            # Check if it's a "not logged in" error (expected if config not mounted)
            error_output = result.stderr.lower() + result.stdout.lower()
            if (
                "not logged in" in error_output
                or "you are not logged into any github hosts" in error_output
                or "to log in, run: gh auth login" in error_output
            ):
                pytest.skip(
                    "GitHub CLI not authenticated in container. "
                    "To enable authentication, ensure GitHub CLI is authenticated on the host "
                    "(run 'gh auth login') so the token can be exported during initialization."
                )
            else:
                pytest.fail(
                    f"GitHub CLI authentication check failed\n"
                    f"stdout: {result.stdout}\n"
                    f"stderr: {result.stderr}"
                )

        # Verify we got a successful authentication response
        output = result.stdout + result.stderr
        assert "Logged in to " in output or "✓ Logged in" in output, (
            f"GitHub CLI authentication status unclear\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}\n"
            f"Expected a successful gh auth status message in output"
        )

    def test_valid_branch_names_commit_succeeds(self, devcontainer_up):
        """Valid branch names (convention) allow commits; passes with or without branch-name hook."""
        # Create dummy file to commit
        workspace_path = devcontainer_up.resolve()
        dummy_file = workspace_path / "dummy.txt"
        dummy_file.write_text("dummy\n")

        # Define valid branch names
        valid_branch_names = [
            "feature/123-test-branch",
            "bugfix/123-test-branch",
            "hotfix/123-test-branch",
            "release/123-test-branch",
            "docs/123-test-branch",
            "test/123-test-branch",
            "refactor/123-test-branch",
        ]

        # Test valid branch names
        for branch_name in valid_branch_names:
            # Create branch and run the prek hook runner
            result = dc_exec(
                devcontainer_up,
                "bash",
                "-c",
                (
                    "cd /workspace/test_project"
                    " && printf 'dummy\\n' > dummy.txt"
                    f" && git checkout -b '{branch_name}'"
                    " && git add dummy.txt"
                    " && prek run -a"
                ),
                timeout=120,
            )

            assert result.returncode == 0, (
                f"prek on valid branch '{branch_name}' should succeed\n"
                f"stdout: {result.stdout}\n"
                f"stderr: {result.stderr}"
            )

    def test_invalid_branch_names_commit_fails(self, devcontainer_up):
        """Invalid branch names (convention) fail commits (branch-name pre-commit hook)."""
        # Create dummy file to commit
        workspace_path = devcontainer_up.resolve()
        dummy_file = workspace_path / "dummy.txt"
        dummy_file.write_text("dummy\n")

        invalid_branch_names = [
            "featur/123-typo",
            "bugfix/missing-issue-number",
            "hotfix/123",
            "release123-missing-/",
            "random-string",
        ]

        for branch_name in invalid_branch_names:
            result = dc_exec(
                devcontainer_up,
                "bash",
                "-c",
                (
                    "cd /workspace/test_project"
                    " && printf 'dummy\\n' > dummy.txt"
                    f" && git checkout -b '{branch_name}'"
                    " && git add dummy.txt"
                    " && prek run -a"
                ),
                timeout=120,
            )

            assert result.returncode != 0, (
                f"prek on invalid branch '{branch_name}' should fail\n"
                f"stdout: {result.stdout}\n"
                f"stderr: {result.stderr}"
            )
            output = (result.stdout + result.stderr).lower()
            assert "branch" in output or "no-commit-to-branch" in output, (
                f"Expected branch-name hook failure in output\n"
                f"stdout: {result.stdout}\nstderr: {result.stderr}"
            )


class TestJustRecipes:
    """Test the just recipes."""

    _just_help_output_lines = [
        "Available recipes:",
        "    [info]",
        r"    help\s+# Show available commands",
        r"    info\s+# Show project information",
        "    [build]",
        "    [test]",
        "    [quality]",
        "    [deps]",
    ]

    @pytest.mark.parametrize("args", [[], ["help"]], ids=["default", "help"])
    def test_just_help_output(self, devcontainer_up, args):
        """`just` (default) and `just help` list the expected recipe groups."""
        result = dc_exec(devcontainer_up, "just", *args, timeout=10)

        # Return code must be 0
        assert result.returncode == 0, (
            f"`just {' '.join(args)}` recipe failed\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )

        # Verify we got expected lines in the response
        output = result.stdout
        for line in self._just_help_output_lines:
            # Use regex for lines that contain \s+ (variable whitespace)
            # Otherwise use exact string matching
            if "\\s+" in line:
                pattern = re.compile(line)
                assert pattern.search(output) is not None, (
                    f"Expected pattern '{line}' not found in output\n"
                    f"stdout: {result.stdout}\n"
                    f"stderr: {result.stderr}"
                )
            else:
                assert line in output, (
                    f"Expected line '{line}' not found in output\n"
                    f"stdout: {result.stdout}\n"
                    f"stderr: {result.stderr}"
                )

    def test_just_info(self, devcontainer_up):
        """Test the just info command."""
        result = dc_exec(devcontainer_up, "just", "info", timeout=10)

        assert result.returncode == 0, (
            f"`just info` recipe failed\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )

        assert "Project: test_project" in result.stdout, (
            f"Project information not found in output\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )

    def test_just_test_recipe(self, devcontainer_up):
        """`just test` no-ops (exit 0) on a language-neutral base scaffold (#929).

        The scaffold ships no ``pyproject.toml``, so the guarded recipe runs
        nothing and exits 0 — the shipped ``ci.yml`` (and the release smoke-test
        dispatch) stay green on a project that has not added a Python package.
        Adding one (e.g. ``nix flake init -t ...#python``, #930) activates pytest.
        """
        result = dc_exec(devcontainer_up, "just", "test", timeout=10)

        assert result.returncode == 0, (
            f"`just test` recipe failed\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )

        # No pyproject.toml -> the guard skips pytest entirely (no session).
        assert "test session starts" not in result.stdout, (
            f"`just test` should no-op without a pyproject.toml, but pytest ran\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )

    def test_template_justfile_gh_includes_release_recipes(self):
        """Test that template justfile.gh exposes release helper recipes."""
        project_root = Path(__file__).resolve().parents[1]
        justfile_gh = project_root / "assets/workspace/.devcontainer/justfile.gh"
        content = justfile_gh.read_text()

        for recipe_name in [
            "prepare-release",
            "finalize-release",
            "promote-release",
            "publish-candidate",
            "reset-changelog",
        ]:
            assert re.search(rf"(?m)^{recipe_name}(?:\s+.*)?:$", content), (
                f"{recipe_name} recipe definition should exist in .devcontainer/justfile.gh"
            )

    def test_template_release_helpers_dispatch_expected_workflows(self):
        """Test release helper dispatch defaults in template justfile.gh."""
        project_root = Path(__file__).resolve().parents[1]
        justfile_gh = project_root / "assets/workspace/.devcontainer/justfile.gh"
        content = justfile_gh.read_text()

        assert 'gh workflow run prepare-release.yml --ref "$REF"' in content
        assert 'REF="dev"' in content
        assert 'gh workflow run release.yml --ref "$REF"' in content
        assert 'gh workflow run promote-release.yml --ref "$REF"' in content
        assert "release-kind=final" in content
        assert "release-kind=candidate" in content
        assert "create-release={{ create-release }}" in content
        assert "\nreset-changelog:\n    prepare-changelog reset CHANGELOG.md" in content
        assert "uv run prepare-changelog" not in content
        assert "build/test images" not in content
        assert "GHCR :latest" not in content
        assert 'pull version="latest"' not in content
        assert "ghcr.io/vig-os/devcontainer" not in content


class TestDockerComposeProjectOverrides:
    """Test docker-compose.project.yaml functionality for additional mounts."""

    def test_override_mount_readable(self, devcontainer_up):
        """The project.yaml override mount is present and readable in the container.

        The conftest fixture mounts tests/ at /workspace/tests-mounted via
        docker-compose.project.yaml; reading a known file's content proves the
        mount exists, is a directory, and is readable in one probe.
        """
        result = dc_exec(
            devcontainer_up, "head", "-n", "1", "/workspace/tests-mounted/conftest.py"
        )

        assert result.returncode == 0, (
            f"Failed to read conftest.py from override mount at "
            f"/workspace/tests-mounted/conftest.py\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )

        # Verify we got some content (should be a comment or import)
        assert result.stdout.strip(), (
            f"conftest.py appears to be empty or unreadable\nstdout: {result.stdout}\n"
        )


class TestPodmanSocketAccess:
    """Tests for Podman/Docker socket access from within the devcontainer.

    These tests verify that container-in-container operations work correctly,
    which is essential for:
    - Building container images inside the devcontainer
    - Testing containerized applications
    """

    def test_socket_file_exists(self, devcontainer_up):
        """Test that the Docker/Podman socket is mounted in the container."""
        result = dc_exec(devcontainer_up, "test", "-S", "/var/run/docker.sock")

        assert result.returncode == 0, (
            f"Docker/Podman socket not found at /var/run/docker.sock\n"
            f"The socket is configured via docker-compose.yml using CONTAINER_SOCKET_PATH from .env\n"
            f"The .env file is created by initialize.sh based on your host OS\n"
            f"stderr: {result.stderr}"
        )

    def test_socket_environment_variables(self, devcontainer_up):
        """Test that CONTAINER_HOST and DOCKER_HOST are set correctly."""
        result = dc_exec(
            devcontainer_up,
            "bash",
            "-c",
            "echo CONTAINER_HOST=$CONTAINER_HOST && echo DOCKER_HOST=$DOCKER_HOST",
        )

        assert result.returncode == 0, (
            f"Failed to check environment variables\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )

        # Check that both variables are set to the socket path
        expected_socket = "unix:///var/run/docker.sock"
        assert f"CONTAINER_HOST={expected_socket}" in result.stdout, (
            f"CONTAINER_HOST not set correctly\n"
            f"Expected: {expected_socket}\n"
            f"stdout: {result.stdout}"
        )
        assert f"DOCKER_HOST={expected_socket}" in result.stdout, (
            f"DOCKER_HOST not set correctly\n"
            f"Expected: {expected_socket}\n"
            f"stdout: {result.stdout}"
        )

    def test_simple_image_build(self, devcontainer_up):
        """A DooD image build through the mounted socket must succeed.

        Building images from inside the devcontainer is the essential use case
        the socket mount exists for; a broken socket must fail this suite
        rather than skip it.
        """
        containerfile_content = (
            "FROM docker.io/library/alpine:latest\nRUN echo 'test build'"
        )

        # Create Containerfile in workspace directory: the workspace is mounted
        # from the host, so the podman daemon can access the build context.
        build_context_dir = "/workspace/test_project/.test-build-context"
        try:
            result = dc_exec(
                devcontainer_up,
                "bash",
                "-c",
                (
                    f"mkdir -p {build_context_dir} && "
                    f"echo '{containerfile_content}' > {build_context_dir}/Containerfile && "
                    f"podman build -t test-build:latest {build_context_dir} && "
                    f"rm -rf {build_context_dir}"
                ),
                timeout=120,  # Building can take time
            )

            assert result.returncode == 0, (
                f"podman build via the mounted socket failed\n"
                f"stdout: {result.stdout}\n"
                f"stderr: {result.stderr}"
            )
        finally:
            # Clean up the test image (attempt cleanup even if the build failed)
            dc_exec(
                devcontainer_up,
                "podman",
                "rmi",
                "-f",  # Force removal in case image exists
                "test-build:latest",
                timeout=10,
            )


# --- Version-check feature ---------------------------------------------------
#
# Behavioral coverage (TestVersionCheckScript) runs the scaffolded
# version-check.sh against the initialized workspace; content coverage
# (TestVersionCheckScaffold) pins the feature's wiring in the scaffold sources.


@pytest.fixture
def version_check_script(initialized_workspace):
    """Path to the scaffolded version-check.sh (the scaffold always ships it)."""
    script_path = (
        initialized_workspace / ".devcontainer" / "scripts" / "version-check.sh"
    )
    assert script_path.exists(), f"version-check.sh not found at {script_path}"
    assert os.access(script_path, os.X_OK), (
        f"version-check.sh is not executable: {script_path}"
    )
    return script_path


@pytest.fixture
def local_dir(initialized_workspace):
    """Path to .local directory for config files."""
    local_path = initialized_workspace / ".devcontainer" / ".local"
    local_path.mkdir(parents=True, exist_ok=True)
    return local_path


class TestVersionCheckScript:
    """Behavioral tests for the version-check.sh script.

    Covers configuration management (enable/disable, intervals, mute),
    duration parsing, and silent failure behavior.
    """

    def test_help_command(self, version_check_script):
        """Test that help command works."""
        result = subprocess.run(
            [str(version_check_script), "help"],
            capture_output=True,
            text=True,
            timeout=5,
        )

        assert result.returncode == 0
        assert "version-check.sh" in result.stdout
        assert "USAGE:" in result.stdout
        assert "check" in result.stdout
        assert "on|enable" in result.stdout
        assert "off|disable" in result.stdout

    def test_config_does_not_execute_vig_os_shell_content(
        self, version_check_script, initialized_workspace
    ):
        """Test config command does not execute shell code from .vig-os."""
        vig_os_file = initialized_workspace / ".vig-os"
        marker_file = initialized_workspace / ".issue285_version_marker"
        original_vig_os = (
            vig_os_file.read_text(encoding="utf-8") if vig_os_file.exists() else None
        )

        try:
            if marker_file.exists():
                marker_file.unlink()

            vig_os_file.write_text(
                "\n".join(
                    [
                        "DEVCONTAINER_VERSION=1.2.3",
                        f'EVIL=$(touch "{marker_file}")',
                        "NOT_RELEVANT=ok",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            result = subprocess.run(
                [str(version_check_script), "config"],
                capture_output=True,
                text=True,
                cwd=str(initialized_workspace),
                timeout=10,
            )

            assert result.returncode == 0, (
                f"version-check.sh config failed\nstdout: {result.stdout}\nstderr: {result.stderr}"
            )
            assert marker_file.exists() is False, (
                "version-check.sh executed shell content from .vig-os"
            )
            assert "Current ver:    1.2.3" in result.stdout
        finally:
            if original_vig_os is None:
                if vig_os_file.exists():
                    vig_os_file.unlink()
            else:
                vig_os_file.write_text(original_vig_os, encoding="utf-8")

    def test_config_creation(self, version_check_script, local_dir):
        """Test that config file is created with defaults on first run."""
        config_file = local_dir / "version-check.conf"

        # Remove config if exists
        if config_file.exists():
            config_file.unlink()

        # Run enable command first (config command alone doesn't create file)
        result = subprocess.run(
            [str(version_check_script), "on"],
            capture_output=True,
            text=True,
            timeout=5,
        )

        assert result.returncode == 0
        assert config_file.exists(), "Config file was not created"

        # Check default values
        config_content = config_file.read_text()
        assert "enabled=true" in config_content
        assert "interval=86400" in config_content

    def test_enable_command(self, version_check_script, local_dir):
        """Test enable command sets enabled=true."""
        result = subprocess.run(
            [str(version_check_script), "on"],
            capture_output=True,
            text=True,
            timeout=5,
        )

        assert result.returncode == 0
        assert "enabled" in result.stdout.lower()

        config_file = local_dir / "version-check.conf"
        assert config_file.exists()
        config_content = config_file.read_text()
        assert "enabled=true" in config_content

    def test_disable_command(self, version_check_script, local_dir):
        """Test disable command sets enabled=false."""
        result = subprocess.run(
            [str(version_check_script), "off"],
            capture_output=True,
            text=True,
            timeout=5,
        )

        assert result.returncode == 0
        assert "disabled" in result.stdout.lower()

        config_file = local_dir / "version-check.conf"
        assert config_file.exists()
        config_content = config_file.read_text()
        assert "enabled=false" in config_content

    def test_mute_command_creates_file(self, version_check_script, local_dir):
        """Test that mute command creates muted-until file."""
        result = subprocess.run(
            [str(version_check_script), "mute", "1m"],
            capture_output=True,
            text=True,
            timeout=5,
        )

        assert result.returncode == 0
        assert "muted" in result.stdout.lower()

        muted_file = local_dir / ".muted-until"
        assert muted_file.exists(), "Muted-until file was not created"

        # Check timestamp is in the future
        muted_until = int(muted_file.read_text().strip())
        now = int(time.time())
        assert muted_until > now, "Muted timestamp should be in the future"
        assert muted_until < now + 120, "Muted timestamp is too far in the future"

    def test_interval_command(self, version_check_script, local_dir):
        """Test that interval command updates config."""
        result = subprocess.run(
            [str(version_check_script), "interval", "12h"],
            capture_output=True,
            text=True,
            timeout=5,
        )

        assert result.returncode == 0
        assert "interval" in result.stdout.lower()

        config_file = local_dir / "version-check.conf"
        assert config_file.exists()
        config_content = config_file.read_text()

        # 12 hours = 43200 seconds
        assert "interval=43200" in config_content

    def test_duration_parsing_days(self, version_check_script, local_dir):
        """Test duration parsing for days."""
        result = subprocess.run(
            [str(version_check_script), "interval", "7d"],
            capture_output=True,
            text=True,
            timeout=5,
        )

        assert result.returncode == 0

        config_file = local_dir / "version-check.conf"
        config_content = config_file.read_text()

        # 7 days = 604800 seconds
        assert "interval=604800" in config_content

    def test_duration_parsing_weeks(self, version_check_script, local_dir):
        """Test duration parsing for weeks."""
        result = subprocess.run(
            [str(version_check_script), "interval", "1w"],
            capture_output=True,
            text=True,
            timeout=5,
        )

        assert result.returncode == 0

        config_file = local_dir / "version-check.conf"
        config_content = config_file.read_text()

        # 1 week = 604800 seconds
        assert "interval=604800" in config_content

    def test_duration_parsing_invalid(self, version_check_script):
        """Test that invalid duration format returns error."""
        result = subprocess.run(
            [str(version_check_script), "interval", "invalid"],
            capture_output=True,
            text=True,
            timeout=5,
        )

        assert result.returncode != 0
        assert "invalid" in result.stdout.lower()

    def test_config_command_shows_status(self, version_check_script):
        """Test that config command shows current configuration."""
        # Set up known state
        subprocess.run(
            [str(version_check_script), "on"],
            capture_output=True,
            timeout=5,
        )
        subprocess.run(
            [str(version_check_script), "interval", "12h"],
            capture_output=True,
            timeout=5,
        )

        result = subprocess.run(
            [str(version_check_script), "config"],
            capture_output=True,
            text=True,
            timeout=5,
        )

        assert result.returncode == 0
        assert "Enabled:" in result.stdout
        assert "true" in result.stdout
        assert "Check interval:" in result.stdout
        assert "12 hour" in result.stdout

    def test_check_when_disabled(self, version_check_script):
        """Verbose check reports the disabled state and exits 0."""
        # Disable
        subprocess.run(
            [str(version_check_script), "off"],
            capture_output=True,
            timeout=5,
        )

        # Run check in verbose mode
        result = subprocess.run(
            [str(version_check_script), "check"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        assert result.returncode == 0
        # Verbose mode logs the disabled state before returning
        assert "disabled" in result.stdout.lower(), (
            f"verbose check should report the disabled state\nstdout: {result.stdout}"
        )

    def test_check_when_muted(self, version_check_script):
        """Verbose check reports the muted state and exits 0."""
        # First enable (mute requires it to be enabled)
        subprocess.run(
            [str(version_check_script), "on"],
            capture_output=True,
            timeout=5,
        )

        # Mute for 1 minute
        subprocess.run(
            [str(version_check_script), "mute", "1m"],
            capture_output=True,
            timeout=5,
        )

        # Run check in verbose mode
        result = subprocess.run(
            [str(version_check_script), "check"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        assert result.returncode == 0
        # Verbose mode logs the muted state before returning
        assert "muted" in result.stdout.lower(), (
            f"verbose check should report the muted state\nstdout: {result.stdout}"
        )

    def test_silent_mode_no_output_on_error(self, version_check_script):
        """Test that silent mode (default) produces no output on errors."""
        # Run without arguments (silent mode) - will fail to fetch from GitHub
        # but should exit cleanly
        result = subprocess.run(
            [str(version_check_script)],
            capture_output=True,
            text=True,
            timeout=10,
        )

        # Should always exit with 0 in silent mode
        assert result.returncode == 0
        # No error output
        assert len(result.stderr) == 0

    def test_missing_docker_compose_silent_failure(
        self, version_check_script, initialized_workspace
    ):
        """Test that missing docker-compose.yml doesn't break silent mode."""
        compose_file = initialized_workspace / ".devcontainer" / "docker-compose.yml"

        # Temporarily rename it
        backup_path = compose_file.with_suffix(".yml.backup")
        if compose_file.exists():
            compose_file.rename(backup_path)

        try:
            result = subprocess.run(
                [str(version_check_script)],
                capture_output=True,
                text=True,
                timeout=10,
            )

            # Should succeed silently
            assert result.returncode == 0
            assert len(result.stderr) == 0
        finally:
            # Restore file
            if backup_path.exists():
                backup_path.rename(compose_file)

    def test_missing_vig_os_silent_failure(
        self, version_check_script, initialized_workspace
    ):
        """Test that missing .vig-os doesn't break silent mode."""
        vig_os_file = initialized_workspace / ".vig-os"
        backup_path = initialized_workspace / ".vig-os.backup"

        if vig_os_file.exists():
            vig_os_file.rename(backup_path)

        try:
            result = subprocess.run(
                [str(version_check_script)],
                capture_output=True,
                text=True,
                timeout=10,
            )

            # Should succeed silently
            assert result.returncode == 0
            assert len(result.stderr) == 0
        finally:
            if backup_path.exists():
                backup_path.rename(vig_os_file)

    def test_just_check_config_via_just_command(self, initialized_workspace):
        """Regression: 'just devc-check config' resolves path correctly (issue #187)."""
        result = subprocess.run(
            ["just", "devc-check", "config"],
            capture_output=True,
            text=True,
            cwd=str(initialized_workspace),
            timeout=10,
        )

        assert result.returncode == 0, (
            f"just devc-check config failed (path resolution bug #187): {result.stderr}"
        )
        assert "Could not locate .devcontainer/scripts directory" not in (
            result.stdout + result.stderr
        ), "Path resolution broken: script dir not found"
        assert "Enabled:" in result.stdout, (
            f"devc-check config did not print the configuration\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )


class TestVersionCheckScaffold:
    """Content pins for the version-check feature's scaffold wiring.

    These read the assets/workspace sources directly — deployment of the same
    files into a workspace is covered by the structure/manifest tests — so no
    container or workspace fixture is needed.
    """

    @staticmethod
    def _recipe_block(content: str, header_pattern: str) -> str:
        """Extract a just recipe body: header line through the indented block."""
        lines = content.split("\n")
        start = next(
            (i for i, line in enumerate(lines) if re.match(header_pattern, line)),
            None,
        )
        assert start is not None, f"recipe matching {header_pattern!r} not found"
        end = len(lines)
        for j in range(start + 1, len(lines)):
            if lines[j] and not lines[j].startswith((" ", "\t")):
                end = j
                break
        return "\n".join(lines[start:end])

    @staticmethod
    def _assert_in_info_group(content: str, header_pattern: str):
        """Assert the recipe carries a [group('info')] annotation."""
        lines = content.split("\n")
        recipe_idx = next(
            (i for i, line in enumerate(lines) if re.match(header_pattern, line)),
            None,
        )
        assert recipe_idx is not None, f"recipe matching {header_pattern!r} not found"
        assert any(
            "[group('info')]" in lines[i]
            for i in range(max(0, recipe_idx - 5), recipe_idx)
        ), f"recipe matching {header_pattern!r} not in 'info' group"

    def test_version_check_script_wiring(self):
        """version-check.sh reads the .vig-os pin and its notification is accurate.

        The notification pins are anchored to the notify_update function body,
        not the whole file, so an unrelated comment cannot satisfy them.
        """
        content = (
            _WORKSPACE_ASSETS / ".devcontainer" / "scripts" / "version-check.sh"
        ).read_text()

        # Version source: the root .vig-os pin
        assert ".vig-os" in content, "version-check.sh should reference .vig-os"
        assert "DEVCONTAINER_VERSION" in content, (
            "version-check.sh should read DEVCONTAINER_VERSION"
        )

        # Notification message (anchored to the notify_update function body)
        start = content.find("notify_update() {")
        assert start != -1, "notify_update function not found"
        notify_body = content[start : content.find("\n}", start)]

        assert "just devc-upgrade" in notify_body, (
            "Notification should mention the 'just devc-upgrade' command"
        )
        assert "To update: ${BOLD}just update${NC}" not in notify_body, (
            "Notification should not suggest 'just update' for devcontainer upgrade"
        )
        assert "curl" in notify_body and "install.sh" in notify_body, (
            "Notification should show curl install.sh as fallback option"
        )
        assert "host terminal" in notify_body, (
            "Notification should clarify upgrade runs on host terminal"
        )
        assert "rebuild" in notify_body.lower(), (
            "Notification should remind user to rebuild container after upgrade"
        )
        assert "just devc-check off" in notify_body, (
            "Notification should show how to disable ('just devc-check off')"
        )
        assert "just devc-check 7d" in notify_body, (
            "Notification should show how to mute (e.g. 'just devc-check 7d')"
        )

    def test_post_attach_runs_version_check_silently(self):
        """post-attach.sh invokes version-check.sh silently, gracefully, at the end."""
        content = (
            _WORKSPACE_ASSETS / ".devcontainer" / "scripts" / "post-attach.sh"
        ).read_text()
        lines = content.split("\n")

        call_lines = [
            (i, line)
            for i, line in enumerate(lines)
            if "version-check.sh" in line and not line.strip().startswith("#")
        ]
        assert call_lines, "post-attach.sh doesn't call version-check.sh"
        call_idx, call_line = call_lines[0]

        # Silent mode: invoked with no subcommand arguments
        after_script = call_line.split("version-check.sh", 1)[1]
        assert not any(
            arg in after_script
            for arg in ["check", "config", "mute", "enable", "disable"]
        ), "post-attach.sh should call version-check.sh in silent mode (no args)"

        # Graceful failure: a failing check must not abort post-attach
        assert "|| true" in call_line or "|| :" in call_line, (
            "post-attach.sh should use graceful failure (|| true) for version-check.sh"
        )

        # Called near the end (within the last 10 meaningful lines)
        non_empty = [
            i
            for i, line in enumerate(lines)
            if line.strip() and not line.strip().startswith("#")
        ]
        assert (non_empty[-1] - call_idx) < 10, (
            "version-check.sh should be called near the end of post-attach.sh"
        )

    def test_devc_check_recipe(self):
        """justfile.devc's devc-check recipe wires version-check.sh correctly."""
        content = (_WORKSPACE_ASSETS / ".devcontainer" / "justfile.devc").read_text()

        # Recipe exists, accepts variadic args, lives in the info group
        assert re.search(r"(?m)^devc-check \*args:", content), (
            "devc-check recipe (with variadic args) not found in justfile.devc"
        )
        self._assert_in_info_group(content, r"^devc-check ")

        recipe = self._recipe_block(content, r"^devc-check ")
        assert "version-check.sh" in recipe, (
            "devc-check recipe doesn't call version-check.sh"
        )
        # No args -> verbose 'check' subcommand (not silent mode)
        assert "{ 'check' }" in recipe, (
            "devc-check recipe doesn't default to verbose check mode"
        )

    def test_devc_upgrade_recipe(self):
        """justfile.devc's devc-upgrade recipe guards and upgrades correctly."""
        content = (_WORKSPACE_ASSETS / ".devcontainer" / "justfile.devc").read_text()

        assert re.search(r"(?m)^devc-upgrade:", content), (
            "devc-upgrade recipe not found in justfile.devc"
        )
        self._assert_in_info_group(content, r"^devc-upgrade:")

        recipe = self._recipe_block(content, r"^devc-upgrade:")
        # Refuses to run inside a container, pointing at a host terminal
        assert "/.dockerenv" in recipe, (
            "devc-upgrade recipe should detect the container environment"
        )
        assert "ERROR" in recipe.upper(), (
            "devc-upgrade recipe should show an error message when run in container"
        )
        assert "host" in recipe.lower() and "terminal" in recipe.lower(), (
            "devc-upgrade error message should mention running from a host terminal"
        )
        # Checks a container runtime is available before upgrading
        assert "command -v podman" in recipe, (
            "devc-upgrade recipe should check if podman/docker is available"
        )
        # Runs the installer in upgrade mode
        assert "install.sh" in recipe, "devc-upgrade recipe should call install.sh"
        assert "--force" in recipe, (
            "devc-upgrade recipe should use --force flag for upgrades"
        )

    def test_project_recipe_split(self):
        """Project recipes live in justfile.project; justfile.devc stays devc-only."""
        justfile_devc = (
            _WORKSPACE_ASSETS / ".devcontainer" / "justfile.devc"
        ).read_text()
        justfile_project = (_WORKSPACE_ASSETS / "justfile.project").read_text()
        workspace_justfile = (_WORKSPACE_ASSETS / "justfile").read_text()

        for recipe_name in ["lint:", "format:", "precommit:", "sync ", "update:"]:
            assert recipe_name not in justfile_devc, (
                f"{recipe_name.rstrip(':')} should not exist in justfile.devc"
            )
            assert recipe_name in justfile_project, (
                f"{recipe_name.rstrip(':')} should exist in justfile.project"
            )

        # The workspace justfile imports justfile.devc optionally (``import?``)
        # so a direnv-mode workspace, which prunes .devcontainer/, still loads
        # `just` (#641).
        assert "import? '.devcontainer/justfile.devc'" in workspace_justfile
        assert "import '.devcontainer/justfile.base'" not in workspace_justfile

    def test_local_directory_gitignored(self):
        """.devcontainer/.local (version-check config/cache) is gitignored."""
        gitignore = (_WORKSPACE_ASSETS / ".devcontainer" / ".gitignore").read_text()
        assert ".local/" in gitignore, (
            ".local/ not gitignored in the scaffold .devcontainer/.gitignore"
        )
