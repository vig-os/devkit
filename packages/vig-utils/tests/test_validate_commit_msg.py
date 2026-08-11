"""
Tests for vig_utils.validate_commit_msg.

These tests run locally (pytest); they do not require the devcontainer CLI.
"""

import sys

import pytest
from vig_utils.validate_commit_msg import (
    DEFAULT_APPROVED_TYPES,
    DEFAULT_REFS_OPTIONAL_TYPES,
    main,
    validate_commit_message,
)


class TestValidateCommitMessage:
    """Test validate_commit_message() with valid and invalid messages."""

    def test_valid_feat_with_issue_ref(self):
        msg = "feat: add new feature\n\nRefs: #36\n"
        valid, err = validate_commit_message(msg)
        assert valid is True
        assert err is None

    def test_valid_feat_with_scope_and_hash_ref(self):
        msg = "feat(ci): add workflow\n\nRefs: #36\n"
        valid, err = validate_commit_message(msg)
        assert valid is True
        assert err is None

    def test_valid_fix_with_multiple_refs(self):
        msg = "fix: correct version substitution\n\nRefs: #42, REQ-123\n"
        valid, err = validate_commit_message(msg)
        assert valid is True
        assert err is None

    def test_valid_docs_with_req_risk_sop_refs(self):
        msg = "docs: describe commit standard\n\nRefs: #36, REQ-DOC-01, RISK-H-02, SOP-DEV-02\n"
        valid, err = validate_commit_message(msg)
        assert valid is True
        assert err is None

    def test_valid_all_approved_types(self):
        """Every default type validates, including `perf` (Refs #1030 — CI's
        validate-commit-range runs with no --types override, so
        DEFAULT_APPROVED_TYPES is the effective allowlist there)."""
        assert "perf" in DEFAULT_APPROVED_TYPES
        for ctype in sorted(DEFAULT_APPROVED_TYPES):
            msg = f"{ctype}: do something\n\nRefs: #1\n"
            valid, err = validate_commit_message(msg)
            assert valid is True, f"Type {ctype} should be valid: {err}"
            assert err is None

    def test_valid_scope_with_hyphens(self):
        msg = "chore(deps): bump pre-commit\n\nRefs: #37\n"
        valid, err = validate_commit_message(msg)
        assert valid is True
        assert err is None

    def test_valid_breaking_change_exclamation(self):
        msg = "feat!: breaking change\n\nRefs: #36\n"
        valid, err = validate_commit_message(msg)
        assert valid is True
        assert err is None

    def test_valid_with_optional_body(self):
        msg = "feat: add feature\n\nBody first paragraph.\n\nBody second paragraph.\n\nRefs: #36\n"
        valid, err = validate_commit_message(msg)
        assert valid is True
        assert err is None

    def test_valid_message_without_trailing_newline(self):
        msg = "feat: add x\n\nRefs: #36"
        valid, err = validate_commit_message(msg)
        assert valid is True
        assert err is None

    def test_invalid_empty_message(self):
        valid, err = validate_commit_message("")
        assert valid is False
        assert "empty" in err.lower()

    def test_invalid_unknown_type(self):
        msg = "feature: add new feature\n\nRefs: #36\n"
        valid, err = validate_commit_message(msg)
        assert valid is False
        assert "Unknown commit type" in err
        assert "feature" in err

    def test_invalid_missing_refs_line(self):
        msg = "feat: add new feature\n\nBody with no Refs line.\n"
        valid, err = validate_commit_message(msg)
        assert valid is False
        assert "Refs" in err

    def test_invalid_no_blank_line_before_refs(self):
        msg = "feat: add new feature\nRefs: #36\n"
        valid, err = validate_commit_message(msg)
        assert valid is False
        assert "blank line" in err.lower()

    def test_invalid_single_line_only(self):
        msg = "feat: add new feature\n"
        valid, err = validate_commit_message(msg)
        assert valid is False
        assert "blank" in err.lower() or "Refs" in err

    def test_invalid_malformed_first_line_no_colon(self):
        msg = "feat add new feature\n\nRefs: #36\n"
        valid, err = validate_commit_message(msg)
        assert valid is False
        assert "First line" in err or "type" in err

    @pytest.mark.parametrize(
        "msg",
        [
            "feat: add feature\n\nRefs: 36\n",
            "feat: add feature\n\nRefs:\n",
            "feat: add feature\n\nRefs: abc\n",
        ],
        ids=["missing_hashtag", "empty", "invalid_id_format"],
    )
    def test_invalid_refs_line_variants(self, msg):
        valid, err = validate_commit_message(msg)
        assert valid is False
        assert "Refs" in err or "reference" in err.lower()

    def test_invalid_refs_without_issue(self):
        msg = "feat: add feature\n\nRefs: REQ-123\n"
        valid, err = validate_commit_message(msg)
        assert valid is False
        assert "issue" in err.lower()

    def test_invalid_multiple_refs_lines(self):
        msg = "feat: add feature\n\nRefs: #36\nRefs: #37\n"
        valid, err = validate_commit_message(msg)
        assert valid is False
        assert "Only one Refs line" in err

    def test_invalid_content_after_refs_line(self):
        msg = "feat: add feature\n\nRefs: #36\n\nExtra line after Refs.\n"
        valid, err = validate_commit_message(msg)
        assert valid is False
        assert "Only one Refs line" in err

    def test_invalid_empty_whitespace_only(self):
        """Test commit message with only whitespace."""
        msg = "\n\n   \n"
        valid, err = validate_commit_message(msg)
        assert valid is False
        assert "empty" in err.lower()


