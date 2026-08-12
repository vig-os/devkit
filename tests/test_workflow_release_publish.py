"""Workflow-shape tests: release tags are lightweight refs, never tag objects.

Issues #1370 (devkit's own ``release.yml``) and #1378 (the consumer scaffold's
``release-publish.yml``): both publish surfaces created the release tag with
``git tag -a`` under a GitHub App identity, producing an **annotated tag
object** whose tagger is permanently ``unsigned`` (live evidence: tag
``1.6.0``). Signing it is not reachable — an App has no registrable GPG/SSH
key, and the server-side ``POST /git/tags`` route is not signed by GitHub
either.

The fix is to create no tag object at all: ``POST /git/refs`` writes
``refs/tags/<tag>`` straight at the release commit. A lightweight tag has no
tagger and no payload, so nothing in the chain can report ``unsigned``, and the
commit the ref resolves to is the GitHub-verified release commit.

The invariant is identical on both surfaces, so the shared tests parametrize
over them (merged from the former ``test_workflow_release_lightweight_tag.py``
/ ``test_workflow_release_publish_lightweight_tag.py``); the per-surface
sections pin what only one copy carries (the devkit candidate-collision guard;
the scaffold tag-prefix composition and dead-input cleanup).

Refs: #1370, #1378
"""

from __future__ import annotations

import pytest

from tests.workflow_scaffold import REPO_ROOT, WORKFLOWS, load_workflow, on_block

DEVKIT_RELEASE = REPO_ROOT / ".github" / "workflows" / "release.yml"
SCAFFOLD_PUBLISH = WORKFLOWS / "release-publish.yml"
SCAFFOLD_ORCHESTRATOR = WORKFLOWS / "release.yml"


def _publish_steps(surface: str) -> list[dict]:
    if surface == "devkit":
        return load_workflow(DEVKIT_RELEASE)["jobs"]["publish"]["steps"]
    (job,) = load_workflow(SCAFFOLD_PUBLISH)["jobs"].values()
    return job["steps"]


def _publish_run_text(surface: str) -> str:
    return "\n".join(step.get("run", "") for step in _publish_steps(surface))


def _create_tag_step(surface: str) -> dict:
    steps = [
        step
        for step in _publish_steps(surface)
        if "git/refs" in step.get("run", "") and "refs/tags/" in step.get("run", "")
    ]
    assert len(steps) == 1, "exactly one publish step may create the release tag"
    return steps[0]


# (surface, the created-ref literal, the skip-if guard) — the ref name and the
# tag_already_exists plumbing differ per surface, the invariant does not.
SURFACES = [
    pytest.param(
        "devkit",
        'ref="refs/tags/${PUBLISH_VERSION}"',
        "${{ needs.finalize.outputs.tag_already_exists != 'true' }}",
        id="devkit-release.yml",
    ),
    pytest.param(
        "scaffold",
        'ref="refs/tags/${PUBLISH_TAG}"',
        "${{ !inputs.tag_already_exists }}",
        id="scaffold-release-publish.yml",
    ),
]

parametrized = pytest.mark.parametrize(("surface", "ref_literal", "skip_if"), SURFACES)


@parametrized
def test_publish_creates_no_annotated_tag_object(
    surface: str, ref_literal: str, skip_if: str
) -> None:
    """No `git tag` invocation survives — an annotated object cannot be signed."""
    run = _publish_run_text(surface)
    for forbidden in ("git tag -a", "git tag -s", "git tag "):
        assert forbidden not in run, (
            f"publish must not run {forbidden!r}: a tag object written by the "
            "release App is unsigned and unsignable (#1370/#1378)"
        )


@parametrized
def test_publish_creates_the_tag_as_a_ref_at_the_release_commit(
    surface: str, ref_literal: str, skip_if: str
) -> None:
    """The tag is a plain ref POSTed to the Git Data refs endpoint."""
    run = _publish_run_text(surface)
    assert "git/refs" in run, "publish must create the tag via POST /git/refs"
    assert ref_literal in run, (
        f"the created ref must be {ref_literal} (the release tag name)"
    )
    assert 'sha="$FINALIZE_SHA"' in run, (
        "the tag ref must point at the finalize (release) commit SHA"
    )


@parametrized
def test_publish_does_not_stamp_a_git_identity(
    surface: str, ref_literal: str, skip_if: str
) -> None:
    """The bot identity existed only to be the tagger; nothing needs it now."""
    run = _publish_run_text(surface)
    assert "git config user." not in run, (
        "publish no longer writes git objects, so it must not configure an identity"
    )


