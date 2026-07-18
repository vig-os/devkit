---
type: issue
state: closed
created: 2026-07-17T12:03:43Z
updated: 2026-07-17T13:00:23Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1181
comments: 1
labels: bug, priority:high, area:ci, effort:small, semver:minor
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-07-18T04:54:25.267Z
---

# [Issue 1181]: [direnv-mode CI: uvx tools with native wheels fail (nix CPython cannot load system libs)](https://github.com/vig-os/devkit/issues/1181)

## Description
On non-Python repos the CI preamble keeps the nix CPython on PATH (the manylinux exclusion of #1028 applies only when `pyproject.toml` exists). `uvx`-run tools resolving that interpreter then fail to load manylinux native wheels because the nix loader does not search `/usr/lib` — the same class for which devkit dropped its own pymarkdown hook (pyjson5).

## Evidence (org-config)
- vig-os/org-config#40: `otterdog` (native `rjsonnet`) → `libstdc++.so.6: cannot open shared object file` on ubuntu-24.04 host runner (run 29577969319); local dev-shell fine.
- Proven fix (org-config@f01175a): command-scoped `LD_LIBRARY_PATH` derived at run time via `cc -print-file-name=libstdc++.so.6` — the `cc` wrapper IS on the preamble-forwarded PATH, and the CI-faithful simulation (`env -i PATH=<store bins>`) reproduces both the failure and the fix.

## Suggested direction
Ship the pattern as a base justfile helper (or preamble export), so consumers running uv tools with native extensions don't rediscover it — it would likely also let the dropped pymarkdown hook return.

Refs: vig-os/org-config#17
---

# [Comment #1]() by [c-vigo]()

_Posted on July 17, 2026 at 01:00 PM_

Fixed on dev via PR #1184 (merge @8bee1891): the root justfile ships a command-scoped `with-native-libs +command` helper deriving LD_LIBRARY_PATH from $VIGOS_STDCPP_LIB or the on-PATH cc wrapper (org-config@f01175a pattern), no-op when unresolvable and never emitting empty path entries. Documented in docs/NIX.md. Ships with the next devkit release.

