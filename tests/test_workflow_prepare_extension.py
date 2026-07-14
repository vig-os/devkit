"""Workflow-shape tests: the prepare-release extension hook.

Issue #1059: ``prepare-release.yml`` gains a scaffolded ``prepare-release-extension.yml``
reusable workflow (``on: workflow_call``, default no-op) — the *mutating*
counterpart to the read-only ``release-extension.yml`` that ``release.yml``
already calls.

The hook is invoked from the prepare phase **after** the ``release/X.Y.Z`` branch
is created (and the changelog-freeze commit pushed) and **before** the draft PR
to ``main`` is opened, so any commits a consumer's extension pushes to the fresh
release branch appear in the PR diff from the start. A reusable workflow is a
job, so the phase is split into jobs (``prepare`` creates the branch,
``extension`` runs the hook, ``open-pr`` opens the draft PR); the single
``rollback`` job watches every phase, so an extension failure deletes the partial
release branch exactly as a ``prepare`` failure would — everything the extension
commits lives on the branch the rollback deletes.

These assertions pin the contract for both copies: the scaffold shipped to
consumers and devkit's own dogfooding workflow (whose extension implements the
``sync_manifest.py sync`` step that used to be a hardcoded divergence).

Refs: #1059
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

# Repository root (tests/ -> repo root) and the consumer scaffold tree.
REPO_ROOT = Path(__file__).resolve().parent.parent
WORKSPACE = REPO_ROOT / "assets" / "workspace"

SCAFFOLD_PREPARE = WORKSPACE / ".github" / "workflows" / "prepare-release.yml"
SCAFFOLD_EXTENSION = (
    WORKSPACE / ".github" / "workflows" / "prepare-release-extension.yml"
)
DEVKIT_PREPARE = REPO_ROOT / ".github" / "workflows" / "prepare-release.yml"
DEVKIT_EXTENSION = REPO_ROOT / ".github" / "workflows" / "prepare-release-extension.yml"

# Both copies of the caller share the same job DAG contract.
CALLER_WORKFLOWS = [SCAFFOLD_PREPARE, DEVKIT_PREPARE]

# Inputs the hook contract carries (issue #1059). Underscore convention, per
# DOWNSTREAM_RELEASE.md's "Input Naming Convention".
REQUIRED_INPUTS = {
    "version",
    "release_branch",
    "branch_sha",
    "dry_run",
    "git_user_name",
    "git_user_email",
}


def _load(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _on(doc: dict) -> object:
    # YAML 1.1 parses the bare ``on:`` key as the boolean ``True``.
    return doc.get("on", doc.get(True))


def _jobs(doc: dict) -> dict:
    return doc.get("jobs") or {}


def _needs(job: dict) -> list[str]:
    needs = job.get("needs") or []
    return [needs] if isinstance(needs, str) else list(needs)


def _job_steps_text(job: dict) -> str:
    """All ``run:`` bodies of a job's steps, concatenated."""
    return "\n".join(
        str(s.get("run", "")) for s in (job.get("steps") or []) if isinstance(s, dict)
    )


def _extension_job(doc: dict) -> tuple[str, dict] | tuple[None, None]:
    """The (name, job) that calls the prepare-release-extension reusable workflow."""
    for name, job in _jobs(doc).items():
        if isinstance(job, dict) and str(job.get("uses", "")).endswith(
            "prepare-release-extension.yml"
        ):
            return name, job
    return None, None


def _job_with_step_run(doc: dict, needle: str) -> tuple[str, dict] | tuple[None, None]:
    """First (name, job) whose concatenated step bodies contain ``needle``."""
    for name, job in _jobs(doc).items():
        if isinstance(job, dict) and needle in _job_steps_text(job):
            return name, job
    return None, None


# --------------------------------------------------------------------------- #
# The scaffolded reusable workflow itself
# --------------------------------------------------------------------------- #


def test_scaffold_ships_prepare_release_extension() -> None:
    """The scaffold ships the mutating extension hook."""
    assert SCAFFOLD_EXTENSION.is_file(), (
        "assets/workspace/.github/workflows/prepare-release-extension.yml must exist"
    )


