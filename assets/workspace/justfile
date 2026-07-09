# ===============================================================================
# MAIN JUSTFILE - Orchestrates all recipe sources
# ===============================================================================

# Run every recipe under a strict bash so pipelines fail on the first error.
# Lives here (not justfile.devc) so it applies in ALL delivery modes — direnv
# and bare have no .devcontainer/justfile.devc, yet their justfile.project
# recipes must still get pipefail (#854).
set shell := ["bash", "-euo", "pipefail", "-c"]

# Show available commands
[group('info')]
help:
    @just --list

# Import devcontainer-managed base recipes (replaced on upgrade).
# Optional: a `direnv`-mode workspace (`init-workspace --mode direnv`) has no
# .devcontainer/, so these must not be hard imports or `just` fails to load.

import? '.devcontainer/justfile.devc'
import? '.devcontainer/justfile.gh'
import? '.devcontainer/justfile.worktree'

# Import team-shared project recipes (git-tracked, preserved on upgrade)

import? 'justfile.project'

# Import personal recipes (gitignored, preserved on upgrade)

import? 'justfile.local'
