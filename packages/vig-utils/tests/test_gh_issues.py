"""Unit tests for pure-logic functions in vig_utils.gh_issues.

No subprocess mocking, no Rich rendering tests - just data in, data out.

Refs: #99
"""

import pytest
from vig_utils import gh_issues

_styled = gh_issues._styled
_extract_label = gh_issues._extract_label
_extract_type = gh_issues._extract_type
_extract_scope = gh_issues._extract_scope
_clean_title = gh_issues._clean_title
_format_assignees = gh_issues._format_assignees
_infer_review = gh_issues._infer_review
_extract_reviewers = gh_issues._extract_reviewers
_build_cross_refs = gh_issues._build_cross_refs
_build_pr_table = gh_issues._build_pr_table


class TestFormatCiStatus:
    """Test _format_ci_status for CI column in PR table.

    Ref: #143
    """

    def test_all_passed_shows_green_check(self):
        """All checks passed: ✓ 6/6 in green."""
        pr = {
            "number": 42,
            "statusCheckRollup": [
                {"name": "Build", "conclusion": "SUCCESS"},
                {"name": "Test", "conclusion": "SUCCESS"},
                {"name": "Lint", "conclusion": "SUCCESS"},
            ],
        }
        result = gh_issues._format_ci_status(pr, "vig-os/devcontainer")
        assert "✓" in result
        assert "3/3" in result
        assert "green" in result
        assert "link=https://github.com/vig-os/devcontainer/pull/42/checks" in result

    def test_failures_shows_red_with_failed_check_names(self):
        """Failed checks: ✗ 1/3 in red with failed check names (Build passed, Test+Lint failed)."""
        pr = {
            "number": 10,
            "statusCheckRollup": [
                {"name": "Build", "conclusion": "SUCCESS"},
                {"name": "Test", "conclusion": "FAILURE"},
                {"name": "Lint", "conclusion": "ERROR"},
            ],
        }
        result = gh_issues._format_ci_status(pr, "owner/repo")
        assert "✗" in result
        assert "1/3" in result
        assert "red" in result
        assert "Test" in result
        assert "Lint" in result
        assert "link=https://github.com/owner/repo/pull/10/checks" in result

    def test_in_progress_shows_yellow(self):
        """Some checks pending: ⏳ 2/3 in yellow."""
        pr = {
            "number": 5,
            "statusCheckRollup": [
                {"name": "Build", "conclusion": "SUCCESS"},
                {"name": "Test", "conclusion": "SUCCESS"},
                {"name": "Lint", "conclusion": None},
            ],
        }
        result = gh_issues._format_ci_status(pr, "x/y")
        assert "⏳" in result
        assert "2/3" in result
        assert "yellow" in result

    def test_empty_rollup_shows_dim_dash(self):
        """No checks: — in dim."""
        pr = {"number": 1, "statusCheckRollup": []}
        result = gh_issues._format_ci_status(pr, "a/b")
        assert "—" in result
        assert "dim" in result

    def test_missing_rollup_shows_dim_dash(self):
        """Missing statusCheckRollup: — in dim."""
        pr = {"number": 1}
        result = gh_issues._format_ci_status(pr, "a/b")
        assert "—" in result
        assert "dim" in result

    def test_dedup_by_name_latest_completed_at_wins(self):
        """Duplicate check names: keep latest by completedAt. Ref: #176."""
        pr = {
            "number": 1,
            "statusCheckRollup": [
                {
                    "name": "Status Gate",
                    "conclusion": "FAILURE",
                    "completedAt": "2026-02-24T12:52:49Z",
                },
                {
                    "name": "Status Gate",
                    "conclusion": "FAILURE",
                    "completedAt": "2026-02-24T12:53:39Z",
                },
                {
                    "name": "Status Gate",
                    "conclusion": "SUCCESS",
                    "completedAt": "2026-02-24T12:53:52Z",
                },
            ],
        }
        result = gh_issues._format_ci_status(pr, "a/b")
        assert "✓" in result
        assert "1/1" in result
        assert "green" in result

    def test_dedup_by_name_without_completed_at_last_wins(self):
        """Duplicate check names without completedAt: last in list wins. Ref: #176."""
        pr = {
            "number": 1,
            "statusCheckRollup": [
                {"name": "Lint", "conclusion": "FAILURE"},
                {"name": "Lint", "conclusion": "SUCCESS"},
            ],
        }
        result = gh_issues._format_ci_status(pr, "a/b")
        assert "✓" in result
        assert "1/1" in result


