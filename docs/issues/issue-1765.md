---
type: issue
state: open
created: 2026-09-29T12:59:21Z
updated: 2026-09-29T16:01:15Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1765
comments: 3
labels: feature
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-09-30T08:17:46.241Z
---

# [Issue 1765]: [[FEATURE] devkit plugin: guided reproducible first-setup (/devkit:init), coverage-gated against devkit's SSoTs, discoverable to agents](https://github.com/vig-os/devkit/issues/1765)

### Description

Extend the `devkit` Claude Code plugin (#1744) so an agent can take a repo from empty to a fully configured devkit consumer **reproducibly**. That means a guided first-setup skill that walks the *whole* option surface, applies it and verifies it. The plugin's coverage of devkit's features should be **drift-gated** by a hook/CI check so it cannot fall behind new knobs, modules or feature groups. And the plugin should be **discoverable** by an agent that is only looking at the devkit repo (or a scaffolded consumer).

Companion: a `/devkit:elevate` review-loop skill that mines a consumer repo (and its agent transcripts) for local tooling that should be promoted into a devkit module/extension. It is being prototyped in vig-os/revkit (link below).

### Problem Statement

`/devkit:adopt` is deliberately a read-only proposal, and its decision table covers `--mode`, `--workflow`, `--version`, identity and the release group. First setup actually needs every one of the following, and today an agent can only find them by reading `docs/MIGRATION.md`, `docs/NIX.md`, `docs/SOLO_ADOPTION.md`, `nix/modules/` and `init-workspace.sh`:

- the ~25 `.vig-os` manifest keys (`DEVKIT_FEATURES_DISABLED`, `DEVKIT_REFS_POLICY`, `DEVKIT_LICENSE`, `DEVKIT_MODULES`, `DEVKIT_CI_RUNNER`, …)
- the capability modules (`native`, `node`, `docs`, `guardrails`, `rust` via `mkRustProject`) and their options
- the nine feature groups, the solo profile, flake `hooks`/`hooksExcludes`, and `mkProjectServices`

Nothing ties the plugin to those sources of truth. A module or manifest key added next release is invisible to the skills until someone remembers to update them.

**Observed on a real first setup (vig-os/revkit, devkit 1.17.0, `--mode direnv`, 2026-09-29).** Each item below is friction a guided skill would have absorbed or a gate would have caught:

1. **The installer hard-requires the container image, even for `--mode direnv`.** `install.sh` pulls `ghcr.io/vig-os/devcontainer:<ver>` to run `init-workspace.sh`. Anonymous pulls (and pulls with a `gh` token lacking `read:packages`) return **403** here, for both `devcontainer:*` and `devkit:*`, so a Nix-only host has no install path. The workaround is to run `init-workspace.sh` from a tag checkout with `TEMPLATE_DIR=… VERSION_FILE=… WORKSPACE_DIR=…`. That path works but is undocumented, and it also skips `install.sh`'s git bootstrap (`git init -b main`, initial commit, `dev` branch). `apps.install` wraps `install.sh`, so it presumably has the same dependency.
2. **Flakes not enabled on the host** → `nix develop` / `use flake` fails with `experimental Nix feature 'flakes' is disabled`. Neither the installer nor `just doctor` preflights this.
3. **`prek install` clobbers the managed hook.** With `core.hooksPath=.githooks`, running `prek install` rewrites `.githooks/pre-commit` and moves the managed one to `pre-commit.legacy`. Agents reach for `prek install` by reflex; nothing tells them the hooks are already wired.
4. **Pin lockstep is manual.** The scaffold floats `vigos.url` while `.vig-os` pins `DEVKIT_VERSION`; aligning `?ref=<DEVKIT_VERSION>` is a hand edit (related: #1756).
5. **`DEVKIT_MODULES` and `modules = [ … ]` are hand-mirrored** in `.vig-os` and `flake.nix` with no check that they agree.
6. **`guardrails` is on PATH but enforces nothing.** `nix/modules/guardrails.nix` says *"hook ENTRIES are rendered by the installer from `DEVKIT_MODULES`"*, but at 1.17.0 neither `install.sh`, `init-workspace.sh` nor `nix/hooks.nix` references the gates. A consumer enabling the module gets 15 gates on PATH and zero hooks running them: the exact *configured, believed active, enforcing nothing* failure the module's header warns about. (revkit wires them by hand as flake custom hooks.)
7. **`no-fake-impl` / `no-debug-leftovers` patterns are Rust-first.** On a `.ts` file, `// TODO: implement` + `throw new Error("not implemented")` passes `no-fake-impl`. For `node` consumers the gate is mostly silent.

### Proposed Solution

**1. `/devkit:init`, a guided, reproducible first setup.** It does not replace `adopt`; it is the apply half that follows it.

- Step 1 is `/devkit:status`, per the plugin's state-lookup-first principle.
- It walks the **full** option surface as questions (mode, workflow, identity, license, feature groups/solo profile, Refs policy, modules + options, `extraPackages`, services, CI runner). Each question has a recommended default and a one-line consequence. The question set is **generated from the SSoTs** (see 2), not hand-kept.
- It records answers as the `.vig-os` manifest and flake edits, so rerunning the skill (or `install.sh --force`) reproduces the same repo with no prompts.
- It applies on a clean tree, pins `vigos.url` to `DEVKIT_VERSION`, mirrors `DEVKIT_MODULES` into `modules`, and wires hook entries for hook-bearing modules (item 6).
- It verifies with `nix develop -c prek run --all-files` and a commit-msg dry run, then hands back what was *not* done (repo creation, App secrets, branch protection).
- It preflights items 1–3: image reachability with a fallback to a documented host path, flakes enabled, and never `prek install`.

**2. Self-guarding: a plugin-coverage gate.** Same pattern as `module-<name>` checks ("a module cannot ship without its check"):

- A check (prek hook + `nix flake check` entry) enumerates the SSoTs: `MANIFEST_*` keys read by `init-workspace.sh` (or the MIGRATION.md key table), `nix/modules/` registry entries and their `knownOptions`, feature groups, `install.sh`/`init-workspace.sh` flags, and exported `lib.*` builders.
- It fails when any of them is not covered by the plugin: the `/devkit:init` question manifest, or an explicit `not-user-facing` allowlist entry with a reason.
- It also asserts `plugin.json` version == `DEVKIT_VERSION`, which the release step already does.

**3. Discoverability for agents looking at devkit itself.**

- A top-of-file pointer in devkit's `CLAUDE.md`, plus an `AGENTS.md` for non-Claude agents: *"To adopt or configure devkit in another repo, use the `devkit` plugin: `/plugin marketplace add vig-os/devkit@<ver> --sparse .claude-plugin plugins`."*
- A "For agents" section at the top of the README (generated from `docs/templates/README.md.j2`), and an `llms.txt` at the repo root listing the plugin, the skills and the SSoT docs.
- A scaffolded consumer `.claude/settings.json` with `extraKnownMarketplaces` + `enabledPlugins` for `vigos-devkit@<DEVKIT_VERSION>`, so a consumer session offers the plugin automatically and the pin moves with upgrades. This is related to #927's plugin-distribution direction.
- The installer's closing message names `/devkit:status` and `/devkit:init`.

**4. `/devkit:elevate`, the review loop (prototype in vig-os/revkit).** A read-only skill run in a consumer: it inventories local tooling (`extraPackages`, custom flake hooks, `justfile.project` recipes, repo scripts, non-managed workflows) and mines agent transcripts for repeated workarounds. It dedupes against devkit's modules and open issues, then proposes module/extension/scaffold/hook promotions with evidence. `bun` in revkit's `extraPackages` is the first candidate (a `bun` module, or a `runtime` option on `node`).

### Alternatives Considered

- **Extend `/devkit:adopt` to apply.** This conflicts with its documented read-only contract and its model-invocable safety argument. A separate, user-invoked `init` keeps that boundary.
- **Hand-maintained option list in the skill.** This is the drift the issue exists to prevent. Rejected unless it is covered by the coverage gate.
- **Docs-only discoverability.** Agents don't read `docs/MIGRATION.md` before acting; the pointer has to be in `CLAUDE.md`/`AGENTS.md`/`llms.txt` and in the consumer's settings.

### Additional Context

- Plugin: #1744 (merged in #1751). Org plugin distribution: #927. Flake pin drift on upgrade: #1756. Guardrails packaging: #1572.
- revkit adoption commit and tracking issue: see the vig-os/revkit link in the first comment.

### Impact

- Every new consumer: setup becomes one guided, repeatable run instead of doc archaeology plus workarounds.
- Plugin/devkit drift turns into a red check instead of a silent gap.
- Fixes needed alongside: the direnv install path without the image (1), guardrails hook rendering (6), TS patterns for the gates (7). These could be split into child issues if preferred.

### Changelog Category

Added

---

# [Comment #1]() by [gerchowl]()

_Posted on September 29, 2026 at 01:00 PM_

Adoption that surfaced this: vig-os/revkit (scaffold commit on `main`, devkit 1.17.0 direnv). The consumer-side `/devkit:elevate` prototype and its ledger: vig-os/revkit#1.

---

# [Comment #2]() by [gerchowl]()

_Posted on September 29, 2026 at 01:07 PM_

Measured AX cost of the setup that produced this issue, plus a proposal to eval-gate it: #1766.

---

# [Comment #3]() by [gerchowl]()

_Posted on September 29, 2026 at 04:01 PM_

Found while wiring the plugin into vig-os/revkit: `plugins/devkit/README.md` tells consumers to `/plugin marketplace add vig-os/devkit@1.17.0`, but **1.17.0 ships no `.claude-plugin/marketplace.json`**. The plugin (#1751) landed on `dev` after the tag, and `main` doesn't have it either. The add fails with `Marketplace file not found …/.claude-plugin/marketplace.json`.

Two consequences for this issue:
- The "pin to `DEVKIT_VERSION`" guidance only holds from the first release that contains the plugin. Until then, discovery points at a ref that 404s. `/devkit:status` (or the README) should say which release first ships it.
- **`.claude/settings.json` is not in `PRESERVE_FILES`**, so a consumer can't durably commit `extraKnownMarketplaces`/`enabledPlugins` there: the next `--force` upgrade drops it. The scaffold should render them (proposal 3 above), or preserve a project-owned settings seam.

revkit's workaround is `just claude-plugin [ref]`: local scope, pinned to `DEVKIT_VERSION`, and it checks that the ref ships the plugin (vig-os/revkit#14).

