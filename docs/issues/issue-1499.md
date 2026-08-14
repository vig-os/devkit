---
type: issue
state: closed
created: 2026-08-13T14:40:20Z
updated: 2026-08-14T07:42:05Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1499
comments: 1
labels: bug, priority:medium, area:ci, effort:small, semver:patch
assignees: none
milestone: 1.10.0
projects: none
parent: none
children: none
synced: 2026-08-14T16:05:16.858Z
---

# [Issue 1499]: [[BUG] A partially-created deploy PR is invisible to the smoke listener's stale-PR cleanup, so re-run recovery fails](https://github.com/vig-os/devkit/issues/1499)

Found while running the 1.9.0 train (rc1). Not a blocker for that train — a transient recovered — but the recovery path documented in `CROSS_REPO_RELEASE_GATE.md` did **not** work unassisted, and the reason is structural.

## What happened

The `deploy` job's `Create deploy PR` step failed on a transient GitHub GraphQL 500:

```
pull request update failed: GraphQL: Something went wrong while executing your query
  on 2026-08-13T14:36:50Z ... BC41:387E8A:D18436:2C6E32A:6A7DD680
```

Run: https://github.com/vig-os/devkit-smoke-test/actions/runs/31710999351

## The structural part

Read the error wording: **`pull request update failed`**, not *create* failed. `gh pr create --label` creates the PR and then applies the label as a follow-up mutation. The create succeeded — [devkit-smoke-test#367](https://github.com/vig-os/devkit-smoke-test/pull/367) exists, opened 14:36:47 — and the *labeling* is what hit the 500. The step then exited 1, so:

1. `pr_url` was never written to `GITHUB_OUTPUT`, so every downstream job skipped, and
2. an **unlabeled** deploy PR was left open on `chore/deploy-<tag>`.

`Close stale deploy PRs` selects candidates with `gh pr list --base dev --state open --label deploy`. An unlabeled PR is invisible to it. So the documented recovery — re-run the failed jobs — re-enters `Create deploy PR`, which fails with *"a pull request already exists"*, and keeps failing until a human adds the label or closes the PR by hand.

The failure mode is: **the one step whose partial success is most likely is also the one the cleanup cannot reclaim.**

## Recovery used

Added the `deploy` label to #367 by hand, then `gh run rerun <id> --failed`. The workflow's own cleanup then closed and recreated it correctly.

## Options

- Select stale deploy PRs by **head-branch pattern** (`chore/deploy-*`) as well as by label — the branch name is deterministic and is written before the PR exists, so it cannot be lost to a partial failure. Probably the smallest correct fix.
- Or make `Create deploy PR` idempotent: look for an existing open PR on `${BRANCH_NAME}` first and adopt it (recording its URL) instead of creating.
- Or apply the label in its own step, so a labeling failure does not fail the create.

The first and second compose well: reclaim by branch, adopt if present.

## Secondary observation

The `Notify upstream on smoke-test dispatch failure` job also failed, on the same class of transient (`4451:2C13C:44BF2C:EA17E4:6A7DD694`, 20 s later), so **no upstream incident issue was auto-filed** for this failure — hence this hand-written one. Worth considering whether the notify path deserves a retry, since it is the thing that is supposed to work when everything else did not.

The SSoT for the asset is `assets/smoke-test/.github/workflows/repository-dispatch.yml`; note the listener runs from the smoke repo's **default branch**, so any fix needs the redeploy dance recorded in `CROSS_REPO_RELEASE_GATE.md` §Contract dependencies.

---

# [Comment #1]() by [c-vigo]()

_Posted on August 14, 2026 at 07:42 AM_

Fixed in #1505 (merged to `dev` as `dc3acf12`), milestone 1.9.1.

## What shipped

All in `assets/smoke-test/.github/workflows/repository-dispatch.yml`, taking all three options from the issue plus the secondary observation — they compose into one unit:

1. **Reclaim by head branch.** `Close stale deploy PRs` now selects every open PR on `chore/deploy-*` **or** carrying the `deploy` label, in one `gh pr list --json number,headRefName,labels --limit 100` call. The branch name is deterministic and pushed before the PR exists, so it cannot be lost to a partial failure.
2. **Adopt, then record, then label.** `Create or adopt deploy PR` looks for an open PR on `${BRANCH_NAME}` and adopts it instead of dying on *"a pull request already exists"*, and writes `pr_url` to `GITHUB_OUTPUT` before anything else can fail.
3. **Labelling is its own step.** `Label deploy PR` retries three times with backoff and is non-fatal — now that the cleanup reclaims by branch, an unlabelled PR stays recoverable, so a label transient must not strand `pr_url`.
4. **`notify-failure` retries** its `gh issue create` (three attempts, then fails loudly). That path 500'd 20 s after the deploy did, which is why this issue had to be written by hand.

## Tests

New `tests/test_smoke_deploy_pr_reclaim.py` (12 tests), following the harness pattern from #1477. Shape assertions parse the YAML; behaviour assertions execute each step's **real bash** against a stubbed `gh` with `--jq` handed to real `jq`, replaying the rc1 timeline:

- the unlabelled PR on `chore/deploy-1-9-0-rc1` is closed, a labelled legacy deploy PR is still closed, an unrelated `feature/*` PR is never touched
- with labelling failing on every attempt, `pr_url` still reaches `GITHUB_OUTPUT` and the job stays green
- with an open PR already on the deploy branch, `gh pr create` is never called and the adopted url is recorded
- notify: two transients then success → three attempts; exhausted retries fail the step

## Docs

`docs/CROSS_REPO_RELEASE_GATE.md` records the reclaim invariant under Receiver Responsibilities and adds a Failure Signals entry for `pull request update failed`, including what to do on a listener version predating this fix (add the `deploy` label by hand *before* re-running).

## Not live yet

`repository_dispatch` runs the listener from the smoke repo's **default branch**, so this merge alone does not protect the next train. The mirror hotfix is open at [devkit-smoke-test#373](https://github.com/vig-os/devkit-smoke-test/pull/373) — a byte-exact copy of the fixed asset, awaiting the human approval that smoke `main` requires. `dev` there is intentionally not patched: the next train's deploy PR carries the same content from the release tag and converges it.


