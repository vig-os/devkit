"""Workflow-shape tests: scaffold release tags are lightweight refs, never tag objects.

Issue #1378 (downstream of #1370): the consumer scaffold's
``release-publish.yml`` created the release tag with ``git tag -a`` under a
GitHub App identity, producing an **annotated tag object** whose tagger is
permanently ``unsigned``. Signing it is not reachable — an App has no
registrable GPG/SSH key, and the server-side ``POST /git/tags`` route is not
signed by GitHub either. The same scaffold's ``promote-release.yml`` already
creates the *floating* tags as lightweight refs (#1045/#1157), so only the
version tag — the one users pin and audit — was an unsigned object.

The fix mirrors devkit's own ``release.yml`` (PR #1374): ``POST /git/refs``
writes ``refs/tags/<prefix><version>`` straight at the release commit. A
lightweight tag has no tagger and no payload, so nothing in the chain can
report ``unsigned``.

Mirrors ``tests/test_workflow_release_lightweight_tag.py`` for the scaffold.

Refs: #1378
"""

from __future__ import annotations

from pathlib import Path

import yaml

# Repository root (tests/ -> repo root).
REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_WORKFLOWS = REPO_ROOT / "assets" / "workspace" / ".github" / "workflows"

PUBLISH_WORKFLOW = TEMPLATE_WORKFLOWS / "release-publish.yml"
ORCHESTRATOR_WORKFLOW = TEMPLATE_WORKFLOWS / "release.yml"


def _load(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _publish_steps() -> list[dict]:
    workflow = _load(PUBLISH_WORKFLOW)
    (job,) = workflow["jobs"].values()
    return job["steps"]


def _publish_run_text() -> str:
    return "\n".join(step.get("run", "") for step in _publish_steps())


def test_publish_creates_no_annotated_tag_object() -> None:
    """No `git tag` invocation survives — an annotated object cannot be signed."""
    run = _publish_run_text()
    for forbidden in ("git tag -a", "git tag -s", "git tag "):
        assert forbidden not in run, (
            f"the scaffold publish must not run {forbidden!r}: a tag object "
            "written by the release App is unsigned and unsignable (#1378)"
        )


def test_publish_creates_the_tag_as_a_ref_at_the_release_commit() -> None:
    """The tag is a plain ref POSTed to the Git Data refs endpoint."""
    run = _publish_run_text()
    assert "git/refs" in run, "publish must create the tag via POST /git/refs"
    assert 'ref="refs/tags/${PUBLISH_TAG}"' in run, (
        "the created ref must be refs/tags/<prefixed publish version>"
    )
    assert 'sha="$FINALIZE_SHA"' in run, (
        "the tag ref must point at the finalize (release) commit SHA"
    )


def test_publish_composes_the_tag_prefix() -> None:
    """The tag name is TAG_PREFIX + publish version, never the bare version (#1044)."""
    create_step = _create_tag_step()
    assert 'PUBLISH_TAG="${TAG_PREFIX}${PUBLISH_VERSION}"' in create_step["run"], (
        "the create step must compose the prefixed tag name (#1044)"
    )
    env = create_step.get("env", {})
    assert env.get("TAG_PREFIX") == "${{ inputs.tag_prefix }}"
    assert env.get("FINALIZE_SHA") == "${{ inputs.finalize_sha }}"


def test_publish_does_not_stamp_a_git_identity() -> None:
    """The bot identity existed only to be the tagger; nothing needs it now."""
    run = _publish_run_text()
    assert "git config user." not in run, (
        "publish no longer writes git objects, so it must not configure an identity"
    )


def test_publish_drops_the_dead_git_identity_inputs() -> None:
    """The workflow_call identity inputs are dead once no tagger exists."""
    workflow = _load(PUBLISH_WORKFLOW)
    # PyYAML parses the bare ``on`` key as the boolean True.
    call_inputs = workflow[True]["workflow_call"]["inputs"]
    for dead in ("git_user_name", "git_user_email"):
        assert dead not in call_inputs, (
            f"release-publish.yml must not declare the dead input {dead!r} (#1378)"
        )


def test_orchestrator_drops_the_publish_identity_pass_throughs() -> None:
    """release.yml no longer threads the identity into the publish call."""
    workflow = _load(ORCHESTRATOR_WORKFLOW)
    publish_with = workflow["jobs"]["publish"]["with"]
    for dead in ("git_user_name", "git_user_email"):
        assert dead not in publish_with, (
            f"release.yml must not pass the dead input {dead!r} to release-publish"
        )


def test_orchestrator_keeps_the_rollback_identity() -> None:
    """The dispatch identity inputs survive: the rollback job still commits."""
    workflow = _load(ORCHESTRATOR_WORKFLOW)
    dispatch_inputs = workflow[True]["workflow_dispatch"]["inputs"]
    for kept in ("git-user-name", "git-user-email"):
        assert kept in dispatch_inputs, (
            f"release.yml must keep the {kept!r} dispatch input: the rollback "
            "job checks out the release branch and writes with that identity"
        )
    rollback_steps = workflow["jobs"]["rollback"]["steps"]
    configure = next(s for s in rollback_steps if s.get("name") == "Configure git")
    assert configure["env"]["GIT_USER_NAME"] == "${{ inputs.git-user-name }}"


def _create_tag_step() -> dict:
    steps = [
        step
        for step in _publish_steps()
        if "git/refs" in step.get("run", "") and "refs/tags/" in step.get("run", "")
    ]
    assert len(steps) == 1, "exactly one publish step may create the release tag"
    return steps[0]


def test_publish_tag_step_is_skipped_when_the_tag_already_exists() -> None:
    """Re-running a release over an existing tag at the finalize SHA is a no-op."""
    step = _create_tag_step()
    assert step["if"] == "${{ !inputs.tag_already_exists }}"


def test_publish_accepts_a_lost_race_only_at_the_release_commit() -> None:
    """A failed create is benign only when the ref already resolves to the commit."""
    run = _create_tag_step()["run"]
    # Peeled-then-plain resolution keeps pre-lightweight annotated tags readable.
    assert "^{}" in run, "race verification must still peel annotated tags"
    assert 'REMOTE_TAG_TARGET_SHA" != "$FINALIZE_SHA"' in run, (
        "a lost race is acceptable only when the existing ref resolves to the "
        "release commit"
    )
