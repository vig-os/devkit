#!/bin/bash
# Initialize workspace by copying template files
#
# Usage: init-workspace [--force] [--no-prompts] [--smoke-test] [--mode MODE]
#
# Options:
#   --force       Overwrite existing files (for upgrades)
#   --no-prompts  Run non-interactively (requires SHORT_NAME env var)
#   --smoke-test  Deploy smoke-test-specific assets
#   --mode MODE   Delivery mode: devcontainer | direnv | both
#                 devcontainer  scaffold .devcontainer/ only (no flake.nix/.envrc)
#                 direnv        scaffold flake.nix + .envrc only (no .devcontainer/)
#                 both          scaffold everything (default)
#                 Unset: prompt interactively, or default to "both" with --no-prompts
#
# Environment variables (used with --no-prompts):
#   SHORT_NAME           - Project short name (required)
#   ORG_NAME             - Organization name (optional, defaults to "vigOS/devc")
#   GITHUB_REPOSITORY    - owner/repo for Renovate preset extends (optional if origin is github.com)
#   VIG_OS_VERSION       - Override the DEVCONTAINER_VERSION pinned in the scaffolded
#                          .vig-os (optional; install.sh forwards its --version, #852)

set -euo pipefail

# Defaults match the in-image layout; overridable so the scaffold can be
# exercised end-to-end from tests against temporary directories.
TEMPLATE_DIR="${TEMPLATE_DIR:-/root/assets/workspace}"
WORKSPACE_DIR="${WORKSPACE_DIR:-/workspace}"
FORCE=false
NO_PROMPTS=false
SMOKE_TEST=false
# Delivery mode: devcontainer | direnv | both. Empty = prompt (or "both" with --no-prompts).
MODE=""

# Files to preserve during --force upgrades (never overwrite if they exist)
# These are user/project customization files that should survive upgrades
PRESERVE_FILES=(
    ".devcontainer/docker-compose.project.yaml"
    ".devcontainer/docker-compose.local.yaml"
    "README.md"
    "CHANGELOG.md"
    "LICENSE"
    ".github/CODEOWNERS"
    ".github/workflows/release-extension.yml"
    "justfile.project"
    "renovate.json"
    # direnv/flake stub (#640): the user owns the extraPackages block, so a
    # dev-env upgrade must never clobber it — same class as justfile.project.
    "flake.nix"
    ".envrc"
    # The consumer owns its project manifest (#738): a (re)scaffold must never
    # overwrite an existing pyproject.toml with the generic template one.
    "pyproject.toml"
    # The consumer owns its hook configuration (#878): repos carry repo-specific
    # global/per-hook `exclude:` patterns (data tables, generated files, PEM
    # marker literals) that a template overwrite silently destroyed — the hook
    # suite then rewrote files it must never touch. Preserved like
    # justfile.project; the upgrade prints a diff against the template below so
    # hook-stack evolution stays visible.
    ".pre-commit-config.yaml"
)

# Base recipes the shipped .github/workflows/ci.yml depends on (sync, precommit,
# test) plus their template siblings. Since 0.4.0 they live in justfile.project,
# which is preserved on upgrade — a pre-0.4.0 consumer never receives them and
# in-container CI fails with "justfile does not contain recipe 'sync'" (#877).
# The upgrade repair below appends the missing ones from the template.
CI_CONTRACT_RECIPES=(lint format precommit test test-cov sync update)

# Get script directory for manifest location
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MANIFEST_FILE="$SCRIPT_DIR/.placeholder-manifest.txt"

# Co-located with init-workspace.sh in the image; path is dynamic at runtime.
# shellcheck disable=SC1091
source "$SCRIPT_DIR/parse-github-remote-lib.sh"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --force)
            FORCE=true
            shift
            ;;
        --no-prompts)
            NO_PROMPTS=true
            shift
            ;;
        --smoke-test)
            SMOKE_TEST=true
            shift
            ;;
        --mode)
            MODE="$2"
            shift 2
            ;;
        --mode=*)
            MODE="${1#--mode=}"
            shift
            ;;
        *)
            echo "Unknown option: $1" >&2
            echo "Usage: init-workspace [--force] [--no-prompts] [--smoke-test] [--mode MODE]" >&2
            exit 1
            ;;
    esac
done

