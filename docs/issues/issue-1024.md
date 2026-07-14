---
type: issue
state: open
created: 2026-07-13T16:43:13Z
updated: 2026-07-13T16:43:13Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1024
comments: 0
labels: bug, priority:medium, area:workspace, effort:medium, semver:minor
assignees: none
milestone: Backlog
projects: none
parent: none
children: none
synced: 2026-07-14T04:57:27.093Z
---

# [Issue 1024]: [[BUG] Scaffold .gitignore is Python-only: blanket dist/ breaks JS Action repos, Node ignores dropped, not upgrade-persistent](https://github.com/vig-os/devkit/issues/1024)

### Description

Surfaced by the commit-action direnv pilot (1.1.0). The scaffolded `.gitignore`
is the stock **Python** `github/gitignore` template, which is wrong for Node /
GitHub Action consumers on two counts:

1. **Blanket `dist/` ignore breaks JS Action repos.** A JS GitHub Action commits
   its bundled entrypoint (`dist/index.js`, referenced by `action.yml`
   `runs.main`). The scaffold's `dist/` line ignores that committed bundle, so
   `git add dist/…` silently no-ops on new bundle files.
2. **Node ignores are dropped.** No `node_modules/`, `*.tsbuildinfo`,
   `coverage/`, `.nyc_output/` — so a fresh `npm ci` leaves `node_modules/`
   untracked-but-not-ignored, easy to commit by accident.

Compounding both: `.gitignore` is a **managed/overwritten** scaffold file, so a
consumer's hand-fix does not survive the next `install.sh`/upgrade.

### Impact

Any Node/TS consumer (commit-action, sync-issues-action, …) must hand-edit
`.gitignore` after every devkit upgrade, and risks either ignoring a committed
artifact (`dist/`) or committing `node_modules/`.

### Repro

Deploy any mode to a Node repo and inspect `.gitignore`:
```
git check-ignore node_modules   # -> not ignored
git check-ignore dist/index.js  # -> IGNORED (should be tracked for a JS action)
```

### Options

- Make the scaffold `.gitignore` **language-aware** (detect `package.json` /
  `Cargo.toml` and emit the matching ignore set), or ship a small language-neutral
  base + language fragments.
- Or provide a preserved **`.gitignore.project`** companion (same
  scaffold-once/never-overwrite guarantee as `justfile.project` /
  `docker-compose.project.yaml`) that consumers own.
- At minimum, do not blanket-ignore `dist/` (scope it to Python build output),
  and document the Node/Action ignore additions.

### Notes

Non-blocking for 1.1.0; found during the pilot rollout. Workaround applied in
commit-action: removed `dist/`, restored the Node/Action ignore section.

