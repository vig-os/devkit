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


# --------------------------------------------------------------------------- #
# Devkit dogfooding: the sync_manifest step moves into devkit's own hook
# --------------------------------------------------------------------------- #


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
