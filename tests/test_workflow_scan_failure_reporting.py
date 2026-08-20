"""Workflow-shape tests: every nightly-scan failure surfaces as a tracking issue.

``security-scan.yml`` opens a deduplicated tracking issue when the nightly scan
goes red (#965, #1237) — but the step was guarded on the *gate step's* outcome:

    if: ${{ failure() && steps.vulnix-gate.outcome == 'failure' }}

Any failure *before* ``vulnix-gate`` leaves that outcome empty (the step never
ran), so the guard was false and the run died silently — a red run in Actions
and nothing else. Scheduled runs execute from the default branch with no other
signal, which is the exact reason #965 restored the issue in the first place.

It fired for real on 2026-08-20: an expired ``.vulnixignore`` block failed the
*first* step of both matrix legs, hours before anyone noticed (#1547).

These are pure YAML-shape assertions (no ``nix``/``gh`` needed).

Refs: #1548
"""

from __future__ import annotations

from pathlib import Path

import yaml

# Repository root (tests/ -> repo root).
REPO_ROOT = Path(__file__).resolve().parent.parent

SECURITY_SCAN_WF = REPO_ROOT / ".github" / "workflows" / "security-scan.yml"

SCAN_JOB = "scan-nix-image"


def _job() -> dict:
    workflow = yaml.safe_load(SECURITY_SCAN_WF.read_text(encoding="utf-8"))
    return workflow["jobs"][SCAN_JOB]


def _reporting_step() -> dict:
    """The step that files the tracking issue (matched on what it runs)."""
    for step in _job()["steps"]:
        if "gh issue create" in step.get("run", ""):
            return step
    raise AssertionError("no tracking-issue step found in security-scan.yml")


def test_tracking_issue_fires_on_any_job_failure() -> None:
    """The guard is ``failure()`` alone — not ``failure()`` AND a gate verdict.

    Conditioning on ``steps.vulnix-gate.outcome`` scopes reporting to the one
    failure mode that happens *at* the gate, leaving every earlier step (the
    register validation, the closure build, the vulnix run itself) silent.
    """
    condition = str(_reporting_step().get("if", ""))

    assert "failure()" in condition, (
        "the tracking-issue step must run on failure() — otherwise a red "
        "nightly scan surfaces nowhere (#965)"
    )
    assert "vulnix-gate.outcome" not in condition, (
        "the tracking-issue step must NOT be gated on `steps.vulnix-gate.outcome`: "
        "a failure BEFORE the gate leaves that outcome empty, so the run dies "
        "silently — no issue, no signal (#1548)"
    )


def test_pre_gate_failures_get_their_own_dedup_title() -> None:
    """Two failure classes, two titles, so each dedups independently per ref.

    A pre-gate failure is not "unexcepted HIGH/CRITICAL findings" — the scan
    never produced a verdict at all. Filing it under the gate's title would
    both misdescribe it and let one class suppress the other's issue.
    """
    script = _reporting_step()["run"]

    assert "GATE_OUTCOME" in script or "steps.vulnix-gate.outcome" in script, (
        "the reporting step must branch on the gate outcome to tell a gate "
        "failure from a pre-gate one (#1548)"
    )
    assert "unexcepted HIGH/CRITICAL vulnix findings" in script, (
        "the gate-failure title must survive: the open issues filed under it "
        "dedup against that exact string (#965, #1237)"
    )
    assert "before the vulnix gate" in script, (
        "a pre-gate failure needs its own distinct title (#1548)"
    )


def test_pre_gate_report_names_the_failing_step() -> None:
    """The issue body names the failing step, read off the run's job records.

    "Something before the gate failed" is not actionable; "the register
    validation failed" is. The same lookup the devkit-upgrade report uses
    (#1530) needs the ``actions: read`` grant on this job.
    """
    job = _job()
    script = _reporting_step()["run"]

    assert job.get("permissions", {}).get("actions") == "read", (
        "naming the failing step reads this run's own job records, which needs "
        "`actions: read` on the job (#1548)"
    )
    assert "/jobs" in script, (
        "the pre-gate body must name the failing step from the run's job "
        "records rather than leaving triage to open the log (#1548)"
    )
