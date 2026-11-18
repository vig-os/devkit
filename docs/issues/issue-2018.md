---
type: issue
state: open
created: 2026-11-03T22:05:54Z
updated: 2026-11-03T22:05:54Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/2018
comments: 0
labels: none
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-11-04T08:54:30.958Z
---

# [Issue 2018]: [mkRustProject: forward mkProjectShell's `python` argument (#1038) so Rust-pack dev shells can pin the tools' interpreter](https://github.com/vig-os/devkit/issues/2018)

`mkProjectShell` takes a `python` argument (#1038): it sets `UV_PYTHON`, and it puts that interpreter first on PATH. `vig.lib.mkRustProject` (`nix/mk-rust-project.nix`, 1.19.0-rc1 and main) neither accepts nor forwards that argument. So every Rust-pack dev shell runs `python3` and `uv run` under the pinned `python314`, with `UV_PYTHON_DOWNLOADS=never`.

**Effect downstream (gerchowl/nodd#146):**
- The repo's Python tools declare 3.13, which is nixpkgs `python3`, and `.python-version` says so.
- The flake checks run the tools under `pkgs.python3` (3.13.15).
- `just test` inside `nix develop` runs them under 3.14.7, because `UV_PYTHON` beats `.python-version`.

**Workaround in nodd:**
- `shellEnv.UV_PYTHON = "${pkgs.python3}/bin/python3.13"`;
- a `shellHook` that prepends `${pkgs.python3}/bin` to PATH (it also has to repeat the default "loaded" echo);
- a flake check that this holds.

**Ask:**
- add `python ? null` to `mkRustProject`;
- forward it to `mkProjectShell` when it is non-null;
- document it next to `shellEnv`.

A consumer could then pass `python = pkgs.python3;` and drop the override.

