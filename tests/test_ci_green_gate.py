"""Behavior tests: the release-PR CI-green gate, executed (#1522).

Issue #1516: during the 1.10.0 train a release PR was closed/reopened to fire a
fresh ``pull_request`` event (a rerun replays the frozen payload and could not
pick up the corrected PR body). The new run went 13/13 green, but the
superseded run's two FAILURE check runs stayed attached to the same head SHA.
The gate counted **every** FAILURE entry in ``statusCheckRollup``, so it refused
a branch ``gh pr checks`` — which keeps only the latest run per name — reported
green. The operator had to ``gh run delete`` the superseded run to proceed.

Issue #1522 makes every copy of the gate group the rollup by check name and
evaluate only the most recent run of each. That is behavior, not shape: a
string assertion cannot tell a correct dedup filter from a plausible one, and
picking the wrong recency key (``completedAt``, null while a rerun is in
flight) would silently let a stale FAILURE win again. So these tests EXTRACT
the gate's real bash and EXECUTE it against fixture rollups — the idiom
``tests/bats/release-mirror-fold.bats`` uses for the mirror fold.

All six gate sites are covered: the two named in the issue (devkit's
``release.yml``, the scaffold's ``release-core.yml``) plus the four promote
gates, which carry the identical logic and the identical hazard.

Refs: #1516, #1522
"""

from __future__ import annotations

from itertools import permutations
from typing import TYPE_CHECKING

import pytest

from tests.workflow_scaffold import (
    REPO_ROOT,
    WORKFLOWS,
    extract_ci_gate,
    load_workflow,
    run_ci_gate,
    step_by_name,
    steps_of_job,
)

if TYPE_CHECKING:
    from pathlib import Path

DEVKIT_WORKFLOWS = REPO_ROOT / ".github" / "workflows"

# site id -> (workflow file, job, step-name fragment carrying the gate)
GATE_SITES: dict[str, tuple[Path, str, str]] = {
    "release/devkit": (
        DEVKIT_WORKFLOWS / "release.yml",
        "validate",
        "Find and verify PR",
    ),
    "release-core/scaffold": (
        WORKFLOWS / "release-core.yml",
        "validate",
        "Find and verify PR",
    ),
    "promote/devkit/validate": (
        DEVKIT_WORKFLOWS / "promote-release.yml",
        "validate",
        "Find and verify release PR",
    ),
    "promote/devkit/merge": (
        DEVKIT_WORKFLOWS / "promote-release.yml",
        "merge",
        "Find and verify release PR",
    ),
    "promote/scaffold/validate": (
        WORKFLOWS / "promote-release.yml",
        "validate",
        "Find and verify release PR",
    ),
    "promote/scaffold/merge": (
        WORKFLOWS / "promote-release.yml",
        "merge",
        "Find and verify release PR",
    ),
}
SITES = list(GATE_SITES)

T1 = "2026-08-14T10:00:00Z"
T2 = "2026-08-14T11:00:00Z"


def _gate(site: str) -> str:
    path, job, step_name = GATE_SITES[site]
    step = step_by_name(steps_of_job(load_workflow(path), job), step_name)
    return extract_ci_gate(step["run"])


def check_run(name: str, conclusion: str | None, started: str) -> dict:
    """A CheckRun rollup node. ``conclusion=None`` means still in progress."""
    return {
        "__typename": "CheckRun",
        "name": name,
        "status": "IN_PROGRESS" if conclusion is None else "COMPLETED",
        "conclusion": conclusion,
        "startedAt": started,
        # Null while the run is in flight — the trap a ``completedAt`` recency
        # key would fall into.
        "completedAt": None if conclusion is None else started,
    }


def status_context(context: str, state: str, created: str) -> dict:
    """A StatusContext rollup node: no ``name``, no ``conclusion``, no run history."""
    return {
        "__typename": "StatusContext",
        "context": context,
        "state": state,
        "createdAt": created,
        "targetUrl": None,
    }


def _output(proc: object) -> str:
    return proc.stdout + proc.stderr  # type: ignore[attr-defined]


# The #1516 rollup: a superseded FAILURE and the operative SUCCESS of the same
# check name on one head SHA, alongside a second green check.
SUPERSEDED_FAILURE = [
    check_run("Project Checks", "FAILURE", T1),
    check_run("Project Checks", "SUCCESS", T2),
    check_run("Test Summary", "SUCCESS", T2),
]

