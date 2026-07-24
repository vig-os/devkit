---
type: issue
state: closed
created: 2026-07-21T07:26:30Z
updated: 2026-07-21T11:59:04Z
author: swiss-chemist
author_url: https://github.com/swiss-chemist
url: https://github.com/vig-os/devkit/issues/1230
comments: 1
labels: none
assignees: none
milestone: 1.4.1
projects: none
parent: none
children: none
synced: 2026-07-22T05:26:40.635Z
---

# [Issue 1230]: [mkProjectShell: Python env in extraPackages is silently shadowed by the builder's bare python](https://github.com/vig-os/devkit/issues/1230)

## Summary

A `pythonXX.withPackages` environment passed to `mkProjectShell` via `extraPackages` is
silently shadowed by the builder's own bare `python`. The consumer gets the pinned 3.14
interpreter on `PATH` with none of their libraries, and there is no error or warning —
the shell builds and loads normally, and the breakage only surfaces later as
`ModuleNotFoundError` in an unrelated script.

This is the natural way to add Python libraries to a project shell (`extraPackages` is
documented as "your project tools go here" in the scaffolded `flake.nix`), so it is easy
to land in and hard to diagnose.

## Reproduction

Minimal flake, no other project content, pinned to `3e0b8c3`:

```nix
{
  inputs.vigos.url = "github:vig-os/devkit/3e0b8c3620fdc8f2fe25cdabc1877d2d39cd34ec";
  outputs = { self, vigos, ... }:
    let
      system = "x86_64-linux";
      pkgs = import vigos.inputs.nixpkgs {
        inherit system;
        overlays = [ vigos.overlays.default ];
        config.allowUnfree = true;
      };
      pyEnv = pkgs.python313.withPackages (ps: [ ps.numpy ]);
    in {
      devShells.${system} = {
        a = vigos.lib.mkProjectShell { inherit pkgs; extraPackages = [ pyEnv ]; };
        b = vigos.lib.mkProjectShell { inherit pkgs; python = pkgs.python313; extraPackages = [ pyEnv ]; };
        c = vigos.lib.mkProjectShell { inherit pkgs; python = pyEnv; };
      };
    };
}
```

```console
$ nix develop .#a -c python3 -c 'import numpy'
ModuleNotFoundError: No module named 'numpy'
```

| variant | config | `python3 --version` | `import numpy` |
|---|---|---|---|
| **a** | `extraPackages = [ pyEnv ]` | 3.14.4 | ❌ `ModuleNotFoundError` |
| **b** | `python = python313` + `extraPackages` | 3.13.13 | ✅ (but see caveat) |
| **c** | `python = pyEnv` | 3.13.13 | ✅ |

## Root cause

`mkProjectShell` unconditionally appends the bare interpreter to `packages`
(`flake.nix:549-555`):

```nix
packages = (devTools pkgs) ++ [ python ] ++ extraPackages ++ modulePackages;
```

`python` defaults to `pkgs.python314` and precedes `extraPackages`, so its `bin/python3`
wins the `buildEnv` symlink race against the consumer's env.

`pythonOverrideHook` (`flake.nix:524-526`) exists to fix exactly this class of shadowing,
but it is gated on the interpreter having been overridden:

```nix
pythonOverrideHook = pkgs.lib.optionalString (python != pkgs.python314) ''
  export PATH="${python}/bin:$PATH"
'';
```

With the default interpreter the hook is empty, so a consumer who only wants to *add
libraries to the pinned Python* — without changing the interpreter version — has no
supported path at all.

## Caveat on variant **b**

**b** appears to work but does so by accident. `type -a python3` resolves to the *bare*
`python3-3.13.13`, not the `-env`:

```
python3 is /nix/store/…-python3-3.13.13/bin/python3        ← prepended by pythonOverrideHook
python3 is /nix/store/…-python3-3.14.4/bin/python3
python3 is /nix/store/…-python3-3.13.13/bin/python3
```

`numpy` imports only because nixpkgs' Python setup hook puts the env's `site-packages` on
`PYTHONPATH`, and the two happen to share an ABI. Change either side of that coincidence
(different CPython minor for the env vs. the override) and it breaks — silently again, in
the other direction. So the documented #1038 override is not a reliable fix for this case.

## Suggested fixes

Any one of these would close it; roughly in order of preference:

1. **Let `extraPackages` win**: order `extraPackages` before the bare `python` in
   `packages`, or apply `lib.lowPrio` to the builder's `python` the way `vig-utils`
   already is in `nix/devtools.nix:36`. That makes the natural spelling correct.
2. **Detect and fail loudly**: if any entry of `extraPackages` provides `bin/python3`,
   abort evaluation with a message pointing at the `python` argument. Silence is the
   worst part of this bug.
3. **Document `python = pyEnv`** (variant **c**) as *the* way to add Python libraries.
   It works today, resolves the env directly rather than relying on `PYTHONPATH`, and
   keeps `UV_PYTHON` consistent — but nothing currently suggests passing a `withPackages`
   env as the `python` argument, and the `#1038` comment reads as version-override only.

Happy to send a PR for whichever you prefer.

## Environment

- devkit `3e0b8c3620fdc8f2fe25cdabc1877d2d39cd34ec`
- nixpkgs `3426825` (via `vigos/nixpkgs`)
- Determinate Nix 3.21.7 (Nix 2.34.8), x86_64-linux

---

# [Comment #1]() by [c-vigo]()

_Posted on July 21, 2026 at 11:59 AM_

Fixed on dev via PR #1246 (merge commit ba0c7706). Root cause differed from the proposal: the shadowing came from vig-utils' propagated pinned 3.14 interpreter via its Python setup hook, not from packages-list order — reordering/dropping the bare python did not fix it. The builder now PATH-prepends any extraPackages-provided withPackages env in the shellHook, before pythonOverrideHook so an explicit python override still wins. Proven by a real-build test (RED reproduced the ModuleNotFoundError). Ships with 1.4.1.

