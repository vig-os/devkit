"""Workflow-shape tests: the hotfix release lane (``prepare-hotfix.yml``).

Issue #1621: a gitflow hotfix cuts ``release/X.Y.Z`` directly from ``main`` so
an urgent fix ships as a patch without carrying whatever ``dev`` accumulated.
Everything downstream of prepare (candidate/final/promote/abandon, the
prepare-release-extension hook, sync-main-to-dev) is base-agnostic and runs
unchanged; only prepare needs a counterpart. These assertions pin what makes
that counterpart safe:

- it never reads, checks out or writes ``dev`` (no freeze, no reset, no
  fast-forward — ``main``'s ``## Unreleased`` is empty by construction, #590);
- ``dry-run`` gates every mutating job;
- the version is a patch increment of the highest stable tag on ``main`` and no
  other ``release/*`` train is in flight;
- the extension hook runs between branch creation and the draft PR with the
  seeded commit as ``branch_sha`` (the shared DAG contract lives in
  ``tests/test_workflow_prepare_extension.py``, which parametrizes over this
  file too);
- rollback deletes the partial branch and nothing else;
- ``release.yml`` refuses to ship a version whose seeded section is still empty.

Phase 1 ships the lane in devkit's root workflows only; the scaffold copy is a
follow-up, so the operator recipe must not leak into the consumer ``justfile.gh``.

Refs: #1621
"""

from __future__ import annotations

import re

from tests.workflow_scaffold import (
    REPO_ROOT,
    WORKSPACE,
    jobs,
    load_workflow,
    needs_of,
    on_block,
    run_text_of_job,
    step_by_name,
    steps_of_job,
)

HOTFIX = REPO_ROOT / ".github" / "workflows" / "prepare-hotfix.yml"
RELEASE = REPO_ROOT / ".github" / "workflows" / "release.yml"
ROOT_JUSTFILE_GH = REPO_ROOT / "justfile.gh"
SCAFFOLD_JUSTFILE_GH = WORKSPACE / ".devcontainer" / "justfile.gh"

DEV_MARKERS = ("refs/heads/dev", "heads/dev", "origin/dev", "--ref dev", "ref: dev")


def _doc() -> dict:
    assert HOTFIX.is_file(), "prepare-hotfix.yml is missing"
    return load_workflow(HOTFIX)


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


def test_dispatch_inputs_match_prepare_release() -> None:
    """Same operator surface as prepare-release.yml: version + dry-run."""
    on = on_block(_doc())
    assert isinstance(on, dict) and "workflow_dispatch" in on
    inputs = on["workflow_dispatch"].get("inputs") or {}
    assert inputs["version"]["required"] is True
    assert inputs["dry-run"]["type"] == "boolean"
    assert inputs["dry-run"]["default"] is False


# --------------------------------------------------------------------------- #
# The lane never touches dev
# --------------------------------------------------------------------------- #


def test_no_job_reads_or_writes_dev() -> None:
    """No checkout ref, API path, git remote ref or commit target names dev."""
    doc = _doc()
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


def test_branch_is_cut_from_main() -> None:
    """The branch-creating job forks release/X.Y.Z from a main checkout."""
    name, job = _job_with_run(_doc(), "git/refs")
    refs = [(s.get("with") or {}).get("ref") for s in _checkout_steps(job)]
    assert refs == ["main"], f"{name}: expected a single checkout of main, got {refs}"


def test_every_checkout_drops_persisted_credentials() -> None:
    """All writes go through App tokens over the API; no checkout keeps git creds.

    Keeps the Phase 2 scaffold port out of the zizmor ``artipacked`` baseline.
    """
    for name, job in jobs(_doc()).items():
        if not isinstance(job, dict):
            continue
        for step in _checkout_steps(job):
            assert (step.get("with") or {}).get("persist-credentials") is False, (
                f"{name}: checkout must set persist-credentials: false"
            )


# --------------------------------------------------------------------------- #
# Validate: version policy and single-train policy
# --------------------------------------------------------------------------- #


