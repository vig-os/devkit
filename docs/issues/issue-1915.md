---
type: issue
state: open
created: 2026-10-26T18:26:23Z
updated: 2026-10-26T18:42:35Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1915
comments: 0
labels: feature
assignees: none
milestone: 1.19.0
projects: none
parent: none
children: none
synced: 2026-10-27T07:38:04.771Z
---

# [Issue 1915]: [gh-app-provision: org secrets with selected-repo visibility, Nix access-tokens recipe, flake app](https://github.com/vig-os/devkit/issues/1915)

Follow-up to #1909, which ships the `gh-app-provision` CLI (vig-utils) and its docs and skill. This issue covers the extensions listed in #1909's proposal item 3, split out so the port can land first.

**Scope**
1. **Org secrets with selected-repo visibility:** `--org-secret --repos a,b` writes the App credentials as organization secrets visible to the listed repositories, as an alternative to repo secrets. Uses `gh secret set --org <owner> --visibility selected --repos ...`. Never print or write the PEM.
2. **Nix recipe:** document how a workflow puts the App token into `NIX_CONFIG` as `access-tokens = github.com=<token>`. The recipe appends to the existing value rather than replacing it, consistent with #1907. Docs page next to the #1909 docs.
3. **Flake app wrapper** (`nix run github:vig-os/devkit#app-provision`), so the tool runs without vig-utils installed.

**Acceptance**
- Tests: `--org-secret --repos` issues the right `gh` calls (mocked) and no secret appears in the output.
- A docs page section for the Nix recipe.
- `nix run .#app-provision -- --dry-run ...` prints the manifest.

Refs #1909.

