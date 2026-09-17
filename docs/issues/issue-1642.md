---
type: issue
state: closed
created: 2026-09-17T07:35:56Z
updated: 2026-09-17T08:12:34Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1642
comments: 1
labels: bug, area:workspace
assignees: c-vigo
milestone: none
projects: none
parent: none
children: none
synced: 2026-09-17T11:46:25.211Z
---

# [Issue 1642]: [[BUG] Switching trunk -> gitflow leaves the dev-branch guard stripped from the preserved .pre-commit-config.yaml](https://github.com/vig-os/devkit/issues/1642)

### Description

`render_workflow_model` applies the `gitflow → trunk` retarget one-way: it
early-returns unless the resolved model is `trunk`. For every file it touches
that is **managed**, that is harmless — the template overwrite restores the
gitflow shape on the next upgrade and the render simply does not re-run. But
`.pre-commit-config.yaml` is **preserved** (`PRESERVE_FILES`, #878), so the trunk
edits stay in it forever.

Switching a consumer back to gitflow therefore leaves the **dev-branch guard
silently stripped**: `no-commit-to-branch` no longer blocks a direct commit to
`dev`, on a repo whose whole point is that `dev` is protected. There is no error,
no notice, and the `.vig-os` manifest says `gitflow`.

This is the last instance of the class fixed in #1640 — same preserved file, same
"the render only runs in one direction" shape. It was scoped out of that PR on
the assumption that it spanned many files and needed its own design. It does not:
measured below, the entire stale surface is two lines of one file.

### Steps to Reproduce

Scaffold, switch to trunk, switch back — using the documented switch path (the
contradiction guard's own step 3: "set `DEVKIT_WORKFLOW=<model>` in `.vig-os` on
a dedicated, clean upgrade branch and re-run the upgrade").

1. `init-workspace --force --no-prompts --mode both`
2. `sed -i 's/^DEVKIT_WORKFLOW=.*/DEVKIT_WORKFLOW=trunk/' .vig-os` and re-run.
3. `sed -i 's/^DEVKIT_WORKFLOW=.*/DEVKIT_WORKFLOW=gitflow/' .vig-os` and re-run.
4. `grep -c '(?!dev\$)' .pre-commit-config.yaml`

### Expected Behavior

`1` — the dev clause is back, and `.pre-commit-config.yaml` matches the template
for those lines, the way every managed file already does.

### Actual Behavior

`0`. Measured across every file `render_workflow_model` touches, after the
round-trip:

| Target | Managed / preserved | After switch-back |
|---|---|---|
| `.github/workflows/ci.yml` | managed | restored (`TRUNK="dev"`) |
| `.github/workflows/codeql.yml` | managed | restored |
| `.github/workflows/sync-issues.yml` | managed | restored |
| `.github/workflows/prepare-release.yml` | managed | restored |
| `.github/workflows/promote-release.yml` | managed | restored |
| `.github/renovate-default.json` | managed | restored (`["dev"]`) |
| `.devcontainer/justfile.gh` | managed | restored |
| `.claude/skills/branch-naming/SKILL.md` | managed | restored |
| **`.pre-commit-config.yaml`** | **preserved** | **STALE** |

The stale surface is exactly two lines:

```diff
-      # Allows main, dev, and branches matching the convention.
+      # Allows main and branches matching the convention.
-          - "^(?!main$)(?!dev$)(?!^(chore)/...
+          - "^(?!main$)(?!^(chore)/...
```

Nothing catches it. The scaffold-drift gate (#1295) re-runs the scaffold and
`git diff`s, and the re-run reproduces the same stale file, so it sees no drift.
A flake-hooks consumer is unaffected: their guard comes from `mkProjectShell`,
which reads `DEVKIT_WORKFLOW` at eval time (#1224/#1434) and is correct in both
directions — it is only the scaffolded YAML that is one-way.

### Environment

Any consumer that has ever been on `trunk`; reproduced against `dev` at 4914a5f6.

### Possible Solution

Follow #1640: split the `.pre-commit-config.yaml` edits out of
`render_workflow_model` into their own render that runs for **both** models and
renders the dev clause according to the resolved model, rather than only
subtracting it under trunk. The gitflow direction needs anchors chosen so a
second run is a no-op — inserting `(?!dev$)` between `(?!main$)` and `(?!^(chore)`
stops matching once it is there, and the comment substitutions likewise.

It should use the `precommit_render_target` resolver added in #1640, so the
symlink and absent-file refusals stay in one place.

### Additional Context

Found while fixing #1640 and deferred there on a premise that turned out to be
wrong — the managed files self-heal, so this is one file and two lines, not a
cross-file redesign.

---

# [Comment #1]() by [c-vigo]()

_Posted on September 17, 2026 at 08:12 AM_

Shipped to `dev` in #1643 (merge commit 0b32ebdc), all checks green.

The `.pre-commit-config.yaml` edits moved out of `render_workflow_model` into a
new `render_branch_guard_model`, which runs for **both** models and renders the
dev clause *from* the resolved model rather than only subtracting it under trunk.
It goes through the `precommit_render_target` resolver from #1640, so the symlink
and absent-file refusals stay in one place. Each direction's anchors stop matching
once applied, so a re-run is a no-op and a default gitflow scaffold stays
byte-identical to the template.

**One trap worth recording, because it silently produced a no-op fix.** GNU sed
4.10 treats a *mid-pattern* `$` in a basic regular expression as an end anchor,
not a literal, so the obvious insert pattern

```sed
s|(?!main$)(?!^(chore)|(?!main$)(?!dev$)(?!^(chore)|
```

matches nothing at all — and fails silently, leaving the file untouched. The
pre-existing `(?!dev$)` strip only works because its `$)` sits at the very end of
the pattern. Both metacharacters are escaped in the insert pattern for that
reason; the replacement side needs none, since sed gives `$`/`^` no meaning
there. The source comment records this so it is not rediscovered.

What caught it was the byte-for-byte template-parity test: a looser assertion
would have caught this particular case too, but parity is what makes the
preserved file provably land on the same bytes a managed file gets.

Verified with four bats cases committed first (`5c33a7ca`), the two behavioural
ones red. Full `bats tests/bats/init-workspace.bats` 270 passed / 0 failed,
deliberately including the #1205 workflow-switch suite and the #1255 flake-hooks
fixtures since this refactors shared machinery; `pytest` 1070 passed / 1 skipped
(`test_flake_checks.py` caught a `typos` violation in one of my source comments,
reworded rather than allowlisted); `prek run --all-files` green.

This closes the #1640 class: every in-place render of the preserved
`.pre-commit-config.yaml` is now bidirectional, idempotent and symlink-safe.

Closing as done. It reaches consumers with the next release train.

