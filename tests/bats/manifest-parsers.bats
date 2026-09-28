#!/usr/bin/env bats
# BATS tests for .vig-os manifest parser tolerance (#885)
#
# .vig-os grew from a single version pin into the project manifest
# (DEVKIT_MODE, DEVKIT_PROJECT, DEVKIT_ORG, DEVKIT_REPO, DEVKIT_MODULES).
# Every existing consumer is a tolerant line-based parser that matches
# DEVCONTAINER_VERSION=* and skips everything else, so the new keys must be
# invisible to them: these tests run the real template scripts against a
# version-only and a full-manifest .vig-os and assert byte-identical results.
# (The devkit's own root resolve-image composite action was removed in #996; the
# scaffold's mode-aware resolve-toolchain parser is covered under assets/workspace.)

bats_require_minimum_version 1.5.0

setup() {
    load test_helper
    TEMPLATE_SCRIPTS="$PROJECT_ROOT/assets/workspace/.devcontainer/scripts"
}

# Write a version-only (legacy) manifest to $1.
_version_only_manifest() {
    cat > "$1" <<'EOF'
# vig-os devcontainer configuration
DEVCONTAINER_VERSION=0.4.0
EOF
}

# Write a full #885 manifest — plus an unknown future key — to $1.
_full_manifest() {
    cat > "$1" <<'EOF'
# vig-os devcontainer configuration
DEVCONTAINER_VERSION=0.4.0
DEVKIT_MODE=both
DEVKIT_PROJECT=probe
DEVKIT_ORG=Probe/Org
DEVKIT_REPO=probe/probe
DEVKIT_MODULES="native rust"
DEVKIT_FUTURE_FLAG=whatever
EOF
}

# The rename (#781) moves the pin key to DEVKIT_VERSION. Write a manifest that
# carries only the new key to $1.
_devkit_only_manifest() {
    cat > "$1" <<'EOF'
# vig-os devkit configuration
DEVKIT_VERSION=1.2.3
EOF
}

# Write a manifest carrying BOTH keys with different values to $1 — the parser
# must prefer DEVKIT_VERSION over the legacy DEVCONTAINER_VERSION (#781).
_dual_key_manifest() {
    cat > "$1" <<'EOF'
# vig-os devkit configuration
DEVCONTAINER_VERSION=0.4.0
DEVKIT_VERSION=1.2.3
EOF
}

# Build a minimal consumer fixture tree at $1 (root with .vig-os written by
# $2, .devcontainer/scripts with the real initialize.sh/version-check.sh and
# a stubbed copy-host-user-conf.sh).
_fixture_tree() {
    local root="$1" manifest_writer="$2"
    mkdir -p "$root/.devcontainer/scripts"
    "$manifest_writer" "$root/.vig-os"
    cp "$TEMPLATE_SCRIPTS/initialize.sh" "$root/.devcontainer/scripts/"
    cp "$TEMPLATE_SCRIPTS/version-check.sh" "$root/.devcontainer/scripts/"
    printf '#!/usr/bin/env bash\nexit 0\n' \
        > "$root/.devcontainer/scripts/copy-host-user-conf.sh"
    chmod +x "$root/.devcontainer/scripts/"*.sh
}

@test "initialize.sh resolves the version pin despite manifest keys (#885)" {
    root="$BATS_TEST_TMPDIR/init-full"
    _fixture_tree "$root" _full_manifest
    run bash "$root/.devcontainer/scripts/initialize.sh"
    assert_success
    run grep -x 'DEVCONTAINER_VERSION=0.4.0' "$root/.devcontainer/.env"
    assert_success
}

@test "initialize.sh output is byte-identical for legacy and full manifests (#885)" {
    legacy="$BATS_TEST_TMPDIR/init-legacy"
    full="$BATS_TEST_TMPDIR/init-full-cmp"
    _fixture_tree "$legacy" _version_only_manifest
    _fixture_tree "$full" _full_manifest
    run bash "$legacy/.devcontainer/scripts/initialize.sh"
    assert_success
    run bash "$full/.devcontainer/scripts/initialize.sh"
    assert_success
    run diff "$legacy/.devcontainer/.env" "$full/.devcontainer/.env"
    assert_success
}

@test "version-check.sh resolves the version pin despite manifest keys (#885)" {
    root="$BATS_TEST_TMPDIR/vc-full"
    _fixture_tree "$root" _full_manifest
    run bash "$root/.devcontainer/scripts/version-check.sh" config
    assert_success
    assert_output --partial "Current ver:    0.4.0"
}

@test "version-check.sh output is byte-identical for legacy and full manifests (#885)" {
    legacy="$BATS_TEST_TMPDIR/vc-legacy"
    full="$BATS_TEST_TMPDIR/vc-full-cmp"
    _fixture_tree "$legacy" _version_only_manifest
    _fixture_tree "$full" _full_manifest
    # The report prints the fixture's own absolute config path; normalize the
    # differing tree roots so the comparison is about parsing, not paths.
    legacy_out="$(bash "$legacy/.devcontainer/scripts/version-check.sh" config \
        | sed "s|$legacy|ROOT|")"
    full_out="$(bash "$full/.devcontainer/scripts/version-check.sh" config \
        | sed "s|$full|ROOT|")"
    [ "$legacy_out" = "$full_out" ]
}

@test "initialize.sh reads the renamed DEVKIT_VERSION pin (#781)" {
    root="$BATS_TEST_TMPDIR/init-devkit"
    _fixture_tree "$root" _devkit_only_manifest
    run bash "$root/.devcontainer/scripts/initialize.sh"
    assert_success
    run grep -x 'DEVCONTAINER_VERSION=1.2.3' "$root/.devcontainer/.env"
    assert_success
}

@test "initialize.sh prefers DEVKIT_VERSION over legacy pin (#781)" {
    root="$BATS_TEST_TMPDIR/init-dual"
    _fixture_tree "$root" _dual_key_manifest
    run bash "$root/.devcontainer/scripts/initialize.sh"
    assert_success
    run grep -x 'DEVCONTAINER_VERSION=1.2.3' "$root/.devcontainer/.env"
    assert_success
}

@test "version-check.sh reads the renamed DEVKIT_VERSION pin (#781)" {
    root="$BATS_TEST_TMPDIR/vc-devkit"
    _fixture_tree "$root" _devkit_only_manifest
    run bash "$root/.devcontainer/scripts/version-check.sh" config
    assert_success
    assert_output --partial "Current ver:    1.2.3"
}

@test "version-check.sh prefers DEVKIT_VERSION over legacy pin (#781)" {
    root="$BATS_TEST_TMPDIR/vc-dual"
    _fixture_tree "$root" _dual_key_manifest
    run bash "$root/.devcontainer/scripts/version-check.sh" config
    assert_success
    assert_output --partial "Current ver:    1.2.3"
}
