---
type: issue
state: closed
created: 2026-09-28T21:38:59Z
updated: 2026-09-29T13:07:30Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1755
comments: 1
labels: none
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-09-30T08:17:48.738Z
---

# [Issue 1755]: [ci.yml branch-name gate allows renovate/* but not dependabot/** — every Dependabot PR fails commit-checks](https://github.com/vig-os/devkit/issues/1755)

## Symptom

In a consumer that uses **Dependabot** rather than Renovate for version updates, every bot PR fails
the `Commit Messages` job at the **`Validate branch name`** step — before the commit-message
validator ever runs:

```
##[error]Branch name 'dependabot/github_actions/dev/actions-minor-patch-64e3431685' does not follow
the convention <type>/<issue>-<summary> (types: feature,bugfix,hotfix,release,docs,test,refactor)
or chore/<summary>.
```

Seen on vig-os/tessera#443 and #444 (run [36385374324](https://github.com/vig-os/tessera/actions/runs/36385374324)).
Every other check on those PRs passes.

## Cause

The allowlist in the scaffolded `ci.yml` (`assets/workspace/.github/workflows/ci.yml`, the
`Validate branch name` step) has a clause for Renovate's namespace but none for Dependabot's:

```bash
ALLOWED="^(main|dev)$"
ALLOWED+="|^chore/[a-z0-9]+(-[a-z0-9]+)*$"
ALLOWED+="|^(${TYPES_ALTERNATION})/[0-9]+-[a-z0-9]+(-[a-z0-9]+)*$"
ALLOWED+="|^worktree/[0-9]+$"
ALLOWED+="|^renovate/.+$"          # <-- Renovate is covered
ALLOWED+="|^release/[0-9]+\.[0-9]+\.[0-9]+$"
```

Dependabot's branch prefix is not configurable. `pull-request-branch-name.separator` only changes
the separator, so a consumer cannot rename its way into the existing pattern — the names are always
`dependabot/<ecosystem>/<target-branch>/<dep>-<version>`.

This looks like it was simply never hit: devkit itself uses Renovate, so its own bot PRs match.

## Why the neighbouring knobs do not help

Worth stating, since they look like the natural escape hatches and are not:

- `DEVKIT_BRANCH_TYPES` adds to the `<type>/<issue>-<summary>` clause, which needs a numeric issue
  segment. `dependabot/github_actions/dev/...` cannot match it.
- `DEVKIT_REFS_OPTIONAL_TYPES` / `DEVKIT_REFS_POLICY` are about the `Refs:` line, which is already
  handled correctly — `validate_commit_range.py` exempts `…[bot]` authors via `BOT_AUTHOR_SUFFIX`,
  and `validate_title` marks every approved type Refs-optional. The failure is strictly the branch
  name.
- `DEVKIT_DRIFT_CHECK=false` lets a consumer hand-patch `ci.yml` without failing the drift gate, but
  `devkit-upgrade.yml` regenerates the file, so the patch is lost on the next upgrade. The only
  preservation seam is `DEVKIT_UPGRADE_EXCLUDE`, and listing `ci.yml` there freezes the whole
  workflow — giving up every future CI improvement to keep a one-line clause.

## Suggested fix

Add a Dependabot clause next to the Renovate one:

```bash
ALLOWED+="|^dependabot/.+$"
```

It is as safe as the existing `renovate/.+` clause: both namespaces are created only by the
respective bot, and neither can be pushed by a human without repo write access.

While there: the same step should cover the **devkit-upgrade bot's own** branch namespace if it ever
moves off `chore/<slug>` (today `chore/devkit-1-17-0` matches, so it is fine).

If a hardcoded clause is unwanted, a `DEVKIT_BOT_BRANCH_PATTERNS`-style key (comma-separated extra
anchored patterns, defaulting to today's behaviour) would let a consumer declare its own bot
namespaces without forking `ci.yml`.

Filed from vig-os/tessera, which is patching `ci.yml` locally in the meantime and will drop the patch
once this lands.
---

# [Comment #1]() by [c-vigo]()

_Posted on September 29, 2026 at 01:07 PM_

Superseded: vig-os moved vulnerability-fix and version-update PRs to Renovate (vig-os/org-config#307, #310; #1763/#1764). Dependabot security updates are off org-wide except qx, which is not devkit-managed. tessera, the only repo using Dependabot for version updates, removed its dependabot.yml (vig-os/tessera#512). No org repo opens dependabot/* PRs into devkit's managed gate anymore.

