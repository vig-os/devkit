#!/usr/bin/env bash
###############################################################################
# devc-remote.sh - Remote devcontainer orchestrator
#
# Starts a devcontainer on a remote host via SSH and optionally opens an IDE.
# Handles SSH connectivity, pre-flight checks, container state detection,
# compose lifecycle, and optional Tailscale auth key injection.
#
# USAGE:
#   ./scripts/devc-remote.sh [options] <ssh-host>[:<remote-path>] [gh:<org>/<repo>[:<branch>]]
#   ./scripts/devc-remote.sh --bootstrap [--yes] <ssh-host>
#   ./scripts/devc-remote.sh --help
#
# Options:
#   --bootstrap       One-time remote host setup (config, GHCR auth, image build)
#   --yes, -y         Auto-accept prompts (use defaults without asking)
#   --force, -f       Auto-push unpushed commits before deploying (gh: targets)
#   --open <mode>     How to connect after compose up:
#                       auto    - detect IDE from $TERM_PROGRAM or CLI availability (default)
#                       cursor  - open Cursor via devcontainer protocol
#                       code    - open VS Code via devcontainer protocol
#                       ssh     - wait for Tailscale, print hostname (for SSH clients)
#                       none    - infra only, no IDE
#
# GitHub repo target (gh:):
#   Clone a GitHub repo on the remote host and start its devcontainer.
#   gh:<org>/<repo>           Clone to <projects_dir>/<repo> (from config or ~/Projects)
#   gh:<org>/<repo>:<branch>  Clone and checkout specified branch
#   Combined with host:path to override clone location:
#     <host>:<path> gh:<org>/<repo>   Clone to <path> instead of default
#
# Tailscale key injection (opt-in):
#   When TS_CLIENT_ID and TS_CLIENT_SECRET are set in the local environment,
#   generates an ephemeral auth key via the Tailscale API and injects it
#   into the remote docker-compose.local.yaml before compose up.
#
# Examples:
#   ./scripts/devc-remote.sh myserver
#   ./scripts/devc-remote.sh --open none myserver:/home/user/repo
#   ./scripts/devc-remote.sh --open ssh myserver
#   ./scripts/devc-remote.sh --yes --open code user@host:/opt/projects/myrepo
#   ./scripts/devc-remote.sh myserver gh:vig-os/fd5
#   ./scripts/devc-remote.sh myserver gh:vig-os/fd5:feature/my-branch
#   ./scripts/devc-remote.sh myserver:~/custom/path gh:vig-os/fd5
#
# Part of #70. See issues #152, #230, #231, #236 for design.
###############################################################################

set -euo pipefail

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

# shellcheck disable=SC2034
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ═══════════════════════════════════════════════════════════════════════════════
# LOGGING (matches init.sh patterns)
# ═══════════════════════════════════════════════════════════════════════════════

log_info() {
    echo -e "${BLUE}ℹ${NC}  $1"
}

# Sanitize a string for use as a DNS label (Tailscale hostnames, etc.)
sanitize_dns_label() {
    echo "${1//_/-}"
}

log_success() {
    echo -e "${GREEN}✓${NC}  $1"
}

log_warning() {
    echo -e "${YELLOW}⚠${NC}  $1"
}

log_error() {
    echo -e "${RED}✗${NC}  $1"
}

show_help() {
    sed -n '/^###############################################################################$/,/^###############################################################################$/p' "$0" | sed '1d;$d'
    exit 0
}

