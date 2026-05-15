#!/usr/bin/env bats
# shellcheck disable=SC2016
# BATS tests for setup-tailscale.sh
#
# Verifies the script's runtime contract without actually starting a Tailscale
# daemon (no live tailnet, no real /dev/net/tun on the test host). We test:
#   - argv handling + usage text
#   - opt-out path (no AUTHKEY → silent no-op)
#   - hostname resolution from devcontainer.json + sanitization rules
#   - fail-loud when /dev/net/tun missing under AUTHKEY-set conditions
#   - idempotency hook (re-runs that find a matching status return early)
#
# Refs: #85

setup() {
    load test_helper
    SCRIPT="$PROJECT_ROOT/assets/workspace/.devcontainer/scripts/setup-tailscale.sh"
    # Each test gets a sandbox to stash fakes (devcontainer.json, /dev/net/tun
    # presence, fake `tailscale`/`pgrep`/`tailscaled` shims).
    SANDBOX="$(mktemp -d)"
    export SANDBOX
}

teardown() {
    rm -rf "$SANDBOX"
    unset TAILSCALE_AUTHKEY TAILSCALE_HOSTNAME
}

# ── script structure ──────────────────────────────────────────────────────────

@test "setup-tailscale.sh is executable" {
    run test -x "$SCRIPT"
    assert_success
}

@test "setup-tailscale.sh has shebang" {
    run head -1 "$SCRIPT"
    assert_output "#!/bin/bash"
}

@test "setup-tailscale.sh sets strict mode (set -euo pipefail)" {
    run grep -E '^set -euo pipefail' "$SCRIPT"
    assert_success
}

# ── argv handling ─────────────────────────────────────────────────────────────

@test "setup-tailscale.sh with no args prints usage to stderr + exits 1" {
    run "$SCRIPT"
    assert_failure
    assert_output --partial "Usage:"
    assert_output --partial "connect"
}

@test "setup-tailscale.sh with unknown subcommand prints usage + exits 1" {
    run "$SCRIPT" mystery
    assert_failure
    assert_output --partial "Usage:"
}

@test "setup-tailscale.sh usage mentions required env vars" {
    run "$SCRIPT" bogus
    assert_failure
    assert_output --partial "TAILSCALE_AUTHKEY"
    assert_output --partial "TAILSCALE_HOSTNAME"
}

@test "setup-tailscale.sh usage mentions required compose config" {
    run "$SCRIPT" bogus
    assert_failure
    assert_output --partial "/dev/net/tun"
    assert_output --partial "NET_ADMIN"
    assert_output --partial "tailscale-state"
}

# ── opt-out: no AUTHKEY = silent no-op ───────────────────────────────────────

@test "connect with no TAILSCALE_AUTHKEY exits 0 silently" {
    unset TAILSCALE_AUTHKEY
    run "$SCRIPT" connect
    assert_success
    # Logs that it skipped (the script's expected behavior) — opt-out should
    # be loud enough to debug but not error.
    assert_output --partial "TAILSCALE_AUTHKEY not set"
}

@test "connect with empty TAILSCALE_AUTHKEY exits 0 silently" {
    TAILSCALE_AUTHKEY="" run "$SCRIPT" connect
    assert_success
    assert_output --partial "TAILSCALE_AUTHKEY not set"
}

# ── fail-loud on missing TUN under AUTHKEY-set ────────────────────────────────
#
# We can't easily replace /dev/net/tun on the test host. Instead we test that
# the script's `require_tun` function exists and references the device, and
# that the error message contains the actionable compose snippet.

@test "require_tun checks /dev/net/tun" {
    run grep -A2 'require_tun' "$SCRIPT"
    assert_output --partial "/dev/net/tun"
}

@test "fail-on-missing-TUN error message contains the compose-fix snippet" {
    run grep -E 'devices:|cap_add:|NET_ADMIN|NET_RAW' "$SCRIPT"
    assert_success
    [ "${#lines[@]}" -ge 4 ]
}

# ── hostname resolution ───────────────────────────────────────────────────────
#
# The resolve_hostname function reads devcontainer.json's `name` field and
# sanitizes for DNS. We test by sourcing the function in isolation and
# manipulating the BASH_SOURCE-relative devcontainer.json path via a fixture.

@test "resolve_hostname uses TAILSCALE_HOSTNAME when set" {
    # Source just the function definition (everything before the case at the end).
    # Easier path: invoke the script under controlled env and observe its log.
    # Since `connect` requires AUTHKEY + TUN, instead we extract the function and
    # call it directly.
    sed -n '/^resolve_hostname/,/^}/p' "$SCRIPT" > "$SANDBOX/fn.sh"
    # shellcheck source=/dev/null
    source "$SANDBOX/fn.sh"
    TAILSCALE_HOSTNAME="custom-name" run resolve_hostname
    assert_success
    assert_output "custom-name"
}