# Validate delivery mode (empty handled later: prompt, or default to "both").
case "$MODE" in
    ""|devcontainer|direnv|both) ;;
    *)
        echo "Error: Invalid --mode: $MODE (expected: devcontainer | direnv | both)" >&2
        exit 1
        ;;
esac

# Smoke mode must run unattended and allow overwriting existing content.
if [[ "$SMOKE_TEST" == "true" ]]; then
    NO_PROMPTS=true
    FORCE=true
fi

# Check if running in interactive mode (only if prompts are needed)
if [[ "$NO_PROMPTS" != "true" ]] && [[ ! -t 0 ]]; then
    echo "Error: This script requires an interactive terminal." >&2
    echo "" >&2
    echo "Please run with the -it flags:" >&2
    echo "  podman run -it --rm -v \"./:/workspace\" ghcr.io/vig-os/devcontainer:latest /root/assets/init-workspace.sh" >&2
    echo "  docker run -it --rm -v \"./:/workspace\" ghcr.io/vig-os/devcontainer:latest /root/assets/init-workspace.sh" >&2
    exit 1
fi

# Check if template directory exists
if [[ ! -d "$TEMPLATE_DIR" ]]; then
    echo "Error: Template directory not found at $TEMPLATE_DIR" >&2
    exit 1
fi

# Function to check if workspace is effectively empty
is_workspace_empty() {
    # Count non-hidden files and directories (excluding .git)
    local count
    count=$(find "$WORKSPACE_DIR" -mindepth 1 -maxdepth 1 \
        ! -name '.git' ! -name '.*' 2>/dev/null | wc -l)

    # Also check for .git only (common case)
    if [[ -d "$WORKSPACE_DIR/.git" ]] && [[ $count -eq 0 ]]; then
        return 0  # Empty except for .git
    fi

    [[ $count -eq 0 ]]
}

# Check if workspace has content
if ! is_workspace_empty && [[ "$FORCE" != "true" ]]; then
    echo "Error: Workspace is not empty. Use --force to overwrite existing files." >&2
    echo "Current workspace contents:" >&2
    find "$WORKSPACE_DIR" -maxdepth 1 -mindepth 1 -exec ls -ld {} \; 2>/dev/null | head -10 >&2
    exit 1
fi

# Get SHORT_NAME - from env var or prompt
if [[ "$NO_PROMPTS" == "true" ]]; then
    # Non-interactive mode: require SHORT_NAME env var
    if [[ -z "${SHORT_NAME:-}" ]]; then
        echo "Error: SHORT_NAME environment variable is required with --no-prompts" >&2
        exit 1
    fi
else
    # Interactive mode: prompt user
    read -rp "Enter a short name for your project (letters/numbers only, e.g. my_proj): " SHORT_NAME
    if [[ -z "$SHORT_NAME" ]]; then
        echo "Error: Short project name is required" >&2
        exit 1
    fi
fi

# Sanitize: replace hyphens and spaces with underscore; lowercase; remove other special chars
SHORT_NAME=$(echo "$SHORT_NAME" | tr '[:upper:]' '[:lower:]' | sed 's/[ -]/_/g' | sed 's/[^a-z0-9_]/_/g')
SHORT_NAME=$(echo "$SHORT_NAME" | sed 's/__*/_/g' | sed 's/^[^a-z0-9]*//; s/[^a-z0-9]*$//')
SHORT_NAME="${SHORT_NAME:-project}"
echo "Project short name set to: $SHORT_NAME"

# Get ORG_NAME - from env var, default, or prompt
if [[ "$NO_PROMPTS" == "true" ]]; then
    # Non-interactive mode: use env var or default
    ORG_NAME="${ORG_NAME:-vigOS/devc}"
else
    # Interactive mode: prompt user
    read -rp "Enter the name of your organization, e.g. 'vigOS': " ORG_NAME
    if [[ -z "$ORG_NAME" ]]; then
        echo "Error: Organization name is required" >&2
        exit 1
    fi
fi
echo "Organization name set to: $ORG_NAME"

