"""Scaffold-render tests: the sync-issues knobs DEVKIT_SYNC_TARGET / DEVKIT_SYNC_SCHEDULE.

Issue #1228: trunk consumers whose ``main`` carries a require-PR ruleset cannot
let the scaffolded ``sync-issues.yml`` push directly to ``main`` (#1227). Two
optional ``.vig-os`` keys, realized entirely at scaffold time (schedule triggers
cannot take inputs), remediate this without a ruleset bypass:

- ``DEVKIT_SYNC_TARGET`` — the branch the sync job commits to. Default is
  workflow-model-aware (``dev`` gitflow / ``main`` trunk), preserving today's
  behavior byte-for-byte when unset. A protected-main consumer points it at an
  unprotected mirror branch (e.g. ``sync/issue-mirror``); the scaffolded job then
  bootstraps that branch from the default branch head if absent.
- ``DEVKIT_SYNC_SCHEDULE`` — cron override for the schedule trigger (default the
  current daily cron). Validated as a 5-field cron at scaffold time.

These drive the REAL ``init-workspace.sh`` end-to-end (the executed-bash style of
``tests/test_workflow_model.py`` / ``tests/test_ci_runner.py``).

Refs: #1228
"""

from __future__ import annotations

from pathlib import Path

from tests.workflow_scaffold import (
    INIT_WORKSPACE,
    WORKSPACE,
    scaffold,
)

# Repository root (tests/ -> repo root).
REPO_ROOT = Path(__file__).resolve().parent.parent

MIRROR = "sync/issue-mirror"
BOOTSTRAP_STEP = "Bootstrap sync target branch if absent"


def _seed(tmp_path: Path, name: str, manifest: str) -> Path:
    """Create a seed workspace holding a ``.vig-os`` with the given manifest text."""
    seed = tmp_path / f"{name}-seed"
    seed.mkdir()
    (seed / ".vig-os").write_text(manifest, encoding="utf-8")
    return seed


def _sync_yaml(
    tmp_path: Path,
    *,
    name: str,
    workflow: str | None = None,
    target: str | None = None,
    schedule: str | None = None,
) -> str:
    """Scaffold a workspace (optionally seeding the sync keys) and return its
    rendered ``sync-issues.yml`` text."""
    manifest_lines = []
    if target is not None:
        manifest_lines.append(f"DEVKIT_SYNC_TARGET={target}")
    if schedule is not None:
        manifest_lines.append(f"DEVKIT_SYNC_SCHEDULE={schedule}")
    seed = (
        _seed(tmp_path, name, "\n".join(manifest_lines) + "\n")
        if manifest_lines
        else None
    )
    proc = scaffold(tmp_path, workflow=workflow, seed=seed, name=name)
    assert proc.returncode == 0, proc.stderr
    return (tmp_path / name / ".github" / "workflows" / "sync-issues.yml").read_text(
        encoding="utf-8"
    )


# ── production wiring seams ───────────────────────────────────────────────────


def test_vig_os_declares_sync_keys() -> None:
    """The scaffold manifest ships both opt-in keys (default empty)."""
    text = (WORKSPACE / ".vig-os").read_text(encoding="utf-8")
    assert "DEVKIT_SYNC_TARGET=" in text
    assert "DEVKIT_SYNC_SCHEDULE=" in text


def test_init_workspace_invokes_render_sync_settings() -> None:
    """init-workspace.sh defines + invokes render_sync_settings."""
    init = INIT_WORKSPACE.read_text(encoding="utf-8")
    assert "render_sync_settings" in init


# ── unset = byte-for-byte today's behavior ────────────────────────────────────


def test_unset_gitflow_keeps_dev_default_and_daily_cron(tmp_path: Path) -> None:
    """No keys on gitflow => today's `dev` target + daily cron, no bootstrap."""
    text = _sync_yaml(tmp_path, name="gf-default")
    assert "default: 'dev'" in text
    assert "|| 'dev'" in text
    assert "cron: '0 2 * * *'" in text
    assert BOOTSTRAP_STEP not in text


def test_unset_trunk_keeps_main_default(tmp_path: Path) -> None:
    """No keys on trunk => the workflow-model `main` default is untouched."""
    text = _sync_yaml(tmp_path, name="tk-default", workflow="trunk")
    assert "default: 'main'" in text
    assert "|| 'main'" in text
    assert "|| 'dev'" not in text
    assert BOOTSTRAP_STEP not in text


# ── DEVKIT_SYNC_TARGET override ───────────────────────────────────────────────


