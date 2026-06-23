---
type: issue
state: open
created: 2026-02-18T00:32:43Z
updated: 2026-06-23T06:56:44Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devcontainer/issues/66
comments: 1
labels: feature, priority:low, area:workspace, effort:medium, semver:minor
assignees: none
milestone: 0.4
projects: none
parent: 71
children: none
synced: 2026-06-23T08:02:59.031Z
---

# [Issue 66]: [[FEATURE] Improve workspace init: global just command and better non-empty error output](https://github.com/vig-os/devcontainer/issues/66)

### Description

Two improvements to the workspace initialization experience:

1. **Global `just` command for workspace init** — A global justfile (`~/.config/just/justfile`) that provides `just -g init-workspace <path>` to initialize any project with the devcontainer template from anywhere on the host system. The `install.sh` script offers to install this global justfile as a post-init step on first run, so users discover it naturally.

2. **Improved error message when workspace is not empty** — When `init-workspace.sh` detects a non-empty workspace and `--force` is not passed, the current error message is vague ("Workspace is not empty. Use --force to overwrite existing files."). The improved version shows exactly which files would be overwritten and which would be added, so the user can make an informed decision.

### Problem Statement

- Installing the devcontainer into an existing project currently requires remembering the full `curl` URL or the `podman run` command with the correct image path and volume mount. A global `just` command makes this a simple, memorable invocation — and offering it during the first install ensures discoverability.
- The current non-force error gives no visibility into what `--force` would actually do, making users hesitant to proceed.

### Proposed Solution

1. Add a global justfile at `~/.config/just/justfile` with an `init-workspace` recipe that auto-detects the container runtime, pulls the latest image, and runs `init-workspace.sh`.
2. At the end of `install.sh`, after the existing post-init steps, detect whether `just` is installed and the global justfile is absent. If so, offer to install it (interactive prompt, skip in `--no-prompts` mode).
3. Update `assets/init-workspace.sh` to show a file-by-file breakdown (overwritten vs. added) when the workspace is non-empty and `--force` is not passed.

### Acceptance Criteria

- [ ] Global justfile template exists in `assets/global-justfile` (source of truth in the repo)
- [ ] `install.sh` offers to install the global justfile when `just` is available and `~/.config/just/justfile` does not exist
- [ ] `just -g init-workspace <path>` pulls the latest image and initializes the target workspace
- [ ] `just -g init-workspace <path> --force` passes `--force` through to `init-workspace.sh`
- [ ] Non-empty workspace error in `init-workspace.sh` lists files that would be overwritten and files that would be added
- [ ] Existing `install.sh` tests still pass; new behavior is covered

### Implementation Notes

- The global justfile template should live in `assets/global-justfile` so it is versioned and can be updated on `--force` upgrades.
- The post-init prompt in `install.sh` should be skipped when `--no-prompts` is set (CI/automation).
- The global justfile uses `ghcr.io/vig-os/devcontainer:latest` as the default image — no repo-local variables.

### Impact

- Who benefits: developers initializing or upgrading projects with the devcontainer.
- Backward compatible: the global justfile is opt-in (offered, not forced); the error message change is purely informational.

### Changelog Category

Added
---

# [Comment #1]() by [c-vigo]()

_Posted on June 23, 2026 at 06:56 AM_

Same install/init entrypoint as #641 (part of #625), which adds a `devcontainer | direnv | both` mode picker. Land the mode picker and these init UX improvements together.

