#!/usr/bin/env bash
# vigOS devcontainer quick install script
#
# Usage:
#   curl -sSfL https://raw.githubusercontent.com/vig-os/devkit/main/install.sh | bash
#   curl -sSfL https://raw.githubusercontent.com/vig-os/devkit/main/install.sh | bash -s -- [OPTIONS] [PATH]
#
# Options:
#   --force           Overwrite existing files (for upgrades)
#   --version VER     Use specific version (default: latest)
#   --docker          Force docker (default: auto-detect, prefers podman)
#   --podman          Force podman
#   --name NAME       Override project name (SHORT_NAME)
#   --org ORG         Override organization name (default: vigOS)
#   --repo OWNER/REPO GitHub repo for Renovate preset (default: detect from origin or OWNER/REPO)
#   --mode MODE       Delivery mode: devcontainer | direnv | both | bare (default: .vig-os manifest, prompt, or both)
#   --smoke-test      Deploy smoke-test-specific assets
#   --preview         Print the add/overwrite/preserve/delete file report for an
#                     upgrade and exit without changing anything
#   --skip-preflight  Bypass the upgrade preflight guard (branch + clean-tree checks)
#   --dry-run         Show the container command that would run without executing
#   -h, --help        Show this help message
#
# Examples:
#   curl -sSfL https://raw.githubusercontent.com/vig-os/devkit/main/install.sh | bash
#   curl -sSfL ... | bash -s -- ~/Projects/my-project
#   curl -sSfL ... | bash -s -- --version 0.2.1 --force ./my-project
#   curl -sSfL ... | bash -s -- --org MyOrg ./my-project

set -euo pipefail

# Configuration
REGISTRY="ghcr.io/vig-os/devcontainer"
VERSION="latest"
RUNTIME=""
FORCE=""
DRY_RUN=false
SKIP_PULL=false
PROJECT_PATH=""
PROJECT_NAME=""
# Resolved after arg parsing: --org > .vig-os DEVKIT_ORG > "vigOS" (#885)
ORG_NAME=""
GITHUB_REPO_OVERRIDE=""
MODE=""
SMOKE_TEST=""
PREVIEW=""
SKIP_PREFLIGHT=false

# Colors (disabled if not a tty)
if [ -t 1 ]; then
    RED='\033[0;31m'
    GREEN='\033[0;32m'
    YELLOW='\033[1;33m'
    BLUE='\033[0;34m'
    NC='\033[0m'
else
    RED='' GREEN='' YELLOW='' BLUE='' NC=''
fi

err() { echo -e "${RED}error${NC}: $1" >&2; }
info() { echo -e "${BLUE}info${NC}: $1"; }
warn() { echo -e "${YELLOW}warn${NC}: $1"; }
success() { echo -e "${GREEN}success${NC}: $1"; }