class TestDedupeStatusChecks:
    """Test _dedupe_status_checks recency keying.

    Ref: #1539
    """

    def test_in_progress_rerun_beats_older_completed_failure(self):
        """A live rerun (completedAt null) wins over the FAILURE it supersedes."""
        rollup = [
            {
                "name": "Project Checks",
                "conclusion": "FAILURE",
                "status": "COMPLETED",
                "startedAt": "2026-08-17T12:00:00Z",
                "completedAt": "2026-08-17T12:05:00Z",
            },
            {
                "name": "Project Checks",
                "conclusion": None,
                "status": "IN_PROGRESS",
                "startedAt": "2026-08-17T12:30:00Z",
                "completedAt": None,
            },
        ]
        result = gh_issues._dedupe_status_checks(rollup)
        assert len(result) == 1
        assert result[0]["status"] == "IN_PROGRESS"

    def test_newer_completed_success_beats_older_failure(self):
        """A completed rerun that passed wins over the older FAILURE."""
        rollup = [
            {
                "name": "Project Checks",
                "conclusion": "FAILURE",
                "startedAt": "2026-08-17T12:00:00Z",
                "completedAt": "2026-08-17T12:05:00Z",
            },
            {
                "name": "Project Checks",
                "conclusion": "SUCCESS",
                "startedAt": "2026-08-17T12:30:00Z",
                "completedAt": "2026-08-17T12:35:00Z",
            },
        ]
        result = gh_issues._dedupe_status_checks(rollup)
        assert [c["conclusion"] for c in result] == ["SUCCESS"]

    def test_distinct_names_are_untouched(self):
        """Different check names all survive dedup."""
        rollup = [
            {
                "name": "Build",
                "conclusion": "SUCCESS",
                "startedAt": "2026-08-17T12:00:00Z",
            },
            {
                "name": "Test",
                "conclusion": "FAILURE",
                "startedAt": "2026-08-17T11:00:00Z",
            },
        ]
        result = gh_issues._dedupe_status_checks(rollup)
        assert {c["name"] for c in result} == {"Build", "Test"}
        assert len(result) == 2

    def test_winner_is_order_independent(self):
        """Input order does not change which run of a name survives."""
        older = {
            "name": "Project Checks",
            "conclusion": "FAILURE",
            "startedAt": "2026-08-17T12:00:00Z",
            "completedAt": "2026-08-17T12:05:00Z",
        }
        newer = {
            "name": "Project Checks",
            "conclusion": None,
            "status": "IN_PROGRESS",
            "startedAt": "2026-08-17T12:30:00Z",
            "completedAt": None,
        }
        forward = gh_issues._dedupe_status_checks([older, newer])
        backward = gh_issues._dedupe_status_checks([newer, older])
        assert forward == backward == [newer]

    def test_status_context_falls_back_to_created_at(self):
        """StatusContexts carry createdAt, not startedAt; recency still works."""
        rollup = [
            {
                "context": "legacy/status",
                "state": "FAILURE",
                "createdAt": "2026-08-17T12:00:00Z",
            },
            {
                "context": "legacy/status",
                "state": "SUCCESS",
                "createdAt": "2026-08-17T12:30:00Z",
            },
        ]
        result = gh_issues._dedupe_status_checks(rollup)
        assert [c["state"] for c in result] == ["SUCCESS"]

    def test_distinct_status_contexts_stay_separate_entries(self):
        """Two contexts are two buckets, not one "?" bucket. Ref: #1544."""
        rollup = [
            {
                "context": "ci/legacy",
                "state": "SUCCESS",
                "createdAt": "2026-08-17T12:00:00Z",
            },
            {
                "context": "security/scan",
                "state": "FAILURE",
                "createdAt": "2026-08-17T11:00:00Z",
            },
        ]
        result = gh_issues._dedupe_status_checks(rollup)
        assert {c["context"] for c in result} == {"ci/legacy", "security/scan"}
        assert len(result) == 2

    def test_status_context_supersedes_a_same_keyed_check_run(self):
        """A context equal to a check name shares its bucket; newest wins.

        Mirrors the release gates' ``.name // .context // "?"`` grouping
        (#1537/#1541). Ref: #1544.
        """
        rollup = [
            {
                "name": "Project Checks",
                "conclusion": "FAILURE",
                "startedAt": "2026-08-17T12:00:00Z",
                "completedAt": "2026-08-17T12:05:00Z",
            },
            {
                "context": "Project Checks",
                "state": "SUCCESS",
                "createdAt": "2026-08-17T12:30:00Z",
            },
        ]
        result = gh_issues._dedupe_status_checks(rollup)
        assert len(result) == 1
        assert result[0]["state"] == "SUCCESS"

    def test_in_progress_rerun_shown_as_pending_in_ci_cell(self):
        """The CI cell reports the live rerun as pending, not as a failure."""
        pr = {
            "number": 7,
            "statusCheckRollup": [
                {
                    "name": "Project Checks",
                    "conclusion": "FAILURE",
                    "startedAt": "2026-08-17T12:00:00Z",
                    "completedAt": "2026-08-17T12:05:00Z",
                },
                {
                    "name": "Project Checks",
                    "conclusion": None,
                    "startedAt": "2026-08-17T12:30:00Z",
                    "completedAt": None,
                },
            ],
        }
        result = gh_issues._format_ci_status(pr, "a/b")
        assert "⏳" in result
        assert "0/1" in result
        assert "yellow" in result


