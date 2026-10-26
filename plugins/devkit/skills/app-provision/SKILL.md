---
name: app-provision
description: >-
  Create a GitHub App from a manifest and wire its credentials into a repository's Actions secrets with the
  `gh-app-provision` tool, so CI bots get a token that never expires and whose pushes trigger downstream
  workflows (unlike a PAT or GITHUB_TOKEN). Use when a workflow fails with "Bad credentials" from an expired PAT,
  when setting up release-please, semantic-release or changeset bots, when a tag or commit pushed by CI must
  trigger another workflow, or when asked to replace a personal access token with a GitHub App. The human only
  clicks Create and Install on GitHub; the private key is never printed.
argument-hint: "<owner/repo>"
disable-model-invocation: true
---

# devkit app-provision

Creates a GitHub App, installs it, stores `<PREFIX>_CLIENT_ID`, `<PREFIX>_ID` and `<PREFIX>_PRIVATE_KEY` as
repository secrets, and prints the workflow snippet. The background, flow and known limits are in
[`docs/GITHUB_APP_PROVISIONING.md`](../../../../docs/GITHUB_APP_PROVISIONING.md); `gh-app-provision --help` is the
source of truth for flags. If this skill and either disagree, they win and this skill is a bug.

GitHub has no API to create an App. The two browser clicks (**Create GitHub App**, **Install**) are the only human
steps. Never try to script the GitHub login with a browser driver.

## 1. Preflight

```bash
command -v gh-app-provision || echo "missing: gh-app-provision (console script of vig-utils)"
gh auth status
```

Stop if either fails. Confirm with the user: the target `OWNER/REPO`, the App owner and whether it is an org or a
user, the App name (globally unique), the permissions the bot needs (least privilege), and the secret prefix.

## 2. Preview the manifest

```bash
gh-app-provision --name <app-name> --owner <owner> --owner-type org --repo <owner>/<repo> \
  --perms contents=write,pull_requests=write --secret-prefix RP_APP --dry-run
```

`--dry-run` makes no network call, starts no server and writes nothing. Show the permissions to the user and get
their go before the real run: it creates an App under their account and writes secrets.

## 3. Choose how the user's browser reaches the tool

- Browser on the same machine: no flag (binds and advertises `127.0.0.1`).
- Browser on another machine over a VPN or LAN: `--host <ADDR>`, an IPv4 address reachable from that browser.
- Behind a TLS reverse proxy: `--base-url <URL>` with a fixed `--port`.

With the default, a remote browser cannot reach the server and the printed URL will not load. Wildcard addresses
are rejected. Never invent an address; ask the user which interface they reach this machine on.

## 4. Run it

Run the command from step 2 without `--dry-run`, plus the binding flags from step 3. It prints one URL and
blocks. Give that URL to the user and tell them to click **Create GitHub App**, then **Install** and pick the
repository. Add `--pem-out <path>` (mode 0600, must not exist) only if the key must be kept elsewhere, and
`--no-secrets` only if the caller stores the secrets itself. Do not read, print or paste the PEM.

Exit codes: `0` done, `1` provisioning failure, `2` timeout or invalid usage, `130` interrupted. On failure,
report the exit code and stop. Errors carry no upstream detail by design; do not retry in a loop, because a
partial run can leave some secrets set (see the docs page).

## 5. Verify

```bash
gh secret list --repo <owner>/<repo> | grep <PREFIX>_
```

Expect `<PREFIX>_CLIENT_ID`, `<PREFIX>_ID` and `<PREFIX>_PRIVATE_KEY`. Names only; never print values.

## 6. Wire the consuming workflow

Propose the printed `actions/create-github-app-token` step as a normal reviewed change (a PR). Pin it to a full
commit SHA with a trailing `# vX` comment, copied from `.github/workflows/`, because `check-action-pins` rejects
tag refs. Do not edit workflow files without the user's go.

## Refusals

| State | Why | What to do |
|---|---|---|
| `--host` is `0.0.0.0` or another wildcard | the tool rejects it and a public listener would expose the conversion code | pick the specific interface address |
| `--pem-out` target exists | the tool never replaces a key file | choose a new path, or ask the user to remove the old one |
| asked to print or paste the private key | the key never leaves the secrets store | refuse; offer `--pem-out` |
| asked to create the App without the user clicking | GitHub gates creation behind a human | hand the URL to the user |
