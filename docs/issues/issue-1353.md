---
type: issue
state: closed
created: 2026-08-07T08:54:20Z
updated: 2026-08-07T10:15:45Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1353
comments: 1
labels: bug, priority:high, area:ci, effort:small, semver:patch
assignees: none
milestone: 1.7.0
projects: none
parent: none
children: none
synced: 2026-08-07T21:31:04.562Z
---

# [Issue 1353]: [fix(action): shellHook env forward ships UV_PYTHON to CI, defeating the bare-CPython exclusion](https://github.com/vig-os/devkit/issues/1353)

## Problem

Two correct mechanisms in `setup-devkit-toolchain` (direnv mode) cancel each other out:

1. The #698/#703/#729 mitigation excludes the bare Nix CPython from the exported PATH and forwards `UV_PYTHON_DOWNLOADS_JSON_URL`, so `uv sync` on a hosted runner builds the venv from a **downloaded manylinux CPython**.
2. The #1180 shellHook-env forward diffs the dev-shell env against the ambient env and ships every added var to `GITHUB_ENV` — including **`UV_PYTHON`**, which `mkProjectShell` pins to the Nix interpreter (needed locally: a manylinux CPython cannot run on NixOS).

`UV_PYTHON` wins over PATH resolution, so `uv` builds the CI venv on the Nix CPython anyway. Any C-extension wheel then fails under the Nix loader on Ubuntu:

```
ImportError: libstdc++.so.6: cannot open shared object file: No such file or directory
```

First live hit: exo-pet/playground-carlos#9 (numpy 2.4.4, run 31163316165). Every existing direnv Python consumer has this forwarded — they are green only because their test deps are pure-Python, i.e. the intended "downloaded manylinux CPython" CI path has likely not actually executed since #1180 landed.

## Expected

Add `UV_PYTHON` to the forward denylist for Python consumers (it is Nix-host-specific by construction, like the PATH entries the action already filters). Worth auditing the denylist for other host-specific pins at the same time.

## Workaround (consumer-side, applied in exo-pet/playground-carlos#9)

```nix
shellHook = ''
  if [ -n "''${GITHUB_ACTIONS:-}" ]; then unset UV_PYTHON; fi
'';
```

Verified: locally the pin stays; under `GITHUB_ACTIONS=true` the var is absent from the dev-shell env, so the diff-forward never ships it.
---

# [Comment #1]() by [c-vigo]()

_Posted on August 7, 2026 at 10:15 AM_

Fixed on dev by PR #1357: UV_PYTHON and UV_PYTHON_DOWNLOADS are now denied by exact name in the shellHook env forward's denylist, so uv sync on hosted runners builds the venv from the downloaded manylinux CPython as designed. UV_PYTHON_DOWNLOADS goes with it — forwarded alone, 'never' would forbid the very download the UV_PYTHON_DOWNLOADS_JSON_URL forward enables. The deliberate JSON-URL forward survives (exact-match patterns) and is now pinned by a test. Ships with the next devkit release; the consumer-side GITHUB_ACTIONS-gated unset in exo-pet/playground-carlos#9 can be dropped after the upgrade. The denylist audit's out-of-scope findings are filed separately.

