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
    # against the template below. (The alternate spellings the `typos` tool also
    # reads — legacy `_typos.toml` and undotted `typos.toml` — are handled at
    # copy time, #913/#1280.)
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
MANIFEST_FEATURES_DISABLED="$(read_manifest_value "$VIG_OS_MANIFEST" DEVKIT_FEATURES_DISABLED || true)"

MANIFEST_REFS_POLICY="$(read_manifest_value "$VIG_OS_MANIFEST" DEVKIT_REFS_POLICY || true)"
MANIFEST_COMMIT_TYPES="$(read_manifest_value "$VIG_OS_MANIFEST" DEVKIT_COMMIT_TYPES || true)"
MANIFEST_BRANCH_TYPES="$(read_manifest_value "$VIG_OS_MANIFEST" DEVKIT_BRANCH_TYPES || true)"

# devkit-upgrade knobs (#1296): runtime-only keys consumed by the scaffolded
# devkit-upgrade.yml at run time (not rendered here) — read them solely to write
# them back below, so an upgrade preserves a consumer's opt-out / exclusions.
MANIFEST_AUTO_UPGRADE="$(read_manifest_value "$VIG_OS_MANIFEST" DEVKIT_AUTO_UPGRADE || true)"
MANIFEST_UPGRADE_EXCLUDE="$(read_manifest_value "$VIG_OS_MANIFEST" DEVKIT_UPGRADE_EXCLUDE || true)"
MANIFEST_DRIFT_CHECK="$(read_manifest_value "$VIG_OS_MANIFEST" DEVKIT_DRIFT_CHECK || true)"

# Declared project languages (#1478): read before the template overwrite, both to
# seed the sticky declaration further down and to write it back — the template
# ships the key empty, so without the read an upgrade would erase the declaration.
MANIFEST_LANGUAGES="$(read_manifest_value "$VIG_OS_MANIFEST" DEVKIT_LANGUAGES || true)"

# The pin this workspace carried BEFORE this run rewrites it (#1348). Read here,
# far ahead of the #852 rewrite further down, because it is the only evidence of
# which devkit generation produced the tree we are upgrading — and the
# retired-paths prune is gated on it. The legacy pre-#781 DEVCONTAINER_VERSION
# key counts: repos still on it are the oldest ones, i.e. exactly the population
# carrying the oldest leftovers. Empty on a fresh install (no manifest yet),
# which disables the prune — no evidence, no deletion.
PREVIOUS_PIN="$(read_manifest_value "$VIG_OS_MANIFEST" DEVKIT_VERSION \
    || read_manifest_value "$VIG_OS_MANIFEST" DEVCONTAINER_VERSION || true)"

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

# Scaffold feature opt-outs (#1284): DEVKIT_FEATURES_DISABLED is a
# comma-separated (whitespace-tolerant, like DEVKIT_FLOATING_TAGS/CI_RUNNER)
# subset of the eight scaffold feature groups. Parse + validate it loudly here —
# an unknown name must abort, never silently disable nothing — into
# DISABLED_FEATURES[], with a feature_disabled helper the copy/prune/notice
# mechanisms below all consult. Pure `.vig-os` key (no CLI flag), so only a
# format guard: no contradiction guard as for --mode / --workflow.
VALID_FEATURES=(release renovate sync-issues scanning gh-templates skills worktree devkit-upgrade)
DISABLED_FEATURES=()
if [[ -n "$MANIFEST_FEATURES_DISABLED" ]]; then
    IFS=',' read -ra _raw_features <<< "$MANIFEST_FEATURES_DISABLED"
    for _feat in "${_raw_features[@]}"; do
        # Trim surrounding whitespace (leading + trailing).
        _feat="${_feat#"${_feat%%[![:space:]]*}"}"
        _feat="${_feat%"${_feat##*[![:space:]]}"}"
        [[ -z "$_feat" ]] && continue
        _valid_feat=false
        for _v in "${VALID_FEATURES[@]}"; do
            [[ "$_feat" == "$_v" ]] && { _valid_feat=true; break; }
        done
        if [[ "$_valid_feat" != "true" ]]; then
            echo "Error: Invalid DEVKIT_FEATURES_DISABLED in $VIG_OS_MANIFEST: $_feat (expected a comma-separated subset of: release, renovate, sync-issues, scanning, gh-templates, skills, worktree, devkit-upgrade)" >&2
            exit 1
        fi
        DISABLED_FEATURES+=("$_feat")
    done
fi

# True when scaffold feature group $1 is in DISABLED_FEATURES (#1284).
feature_disabled() {
    local name="$1" f
    for f in "${DISABLED_FEATURES[@]}"; do
        [[ "$f" == "$name" ]] && return 0
    done
    return 1
}

# Contradiction notice (#1284): a disabled sync-issues feature removes
# sync-issues.yml, so DEVKIT_SYNC_TARGET / DEVKIT_SYNC_SCHEDULE have nothing to
# steer. Warn (never abort — the keys are inert, not invalid) so the combination
# is not silently confusing.
if feature_disabled sync-issues && [[ -n "$MANIFEST_SYNC_TARGET" || -n "$MANIFEST_SYNC_SCHEDULE" ]]; then
    echo "Notice: sync-issues feature disabled (DEVKIT_FEATURES_DISABLED); DEVKIT_SYNC_TARGET/DEVKIT_SYNC_SCHEDULE will have no effect (#1284)." >&2
fi

# Refs policy (#1282): scaffold-time knob steering the Refs enforcement of the
# validate-commit-msg hook and CI's validate-commit-range. Pure `.vig-os` key
# (no CLI flag), so only a value guard — empty resolves to the chore-optional
# default. Refuse an unknown value loudly (mirrors the DEVKIT_WORKFLOW guard).
case "$MANIFEST_REFS_POLICY" in
    ""|chore-optional|optional|required) ;;
    *)
        echo "Error: Invalid DEVKIT_REFS_POLICY in $VIG_OS_MANIFEST: $MANIFEST_REFS_POLICY (expected: chore-optional | optional | required)" >&2
        exit 1
        ;;
esac

