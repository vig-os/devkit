#!/usr/bin/env bash
# Consumer matrix (#1762): render one consumer variant ("cell") with THIS
# checkout's assets/init-workspace.sh and run the rendered consumer's OWN gates.
#
# bats (init-workspace.bats) asserts on the rendered FILES; this executes them.
# It is also the checked-in RC validation recipe: run it from a release-branch
# checkout to prove every variant below before cutting a candidate.
#
# Usage:
#   render-cell.sh list               print the cell names, one per line (the
#                                     single source of the CI matrix)
#   render-cell.sh seed <cell>        print the .vig-os lines the cell pre-seeds
#   render-cell.sh render <cell> <dir>  render the cell into <dir> (no gates)
#   render-cell.sh <cell> [<dir>]     render the cell into <dir> (default: a
#                                     fresh temp dir) and run its gates
#
# A cell is a delivery mode, a workflow model and an optional pre-seeded
# `.vig-os`. Knobs are seeded, never passed as flags: init-workspace.sh has no
# knob flags, and it treats a directory holding only a dotfile as empty, so a
# seeded render is the genuine FIRST-scaffold path (not `--force`, which would
# exercise upgrade semantics instead).
#
# Gates, per cell (each runs even when an earlier one failed, so a red cell
# names every broken gate at once):
#   seed       every pre-seeded knob survived the render into .vig-os
#   lint       `just lint`
#   precommit  `just precommit` (prek over the committed tree, as the
#              consumer's CI runs it); direnv mode ships no
#              .pre-commit-config.yaml (its hooks come from flake eval), so
#              the gate reports itself skipped there
#   actionlint actionlint over the rendered .github/workflows (skipped when
#              the cell disables the actionlint feature, as the consumer does)
#   zizmor     zizmor over the rendered .github/workflows, with the rendered
#              zizmor.yml baseline
#   languages  the rendered resolve-toolchain `resolve` step feeding the
#              rendered ci.yml "Check declared languages" step, both executed
#              verbatim; passes when the guard holds, or — for the
#              language-guard cell — when it FIRES (#1466)
#
# Requires just, uv, prek, actionlint, git and jq on PATH (the devkit dev shell
# provides them); zizmor runs through `uvx` unless ZIZMOR names a binary.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
INIT_WORKSPACE="$ROOT/assets/init-workspace.sh"
TEMPLATE_DIR="$ROOT/assets/workspace"
# Same pin as the devkit's own managed-workflow audit
# (.github/actions/test-project, "Audit managed workflows").
ZIZMOR_VERSION="${ZIZMOR_VERSION:-1.25.2}"

CELLS=(
    direnv
    devcontainer
    bare
    trunk-direnv
    features-disabled
    ci-runner
    tag-prefix
    language-guard
)

# Every scaffold feature group, read from init-workspace.sh's own enum so a new
# group is disabled here without a second list to keep in sync.
all_features() {
    sed -n 's/^VALID_FEATURES=(\(.*\))$/\1/p' "$INIT_WORKSPACE" | tr ' ' ','
}

# Set CELL_MODE, CELL_WORKFLOW, CELL_SEED (array of KEY=VALUE lines) and
# CELL_LANGUAGES_GUARD (hold | fire) for cell $1. Knob cells render `both`, the
# mode with the widest surface (devcontainer AND flake files, plus the
# scaffolded hook config).
cell_spec() {
    CELL_MODE=""
    CELL_WORKFLOW=gitflow
    CELL_SEED=()
    CELL_LANGUAGES_GUARD=hold
    case "$1" in
        direnv | devcontainer | bare) CELL_MODE="$1" ;;
        trunk-direnv)
            CELL_MODE=direnv
            CELL_WORKFLOW=trunk
            ;;
        features-disabled)
            CELL_MODE=both
            CELL_SEED=("DEVKIT_FEATURES_DISABLED=$(all_features)")
            ;;
        ci-runner)
            CELL_MODE=both
            CELL_SEED=("DEVKIT_CI_RUNNER=self-hosted,linux,x64,consumer-matrix")
            ;;
        tag-prefix)
            CELL_MODE=both
            CELL_SEED=("DEVKIT_TAG_PREFIX=v")
            ;;
        language-guard)
            # Declares python with no pyproject.toml: the #1466 shape (the
            # project was deleted, the declaration stayed). The guard must fire.
            CELL_MODE=both
            CELL_SEED=("DEVKIT_LANGUAGES=python")
            CELL_LANGUAGES_GUARD=fire
            ;;
        *)
            echo "render-cell: unknown cell '$1' (known: ${CELLS[*]})" >&2
            return 1
            ;;
    esac
}

