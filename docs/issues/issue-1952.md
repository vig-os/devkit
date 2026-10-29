---
type: issue
state: open
created: 2026-10-28T21:58:49Z
updated: 2026-10-28T21:58:49Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1952
comments: 0
labels: bug
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-10-29T08:18:31.159Z
---

# [Issue 1952]: [direnv/nix shell: uv-installed numpy/scipy/pillow wheels fail on NixOS with libz.so.1 (only libstdc++ is exported)](https://github.com/vig-os/devkit/issues/1952)

Devkit 1.18.0, direnv mode, NixOS host (vm-dev), Python project via uv (nerdmachines/glint).

Inside `nix develop`, `.venv/bin/python -c 'import numpy'` fails:
`ImportError: libz.so.1: cannot open shared object file`.
The devkit shell hook adds libstdc++ to `LD_LIBRARY_PATH` for manylinux wheels, but not zlib. `ldd` over the venv shows ~36 shared objects needing libz (numpy, scipy gfortran/openblas, pillow). pytest masks it because stdlib zlib loads libz first.

Project-side fix applied: `mkProjectShell { shellHook = ...; }` prepending `${pkgs.zlib}/lib` on Linux.
Request: export zlib alongside libstdc++ in the devkit's manylinux compatibility hook so every Python consumer gets it.