def test_validate_enforces_patch_increment_of_latest_main_tag() -> None:
    """The version must be MAJOR.MINOR.(PATCH+1) of the highest stable tag on main."""
    run = run_text_of_job(jobs(_doc())["validate"])
    assert "--merged" in run and "sort -V" in run, (
        "validate must derive the highest stable tag reachable from main"
    )
    assert "PATCH + 1" in run or "PATCH+1" in run, (
        "validate must compute and assert the expected patch increment"
    )


def test_validate_refuses_when_another_release_branch_exists() -> None:
    """Hard refusal: no hotfix while any other release/* train is in flight."""
    run = run_text_of_job(jobs(_doc())["validate"])
    assert "refs/remotes/origin/release/" in run, (
        "validate must enumerate existing release/* branches"
    )
    assert "release train" in run.lower() or "in flight" in run.lower(), (
        "the refusal must name the in-flight train in its error message"
    )


def test_validate_requires_empty_unreleased_on_main() -> None:
    """Sanity: main's Unreleased is empty by construction (#590); refuse otherwise."""
    run = run_text_of_job(jobs(_doc())["validate"])
    assert "prepare-changelog validate" in run, (
        "validate must probe main's Unreleased with prepare-changelog validate"
    )


# --------------------------------------------------------------------------- #
# dry-run gates every mutating job
# --------------------------------------------------------------------------- #


def test_dry_run_gates_every_job_but_validate() -> None:
    doc = _doc()
    for name, job in jobs(doc).items():
        if name == "validate" or not isinstance(job, dict):
            continue
        cond = str(job.get("if", ""))
        assert "github.event.inputs.dry-run != 'true'" in cond, (
            f"{name}: must be skipped on dry-run"
        )


# --------------------------------------------------------------------------- #
# Prepare: seed commit on the branch, its SHA handed to the extension
# --------------------------------------------------------------------------- #


def test_prepare_seeds_changelog_on_the_release_branch() -> None:
    """The seed commit targets release/X.Y.Z (never main) via commit-action."""
    doc = _doc()
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


def test_extension_receives_the_seeded_commit_sha() -> None:
    """branch_sha passed to the hook is the prepare job's seed-commit output."""
    doc = _doc()
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


def test_open_pr_targets_main_as_draft() -> None:
    doc = _doc()
    name, job = _job_with_run(doc, "gh pr create")
    run = run_text_of_job(job)
    assert "--base main" in run
    assert "--draft" in run
    assert '--head "$RELEASE_BRANCH"' in run


def test_open_pr_needs_no_toolchain() -> None:
    """Same as prepare-release.yml (#1079): gh only, no setup-env."""
    _, job = _job_with_run(_doc(), "gh pr create")
    assert not any(
        isinstance(s, dict) and "setup-env" in str(s.get("uses", ""))
        for s in job.get("steps") or []
    )


# --------------------------------------------------------------------------- #
# Rollback: delete the partial branch, nothing else
# --------------------------------------------------------------------------- #


def test_rollback_deletes_only_the_release_branch() -> None:
    doc = _doc()
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
# release.yml: the finalize-time content guard
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


# --------------------------------------------------------------------------- #
# Operator recipe: present upstream, not leaked into the consumer scaffold
# --------------------------------------------------------------------------- #


def test_root_justfile_has_prepare_hotfix_recipe() -> None:
    text = ROOT_JUSTFILE_GH.read_text(encoding="utf-8")
    assert re.search(r"^prepare-hotfix version ref=\"\" \*flags:", text, re.MULTILINE)
    assert "gh workflow run prepare-hotfix.yml" in text


def test_scaffold_justfile_does_not_leak_prepare_hotfix() -> None:
    """Phase 1 is devkit-only: consumers have no prepare-hotfix.yml to dispatch."""
    assert "prepare-hotfix" not in SCAFFOLD_JUSTFILE_GH.read_text(encoding="utf-8")
