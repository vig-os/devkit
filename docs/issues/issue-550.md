---
type: issue
state: closed
created: 2026-06-08T09:25:06Z
updated: 2026-06-08T11:43:29Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devcontainer/issues/550
comments: 1
labels: bug, area:ci, security
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-06-09T06:16:01.415Z
---

# [Issue 550]: [Renovate PRs blocked by expired CI gates and stale base image](https://github.com/vig-os/devcontainer/issues/550)

## Summary

All 16 open Renovate PRs (#528, #530–#544) fail CI for shared infrastructure reasons, not because of the dependency bumps themselves. Five time-triggered problems went red as expiration dates passed (2026-06-08):

1. **Security Scan** — `.trivyignore` entries with `Expiration:` dates of `2026-05-15` / `2026-06-01` are now expired, so Trivy re-surfaces fixable HIGH/CRITICAL findings. Same root cause as #549.
2. **Dependency Review** — `.github/dependency-review-allow.txt` entry `GHSA-wvrr-2x4r-394v` expired `2026-06-01`.
3. **changelog** — `renovate-changelog.yml` runs `set -euo pipefail` under `sh`/dash inside the container (`Illegal option -o pipefail`).
4. **Project Checks** — `taplo-lint` pre-commit hook uses `--default-schema-catalogs`, which now fails to parse the remote catalog.
5. **renovate/artifacts** — Mend-side lockfile update failures; resolved by rebasing PRs once `dev` is green.

## Affected PRs

#528, #530, #531, #532, #533, #534, #535, #536, #537, #538, #539, #540, #541, #542, #543, #544

## Plan

### Phase 1 (this issue)
- Fix changelog pipefail (`shell: bash`)
- Fix taplo-lint catalog (`--no-default-schema-catalogs`)
- Renew dependency-review allow-list

### Phase 2 (#549)
- Rebase base image to newest `python:3.12-slim-bookworm` digest
- Re-evaluate `.trivyignore` from scratch
- Add targeted apt `--only-upgrade` pins for remaining fixable CVEs

### Phase 3
- Rebase and merge all 16 Renovate PRs in dependency order

## Related

- Security sub-part: #549 (nightly scan gate failure on `:latest`)
- Tracking: #512 (upstream CVEs with no Debian fix)
---

# [Comment #1]() by [c-vigo]()

_Posted on June 8, 2026 at 11:43 AM_

Resolved by #552.

