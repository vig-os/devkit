"""Client-ID App credentials in the sync-issues workflows (#1365).

The 2026-08-07 credential audit consolidates every GitHub-App secret pair to
**Client ID only** — nothing in the auth path is numerically load-bearing. The
``vig-os/sync-issues-action`` step was the last consumer forcing the numeric
``COMMIT_APP_ID`` org secret to stay alive, purely through its input name;
v0.5.0 (vig-os/sync-issues-action#168) adds the preferred ``client-id`` input.

Both copies of the workflow — devkit's own and the scaffold stamped into every
consumer — must pass ``COMMIT_APP_CLIENT_ID`` through ``client-id`` and never
reference the numeric secret again, so the org secrets can be retired (#1366).
The exo-pet org never had a ``COMMIT_APP_ID`` secret at all, so the stamped
``app-id`` line was already passing an empty value there.

Refs: #1365
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent

# Both copies: devkit's own workflow and the scaffold shipped to consumers
# (intentionally decoupled files, same credential contract).
SYNC_WORKFLOWS = [
    REPO_ROOT / ".github" / "workflows" / "sync-issues.yml",
    REPO_ROOT / "assets" / "workspace" / ".github" / "workflows" / "sync-issues.yml",
]

_IDS = [str(p.relative_to(REPO_ROOT)) for p in SYNC_WORKFLOWS]


def _sync_action_steps(path: Path) -> list[dict]:
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    steps: list[dict] = []
    for job in (doc.get("jobs") or {}).values():
        for step in job.get("steps", []) or []:
            if "sync-issues-action" in str(step.get("uses", "")):
                steps.append(step)
    return steps


@pytest.mark.parametrize("path", SYNC_WORKFLOWS, ids=_IDS)
def test_sync_step_authenticates_via_client_id(path: Path) -> None:
    """The action step passes COMMIT_APP_CLIENT_ID via client-id, never app-id."""
    steps = _sync_action_steps(path)
    assert steps, f"{path} has no sync-issues-action step"
    for step in steps:
        with_block = step.get("with", {})
        assert with_block.get("client-id") == ("${{ secrets.COMMIT_APP_CLIENT_ID }}")
        # The deprecated numeric input must be gone, not merely superseded:
        # the action errors when both are set.
        assert "app-id" not in with_block


@pytest.mark.parametrize("path", SYNC_WORKFLOWS, ids=_IDS)
def test_action_pin_is_sha_pinned_client_id_capable_release(path: Path) -> None:
    """The pin is a full SHA of a release that has the client-id input (>= 0.5.0)."""
    match = re.search(
        r"sync-issues-action@([0-9a-f]{40})\s+#\s*v(\d+)\.(\d+)",
        path.read_text(encoding="utf-8"),
    )
    assert match, (
        f"{path}: sync-issues-action must be SHA-pinned with a version comment"
    )
    major, minor = int(match.group(2)), int(match.group(3))
    assert (major, minor) >= (0, 5), (
        f"{path}: pinned sync-issues-action v{major}.{minor} predates the "
        "client-id input (vig-os/sync-issues-action#168, v0.5.0)"
    )


@pytest.mark.parametrize("path", SYNC_WORKFLOWS, ids=_IDS)
def test_numeric_commit_app_id_secret_is_gone(path: Path) -> None:
    """No reference to the numeric COMMIT_APP_ID secret remains (retired by #1366)."""
    assert "secrets.COMMIT_APP_ID" not in path.read_text(encoding="utf-8")
