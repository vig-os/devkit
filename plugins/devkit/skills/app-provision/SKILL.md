---
name: app-provision
description: >-
  Create a GitHub App from a manifest and wire its credentials into repository or organization Actions secrets with the
  `gh-app-provision` tool, so CI bots mint a fresh short-lived installation token on every run from a private key
  that does not expire, and pushes made with it trigger downstream workflows (unlike GITHUB_TOKEN). Use when
  a workflow fails with "Bad credentials" from an expired PAT,
  when setting up release-please, semantic-release or changeset bots, when a tag or commit pushed by CI must
  trigger another workflow, or when asked to replace a personal access token with a GitHub App. The human only
  clicks Create and Install on GitHub; the private key is never printed.
argument-hint: "<owner/repo>"
disable-model-invocation: true
---

# devkit app-provision

Creates a GitHub App, installs it, stores `<PREFIX>_CLIENT_ID`, `<PREFIX>_ID` and `<PREFIX>_PRIVATE_KEY` as
repository secrets by default (or organization secrets with selected-repo visibility), and prints the workflow snippet. The background, flow and known limits are in
[`docs/GITHUB_APP_PROVISIONING.md`](../../../../docs/GITHUB_APP_PROVISIONING.md); the tool's `--help` output is the
source of truth for flags. If this skill and either disagree, they win and this skill is a bug.

GitHub has no API to create an App. The two browser clicks (**Create GitHub App**, **Install**) are the only human
steps. Never try to script the GitHub login with a browser driver.

## 1. State lookup

Run `/devkit:status` and read the repository scope and the required GitHub App secrets it reports, so you do not
create a second App next to a working one. Then check the tool and the `gh` login:

```bash
command -v gh-app-provision || command -v nix
gh auth status
```

If the console script is missing, use `nix run .#app-provision --` in a devkit checkout,
or `nix run github:vig-os/devkit#app-provision --` elsewhere, followed by the same flags.
Stop if neither runner is available or `gh` authentication fails. Confirm with the user: the target `OWNER/REPO`, the App owner and whether it is an org or a
user, the App name (globally unique), the permissions the bot needs (least privilege), the secret prefix, and repository or organization secret storage.

Before provisioning, check the chosen prefix as well: `/devkit:status` only reports the standard App prefixes.
Substitute the confirmed repository and prefix:

```bash
gh secret list -R <repo> | grep '^<PREFIX>_'
```

If any matching secrets exist, inspect the existing App setup before creating another App. If listing secrets
fails, stop and resolve repository access first. No matches means the chosen prefix has no stored secrets.
For organization storage, use `gh secret list --org <owner>` for this check instead.

## 2. Refuse

| State | Why | What to do |
|---|---|---|
| `--host` is `0.0.0.0` or another wildcard | the tool rejects it and a public listener would expose the conversion code | pick the specific interface address |
| `--pem-out` target exists | the tool never replaces a key file | choose a new path, or ask the user to remove the old one |
| asked to print or paste the private key | the key never leaves the secrets store | refuse; offer `--pem-out` |
| asked to create the App without the user clicking | GitHub gates creation behind a human | hand the URL to the user |

## 3. Preview the manifest

```bash
gh-app-provision --name <app-name> --owner <owner> --owner-type org --repo <owner>/<repo> \
  --perms contents=write,pull_requests=write --secret-prefix RP_APP --dry-run
```

For organization secrets, add `--org-secret --repos <repo>,<other-repo>` with repository names.
This requires `--owner-type org` and a non-empty list, and excludes `--no-secrets`.
The list controls secret visibility; install the App on each repository separately.
`--repo` is still required for the manifest URL. Confirm organization secret-management access.

`--dry-run` makes no network call, starts no server and writes nothing. Show the permissions to the user and get
their go before the real run: it creates an App under their account and writes secrets.

## 4. Choose how the user's browser reaches the tool

- Browser on the same machine: no flag (binds and advertises `127.0.0.1`).
- Browser on another machine over a VPN or LAN: `--host <ADDR>`, an IPv4 address reachable from that browser.
- Behind a TLS reverse proxy: `--base-url <URL>` with a fixed `--port`; URL must have an HTTP(S) scheme and host.

`--host` and `--base-url` are mutually exclusive.

With the default, a remote browser cannot reach the server and the printed URL will not load. Wildcard addresses
are rejected. Never invent an address; ask the user which interface they reach this machine on.

## 5. Run it

Run the command from step 3 without `--dry-run`, plus the binding flags from step 4. It prints one URL and
blocks. Give that URL to the user and tell them to click **Create GitHub App**, then **Install** and pick the
repository. Add `--pem-out <path>` (mode 0600, must not exist) only if the key must be kept elsewhere, and
`--no-secrets` only if the caller stores the secrets itself. Do not read, print or paste the PEM.

Exit codes: `0` the App was created and its secrets stored, `1` provisioning failure, `2` timeout or invalid usage,
`130` interrupted. **`0` does not prove the Install click happened:** the tool waits up to `min(timeout, 300)`
seconds, then prints `install: not yet confirmed` and still exits `0`. Read that line. If it says not confirmed,
have the user open the printed install URL and install the App on the repository; the secrets are already set, so
do not rerun the tool. On failure, report the exit code and stop. Errors carry no upstream detail by design; do not retry in a loop, because a
partial run can leave some secrets set (see the docs page). A later callback after a rejected or failed
first callback shows "This provisioning run has ended"; it does not restart provisioning.

## 6. Verify

```bash
gh secret list -R <repo> | grep '^<PREFIX>_'
```

For organization storage, use `gh secret list --org <owner>` instead.

Expect `<PREFIX>_CLIENT_ID`, `<PREFIX>_ID` and `<PREFIX>_PRIVATE_KEY`. Names only; never print values.

## 7. Wire the consuming workflow

Propose the printed `actions/create-github-app-token` step as a normal reviewed change (a PR). Pin it to a full
commit SHA with a trailing `# vX` comment, copied from `.github/workflows/`, because `check-action-pins` rejects
tag refs. Do not edit workflow files without the user's go.

For private Nix inputs, follow the [Nix token recipe](../../../../docs/GITHUB_APP_PROVISIONING.md#use-the-minted-token-with-nix):
mask the minted token and append `access-tokens = github.com=<token>` to the existing `NIX_CONFIG`
after toolchain setup. Keep credentials out of logs and pin the action to a full SHA.
