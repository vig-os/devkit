#!/bin/bash

# Post-start script - runs every time the container starts (create + restart).
# This script is called from postStartCommand in devcontainer.json.
#
# Tasks that should run on every container start:
#   - Fix Docker socket permissions
#   - Sync dependencies (fast no-op if nothing changed)

set -euo pipefail

echo "Running post-start setup..."

PROJECT_ROOT="/workspace/{{SHORT_NAME}}"

# Ensure Docker socket is accessible
sudo chmod 666 /var/run/docker.sock 2>/dev/null || true

# Sync dependencies (fast no-op if nothing changed)
echo "Syncing dependencies..."
just --justfile "$PROJECT_ROOT/justfile" --working-directory "$PROJECT_ROOT" sync

# Bring container into tailnet if TAILSCALE_AUTHKEY is set (no-op otherwise).
# Image bake handles install; this script only handles runtime connect.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -x "$SCRIPT_DIR/setup-tailscale.sh" ]; then
    "$SCRIPT_DIR/setup-tailscale.sh" connect || \
        echo "Tailscale: connect failed but post-start continues (container still usable via devcontainer protocol)"
fi

echo "Post-start setup complete"
