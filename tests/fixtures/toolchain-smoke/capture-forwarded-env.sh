#!/usr/bin/env bash
# BASH_ENV hook used only by the smoke job. Capture the forwarding step's
# actual command file; other action steps export unrelated installer settings.
devkit_smoke_capture_env() {
  if declare -F devkit_dump_env >/dev/null; then
    cp "$GITHUB_ENV" "$RUNNER_TEMP/devkit-smoke-forwarded-env"
  fi
}
trap devkit_smoke_capture_env EXIT
