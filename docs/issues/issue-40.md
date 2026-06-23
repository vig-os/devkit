---
type: issue
state: open
created: 2026-02-02T08:56:09Z
updated: 2026-06-23T06:56:38Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devcontainer/issues/40
comments: 3
labels: feature, priority:backlog, area:workflow
assignees: none
milestone: Backlog
projects: none
parent: none
children: none
synced: 2026-06-23T08:02:59.411Z
---

# [Issue 40]: [[DISCUSSION] Migration to prek](https://github.com/vig-os/devcontainer/issues/40)

Should we migrate from `pre-commit` to [`prek`](https://github.com/j178/prek)?
---

# [Comment #1]() by [gerchowl]()

_Posted on February 20, 2026 at 03:18 PM_

@c-vigo Should we target this for the 0.4 milestone, or keep it on the backlog for now?

---

# [Comment #2]() by [c-vigo]()

_Posted on February 20, 2026 at 03:49 PM_

@gerchowl backlog

---

# [Comment #3]() by [c-vigo]()

_Posted on June 23, 2026 at 06:56 AM_

Decision point surfaced by #634 (part of #625): the pre-commit cache layer is rebuilt on the Nix image, so `pre-commit` vs `prek` (both packaged in nixpkgs) is the natural choice to make there. Light reference — not superseded.