class TestFormatCiStatusCommitStatuses:
    """Test _format_ci_status classification of StatusContext entries.

    StatusContexts carry ``state`` where CheckRuns carry ``conclusion``, so the
    cell classifies on a normalized verdict, as the release gates do.

    Ref: #1544
    """

    def _pr(self, rollup: list[dict]) -> dict:
        return {"number": 3, "statusCheckRollup": rollup}

    @pytest.mark.parametrize("state", ["FAILURE", "ERROR"])
    def test_red_state_renders_failed(self, state):
        """A red commit status turns the cell red and names the context."""
        pr = self._pr(
            [
                {
                    "context": "ci/legacy",
                    "state": state,
                    "createdAt": "2026-08-17T12:00:00Z",
                },
            ]
        )
        result = gh_issues._format_ci_status(pr, "a/b")
        assert "✗" in result
        assert "0/1" in result
        assert "red" in result
        assert "ci/legacy" in result

    def test_success_state_counts_as_passed(self):
        """A green commit status counts toward the pass tally."""
        pr = self._pr(
            [
                {
                    "context": "ci/legacy",
                    "state": "SUCCESS",
                    "createdAt": "2026-08-17T12:00:00Z",
                },
                {
                    "context": "security/scan",
                    "state": "SUCCESS",
                    "createdAt": "2026-08-17T12:00:00Z",
                },
            ]
        )
        result = gh_issues._format_ci_status(pr, "a/b")
        assert "✓" in result
        assert "2/2" in result
        assert "green" in result

    @pytest.mark.parametrize("state", ["PENDING", "EXPECTED"])
    def test_non_terminal_state_renders_pending(self, state):
        """PENDING and EXPECTED statuses render as pending, not as passed."""
        pr = self._pr(
            [
                {
                    "name": "Build",
                    "conclusion": "SUCCESS",
                    "startedAt": "2026-08-17T12:00:00Z",
                },
                {
                    "context": "ci/legacy",
                    "state": state,
                    "createdAt": "2026-08-17T12:00:00Z",
                },
            ]
        )
        result = gh_issues._format_ci_status(pr, "a/b")
        assert "⏳" in result
        assert "1/2" in result
        assert "yellow" in result

    def test_red_status_context_beats_green_check_runs(self):
        """A red commit status alongside green checks still reports failure."""
        pr = self._pr(
            [
                {
                    "name": "Build",
                    "conclusion": "SUCCESS",
                    "startedAt": "2026-08-17T12:00:00Z",
                },
                {
                    "context": "ci/legacy",
                    "state": "FAILURE",
                    "createdAt": "2026-08-17T12:00:00Z",
                },
            ]
        )
        result = gh_issues._format_ci_status(pr, "a/b")
        assert "✗" in result
        assert "1/2" in result
        assert "red" in result
        assert "ci/legacy" in result


