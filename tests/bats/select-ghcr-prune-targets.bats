#!/usr/bin/env bats
# BATS tests for digest-aware GHCR RC prune target selection (#583).

setup() {
  load test_helper
  SCRIPT="${PROJECT_ROOT}/.github/scripts/select-ghcr-prune-targets.sh"
  FIXTURE="${PROJECT_ROOT}/tests/bats/fixtures/ghcr-versions.json"
}

@test "select-ghcr-prune-targets emits RC images and matching RC signatures only" {
  run bash "$SCRIPT" 0.3.5 <"$FIXTURE"
  assert_success
  mapfile -t ids < <(printf '%s\n' "${lines[@]}" | sort -n)
  assert_equal 4 "${#ids[@]}"
  assert_equal 932182788 "${ids[0]}"
  assert_equal 932185633 "${ids[1]}"
  assert_equal 932185755 "${ids[2]}"
  assert_equal 932189862 "${ids[3]}"
}

@test "select-ghcr-prune-targets preserves published release signature" {
  run bash "$SCRIPT" 0.3.5 <"$FIXTURE"
  assert_success
  refute_output --partial "932331806"
  refute_output --partial "932335861"
}

@test "select-ghcr-prune-targets leaves unrelated orphan signatures untouched" {
  run bash "$SCRIPT" 0.3.5 <"$FIXTURE"
  assert_success
  refute_output --partial "829404195"
}

@test "select-ghcr-prune-targets emits nothing when no RC versions exist" {
  run bash "$SCRIPT" 9.9.9 <"$FIXTURE"
  assert_success
  assert_output ""
}
