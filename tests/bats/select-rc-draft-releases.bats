#!/usr/bin/env bats
# BATS tests for RC draft pre-release selection used by promote-release cleanup (#623).

setup() {
  load test_helper
  SCRIPT="${PROJECT_ROOT}/.github/scripts/select-rc-draft-releases.sh"
  FIXTURE="${PROJECT_ROOT}/tests/bats/fixtures/releases-list.json"
}

@test "select-rc-draft-releases emits id and tag for every RC draft pre-release of the base" {
  run bash "$SCRIPT" 0.3.8 <"$FIXTURE"
  assert_success
  assert_line "1001	0.3.8-rc1"
  assert_line "1002	0.3.8-rc2"
}

@test "select-rc-draft-releases ignores published (non-draft) RC pre-releases" {
  run bash "$SCRIPT" 0.3.8 <"$FIXTURE"
  assert_success
  refute_output --partial "1003"
}

@test "select-rc-draft-releases ignores draft final (non-prerelease) releases" {
  run bash "$SCRIPT" 0.3.8 <"$FIXTURE"
  assert_success
  refute_output --partial "1004"
  refute_output --partial "1005"
}

@test "select-rc-draft-releases ignores RC drafts of other base versions" {
  run bash "$SCRIPT" 0.3.8 <"$FIXTURE"
  assert_success
  refute_output --partial "0.3.7-rc1"
  refute_output --partial "0.3.80-rc1"
}

@test "select-rc-draft-releases ignores malformed rc suffixes" {
  run bash "$SCRIPT" 0.3.8 <"$FIXTURE"
  assert_success
  refute_output --partial "0.3.8-rcx"
}

@test "select-rc-draft-releases emits nothing when no RC drafts match" {
  run bash "$SCRIPT" 9.9.9 <"$FIXTURE"
  assert_success
  assert_output ""
}

@test "select-rc-draft-releases rejects an invalid base version" {
  run bash "$SCRIPT" not-a-version <"$FIXTURE"
  assert_failure
}

@test "select-rc-draft-releases requires exactly one argument" {
  run bash "$SCRIPT"
  assert_failure
}
