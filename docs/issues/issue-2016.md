---
type: issue
state: open
created: 2026-11-03T18:43:06Z
updated: 2026-11-03T18:43:06Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/2016
comments: 0
labels: none
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-11-04T08:54:31.418Z
---

# [Issue 2016]: [devkit-docs module: follow-ups from the #2012 review (nested-import clash, variable false positive, preview on clash)](https://github.com/vig-os/devkit/issues/2016)

Follow-ups from the review of #2012 (#2011). None blocked the merge.

1. **Clash check misses imported justfiles.** Collision detection only greps justfile, justfile.project and justfile.local. A `devkit-docs` recipe in a justfile imported from one of those still breaks `just --list` once docs is ON. A sturdier check: append the `mod devkit-docs` line to a temp copy, run `just --summary`, and drop the line with the notice if that fails.
2. **False positive on variables.** A consumer variable `devkit-docs := 'x'`, or a recipe body line starting with `devkit-docs`, triggers the skip, although just 1.51 accepts a variable and a module with the same name.
3. **Preview on a clash.** `--preview` says the module will be added even when the real install will skip it.

Refs: #2011
