"""
Tests for vig_utils.validate_commit_range.

The commit-msg hook only guards a healthy laptop; CI must validate the commits
a pull request actually carries. These tests pin the two rules that make that
safe to switch on (Refs: #1019):

1. merge commits are skipped (their subject is the PR title, checked separately);
2. bot-authored commits are skipped -- Renovate/Dependabot emit
   ``build(pip): ...`` / ``ci(actions): ...`` with no ``Refs:`` line, so
   enforcing the human rule on them would redden every dependency PR.

These tests run locally (pytest); they do not require the devcontainer CLI.
"""

from __future__ import annotations

import os
import subprocess
from typing import TYPE_CHECKING

import pytest
from vig_utils.validate_commit_range import (
    Commit,
    is_bot_author,
    main,
    parse_git_log,
    read_commits,
    validate_commits,
    validate_title,
)

if TYPE_CHECKING:
    from pathlib import Path


def _commit(
    sha: str = "a" * 40,
    author: str = "Carlos Vigo",
    message: str = "feat(ci): add a lane\n\nRefs: #1",
    parents: tuple[str, ...] = ("b" * 40,),
) -> Commit:
    return Commit(sha=sha, author=author, message=message, parents=parents)


class TestIsBotAuthor:
    """Bot detection is a ``[bot]`` suffix rule, not a hardcoded roster."""

    @pytest.mark.parametrize(
        "author",
        [
            "renovate[bot]",
            "dependabot[bot]",
            "commit-action-bot[bot]",
            "github-actions[bot]",
            "  renovate[bot]  ",
        ],
    )
    def test_known_bots_are_bots(self, author: str) -> None:
        assert is_bot_author(author) is True

    @pytest.mark.parametrize("author", ["Carlos Vigo", "robot", "bot", "Botticelli"])
    def test_humans_are_not_bots(self, author: str) -> None:
        assert is_bot_author(author) is False


class TestValidateCommits:
    def test_empty_range_is_valid(self) -> None:
        assert validate_commits([]) == []

    def test_valid_commit_passes(self) -> None:
        assert validate_commits([_commit()]) == []

    def test_unknown_type_is_reported(self) -> None:
        bad = _commit(sha="c" * 40, message="wibble(ci): nope\n\nRefs: #1")
        failures = validate_commits([bad])
        assert len(failures) == 1
        commit, error = failures[0]
        assert commit.sha == "c" * 40
        assert "wibble" in error or "type" in error.lower()

    def test_human_commit_without_refs_is_reported(self) -> None:
        bad = _commit(message="feat(ci): add a lane")
        assert len(validate_commits([bad])) == 1

    def test_chore_without_refs_is_allowed(self) -> None:
        assert validate_commits([_commit(message="chore(nix): bump nixpkgs")]) == []

    def test_freeform_scope_is_allowed(self) -> None:
        """The scope allowlist is gone; #1019's rejected scopes must pass."""
        commits = [
            _commit(message="fix(workspace): point flake stub at devkit\n\nRefs: #1"),
            _commit(message="chore(nix): bump nixpkgs-unstable"),
            _commit(message="ci(gh-issues): resync labels\n\nRefs: #2"),
        ]
        assert validate_commits(commits) == []

    def test_merge_commit_is_skipped(self) -> None:
        """A merge commit's subject is the PR title -- validated via --title."""
        merge = _commit(
            message="Merge pull request #7 from vig-os/x",
            parents=("b" * 40, "c" * 40),
        )
        assert validate_commits([merge]) == []

    @pytest.mark.parametrize(
        "message",
        [
            "build(pip): lock file maintenance",
            "ci(actions): update cachix/install-nix-action action to v31.10.7",
            "docs(changelog): add unreleased entry for renovate PR 985",
        ],
    )
    def test_bot_commit_without_refs_is_skipped(self, message: str) -> None:
        """The exact shapes Renovate/Dependabot/commit-action-bot emit today."""
        bot = _commit(author="renovate[bot]", message=message)
        assert validate_commits([bot]) == []

    def test_bot_exemption_does_not_leak_to_humans(self) -> None:
        """The same message from a human is still a failure."""
        human = _commit(
            author="Carlos Vigo", message="build(pip): lock file maintenance"
        )
        assert len(validate_commits([human])) == 1

    def test_reports_every_failing_commit(self) -> None:
        failures = validate_commits(
            [
                _commit(sha="1" * 40, message="feat(ci): good\n\nRefs: #1"),
                _commit(sha="2" * 40, message="nope: bad type\n\nRefs: #1"),
                _commit(sha="3" * 40, message="feat(ci): missing refs"),
            ]
        )
        assert {c.sha for c, _ in failures} == {"2" * 40, "3" * 40}


