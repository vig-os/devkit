#!/usr/bin/env bash
# Wait for the Sigstore transparency log before retrying an attestation (#1399).
#
# `actions/attest` already retries internally: @actions/attest hardcodes
# DEFAULT_TIMEOUT = 10000 and DEFAULT_RETRIES = 3 into the Rekor witness, so a
# single action step makes 4 Rekor attempts (0/+1/+2/+4s) over roughly 47s. It
# exposes no input to widen that, which leaves the gap between our two attempts
# as the only lever we control. A fixed `sleep 30` there capped the whole
# envelope at about 2 minutes -- shorter than the Sigstore incident that took
# down 1.7.0-rc1 and rc2 (#1390).
#
# Rather than copy-pasting more attempts (Actions cannot loop over a `uses:`
# step), this waits until the log answers again, up to a minutes-scale
# deadline. That both covers a longer outage and returns as soon as the service
# is actually back, instead of burning a fixed interval either way.
#
# Always exits 0. Deciding the release's fate belongs to the retry step; a
# non-zero exit here would abort the job before that retry ever ran.
#
# Env:
#   REKOR_URL             transparency log base URL (default: public good instance)
#   REKOR_SETTLE_SECONDS  quiet period before the first probe (default: 30)
#   REKOR_PROBE_INTERVAL  seconds between probes (default: 30)
#   REKOR_WAIT_SECONDS    total budget before giving up and retrying anyway
#                         (default: 600)

set -uo pipefail

REKOR_URL="${REKOR_URL:-https://rekor.sigstore.dev}"
REKOR_SETTLE_SECONDS="${REKOR_SETTLE_SECONDS:-30}"
REKOR_PROBE_INTERVAL="${REKOR_PROBE_INTERVAL:-30}"
REKOR_WAIT_SECONDS="${REKOR_WAIT_SECONDS:-600}"

probe_url="${REKOR_URL%/}/api/v1/log"

# The attestation may have failed for a reason that has nothing to do with the
# log being down, in which case an immediate probe would succeed and we would
# retry straight back into the same broken state. Settle first, always.
echo "Attestation failed; settling ${REKOR_SETTLE_SECONDS}s before probing ${probe_url}"
sleep "$REKOR_SETTLE_SECONDS"
waited="$REKOR_SETTLE_SECONDS"

while true; do
  if curl -fsS --max-time 10 -o /dev/null "$probe_url"; then
    echo "✓ Transparency log responding after ${waited}s -- retrying attestation"
    exit 0
  fi

  if [ "$waited" -ge "$REKOR_WAIT_SECONDS" ]; then
    echo "Transparency log still unreachable after ${waited}s -- retrying anyway"
    exit 0
  fi

  echo "Transparency log unreachable after ${waited}s; probing again in ${REKOR_PROBE_INTERVAL}s"
  sleep "$REKOR_PROBE_INTERVAL"
  waited=$((waited + REKOR_PROBE_INTERVAL))
done