# The inverse: the newest run is the failing one. Dedup must not simply prefer
# a SUCCESS over a FAILURE.
LATEST_FAILURE = [
    check_run("Project Checks", "SUCCESS", T1),
    check_run("Project Checks", "FAILURE", T2),
    check_run("Test Summary", "SUCCESS", T2),
]


@pytest.mark.parametrize("site", SITES)
def test_superseded_failure_does_not_block(site: str) -> None:
    """#1516: a stale FAILURE replaced by a newer SUCCESS must let the gate pass."""
    proc = run_ci_gate(_gate(site), SUPERSEDED_FAILURE)
    assert proc.returncode == 0, _output(proc)


@pytest.mark.parametrize("site", SITES)
def test_latest_run_failure_still_blocks(site: str) -> None:
    """An older SUCCESS superseded by a FAILURE keeps the gate shut."""
    proc = run_ci_gate(_gate(site), LATEST_FAILURE)
    assert proc.returncode != 0
    assert "failed CI checks" in _output(proc)


@pytest.mark.parametrize("site", SITES)
def test_in_progress_rerun_counts_as_pending_not_failed(site: str) -> None:
    """A rerun in flight over an older FAILURE waits; it is never a failure.

    ``release-core.yml`` gates on failures only, so there the gate passes —
    what matters everywhere is that the superseded FAILURE stops counting.
    """
    gate = _gate(site)
    proc = run_ci_gate(
        gate,
        [
            check_run("Project Checks", "FAILURE", T1),
            check_run("Project Checks", None, T2),
            check_run("Test Summary", "SUCCESS", T2),
        ],
    )
    assert "failed CI checks" not in _output(proc)
    if "CI_PENDING" in gate:
        assert proc.returncode != 0
        assert "in progress" in _output(proc)
    else:
        assert proc.returncode == 0, _output(proc)


@pytest.mark.parametrize("site", SITES)
def test_failure_on_a_distinct_name_still_blocks(site: str) -> None:
    """Dedup is per name: a red check A is not excused by a green check B."""
    proc = run_ci_gate(
        _gate(site),
        [
            check_run("Project Checks", "FAILURE", T2),
            check_run("Test Summary", "SUCCESS", T2),
        ],
    )
    assert proc.returncode != 0
    assert "failed CI checks" in _output(proc)


@pytest.mark.parametrize("site", SITES)
def test_status_contexts_keep_their_current_treatment(site: str) -> None:
    """A StatusContext has no ``conclusion``, so it counts as pending — as before.

    Dedup must not quietly reclassify commit statuses: this pins the pre-#1522
    behavior rather than blessing it.
    """
    gate = _gate(site)
    proc = run_ci_gate(
        gate,
        [
            status_context("ci/legacy", "SUCCESS", T1),
            check_run("Test Summary", "SUCCESS", T1),
        ],
    )
    assert "failed CI checks" not in _output(proc)
    if "CI_PENDING" in gate:
        assert proc.returncode != 0
        assert "in progress" in _output(proc)
    else:
        assert proc.returncode == 0, _output(proc)


@pytest.mark.parametrize("site", SITES)
def test_distinct_status_contexts_are_not_collapsed(site: str) -> None:
    """Two commit statuses stay two entries: they key on ``context``, not ``name``.

    Grouping on ``name`` alone would fold every StatusContext (whose ``name``
    is null) into a single bucket and drop entries from the counts.
    """
    gate = _gate(site)
    proc = run_ci_gate(
        gate,
        [
            status_context("ci/one", "SUCCESS", T1),
            status_context("ci/two", "SUCCESS", T2),
            check_run("Test Summary", "SUCCESS", T2),
        ],
    )
    if "$CI_PENDING checks" in gate:  # only this copy prints the count
        assert "has 2 checks still in progress" in _output(proc)
    elif "CI_PENDING" in gate:
        assert proc.returncode != 0
    else:
        assert proc.returncode == 0, _output(proc)


@pytest.mark.parametrize("site", SITES)
def test_recency_comes_from_timestamps_not_array_order(site: str) -> None:
    """Every ordering of the same rollup yields the same verdict."""
    gate = _gate(site)
    for rollup in permutations(SUPERSEDED_FAILURE):
        proc = run_ci_gate(gate, list(rollup))
        assert proc.returncode == 0, _output(proc)
    proc = run_ci_gate(gate, list(reversed(LATEST_FAILURE)))
    assert proc.returncode != 0
    assert "failed CI checks" in _output(proc)
