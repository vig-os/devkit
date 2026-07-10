# Container CI Notes

Behavioral notes for the workspace CI workflow (`.github/workflows/ci.yml`)
when jobs run inside `ghcr.io/vig-os/devkit:*` via GitHub Actions
`container:`.

## Tool bootstrap model

The workflow runs with tools already provided by the devcontainer image, then
uses downstream `just` recipes to keep CI aligned with project commands:

```yaml
- run: just sync
```

## git safe.directory

`actions/checkout` runs on the host and bind-mounts the workspace into the
container. The resulting directory is owned by a different UID than the
container's root user, which triggers git's `safe.directory` rejection.
The container workflow adds:

```yaml
- run: git config --global --add safe.directory "$GITHUB_WORKSPACE"
```

## Root user

The container runs as `root` by default. No `sudo` is required and file
permission issues are unlikely, but any git operations need the
`safe.directory` fix above.

## No Docker-in-Docker

The container job does not have access to a Docker or Podman daemon.
Jobs that require building or running containers (e.g. integration tests
using `devcontainer up`) are not supported in this workflow.

## Security scope

`bandit` can still run as a `prek` lint hook (add it to
`.pre-commit-config.yaml`; the hook runner is `prek`, not the removed
`pre-commit` binary — see docs/MIGRATION.md), but there is no separate CI
security-report job with JSON artifact uploads.

## Dependency review scope

The CI workflow does not include a dedicated `actions/dependency-review-action`
job; it focuses on validating code quality and tests inside the image.

## No coverage artifact upload

The test job runs `just test` (plain `pytest`) and does not upload
coverage artifacts.

## prek cache miss

The image ships a prek hook cache at `/opt/prek-cache` (`PREK_HOME`), built
from the template workspace's `.pre-commit-config.yaml` (which uses version
tags as revs).  This repository pins hooks by commit hash, so the cached
environments do not match and prek downloads fresh environments at
runtime.

## Authenticated pulls (private / rate-limited registries)

The shipped container workflows support **authenticated** GHCR pulls, so a
**private** (or anonymous-rate-limited) `ghcr.io/vig-os/devkit` image works
without any per-repo YAML edits ([#920](https://github.com/vig-os/devcontainer/issues/920)).
Public consumers are unaffected: the automatic `GITHUB_TOKEN` performs an
authenticated pull of a public image, which succeeds unchanged.

### The `GHCR_PULL_TOKEN` secret contract

Every container job declares:

```yaml
credentials:
  username: ${{ github.actor }}
  password: ${{ secrets.GHCR_PULL_TOKEN || github.token }}
```

- **Public image (default):** leave `GHCR_PULL_TOKEN` unset. The expression
  falls back to `github.token` (the automatic `GITHUB_TOKEN`) — never an empty
  password — and an authenticated pull of a public image succeeds.
- **Private image:** set a repository/org secret `GHCR_PULL_TOKEN` to a token
  (PAT or fine-grained token) with `read:packages` / `packages: read` scope for
  the package. It overrides the fallback and authenticates the pull. This is
  also the path when the automatic `GITHUB_TOKEN` lacks cross-org package
  access.

### `packages: read` permission

Each container job (and the `resolve-image` job) grants `packages: read` — at the
workflow level where the jobs inherit the default, or in the job's own
`permissions:` block otherwise. This is what lets the `github.token` fallback
read the package; without it the automatic token cannot pull even a public image
when other permission scopes are narrowed.

### Authenticated probe in `resolve-image`

The `resolve-image` action logs in to `ghcr.io` before probing the tag when a
token is supplied (it is passed
`registry-token: ${{ secrets.GHCR_PULL_TOKEN || github.token }}` and
`registry-username: ${{ github.actor }}`), and no longer swallows the probe's
stderr. A failure is classified into an actionable `::error::` annotation that
distinguishes an **auth/denied** failure ("authentication required or denied —
set the GHCR_PULL_TOKEN secret / grant packages:read") from a **missing tag**
("the tag does not exist or is not readable"). The anonymous path is kept for
public images when no token is provided.

The broader workflow audit that this fix rides is tracked in
[#781](https://github.com/vig-os/devcontainer/issues/781) and
[#854](https://github.com/vig-os/devcontainer/issues/854).
