---
type: issue
state: closed
created: 2026-03-26T10:55:09Z
updated: 2026-03-26T12:06:51Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devcontainer/issues/449
comments: 0
labels: chore, area:ci
assignees: c-vigo
milestone: none
projects: none
parent: none
children: none
synced: 2026-03-26T17:53:31.228Z
---

# [Issue 449]: [[CHORE] Fix release PR body Markdown heading hierarchy](https://github.com/vig-os/devcontainer/issues/449)

**Chore Type:** CI / Build change

**Description**

Release PR bodies (e.g. PR 342) use the wrong heading levels: the main title is `## Release X.Y.Z`, the changelog section from `CHANGELOG.md` starts with `## [X.Y.Z] - TBD`, and a redundant `### Release Content` wrapper sits between the intro and the changelog. That makes the changelog subsection effectively demoted under "Release Content" instead of reading as the top-level release notes under the PR title.

**Desired structure**

- **Prepare (draft PR):** `# Release X.Y.Z`, one-line intro, then the extracted changelog block unchanged so it still begins with `## [X.Y.Z] - TBD`.
- **Finalize (`release.yml` refresh):** Keep the existing main H1 as-is (`# [Release X.Y.Z](…) - <date>`). Only the changelog slice should be updated (date/link in the `## [X.Y.Z]` line per current behavior). Remove the `### Release Content` wrapper there as well.

**Acceptance criteria**

- [ ] `prepare-release.yml` — draft PR body uses `# Release $VERSION`, no `### Release Content`, changelog content still starts at `## [$VERSION]`.
- [ ] `release.yml` — refreshed PR body matches the same hierarchy (H1 unchanged from current linked title + date; no `### Release Content`).
- [ ] Synced copy under `assets/workspace/.github/workflows/prepare-release.yml` updated if it mirrors this workflow.
- [ ] BATS or other tests updated if they assert the old strings.
- [ ] `docs/RELEASE_CYCLE.md` (or other canonical release docs) updated only if they describe the old PR body shape.

**Implementation notes**

- Current templates: `PR_BODY` in `.github/workflows/prepare-release.yml` (~298–304); `cat > /tmp/release-pr-body.md` in `.github/workflows/release.yml` (~729–737).

**Related issues**

- Related: #300, PR #319 / #342 (release PR body refresh behavior).

**Priority**

Low

**Changelog category**

No changelog needed

**Additional context**

GitHub PR bodies render Markdown; correct hierarchy improves readability and matches Keep a Changelog–style `## [version]` sections.

