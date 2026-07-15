---
type: issue
state: closed
created: 2026-07-15T18:07:59Z
updated: 2026-07-15T19:38:01Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1140
comments: 1
labels: feature, area:ci, semver:minor
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-07-15T20:03:58.894Z
---

# [Issue 1140]: [[FEATURE] Scaffold ci.yml lacks a dependency-review job (consumers lose vulnerable-dependency gating)](https://github.com/vig-os/devkit/issues/1140)

### Description

The scaffolded consumer CI (`assets/workspace/.github/workflows/ci.yml`) has no
dependency-vulnerability gate. Devkit's **own** `.github/workflows/ci.yml`
already runs a `Dependency Review` job (`actions/dependency-review-action` v5,
`fail-on-severity: high`), but consumers get nothing equivalent from the
scaffold.

Surfaced by the sync-issues-action migration recon: its bespoke `ci.yml`
carries a real `dependency-review` job that would be silently lost when the
scaffold replaces it. commit-action (already migrated) has no dependency
review today for the same reason.

### Why the scaffold should provide it

- **Language-neutral**: works off GitHub's dependency graph
  (`package-lock.json`, `uv.lock`, `Cargo.lock`, action pins alike) —
  zero per-language config.
- **Zero toolchain**: plain checkout + marketplace action; needs neither
  `resolve-toolchain` nor the devkit dev-shell.
- Complements the existing scaffold security lane (CodeQL, Scorecard,
  Renovate) with the one missing piece: blocking PRs that *introduce*
  known-vulnerable dependencies.

### Proposal

Add a `dependency-review` job to the scaffold `ci.yml`:

- `if: ${{ github.event_name == 'pull_request' && !github.event.repository.private }}`
  — the action only works on PRs (base/head diff), and the dependency-graph
  API is unavailable on Free-plan private repos, so guard exactly like the
  scaffold `codeql.yml`/`scorecard.yml` (#1039 pattern): skipped-neutral on
  private, auto-activates when a repo flips public.
- `actions/dependency-review-action` pinned by SHA (v5.0.0, same pin as
  devkit-own), `fail-on-severity: high`.
- Standalone job (no `needs: resolve-toolchain`, no container) —
  `runs-on: ubuntu-24.04`, `permissions: contents: read` +
  `pull-requests: write` (PR summary comment).
- Wire into the `summary` (`CI Summary`) job's `needs` with skipped-is-OK
  handling (same treatment as the PR-only `commit-checks` job).
- **No exceptions/allow-list seam** in the scaffold for now (devkit-own's
  `dependency-review-allow.txt` mechanism needs `check-expirations` from the
  dev-shell; consumers needing exceptions can request the seam separately).

Devkit's own `ci.yml` is NOT in scope — it already has the job.

### Acceptance criteria

- Scaffold `ci.yml` gains the guarded `dependency-review` job; `CI Summary`
  requires it without going red on push/dispatch/private-repo skips.
- Shape tests cover the new job (TDD) and actionlint fixtures stay green.
- `CHANGELOG.md` `[1.3.0]` section updated (targets the in-flight release
  branch `release/1.3.0`).

### Related

#1039 (private-repo guards), #1025 (scaffold not language-aware class),
sync-issues-action onboarding (next consumer).

---

# [Comment #1]() by [c-vigo]()

_Posted on July 15, 2026 at 07:38 PM_

Shipped via PR #1141 into release/1.3.0 (merge 6c909376) — closed manually since release-branch merges don't auto-close.

