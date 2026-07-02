#!/bin/bash
set -euo pipefail

# {{SHORT_NAME}} is replaced during template initialization
PROJECT_ROOT="/workspace/{{SHORT_NAME}}"

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
