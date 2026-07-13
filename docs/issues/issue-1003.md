---
type: issue
state: closed
created: 2026-07-13T07:52:09Z
updated: 2026-07-13T10:58:33Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1003
comments: 1
labels: chore, area:ci, effort:medium
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-07-13T15:17:52.561Z
---

# [Issue 1003]: [Re-enable actionlint's shellcheck integration and harden workflow run-blocks](https://github.com/vig-os/devkit/issues/1003)

### Description

The #995 actionlint adoption disabled the bundled shellcheck integration
(`-shellcheck=`) because the initial sweep surfaced 41 info/style/warning
findings (SC2086 quoting etc.) in `run:` blocks across the devkit's own and the
scaffolded template workflows. None were correctness defects, so they were
deferred rather than fixed in that scope.

### Acceptance Criteria

- [ ] Workflow `run:` blocks hardened (quoting, error handling) until the
      actionlint shellcheck pass is clean
- [ ] `-shellcheck=` opt-out removed from the hook (nix/hooks.nix) and the bats
      fixtures (tests/bats/init-workspace.bats)

### Related Issues

Follow-up to #995. Coordinate with the #991 workflow conversion to avoid churn
(convert first, then harden).

---

# [Comment #1]() by [c-vigo]()

_Posted on July 13, 2026 at 10:58 AM_

Resolved by #1013 (merged to `dev`). Closing.