parse_args() {
    SSH_HOST=""
    REMOTE_PATH="~"
    YES_MODE=0
    OPEN_MODE="auto"
    BOOTSTRAP_MODE=0
    FORCE_PUSH=0
    GH_REPO=""
    GH_BRANCH=""
    GH_MODE=0

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --help|-h)
                show_help
                ;;
            --bootstrap)
                BOOTSTRAP_MODE=1
                shift
                ;;
            --yes|-y)
                # shellcheck disable=SC2034
                YES_MODE=1
                shift
                ;;
            --force|-f)
                # shellcheck disable=SC2034
                FORCE_PUSH=1
                shift
                ;;
            --open)
                shift
                OPEN_MODE="${1:-cursor}"
                if [[ "$OPEN_MODE" != "auto" && "$OPEN_MODE" != "cursor" && "$OPEN_MODE" != "code" && "$OPEN_MODE" != "ssh" && "$OPEN_MODE" != "none" ]]; then
                    log_error "--open must be auto, cursor, code, ssh, or none"
                    exit 1
                fi
                shift
                ;;
            -*)
                log_error "Unknown option: $1"
                echo "Use --help for usage information"
                exit 1
                ;;
            gh:*)
                # gh:org/repo or gh:org/repo:branch
                local gh_target="${1#gh:}"
                if [[ -z "$gh_target" || "$gh_target" != */* ]]; then
                    log_error "Invalid gh: target. Use gh:org/repo or gh:org/repo:branch"
                    exit 1
                fi
                # shellcheck disable=SC2034
                GH_MODE=1
                # Split on first colon after org/repo (branch may contain slashes)
                if [[ "$gh_target" =~ ^([^:]+):(.+)$ ]]; then
                    # shellcheck disable=SC2034
                    GH_REPO="${BASH_REMATCH[1]}"
                    # shellcheck disable=SC2034
                    GH_BRANCH="${BASH_REMATCH[2]}"
                else
                    # shellcheck disable=SC2034
                    GH_REPO="$gh_target"
                fi
                shift
                ;;
            *)
                if [[ -n "$SSH_HOST" ]]; then
                    log_error "Unexpected argument: $1"
                    exit 1
                fi
                # Parse SSH-style format: user@host:path or host:path
                if [[ "$1" =~ ^([^:]+):(.+)$ ]]; then
                    SSH_HOST="${BASH_REMATCH[1]}"
                    REMOTE_PATH="${BASH_REMATCH[2]}"
                else
                    SSH_HOST="$1"
                    # Default to ~ (expanded by remote shell) if no path specified
                    REMOTE_PATH="~"
                fi
                shift
                ;;
        esac
    done

    if [[ -z "$SSH_HOST" ]]; then
        log_error "Missing required argument: <ssh-host>[:<remote-path>]"
        echo "Use --help for usage information"
        exit 1
    fi
}

check_unpushed_commits() {
    # Only relevant when deploying a gh: target from a local repo
    [[ "$GH_MODE" == "1" ]] || return 0

    # Check if we're in a git repo
    if ! git rev-parse --is-inside-work-tree &>/dev/null; then
        return 0
    fi

    local branch upstream ahead
    branch=$(git branch --show-current 2>/dev/null)
    [[ -n "$branch" ]] || return 0

    upstream=$(git rev-parse --abbrev-ref "@{upstream}" 2>/dev/null) || {
        log_warning "Branch '$branch' has no upstream. Push with: git push -u origin $branch"
        if [[ "$FORCE_PUSH" == "1" ]]; then
            log_info "Pushing $branch to origin..."
            git push -u origin "$branch"
            log_success "Pushed $branch"
            return 0
        fi
        exit 1
    }

    ahead=$(git rev-list --count "$upstream..HEAD" 2>/dev/null || echo 0)
    if [[ "$ahead" -gt 0 ]]; then
        if [[ "$FORCE_PUSH" == "1" ]]; then
            log_info "Pushing $ahead commit(s) on $branch to origin..."
            git push
            log_success "Pushed $ahead commit(s)"
        else
            log_error "$ahead unpushed commit(s) on $branch. Push first or use --force."
            exit 1
        fi
    fi
}

detect_editor_cli() {
    if [[ "$OPEN_MODE" == "none" || "$OPEN_MODE" == "ssh" ]]; then
        EDITOR_CLI=""
        return
    fi

    # Auto-detect: check TERM_PROGRAM, then fall back to CLI availability
    if [[ "$OPEN_MODE" == "auto" ]]; then
        case "${TERM_PROGRAM:-}" in
            cursor|Cursor)
                OPEN_MODE="cursor" ;;
            vscode|VSCode)
                OPEN_MODE="code" ;;
            WezTerm|iTerm*|Apple_Terminal|tmux)
                # Terminal app — no devcontainer protocol, default to ssh
                OPEN_MODE="ssh" ;;
        esac
    fi

    # Still auto? Fall back to CLI availability
    if [[ "$OPEN_MODE" == "auto" ]]; then
        if command -v cursor &>/dev/null; then
            OPEN_MODE="cursor"
        elif command -v code &>/dev/null; then
            OPEN_MODE="code"
        else
            OPEN_MODE="ssh"
            log_info "No IDE CLI found, falling back to --open ssh"
        fi
    fi

    if [[ "$OPEN_MODE" == "cursor" ]]; then
        if command -v cursor &>/dev/null; then
            EDITOR_CLI="cursor"
        else
            log_error "cursor CLI not found. Install Cursor and enable the shell command, or use --open code|ssh|none."
            exit 1
        fi
    elif [[ "$OPEN_MODE" == "code" ]]; then
        if command -v code &>/dev/null; then
            EDITOR_CLI="code"
        else
            log_error "code CLI not found. Install VS Code and enable the shell command, or use --open cursor|ssh|none."
            exit 1
        fi
    fi
}

# ═══════════════════════════════════════════════════════════════════════════════
# TAILSCALE KEY INJECTION (opt-in via TS_CLIENT_ID + TS_CLIENT_SECRET)
# ═══════════════════════════════════════════════════════════════════════════════

inject_tailscale_key() {
    # Resolve credentials: env var → macOS keychain → skip
    if [[ -z "${TS_CLIENT_ID:-}" ]]; then
        TS_CLIENT_ID=$(security find-generic-password -a tailscale-oauth -s TS_CLIENT_ID -w 2>/dev/null || true)
    fi
    if [[ -z "${TS_CLIENT_SECRET:-}" ]]; then
        TS_CLIENT_SECRET=$(security find-generic-password -a tailscale-oauth -s TS_CLIENT_SECRET -w 2>/dev/null || true)
    fi
    if [[ -z "${TS_CLIENT_ID:-}" || -z "${TS_CLIENT_SECRET:-}" ]]; then
        return 0
    fi

    # Always regenerate — ephemeral keys may have expired since last deploy.

    # Verify local prerequisites
    if ! command -v curl &>/dev/null || ! command -v jq &>/dev/null; then
        log_warning "Tailscale: curl and jq required for key generation, skipping"
        return 0
    fi

    log_info "Tailscale: generating ephemeral auth key..."

    # Get OAuth access token
    local token_response token
    token_response=$(curl -s -f \
        -d "client_id=$TS_CLIENT_ID" \
        -d "client_secret=$TS_CLIENT_SECRET" \
        "https://api.tailscale.com/api/v2/oauth/token" 2>&1) || {
        log_warning "Tailscale: failed to get OAuth token, skipping"
        return 0
    }
    token=$(echo "$token_response" | jq -r '.access_token // empty')
    if [[ -z "$token" ]]; then
        log_warning "Tailscale: empty access token, skipping"
        return 0
    fi

    # Create ephemeral, non-reusable auth key
    local key_response auth_key
    key_response=$(curl -s -f -X POST \
        -H "Authorization: Bearer $token" \
        -H "Content-Type: application/json" \
        -d '{
            "capabilities": {
                "devices": {
                    "create": {
                        "reusable": false,
                        "ephemeral": true,
                        "tags": ["tag:devc"]
                    }
                }
            }
        }' \
        "https://api.tailscale.com/api/v2/tailnet/-/keys" 2>&1) || {
        log_warning "Tailscale: failed to create auth key, skipping"
        return 0
    }
    auth_key=$(echo "$key_response" | jq -r '.key // empty')
    if [[ -z "$auth_key" ]]; then
        local err_msg
        err_msg=$(echo "$key_response" | jq -r '.message // empty')
        log_warning "Tailscale: API error: ${err_msg:-unknown}, skipping"
        return 0
    fi

    # Inject into remote docker-compose.local.yaml
    # Includes devices + cap_add for real TUN (required for Tailscale SSH)
    # shellcheck disable=SC2029
    ssh "$SSH_HOST" "bash -s" "$REMOTE_PATH" "$auth_key" << 'INJECT_EOF'
REPO_PATH="$1"
AUTH_KEY="$2"
LOCAL_YAML="$REPO_PATH/.devcontainer/docker-compose.local.yaml"

# Full Tailscale block with TUN device + capabilities for SSH support
write_full_ts_yaml() {
    cat > "$LOCAL_YAML" << YAML
services:
  devcontainer:
    devices:
      - /dev/net/tun:/dev/net/tun
    cap_add:
      - NET_ADMIN
      - NET_RAW
    environment:
      - TAILSCALE_AUTHKEY=${AUTH_KEY}
YAML
}

# Create if missing
if [ ! -f "$LOCAL_YAML" ]; then
    write_full_ts_yaml
elif grep -q 'services: {}' "$LOCAL_YAML"; then
    write_full_ts_yaml
elif grep -q 'TAILSCALE_AUTHKEY' "$LOCAL_YAML"; then
    # Update existing key, ensure devices/cap_add present
    sed -i "s|TAILSCALE_AUTHKEY=.*|TAILSCALE_AUTHKEY=${AUTH_KEY}|" "$LOCAL_YAML"
    if ! grep -q '/dev/net/tun' "$LOCAL_YAML"; then
        sed -i "/devcontainer:/a\\    devices:\\n      - /dev/net/tun:/dev/net/tun\\n    cap_add:\\n      - NET_ADMIN\\n      - NET_RAW" "$LOCAL_YAML"
    fi
else
    write_full_ts_yaml
fi
INJECT_EOF

    log_success "Tailscale: ephemeral auth key injected into remote compose"
}

# ═══════════════════════════════════════════════════════════════════════════════
# CLAUDE CODE AUTH INJECTION (opt-in via CLAUDE_CODE_OAUTH_TOKEN)
# ═══════════════════════════════════════════════════════════════════════════════

inject_claude_auth() {
    # Resolve token: env var → macOS keychain → skip
    if [[ -z "${CLAUDE_CODE_OAUTH_TOKEN:-}" ]]; then
        CLAUDE_CODE_OAUTH_TOKEN=$(security find-generic-password -s devc-remote -a CLAUDE_CODE_OAUTH_TOKEN -w 2>/dev/null || true)
    fi
    if [[ -z "${CLAUDE_CODE_OAUTH_TOKEN:-}" ]]; then
        return 0
    fi

    # Check if token already set on remote
    # shellcheck disable=SC2029
    if ssh "$SSH_HOST" "grep -q 'CLAUDE_CODE_OAUTH_TOKEN' '$REMOTE_PATH/.devcontainer/docker-compose.local.yaml' 2>/dev/null"; then
        log_info "Claude: OAuth token already configured on remote"
        return 0
    fi

    log_info "Claude: injecting OAuth token into remote compose..."

    # shellcheck disable=SC2029
    ssh "$SSH_HOST" "bash -s" "$REMOTE_PATH" "$CLAUDE_CODE_OAUTH_TOKEN" << 'INJECT_EOF'
REPO_PATH="$1"
TOKEN="$2"
LOCAL_YAML="$REPO_PATH/.devcontainer/docker-compose.local.yaml"

# Create if missing
if [ ! -f "$LOCAL_YAML" ]; then
    cat > "$LOCAL_YAML" << YAML
services:
  devcontainer:
    environment:
      - CLAUDE_CODE_OAUTH_TOKEN=${TOKEN}
YAML
elif grep -q 'services: {}' "$LOCAL_YAML"; then
    cat > "$LOCAL_YAML" << YAML
services:
  devcontainer:
    environment:
      - CLAUDE_CODE_OAUTH_TOKEN=${TOKEN}
YAML
elif grep -q 'CLAUDE_CODE_OAUTH_TOKEN' "$LOCAL_YAML"; then
    sed -i "s|CLAUDE_CODE_OAUTH_TOKEN=.*|CLAUDE_CODE_OAUTH_TOKEN=${TOKEN}|" "$LOCAL_YAML"
elif grep -q 'environment:' "$LOCAL_YAML"; then
    sed -i "/environment:/a\\      - CLAUDE_CODE_OAUTH_TOKEN=${TOKEN}" "$LOCAL_YAML"
elif grep -q 'devcontainer:' "$LOCAL_YAML"; then
    sed -i "/devcontainer:/a\\    environment:\\n      - CLAUDE_CODE_OAUTH_TOKEN=${TOKEN}" "$LOCAL_YAML"
else
    cat > "$LOCAL_YAML" << YAML
services:
  devcontainer:
    environment:
      - CLAUDE_CODE_OAUTH_TOKEN=${TOKEN}
YAML
fi
INJECT_EOF

    log_success "Claude: OAuth token injected into remote compose"
}

check_ssh() {
    if ! ssh -o ConnectTimeout=5 -o BatchMode=yes "$SSH_HOST" true 2>/dev/null; then
        log_error "Cannot connect to $SSH_HOST. Check your SSH config and network."
        exit 1
    fi
}

remote_clone_project() {
    [[ "$GH_MODE" == "1" ]] || return 0

    log_info "Cloning $GH_REPO on $SSH_HOST..."

    local clone_output
    # shellcheck disable=SC2029
    # Use sentinels for empty/default args — SSH drops empty strings and expands ~
    local _branch="${GH_BRANCH:-_NONE_}"
    local _path="${REMOTE_PATH}"
    [[ "$_path" == "~" ]] && _path="_DEFAULT_"
    # shellcheck disable=SC2029
    clone_output=$(ssh "$SSH_HOST" "bash -s" "$GH_REPO" "$_branch" "$_path" << 'CLONEEOF'
GH_REPO="$1"
GH_BRANCH="$2"
[ "$GH_BRANCH" = "_NONE_" ] && GH_BRANCH=""
USER_PATH="$3"
[ "$USER_PATH" = "_DEFAULT_" ] && USER_PATH=""
REPO_NAME="${GH_REPO##*/}"

# Resolve target directory
if [ -n "$USER_PATH" ]; then
    TARGET_DIR="$USER_PATH"
else
    # Read projects_dir from config, fallback to ~/Projects
    PROJECTS_DIR="$HOME/Projects"
    CONFIG_FILE="$HOME/.config/devc-remote/config.yaml"
    if [ -f "$CONFIG_FILE" ]; then
        CONFIGURED_DIR=$(sed -n 's/^projects_dir: *//p' "$CONFIG_FILE")
        [ -n "$CONFIGURED_DIR" ] && PROJECTS_DIR="${CONFIGURED_DIR/#\~/$HOME}"
    fi
    TARGET_DIR="$PROJECTS_DIR/$REPO_NAME"
fi

# Clone or fetch
CLONE_STATUS="fetched"
if [ ! -d "$TARGET_DIR/.git" ]; then
    git clone "https://github.com/${GH_REPO}.git" "$TARGET_DIR"
    CLONE_STATUS="cloned"
else
    cd "$TARGET_DIR" && git fetch
fi

# Checkout branch if specified
if [ -n "$GH_BRANCH" ]; then
    cd "$TARGET_DIR" && git checkout "$GH_BRANCH"
    echo "CLONE_BRANCH=$GH_BRANCH"
fi

echo "CLONE_PATH=$TARGET_DIR"
echo "CLONE_STATUS=$CLONE_STATUS"
CLONEEOF
    )

    local clone_path="" clone_status="" clone_branch=""
    while IFS= read -r line; do
        [[ "$line" =~ ^([A-Z_]+)=(.*)$ ]] || continue
        case "${BASH_REMATCH[1]}" in
            CLONE_PATH) clone_path="${BASH_REMATCH[2]}" ;;
            CLONE_STATUS) clone_status="${BASH_REMATCH[2]}" ;;
            CLONE_BRANCH) clone_branch="${BASH_REMATCH[2]}" ;;
        esac
    done <<< "$clone_output"

    if [[ -n "$clone_path" ]]; then
        REMOTE_PATH="$clone_path"
    fi

    if [[ "$clone_status" == "cloned" ]]; then
        log_success "Cloning $GH_REPO — cloned to $clone_path"
    else
        log_success "Fetching $GH_REPO — updated at $clone_path"
    fi

    if [[ -n "$clone_branch" ]]; then
        log_success "Checked out $clone_branch"
    fi
}

