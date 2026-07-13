---
type: issue
state: closed
created: 2026-07-13T06:14:20Z
updated: 2026-07-13T09:23:15Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/991
comments: 2
labels: refactor, priority:high, area:ci, effort:large, semver:minor
assignees: none
milestone: Backlog
projects: none
parent: 988
children: none
synced: 2026-07-13T15:17:54.695Z
---

# [Issue 991]: [CI + release workflows hard-coupled to the container image regardless of DEVKIT_MODE](https://github.com/vig-os/devkit/issues/991)

### Description

Every scaffolded CI and release job runs inside
`container: ghcr.io/vig-os/devcontainer:<tag>`, gated by a `resolve-image` job
that reads `.vig-os`. **No workflow branches on `DEVKIT_MODE`.** A `direnv` or
`bare` consumer still mandates the devcontainer image in CI and at release time —
contradicting the point of choosing a container-less mode.

This is the core of the epic and the largest surface.

### Agreed design

- **Keep one release pipeline.** `release-core/publish/extension` stay reusable
  `workflow_call` workflows; the choreography does not fork per mode.
- **Add a shared `setup-devkit-toolchain` composite action** that branches on
  `DEVKIT_MODE` from `.vig-os`:
  - `container` → today's `container:` image path
  - `direnv`   → `install-nix-action` + `nix develop` / flake devshell
  - `bare`     → host-native `setup-node` / `uv` / etc.
- **Publish step keyed on artifact type, not mode** (image / JS action / crate /
  flake) — a small per-repo hook.
- Job-level `container:` can't be conditionally unset by expression: use
  `if:`-gated job wrappers, or a documented "container unless mode≠container"
  default.

### Acceptance Criteria

- [ ] CI (`ci.yml`) provisions its toolchain via the mode-aware action; `direnv`/
      `bare` runs contain no `container: ghcr.io/vig-os/devcontainer`.
- [ ] Release workflows provision toolchain the same way; release logic unchanged
      and single-source.
- [ ] `resolve-image` usage confined to `container` mode.
- [ ] Validated per mode: rendered-workflow bats assertions + actionlint (#995)
      for all modes; live container lane via the smoke-test repo release cycle;
      live direnv lane via the commit-action rollout pilot. (Reworded from
      "smoke-tested across all three modes" — the smoke-test repo stays
      single-mode, see the plan on #988.)

### Related Issues

Part of the mode-aware scaffold epic. Absorbs the `container:`/`resolve-image`
leaks noted in D1. Building blocks split out: #992 (spike: conditional
`container:`, Option A vs B), #993 (vig-utils host-side), #994
(`setup-devkit-toolchain` composite), #995 (actionlint). This issue covers the
conversion of `ci.yml` (collapsing the per-mode overlays, per the #992 spike
outcome) and the release/automation workflow set to the composite pattern.


Part of #988.


---

# [Comment #1]() by [c-vigo]()

_Posted on July 13, 2026 at 08:26 AM_

PART A merged via #1005: single mode-aware ci.yml (resolve-toolchain + conditional container + setup-devkit-toolchain), overlay dirs and init-workspace.sh overlay logic removed. Verified locally in the dev-shell: 146/146 + 89/89 bats green, actionlint fixtures green across all rendered modes. PART B (release/automation set) in progress.

---

# [Comment #2]() by [c-vigo]()

_Posted on July 13, 2026 at 09:23 AM_

Both parts merged into the epic branch: PART A #1005 (single mode-aware ci.yml, overlays removed) and PART B #1006 (release/automation set on resolve-toolchain threading + setup-devkit-toolchain; scaffold resolve-image retired). Choreography unchanged. Verified locally in the dev-shell: 288/288 scoped bats green incl. actionlint fixtures over every rendered mode; the only full-dir failures are the 9 pre-existing environment-dependent IN_CONTAINER githook tests (identical on the epic-branch baseline, green in CI).

