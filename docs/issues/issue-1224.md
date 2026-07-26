---
type: issue
state: closed
created: 2026-07-20T16:42:21Z
updated: 2026-07-21T07:51:04Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1224
comments: 1
labels: bug
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-07-22T05:26:42.646Z
---

# [Issue 1224]: [Flake-generated pre-commit branch guard is not workflow-model-aware](https://github.com/vig-os/devkit/issues/1224)

Found during the first live trunk switches (exo-pet/vault#31). `render_workflow_model()` rewrites the branch-guard regex (drops the `(?!dev$)` clause) only in the scaffolded `.pre-commit-config.yaml`; its `[[ -f ]]` guard correctly skips when the consumer uses flake-generated hooks (`hooks = { };` → store symlink), so every direnv consumer that opted into flake hooks (#1167 default) keeps `^(?!main$)(?!dev$)…` after switching to `DEVKIT_WORKFLOW=trunk`.

Impact: inert — the residual clause protects a branch trunk repos do not have; `main` protection and the type prefixes still work. But the pattern should follow the workflow model for correctness and to avoid confusing future readers.

Suggested fix: make the mkProjectShell hook definition read the workspace `.vig-os` `DEVKIT_WORKFLOW` (or accept a workflow argument) and emit the guard pattern accordingly, mirroring the scaffold render. Add a trunk-mode flake-hooks case to the workflow-model test matrix (`tests/test_workflow_model.py` covers only the scaffolded-file path today).

Dev-targeted polish, not urgent (no functional breakage).

Refs: #1205, #1167
---

# [Comment #1]() by [c-vigo]()

_Posted on July 21, 2026 at 07:51 AM_

Fixed by PR #1231, merged to dev @436e7b59 (dev-targeted PRs don't auto-close). mkProjectShell now takes a validated `workflow` argument and the scaffolded consumer flake forwards `DEVKIT_WORKFLOW` from `.vig-os`. Note for existing trunk consumers (vault, exo-fleet): the preserved `flake.nix` needs a re-scaffold or a one-line `workflow = "trunk";` to pick this up — residual clause is inert meanwhile. Ships with 1.4.1.

