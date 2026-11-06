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
| `GITHUB_TOKEN` | at the end of the job | no (GitHub's anti-recursion rule) | no |
| Fine-grained personal access token | yes, always (at most one year); CI then fails with `Bad credentials` | yes | yes |
| Classic personal access token | only if an expiry was set; it can be created without one, but is then a standing credential tied to a person | yes | yes |
| GitHub App installation token | after about 1 hour; `actions/create-github-app-token` mints a fresh one on every run | yes | no |

What persists for an App is its private key, stored as an Actions secret. The key does not expire on its own,
but you can rotate or revoke it in the App's settings.

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
   The callback is claimed before processing starts. Later requests, including
   concurrent requests and browser reloads, receive HTTP `200`. After a rejected
   or failed callback the page says "This provisioning run has ended"; otherwise
   it says "Callback already accepted". They never repeat the exchange or change
   the first callback's result or error.
4. The success page links to the install page. Click **Install** and select the
   repository. GitHub then redirects your browser to the manifest's `setup_url`,
   which points at the tool's local `/installed` endpoint; the tool detects that
   request.
5. The tool prints the `actions/create-github-app-token` snippet and exits. The
   server closes on success, failure, timeout or interruption.

   **Exit `0` does not mean the Install click happened.** After creation the tool
   waits up to `min(timeout, 300)` seconds for the install redirect. If it never
   arrives, the tool prints `install: not yet confirmed — finish it at the URL
   above.`, still prints the snippet and still exits `0`. The App exists and the
   secrets are already stored, so do not rerun the tool: open the printed
   `.../installations/new` URL and install the App on the repository yourself.
   Without an installation the token step in the workflow fails.

`--timeout` (default 900 s) bounds the wait for creation; installation then gets
up to `min(timeout, 300)` seconds. Requires an authenticated `gh` on `PATH`.
Exit codes: `0` App created and secrets stored (or a `--dry-run` preview; see
the Install caveat above), `1` provisioning/startup failure, `2` timeout or
invalid usage, `130` interrupted.

## Run without installing vig-utils

The flake app exposes the same console script and accepts the same flags:

```bash
nix run .#app-provision -- --dry-run \
  --name my-release-bot --owner my-org --repo my-org/my-repo
```

Outside a checkout, use `nix run github:vig-os/devkit#app-provision -- ...`.
An authenticated `gh` must still be on `PATH` for a real provisioning run.

## Organization secrets for selected repositories

Add `--org-secret --repos my-repo,other-repo` to store all three credentials as
organization Actions secrets under `--owner`, visible only to those repositories:

```bash
gh-app-provision --name my-release-bot --owner my-org --owner-type org \
  --repo my-org/my-repo --org-secret --repos my-repo,other-repo
```

`--org-secret` requires `--owner-type org` and a non-empty repository list, and
is mutually exclusive with `--no-secrets`. `--repos` requires `--org-secret`;
whitespace around repository names is stripped and empty entries are rejected.
Invalid combinations exit `2` before
starting the server. `--repo` remains required for the manifest's project URL;
`--repos` controls secret visibility, not App installation or permissions.
Install the App on every repository that needs an installation token.
The authenticated `gh` account needs permission to manage organization Actions
secrets; organization plan and policy restrictions still apply. Verify names
with `gh secret list --org my-org`. Writes use
`gh secret set NAME --org my-org --visibility selected --repos my-repo,other-repo`,
with values passed only on stdin. The recovery-key and partial-write behavior
below also applies to organization secrets.

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
`--host` (`0.0.0.0`) is rejected. `--host` and `--base-url` are mutually
exclusive, even if `--host` explicitly selects loopback. `--base-url` requires
an `http` or `https` scheme and a host; invalid options exit with code `2`.

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

## Use the minted token with Nix

For private GitHub flake inputs, give the App read access to their contents and
install it on the input repositories. Mint a token scoped to those repositories,
mask it before exporting, and append the Nix setting to the existing `NIX_CONFIG`
so runner cache, feature and other settings survive. Run this after any toolchain
setup that exports `NIX_CONFIG`, before the Nix command that fetches private inputs:

```yaml
      - uses: actions/create-github-app-token@bcd2ba49218906704ab6c1aa796996da409d3eb1  # v3
        id: app-token
        with:
          client-id: ${{ secrets.RP_APP_CLIENT_ID }}
          private-key: ${{ secrets.RP_APP_PRIVATE_KEY }}
          owner: my-org
          repositories: my-repo,other-repo
      - name: Configure Nix GitHub access
        shell: bash
        env:
          APP_TOKEN: ${{ steps.app-token.outputs.token }}
        run: |
          set -euo pipefail
          echo "::add-mask::$APP_TOKEN"
          delimiter="NIX_CONFIG_$(openssl rand -hex 16)"
          {
            printf 'NIX_CONFIG<<%s\n' "$delimiter"
            printf '%s\n' "${NIX_CONFIG:-}"
            printf 'access-tokens = github.com=%s\n' "$APP_TOKEN"
            printf '%s\n' "$delimiter"
          } >> "$GITHUB_ENV"
      - run: nix flake metadata
```

The appended `access-tokens` setting takes precedence over any earlier setting
of that name; include any required non-GitHub host tokens in the appended value.
Never print `NIX_CONFIG` or enable shell tracing around credentials. The token
expires, so mint it within each job rather than persisting it as a long-lived
secret. The existing credential slots work with either secret storage mode.

## Known limits

- The conversion `code` is single-use and expires about an hour after creation.
- Error messages omit upstream details on purpose, because they can contain
  secrets; rerun with `--dry-run` or check the App's settings page to diagnose.
