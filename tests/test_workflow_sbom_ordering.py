"""Workflow-shape tests for SBOM survival past a red vulnix gate.

The nightly ``security-scan.yml`` uploads its artifact with ``if: always()``
because, as that step's own comment says, "a red vulnix-gate is exactly when the
findings are needed". But the two steps that *produce* half of that artifact —
the image build and the CycloneDX SBOM generation — sat **after** the blocking
gate with no condition, so a red gate ended the job before they ran. The
artifact was therefore complete only on green runs and stripped on red ones,
the inverse of what triage needs (#1342).

The fix is ordering, not conditions: the SBOM steps move above the gate, leaving
``vulnix-gate`` as the job's last step and unambiguous verdict.

These are pure YAML-shape assertions (no ``nix``/``trivy`` needed).

Refs: #1342
"""

from __future__ import annotations

from pathlib import Path

import yaml

# Repository root (tests/ -> repo root).
REPO_ROOT = Path(__file__).resolve().parent.parent

SECURITY_SCAN_WF = REPO_ROOT / ".github" / "workflows" / "security-scan.yml"

SCAN_JOB = "scan-nix-image"


def _steps() -> list[dict]:
    workflow = yaml.safe_load(SECURITY_SCAN_WF.read_text(encoding="utf-8"))
    return workflow["jobs"][SCAN_JOB]["steps"]


def _index_of(steps: list[dict], predicate) -> int:
    """Position of the first step matching ``predicate`` (-1 when absent)."""
    for position, step in enumerate(steps):
        if predicate(step):
            return position
    return -1


def _is_gate(step: dict) -> bool:
    return step.get("id") == "vulnix-gate"


def _is_sbom_image_build(step: dict) -> bool:
    return "nix build .#devkitImage" in step.get("run", "")


def _is_sbom_generate(step: dict) -> bool:
    return step.get("with", {}).get("format") == "cyclonedx"


def _is_upload(step: dict) -> bool:
    return "upload-artifact" in step.get("uses", "")


def test_sbom_steps_precede_the_blocking_gate() -> None:
    """The SBOM producers run before the gate, so a red gate cannot skip them."""
    steps = _steps()

    gate = _index_of(steps, _is_gate)
    image_build = _index_of(steps, _is_sbom_image_build)
    sbom = _index_of(steps, _is_sbom_generate)

    assert gate != -1, "the vulnix-gate step is missing"
    assert image_build != -1, "the SBOM image-build step is missing"
    assert sbom != -1, "the CycloneDX SBOM step is missing"

    assert image_build < gate, (
        "the SBOM image build must run BEFORE the blocking vulnix gate — after it, "
        "a red gate ends the job and the artifact loses its SBOM exactly when it "
        "is needed for triage (#1342)"
    )
    assert sbom < gate, (
        "CycloneDX SBOM generation must run BEFORE the blocking vulnix gate (#1342)"
    )


def test_nothing_unconditioned_follows_the_gate() -> None:
    """Every step after the gate states its own run condition.

    Keeping the gate last preserves it as the job's unambiguous pass/fail
    signal. A step scheduled after it with no ``if:`` silently inherits the
    gate's outcome — the #1342 defect. The conditions themselves differ by
    intent: the upload and summary use ``always()``, while the tracking-issue
    step deliberately fires only on ``failure()``.
    """
    steps = _steps()
    gate = _index_of(steps, _is_gate)

    for step in steps[gate + 1 :]:
        assert "if" in step, (
            f"step {step.get('name')!r} follows the blocking gate with no `if:` "
            f"condition, so a red gate would silently skip it (#1342)"
        )


def test_gate_stays_blocking() -> None:
    """The gate must keep failing the job — the tracking automation depends on it.

    ``security-scan.yml`` opens a deduplicated tracking issue keyed on
    ``vulnix-gate.outcome == 'failure'`` (#965, #1237), so a fix that softened
    the gate to keep the SBOM steps reachable would silently disable the
    nightly's issue-opening path.
    """
    steps = _steps()
    gate = steps[_index_of(steps, _is_gate)]

    assert not gate.get("continue-on-error", False), (
        "the vulnix gate must stay blocking (#639)"
    )
    assert "if" not in gate, "the vulnix gate must run unconditionally (#639)"


def test_upload_still_runs_on_a_red_gate() -> None:
    """The artifact upload keeps its `if: always()` guard."""
    steps = _steps()
    upload = steps[_index_of(steps, _is_upload)]

    assert "always()" in str(upload.get("if", "")), (
        "the artifact upload must stay `if: always()` — a red gate is when the "
        "findings and SBOM are most needed"
    )