# Commit types (#1431): DEVKIT_COMMIT_TYPES is a comma-separated (whitespace-
# tolerant, like DEVKIT_FEATURES_DISABLED) FULL REPLACEMENT of the approved
# commit types, steering the validate-commit-msg hook's `--types` arg and CI's
# validate-commit-range from this one key. The value is spliced into sed
# replacement text and YAML, so the LOAD-BEARING guard is a strict per-entry
# charset allowlist (mirrors DEVKIT_SYNC_TARGET): refuse anything but
# lowercase alphanumerics loudly. Resolves into RESOLVED_COMMIT_TYPES — the
# 11-type default when the key is empty — which BOTH renderers consume
# (render_commit_types and render_refs_policy's `optional` expansion).
DEFAULT_COMMIT_TYPES="feat,fix,docs,chore,refactor,perf,test,ci,build,revert,style"
RESOLVED_COMMIT_TYPES=""
if [[ -n "$MANIFEST_COMMIT_TYPES" ]]; then
    IFS=',' read -ra _raw_types <<< "$MANIFEST_COMMIT_TYPES"
    for _type in "${_raw_types[@]}"; do
        # Trim surrounding whitespace (leading + trailing).
        _type="${_type#"${_type%%[![:space:]]*}"}"
        _type="${_type%"${_type##*[![:space:]]}"}"
        [[ -z "$_type" ]] && continue
        if [[ ! "$_type" =~ ^[a-z][a-z0-9]*$ ]]; then
            echo "Error: Invalid DEVKIT_COMMIT_TYPES in $VIG_OS_MANIFEST: $_type (expected a comma-separated list of lowercase alphanumeric commit types, e.g. 'feat,fix,chore,record')" >&2
            exit 1
        fi
        RESOLVED_COMMIT_TYPES+="${RESOLVED_COMMIT_TYPES:+,}$_type"
    done
    # Bot-type notice (never abort — a deliberate removal is allowed, but
    # never silent, mirroring the #1284 contradiction notice): Renovate
    # commits `chore(deps)` and devkit-upgrade commits `build(devkit)` in
    # consumer repos; dropping either fails those bot PRs in commit-checks.
    if [[ -n "$RESOLVED_COMMIT_TYPES" ]]; then
        for _bot_type in chore build; do
            if [[ ",$RESOLVED_COMMIT_TYPES," != *",$_bot_type,"* ]]; then
                echo "Notice: DEVKIT_COMMIT_TYPES omits '$_bot_type' — Renovate/devkit-upgrade bot commits use it; their PRs will fail commit-checks (#1431)." >&2
            fi
        done
    fi
fi
# An all-blank value (e.g. `DEVKIT_COMMIT_TYPES= ,`) falls back to the default.
RESOLVED_COMMIT_TYPES="${RESOLVED_COMMIT_TYPES:-$DEFAULT_COMMIT_TYPES}"

# Branch types (#1432): DEVKIT_BRANCH_TYPES is a comma-separated (whitespace-
# tolerant) FULL REPLACEMENT of the issue-numbered branch-type set in the
# no-commit-to-branch pattern, steering the local guard, the flake consumer
# surface (via the template flake.nix reader), and CI's branch-name gate from
# this one key. The chore/renovate/worktree clauses are never knob-driven. The
# value lands in a sed replacement AND a regex alternation, so the same strict
# per-entry charset allowlist as DEVKIT_COMMIT_TYPES is load-bearing. Resolves
# into RESOLVED_BRANCH_TYPES (stock set when the key is empty) for
# render_branch_types.
DEFAULT_BRANCH_TYPES="feature,bugfix,hotfix,release,docs,test,refactor"
RESOLVED_BRANCH_TYPES=""
if [[ -n "$MANIFEST_BRANCH_TYPES" ]]; then
    IFS=',' read -ra _raw_btypes <<< "$MANIFEST_BRANCH_TYPES"
    for _btype in "${_raw_btypes[@]}"; do
        # Trim surrounding whitespace (leading + trailing).
        _btype="${_btype#"${_btype%%[![:space:]]*}"}"
        _btype="${_btype%"${_btype##*[![:space:]]}"}"
        [[ -z "$_btype" ]] && continue
        if [[ ! "$_btype" =~ ^[a-z][a-z0-9]*$ ]]; then
            echo "Error: Invalid DEVKIT_BRANCH_TYPES in $VIG_OS_MANIFEST: $_btype (expected a comma-separated list of lowercase alphanumeric branch types, e.g. 'feature,bugfix,record')" >&2
            exit 1
        fi
        RESOLVED_BRANCH_TYPES+="${RESOLVED_BRANCH_TYPES:+,}$_btype"
    done
    # Release-type notice (never abort — a deliberate removal is allowed, but
    # never silent, mirroring the #1431 bot-type notice): the release feature
    # works on release/X.Y.Z branches, and maintainers commonly type topic
    # branches into a release PR as release/<issue>-<slug>.
    if [[ -n "$RESOLVED_BRANCH_TYPES" && ",$RESOLVED_BRANCH_TYPES," != *",release,"* ]]; then
        echo "Notice: DEVKIT_BRANCH_TYPES omits 'release' — release-typed topic branches will be rejected by the branch guard (#1432)." >&2
    fi
fi
# An all-blank value (e.g. `DEVKIT_BRANCH_TYPES= ,`) falls back to the default.
RESOLVED_BRANCH_TYPES="${RESOLVED_BRANCH_TYPES:-$DEFAULT_BRANCH_TYPES}"

# Scaffold-drift gate (#1295): pure runtime toggle for the ci.yml scaffold-drift
# job (empty resolves to the enabled `true` default). No scaffold render — the CI
# job reads it via resolve-toolchain's `drift-check` output — so only a value
# guard here, refusing an unexpected literal loudly (mirrors DEVKIT_REFS_POLICY).
case "$MANIFEST_DRIFT_CHECK" in
    ""|true|false) ;;
    *)
        echo "Error: Invalid DEVKIT_DRIFT_CHECK in $VIG_OS_MANIFEST: $MANIFEST_DRIFT_CHECK (expected: true | false)" >&2
        exit 1
        ;;
esac

# Declared project languages (#1478): the repo's own statement of which language
# projects it is expected to carry. Parsed here (the same charset/enum guard shape
# as DEVKIT_FEATURES_DISABLED — an unknown name aborts rather than silently
# declaring nothing); SEEDED from detection and only ever GROWN further down,
# where DETECTED_LANGUAGES is computed. Pure `.vig-os` key, no CLI flag.
VALID_LANGUAGES=(python node rust nix)
DECLARED_LANGUAGES=()

# True when language $1 is already in DECLARED_LANGUAGES.
language_declared() {
    local name="$1" l
    for l in ${DECLARED_LANGUAGES[@]+"${DECLARED_LANGUAGES[@]}"}; do
        [[ "$l" == "$name" ]] && return 0
    done
    return 1
}

if [[ -n "$MANIFEST_LANGUAGES" ]]; then
    IFS=',' read -ra _raw_langs <<< "$MANIFEST_LANGUAGES"
    for _lang in "${_raw_langs[@]}"; do
        # Trim surrounding whitespace (leading + trailing).
        _lang="${_lang#"${_lang%%[![:space:]]*}"}"
        _lang="${_lang%"${_lang##*[![:space:]]}"}"
        [[ -z "$_lang" ]] && continue
        _valid_lang=false
        for _v in "${VALID_LANGUAGES[@]}"; do
            [[ "$_lang" == "$_v" ]] && { _valid_lang=true; break; }
        done
        if [[ "$_valid_lang" != "true" ]]; then
            echo "Error: Invalid DEVKIT_LANGUAGES in $VIG_OS_MANIFEST: $_lang (expected a comma-separated subset of: python, node, rust, nix)" >&2
            exit 1
        fi
        # De-duplicate: the value is rewritten on every scaffold, so a repeated
        # entry must not multiply across upgrades.
        language_declared "$_lang" || DECLARED_LANGUAGES+=("$_lang")
    done
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
#
# In the shipped image the devkit assets are /nix/store SYMLINKS (#1349), so
# `git diff --no-index` compared the LINK against the consumer's regular file
# and rendered a typechange (symlink deleted / file added) whose only "content"
# was the store path — hiding the very divergence this preview exists for.
# Dereference the template side first. The `-f` gate below already follows the
# link, so a template symlink whose target does NOT resolve is treated as a
# missing template (return 1) and never reaches the copy.
print_preserved_template_diff() {
    local rel="$1"
    local preserved="$WORKSPACE_DIR/$rel"
    local template="$TEMPLATE_DIR/$rel"
    [[ -f "$preserved" && -f "$template" ]] || return 1
    # Materialize the dereferenced content under the file's own name in a temp
    # dir rather than diffing the resolved path directly: the diff header then
    # still identifies the file instead of naming an opaque store path.
    local scratch=""
    if [[ -L "$template" ]]; then
        scratch="$(mktemp -d)" || return 1
        if ! mkdir -p "$scratch/$(dirname "$rel")" \
            || ! cat "$template" > "$scratch/$rel"; then
            rm -rf "$scratch"
            return 1
        fi
        template="$scratch/$rel"
    fi
    local rc=1  # stays 1 when the files are identical: nothing to surface
    if ! GIT_DIR=/dev/null git diff --no-index --quiet -- "$template" "$preserved" \
        > /dev/null 2>&1; then
        echo "Preserved $rel differs from the template (yours was kept)."
        echo "Template changes NOT applied (fold in what you need, see MIGRATION.md):"
        echo "─────────────────────────────────────────────────────────────"
        GIT_DIR=/dev/null git diff --no-index -- "$template" "$preserved" || true
        echo "─────────────────────────────────────────────────────────────"
        rc=0
    fi
    if [[ -n "$scratch" ]]; then
        rm -rf "$scratch"
    fi
    return "$rc"
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

# ── declared languages: seed from detection, never narrow (#1478) ─────────────
# DETECTED_LANGUAGES above is live truth and keeps driving every scaffold render
# (.gitignore fragments, codeql.yml's language matrix, the Node justfile.project
# seed). DECLARED_LANGUAGES is the repo's persisted DECLARATION, written back to
# .vig-os, and it is deliberately NOT a detection cache: the scaffold seeds it
# from detection, ADDS a language that appeared since the last run, and never
# removes one. A cache would not have caught #1466 — the deploy that deleted
# pyproject.toml re-ran the scaffold in the same commit, so the cache would have
# been rewritten to empty and CI would still have been green. Divergence between
# declared and detected is exactly the signal the CI gate exists to surface, so
# it is reported loudly here and reconciled by nobody but the consumer.
for lang in ${DETECTED_LANGUAGES[@]+"${DETECTED_LANGUAGES[@]}"}; do
    language_declared "$lang" || DECLARED_LANGUAGES+=("$lang")
done

# Canonicalize to the VALID_LANGUAGES order so the written-back value is
# deterministic (a hand-written `node,python` normalizes once, then is stable —
# an unstable order would read as scaffold drift on every upgrade).
_ordered_languages=()
for _v in "${VALID_LANGUAGES[@]}"; do
    language_declared "$_v" && _ordered_languages+=("$_v")
done
DECLARED_LANGUAGES=(${_ordered_languages[@]+"${_ordered_languages[@]}"})

# Loud notice per declared-but-undetected language: the scaffold keeps the
# declaration (sticky), it does not reconcile it. `nix` is called out separately
# because CI cannot gate it — it has no single marker file.
for lang in ${DECLARED_LANGUAGES[@]+"${DECLARED_LANGUAGES[@]}"}; do
    _still_detected=false
    for _d in ${DETECTED_LANGUAGES[@]+"${DETECTED_LANGUAGES[@]}"}; do
        [[ "$_d" == "$lang" ]] && { _still_detected=true; break; }
    done
    [[ "$_still_detected" == "true" ]] && continue
    case "$lang" in
        python) _marker="pyproject.toml" ;;
        node) _marker="package.json" ;;
        rust) _marker="Cargo.toml" ;;
        nix) _marker="*.nix files beyond flake.nix" ;;
        *) _marker="its marker file" ;;
    esac
    echo "Notice: DEVKIT_LANGUAGES declares '$lang' but $_marker is absent." >&2
    if [[ "$lang" == "nix" ]]; then
        echo "Notice: the declaration is STICKY — the scaffold keeps '$lang' (CI does not gate nix: it has no single marker file). Drop it from DEVKIT_LANGUAGES in .vig-os if this repo is deliberately no longer a nix project (#1478)." >&2
    else
        echo "Notice: the declaration is STICKY — the scaffold keeps '$lang', and CI's declared-language gate will FAIL until $_marker is restored. Drop '$lang' from DEVKIT_LANGUAGES in .vig-os if this repo is deliberately no longer a $lang project (#1478)." >&2
    fi