# Get MODE - from flag, prompt, or default. Selects which delivery the workspace
# scaffolds: a devcontainer, the Nix/direnv stub, or both.
if [[ -z "$MODE" ]]; then
    if [[ "$NO_PROMPTS" == "true" ]] || [[ ! -t 0 ]]; then
        # Non-interactive (--no-prompts, or no TTY: CI / piped stdin): default to
        # "both" without blocking on the prompt, preserving prior behaviour.
        MODE="both"
    else
        # Interactive mode: prompt user (default selection: both).
        echo "Choose how this workspace runs its dev environment:"
        echo "  1) devcontainer - VS Code Dev Containers (.devcontainer/)"
        echo "  2) direnv       - Nix flake + direnv (flake.nix + .envrc)"
        echo "  3) both         - scaffold both (default)"
        read -rp "Delivery mode [devcontainer/direnv/both] (default: both): " MODE
        MODE="${MODE:-both}"
        case "$MODE" in
            devcontainer|direnv|both) ;;
            *)
                echo "Error: Invalid mode: $MODE (expected: devcontainer | direnv | both)" >&2
                exit 1
                ;;
        esac
    fi
fi
echo "Delivery mode set to: $MODE"

# Print one recipe block from the template justfile.project: the immediately
# preceding comment/attribute lines, the recipe header, and the indented body.
# Used to repair a preserved pre-0.4.0 justfile.project that lacks the
# relocated base recipes (#877); the template stays the single source of truth.
extract_template_recipe() {
    local recipe="$1"
    awk -v r="$recipe" '
        found && /^[[:space:]]/ { print; next }
        found { exit }
        /^(#|\[)/ { buf = buf $0 ORS; next }
        $0 ~ ("^" r "([[:space:]][^:]*)?:") { found = 1; printf "%s", buf; print; next }
        { buf = "" }
    ' "$TEMPLATE_DIR/justfile.project"
}

# Helper: check if a file is in the preserve list
is_preserved_file() {
    local file="$1"
    for preserved in "${PRESERVE_FILES[@]}"; do
        if [[ "$file" == "$preserved" ]]; then
            return 0
        fi
    done
    return 1
}

# Warn if forcing (prompt user) - show which files would be overwritten
if [[ "$FORCE" == "true" ]]; then
    echo ""
    echo "Checking for files that would be affected..."

    # Find files that exist in both template and workspace
    CONFLICTS=()
    PRESERVED=()
    while IFS= read -r -d '' template_file; do
        # Get relative path from template directory
        rel_path="${template_file#"$TEMPLATE_DIR"/}"
        workspace_file="$WORKSPACE_DIR/$rel_path"

        if [[ -e "$workspace_file" ]]; then
            if is_preserved_file "$rel_path"; then
                PRESERVED+=("$rel_path")
            else
                CONFLICTS+=("$rel_path")
            fi
        fi
    done < <(find "$TEMPLATE_DIR" -type f ! -path "*/.git/*" -print0)

    # Show preserved files
    if [[ ${#PRESERVED[@]} -gt 0 ]]; then
        echo ""
        echo "The following ${#PRESERVED[@]} file(s) will be PRESERVED (not overwritten):"
        echo "─────────────────────────────────────────────────────────────"
        for preserved in "${PRESERVED[@]}"; do
            echo "  ✓  $preserved"
        done
        echo "─────────────────────────────────────────────────────────────"
    fi

    # Show files that will be overwritten
    if [[ ${#CONFLICTS[@]} -eq 0 ]]; then
        echo ""
        echo "No existing files would be overwritten."
    else
        echo ""
        echo "The following ${#CONFLICTS[@]} file(s) will be OVERWRITTEN:"
        echo "─────────────────────────────────────────────────────────────"
        for conflict in "${CONFLICTS[@]}"; do
            echo "  ⚠  $conflict"
        done
        echo "─────────────────────────────────────────────────────────────"
        echo ""
    fi

    # Only prompt for confirmation in interactive mode
    if [[ "$NO_PROMPTS" != "true" ]]; then
        read -rp "Continue with --force? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            echo "Aborted."
            exit 0
        fi
    else
        echo "Proceeding with --force (non-interactive mode)"
    fi
fi

# Record whether the consumer already had a populated .devcontainer/ before the
# scaffold (#738). In direnv mode we must neither overwrite nor delete it.
DEVCONTAINER_PREEXISTED=false
if [[ -d "$WORKSPACE_DIR/.devcontainer" ]] \
    && [[ -n "$(ls -A "$WORKSPACE_DIR/.devcontainer" 2>/dev/null)" ]]; then
    DEVCONTAINER_PREEXISTED=true
fi

# Same guard for the consumer's own nix-direnv files (#859): the
# devcontainer-mode prune may only remove the flake stub/`.envrc` that this
# scaffold would create, never a pre-existing setup (they are PRESERVE_FILES,
# so rsync never overwrites them either — the prune must match).
FLAKE_PREEXISTED=false
[[ -f "$WORKSPACE_DIR/flake.nix" ]] && FLAKE_PREEXISTED=true
ENVRC_PREEXISTED=false
[[ -f "$WORKSPACE_DIR/.envrc" ]] && ENVRC_PREEXISTED=true

# A preserved justfile.project may predate the 0.4.0 base-recipe relocation
# (#877); record it so the post-scaffold repair can append what is missing.
JUSTFILE_PROJECT_PREEXISTED=false
[[ -f "$WORKSPACE_DIR/justfile.project" ]] && JUSTFILE_PROJECT_PREEXISTED=true

# A preserved .pre-commit-config.yaml may lag the template hook stack (#878);
# record it so the post-scaffold guard can surface the divergence.
PRECOMMIT_CONFIG_PREEXISTED=false
[[ -f "$WORKSPACE_DIR/.pre-commit-config.yaml" ]] && PRECOMMIT_CONFIG_PREEXISTED=true

# Copy template contents to workspace
echo "Initializing workspace from template..."
echo "Copying files from $TEMPLATE_DIR to $WORKSPACE_DIR..."

# Note: Excluding .venv - it is used directly from the container image
# via UV_PROJECT_ENVIRONMENT environment variable (set in docker-compose.yml)
# Pre-commit cache is now at /opt/pre-commit-cache (not in assets/workspace)
if [[ "$SMOKE_TEST" == "true" ]]; then
    # Smoke mode: clean deploy (--delete removes stale files), then overlay smoke-test assets
    rsync -avL --delete --exclude='.git' --exclude='.venv' --exclude='docs/issues/' --exclude='docs/pull-requests/' "$TEMPLATE_DIR/" "$WORKSPACE_DIR/"

    SMOKE_TEST_DIR="$SCRIPT_DIR/smoke-test"
    if [[ -d "$SMOKE_TEST_DIR" ]]; then
        echo "Deploying smoke-test-specific files..."
        rsync -avL "$SMOKE_TEST_DIR/" "$WORKSPACE_DIR/"
    else
        echo "Warning: Smoke-test directory not found at $SMOKE_TEST_DIR" >&2
    fi

    # Workspace scaffold CHANGELOG is empty; copy devcontainer changelog and
    # rename top ## [version] - … to ## Unreleased for downstream prepare-release.
    if [[ -f "$WORKSPACE_DIR/.devcontainer/CHANGELOG.md" ]]; then
        echo "Syncing workspace CHANGELOG from .devcontainer/CHANGELOG.md (smoke-test)..."
        cp "$WORKSPACE_DIR/.devcontainer/CHANGELOG.md" "$WORKSPACE_DIR/CHANGELOG.md"
        if ! command -v prepare-changelog >/dev/null 2>&1; then
            echo "ERROR: prepare-changelog not found (required for smoke-test CHANGELOG sync)" >&2
            exit 1
        fi
        prepare-changelog unprepare "$WORKSPACE_DIR/CHANGELOG.md"
    fi
else
    # Build exclude list for preserved files that already exist
    EXCLUDE_ARGS=()
    for preserved in "${PRESERVE_FILES[@]}"; do
        if [[ -e "$WORKSPACE_DIR/$preserved" ]]; then
            EXCLUDE_ARGS+=("--exclude=$preserved")
        fi
    done

    # direnv mode wants no .devcontainer/ at all, so never copy the template one
    # over a populated consumer .devcontainer/ (#738). Excluding it from the copy
    # (rather than copying-then-pruning) keeps a real .devcontainer/ intact.
    if [[ "$MODE" == "direnv" ]]; then
        EXCLUDE_ARGS+=("--exclude=.devcontainer")
    fi

    rsync -avL --exclude='.git' --exclude='.venv' "${EXCLUDE_ARGS[@]}" "$TEMPLATE_DIR/" "$WORKSPACE_DIR/"
fi

# The Nix-built image stores the baked template as read-only symlinks into the
# Nix store. The rsync `-L` (--copy-links) above dereferences them into real
# files, but those inherit the store's read-only (0444) mode. Make the scaffold
# user-writable so the placeholder substitution below — and the user's own edits
# — work. No-op on the Debian image (its template files are already writable).
chmod -R u+w "$WORKSPACE_DIR"

# Prune the scaffold to the chosen delivery mode. Idempotent and safe: only
# removes paths inside the new workspace.
#   devcontainer -> remove the flake.nix + .envrc stub
#   direnv       -> remove the .devcontainer/ scaffold
#   both         -> keep everything
case "$MODE" in
    devcontainer)
        # Only prune the stub files this scaffold created; a consumer's own
        # pre-existing flake.nix/.envrc must survive (#859).
        if [[ "$FLAKE_PREEXISTED" == "true" ]]; then
            echo "devcontainer mode: preserving existing flake.nix (#859)"
        else
            echo "Pruning to 'devcontainer' mode: removing flake.nix..."
            rm -f "$WORKSPACE_DIR/flake.nix"
        fi
        if [[ "$ENVRC_PREEXISTED" == "true" ]]; then
            echo "devcontainer mode: preserving existing .envrc (#859)"
        else
            echo "Pruning to 'devcontainer' mode: removing .envrc..."
            rm -f "$WORKSPACE_DIR/.envrc"
        fi
        ;;
    direnv)
        # Only drop a .devcontainer/ that this scaffold created; never delete a
        # populated consumer .devcontainer/ that predates the (re)scaffold (#738).
        if [[ "$DEVCONTAINER_PREEXISTED" == "true" ]]; then
            echo "direnv mode: preserving existing .devcontainer/ (#738)"
        else
            echo "Pruning to 'direnv' mode: removing .devcontainer/..."
            rm -rf "$WORKSPACE_DIR/.devcontainer"
        fi
        ;;
    both)
        : # keep everything
        ;;
esac

# 0.4.0 retired .devcontainer/justfile.base (recipes relocated to
# justfile.project), so drop the stale copy an upgraded 0.3.x repo carries —
# nothing imports it anymore (#877). Only when this scaffold manages
# .devcontainer/: a direnv-mode consumer's own .devcontainer/ is never
# touched (#738).
if [[ "$MODE" != "direnv" && -f "$WORKSPACE_DIR/.devcontainer/justfile.base" ]]; then
    echo "Removing retired .devcontainer/justfile.base (recipes live in justfile.project since 0.4.0)..."
    rm -f "$WORKSPACE_DIR/.devcontainer/justfile.base"
fi

# Pin the explicitly requested devcontainer version (#852). The image bakes
# the release it was built from into the scaffolded .vig-os (flake bootstrap),
# which is correct for finals but stale for release candidates: the repo-root
# pin only advances at finalize. install.sh forwards its --version here so the
# scaffold pins the image actually installed.
if [[ -n "${VIG_OS_VERSION:-}" && -f "$WORKSPACE_DIR/.vig-os" ]]; then
    if [[ ! "$VIG_OS_VERSION" =~ ^[A-Za-z0-9._-]+$ ]]; then
        echo "Error: invalid VIG_OS_VERSION: $VIG_OS_VERSION" >&2
        exit 1
    fi
    echo "Pinning DEVCONTAINER_VERSION=${VIG_OS_VERSION} in .vig-os..."
    sed -i "s/^DEVCONTAINER_VERSION=.*/DEVCONTAINER_VERSION=${VIG_OS_VERSION}/" "$WORKSPACE_DIR/.vig-os"
fi

resolve_github_repository

# Replace placeholders in files (using pre-built manifest from image)
echo "Replacing placeholders in files..."

# Escape special characters in variables for sed (especially slashes in ORG_NAME, GITHUB_REPOSITORY)
SHORT_NAME_ESCAPED=$(printf '%s\n' "$SHORT_NAME" | sed 's/[&/\]/\\&/g')
ORG_NAME_ESCAPED=$(printf '%s\n' "$ORG_NAME" | sed 's/[&/\]/\\&/g')
GITHUB_REPOSITORY_ESCAPED=$(printf '%s\n' "$GITHUB_REPOSITORY" | sed 's/[&/\]/\\&/g')

if [[ -f "$MANIFEST_FILE" ]]; then
    # Use build-time manifest (much faster - no searching at runtime)
    echo "Using build-time manifest ($(wc -l < "$MANIFEST_FILE") files)"
    while IFS= read -r template_file; do
        # Translate template path to workspace path
        workspace_file="${template_file/\/root\/assets\/workspace/$WORKSPACE_DIR}"

        if [[ -f "$workspace_file" ]]; then
            # Simple sed -i (always Linux in container - no cross-platform needed)
            sed -i "s/{{SHORT_NAME}}/${SHORT_NAME_ESCAPED}/g; s/{{ORG_NAME}}/${ORG_NAME_ESCAPED}/g; s/{{GITHUB_REPOSITORY}}/${GITHUB_REPOSITORY_ESCAPED}/g" "$workspace_file"
        fi
    done < "$MANIFEST_FILE"
else
    # Fallback: search at runtime (slower, but works if manifest is missing)
    echo "Warning: Manifest not found, searching at runtime (slower)"
    find "$WORKSPACE_DIR" -type f ! -path "*/.git/*" -print0 | while IFS= read -r -d '' file; do
        if grep -q '{{SHORT_NAME}}\|{{ORG_NAME}}\|{{GITHUB_REPOSITORY}}' "$file" 2>/dev/null; then
            sed -i "s/{{SHORT_NAME}}/${SHORT_NAME_ESCAPED}/g; s/{{ORG_NAME}}/${ORG_NAME_ESCAPED}/g; s/{{GITHUB_REPOSITORY}}/${GITHUB_REPOSITORY_ESCAPED}/g" "$file"
        fi
    done
fi

# Rename template_project directory to match project short name
if [[ -d "$WORKSPACE_DIR/src/template_project" ]]; then
    if [[ -d "$WORKSPACE_DIR/src/${SHORT_NAME}" ]] && [[ "$SHORT_NAME" != "template_project" ]]; then
        echo "Removing duplicate src/template_project (src/${SHORT_NAME} already exists)..."
        rm -rf "$WORKSPACE_DIR/src/template_project"
    else
        echo "Renaming src/template_project to src/${SHORT_NAME}..."
        mv "$WORKSPACE_DIR/src/template_project" "$WORKSPACE_DIR/src/${SHORT_NAME}"
    fi
fi

# Update test imports to use actual project name (template_project -> $SHORT_NAME)
if [[ -f "$WORKSPACE_DIR/tests/test_example.py" ]]; then
    sed -i "s/import template_project/import ${SHORT_NAME}/g; s/template_project\.__version__/${SHORT_NAME}.__version__/g" "$WORKSPACE_DIR/tests/test_example.py"
fi

# Restore executable permissions on shell scripts and hooks (must be after sed -i)
echo "Setting executable permissions on shell scripts and hooks..."
find "$WORKSPACE_DIR" -type f -name "*.sh" -exec chmod +x {} \;
find "$WORKSPACE_DIR/.githooks" -type f -exec chmod +x {} \; 2>/dev/null || true

# The root justfile is managed (rsync overwrites it on upgrade), so the
# scaffold import block must be present at this point; without it every
# layered recipe is unreachable, however complete justfile.project is
# (#877, observed in the field). Warn loudly — this indicates a broken
# scaffold or external interference.
if [[ -f "$WORKSPACE_DIR/justfile" ]] \
    && ! grep -qF "import? 'justfile.project'" "$WORKSPACE_DIR/justfile"; then
    echo "Warning: root justfile lacks the scaffold import block (import? 'justfile.project')." >&2
    echo "         Restore the imports from the template or layered recipes stay unreachable (see MIGRATION.md)." >&2
fi

# Repair a preserved pre-0.4.0 justfile.project (#877): the shipped ci.yml
# calls `just sync` / `just precommit` / `just test`, so an upgrade must
# deliver the CI-contract recipes. Append (from the template) only those that
# do not resolve anywhere in the import graph — customized consumer recipes
# always win, and re-running the upgrade is a no-op.
if [[ "$JUSTFILE_PROJECT_PREEXISTED" == "true" && -f "$WORKSPACE_DIR/justfile.project" ]]; then
    if ! command -v just > /dev/null 2>&1; then
        echo "Warning: 'just' not found on PATH; skipping base-recipe repair (#877)." >&2
        MISSING_RECIPES=()
    # If the import graph does not parse (e.g. a syntax error in the preserved
    # justfile.project), `just --show` fails for EVERY recipe — probing would
    # misread all of them as missing and append duplicates on each run.
    elif ! (cd "$WORKSPACE_DIR" && just --list > /dev/null 2>&1); then
        echo "Warning: justfile graph does not parse; skipping base-recipe repair (#877)." >&2
        echo "         Fix the syntax error (run 'just --list' to see it) and re-run init-workspace." >&2
        MISSING_RECIPES=()
    else
        MISSING_RECIPES=()
        for recipe in "${CI_CONTRACT_RECIPES[@]}"; do
            if ! (cd "$WORKSPACE_DIR" && just --show "$recipe" > /dev/null 2>&1); then
                MISSING_RECIPES+=("$recipe")
            fi
        done
    fi
    if [[ ${#MISSING_RECIPES[@]} -gt 0 ]]; then
        echo "Preserved justfile.project lacks base recipe(s): ${MISSING_RECIPES[*]}"
        echo "Appending them from the template (review the marked block, fold into your own recipes as needed)..."
        {
            echo ""
            echo "# ==============================================================================="
            echo "# BASE RECIPES appended by init-workspace on upgrade (vig-os/devcontainer#877)."
            echo "# Since 0.4.0 these live in justfile.project (preserved on upgrade); the shipped"
            echo "# ci.yml requires sync/precommit/test. Review, keep, or fold into your own."
            echo "# ==============================================================================="
            for recipe in "${MISSING_RECIPES[@]}"; do
                recipe_block="$(extract_template_recipe "$recipe")"
                if [[ -z "$recipe_block" ]]; then
                    echo "Warning: recipe '$recipe' not found in the template justfile.project; skipping it (#877)." >&2
                    continue
                fi
                echo ""
                printf '%s\n' "$recipe_block"
            done
        } >> "$WORKSPACE_DIR/justfile.project"
    fi
fi

# A preserved .pre-commit-config.yaml is the consumer's (#878) — never
# overwritten, so their global/per-hook `exclude:` patterns survive. The cost
# is that template hook-stack evolution (runner migrations, new hooks, compat
# fixes) no longer arrives automatically: print the divergence from the
# template so consumers can fold in what they need deliberately, and gate the
# preserved file through `prek validate-config` — a config the runner cannot
# load breaks every commit in the new image. Both are warnings, never fatal.
if [[ "$PRECOMMIT_CONFIG_PREEXISTED" == "true" \
    && -f "$WORKSPACE_DIR/.pre-commit-config.yaml" \
    && -f "$TEMPLATE_DIR/.pre-commit-config.yaml" ]] \
    && ! diff -q "$TEMPLATE_DIR/.pre-commit-config.yaml" \
        "$WORKSPACE_DIR/.pre-commit-config.yaml" > /dev/null 2>&1; then
    echo "Preserved .pre-commit-config.yaml differs from the template (yours was kept, #878)."
    echo "Template changes NOT applied (fold in what you need, see MIGRATION.md):"
    echo "─────────────────────────────────────────────────────────────"
    diff -u "$WORKSPACE_DIR/.pre-commit-config.yaml" \
        "$TEMPLATE_DIR/.pre-commit-config.yaml" || true
    echo "─────────────────────────────────────────────────────────────"
    if command -v prek > /dev/null 2>&1; then
        if ! (cd "$WORKSPACE_DIR" && prek validate-config .pre-commit-config.yaml > /dev/null 2>&1); then
            echo "Warning: preserved .pre-commit-config.yaml does not validate under prek (#878)." >&2
            echo "         Every commit will fail until it parses — run 'prek validate-config .pre-commit-config.yaml' and fix it." >&2
        fi
    fi
fi

# Sync dependencies: resolves uv.lock for the new project name and installs the
# project. Non-fatal (#859): a preserved old-generation justfile.project may not
# define `sync` yet — the scaffold itself is complete at this point, so warn and
# let the consumer sync after migrating their recipes.
echo "Syncing dependencies..."
cd "$WORKSPACE_DIR"
if just --show sync > /dev/null 2>&1; then
    just sync
else
    echo "Warning: no 'sync' recipe found (preserved pre-0.4.0 justfile.project?)." >&2
    echo "         Run 'uv sync' manually after migrating your recipes (see MIGRATION.md)." >&2
fi

echo "Workspace initialized successfully!"
echo ""
echo "You can now start developing in your workspace."
