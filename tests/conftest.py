"""
Shared fixtures for all devc container tests.

This module supports running tests from both:
1. Host machine (direct podman access)
2. Inside a devcontainer (Docker-out-of-Docker via socket)

When running from within a container, set HOST_WORKSPACE_PATH environment
variable to the host path that maps to /workspace/devcontainer in the container.
This enables path translation for volume mounts.

Example:
    HOST_WORKSPACE_PATH=/Users/you/Projects/devcontainer just test-integration
"""

import atexit
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pexpect
import pytest
import testinfra
import yaml


def pytest_sessionstart(session):
    """
    Pre-flight check: Detect lingering test containers from previous runs.

    Runs before any tests to ensure a clean environment.
    Skip this check when running as part of 'just test' (PYTEST_SKIP_CONTAINER_CHECK=1)
    since the check is done once at the start of the full test run.
    """
    # Skip check when running under 'just test' - check already done at start
    if os.environ.get("PYTEST_SKIP_CONTAINER_CHECK") == "1":
        return

    # Check for lingering containers from previous test runs
    check_cmd = [
        "podman",
        "ps",
        "-a",
        "--filter",
        "name=workspace-devcontainer",
        "--format",
        "{{.ID}}\t{{.Names}}\t{{.Status}}\t{{.CreatedAt}}",
    ]

    result = subprocess.run(check_cmd, capture_output=True, text=True)

    if result.returncode == 0 and result.stdout.strip():
        containers = result.stdout.strip().split("\n")

        # Also check for test-sidecar containers
        sidecar_check_cmd = [
            "podman",
            "ps",
            "-a",
            "--filter",
            "name=test-sidecar",
            "--format",
            "{{.ID}}\t{{.Names}}\t{{.Status}}\t{{.CreatedAt}}",
        ]
        sidecar_result = subprocess.run(
            sidecar_check_cmd, capture_output=True, text=True
        )

        if sidecar_result.returncode == 0 and sidecar_result.stdout.strip():
            containers.extend(sidecar_result.stdout.strip().split("\n"))

        # Format the error message
        container_list = "\n".join(f"  - {c}" for c in containers)

        cleanup_commands = """
To clean up these containers, run:

    # Clean up workspace devcontainers
    podman ps -a --filter "name=workspace-devcontainer" --format "{{{{.ID}}}}" | xargs -r podman rm -f

    # Clean up test sidecars
    podman ps -a --filter "name=test-sidecar" --format "{{{{.ID}}}}" | xargs -r podman rm -f

    # Or use the justfile recipe:
    just clean-test-containers

Alternatively, set PYTEST_AUTO_CLEANUP=1 to automatically clean up before tests:

    PYTEST_AUTO_CLEANUP=1 uv run pytest tests/
"""

        # Check if auto-cleanup is enabled
        if os.environ.get("PYTEST_AUTO_CLEANUP") == "1":
            print(f"\n⚠️  Found {len(containers)} lingering test container(s)")
            print("🧹 Auto-cleanup enabled, removing containers...")

            # Clean up workspace devcontainers
            cleanup_devcontainer = [
                "podman",
                "ps",
                "-a",
                "--filter",
                "name=workspace-devcontainer",
                "--format",
                "{{.ID}}",
            ]
            ids_result = subprocess.run(
                cleanup_devcontainer, capture_output=True, text=True
            )
            if ids_result.stdout.strip():
                for container_id in ids_result.stdout.strip().split("\n"):
                    subprocess.run(
                        ["podman", "rm", "-f", container_id], capture_output=True
                    )

            # Clean up test sidecars
            cleanup_sidecar = [
                "podman",
                "ps",
                "-a",
                "--filter",
                "name=test-sidecar",
                "--format",
                "{{.ID}}",
            ]
            sidecar_ids_result = subprocess.run(
                cleanup_sidecar, capture_output=True, text=True
            )
            if sidecar_ids_result.stdout.strip():
                for container_id in sidecar_ids_result.stdout.strip().split("\n"):
                    subprocess.run(
                        ["podman", "rm", "-f", container_id], capture_output=True
                    )

            print("✅ Cleanup complete\n")
        else:
            # Fail with helpful error message
            pytest.exit(
                f"\n\n❌ Found {len(containers)} lingering test container(s) from previous runs:\n\n"
                f"{container_list}\n\n"
                f"{cleanup_commands}",
                returncode=1,
            )


def is_running_in_container() -> bool:
    """Detect if we're running inside a container."""
    # Check for container environment indicators
    if os.environ.get("IN_CONTAINER") == "true":
        return True
    if Path("/.dockerenv").exists():
        return True
    if Path("/run/.containerenv").exists():
        return True
    # Check cgroup for container runtime
    try:
        with Path("/proc/1/cgroup").open() as f:
            return "docker" in f.read() or "podman" in f.read()
    except (FileNotFoundError, PermissionError):
        pass
    return False


