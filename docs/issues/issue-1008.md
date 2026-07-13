---
type: issue
state: closed
created: 2026-07-13T10:03:53Z
updated: 2026-07-13T10:58:31Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1008
comments: 1
labels: docs, area:workspace, effort:small, semver:patch
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-07-13T15:17:52.165Z
---

# [Issue 1008]: [Document --skip-pull in install.sh usage text](https://github.com/vig-os/devkit/issues/1008)

### Description

`install.sh` supports `--skip-pull` (use a local image tag without pulling from GHCR — needed e.g. to run against a locally built `:dev` image), but the flag is missing from the usage/help text. Surfaced by the #988 local validation run.

### Acceptance Criteria

- [ ] `--skip-pull` documented in the usage block and `--help` output

### Related Issues

Surfaced by #988 local validation.

---

# [Comment #1]() by [c-vigo]()

_Posted on July 13, 2026 at 10:58 AM_

Resolved by #1011 (merged to `dev`). Closing.

