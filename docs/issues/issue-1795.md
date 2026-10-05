---
type: issue
state: closed
created: 2026-10-01T12:57:23Z
updated: 2026-10-01T13:50:25Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1795
comments: 1
labels: none
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-10-02T08:18:23.409Z
---

# [Issue 1795]: [sync-issues.yml: the sync job ignores DEVKIT_CI_RUNNER and always runs hosted](https://github.com/vig-os/devkit/issues/1795)

`sync-issues.yml`'s `sync` job is hardcoded to the hosted default and ignores
`DEVKIT_CI_RUNNER`, so consumers with their own runners still pay for it.

## The gap

`ci.yml` resolves the runner once and every downstream job honours it:

```yaml
runs-on: ${{ fromJSON(needs.resolve-toolchain.outputs.runner-json) }}
```

`sync-issues.yml` does not. Its `resolve-toolchain` job (`:44-70`) never adds
`runner-json` to its `outputs:` block, and the `sync` job is pinned directly:

```yaml
# assets/workspace/.github/workflows/sync-issues.yml:74
runs-on: ubuntu-26.04
```

So a repo that sets `DEVKIT_CI_RUNNER=self-hosted,...` gets self-hosted CI but
still runs this workflow's real work on a paid hosted runner. The key is
honoured in `ci.yml` and silently dropped here.

## Why it matters more than it looks

The workflow is on a **daily cron** (`:15`), so the cost is incurred per repo
per day regardless of activity — unlike `ci.yml`, which at least scales with PR
volume. Measured across five private consumer repos over one week, the `sync`
job accounted for ~53 billed minutes that the consumers' own runners would have
absorbed for free. On private repos GitHub bills each job rounded **up** to a
whole minute, so short jobs are disproportionately expensive.

## Proposed change

1. Add `runner-json: ${{ steps.resolve.outputs.runner-json }}` to
   `resolve-toolchain`'s `outputs:` in `sync-issues.yml`.
2. Change the `sync` job's `runs-on:` to the same `fromJSON(...)` expression
   `ci.yml` uses.

The `sync` job already calls `./.github/actions/setup-devkit-toolchain` (`:107`),
so it brings its own `gh`/`python3` closure and needs nothing from the runner
image beyond `nix`. No change to the resolve job's own runner (see the separate
issue for that).

`resolve-toolchain` stays on the hosted default here, consistent with #1173.

## Check while in there

`sync-main-to-dev.yml` (`:52-54`) has the same shape and fires on every push to
the default branch; the dispatch-only release workflows
(`abandon-release.yml`, `prepare-hotfix.yml`, `promote-release.yml`,
`release.yml`) also declare a hosted `resolve-toolchain` but are low frequency.
Worth confirming whether any of their non-resolve jobs are similarly pinned.

---

# [Comment #1]() by [c-vigo]()

_Posted on October 1, 2026 at 01:50 PM_

Landed in #1798 (merge commit 109231a77) on `dev`.

Not auto-closed because this repo runs gitflow: `Closes #…` only fires on a merge to the default branch (`main`), and the change reaches `main` at the next release via the normal release train.

Consumers pick it up through `devkit-upgrade.yml` once released — staggered per repo on its weekly cron, or immediately by dispatching that workflow. A repo with `DEVKIT_AUTO_UPGRADE=false` needs a manual dispatch.

The out-of-scope findings recorded in #1798 (other managed workflows with non-resolve jobs pinned to a hosted literal, `sync-main-to-dev.yml` most notably) are not covered here and still want a follow-up issue.

