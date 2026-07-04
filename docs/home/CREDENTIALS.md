# Credential hygiene

Persistent remote sessions (tmux surviving SSH disconnects, long agent runs)
require **resident** per-user credentials on servers — SSH agent forwarding
dies with the connection and is hijackable on shared hosts. Residency is
safe only with **scoped, revocable** credentials.

## The interface

One file per secret, named like the target environment variable:

```
~/.config/vigos/secrets/<NAME>     # mode 0600, NAME =~ [A-Z_][A-Z0-9_]*
```

Opt in via `vigos.shell.secretsEnv.enable = true;` — each file is exported
as an env var at shell startup (profile + rc, idempotent; trailing newline
stripped). How the files get there is up to the machine: sops-nix on org
servers, hand-placed on laptops. Interactive logins (`gh auth login`,
`claude` `/login`) keep working if you never adopt this.

## What goes where

| Credential | Form | Notes |
|---|---|---|
| GitHub API / gh | **Fine-grained PAT**, scoped repos, expiring | `GH_TOKEN`; never a classic token |
| Claude Code | `claude setup-token` output | `CLAUDE_CODE_OAUTH_TOKEN`; revocable from the console |
| Cachix | — | Not a per-user credential: pulls are anonymous, pushes are CI's job |
| SSH keys (auth **and** signing) | **Minted per user × host, never copied** | Register each with GitHub individually — a signature then identifies the machine it was made on; a compromise revokes one host, not your identity |

Git signing activates only when you set `vigos.git.signingKeyPath` — mint
the key first:

```bash
ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519_signing -C "$(whoami)@$(hostname)"
# add the .pub on GitHub as a SIGNING key, then:
#   vigos.git.signingKeyPath = "~/.ssh/id_ed25519_signing.pub";
```

## Rotation / offboarding

Expiry does the rotating for PATs — renew on the provider, replace the file.
Offboarding = revoke at the provider (GitHub token/keys pages, Anthropic
console); resident copies become dead bytes. Audit what a host holds with
`ls -l ~/.config/vigos/secrets/`.

## Honest threat model

Anything readable by your uid is readable by every process running as your
uid — **including an agent**. Files vs env vars vs encryption-at-rest do not
change this. The mitigations are credential scoping (above) and the working
agreement that autonomous agent runs happen inside the container.
