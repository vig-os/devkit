"""Workflow-shape tests: the CI extension seam (#1761).

A fourth consumer-owned seam, alongside the three release-process ones
(``release-extension.yml``, ``prepare-release-extension.yml``,
``publish-release-extension.yml``): ``ci-extension.yml``, a preserved,
no-op-by-default ``workflow_call`` stub that the managed ``ci.yml`` calls as a
job named ``extension``, aggregated by the ``summary`` (``CI Summary``) gate
exactly like every other lane.

Design comment (5931690653) proposed gating the call behind a
``DEVKIT_CI_EXTENSION`` knob; the approved amendments (5931764358) reject that:
a knob reintroduces the exact silent-skip failure this issue exists to
prevent, so ``ci.yml`` calls the extension job **unconditionally** — no
``resolve-toolchain`` output, no ``if:`` gate. The amendments also require
every ``workflow_call`` input to be ``required: false`` (the stub is a
preserved, consumer-owned contract; a later required input would break every
existing copy) and the stub's ``runs-on`` to resolve from
``fromJSON(inputs.runner-json)`` rather than a literal label (actionlint
1.7.12 does not know ``ubuntu-26.04``, so a literal fails the moment a
consumer starts editing the stub).

Refs: #1761
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from scripts.sync_manifest import load_preserve_files
from tests.workflow_scaffold import (
    INIT_WORKSPACE,
    REPO_ROOT,
    WORKFLOWS,
    cached_tree,
    load_workflow,
    needs_of,
    on_block,
    scaffold,
)

if TYPE_CHECKING:
    from pathlib import Path

REL = ".github/workflows/ci-extension.yml"
CI = WORKFLOWS / "ci.yml"
SEAM = WORKFLOWS / "ci-extension.yml"
SMOKE_SEAM = (
    REPO_ROOT / "assets" / "smoke-test" / ".github" / "workflows" / "ci-extension.yml"
)

# The contract inputs the issue's approved design specifies, hyphenated to
# match ci.yml's own resolve-toolchain output naming (mode, image, image-tag,
# runner-json) rather than release.yml's underscore convention — a different
# caller, a different established convention.
CONTRACT_INPUTS = {"mode", "image", "image-tag", "runner-json"}


def _ci_doc() -> dict:
    return load_workflow(CI)


def _extension_caller_job() -> dict:
    return _ci_doc()["jobs"]["extension"]


def _seam_doc() -> dict:
    return load_workflow(SEAM)


# ── ci.yml wiring ───────────────────────────────────────────────────────────


def test_extension_job_calls_the_seam_unconditionally() -> None:
    """No knob, no `if:` — the extension job always runs (amendment 1)."""
    job = _extension_caller_job()
    assert job["uses"] == "./.github/workflows/ci-extension.yml"
    assert needs_of(job) == ["resolve-toolchain"]
    assert "if" not in job, (
        "the extension job must not be gated behind a knob — amendment 1 "
        "rejects DEVKIT_CI_EXTENSION precisely because a skip-by-default "
        "knob lets a consumer forget to flip it"
    )


def test_extension_job_passes_the_resolved_toolchain_context() -> None:
    job = _extension_caller_job()
    with_block = job["with"]
    assert with_block["mode"] == "${{ needs.resolve-toolchain.outputs.mode }}"
    assert with_block["image"] == "${{ needs.resolve-toolchain.outputs.image }}"
    assert with_block["image-tag"] == "${{ needs.resolve-toolchain.outputs.image-tag }}"
    assert with_block["runner-json"] == (
        "${{ needs.resolve-toolchain.outputs.runner-json }}"
    )
    assert job["secrets"] == "inherit"


def test_extension_job_permissions_stay_read_only() -> None:
    """No elevation beyond the rest of ci.yml — the amendments keep it read-only."""
    job = _extension_caller_job()
    perms = job.get("permissions")
    assert perms == {"contents": "read", "packages": "read"}


def test_resolve_toolchain_gains_no_ci_extension_output() -> None:
    """Amendment 1: no resolve-toolchain output change is needed for this seam."""
    outputs = _ci_doc()["jobs"]["resolve-toolchain"].get("outputs") or {}
    assert "ci-extension" not in outputs


# ── the preserved stub ──────────────────────────────────────────────────────


def test_seam_every_input_is_optional() -> None:
    """Amendment 2: every workflow_call input is required: false."""
    inputs = on_block(_seam_doc())["workflow_call"]["inputs"]
    assert set(inputs) == CONTRACT_INPUTS
    for name, spec in inputs.items():
        assert spec.get("required") is False, (
            f"input {name!r} must be required: false — a later devkit release "
            "adding a required input would break every preserved consumer copy"
        )


def test_seam_runner_resolves_from_runner_json_not_a_literal_label() -> None:
    """Amendment 3: fromJSON(inputs.runner-json), never a literal `ubuntu-26.04`."""
    job = _seam_doc()["jobs"]["extension"]
    assert job["runs-on"] == "${{ fromJSON(inputs.runner-json) }}"


def test_seam_runner_json_input_has_a_safe_default() -> None:
    """A direct call (no caller-supplied runner-json) must still resolve."""
    inputs = on_block(_seam_doc())["workflow_call"]["inputs"]
    default = inputs["runner-json"].get("default")
    assert default, "runner-json needs a default so fromJSON never sees empty input"
    import json

    parsed = json.loads(default)
    assert isinstance(parsed, list) and parsed, "default must be a non-empty JSON array"


def test_seam_default_is_a_no_op() -> None:
    doc = _seam_doc()
    assert doc["permissions"] == {"contents": "read"}
    steps = doc["jobs"]["extension"]["steps"]
    run_text = "\n".join(str(s.get("run", "")) for s in steps)
    assert "No CI extension configured" in run_text


# ── scaffold / preserve ─────────────────────────────────────────────────────


def test_seam_is_a_preserved_consumer_seed() -> None:
    assert REL in load_preserve_files(INIT_WORKSPACE)


def test_scaffold_ships_the_seed() -> None:
    shipped = cached_tree() / REL
    assert shipped.is_file()
    assert "Seeded by vigOS devkit" in shipped.read_text(encoding="utf-8")


def test_upgrade_preserves_a_consumer_implementation(tmp_path: Path) -> None:
    seed = tmp_path / "seed"
    (seed / ".github" / "workflows").mkdir(parents=True)
    custom = "name: CI Extension\n# consumer implementation\n"
    (seed / REL).write_text(custom, encoding="utf-8")
    proc = scaffold(tmp_path, seed=seed, name="upgraded")
    assert proc.returncode == 0, proc.stderr
    assert (tmp_path / "upgraded" / REL).read_text(encoding="utf-8") == custom


# ── smoke-test overlay (amendment 4) ────────────────────────────────────────


def test_smoke_test_overlay_ships_a_real_non_empty_extension() -> None:
    """The release train must live-prove the seam, not just the no-op default."""
    assert SMOKE_SEAM.is_file()
    doc = load_workflow(SMOKE_SEAM)
    run_text = "\n".join(
        str(s.get("run", "")) for s in doc["jobs"]["extension"]["steps"]
    )
    assert "No CI extension configured" not in run_text, (
        "smoke-test's ci-extension.yml must be a real check, not the shipped no-op"
    )
    assert run_text.strip(), "smoke-test's extension must actually run something"
