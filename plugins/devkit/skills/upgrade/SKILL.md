---
name: upgrade
description: >-
  Move a repository to a newer vigOS devkit: run the read-only state lookup, show the add/overwrite/preserve/delete
  report as a dry run, flag manifest-key and workflow-model rendering changes, refuse through a dirty tree or a
  protected branch, and apply only after an explicit confirmation. Use when asked to upgrade devkit, bump
  DEVKIT_VERSION, or adopt a newer devkit release in a scaffolded repo.
argument-hint: "[version]"
disable-model-invocation: true
---

# devkit upgrade

Move a scaffolded repo from its pinned devkit version to a newer one. Dry run first, always; apply only on an
explicit second-turn confirmation.

## 1. State lookup

Run `/devkit:status`. You need section 2 (pinned vs latest, and how far behind), section 3 (drift), section 8 (the
workflow model) and section 4 (a train in flight — never upgrade a repo mid-release).

```bash
git rev-parse --abbrev-ref HEAD
git status --porcelain
```

Resolve the target version explicitly. `latest` is not a version: read it and print the number you resolved.

```bash
gh release view --repo vig-os/devkit --json tagName --jq .tagName
```

## 2. Refuse

| State | Why | Offer instead |
|---|---|---|
| Working tree is dirty | The upgrade overwrites managed files in place; uncommitted work is lost with no diff to recover it. The installer's own preflight refuses too | Commit or set the work aside, then retry |
| On `main`, `dev`, a `release/*` branch or a detached HEAD | The upgrade is a reviewable change, not a direct write to a protected branch. The preflight refuses | Create a dedicated upgrade branch |
| A release train is in flight | The upgrade would land inside a frozen release surface | Finish or abandon the train first |
| The pin is already at or above the target | Nothing to do — and a downgrade is not an upgrade | Report the versions and stop |
| The operator asks for `--skip-preflight` | That flag exists for a bootstrap emergency, not for getting past a dirty tree | Clean the tree |

Never pass `--force` without having shown the dry-run report in the same run.

## 3. Dry run — this is the default

```bash
./install.sh --preview --force --version 1.18.0 .
```

`--preview` prints the add / overwrite / preserve / delete report and exits without changing a single file. In a
repo that has no local installer, fetch the one for the target version rather than `main`, so the preview matches
what you would apply.

Read the report back to the operator and call out, specifically:

- **manifest keys**: new or renamed `DEVKIT_*` keys in `.vig-os`, and any key whose empty-means-default changed;
- **workflow-model rendering**: files re-rendered because of `DEVKIT_WORKFLOW`. A model switch leaves the
  **preserved** `.pre-commit-config.yaml` carrying the other model's branch guard (#1642) — check it by hand;
- **preserved files that will not move**: an upgrade cannot fix a preserved file; say which ones are stale;
- **deletions**: a retired scaffold path being removed is normal, but it is still a deletion — list them.

## 4. Apply, only after confirmation

```bash
./install.sh --force --version 1.18.0 .
```

Run it inside the project shell so the repo's own hooks run on the resulting commit. Then review the diff before
committing — the upgrade is a proposal until you have read it.

In a consumer repo the scheduled lane does the same thing on its own and opens the adoption PR:

```bash
gh workflow run devkit-upgrade.yml -f version=1.18.0
```

Prefer that lane when it exists: it commits through the App identity, so the adoption commit is signed and the PR
triggers CI.

## 5. Verify

```bash
sed -n 's/^DEVKIT_VERSION=//p' .vig-os
git status --porcelain
git diff --stat
```

Confirm the pin moved, the flake input (if any) moved with it, and nothing you did not expect changed. Note that a
consumer whose flake input is named something other than `vigos`, or is pinned to a ref, is **not** auto-bumped and
nothing says so (#1497) — check the input by hand and report it either way.

Then re-run `/devkit:status` and confirm drift is clean against the new pin.

## 6. Hand off

Open the upgrade as its own PR. If the new version changes a release verb, re-read `docs/RELEASE_CYCLE.md` before
the next train — the `/devkit:*` skills ship with devkit and move in the same release.