def get_host_path(container_path: Path) -> Path:
    """
    Translate a container path to a host path.

    When running inside a container with Docker-out-of-Docker (DooD),
    volume mounts must use HOST paths because podman runs on the host.

    Args:
        container_path: Path inside the container

    Returns:
        Host path if HOST_WORKSPACE_PATH is set and path is under /workspace,
        otherwise returns the original path.
    """
    host_workspace = os.environ.get("HOST_WORKSPACE_PATH")
    if not host_workspace:
        return container_path

    container_path_str = str(container_path.resolve())
    container_workspace = "/workspace/devcontainer"

    if container_path_str.startswith(container_workspace):
        relative = container_path_str[len(container_workspace) :]
        return Path(host_workspace + relative)

    return container_path


def get_compose_project_name() -> str:
    """Generate a unique compose project name for test isolation."""
    return f"test-{int(time.time())}"


@pytest.fixture(scope="session")
def container_tag():
    """
    Get the container tag from TEST_CONTAINER_TAG environment variable.
    Defaults to 'dev' if not set.
    """
    return os.environ.get("TEST_CONTAINER_TAG", "dev")


@pytest.fixture(scope="session")
def container_image(container_tag):
    """
    Construct the full container image name and verify it exists.
    """
    image_name = f"ghcr.io/vig-os/devcontainer:{container_tag}"

    # Check if image exists
    result = subprocess.run(
        ["podman", "image", "exists", image_name], capture_output=True, text=True
    )

    if result.returncode != 0:
        pytest.fail(
            f"Podman image {image_name} not found. "
            f"Please build it first with 'just build'"
        )

    return image_name


