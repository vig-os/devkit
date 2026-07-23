#!/usr/bin/env bash
###############################################################################
# setup-labels.sh — Provision GitHub labels from label-taxonomy.toml
###############################################################################

set -euo pipefail

if [[ -n "${VIG_UTILS_REPO_ROOT:-}" ]]; then
    REPO_ROOT="$VIG_UTILS_REPO_ROOT"
else
    REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
fi
TAXONOMY_FILE="${REPO_ROOT}/.github/label-taxonomy.toml"
# Optional repo-local extension: same [[labels]] schema, never devkit-managed
# (mirrors the justfile layering: managed base -> repo-owned local layer).
# Merged into the effective taxonomy; on a name collision the local entry wins.
LOCAL_TAXONOMY_FILE="${REPO_ROOT}/.github/label-taxonomy.local.toml"

REPO_ARGS=()
PRUNE=false
DRY_RUN=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --repo)
            REPO_ARGS=(--repo "$2")
            shift 2
            ;;
        --prune)
            PRUNE=true
            shift
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --help|-h)
            echo "Usage: setup-labels [--repo owner/repo] [--prune] [--dry-run]"
            exit 0
            ;;
        *)
            echo "Unknown option: $1" >&2
            exit 1
            ;;
    esac
done

if [[ ! -f "$TAXONOMY_FILE" ]]; then
    echo "Error: taxonomy file not found: $TAXONOMY_FILE" >&2
    exit 1
fi

NAMES=()
DESCRIPTIONS=()
COLORS=()

current_name=""
current_desc=""
current_color=""

# Append the pending label, or — local-wins collision policy — replace the
# existing entry of the same name so a later file (the local extension)
# overrides the canonical color/description without duplicating the entry.
flush_label() {
    local i
    if [[ -n "$current_name" ]]; then
        for i in "${!NAMES[@]}"; do
            if [[ "${NAMES[$i]}" == "$current_name" ]]; then
                DESCRIPTIONS[i]="$current_desc"
                COLORS[i]="$current_color"
                current_name=""
                current_desc=""
                current_color=""
                return
            fi
        done
        NAMES+=("$current_name")
        DESCRIPTIONS+=("$current_desc")
        COLORS+=("$current_color")
    fi
    current_name=""
    current_desc=""
    current_color=""
}

parse_taxonomy() {
    local file="$1" line
    while IFS= read -r line || [[ -n "$line" ]]; do
        [[ "$line" =~ ^[[:space:]]*# ]] && continue
        [[ -z "${line// /}" ]] && continue

        if [[ "$line" =~ ^\[\[labels\]\] ]]; then
            flush_label
            continue
        fi

        if [[ "$line" =~ ^name[[:space:]]*=[[:space:]]*\"(.+)\" ]]; then
            current_name="${BASH_REMATCH[1]}"
        elif [[ "$line" =~ ^description[[:space:]]*=[[:space:]]*\"(.+)\" ]]; then
            current_desc="${BASH_REMATCH[1]}"
        elif [[ "$line" =~ ^color[[:space:]]*=[[:space:]]*\"(.+)\" ]]; then
            current_color="${BASH_REMATCH[1]}"
        fi
    done < "$file"
    flush_label
}

parse_taxonomy "$TAXONOMY_FILE"

echo "Taxonomy: ${#NAMES[@]} labels defined in $(basename "$TAXONOMY_FILE")"

if [[ -f "$LOCAL_TAXONOMY_FILE" ]]; then
    parse_taxonomy "$LOCAL_TAXONOMY_FILE"
    echo "Extended: ${#NAMES[@]} labels after merging $(basename "$LOCAL_TAXONOMY_FILE") (local wins on collision)"
fi

mapfile -t EXISTING < <(gh label list "${REPO_ARGS[@]}" --limit 100 --json name --jq '.[].name')

echo "Remote:   ${#EXISTING[@]} labels on repo"
echo ""

for i in "${!NAMES[@]}"; do
    name="${NAMES[$i]}"
    desc="${DESCRIPTIONS[$i]}"
    color="${COLORS[$i]}"

    found=false
    for existing in "${EXISTING[@]}"; do
        if [[ "$existing" == "$name" ]]; then
            found=true
            break
        fi
    done

    if $found; then
        if $DRY_RUN; then
            echo "[DRY-RUN]  update  $name"
        else
            gh label edit "$name" --description "$desc" --color "$color" "${REPO_ARGS[@]}"
            echo "[UPDATED]  $name"
        fi
    else
        if $DRY_RUN; then
            echo "[DRY-RUN]  create  $name"
        else
            gh label create "$name" --description "$desc" --color "$color" "${REPO_ARGS[@]}"
            echo "[CREATED]  $name"
        fi
    fi
done

if $PRUNE; then
    for existing in "${EXISTING[@]}"; do
        is_canonical=false
        for name in "${NAMES[@]}"; do
            if [[ "$existing" == "$name" ]]; then
                is_canonical=true
                break
            fi
        done

        if ! $is_canonical; then
            if $DRY_RUN; then
                echo "[DRY-RUN]  delete  $existing"
            else
                gh label delete "$existing" --yes "${REPO_ARGS[@]}"
                echo "[DELETED]  $existing"
            fi
        fi
    done
fi

echo ""
echo "Done."
