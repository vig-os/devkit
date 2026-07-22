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


# ── setup-labels: taxonomy parsing and local extension merge ─────────────────
#
# Harness: a stub `gh` on PATH records every invocation to $GH_STUB_LOG and
# answers `gh label list` from $GH_STUB_EXISTING (space-separated names), so
# the script's reconcile/prune loops run against a fake remote.

_CANONICAL_TAXONOMY = """\
[[labels]]
name = "bug"
description = "Something isn't working"
color = "d73a4a"

[[labels]]
name = "feature"
description = "New functionality"
color = "a2eeef"
"""

_LOCAL_TAXONOMY = """\
[[labels]]
name = "drift"
description = "Configuration drift detected"
color = "5319e7"
"""

_LOCAL_TAXONOMY_COLLIDING = """\
[[labels]]
name = "drift"
description = "Configuration drift detected"
color = "5319e7"

[[labels]]
name = "bug"
description = "Local bug override"
color = "000000"
"""

_GH_STUB = """\
#!/usr/bin/env bash
printf '%s\\n' "$*" >> "$GH_STUB_LOG"
if [[ "${1:-}" == "label" && "${2:-}" == "list" ]]; then
    for name in ${GH_STUB_EXISTING:-}; do
        printf '%s\\n' "$name"
    done
fi
"""


def _run_setup_labels(
    tmp_path: Path,
    *,
    canonical: str = _CANONICAL_TAXONOMY,
    local: str | None = None,
    existing: str = "",
    args: list[str] | None = None,
) -> tuple[subprocess.CompletedProcess[str], list[str]]:
    """Run setup-labels against a temp repo root with a stubbed gh CLI."""
    stub_bin = tmp_path / "bin"
    stub_bin.mkdir(exist_ok=True)
    gh_stub = stub_bin / "gh"
    gh_stub.write_text(_GH_STUB)
    gh_stub.chmod(0o755)

    repo_root = tmp_path / "repo"
    (repo_root / ".github").mkdir(parents=True, exist_ok=True)
    (repo_root / ".github" / "label-taxonomy.toml").write_text(canonical)
    if local is not None:
        (repo_root / ".github" / "label-taxonomy.local.toml").write_text(local)

    gh_log = tmp_path / "gh.log"
    gh_log.write_text("")

    env = dict(os.environ)
    env["PATH"] = f"{stub_bin}{os.pathsep}{env['PATH']}"
    env["VIG_UTILS_REPO_ROOT"] = str(repo_root)
    env["GH_STUB_LOG"] = str(gh_log)
    env["GH_STUB_EXISTING"] = existing

    result = _run(["setup-labels", *(args or [])], env=env)
    return result, gh_log.read_text().splitlines()


def test_setup_labels_reconciles_extension_labels(tmp_path: Path) -> None:
    result, gh_log = _run_setup_labels(tmp_path, local=_LOCAL_TAXONOMY)

    assert result.returncode == 0, result.stderr
    assert "label-taxonomy.local.toml" in result.stdout
    assert any(line.startswith("label create bug ") for line in gh_log)
    assert any(line.startswith("label create drift ") for line in gh_log)


def test_setup_labels_prune_spares_extension_labels(tmp_path: Path) -> None:
    result, gh_log = _run_setup_labels(
        tmp_path,
        local=_LOCAL_TAXONOMY,
        existing="bug feature drift stale",
        args=["--prune"],
    )

    assert result.returncode == 0, result.stderr
    assert any(line.startswith("label delete stale ") for line in gh_log)
    assert not any(line.startswith("label delete drift ") for line in gh_log)
    assert not any(line.startswith("label delete bug ") for line in gh_log)


def test_setup_labels_local_wins_on_name_collision(tmp_path: Path) -> None:
    result, gh_log = _run_setup_labels(
        tmp_path,
        local=_LOCAL_TAXONOMY_COLLIDING,
        existing="bug",
    )

    assert result.returncode == 0, result.stderr
    bug_edits = [line for line in gh_log if line.startswith("label edit bug ")]
    assert len(bug_edits) == 1
    assert "Local bug override" in bug_edits[0]
    assert "000000" in bug_edits[0]
    assert not any(line.startswith("label create bug ") for line in gh_log)


def test_setup_labels_without_extension_behaves_as_before(tmp_path: Path) -> None:
    result, gh_log = _run_setup_labels(tmp_path, existing="bug")

    assert result.returncode == 0, result.stderr
    assert "Taxonomy: 2 labels defined in label-taxonomy.toml" in result.stdout
    assert "local" not in result.stdout.lower()
    assert any(line.startswith("label edit bug ") for line in gh_log)
    assert any(line.startswith("label create feature ") for line in gh_log)
    mutations = [line for line in gh_log if not line.startswith("label list")]
    assert len(mutations) == 2


def test_setup_labels_dry_run_previews_extension_labels(tmp_path: Path) -> None:
    result, gh_log = _run_setup_labels(
        tmp_path,
        local=_LOCAL_TAXONOMY_COLLIDING,
        existing="bug",
        args=["--dry-run"],
    )

    assert result.returncode == 0, result.stderr
    assert "[DRY-RUN]  create  drift" in result.stdout
    assert result.stdout.count("[DRY-RUN]  update  bug") == 1
    mutations = [line for line in gh_log if not line.startswith("label list")]
    assert mutations == []


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
