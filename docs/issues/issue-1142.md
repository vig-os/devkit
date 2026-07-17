---
type: issue
state: closed
created: 2026-07-15T20:10:37Z
updated: 2026-07-16T11:50:49Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1142
comments: 1
labels: bug, priority:medium, area:workspace, effort:small, semver:patch
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-07-17T05:20:04.484Z
---

# [Issue 1142]: [[BUG] Scaffold codeql.yml push paths hardcoded to '**.py' — not rendered per language, consumer hand-fixes lost on upgrade](https://github.com/vig-os/devkit/issues/1142)

### Description

`assets/workspace/.github/workflows/codeql.yml` hardcodes the `push` trigger path filter:

```yaml
push:
  branches:
    - main
  paths:
    - '**.py'
    - '.github/workflows/**'
```

`render_codeql_matrix()` (`assets/init-workspace.sh`, added in #1025) rewrites the `language:` matrix to match the detected repo language(s), but leaves the push `paths:` filter untouched. On a Node consumer the push-to-main CodeQL scan therefore never triggers for TS/JS changes — only the PR trigger (unfiltered) catches them.

Worse, `codeql.yml` is a managed file (`scripts/manifest.toml`), so consumer hand-fixes are silently reverted on every devkit upgrade: commit-action patched the paths to `**.ts` (vig-os/commit-action#67) and the next scaffold sync overwrote it. Re-verified still hardcoded on `release/1.3.0`.

### Acceptance Criteria

- [ ] `render_codeql_matrix()` (or a sibling renderer) also rewrites the push `paths:` filter per detected language (python → `**.py`; node → `**.ts`, `**.js`, `**.mjs`, `**.cjs`; always keep `.github/workflows/**`)
- [ ] Marker-less repos keep a sane default (workflows-only filter or no paths filter)
- [ ] Regression test: node-marker workspace renders TS/JS paths, python-marker renders `**.py`
- [ ] Upgrading commit-action no longer reverts its paths fix

### Additional Context

Found during sync-issues-action deploy recon (2026-07-15). Affects every JS-action consumer: commit-action today, sync-issues-action next. Until fixed, deploys must re-patch `codeql.yml` by hand after every scaffold sync.
---

# [Comment #1]() by [c-vigo]()

_Posted on July 16, 2026 at 11:50 AM_

Fixed on `dev` via #1147 (merge commit 0bb3afb6). `render_codeql_matrix()` now renders the push `paths:` filter per detected language (python → `**.py`; node → `**.ts`/`**.js`/`**.mjs`/`**.cjs`; rust/marker-less → workflows-only). Ships with the next devkit release.

