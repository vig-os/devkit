# GitHub App provisioning (`gh-app-provision`)

How to replace an expiring personal access token (PAT) in CI with a GitHub App,
using the `gh-app-provision` console script shipped in `vig-utils`. The tool's
`--help` and module docstring
([`gh_app_provision.py`](../packages/vig-utils/src/vig_utils/gh_app_provision.py))
are the source of truth for flags and behaviour; this page explains when and how
to use it and does not restate every option. The agent-facing counterpart is the
`/devkit:app-provision` skill ([`plugins/devkit/skills/app-provision/SKILL.md`](../plugins/devkit/skills/app-provision/SKILL.md)).

For how devkit's own managed workflows use Apps and where their credentials live,
see [`WORKFLOW_SECURITY.md`](WORKFLOW_SECURITY.md#where-the-credentials-live-devkit_commit_app_environment).

## When to use a GitHub App instead of a PAT

| Credential | Expires | Pushes trigger downstream workflows | Tied to a person |
|---|---|---|---|
| `GITHUB_TOKEN` | per job | no (GitHub's anti-recursion rule) | no |
| Personal access token | yes (at most one year), then CI fails with `Bad credentials` | yes | yes |
| GitHub App installation token | no: minted per job from a long-lived key | yes | no |

Use an App when a workflow must push a tag or commit that triggers another
workflow (release-please, semantic-release, changeset bots), when a PAT has
expired, or when CI should not depend on one person's account.

## What is automated, and what is not

GitHub has no API to create an App; creation is gated behind a browser action by
design. The tool automates everything around it. The only human steps are
**Create GitHub App** and **Install** on GitHub's pages. Do not script the login
with a browser driver.

## End-to-end flow

1. Run the tool with the App name, owner, target repo and permissions:

   ```bash
   gh-app-provision \
       --name my-release-bot --owner my-org --owner-type org \
       --repo my-org/my-repo --perms contents=write,pull_requests=write \
       --secret-prefix RP_APP
   ```

   `--dry-run` prints the manifest without network, server or `gh` calls. It is
   a good first run to check the permissions.
2. The tool prints one URL. Open it in a browser; it lands on GitHub's pre-filled
   *Create GitHub App* page. Click **Create GitHub App**.
3. GitHub redirects the single-use `code` to the tool's local `/callback`. The
   tool exchanges it through `gh` and stores `<PREFIX>_CLIENT_ID`,
   `<PREFIX>_ID` and `<PREFIX>_PRIVATE_KEY` as repository Actions secrets. The
   PEM is piped into `gh secret set` and is never printed or logged.
4. The success page links to the install page. Click **Install** and select the
   repository. GitHub calls the tool's `/installed` endpoint, which the tool
   detects.
5. The tool prints the `actions/create-github-app-token` snippet and exits. The
   server closes on success, failure, timeout or interruption.

`--timeout` (default 900 s) bounds the wait for creation; installation then gets
up to `min(timeout, 300)` seconds. Requires an authenticated `gh` on `PATH`.
Exit codes: `0` success or preview, `1` provisioning/startup failure, `2` timeout
or invalid usage, `130` interrupted.

## Binding modes

The tool never listens on a wildcard address and never guesses an address.

| Mode | Flags | Binds | Advertised URL | Use when |
|---|---|---|---|---|
| Local (default) | none | `127.0.0.1` | `http://127.0.0.1:<port>/…` | the browser runs on the same machine |
| Explicit address | `--host ADDR` | exactly `ADDR` (IPv4) | exactly `ADDR` | the browser is on another machine over a VPN or LAN |
| Reverse proxy | `--base-url URL` (with a fixed `--port`) | `127.0.0.1` | `URL` | a proxy with TLS fronts the tool |

**Failure mode:** with the default, a browser on another machine cannot reach the
server; the URL the tool prints simply does not load. Choose `--host` with an
address that is reachable from the browser, or `--base-url`. A wildcard
`--host` (`0.0.0.0`) is rejected.

Behind a reverse proxy, configure it to forward to the fixed `--port`, strip any
path prefix from the base URL, and omit query strings from its access logs: the
query string carries the single-use conversion code.

## Where the private key goes

By default the key goes only into the repository secrets. Two flags cover a caller
that stores the key elsewhere:

- `--pem-out PATH` also writes the key to `PATH` (mode `0600`, created exclusively;
  an existing file is never replaced). It is written before the secrets, so a
  failed secret write leaves a recoverable key.
- `--no-secrets` skips the repository secret writes (the exchange with GitHub
  still runs). Without `--pem-out` the returned key is discarded.

Secret writes are sequential, so a failure can leave some secrets set. Without
`--pem-out`, a failed exchange or storage may require regenerating the key in the
App's GitHub settings.

## Consuming the App in a workflow

Add the snippet to the consuming workflow as a normal reviewed change; the tool
never edits workflow files. Pin the action to a full commit SHA with a trailing
version comment, as devkit's own workflows do (`check-action-pins` enforces it).
The tool prints the action by tag; replace it with the pinned form:

```yaml
      - uses: actions/create-github-app-token@bcd2ba49218906704ab6c1aa796996da409d3eb1  # v3
        id: app-token
        with:
          client-id: ${{ secrets.RP_APP_CLIENT_ID }}
          private-key: ${{ secrets.RP_APP_PRIVATE_KEY }}
      # then:  token: ${{ steps.app-token.outputs.token }}
```

Use the SHA currently in `.github/workflows/` rather than the one above if it has
moved; Renovate keeps the pins fresh.

## Known limits

- The conversion `code` is single-use and expires about an hour after creation.
- The secrets are repository secrets. Organization secrets with selected-repository
  visibility, a Nix `access-tokens` recipe and a flake app are tracked in
  [#1915](https://github.com/vig-os/devkit/issues/1915).
- The callback is not yet strictly single-use, the failure paths lack dedicated
  tests, and `--base-url` is not yet validated. Tracked in
  [#1919](https://github.com/vig-os/devkit/issues/1919).
- Error messages omit upstream details on purpose, because they can contain
  secrets; rerun with `--dry-run` or check the App's settings page to diagnose.
