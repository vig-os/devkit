---
type: issue
state: closed
created: 2026-08-12T05:15:17Z
updated: 2026-08-12T05:53:34Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1433
comments: 1
labels: feature, priority:medium, area:workspace, effort:small, semver:minor
assignees: none
milestone: 1.8.0
projects: none
parent: none
children: none
synced: 2026-08-12T13:33:42.597Z
---

# [Issue 1433]: [[FEATURE] feat(hooks): allow renovate/* branches in the default no-commit-to-branch guard](https://github.com/vig-os/devkit/issues/1433)

### Description

Add a `(?!^renovate/.+$)` allowance clause to the default `no-commit-to-branch` pattern (all three renders: committed runner YAML, scaffold template YAML, flake consumer surface — one definition in `nix/hooks.nix`), so local commits on Renovate's branches are not blocked.

### Problem Statement

The Renovate app itself commits server-side, where local hooks never run — so the guard doesn't affect the bot. But **maintainer fix-up commits on `renovate/*` branches are a real, recurring flow**: conflict resolution against the shared changelog `## Unreleased` block, `dist/` rebuilds in npm action repos, and lock-file merges during batch weeks. The 2026-07-25 renovate batch (17 PRs across devkit + sync-issues-action + commit-action) hit this exact wall, and the standing workaround is awkward and error-prone: commit on a compliant `chore/…` branch, then `git push origin HEAD:renovate/…`.

Renovate branch names can never satisfy `DEVKIT_BRANCH_TYPES` (#1432): they carry no issue number and use a charset outside the slug rule — live examples in this repo include `renovate/github-actions-(minor-and-patch)` and `renovate/lock-file-maintenance`. Hence a dedicated default clause rather than a knob value.

### Proposed Solution

- `nix/hooks.nix`: add the `renovate/` lookahead to `branchNamePatternFor` (next to the `worktree/[0-9]+` clause — same rationale: a tool-owned branch namespace). Permissive `.+` after the prefix: Renovate composes names from dep names/version ranges, so pinning a charset would re-break on the next scheme.
- Regenerate both rendered YAMLs (drift-gated by tests/test_flake_hooks.py); update the pattern comment block.
- bats/pytest: `renovate/foo-1.x` and `renovate/github-actions-(minor-and-patch)` allowed; `renovated/x` (prefix confusion) still blocked.

### Alternatives Considered

- **Keep the push-to-ref workaround** — documented friction, defeats the guard's purpose (it blocks the compliant flow, not a mistake).
- **Express via DEVKIT_BRANCH_TYPES** — impossible; wrong shape and charset (see above).

### Additional Context

Surfaced while planning #1432 (exo-pet/vault#54 option B). Renovate is devkit-scaffolded standard equipment (`renovate.json` is a managed file), so the allowance belongs in the default for every consumer.

### Impact

Backward compatible (purely additive allowance; a branch allowed by today's pattern stays allowed). Default renders change byte-wise — intended, covered by the drift gate regen.
---

# [Comment #1]() by [c-vigo]()

_Posted on August 12, 2026 at 05:53 AM_

Merged to dev via #1435 (dev-targeted PRs do not auto-close). Ships with 1.7.1.

