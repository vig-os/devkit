---
type: issue
state: open
created: 2026-02-22T09:52:12Z
updated: 2026-06-23T06:56:42Z
author: gerchowl
author_url: https://github.com/gerchowl
url: https://github.com/vig-os/devcontainer/issues/157
comments: 4
labels: feature
assignees: gerchowl
milestone: none
projects: none
parent: 145
children: none
synced: 2026-06-23T08:02:57.077Z
---

# [Issue 157]: [[FEATURE] Show pipeline phase (progress) per issue in gh-issues dashboard](https://github.com/vig-os/devcontainer/issues/157)

### Description

Add a "Phase" column to the `just gh-issues` issue table that shows where each issue stands in the skill pipeline (as defined in `docs/SKILL_PIPELINE.md`). The phase is inferred from issue comments and linked PR/branch state, giving an at-a-glance view of progress without clicking into each issue.

### Problem Statement

The `just gh-issues` dashboard shows issues with their metadata (priority, effort, assignee, branch, PR) but gives no signal about *how far along* the work is. An issue might have a branch but no design, or a full design but no implementation plan, or code already in review. Currently, you have to open each issue and scan the comments to understand its progress. For project triage and daily standups, a compact phase indicator would save significant context-switching.

### Proposed Solution

#### Phase column (issues table)

Detect the pipeline phase per issue by scanning issue comments for well-known headings (mirroring the state detection in `worktree_solve-and-pr`), plus branch/PR state:

| Detected signal | Phase label |
|---|---|
| No branch, no comments | `Backlog` |
| Branch exists, no design comment | `Claimed` |
| `## Design` comment found | `Design` |
| `## Implementation Plan` comment found | `Planned` |
| Commits on branch (or plan + branch with commits) | `In Progress` |
| Linked PR exists (open) | `In Review` |
| Linked PR merged | `Done` |

Display as a color-coded "Phase" column (e.g., dim for Backlog, cyan for Claimed, yellow for Design/Planned, green for In Progress/In Review).

#### Column consolidation (PRs table) — open question

The current PR table has 10 columns (`#`, `Title`, `Author`, `Assignee`, `Issues`, `Branch`, `CI`, `Review`, `Reviewer`, `Delta`) which causes heavy truncation on normal terminal widths. Consider merging columns that carry related information into compact representations:

**Review + Reviewer → single "Review" column** using icons/shorthand per reviewer:

| State | Display |
|---|---|
| Review requested | `?alice` (dim) |
| Pending / commented | `◎bob` (yellow) |
| Approved | `✓carol` (green) |
| Changes requested | `✗dave` (red) |

This preserves all information (who + state) in one column instead of two, freeing horizontal space for the new Phase column and reducing truncation overall.

Other candidates for consolidation:
- **Author + Assignee** — often the same person on solo projects; could merge into `Owner` showing author, with assignee only when different.
- **Branch** — already partially redundant with `Issues` column (branch name encodes issue number); could shorten or drop in favour of issue link.

> **Question:** Which column merges feel right? The Review+Reviewer merge seems like the clearest win. Author+Assignee and Branch trimming are more opinionated — worth doing in the same pass or separate issue?

### Alternatives Considered

- **GitHub Projects board** — provides a Kanban view but isn't integrated into the terminal dashboard and doesn't auto-detect phase from comments.
- **Manual labels** (e.g., `phase:design`, `phase:in-progress`) — requires discipline to update. Auto-detection from existing artifacts is more reliable and zero-overhead.

### Additional Context

- This should be a sub-issue of #145 (Rewrite gh-issues dashboard).
- The phase detection logic mirrors `worktree_solve-and-pr`'s state detection (see `docs/SKILL_PIPELINE.md` § State Detection).
- The implementation needs a GraphQL or REST call to fetch issue comments (at least headings) — consider batching to avoid N+1 queries.

### Impact

- **Beneficiaries:** Anyone using `just gh-issues` for triage or daily planning.
- **Breaking change:** No — additive column in the issue table, consolidation preserves information.

### Changelog Category

Added

### Acceptance Criteria

- [ ] Phase column renders in issue table with color-coded phase label
- [ ] Phase detection covers: Backlog, Claimed, Design, Planned, In Progress, In Review
- [ ] At least Review+Reviewer column merge implemented in PR table
- [ ] No information loss from column consolidation
- [ ] TDD compliance (see `.cursor/rules/tdd.mdc`)
---

# [Comment #1]() by [gerchowl]()

_Posted on February 23, 2026 at 11:57 PM_

## Design

### Scope

Two changes in `scripts/gh_issues.py`:
1. **Phase column** in the issues table — infer pipeline phase from issue comments + branch/PR state
2. **Review+Reviewer column merge** in the PR table — combine two columns into one compact representation

### A. Phase Column (Issues Table)

#### Data Fetching

Extend the existing GraphQL query (`_LINKED_BRANCHES_QUERY`) to also return `comments(first: 20) { nodes { body } }` per issue. This avoids N+1 REST calls — one query fetches both linked branches and comments.

#### Phase Detection Logic

New function `_detect_phase(issue_number, comments, branches, issue_to_pr)` returns a `(label, style)` tuple:

| Priority (highest wins) | Condition | Phase | Style |
|---|---|---|---|
| 1 | Linked PR exists (open) | `In Review` | `bold green` |
| 2 | `## Implementation Plan` comment + branch exists | `In Progress` | `green` |
| 3 | `## Implementation Plan` comment found | `Planned` | `yellow` |
| 4 | `## Design` comment found | `Design` | `yellow` |
| 5 | Branch exists (no design/plan comments) | `Claimed` | `cyan` |
| 6 | None of the above | `Backlog` | `dim` |

