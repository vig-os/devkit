
<!-- Auto-generated from docs/templates/CONTRIBUTE.md.j2 - DO NOT EDIT DIRECTLY -->
<!-- Run 'just docs' to regenerate -->

# Contributing to vigOS Development Environment

This guide explains how to develop, build, test, and release the vigOS development container image.

## Requirements

| Component            | Version | Purpose |
|----------------------|---------|---------|
| **podman** | >=4.0 | Container runtime, compose, and image building |
| **just** | >=1.40.0 | Command runner for task automation |
| **git** | >=2.34 | Version control and pre-commit hooks |
| **ssh** | latest | GitHub authentication and commit signing |
| **gh** | latest | GitHub CLI for repository and PR/issue management |
| **jq** | latest | JSON parsing for worktree commands and issue metadata |
| **tmux** | latest | Session manager required by worktree-start and worktree-attach |
| **claude** | latest | Claude Code CLI required by worktree-start/worktree-attach flows |
| **npm** | latest | Node.js package manager (for DevContainer CLI) |
| **uv** | >=0.8 | Python package and project manager |
| **bats** | 1.13.0 | Bash Automated Testing System for shell script tests |
| **devcontainer** | 0.81.1 | DevContainer CLI for testing devcontainer functionality |
| **taplo** | latest | TOML formatter and linter used by pre-commit |
| **parallel** | latest | Parallelizes BATS test execution for faster test runs |

**Ubuntu/Debian:**

```bash
sudo apt update
sudo apt install -y podman git openssh-client jq tmux nodejs npm parallel
# just
curl --proto '=https' --tlsv1.2 -sSf https://just.systems/install.sh | sudo bash -s -- --to /usr/local/bin

# gh
curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | sudo dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null
sudo apt update && sudo apt install -y gh

# taplo
case "$(dpkg --print-architecture)" in
  amd64) ARCH="x86_64" ;;
  arm64) ARCH="aarch64" ;;
  *)
    echo "Unsupported architecture: $(dpkg --print-architecture)"
    exit 1
    ;;
esac
BASE_URL="https://github.com/tamasfe/taplo/releases/latest/download"
BIN_FILE="taplo-linux-${ARCH}.gz"
curl -fsSL "${BASE_URL}/${BIN_FILE}" -o "${BIN_FILE}"
gunzip "${BIN_FILE}"
sudo install -m 0755 "taplo-linux-${ARCH}" /usr/local/bin/taplo
rm -f "taplo-linux-${ARCH}"

```

**macOS (Homebrew):**

```bash
brew install podman just git openssh gh jq tmux node taplo parallel
```

- For other Linux distributions, use your package manager (e.g., `dnf`, `yum`, `zypper`, `apk`) to install these dependencies.
- Run `./scripts/init.sh` to check dependencies and get OS-specific installation commands.
- Ensure Docker is installed if you plan to use it instead of Podman.

## Nix dev shell (fast path)

