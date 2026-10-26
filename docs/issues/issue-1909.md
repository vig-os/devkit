---
type: issue
state: open
created: 2026-10-25T10:28:49Z
updated: 2026-10-25T10:28:49Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1909
comments: 0
labels: none
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-10-26T07:40:28.514Z
---

# [Issue 1909]: [Ship gh-app-provision (GitHub App from manifest -> secrets) as a devkit tool + agent skill](https://github.com/vig-os/devkit/issues/1909)

**Problem:** creating a GitHub App for CI (a read-only cross-repo token, a release bot, ...) is a recurring manual chore, and people fall back to personal access tokens that expire or are over-scoped. A working tool for it exists, but only in one person's private agent config, so other devkit users and their agents can't use it.

**What the tool does** (stdlib Python plus an authenticated `gh`):
- builds an App manifest from flags (`--name --owner --owner-type --perms --secret-prefix --repo`);
- serves a one-shot, auto-submitting form on an ephemeral port and a random path, with `--host` to bind to a specific (e.g. VPN) address;
- the manifest `redirect_url` captures the code, exchanges it for client id, App id and private key, and pipes the PEM straight into `gh secret set` (never printed or written to disk);
- `setup_url` detects the Install click, and the server tears down on completion or timeout;
- prints the `actions/create-github-app-token` snippet for the consuming workflow.

The only human steps are GitHub's own Create and Install clicks.

**Proposal**
1. Add it to devkit as a CLI (`devkit app-provision` or a flake app) with tests: manifest rendering, a callback handler with a mocked exchange, and an assertion that no secret appears in output or logs.
2. Ship the matching agent skill in devkit's agent assets, so any devkit project's agent can run it.
3. Extensions:
   - write the secrets as **org** secrets with selected-repo visibility (`--org-secret --repos a,b`), not only repo secrets;
   - a documented recipe for Nix: `NIX_CONFIG` `access-tokens = github.com=<token>`, appended rather than replacing (#1907).

**Acceptance:** `devkit app-provision --dry-run` prints the manifest; one real provisioning end to end; docs page.

Related: #1754 (mentions it), #1907, #1908.
