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

**Delivery mode.** A workspace can run on a VS Code **devcontainer**, on a Nix
flake + **direnv**, or **both**. Pass `--mode devcontainer|direnv|both` to choose
(both forms `--mode X` and `--mode=X` work). The one-line install runs
non-interactively and defaults to `both`; run `init-workspace.sh` directly (see
Manual Setup) without `--mode` to be prompted, where the default selection is
also `both`. `devcontainer` scaffolds `.devcontainer/` only; `direnv` scaffolds
`flake.nix` + `.envrc` only; `both` scaffolds everything.

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

# Choose the delivery mode: devcontainer | direnv | both (default: both)
curl -sSf https://raw.githubusercontent.com/vig-os/devcontainer/main/install.sh | bash -s -- --mode direnv ~/my-project

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

   Run interactively (no `-it` dropped), the script prompts for the delivery mode
   (`devcontainer`/`direnv`/`both`, default `both`). Pass `--mode <value>` to skip
   the prompt; under `--no-prompts` (e.g. the one-line install) it defaults to
   `both`.

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
Available recipes:
    [build]
    build no_cache=""                          # Build local development image
    clean version="dev"                        # Remove image (default: dev)
    clean-test-containers                      # Clean up lingering test containers

    [git]
    gh-branch                                  # Show current branch + list recent branches
    gh-log                                     # Pretty one-line git log (last 20 commits)

    [github]
    gh-issues                                  # List open issues and PRs grouped by milestone [alias: gh-i]

    [info]
    default                                    # Show available commands (default)
    docs                                       # Generate documentation from templates
    help                                       # Show available commands
    info                                       # Show image information
    init *args                                 # Gate Nix prerequisites and bootstrap the project (venv, git hooks, pre-commit)
    login                                      # Test login to GHCR
    sync-workspace                             # Sync workspace templates from repo root to assets/workspace/

    [podman]
    podman-kill name                           # Stop and remove a container by name or ID [alias: pdm-kill]
    podman-kill-all                            # Stop and remove all containers (with confirmation) [alias: pdm-kill-all]
    podman-kill-project                        # Stop and remove project-related containers [alias: pdm-kill-project]
    podman-prune                               # Prune unused containers, images, networks, and volumes [alias: pdm-prune]
    podman-prune-all                           # Full cleanup: prune including volumes [alias: pdm-prune-all]
    podman-ps *args                            # List containers/images (--all for all podman resources) [alias: pdm-ps]
    podman-rmi image                           # Remove an image by name, tag, or ID [alias: pdm-rmi]
    podman-rmi-all                             # Remove all images (with confirmation) [alias: pdm-rmi-all]
    podman-rmi-dangling                        # Remove dangling images (untagged) [alias: pdm-rmi-dangling]
    podman-rmi-project                         # Remove project-related images [alias: pdm-rmi-project]

    [quality]
    format                                     # Format code
    lint                                       # Run all linters
    precommit                                  # Run pre-commit hooks on all files

    [release]
    finalize-release version ref="" *flags     # Finalize and publish release via GitHub Actions workflow (step 3, after testing)
    prepare-release version ref="" *flags      # Prepare release branch for testing (step 1)
    promote-release version ref="" *flags      # Promote final release: GHCR :latest, publish draft GitHub Release, merge release PR (after downstream smoke-test final release)
    publish-candidate version ref="" *flags    # Publish release candidate via GitHub Actions workflow
    pull version="latest"                      # Pull image from registry (default: latest)
    reset-changelog                            # Reset CHANGELOG Unreleased section (after merging release to dev)

    [test]
    test version="dev"                         # Run all test suites
    test-bats                                  # Run BATS shell script tests
    test-image version="dev"                   # Run image tests only
    test-install                               # Run install script tests only
    test-integration version="dev"             # Run integration tests only
    test-renovate                              # Validate tracked Renovate configs with renovate-config-validator --strict
    test-utils                                 # Run utils tests only
    test-validate-commit-msg                   # Run validate commit msg tests only
    test-vig-utils                             # Run check action pins tests only

    [worktree]
    worktree-attach issue                      # before attaching. See tests/bats/worktree.bats for integration tests. [alias: wt-attach]
    worktree-clean mode=""                     # Default (no args): clean only stopped worktrees. Use 'all' to clean everything. [alias: wt-clean]
    worktree-list                              # List active worktrees and their tmux sessions [alias: wt-list]
    worktree-start issue prompt="" reviewer="" # Create a worktree for an issue, open tmux session, launch the claude CLI [alias: wt-start]
    worktree-stop issue                        # Stop a worktree's tmux session and remove the worktree [alias: wt-stop]

```

For detailed command descriptions, run `just --list --unsorted` or `just --help`.

## Image Details

- **Build**: Nix flake via `dockerTools.buildLayeredImage` (no Debian/Docker base image); bit-reproducible
- **Registry**: `ghcr.io/vig-os/devcontainer`
- **Architecture**: Multi-platform support (AMD64, ARM64)
- **License**: Apache
- **Latest Version**: [0.4.0](https://github.com/vig-os/devcontainer/releases/tag/0.4.0) - 2026-07-06
- **Image tags**: bare semver (`0.2.1`, `latest`) — git tags use `v` prefix (`v0.2.1`) but image tags do not

## Features

### **Build**

- **Nix flake** – The image is assembled entirely by Nix via `dockerTools.buildLayeredImage` (no Debian/Docker base image). Python (CPython 3.14) and the whole toolchain come from a pinned `nixpkgs`, so the build is bit-reproducible

### **System Tools**

- **curl** – HTTP client for API testing and downloads
- **git** – Version control system
- **gh** – GitHub CLI for interacting with GitHub from the command line and pre-commits
- **openssh-client** – SSH client for secure Git operations and remote access
- **ca-certificates** – SSL/TLS certificate support for secure connections
- **locales** – UTF-8 locale support for internationalization
- **cargo-binstall** - Install Rust binary crates without full Rust toolchain

### **Python Environment**

- **Python 3.14** - CPython from the pinned `nixpkgs`
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
