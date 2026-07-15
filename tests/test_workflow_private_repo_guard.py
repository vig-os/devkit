"""Workflow-shape tests: security-scan jobs must skip on private repositories.

Issue #1039: the scaffold ships ``codeql.yml`` and ``scorecard.yml``
unconditionally. On a **private** repo neither can ever succeed — CodeQL needs
GitHub Advanced Security (unavailable on Free-plan private repos) and OpenSSF
Scorecard is public-only — so the first private consumer would scaffold two
permanently red workflows.

The fix gates each analysis job with ``if: ${{ !github.event.repository.private
}}`` at the *job* level, so a private repo yields a skipped (neutral) run rather
than a failing one, and a repo later flipped public starts scanning
automatically with no re-scaffold. ``github.event.repository`` (and its
``private`` field) is populated on every trigger these workflows declare —
``pull_request``, ``push``, and (since the 2022-09-27 Actions change that added
repository info to scheduled-run payloads) ``schedule`` — so the guard is valid
and meaningful on all of them.

These assertions pin that invariant for both copies of each workflow: the
devkit's own (a public no-op) and the manifest-synced scaffold shipped to
consumers.

Refs: #1039
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

# Repository root (tests/ -> repo root).
REPO_ROOT = Path(__file__).resolve().parent.parent

# The guard skips the job whenever the repository is private.
EXPECTED_GUARD = "${{ !github.event.repository.private }}"

# (workflow path, analysis job key); each is checked in both the devkit's own
# copy and the manifest-synced scaffold copy under assets/workspace/.
_WORKFLOWS = [
    (".github/workflows/codeql.yml", "analyze"),
    (".github/workflows/scorecard.yml", "analysis"),
]
GUARDED_JOBS = [
    (REPO_ROOT / prefix / rel, job)
    for rel, job in _WORKFLOWS
    for prefix in (".", "assets/workspace")
]


def _load(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    ("path", "job"),
    GUARDED_JOBS,
    ids=lambda v: str(v.relative_to(REPO_ROOT)) if isinstance(v, Path) else v,
)
def test_scan_job_skips_on_private_repo(path: Path, job: str) -> None:
    """The analysis job is gated so private repos get a neutral (skipped) run."""
    workflow = _load(path)
    assert job in workflow["jobs"], f"{path} has no `{job}` job"
    guard = workflow["jobs"][job].get("if")
    assert guard == EXPECTED_GUARD, (
        f"{path} job `{job}` must be guarded with `if: {EXPECTED_GUARD}` so it "
        f"is skipped on private repos (CodeQL/Scorecard cannot succeed there); "
        f"found {guard!r}"
    )


# --- Scaffold ci.yml dependency-review job (#1140) ---------------------------
#
# The scaffold CI must gate PRs that introduce known-vulnerable dependencies,
# mirroring the devkit's own `dependency-review` job (minus its exceptions
# allow-list seam, which needs the dev-shell). The job is doubly guarded: the
# action only works on pull_request (base/head diff), and the dependency-graph
# API is unavailable on Free-plan private repos, so private repos get a
# skipped-neutral run and a repo flipped public activates automatically
# (#1039 pattern).

SCAFFOLD_CI = REPO_ROOT / "assets/workspace/.github/workflows/ci.yml"

# SHA pin for actions/dependency-review-action v5.0.0 (same pin as devkit-own).
DEP_REVIEW_ACTION = (
    "actions/dependency-review-action@a1d282b36b6f3519aa1f3fc636f609c47dddb294"
)


def _dep_review_job() -> dict:
    workflow = _load(SCAFFOLD_CI)
    assert "dependency-review" in workflow["jobs"], (
        f"{SCAFFOLD_CI} has no `dependency-review` job"
    )
    return workflow["jobs"]["dependency-review"]


def test_scaffold_ci_has_dependency_review_job() -> None:
    """The scaffold ci.yml ships a standalone `dependency-review` job."""
    job = _dep_review_job()
    assert "needs" not in job, "dependency-review must be standalone (no needs)"
    assert "container" not in job, "dependency-review must not run in a container"


def test_dependency_review_guarded_on_pr_and_public() -> None:
    """The guard skips on non-PR triggers and on private repos (#1039 pattern)."""
    guard = _dep_review_job().get("if", "")
    assert "github.event_name == 'pull_request'" in guard, (
        f"dependency-review `if` must gate on pull_request; found {guard!r}"
    )
    assert "!github.event.repository.private" in guard, (
        f"dependency-review `if` must skip private repos; found {guard!r}"
    )


def test_dependency_review_action_pinned_v5_fail_on_high() -> None:
    """The action is SHA-pinned to v5.0.0 and fails on high-severity findings."""
    steps = _dep_review_job()["steps"]
    review = [
        s
        for s in steps
        if str(s.get("uses", "")).startswith("actions/dependency-review-action@")
    ]
    assert review, "dependency-review job must run dependency-review-action"
    step = review[0]
    assert step["uses"] == DEP_REVIEW_ACTION, (
        f"dependency-review-action must be SHA-pinned to v5.0.0; found {step['uses']!r}"
    )
    assert step.get("with", {}).get("fail-on-severity") == "high", (
        "dependency-review-action must set fail-on-severity: high"
    )
    # No exceptions/allow-list seam in the scaffold (unlike devkit-own).
    assert "allow-ghsas" not in step.get("with", {}), (
        "scaffold dependency-review must not carry an allow-ghsas seam"
    )
    # v5.0.0 version comment pins the human-readable ref next to the SHA.
    assert "# v5.0.0" in SCAFFOLD_CI.read_text(encoding="utf-8"), (
        "dependency-review-action pin must carry its `# v5.0.0` version comment"
    )


def test_summary_needs_dependency_review_with_skip_tolerance() -> None:
    """CI Summary requires dependency-review but tolerates a skipped run."""
    workflow = _load(SCAFFOLD_CI)
    summary = workflow["jobs"]["summary"]
    assert "dependency-review" in summary["needs"], (
        "summary `needs` must include dependency-review"
    )
    run = summary["steps"][0]["run"]
    # Skip-tolerant, exactly like the PR-only commit-checks job: FAILED is set
    # only on a `failure` result, never on `skipped`/`cancelled`.
    assert 'needs.dependency-review.result }}" = "failure"' in run, (
        "summary must fail only when dependency-review result is failure"
    )
    for tolerated in ('"skipped"', '"cancelled"'):
        assert f"needs.dependency-review.result }}}} = {tolerated}" not in run, (
            f"dependency-review {tolerated} must not trip the summary"
        )
