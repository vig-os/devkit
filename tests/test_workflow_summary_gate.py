"""Workflow-shape tests: the CI summary gates must not pass on cancel.

Issue #1371: the summary job is the only required status check on the default
merge target (``dev`` here; ``main`` for trunk consumers). It aggregates its
``needs:`` jobs but originally set ``FAILED=true`` only on
``result == "failure"``, so a **cancelled** job — job timeout, concurrency
cancel, runner eviction, a manual "Cancel workflow" — left the required check
green and a PR whose CI never finished was mergeable.

Issue #1414: the scaffolded consumer copy shipped the cancelled leg only for
``resolve-toolchain``; every needed job in *both* copies must trip the gate on
cancel, so the doctrine is pinned parametrically over the two files.

``skipped`` stays tolerated on purpose: dispatch subsets and PR-only jobs
(``commit-checks``/``dependency-review``, and the scaffold's push-skipped
``scaffold-drift``) make a skipped job a legitimate outcome rather than a
missing result.

Refs: #1371, #1414
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.workflow_scaffold import WORKSPACE, load_workflow, run_text_of_job

# Repository root (tests/ -> repo root).
REPO_ROOT = Path(__file__).resolve().parent.parent

# copy id -> (workflow path, display name, full needs set of the summary job)
SUMMARY_COPIES: dict[str, tuple[Path, str, set[str]]] = {
    "devkit": (
        REPO_ROOT / ".github" / "workflows" / "ci.yml",
        "Test Summary",
        {
            "build-image",
            "test-image",
            "test-integration",
            "project-checks",
            "commit-checks",
            "python-security",
            "security-scan",
            "dependency-review",
        },
    ),
    "scaffold": (
        WORKSPACE / ".github" / "workflows" / "ci.yml",
        "CI Summary",
        {
            "resolve-toolchain",
            "lint",
            "test",
            "commit-checks",
            "scaffold-drift",
            "dependency-review",
        },
    ),
}


def _summary_job(copy: str) -> dict:
    path, _, _ = SUMMARY_COPIES[copy]
    return load_workflow(path)["jobs"]["summary"]


def _summary_run(copy: str) -> str:
    return run_text_of_job(_summary_job(copy))


# (copy, job) pairs for every needed job of every copy, with stable test ids.
_COPY_JOB_PAIRS = [
    pytest.param(copy, job, id=f"{copy}-{job}")
    for copy, (_, _, needed) in SUMMARY_COPIES.items()
    for job in sorted(needed)
]


@pytest.mark.parametrize("copy", sorted(SUMMARY_COPIES))
def test_summary_is_the_required_check_over_every_job(copy: str) -> None:
    """The aggregate still fans in over the full job set it is meant to gate."""
    _, name, needed = SUMMARY_COPIES[copy]
    job = _summary_job(copy)
    assert job["name"] == name
    assert set(job["needs"]) == needed


@pytest.mark.parametrize(("copy", "job"), _COPY_JOB_PAIRS)
def test_summary_fails_on_failure(copy: str, job: str) -> None:
    """Every needed job trips the gate when it fails."""
    assert f'needs.{job}.result }}}}" = "failure"' in _summary_run(copy), (
        f"{copy} summary must fail when {job} result is failure"
    )


@pytest.mark.parametrize(("copy", "job"), _COPY_JOB_PAIRS)
def test_summary_fails_on_cancelled(copy: str, job: str) -> None:
    """Every needed job trips the gate when it is cancelled (#1371, #1414)."""
    assert f'needs.{job}.result }}}}" = "cancelled"' in _summary_run(copy), (
        f"{copy} summary must fail when {job} result is cancelled — a "
        "cancelled job is an unfinished check, not a passing one"
    )


@pytest.mark.parametrize(("copy", "job"), _COPY_JOB_PAIRS)
def test_summary_tolerates_skipped(copy: str, job: str) -> None:
    """A skipped job is legitimate (dispatch subset, PR-only jobs) — never fatal."""
    assert f'needs.{job}.result }}}}" = "skipped"' not in _summary_run(copy), (
        f"{copy}: {job} skipped must not trip the summary"
    )