remote_preflight() {
    local preflight_output
    # shellcheck disable=SC2029
    preflight_output=$(ssh "$SSH_HOST" "bash -s" "$REMOTE_PATH" << 'REMOTEEOF'
REPO_PATH="${1:-$HOME}"
if command -v podman &>/dev/null; then
    echo "RUNTIME=podman"
elif command -v docker &>/dev/null; then
    echo "RUNTIME=docker"
else
    echo "RUNTIME="
fi
if (command -v podman &>/dev/null && podman compose version &>/dev/null) || \
   (command -v docker &>/dev/null && docker compose version &>/dev/null); then
    echo "COMPOSE_AVAILABLE=1"
else
    echo "COMPOSE_AVAILABLE=0"
fi
if [ -d "$REPO_PATH" ]; then
    echo "REPO_PATH_EXISTS=1"
else
    echo "REPO_PATH_EXISTS=0"
fi
if [ -d "$REPO_PATH/.devcontainer" ]; then
    echo "DEVCONTAINER_EXISTS=1"
else
    echo "DEVCONTAINER_EXISTS=0"
fi
AVAIL_GB=$(df -BG "$REPO_PATH" 2>/dev/null | awk 'NR==2 {gsub(/G/,""); print $4}')
echo "DISK_AVAILABLE_GB=${AVAIL_GB:-0}"
if [ "$(uname -s)" = "Darwin" ]; then
    echo "OS_TYPE=macos"
else
    echo "OS_TYPE=linux"
fi
# Detect container socket path
if [ -S /var/run/docker.sock ]; then
    echo "SOCKET_PATH=/var/run/docker.sock"
elif [ -S "/run/user/$(id -u)/podman/podman.sock" ]; then
    echo "SOCKET_PATH=/run/user/$(id -u)/podman/podman.sock"
else
    echo "SOCKET_PATH="
fi
REMOTEEOF
    )

    while IFS= read -r line; do
        [[ "$line" =~ ^([A-Z_]+)=(.*)$ ]] || continue
        case "${BASH_REMATCH[1]}" in
            RUNTIME) RUNTIME="${BASH_REMATCH[2]}" ;;
            COMPOSE_AVAILABLE) COMPOSE_AVAILABLE="${BASH_REMATCH[2]}" ;;
            REPO_PATH_EXISTS) REPO_PATH_EXISTS="${BASH_REMATCH[2]}" ;;
            DEVCONTAINER_EXISTS) DEVCONTAINER_EXISTS="${BASH_REMATCH[2]}" ;;
            DISK_AVAILABLE_GB) DISK_AVAILABLE_GB="${BASH_REMATCH[2]}" ;;
            OS_TYPE) OS_TYPE="${BASH_REMATCH[2]}" ;;
            SOCKET_PATH) SOCKET_PATH="${BASH_REMATCH[2]}" ;;
        esac
    done <<< "$preflight_output"

    if [[ -z "${RUNTIME:-}" ]]; then
        log_error "No container runtime found on $SSH_HOST. Install podman or docker."
        exit 1
    fi
    if [[ "$RUNTIME" == "podman" ]]; then
        COMPOSE_CMD="podman compose"
    else
        COMPOSE_CMD="docker compose"
    fi
    if [[ "${COMPOSE_AVAILABLE:-0}" != "1" ]]; then
        log_error "Compose not available on $SSH_HOST. Install docker-compose or podman-compose."
        exit 1
    fi
    if [[ "${REPO_PATH_EXISTS:-0}" != "1" ]]; then
        log_error "Repository not found at $REMOTE_PATH on $SSH_HOST."
        exit 1
    fi
    if [[ "${DEVCONTAINER_EXISTS:-0}" != "1" ]]; then
        log_error "No .devcontainer/ found in $REMOTE_PATH. Is this a devcontainer-enabled project?"
        exit 1
    fi
    if [[ "${DISK_AVAILABLE_GB:-0}" -lt 2 ]] 2>/dev/null; then
        log_warning "Low disk space on $SSH_HOST (${DISK_AVAILABLE_GB:-0}GB). At least 2GB recommended."
    fi
    if [[ "${OS_TYPE:-}" == "macos" ]]; then
        log_warning "Remote host is macOS. Devcontainer support may be limited."
    fi
}

