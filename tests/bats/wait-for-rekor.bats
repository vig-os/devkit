#!/usr/bin/env bats
# BATS tests for the attestation backoff helper (#1399).
#
# The helper stands between a failed attestation attempt and its retry. It must
# wait for the transparency log to actually come back rather than sleeping a
# fixed interval, and it must never fail the step itself -- failing the release
# is the retry step's job, not the wait's.

setup() {
  load test_helper
  SCRIPT="${PROJECT_ROOT}/.github/scripts/wait-for-rekor.sh"

  STUB_DIR="${BATS_TEST_TMPDIR}/stubs"
  mkdir -p "$STUB_DIR"

  # Simulated clock: sleeps return immediately so the deadline logic is
  # exercised without spending real seconds.
  cat >"${STUB_DIR}/sleep" <<'STUB'
#!/usr/bin/env bash
echo "sleep $1" >>"${SLEEP_LOG}"
STUB
  chmod +x "${STUB_DIR}/sleep"

  export SLEEP_LOG="${BATS_TEST_TMPDIR}/sleeps"
  export CURL_LOG="${BATS_TEST_TMPDIR}/curls"
  : >"$SLEEP_LOG"
  : >"$CURL_LOG"

  export PATH="${STUB_DIR}:${PATH}"
  export REKOR_SETTLE_SECONDS=30
  export REKOR_PROBE_INTERVAL=30
  export REKOR_WAIT_SECONDS=600
}

# Install a curl stub that fails $1 times before succeeding.
stub_curl_failing_times() {
  cat >"${STUB_DIR}/curl" <<STUB
#!/usr/bin/env bash
echo "\$*" >>"\${CURL_LOG}"
attempts=\$(wc -l <"\${CURL_LOG}")
[ "\$attempts" -gt "$1" ]
STUB
  chmod +x "${STUB_DIR}/curl"
}

@test "wait-for-rekor returns as soon as the transparency log answers" {
  stub_curl_failing_times 0

  run bash "$SCRIPT"
  assert_success
  assert_output --partial "responding"

  # One settle sleep, then a successful probe -- no further waiting.
  assert_equal 1 "$(wc -l <"$SLEEP_LOG")"
}

@test "wait-for-rekor keeps probing while the log is down" {
  stub_curl_failing_times 3

  run bash "$SCRIPT"
  assert_success
  assert_output --partial "responding"

  # Four probes: three refused, the fourth answered.
  assert_equal 4 "$(wc -l <"$CURL_LOG")"
}

@test "wait-for-rekor gives up at the deadline without failing the step" {
  stub_curl_failing_times 9999
  export REKOR_WAIT_SECONDS=120

  run bash "$SCRIPT"
  # Never non-zero: the retry step is what decides the release's fate. A
  # failing wait would abort the job before the retry ever ran.
  assert_success
  assert_output --partial "still unreachable"

  # Settle (30) + probes at 60/90/120 -- bounded by the deadline, not endless.
  assert_equal 4 "$(wc -l <"$SLEEP_LOG")"
}

@test "wait-for-rekor probes the configured transparency log" {
  stub_curl_failing_times 0
  export REKOR_URL="https://rekor.example.test"

  run bash "$SCRIPT"
  assert_success
  assert_output --partial "https://rekor.example.test/api/v1/log"
  run cat "$CURL_LOG"
  assert_output --partial "https://rekor.example.test/api/v1/log"
}

@test "wait-for-rekor settles before its first probe" {
  # The failure may not have been Rekor at all; probing instantly would retry
  # into the same broken state.
  stub_curl_failing_times 0

  run bash "$SCRIPT"
  assert_success
  run head -n 1 "$SLEEP_LOG"
  assert_output "sleep 30"
}
