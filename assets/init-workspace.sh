#!/bin/bash
# Initialize workspace by copying template files
#
# Usage: init-workspace [--force] [--no-prompts] [--smoke-test] [--preview] [--mode MODE] [--workflow MODEL] [--prune-devcontainer]
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
#   --workflow MODEL  Workflow model: gitflow | trunk (#1205)
#                 gitflow  long-lived dev + main with sync-main-to-dev.yml (default)
#                 trunk    feature/bugfix/chore straight to main; releases fork
#                          release/X.Y.Z from main and merge back into main; the
#                          dev branch and sync-main-to-dev.yml disappear
#                 Unset: read DEVKIT_WORKFLOW from the workspace .vig-os manifest,
#                 else default to gitflow
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
# Workflow model: gitflow | trunk. Empty = manifest, or the gitflow default (#1205).
WORKFLOW_MODEL=""

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
    # Mutating counterpart to release-extension.yml (#1059): consumers replace
    # this no-op with release-branch preparation, so an upgrade must never
    # clobber their implementation — same preserved class as release-extension.
    ".github/workflows/prepare-release-extension.yml"
    "justfile.project"
    # Personal, gitignored recipes (#1054): the file's own header promises it is
    # preserved on upgrade, but it was absent here — so a re-scaffold silently
    # overwrote personal recipes. Align the mechanism with the promise (same
    # silent-clobber class as justfile.project/#878/#913).
    "justfile.local"
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
    # The consumer owns its lint-rule exceptions (#1099): repos add repo-specific
    # yamllint `ignore:` globs / rule disables and pymarkdown rule tweaks that a
    # template overwrite silently destroyed, so the hook then flagged legitimate
    # content. Preserved like .typos.toml; the upgrade prints a diff against the
    # template below so lint-rule evolution stays visible. `.pymarkdown` is the
    # strict-JSON config pymarkdown actually reads (md0xx rule settings); like
    # renovate.json it carries no banner but is preserved all the same, while
    # `.pymarkdown.config.md` is its human-readable doc companion.
    ".yamllint"
    ".pymarkdown"
    ".pymarkdown.config.md"
    # The consumer owns its repo-ROOT ignores (#1092): the managed root
    # .gitignore is overwritten on every upgrade, and git honors a repo-root
    # ignore only from that root .gitignore — so there was no durable committed
    # home for root-level ignores. .gitignore.project is that home (mirroring
    # justfile.project): preserved here, and its contents are appended to the
    # regenerated .gitignore by render_gitignore below so they survive upgrades.
    ".gitignore.project"
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
        --workflow)
            WORKFLOW_MODEL="$2"
            shift 2
            ;;
        --workflow=*)
            WORKFLOW_MODEL="${1#--workflow=}"
            shift
            ;;
        *)
            echo "Unknown option: $1" >&2
            echo "Usage: init-workspace [--force] [--no-prompts] [--smoke-test] [--preview] [--mode MODE] [--workflow MODEL] [--prune-devcontainer]" >&2
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

# Validate the workflow model (empty resolves from manifest/default later, #1205).
case "$WORKFLOW_MODEL" in
    ""|gitflow|trunk) ;;
    *)
        echo "::error::Invalid --workflow: $WORKFLOW_MODEL (expected: gitflow | trunk)" >&2
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

