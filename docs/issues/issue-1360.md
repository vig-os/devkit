---
type: issue
state: closed
created: 2026-08-07T10:51:59Z
updated: 2026-08-07T12:32:20Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1360
comments: 1
labels: bug, priority:medium, area:ci, effort:medium, semver:patch
assignees: none
milestone: 1.7.0
projects: none
parent: none
children: none
synced: 2026-08-07T21:31:02.879Z
---

# [Issue 1360]: [fix(action): pyproject-gated CPython PATH exclusion breaks Python consumers on NixOS self-hosted runners](https://github.com/vig-os/devkit/issues/1360)

## Problem

Split out of #1358 (found during the #1353 audit). The direnv-mode `setup-devkit-toolchain` PATH filter (#1028) removes the bare Nix CPython from the exported dev-shell PATH whenever `pyproject.toml` is present — unconditionally. On a hosted (FHS) runner that is correct: `uv` downloads a managed manylinux CPython. On a **NixOS self-hosted runner** it is wrong by design: after #1353 (UV_PYTHON no longer forwarded), `uv` downloads a managed CPython that NixOS cannot execute, so `uv sync` fails. Before #1353 the forwarded `UV_PYTHON` pin masked the gap.

No current consumer matches the combination (the only NixOS self-hosted runner consumer has no `pyproject.toml`), so nothing is broken today — this is a landmine for the first Python consumer that targets a NixOS runner.

## Expected

Make the exclusion NixOS-aware: keep the Nix CPython on PATH (and skip the managed-download path, e.g. keep/restore the uv pins) when the runner is NixOS — `[ -e /etc/NIXOS ]` is the established probe (mkProjectShell's own shellHook uses it for `LD_LIBRARY_PATH`).

Refs: #1358, #1353, #1028
---

# [Comment #1]() by [c-vigo]()

_Posted on August 7, 2026 at 12:32 PM_

Fixed on dev by PR #1363: the step probes the runner host once (/etc/NIXOS; DEVKIT_NIXOS_MARKER overrides it for the test harness only) and on NixOS keeps the Nix CPython on PATH AND lets the UV_PYTHON/UV_PYTHON_DOWNLOADS pins forward — both halves needed, since uv's python-preference could otherwise still pick an unrunnable managed download. FHS runners are byte-identical to before, now pinned by a regression-bar test (the #1028 exclusion previously had no coverage). Ships with 1.6.1.

