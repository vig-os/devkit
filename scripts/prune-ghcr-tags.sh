#!/usr/bin/env bash
# One-time / ad-hoc prune of stale RC images on GHCR (vig-os/devcontainer) and matching git tags.
# Dry-run by default; pass --execute to delete. Requires gh and jq. Set GH_TOKEN (e.g. PAT with
# delete:packages, or a GitHub App token with package delete rights).
#
# Usage:
#   ./scripts/prune-ghcr-tags.sh --version X.Y.Z          # scope RC tag prune to one base version (sha256-orphan cleanup is global)
#   ./scripts/prune-ghcr-tags.sh --all                    # all *-rc* tags on GHCR (any base) + global sha256-orphan cleanup
#   ./scripts/prune-ghcr-tags.sh --execute ...            # perform deletes (default is dry-run)
#
# Refs: #463

set -euo pipefail

ORG="vig-os"
PKG="devcontainer"
PKG_PATH="/orgs/${ORG}/packages/container/${PKG}/versions"
DRY_RUN=1
MODE=""
BASE_VERSION=""

usage() {
  sed -n '1,20p' "$0" | tail -n +2
  exit 1
}

while [ $# -gt 0 ]; do
  case "$1" in
    --execute) DRY_RUN=0; shift ;;
    --version)
      BASE_VERSION="${2:-}"
      [ -n "$BASE_VERSION" ] || usage
      MODE="version"
      shift 2
      ;;
    --all) MODE="all"; shift ;;
    -h|--help) usage ;;
    *) echo "Unknown option: $1"; usage ;;
  esac
done

[ -n "$MODE" ] || { echo "ERROR: specify --version X.Y.Z or --all"; usage; }

if ! command -v gh >/dev/null 2>&1 || ! command -v jq >/dev/null 2>&1; then
  echo "ERROR: gh and jq are required"
  exit 1
fi

if [ "$MODE" = "version" ]; then
  if ! printf '%s' "$BASE_VERSION" | grep -qE '^[0-9]+\.[0-9]+\.[0-9]+$'; then
    echo "ERROR: --version must be MAJOR.MINOR.PATCH (got '$BASE_VERSION')"
    exit 1
  fi
fi

is_rc_for_base() {
  local tag="$1" base="$2"
  local prefix="${base}-rc" rc_suffix
  [[ "$tag" == "$prefix"* ]] || return 1
  rc_suffix="${tag#"$prefix"}"
  [[ "$rc_suffix" =~ ^[0-9]+$ ]] && return 0
  [[ "$rc_suffix" =~ ^[0-9]+-(amd64|arm64)$ ]] && return 0
  return 1
}

is_rc_tag_any_base() {
  local tag="$1"
  [[ "$tag" =~ -rc[0-9]+$ ]] && return 0
  [[ "$tag" =~ -rc[0-9]+-(amd64|arm64)$ ]] && return 0
  return 1
}

all_tags_sha256_prefixed() {
  local -a tags=("$@")
  [ "${#tags[@]}" -gt 0 ] || return 1
  local t
  for t in "${tags[@]}"; do
    [[ "$t" == sha256-* ]] || return 1
  done
  return 0
}

ghcr_version_matches_row() {
  local i
  if [ "$MODE" = "all" ]; then
    for i in "$@"; do
      is_rc_tag_any_base "$i" && return 0
    done
    all_tags_sha256_prefixed "$@" && return 0
    return 1
  fi
  for i in "$@"; do
    is_rc_for_base "$i" "$BASE_VERSION" && return 0
  done
  if [ "$MODE" = "version" ]; then
    all_tags_sha256_prefixed "$@" && return 0
  fi
  return 1
}

REPO_SLUG="${GITHUB_REPOSITORY:-}"
if [ -z "$REPO_SLUG" ]; then
  REPO_SLUG=$(gh repo view --json nameWithOwner -q .nameWithOwner 2>/dev/null || true)
fi
if [ -z "$REPO_SLUG" ]; then
  echo "WARN: GITHUB_REPOSITORY not set and gh repo view failed; skipping git tag deletes"
fi

TMP=$(mktemp)
trap 'rm -f "$TMP"' EXIT

echo "Listing GHCR package versions (${ORG}/${PKG})..."
gh api --paginate "$PKG_PATH" > "$TMP"

declare -a DELETE_IDS=()
while IFS= read -r row; do
  [ -z "$row" ] && continue
  vid=$(printf '%s' "$row" | jq -r '.id')
  mapfile -t tags < <(printf '%s' "$row" | jq -r '(.metadata.container.tags // [])[]?')
  if ghcr_version_matches_row "${tags[@]}"; then
    DELETE_IDS+=("$vid")
    echo "Would delete GHCR version id=$vid tags=[${tags[*]}]"
  fi
done < <(jq -s 'add // []' "$TMP" | jq -c '.[]')

if [ "$DRY_RUN" -eq 1 ]; then
  echo ""
  echo "Dry-run only (${#DELETE_IDS[@]} GHCR version(s)). Re-run with --execute to delete."
else
  for vid in "${DELETE_IDS[@]}"; do
    echo "Deleting GHCR package version id=$vid"
    gh api -X DELETE "$PKG_PATH/$vid"
  done
fi

# Git tags: RC tags for this repo matching scope
if [ -n "$REPO_SLUG" ]; then
  list_remote_rc_tags() {
    if [ "$MODE" = "all" ]; then
      git ls-remote --tags --refs "https://x-access-token:${GH_TOKEN}@github.com/${REPO_SLUG}.git" \
        | awk '{print $2}' | sed 's#refs/tags/##' | grep -E -- '-rc[0-9]+(-(amd64|arm64))?$' || true
    else
      git ls-remote --tags --refs "https://x-access-token:${GH_TOKEN}@github.com/${REPO_SLUG}.git" "${BASE_VERSION}-rc*" \
        | awk '{print $2}' | sed 's#refs/tags/##' || true
    fi
  }

  if [ -n "${GH_TOKEN:-}" ]; then
    TAGS=$(list_remote_rc_tags || true)
    if [ -z "$TAGS" ]; then
      echo "No matching remote git RC tags."
    else
      while IFS= read -r tag; do
        [ -z "$tag" ] && continue
        if gh api "repos/${REPO_SLUG}/releases/tags/${tag}" >/dev/null 2>&1; then
          echo "Skipping git tag $tag (GitHub Release exists)"
          continue
        fi
        if [ "$DRY_RUN" -eq 1 ]; then
          echo "Would delete git tag $tag (no GitHub Release)"
        else
          echo "Deleting git tag $tag"
          gh api -X DELETE "repos/${REPO_SLUG}/git/refs/tags/${tag}"
        fi
      done <<< "$TAGS"
    fi
  else
    echo "WARN: GH_TOKEN unset; skipping git tag listing/deletes"
  fi
fi

if [ "$DRY_RUN" -eq 1 ]; then
  echo "Done (dry-run)."
else
  echo "Done."
fi
