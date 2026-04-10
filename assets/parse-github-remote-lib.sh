#!/usr/bin/env bash
# Parse github.com remote URL to owner/repo (stdout), or return 1 if unsupported
# Used by init-workspace.sh for {{GITHUB_REPOSITORY}} in renovate.json (Refs: #509).
parse_github_remote() {
    local url="$1"
    local owner repo
    [[ -z "$url" ]] && return 1
    # https://github.com/org/repo.git or trailing /
    if [[ "$url" =~ https?://github\.com/([^/]+)/([^/.]+)(\.git)?/?$ ]]; then
        owner="${BASH_REMATCH[1]}"
        repo="${BASH_REMATCH[2]}"
        [[ "$owner/$repo" =~ ^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$ ]] || return 1
        echo "$owner/$repo"
        return 0
    fi
    # git@github.com:org/repo.git
    if [[ "$url" =~ ^git@github\.com:([^/]+)/([^/.]+)(\.git)?$ ]]; then
        owner="${BASH_REMATCH[1]}"
        repo="${BASH_REMATCH[2]}"
        [[ "$owner/$repo" =~ ^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$ ]] || return 1
        echo "$owner/$repo"
        return 0
    fi
    # ssh://git@github.com/org/repo.git
    if [[ "$url" =~ ^ssh://git@github\.com/([^/]+)/([^/.]+)(\.git)?$ ]]; then
        owner="${BASH_REMATCH[1]}"
        repo="${BASH_REMATCH[2]}"
        [[ "$owner/$repo" =~ ^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$ ]] || return 1
        echo "$owner/$repo"
        return 0
    fi
    return 1
}

# Resolve GITHUB_REPOSITORY for {{GITHUB_REPOSITORY}} in renovate.json (after template copy)
resolve_github_repository() {
    if [[ -n "${GITHUB_REPOSITORY:-}" ]]; then
        if [[ ! "$GITHUB_REPOSITORY" =~ ^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$ ]]; then
            echo "Error: GITHUB_REPOSITORY must be owner/repo using only [A-Za-z0-9._-] segments." >&2
            exit 1
        fi
        echo "GitHub repository (Renovate): $GITHUB_REPOSITORY (from environment)"
        return 0
    fi
    local url=""
    if [[ -d "$WORKSPACE_DIR/.git" ]]; then
        url=$(git -C "$WORKSPACE_DIR" remote get-url origin 2>/dev/null || true)
    fi
    if [[ -n "$url" ]]; then
        local parsed=""
        if parsed=$(parse_github_remote "$url"); then
            GITHUB_REPOSITORY="$parsed"
            echo "GitHub repository (Renovate): $GITHUB_REPOSITORY (from git remote origin)"
            return 0
        fi
    fi
    if [[ "$NO_PROMPTS" == "true" ]]; then
        echo "Error: GITHUB_REPOSITORY is required with --no-prompts (e.g. export GITHUB_REPOSITORY=org/repo), or use a workspace with github.com origin." >&2
        exit 1
    fi
    read -rp "Enter GitHub repository for Renovate (owner/repo, e.g. vig-os/myapp): " GITHUB_REPOSITORY
    if [[ -z "$GITHUB_REPOSITORY" ]]; then
        echo "Error: GitHub repository is required to fill renovate.json." >&2
        exit 1
    fi
    if [[ ! "$GITHUB_REPOSITORY" =~ ^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$ ]]; then
        echo "Error: GITHUB_REPOSITORY must be owner/repo using only [A-Za-z0-9._-] segments." >&2
        exit 1
    fi
    echo "GitHub repository (Renovate): $GITHUB_REPOSITORY"
}
