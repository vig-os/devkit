---
type: issue
state: closed
created: 2026-08-07T11:13:10Z
updated: 2026-08-07T12:48:01Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1362
comments: 1
labels: docs, effort:small, area:docs
assignees: none
milestone: 1.7.0
projects: none
parent: none
children: none
synced: 2026-08-07T21:31:02.225Z
---

# [Issue 1362]: [docs: MIGRATION.md env-forward denylist prose is stale after #1353/#1358](https://github.com/vig-os/devkit/issues/1362)

## Problem

`docs/MIGRATION.md` (~lines 145–157) enumerates the shellHook env-forward denylist in prose. It predates both denylist extensions and now disagrees with the shipped action:

- #1353 (PR #1357) added `UV_PYTHON` and `UV_PYTHON_DOWNLOADS`
- #1358 (PR #1361) added `IN_NIX_SHELL`, `_PYTHON_HOST_PLATFORM`, `_PYTHON_SYSCONFIGDATA_NAME`, `DETERMINISTIC_BUILD`, `CONFIG_SHELL`, `do[A-Z]*`, the cc/binutils hook names `AR`–`STRIP`, and the PYTHONPATH store-component strip (a transform, not a deny — the prose model does not cover that shape at all)

## Expected

Replace the enumeration with an SSoT pointer to the `devkit_env_denied` function in `assets/workspace/.github/actions/setup-devkit-toolchain/action.yml`, plus a short description of the *categories* (shell session state, Nix/stdenv build machinery, Nix-host interpreter pins, store-path stripping) so the doc stops going stale on every denylist change. Alternatively, update the prose to match — but the pointer form is preferred (single source of truth).

Refs: #1353, #1358
---

# [Comment #1]() by [c-vigo]()

_Posted on August 7, 2026 at 12:48 PM_

Fixed on dev by PR #1364: the stale enumeration is replaced with a category description (session state, build machinery, Nix-host interpreter pins incl. the #1360 NixOS exception, and the PYTHONPATH strip transform) plus an SSoT pointer to the devkit_env_denied function in the consumer's scaffolded action. The doc now states explicitly that the function is the single source of truth, so it stops going stale on denylist changes. Ships with 1.6.1.

