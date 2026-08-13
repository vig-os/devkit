---
type: issue
state: closed
created: 2026-08-13T09:13:48Z
updated: 2026-08-13T10:05:38Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1491
comments: 1
labels: chore, area:workspace
assignees: none
milestone: 1.9.0
projects: none
parent: none
children: none
synced: 2026-08-13T14:59:07.745Z
---

# [Issue 1491]: [[CHORE] Pin stages on the remaining unfiltered local hooks (sync-manifest, check-agent-identity)](https://github.com/vig-os/devkit/issues/1491)

### Chore Type

Cleanup

### Description

Split out of [#1489](https://github.com/vig-os/devkit/issues/1489), which fixed
the one hook of this group that actually broke a commit.

Three `local` hooks carry neither `stages:` nor a file filter, so they run at
**every** hook stage — pre-commit, prepare-commit-msg and commit-msg:

| Hook | `pass_filenames` | Consequence of no `stages` |
|---|---|---|
| `typos` | `true` | **Was a real bug** — got `COMMIT_EDITMSG` and rejected rebases. Fixed in #1489 |
| `sync-manifest` | `false` | Runs 3x per commit instead of 1x — a `uv run` script over the whole manifest |
| `check-agent-identity` | `false` | Runs 3x per commit instead of 1x |

Only `typos` received a filename, which is why only `typos` broke. The other
two are pure waste: each commit pays for two redundant invocations of a
`uv run` entry point.

### Acceptance Criteria

- [ ] `sync-manifest` pinned to the stage(s) it is actually meant to run at
- [ ] A deliberate decision recorded for `check-agent-identity` — see the note
      below; it may legitimately want the message stages
- [ ] Both committed configs and `nix/hooks.nix` stay in step (the drift gate in
      `tests/test_flake_hooks.py` enforces this)
- [ ] No coverage change: `prek run --all-files` and the CI lint lane unaffected

### Implementation Notes

**Check before changing `check-agent-identity`.** It guards the *author and
committer*, not the message, and its consumer fragment is already pinned to
`stages = [ "pre-commit" ]` in `nix/hooks.nix` — but the `yaml` fragment (both
committed configs) has no `stages` at all, so the runner and the flake-generated
surfaces currently disagree about when it runs. Reconciling that disagreement is
the real content of this issue for that hook; picking `pre-commit` to match the
consumer surface is the obvious candidate, but confirm the message stages are
genuinely not wanted first.

`sync-manifest` is a repo generator (`uv run python scripts/sync_manifest.py`)
and is runner-only — it has no consumer fragment, so only the root config is in
scope for it.

This is a performance/consistency cleanup, not a bug fix: nothing is currently
broken by it.

### Related Issues

Refs: #1489
---

# [Comment #1]() by [c-vigo]()

_Posted on August 13, 2026 at 10:05 AM_

Fixed on `dev` via #1494 (merged `e214b3a1`).

`sync-manifest` and `check-agent-identity` are pinned to `pre-commit` in the `yaml` fragment of `nix/hooks.nix`, which renders both committed configs. All four acceptance criteria met:

- `sync-manifest` pinned — it is runner-only, and only ever has something to say about staged files
- **Decision recorded** for `check-agent-identity` (code comment, commit message, changelog): probed against real git rather than assumed. Git exports the same `GIT_AUTHOR_NAME`/`GIT_AUTHOR_EMAIL` to all three stages of an ordinary commit — including under `git commit --author=…`, the case the hook exists to catch — so the message stages only re-read what `pre-commit` had already rejected on. The one path where they fire and `pre-commit` does not is `git merge`, where git exports no author at all and the hook fell back to `git config user.*`: the persistent identity that fails the committer's very next ordinary commit. A merge is therefore the single commit this no longer guards locally, in exchange for dropping two of three invocations per commit. `pre-commit` also matches the consumer fragment, so the runner and flake-generated surfaces no longer disagree
- Both committed configs stay in step with `nix/hooks.nix` — the drift gate in `tests/test_flake_hooks.py` is green, in CI as well as locally
- No coverage change — `prek run --all-files` still runs both hooks (green, exit 0), and the CI lint lane is unaffected

Live-proven on the PR's own commits: one commit ran the two hooks 9 times across the three rounds and both surfaces before, 3 after — they now appear only in the `pre-commit` round.

Scaffolded consumers pick up the alignment by adopting the next release; milestone set to 1.8.1.