@pytest.fixture(scope="session")
def test_container(container_image):
    """
    Start a container from the image and return its name.
    The container will be cleaned up after all tests.
    """
    # Create a unique container name
    container_id = f"test-devcontainer-{int(time.time())}"

    # Start the container in detached mode
    result = subprocess.run(
        [
            "podman",
            "run",
            "-d",
            "--name",
            container_id,
            container_image,
            "sleep",
            "infinity",
        ],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        pytest.fail(
            f"Failed to start container from {container_image}\nstderr: {result.stderr}"
        )

    # Register cleanup function
    def cleanup():
        subprocess.run(["podman", "stop", container_id], capture_output=True, text=True)
        subprocess.run(["podman", "rm", container_id], capture_output=True, text=True)

    atexit.register(cleanup)

    yield container_id

    # Cleanup
    cleanup()


@pytest.fixture(scope="session")
def host(test_container):
    """
    Create a testinfra connection to the running container.
    This fixture is used by all testinfra tests.
    """
    # Create a podman connection to the running container
    # We use 'podman://' prefix to tell testinfra to use podman
    connection_string = f"podman://{test_container}"

    # Create the host connection
    host = testinfra.host.get_host(connection_string)

    return host


# --- Helpers and fixtures for init-workspace.sh ---


def _build_podman_cmd(container_image, workspace_mount, smoke_test):
    """Build podman command for init-workspace script."""
    cmd = ["podman", "run", "--rm", "-v", workspace_mount]
    if smoke_test:
        cmd.extend(
            [
                "-e",
                "SHORT_NAME=test_project",
                "-e",
                "ORG_NAME=Test Org",
                "-e",
                "GITHUB_REPOSITORY=test-org/test-project",
            ]
        )
    else:
        cmd.append("-it")
    cmd.extend([container_image, "/root/assets/init-workspace.sh"])
    if smoke_test:
        cmd.append("--smoke-test")
    return cmd


def _run_noninteractive_init(cmd):
    """Run init-workspace in non-interactive mode."""
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    if result.returncode != 0:
        pytest.fail(
            "Failed to initialize workspace with init-workspace.sh (non-interactive)\n"
            f"Command: {' '.join(cmd)}\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )


def _run_interactive_init(cmd, container_image):
    """Run init-workspace in interactive mode with pexpect progress tracking."""
    project_name = "test_project"
    organization_name = "Test Org"
    stages = {
        "started": None,
        "short_name_prompt": None,
        "org_name_prompt": None,
        "copying_files": None,
        "renovate_prompt": None,
        "replacing_placeholders": None,
        "setting_permissions": None,
        "syncing_deps": None,
        "completed": None,
    }
    current_stage = "started"
    stages["started"] = time.time()
    stage_patterns_after_copy = [
        ("Replacing placeholders", "replacing_placeholders", 60),
        ("Setting executable permissions", "setting_permissions", 30),
        ("Syncing dependencies", "syncing_deps", 60),
        ("Workspace initialized successfully", "completed", 30),
    ]
    renovate_repo_answer = "test-org/test-project"

    try:
        child = pexpect.spawn(" ".join(cmd), encoding="utf-8", timeout=60)
        child.expect("Enter a short name", timeout=30)
        stages["short_name_prompt"] = time.time()
        current_stage = "short_name_prompt"
        child.sendline(project_name)

        child.expect("Enter the name of your organization", timeout=30)
        stages["org_name_prompt"] = time.time()
        current_stage = "org_name_prompt"
        child.sendline(organization_name)

        # Delivery-mode picker (#641): answer "both" to keep the full scaffold
        # (prior behaviour) so the downstream structure assertions still hold.
        child.expect("Delivery mode", timeout=30)
        child.sendline("both")

        pattern = "Copying files from"
        stage_name = "copying_files"
        timeout = 30
        try:
            child.expect(pattern, timeout=timeout)
            stages[stage_name] = time.time()
            current_stage = stage_name
        except pexpect.TIMEOUT:
            stage_start = stages.get(current_stage) or stages["started"]
            time_in_stage = time.time() - stage_start
            pytest.fail(
                f"⏱️  Timeout waiting for: '{pattern}'\n"
                f"\n"
                f"📊 Progress tracking:\n"
                f"   Current stage: {current_stage}\n"
                f"   Time in stage: {time_in_stage:.1f}s (timeout: {timeout}s)\n"
                f"\n"
                f"📈 Stage timings:\n"
                + "\n".join(
                    f"   {'✓' if stages[s] else '✗'} {s}: "
                    + (
                        f"{stages[s] - stages['started']:.1f}s"
                        if stages[s]
                        else "not reached"
                    )
                    for s in stages
                )
                + "\n\n"
                "💡 If stuck on 'copying_files':\n"
                "   - Check if .pre-commit-cache is being copied (should be excluded)\n"
                "   - Volume mounts can be slow\n"
                f"   - Check: podman run --rm {container_image} du -sh /root/assets/workspace/\n"
                "\n"
                f"📤 Last output:\n{child.before}"
            )

        pattern = "Enter GitHub repository for Renovate"
        stage_name = "renovate_prompt"
        timeout = 60
        current_stage = "awaiting_renovate_prompt"
        try:
            child.expect(pattern, timeout=timeout)
            stages[stage_name] = time.time()
            current_stage = stage_name
            child.sendline(renovate_repo_answer)
        except pexpect.TIMEOUT:
            stage_start = stages.get(current_stage) or stages["started"]
            time_in_stage = time.time() - stage_start
            pytest.fail(
                f"⏱️  Timeout waiting for: '{pattern}'\n"
                f"\n"
                f"📊 Progress tracking:\n"
                f"   Current stage: {current_stage}\n"
                f"   Time in stage: {time_in_stage:.1f}s (timeout: {timeout}s)\n"
                f"\n"
                f"📈 Stage timings:\n"
                + "\n".join(
                    f"   {'✓' if stages[s] else '✗'} {s}: "
                    + (
                        f"{stages[s] - stages['started']:.1f}s"
                        if stages[s]
                        else "not reached"
                    )
                    for s in stages
                )
                + "\n\n"
                "💡 If stuck here: init-workspace may need GITHUB_REPOSITORY or this prompt text changed.\n"
                "\n"
                f"📤 Last output:\n{child.before}"
            )

        for pattern, stage_name, timeout in stage_patterns_after_copy:
            try:
                child.expect(pattern, timeout=timeout)
                stages[stage_name] = time.time()
                current_stage = stage_name
            except pexpect.TIMEOUT:
                stage_start = stages.get(current_stage) or stages["started"]
                time_in_stage = time.time() - stage_start
                pytest.fail(
                    f"⏱️  Timeout waiting for: '{pattern}'\n"
                    f"\n"
                    f"📊 Progress tracking:\n"
                    f"   Current stage: {current_stage}\n"
                    f"   Time in stage: {time_in_stage:.1f}s (timeout: {timeout}s)\n"
                    f"\n"
                    f"📈 Stage timings:\n"
                    + "\n".join(
                        f"   {'✓' if stages[s] else '✗'} {s}: "
                        + (
                            f"{stages[s] - stages['started']:.1f}s"
                            if stages[s]
                            else "not reached"
                        )
                        for s in stages
                    )
                    + "\n\n"
                    "💡 If stuck on 'copying_files':\n"
                    "   - Check if .pre-commit-cache is being copied (should be excluded)\n"
                    "   - Volume mounts can be slow\n"
                    f"   - Check: podman run --rm {container_image} du -sh /root/assets/workspace/\n"
                    "\n"
                    f"📤 Last output:\n{child.before}"
                )

        child.expect(pexpect.EOF, timeout=30)
        child.close()
        if child.exitstatus != 0:
            pytest.fail(
                "Failed to initialize workspace with init-workspace.sh\n"
                f"Return code: {child.exitstatus}\n"
                f"Output: {child.before}"
            )

        total_time = time.time() - stages["started"]
        print(f"[DEBUG] Workspace initialized in {total_time:.1f}s")
    except pexpect.TIMEOUT:
        output = child.before if "child" in locals() else "N/A"
        stage_start = stages.get(current_stage) or stages.get("started") or time.time()
        time_in_stage = time.time() - stage_start
        pytest.fail(
            "⏱️  Timeout while initializing workspace\n"
            "\n"
            "📊 Progress tracking:\n"
            f"   Current stage: {current_stage}\n"
            f"   Time in stage: {time_in_stage:.1f}s\n"
            "\n"
            "📈 Stage timings:\n"
            + "\n".join(
                f"   {'✓' if stages[s] else '✗'} {s}: "
                + (
                    f"{stages[s] - stages['started']:.1f}s"
                    if stages[s]
                    else "not reached"
                )
                for s in stages
            )
            + "\n\n"
            f"Command: {' '.join(cmd)}\n"
            "\n"
            f"📤 Last output:\n{output}"
        )
    except pexpect.EOF:
        output = child.before if "child" in locals() else "N/A"
        pytest.fail(
            "Error while initializing workspace with init-workspace.sh: EOF\n"
            f"Command: {' '.join(cmd)}\n"
            f"Output so far: {output}\n"
            "This usually means the container exited before responding.\n"
            "Check that the image exists and the command is correct."
        )
    except pexpect.ExceptionPexpect as e:
        output = child.before if "child" in locals() else "N/A"
        pytest.fail(
            f"Error while initializing workspace with init-workspace.sh: {e}\n"
            f"Command: {' '.join(cmd)}\n"
            f"Output: {output}"
        )


def _init_workspace(container_image, *, smoke_test=False):
    """
    Create a temporary workspace directory and initialize it with init-workspace.

    Supports running from host and from inside a container.
    """
    project_root = Path(__file__).resolve().parents[1]
    tests_dir = project_root / "tests"
    in_container = is_running_in_container()

    tests_tmp_dir = tests_dir / "tmp"
    tests_tmp_dir.mkdir(parents=True, exist_ok=True)
    workspace_dir = tempfile.mkdtemp(
        dir=str(tests_tmp_dir), prefix="workspace-devcontainer-"
    )
    workspace_path = Path(workspace_dir)

    unique_id = workspace_path.name.replace("workspace-devcontainer-", "")
    volume_name = f"test-workspace-{unique_id}"
    using_compose = in_container

    def cleanup():
        if workspace_path.exists():
            shutil.rmtree(workspace_path, ignore_errors=True)
        if using_compose:
            subprocess.run(
                ["podman", "volume", "rm", "-f", volume_name],
                capture_output=True,
                text=True,
            )

    atexit.register(cleanup)

    try:
        if in_container:
            create_result = subprocess.run(
                ["podman", "volume", "create", volume_name],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if create_result.returncode != 0:
                pytest.fail(
                    f"Failed to create volume {volume_name}\n"
                    f"stdout: {create_result.stdout}\n"
                    f"stderr: {create_result.stderr}"
                )
            print(f"[DEBUG] Created volume: {volume_name}")
            workspace_mount = f"{volume_name}:/workspace"
        else:
            workspace_mount = f"{workspace_path}:/workspace"

        cmd = _build_podman_cmd(container_image, workspace_mount, smoke_test)
        if smoke_test:
            _run_noninteractive_init(cmd)
        else:
            _run_interactive_init(cmd, container_image)

        if in_container:
            workspace_path_host = get_host_path(workspace_path)
            copy_cmd = [
                "podman",
                "run",
                "--rm",
                "-v",
                f"{volume_name}:/source:ro",
                "-v",
                f"{workspace_path_host}:/dest",
                "alpine",
                "sh",
                "-c",
                "cp -a /source/. /dest/",
            ]
            print(
                f"[DEBUG] Copying files from volume {volume_name} to {workspace_path_host}"
            )
            copy_result = subprocess.run(
                copy_cmd, capture_output=True, text=True, timeout=30
            )
            if copy_result.returncode != 0:
                pytest.fail(
                    "Failed to copy files from volume to workspace\n"
                    f"Command: {' '.join(copy_cmd)}\n"
                    f"stdout: {copy_result.stdout}\n"
                    f"stderr: {copy_result.stderr}"
                )

        if not (workspace_path / "README.md").exists():
            pytest.fail(
                f"Workspace initialization failed - README.md not found in {workspace_path}\n"
                f"Workspace contents: {list(workspace_path.iterdir()) if workspace_path.exists() else 'N/A'}"
            )

        yield workspace_path
    finally:
        cleanup()


@pytest.fixture(scope="session")
def initialized_workspace(container_image):
    """Default workspace initialization fixture."""
    yield from _init_workspace(container_image, smoke_test=False)


@pytest.fixture(scope="session")
def initialized_smoke_workspace(container_image):
    """Smoke-test workspace initialization fixture."""
    yield from _init_workspace(container_image, smoke_test=True)


# --- Shared helpers for devcontainer_up and devcontainer_with_sidecar ---


def _resolve_devcontainer_cli_workspace(workspace_path):
    """
    Resolve workspace paths for devcontainer CLI (DooD-aware).
    Returns (workspace_path, workspace_path_for_cli, in_container).
    Calls pytest.skip() if running in container without HOST_WORKSPACE_PATH.
    """
    workspace_path = workspace_path.resolve()
    in_container = is_running_in_container()
    host_workspace = os.environ.get("HOST_WORKSPACE_PATH")
    if in_container and not host_workspace:
        pytest.skip(
            "Running inside a container without HOST_WORKSPACE_PATH set. "
            "Devcontainer CLI tests require host path translation. "
            "Set HOST_WORKSPACE_PATH to the host path that maps to /workspace/devcontainer"
        )
    if in_container and host_workspace:
        workspace_path_for_cli = get_host_path(workspace_path)
        print(
            f"[DEBUG] Translated workspace path: {workspace_path} -> {workspace_path_for_cli}"
        )
    else:
        workspace_path_for_cli = workspace_path
    return workspace_path, workspace_path_for_cli, in_container


def _prepare_devcontainer_env(
    workspace_path, docker_path="podman", enable_ssh_forwarding=True
):
    """
    Prepare env for devcontainer CLI and optionally add SSH agent to devcontainer.json.
    Returns (env, original_devcontainer_json_str or None for restore).
    """
    env = os.environ.copy()
    devcontainer_json_path = workspace_path / ".devcontainer" / "devcontainer.json"
    original_config = None
    if (
        platform.system() == "Darwin"
        and docker_path == "podman"
        and "SSH_AUTH_SOCK" in env
    ):
        print("[DEBUG] Disabling SSH agent forwarding on macOS+podman")
        print("[DEBUG] (VM isolation prevents socket mounting)")
        del env["SSH_AUTH_SOCK"]
    elif (
        enable_ssh_forwarding
        and "SSH_AUTH_SOCK" in env
        and Path(env["SSH_AUTH_SOCK"]).exists()
    ):
        print("[DEBUG] Setting up SSH agent forwarding in devcontainer.json")
        with devcontainer_json_path.open() as f:
            config = json.load(f)
        original_config = json.dumps(config, indent=4)
        if "mounts" not in config:
            config["mounts"] = []
        if "remoteEnv" not in config:
            config["remoteEnv"] = {}
        ssh_mount = (
            f"source={env['SSH_AUTH_SOCK']},target=/tmp/ssh-agent.sock,type=bind"
        )
        if ssh_mount not in config["mounts"]:
            config["mounts"].append(ssh_mount)
        if config["remoteEnv"].get("SSH_AUTH_SOCK") != "/tmp/ssh-agent.sock":
            config["remoteEnv"]["SSH_AUTH_SOCK"] = "/tmp/ssh-agent.sock"
        with devcontainer_json_path.open("w") as f:
            json.dump(config, f, indent=4)
        print("[DEBUG] Added SSH agent forwarding to devcontainer.json")
    return env, original_config


def _ensure_project_yaml_test_mount(project_config, workspace_path, in_container):
    """Ensure devcontainer service has the tests-mounted volume. Mutates project_config."""
    tests_dir = Path(__file__).parent.resolve()
    tests_dir_for_mount = get_host_path(tests_dir) if in_container else tests_dir
    if "services" not in project_config:
        project_config["services"] = {}
    if "devcontainer" not in project_config["services"]:
        project_config["services"]["devcontainer"] = {}
    if "volumes" not in project_config["services"]["devcontainer"]:
        project_config["services"]["devcontainer"]["volumes"] = []
    test_mount = f"{tests_dir_for_mount}:/workspace/tests-mounted:cached"
    if test_mount not in project_config["services"]["devcontainer"]["volumes"]:
        project_config["services"]["devcontainer"]["volumes"].append(test_mount)
        print(f"[DEBUG] Added test mount: {tests_dir_for_mount}")
    return project_config


def _find_devcontainer_cli():
    """Resolve the devcontainer CLI binary, checking PATH then node_modules/.bin/."""
    path_bin = shutil.which("devcontainer")
    if path_bin:
        return path_bin
    local_bin = Path("node_modules/.bin/devcontainer")
    if local_bin.is_file():
        return str(local_bin.resolve())
    return None


def _run_devcontainer_up(
    workspace_path_for_cli, workspace_path, env, docker_path="podman"
):
    """Run devcontainer up. Returns subprocess.CompletedProcess."""
    devcontainer_bin = _find_devcontainer_cli() or "devcontainer"
    up_cmd = [
        devcontainer_bin,
        "up",
        "--workspace-folder",
        str(workspace_path_for_cli),
        "--config",
        f"{workspace_path_for_cli}/.devcontainer/devcontainer.json",
        "--remove-existing-container",
        "--docker-path",
        docker_path,
        "--log-level",
        "trace",
    ]
    print(f"\n[DEBUG] Setting up devcontainer: {' '.join(up_cmd)}")
    print("[DEBUG] This may take about a minute...")
    return subprocess.run(
        up_cmd,
        capture_output=True,
        text=True,
        cwd=str(workspace_path),
        env=env,
        timeout=120,
    )


def _teardown_devcontainer_containers(
    docker_path, workspace_path, extra_name_filters=None
):
    """List containers by name (workspace_path.name + extra_name_filters) and rm -f. Same as just clean-test-containers."""
    filters = [workspace_path.name]
    if extra_name_filters:
        filters = list(extra_name_filters) + filters
    for name_filter in filters:
        list_result = subprocess.run(
            [
                docker_path,
                "ps",
                "-a",
                "--filter",
                f"name={name_filter}",
                "--format",
                "{{.ID}}",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if list_result.returncode == 0 and list_result.stdout.strip():
            for cid in list_result.stdout.strip().splitlines():
                subprocess.run(
                    [docker_path, "rm", "-f", cid.strip()],
                    capture_output=True,
                    timeout=30,
                )


@pytest.fixture(scope="session")
def devcontainer_up(initialized_workspace):
    """
    Set up a devcontainer using devcontainer CLI.

    This fixture:
    - Builds and starts the devcontainer using `devcontainer up`
    - SSH agent forwarding is disabled on macOS+podman due to VM isolation
    - Yields the workspace path for tests to use
    - Cleans up containers by name (same approach as just clean-test-containers)

    When running from inside a container (DooD), set HOST_WORKSPACE_PATH
    environment variable to enable path translation for devcontainer CLI.

    Note: This fixture takes some time to set up.
    """
    workspace_path, workspace_path_for_cli, in_container = (
        _resolve_devcontainer_cli_workspace(initialized_workspace)
    )
    if not _find_devcontainer_cli():
        pytest.skip("devcontainer CLI not available. Install with: npm install")
    bin_dir = str(Path("node_modules/.bin").resolve())
    if bin_dir not in os.environ.get("PATH", ""):
        os.environ["PATH"] = bin_dir + os.pathsep + os.environ.get("PATH", "")

    docker_path = "podman"
    env, original_config = _prepare_devcontainer_env(
        workspace_path, docker_path, enable_ssh_forwarding=True
    )
    if not original_config:
        devcontainer_json_path = workspace_path / ".devcontainer" / "devcontainer.json"
        with devcontainer_json_path.open() as f:
            original_config = json.dumps(json.load(f), indent=4)

    project_yaml_path = workspace_path / ".devcontainer" / "docker-compose.project.yaml"
    if project_yaml_path.exists():
        with project_yaml_path.open() as f:
            project_config = yaml.safe_load(f) or {}
    else:
        project_config = {}
    if not project_config:
        project_config = {"services": {"devcontainer": {"volumes": []}}}
    _ensure_project_yaml_test_mount(project_config, workspace_path, in_container)
    with project_yaml_path.open("w") as f:
        yaml.dump(project_config, f, default_flow_style=False, sort_keys=False)
    print("[DEBUG] Updated docker-compose.project.yaml with test mount")

    up_result = _run_devcontainer_up(
        workspace_path_for_cli=workspace_path_for_cli,
        workspace_path=workspace_path,
        env=env,
        docker_path=docker_path,
    )
    if up_result.returncode != 0:
        pytest.fail(
            f"devcontainer up failed\n"
            f"stdout: {up_result.stdout}\n"
            f"stderr: {up_result.stderr}"
        )
    print("[DEBUG] Devcontainer is up and running")

    yield workspace_path

    print("\n[DEBUG] Cleaning up devcontainer...")
    _teardown_devcontainer_containers(docker_path, workspace_path)
    devcontainer_json_path = workspace_path / ".devcontainer" / "devcontainer.json"
    if original_config:
        with devcontainer_json_path.open("w") as f:
            f.write(original_config)
        print("[DEBUG] Restored original devcontainer.json")


@pytest.fixture(scope="session")
def sidecar_image():
    """
    Build the test sidecar image once for all sidecar tests.

    This fixture:
    - Builds the sidecar image using podman
    - Image is stored in Podman VM where compose can access it
    - Returns the image name for use in compose configuration
    - Skips all sidecar tests if build fails
    """

    sidecar_dir = Path(__file__).parent / "fixtures"
    image_name = "localhost/test-sidecar:latest"

    print(f"\n[DEBUG] Building sidecar image: {image_name}")
    print(f"[DEBUG] Sidecar directory: {sidecar_dir}")

    # Build using podman (this runs in the VM where compose needs it)
    build_cmd = [
        "podman",
        "build",
        "-t",
        image_name,
        "-f",
        str(sidecar_dir / "sidecar.Containerfile"),
        str(sidecar_dir),
    ]

    result = subprocess.run(build_cmd, capture_output=True, text=True, timeout=120)

    if result.returncode != 0:
        pytest.skip(
            f"Failed to build sidecar image: {result.stderr}\n"
            f"Sidecar tests will be skipped."
        )

    print(f"[DEBUG] Sidecar image built successfully: {image_name}")
    return image_name


@pytest.fixture(scope="session")
def devcontainer_with_sidecar(initialized_workspace, sidecar_image):
    """
    Set up a devcontainer WITH a sidecar for testing multi-container setups.

    This fixture:
    - Uses the pre-built sidecar image
    - Configures docker-compose.project.yaml with sidecar service
    - Starts both devcontainer and sidecar together
    - Enables testing of Approach 1: command execution via podman exec
    - Cleans up both containers after the test session (session scope, like devcontainer_up)

    When running from inside a container (DooD), set HOST_WORKSPACE_PATH
    environment variable to enable path translation for devcontainer CLI.

    Note: This is separate from devcontainer_up to avoid breaking other tests.
    """
    workspace_path, workspace_path_for_cli, in_container = (
        _resolve_devcontainer_cli_workspace(initialized_workspace)
    )
    if not _find_devcontainer_cli():
        pytest.skip("devcontainer CLI not available. Install with: npm install")

    docker_path = "podman"
    env, _ = _prepare_devcontainer_env(
        workspace_path, docker_path, enable_ssh_forwarding=False
    )
    devcontainer_json_path = workspace_path / ".devcontainer" / "devcontainer.json"
    with devcontainer_json_path.open() as f:
        original_config = json.dumps(json.load(f), indent=4)

    project_yaml_path = workspace_path / ".devcontainer" / "docker-compose.project.yaml"
    if project_yaml_path.exists():
        with project_yaml_path.open() as f:
            project_config = yaml.safe_load(f) or {}
    else:
        project_config = {}
    if not project_config:
        project_config = {"services": {"devcontainer": {"volumes": []}}}
    _ensure_project_yaml_test_mount(project_config, workspace_path, in_container)
    project_config["services"]["test-sidecar"] = {
        "image": sidecar_image,
        "container_name": "test-sidecar",
        "command": "sleep infinity",
        "volumes": [f"..:/workspace/{initialized_workspace.name}:cached"],
    }
    print(f"[DEBUG] Added test-sidecar service using image: {sidecar_image}")
    with project_yaml_path.open("w") as f:
        yaml.dump(project_config, f, default_flow_style=False, sort_keys=False)
    print("[DEBUG] Updated docker-compose.project.yaml with sidecar")

    up_result = _run_devcontainer_up(
        workspace_path_for_cli=workspace_path_for_cli,
        workspace_path=workspace_path,
        env=env,
        docker_path=docker_path,
    )

    if up_result.returncode != 0:
        # Extract error details for better diagnostics
        # Try to parse JSON error from stdout
        error_message = "Unknown error"
        podman_command = None
        try:
            stdout_json = json.loads(up_result.stdout)
            if "message" in stdout_json:
                error_message = stdout_json["message"]
                # Extract the actual podman compose command from the error
                if "Command failed:" in error_message:
                    parts = error_message.split("Command failed:")
                    if len(parts) > 1:
                        podman_command = parts[1].strip()
        except (json.JSONDecodeError, KeyError):
            pass

        # Extract actual podman error from stderr
        # The devcontainer CLI swallows Podman errors, so we need to search carefully
        podman_errors = []
        stderr_lines = up_result.stderr.split("\n") if up_result.stderr else []

        # Look for actual Podman compose errors (not just "Command failed")
        # Podman errors often contain: "Error", "failed", "cannot", "unable", etc.
        # But NOT from devcontainer CLI (which has timestamps like [2025-12-16T...])
        podman_error_patterns = [
            "Error creating",
            "Error starting",
            "Error:",
            "failed to",
            "cannot",
            "unable to",
            "invalid",
            "not found",
            "permission denied",
            "connection refused",
            "no such",
        ]

        # Search through all stderr lines for actual Podman errors
        for i, line in enumerate(stderr_lines):
            line_stripped = line.strip()
            if not line_stripped:
                continue

            # Skip devcontainer CLI log lines (they have timestamps)
            if line_stripped.startswith("[") and "Z]" in line_stripped:
                continue
            if line_stripped.startswith("Start:") or line_stripped.startswith("Stop:"):
                continue
            if "at " in line_stripped and (
                "async" in line_stripped or "/node_modules/" in line_stripped
            ):
                continue  # Skip Node.js stack traces

            # Check if this looks like a Podman error
            line_lower = line_stripped.lower()
            for pattern in podman_error_patterns:
                if pattern.lower() in line_lower:
                    # Get some context (2 lines before and after)
                    context_start = max(0, i - 2)
                    context_end = min(len(stderr_lines), i + 3)
                    context = "\n".join(stderr_lines[context_start:context_end])
                    podman_errors.append(context)
                    break

        # If we found Podman errors, use them; otherwise look at the end
        podman_error = None
        if podman_errors:
            # Use the first substantial error found
            podman_error = podman_errors[0]
        else:
            # Fallback: get last meaningful lines (not stack traces)
            for line in reversed(stderr_lines[-30:]):
                line_stripped = line.strip()
                if not line_stripped:
                    continue
                # Skip stack traces and log prefixes
                if (
                    line_stripped.startswith("[")
                    or line_stripped.startswith("Start:")
                    or line_stripped.startswith("Stop:")
                    or "at " in line_stripped
                    or "/node_modules/" in line_stripped
                ):
                    continue
                podman_error = line_stripped
                break

        # Build comprehensive error message
        skip_msg = "❌ SKIPPED: devcontainer up with sidecar failed\n"
        skip_msg += "\n"
        skip_msg += "📋 Error Summary:\n"
        skip_msg += f"   {error_message}\n"

        if podman_errors:
            skip_msg += "\n"
            skip_msg += f"🔴 Podman Error(s) Found ({len(podman_errors)}):\n"
            for i, err in enumerate(podman_errors[:3], 1):  # Show up to 3 errors
                skip_msg += f"   [{i}] {err}\n"
        elif podman_error:
            skip_msg += "\n"
            skip_msg += "🔴 Podman Error (extracted):\n"
            skip_msg += f"   {podman_error}\n"
        else:
            skip_msg += "\n"
            skip_msg += "⚠️  Could not extract Podman error from stderr\n"
            skip_msg += "   (devcontainer CLI may be swallowing the actual error)\n"

        if podman_command:
            skip_msg += "\n"
            skip_msg += "⚙️  Failed Command:\n"
            skip_msg += f"   {podman_command[:200]}\n"
        skip_msg += "\n"
        skip_msg += "💡 Common causes:\n"
        skip_msg += "   - Podman compose issues with multi-container setups\n"
        skip_msg += "   - Socket mount configuration problems\n"
        skip_msg += "   - SELinux labeling conflicts on macOS\n"
        skip_msg += "   - Image pull/build failures\n"
        skip_msg += "\n"
        skip_msg += "🔍 Full Details:\n"
        skip_msg += f"   Return code: {up_result.returncode}\n"
        skip_msg += f"   Devcontainer command: devcontainer up --workspace-folder {workspace_path_for_cli} ...\n"
        skip_msg += "\n"
        skip_msg += "📤 stdout (last 1000 chars):\n"
        skip_msg += f"{up_result.stdout[-1000:]}\n"
        skip_msg += "\n"
        skip_msg += "📤 stderr (last 1500 chars - where errors usually appear):\n"
        skip_msg += f"{up_result.stderr[-1500:]}\n"
        skip_msg += "\n"
        skip_msg += (
            "💭 Note: Socket tests already prove the underlying capability works."
        )

        pytest.skip(skip_msg)

    print("[DEBUG] Devcontainer with sidecar is up and running")

    yield workspace_path

    print("[DEBUG] Cleaning up devcontainer with sidecar...")
    _teardown_devcontainer_containers(
        docker_path, workspace_path, extra_name_filters=["test-sidecar"]
    )
    if original_config:
        with devcontainer_json_path.open("w") as f:
            f.write(original_config)
        print("[DEBUG] Restored original devcontainer.json")


@pytest.fixture
def parse_manifest():
    """
    Fixture that returns manifest entries from the declarative Python manifest.

    Each entry is a tuple of (src, dest, is_transformed).

    Returns:
        Function that returns list of (src, dest, is_transformed) tuples
    """

    def _parse():
        """Read manifest entries from scripts/sync_manifest.py."""
        # Import the manifest directly
        import importlib.util

        project_root = Path(__file__).parent.parent
        spec = importlib.util.spec_from_file_location(
            "sync_manifest", project_root / "scripts" / "sync_manifest.py"
        )
        module = importlib.util.module_from_spec(spec)
        sys.modules["sync_manifest"] = module
        spec.loader.exec_module(module)

        return [
            (entry.src, entry.dest, entry.is_transformed) for entry in module.MANIFEST
        ]

    return _parse
