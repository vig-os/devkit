#!/bin/bash
# Initialize workspace by copying template files
#
# Usage: init-workspace [--force] [--no-prompts] [--smoke-test] [--preview] [--mode MODE] [--prune-devcontainer]
#
# Options:
#   --force       Overwrite existing files (for upgrades)
#   --no-prompts  Run non-interactively (requires SHORT_NAME env var)
#   --smoke-test  Deploy smoke-test-specific assets
#   --preview     Print the add/overwrite/preserve/delete report an upgrade
#                 would produce, then exit 0 without touching the tree (#886)
#   --prune-devcontainer
#                 In direnv/bare mode, also remove a PRE-EXISTING .devcontainer/
#                 (a container→direnv/bare migration cleanup, #990). Without it
#                 the #738 default is non-destructive and keeps it. Interactive
#                 runs prompt once when a populated .devcontainer/ is detected.
#                 Rejected in devcontainer/both modes.
#   --mode MODE   Delivery mode: devcontainer | direnv | both | bare
#                 devcontainer  scaffold .devcontainer/ only (no flake.nix/.envrc)
#                 direnv        scaffold flake.nix + .envrc only (no .devcontainer/)
#                 both          scaffold everything (default)
#                 bare          standards only: justfiles, hooks, host-native CI
#                               (no .devcontainer/, no flake.nix/.envrc)
#                 Unset: read DEVKIT_MODE from the workspace .vig-os manifest,
#                 else prompt interactively / default to "both" with --no-prompts
#
# Environment variables (used with --no-prompts):
#   SHORT_NAME           - Project short name (required unless the workspace
#                          .vig-os persists DEVKIT_PROJECT, #885)
#   ORG_NAME             - Organization name (optional, defaults to DEVKIT_ORG
#                          from .vig-os, else the GITHUB_REPOSITORY owner
#                          segment, else the literal "vigOS")
#   GITHUB_REPOSITORY    - owner/repo for Renovate preset extends (optional if
#                          persisted as DEVKIT_REPO or origin is github.com)
#   VIG_OS_VERSION       - Override the DEVKIT_VERSION pinned in the scaffolded
#                          .vig-os (optional; install.sh forwards its --version, #852)
#
# The workspace .vig-os is the project's declarative manifest (#885): the
# delivery mode and identity resolved by this script are written back to it,
# so upgrades of a manifest-bearing repo are non-interactive and
# shape-preserving with no flags. Precedence: flag/env > .vig-os > prompt/default.

set -euo pipefail

# Defaults match the in-image layout; overridable so the scaffold can be
# exercised end-to-end from tests against temporary directories.
TEMPLATE_DIR="${TEMPLATE_DIR:-/root/assets/workspace}"
WORKSPACE_DIR="${WORKSPACE_DIR:-/workspace}"
# Authoritative built-tag record baked into the image by the flake (#921): the
# fallback pin source when VIG_OS_VERSION is unset (a raw `podman run ...
# init-workspace.sh` upgrade forwards no env). Overridable for tests.
VERSION_FILE="${VERSION_FILE:-/root/assets/VERSION}"
FORCE=false
NO_PROMPTS=false
SMOKE_TEST=false
PREVIEW=false
# Opt-in removal of a PRE-EXISTING .devcontainer/ in direnv/bare mode (#990).
PRUNE_DEVCONTAINER=false
# Delivery mode: devcontainer | direnv | both | bare. Empty = manifest, prompt, or "both".
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
    # overwrite an existing pyproject.toml. The scaffold is language-neutral and
    # ships none (#929); a Python consumer brings their own (e.g. via the opt-in
    # `nix flake init -t ...#python` template, #930), and it is preserved here.
    "pyproject.toml"
    # The consumer owns its hook configuration (#878): repos carry repo-specific
    # global/per-hook `exclude:` patterns (data tables, generated files, PEM
    # marker literals) that a template overwrite silently destroyed — the hook
    # suite then rewrote files it must never touch. Preserved like
    # justfile.project; the upgrade prints a diff against the template below so
    # hook-stack evolution stays visible.
    ".pre-commit-config.yaml"
    # The consumer owns its spell-check exceptions (#913): repos curate
    # repo-specific extend-words/extend-exclude that a template overwrite
    # silently destroyed, so the typos hook then flagged legitimate domain
    # terms. Preserved like .pre-commit-config.yaml; the upgrade prints a diff
    # against the template below. (Legacy `_typos.toml` handled at copy time.)
    ".typos.toml"
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
        --preview)
            PREVIEW=true
            shift
            ;;
        --prune-devcontainer)
            PRUNE_DEVCONTAINER=true
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
            echo "Usage: init-workspace [--force] [--no-prompts] [--smoke-test] [--preview] [--mode MODE] [--prune-devcontainer]" >&2
            exit 1
            ;;
    esac
done

# Validate delivery mode (empty handled later: prompt, or default to "both").
case "$MODE" in
    ""|devcontainer|direnv|both|bare) ;;
    *)
        echo "Error: Invalid --mode: $MODE (expected: devcontainer | direnv | both | bare)" >&2
        exit 1
        ;;
