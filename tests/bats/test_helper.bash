# BATS test helper — loads BATS libraries and performs project-specific setup
#
# Usage (in every .bats file):
#   setup() { load test_helper; }
#
# bats and its helper libraries (bats-support/-assert/-file) come from the Nix
# flake (the toolchain SSoT). The `bats.withLibraries` wrapper and the
# dev-shell/image both export BATS_LIB_PATH, so `bats_load_library` resolves the
# helpers from the Nix store — no node_modules (npm) or /usr/lib (Debian)
# needed. Refs #695.

# Resolve project root (two levels up from tests/bats/)
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
export PROJECT_ROOT

# Load BATS helper libraries via BATS_LIB_PATH (provided by the flake).
bats_load_library bats-support
bats_load_library bats-assert
bats_load_library bats-file