done

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
    # #1167) before the store symlink exists, so seed the ignore for it too —
    # as does an UPGRADED flake-hooks consumer whose generated config is absent
    # from a fresh checkout/worktree (FLAKE_HOOKS_CONSUMER, #1255): without the
    # seed the regenerated root .gitignore would drop the entry and the next
    # shell entry would leave the store symlink dirtying git status.
    # Idempotent: skip when the assembled ignore (incl. .gitignore.project)
    # already lists it.
    local pcc="$WORKSPACE_DIR/.pre-commit-config.yaml"
    if { [[ -L "$pcc" ]] && readlink "$pcc" | grep -q '/nix/store/'; } \
        || [[ "${FLAKE_HOOKS_DEFAULT:-false}" == "true" ]] \
        || [[ "${FLAKE_HOOKS_CONSUMER:-false}" == "true" ]]; then
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
        /^            extraPackages = extraPackages pkgs;$/ && !inserted {
            print ""
            print "            # Host-runner hooks (#1167): direnv CI runs on the bare host"
            print "            # runner, so let the flake GENERATE .pre-commit-config.yaml from"
            print "            # the shared base hook set, resolved entirely from the Nix store"
            print "            # (incl. pymarkdown, now a flake system hook, #1170) rather than"
            print "            # building the committed YAML remote pre-commit repo hook envs"
            print "            # per runner. Customize like the opt-in block below; the generated"
            print "            # config is a gitignored /nix/store symlink."
            print "            hooks = { };"
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
# Alternate typos config spellings (#913, #1280): the `typos` tool reads
# .typos.toml, the legacy _typos.toml AND the undotted typos.toml. A consumer
# carrying an alternate spelling (and no .typos.toml) keeps it as the single
# config — do not also ship the template .typos.toml, or two active configs
# collide (the curated allowlist gets silently shadowed). Record which
# spelling(s) triggered the skip so the copy can name them; (a *preserved*
# .typos.toml is handled by the preserve list).
TYPOS_ALT_CONFIGS=()
if [[ ! -f "$WORKSPACE_DIR/.typos.toml" ]]; then
    [[ -f "$WORKSPACE_DIR/typos.toml" ]] && TYPOS_ALT_CONFIGS+=("typos.toml")
    [[ -f "$WORKSPACE_DIR/_typos.toml" ]] && TYPOS_ALT_CONFIGS+=("_typos.toml")
fi
if [[ ${#TYPOS_ALT_CONFIGS[@]} -gt 0 ]]; then
    MODE_CONFIG_EXCLUDES+=(".typos.toml")
fi
# Flake-hooks consumer with an ABSENT generated config (#1255): the consumer's
# .pre-commit-config.yaml is flake-GENERATED (#883/#1167) — a gitignored
# /nix/store symlink that only materializes on shell entry — so in a fresh
# checkout/worktree the file is absent and the preserve list cannot protect it.
# Deploying the template YAML then SHADOWS the generated config (git-hooks.nix
# refuses to overwrite an existing file): the shell silently runs the generic
# template without the consumer's hooks/hooksExcludes customizations. The
# opt-in is detectable without the file: an ACTIVE (uncommented)
# hooks/hooksExcludes argument in the preserved flake.nix — exactly
# mkProjectShell's generation trigger (hooks != null || hooksExcludes != [ ]);
# the template's commented opt-in block never matches. Gated on the config
# being absent: when it IS present the existing paths already handle it (store
# symlink -> preserved #1117; regular file -> mid-migration, consumer-owned).
FLAKE_HOOKS_CONSUMER=false
if [[ "$FLAKE_PREEXISTED" == "true" && "$PRECOMMIT_CONFIG_PREEXISTED" == "false" ]] \
    && grep -Eq '^[[:space:]]*hooks(Excludes)?[[:space:]]*=' "$WORKSPACE_DIR/flake.nix"; then
    FLAKE_HOOKS_CONSUMER=true
    MODE_CONFIG_EXCLUDES+=(".pre-commit-config.yaml")
fi

# Feature opt-outs (#1284): expand a disabled feature group into its
# transfer-root rel-paths — the SSoT feature->path map. The skills/worktree
# groups are enumerated from the template tree at runtime (the filesystem is the
# SSoT; skills = every .claude/skills/* dir EXCEPT worktree_*, worktree = the
# worktree_* dirs plus the optional justfile.worktree import), so the ~24 skill
# names are never hardcoded. A directory entry (an ISSUE_TEMPLATE or skill dir)
# covers its whole subtree for the copy-exclude + preview classifier below.
feature_paths() {
    local feature="$1" d name
    case "$feature" in
        release)
            printf '%s\n' \
                ".github/workflows/release.yml" \
                ".github/workflows/release-core.yml" \
                ".github/workflows/release-extension.yml" \
                ".github/workflows/release-publish.yml" \
                ".github/workflows/prepare-release.yml" \
                ".github/workflows/prepare-release-extension.yml" \
                ".github/workflows/promote-release.yml" \
                ".github/workflows/sync-main-to-dev.yml" \
                "docs/DOWNSTREAM_RELEASE.md"
            ;;
        renovate)
            printf '%s\n' \
                "renovate.json" \
                ".github/renovate-default.json"
            ;;
        sync-issues)
            printf '%s\n' \
                ".github/workflows/sync-issues.yml" \
                ".github/label-taxonomy.toml"
            ;;
        scanning)
            printf '%s\n' \
                ".github/workflows/codeql.yml" \
                ".github/workflows/scorecard.yml"
            ;;
        gh-templates)
            printf '%s\n' \
                ".github/ISSUE_TEMPLATE" \
                ".github/pull_request_template.md"
            ;;
        skills)
            for d in "$TEMPLATE_DIR"/.claude/skills/*/; do
                [[ -d "$d" ]] || continue
                name="$(basename "$d")"
                [[ "$name" == worktree_* ]] && continue
                printf '%s\n' ".claude/skills/$name"
            done
            ;;
        worktree)
            for d in "$TEMPLATE_DIR"/.claude/skills/worktree_*/; do
                [[ -d "$d" ]] || continue
                printf '%s\n' ".claude/skills/$(basename "$d")"
            done
            printf '%s\n' ".devcontainer/justfile.worktree"
            ;;
        devkit-upgrade)
            printf '%s\n' \
                ".github/workflows/devkit-upgrade.yml"
            ;;
    esac
}

