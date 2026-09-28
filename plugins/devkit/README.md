# devkit — the vigOS devkit operator plugin

A Claude Code plugin of state-lookup-first skills for **adopting** vigOS devkit, **operating** its release train,
and **keeping a consumer in sync**. It ships from the same repository as the workflows it drives, and every release
tag carries the plugin whose skills match that release's verbs.

## Install

**Pin the marketplace to the devkit version this repo runs.** A marketplace added without a ref tracks the
repository's **default branch**, which is the newest release — so an unpinned install gives you the latest skills
no matter which `DEVKIT_VERSION` your `.vig-os` pins. The `@ref` form is what makes the two agree:

```text
/plugin marketplace add vig-os/devkit@1.17.0
/plugin install devkit@vigos-devkit
```

Use the value of `DEVKIT_VERSION` from your `.vig-os` as the ref.

**To move to a new devkit version, remove the marketplace and add it again at the new tag.** A plain re-add is a
no-op (`already on disk`, exit 0), and `marketplace update` refreshes the ref it was added with rather than moving
to a different one:

```text
/plugin marketplace remove vigos-devkit
/plugin marketplace add vig-os/devkit@1.18.0 --sparse .claude-plugin plugins
/plugin install devkit@vigos-devkit
```

The re-install is required, not a belt-and-braces step: removing a marketplace from its last scope uninstalls the
plugins installed from it. `/devkit:upgrade` walks you through this, and `/devkit:status` reports the mismatch
until it is done.

Devkit is a large repository, and `--sparse` takes the directories to check out, so name the two the marketplace
actually needs:

```text
/plugin marketplace add vig-os/devkit@1.17.0 --sparse .claude-plugin plugins
```

Adding it unpinned is a legitimate choice for someone who always tracks the newest devkit — it is simply not the
same guarantee, and `/devkit:status` will say so rather than let you assume otherwise.

While developing the plugin, load it straight from this directory instead:

```bash
claude --plugin-dir plugins/devkit
```

## Commands

Claude Code namespaces every plugin component under the plugin name, so each skill below is invoked as
`/devkit:<name>`.

| Command | What it does | Mutates |
|---|---|---|
| `/devkit:status` | The read-only state report every other skill delegates to: pin vs latest, drift, trains in flight, pre-release tags, the promote gate, the hotfix lane, workflow model, legacy-tag hazards, required App secrets | no |
| `/devkit:adopt` | Proposes adoption for a repo that has no `.vig-os`: the installer line, the resulting manifest, the diff, and the release-tooling collisions | no |
| `/devkit:upgrade` | Dry-run preview of an upgrade to a newer devkit, applied only on confirmation | on confirmation |
| `/devkit:release-prepare` | Cuts `release/X.Y.Z` and opens the draft PR | yes |
| `/devkit:release-candidate` | Publishes the next release candidate from the release branch | yes |
| `/devkit:release-finalize` | Creates the final tag and a **draft** GitHub Release, then stops | yes |
| `/devkit:release-promote` | The irreversible step: publishes the draft, moves the floating tag, merges the PR | yes |
| `/devkit:release-abandon` | Draft-only rejection path: deletes the branch, tag, PR and draft Release | yes |
| `/devkit:release-hotfix` | Cuts a patch from `main` instead of `dev` | yes |
| `/devkit:release-neutral` | Lands a change on `main` without cutting a release (devkit only) | yes |
| `/devkit:pack-rust` | Audits a Rust repo against what the Rust pack ships today, and names what is still open | no |

## Principles

1. **State-lookup-first.** Every skill's step 1 is `/devkit:status`, re-read in the same run. No mutation without a
   fresh state read.
2. **Dry-run by default.** Adoption and upgrade never mutate without a second-turn confirmation. A release verb
   echoes the exact line and the state it observed before it dispatches. Where the underlying workflow has a
   `dry-run` input, the skill offers it; where it has none (promote, abandon), the state lookup *is* the dry run
   and the skill says so.
3. **Skills wrap canonical verbs.** A skill calls `just prepare-release` or dispatches a workflow; it never
   re-implements one. A missing knob is a devkit issue against the workflow, not a workaround in a skill.
4. **Versioned with devkit.** `plugin.json`'s version equals `DEVKIT_VERSION`, and `release.yml` bumps both in the
   same step, so **every release tag carries skills that match that release's verbs**. That is a property of the
   tag, not of your install: pin the marketplace to your `DEVKIT_VERSION` to inherit it. `/devkit:status` reads the
   running plugin's own manifest and reports a mismatch, so an unpinned install is visible rather than assumed
   away.
5. **Refusals are first-class.** Each mutating skill carries a refusal table: the state, why it is a foot-gun, and
   the verb that clears it.

Read-only skills are model-invocable. Every mutating skill sets `disable-model-invocation: true`, so an agent
cannot infer its way into cutting a release train — a human has to type the command.

## Source of truth

The plugin is an operator surface, not documentation. The cycle itself is specified in
[`docs/RELEASE_CYCLE.md`](../../docs/RELEASE_CYCLE.md), the consumer side in
[`docs/DOWNSTREAM_RELEASE.md`](../../docs/DOWNSTREAM_RELEASE.md), and the cross-repo gate in
[`docs/CROSS_REPO_RELEASE_GATE.md`](../../docs/CROSS_REPO_RELEASE_GATE.md). When a skill and a doc disagree, the
doc wins and the skill is a bug.

`tests/test_devkit_plugin.py` enforces both invariants: the version lock, and that every `just` recipe and
workflow filename named inside a skill actually exists.
