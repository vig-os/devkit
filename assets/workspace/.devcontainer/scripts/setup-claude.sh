#!/bin/bash

# Claude Code CLI setup for devcontainer — opt-in via CLAUDE_CODE_OAUTH_TOKEN env var.
#
# Subcommands:
#   install  — install Claude Code CLI + create non-root user (post-create.sh)
#   start    — ensure workspace access for claude user (post-start.sh)
#
# Both subcommands are silent no-ops when CLAUDE_CODE_OAUTH_TOKEN is unset or empty.
#
# Auth flow:
#   1. User runs `claude setup-token` on host (one-time, opens browser)
#   2. Token (sk-ant-oat01-..., valid 1 year) is injected into container env
#   3. Claude Code uses CLAUDE_CODE_OAUTH_TOKEN — no login needed in container
#
# Why a dedicated user?
#   Claude Code refuses --dangerously-skip-permissions under root for security.
#   The devcontainer runs as root, so we create a non-root 'claude' user.
#   The `claude` command is replaced with a wrapper that, when run as root,
#   auto-switches to the claude user via runuser. This means:
#     - `claude` as root → switches to claude user + --dangerously-skip-permissions
#     - `claude` as claude user → runs directly
#     - `claude-bin` → the real npm-installed binary (escape hatch)

set -euo pipefail

CLAUDE_USER="claude"
CLAUDE_HOME="/home/$CLAUDE_USER"

# ── helpers ──────────────────────────────────────────────────────────────────

require_token() {
    if [ -z "${CLAUDE_CODE_OAUTH_TOKEN:-}" ]; then
        echo "Claude: CLAUDE_CODE_OAUTH_TOKEN not set, skipping."
        return 1
    fi
    return 0
}

# ── subcommands ──────────────────────────────────────────────────────────────