esac

# Smoke mode must run unattended and allow overwriting existing content.
if [[ "$SMOKE_TEST" == "true" ]]; then
    NO_PROMPTS=true
    FORCE=true
fi

# A preview is by definition of an upgrade (#886): ride the --force report
# path (and pass the "workspace not empty" check) without requiring an
# explicit --force. The preview exits right after the report, before any
# mutation.
if [[ "$PREVIEW" == "true" ]]; then
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

# ── .vig-os project manifest (#885) ───────────────────────────────────────────
# The workspace .vig-os persists the delivery mode, identity, and (reserved)
# capability modules. Read it before any prompt/default so a manifest-bearing
# repo (re)scaffolds its own shape; precedence stays flag/env > .vig-os >
# prompt/default. Same tolerant line-based parsing as every other consumer
# (unknown keys ignored, quotes stripped).

VIG_OS_MANIFEST="$WORKSPACE_DIR/.vig-os"

# Print the value of manifest key $2 in file $1; return 1 when absent.
read_manifest_value() {
    local file="$1" key="$2" line value
    [[ -f "$file" ]] || return 1
    while IFS= read -r line || [[ -n "${line:-}" ]]; do
        [[ -z "${line//[[:space:]]/}" ]] && continue
        [[ "$line" =~ ^[[:space:]]*# ]] && continue
        case "$line" in
            "$key"=*)
                value="${line#*=}"
                value="${value#"${value%%[![:space:]]*}"}"
                value="${value%"${value##*[![:space:]]}"}"
                if [[ "$value" =~ ^\".*\"$ ]]; then
                    value="${value:1:-1}"
                elif [[ "$value" =~ ^\'.*\'$ ]]; then
                    value="${value:1:-1}"
                fi
                [[ -n "$value" ]] || return 1
                echo "$value"
                return 0
                ;;
        esac
    done < "$file"
    return 1
}

# Persist manifest key $1 with value $2 in the scaffolded .vig-os: replace the
# existing line, or append it (self-documenting upgrade of a legacy
# version-only file). Same sed pattern as the #852 version pin.
write_manifest_value() {
    local key="$1" value="$2" value_escaped
    [[ -f "$VIG_OS_MANIFEST" ]] || return 0
    if grep -q "^${key}=" "$VIG_OS_MANIFEST"; then
        value_escaped=$(printf '%s\n' "$value" | sed 's/[&/\]/\\&/g')
        sed -i "s/^${key}=.*/${key}=${value_escaped}/" "$VIG_OS_MANIFEST"
    else
        printf '%s=%s\n' "$key" "$value" >> "$VIG_OS_MANIFEST"
    fi
}

MANIFEST_MODE="$(read_manifest_value "$VIG_OS_MANIFEST" DEVKIT_MODE || true)"
MANIFEST_PROJECT="$(read_manifest_value "$VIG_OS_MANIFEST" DEVKIT_PROJECT || true)"
MANIFEST_ORG="$(read_manifest_value "$VIG_OS_MANIFEST" DEVKIT_ORG || true)"
MANIFEST_REPO="$(read_manifest_value "$VIG_OS_MANIFEST" DEVKIT_REPO || true)"
MANIFEST_MODULES="$(read_manifest_value "$VIG_OS_MANIFEST" DEVKIT_MODULES || true)"

# The OWNER/REPO placeholder (written when no origin was resolvable) must not
# mask a now-detectable git origin on a later upgrade.
[[ "$MANIFEST_REPO" == "OWNER/REPO" ]] && MANIFEST_REPO=""

# A corrupt persisted mode must not silently fall back to "both" — that would
# reshape the repo. Refuse loudly instead.
case "$MANIFEST_MODE" in
    ""|devcontainer|direnv|both|bare) ;;
    *)
        echo "Error: Invalid DEVKIT_MODE in $VIG_OS_MANIFEST: $MANIFEST_MODE (expected: devcontainer | direnv | both | bare)" >&2
        exit 1
        ;;
esac

# Mode switching is destructive (e.g. both -> direnv deletes .devcontainer/)
# and owned by the upgrade-guard flow — it must never happen implicitly. An
# explicit --mode that contradicts the persisted DEVKIT_MODE refuses;
# --preview stays available as the way to inspect a would-be switch first.
# (--smoke-test redeploys a CI checkout from scratch and is exempt.)
if [[ -n "$MODE" && -n "$MANIFEST_MODE" && "$MODE" != "$MANIFEST_MODE" \
    && "$PREVIEW" != "true" && "$SMOKE_TEST" != "true" ]]; then
    echo "Error: requested --mode $MODE contradicts the persisted DEVKIT_MODE=$MANIFEST_MODE in .vig-os." >&2
    echo "" >&2
    echo "Mode switching reshapes the workspace and never happens implicitly:" >&2
    echo "  1. Inspect the would-be change first:  init-workspace --preview --mode $MODE" >&2
    echo "  2. Keep the persisted mode by omitting --mode, or" >&2
    echo "  3. Switch deliberately: set DEVKIT_MODE=$MODE in .vig-os on a dedicated," >&2
    echo "     clean upgrade branch (see the upgrade preflight guard in MIGRATION.md)" >&2
    echo "     and re-run the upgrade." >&2
    exit 1
fi

# Get SHORT_NAME - from env var, manifest, or prompt (#885)
if [[ -z "${SHORT_NAME:-}" && -n "$MANIFEST_PROJECT" ]]; then
    SHORT_NAME="$MANIFEST_PROJECT"
    echo "Project short name from .vig-os manifest: $SHORT_NAME"
fi
if [[ "$NO_PROMPTS" == "true" ]]; then
    # Non-interactive mode: require SHORT_NAME (env var or persisted manifest)
    if [[ -z "${SHORT_NAME:-}" ]]; then
        echo "Error: SHORT_NAME environment variable is required with --no-prompts" >&2
        exit 1
    fi
elif [[ -z "${SHORT_NAME:-}" ]]; then
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

# Get ORG_NAME - from env var, manifest, default, or prompt (#885)
if [[ -z "${ORG_NAME:-}" && -n "$MANIFEST_ORG" ]]; then
    ORG_NAME="$MANIFEST_ORG"
    echo "Organization name from .vig-os manifest: $ORG_NAME"
fi
if [[ "$NO_PROMPTS" == "true" ]]; then
    # Non-interactive mode: env var/manifest, else derive the org from the
    # repo owner already in hand (#954). A hardcoded "vigOS/devc" default is a
    # bogus org — it contains a '/', which sed-substitutes into {{ORG_NAME}} in
    # generated files (e.g. the LICENSE copyright). GITHUB_REPOSITORY (owner/repo)
    # is available on this path (DEVKIT_REPO uses it), so take its owner segment;
    # fall back to a sane literal only when no usable owner/repo is present.
    if [[ -z "${ORG_NAME:-}" ]]; then
        _repo_owner="${GITHUB_REPOSITORY:-}"
        _repo_owner="${_repo_owner%%/*}"
        if [[ -n "$_repo_owner" && "${GITHUB_REPOSITORY:-}" != "OWNER/REPO" ]]; then
            ORG_NAME="$_repo_owner"
        else
            ORG_NAME="vigOS"
        fi
        unset _repo_owner
    fi
elif [[ -z "${ORG_NAME:-}" ]]; then
    # Interactive mode: prompt user
    read -rp "Enter the name of your organization, e.g. 'vigOS': " ORG_NAME
    if [[ -z "$ORG_NAME" ]]; then
        echo "Error: Organization name is required" >&2
        exit 1
    fi
fi
echo "Organization name set to: $ORG_NAME"

# Get MODE - from flag, manifest, inference, prompt, or default (#885).
# Selects which delivery the workspace scaffolds: a devcontainer, the
# Nix/direnv stub, or both. Smoke-test deploys ignore the manifest: they
# redeploy the full template over a CI checkout regardless of the
# checked-in mode.
if [[ -z "$MODE" && -n "$MANIFEST_MODE" && "$SMOKE_TEST" != "true" ]]; then
    MODE="$MANIFEST_MODE"
    echo "Delivery mode from .vig-os manifest: $MODE"
fi

# Legacy consumers (version-only .vig-os, or none) persist no DEVKIT_MODE:
# infer it from the tree shape on upgrade — conservatively (the wider mode
# on ambiguity), transparently (the inference is printed and, when
# interactive, confirmed), and never reshaping the repo: the inferred mode
# matches the shape that is already there. Sets MODE, or leaves it empty
# when the tree carries no mode markers at all.
infer_legacy_mode() {
    local has_devc=false has_direnv=false
    if [[ -d "$WORKSPACE_DIR/.devcontainer" ]] \
        && [[ -n "$(ls -A "$WORKSPACE_DIR/.devcontainer" 2>/dev/null)" ]]; then
        has_devc=true
    fi
    if [[ -f "$WORKSPACE_DIR/flake.nix" || -f "$WORKSPACE_DIR/.envrc" ]]; then
        has_direnv=true
    fi
    if [[ "$has_devc" == "true" && "$has_direnv" == "true" ]]; then
        MODE="both"
        if [[ -f "$WORKSPACE_DIR/flake.nix" ]] \
            && ! grep -q 'vigos.lib.mkProjectShell' "$WORKSPACE_DIR/flake.nix" 2>/dev/null; then
            echo "Note: flake.nix does not look like the scaffold stub (consumer-authored?);"
            echo "      resolving the ambiguity to the wider mode. Your flake.nix/.envrc are"
            echo "      preserved files and stay untouched (#859)."
        fi
    elif [[ "$has_devc" == "true" ]]; then
        MODE="devcontainer"
    elif [[ "$has_direnv" == "true" ]]; then
        MODE="direnv"
    else
        return 0
    fi
    echo "Inferred delivery mode '$MODE' from the existing tree (no DEVKIT_MODE"
    echo "persisted in .vig-os): .devcontainer/ populated: $has_devc, flake.nix/.envrc: $has_direnv."
    echo "The inferred mode will be persisted in .vig-os after the upgrade."
    if [[ "$NO_PROMPTS" != "true" ]]; then
        local reply
        read -rp "Use inferred delivery mode '$MODE'? (Y/n): " reply
        if [[ "$reply" =~ ^[Nn]$ ]]; then
            MODE=""
        fi
    fi
}
if [[ -z "$MODE" && "$FORCE" == "true" && "$SMOKE_TEST" != "true" ]]; then
    infer_legacy_mode
fi

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
        echo "  4) bare         - standards only: justfiles, hooks, CI (no container, no flake)"
        read -rp "Delivery mode [devcontainer/direnv/both/bare] (default: both): " MODE
        MODE="${MODE:-both}"
        case "$MODE" in
            devcontainer|direnv|both|bare) ;;
            *)
                echo "Error: Invalid mode: $MODE (expected: devcontainer | direnv | both | bare)" >&2
                exit 1
                ;;
        esac
    fi
fi
echo "Delivery mode set to: $MODE"

# --prune-devcontainer is only meaningful where the scaffold owns no container
# (#990). In devcontainer/both mode a .devcontainer/ is a first-class deliverable,
# so reject the flag loudly rather than silently ignore it — same failure shape
# as an invalid --mode above.
if [[ "$PRUNE_DEVCONTAINER" == "true" && "$MODE" != "direnv" && "$MODE" != "bare" ]]; then
    echo "Error: --prune-devcontainer only applies to direnv/bare modes (got: $MODE)" >&2
    exit 1
fi

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

# Preview the template-vs-preserved divergence for a preserved consumer file
# (#878, #913). A preserved file never receives template evolution
# automatically, so surface the diff for the consumer to fold in deliberately.
# The image ships git but no diff(1)/cmp(1) (#916): use `git diff --no-index`,
# whose --quiet form gates the block and which exits 1 (the expected "they
# diverged" signal, not an error) when the files differ. Returns 0 when a diff
# was printed (files differ), 1 when identical or either file is missing.
print_preserved_template_diff() {
    local rel="$1"
    local preserved="$WORKSPACE_DIR/$rel"
    local template="$TEMPLATE_DIR/$rel"
    [[ -f "$preserved" && -f "$template" ]] || return 1
    if git diff --no-index --quiet -- "$template" "$preserved" > /dev/null 2>&1; then
        return 1  # identical: nothing to surface
    fi
    echo "Preserved $rel differs from the template (yours was kept)."
    echo "Template changes NOT applied (fold in what you need, see MIGRATION.md):"
    echo "─────────────────────────────────────────────────────────────"
    git diff --no-index -- "$template" "$preserved" || true
    echo "─────────────────────────────────────────────────────────────"
    return 0
}

# Record whether the consumer already had a populated .devcontainer/ before the
# scaffold (#738). In direnv mode we must neither overwrite nor delete it.
# Recorded before the file report below so the DELETED listing (#886) can
# mirror the prune guards; pure reads, nothing is mutated here.
DEVCONTAINER_PREEXISTED=false
if [[ -d "$WORKSPACE_DIR/.devcontainer" ]] \
    && [[ -n "$(ls -A "$WORKSPACE_DIR/.devcontainer" 2>/dev/null)" ]]; then
    DEVCONTAINER_PREEXISTED=true
fi

# Interactive prune offer (#990): on a container→direnv/bare (re)scaffold a
# populated pre-existing .devcontainer/ is kept by default (#738). When the
# operator did not pass --prune-devcontainer, ask once — default No preserves
# the #738 behavior. Resolved here (before the file report below) so the DELETED
# listing mirrors the choice. Skipped under --no-prompts and --preview (a preview
# must stay side-effect-free and decide purely from the flag).
if [[ "$PRUNE_DEVCONTAINER" != "true" && "$DEVCONTAINER_PREEXISTED" == "true" \
    && ( "$MODE" == "direnv" || "$MODE" == "bare" ) \
    && "$NO_PROMPTS" != "true" && "$PREVIEW" != "true" ]]; then
    read -rp "Prune existing .devcontainer/? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        PRUNE_DEVCONTAINER=true
    fi
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

# A preserved .typos.toml is the consumer's spell-check exception set (#913);
# record it so the post-scaffold guard can surface template divergence.
TYPOS_CONFIG_PREEXISTED=false
[[ -f "$WORKSPACE_DIR/.typos.toml" ]] && TYPOS_CONFIG_PREEXISTED=true

# Warn if forcing (prompt user) - show which files would be overwritten
if [[ "$FORCE" == "true" ]]; then
    echo ""
    echo "Checking for files that would be affected..."

    # Classify how each template file lands in the workspace
    CONFLICTS=()
    PRESERVED=()
    ADDED=()
    while IFS= read -r -d '' template_file; do
        # Get relative path from template directory
        rel_path="${template_file#"$TEMPLATE_DIR"/}"
        workspace_file="$WORKSPACE_DIR/$rel_path"

        # Mode filters (#886): skip template paths the chosen delivery mode
        # never scaffolds. direnv and bare modes exclude .devcontainer/ from
        # the copy entirely (#738); devcontainer and bare modes prune the
        # flake.nix/.envrc stubs they would themselves create — unless they
        # pre-exist (#859), in which case they fall through to the PRESERVED
        # listing below.
        if [[ ("$MODE" == "direnv" || "$MODE" == "bare") \
            && "$rel_path" == .devcontainer/* ]]; then
            continue
        fi
        if [[ "$MODE" == "devcontainer" || "$MODE" == "bare" ]] \
            && [[ "$rel_path" == "flake.nix" || "$rel_path" == ".envrc" ]] \
            && [[ ! -e "$workspace_file" ]]; then
            continue
        fi

        if [[ -e "$workspace_file" ]]; then
            if is_preserved_file "$rel_path"; then
                PRESERVED+=("$rel_path")
            else
                CONFLICTS+=("$rel_path")
            fi
        else
            ADDED+=("$rel_path")
        fi
    done < <(find -L "$TEMPLATE_DIR" -type f \
        ! -path "*/.git/*" ! -path "*/.venv/*" \
        ! -path "*/docs/issues/*" ! -path "*/docs/pull-requests/*" -print0)

    # Mode-prune deletions (#886): paths that exist right now and the upgrade
    # would remove. Mirrors the prune guards further down (#738/#859/#877).
    DELETIONS=()
    if [[ "$MODE" == "direnv" || "$MODE" == "bare" ]]; then
        if [[ -e "$WORKSPACE_DIR/.devcontainer" && "$DEVCONTAINER_PREEXISTED" != "true" ]]; then
            DELETIONS+=(".devcontainer/")
        elif [[ "$DEVCONTAINER_PREEXISTED" == "true" && "$PRUNE_DEVCONTAINER" == "true" ]]; then
            # --prune-devcontainer opts into removing a pre-existing container
            # on a container→direnv/bare migration (#990).
            DELETIONS+=(".devcontainer/ (pre-existing, pruned — #990)")
        elif [[ "$DEVCONTAINER_PREEXISTED" == "true" ]]; then
            # The #738 guard keeps a populated consumer .devcontainer/; say so
            # explicitly instead of leaving it silently absent from the report.
            PRESERVED+=(".devcontainer/ (pre-existing, kept — #738)")
        fi
    else
        # The devcontainer-mode flake.nix/.envrc prune only removes stubs this
        # scaffold itself creates (#859), so it never deletes an existing file.
        if [[ -f "$WORKSPACE_DIR/.devcontainer/justfile.base" ]]; then
            DELETIONS+=(".devcontainer/justfile.base")
        fi
    fi

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

    # Show paths the mode prune would delete (#886)
    if [[ ${#DELETIONS[@]} -gt 0 ]]; then
        echo ""
        echo "The following ${#DELETIONS[@]} path(s) will be DELETED:"
        echo "─────────────────────────────────────────────────────────────"
        for deletion in "${DELETIONS[@]}"; do
            echo "  ✗  $deletion"
        done
        echo "─────────────────────────────────────────────────────────────"
        echo ""
    fi

    # Preview mode (#886): also list the files new to the tree, then stop
    # before anything is mutated. The ADDED listing is preview-only so the
    # interactive --force report stays compact.
    if [[ "$PREVIEW" == "true" ]]; then
        if [[ ${#ADDED[@]} -eq 0 ]]; then
            echo ""
            echo "No new files would be added."
        else
            echo ""
            echo "The following ${#ADDED[@]} file(s) will be ADDED:"
            echo "─────────────────────────────────────────────────────────────"
            for added in "${ADDED[@]}"; do
                echo "  +  $added"
            done
            echo "─────────────────────────────────────────────────────────────"
        fi
        echo ""
        echo "Preview complete — no files were changed."
        exit 0
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

# Land the resolved mode/identity into a PRE-EXISTING manifest before the early
# --no-prompts resolution below can abort (#885 + #916). The abort now fires
# before the rsync copy, so the post-copy early write-back would never run on an
# aborted upgrade — a torn legacy upgrade must still leave a truthful DEVKIT_MODE
# (never the template's) so the next --force run does not re-add pruned artifacts.
# A fresh scaffold has no .vig-os yet, so this writes nothing and the workspace
# stays pristine on abort. DEVKIT_REPO is only known after resolution and stays
# in the late write-back.
if [[ -f "$VIG_OS_MANIFEST" ]]; then
    write_manifest_value DEVKIT_MODE "$MODE"
    write_manifest_value DEVKIT_PROJECT "$SHORT_NAME"
    write_manifest_value DEVKIT_ORG "$ORG_NAME"
fi

# Persisted DEVKIT_REPO fills GITHUB_REPOSITORY when the env var is absent or
# still the OWNER/REPO placeholder (#885); an explicit env value wins. This runs
# before the early --no-prompts resolution below (#916) so a manifest-bearing
# upgrade resolves from its own .vig-os instead of aborting for a missing origin.
if [[ -z "${GITHUB_REPOSITORY:-}" || "${GITHUB_REPOSITORY:-}" == "OWNER/REPO" ]] \
    && [[ -n "$MANIFEST_REPO" ]]; then
    GITHUB_REPOSITORY="$MANIFEST_REPO"
    echo "GitHub repository from .vig-os manifest: $GITHUB_REPOSITORY"
fi

# Under --no-prompts, resolve (and validate) the GitHub origin for renovate.json
# BEFORE the first filesystem mutation (#916): a missing/underivable origin must
# abort while the workspace is still pristine, not after rsync has left a
# half-scaffolded tree. In interactive mode the resolution (which prompts) stays
# after the copy, at its original call site below, to preserve prompt ordering.
if [[ "$NO_PROMPTS" == "true" ]]; then
    resolve_github_repository
fi

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
    # Root-anchor each exclude (leading slash) so it matches the exact
    # transfer-root path, not the basename at every depth (#953). Bare names
    # like README.md/CHANGELOG.md protect the consumer's ROOT docs only;
    # without the anchor rsync also skipped devkit-authored NESTED docs
    # (.devcontainer/README.md, .claude/skills/*/README.md), which the preview
    # (is_preserved_file, exact rel-path) still promised as ADDED. The anchor
    # matches is_preserved_file's exact-path semantics.
    EXCLUDE_ARGS=()
    for preserved in "${PRESERVE_FILES[@]}"; do
        if [[ -e "$WORKSPACE_DIR/$preserved" ]]; then
            EXCLUDE_ARGS+=("--exclude=/$preserved")
        fi
    done

    # direnv and bare modes want no .devcontainer/ at all, so never copy the
    # template one over a populated consumer .devcontainer/ (#738). Excluding it
    # from the copy (rather than copying-then-pruning) keeps a real
    # .devcontainer/ intact.
    if [[ "$MODE" == "direnv" || "$MODE" == "bare" ]]; then
        EXCLUDE_ARGS+=("--exclude=.devcontainer")
    fi

    # Legacy typos config (#913): the `typos` tool reads .typos.toml, typos.toml
    # AND _typos.toml. A consumer still carrying _typos.toml (and no .typos.toml)
    # must not also receive the template .typos.toml, or two active configs
    # collide. Skip shipping the template one; their _typos.toml stands as the
    # single config (a preserved .typos.toml is already excluded above).
    if [[ -f "$WORKSPACE_DIR/_typos.toml" && ! -f "$WORKSPACE_DIR/.typos.toml" ]]; then
        echo "Consumer carries legacy _typos.toml; not shipping template .typos.toml (#913)."
        EXCLUDE_ARGS+=("--exclude=.typos.toml")
    fi

    rsync -avL --exclude='.git' --exclude='.venv' "${EXCLUDE_ARGS[@]}" "$TEMPLATE_DIR/" "$WORKSPACE_DIR/"

    # ci.yml is a single mode-aware workflow (#991): it resolves DEVKIT_MODE at
    # run time via the resolve-toolchain job + setup-devkit-toolchain composite,
    # so every mode ships the same file — no per-mode overlay to re-apply.
fi

# The Nix-built image stores the baked template as read-only symlinks into the
# Nix store. The rsync `-L` (--copy-links) above dereferences them into real
# files, but those inherit the store's read-only (0444) mode. Make the scaffold
# user-writable so the placeholder substitution below — and the user's own edits
# — work. No-op on the Debian image (its template files are already writable).
chmod -R u+w "$WORKSPACE_DIR"

# Early write-back (#885): the rsync above just replaced .vig-os with the
# template, so until the late write-back below the manifest would claim the
# template's values instead of this run's. Any abort inside that window
# (e.g. resolve_github_repository under --no-prompts) must not persist a
# state the repo did not choose — the next --force run trusts the manifest.
# Mode and identity are already resolved, so land them now; DEVKIT_REPO is
# only known after resolve_github_repository and stays in the late write-back.
if [[ -f "$VIG_OS_MANIFEST" ]]; then
    write_manifest_value DEVKIT_MODE "$MODE"
    write_manifest_value DEVKIT_PROJECT "$SHORT_NAME"
    write_manifest_value DEVKIT_ORG "$ORG_NAME"
fi

# Prune the scaffold to the chosen delivery mode. Idempotent and safe: only
# removes paths inside the new workspace.
#   devcontainer -> remove the flake.nix + .envrc stub
#   direnv       -> remove the .devcontainer/ scaffold
#   both         -> keep everything
#   bare         -> remove .devcontainer/ AND the flake.nix + .envrc stub
case "$MODE" in
    bare)
        # Standards-only scaffold (#885): prune every container/flake
        # artifact, with the same pre-existence guards as the other modes —
        # consumer-owned files always survive (#738/#859).
        if [[ "$DEVCONTAINER_PREEXISTED" == "true" && "$PRUNE_DEVCONTAINER" != "true" ]]; then
            echo "bare mode: preserving existing .devcontainer/ (#738)"
        else
            if [[ "$DEVCONTAINER_PREEXISTED" == "true" ]]; then
                echo "bare mode: pruning pre-existing .devcontainer/ (--prune-devcontainer, #990)..."
            else
                echo "Pruning to 'bare' mode: removing .devcontainer/..."
            fi
            rm -rf "$WORKSPACE_DIR/.devcontainer"
        fi
        if [[ "$FLAKE_PREEXISTED" == "true" ]]; then
            echo "bare mode: preserving existing flake.nix (#859)"
        else
            echo "Pruning to 'bare' mode: removing flake.nix..."
            rm -f "$WORKSPACE_DIR/flake.nix"
        fi
        if [[ "$ENVRC_PREEXISTED" == "true" ]]; then
            echo "bare mode: preserving existing .envrc (#859)"
        else
            echo "Pruning to 'bare' mode: removing .envrc..."
            rm -f "$WORKSPACE_DIR/.envrc"
        fi
        ;;
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
        if [[ "$DEVCONTAINER_PREEXISTED" == "true" && "$PRUNE_DEVCONTAINER" != "true" ]]; then
            echo "direnv mode: preserving existing .devcontainer/ (#738)"
        else
            if [[ "$DEVCONTAINER_PREEXISTED" == "true" ]]; then
                echo "direnv mode: pruning pre-existing .devcontainer/ (--prune-devcontainer, #990)..."
            else
                echo "Pruning to 'direnv' mode: removing .devcontainer/..."
            fi
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
# .devcontainer/: a direnv- or bare-mode consumer's own .devcontainer/ is
# never touched (#738).
if [[ "$MODE" != "direnv" && "$MODE" != "bare" \
    && -f "$WORKSPACE_DIR/.devcontainer/justfile.base" ]]; then
    echo "Removing retired .devcontainer/justfile.base (recipes live in justfile.project since 0.4.0)..."
    rm -f "$WORKSPACE_DIR/.devcontainer/justfile.base"
fi

# Pin the explicitly requested devcontainer version (#852). The image bakes
# the release it was built from into the scaffolded .vig-os (flake bootstrap),
# which is correct for finals but stale for release candidates: the repo-root
# pin only advances at finalize. install.sh forwards its --version here so the
# scaffold pins the image actually installed.
#
# Fall back to the image's authoritative built-tag record when no explicit
# override was forwarded (#921): a raw `podman run ... init-workspace.sh`
# upgrade (no install.sh) sets no VIG_OS_VERSION, so read the baked $VERSION_FILE
# to stamp the image's real tag instead of the stale baked template pin. When
# the record is absent (older image) or empty, VIG_OS_VERSION stays unset and
# the pin is left untouched — unchanged behavior. An explicit env override wins.
if [[ -z "${VIG_OS_VERSION:-}" && -f "$VERSION_FILE" ]]; then
    VIG_OS_VERSION="$(tr -d '[:space:]' < "$VERSION_FILE")"
    if [[ -n "$VIG_OS_VERSION" ]]; then
        echo "Using image built-tag record: $VIG_OS_VERSION"
    fi
fi

if [[ -n "${VIG_OS_VERSION:-}" && -f "$WORKSPACE_DIR/.vig-os" ]]; then
    if [[ ! "$VIG_OS_VERSION" =~ ^[A-Za-z0-9._-]+$ ]]; then
        echo "Error: invalid VIG_OS_VERSION: $VIG_OS_VERSION" >&2
        exit 1
    fi
    echo "Pinning DEVKIT_VERSION=${VIG_OS_VERSION} in .vig-os..."
    # Rewrite whichever version key the manifest carries to the renamed
    # DEVKIT_VERSION, so a stray legacy DEVCONTAINER_VERSION line is migrated
    # rather than left stale (#781).
    sed -i -E "s/^(DEVKIT_VERSION|DEVCONTAINER_VERSION)=.*/DEVKIT_VERSION=${VIG_OS_VERSION}/" "$WORKSPACE_DIR/.vig-os"
fi

# Interactive origin resolution (the renovate.json owner/repo prompt) runs here,
# after the copy, to keep the prompt ordering consumers and the integration
# tests expect. Under --no-prompts this already resolved before the copy (#916),
# so this call is a no-op then (GITHUB_REPOSITORY is set, possibly from the
# .vig-os manifest fallback applied before the copy, #885).
if [[ "$NO_PROMPTS" != "true" ]]; then
    resolve_github_repository
fi

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

# Persist the resolved manifest (#885). The scaffolded .vig-os is a managed
# file (template-overwritten on upgrade), so the resolved delivery mode and
# identity are written back on every (re)scaffold — the next upgrade then
# needs no mode/identity flags at all. A consumer's DEVKIT_MODULES
# declaration (#884, read before the template overwrite) is restored too.
if [[ -f "$VIG_OS_MANIFEST" ]]; then
    echo "Persisting resolved manifest values in .vig-os..."
    write_manifest_value DEVKIT_MODE "$MODE"
    write_manifest_value DEVKIT_PROJECT "$SHORT_NAME"
    write_manifest_value DEVKIT_ORG "$ORG_NAME"
    write_manifest_value DEVKIT_REPO "$GITHUB_REPOSITORY"
    if [[ -n "$MANIFEST_MODULES" ]]; then
        write_manifest_value DEVKIT_MODULES "\"$MANIFEST_MODULES\""
    fi
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
if [[ "$PRECOMMIT_CONFIG_PREEXISTED" == "true" ]] \
    && print_preserved_template_diff ".pre-commit-config.yaml"; then
    if command -v prek > /dev/null 2>&1; then
        if ! (cd "$WORKSPACE_DIR" && prek validate-config .pre-commit-config.yaml > /dev/null 2>&1); then
            echo "Warning: preserved .pre-commit-config.yaml does not validate under prek (#878)." >&2
            echo "         Every commit will fail until it parses — run 'prek validate-config .pre-commit-config.yaml' and fix it." >&2
        fi
    fi
fi

# A preserved .typos.toml is the consumer's (#913) — never overwritten, so
# their spell-check exceptions survive; the cost is that template exception
# evolution no longer arrives automatically. Print the divergence so consumers
# can fold in what they need deliberately. Non-fatal, like the #878 guard.
if [[ "$TYPOS_CONFIG_PREEXISTED" == "true" ]]; then
    print_preserved_template_diff ".typos.toml" || true
fi

# The retired `pre-commit` binary (#778) exits 127 at first use: a preserved
# justfile.project recipe, a consumer-owned .githooks script, or a hook entry
# in the preserved .pre-commit-config.yaml that still invokes it breaks even
# after a clean re-scaffold — the image ships prek plus a one-cycle compat
# shim (removed in 0.5). Scan the post-scaffold state of those surfaces for
# invocation-shaped references and warn with file:line (#881). Non-fatal,
# like the #877/#878 guards. The pattern only matches `pre-commit` framed as
# a command word (start/whitespace/shell punctuation on both sides), so the
# config FILENAME (leading `.`), pre-commit-hooks repo URLs (leading `/`),
# pre-commit.com links (trailing `.`), and `prek` never trip it; comment
# lines, bare YAML stage-name list items (`- pre-commit`), and YAML `name:`
# step descriptions (a workflow's "Run pre-commit hooks" step name, #916) are
# filtered. Preserved consumer CI workflows are scanned too (#916): a workflow
# that still runs the retired binary breaks the same way as a justfile recipe.
PRECOMMIT_REF_PATTERN='(^|[[:space:]("'"'"';&|=`])pre-commit([[:space:])"'"'"';&|]|$)'
PRECOMMIT_SCAN_TARGETS=()
for scan_file in "$WORKSPACE_DIR/justfile.project" "$WORKSPACE_DIR/.pre-commit-config.yaml"; do
    [[ -f "$scan_file" ]] && PRECOMMIT_SCAN_TARGETS+=("$scan_file")
done
while IFS= read -r scan_file; do
    PRECOMMIT_SCAN_TARGETS+=("$scan_file")
done < <({ find "$WORKSPACE_DIR/.githooks" -type f 2>/dev/null
          find "$WORKSPACE_DIR/.github/workflows" -maxdepth 1 -type f \
              \( -name '*.yml' -o -name '*.yaml' \) 2>/dev/null; } | sort)
PRECOMMIT_REF_HITS=""
if [[ ${#PRECOMMIT_SCAN_TARGETS[@]} -gt 0 ]]; then
    PRECOMMIT_REF_HITS="$(grep -nHE "$PRECOMMIT_REF_PATTERN" "${PRECOMMIT_SCAN_TARGETS[@]}" 2>/dev/null \
        | grep -vE '^[^:]*:[0-9]+:[[:space:]]*#' \
        | grep -vE '^[^:]*:[0-9]+:[[:space:]]*-[[:space:]]+pre-commit[[:space:]]*$' \
        | grep -vE '^[^:]*:[0-9]+:[[:space:]]*(-[[:space:]]+)?name:' || true)"
fi
if [[ -n "$PRECOMMIT_REF_HITS" ]]; then
    echo "Warning: the retired 'pre-commit' binary is still invoked by preserved file(s) (#881):" >&2
    printf '%s\n' "$PRECOMMIT_REF_HITS" | sed "s|^$WORKSPACE_DIR/|         |" >&2
    echo "         The image ships 'prek' (drop-in for run-style invocations); a temporary" >&2
    echo "         pre-commit->prek shim keeps these working through 0.4.x only — it is" >&2
    echo "         removed in 0.5. Rename the invocations to 'prek' (see MIGRATION.md," >&2
    echo "         'Upgrading an existing 0.3.x consumer')." >&2
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