def test_target_override_gitflow(tmp_path: Path) -> None:
    """A mirror target on gitflow replaces every `dev` sync target + bootstraps."""
    text = _sync_yaml(tmp_path, name="gf-target", target=MIRROR)
    assert f"default: '{MIRROR}'" in text
    assert f"|| '{MIRROR}'" in text
    assert "|| 'dev'" not in text
    assert "default: 'dev'" not in text
    assert BOOTSTRAP_STEP in text


def test_target_override_trunk(tmp_path: Path) -> None:
    """A mirror target on trunk replaces the rendered `main` sync target."""
    text = _sync_yaml(tmp_path, name="tk-target", workflow="trunk", target=MIRROR)
    assert f"default: '{MIRROR}'" in text
    assert f"|| '{MIRROR}'" in text
    assert "|| 'main'" not in text
    assert BOOTSTRAP_STEP in text


def test_bootstrap_step_creates_ref_from_default_branch(tmp_path: Path) -> None:
    """The injected bootstrap step creates the absent branch from the default head."""
    text = _sync_yaml(tmp_path, name="gf-bootstrap", target=MIRROR)
    assert "git/refs" in text
    assert "default_branch" in text
    # Uses the app token (same as the commit push), not the restricted GITHUB_TOKEN.
    assert "steps.generate-token.outputs.token" in text


def test_target_persisted_in_manifest(tmp_path: Path) -> None:
    """A custom target is written back to .vig-os (upgrade-persistent)."""
    seed = _seed(tmp_path, "persist", f"DEVKIT_SYNC_TARGET={MIRROR}\n")
    proc = scaffold(tmp_path, seed=seed, name="persist")
    assert proc.returncode == 0, proc.stderr
    text = (tmp_path / "persist" / ".vig-os").read_text(encoding="utf-8")
    assert f"DEVKIT_SYNC_TARGET={MIRROR}" in text


# ── DEVKIT_SYNC_SCHEDULE override ─────────────────────────────────────────────


def test_schedule_override(tmp_path: Path) -> None:
    """A cron override replaces the daily cron line."""
    text = _sync_yaml(tmp_path, name="sched", schedule="0 5 * * 0")
    assert "cron: '0 5 * * 0'" in text
    assert "cron: '0 2 * * *'" not in text


def test_schedule_persisted_in_manifest(tmp_path: Path) -> None:
    """A custom schedule is written back to .vig-os."""
    seed = _seed(tmp_path, "sched-persist", "DEVKIT_SYNC_SCHEDULE=0 5 * * 0\n")
    proc = scaffold(tmp_path, seed=seed, name="sched-persist")
    assert proc.returncode == 0, proc.stderr
    text = (tmp_path / "sched-persist" / ".vig-os").read_text(encoding="utf-8")
    assert "DEVKIT_SYNC_SCHEDULE=0 5 * * 0" in text


def test_target_and_schedule_combined(tmp_path: Path) -> None:
    """Both knobs compose: mirror target + weekly cron, on trunk."""
    text = _sync_yaml(
        tmp_path,
        name="combo",
        workflow="trunk",
        target=MIRROR,
        schedule="30 4 * * 1",
    )
    assert f"default: '{MIRROR}'" in text
    assert "cron: '30 4 * * 1'" in text
    assert BOOTSTRAP_STEP in text


# ── guards (format validation, loud at scaffold time) ─────────────────────────


def test_guard_rejects_bad_branch_name(tmp_path: Path) -> None:
    """An invalid git branch name is refused loudly before any mutation."""
    seed = _seed(tmp_path, "bad-branch", "DEVKIT_SYNC_TARGET=bad..name\n")
    proc = scaffold(tmp_path, seed=seed, name="bad-branch", check=False)
    assert proc.returncode != 0
    assert "Invalid DEVKIT_SYNC_TARGET" in proc.stderr


def test_guard_rejects_bad_cron_field_count(tmp_path: Path) -> None:
    """A cron with the wrong field count is refused loudly."""
    seed = _seed(tmp_path, "bad-cron", "DEVKIT_SYNC_SCHEDULE=0 2 * *\n")
    proc = scaffold(tmp_path, seed=seed, name="bad-cron", check=False)
    assert proc.returncode != 0
    assert "Invalid DEVKIT_SYNC_SCHEDULE" in proc.stderr


def test_guard_rejects_bad_cron_charset(tmp_path: Path) -> None:
    """A 5-field cron with a stray character is refused loudly."""
    seed = _seed(tmp_path, "bad-cron2", "DEVKIT_SYNC_SCHEDULE=0 2 * * @\n")
    proc = scaffold(tmp_path, seed=seed, name="bad-cron2", check=False)
    assert proc.returncode != 0
    assert "Invalid DEVKIT_SYNC_SCHEDULE" in proc.stderr
