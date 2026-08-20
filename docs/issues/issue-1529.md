---
type: issue
state: closed
created: 2026-08-17T07:18:17Z
updated: 2026-08-17T09:02:43Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1529
comments: 2
labels: bug, priority:high, area:workspace, effort:small, semver:patch
assignees: none
milestone: 1.11.0
projects: none
parent: none
children: none
synced: 2026-08-18T03:02:15.912Z
---

# [Issue 1529]: [[BUG] Generated scaffold content must lint under the stock .typos.toml seed — 'mis-parse' breaks upgrades for pre-#1488 consumers](https://github.com/vig-os/devkit/issues/1529)

## Description

Devkit 1.10.0 renders a comment into the consumer's **managed**
`.github/workflows/release-core.yml` that only passes `typos` under devkit's
**own** `.typos.toml`. Every pre-existing consumer whose seeded `.typos.toml`
predates #1488 fails its `devkit-upgrade` run at the commit step.

`assets/init-workspace.sh:1791` (from `110049e8`, first shipped in 1.10.0)
emits, inside the `DEVKIT_SYNC_TARGET` mirror-fold block (#1424):

```
# renames as "R old -> new", both of which mis-parse. The tr has to
```

`mis` is only spell-clean because #1488 added `mis = "mis"` to devkit's own
`.typos.toml` (for the vendored guardrails gates) **and** to the seed at
`assets/workspace/.typos.toml`. But that file ships with the banner
*"yours to edit; upgrades never overwrite this file"* — so a consumer seeded
before #1488 never receives the entry, and the generated content it now
receives is unlintable against its own config.

Devkit CI cannot catch this: it lints itself, where the word is allowlisted.

## Steps to Reproduce

1. Take a consumer scaffolded before #1488 (its `.typos.toml` has no `mis`)
   with `DEVKIT_SYNC_TARGET` set to a mirror branch.
2. Run `devkit-upgrade.yml` (schedule or dispatch) targeting 1.10.0.
3. The scaffold applies; the in-shell commit is rejected by the `typos` hook.

Live failure: https://github.com/vig-os/org-config/actions/runs/32002045870

```
error: `mis` should be `miss`, `mist`
  .github/workflows/release-core.yml:641:54
```

## Expected Behavior

Content devkit **generates** into a consumer repo is clean under the **stock**
seed `.typos.toml`, not under devkit's extended one. A consumer must never need
to hand-edit a seeded, never-overwritten file to make a managed file lint.

## Actual Behavior

The upgrade fails at "Commit the upgrade in the project shell" and leaves
nothing behind — no branch (the ref is only created in the later Publish step),
no PR, no issue. The pin stays behind and the scheduled run re-fails weekly.
See the companion issue on failure reporting.

## Blast radius

Only `vig-os/org-config` today: the offending comment lives in the
conditionally-rendered mirror-fold block, and org-config is the sole repo with a
non-empty `DEVKIT_SYNC_TARGET`. `commit-action` (#145) and `sync-issues-action`
(#184) adopted 1.10.0 cleanly on 2026-08-17 despite also lacking `mis` in their
seeds. The other two #1488 words (`tatus`, `fnd`) are safe — they appear only in
`assets/guardrails/`, which reaches consumers through the nix store, not the
worktree.

## Proposed fix

1. Reword the generated comment to avoid the token — e.g. "both of which parse
   incorrectly". Cheapest correct fix; no consumer action needed.
2. Add a guard so the class cannot recur: lint the **rendered** scaffold output
   against the stock `assets/workspace/.typos.toml`, not devkit's repo config.
   Any word devkit's own config needs that a consumer's seed lacks is a bug in
   the generated content, not in the consumer.
3. Consider whether a word #1488 added for *devkit's own* vendored assets
   belongs in the consumer seed at all — the seed and the repo config are
   serving two different audiences and drifted together by accident.

## Workaround for affected consumers

Add `mis = "mis"` to the repo's own `.typos.toml` and re-dispatch the upgrade.

---

# [Comment #1]() by [c-vigo]()

_Posted on August 17, 2026 at 07:18 AM_

Related: #1530 (the failure left no artifact at all — no branch, no PR, no issue), #1531 (the render path this shipped through is untested).

---

# [Comment #2]() by [c-vigo]()

_Posted on August 17, 2026 at 09:02 AM_

Fixed in #1533 (merged to dev): generated comment reworded to "parse wrong"; the render is now pinned typos-clean with no allowlist at all by tests/bats/release-mirror-fold-lint.bats. Ships to consumers with 1.11.0. Point 3 of the issue (whether #1488's vendored-asset words belong in the consumer seed) remains open as a design question — not addressed here.

