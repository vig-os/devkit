"""
Tests for vig_utils.validate_branch_name.

The branch-name convention used to live in four hand-kept renderings: the local
``no-commit-to-branch`` negative-lookahead regex and three ``ALLOWED`` bash
alternations in the CI ``Validate branch name`` steps. They disagreed on shape
(``release/X.Y.Z`` passed CI but not the hook). This validator is the one rule
every enforcement point calls (Refs: #1760), so these tests pin the union the
old renderings accepted:

- ``main`` always; ``dev`` only under the gitflow workflow model;
- ``<issueless-type>/<slug>`` (``chore`` plus every Refs-optional type, #1767);
- ``<type>/<issue>-<slug>`` for the issue-numbered types (DEVKIT_BRANCH_TYPES);
- ``worktree/<issue>``, ``renovate/<anything>``, ``release/X.Y.Z``.

These tests run locally (pytest); they do not require the devcontainer CLI.
"""

from __future__ import annotations

import os
import subprocess
from typing import TYPE_CHECKING

import pytest
from vig_utils.validate_branch_name import (
    DEFAULT_BRANCH_TYPES,
    DEFAULT_ISSUELESS_TYPES,
    current_branch,
    main,
    validate_branch_name,
)

if TYPE_CHECKING:
    from pathlib import Path


class TestDefaults:
    """The defaults are the stock sets nix/hooks.nix and init-workspace.sh ship."""

    def test_default_branch_types(self) -> None:
        assert DEFAULT_BRANCH_TYPES == (
            "feature",
            "bugfix",
            "hotfix",
            "release",
            "docs",
            "test",
            "refactor",
        )

    def test_default_issueless_types(self) -> None:
        assert DEFAULT_ISSUELESS_TYPES == ("chore",)


class TestValidateBranchName:
    @pytest.mark.parametrize(
        "branch",
        [
            "main",
            "dev",
            "chore/sync-main-to-dev",
            "chore/bump",
            "feature/1760-validate-branch-name",
            "bugfix/12-fix",
            "release/7-cherry-pick",
            "refactor/1-a-b-c",
            "worktree/1760",
            "renovate/actions-checkout-7.x",
            "renovate/(weird)name",
            "release/1.2.3",
            "release/10.20.30",
        ],
    )
    def test_stock_accepts(self, branch: str) -> None:
        assert validate_branch_name(branch) is None

    @pytest.mark.parametrize(
        "branch",
        [
            "master",
            "feat/1-x",  # commit type, not a branch type
            "feature/add-thing",  # missing issue number
            "feature/12",  # missing summary
            "feature/12-",  # empty summary segment
            "feature/12-Upper",  # charset
            "feature/12-a_b",  # charset
            "feature/12-a--b",  # empty segment
            "docs/readme",  # docs is issue-numbered, not issue-less
            "chore/",  # empty slug
            "chore/Bump",  # charset
            "worktree/abc",
            "worktree/12-x",
            "renovate/",
            "release/1.2",
            "release/v1.2.3",
            "release/1.2.3-rc1",
            "main2",
            "dev/1-x",
            "",
        ],
    )
    def test_stock_rejects(self, branch: str) -> None:
        error = validate_branch_name(branch)
        assert error is not None
        assert repr(branch) in error or branch in error

    def test_custom_types_replace_the_stock_set(self) -> None:
        types = ("record",)
        assert validate_branch_name("record/4-adr", types=types) is None
        assert validate_branch_name("feature/4-adr", types=types) is not None

    def test_release_semver_survives_a_set_without_release(self) -> None:
        # release/X.Y.Z is a fixed clause (release trains), not knob-driven.
        assert validate_branch_name("release/1.2.3", types=("feature",)) is None
        assert validate_branch_name("release/7-x", types=("feature",)) is not None

    def test_issueless_types_extend_the_slug_form(self) -> None:
        issueless = ("chore", "docs")
        assert validate_branch_name("docs/readme", issueless_types=issueless) is None
        # The issue-numbered form of docs still works through --types.
        assert validate_branch_name("docs/5-readme", issueless_types=issueless) is None
        assert validate_branch_name("test/flaky", issueless_types=issueless) is not None

    def test_issueless_set_is_exactly_what_is_passed(self) -> None:
        # chore is a floor the RENDERERS add; the validator takes the set as given.
        assert validate_branch_name("chore/x", issueless_types=("docs",)) is not None

    def test_trunk_rejects_dev(self) -> None:
        assert validate_branch_name("dev", workflow="trunk") is not None
        assert validate_branch_name("main", workflow="trunk") is None
        assert validate_branch_name("feature/1-x", workflow="trunk") is None

    def test_gitflow_accepts_dev(self) -> None:
        assert validate_branch_name("dev", workflow="gitflow") is None

    def test_error_names_both_conventions_and_the_docs(self) -> None:
        error = validate_branch_name(
            "nope", types=("feature", "bugfix"), issueless_types=("chore", "docs")
        )
        assert error is not None
        assert "'nope'" in error
        assert "<type>/<issue>-<summary> (types: feature,bugfix)" in error
        assert "<type>/<summary> (types: chore,docs)" in error
        assert "docs/COMMIT_MESSAGE_STANDARD.md" in error
        assert "branch-naming skill" in error

    @pytest.mark.parametrize("branch", ["feature/1-x\nmain", "main\n"])
    def test_newlines_never_sneak_through(self, branch: str) -> None:
        assert validate_branch_name(branch) is not None