prepare_remote() {
    local devc_dir="$REMOTE_PATH/.devcontainer"

    # Write container socket path to .env for compose interpolation
    if [[ -n "${SOCKET_PATH:-}" ]]; then
        # shellcheck disable=SC2029
        ssh "$SSH_HOST" "echo 'CONTAINER_SOCKET_PATH=$SOCKET_PATH' > $devc_dir/.env"
        log_info "Container socket: $SOCKET_PATH"
    fi

    # Create stub docker-compose.local.yaml if missing
    # shellcheck disable=SC2029
    ssh "$SSH_HOST" "test -f $devc_dir/docker-compose.local.yaml || echo -e '---\nservices: {}' > $devc_dir/docker-compose.local.yaml"
}

read_compose_files() {
    # Read dockerComposeFile array from devcontainer.json on remote host
    local raw
    # shellcheck disable=SC2029
    # shellcheck disable=SC2029
    raw=$(ssh "$SSH_HOST" \
        "python3 -c \"
import json, os, sys
path = os.path.expanduser('${REMOTE_PATH}/.devcontainer/devcontainer.json')
with open(path) as f:
    data = json.load(f)
files = data.get('dockerComposeFile', ['docker-compose.yml'])
if isinstance(files, str):
    files = [files]
for f in files:
    print(f)
\" 2>/dev/null" || echo "")
    if [[ -z "$raw" ]]; then
        echo "docker-compose.yml"
        return
    fi
    echo "$raw"
}

