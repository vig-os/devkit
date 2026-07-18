---
type: issue
state: open
created: 2026-07-17T20:27:10Z
updated: 2026-07-17T20:27:10Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1208
comments: 0
labels: feature, priority:medium, area:ci, area:workspace, effort:medium
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-07-18T04:54:21.058Z
---

# [Issue 1208]: [workflow-model: scaffold render core (render_workflow_model + sync-main-to-dev exclude + preview mirror)](https://github.com/vig-os/devkit/issues/1208)

Part of #1205. Depends on #1205 sub-1 (manifest key).

- **Copy-exclude** `sync-main-to-dev.yml` in trunk (`EXCLUDE_ARGS` after mode excludes ~:1148-1153) + post-copy prune for gitflow→trunk upgrade (~:1259, modeled on the container-docs prune).
- **`render_workflow_model()`** (sibling to `render_codeql_matrix()` ~:857), run in trunk, anchored `dev→main` edits: `prepare-release.yml` (`ref: dev`, `heads/dev`, step names — anchored so `development`/`devkit`/`devcontainer` untouched); `ci.yml` (drop `- dev` from `on:` filter, `TRUNK="dev"`→`main`); `codeql.yml` (drop `- dev`); `sync-issues.yml` (default + fallbacks dev→main); scaffolded `branch-naming/SKILL.md` (base default); scaffolded `.pre-commit-config.yaml` (drop `(?!dev$)`).
- **`--force` preview mirror** (:917-990): skip `sync-main-to-dev.yml` in copy report, list under DELETIONS on gitflow→trunk, note the rendered files — keep `--preview` truthful.

Compose as separate sequential if/case blocks (mode × model orthogonal, never combined case).

Refs: #1205
