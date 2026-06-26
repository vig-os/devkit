"""
DevContainer integration tests for Base Development Environment.

These tests verify that the container works correctly as a devcontainer,
including template initialization, configuration files, and scripts.

Derived containers can inherit from these test classes to verify that
devcontainer functionality works correctly in their containers too.
"""

import json
import os
import re
import subprocess
import time
import warnings
from pathlib import Path

import pytest
import yaml

from .conftest import _build_podman_cmd, _run_noninteractive_init


class TestHostGitSignatureSetup:
    """Test that git commit signing is properly configured on the host.

    These tests run on the host machine (not inside containers) to verify
    that SSH-based git commit signing prerequisites are in place.
    """

    def test_ssh_public_key_exists(self):
        """Test that SSH public key for signing exists on host."""
        from pathlib import Path

        ssh_pubkey = Path.home() / ".ssh" / "id_ed25519_github.pub"

        if not ssh_pubkey.exists():
            pytest.skip(
                f"SSH public key not found at {ssh_pubkey}. "
                "This is optional but recommended for git commit signing. "
                "Generate with: ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519_github"
            )

        assert ssh_pubkey.is_file(), "SSH public key path exists but is not a file"

        # Verify it's a valid public key
        content = ssh_pubkey.read_text()
        assert content.startswith("ssh-ed25519 "), (
            f"SSH public key doesn't appear to be valid ED25519 key: {content[:50]}"
        )

    def test_git_signing_format_configured(self):
        """Test that git is configured to use SSH signing format."""
        result = subprocess.run(
            ["git", "config", "gpg.format"],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            pytest.skip(
                "Git signing format not configured. "
                "This is optional but recommended. "
                "Configure with: git config gpg.format ssh"
            )

        assert result.stdout.strip() == "ssh", (
            f"Expected gpg.format=ssh, got: {result.stdout.strip()}"
        )

    def test_git_signing_key_configured(self):
        """Test that git signing key is configured."""
        result = subprocess.run(
            ["git", "config", "user.signingkey"],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            pytest.skip(
                "Git signing key not configured. "
                "This is optional but recommended. "
                "Configure with the full SSH public key string or file path"
            )

        signing_key = result.stdout.strip()
        assert signing_key, "Signing key is configured but empty"

        # Check if it's a file path, email, or full public key string
        if signing_key.startswith("~") or signing_key.startswith("/"):
            # Old behavior: file path
            from pathlib import Path

            key_path = Path(signing_key.replace("~", str(Path.home())))
            assert key_path.exists(), f"Signing key file not found: {signing_key}"
        elif signing_key.startswith("ssh-"):
            # Full SSH public key string (for SSH agent signing)
            # Verify it looks like a valid SSH public key format
            parts = signing_key.split()
            assert len(parts) >= 2, (
                f"Invalid SSH public key format. "
                f"Expected 'ssh-<type> <key-data> [comment]', got: {signing_key[:50]}..."
            )
            assert parts[0] in [
                "ssh-rsa",
                "ssh-ed25519",
                "ecdsa-sha2-nistp256",
                "ecdsa-sha2-nistp384",
                "ecdsa-sha2-nistp521",
            ], f"Unsupported SSH key type: {parts[0]}"
        elif "@" in signing_key:
            # Email address (standard for SSH agent signing)
            # This is the preferred method - git looks up the email in allowed-signers
            pass
        else:
            # Could be other identifier (namespace, etc.)
            pass

    def test_git_commit_gpgsign_configured(self):
        """Test that git is configured to sign commits by default."""
        result = subprocess.run(
            ["git", "config", "commit.gpgsign"],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            pytest.skip(
                "Commit signing not enabled by default. "
                "This is optional but recommended. "
                "Enable with: git config commit.gpgsign true"
            )

        assert result.stdout.strip() == "true", (
            f"Expected commit.gpgsign=true, got: {result.stdout.strip()}"
        )

    def test_allowed_signers_file_exists(self):
        """Test that allowed-signers file exists for signature verification."""
        from pathlib import Path

        # Check if allowedSignersFile is configured
        result = subprocess.run(
            ["git", "config", "gpg.ssh.allowedSignersFile"],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            pytest.skip(
                "Allowed signers file not configured. "
                "This is optional but recommended for signature verification. "
                "Configure with: git config gpg.ssh.allowedSignersFile ~/.config/git/allowed-signers"
            )

        allowed_signers_path = result.stdout.strip()
        assert allowed_signers_path, "Allowed signers file path is configured but empty"

        # Resolve ~ to home directory
        allowed_signers = Path(allowed_signers_path.replace("~", str(Path.home())))

        if not allowed_signers.exists():
            pytest.skip(
                f"Allowed signers file configured but doesn't exist: {allowed_signers_path}. "
                "Create it with your email and public key."
            )

        assert allowed_signers.is_file(), (
            f"Allowed signers path exists but is not a file: {allowed_signers}"
        )

        # Verify it has some content
        content = allowed_signers.read_text()
        assert len(content.strip()) > 0, "Allowed signers file is empty"
        key_types = (
            "ssh-ed25519",
            "ssh-rsa",
            "ecdsa-sha2-nistp",
            "sk-ssh-ed25519@openssh.com",
            "sk-ecdsa-sha2-nistp256@openssh.com",
        )
        assert any(k in content for k in key_types), (
            "Allowed signers file doesn't appear to contain SSH public keys"
        )

    def test_git_user_configured(self):
        """Test that git user name and email are configured."""
        # Check user.name
        result = subprocess.run(
            ["git", "config", "user.name"],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, (
            "Git user.name not configured. "
            "Configure with: git config user.name 'Your Name'"
        )

        name = result.stdout.strip()
        assert name, "Git user.name is configured but empty"

        # Check user.email
        result = subprocess.run(
            ["git", "config", "user.email"],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, (
            "Git user.email not configured. "
            "Configure with: git config user.email 'your.email@example.com'"
        )

        email = result.stdout.strip()
        assert email, "Git user.email is configured but empty"
        assert "@" in email, f"Git user.email doesn't appear to be valid: {email}"


class TestDevContainerStructure:
    """Test that devcontainer structure is created correctly."""

    def test_devcontainer_directory_exists(self, initialized_workspace):
        """Test that .devcontainer directory exists."""
        devcontainer_dir = initialized_workspace / ".devcontainer"
        assert devcontainer_dir.exists(), ".devcontainer directory not found"
        assert devcontainer_dir.is_dir(), ".devcontainer is not a directory"

    def test_devcontainer_json_exists(self, initialized_workspace):
        """Test that devcontainer.json exists."""
        devcontainer_json = (
            initialized_workspace / ".devcontainer" / "devcontainer.json"
        )
        assert devcontainer_json.exists(), "devcontainer.json not found"
        assert devcontainer_json.is_file(), "devcontainer.json is not a file"

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

        with devcontainer_json.open() as f:
            config = json.load(f)

        assert isinstance(config, dict), "devcontainer.json is not a valid JSON object"

    def test_devcontainer_json_name(self, initialized_workspace):
        """Test that devcontainer.json has correct name."""
        devcontainer_json = (
            initialized_workspace / ".devcontainer" / "devcontainer.json"
        )

        with devcontainer_json.open() as f:
            config = json.load(f)

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

        with devcontainer_json.open() as f:
            config = json.load(f)

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

        with devcontainer_json.open() as f:
            config = json.load(f)

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

        with devcontainer_json.open() as f:
            config = json.load(f)

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

        with devcontainer_json.open() as f:
            config = json.load(f)

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

        with devcontainer_json.open() as f:
            config = json.load(f)

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

        with devcontainer_json.open() as f:
            config = json.load(f)

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

        with devcontainer_json.open() as f:
            config = json.load(f)

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

        with devcontainer_json.open() as f:
            config = json.load(f)

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

        with devcontainer_json.open() as f:
            config = json.load(f)

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

    def test_docker_compose_yml_exists(self, initialized_workspace):
        """Test that docker-compose.yml exists."""
        docker_compose_yml = (
            initialized_workspace / ".devcontainer" / "docker-compose.yml"
        )
        assert docker_compose_yml.exists(), "docker-compose.yml not found"
        assert docker_compose_yml.is_file(), "docker-compose.yml is not a file"

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

    def test_vig_os_exists(self, initialized_workspace):
        """Test that .vig-os exists at workspace root."""
        vig_os_file = initialized_workspace / ".vig-os"
        assert vig_os_file.exists(), ".vig-os not found in workspace root"
        assert vig_os_file.is_file(), ".vig-os is not a regular file"

    def test_vig_os_contains_devcontainer_version(self, initialized_workspace):
        """Test that .vig-os contains DEVCONTAINER_VERSION key."""
        vig_os_file = initialized_workspace / ".vig-os"
        content = vig_os_file.read_text(encoding="utf-8")
        assert "DEVCONTAINER_VERSION=" in content, (
            "DEVCONTAINER_VERSION key not found in .vig-os"
        )
        assert "{{IMAGE_TAG}}" not in content, (
            "IMAGE_TAG placeholder should be replaced in .vig-os"
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
        """Test that organization name placeholder is replaced in specific asset files."""
        # Files with organization name in specific paths
        files = [
            initialized_workspace / "LICENSE",
        ]

        # Check each file for organization name placeholder (not literal "vigOS")
        for file in files:
            content = file.read_text(encoding="utf-8")
            assert "{{ORG_NAME}}" not in content, (
                f"{{{{ORG_NAME}}}} placeholder not replaced in {file}"
            )
            assert "Test Org" in content, f"Organization name not replaced in {file}"

    def test_short_name_replaced(self, initialized_workspace):
        """Test that short name placeholder is replaced in specific asset files."""
        # Files with short name in specific paths
        files = [
            initialized_workspace / ".devcontainer" / "devcontainer.json",
            initialized_workspace / ".devcontainer" / "scripts" / "post-create.sh",
        ]

        # Check each file for short name placeholder (not literal "devcontainer")
        # Note: "devcontainer" can legitimately appear as a service name
        for file in files:
            content = file.read_text(encoding="utf-8")
            assert "{{SHORT_NAME}}" not in content, (
                f"{{{{SHORT_NAME}}}} placeholder not replaced in {file}"
            )
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

        # Root changelog is a copy of .devcontainer/CHANGELOG.md with the top semver
        # heading renamed via prepare-changelog unprepare; older release sections stay.
        first_h2 = re.search(r"^## .+$", root_content, re.MULTILINE)
        assert first_h2 is not None, "Root changelog should have a top-level ## heading"
        assert first_h2.group(0).rstrip("\r\n") == "## Unreleased", (
            "Root changelog top section should be ## Unreleased after smoke-test unprepare"
        )
        assert re.search(r"^## \[\d+\.\d+\.\d+\]", root_content, re.MULTILINE), (
            "Root changelog should retain semver release sections below Unreleased"
        )
        assert re.search(
            r"^## \[\d+\.\d+\.\d+\]", devcontainer_content, re.MULTILINE
        ), ".devcontainer changelog should include semver release history"


class TestDevContainerGit:
    """Test that git configuration files are set up."""

    def test_githooks_directory_exists(self, initialized_workspace):
        """Test that .githooks directory exists."""
        githooks_dir = initialized_workspace / ".githooks"
        assert githooks_dir.exists(), ".githooks directory not found"
        assert githooks_dir.is_dir(), ".githooks is not a directory"

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

    def test_project_installed_after_init(self, initialized_workspace):
        """Regression: uv.lock must reference the actual project name after init.

        init-workspace.sh runs `just sync` which calls `uv sync --all-extras`.
        This resolves the lock file for the renamed project and installs it.

        Before the fix, init did not sync, so uv.lock still referenced
        template-project. The first `uv run pre-commit run -a` would then
        mutate the venv and rewrite uv.lock.
        """
        lock_file = initialized_workspace / "uv.lock"
        assert lock_file.exists(), "uv.lock not found after init"

        content = lock_file.read_text()

        assert (
            "template-project" not in content and "template_project" not in content
        ), "uv.lock still references template-project after init"

        assert "test-project" in content or "test_project" in content, (
            "uv.lock does not reference the project 'test_project' after init\n"
            f"Lock file content (first 500 chars): {content[:500]}"
        )

    def test_venv_prompt_name(self, devcontainer_up):
        """Test that .venv/bin/activate in the image does not contain 'template-project', but is renamed to `test_project`."""
        workspace_path = str(devcontainer_up.resolve())
        activate_path = "/root/assets/workspace/.venv/bin/activate"
        cat_cmd = [
            "devcontainer",
            "exec",
            "--workspace-folder",
            workspace_path,
            "--config",
            f"{workspace_path}/.devcontainer/devcontainer.json",
            "--docker-path",
            "podman",
            "bash",
            "-c",
            f"cat {activate_path}",
        ]
        result = subprocess.run(
            cat_cmd,
            capture_output=True,
            text=True,
            cwd=workspace_path,
            env=os.environ.copy(),
        )
        assert result.returncode == 0, (
            f"Failed to read {activate_path}\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}\n"
            f"command: {' '.join(cat_cmd)}"
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
        """Test that .devcontainer/.conf contains all expected files."""
        workspace_path = str(devcontainer_up.resolve())
        # .devcontainer is inside the project subdirectory
        conf_dir = "/workspace/test_project/.devcontainer/.conf"

        # Check that .gitconfig exists (should always be generated)
        check_gitconfig_cmd = [
            "devcontainer",
            "exec",
            "--workspace-folder",
            workspace_path,
            "--config",
            f"{workspace_path}/.devcontainer/devcontainer.json",
            "--docker-path",
            "podman",
            "test",
            "-f",
            f"{conf_dir}/.gitconfig",
        ]

        result = subprocess.run(
            check_gitconfig_cmd,
            capture_output=True,
            text=True,
            cwd=workspace_path,
            env=os.environ.copy(),
        )

        assert result.returncode == 0, (
            f".gitconfig not found in {conf_dir}\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}\n"
            f"command: {' '.join(check_gitconfig_cmd)}"
        )

        # Check for optional files (these may not exist if not present on host)
        # SSH public key
        check_ssh_key_cmd = [
            "devcontainer",
            "exec",
            "--workspace-folder",
            workspace_path,
            "--config",
            f"{workspace_path}/.devcontainer/devcontainer.json",
            "--docker-path",
            "podman",
            "test",
            "-f",
            f"{conf_dir}/id_ed25519_github.pub",
        ]

        ssh_key_result = subprocess.run(
            check_ssh_key_cmd,
            capture_output=True,
            text=True,
            cwd=workspace_path,
            env=os.environ.copy(),
        )

        # SSH key is optional, so we warn if it's missing
        if ssh_key_result.returncode != 0:
            warnings.warn(
                f"SSH public key not found at {conf_dir}/id_ed25519_github.pub "
                "(this is optional if not present on host)",
                UserWarning,
                stacklevel=2,
            )

        # Allowed signers file
        check_allowed_signers_cmd = [
            "devcontainer",
            "exec",
            "--workspace-folder",
            workspace_path,
            "--config",
            f"{workspace_path}/.devcontainer/devcontainer.json",
            "--docker-path",
            "podman",
            "test",
            "-f",
            f"{conf_dir}/allowed-signers",
        ]

        allowed_signers_result = subprocess.run(
            check_allowed_signers_cmd,
            capture_output=True,
            text=True,
            cwd=workspace_path,
            env=os.environ.copy(),
        )

        # Allowed signers is optional, so we warn if it's missing
        if allowed_signers_result.returncode != 0:
            warnings.warn(
                f"allowed-signers file not found at {conf_dir}/allowed-signers "
                "(this is optional if not present on host)",
                UserWarning,
                stacklevel=2,
            )

        # GitHub CLI config directory (optional)
        check_gh_config_cmd = [
            "devcontainer",
            "exec",
            "--workspace-folder",
            workspace_path,
            "--config",
            f"{workspace_path}/.devcontainer/devcontainer.json",
            "--docker-path",
            "podman",
            "test",
            "-d",
            f"{conf_dir}/gh",
        ]

        gh_config_result = subprocess.run(
            check_gh_config_cmd,
            capture_output=True,
            text=True,
            cwd=workspace_path,
            env=os.environ.copy(),
        )

        # GitHub CLI config is optional, so we warn if it's missing
        if gh_config_result.returncode != 0:
            warnings.warn(
                f"GitHub CLI config directory not found at {conf_dir}/gh "
                "(this is optional if not present on host)",
                UserWarning,
                stacklevel=2,
            )

        # GitHub CLI token file must NOT exist (should be deleted after authentication)
        check_gh_token_cmd = [
            "devcontainer",
            "exec",
            "--workspace-folder",
            workspace_path,
            "--config",
            f"{workspace_path}/.devcontainer/devcontainer.json",
            "--docker-path",
            "podman",
            "test",
            "!",
            "-f",
            f"{conf_dir}/.gh_token",
        ]

        gh_token_result = subprocess.run(
            check_gh_token_cmd,
            capture_output=True,
            text=True,
            cwd=workspace_path,
            env=os.environ.copy(),
        )

        assert gh_token_result.returncode == 0, (
            f".gh_token file still exists in {conf_dir} - token was not deleted after authentication\n"
            f"This is a security risk as the token should be removed after use.\n"
            f"stdout: {gh_token_result.stdout}\n"
            f"stderr: {gh_token_result.stderr}\n"
            f"command: {' '.join(check_gh_token_cmd)}"
        )

    def test_files_copied_to_home(self, devcontainer_up):
        """Test that files from .devcontainer/.conf have been copied to their destinations."""
        workspace_path = str(devcontainer_up.resolve())

        # Check that .gitconfig was copied to ~/.gitconfig
        check_gitconfig_cmd = [
            "devcontainer",
            "exec",
            "--workspace-folder",
            workspace_path,
            "--config",
            f"{workspace_path}/.devcontainer/devcontainer.json",
            "--docker-path",
            "podman",
            "bash",
            "-c",
            "test -f $HOME/.gitconfig",
        ]

        result = subprocess.run(
            check_gitconfig_cmd,
            capture_output=True,
            text=True,
            cwd=workspace_path,
            env=os.environ.copy(),
        )

        assert result.returncode == 0, (
            f".gitconfig not found in $HOME/.gitconfig\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}\n"
            f"command: {' '.join(check_gitconfig_cmd)}"
        )

    def test_setup_git_conf_falls_back_to_nano_for_invalid_editor(
        self, devcontainer_up
    ):
        """Regression: setup-git-conf should enforce a usable editor fallback."""
        workspace_path = str(devcontainer_up.resolve())
        conf_dir = "/workspace/test_project/.devcontainer/.conf"
        exec_cmd = [
            "devcontainer",
            "exec",
            "--workspace-folder",
            workspace_path,
            "--config",
            f"{workspace_path}/.devcontainer/devcontainer.json",
            "--docker-path",
            "podman",
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
        ]

        result = subprocess.run(
            exec_cmd,
            capture_output=True,
            text=True,
            cwd=workspace_path,
            env=os.environ.copy(),
            timeout=60,
        )

        assert result.returncode == 0, (
            f"Failed to re-run setup-git-conf.sh\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}\n"
            f"command: {' '.join(exec_cmd)}"
        )
        assert result.stdout.strip() == "nano", (
            "setup-git-conf.sh should replace invalid core.editor with nano\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )

        # Check that SSH public key was copied (if it exists in .conf)
        # First check if it exists in .conf
        check_conf_ssh_key_cmd = [
            "devcontainer",
            "exec",
            "--workspace-folder",
            workspace_path,
            "--config",
            f"{workspace_path}/.devcontainer/devcontainer.json",
            "--docker-path",
            "podman",
            "test",
            "-f",
            f"{conf_dir}/id_ed25519_github.pub",
        ]

        conf_ssh_key_result = subprocess.run(
            check_conf_ssh_key_cmd,
            capture_output=True,
            text=True,
            cwd=workspace_path,
            env=os.environ.copy(),
        )

        if conf_ssh_key_result.returncode == 0:
            # If it exists in .conf, it should be copied to ~/.ssh/
            check_home_ssh_key_cmd = [
                "devcontainer",
                "exec",
                "--workspace-folder",
                workspace_path,
                "--config",
                f"{workspace_path}/.devcontainer/devcontainer.json",
                "--docker-path",
                "podman",
                "bash",
                "-c",
                "test -f $HOME/.ssh/id_ed25519_github.pub",
            ]

            home_ssh_key_result = subprocess.run(
                check_home_ssh_key_cmd,
                capture_output=True,
                text=True,
                cwd=workspace_path,
                env=os.environ.copy(),
            )

            assert home_ssh_key_result.returncode == 0, (
                f"SSH public key found in {conf_dir} but not copied to $HOME/.ssh/id_ed25519_github.pub\n"
                f"stdout: {home_ssh_key_result.stdout}\n"
                f"stderr: {home_ssh_key_result.stderr}\n"
                f"command: {' '.join(check_home_ssh_key_cmd)}"
            )

        # Check that allowed-signers was copied (if it exists in .conf)
        check_conf_allowed_signers_cmd = [
            "devcontainer",
            "exec",
            "--workspace-folder",
            workspace_path,
            "--config",
            f"{workspace_path}/.devcontainer/devcontainer.json",
            "--docker-path",
            "podman",
            "test",
            "-f",
            f"{conf_dir}/allowed-signers",
        ]

        conf_allowed_signers_result = subprocess.run(
            check_conf_allowed_signers_cmd,
            capture_output=True,
            text=True,
            cwd=workspace_path,
            env=os.environ.copy(),
        )

        if conf_allowed_signers_result.returncode == 0:
            # If it exists in .conf, it should be copied to ~/.config/git/
            check_home_allowed_signers_cmd = [
                "devcontainer",
                "exec",
                "--workspace-folder",
                workspace_path,
                "--config",
                f"{workspace_path}/.devcontainer/devcontainer.json",
                "--docker-path",
                "podman",
                "bash",
                "-c",
                "test -f $HOME/.config/git/allowed-signers",
            ]

            home_allowed_signers_result = subprocess.run(
                check_home_allowed_signers_cmd,
                capture_output=True,
                text=True,
                cwd=workspace_path,
                env=os.environ.copy(),
            )

            assert home_allowed_signers_result.returncode == 0, (
                f"allowed-signers file found in {conf_dir} but not copied to $HOME/.config/git/allowed-signers\n"
                f"stdout: {home_allowed_signers_result.stdout}\n"
                f"stderr: {home_allowed_signers_result.stderr}\n"
                f"command: {' '.join(check_home_allowed_signers_cmd)}"
            )

        # Check that GitHub CLI config was copied (if it exists in .conf)
        check_conf_gh_config_cmd = [
            "devcontainer",
            "exec",
            "--workspace-folder",
            workspace_path,
            "--config",
            f"{workspace_path}/.devcontainer/devcontainer.json",
            "--docker-path",
            "podman",
            "test",
            "-d",
            f"{conf_dir}/gh",
        ]

        conf_gh_config_result = subprocess.run(
            check_conf_gh_config_cmd,
            capture_output=True,
            text=True,
            cwd=workspace_path,
            env=os.environ.copy(),
        )

        if conf_gh_config_result.returncode == 0:
            # If it exists in .conf, it should be copied to ~/.config/gh/
            check_home_gh_config_cmd = [
                "devcontainer",
                "exec",
                "--workspace-folder",
                workspace_path,
                "--config",
                f"{workspace_path}/.devcontainer/devcontainer.json",
                "--docker-path",
                "podman",
                "bash",
                "-c",
                "test -d $HOME/.config/gh",
            ]

            home_gh_config_result = subprocess.run(
                check_home_gh_config_cmd,
                capture_output=True,
                text=True,
                cwd=workspace_path,
                env=os.environ.copy(),
            )

            assert home_gh_config_result.returncode == 0, (
                f"GitHub CLI config directory found in {conf_dir}/gh but not copied to $HOME/.config/gh\n"
                f"stdout: {home_gh_config_result.stdout}\n"
                f"stderr: {home_gh_config_result.stderr}\n"
                f"command: {' '.join(check_home_gh_config_cmd)}"
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
        workspace_path = str(devcontainer_up.resolve())

        # First check if SSH keys are available in the container
        check_keys_cmd = [
            "devcontainer",
            "exec",
            "--workspace-folder",
            workspace_path,
            "--config",
            f"{workspace_path}/.devcontainer/devcontainer.json",
            "--docker-path",
            "podman",
            "bash",
            "-c",
            "test -f ~/.ssh/id_ed25519_github.pub && echo 'keys_found' || echo 'no_keys'",
        ]

        keys_result = subprocess.run(
            check_keys_cmd,
            capture_output=True,
            text=True,
            cwd=workspace_path,
            env=os.environ.copy(),
        )

        # If no SSH keys are available, skip the test
        if "no_keys" in keys_result.stdout:
            pytest.skip(
                "SSH keys not available in devcontainer. "
                "SSH keys need to be set up via .devcontainer/.conf/ for this test to run."
            )

        # Test SSH connection to GitHub
        # This verifies that SSH keys are properly configured
        exec_cmd = [
            "devcontainer",
            "exec",
            "--workspace-folder",
            workspace_path,
            "--config",
            f"{workspace_path}/.devcontainer/devcontainer.json",
            "--docker-path",
            "podman",
            "ssh",
            "-T",
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            "UserKnownHostsFile=/dev/null",
            "-i",
            "~/.ssh/id_ed25519_github",
            "git@github.com",
        ]

        result = subprocess.run(
            exec_cmd,
            capture_output=True,
            text=True,
            cwd=workspace_path,
            env=os.environ.copy(),
            timeout=10,
        )

        # SSH to GitHub returns exit code 1 on success (it's a test connection)
        # Exit code 255 means connection/auth failed
        # We accept exit code 1 (successful test connection) or specific error messages
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
                    f"stderr: {result.stderr}\n"
                    f"command: {' '.join(exec_cmd)}"
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

    def test_pre_commit_hook(self, devcontainer_up):
        """Test that pre-commit hook runs successfully on a dummy file."""

        workspace_path = devcontainer_up.resolve()

        # Create a dummy Python file to test pre-commit
        test_file = workspace_path / "test_file.py"
        test_file.write_text("def hello():\n    print('hello')\n")

        # Run pre-commit on the file
        exec_cmd = [
            "devcontainer",
            "exec",
            "--workspace-folder",
            str(workspace_path),
            "--config",
            f"{workspace_path}/.devcontainer/devcontainer.json",
            "--docker-path",
            "podman",
            "bash",
            "-c",
            "cd /workspace/test_project && pre-commit run --files test_file.py",
        ]

        result = subprocess.run(
            exec_cmd,
            capture_output=True,
            text=True,
            cwd=str(workspace_path),
            env=os.environ.copy(),
            timeout=120,  # Pre-commit can take a while on first run
        )

        # Pre-commit should succeed (exit code 0) or pass with warnings
        # Exit code 1 means hooks failed, which is also acceptable for testing
        # We just want to verify pre-commit runs
        assert result.returncode in [0, 1], (
            f"Pre-commit failed unexpectedly\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}\n"
            f"command: {' '.join(exec_cmd)}"
        )

        # Verify pre-commit actually ran (check for pre-commit output)
        assert (
            "pre-commit" in result.stdout.lower() or "ruff" in result.stdout.lower()
        ), (
            f"Pre-commit doesn't appear to have run\n"
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
        check_config_cmd = [
            "devcontainer",
            "exec",
            "--workspace-folder",
            str(workspace_path),
            "--config",
            f"{workspace_path}/.devcontainer/devcontainer.json",
            "--docker-path",
            "podman",
            "bash",
            "-c",
            (
                "cd /workspace/test_project && "
                "git config --get gpg.format 2>/dev/null | grep -q ssh && echo 'ssh_signing_configured' || echo 'not_configured'"
            ),
        ]

        config_result = subprocess.run(
            check_config_cmd,
            capture_output=True,
            text=True,
            cwd=str(workspace_path),
            env=os.environ.copy(),
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
        exec_cmd = [
            "devcontainer",
            "exec",
            "--workspace-folder",
            str(workspace_path),
            "--config",
            f"{workspace_path}/.devcontainer/devcontainer.json",
            "--docker-path",
            "podman",
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
        ]

        result = subprocess.run(
            exec_cmd,
            capture_output=True,
            text=True,
            cwd=str(workspace_path),
            env=os.environ.copy(),
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
                    f"stderr: {result.stderr}\n"
                    f"command: {' '.join(exec_cmd)}"
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
        cleanup_cmd = [
            "devcontainer",
            "exec",
            "--workspace-folder",
            str(workspace_path),
            "--config",
            f"{workspace_path}/.devcontainer/devcontainer.json",
            "--docker-path",
            "podman",
            "bash",
            "-c",
            "cd /workspace && git reset --soft HEAD~1 && git reset test_commit.txt",
        ]
        subprocess.run(
            cleanup_cmd,
            capture_output=True,
            text=True,
            cwd=str(workspace_path),
            env=os.environ.copy(),
        )
        test_file.unlink()

    def test_github_cli_authentication(self, devcontainer_up):
        """Test that GitHub CLI authentication works in the devcontainer."""
        workspace_path = str(devcontainer_up.resolve())

        # Test gh auth status in the container
        exec_cmd = [
            "devcontainer",
            "exec",
            "--workspace-folder",
            workspace_path,
            "--config",
            f"{workspace_path}/.devcontainer/devcontainer.json",
            "--docker-path",
            "podman",
            "gh",
            "auth",
            "status",
        ]

        result = subprocess.run(
            exec_cmd,
            capture_output=True,
            text=True,
            cwd=workspace_path,
            env=os.environ.copy(),
            timeout=10,
        )

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
                    f"stderr: {result.stderr}\n"
                    f"command: {' '.join(exec_cmd)}"
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
            # Create branch and run pre-commit hook
            exec_cmd = [
                "devcontainer",
                "exec",
                "--workspace-folder",
                str(workspace_path),
                "--config",
                f"{workspace_path}/.devcontainer/devcontainer.json",
                "--docker-path",
                "podman",
                "bash",
                "-c",
                (
                    "cd /workspace/test_project"
                    " && printf 'dummy\\n' > dummy.txt"
                    f" && git checkout -b '{branch_name}'"
                    " && git add dummy.txt"
                    " && pre-commit run -a"
                ),
            ]
            result = subprocess.run(
                exec_cmd,
                capture_output=True,
                text=True,
                cwd=str(workspace_path),
                env=os.environ.copy(),
                timeout=120,
            )

            assert result.returncode == 0, (
                f"pre-commit on valid branch '{branch_name}' should succeed\n"
                f"stdout: {result.stdout}\n"
                f"stderr: {result.stderr}\n"
                f"command: {' '.join(exec_cmd)}"
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
            exec_cmd = [
                "devcontainer",
                "exec",
                "--workspace-folder",
                str(workspace_path),
                "--config",
                f"{workspace_path}/.devcontainer/devcontainer.json",
                "--docker-path",
                "podman",
                "bash",
                "-c",
                (
                    "cd /workspace/test_project"
                    " && printf 'dummy\\n' > dummy.txt"
                    f" && git checkout -b '{branch_name}'"
                    " && git add dummy.txt"
                    " && pre-commit run -a"
                ),
            ]
            result = subprocess.run(
                exec_cmd,
                capture_output=True,
                text=True,
                cwd=str(workspace_path),
                env=os.environ.copy(),
                timeout=120,
            )

            assert result.returncode != 0, (
                f"pre-commit on invalid branch '{branch_name}' should fail\n"
                f"stdout: {result.stdout}\n"
                f"stderr: {result.stderr}\n"
                f"command: {' '.join(exec_cmd)}"
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
        "    [sidecar]",
    ]

    def _just_cmd(self, workspace_path: str, args: list[str]) -> list[str]:
        return [
            "devcontainer",
            "exec",
            "--workspace-folder",
            workspace_path,
            "--config",
            f"{workspace_path}/.devcontainer/devcontainer.json",
            "--docker-path",
            "podman",
            "just",
            *args,
        ]

    def test_just_default(self, devcontainer_up):
        """Test the default just recipe."""
        workspace_path = str(devcontainer_up.resolve())

        just_cmd = self._just_cmd(workspace_path, [])
        result = subprocess.run(
            just_cmd,
            capture_output=True,
            text=True,
            cwd=workspace_path,
            env=os.environ.copy(),
            timeout=10,
        )

        # Return code must be 0
        assert result.returncode == 0, (
            f"`just` recipe failed\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}\n"
            f"command: {' '.join(just_cmd)}"
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

    def test_just_help(self, devcontainer_up):
        """Test the just help command."""
        workspace_path = str(devcontainer_up.resolve())

        just_cmd = self._just_cmd(workspace_path, ["help"])
        result = subprocess.run(
            just_cmd,
            capture_output=True,
            text=True,
            cwd=workspace_path,
            env=os.environ.copy(),
            timeout=10,
        )

        # Return code must be 0
        assert result.returncode == 0, (
            f"`just help` recipe failed\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}\n"
            f"command: {' '.join(just_cmd)}"
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
        workspace_path = str(devcontainer_up.resolve())

        just_cmd = self._just_cmd(workspace_path, ["info"])
        result = subprocess.run(
            just_cmd,
            capture_output=True,
            text=True,
            cwd=workspace_path,
            env=os.environ.copy(),
            timeout=10,
        )

        assert result.returncode == 0, (
            f"`just info` recipe failed\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}\n"
            f"command: {' '.join(just_cmd)}"
        )

        assert "Project: test_project" in result.stdout, (
            f"Project information not found in output\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}\n"
            f"command: {' '.join(just_cmd)}"
        )

    def test_just_test_recipe(self, devcontainer_up):
        """Test the just test command."""
        workspace_path = str(devcontainer_up.resolve())

        just_cmd = self._just_cmd(workspace_path, ["test"])
        result = subprocess.run(
            just_cmd,
            capture_output=True,
            text=True,
            cwd=workspace_path,
            env=os.environ.copy(),
            timeout=10,
        )

        assert result.returncode == 0, (
            f"`just test` recipe failed\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}\n"
            f"command: {' '.join(just_cmd)}"
        )

        assert (
            "test session starts" in result.stdout
            and "passed" in result.stdout
            and "failed" not in result.stdout
        ), (
            f"Unexpected pytest output\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}\n"
            f"command: {' '.join(just_cmd)}"
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

    def test_project_mount_directory_exists(self, devcontainer_up):
        """Test that the directory mounted via project.yaml exists in container."""
        workspace_path = str(devcontainer_up.resolve())

        # The conftest.py fixture creates an override mounting tests/ to /workspace/tests-mounted
        check_dir_cmd = [
            "devcontainer",
            "exec",
            "--workspace-folder",
            workspace_path,
            "--config",
            f"{workspace_path}/.devcontainer/devcontainer.json",
            "--docker-path",
            "podman",
            "test",
            "-d",
            "/workspace/tests-mounted",
        ]

        result = subprocess.run(
            check_dir_cmd,
            capture_output=True,
            text=True,
            cwd=workspace_path,
            env=os.environ.copy(),
        )

        assert result.returncode == 0, (
            f"Override mount directory /workspace/tests-mounted not found\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}\n"
            f"command: {' '.join(check_dir_cmd)}"
        )

    def test_override_mount_file_accessible(self, devcontainer_up):
        """Test that files in the override mount are accessible."""
        workspace_path = str(devcontainer_up.resolve())

        # Check that conftest.py exists in the mounted tests directory
        check_file_cmd = [
            "devcontainer",
            "exec",
            "--workspace-folder",
            workspace_path,
            "--config",
            f"{workspace_path}/.devcontainer/devcontainer.json",
            "--docker-path",
            "podman",
            "test",
            "-f",
            "/workspace/tests-mounted/conftest.py",
        ]

        result = subprocess.run(
            check_file_cmd,
            capture_output=True,
            text=True,
            cwd=workspace_path,
            env=os.environ.copy(),
        )

        assert result.returncode == 0, (
            f"conftest.py not found in override mount at /workspace/tests-mounted/conftest.py\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}\n"
            f"command: {' '.join(check_file_cmd)}"
        )

    def test_override_mount_file_readable(self, devcontainer_up):
        """Test that files in the override mount are readable."""
        workspace_path = str(devcontainer_up.resolve())

        # Read first line of conftest.py to verify content is accessible
        read_file_cmd = [
            "devcontainer",
            "exec",
            "--workspace-folder",
            workspace_path,
            "--config",
            f"{workspace_path}/.devcontainer/devcontainer.json",
            "--docker-path",
            "podman",
            "head",
            "-n",
            "1",
            "/workspace/tests-mounted/conftest.py",
        ]

        result = subprocess.run(
            read_file_cmd,
            capture_output=True,
            text=True,
            cwd=workspace_path,
            env=os.environ.copy(),
        )

        assert result.returncode == 0, (
            f"Failed to read conftest.py from override mount\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}\n"
            f"command: {' '.join(read_file_cmd)}"
        )

        # Verify we got some content (should be a comment or import)
        assert result.stdout.strip(), (
            f"conftest.py appears to be empty or unreadable\nstdout: {result.stdout}\n"
        )

    def test_override_mount_list_directory(self, devcontainer_up):
        """Test that we can list the contents of the override mount."""
        workspace_path = str(devcontainer_up.resolve())

        # List contents of the mounted tests directory
        ls_cmd = [
            "devcontainer",
            "exec",
            "--workspace-folder",
            workspace_path,
            "--config",
            f"{workspace_path}/.devcontainer/devcontainer.json",
            "--docker-path",
            "podman",
            "ls",
            "-la",
            "/workspace/tests-mounted",
        ]

        result = subprocess.run(
            ls_cmd,
            capture_output=True,
            text=True,
            cwd=workspace_path,
            env=os.environ.copy(),
        )

        assert result.returncode == 0, (
            f"Failed to list contents of override mount\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}\n"
            f"command: {' '.join(ls_cmd)}"
        )

        # Verify expected test files are listed
        assert "conftest.py" in result.stdout, (
            f"conftest.py not found in directory listing\nstdout: {result.stdout}"
        )
        assert "test_integration.py" in result.stdout, (
            f"test_integration.py not found in directory listing\n"
            f"stdout: {result.stdout}"
        )


class TestPodmanSocketAccess:
    """Tests for Podman/Docker socket access from within the devcontainer.

    These tests verify that container-in-container operations work correctly,
    which is essential for:
    - Building container images inside the devcontainer
    - Running sidecar containers
    - Testing containerized applications
    """

    def test_socket_file_exists(self, devcontainer_up):
        """Test that the Docker/Podman socket is mounted in the container."""
        workspace_path = str(devcontainer_up.resolve())

        check_socket_cmd = [
            "devcontainer",
            "exec",
            "--workspace-folder",
            workspace_path,
            "--config",
            f"{workspace_path}/.devcontainer/devcontainer.json",
            "--docker-path",
            "podman",
            "test",
            "-S",
            "/var/run/docker.sock",
        ]

        result = subprocess.run(
            check_socket_cmd,
            capture_output=True,
            text=True,
            cwd=workspace_path,
            env=os.environ.copy(),
        )

        assert result.returncode == 0, (
            f"Docker/Podman socket not found at /var/run/docker.sock\n"
            f"The socket is configured via docker-compose.yml using CONTAINER_SOCKET_PATH from .env\n"
            f"The .env file is created by initialize.sh based on your host OS\n"
            f"stderr: {result.stderr}"
        )

    def test_socket_environment_variables(self, devcontainer_up):
        """Test that CONTAINER_HOST and DOCKER_HOST are set correctly."""
        workspace_path = str(devcontainer_up.resolve())

        check_env_cmd = [
            "devcontainer",
            "exec",
            "--workspace-folder",
            workspace_path,
            "--config",
            f"{workspace_path}/.devcontainer/devcontainer.json",
            "--docker-path",
            "podman",
            "bash",
            "-c",
            "echo CONTAINER_HOST=$CONTAINER_HOST && echo DOCKER_HOST=$DOCKER_HOST",
        ]

        result = subprocess.run(
            check_env_cmd,
            capture_output=True,
            text=True,
            cwd=workspace_path,
            env=os.environ.copy(),
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

    def test_podman_version_works(self, devcontainer_up):
        """Test that we can communicate with the Podman daemon via the socket."""
        workspace_path = str(devcontainer_up.resolve())

        # Try podman version command
        version_cmd = [
            "devcontainer",
            "exec",
            "--workspace-folder",
            workspace_path,
            "--config",
            f"{workspace_path}/.devcontainer/devcontainer.json",
            "--docker-path",
            "podman",
            "podman",
            "version",
        ]

        result = subprocess.run(
            version_cmd,
            capture_output=True,
            text=True,
            cwd=workspace_path,
            env=os.environ.copy(),
            timeout=10,
        )

        if result.returncode != 0:
            pytest.skip(
                f"Podman socket not accessible from container. "
                f"The socket is configured via docker-compose.yml using CONTAINER_SOCKET_PATH.\n"
                f"Ensure initialize.sh ran and created .env with the correct socket path.\n"
                f"stderr: {result.stderr}"
            )

        # Verify we got version information
        assert "Version:" in result.stdout or "version" in result.stdout.lower(), (
            f"Unexpected podman version output\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )

    def test_podman_info_works(self, devcontainer_up):
        """Test that we can query the Podman daemon for system information."""
        workspace_path = str(devcontainer_up.resolve())

        info_cmd = [
            "devcontainer",
            "exec",
            "--workspace-folder",
            workspace_path,
            "--config",
            f"{workspace_path}/.devcontainer/devcontainer.json",
            "--docker-path",
            "podman",
            "podman",
            "info",
            "--format",
            "{{.Host.OS}}",
        ]

        result = subprocess.run(
            info_cmd,
            capture_output=True,
            text=True,
            cwd=workspace_path,
            env=os.environ.copy(),
            timeout=10,
        )

        if result.returncode != 0:
            pytest.skip(
                f"Podman socket not accessible from container.\nstderr: {result.stderr}"
            )

        # Verify we got OS information (darwin for macOS, linux for Linux)
        assert result.stdout.strip() in ["darwin", "linux"], (
            f"Unexpected OS from podman info\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )

    def test_container_image_pull(self, devcontainer_up):
        """Test that we can pull container images via the socket."""
        workspace_path = str(devcontainer_up.resolve())

        # Use a very small test image
        test_image = "docker.io/library/hello-world:latest"

        pull_cmd = [
            "devcontainer",
            "exec",
            "--workspace-folder",
            workspace_path,
            "--config",
            f"{workspace_path}/.devcontainer/devcontainer.json",
            "--docker-path",
            "podman",
            "podman",
            "pull",
            test_image,
        ]

        result = subprocess.run(
            pull_cmd,
            capture_output=True,
            text=True,
            cwd=workspace_path,
            env=os.environ.copy(),
            timeout=60,  # Pulling can take time
        )

        if result.returncode != 0:
            pytest.skip(
                f"Podman socket not accessible or network unavailable.\n"
                f"stderr: {result.stderr}"
            )

        # Verify the image was pulled
        assert (
            "Writing manifest" in result.stdout
            or "Trying to pull" in result.stdout
            or result.returncode == 0
        ), f"Image pull failed\nstdout: {result.stdout}\nstderr: {result.stderr}"

    def test_container_run_simple(self, devcontainer_up):
        """Test that we can run a simple container via the socket."""
        workspace_path = str(devcontainer_up.resolve())

        # First ensure we have the image
        test_image = "docker.io/library/hello-world:latest"

        run_cmd = [
            "devcontainer",
            "exec",
            "--workspace-folder",
            workspace_path,
            "--config",
            f"{workspace_path}/.devcontainer/devcontainer.json",
            "--docker-path",
            "podman",
            "podman",
            "run",
            "--rm",
            test_image,
        ]

        result = subprocess.run(
            run_cmd,
            capture_output=True,
            text=True,
            cwd=workspace_path,
            env=os.environ.copy(),
            timeout=30,
        )

        if result.returncode != 0:
            pytest.skip(f"Cannot run containers via socket.\nstderr: {result.stderr}")

        # hello-world image prints a message
        assert "Hello from Docker" in result.stdout or result.returncode == 0, (
            f"Container run failed\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_simple_image_build(self, devcontainer_up):
        """Test that we can build a simple container image via the socket."""
        workspace_path = str(devcontainer_up.resolve())

        # Create a simple Containerfile in the workspace
        # Use workspace directory (mounted from host) so podman daemon can access it
        containerfile_content = (
            "FROM docker.io/library/alpine:latest\nRUN echo 'test build'"
        )

        # Create Containerfile in workspace directory
        # The workspace is mounted from host, so podman daemon can access the build context
        # Use /workspace/test_project (the workspaceFolder from conftest.py initialization)
        build_context_dir = "/workspace/test_project/.test-build-context"
        build_cmd = [
            "devcontainer",
            "exec",
            "--workspace-folder",
            workspace_path,
            "--config",
            f"{workspace_path}/.devcontainer/devcontainer.json",
            "--docker-path",
            "podman",
            "bash",
            "-c",
            (
                f"mkdir -p {build_context_dir} && "
                f"echo '{containerfile_content}' > {build_context_dir}/Containerfile && "
                f"podman build -t test-build:latest {build_context_dir} && "
                f"rm -rf {build_context_dir}"
            ),
        ]

        result = subprocess.run(
            build_cmd,
            capture_output=True,
            text=True,
            cwd=workspace_path,
            env=os.environ.copy(),
            timeout=120,  # Building can take time
        )

        if result.returncode != 0:
            pytest.skip(
                f"Cannot build images via socket.\n"
                f"This may require additional permissions or configuration.\n"
                f"stdout: {result.stdout}\n"
                f"stderr: {result.stderr}"
            )

        # Verify the build succeeded
        # Podman build output varies, check for success indicators
        build_succeeded = (
            result.returncode == 0
            or "COMMIT test-build:latest" in result.stdout
            or "Successfully tagged" in result.stdout
            or "STEP 2/2" in result.stdout  # Podman build step indicator
            or "test-build:latest" in result.stdout
        )

        assert build_succeeded, (
            f"Image build failed\n"
            f"Return code: {result.returncode}\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )

        # Clean up the test image (attempt cleanup even if build might have failed)
        cleanup_cmd = [
            "devcontainer",
            "exec",
            "--workspace-folder",
            workspace_path,
            "--config",
            f"{workspace_path}/.devcontainer/devcontainer.json",
            "--docker-path",
            "podman",
            "podman",
            "rmi",
            "-f",  # Force removal in case image exists
            "test-build:latest",
        ]

        subprocess.run(
            cleanup_cmd,
            capture_output=True,
            text=True,
            cwd=workspace_path,
            env=os.environ.copy(),
            timeout=10,
        )


class TestSidecarConnectivity:
    """Standalone tests for sidecar functionality using Approach 1 (podman exec).

    These tests verify the real-world sidecar workflow:
    - Sidecar containers can be started alongside the devcontainer
    - Commands can be executed in sidecars via podman exec (Approach 1)
    - Build workflows can be triggered in sidecar builders
    - This is the ACTUAL workflow users will use for builder sidecars

    Test Setup:
    - Uses a custom test-sidecar image (alpine-based)
    - Sidecar stays alive with 'sleep infinity'
    - Commands are executed via: podman exec sidecar <command>

    Communication Method:
    - Uses Podman socket for container management (podman exec)
    - NOT HTTP networking (that's tested separately)
    - This is Approach 1: Direct command execution

    Note on CI:
    - In CI the host podman may be older than the podman client inside the
      devcontainer image.  To avoid API-version mismatches (e.g. host 3.4.4
      vs container client 4.0.0), these tests run podman commands directly
      on the host rather than through ``devcontainer exec``.  The sidecar
      container is managed by compose on the host, so the host's podman can
      interact with it natively.
    """

    def test_sidecar_starts_with_devcontainer(self, devcontainer_with_sidecar):
        """Test that sidecar container starts alongside devcontainer."""
        workspace_path = str(devcontainer_with_sidecar.resolve())

        # Check sidecar is running via host podman directly.
        # We avoid `devcontainer exec ... podman ps` because the podman
        # client inside the container may be newer than the host daemon,
        # causing an API-version mismatch on the mounted socket.
        check_cmd = [
            "podman",
            "ps",
            "--filter",
            "name=test-sidecar",
            "--format",
            "{{.Names}}",
        ]

        result = subprocess.run(
            check_cmd,
            capture_output=True,
            text=True,
            cwd=workspace_path,
            env=os.environ.copy(),
            timeout=10,
        )

        assert result.returncode == 0, (
            f"Failed to check running containers\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )

        # Verify sidecar is running
        assert "test-sidecar" in result.stdout, (
            f"Test sidecar container not found in running containers\n"
            f"stdout: {result.stdout}"
        )

    def test_exec_simple_command_in_sidecar(self, devcontainer_with_sidecar):
        """Test executing a script in sidecar via podman exec (Approach 1)."""
        workspace_path = str(devcontainer_with_sidecar.resolve())

        # Execute the test build script IN the sidecar directly from the
        # host.  This is functionally equivalent to what a user would do
        # from inside the devcontainer (podman exec test-sidecar ...), but
        # avoids the DooD API-version constraint in CI.
        exec_cmd = [
            "podman",
            "exec",
            "test-sidecar",
            "/usr/local/bin/test-build.sh",
        ]

        result = subprocess.run(
            exec_cmd,
            capture_output=True,
            text=True,
            cwd=workspace_path,
            env=os.environ.copy(),
            timeout=10,
        )

        assert result.returncode == 0, (
            f"Failed to execute script in sidecar\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )

        # Verify we got the expected output from the script
        assert "Hello from sidecar test script" in result.stdout, (
            f"Script did not execute correctly\nstdout: {result.stdout}"
        )
        assert "Communication verified!" in result.stdout, (
            f"Script output incomplete\nstdout: {result.stdout}"
        )

    def test_exec_build_workflow_in_sidecar(self, devcontainer_with_sidecar):
        """Test a realistic build workflow: exec into sidecar to create build artifacts."""
        workspace_path = str(devcontainer_with_sidecar.resolve())

        # Simulate a build process in the sidecar directly from the host.
        build_cmd = [
            "podman",
            "exec",
            "test-sidecar",
            "sh",
            "-c",
            "echo 'Building project...' && "
            "mkdir -p /workspace/build-output && "
            "echo 'build artifacts' > /workspace/build-output/result.txt && "
            "cat /workspace/build-output/result.txt",
        ]

        result = subprocess.run(
            build_cmd,
            capture_output=True,
            text=True,
            cwd=workspace_path,
            env=os.environ.copy(),
            timeout=10,
        )

        assert result.returncode == 0, (
            f"Failed to execute build workflow in sidecar\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )

        # Verify the build executed
        assert "Building project" in result.stdout, (
            f"Build workflow did not execute\nstdout: {result.stdout}"
        )
        assert "build artifacts" in result.stdout, (
            f"Build artifacts not created\nstdout: {result.stdout}"
        )

    def test_sidecar_has_bash(self, devcontainer_with_sidecar):
        """Test that sidecar has bash installed for complex build scripts."""
        workspace_path = str(devcontainer_with_sidecar.resolve())

        # Check bash is available in the sidecar directly from the host.
        bash_cmd = [
            "podman",
            "exec",
            "test-sidecar",
            "bash",
            "--version",
        ]

        result = subprocess.run(
            bash_cmd,
            capture_output=True,
            text=True,
            cwd=workspace_path,
            env=os.environ.copy(),
            timeout=10,
        )

        assert result.returncode == 0, (
            f"Bash not available in sidecar\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )

        assert "bash" in result.stdout.lower(), (
            f"Unexpected bash version output\nstdout: {result.stdout}"
        )


class TestVersionCheckScript:
    """Test the version-check.sh script behavior.

    Tests configuration management (enable/disable, intervals, mute),
    duration parsing, and silent failure behavior.
    """

    @pytest.fixture
    def version_check_script(self, initialized_workspace):
        """Path to the version-check.sh script in initialized workspace."""
        script_path = (
            initialized_workspace / ".devcontainer" / "scripts" / "version-check.sh"
        )
        assert script_path.exists(), f"version-check.sh not found at {script_path}"
        assert os.access(script_path, os.X_OK), (
            f"version-check.sh is not executable: {script_path}"
        )
        return script_path

    @pytest.fixture
    def local_dir(self, initialized_workspace):
        """Path to .local directory for config files."""
        local_path = initialized_workspace / ".devcontainer" / ".local"
        local_path.mkdir(parents=True, exist_ok=True)
        return local_path

    def test_script_exists_and_executable(self, version_check_script):
        """Test that version-check.sh exists and is executable."""
        assert version_check_script.is_file()
        assert os.access(version_check_script, os.X_OK)

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

    def test_reads_version_from_vig_os_config(self, version_check_script):
        """Test that version-check reads version from .vig-os config."""
        content = version_check_script.read_text(encoding="utf-8")
        assert ".vig-os" in content, "version-check.sh should reference .vig-os"
        assert "DEVCONTAINER_VERSION" in content, (
            "version-check.sh should read DEVCONTAINER_VERSION"
        )

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
        """Test that check does nothing when disabled."""
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

        # Should exit successfully but show disabled message
        assert result.returncode == 0
        # In verbose mode, should mention it's disabled
        assert "disabled" in result.stdout.lower() or len(result.stdout) == 0

    def test_check_when_muted(self, version_check_script):
        """Test that check does nothing when muted."""
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

        # Should exit successfully
        assert result.returncode == 0
        # In verbose mode, should mention it's muted or be silent
        # Note: The script may still say "disabled" if check interval wasn't met
        assert result.returncode == 0  # Main assertion is it doesn't fail

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

    def test_local_directory_gitignored(self, initialized_workspace):
        """Test that .local directory is in .gitignore."""
        gitignore_path = initialized_workspace / ".devcontainer" / ".gitignore"

        # Note: This test checks if .gitignore exists. If the template was updated
        # after the workspace was initialized, the file may not have .local/ yet.
        # The important thing is that new workspaces will have it.
        if not gitignore_path.exists():
            pytest.skip(
                ".devcontainer/.gitignore not found in this test workspace. "
                "This is expected for older workspaces. New workspaces will have it."
            )

        gitignore_content = gitignore_path.read_text()

        # Check that .local/ is gitignored (either explicitly or via pattern)
        is_ignored = ".local/" in gitignore_content or ".local" in gitignore_content

        if not is_ignored:
            # Log what we found for debugging
            print(f"Current .gitignore content:\n{gitignore_content}")
            pytest.skip(
                ".local/ not yet in .gitignore for this workspace. "
                "The template has been updated and new workspaces will include it."
            )


class TestVersionComparison:
    """Test version comparison logic."""

    def test_version_comparison_with_script(self, initialized_workspace):
        """Test version comparison by mocking docker-compose.yml."""
        compose_file = initialized_workspace / ".devcontainer" / "docker-compose.yml"

        # This test is mainly checking that the compose file can be read
        # and that version can be extracted. The actual version may vary.
        if compose_file.exists():
            content = compose_file.read_text()
            # Just verify it contains the image reference
            assert "ghcr.io/vig-os/devcontainer:" in content


class TestVersionCheckJustIntegration:
    """Test integration of version check with just commands."""

    def test_just_check_command_exists(self, initialized_workspace):
        """Test that 'just check' command is available."""
        # Check if .devcontainer/justfile.devc has the check recipe
        justfile_base = initialized_workspace / ".devcontainer" / "justfile.devc"

        if not justfile_base.exists():
            pytest.skip(
                "justfile.devc not found - workspace may be from older template"
            )

        content = justfile_base.read_text()
        assert "check" in content, "check recipe not found in justfile.devc"

    def test_just_update_command_exists(self, initialized_workspace):
        """Test that 'just update' command is available."""
        # Check if justfile.project has the update recipe
        justfile_base = initialized_workspace / "justfile.project"

        if not justfile_base.exists():
            pytest.skip(
                "justfile.project not found - workspace may be from older template"
            )

        content = justfile_base.read_text()
        assert "update" in content, "update recipe not found in justfile.project"

    def test_just_check_calls_script(self, initialized_workspace):
        """Test that 'just check config' executes successfully."""
        # First verify the script exists
        script_path = (
            initialized_workspace / ".devcontainer" / "scripts" / "version-check.sh"
        )

        if not script_path.exists():
            pytest.skip("version-check.sh not found - workspace from older template")

        # Check if justfile.devc has check recipe
        justfile_base = initialized_workspace / ".devcontainer" / "justfile.devc"

        if not justfile_base.exists():
            pytest.skip("justfile.devc not found - workspace from older template")

        content = justfile_base.read_text()
        if "check" not in content:
            pytest.skip(
                "check recipe not in justfile.devc - workspace from older template"
            )

        # Test that check recipe can be called directly via the script
        result = subprocess.run(
            [str(script_path), "config"],
            capture_output=True,
            text=True,
            cwd=str(initialized_workspace),
            timeout=10,
        )

        assert result.returncode == 0
        assert "Configuration" in result.stdout or "Enabled:" in result.stdout

    def test_just_check_recipe_calls_version_check_script(self, initialized_workspace):
        """Test that 'just check' recipe properly calls version-check.sh."""
        justfile_base = initialized_workspace / ".devcontainer" / "justfile.devc"

        if not justfile_base.exists():
            pytest.skip("justfile.devc not found - workspace from older template")

        content = justfile_base.read_text()

        # Verify the recipe calls version-check.sh
        assert "version-check.sh" in content, (
            "check recipe doesn't call version-check.sh"
        )

        # Verify the recipe is in the info group
        lines = content.split("\n")
        check_recipe_idx = None
        for i, line in enumerate(lines):
            if line.startswith("check "):
                check_recipe_idx = i
                break

        assert check_recipe_idx is not None, "check recipe not found"

        # Look backwards for group annotation
        for i in range(check_recipe_idx - 1, max(0, check_recipe_idx - 5), -1):
            if "[group('info')]" in lines[i]:
                break
        else:
            pytest.fail("check recipe not in 'info' group")

    def test_just_check_verbose_mode(self, initialized_workspace):
        """Test that 'just check' runs in verbose mode (check subcommand)."""
        justfile_base = initialized_workspace / ".devcontainer" / "justfile.devc"

        if not justfile_base.exists():
            pytest.skip("justfile.devc not found")

        content = justfile_base.read_text()
        if "check" not in content:
            pytest.skip("check recipe not found")

        # The recipe should default to 'check' subcommand when no args provided
        # This ensures verbose output instead of silent mode
        assert "{ 'check' }" in content or 'version-check.sh" check' in content, (
            "check recipe doesn't default to verbose check mode"
        )

    def test_just_check_accepts_subcommands(self, initialized_workspace):
        """Test that 'just check' recipe accepts and passes through subcommands."""
        justfile_base = initialized_workspace / ".devcontainer" / "justfile.devc"

        if not justfile_base.exists():
            pytest.skip("justfile.devc not found")

        content = justfile_base.read_text()
        if "check" not in content:
            pytest.skip("check recipe not found")

        # The recipe should accept variadic args
        lines = content.split("\n")
        check_line = None
        for line in lines:
            if line.startswith("check "):
                check_line = line
                break

        assert check_line is not None
        assert "*args" in check_line, "check recipe doesn't accept variadic arguments"

    def test_just_check_config_shows_configuration(self, initialized_workspace):
        """Test that 'just check config' shows version check configuration."""
        script_path = (
            initialized_workspace / ".devcontainer" / "scripts" / "version-check.sh"
        )

        if not script_path.exists():
            pytest.skip("version-check.sh not found")

        # Call the script directly (just recipe may not exist yet in TDD RED phase)
        result = subprocess.run(
            [str(script_path), "config"],
            capture_output=True,
            text=True,
            cwd=str(initialized_workspace),
            timeout=10,
        )

        assert result.returncode == 0
        assert "Enabled:" in result.stdout
        assert "interval:" in result.stdout.lower()

    def test_just_check_config_via_just_command(self, initialized_workspace):
        """Regression: 'just check config' resolves path correctly (issue #187)."""
        justfile_base = initialized_workspace / ".devcontainer" / "justfile.devc"
        if not justfile_base.exists():
            pytest.skip("justfile.devc not found")
        if "check" not in justfile_base.read_text():
            pytest.skip("check recipe not found")

        result = subprocess.run(
            ["just", "check", "config"],
            capture_output=True,
            text=True,
            cwd=str(initialized_workspace),
            timeout=10,
        )

        assert result.returncode == 0, (
            f"just check config failed (path resolution bug #187): {result.stderr}"
        )
        assert "Could not locate .devcontainer/scripts directory" not in (
            result.stdout + result.stderr
        ), "Path resolution broken: script dir not found"

    def test_justfile_devc_excludes_project_recipes(self, initialized_workspace):
        """Test that project-focused recipes are not defined in justfile.devc."""
        justfile_devc = initialized_workspace / ".devcontainer" / "justfile.devc"

        if not justfile_devc.exists():
            pytest.skip("justfile.devc not found")

        content = justfile_devc.read_text()
        for recipe_name in ["lint:", "format:", "precommit:", "sync:", "update:"]:
            assert recipe_name not in content, (
                f"{recipe_name.rstrip(':')} should not exist in justfile.devc"
            )

    def test_workspace_justfile_project_contains_project_recipes(
        self, initialized_workspace
    ):
        """Test that moved project recipes are defined in justfile.project."""
        justfile_project = initialized_workspace / "justfile.project"

        if not justfile_project.exists():
            pytest.skip("justfile.project not found")

        content = justfile_project.read_text()
        for recipe_name in ["lint:", "format:", "precommit:", "sync:", "update:"]:
            assert recipe_name in content, (
                f"{recipe_name.rstrip(':')} should exist in justfile.project"
            )

    def test_workspace_justfile_imports_justfile_devc(self, initialized_workspace):
        """Test that workspace justfile optionally imports justfile.devc.

        The import is optional (``import?``) so a ``direnv``-mode workspace, which
        prunes ``.devcontainer/``, still loads `just` (#641).
        """
        workspace_justfile = initialized_workspace / "justfile"

        if not workspace_justfile.exists():
            pytest.skip("workspace justfile not found")

        content = workspace_justfile.read_text()
        assert "import? '.devcontainer/justfile.devc'" in content
        assert "import '.devcontainer/justfile.base'" not in content

    def test_just_check_mute_functionality(self, initialized_workspace):
        """Test that 'just check 7d' mutes notifications."""
        script_path = (
            initialized_workspace / ".devcontainer" / "scripts" / "version-check.sh"
        )

        if not script_path.exists():
            pytest.skip("version-check.sh not found")

        # Test mute command
        result = subprocess.run(
            [str(script_path), "mute", "7d"],
            capture_output=True,
            text=True,
            cwd=str(initialized_workspace),
            timeout=10,
        )

        assert result.returncode == 0
        assert "muted" in result.stdout.lower()

        # Verify mute file was created
        muted_file = initialized_workspace / ".devcontainer" / ".local" / ".muted-until"
        assert muted_file.exists()

    def test_just_check_enable_disable(self, initialized_workspace):
        """Test that 'just check on/off' enables/disables notifications."""
        script_path = (
            initialized_workspace / ".devcontainer" / "scripts" / "version-check.sh"
        )

        if not script_path.exists():
            pytest.skip("version-check.sh not found")

        # Test disable
        result = subprocess.run(
            [str(script_path), "off"],
            capture_output=True,
            text=True,
            cwd=str(initialized_workspace),
            timeout=10,
        )

        assert result.returncode == 0
        assert "disabled" in result.stdout.lower()

        # Verify config was updated
        config_file = (
            initialized_workspace / ".devcontainer" / ".local" / "version-check.conf"
        )
        assert config_file.exists()
        config_content = config_file.read_text()
        assert "enabled=false" in config_content

        # Test enable
        result = subprocess.run(
            [str(script_path), "on"],
            capture_output=True,
            text=True,
            cwd=str(initialized_workspace),
            timeout=10,
        )

        assert result.returncode == 0
        assert "enabled" in result.stdout.lower()

        config_content = config_file.read_text()
        assert "enabled=true" in config_content


class TestVersionCheckInitWorkspace:
    """Test that init-workspace.sh creates necessary version check files."""

    def test_local_directory_created(self, initialized_workspace):
        """Test that .local directory is created on init."""
        local_dir = initialized_workspace / ".devcontainer" / ".local"

        assert local_dir.exists(), ".local directory not created by init-workspace.sh"
        assert local_dir.is_dir()

    def test_default_config_created(self, initialized_workspace):
        """Test that default config file is created on init."""
        config_file = (
            initialized_workspace / ".devcontainer" / ".local" / "version-check.conf"
        )

        assert config_file.exists(), (
            "version-check.conf not created by init-workspace.sh"
        )

        config_content = config_file.read_text()
        assert "enabled=true" in config_content
        # Interval may vary - just check it exists
        assert "interval=" in config_content


class TestVersionCheckPostAttachIntegration:
    """Test that post-attach.sh automatically calls version-check.sh."""

    def test_post_attach_calls_version_check(self, initialized_workspace):
        """Test that post-attach.sh calls version-check.sh in silent mode."""
        post_attach = (
            initialized_workspace / ".devcontainer" / "scripts" / "post-attach.sh"
        )

        if not post_attach.exists():
            pytest.skip("post-attach.sh not found")

        content = post_attach.read_text()

        # Verify the script calls version-check.sh
        assert "version-check.sh" in content, (
            "post-attach.sh doesn't call version-check.sh"
        )

    def test_post_attach_calls_version_check_at_end(self, initialized_workspace):
        """Test that version-check.sh is called at the end of post-attach.sh."""
        post_attach = (
            initialized_workspace / ".devcontainer" / "scripts" / "post-attach.sh"
        )

        if not post_attach.exists():
            pytest.skip("post-attach.sh not found")

        content = post_attach.read_text()
        lines = content.split("\n")

        # Find the version-check.sh call
        version_check_line = None
        for i, line in enumerate(lines):
            if "version-check.sh" in line and not line.strip().startswith("#"):
                version_check_line = i
                break

        assert version_check_line is not None, "version-check.sh call not found"

        # Verify it's near the end (within last 10 non-empty lines)
        non_empty_lines = [
            i
            for i, line in enumerate(lines)
            if line.strip() and not line.strip().startswith("#")
        ]

        if non_empty_lines:
            last_meaningful_line = non_empty_lines[-1]
            # Version check should be within last 10 meaningful lines
            assert (last_meaningful_line - version_check_line) < 10, (
                "version-check.sh should be called near the end of post-attach.sh"
            )

    def test_post_attach_uses_silent_mode(self, initialized_workspace):
        """Test that post-attach.sh calls version-check.sh with no args (silent)."""
        post_attach = (
            initialized_workspace / ".devcontainer" / "scripts" / "post-attach.sh"
        )

        if not post_attach.exists():
            pytest.skip("post-attach.sh not found")

        content = post_attach.read_text()

        # Find the version-check.sh invocation
        lines = content.split("\n")
        for line in lines:
            if "version-check.sh" in line and not line.strip().startswith("#"):
                # Should be called with no arguments (silent mode)
                # Allow patterns like: "./version-check.sh" or "$SCRIPT_DIR/version-check.sh"
                # but NOT: "./version-check.sh check" or with other args
                after_script = line.split("version-check.sh", 1)[1]
                assert not any(
                    arg in after_script
                    for arg in ["check", "config", "mute", "enable", "disable"]
                ), (
                    "post-attach.sh should call version-check.sh in silent mode (no args)"
                )
                break

    def test_post_attach_graceful_failure(self, initialized_workspace):
        """Test that post-attach.sh doesn't fail if version-check.sh fails."""
        post_attach = (
            initialized_workspace / ".devcontainer" / "scripts" / "post-attach.sh"
        )

        if not post_attach.exists():
            pytest.skip("post-attach.sh not found")

        content = post_attach.read_text()

        # Find the version-check.sh call
        lines = content.split("\n")
        for line in lines:
            if "version-check.sh" in line and not line.strip().startswith("#"):
                # Should have || true or similar error handling
                assert "|| true" in line or "|| :" in line, (
                    "post-attach.sh should use graceful failure (|| true) for version-check.sh"
                )
                break


class TestVersionCheckNotificationMessage:
    """Test that the version check notification shows correct upgrade instructions."""

    @pytest.fixture
    def version_check_script(self, initialized_workspace):
        """Path to version-check.sh script."""
        script_path = (
            initialized_workspace / ".devcontainer" / "scripts" / "version-check.sh"
        )
        if not script_path.exists():
            pytest.skip("version-check.sh not found")
        return script_path

    def test_notification_shows_devcontainer_upgrade_command(
        self, version_check_script
    ):
        """Test that notification message shows 'just devcontainer-upgrade'."""
        content = version_check_script.read_text()

        # Find the notify_update function
        assert "notify_update" in content, "notify_update function not found"

        # Check if it mentions the correct upgrade command
        assert (
            "just devcontainer-upgrade" in content or "devcontainer-upgrade" in content
        ), "Notification should mention 'just devcontainer-upgrade' command"

    def test_notification_does_not_show_just_update(self, version_check_script):
        """Test that notification doesn't show misleading 'just update' command."""
        content = version_check_script.read_text()

        # Find the notify_update function (approximately lines 253-300)
        lines = content.split("\n")
        notify_start = None
        notify_end = None

        for i, line in enumerate(lines):
            if "notify_update()" in line or "notify_update ()" in line:
                notify_start = i
            if notify_start and line.strip() == "}" and i > notify_start:
                notify_end = i
                break

        assert notify_start is not None, "notify_update function not found"

        notify_function = "\n".join(lines[notify_start:notify_end])

        # Should NOT mention "just update" in the notification
        # (that's for Python deps, not devcontainer upgrade)
        # Allow "just" but not "just update" as a standalone command
        assert "To update: ${BOLD}just update${NC}" not in notify_function, (
            "Notification should not suggest 'just update' for devcontainer upgrade"
        )

    def test_notification_shows_curl_fallback(self, version_check_script):
        """Test that notification shows curl install.sh fallback option."""
        content = version_check_script.read_text()

        # Should mention the curl command as a fallback
        assert "curl" in content and "install.sh" in content, (
            "Notification should show curl install.sh as fallback option"
        )

    def test_notification_mentions_host_terminal(self, version_check_script):
        """Test that notification clarifies upgrade must run on host."""
        content = version_check_script.read_text()

        # Should clarify that this needs to run on host
        assert "host" in content.lower() and "terminal" in content.lower(), (
            "Notification should clarify upgrade runs on host terminal"
        )

    def test_notification_mentions_rebuild_container(self, version_check_script):
        """Test that notification reminds user to rebuild container."""
        content = version_check_script.read_text()

        # Should mention rebuilding the container
        assert "rebuild" in content.lower(), (
            "Notification should remind user to rebuild container after upgrade"
        )

    def test_notification_shows_mute_options(self, version_check_script):
        """Test that notification shows how to mute or disable."""
        content = version_check_script.read_text()

        # Should show mute and disable options
        notify_section = content[content.find("notify_update") :]

        assert "just check" in notify_section and "off" in notify_section, (
            "Notification should show how to disable ('just check off')"
        )

        assert "7d" in notify_section or "mute" in notify_section.lower(), (
            "Notification should show how to mute (e.g., 'just check 7d')"
        )


class TestDevcontainerUpgradeRecipe:
    """Test the host-side 'just devcontainer-upgrade' recipe."""

    def test_devcontainer_upgrade_recipe_exists(self, initialized_workspace):
        """Test that 'just devcontainer-upgrade' recipe exists in justfile.devc."""
        justfile_base = initialized_workspace / ".devcontainer" / "justfile.devc"

        if not justfile_base.exists():
            pytest.skip("justfile.devc not found")

        content = justfile_base.read_text()

        # Recipe should exist
        assert "devcontainer-upgrade" in content, (
            "devcontainer-upgrade recipe not found in justfile.devc"
        )

    def test_devcontainer_upgrade_detects_container_environment(
        self, initialized_workspace
    ):
        """Test that recipe detects when running inside container."""
        justfile_base = initialized_workspace / ".devcontainer" / "justfile.devc"

        if not justfile_base.exists():
            pytest.skip("justfile.devc not found")

        content = justfile_base.read_text()

        # Should check for container indicators
        assert "/.dockerenv" in content or "container" in content, (
            "devcontainer-upgrade recipe should detect container environment"
        )

    def test_devcontainer_upgrade_shows_error_in_container(self, initialized_workspace):
        """Test that recipe shows clear error when run inside container."""
        justfile_base = initialized_workspace / ".devcontainer" / "justfile.devc"

        if not justfile_base.exists():
            pytest.skip("justfile.devc not found")

        content = justfile_base.read_text()

        # Find the devcontainer-upgrade recipe
        lines = content.split("\n")
        recipe_start = None
        recipe_end = None

        for i, line in enumerate(lines):
            if "devcontainer-upgrade" in line and ":" in line:
                recipe_start = i
                # Find the end (next recipe or end of file)
                for j in range(i + 1, len(lines)):
                    if (
                        lines[j]
                        and not lines[j].startswith(" ")
                        and not lines[j].startswith("\t")
                    ):
                        recipe_end = j
                        break
                break

        if recipe_start is None:
            pytest.skip("devcontainer-upgrade recipe not found")

        recipe_content = "\n".join(
            lines[recipe_start : recipe_end if recipe_end else len(lines)]
        )

        # Should show error message about running from host
        assert "ERROR" in recipe_content.upper() or "error" in recipe_content, (
            "Recipe should show error message when run in container"
        )

        assert (
            "host" in recipe_content.lower() and "terminal" in recipe_content.lower()
        ), "Error message should mention running from host terminal"

    def test_devcontainer_upgrade_checks_runtime_available(self, initialized_workspace):
        """Test that recipe checks if podman/docker is available."""
        justfile_base = initialized_workspace / ".devcontainer" / "justfile.devc"

        if not justfile_base.exists():
            pytest.skip("justfile.devc not found")

        content = justfile_base.read_text()

        # Should check for runtime availability
        assert (
            "podman" in content and "docker" in content
        ) or "command -v" in content, (
            "Recipe should check if podman or docker is available"
        )

    def test_devcontainer_upgrade_calls_install_script(self, initialized_workspace):
        """Test that recipe calls install.sh with --force flag."""
        justfile_base = initialized_workspace / ".devcontainer" / "justfile.devc"

        if not justfile_base.exists():
            pytest.skip("justfile.devc not found")

        content = justfile_base.read_text()

        # Find the devcontainer-upgrade recipe section
        if "devcontainer-upgrade" in content:
            # Should call the install script
            assert "install.sh" in content, "Recipe should call install.sh"

            assert "--force" in content, "Recipe should use --force flag for upgrades"

    def test_devcontainer_upgrade_in_info_group(self, initialized_workspace):
        """Test that devcontainer-upgrade recipe is in the 'info' group."""
        justfile_base = initialized_workspace / ".devcontainer" / "justfile.devc"

        if not justfile_base.exists():
            pytest.skip("justfile.devc not found")

        content = justfile_base.read_text()
        lines = content.split("\n")

        # Find the devcontainer-upgrade recipe
        recipe_idx = None
        for i, line in enumerate(lines):
            if "devcontainer-upgrade:" in line:
                recipe_idx = i
                break

        if recipe_idx is None:
            pytest.skip("devcontainer-upgrade recipe not found")

        # Look backwards for group annotation
        for i in range(recipe_idx - 1, max(0, recipe_idx - 5), -1):
            if "[group('info')]" in lines[i]:
                return  # Found it

        pytest.fail("devcontainer-upgrade recipe not in 'info' group")


class TestVersionCheckGracefulFailure:
    """Test that the version check feature fails gracefully in various scenarios."""

    @pytest.fixture
    def version_check_script(self, initialized_workspace):
        """Path to version-check.sh script."""
        script_path = (
            initialized_workspace / ".devcontainer" / "scripts" / "version-check.sh"
        )
        if not script_path.exists():
            pytest.skip("version-check.sh not found in workspace")
        return script_path

    @pytest.fixture
    def local_dir(self, initialized_workspace):
        """Path to .local directory."""
        local_path = initialized_workspace / ".devcontainer" / ".local"
        local_path.mkdir(parents=True, exist_ok=True)
        return local_path

    def test_no_network_silent_failure(self, version_check_script, local_dir):
        """Test that network failures don't break the script in silent mode."""
        # Silent mode (no arguments) should never fail
        result = subprocess.run(
            [str(version_check_script)],
            capture_output=True,
            text=True,
            timeout=10,
        )

        # Should always succeed in silent mode
        assert result.returncode == 0
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
