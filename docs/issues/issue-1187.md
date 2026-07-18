---
type: issue
state: open
created: 2026-07-17T13:49:35Z
updated: 2026-07-17T13:49:35Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1187
comments: 0
labels: bug, priority:blocking, area:ci, area:workspace, effort:small, semver:patch
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-07-18T04:54:24.634Z
---

# [Issue 1187]: [Literal ${{ fromJSON(...) }} doc text breaks resolve-toolchain action manifest](https://github.com/vig-os/devkit/issues/1187)

## Description

1.4.0-rc1 smoke test failed at the very first job: the runner cannot load the managed composite action `assets/workspace/.github/actions/resolve-toolchain/action.yml`.

Failed run: https://github.com/vig-os/devkit-smoke-test/actions/runs/29584889283

```
##[error]./.github/actions/resolve-toolchain/action.yml (Line: 63, Col: 18): Unexpected symbol: '...'. Located at position 10 within expression: fromJSON(...)
##[error]./.github/actions/resolve-toolchain/action.yml (Line: 77, Col: 12): Unexpected symbol: '...'. Located at position 10 within expression: fromJSON(...)
##[error]GitHub.DistributedTask.ObjectTemplating.TemplateValidationException: The template is not valid.
```

## Root cause

The DEVKIT_CI_RUNNER work (#1173) added documentation text containing a **literal** `${{ fromJSON(...) }}` in two scalars that the Actions runner template-evaluates when loading the action manifest:

1. The `runner-json` output `description` (line 65)
2. A bash comment inside the `run:` block of the resolve step (line 149)

There is no escape for `${{` in Actions YAML, so `fromJSON(...)` is parsed as a real expression and the three literal dots are a parse error — the manifest fails to load before any step runs, killing every consumer CI run at "Resolve toolchain".

Repo-wide grep confirms these are the only two occurrences.

## Fix

Rephrase both doc strings without the `${{ }}` wrapper (e.g. "for use with `fromJSON()` in `runs-on`"). Fix goes to `release/1.4.0` per the RC-validation runbook; dev picks it up via sync-main-to-dev.

## Impact

Blocks 1.4.0 (rc1 dead on arrival for every consumer using the managed CI workflow).
