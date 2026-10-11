---
type: issue
state: open
created: 2026-10-10T22:19:48Z
updated: 2026-10-10T22:19:48Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1857
comments: 0
labels: bug, priority:high, area:ci
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-10-11T08:37:36.616Z
---

# [Issue 1857]: [setup-devkit-toolchain fails on macOS runners: tac, declare -A and env -0 under bash 3.2 / BSD userland](https://github.com/vig-os/devkit/issues/1857)

Found while planning a macOS CI lane for vig-os/vigil (devkit 1.18.0, direnv mode). Read from the action, not yet run on a macOS runner:

- `.github/actions/setup-devkit-toolchain/action.yml:263` pipes through **`tac`**. GitHub's macOS images have no GNU `tac` (BSD userland; `tail -r` is the equivalent).
- `:349` uses **`declare -A`** (associative arrays). macOS runners' `/bin/bash` is **3.2**, which doesn't support it (needs bash ≥4).
- `:290` and `:296` use **`env -0`** (GNU coreutils), which BSD `env` lacks.

Also, `DEVKIT_CI_RUNNER` is a single label set for every lane (`resolve-toolchain/action.yml:237`), so a consumer can't run *one* extra lane on macOS through the managed ci.yml. vigil will add its own `ci-extension.yml` job on `macos-15` that calls `setup-devkit-toolchain`.

**Ask:** make the action portable (POSIX or bash-3.2-compatible constructs, or install and use Nix-provided bash/coreutils before those steps), and add a macOS smoke job to devkit's own CI so it stays portable. vigil needs this for its 1.0 platform support (vig-os/vigil#46). A PR from the vigil side can follow if that helps.
