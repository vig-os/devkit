# Soft Main Guard

Branch protection and rulesets on **private** repositories need the GitHub Team
plan; the merge queue needs Enterprise Cloud. On the Free plan nothing stops a
direct push to `main`, and nothing tells you it happened.

`.github/workflows/main-guard.yml` is a reusable workflow (`workflow_call`) that
closes the second half: after every push to the guarded branch it checks that
each new commit belongs to a **merged** pull request whose base is that branch
(`gh api repos/R/commits/SHA/pulls`). Commits that do not are listed in one
tracking issue (label `main-guard`; a later offender comments on the open issue
instead of opening a second one).

It is a tripwire, not a gate: it **never reverts, force-pushes or fails the
caller**. A wrong automatic revert on `main` is worse than the problem, and
hotfixes and bots legitimately push.

## Use it

Add `.github/workflows/main-guard.yml` to the consumer repo:

```yaml
name: Main Guard
on:
  push:
    branches: [main]
permissions: {}
jobs:
  guard:
    permissions:
      contents: read        # compare API (commit range)
      issues: write         # the tracking issue and its label
      pull-requests: read   # commit -> PR lookup
    uses: vig-os/devkit/.github/workflows/main-guard.yml@<tag-or-sha>
    # with:
    #   branch: main                  # default: the repo's default branch
    #   label: main-guard
    #   ignore-authors: release-bot   # comma-separated logins never flagged
    #   runner: '["self-hosted","linux"]'   # default ["ubuntu-latest"]
```

The workflow must be triggered by `push` (the commit range comes from the push
event) and the caller needs `issues: write` or the alert cannot be filed. Pin
`@<tag-or-sha>`; devkit is public, so any repository can call it.

## Behaviour notes

- **Range**: `before..after` from the push event. A new branch or a force-push
  whose old head is unreachable checks the head commit only.
- **Squash, rebase and merge-commit** merges all count: each resulting commit is
  associated with the merged PR by GitHub.
- **Lag**: right after a merge the commit→PR index can be empty for a few
  seconds, so each unassociated commit is re-checked (4 tries, 5 s apart) before
  being flagged.
- **Bots**: Dependabot/Renovate merge through PRs and need no exemption. Use
  `ignore-authors` for bots that push directly (e.g. release automation).
- **Closing the loop**: close the issue once reviewed; the next offender opens a
  fresh one. If the repo moves to Team, replace this with a ruleset
  ("Require a pull request before merging"); keeping the guard as a second line
  is harmless.

## Tests

`tests/test_main_guard.py` pins the contract (permissions, inputs, actionlint)
and executes the workflow's real `run:` script against a fake `gh`: merged PR is
silent, direct push opens one issue, an open issue gets a comment, unmerged or
other-base PRs do not count, the lag retry, ignored authors, new-branch/force
push, other-branch pushes.