class TestChoreRefsExemption:
    """Test that chore commits may omit the Refs line."""

    def test_chore_valid_without_refs(self):
        """chore commits are valid without a Refs line."""
        msg = "chore: sync dev with main after merge\n\n"
        valid, err = validate_commit_message(msg)
        assert valid is True
        assert err is None

    def test_chore_valid_without_refs_with_body(self):
        """chore commits with a body but no Refs are valid."""
        msg = "chore: maintenance task\n\nSome body explaining what happened.\n"
        valid, err = validate_commit_message(msg)
        assert valid is True
        assert err is None

    def test_chore_valid_with_refs(self):
        """chore commits with a Refs line are also valid."""
        msg = "chore: sync dev with main\n\nRefs: #42\n"
        valid, err = validate_commit_message(msg)
        assert valid is True
        assert err is None

    def test_chore_valid_with_scope_without_refs(self):
        """chore(scope) commits are valid without Refs."""
        msg = "chore(deps): bump pre-commit\n\n"
        valid, err = validate_commit_message(msg)
        assert valid is True
        assert err is None

    def test_chore_invalid_malformed_refs_still_rejected(self):
        """chore commits with a malformed Refs line are still invalid."""
        msg = "chore: do something\n\nRefs: abc\n"
        valid, err = validate_commit_message(msg)
        assert valid is False
        assert "Refs" in err or "reference" in err.lower()

    def test_chore_still_needs_blank_line(self):
        """chore commits still require a blank line after the subject."""
        msg = "chore: do something\nRefs: #36\n"
        valid, err = validate_commit_message(msg)
        assert valid is False
        assert "blank line" in err.lower()

    def test_non_chore_types_still_require_refs(self):
        """All non-chore types still require a Refs line."""
        for ctype in sorted(DEFAULT_APPROVED_TYPES - DEFAULT_REFS_OPTIONAL_TYPES):
            msg = f"{ctype}: do something\n\n"
            valid, err = validate_commit_message(msg)
            assert valid is False, f"Type {ctype} should require Refs but passed"
            assert "Refs" in err


