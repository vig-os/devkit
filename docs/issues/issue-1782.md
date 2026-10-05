---
type: issue
state: open
created: 2026-09-29T15:45:28Z
updated: 2026-09-29T15:45:28Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1782
comments: 0
labels: feature, area:workspace, area:workflow, semver:minor
assignees: none
milestone: none
projects: none
parent: 1773
children: none
synced: 2026-09-30T08:17:37.622Z
---

# [Issue 1782]: [[FEATURE] GitHub Action publish lane: dist freshness + floating major tags (+ Marketplace)](https://github.com/vig-os/devkit/issues/1782)

### Description

A separate channel identified in the npm review on #1773 (spike #1769): repos that **are GitHub Actions** (e.g. vig-os/commit-action) publish by committing a bundled `dist/`, keeping floating major tags (`v1`, `v1.2`), and optionally listing on the Marketplace. That is not npm.

### Problem Statement

`docs/DOWNSTREAM_RELEASE.md` documents only the dist-rebuild half as a prepare-release-extension example. Floating major tags and Marketplace listing are left to each repo.

### Proposed Solution

- Evidence: `action.yml` or `action.yaml` at the repo root.
- **Seeded:** a prepare-time `dist/` rebuild (the existing doc example turned into a template).
- **Managed:** a floating major/minor tag move after `release: published`, reusing the `DEVKIT_FLOATING_TAGS` machinery (#1626).
- Document Marketplace publishing (a manual checkbox at release time), and whether it can be automated under immutable releases.

### Alternatives Considered

Treating actions as npm packages (wrong: the "package" is the tagged repo).

### Additional Context

Needs to check how floating tags interact with immutable releases and tag rulesets.

### Impact

Action repos stop hand-maintaining their major-tag and dist-freshness logic.

### Changelog Category

Added

Refs: #1769, #1773

