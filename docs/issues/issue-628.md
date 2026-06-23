---
type: issue
state: open
created: 2026-06-23T06:53:57Z
updated: 2026-06-23T06:55:33Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devcontainer/issues/628
comments: 0
labels: area:image, security
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-06-23T08:02:52.556Z
---

# [Issue 628]: [C3 — Remove `cursor-agent` install from the image](https://github.com/vig-os/devcontainer/issues/628)

Tracking: #625



## Context

`Containerfile` (~lines 166–182) curl-installs `cursor-agent` unpinned from an external CDN,
and `.trivyignore` carries `CVE-2026-55388` (piscina) on its behalf. `cursor-agent` is the
only tool **not** available in nixpkgs, so removing it leaves an all-nixpkgs toolchain and
materially simplifies the Nix migration (precedes #634).

## Scope

**In:**
- Delete the `cursor-agent` install block and its `/root/.local/bin` PATH note.
- Drop the piscina CVE (`CVE-2026-55388`) from `.trivyignore`.

**Out:**
- The broader Nix rebuild of the image (#634).

## Tasks

- [ ] Remove the install block from `Containerfile` and `build/Containerfile`
- [ ] Prune the related PATH note
- [ ] Remove the `CVE-2026-55388` entry from `.trivyignore`
- [ ] Changelog entry

## Acceptance criteria

- Image builds without `cursor-agent`.
- Trivy run is clean without the previously ignored CVE.

## Dependencies

- **Depends-on:** #627.
- **Blocks:** (precedes) #634.

## Files

- `Containerfile`
- `build/Containerfile`
- `.trivyignore`

## Test notes

- #630 removes the corresponding `test_cursor_agent_installed` image test.

## Related issues

- **#545** (bake agent-CLI toolkit + Claude Code into image) — as `cursor-agent` is removed,
  `claude` becomes the baked agent CLI. The install *mechanism* in #545 (apt/curl) is replaced
  by the Nix `devTools` path (#631/#634); its `IS_SANDBOX=1` + `cc`/`cld` aliases carry into
  #634. Coordinate so cursor-agent removal and claude bake-in are consistent.

