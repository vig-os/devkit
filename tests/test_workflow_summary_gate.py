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

Issue #1692: the ``needs:`` set is asserted **exactly**, not as a subset. With
``if: always()`` a job left out of ``needs:`` is not merely unchecked — it is
invisible to the aggregate, so its failure cannot block the merge. That is why
splitting ``project-checks`` into the four ``project-*`` lanes had to update
this set rather than relax the assertion.

The same issue adds the lanes' other silent-pass hazard: a lane observed by the
aggregate but running *nothing* is green. The composite refuses an unknown
``suite`` at runtime; here the static half is pinned — each lane passes its own
block, no two lanes pass the same one, and no block the composite implements is
left without a lane to run it.

Refs: #1371, #1414, #1692
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from tests.workflow_scaffold import WORKSPACE, load_workflow, run_text_of_job

# Repository root (tests/ -> repo root).
REPO_ROOT = Path(__file__).resolve().parent.parent
DEVKIT_CI = REPO_ROOT / ".github" / "workflows" / "ci.yml"
TEST_PROJECT = REPO_ROOT / ".github" / "actions" / "test-project" / "action.yml"

# The four project lanes (#1692) -> the `suite` each one selects. Pinned in both
# directions below: every lane runs a block, and every block the composite
# implements is run by a lane.
PROJECT_LANES = {
    "project-lint": "lint",
    "project-tests": "pytest",
    "project-bats": "bats",
    "project-flake": "flake",
}

# copy id -> (workflow path, display name, full needs set of the summary job)
SUMMARY_COPIES: dict[str, tuple[Path, str, set[str]]] = {
    "devkit": (
        REPO_ROOT / ".github" / "workflows" / "ci.yml",
        "Test Summary",
        {
            "build-image",
            "test-image",
            "test-integration",
            "project-lint",
            "project-tests",
            "project-bats",
            "project-flake",
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


def _lane_suite(job_name: str) -> str:
    """The `suite` the named lane passes to the test-project composite."""
    job = load_workflow(DEVKIT_CI)["jobs"][job_name]
    calls = [
        step for step in job["steps"] if "test-project" in str(step.get("uses", ""))
    ]
    assert len(calls) == 1, f"{job_name} must call the test-project composite once"
    return calls[0]["with"]["suite"]


@pytest.mark.parametrize(("lane", "suite"), sorted(PROJECT_LANES.items()))
def test_each_project_lane_runs_its_own_block(lane: str, suite: str) -> None:
    """Each lane selects the block it is named for (#1692)."""
    assert _lane_suite(lane) == suite


def test_no_two_project_lanes_run_the_same_block() -> None:
    """Distinct suites: a duplicated value would leave a block unrun, and green."""
    suites = [_lane_suite(lane) for lane in PROJECT_LANES]
    assert len(set(suites)) == len(suites), f"duplicate lane suites: {suites}"


def test_every_composite_block_has_a_lane() -> None:
    """No block is implemented in the composite without a lane running it.

    The composite guards each block on ``inputs.suite == '<block>'``; ``all`` is
    the run-everything value no lane passes. Any other value it knows about must
    be some lane's suite, or that block runs in no CI job at all (the #1413
    class of gap, one level up).
    """
    guarded = set(
        re.findall(
            r"inputs\.suite == '([a-z]+)'",
            TEST_PROJECT.read_text(encoding="utf-8"),
        )
    )
    assert guarded - {"all"} == set(PROJECT_LANES.values())
