"""Scaffold-shape test: the DOWNSTREAM_RELEASE.md reference must resolve.

Issue #1046: the scaffolded ``promote-release.yml`` header tells consumers to
"See ``docs/DOWNSTREAM_RELEASE.md``", but the scaffold shipped only
``COMMIT_MESSAGE_STANDARD.md`` and ``container-ci-quirks.md`` under
``assets/workspace/docs/`` — so every consumer carried a dangling reference to
its primary release documentation.

Option 1 (managed file): the doc is manifest-synced from the devkit root
(SSoT) into the scaffold, exactly like COMMIT_MESSAGE_STANDARD.md. These
assertions pin that the reference now resolves inside the scaffold.

Refs: #1046
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKSPACE = REPO_ROOT / "assets" / "workspace"
DOC_RELPATH = "docs/DOWNSTREAM_RELEASE.md"


def _load_transforms():
    spec = importlib.util.spec_from_file_location(
        "transforms", REPO_ROOT / "scripts" / "transforms.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["transforms"] = module
    spec.loader.exec_module(module)
    return module


def test_scaffold_ships_downstream_release_doc() -> None:
    """The scaffold ships the doc the promote workflow points at."""
    assert (WORKSPACE / DOC_RELPATH).is_file()


def test_promote_reference_resolves_in_scaffold() -> None:
    """The 'See docs/DOWNSTREAM_RELEASE.md' reference resolves from the consumer repo."""
    workflow = (WORKSPACE / ".github" / "workflows" / "promote-release.yml").read_text(
        encoding="utf-8"
    )
    assert DOC_RELPATH in workflow  # the reference exists...
    assert (WORKSPACE / DOC_RELPATH).exists()  # ...and now points at a shipped file


def test_scaffold_doc_matches_root_sssot() -> None:
    """The synced copy matches the devkit root SSoT once its banner is stripped.

    The scaffold copy carries the #1043 provenance banner (a managed file), so
    the comparison strips it with the Banner transform's own helper — never a
    re-encoded banner shape — leaving a guard on real content drift.
    """
    root = (REPO_ROOT / DOC_RELPATH).read_text(encoding="utf-8")
    scaffold = (WORKSPACE / DOC_RELPATH).read_text(encoding="utf-8")
    strip_banner = _load_transforms().strip_banner
    assert strip_banner(scaffold) == root
