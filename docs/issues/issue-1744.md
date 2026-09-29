---
type: issue
state: closed
created: 2026-09-28T11:45:32Z
updated: 2026-09-29T00:29:41Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1744
comments: 3
labels: feature
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-09-29T08:16:56.085Z
---

# [Issue 1744]: [[FEATURE] "devkit" Claude Code plugin — /devkit-adopt, /devkit-status, /devkit-release-* skills that wrap the canonical workflows with a state-lookup-first pre-flight](https://github.com/vig-os/devkit/issues/1744)

## Description

Ship a **`devkit` Claude Code plugin** that packages state-aware slash-command skills for **adopting devkit**, **operating the devkit release train**, and **keeping a consumer in sync with devkit**. The plugin is versioned with devkit (so skills cannot drift from the workflows they drive) and distributed through the private marketplace already proposed in #927.

The plugin is a thin operator surface, not a re-implementation: every skill wraps the canonical devkit verbs (`install.sh`, `just prepare-release`, `just publish-candidate`, `just finalize-release`, `just promote-release`, `just abandon-release`, `just prepare-hotfix`, `scripts/sync_manifest.py`) and starts with a read-only state lookup so an agent cannot walk into a foot-gun (another RC open, a draft Release live, `dev` diverged from `main`, tag ruleset in the way, missing Apps/secrets).

## Problem Statement