class TestGhLink:
    """Test _gh_link helper for clickable issue/PR numbers."""

    def test_issue_link_format(self):
        """Issue number renders as Rich hyperlink to GitHub issues URL."""
        result = gh_issues._gh_link("vig-os/devcontainer", 104, "issues")
        assert (
            result
            == "[link=https://github.com/vig-os/devcontainer/issues/104]104[/link]"
        )

    def test_pr_link_format(self):
        """PR number renders as Rich hyperlink to GitHub pull URL."""
        result = gh_issues._gh_link("vig-os/devcontainer", 42, "pull")
        assert (
            result == "[link=https://github.com/vig-os/devcontainer/pull/42]42[/link]"
        )


class TestStyled:
    def test_wraps_value_in_markup(self):
        assert _styled("hello", "bold red") == "[bold red]hello[/]"

    def test_empty_value(self):
        assert _styled("", "dim") == "[dim][/]"

    def test_empty_style(self):
        assert _styled("text", "") == "[]text[/]"


class TestExtractLabel:
    def test_matching_prefix(self):
        labels = [{"name": "priority:high"}]
        assert _extract_label(labels, "priority:") == "[red]high[/]"

    def test_no_matching_prefix(self):
        labels = [{"name": "feature"}]
        assert _extract_label(labels, "priority:") == ""

    def test_empty_labels(self):
        assert _extract_label([], "priority:") == ""

    def test_unknown_label_uses_dim(self):
        labels = [{"name": "priority:unknown"}]
        assert _extract_label(labels, "priority:") == "[dim]unknown[/]"

    def test_first_match_wins(self):
        labels = [{"name": "priority:high"}, {"name": "priority:low"}]
        result = _extract_label(labels, "priority:")
        assert result == "[red]high[/]"

    def test_effort_label(self):
        labels = [{"name": "effort:small"}]
        assert _extract_label(labels, "effort:") == "[green]small[/]"

    def test_semver_label(self):
        labels = [{"name": "semver:patch"}]
        assert _extract_label(labels, "semver:") == "[green]patch[/]"


class TestExtractType:
    @pytest.mark.parametrize(
        ("label", "expected"),
        [
            ("feature", "[cyan]feature[/]"),
            ("bug", "[bold red]bug[/]"),
            ("discussion", "[bright_magenta]discussion[/]"),
            ("chore", "[dim]chore[/]"),
        ],
    )
    def test_type_label_styles(self, label: str, expected: str):
        assert _extract_type([{"name": label}]) == expected

    def test_no_type_label(self):
        labels = [{"name": "priority:high"}, {"name": "area:ci"}]
        assert _extract_type(labels) == ""

    def test_empty_labels(self):
        assert _extract_type([]) == ""


class TestExtractScope:
    def test_single_area(self):
        labels = [{"name": "area:ci"}]
        assert _extract_scope(labels) == "[blue]ci[/]"

    def test_multiple_areas(self):
        labels = [{"name": "area:ci"}, {"name": "area:docs"}]
        assert _extract_scope(labels) == "[blue]ci[/], [blue]docs[/]"

    def test_no_area_labels(self):
        labels = [{"name": "feature"}, {"name": "priority:high"}]
        assert _extract_scope(labels) == ""

    def test_empty_labels(self):
        assert _extract_scope([]) == ""


class TestCleanTitle:
    @pytest.mark.parametrize(
        ("title", "expected"),
        [
            ("[FEATURE] Add tests", "Add tests"),
            ("[BUG] Fix crash", "Fix crash"),
            ("[TASK] Update deps", "Update deps"),
            ("[DISCUSSION] API design", "API design"),
            ("[CHORE] Bump versions", "Bump versions"),
        ],
    )
    def test_strips_known_prefixes(self, title: str, expected: str):
        assert _clean_title(title) == expected

    def test_no_prefix_unchanged(self):
        assert _clean_title("Plain title") == "Plain title"

    def test_empty_title(self):
        assert _clean_title("") == ""


class TestFormatAssignees:
    def test_empty_list(self):
        assert _format_assignees([]) == "[dim]—[/]"

    def test_single_assignee(self):
        assignees = [{"login": "alice"}]
        assert _format_assignees(assignees) == "[bright_white]alice[/]"

    def test_multiple_assignees(self):
        assignees = [{"login": "alice"}, {"login": "bob"}]
        result = _format_assignees(assignees)
        assert result == "[bright_white]alice[/], [bright_white]bob[/]"


