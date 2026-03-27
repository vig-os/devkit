#!/bin/bash

# Tailscale SSH setup for devcontainer — opt-in via TAILSCALE_AUTHKEY env var.
#
# Subcommands:
#   install  — install Tailscale (called from post-create.sh, runs once)
#   start    — start tailscaled + tailscale up --ssh (called from post-start.sh, runs every start)
#
# Both subcommands are silent no-ops when TAILSCALE_AUTHKEY is unset or empty.

set -euo pipefail

# ── helpers ──────────────────────────────────────────────────────────────────

require_authkey() {
    if [ -z "${TAILSCALE_AUTHKEY:-}" ]; then
        echo "Tailscale: TAILSCALE_AUTHKEY not set, skipping."
        return 1
    fi
    return 0
}

resolve_hostname() {
    if [ -n "${TAILSCALE_HOSTNAME:-}" ]; then
        echo "$TAILSCALE_HOSTNAME"
        return
    fi

    local project="devc"
    local devc_json
    devc_json="$(dirname "${BASH_SOURCE[0]}")/../devcontainer.json"
    if [ -f "$devc_json" ]; then
        local name
        name=$(python3 -c "import json,sys; print(json.load(sys.stdin).get('name',''))" < "$devc_json" 2>/dev/null || true)
        if [ -n "$name" ]; then
            project="${name%-devc}"
        fi
    fi

    # Sanitize: DNS labels cannot contain underscores
    project="${project//_/-}"
    echo "${project}-devc-$(hostname -s)"
}

# ── subcommands ──────────────────────────────────────────────────────────────

cmd_install() {
    require_authkey || return 0

    if command -v tailscale &>/dev/null; then
        echo "Tailscale: already installed, skipping install."
        return 0
    fi

    echo "Tailscale: installing..."
    # Containers often have clock skew causing apt "Release file not valid yet".
    # Install directly from Tailscale repo with clock-skew workaround.
    curl -fsSL https://pkgs.tailscale.com/stable/debian/bookworm.noarmor.gpg \
        | tee /usr/share/keyrings/tailscale-archive-keyring.gpg >/dev/null
    echo "deb [signed-by=/usr/share/keyrings/tailscale-archive-keyring.gpg] https://pkgs.tailscale.com/stable/debian bookworm main" \
        | tee /etc/apt/sources.list.d/tailscale.list
    # Only update the tailscale repo (avoids clock-skew failures on other repos)
    apt-get -o Acquire::Check-Valid-Until=false update \
        -o Dir::Etc::sourcelist=/etc/apt/sources.list.d/tailscale.list \
        -o Dir::Etc::sourceparts=- -qq 2>/dev/null
    apt-get install -y -qq tailscale
    echo "Tailscale: install complete."
}

cmd_start() {
    require_authkey || return 0

    local hostname
    hostname=$(resolve_hostname)

    echo "Tailscale: starting (hostname=$hostname)..."

    if ! pgrep -x tailscaled &>/dev/null; then
        # Use real TUN if /dev/net/tun exists (required for Tailscale SSH to work).
        # Falls back to userspace networking (outbound-only, no SSH server).
        local tun_flag=""
        if [ ! -c /dev/net/tun ]; then
            echo "Tailscale: WARNING — /dev/net/tun not available. SSH into container will NOT work." >&2
            echo "Tailscale: Add 'devices: [\"/dev/net/tun:/dev/net/tun\"]' and 'cap_add: [NET_ADMIN, NET_RAW]' to compose." >&2
            tun_flag="--tun=userspace-networking"
        fi
        # shellcheck disable=SC2086
        setsid tailscaled $tun_flag --state=/var/lib/tailscale/tailscaled.state &>/dev/null &
        sleep 2
    fi

    if tailscale up --ssh --authkey="$TAILSCALE_AUTHKEY" --hostname="$hostname"; then
        echo "Tailscale: connected as $hostname"
    else
        echo "Tailscale: WARNING — failed to connect. Container still usable via devcontainer protocol." >&2
    fi
}

# ── main ─────────────────────────────────────────────────────────────────────

case "${1:-}" in
    install) cmd_install ;;
    start)   cmd_start ;;
    *)
        echo "Usage: $(basename "$0") {install|start}" >&2
        exit 1
        ;;
esac
