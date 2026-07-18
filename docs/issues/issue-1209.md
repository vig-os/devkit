---
type: issue
state: open
created: 2026-07-17T20:27:19Z
updated: 2026-07-17T20:27:19Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1209
comments: 0
labels: feature, priority:medium, area:workspace, effort:medium
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-07-18T04:54:20.783Z
---

# [Issue 1209]: [workflow-model: install.sh --workflow flag + dev-branch creation gating](https://github.com/vig-os/devkit/issues/1209)

Part of #1205. Depends on #1205 sub-1 (manifest key).

- `install.sh`: `--workflow gitflow|trunk` flag parse (~:436-442) + enum validate (~:485-489); thread to init-workspace (~:713-714); adopt-persisted fallback (~:562-564).
- `init-workspace.sh`: matching `--workflow` flag parse (~:163-170) + validate (~:180-186).
- **Gate dev creation** in `setup_git_repo` (:848-875): `git branch dev` (:851-855) + missing-dev warning (:862-866) run only in gitflow; push hint (:875) drops `dev` in trunk. `git init -b main` (:825) unchanged.

Single canonical `--workflow` flag; no `--no-dev` alias.

Refs: #1205
