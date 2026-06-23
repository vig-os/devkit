---
type: issue
state: open
created: 2026-06-23T06:54:08Z
updated: 2026-06-23T06:55:06Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devcontainer/issues/635
comments: 0
labels: area:image, area:testing
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-06-23T08:02:49.530Z
---

# [Issue 635]: [T2.2 — Make the testinfra suite portable (TEST ADAPTATION)](https://github.com/vig-os/devcontainer/issues/635)

Tracking: #625



## Context

`tests/test_image.py` asserts Debian/FHS-specific facts (dpkg packages, hardcoded
`/usr/local/bin` paths, apt version prefixes, `DEBIAN_FRONTEND`) that break on a Nix-built
image. This issue makes the suite path-agnostic so it stays valid against **both** the Debian
and the Nix image — it is the linchpin that lets #634 go green.

## Scope

**In:**
- Replace `host.package("git"/"curl"/"tmux"/"rsync"/"openssh-client"/"nano").is_installed`
  (dpkg-only) with `host.run("<tool> --version").rc == 0`.
- Replace hardcoded `/usr/local/bin/{gh,just,hadolint,taplo}`, `/root/.cargo/bin`,
  `/root/.local/bin` with `which` / PATH resolution.
- Drop or skip `DEBIAN_FRONTEND` (~line 469) and apt version-prefix checks.
- Re-validate the `/root/assets/workspace/` mount assertions (~lines 521–578).

**Out:**
- The image build (#634).

## Tasks

- [ ] Convert dpkg `host.package(...)` checks to `--version` runs
- [ ] Convert hardcoded-path checks to `which` / PATH resolution
- [ ] Remove/skip `DEBIAN_FRONTEND` and apt version-prefix assertions
- [ ] Re-validate `/root/assets/workspace/` assertions

## Acceptance criteria

- Suite stays green on the **Debian** image.
- Suite is valid (path-agnostic) for the **Nix** image.

## Dependencies

- **Depends-on:** none (start early).
- **Gates:** #634 going green.

## Files

- `tests/test_image.py`
- `tests/conftest.py`

## Test notes

- Pure refactor — run against the current Debian image first to prove no regression, then it
  is ready for #634.