class TestCustomApprovedTypes:
    """Test validate_commit_message() with custom approved types."""

    def test_custom_types_valid_with_custom_type(self):
        """Custom types override defaults."""
        custom_types = frozenset({"mytype", "othertype"})
        msg = "mytype: do something\n\nRefs: #1\n"
        valid, err = validate_commit_message(msg, approved_types=custom_types)
        assert valid is True
        assert err is None

    def test_custom_types_reject_default_type(self):
        """Default types are rejected when custom types are used."""
        custom_types = frozenset({"mytype", "othertype"})
        msg = "feat: add feature\n\nRefs: #1\n"
        valid, err = validate_commit_message(msg, approved_types=custom_types)
        assert valid is False
        assert "Unknown commit type" in err
        assert "feat" in err

    def test_custom_types_empty_set_rejects_all(self):
        """Empty custom types set rejects all types."""
        custom_types = frozenset()
        msg = "feat: add feature\n\nRefs: #1\n"
        valid, err = validate_commit_message(msg, approved_types=custom_types)
        assert valid is False
        assert "Unknown commit type" in err


class TestCustomRefsOptionalTypes:
    """Test validate_commit_message() with custom refs-optional types."""

    def test_custom_refs_optional_types_makes_type_optional(self):
        """Custom refs-optional-types makes specified types not require Refs."""
        custom_optional = frozenset({"feat", "build"})
        msg = "feat: add feature\n\n"
        valid, err = validate_commit_message(msg, refs_optional_types=custom_optional)
        assert valid is True
        assert err is None

    def test_custom_refs_optional_types_preserves_others(self):
        """Types not in refs-optional still require Refs."""
        custom_optional = frozenset({"chore"})
        msg = "fix: fix bug\n\n"
        valid, err = validate_commit_message(msg, refs_optional_types=custom_optional)
        assert valid is False
        assert "Refs" in err

    def test_custom_refs_optional_types_empty_all_require_refs(self):
        """Empty refs-optional-types makes all types require Refs."""
        custom_optional = frozenset()
        msg = "chore: do something\n\n"
        valid, err = validate_commit_message(msg, refs_optional_types=custom_optional)
        assert valid is False
        assert "Refs" in err

    def test_custom_refs_optional_types_multiple(self):
        """Multiple custom refs-optional types work together."""
        custom_optional = frozenset({"chore", "build", "ci"})
        for ctype in custom_optional:
            msg = f"{ctype}: do something\n\n"
            valid, err = validate_commit_message(
                msg, refs_optional_types=custom_optional
            )
            assert valid is True, f"Type {ctype} should be optional: {err}"

    def test_custom_refs_optional_with_refs_still_valid(self):
        """Custom refs-optional types with Refs are still valid."""
        custom_optional = frozenset({"feat"})
        msg = "feat: add feature\n\nRefs: #1\n"
        valid, err = validate_commit_message(msg, refs_optional_types=custom_optional)
        assert valid is True
        assert err is None


class TestCustomApprovedAndOptionalTypes:
    """Test combining custom approved types and custom refs-optional types.

    Type approval and refs-optionality are independent lookups; one combined
    case pins that the two custom sets compose.
    """

    def test_combined_custom_types(self):
        """Custom approved types with custom refs-optional types."""
        custom_types = frozenset({"task", "hotfix", "release"})
        custom_optional = frozenset({"release"})
        msg = "release: prepare v1.0\n\n"
        valid, err = validate_commit_message(
            msg, approved_types=custom_types, refs_optional_types=custom_optional
        )
        assert valid is True
        assert err is None