class TestValidateTitle:
    """PR titles are subject-only, so the Refs rule cannot apply to them.

    They still land in history verbatim: PRs merge --no-ff and the merge
    commit's subject is the PR title.
    """

    @pytest.mark.parametrize(
        "title",
        [
            "ci: re-enable actionlint shellcheck integration",
            "fix(workspace): point scaffolded flake stub at github:vig-os/devkit",
            "feat(ci)!: drop the legacy lane",
        ],
    )
    def test_wellformed_subject_only_title_passes(self, title: str) -> None:
        assert validate_title(title) is None

    @pytest.mark.parametrize(
        "title",
        ["Update stuff", "WIP", "fix bug", "Fix(ci): capitalised type"],
    )
    def test_malformed_title_is_reported(self, title: str) -> None:
        assert validate_title(title) is not None

    def test_title_does_not_require_refs(self) -> None:
        assert validate_title("feat(ci): add a lane") is None

    def test_refs_requiring_type_is_exempt_end_to_end(self) -> None:
        """A Refs-requiring type is safe as a title (#1074).

        ``docs`` is not in DEFAULT_REFS_OPTIONAL_TYPES, yet a bare ``docs:``
        title must pass: the --no-ff merge commit it becomes on dev is skipped
        by validate_commits (``is_merge``), so it never faces the Refs rule.
        The same subject as a plain human commit still fails -- the exemption
        reaches merge commits only.
        """
        title = "docs: update readme"
        assert validate_title(title) is None
        merge = _commit(message=title, parents=("b" * 40, "c" * 40))
        assert validate_commits([merge]) == []
        assert len(validate_commits([_commit(message=title)])) == 1


class TestParseGitLog:
    """The %H/%an/%P/%B record parser feeding validate_commits from CI."""

    def test_parses_records(self) -> None:
        sep, rec = "\x1f", "\x1e"
        raw = (
            f"{'a' * 40}{sep}Carlos Vigo{sep}{'b' * 40}{sep}"
            f"feat(ci): one\n\nRefs: #1\n{rec}"
            f"{'c' * 40}{sep}renovate[bot]{sep}{'d' * 40} {'e' * 40}{sep}"
            f"build(pip): two\n{rec}"
        )
        commits = parse_git_log(raw)
        assert [c.sha for c in commits] == ["a" * 40, "c" * 40]
        assert commits[0].author == "Carlos Vigo"
        assert commits[0].parents == ("b" * 40,)
        assert commits[0].message.strip() == "feat(ci): one\n\nRefs: #1"
        assert commits[1].is_merge is True

    def test_empty_output_is_empty_list(self) -> None:
        assert parse_git_log("") == []
        assert parse_git_log("\n") == []


class TestReadCommits:
    """``--exclude-reachable`` drops history already gated on the trunk branch.

    On a release PR (``release/X.Y.Z`` -> ``main``) the ``base..head`` span
    reaches back through pre-migration commits that predate the commit gate but
    were already merged into (or grandfathered onto) the trunk branch. Excluding
    commits reachable from the trunk stops the first release train re-litigating
    them, while staying a no-op on a dev PR whose base *is* the trunk (#1149).
    """

    @staticmethod
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

    def _commit(self, repo: Path, message: str) -> str:
        self._git(repo, "commit", "--allow-empty", "-m", message)
        return self._git(repo, "rev-parse", "HEAD")

    @pytest.fixture
    def repo(self, tmp_path: Path) -> Path:
        """Build main(base) -> dev(grandfathered) -> release(head) topology."""
        self._git(tmp_path, "init", "-q", "-b", "main")
        self.base = self._commit(tmp_path, "chore: base commit")
        # A non-compliant commit that was grandfathered onto the trunk branch.
        self._git(tmp_path, "checkout", "-q", "-b", "dev")
        self.grandfathered = self._commit(tmp_path, "broken commit with no type")
        # The release branch cuts from dev, then adds one compliant commit.
        self._git(tmp_path, "checkout", "-q", "-b", "release/1.0.0")
        self.head = self._commit(tmp_path, "feat(x): new thing\n\nRefs: #2")
        return tmp_path

    def test_without_exclude_returns_trunk_history(self, repo: Path) -> None:
        commits = read_commits(self.base, self.head, repo=repo)
        subjects = {c.subject for c in commits}
        assert "broken commit with no type" in subjects
        assert "feat(x): new thing" in subjects

    def test_exclude_reachable_drops_trunk_history(self, repo: Path) -> None:
        commits = read_commits(self.base, self.head, repo=repo, exclude=["dev"])
        subjects = {c.subject for c in commits}
        assert "broken commit with no type" not in subjects
        assert "feat(x): new thing" in subjects


class TestMain:
    def test_exits_zero_on_clean_title_only(self) -> None:
        assert main(["--title", "feat(ci): add a lane"]) == 0

    def test_exits_one_on_bad_title(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert main(["--title", "Update stuff"]) == 1
        assert "Update stuff" in capsys.readouterr().err
