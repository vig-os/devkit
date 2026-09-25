"""Workflow-shape tests: the hotfix release lane (``prepare-hotfix.yml``).

Issue #1621: a gitflow hotfix cuts ``release/X.Y.Z`` directly from ``main`` so
an urgent fix ships as a patch without carrying whatever ``dev`` accumulated.
Everything downstream of prepare (candidate/final/promote/abandon, the
prepare-release-extension hook, sync-main-to-dev) is base-agnostic and runs
unchanged; only prepare needs a counterpart. These assertions pin what makes
that counterpart safe:

- it never reads, checks out or writes ``dev`` (no freeze on ``dev``, no reset,
  no fast-forward): whatever ``main``'s ``## Unreleased`` carries is frozen on
  the RELEASE BRANCH, never on ``main`` and never on ``dev``;
- ``dry-run`` gates every mutating job;
- the version is a patch increment of the highest stable tag on ``main`` and no
  other ``release/*`` train is in flight;
- the extension hook runs between branch creation and the draft PR with the
  seeded commit as ``branch_sha`` (the shared DAG contract lives in
  ``tests/test_workflow_prepare_extension.py``, which parametrizes over this
  file too);
- rollback deletes the partial branch and nothing else;
- ``release.yml`` refuses to ship a version whose seeded section is still empty.

#1679: ``main`` may now carry changes that have landed but are not yet shipped
(#1676 supersedes #590's empty-by-construction invariant), so ``validate`` no
longer refuses a non-empty ``## Unreleased`` on ``main`` — it classifies it and
``prepare`` freezes (``prepare-changelog prepare``) or seeds
(``prepare-changelog seed``) accordingly.

Phase 1 (#1621) shipped the lane in devkit's root workflows; Phase 2 (#1625)
ports it to the consumer scaffold in the scaffold dialect (mode-aware devkit
toolchain instead of ``uv run`` + ``setup-env``, tag-prefix-aware tag checks),
copy-excluded under the trunk workflow model where releases already cut from
``main``. The invariants above hold for both copies; the scaffold's
``release-core.yml`` gains the same finalize-time content guard.

Refs: #1621, #1625, #1679
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pytest

from tests.workflow_scaffold import (
    REPO_ROOT,
    WORKFLOWS,
    WORKSPACE,
    jobs,
    load_workflow,
    needs_of,
    on_block,
    run_text_of_job,
    step_by_name,
    steps_of_job,
)

if TYPE_CHECKING:
    from pathlib import Path

# copy id -> the prepare-hotfix.yml of that copy (#1625 ports the lane).
HOTFIX_COPIES: dict[str, Path] = {
    "devkit": REPO_ROOT / ".github" / "workflows" / "prepare-hotfix.yml",
    "scaffold": WORKFLOWS / "prepare-hotfix.yml",
}
COPIES = list(HOTFIX_COPIES)
RELEASE = REPO_ROOT / ".github" / "workflows" / "release.yml"
SCAFFOLD_RELEASE_CORE = WORKFLOWS / "release-core.yml"
ROOT_JUSTFILE_GH = REPO_ROOT / "justfile.gh"
SCAFFOLD_JUSTFILE_GH = WORKSPACE / ".devcontainer" / "justfile.gh"

DEV_MARKERS = ("refs/heads/dev", "heads/dev", "origin/dev", "--ref dev", "ref: dev")

# Jobs that never mutate anything and therefore run on a dry-run too: validate
# itself, and the scaffold's read-only toolchain resolution (#991).
READ_ONLY_JOBS = {"validate", "resolve-toolchain"}

# The two dialects spell the dry-run gate differently.
DRY_RUN_GATES = ("github.event.inputs.dry-run != 'true'", "inputs.dry-run != true")


def _doc(copy: str = "devkit") -> dict:
    path = HOTFIX_COPIES[copy]
    assert path.is_file(), f"{copy}: prepare-hotfix.yml is missing"
    return load_workflow(path)


def _job_with_run(doc: dict, needle: str) -> tuple[str, dict]:
    for name, job in jobs(doc).items():
        if isinstance(job, dict) and needle in run_text_of_job(job):
            return name, job
    raise AssertionError(f"no job whose run: bodies contain {needle!r}")


def _checkout_steps(job: dict) -> list[dict]:
    return [
        s
        for s in job.get("steps") or []
        if isinstance(s, dict) and "actions/checkout" in str(s.get("uses", ""))
    ]


# --------------------------------------------------------------------------- #
# Trigger and inputs
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("copy", COPIES)
def test_dispatch_inputs_match_prepare_release(copy: str) -> None:
    """Same operator surface as prepare-release.yml: version + dry-run."""
    on = on_block(_doc(copy))
    assert isinstance(on, dict) and "workflow_dispatch" in on
    inputs = on["workflow_dispatch"].get("inputs") or {}
    assert inputs["version"]["required"] is True
    assert inputs["dry-run"]["type"] == "boolean"
    assert inputs["dry-run"]["default"] is False


# --------------------------------------------------------------------------- #
# The lane never touches dev
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("copy", COPIES)
def test_no_job_reads_or_writes_dev(copy: str) -> None:
    """No checkout ref, API path, git remote ref or commit target names dev."""
    doc = _doc(copy)
    for name, job in jobs(doc).items():
        if not isinstance(job, dict):
            continue
        for step in _checkout_steps(job):
            ref = (step.get("with") or {}).get("ref")
            assert ref != "dev", f"{name}: checkout must not target dev"
        run = run_text_of_job(job)
        for marker in DEV_MARKERS:
            assert marker not in run, f"{name}: run body references dev ({marker!r})"
        for step in job.get("steps") or []:
            env = (step.get("env") or {}) if isinstance(step, dict) else {}
            assert env.get("TARGET_BRANCH") != "refs/heads/dev", (
                f"{name}: a commit-action step targets dev"
            )


@pytest.mark.parametrize("copy", COPIES)
def test_branch_is_cut_from_main(copy: str) -> None:
    """The branch-creating job forks release/X.Y.Z from a main checkout."""
    name, job = _job_with_run(_doc(copy), "git/refs")
    refs = [(s.get("with") or {}).get("ref") for s in _checkout_steps(job)]
    assert refs == ["main"], f"{name}: expected a single checkout of main, got {refs}"


@pytest.mark.parametrize("copy", COPIES)
def test_every_checkout_drops_persisted_credentials(copy: str) -> None:
    """All writes go through App tokens over the API; no checkout keeps git creds.

    Keeps the Phase 2 scaffold port out of the zizmor ``artipacked`` baseline.
    """
    for name, job in jobs(_doc(copy)).items():
        if not isinstance(job, dict):
            continue
        for step in _checkout_steps(job):
            assert (step.get("with") or {}).get("persist-credentials") is False, (
                f"{name}: checkout must set persist-credentials: false"
            )


# --------------------------------------------------------------------------- #
# Validate: version policy and single-train policy
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("copy", COPIES)
def test_validate_enforces_patch_increment_of_latest_main_tag(copy: str) -> None:
    """The version must be MAJOR.MINOR.(PATCH+1) of the highest stable tag on main."""
    run = run_text_of_job(jobs(_doc(copy))["validate"])
    assert "--merged" in run and "sort -V" in run, (
        "validate must derive the highest stable tag reachable from main"
    )
    assert "PATCH + 1" in run or "PATCH+1" in run, (
        "validate must compute and assert the expected patch increment"
    )


@pytest.mark.parametrize("copy", COPIES)
def test_validate_refuses_when_another_release_branch_exists(copy: str) -> None:
    """Hard refusal: no hotfix while any other release/* train is in flight."""
    run = run_text_of_job(jobs(_doc(copy))["validate"])
    assert "release/" in run and ("for-each-ref" in run or "ls-remote" in run), (
        "validate must enumerate existing release/* branches"
    )
    assert "release train" in run.lower() or "in flight" in run.lower(), (
        "the refusal must name the in-flight train in its error message"
    )


@pytest.mark.parametrize("copy", COPIES)
def test_validate_classifies_mains_unreleased_instead_of_refusing(copy: str) -> None:
    """#1679: content on main's ## Unreleased is a mode, not a refusal.

    Under #1676's model main may carry unshipped changes; a hotfix cuts from
    main's head and therefore ships them. validate probes the section and hands
    prepare the verdict as an output instead of failing the lane.
    """
    validate = jobs(_doc(copy))["validate"]
    run = run_text_of_job(validate)
    assert "prepare-changelog validate" in run, (
        "validate must probe main's Unreleased with prepare-changelog validate"
    )
    assert "a hotfix seeds an EMPTY section" not in run, (
        "validate must no longer refuse a non-empty ## Unreleased on main (#1679)"
    )
    assert "changelog_mode" in (validate.get("outputs") or {}), (
        "validate must publish the prepare/seed verdict as a job output"
    )


# --------------------------------------------------------------------------- #
# dry-run gates every mutating job
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("copy", COPIES)
def test_dry_run_gates_every_job_but_validate(copy: str) -> None:
    doc = _doc(copy)
    for name, job in jobs(doc).items():
        if name in READ_ONLY_JOBS or not isinstance(job, dict):
            continue
        cond = str(job.get("if", ""))
        assert any(gate in cond for gate in DRY_RUN_GATES), (
            f"{name}: must be skipped on dry-run"
        )


# --------------------------------------------------------------------------- #
# Prepare: seed commit on the branch, its SHA handed to the extension
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("copy", COPIES)
def test_prepare_seeds_changelog_on_the_release_branch(copy: str) -> None:
    """The seed commit targets release/X.Y.Z (never main) via commit-action."""
    doc = _doc(copy)
    commits = [
        (name, s)
        for name, job in jobs(doc).items()
        if isinstance(job, dict)
        for s in job.get("steps") or []
        if isinstance(s, dict) and "vig-os/commit-action" in str(s.get("uses", ""))
    ]
    assert len(commits) == 1, "expected exactly one commit-action step in the lane"
    name, commit = commits[0]
    assert "prepare-changelog seed" in run_text_of_job(jobs(doc)[name]), (
        f"{name}: the committing job must be the one that seeds the changelog"
    )
    target = (commit.get("env") or {}).get("TARGET_BRANCH", "")
    assert target.startswith("refs/heads/release/"), target
    assert (commit.get("env") or {}).get("FILE_PATHS") == "CHANGELOG.md"


@pytest.mark.parametrize("copy", COPIES)
def test_prepare_freezes_carried_entries_or_seeds_an_empty_section(copy: str) -> None:
    """#1679: the committing job branches on validate's changelog_mode.

    Content on main -> ``prepare-changelog prepare`` freezes it into
    ``## [X.Y.Z] - TBD``; empty -> ``prepare-changelog seed`` as before. Either
    way the write lands on the release branch (asserted above), never on main.
    """
    doc = _doc(copy)
    name = next(
        n
        for n, j in jobs(doc).items()
        if isinstance(j, dict)
        and any(
            isinstance(s, dict) and "vig-os/commit-action" in str(s.get("uses", ""))
            for s in j.get("steps") or []
        )
    )
    job = jobs(doc)[name]
    run = run_text_of_job(job)
    assert 'prepare-changelog prepare "$VERSION" CHANGELOG.md' in run, (
        f"{name}: must freeze main's carried Unreleased entries when present"
    )
    assert 'prepare-changelog seed "$VERSION" CHANGELOG.md' in run, (
        f"{name}: must still seed an empty section when main's Unreleased is empty"
    )
    envs = "\n".join(
        str((s.get("env") or {}).values())
        for s in job.get("steps") or []
        if isinstance(s, dict)
    )
    assert "needs.validate.outputs.changelog_mode" in envs, (
        f"{name}: the branch must read validate's changelog_mode verdict"
    )


@pytest.mark.parametrize("copy", COPIES)
def test_extension_receives_the_seeded_commit_sha(copy: str) -> None:
    """branch_sha passed to the hook is the prepare job's seed-commit output."""
    doc = _doc(copy)
    ext = next(
        job
        for job in jobs(doc).values()
        if isinstance(job, dict)
        and str(job.get("uses", "")).endswith("prepare-release-extension.yml")
    )
    branch_name, _ = _job_with_run(doc, "git/refs")
    passed = ext.get("with") or {}
    assert passed.get("branch_sha") == (
        f"${{{{ needs.{branch_name}.outputs.branch_sha }}}}"
    ), passed


# --------------------------------------------------------------------------- #
# Open-PR: draft PR to main on a bare checkout
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("copy", COPIES)
def test_open_pr_targets_main_as_draft(copy: str) -> None:
    doc = _doc(copy)
    name, job = _job_with_run(doc, "gh pr create")
    run = run_text_of_job(job)
    assert "--base main" in run
    assert "--draft" in run
    assert '--head "$RELEASE_BRANCH"' in run


def test_open_pr_needs_no_toolchain() -> None:
    """Devkit copy, same as its prepare-release.yml (#1079): gh only, no setup-env."""
    _, job = _job_with_run(_doc("devkit"), "gh pr create")
    assert not any(
        isinstance(s, dict) and "setup-env" in str(s.get("uses", ""))
        for s in job.get("steps") or []
    )


# --------------------------------------------------------------------------- #
# Rollback: delete the partial branch, nothing else
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("copy", COPIES)
def test_rollback_deletes_only_the_release_branch(copy: str) -> None:
    doc = _doc(copy)
    branch_name, _ = _job_with_run(doc, "git/refs")
    ext_name = next(
        name
        for name, job in jobs(doc).items()
        if isinstance(job, dict)
        and str(job.get("uses", "")).endswith("prepare-release-extension.yml")
    )
    pr_name, _ = _job_with_run(doc, "gh pr create")
    rollback = jobs(doc)["rollback"]
    assert set(needs_of(rollback)) >= {"validate", branch_name, ext_name, pr_name}
    cond = str(rollback.get("if", ""))
    assert "always()" in cond
    assert "needs.validate.result == 'success'" in cond
    run = run_text_of_job(rollback)
    assert "-X DELETE" in run and "git/refs/heads/$RELEASE_BRANCH" in run
    # No dev mutation exists to undo: no commit-action, no contents API writes.
    assert not any(
        isinstance(s, dict) and "vig-os/commit-action" in str(s.get("uses", ""))
        for s in rollback.get("steps") or []
    ), "rollback must not commit anything (nothing on dev to restore)"
    assert "contents/CHANGELOG.md" not in run


# --------------------------------------------------------------------------- #
# Scaffold dialect (#1625): mode-aware toolchain, no uv, tag-prefix aware
# --------------------------------------------------------------------------- #


def test_scaffold_copy_runs_on_the_devkit_toolchain() -> None:
    """No ``uv run`` / ``setup-env``: the CLI comes from the resolved toolchain (#991)."""
    doc = _doc("scaffold")
    all_run = "\n".join(
        run_text_of_job(job) for job in jobs(doc).values() if isinstance(job, dict)
    )
    assert "uv run" not in all_run
    uses = [
        str(s.get("uses", ""))
        for job in jobs(doc).values()
        if isinstance(job, dict)
        for s in job.get("steps") or []
        if isinstance(s, dict)
    ]
    assert not any("setup-env" in u for u in uses)
    assert any(u.endswith("actions/resolve-toolchain") for u in uses)
    for name, job in jobs(doc).items():
        if not isinstance(job, dict) or "prepare-changelog" not in run_text_of_job(job):
            continue
        assert any(
            isinstance(s, dict)
            and str(s.get("uses", "")).endswith("actions/setup-devkit-toolchain")
            for s in job.get("steps") or []
        ), f"{name}: runs prepare-changelog without the devkit toolchain"


def test_scaffold_validate_is_tag_prefix_aware() -> None:
    """Consumers publish ``<prefix>X.Y.Z`` tags (#1044): the latest-tag lookup and
    the collision check must strip/apply the prefix, never assume bare tags."""
    steps = steps_of_job(_doc("scaffold"), "validate")
    prefixed = [s for s in steps if "TAG_PREFIX" in (s.get("env") or {})]
    assert prefixed, "no validate step receives TAG_PREFIX"
    run = "\n".join(str(s.get("run", "")) for s in prefixed)
    assert "sort -V" in run, "the latest-tag lookup must be prefix-aware"
    assert "already exists" in run, "the tag collision check must be prefix-aware"


# --------------------------------------------------------------------------- #
# release.yml / release-core.yml: the finalize-time content guard
# --------------------------------------------------------------------------- #


def test_release_validate_refuses_an_empty_pending_section() -> None:
    """release.yml's TBD check must require content, not just the heading.

    A hotfix branch is seeded with an empty ``## [X.Y.Z] - TBD``; the fix PR
    fills it. A bare grep for the heading would let an unfilled section ship.
    """
    step = step_by_name(steps_of_job(load_workflow(RELEASE), "validate"), "TBD")
    assert re.search(
        r'prepare-changelog validate --version "\$VERSION"', step["run"]
    ), step["run"]


def test_scaffold_release_core_refuses_an_empty_pending_section() -> None:
    """The scaffold's ``release-core.yml`` carries the same guard (#1625).

    Its validate step used to grep for the bare heading, which would let a
    seeded-but-unfilled hotfix section ship downstream.
    """
    step = step_by_name(
        steps_of_job(load_workflow(SCAFFOLD_RELEASE_CORE), "validate"), "TBD"
    )
    assert re.search(
        r'prepare-changelog validate --version "\$VERSION"', step["run"]
    ), step["run"]


# --------------------------------------------------------------------------- #
# Operator recipe: present upstream and, since #1625, in the consumer scaffold
# --------------------------------------------------------------------------- #


def test_root_justfile_has_prepare_hotfix_recipe() -> None:
    text = ROOT_JUSTFILE_GH.read_text(encoding="utf-8")
    assert re.search(r"^prepare-hotfix version ref=\"\" \*flags:", text, re.MULTILINE)
    assert "gh workflow run prepare-hotfix.yml" in text


def test_scaffold_justfile_ships_prepare_hotfix_recipe() -> None:
    """Phase 2: the recipe reaches consumers alongside the workflow it dispatches."""
    text = SCAFFOLD_JUSTFILE_GH.read_text(encoding="utf-8")
    assert re.search(r"^prepare-hotfix version ref=\"\" \*flags:", text, re.MULTILINE)
    assert "gh workflow run prepare-hotfix.yml" in text
