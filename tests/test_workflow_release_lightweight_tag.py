"""Workflow-shape tests: release tags are lightweight refs, never tag objects.

Issue #1370: the publish job created the release tag with ``git tag -a`` under
the ``vigOS Release Bot <release@vig-os.local>`` identity, producing an
**annotated tag object** whose tagger is permanently ``unsigned`` (live evidence:
tag ``1.6.0``). Signing it is not reachable — the tag is written under a GitHub
**App** installation token, and an App has no registrable GPG/SSH key; the
server-side ``POST /git/tags`` route is not signed by GitHub either.

The fix is to create no tag object at all: ``POST /git/refs`` writes
``refs/tags/<version>`` straight at the release commit. A lightweight tag has no
tagger and no payload, so nothing in the chain can report ``unsigned``, and the
commit the ref resolves to is the GitHub-verified release commit.

Refs: #1370
"""

from __future__ import annotations

from pathlib import Path

import yaml

# Repository root (tests/ -> repo root).
REPO_ROOT = Path(__file__).resolve().parent.parent

RELEASE_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "release.yml"


def _publish_steps() -> list[dict]:
    workflow = yaml.safe_load(RELEASE_WORKFLOW.read_text(encoding="utf-8"))
    return workflow["jobs"]["publish"]["steps"]


def _publish_run_text() -> str:
    return "\n".join(step.get("run", "") for step in _publish_steps())


def test_publish_creates_no_annotated_tag_object() -> None:
    """No `git tag` invocation survives — an annotated object cannot be signed."""
    run = _publish_run_text()
    for forbidden in ("git tag -a", "git tag -s", "git tag "):
        assert forbidden not in run, (
            f"publish must not run {forbidden!r}: a tag object written by the "
            "release App is unsigned and unsignable (#1370)"
        )


def test_publish_creates_the_tag_as_a_ref_at_the_release_commit() -> None:
    """The tag is a plain ref POSTed to the Git Data refs endpoint."""
    run = _publish_run_text()
    assert "git/refs" in run, "publish must create the tag via POST /git/refs"
    assert 'ref="refs/tags/${PUBLISH_VERSION}"' in run, (
        "the created ref must be refs/tags/<publish version>"
    )
    assert 'sha="$FINALIZE_SHA"' in run, (
        "the tag ref must point at the finalize (release) commit SHA"
    )


def test_publish_does_not_stamp_a_git_identity() -> None:
    """The bot identity existed only to be the tagger; nothing needs it now."""
    run = _publish_run_text()
    assert "git config user." not in run, (
        "publish no longer writes git objects, so it must not configure an identity"
    )


def test_publish_still_guards_candidate_tag_collisions() -> None:
    """A concurrent RC publish must still be caught before the tag is written."""
    run = _publish_run_text()
    assert 'RELEASE_KIND" = "candidate"' in run, (
        "the candidate collision guard must survive the tag-creation rewrite"
    )


def test_publish_tag_step_is_skipped_when_the_tag_already_exists() -> None:
    """Re-running a release over an existing tag at the finalize SHA is a no-op."""
    steps = [
        step
        for step in _publish_steps()
        if "git/refs" in step.get("run", "") and "refs/tags/" in step.get("run", "")
    ]
    assert len(steps) == 1, "exactly one publish step may create the release tag"
    assert (
        steps[0]["if"] == "${{ needs.finalize.outputs.tag_already_exists != 'true' }}"
    )
