---
type: issue
state: open
created: 2026-09-28T21:48:15Z
updated: 2026-09-28T22:00:29Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1759
comments: 1
labels: none
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-09-29T08:16:50.306Z
---

# [Issue 1759]: [ci.yml/codeql.yml pull_request base filter excludes stacked PRs — a PR onto a topic branch gets no checks at all](https://github.com/vig-os/devkit/issues/1759)

## Symptom

A stacked PR — one whose base is another topic branch rather than `dev`/`release/**`/`main` — runs
**no** checks. No lint, no tests, no commit-message validation, no `nix flake check`. It stays
completely untested until its base merges and GitHub retargets it onto the trunk.

Seen in vig-os/tessera#463 (PR #461 stacked on #460).

## Cause

The scaffolded `ci.yml` (and `codeql.yml`) filter `pull_request` to an enumerated base list:

```yaml
on:
  pull_request:
    branches:
      - dev
      - 'release/**'
      - main
```

A PR onto `feature/123-foo` matches none of them, so the workflow never triggers. There is no knob:
`grep DEVKIT_CI_ assets/init-workspace.sh` turns up only `DEVKIT_CI_RUNNER`, and nothing renders the
`branches:` list.

The failure mode is quiet in the worst way — the PR does not show a *failing* check, it shows *no*
checks, which reads as "nothing to run" rather than "nothing was verified". Whether a required status
check can be satisfied at all then depends on repo protection settings.

## Why the filter is presumably there

Almost certainly to stop double runs in the era before the concurrency group, and to avoid spending
runner minutes on intermediate refs. The first reason is now handled directly: since #1602 the
workflow has

```yaml
concurrency:
  group: ci-${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: ${{ github.event_name != 'push' }}
```

so a superseded stacked run cancels rather than accumulating. That removes most of the cost argument
for excluding stacked bases.

## Suggested fix

Either widen the default to any base:

```yaml
  pull_request:
    branches:
      - '**'
```

(`**` matches `/`, so it covers `dev`, `release/**` and `main` too; a `pull_request` event matches the
filter once, so this adds no duplicate runs) — or expose the list as a `.vig-os` key, e.g.
`DEVKIT_CI_PR_BASES`, defaulting to today's three entries so existing consumers are unchanged.

Widening seems right as the default: a stacked PR silently receiving zero verification is a worse
failure than spending runner minutes on it, and a consumer that wants the narrow behaviour is the one
with the unusual requirement.

If neither is wanted, the scaffold should at least document `workflow_dispatch` as the stacked-PR
procedure, since that is the only workaround today and it is not discoverable.

## Note on the same filter in `nix-check.yml`

Not devkit-managed in tessera, but consumers are likely to copy the same three-entry list into their
own workflows (tessera did, and that is where its *required* status check lives — so the required
check was exactly the one that could never run on a stacked PR). Worth a line in the scaffold docs
either way.

Filed from vig-os/tessera, which is patching all three workflows locally in the meantime; the two
devkit-managed ones carry a `REMOVE once this lands` comment.
---

# [Comment #1]() by [gerchowl]()

_Posted on September 28, 2026 at 10:00 PM_

One addition found while patching this locally: **widening the trigger needs a concurrency group to
land with it**, and `codeql.yml` does not have one today.

`ci.yml` got its group in #1602, but the scaffolded `codeql.yml` has no `concurrency:` key at all. So
if the base filter is widened as proposed above without also adding a group, a force-push to a stacked
branch leaves the superseded analysis running — which is the runner-waste problem #1602 fixed,
reintroduced through the other workflow.

What worked here, mirroring `ci.yml`'s shape:

```yaml
concurrency:
  group: codeql-${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: ${{ github.event_name != 'push' }}
```

The `!= 'push'` carve-out is worth keeping rather than a bare `true`: the push-to-main leg is
post-merge analysis feeding the security tab, so two merges landing quickly should each report
instead of the first being cancelled.

Consumers likely have the same gap in their own `nix flake check`-style workflows — in tessera that
lane is ~40-60 min per leg across two arch legs, so it is the one where an uncancelled superseded run
actually hurts. Might be worth a line in the scaffold docs even though those files are consumer-owned.

