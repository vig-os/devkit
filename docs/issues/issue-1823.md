---
type: issue
state: open
created: 2026-10-05T13:36:16Z
updated: 2026-10-05T13:36:16Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1823
comments: 0
labels: bug, area:workspace, area:workflow
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-10-06T08:51:01.665Z
---

# [Issue 1823]: [Release-train just recipes are devcontainer-only, so the 1.18.0 plugin skills break in direnv/bare mode](https://github.com/vig-os/devkit/issues/1823)

### Description

The `devkit` Claude Code plugin skills added in 1.18.0 (#1744) wrap the
release-train `just` recipes and explicitly forbid dispatching the workflows
directly. Those recipes are defined only in `.devcontainer/justfile.gh`, which
`direnv` and `bare` mode never ship — so every mutating release skill is
unusable in the two container-less modes.

`plugins/devkit/skills/release-prepare/SKILL.md`:

> The recipe dispatches `prepare-release.yml`. Do not call `gh workflow run`
> directly and do not reimplement the …

while `init-workspace.sh` excludes the whole directory for those modes:

```bash
if [[ "$MODE" == "direnv" || "$MODE" == "bare" ]]; then
    MODE_CONFIG_EXCLUDES+=(".devcontainer" "docs/container-ci-quirks.md")
fi
```

`tests/test_devkit_plugin.py` is mode-blind here: it asserts a skill's named
recipe exists "in devkit or in the scaffold", and devkit's own repo-root
`justfile` is not what a `direnv` consumer gets. So the guard passes while the
rendered `direnv` consumer has no `prepare-release` recipe at all.

The same gap hits `/devkit:release-candidate`, `-finalize`, `-promote`,
`-abandon`, `-hotfix`, `-neutral` and `/devkit:status` wherever it reports on
recipes.

### Steps to Reproduce

1. Scaffold or upgrade a consumer with `--mode direnv` (or `bare`).
2. Install the plugin marketplace pinned to `1.18.0` and
   `/plugin install devkit@vigos-devkit`.
3. Run `/devkit:release-prepare`.
4. The skill's canonical command `just prepare-release <version>` fails:
   `just` has no such recipe. The repo-root `justfile` carries only `help`,
   `doctor` and `with-native-libs`.

### Expected Behavior

Either the release-train recipes are reachable in every delivery mode, or the
skills degrade to the workflow dispatch they currently forbid, or the skills
declare a mode precondition and refuse with an explanation (consistent with the
explicit refusal tables they already carry for other foot-gun states).

### Actual Behavior

The skills name recipes that do not exist in `direnv`/`bare` mode, and the
plugin test suite does not catch it.

### Environment

- devkit `1.18.0`
- Affects `DEVKIT_MODE=direnv` and `DEVKIT_MODE=bare`
- Found while planning a `0.3.4` → `1.18.0` consumer upgrade that moves to
  `direnv` mode (the consumer needs a project `flake.nix` for a native library
  the image cannot carry)

### Additional Context

The *workflows* are fine — all 17 are scaffolded in every mode, and 1.18.0 made
the release/automation set mode-aware. This is purely about the local `just`
front-end the skills depend on.

Worth noting the recipes themselves are thin dispatchers: `prepare-release` is
~8 lines of `gh workflow run` with a `dev` ref default. A consumer can vendor
them into `justfile.project`, but then every consumer in a container-less mode
carries its own copy of a devkit-owned contract — which is the per-repo drift
model #927 exists to retire.

### Possible Solution

Move the mode-independent recipes out of `.devcontainer/justfile.gh` into the
repo-root `justfile` (or a new always-shipped `justfile.release`), leaving
genuinely container-specific recipes in `justfile.devc`. The release recipes
only need `gh`, which every mode provides. `justfile.worktree` is a separate
question — it is substantial and arguably is container-shaped.

A smaller fix: make `tests/test_devkit_plugin.py` resolve recipes against each
*rendered mode's* justfile set rather than the union, so the gap fails the suite.
The new consumer matrix (#1762) already renders `direnv` and `bare` cells and
could host that assertion.

### Changelog Category

Fixed

