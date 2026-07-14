---
type: issue
state: closed
created: 2026-07-14T08:33:09Z
updated: 2026-07-14T09:51:59Z
author: c-vigo
author_url: https://github.com/c-vigo
url: https://github.com/vig-os/devkit/issues/1039
comments: 1
labels: feature, priority:high, area:ci, area:workspace, effort:small, semver:minor
assignees: none
milestone: Backlog
projects: none
parent: 1040
children: none
synced: 2026-07-14T20:06:30.796Z
---

# [Issue 1039]: [[FEATURE] Scaffold: guard codeql/scorecard workflows on private repos](https://github.com/vig-os/devkit/issues/1039)

### Description

The scaffold ships `codeql.yml` and `scorecard.yml` unconditionally (`assets/workspace/.github/workflows/`), with no repository-visibility guard. On a **private** repo they cannot succeed:

- CodeQL requires GitHub Advanced Security on private repos (not available on Free-plan orgs).
- OpenSSF Scorecard only supports public repositories.

The devkit itself is public so this never surfaced. The first private consumer (exoma-ch/cad2gdml, Free-plan org — the target of the onboarding epic) would scaffold two permanently red workflows on day one.

### Proposed solution

Options considered:

1. **Runtime guard** — gate the jobs with `if: ${{ !github.event.repository.private }}`. Scaffold stays uniform across consumers; private repos get skipped (neutral) runs. Zero scaffold-logic changes.
2. **Scaffold-time filtering** — `init-workspace.sh` detects/asks repo visibility and omits the two workflows, persisting the choice in `.vig-os` (same pattern as `DEVKIT_MODE` file-filtering).
3. **Documented manual removal** — cheapest, but violates the "scaffold lands green" expectation and will be forgotten.

Recommendation: option 1 for both workflows (a repo later flipped to public starts scanning automatically, with no re-scaffold). Option 2 can layer on later if skipped runs prove noisy.

### Acceptance criteria

- [ ] Scaffolding a private repo yields no permanently failing workflow (CodeQL/Scorecard skipped or absent).
- [ ] Public consumers keep current behavior unchanged.
- [ ] Behavior documented (workflow header comments + migration/onboarding doc).

### Additional context

Surfaced by the readiness audit for the cad2gdml onboarding epic (Phase 0). Related known consumer-affecting bug: #1034 (sync-main-to-dev references a local action that only exists on `main`).

---

# [Comment #1]() by [c-vigo]()

_Posted on July 14, 2026 at 09:51 AM_

Implemented in #1050 (merged to dev): job-level `if: ${{ !github.event.repository.private }}` guard on both scan workflows (Option 1 per the issue's recommendation) — private repos get neutral skipped runs; flipping public re-enables scanning with no re-scaffold. Guard validity verified for every declared trigger incl. schedule. Both cad2gdml Phase-0 devkit prerequisites (#1038, #1039) are now on dev.