def test_prepare_extension_is_workflow_call_with_required_inputs() -> None:
    """The hook is a reusable workflow carrying the whole prepare-phase context."""
    doc = _load(SCAFFOLD_EXTENSION)
    on = _on(doc)
    assert isinstance(on, dict) and "workflow_call" in on, (
        "prepare-release-extension.yml must trigger on workflow_call"
    )
    inputs = set((on["workflow_call"].get("inputs") or {}).keys())
    missing = REQUIRED_INPUTS - inputs
    assert not missing, (
        f"prepare-release-extension.yml missing inputs: {sorted(missing)}"
    )


def test_prepare_extension_default_is_noop_readonly() -> None:
    """The default hook only reads (contents: read) and prints its inputs."""
    doc = _load(SCAFFOLD_EXTENSION)
    assert (doc.get("permissions") or {}).get("contents") == "read", (
        "the default no-op hook must declare read-only permissions"
    )
    assert "vig-os/commit-action" not in SCAFFOLD_EXTENSION.read_text(
        encoding="utf-8"
    ), "the default no-op hook must not commit anything"


# --------------------------------------------------------------------------- #
# The call site: extension runs between branch-creation and PR-open
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "path", CALLER_WORKFLOWS, ids=lambda p: str(p.relative_to(REPO_ROOT))
)
def test_prepare_release_calls_extension_between_branch_and_pr(path: Path) -> None:
    """The extension job runs after branch creation and before the draft PR."""
    doc = _load(path)
    ext_name, ext_job = _extension_job(doc)
    assert ext_name is not None, (
        f"{path.relative_to(REPO_ROOT)} must call ./.github/workflows/"
        "prepare-release-extension.yml as a job"
    )

    # The branch-creating job pushes the release ref via the git refs API.
    branch_name, _ = _job_with_step_run(doc, "git/refs")
    assert branch_name is not None, "could not locate the release-branch-creating job"

    # The PR-opening job runs `gh pr create`.
    pr_name, pr_job = _job_with_step_run(doc, "gh pr create")
    assert pr_name is not None, "could not locate the draft-PR-opening job"
    assert pr_name != ext_name and pr_name != branch_name

    # Ordering: extension after branch creation, PR after extension.
    assert branch_name in _needs(ext_job), (
        f"the extension job must run after branch creation (needs: {branch_name})"
    )
    assert ext_name in _needs(pr_job), (
        f"the draft PR must open after the extension (needs: {ext_name})"
    )


@pytest.mark.parametrize(
    "path", CALLER_WORKFLOWS, ids=lambda p: str(p.relative_to(REPO_ROOT))
)
def test_prepare_release_forwards_dry_run_to_extension(path: Path) -> None:
    """dry-run is forwarded so consumer extensions can honor it."""
    _, ext_job = _extension_job(_load(path))
    passed = ext_job.get("with") or {}
    assert "dry_run" in passed, "the extension call must forward dry_run"


@pytest.mark.parametrize(
    "path", CALLER_WORKFLOWS, ids=lambda p: str(p.relative_to(REPO_ROOT))
)
def test_extension_failure_is_covered_by_rollback(path: Path) -> None:
    """A rollback job watches the extension, so its failure deletes the branch."""
    doc = _load(path)
    ext_name, _ = _extension_job(doc)
    rollback_jobs = [
        name
        for name, job in _jobs(doc).items()
        if isinstance(job, dict)
        and ext_name in _needs(job)
        and "failure" in str(job.get("if", ""))
    ]
    assert rollback_jobs, (
        "a rollback job must list the extension in `needs` and trigger on its "
        "failure, so an extension failure rolls back the partial release branch"
    )