class TestCustomScopes:
    """Test validate_commit_message() with custom approved scopes."""

    def test_scopes_not_enforced_by_default(self):
        """Scopes are not enforced when not provided."""
        msg = "feat(any-scope): add feature\n\nRefs: #1\n"
        valid, err = validate_commit_message(msg)
        assert valid is True
        assert err is None

    @pytest.mark.parametrize(
        ("scopes", "subject"),
        [
            pytest.param(
                frozenset(), "feat(random-scope): x", id="empty_set_no_enforcement"
            ),
            pytest.param(
                frozenset({"api", "cli", "utils"}), "feat(api): x", id="single_valid"
            ),
            pytest.param(frozenset({"api", "cli"}), "feat: x", id="scope_optional"),
            pytest.param(
                frozenset({"api-v2", "cli-tool"}), "feat(api-v2): x", id="hyphens"
            ),
            pytest.param(
                frozenset({"api", "cli", "utils"}),
                "feat(api, cli): x",
                id="multiple_comma",
            ),
            pytest.param(
                frozenset({"api", "cli", "utils"}),
                "feat(api , cli , utils): x",
                id="spaces_around_commas",
            ),
        ],
    )
    def test_valid_scopes(self, scopes, subject):
        msg = f"{subject}\n\nRefs: #1\n"
        valid, err = validate_commit_message(msg, approved_scopes=scopes)
        assert valid is True, err
        assert err is None

    @pytest.mark.parametrize(
        ("subject", "rejected"),
        [
            pytest.param("feat(database): x", "database", id="not_in_list"),
            pytest.param("feat(API): x", "API", id="case_sensitive"),
            pytest.param(
                "feat(api, invalid, cli): x", "invalid", id="one_invalid_among_valid"
            ),
            pytest.param("feat(invalid1, invalid2): x", "invalid1", id="all_invalid"),
        ],
    )
    def test_invalid_scopes(self, subject, rejected):
        custom_scopes = frozenset({"api", "cli"})
        msg = f"{subject}\n\nRefs: #1\n"
        valid, err = validate_commit_message(msg, approved_scopes=custom_scopes)
        assert valid is False
        assert "Unknown scope" in err
        assert rejected in err

    def test_require_scope_without_approved_scopes(self):
        """require_scope=True without approved_scopes should fail early."""
        msg = "feat(api): add feature\n\nRefs: #1\n"
        valid, err = validate_commit_message(msg, require_scope=True)
        assert valid is False
        assert "require_scope=True requires approved_scopes" in err

    @pytest.mark.parametrize(
        ("subject", "expect_valid", "err_fragment"),
        [
            pytest.param("feat(api): x", True, None, id="with_scope"),
            pytest.param("feat: x", False, "scope is required", id="without_scope"),
            pytest.param("feat(api, cli): x", True, None, id="multiple_scopes"),
            pytest.param(
                "feat(invalid): x", False, "Unknown scope", id="invalid_scope"
            ),
        ],
    )
    def test_require_scope_enforcement(self, subject, expect_valid, err_fragment):
        custom_scopes = frozenset({"api", "cli"})
        msg = f"{subject}\n\nRefs: #1\n"
        valid, err = validate_commit_message(
            msg, approved_scopes=custom_scopes, require_scope=True
        )
        assert valid is expect_valid, err
        if err_fragment:
            assert err_fragment in err

    def test_combined_types_and_scopes(self):
        """Use custom types with custom scopes."""
        custom_types = frozenset({"feature", "bugfix"})
        custom_scopes = frozenset({"backend", "frontend"})
        msg = "feature(backend): add API\n\nRefs: #1\n"
        valid, err = validate_commit_message(
            msg, approved_types=custom_types, approved_scopes=custom_scopes
        )
        assert valid is True
        assert err is None


