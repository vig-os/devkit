---
type: issue
state: open
created: 2026-09-25T21:09:21Z
updated: 2026-09-25T21:09:21Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1727
comments: 0
labels: chore, priority:low, area:workspace, effort:small, semver:patch
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-09-26T07:26:39.151Z
---

# [Issue 1727]: [[CHORE] Match devkit sentinel ids exactly in hook_block_range](https://github.com/vig-os/devkit/issues/1727)

### Chore Type

Refactoring / Technical debt

### Description

`hook_block_range` in `assets/init-workspace.sh` (around line ) locates a hook's sentinel range with a **prefix** match: `index($0, "# >>> devkit:" id)`. A sentinel whose id extends another id therefore satisfies the shorter id's lookup — verified with a fixture: a `# >>> devkit:shellcheck-composite-actions` block is returned for a lookup of id `shellcheck`.

Nothing in the template trips it today (the only sentinelled hooks are `actionlint` and the release group, and `shellcheck-composite-actions` is deliberately un-sentinelled — see the docstring added in #1725, which records this trap as the reason). It is a latent hazard for the next person who sentinel-wraps a hook whose id is a prefix-extension of another: the preserved-hook insert's anchor walk (#1725) and the feature excisions (`render_actionlint_optout`) would silently pick the wrong range.

### Acceptance Criteria

- [ ] The sentinel match requires the id to be followed by end-of-line or whitespace (exact id), for both `# >>> devkit:<id>` and `# <<< devkit:<id>`
- [ ] A pytest in `tests/test_scaffold_preserved_hooks.py` feeds a fixture carrying `# >>> devkit:shellcheck-composite-actions` and asserts a lookup for `shellcheck` falls through to the structural branch (or returns its own block), not the composite one
- [ ] The docstring's "do not sentinel-wrap an ungrouped hook" guidance is re-scoped to the feature-gating reason alone once the prefix hazard is gone

### Implementation Notes

In the awk: match `$0 ~ ("^[[:space:]]*# >>> devkit:" id "([[:space:]]|$)")` with the id escaped for regex metacharacters, or compare the extracted id token for equality instead of `index()`.

### Related Issues

- #1725 (found there), #1660 (sentinels' origin)

### Priority

Low

### Changelog Category

No changelog needed

