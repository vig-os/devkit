---
type: issue
state: open
created: 2026-04-02T16:09:06Z
updated: 2026-04-02T16:09:29Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devcontainer/issues/482
comments: 0
labels: chore, area:workspace, effort:small
assignees: c-vigo
milestone: none
projects: none
parent: none
children: none
synced: 2026-04-03T04:35:47.792Z
---

# [Issue 482]: [[CHORE] Simplify pull recipe in justfile.gh — remove dead TEST_REGISTRY/REGISTRY_TEST logic](https://github.com/vig-os/devcontainer/issues/482)

### Chore Type

Configuration change

### Description

The `pull` recipe in `justfile.gh` (lines 105-116) is outdated and carries dead code:

1. **`repo` argument is unnecessary** — The parent `justfile` already defines `repo := env("TEST_REGISTRY", "ghcr.io/vig-os/devcontainer")` (line 10). Since `justfile.gh` is imported, `{{ repo }}` is available. All other registry-aware recipes (`build`, `test`, `clean`) use `{{ repo }}` directly.
2. **`TEST_REGISTRY` shell fallback is redundant** — The `RESOLVED_REPO="${repo:-${TEST_REGISTRY:-...}}"` logic duplicates what the justfile `repo` variable already handles at the just level.
3. **`REGISTRY_TEST` / TLS logic is dead code** — `REGISTRY_TEST` is only referenced in this one recipe across the entire codebase. It was a leftover from a local insecure-registry testing setup that no longer exists.

### Acceptance Criteria

- [ ] Remove `repo` argument from the `pull` recipe
- [ ] Use `{{ repo }}` from the parent justfile instead of shell-level fallback
- [ ] Remove `REGISTRY_TEST` / `--tls-verify=false` dead code
- [ ] Recipe works: `just pull latest` pulls from `ghcr.io/vig-os/devcontainer:latest`

### Implementation Notes

Target file: `justfile.gh` (lines 105-116)

Simplified recipe:
```just
# Pull image from registry (default: latest)
[group('release')]
pull version="latest":
    podman pull "{{ repo }}:{{ version }}"
```

No changes needed to the workspace copy (`assets/workspace/.devcontainer/justfile.gh`) — it doesn't have a `pull` recipe.

### Priority

Low

### Changelog Category

Changed
