---
type: issue
state: open
created: 2026-11-26T23:06:38Z
updated: 2026-11-26T23:06:38Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/2094
comments: 0
labels: none
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-11-27T10:43:41.268Z
---

# [Issue 2094]: [Adopting into an existing Nix-flake repo (solo, direnv): first-render leftovers, preserved flake.nix without hook tooling, language detection](https://github.com/vig-os/devkit/issues/2094)

Found while adopting devkit 1.19.2 (e93420926f) into an existing Nix-flake repo (nerdmachines/ee: own `flake.nix` with packages, checks and a devShell; Python under `python/` with no `pyproject.toml`; a Rust workspace under `crates/`). Commands: `install.sh --force --preview`, then `--force --mode direnv --workflow trunk`, then the solo keys from docs/SOLO_ADOPTION.md, then `--force` again. Then `prek run --all-files` inside the devkit dev-shell.

1. **Solo keys can only be set after a full render, and that render leaves files behind.** `DEVKIT_FEATURES_DISABLED`, `DEVKIT_REFS_POLICY` and `DEVKIT_LICENSE` are manifest-only. So the first `--force` adds LICENSE (Apache-2.0), CHANGELOG.md and the release workflows. Setting `DEVKIT_LICENSE=none` afterwards does not remove that LICENSE: by design it "never deletes a license". A private solo repo therefore ends up carrying an Apache-2.0 LICENSE unless the adopter notices and deletes it by hand. SOLO_ADOPTION.md says a `--profile solo` flag is "tracked against #1285", but #1285 is closed. Ask: accept these keys as flags or env on the first render (e.g. `DEVKIT_LICENSE=none install.sh …`, or `--profile solo`), or have `--preview` honour a pre-seeded `.vig-os`.
2. **When `flake.nix` is PRESERVED in direnv mode, the hooks are wired to a shell that can't run them.** `.githooks/pre-commit` runs `prek run` once `IN_NIX_SHELL` is set, and the consumer's own dev-shell sets that without providing `prek`, ruff, typos and the rest. So every commit fails with `prek: command not found`, and nothing in the install output says so. The preview lists `flake.nix` as preserved but gives no hint that the preserved flake must adopt `mkProjectShell` (or add the hook toolchain) for the scaffold to work. Ask: a notice, or a check, when a preserved flake's devShell does not provide the hook tools, linking the migration doc.
3. **`DEVKIT_REPO=OWNER/REPO` when origin is a local path.** The scratch clone's origin was a filesystem path, and the manifest got the placeholder silently. A warning would help, since renovate and CI read the value.
4. **`detect-private-key` flags a test fixture.** The repo's secrets tests embed a PEM header as an input to its own credential detector. Ask: document the sanctioned exclude mechanism for that hook in `.pre-commit-config.yaml`, or point to `justfile.project`.
5. **`DEVKIT_LANGUAGES` detection.** It seeded only `nix`: there's no root `pyproject.toml`, and Cargo lives at `crates/Cargo.toml`. Does the Rust pack detect a workspace that isn't at the root? The SOLO doc says "with a Cargo.toml present", which suggests root only. Ask: detect `*/Cargo.toml` workspaces, or document the declaration.

Not blocking. The first-run hook results on this repo: ruff, ruff-format, nixfmt, pymarkdown, typos and end-of-file auto-fixes plus around 30 manual items. That's reasonable, and the hook stack is the reason for adopting.