# ── retired scaffold paths (#1348) ────────────────────────────────────────────
# An upgrade regenerates what the CURRENT scaffold manages and prunes what the
# current mode / workflow model / feature set excludes. A path that an OLD devkit
# shipped and a later devkit RETIRED is managed by neither, so it rode along
# through every upgrade — observed going 0.3.4 -> 1.6.0 in
# exo-pet/playground-carlos#9. The `renovate-changelog.yml` case shows why this
# is not merely cosmetic: the retired workflow coexists with the build/commit
# pair that replaced it AND references the pruned `resolve-image` action, so it
# breaks at its next trigger rather than at upgrade time.
#
# The cumulative manifest below is the missing knowledge — "version V no longer
# ships path P" — and PREVIOUS_PIN says which generation produced this tree.
#
# Adding an entry: one `<version> <path>` line per path, `<version>` being the
# first release that stopped shipping it. Paths are workspace-relative; a
# directory prunes recursively. Sibling of the never-migrate denylist in
# migrate_root_gitignore (#1145) — same "the template used to own this" spirit,
# extended across versions instead of within one tree.
#
# NOT listed here: `.devcontainer/justfile.base` (also retired in 0.4.0). Its
# prune is mode-guarded — a direnv/bare consumer's own .devcontainer/ is never
# touched (#738) — which this version-only manifest cannot express, so it keeps
# its dedicated block further down.
retired_paths() {
    # Split into the build/commit pair; the leftover referenced resolve-image.
    printf '%s\n' '0.3.5 .github/workflows/renovate-changelog.yml'
    # Agent rules/skills moved to .claude/ (the SSoT since 0.4.0).
    printf '%s\n' '0.4.0 .cursor'
    # Debian build path decommissioned: no Dockerfile-like artifact remains.
    printf '%s\n' '0.4.0 .hadolint.yaml'
    # Superseded by the mode-aware resolve-toolchain composite action.
    printf '%s\n' '1.1.0 .github/actions/resolve-image'
    # Per-PR changelog pipeline replaced by release-time synthesis (#1423).
    printf '%s\n' '1.8.0 .github/workflows/renovate-changelog-build.yml'
    printf '%s\n' '1.8.0 .github/workflows/renovate-changelog-commit.yml'
}

