#!/usr/bin/env bash
###############################################################################
# init.sh - Nix-first development environment bootstrapper
#
# This repo's toolchain is defined by the Nix flake (`flake.nix` devTools) and
# provisioned by `direnv allow` (recommended) or `nix develop`. This script does
# NOT install tools. It:
#   1. Gates on the host prerequisites (Nix, and direnv unless --no-direnv).
#   2. Confirms the dev-shell toolchain is on PATH.
#   3. Performs one-time, idempotent project bootstrap (uv sync, git hooks,
#      commit template, pre-commit) and advisory host checks (podman, gh).
#
# USAGE:
#   ./scripts/init.sh              # Gate prerequisites, then bootstrap the project
#   ./scripts/init.sh --check      # Verify prerequisites only; do not bootstrap
#   ./scripts/init.sh --no-direnv  # Don't require direnv (using `nix develop`)
#   ./scripts/init.sh --help       # Show this help
#
# TOOLCHAIN: see `flake.nix` (devTools) — the single source of truth.
###############################################################################

set -euo pipefail

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color
BOLD='\033[1m'

# Flags
CHECK_ONLY=false
REQUIRE_DIRENV=true

# ═══════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

print_section() {
    echo -e "\n${BOLD}${CYAN}───────────────────────────────────────────────────────────────${NC}"
    echo -e "${BOLD}${CYAN}  $1${NC}"
    echo -e "${BOLD}${CYAN}───────────────────────────────────────────────────────────────${NC}\n"
}

log_info() {
    echo -e "${BLUE}ℹ${NC}  $1"
}

log_success() {
    echo -e "${GREEN}✓${NC}  $1"
}

log_warning() {
    echo -e "${YELLOW}⚠${NC}  $1"
}

log_error() {
    echo -e "${RED}✗${NC}  $1" >&2
}

usage() {
    cat <<'EOF'
init.sh - Nix-first development environment bootstrapper

USAGE:
  ./scripts/init.sh              Gate prerequisites, then bootstrap the project
  ./scripts/init.sh --check      Verify prerequisites only; do not bootstrap
  ./scripts/init.sh --no-direnv  Don't require direnv (using `nix develop`)
  ./scripts/init.sh --help       Show this help

The toolchain is provisioned by the Nix flake, not by this script. Enter the dev
shell with `direnv allow` (recommended) or `nix develop`, then run `just init`.
EOF
}

# ═══════════════════════════════════════════════════════════════════════════════
# PREREQUISITE GUIDANCE
# ═══════════════════════════════════════════════════════════════════════════════

# NOTE: these print with the printf builtin (not `cat`) so the gate still works
# when PATH carries no external tools — the whole point of the gate.
print_nix_guidance() {
    log_error "Nix is required but was not found on PATH."
    printf '%s\n' \
        '' \
        "  This repository's toolchain is provided by the Nix flake. Install Nix, then" \
        '  re-enter the project to get every tool automatically.' \
        '' \
        '  1. Install Nix:' \
        '       https://nixos.org/download' \
        '' \
        '  2. Enable flakes — add to ~/.config/nix/nix.conf (or /etc/nix/nix.conf):' \
        '       experimental-features = nix-command flakes' \
        '' \
        '  3. Add the vig-os binary cache so the dev-shell is a fast fetch, not a build:' \
        '       substituters = https://cache.nixos.org https://vig-os.cachix.org' \
        '       trusted-public-keys = cache.nixos.org-1:6NCHdD59X431o0gWypbMrAURkbJ16ZPMQFGspcDShjY= vig-os.cachix.org-1:yoOYRi3bvnM6ThxO0joLt7vtzhTfkq3r6jykeUMg7Bk=' \
        '' \
        '  4. Then enter the dev shell and re-run:' \
        '       direnv allow      # (recommended) or: nix develop' \
        '       just init' \
        ''
}

print_devshell_guidance() {
    log_error "The dev-shell toolchain is not on PATH (uv was not found)."
    printf '%s\n' \
        '' \
        '  Enter the Nix dev shell first, then re-run "just init":' \
        '       direnv allow      # (recommended) or: nix develop' \
        ''
}

# ═══════════════════════════════════════════════════════════════════════════════
# ARGUMENT PARSING
# ═══════════════════════════════════════════════════════════════════════════════