Comment scanning checks for lines starting with `## Design` or `## Implementation Plan` — matching the exact H2 headings that `worktree_solve-and-pr` and `design_brainstorm`/`design_plan` post.

"In Progress" uses the simple heuristic: plan exists + branch exists (no commit-count API calls). Good enough for on-demand dashboard use.

#### Column Placement

After PR, before Prio. Width ~11 chars to fit "In Progress".

Result: `# | Type | Title | Assignee | Branch | PR | Phase | Prio | Scope | Effort | SemVer`

### B. Review+Reviewer Merge (PR Table)

Merge the `Review` (8 chars) and `Reviewer` (12 chars) columns into a single `Review` column (~18 chars):

| State | Display |
|---|---|
| Review requested | `?alice` (dim) |
| Commented/pending | `◎bob` (yellow) |
| Approved | `✓carol` (green) |
| Changes requested | `✗dave` (red) |

Multiple reviewers space-separated. Replaces `_infer_review()` + `_extract_reviewers()` with a single `_format_review()` function. No information loss.

### C. Files Changed

| File | Changes |
|---|---|
| `scripts/gh_issues.py` | GraphQL extension, phase detection, column additions, review merge |
| `tests/test_gh_issues.py` | New test file |

### D. Testing Strategy

- **`_detect_phase()`** — unit tests covering all 6 phase transitions with mock data
- **`_format_review()`** — unit tests covering all reviewer state combinations (requested, pending, approved, changes requested, multiple reviewers, no reviewers)
- **Comment heading extraction** — unit test ensuring `## Design` / `## Implementation Plan` scanning works correctly on real-ish comment bodies
- Test type: unit (no API calls, all inputs mocked)

---

# [Comment #2]() by [gerchowl]()

_Posted on February 23, 2026 at 11:58 PM_

## Implementation Plan

### Task 1: Extend GraphQL Query for Comments
- [ ] Modify `_LINKED_BRANCHES_QUERY` to include `comments(first: 20) { nodes { body } }` per issue
- [ ] Update `_fetch_linked_branches()` to return both branches and comments
- [ ] Rename function to `_fetch_linked_branches_and_comments()` or split into two functions

### Task 2: Phase Detection Logic
- [ ] Write unit tests for `_detect_phase()` covering all 6 phase transitions:
  - Backlog (no branch, no comments)
  - Claimed (branch exists, no design/plan comments)
  - Design (`## Design` comment found)
  - Planned (`## Implementation Plan` comment found)
  - In Progress (`## Implementation Plan` + branch exists)
  - In Review (linked PR exists)
- [ ] Implement `_detect_phase(issue_number, comments, branches, issue_to_pr)` function
- [ ] Add helper function to scan comments for H2 headings (`## Design`, `## Implementation Plan`)

### Task 3: Add Phase Column to Issues Table
- [ ] Add "Phase" column after PR column, before Prio column
- [ ] Set column width to ~11 chars
- [ ] Update `_build_table()` to call `_detect_phase()` and add phase cell
- [ ] Apply color styling per phase (dim, cyan, yellow, green, bold green)

### Task 4: Merge Review+Reviewer Columns
- [ ] Write unit tests for `_format_review()` covering:
  - Review requested (`?alice` dim)
  - Commented/pending (`◎bob` yellow)
  - Approved (`✓carol` green)
  - Changes requested (`✗dave` red)
  - Multiple reviewers (space-separated)
  - No reviewers (dim dash)
- [ ] Implement `_format_review(pr)` function combining `_infer_review()` + `_extract_reviewers()` logic
- [ ] Update PR table to remove separate Review and Reviewer columns
- [ ] Add single merged Review column (~18 chars width)

### Task 5: Testing & Verification
- [ ] Run unit tests: `pytest tests/test_gh_issues.py -v`
- [ ] Run lint: `ruff check scripts/gh_issues.py`
- [ ] Run precommit: `pre-commit run --all-files`
- [ ] Manual smoke test: `just gh-issues` to verify Phase column renders correctly

### Acceptance Criteria
- [ ] Phase column renders in issue table with color-coded phase label
- [ ] Phase detection covers: Backlog, Claimed, Design, Planned, In Progress, In Review
- [ ] At least Review+Reviewer column merge implemented in PR table
- [ ] No information loss from column consolidation
- [ ] TDD compliance (tests written first, then implementation)


---

# [Comment #3]() by [gerchowl]()

_Posted on February 24, 2026 at 12:00 AM_

## Autonomous Run Complete

✅ **Implementation completed and PR created**

### Summary
- Created Implementation Plan comment
- Implemented Phase column detection with comprehensive unit tests (13 tests)
- Extended GraphQL query to fetch issue comments
- Added Phase column to issues table
- Implemented Review+Reviewer column merge with unit tests (12 tests)
- Updated PR table to use merged Review column
- All tests pass (91 total)
- Lint and pre-commit checks pass
- CHANGELOG updated

### PR
Created PR #168: https://github.com/vig-os/devcontainer/pull/168

### Commits
- `test(gh_issues): add tests for _detect_phase function`
- `feat(gh_issues): implement _detect_phase function for pipeline phase detection`
- `feat(gh_issues): extend GraphQL query to fetch comments and add Phase column`
- `test(gh_issues): add tests for _format_review function`
- `feat(gh_issues): implement _format_review function for merged Review column`
- `feat(gh_issues): merge Review+Reviewer columns into single Review column`
- `docs: update CHANGELOG for pipeline phase column feature`

Refs: #157

---

# [Comment #4]() by [c-vigo]()

_Posted on June 23, 2026 at 06:56 AM_

Built on the worktree pipeline migrated in #625 (#626 paths, #627 CLI swap). Coordinate so the dashboard reflects the new paths/CLI.

