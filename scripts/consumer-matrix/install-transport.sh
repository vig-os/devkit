#!/usr/bin/env bash
# Local transport for the real installer/workflow replay. Unknown calls fail.
# The container boundary starts clean and receives ONLY install.sh's -e values.
set -euo pipefail
case "${0##*/}" in
    curl)
        [[ "$*" == "-sSfL https://raw.githubusercontent.com/vig-os/devkit/refs/tags/$MATRIX_TARGET/install.sh" ]]
        cat "$MATRIX_ROOT/install.sh"
        ;;
    docker)
        case "$*" in
            info | "pull ghcr.io/vig-os/devcontainer:$MATRIX_TARGET") exit 0 ;;
        esac
        [[ "$1 $2" == 'run --rm' ]]
        shift 2
        forwarded=()
        while [[ "$1" == -* ]]; do
            case "$1" in
                -e) forwarded+=("$2") ;;
                -v) [[ "$2" == "$PWD:/workspace" ]] ;;
                *) exit 2 ;;
            esac
            shift 2
        done
        [[ "$1 $2" == "ghcr.io/vig-os/devcontainer:$MATRIX_TARGET /root/assets/init-workspace.sh" ]]
        shift 2
        exec env -i PATH="$PATH" HOME="$HOME" "${forwarded[@]}" \
            TEMPLATE_DIR="$MATRIX_ROOT/assets/workspace" \
            VERSION_FILE="$MATRIX_EVIDENCE/no-version" WORKSPACE_DIR="$PWD" \
            bash "$MATRIX_ROOT/assets/init-workspace.sh" "$@"
        ;;
    gh)
        [[ "$1 $2" != 'pr view' ]] || exit 1
        [[ "$1 $2" == 'pr create' ]]
        shift 2
        while (($#)); do
            case "$1" in
                --body) printf '%s\n' "$2" > "$MATRIX_EVIDENCE/pr-body" ;;
                --base) printf '%s\n' "$2" > "$MATRIX_EVIDENCE/pr-base" ;;
                --head | --title) ;;
                *) exit 2 ;;
            esac
            shift 2
        done
        ;;
    *) exit 2 ;;
esac