compose_cmd_with_files() {
    # Build compose command with -f flags for each compose file
    local cmd="$COMPOSE_CMD"
    local file
    while IFS= read -r file; do
        [[ -n "$file" ]] && cmd="$cmd -f $file"
    done < <(read_compose_files)
    echo "$cmd"
}

remote_compose_up() {
    local ps_output state health compose_full
    compose_full=$(compose_cmd_with_files)
    local devc_dir="$REMOTE_PATH/.devcontainer"

    # shellcheck disable=SC2029
    ps_output=$(ssh "$SSH_HOST" "cd $devc_dir && $compose_full ps --format json 2>/dev/null" || true)
    state=$(echo "$ps_output" | grep -o '"State":"[^"]*"' | head -1 | cut -d'"' -f4 || true)
    # shellcheck disable=SC2034
    health=$(echo "$ps_output" | grep -o '"Health":"[^"]*"' | head -1 | cut -d'"' -f4 || true)

    log_info "Starting devcontainer on $SSH_HOST..."
    # Always run compose up -d: it's idempotent and auto-recreates if config changed.
    # shellcheck disable=SC2029
    if ! ssh "$SSH_HOST" "cd $devc_dir && $compose_full up -d"; then
        log_error "Failed to start devcontainer on $SSH_HOST."
        log_error "Debug with: ssh $SSH_HOST 'cd $devc_dir && $compose_full logs'"
        exit 1
    fi
    sleep 2

    if [[ "$state" == "running" ]]; then
        CONTAINER_FRESH=0  # was already running, lifecycle scripts already ran
    else
        CONTAINER_FRESH=1
    fi
}

