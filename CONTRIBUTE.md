
<!-- Auto-generated from docs/templates/CONTRIBUTE.md.j2 - DO NOT EDIT DIRECTLY -->
<!-- Run 'just docs' to regenerate -->

# Contributing to vigOS Development Environment

This guide explains how to develop, build, test, and release the vigOS development container image.

## Prerequisites

This repository is **Nix-first**: the toolchain is defined by the Nix flake
(`flake.nix` — its `devTools` list is the single source of truth) and provisioned
into your shell by [direnv](https://direnv.net/) or `nix develop`. You only need
three things on the host:

| Prerequisite | Purpose |
|--------------|---------|
| **[Nix](https://nixos.org/download)** | Provides the entire dev toolchain (just, git, gh, uv, node, jq, tmux, ripgrep, claude, …) from the flake — no manual installs |
| **[direnv](https://direnv.net/)** | Loads the flake dev-shell automatically on `cd` — **once its [shell hook](https://direnv.net/docs/hook.html) is installed** (e.g. `eval "$(direnv hook bash)"` in `~/.bashrc`). Without the hook, `direnv allow` still succeeds but nothing loads on `cd` and you silently fall back to host tools. Recommended; `nix develop` works without direnv |
| **A working container runtime** (podman or Docker) | Building and testing the image needs a usable rootless runtime. The flake ships the `podman` CLI, but rootless operation depends on host setup — `subuid`/`subgid` + `uidmap` on Linux, or `podman machine` on macOS |

Everything else comes from the flake. See the fast path below to get set up.

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

   > **First time using direnv on this machine?** Install its shell hook first —
   > add `eval "$(direnv hook bash)"` (or the
   > [equivalent for your shell](https://direnv.net/docs/hook.html)) to your shell
   > rc and start a new shell. The hook is what loads/unloads the environment on
   > `cd`; without it `direnv allow` reports success but the flake never activates,
   > so you keep host tooling (e.g. an old system Node) with no warning. Prefer not
   > to install the hook? Use `nix develop` instead.

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

Clone this repository, enter the Nix dev shell, then bootstrap the project:

```bash
git clone git@github.com:vig-os/devcontainer.git
cd devcontainer
direnv allow        # (recommended) loads the flake toolchain — or run `nix develop`
just init           # Gate prerequisites and bootstrap the project (venv, git hooks, pre-commit)
```

`just init` does not install tools — it verifies the Nix prerequisites are in
place and then performs one-time project bootstrap (`uv sync`, git hooks, commit
template, pre-commit). It is safe to re-run.

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
