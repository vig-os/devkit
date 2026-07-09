#!/usr/bin/env bash
set -euo pipefail

# Derive the project root from this script's own location
# (<project-root>/.devcontainer/scripts/init-precommit.sh) rather than a
# hard-coded /workspace/<name>, so it works regardless of the mount point (#854).
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

if [ -f "$PROJECT_ROOT/.pre-commit-config.yaml" ]; then
    echo "Setting up Git hooks (this may take a few minutes)..."
    cd "$PROJECT_ROOT"
    # prek (Rust) is the hook runner shipped in the devcontainer image; its
    # `prepare-hooks` is the analogue of `pre-commit install-hooks`. It is
    # idempotent, so it is safe to run on every container init. Refs #778.
    prek prepare-hooks || {
        echo "⚠️  Git hook environment setup failed"
        echo "    You can manually run 'prek prepare-hooks' later"
        exit 1
    }
    echo "Git hooks installed successfully"
else
    echo "No .pre-commit-config.yaml found, skipping"
fi
