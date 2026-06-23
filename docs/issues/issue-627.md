---
type: issue
state: open
created: 2026-06-23T06:53:55Z
updated: 2026-06-23T06:55:31Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devcontainer/issues/627
comments: 0
labels: feature, area:workflow
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-06-23T08:02:52.921Z
---

# [Issue 627]: [C2 — Replace `cursor-agent` with the `claude` CLI in worktree pipelines](https://github.com/vig-os/devcontainer/issues/627)

Tracking: #625



## Context

`justfile.worktree` (15+ references) drives the autonomous worktree flows via the
`cursor-agent` CLI (`agent chat --yolo`, tmux `send-keys`). Migrating to a Claude-native
setup means driving these pipelines with the `claude` CLI instead. This is a functional
change, not a rename.

## Scope

**In:**
- Rewrite the worktree recipes to use the `claude` CLI.
- Update `CONTRIBUTE.md`, `README.md`, `scripts/requirements.yaml`.

**Out:**
- Removing the `cursor-agent` install from the image (#628).

## Tasks

- [ ] Map `agent` invocations → `claude` equivalents (notably `agent chat --yolo` → headless
      `claude -p`/`--dangerously-skip-permissions`; verify the tmux `send-keys` driving still
      applies or is replaced by non-interactive invocation)
- [ ] Rewrite `justfile.worktree` (and the template copy)
- [ ] Update docs and `scripts/requirements.yaml`

## Acceptance criteria

- Worktree pipelines run end-to-end via `claude`.
- No `cursor-agent` invocation remains in any recipe.

## Dependencies

- **Depends-on:** none.
- **Blocks:** #628, #630.

## Files

- `justfile.worktree`
- `assets/workspace/.devcontainer/justfile.worktree`
- `CONTRIBUTE.md`
- `README.md`
- `scripts/requirements.yaml`

## Test notes

- Functional change; covered by #630's `worktree.bats` rewrite.

## Related issues

- **#545** (bake Claude Code into image) — provides the `claude` binary these recipes drive;
  align with #628/#634 on where `claude` comes from.
- **#162** (replace hand-rolled CI polling with `gh pr checks --watch`) — touches the same
  worktree skills; a good companion refactor to land alongside the CLI swap.
- **#178 / #157** (worktree idle mode / pipeline-phase dashboard) — built on the same
  pipeline; verify they still work once driven by `claude`.

