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

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKSPACE = REPO_ROOT / "assets" / "workspace"
DOC_RELPATH = "docs/DOWNSTREAM_RELEASE.md"


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
    """The synced copy is byte-identical to the devkit root SSoT (managed file)."""
    root = (REPO_ROOT / DOC_RELPATH).read_text(encoding="utf-8")
    scaffold = (WORKSPACE / DOC_RELPATH).read_text(encoding="utf-8")
    assert scaffold == root
