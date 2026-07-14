"""Workflow-shape tests: security-scan jobs must skip on private repositories.

Issue #1039: the scaffold ships ``codeql.yml`` and ``scorecard.yml``
unconditionally. On a **private** repo neither can ever succeed — CodeQL needs
GitHub Advanced Security (unavailable on Free-plan private repos) and OpenSSF
Scorecard is public-only — so the first private consumer would scaffold two
permanently red workflows.

The fix gates each analysis job with ``if: ${{ !github.event.repository.private
}}`` at the *job* level, so a private repo yields a skipped (neutral) run rather
than a failing one, and a repo later flipped public starts scanning
automatically with no re-scaffold. ``github.event.repository`` (and its
``private`` field) is populated on every trigger these workflows declare —
``pull_request``, ``push``, and (since the 2022-09-27 Actions change that added
repository info to scheduled-run payloads) ``schedule`` — so the guard is valid
and meaningful on all of them.

These assertions pin that invariant for both copies of each workflow: the
devkit's own (a public no-op) and the manifest-synced scaffold shipped to
consumers.

Refs: #1039
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

# Repository root (tests/ -> repo root).
REPO_ROOT = Path(__file__).resolve().parent.parent

# The guard skips the job whenever the repository is private.
EXPECTED_GUARD = "${{ !github.event.repository.private }}"

# (workflow path, analysis job key); each is checked in both the devkit's own
# copy and the manifest-synced scaffold copy under assets/workspace/.
_WORKFLOWS = [
    (".github/workflows/codeql.yml", "analyze"),
    (".github/workflows/scorecard.yml", "analysis"),
]
GUARDED_JOBS = [
    (REPO_ROOT / prefix / rel, job)
    for rel, job in _WORKFLOWS
    for prefix in (".", "assets/workspace")
]


def _load(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    ("path", "job"),
    GUARDED_JOBS,
    ids=lambda v: str(v.relative_to(REPO_ROOT)) if isinstance(v, Path) else v,
)
def test_scan_job_skips_on_private_repo(path: Path, job: str) -> None:
    """The analysis job is gated so private repos get a neutral (skipped) run."""
    workflow = _load(path)
    assert job in workflow["jobs"], f"{path} has no `{job}` job"
    guard = workflow["jobs"][job].get("if")
    assert guard == EXPECTED_GUARD, (
        f"{path} job `{job}` must be guarded with `if: {EXPECTED_GUARD}` so it "
        f"is skipped on private repos (CodeQL/Scorecard cannot succeed there); "
        f"found {guard!r}"
    )
