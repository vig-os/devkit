---
type: issue
state: open
created: 2026-10-11T14:43:58Z
updated: 2026-10-11T14:43:58Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1862
comments: 0
labels: none
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-10-12T08:59:44.900Z
---

# [Issue 1862]: [install.sh: reports "No git repository found" and reinitializes inside a linked git worktree](https://github.com/vig-os/devkit/issues/1862)

## Summary

Run inside a **linked git worktree**, `install.sh` reports *"No git repository found"* and then
performs a git reinitialization. It is harmless in effect — branch, commits and remote all
survived — but the message is wrong and the reinit is unnecessary work on a repo that is already
perfectly valid.

## Observed

Consumer `gerchowl/pidgy`, upgrading 1.7.0 → 1.18.0 in a linked worktree created by a worktree
manager:

```sh
# cwd: /Users/larsgerchow/.flock/worktrees/pidgy-14782b58/chore-devkit-1-18-0
curl -sSfL .../install.sh | bash -s -- --force --version 1.18.0 \
  --skip-preflight --mode direnv --podman .
```

The installer announced no git repository was found and reinitialized. The upgrade otherwise
completed correctly and the resulting commits and push were intact.

## Likely cause

In a linked worktree, `.git` is a **file** containing a `gitdir:` pointer, not a directory:

```text
$ cat .git
gitdir: /path/to/main/checkout/.git/worktrees/<name>
```

A check shaped like `[ -d .git ]` therefore fails in a worktree that is genuinely a valid repo.
`git rev-parse --git-dir` (or `--is-inside-work-tree`) handles both layouts and is the portable
test.

## Why it matters beyond cosmetics

Worktrees are the normal working mode for parallel/agent-driven development, so this path gets hit
often. Two risks beyond the misleading message:

1. A reinit in a valid repo is a surprising write — anything that later depends on git state being
   untouched could be affected in a way that is hard to attribute.
2. The incorrect "no repository" conclusion may gate *other* behaviour in the installer (preflight
   checks, branch detection, the upgrade commit path), so the real blast radius depends on what
   else keys off that detection.

Reproduces on demand: run `install.sh` from any `git worktree add` directory.

Context: found while working around vig-os/devkit#1856 (the upgrade commit running the new hook
config in the old project shell), which is why the installer was being invoked by hand rather than
through `devkit-upgrade.yml`.

