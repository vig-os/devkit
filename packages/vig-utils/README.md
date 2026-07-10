# vig-utils

Reusable CLI utilities for repository automation, release management, policy enforcement, and workspace tooling.

This package is used both in this repository and in downstream workspaces synced from it.

## Install

```bash
pip install vig-utils
```

For local development in this repo:

```bash
uv sync --all-extras
uv run check-action-pins --help
```

## What is included

`vig-utils` exposes Python CLIs and shell-wrapper CLIs through `project.scripts` in `pyproject.toml`.

| Command | Type | Purpose |
|---|---|---|
| `validate-commit-msg` | Python | Enforce commit message standard |
| `check-action-pins` | Python | Ensure GitHub Actions are SHA pinned |
| `prepare-changelog` | Python | Validate/prepare/finalize/reset/unprepare changelog |
| `gh-issues` | Python | Rich issue/PR dashboard via `gh` |
| `prepare-commit-msg-strip-trailers` | Python | Remove blocked trailers from commit messages |
| `check-agent-identity` | Python | Block commits from agent fingerprints in author identity |
| `check-pr-agent-fingerprints` | Python | Block PR title/body fingerprints |
| `resolve-branch` | Shell wrapper | Parse branch name from `gh issue develop --list` output |
| `derive-branch-summary` | Shell wrapper | Generate branch-summary slug from an issue title |
| `check-skill-names` | Shell wrapper | Enforce skill directory naming convention |
| `setup-labels` | Shell wrapper | Sync labels from `.github/label-taxonomy.toml` |
| `vig-utils` | Python | Utility entrypoint (`version`, `sed`) for sync/build scripts |

## Command reference

### `validate-commit-msg`

Validates commit messages against the project standard.

Canonical standard: [`docs/COMMIT_MESSAGE_STANDARD.md`](../../docs/COMMIT_MESSAGE_STANDARD.md)

```bash
validate-commit-msg <message-file> \
  [--types TYPE,...] \
  [--scopes SCOPE,...] \
  [--refs-optional-types TYPE,...] \
  [--require-scope] \
  [--blocked-patterns PATH]
```

Examples:

```bash
validate-commit-msg .git/COMMIT_EDITMSG
validate-commit-msg .git/COMMIT_EDITMSG --scopes setup,ci,vigutils --require-scope
```

### `check-action-pins`

Validates that external workflow `uses:` references are pinned to a 40-char commit SHA.

```bash
check-action-pins [--repo-root PATH] [--verbose]
```

Examples:

```bash
check-action-pins
check-action-pins --verbose
check-action-pins --repo-root /path/to/repo
```

### `prepare-changelog`

Manages `CHANGELOG.md` in Keep a Changelog format.

```bash
prepare-changelog validate [FILE]
prepare-changelog prepare <VERSION> [FILE]
prepare-changelog finalize <VERSION> <YYYY-MM-DD> [FILE] [--github-repository OWNER/REPO]
prepare-changelog reset [FILE]
prepare-changelog unprepare [FILE]
```

`finalize` needs a repository slug for the release link: use `GITHUB_REPOSITORY` (as in GitHub Actions) or pass `--github-repository` after the optional file path.

Examples:

```bash
prepare-changelog validate
prepare-changelog prepare 0.3.0
prepare-changelog finalize 0.3.0 2026-03-04
prepare-changelog finalize 0.3.0 2026-03-04 CHANGELOG.md --github-repository my-org/my-repo
prepare-changelog reset
prepare-changelog unprepare
```

### `gh-issues`

Displays open issues and pull requests in rich terminal tables.

Notes:
- Uses `gh` CLI (`gh issue list`, `gh pr list`, GraphQL calls).
- Expects an authenticated GitHub CLI session in the target repository.

```bash
gh-issues
```

### `prepare-commit-msg-strip-trailers`

Prepare-commit-msg hook helper that removes blocked trailer lines using patterns from `.github/agent-blocklist.toml`.

