---
type: issue
state: closed
created: 2026-09-25T20:11:53Z
updated: 2026-09-25T21:32:03Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1725
comments: 2
labels: bug, priority:low, area:workspace, effort:small, semver:patch
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-09-26T07:26:39.538Z
---

# [Issue 1725]: [[BUG] Preserved-hook insert skips a new hook when its template anchor is a disabled feature](https://github.com/vig-os/devkit/issues/1725)

### Description

`insert_missing_hook_blocks` (`assets/init-workspace.sh`) inserts a new scaffolded hook into a preserved `.pre-commit-config.yaml` right after the hook the template places before it (`template_hook_anchor`). For `shellcheck-composite-actions` that anchor is `actionlint`. A consumer pinned below 1.17.0 who set `DEVKIT_FEATURES_DISABLED=actionlint` therefore has no anchor, and the insert is skipped:

```
Warning: the preserved .pre-commit-config.yaml carries no 'actionlint' hook to anchor the new 'shellcheck-composite-actions' block (#1654).
```

Exit 0, no partial write — safe, and the existing `test_the_feature_opt_out_is_honoured` covers the skip. But the consumer never receives a hook they did not opt out of, and the warning reads as a defect rather than a decision. Reproduced live while verifying #1717. No known consumer is currently in that state (the local fleet shows none disabling actionlint), so this is low priority.

### Steps to Reproduce

1. Scaffold a consumer at `DEVKIT_VERSION=1.16.0` with `DEVKIT_FEATURES_DISABLED=actionlint` (its preserved config has no actionlint block)
2. Upgrade with a devkit whose `inserted_hook_blocks()` carries the `1.17.0 shellcheck-composite-actions` row
3. Observe the warning; the composite block is absent

### Expected Behavior

The insert falls back to the next available anchor in template order (the hook before actionlint, i.e. `shellcheck`, or the first present predecessor), so an opt-out of one hook does not block delivery of an unrelated later one.

### Actual Behavior

Skipped with a warning.

### Environment

- **OS**: any
- **Container Runtime**: n/a
- **Image Version/Tag**: dev
- **Architecture**: any

### Additional Context

Found in the #1717 implementation. The single-anchor design dates from #1660 when there was only one insertable hook.

### Possible Solution

`template_hook_anchor` returns the list of predecessors in template order; `insert_missing_hook_blocks` walks it and anchors on the first one present in the consumer's file, warning only when none is. Boundary tests in `tests/test_scaffold_preserved_hooks.py`: actionlint disabled + pin 1.16.0 gains the composite block after `shellcheck`.

### Changelog Category

Fixed

---

# [Comment #1]() by [c-vigo]()

_Posted on September 25, 2026 at 08:18 PM_

Also from the #1717 review, same area: the composite block is the template entry byte-exact but loses its leading prose comment when inserted, because `hook_block_range` falls back to scanning from `- repo:` for an un-sentinelled entry (actionlint keeps its comment only because sentinels wrap it). Sentinel-wrapping the composite entry in the template would keep the rationale in the consumer's copy; worth doing together with the anchor fallback.

---

# [Comment #2]() by [c-vigo]()

_Posted on September 25, 2026 at 09:32 PM_

Fixed in #1728, merged to `dev` (641b6ede): the insert anchors on the nearest predecessor the consumer's file still carries (sentinel range preferred, so an insert after a present actionlint still lands outside its excision range), and an un-sentinelled block now arrives with its template comment run — the fold shares the extractor and carries it too. Sentinel-wrapping was rejected because `hook_block_range` matches sentinel ids by prefix; hardening that is #1727.