# True (0) when semver $1 is STRICTLY lower than $2. Prerelease-aware in the one
# direction that matters here: X.Y.Z-rcN sorts below X.Y.Z, so a consumer pinned
# to an rc of the very release that retires a path is still pruned.
version_lt() {
    local a="$1" b="$2"
    local acore="${a%%-*}" bcore="${b%%-*}"
    local -a av bv
    local i ai bi
    IFS='.' read -ra av <<< "$acore"
    IFS='.' read -ra bv <<< "$bcore"
    for i in 0 1 2; do
        ai="${av[$i]:-0}"; bi="${bv[$i]:-0}"
        # 10# guards a zero-padded segment from being read as octal.
        (( 10#$ai < 10#$bi )) && return 0
        (( 10#$ai > 10#$bi )) && return 1
    done
    # Equal cores: a prerelease is lower than its release. Two prereleases of
    # the same core are not ordered here — no retirement version is a
    # prerelease, so that comparison never arises.
    [[ "$a" != "$acore" && "$b" == "$bcore" ]]
}

# Emit (one workspace-relative path per line) the retired paths this upgrade
# should delete. Consulted by BOTH the --preview DELETIONS report and the
# post-copy prune, so the report can never lie about what the run removes.
#
# Four gates, each load-bearing:
#  - a pin is present and semver-shaped. No pin (fresh install, hand-made tree)
#    or a malformed one means no evidence about this tree's provenance, so
#    nothing is deleted;
#  - the pin PREDATES the retirement. This is the safety property: `.cursor/`
#    and `.hadolint.yaml` are generic names, and a repo pinned at or past the
#    retiring version was never shipped them by devkit — an identically named
#    path there is the consumer's own. Under-pruning a repo that already
#    upgraded past the retirement without this fix is the deliberate trade;
#    those are cleaned by hand once (see #1348);
#  - the current template does not ship the path. Defence in depth: a path can
#    never be both retired and current, and if that invariant ever breaks the
#    upgrade must not delete a file it is about to write;
#  - the path is not consumer-owned (PRESERVE_FILES).
retired_prune_paths() {
    local ver path
    [[ -n "$PREVIOUS_PIN" ]] || return 0
    [[ "$PREVIOUS_PIN" =~ ^[0-9]+\.[0-9]+\.[0-9]+(-[0-9A-Za-z.-]+)?$ ]] || return 0
    while read -r ver path; do
        [[ -n "$ver" && -n "$path" ]] || continue
        version_lt "$PREVIOUS_PIN" "$ver" || continue
        path_present "$WORKSPACE_DIR/$path" || continue
        [[ ! -e "$TEMPLATE_DIR/$path" ]] || continue
        if ! is_preserved_file "$path"; then
            printf '%s\n' "$path"
        fi
    done < <(retired_paths)
}

# Feature opt-outs (#1284): append each disabled feature's paths to
# MODE_CONFIG_EXCLUDES, which both the --preview ADDED classifier and the rsync
# copy consult — so a disabled feature is never shipped and never advertised.
# The post-copy prune + DELETIONS report (with the preserved-class carve-out)
# handle a pre-existing copy left by an earlier scaffold.
for _feat in "${DISABLED_FEATURES[@]}"; do
    while IFS= read -r _p; do
        [[ -n "$_p" ]] && MODE_CONFIG_EXCLUDES+=("$_p")
    done < <(feature_paths "$_feat")
done

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
# end-anchored. /dev/null device paths are deliberately preserved (behavior is
# unaffected by their spelling).
#
# One retarget is NOT a plain dev->main rename: the CHANGELOG freeze targets the
# release branch under trunk (#1479). That is still an anchored substitution
# rather than a structural rewrite, because the shipped asset already creates
# release/X.Y.Z before it freezes.
render_workflow_model() {
    local model="$1"
    [[ "$model" == "trunk" ]] || return 0

    local wf="$WORKSPACE_DIR/.github/workflows"

    # prepare-release.yml — retarget the release base dev -> main (#590/#617
    # logic is base-agnostic), point the CHANGELOG freeze at the release branch
    # instead of the trunk (#1479), and scrub the inert dev step-names/comments
    # so a trunk repo carries no `dev` cruft (/dev/null stays intact).
    local pr="$wf/prepare-release.yml"
    if [[ -f "$pr" ]]; then
        # Freeze target (#1479). Under trunk the base branch IS the PR base, so
        # freezing onto it would leave the release PR's head and base at the same
        # commit (GitHub then refuses to open it) and would push straight to a
        # trunk a require-PR ruleset protects. The asset creates release/X.Y.Z
        # BEFORE the freeze precisely so this stays a literal substitution: the
        # freeze commit (and the rollback's restore commit) target the release
        # branch, and the ref reads that watch the freeze — the #617 wait and the
        # rollback's post-delete guard — follow via FREEZE_REF. Both run BEFORE
        # the blanket heads/dev retarget below, which must not claim these lines.
        sed -i -E 's|^([[:space:]]*TARGET_BRANCH:) refs/heads/dev$|\1 refs/heads/${{ needs.validate.outputs.release_branch }}|' "$pr"
        sed -i -E 's|^([[:space:]]*FREEZE_REF:) heads/dev$|\1 heads/${{ needs.validate.outputs.release_branch }}|' "$pr"
        # Behavioral branch literals: checkout refs + REST ref reads + targets.
        sed -i -E 's|^([[:space:]]*ref:) dev$|\1 main|' "$pr"
        sed -i -E 's|heads/dev\b|heads/main|g' "$pr"
        sed -i -E 's| from dev$| from main|' "$pr"
        # Inert step names + comments (no behavior change; the branch literals
        # above are what drive the retarget).
        sed -i 's|Checkout dev branch|Checkout main branch|' "$pr"
        sed -i 's|Capture pre-prepare dev SHA|Capture pre-prepare main SHA|' "$pr"
        sed -i 's| to dev via API| to the release branch via API|g' "$pr"
        sed -i 's|CHANGELOG.md on dev|CHANGELOG.md on the release branch|g' "$pr"
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

    # devkit-upgrade.yml — retarget the self-upgrade base branch dev -> main:
    # the checkout `ref:` and the PR `BASE:` env value (the only behavioral `dev`
    # literals; both full-line anchored, #1296). Absent when the devkit-upgrade
    # feature is disabled — the -f guard skips it then.
    local du="$wf/devkit-upgrade.yml"
    if [[ -f "$du" ]]; then
        sed -i -E 's|^([[:space:]]*ref:) dev$|\1 main|' "$du"
        sed -i -E 's|^([[:space:]]*BASE:) dev$|\1 main|' "$du"
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

    # renovate-default.json — retarget baseBranchPatterns dev -> main: Renovate
    # restricted to a base-branch pattern matching no existing branch has
    # nothing to operate on, so a trunk consumer keeping the gitflow-shaped
    # ["dev"] runs no updates at all (#1336). Anchored to the exact preset
    # line; the consumer-owned root renovate.json is preserved and untouched.
    local rd="$WORKSPACE_DIR/.github/renovate-default.json"
    if [[ -f "$rd" ]]; then
        sed -i 's|"baseBranchPatterns": \["dev"\]|"baseBranchPatterns": ["main"]|' "$rd"
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
          # Env indirection instead of inline \${{ }} in the run block: the
          # dispatch input would otherwise expand as code (zizmor
          # template-injection, High). The scaffold-time default is the safe,
          # allowlist-validated literal shell fallback.
          TARGET_INPUT: \${{ github.event.inputs.target-branch }}
        run: |
          set -euo pipefail
          TARGET="\${TARGET_INPUT:-${MANIFEST_SYNC_TARGET}}"
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

        # Mirror mode makes the release train the mirror's integration point
        # (#1424). release-core's final-leg sync dispatch retargets to the
        # MIRROR — the only branch allowed to advance the shared
        # incremental-state cutoff (sync-issues-state-<repo> is repo-wide; a
        # release-branch run would leave the mirror permanently missing the
        # inter-sync window, and unlike gitflow there is no sync-main-to-dev
        # backflow to heal it) — then fold steps land the mirror's snapshot
        # archive on the release branch so it reaches main via the
        # human-approved release PR. Absent when the release feature is
        # disabled — the -f guard skips it then.
        local rc="$WORKSPACE_DIR/.github/workflows/release-core.yml"
        if [[ -f "$rc" ]]; then
            sed -i "s#target-branch=release/\$VERSION#target-branch=${tgt_esc}#" "$rc"

            local fold_block
            fold_block="$(mktemp)"
            cat > "$fold_block" <<YAML

      # Rendered by init-workspace.sh (#1424): DEVKIT_SYNC_TARGET mirror mode.
      # The sync dispatch above targeted the mirror, so the release branch has
      # no archive yet; fold the mirror's snapshot dirs in, then re-pull so
      # the finalize SHA (the tag target) includes the fold commit. A missing
      # mirror or an already-identical archive is a clean no-op. commit-action
      # only adds/updates files — a path deleted on the mirror survives on the
      # release branch until it is removed by hand (archives only grow, so
      # this stays theoretical).
      - name: Stage sync mirror archive for fold
        if: \${{ inputs.release_kind == 'final' }}
        id: mirror_fold
        run: |
          set -euo pipefail
          MIRROR_REF="\$(retry --retries 3 --backoff 3 --max-backoff 20 -- git ls-remote origin "refs/heads/${MANIFEST_SYNC_TARGET}")"
          if [ -z "\$MIRROR_REF" ]; then
            echo "eligible=false" >> "\$GITHUB_OUTPUT"
            echo "Mirror branch '${MANIFEST_SYNC_TARGET}' not found; skipping fold."
            exit 0
          fi
          retry --retries 3 --backoff 3 --max-backoff 20 -- git fetch origin "${MANIFEST_SYNC_TARGET}"
          staged=false
          for dir in docs/issues docs/pull-requests; do
            if git rev-parse -q --verify "FETCH_HEAD:\${dir}" >/dev/null; then
              git checkout FETCH_HEAD -- "\${dir}"
              staged=true
            fi
          done
          if [ "\$staged" != "true" ]; then
            echo "eligible=false" >> "\$GITHUB_OUTPUT"
            echo "Mirror carries no snapshot dirs; skipping fold."
            exit 0
          fi
          # commit-action parses FILE_PATHS as a COMMA-separated list and logs
          # "No files to commit" + exits 0 when nothing resolves, so a
          # newline-joined value folds NOTHING while every step stays green
          # (#1502). Build the list from the staged diff with NUL framing:
          # git status --porcelain C-quotes paths containing spaces and renders
          # renames as "R old -> new", both of which mis-parse. The tr has to
          # run inside the pipeline — command substitution drops NUL bytes.
          mirror_paths() {
            git diff --cached --name-only --no-renames --diff-filter=ACM -z -- docs/issues docs/pull-requests
          }
          if mirror_paths | tr '\0' '\n' | grep -q ','; then
            echo "ERROR: a mirror archive path contains a comma, which FILE_PATHS cannot represent:"
            mirror_paths | tr '\0' '\n' | grep ','
            exit 1
          fi
          CHANGED="\$(mirror_paths | tr '\0' ',')"
          CHANGED="\${CHANGED%,}"
          if [ -z "\$CHANGED" ]; then
            echo "eligible=false" >> "\$GITHUB_OUTPUT"
            echo "Release branch already matches the mirror archive; nothing to fold."
            exit 0
          fi
          echo "file_paths=\$CHANGED" >> "\$GITHUB_OUTPUT"
          echo "eligible=true" >> "\$GITHUB_OUTPUT"
          echo "Folding \$(printf '%s\n' "\$CHANGED" | tr ',' '\n' | wc -l) mirror archive path(s) into the release branch."

      - name: Commit folded archive to the release branch
        if: \${{ steps.mirror_fold.outputs.eligible == 'true' }}
        uses: vig-os/commit-action@0361e9aa65b64711a18286ac5dfdcba7cc7a2ac7  # v0.3.2
        env:
          GH_TOKEN: \${{ steps.commit_app_token.outputs.token }}
          GITHUB_REPOSITORY: \${{ github.repository }}
          TARGET_BRANCH: refs/heads/release/\${{ needs.validate.outputs.version }}
          MAX_ATTEMPTS: "3"
          COMMIT_MESSAGE: "chore: fold sync mirror archive into release \${{ needs.validate.outputs.version }}"
          FILE_PATHS: \${{ steps.mirror_fold.outputs.file_paths }}

      - name: Re-pull release branch and verify the fold landed
        if: \${{ steps.mirror_fold.outputs.eligible == 'true' }}
        env:
          VERSION: \${{ needs.validate.outputs.version }}
        run: |
          set -euo pipefail
          retry --retries 3 --backoff 3 --max-backoff 20 -- git fetch origin "release/\$VERSION"
          git reset --hard "origin/release/\$VERSION"
          # Assert the POST-CONDITION, not the step outcome: commit-action
          # reports success when it commits nothing (#1502), and a fold that
          # announces N paths and lands zero must not be green — promote later
          # force-resets the mirror onto main and would take the only copy of
          # the archive with it. M/D = a mirror path this branch lacks or has
          # stale; A = a release-only path, tolerated (archives only grow).
          retry --retries 3 --backoff 3 --max-backoff 20 -- git fetch origin "${MANIFEST_SYNC_TARGET}"
          UNFOLDED="\$(git diff --name-only --no-renames --diff-filter=MD FETCH_HEAD HEAD -- docs/issues docs/pull-requests)"
          if [ -n "\$UNFOLDED" ]; then
            echo "ERROR: the fold did not land — release/\$VERSION is missing or stale for:"
            printf '%s\n' "\$UNFOLDED"
            exit 1
          fi
          echo "Fold verified: release/\$VERSION carries the mirror archive."
YAML
            # shellcheck disable=SC2016  # literal $VERSION: the anchor is the rendered YAML's shell line, not an expansion
            sed -i '/^          git reset --hard "origin\/release\/\$VERSION"$/r '"$fold_block" "$rc"
            rm -f "$fold_block"
        fi

        # After the release PR merges, main carries exactly the archive the
        # release folded in, so promote re-bases the mirror onto main and its
        # divergence stays bounded to post-release snapshot commits (#1424).
        # Ref mutation goes via git push, never the REST refs API (#1157,
        # #1377); the mirror is unprotected by design and its history is
        # regenerated state, so a force reset loses nothing. A concurrent
        # nightly sync run is benign — the next nightly regenerates any
        # clobbered delta.
        local prom="$WORKSPACE_DIR/.github/workflows/promote-release.yml"
        if [[ -f "$prom" ]]; then
            cat >> "$prom" <<YAML

  # Rendered by init-workspace.sh (#1424): DEVKIT_SYNC_TARGET mirror mode.
  reset-sync-mirror:
    name: Reset sync mirror onto main
    needs: [resolve-toolchain, merge]
    runs-on: ubuntu-24.04
    container:
      image: \${{ needs.resolve-toolchain.outputs.image }}
      credentials:
        username: \${{ github.actor }}
        password: \${{ secrets.GHCR_PULL_TOKEN || github.token }}
    timeout-minutes: 5
    if: \${{ needs.merge.result == 'success' }}
    permissions:
      contents: read
      packages: read
    defaults:
      run:
        shell: bash

    steps:
      # Token FIRST, then check out with it: git authenticates through the
      # credentials checkout persists as http.<host>.extraheader, and that
      # header outranks any userinfo embedded in a push URL. The previous
      # form (default checkout + token in the URL) therefore pushed as
      # github-actions[bot] and 403'd on every run (#1503). \`contents: read\`
      # above is deliberate and stays: the mirror reset must carry the Commit
      # App identity, so do not "fix" a future 403 by granting the Actions
      # token \`contents: write\`.
      - name: Generate commit app token
        id: commit_app_token
        uses: actions/create-github-app-token@bcd2ba49218906704ab6c1aa796996da409d3eb1  # v3
        with:
          client-id: \${{ secrets.COMMIT_APP_CLIENT_ID }}
          private-key: \${{ secrets.COMMIT_APP_PRIVATE_KEY }}

      - name: Checkout repository
        uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1  # v7.0.1
        with:
          token: \${{ steps.commit_app_token.outputs.token }}

      - name: Set up devkit toolchain
        uses: ./.github/actions/setup-devkit-toolchain
        with:
          mode: \${{ needs.resolve-toolchain.outputs.mode }}
          devkit-version: \${{ needs.resolve-toolchain.outputs.image-tag }}

      - name: Verify main carries the mirror archive
        id: archive_guard
        run: |
          set -euo pipefail
          # The reset below is only the harmless housekeeping its comment
          # claims if main ALREADY carries the archive the mirror is being
          # reset away from — the release fold puts it there (#1424). When the
          # fold is skipped or broken (#1502), force-pushing main onto the
          # mirror would delete the only copy of the snapshots. So assert the
          # precondition and skip loudly instead: a stale mirror self-heals at
          # the next nightly sync, deleted snapshots do not.
          retry --retries 3 --backoff 3 --max-backoff 20 -- git fetch origin main
          MAIN_SHA="\$(git rev-parse FETCH_HEAD)"
          echo "main_sha=\$MAIN_SHA" >> "\$GITHUB_OUTPUT"
          MIRROR_REF="\$(retry --retries 3 --backoff 3 --max-backoff 20 -- git ls-remote origin "refs/heads/${MANIFEST_SYNC_TARGET}")"
          if [ -z "\$MIRROR_REF" ]; then
            echo "safe=false" >> "\$GITHUB_OUTPUT"
            echo "::warning::Mirror branch '${MANIFEST_SYNC_TARGET}' not found; nothing to reset."
            exit 0
          fi
          retry --retries 3 --backoff 3 --max-backoff 20 -- git fetch origin "${MANIFEST_SYNC_TARGET}"
          STRANDED="\$(git diff --name-only --no-renames --diff-filter=MD FETCH_HEAD "\$MAIN_SHA" -- docs/issues docs/pull-requests)"
          if [ -n "\$STRANDED" ]; then
            echo "safe=false" >> "\$GITHUB_OUTPUT"
            echo "::warning::Skipping the mirror reset: main is missing or stale for \$(printf '%s\n' "\$STRANDED" | wc -l) archive path(s) the mirror carries. Check the release fold (#1502)."
            printf '%s\n' "\$STRANDED"
            exit 0
          fi
          echo "safe=true" >> "\$GITHUB_OUTPUT"
          echo "main carries the mirror archive; the reset is safe."

      - name: Force-reset mirror to main
        if: \${{ steps.archive_guard.outputs.safe == 'true' }}
        env:
          MAIN_SHA: \${{ steps.archive_guard.outputs.main_sha }}
        run: |
          set -euo pipefail
          # After the merged release PR, main carries the folded archive (the
          # step above proved it), so the mirror re-bases onto main and its
          # divergence stays bounded (#1424). Push, never the REST refs API
          # (#1157, #1377). The mirror is unprotected and its history is
          # regenerated state — with the guard above passing, a force reset
          # loses nothing; a racing nightly sync self-heals at its next run.
          # The push authenticates as the Commit App through the credentials
          # the checkout persisted (#1503).
          retry --retries 3 --backoff 5 --max-backoff 30 -- git push --force origin "\${MAIN_SHA}:refs/heads/${MANIFEST_SYNC_TARGET}"
          echo "Mirror '${MANIFEST_SYNC_TARGET}' reset to main @ \${MAIN_SHA}"
YAML
        fi
    fi

    echo "Rendered sync-issues settings (target=${MANIFEST_SYNC_TARGET:-default}, schedule=${MANIFEST_SYNC_SCHEDULE:-default})"
}

# Render the Refs policy knob (#1282): DEVKIT_REFS_POLICY steers the
# validate-commit-msg hook's `--refs-optional-types` arg in the scaffolded
# .pre-commit-config.yaml. The IDENTICAL policy->types mapping drives CI's
# validate-commit-range from the same key in
# .github/actions/resolve-toolchain/action.yml (two renderers, one key) — keep
# them in lockstep. Empty/absent or `chore-optional` is a pure no-op, so a
# default scaffold's .pre-commit-config.yaml stays byte-identical. The anchored
# sed targets only the quoted arg value, distinct from render_workflow_model's
# `(?!dev$)` sed and render_commit_types' `--types` sed on the same file, so
# the three compose.
render_refs_policy() {
    [[ -z "$MANIFEST_REFS_POLICY" || "$MANIFEST_REFS_POLICY" == "chore-optional" ]] && return 0

    local pc="$WORKSPACE_DIR/.pre-commit-config.yaml"
    [[ -f "$pc" ]] || return 0

    # `optional` mirrors the RESOLVED approved-types list — the custom
    # DEVKIT_COMMIT_TYPES when set (#1431), else the stock 11 — so the hook
    # never requires Refs for a type it just accepted; `required` uses a
    # `none` sentinel type (no real commit is type `none`, and the CLI treats
    # an empty --refs-optional-types as falsy => the {chore} default), so
    # every real type requires Refs.
    local types
    case "$MANIFEST_REFS_POLICY" in
        optional) types="$RESOLVED_COMMIT_TYPES" ;;
        required) types="none" ;;
    esac

    sed -i -E "s|^([[:space:]]*\"--refs-optional-types\", \")[^\"]*(\",)\$|\1${types}\2|" "$pc"
    echo "Rendered Refs policy: ${MANIFEST_REFS_POLICY} (refs-optional-types=${types})"
}

# Render the commit-types knob (#1431): DEVKIT_COMMIT_TYPES replaces the
# validate-commit-msg hook's `--types` arg in the scaffolded
# .pre-commit-config.yaml with the resolved list (guarded + resolved above; the
# IDENTICAL list drives CI's validate-commit-range via resolve-toolchain's
# `commit-types` output — two renderers, one key, keep in lockstep). Empty/
# absent is a pure no-op, so a default scaffold stays byte-identical. The
# anchored sed targets only the quoted `--types` value — distinct from
# render_refs_policy's `--refs-optional-types` anchor and
# render_workflow_model's `(?!dev$)` sed on the same file — so the three
# compose.
render_commit_types() {
    [[ -z "$MANIFEST_COMMIT_TYPES" ]] && return 0

    local pc="$WORKSPACE_DIR/.pre-commit-config.yaml"
    [[ -f "$pc" ]] || return 0

    sed -i -E "s|^([[:space:]]*\"--types\", \")[^\"]*(\",)\$|\1${RESOLVED_COMMIT_TYPES}\2|" "$pc"
    echo "Rendered commit types: ${RESOLVED_COMMIT_TYPES}"
}

# Render the branch-types knob (#1432): DEVKIT_BRANCH_TYPES replaces the
# issue-numbered alternation of the no-commit-to-branch pattern in the
# scaffolded .pre-commit-config.yaml (guarded + resolved above; the IDENTICAL
# set drives the flake consumer surface via the template flake.nix reader and
# CI's branch-name gate via resolve-toolchain's `branch-types` output — keep in
# lockstep). Empty/absent is a pure no-op, so a default scaffold stays
# byte-identical. Plain (basic-regex) sed with a `#` delimiter (the
# replacement contains `|`, literal in basic syntax), anchored on the literal
# stock alternation + its `/[0-9]` suffix — the
# single occurrence in the file, distinct from the other renders' anchors, so
# all four compose. The anchor is the STOCK list, so this must run before any
# future render that could rewrite it (it is the only one that does).
render_branch_types() {
    [[ -z "$MANIFEST_BRANCH_TYPES" ]] && return 0

    local pc="$WORKSPACE_DIR/.pre-commit-config.yaml"
    [[ -f "$pc" ]] || return 0

    local alternation="${RESOLVED_BRANCH_TYPES//,/|}"
    sed -i "s#(feature|bugfix|hotfix|release|docs|test|refactor)/\[0-9\]#(${alternation})/[0-9]#" "$pc"
    echo "Rendered branch types: ${RESOLVED_BRANCH_TYPES}"
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
        # (.devcontainer/ #738, docs/container-ci-quirks.md #989, the template
        # .typos.toml when the consumer carries an alternate spelling #913/#1280),
        # so --preview never lists them as ADDED. SSoT: MODE_CONFIG_EXCLUDES, also
        # consumed by the rsync copy below; a directory entry (.devcontainer)
        # matches its whole subtree.
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

    # Feature opt-outs (#1284): a disabled feature's pre-existing paths are
    # pruned on upgrade — list them under DELETIONS (mirrors the trunk
    # sync-main-to-dev entry above). EXCEPT the preserved class
    # (release-extension.yml, prepare-release-extension.yml, renovate.json),
    # which carry consumer implementation and are never pruned: report a
    # left-in-place notice instead (preview only — the post-copy prune echoes it
    # on a real --force run). sync-main-to-dev.yml is skipped when trunk already
    # listed it, so a trunk + release-disabled upgrade reports it exactly once.
    for _feat in "${DISABLED_FEATURES[@]}"; do
        while IFS= read -r _p; do
            [[ -n "$_p" && -e "$WORKSPACE_DIR/$_p" ]] || continue
            if [[ "$WORKFLOW_MODEL" == "trunk" \
                && "$_p" == ".github/workflows/sync-main-to-dev.yml" ]]; then
                continue
            fi
            if is_preserved_file "$_p"; then
                [[ "$PREVIEW" == "true" ]] && \
                    echo "  Note: $_p left in place (preserved); delete manually if unwanted (#1284)."
                continue
            fi
            DELETIONS+=("$_p")
        done < <(feature_paths "$_feat")
    done

    # Retired scaffold paths (#1348): shipped by the consumer's old devkit,
    # managed by no current mechanism. Reported like every other deletion so
    # --preview shows them before anything is touched.
    while IFS= read -r _p; do
        [[ -n "$_p" ]] && DELETIONS+=("$_p (retired scaffold path — #1348)")
    done < <(retired_prune_paths)

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
        # Feature opt-outs (#1284): surface the disabled set so the preview is
        # self-explaining — the skipped paths are absent from ADDED above.
        if [[ ${#DISABLED_FEATURES[@]} -gt 0 ]]; then
            echo ""
            echo "Disabled features (DEVKIT_FEATURES_DISABLED): ${DISABLED_FEATURES[*]}"
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
#
# --checksum on every template copy (#1344): the dereferenced (-L) template
# files carry the Nix store's canonical epoch+1 mtime, and -a (-t) stamps that
# same mtime onto the workspace copies — so on the NEXT upgrade a template
# change that keeps the byte count identical (a digest-for-digest action bump)
# matches the consumer file on both size and mtime and rsync's quick-check
# silently skips it. Content comparison is the only sound check here; the
# template is small, so the cost is negligible.
if [[ "$SMOKE_TEST" == "true" ]]; then
    # Smoke mode: overwrite the managed scaffold (no preserve excludes — every
    # deploy is a fresh render), then overlay smoke-test assets.
    #
    # No --delete (#1466). It removed every tracked path the template does not
    # ship, which is the consumer's own payload: the smoke repo's pyproject.toml,
    # uv.lock, src/ and tests/. That was invisible while commit-action built the
    # deploy tree additively; once #1443 began publishing `git ls-files --deleted`
    # the 1.8.0-rc3 deploy committed those deletions and the smoke repo lost its
    # Python project. Retirement is expressed by the #1348 manifest (pruned below,
    # in this mode as in any other), not by a blanket delete — and the drift gate
    # re-scaffolds in NORMAL mode, which never deletes, so gate and deploy now
    # agree by construction. The docs/issues/ + docs/pull-requests/ excludes went
    # with it: they existed only to shield sync-issues output from --delete.
    #
    # /CHANGELOG.md is root-anchored (#953 semantics): the consumer's ROOT
    # changelog is consumer state — its own frozen release history
    # (## [X.Y.Z] - TBD) must survive re-deploys (#1403). The anchor keeps
    # .devcontainer/CHANGELOG.md (devkit's manifest mirror) syncing.
    rsync -avL --checksum --exclude='.git' --exclude='.venv' --exclude='/CHANGELOG.md' "$TEMPLATE_DIR/" "$WORKSPACE_DIR/"

    SMOKE_TEST_DIR="$SCRIPT_DIR/smoke-test"
    if [[ -d "$SMOKE_TEST_DIR" ]]; then
        echo "Deploying smoke-test-specific files..."
        rsync -avL --checksum "$SMOKE_TEST_DIR/" "$WORKSPACE_DIR/"
    else
        echo "Warning: Smoke-test directory not found at $SMOKE_TEST_DIR" >&2
    fi

    # First deploy only: bootstrap the workspace scaffold CHANGELOG
    # (## Unreleased skeleton). Later deploys never touch the consumer's
    # changelog; devkit's own history lives in .devcontainer/CHANGELOG.md.
    # The old cp + `prepare-changelog unprepare` here rewrote the consumer's
    # frozen ## [X.Y.Z] - TBD heading with devkit's dated release line
    # (unprepare no-ops since #590 — the first heading is always
    # ## Unreleased), guaranteeing a main<->dev sync conflict at every smoke
    # release (#1403).
    if [[ ! -f "$WORKSPACE_DIR/CHANGELOG.md" ]]; then
        echo "Bootstrapping workspace CHANGELOG.md from template scaffold..."
        cp -L "$TEMPLATE_DIR/CHANGELOG.md" "$WORKSPACE_DIR/CHANGELOG.md"
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
    # (#989) plus the template .typos.toml when the consumer carries an alternate
    # spelling (#913/#1280). Root-anchored (leading slash) to
    # match is_preserved_file's exact transfer-root semantics (#953); a directory
    # entry (.devcontainer) excludes its whole subtree. Excluding these from the
    # copy (rather than copying-then-pruning) keeps a real .devcontainer/ intact.
    for excl in "${MODE_CONFIG_EXCLUDES[@]}"; do
        EXCLUDE_ARGS+=("--exclude=/$excl")
        # Surface the otherwise-silent alternate-typos skip so the consumer knows
        # which spelling of their config stands as the single config (#913, #1280).
        if [[ "$excl" == ".typos.toml" ]]; then
            echo "Consumer carries ${TYPOS_ALT_CONFIGS[*]}; not shipping template .typos.toml (#1280)."
        fi
        # Surface the flake-hooks skip so the upgrade report explains the
        # missing template YAML (#1255).
        if [[ "$excl" == ".pre-commit-config.yaml" ]]; then
            echo "Flake-generated pre-commit hooks consumer; not shipping template .pre-commit-config.yaml (#1255)."
        fi
    done

    # trunk workflow model (#1205): the long-lived dev branch and its sync
    # workflow disappear, so a trunk workspace never receives
    # sync-main-to-dev.yml (a leftover copy is pruned after the copy below).
    if [[ "$WORKFLOW_MODEL" == "trunk" ]]; then
        EXCLUDE_ARGS+=("--exclude=/.github/workflows/sync-main-to-dev.yml")
    fi

    rsync -avL --checksum --exclude='.git' --exclude='.venv' "${EXCLUDE_ARGS[@]}" "$TEMPLATE_DIR/" "$WORKSPACE_DIR/"

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

# Feature opt-outs (#1284): prune a disabled feature's pre-existing paths left
# by an earlier scaffold (the rsync copy already excludes them via
# MODE_CONFIG_EXCLUDES; this removes the upgrade leftover). Preserved-class files
# (release-extension.yml, prepare-release-extension.yml, renovate.json) carry
# consumer implementation and are never pruned — print a left-in-place notice
# instead. Composes with the trunk sync-main-to-dev prune above: that one path
# is skipped under trunk so it is pruned + echoed exactly once.
for _feat in "${DISABLED_FEATURES[@]}"; do
    while IFS= read -r _p; do
        [[ -n "$_p" && -e "$WORKSPACE_DIR/$_p" ]] || continue
        if [[ "$WORKFLOW_MODEL" == "trunk" \
            && "$_p" == ".github/workflows/sync-main-to-dev.yml" ]]; then
            continue
        fi
        if is_preserved_file "$_p"; then
            echo "Feature '$_feat' disabled: $_p left in place (preserved); delete manually if unwanted (#1284)."
            continue
        fi
        echo "Pruning $_p for disabled feature '$_feat' (#1284)..."
        rm -rf "${WORKSPACE_DIR:?}/$_p"
    done < <(feature_paths "$_feat")
done

# Retired scaffold paths (#1348): delete what an older devkit shipped into this
# tree and no current mechanism manages. Gating and rationale live in
# retired_prune_paths above; this is purely its executor, so the --preview
# report and the real run can never disagree.
while IFS= read -r _p; do
    [[ -n "$_p" ]] || continue
    echo "Pruning retired scaffold path $_p (shipped before this repo's ${PREVIOUS_PIN} pin, #1348)..."
    rm -rf "${WORKSPACE_DIR:?}/$_p"
done < <(retired_prune_paths)

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
    # A FLOATING input (no ?ref=) never warns HERE — not because it cannot skew
    # (it does, via the rev flake.lock last locked, #1263), but because that
    # case is handled elsewhere: install.sh advances the lock host-side on
    # --force upgrades, and mkProjectShell's shell-entry guard warns until the
    # lock catches up. Only a pin that differs from the target warns here.
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
# the workflow-model default. A no-op when both keys are unset. Skipped entirely
# when the sync-issues feature is disabled (#1284) — the file it seds no longer
# exists, so the render would be a silent no-op anyway; skip it explicitly.
if feature_disabled sync-issues; then
    echo "Skipping sync-issues render (feature disabled via DEVKIT_FEATURES_DISABLED, #1284)."
else
    render_sync_settings
fi
# Refs policy (#1282) + commit types (#1431): render the validate-commit-msg
# hook's --refs-optional-types / --types from DEVKIT_REFS_POLICY /
# DEVKIT_COMMIT_TYPES (each paired with its CI mapping in resolve-toolchain).
# No-ops for the defaults, so a default scaffold is unchanged. Both run after
# render_workflow_model (all three sed .pre-commit-config.yaml on distinct
# anchors) so the renders compose.
render_refs_policy
render_commit_types
# Branch types (#1432): swaps the issue-numbered alternation of the branch
# guard pattern — a distinct anchor from the three renders above, so all
# compose. No-op for the default.
render_branch_types

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
    # Feature opt-outs (#1284): bare in the template (DEVKIT_FEATURES_DISABLED=),
    # so a consumer's disabled-feature list is read before the overwrite and
    # written back — else an upgrade silently re-ships the pruned features. The
    # raw value round-trips (like DEVKIT_TAG_PREFIX); clearing it re-enables.
    if [[ -n "$MANIFEST_FEATURES_DISABLED" ]]; then
        write_manifest_value DEVKIT_FEATURES_DISABLED "$MANIFEST_FEATURES_DISABLED"
    fi
    # Refs policy (#1282): bare in the template (DEVKIT_REFS_POLICY=), so a
    # consumer's non-default policy is written back — else an upgrade silently
    # resets the commit-msg/commit-range Refs enforcement to chore-optional.
    if [[ -n "$MANIFEST_REFS_POLICY" ]]; then
        write_manifest_value DEVKIT_REFS_POLICY "$MANIFEST_REFS_POLICY"
    fi
    # Commit types (#1431): bare in the template (DEVKIT_COMMIT_TYPES=), so a
    # consumer's replacement list is written back — else an upgrade silently
    # resets the approved commit types to the stock 11. The raw value
    # round-trips (like DEVKIT_FEATURES_DISABLED).
    if [[ -n "$MANIFEST_COMMIT_TYPES" ]]; then
        write_manifest_value DEVKIT_COMMIT_TYPES "$MANIFEST_COMMIT_TYPES"
    fi
    # Branch types (#1432): bare in the template (DEVKIT_BRANCH_TYPES=), so a
    # consumer's replacement set is written back — else an upgrade silently
    # resets the branch guard (and the CI branch-name gate) to the stock set.
    if [[ -n "$MANIFEST_BRANCH_TYPES" ]]; then
        write_manifest_value DEVKIT_BRANCH_TYPES "$MANIFEST_BRANCH_TYPES"
    fi
    # devkit-upgrade knobs (#1296): bare in the template (DEVKIT_AUTO_UPGRADE= /
    # DEVKIT_UPGRADE_EXCLUDE=), so a consumer's opt-out / exclusion list is read
    # before the overwrite and written back — else an upgrade silently re-enables
    # auto-upgrade and drops the exclusions. Round-trips like DEVKIT_FEATURES_DISABLED.
    if [[ -n "$MANIFEST_AUTO_UPGRADE" ]]; then
        write_manifest_value DEVKIT_AUTO_UPGRADE "$MANIFEST_AUTO_UPGRADE"
    fi
    if [[ -n "$MANIFEST_UPGRADE_EXCLUDE" ]]; then
        write_manifest_value DEVKIT_UPGRADE_EXCLUDE "$MANIFEST_UPGRADE_EXCLUDE"
    fi
    # Scaffold-drift gate (#1295): bare in the template (DEVKIT_DRIFT_CHECK=), so a
    # consumer's explicit false (opt-out) is written back — else an upgrade
    # silently re-enables the drift gate the consumer disabled.
    if [[ -n "$MANIFEST_DRIFT_CHECK" ]]; then
        write_manifest_value DEVKIT_DRIFT_CHECK "$MANIFEST_DRIFT_CHECK"
    fi
    # Declared languages (#1478): bare in the template (DEVKIT_LANGUAGES=), so
    # the declaration is written back — else an upgrade would erase it and the
    # CI gate would go silent exactly when it is needed. Unlike the other
    # round-tripped keys this one is not merely preserved: it is the union of
    # the previous declaration and this run's detection, so a first scaffold
    # SEEDS it and a later one GROWS it. A language-neutral repo has an empty
    # union and keeps the bare template line.
    if [[ ${#DECLARED_LANGUAGES[@]} -gt 0 ]]; then
        write_manifest_value DEVKIT_LANGUAGES "$(IFS=','; echo "${DECLARED_LANGUAGES[*]}")"
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
