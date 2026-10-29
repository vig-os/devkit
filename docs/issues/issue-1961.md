---
type: issue
state: open
created: 2026-10-29T03:28:18Z
updated: 2026-10-29T03:28:18Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1961
comments: 0
labels: bug, area:workspace
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-10-29T08:18:28.040Z
---

# [Issue 1961]: [mkProjectShell: interactive shell PYTHONPATH carries devkit tool site-packages that shadow the project venv](https://github.com/vig-os/devkit/issues/1961)

## Problem

The interactive dev shell from `mkProjectShell` exports `PYTHONPATH` with Nix store `site-packages` from the devkit's own Python tools. On vm-dev (NixOS, x86_64) these include vig-utils, rich, markdown-it-py, pygments, pyyaml, pymarkdownlnt, application-properties and **typing-extensions 4.15.0**.

`PYTHONPATH` entries come before the venv's `site-packages` on `sys.path`. So `uv run` in a consumer project imports the devkit's copies instead of the versions locked in the project's `uv.lock`. Nothing reports the mismatch: the wrong version is just imported.

#1358 fixed the same leak for the CI env forward (`GITHUB_ENV`). The interactive shell still has it.

## Reproduction (nerdmachines/glint, devkit `91083c0`)

- `uv.lock` pins `typing-extensions 4.16.0`; build123d 0.13.0 needs `typing_extensions.sentinel`, which is new in 4.16.
- Inside the dev shell:

```
$ uv run --group eda python -c "import build123d"
ImportError: cannot import name 'sentinel' from 'typing_extensions'
  (/nix/store/cj59m6ghchw555wpq42a5jj1w0z00x2j-python3.14-typing-extensions-4.15.0/lib/python3.14/site-packages/typing_extensions.py)
$ env -u PYTHONPATH uv run --group eda python -c "import build123d"   # works
```

- `echo $PYTHONPATH` in the shell lists the store paths above.

## Cause (likely)

The devkit's Python tools are in the dev shell's `packages`. The nixpkgs Python setup hook then adds every Python package's `site-packages` to `PYTHONPATH`. This is the same mechanism #1358 describes for CI.

## Possible fixes

1. **Keep tool libraries out of the shell environment:** ship vig-utils, pymarkdown and the rest as wrapped applications (`toPythonApplication` / `makeWrapper` with their own `PYTHONPATH`), so no library store paths reach the shell's `PYTHONPATH`. This is the preferred fix.
2. **Clear the variable for Python consumers:** in the `mkProjectShell` shellHook, remove `/nix/store` components from `PYTHONPATH` when `pyproject.toml` exists. Keep consumer-added entries (the legitimate #1180 case, e.g. `$PWD/src`).
3. **At least warn** in `doctor` when `PYTHONPATH` contains store paths and a `uv.lock` exists.

## Workaround in consumers

`env -u PYTHONPATH uv run …` (glint does this in `just eda-doctor`, nerdmachines/glint#40). The project's pytest runs still pass only because nothing they import needs a newer version than the leaked ones.

Refs: #1358, #1230

