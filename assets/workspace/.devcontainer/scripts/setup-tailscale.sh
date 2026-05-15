#!/bin/bash

# setup-tailscale.sh — bring the container into the user's tailnet.
#
# Tailscale binaries (tailscale + tailscaled) are baked into the image at
# build time, so this script only handles the runtime concerns:
#   - opt-in via TAILSCALE_AUTHKEY env var (no key, no daemon)
#   - daemon startup with state in a persistent compose volume
#   - idempotent: re-runs are no-ops when already authed under the same hostname
#   - fail loud (exit non-zero) on missing /dev/net/tun + caps — the silent
#     userspace-networking fallback was removed because it cannot serve
#     inbound SSH, which is the entire point of running Tailscale here
#
# Single subcommand `connect` (kept for forward-compat with potential `down`,
# `status` siblings later — see issue #545+ for `just tailscale-*` recipes).

set -euo pipefail

STATE_DIR="/var/lib/tailscale"
STATE_FILE="$STATE_DIR/tailscaled.state"
SOCKET="/var/run/tailscale/tailscaled.sock"
LOG_TAG="Tailscale:"

log()  { printf '%s %s\n' "$LOG_TAG" "$*"; }
warn() { printf '%s WARNING: %s\n' "$LOG_TAG" "$*" >&2; }
die()  { printf '%s ERROR: %s\n' "$LOG_TAG" "$*" >&2; exit 1; }

require_authkey() {
    [ -n "${TAILSCALE_AUTHKEY:-}" ] && return 0
    log "TAILSCALE_AUTHKEY not set, skipping (this is the documented opt-out path)."
    return 1
}

require_tun() {
    if [ ! -c /dev/net/tun ]; then
        die "/dev/net/tun is not available inside the container — Tailscale SSH cannot work without a real TUN device.

The default workspace docker-compose.yml ships with the necessary device + caps:
    devices:
      - /dev/net/tun:/dev/net/tun
    cap_add:
      - NET_ADMIN
      - NET_RAW

If you've customized your compose file, restore those entries (or unset TAILSCALE_AUTHKEY to skip Tailscale entirely)."
    fi
}

resolve_hostname() {
    if [ -n "${TAILSCALE_HOSTNAME:-}" ]; then
        printf '%s\n' "$TAILSCALE_HOSTNAME"
        return
    fi
    local project="devc"
    local devc_json
    devc_json="$(dirname "${BASH_SOURCE[0]}")/../devcontainer.json"
    if [ -f "$devc_json" ]; then
        local name
        name=$(python3 -c \
            "import json,sys; print(json.load(sys.stdin).get('name',''))" \
            < "$devc_json" 2>/dev/null || true)
        if [ -n "$name" ]; then
            project="${name%-devc}"
        fi
    fi
    # DNS labels: lowercase + alphanumerics + hyphens. Replace anything else.
    project="$(printf '%s' "$project" | tr '[:upper:]_' '[:lower:]-' | tr -cd 'a-z0-9-')"
    printf '%s-devc-%s\n' "$project" "$(hostname -s)"
}

# Returns 0 if tailscaled is already running and "up" against our intended
# hostname; otherwise returns non-zero so cmd_connect proceeds with `up`.
already_connected_as() {
    local want="$1"
    pgrep -x tailscaled >/dev/null 2>&1 || return 1
    [ -S "$SOCKET" ] || return 1
    # Tailscale CLI uses the daemon socket; --self gives the local node info.
    local got
    got=$(tailscale status --self --json 2>/dev/null \
            | python3 -c \
                "import json,sys; d=json.load(sys.stdin); print(d.get('Self',{}).get('HostName',''))" \
                2>/dev/null || true)
    [ -n "$got" ] && [ "$got" = "$want" ]
}

cmd_connect() {
    require_authkey || return 0
    require_tun

    local hostname
    hostname=$(resolve_hostname)
    log "target hostname: $hostname"

    if already_connected_as "$hostname"; then
        log "already connected as $hostname — no-op"
        return 0
    fi

    mkdir -p "$STATE_DIR" "$(dirname "$SOCKET")"

    if ! pgrep -x tailscaled >/dev/null 2>&1; then
        log "starting tailscaled (state=$STATE_FILE socket=$SOCKET)"
        # setsid detaches the daemon from this shell's process group so it
        # survives postStartCommand's exit. Output to a log file (overflowing
        # to container stderr would spam compose logs).
        setsid /usr/local/sbin/tailscaled \
            --state="$STATE_FILE" \
            --socket="$SOCKET" \
            >/var/log/tailscaled.log 2>&1 &
        # Wait briefly for the socket — gives a clean error if the daemon
        # crashes immediately (TUN missing, perms wrong) rather than a vague
        # "tailscale up failed" later.
        local _
        for _ in $(seq 1 20); do
            [ -S "$SOCKET" ] && break
            sleep 0.25
        done
        [ -S "$SOCKET" ] || die "tailscaled failed to create socket within 5s — check /var/log/tailscaled.log"
    fi

    log "tailscale up --ssh --hostname=$hostname"
    if tailscale --socket="$SOCKET" up \
            --ssh \
            --authkey="$TAILSCALE_AUTHKEY" \
            --hostname="$hostname" \
            --accept-routes; then
        log "connected as $hostname"
    else
        die "tailscale up failed — check /var/log/tailscaled.log + Tailscale ACLs (must allow SSH for autogroup:member -> autogroup:self)"
    fi
}

case "${1:-}" in
    connect) cmd_connect ;;
    *)
        cat <<EOF >&2
Usage: $(basename "$0") connect

Brings the container into the tailnet identified by \$TAILSCALE_AUTHKEY.
No-ops silently when TAILSCALE_AUTHKEY is unset.

Env vars:
  TAILSCALE_AUTHKEY   required — opt-in. Without it, this is a no-op.
  TAILSCALE_HOSTNAME  optional — overrides the auto-derived <project>-devc-<host> name.

Required compose config (shipped by default in the workspace template):
  devices:    [/dev/net/tun:/dev/net/tun]
  cap_add:    [NET_ADMIN, NET_RAW]
  volumes:    [tailscale-state:/var/lib/tailscale]
EOF
        exit 1
        ;;
esac
