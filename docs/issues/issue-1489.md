---
type: issue
state: closed
created: 2026-08-13T08:24:13Z
updated: 2026-08-13T09:30:52Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1489
comments: 1
labels: bug, area:workspace, effort:small
assignees: none
milestone: 1.9.0
projects: none
parent: none
children: none
synced: 2026-08-13T14:59:08.278Z
---

# [Issue 1489]: [[BUG] typos hook lints COMMIT_EDITMSG — a rebase whose todo comment embeds a git SHA cannot commit](https://github.com/vig-os/devkit/issues/1489)

### Description

The `typos` hook has no `stages:` and no `files:` filter, so it runs at **every**
hook stage — including `commit-msg` — and is handed `COMMIT_EDITMSG` as a
filename. `typos` reliably flags trigrams inside abbreviated git SHAs
(`afe` -> `safe`, `abd` -> `and`/`bad`, `daa` -> `data`, `ded` -> `dead`), so any
commit whose message **or its commented-out lines** contains such a SHA is
rejected.

`git rebase --continue` hits this routinely: git writes the rebase todo into
`COMMIT_EDITMSG` as comment lines, e.g.

```
#    pick 5c7afe1b # docs(release): document the release-PR re-approval before promote
```

and the commit is refused with `error: could not commit staged changes`. The
content being committed is irrelevant — it is the *comment* that fails.

### Steps to Reproduce

Verified on `dev` (worktree of `docs/1474-release-pr-reapproval`):

```console
$ printf 'chore: typos probe\n\n# pick 5c7afe1b # docs(release): probe comment line\n' > /tmp/msg.txt
$ git commit -F /tmp/msg.txt
...
typos (source typo checker)..............................................Failed
- hook id: typos
- exit code: 2
  error: `afe` should be `safe`
    ╭▸ ../../devkit/.git/worktrees/1474/COMMIT_EDITMSG:3:11
    │
  3 │ # pick 5c7afe1b # docs(release): probe comment line
    ╰╴          ━━━
```

The failure appears in the **second** hook round, not the first — the
`pre-commit` stage passes, and it is the message-stage invocation that fails.

Encountered live while rebasing #1485/#1486 onto `dev` after #1482 merged; the
workaround was `git commit -C REBASE_HEAD` (which writes a clean
`COMMIT_EDITMSG` with no todo comments) followed by `git rebase --continue`.

### Expected Behavior

`typos` is a *source* typo checker. It should lint the working tree, not the
commit message buffer — and certainly not git's own generated comment lines,
which never enter the committed message.

### Actual Behavior

A legitimate rebase is blocked by a false positive on a hex string in a comment.
Worse, the natural "fix" is for the developer to edit git's todo comment or
reach for `--no-verify`, which this repo forbids.

### Scope

**Not devkit-only.** `nix/hooks.nix:638` marks `typos` `scaffold = true`, and
`assets/workspace/.pre-commit-config.yaml:126-129` ships the identical
unfiltered definition, so **every scaffolded consumer** carries the same trap.

Three `local` hooks lack both `stages` and a file filter — `sync-manifest`,
`typos`, `check-agent-identity` — but only `typos` has `pass_filenames: true`,
so it is the only one that receives `COMMIT_EDITMSG` as an argument. The other
two merely run redundantly at each stage.

### Possible Solution

Add `stages: [pre-commit]` to the `typos` hook in **both**
`.pre-commit-config.yaml` and `nix/hooks.nix` (the `yaml`, `check` and `consumer`
fragments), so it lints source at the pre-commit stage only. That matches what
the hook is named for and costs no coverage: `prek run --all-files` and the CI
lane are unaffected.

Worth considering alongside:

- pinning `stages` on `sync-manifest` / `check-agent-identity` too, so the hook
  set stops doing three times the work per commit — though `check-agent-identity`
  may want the message stages deliberately; check before changing it;
- the same SHA-vs-`typos` collision already litters `docs/pull-requests/*.md`
  (`111abd5`, `daa54b4`, `ded6c23` all trip it). Those files are silenced only by
  the top-level `exclude:` in the pre-commit config, so the collision is latent
  rather than solved.

### Environment

devkit `dev` @`bcc92144`; `typos --force-exclude`, `language: system`, hook
defined at `.pre-commit-config.yaml:171-177` and `nix/hooks.nix:638-651`.

### Changelog Category

Fixed

Refs: #1474

---

# [Comment #1]() by [c-vigo]()

_Posted on August 13, 2026 at 09:30 AM_

Fixed on `dev` via #1493 (merge commit `e9a407db`).

`stages: [pre-commit]` on the `yaml` fragment of `nix/hooks.nix`, which renders both committed configs. Live-proven: the exact commit that failed on this branch's worktree before the fix (`typos … Passed` on the pre-commit round, `Failed` on the message round) commits cleanly after it.

**Correction to the proposed solution:** only the `yaml` fragment needed it. git-hooks.nix already defaults the hook to `stages: ['pre-commit']` — verified on the rendered consumer surface in all six variants that enable it — so flake-generated **direnv consumers were never affected**. Scaffolded consumers were, and are fixed by adopting this release. `TestTyposRunsOnlyAtPreCommit` asserts all three surfaces regardless, so the guard does not depend on that default staying put.

The two "worth considering" items are split out rather than bundled: #1491 covers `sync-manifest` / `check-agent-identity` (neither receives a filename, so neither is broken — but `check-agent-identity`'s `consumer` and `yaml` fragments currently disagree about its stage, which needs a decision). The `docs/pull-requests/*.md` SHA collisions stay silenced by the top-level `exclude:`.

Closing manually — a `Closes` line in a PR targeting `dev` does not auto-close.

