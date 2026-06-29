#!/usr/bin/env bash
# vigOS devcontainer quick install script
#
# Usage:
#   curl -sSf https://raw.githubusercontent.com/vig-os/devcontainer/main/install.sh | bash
#   curl -sSf https://raw.githubusercontent.com/vig-os/devcontainer/main/install.sh | bash -s -- [OPTIONS] [PATH]
#
# Options:
#   --force           Overwrite existing files (for upgrades)
#   --version VER     Use specific version (default: latest)
#   --docker          Force docker (default: auto-detect, prefers podman)
#   --podman          Force podman
#   --name NAME       Override project name (SHORT_NAME)
#   --org ORG         Override organization name (default: vigOS)
#   --repo OWNER/REPO GitHub repo for Renovate preset (default: detect from origin or OWNER/REPO)
#   --mode MODE       Delivery mode: devcontainer | direnv | both (default: prompt, both non-interactively)
#   --smoke-test      Deploy smoke-test-specific assets
#   --dry-run         Show what would be done without executing
#   -h, --help        Show this help message
#
# Examples:
#   curl -sSf https://raw.githubusercontent.com/vig-os/devcontainer/main/install.sh | bash
#   curl -sSf ... | bash -s -- ~/Projects/my-project
#   curl -sSf ... | bash -s -- --version 0.2.1 --force ./my-project
#   curl -sSf ... | bash -s -- --org MyOrg ./my-project

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
ORG_NAME="vigOS"
GITHUB_REPO_OVERRIDE=""
MODE=""
SMOKE_TEST=""

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
    curl -sSf https://raw.githubusercontent.com/vig-os/devcontainer/main/install.sh | bash
    curl -sSf ... | bash -s -- [OPTIONS] [PATH]

OPTIONS:
    --force           Overwrite existing files (for upgrades)
    --version VER     Use specific version (default: latest)
    --docker          Force docker runtime
    --podman          Force podman runtime
    --name NAME       Override project name (SHORT_NAME, used for module name)
    --org ORG         Override organization name (default: vigOS)
    --repo OWNER/REPO GitHub repository for Renovate (default: git origin or OWNER/REPO)
    --mode MODE       Delivery mode: devcontainer | direnv | both
                      (default: prompt interactively; "both" non-interactively)
    --smoke-test      Deploy smoke-test-specific assets
    --dry-run         Show what would be done
    -h, --help        Show this help

EXAMPLES:
    # Initialize current directory with latest version
    curl -sSf https://raw.githubusercontent.com/vig-os/devcontainer/main/install.sh | bash

    # Initialize specific directory
    curl -sSf ... | bash -s -- ~/Projects/my-new-project

    # Upgrade existing project
    curl -sSf ... | bash -s -- --force ./my-project

    # Use specific version
    curl -sSf ... | bash -s -- --version 0.2.1 ./my-project

    # Override project name
    curl -sSf ... | bash -s -- --name my_custom_name ./my-project

    # Use custom organization name
    curl -sSf ... | bash -s -- --org MyOrg ./my-project

    # Scaffold only the Nix/direnv stub (no .devcontainer/)
    curl -sSf ... | bash -s -- --mode direnv ./my-project
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

# Validate delivery mode (empty = let init-workspace.sh prompt / default to both)
case "$MODE" in
    ""|devcontainer|direnv|both) ;;
    *)
        err "Invalid --mode: $MODE (expected: devcontainer | direnv | both)"
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

# Derive project name from folder if not provided
if [ -z "$PROJECT_NAME" ]; then
    PROJECT_NAME="$(basename "$PROJECT_PATH")"
fi
PROJECT_NAME=$(sanitize_name "$PROJECT_NAME")

# Sanitize ORG_NAME for security (remove shell metacharacters) but preserve capitalization
ORG_NAME=$(sanitize_for_security "$ORG_NAME")

# GITHUB_REPOSITORY for init-workspace --no-prompts (Renovate extends in renovate.json)
GITHUB_REPOSITORY="$GITHUB_REPO_OVERRIDE"
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

# Build the command using an array for safe execution
# Use --rm to cleanup container after run; no -it since we use --no-prompts (non-interactive)
# Pass SHORT_NAME and ORG_NAME as environment variables to the container
declare -a CMD=(
    "$RUNTIME" run --rm
    -e "SHORT_NAME=$PROJECT_NAME"
    -e "ORG_NAME=$ORG_NAME"
    -e "GITHUB_REPOSITORY=$GITHUB_REPOSITORY"
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

if [ -n "$MODE" ]; then
    CMD+=(--mode "$MODE")
fi

if [ "$DRY_RUN" = true ]; then
    info "Would execute:"
    printf "  %s" "$RUNTIME run --rm -e SHORT_NAME=\"$PROJECT_NAME\" -e ORG_NAME=\"$ORG_NAME\" -e GITHUB_REPOSITORY=\"$GITHUB_REPOSITORY\" -v \"$PROJECT_PATH\":/workspace \"$IMAGE\" /root/assets/init-workspace.sh --no-prompts"
    if [ -n "$FORCE" ]; then
        printf " %s" "--force"
    fi
    if [ -n "$SMOKE_TEST" ]; then
        printf " %s" "--smoke-test"
    fi
    if [ -n "$MODE" ]; then
        printf " %s %s" "--mode" "$MODE"
    fi
    printf "\n"
    exit 0
fi

# Check if terminal is interactive (needed for init-workspace.sh prompts)
# When piped via curl, stdin is the script - use /dev/tty for user input
# Only check this when actually running (not in dry-run mode)
if [ ! -t 0 ]; then
    if [ ! -e /dev/tty ]; then
        err "This script requires an interactive terminal"
        echo ""
        echo "Try running directly instead of piping:"
        echo "  curl -sSf https://raw.githubusercontent.com/vig-os/devcontainer/main/install.sh -o install.sh"
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
    if ! $RUNTIME image exists "$IMAGE" 2>/dev/null; then
        err "Image $IMAGE not found locally (--skip-pull was specified)"
        exit 1
    fi
    info "Using local image $IMAGE (skipping pull)"
fi

# Run the initialization
info "Initializing workspace..."
echo ""

# Execute the container using array expansion (safe from shell injection)
if ! "${CMD[@]}"; then
    err "Failed to initialize workspace"
    exit 1
fi

# ── Post-initialization: host-side setup ──────────────────────────────────────

echo ""
info "Running post-initialization setup..."

# 1. Copy host user configuration (git, ssh, gh) into .devcontainer/.conf/
# Non-fatal: warnings about missing SSH keys or GH CLI are expected on CI/fresh machines.
# direnv mode scaffolds no .devcontainer/, so the host-user-conf step (a
# devcontainer-only concern) does not apply — skip it rather than emit a
# misleading "script not found" warning (#738).
if [ "$MODE" = "direnv" ]; then
    info "direnv mode: skipping host user-conf copy (no .devcontainer/)"
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

    # Create initial commit if repo has no commits (enables branch creation)
    if ! git rev-parse HEAD >/dev/null 2>&1; then
        echo "Creating initial commit..."
        git add -A
        git commit -m "chore: initial project scaffold" --allow-empty
        created_repo=true
        echo "Initial commit created"
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
echo "  2. Open in VS Code - it will detect .devcontainer/ and offer to reopen in container"
echo ""
