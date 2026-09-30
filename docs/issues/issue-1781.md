---
type: issue
state: open
created: 2026-09-29T15:45:24Z
updated: 2026-09-29T15:53:58Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1781
comments: 1
labels: feature, area:workspace, area:workflow, semver:minor
assignees: none
milestone: none
projects: none
parent: 1773
children: none
synced: 2026-09-30T08:17:38.456Z
---

# [Issue 1781]: [[FEATURE] npm publish lane: Trusted Publishing + provenance + next/latest dist-tags](https://github.com/vig-os/devkit/issues/1781)

### Description

Implementation of the npm channel for the publish-lane spike #1769 (review on #1773). This is the `npm` job in the managed `publish-release.yml`. devkit has no npm support today.

### Problem Statement

npm permanently revoked classic tokens on 2025-12-09. Granular tokens are capped at 90 days, and bypass-2FA tokens lose publish rights around Jan 2027. Any repo still hand-publishing with `NPM_TOKEN` is on a deadline.

### Proposed Solution

- **Managed:** the `npm` job composite.
  - Trusted Publishing (npm CLI >= 11.5.2, Node >= 22.14) with automatic provenance.
  - `npm view` idempotency precheck.
  - Release candidates go to `--tag next` (derived from the SemVer suffix) and finals to `latest`; a prerelease never takes `latest`.
  - `npm audit signatures` verification afterwards.
  - Always publishes with the npm CLI, whatever the build tool (pnpm, yarn or bun).
- **Seeded:** a `just dist-npm` recipe and `.npmrc`.
- **Evidence:** a `package.json` without `"private": true`. Workspaces need **one registration per child package**.
- **Docs:** the **first publish must be manual** (Trusted Publishing needs the package to already exist); then register `publish-release.yml` and the `npm` environment. Also cover the post-2026-09-03 requirement to allow at least one action, and malware-scan wait times.

### Alternatives Considered

Seeding an `NPM_TOKEN` path (rejected); JSR as a default (optional later seed only).

### Additional Context

The GitHub Action / Marketplace lane (committed `dist/` + moving major tags) is a **separate channel**, filed separately.

### Impact

JS/TS repos get token-free npm publishing with provenance.

### Changelog Category

Added

Refs: #1769, #1773

---

# [Comment #1]() by [gerchowl]()

_Posted on September 29, 2026 at 03:53 PM_

**Revised after the ADR review on PR #1785** (`docs/rfcs/ADR-publish-lanes.md`):
- **v1 is finals only.** Release candidates on `--tag next` move to #1787.
- Register the trusted publisher against `publish-release.yml` + environment **`publish-npm`**.