run_container_lifecycle() {
    local compose_full devc_dir workspace_folder scripts_dir
    compose_full=$(compose_cmd_with_files)
    devc_dir="$REMOTE_PATH/.devcontainer"
    workspace_folder=$(read_workspace_folder)
    scripts_dir="$workspace_folder/.devcontainer/scripts"

    local has_scripts
    # shellcheck disable=SC2029
    has_scripts=$(ssh "$SSH_HOST" "cd $devc_dir && $compose_full exec -T devcontainer \
        test -f $scripts_dir/post-create.sh && echo 1 || echo 0" 2>/dev/null || echo "0")

    if [[ "$has_scripts" != "1" ]]; then
        log_info "No lifecycle scripts found at $scripts_dir — skipping"
        return 0
    fi

    # post-create: one-time setup (git, precommit, tailscale install, deps)
    if [[ "${CONTAINER_FRESH:-0}" == "1" ]]; then
        log_info "Running post-create lifecycle (first start)..."
        # shellcheck disable=SC2029
        ssh "$SSH_HOST" "cd $devc_dir && $compose_full exec -T devcontainer \
            /bin/bash $scripts_dir/post-create.sh" 2>&1 || {
            log_warning "post-create.sh failed (non-fatal, container still running)"
        }
    fi

    # post-start: every-start setup (socket perms, deps sync, tailscale start)
    local has_post_start
    # shellcheck disable=SC2029
    has_post_start=$(ssh "$SSH_HOST" "cd $devc_dir && $compose_full exec -T devcontainer \
        test -f $scripts_dir/post-start.sh && echo 1 || echo 0" 2>/dev/null || echo "0")

    if [[ "$has_post_start" == "1" ]]; then
        log_info "Running post-start lifecycle..."
        # shellcheck disable=SC2029
        ssh "$SSH_HOST" "cd $devc_dir && $compose_full exec -T devcontainer \
            /bin/bash $scripts_dir/post-start.sh" 2>&1 || {
            log_warning "post-start.sh failed (non-fatal, container still running)"
        }
    fi
}

read_workspace_folder() {
    # Read workspaceFolder from devcontainer.json on remote host
    local folder
    # shellcheck disable=SC2029
    folder=$(ssh "$SSH_HOST" \
        "grep -o '\"workspaceFolder\"[[:space:]]*:[[:space:]]*\"[^\"]*\"' \
         ${REMOTE_PATH}/.devcontainer/devcontainer.json 2>/dev/null" \
        | sed 's/.*: *"//;s/"//' || echo "/workspace")
    echo "${folder:-/workspace}"
}

open_editor() {
    local container_workspace uri
    container_workspace=$(read_workspace_folder)

    # Build URI using Python helper
    uri=$(python3 "$SCRIPT_DIR/devc_remote_uri.py" \
        "$REMOTE_PATH" \
        "$SSH_HOST" \
        "$container_workspace")

    "$EDITOR_CLI" --folder-uri "$uri"
}

# ═══════════════════════════════════════════════════════════════════════════════
# TAILSCALE WAIT + SSH OUTPUT
# ═══════════════════════════════════════════════════════════════════════════════

check_local_tailscale() {
    if ! command -v tailscale &>/dev/null; then
        log_error "tailscale CLI not found locally. Install Tailscale to use --open ssh."
        exit 1
    fi

    local ts_status backend_state self_online
    ts_status=$(tailscale status --json 2>/dev/null) || {
        log_error "Tailscale: cannot query local daemon. Is Tailscale running?"
        exit 1
    }
    backend_state=$(echo "$ts_status" | python3 -c "import json,sys; print(json.load(sys.stdin).get('BackendState',''))" 2>/dev/null)
    self_online=$(echo "$ts_status" | python3 -c "import json,sys; print(json.load(sys.stdin).get('Self',{}).get('Online',False))" 2>/dev/null)

    if [[ "$backend_state" != "Running" ]]; then
        log_error "Tailscale: local daemon state is '$backend_state' (expected 'Running'). Start Tailscale first."
        exit 1
    fi
    if [[ "$self_online" != "True" ]]; then
        log_error "Tailscale: local node is offline. Reconnect with: tailscale up"
        exit 1
    fi
    log_success "Tailscale: local client healthy (state=$backend_state)"
}