class TestInferReview:
    def test_approved_decision(self):
        pr = {"reviewDecision": "APPROVED"}
        assert _infer_review(pr) == ("APPROVED", "approved")

    def test_changes_requested_decision(self):
        pr = {"reviewDecision": "CHANGES_REQUESTED"}
        assert _infer_review(pr) == ("CHANGES_REQUESTED", "changes")

    def test_review_required_decision(self):
        pr = {"reviewDecision": "REVIEW_REQUIRED"}
        assert _infer_review(pr) == ("REVIEW_REQUIRED", "pending")

    def test_unknown_decision_uses_lowercase(self):
        pr = {"reviewDecision": "DISMISSED"}
        assert _infer_review(pr) == ("DISMISSED", "dismissed")

    def test_fallback_to_latest_reviews(self):
        pr = {
            "reviewDecision": "",
            "latestReviews": [{"state": "APPROVED"}],
        }
        assert _infer_review(pr) == ("APPROVED", "approved")

    def test_fallback_latest_reviews_last_wins(self):
        pr = {
            "reviewDecision": "",
            "latestReviews": [
                {"state": "APPROVED"},
                {"state": "CHANGES_REQUESTED"},
            ],
        }
        assert _infer_review(pr) == ("CHANGES_REQUESTED", "changes")

    def test_fallback_to_review_requests(self):
        pr = {
            "reviewDecision": "",
            "latestReviews": [],
            "reviewRequests": [{"login": "alice"}],
        }
        assert _infer_review(pr) == ("REVIEW_REQUIRED", "pending")

    def test_no_review_info(self):
        pr = {"reviewDecision": "", "latestReviews": [], "reviewRequests": []}
        assert _infer_review(pr) == ("", "—")

    def test_empty_pr_dict(self):
        assert _infer_review({}) == ("", "—")


class TestExtractReviewers:
    def test_no_reviews_or_requests(self):
        pr = {"latestReviews": [], "reviewRequests": []}
        assert _extract_reviewers(pr) == "[dim]—[/]"

    def test_approved_reviewer(self):
        pr = {
            "latestReviews": [{"author": {"login": "alice"}, "state": "APPROVED"}],
            "reviewRequests": [],
        }
        assert _extract_reviewers(pr) == "[green]alice[/]"

    def test_changes_requested_reviewer(self):
        pr = {
            "latestReviews": [
                {"author": {"login": "bob"}, "state": "CHANGES_REQUESTED"},
            ],
            "reviewRequests": [],
        }
        assert _extract_reviewers(pr) == "[red]bob[/]"

    def test_requested_reviewer(self):
        pr = {
            "latestReviews": [],
            "reviewRequests": [{"login": "carol"}],
        }
        assert _extract_reviewers(pr) == "[dim italic]?carol[/]"

    def test_mixed_reviewers(self):
        pr = {
            "latestReviews": [{"author": {"login": "alice"}, "state": "APPROVED"}],
            "reviewRequests": [{"login": "bob"}],
        }
        result = _extract_reviewers(pr)
        assert "[green]alice[/]" in result
        assert "[dim italic]?bob[/]" in result

    def test_review_request_with_name_fallback(self):
        pr = {
            "latestReviews": [],
            "reviewRequests": [{"login": "", "name": "team-review"}],
        }
        assert _extract_reviewers(pr) == "[dim italic]?team-review[/]"

    def test_empty_pr_dict(self):
        assert _extract_reviewers({}) == "[dim]—[/]"

    def test_reviewer_already_in_latest_not_duplicated(self):
        pr = {
            "latestReviews": [{"author": {"login": "alice"}, "state": "APPROVED"}],
            "reviewRequests": [{"login": "alice"}],
        }
        result = _extract_reviewers(pr)
        assert result.count("alice") == 1


