---
type: issue
state: closed
created: 2026-07-28T13:26:58Z
updated: 2026-07-29T13:07:54Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1282
comments: 1
labels: feature, priority:low, area:workspace, effort:medium, semver:minor
assignees: none
milestone: Backlog
projects: none
parent: none
children: none
synced: 2026-07-30T05:15:35.661Z
---

# [Issue 1282]: [feat(workspace): scaffold-time Refs policy knob (DEVKIT_REFS_POLICY) for validate-commit-msg + validate-commit-range](https://github.com/vig-os/devkit/issues/1282)

### Description

A `.vig-os` manifest key (e.g. `DEVKIT_REFS_POLICY`) that renders the `Refs: #N` requirement policy into **both** enforcement points at scaffold time — the `validate-commit-msg` hook args in `.pre-commit-config.yaml` and CI's `validate-commit-range` — instead of hardcoding `--refs-optional-types chore`.

### Problem Statement

Solo/private consumers without an issue-driven workflow (personal repos, data repos) want `Refs:` optional for **all** commit types while keeping type/format validation. Today the only route is editing the preserved `.pre-commit-config.yaml`, which has two costs:

1. **Permanent template drift** — the upgrade path prints the preserved-file diff against the template on every re-scaffold, forever, for a deliberate policy choice.
2. **CI desync** — `validate-commit-range` enforces its own copy of the policy, so the local hook and the CI gate silently disagree (this consistency has already broken once, #1074).

### Proposed Solution

- New `.vig-os` key `DEVKIT_REFS_POLICY` with values `chore-optional` (default — today's behavior), `optional` (Refs never required), and optionally `required` (strict, no exemptions).
- Rendered via the existing `{{TOKEN}}` substitution into the scaffolded hook args; the CI side either reads the manifest (the `resolve-toolchain` composite already parses `.vig-os`) or receives the same substitution.
- Round-trip the key across `--force` upgrades like `DEVKIT_TAG_PREFIX`/`DEVKIT_FLOATING_TAGS` (#1116 pattern).

#### Acceptance criteria

- [ ] Key documented in the `docs/MIGRATION.md` manifest table
- [ ] Hook and `validate-commit-range` agree in all modes/policies (single source of truth)
- [ ] Default (absent key) produces a byte-identical scaffold to today
- [ ] bats coverage incl. manifest round-trip

### Alternatives Considered

- **Edit the preserved `.pre-commit-config.yaml`** — works, but permanent drift nag + CI desync (see above).
- **Disable the commit-msg hooks entirely** — throws away type/format validation, which solo repos still want.

### Additional Context

#885 (manifest as the per-consumer config surface), #1074 (hook/CI policy desync precedent), #1173 (`DEVKIT_CI_RUNNER` — precedent for a consumer knob consumed by CI). Surfaced while evaluating devkit adoption for a private single-user repo whose history is legitimately `chore`-dominant but occasionally needs `fix`/`refactor` without an issue tracker.

### Impact

- Benefits solo/private consumers and any org repo with a non-issue-driven workflow.
- Backward compatible (`semver:minor`); default behavior unchanged.

---

# [Comment #1]() by [c-vigo]()

_Posted on July 29, 2026 at 01:07 PM_

Merged to dev via #1292 (dev-targeted PRs do not auto-close). Ships with the next release.

