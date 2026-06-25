#!/bin/bash

# Post-create script - runs once when container is created for the first time.
# This script is called from postCreateCommand in devcontainer.json.
#
# All one-time setup belongs here:
#   - Git repo init, config, hooks
#   - SSH key + allowed-signers placement
#   - GitHub CLI config + authentication
#   - Pre-commit hook installation
#   - Dependency sync (via just)

set -euo pipefail

echo "Running post-create setup..."

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="/workspace/{{SHORT_NAME}}"

if [ ! -d "$PROJECT_ROOT" ]; then
    echo "Error: Project directory $PROJECT_ROOT does not exist"
    exit 1
fi

# One-time setup: git repo, config, hooks, gh auth
"$SCRIPT_DIR/init-git.sh"
"$SCRIPT_DIR/setup-git-conf.sh"
"$SCRIPT_DIR/setup-gh-repo.sh"
"$SCRIPT_DIR/init-precommit.sh"

# Sync dependencies (fast if nothing changed from pre-built venv)
echo "Syncing dependencies..."
just --justfile "$PROJECT_ROOT/justfile" --working-directory "$PROJECT_ROOT" sync

# Set the venv prompt to the project name. Runs after `just sync` because the
# Nix image populates /root/assets/workspace/.venv at this stage rather than
# baking it at image-build time (the Debian image baked a venv whose prompt was
# the literal "template-project"). `uv` writes the prompt as the basename of the
# venv's parent dir, so rewrite the VIRTUAL_ENV_PROMPT assignment directly
# instead of substituting a fixed string. Guarded so a missing activate script
# never aborts post-create.
venv_activate="/root/assets/workspace/.venv/bin/activate"
if [ -f "$venv_activate" ]; then
    sed -i -E 's/^([[:space:]]*VIRTUAL_ENV_PROMPT=)"[^"]*"/\1"{{SHORT_NAME}}"/' "$venv_activate"
fi

# User specific setup
# Add your custom setup commands here to install any dependencies or tools needed for your project

echo "Post-create setup complete"
