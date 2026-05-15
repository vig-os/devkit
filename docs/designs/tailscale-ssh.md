# Tailscale SSH for Devcontainers

Design document for opt-in Tailscale SSH access to vigOS devcontainers.

Refs: #85

## Problem

Cursor's devcontainer-protocol mode cannot route shell commands through the AI agent (Cursor IDE limitation; the agent's shell tool fails). VS Code's devcontainer protocol works fine, and Cursor's CLI/terminal mode also works — only Cursor GUI + devcontainer protocol is broken.

The workaround is to bypass the devcontainer protocol entirely: connect Cursor (and other IDEs) via SSH to the container, treating it as a regular host on the user's tailnet. No port forwarding, no jump hosts, no manual ssh-key juggling.

## Solution

Run Tailscale inside the devcontainer with SSH enabled. The user generates an auth key once (manually or via OAuth API), exposes it via `TAILSCALE_AUTHKEY` in `docker-compose.local.yaml`, and the post-start lifecycle hook brings the container into the tailnet on every start.

Connect with `ssh root@<hostname>` from anywhere on the tailnet.

## Architecture decisions

| Decision | Choice | Rationale |
|---|---|---|
| Networking mode | **Real TUN** (`/dev/net/tun` device + `NET_ADMIN`/`NET_RAW` caps) | Tailscale's `--ssh` server requires a real TUN device. `--tun=userspace-networking` works for outbound but cannot serve inbound SSH connections, which is the entire point of this feature. The compose template ships TUN + caps **by default** so this is never a footgun — they're idle when no `TAILSCALE_AUTHKEY` is set. |
| SSH server | Tailscale SSH (`tailscale up --ssh`) | No openssh-server needed. Auth handled by Tailscale ACLs. |
| Auth mechanism | `TAILSCALE_AUTHKEY` env var | Set in `docker-compose.local.yaml` (git-ignored). Recommended: reusable + ephemeral keys so stale containers auto-expire from the tailnet. |
| Opt-in strategy | No-op when `TAILSCALE_AUTHKEY` is unset | Connect step skips silently in `post-start.sh`. Zero impact on users who don't set the key. |
| Install method | **Baked into image** at build time | Static binary tarball from `pkgs.tailscale.com/stable/`, sha256-verified. No apt-repo dance, no apt clock-skew workaround at start time. ~25MB delta. |
| Daemon lifecycle | `setsid /usr/local/sbin/tailscaled ... &` from `setup-tailscale.sh connect` | `setsid` detaches the daemon from the post-start shell so it survives the script's exit. State at `/var/lib/tailscale/tailscaled.state`. |
| State persistence | Named volume `tailscale-state` mounted at `/var/lib/tailscale` | Survives `compose down` + `compose up` cycles. Same node identity is re-used → no ephemeral-key collisions on the tailnet. Wiped only on `compose down -v`. |
| Hostname | `TAILSCALE_HOSTNAME` env var, default `<project>-devc-<server>` | Disambiguates same repo on different machines. Project name parsed from `devcontainer.json`'s `name` field, sanitized to a valid DNS label (lowercase, alphanumerics + hyphens). |
| Failure mode | **Fail loud** when `/dev/net/tun` is missing | Hard exit with actionable error pointing at the compose entries to restore. Previous design quietly fell back to userspace-networking; users would never see the warning, then wonder why SSH didn't work. |
| Idempotency | `setup-tailscale.sh connect` checks `tailscale status --self` before running `tailscale up` | Re-runs are no-ops when already authed under the same hostname. Avoids regenerating sessions on every container start. |

## Lifecycle hook placement

| Hook | Script | Tailscale action |
|------|--------|-----------------|
| `postCreateCommand` | `post-create.sh` | (no Tailscale work — image bake + state volume handle install) |
| `postStartCommand` | `post-start.sh` | `setup-tailscale.sh connect` — start daemon + connect to tailnet (idempotent) |

`postStartCommand` runs on every container start (create + restart), **before** the IDE attaches. This is critical — `postAttachCommand` runs in a transient shell tied to the IDE session, and background processes started there die when the shell exits.

## Files

| File | Role |
|------|------|
| `Containerfile` | Bakes `tailscale` (CLI) + `tailscaled` (daemon) into `/usr/local/{bin,sbin}` |
| `assets/workspace/.devcontainer/docker-compose.yml` | Ships `/dev/net/tun` + `NET_ADMIN`/`NET_RAW` + `tailscale-state` volume by default |
| `assets/workspace/.devcontainer/scripts/setup-tailscale.sh` | Single `connect` subcommand; idempotent + state-aware + fail-loud on missing TUN |
| `assets/workspace/.devcontainer/scripts/post-start.sh` | Calls `setup-tailscale.sh connect` (silent no-op when `TAILSCALE_AUTHKEY` unset) |
| `assets/workspace/.devcontainer/docker-compose.local.yaml` | Commented example showing where the user sets `TAILSCALE_AUTHKEY` |

## User setup

### 1. Configure Tailscale SSH ACLs

The tailnet's ACL policy must allow SSH access. In the [Tailscale admin console](https://login.tailscale.com/admin/acls/file):

```jsonc
"ssh": [
  {
    "action": "accept",
    "src":    ["autogroup:member"],
    "dst":    ["autogroup:self"],
    "users":  ["root", "autogroup:nonroot"]
  }
]
```

### 2. Generate a Tailscale auth key

Generate at https://login.tailscale.com/admin/settings/keys. **Reusable + Ephemeral** recommended — the container can re-register on recreate without manual key rotation, and stale ephemerals expire automatically from the tailnet.

### 3. Configure the devcontainer

Edit `.devcontainer/docker-compose.local.yaml` (git-ignored, your personal overrides):

```yaml
services:
  devcontainer:
    environment:
      - TAILSCALE_AUTHKEY=tskey-auth-XXXX
      - TAILSCALE_HOSTNAME=myproject-devc-mybox  # optional override
```

### 4. Rebuild

Rebuild (or recreate) the devcontainer. Post-start connects to the tailnet on every start — typically <2 seconds when the state volume is warm.

### 5. Connect

```bash
ssh root@<tailscale-hostname>
```

For Cursor: "Remote - SSH" → `root@<hostname>`.

## Programmatic auth key generation (devc-remote)

For unattended deploys, the `devc-remote.sh` orchestration script (separate issue) generates ephemeral auth keys via the Tailscale API using OAuth client credentials stored in macOS Keychain. See `docs/designs/devc-remote.md` (when added) for the OAuth client setup.

## What a manual recovery looks like

| Scenario | Action |
|----------|--------|
| Auth key expired between deploys | `compose exec <service> /workspace/.../scripts/setup-tailscale.sh connect` (with refreshed env) |
| `tailscaled` crashed | Same — script detects no daemon and starts one |
| Hostname changed | Update env, re-run script. Old hostname remains on tailnet until ephemeral expires. |
| Want to disconnect | `compose exec <service> tailscale logout` (manual; no `down` subcommand yet — see issue #545+ for `just tailscale-*` recipes) |