class TestValidateCommitMsgMain:
    """Test main()'s own logic: argv parsing, option splitting, exit codes.

    Validation behavior itself is covered above through the library API.
    """

    def _run_main(self, monkeypatch, *argv):
        monkeypatch.setattr(sys, "argv", ["validate_commit_msg.py", *argv])
        return main()

    def test_main_valid_message_file(self, tmp_path, monkeypatch):
        msg_file = tmp_path / "msg"
        msg_file.write_text("feat: add feature\n\nRefs: #36\n")
        assert self._run_main(monkeypatch, str(msg_file)) == 0

    def test_main_invalid_message_file(self, tmp_path, monkeypatch):
        msg_file = tmp_path / "msg"
        msg_file.write_text("feat: add feature\n\n")  # missing Refs
        assert self._run_main(monkeypatch, str(msg_file)) == 1

    def test_main_file_not_found(self, monkeypatch):
        assert self._run_main(monkeypatch, "/nonexistent/path/msg") == 2

    @pytest.mark.parametrize(
        "argv", [[], ["arg1", "arg2"]], ids=["no_args", "too_many_args"]
    )
    def test_main_wrong_arg_count(self, capsys, monkeypatch, argv):
        """argparse exits 2 with usage on a wrong argument count."""
        monkeypatch.setattr(sys, "argv", ["validate_commit_msg.py", *argv])
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 2
        captured = capsys.readouterr()
        assert "usage" in (captured.out + captured.err).lower()

    def test_main_with_custom_types(self, tmp_path, monkeypatch):
        """--types wires a comma-split allowlist through to validation."""
        msg_file = tmp_path / "msg"
        msg_file.write_text("custom: do something\n\nRefs: #1\n")
        assert (
            self._run_main(monkeypatch, str(msg_file), "--types", "custom,other") == 0
        )

    def test_main_with_spaces_in_comma_separated_types(self, tmp_path, monkeypatch):
        """--types entries are stripped of whitespace around commas."""
        msg_file = tmp_path / "msg"
        msg_file.write_text("feat: add feature\n\nRefs: #1\n")
        assert (
            self._run_main(monkeypatch, str(msg_file), "--types", "feat , fix , docs")
            == 0
        )

    def test_main_with_custom_refs_optional_types(self, tmp_path, monkeypatch):
        """--refs-optional-types wires the exemption set through."""
        msg_file = tmp_path / "msg"
        msg_file.write_text("custom: do something\n\n")
        assert (
            self._run_main(
                monkeypatch,
                str(msg_file),
                "--types",
                "custom,other",
                "--refs-optional-types",
                "custom",
            )
            == 0
        )


class TestGitHubLinkedRefs:
    """Test that Refs line accepts GitHub auto-linked issue format [#N](URL).

    After pushing, GitHub rewrites '#31' to '[#31](https://github.com/…/issues/31)'.
    The validator must accept both plain and linked formats.
    """

    @pytest.mark.parametrize(
        "refs_line",
        [
            pytest.param(
                "Refs: [#31](https://github.com/org/repo/issues/31)",
                id="single_linked_issue",
            ),
            pytest.param(
                "Refs: [#31](https://github.com/org/repo/issues/31), "
                "[#32](https://github.com/org/repo/issues/32)",
                id="multiple_linked_issues",
            ),
            pytest.param(
                "Refs: #10, [#31](https://github.com/org/repo/issues/31)",
                id="mixed_plain_and_linked",
            ),
            pytest.param(
                "Refs: [#31](https://github.com/org/repo/issues/31), "
                "REQ-DOC-01, RISK-H-02",
                id="linked_with_other_ref_types",
            ),
            pytest.param(
                "Refs: [#42](https://github.com/org/repo/pull/42)",
                id="pull_url",
            ),
            pytest.param(
                "Refs: [#31](https://github.com/org/repo/issues/31), "
                "[#99](https://github.com/another-org/other-repo/issues/99)",
                id="cross_repo_link",
            ),
        ],
    )
    def test_valid_linked_refs(self, refs_line):
        msg = f"feat: add feature\n\n{refs_line}\n"
        valid, err = validate_commit_message(msg)
        assert valid is True, err
        assert err is None


