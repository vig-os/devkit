---
type: issue
state: closed
created: 2026-09-25T09:29:09Z
updated: 2026-09-25T16:10:54Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1704
comments: 2
labels: chore, priority:low, area:ci, effort:small, semver:patch
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-09-26T07:26:42.602Z
---

# [Issue 1704]: [[CHORE] Shellcheck the run bodies of composite actions](https://github.com/vig-os/devkit/issues/1704)

### Chore Type

CI / Build change

### Description

`actionlint` lints the shell in workflow `run:` steps, and the repo's `actionlint` pre-commit hook is scoped to `.github/workflows/*.ya?ml`. Composite actions under `.github/actions/*/action.yml` are not workflows: `actionlint` refuses the file outright (`unexpected key "runs" for "workflow" section`), so their `run:` bodies get no shellcheck pass at all — not locally, not in CI.

#1692 moved the seven flake-gate step bodies out of `ci.yml` into the `test-project` composite, where they join the prek, BATS, pytest and coverage bodies already there. Every one of those bodies was shellchecked by hand for that PR, but nothing guards them going forward: a shell mistake in a composite step is invisible until it fails on a runner.

### Acceptance Criteria

- [ ] Every `run:` body in `.github/actions/*/action.yml` is shellchecked in pre-commit and in CI (the lint lane)
- [ ] The pre-existing deliberate `SC2086` on `$TEST_ARGS` in `test-project` is either fixed or suppressed inline, so the gate starts green
- [ ] The extraction handles `shell: bash` bodies with `${{ }}` expressions without false positives (neutralise them the way actionlint does, or document the limitation)

### Implementation Notes

- Cheapest: a small script (Python, in `scripts/` or `packages/vig-utils`) that parses each composite's YAML, writes every `run:` body to a temp file with a `#!/usr/bin/env bash` shebang and `${{ … }}` replaced by a placeholder, and runs `shellcheck -x -S warning` over them; wire it as a `language: system` prek hook scoped to `^\.github/actions/.*/action\.ya?ml$`.
- Alternative: `actionlint` has no composite-action mode; do not wait for one.
- `setup-env`, `build-image`, `test-image`, `test-integration` composites are in scope too.

### Related Issues

- Raised by the #1692 review; #1692 moved the bodies

### Priority

Low

### Changelog Category

No changelog needed

---

# [Comment #1]() by [c-vigo]()

_Posted on September 25, 2026 at 01:24 PM_

## Triage 2026-09-25: implement, and widen the scope to the scaffold's composites

Inventory: 44 `run:` bodies across 7 composites, all `shell: bash`, none missing `shell:`. Five are devkit's own (`build-image` 5, `setup-env` 5, `test-image` 5, `test-integration` 8, `test-project` 12) and **two live under `assets/workspace/.github/actions/`** (`resolve-toolchain` 2, `setup-devkit-toolchain` 7) — the composites consumers actually run, equally unlinted, and missed by the issue's `^\.github/actions/` regex.

actionlint's exact shellcheck recipe is reproducible (captured by stubbing its `-shellcheck=`):

```
shellcheck --norc -f json -x --shell bash -e SC1091,SC2194,SC2050,SC2153,SC2154,SC2157,SC2043 -
```

stdin = `set -eo pipefail\n` + body, with each `${{ … }}` replaced by `_` repeated to the same length (column offsets preserved). The `-e` list is precisely the placeholder-induced false-positive set, so mirroring these three facts gives actionlint parity rather than an approximation. With it, **exactly one finding at `-S warning` today**: `test-integration` "Start podman socket", SC2046 on `unix:///run/user/$(id -u)/podman/podman.sock` — fix, don't suppress. The `$TEST_ARGS` SC2086 the description cites is `info` level and does not fire at `-S warning` (19 info/style findings exist; not gated). No tool covers this: actionlint has no composite mode (#245 closed as dup of the dormant #46; 1.7.12 is latest), `action-validator` is schema-only.

**Plan:** a `shellcheck-composite-actions` console script in `packages/vig-utils` (on PATH in every consumer env, store-path resolvable, so it can be scaffolded) + a `nix/hooks.nix` entry with `scaffold = true` and `files = "(^|/)\.github/actions/[^/]+/action\.ya?ml$"` covering both trees; hand-sync the rendered `.pre-commit-config.yaml` and its scaffold mirror (`tests/test_flake_hooks.py` drift-gates it). CI needs no wiring: `project-lint` runs `prek run --all-files`. Pytest fixtures: clean body, planted SC2046, a `${{ }}`-in-`[ … ]` body that must not raise SC2050, `shell: python` skipped, offsets preserved. Consumers pick the hook up on their next `devkit-upgrade` PR.


---

# [Comment #2]() by [c-vigo]()

_Posted on September 25, 2026 at 04:10 PM_

Done in #1718, merged to `dev` (447829c3). The hook is scaffolded; delivery to existing consumers with a preserved `.pre-commit-config.yaml` is tracked in #1717 (insert row on the release that first ships it).

