---
type: issue
state: open
created: 2026-02-23T22:58:38Z
updated: 2026-06-23T06:56:40Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devcontainer/issues/162
comments: 1
labels: refactor
assignees: none
milestone: none
projects: none
parent: none
children: none
synced: 2026-06-23T08:02:56.625Z
---

# [Issue 162]: [[REFACTOR] Replace hand-rolled CI polling in worktree_ci-check with gh pr checks --watch](https://github.com/vig-os/devcontainer/issues/162)

### Description

The `worktree_ci-check` skill (`.cursor/skills/worktree_ci-check/SKILL.md`) implements a hand-rolled exponential-backoff polling loop (30s → 60s → 120s → 120s cap, 15-minute timeout) to wait for CI to complete. The GitHub CLI already provides `gh pr checks --watch --fail-fast` and `gh run watch --exit-status`, which natively block until all checks complete or a failure is detected.

Replace the manual polling logic in Step 2 of `worktree_ci-check` with:
```bash
timeout 900 gh pr checks <pr-number> --watch --fail-fast
```
For the branch-only (no-PR) path, use:
```bash
timeout 900 gh run watch <run-id> --exit-status
```

Also handle the "no run yet" edge case (run may not appear immediately after push) with a short initial poll before handing off to `gh run watch` / `gh pr checks --watch`.

**Token-cost investigation:** Both `gh pr checks --watch` and `gh run watch` stream live progress output to stdout (updating check statuses, spinner lines, etc.). In an agent context, every byte of stdout becomes tokens. The implementation must investigate:
- What exactly each command outputs and how verbose it is
- Whether `--json` or other flags can suppress streaming output while preserving the blocking + exit-code behavior
- Whether redirecting stdout to `/dev/null` (keeping only the exit code) is sufficient, or if the final status output is needed for the failure-handling step
- The goal: block until CI completes, get pass/fail via exit code, capture only the minimal output needed to identify which check failed — zero streaming noise

### Files / Modules in Scope

- `.cursor/skills/worktree_ci-check/SKILL.md`

### Out of Scope

- `ci_check/SKILL.md` (interactive variant — reports status, doesn't wait)
- `ci_fix/SKILL.md` and `worktree_ci-fix/SKILL.md` (fix logic unchanged)
- Delegation sections (can be updated in a follow-up if needed)

### Invariants / Constraints

- Observable behavior unchanged: skill still waits for CI, reports pass/fail, triggers `worktree_ci-fix` on failure, times out at 15 minutes
- The `timeout 900` wrapper preserves the existing 15-minute cap
- The "no run yet" edge case must still be handled (initial delay/retry before watching)
- All existing skill cross-references remain valid
- Stdout token cost must be equal to or less than the current polling approach (no regression)

### Acceptance Criteria

- [ ] Step 2 of `worktree_ci-check/SKILL.md` uses `gh pr checks --watch --fail-fast` (PR path) or `gh run watch --exit-status` (branch path) instead of manual polling
- [ ] A `timeout 900` wrapper enforces the 15-minute cap
- [ ] The "wait for run to appear" edge case is still handled
- [ ] Streaming stdout is suppressed or redirected — only the exit code and (on failure) the failing check name are captured
- [ ] Delegation section is updated to reflect the simplified polling
- [ ] TDD compliance (see `.cursor/rules/tdd.mdc`)

### Changelog Category

Changed

### Additional Context

Discussion: the `gh pr checks --watch` flag has been available since gh v2.26+. The `gh run watch` command has been available for longer. Both eliminate the need for agent-side backoff loops, reducing token consumption and complexity in the autonomous worktree pipeline.

Token cost concern: the current polling approach generates ~5-10 `gh pr checks` calls over 15 minutes. If `gh run watch` streams hundreds of status lines, the cure could be worse than the disease. The implementation must measure and compare.
---

# [Comment #1]() by [c-vigo]()

_Posted on June 23, 2026 at 06:56 AM_

Touches the worktree pipeline being migrated in #625: #626 moves the skill paths and #627 swaps `cursor-agent` → `claude`. The `gh pr checks --watch` refactor is a good companion to land alongside the CLI swap. Coordinate.

