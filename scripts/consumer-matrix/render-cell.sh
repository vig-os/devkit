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
# A cell is a delivery mode, a workflow model, an optional pre-seeded
# `.vig-os` and an optional language fixture (tests/fixtures/consumer/<lang>/:
# a zero-dependency hello world plus one test, copied in as the marker files
# the scaffold detects the language from). Knobs are seeded, never passed as flags: init-workspace.sh has no
# knob flags, and it treats a directory holding only a dotfile as empty, so a
# seeded render is the genuine FIRST-scaffold path (not `--force`, which would
# exercise upgrade semantics instead).
#
# Gates, per cell (each runs even when an earlier one failed, so a red cell
# names every broken gate at once):
#   runners    key-only / variable-only runner outputs and full warning text
#   adoption   gitflow pre-N default-branch body, retained key and dev ancestry
#   seed       every pre-seeded knob survived the render into .vig-os, and a
#              fixture cell's language was detected into DEVKIT_LANGUAGES
#   flake-check  (flake cells only) `nix flake check` of the rendered flake
#              against THIS checkout (--override-input vigos), then its dev
#              shell is built; every later gate of the cell runs inside it, so
#              the flake-generated direnv hooks are the ones exercised
#   first-commit  the commit-stage hooks over the STAGED scaffold, before the
#              first commit exists — what a new consumer's first `git commit`
#              runs (`prek run` without --all-files); skipped like precommit
#              when the mode ships no .pre-commit-config.yaml
#   sync       `just sync`, as the consumer's CI runs before lint and test
#   lint       `just lint`
#   precommit  `just precommit` (prek over the committed tree, as the
#              consumer's CI runs it); direnv mode ships no
#              .pre-commit-config.yaml (its hooks come from flake eval), so
#              the gate reports itself skipped there
#   test       `just test`; a fixture cell must also PROVE its suite ran (the
#              fixture test writes $CONSUMER_MATRIX_SENTINEL), so a recipe that
#              silently no-ops fails instead of passing green
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
# provides them), npm for the node cell, cargo for the rust cell and nix for
# the flake cells; zizmor runs
# through `uvx` unless ZIZMOR names a binary.
#
# Sourcing the script (bats does) defines its functions without running it.

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
    trunk
    features-disabled
    ci-runner
    runner-key-only
    runner-gitflow
    tag-prefix
    language-guard
    python
    node
    rust
    direnv-flake
    rust-flake
)

# Known defects a cell must reproduce EXACTLY: <cell> -> "<gate> <issue>". The
# cell still runs every gate; it is accepted only when that one gate is the
# sole failure AND failed with the silent-no-op signal. Passing fails the cell
# (the marker is stale), and so does failing any other way. Remove an entry in
# the PR that fixes its issue.
declare -gA EXPECTED_FAIL=()

# Print the expected-fail spec ("<gate> <issue>") of cell $1, or nothing.
expected_fail_spec() {
    if [[ -n "${EXPECTED_FAIL[$1]:-}" ]]; then
        printf '%s\n' "${EXPECTED_FAIL[$1]}"
    fi
}