cmd_install() {
    require_token || return 0

    # Install the CLI if not present (check for real binary or wrapper)
    if command -v claude-bin &>/dev/null; then
        echo "Claude: already installed, skipping install."
    elif command -v claude &>/dev/null && ! grep -q 'claude-wrapper' "$(command -v claude)" 2>/dev/null; then
        echo "Claude: already installed, skipping install."
    else
        echo "Claude: installing Claude Code CLI..."

        # Ensure Node.js LTS is available (npm required for install)
        if ! command -v npm &>/dev/null; then
            echo "Claude: installing Node.js LTS..."
            # Add nodesource repo directly (the setup_lts.x script fails with clock skew)
            local arch
            arch=$(dpkg --print-architecture 2>/dev/null || echo "amd64")
            curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key \
                | gpg --dearmor --yes -o /usr/share/keyrings/nodesource.gpg 2>/dev/null
            echo "deb [signed-by=/usr/share/keyrings/nodesource.gpg arch=$arch] https://deb.nodesource.com/node_22.x nodistro main" \
                | tee /etc/apt/sources.list.d/nodesource.list >/dev/null
            # Update all repos with clock-skew tolerance (nodesource nodejs depends on system python3)
            # apt returns 100 if any repo has clock issues — ignore since the repos we need still update
            apt-get -o Acquire::Check-Valid-Until=false update -qq 2>/dev/null || true
            apt-get install -y nodejs
        fi

        npm install -g @anthropic-ai/claude-code
        echo "Claude: CLI installed."
    fi

    # Create non-root user for --dangerously-skip-permissions
    if ! id "$CLAUDE_USER" &>/dev/null; then
        echo "Claude: creating user '$CLAUDE_USER'..."
        useradd -m -d "$CLAUDE_HOME" -s /bin/bash "$CLAUDE_USER"
    fi

    # Grant workspace access (read/write for project files)
    if command -v setfacl &>/dev/null; then
        setfacl -R -m "u:${CLAUDE_USER}:rwX" /workspace 2>/dev/null || true
        setfacl -R -d -m "u:${CLAUDE_USER}:rwX" /workspace 2>/dev/null || true
    else
        chown -R "root:${CLAUDE_USER}" /workspace 2>/dev/null || true
        chmod -R g+rwX /workspace 2>/dev/null || true
    fi

    # Replace `claude` with a wrapper that auto-switches user when root.
    # Move the real binary out of the way first.
    local real_claude
    real_claude="$(command -v claude 2>/dev/null || true)"
    if [ -n "$real_claude" ] && ! grep -q 'claude-wrapper' "$real_claude" 2>/dev/null; then
        mv "$real_claude" "${real_claude}-bin"
        # Create wrapper at the original path
        # Tag: claude-wrapper (used to detect if wrapper is already installed)
        cat > "$real_claude" << 'WRAPPER'
#!/bin/bash
# claude-wrapper: auto-switch to claude user when running as root.
# The real binary lives at claude-bin (same directory).
REAL="$(dirname "$0")/claude-bin"
# Source OAuth token from container PID 1 if not in current env (e.g. Tailscale SSH)
if [ -z "${CLAUDE_CODE_OAUTH_TOKEN:-}" ] && [ -f /proc/1/environ ]; then
    export CLAUDE_CODE_OAUTH_TOKEN=$(tr '\0' '\n' < /proc/1/environ 2>/dev/null | sed -n 's/^CLAUDE_CODE_OAUTH_TOKEN=//p')
fi
if [ "$(id -u)" = "0" ]; then
    exec runuser --pty -w CLAUDE_CODE_OAUTH_TOKEN -u claude -- "$REAL" --dangerously-skip-permissions --add-dir "$PWD" "$@"
fi
exec "$REAL" --add-dir "$PWD" "$@"
WRAPPER
        chmod +x "$real_claude"
    fi

    # Configure claude user: auto-cd to workspace project, source token
    cat > "$CLAUDE_HOME/.bashrc" << 'BASHRC'
# Auto-cd to workspace project
WS_PROJECT=$(ls -d /workspace/*/ 2>/dev/null | head -1)
if [ -n "$WS_PROJECT" ]; then
    cd "$WS_PROJECT" || true
fi

# Source OAuth token from container environment if not already set
if [ -z "${CLAUDE_CODE_OAUTH_TOKEN:-}" ] && [ -f /proc/1/environ ]; then
    CLAUDE_CODE_OAUTH_TOKEN=$(tr '\0' '\n' < /proc/1/environ 2>/dev/null | sed -n 's/^CLAUDE_CODE_OAUTH_TOKEN=//p')
    export CLAUDE_CODE_OAUTH_TOKEN
fi

export PATH="/usr/local/bin:/usr/bin:/bin:/root/.cargo/bin:$PATH"

# Claude toolkit aliases (mirrors local dev environment)
alias cl='claude'
alias cld='claude --dangerously-skip-permissions'
BASHRC
    chown "$CLAUDE_USER:$CLAUDE_USER" "$CLAUDE_HOME/.bashrc"

    # Add aliases to root's shell too (for ssh root@... sessions)
    grep -q 'alias cl=' /root/.bashrc 2>/dev/null || cat >> /root/.bashrc << 'ROOT_ALIASES'

# Claude toolkit aliases (mirrors local dev environment)
alias cl='claude'
alias cld='claude --dangerously-skip-permissions'
ROOT_ALIASES

    # Pre-configure onboarding + workspace trust so interactive TUI skips all prompts
    local ws_project
    ws_project=$(find /workspace -maxdepth 1 -mindepth 1 -type d 2>/dev/null | head -1)
    if [[ -z "$ws_project" ]]; then
        ws_project="/workspace"
    fi

    # .claude.json: onboarding state + per-project trust (keyed by absolute path)
    python3 -c "
import json, pathlib
data = {
    'hasCompletedOnboarding': True,
    'hasCompletedAuthFlow': True,
    'projects': {
        '${ws_project}': {
            'hasTrustDialogAccepted': True,
            'allowedTools': [],
            'hasCompletedProjectOnboarding': True
        },
        '/workspace': {
            'hasTrustDialogAccepted': True,
            'allowedTools': [],
            'hasCompletedProjectOnboarding': True
        }
    }
}
pathlib.Path('$CLAUDE_HOME/.claude/.claude.json').write_text(json.dumps(data, indent=2))
"
    chown "$CLAUDE_USER:$CLAUDE_USER" "$CLAUDE_HOME/.claude/.claude.json"

    # Per-project settings.json (trust dialog flag in project dir too)
    local project_key
    project_key=$(echo "$ws_project" | tr '/' '-')
    mkdir -p "$CLAUDE_HOME/.claude/projects/${project_key}"
    echo '{"hasTrustDialogAccepted": true}' > "$CLAUDE_HOME/.claude/projects/${project_key}/settings.json"
    chown -R "$CLAUDE_USER:$CLAUDE_USER" "$CLAUDE_HOME/.claude/projects/"

    # Global settings: trust workspace dirs, skip dangerous mode prompt
    cat > "$CLAUDE_HOME/.claude/settings.json" << SETTINGS
{
  "permissions": {
    "additionalDirectories": ["${ws_project}", "/workspace"]
  },
  "skipDangerousModePermissionPrompt": true
}
SETTINGS
    chown "$CLAUDE_USER:$CLAUDE_USER" "$CLAUDE_HOME/.claude/settings.json"

    echo "Claude: install complete. 'claude' auto-switches to non-root user when run as root."
}

cmd_start() {
    require_token || return 0

    # Refresh workspace access (volumes may have been recreated)
    if id "$CLAUDE_USER" &>/dev/null; then
        if command -v setfacl &>/dev/null; then
            setfacl -R -m "u:${CLAUDE_USER}:rwX" /workspace 2>/dev/null || true
            setfacl -R -d -m "u:${CLAUDE_USER}:rwX" /workspace 2>/dev/null || true
        else
            chown -R "root:${CLAUDE_USER}" /workspace 2>/dev/null || true
            chmod -R g+rwX /workspace 2>/dev/null || true
        fi
    fi

    echo "Claude: OAuth token present, CLI ready."
}

# ── main ─────────────────────────────────────────────────────────────────────

case "${1:-}" in
    install) cmd_install ;;
    start)   cmd_start ;;
    *)
        echo "Usage: $(basename "$0") {install|start}" >&2
        exit 1
        ;;
esac