class TestBuildCrossRefs:
    def test_branch_match(self):
        branches = {42: "feature/42-add-tests"}
        prs = [{"number": 100, "headRefName": "feature/42-add-tests", "body": ""}]
        issue_to_pr, pr_to_issues = _build_cross_refs(branches, prs)
        assert issue_to_pr == {42: 100}
        assert pr_to_issues == {100: [42]}

    @pytest.mark.parametrize(
        "body", ["Closes #7", "Fixes #7", "Resolves #7", "closes #7"]
    )
    def test_closing_keyword_match(self, body: str):
        branches = {}
        prs = [{"number": 100, "headRefName": "x", "body": body}]
        issue_to_pr, pr_to_issues = _build_cross_refs(branches, prs)
        assert issue_to_pr == {7: 100}
        assert pr_to_issues == {100: [7]}

    def test_both_branch_and_keyword(self):
        branches = {42: "feature/42-stuff"}
        prs = [
            {
                "number": 100,
                "headRefName": "feature/42-stuff",
                "body": "Closes #42\nAlso fixes #43",
            },
        ]
        issue_to_pr, pr_to_issues = _build_cross_refs(branches, prs)
        assert issue_to_pr[42] == 100
        assert issue_to_pr[43] == 100
        assert pr_to_issues[100] == [42, 43]

    def test_no_matches(self):
        branches = {42: "feature/42-stuff"}
        prs = [{"number": 100, "headRefName": "unrelated-branch", "body": "No refs"}]
        issue_to_pr, pr_to_issues = _build_cross_refs(branches, prs)
        assert issue_to_pr == {}
        assert pr_to_issues == {}

    def test_empty_inputs(self):
        issue_to_pr, pr_to_issues = _build_cross_refs({}, [])
        assert issue_to_pr == {}
        assert pr_to_issues == {}

    def test_none_body(self):
        branches = {}
        prs = [{"number": 100, "headRefName": "x", "body": None}]
        issue_to_pr, pr_to_issues = _build_cross_refs(branches, prs)
        assert issue_to_pr == {}

    def test_multiple_prs(self):
        branches = {42: "feature/42-stuff", 43: "feature/43-other"}
        prs = [
            {"number": 100, "headRefName": "feature/42-stuff", "body": ""},
            {"number": 101, "headRefName": "feature/43-other", "body": ""},
        ]
        issue_to_pr, pr_to_issues = _build_cross_refs(branches, prs)
        assert issue_to_pr == {42: 100, 43: 101}
        assert pr_to_issues == {100: [42], 101: [43]}

    def test_refs_keyword_match(self):
        branches = {}
        prs = [{"number": 100, "headRefName": "some-branch", "body": "Refs: #102"}]
        issue_to_pr, pr_to_issues = _build_cross_refs(branches, prs)
        assert issue_to_pr == {102: 100}
        assert pr_to_issues == {100: [102]}

    def test_refs_comma_separated(self):
        branches = {}
        prs = [{"number": 100, "headRefName": "x", "body": "Refs: #102, #103"}]
        issue_to_pr, pr_to_issues = _build_cross_refs(branches, prs)
        assert issue_to_pr == {102: 100, 103: 100}
        assert pr_to_issues == {100: [102, 103]}


def _minimal_pr(number=42, linked_issues=None):
    """Build a minimal PR dict sufficient for _build_pr_table."""
    return {
        "number": number,
        "title": "Test PR",
        "author": {"login": "alice"},
        "assignees": [],
        "headRefName": "feature/42",
        "baseRefName": "dev",
        "isDraft": False,
        "additions": 10,
        "deletions": 2,
        "changedFiles": 1,
        "reviewDecision": "",
        "latestReviews": [],
        "reviewRequests": [],
        "statusCheckRollup": [],
    }


class TestBuildPrTableIssueLinks:
    """Regression: issue numbers in PR table Issues column must be clickable links.

    Ref: #174
    """

    def _issues_cell(self, table):
        """Extract the raw Issues column cell string from the first row."""
        issues_col_idx = 4
        return table.columns[issues_col_idx]._cells[0]

    def test_linked_issues_are_hyperlinks(self):
        """Issue numbers in the Issues column render as Rich hyperlinks, not plain styled text."""
        pr = _minimal_pr(number=42)
        pr_to_issues = {42: [100, 101]}
        table = _build_pr_table("Test", [pr], pr_to_issues, "owner/repo")

        cell = self._issues_cell(table)
        assert "link=https://github.com/owner/repo/issues/100" in cell
        assert "link=https://github.com/owner/repo/issues/101" in cell
