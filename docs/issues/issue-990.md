---
type: issue
state: closed
created: 2026-07-13T06:14:18Z
updated: 2026-07-13T07:44:32Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/990
comments: 1
labels: feature, area:workspace, effort:small, semver:minor
assignees: none
milestone: Backlog
projects: none
parent: 988
children: none
synced: 2026-07-13T15:17:55.085Z
---

# [Issue 990]: [Mode-switch doesn't prune a pre-existing .devcontainer/ on container→direnv migration](https://github.com/vig-os/devkit/issues/990)

### Description

Mode-switch is deliberately non-destructive toward a **pre-existing**
`.devcontainer/` (#738): a container-mode `.devcontainer/` is preserved when
re-running in `direnv`/`bare`. That is correct for coexistence, but on a real
**container → direnv migration** it strands the old container next to the new
flake, with no signal to remove it.

Concrete case from the rollout pilot: `vig-os/commit-action` carries an old
apt/Debian `.devcontainer/` (broken — assumes a Debian base, see
vig-os/commit-action#30). A `--mode direnv` deploy would leave that stale,
broken container in place alongside the new `flake.nix`/`.envrc`.

### Acceptance Criteria

- [ ] A supported way to prune a stale `.devcontainer/` on mode-switch
      (e.g. opt-in `--prune-devcontainer`, or an interactive prompt when a
      populated `.devcontainer/` is detected in a container-less mode).
- [ ] Default stays non-destructive (#738 preserved).
- [ ] `docs/MIGRATION.md` documents the container → direnv/bare migration cleanup.

### Related Issues

Part of the mode-aware scaffold epic. Preserves #738 default behavior.


Part of #988.

---

# [Comment #1]() by [c-vigo]()

_Posted on July 13, 2026 at 07:44 AM_

Merged into the epic branch via #1000: opt-in --prune-devcontainer (init-workspace.sh + install.sh forwarding), interactive prompt, preview DELETED integration, #738 default preserved, MIGRATION.md runbook. Verified locally: 224/224 bats green.

