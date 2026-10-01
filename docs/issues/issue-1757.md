---
type: issue
state: closed
created: 2026-09-28T21:44:34Z
updated: 2026-09-30T20:16:25Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1757
comments: 1
labels: none
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-10-01T08:40:58.451Z
---

# [Issue 1757]: [sync-issues: 'Save sync state' with if: always() advances the watermark even when the push FAILED — the delta is silently dropped](https://github.com/vig-os/devkit/issues/1757)

## Summary

`sync-issues.yml` saves the incremental-sync watermark with `if: always()`, so it is saved even when
`Commit and push changes via API` has just **failed**. The next run then syncs from the advanced
cutoff, so the issues/PRs whose files were never pushed are never regenerated. They are lost
silently, and the job reports `failure` only on the run where the push broke — after that, a quiet
day looks green.

Data-loss class, not a cosmetic ordering issue, and it affects every consumer.

## Step order

```yaml
- name: Sync Issues and PRs           # writes .sync-state/last-sync.txt + the docs files
- name: Commit and push changes via API
  if: steps.sync.outputs.modified-files != ''
- name: Save sync state
  if: always()                        # <-- saves the NEW cutoff regardless of the push result
  uses: actions/cache/save@…
```

The watermark is produced by the sync step and consumed by the *next* run, but the only thing that
makes it durable — the push — sits between them and is allowed to fail.

## Observed

vig-os/tessera, run [36395811823](https://github.com/vig-os/tessera/actions/runs/36395811823):

```
Synced PR #444 with 0 comment(s) to docs/pull-requests/pr-444.md
Synced PR #443 with 0 comment(s) to docs/pull-requests/pr-443.md
Committing 2 file(s) to branch dev
##[error]Required status check "nix flake check" is expected.
...
Cache saved with key: sync-issues-state-vig-os/tessera        <-- watermark advanced anyway
```

Those two files are not on `dev` and no later run will reproduce them, because their `updated_at` is
now behind the cutoff. Only a `force-update: true` dispatch recovers them.

## Why `if: always()` was presumably added

It looks like a fix for the opposite failure — the scenario in tessera#362, where a run died on a
secondary rate limit and, with no state saved, the next run rebuilt the same oversized set and hit
the same limit, never self-healing. `if: always()` does break that loop, but by discarding the work
instead of retrying it, which trades a visible stall for silent loss.

The bounded 14-day look-back in `Compute incremental cutoff` already handles the original
non-self-healing case far better: a cache miss can no longer mean "re-sync from epoch". So the
`always()` is no longer carrying the weight it was added for.

## Suggested fix

Save the watermark only when the delta actually landed — i.e. gate it on the commit step having
succeeded or having been legitimately skipped (nothing to commit), rather than on `always()`:

```yaml
- name: Save sync state
  if: ${{ steps.sync.outcome == 'success' && steps.commit.outcome != 'failure' }}
```

A failed push then leaves the previous cutoff in place and the next run retries the same delta, which
is the self-healing behaviour. Combined with the 14-day look-back, the unbounded-rebuild risk that
motivated `always()` is already covered.

If partial progress is genuinely wanted, the watermark would have to be advanced to the last
*successfully pushed* item rather than to the end of the sync — but per-run retry is much simpler and
sufficient, since a failing push is an operator-visible condition.

## Second-order note

Because the commit step is `if: steps.sync.outputs.modified-files != ''`, a run with nothing to
commit **skips** it and the job goes green. So a repo whose pushes are permanently broken shows green
on every quiet day and red only when something changed — which is how this stayed unnoticed in
tessera for weeks. Worth considering whether a push that *should* have happened and did not ought to
fail louder than one red run.
---

# [Comment #1]() by [c-vigo]()

_Posted on September 30, 2026 at 08:16 PM_

Fixed on `dev` by #1792 (964a49da): `Save sync state` now runs only when `steps.sync.outcome == 'success' && steps.commit.outcome != 'failure'`, in both the scaffold and devkit's own `sync-issues.yml`. A failed push keeps the old cutoff, so the next run retries the delta. Consumers receive it with the next devkit release.

