---
type: issue
state: closed
created: 2026-07-14T09:05:22Z
updated: 2026-07-14T09:39:49Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1047
comments: 1
labels: bug, priority:medium, area:workspace, effort:small, semver:patch
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-07-14T20:06:28.322Z
---

# [Issue 1047]: [[BUG] Renovate preset does not group npm updates — one PR per package, all mutually conflicting](https://github.com/vig-os/devkit/issues/1047)

## Description

The scaffolded Renovate preset (`assets/workspace/.github/renovate-default.json`)
groups minor/patch updates for **`github-actions`** and **`pep621`**, but the
**`npm`** rule sets only `semanticCommitType` / `semanticCommitScope` and **no
`groupName`**:

```jsonc
{
  "description": "GitHub Actions — semantic commit + group minor/patch",
  "matchManagers": ["github-actions"],
  "matchUpdateTypes": ["minor", "patch"],
  "groupName": "github-actions (minor and patch)",   // ← grouped
  ...
},
{
  "description": "Python — group minor/patch",
  "matchManagers": ["pep621"],
  "matchUpdateTypes": ["minor", "patch"],
  "groupName": "python (minor and patch)"            // ← grouped
},
{
  "description": "npm",
  "matchManagers": ["npm"],
  "semanticCommitType": "build",
  "semanticCommitScope": "npm"                       // ← no groupName: fans out
}
```

So npm consumers get **one PR per package**. Because every such PR touches both
`package-lock.json` and `CHANGELOG.md` (the latter via the scaffolded
`renovate-changelog-*` workflows), the PRs conflict **pairwise** — and with the
base branch as soon as any one of them merges.

The result is not just noise: the set is effectively unlandable serially without
N rounds of rebase → regenerate lockfile → re-run CI → merge, where each merge
re-dirties the rest.

## Steps to Reproduce

`vig-os/commit-action`, first Renovate run after devkit 1.1.0 adoption:

1. Renovate opens **11 npm PRs** (`#44`–`#56`), one per package.
2. One security PR (`#41`, `undici`) merges.
3. Every remaining PR immediately goes `CONFLICTING / DIRTY`:

```console
$ gh pr view 45 --json mergeable,mergeStateStatus
#45 CONFLICTING/DIRTY   #46 CONFLICTING/DIRTY
#47 CONFLICTING/DIRTY   #48 CONFLICTING/DIRTY   ...
```

Because all of them touch the same two files:

```console
$ gh pr view 45 --json files --jq '[.files[].path]|join(" ")'
CHANGELOG.md package-lock.json
$ gh pr view 46 --json files --jq '[.files[].path]|join(" ")'
CHANGELOG.md package-lock.json package.json
```

## Expected Behavior

Routine npm dev-dependency updates arrive as **one grouped PR** (as they already
do for `github-actions` and `pep621`), so they land in a single lockfile
regeneration and a single CI run.

## Actual Behavior

Six mutually-conflicting PRs for six dev-dependency bumps. Landing them required
abandoning the Renovate PRs entirely and hand-building a batch branch
(`vig-os/commit-action#57`), regenerating `package-lock.json` once — because
resolving a `package-lock.json` conflict six times by hand is not viable.

## Environment

- **Consumer**: `vig-os/commit-action` (devkit 1.1.0, `DEVKIT_MODE=direnv`)
- **Preset**: `assets/workspace/.github/renovate-default.json`, copied into
  consumers **verbatim**
- **Affected**: every scaffolded repo with an npm manager — `commit-action`,
  `sync-issues-action`, and devkit itself

## Possible Solution

Give npm the same grouping treatment the other two managers already get:

```diff
   {
     "description": "npm",
     "matchManagers": ["npm"],
     "semanticCommitType": "build",
     "semanticCommitScope": "npm"
+  },
+  {
+    "description": "npm — group dev dependencies (they never ship in the bundle)",
+    "matchManagers": ["npm"],
+    "matchDepTypes": ["devDependencies"],
+    "groupName": "npm dev dependencies"
+  },
+  {
+    "description": "npm — group runtime minor/patch; majors stay separate",
+    "matchManagers": ["npm"],
+    "matchDepTypes": ["dependencies"],
+    "matchUpdateTypes": ["minor", "patch"],
+    "groupName": "npm (minor and patch)"
   },
```

Rationale for the split: **dev** dependencies never reach the shipped artifact, so
grouping them across update types (including majors) is low-risk and is exactly the
case that blew up here. **Runtime** deps should keep majors separate, since those
are the ones that can break the bundle — in `commit-action`, the `@actions/*` v-next
majors turned out to be ESM-only and genuinely unlandable, and it was useful to have
them as individual PRs.

Worth pairing with a `schedule` note: grouped PRs also cut the CI cost of a Monday
batch from N runs to one.

## Related

- vig-os/devkit#1041 — transitive npm vulns unreported. **Same file**, same rollout
  pilot; if both are fixed, do them in one PR against the preset.
- `vig-os/commit-action#57` — the hand-built batch branch this gap forced.

---

# [Comment #1]() by [c-vigo]()

_Posted on July 14, 2026 at 09:39 AM_

Fixed in #1049 (merged to dev): npm devDependencies grouped across all update types; runtime dependencies grouped for minor/patch with majors kept individual; the build(npm) semantic-commit rule still applies to every npm PR. Interim lockFileMaintenance for #1041 shipped in the same PR — that issue stays open tracking upstream renovatebot/renovate#41825.