usage() {
    cat <<'EOF'
vigOS Devcontainer Install Script

USAGE:
    curl -sSfL https://raw.githubusercontent.com/vig-os/devkit/main/install.sh | bash
    curl -sSfL ... | bash -s -- [OPTIONS] [PATH]

OPTIONS:
    --force           Overwrite existing files (for upgrades)
    --version VER     Use specific version (default: latest)
    --docker          Force docker runtime
    --podman          Force podman runtime
    --name NAME       Override project name (SHORT_NAME, used for module name)
    --org ORG         Override organization name (default: vigOS)
    --repo OWNER/REPO GitHub repository for Renovate (default: git origin or OWNER/REPO)
    --mode MODE       Delivery mode: devcontainer | direnv | both | bare
                      (default: DEVKIT_MODE from the target's .vig-os manifest,
                      else prompt interactively / "both" non-interactively)
    --smoke-test      Deploy smoke-test-specific assets
    --preview         Preview an upgrade: print the add/overwrite/preserve/delete
                      file report and exit without changing any files
    --skip-preflight  Bypass the upgrade preflight guard (--force refuses on
                      main/dev/release/*/detached HEAD and on a dirty tree)
    --dry-run         Show the container command that would run (unlike
                      --preview, no file report is computed)
    -h, --help        Show this help

EXAMPLES:
    # Initialize current directory with latest version
    curl -sSfL https://raw.githubusercontent.com/vig-os/devkit/main/install.sh | bash

    # Initialize specific directory
    curl -sSfL ... | bash -s -- ~/Projects/my-new-project

    # Upgrade existing project
    curl -sSfL ... | bash -s -- --force ./my-project

    # Use specific version
    curl -sSfL ... | bash -s -- --version 0.2.1 ./my-project

    # Override project name
    curl -sSfL ... | bash -s -- --name my_custom_name ./my-project

    # Use custom organization name
    curl -sSfL ... | bash -s -- --org MyOrg ./my-project

    # Scaffold only the Nix/direnv stub (no .devcontainer/)
    curl -sSfL ... | bash -s -- --mode direnv ./my-project
EOF
}

detect_os() {
    case "$(uname -s)" in
        Darwin*)  echo "macos" ;;
        Linux*)
            if [ -f /etc/os-release ]; then
                # shellcheck source=/dev/null
                . /etc/os-release
                case "$ID" in
                    ubuntu|debian|pop|linuxmint) echo "debian" ;;
                    fedora|rhel|centos|rocky|almalinux) echo "fedora" ;;
                    arch|manjaro|endeavouros) echo "arch" ;;
                    opensuse*|sles) echo "suse" ;;
                    *) echo "linux" ;;
                esac
            else
                echo "linux"
            fi
            ;;
        MINGW*|MSYS*|CYGWIN*) echo "windows" ;;
        *) echo "unknown" ;;
    esac
}

detect_runtime() {
    if [ -n "$RUNTIME" ]; then
        echo "$RUNTIME"
        return
    fi

    if command -v podman &> /dev/null; then
        echo "podman"
    elif command -v docker &> /dev/null; then
        echo "docker"
    else
        echo ""
    fi
}

show_install_instructions() {
    local os="$1"

    echo ""
    echo "Please install podman (recommended) or docker:"
    echo ""

    case "$os" in
        macos)
            echo "  ${BLUE}macOS (Homebrew):${NC}"
            echo "    brew install podman"
            echo "    podman machine init"
            echo "    podman machine start"
            echo ""
            echo "  ${BLUE}macOS (Docker Desktop):${NC}"
            echo "    Download from: https://docker.com/products/docker-desktop"
            ;;
        debian)
            echo "  ${BLUE}Ubuntu/Debian:${NC}"
            echo "    sudo apt update"
            echo "    sudo apt install -y podman"
            echo ""
            echo "  ${BLUE}Or Docker:${NC}"
            echo "    curl -fsSL https://get.docker.com | sh"
            echo "    sudo usermod -aG docker \$USER"
            echo "    # Log out and back in for group changes"
            ;;
        fedora)
            echo "  ${BLUE}Fedora/RHEL/CentOS:${NC}"
            echo "    sudo dnf install -y podman"
            echo ""
            echo "  ${BLUE}Or Docker:${NC}"
            echo "    sudo dnf install -y docker-ce docker-ce-cli containerd.io"
            echo "    sudo systemctl enable --now docker"
            echo "    sudo usermod -aG docker \$USER"
            ;;
        arch)
            echo "  ${BLUE}Arch Linux:${NC}"
            echo "    sudo pacman -S podman"
            echo ""
            echo "  ${BLUE}Or Docker:${NC}"
            echo "    sudo pacman -S docker"
            echo "    sudo systemctl enable --now docker"
            echo "    sudo usermod -aG docker \$USER"
            ;;
        suse)
            echo "  ${BLUE}openSUSE/SLES:${NC}"
            echo "    sudo zypper install podman"
            echo ""
            echo "  ${BLUE}Or Docker:${NC}"
            echo "    sudo zypper install docker"
            echo "    sudo systemctl enable --now docker"
            ;;
        windows)
            echo "  ${BLUE}Windows:${NC}"
            echo "    1. Install WSL2: wsl --install"
            echo "    2. Install Docker Desktop: https://docker.com/products/docker-desktop"
            echo "       (Enable WSL2 backend in settings)"
            echo ""
            echo "  ${BLUE}Or Podman Desktop:${NC}"
            echo "    Download from: https://podman-desktop.io"
            ;;
        *)
            echo "  ${BLUE}Generic Linux:${NC}"
            echo "    # Check your distribution's package manager for 'podman' or 'docker'"
            echo ""
            echo "  ${BLUE}Docker (universal):${NC}"
            echo "    curl -fsSL https://get.docker.com | sh"
            echo "    sudo usermod -aG docker \$USER"
            ;;
    esac

    echo ""
    echo "After installation, run this script again."
    echo ""
}

# Sanitize project name: replace hyphens and spaces with underscore; lowercase; remove other special chars
sanitize_name() {
    local sanitized
    sanitized=$(echo "$1" | tr '[:upper:]' '[:lower:]' | sed 's/[ -]/_/g' | sed 's/[^a-z0-9_]/_/g')
    # Ensure generated package names start/end with alphanumeric characters.
    sanitized=$(echo "$sanitized" | sed 's/__*/_/g' | sed 's/^[^a-z0-9]*//; s/[^a-z0-9]*$//')
    echo "${sanitized:-project}"
}

# Sanitize for security only: remove shell metacharacters but preserve capitalization
sanitize_for_security() {
    echo "$1" | sed 's/[^a-zA-Z0-9._\/-]/_/g'
}

# Parse github.com remote URL to owner/repo (stdout), or return 1 if unsupported
# Same rules as assets/parse-github-remote-lib.sh (for GITHUB_REPOSITORY / renovate.json).
parse_github_remote() {
    local url="$1"
    local owner repo
    [[ -z "$url" ]] && return 1
    if [[ "$url" =~ https?://github\.com/([^/]+)/([^/.]+)(\.git)?/?$ ]]; then
        owner="${BASH_REMATCH[1]}"
        repo="${BASH_REMATCH[2]}"
        [[ "$owner/$repo" =~ ^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$ ]] || return 1
        echo "$owner/$repo"
        return 0
    fi
    if [[ "$url" =~ ^git@github\.com:([^/]+)/([^/.]+)(\.git)?$ ]]; then
        owner="${BASH_REMATCH[1]}"
        repo="${BASH_REMATCH[2]}"
        [[ "$owner/$repo" =~ ^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$ ]] || return 1
        echo "$owner/$repo"
        return 0
    fi
    if [[ "$url" =~ ^ssh://git@github\.com/([^/]+)/([^/.]+)(\.git)?$ ]]; then
        owner="${BASH_REMATCH[1]}"
        repo="${BASH_REMATCH[2]}"
        [[ "$owner/$repo" =~ ^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$ ]] || return 1
        echo "$owner/$repo"
        return 0
    fi
    return 1
}

# Run copy-host-user-conf.sh from the deployed project (non-fatal)
run_user_conf() {
    local project_path="$1"
    local script="$project_path/.devcontainer/scripts/copy-host-user-conf.sh"

    if [ ! -f "$script" ]; then
        warn "User configuration script not found at $script"
        echo "  Ensure the workspace has been initialized first."
        return 1
    fi

    info "Running user configuration setup (git, ssh, gh)..."
    if bash "$script"; then
        success "User configuration complete"
    else
        warn "User configuration had issues (see warnings above)"
        echo "  You can re-run this step later with:"
        echo "    cd $project_path && bash .devcontainer/scripts/copy-host-user-conf.sh"
        echo "  Or use: bash install.sh --user-conf $project_path"
    fi
}

# ── Upgrade preflight guard (#886) ────────────────────────────────────────────
# An upgrade (`--force`) rewrites and deletes files across the consumer tree,
# so it must land on a dedicated working branch with a clean tree, where it
# stays a single reviewable, revertible diff. The guard runs host-side because
# only the host reliably sees git state: the container mounts $PROJECT_PATH
# alone, so in a git worktree (where .git is a file pointing at an unmounted
# gitdir) git is unusable inside the container.

# Read a yes/no confirmation for the preflight guard.
# Returns 0 on yes, 1 on no or when no interactive input is available.
# stdin is used when it is a terminal or a redirected pipe/file; in the
# curl | bash form the script itself occupies stdin, so the prompt goes to
# /dev/tty and the reply never consumes script text.
preflight_confirm() {
    local prompt="$1" reply="" invoked
    invoked="$(basename -- "${0#-}")"
    if [ -t 0 ]; then
        read -rp "$prompt" reply
    elif [ "$invoked" = "bash" ] || [ "$invoked" = "sh" ]; then
        if [ -e /dev/tty ]; then
            read -rp "$prompt" reply </dev/tty || return 1
        else
            return 1
        fi
    else
        read -rp "$prompt" reply || return 1
    fi
    [[ "$reply" =~ ^[Yy]$ ]]
}

# Gate the --force (upgrade) path on git state. Refuses (exit != 0) on a dirty
# tree, on a detached HEAD, and on protected branches (main, dev, release/*
# by prefix) — on the latter, with a clean tree, it offers to create and
# switch to chore/devkit-upgrade-<version> and proceed there. A non-git
# directory gets a loud warning plus an explicit confirmation. Every refusal
# prints the --skip-preflight bypass. Under --dry-run nothing is mutated (the
# branch offer only reports what it would do).
run_preflight_guard() {
    local path="$1"
    local skip_hint="Re-run with --skip-preflight to bypass the upgrade preflight guard."
    local branch upgrade_branch dirty

    if ! command -v git >/dev/null 2>&1 \
        || ! git -C "$path" rev-parse --git-dir >/dev/null 2>&1; then
        warn "preflight: $path is not a git repository (or git is unavailable)."
        warn "There is no VCS safety net here: a bad upgrade cannot be reviewed or reverted."
        if preflight_confirm "Continue the upgrade anyway? (y/N): "; then
            return 0
        fi
        err "preflight: upgrade refused (no git repository, not confirmed)."
        echo "  Put the project under version control first, or:"
        echo "  $skip_hint"
        exit 1
    fi

    dirty="$(git -C "$path" status --porcelain 2>/dev/null || true)"
    if [ -n "$dirty" ]; then
        err "preflight: refusing to upgrade on a dirty tree."
        echo "  An upgrade must be the only change in its diff — commit or stash this first:"
        printf '%s\n' "$dirty" | head -10 | sed 's/^/    /'
        echo "  $skip_hint"
        exit 1
    fi

    upgrade_branch="chore/devkit-upgrade-$VERSION"
    if ! branch="$(git -C "$path" symbolic-ref --quiet --short HEAD)"; then
        err "preflight: refusing to upgrade on a detached HEAD."
        echo "  Check out a working branch first, e.g.:"
        echo "    git -C \"$path\" switch -c $upgrade_branch"
        echo "  $skip_hint"
        exit 1
    fi

    case "$branch" in
        main|dev|release/*)
            warn "preflight: '$branch' is a protected branch — upgrades need a dedicated branch."
            if preflight_confirm "Create and switch to '$upgrade_branch' now? (y/N): "; then
                if [ "$DRY_RUN" = true ]; then
                    info "dry-run: would create and switch to '$upgrade_branch'"
                elif git -C "$path" checkout -b "$upgrade_branch"; then
                    info "Switched to new branch '$upgrade_branch'"
                else
                    err "preflight: could not create branch '$upgrade_branch'."
                    exit 1
                fi
            else
                err "preflight: refusing to upgrade on protected branch '$branch'."
                echo "  Create a dedicated branch and re-run:"
                echo "    git -C \"$path\" checkout -b $upgrade_branch"
                echo "  $skip_hint"
                exit 1
            fi
            ;;
    esac
}

# Parse arguments
while [ $# -gt 0 ]; do
    case "$1" in
        --force)
            FORCE="--force"
            shift
            ;;
        --version)
            VERSION="$2"
            shift 2
            ;;
        --docker)
            RUNTIME="docker"
            shift
            ;;
        --podman)
            RUNTIME="podman"
            shift
            ;;
        --name)
            PROJECT_NAME="$2"
            shift 2
            ;;
        --org)
            ORG_NAME="$2"
            shift 2
            ;;
        --repo)
            GITHUB_REPO_OVERRIDE="$2"
            shift 2
            ;;
        --mode)
            MODE="$2"
            shift 2
            ;;
        --mode=*)
            MODE="${1#--mode=}"
            shift
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --smoke-test)
            SMOKE_TEST="--smoke-test"
            shift
            ;;
        --preview)
            PREVIEW="--preview"
            shift
            ;;
        --skip-preflight)
            SKIP_PREFLIGHT=true
            shift
            ;;
        --skip-pull)
            SKIP_PULL=true
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        -*)
            err "Unknown option: $1"
            usage
            exit 1
            ;;
        *)
            PROJECT_PATH="$1"
            shift
            ;;
    esac
done

# Validate delivery mode (empty = .vig-os manifest, else init-workspace.sh prompt/default)
case "$MODE" in
    ""|devcontainer|direnv|both|bare) ;;
    *)
        err "Invalid --mode: $MODE (expected: devcontainer | direnv | both | bare)"
        usage
        exit 1
        ;;
esac

# Validate and set project path
PROJECT_PATH="${PROJECT_PATH:-.}"
if [ ! -d "$PROJECT_PATH" ]; then
    err "Directory does not exist: $PROJECT_PATH"
    exit 1
fi
PROJECT_PATH="$(cd "$PROJECT_PATH" && pwd)"

# ── .vig-os project manifest (#885) ───────────────────────────────────────────
# The target's .vig-os persists the delivery mode and identity, so upgrades
# need no mode/identity flags. Precedence per key: explicit flag > .vig-os >
# detection/default. Same tolerant line-based parsing as every other consumer.

# Print the value of manifest key $2 in file $1; return 1 when absent.
read_manifest_value() {
    local file="$1" key="$2" line value
    [ -f "$file" ] || return 1
    while IFS= read -r line || [ -n "${line:-}" ]; do
        [ -z "${line//[[:space:]]/}" ] && continue
        [[ "$line" =~ ^[[:space:]]*# ]] && continue
        case "$line" in
            "$key"=*)
                value="${line#*=}"
                value="${value#"${value%%[![:space:]]*}"}"
                value="${value%"${value##*[![:space:]]}"}"
                case "$value" in
                    \"*\") value="${value#\"}"; value="${value%\"}" ;;
                    \'*\') value="${value#\'}"; value="${value%\'}" ;;
                esac
                [ -n "$value" ] || return 1
                echo "$value"
                return 0
                ;;
        esac
    done < "$file"
    return 1
}

MANIFEST_MODE="$(read_manifest_value "$PROJECT_PATH/.vig-os" DEVKIT_MODE || true)"
MANIFEST_PROJECT="$(read_manifest_value "$PROJECT_PATH/.vig-os" DEVKIT_PROJECT || true)"
MANIFEST_ORG="$(read_manifest_value "$PROJECT_PATH/.vig-os" DEVKIT_ORG || true)"
MANIFEST_REPO="$(read_manifest_value "$PROJECT_PATH/.vig-os" DEVKIT_REPO || true)"
# The OWNER/REPO placeholder (persisted when no origin was resolvable) must
# not mask a now-detectable git origin.
[ "$MANIFEST_REPO" = "OWNER/REPO" ] && MANIFEST_REPO=""

case "$MANIFEST_MODE" in
    ""|devcontainer|direnv|both|bare) ;;
    *)
        err "Invalid DEVKIT_MODE in $PROJECT_PATH/.vig-os: $MANIFEST_MODE"
        exit 1
        ;;
esac

# Mode switching is destructive and never happens implicitly (#885): an
# explicit --mode contradicting the persisted DEVKIT_MODE refuses. --preview
# (report-only) stays available to inspect the would-be switch first.
if [ -n "$MODE" ] && [ -n "$MANIFEST_MODE" ] && [ "$MODE" != "$MANIFEST_MODE" ] \
    && [ -z "$PREVIEW" ] && [ -z "$SMOKE_TEST" ]; then
    err "requested --mode $MODE contradicts the persisted DEVKIT_MODE=$MANIFEST_MODE in $PROJECT_PATH/.vig-os"
    echo "  Mode switching reshapes the workspace and must be deliberate:"
    echo "  1. Inspect the would-be change first:  install.sh --preview --mode $MODE $PROJECT_PATH"
    echo "  2. Keep the persisted mode by omitting --mode, or"
    echo "  3. Switch deliberately: set DEVKIT_MODE=$MODE in .vig-os on a dedicated,"
    echo "     clean upgrade branch (the preflight guard flow) and re-run."
    exit 1
fi

if [ -z "$MODE" ] && [ -n "$MANIFEST_MODE" ] && [ -z "$SMOKE_TEST" ]; then
    MODE="$MANIFEST_MODE"
    info "Delivery mode from .vig-os manifest: $MODE"
fi

# Derive project name: --name > persisted DEVKIT_PROJECT > folder name (#885)
if [ -z "$PROJECT_NAME" ] && [ -n "$MANIFEST_PROJECT" ]; then
    PROJECT_NAME="$MANIFEST_PROJECT"
    info "Project name from .vig-os manifest: $PROJECT_NAME"
fi
if [ -z "$PROJECT_NAME" ]; then
    PROJECT_NAME="$(basename "$PROJECT_PATH")"
fi
PROJECT_NAME=$(sanitize_name "$PROJECT_NAME")

# Organization: --org > persisted DEVKIT_ORG > default (#885)
if [ -z "$ORG_NAME" ] && [ -n "$MANIFEST_ORG" ]; then
    ORG_NAME="$MANIFEST_ORG"
    info "Organization name from .vig-os manifest: $ORG_NAME"
fi
ORG_NAME="${ORG_NAME:-vigOS}"
# Sanitize ORG_NAME for security (remove shell metacharacters) but preserve capitalization
ORG_NAME=$(sanitize_for_security "$ORG_NAME")

# GITHUB_REPOSITORY for init-workspace --no-prompts (Renovate extends in
# renovate.json): --repo > persisted DEVKIT_REPO > git origin > OWNER/REPO
GITHUB_REPOSITORY="$GITHUB_REPO_OVERRIDE"
if [ -z "$GITHUB_REPOSITORY" ] && [ -n "$MANIFEST_REPO" ]; then
    GITHUB_REPOSITORY="$MANIFEST_REPO"
    info "GitHub repository from .vig-os manifest: $GITHUB_REPOSITORY"
fi
GITHUB_REPOSITORY=$(sanitize_for_security "$GITHUB_REPOSITORY")
if [ -z "$GITHUB_REPOSITORY" ] && [ -d "$PROJECT_PATH/.git" ]; then
    url=$(git -C "$PROJECT_PATH" remote get-url origin 2>/dev/null || true)
    if [ -n "$url" ]; then
        if repo=$(parse_github_remote "$url"); then
            GITHUB_REPOSITORY=$(sanitize_for_security "$repo")
        fi
    fi
fi
if [ -z "$GITHUB_REPOSITORY" ]; then
    GITHUB_REPOSITORY="OWNER/REPO"
fi

# Preflight-gate --force upgrades (#886). Exemptions:
# - --smoke-test: the downstream release gate runs `install.sh --version <tag>
#   --smoke-test --force --docker .` headless on a CI checkout;
# - --preview: report-only, exits before mutating anything (#885 mode switches
#   point users at it first, so it must work from any branch/tree state);
# - fresh installs (no --force): the "workspace not empty" refusal in
#   init-workspace.sh already covers accidental re-runs.
if [ -n "$FORCE" ] && [ -z "$SMOKE_TEST" ] && [ -z "$PREVIEW" ] \
    && [ "$SKIP_PREFLIGHT" = false ]; then
    run_preflight_guard "$PROJECT_PATH"
fi

# Detect container runtime
RUNTIME=$(detect_runtime)
if [ -z "$RUNTIME" ]; then
    err "No container runtime found!"
    OS=$(detect_os)
    show_install_instructions "$OS"
    exit 1
fi

# Verify runtime is actually working
if ! $RUNTIME info >/dev/null 2>&1; then
    OS=$(detect_os)
    err "$RUNTIME is installed but not running!"
    echo ""
    case "$OS" in
        macos)
            if [ "$RUNTIME" = "podman" ]; then
                echo "Start the Podman machine:"
                echo "  podman machine start"
                echo ""
                echo "If no machine exists, create one first:"
                echo "  podman machine init"
                echo "  podman machine start"
            else
                echo "Start Docker Desktop from your Applications folder,"
                echo "or run: open -a Docker"
            fi
            ;;
        windows)
            echo "Make sure Docker Desktop or Podman Desktop is running."
            echo "Check the system tray for the container icon."
            ;;
        *)
            if [ "$RUNTIME" = "docker" ]; then
                echo "Start the Docker daemon:"
                echo "  sudo systemctl start docker"
                echo ""
                echo "To enable on boot:"
                echo "  sudo systemctl enable docker"
            else
                echo "Podman should work without a daemon on Linux."
                echo "Try running: podman info"
                echo ""
                echo "If using rootless podman, ensure your user session is set up:"
                echo "  podman system migrate"
            fi
            ;;
    esac
    echo ""
    exit 1
fi

IMAGE="$REGISTRY:$VERSION"

info "Using $RUNTIME with image $IMAGE"
info "Target directory: $PROJECT_PATH"
info "Project name: $PROJECT_NAME"

# Forward an explicitly requested version so init-workspace pins it in the
# scaffolded .vig-os (#852). The image's baked pin is the release the image
# was built from, which is stale for release candidates (the repo pin only
# advances at finalize). "latest" is not a concrete tag: keep the baked pin.
# (The ${arr[@]+...} idiom keeps empty-array expansion safe under set -u on
# bash 3.2, e.g. macOS.)
declare -a VERSION_ENV=()
if [ "$VERSION" != "latest" ]; then
    VERSION_ENV=(-e "VIG_OS_VERSION=$VERSION")
fi

# Build the command using an array for safe execution
# Use --rm to cleanup container after run; no -it since we use --no-prompts (non-interactive)
# Pass SHORT_NAME and ORG_NAME as environment variables to the container
declare -a CMD=(
    "$RUNTIME" run --rm
    -e "SHORT_NAME=$PROJECT_NAME"
    -e "ORG_NAME=$ORG_NAME"
    -e "GITHUB_REPOSITORY=$GITHUB_REPOSITORY"
    ${VERSION_ENV[@]+"${VERSION_ENV[@]}"}
    -v "$PROJECT_PATH:/workspace"
    "$IMAGE"
    /root/assets/init-workspace.sh --no-prompts
)

if [ -n "$FORCE" ]; then
    CMD+=(--force)
fi

if [ -n "$SMOKE_TEST" ]; then
    CMD+=(--smoke-test)
fi

if [ -n "$PREVIEW" ]; then
    CMD+=(--preview)
fi

if [ -n "$MODE" ]; then
    CMD+=(--mode "$MODE")
fi

if [ "$DRY_RUN" = true ]; then
    info "Would execute:"
    # Derive the shown command from the real CMD array (built above, including
    # --force/--smoke-test/--mode) via printf '%q' so it is shell-safe and stays
    # in sync with what would actually run — no hand-maintained duplicate string.
    printf '  '
    printf '%q ' "${CMD[@]}"
    printf '\n'
    exit 0
fi

# Record whether the target was empty BEFORE the container scaffolds it. The git
# step below only auto-commits a freshly scaffolded tree, so it never sweeps a
# pre-populated directory into a misleading "initial scaffold" commit (#759).
TARGET_WAS_EMPTY=false
if [ -z "$(ls -A "$PROJECT_PATH" 2>/dev/null)" ]; then
    TARGET_WAS_EMPTY=true
fi

# Check if terminal is interactive (needed for init-workspace.sh prompts)
# When piped via curl, stdin is the script - use /dev/tty for user input
# Only check this when actually running (not in dry-run mode)
if [ ! -t 0 ]; then
    if [ ! -e /dev/tty ]; then
        err "This script requires an interactive terminal"
        echo ""
        echo "Try running directly instead of piping:"
        echo "  curl -sSfL https://raw.githubusercontent.com/vig-os/devkit/main/install.sh -o install.sh"
        echo "  bash install.sh $PROJECT_PATH"
        exit 1
    fi
fi

# Pull image first (better UX - shows progress separately)
if [ "$SKIP_PULL" = false ]; then
    info "Pulling image $IMAGE..."
    if ! $RUNTIME pull "$IMAGE" >/dev/null 2>&1; then
        err "Failed to pull image $IMAGE"
        echo ""
        echo "Check your internet connection and that the image exists:"
        echo "  $REGISTRY:$VERSION"
        exit 1
    fi
else
    # Verify image exists locally when skipping pull
    if ! $RUNTIME image inspect "$IMAGE" >/dev/null 2>&1; then
        err "Image $IMAGE not found locally (--skip-pull was specified)"
        exit 1
    fi
    info "Using local image $IMAGE (skipping pull)"
fi

# Run the initialization
if [ -n "$PREVIEW" ]; then
    info "Previewing upgrade (no files will be changed)..."
else
    info "Initializing workspace..."
fi
echo ""

# Execute the container using array expansion (safe from shell injection)
if ! "${CMD[@]}"; then
    err "Failed to initialize workspace"
    exit 1
fi

# Preview mode: init-workspace.sh printed the file report and exited before
# mutating anything — skip all post-initialization (user conf, git setup).
if [ -n "$PREVIEW" ]; then
    echo ""
    success "Preview complete — no files were changed in $PROJECT_PATH"
    exit 0
fi

# ── Post-initialization: host-side setup ──────────────────────────────────────

echo ""
info "Running post-initialization setup..."

# 1. Copy host user configuration (git, ssh, gh) into .devcontainer/.conf/
# Non-fatal: warnings about missing SSH keys or GH CLI are expected on CI/fresh machines.
# direnv and bare modes scaffold no .devcontainer/, so the host-user-conf step
# (a devcontainer-only concern) does not apply — skip it rather than emit a
# misleading "script not found" warning (#738, #885).
if [ "$MODE" = "direnv" ] || [ "$MODE" = "bare" ]; then
    info "$MODE mode: skipping host user-conf copy (no .devcontainer/)"
else
    run_user_conf "$PROJECT_PATH" || true
fi

# 2. Git repository setup (init, initial commit, dev branch)
# Runs on the host (not in container) so that SSH agent is available for commit signing
info "Setting up git repository..."

setup_git_repo() {
    local workspace_dir="$1"
    local created_repo=false

    echo "Verifying git repository..."
    cd "$workspace_dir"

    # Initialize git repo if missing
    if [ ! -d ".git" ]; then
        echo "No git repository found, initializing..."
        git init -b main
        created_repo=true
        echo "Git repository initialized with 'main' branch"
    fi

    # Create initial commit if repo has no commits (enables branch creation).
    # Only auto-commit when we scaffolded an empty target; never sweep a
    # pre-populated directory into a misleading "initial scaffold" commit (#759).
    if ! git rev-parse HEAD >/dev/null 2>&1; then
        if [ "${TARGET_WAS_EMPTY:-false}" = true ]; then
            echo "Creating initial commit..."
            git add -A
            git commit -m "chore: initial project scaffold" --allow-empty
            created_repo=true
            echo "Initial commit created"
        else
            echo "Existing files detected; skipping the automatic scaffold commit."
            echo "  Review and commit your files yourself, e.g.:"
            echo "    git add -A && git commit -m 'chore: initial commit'"
            created_repo=false
        fi
    fi

    # Verify or create branches
    if [ "$created_repo" = true ]; then
        # New repo: create dev branch from main
        if ! git rev-parse --verify dev >/dev/null 2>&1; then
            echo "Creating 'dev' branch..."
            git branch dev
            echo "'dev' branch created"
        fi
    else
        # Existing repo: warn about missing branches
        if ! git rev-parse --verify main >/dev/null 2>&1; then
            echo "Warning: Branch 'main' not found in existing repository"
            echo "  The project workflow expects a 'main' branch."
        fi
        if ! git rev-parse --verify dev >/dev/null 2>&1; then
            echo "Warning: Branch 'dev' not found in existing repository"
            echo "  The project workflow expects a 'dev' branch."
            echo "  Create it with: git branch dev"
        fi
    fi

    echo ""
    echo "Git repository setup complete."
    echo ""
    echo "You can set a remote origin with:"
    echo "  git remote add origin <your-repo-url>"
    echo "Then push your branches with:"
    echo "  git push -u origin main dev"
    echo ""
}

if ! setup_git_repo "$PROJECT_PATH"; then
    warn "Git repository setup failed (non-fatal)"
    echo "  You can set up the repository manually with:"
    echo "    cd $PROJECT_PATH && git init -b main && git add -A && git commit -m 'chore: initial project scaffold'"
fi

# ── Done ──────────────────────────────────────────────────────────────────────

echo ""
success "Devcontainer deployed to $PROJECT_PATH"
echo ""
echo "Next steps:"
echo "  1. cd $PROJECT_PATH"
if [ "$MODE" = "bare" ]; then
    echo "  2. Run 'just help' to list the shipped recipes (host-native: no container)"
else
    echo "  2. Open in VS Code - it will detect .devcontainer/ and offer to reopen in container"
fi
echo ""
