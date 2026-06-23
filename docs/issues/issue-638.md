---
type: issue
state: open
created: 2026-06-23T06:54:13Z
updated: 2026-06-23T06:55:00Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devcontainer/issues/638
comments: 0
labels: area:ci, security
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-06-23T08:02:48.271Z
---

# [Issue 638]: [T3.2 — Renovate `nix` manager for `flake.lock`](https://github.com/vig-os/devcontainer/issues/638)

Tracking: #625



## Context

Once the toolchain comes from the flake, the Renovate `dockerfile` base-digest loop is
replaced by maintenance of `flake.lock`. Renovate's `nix` manager + `lockFileMaintenance`
can bump the flake inputs through the normal PR/CI gate. The remaining `pep621`, `npm`, and
`github-actions` managers stay.

## Scope

**In:**
- Add the `nix` manager + `lockFileMaintenance` in `renovate.json`.
- Document the compensating control: include a `vulnix` before/after diff in each
  nixpkgs-bump PR (the `nix` manager won't name *which* CVE a rev bump fixes).

**Out:**
- The vulnix scanner setup itself (#637).

## Tasks

- [ ] Add the `nix` manager + `lockFileMaintenance` config
- [ ] Keep `pep621` / `npm` / `github-actions` managers
- [ ] Document the vulnix-diff compensating control in security docs

## Acceptance criteria

- Renovate opens `flake.lock` PRs through the normal CI gate.

## Dependencies

- **Depends-on:** #631.
- **Blocks:** none.

## Files

- `renovate.json`
- `CONTRIBUTE.md` / security docs

## Test notes

- Validate the Renovate config (`npx renovate-config-validator`) as part of the existing
  `test-renovate` recipe.

## Related issues

- **#604** (consolidate Trivy scan categories) — replacing the `dockerfile` base-digest update
  loop with `flake.lock` maintenance changes what Renovate produces; keep the scan-config SSoT
  documentation in #604 consistent with the new manager set.

