---
type: issue
state: open
created: 2026-11-02T05:21:35Z
updated: 2026-11-02T05:21:35Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1986
comments: 0
labels: bug
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-11-02T09:14:44.057Z
---

# [Issue 1986]: [release train: final tag is cut before post-finalize CI, so release-branch fixes land after the tag and main diverges from the published tag](https://github.com/vig-os/devkit/issues/1986)

## Problem
`release.yml -f release-kind=final` cuts the final git tag **before** the release branch's post-finalize CI has run. The finalize step itself pushes commits ("chore: finalize", "chore: sync issues and PRs"), and those commits can turn the release PR red:
- the generated `docs/pull-requests` mirrors were picked up by a repo test;
- the frozen CHANGELOG fails `end-of-file-fixer` (#1901).

The fixes then have to land on `release/X.Y.Z` **after** the tag exists. `promote-release.yml` merges the release branch head into main but publishes the Release at the older tag, so **the published tag and main diverge**.

## Observed (vig-os/vigil 0.1.0)
- Tag `0.1.0` is at `e82890c`. After two release-branch fixes (vigil#161, a test scope; vigil#167, README install docs), the release branch head is `e81edaa`.
- `git diff --stat e82890c e81edaa` touches only `README.md` and `tests/release_docs.rs`, so the shipped code is the same. But the tagged tree's crate root doc (the README is `include_str!`'d) lacks the install section that main has.

## Expected (either one)
- **(a)** The final step runs the full CI on the finalized head (after its own finalize commits) and tags only when that head is green.
- **(b)** `promote-release` refuses when the release branch head is not the tagged commit, or offers a re-tag path for post-final fixes (a new `-rcN` or final cycle), so that main and the published tag can't silently diverge.

Related: #1901 (finalize leaves a blank line at EOF), #1899.