wait_for_tailscale() {
    check_local_tailscale

    # Derive expected hostname pattern from devcontainer.json name field
    local devc_name
    # shellcheck disable=SC2029
    devc_name=$(ssh "$SSH_HOST" \
        "python3 -c \"import json,sys; print(json.load(sys.stdin).get('name',''))\" \
         < ${REMOTE_PATH}/.devcontainer/devcontainer.json 2>/dev/null" || true)
    devc_name=$(sanitize_dns_label "${devc_name:-devc}")

    log_info "Tailscale: waiting for container to join tailnet (pattern: *${devc_name}*)..."

    local ip hostname
    for _ in $(seq 1 30); do
        # Query local tailscale for peers matching the devc hostname pattern
        local ts_status
        ts_status=$(tailscale status --json 2>/dev/null || true)
        if [[ -n "$ts_status" ]]; then
            # Find an online peer whose hostname contains the devc name
            local match
            match=$(echo "$ts_status" | python3 -c "
import json, sys
data = json.load(sys.stdin)
for peer in (data.get('Peer') or {}).values():
    if peer.get('Online') and '${devc_name}' in peer.get('HostName', ''):
        ips = peer.get('TailscaleIPs', [])
        print(peer['HostName'] + ' ' + (ips[0] if ips else ''))
        break
" 2>/dev/null || true)

            if [[ -n "$match" ]]; then
                hostname="${match%% *}"
                ip="${match#* }"
                log_success "Tailscale: container online as ${hostname} (${ip})"
                # Output connection info to stdout (for scripting)
                echo ""
                echo "Connect via:"
                echo "  ssh root@${hostname}"
                echo "  ssh root@${ip}"
                echo ""
                echo "Cursor:  cursor --remote ssh-remote+root@${hostname} $(read_workspace_folder)"
                echo "VS Code: code --remote ssh-remote+root@${hostname} $(read_workspace_folder)"
                return 0
            fi
        fi
        sleep 2
    done

    log_warning "Tailscale: container did not appear on tailnet within 60s"
    log_warning "Check that TAILSCALE_AUTHKEY is set and Tailscale ACLs allow SSH"
    return 1
}

# ═══════════════════════════════════════════════════════════════════════════════
# BOOTSTRAP (one-time remote host setup)
# ═══════════════════════════════════════════════════════════════════════════════

bootstrap_check_config() {
    # Check if config exists on remote, read values if so
    local config_output
    # shellcheck disable=SC2029
    config_output=$(ssh "$SSH_HOST" "bash -s" << 'CFGEOF'
CONFIG_DIR="$HOME/.config/devc-remote"
CONFIG_FILE="$CONFIG_DIR/config.yaml"
if [ -f "$CONFIG_FILE" ]; then
    echo "CONFIG_EXISTS=1"
    # Parse simple flat YAML (key: value) using sed
    sed -n 's/^projects_dir: *//p'      "$CONFIG_FILE" | while read -r v; do echo "PROJECTS_DIR=$v"; done
    sed -n 's/^devcontainer_repo: *//p'  "$CONFIG_FILE" | while read -r v; do echo "DEVCONTAINER_REPO=$v"; done
    sed -n 's/^devcontainer_path: *//p'  "$CONFIG_FILE" | while read -r v; do echo "DEVCONTAINER_PATH=$v"; done
    sed -n 's/^image_tag: *//p'          "$CONFIG_FILE" | while read -r v; do echo "IMAGE_TAG=$v"; done
    sed -n 's/^registry: *//p'           "$CONFIG_FILE" | while read -r v; do echo "REGISTRY=$v"; done
else
    echo "CONFIG_EXISTS=0"
fi
CFGEOF
    )

    CONFIG_EXISTS=0
    while IFS= read -r line; do
        [[ "$line" =~ ^([A-Z_]+)=(.*)$ ]] || continue
        case "${BASH_REMATCH[1]}" in
            CONFIG_EXISTS)      CONFIG_EXISTS="${BASH_REMATCH[2]}" ;;
            PROJECTS_DIR)       BOOTSTRAP_PROJECTS_DIR="${BASH_REMATCH[2]}" ;;
            DEVCONTAINER_REPO)  BOOTSTRAP_DEVC_REPO="${BASH_REMATCH[2]}" ;;
            DEVCONTAINER_PATH)  BOOTSTRAP_DEVC_PATH="${BASH_REMATCH[2]}" ;;
            IMAGE_TAG)          BOOTSTRAP_IMAGE_TAG="${BASH_REMATCH[2]}" ;;
            REGISTRY)           BOOTSTRAP_REGISTRY="${BASH_REMATCH[2]}" ;;
        esac
    done <<< "$config_output"
}

bootstrap_prompt_config() {
    # Set defaults
    BOOTSTRAP_PROJECTS_DIR="${BOOTSTRAP_PROJECTS_DIR:-~/Projects}"
    BOOTSTRAP_DEVC_REPO="${BOOTSTRAP_DEVC_REPO:-vig-os/devcontainer}"
    BOOTSTRAP_IMAGE_TAG="${BOOTSTRAP_IMAGE_TAG:-dev}"
    BOOTSTRAP_REGISTRY="${BOOTSTRAP_REGISTRY:-ghcr.io/vig-os/devcontainer}"

    if [[ "$YES_MODE" == "0" ]]; then
        log_info "No devc-remote config found on $SSH_HOST."
        read -rp "Where should projects be cloned? [$BOOTSTRAP_PROJECTS_DIR]: " user_input
        BOOTSTRAP_PROJECTS_DIR="${user_input:-$BOOTSTRAP_PROJECTS_DIR}"
    fi

    # Derive devcontainer_path from projects_dir
    BOOTSTRAP_DEVC_PATH="${BOOTSTRAP_PROJECTS_DIR}/devcontainer"
}

bootstrap_write_config() {
    # Write config file on remote
    # shellcheck disable=SC2029
    ssh "$SSH_HOST" "bash -s" "$BOOTSTRAP_PROJECTS_DIR" "$BOOTSTRAP_DEVC_REPO" "$BOOTSTRAP_DEVC_PATH" "$BOOTSTRAP_IMAGE_TAG" "$BOOTSTRAP_REGISTRY" << 'WRITEEOF'
PROJECTS_DIR="$1"
DEVC_REPO="$2"
DEVC_PATH="$3"
IMAGE_TAG="$4"
REGISTRY="$5"
CONFIG_DIR="$HOME/.config/devc-remote"
CONFIG_FILE="$CONFIG_DIR/config.yaml"
mkdir -p "$CONFIG_DIR"
cat > "$CONFIG_FILE" << YAML
projects_dir: ${PROJECTS_DIR}
devcontainer_repo: ${DEVC_REPO}
devcontainer_path: ${DEVC_PATH}
image_tag: ${IMAGE_TAG}
registry: ${REGISTRY}
YAML
WRITEEOF

    log_success "Config written to ~/.config/devc-remote/config.yaml — edit to customize."
}

