---
type: issue
state: open
created: 2026-11-17T19:41:06Z
updated: 2026-11-17T19:41:06Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/2085
comments: 0
labels: bug, area:ci
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-11-17T20:22:43.594Z
---

# [Issue 2085]: [Toolchain setup hardening: follow-ups from the #2082 review](https://github.com/vig-os/devkit/issues/2085)

These came out of the fresh review of #2082 (#2010). None of them blocked that PR.

- [ ] **Minimal host mode assumes gh and jq on the runner.** With `minimal: true`, rollback and cleanup jobs in direnv mode no longer get `gh`/`jq` from the dev-shell (`nix/devtools.nix`). They rely on the runner image instead. A runner without `gh` would fail the rollback with exit 127. Add a `command -v gh jq` precheck that fails with an explicit `::error::` in minimal host mode.
- [ ] **Devkit's own CI has no Nix network bounds.** `.github/actions/setup-env/action.yml` uses the same `install-nix-action` without the `connect-timeout` / `stalled-download-timeout` / `download-attempts` settings that #2082 added to the scaffold action. Devkit's own CI can still stall silently. Share one source for the settings rather than copying them.
- [ ] **Two steps have no wall-clock bound.** The "Install Nix" step (the installer download) and bare mode's `uv tool install` have no bound. The network settings only cover Nix transfers after install.
- [ ] **The minimal-job guard uses a hard-coded list.** `MINIMAL_JOBS` in `tests/test_toolchain_release_lane.py` names jobs explicitly, so a new rollback or cleanup job that forgets `minimal: true` still passes. Derive the set from the workflows, e.g. jobs gated on failure/cancellation or named rollback/cleanup, or require an explicit annotation.

Refs #2010.