class TestMainWithCustomScopes:
    """Test main()'s --scopes / --require-scope wiring (behavior covered above)."""

    def _run_main(self, monkeypatch, *argv):
        monkeypatch.setattr(sys, "argv", ["validate_commit_msg.py", *argv])
        return main()

    def test_main_with_custom_scopes(self, tmp_path, monkeypatch):
        """--scopes wires a comma-split allowlist through to validation."""
        msg_file = tmp_path / "msg"
        msg_file.write_text("feat(api): add endpoint\n\nRefs: #1\n")
        assert (
            self._run_main(monkeypatch, str(msg_file), "--scopes", "api,cli,utils") == 0
        )

    def test_main_with_spaces_in_scopes(self, tmp_path, monkeypatch):
        """--scopes entries are stripped of whitespace around commas."""
        msg_file = tmp_path / "msg"
        msg_file.write_text("feat(api): add endpoint\n\nRefs: #1\n")
        assert (
            self._run_main(monkeypatch, str(msg_file), "--scopes", "api , cli , utils")
            == 0
        )

    def test_main_with_require_scope(self, tmp_path, monkeypatch):
        """--require-scope flag reaches through to validation (exit 1 sans scope)."""
        msg_file = tmp_path / "msg"
        msg_file.write_text("feat: add feature\n\nRefs: #1\n")
        assert (
            self._run_main(
                monkeypatch, str(msg_file), "--scopes", "api,cli", "--require-scope"
            )
            == 1
        )


class TestAgentFingerprints:
    """Test that commit messages containing AI agent identity fingerprints are rejected.

    Refs: #163
    """

    def test_rejects_co_authored_by_cursor(self):
        """Reject Co-authored-by trailer with Cursor agent."""
        msg = "feat: add feature\n\nRefs: #163\n\nCo-authored-by: Cursor <cursoragent@cursor.com>\n"
        valid, err = validate_commit_message(msg)
        assert valid is False
        assert (
            "agent" in err.lower()
            or "fingerprint" in err.lower()
            or "co-authored-by" in err.lower()
        )

    def test_rejects_co_authored_by_any_agent(self):
        """Reject Co-authored-by trailer regardless of agent name."""
        msg = "fix: fix bug\n\nRefs: #1\n\nCo-authored-by: Claude <claude@anthropic.com>\n"
        valid, err = validate_commit_message(msg)
        assert valid is False

    def test_rejects_cursoragent_in_body(self):
        """Reject cursoragent identifier in body."""
        msg = "feat: add feature\n\nGenerated by cursoragent@cursor.com\n\nRefs: #163\n"
        valid, err = validate_commit_message(msg)
        assert valid is False

    def test_rejects_claude_as_whole_word(self):
        """Reject 'claude' as a whole word on its own.

        The message must contain no other fingerprint (no Co-authored-by, no
        agent email) so the ``\\bclaude\\b`` pattern is the one that fires.
        """
        msg = "feat: add feature\n\nReviewed by claude before merge.\n\nRefs: #163\n"
        valid, err = validate_commit_message(msg)
        assert valid is False

    def test_valid_message_without_agent_fingerprints(self):
        """Valid messages without agent fingerprints still pass."""
        msg = "feat: add feature\n\nRefs: #163\n"
        valid, err = validate_commit_message(msg)
        assert valid is True
        assert err is None

    def test_rejects_made_with_cursor_link(self):
        """Reject 'Made with [Cursor](https://cursor.com)' branding in body."""
        msg = "feat: add feature\n\nMade with [Cursor](https://cursor.com)\n\nRefs: #163\n"
        valid, err = validate_commit_message(msg)
        assert valid is False

    def test_blocked_patterns_from_toml_rejects_openai(self):
        """When blocked_patterns from TOML is provided, reject names from blocklist (e.g. openai)."""
        from pathlib import Path

        from vig_utils.agent_blocklist import load_blocklist

        blocklist_path = (
            Path(__file__).resolve().parent.parent.parent.parent
            / ".github"
            / "agent-blocklist.toml"
        )
        if not blocklist_path.exists():
            pytest.skip("agent-blocklist.toml not in repo")
        blocklist = load_blocklist(blocklist_path)
        msg = "feat: add feature\n\nPowered by openai\n\nRefs: #163\n"
        valid, err = validate_commit_message(msg, blocked_patterns=blocklist)
        assert valid is False
        assert "openai" in err.lower() or "blocked" in err.lower()
