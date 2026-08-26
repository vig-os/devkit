"""Scaffolded Claude Code attribution suppression (#1562).

Claude Code appends AI attribution to commits and PR bodies of web and Remote
Control sessions: a ``Claude-Session:`` commit trailer and a bare
``claude.ai/code/session_…`` PR-body footer, gated by ``attribution.sessionUrl``
(default ``true`` — a separate gate from ``includeCoAuthoredBy``). Cloud
sessions never read a developer's ``~/.claude/settings.json``; the only
configuration they see is what is committed in the repo. The devkit scaffold is
therefore the single point that covers every consumer repo, so the workspace
template must ship a ``.claude/settings.json`` that suppresses every built-in
attribution channel.

The file is managed (option 1 of the issue): it is NOT in ``PRESERVE_FILES``,
so an upgrade regenerates it — the suppression rule is absolute, and no
consumer repo owns a ``.claude/settings.json`` today (verified across all four
orgs, 2026-08-26). It is strict JSON, so it must be exempt from the provenance
banner (a ``#``/``//`` banner would corrupt it for strict parsers).

Refs: #1562
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCAFFOLD_SETTINGS = REPO_ROOT / "assets" / "workspace" / ".claude" / "settings.json"
ROOT_SETTINGS = REPO_ROOT / ".claude" / "settings.json"
INIT_WORKSPACE = REPO_ROOT / "assets" / "init-workspace.sh"

# The full suppression block: both modern gates and the deprecated-but-still-read
# includeCoAuthoredBy as cheap insurance while both are honoured.
EXPECTED_ATTRIBUTION = {"commit": "", "pr": "", "sessionUrl": False}


def _load_sync_manifest():
    """Load scripts/sync_manifest.py the way the sibling manifest tests do."""
    scripts_dir = REPO_ROOT / "scripts"
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    spec = importlib.util.spec_from_file_location(
        "sync_manifest", scripts_dir / "sync_manifest.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["sync_manifest"] = module
    spec.loader.exec_module(module)
    return module


class TestScaffoldAttributionSettings:
    """The workspace template ships the attribution-suppression settings."""

    def test_scaffold_settings_exists_and_is_strict_json(self) -> None:
        assert SCAFFOLD_SETTINGS.is_file(), (
            "assets/workspace/.claude/settings.json missing — no repo scaffolded "
            "from devkit suppresses Claude Code session-link attribution"
        )
        # Strict json.loads: a provenance banner or JSONC comment would fail here.
        json.loads(SCAFFOLD_SETTINGS.read_text(encoding="utf-8"))

    def test_scaffold_settings_suppress_all_attribution_channels(self) -> None:
        settings = json.loads(SCAFFOLD_SETTINGS.read_text(encoding="utf-8"))
        assert settings.get("attribution") == EXPECTED_ATTRIBUTION
        assert settings.get("includeCoAuthoredBy") is False

    def test_scaffold_settings_is_managed_not_preserved(self) -> None:
        """Option 1 (#1562): the file is regenerated on upgrade, never consumer-owned."""
        sync_manifest = _load_sync_manifest()
        preserve = sync_manifest.load_preserve_files(INIT_WORKSPACE)
        assert ".claude/settings.json" not in preserve

    def test_scaffold_settings_is_banner_exempt(self) -> None:
        """Strict JSON: the sync-manifest banner pass must skip it or corrupt it."""
        sync_manifest = _load_sync_manifest()
        assert ".claude/settings.json" in sync_manifest._BANNER_SKIP  # noqa: SLF001


class TestDevkitRootAttributionSettings:
    """Devkit's own repo settings carry the same suppression (drift guard).

    The measured leak includes devkit's own merged main history, and cloud
    sessions on devkit read only the committed repo settings — so the root
    .claude/settings.json must carry the identical block the scaffold ships.
    """

    def test_root_settings_match_scaffold_attribution(self) -> None:
        root = json.loads(ROOT_SETTINGS.read_text(encoding="utf-8"))
        assert root.get("attribution") == EXPECTED_ATTRIBUTION
        assert root.get("includeCoAuthoredBy") is False