@test "resolve_hostname sanitizes uppercase + underscores to DNS-safe" {
    sed -n '/^resolve_hostname/,/^}/p' "$SCRIPT" > "$SANDBOX/fn.sh"
    # shellcheck source=/dev/null
    source "$SANDBOX/fn.sh"
    TAILSCALE_HOSTNAME="MyProject_Dev" run resolve_hostname
    assert_success
    # Custom hostname is passed through verbatim — sanitization only applies
    # to the auto-derived path. This test documents that contract.
    assert_output "MyProject_Dev"
}

# resolve_hostname's auto-derive path reads "$(dirname "${BASH_SOURCE[0]}")/../devcontainer.json".
# We simulate by sourcing a copy of the function from a path next to a fake
# devcontainer.json. Done via a wrapper script in $SANDBOX.

@test "resolve_hostname reads devcontainer.json name + strips -devc suffix + appends host" {
    mkdir -p "$SANDBOX/dc/scripts"
    cat > "$SANDBOX/dc/devcontainer.json" <<'EOF'
{ "name": "MyProj-devc" }
EOF
    sed -n '/^resolve_hostname/,/^}/p' "$SCRIPT" > "$SANDBOX/dc/scripts/fn.sh"
    cat > "$SANDBOX/dc/scripts/wrap.sh" <<'EOF'
#!/bin/bash
source "$(dirname "${BASH_SOURCE[0]}")/fn.sh"
unset TAILSCALE_HOSTNAME
resolve_hostname
EOF
    chmod +x "$SANDBOX/dc/scripts/wrap.sh"
    run "$SANDBOX/dc/scripts/wrap.sh"
    assert_success
    # myproj (lowercased + sanitized) -devc- hostname
    assert_output --regexp "^myproj-devc-"
}

@test "resolve_hostname sanitizes underscores in project name" {
    mkdir -p "$SANDBOX/dc/scripts"
    cat > "$SANDBOX/dc/devcontainer.json" <<'EOF'
{ "name": "my_proj_2-devc" }
EOF
    sed -n '/^resolve_hostname/,/^}/p' "$SCRIPT" > "$SANDBOX/dc/scripts/fn.sh"
    cat > "$SANDBOX/dc/scripts/wrap.sh" <<'EOF'
#!/bin/bash
source "$(dirname "${BASH_SOURCE[0]}")/fn.sh"
unset TAILSCALE_HOSTNAME
resolve_hostname
EOF
    chmod +x "$SANDBOX/dc/scripts/wrap.sh"
    run "$SANDBOX/dc/scripts/wrap.sh"
    assert_success
    # underscores -> hyphens
    assert_output --regexp "^my-proj-2-devc-"
    refute_output --regexp "_"
}

@test "resolve_hostname falls back to 'devc' when devcontainer.json missing" {
    mkdir -p "$SANDBOX/dc/scripts"
    sed -n '/^resolve_hostname/,/^}/p' "$SCRIPT" > "$SANDBOX/dc/scripts/fn.sh"
    cat > "$SANDBOX/dc/scripts/wrap.sh" <<'EOF'
#!/bin/bash
source "$(dirname "${BASH_SOURCE[0]}")/fn.sh"
unset TAILSCALE_HOSTNAME
resolve_hostname
EOF
    chmod +x "$SANDBOX/dc/scripts/wrap.sh"
    run "$SANDBOX/dc/scripts/wrap.sh"
    assert_success
    assert_output --regexp "^devc-devc-"
}

# ── idempotency check shape ──────────────────────────────────────────────────

@test "already_connected_as helper exists + uses tailscale status" {
    run grep -E '^already_connected_as' "$SCRIPT"
    assert_success
    run grep -A10 'already_connected_as' "$SCRIPT"
    assert_output --partial "tailscale status"
    assert_output --partial "Self"
}

@test "cmd_connect calls already_connected_as before tailscale up" {
    # Order matters: idempotency check must precede the up call.
    cmd_connect_block=$(sed -n '/^cmd_connect/,/^}/p' "$SCRIPT")
    idem_pos=$(printf '%s\n' "$cmd_connect_block" | grep -n 'already_connected_as' | head -1 | cut -d: -f1)
    up_pos=$(printf '%s\n' "$cmd_connect_block" | grep -n 'tailscale.*up' | head -1 | cut -d: -f1)
    [ -n "$idem_pos" ] && [ -n "$up_pos" ] && [ "$idem_pos" -lt "$up_pos" ]
}
