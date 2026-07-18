---
type: issue
state: closed
created: 2026-07-17T11:28:35Z
updated: 2026-07-17T11:57:22Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1178
comments: 1
labels: feature, priority:high, area:workspace, effort:small, semver:minor
assignees: none
milestone: Backlog
projects: none
parent: none
children: none
synced: 2026-07-18T04:54:25.853Z
---

# [Issue 1178]: [docs capability module: typst toolchain for document-oriented consumers](https://github.com/vig-os/devkit/issues/1178)

### Description

Add a `docs` capability module (`nix/modules/docs.nix`) providing the document-edition toolchain — `typst` and `typstyle` — so document-oriented consumers opt in with `mkProjectShell { modules = [ "docs" ]; }`.

### Problem Statement

exo-pet/vault (the EXOPET documentation vault, direnv-only deployment in the current wave) needs `typst` in its dev shell; today it gets it via a PyPI pin (`typst==0.15.0`) inside the old devcontainer image. It will not be the only such consumer: the future `qms` app consumes vault's content, and EXOMA holds presentations/grants with the same document-edition profile. Per ADR-capability-modules, modules are ask-gated until a concrete consumer asks — vault is that consumer.

Adding typst to base `devTools` is the wrong shape: it would land in every consumer's shell and the image (recently slimmed 2.14→1.53 GiB, #1103), while code repos have zero use for it. The v1 module contract (packages + env + shellHook) fits exactly, like `node`.

### Proposed Solution

- `nix/modules/docs.nix`: puts `typst` and `typstyle` on the dev-shell PATH. No version option in v1 — nixpkgs carries a single typst per pin; the module tracks the toolchain pin (document this).
- Register in `nix/modules/default.nix`; document in `docs/NIX.md` (capability modules section), including the deliberate v1 exclusions: pandoc/LaTeX (ask-gated), headless drawio/excalidraw export (electron-shaped, repo-owned), and Python doc-processing libs (`pymupdf4llm`, `openpyxl` — these belong in the consumer's own `pyproject.toml` via uv, not in the module).
- Tests following the `node` module's existing test pattern.

### Alternatives Considered

- **Base devTools**: rejected — image/shell bloat for non-doc consumers (see above).
- **Per-repo `extraPackages`**: works (it was the initial plan for vault) but re-wires the same need in every doc-oriented repo; the module is the DRY point now that multiple consumers are foreseeable.
- **Pinning typst 0.15.0 via overlay**: deferred — typst output is not stable across versions, so vault's migration includes a one-time regeneration commit of its `generated/` artifacts under the toolchain typst; tracking the pin beats maintaining a bespoke version.

### Additional Context

From the vault deployment discussion (2026-07-17). Related: ADR-capability-modules, #1027 (node module), #1103 (image slimming). A scaffolded docs justfile.project seed is deliberately out of scope until the recipe pattern appears in a second consumer (DRY rule).

### Impact

- Opt-in only; zero change for consumers not declaring the module. Backward compatible (semver:minor).

### Changelog Category

Added
---

# [Comment #1]() by [c-vigo]()

_Posted on July 17, 2026 at 11:57 AM_

Shipped via PR #1179, merged to `dev` (dev-PR `Closes` does not auto-close — closing manually). Reaches consumers with the next devkit release; vault opts in with `modules = [ "docs" ]` at migration.