Adopting devkit and running its release train are **procedural workflows with a large, learnable surface**: `install.sh` flags (`--mode`, `--workflow`, `--force`, `--version`, `--org`), the `.vig-os` manifest keys (`DEVKIT_VERSION`, `DEVKIT_WORKFLOW`, `DEVKIT_TAG_PREFIX`, `DEVCONTAINER_VERSION`), the gitflow-vs-trunk branch topology, the six-verb release cycle, the two repo-owned extension seams (`prepare-release-extension.yml`, `release-extension.yml`), the release-neutral lane, the hotfix lane cut from `main`, the "publishing burns the tag name" immutable-releases hazard (#1301), the legacy-tag hazard when discovering RC numbers, the required GitHub Apps (`RELEASE_APP_*`, `COMMIT_APP_*`), and the promote-time cross-repo validation gate.

Concrete evidence this is a real cost, not theory:

- **tessera adoption was toolchain-only.** vig-os/tessera#442 (merged 2026-09-24) adopts the scaffold **without** the release train because the train's cost was not legible. The full-train question is deferred to vig-os/tessera#441, which enumerates the six blockers a human had to compile by hand (version-series decision, cargo-dist ↔ `release-publish.yml` seam collision, changelog-model habit change, App/secret rotation, legacy-tag hazard, first-promote bootstrap). An informed skill would have surfaced that list from the state, not from a person re-reading the docs.
- **The Rust pack (#1496, #1519) has never been adopted cold** — the L7 template that would make a Rust repo adoptable in one step was never shipped, so every new Rust consumer hand-writes `flake.nix`, `rust-toolchain.toml`, `Cargo.toml` lint tables, `justfile.project`, and can silently green a build of nothing. An `/devkit-adopt` that inspects the repo (languages present, existing CI, existing release tooling) and proposes the manifest + diff makes this failure mode visible before it ships.
- **Release-train foot-guns are already documented one-by-one** as separate issues that all shape the same rules: #1626 (`:latest` never moves backwards), #1627 (refuse `prepare-release` while a hotfix is in flight), #1301 / #1311 (published-release tombstoning), #1497 (upgrade staleness unobservable on both axes), #1642 (workflow-model switch leaves stale guards), #1676 (release-neutral lane). Each of these is a state check a skill should run **before** dispatching, not a lesson each consumer re-learns.
- **Skills today are copied per-repo and drift** (see #927's audit). Distributing them through the same marketplace fixes drift for both the org-Claude payload and the devkit-operator payload with one mechanism.

The gap is not features — it is an **operator surface that knows the current state**.

## Proposed Solution

### Distribution

- Add a `.claude-plugin/` tree to `vig-os/devkit` (co-located with the workflows it drives, so a devkit release cannot ship without also releasing the matching skills):
  ```
  .claude-plugin/
    plugin.json          # id: "devkit", version = devkit's own
    skills/
      devkit-adopt/SKILL.md
      devkit-status/SKILL.md
      devkit-release-prepare/SKILL.md
      devkit-release-candidate/SKILL.md
      devkit-release-finalize/SKILL.md
      devkit-release-promote/SKILL.md
      devkit-release-abandon/SKILL.md
      devkit-release-hotfix/SKILL.md
      devkit-release-neutral/SKILL.md
      devkit-upgrade/SKILL.md
      devkit-pack-rust/SKILL.md    # extension-specific; one per pack
    commands/            # optional slash-command wrappers
    hooks/               # optional; e.g. block release-train verbs on a dirty tree
  ```
- Register the plugin in the marketplace repo agreed under #927 (proposed `vig-os/org-config`). Consumers already run `/plugin marketplace add vig-os/org-config` + `/plugin install`; the `devkit` plugin ships alongside the org-Claude plugin, not instead of it.
- **Versioned with devkit itself.** `plugin.json` version = devkit version. A consumer pinned to `DEVKIT_VERSION=1.10.0` gets the `devkit@1.10.0` skills. `devkit-upgrade` bumps both together. Skills cannot describe a verb that does not exist in the consumer's pinned scaffold.

### Skill catalogue

Every skill starts with a **read-only state lookup** (dry-run by default, apply only after explicit confirmation). Section 1 of every skill is that lookup; no skill mutates before it runs.

- **`/devkit-adopt`** — inspect the target repo (languages via file globs, existing CI under `.github/workflows/`, existing release tooling like release-plz / release-please / cargo-dist / semantic-release, existing `.claude/`, existing pre-commit config, existing Nix flake), map devkit's scaffold and all packs/extensions (Python template, Rust pack per #1496 when it ships, guardrails module, docs capability, workflow-mode gitflow-vs-trunk) to the repo's actual needs, **propose** the `install.sh` invocation + resulting `.vig-os` manifest + the concrete diff, and **flag conflicts** (release-plz ↔ `release-publish.yml`, cargo-dist ↔ `release-publish.yml` per tessera#441 blocker 2, existing `flake.nix` already present, `.gitignore` collisions per #1024, CodeQL matrix collision per #1025). Never auto-applies. Ends by handing the operator the exact `install.sh` line and the follow-up checklist.

- **`/devkit-status`** — pure read-only state, no arguments. Reports:
  - Pinned `DEVKIT_VERSION` in `.vig-os` vs latest tag on `vig-os/devkit`;
  - Scaffold drift (delegates to devkit's own drift check per #1497);
  - Open release PRs (any `release/X.Y.Z` branch, PR draft/ready state);
  - Open/draft **RCs**: which `X.Y.Z-rcN` tags exist for the in-flight base version, highest N, whether the tag has a linked (draft or published) GitHub Release;
  - Pending promotes: has the cross-repo smoke-test gate published a **final** Release for the tag yet? (`promote-release.yml`'s precondition);
  - Hotfix lane state: is a `release/*` branch cut from `main` in flight? (#1627 blocks `prepare-release` when one is);
  - `DEVKIT_WORKFLOW` (gitflow/trunk) and whether the repo's branch topology matches;
  - Legacy-tag hazards: tags outside the current version series that sort above it lexically (the trap tessera#441 flags in blocker 4);
  - Required Apps/secrets present: `RELEASE_APP_CLIENT_ID` / `RELEASE_APP_PRIVATE_KEY`, `COMMIT_APP_CLIENT_ID` / `COMMIT_APP_PRIVATE_KEY`;
  - GHCR immutable-releases setting on the repo (informational; #1301 hazard).
  - Output is stable text a human can scan and an agent can grep — this is the skill every other release-train skill delegates to as step 1.

- **`/devkit-release-prepare X.Y.Z`** — pre-flight `/devkit-status`, refuse (with reason) if any RC is open on a different base version, a hotfix release is in flight (#1627), the working tree is dirty, or `dev` is behind `main`. Then dispatch `just prepare-release X.Y.Z`. End by verifying the release PR opened and `dev`'s Unreleased reset.

- **`/devkit-release-candidate`** — infer version from the current `release/X.Y.Z` branch, refuse if the PR isn't draft or CI isn't green, then dispatch `just publish-candidate`. Verify the `X.Y.Z-rcN` tag pushed and the cross-repo smoke-test dispatch fired. Print the RC number the operator now has to accept downstream.

- **`/devkit-release-finalize`** — refuse if any candidate is still in progress or if the PR is still draft (marking ready is a human act). Dispatch `just finalize-release`. Verify a **draft** GitHub Release was opened for the tag and stop — publishing is the human's single approval, per RELEASE_CYCLE.md phase 5.

- **`/devkit-release-promote`** — refuse if the downstream smoke-test hasn't published a **final** Release for the tag, if `:latest` would move backwards (#1626), or if the draft Release for this version was already deleted (the tombstone trap of #1301). Dispatch `just promote-release`. Verify `:latest` moved, the draft Release published, the release PR merged, and RC cleanup ran.

- **`/devkit-release-abandon`** — refuse if the Release is already published (tombstone risk) or the PR is out of draft. Dispatch `just abandon-release`. Verify the release branch was cleaned up and `dev`'s Unreleased was restored.

- **`/devkit-release-hotfix X.Y.Z`** — refuse if a regular-train `release/*` is in flight (#1627 mirror), or if the trunk-mode repo would take the wrong copy-exclude path (#1625). Dispatch `just prepare-hotfix`. Handoff to `/devkit-release-candidate` and `/devkit-release-finalize`.

- **`/devkit-release-neutral`** — the merge-to-main-without-a-release lane (#1676). Same state pre-flight; verifies the release-neutral guard passes.

- **`/devkit-upgrade`** — dry-run `install.sh --force --version <latest>` on the consumer, show the diff, flag `.vig-os` key changes and workflow-model rendering changes, then apply on confirmation. Delegates to `/devkit-status` for drift observability.

- **`/devkit-pack-rust`** (and one per pack) — extension-specific: check L1/L4/L7 presence per #1496, `justfile.project`'s `test`/`lint` recipes actually compile something (the silent-green trap #1496 opens with), `deny.toml` / `clippy.toml` / `rustfmt.toml` ownership vs guardrails (#1488), `release-extension.yml` wired for crates.io + `cargo set-version --workspace` (tessera#441 blocker 2, once resolved).

### Principles

1. **State-lookup-first.** Every skill's step 1 is `/devkit-status` (or its skill-scoped equivalent). No mutation without a fresh state read in the same run.
2. **Dry-run by default.** Adoption and upgrade never mutate without an explicit second-turn confirmation. Release-train verbs echo the exact `just` line and the state they observed before dispatching.
3. **Skills wrap canonical workflows.** Never re-implement release logic in a skill; only call the `just` verbs and read the state. If a workflow is missing a knob, the fix is a devkit issue against the workflow, not a workaround in the skill.
4. **Versioned with devkit.** Plugin version = devkit release. Cross-version drift is impossible by construction.
5. **Distributed via the #927 marketplace.** One `/plugin marketplace add`, one update path.

## Alternatives Considered

- **Prose in `docs/RELEASE_CYCLE.md` only** (status quo). Works for a careful human; every automated agent has to re-derive the state each time and gets it wrong (see the six-blocker list a human had to compile for tessera#441).
- **Per-repo `.claude/skills/` copies.** This is the drift model #927 exists to retire.
- **A separate `vig-os/devkit-plugin` repo.** Splits the version pin from the workflows the plugin drives — the exact drift #927 is trying to eliminate. Co-locating in `vig-os/devkit` and shipping through the marketplace gives distribution without splitting the SSoT.
- **Fold devkit skills into the org-config plugin (#927).** Possible, but the org-Claude plugin is language/workflow-neutral by design; devkit-operator skills only make sense to a devkit-adopting repo. Two plugins in one marketplace is the cleaner factoring.

## Additional Context

- **Distribution vehicle:** #927 (private marketplace; devkit plugin ships alongside the org-Claude plugin proposed there).
- **Adjacent motivation:** vig-os/tessera#442 (merged: scaffold adopted without the release train) and vig-os/tessera#441 (open: release-train migration decision — the six-blocker list is exactly the state a `/devkit-adopt`+`/devkit-status` pair would report).
- **Extension-pack motivator:** #1496 (Rust pack L1/L4/L7 never shipped) and #1519 (smallest-denominator defaults) — `/devkit-pack-rust` is the operator surface both issues have been missing.
- **Release-train foot-gun issues the skills encode:** #1626, #1627, #1301 / #1311, #1497, #1642, #1676, #1625.
- **Claude Code plugin format reference:** `.claude-plugin/plugin.json`, `skills/<name>/SKILL.md`, `commands/`, `hooks/`, marketplace via `/plugin marketplace add <owner>/<repo>` + `/plugin install`.

## Impact

- **Who benefits:** every devkit consumer (adoption cost drops from re-reading `docs/RELEASE_CYCLE.md` to running `/devkit-adopt`), every agent (release-train mutations can be gated on read-only state, not on prompt discipline), the devkit maintainers (one place to encode a new release-train rule so every consumer picks it up on the next `/devkit-upgrade`).
- **Compatibility:** additive. No change to `install.sh`, no change to the six release verbs, no change to `.vig-os` semantics. Consumers who don't install the plugin see zero behavior change.
- **Rollout:** pilot on `vig-os/devkit` itself (dogfood: run the plugin against devkit's own release train, which is the reference implementation), then a second Rust-consumer pilot when `/devkit-pack-rust` has something to say.

## Acceptance Criteria

- [ ] `.claude-plugin/plugin.json` in `vig-os/devkit`, id `devkit`, version = devkit release version.
- [ ] `skills/devkit-status/SKILL.md` exists and, run against `vig-os/devkit` itself, correctly reports: pinned version, drift, open release PRs, open RCs, pending promotes, workflow model, legacy-tag hazards, App/secret presence.
- [ ] Every `skills/devkit-release-*/SKILL.md` starts with a `devkit-status` step and refuses cleanly (with a reason and an offered next-step verb) on every state that would foot-gun the corresponding `just` verb — including at least: another RC open on a different base, a draft Release deleted (tombstone), `:latest` regression (#1626), hotfix-in-flight collision (#1627), dirty working tree.
- [ ] `skills/devkit-adopt/SKILL.md` produces a diff-only proposal for a repo with no `.vig-os`, and flags a release-tool collision when the repo already ships release-plz or cargo-dist.
- [ ] `skills/devkit-upgrade/SKILL.md` is a dry-run wrapper over `install.sh --force --version <latest>` and refuses to run through a dirty tree.
- [ ] At least one extension-pack skill (`devkit-pack-rust`) exists as a stub tied to #1496, so the extension seam is proven with more than one pack once Rust ships.
- [ ] Plugin appears in the marketplace repo agreed under #927 and installs via `/plugin marketplace add ... && /plugin install devkit`.
- [ ] `plugin.json`'s version is bumped in the same release PR as any workflow change under `docs/RELEASE_CYCLE.md`'s six verbs (drift-prevention gate).

## Open Questions

1. **Marketplace home.** #927 leaves `vig-os/org-config` vs a dedicated `vig-os/claude-plugin` open. The devkit plugin inherits whichever answer #927 lands on; no independent decision needed here.
2. **Command wrappers vs skills.** Ship every skill also as a `commands/<name>.md` slash-command wrapper (belt-and-suspenders discovery), or skills only? Preference: skills only, plus one `README.md` in the plugin listing all `/devkit-*` slash-command names.
3. **Hooks.** Does the plugin ship a `PreToolUse` hook that blocks `git tag v*` / `gh release create` outside a `/devkit-release-*` flow, mirroring #927's `--no-verify` guard? Useful, but touches the same trust model — defer to #927's answer.
4. **Extension-pack ownership.** When the Rust pack (#1496) ships, does `devkit-pack-rust` live in this plugin, or in a `vig-os/rust-pack` plugin? Preference: this plugin, one skill per pack, until packs are large enough to be their own marketplace entry.
5. **First-adopter for the release-train skills.** devkit itself (dogfood on the reference implementation) or a downstream consumer? Preference: devkit — the reference implementation is the shortest path to catching a skill/workflow mismatch.

Refs: #927, #1496, #1519, #1523, #1626, #1627, #1301, #1497, #1642, #1676, #1625, vig-os/tessera#441, vig-os/tessera#442

https://claude.ai/code/session_01XdERKMVDAwfMJSKdTytNnK

---

# [Comment #1]() by [gerchowl]()

_Posted on September 28, 2026 at 11:53 AM_

Related: #1746 (Rust release extension — pre-release format, draft-Release-owner contract, standalone publish seam). A `/devkit-pack-rust` / `/devkit-release-*` skill should encode #1746's contract once it lands.

https://claude.ai/code/session_01XdERKMVDAwfMJSKdTytNnK

---

# [Comment #2]() by [gerchowl]()

_Posted on September 28, 2026 at 12:18 PM_

## Two format corrections while implementing this

Verified the plugin format against the current Claude Code docs (they have moved to `code.claude.com/docs/en/plugins-reference` and `.../plugins/marketplace-reference`). Two points in the issue body above are off-spec, so the implementation deviates deliberately:

**1. `.claude-plugin/` holds only `plugin.json`.** The manifest reference is explicit: *"Save the manifest at `.claude-plugin/plugin.json` under the plugin root. Put every other plugin file at the plugin root, not inside `.claude-plugin/`. That includes `skills/`, `commands/`, and `hooks/`."* The layout sketched above (`.claude-plugin/skills/devkit-adopt/SKILL.md`) would not load from its default location.

**2. Components are namespaced, so there is no bare `/devkit-status`.** A plugin namespaces every component under its `name`: a skill `status` in plugin `devkit` is invoked as `/devkit:status`. Keeping the directory name `devkit-status` would yield `/devkit:devkit-status`. The skills are therefore named without the redundant prefix.

Shipped layout:

```text
.claude-plugin/marketplace.json      # this repo is the marketplace ("vigos-devkit")
plugins/devkit/                      # plugin root
  .claude-plugin/plugin.json         # name "devkit", version == DEVKIT_VERSION
  README.md                          # lists every /devkit:* command
  skills/status/SKILL.md
  skills/adopt/SKILL.md
  skills/upgrade/SKILL.md
  skills/release-{prepare,candidate,finalize,promote,abandon,hotfix,neutral}/SKILL.md
  skills/pack-rust/SKILL.md
```

Command names: `/devkit:status`, `/devkit:adopt`, `/devkit:upgrade`, `/devkit:release-prepare`, `/devkit:release-candidate`, `/devkit:release-finalize`, `/devkit:release-promote`, `/devkit:release-abandon`, `/devkit:release-hotfix`, `/devkit:release-neutral`, `/devkit:pack-rust`.

Both manifests pass `claude plugin validate --strict`.

### Other decisions taken

- **Marketplace home.** This repo ships `.claude-plugin/marketplace.json` now, so the plugin is installable and dogfoodable the moment this merges (`/plugin marketplace add vig-os/devkit` then `/plugin install devkit@vigos-devkit`) rather than blocking on #927. When #927 lands, `vig-os/org-config` adds a `git-subdir` entry pointing at `plugins/devkit` in this repo — nothing moves, and the version pin stays co-located with the workflows.
- **Not vendored into the scaffold.** No entry in `scripts/manifest.toml`; a test asserts there never is one. Per-repo copies are the drift model #927 exists to retire.
- **Skills only, no `commands/` wrappers** (open question 2's stated preference; the docs also say to prefer `skills/` for new plugins, and skills already run as commands). **No hooks** in this cut (open question 3 defers to #927).
- **Auto-invocation.** Read-only skills (`status`, `adopt`, `pack-rust`) stay model-invocable. Every mutating skill sets `disable-model-invocation: true`, so an agent cannot infer its way into dispatching a release verb — a human has to type the command.
- **`/devkit:pack-rust` scope** (open question 4): a real read-only auditor for what devkit ships today — toolchain/lint-table/project-recipe layers per #1496, and the silent-green trap where `test`/`lint` compile nothing — plus an explicit "still open" section naming #1746's three contracts (pre-release format, draft-Release-owner, the standalone publish seam) as unmerged. It reports the gap rather than describing an unmerged contract as if it existed.

### Drift gate

`tests/test_devkit_plugin.py` fails when a skill names a `just` recipe or a workflow file that does not exist in devkit or in the consumer scaffold, so a renamed verb breaks the suite before it breaks an operator mid-release. It also pins `plugin.json`'s version to `DEVKIT_VERSION`, and asserts that `release.yml`'s finalize step bumps both in the same place.

Per @gerchowl's note above, `/devkit:status` matches a pre-release as `<base>-<anything>` and reads `DEVKIT_PRERELEASE_FORMAT` rather than hard-coding `-rc*`, so it stays correct once #1746 makes the format configurable.


---

# [Comment #3]() by [gerchowl]()

_Posted on September 29, 2026 at 12:29 AM_

Implemented by #1751 (merged): the plugins/devkit Claude Code plugin with 11 state-lookup-first skills, and this repo as the vigos-devkit marketplace. Install pinned: /plugin marketplace add vig-os/devkit@<version>.

