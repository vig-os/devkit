---
type: issue
state: open
created: 2026-04-08T10:38:40Z
updated: 2026-04-08T10:38:40Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devcontainer/issues/506
comments: 0
labels: feature, area:ci
assignees: none
milestone: none
projects: none
parent: 509
children: none
synced: 2026-04-09T04:39:38.868Z
---

# [Issue 506]: [[FEATURE] Automatic changelog edits in Dependabot PRs](https://github.com/vig-os/devcontainer/issues/506)

### Description

Add a GitHub Actions workflow that automatically inserts a CHANGELOG.md entry when Dependabot opens a pull request. Today these entries are added manually during release preparation; automating them keeps `## Unreleased` up to date throughout the development cycle and satisfies the changelog rule ("always update for dependency version bumps").

### Problem Statement

Dependabot PRs are merged without a CHANGELOG entry. The entries are batched manually at release time (e.g., "Dependabot dependency update batch" in 0.3.2). This means `## Unreleased` does not reflect dependency updates during the dev cycle, and the manual step is easy to forget.

### Proposed Solution

**Preferred: Option A -- per-PR workflow via `pull_request_target`**

A new workflow triggers on `pull_request_target` (opened, synchronize) filtered to `dependabot[bot]`:

1. `dependabot/fetch-metadata@v3` extracts package name, old/new version, ecosystem, and update type.
2. A script inserts an entry under `## Unreleased` / `### Changed` in CHANGELOG.md (idempotent -- skips if an entry for this PR already exists).
3. `vig-os/commit-action` commits the change to the PR branch with a `[dependabot skip]` prefix so Dependabot can continue rebasing.

Entry format (matching existing style):

```markdown
### Changed

- **Bump `<package>` from `<old>` to `<new>`** ([#<PR>](https://github.com/vig-os/devcontainer/pull/<PR>))
```

Pros:
- CHANGELOG visible in the PR diff for review
- Each PR is self-contained with its own changelog entry
- Uses existing infrastructure (`commit-action`, `fetch-metadata`)

Cons:
- Merge conflict risk when multiple Dependabot PRs are open (mitigated by grouped PRs, auto-rebase, and appending to end of section)
- Extra commit per PR
- `pull_request_target` security considerations (mitigated: no PR code execution, only metadata)

### Alternatives Considered

**Option B -- post-merge batch on `dev` push**

A workflow triggers on `push` to `dev`, detects Dependabot merge commits, parses the commit message for package/version info, and inserts a CHANGELOG entry after the fact.

Pros:
- No merge conflict risk (sequential writes after each merge)
- No `pull_request_target` or `[dependabot skip]` needed
- Simpler implementation

Cons:
- CHANGELOG entry not visible in the Dependabot PR itself
- Parsing commit messages is less reliable than `fetch-metadata` structured output
- Extra commit to `dev` after every Dependabot merge

**Option C -- batch at release time (automate current practice)**

A step inside `prepare-release.yml` queries merged Dependabot PRs since the last release tag and inserts a single batched entry into the changelog before freeze.

Pros:
- Zero merge conflict risk
- Matches current manual practice (batched entries like in 0.3.2)
- No extra commits during the dev cycle

Cons:
- `## Unreleased` does not reflect dependency updates until release preparation
- Requires changes to `prepare-release.yml`
- Less immediate traceability

### Additional Context

- Dependabot targets `dev` across four ecosystems: `github-actions`, `pip`, `npm`, `docker` (see `.github/dependabot.yml`).
- Dependabot commit prefixes are already configured (`ci` for actions, `build` for pip/npm/docker).
- The project uses `vig-os/commit-action` for API-based commits in other workflows (sync-issues, prepare-release, release).
- The `[dependabot skip]` commit prefix allows Dependabot to rebase without creating merge commits.
- Since Dec 2025, `pull_request_target` always uses the workflow file from the default branch.

### Impact

- All Dependabot PRs across all ecosystems benefit.
- No breaking change; backward compatible.
- The workflow template in `assets/workspace/` should also receive this workflow for downstream repos.

### Changelog Category

Added

### Acceptance Criteria

- [ ] TDD compliance (see `.cursor/rules/tdd.mdc`)
