---
type: issue
state: open
created: 2026-06-16T13:08:56Z
updated: 2026-06-16T13:08:56Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devcontainer/issues/591
comments: 0
labels: bug, priority:high, area:workspace, effort:small
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-06-17T07:21:12.036Z
---

# [Issue 591]: [fix: devcontainer-upgrade / install URL 404s (vig-os.github.io not hosted)](https://github.com/vig-os/devcontainer/issues/591)

## Summary

The install/upgrade flow points users at `https://vig-os.github.io/devcontainer/install.sh`, which **404s** because GitHub Pages is not set up for this repo. The canonical, working URL (used in `README.md`) is the raw GitHub URL piped to **`bash`** (not `sh`):

```
curl -sSf https://raw.githubusercontent.com/vig-os/devcontainer/main/install.sh | bash -s -- --force ./
```

This affects the actual `just devcontainer-upgrade` recipe — not just printed hints — so upgrading is broken even from a host terminal.

## Reproduction

Inside the devcontainer:

```
$ just devcontainer-upgrade
❌ ERROR: This command must be run from a HOST terminal
...
Or use the curl method:

    curl -sSf https://vig-os.github.io/devcontainer/install.sh | sh -s -- --force .
```

Following the suggested curl command (or running the recipe from the host):

```
$ curl -sSf https://vig-os.github.io/devcontainer/install.sh | sh -s -- --force .
curl: (22) The requested URL returned error: 404
```

## Root cause

The `vig-os.github.io/devcontainer/install.sh` URL assumes GitHub Pages hosting that was never enabled (already noted in `docs/pull-requests/pr-22.md`). `README.md` already uses the correct `raw.githubusercontent.com/.../main/install.sh | bash` form, but the rest of the repo was never updated to match.

Two distinct defects:
1. **Wrong host** — `vig-os.github.io` (Pages, not enabled) vs `raw.githubusercontent.com/vig-os/devcontainer/main`.
2. **Wrong shell** — piped to `sh`, but `install.sh` has a `#!/bin/bash` shebang and may use bashisms; `README.md` correctly uses `bash`.

## Affected files (excluding archived `docs/issues`, `docs/pull-requests`)

- `assets/workspace/.devcontainer/justfile.devc:50` — error hint shown inside container
- `assets/workspace/.devcontainer/justfile.devc:77` — **the actual upgrade command run on the host** (this is the real breakage)
- `assets/workspace/.devcontainer/scripts/version-check.sh:287` — upgrade-available nag message
- `assets/smoke-test/README.md:92` — smoke-test install instructions
- `install.sh:5,6,21,62,79,470` — usage/help comments and `--help` output

## Proposed fix

Replace all `vig-os.github.io/devcontainer/install.sh | sh` references with `raw.githubusercontent.com/vig-os/devcontainer/main/install.sh | bash`, matching the canonical form already in `README.md` (single source of truth). Verify the resulting `just devcontainer-upgrade` succeeds end-to-end from a host terminal.

