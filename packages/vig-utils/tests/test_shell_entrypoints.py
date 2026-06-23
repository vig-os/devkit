"""Tests for packaged shell entrypoints exposed by vig-utils."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]


def _run(
    args: list[str],
    *,
    input_text: str | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        input=input_text,
        text=True,
        capture_output=True,
        check=False,
        cwd=REPO_ROOT,
        env=env,
    )


def test_check_skill_names_command_available() -> None:
    assert shutil.which("check-skill-names")


def test_check_skill_names_accepts_valid_names(tmp_path: Path) -> None:
    (tmp_path / "ci_check").mkdir()
    (tmp_path / "pr_post-merge").mkdir()
    (tmp_path / "worktree_solve-and-pr").mkdir()

    result = _run(["check-skill-names", str(tmp_path)])

    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    "bad_name",
    ["ci:check", "ci.check", "CI_Check", "ci check"],
)
def test_check_skill_names_rejects_invalid_name(tmp_path: Path, bad_name: str) -> None:
    (tmp_path / bad_name).mkdir()

    result = _run(["check-skill-names", str(tmp_path)])

    assert result.returncode != 0
    assert bad_name in result.stderr


def test_check_skill_names_reports_all_invalid_names(tmp_path: Path) -> None:
    (tmp_path / "ci:check").mkdir()
    (tmp_path / "code_tdd").mkdir()
    (tmp_path / "Design:Plan").mkdir()

    result = _run(["check-skill-names", str(tmp_path)])

    assert result.returncode != 0
    assert "ci:check" in result.stderr
    assert "Design:Plan" in result.stderr


def test_check_skill_names_passes_for_repo_skills_dir() -> None:
    result = _run(["check-skill-names", ".claude/skills"])

    assert result.returncode == 0, result.stderr


def test_check_skill_names_canary_invalid_repo_skill_is_detected() -> None:
    canary_dir = REPO_ROOT / ".claude/skills/bad:canary"
    canary_dir.mkdir(parents=True)
    try:
        result = _run(["check-skill-names", ".claude/skills"])
    finally:
        canary_dir.rmdir()

    assert result.returncode != 0
    assert "bad:canary" in result.stderr


def test_resolve_branch_extracts_first_tab_separated_field() -> None:
    result = _run(
        ["resolve-branch"],
        input_text=(
            "feature/103-first\thttps://example.com\n"
            "bugfix/99-second\thttps://example.com\n"
        ),
    )

    assert result.returncode == 0
    assert result.stdout.strip() == "feature/103-first"


def test_resolve_branch_handles_input_without_tabs() -> None:
    result = _run(["resolve-branch"], input_text="feature/103-enhancements\n")

    assert result.returncode == 0
    assert result.stdout.strip() == "feature/103-enhancements"


def test_resolve_branch_returns_empty_for_empty_input() -> None:
    result = _run(["resolve-branch"], input_text="")

    assert result.returncode == 0
    assert result.stdout == ""


def test_setup_labels_command_available() -> None:
    assert shutil.which("setup-labels")


def test_derive_branch_summary_outputs_summary_when_cmd_succeeds() -> None:
    env = dict(os.environ)
    env["BRANCH_SUMMARY_CMD"] = "echo fix-login-bug"
    result = _run(["derive-branch-summary", "Fix login bug"], env=env)

    assert result.returncode == 0
    assert result.stdout.strip() == "fix-login-bug"


def test_derive_branch_summary_errors_when_cmd_fails() -> None:
    env = dict(os.environ)
    env["BRANCH_SUMMARY_CMD"] = "false"
    result = _run(["derive-branch-summary", "Some title"], env=env)

    assert result.returncode != 0
    assert "[ERROR]" in result.stderr
    assert "Create one manually" in result.stderr
    assert "gh issue develop" in result.stderr


def test_derive_branch_summary_times_out_when_cmd_hangs() -> None:
    env = dict(os.environ)
    env["BRANCH_SUMMARY_CMD"] = "sleep 5"
    env["DERIVE_BRANCH_TIMEOUT"] = "2"
    result = _run(["derive-branch-summary", "Some title"], env=env)

    assert result.returncode != 0
    assert "[ERROR]" in result.stderr
    assert "Failed to derive branch summary" in result.stderr


def test_derive_branch_summary_accepts_optional_model_tier_arg() -> None:
    env = dict(os.environ)
    env["BRANCH_SUMMARY_CMD"] = "echo retry-summary"
    result = _run(
        ["derive-branch-summary", "Some title", "/dev/null", "standard"],
        env=env,
    )

    assert result.returncode == 0
    assert result.stdout.strip() == "retry-summary"


@pytest.mark.parametrize("flag", ["-h", "--help"])
def test_derive_branch_summary_help_exits_zero(flag: str) -> None:
    result = _run(["derive-branch-summary", flag])

    assert result.returncode == 0, result.stderr
    assert "Usage" in result.stdout
