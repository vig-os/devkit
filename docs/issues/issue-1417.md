---
type: issue
state: closed
created: 2026-08-11T09:26:53Z
updated: 2026-08-11T09:56:29Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1417
comments: 1
labels: chore, area:testing
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-08-12T04:13:06.970Z
---

# [Issue 1417]: [[CHORE] Test-suite runtime: shared scaffold fixtures and consolidated nix invocations](https://github.com/vig-os/devkit/issues/1417)

## Description

WP5 of #1413 (deferred there as runtime-only): the suite's dominant wall-clock costs are repeated `init-workspace.sh` scaffold runs and per-test `nix develop`/`nix build` launches that share identical inputs. Consolidate them behind shared fixtures without changing any assertion.

- **Session-scoped scaffold trees**: add cached `gitflow_tree`/`trunk_tree` fixtures to `tests/workflow_scaffold.py` and migrate all read-only workflow-shape assertions onto them (~30 of ~55 scaffold call-sites collapse to 2 runs — heaviest in `test_workflow_model.py` and `test_sync_settings.py`). Per-test scaffolds stay for mutating cases (upgrades, seeds, hostile-input guards).
- **Bats per-mode scaffolds**: `setup_file`-scoped scaffolds for `init-workspace.bats`' read-only per-mode assertion groups (~20 scaffold runs → 4).
- **`tests/test_flake_devshell.py`**: replace the per-tool `nix develop` loop in `test_each_tool_runs_in_devshell` with one entry running a generated script over all devTools (~30 launches → 1, per-tool failure attribution preserved); merge the python3/console-scripts PATH probes into one `--ignore-environment` entry and fix the stale `test_devshell_exposes_python3_and_precommit` name — **the `-k` selection in `.github/workflows/ci.yml` references that name and must be updated in the same commit**.
- **`tests/test_setup_toolchain_env.py`**: one module-scoped run of the step script for the ~31 byte-identical default invocations (parametrized cases stay as assertions against the shared result).
- **`tests/test_flake_hooks.py`**: build the three consumer-config fixtures (`consumer_config`, `gitleaks_enabled_config`, `trunk_consumer_config`) in a single derivation set.

## Acceptance Criteria

- [ ] No assertion removed or weakened; test counts unchanged except where probes merge (failure attribution preserved).
- [ ] Scaffold subprocess runs in the workflow-shape suite drop from ~55 to ~25; the devshell per-tool sweep runs one `nix develop` entry.
- [ ] `ci.yml` `-k` selection updated in lockstep with any test rename; the Project Checks lane stays green.
- [ ] Full local runs green: workflow-shape sweep, `test_flake_devshell.py`, `test_flake_hooks.py`, `test_setup_toolchain_env.py`, `bats tests/bats/init-workspace.bats`.

## Related Issues

Refs: #1413 (WP5 checklist)

## Changelog Category

No changelog needed

---

# [Comment #1]() by [c-vigo]()

_Posted on August 11, 2026 at 09:56 AM_

Implemented in PR #1420 (merged to dev @9e0af0d4): cached read-only gitflow/trunk scaffold trees in workflow_scaffold.py (~40 → 20 sweep scaffold runs), setup_file-shared per-mode trees in init-workspace.bats (19 → 4), single-entry dev-shell tool sweep (~29 nix develop launches → 1, per-tool attribution kept) with the ci.yml -k selection updated in lockstep, module-scoped toolchain-step run (file now 0.36 s), and the three hooks consumer-config builds folded into one linkFarm derivation. Shape sweep 27 s → ~17 s locally; test counts unchanged (897 passed).