```bash
prepare-commit-msg-strip-trailers <path-to-COMMIT_EDITMSG>
```

### `check-agent-identity`

Checks git author/committer values against names/emails in `.github/agent-blocklist.toml`.

Behavior:
- Returns `0` in CI (`CI=true` or `GITHUB_ACTIONS=true`).
- Returns `1` when blocked identity content is found.

```bash
check-agent-identity
```

### `check-pr-agent-fingerprints`

Checks PR title/body content for blocked fingerprints.

Inputs are read from environment variables:
- `PR_TITLE`
- `PR_BODY`

```bash
PR_TITLE="..." PR_BODY="..." check-pr-agent-fingerprints
```

### `resolve-branch`

Reads tab-separated lines from stdin (`branch<TAB>url`) and prints first branch.

```bash
gh issue develop --list | resolve-branch
```

### `derive-branch-summary`

Produces a short kebab-case summary for branch names from an issue title.

```bash
derive-branch-summary "<issue-title>" [naming_rule_path] [model_tier]
```

Environment variables:
- `BRANCH_SUMMARY_CMD`: test override command (stdout used as summary)
- `BRANCH_SUMMARY_MODEL`: default model tier (if arg not provided)
- `DERIVE_BRANCH_TIMEOUT`: timeout seconds (default `30`)

### `check-skill-names`

Enforces skill directory pattern: `[a-z0-9][a-z0-9_-]*`

```bash
check-skill-names [skills_dir]
```

Examples:

```bash
check-skill-names
check-skill-names .claude/skills
```

### `setup-labels`

Creates/updates repository labels from `.github/label-taxonomy.toml`.

```bash
setup-labels [--repo owner/repo] [--prune] [--dry-run]
```

Examples:

```bash
setup-labels --dry-run
setup-labels --repo vig-os/devkit
setup-labels --repo vig-os/devkit --prune
```

### `vig-utils` (utility helper)

General utility entrypoint used by sync/build tooling.

Subcommands:

```bash
vig-utils version <readme> <version> <release_url> <release_date>
vig-utils sed 's|old|new|g' <file>
```

## Shell wrappers and packaged scripts

The following shell helpers are shipped as package data and executed through Python wrappers:

- `check-skill-names.sh`
- `resolve-branch.sh`
- `derive-branch-summary.sh`
- `setup-labels.sh`

The wrappers forward argv/stdin/stdout/stderr so they behave like native shell commands.

## Environment variables used by vig-utils

| Variable | Used by | Purpose |
|---|---|---|
| `VIG_UTILS_REPO_ROOT` | repo-root resolution helpers and `setup-labels` | Override repository root discovery |
| `PR_TITLE` | `check-pr-agent-fingerprints` | PR title content |
| `PR_BODY` | `check-pr-agent-fingerprints` | PR body content |
| `BRANCH_SUMMARY_CMD` | `derive-branch-summary` | Test override for summary generation |
| `BRANCH_SUMMARY_MODEL` | `derive-branch-summary` | Default model tier if arg omitted |
| `DERIVE_BRANCH_TIMEOUT` | `derive-branch-summary` | Timeout seconds |
| `CI` / `GITHUB_ACTIONS` | `check-agent-identity` | Skip local identity checks in CI |

## Development and tests

Run package tests from repository root:

```bash
uv run pytest packages/vig-utils/tests/
```

Focused runs:

```bash
uv run pytest packages/vig-utils/tests/test_validate_commit_msg.py
uv run pytest packages/vig-utils/tests/test_check_action_pins.py
uv run pytest packages/vig-utils/tests/test_gh_issues.py
uv run pytest packages/vig-utils/tests/test_shell_entrypoints.py
```

## Design notes

- CLI outputs are intended for both human and CI usage (clear stdout/stderr and non-zero exits on failures).
- `vig-utils` centralizes reusable behavior so downstream workspaces do not depend on repo-local script paths.
- Policy data (for example agent identity patterns) remains in canonical repository files, which utilities read at runtime.
