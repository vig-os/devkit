---
type: issue
state: closed
created: 2026-07-14T07:26:36Z
updated: 2026-07-14T08:26:59Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1028
comments: 1
labels: bug, priority:low, area:ci, effort:small, semver:patch
assignees: none
milestone: Backlog
projects: none
parent: none
children: none
synced: 2026-07-14T20:06:33.680Z
---

# [Issue 1028]: [[BUG] setup-devkit-toolchain applies python/uv CI env unconditionally on non-python consumers](https://github.com/vig-os/devkit/issues/1028)

### Description

Surfaced by the commit-action pilot (vig-os/commit-action#32). The shared CI
composite `.github/actions/setup-devkit-toolchain/action.yml` applies **Python/uv
environment unconditionally**, regardless of the consumer's language or
`DEVKIT_MODULES`:

- `UV_PROJECT_ENVIRONMENT=/root/assets/workspace/.venv` (line ~61)
- forwards `UV_PYTHON_DOWNLOADS_JSON_URL` (lines ~127-134)
- filters the Nix CPython out of `$GITHUB_PATH` so `uv sync` rebuilds a manylinux
  CPython (lines ~119-125)

On a repo with no Python (e.g. `commit-action`, a TypeScript action) these run
anyway.

### Impact

Harmless today — the vars are unused when CI runs `just sync` (= `npm ci`) — but
it is Python-assuming plumbing baked into the shared, language-neutral CI
toolchain. Confusing to read, and a latent footgun (the deliberate PATH filtering
of CPython could surprise a consumer that legitimately wants the Nix python).

### Suggested fix

Gate the uv/python env on the project actually being Python (presence of
`pyproject.toml`, or a `python` entry in `DEVKIT_MODULES`), so the composite is a
no-op for non-Python consumers.

### Related

Pilot #32; node module #1027. Non-blocking.

---

# [Comment #1]() by [c-vigo]()

_Posted on July 14, 2026 at 08:26 AM_

Fixed in #1033 (merged to dev): python/uv env in setup-devkit-toolchain is now gated on a root pyproject.toml — the composite is a no-op for those steps on non-Python consumers.

