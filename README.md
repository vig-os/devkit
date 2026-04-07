<!-- Auto-generated from docs/templates/README.md.j2 - DO NOT EDIT DIRECTLY -->
<!-- Run 'just docs' to regenerate -->

# vigOS Development Environment

This repository provides a standardized development container image.
It serves as a minimal, consistent development environment with essential
tools and configurations for containerized development workflows.

## Requirements

To use this devcontainer image, you need:

- **VS Code** - Visual Studio Code editor
- **Dev Containers extension** - VS Code extension for working with development containers
- **Podman** or **Docker** - Container runtime to run the container image

That's it! All development tools (Python, git, pre-commit, just, etc.) are included in the container image itself.

## Quick Start

### One-Line Install

```bash
curl -sSf https://raw.githubusercontent.com/vig-os/devcontainer/main/install.sh | bash -s -- ~/my-project
```

This will:
- Auto-detect podman or docker
- Pull the latest devcontainer image
- Initialize your project with the devcontainer template

**Options:**

```bash
# Use specific version
curl -sSf https://raw.githubusercontent.com/vig-os/devcontainer/main/install.sh | bash -s -- --version 0.2.1 ~/my-project

# Upgrade existing project (overwrites template files)
curl -sSf https://raw.githubusercontent.com/vig-os/devcontainer/main/install.sh | bash -s -- --force ~/my-project

# Override project name
curl -sSf https://raw.githubusercontent.com/vig-os/devcontainer/main/install.sh | bash -s -- --name my_custom_name ~/my-project

# Override organization name (default: vigOS)
curl -sSf https://raw.githubusercontent.com/vig-os/devcontainer/main/install.sh | bash -s -- --org MyOrg ~/my-project

# Preview without executing
curl -sSf https://raw.githubusercontent.com/vig-os/devcontainer/main/install.sh | bash -s -- --dry-run ~/my-project

# Force specific runtime
curl -sSf https://raw.githubusercontent.com/vig-os/devcontainer/main/install.sh | bash -s -- --docker ~/my-project
curl -sSf https://raw.githubusercontent.com/vig-os/devcontainer/main/install.sh | bash -s -- --podman ~/my-project
```

> **Note:** If podman or docker is not installed, the script provides OS-specific installation instructions for macOS, Ubuntu/Debian, Fedora, Arch Linux, and Windows.

### Manual Setup

<details>
<summary>Click to expand manual installation steps</summary>

1. **Pull the latest image**

   ```bash
   podman pull ghcr.io/vig-os/devcontainer:latest
   # or
   docker pull ghcr.io/vig-os/devcontainer:latest
   ```

   To pull a specific version, use the bare semver tag (without `v` prefix):

   ```bash
   podman pull ghcr.io/vig-os/devcontainer:0.2.1
   ```

2. **Initialize a workspace inside `PATH_TO_PROJECT`**

   ```bash
   podman run -it --rm -v "PATH_TO_PROJECT:/workspace" \
     ghcr.io/vig-os/devcontainer:latest /root/assets/init-workspace.sh
   # or with Docker:
   docker run -it --rm -v "PATH_TO_PROJECT:/workspace" \
     ghcr.io/vig-os/devcontainer:latest /root/assets/init-workspace.sh
   ```

   The script copies the devcontainer template (`.devcontainer/`), git hooks, README/CHANGELOG, and auth helpers into your project.

3. **Run with `--force` when overwriting or updating an existing project**

   ```bash
   podman run -it --rm -v "PATH_TO_PROJECT:/workspace" \
     ghcr.io/vig-os/devcontainer:latest /root/assets/init-workspace.sh --force
   ```

   You will be prompted to confirm before files are replaced.
   **Preserved files**: `docker-compose.project.yaml` and `docker-compose.local.yaml`
   are never overwritten, keeping your customizations intact.

   It is advised to commit all your changes before so that it can be easily reverted.

</details>

### Open in VS Code

After installation, open the project in VS Code. It will detect `.devcontainer/devcontainer.json` and offer to reopen inside the container automatically.

## Available Commands

```text
<!-- Run 'just --list' to see available recipes -->
```

For detailed command descriptions, run `just --list --unsorted` or `just --help`.

## Image Details

- **Base Image**: `python:3.12-slim-trixie`
- **Registry**: `ghcr.io/vig-os/devcontainer`
- **Architecture**: Multi-platform support (AMD64, ARM64)
- **License**: Apache
- **Latest Version**: [0.3.2](https://github.com/vig-os/devcontainer/releases/tag/0.3.2) - 2026-04-07
- **Image tags**: bare semver (`0.2.1`, `latest`) — git tags use `v` prefix (`v0.2.1`) but image tags do not

## Features

### **Base Image**

- **python:3.12-slim-trixie** – Minimal Python base image (Debian Trixie) for lightweight and robust foundation

### **System Tools**

- **curl** – HTTP client for API testing and downloads
- **git** – Version control system
- **gh** – GitHub CLI for interacting with GitHub from the command line and pre-commits
- **openssh-client** – SSH client for secure Git operations and remote access
- **ca-certificates** – SSL/TLS certificate support for secure connections
- **locales** – UTF-8 locale support for internationalization
- **cargo-binstall** - Install Rust binary crates without full Rust toolchain

### **Python Environment**

- **Python 3.12** - Latest stable Python version
- **pip, setuptools, wheel** - Python packaging tools (included with base image)
- **uv** - Fast Python package installer and resolver

### **Development Tools**

- **pre-commit** - Git hook framework for code quality
- **ruff** - Fast Python linter and formatter (replaces Black, isort, flake8, and more)
- **typstyle** - Typo and style checks (e.g. in docs and prose)
- **just** - Command runner for task automation
- **precommit alias** - Shortcut command for running pre-commit hooks

## Contributing

If you want to contribute to the development of this devcontainer image, see [CONTRIBUTE.md](CONTRIBUTE.md) for information about:

- Requirements and setup
- Building and testing the image
- Version tagging and release process
- Multi-architecture support
- Testing strategies

## License

This project is licensed under the Apache License. See the [LICENSE](LICENSE) file for details.
