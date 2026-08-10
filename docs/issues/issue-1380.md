---
type: issue
state: closed
created: 2026-08-07T16:21:11Z
updated: 2026-08-07T16:46:54Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1380
comments: 1
labels: bug, priority:medium, effort:small, area:testing, semver:patch
assignees: none
milestone: 1.7.0
projects: none
parent: none
children: none
synced: 2026-08-07T21:30:57.544Z
---

# [Issue 1380]: [[BUG] nix/hooks.nix pymarkdown excludes still reference CONTRIBUTE.md after the CONTRIBUTING.md rename](https://github.com/vig-os/devkit/issues/1380)

## Summary

PR #1376 (#1372) renamed `CONTRIBUTE.md` to `CONTRIBUTING.md` and updated the
pymarkdown `exclude` in `.pre-commit-config.yaml`, but missed the flake-side
mirror in `nix/hooks.nix`. The two sources of the hook config have drifted:

```console
$ git grep -n "CONTRIBUT" origin/dev -- nix/hooks.nix .pre-commit-config.yaml
.pre-commit-config.yaml:129:        exclude: ^(README\.md|CONTRIBUTING\.md|TESTING\.md)
nix/hooks.nix:436:    # `.pymarkdown` JSON config and README/CONTRIBUTE/TESTING excludes.
nix/hooks.nix:457:        exclude = "^(README\\.md|CONTRIBUTE\\.md|TESTING\\.md)";
nix/hooks.nix:467:          excludes = [ "^(README\\.md|CONTRIBUTE\\.md|TESTING\\.md)" ];
nix/hooks.nix:475:          excludes = [ "^(README\\.md|CONTRIBUTE\\.md|TESTING\\.md)" ];
```

## Observed impact

- `tests/test_flake_hooks.py::test_runner_render_matches_committed_config` FAILS
  on a plain `uv run pytest tests` run from origin/dev — the flake-rendered
  config no longer matches the committed `.pre-commit-config.yaml`.
- Dev CI stayed green only because the `test-project` job deny-lists that test
  file, so the drift gate never ran on PR #1376.
- Functionally, the flake-generated hook set no longer excludes the (renamed)
  contributing guide from pymarkdown, and still excludes a file that no longer
  exists.

## Fix

Update the three exclude patterns (and the line-436 comment) in
`nix/hooks.nix` from `CONTRIBUTE` to `CONTRIBUTING`, and confirm
`test_runner_render_matches_committed_config` passes again.

## Related

Fallout from #1372 / PR #1376. Surfaced while validating #1377 (PR #1379).

Refs: #1372
---

# [Comment #1]() by [c-vigo]()

_Posted on August 7, 2026 at 04:46 PM_

Fixed on dev by PR #1383: the three pymarkdown exclude patterns (and the comment) in nix/hooks.nix now reference CONTRIBUTING.md, plus the same stale exclude in the scaffold template assets/workspace/.pre-commit-config.yaml (necessary addition — the sibling scaffold drift gate failed without it, same #1372 rename fallout). Pinned by the pre-existing drift-gate tests: test_runner_render_matches_committed_config red before, all 36 flake-hook tests green after. Remaining cosmetic loose end: a prose comment at flake.nix:1358 still mentions CONTRIBUTE.md — can ride any future PR.

