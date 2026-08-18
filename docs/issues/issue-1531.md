---
type: issue
state: closed
created: 2026-08-17T07:18:30Z
updated: 2026-08-17T09:02:45Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1531
comments: 2
labels: chore, priority:medium, effort:medium, area:testing, semver:patch
assignees: none
milestone: 1.11.0
projects: none
parent: none
children: none
synced: 2026-08-18T03:02:14.796Z
---

# [Issue 1531]: [[CHORE] Smoke-test the DEVKIT_SYNC_TARGET mirror-fold render against a stock seed](https://github.com/vig-os/devkit/issues/1531)

## Description

The `DEVKIT_SYNC_TARGET` mirror-fold render (#1424) — the block
`assets/init-workspace.sh` injects into `release-core.yml` when a consumer sets
a mirror branch — is **never exercised by any test or smoke run**. It has
exactly one consumer in the org (`vig-os/org-config`), and it is that consumer's
scheduled upgrade that discovers regressions, in production, a weekend after the
release ships.

That is how the 1.10.0 typos regression reached a consumer untouched: the
offending comment lives inside this conditional block, so `devkit-smoke-test`,
`commit-action` and `sync-issues-action` all adopted 1.10.0 green while
`org-config` failed. See the companion bug for the failure itself.

## What to cover

1. **Render the block at all.** A scaffold run with `DEVKIT_SYNC_TARGET` set to
   a mirror branch, asserting the fold steps land in `release-core.yml` and the
   `target-branch=` rewrite applied.
2. **Lint the render against a stock seed.** Run the generated tree through the
   hooks with an unmodified `assets/workspace/.typos.toml` — the combination
   that nobody ran. Generated content must be clean under the seed a consumer
   actually has, not under devkit's own repo config.
3. **Both workflow models.** The block interacts with the release branch and,
   for trunk repos, with the absence of `sync-main-to-dev` backflow; the
   rendered YAML should at minimum parse and pass `actionlint` in both.

## Where

Natural home is `devkit-smoke-test` (it already validates releases via
`repository_dispatch`), either as a second scaffold matrix leg with the manifest
key set, or as a scaffold-render unit test in devkit itself if a full smoke leg
is too heavy. The cheap 80% is (2): lint the rendered output against the stock
seed as part of the existing scaffold checks.

## Rationale

Any conditionally-rendered scaffold path with a single consumer is effectively
untested by construction. The manifest knobs that gate renders
(`DEVKIT_SYNC_TARGET`, and by the same argument `DEVKIT_FEATURES_DISABLED`,
`DEVKIT_WORKFLOW`, `DEVKIT_REFS_POLICY`) each carve out a render variant that
the default-path smoke run cannot see. Worth deciding whether this issue covers
just the mirror-fold leg or establishes the pattern for all of them.

---

# [Comment #1]() by [c-vigo]()

_Posted on August 17, 2026 at 07:18 AM_

Triggered by #1529 — the regression shipped through this untested render path. See also #1530.

---

# [Comment #2]() by [c-vigo]()

_Posted on August 17, 2026 at 09:02 AM_

Done in #1533 (merged to dev): tests/bats/release-mirror-fold-lint.bats renders a full mirror-mode workspace in both workflow models and lints each tree with typos --isolated (no allowlist — stricter than a stock seed, since real consumer seeds are frozen at scaffold time) and actionlint (first coverage of the fold-injected steps/job). Fixture preconditions assert the fold rendered, so the lints cannot pass vacuously. The broader question of guarding the other conditionally-rendered knobs (DEVKIT_FEATURES_DISABLED, DEVKIT_WORKFLOW, DEVKIT_REFS_POLICY) is not covered — file separately if wanted.

