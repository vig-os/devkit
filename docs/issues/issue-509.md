---
type: issue
state: open
created: 2026-04-08T15:20:56Z
updated: 2026-04-08T15:20:56Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devcontainer/issues/509
comments: 0
labels: chore, area:ci
assignees: none
milestone: none
projects: none
parent: none
children: 506
synced: 2026-04-09T04:39:38.376Z
---

# [Issue 509]: [[CHORE] Switch from Dependabot to Renovate for dependency management](https://github.com/vig-os/devcontainer/issues/509)

### Chore Type

CI / Build change

### Description

Switch from Dependabot to Renovate for dependency version updates.

**Motivation:** Dependabot's `github-actions` ecosystem only supports scanning workflow files at the repository root (`directory: "/"`). This means template workflow files under `assets/workspace/.github/workflows/` (12 workflows + 1 composite action) and `assets/smoke-test/.github/workflows/` (1 workflow) — totalling ~50+ SHA-pinned action references across 7 distinct actions — are not tracked and must be updated manually.

Renovate supports custom file matching via `fileMatch` / `managerFilePatterns`, allowing it to scan any directory for action references. It also offers more flexible grouping, automerge policies, and better monorepo support.

### Acceptance Criteria

- [ ] Renovate configured for all ecosystems currently tracked by Dependabot (`github-actions`, `pip`, `npm`, `docker`)
- [ ] Renovate configured to also track GitHub Actions in `assets/workspace/.github/` and `assets/smoke-test/.github/`
- [ ] Dependabot configuration removed (`.github/dependabot.yml` from root and from `assets/workspace/`)
- [ ] Existing open Dependabot PRs closed or superseded

### Implementation Notes

Target files:
- Add: `renovate.json` (root)
- Remove: `.github/dependabot.yml`, `assets/workspace/.github/dependabot.yml`

Downstream template action SHAs currently not tracked:
- `actions/checkout`, `actions/create-github-app-token`, `actions/cache`
- `github/codeql-action`, `ossf/scorecard-action`
- `vig-os/commit-action`, `vig-os/sync-issues-action`

### Related Issues

Parent of #506 (automatic changelog edits in dependency PRs — will need to target Renovate instead of Dependabot)

### Priority

Medium

### Changelog Category

Changed

### Additional Context

_No response_
