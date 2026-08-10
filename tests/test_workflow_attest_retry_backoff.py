"""Workflow-shape tests: the attestation retry envelope survives a Rekor outage.

Issue #1399 (follow-up from #1390): 1.7.0-rc1 and rc2 both died in ``publish``
when the public-good Sigstore transparency log timed out. The action already
retries internally -- ``@actions/attest`` hardcodes ``DEFAULT_TIMEOUT = 10000``
and ``DEFAULT_RETRIES = 3`` into the Rekor witness, giving 4 attempts at
0/+1/+2/+4s, roughly 47s per action step -- and exposes no input to widen that.
The outer retry in this workflow is therefore the only lever we control, and a
fixed ``sleep 30`` brought the whole envelope to about 2 minutes, shorter than a
typical Sigstore incident.

The fix keeps exactly two attempts per attestation (GitHub Actions cannot loop
over a ``uses:`` step, so more attempts would mean more copy-paste) and instead
makes the wait between them adaptive: poll the transparency log until it answers
again, up to a minutes-scale deadline.

Refs: #1399
"""

from __future__ import annotations

from pathlib import Path

import yaml

# Repository root (tests/ -> repo root).
REPO_ROOT = Path(__file__).resolve().parent.parent

RELEASE_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "release.yml"
WAIT_SCRIPT = REPO_ROOT / ".github" / "scripts" / "wait-for-rekor.sh"

# Each attestation is a triple: attempt (soft-failing) -> wait -> retry (hard).
# Keyed by the id of the first attempt.
ATTEMPT_IDS = ("attest_provenance", "attest_sbom")

# The outer wait must be measured in minutes: a Sigstore incident outlasts the
# ~47s the action already spends on its own internal retries.
MINIMUM_WAIT_SECONDS = 300


def _publish_steps() -> list[dict]:
    workflow = yaml.safe_load(RELEASE_WORKFLOW.read_text(encoding="utf-8"))
    return workflow["jobs"]["publish"]["steps"]


def _triple(attempt_id: str) -> tuple[dict, dict, dict]:
    """Return the (attempt, wait, retry) steps for one attestation."""
    steps = _publish_steps()
    index = next(i for i, step in enumerate(steps) if step.get("id") == attempt_id)
    attempt, wait, retry = steps[index : index + 3]
    return attempt, wait, retry


def test_wait_script_exists() -> None:
    """The shared wait helper is what both attestations call."""
    assert WAIT_SCRIPT.is_file(), (
        f"{WAIT_SCRIPT.relative_to(REPO_ROOT)} must exist: both attestation "
        "waits source their backoff from it (#1399)"
    )


def test_attestation_waits_poll_the_transparency_log() -> None:
    """No fixed `sleep` — the wait probes Rekor until it recovers."""
    for attempt_id in ATTEMPT_IDS:
        _, wait, _ = _triple(attempt_id)
        run = wait.get("run", "")
        assert "wait-for-rekor.sh" in run, (
            f"the wait after {attempt_id} must call wait-for-rekor.sh, not "
            f"sleep a fixed interval; got {run!r} (#1399)"
        )
        assert "sleep" not in run, (
            f"the wait after {attempt_id} must not hardcode a sleep: a fixed "
            "30s gap is shorter than a Sigstore incident (#1399)"
        )


def test_attestation_waits_span_minutes() -> None:
    """The deadline is minutes-scale, not the old 30 seconds."""
    for attempt_id in ATTEMPT_IDS:
        _, wait, _ = _triple(attempt_id)
        deadline = int(wait.get("env", {})["REKOR_WAIT_SECONDS"])
        assert deadline >= MINIMUM_WAIT_SECONDS, (
            f"the wait after {attempt_id} allows only {deadline}s; a Rekor "
            f"incident needs at least {MINIMUM_WAIT_SECONDS}s of cover (#1399)"
        )


def test_wait_runs_only_when_the_first_attempt_failed() -> None:
    """The happy path stays fast: no wait when attempt 1 succeeded."""
    for attempt_id in ATTEMPT_IDS:
        _, wait, retry = _triple(attempt_id)
        guard = f"steps.{attempt_id}.outcome == 'failure'"
        for step in (wait, retry):
            assert guard in step.get("if", ""), (
                f"{step.get('name')!r} must be guarded by {guard!r} so a green "
                "first attempt costs nothing (#1399)"
            )


def test_first_attempt_is_soft_and_the_retry_is_final() -> None:
    """Attempt 1 may fail quietly; the retry must still fail the job."""
    for attempt_id in ATTEMPT_IDS:
        attempt, _, retry = _triple(attempt_id)
        assert attempt.get("continue-on-error") is True, (
            f"{attempt_id} must be continue-on-error so the wait can run (#1399)"
        )
        assert "continue-on-error" not in retry, (
            f"the retry after {attempt_id} must fail the job: a release must "
            "never be published with a silently skipped attestation (#1399)"
        )


def test_retry_attests_exactly_what_the_first_attempt_did() -> None:
    """Retry and attempt stay in lockstep — same action, same subject."""
    for attempt_id in ATTEMPT_IDS:
        attempt, _, retry = _triple(attempt_id)
        assert retry["uses"] == attempt["uses"], (
            f"the retry after {attempt_id} must use the same pinned action"
        )
        assert retry["with"] == attempt["with"], (
            f"the retry after {attempt_id} must attest the same subject"
        )


def test_no_third_copy_of_the_attestation_steps() -> None:
    """Widening the envelope must not mean more copy-pasted `uses:` blocks."""
    attest_steps = [
        step
        for step in _publish_steps()
        if str(step.get("uses", "")).startswith("actions/attest")
    ]
    assert len(attest_steps) == 2 * len(ATTEMPT_IDS), (
        "expected exactly one attempt and one retry per attestation; extra "
        "copies mean the backoff was widened by duplication instead of by "
        "polling (#1399)"
    )
