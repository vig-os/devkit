<!-- Auto-generated from docs/templates/TESTING.md.j2 - DO NOT EDIT DIRECTLY -->
<!-- Run 'just docs' to regenerate -->

# Testing

This document describes the testing strategy and structure for this project.

## Test Strategy

We use a layered testing approach:

1. **Image Tests**: Verify the container image itself (installed tools, versions, environment variables, file structure)
2. **Integration Tests**: Verify that the container works correctly as a devcontainer (template initialization, configuration files, scripts, VS Code integration)
3. **Utility / Script Tests**: Unit and integration tests for repo scripts and utilities (e.g. install script, version check, build helpers)

The tests are organized as:

```text
tests/
├── conftest.py              # Shared fixtures for all tests
├── test_image.py            # Container image verification tests
├── test_integration.py      # Devcontainer integration tests
├── test_release_cycle.py    # Release cycle script tests (changelog, release)
└── test_utils.py            # Utility and install script tests
```

### Image Tests

These tests run against a running container instance to verify the image itself
(installed tools, versions, environment variables, file structure).

- `TestSystemTools` - git, curl, openssh-client, gh, just
- `TestPythonEnvironment` - Python 3.14, uv
- `TestDevelopmentTools` - pre-commit, ruff, just
- `TestEnvironmentVariables` - environment variables
- `TestFileStructure` - file structure

### Integration Tests

These tests run against an initialized workspace to verify that the container works correctly as a devcontainer
(template initialization, configuration files, scripts, VS Code integration, devcontainer deployment)

- `TestHostGitSignatureSetup` - git commit signing prerequisites on host
- `TestDevContainerStructure` - directory structure
- `TestDevContainerJson` - devcontainer.json validation
- `TestDevContainerScripts` - script existence/executability
- `TestDevContainerPlaceholders` - placeholder replacement
- `TestDevContainerGit` - git hooks/config
- `TestDevContainerUserConf` - user configuration files
- `TestDevContainerCLI` - devcontainer deployment and functionality

### Test fixtures

Image and integration fixtures:

- `container_tag`: Container tag from `TEST_CONTAINER_TAG` environment variable (defaults to "dev")
- `container_image`: Full image name (e.g. `ghcr.io/vig-os/devcontainer:dev`)
- `test_container`: Running container instance for testing (session-scoped)
- `host`: Testinfra host connection to the container (session-scoped)
- `initialized_workspace`: Temporary workspace initialized with `init-workspace` script (session-scoped)
- `devcontainer_up`: Devcontainer set up using devcontainer CLI, ready for testing (session-scoped)

**Note**: Session-scoped fixtures (e.g. `devcontainer_up`) are set up once per test session and reused. This is important for fixtures that take time to set up (e.g. `devcontainer_up` takes about a minute). Fixtures automatically clean up after all tests complete.

## Running Tests

Tests are run using just recipes. The `test` recipe runs all test suites (image, integration, utils, version-check, install script):

```bash
# Run all test suites
just test

# Run tests for a specific image version (must be locally available)
just test version=1.0.0
```

### Individual Test Suites

```bash
# Run only image tests (builds dev image if needed)
just test-image

# Run only integration tests (builds dev image if needed)
just test-integration

# Run only utility/script tests (no container required for test_utils)
just test-utils
just test-version-check

# Run specific suite for a locally available version
just test-image version=1.0.0
just test-integration version=1.0.0
```

### Notes

- `test-image` and `test-integration` ensure the dev image exists (built if needed when `version=dev`); they do not auto-update it
- `TEST_CONTAINER_TAG` is set from the `version` parameter (default `"dev"`)
- Tests use pytest with verbose output (`-v`) and short tracebacks (`--tb=short`)
- See [tests/CLEANUP.md](tests/CLEANUP.md) for lingering container cleanup and `just clean-test-containers`
