# Solo / private-repo adoption profile

This is the one document a **single-user, private repository** follows to adopt
devkit **without the team/traceability layer** — no release train, no issue/PR
archive, no public-repo scanning, no agent-workflow skills — while keeping the
part that is valuable solo: the pre-commit hook stack, commit hygiene, the
justfiles, the dev environment, and the managed upgrade path.

The profile is not a new mode. It is a **combination of existing `.vig-os`
knobs**, each documented in full in [`docs/MIGRATION.md`](./MIGRATION.md); this
guide only assembles them into one repeatable recipe and calls out the few
adoption notes that trip solo adopters. Follow it and you get a working scaffold
without discovering knobs by reading `init-workspace.sh`.

## The recipe

Two flags at install time, two keys in the generated `.vig-os`:

```text
--mode devcontainer --workflow trunk
DEVKIT_FEATURES_DISABLED=release,sync-issues,scanning,skills,worktree,gh-templates
DEVKIT_REFS_POLICY=optional
```

- **`--mode devcontainer`** — the VS Code devcontainer that pulls the published
  image. Pick `direnv` instead if you develop on a bare Nix host; the profile is
  otherwise identical (see [delivery modes](./MIGRATION.md#the-delivery-modes)).
- **`--workflow trunk`** — no long-lived `dev` branch and no `sync-main-to-dev`;
  topic branches merge straight to `main`. A solo repo has no integration branch
  to justify gitflow (see [workflow models](./MIGRATION.md#workflow-models),
  [#1205](https://github.com/vig-os/devkit/issues/1205)).
- **`DEVKIT_FEATURES_DISABLED`** — the comma-separated list of scaffold feature
  groups a solo repo declines (see [scaffold feature
  opt-outs](./MIGRATION.md#scaffold-feature-opt-outs),
  [#1284](https://github.com/vig-os/devkit/issues/1284)). The value above drops
  the entire team/traceability surface; each group is detailed below.
- **`DEVKIT_REFS_POLICY=optional`** — a solo repo has no issue tracker to
  reference, so the mandatory `Refs:` line is relaxed to optional. Commit **type
  and format are still validated** — only the issue link becomes optional (see
  [Refs policy](./MIGRATION.md#the-vig-os-project-manifest),
  [#1282](https://github.com/vig-os/devkit/issues/1282)).

`DEVKIT_FEATURES_DISABLED` and `DEVKIT_REFS_POLICY` are **manifest-only keys**
(no CLI flag), so apply them in two steps — exactly the flow used to switch mode
or workflow model:

1. **Scaffold once** with the flags:

   ```bash
   curl -sSfL https://raw.githubusercontent.com/vig-os/devkit/main/install.sh \
     | bash -s -- --mode devcontainer --workflow trunk ~/my-solo-repo
   ```

2. **Set the two keys** in the generated `.vig-os` and commit them:

   ```ini
   # .vig-os
   DEVKIT_FEATURES_DISABLED=release,sync-issues,scanning,skills,worktree,gh-templates
   DEVKIT_REFS_POLICY=optional
   ```

3. **Re-render** so the disabled groups are pruned and the Refs policy is
   applied. Preview first, then apply on a clean branch (the [upgrade preflight
   guard](./MIGRATION.md#upgrade-preflight-guard-and-preview) requires it):

   ```bash
   curl -sSfL https://raw.githubusercontent.com/vig-os/devkit/main/install.sh \
     | bash -s -- --force --preview ~/my-solo-repo   # inspect, then drop --preview
   ```

The two keys round-trip in `.vig-os` from then on, so every later
`install.sh --force` upgrade preserves the profile with no flags.

> **`renovate` is a judgment call — kept by default.** Dependency updates are
> useful even solo, so `renovate` is deliberately **not** in the disable list
> above. Add it (`DEVKIT_FEATURES_DISABLED=renovate,release,…`) only if the
> Renovate GitHub App is not installed on the repo, otherwise the scaffolded
> Renovate config is inert. Note the `renovate.json` extension seam is a
> preserved-class file and is **never pruned** when the group is disabled — an
> existing one is left in place with a notice, delete it by hand if you want it
> gone.

## What is kept vs. dropped

The profile keeps everything that protects a single author's working tree and
history, and drops everything whose value is coordination between people.

| Kept | Dropped (via the recipe) |
|------|--------------------------|
| The full **pre-commit hook stack** (`ruff`, `typos`, `pymarkdown`, `shellcheck`, whitespace/EOF fixers, private-key detection, …) | **`release`** — the release/prepare/promote workflows and `docs/DOWNSTREAM_RELEASE.md` |
| **Commit-message type/format validation** (`validate-commit-msg` — Conventional Commit type and shape) | **`sync-issues`** — the issue/PR archive workflow and label taxonomy |
| **Agent-identity enforcement** — no AI author/committer, no `Co-authored-by` | **`scanning`** — `codeql.yml` + `scorecard.yml` (already neutral on private repos) |
| The **managed upgrade path** — `.vig-os` manifest, `install.sh --force`, pinned flake input | **`gh-templates`** — issue/PR templates |
| The **justfiles** (`lint`/`format`/`test`/`sync`/…) | **`skills`** — the `.claude/skills/` agent-workflow commands |
| The **dev environment** — devcontainer image (or the `direnv` flake dev-shell) | **`worktree`** — the `worktree_*` skills + `.devcontainer/justfile.worktree` |
| **`ci.yml`** — still runs `lint`/`test`/`commit-checks` on every push | The mandatory `Refs:` line — relaxed to optional (`DEVKIT_REFS_POLICY`) |

`ci.yml` is intentionally **not** opt-outable — it stays a single atomic,
mode-aware workflow, and its lint/test/commit-checks gates are exactly the solo
value. Disabling `sync-issues` also makes `DEVKIT_SYNC_TARGET` /
`DEVKIT_SYNC_SCHEDULE` inert (a notice is printed).

> **Forward-drift note.** New scaffold feature groups shipped in future devkit
> releases arrive **enabled** — `DEVKIT_FEATURES_DISABLED` is an explicit opt-out
> list, not a snapshot. Re-read this list (and `--preview` the diff) on each
> `install.sh --force` upgrade so a newly added team-layer group does not land
> silently.

## Adoption notes that trip solo adopters

- **Default branch must be `main`** ([#1283](https://github.com/vig-os/devkit/issues/1283)).
  Both workflow models assume the repository's default branch is `main`; the
  installer **refuses to scaffold on a legacy `master` repo** rather than
  succeed silently and then reject every commit via the branch-name hook. Rename
  first (`git branch -m master main && git push -u origin main`,
  `gh repo edit --default-branch main`), then run the installer — see [legacy
  default branches](./MIGRATION.md#legacy-default-branches-master).

- **A repo-owned `typos.toml` is respected** ([#1280](https://github.com/vig-os/devkit/issues/1280)).
  If your repo already carries an undotted `typos.toml` (or `_typos.toml`), the
  scaffold no longer also ships the template `.typos.toml` on top of it — your
  file stays the single active spell-check config instead of being silently
  shadowed. Fold the shipped `[default.extend-words]` entries into it if you want
  the curated allowlist.

- **Zero-test Python repos stay green** ([#1281](https://github.com/vig-os/devkit/issues/1281)).
  A repo with a `pyproject.toml` but no test suite yet (a config/data repo, or a
  project before its first test) no longer reds `just test` / CI on pytest's
  "no tests collected" (exit 5); "nothing to test" is treated as success, the
  same no-op as a non-Python consumer.

## Out of scope: a `--profile solo` installer flag

A one-shot installer flag (`--profile solo`) that writes these same manifest
keys for you is a **possible follow-up**, tracked against
[#1285](https://github.com/vig-os/devkit/issues/1285). This guide documents the
knob combination directly; no such flag exists today.