@parametrized
def test_publish_tag_step_is_skipped_when_the_tag_already_exists(
    surface: str, ref_literal: str, skip_if: str
) -> None:
    """Re-running a release over an existing tag at the finalize SHA is a no-op."""
    assert _create_tag_step(surface)["if"] == skip_if


# ── devkit-only: the candidate publish path ──────────────────────────────────


def test_devkit_publish_still_guards_candidate_tag_collisions() -> None:
    """A concurrent RC publish must still be caught before the tag is written."""
    run = _publish_run_text("devkit")
    assert 'RELEASE_KIND" = "candidate"' in run, (
        "the candidate collision guard must survive the tag-creation rewrite"
    )


# ── scaffold-only: prefix composition, dead inputs, lost race ────────────────


def test_scaffold_publish_composes_the_tag_prefix() -> None:
    """The tag name is TAG_PREFIX + publish version, never the bare version (#1044)."""
    create_step = _create_tag_step("scaffold")
    assert 'PUBLISH_TAG="${TAG_PREFIX}${PUBLISH_VERSION}"' in create_step["run"], (
        "the create step must compose the prefixed tag name (#1044)"
    )
    env = create_step.get("env", {})
    assert env.get("TAG_PREFIX") == "${{ inputs.tag_prefix }}"
    assert env.get("FINALIZE_SHA") == "${{ inputs.finalize_sha }}"


def test_scaffold_drops_the_dead_git_identity_inputs() -> None:
    """With no tagger left, the identity plumbing is dead on both ends (#1378):
    release-publish.yml must not declare the workflow_call inputs, and the
    orchestrator release.yml must not thread them into the publish call."""
    publish = load_workflow(SCAFFOLD_PUBLISH)
    call_inputs = on_block(publish)["workflow_call"]["inputs"]
    orchestrator = load_workflow(SCAFFOLD_ORCHESTRATOR)
    publish_with = orchestrator["jobs"]["publish"]["with"]
    for dead in ("git_user_name", "git_user_email"):
        assert dead not in call_inputs, (
            f"release-publish.yml must not declare the dead input {dead!r} (#1378)"
        )
        assert dead not in publish_with, (
            f"release.yml must not pass the dead input {dead!r} to release-publish"
        )


def test_scaffold_orchestrator_keeps_the_dispatch_identity_inputs() -> None:
    """The dispatch identity inputs survive while release-core declares them.

    #1378 kept them for the git-CLI rollback; #1462 replaced that rollback
    with Git Data API commits (App identity, no configured git user), so the
    rollback job must mint the commit App token instead of configuring a
    local identity.
    """
    workflow = load_workflow(SCAFFOLD_ORCHESTRATOR)
    dispatch_inputs = on_block(workflow)["workflow_dispatch"]["inputs"]
    for kept in ("git-user-name", "git-user-email"):
        assert kept in dispatch_inputs, (
            f"release.yml must keep the {kept!r} dispatch input while the "
            "release-core call still declares it"
        )
    rollback_steps = workflow["jobs"]["rollback"]["steps"]
    assert not any(s.get("name") == "Configure git" for s in rollback_steps), (
        "the API-based rollback must not configure a git-CLI identity (#1462)"
    )
    rollback = next(
        s for s in rollback_steps if s.get("name") == "Rollback release branch"
    )
    assert rollback["env"]["GH_TOKEN"] == "${{ steps.commit_app_token.outputs.token }}"


def test_scaffold_publish_accepts_a_lost_race_only_at_the_release_commit() -> None:
    """A failed create is benign only when the ref already resolves to the commit."""
    run = _create_tag_step("scaffold")["run"]
    # Peeled-then-plain resolution keeps pre-lightweight annotated tags readable.
    assert "^{}" in run, "race verification must still peel annotated tags"
    assert 'REMOTE_TAG_TARGET_SHA" != "$FINALIZE_SHA"' in run, (
        "a lost race is acceptable only when the existing ref resolves to the "
        "release commit"
    )


def test_scaffold_publish_ceiling_is_read_only() -> None:
    """Workflow and publish-job ceilings grant reads only (#1418).

    Tag creation and release publishing go through the minted App token, so
    GITHUB_TOKEN never needs a write grant; a widening here must fail review.
    """
    workflow = load_workflow(SCAFFOLD_PUBLISH)
    read_only = {"contents": "read", "packages": "read"}
    assert workflow["permissions"] == read_only
    (job,) = workflow["jobs"].values()
    assert job["permissions"] == read_only
