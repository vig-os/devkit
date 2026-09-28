---
type: issue
state: closed
created: 2026-09-25T07:50:38Z
updated: 2026-09-25T09:52:04Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1698
comments: 1
labels: bug, priority:low, area:ci, effort:small
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-09-26T07:26:44.242Z
---

# [Issue 1698]: [fix(ci): release-neutral guard cancels its own in-flight run on every label event](https://github.com/vig-os/devkit/issues/1698)

## Problem

`.github/workflows/release-neutral-guard.yml` triggers on `pull_request` with
`types: [opened, reopened, synchronize, labeled, unlabeled]` (line 78) and carries one workflow-level
concurrency group, `release-neutral-guard-${{ github.event.pull_request.number }}` with `cancel-in-progress: true`
(lines 82-84), undiscriminated by event. Every label event on a pull request therefore cancels whatever guard run is
in flight for it — including the run started by the `opened` or `synchronize` event that the label has nothing to do
with — and leaves a `cancelled` run on the pull request.

Two facts measured today on a consumer repository with the same shape (a `labeled` trigger sharing one
cancel-in-progress lane with code events):

- `gh pr create --label a --label b` emits **two** `labeled` events per label, within a second. A pull request created
  with two labels starts five runs; four of them cancel each other in entry order.
- A cancelled check run of a **required** name keeps the pull request's status rollup red however many later successes
  land beside it; GitHub does not resolve a required context to its latest check run. `gh pr checks` dedupes by name
  and shows green, so the block is invisible from the CLI.

Here the guard's job is **not** a required check (the `main` ruleset requires `Test Summary` and the two
`CodeQL Analysis` contexts), so it cannot block a merge. The cost is a red cancelled run on the pull request, a stale
verdict comment, and a wasted runner start per label event. Low priority, but the same class of defect, and this file
is the reference workflow other repositories copy.

## Proposal

Split the lane by event kind and give label events their own lane, as the consumer did:

```yaml
concurrency:
  group: release-neutral-guard-${{ github.event.pull_request.number }}-${{ (github.event.action == 'labeled' || github.event.action == 'unlabeled') && github.run_id || 'code' }}
  cancel-in-progress: true
```

and, if only the `release-neutral` label matters to the guard, gate the label events on
`github.event.label.name == 'release-neutral'` so unrelated labels start a run whose jobs skip (a `skipped` run is
neutral; a `cancelled` one is red). Note the interaction with the verdict comment: two label runs may now both post;
make the comment sticky by marker if it is not already.

## Tasks

- [ ] Concurrency lane keyed on the run id for `labeled`/`unlabeled`
- [ ] Label-name gate on the label events, if the guard only cares about its own label
- [ ] Verify by creating a pull request with two labels: zero `cancelled` guard runs on the head
- [ ] `CHANGELOG.md` `## Unreleased` (Fixed)

## Refs

Same-class defect fixed in a consumer repository on 2026-09-25; that fix is the model above.

---

# [Comment #1]() by [c-vigo]()

_Posted on September 25, 2026 at 09:52 AM_

Shipped to `dev` in #1706. Reaches `main` with the next train; the live two-label acceptance check runs on the first lane PR after that. Gate 6's missing `always()` is tracked in #1705.

