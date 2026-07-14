---
type: issue
state: closed
created: 2026-07-14T08:33:07Z
updated: 2026-07-14T09:34:34Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1038
comments: 1
labels: feature, priority:high, area:workspace, effort:small, semver:minor
assignees: none
milestone: Backlog
projects: none
parent: 1040
children: none
synced: 2026-07-14T20:06:31.200Z
---

# [Issue 1038]: [[FEATURE] mkProjectShell: overridable Python interpreter for nixpkgs C-extension ABI alignment](https://github.com/vig-os/devkit/issues/1038)

### Description

`mkProjectShell` pins the interpreter to `pkgs.python314` (`flake.nix:389`) and hardcodes the binary name in `UV_PYTHON = "${python}/bin/python3.14"` (`flake.nix:461`). A consumer cannot override it.

This breaks any consumer whose nixpkgs-provided C-extension dependency is built against a different CPython ABI. Concrete case (first external onboarding, exoma-ch/cad2gdml): `pkgs.freecad` 1.1.1 in the pinned nixpkgs is built against the nixpkgs default Python **3.13.13**, so `import FreeCAD` from the devkit's 3.14 interpreter fails with no consumer-side workaround (`extraPackages` can add FreeCAD to the shell but cannot change the interpreter uv pins).

### Proposed solution

- Add `python ? pkgs.python314` to the `mkProjectShell` argument set.
- Derive the pinned binary path from the argument (e.g. `${python}/bin/${python.executable}` or via `python.pythonVersion`) instead of the hardcoded `python3.14` string, so `UV_PYTHON` follows the override.
- Keep the default byte-identical to today (parity guard in `tests/test_flake_devshell.py`, same pattern as the `modules`/`hooks` arguments).
- Document the argument and the ABI-alignment use case in `docs/MIGRATION.md` (consumer section), with the FreeCAD example.

### Acceptance criteria

- [ ] `mkProjectShell { python = pkgs.python313; extraPackages = [ pkgs.freecad ]; }` produces a shell where `python3 -c "import FreeCAD"` succeeds (headless).
- [ ] Default invocation (no `python` argument) is unchanged (parity test).
- [ ] `uv` inside the shell resolves the overridden interpreter (`UV_PYTHON` points at it, `UV_PYTHON_DOWNLOADS=never` still enforced).
- [ ] Documented in `docs/MIGRATION.md`.

### Additional context

Blocks the cad2gdml onboarding epic (Phase 0). Per `docs/rfcs/ADR-capability-modules.md`, heavy third-party libraries stay per-project `extraPackages` — this issue provides the missing interpreter-alignment knob that makes that escape hatch actually usable for compiled Python bindings (FreeCAD now; Geant4/ROOT bindings later).

---

# [Comment #1]() by [c-vigo]()

_Posted on July 14, 2026 at 09:34 AM_

Implemented in #1048 (merged to dev): `mkProjectShell` accepts `python ? pkgs.python314`; `UV_PYTHON` derives from `python.executable`; an override also wins bare `python3` on PATH (conditional hook — the default shell stays byte-identical, drvPath-parity-tested). Documented in docs/MIGRATION.md with the FreeCAD ABI example. The FreeCAD import acceptance criterion is exercised by the #1040 Phase-0 spike, not devkit CI.

