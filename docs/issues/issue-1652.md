---
type: issue
state: closed
created: 2026-09-18T14:27:13Z
updated: 2026-09-21T06:53:44Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1652
comments: 1
labels: feature, priority:high, area:workspace, effort:medium, semver:minor
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-09-21T07:52:32.182Z
---

# [Issue 1652]: [Upgrade can't fold hook fixes into a preserved .pre-commit-config.yaml — warn on the pre-#1170 jackdewinter/pymarkdown block](https://github.com/vig-os/devkit/issues/1652)

## Problem

When a consumer's `.pre-commit-config.yaml` is **preserved** (hand-edited — e.g. it carries a repo-specific `exclude:`), `install.sh --force` cannot fold in later template hook changes. A consumer scaffolded before **#1170** therefore keeps the old upstream `repo: https://github.com/jackdewinter/pymarkdown` prek hook indefinitely, silently overriding the fix that #1170 shipped.

That old hook is `language: python`: prek builds a venv on a **3.13** base interpreter, but the flake toolchain's `pymarkdownlnt` is built for **3.14** (`default_language_version: python3.14`). Loading a `cpython-314` `pyjson5` `.so` under 3.13 fails:

```
prek → pymarkdown → application_properties → import pyjson5 → from .pyjson5 import *
ModuleNotFoundError: No module named 'pyjson5.pyjson5'
```

(The `.so` is present — it's an interpreter/ABI skew, not a broken package.) This breaks `just precommit`, local markdown commits, **and the `devkit-upgrade.yml` commit step** — so a stale consumer's auto-upgrade can never land. Observed live on a 1.3.1 → 1.15.1 consumer whose preserved config predated #1170.

## Why the upgrade can't self-heal

#1170 replaced the `jackdewinter/pymarkdown` block with a `repo: local` / `entry: pymarkdown` / `language: system` hook. But #878-style preservation means a hand-edited `.pre-commit-config.yaml` is consumer-owned, so `install.sh --force` won't rewrite it — the fix never reaches exactly the repos that most need it, and the failure is invisible until someone enters the new shell.

## Proposed guard (any of)

1. **Scaffold/upgrade warning:** when `.pre-commit-config.yaml` is preserved AND still matches `repo:\s*https://github.com/jackdewinter/pymarkdown`, `install.sh` prints an actionable notice ('your preserved pre-commit config still uses the pre-#1170 pymarkdown hook; replace it with the language: system form — see …').
2. **Drift-check lane:** the scaffold-drift gate flags the stale block (even though the file is preserved) as a known-bad pattern rather than generic drift.
3. **Migration doc entry** in `docs/MIGRATION.md` for the #1170 hook change, so preserved-config consumers know to fold it.

A pattern-scan for known-bad *preserved-hook* blocks generalises beyond pymarkdown — the same trap applies to any future `language: python`→`language: system` hook migration.

Context: fixed in one consumer by folding the #1170 block by hand; this issue is about the other consumers that won't know they need to.
---

# [Comment #1]() by [c-vigo]()

_Posted on September 21, 2026 at 06:53 AM_

Solved on `dev` in #1653: the scaffold scans preserved files for retired hook blocks, warns with `file:line` + remedy, and prints a `preserved-hook-drift:` line that `devkit-upgrade.yml` lifts into the adoption PR body. `docs/MIGRATION.md` carries the #1170 fold instructions. Closing manually — `Closes #` only fires on a main-branch merge.

Follow-up split out: #1654 (auto-fold a byte-exact retired block — the only thing that unsticks a consumer whose prek is already broken).

