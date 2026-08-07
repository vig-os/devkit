"""Workflow-shape tests: the CI ``Test Summary`` gate must not pass on cancel.

Issue #1371: ``Test Summary`` (the ``summary`` job in ``.github/workflows/ci.yml``)
is the only required status check on ``dev``. It aggregates its ``needs:`` jobs
but originally set ``FAILED=true`` only on ``result == "failure"``, so a
**cancelled** job — job timeout, concurrency cancel, runner eviction, a manual
"Cancel workflow" — left the required check green and a PR whose CI never
finished was mergeable.

``skipped`` stays tolerated on purpose: ``workflow_dispatch`` takes a
``test-suite`` input (``all``/``image``/``integration``/``project``) that every
job is gated on, and ``commit-checks``/``dependency-review`` are pull-request
only, so a skipped job is a legitimate outcome rather than a missing result.

Refs: #1371
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

# Repository root (tests/ -> repo root).
REPO_ROOT = Path(__file__).resolve().parent.parent

CI_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"


def _summary_job() -> dict:
    workflow = yaml.safe_load(CI_WORKFLOW.read_text(encoding="utf-8"))
    return workflow["jobs"]["summary"]


def _summary_run() -> str:
    return _summary_job()["steps"][0]["run"]


def _needed_jobs() -> list[str]:
    return list(_summary_job()["needs"])


def test_summary_is_the_required_check_over_every_test_job() -> None:
    """The aggregate still fans in over the full job set it is meant to gate."""
    assert _summary_job()["name"] == "Test Summary"
    assert set(_needed_jobs()) == {
        "build-image",
        "test-image",
        "test-integration",
        "project-checks",
        "commit-checks",
        "python-security",
        "security-scan",
        "dependency-review",
    }


@pytest.mark.parametrize("job", _needed_jobs())
def test_summary_fails_on_failure(job: str) -> None:
    """Every needed job trips the gate when it fails."""
    assert f'needs.{job}.result }}}}" = "failure"' in _summary_run(), (
        f"summary must fail when {job} result is failure"
    )


@pytest.mark.parametrize("job", _needed_jobs())
def test_summary_fails_on_cancelled(job: str) -> None:
    """Every needed job trips the gate when it is cancelled (#1371)."""
    assert f'needs.{job}.result }}}}" = "cancelled"' in _summary_run(), (
        f"summary must fail when {job} result is cancelled — a cancelled job is "
        "an unfinished check, not a passing one"
    )


@pytest.mark.parametrize("job", _needed_jobs())
def test_summary_tolerates_skipped(job: str) -> None:
    """A skipped job is legitimate (dispatch subset, PR-only jobs) — never fatal."""
    assert f'needs.{job}.result }}}}" = "skipped"' not in _summary_run(), (
        f"{job} skipped must not trip the summary"
    )
