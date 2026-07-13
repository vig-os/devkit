---
type: issue
state: closed
created: 2026-07-13T10:08:25Z
updated: 2026-07-13T10:58:29Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1009
comments: 1
labels: chore, area:workspace, effort:small, semver:patch
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-07-13T15:17:51.826Z
---

# [Issue 1009]: [Scaffolded flake stub still points at github:vig-os/devcontainer after the devkit rename](https://github.com/vig-os/devkit/issues/1009)

### Description

`assets/workspace/flake.nix` (the consumer stub) sets
`vigos.url = "github:vig-os/devcontainer"` and its pin example uses the same
name. #781 (rename devcontainer → devkit) is closed; the URL keeps working only
via GitHub's repo redirect. New consumers should reference `vig-os/devkit`
directly. Note the stub is a PRESERVE_FILES entry, so existing consumers never
receive the fix automatically — mention the rename in MIGRATION.md.

Surfaced by a commit-action migration dry-run against the #988 epic branch.

### Acceptance Criteria

- [ ] Stub (and its pin-example comment) reference `github:vig-os/devkit`
- [ ] MIGRATION.md notes the URL rename for existing direnv consumers

### Related Issues

Follow-up to #781. Related to the #988 rollout pilot.

---

# [Comment #1]() by [c-vigo]()

_Posted on July 13, 2026 at 10:58 AM_

Resolved by #1010 (merged to `dev`). Closing.