render_cell() {
    local cell="$1" ws="$2" line version_file
    cell_spec "$cell"
    mkdir -p "$ws"
    if [[ -n "$(ls -A "$ws")" ]]; then
        echo "render-cell: refusing to render into non-empty '$ws'" >&2
        return 1
    fi
    if ((${#CELL_SEED[@]} > 0)); then
        for line in "${CELL_SEED[@]}"; do
            printf '%s\n' "$line" >>"$ws/.vig-os"
        done
    fi
    local -a args=(--no-prompts --mode "$CELL_MODE")
    [[ "$CELL_WORKFLOW" == gitflow ]] || args+=(--workflow "$CELL_WORKFLOW")
    # No baked image VERSION outside the image: point VERSION_FILE at a path
    # that does not exist so the template pin stays as shipped.
    version_file="$ws/.consumer-matrix-no-version"
    env TEMPLATE_DIR="$TEMPLATE_DIR" \
        WORKSPACE_DIR="$ws" \
        VERSION_FILE="$version_file" \
        SHORT_NAME=consumer_matrix \
        ORG_NAME=vig-os \
        GITHUB_REPOSITORY=vig-os/consumer-matrix \
        bash "$INIT_WORKSPACE" "${args[@]}"
}

# Print the `run:` body of the first step named $2 in workflow/action file $1.
step_script() {
    uv run --project "$ROOT" --frozen --quiet python - "$1" "$2" <<'PY'
import sys
import yaml

path, name = sys.argv[1], sys.argv[2]
with open(path, encoding="utf-8") as fh:
    doc = yaml.safe_load(fh)
steps = list(doc.get("runs", {}).get("steps", []))
for job in (doc.get("jobs") or {}).values():
    steps.extend(job.get("steps", []))
for step in steps:
    if step.get("name") == name and "run" in step:
        sys.stdout.write(step["run"])
        sys.exit(0)
sys.exit(f"no step named {name!r} with a run body in {path}")
PY
}

gate_seed() {
    local line rc=0
    if ((${#CELL_SEED[@]} == 0)); then
        echo "no seeded knobs"
        return 0
    fi
    for line in "${CELL_SEED[@]}"; do
        if grep -qxF -- "$line" .vig-os; then
            echo "persisted: $line"
        else
            echo "NOT persisted: $line (got: $(grep -E "^${line%%=*}=" .vig-os || echo none))"
            rc=1
        fi
    done
    return "$rc"
}

gate_precommit() {
    if [[ ! -f .pre-commit-config.yaml ]]; then
        echo "SKIP: no .pre-commit-config.yaml (mode '$CELL_MODE' generates its hooks by flake eval)"
        return 0
    fi
    just precommit
}

# The consumer's actionlint gate exists only while the actionlint feature is
# on: disabling it drops both the hook and the runner-label config, and linting
# against actionlint's bare built-in label list then reports every non-builtin
# hosted label (#1660) — a gate the consumer opted out of, not a defect.
gate_actionlint() {
    if grep -qE '^DEVKIT_FEATURES_DISABLED=.*actionlint' .vig-os; then
        echo "SKIP: actionlint feature disabled in .vig-os"
        return 0
    fi
    actionlint
}

# uvx fetches the pinned upstream wheel (a generic-linux binary). A host that
# cannot run it (NixOS) may put its own zizmor on PATH via ZIZMOR=zizmor.
gate_zizmor() {
    local -a cmd=(uvx "zizmor@$ZIZMOR_VERSION")
    [[ -z "${ZIZMOR:-}" ]] || cmd=("$ZIZMOR")
    "${cmd[@]}" --offline --config zizmor.yml .github/workflows/
}

# Run the rendered resolve step, then the rendered guard step, verbatim.
gate_languages() {
    local resolve guard out languages rc=0
    resolve="$(step_script .github/actions/resolve-toolchain/action.yml 'Resolve mode + image tag')" || return 1
    guard="$(step_script .github/workflows/ci.yml 'Check declared languages')" || return 1
    out="$(mktemp)"
    if ! env GITHUB_OUTPUT="$out" INPUT_IMAGE_TAG= bash -eo pipefail -c "$resolve"; then
        echo "rendered resolve-toolchain step failed"
        rm -f "$out"
        return 1
    fi
    languages="$(sed -n 's/^languages=//p' "$out")"
    rm -f "$out"
    echo "resolved languages: '${languages}'"
    env LANGUAGES="$languages" bash -eo pipefail -c "$guard" || rc=$?
    if [[ "$CELL_LANGUAGES_GUARD" == fire ]]; then
        if ((rc == 0)); then
            echo "EXPECTED the declared-language guard to fire, but it passed (#1466 regression)"
            return 1
        fi
        echo "guard fired as expected (exit $rc)"
        return 0
    fi
    return "$rc"
}

summary() {
    [[ -n "${GITHUB_STEP_SUMMARY:-}" ]] || return 0
    printf '%s\n' "$@" >>"$GITHUB_STEP_SUMMARY"
}

run_cell() {
    local cell="$1" ws="${2:-}" gate rc
    local -a failed=()
    cell_spec "$cell"
    [[ -n "$ws" ]] || ws="$(mktemp -d "${RUNNER_TEMP:-${TMPDIR:-/tmp}}/consumer-matrix-$cell.XXXXXX")"

    echo "== consumer-matrix cell '$cell' (mode=$CELL_MODE workflow=$CELL_WORKFLOW) in $ws"
    if ! render_cell "$cell" "$ws"; then
        echo "::error::consumer-matrix cell '$cell': render failed"
        summary "### Consumer matrix: \`$cell\` FAILED" "" "Render failed (assets/init-workspace.sh)."
        return 1
    fi

    cd "$ws"
    local branch=dev
    [[ "$CELL_WORKFLOW" == trunk ]] && branch=main
    git init -q -b "$branch"
    git add -A
    git -c user.name=consumer-matrix -c user.email=consumer-matrix@invalid \
        -c commit.gpgsign=false -c core.hooksPath=/dev/null \
        commit -q -m "chore: initial scaffold"

    local -a rows=("| gate | result |" "| --- | --- |")
    for gate in seed lint precommit actionlint zizmor languages; do
        echo "::group::$cell / $gate"
        rc=0
        case "$gate" in
            seed) gate_seed || rc=$? ;;
            lint) just lint || rc=$? ;;
            precommit) gate_precommit || rc=$? ;;
            actionlint) gate_actionlint || rc=$? ;;
            zizmor) gate_zizmor || rc=$? ;;
            languages) gate_languages || rc=$? ;;
        esac
        echo "::endgroup::"
        if ((rc == 0)); then
            rows+=("| $gate | pass |")
        else
            echo "::error::consumer-matrix cell '$cell': gate '$gate' failed (exit $rc)"
            rows+=("| $gate | **FAIL** (exit $rc) |")
            failed+=("$gate")
        fi
    done

    if ((${#failed[@]} > 0)); then
        summary "### Consumer matrix: \`$cell\` FAILED (${failed[*]})" "" "${rows[@]}" ""
        echo "== cell '$cell' FAILED: ${failed[*]}"
        return 1
    fi
    summary "### Consumer matrix: \`$cell\` passed" "" "${rows[@]}" ""
    echo "== cell '$cell' passed"
}

main() {
    case "${1:-}" in
        list) printf '%s\n' "${CELLS[@]}" ;;
        seed)
            cell_spec "${2:?usage: render-cell.sh seed <cell>}"
            if ((${#CELL_SEED[@]} > 0)); then printf '%s\n' "${CELL_SEED[@]}"; fi
            ;;
        render) render_cell "${2:?usage: render-cell.sh render <cell> <dir>}" "${3:?usage: render-cell.sh render <cell> <dir>}" ;;
        "" | -h | --help)
            sed -n '2,/^$/s/^# \{0,1\}//p' "${BASH_SOURCE[0]}"
            [[ -n "${1:-}" ]]
            ;;
        *) run_cell "$@" ;;
    esac
}

main "$@"