forward_ghcr_auth() {
    # Forward container registry credentials to remote
    local local_auth=""

    # Check podman auth first, then docker
    if [[ -f "${HOME}/.config/containers/auth.json" ]]; then
        local_auth="${HOME}/.config/containers/auth.json"
    elif [[ -f "${HOME}/.docker/config.json" ]]; then
        local_auth="${HOME}/.docker/config.json"
    elif [[ -n "${GHCR_TOKEN:-}" ]]; then
        # Use token-based auth — create temp auth file
        local tmp_auth
        tmp_auth="$(mktemp)"
        echo "{\"auths\":{\"ghcr.io\":{\"auth\":\"$(echo -n "token:${GHCR_TOKEN}" | base64)\"}}}" > "$tmp_auth"
        local_auth="$tmp_auth"
    fi

    if [[ -z "$local_auth" ]]; then
        log_warning "GHCR auth: no local credentials found, skipping"
        return 0
    fi

    # Ensure remote directories exist and copy auth file
    # shellcheck disable=SC2029
    ssh "$SSH_HOST" "mkdir -p ~/.config/containers ~/.docker"
    scp -q "$local_auth" "$SSH_HOST:~/.config/containers/auth.json"
    scp -q "$local_auth" "$SSH_HOST:~/.docker/config.json"

    # Clean up temp file if we created one
    if [[ -n "${GHCR_TOKEN:-}" && -n "${tmp_auth:-}" ]]; then
        rm -f "$tmp_auth"
    fi

    log_success "GHCR auth forwarded to $SSH_HOST"
}

bootstrap_clone_and_build() {
    log_info "Building devcontainer image on $SSH_HOST..."
    # shellcheck disable=SC2029
    ssh "$SSH_HOST" "bash -s" "$BOOTSTRAP_DEVC_REPO" "$BOOTSTRAP_DEVC_PATH" "$BOOTSTRAP_IMAGE_TAG" "$BOOTSTRAP_REGISTRY" << 'BUILDEOF'
DEVC_REPO="$1"
DEVC_PATH="$2"
IMAGE_TAG="$3"
REGISTRY="$4"

# Ensure ~/.local/bin is in PATH (uv, etc.)
export PATH="$HOME/.local/bin:$PATH"

# Expand ~ in DEVC_PATH
DEVC_PATH="${DEVC_PATH/#\~/$HOME}"

if [ -d "$DEVC_PATH/.git" ]; then
    echo "Repository exists, pulling latest..."
    cd "$DEVC_PATH" && git pull
else
    echo "Cloning $DEVC_REPO..."
    # Expand ~ in parent dir
    PARENT_DIR="$(dirname "$DEVC_PATH")"
    mkdir -p "$PARENT_DIR"
    cd "$PARENT_DIR"
    git clone "https://github.com/${DEVC_REPO}.git" "$(basename "$DEVC_PATH")"
    cd "$DEVC_PATH"
fi

# Build the image
if [ -f "scripts/build.sh" ]; then
    echo "Running scripts/build.sh..."
    bash scripts/build.sh
else
    echo "WARNING: scripts/build.sh not found in $DEVC_PATH"
fi
BUILDEOF

    log_success "Devcontainer image built on $SSH_HOST"
}

bootstrap_remote() {
    log_info "Bootstrap: checking remote config on $SSH_HOST..."
    bootstrap_check_config

    if [[ "$CONFIG_EXISTS" == "1" ]]; then
        log_info "Config: ~/.config/devc-remote/config.yaml (existing, not modified)"
    else
        bootstrap_prompt_config
        bootstrap_write_config
    fi

    forward_ghcr_auth
    bootstrap_clone_and_build

    log_success "Bootstrap complete for $SSH_HOST"
}

# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

main() {
    parse_args "$@"
    CONTAINER_FRESH=0

    # Bootstrap mode: one-time remote host setup
    if [[ "$BOOTSTRAP_MODE" == "1" ]]; then
        log_info "Checking SSH connectivity to $SSH_HOST..."
        check_ssh
        log_success "SSH connection OK"
        bootstrap_remote
        return
    fi

    check_unpushed_commits

    detect_editor_cli
    # Fail fast: verify local Tailscale before spending time on remote setup
    if [[ "$OPEN_MODE" == "ssh" ]]; then
        check_local_tailscale
    fi
    case "$OPEN_MODE" in
        cursor|code) log_success "IDE: $EDITOR_CLI" ;;
        ssh)         log_info "Mode: SSH (wait for Tailscale, print connection info)" ;;
        none)        log_info "Mode: infra only (no IDE)" ;;
    esac

    log_info "Checking SSH connectivity to $SSH_HOST..."
    check_ssh
    log_success "SSH connection OK"

    forward_ghcr_auth

    remote_clone_project

    log_info "Running pre-flight checks on $SSH_HOST..."
    remote_preflight
    log_success "Pre-flight OK (runtime: $RUNTIME)"

    prepare_remote

    inject_tailscale_key
    inject_claude_auth

    remote_compose_up

    run_container_lifecycle

    case "$OPEN_MODE" in
        cursor|code)
            open_editor
            log_success "Done — opened $EDITOR_CLI for $SSH_HOST:$REMOTE_PATH"
            ;;
        ssh)
            wait_for_tailscale
            ;;
        none)
            log_success "Done — devcontainer running on $SSH_HOST:$REMOTE_PATH"
            ;;
    esac
}

main "$@"