# Validate a 5-field cron expression (minute hour day-of-month month
# day-of-week). A loose per-field charset check — digits, `*`, ranges, steps,
# and lists — that rejects the wrong field count and stray characters so a
# malformed DEVKIT_SYNC_SCHEDULE fails loudly at scaffold time rather than
# silently disabling the schedule in GitHub Actions (#1228).
is_valid_cron() {
    local expr="$1" field
    local -a fields
    read -ra fields <<< "$expr"
    [[ ${#fields[@]} -eq 5 ]] || return 1
    for field in "${fields[@]}"; do
        [[ "$field" =~ ^[0-9A-Za-z*,/-]+$ ]] || return 1
    done
    return 0
}

MANIFEST_MODE="$(read_manifest_value "$VIG_OS_MANIFEST" DEVKIT_MODE || true)"
MANIFEST_PROJECT="$(read_manifest_value "$VIG_OS_MANIFEST" DEVKIT_PROJECT || true)"
MANIFEST_ORG="$(read_manifest_value "$VIG_OS_MANIFEST" DEVKIT_ORG || true)"
MANIFEST_REPO="$(read_manifest_value "$VIG_OS_MANIFEST" DEVKIT_REPO || true)"
MANIFEST_MODULES="$(read_manifest_value "$VIG_OS_MANIFEST" DEVKIT_MODULES || true)"
MANIFEST_TAG_PREFIX="$(read_manifest_value "$VIG_OS_MANIFEST" DEVKIT_TAG_PREFIX || true)"
MANIFEST_FLOATING_TAGS="$(read_manifest_value "$VIG_OS_MANIFEST" DEVKIT_FLOATING_TAGS || true)"
MANIFEST_CI_RUNNER="$(read_manifest_value "$VIG_OS_MANIFEST" DEVKIT_CI_RUNNER || true)"
MANIFEST_WORKFLOW="$(read_manifest_value "$VIG_OS_MANIFEST" DEVKIT_WORKFLOW || true)"
MANIFEST_SYNC_TARGET="$(read_manifest_value "$VIG_OS_MANIFEST" DEVKIT_SYNC_TARGET || true)"
MANIFEST_SYNC_SCHEDULE="$(read_manifest_value "$VIG_OS_MANIFEST" DEVKIT_SYNC_SCHEDULE || true)"

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

# A corrupt persisted workflow model must not silently fall back to gitflow —
# that would reshape the release topology. Refuse loudly (mirrors DEVKIT_MODE).
case "$MANIFEST_WORKFLOW" in
    ""|gitflow|trunk) ;;
    *)
        echo "Error: Invalid DEVKIT_WORKFLOW in $VIG_OS_MANIFEST: $MANIFEST_WORKFLOW (expected: gitflow | trunk)" >&2
        exit 1
        ;;
esac

# Switching the workflow model reshapes the release topology (trunk drops the
# dev branch + sync-main-to-dev.yml) and, like a mode switch, must never happen
# implicitly. An explicit --workflow that contradicts the persisted
# DEVKIT_WORKFLOW refuses; --preview inspects the would-be switch first.
# (--smoke-test redeploys a CI checkout from scratch and is exempt.)
if [[ -n "$WORKFLOW_MODEL" && -n "$MANIFEST_WORKFLOW" && "$WORKFLOW_MODEL" != "$MANIFEST_WORKFLOW" \
    && "$PREVIEW" != "true" && "$SMOKE_TEST" != "true" ]]; then
    echo "Error: requested --workflow $WORKFLOW_MODEL contradicts the persisted DEVKIT_WORKFLOW=$MANIFEST_WORKFLOW in .vig-os." >&2
    echo "" >&2
    echo "Switching the workflow model reshapes the release topology and never happens implicitly:" >&2
    echo "  1. Inspect the would-be change first:  init-workspace --preview --workflow $WORKFLOW_MODEL" >&2
    echo "  2. Keep the persisted model by omitting --workflow, or" >&2
    echo "  3. Switch deliberately: set DEVKIT_WORKFLOW=$WORKFLOW_MODEL in .vig-os on a dedicated," >&2
    echo "     clean upgrade branch and re-run the upgrade." >&2
    exit 1
fi

# sync-issues target branch (#1228): the value is spliced into single-quoted
# YAML, sed replacement text, and the bootstrap step's double-quoted shell
# assignment (executed at sync runtime with the App token in scope) — so the
# LOAD-BEARING guard is a strict charset allowlist. git check-ref-format alone
# is NOT enough: it accepts quotes, `$`, backticks, `;`, `|`, `#`, `&` … which
# would render invalid YAML, crash the render seds, or inject commands. The
# ref-format check is kept on top to also refuse git-illegal shapes the
# allowlist admits (e.g. `bad..name`, a trailing `/` or `.lock`). Pure
# `.vig-os` key (no CLI flag), so only format guards — no contradiction guard
# as for --mode / --workflow.
if [[ -n "$MANIFEST_SYNC_TARGET" ]]; then
    if [[ ! "$MANIFEST_SYNC_TARGET" =~ ^[A-Za-z0-9._/-]+$ ]] \
        || ! git check-ref-format "refs/heads/$MANIFEST_SYNC_TARGET" >/dev/null 2>&1; then
        echo "Error: Invalid DEVKIT_SYNC_TARGET in $VIG_OS_MANIFEST: $MANIFEST_SYNC_TARGET (expected a valid git branch name using only [A-Za-z0-9._/-])" >&2
        exit 1
    fi
fi

# sync-issues schedule (#1228): validate the 5-field cron loudly — a bad cron
# silently disables the schedule trigger in GitHub Actions.
if [[ -n "$MANIFEST_SYNC_SCHEDULE" ]] && ! is_valid_cron "$MANIFEST_SYNC_SCHEDULE"; then
    echo "Error: Invalid DEVKIT_SYNC_SCHEDULE in $VIG_OS_MANIFEST: $MANIFEST_SYNC_SCHEDULE (expected a 5-field cron expression, e.g. '0 2 * * *')" >&2
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

# Resolve the workflow model (#1205): explicit --workflow > persisted
# DEVKIT_WORKFLOW > the gitflow default. Smoke deploys ignore the manifest
# (they redeploy the full template over a CI checkout), mirroring DEVKIT_MODE.
# trunk is realized entirely at scaffold time (render_workflow_model + the
# sync-main-to-dev copy-exclude); gitflow is the unchanged default and a no-op.
if [[ -z "$WORKFLOW_MODEL" && -n "$MANIFEST_WORKFLOW" && "$SMOKE_TEST" != "true" ]]; then
    WORKFLOW_MODEL="$MANIFEST_WORKFLOW"
    echo "Workflow model from .vig-os manifest: $WORKFLOW_MODEL"
fi
WORKFLOW_MODEL="${WORKFLOW_MODEL:-gitflow}"
echo "Workflow model set to: $WORKFLOW_MODEL"

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

# Helper: a path is "present" in the workspace if it exists as a resolvable
# target OR is a symlink of any kind — including a DANGLING one (#1117). In
# direnv mode a flake-hooks consumer's .pre-commit-config.yaml is a symlink into
# the HOST /nix/store, which is not mounted inside the image where this script
# runs, so `-e` alone (it follows the link) reports the symlink absent. Every
# presence gate that decides whether to preserve/classify/track such a file must
# see the symlink itself, so the rsync copy never clobbers it and the #1092
# ignore seed (which reads the still-present symlink's target) still fires.
path_present() {
    [[ -e "$1" || -L "$1" ]]
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
#
# `git diff --no-index` needs no repository, yet git first DISCOVERS a repo from
# the cwd. When the workspace is a git worktree (bare `podman run -v` mount), its
# `.git` is a FILE pointing at a gitdir outside the mount; discovery fails and
# the diff aborts with `fatal: not a git repository: (null)` before comparing
# (#1197). `GIT_DIR=/dev/null` pins the git dir explicitly, so git skips
# discovery entirely and the pure file comparison runs regardless of any
# broken/foreign `.git` in the cwd.
print_preserved_template_diff() {
    local rel="$1"
    local preserved="$WORKSPACE_DIR/$rel"
    local template="$TEMPLATE_DIR/$rel"
    [[ -f "$preserved" && -f "$template" ]] || return 1
    if GIT_DIR=/dev/null git diff --no-index --quiet -- "$template" "$preserved" \
        > /dev/null 2>&1; then
        return 1  # identical: nothing to surface
    fi
    echo "Preserved $rel differs from the template (yours was kept)."
    echo "Template changes NOT applied (fold in what you need, see MIGRATION.md):"
    echo "─────────────────────────────────────────────────────────────"
    GIT_DIR=/dev/null git diff --no-index -- "$template" "$preserved" || true
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
# path_present, not -f: a flake-hooks consumer's config is a dangling store
# symlink (#1117), which -f (it follows the link) would miss.
path_present "$WORKSPACE_DIR/.pre-commit-config.yaml" && PRECOMMIT_CONFIG_PREEXISTED=true

# A preserved .typos.toml is the consumer's spell-check exception set (#913);
# record it so the post-scaffold guard can surface template divergence.
TYPOS_CONFIG_PREEXISTED=false
[[ -f "$WORKSPACE_DIR/.typos.toml" ]] && TYPOS_CONFIG_PREEXISTED=true

# Preserved lint configs are the consumer's rule exceptions (#1099); record them
# so the post-scaffold guard can surface template divergence.
YAMLLINT_CONFIG_PREEXISTED=false
[[ -f "$WORKSPACE_DIR/.yamllint" ]] && YAMLLINT_CONFIG_PREEXISTED=true
PYMARKDOWN_CONFIG_PREEXISTED=false
[[ -f "$WORKSPACE_DIR/.pymarkdown" ]] && PYMARKDOWN_CONFIG_PREEXISTED=true
PYMARKDOWN_DOC_PREEXISTED=false
[[ -f "$WORKSPACE_DIR/.pymarkdown.config.md" ]] && PYMARKDOWN_DOC_PREEXISTED=true

# Snapshot the consumer's OLD root .gitignore before the rsync overwrite (#1111).
# Root .gitignore is managed (NOT a PRESERVE_FILE), so rsync replaces it below;
# capture it now so migrate_root_gitignore can recover any root ignores the
# consumer had hand-added directly to it (they predate the #1092 durable home,
# .gitignore.project, and would otherwise be silently dropped on the upgrade that
# introduces it). Empty on a fresh scaffold (no old file) — the migration no-ops.
OLD_GITIGNORE_SNAPSHOT=""
[[ -f "$WORKSPACE_DIR/.gitignore" ]] && OLD_GITIGNORE_SNAPSHOT="$(cat "$WORKSPACE_DIR/.gitignore")"

# ── consumer language detection (#1024/#1025) ─────────────────────────────────
# Managed scaffold statics (.gitignore, .github/workflows/codeql.yml) are
# Python-shaped by default, which is wrong for Node/Rust consumers and does not
# survive an upgrade (both files are overwritten). Detect the consumer's
# language(s) from marker files present in the workspace BEFORE the template
# copy (rsync never removes them: pyproject.toml is preserved, package.json and
# Cargo.toml are not in the template), then render those statics per-language
# after the copy. Detection re-runs on every (re)scaffold, so the result is
# upgrade-persistent. Empty when no marker is present (language-neutral repo).
DETECTED_LANGUAGES=()
[[ -f "$WORKSPACE_DIR/pyproject.toml" ]] && DETECTED_LANGUAGES+=("python")
[[ -f "$WORKSPACE_DIR/package.json" ]] && DETECTED_LANGUAGES+=("node")
[[ -f "$WORKSPACE_DIR/Cargo.toml" ]] && DETECTED_LANGUAGES+=("rust")
# nix (#1171): a repo is nix-oriented when it carries *.nix files BEYOND the
# scaffold-managed ./flake.nix (excluding .git/, .direnv/, .worktrees/).
# flake.nix alone cannot be the marker: every direnv scaffold ships one, so
# naive detection would false-positive on every direnv consumer at re-scaffold
# time. The beyond-flake.nix rule is deterministic and re-scaffold-safe.
if find "$WORKSPACE_DIR" \
    -path "$WORKSPACE_DIR/.git" -prune -o \
    -path "$WORKSPACE_DIR/.direnv" -prune -o \
    -path "$WORKSPACE_DIR/.worktrees" -prune -o \
    -name '*.nix' ! -path "$WORKSPACE_DIR/flake.nix" -print -quit \
    | grep -q .; then
    DETECTED_LANGUAGES+=("nix")
fi

# Seed npm-mapped justfile.project recipes on the FIRST scaffold of a Node
# consumer (#1027). justfile.project is a PRESERVE_FILE: the stock template
# ships uv/pyproject recipes, so a Node repo's `just sync` / `just test` (which
# ci.yml calls in every mode) would no-op against `uv`. When `node` is detected
# AND the consumer had no justfile.project before this scaffold (the template
# copy above just placed the default), replace that fresh default with the Node
# seed — `sync` = `npm ci`, plus lint/test/build (tsc)/bundle (ncc). Guarded on
# JUSTFILE_PROJECT_PREEXISTED so an EXISTING consumer-owned justfile.project is
# NEVER touched (same preserve semantics as the #877 repair path). The seed
# lives beside init-workspace.sh in the image ($SCRIPT_DIR), so it is an
# install-time input; it carries the same {{SHORT_NAME}} token the template
# does and is placed BEFORE the substitution pass so that pass resolves it. A
# full replacement (not an append like the .gitignore fragments): appending npm
# recipes onto the uv template would redeclare recipe names and break `just`.
seed_node_justfile_project() {
    local seed="$SCRIPT_DIR/justfile.d/node.justfile.project"
    local dst="$WORKSPACE_DIR/justfile.project"
    # Only on a first scaffold (never over a consumer-owned file) of a Node repo.
    [[ "$JUSTFILE_PROJECT_PREEXISTED" == "true" ]] && return 0
    [[ -f "$seed" && -f "$dst" ]] || return 0
    local lang is_node=false
    for lang in ${DETECTED_LANGUAGES[@]+"${DETECTED_LANGUAGES[@]}"}; do
        [[ "$lang" == "node" ]] && is_node=true
    done
    [[ "$is_node" == "true" ]] || return 0
    echo "Seeding npm-mapped justfile.project recipes for the Node consumer (#1027)..."
    cp "$seed" "$dst"
}

# Render the managed .gitignore as the language-neutral base (already copied
# from the template) plus one appended fragment per detected language (#1024).
# The fragments live beside init-workspace.sh in the image ($SCRIPT_DIR), never
# under the template, so they are install-time inputs and never leak into the
# consumer tree. No-op when the base or a fragment is absent.
render_gitignore() {
    local gi="$WORKSPACE_DIR/.gitignore"
    [[ -f "$gi" ]] || return 0
    local lang frag
    for lang in ${DETECTED_LANGUAGES[@]+"${DETECTED_LANGUAGES[@]}"}; do
        frag="$SCRIPT_DIR/gitignore.d/$lang.gitignore"
        if [[ -f "$frag" ]]; then
            printf '\n' >>"$gi"
            cat "$frag" >>"$gi"
        fi
    done

    # Consumer-owned durable root ignores (#1092): .gitignore.project is a
    # PRESERVE_FILE — the only committed home git honors for repo-ROOT ignores,
    # since git reads root ignores solely from this regenerated root .gitignore.
    # Append its contents LAST so consumer entries survive every regeneration.
    local proj="$WORKSPACE_DIR/.gitignore.project"
    if [[ -f "$proj" ]]; then
        printf '\n' >>"$gi"
        cat "$proj" >>"$gi"
    fi

    # flake-hooks opt-in seed (#1092): a consumer that opts into flake-generated
    # hooks (hooks = { } in flake.nix) gets .pre-commit-config.yaml installed as
    # a /nix/store symlink, which must be ignored — committing it pushes a
    # machine-local, broken symlink. Seed the ignore automatically, gated
    # STRICTLY on the store-symlink condition so a hand-managed consumer who
    # commits a real .pre-commit-config.yaml file is never affected. A fresh
    # direnv scaffold defaults to flake-generated hooks (FLAKE_HOOKS_DEFAULT,
    # #1167) before the store symlink exists, so seed the ignore for it too.
    # Idempotent: skip when the assembled ignore (incl. .gitignore.project)
    # already lists it.
    local pcc="$WORKSPACE_DIR/.pre-commit-config.yaml"
    if { [[ -L "$pcc" ]] && readlink "$pcc" | grep -q '/nix/store/'; } \
        || [[ "${FLAKE_HOOKS_DEFAULT:-false}" == "true" ]]; then
        if ! grep -qxF '.pre-commit-config.yaml' "$gi"; then
            {
                printf '\n# flake-hooks opt-in (#1092): the generated'
                printf ' .pre-commit-config.yaml is a\n'
                printf '# /nix/store symlink — never commit it.\n'
                printf '.pre-commit-config.yaml\n'
            } >>"$gi"
        fi
    fi
}

# Turn a freshly-scaffolded direnv flake.nix into a flake-hooks generator (#1167)
# by activating an empty `hooks = { }` argument to mkProjectShell. The direnv CI
# lane runs on the bare host runner (resolve-toolchain emits an empty container
# image), so the shared flake hook set — resolved entirely from the Nix store,
# including pymarkdown now that it is a flake system hook (#1170) — is more
# robust there than the committed YAML, which builds its remote pre-commit repo
# hook envs (pre-commit-hooks, yamllint) per runner. Deterministic single insert
# after the (unique) extraPackages line — a bats regression guard pins that
# anchor. Only ever called on a FRESH scaffold (guarded by the caller).
activate_flake_hooks_default() {
    local flake="$WORKSPACE_DIR/flake.nix"
    [[ -f "$flake" ]] || return 0
    local tmp="${flake}.hooks-default"
    awk '
        { print }
        /^          extraPackages = extraPackages pkgs;$/ && !inserted {
            print ""
            print "          # Host-runner hooks (#1167): direnv CI runs on the bare host"
            print "          # runner, so let the flake GENERATE .pre-commit-config.yaml from"
            print "          # the shared base hook set, resolved entirely from the Nix store"
            print "          # (incl. pymarkdown, now a flake system hook, #1170) rather than"
            print "          # building the committed YAML remote pre-commit repo hook envs"
            print "          # per runner. Customize like the opt-in block below; the generated"
            print "          # config is a gitignored /nix/store symlink."
            print "          hooks = { };"
            inserted = 1
        }
    ' "$flake" >"$tmp" && mv "$tmp" "$flake"
}

# Migrate consumer-added root ignores into .gitignore.project (#1111). The #1092
# fix made .gitignore.project the durable, preserved home for repo-ROOT ignores,
# but the upgrade that INTRODUCES it seeds it empty — so any ignores a consumer
# had hand-added directly to the managed root .gitignore (.DS_Store, editor/OS
# cruft, project paths) are silently dropped when render_gitignore regenerates
# root .gitignore from the template. Recover them: any non-blank, non-comment
# line in the pre-overwrite root .gitignore (OLD_GITIGNORE_SNAPSHOT) that is NOT
# a managed entry (template base + ALL language fragments + the #1092 seed), NOT
# a scaffold-committed file, and NOT already in .gitignore.project is appended
# to .gitignore.project, whence
# render_gitignore (called AFTER this) folds it back into the regenerated root
# .gitignore — no separate write to the root file. Append-only and deduplicated
# against the existing .gitignore.project, so a second upgrade re-adds nothing
# (idempotent: the migrated lines now live in .gitignore.project) and the
# consumer's existing entries are never reordered or rewritten. Only entries
# (non-blank, non-comment lines) migrate; a consumer's free-text comments are not
# semantically ignorable, so they are left behind with the old managed file.
#
# Two never-migrate rules (#1145, field report vig-os/sync-issues-action#106):
#  1. Scaffold-COMMITTED files (.envrc & co.) never migrate: an old template's
#     ignore entry for one (the pre-#640 Python template shipped `.envrc`)
#     would shadow the file the scaffold itself commits — e.g. keep the
#     committed .envrc untracked and silently break direnv onboarding on every
#     clone. These are literal file names, not glob patterns, so a plain
#     literal match on the line is enough — no variant handling.
#  2. The managed set is built from ALL gitignore.d fragments, not just the
#     detected languages': the OLD root .gitignore was a devkit-managed
#     template for whatever language set applied back then, so any line found
#     in ANY devkit fragment is template material, not consumer-authored — a
#     repo that switched language templates must not inherit the stale
#     fragment's lines as "consumer" entries.
migrate_root_gitignore() {
    local proj="$WORKSPACE_DIR/.gitignore.project"
    [[ -f "$proj" ]] || return 0
    [[ -n "$OLD_GITIGNORE_SNAPSHOT" ]] || return 0

    local line frag
    # Managed entries the regenerated root .gitignore already provides — never
    # migrate one of these (idempotent even for a line the template later drops).
    local -A managed=()
    while IFS= read -r line; do
        [[ "$line" =~ ^[[:space:]]*$ || "$line" =~ ^[[:space:]]*# ]] && continue
        managed["$line"]=1
    done < "$TEMPLATE_DIR/.gitignore"
    # ALL fragments, not just the detected languages' (#1145 rule 2): the old
    # root .gitignore may be a stale template of a language this repo no longer
    # markers for — its fragment lines are template material, never consumer's.
    for frag in "$SCRIPT_DIR"/gitignore.d/*.gitignore; do
        [[ -f "$frag" ]] || continue
        while IFS= read -r line; do
            [[ "$line" =~ ^[[:space:]]*$ || "$line" =~ ^[[:space:]]*# ]] && continue
            managed["$line"]=1
        done < "$frag"
    done
    # The #1092 flake-hooks seed is a managed entry too.
    managed[".pre-commit-config.yaml"]=1
    # Never-migrate denylist (#1145 rule 1): files the scaffold itself COMMITS.
    # Migrating an old template's ignore entry for one of these would shadow the
    # committed file (e.g. `.envrc` from the pre-#640 Python template keeps the
    # scaffolded .envrc untracked and breaks direnv onboarding). Literal file
    # names, so a plain literal line match suffices.
    local entry
    for entry in .envrc .gitignore.project flake.nix flake.lock \
        justfile justfile.project .vig-os; do
        managed["$entry"]=1
    done

    # Entries already committed in .gitignore.project must not be re-added — this
    # is what makes a second upgrade a no-op.
    local -A existing=()
    while IFS= read -r line; do
        [[ "$line" =~ ^[[:space:]]*$ || "$line" =~ ^[[:space:]]*# ]] && continue
        existing["$line"]=1
    done < "$proj"

    # Consumer-added lines: present in the old root .gitignore, owned by neither
    # the managed sources nor .gitignore.project. Deduplicated, order preserved.
    local -a migrate=()
    local -A seen=()
    while IFS= read -r line; do
        [[ "$line" =~ ^[[:space:]]*$ || "$line" =~ ^[[:space:]]*# ]] && continue
        [[ -n "${managed[$line]:-}" ]] && continue
        [[ -n "${existing[$line]:-}" ]] && continue
        [[ -n "${seen[$line]:-}" ]] && continue
        seen["$line"]=1
        migrate+=("$line")
    done <<< "$OLD_GITIGNORE_SNAPSHOT"

    [[ ${#migrate[@]} -eq 0 ]] && return 0

    {
        printf '\n# Migrated from the managed root .gitignore on upgrade (#1111).\n'
        printf '%s\n' "${migrate[@]}"
    } >> "$proj"
    echo "Migrated ${#migrate[@]} consumer line(s) into .gitignore.project (#1111):"
    printf '  %s\n' "${migrate[@]}"
}

# Rewrite the managed CodeQL language matrix to the detected language(s) (#1025):
# python -> 'python', node -> 'javascript-typescript', rust -> omitted (CodeQL
# ships no first-class Rust analyzer). 'actions' is always analyzed, so the
# matrix is never empty (a marker-less repo analyzes just actions). No-op when
# the workflow is absent (e.g. it was never scaffolded or was pruned).
#
# The push-to-main trigger's `paths:` filter is rendered from the SAME detection
# (#1142): a python source push must match '**.py', a node one '**.ts'/'**.js'/
# '**.mjs'/'**.cjs'; rust has no CodeQL source leg so it adds no source globs.
# The '.github/workflows/**' catch-all is always kept (the 'actions' leg always
# runs). Left hardcoded to '**.py', a Node consumer's post-merge scan never fired
# for TS/JS changes — and being a managed file, hand-fixes were reverted on every
# upgrade.
render_codeql_matrix() {
    local cq="$WORKSPACE_DIR/.github/workflows/codeql.yml"
    [[ -f "$cq" ]] || return 0
    local -a langs=()
    local -a paths=()
    local lang
    for lang in ${DETECTED_LANGUAGES[@]+"${DETECTED_LANGUAGES[@]}"}; do
        case "$lang" in
            python)
                langs+=("'python'")
                paths+=("'**.py'")
                ;;
            node)
                langs+=("'javascript-typescript'")
                paths+=("'**.ts'" "'**.js'" "'**.mjs'" "'**.cjs'")
                ;;
            rust) : ;; # CodeQL rust support caveat (#1025): omit the leg
            nix) : ;; # nix is not a CodeQL language (#1171): omit the leg
        esac
    done
    langs+=("'actions'")
    paths+=("'.github/workflows/**'")
    local joined=""
    for lang in "${langs[@]}"; do
        joined="${joined:+$joined, }$lang"
    done
    sed -i -E "s|^([[:space:]]*language:).*|\1 [${joined}]|" "$cq"
    echo "Rendered CodeQL language matrix: [${joined}]"

    # Replace the list items under the push `paths:` key (4-space `paths:`,
    # 6-space `- ` items) with the rendered set. awk, not sed: the item count
    # varies per language, so we rewrite the whole block in one pass.
    local rendered_paths
    rendered_paths="$(printf '      - %s\n' "${paths[@]}")"
    awk -v items="$rendered_paths" '
        /^    paths:$/ { print; print items; inpaths = 1; next }
        inpaths && /^      - / { next }
        inpaths { inpaths = 0 }
        { print }
    ' "$cq" >"$cq.tmp" && mv "$cq.tmp" "$cq"
    echo "Rendered CodeQL push paths filter: [${paths[*]}]"
    # Preflight note (#1025): the advanced CodeQL config the scaffold ships
    # cannot coexist with GitHub's *default* code-scanning setup — its uploads
    # are rejected while default setup is enabled. We never flip that API
    # setting; the consumer disables default setup deliberately.
    echo "Note: this advanced CodeQL config conflicts with GitHub's default"
    echo "      code-scanning setup — disable default setup (Settings -> Code"
    echo "      security -> Code scanning) or the uploads reject (#1025). This"
    echo "      scaffold does not change your repo's code-scanning API setting."
}

# Mode- and config-dependent copy excludes (#1196): the single source of truth
# for template paths the rsync copy skips for reasons OTHER than the preserve
# list. BOTH the --preview ADDED classification and the real rsync copy below
# consult this array, so --preview never advertises a file the copy silently
# skips (exo-pet/vault#31). Entries are exact transfer-root rel-paths; a
# directory entry (.devcontainer) covers its whole subtree.
MODE_CONFIG_EXCLUDES=()
# direnv and bare modes carry no .devcontainer/ (#738) and no in-image CI notes
# (docs/container-ci-quirks.md, #989); a previously scaffolded copy of either is
# pruned after the copy (see the DELETIONS block below).
if [[ "$MODE" == "direnv" || "$MODE" == "bare" ]]; then
    MODE_CONFIG_EXCLUDES+=(".devcontainer" "docs/container-ci-quirks.md")
fi
# Legacy typos config (#913): the `typos` tool reads .typos.toml AND _typos.toml.
# A consumer still carrying _typos.toml (and no .typos.toml) keeps it as the
# single config — do not also ship the template .typos.toml, or two active
# configs collide. (A *preserved* .typos.toml is handled by the preserve list.)
if [[ -f "$WORKSPACE_DIR/_typos.toml" && ! -f "$WORKSPACE_DIR/.typos.toml" ]]; then
    MODE_CONFIG_EXCLUDES+=(".typos.toml")
fi

# Rewrite the scaffolded workspace from the gitflow default shape (long-lived
# `dev` + `main` + sync-main-to-dev.yml) to the trunk shape (`main` only) when
# the resolved DEVKIT_WORKFLOW is `trunk` (#1205). A pure no-op for gitflow (the
# default), so a gitflow scaffold is byte-for-byte unchanged. Sibling of
# render_codeql_matrix: an anchored dev->main retarget applied AFTER the rsync
# copy. Every `dev` in these files is a plain branch literal (or an inert
# step-name/comment), so this is an anchored retarget, not a structural rewrite
# and not a workflow twin. sync-main-to-dev.yml is removed by the copy-exclude
# (EXCLUDE_ARGS) + upgrade prune below, not here.
#
# Anchoring is load-bearing: `heads/dev\b` (word boundary) never touches
# `development`/`devkit`/`devcontainer`; `ref: dev$` / ` from dev$` are
# end-anchored. /dev/null device paths and the dev_sha/DEV_SHA variable names
# are deliberately preserved (behavior is unaffected by their spelling).
render_workflow_model() {
    local model="$1"
    [[ "$model" == "trunk" ]] || return 0

    local wf="$WORKSPACE_DIR/.github/workflows"

    # prepare-release.yml — retarget the release base dev -> main (#590/#617
    # logic is base-agnostic) and scrub the inert dev step-names/comments so a
    # trunk repo carries no `dev` cruft (variable names + /dev/null stay intact).
    local pr="$wf/prepare-release.yml"
    if [[ -f "$pr" ]]; then
        # Behavioral branch literals: checkout refs + REST ref reads + targets.
        sed -i -E 's|^([[:space:]]*ref:) dev$|\1 main|' "$pr"
        sed -i -E 's|heads/dev\b|heads/main|g' "$pr"
        sed -i -E 's| from dev$| from main|' "$pr"
        # Inert step names + comments (no behavior change; the branch literals
        # above are what drive the retarget).
        sed -i 's|Checkout dev branch|Checkout main branch|' "$pr"
        sed -i 's|Capture pre-prepare dev SHA|Capture pre-prepare main SHA|' "$pr"
        sed -i 's| to dev via API| to main via API|g' "$pr"
        sed -i 's|Wait for dev to advance|Wait for main to advance|' "$pr"
        sed -i 's|freeze commit-action updates dev|freeze commit-action updates main|' "$pr"
        sed -i 's|dev still at pre-freeze SHA|main still at pre-freeze SHA|' "$pr"
        sed -i 's|ERROR: dev did not advance|ERROR: main did not advance|' "$pr"
        sed -i 's|CHANGELOG.md on dev|CHANGELOG.md on main|g' "$pr"
        # The #590 rationale comment describes the gitflow main/dev sync merge,
        # which does not exist in trunk — reword it (full-line anchored swaps).
        sed -i 's|dated release, matching$|dated release, so the|' "$pr"
        sed -i 's|# dev, so the section is stable common context in the eventual main/dev$|# section stays stable and can never be silently dropped (#590) even as|' "$pr"
        sed -i 's|# sync merge and can never be silently dropped.*Keep a Changelog$|# releases land directly on main. Keep a Changelog|' "$pr"
    fi

    # promote-release.yml — no behavioral `dev` literals, but two comments name
    # sync-main-to-dev, which is copy-excluded in trunk (EXCLUDE_ARGS). Drop the
    # parentheticals so a trunk repo carries no prose referencing a workflow it
    # does not have (#1233; comments only, no behavior change).
    local prom="$wf/promote-release.yml"
    if [[ -f "$prom" ]]; then
        sed -i 's| (triggers sync-main-to-dev)||' "$prom"
        sed -i 's| (sync-main-to-dev may run next)||' "$prom"
    fi

    # ci.yml — drop `- dev` from the PR branch filter; retarget the commit-gate
    # TRUNK anchor used to exclude already-merged history on release PRs. Also
    # scrub the inert prose: the trigger-header comment and the origin/dev
    # commit-gate rationale so a trunk repo carries no lying `dev` comments
    # (#1226; no behavior change — comments only).
    local ci="$wf/ci.yml"
    if [[ -f "$ci" ]]; then
        sed -i '/^      - dev$/d' "$ci"
        sed -i 's|TRUNK="dev"|TRUNK="main"|' "$ci"
        sed -i 's|Pull requests to dev, release/\*\*, and main|Pull requests to release/** and main|' "$ci"
        sed -i 's|origin/dev — a no-op on a dev PR|origin/main — a no-op on a main PR|' "$ci"
        sed -i 's|(its base IS dev)|(its base IS main)|' "$ci"
    fi

    # codeql.yml — drop `- dev` from the PR branch filter (push is main-only)
    # and scrub the trigger-header comment prose dev -> main (#1226).
    local cq="$wf/codeql.yml"
    if [[ -f "$cq" ]]; then
        sed -i '/^      - dev$/d' "$cq"
        sed -i 's|Pull requests to dev, release/\*\*, and main|Pull requests to release/** and main|' "$cq"
    fi

    # sync-issues.yml — default target branch + `|| 'dev'` fallbacks dev -> main,
    # plus the illustrative `e.g., dev, …` description text so no stray `dev`
    # prose survives (#1226).
    local si="$wf/sync-issues.yml"
    if [[ -f "$si" ]]; then
        sed -i -E "s|^([[:space:]]*default:) 'dev'\$|\1 'main'|" "$si"
        sed -i "s#|| 'dev'#|| 'main'#g" "$si"
        sed -i 's|e.g., dev, release/x.y.z|e.g., main, release/x.y.z|' "$si"
    fi

    # branch-naming SKILL.md — base-branch default dev -> main. (Single-quoted
    # sed so the Markdown backticks stay literal; the `chore/sync-main-to-dev`
    # example on another line is a branch NAME, not a base default, and stays.)
    local skill="$WORKSPACE_DIR/.claude/skills/branch-naming/SKILL.md"
    if [[ -f "$skill" ]]; then
        # shellcheck disable=SC2016  # literal Markdown backticks, not command substitution
        sed -i 's|fall back to `dev`|fall back to `main`|' "$skill"
        # shellcheck disable=SC2016  # literal Markdown backticks, not command substitution
        sed -i 's|use `dev` as|use `main` as|' "$skill"
    fi

    # .pre-commit-config.yaml — drop the `(?!dev$)` protect-clause + its comments
    # (main stays protected; trunk has no long-lived dev branch to protect).
    local pc="$WORKSPACE_DIR/.pre-commit-config.yaml"
    if [[ -f "$pc" ]]; then
        sed -i 's|# Allows main, dev, and|# Allows main and|' "$pc"
        sed -i 's|main/dev are not protected|main is not protected|' "$pc"
        sed -i 's|(?!dev$)||' "$pc"
    fi

    echo "Rendered workflow model: trunk (anchored dev -> main retarget)"
}

# Render the sync-issues.yml knobs (#1228): the commit target branch
# (DEVKIT_SYNC_TARGET) and the schedule cron (DEVKIT_SYNC_SCHEDULE). Runs AFTER
# render_workflow_model, so a custom target overrides the workflow-model default
# already in the file (dev for gitflow / main for trunk). Both are no-ops when
# their manifest key is unset, so an unconfigured workspace stays byte-for-byte
# unchanged. When a custom target is set — a protected-main mirror branch such as
# sync/issue-mirror (#1227) — the job also gains a bootstrap step that creates the
# branch from the default branch head if absent; the mirror diverges permanently
# and is never merged back (each sync regenerates full state).
render_sync_settings() {
    local si="$WORKSPACE_DIR/.github/workflows/sync-issues.yml"
    [[ -f "$si" ]] || return 0

    # Schedule override: the file carries a single `- cron: '…'` line.
    if [[ -n "$MANIFEST_SYNC_SCHEDULE" ]]; then
        local cron_esc
        cron_esc=$(printf '%s' "$MANIFEST_SYNC_SCHEDULE" | sed 's/[&\]/\\&/g')
        sed -i -E "s|^([[:space:]]*- cron:) '[^']*'\$|\1 '${cron_esc}'|" "$si"
    fi

    # Target-branch override: replace the workflow-model default (dev/main,
    # already rendered above) with the consumer's mirror branch, then inject the
    # bootstrap step so the subsequent checkout of the (possibly absent) branch
    # succeeds.
    if [[ -n "$MANIFEST_SYNC_TARGET" ]]; then
        local model_default="dev"
        [[ "$WORKFLOW_MODEL" == "trunk" ]] && model_default="main"
        local tgt_esc
        tgt_esc=$(printf '%s' "$MANIFEST_SYNC_TARGET" | sed 's/[&/\]/\\&/g')
        sed -i -E "s|^([[:space:]]*default:) '${model_default}'\$|\1 '${tgt_esc}'|" "$si"
        sed -i "s#|| '${model_default}'#|| '${tgt_esc}'#g" "$si"

        # Insert the bootstrap step right after the app-token step (its
        # `private-key:` line is unique — the sync action uses `app-private-key:`),
        # before the checkout. `sed r` appends the block file after the match.
        local block
        block="$(mktemp)"
        cat > "$block" <<YAML

      - name: Bootstrap sync target branch if absent
        env:
          GH_TOKEN: \${{ steps.generate-token.outputs.token }}
        run: |
          set -euo pipefail
          TARGET="\${{ github.event.inputs.target-branch || '${MANIFEST_SYNC_TARGET}' }}"
          if gh api "repos/\${{ github.repository }}/git/ref/heads/\${TARGET}" >/dev/null 2>&1; then
            echo "Sync target branch '\${TARGET}' already exists."
          else
            echo "Sync target branch '\${TARGET}' absent — creating it from the default branch head."
            DEFAULT_BRANCH="\$(gh api "repos/\${{ github.repository }}" --jq .default_branch)"
            SHA="\$(gh api "repos/\${{ github.repository }}/git/ref/heads/\${DEFAULT_BRANCH}" --jq .object.sha)"
            gh api "repos/\${{ github.repository }}/git/refs" -f "ref=refs/heads/\${TARGET}" -f "sha=\${SHA}"
          fi
YAML
        sed -i "/^          private-key: /r $block" "$si"
        rm -f "$block"
    fi

    echo "Rendered sync-issues settings (target=${MANIFEST_SYNC_TARGET:-default}, schedule=${MANIFEST_SYNC_SCHEDULE:-default})"
}

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

        # Mode/config copy excludes (#1196): skip the template paths the real
        # rsync copy skips for the resolved mode and the consumer's config
        # (.devcontainer/ #738, docs/container-ci-quirks.md #989, the legacy
        # .typos.toml #913), so --preview never lists them as ADDED. SSoT:
        # MODE_CONFIG_EXCLUDES, also consumed by the rsync copy below; a
        # directory entry (.devcontainer) matches its whole subtree.
        skip_excluded=false
        for excl in "${MODE_CONFIG_EXCLUDES[@]}"; do
            if [[ "$rel_path" == "$excl" || "$rel_path" == "$excl"/* ]]; then
                skip_excluded=true
                break
            fi
        done
        if [[ "$skip_excluded" == "true" ]]; then
            continue
        fi
        # trunk workflow model (#1205): sync-main-to-dev.yml is copy-excluded, so
        # it never lands in a trunk workspace — keep the report truthful (a
        # leftover copy on a gitflow->trunk upgrade is listed under DELETIONS).
        if [[ "$WORKFLOW_MODEL" == "trunk" \
            && "$rel_path" == ".github/workflows/sync-main-to-dev.yml" ]]; then
            continue
        fi
        # Devcontainer and bare modes prune the flake.nix/.envrc stubs they would
        # themselves create — unless they pre-exist (#859), in which case they
        # fall through to the PRESERVED listing below. This is a post-copy prune,
        # not an rsync exclude, so it stays separate from MODE_CONFIG_EXCLUDES.
        if [[ "$MODE" == "devcontainer" || "$MODE" == "bare" ]] \
            && [[ "$rel_path" == "flake.nix" || "$rel_path" == ".envrc" ]] \
            && [[ ! -e "$workspace_file" ]]; then
            continue
        fi

        # path_present, not -e: a dangling store symlink (#1117) at a preserved
        # path exists in the tree and must classify as PRESERVED, not ADDED.
        if path_present "$workspace_file"; then
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
        # Container-only documentation is pruned in the container-less modes
        # (#989): devkit-managed, so no pre-existence guard — mirrors the copy
        # filter above.
        if [[ -f "$WORKSPACE_DIR/docs/container-ci-quirks.md" ]]; then
            DELETIONS+=("docs/container-ci-quirks.md")
        fi
    else
        # The devcontainer-mode flake.nix/.envrc prune only removes stubs this
        # scaffold itself creates (#859), so it never deletes an existing file.
        if [[ -f "$WORKSPACE_DIR/.devcontainer/justfile.base" ]]; then
            DELETIONS+=(".devcontainer/justfile.base")
        fi
    fi

    # trunk workflow model (#1205): a gitflow->trunk upgrade removes the
    # now-excluded sync-main-to-dev.yml (mirrors the .devcontainer/ deletion).
    # Mode-independent, so it sits outside the mode if/else above.
    if [[ "$WORKFLOW_MODEL" == "trunk" \
        && -f "$WORKSPACE_DIR/.github/workflows/sync-main-to-dev.yml" ]]; then
        DELETIONS+=(".github/workflows/sync-main-to-dev.yml")
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
        # trunk workflow model (#1205): the copied release workflows are
        # rendered dev -> main after the copy, so call it out in the preview.
        if [[ "$WORKFLOW_MODEL" == "trunk" ]]; then
            echo ""
            echo "Workflow model: trunk — the release workflows are rendered from the"
            echo "dev base to main (prepare-release/ci/codeql/sync-issues), along with"
            echo "the branch-naming skill and the pre-commit branch guard."
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
    # path_present, not -e: a preserved path that is a symlink of any kind —
    # including a dangling store symlink (#1117) — must be excluded from the
    # copy, or `rsync -avL` dereferences and writes a real template file over it.
    EXCLUDE_ARGS=()
    for preserved in "${PRESERVE_FILES[@]}"; do
        if path_present "$WORKSPACE_DIR/$preserved"; then
            EXCLUDE_ARGS+=("--exclude=/$preserved")
        fi
    done

    # Mode/config copy excludes (#1196): the same SSoT the --preview ADDED report
    # consults (MODE_CONFIG_EXCLUDES) — so preview and copy never disagree —
    # covering the mode-pruned .devcontainer/ (#738) and container-ci-quirks.md
    # (#989) plus the legacy .typos.toml (#913). Root-anchored (leading slash) to
    # match is_preserved_file's exact transfer-root semantics (#953); a directory
    # entry (.devcontainer) excludes its whole subtree. Excluding these from the
    # copy (rather than copying-then-pruning) keeps a real .devcontainer/ intact.
    for excl in "${MODE_CONFIG_EXCLUDES[@]}"; do
        EXCLUDE_ARGS+=("--exclude=/$excl")
        # Surface the otherwise-silent legacy-typos skip so the consumer knows
        # their _typos.toml stands as the single config (#913).
        if [[ "$excl" == ".typos.toml" ]]; then
            echo "Consumer carries legacy _typos.toml; not shipping template .typos.toml (#913)."
        fi
    done

    # trunk workflow model (#1205): the long-lived dev branch and its sync
    # workflow disappear, so a trunk workspace never receives
    # sync-main-to-dev.yml (a leftover copy is pruned after the copy below).
    if [[ "$WORKFLOW_MODEL" == "trunk" ]]; then
        EXCLUDE_ARGS+=("--exclude=/.github/workflows/sync-main-to-dev.yml")
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

# Container-only documentation (#989): prune a previously scaffolded
# docs/container-ci-quirks.md from the container-less modes. Devkit-managed
# (never in PRESERVE_FILES), so no pre-existence guard — the rsync above
# already excludes the template copy; this removes an old scaffold's leftover.
if [[ ("$MODE" == "direnv" || "$MODE" == "bare") \
    && -f "$WORKSPACE_DIR/docs/container-ci-quirks.md" ]]; then
    echo "Pruning container-only docs/container-ci-quirks.md (#989)..."
    rm -f "$WORKSPACE_DIR/docs/container-ci-quirks.md"
fi

# trunk workflow model (#1205): prune a sync-main-to-dev.yml left by a prior
# gitflow scaffold on a gitflow->trunk upgrade. The rsync above already excludes
# the template copy; this removes the upgrade leftover. Devkit-managed (never in
# PRESERVE_FILES), so no pre-existence guard — mirrors the container-docs prune.
if [[ "$WORKFLOW_MODEL" == "trunk" \
    && -f "$WORKSPACE_DIR/.github/workflows/sync-main-to-dev.yml" ]]; then
    echo "Pruning sync-main-to-dev.yml for the trunk workflow model (#1205)..."
    rm -f "$WORKSPACE_DIR/.github/workflows/sync-main-to-dev.yml"
fi

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

    # Flake pin / DEVKIT_VERSION lockstep skew warning (#1093). For direnv/flake
    # consumers the scaffold and the pinned `vigos` flake input deliver coupled
    # halves of the same change (e.g. #1053's JSONC banner is written by the
    # scaffold, but its compensating check-json exclude lives in nix/hooks.nix,
    # delivered through the flake input). Bumping only the scaffold while a pinned
    # `vigos` ref lags behind silently breaks every commit. We cannot fix it for
    # the consumer — flake.nix is a PRESERVE_FILE they own — but we can warn.
    # A FLOATING input (no ?ref=) is intentionally unpinned, so it never warns;
    # only a pin that differs from the target does.
    if [[ "$FORCE" == "true" && ( "$MODE" == "direnv" || "$MODE" == "both" ) \
        && -f "$WORKSPACE_DIR/flake.nix" ]]; then
        # `|| true`: a floating input yields no grep match (exit 1), which would
        # abort under `set -o pipefail`; an empty pinned_ref is the intended
        # "unpinned, no warning" signal.
        # Anchor on `^[[:space:]]*vigos\.url` so we read the REAL input line only:
        # the standard-layout flake.nix ships a doc-comment EXAMPLE line
        # (`#   vigos.url = "github:vig-os/devkit?ref=<tag>";`) above it, and an
        # unanchored match picked that comment first, reporting the literal
        # `<tag>` and false-firing even on an aligned pin (#1110).
        pinned_ref="$(grep -oE '^[[:space:]]*vigos\.url[[:space:]]*=[[:space:]]*"github:vig-os/devkit\?ref=[^"]+"' \
            "$WORKSPACE_DIR/flake.nix" 2>/dev/null \
            | sed -E 's/.*\?ref=([^"]+)".*/\1/' | head -n1 || true)"
        if [[ -n "$pinned_ref" && "$pinned_ref" != "$VIG_OS_VERSION" ]]; then
            echo "" >&2
            echo "WARNING: scaffold upgraded to ${VIG_OS_VERSION}, but the pinned vigos flake input is still ${pinned_ref}." >&2
            echo "         The two must move together — they deliver coupled halves of the same" >&2
            echo "         change (e.g. #1053's JSONC banner + its check-json exclude). Update your" >&2
            echo "         flake.nix to 'vigos.url = \"github:vig-os/devkit?ref=${VIG_OS_VERSION}\";' and run" >&2
            echo "         'nix flake update vigos', else strict hooks may reject files this scaffold wrote." >&2
            echo "" >&2
        fi
    fi
fi

# Interactive origin resolution (the renovate.json owner/repo prompt) runs here,
# after the copy, to keep the prompt ordering consumers and the integration
# tests expect. Under --no-prompts this already resolved before the copy (#916),
# so this call is a no-op then (GITHUB_REPOSITORY is set, possibly from the
# .vig-os manifest fallback applied before the copy, #885).
if [[ "$NO_PROMPTS" != "true" ]]; then
    resolve_github_repository
fi

# Seed the Node justfile.project on a first scaffold BEFORE the substitution
# pass below, so the seed's {{SHORT_NAME}} token is resolved like every other
# managed file (the seed replaces the freshly-copied template at the same path,
# which the manifest already lists as carrying the token). No-op for non-Node
# consumers and for an existing (preserved) justfile.project. Refs #1027.
seed_node_justfile_project

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

# Host-runner hooks default (#1167): a FRESH direnv scaffold defaults to
# flake-generated pre-commit hooks. The direnv CI lane runs on the bare host
# runner (empty container image), where the shared flake hook set — resolved
# from the Nix store, including pymarkdown now that it is a flake system hook
# (#1170) — is more robust than the committed YAML's per-runner remote
# pre-commit repo hook env builds. Runs BEFORE render_gitignore so the generated config is
# ignored from the first scaffold. Gated on a fresh scaffold: never rewrite a
# consumer's own flake.nix nor delete a committed .pre-commit-config.yaml (both
# PRESERVE_FILES). bare mode is out of scope — it prunes flake.nix (no generator)
# and the consumer owns its own toolchain there.
FLAKE_HOOKS_DEFAULT=false
if [[ "$MODE" == "direnv" && "$FLAKE_PREEXISTED" == "false" \
    && "$PRECOMMIT_CONFIG_PREEXISTED" == "false" ]]; then
    activate_flake_hooks_default
    rm -f "$WORKSPACE_DIR/.pre-commit-config.yaml"
    FLAKE_HOOKS_DEFAULT=true
    echo "direnv mode: defaulting to flake-generated pre-commit hooks (#1167)"
fi

# Render the language-aware managed statics (#1024/#1025) from the freshly
# copied template, keyed on the languages detected before the copy. Runs on
# every (re)scaffold, so the correct .gitignore / codeql matrix is
# upgrade-persistent. These files carry no placeholders, so ordering after the
# substitution above is incidental.
migrate_root_gitignore
render_gitignore
render_codeql_matrix
# trunk workflow model (#1205): retarget the copied release workflows dev ->
# main. A no-op for the gitflow default, so a gitflow scaffold is unchanged.
render_workflow_model "$WORKFLOW_MODEL"
# sync-issues knobs (#1228): override the target branch + schedule cron on top of
# the workflow-model default. A no-op when both keys are unset.
render_sync_settings

# Persist the resolved manifest (#885). The scaffolded .vig-os is a managed
# file (template-overwritten on upgrade), so the resolved delivery mode and
# identity are written back on every (re)scaffold — the next upgrade then
# needs no mode/identity flags at all. A consumer's DEVKIT_MODULES
# declaration (#884, read before the template overwrite) is restored too, as
# are the DEVKIT_TAG_PREFIX / DEVKIT_FLOATING_TAGS release tag-scheme keys
# (#1116, read before the overwrite) and the DEVKIT_CI_RUNNER runner override
# (#1173) — the template ships them empty, so without a write-back an upgrade
# would silently reset a consumer's tag scheme or self-hosted runner selection.
if [[ -f "$VIG_OS_MANIFEST" ]]; then
    echo "Persisting resolved manifest values in .vig-os..."
    write_manifest_value DEVKIT_MODE "$MODE"
    write_manifest_value DEVKIT_PROJECT "$SHORT_NAME"
    write_manifest_value DEVKIT_ORG "$ORG_NAME"
    write_manifest_value DEVKIT_REPO "$GITHUB_REPOSITORY"
    if [[ -n "$MANIFEST_MODULES" ]]; then
        write_manifest_value DEVKIT_MODULES "\"$MANIFEST_MODULES\""
    fi
    # Bare in the template (DEVKIT_TAG_PREFIX= / DEVKIT_FLOATING_TAGS=), so
    # written back bare — matching the template's unquoted form.
    if [[ -n "$MANIFEST_TAG_PREFIX" ]]; then
        write_manifest_value DEVKIT_TAG_PREFIX "$MANIFEST_TAG_PREFIX"
    fi
    if [[ -n "$MANIFEST_FLOATING_TAGS" ]]; then
        write_manifest_value DEVKIT_FLOATING_TAGS "$MANIFEST_FLOATING_TAGS"
    fi
    # CI runner override (#1173): bare in the template (DEVKIT_CI_RUNNER=), so a
    # self-hosted consumer's label list is read before the overwrite and written
    # back — else an upgrade silently resets ci.yml onto the hosted default.
    if [[ -n "$MANIFEST_CI_RUNNER" ]]; then
        write_manifest_value DEVKIT_CI_RUNNER "$MANIFEST_CI_RUNNER"
    fi
    # Workflow model (#1205): the template ships DEVKIT_WORKFLOW= (empty =
    # gitflow default), so only a trunk consumer needs a written-back value — a
    # gitflow repo's .vig-os stays byte-identical (no new non-empty line), the
    # same conditional-writeback shape as DEVKIT_TAG_PREFIX above.
    if [[ "$WORKFLOW_MODEL" == "trunk" ]]; then
        write_manifest_value DEVKIT_WORKFLOW "$WORKFLOW_MODEL"
    fi
    # sync-issues knobs (#1228): bare in the template (DEVKIT_SYNC_TARGET= /
    # DEVKIT_SYNC_SCHEDULE=), so a consumer's mirror branch + cron override are
    # written back — else an upgrade silently resets the sync job onto the
    # workflow-model default branch and the daily cron.
    if [[ -n "$MANIFEST_SYNC_TARGET" ]]; then
        write_manifest_value DEVKIT_SYNC_TARGET "$MANIFEST_SYNC_TARGET"
    fi
    if [[ -n "$MANIFEST_SYNC_SCHEDULE" ]]; then
        write_manifest_value DEVKIT_SYNC_SCHEDULE "$MANIFEST_SYNC_SCHEDULE"
    fi
fi

# Restore executable permissions on shell scripts and hooks (must be after sed -i).
# Scope the +x to the scaffold-delivered script set only: key the sweep on the
# template's .sh files, not a blanket `find "$WORKSPACE_DIR"`. A consumer's own
# sourced-only .sh libraries are not template paths, so a blanket sweep wrongly
# flipped their mode (644 → 755) on every --force re-scaffold (#1195).
echo "Setting executable permissions on shell scripts and hooks..."
while IFS= read -r -d '' template_script; do
    rel="${template_script#"$TEMPLATE_DIR"/}"
    [[ -f "$WORKSPACE_DIR/$rel" ]] && chmod +x "$WORKSPACE_DIR/$rel"
done < <(find -L "$TEMPLATE_DIR" -type f -name "*.sh" -print0)
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

# Preserved lint configs are the consumer's (#1099) — never overwritten, so
# their yamllint/pymarkdown rule exceptions survive; the cost is that template
# rule evolution no longer arrives automatically. Print the divergence so
# consumers can fold in what they need deliberately. Non-fatal, like the #913 guard.
if [[ "$YAMLLINT_CONFIG_PREEXISTED" == "true" ]]; then
    print_preserved_template_diff ".yamllint" || true
fi
if [[ "$PYMARKDOWN_CONFIG_PREEXISTED" == "true" ]]; then
    print_preserved_template_diff ".pymarkdown" || true
fi
if [[ "$PYMARKDOWN_DOC_PREEXISTED" == "true" ]]; then
    print_preserved_template_diff ".pymarkdown.config.md" || true
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
# project. Two mode-aware behaviors (#1118):
#   * direnv/bare: skip entirely — the consumer's host nix/direnv shell owns
#     dependency install; a container-side `just sync` (e.g. `npm ci`) would
#     write wrong-platform, wrong-owner artifacts into the bind-mounted workspace.
#   * devcontainer/both: run it, but non-fatally — the scaffold is already
#     complete, so a sync failure warns and continues rather than aborting init
#     with a misleading "Failed to initialize workspace".
# Also non-fatal (#859): a preserved old-generation justfile.project may not
# define `sync` yet — warn and let the consumer sync after migrating recipes.
if [[ "$MODE" == "direnv" || "$MODE" == "bare" ]]; then
    echo "Skipping dependency sync for $MODE mode; your nix/direnv shell installs" \
         "dependencies (a container-side 'just sync' would write wrong-platform" \
         "node_modules into the bind mount)."
else
    echo "Syncing dependencies..."
    cd "$WORKSPACE_DIR"
    if just --show sync > /dev/null 2>&1; then
        just sync || echo "Warning: dependency sync failed; the scaffold itself is complete — run 'just sync' manually." >&2
    else
        echo "Warning: no 'sync' recipe found (preserved pre-0.4.0 justfile.project?)." >&2
        echo "         Run 'uv sync' manually after migrating your recipes (see MIGRATION.md)." >&2
    fi
fi

echo "Workspace initialized successfully!"
echo ""
echo "You can now start developing in your workspace."