while [[ $# -gt 0 ]]; do
    case "$1" in
        --check | -c)
            CHECK_ONLY=true
            shift
            ;;
        --no-direnv)
            REQUIRE_DIRENV=false
            shift
            ;;
        --help | -h)
            usage
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            echo "Use --help for usage information." >&2
            exit 1
            ;;
    esac
done

# ═══════════════════════════════════════════════════════════════════════════════
# CONTAINER SHORT-CIRCUIT
# ═══════════════════════════════════════════════════════════════════════════════

# The built devcontainer image already bakes the toolchain, the project venv,
# and the pre-commit cache — there is nothing to bootstrap.
if [ "${IN_CONTAINER:-}" = "true" ]; then
    log_success "Running inside the devcontainer image — already provisioned. Nothing to do."
    exit 0
fi

# ═══════════════════════════════════════════════════════════════════════════════
# PREREQUISITE GATE  (pure shell builtins only — runs before any external tool)
# ═══════════════════════════════════════════════════════════════════════════════

if ! command -v nix >/dev/null 2>&1; then
    print_nix_guidance
    exit 1
fi

if [ "$REQUIRE_DIRENV" = true ] && ! command -v direnv >/dev/null 2>&1; then
    log_warning "direnv not found — recommended for automatic dev-shell entry (https://direnv.net/)."
    log_info "Continuing; use \`nix develop\` to enter the shell, or pass --no-direnv to silence this."
fi

if ! command -v uv >/dev/null 2>&1; then
    print_devshell_guidance
    exit 1
fi

if [ "$CHECK_ONLY" = true ]; then
    log_success "Prerequisites satisfied: Nix and the dev-shell toolchain are available."
    exit 0
fi

# ═══════════════════════════════════════════════════════════════════════════════
# PROJECT BOOTSTRAP  (one-time, idempotent)
# ═══════════════════════════════════════════════════════════════════════════════

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

print_section "Project Bootstrap"

# Materialize the project venv from the lockfile. uv builds it from the
# interpreter the flake dev-shell pins via UV_PYTHON (UV_PYTHON_DOWNLOADS=never);
# no interpreter is hardcoded here.
log_info "Syncing the project environment from the lockfile..."
if uv sync --frozen --all-extras; then
    log_success "Project dependencies installed"
else
    log_error "Failed to sync project dependencies"
    exit 1
fi

# Git hooks live in .githooks (tracked); point core.hooksPath at them.
if git config core.hooksPath .githooks && chmod +x .githooks/* 2>/dev/null; then
    log_success "Git hooks path configured (.githooks)"
else
    log_warning "Could not configure the git hooks path"
fi

# Commit message template (see docs/COMMIT_MESSAGE_STANDARD.md)
if [ -f .gitmessage ] && git config commit.template .gitmessage; then
    log_success "Commit message template configured (.gitmessage)"
fi

if uv run pre-commit install-hooks; then
    log_success "Pre-commit hooks installed"
else
    log_warning "Could not install pre-commit hooks"
fi

# ═══════════════════════════════════════════════════════════════════════════════
# ADVISORY HOST CHECKS  (non-fatal — these depend on host configuration)
# ═══════════════════════════════════════════════════════════════════════════════

print_section "Host Checks"

# A working rootless container runtime is a host prerequisite: the flake ships
# the podman CLI, but rootless operation needs host setuid uid-mappers (Linux)
# or a podman machine (macOS), which Nix cannot provide.
if podman info >/dev/null 2>&1; then
    log_success "Container runtime is working (podman info)"
else
    log_warning "podman is not usable yet (rootless runtime needs host setup)."
    if [ "$(uname -s)" = "Darwin" ]; then
        log_info "macOS: initialize a VM with \`podman machine init && podman machine start\`."
    else
        log_info "Linux: ensure rootless podman is configured (subuid/subgid, uidmap), then re-check with \`podman info\`."
    fi
fi

if gh auth status >/dev/null 2>&1; then
    log_success "GitHub CLI is authenticated"
else
    log_warning "GitHub CLI is not authenticated — run \`gh auth login\`."
fi

# ═══════════════════════════════════════════════════════════════════════════════
# DONE
# ═══════════════════════════════════════════════════════════════════════════════

print_section "Setup Complete"
log_success "Environment bootstrapped."
log_info "Run ${BOLD}just${NC} to see available commands."
