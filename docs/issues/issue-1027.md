---
type: issue
state: closed
created: 2026-07-14T07:22:13Z
updated: 2026-07-14T09:01:22Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1027
comments: 2
labels: feature, priority:medium, area:workspace, effort:large, semver:minor
assignees: none
milestone: Backlog
projects: none
parent: none
children: none
synced: 2026-07-14T20:06:34.094Z
---

# [Issue 1027]: [[feature] node/typescript capability module (+ language-aware scaffold for npm recipes/gitignore/hooks/codeql)](https://github.com/vig-os/devkit/issues/1027)

### Description

The commit-action direnv pilot (vig-os/commit-action#32) needed Node/TypeScript
support, which today has to be **hand-wired** in every consumer:

- `extraPackages = [ pkgs.nodejs ]` in the flake
- npm-mapped `justfile.project` recipes (`sync`=`npm ci`, `lint`, `test`, `build`,
  `bundle`)
- Node/Action `.gitignore` fragment (`node_modules/`, `*.tsbuildinfo`,
  `coverage/`; and *not* blanket-ignoring `dist/`) — see #1024
- `codeql.yml` language `javascript-typescript` instead of `python` — see #1025
- (missing today) eslint/prettier pre-commit hooks

`sync-issues-action` — and every future TS action — needs the byte-identical
setup. This asks for a **`node` (and/or `typescript`) capability module** so a
consumer opts in with `modules = [ "node" ]` (`DEVKIT_MODULES` in `.vig-os`)
instead of copy-pasting the above.

### Key design question (raise before implementing)

Per `docs/rfcs/ADR-capability-modules.md`, a v1 module is **packages + env +
shellHook only**. That means a `node` module can put `nodejs` in the dev-shell —
but it **cannot** by itself provide the npm `justfile` recipes, the `.gitignore`
fragment, the pre-commit hooks, or the `codeql` language. Those are scaffold
files, not shell contributions.

So turnkey Node support spans **two mechanisms**:

1. **The shell module** (v1): `nodejs` (+ optional `pnpm`/`yarn`) in
   `mkProjectShell`, with a **selectable Node version** — the pilot used
   `pkgs.nodejs` (24) while the action runtime is `node20` (`action.yml`); the
   module should let a consumer pin to their runtime.
2. **Language-aware scaffold** (needs a decision): npm `justfile.project` recipes,
   the Node `.gitignore` fragment (#1024), eslint/prettier pre-commit hooks, and
   `codeql` language (#1025) — either by **extending the module contract** so
   modules can contribute scaffold fragments, or by a **language-aware scaffold**
   keyed on `package.json` that the module composes with.

Decide (1) alone (shell packages only, leave the rest to #1024/#1025 + manual) vs
(1)+(2) (a true "flavour" that ships everything). The pilot shows (2) is where
the real per-repo toil is.

### Acceptance criteria (proposed)

- [ ] `modules = [ "node" ]` puts a version-selectable Node (+ npm) in the shell,
      stacking cleanly with other modules.
- [ ] Decision recorded on whether the module also drives npm recipes / gitignore
      / hooks / codeql, or those stay in a language-aware scaffold.
- [ ] `commit-action` and `sync-issues-action` can drop their hand-wired
      `extraPackages`/recipes in favor of the module.

### Related

Capability modules #884; scaffold language-awareness #1024 (.gitignore), #1025
(codeql.yml). Pilot: vig-os/commit-action#32.

---

# [Comment #1]() by [c-vigo]()

_Posted on July 14, 2026 at 08:00 AM_

## Design decision (pre-implementation)

Per `docs/rfcs/ADR-capability-modules.md`, the answer to the key design question is **(1) + (2), but split across the two mechanisms the codebase already has** — no module-contract extension:

1. **Shell module (v1 contract, this issue):** a `node` module in `nix/modules/` contributing `nodejs` (+ npm) as packages. Version selection uses the ADR's recorded migration path — `modules` accepts an attrset entry alongside plain strings: `{ name = "node"; version = 20; }` (plain `"node"` = nixpkgs default). #1027 is the "first module that needs it", so this lands the per-module-options mechanism the ADR deferred. Per the ADR, each new module ships with its generated `checks.<system>.module-node` flake check plus a `tests/test_flake_modules.py` smoke test.

2. **Scaffold pieces (already landing separately):** language-aware scaffold rendering now exists in `init-workspace.sh` (`DETECTED_LANGUAGES`, keyed on `package.json` etc.) via #1024/#1025 (PR #1035), and the release bundle step via #1029 (PR #1033). What remains in scope here is seeding npm-mapped recipes into `justfile.project` **only at first scaffold** (it is a preserved, consumer-owned file) when node is detected — plus eslint/prettier hooks, which stay out of scope for this issue (they belong with the #883 consumer-hooks seam; will file separately if wanted).

This keeps the v1 module contract intact (packages/env/shellHook only), avoids inventing a scaffold-fragment contract, and still delivers turnkey Node: `modules = [ "node" ]` + automatic language-aware statics + first-scaffold npm recipes.

Acceptance mapping: version-selectable Node ✔ (attrset option); decision recorded ✔ (this comment); `commit-action`/`sync-issues-action` can drop `extraPackages` + hand-written recipes ✔.

---

# [Comment #2]() by [c-vigo]()

_Posted on July 14, 2026 at 09:01 AM_

Implemented in #1042 (merged to dev), per the design decision recorded above: `node` v1 shell module with version selection via the new per-module-options mechanism (`{ name = "node"; version = 22; }`), plus first-scaffold npm `justfile.project` seeding for node-detected consumers. Scaffold statics landed separately via #1024/#1025, release bundling via #1029. eslint/prettier hooks deferred to the #883 seam.

