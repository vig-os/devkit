"""Workflow-shape + behavioral tests: the warn-only devkit-staleness job (#1497).

``scaffold-drift`` resolves its comparison image from the consumer's own
``DEVKIT_VERSION`` pin, so it compares the pin against itself — being behind is
invisible to it *by construction* (the field case sat two minor versions behind
with a green drift check). This job answers the other question — is the pin
behind the latest devkit release? — and never fails the build: the report is a
``::warning`` annotation plus a step-summary line, not a gate. Deliberately:

- **not** gated on ``DEVKIT_DRIFT_CHECK`` and needing no docker runner — a
  consumer who disabled the (expensive, containerized) drift gate still sees
  the (cheap, API-only) staleness report;
- **not** in the ``summary`` gate's ``needs`` — a warn-only job must never
  block a merge (the summary needs-set is pinned in
  ``test_workflow_summary_gate.py``).

Refs: #1497
"""

from __future__ import annotations

import os
import subprocess
from typing import TYPE_CHECKING

import pytest

from tests.workflow_scaffold import WORKFLOWS, jobs, load_workflow, needs_of

if TYPE_CHECKING:
    from pathlib import Path

JOB = "devkit-staleness"


def _job() -> dict:
    return jobs(load_workflow(WORKFLOWS / "ci.yml"))[JOB]


def _step_run() -> str:
    (step,) = [s for s in _job()["steps"] if "run" in s]
    return str(step["run"])


# ── shape ─────────────────────────────────────────────────────────────────────


def test_ci_declares_the_staleness_job() -> None:
    assert JOB in jobs(load_workflow(WORKFLOWS / "ci.yml"))


def test_staleness_is_pr_only_and_not_drift_gated() -> None:
    """PR-gated like drift, but immune to the DEVKIT_DRIFT_CHECK opt-out."""
    job = _job()
    assert "pull_request" in str(job["if"])
    assert "drift-check" not in str(job["if"])


def test_staleness_reads_the_resolved_pin() -> None:
    """The pin comes from resolve-toolchain (legacy-key handling included)."""
    job = _job()
    assert "resolve-toolchain" in needs_of(job)
    (step,) = [s for s in job["steps"] if "run" in s]
    assert step["env"]["PIN"] == "${{ needs.resolve-toolchain.outputs.image-tag }}"
    assert step["env"]["GH_TOKEN"] == "${{ github.token }}"


def test_staleness_warns_and_never_fails() -> None:
    run = _step_run()
    assert "::warning::" in run
    assert "::error::" not in run
    assert "exit 1" not in run, "the staleness report must never fail the build"


def test_staleness_stays_out_of_the_summary_gate() -> None:
    """Warn-only: a red/missing staleness job must never block a merge."""
    summary = jobs(load_workflow(WORKFLOWS / "ci.yml"))["summary"]
    assert JOB not in needs_of(summary)


# ── behavior: execute the real run block against a stubbed gh ─────────────────

RELEASES = ["1.8.0", "1.9.0", "1.10.0"]


def _run_staleness(
    tmp_path: Path, pin: str, gh_exit: int = 0
) -> subprocess.CompletedProcess:
    stub_dir = tmp_path / "bin"
    stub_dir.mkdir()
    gh = stub_dir / "gh"
    body = "\n".join(RELEASES)
    gh.write_text(
        f"#!/usr/bin/env bash\n[ {gh_exit} -ne 0 ] && exit {gh_exit}\nprintf '%s\\n' \"{body}\"\n"
    )
    gh.chmod(0o755)
    summary = tmp_path / "summary.md"
    summary.touch()
    return subprocess.run(
        ["bash", "-c", _step_run()],
        cwd=tmp_path,
        env={
            **os.environ,
            "PATH": f"{stub_dir}:{os.environ['PATH']}",
            "PIN": pin,
            "GH_TOKEN": "test-token",
            "GITHUB_STEP_SUMMARY": str(summary),
        },
        capture_output=True,
        text=True,
    )


def test_behind_pin_emits_a_counted_warning(tmp_path: Path) -> None:
    proc = _run_staleness(tmp_path, "1.8.0")
    assert proc.returncode == 0, proc.stderr
    assert "::warning::" in proc.stdout
    assert "2" in proc.stdout, f"expected the behind-count in:\n{proc.stdout}"
    assert "1.10.0" in proc.stdout
    assert "1.10.0" in (tmp_path / "summary.md").read_text()


def test_current_pin_is_silent(tmp_path: Path) -> None:
    proc = _run_staleness(tmp_path, "1.10.0")
    assert proc.returncode == 0, proc.stderr
    assert "::warning::" not in proc.stdout


@pytest.mark.parametrize("pin", ["", "1.8.0"])
def test_api_failure_and_empty_pin_never_fail(tmp_path: Path, pin: str) -> None:
    proc = _run_staleness(tmp_path, pin, gh_exit=1 if pin else 0)
    assert proc.returncode == 0, proc.stderr
    assert "::warning::" not in proc.stdout


def test_rc_pin_counts_as_behind_its_final(tmp_path: Path) -> None:
    """A 1.10.0-rc1 pin sorts before 1.10.0 and reports 1 release behind."""
    proc = _run_staleness(tmp_path, "1.10.0-rc1")
    assert proc.returncode == 0, proc.stderr
    assert "::warning::" in proc.stdout
