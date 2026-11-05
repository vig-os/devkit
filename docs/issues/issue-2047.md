---
type: issue
state: open
created: 2026-11-04T15:39:59Z
updated: 2026-11-04T15:39:59Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/2047
comments: 0
labels: bug
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-11-05T09:17:45.543Z
---

# [Issue 2047]: [.vig-os readers disagree on duplicate keys (resolver: last wins; init-workspace: first wins)](https://github.com/vig-os/devkit/issues/2047)

Found in review of #2046 (#2045).

- `resolve-toolchain` keeps the **last** occurrence of a `.vig-os` key.
- `assets/init-workspace.sh` `read_manifest_value` stops at the **first** one, and returns 1 when that first value is empty.

The template now ships `DEVKIT_CI_CONTAINER_RUNNERS=` empty. A user who *appends* `DEVKIT_CI_CONTAINER_RUNNERS=true` instead of editing that line gets this:

- CI: opted in (the resolver reads `true`).
- Next upgrade: init-workspace reads the empty first value, so the opt-in is not carried forward and the repo silently moves back to hosted runners.

The mismatch affects every key; the empty template line just makes it easy to hit.

**Acceptance:** one shared `.vig-os` reading rule (one implementation, or both readers pinned to the same semantics by a shared test), and a duplicate key is either last-wins everywhere or rejected with a clear error.
