"""Workflow-shape test: tombstoned tag names fail with the real cause.

Issue #1319 (lesson from the 1.5.0 ghost, #1301): with org-enforced release
immutability, deleting a *published* GitHub Release permanently retires
(tombstones) its tag name — re-creating the tag or a release for it fails with
``GH013: ... creations restricted``. Two workflow surfaces previously reported
this state misleadingly:

- the downstream ``release-publish.yml`` template died with a generic
  "Failed to push tag" / raw ``gh`` error, hiding that the version is burned;
- devkit's ``promote-release.yml`` cross-repo gate said "wait for the
  smoke-test workflow to publish its final release, then retry" — futile
  advice when the smoke tag is tombstoned and can never be re-published.

This pins the detection: the publish steps must recognize the GH013 signature
and fail with a "version burned — re-cut required" diagnosis, and the gate's
no-downstream-release error must name the tombstone as a possible cause. The
live GH013 path is only provable on a real tombstone, so these tests assert
the script shape, not the choreography.

Since #1378 the tag is created via ``POST /git/refs`` instead of ``git push``,
so the tag-side signature is matched against the API error surface (HTTP 422
JSON body, ``Cannot create ref due to creations being restricted.``) as well as
the git-protocol ``GH013`` shape. The extracted grep pattern is exercised
against both shapes — and against the benign lost-race shape, which must NOT
match — so the detection cannot silently rot into matching neither.

Refs: #1319
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_WORKFLOWS = REPO_ROOT / "assets" / "workspace" / ".github" / "workflows"
DEVKIT_WORKFLOWS = REPO_ROOT / ".github" / "workflows"


def _load(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _step_run(workflow_path: Path, job: str, step_name: str) -> str:
    workflow = _load(workflow_path)
    steps = workflow["jobs"][job]["steps"]
    step = next(s for s in steps if s.get("name") == step_name)
    return step["run"]


def _publish_step_run(step_name: str) -> str:
    workflow = _load(TEMPLATE_WORKFLOWS / "release-publish.yml")
    (job,) = workflow["jobs"].values()
    step = next(s for s in job["steps"] if s.get("name") == step_name)
    return step["run"]


# Observed error surfaces for a tombstoned tag name. The git-protocol shape is
# live evidence from the 1.5.0 ghost (#1301); the API shape is the repository
# rules engine's 422 body for a rule-rejected `POST /git/refs`, as `gh api`
# prints it. The race shape ("Reference already exists") must NOT match: it is
# the benign lost-race case, resolved by the remote-state verification instead.
TOMBSTONE_GIT_SHAPE = (
    "remote: error: GH013: Repository rule violations found for refs/tags/1.5.0.\n"
    "remote: - Cannot create ref due to creations being restricted."
)
TOMBSTONE_API_SHAPE = (
    "gh: Repository rule violations found\n"
    "Cannot create ref due to creations being restricted. (HTTP 422)"
)
BENIGN_RACE_SHAPE = "gh: Reference already exists (HTTP 422)"


def _extract_grep_pattern(run: str) -> str:
    """Pull the tombstone signature out of the step's ``grep -Eqi`` line."""
    match = re.search(r'grep -Eqi "([^"]+)"', run)
    assert match, "the step must grep the captured output for the tombstone signature"
    return match.group(1)


def test_tag_create_detects_tombstone() -> None:
    """A rule-rejected tag ref creation is diagnosed as a tombstone."""
    run = _publish_step_run("Create release tag")
    assert "burned" in run
    pattern = re.compile(_extract_grep_pattern(run), re.IGNORECASE)
    assert pattern.search(TOMBSTONE_GIT_SHAPE), (
        "the signature must still match the git-protocol GH013 shape"
    )
    assert pattern.search(TOMBSTONE_API_SHAPE), (
        "the signature must match the POST /git/refs 422 rule-violation shape"
    )
    assert not pattern.search(BENIGN_RACE_SHAPE), (
        "a benign lost race must not be diagnosed as a tombstone"
    )


def test_release_create_detects_tombstone() -> None:
    """A GH013-rejected release create is diagnosed as a tombstone."""
    run = _publish_step_run("Create GitHub Release")
    assert "GH013" in run
    assert "burned" in run


def test_tombstone_diagnosis_points_at_runbook() -> None:
    """The burned-version diagnosis points at the point-of-no-return runbook."""
    run = _publish_step_run("Create release tag")
    assert "Point of No Return" in run


def test_promote_gate_names_tombstone_cause() -> None:
    """The cross-repo gate's no-release error names the tombstone as a cause."""
    run = _step_run(
        DEVKIT_WORKFLOWS / "promote-release.yml",
        "validate",
        "Verify downstream published final release",
    )
    assert "tombstone" in run
    assert "GH013" in run
    assert "burned" in run