@pytest.mark.parametrize(
    "path", CALLER_WORKFLOWS, ids=lambda p: str(p.relative_to(REPO_ROOT))
)
def test_rollback_fires_on_phase_cancellation(path: Path) -> None:
    """Cancelling a run after the freeze commit rolls back like a failure (#1078).

    ``needs.<job>.result == 'failure'`` alone skips the rollback when the run is
    CANCELLED mid-phase, stranding the partial ``release/X.Y.Z`` branch and the
    freeze commit on dev. The guard must (a) keep ``always()`` so GitHub even
    evaluates the job after a cancellation, and (b) match
    ``result == 'cancelled'`` for every phase job it watches.
    """
    doc = _load(path)
    ext_name, _ = _extension_job(doc)
    branch_name, _ = _job_with_step_run(doc, "git/refs")
    pr_name, _ = _job_with_step_run(doc, "gh pr create")
    assert ext_name and branch_name and pr_name

    rollback_ifs = [
        str(job.get("if", ""))
        for job in _jobs(doc).values()
        if isinstance(job, dict)
        and ext_name in _needs(job)
        and "failure" in str(job.get("if", ""))
    ]
    assert rollback_ifs, "could not locate the rollback job"
    cond = rollback_ifs[0]
    assert "always()" in cond, (
        "the rollback guard needs always() to be evaluated at all after a "
        "workflow cancellation"
    )
    for phase in (branch_name, ext_name, pr_name):
        assert f"needs.{phase}.result == 'cancelled'" in cond, (
            f"the rollback guard must also fire when the `{phase}` job is "
            "cancelled, or a cancelled run strands the partial release branch "
            "and the freeze commit on dev (#1078)"
        )


# --------------------------------------------------------------------------- #
# Devkit dogfooding: the sync_manifest step moves into devkit's own hook
# --------------------------------------------------------------------------- #


def test_devkit_open_pr_needs_no_toolchain() -> None:
    """Devkit's open-pr job runs on a bare checkout — no setup-env (#1079).

    The job's only real work is `gh pr create` (gh ships preinstalled on
    GitHub-hosted runners), yet it stood up the full setup-env composite
    (Nix + `uv sync`) on the release critical path just to reach the
    `uv run retry` wrapper. Retries come from sourcing the canonical bash
    helper (.github/scripts/retry.sh) instead, so the job must invoke no
    local action and no `uv run`.
    """
    doc = _load(DEVKIT_PREPARE)
    pr_name, pr_job = _job_with_step_run(doc, "gh pr create")
    assert pr_name is not None, "could not locate the draft-PR-opening job"

    local_actions = [
        str(s.get("uses"))
        for s in (pr_job.get("steps") or [])
        if isinstance(s, dict) and str(s.get("uses", "")).startswith("./")
    ]
    assert not local_actions, (
        f"devkit's `{pr_name}` job must not invoke local composite actions "
        f"(found {local_actions}): a bare checkout plus the preinstalled gh "
        "CLI suffices to open the draft PR (#1079)"
    )
    steps_text = _job_steps_text(pr_job)
    assert "uv run" not in steps_text, (
        f"devkit's `{pr_name}` job must not depend on the uv environment; "
        "source .github/scripts/retry.sh for retries instead (#1079)"
    )
    assert "retry" in steps_text, (
        f"devkit's `{pr_name}` job must keep retrying the gh call "
        "(canonical bash retry helper)"
    )


def test_devkit_prepare_release_no_longer_syncs_manifest_inline() -> None:
    """Devkit's prepare-release.yml is scaffold-shaped: no hardcoded sync step."""
    assert "sync_manifest.py" not in DEVKIT_PREPARE.read_text(encoding="utf-8"), (
        "the sync_manifest.py divergence must move out of prepare-release.yml "
        "into devkit's own prepare-release-extension.yml (#1059)"
    )


def test_devkit_extension_implements_manifest_sync() -> None:
    """Devkit's own hook implements the manifest sync it removed from prepare."""
    assert DEVKIT_EXTENSION.is_file(), (
        "devkit must ship its own prepare-release-extension.yml"
    )
    assert "sync_manifest.py sync" in DEVKIT_EXTENSION.read_text(encoding="utf-8"), (
        "devkit's hook must run the workspace manifest sync on the release branch"
    )