The repository ships a Nix flake (`flake.nix`) whose `devTools` list is the single
source of truth for the toolchain. With [Nix](https://nixos.org/download) and
[direnv](https://direnv.net/) installed you get the full dev environment on
`cd` into the clone — no manual dependency install. On a warm
[Cachix](https://www.cachix.org/) cache this is a binary fetch, not a from-source
build, so the first `direnv allow` completes in seconds.

1. **Enable the flakes experimental features.** Add to `~/.config/nix/nix.conf`
   (or `/etc/nix/nix.conf`):

   ```conf
   experimental-features = nix-command flakes
   ```

2. **Add the `vig-os` Cachix substituter** so the dev-shell closure is fetched
   from the binary cache instead of built locally. Add to the same `nix.conf`:

   ```conf
   substituters = https://cache.nixos.org https://vig-os.cachix.org
   trusted-public-keys = cache.nixos.org-1:6NCHdD59X431o0gWypbMrAURkbJ16ZPMQFGspcDShjY= vig-os.cachix.org-1:yoOYRi3bvnM6ThxO0joLt7vtzhTfkq3r6jykeUMg7Bk=
   ```

   Pulling from the public `vig-os` cache needs no token. (If you have the Cachix
   CLI: `cachix use vig-os` writes the same lines for you.)

3. **Clone and allow direnv:**

   ```bash
   git clone git@github.com:vig-os/devcontainer.git
   cd devcontainer
   direnv allow        # first allow fetches the closure from Cachix (seconds on a warm cache)
   ```

   The committed `.envrc` uses
   [nix-direnv](https://github.com/nix-community/nix-direnv): the dev-shell
   evaluation is cached and GC-rooted (under `.direnv/`, which is gitignored), so
   re-entering the directory is instant and the closure is never garbage-collected.
   nix-direnv is self-bootstrapped by `.envrc` on first allow; if you already
   source it from `~/.config/direnv/direnvrc`, that installation is used instead.

This Nix dev shell is an alternative to the devcontainer image below; use whichever
fits your workflow. Downstream workspaces scaffolded by `install.sh` choose between
the two (or both) via the delivery mode: `--mode devcontainer|direnv|both`
(default `both`; the interactive `init-workspace.sh` prompts, defaulting to
`both`). `devcontainer` scaffolds `.devcontainer/` only, `direnv` scaffolds
`flake.nix` + `.envrc` only, and `both` scaffolds everything.

## Setup

Clone this repository and prepare it for container development:

```bash
git clone git@github.com:vig-os/devcontainer.git
cd devcontainer
just init           # Install dependencies and setup development environment
```

## Development Workflow

When contributing to this project, follow this workflow:

1. **Create an issue** to report a bug or request a feature
   - Use [GitHub Issues](https://github.com/vig-os/devcontainer/issues) to document the problem or feature request
   - This helps track work and provides context for reviewers

2. **Create a branch from `dev` branch**

   ```bash
   git checkout dev
   git pull origin dev
   git checkout -b feature/your-feature-name
   # or
   git checkout -b fix/your-bug-fix
   ```

3. **Work on the issue or feature**
   - Make your changes
   - Commit often and descriptively
   - Add tests
   - Build and test locally: `just build && just test`
   - Ensure your code follows the project's style and conventions

4. **Update documentation if necessary**
   - Update templates in `docs/templates/` (not the generated files directly)
   - Run `just docs` to regenerate documentation
   - Update the [CHANGELOG](CHANGELOG.md) with your changes in the `[Unreleased]` section
     - Add entries under appropriate categories (Added, Changed, Fixed, etc.)
     - Use clear, concise descriptions
     - Reference related [issues](https://github.com/vig-os/devcontainer/issues) and [PRs](https://github.com/vig-os/devcontainer/pulls) when applicable
   - Keep documentation in sync with code changes

5. **Verify tests pass**

   ```bash
   # Run all test suites (image, integration, utils, version-check, install script)
   just test

   # Or run individual test suites
   just test-image
   just test-integration
   just test-utils
   just test-version-check
   just test-sidecar
   ```

6. **Create a pull request**
   - Create a [pull request](https://github.com/vig-os/devcontainer/pulls) targeting the `dev` branch
   - Link the PR to the related [issue(s)](https://github.com/vig-os/devcontainer/issues)
   - Provide a clear description of your changes

7. **Accepted contributions will be merged into `dev` branch**
   - Maintainers will review your PR
   - Address any feedback or requested changes
   - Once approved, your changes will be merged into `dev`

## Just Recipes

```text
Available recipes:
    [build]
    build no_cache=""                          # Build local development image
    clean version="dev"                        # Remove image (default: dev)
    clean-test-containers                      # Clean up lingering test containers

    [git]
    branch                                     # Show current branch + list recent branches
    log                                        # Pretty one-line git log (last 20 commits)

    [github]
    gh-issues                                  # List open issues and PRs grouped by milestone [alias: gh-i]

    [info]
    default                                    # Show available commands (default)
    docs                                       # Generate documentation from templates
    help                                       # Show available commands
    info                                       # Show image information
    init *args                                 # Install system dependencies and setup development environment
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

## Release Workflow

Releases are managed through automated GitHub Actions workflows. For the full
reference, see [docs/RELEASE_CYCLE.md](docs/RELEASE_CYCLE.md).

### Quick Reference

1. **Ensure all features are merged to `dev`** and tests are passing

   ```bash
   git checkout dev
   git pull origin dev
   just test
   ```

2. **Prepare the release** (creates release branch, prepares CHANGELOG, opens draft PR)

   ```bash
   just prepare-release X.Y.Z
   ```

3. **Review and test the release**
   - Monitor CI on the draft PR
   - Fix any issues via bugfix PRs to `release/X.Y.Z`
   - Mark PR as ready for review and get approval

4. **Finalize and publish** (validates, finalizes CHANGELOG, builds, tests, signs, and publishes)

   ```bash
   just finalize-release X.Y.Z
   ```

   The workflow will:
   - Validate CI status and PR approval
   - Set the release date in CHANGELOG
   - Build and test multi-arch images (amd64, arm64)
   - Scan for vulnerabilities with Trivy
   - Push to GHCR with `:latest` and `:X.Y.Z` tags
   - Sign images with Sigstore cosign
   - Generate SBOM and attest provenance
   - Automatically roll back on failure

5. **Merge the release PR into `main`**
   - The `sync-main-to-dev` workflow automatically opens a PR to merge `main` into `dev`

## Version Tagging

vigOS Development Environment uses **Semantic Versioning** ([SemVer](https://semver.org/)) to manage both GHCR tags and git tags:

- **Development versions** (`dev`):
  - Only local, without time stamp or git reference
  - Meant for development and testing only
  - Use `just build` and `just test` to build and test

- **Stable versions** (e.g., `1.2.0`, `2.0.0`):
  - Follow Semantic Versioning format: `MAJOR.MINOR.PATCH` (e.g., `1.0.0`, `1.2.3`, `2.0.0`)
  - Pushes to GHCR with both `:latest` and `:version` tags
  - Creates git tag `{version}` (e.g., `1.2.0`)
  - Use `just push X.Y.Z` where X.Y.Z is the semantic version

This ensures that `:latest` always points to the latest stable release, and git tags provide traceability for all stable container versions.

## Multi-Architecture Support

vigOS Development Environment supports both **AMD64** (x86_64) and **ARM64** (Apple Silicon) architectures:

- **Local builds** (`just build` and `just test`): Build and test for your native platform (ARM64 on macOS, AMD64 on Linux)
- **Releases** (GitHub Actions on version tags): The publish workflow builds and pushes multi-arch manifests (amd64, arm64) to GHCR
- **Pull from registry** (`just pull`): Pull the correct architecture for your platform from GHCR

This allows development on any supported platform and consistent multi-arch images for releases.

## Testing

vigOS Development Environment relies on comprehensive tests to verify both container images and devcontainer functionality.
For detailed information about the testing strategy, test structure, and how to develop tests, see the [Testing Guide](TESTING.md).
