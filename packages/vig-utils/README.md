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
| `release-version` | Python | Compute the release train's publish version from a pre-release format |
| `gh-app-provision` | Python | Create a GitHub App from a manifest and store its credentials as secrets ([guide](../../docs/GITHUB_APP_PROVISIONING.md)) |
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

### `release-version`

Computes the bare publish version (`X.Y.Z` or `X.Y.Z-<pre-release>`) for the
release train from a pre-release format string (`{N}` counter, `{YYYYMMDD}`
date; default `rc{N}`), reading existing tags from stdin and printing
`$GITHUB_OUTPUT` lines. Refuses a format switch that would publish a version
below an existing tag of the same `X.Y.Z`
([#1746](https://github.com/vig-os/devkit/issues/1746)).

```bash
git ls-remote --tags --refs origin "v1.2.3" "v1.2.3-*" | sed 's#.*refs/tags/##' \
  | release-version --version 1.2.3 --kind candidate --format 'alpha.{N}' --tag-prefix v
# publish_version=1.2.3-alpha.1
# next_n=1
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

#### Repo-local taxonomy extension

An optional `.github/label-taxonomy.local.toml` (same `[[labels]]` schema)
declares repo-specific labels. It is never devkit-managed — the scaffold/upgrade
step neither creates nor overwrites it — mirroring the justfile layering
(managed base -> repo-owned local layer). When present, `setup-labels` merges it
into the effective taxonomy: its labels are created/updated alongside the
canonical ones, `--prune` only deletes labels absent from *both* files, and on a
`name` collision the local entry wins (overrides the canonical
color/description). `--dry-run` previews the merged result.

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

## Endpoint lint

`check-hardcoded-endpoints FILE [FILE ...]` enforces the two narrow rules in
[ADR §10](../../docs/rfcs/ADR-site-agnostic-projects.md#10-env-only-runtime-config-lint-and-leak-check-hook-point).
The default-on `no-hardcoded-endpoints` hook scans shell (extension or shebang),
Python, YAML, TOML and JSON. Its companion `no-hardcoded-endpoints-dotenv` selects
`.env`, `.env.*` and `*.env` by path. Other text, including Markdown, is ignored.
Shell/dotenv scan physical assignment lines without parse notices. Other parse/
encoding failures emit one notice and scan each line. Only findings exit 1;
unreadable inputs emit a notice. Diagnostics omit values. Variable/command and
`{{ ... }}` / `{% ... %}` references, empty values and reserved hosts/subdomains
are exempt. Parseable Python fixtures/docstrings stay inert; JSON comments and
TOML multiline literals are supported.

For an intentional literal, add `# devkit: allow-endpoint` on its assignment line.
For a whole path, override the hook in the consumer's preserved `flake.nix`:

```nix
hooks.no-hardcoded-endpoints.excludes = [ "^tests/fixtures/legacy\\.py$" ];
```

Use `hooks.no-hardcoded-endpoints-dotenv.excludes` for dotenv paths. See the
[upgrade guidance](../../docs/MIGRATION.md#env-only-endpoint-lint) for generated
versus preserved hook configs. Broader patterns belong to the separate site
leak check; this lint is not a full-history secret scanner.

## Site leak check

`site-leak-check` loads `$DEVKIT_LEAK_PATTERNS` (an absolute path), otherwise
`.site/leak-patterns.toml` at the repository root. Without either, it exits 0
silently, including on hosted and fork runs. devkit ships no patterns. The file
uses self-contained gitleaks format: at least one `[[rules]]` entry with a
nonempty string `id` and either a nonempty `regex` or `path`. Path-only rules
are valid. Any `[extend]` table, including empty tables and case variants, is
rejected: patterns cannot load another file or the default ruleset. Present
files without usable rules also exit 2, naming the file without printing patterns.
Keep rule IDs suitable for public logs. Tracked pattern files and files inside
the worktree outside `.site/` are errors, including through symlinks.

Linked git worktrees (for example, `just worktree-start`) do not inherit the
main clone's gitignored `.site/`. Each worktree runs without patterns unless the
operator provisions its own `.site/leak-patterns.toml` or sets the absolute
`DEVKIT_LEAK_PATTERNS` path in its environment.

With no arguments, the CLI snapshots full index contents at added, copied,
modified and renamed paths; deleted and untouched paths are skipped. Raw blobs
bypass attributes, textconv and checkout filters. All modes use the same gitleaks
directory scanner. `--all-files` scans tracked and nonignored untracked working-tree
files; explicit filenames scan those working-tree files. Only the active,
untracked pattern file is excluded from selected inputs; selected `.site/`
files, including force-added bindings, are scanned. Symlinks are committed as
links; link targets are never scanned.
This scans current content, not history; use the same config for a history scan.

The hook scans text files only. Filename mode skips files containing a NUL byte,
even with a text extension; direct staged and `--all-files` scans include them.
Pre-commit supplies staged text files during commits and all tracked text files
for `pre-commit run --all-files`. Filename mode catches pure renames that a
content diff would miss; index snapshots cover renamed paths too. Every hook
passes `--` before filenames, including names beginning with `-`. Direct CLI
callers must do the same; `-h` and `--help` are rejected rather than exiting
successfully without scanning. See the [S6 ADR amendment](../../docs/rfcs/ADR-site-agnostic-projects.md).

The executable requires gitleaks on PATH (provided by the devkit environment;
Nix-generated hooks pin its executable). All scans use `--config` and `--redact`.
Only file, line and rule ID are published; private scanner diagnostics, matched
text and rule descriptions are suppressed. Matching file paths are printed
as-is, even when a path contains a private name. Exit codes are 0 for clean, 1 for
findings and 2 for configuration or scanner errors. Investigate errors locally
with gitleaks and the private config; those diagnostics can disclose patterns.
Filesystem errors identify the input path and OS reason without its contents.
SIGINT, SIGTERM and SIGHUP remove the private snapshot and exit 130, 143 and 129.
Project input syntax is not parsed, so malformed project syntax is harmless.

For an intentional match, use gitleaks' same-line `gitleaks:allow` pragma or the
site config's allowlist. For a whole path, override the generated consumer hook:

```nix
hooks.site-leak-check.excludes = [ "^tests/fixtures/legacy\\.txt$" ];
```

Exclusions apply to filenames supplied by pre-commit. Direct CLI staged/tree
scans use the private config's allowlist. This hook is independent of the opt-in
repo-level `gitleaks` hook and its `.gitleaks.toml`. Repository `.gitleaksignore`
and `.gitleaks.toml` files cannot suppress site findings. With gitleaks 8.30.1,
a root `.gitleaksignore` is scanned separately as data to prevent automatic
loading as ignore configuration; its content remains covered by the check.

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
