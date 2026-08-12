---
type: issue
state: closed
created: 2026-08-12T11:41:15Z
updated: 2026-08-12T12:17:14Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1466
comments: 1
labels: bug
assignees: none
milestone: 1.8.0
projects: none
parent: none
children: none
synced: 2026-08-12T13:33:34.792Z
---

# [Issue 1466]: [[BUG] Smoke deploy publishes consumer-owned files as deletions — the smoke repo loses its Python project](https://github.com/vig-os/devkit/issues/1466)

### Description

The 1.8.0-rc3 smoke deploy **deleted devkit-smoke-test's own Python project** from the deploy branch. Deploy PR [devkit-smoke-test#359](https://github.com/vig-os/devkit-smoke-test/pull/359) removes:

```
pyproject.toml
uv.lock
src/devcontainer_smoke_test/__init__.py
tests/__init__.py
tests/test_example.py
.hadolint.yaml
.github/actions/resolve-image/action.yml
```

alongside the two genuinely-retired `renovate-changelog-*.yml` workflows (#1423/#1348), which were the only intended deletions.

Two defects compose:

1. **Smoke mode's rsync has no preserve excludes.** `assets/init-workspace.sh:2138` is the only copy branch that does not build `EXCLUDE_ARGS` from `PRESERVE_FILES` — the `else` branch at `:2172` does. So the smoke-mode `rsync --delete` removes every consumer-owned file the template does not ship, including `pyproject.toml`, which is explicitly listed as consumer-owned at `assets/init-workspace.sh:100` (#738).

2. **#1443 removed the accidental shield.** That was previously harmless because `commit-action` builds its tree additively — the on-disk deletions never reached git. #1443's fix publishes `git ls-files --deleted` wholesale (`assets/smoke-test/.github/workflows/repository-dispatch.yml:377`) on the stated assumption that *"in smoke mode the installer's `rsync --delete` + overlay makes the working tree exactly the fresh render, so this set is precisely what the new scaffold no longer ships."* That assumption does not hold: the render never contained the smoke repo's test payload.

The scaffold-drift failure is the second-order effect. With `pyproject.toml` gone from the branch, the drift gate's re-scaffold (which runs in **normal** mode, language detection at `assets/init-workspace.sh:929`) no longer sees a Python repo, so it renders `language: ['actions']` for CodeQL and strips the 166-line Python block from `.gitignore`.

### Steps to Reproduce

1. Dispatch `release.yml` as a candidate so the smoke chain runs (1.8.0-rc3, devkit run [31590939254](https://github.com/vig-os/devkit/actions/runs/31590939254)).
2. Observe the deploy PR opened by the listener in `devkit-smoke-test`.
3. `gh api repos/vig-os/devkit-smoke-test/pulls/<N>/files --jq '.[] | select(.status=="removed") | .filename'` lists the consumer's own `pyproject.toml`, `src/`, `tests/`, `uv.lock`.
4. `Scaffold Drift` fails on the resulting branch; `Wait for deploy PR merge` fails; the whole smoke orchestration aborts.

### Expected Behavior

A smoke deploy publishes deletions **only** for paths the new render genuinely retires. Consumer-owned files listed in `PRESERVE_FILES` — and the smoke repo's own project payload — survive the deploy exactly as they do on the normal consumer upgrade path.

### Actual Behavior

Every tracked file absent from the template is deleted on the deploy branch. The smoke repo loses its Python project, the drift gate rejects the PR, and the RC cannot be validated.

Listener run [31592199981](https://github.com/vig-os/devkit-smoke-test/actions/runs/31592199981): `Wait for deploy PR merge` failure → cleanup, prepare, release, promote all skipped.

### Environment

devkit 1.8.0-rc3 (`ghcr.io/vig-os/devcontainer:1.8.0-rc3`), `release/1.8.0` @ `4c6d57dc`. First RC whose smoke chain reached the deploy stage — rc1 failed earlier (#1443) and rc2's listener predated the #1443 redeploy.

### Additional Context

`Tests` reported SUCCESS on the deploy PR despite the tree having no `pyproject.toml`: the Python `just` recipes no-op without one, so CI was green while testing nothing. Worth a separate issue — it is what let the deletion reach the drift gate unannounced.

### Possible Solution

Fix at the root, in the installer: give the smoke-mode rsync the same `PRESERVE_FILES` exclude list the normal branch builds. Then the working tree is correct, `git ls-files --deleted` narrows to genuinely retired paths on its own, and the drift gate agrees because both modes preserve the same set.

Optionally, as defence in depth, intersect the deletions the dispatch template publishes with `retired_prune_paths()` rather than trusting the working tree.

Note the listener executes from devkit-smoke-test's default branch, so a template change needs a manual redeploy there before the next candidate dispatch — same operational step #1443 called out.

### Changelog Category

Fixed

Refs: #1443, #1423, #1348, #738

---

# [Comment #1]() by [c-vigo]()

_Posted on August 12, 2026 at 12:17 PM_

Fixed on `release/1.8.0` via #1468 (merge `eaa2fb9b`).

The smoke-mode scaffold copy no longer carries `rsync --delete`, so a deploy leaves consumer-owned paths alone; retirement stays the #1348 manifest's job, which the drift gate's normal-mode re-scaffold agrees with by construction.

Live proof is the next candidate's smoke chain.

