---
type: issue
state: open
created: 2026-10-26T19:46:40Z
updated: 2026-10-26T19:46:40Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devkit/issues/1921
comments: 0
labels: feature
assignees: none
milestone: 1.20.0
projects: none
parent: none
children: none
synced: 2026-10-27T07:38:03.918Z
---

# [Issue 1921]: [Optional site-agnostic data feature: logical data locations, .site/ mapping, safe transfer recipes, /devkit:data skill](https://github.com/vig-os/devkit/issues/1921)

**Goal:** an optional, site-agnostic "data" feature for devkit repos. A repo declares *logical* data locations, and the site maps them to concrete storage at clone time, so the repo carries no endpoint, bucket name or credential. Agents get a skill that explains the model.

Builds on the accepted [ADR-site-agnostic-projects](../blob/dev/docs/rfcs/ADR-site-agnostic-projects.md) (#1908): its `.site/` convention (§8) and `site init` hook (§9). Sequence it after #1908's S4 (`.site/` plus site-init) lands.

**Scope**
1. **Logical locations in `.vig-os`**, for example `DEVKIT_DATA_INPUTS=s3:project/raw/…` and `DEVKIT_DATA_OUTPUTS=s3:project/runs/`. These are names only; the scheme names a storage kind, not an endpoint. Settle the exact key names and grammar in a short design note or ADR addendum before implementation.
2. **Site mapping in `.site/`**, which is gitignored and written by the site's `site init` initialiser. It maps each logical location to an endpoint, a profile name and a concrete bucket or prefix. Credentials stay in the environment or profile (ADR §10, env-only runtime config) and are never written to `.site/` or the repo.
3. **Optional dev-shell component** (awscli2 or rclone; the design note picks one with rationale) with `just data-pull`, `just data-push` and `just data-ls` recipes that:
   - refuse to run without a `.site/` mapping for the requested location, and name the missing key;
   - transfer in bounded batches (at most 1 TiB per batch), run a dry-run sync before each real one, and verify afterwards;
   - on failure, list and abort the multipart uploads this transfer started, and only those.
4. **CI is opt-in**: no data access by default. Fork PRs never get data access, on any path; the #1908 fork predicate applies.
5. **Agent skill** `/devkit:data` (plugin skill) covering the logical-location model, the recipes, and the rules: never commit credentials, endpoints, bucket names or host-local paths. For site specifics such as how to request a bucket, quotas, or job I/O, it points to whatever the site's initialiser declares in `.site/` (for example a site docs pointer or a site skill name). devkit names no site.
6. **Scaffold option** to enable the feature (`--with data` on the installer, or the repo's equivalent feature-flag mechanism), plus a docs page.

**Acceptance**
- With no `.site/`, the recipes refuse with an actionable message and CI passes without data access.
- Tests for the refusal, for the batching and dry-run flow (with a mocked client), and for multipart-abort scoping (only this transfer's uploads).
- The leak-check from #1908 S6 catches a committed endpoint or bucket in `.vig-os`.
- Docs and the skill pass the repo's skill and docs checks. No site names, endpoints or host paths anywhere.

