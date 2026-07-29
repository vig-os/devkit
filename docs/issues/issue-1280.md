---
type: issue
state: open
created: 2026-07-28T13:26:54Z
updated: 2026-07-28T13:26:54Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1280
comments: 0
labels: bug, priority:medium, area:workspace, effort:small, semver:patch
assignees: none
milestone: Backlog
projects: none
parent: none
children: none
synced: 2026-07-29T05:28:56.326Z
---

# [Issue 1280]: [fix(workspace): undotted typos.toml escapes the #913 dual-config guard](https://github.com/vig-os/devkit/issues/1280)

### Description

The `typos` tool reads its configuration from any of **three** filenames: `typos.toml`, `.typos.toml`, or `_typos.toml`. The scaffold guards two of them:

- a consumer's `.typos.toml` is in `PRESERVE_FILES` (#913), and
- a legacy `_typos.toml` (with no `.typos.toml`) is handled at copy time via `MODE_CONFIG_EXCLUDES` — the template `.typos.toml` is not shipped, so the consumer keeps a single active config.

The third valid filename, **undotted `typos.toml`**, has no guard. The scaffold ships the template `.typos.toml` alongside it, leaving two active configs in the workspace — the same dual-config corruption class #913 fixed for `_typos.toml`.

### Steps to Reproduce

1. Consumer repo with a curated undotted `typos.toml` (e.g. a large domain-term/person-name allowlist) and no `.typos.toml`
2. Run `init-workspace.sh` (fresh scaffold or `--force` upgrade)
3. The template `.typos.toml` is written next to the existing `typos.toml`

### Expected Behavior

Same as the `_typos.toml` legacy case: the consumer's existing file is treated as the single active config and the template copy is not shipped (or the file is migrated to the canonical `.typos.toml` name with a visible notice in the scaffold report).

### Actual Behavior

Both `typos.toml` and `.typos.toml` exist after scaffolding. Depending on the tool's resolution order, the consumer's curated exceptions are silently shadowed — the `typos` hook then flags legitimate domain terms, or new exceptions get added to the file that isn't being read.

### Environment

devkit 1.4.2 (`init-workspace.sh`, `MODE_CONFIG_EXCLUDES` legacy-typos branch). Real-world consumer: a private single-user repo carrying a large undotted `typos.toml` allowlist, evaluated for devkit adoption.

### Possible Solution

Extend the existing #913 legacy-config branch in `init-workspace.sh` (the `MODE_CONFIG_EXCLUDES` block that special-cases `_typos.toml`) to also recognize undotted `typos.toml` as the consumer's single config, mirrored in `--preview` classification. Add a bats regression case alongside the existing `_typos.toml` one.

### Changelog Category

Fixed

