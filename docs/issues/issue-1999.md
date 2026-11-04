---
type: issue
state: open
created: 2026-11-03T09:28:12Z
updated: 2026-11-03T09:28:12Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1999
comments: 0
labels: feature, area:workspace
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-11-03T12:23:59.992Z
---

# [Issue 1999]: [[FEATURE] One-step new Python project: install.sh --language python (starter rendered + .gitignore fragment + DEVKIT_LANGUAGES in one pass)](https://github.com/vig-os/devkit/issues/1999)

## Description

There's no one-step path to a **new Python project** on devkit. The pieces exist (`templates.python`, the per-language `.gitignore` fragment, `DEVKIT_LANGUAGES`), but they only line up if the steps happen in an order nobody is told about.

## Problem Statement

Bootstrapping `exoma-ch/ravmatic` (direnv, 1.18.0):

1. `install.sh` has no language flag, so the scaffold runs language-neutral. `DEVKIT_LANGUAGES` stays empty, and no Python `.gitignore` fragment is added because `pyproject.toml` doesn't exist yet.
2. `nix flake init -t github:vig-os/devkit#python` copies `example_pkg` verbatim. Its README asks for a rename in four places. Its `pyproject.toml` hardcodes `requires-python = ">=3.14,<3.15"`, which is wrong for code deployed to another interpreter (here: klippy on Raspberry Pi OS, Python 3.11). It also duplicates the version in `__init__.py` (`__version__ = "0.1.0"`) next to `pyproject.toml`.
3. The first commit then tracked `__pycache__/*.pyc`, because the managed `.gitignore` had no Python fragment. Fixing it took a second `install.sh --force` from a feature branch (the upgrade preflight refuses `main`/`dev`) plus a PR. Related: #1826.

## Proposed Solution

- `install.sh --language python` (repeatable or comma-separated). It seeds `DEVKIT_LANGUAGES`, renders the Python starter with placeholder substitution (package = `SHORT_NAME`), and appends the `.gitignore` fragment, all in the same pass.
- In the starter, derive `__version__` from `importlib.metadata.version(...)` instead of duplicating it, and use a floor-only `requires-python` (e.g. `>=3.11`). The dev shell's pinned interpreter doesn't need to be the package's ceiling.
- Until then, document the order in the README: create `pyproject.toml` *before* running the scaffold, or re-scaffold afterwards.

## Related

#929 (opt-in Python starter), #1826, #1478 (`DEVKIT_LANGUAGES`).

