#!/usr/bin/env bats
# BATS tests for the bash retry() helper (setup-env / sync-main-to-dev).
# Regression: exit code after failed command must not be 0 (#500).

bats_require_minimum_version 1.5.0

setup() {
  load test_helper
  # shellcheck source=tests/bats/fixtures/retry_helper.bash
  source "${PROJECT_ROOT}/tests/bats/fixtures/retry_helper.bash"
}

@test "retry returns 0 when command succeeds on first attempt" {
  run retry --retries 3 --backoff 0 --max-backoff 0 -- true
  assert_success
  assert_output ""
}

@test "retry returns the command exit code when all attempts fail" {
  run retry --retries 2 --backoff 0 --max-backoff 0 -- bash -c 'exit 42'
  assert_failure
  assert_equal 42 "$status"
}

@test "retry retry message includes non-zero exit code" {
  run retry --retries 2 --backoff 0 --max-backoff 0 -- bash -c 'exit 7'
  assert_failure
  assert_equal 7 "$status"
  assert_output --partial "Retry 1/2 failed (exit 7)"
  assert_output --partial "ERROR: Command failed after 2 attempts"
}

@test "retry succeeds after transient failure" {
  count_file="$(mktemp)"
  echo 0 >"$count_file"
  run retry --retries 3 --backoff 0 --max-backoff 0 -- bash -c "
    n=\$(cat '$count_file')
    echo \$((n + 1)) > '$count_file'
    [ \"\$n\" -ge 1 ]
  "
  rm -f "$count_file"
  assert_success
}

@test "retry errors when no command after --" {
  run retry --retries 1 --
  assert_failure
  assert_equal 2 "$status"
  assert_output --partial "requires a command after '--'"
}
