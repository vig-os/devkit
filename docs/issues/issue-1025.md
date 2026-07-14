---
type: issue
state: closed
created: 2026-07-14T05:43:17Z
updated: 2026-07-14T08:14:40Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1025
comments: 1
labels: bug, priority:medium, area:ci, effort:medium, semver:minor
assignees: none
milestone: Backlog
projects: none
parent: none
children: none
synced: 2026-07-14T20:06:34.499Z
---

# [Issue 1025]: [[BUG] Scaffold codeql.yml: hardcoded python matrix + conflicts with GitHub default code-scanning setup](https://github.com/vig-os/devkit/issues/1025)

### Description

Surfaced by the commit-action direnv pilot (1.1.0). The scaffolded
`.github/workflows/codeql.yml` fails on a JS/TS consumer for two reasons:

1. **Hardcoded Python language matrix.** `language: ['python', 'actions']`. On a
   repo with no Python, the `python` leg fails: *"CodeQL could not process any
   code written in Python"* (no-source-code-seen-during-build).
2. **Advanced config conflicts with GitHub default CodeQL setup.** If the repo has
   GitHub's **default** code-scanning setup enabled (a common default), the
   advanced `codeql.yml` upload is rejected: *"CodeQL analyses from advanced
   configurations cannot be processed when the default setup is enabled."* Both
   the `actions` and language legs then fail on upload.

Like the `.gitignore` gap (#1024), `codeql.yml` is a managed/overwritten scaffold
file, so a consumer's per-repo language fix does not survive upgrades.

### Repro

Deploy any mode to a JS/TS repo that has default code-scanning enabled; the
`CodeQL Analysis (python)` and `(actions)` checks fail as above.

### Options

- Make the scaffolded matrix **language-aware** (detect `package.json` →
  `javascript-typescript`, `Cargo.toml` → none/`rust` when supported,
  `pyproject.toml` → `python`; always include `actions`).
- Document (and/or automate) that adopting the devkit's **advanced** CodeQL config
  requires **disabling GitHub default setup** — the two cannot coexist. Consider a
  scaffold/preflight note or an `install.sh` step to flip
  `code-scanning/default-setup` to `not-configured`.
- Consider making `codeql.yml` opt-in for repos that prefer GitHub default setup.

### Pilot workaround (commit-action)

Disabled default setup via the API and changed the matrix
`python` → `javascript-typescript` (kept `actions`). Non-blocking for 1.1.0.

---

# [Comment #1]() by [c-vigo]()

_Posted on July 14, 2026 at 08:14 AM_

Fixed in #1035 (merged to dev): CodeQL language matrix rendered per detected language at scaffold time (always includes actions); the default-setup conflict is documented in the workflow header and printed as an install-time note.

