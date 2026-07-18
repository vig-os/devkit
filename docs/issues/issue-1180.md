---
type: issue
state: closed
created: 2026-07-17T12:03:42Z
updated: 2026-07-17T13:00:21Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1180
comments: 1
labels: bug, priority:high, area:ci, effort:medium, semver:minor
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-07-18T04:54:25.551Z
---

# [Issue 1180]: [direnv-mode CI: setup-devkit-toolchain forwards only PATH, shellHook env is silently dropped](https://github.com/vig-os/devkit/issues/1180)

## Description
The direnv-mode CI preamble (`setup-devkit-toolchain`) exports the dev-shell store bin dirs to `GITHUB_PATH` but never the shellHook's environment exports. Anything a project wires via `shellHook` (env defaults, tool configuration) works in every local `nix develop`/direnv session and silently vanishes on CI — local-vs-CI divergence that surfaces as unrelated tool errors.

## Evidence (org-config)
- vig-os/org-config#40: `just validate` green locally (shellHook seeded a placeholder `OTTERDOG_TOKEN`), red on CI with `environment variable 'OTTERDOG_TOKEN' not found` (run 29577821802). Fixed consumer-side by inlining the default into the recipe (org-config@fb01eee).

## Suggested direction
Either forward shellHook env (e.g. capture `nix print-dev-env` exports into `GITHUB_ENV`, possibly behind an opt-in) or document loudly that shellHook env is local-only and recipes must be self-sufficient.

Refs: vig-os/org-config#17
---

# [Comment #1]() by [c-vigo]()

_Posted on July 17, 2026 at 01:00 PM_

Fixed on dev via PR #1183 (merge @972e74b1): the direnv-mode preamble now diffs the ambient environment against the dev-shell environment and forwards shellHook-added/changed vars to GITHUB_ENV by default, minus a denylist of session state and Nix/stdenv build machinery. Documented in docs/MIGRATION.md. Ships with the next devkit release.