def _git(repo: Path, *args: str) -> str:
    env = {
        "GIT_AUTHOR_NAME": "Test",
        "GIT_AUTHOR_EMAIL": "test@example.com",
        "GIT_COMMITTER_NAME": "Test",
        "GIT_COMMITTER_EMAIL": "test@example.com",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_SYSTEM": "/dev/null",
        "PATH": os.environ.get("PATH", ""),
    }
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


class TestCurrentBranch:
    @pytest.fixture
    def repo(self, tmp_path: Path) -> Path:
        _git(tmp_path, "init", "-q", "-b", "feature/9-x")
        _git(tmp_path, "commit", "-q", "--allow-empty", "-m", "chore: base")
        return tmp_path

    def test_reads_the_checked_out_branch(self, repo: Path) -> None:
        assert current_branch(repo) == "feature/9-x"

    def test_detached_head_is_none(self, repo: Path) -> None:
        _git(repo, "checkout", "-q", "--detach")
        assert current_branch(repo) is None

    def test_outside_a_repo_is_none(self, tmp_path: Path) -> None:
        assert current_branch(tmp_path) is None


class TestMain:
    def test_valid_branch_exits_zero(self) -> None:
        assert main(["--branch", "feature/1-x"]) == 0

    def test_invalid_branch_exits_one(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert main(["--branch", "wip/stuff"]) == 1
        assert "wip/stuff" in capsys.readouterr().err

    def test_types_are_comma_separated_and_whitespace_tolerant(self) -> None:
        argv = ["--branch", "record/1-x", "--types", " record , feature "]
        assert main(argv) == 0

    def test_empty_types_fall_back_to_the_default(self) -> None:
        assert main(["--branch", "feature/1-x", "--types", ""]) == 0

    def test_issueless_types_flag(self) -> None:
        assert main(["--branch", "ci/fix", "--issueless-types", "chore,ci"]) == 0
        assert main(["--branch", "ci/fix"]) == 1

    def test_equals_form_as_rendered_in_the_hook(self) -> None:
        argv = [
            "--branch=docs/readme",
            "--types=feature",
            "--issueless-types=chore,docs",
            "--workflow=gitflow",
        ]
        assert main(argv) == 0

    def test_workflow_trunk_rejects_dev(self) -> None:
        assert main(["--branch", "dev", "--workflow", "trunk"]) == 1
        assert main(["--branch", "dev", "--workflow", "gitflow"]) == 0

    def test_unknown_workflow_is_a_usage_error(self) -> None:
        with pytest.raises(SystemExit) as exc:
            main(["--branch", "main", "--workflow", "wibble"])
        assert exc.value.code == 2

    def test_defaults_to_the_current_branch(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _git(tmp_path, "init", "-q", "-b", "wip/stuff")
        monkeypatch.chdir(tmp_path)
        assert main([]) == 1
        _git(tmp_path, "checkout", "-q", "-b", "chore/fine")
        assert main([]) == 0

    def test_detached_head_passes_with_a_note(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        # Same as pre-commit-hooks' no-commit-to-branch: no branch, nothing to
        # check (a CI checkout of a PR merge ref is detached).
        _git(tmp_path, "init", "-q", "-b", "wip/stuff")
        _git(tmp_path, "commit", "-q", "--allow-empty", "-m", "chore: base")
        _git(tmp_path, "checkout", "-q", "--detach")
        monkeypatch.chdir(tmp_path)
        assert main([]) == 0
        assert "detached" in capsys.readouterr().err.lower()
