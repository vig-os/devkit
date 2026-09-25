"""Workflow-shape tests: the PR-CI security report is SBOM-derived.

Issue #1701: ``Security Scan`` sat on the run's critical path because its two
Trivy steps each re-parsed the same 1.5 GiB image tarball — the walk, not the
DB pull, is the cost. The fix generates the CycloneDX SBOM **first** and then
reports over it (``scan-type: sbom``), so the image is parsed once; the same
pattern the nightly ``security-scan.yml`` already uses.

Two invariants are easy to undo silently and are therefore pinned here:

- **Order and wiring.** Restoring the image-mode report (or moving the SBOM
  step back below it) reintroduces the second image parse. The report's
  ``scan-ref`` must be exactly the SBOM step's ``output``, or it scans a file
  that does not exist yet — Trivy reports *nothing* rather than failing, since
  the report is deliberately non-blocking (``exit-code: 0``).
- **Where the register check lives.** ``check-expirations`` is blocking and must
  keep running in PR CI (an acceptance criterion of #1701), but it needs the Nix
  shell, and keeping it in ``security-scan`` forces a ``setup-env`` onto a job
  that otherwise needs neither Nix nor ``uv``. It moved to ``python-security``,
  which already sets up the environment and does not wait on ``build-image``.

These are pure YAML-shape assertions (no ``nix``/``trivy`` needed). The finding
sets of an image-mode and an SBOM-mode scan were compared out of band on the
same tarball; a test cannot assert that.

Refs: #1701
"""

from __future__ import annotations

from pathlib import Path

from tests.workflow_scaffold import load_workflow, steps_of_job

# Repository root (tests/ -> repo root).
REPO_ROOT = Path(__file__).resolve().parent.parent
DEVKIT_CI = REPO_ROOT / ".github" / "workflows" / "ci.yml"

SCAN_JOB = "security-scan"
PYTHON_JOB = "python-security"

REGISTER_CHECK = "check-expirations .trivyignore .vulnixignore"


def _steps(job: str) -> list[dict]:
    return steps_of_job(load_workflow(DEVKIT_CI), job)


def _register_checks(steps: list[dict]) -> list[dict]:
    return [s for s in steps if REGISTER_CHECK in str(s.get("run", ""))]


def _index_of(steps: list[dict], predicate) -> int:
    """Position of the first step matching ``predicate`` (-1 when absent)."""
    for position, step in enumerate(steps):
        if predicate(step):
            return position
    return -1


def _step_matching(steps: list[dict], predicate, what: str) -> dict:
    """The first step matching ``predicate``, or a clear failure."""
    position = _index_of(steps, predicate)
    assert position != -1, f"the {what} step is missing"
    return steps[position]


def _is_sbom_generate(step: dict) -> bool:
    return step.get("with", {}).get("format") == "cyclonedx"


def _is_sbom_report(step: dict) -> bool:
    return step.get("with", {}).get("scan-type") == "sbom"


def _is_upload(step: dict) -> bool:
    return "upload-artifact" in str(step.get("uses", ""))


def test_register_check_runs_in_python_security() -> None:
    """The blocking register-expiry check keeps a home in PR CI — one of them."""
    python_security = _register_checks(_steps(PYTHON_JOB))
    assert len(python_security) == 1, (
        f"expected exactly one {REGISTER_CHECK!r} step in {PYTHON_JOB!r}, "
        f"found {len(python_security)} — the .trivyignore/.vulnixignore expiry "
        f"validation must keep running (blocking) in PR CI (#1701)"
    )

    scan = _register_checks(_steps(SCAN_JOB))
    assert not scan, (
        f"{SCAN_JOB!r} must not run {REGISTER_CHECK!r} — it moved to "
        f"{PYTHON_JOB!r} so this job needs no Nix/uv setup at all (#1701)"
    )


def test_security_scan_needs_no_nix_environment() -> None:
    """Nothing left in ``security-scan`` depends on the Nix shell.

    The trivy action ships its own binary and ``download-artifact`` is pure
    JavaScript, so a reinstated ``setup-env`` would be 42 s of pure critical
    path.
    """
    for step in _steps(SCAN_JOB):
        assert "setup-env" not in str(step.get("uses", "")), (
            f"step {step.get('name')!r} sets up the Nix environment in "
            f"{SCAN_JOB!r}, which no longer needs it (#1701)"
        )
        assert "uv run" not in str(step.get("run", "")), (
            f"step {step.get('name')!r} runs `uv run` in {SCAN_JOB!r}, which has "
            f"no Nix/uv setup — move it to a job that does (#1701)"
        )


def test_report_scans_the_sbom_generated_before_it() -> None:
    """One image parse: the SBOM comes first, the report reads that file."""
    steps = _steps(SCAN_JOB)

    sbom = _index_of(steps, _is_sbom_generate)
    report = _index_of(steps, _is_sbom_report)

    assert sbom != -1, "the CycloneDX SBOM step is missing"
    assert report != -1, (
        "the vulnerability report must run in SBOM mode (`scan-type: sbom`) — "
        "an image-mode report re-parses the 1.5 GiB tarball a second time (#1701)"
    )
    assert sbom < report, (
        "the SBOM must be generated BEFORE the report that scans it (#1701)"
    )

    output = steps[sbom]["with"]["output"]
    assert steps[report]["with"]["scan-ref"] == output, (
        f"the report's `scan-ref` must be the SBOM step's `output` ({output!r}); "
        f"a mismatch makes Trivy scan a missing file and report nothing, "
        f"silently, because the step is non-blocking (#1701)"
    )


def test_report_stays_non_blocking_and_register_filtered() -> None:
    """Severity tiers, the exception register and exit-code 0 are unchanged."""
    report = _step_matching(_steps(SCAN_JOB), _is_sbom_report, "SBOM-mode report")
    with_ = report["with"]

    assert set(str(with_["severity"]).split(",")) == {"HIGH", "CRITICAL", "MEDIUM"}
    assert str(with_["exit-code"]) == "0", (
        "the PR-CI report is awareness only — the authoritative CVE gate is the "
        "nightly vulnix lane in security-scan.yml (#642)"
    )
    assert with_["trivyignores"] == ".trivyignore"


def test_sbom_artifact_keeps_its_name_and_content() -> None:
    """The published artifact is unchanged by the reordering (#1701)."""
    steps = _steps(SCAN_JOB)
    upload = _step_matching(steps, _is_upload, "SBOM upload")
    sbom = _step_matching(steps, _is_sbom_generate, "CycloneDX SBOM")

    assert str(upload["with"]["name"]).startswith("sbom-"), (
        "the SBOM artifact name must keep its `sbom-<version>-<arch>` shape"
    )
    assert str(upload["with"]["path"]).strip() == sbom["with"]["output"], (
        "the upload must publish the file the SBOM step writes"
    )
    assert "always()" in str(upload.get("if", "")), (
        "the SBOM upload keeps its `if: always()` guard"
    )
