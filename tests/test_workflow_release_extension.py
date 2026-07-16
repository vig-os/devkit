"""Workflow-shape tests: the release extension seam's GITHUB_TOKEN ceiling.

Issue #1144: ``release.yml`` calls the ``release-extension.yml`` consumer seam,
but the ``extension`` caller job declared no ``permissions:`` block, so the
called reusable workflow ran under the caller's workflow-level default
(``contents: read, packages: read``). GitHub never lets a called reusable
workflow *elevate* the caller's ``GITHUB_TOKEN`` — the callee's own
``permissions:`` can only downgrade. So any write-scoped extension step was
silently denied: ``actions/attest-build-provenance`` (needs ``id-token: write`` +
``attestations: write``) and even the GHCR-publish example the docs already ship
(needs ``packages: write``).

Fix (option A): the managed ``extension`` job in ``release.yml`` grants a
documented broader *ceiling* — ``contents: read``, ``packages: write``,
``id-token: write``, ``attestations: write``. This is the maximum the seam can
reach, not a default grant: the consumer-owned ``release-extension.yml`` still
declares its own (lower) permissions per job, so the shipped default no-op stays
read-only (deny-by-default preserved). A consumer opts a job in by raising its
permissions up to this ceiling.

Refs: #1144
"""

from __future__ import annotations

from pathlib import Path

import yaml

# Repository root (tests/ -> repo root) and the consumer scaffold tree.
REPO_ROOT = Path(__file__).resolve().parent.parent
WORKSPACE = REPO_ROOT / "assets" / "workspace"

SCAFFOLD_RELEASE = WORKSPACE / ".github" / "workflows" / "release.yml"
SCAFFOLD_EXTENSION = WORKSPACE / ".github" / "workflows" / "release-extension.yml"

# The seam's documented permission ceiling (issue #1144). Every scope the
# documented extension tasks need — container/package publishing, keyless
# signing, build provenance attestation — plus read to check out the commit.
CEILING = {
    "contents": "read",
    "packages": "write",
    "id-token": "write",
    "attestations": "write",
}


def _load(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _jobs(doc: dict) -> dict:
    return doc.get("jobs") or {}


def _extension_job(doc: dict) -> tuple[str, dict] | tuple[None, None]:
    """The (name, job) that calls the release-extension reusable workflow."""
    for name, job in _jobs(doc).items():
        if isinstance(job, dict) and str(job.get("uses", "")).endswith(
            "release-extension.yml"
        ):
            return name, job
    return None, None


def test_scaffold_ships_release_extension() -> None:
    """The scaffold ships the read-only extension seam."""
    assert SCAFFOLD_EXTENSION.is_file(), (
        "assets/workspace/.github/workflows/release-extension.yml must exist"
    )


def test_release_extension_caller_grants_documented_ceiling() -> None:
    """The ``extension`` caller job raises the seam's token ceiling (#1144)."""
    name, job = _extension_job(_load(SCAFFOLD_RELEASE))
    assert name is not None, "release.yml must call release-extension.yml as a job"
    perms = job.get("permissions")
    assert isinstance(perms, dict), (
        "the extension caller job must declare a permissions block so the seam "
        "can reach write scopes (a called workflow cannot elevate the caller)"
    )
    for scope, level in CEILING.items():
        assert perms.get(scope) == level, (
            f"extension job ceiling must grant {scope}: {level} (got "
            f"{perms.get(scope)!r})"
        )


def test_release_extension_default_stays_readonly() -> None:
    """The shipped default no-op keeps deny-by-default (ceiling ≠ grant)."""
    doc = _load(SCAFFOLD_EXTENSION)
    perms = doc.get("permissions") or {}
    assert perms.get("contents") == "read", (
        "the default no-op extension must stay read-only at the workflow level"
    )
    assert "packages" not in perms and "attestations" not in perms, (
        "the default no-op must not request write scopes — a consumer opts in "
        "per job up to the release.yml ceiling"
    )