# --------------------------------------------------------------------------- #
# Devkit dogfooding: dev-side mirror reconciliation (#1059)
#
# The freeze commit is scaffold-verbatim (root CHANGELOG.md only), so after
# every prepare, dev's synced mirror (assets/workspace/.devcontainer/CHANGELOG.md)
# is stale until reconciled — a red sync-manifest hook on every dev PR during
# the release window. Devkit's extension closes that drift by committing the
# reconciled mirror to dev, and its ORDERING is load-bearing for the rollback:
#
# * The dev-reconcile commit must be the LAST step of the job. Any extension
#   failure then implies the reconcile did NOT land, dev holds only the
#   root-only freeze, and the scaffold-shaped rollback's root-restore returns
#   dev to root(pre) == mirror(pre).
# * If the reconcile landed, the only remaining failure domain is open-pr; the
#   rollback's dev-advanced guard skips the root-restore, leaving dev at
#   root(frozen) == mirror(frozen) — also consistent.
#
# Either way, every failure path leaves dev's root+mirror consistent.
# --------------------------------------------------------------------------- #


def _devkit_extension_job() -> dict:
    doc = _load(DEVKIT_EXTENSION)
    jobs = _jobs(doc)
    assert len(jobs) == 1, "devkit's extension is expected to be a single job"
    return next(iter(jobs.values()))


def _commit_action_steps(job: dict) -> list[tuple[int, dict]]:
    """(index, step) of every vig-os/commit-action invocation in the job."""
    return [
        (i, s)
        for i, s in enumerate(job.get("steps") or [])
        if isinstance(s, dict) and "vig-os/commit-action" in str(s.get("uses", ""))
    ]


def test_devkit_extension_reconciles_dev_mirror() -> None:
    """The hook commits the reconciled changelog mirror back to dev.

    The freeze commit is scaffold-verbatim (root CHANGELOG.md only), so devkit's
    extension must close the resulting mirror drift on dev: a commit-action step
    targeting refs/heads/dev whose FILE_PATHS is exactly the mirror. The job
    must be gated on dry_run (no writes on a dry run).
    """
    job = _devkit_extension_job()
    dev_commits = [
        (i, s)
        for i, s in _commit_action_steps(job)
        if (s.get("env") or {}).get("TARGET_BRANCH") == "refs/heads/dev"
    ]
    assert dev_commits, (
        "devkit's extension must commit the reconciled mirror to refs/heads/dev"
    )
    _, step = dev_commits[0]
    assert (step.get("env") or {}).get("FILE_PATHS") == (
        "assets/workspace/.devcontainer/CHANGELOG.md"
    ), "the dev reconciliation commit must touch exactly the changelog mirror"
    assert "dry_run" in str(job.get("if", "")), (
        "the job holding the dev reconciliation must be gated on dry_run"
    )


def test_devkit_extension_dev_reconcile_is_last_step() -> None:
    """Ordering invariant the rollback analysis relies on (#1059).

    The dev reconciliation commit runs AFTER the release-branch commit and is
    the LAST step of the job: nothing failable follows it, so a rollback with
    the reconcile landed can only come from open-pr — the one path where
    skipping the root-restore is exactly what keeps dev consistent.
    """
    job = _devkit_extension_job()
    steps = job.get("steps") or []
    commits = _commit_action_steps(job)

    release_idx = [
        i
        for i, s in commits
        if "release_branch" in str((s.get("env") or {}).get("TARGET_BRANCH", ""))
    ]
    dev_idx = [
        i
        for i, s in commits
        if (s.get("env") or {}).get("TARGET_BRANCH") == "refs/heads/dev"
    ]
    assert release_idx and dev_idx, (
        "expected both a release-branch commit and a dev reconciliation commit"
    )
    assert release_idx[0] < dev_idx[0], (
        "the dev reconciliation must run after the release-branch commit"
    )
    assert dev_idx[0] == len(steps) - 1, (
        "the dev reconciliation commit must be the job's last step — anything "
        "after it would create a failure window in which the reconcile landed "
        "but the extension still fails, defeating the rollback analysis"
    )