# Verdict for cell $1 given the silent-no-op signal $2 (true | false) and the
# failed gates in $3...: prints it, returns 0 for an accepted outcome.
cell_verdict() {
    local cell="$1" noop="$2" spec gate issue
    shift 2
    spec="$(expected_fail_spec "$cell")"
    if [[ -z "$spec" ]]; then
        if (($# == 0)); then
            echo "passed"
            return 0
        fi
        echo "FAILED: $*"
        return 1
    fi
    read -r gate issue <<<"$spec"
    if (($# == 0)); then
        echo "FAILED: $cell now passes — remove the $issue expected-fail marker"
        return 1
    fi
    if [[ "$*" == "$gate" && "$noop" == true ]]; then
        echo "expected-fail ($issue)"
        return 0
    fi
    echo "FAILED: $* (the $issue expected-fail accepts only the silent no-op of gate '$gate')"
    return 1
}

# Every scaffold feature group, read from init-workspace.sh's own enum so a new
# group is disabled here without a second list to keep in sync.
all_features() {
    sed -n 's/^VALID_FEATURES=(\(.*\))$/\1/p' "$INIT_WORKSPACE" | tr ' ' ','
}

# Set CELL_MODE, CELL_WORKFLOW, CELL_SEED (array of KEY=VALUE lines),
# CELL_LANGUAGES_GUARD (hold | fire), CELL_FIXTURE (language fixture or empty)
# and CELL_FLAKE (true | false) for cell $1. Knob cells render `both`, the mode
# with the widest surface (devcontainer AND flake files, plus the scaffolded
# hook config). Language cells render `bare`, which ships the scaffolded hook
# config with no mode-specific files, so a red language cell is about the
# language (the mode axis has its own cells).
cell_spec() {
    CELL_MODE=""
    CELL_WORKFLOW=gitflow
    CELL_SEED=()
    CELL_LANGUAGES_GUARD=hold
    CELL_FIXTURE=""
    CELL_FLAKE=false
    CELL_RUNNER_SMALL=""
    CELL_RUNNER_LARGE=""
    CELL_RUNNER_XLARGE=""
    case "$1" in
        direnv | devcontainer | bare) CELL_MODE="$1" ;;
        python | node | rust)
            CELL_MODE=bare
            CELL_FIXTURE="$1"
            ;;
        direnv-flake)
            CELL_MODE=direnv
            CELL_FLAKE=true
            ;;
        rust-flake)
            # Rust cold adoption end to end (#1496): a fresh direnv scaffold of
            # a Cargo repo gets the mkRustProject flake, whose `nix flake check`
            # builds fmt/clippy/nextest/doctest/doc/deny, and whose dev shell
            # runs every later gate — including the seeded cargo recipes.
            CELL_MODE=direnv
            CELL_FIXTURE=rust
            CELL_FLAKE=true
            ;;
        trunk)
            # `both`, not direnv: direnv ships no .pre-commit-config.yaml, so
            # only a mode with the scaffolded hook config runs the trunk branch
            # guard (the direnv cell still covers direnv mode).
            CELL_MODE=both
            CELL_WORKFLOW=trunk
            ;;
        features-disabled)
            CELL_MODE=both
            CELL_SEED=("DEVKIT_FEATURES_DISABLED=$(all_features)")
            ;;
        ci-runner)
            CELL_MODE=both
            CELL_RUNNER_SMALL="${CONSUMER_MATRIX_RUNNER_LABEL:-pool-s}"
            CELL_RUNNER_LARGE="${CONSUMER_MATRIX_RUNNER_LARGE:-pool-l}"
            CELL_RUNNER_XLARGE="${CONSUMER_MATRIX_RUNNER_XLARGE:-pool-xl}"
            ;;
        runner-key-only | runner-gitflow)
            CELL_MODE=bare
            CELL_SEED=("DEVKIT_CI_RUNNER=pool-legacy")
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
    ws="$(cd "$ws" && pwd)" || return 1
    if [[ -n "$(ls -A "$ws")" ]]; then
        echo "render-cell: refusing to render into non-empty '$ws'" >&2
        return 1
    fi
    if [[ -n "$CELL_FIXTURE" ]]; then
        cp -a "$ROOT/tests/fixtures/consumer/$CELL_FIXTURE/." "$ws/"
    fi
    if ((${#CELL_SEED[@]} > 0)); then
        for line in "${CELL_SEED[@]}"; do
            printf '%s\n' "$line" >>"$ws/.vig-os"
        done
    fi
    if [[ "$cell" == runner-gitflow ]]; then
        prepare_adoption "$ws" && adoption_body "$ws" && migrating_adoption "$ws"
        return $?
    fi
    local -a args=(--no-prompts --mode "$CELL_MODE")
    [[ "$CELL_WORKFLOW" == gitflow ]] || args+=(--workflow "$CELL_WORKFLOW")
    # A fixture is an EXISTING project adopting devkit: its files make the
    # directory non-empty, and init-workspace.sh takes that path only with
    # --force (no .vig-os yet, so nothing is upgraded — an adoption).
    [[ -z "$CELL_FIXTURE" ]] || args+=(--force)
    # No baked image VERSION outside the image: point VERSION_FILE at a path
    # that does not exist so the template pin stays as shipped.
    version_file="$ws/.consumer-matrix-no-version"
    env TEMPLATE_DIR="$TEMPLATE_DIR" WORKSPACE_DIR="$ws" VERSION_FILE="$version_file" \
        SHORT_NAME=consumer_matrix ORG_NAME=vig-os GITHUB_REPOSITORY=vig-os/consumer-matrix \
        bash "$INIT_WORKSPACE" "${args[@]}"
}

# Local-only gitflow history: the default-branch workflow is deliberately pre-N.
# No consumer remote, workflow dispatch, or API call is involved.
fixture_commit() {
    git -c user.name=consumer-matrix -c user.email=consumer-matrix@example.com \
        -c commit.gpgsign=false -c core.hooksPath=/dev/null commit -qm "$1"
}

prepare_adoption() (
    cd "$1" || return 1
    git init -q -b main
    git config user.name consumer-matrix
    git config user.email consumer-matrix@example.com
    git config commit.gpgsign false
    git config core.hooksPath /dev/null
    local evidence="$PWD/.git/consumer-matrix"
    if ! git -C "$ROOT" rev-parse --verify refs/tags/1.18.0 >/dev/null 2>&1; then
        echo 'consumer-matrix: required pre-N tag 1.18.0 missing; run git fetch --depth=1 origin tag 1.18.0' >&2
        return 1
    fi
    mkdir -p "$evidence/pre-n"
    git -C "$ROOT" archive 1.18.0 assets | tar -x -C "$evidence/pre-n" || return 1
    env TEMPLATE_DIR="$evidence/pre-n/assets/workspace" WORKSPACE_DIR="$PWD" \
        VERSION_FILE="$evidence/no-version" SHORT_NAME=consumer_matrix ORG_NAME=vig-os \
        GITHUB_REPOSITORY=vig-os/consumer-matrix \
        bash "$evidence/pre-n/assets/init-workspace.sh" --force --mode bare --no-prompts || return 1
    git -C "$ROOT" show 1.18.0:assets/workspace/.github/workflows/devkit-upgrade.yml > "$evidence/pre-n.yml"
    git add .
    fixture_commit 'chore: pre-N consumer' || return 1
    git checkout -qb dev || return 1
    echo 'Consumer work ahead of main.' > consumer.txt
    git add consumer.txt
    fixture_commit 'chore: advance dev' || return 1
    git checkout -qb chore/adopt-devkit
)

# Replay the immutable default-branch upgrade and body steps. Only the download,
# container, and PR API boundaries are local adapters; install.sh runs unchanged.
adoption_body() (
    cd "$1" || return 1
    local evidence="$PWD/.git/consumer-matrix" upgrade body
    upgrade="$(step_script "$evidence/pre-n.yml" 'Run the devkit upgrade (install.sh --force)')" || return 1
    body="$(step_script "$evidence/pre-n.yml" 'Open or update the adoption PR')" || return 1
    mkdir -p "$evidence/bin"
    local tool
    for tool in curl docker gh; do
        ln -sf "$ROOT/scripts/consumer-matrix/install-transport.sh" "$evidence/bin/$tool"
    done
    # Upgrade defines the exact FLAKE_BUMP/HOOK_* values it writes to its outputs;
    # consume those same values in the following PR step, without fabricating them.
    env -u DEVKIT_UPGRADE_CONTEXT -u DEVKIT_UPGRADE_CI_RUNNER_SMALL \
        -u DEVKIT_UPGRADE_CI_RUNNER_LARGE -u DEVKIT_UPGRADE_CI_RUNNER_XLARGE \
        -u DEVKIT_UPGRADE_LEGACY_RESOLVE_RUNNER -u DEVKIT_UPGRADE_REPO_PRIVATE \
        PATH="$evidence/bin:$PATH" MATRIX_ROOT="$ROOT" MATRIX_EVIDENCE="$evidence" \
        RUNNER_TEMP="$evidence" GITHUB_OUTPUT="$evidence/outputs" \
        GITHUB_STEP_SUMMARY="$evidence/summary" TARGET=1.19.0 \
        BRANCH=chore/adopt-devkit BASE=dev \
        bash -eo pipefail -c "$upgrade
$body"
)

# A >=N workflow's context must also survive install.sh's isolated boundary.
# Start from the old dev scaffold again so stock seeded hooks must reconcile.
migrating_adoption() (
    local evidence="$1/.git/consumer-matrix" ws rc=0
    ws="$(mktemp -d)"
    trap 'rm -rf "$ws"' EXIT
    git -C "$1" archive dev | tar -x -C "$ws" || return 1
    git -C "$ws" init -q -b dev
    cd "$ws" || return 1
    env DEVKIT_UPGRADE_CONTEXT=1 DEVKIT_UPGRADE_CI_RUNNER_SMALL=pool-s \
        DEVKIT_UPGRADE_CI_RUNNER_LARGE=pool-l DEVKIT_UPGRADE_CI_RUNNER_XLARGE=pool-xl \
        DEVKIT_UPGRADE_LEGACY_RESOLVE_RUNNER= DEVKIT_UPGRADE_REPO_PRIVATE=true \
        PATH="$evidence/bin:$PATH" MATRIX_ROOT="$ROOT" MATRIX_EVIDENCE="$evidence" \
        bash "$ROOT/install.sh" --force --version 1.19.0 --skip-preflight --docker . \
        > "$evidence/migrating.log" 2>&1 || rc=$?
    cat "$evidence/migrating.log"
    ((rc == 0)) || return "$rc"
    if grep -q '^DEVKIT_CI_RUNNER=.' .vig-os; then
        echo 'migration context did not reach the scaffold'
        return 1
    fi
    grep -q '^ci-runner-migration: Seeded hook reconciled:' "$evidence/migrating.log"
)

gate_adoption() {
    local evidence=.git/consumer-matrix
    git merge-base --is-ancestor main dev || return 1
    [[ "$(git rev-list --count main..dev)" == 1 ]] || return 1
    [[ "$(git branch --show-current)" == chore/adopt-devkit ]] || return 1
    grep -qxF DEVKIT_CI_RUNNER=pool-legacy .vig-os || return 1
    local finding='ci-runner-migration: DEVKIT_CI_RUNNER kept; variables unknown (no CI upgrade context); required variables: CI_RUNNER_SMALL; set them at repository level on private GitHub Free repos. gh variable set CI_RUNNER_SMALL --body <label>; Until N+2 the key keeps working; after that CI fails until the required variables are set. Then delete the key. See MIGRATION.md#seeded-hook-runner-migration.'
    grep -qxF "$finding" "$evidence/install.log" || return 1
    grep -qx dev "$evidence/pr-base" || return 1
    grep -q 'Automated devkit upgrade' "$evidence/pr-body" || return 1
    if grep -qiE 'CI runner migration|ci-runner-migration:|DEVKIT_CI_RUNNER' "$evidence/pr-body"; then
        echo 'pre-N PR body unexpectedly lifted the runner migration'
        return 1
    fi
    echo 'pre-N main adoption targets dev, keeps the key, and omits the migration section'
}

# Execute the consumer action with the same input names its CI supplies.
# Capture and print its log so the full warning is visible in the matrix job.
gate_runners() (
    local evidence resolve
    evidence="$(mktemp -d)"
    trap 'rm -rf "$evidence"' EXIT
    resolve="$(step_script .github/actions/resolve-toolchain/action.yml 'Resolve mode + image tag')" || return 1
    env GITHUB_OUTPUT="$evidence/outputs" INPUT_IMAGE_TAG= \
        RUNNER_SMALL="$CELL_RUNNER_SMALL" RUNNER_LARGE="$CELL_RUNNER_LARGE" \
        RUNNER_XLARGE="$CELL_RUNNER_XLARGE" LEGACY_RESOLVE_RUNNER= \
        PR_PRESENT=true HEAD_REPO_FORK=false HEAD_REPOSITORY=example/consumer \
        BASE_REPOSITORY=example/consumer REPOSITORY_PRIVATE=true \
        bash -eo pipefail -c "$resolve" > "$evidence/ci.log" 2>&1
    local rc=$?
    cat "$evidence/ci.log"
    ((rc == 0)) || return "$rc"
    assert_runner_result "$evidence/outputs" "$evidence/ci.log"
)

assert_runner_result() {
    local runners sources expected source warning
    runners="$(sed -n 's/^runners=//p' "$1")"
    sources="$(sed -n 's/^runner-sources=//p' "$1")"
    if [[ -n "$CELL_RUNNER_SMALL" ]]; then
        expected="$(jq -cn --arg s "$CELL_RUNNER_SMALL" --arg l "$CELL_RUNNER_LARGE" \
            --arg xl "$CELL_RUNNER_XLARGE" '{small:[$s],large:[$l],xlarge:[$xl]}')"
        source=variable
        if grep -q '::warning::' "$2"; then return 1; fi
    else
        expected='{"small":["pool-legacy"],"large":["pool-legacy"],"xlarge":["pool-legacy"]}'
        source=legacy-key
        warning='::warning::DEVKIT_CI_RUNNER is deprecated and stops selecting runners in N+2.'
        warning+=' Unset required class: CI_RUNNER_SMALL; set it with gh variable set CI_RUNNER_SMALL --body <label>.'
        warning+=' Use repository-level variables on a private GitHub Free repo.'
        warning+=' Once every required class is set, the key decides nothing; delete DEVKIT_CI_RUNNER from .vig-os.'
        warning+=' See MIGRATION.md#run-ci-on-self-hosted-runners.'
        grep -qxF "$warning" "$2" || return 1
    fi
    expected="$(jq -c '. + {lint:.small,test:.small,extension:.small,"release-test":.small}' <<< "$expected")"
    jq -en --argjson actual "$runners" --argjson expected "$expected" '$actual == $expected' || return 1
    jq -en --argjson actual "$sources" --arg source "$source" \
        '$actual == {small:$source,large:$source,xlarge:$source}' || return 1
    echo "verified runners: $runners (source=$source)"
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
    local line rc=0 declared
    if [[ -n "$CELL_FIXTURE" ]]; then
        declared="$(sed -n 's/^DEVKIT_LANGUAGES=//p' .vig-os)"
        if [[ "$declared" == "$CELL_FIXTURE" ]]; then
            echo "detected: DEVKIT_LANGUAGES=$declared"
        else
            echo "NOT detected: expected DEVKIT_LANGUAGES=$CELL_FIXTURE, got '$declared'"
            rc=1
        fi
    fi
    if ((${#CELL_SEED[@]} == 0)); then
        echo "no seeded knobs"
        return "$rc"
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

# Run "$@" in the cell's environment: inside the rendered flake's dev shell for
# a flake cell (built by gate_flake_check), directly otherwise.
in_shell() {
    if [[ "$CELL_FLAKE" == true ]]; then
        nix develop "$CELL_PROFILE" --command "$@"
    else
        "$@"
    fi
}

# Evaluate the rendered flake against THIS checkout and build its dev shell
# into $CELL_PROFILE. The vigos override is what makes it this PR's toolchain
# (precedent: test-project's "Check downstream flake stub"); the rendered
# flake.nix floats on github:vig-os/devkit and ships no lock, so the lock stays
# in memory (--no-write-lock-file) and the tree stays clean.
gate_flake_check() {
    local -a flake_args=(--override-input vigos "path:$ROOT" --accept-flake-config --no-write-lock-file)
    nix flake check . "${flake_args[@]}" || return 1
    nix develop . "${flake_args[@]}" --profile "$CELL_PROFILE" --command true
}

# Hooks over the staged files only, as `git commit` invokes them: some hooks
# (check-added-large-files) inspect ADDED files, which a committed tree never
# has again, so this is the only gate that sees the first-scaffold commit.
# A flake cell's shell hook installs the generated config on entry, so only a
# non-flake cell without a scaffolded config skips (direnv-flake covers it).
gate_first_commit() {
    if [[ "$CELL_FLAKE" != true && ! -f .pre-commit-config.yaml ]]; then
        echo "SKIP: no .pre-commit-config.yaml (mode '$CELL_MODE' generates its hooks by flake eval; see direnv-flake)"
        return 0
    fi
    in_shell prek run --hook-stage pre-commit
}

gate_precommit() {
    if [[ "$CELL_FLAKE" != true && ! -f .pre-commit-config.yaml ]]; then
        echo "SKIP: no .pre-commit-config.yaml (mode '$CELL_MODE' generates its hooks by flake eval; see direnv-flake)"
        return 0
    fi
    in_shell just precommit
}

# `just test`, plus — for a fixture cell — proof the fixture suite ran. The
# recipes guard on a marker file and exit 0 when theirs is absent, so a green
# `just test` alone cannot tell "tested" from "skipped" (#1466, #1496).
gate_test() {
    local sentinel rc=0
    sentinel="$(mktemp -u "${RUNNER_TEMP:-${TMPDIR:-/tmp}}/consumer-matrix-sentinel.XXXXXX")"
    CONSUMER_MATRIX_SENTINEL="$sentinel" in_shell just test || rc=$?
    if ((rc == 0)) && [[ -n "$CELL_FIXTURE" ]]; then
        if [[ -f "$sentinel" ]]; then
            echo "fixture suite ran ($(cat "$sentinel"))"
        else
            echo "\`just test\` exited 0 but the $CELL_FIXTURE fixture suite never ran (silent no-op)"
            CELL_SILENT_NOOP=true
            rc=1
        fi
    fi
    rm -f "$sentinel"
    return "$rc"
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
    if [[ "$CELL_LANGUAGES_GUARD" == fire ]]; then
        # The firing guard's `::error::` lines are this cell's PASS evidence;
        # defuse them so they do not surface as PR annotations.
        env LANGUAGES="$languages" bash -eo pipefail -c "$guard" 2>&1 \
            | sed 's/^::error::/(expected) error: /' || rc=$?
        if ((rc == 0)); then
            echo "EXPECTED the declared-language guard to fire, but it passed (#1466 regression)"
            return 1
        fi
        echo "guard fired as expected (exit $rc)"
        return 0
    fi
    env LANGUAGES="$languages" bash -eo pipefail -c "$guard"
}

summary() {
    [[ -n "${GITHUB_STEP_SUMMARY:-}" ]] || return 0
    printf '%s\n' "$@" >>"$GITHUB_STEP_SUMMARY"
}

run_cell() {
    local cell="$1" ws="${2:-}" gate rc start verdict vrc=0 expected_gate="" issue=""
    local -a failed=()
    CELL_SILENT_NOOP=false
    read -r expected_gate issue <<<"$(expected_fail_spec "$cell")" || true
    # Per-gate and per-cell wall time, for the job summary: the cells run
    # concurrently and their logs are printed afterwards, so log timestamps
    # cannot show where the time went.
    SECONDS=0
    cell_spec "$cell"
    [[ -n "$ws" ]] || ws="$(mktemp -d "${RUNNER_TEMP:-${TMPDIR:-/tmp}}/consumer-matrix-$cell.XXXXXX")"
    CELL_PROFILE="$(mktemp -d "${RUNNER_TEMP:-${TMPDIR:-/tmp}}/consumer-matrix-profile.XXXXXX")/dev-profile"

    echo "== consumer-matrix cell '$cell' (mode=$CELL_MODE workflow=$CELL_WORKFLOW) in $ws"
    if ! render_cell "$cell" "$ws"; then
        echo "::error::consumer-matrix cell '$cell': render failed"
        summary "### Consumer matrix: \`$cell\` FAILED" "" "Render failed (assets/init-workspace.sh)."
        return 1
    fi

    cd "$ws"
    local branch=dev
    [[ "$CELL_WORKFLOW" == trunk ]] && branch=main
    [[ -d .git ]] || git init -q -b "$branch"
    git add -A

    # first-commit runs against the index, so it comes before the commit that
    # every later gate needs; the commit itself bypasses hooks so a red
    # first-commit gate does not hide the remaining gates' verdicts.
    local -a rows=("| gate | result | time |" "| --- | --- | --- |")
    local -a gates=(seed)
    [[ "$CELL_FLAKE" == true ]] && gates+=(flake-check)
    [[ "$cell" != runner-gitflow ]] || gates+=(adoption)
    case "$cell" in ci-runner | runner-key-only | runner-gitflow) gates+=(runners) ;; esac
    gates+=(first-commit commit sync lint precommit test actionlint zizmor languages)
    for gate in "${gates[@]}"; do
        if [[ "$gate" == commit ]]; then
            git -c user.name=consumer-matrix -c user.email=consumer-matrix@invalid \
                -c commit.gpgsign=false -c core.hooksPath=/dev/null \
                commit -q -m "chore: initial scaffold"
            continue
        fi
        echo "::group::$cell / $gate"
        rc=0
        start=$SECONDS
        case "$gate" in
            seed) gate_seed || rc=$? ;;
            adoption) gate_adoption || rc=$? ;;
            runners) gate_runners || rc=$? ;;
            flake-check) gate_flake_check || rc=$? ;;
            first-commit) gate_first_commit || rc=$? ;;
            sync) in_shell just sync || rc=$? ;;
            lint) in_shell just lint || rc=$? ;;
            precommit) gate_precommit || rc=$? ;;
            test) gate_test || rc=$? ;;
            actionlint) gate_actionlint || rc=$? ;;
            zizmor) gate_zizmor || rc=$? ;;
            languages) gate_languages || rc=$? ;;
        esac
        echo "::endgroup::"
        if ((rc == 0)); then
            rows+=("| $gate | pass | $((SECONDS - start)) s |")
        elif [[ "$gate" == "$expected_gate" ]]; then
            # Judged by cell_verdict below; no annotation for a known defect.
            echo "consumer-matrix cell '$cell': gate '$gate' failed (exit $rc), expected-fail candidate ($issue)"
            rows+=("| $gate | expected-fail ($issue) | $((SECONDS - start)) s |")
            failed+=("$gate")
        else
            echo "::error::consumer-matrix cell '$cell': gate '$gate' failed (exit $rc)"
            rows+=("| $gate | **FAIL** (exit $rc) | $((SECONDS - start)) s |")
            failed+=("$gate")
        fi
    done

    verdict="$(cell_verdict "$cell" "$CELL_SILENT_NOOP" ${failed[@]+"${failed[@]}"})" || vrc=$?
    summary "### Consumer matrix: \`$cell\` $verdict (${SECONDS} s)" "" "${rows[@]}" ""
    echo "== cell '$cell' $verdict (${SECONDS} s)"
    if ((vrc != 0)); then
        echo "::error::consumer-matrix cell '$cell': $verdict"
        return 1
    fi
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

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    set -euo pipefail
    main "$@"
fi
